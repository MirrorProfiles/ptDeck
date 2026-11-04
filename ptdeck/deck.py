"""The Stream Deck: pages (folders), button pictures, and reacting to presses."""
from __future__ import annotations

import queue
import re
import threading
import time
from pathlib import Path

import yaml
from PIL import Image, ImageDraw, ImageFont

# Key grid per model, used for previews and when no deck is plugged in.
MODELS = {
    "mini": (2, 3, 80), "original": (3, 5, 72), "mk2": (3, 5, 72), "xl": (4, 8, 96),
    "plus": (2, 4, 120), "neo": (2, 4, 96),
}

BUTTON_FIELDS = {"label", "macro", "folder", "back", "home", "icon", "color", "text color",
                 "key", "font size", "note", "outline", "live", "live track", "corner", "metric", "metric ab", "glyph", "style", "audiosuite", "live name", "font", "strip", "strip color", "strip text color", "color bar", "if empty", "metric toggle",
                 "lit menu", "lit color", "lit label", "lit text color", "lit outline", "gradient", "palette color"}

FONT_PATHS = [
    "/System/Library/Fonts/SFNS.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


class ConfigError(Exception):
    pass


# ---------- layout (pure logic) ----------

def load_config(path: Path) -> dict:
    if not Path(path).exists():
        raise ConfigError(f"deck.yaml is missing. It should be in {Path(path).parent}/ "
                          "next to 'Start PT Deck.command'. Copy it in from the latest download.")
    try:
        cfg = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{Path(path).name} has a formatting mistake: {e}") from None
    if not isinstance(cfg.get("pages"), dict) or not cfg["pages"]:
        raise ConfigError("deck.yaml needs a 'pages:' section with at least one page")
    cfg.setdefault("home", next(iter(cfg["pages"])))
    if cfg["home"] not in cfg["pages"]:
        raise ConfigError(f"home page '{cfg['home']}' isn't one of the pages")
    return cfg


PAGE_SETTINGS = {"back button", "back label", "back color", "back font size", "page titles",
                 "title pattern", "icon style", "key font"}


def page_cfg(cfg: dict, page: str) -> dict:
    """Deck-wide settings with this page's own 'page settings' on top (e.g. one page plain, the rest designed)."""
    own = (cfg.get("page settings") or {}).get(page) or {}
    return {**cfg, **{k: v for k, v in own.items() if k in PAGE_SETTINGS}}


def layout(cfg: dict, page: str, key_count: int, base=None) -> list[dict | None]:
    """Which button goes on which key for a page. Folder pages get a Back button on key 1."""
    cfg = page_cfg(cfg, page)
    items = cfg["pages"].get(page)
    if items is None:
        raise ConfigError(f"There's no page called '{page}'")
    slots: list[dict | None] = [None] * key_count
    auto_back = page != cfg["home"] and cfg.get("back button", True)
    if auto_back:
        slots[0] = {"label": cfg.get("back label", "↑"), "back": True, "color": cfg.get("back color", "#505050"),
                    "font size": cfg.get("back font size", 40)}
    fill = []
    for item in items or []:
        if item in (None, "blank", "", {}):
            fill.append(None)
            continue
        if not isinstance(item, dict):
            raise ConfigError(f"Page '{page}': button {item!r} should look like 'label: ..., macro: ...'")
        if "key" in item:
            k = int(item["key"]) - 1
            if not 0 <= k < key_count:
                raise ConfigError(f"Page '{page}': key {item['key']} doesn't exist on this deck")
            slots[k] = item
        else:
            fill.append(item)
    free = (i for i in range(key_count) if slots[i] is None)
    for item in fill:
        i = next(free, None)
        if i is None:
            raise ConfigError(f"Page '{page}' has more buttons than the deck has keys ({key_count})")
        slots[i] = item  # None keeps the key blank
    if cfg.get("key font"):                 # the page's font, for keys that don't name their own
        for i, b in enumerate(slots):
            if b and not b.get("font") and not b.get("banner"):
                slots[i] = dict(b, _font=cfg["key font"])
    if str(cfg.get("icon style", "classic")).lower() == "designed":
        for i, b in enumerate(slots):
            if b and not b.get("back") and not b.get("banner"):
                slots[i] = dict(b, _look="designed")
        if base is not None:
            from .look import match_sizes
            match_sizes(slots, base, COLUMNS.get(key_count, 8))
    if auto_back and cfg.get("page titles", True):
        _add_title_banner(slots, page, COLUMNS.get(key_count, 8),
                          pattern=str(cfg.get("title pattern", "237")).lower() not in ("none", "off", "false"))
    return slots


COLUMNS = {32: 8, 15: 5, 6: 3, 8: 4}   # keys per row for each Stream Deck size


def _add_title_banner(slots, page, cols, pattern=True):
    """On a folder page, write the page name across the longest run (3+) of empty keys
    in the top row, as one banner sliced over those keys."""
    best, run = (0, 0), []
    for i in range(1, cols):
        if slots[i] is None:
            run.append(i)
            if len(run) > best[1]:
                best = (run[0], len(run))
        else:
            run = []
    start, n = best
    if n >= 3:
        for j in range(n):
            slots[start + j] = {"banner": str(page), "part": j, "parts": n, "col": start + j}
    if pattern:
        # Any other empty keys in the top row: the carpet, continuous along the row.
        for i in range(1, cols):
            if slots[i] is None:
                slots[i] = {"banner": "carpet", "carpet": True, "part": 0, "parts": 1, "col": i}


def check_config(cfg: dict, base: Path, library=None, key_count: int = 32) -> list[str]:
    problems = []
    for page, items in cfg["pages"].items():
        try:
            layout(cfg, page, key_count)
        except ConfigError as e:
            problems.append(str(e))
        for item in items or []:
            if not isinstance(item, dict):
                continue
            bad = [k for k in item if k not in BUTTON_FIELDS]
            if bad:
                problems.append(f"Page '{page}': unknown button setting '{bad[0]}'")
            if "folder" in item and item["folder"] not in cfg["pages"]:
                problems.append(f"Page '{page}': folder '{item['folder']}' has no page")
            if "icon" in item and not icon_path(base, item["icon"]).exists():
                problems.append(f"Page '{page}': icon file '{item['icon']}' not found in icons folder")
            if "macro" in item and library is not None:
                try:
                    library.get(item["macro"])
                except Exception as e:  # noqa: BLE001
                    problems.append(f"Page '{page}': {e}")
    return problems


# ---------- drawing ----------

def icon_path(base: Path, name: str) -> Path:
    p = Path(name).expanduser()
    return p if p.is_absolute() else Path(base) / "icons" / p


_font_cache: dict = {}


def font(size: int):
    if size not in _font_cache:
        f = None
        for p in FONT_PATHS:
            if Path(p).exists():
                try:
                    f = ImageFont.truetype(p, size)
                    break
                except OSError:
                    continue
        _font_cache[size] = f or ImageFont.load_default(size=size)
    return _font_cache[size]


FONT_DIRS = ["~/Library/Fonts", "/Library/Fonts", "/System/Library/Fonts", "/System/Library/Fonts/Supplemental",
             # Adobe Fonts (Creative Cloud) keeps activated fonts here, under hidden file names
             "~/Library/Application Support/Adobe/CoreSync/plugins/livetype",
             "/usr/share/fonts"]
_named_index: dict | None = None
missing_fonts: set = set()       # key fonts asked for but not found (the deck logs each once)


def _coretext_font(name: str):
    """Ask macOS for a font by name, the way apps' font menus do. Finds fonts wherever they're installed,
    including ones activated by Adobe Fonts or a font manager. (file, index) or None."""
    try:
        import CoreText
    except Exception:  # noqa: BLE001 - not a Mac, or the CoreText bridge isn't installed
        return None
    want = _squash(name)
    for cand in dict.fromkeys([name, name.replace(" ", "-"), name.replace(" ", "")]):
        try:
            f = CoreText.CTFontCreateWithName(cand, 12, None)
            if f is None:
                continue
            names = {_squash(CoreText.CTFontCopyFullName(f) or ""), _squash(CoreText.CTFontCopyPostScriptName(f) or "")}
            if want not in names:                   # macOS hands back a stand-in when it has no match
                continue
            url = CoreText.CTFontCopyAttribute(f, CoreText.kCTFontURLAttribute)
            path = str(url.path()) if url is not None else None
        except Exception:  # noqa: BLE001
            continue
        if not path or not Path(path).exists():
            continue
        for idx in range(16 if path.lower().endswith(".ttc") else 1):   # which face in a collection
            try:
                family, style = ImageFont.truetype(path, 12, index=idx).getname()
            except (OSError, ValueError):
                break
            plain = str(style).lower() in ("regular", "book", "normal", "roman")
            if want in (_squash(f"{family} {style}"), _squash(family) if plain else ""):
                return path, idx
        return path, 0
    return None


def _squash(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(name).lower())


WEIGHT_WORDS = {"thin", "hairline", "light", "book", "regular", "normal", "roman", "medium", "demi", "demibold",
                "semibold", "bold", "heavy", "black", "extrabold", "ultra"}
font_substitutes: dict = {}      # asked-for key font -> the installed font used instead


def font_candidates(name: str) -> list[str]:
    """The name, then the same family with fewer words, keeping the weight:
    'Futura PT Medium' -> 'Futura PT Medium', 'Futura PT', 'Futura Medium', 'Futura'.
    (macOS ships 'Futura' with a Medium weight; 'Futura PT' is Paratype's separate font.)"""
    words = str(name).split()
    weight = words[-1] if len(words) > 1 and words[-1].lower() in WEIGHT_WORDS else None
    family = words[:-1] if weight else words
    out = [str(name)]
    if weight:
        out.append(" ".join(family))
    for k in range(len(family) - 1, 0, -1):
        if weight:
            out.append(" ".join(family[:k] + [weight]))
        out.append(" ".join(family[:k]))
    return list(dict.fromkeys(out))


def _font_index() -> dict:
    """squashed font name -> (file, index), from every font file in FONT_DIRS (built once)."""
    global _named_index
    if _named_index is not None:
        return _named_index
    index, files = {}, []
    from .paths import ASSETS
    for d in FONT_DIRS + [str(Path(ASSETS) / "fonts")]:
        root = Path(d).expanduser()
        if root.is_dir():
            files += [p for p in root.rglob("*") if p.suffix.lower() in (".ttf", ".otf", ".ttc")]
    for p in files:                       # names inside each font first...
        for idx in range(16 if p.suffix.lower() == ".ttc" else 1):
            try:
                family, style = ImageFont.truetype(str(p), 12, index=idx).getname()
            except (OSError, ValueError):
                break
            plain = str(style).lower() in ("regular", "book", "normal", "roman")
            for key in (_squash(f"{family} {style}"), _squash(family) if plain else None):
                if key:
                    index.setdefault(key, (str(p), idx))
    for p in files:                       # ...then file names (FuturaPT-Medium.otf) for anything else
        index.setdefault(_squash(p.stem), (str(p), 0))
    _named_index = index
    return index


def find_font(name: str):
    """(file, index) of an installed font by its name as Font Book shows it, e.g. 'Futura PT Medium'.
    Asks macOS first, then searches the font folders; if that exact font isn't installed, the same family
    with fewer words (see font_candidates) is used instead, and remembered in font_substitutes."""
    for cand in font_candidates(name):
        found = _coretext_font(cand) or _font_index().get(_squash(cand))
        if found:
            if cand != name:
                font_substitutes[str(name)] = cand
            return found
    return None


def named_font(name, size: int):
    """A key font by name ('narrow' = PT Deck's condensed font); falls back to the standard font."""
    if not name:
        return font(size)
    if str(name).lower() == "narrow":
        from .look import font as look_font
        return look_font("narrow", size)
    key = (str(name), size)
    if key not in _font_cache:
        found = find_font(str(name))
        try:
            _font_cache[key] = ImageFont.truetype(found[0], size, index=found[1]) if found else font(size)
        except OSError:
            found = None
            _font_cache[key] = font(size)
        if not found:
            missing_fonts.add(str(name))
    return _font_cache[key]


def _wrap(draw, text, fnt, width):
    lines = []
    for para in str(text).split("\n"):
        words, line = para.split(), ""
        for w in words:
            test = f"{line} {w}".strip()
            if draw.textlength(test, font=fnt) <= width or not line:
                line = test
            else:
                lines.append(line)
                line = w
        lines.append(line)
    return lines


def _banner_words(text: str, parts: int) -> list[str]:
    """Split a page title into whole words, at most one group per key."""
    words = str(text).upper().split() or [""]
    while len(words) > parts:                       # too many words: join the shortest neighbours
        i = min(range(len(words) - 1), key=lambda k: len(words[k]) + len(words[k + 1]))
        words[i:i + 2] = [words[i] + " " + words[i + 1]]
    return words


def _banner_font(px):
    """Page titles: the tall capitals used for folders."""
    from .look import font as look_font
    return look_font("folder", int(px * 1.25))


_carpet_cache: dict = {}


def carpet_tile(col: int, size: int, base=None) -> Image.Image | None:
    """Key 'col' of the Room 237 carpet running along the top row (one continuous rug)."""
    key = (col, size)
    if key not in _carpet_cache:
        from .paths import DATA
        src = Path(base or DATA) / "icons" / "source" / "carpet-237.png"
        try:
            tile = Image.open(src).convert("RGB")
        except OSError:
            return None
        t = int(size * 1.4)                                  # one repeat of the pattern
        tile = tile.resize((t, t), Image.LANCZOS)
        x0 = (col * size) % t
        strip = Image.new("RGB", (t * 2 + size, size))
        for k in range(0, t * 2 + size, t):
            strip.paste(tile, (k, 0))
        _carpet_cache[key] = strip.crop((x0, 0, x0 + size, size))
    return _carpet_cache[key].copy()


def render_banner(text: str, part: int, parts: int, size: int, col=None, base=None) -> Image.Image:
    """One key of a page-title banner: each word sits whole on its own key (never cut across
    the gap between keys), centred along the row, all words the same size. Behind it (and on
    empty top-row keys) runs the Room 237 carpet, with the title on a dark band."""
    img = carpet_tile(int(col), size, base) if col is not None else None
    if img is None:
        img = Image.new("RGB", (size, size), "#141414")
    if text:
        band = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        ImageDraw.Draw(band).rectangle([0, size * 0.27, size, size * 0.73], fill=(22, 10, 8, 225))
        img = Image.alpha_composite(img.convert("RGBA"), band).convert("RGB")
    elif col is not None:
        return img
    d = ImageDraw.Draw(img)
    words = _banner_words(text, parts)
    first = (parts - len(words)) // 2
    fs = int(size * 0.34)
    while fs > 9 and any(d.textlength(w, font=_banner_font(fs)) > size * 0.9 for w in words):
        fs -= 1
    f = _banner_font(fs)
    i = part - first
    if 0 <= i < len(words):
        w = words[i]
        box = d.textbbox((0, 0), w, font=f)
        d.text(((size - (box[2] - box[0])) / 2 - box[0], (size - (box[3] - box[1])) / 2 - box[1]),
               w, fill="#f2e6cf", font=f)
    return img


SLOT_LETTERS = "ABCDEFGHIJ"
LIVE_STYLES = {   # insert state -> (background, text colour)
    "active": ("#16324f", "#ffffff"), "bypassed": ("#6a5410", "#ffffff"),
    "inactive": ("#2e2e2e", "#8a8a8a"), "empty": ("#0d0d0d", "#4a4a4a"),
}


def plugin_icon(base: Path, plugin: str):
    """A picture named after the plug-in (e.g. 'UADx Manley Massive Passive EQ.png'), in
    icons/plugins or icons. Spaces, capitals and punctuation in the file name don't matter."""
    if not plugin:
        return None
    want = re.sub(r"[^a-z0-9]+", "", plugin.lower())
    for sub in ("plugins", ""):
        folder = Path(base) / "icons" / sub if sub else Path(base) / "icons"
        if not folder.is_dir():
            continue
        for f in folder.glob("*.png"):
            if re.sub(r"[^a-z0-9]+", "", f.stem.lower()) == want:
                return f"{sub}/{f.name}" if sub else f.name
    return None


def live_button(button: dict, info, base: Path) -> dict:
    """A live insert key's look, from (plug-in name, state) read from Pro Tools."""
    slot = int(button["live"])
    letter = SLOT_LETTERS[slot - 1] if 1 <= slot <= 10 else "?"
    out = {k: v for k, v in button.items() if k not in ("label", "icon", "color", "text color")}
    if info is None:                                    # Pro Tools not reachable / track not shown
        out.update(label=f"Insert {slot}\n–", color="#141414", **{"text color": "#555555"})
    else:
        name, state = info[0], info[1]
        tcol = info[2] if len(info) > 2 else None
        style = "empty" if name in ("", "unassigned") else (
            "inactive" if "inactive" in state else "bypassed" if "bypassed" in state else "active")
        bg, fg = LIVE_STYLES[style]
        if tcol and style == "active":
            bg = track_tint(tcol)            # active plug-ins wear the track's colour
        out.update(color=bg, **{"text color": fg})
        if tcol:
            out["color bar"] = tcol          # like Pro Tools' track colour strip
        icon = plugin_icon(base, name) if style != "empty" else None
        if icon:
            out["icon"] = icon
        else:
            out["label"] = "empty" if style == "empty" else name
        if state.startswith("open"):
            out["outline"] = "#ffffff"
            out["folder_outline"] = True
    out["corner"] = f"{slot} {letter}"
    out.setdefault("font", "narrow")
    return out


METRIC_STYLES = {"selected": ("#d9894f", "#1a1a1a"), "normal": ("#1d2a38", "#e0a274"),
                 "unknown": ("#141c24", "#6c7f92")}


def metric_toggle_button(button: dict, on) -> dict:
    """A MetricAB on/off key (Sides, Loudness Match): lit orange like the plug-in when on."""
    which = str(button["metric toggle"]).lower()
    out = {k: v for k, v in button.items() if k not in ("color", "text color")}
    out.setdefault("label", {"sides": "SIDES", "match": "LOUDNESS\nMATCH"}.get(which, which.upper()))
    if on:
        out.update(color="#d9894f", **{"text color": "#1a1a1a"})
    else:
        out.update(color="#1d2a38", **{"text color": "#e0a274" if on is not None else "#6c7f92"})
    out["corner"] = out.get("corner", "")
    return out


def metric_ab_button(button: dict, ab: str | None) -> dict:
    """MetricAB's A/B key: a big A on orange, or a big B the other way round."""
    out = {k: v for k, v in button.items() if k not in ("label", "icon", "color", "text color")}
    if ab == "A":
        out.update(label="A", color="#d9894f", **{"text color": "#1a1a1a"})
    elif ab == "B":
        out.update(label="B", color="#1a1a1a", **{"text color": "#d9894f"})
    else:
        out.update(label="A/B", color="#1d2a38", **{"text color": "#6c7f92"})
    out.setdefault("font size", 64 if ab else 34)
    out["corner"] = out.get("corner", "")
    return out


def metric_button(button: dict, names: dict | None, selected: str | None) -> dict:
    """A MetricAB slot key: the song name (if known), lit orange when it's the selected slot."""
    slot = str(button["metric"]).upper()
    name = (names or {}).get(slot, "")
    style = "selected" if slot == selected else ("normal" if name else "unknown")
    bg, fg = METRIC_STYLES[style]
    out = {k: v for k, v in button.items() if k not in ("label", "icon", "color", "text color")}
    out.update(label=name or slot, color=bg, corner=slot, **{"text color": fg})
    if not name:
        out.setdefault("font size", 30)
    return out


def _remembered(base, key):
    from . import settings
    return settings.get(base, key)


def live_name_button(button: dict, info) -> dict:
    """Shows which track a row of live insert keys is following."""
    which = str(button["live name"])
    name, count = (info[0], info[1]) if info else (None, 0)
    tcol = info[2] if info and len(info) > 2 else None
    out = {k: v for k, v in button.items() if k not in ("label", "icon", "color", "text color")}
    caption = "SELECTED" if which.lower() == "selected" else "TRACK"
    more = f"\n+{count - 1} more" if count and count > 1 else ""
    out.update(label=(name or ("none selected" if which.lower() == "selected" else which)) + more,
               color=track_tint(tcol, 0.5) if tcol else "#0f1720", font="narrow", corner=caption,
               **{"text color": "#ffffff" if name else "#6c7f92"})
    if tcol:
        out["color bar"] = tcol
    return out


def track_tint(colour, keep=0.42):
    """A track colour darkened enough for white text to stay readable."""
    from .look import rgb
    r, g, b = rgb(colour)
    return "#%02x%02x%02x" % (int(r * keep), int(g * keep), int(b * keep))


def palette_button(button: dict, base) -> dict:
    """A 'palette color: N' key takes Pro Tools' own colour N as its background (once PT Deck has read
    the palette from Pro Tools; until then its 'color' is shown)."""
    from .ptsl import COLOUR_BASE
    pal = _remembered(base, "track palette") or []
    try:
        i = int(button["palette color"]) - COLOUR_BASE
    except (TypeError, ValueError):
        return button
    if 0 <= i < len(pal):
        return dict(button, color=pal[i])
    return button


def render(button: dict | None, size: int, base: Path, state: str = "idle") -> Image.Image:
    """Draw one key. state: idle / running / ok / error."""
    if button and button.get("palette color") is not None:
        button = palette_button(button, base)
    if button and button.get("live") and "corner" not in button:
        button = live_button(button, None, base)        # previews / Manager: placeholder look
    if button and button.get("live name") and "corner" not in button:
        button = live_name_button(button, (button["live name"], 1) if str(button["live name"]).lower() != "selected" else None)
    if button and button.get("metric toggle") and "corner" not in button:
        button = metric_toggle_button(button, _remembered(base, f"metric {str(button['metric toggle']).lower()}"))
    if button and button.get("metric ab") and "corner" not in button:
        button = metric_ab_button(button, _remembered(base, "metric ab"))
    if button and button.get("metric") and "corner" not in button:
        button = metric_button(button, _remembered(base, "metric names"), _remembered(base, "metric selected"))
    if button and button.get("banner"):
        if button.get("carpet"):                          # an empty top-row key: just the carpet
            return carpet_tile(int(button.get("col", 0)), size, base) or Image.new("RGB", (size, size), "#141414")
        return render_banner(button["banner"], int(button.get("part", 0)), int(button.get("parts", 1)), size,
                             col=button.get("col"), base=base)
    if (button and button.get("_look") == "designed" and not button.get("icon")
            and "corner" not in button and not button.get("live")):
        from .look import render_designed
        img = render_designed(button, size, base)
        ring = {"running": "#ffcc00", "ok": "#33dd66", "error": "#ff3333"}.get(state)
        if ring:
            ImageDraw.Draw(img).rectangle([0, 0, size - 1, size - 1], outline=ring, width=max(3, size // 14))
        return img
    bg = (button or {}).get("color", "#000000")
    img = Image.new("RGB", (size, size), bg)
    if not button:
        return img
    if button.get("gradient"):              # colours blended left to right, e.g. a rainbow
        img.paste(gradient_image(button["gradient"], size), (0, 0))
    d = ImageDraw.Draw(img)
    label = str(button.get("label", "")).replace("\\n", "\n")
    icon = button.get("icon")
    pad = max(3, size // 16)
    bar = max(4, size // 11) if button.get("color bar") else 0      # the track colour strip
    text_top = pad + bar + (size // 7 if button.get("corner") else 0)   # room for the strip + slot label
    if icon:
        try:
            ic = Image.open(icon_path(base, icon)).convert("RGBA")
            if not label:              # picture only: fill the whole key
                ic = ic.resize((size, size), Image.LANCZOS)
                img.paste(ic, (0, 0), ic)
                text_top = size
            else:
                box = int(size * 0.62)
                ic.thumbnail((box, box))
                img.paste(ic, ((size - ic.width) // 2, pad), ic)
                text_top = pad + ic.height + 1
        except (OSError, ValueError):
            d.text((pad, pad), "?", fill="red", font=font(size // 3))
    if label:
        avail_h = size - text_top - pad
        fs = int(button.get("font size", size // 5 if not icon else size // 7))
        while True:
            fnt = named_font(button.get("font") or button.get("_font"), fs)
            lines = _wrap(d, label, fnt, size - 2 * pad)
            lh = fs + 2
            if (len(lines) * lh <= avail_h and all(d.textlength(l, font=fnt) <= size - 2 * pad for l in lines)) or fs <= 8:
                break
            fs -= 1
        y = text_top + (avail_h - len(lines) * lh) // 2 if not icon else size - pad - len(lines) * lh
        for line in lines:
            w = d.textlength(line, font=fnt)
            d.text(((size - w) / 2, y), line, fill=button.get("text color", "white"), font=fnt)
            y += lh
    if button.get("color bar"):   # track colour strip along the top
        d.rectangle([0, 0, size, bar], fill=button["color bar"])
    if button.get("corner"):    # small slot label in the top-left (live insert keys)
        cf = font(max(9, size // 8))
        d.text((max(3, size // 18), max(2, size // 24) + bar), str(button["corner"]), fill="#9fb6cc", font=cf)
    if (button.get("folder") or button.get("folder_outline")) and button.get("outline") != "none":
        w = max(3, size // 12) if button.get("_lit_outline") else max(2, size // 36)   # lit: easy to see
        d.rounded_rectangle([w // 2 + 1, w // 2 + 1, size - w // 2 - 2, size - w // 2 - 2],
                            radius=size // 10, outline=button.get("outline", "#d8d8d8"), width=w)
    ring = {"running": "#ffcc00", "ok": "#33dd66", "error": "#ff3333"}.get(state)
    if ring:
        d.rectangle([0, 0, size - 1, size - 1], outline=ring, width=max(3, size // 14))
    return img


def gradient_image(colours, size: int) -> Image.Image:
    from .look import rgb
    cols = [rgb(c) for c in (colours if isinstance(colours, list) else str(colours).split(","))]
    img = Image.new("RGB", (size, size))
    if len(cols) < 2:
        cols = cols * 2
    px = img.load()
    for x in range(size):
        t = x / max(1, size - 1) * (len(cols) - 1)
        i = min(int(t), len(cols) - 2)
        f = t - i
        c = tuple(int(cols[i][j] + (cols[i + 1][j] - cols[i][j]) * f) for j in range(3))
        for y in range(size):
            px[x, y] = c
    return img


def lit_paths(button: dict) -> list[str]:
    """A key's 'lit menu' as a list of menu paths: one path, or several that must all be ticked
    (e.g. ['Options > Solo Mode > AFL*', 'Options > Solo Mode > X-OR*'])."""
    v = button.get("lit menu") if button else None
    if not v:
        return []
    return [str(p) for p in v] if isinstance(v, list) else [str(v)]


def lit_button(button: dict, on) -> dict:
    """A 'lit menu' key: its lit look while that Pro Tools menu item is ticked."""
    if not on:
        return button
    out = dict(button, color=button.get("lit color", button.get("color")))
    out.pop("gradient", None) if button.get("lit color") else None
    if button.get("lit label"):
        out["label"] = button["lit label"]
    if button.get("lit text color"):
        out["text color"] = button["lit text color"]
    if button.get("lit outline"):          # shows on picture keys too, where a background can't
        out["outline"], out["folder_outline"], out["_lit_outline"] = button["lit outline"], True, True
    return out


def preview(cfg: dict, base: Path, page: str, model: str = "original") -> Image.Image:
    rows, cols, size = MODELS[model]
    gap = 10
    sheet = Image.new("RGB", (cols * (size + gap) + gap, rows * (size + gap) + gap), "#1b1b1b")
    for i, btn in enumerate(layout(cfg, page, rows * cols, base)):
        r, c = divmod(i, cols)
        sheet.paste(render(btn, size, base), (gap + c * (size + gap), gap + r * (size + gap)))
    return sheet


# ---------- the live deck ----------

class DeckController:
    """Connects pages + macros to the physical Stream Deck."""

    def __init__(self, base: Path, runner, log=print):
        self.base = Path(base)
        self.cfg_path = self.base / "deck.yaml"
        self.runner = runner
        self.log = log
        self.cfg = load_config(self.cfg_path)
        self.page = self.cfg["home"]
        self.history: list[str] = []
        self.jobs: queue.Queue = queue.Queue()
        self.deck = None
        self.slots: list = []
        self._mtime = self.cfg_path.stat().st_mtime
        self._stop = threading.Event()
        self.menu_lit, self._menu_read, self._menu_items = {}, {}, {}

    # pure-ish parts, also used by tests
    def key_count(self):
        if self.deck:
            return self.deck.key_count()
        rows, cols, _ = MODELS.get(str(self.cfg.get("model", "xl")), MODELS["xl"])
        return rows * cols

    def go(self, page):
        if page != self.page:
            self.history.append(self.page)
        self.page = page
        self.draw()
        self._warm_up(page)

    def _warm_up(self, page):
        """Opening a page with bounce keys: find the session's insert slots in the background,
        so the hardware-insert check is quick when a bounce key is pressed."""
        items = self.cfg["pages"].get(page) or []
        if self.runner is None or not any(isinstance(b, dict) and "bounce" in str(b.get("macro", "")).lower()
                                          for b in items):
            return
        prep = getattr(self.runner, "prepare_insert_scan", None)
        if prep:
            threading.Thread(target=prep, daemon=True).start()

    def pressed(self, key: int):
        btn = self.slots[key] if key < len(self.slots) else None
        if not btn:
            return
        if btn.get("back"):
            self.page = self.history.pop() if self.history else self.cfg["home"]
            self.draw()
        elif btn.get("home"):
            self.history.clear()
            self.page = self.cfg["home"]
            self.draw()
        elif btn.get("folder"):
            self.go(btn["folder"])
        elif btn.get("macro"):
            self.jobs.put((self.page, key, btn))

    live: dict = {}          # key -> (plug-in name, state) last read from Pro Tools
    metric_state: dict | None = None   # MetricAB: {'selected': 'B2', 'names': {...}}

    menu_lit: dict = {}      # menu_key -> ticked, for 'lit menu' keys (shared with the runner)
    _menu_read: dict = {}    # menu_key -> last tick read from Pro Tools
    _menu_items: dict = {}   # menu_key -> the menu item element, remembered so a re-check is one request

    def shown(self, k, btn):
        """The button as drawn: live insert keys take their look from Pro Tools."""
        if btn and btn.get("lit menu"):
            return lit_button(btn, self._lit(btn))
        if btn and btn.get("live"):
            return live_button(btn, self.live.get((self.page, k)), self.base)
        if btn and btn.get("live name"):
            return live_name_button(btn, self.live.get((self.page, k)))
        if btn and btn.get("metric toggle"):
            return metric_toggle_button(btn, _remembered(self.base, f"metric {str(btn['metric toggle']).lower()}"))
        if btn and (btn.get("metric") or btn.get("metric ab")):
            m = self.metric_state or {"names": _remembered(self.base, "metric names"),
                                      "selected": _remembered(self.base, "metric selected"),
                                      "ab": _remembered(self.base, "metric ab")}
            if btn.get("metric ab"):
                return metric_ab_button(btn, m.get("ab"))
            return metric_button(btn, m.get("names"), m.get("selected"))
        return btn

    status = "Starting…"      # one line for the menu bar app

    def stop(self):
        """Let go of the Stream Deck (for Quit / Restart)."""
        self._stop.set()
        deck, self.deck = self.deck, None
        if deck:
            try:
                with deck:
                    deck.reset()
                    deck.close()
            except Exception:  # noqa: BLE001
                pass

    # What the deck is showing, for the Manager's 'Mirror deck' view.
    version = 0
    key_states: dict = {}

    def mirror(self) -> dict:
        return {"page": self.page, "version": self.version, "connected": self.deck is not None}

    def mirror_key(self, k: int, size: int = 96):
        """Key k exactly as the deck shows it now (live keys, running/ok/error rings and all)."""
        slots = self.slots or layout(self.cfg, self.page, self.key_count(), self.base)
        btn = slots[k] if 0 <= k < len(slots) else None
        return render(self.shown(k, btn), size, self.base, self.key_states.get((self.page, k), "idle"))

    def _say_missing_fonts(self):
        said = self.__dict__.setdefault("_fonts_said", set())
        for f, used in sorted(font_substitutes.items()):
            if ("sub", f) not in said:
                said.add(("sub", f))
                self.log(f"key font '{f}' isn't installed, so keys use '{used}' (the nearest installed font).")
        for f in sorted(missing_fonts - said):
            said.add(f)
            self.log(f"✗ key font '{f}' isn't installed (or macOS won't share it), so keys use the standard font. "
                     "Check the name in Font Book; Adobe Fonts must be switched on in Creative Cloud.")

    def draw(self, only: int | None = None, state: str = "idle"):
        self.slots = layout(self.cfg, self.page, self.key_count(), self.base)
        self.version += 1
        if only is None:
            self.key_states = {}
        else:
            self.key_states = {**self.key_states, (self.page, only): state}
        deck = self.deck
        if not deck:
            self._say_missing_fonts()
            return
        from StreamDeck.ImageHelpers import PILHelper
        try:
            size = deck.key_image_format()["size"][0]
            with deck:
                for k, btn in enumerate(self.slots):
                    if only is not None and k != only:
                        continue
                    img = render(self.shown(k, btn), size, self.base, state if only is not None else "idle")
                    deck.set_key_image(k, PILHelper.to_native_key_format(deck, img))
        except Exception as e:  # noqa: BLE001 - unplugged / taken by another app mid-draw
            self._lost(e)
        self._say_missing_fonts()

    def poller(self):
        if getattr(self, "_poller", None) is None:     # its own reader, separate from running macros
            self._poller = type(self.runner)(self.runner.sys, self.runner.lib, log=lambda m: None)
        return self._poller

    busy = False

    def poll_metric(self, fresh=False):
        """Update the MetricAB slot keys (selected slot + song names); return keys that changed."""
        keys = [k for k, b in enumerate(self.slots)
                if b and (b.get("metric") or b.get("metric ab") or b.get("metric toggle"))]
        if not keys or self.runner is None:
            return []
        if getattr(self, "_metric", None) is None:
            from .metric import MetricReader
            self._metric = MetricReader(self.poller(), self.base, log=self.log)
            self._metric.paused = lambda: self.busy
        self._metric_tick = getattr(self, "_metric_tick", 0) + 1
        # Song names (a picture + text reading) every 3 seconds; the selected slot every second.
        names_wanted = any(self.slots[k].get("metric") for k in keys)
        state = self._metric.poll(want_names=names_wanted and not fresh and self._metric_tick % 3 == 1)
        from . import settings as _st
        new = {"names": state["names"], "selected": state["selected"], "ab": state.get("ab"),
               "sides": _st.get(self.base, "metric sides"), "match": _st.get(self.base, "metric match")}
        if new == self.metric_state:
            return []
        old = self.metric_state or {}
        if (old.get("selected"), old.get("ab")) != (new["selected"], new["ab"]) or old.get("names") != new["names"]:
            named = sum(1 for n in (new["names"] or {}).values() if n)
            self.log(f"MetricAB ({'window open' if state['open'] else 'window closed'}): slot {new['selected']},"
                     f" playing {new['ab']}, {named} song names")
        self.metric_state = new
        return keys

    def _saw_plugin(self, name):
        """Remember plug-in names seen on your tracks (for the Manager's plug-in pictures)."""
        if not name or name in ("unassigned",):
            return
        seen = getattr(self, "_seen", None)
        if seen is None:
            from . import settings
            seen = self._seen = set(settings.get(self.base, "seen plugins", []) or [])
        if name not in seen:
            from . import settings
            seen.add(name)
            settings.put(self.base, "seen plugins", sorted(seen)[:1000])

    def _ptsl_problem(self, e):
        """Say once (not every second) when the live keys can't ask Pro Tools for the selected
        track or track colours, and again when it works."""
        msg = str(e) if e else None
        if msg != getattr(self, "_ptsl_said", None):
            if msg:
                self.log(f"✗ live keys: can't read the selected track / colours from Pro Tools ({msg})")
            elif getattr(self, "_ptsl_said", None):
                self.log("live keys: reading the selected track and colours again")
            self._ptsl_said = msg

    def poll_live(self, fresh=False):
        """Read the live insert keys' tracks from Pro Tools; return keys whose look changed."""
        if self.busy:
            return []
        # A macro just opened a plug-in menu for you to type into: don't touch Pro Tools
        # until that menu has gone (then update straight away).
        if time.time() < float(getattr(self.runner, "hold_live_until", 0) or 0):
            try:
                still_open = self.runner.menu_on_screen()
            except Exception:  # noqa: BLE001
                still_open = True
            if still_open:
                return []
            self.runner.hold_live_until = 0
            time.sleep(0.3)                   # give Pro Tools a moment to load the plug-in
        changed = self.poll_metric(fresh)
        changed += self.poll_menus(fresh)
        changed += self.poll_palette()
        live_keys = [(k, b) for k, b in enumerate(self.slots) if b and (b.get("live") or b.get("live name"))]
        if not live_keys or self.runner is None:
            return changed
        self.poller()
        cache, picked = {}, {}

        def colour_of(track):
            """A track's colour in Pro Tools (all tracks re-read every 5 seconds)."""
            now = time.time()
            if now - getattr(self, "_colours_at", 0) > 5:
                self._colours_at = now
                try:
                    self._colours = {t["name"]: t["color"] for t in self.runner.sys.ptsl().track_info("all")}
                    self._ptsl_problem(None)
                except Exception as e:  # noqa: BLE001
                    self._ptsl_problem(e)
                    self._colours = getattr(self, "_colours", {})
            return getattr(self, "_colours", {}).get(track)

        def real(name):
            """'selected' -> (first selected track, how many are selected, its colour)."""
            if str(name).lower() != "selected":
                return str(name), 1, colour_of(str(name))
            if "sel" not in picked:
                try:
                    info = self.runner.sys.ptsl().track_info("selected")
                    self._ptsl_problem(None)
                except Exception as e:  # noqa: BLE001 - Pro Tools closed
                    self._ptsl_problem(e)
                    info = []
                picked["sel"] = (info[0]["name"] if info else None, len(info), info[0]["color"] if info else None)
            return picked["sel"]
        for k, b in live_keys:
            if b.get("live name"):
                info = real(b["live name"])
                if self.live.get((self.page, k)) != info:
                    self.live[(self.page, k)] = info
                    changed.append(k)
                continue
            track, _n, tcol = real(b.get("live track", "(PRINT)"))
            if track is None:
                info = None
                if self.live.get((self.page, k)) != info:
                    self.live[(self.page, k)] = info
                    changed.append(k)
                continue
            if track not in cache:
                try:
                    cache[track] = self._poller.read_inserts(track)
                except Exception:  # noqa: BLE001 - Pro Tools closed, track hidden...
                    cache[track] = None
            slots = cache[track]
            letter = SLOT_LETTERS[int(b["live"]) - 1]
            info = slots.get(letter) if slots else None
            # Window open and its Bypass button couldn't be read: keep the state from before.
            if info and info[1] == "open":
                prev = self.live.get((self.page, k))
                if prev and prev[0] == info[0] and prev[1] in ("bypassed", "inactive", "open bypassed"):
                    info = (info[0], "open " + prev[1].replace("open ", ""))
            if info is not None:
                info = (info[0], info[1], tcol)
                self._saw_plugin(info[0])
            if self.live.get((self.page, k)) != info:
                self.live[(self.page, k)] = info
                changed.append(k)
        return changed

    MENU_EVERY = 2.5             # seconds between reads of the 'lit menu' keys' ticks

    def poll_menus(self, fresh=False):
        """Re-read the ticks for this page's 'lit menu' keys; return keys whose look changed.
        Light: each menu item is found once and then re-checked with a single request, menus are
        never opened, and a reading only overrides what CHP believes when the reading itself changed
        (Pro Tools can leave an old tick in a closed menu for a while after a key changed it)."""
        from .macros import Runner
        keys = [(k, b) for k, b in enumerate(self.slots) if b and b.get("lit menu")]
        if not keys or self.runner is None:
            return []
        now = time.time()
        if not fresh and now - getattr(self, "_menus_at", 0) < self.MENU_EVERY:
            return []
        self._menus_at = now
        self.poller()
        before = {k: self._lit(b) for k, b in keys}
        paths = {Runner.menu_key(p): p for _, b in keys for p in lit_paths(b)}   # each item read once
        for key, path in paths.items():
            try:
                item = self._menu_items.get(key)
                if item is None:
                    item, _ = self._poller._menu_item(path, open_menus=False)
                    if item is None:
                        continue
                    self._menu_items[key] = item
                ticked = bool(item.attr("AXMenuItemMarkChar"))
            except Exception:  # noqa: BLE001 - Pro Tools closed or its menus changed: look again next time
                self._menu_items.pop(key, None)
                continue
            if key not in self._menu_read or self._menu_read[key] != ticked or key not in self.menu_lit:
                self.menu_lit[key] = ticked
            self._menu_read[key] = ticked
        return [k for k, b in keys if self._lit(b) != before[k]]

    def _lit(self, button) -> bool | None:
        """Is this 'lit menu' key lit? All its menu items must be ticked (None if not known yet)."""
        from .macros import Runner
        states = [self.menu_lit.get(Runner.menu_key(p)) for p in lit_paths(button)]
        if not states or any(s is None for s in states):
            return None
        return all(states)

    def poll_palette(self):
        """Read Pro Tools' track colours once per run (and remember them) for 'palette color' keys."""
        keys = [k for k, b in enumerate(self.slots) if b and b.get("palette color") is not None]
        if not keys or self.runner is None or getattr(self, "_palette_read", False):
            return []
        if time.time() - getattr(self, "_palette_tried", 0) < 20:
            return []
        self._palette_tried = time.time()
        try:
            pal = self.runner.sys.ptsl().palette()
        except Exception:  # noqa: BLE001 - Pro Tools closed: try again later
            return []
        if not pal:
            return []
        from . import settings
        hexes = ["#%02x%02x%02x" % tuple(c) for c in pal]
        self._palette_read = True
        if hexes == settings.get(self.base, "track palette"):
            return []
        settings.put(self.base, "track palette", hexes)
        return keys

    def note_menu_changes(self, changes):
        """After a macro: record the ticks its menu steps changed, so 'lit menu' keys follow at once.
        Items in a '... Mode' submenu are pick-one within their group: Pro Tools' Solo Mode menu has
        two groups split by a separator (SIP / AFL / PFL and Latch / Momentary / X-OR), so choosing
        X-OR unticks Latch but leaves AFL alone. If the groups can't be read, other items in that
        submenu are forgotten (re-read from Pro Tools) rather than guessed."""
        import fnmatch
        for key, state in changes or []:
            parent, _, leaf = key.rpartition(" > ")
            if parent.endswith("mode"):
                group = self._menu_group(parent, leaf)
                for other in [o for o in self.menu_lit if o.startswith(parent + " > ") and o != key]:
                    other_leaf = other.rpartition(" > ")[2]
                    if group is None:
                        self.menu_lit.pop(other, None)
                    elif any(fnmatch.fnmatchcase(t, other_leaf) for t in group):
                        self.menu_lit[other] = False
                self.menu_lit[key] = True
            else:
                self.menu_lit[key] = (not self.menu_lit.get(key, False)) if state is None else bool(state)

    def _menu_group(self, parent: str, leaf: str) -> list[str] | None:
        """Titles (lowercase) of the items in leaf's group of a menu-bar submenu, split at its
        separators; None if the submenu can't be read without opening it. Read once per submenu."""
        import fnmatch
        from . import elements as E
        cache = self.__dict__.setdefault("_menu_groups", {})
        if parent not in cache:
            groups = None
            try:
                self.poller()
                current = self._poller.app().attr("AXMenuBar")
                for part in parent.split(" > "):
                    item = next((c for c in E.children(current)
                                 if fnmatch.fnmatchcase(E.norm(c.attr("AXTitle") or "").lower(), part)), None)
                    current = next((c for c in E.children(item) if c.attr("AXRole") == "AXMenu"), None) if item else None
                    if current is None:
                        break
                kids = E.children(current) if current is not None else []
                if kids:
                    groups, cur = [], []
                    for c in kids:
                        title = E.norm(c.attr("AXTitle") or "").lower()
                        if title:
                            cur.append(title)
                        elif cur:                     # a separator ends a group
                            groups.append(cur)
                            cur = []
                    if cur:
                        groups.append(cur)
                    self.log(f"menu groups in '{parent}': " + " | ".join(", ".join(g) for g in groups))
            except Exception:  # noqa: BLE001 - Pro Tools closed: don't guess
                groups = None
            if groups is None:
                return None
            cache[parent] = groups
        return next((g for g in cache[parent] if any(fnmatch.fnmatchcase(t, leaf) for t in g)), None)

    # After a key press, leave Pro Tools alone this long before reading the live keys, so it can
    # finish what the key asked for (moving the selection, opening a window...) first.
    # Quick repeated presses get one read, after the last one.
    QUIET_AFTER_PRESS = 0.5
    SLOW_READ = 0.3              # log live reads slower than this (seconds)
    _quiet_until = 0.0
    _poke = False

    def _after_press(self):
        self._quiet_until = time.time() + self.QUIET_AFTER_PRESS
        self._poke = True

    def _live_loop(self):
        next_at = 0.0
        while not self._stop.is_set():
            time.sleep(0.1)
            now = time.time()
            if now < self._quiet_until or self.busy or not self.jobs.empty():
                continue
            fresh = self._poke
            if not fresh and now < next_at:
                continue
            self._poke = False
            waiting = now < float(getattr(self.runner, "hold_live_until", 0) or 0)
            try:
                page = self.page
                t0 = time.time()
                changed = self.poll_live(fresh=fresh)
                took = time.time() - t0
                if took > self.SLOW_READ and time.time() - getattr(self, "_slow_said", 0) > 30:
                    self._slow_said = time.time()
                    self.log(f"live keys: reading Pro Tools took {took:.1f}s (page '{page}')")
                for k in changed:
                    if self.page == page and self.jobs.empty() and not self.busy:
                        self.draw(k)
            except Exception as e:  # noqa: BLE001
                self.log(f"✗ live keys: {e}")
            next_at = time.time() + (0.4 if waiting else 1.0)

    def _flash(self, page, key, state):
        """Show ok/error on the key, then back to normal, without holding up the next press."""
        token = object()
        self._flashes = getattr(self, "_flashes", {})
        self._flashes[(page, key)] = token
        self.draw(key, state)

        def back():
            if self.page == page and self._flashes.get((page, key)) is token:
                self.draw(key, "idle")
        t = threading.Timer(0.4 if state == "ok" else 2.0, back)
        t.daemon = True
        t.start()

    def _worker(self):
        while not self._stop.is_set():
            try:
                page, key, btn = self.jobs.get(timeout=0.5)
            except queue.Empty:
                continue
            same = lambda: self.page == page  # noqa: E731
            if same():
                getattr(self, "_flashes", {}).pop((page, key), None)    # cancel an earlier flash
                self.draw(key, "running")
            from . import results
            try:
                name = self.runner.lib.get(btn["macro"])["name"]
            except Exception:  # noqa: BLE001
                name = btn["macro"]
            self.busy = True           # the live keys don't read Pro Tools mid-macro
            self.runner.believed = self.menu_lit
            self.runner.menu_changes = []
            try:
                self.runner.run(btn["macro"])
                state = "ok"
                results.record_run(self.base, name, True)
            except Exception as e:  # noqa: BLE001 - show any failure on the key and in the log
                self.log(f"✗ {e}")
                state = "error"
                results.record_run(self.base, name, False, str(e))
            self.busy = False
            if self.runner.menu_changes:
                self.note_menu_changes(self.runner.menu_changes)
                if same():
                    self.draw()
            self._after_press()        # the live keys catch up once Pro Tools has settled
            if same():
                self._flash(page, key, state)

    def _watch(self):
        while not self._stop.is_set():
            time.sleep(1)
            try:
                m = self.cfg_path.stat().st_mtime
                if m != self._mtime:
                    self._mtime = m
                    self.cfg = load_config(self.cfg_path)
                    if self.page not in self.cfg["pages"]:
                        self.page, self.history = self.cfg["home"], []
                    self.draw()
                    self.log("↻ deck.yaml reloaded")
            except Exception as e:  # noqa: BLE001
                self.log(f"✗ deck.yaml: {e}")

    # ----- connection: keeps itself connected -----
    BLOCKERS = {"SoundFlow": "SoundFlow", "sf-": "SoundFlow", "Stream Deck": "Elgato's Stream Deck app",
                "StreamDeck": "Elgato's Stream Deck app"}

    def blockers(self) -> list[str]:
        """Other programs running that grab the Stream Deck (SoundFlow, Elgato's app)."""
        import subprocess
        try:
            out = subprocess.run(["ps", "-axo", "comm"], capture_output=True, text=True, timeout=5).stdout
        except Exception:  # noqa: BLE001
            return []
        found = []
        for line in out.splitlines():
            name = line.strip().rsplit("/", 1)[-1]
            for pat, label in self.BLOCKERS.items():
                if name.startswith(pat) and label not in found and "ptdeck" not in name.lower():
                    found.append(label)
        return found

    def connect(self) -> bool:
        """Find and open the Stream Deck. False if it isn't there (or another program has it)."""
        from StreamDeck.DeviceManager import DeviceManager
        try:
            decks = [d for d in DeviceManager().enumerate() if d.is_visual()]
            if not decks:
                return False
            deck = decks[0]
            deck.open()
            deck.reset()
            deck.set_brightness(int(self.cfg.get("brightness", 70)))
            deck.set_key_callback(lambda d, key, down: down and self._safe_press(key))
        except Exception as e:  # noqa: BLE001 - busy, unplugged half-way, permissions...
            self._last_error = str(e)
            return False
        self.deck = deck
        self.status = f"{deck.deck_type()} connected"
        self.log(f"Connected to {deck.deck_type()} ({deck.key_count()} keys)")
        self.draw()
        return True

    def _lost(self, why=None):
        """The deck stopped answering: drop it; the main loop reconnects."""
        deck, self.deck = self.deck, None
        if deck is None:
            return
        self.log(f"Lost the Stream Deck{f' ({why})' if why else ''}. Reconnecting...")
        try:
            deck.close()
        except Exception:  # noqa: BLE001
            pass

    def _still_connected(self) -> bool:
        try:
            return bool(self.deck and self.deck.connected())
        except Exception:  # noqa: BLE001
            return False

    def run_forever(self):
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._watch, daemon=True).start()
        threading.Thread(target=self._live_loop, daemon=True).start()
        waiting_since, told = None, ""
        try:
            while True:
                if self.deck is None:
                    if self.connect():
                        waiting_since, told = None, ""
                    else:
                        waiting_since = waiting_since or time.time()
                        who = self.blockers()
                        msg = (f"Waiting for the Stream Deck: {' and '.join(who)} "
                               f"{'is' if len(who) == 1 else 'are'} running and may be using it. Quit "
                               f"{'it' if len(who) == 1 else 'them'} (check the menu bar too) and PT Deck "
                               "will connect by itself." if who else
                               "Waiting for the Stream Deck (is it plugged in?). PT Deck will connect "
                               "as soon as it appears.")
                        self.status = ("Waiting: " + " and ".join(who) + (" is" if len(who) == 1 else " are")
                                       + " using the Stream Deck") if who else "Waiting for the Stream Deck"
                        if msg != told:
                            self.log(msg)
                            told = msg
                        time.sleep(3)
                        continue
                time.sleep(2)
                if not self._still_connected():
                    self._lost("unplugged or taken by another program")
                    continue
                tick = getattr(self, "_tick", 0) + 1
                self._tick = tick
                if tick % 5 == 0:          # every ~10s: is something else drawing on the deck?
                    who = self.blockers()
                    before = getattr(self, "_blocking", [])
                    if who and who != before:
                        self.log(f"Heads up: {' and '.join(who)} {'is' if len(who) == 1 else 'are'} running and "
                                 "can draw over PT Deck. Quit it (check the menu bar) if the keys look wrong.")
                    if before and not who:
                        self.log("Other Stream Deck programs have quit; redrawing.")
                        try:
                            self.deck.reset()
                        except Exception:  # noqa: BLE001
                            pass
                        self.draw()
                    self._blocking = who
        except KeyboardInterrupt:
            pass
        finally:
            self._stop.set()
            if self.deck:
                try:
                    with self.deck:
                        self.deck.reset()
                        self.deck.close()
                except Exception:  # noqa: BLE001
                    pass

    def _safe_press(self, key):
        try:
            self.pressed(key)
        except Exception as e:  # noqa: BLE001
            self.log(f"✗ {e}")
