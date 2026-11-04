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

from .paths import APP as BASE, DATA     # BASE: the PT Deck folder; DATA: your deck
APP = BASE / "PT Deck.app"
AGENT = Path.home() / "Library" / "LaunchAgents" / "com.easstudios.ptdeck.plist"
BUNDLE_ID = "com.easstudios.ptdeck"


# ---------- the app bundle ----------

LAUNCHER_C = r"""
/* PT Deck.app's own program: runs PT Deck's Python inside this app, so macOS treats PT Deck as
   an app (its menu bar icon is shown; permissions are listed as "PT Deck"). Made by make-app. */
#include <Python.h>
#include <mach-o/dyld.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

int main(int argc, char **argv) {
    char exe[PATH_MAX], real[PATH_MAX];
    uint32_t n = sizeof exe;
    if (_NSGetExecutablePath(exe, &n) != 0 || !realpath(exe, real)) return 1;
    char *menubar[] = {real, "-m", "ptdeck", "menubar", NULL};
    if (argc < 2) {                       /* opened from Finder: run the menu bar app, in this */
        argc = 4;                         /* same process (handing over with exec loses the icon) */
        argv = menubar;
    }
    char base[PATH_MAX];                  /* .../chp/PT Deck.app/Contents/MacOS/PT Deck -> .../chp */
    strncpy(base, real, sizeof base - 1); base[sizeof base - 1] = 0;
    for (int i = 0; i < 4; i++) { char *s = strrchr(base, '/'); if (!s) return 1; *s = 0; }
    if (chdir(base) != 0) return 1;
    char py[PATH_MAX], logp[PATH_MAX], path[PATH_MAX * 2];
    snprintf(py, sizeof py, "%s/.venv/bin/python", base);
    if (access(py, X_OK) != 0) {
        system("osascript -e 'display alert \"PT Deck isn'\\''t installed yet\" message "
               "\"Double-click Install.command in the PT Deck folder first.\"'");
        return 1;
    }
    snprintf(logp, sizeof logp, "%s/ptdeck-app.log", base);
    freopen(logp, "a", stdout);
    freopen(logp, "a", stderr);
    setenv("PTDECK_LAUNCHER", real, 1);   /* PT Deck restarts itself through this program */
    snprintf(path, sizeof path, "%s:%s/.venv/lib/python%d.%d/site-packages", base, base,
             PY_MAJOR_VERSION, PY_MINOR_VERSION);
    setenv("PYTHONPATH", path, 1);

    PyStatus st;
    PyConfig c;
    PyConfig_InitPythonConfig(&c);
    c.buffered_stdio = 0;
    st = PyConfig_SetBytesString(&c, &c.executable, py);   /* finds the .venv (pyvenv.cfg) */
    if (!PyStatus_Exception(st)) st = PyConfig_SetBytesString(&c, &c.program_name, py);
    if (!PyStatus_Exception(st)) st = PyConfig_SetBytesArgv(&c, argc, argv);
    if (!PyStatus_Exception(st)) st = Py_InitializeFromConfig(&c);
    PyConfig_Clear(&c);
    if (PyStatus_Exception(st)) Py_ExitStatusException(st);
    return Py_RunMain();
}
"""

LAUNCHER_SH = """#!/bin/bash
# Starts PT Deck from the folder this app sits in.
DIR="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$DIR" || exit 1
if [ ! -x .venv/bin/python ]; then
  osascript -e 'display alert "PT Deck isn'"'"'t installed yet" message "Double-click Install.command in the PT Deck folder first."'
  exit 1
fi
exec "$DIR/.venv/bin/python" -m ptdeck menubar >> "$DIR/ptdeck-app.log" 2>&1
"""


def _python_config() -> list[str]:
    """Compiler flags for embedding this Python (from python3.X-config), or [] if not found."""
    import shutil
    import sysconfig
    ver = sysconfig.get_config_var("VERSION") or f"{sys.version_info[0]}.{sys.version_info[1]}"
    for cand in (Path(sys.base_prefix) / "bin" / f"python{ver}-config", shutil.which(f"python{ver}-config"),
                 "/opt/homebrew/bin/python3.12-config", "/usr/local/bin/python3.12-config"):
        if cand and Path(cand).exists():
            out = subprocess.run([str(cand), "--embed", "--cflags", "--ldflags"], capture_output=True,
                                 text=True, timeout=20)
            if out.returncode == 0 and out.stdout.strip():
                return out.stdout.split()
    return []


def build_launcher(exe: Path, log=print) -> bool:
    """Compile PT Deck.app's own program (needs Apple's command line tools, which Homebrew installs).
    Returns False, having changed nothing, if it can't."""
    import tempfile
    if sys.platform != "darwin":
        return False
    if subprocess.run(["xcode-select", "-p"], capture_output=True).returncode != 0:
        log("(PT Deck.app uses a simple starter: Apple's command line tools aren't installed)")
        return False
    flags = _python_config()
    if not flags:
        log("(PT Deck.app uses a simple starter: couldn't find python3.12-config)")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        src, out = Path(tmp) / "launcher.c", Path(tmp) / "PT Deck"
        src.write_text(LAUNCHER_C, encoding="utf-8")
        res = subprocess.run(["cc", "-O2", "-Wno-unused-result", str(src), "-o", str(out), *flags],
                             capture_output=True, text=True, timeout=120)
        if res.returncode != 0 or not out.exists():
            log("(PT Deck.app uses a simple starter: building its own program failed: "
                + (res.stderr.strip().splitlines() or ["?"])[-1] + ")")
            return False
        tmp_exe = exe.with_name(exe.name + ".new")
        shutil_copy(out, tmp_exe)
        os.replace(tmp_exe, exe)          # safe even while PT Deck.app is running
    return True


def shutil_copy(a: Path, b: Path):
    import shutil
    shutil.copy2(a, b)
    b.chmod(0o755)


def make_app(base: Path = BASE, log=print) -> Path:
    """Create 'PT Deck.app' next to PT Deck's files: a menu bar app (no Dock icon) that runs
    PT Deck with this folder's Python. Safe to run again (e.g. after an update)."""
    app = base / "PT Deck.app"
    macos = app / "Contents" / "MacOS"
    res = app / "Contents" / "Resources"
    macos.mkdir(parents=True, exist_ok=True)
    res.mkdir(parents=True, exist_ok=True)
    exe = macos / "PT Deck"
    if build_launcher(exe, log=log):
        log("PT Deck.app runs PT Deck itself (menu bar icon and permissions show as 'PT Deck').")
    else:
        tmp_exe = exe.with_name(exe.name + ".new")
        tmp_exe.write_text(LAUNCHER_SH, encoding="utf-8")
        tmp_exe.chmod(0o755)
        os.replace(tmp_exe, exe)
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
    """The program macOS gives permissions to: PT Deck.app's own program, or the real Python."""
    return os.environ.get("PTDECK_LAUNCHER") or os.path.realpath(sys.executable)


def shown_as() -> str:
    """The name PT Deck has in System Settings' lists."""
    return "PT Deck" if os.environ.get("PTDECK_LAUNCHER") else "python3"


def relaunch_app() -> bool:
    """When PT Deck runs as PT Deck.app, restart by opening the app again a moment after this copy
    quits (a restart that hands over with exec loses the menu bar icon). The caller then exits."""
    if not os.environ.get("PTDECK_LAUNCHER"):
        return False
    subprocess.Popen(["/bin/sh", "-c", 'sleep 1; /usr/bin/open -n "$0"', str(APP)], start_new_session=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def self_command(*args) -> list[str]:
    """The command that starts PT Deck again the way it is running now (through PT Deck.app's own
    program when it started that way, so the menu bar icon still shows after a restart)."""
    launcher = os.environ.get("PTDECK_LAUNCHER")
    return [launcher or sys.executable, "-m", "ptdeck", *args]


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
    M.trim_log(BASE / "ptdeck-app.log")      # the app's own log, held open by its starter
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
        ask_for("Screen Recording")          # adds PT Deck / python3 to Screen Recording's list
    M.log(f"PT Deck runs as {python_path()} (shown as '{shown_as()}' in System Settings)")
    runner = Runner(system, M.library(), log=M.log)
    controller = DeckController(DATA, runner, log=M.log)
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
        if relaunch_app():
            os._exit(0)
        os.chdir(BASE)
        cmd = self_command("menubar")
        os.execv(cmd[0], cmd)

    class Delegate(NSObject):
        def applicationDidFinishLaunching_(self, _n):
            try:
                self._build()
                M.log("Menu bar icon added (top right of the screen, near the clock).")
            except Exception:  # noqa: BLE001 - say why, rather than run on silently with no icon
                import traceback
                M.log("Couldn't add the menu bar icon: " + traceback.format_exc().strip().splitlines()[-1])
                M.log(traceback.format_exc())

        @objc.python_method
        def _build(self):
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
                f"In System Settings, PT Deck appears as \u201c{shown_as()}\u201d", None, "")
            note.setEnabled_(False)
            self.perm_menu.addItem_(note)
            show = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
                f"Not in the list? Show {shown_as()} in Finder (drag it into the list)", "showPython:", "")
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
            subprocess.run(["open", "-R", str(APP) if os.environ.get("PTDECK_LAUNCHER") else python_path()])

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
                mgr = Manager(DATA, log=M.log)
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
    M.log("Starting the menu bar app…")
    app.run()
