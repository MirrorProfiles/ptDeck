"""PT Deck in the macOS menu bar: runs the deck and the Manager with no Terminal window.

Menu: status · Open Manager · Install Update… · Show Log · Permissions · Open at Login ·
Restart · Quit. Started by 'PT Deck.app' (made with: python -m ptdeck make-app).
"""
from __future__ import annotations

import base64
import os
import plistlib
import subprocess
import sys
import threading
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
APP = BASE / "PT Deck.app"
AGENT = Path.home() / "Library" / "LaunchAgents" / "com.easstudios.ptdeck.plist"
BUNDLE_ID = "com.easstudios.ptdeck"


# ---------- the app bundle ----------

def make_app(base: Path = BASE, log=print) -> Path:
    """Create 'PT Deck.app' next to PT Deck's files: a menu bar app (no Dock icon) that starts
    PT Deck with this folder's Python. Safe to run again (e.g. after an update)."""
    app = base / "PT Deck.app"
    macos = app / "Contents" / "MacOS"
    res = app / "Contents" / "Resources"
    macos.mkdir(parents=True, exist_ok=True)
    res.mkdir(parents=True, exist_ok=True)
    exe = macos / "PT Deck"
    exe.write_text('''#!/bin/bash
# Starts PT Deck from the folder this app sits in.
DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$DIR" || exit 1
if [ ! -x .venv/bin/python ]; then
  osascript -e 'display alert "PT Deck isn'"'"'t installed yet" message "Double-click Install.command in the PT Deck folder first."'
  exit 1
fi
exec "$DIR/.venv/bin/python" -m ptdeck menubar >> "$DIR/ptdeck-app.log" 2>&1
''', encoding="utf-8")
    exe.chmod(0o755)
    info = {
        "CFBundleName": "PT Deck", "CFBundleDisplayName": "PT Deck", "CFBundleIdentifier": BUNDLE_ID,
        "CFBundleExecutable": "PT Deck", "CFBundlePackageType": "APPL", "CFBundleVersion": "1",
        "CFBundleShortVersionString": "1.0", "LSUIElement": True, "CFBundleIconFile": "PTDeck",
        "NSHighResolutionCapable": True,
        "NSAppleEventsUsageDescription": "PT Deck controls Pro Tools for your Stream Deck macros.",
    }
    with (app / "Contents" / "Info.plist").open("wb") as f:
        plistlib.dump(info, f)
    try:
        _make_icns(res / "PTDeck.icns")
    except Exception as e:  # noqa: BLE001 - an app without its own icon still works
        log(f"(no app icon: {e})")
    subprocess.run(["touch", str(app)], check=False)
    return app


def _app_icon_png(size=1024):
    """The app's icon: a little Stream Deck in PT Deck's colours."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    m = size * 0.08
    d.rounded_rectangle([m, m * 1.6, size - m, size - m * 1.6], radius=size * 0.16, fill=(28, 30, 34, 255))
    cols, rows = 4, 3
    gx0, gy0, gx1, gy1 = size * 0.17, size * 0.27, size * 0.83, size * 0.73
    w, h = (gx1 - gx0) / cols, (gy1 - gy0) / rows
    colours = [(217, 137, 79), (96, 214, 108), (34, 184, 240), (194, 32, 127)]
    for r in range(rows):
        for c in range(cols):
            x, y = gx0 + c * w, gy0 + r * h
            fill = colours[(r + c) % 4] if (r + c) % 3 == 0 else (60, 64, 72)
            d.rounded_rectangle([x + w * 0.1, y + h * 0.1, x + w * 0.9, y + h * 0.9], radius=w * 0.14, fill=fill)
    return img


def _make_icns(dest: Path):
    import shutil
    import tempfile
    if not shutil.which("iconutil"):
        raise RuntimeError("iconutil isn't available")
    big = _app_icon_png()
    with tempfile.TemporaryDirectory() as t:
        iconset = Path(t) / "PTDeck.iconset"
        iconset.mkdir()
        for px in (16, 32, 128, 256, 512):
            big.resize((px, px)).save(iconset / f"icon_{px}x{px}.png")
            big.resize((px * 2, px * 2)).save(iconset / f"icon_{px}x{px}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(dest)], check=True)


def menu_icon(connected: bool, path: Path) -> Path:
    """The menu bar glyph (a 'template' image: macOS colours it for light/dark menu bars).
    Filled keys when connected, outlined while waiting."""
    from PIL import Image, ImageDraw
    s = 44
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for r in range(2):
        for c in range(3):
            x, y = 4 + c * 13, 9 + r * 14
            box = [x, y, x + 10, y + 10]
            if connected:
                d.rounded_rectangle(box, radius=3, fill=(0, 0, 0, 255))
            else:
                d.rounded_rectangle(box, radius=3, outline=(0, 0, 0, 255), width=2)
    img.save(path)
    return path


# ---------- open at login ----------

def login_enabled() -> bool:
    return AGENT.exists()


def set_login(on: bool, app: Path = APP):
    if on:
        AGENT.parent.mkdir(parents=True, exist_ok=True)
        with AGENT.open("wb") as f:
            plistlib.dump({"Label": BUNDLE_ID, "ProgramArguments": ["/usr/bin/open", "-a", str(app)],
                           "RunAtLoad": True}, f)
    elif AGENT.exists():
        AGENT.unlink()


# ---------- permissions ----------

def permissions() -> dict:
    """{'Accessibility': bool, 'Screen Recording': bool} for this app."""
    out = {}
    try:
        from ApplicationServices import AXIsProcessTrusted
        out["Accessibility"] = bool(AXIsProcessTrusted())
    except Exception:  # noqa: BLE001
        out["Accessibility"] = False
    try:
        import Quartz
        out["Screen Recording"] = bool(Quartz.CGPreflightScreenCaptureAccess())
    except Exception:  # noqa: BLE001
        out["Screen Recording"] = True       # can't tell on this macOS: don't nag
    return out


def python_path() -> str:
    """The real Python program running PT Deck (what macOS lists as 'python3')."""
    return os.path.realpath(sys.executable)


def ask_for(name: str):
    """Ask macOS for a permission: this is what puts 'python3' into System Settings' list
    (and shows macOS's own 'allow?' prompt the first time)."""
    try:
        if name == "Screen Recording":
            import Quartz
            Quartz.CGRequestScreenCaptureAccess()
        elif name == "Accessibility":
            from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
            AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True})
    except Exception:  # noqa: BLE001 - older macOS: the settings page is still opened
        pass


SETTINGS_PANES = {
    "Accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "Screen Recording": "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture",
}


# ---------- the menu bar app ----------

def run():
    import objc
    from AppKit import (NSApplication, NSApplicationActivationPolicyAccessory, NSImage, NSMenu,
                        NSMenuItem, NSOpenPanel, NSStatusBar, NSVariableStatusItemLength)
    from Foundation import NSObject, NSTimer

    from . import __main__ as M
    from .deck import DeckController
    from .macros import Runner
    from .manager import PORT, Manager
    from .mac import MacSystem

    stopped = M.stop_other_copies()
    if stopped:
        M.log(f"Stopped {stopped} other copy(ies) of PT Deck that were already running.")
    system = MacSystem()
    if not system.has_permission(prompt=True):
        M.log("PT Deck needs Accessibility permission: see the menu bar icon > Permissions.")
    if not permissions().get("Screen Recording", True):
        ask_for("Screen Recording")          # adds python3 to Screen Recording's list
    M.log(f"PT Deck runs as {python_path()} (shown as 'python3' in System Settings)")
    runner = Runner(system, M.library(), log=M.log)
    controller = DeckController(BASE, runner, log=M.log)
    if M.start_manager(system, controller):
        M.log(f"Manager: http://localhost:{PORT}")
    threading.Thread(target=controller.run_forever, daemon=True).start()

    icons_dir = BASE / ".menubar"
    icons_dir.mkdir(exist_ok=True)
    icon_on = NSImage.alloc().initWithContentsOfFile_(str(menu_icon(True, icons_dir / "on.png")))
    icon_off = NSImage.alloc().initWithContentsOfFile_(str(menu_icon(False, icons_dir / "off.png")))
    for im in (icon_on, icon_off):
        im.setTemplate_(True)
        im.setSize_((22, 22))

    def restart():
        controller.stop()
        os.chdir(BASE)
        os.execv(sys.executable, [sys.executable, "-m", "ptdeck", "menubar"])

    class Delegate(NSObject):
        def applicationDidFinishLaunching_(self, _n):
            self.item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
            self.item.button().setImage_(icon_off)
            self.item.button().setToolTip_("PT Deck")
            self.menu = NSMenu.alloc().init()
            self.menu.setAutoenablesItems_(False)
            self.status = self._add("Starting…", None)
            self.status.setEnabled_(False)
            self.menu.addItem_(NSMenuItem.separatorItem())
            self._add("Open Manager…", "openManager:", "m")
            self._add("Install Update…", "installUpdate:", "u")
            self._add("Show Log", "showLog:", "l")
            self.menu.addItem_(NSMenuItem.separatorItem())
            self.perm_menu = NSMenu.alloc().init()
            self.perm_item = self._add("Permissions", None)
            self.perm_item.setSubmenu_(self.perm_menu)
            self.login = self._add("Open at Login", "toggleLogin:")
            self.menu.addItem_(NSMenuItem.separatorItem())
            self._add("Restart PT Deck", "restart:", "r")
            self._add("Quit PT Deck", "quit:", "q")
            self.item.setMenu_(self.menu)
            self.tick_(None)
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(2.0, self, "tick:", None, True)

        @objc.python_method
        def _add(self, title, action, key=""):
            it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
            if action:
                it.setTarget_(self)
            self.menu.addItem_(it)
            return it

        @objc.python_method
        def _refresh_permissions(self):
            self.perm_menu.removeAllItems()
            perms = permissions()
            for name, ok in perms.items():
                it = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                    f"{'✓' if ok else '✗'} {name}" + ("" if ok else " — click to turn on"), "openSettings:", "")
                it.setTarget_(self)
                it.setRepresentedObject_(name)
                self.perm_menu.addItem_(it)
            self.perm_menu.addItem_(NSMenuItem.separatorItem())
            note = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "In System Settings, PT Deck appears as \u201cpython3\u201d", None, "")
            note.setEnabled_(False)
            self.perm_menu.addItem_(note)
            show = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                "Not in the list? Show python3 in Finder (drag it into the list)", "showPython:", "")
            show.setTarget_(self)
            self.perm_menu.addItem_(show)
            missing = [n for n, ok in perms.items() if not ok]
            self.perm_item.setTitle_("Permissions" + (f" ({len(missing)} missing)" if missing else " ✓"))

        def tick_(self, _t):
            connected = controller.deck is not None
            self.item.button().setImage_(icon_on if connected else icon_off)
            self.status.setTitle_(str(getattr(controller, "status", "")) or "PT Deck")
            self.item.button().setToolTip_(f"PT Deck: {getattr(controller, 'status', '')}")
            self.login.setState_(1 if login_enabled() else 0)
            self._refresh_permissions()

        def openManager_(self, _s):
            subprocess.run(["open", f"http://localhost:{PORT}"])

        def showLog_(self, _s):
            subprocess.run(["open", "-a", "Console", str(M.LOG_FILE)])

        def openSettings_(self, sender):
            name = str(sender.representedObject())
            ask_for(name)              # macOS only lists an app once it has asked
            subprocess.run(["open", SETTINGS_PANES.get(name, SETTINGS_PANES["Accessibility"])])

        def showPython_(self, _s):
            subprocess.run(["open", "-R", python_path()])

        def toggleLogin_(self, _s):
            set_login(not login_enabled())
            self.tick_(None)

        def installUpdate_(self, _s):
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
            panel = NSOpenPanel.openPanel()
            panel.setTitle_("Choose the PT Deck update (.zip)")
            panel.setAllowedFileTypes_(["zip"])
            panel.setDirectoryURL_(__import__("Foundation").NSURL.fileURLWithPath_(str(Path.home() / "Downloads")))
            if panel.runModal() != 1:
                return
            path = Path(str(panel.URLs()[0].path()))
            try:
                mgr = Manager(BASE, log=M.log)
                mgr.restart_soon = lambda: None
                res = mgr.install_update(base64.b64encode(path.read_bytes()).decode())
                make_app(BASE, log=M.log)
                M.log(f"Installed update from {path.name} ({res['files']} files). Restarting…")
                subprocess.run(["osascript", "-e", f'display notification "Installed {res["files"]} files. '
                                f'Restarting PT Deck." with title "PT Deck updated"'])
            except Exception as e:  # noqa: BLE001
                subprocess.run(["osascript", "-e", f'display alert "Update failed" message "{str(e)[:200]}"'])
                return
            restart()

        def restart_(self, _s):
            restart()

        def quit_(self, _s):
            controller.stop()
            NSApplication.sharedApplication().terminate_(None)

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = Delegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()
