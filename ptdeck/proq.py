"""FabFilter Pro-Q 3 -> Pro-Q 4 converter (rebuilt from Tristan Hoogland's SoundFlow script).

For each active Pro-Q 3: save its settings as a temporary preset (Control-click on
the preset area > Save As), swap the insert to Pro-Q 4 with the plug-in selector,
then load that preset in Pro-Q 4 (click its preset area and type the name).

Pro-Q 4's window must be at MEDIUM scale. Pro-Q 3 can be any scale: each is tried.
"""
from __future__ import annotations

import posixpath
from pathlib import Path

from . import elements as E
from .keys import CTRL, parse_combo

TEMP_PRESET = "TH_q3q4_Convert"
PRESET_DIR = Path("~/Documents/FabFilter/Presets/Pro-Q 3").expanduser()
APPENDIX = "_q3q4Convert"
Q3, Q4 = "FabFilter Pro-Q 3", "FabFilter Pro-Q 4"
# Where Pro-Q 3's preset area sits, as a fraction of its window, at each scale.
Q3_PRESET_POS = {"mini": (0.74, 0.29), "small": (0.715, 0.225), "medium": (0.69, 0.20),
                 "large": (0.67, 0.175), "very large": (0.655, 0.155)}
Q4_PASTE_POS = (0.69, 0.18)          # Pro-Q 4 at MEDIUM scale


def convert(runner, v, o):
    from .macros import MacroError
    sys = runner.sys
    preset_file = PRESET_DIR / f"{TEMP_PRESET}.ffp"
    if not preset_file.exists():
        # Pro-Q 4 only sees presets that existed when the session was opened.
        preset_file.parent.mkdir(parents=True, exist_ok=True)
        preset_file.write_text("")
        raise MacroError("First run: the temporary preset file has been created. Close and reopen your "
                         "session once (Pro-Q 4 needs to see the file), then run the converter again.")

    scope = str(o.get("scope", v or "ask")).lower()
    if scope == "ask":
        scope = (sys.choose(["Single Instance", "Selected Tracks", "Entire Session"],
                            "What Pro-Q 3 to Pro-Q 4 conversion do you want?",
                            "Pro-Q 3 to Pro-Q 4 Converter") or "").lower()
        if not scope:
            runner.log("  cancelled")
            return
        sys.activate()                     # back to Pro Tools after the dialog
        sys.sleep(0.3)
    scale = str(o.get("scale", "medium")).lower()
    order = [scale] + [s for s in Q3_PRESET_POS if s != scale]

    if scope.startswith("single"):
        win = _q3_window(runner)
        if win is None:
            raise MacroError("Open the Pro-Q 3 you want to convert, then press the button again.")
        track = str(_popup_value(win, "Track Selector*") or "")
        n = _convert_window(runner, win, track, order)
        runner.log(f"  converted {n} instance")
        return

    pt = sys.ptsl()
    pt.run("SaveSession")
    _save_as_copy(runner)
    tracks = runner.target_tracks({"tracks": "selected" if scope.startswith("selected") else "all"})
    done = 0
    for track in tracks:
        try:
            header = runner.track_header(track, "Inserts A-E", "Inserts F-J")
        except E.NotFound:
            continue                       # hidden tracks / VCAs
        for letter in runner.SLOTS:
            state, asg = runner._try_slot(header, "Insert", letter)
            if asg is None or str(asg.attr("AXValue") or "") != Q3 or str(state or "") == "inactive":
                continue
            runner.plugin_window(letter, {"track": track, "set": "open"})
            win = runner.until(lambda: _q3_window(runner) or _missing(), 5, "the Pro-Q 3 window")
            done += _convert_window(runner, win, track, order)
            runner._btn_cache = None
    pt.run("SaveSession")
    runner.log(f"  converted {done} Pro-Q 3 instance(s)")
    sys.alert(f"Pro-Q 3 to Pro-Q 4 conversion complete: {done} instance(s).")


def _missing():
    raise E.NotFound("the Pro-Q 3 window")


def _q3_window(runner):
    for w in E.window_list(runner.app()):
        if str(w.attr("AXTitle") or "").startswith(f"Plug-in: {Q3}"):
            return w
    return None


def _popup_value(win, pattern):
    hits = E.find_all(win, "AXPopUpButton", pattern, max_depth=2)
    return hits[0].attr("AXValue") if hits else None


def _frame(el):
    pos, size = el.attr("AXPosition"), el.attr("AXSize")
    return pos[0], pos[1], size[0], size[1]


def _convert_window(runner, win, track, order) -> int:
    from .macros import MacroError
    sys = runner.sys
    bypass = E.find_all(win, "AXButton", "Effect Bypass", max_depth=2)
    if bypass and str(bypass[0].attr("AXValue") or "") == "on":
        runner.log(f"  skipped a bypassed Pro-Q 3 on '{track}'")
        return 0
    if E.find_all(win, "AXButton", "Master Link button", max_depth=2):
        link = E.find_all(win, "AXButton", "Master Link button", max_depth=2)[0]
        if str(link.attr("AXValue") or "") == "":
            raise MacroError("Unlinked multi-mono Pro-Q 3 isn't supported (same as the SoundFlow version)")

    # 1. Save Pro-Q 3's settings as the temporary preset.
    preset = PRESET_DIR / f"{TEMP_PRESET}.ffp"
    saved = False
    for scale in order:
        x, y, w, h = _frame(win)
        fx, fy = Q3_PRESET_POS[scale]
        sys.click(x + w * fx, y + h * fy, flags=CTRL)
        sys.sleep(0.2)
        for _ in range(2):
            sys.key(*parse_combo("down"))
        sys.key(*parse_combo("return"))
        if preset.exists():
            preset.unlink()
        try:
            save = runner.until(lambda: E.find_window(runner.app(), "Save"), 1.0, "the Save window")
        except E.NotFound:
            sys.key(*parse_combo("escape"))
            continue
        field = E.find_all(save, "AXTextField", max_depth=4)
        if field:
            field[0].set_attr("AXValue", TEMP_PRESET)
        else:
            sys.key(*parse_combo("cmd+a"))
            sys.type_text(TEMP_PRESET)
        E.find_one(save, "button", "Save").perform("AXPress")
        runner.until(lambda: _gone(runner, "Save"), 5, "the Save window to close")
        saved = True
        break
    if not saved:
        raise MacroError("couldn't open Pro-Q 3's preset menu at any window scale")

    # 2. Swap the insert to Pro-Q 4, keeping the same width.
    width = _width(runner, track)
    selector = E.find_all(win, "AXPopUpButton", "Plugin Selector*", max_depth=2)
    if not selector:
        raise MacroError("couldn't find the plug-in selector in the Pro-Q 3 window")
    runner.choose_from(selector[0], ["multichannel plug-in", "EQ", f"{Q4} ({width})"])
    sys.sleep(0.4)
    dialog = _dialog_with(runner, "Cancel")
    if dialog is not None:      # Pro Tools asks about automation: leave this one alone
        E.find_one(dialog, "button", "Cancel").perform("AXPress")
        runner.log(f"  skipped a Pro-Q 3 with automation on '{track}'")
        return 0

    # 3. Load the preset in Pro-Q 4 (window must be at MEDIUM scale).
    q4 = runner.until(lambda: E.find_window(runner.app(), f"Plug-in: {Q4}*"), 5, "the Pro-Q 4 window")
    sys.sleep(0.3)
    x, y, w, h = _frame(q4)
    sys.click(x + w * Q4_PASTE_POS[0], y + h * Q4_PASTE_POS[1])
    sys.sleep(0.2)
    sys.type_text(TEMP_PRESET)
    sys.sleep(0.2)
    sys.key(*parse_combo("return"))
    sys.key(*parse_combo("return"))
    sys.sleep(0.2)
    btn = q4.attr("AXCloseButton")
    if btn is not None:
        btn.perform("AXPress")
    runner.log(f"  converted Pro-Q 3 → Pro-Q 4 on '{track}'")
    return 1


def _gone(runner, title):
    try:
        E.find_window(runner.app(), title)
    except E.NotFound:
        return True
    raise E.NotFound(f"'{title}' is still open")


def _dialog_with(runner, button):
    for w in E.window_list(runner.app()):
        t = str(w.attr("AXTitle") or "")
        if t.startswith(("Edit:", "Mix:", "Plug-in:")):
            continue
        if E.find_all(w, "AXButton", button, max_depth=3):
            return w
    return None


def _width(runner, track) -> str:
    """'stereo' or 'mono', from the track's format (Pro Tools SDK)."""
    try:
        res = runner.sys.ptsl().run("GetTrackList", {"page_limit": 10000, "pagination_request": {"limit": 10000, "offset": 0},
                                                     "track_filter_list": [{"filter": "TLFilter_All", "is_inverted": False}]})
        fmt = next((t.get("format", "") for t in res.get("track_list", []) if t.get("name") == track), "")
        return "mono" if "Mono" in fmt else "stereo"
    except Exception:  # noqa: BLE001
        return "stereo"


def _save_as_copy(runner):
    """Work on a copy: 'Song.ptx' -> 'Song_q3q4Convert.ptx' (like the original script)."""
    name, path = runner.session_info()
    base = name[:-4] if name.lower().endswith(".ptx") else name
    if base.endswith(APPENDIX):
        return
    runner.sys.ptsl().run("SaveSessionAs", {"session_name": base + APPENDIX,
                                            "session_location": posixpath.dirname(path)})
    runner.log(f"  working on a copy: {base + APPENDIX}")
