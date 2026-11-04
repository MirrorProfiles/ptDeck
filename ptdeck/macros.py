"""Loading macro files and running their steps."""
from __future__ import annotations

import re
import time
from pathlib import Path

import yaml

from . import elements as E
from .ptsl import PTSLError
from .keys import parse_sequence, parse_combo, MODIFIERS

# Words that start a step. Everything else in a step is an option.
ACTIONS = [
    "activate", "menu", "press", "type", "wait", "wait for window", "wait for",
    "click", "checkbox", "popup", "set text", "click at", "raise window",
    "run macro", "note", "todo",
    "pro tools", "track color", "track colour", "select tracks",
    "midi cc", "open", "quit app", "close window", "slider", "metric slot", "metric ab", "bypass open plugin", "new track preset", "toggle open plugin active", "remove open plugin", "plugin preset", "metric button",
    "plugin window", "insert plugin", "send", "output", "input", "remove inactive",
    "open session folder", "if window", "accept dialog", "track menu", "paste", "import io settings", "set buffer size", "bounce dialog", "convert pro-q 3 to 4", "compact inserts", "toggle tce trim", "clear", "bypass plugin", "toggle plugin active",
    "audiosuite", "audiosuite preset", "audiosuite render",
    "save new version", "delete empty audio tracks", "bounce mix",
]
OPTIONS = {
    "window", "group", "path", "kind", "set", "choose", "to", "times", "gone",
    "timeout", "optional", "button", "double", "modifiers", "relative to", "element",
    "mouse", "typing", "pause", "body", "tracks",
    "app", "value", "channel", "port", "category", "source", "bits", "sample rate",
    "folder", "offline", "keep window", "source type", "track", "slot", "all selected", "scope", "scale",
    "name", "click bounce", "then", "else", "all", "or", "processing", "if empty", "stereo",
}

DEFAULT_TIMEOUT = 5.0        # how long to keep looking for a button/checkbox/etc.
WINDOW_TIMEOUT = 15.0        # how long "wait for window" waits
POLL = 0.05


class MacroError(Exception):
    pass


def slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "macro"


def seconds(v) -> float:
    """0.5, '500ms', '2s', '2 sec' -> seconds."""
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"^\s*([\d.]+)\s*(ms|s|sec|secs|seconds?)?\s*$", str(v).lower())
    if not m:
        raise MacroError(f"Can't understand the time '{v}'. Use e.g. 0.5, 500ms or 2s")
    n = float(m.group(1))
    return n / 1000 if m.group(2) == "ms" else n


REBUILT_MARK = "# Rebuilt for PT Deck"
EDITED_MARK = "# Edited by you (started from PT Deck's rebuilt version)"


def next_version_name(name: str) -> str:
    """'Song.01' -> 'Song.02', 'Song.09' -> 'Song.10', 'Song' -> 'Song.01'.
    Only a dot and number at the very end counts as the version."""
    base = name[:-4] if name.lower().endswith(".ptx") else name
    m = re.match(r"^(.*\.)(\d+)$", base)
    if not m:
        return f"{base}.01"
    digits = m.group(2)
    return f"{m.group(1)}{int(digits) + 1:0{len(digits)}d}"


class Library:
    """All macros in the macros folder. Re-read on every lookup so edits apply instantly."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        # Hand-rebuilt macros that come with PT Deck. A file with the same name in
        # 'macros' wins, so your own edits always take priority.
        self.rebuilt = self.folder.parent / "rebuilt"

    def files(self) -> list[Path]:
        own = sorted(self.folder.glob("*.yaml")) + sorted(self.folder.glob("*.yml"))
        if self.rebuilt.is_dir() and self.rebuilt != self.folder:
            # A rebuilt macro replaces a raw SoundFlow import of the same name,
            # but never a macro you've written or edited yourself.
            rebuilt_files = {p.name for p in self.rebuilt.glob("*.yaml")}
            rebuilt_names = set()
            for p in self.rebuilt.glob("*.yaml"):
                m = re.search(r"(?m)^name:\s*(.+?)\s*$", p.read_text(encoding="utf-8", errors="ignore"))
                if m:
                    rebuilt_names.add(m.group(1).strip("'\"").lower())

            def replaced(p):
                text = p.read_text(encoding="utf-8", errors="ignore")
                if text.startswith(REBUILT_MARK) and p.name in rebuilt_files:
                    return True              # an old copy of a rebuilt macro: the current version wins
                if not text.startswith("# Imported from SoundFlow"):
                    return False
                m = re.search(r"(?m)^name:\s*(.+?)\s*$", text)
                return p.name in rebuilt_files or bool(m and m.group(1).strip("'\"").lower() in rebuilt_names)
            own = [p for p in own if not replaced(p)]
        names = {p.name for p in own}
        extra = [p for p in sorted(self.rebuilt.glob("*.yaml")) if p.name not in names] \
            if self.rebuilt.is_dir() and self.rebuilt != self.folder else []
        return own + extra

    def load(self, path: Path) -> dict:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            raise MacroError(f"{path.name} has a formatting mistake: {e}") from None
        if isinstance(data, list):
            data = {"steps": data}
        data.setdefault("name", path.stem)
        data.setdefault("steps", [])
        data["_file"] = path
        return data

    def all(self) -> list[dict]:
        return [self.load(p) for p in self.files()]

    def get(self, name: str) -> dict:
        want = str(name).strip().lower()
        for p in self.files():
            if p.stem.lower() == want or p.stem.lower() == slug(want):
                return self.load(p)
        for m in self.all():
            if str(m["name"]).strip().lower() == want:
                return m
        raise MacroError(f"No macro called '{name}' in the macros folder. "
                         f"If it's a SoundFlow command, import it too (see README).")


def step_action(step) -> tuple[str, object]:
    if isinstance(step, str):
        step = {step: None}
    if not isinstance(step, dict):
        raise MacroError(f"Step isn't understood: {step!r}")
    found = [k for k in step if str(k).lower() in ACTIONS]
    if len(found) != 1:
        unknown = [k for k in step if str(k).lower() not in ACTIONS and str(k).lower() not in OPTIONS]
        if unknown:
            raise MacroError(f"Unknown word '{unknown[0]}' in step {step!r}")
        raise MacroError(f"Each step needs exactly one action (like click, press, menu): {step!r}")
    return str(found[0]).lower(), step[found[0]]


def validate(macro: dict, library: Library | None = None) -> list[str]:
    """Problems in a macro without running it."""
    problems = []
    for i, step in enumerate(macro["steps"], 1):
        try:
            action, value = step_action(step)
            opts = {str(k).lower(): v for k, v in step.items()} if isinstance(step, dict) else {}
            bad = [k for k in opts if k not in OPTIONS and k not in ACTIONS]
            if bad:
                problems.append(f"step {i}: unknown option '{bad[0]}'")
            if action == "if window":
                for branch in ("then", "else"):
                    problems += [f"step {i} ({branch}) {p}" for p in
                                 validate({"steps": opts.get(branch) or []}, library)]
            if action == "todo":
                problems.append(f"step {i}: needs converting by hand: {value}")
            elif action == "press":
                parse_sequence(value)
            elif action == "wait":
                seconds(value)
            elif action == "run macro" and library is not None:
                library.get(value)
            if opts.get("kind"):
                E.kind_role(opts["kind"])
        except Exception as e:  # noqa: BLE001 - report everything
            problems.append(f"step {i}: {e}")
    return problems


class Runner:
    """Runs macros against a 'system' (the real Mac, or a fake one in tests)."""

    def __init__(self, system, library: Library, log=print, step_pause: float = 0.0):
        self.sys = system
        self.lib = library
        self.log = log
        self.step_pause = step_pause
        self._opened = set()      # plug-in windows this macro opened (for set: restore)

    # ----- public -----
    def run(self, name: str, _depth: int = 0):
        if _depth > 10:
            raise MacroError("Macros are calling each other in a loop")
        macro = self.lib.get(name)
        if _depth == 0:
            self._opened = set()       # 'set: restore' only undoes what this press opened
            self._btn_cache = None     # ask Pro Tools afresh: a slot may have changed since last time
        self.log(f"▶ {macro['name']}")
        self._run_steps(macro["steps"], macro["name"], _depth)
        self.log(f"✓ {macro['name']}")

    def _run_steps(self, steps, macro_name, depth, prefix=""):
        for i, step in enumerate(steps or [], 1):
            action, value = step_action(step)
            opts = {str(k).lower(): v for k, v in step.items()} if isinstance(step, dict) else {}
            self._target = opts.get("app")
            label = f"{prefix}{i}"
            if action not in ("note",):
                shown = "" if value is None else f": {value}"
                self.log(f"  {label}. {action}{shown}"[:120])
            try:
                if action == "if window":
                    self._if_window(value, opts, macro_name, depth, label)
                else:
                    self.do(action, value, opts, depth)
            except (E.NotFound, MacroError, ValueError, PTSLError, RuntimeError) as e:
                if opts.get("optional"):
                    self.log(f"  step {label} skipped (optional): {e}")
                    continue
                if isinstance(e, MacroError) and str(e).startswith(f"'{macro_name}' stopped"):
                    raise
                raise MacroError(f"'{macro_name}' stopped at step {label} ({action}): {e}") from None
            pause = opts.get("pause", self.step_pause)
            if pause:
                self.sys.sleep(seconds(pause))

    def _if_window(self, v, o, macro_name, depth, label):
        """if window: Batch Fades   then: [steps]   else: [steps]
        Waits briefly (timeout, default 3s) for any window; runs 'then' if it's the named one."""
        timeout = seconds(o.get("timeout", 3))
        others = o.get("or") or []
        others = others if isinstance(others, list) else [others]

        def which():
            try:
                E.find_window(self.app(), v)
                return True
            except E.NotFound:
                pass
            for alt in others:              # one of the other expected windows: decide now
                try:
                    E.find_window(self.app(), alt)
                    return False
                except E.NotFound:
                    pass
            raise E.NotFound(f"window '{v}'")
        try:
            found = self.until(which, timeout, f"window '{v}'")
        except E.NotFound:
            found = False
        branch = o.get("then") if found else o.get("else")
        self.log(f"    window '{v}' {'is' if found else 'is not'} open")
        self._run_steps(branch or [], macro_name, depth, prefix=f"{label}.")

    # ----- helpers -----
    _target = None   # another app's bundle id for this step ("app:" option)

    def app(self):
        return self.sys.app(self._target) if self._target else self.sys.app()

    def until(self, fn, timeout: float, what: str):
        """Keep trying fn() until it works or time runs out."""
        end = self.sys.now() + timeout
        last = None
        while True:
            try:
                return fn()
            except E.NotFound as e:
                last = e
            if self.sys.now() >= end:
                raise E.NotFound(f"{last or what} (waited {timeout:g}s)")
            self.sys.sleep(POLL)

    def element(self, o: dict, name, kind=None):
        timeout = seconds(o.get("timeout", DEFAULT_TIMEOUT))
        kind = o.get("kind", kind)
        return self.until(
            lambda: E.resolve(self.app(), o.get("window"), o.get("group"), o.get("path"), kind, name),
            timeout, f"{kind or 'element'} '{name}'")

    PRESS_WAIT = 0.6     # how long to wait for Pro Tools to confirm a button press

    def press_el(self, el, mouse=False):
        """Press a button. Pro Tools can take up to 3 seconds to confirm some presses, so the
        press runs in the background: if it hasn't confirmed within PRESS_WAIT, carry on
        (the press has been delivered; Pro Tools handles it in order)."""
        if not mouse:
            import threading
            result, done = [None], threading.Event()

            def go():
                try:
                    result[0] = el.perform("AXPress")
                finally:
                    done.set()
            threading.Thread(target=go, daemon=True).start()
            if not done.wait(self.PRESS_WAIT) or result[0]:
                return
        x, y = self.center(el)
        self.sys.click(x, y)

    def center(self, el):
        pos, size = el.attr("AXPosition"), el.attr("AXSize")
        if not pos or not size:
            raise MacroError(f"Can't tell where {E.describe(el)} is on screen")
        return pos[0] + size[0] / 2, pos[1] + size[1] / 2

    # ----- actions -----
    def do(self, action, v, o, depth):
        if action in ("note", "todo"):
            if action == "todo":
                raise MacroError(f"this step still needs converting by hand: {v}")
            return
        if action == "activate":
            self.sys.activate()
        elif action == "menu":
            self.menu(v, o)
        elif action == "press":
            times = int(o.get("times", 1))
            for _ in range(times):
                for code, flags in parse_sequence(v):
                    self.sys.key(code, flags)
        elif action == "type":
            self.sys.type_text(str(v))
        elif action == "paste":
            self.sys.paste(str(v))
        elif action == "wait":
            self.sys.sleep(seconds(v))
        elif action == "wait for window":
            self.wait_window(v, o)
        elif action == "wait for":
            self.wait_element(v, o)
        elif action == "click":
            if o.get("all"):            # every match in the window (e.g. each 'Equal Power' option)
                win = self.until(lambda: E.find_window(self.app(), o.get("window")),
                                 seconds(o.get("timeout", DEFAULT_TIMEOUT)), "the window")
                hits = E.find_all(win, E.kind_role(o.get("kind")), v)
                if not hits:
                    raise E.NotFound(f"'{v}' in window '{o.get('window')}'")
                for h in hits:
                    self.press_el(h, mouse=bool(o.get("mouse")))
            else:
                self.press_el(self.element(o, v), mouse=bool(o.get("mouse")))
        elif action == "checkbox":
            self.checkbox(v, o)
        elif action == "popup":
            self.popup(v, o)
        elif action == "set text":
            self.set_text(v, o)
        elif action == "click at":
            self.click_at(v, o)
        elif action == "raise window":
            w = self.until(lambda: E.find_window(self.app(), v), seconds(o.get("timeout", DEFAULT_TIMEOUT)), v)
            w.perform("AXRaise")
        elif action == "run macro":
            self.run(v, depth + 1)
        elif action == "pro tools":
            self.sys.ptsl().run(v, o.get("body") or {})
        elif action == "midi cc":
            self.sys.midi_cc(str(o.get("port", "")), int(o.get("channel", 1)), int(v), int(o.get("value", 127)))
        elif action == "open":
            self.sys.open(str(v))
        elif action == "quit app":
            self.sys.quit_app(str(v))
        elif action == "close window":
            w = self.until(lambda: E.find_window(self.app(), v), seconds(o.get("timeout", DEFAULT_TIMEOUT)), v)
            btn = w.attr("AXCloseButton")
            if btn is None or not btn.perform("AXPress"):
                raise MacroError(f"couldn't close window '{v}'")
        elif action == "bounce dialog":
            self.bounce_dialog(o)
        elif action == "set buffer size":
            self.set_buffer_size(v)
        elif action == "import io settings":
            self.import_io_settings(v, o)
        elif action == "toggle tce trim":
            self.toggle_tce_trim()
        elif action == "compact inserts":
            self.compact_inserts(o)
        elif action == "convert pro-q 3 to 4":
            from . import proq
            proq.convert(self, v, o)
        elif action == "track menu":
            self.track_menu(v, o)
        elif action == "accept dialog":
            self.accept_dialog(o)
        elif action == "open session folder":
            import posixpath
            _, path = self.session_info()
            self.sys.open(posixpath.join(posixpath.dirname(path), str(v or "")))
        elif action == "plugin window":
            self.plugin_window(v, o)
        elif action == "insert plugin":
            self.insert_plugin(v, o)
        elif action in ("send", "output", "input"):
            self.assign(action, v, o)
        elif action == "remove inactive":
            self.remove_inactive(v, o)
        elif action == "clear":
            self.clear_slots(v, o)
        elif action in ("bypass plugin", "toggle plugin active"):
            self.plugin_click(action, v, o)
        elif action == "slider":
            self.slider(v, o)
        elif action == "metric slot":
            self.metric_slot(v, o)
        elif action == "metric ab":
            self.metric_ab(v, o)
        elif action == "bypass open plugin":
            self.bypass_open_plugin(v, o)
        elif action == "new track preset":
            self.new_track_preset(v, o)
        elif action == "toggle open plugin active":
            self.toggle_open_plugin_active(v, o)
        elif action == "remove open plugin":
            self.remove_open_plugin(v, o)
        elif action == "plugin preset":
            self.plugin_preset(v, o)
        elif action == "metric button":
            self.metric_button(v, o)
        elif action == "audiosuite":
            self.audiosuite_open(str(v), o)
        elif action == "audiosuite preset":
            self.audiosuite_preset(v, o)
        elif action == "audiosuite render":
            self.audiosuite_render(o)
        elif action == "save new version":
            self.save_new_version()
        elif action == "delete empty audio tracks":
            self.delete_empty_audio_tracks(o)
        elif action == "bounce mix":
            self.bounce_mix(v, o)
        elif action in ("track color", "track colour"):
            self.track_colour(v, o)
        elif action == "select tracks":
            names = self.sys.ptsl().tracks(v)
            if not names:
                raise PTSLError(f"no tracks match {v!r}")
            self.sys.ptsl().run("SelectTracksByName", {"track_names": names,
                                                        "selection_mode": "SMode_Replace"})

    def metric_slot(self, v, o):
        """metric slot: B2 — pick a MetricAB reference slot (its window must be open).
        Clicks the slot once, like you would. (Pro Tools ignores setting the slot number
        directly, and stepping through the slots in between flips A/B on every step.)"""
        from . import metric, settings
        base = self.lib.folder.parent
        col, row = metric.parse_slot(v)
        win = self.until(lambda: E.find_window(self.app(), o.get("window", "Plug-in: ADPTR MetricAB*")),
                         seconds(o.get("timeout", DEFAULT_TIMEOUT)), "the MetricAB window")
        track = E.find_one(win, "slider", "Selected Track")
        group = E.find_one(win, "group", "FXTDMEditView")

        def current():
            try:
                return int(round(float(track.attr("AXValue"))))
            except (TypeError, ValueError):
                return None
        before = current()
        x, y = metric.cell_center(group.attr("AXPosition"), group.attr("AXSize"), col, row)
        mouse = self.sys.mouse_position() if hasattr(self.sys, "move_mouse") else None
        for attempt in range(2):
            self.sys.click(x, y)
            for _ in range(10):
                self.sys.sleep(0.04)
                if current() != before:
                    break
            if current() != before or attempt:
                break
            self.sys.sleep(0.3)        # window only just opened: give it a moment, then once more
        if mouse:
            self.sys.move_mouse(*mouse)      # put the pointer back where it was
        after = current()
        self.log(f"    clicked {metric.slot_name(col, row)}: slot number {before} -> {after}"
                 f" (playing {metric.ab_from(E.find_one(win, 'slider', 'AB Switch'))})")
        if after is not None and after != before:
            # Learn how MetricAB counts its slots from where we clicked.
            for how in ("rows", "columns"):
                if metric.index_of(col, row, how) == after and how != metric.order(base) and col != row:
                    settings.put(base, "metric order", how)
        settings.put(base, "metric selected", metric.slot_name(col, row))
        try:
            settings.put(base, "metric ab", metric.ab_from(E.find_one(win, "slider", "AB Switch")))
        except E.NotFound:
            pass

    TRACK_TYPES = ("audio track", "aux input", "instrument track", "midi track", "vca master",
                   "folder", "basic folder", "routing folder", "master fader", "video track", "track presets")

    def new_track_preset(self, v, o):
        """new track preset: INSTRUMENTS > SD3 — Track > New, type 'Track Presets', pick the
        category and preset, then Create (count: 1 by default)."""
        parts = [p.strip() for p in str(v).split(">") if p.strip()]
        if len(parts) < 2:
            raise MacroError("new track preset needs 'Category > Preset', e.g. INSTRUMENTS > SD3")
        category, preset = parts[:-1], parts[-1]
        self.sys.activate()
        self.sys.key(*parse_combo("shift+cmd+n"))
        win = self.until(lambda: E.find_window(self.app(), "New Tracks"), DEFAULT_TIMEOUT, "the New Tracks window")

        def popups():
            return [p for p in E.find_all(win, "AXPopUpButton", "*", max_depth=3)]
        kind = next((p for p in popups() if str(E.labels(p)[0] if E.labels(p) else "").lower() in self.TRACK_TYPES
                     or str(p.attr("AXValue") or p.attr("AXTitle") or "").lower() in self.TRACK_TYPES), None)
        if kind is None:
            raise MacroError("couldn't find the track type pop-up in New Tracks")
        before = {id(p): str(p.attr("AXTitle") or p.attr("AXValue") or "") for p in popups()}
        names_before = set(before.values())
        self.choose_from(kind, ["Track Presets", *category])
        self.sys.sleep(0.5)
        # The preset list is a pop-up that's new or changed since we picked the category.
        cands = [p for p in popups() if str(p.attr("AXTitle") or p.attr("AXValue") or "") not in names_before
                 and str(p.attr("AXTitle") or p.attr("AXValue") or "").lower() != category[-1].lower()]
        cands += [p for p in popups() if p not in cands]
        last = None
        for p in cands:
            if str(p.attr("AXTitle") or p.attr("AXValue") or "") == preset:
                last = None
                break
            try:
                self.choose_from(p, [preset])
                self.sys.sleep(0.2)
                if any(str(q.attr("AXTitle") or q.attr("AXValue") or "") == preset for q in popups()):
                    last = None
                    break
            except Exception as e:  # noqa: BLE001 - not this pop-up: try the next
                last = e
                self.sys.key(*parse_combo("escape"))
                self.sys.sleep(0.2)
        else:
            raise MacroError(f"couldn't find the track preset '{preset}' in New Tracks ({last})")
        self.log(f"    preset {' > '.join(category)} > {preset}")
        self.press_el(E.find_one(win, "button", "Create"))
        self.until(lambda: not self._window_open("New Tracks"), DEFAULT_TIMEOUT, "New Tracks to close")

    def _window_open(self, title):
        try:
            E.find_window(self.app(), title)
            return True
        except E.NotFound:
            return False

    def open_plugin(self, track=""):
        """(window, track, slot letter) of the open plug-in window for a track (any track if
        empty; the front one if there are several)."""
        for w in E.window_list(self.app()):
            if not str(w.attr("AXTitle") or "").startswith("Plug-in:"):
                continue
            try:
                on = str(E.find_one(w, "popup", "Track Selector").attr("AXValue") or "")
            except E.NotFound:
                on = ""
            if track and on != track:
                continue
            try:
                letter = str(E.find_one(w, "popup", "Insert Position selector").attr("AXValue") or "").strip().upper()
            except E.NotFound:
                letter = ""
            if on and letter in self.SLOTS:           # remember it, for when its window has gone
                self.remember_plugin(on, letter, str(w.attr("AXTitle"))[len("Plug-in: "):])
            return w, on, letter
        raise MacroError(f"no plug-in window is open{f' for {track}' if track else ''}")

    def bypass_open_plugin(self, v, o):
        """bypass open plugin: (PRINT) — presses Bypass in the plug-in window that's open for
        that track (the front one if there are several). Leave the value empty for any track."""
        win, on, _ = self.open_plugin(str(v or "").strip())
        self.press_el(E.find_one(win, "button", "Effect Bypass"))
        self.log(f"    bypass pressed on {str(win.attr('AXTitle'))[len('Plug-in: '):]} ({on})")

    def plugin_preset(self, v, o):
        """plugin preset: EAS NAM  (or 'Folder > Preset') — picks a preset from Pro Tools' own
        preset menu (the Librarian menu) in the open plug-in window."""
        want = [p.strip() for p in str(v).split(">") if p.strip()]
        pattern = str(o.get("window", "Plug-in:*"))

        def window():
            for w in E.window_list(self.app()):
                if E.name_matches(w, pattern) or str(w.attr("AXTitle") or "").startswith(pattern.rstrip("*")):
                    return w
            raise E.NotFound(f"a window '{pattern}'")
        win = self.until(window, seconds(o.get("timeout", DEFAULT_TIMEOUT)), "the plug-in window")
        lib = self.until(lambda: E.find_one(win, "popup", "Librarian menu"), DEFAULT_TIMEOUT, "its preset menu")
        if E.norm(lib.attr("AXValue")) == E.norm(want[-1]):
            self.log(f"    preset '{want[-1]}' is already loaded")
            return
        self.choose_from(lib, want)

        def loaded():
            if E.norm(lib.attr("AXValue")) != E.norm(want[-1]):
                raise E.NotFound("the preset to load")
            return True
        try:
            self.until(loaded, 3, "the preset to load")
        except E.NotFound:
            raise MacroError(f"the preset '{want[-1]}' didn't load (shows '{lib.attr('AXValue')}')") from None
        self.log(f"    preset '{want[-1]}' loaded")

    def remember_plugin(self, track, letter, name):
        """Note the plug-in you last opened (by insert key or window), for Active/Inactive and
        Remove: an inactive plug-in's window doesn't say which track and slot it's on."""
        from . import settings
        if track and letter in self.SLOTS and name not in ("", "unassigned"):
            settings.put(self.lib.folder.parent, "last plugin", {"track": track, "slot": letter, "name": name})

    def plugin_target(self, v):
        """(window or None, track, slot letter, name) for the open plug-in; when its window can't
        tell us (inactive plug-ins open a small window without the track and slot), the plug-in
        you last opened with an insert key."""
        from . import settings
        try:
            win, track, letter = self.open_plugin(str(v or "").strip())
            if track and letter in self.SLOTS:
                return win, track, letter, str(win.attr("AXTitle"))[len("Plug-in: "):]
        except MacroError:
            win = None
        last = settings.get(self.lib.folder.parent, "last plugin") or {}
        if not last.get("track"):
            raise MacroError("open a plug-in first (with its insert key)")
        self.log(f"    using the plug-in you last opened: {last.get('name')} on {last['track']} slot {last['slot']}")
        return win, last["track"], last["slot"], last.get("name", "")

    def open_plugin_slot(self, v, o):
        win, track, letter, _ = self.plugin_target(v)
        return win, track, letter

    def _prepare_slot_click(self, win, track, name):
        """Before clicking a slot for Active/Inactive or Remove: close the plug-in's window (it
        can float over the slot) and scroll the Edit window to the track, (PRINT) included."""
        for w in [win] + [x for x in E.window_list(self.app())
                          if str(x.attr("AXTitle") or "").startswith("Plug-in:") and x is not win]:
            if w is None:
                continue
            if w is win or (name and name in str(w.attr("AXTitle") or "")):
                close = w.attr("AXCloseButton")
                if close is not None:
                    close.perform("AXPress")
                    self.sys.sleep(0.3)
        self._btn_cache = None
        try:
            header = self.track_header(track, "Inserts A-E", "Inserts F-J")
            sel, _ = self.slot_buttons(header, "Insert", self._target_letter)
            in_view = self._slot_in_view(sel)
        except Exception:  # noqa: BLE001
            in_view = False
        if not in_view:                       # e.g. (PRINT) scrolled out of view
            try:
                self.scroll_into_view(track, lambda: self.slot_buttons(self.track_header(track, "Inserts A-E", "Inserts F-J"), "Insert", self._target_letter)[0])
            except Exception as e:  # noqa: BLE001 - carry on: the click may still land
                self.log(f"    (couldn't scroll to {track}: {e})")
            self._btn_cache = None

    def toggle_open_plugin_active(self, v, o):
        """toggle open plugin active: — makes the open plug-in inactive (or active again).
        Pro Tools closes a plug-in's window when it goes inactive, so with no window open this
        works on the last plug-in that had one."""
        win, track, letter, name = self.plugin_target(v)
        self._target_letter = letter
        self._prepare_slot_click(win, track, name)
        header = self.track_header(track, "Inserts A-E", "Inserts F-J")
        before, asg = self._try_slot(header, "Insert", letter)
        before = str(before or "")
        if asg is None or str(asg.attr("AXValue") or "") == "unassigned":
            raise MacroError(f"{track} slot {letter} is empty now")
        self.plugin_click("toggle plugin active", letter, {"track": track})
        self.sys.sleep(0.2)
        self._btn_cache = None
        after = str(self._try_slot(self.track_header(track, "Inserts A-E", "Inserts F-J"), "Insert", letter)[0] or "")
        self.log(f"    {name} on {track} slot {letter}: {before or 'active'} -> {after or 'active'}")
        if before == after and after != "open":
            raise MacroError(f"{name} on {track} didn't change (still {after or 'active'})")

    def remove_open_plugin(self, v, o):
        """remove open plugin: — takes the open plug-in out of its slot ('no insert')."""
        win, track, letter, name = self.plugin_target(v)
        self._target_letter = letter
        self._prepare_slot_click(win, track, name)
        header = self.track_header(track, "Inserts A-E", "Inserts F-J")
        sel, asg = self.slot_buttons(header, "Insert", letter)
        self.log(f"    removing {name} from {track} slot {letter} (slot shows {asg.attr('AXValue')!r})")
        def slot_now():
            self._btn_cache = None
            return str(self.slot_buttons(self.track_header(track, "Inserts A-E", "Inserts F-J"), "Insert",
                                         letter)[1].attr("AXValue") or "")
        try:
            self.choose_from(sel, ["no insert"])
        except (E.NotFound, MacroError) as e:
            self.log(f"    menu pick didn't work ({e})")
        self.sys.sleep(0.3)
        if slot_now() != "unassigned":
            # Inactive and bypassed plug-ins ignore a menu pick made behind Pro Tools' back:
            # do it with the mouse, like you would — click the slot, then click 'no insert'.
            self.log("    trying again with real clicks")
            self.sys.key(*parse_combo("escape"))
            self.sys.sleep(0.2)
            self.mouse_choose(track, letter, "no insert")
            self.sys.sleep(0.3)
        now = slot_now()
        if now != "unassigned":
            raise MacroError(f"{name} is still in {track} slot {letter} (shows {now!r})")
        self.log(f"    removed {name} from {track} slot {letter}")

    def mouse_choose(self, track, letter, item):
        """Open an insert slot's menu with a real click and click one of its items (the item
        nearest the slot, so menus left over from earlier don't get in the way)."""
        header = self.track_header(track, "Inserts A-E", "Inserts F-J")
        sel, _ = self.slot_buttons(header, "Insert", letter)
        if not self._slot_in_view(sel):
            self.scroll_into_view(track, lambda: self.slot_buttons(self.track_header(track, "Inserts A-E", "Inserts F-J"), "Insert", letter)[0])
            header = self.track_header(track, "Inserts A-E", "Inserts F-J")
            sel, _ = self.slot_buttons(header, "Insert", letter)
        self.sys.activate()
        x, y = self.center(sel)
        self.sys.click(x, y)
        end = self.sys.now() + 2.0
        while self.sys.now() < end:
            self.sys.sleep(0.1)
            best = None
            for w in E.children(self.app()):
                if not self._is_menu_window(w):
                    continue
                for it in E.find_all(w, "AXMenuItem", item, max_depth=2):
                    try:
                        ix, iy = self.center(it)
                    except Exception:  # noqa: BLE001 - not on screen
                        continue
                    dist = abs(ix - x) + abs(iy - y)
                    if best is None or dist < best[0]:
                        best = (dist, ix, iy)
            if best:
                self.sys.click(best[1], best[2])
                return
        self.sys.key(*parse_combo("escape"))
        raise MacroError(f"the slot's menu didn't show '{item}'")

    def metric_button(self, v, o):
        """metric button: sides | match | match all — clicks that MetricAB button (its window must
        be open) and checks the plug-in's setting changed (Sides and Match are toggles)."""
        from . import metric, settings
        which = str(v or "").strip().lower()
        if which not in metric.BUTTONS:
            raise MacroError(f"metric button should be one of: {', '.join(metric.BUTTONS)} (got {v!r})")
        win = self.until(lambda: E.find_window(self.app(), o.get("window", "Plug-in: ADPTR MetricAB*")),
                         seconds(o.get("timeout", DEFAULT_TIMEOUT)), "the MetricAB window")
        group = E.find_one(win, "group", "FXTDMEditView")
        try:
            slider = E.find_one(win, "slider", metric.BUTTONS[which][1])
        except E.NotFound:
            slider = None
        toggle = which in ("sides", "match") and slider is not None
        before = metric.is_on(which, slider) if toggle else None
        x, y = metric.button_center(group.attr("AXPosition"), group.attr("AXSize"), which)
        mouse = self.sys.mouse_position() if hasattr(self.sys, "move_mouse") else None
        for attempt in range(2 if toggle else 1):
            self.sys.click(x, y)
            if not toggle:
                break
            for _ in range(10):
                self.sys.sleep(0.04)
                if metric.is_on(which, slider) != before:
                    break
            if metric.is_on(which, slider) != before:
                break
            self.sys.sleep(0.3)        # window only just opened: give it a moment, then once more
        if mouse:
            self.sys.move_mouse(*mouse)
        if toggle:
            after = metric.is_on(which, slider)
            settings.put(self.lib.folder.parent, f"metric {which}", after)
            self.log(f"    {which}: {'on' if before else 'off'} -> {'on' if after else 'off'}")
            if after == before:
                raise MacroError(f"MetricAB's {which.title()} button didn't switch")
        else:
            self.log(f"    {which}: clicked")

    def metric_ab(self, v, o):
        """metric ab: toggle | A | B — clicks MetricAB's big A|B button (its window must be open).
        Its A/B setting only moves a tiny bit per step, so stepping can't switch it."""
        from . import metric, settings
        want = str(v or "toggle").strip().upper()
        win = self.until(lambda: E.find_window(self.app(), o.get("window", "Plug-in: ADPTR MetricAB*")),
                         seconds(o.get("timeout", DEFAULT_TIMEOUT)), "the MetricAB window")
        switch = E.find_one(win, "slider", "AB Switch")
        group = E.find_one(win, "group", "FXTDMEditView")
        before = metric.ab_from(switch)
        if want in ("A", "B") and want == before:
            self.log(f"    already playing {before}")
            return
        target = "B" if before == "A" else "A"
        x, y = metric.ab_center(group.attr("AXPosition"), group.attr("AXSize"), target)
        mouse = self.sys.mouse_position() if hasattr(self.sys, "move_mouse") else None
        for attempt in range(2):
            self.sys.click(x, y)
            for _ in range(10):
                self.sys.sleep(0.04)
                if metric.ab_from(switch) != before:
                    break
            if metric.ab_from(switch) != before or attempt:
                break
            self.sys.sleep(0.3)        # window only just opened: give it a moment, then once more
        if mouse:
            self.sys.move_mouse(*mouse)
        after = metric.ab_from(switch)
        self.log(f"    A/B: {before} -> {after}")
        settings.put(self.lib.folder.parent, "metric ab", after)
        if after == before:
            raise MacroError("MetricAB's A/B button didn't switch")

    def slider(self, v, o):
        """Plug-in controls: set: toggle | up | down | a number."""
        el = self.element(o, v, kind=o.get("kind", "slider"))
        want = str(o.get("set", "toggle")).lower()
        if want == "up":
            el.perform("AXIncrement")
        elif want == "down":
            el.perform("AXDecrement")
        elif want == "toggle":
            cur, low = float(el.attr("AXValue") or 0), float(el.attr("AXMinValue") or 0)
            el.perform("AXIncrement" if cur <= low + 1e-6 else "AXDecrement")
            if str(v) == "AB Switch" and "MetricAB" in str(o.get("window", "")):
                # Tell the deck's A/B key straight away (even if the window closes next).
                from . import metric, settings
                self.sys.sleep(0.05)
                settings.put(self.lib.folder.parent, "metric ab", metric.ab_from(el))
        else:
            try:
                target = float(want)
            except ValueError:
                raise MacroError(f"slider 'set' should be toggle, up, down or a number (got {want!r})") from None
            self.set_slider(el, v, target)

    def set_slider(self, el, name, target):
        """Set a plug-in control to a number and check it took. If Pro Tools ignores the
        direct setting, step it up/down one notch at a time instead."""
        def now():
            try:
                return float(el.attr("AXValue"))
            except (TypeError, ValueError):
                return None
        before = now()
        self.log(f"    '{name}' is {before if before is None else f'{before:g}'}, setting {target:g}")
        if before is not None and abs(before - target) < 0.5:
            return
        el.set_attr("AXValue", target)
        for _ in range(10):
            self.sys.sleep(0.03)
            if (cur := now()) is not None and abs(cur - target) < 0.5:
                self.log(f"    '{name}' is now {cur:g}")
                return
        cur = now()
        self.log(f"    '{name}' ignored the direct setting (still {cur}); stepping instead")
        for _ in range(64):
            if cur is None or abs(cur - target) < 0.5:
                break
            el.perform("AXIncrement" if cur < target else "AXDecrement")
            self.sys.sleep(0.03)
            nxt = now()
            if nxt == cur:          # didn't move: wait a moment once more
                self.sys.sleep(0.15)
                nxt = now()
                if nxt == cur:
                    break
            cur = nxt
        if cur is None or abs(cur - target) >= 0.5:
            raise MacroError(f"couldn't set '{name}' to {target:g} (it's {cur})")
        self.log(f"    '{name}' is now {cur:g}")

    # ----- track headers in the Edit window -----
    SLOTS = "ABCDEFGHIJ"

    def edit_window(self):
        return self.until(lambda: E.find_window(self.app(), "Edit:*"), DEFAULT_TIMEOUT, "the Edit window")

    VIEW_GROUPS = {"I/O": "*IO"}      # Edit window view -> the group it adds to each track

    def track_header(self, track, *views):
        """The track's header in the Edit window. Any 'views' (e.g. 'Sends A-E') that aren't
        showing are switched on first, but only if they're actually missing."""
        pattern = re.sub(r"([*?\[])", r"[\1]", str(track)) + " - * Track"

        def find():
            # The Edit window first; if it's closed or the track isn't there, the Mix window's strip.
            for title in ("Edit:*", "Mix:*"):
                try:
                    win = E.find_window(self.app(), title)
                except E.NotFound:
                    continue
                for c in E.children(win):           # track headers / strips sit directly in the window
                    if c.attr("AXRole") == "AXGroup" and E.name_matches(c, pattern):
                        return c
                try:
                    return E.find_one(win, "group", pattern)
                except E.NotFound:
                    continue
            raise E.NotFound(f"track '{track}'")
        header = self.until(find, 3.0, f"track '{track}' in the Edit or Mix window (is it shown?)")
        missing = [v for v in views if not any(E.name_matches(c, self.VIEW_GROUPS.get(v, v))
                                               for c in E.children(header) if c.attr("AXRole") == "AXGroup")]
        if missing and not str(header.attr("AXTitle") or "").endswith(("VCA Track", "Basic Folder Track")):
            self.log(f"    showing {', '.join(missing)} in the Edit window")
            self.show_views(*missing)
            self.sys.sleep(0.3)
            header = self.until(find, 3.0, f"track '{track}'")
        return header

    def target_tracks(self, o):
        """Track names from 'track:' / 'tracks:' (default: the selected tracks)."""
        which = o.get("track", o.get("tracks", "selected"))
        names = self.sys.ptsl().tracks(which) if str(which).lower() in ("selected", "all") else (
            which if isinstance(which, list) else [t.strip() for t in str(which).split(",") if t.strip()])
        if not names:
            raise MacroError("no tracks are selected")
        return names

    def slot_letter(self, slot):
        s = str(slot).strip().upper()
        if s.isdigit() and 1 <= int(s) <= 10:
            return self.SLOTS[int(s) - 1]
        if len(s) == 1 and s in self.SLOTS:
            return s
        raise MacroError(f"slot should be 1-10 or A-J (got {slot!r})")

    def _header_buttons(self, header):
        """All named buttons in a track header, found in one pass (much faster than searching per slot)."""
        cache = getattr(self, "_btn_cache", None)
        if cache and cache[0] == header:
            return cache[1]
        found = {}
        for grp in E.children(header):
            for b in E.children(grp):
                if b.attr("AXRole") == "AXButton":
                    for lab in E.labels(b):
                        found.setdefault(lab, b)
        self._btn_cache = (header, found)
        return found

    def slot_buttons(self, header, kind, letter):
        """(selector, assignment) buttons for an insert/send slot."""
        btns = self._header_buttons(header)
        sel, asg = btns.get(f"{kind} selector {letter}"), btns.get(f"{kind} Assignment {letter}")
        if sel is None or asg is None:
            sel = E.find_one(header, "button", f"{kind} selector {letter}")
            asg = E.find_one(header, "button", f"{kind} Assignment {letter}")
        return sel, asg

    def show_views(self, *views):
        for view in views:
            try:
                self.menu(f"View > Edit Window Views > {view}", {"set": "on"})
            except (E.NotFound, MacroError):
                pass

    def read_inserts(self, track):
        """{'A': (plug-in name, state), ...} for a track's inserts, as Pro Tools shows them.
        state: '' (active), 'inactive', 'bypassed', 'open' (window showing) or 'unassigned'.
        Read-only and quiet: never switches Edit window views."""
        header = self.track_header(track)
        out = {}
        for L in self.SLOTS:
            state, asg = self._try_slot(header, "Insert", L)
            if asg is not None:
                out[L] = (str(asg.attr("AXValue") or ""), str(state or ""))
        self._btn_cache = None
        # With its window open, a slot only says 'open': ask the window if it's bypassed.
        for L, (name, state) in out.items():
            if state == "open":
                b = self.open_window_bypassed(track, L)
                if b is not None:
                    out[L] = (name, "open bypassed" if b else "open active")
        return out

    def open_window_bypassed(self, track, letter):
        """True/False from the Bypass button of the open plug-in window for this track's insert
        (None if that window can't be found)."""
        try:
            wins = E.window_list(self.app())
        except Exception:  # noqa: BLE001
            return None
        for w in wins:
            if not str(w.attr("AXTitle") or "").startswith("Plug-in:"):
                continue
            try:
                on = str(E.find_one(w, "popup", "Track Selector").attr("AXValue") or "")
                slot = str(E.find_one(w, "popup", "Insert Position selector").attr("AXValue") or "")
                if on != track or slot.strip().upper() != letter:
                    continue
                v = E.find_one(w, "button", "Effect Bypass").attr("AXValue")
            except E.NotFound:
                continue
            # Pro Tools marks a pressed toggle as 'Selected' (nothing when it's off).
            return str(v or "").lower() in ("selected", "on", "1", "true", "bypassed")
        return None

    def find_plugin_slot(self, header, track, v):
        """Slot letter for a plug-in given by slot (8 / 'H') or by (part of) its name."""
        sv = str(v).strip()
        if isinstance(v, int) or sv.isdigit() or (len(sv) == 1 and sv.upper() in self.SLOTS):
            return self.slot_letter(v)
        for L in self.SLOTS:
            _, asg = self._try_slot(header, "Insert", L)
            if asg is not None and sv.lower() in str(asg.attr("AXValue") or "").lower():
                return L
        raise E.NotFound(f"plug-in '{v}' on track '{track}'")

    def plugin_window(self, v, o):
        """plugin window: ADPTR MetricAB  (or a slot: 8 / H)   track: -OUT MASTER   set: toggle|open|close|restore"""
        track = self.target_tracks(o)[0]
        header = self.track_header(track, "Inserts A-E", "Inserts F-J")
        letter = self.find_plugin_slot(header, track, v)
        sel, asg = self.slot_buttons(header, "Insert", letter)
        if str(asg.attr("AXValue") or "") == "unassigned":
            if str(o.get("if empty", "")).lower() in ("choose plug-in", "choose plugin", "choose", "menu"):
                # Open the slot's plug-in menu with ONE real click, like you would, and then
                # leave everything alone so it stays open: type to search, Return to add.
                # (A second click, or asking Pro Tools about the slot, would close it again.)
                self.sys.activate()
                self.sys.sleep(0.15)
                if not self._slot_in_view(sel):                  # scrolled out of view: bring it in
                    self.scroll_into_view(track, lambda: self.slot_buttons(self.track_header(track, "Inserts A-E", "Inserts F-J"), "Insert", letter)[0])
                    header = self.track_header(track, "Inserts A-E", "Inserts F-J")
                    sel, _ = self.slot_buttons(header, "Insert", letter)
                x, y = self.center(sel)
                self.hold_live_until = time.time() + 15      # the deck's live keys keep quiet until it closes (15s at most)
                self.sys.click(x, y)
                self.log(f"    insert {letter} on '{track}' is empty: plug-in menu open, type to search")
                return
            raise MacroError(f"insert {letter} on '{track}' is empty")
        self.remember_plugin(track, letter, str(asg.attr("AXValue") or ""))
        is_open = str(sel.attr("AXValue") or "") == "open"
        if not is_open and not str(v).strip().isdigit():
            # The plug-in's own window on screen is the surest sign it's open.
            try:
                E.find_window(self.app(), f"Plug-in: {v}*")
                is_open = True
            except E.NotFound:
                pass
        want = str(o.get("set", "toggle")).lower()
        key = (track, letter)
        self.log(f"    insert {letter} on '{track}': window {'open' if is_open else 'closed'}"
                 f" (selector says {str(sel.attr('AXValue') or '')!r})")
        if want == "restore":
            self.log("    closing it again" if key in self._opened and is_open else "    leaving it as it is")
            # Close it again only if an earlier step of this macro opened it.
            if key in self._opened and is_open:
                self._opened.discard(key)
                asg.perform("AXPress")
                self.sys.sleep(0.2)
            return
        if want == "toggle" or (want == "open") != is_open:
            asg.perform("AXPress")
            self.sys.sleep(0.3)
            if not is_open:
                self._opened.add(key)

    def menu_on_screen(self) -> bool:
        """Is one of Pro Tools' pop-up menus showing right now? (Only asks the app for its
        windows, which is safe while a menu is open; leftover invisible menus don't count.)"""
        try:
            return any(self._is_menu_window(w) and self._on_screen(w) for w in E.children(self.app()))
        except Exception:  # noqa: BLE001
            return False

    def scroll_into_view(self, track, get_el):
        """Bring a track's slot into view in the Edit window by scrolling the mouse wheel over
        it, re-checking where the slot is after each step (quick, no dialogs). get_el() finds
        the slot again (Pro Tools may rebuild it). Falls back to Track > Scroll to Track."""
        try:
            win = self.edit_window()
            (wx, wy), (ww, wh) = win.attr("AXPosition"), win.attr("AXSize")
        except Exception:  # noqa: BLE001
            return self.scroll_to_track(track)
        top, bottom = wy + wh * 0.25, wy + wh * 0.85       # aim for the middle of the tracks area
        mouse = self.sys.mouse_position() if hasattr(self.sys, "move_mouse") else None
        hx, hy = wx + ww * 0.6, wy + wh * 0.55              # wheel over the tracks
        sign, last = 1, None
        try:
            for _ in range(40):
                self._btn_cache = None
                el = get_el()
                if self._slot_in_view(el):
                    return
                _, y = self.center(el)
                dist = (top - y) if y < top else (bottom - y)       # + means it's above the view
                if last is not None and abs(dist) > abs(last) + 5:
                    sign = -sign                                     # went the wrong way: flip
                self.sys.scroll(hx, hy, sign * max(-900, min(900, dist)))
                last = dist
                self.sys.sleep(0.06)
        finally:
            if mouse:
                self.sys.move_mouse(*mouse)
        self._btn_cache = None
        if not self._slot_in_view(get_el()):
            self.log(f"    (wheel scrolling didn't reach {track}; trying Track > Scroll to Track)")
            self.scroll_to_track(track)

    def _slot_in_view(self, el) -> bool:
        """Is the element inside its window's visible area (so a mouse click would hit it)?"""
        try:
            x, y = self.center(el)
        except Exception:  # noqa: BLE001 - can't tell: assume it's fine
            return True
        frames = []
        for w in E.window_list(self.app()):
            if not str(w.attr("AXTitle") or "").startswith(("Edit:", "Mix:")):
                continue
            pos, size = w.attr("AXPosition"), w.attr("AXSize")
            if pos and size:
                frames.append((pos, size))
        if not frames:
            return True                      # no window size to go on: assume it's fine
        return any(wx <= x <= wx + ww and wy <= y <= wy + wh for (wx, wy), (ww, wh) in frames)

    def plugin_click(self, action, v, o):
        """bypass plugin: 1 (Cmd-click)  /  toggle plugin active: 10 (Cmd-Ctrl-click) on the selected track."""
        from .keys import CMD, CTRL
        flags = CMD if action == "bypass plugin" else CMD | CTRL
        for track in self.target_tracks(o):
            header = self.track_header(track, "Inserts A-E", "Inserts F-J")
            letter = self.find_plugin_slot(header, track, v)
            _, asg = self.slot_buttons(header, "Insert", letter)
            if str(asg.attr("AXValue") or "") == "unassigned":
                continue
            if not self._slot_in_view(asg):              # a mouse click needs the slot in view
                self.scroll_into_view(track, lambda: self.slot_buttons(self.track_header(track, "Inserts A-E", "Inserts F-J"), "Insert", letter)[1])
                header = self.track_header(track, "Inserts A-E", "Inserts F-J")
                _, asg = self.slot_buttons(header, "Insert", letter)
            x, y = self.center(asg)
            self.sys.click(x, y, flags=flags)
            self.sys.sleep(0.1)

    def insert_plugin(self, v, o):
        """insert plugin: Cabinetron   category: TBTECH   slot: 10 | first free | 2 or first free"""
        slot = str(o.get("slot", "first free")).lower().strip()
        m = re.fullmatch(r"(\w+)\s+or\s+first\s+free", slot)       # e.g. '2 or first free'
        for track in self.target_tracks(o):
            header = self.track_header(track, "Inserts A-E", "Inserts F-J")

            def first_free():
                letter = next((L for L in self.SLOTS
                               if str(self._try_slot(header, "Insert", L)[0]) == "unassigned"), None)
                if letter is None:
                    raise MacroError(f"no free insert slot on '{track}'")
                return letter
            if slot in ("first free", "firstfree", "free"):
                letter = first_free()
            elif m:
                letter = self.slot_letter(m.group(1))
                if str(self._try_slot(header, "Insert", letter)[0]) != "unassigned":
                    letter = first_free()
                    self.log(f"    slot {m.group(1)} is taken: using slot {self.SLOTS.index(letter) + 1}")
            else:
                letter = self.slot_letter(slot)
            sel, _ = self.slot_buttons(header, "Insert", letter)
            path = (["plug-in", str(o["category"]), str(v)] if o.get("category") else [str(v)])
            self.choose_from(sel, path, prefer="plug-in")
            self.sys.sleep(0.3)

    # Toolbar button name -> Pro Tools Scripting SDK tool (for putting a tool back).
    TOOL_IDS = {"Selector tool": "ET_Selector", "Grabber tool (Time)": "ET_GrabberTime",
                "Grabber tool (Separation)": "ET_GrabberSeparation", "Grabber tool (Object)": "ET_GrabberObject",
                "Zoomer tool": "ET_ZoomNormal", "Scrubber tool": "ET_Scrubber",
                "Pencil tool (Free Hand)": "ET_PencilFreeHand", "Pencil tool (Line)": "ET_PencilLine"}

    def _toolbar(self):
        """(trim button, smart button, all tool buttons) from the Edit window toolbar."""
        win = self.edit_window()
        cluster = next(iter(E.find_all(win, "AXGroup", "Cursor Tool Cluster", max_depth=2)), win)
        tools = [b for b in E.children(cluster) if b.attr("AXRole") == "AXButton"]
        trim = next((b for b in tools if "trim tool" in self._title(b).lower()), None)
        smart = next((b for b in tools if self._title(b).lower().startswith("smart tool")), None)
        return trim, smart, tools

    @staticmethod
    def _title(b):
        return (E.labels(b) or [""])[0]

    @staticmethod
    def _selected(b):
        return b is not None and str(b.attr("AXValue") or "") == "Selected"

    def toggle_tce_trim(self):
        """Switch the Trim tool between Standard and TCE, leaving Smart mode (or the selected
        tool) as it was. The Trim tool's name shows its mode: 'Trim tool' vs
        'Time Compression/Expansion Trim tool'. Afterwards the toolbar is checked, and Smart
        mode is corrected if Pro Tools changed it."""
        trim, smart, tools = self._toolbar()
        if trim is None:
            raise E.NotFound("the Trim tool in the Edit window toolbar")
        is_tce = "time compression" in self._title(trim).lower()
        smart_on = self._selected(smart)
        prev = None if smart_on else next((self._title(b) for b in tools if b is not trim and b is not smart
                                           and self._selected(b) and self._title(b) in self.TOOL_IDS), None)
        new_mode = "ET_TrimStandard" if is_tce else "ET_TrimTce"
        pt = self.sys.ptsl()
        pt.run("SetEditTool", {"edit_tool": new_mode})
        if smart_on:
            pt.run("SetEditTool", {"edit_tool": "ET_SmartTool"})
        elif prev:
            pt.run("SetEditTool", {"edit_tool": self.TOOL_IDS[prev]})
        # Check, and put Smart mode back if Pro Tools changed it.
        for attempt in range(3):
            self.sys.sleep(0.05)
            _, smart_now, _ = self._toolbar()
            if self._selected(smart_now) == smart_on:
                break
            if attempt == 2:
                self.log("    couldn't put Smart mode back")
                break
            self.log(f"    Smart mode was {'on' if smart_on else 'off'} but is now "
                     f"{'on' if not smart_on else 'off'}; correcting")
            if smart_on:
                pt.run("SetEditTool", {"edit_tool": "ET_SmartTool"})
            elif attempt == 0:
                pt.run("SetEditTool", {"edit_tool": self.TOOL_IDS.get(prev, new_mode)})
            elif smart_now is not None:
                smart_now.perform("AXPress")       # last resort: click the Smart button itself
        self.log(f"  trim tool now {'Standard' if is_tce else 'TCE'} "
                 f"(Smart {'on' if smart_on else 'off'}{', ' + prev if prev else ''})")

    RATE_LABELS = {44100: "44.1 kHz", 48000: "48 kHz", 88200: "88.2 kHz", 96000: "96 kHz",
                   176400: "176.4 kHz", 192000: "192 kHz"}
    SHORT_RATES = {44100: "44", 48000: "48", 88200: "88", 96000: "96", 176400: "176", 192000: "192"}

    def popup_by_label(self, win, label):
        """The pop-up sitting to the right of a text label (e.g. 'Bit Depth:'). Pro Tools names
        these pop-ups after whatever they currently show, so the label is the reliable handle."""
        labs = E.find_all(win, "AXStaticText", label, max_depth=8)
        if not labs:
            raise E.NotFound(f"the '{label}' label")
        (lx, ly), (lw, lh) = labs[0].attr("AXPosition"), labs[0].attr("AXSize")
        cy = ly + lh / 2
        best, dist = None, None
        for p in E.find_all(win, "AXPopUpButton", max_depth=8):
            (px, py), (_, ph) = p.attr("AXPosition"), p.attr("AXSize")
            if px < lx:
                continue
            d = abs((py + ph / 2) - cy) + (px - (lx + lw)) * 0.01
            if dist is None or d < dist:
                best, dist = p, d
        if best is None or dist > 20:
            raise E.NotFound(f"the pop-up next to '{label}'")
        return best

    def type_into(self, field, text):
        """Fill a text box the way a person would (Pro Tools ignores text set behind its back):
        click in it, select all, paste, Tab to confirm, then check it took."""
        x, y = self.center(field)
        self.sys.click(x, y)
        self.sys.sleep(0.1)
        self.sys.key(*parse_combo("cmd+a"))
        self.sys.paste(text)
        self.sys.key(*parse_combo("tab"))
        self.sys.sleep(0.15)
        got = E.norm(field.attr("AXValue"))
        if got and got != E.norm(text):
            self.log(f"    (the name box shows '{got}', expected '{text}')")

    def hardware_insert_names(self, force=False) -> list[str]:
        """Your hardware inserts' names (as listed under 'i/o' in an insert slot's menu).
        Learned by opening an empty slot's menu once, then remembered for a day."""
        from . import settings
        base = self.lib.folder.parent
        saved = settings.get(base, "hardware inserts") or {}
        if not force and saved.get("names") and time.time() - saved.get("at", 0) < 86400:
            return saved["names"] + [str(n) for n in (saved.get("also") or [])]
        win = self.edit_window()
        sel = None
        for header in E.find_all(win, "AXGroup", "* - * Track"):
            for L in self.SLOTS:
                state, asg = self._try_slot(header, "Insert", L)
                if asg is not None and str(asg.attr("AXValue") or "") == "unassigned":
                    sel = self.slot_buttons(header, "Insert", L)[0]
                    break
            if sel is not None:
                break
        if sel is None:
            raise MacroError("couldn't find an empty insert slot to read your hardware inserts from")
        names = []
        root = self.open_menu(sel)
        try:
            item = next((c for c in E.children(root)
                         if any(E.norm(lab).lower() == "i/o" for lab in E.labels(c))), None) if root else None
            if item is None and root is not None:
                self.log("    (the insert menu had no 'i/o' section: " +
                         ", ".join(E.labels(c)[0] for c in E.children(root) if E.labels(c))[:200] + ")")
            if item is not None:
                sub = self._submenu(item)
                if sub is None or not E.children(sub):
                    item.perform("AXPress")
                    self.sys.sleep(0.3)
                    sub = self._submenu(item)
                for c in E.children(sub) if sub is not None else []:
                    labels = E.labels(c)
                    if c.attr("AXRole") == "AXMenuItem" and labels and labels[0].strip():
                        names.append(re.sub(r"(?i)\s+\((mono|stereo)\)$", "", labels[0]).strip())
        finally:
            self.close_menus()
        extra = [str(n) for n in (saved.get("also") or [])]       # names you've added by hand
        if names:                                                 # an empty list is re-checked next time
            settings.put(base, "hardware inserts", {"names": names, "at": time.time(), "also": extra})
        self.log(f"    your hardware inserts (from the i/o menu): {', '.join(names) or 'none found'}")
        return names + extra

    NO_INSERTS = ("VCA Track", "MIDI Track", "Folder Track", "Basic Folder Track", "Video Track")

    def _insert_slots(self, rebuild=False):
        """Every insert slot in the session: [(track, letter, selector, name button)]. Finding
        the track headers means searching the whole Edit window (slow with many tracks), so the
        slots are found once per session and kept; their contents are read fresh every time."""
        import threading
        lock = getattr(type(self), "_slots_lock", None)
        if lock is None:
            lock = type(self)._slots_lock = threading.Lock()
        with lock:
            try:
                info = self.sys.ptsl().track_info("all")
                key = (self.session_info()[1], len(info))
            except Exception:  # noqa: BLE001
                key = None
            cached = getattr(type(self), "_slots_cache", None)
            if cached and not rebuild and key is not None and cached[0] == key:
                return cached[1]
            slots = []
            for header in E.find_all(self.edit_window(), "AXGroup", "* - * Track"):
                title = str(header.attr("AXTitle") or "")
                if title.endswith(self.NO_INSERTS):
                    continue
                track = title.rsplit(" - ", 1)[0]
                for group in E.children(header):
                    gname = str(group.attr("AXTitle") or "")
                    if not gname.startswith("Inserts"):
                        continue
                    kids = E.children(group)
                    if len(kids) < 2:
                        continue
                    # Pro Tools lists the 5 selectors, then the 5 slot names; check the order once.
                    if str(kids[1].attr("AXTitle") or "").startswith("Insert Assignment"):
                        pairs = [(kids[j], kids[j + 1]) for j in range(0, len(kids) - 1, 2)]
                    else:
                        half = len(kids) // 2
                        pairs = list(zip(kids[:half], kids[half:]))
                    first = gname.split()[-1][:1] if " " in gname else "A"
                    for i, (selector, asg) in enumerate(pairs):
                        letter = chr(ord(first) + i) if first.isalpha() else "?"
                        slots.append((track, letter, selector, asg))
            type(self)._slots_cache = (key, slots)
            return slots

    def prepare_insert_scan(self):
        """Find the session's insert slots ahead of time (e.g. when the Bounce Mix page opens)."""
        try:
            self._insert_slots()
        except Exception:  # noqa: BLE001
            pass

    def active_hardware_inserts(self) -> list[str]:
        """'Track slot: insert' for every hardware insert that's active right now (read fresh
        every time; only the slots' places are remembered)."""
        names = {E.norm(n).lower() for n in self.hardware_insert_names()}
        for attempt in range(2):
            slots = self._insert_slots(rebuild=attempt > 0)
            found, seen, broken = [], set(), 0
            for track, letter, selector, asg in slots:
                value = asg.attr("AXValue")
                if value is None:
                    broken += 1                  # Pro Tools rebuilt this track: find the slots again
                    continue
                name = re.sub(r"(?i)\s+\((mono|stereo)\)$", "", str(value)).strip()
                if not name or name == "unassigned":
                    continue
                seen.add(name)
                if E.norm(name).lower() in names and "inactive" not in str(selector.attr("AXValue") or "").lower():
                    found.append(f"{track} {letter}: {name}")
            if broken <= len(slots) // 20:
                break
        tracks = len({t for t, *_ in slots})
        self.log(f"    checked {tracks} tracks; inserts in use: {', '.join(sorted(seen))[:300] or 'none'}")
        return found

    def bounce_dialog(self, o):
        """Open Bounce Mix and fill it in (name, source, 24-bit, the session's sample rate,
        Offline on/off/auto), then leave it open for you to check and click Bounce.
        offline: auto -> Real-time if any hardware insert is active, otherwise Offline."""
        import datetime
        if str(o.get("offline", "")).lower() == "auto":
            try:
                hw = self.active_hardware_inserts()
                o = dict(o, offline=not hw)
                self.log("    hardware inserts active (" + "; ".join(hw[:4]) + (" …" if len(hw) > 4 else "")
                         + "): Real-time bounce" if hw else "    no hardware inserts active: Offline bounce")
            except Exception as e:  # noqa: BLE001 - can't tell: real-time is always safe
                o = dict(o, offline=False)
                self.log(f"    couldn't check for hardware inserts ({e}): Real-time bounce to be safe")
        rate = self.session_sample_rate()
        name, _ = self.session_info()
        session = name[:-4] if name.lower().endswith(".ptx") else name
        bits = str(o.get("bits", 24)).lower().replace("bit", "").strip()
        file_name = str(o.get("name", "{date}_{session}_EASMIX_{rate}_{bits}.wav")).format(
            date=datetime.date.today().strftime("%y%m%d"), session=session,
            rate=self.SHORT_RATES.get(rate, str(rate)), bits=f"{bits}b" if bits != "32" else "32f")

        self.sys.key(*parse_combo("cmd+option+b"))          # Bounce Mix...
        win = self.until(lambda: E.find_window(self.app(), "Bounce Mix*"), 10, "the Bounce Mix window")
        self.sys.sleep(0.2)

        if "offline" in o:          # first, before anything else in the dialog
            self.checkbox("Offline", {"window": "Bounce Mix*", "set": "on" if o.get("offline") else "off"})
        field = E.find_all(win, "AXTextField", max_depth=8)
        if field:
            self.type_into(field[0], file_name)
        raw = o.get("source")
        if raw:
            import fnmatch
            wanted = raw if isinstance(raw, list) else [x.strip() for x in str(raw).split(" or ")]
            # Your main outputs can go by another name (Default I/O renames them), so if the named
            # one doesn't exist, a stereo '1-2' output that's already selected is kept.
            patterns = [w if "*" in w else w + "*" for w in wanted]
            pop = self.popup_by_label(win, "Mix Source:")
            current = " ".join(E.labels(pop))

            def fits(label, pats):
                return any(fnmatch.fnmatchcase(E.norm(label).lower(), E.norm(p).lower()) for p in pats)
            if not fits(current, patterns):
                for pat in patterns:
                    try:
                        self.choose_from(pop, pat)
                        break
                    except (E.NotFound, MacroError):
                        win = self.until(lambda: E.find_window(self.app(), "Bounce Mix*"), 2,
                                         "the Bounce Mix window (it closed)")
                        pop = self.popup_by_label(win, "Mix Source:")
                else:
                    if fits(current, ["*1-2 (stereo)*"]) and not current.lower().startswith("bus"):
                        self.log(f"  mix source: '{wanted[0].rstrip('*')}' isn't there; kept '{current}' "
                                 f"(your stereo 1-2 output)")
                    else:
                        self.log(f"  ⚠ couldn't find the mix source '{wanted[0].rstrip('*')}'; left it on "
                                 f"'{current}' — check it before bouncing")
            win = self.until(lambda: E.find_window(self.app(), "Bounce Mix*"), 2, "the Bounce Mix window (it closed)")
        bit_label = {"16": "16 Bit", "24": "24 Bit", "32": "32 Bit Float"}[bits]
        pop = self.popup_by_label(win, "Bit Depth:")
        if E.norm(" ".join(E.labels(pop))) != bit_label:
            self.choose_from(pop, bit_label)
        rate_label = self.RATE_LABELS.get(rate)
        if rate_label:
            pop = self.popup_by_label(win, "Sample Rate:")
            if E.norm(" ".join(E.labels(pop))) != rate_label:
                self.choose_from(pop, rate_label)
        if E.find_all(win, "AXCheckBox", "Import After Bounce", max_depth=8):
            self.checkbox("Import After Bounce", {"window": "Bounce Mix*", "set": "off"})
        self.log(f"  Bounce Mix ready: {file_name} ({bit_label}, {rate_label or rate})")
        if o.get("click bounce"):
            E.find_one(win, "button", "Bounce").perform("AXPress")

    def set_buffer_size(self, v):
        """set buffer size: 128  — via Setup > Playback Engine > H/W Buffer Size, then OK."""
        size = int(re.sub(r"\D", "", str(v)) or 0)
        if not size:
            raise MacroError("set buffer size needs a number of samples, e.g. 128")
        self.menu("Setup > Playback Engine...", {})
        win = self.until(lambda: E.find_window(self.app(), "Playback Engine*"), 10, "the Playback Engine window")

        def buffer_popup():
            pops = E.find_all(win, "AXPopUpButton", max_depth=6)
            for p in pops:          # its label or value reads like '1024 Samples'
                text = " ".join(E.labels(p) + [str(p.attr("AXValue") or "")]).lower()
                if "buffer" in text or re.search(r"\b\d+ samples\b", text):
                    return p
            raise E.NotFound("the H/W Buffer Size pop-up")
        pop = self.until(buffer_popup, 3, "the H/W Buffer Size pop-up")
        current = " ".join(E.labels(pop) + [str(pop.attr("AXValue") or "")])
        if re.search(rf"\b{size} samples\b", current.lower()):
            self.log(f"    buffer is already {size} samples")
        else:
            self.choose_from(pop, f"{size} Samples")
        ok = E.find_all(win, "AXButton", "OK", max_depth=6)
        if ok:
            ok[0].perform("AXPress")
        self.until(lambda: self._gone_window("Playback Engine*"), 15, "the Playback Engine window to close")
        self.log(f"  H/W buffer set to {size} samples")

    def _gone_window(self, title):
        try:
            E.find_window(self.app(), title)
        except E.NotFound:
            return True
        raise E.NotFound(f"'{title}' is still open")

    def session_sample_rate(self) -> int:
        rate = self.sys.ptsl().run("GetSessionSampleRate").get("sample_rate", "")
        return int(re.sub(r"\D", "", str(rate)) or 0)

    def press_without_waiting(self, el):
        """Press a button that opens a modal window (file browser, dialog) without
        getting stuck: macOS doesn't return from such a press until the window closes."""
        import threading
        threading.Thread(target=lambda: el.perform("AXPress"), daemon=True).start()

    def open_file_in_browser(self, path):
        """In an open macOS file browser: Go to Folder, paste the full path, open it."""
        self.sys.sleep(1.0)
        self.sys.key(*parse_combo("cmd+shift+g"))
        self.sys.sleep(0.6)
        self.sys.key(*parse_combo("cmd+a"))
        self.sys.paste(str(path))
        self.sys.sleep(0.6)
        self.sys.key(*parse_combo("return"))      # go to (and select) the file
        self.sys.sleep(0.8)
        self.sys.key(*parse_combo("return"))      # open it

    def import_io_settings(self, v, o):
        """import io settings: {44100: /path/a.pio, 48000: /path/b.pio}  (picked by the session's sample rate)"""
        if not isinstance(v, dict):
            raise MacroError("import io settings needs a file for each sample rate, e.g. 48000: /path/to/file.pio")
        files = {int(re.sub(r"\D", "", str(k)) or 0): str(p) for k, p in v.items()}
        rate = self.session_sample_rate()
        path = files.get(rate)
        if not path:
            raise MacroError(f"no I/O settings file for {rate} Hz sessions (have: "
                             f"{', '.join(str(r) for r in sorted(files))})")
        self.log(f"    session is {rate} Hz: importing {path.split('/')[-1]}")
        self.menu("Setup > I/O...", {})
        win = self.until(lambda: E.find_window(self.app(), "I/O Setup*"), 10, "the I/O Setup window")
        btn = self.until(lambda: E.find_one(win, "button", "Import Settings*"), 5, "the Import Settings button")
        self.press_without_waiting(btn)
        self.open_file_in_browser(path)

    def track_menu(self, v, o):
        """track menu: Change Track Width > Mono   — right-clicks each selected track's name
        and picks from its menu (scrolling the track into view first if needed)."""
        parts = v if isinstance(v, list) else [p.strip() for p in str(v).split(">") if p.strip()]
        done = 0
        for track in self.target_tracks(o):
            header = self.track_header(track)
            name = next(iter(E.find_all(header, None, "Track name*", max_depth=2)), None)
            if name is None:
                raise E.NotFound(f"the name of track '{track}'")
            if not self._visible_in_edit_window(name):
                try:
                    self.scroll_to_track(track)
                    header = self.track_header(track)
                    name = next(iter(E.find_all(header, None, "Track name*", max_depth=2)), name)
                except (E.NotFound, MacroError):
                    pass
            x, y = self.center(name)
            self.sys.click(x, y, button="right")
            menu = self.until(lambda: self._find_menu(name), 2.0, f"the right-click menu for '{track}'")
            item = self._walk(menu, parts) or self._walk_from_anywhere(menu, parts)
            if item is None:
                self.close_menus()
                raise E.NotFound(f"'{' > '.join(parts)}' in the right-click menu for '{track}'")
            if item.attr("AXEnabled") is False:
                self.close_menus()
                self.log(f"    '{parts[-1]}' isn't available on '{track}' (it needs no clips or extra playlists)")
                continue
            if not self._press_item(item, name, root=menu):
                self.close_menus()
            done += 1
            self.sys.sleep(0.2)
        self.log(f"  {' > '.join(parts)}: {done} track(s)")

    def _walk_from_anywhere(self, menu, parts, depth=0):
        """Find the first part of the path at any depth (e.g. 'Change Track Width' inside
        another sub-menu), then follow the rest of the path from there."""
        if depth > 6:
            return None
        for item in E.children(menu):
            sub = self._submenu(item)
            if self._item_matches(item, parts[0]):
                if len(parts) == 1:
                    return item
                if sub is None or not E.children(sub):
                    item.perform("AXPress")
                    self.sys.sleep(0.15)
                    sub = self._submenu(item)
                if sub is not None:
                    found = self._walk(sub, parts[1:])
                    if found:
                        return found
            elif sub is not None:
                found = self._walk_from_anywhere(sub, parts, depth + 1)
                if found:
                    return found
        return None

    def accept_dialog(self, o):
        """If a small dialog pops up (e.g. Pro Tools asking to name a new playlist), press
        Return to accept it. Nothing happens if no dialog appears within 'timeout' (default 2s)."""
        timeout = seconds(o.get("timeout", 2))

        def dialog():
            for w in self._windows():
                title = str(w.attr("AXTitle") or "")
                if title.startswith(("Edit:", "Mix:", "Plug-in:")) or self._is_menu_window(w):
                    continue
                if E.find_all(w, "AXTextField", max_depth=4) or E.find_all(w, "AXButton", "OK", max_depth=4):
                    return w
            raise E.NotFound("a dialog")
        try:
            w = self.until(dialog, timeout, "a dialog")
        except E.NotFound:
            self.log("    (no dialog appeared)")
            return
        self.sys.key(*parse_combo("return"))
        try:
            self.until(lambda: self._gone_dialog(w), 3, "the dialog to close")
        except E.NotFound:
            ok = E.find_all(w, "AXButton", "OK", max_depth=4)
            if ok:
                ok[0].perform("AXPress")

    def _windows(self):
        return E.window_list(self.app())

    def scroll_to_track(self, track):
        """Track > Scroll to Track..., so a track's header is on screen for mouse work.
        The menu item opens a modal dialog, which would block an Accessibility press until
        the dialog closes, so the press runs in the background while we fill the dialog in."""
        import threading
        app = self.app()
        before = list(E.children(app)) + self._windows()
        threading.Thread(target=lambda: self._safe_menu("Track > Scroll to Track..."), daemon=True).start()

        def dialog():
            for w in list(E.children(app)) + self._windows():
                if w.attr("AXRole") == "AXWindow" and not any(w == b for b in before) \
                        and E.find_all(w, "AXTextField", max_depth=4):
                    return w
            raise E.NotFound("the Scroll to Track window")
        try:
            w = self.until(dialog, 3.0, "the Scroll to Track window")
        except E.NotFound:
            self.close_menus()
            raise
        field = E.find_all(w, "AXTextField", max_depth=4)[0]
        # Pro Tools ignores text set behind its back: type it like you would, then Return (= OK).
        try:
            self.type_into(field, str(track))
        except Exception as e:  # noqa: BLE001
            self.log(f"    (typing the track name: {e})")
        self.sys.key(*parse_combo("return"))

        def gone():
            if any(w == x for x in list(E.children(app)) + self._windows()):
                raise E.NotFound("the Scroll to Track window to close")
            return True
        try:
            self.until(gone, 2.0, "the Scroll to Track window to close")
        except E.NotFound:
            self.sys.key(*parse_combo("escape"))        # never leave it stuck open
            self.sys.sleep(0.2)
            raise MacroError(f"couldn't scroll to '{track}' (the Scroll to Track window didn't take it)")
        self.sys.sleep(0.3)

    def _safe_menu(self, path):
        try:
            self.menu(path, {})
        except Exception:  # noqa: BLE001 - reported by the caller if the dialog never shows
            pass

    def _visible_in_edit_window(self, el):
        """Is el inside the visible part of the Edit window?"""
        try:
            win = self.edit_window()
            (wx, wy), (ww, wh) = win.attr("AXPosition"), win.attr("AXSize")
            (x, y), (w, h) = el.attr("AXPosition"), el.attr("AXSize")
        except (TypeError, ValueError, E.NotFound):
            return False
        return wx <= x and x + w <= wx + ww and wy + 60 <= y and y + h <= wy + wh - 20

    def compact_inserts(self, o):
        """Move each track's plug-ins up into the earliest empty insert slots, keeping their order."""
        moved = 0
        tracks = self.target_tracks(o)
        self.log(f"    tracks: {', '.join(tracks)}")
        for track in tracks:
            self.log(f"    finding '{track}' in the Edit window")
            header = self.track_header(track, "Inserts A-E", "Inserts F-J")
            first, last = (self._try_slot(header, "Insert", L)[1] for L in "AJ")
            self.log(f"    inserts on screen: {bool(first and last and self._visible_in_edit_window(first) and self._visible_in_edit_window(last))}")
            if not (first and last and self._visible_in_edit_window(first) and self._visible_in_edit_window(last)):
                try:
                    self.log(f"    scrolling to '{track}'")
                    self.scroll_to_track(track)
                    header = self.track_header(track, "Inserts A-E", "Inserts F-J")
                    self._btn_cache = None
                except (E.NotFound, MacroError):
                    self.log(f"  (couldn't scroll to '{track}'; trying anyway)")
            target = 0
            for i, letter in enumerate(self.SLOTS):
                _, asg = self._try_slot(header, "Insert", letter)
                if asg is None or str(asg.attr("AXValue") or "unassigned") == "unassigned":
                    continue
                if i != target:
                    _, dest = self._try_slot(header, "Insert", self.SLOTS[target])
                    self.log(f"    moving insert {letter} to {self.SLOTS[target]}")
                    for _attempt in range(3):
                        (sx, sy), (dx, dy) = asg.attr("AXPosition"), dest.attr("AXPosition")
                        self.sys.drag((sx + 2, sy + 5), (dx + 2, dy + 5))
                        try:
                            self.until(lambda: self._slot_emptied(asg), 10, "the plug-in to move")
                            moved += 1
                            break
                        except E.NotFound:
                            continue
                    else:
                        raise MacroError(f"couldn't move the plug-in in insert {letter} on '{track}' after 3 tries")
                target += 1
        self.log(f"  moved {moved} plug-in(s)")

    @staticmethod
    def _slot_emptied(asg):
        if str(asg.attr("AXValue") or "") == "unassigned":
            return True
        raise E.NotFound("slot still in use")

    def _try_slot(self, header, kind, letter):
        try:
            sel, asg = self.slot_buttons(header, kind, letter)
            return sel.attr("AXValue"), asg
        except E.NotFound:
            return None, None

    def _is_stereo(self, track) -> bool:
        """Is the track stereo? (Its input selector names the format, e.g. '... (Stereo)'.)"""
        try:
            header = self.track_header(track)
            el = next(iter(E.find_all(header, None, "Audio Input Path selector*", max_depth=3)), None)
            text = " ".join(str(x) for x in (E.labels(el) if el is not None else []))
            return "(stereo)" in text.lower() or "stereo" in str(el.attr("AXValue") or "").lower()
        except Exception:  # noqa: BLE001
            return False

    def assign(self, what, v, o):
        """send: //[PARA DRUMS] (slot: 1)  /  output: (PRINT)  /  input: Analog 1-2  — for the selected tracks.

        Outputs: the first track is set through its menu, then the same output is copied
        to the other tracks in one go with the Pro Tools Scripting SDK.
        Sends and inputs: each track is set through its own menu."""
        tracks = self.target_tracks(o)
        prefer = "interface" if what == "input" else "bus"
        if what == "input" and o.get("stereo") and self._is_stereo(tracks[0]):
            v = o["stereo"]                    # stereo tracks have a different input name
            self.log(f"    stereo track: using '{v}'")
        if what == "output" and len(tracks) > 1:
            self._assign_one(what, tracks[0], v, o, prefer)
            try:
                self._copy_output(tracks[0], tracks[1:])
                return
            except Exception as e:  # noqa: BLE001 - fall back to one track at a time
                self.log(f"  (couldn't copy the output with the SDK: {e}; doing each track)")
            rest = tracks[1:]
        elif len(tracks) > 1:
            # Like doing it by hand: Option+Shift-click the first track's selector and choose,
            # which sets every selected track. Then check, and do any track that missed out.
            letter = self._assign_one(what, tracks[0], v, o, prefer, all_selected=True)
            name = [p.strip() for p in str(v).split(">")][-1]
            rest = [t for t in tracks if not self._has_assignment(what, t, letter, name)]
            if rest:
                self.log(f"  ({len(rest)} track(s) didn't pick it up; setting them one by one)")
        else:
            rest = tracks
        for t in rest:
            self._assign_one(what, t, v, o, prefer, slot_letter=letter if what == "send" and len(tracks) > 1 else None)

    def _has_assignment(self, what, track, letter, name):
        try:
            header = self.track_header(track)
        except E.NotFound:
            return False
        if what == "send":
            _, asg = self._try_slot(header, "Send", letter)
            value = str(asg.attr("AXValue") or "") if asg is not None else ""
        else:
            el = next(iter(E.find_all(header, None, "Audio Input Path selector*", max_depth=3)), None)
            value = str(el.attr("AXValue") or "") if el is not None else ""
        return E.norm(value) == E.norm(name) or E.norm(value).startswith(E.norm(name) + " ")

    def _assign_one(self, what, track, v, o, prefer, all_selected=False, slot_letter=None):
        """Set one track's send/input/output through its menu. Returns the send slot letter used."""
        header = self.track_header(track, *(("Sends A-E", "Sends F-J") if what == "send" else ("I/O",)))
        letter = None
        if what == "send":
            slot = str(o.get("slot", "first free")).lower()
            if slot_letter:
                letter = slot_letter
            elif slot in ("first free", "firstfree", "free"):
                letter = next((L for L in self.SLOTS
                               if str(self._try_slot(header, "Send", L)[0]) == "unassigned"), None)
                if letter is None:
                    raise MacroError(f"no free send on '{track}'")
            else:
                letter = self.slot_letter(slot)
            el, _ = self.slot_buttons(header, "Send", letter)
        else:
            label = "Audio Output Path selector*" if what == "output" else "Audio Input Path selector*"
            el = E.find_one(header, None, label)
        if all_selected:
            self._choose_for_all(el, v, prefer)
        else:
            self.choose_from(el, v, prefer=prefer)
        if self._menu_still_open(el):          # never leave a menu hanging open
            self.close_menus()
            self.sys.sleep(0.2)
        return letter

    def _choose_for_all(self, el, choose, prefer):
        """Option+Shift-click the selector, pick the item while still holding them."""
        from .keys import ALT, SHIFT
        flags = ALT | SHIFT
        parts = choose if isinstance(choose, list) else [p.strip() for p in str(choose).split(">") if p.strip()]
        x, y = self.center(el)
        self.sys.hold(flags, True)
        try:
            self.sys.click(x, y, flags=flags)
            try:
                menu = self.until(lambda: self._find_menu(el), 2.0, "the pop-up menu")
            except E.NotFound:
                return
            item = self._walk(menu, parts) or self._search(menu, parts[-1], prefer)
            if item is not None:
                self._press_item(item, el, flags, root=menu, expect=parts[-1])
        finally:
            self.sys.hold(flags, False)

    def _copy_output(self, source, targets):
        pt = self.sys.ptsl()
        res = pt.run("GetTrackList", {"page_limit": 10000, "pagination_request": {"limit": 10000, "offset": 0},
                                      "track_filter_list": [{"filter": "TLFilter_All", "is_inverted": False}]})
        ids = {t["name"]: t["id"] for t in res.get("track_list", [])}
        if source not in ids:
            raise MacroError(f"track '{source}' not found")
        paths = pt.run("GetTrackMainOutputAssignments", {"track_ids": [ids[source]]}).get("signalpath_ids", [])
        if not paths:
            raise MacroError(f"'{source}' has no output to copy")
        pt.run("SetTrackMainOutputAssignments", {"track_names": list(targets), "signalpath_ids": paths})
        self.log(f"  copied the output to {len(targets)} more track(s)")

    def remove_inactive(self, v, o, only_inactive=True):
        """remove inactive: plugins | sends | both   (tracks: selected | all)
        clear: plugins | sends | both  removes every plug-in/send, active or not."""
        which = str(v or "both").lower()
        kinds = (["Insert"] if which.startswith("plug") or which.startswith("insert") else
                 ["Send"] if which.startswith("send") else ["Insert", "Send"])
        views = (["Inserts A-E", "Inserts F-J"] if "Insert" in kinds else []) + \
                (["Sends A-E", "Sends F-J"] if "Send" in kinds else [])
        removed = 0
        for track in self.target_tracks(o):
            try:
                header = self.track_header(track, *views)
            except E.NotFound:
                continue            # hidden tracks and VCAs have no slots to clean
            for kind in kinds:
                for L in self.SLOTS:
                    value, asg = self._try_slot(header, kind, L)
                    if asg is None:
                        continue
                    if only_inactive and str(value or "").lower() != "inactive":
                        continue
                    if not only_inactive and str(asg.attr("AXValue") or "unassigned") == "unassigned":
                        continue
                    sel, _ = self.slot_buttons(header, kind, L)
                    self.choose_from(sel, ["no insert" if kind == "Insert" else "no send"])
                    self._confirm_dialog(("Remove", "Change", "OK"))
                    removed += 1
        self.log(f"  removed {removed} {'inactive ' if only_inactive else ''}item(s)")

    HEIGHTS = {"micro", "mini", "small", "medium", "large", "jumbo", "extreme"}

    def clear_slots(self, v, o):
        """clear: sends | plugins | both  — removes every send/plug-in from the selected tracks.

        Fast: tracks are set to a height that shows every slot (then put back), and each
        slot is cleared on all selected tracks at once with Option+Shift, like doing it by hand."""
        which = str(v or "both").lower()
        kinds = (["Insert"] if which.startswith("plug") or which.startswith("insert") else
                 ["Send"] if which.startswith("send") else ["Insert", "Send"])
        views = (["Inserts A-E", "Inserts F-J"] if "Insert" in kinds else []) + \
                (["Sends A-E", "Sends F-J"] if "Send" in kinds else [])
        tracks = self.target_tracks(o)
        pt = self.sys.ptsl()
        height = "THeight_" + str(o.get("height", "medium")).strip().title()
        originals = {}
        try:
            res = pt.run("GetTrackList", {"page_limit": 10000, "pagination_request": {"limit": 10000, "offset": 0},
                                          "track_filter_list": [{"filter": "TLFilter_All", "is_inverted": False}]})
            originals = {t["name"]: t.get("height", "") for t in res.get("track_list", []) if t.get("name") in tracks}
            pt.run("SetTrackHeight", {"track_names": tracks, "height": height})
            self.sys.sleep(0.2)
        except Exception as e:  # noqa: BLE001 - older Pro Tools: carry on at the current heights
            self.log(f"    (couldn't resize the tracks: {e})")
            originals = {}
        removed = 0
        try:
            headers = {}
            for t in tracks:
                try:
                    headers[t] = self.track_header(t, *views)
                except E.NotFound:
                    pass                 # hidden tracks and VCAs have no slots to clear
            for kind in kinds:
                empty = "no insert" if kind == "Insert" else "no send"
                for L in self.SLOTS:
                    used = [t for t, h in headers.items() if self._slot_used(h, kind, L)]
                    if not used:
                        continue
                    first = headers[used[0]]
                    sel, _ = self.slot_buttons(first, kind, L)
                    if len(headers) > 1:
                        self._choose_for_all(sel, [empty], prefer=None)
                    else:
                        self.choose_from(sel, [empty])
                    self._confirm_dialog(("Remove", "Change", "OK"))
                    for t in used:                    # anything that didn't take: one at a time
                        if self._slot_used(headers[t], kind, L):
                            s_el, _ = self.slot_buttons(headers[t], kind, L)
                            self.choose_from(s_el, [empty])
                            self._confirm_dialog(("Remove", "Change", "OK"))
                    removed += len(used)
        finally:
            by_height = {}
            for t, h in originals.items():
                if h and h != height:
                    by_height.setdefault(h, []).append(t)
            for h, names in by_height.items():
                try:
                    pt.run("SetTrackHeight", {"track_names": names, "height": h})
                except Exception:  # noqa: BLE001
                    pass
        self.log(f"  cleared {removed} {'send' if kinds == ['Send'] else 'plug-in' if kinds == ['Insert'] else 'item'}(s)")

    def _slot_used(self, header, kind, letter):
        _, asg = self._try_slot(header, kind, letter)
        return asg is not None and str(asg.attr("AXValue") or "unassigned") != "unassigned"

    def _confirm_dialog(self, buttons, wait=0.3):
        """Click Remove/Change in a confirmation box if Pro Tools shows one."""
        end = self.sys.now() + wait
        while self.sys.now() < end:
            for w in E.window_list(self.app()):
                if str(w.attr("AXTitle") or "").startswith(("Edit:", "Mix:", "Plug-in:")):
                    continue
                for b in buttons:
                    hits = E.find_all(w, "AXButton", b, max_depth=3)
                    if hits:
                        hits[0].perform("AXPress")
                        self.sys.sleep(0.2)
                        return
            self.sys.sleep(POLL)

    # ----- AudioSuite -----
    AUDIOSUITE_WINDOW = "Audio*Suite*"

    def audiosuite_open(self, name, o):
        """Finds the plug-in anywhere in the AudioSuite menu, so it works whether
        Pro Tools groups plug-ins by category or by manufacturer."""
        bar = self.app().attr("AXMenuBar")
        top = next((c for c in E.children(bar) if E.name_matches(c, "AudioSuite")), None) if bar else None
        if top is None:
            raise E.NotFound("the AudioSuite menu")

        def search(item, depth):
            if depth > 4:
                return None
            for menu in (c for c in E.children(item) if c.attr("AXRole") == "AXMenu"):
                for mi in E.children(menu):
                    if E.name_matches(mi, name) and not any(c.attr("AXRole") == "AXMenu" for c in E.children(mi)):
                        return mi
                    found = search(mi, depth + 1)
                    if found:
                        return found
            return None
        item = search(top, 0)
        if item is None:
            top.perform("AXPress")          # menus sometimes only fill in once opened
            self.sys.sleep(0.3)
            item = search(top, 0)
            self.close_menus()
        if item is None:
            raise E.NotFound(f"AudioSuite plug-in '{name}'")
        item.perform("AXPress")
        self.until(lambda: E.find_window(self.app(), f"*{name}*"), 10, f"the {name} window")

    def audiosuite_window(self, o):
        return self.until(lambda: E.find_window(self.app(), o.get("window", self.AUDIOSUITE_WINDOW)),
                          seconds(o.get("timeout", DEFAULT_TIMEOUT)), "an AudioSuite window")

    def audiosuite_preset(self, v, o):
        w = self.audiosuite_window(o)
        parts = v if isinstance(v, list) else [p.strip() for p in str(v).split(">")]
        pops = E.find_all(w, "AXPopUpButton", "Librarian menu") or [
            p for p in E.find_all(w, "AXPopUpButton") if "preset" in " ".join(E.labels(p)).lower()]
        if not pops:
            raise E.NotFound("the AudioSuite preset menu (run Pick Element on it and send me the result)")
        self.choose_from(pops[0], parts)

    def audiosuite_processing(self, w, mode):
        """Set AudioSuite's processing mode pop-up ('Clip by Clip' / 'Entire Selection')."""
        want = "clip" if "clip" in str(mode).lower() else "entire"
        target = "*lip by *lip" if want == "clip" else "*ntire *election"
        for p in E.find_all(w, "AXPopUpButton", max_depth=6):
            text = " ".join(E.labels(p) + [str(p.attr("AXValue") or "")]).lower()
            if "clip by clip" in text or "entire selection" in text:
                if (want == "clip" and "clip by clip" in text) or (want == "entire" and "entire selection" in text):
                    return                                   # already set
                self.choose_from(p, target)
                self.log(f"    AudioSuite processing: {'Clip by Clip' if want == 'clip' else 'Entire Selection'}")
                return
        raise E.NotFound("AudioSuite's 'Clip by Clip / Entire Selection' pop-up")

    def audiosuite_render(self, o):
        w = self.audiosuite_window(o)
        if o.get("processing"):
            self.audiosuite_processing(w, o["processing"])
        btn = E.find_one(w, "button", "Render")
        btn.perform("AXPress")
        # Wait for rendering to finish: the Render button comes back once it's done.
        self.sys.sleep(0.5)
        self.until(lambda: E.find_one(self.audiosuite_window(o), "button", "Render"), 600, "rendering to finish")

    # ----- Pro Tools Scripting SDK tasks -----
    def session_info(self):
        pt = self.sys.ptsl()
        name = pt.run("GetSessionName").get("session_name", "")
        path = pt.run("GetSessionPath").get("session_path", {}).get("path", "")
        if ":" in path and not path.startswith("/"):        # old Mac-style path
            path = "/Volumes/" + path.replace(":", "/")
        return name, path

    def save_new_version(self):
        """Save, then File > Save As with the next number: Song.03 -> Song.04 (Song -> Song.01).
        Done through the Save As dialog (Pro Tools 2026's SDK Save As fails), which opens in
        the session's folder."""
        name, _ = self.session_info()
        new = next_version_name(name)
        self.sys.key(*parse_combo("cmd+s"))          # plain save first
        self.sys.sleep(0.5)
        before = self._windows()
        self.sys.key(*parse_combo("ctrl+cmd+s"))     # Save As

        def dialog():
            for w in self._windows():
                if not any(w == b for b in before) and E.find_all(w, "AXTextField", max_depth=6):
                    return w
            raise E.NotFound("the Save As window")
        win = self.until(dialog, 5, "the Save As window")
        field = E.find_all(win, "AXTextField", max_depth=6)[0]
        field.set_attr("AXFocused", True)
        self.sys.key(*parse_combo("cmd+a"))
        self.sys.paste(new)
        self.sys.sleep(0.2)
        self.sys.key(*parse_combo("return"))
        self.until(lambda: self._gone_dialog(win), 10, "the Save As window to close")
        self.log(f"  saved as {new}")

    def _gone_dialog(self, win):
        if any(w == win for w in self._windows()):
            raise E.NotFound("still open")
        return True

    def delete_empty_audio_tracks(self, o):
        pt = self.sys.ptsl()
        which = str(o.get("tracks", "selected")).lower()
        flt = "TLFilter_Selected" if which == "selected" else "TLFilter_All"
        res = pt.run("GetTrackList", {"page_limit": 10000, "pagination_request": {"limit": 10000, "offset": 0},
                                      "track_filter_list": [{"filter": flt, "is_inverted": False}]})
        empty = [t["name"] for t in res.get("track_list", [])
                 if t.get("type") == "TType_Audio" and not t.get("track_attributes", {}).get("contains_clips")]
        if empty:
            pt.run("DeleteTracks", {"track_names": empty, "delete_track_behavior_options": {
                "keep_folder_members": True, "keep_alternate_playlists": False, "coalesce_automation": False}})
        self.log(f"  deleted {len(empty)} empty audio track(s)")

    def bounce_mix(self, v, o):
        """bounce mix: "{date}_{session}_EASMIX_{rate}_{bits}"  (source: the output/bus to bounce)"""
        import datetime
        pt = self.sys.ptsl()
        source, source_type = o.get("source"), str(o.get("source type", "Output"))
        if not source or str(source).lower() in ("ask", "remembered"):
            source, source_type = self._bounce_source(pt, ask=str(source or "").lower() == "ask")
        name, _ = self.session_info()
        session = name[:-4] if name.lower().endswith(".ptx") else name
        rate = o.get("sample rate", "session")
        if str(rate).lower() == "session":
            rate = pt.run("GetSessionSampleRate").get("sample_rate", "SRate_48000")
        rate = int(re.sub(r"\D", "", str(rate)) or 48000)
        bits = str(o.get("bits", 24)).lower().replace("bit", "").strip()
        depth = {"16": "BDepth_16", "24": "BDepth_24", "32": "BDepth_32Float", "32float": "BDepth_32Float"}[bits]
        short_rate = {44100: "44", 48000: "48", 88200: "88", 96000: "96", 176400: "176", 192000: "192"}.get(rate, str(rate))
        file_name = str(v or "{session}").format(
            date=datetime.date.today().strftime("%y%m%d"), session=session, rate=short_rate,
            bits=f"{bits}b" if bits != "32float" else "32f")
        if file_name.lower().endswith(".wav"):
            file_name = file_name[:-4]
        folder = str(o.get("folder", "session"))
        location = ({"file_destination": "EMFDestination_SessionFolder"} if folder.lower() == "session"
                    else {"file_destination": "EMFDestination_Directory", "directory": folder})
        pt.run("ExportMix", {
            "file_name": file_name, "file_type": "EMFType_WAV",
            "mix_source_list": [{"source_type": "EMSType_" + source_type.title().replace(" ", ""),
                                 "name": str(source)}],
            "audio_info": {"compression_type": "CType_PCM", "export_format": "EFormat_Interleaved",
                           "bit_depth": depth, "sample_rate": f"SRate_{rate}"},
            "location_info": location,
            "offline_bounce": "TBool_True" if o.get("offline", True) else "TBool_False",
        }, timeout=None if o.get("offline", True) else 4 * 3600)   # real-time takes as long as the mix
        self.log(f"  bounced {file_name}.wav")

    def _bounce_source(self, pt, ask=False):
        """The output/bus you bounce from: asked once (a list of your session's
        outputs and buses), then remembered for every bounce."""
        from . import settings
        base = self.lib.folder.parent
        saved = settings.get(base, "bounce source")
        if saved and not ask:
            return saved["name"], saved["type"]
        choices = []
        for typ, label in (("EMSType_Output", "Output"), ("EMSType_Bus", "Bus")):
            try:
                for n in pt.run("GetExportMixSourceList", {"type": typ}).get("source_list", []):
                    choices.append(f"{label}: {n}")
            except Exception:  # noqa: BLE001
                pass
        if not choices:
            raise MacroError("couldn't get the list of outputs and buses from Pro Tools")
        pick = self.sys.choose(choices, "Which output or bus do you bounce your mix from? "
                                        "(PT Deck remembers this.)", "Bounce source")
        self.sys.activate()
        if not pick:
            raise MacroError("no bounce source chosen")
        typ, name = pick.split(": ", 1)
        settings.put(base, "bounce source", {"type": typ, "name": name})
        self.log(f"    bounce source set to {pick} (remembered)")
        return name, typ

    def track_colour(self, v, o):
        """track color: 13  /  "#3366ff"  /  none  /  default   (tracks: selected | all | names)"""
        from .ptsl import hex_to_rgb, nearest_colour, COLOUR_BASE
        pt = self.sys.ptsl()
        names = pt.tracks(o.get("tracks", "selected"))
        if not names:
            raise PTSLError("no tracks are selected" if str(o.get("tracks", "selected")).lower() == "selected"
                            else "no tracks to colour")
        word = str(v).strip().lower()
        if word in ("none", "no color", "no colour"):
            index = -1
        elif word == "default":
            index = -2
        elif str(v).strip().startswith("#"):
            index = nearest_colour(pt.palette(), hex_to_rgb(str(v))) + COLOUR_BASE
        else:
            try:
                index = int(v)
            except (TypeError, ValueError):
                raise MacroError(f"track color needs a number, a colour like '#3366ff', none or default (got {v!r})") from None
        pt.run("SetTrackColor", {"track_names": names, "color_index": index})

    def menu(self, v, o):
        parts = v if isinstance(v, list) else [p.strip() for p in str(v).split(">")]
        app = self.app()
        bar = app.attr("AXMenuBar")
        if bar is None:
            raise MacroError("Can't see Pro Tools' menu bar (is Accessibility permission on?)")
        current = bar
        for i, part in enumerate(parts):
            item = next((c for c in E.children(current) if E.name_matches(c, part)), None)
            if item is None:
                raise E.NotFound(f"menu item '{part}' (in {' > '.join(parts[:i]) or 'menu bar'})")
            if i == len(parts) - 1:
                if item.attr("AXEnabled") is False:
                    raise MacroError(f"menu item '{' > '.join(parts)}' is greyed out right now")
                want = o.get("set")
                if want is not None:
                    checked = bool(item.attr("AXMenuItemMarkChar"))
                    if (str(want).lower() in ("on", "true", "enable")) == checked:
                        self.close_menus()
                        return
                item.perform("AXPress")
                return
            sub = next((c for c in E.children(item) if c.attr("AXRole") == "AXMenu"), None)
            if sub is None or not E.children(sub):
                item.perform("AXPress")      # open it so its contents appear
                self.sys.sleep(0.15)
                sub = next((c for c in E.children(item) if c.attr("AXRole") == "AXMenu"), None)
            if sub is None:
                raise E.NotFound(f"submenu '{part}'")
            current = sub

    def close_menus(self):
        code, flags = parse_combo("escape")
        self.sys.key(code, flags)

    def wait_window(self, v, o):
        timeout = seconds(o.get("timeout", WINDOW_TIMEOUT))
        if o.get("gone"):
            end = self.sys.now() + timeout
            while True:
                try:
                    E.find_window(self.app(), v)
                except E.NotFound:
                    return
                if self.sys.now() >= end:
                    raise E.NotFound(f"window '{v}' is still open after {timeout:g}s")
                self.sys.sleep(POLL)
        self.until(lambda: E.find_window(self.app(), v), timeout, f"window '{v}'")

    def wait_element(self, v, o):
        timeout = seconds(o.get("timeout", WINDOW_TIMEOUT))
        if o.get("gone"):
            end = self.sys.now() + timeout
            while True:
                try:
                    E.resolve(self.app(), o.get("window"), o.get("group"), o.get("path"), o.get("kind"), v)
                except E.NotFound:
                    return
                if self.sys.now() >= end:
                    raise E.NotFound(f"'{v}' is still there after {timeout:g}s")
                self.sys.sleep(POLL)
        self.element(dict(o, timeout=timeout), v)

    def checkbox(self, v, o):
        el = self.element(o, v, kind="checkbox")
        want = str(o.get("set", "on")).lower()
        if want in ("toggle",):
            self.press_el(el, o.get("mouse"))
            return
        target = want in ("on", "true", "yes", "enable", "1", "checked")
        if bool(el.attr("AXValue")) == target:
            return
        if el.attr("AXEnabled") is False:
            self.log(f"    '{v}' is greyed out right now; left as it is")
            return
        self.press_el(el, o.get("mouse"))
        if self._wait_value(el, target, 0.6):
            return
        # The press didn't take (some Pro Tools boxes ignore it): click it once with the mouse.
        x, y = self.center(el)
        self.sys.click(x, y)
        if not self._wait_value(el, target, 0.6):
            self.log(f"    couldn't set '{v}' {'on' if target else 'off'}")

    def _wait_value(self, el, target, timeout):
        """Give Pro Tools a moment to update a checkbox before deciding a click didn't work."""
        end = self.sys.now() + timeout
        while True:
            if bool(el.attr("AXValue")) == target:
                return True
            if self.sys.now() >= end:
                return False
            self.sys.sleep(POLL)

    def popup(self, v, o):
        choose = o.get("choose")
        if choose is None:
            raise MacroError("popup needs 'choose:' (the item to pick, e.g. 'Stereo' or 'Bus > Bus 1')")
        el = self.element(o, v, kind=o.get("kind", "popup"))
        self.choose_from(el, choose)

    # ----- pop-up menus -----
    # Pro Tools 2026 draws pop-up menus as small windows (subrole AXDialog) full of
    # menu items; each submenu is another such window inside its menu item.
    @staticmethod
    def _is_menu_window(w):
        return (w.attr("AXRole") == "AXWindow" and not str(w.attr("AXTitle") or "").startswith(("Edit:", "Mix:"))
                and any(c.attr("AXRole") == "AXMenuItem" for c in E.children(w)))

    def _find_menu(self, el):
        """The pop-up menu that's open right now (a real menu, or Pro Tools' menu window).
        Pro Tools' menu windows are checked first: asking the clicked button itself while
        its menu is open makes macOS wait for its full time-out (3 seconds)."""
        app = self.app()
        candidates = []
        for c in E.children(app):
            if c.attr("AXRole") == "AXMenu":
                return c
            if self._is_menu_window(c):
                candidates.append(c)
        if candidates:
            # The top level is the one with a 'search...' item, or else the last one opened.
            for w in candidates:
                if any(E.name_matches(i, "search...") for i in E.children(w)):
                    return w
            return candidates[-1]
        for c in E.children(el):              # a standard Mac pop-up keeps its menu inside it
            if c.attr("AXRole") == "AXMenu":
                return c
        raise E.NotFound("the pop-up menu")

    _mouse_first: set = set()   # windows whose pop-ups only open with a real click (learned)

    def _window_key(self, el):
        try:
            w = el.attr("AXWindow")
            return (str(el.attr("AXRole")), str((w.attr("AXTitle") if w is not None else "") or "")[:40])
        except Exception:  # noqa: BLE001
            return (str(el.attr("AXRole")), "")

    def open_menu(self, el):
        """Open el's pop-up menu and return it, or None if it couldn't be opened.
        Tries a quick Accessibility press, then a real click; remembers where only the
        click works so next time it goes straight to that."""
        key = self._window_key(el)
        if key not in self._mouse_first:
            # Don't wait on the press: macOS doesn't report back until the menu closes
            # (or 3 seconds pass), even though the menu is already open.
            import threading
            threading.Thread(target=lambda: el.perform("AXPress"), daemon=True).start()
            try:
                return self.until(lambda: self._find_menu(el), 0.5, "the pop-up menu")
            except E.NotFound:
                pass
            self.close_menus()
            self.sys.sleep(0.1)
        x, y = self.center(el)
        self.sys.click(x, y)
        try:
            menu = self.until(lambda: self._find_menu(el), 1.5, "the pop-up menu")
            self._mouse_first.add(key)
            return menu
        except E.NotFound:
            return None

    @staticmethod
    def _item_matches(item, name):
        """'[DRUMS]' matches '[DRUMS]' and '[DRUMS] (Stereo)'. Checks the title first (one
        quick question per item) before anything slower."""
        want = E.norm(name)
        title = E.norm(item.attr("AXTitle"))
        if title:
            if "*" in want or "?" in want:
                import fnmatch
                return fnmatch.fnmatchcase(title, want)
            return title == want or re.sub(r"(?i)\s+\((stereo|mono)\)$", "", title) == want
        if E.name_matches(item, name):
            return True
        return any(re.sub(r"(?i)\s+\((stereo|mono)\)$", "", lab) == want for lab in E.labels(item))

    @staticmethod
    def _submenu(item):
        return next((c for c in E.children(item) if c.attr("AXRole") in ("AXMenu", "AXWindow")), None)

    def _press_item(self, item, el, flags=0, root=None, expect=None):
        """Choose a menu item without waiting on macOS (an Accessibility press on Pro Tools'
        menus can take seconds to report back even though it worked straight away).
        Done as soon as the pop-up shows the new value, or our menu has closed. Only if
        the menu is visibly still open is the item clicked with the mouse."""
        import threading
        threading.Thread(target=lambda: item.perform("AXPress"), daemon=True).start()
        end = self.sys.now() + 0.6
        while self.sys.now() < end:
            self.sys.sleep(0.03)
            if self._shows(el, expect) or not self._root_open(root, el):
                return True
        if self._root_open(root, el) and self._on_screen(item):
            x, y = self.center(item)
            self.sys.click(x, y, flags=flags)
            self.sys.sleep(0.15)
        return self._shows(el, expect) or not self._root_open(root, el)

    def _shows(self, el, expect):
        """Does the pop-up now show the chosen value (e.g. '24 Bit')?"""
        if not expect:
            return False
        try:
            text = E.norm(" ".join(E.labels(el) + [str(el.attr("AXValue") or "")])).lower()
        except Exception:  # noqa: BLE001
            return False
        want = E.norm(str(expect)).rstrip("*").lower()
        return bool(want) and want in text

    def _root_open(self, root, el=None):
        """Is *our* menu still open and visible? (Pro Tools keeps invisible menu windows
        around, so 'some menu window exists' isn't enough.)"""
        if root is None:
            return self._menu_still_open(el) if el is not None else False
        try:
            if root.attr("AXRole") is None:
                return False
            app_kids = E.children(self.app())
            if root.attr("AXRole") == "AXWindow" and not any(root == k for k in app_kids):
                return False
            return self._on_screen(root) or root.attr("AXRole") == "AXMenu"
        except Exception:  # noqa: BLE001
            return False

    def _menu_still_open(self, el):
        try:
            self._find_menu(el)
            return True
        except E.NotFound:
            return False

    def choose_from(self, el, choose, all_selected=False, prefer=None):
        """Open el's menu and pick 'A > B > C'.

        One track / one pop-up: walk the menu path and press the item. If that doesn't
        take and our menu is visibly still open, search the menu and click the result.
        Several tracks (all_selected): search the menu and Option+Shift-click the result.
        Return is never pressed: in a dialog it would press the default button (Bounce, OK)."""
        parts = choose if isinstance(choose, list) else [p.strip() for p in str(choose).split(">") if p.strip()]
        import time as _time
        t0 = _time.monotonic()
        root = self.open_menu(el)
        if root is None:
            raise E.NotFound(f"the pop-up menu for {E.describe(el)} didn't open")
        t1 = _time.monotonic()
        if all_selected:
            from .keys import ALT, SHIFT
            self._search_and_click(el, parts[-1], ALT | SHIFT, prefer, root)
            return
        item = self._walk(root, parts) or self._search(root, parts[-1], prefer)
        t2 = _time.monotonic()
        if item is not None and self._press_item(item, el, root=root, expect=parts[-1]):
            t3 = _time.monotonic()
            if t3 - t0 > 1.0:
                self.log(f"    (slow pop-up: open {t1 - t0:.1f}s, find '{parts[-1]}' {t2 - t1:.1f}s, "
                         f"choose {t3 - t2:.1f}s)")
            return
        if self._root_open(root, el):
            self._search_and_click(el, parts[-1], 0, prefer, root)
        elif not self._shows(el, parts[-1]) and item is None:
            raise E.NotFound(f"'{parts[-1]}' in the pop-up menu")

    def _search_and_click(self, el, name, flags, prefer=None, root=None):
        """Type into the open menu's search, then click the matching result (with flags).
        If nothing matches, Escape closes the menu (never Return)."""
        if root is not None and not self._root_open(root, el):
            return
        self.log(f"  (searching the menu for '{name}')")
        self.sys.type_text(name)
        hit, seen = None, []
        end = self.sys.now() + (2.5 if prefer == "plug-in" else 0.8)
        while hit is None:
            self.sys.sleep(0.25)
            try:
                menu = self._find_menu(el)
                items = [(h, p) for h, p in self._all_items(menu, prefer) if self._on_screen(h)]
                hits = [(h, p) for h, p in items if self._item_matches(h, name)]
                if not hits and prefer == "plug-in":
                    # Plug-in results often differ a little ('Renaissance Axx Mono',
                    # 'UADx 1176 Rev A'): take a close match, shortest name first.
                    hits = sorted(((h, p) for h, p in items if self._close_plugin_match(h, name)),
                                  key=lambda x: len(" ".join(E.labels(x[0]))))
                    if hits:
                        self.log(f"  (closest match: '{E.labels(hits[0][0])[0]}')")
                hits.sort(key=lambda x: 0 if x[1] else 1)       # a bus before a track of the same name
                hit = hits[0][0] if hits else None
                seen = [E.labels(h)[0] for h, _ in items if E.labels(h)][:15]
            except E.NotFound:
                pass
            if self.sys.now() >= end:
                break
        if hit is None:
            if seen:
                self.log(f"  (the menu showed: {', '.join(seen)})")
            self.close_menus()
            raise E.NotFound(f"'{name}' in the pop-up menu")
        x, y = self.center(hit)
        if flags:
            self.sys.hold(flags, True)
        try:
            self.sys.click(x, y, flags=flags)
        finally:
            if flags:
                self.sys.hold(flags, False)
        self.sys.sleep(0.3)

    @staticmethod
    def _close_plugin_match(item, name) -> bool:
        from .plugins import same_plugin
        labels = E.labels(item)
        if not labels or E.children(item):          # a submenu (a category), not a plug-in
            return False
        label = re.sub(r"(?i)\s*\((mono|stereo|mono/stereo|m|s)\)$|\s+(mono|stereo)$", "", labels[0]).strip()
        n = re.sub(r"(?i)\s+(mono|stereo)$", "", str(name)).strip()
        return E.norm(label).lower().startswith(E.norm(n).lower()) or same_plugin(label, n)

    def _all_items(self, menu, prefer=None, inside=False, depth=0):
        """Every menu item, with whether it sits under the 'prefer' submenu (e.g. 'bus')."""
        out = []
        if depth > 8:
            return out
        for c in E.children(menu):
            here = inside
            if c.attr("AXRole") == "AXMenuItem":
                out.append((c, inside))
                here = inside or bool(prefer and E.name_matches(c, prefer))
            out.extend(self._all_items(c, prefer, here, depth + 1))
        return out

    @staticmethod
    def _on_screen(el):
        pos, size = el.attr("AXPosition"), el.attr("AXSize")
        return bool(pos and size and size[0] > 0 and size[1] > 0 and pos[0] > -10000)

    def _walk(self, menu, parts):
        current = menu
        for i, part in enumerate(parts):
            item = next((c for c in E.children(current) if self._item_matches(c, part)), None)
            if item is None:
                return None
            if i == len(parts) - 1:
                return item
            sub = self._submenu(item)
            if sub is None or not E.children(sub):
                item.perform("AXPress")
                self.sys.sleep(0.15)
                sub = self._submenu(item)
            if sub is None:
                return None
            current = sub
        return None

    def _search(self, menu, name, prefer=None, depth=0):
        if depth > 5:
            return None
        items = E.children(menu)
        if prefer:   # look in the preferred submenu (e.g. 'bus') first
            items = sorted(items, key=lambda c: 0 if E.name_matches(c, prefer) else 1)
        for item in items:
            sub = self._submenu(item)
            if sub is None and self._item_matches(item, name):
                return item
            if sub is not None:
                found = self._search(sub, name, prefer, depth + 1)
                if found:
                    return found
        return None

    @staticmethod
    def _has_menu(el):
        return any(c.attr("AXRole") == "AXMenu" for c in E.children(el))

    @staticmethod
    def _menu_of(el):
        m = next((c for c in E.children(el) if c.attr("AXRole") == "AXMenu"), None)
        if m is None:
            raise E.NotFound("menu")
        return m

    def set_text(self, v, o):
        """set text: <box>  to: <value>. With 'typing: true' it clicks into the box and types,
        which Pro Tools dialogs need (they ignore text set behind their back)."""
        el = self.element(o, v, kind=o.get("kind", "text field"))
        text = "" if o.get("to") is None else str(o.get("to"))
        if o.get("typing"):
            self.type_into(el, text)
            return
        el.set_attr("AXFocused", True)
        if not el.set_attr("AXValue", text):
            self.sys.key(*parse_combo("cmd+a"))
            self.sys.type_text(text)

    def click_at(self, v, o):
        """Click a spot: [x, y] measured from the top-left of a window, an element, or the screen."""
        if v is None:
            xy = None
        elif isinstance(v, (list, tuple)) and len(v) == 2:
            xy = (float(v[0]), float(v[1]))
        else:
            raise MacroError("click at needs [x, y], e.g. click at: [120, 40]")
        rel = str(o.get("relative to", "element" if o.get("element") is not None else "window")).lower()
        if rel == "screen":
            if xy is None:
                raise MacroError("click at with 'relative to: screen' needs [x, y]")
            x, y = xy
        else:
            if rel == "element":
                el = self.element(o, o.get("element"))
            else:
                el = self.until(lambda: E.find_window(self.app(), o.get("window")),
                                seconds(o.get("timeout", DEFAULT_TIMEOUT)), "window")
            if xy is None:
                x, y = self.center(el)
            else:
                pos = el.attr("AXPosition")
                if not pos:
                    raise MacroError(f"Can't tell where {E.describe(el)} is on screen")
                x, y = pos[0] + xy[0], pos[1] + xy[1]
        flags = 0
        for m in (o.get("modifiers") or "").replace(",", "+").split("+"):
            if m.strip():
                flags |= MODIFIERS[m.strip().lower()]
        self.sys.click(x, y, button=str(o.get("button", "left")).lower(),
                       count=2 if o.get("double") else 1, flags=flags)
