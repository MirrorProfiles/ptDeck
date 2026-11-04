"""PT Deck Manager: a page in your web browser (http://localhost:8765) for seeing
and changing what every Stream Deck key does, checking macros and test-running them.

It only listens on this Mac (127.0.0.1); nothing is reachable from the network.
"""
from __future__ import annotations

import base64
import io
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

from . import deck as D
from . import results
from .macros import Library, MacroError, slug, validate

PORT = 8765
HEADER = """# ─────────────────────────────────────────────────────────────
#  Your Stream Deck layout. Easiest to change with the Manager
#  (Open Manager.command). You can also edit this file by hand:
#  save it and the deck updates within a second.
#
#  Each button can have:
#    label:      text on the key (use \\n for a new line)
#    macro:      name of a macro in the macros folder
#    folder:     name of another page to open (a folder)
#    icon:       picture file in the icons folder (PNG). With no label,
#                the picture fills the whole key.
#    color:      background, e.g. "#204060"
#    text color: label colour (default white)
#    key:        which key (1 = top-left)
#  Folder pages automatically get a "↑" back button on key 1, and
#  folder buttons get a thin outline so they stand out from commands.
# ─────────────────────────────────────────────────────────────

"""
FIELD_ORDER = ["key", "label", "icon", "macro", "folder", "color", "text color", "font size", "outline", "note"]


def backup(path: Path, keep: int = 30):
    """Copy deck.yaml into 'backups' (dated) before it changes; keep the newest few."""
    import shutil
    import time as _t
    path = Path(path)
    if not path.exists():
        return
    folder = path.parent / "backups"
    folder.mkdir(exist_ok=True)
    shutil.copy2(path, folder / f"deck-{_t.strftime('%Y-%m-%d-%H%M%S')}.yaml")
    for old in sorted(folder.glob("deck-*.yaml"))[:-keep]:
        old.unlink(missing_ok=True)


def save_config(path: Path, cfg: dict):
    """Write deck.yaml: settings first, then one tidy line per button."""
    lines = [HEADER.rstrip("\n"), ""]
    for k, v in cfg.items():
        if k != "pages":
            lines.append(yaml.safe_dump({k: v}, allow_unicode=True, sort_keys=False).strip())
    lines += ["", "pages:"]
    for page, items in cfg["pages"].items():
        items = [b for b in (items or []) if isinstance(b, dict)]
        if not items:
            lines.append(f"  {yaml.safe_dump(page, allow_unicode=True).splitlines()[0]}: []")
            continue
        lines.append(f"  {yaml.safe_dump(page, allow_unicode=True).splitlines()[0]}:")
        for b in sorted(items, key=lambda b: int(b.get("key", 99))):
            ordered = {f: b[f] for f in FIELD_ORDER if f in b and b[f] not in (None, "")}
            ordered.update({f: v for f, v in b.items() if f not in ordered and v not in (None, "")})
            lines.append("    - " + yaml.safe_dump(ordered, default_flow_style=True, allow_unicode=True,
                                                    width=10000, sort_keys=False).strip())
        lines.append("")
    backup(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    tmp.replace(path)


class Manager:
    def __init__(self, base: Path, runner_factory=None, log=print, app: Path | None = None):
        from .paths import APP
        self.base = Path(base)                     # your deck folder
        self.app = Path(app) if app else APP       # the PT Deck folder (code, .venv, log)
        self.cfg_path = self.base / "deck.yaml"
        self.lib = Library(self.base / "macros")
        self.runner_factory = runner_factory
        self.log = log
        self.lock = threading.Lock()
        self.runs: dict[str, dict] = {}
        self.deck = None          # the running DeckController (set by 'start'), for Mirror deck

    # ----- data -----
    _cfg_cache = (None, None)
    _png_cache: dict = {}

    def cfg(self):
        """deck.yaml, re-read only when it changes."""
        m = self.cfg_path.stat().st_mtime if self.cfg_path.exists() else None
        if self._cfg_cache[0] != m or m is None:
            self._cfg_cache = (m, D.load_config(self.cfg_path))
            self._png_cache = {}
        import copy
        return copy.deepcopy(self._cfg_cache[1])

    def grid(self, cfg):
        rows, cols, _ = D.MODELS.get(cfg.get("model", "xl"), D.MODELS["xl"])
        return rows, cols

    # ----- plug-in buttons -----
    def plugins(self):
        from . import plugins as P
        from .macros import step_action
        made = []
        for p in self.lib.files():
            try:
                m = self.lib.load(p)
            except MacroError:
                continue
            ins = [str(v) for a, v in (step_action(st) for st in m.get("steps") or []) if a == "insert plugin" and v]
            if ins:
                made.append({"name": str(m["name"]), "file": p.stem, "inserts": ins})
        cfg = self.cfg()
        on_deck = {str(b.get("macro")).lower() for items in cfg["pages"].values() for b in items or []
                   if isinstance(b, dict) and b.get("macro")}
        for m in made:                       # a key may name the macro by its file name
            if m["file"].lower() in on_deck:
                on_deck.add(m["name"].lower())
        found = P.scan()
        from . import settings
        seen = settings.get(self.base, "seen plugins", []) or []
        have = {p["name"].lower() for p in found}
        for n in seen:                       # plug-ins on your tracks, named as Pro Tools shows them
            if n.lower() not in have:
                found.append({"file": "", "name": n, "vendor": ""})
        seen_l = {n.lower() for n in seen}
        out = P.with_buttons(found, made, on_deck)
        for p in out:
            p["seen"] = p["name"].lower() in seen_l
            p["icon"] = D.plugin_icon(self.base, p["name"])
        out.sort(key=lambda p: (not p["seen"], p["name"].lower()))
        return {"folder": str(P.FOLDER), "found": bool(found), "plugins": out}

    def plugin_picture(self, plugin, icon=None, data=None, remove=False, on_buttons=False):
        """Give a plug-in its own picture (shown on the live insert keys): saved as
        icons/plugins/<plug-in name>.png, from one of your pictures or new image data."""
        import shutil
        from PIL import Image
        from . import plugins as P
        plugin = str(plugin).strip()
        if not plugin:
            raise ValueError("Which plug-in?")
        folder = self.base / "icons" / "plugins"
        folder.mkdir(parents=True, exist_ok=True)
        old = D.plugin_icon(self.base, plugin)
        if old:
            (self.base / "icons" / old).unlink(missing_ok=True)
        if remove:
            return {"icon": None}
        safe = re.sub(r'[\\/:*?"<>|]+', " ", plugin).strip() or "plugin"
        dest = folder / f"{safe}.png"
        if icon:
            src = self.base / "icons" / str(icon)
            if not src.resolve().is_relative_to((self.base / "icons").resolve()) or not src.exists():
                raise ValueError(f"no picture called '{icon}'")
            shutil.copyfile(src, dest)
        elif data:
            img = Image.open(io.BytesIO(base64.b64decode(str(data).split(",")[-1]))).convert("RGBA")
            img.thumbnail((288, 288))
            if img.width != img.height:
                side = max(img.size)
                sq = Image.new("RGBA", (side, side), (0, 0, 0, 255))
                sq.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
                img = sq
            img.save(dest)
        else:
            raise ValueError("Choose a picture")
        rel = f"plugins/{dest.name}"
        changed = 0
        if on_buttons:                       # the 'Assign ...' keys for this plug-in get it too
            makes = set()
            from .macros import step_action
            for f in self.lib.files():
                try:
                    m = self.lib.load(f)
                except MacroError:
                    continue
                if any(a == "insert plugin" and P.same_plugin(str(v), plugin)
                       for a, v in (step_action(st) for st in m.get("steps") or [])):
                    makes |= {str(m["name"]).lower(), f.stem.lower()}
            with self.lock:
                cfg = self.cfg()
                for items in cfg["pages"].values():
                    for b in items or []:
                        if isinstance(b, dict) and str(b.get("macro", "")).lower() in makes:
                            b["icon"] = rel
                            b.pop("label", None)
                            changed += 1
                if changed:
                    save_config(self.cfg_path, cfg)
        self._png_cache.clear()
        return {"icon": rel, "buttons": changed}

    def plugin_button(self, plugin, category="", slot="first free", page=None, label=None):
        """Make an 'insert this plug-in' macro and put a key for it on the first free key of a page."""
        from . import plugins as P
        plugin = str(plugin).strip()
        if not plugin:
            raise ValueError("Which plug-in?")
        name = f"Assign {plugin}" if str(slot) in ("", "first free") else f"Assign {plugin} to Slot {slot}"
        path = self.base / "macros" / f"{slug(name)}.yaml"
        if not path.exists():
            path.write_text(P.macro_yaml(name, plugin, category, slot), encoding="utf-8")
        key = None
        if page:
            cfg = self.cfg()
            rows, cols = self.grid(cfg)
            if page not in cfg["pages"]:
                raise ValueError(f"no page '{page}'")
            slots = D.layout(cfg, page, rows * cols)
            key = next((i for i, b in enumerate(slots) if (b is None or b.get("banner"))
                        and not (i == 0 and page != cfg["home"])), None)
            if key is None:
                raise ValueError(f"'{page}' has no empty keys left")
            self.set_button(page, key, {"label": label or plugin, "macro": name, "glyph": "plug"})
        return {"macro": name, "file": path.name, "key": key}

    def icon_from_url(self, url, name=None):
        """Download a picture from the web (e.g. dragged in from another browser tab) as an icon."""
        import urllib.request
        if not str(url).startswith(("http://", "https://", "data:image/")):
            raise ValueError("That isn't a picture link")
        if str(url).startswith("data:image/"):
            return self.save_icon(name or "pasted", url)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 PT Deck"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read(15_000_000)
        stem = name or Path(urlparse(url).path).stem or "picture"
        return self.save_icon(stem, base64.b64encode(data).decode())

    def macros(self):
        out = []
        for p in self.lib.files():
            try:
                m = self.lib.load(p)
                problems = validate(m, self.lib)
            except MacroError as e:
                m, problems = {"name": p.stem, "steps": []}, [str(e)]
            todo = any("needs converting" in x for x in problems)
            out.append({"name": str(m["name"]), "file": p.name, "steps": len(m.get("steps") or []),
                        "status": "ok" if not problems else ("todo" if todo else "problem"),
                        "problems": problems})
        return sorted(out, key=lambda x: x["name"].lower())

    def state(self):
        cfg = self.cfg()
        rows, cols = self.grid(cfg)
        macros = self.macros()
        known = {m["name"].lower() for m in macros} | {Path(m["file"]).stem.lower() for m in macros}
        status = {}
        for m in macros:
            status[m["name"].lower()] = m["status"]
            status[Path(m["file"]).stem.lower()] = m["status"]
        pages = {}
        for name in cfg["pages"]:
            slots = D.layout(cfg, name, rows * cols)
            out = []
            for b in slots:
                if not b:
                    out.append(None)
                    continue
                b = dict(b)
                if b.get("macro"):
                    key = str(b["macro"]).lower()
                    b["_status"] = status.get(key) or status.get(slug(key)) or (
                        "missing" if key not in known and slug(key) not in known else "ok")
                out.append(b)
            pages[name] = out
        used = {str(b.get("macro")).lower() for items in cfg["pages"].values() for b in items or []
                if isinstance(b, dict) and b.get("macro")}
        res = results.load(self.base)
        for m in macros:
            m["on_deck"] = m["name"].lower() in used or Path(m["file"]).stem.lower() in used
            m["result"] = res.get(m["name"], {})
        icons = [p.name for p in sorted((self.base / "icons").glob("*.png"),
                                        key=lambda p: p.stat().st_mtime, reverse=True)]   # newest first
        return {"rows": rows, "cols": cols, "home": cfg["home"], "pages": pages, "page_order": list(cfg["pages"]),
                "macros": macros, "icons": icons, "runs": self.runs, "log": self.log_tail()}

    def log_tail(self, n=60):
        f = self.app / "ptdeck.log"
        try:
            return f.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
        except OSError:
            return []

    def key_png(self, page, key, size=96):
        cfg = self.cfg()
        rows, cols = self.grid(cfg)
        slots = D.layout(cfg, page, rows * cols, self.base)
        b = slots[key] if 0 <= key < len(slots) else None
        cache_key = json.dumps(b, sort_keys=True, default=str)
        if b and b.get("icon"):
            ip = D.icon_path(self.base, b["icon"])
            cache_key += str(ip.stat().st_mtime if ip.exists() else 0)
        if cache_key not in self._png_cache:
            buf = io.BytesIO()
            D.render(b, size, self.base).save(buf, "PNG")
            self._png_cache[cache_key] = buf.getvalue()
        return self._png_cache[cache_key]

    # ----- changes -----
    def set_button(self, page, key, button):
        """key is 0-based. button=None clears the key."""
        with self.lock:
            cfg = self.cfg()
            if page not in cfg["pages"]:
                raise ValueError(f"no page '{page}'")
            if key == 0 and page != cfg["home"] and cfg.get("back button", True):
                raise ValueError("Key 1 on a folder page is the Back button")
            rows, cols = self.grid(cfg)
            # Pin every button to its current key so nothing shifts around.
            items = []
            for i, b in enumerate(D.layout(cfg, page, rows * cols)):
                if b and not b.get("back") and not b.get("banner") and i != key:
                    b = {k: v for k, v in b.items() if not k.startswith("_")}
                    b["key"] = i + 1
                    items.append(b)
            if button:
                clean = {k: v for k, v in button.items() if k in D.BUTTON_FIELDS and v not in (None, "")}
                if "macro" in clean and "folder" in clean:
                    raise ValueError("A key can run a macro or open a folder, not both")
                if "folder" in clean and clean["folder"] not in cfg["pages"]:
                    cfg["pages"][clean["folder"]] = []
                clean["key"] = key + 1
                items.append(clean)
            cfg["pages"][page] = items
            save_config(self.cfg_path, cfg)

    def move_button(self, page, src, dst):
        with self.lock:
            cfg = self.cfg()
            rows, cols = self.grid(cfg)
            slots = D.layout(cfg, page, rows * cols)
            if page != cfg["home"] and 0 in (src, dst):
                raise ValueError("Key 1 on a folder page is the Back button")
            slots[src], slots[dst] = slots[dst], slots[src]
            items = []
            for i, b in enumerate(slots):
                if b and not b.get("back") and not b.get("banner"):
                    b = {k: v for k, v in b.items() if not k.startswith("_")}
                    b["key"] = i + 1
                    items.append(b)
            cfg["pages"][page] = items
            save_config(self.cfg_path, cfg)

    def move_between(self, src_page, src, dst_page, dst):
        """Move a key to another page (swapping with whatever is at the destination)."""
        if src_page == dst_page:
            return self.move_button(src_page, src, dst)
        with self.lock:
            cfg = self.cfg()
            rows, cols = self.grid(cfg)
            for pg, k in ((src_page, src), (dst_page, dst)):
                if pg not in cfg["pages"]:
                    raise ValueError(f"no page '{pg}'")
                if k == 0 and pg != cfg["home"] and cfg.get("back button", True):
                    raise ValueError("Key 1 on a folder page is the Back button")
            a = D.layout(cfg, src_page, rows * cols)
            b = D.layout(cfg, dst_page, rows * cols)
            moving = a[src] if a[src] and not a[src].get("banner") else None
            if moving is None:
                raise ValueError("There's nothing on that key to move")
            if moving.get("folder") == dst_page:
                raise ValueError("A folder can't go inside itself")
            other = b[dst] if b[dst] and not b[dst].get("banner") and not b[dst].get("back") else None
            a[src], b[dst] = other, moving

            def pinned(slots):
                out = []
                for i, x in enumerate(slots):
                    if x and not x.get("back") and not x.get("banner"):
                        x = {k: v for k, v in x.items() if not k.startswith("_")}
                        x["key"] = i + 1
                        out.append(x)
                return out
            cfg["pages"][src_page] = pinned(a)
            cfg["pages"][dst_page] = pinned(b)
            save_config(self.cfg_path, cfg)

    def page_action(self, action, name, new=None):
        with self.lock:
            cfg = self.cfg()
            if action == "add":
                if not name or name in cfg["pages"]:
                    raise ValueError("Pick a new, unused page name")
                cfg["pages"][name] = []
            elif action == "rename":
                if name not in cfg["pages"] or not new or new in cfg["pages"]:
                    raise ValueError("Pick a new, unused page name")
                cfg["pages"] = {(new if k == name else k): v for k, v in cfg["pages"].items()}
                for items in cfg["pages"].values():
                    for b in items or []:
                        if isinstance(b, dict) and b.get("folder") == name:
                            b["folder"] = new
                if cfg["home"] == name:
                    cfg["home"] = new
            elif action == "delete":
                if name == cfg["home"]:
                    raise ValueError("The Home page can't be deleted")
                cfg["pages"].pop(name, None)
                for page, items in cfg["pages"].items():
                    cfg["pages"][page] = [b for b in items or [] if not (isinstance(b, dict) and b.get("folder") == name)]
            save_config(self.cfg_path, cfg)

    def macro_text(self, name):
        m = self.lib.get(name)
        return m["_file"].name, m["_file"].read_text(encoding="utf-8")

    def save_macro(self, file, text):
        if not re.match(r"^[\w.\- ]+\.ya?ml$", file):
            raise ValueError("bad file name")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            raise ValueError(f"Formatting mistake: {e}") from None
        if not isinstance(data, (dict, list)):
            raise ValueError("A macro needs 'name:' and 'steps:'")
        from .macros import REBUILT_MARK, EDITED_MARK
        if text.startswith(REBUILT_MARK):        # your edit of a rebuilt macro: now it's yours
            text = EDITED_MARK + text[len(REBUILT_MARK):]
        (self.base / "macros" / file).write_text(text, encoding="utf-8")
        m = self.lib.load(self.base / "macros" / file)
        return validate(m, self.lib)

    def import_soundflow(self, name, js, replace=False):
        """Convert a pasted SoundFlow script and save it, like the import window does."""
        from .soundflow import convert, to_yaml
        name = str(name or "").strip()
        if not name:
            raise ValueError("Give the macro a name (use the button's macro name to link it)")
        if "sf." not in js:
            raise ValueError("That doesn't look like a SoundFlow script")
        out = self.base / "macros" / f"{slug(name)}.yaml"
        if out.exists() and not replace:
            raise ValueError(f"A macro called '{name}' already exists. Tick 'Replace' to overwrite it.")
        macro, warnings = convert(js, name)
        out.write_text(to_yaml(macro), encoding="utf-8")
        (self.base / "soundflow-scripts").mkdir(exist_ok=True)
        (self.base / "soundflow-scripts" / f"{slug(name)}.js").write_text(js, encoding="utf-8")
        todos = sum(1 for st in macro["steps"] if isinstance(st, dict) and "todo" in st)
        return {"file": out.name, "steps": len(macro["steps"]), "todos": todos,
                "warnings": [w for w in warnings if "Calls another SoundFlow command" not in w],
                "calls": [st["run macro"] for st in macro["steps"] if isinstance(st, dict) and "run macro" in st]}

    # Files from a download that belong to PT Deck itself. Everything else in your folder
    # (macros, soundflow-scripts, deck.yaml, test results, the log, .venv) is never touched.
    # Downloads in the old flat layout and the my-deck layout both work.
    INSTALL_DIRS = ("ptdeck/", "rebuilt/", "additions/", "icons/")
    APP_DIRS = ("ptdeck/", "assets/", "tools/")
    DECK_DIRS = ("rebuilt/", "additions/", "icons/")

    def _install_dest(self, rel):
        """Where a file from a download goes, or None to skip it."""
        if rel.startswith("my-deck/"):
            rel = rel[len("my-deck/"):]
            return self.base / rel if rel.startswith(self.DECK_DIRS) else None
        if rel.startswith("icons/fonts/"):                        # old layout: fonts are the app's
            return self.app / "assets" / "fonts" / rel[len("icons/fonts/"):]
        if rel.startswith(self.APP_DIRS) or rel in self.INSTALL_FILES:
            return self.app / rel
        if rel.startswith(self.DECK_DIRS):
            return self.base / rel
        return None
    INSTALL_FILES = ("README.md", "requirements.txt", "Install.command", "Start PT Deck.command",
                     "Open Manager.command", "Import From SoundFlow.command", "Pick Element.command",
                     "Check Macros.command", "Update Macros.command")

    def install_update(self, data_b64):
        """Install a PT Deck download (.zip) over this copy, keeping your own files."""
        import subprocess
        import zipfile
        raw = base64.b64decode(data_b64.split(",")[-1])
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile:
            raise ValueError("That isn't a PT Deck download (.zip)") from None
        names = zf.namelist()
        prefix = "ptdeck/" if all(n.startswith("ptdeck/") for n in names) else ""
        if not any(n.startswith(prefix + "ptdeck/__main__.py") for n in names):
            raise ValueError("That zip doesn't contain PT Deck")
        installed = 0
        old_reqs = (self.app / "requirements.txt").read_bytes() if (self.app / "requirements.txt").exists() else b""
        for n in names:
            rel = n[len(prefix):]
            if not rel or rel.endswith("/") or ".." in Path(rel).parts or rel.startswith("/"):
                continue
            dest = self._install_dest(rel)
            if dest is None or "__pycache__" in rel:
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(zf.read(n))
            if rel.endswith(".command"):
                dest.chmod(0o755)
            installed += 1
        reqs = self.app / "requirements.txt"
        if reqs.exists() and reqs.read_bytes() != old_reqs:
            pip = self.app / ".venv" / "bin" / "pip"
            if pip.exists():
                subprocess.run([str(pip), "install", "-q", "-r", str(reqs)])
        added = []
        try:
            from .__main__ import apply_additions, remove_stale_rebuilt_copies
            removed = remove_stale_rebuilt_copies(self.base)
            if removed:
                self.log(f"Tidied {removed} old cop(ies) of rebuilt macros")
            added = apply_additions(base=self.base)
        except Exception as e:  # noqa: BLE001
            self.log(f"✗ adding new pages: {e}")
        try:                                  # keep PT Deck.app's launcher up to date
            if (self.app / "PT Deck.app").exists():
                from .menubar import make_app
                make_app(self.app, log=self.log)
        except Exception as e:  # noqa: BLE001
            self.log(f"(couldn't refresh PT Deck.app: {e})")
        self.log(f"Installed update ({installed} files). Restarting...")
        self.restart_soon()
        return {"files": installed, "pages": added}

    def restart_soon(self):
        """Restart PT Deck (same command as it was started with) so new code takes effect."""
        import os
        import sys

        def go():
            time.sleep(1.0)
            os.chdir(self.base)
            os.execv(sys.executable, [sys.executable, "-m", "ptdeck", *sys.argv[1:]])
        threading.Thread(target=go, daemon=True).start()

    def new_macro(self, name):
        path = self.base / "macros" / f"{slug(name)}.yaml"
        if path.exists():
            raise ValueError(f"{path.name} already exists")
        path.write_text(f"name: {json.dumps(name)}\nsteps:\n- note: add steps here\n", encoding="utf-8")
        return path.name

    def save_icon(self, name, data_b64):
        from PIL import Image
        stem = slug(Path(name).stem) or "picture"
        name, n = stem + ".png", 2
        while (self.base / "icons" / name).exists():       # never overwrite another picture
            name, n = f"{stem}-{n}.png", n + 1
        img = Image.open(io.BytesIO(base64.b64decode(data_b64.split(",")[-1]))).convert("RGBA")
        img.thumbnail((288, 288))
        if img.width != img.height:                          # centre it on a square, don't stretch
            side = max(img.size)
            sq = Image.new("RGBA", (side, side), (0, 0, 0, 255))
            sq.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
            img = sq
        img.save(self.base / "icons" / name)
        return name

    def run_macro(self, name, delay=1.0):
        if self.runner_factory is None:
            raise ValueError("Test runs only work on the Mac running PT Deck")
        self.runs[name] = {"status": "running", "message": "", "at": time.strftime("%H:%M:%S")}

        def go():
            try:
                runner = self.runner_factory()
                runner.sys.activate()          # bring Pro Tools to the front, as when using the deck
                time.sleep(delay)
                runner.run(name)
                self.runs[name] = {"status": "ok", "message": "Finished", "at": time.strftime("%H:%M:%S")}
                results.record_run(self.base, name, True)
            except Exception as e:  # noqa: BLE001
                self.runs[name] = {"status": "error", "message": str(e), "at": time.strftime("%H:%M:%S")}
                results.record_run(self.base, name, False, str(e))
                self.log(f"✗ {e}")
        threading.Thread(target=go, daemon=True).start()


def make_handler(mgr: Manager):
    page_html = (Path(__file__).parent / "manager.html").read_text(encoding="utf-8")

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            data = body if isinstance(body, bytes) else (
                body.encode() if isinstance(body, str) else json.dumps(body).encode())
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            u = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(u.query).items()}
            try:
                if u.path == "/":
                    return self.send(200, page_html, "text/html; charset=utf-8")
                if u.path == "/api/state":
                    return self.send(200, mgr.state())
                if u.path == "/api/key.png":
                    return self.send(200, mgr.key_png(q["page"], int(q["key"])), "image/png")
                if u.path == "/api/icon":
                    name = str(q["name"])
                    sub = "plugins" if name.startswith("plugins/") else ""
                    p = mgr.base / "icons" / sub / Path(name).name
                    return self.send(200, p.read_bytes(), "image/png")
                if u.path == "/api/deck":
                    if mgr.deck is None:
                        return self.send(200, {"running": False})
                    return self.send(200, dict(mgr.deck.mirror(), running=True))
                if u.path == "/api/deck-key.png":
                    if mgr.deck is None:
                        return self.send(404, {"error": "the deck isn't running"})
                    buf = io.BytesIO()
                    mgr.deck.mirror_key(int(q["key"])).save(buf, "PNG")
                    return self.send(200, buf.getvalue(), "image/png")
                if u.path == "/api/plugins":
                    return self.send(200, mgr.plugins())
                if u.path == "/api/macro":
                    f, text = mgr.macro_text(q["name"])
                    return self.send(200, {"file": f, "text": text})
                return self.send(404, {"error": "not found"})
            except Exception as e:  # noqa: BLE001
                return self.send(400, {"error": str(e)})

        def do_POST(self):
            if self.headers.get("Origin") not in (None, f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"):
                return self.send(403, {"error": "forbidden"})
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            try:
                p = urlparse(self.path).path
                if p == "/api/button":
                    mgr.set_button(body["page"], int(body["key"]), body.get("button"))
                elif p == "/api/move":
                    mgr.move_button(body["page"], int(body["src"]), int(body["dst"]))
                elif p == "/api/move-between":
                    mgr.move_between(body["src_page"], int(body["src"]), body["dst_page"], int(body["dst"]))
                elif p == "/api/page":
                    mgr.page_action(body["action"], body.get("name"), body.get("new"))
                elif p == "/api/macro":
                    return self.send(200, {"problems": mgr.save_macro(body["file"], body["text"])})
                elif p == "/api/install":
                    return self.send(200, mgr.install_update(body["data"]))
                elif p == "/api/import":
                    return self.send(200, mgr.import_soundflow(body.get("name"), body.get("js", ""), bool(body.get("replace"))))
                elif p == "/api/macro/new":
                    return self.send(200, {"file": mgr.new_macro(body["name"])})
                elif p == "/api/plugin-button":
                    return self.send(200, mgr.plugin_button(body.get("plugin"), body.get("category", ""),
                                                            body.get("slot", "first free"), body.get("page"),
                                                            body.get("label")))
                elif p == "/api/plugin-picture":
                    return self.send(200, mgr.plugin_picture(body.get("plugin"), body.get("icon"), body.get("data"),
                                                             bool(body.get("remove")), bool(body.get("on_buttons"))))
                elif p == "/api/icon-url":
                    return self.send(200, {"name": mgr.icon_from_url(body["url"], body.get("name"))})
                elif p == "/api/icon":
                    return self.send(200, {"name": mgr.save_icon(body["name"], body["data"])})
                elif p == "/api/verdict":
                    results.set_verdict(mgr.base, body["name"], body.get("verdict"))
                elif p == "/api/run":
                    mgr.run_macro(body["name"])
                else:
                    return self.send(404, {"error": "not found"})
                return self.send(200, {"ok": True})
            except Exception as e:  # noqa: BLE001
                return self.send(400, {"error": str(e)})

    return H


def serve(mgr: Manager, port: int = PORT, background: bool = False):
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(mgr))
    if background:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        return srv
    srv.serve_forever()
