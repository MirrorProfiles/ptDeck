"""Your installed plug-ins, for the Manager's 'Plug-in buttons' tool.

Reads Pro Tools' plug-in folder, turns file names into the names Pro Tools shows (as near as
can be guessed: you can correct a name before making its button), and spots which plug-ins
already have an 'insert plugin' macro and a key on the deck.
"""
from __future__ import annotations

import re
from pathlib import Path

FOLDER = Path("/Library/Application Support/Avid/Audio/Plug-Ins")
WAVES = Path("/Applications/Waves")      # Waves keeps the real list here ('Plug-Ins V15' etc.)
SKIP = re.compile(r"(?i)^waveshell")      # Waves shells hold many plug-ins: they can't be listed

# File-name prefix -> (how the name starts in Pro Tools, manufacturer menu in Pro Tools)
VENDORS = [
    (r"^iZ", "", "iZotope"),
    (r"^uaudio_", "UADx ", "Universal Audio (UADx)"),
    (r"^FabFilter ", "FabFilter ", "FabFilter"),
    (r"^bx_", "bx_", "Plugin Alliance"),
    (r"^SSL ", "SSL ", "Solid State Logic"),
    (r"^Valhalla", "Valhalla", "Valhalla DSP, LLC"),
    (r"^TemeculaDSP", "", "Temecula DSP"),
    (r"^Unfiltered Audio ", "Unfiltered Audio ", "Unfiltered Audio"),
    (r"^Archetype ", "Archetype ", "Neural DSP"),
    (r"^STL ", "STL ", "STL Tones"),
    (r"^Oxford ", "Oxford ", "Sonnox"),
    (r"^elysia ", "elysia ", "Plugin Alliance"),
    (r"^Lindell ", "Lindell ", "Plugin Alliance"),
    (r"^AIR", "AIR ", "AIR"),
    (r"^NA ", "NA ", "Nembrini Audio"),
    (r"^TDR ", "TDR ", "Tokyo Dawn Labs"),
    (r"^Tube-Tech ", "Tube-Tech ", "Softube"),
]
# Bundle-identifier word (com.<word>.…) or scanner vendor -> (name on keys, colour). Anyone else
# gets their domain word and a colour picked from its letters, so one maker's plug-ins still match.
VENDOR_LOOK = {
    "fabfilter": ("FabFilter", "#c0392b"), "uaudio": ("UA", "#2e86c1"), "izotope": ("iZotope", "#16a085"),
    "wavesaudio": ("Waves", "#2980b9"), "waves": ("Waves", "#2980b9"),
    "plugin-alliance": ("Plugin Alliance", "#e67e22"), "pluginalliance": ("Plugin Alliance", "#e67e22"),
    "lindellplugins": ("Lindell", "#e67e22"), "lindellaudio": ("Lindell", "#e67e22"),
    "softube": ("Softube", "#a0763b"), "ssl": ("SSL", "#5d6d7e"), "solid state logic": ("SSL", "#5d6d7e"),
    "ikmultimedia": ("IK Multimedia", "#d35400"), "neuraldsp": ("Neural DSP", "#7f8c8d"),
    "native-instruments": ("Native Instruments", "#2c3e50"), "avid": ("Avid", "#6c3483"),
    "wizoo": ("AIR", "#1f77b4"), "air": ("AIR", "#1f77b4"), "sonnox": ("Sonnox", "#1abc9c"),
    "valhalladsp": ("Valhalla", "#27ae60"), "stltones": ("STL Tones", "#b03a2e"),
    "unfilteredaudio": ("Unfiltered Audio", "#9b59b6"), "nembriniaudio": ("Nembrini", "#c0631b"),
    "temeculadsp": ("Temecula DSP", "#34495e"), "xlnaudio": ("XLN Audio", "#e74c3c"),
    "tokyodawnlabs": ("TDR", "#148f77"), "u-he": ("u-he", "#7d3c98"), "klanghelm": ("Klanghelm", "#5b2c6f"),
    "baby audio": ("Baby Audio", "#f39c12"), "korneffaudio": ("Korneff", "#784212"),
    "threebodytech": ("Three-Body", "#8e44ad"), "synchroarts": ("Synchro Arts", "#117a65"),
    "stevenslate": ("Slate", "#922b21"), "celemony": ("Celemony", "#1f618d"), "soundtoys": ("Soundtoys", "#d4ac0d"),
    "eventide": ("Eventide", "#2e4053"), "antares": ("Antares", "#1b4f72"), "toontrack": ("Toontrack", "#7b241c"),
    "arturia": ("Arturia", "#2874a6"), "adptr": ("ADPTR", "#6e2c00"), "mhlabs": ("Metric Halo", "#145a32"),
    "dmgaudio": ("DMG Audio", "#4a235a"), "liquidsonics": ("LiquidSonics", "#1a5276"),
    "klevgrand": ("Klevgrand", "#7e5109"), "toguaudioline": ("TAL", "#633974"),
    "universal audio (uadx)": ("UA", "#2e86c1"), "tube-tech": ("Softube", "#a0763b"),
}
VENDOR_PREFIXES = ("UADx ", "UAD ", "FabFilter ", "bx_console ", "bx_", "iZotope ", "Waves ", "Softube ", "Valhalla",
                   "Unfiltered Audio ", "STL ", "TDR ", "NA ", "Oxford ", "Lindell ", "Tube-Tech ")
GENERIC_TAIL = {"compressor", "equalizer", "eq", "limiter", "preamp", "and", "plug-in", "plugin", "processor"}

UA_UPPER = {"ua", "ssl", "la", "api", "emt", "eq", "eqp", "meq", "hlf", "atr", "vt", "dbx", "vog", "b3", "a800"}


def split_words(text: str) -> list[str]:
    """'RX11De-click' -> ['RX', '11', 'De-click']; 'MouthDe-click' -> ['Mouth', 'De-click']."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Za-z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([A-Za-z]{2,})", r"\1 \2", text)
    return text.split()


def display_name(file_name: str) -> tuple[str, str]:
    """(name as Pro Tools probably shows it, manufacturer menu guess) from a .aaxplugin name."""
    stem = re.sub(r"\.aaxplugin$", "", file_name)
    for pat, lead, vendor in VENDORS:
        if re.match(pat, stem):
            if pat == r"^iZ":
                core = re.sub(r"AAXHook$", "", stem[2:])
                return " ".join(split_words(core)), vendor
            if pat == r"^uaudio_":
                words = stem[len("uaudio_"):].split("_")
                return lead + " ".join(w.upper() if w in UA_UPPER else w.capitalize() for w in words), vendor
            return stem.replace("_", " ") if not stem.startswith("bx_") else stem, vendor
    return stem.replace("_", " "), ""


VENDOR_WORDS = {"ua", "uadx", "uaudio", "iz", "izotope", "plugin", "plug", "in", "v6", "aax"}


def tokens(text: str) -> set[str]:
    words = re.split(r"[^a-z0-9]+", " ".join(split_words(str(text))).lower())
    return {w for w in words if w and w not in VENDOR_WORDS}


def same_plugin(a: str, b: str) -> bool:
    """True if two names look like the same plug-in (all words of the shorter in the longer)."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if small <= big:
        return True
    # Same model number (e.g. 1073, 1176): 'UADx Neve 1073' = 'UADx 1073 Preamp and EQ'
    return any(w.isdigit() and len(w) >= 3 for w in ta & tb)


_bundle_words: dict | None = None     # lower plug-in name -> (bundle-id word, scanner vendor)


def _bundles(folder: Path | None = None) -> dict:
    """Each installed plug-in's maker, read once from the bundles' Info.plist identifiers
    (com.fabfilter.Pro-Q.AAX.4 -> 'fabfilter') and the scanner's own guess."""
    global _bundle_words
    if _bundle_words is None or folder is not None:
        import plistlib
        out = {}
        base = Path(folder or FOLDER)
        for p in scan(base):
            word = ""
            if p["file"].endswith(".aaxplugin"):
                for plist in (base / p["file"] / "Contents" / "Info.plist",
                              *base.glob(f"*/{p['file']}/Contents/Info.plist")):
                    try:
                        ident = str(plistlib.loads(plist.read_bytes()).get("CFBundleIdentifier", ""))
                    except (OSError, ValueError, plistlib.InvalidFileException):
                        continue
                    parts = ident.lower().split(".")
                    if len(parts) >= 2:
                        word = parts[1]
                    break
            out[p["name"].lower()] = (word, p.get("vendor", ""))
        if folder is not None:
            return out
        _bundle_words = out
    return _bundle_words


def vendor_of(name: str, folder: Path | None = None):
    """(name on keys, colour) of the maker of a plug-in, as Pro Tools names it; None if unknown."""
    import colorsys
    import hashlib
    if not name:
        return None
    table = _bundles(folder)
    hit = table.get(name.lower())
    if hit is None:                                   # 'Valhalla VintageVerb' = 'ValhallaVintageVerb'
        squashed = re.sub(r"[^a-z0-9]+", "", name.lower()).replace("renaissance", "ren")   # Waves' RenAxx
        hit = next((v for n, v in table.items()
                    if re.sub(r"[^a-z0-9]+", "", n).replace("renaissance", "ren") == squashed), None)
    if hit is None:
        hit = next((v for n, v in table.items() if same_plugin(n, name)), None)
    if hit is None:
        return None
    word, vendor = hit
    for key in (word, vendor.lower()):
        if key and key in VENDOR_LOOK:
            return VENDOR_LOOK[key]
    label = vendor or word.replace("-", " ").title()
    if not label or label in ("Aaxplugin", "Co", "Insert"):
        return None
    hue = int(hashlib.md5(label.lower().encode()).hexdigest(), 16) % 360 / 360
    r, g, b = colorsys.hls_to_rgb(hue, 0.42, 0.6)
    return label, "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))


def short_name(name: str, vendor: str = "") -> str:
    """The name as a key shows it: no maker's prefix ('UADx 1176 Rev A Compressor' -> '1176 Rev A',
    'FabFilter Pro-Q 4' -> 'Pro-Q 4'), and no long generic tail once it runs past two words."""
    out = str(name).strip()
    for pre in VENDOR_PREFIXES + ((vendor + " ",) if len(vendor) > 3 else ()):   # 'SSL …' stays
        if out.lower().startswith(pre.lower()) and len(out) > len(pre):
            out = out[len(pre):].strip()
            break
    words = out.split()
    while len(words) > 2 and words[-1].lower() in GENERIC_TAIL:
        words.pop()
    return " ".join(words) or str(name)


def scan(folder: Path | None = None) -> list[dict]:
    """Every .aaxplugin in the folder (and one level of vendor sub-folders), plus Waves."""
    folder = Path(folder or FOLDER)
    found = []
    if not folder.is_dir():
        return found
    for p in sorted(folder.rglob("*.aaxplugin")):
        if len(p.relative_to(folder).parts) > 2 or SKIP.match(p.stem):
            continue
        name, vendor = display_name(p.name)
        found.append({"file": p.name, "name": name, "vendor": vendor})
    found += scan_waves()
    return found


def scan_waves(folder: Path | None = None) -> list[dict]:
    """Waves plug-ins all hide inside one 'WaveShell' in Pro Tools' folder; the real list is the
    .bundle files in Waves' own 'Plug-Ins V..' folder (the newest version you have)."""
    folder = Path(folder or WAVES)
    if not folder.is_dir():
        return []
    versions = sorted((d for d in folder.glob("Plug-Ins V*") if d.is_dir()),
                      key=lambda d: [int(x) for x in re.findall(r"\d+", d.name)] or [0])
    if not versions:
        return []
    out, seen = [], set()
    for d in reversed(versions):                     # newest first; older-only plug-ins still count
        for b in sorted(d.glob("*.bundle")):
            if b.stem.lower() in seen or re.match(r"(?i)waves(shell|lib)|^lib", b.stem):
                continue
            seen.add(b.stem.lower())
            out.append({"file": f"{b.stem} (Waves)", "name": b.stem, "vendor": "Waves"})
    return out


def with_buttons(plugins: list[dict], macros: list[dict], on_deck: set[str]) -> list[dict]:
    """Mark each plug-in with the macros that already insert it, and whether one is on the deck.
    macros: [{'name', 'inserts': [plug-in names]}]."""
    for p in plugins:
        hits = [m["name"] for m in macros if any(same_plugin(p["name"], i) or same_plugin(p["file"], i)
                                                 for i in m["inserts"])]
        p["macros"] = hits
        p["on_deck"] = any(h.lower() in on_deck for h in hits)
    return plugins


def macro_yaml(name: str, plugin: str, category: str, slot) -> str:
    lines = ["# Made with PT Deck's Plug-in buttons tool",
             f"name: {_q(name)}", "steps:", f"- insert plugin: {_q(plugin)}",
             f"  slot: {slot if slot not in (None, '') else 'first free'}"]
    if category:
        lines.append(f"  category: {_q(category)}")
    return "\n".join(lines) + "\n"


def _q(s) -> str:
    import json
    s = str(s)
    return json.dumps(s) if re.search(r"[:#'\"\[\]{}&*!|>%@`]|^\s|\s$", s) else s
