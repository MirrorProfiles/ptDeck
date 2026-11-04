"""Command line: python -m ptdeck <command>.  Run with no command to see the list."""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
import time
from pathlib import Path

import yaml

from . import elements as E
from .macros import Library, Runner, slug, validate

from .paths import APP, DATA

BASE = DATA                      # your deck: deck.yaml, macros, icons...
LOG_FILE = APP / "ptdeck.log"


def log(msg):
    line = f"{datetime.datetime.now():%H:%M:%S} {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def mac_system():
    from .mac import MacSystem
    s = MacSystem()
    if not s.has_permission(prompt=True):
        sys.exit("PT Deck needs Accessibility permission.\n"
                 "System Settings > Privacy & Security > Accessibility: turn on Terminal "
                 "(or whichever app you started PT Deck from), then start it again.")
    return s


def library():
    return Library(BASE / "macros")


# ---------- commands ----------

def start_manager(system, deck=None) -> bool:
    """Start the Manager web page in the background. False if it's already running."""
    from .manager import Manager, serve
    mgr = Manager(BASE, runner_factory=lambda: Runner(system, library(), log=log), log=log)
    mgr.deck = deck
    try:
        serve(mgr, background=True)
    except OSError:          # port already in use: the Manager is already running
        return False
    return True


def stop_other_copies() -> int:
    """Stop any other PT Deck already running (two copies fight over the Stream Deck and the
    keys end up showing a mix of pages). Returns how many were stopped."""
    import os
    import signal
    me = os.getpid()
    try:
        out = subprocess.run(["pgrep", "-f", r"[-]m ptdeck (start|manager|menubar)|PT Deck[.]app/Contents/MacOS/PT Deck"], capture_output=True,
                             text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return 0
    others = [int(p) for p in out.split() if p.strip().isdigit() and int(p) not in (me, os.getppid())]
    found = len(others)
    for pid in others:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 4
    while others and time.time() < deadline:
        time.sleep(0.2)
        alive = []
        for pid in others:
            try:
                os.kill(pid, 0)
                alive.append(pid)
            except OSError:
                pass
        others = alive
    for pid in others:                    # still there: force it
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass
    return found


def cmd_start(a):
    from .deck import DeckController
    from .manager import PORT
    stopped = stop_other_copies()
    if stopped:
        log(f"Stopped {stopped} other copy(ies) of PT Deck that were already running.")
        time.sleep(0.5)
    system = mac_system()
    runner = Runner(system, library(), log=log)
    controller = DeckController(BASE, runner, log=log)
    if start_manager(system, controller):
        log(f"Manager: http://localhost:{PORT}  (or double-click Open Manager.command)")
    controller.run_forever()


def cmd_manager(a):
    from .manager import PORT
    started = start_manager(mac_system())
    subprocess.run(["open", f"http://localhost:{PORT}"])
    if not started:
        print("The Manager is already running (it starts with PT Deck). Opened it in your browser.")
        return
    log(f"Manager open at http://localhost:{PORT}. Close this window to stop it.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


def cmd_run(a):
    if a.delay:
        print(f"Running '{a.macro}' in {a.delay}s...")
        time.sleep(a.delay)
    Runner(mac_system(), library(), log=log).run(a.macro)


def clipboard() -> str:
    return subprocess.run(["pbpaste"], capture_output=True, text=True).stdout


def save_import(js: str, name: str, force: bool) -> bool:
    from .soundflow import convert, to_yaml
    macro, warnings = convert(js, name)
    out = BASE / "macros" / f"{slug(name)}.yaml"
    if out.exists() and not force:
        if input(f"{out.name} already exists. Replace it? [y/N] ").strip().lower() != "y":
            print("Skipped.")
            return False
    out.write_text(to_yaml(macro), encoding="utf-8")
    (BASE / "soundflow-scripts").mkdir(exist_ok=True)
    (BASE / "soundflow-scripts" / f"{slug(name)}.js").write_text(js, encoding="utf-8")
    print(f"Saved macros/{out.name} ({len(macro['steps'])} steps).")
    for w in warnings:
        if "Calls another SoundFlow command" not in w:
            print("  ! " + w)
    return True


def missing_macros() -> list[str]:
    """Macros used by other macros or by deck buttons that haven't been imported yet."""
    lib, missing = library(), []
    try:
        from .deck import load_config
        for items in load_config(BASE / "deck.yaml")["pages"].values():
            for b in items or []:
                if isinstance(b, dict) and b.get("macro"):
                    try:
                        lib.get(b["macro"])
                    except Exception:  # noqa: BLE001
                        if b["macro"] not in missing:
                            missing.append(b["macro"])
    except Exception:  # noqa: BLE001
        pass
    for m in lib.all():
        for step in m["steps"]:
            if isinstance(step, dict) and "run macro" in step:
                try:
                    lib.get(step["run macro"])
                except Exception:  # noqa: BLE001
                    if step["run macro"] not in missing:
                        missing.append(step["run macro"])
    return missing


def cmd_import(a):
    if a.watch:
        return import_watch(a)
    if a.file:
        js = Path(a.file).read_text(encoding="utf-8")
    else:
        js = clipboard()
        if "sf." not in js:
            sys.exit("The clipboard doesn't look like a SoundFlow script. "
                     "In SoundFlow, open the script, press Cmd+A then Cmd+C, and try again.")
    name = a.name or input("Name for this macro (e.g. the SoundFlow command name): ").strip()
    if not name:
        sys.exit("A name is needed.")
    save_import(js, name, a.force)


def copy_counter():
    """A number that goes up every time anything is copied (even the same text again)."""
    try:
        from AppKit import NSPasteboard
        pb = NSPasteboard.generalPasteboard()
        return lambda: pb.changeCount()
    except ImportError:          # not on a Mac (tests): fall back to comparing text
        return clipboard


def import_watch(a):
    import select
    print("Import mode: in SoundFlow, open a script, click in it, press Cmd+A then Cmd+C.")
    print("Each script you copy is picked up here. You can also press Return here to")
    print("import whatever is on the clipboard right now. Close this window when you're done.\n")
    need = missing_macros()
    if need:
        print("Buttons waiting for a script (copy the SoundFlow script with the same name,")
        print("then press Return to accept the suggested name):")
        for n in need:
            print(f"  - {n}")
        print()
    counter = copy_counter()
    last = counter()
    count = 0
    while True:
        pressed = False
        if sys.stdin.isatty():
            ready, _, _ = select.select([sys.stdin], [], [], 0.4)
            if ready:
                sys.stdin.readline()
                pressed = True
        else:
            time.sleep(0.4)
        now = counter()
        if now == last and not pressed:
            continue
        last = now
        js = clipboard()
        if "sf." not in js:
            preview = " ".join(js.split())[:70]
            print(f"Copied something, but it isn't a SoundFlow script: \"{preview}\"" if preview
                  else "The clipboard has no text in it (did the copy select anything?)")
            continue
        need = missing_macros()
        hint = f" [Return = {need[0]}]" if need else ""
        name = input(f"Got a script ({len(js.splitlines())} lines). Name{hint}: ").strip()
        if not name and need:
            name = need[0]
        if not name:
            print("No name given, skipped.\n")
            continue
        if save_import(js, name, a.force):
            count += 1
        need = missing_macros()
        if need:
            print("Still needed (called by your macros): " + ", ".join(need))
        print(f"{count} imported so far. Copy the next one...\n")
        last = counter()


def apply_additions(force=False, base=None):
    """Add new pages from the 'additions' folder to deck.yaml, without touching anything else.
    A page that already exists is left alone (unless force)."""
    from .deck import load_config
    from .manager import save_config
    base = Path(base) if base else BASE
    folder = base / "additions"
    if not folder.is_dir():
        return []
    cfg = load_config(base / "deck.yaml")
    applied = dict(cfg.get("additions applied") or {})
    before = dict(applied)
    added = []
    for f in sorted(folder.glob("*.yaml")):
        add = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        if add.get("update buttons on"):
            # Change some settings on existing buttons (matched by their macro), once.
            page, tag = add["update buttons on"], f.stem
            if page not in cfg["pages"] or applied.get(tag):
                continue
            n, drop = 0, []
            for b in cfg["pages"][page] or []:
                if not isinstance(b, dict):
                    continue
                for u in add.get("buttons") or []:
                    want = ("macro", u["macro"]) if u.get("macro") else ("folder", u.get("folder"))
                    if str(b.get(want[0], "")).lower() == str(want[1] or "").lower() and want[1]:
                        if u.get("delete"):
                            drop.append(b)
                        for k in u.get("remove") or []:
                            b.pop(k, None)
                        b.update(u.get("set") or {})
                        n += 1
            if drop:
                cfg["pages"][page] = [b for b in cfg["pages"][page] if not any(b is x for x in drop)]
            applied[tag] = 1
            cfg["additions applied"] = applied
            if n:
                added.append(f"{n} button(s) updated on {page}")
            continue
        if add.get("add to page"):
            # Add single buttons to an existing page, only into keys that are empty.
            page, tag = add["add to page"], f.stem
            if page not in cfg["pages"] or applied.get(tag):
                continue
            items = cfg["pages"][page] or []
            taken = {int(b.get("key", 0)) for b in items if isinstance(b, dict)}
            new = [b for b in add.get("buttons") or [] if int(b.get("key", 0)) not in taken]
            cfg["pages"][page] = items + new
            applied[tag] = 1
            cfg["additions applied"] = applied
            if new:
                added.append(f"{len(new)} button(s) on {page}")
            continue
        if add.get("fix macro"):
            # Change one line in a macro of yours that copies an old rebuilt one (once).
            tag = f.stem
            target = base / "macros" / str(add["fix macro"])
            if applied.get(tag):
                continue
            applied[tag] = 1
            cfg["additions applied"] = applied
            if target.exists():
                text = target.read_text(encoding="utf-8")
                new_text = text
                for old_line, new_line in (add.get("replace") or {}).items():
                    new_text = new_text.replace(str(old_line), str(new_line))
                if new_text != text:
                    target.write_text(new_text, encoding="utf-8")
                    added.append(f"updated your macro {target.name}")
            continue
        if add.get("rename page"):
            # Rename a page, keeping its place, and point every folder key at the new name.
            r, tag = add["rename page"], f.stem
            old_name, new_name = str(r.get("from")), str(r.get("to"))
            if applied.get(tag) or old_name not in cfg["pages"] or new_name in cfg["pages"]:
                continue
            cfg["pages"] = {(new_name if k == old_name else k): v for k, v in cfg["pages"].items()}
            for items in cfg["pages"].values():
                for b in items or []:
                    if isinstance(b, dict) and b.get("folder") == old_name:
                        b["folder"] = new_name
            if cfg.get("home") == old_name:
                cfg["home"] = new_name
            applied[tag] = 1
            cfg["additions applied"] = applied
            added.append(f"renamed {old_name} to {new_name}")
            continue
        if add.get("settings"):
            # Deck-wide settings (e.g. icon style), applied once.
            tag = f.stem
            if applied.get(tag):
                continue
            cfg.update(add["settings"])
            applied[tag] = 1
            cfg["additions applied"] = applied
            added.append("settings: " + ", ".join(f"{k} = {v}" for k, v in add["settings"].items()))
            continue
        page = add.get("page")
        version = int(add.get("version", 1))
        # A page that exists is only replaced by a newer version of the same addition.
        have = int(applied.get(page, 1 if page in cfg["pages"] else 0))
        if not page or (have >= version and not force):
            continue
        new_buttons = list(add.get("buttons") or [])
        if add.get("keep others") and page in cfg["pages"]:
            # Keep any of your own keys the new layout doesn't mention, where there's room.
            mine = {str(b.get("macro") or b.get("folder") or "").lower() for b in new_buttons}
            taken = {int(b.get("key", 0)) for b in new_buttons}
            for b in cfg["pages"][page] or []:
                if not isinstance(b, dict):
                    continue
                name = str(b.get("macro") or b.get("folder") or "").lower()
                if name in mine or name in {m.lower() for m in add.get("replaces") or []}:
                    continue
                if int(b.get("key", 0)) not in taken:
                    new_buttons.append(b)
                    taken.add(int(b.get("key", 0)))
        cfg["pages"][page] = new_buttons
        applied[page] = version
        cfg["additions applied"] = applied
        link = add.get("link")
        if link and link.get("page") in cfg["pages"]:
            items = [b for b in cfg["pages"][link["page"]] or []
                     if not (isinstance(b, dict) and int(b.get("key", 0)) == int(link["key"]))]
            items.append(dict(link["button"], key=int(link["key"])))
            cfg["pages"][link["page"]] = items
        added.append(page)
    if added or applied != before:
        save_config(base / "deck.yaml", cfg)
    return added


def remove_stale_rebuilt_copies(base) -> int:
    """Old PT Deck versions copied rebuilt macros into 'macros', where they then hid every
    later fix. Remove those copies (never anything you've written or edited)."""
    from .macros import REBUILT_MARK
    base = Path(base)
    rebuilt = {p.name for p in (base / "rebuilt").glob("*.yaml")}
    n = 0
    for p in (base / "macros").glob("*.yaml"):
        try:
            if p.name in rebuilt and p.read_text(encoding="utf-8", errors="ignore").startswith(REBUILT_MARK):
                p.unlink()
                n += 1
        except OSError:
            pass
    return n


def cmd_update(a):
    """Re-convert every saved SoundFlow script with the latest importer, then add
    the hand-rebuilt macros from the 'rebuilt' folder."""
    from .soundflow import convert, to_yaml
    macros = BASE / "macros"
    redone = kept = 0
    for js_path in sorted((BASE / "soundflow-scripts").glob("*.js")):
        out = macros / f"{js_path.stem}.yaml"
        name = js_path.stem
        if out.exists():
            text = out.read_text(encoding="utf-8")
            if not text.startswith("# Imported from SoundFlow"):
                kept += 1            # edited by hand or rebuilt: leave it alone
                continue
            name = (yaml.safe_load(text) or {}).get("name", name)
        macro, _ = convert(js_path.read_text(encoding="utf-8"), name)
        out.write_text(to_yaml(macro), encoding="utf-8")
        redone += 1
    removed = remove_stale_rebuilt_copies(BASE)
    added = len(list((BASE / "rebuilt").glob("*.yaml")))
    print(f"Re-converted {redone} imported macro(s), kept {kept} edited one(s), "
          f"{added} rebuilt macro(s) available" + (f", tidied {removed} old cop(ies)" if removed else "") + ".")
    pages = apply_additions()
    if pages:
        print(f"Added to your deck: {', '.join(pages)}")
    print()
    return cmd_check(a)


def cmd_check(a):
    from .deck import check_config, load_config, ConfigError
    lib = library()
    bad = 0
    for m in lib.all():
        for p in validate(m, lib):
            print(f"macros/{m['_file'].name}: {p}")
            bad += 1
    try:
        for p in check_config(load_config(BASE / "deck.yaml"), BASE, lib):
            print(f"deck.yaml: {p}")
            bad += 1
    except ConfigError as e:
        print(f"deck.yaml: {e}")
        bad += 1
    print("All good." if not bad else f"{bad} problem(s) found.")
    return 1 if bad else 0


def cmd_list(a):
    for m in library().all():
        print(f"{m['name']:40} macros/{m['_file'].name}  ({len(m['steps'])} steps)")


def cmd_preview(a):
    from .deck import load_config, preview
    cfg = load_config(BASE / "deck.yaml")
    pages = [a.page] if a.page else list(cfg["pages"])
    outdir = BASE / "previews"
    outdir.mkdir(exist_ok=True)
    for p in pages:
        out = outdir / f"{slug(p)}.png"
        preview(cfg, BASE, p, a.model or cfg.get("model", "original")).save(out)
        print(f"Saved {out.relative_to(BASE)}")


def cmd_rename(a):
    """Swap a name everywhere, e.g. after Avid renames a checkbox or window."""
    total = 0
    for path in library().files():
        text = path.read_text(encoding="utf-8")
        data, n = _swap(yaml.safe_load(text), a.old, a.new)
        if not n:
            continue
        header = "".join(l + "\n" for l in text.splitlines() if l.startswith("#"))
        if not a.dry_run:
            body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=1000)
            body = body.replace("\n- ", "\n\n- ").replace("steps:\n\n- ", "steps:\n- ")
            path.write_text(header + body, encoding="utf-8")
        print(f"{'Would change' if a.dry_run else 'Changed'} {n} place(s) in macros/{path.name}")
        total += n
    if not total:
        print(f"'{a.old}' wasn't found in any macro.")


def _swap(v, old, new):
    """Replace exact values, and whole parts of 'A > B' menu paths. Returns (new value, count)."""
    if isinstance(v, str):
        if v == old:
            return new, 1
        parts = [p.strip() for p in v.split(">")]
        if len(parts) > 1 and old in parts:
            return " > ".join(new if p == old else p for p in parts), parts.count(old)
        return v, 0
    if isinstance(v, list):
        pairs = [_swap(x, old, new) for x in v]
        return [x for x, _ in pairs], sum(k for _, k in pairs)
    if isinstance(v, dict):
        pairs = {key: _swap(x, old, new) for key, x in v.items()}
        return {key: x for key, (x, _) in pairs.items()}, sum(k for _, k in pairs.values())
    return v, 0


def _ancestry(el):
    chain, cur = [], el
    for _ in range(40):
        if cur is None:
            break
        chain.append(cur)
        if cur.attr("AXRole") in ("AXWindow", "AXApplication"):
            break
        cur = cur.attr("AXParent")
    return list(reversed(chain))


def cmd_pick(a):
    s = mac_system()
    for i in range(a.delay, 0, -1):
        print(f"Hover the mouse over the thing in Pro Tools... {i}", flush=True)
        time.sleep(1)
    x, y = s.mouse_position()
    el = s.element_at(x, y)
    if el is None:
        sys.exit("Nothing readable under the mouse.")
    chain = _ancestry(el)
    win = chain[0] if chain and chain[0].attr("AXRole") == "AXWindow" else None
    wname = E.labels(win)[0] if win is not None and E.labels(win) else None
    groups = [E.labels(c)[0] for c in chain[1:-1] if c.attr("AXRole") == "AXGroup" and E.labels(c)]
    role = el.attr("AXRole")
    kind = E.ROLE_TO_KIND.get(role, role)
    name = E.labels(el)[0] if E.labels(el) else None
    print("\nFound:", " > ".join(E.describe(c) for c in chain))
    fields = {}
    if wname:
        fields["window"] = wname
    if groups:
        fields["group"] = groups[-1]
    if name:
        action = "checkbox" if role == "AXCheckBox" else "click"
        step = {action: name, **({"set": "on"} if action == "checkbox" else {"kind": kind}), **fields}
        print("\nPaste this into a macro to click it:\n")
        print(yaml.safe_dump([step], sort_keys=False, allow_unicode=True))
    pos = (win or el).attr("AXPosition")
    if pos:
        print("Or, to click this exact spot (a 'click zone'):\n")
        print(yaml.safe_dump([{"click at": [round(x - pos[0]), round(y - pos[1])], **({"window": wname} if wname else {})}],
                             sort_keys=False, allow_unicode=True))


def cmd_probe_menu(a):
    """Describe an open Pro Tools pop-up menu, so menu handling can be fixed."""
    s = mac_system()
    for i in range(a.delay, 0, -1):
        print(f"Open the menu in Pro Tools and hover over an item (e.g. 'bus')... {i}", flush=True)
        time.sleep(1)
    app = s.app()
    out = ["== app children"]

    def dump(el, depth, limit=4):
        if depth > limit or len(out) > 400:
            return
        extra = ""
        for attr in ("AXSubrole", "AXValue"):
            v = el.attr(attr)
            if isinstance(v, str) and v.strip():
                extra += f" [{attr}={v.strip()[:40]!r}]"
        out.append("  " * depth + E.describe(el) + extra)
        for c in E.children(el):
            dump(c, depth + 1, limit)
    for c in E.children(app):
        dump(c, 1, 3 if c.attr("AXRole") == "AXWindow" and str(c.attr("AXTitle") or "").startswith(("Edit:", "Mix:")) else 6)
    out.append("== focused element and its parents")
    f = app.attr("AXFocusedUIElement")
    for _ in range(8):
        if f is None:
            break
        out.append("  " + E.describe(f) + f" [{f.attr('AXRole')}]")
        f = f.attr("AXParent")
    out.append("== under the mouse and its parents")
    x, y = s.mouse_position()
    el = s.element_at(x, y)
    for c in (_ancestry(el) if el is not None else []):
        out.append("  " + E.describe(c) + f" [{c.attr('AXRole')}]")
    text = "\n".join(out)
    dest = Path.home() / "Desktop" / "menu-probe.txt"
    dest.write_text(text, encoding="utf-8")
    print(f"Saved {dest}. Upload it to Claude.")


def cmd_probe_tools(a):
    """Record every detail of the Edit window's tool buttons, and the Trim tool's menu."""
    s = mac_system()
    app = s.app()
    win = E.find_window(app, "Edit:*")
    cluster = next(iter(E.find_all(win, "AXGroup", "Cursor Tool Cluster", max_depth=2)), None)
    if cluster is None:
        sys.exit("Couldn't find the tool buttons in the Edit window toolbar.")
    out = [f"== {a.label}"]

    def details(el, indent="  "):
        for n in el.attr_names():
            if n in ("AXChildren", "AXParent", "AXWindow", "AXTopLevelUIElement", "AXChildrenInNavigationOrder"):
                continue
            v = el.attr(n)
            if v not in (None, "", []):
                out.append(f"{indent}{n} = {str(v)[:80]!r}")
    for b in E.children(cluster):
        out.append("- " + E.describe(b))
        details(b, "    ")
    trim = next((b for b in E.children(cluster) if E.name_matches(b, "Trim tool*")), None)
    if trim is not None and a.menu:
        pos, size = trim.attr("AXPosition"), trim.attr("AXSize")
        s.click(pos[0] + size[0] / 2, pos[1] + size[1] / 2, button="right")
        time.sleep(0.8)
        out.append("== Trim tool right-click menu")
        for c in E.children(app):
            for item in E.find_all(c, "AXMenuItem", max_depth=4):
                out.append("- " + E.describe(item))
                details(item, "    ")
        s.key(53)    # Escape: close the menu without choosing
    dest = Path.home() / "Desktop" / f"tools-{a.label}.txt"
    dest.write_text("\n".join(out), encoding="utf-8")
    print(f"Saved {dest}")


def cmd_probe_plugin(a):
    """Record every detail of a plug-in window's controls (values, ranges, descriptions)."""
    s = mac_system()
    win = E.find_window(s.app(), a.window)
    out = [f"== {a.label}: {E.describe(win)}"]
    skip = {"AXChildren", "AXParent", "AXWindow", "AXTopLevelUIElement", "AXChildrenInNavigationOrder"}

    def dump(el, depth):
        if depth > 6 or len(out) > 3000:
            return
        out.append("  " * depth + "- " + E.describe(el))
        for n in el.attr_names():
            if n in skip:
                continue
            v = el.attr(n)
            if v not in (None, "", []):
                out.append("  " * depth + f"    {n} = {str(v)[:100]!r}")
        for c in E.children(el):
            dump(c, depth + 1)
    dump(win, 0)
    dest = Path.home() / "Desktop" / f"plugin-{a.label}.txt"
    dest.write_text("\n".join(out), encoding="utf-8")
    print(f"Saved {dest}")


def cmd_menubar(a):
    """PT Deck in the menu bar (what PT Deck.app runs)."""
    from .menubar import run
    run()


def cmd_make_app(a):
    """Create PT Deck.app (a menu bar app) in the PT Deck folder."""
    from .menubar import make_app
    app = make_app(APP, log=print)
    print(f"Made {app}")
    print("Double-click it to start PT Deck from the menu bar. You can drag it to your Dock or "
          "Applications too (keep the PT Deck folder where it is).")


def cmd_install_update(a):
    """Install a PT Deck download (.zip) from Terminal, for when the Manager isn't running."""
    import base64
    from .manager import Manager
    zp = Path(a.zip).expanduser()
    if not zp.exists():
        print(f"Can't find {zp}")
        return
    mgr = Manager(BASE, log=print)
    mgr.restart_soon = lambda: None
    res = mgr.install_update(base64.b64encode(zp.read_bytes()).decode())
    print(f"Installed {res['files']} files." + (f" Added: {', '.join(res['pages'])}" if res["pages"] else ""))
    print("Now double-click Start PT Deck.command.")


def cmd_metric_names(a):
    """Read MetricAB's song names now (its window must be open) and save the picture it read."""
    from .metric import MetricReader, order
    from .macros import Library, Runner
    s = mac_system()
    reader = MetricReader(Runner(s, Library(BASE / "macros"), log=lambda m: None), BASE, log=print)
    win = reader.window()
    if win is None:
        print("Open MetricAB first (on -OUT MASTER), then run this again.")
        return
    grid = reader.grid_image(win)
    if grid is None:
        print("Couldn't take a picture of the MetricAB window. Turn on Terminal in System Settings > "
              "Privacy & Security > Screen Recording, quit and reopen Terminal, then try again.")
        return
    dest = Path.home() / "Desktop" / "metric-grid.png"
    grid.save(dest)
    state = reader.poll()
    print(f"Saved the picture it read: {dest}")
    print(f"Selected: {state['selected']}   (slots counted by {order(BASE)})")
    for r in "1234":
        print("  " + " | ".join(f"{c}{r}: {state['names'].get(c + r, '') or '?'}" for c in "ABCD"))


def cmd_inspect(a):
    s = mac_system()
    app = s.app()
    if a.window is None:
        print("Open windows:")
        for w in E.window_list(app):
            print("  ", E.describe(w))
        print("\nRun again with a window name to see what's inside it.")
        return
    w = E.find_window(app, a.window)

    def show(el, depth):
        if depth > a.depth:
            return
        extra = ""
        val = el.attr("AXValue")
        if el.attr("AXRole") in ("AXCheckBox", "AXRadioButton"):
            extra = " [on]" if val else " [off]"
        elif isinstance(val, str) and val.strip() and val.strip() not in E.labels(el):
            extra = f" = {' / '.join(val.split(chr(10)))[:80]!r}"
        print("  " * depth + E.describe(el) + extra)
        for c in E.children(el):
            show(c, depth + 1)
    show(w, 0)


def cmd_colours(a):
    """Save a numbered chart of Pro Tools' track colours."""
    from PIL import Image, ImageDraw
    from .deck import font
    from .ptsl import PTSL, COLOUR_BASE
    pal = PTSL().palette()
    cols, size = 12, 64
    rows = (len(pal) + cols - 1) // cols
    img = Image.new("RGB", (cols * size, rows * size), "#1b1b1b")
    d = ImageDraw.Draw(img)
    for i, rgb in enumerate(pal):
        x, y = (i % cols) * size, (i // cols) * size
        d.rectangle([x + 2, y + 2, x + size - 3, y + size - 3], fill=rgb)
        text_col = "black" if sum(rgb) > 380 else "white"
        d.text((x + 8, y + 6), str(i + COLOUR_BASE), fill=text_col, font=font(18))
    out = BASE / "previews" / "track-colours.png"
    out.parent.mkdir(exist_ok=True)
    img.save(out)
    print(f"{len(pal)} colours. Chart saved to previews/track-colours.png")
    subprocess.run(["open", str(out)])


def cmd_test_pro_tools(a):
    """Check the scripting connection to Pro Tools."""
    from .ptsl import PTSL
    pt = PTSL()
    pt.connect()
    print("Connected to Pro Tools' scripting SDK.")
    try:
        name = pt.run("GetSessionName").get("session_name")
        print(f"Session: {name}")
        print(f"Selected tracks: {', '.join(pt.tracks('selected')) or '(none)'}")
    except Exception as e:  # noqa: BLE001
        print(f"(No session open? {e})")


def cmd_pro_tools(a):
    """Send any SDK command, e.g.: ptdeck pro-tools GetTrackList '{"page_limit": 5}'"""
    from .ptsl import PTSL
    res = PTSL().run(a.command, json.loads(a.body) if a.body else {})
    print(json.dumps(res, indent=2))


def main(argv=None):
    p = argparse.ArgumentParser(prog="ptdeck", description="Stream Deck macros for Pro Tools")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("start", help="connect to the Stream Deck and wait for presses")
    sub.add_parser("manager", help="open the Manager in your web browser")
    r = sub.add_parser("run", help="run one macro now")
    r.add_argument("macro")
    r.add_argument("--delay", type=float, default=0)
    i = sub.add_parser("import", help="convert a SoundFlow script (from the clipboard or a .js file)")
    i.add_argument("file", nargs="?")
    i.add_argument("--name")
    i.add_argument("--force", action="store_true")
    i.add_argument("--watch", action="store_true", help="keep importing each script you copy")
    sub.add_parser("check", help="look for mistakes in macros and deck.yaml")
    sub.add_parser("update", help="re-convert imported scripts and add rebuilt macros")
    sub.add_parser("list", help="list macros")
    v = sub.add_parser("preview", help="save pictures of the deck pages to the previews folder")
    v.add_argument("page", nargs="?")
    v.add_argument("--model", choices=["mini", "original", "mk2", "xl", "plus", "neo"])
    n = sub.add_parser("rename", help="replace a name in every macro (after a Pro Tools update)")
    n.add_argument("old")
    n.add_argument("new")
    n.add_argument("--dry-run", action="store_true")
    k = sub.add_parser("pick", help="show how to target whatever is under the mouse")
    k.add_argument("--delay", type=int, default=3)
    sub.add_parser("menubar", help="run PT Deck in the menu bar (used by PT Deck.app)")
    sub.add_parser("make-app", help="create PT Deck.app, the menu bar app")
    iu = sub.add_parser("install-update", help="install a PT Deck .zip without the Manager")
    iu.add_argument("zip")
    sub.add_parser("metric-names", help="read MetricAB's song names now (troubleshooting)")
    pp = sub.add_parser("probe-plugin", help="describe a plug-in window's controls (troubleshooting)")
    pp.add_argument("label")
    pp.add_argument("--window", default="Plug-in: ADPTR MetricAB*")
    pt_ = sub.add_parser("probe-tools", help="describe the toolbar tool buttons (troubleshooting)")
    pt_.add_argument("label")
    pt_.add_argument("--menu", action="store_true", help="also open the Trim tool's right-click menu")
    pm = sub.add_parser("probe-menu", help="describe an open pop-up menu (troubleshooting)")
    pm.add_argument("--delay", type=int, default=8)
    ins = sub.add_parser("inspect", help="list everything inside a Pro Tools window")
    ins.add_argument("window", nargs="?")
    ins.add_argument("--depth", type=int, default=8)
    sub.add_parser("colours", help="show Pro Tools' track colours with their numbers")
    sub.add_parser("test-pro-tools", help="check the scripting connection to Pro Tools")
    pc = sub.add_parser("pro-tools", help="send a Pro Tools Scripting SDK command")
    pc.add_argument("command")
    pc.add_argument("body", nargs="?")
    a = p.parse_args(argv)
    if not a.cmd:
        p.print_help()
        return 0
    try:
        return {"start": cmd_start, "manager": cmd_manager, "run": cmd_run, "import": cmd_import, "check": cmd_check,
                "list": cmd_list, "update": cmd_update, "preview": cmd_preview, "rename": cmd_rename, "pick": cmd_pick,
                "inspect": cmd_inspect, "probe-menu": cmd_probe_menu, "probe-tools": cmd_probe_tools, "probe-plugin": cmd_probe_plugin, "metric-names": cmd_metric_names, "install-update": cmd_install_update, "menubar": cmd_menubar, "make-app": cmd_make_app, "colours": cmd_colours, "test-pro-tools": cmd_test_pro_tools,
                "pro-tools": cmd_pro_tools}[a.cmd](a) or 0
    except Exception as e:  # noqa: BLE001 - friendly message instead of a traceback
        log(f"✗ {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
