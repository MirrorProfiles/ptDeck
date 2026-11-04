"""The macOS side: reading/pressing Pro Tools' interface (Accessibility) and
sending keys and mouse clicks (Quartz). Only imported on a Mac."""
from __future__ import annotations

import time
from pathlib import Path

import Quartz
from AppKit import NSRunningApplication, NSWorkspace
from ApplicationServices import (
    AXIsProcessTrustedWithOptions,
    AXUIElementCopyAttributeNames,
    AXUIElementCopyAttributeValue,
    AXUIElementCopyElementAtPosition,
    AXUIElementCreateApplication,
    AXUIElementCreateSystemWide,
    AXUIElementGetTypeID,
    AXUIElementPerformAction,
    AXUIElementSetAttributeValue,
    AXUIElementSetMessagingTimeout,
    AXValueGetType,
    AXValueGetTypeID,
    AXValueGetValue,
    kAXTrustedCheckOptionPrompt,
)
from CoreFoundation import CFGetTypeID

from .keys import MODIFIER_KEYCODES

PRO_TOOLS = "com.avid.ProTools"
_POINT = 1  # kAXValueCGPointType
_SIZE = 2   # kAXValueCGSizeType
_EL_TYPE = AXUIElementGetTypeID()
_VAL_TYPE = AXValueGetTypeID()


def _wrap(v):
    if v is None or isinstance(v, (bool, int, float)):
        return v
    if isinstance(v, str):
        return str(v)
    try:
        tid = CFGetTypeID(v)
    except Exception:  # noqa: BLE001
        tid = None
    if tid == _EL_TYPE:
        return AXElement(v)
    if tid == _VAL_TYPE:
        t = AXValueGetType(v)
        ok, val = AXValueGetValue(v, t, None)
        if not ok:
            return None
        if t == _POINT:
            return (float(val.x), float(val.y))
        if t == _SIZE:
            return (float(val.width), float(val.height))
        return None
    try:
        return [_wrap(x) for x in v]
    except TypeError:
        return v


class AXElement:
    def __init__(self, ref):
        self.ref = ref

    def attr(self, name):
        err, v = AXUIElementCopyAttributeValue(self.ref, name, None)
        return _wrap(v) if err == 0 else None

    def attr_names(self):
        err, names = AXUIElementCopyAttributeNames(self.ref, None)
        return [str(n) for n in names] if err == 0 and names else []

    def set_attr(self, name, value) -> bool:
        return AXUIElementSetAttributeValue(self.ref, name, value) == 0

    def perform(self, action) -> bool:
        return AXUIElementPerformAction(self.ref, action) == 0

    def __eq__(self, other):
        return isinstance(other, AXElement) and self.ref == other.ref

    def __hash__(self):
        return hash(self.ref)


class MacSystem:
    _ptsl = None

    def __init__(self):
        # Never wait more than 3s on any app for an Accessibility answer (the default is
        # much longer, which looks like a hang when Pro Tools is busy with a menu or dialog).
        try:
            AXUIElementSetMessagingTimeout(AXUIElementCreateSystemWide(), 3.0)
        except Exception:  # noqa: BLE001
            pass

    def ptsl(self):
        """Connection to Pro Tools' Scripting SDK, made on first use."""
        if self._ptsl is None:
            from .ptsl import PTSL
            self._ptsl = PTSL()
        return self._ptsl

    def now(self):
        return time.monotonic()

    def sleep(self, s):
        time.sleep(s)

    @staticmethod
    def has_permission(prompt=True) -> bool:
        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: prompt}))

    def _running(self):
        apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(PRO_TOOLS)
        if not apps or len(apps) == 0:
            raise RuntimeError("Pro Tools isn't running")
        return apps[0]

    def app(self, bundle: str | None = None):
        running = self._running() if bundle is None else self._running_app(bundle)
        ref = AXUIElementCreateApplication(running.processIdentifier())
        AXUIElementSetMessagingTimeout(ref, 3.0)
        return AXElement(ref)

    @staticmethod
    def _running_app(bundle_or_name: str):
        for a in NSWorkspace.sharedWorkspace().runningApplications():
            if bundle_or_name in (a.bundleIdentifier(), a.localizedName()):
                return a
        raise RuntimeError(f"'{bundle_or_name}' isn't running")

    def open(self, target: str):
        """Open a file, folder or app (a path, or an app name like 'QuickTime Player')."""
        import os
        import subprocess
        path = os.path.expanduser(target)
        cmd = ["open", path] if os.path.exists(path) or "/" in target else ["open", "-a", target]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"couldn't open '{target}': {r.stderr.strip()}")
        time.sleep(0.5)

    def quit_app(self, bundle_or_name: str):
        try:
            app = self._running_app(bundle_or_name)
        except RuntimeError:
            return                       # already closed
        app.terminate()
        end = time.monotonic() + 10
        while time.monotonic() < end and not app.isTerminated():
            time.sleep(0.1)

    _midi_ports: dict = {}

    def midi_cc(self, port: str, channel: int, cc: int, value: int):
        import mido
        names = mido.get_output_names()
        match = next((n for n in names if n == port), None) or next((n for n in names if port.lower() in n.lower()), None)
        if match is None:
            raise RuntimeError(f"MIDI port '{port}' not found. Available: {', '.join(names) or 'none'}")
        if match not in self._midi_ports:
            self._midi_ports[match] = mido.open_output(match)
        self._midi_ports[match].send(mido.Message("control_change", channel=channel - 1, control=cc, value=value))

    def activate(self):
        app = self._running()
        app.activateWithOptions_(1 << 1)  # ignore other apps
        self.app().set_attr("AXFrontmost", True)
        end = time.monotonic() + 3
        while time.monotonic() < end:
            front = NSWorkspace.sharedWorkspace().frontmostApplication()
            if front and front.bundleIdentifier() == PRO_TOOLS:
                return
            time.sleep(0.05)

    # ----- keyboard -----
    def _post(self, ev):
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        time.sleep(0.004)

    def key(self, code: int, flags: int = 0):
        held = 0
        for flag, mc in MODIFIER_KEYCODES.items():
            if flags & flag:
                held |= flag
                ev = Quartz.CGEventCreateKeyboardEvent(None, mc, True)
                Quartz.CGEventSetFlags(ev, held)
                self._post(ev)
        for down in (True, False):
            ev = Quartz.CGEventCreateKeyboardEvent(None, code, down)
            Quartz.CGEventSetFlags(ev, flags)
            self._post(ev)
        for flag, mc in reversed(list(MODIFIER_KEYCODES.items())):
            if flags & flag:
                held &= ~flag
                ev = Quartz.CGEventCreateKeyboardEvent(None, mc, False)
                Quartz.CGEventSetFlags(ev, held)
                self._post(ev)
        time.sleep(0.02)

    def hold(self, flags: int, down: bool):
        """Press (down=True) or release modifier keys, e.g. while picking a menu item."""
        items = list(MODIFIER_KEYCODES.items())
        held = flags if not down else 0
        for flag, mc in (items if down else reversed(items)):
            if flags & flag:
                held = held | flag if down else held & ~flag
                ev = Quartz.CGEventCreateKeyboardEvent(None, mc, down)
                Quartz.CGEventSetFlags(ev, held)
                self._post(ev)

    @staticmethod
    def _osa_list(items):
        return "{" + ", ".join('"' + str(i).replace('"', '\\"') + '"' for i in items) + "}"

    def choose(self, items, prompt, title="PT Deck"):
        """A small macOS 'choose from list' dialog. Returns the choice, or None if cancelled."""
        import subprocess
        q = lambda t: '"' + str(t).replace('"', '\\"') + '"'  # noqa: E731
        script = (f"choose from list {self._osa_list(items)} with prompt {q(prompt)} with title {q(title)} "
                  f"default items {{{q(items[0])}}}")
        full = f'tell application "System Events"\nactivate\nset r to ({script})\nend tell\nreturn r'
        r = subprocess.run(["osascript", "-e", full], capture_output=True, text=True)
        out = r.stdout.strip()
        return None if not out or out == "false" else out

    def alert(self, message, title="PT Deck"):
        import subprocess
        q = lambda t: '"' + str(t).replace('"', '\\"') + '"'  # noqa: E731
        subprocess.Popen(["osascript", "-e", f"display notification {q(message)} with title {q(title)}"])

    def paste(self, text: str):
        """Put text on the clipboard, press Cmd+V, then put the old clipboard back."""
        import subprocess
        from .keys import parse_combo
        old = subprocess.run(["pbpaste"], capture_output=True).stdout
        subprocess.run(["pbcopy"], input=text.encode("utf-8"))
        time.sleep(0.05)
        self.key(*parse_combo("cmd+v"))
        time.sleep(0.3)
        subprocess.run(["pbcopy"], input=old)

    def type_text(self, text: str):
        for ch in text:
            for down in (True, False):
                ev = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
                Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch.encode("utf-16-le")) // 2, ch)
                self._post(ev)

    # ----- mouse -----
    def window_image(self, x, y, w, h):
        """A picture of the Pro Tools window at this position/size (a PIL image), or None.
        Needs Screen Recording permission for Terminal."""
        import subprocess
        import tempfile
        from PIL import Image
        infos = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,
                                                  Quartz.kCGNullWindowID) or []
        wid = None
        for i in infos:
            if "Pro Tools" not in str(i.get("kCGWindowOwnerName", "")):
                continue
            b = i.get("kCGWindowBounds") or {}
            if all(abs(float(b.get(k, -99)) - v) < 3 for k, v in (("X", x), ("Y", y), ("Width", w), ("Height", h))):
                wid = int(i["kCGWindowNumber"])
                break
        if wid is None:
            return None
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "window.png"
            subprocess.run(["screencapture", "-x", "-o", f"-l{wid}", str(path)],
                           capture_output=True, timeout=10)
            if not path.exists():
                return None
            img = Image.open(path)
            img.load()
            return img

    def read_text(self, image):
        """Text in a picture, using macOS's own text recognition: [(text, x, y)] with x/y
        as 0-1 fractions from the top-left."""
        import io
        try:
            import Vision
        except ImportError:
            raise RuntimeError("text recognition isn't installed yet: run Install.command again") from None
        from Foundation import NSData
        if image.height < 48:          # small text reads better a little bigger
            k = 48 / image.height
            image = image.resize((int(image.width * k), 48))
        buf = io.BytesIO()
        image.save(buf, "PNG")
        raw = buf.getvalue()
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        req.setUsesLanguageCorrection_(False)
        handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(
            NSData.dataWithBytes_length_(raw, len(raw)), None)
        handler.performRequests_error_([req], None)
        out = []
        for obs in req.results() or []:
            cands = obs.topCandidates_(1)
            if not cands:
                continue
            bb = obs.boundingBox()
            out.append((str(cands[0].string()), bb.origin.x + bb.size.width / 2,
                        1 - (bb.origin.y + bb.size.height / 2)))
        out.sort(key=lambda t: (round(t[2], 1), t[1]))
        return out

    def scroll(self, x, y, dy):
        """Scroll-wheel at (x, y) by dy pixels (positive = towards the top)."""
        self.move_mouse(x, y)
        ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitPixel, 1, int(dy))
        Quartz.CGEventSetLocation(ev, (x, y))
        self._post(ev)

    def move_mouse(self, x, y):
        self._post(Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y),
                                                  Quartz.kCGMouseButtonLeft))

    def mouse_position(self):
        p = Quartz.CGEventGetLocation(Quartz.CGEventCreate(None))
        return p.x, p.y

    def click(self, x, y, button="left", count=1, flags=0):
        if button == "right":
            down_t, up_t, btn = Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGMouseButtonRight
        else:
            down_t, up_t, btn = Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, Quartz.kCGMouseButtonLeft
        pt = (x, y)
        move = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, pt, btn)
        self._post(move)
        time.sleep(0.03)
        for n in range(1, count + 1):
            for t in (down_t, up_t):
                ev = Quartz.CGEventCreateMouseEvent(None, t, pt, btn)
                Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, n)
                if flags:
                    Quartz.CGEventSetFlags(ev, flags)
                self._post(ev)
            time.sleep(0.03)

    def drag(self, start, end, steps=12):
        """Press at start, move to end, release (like dragging with the mouse)."""
        btn = Quartz.kCGMouseButtonLeft
        self._post(Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, start, btn))
        time.sleep(0.05)
        self._post(Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, start, btn))
        time.sleep(0.1)
        for i in range(1, steps + 1):
            p = (start[0] + (end[0] - start[0]) * i / steps, start[1] + (end[1] - start[1]) * i / steps)
            self._post(Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDragged, p, btn))
            time.sleep(0.015)
        time.sleep(0.1)
        self._post(Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, end, btn))
        time.sleep(0.1)

    def element_at(self, x, y):
        err, el = AXUIElementCopyElementAtPosition(AXUIElementCreateSystemWide(), x, y, None)
        return AXElement(el) if err == 0 and el is not None else None
