"""Tests that run without a Mac: a fake Pro Tools window stands in for the real one."""
from pathlib import Path

import pytest

from ptdeck import elements as E
from ptdeck import deck as D
from ptdeck.keys import parse_combo, parse_sequence, CMD, SHIFT
from ptdeck.macros import Library, Runner, MacroError, validate
from ptdeck.soundflow import convert, to_yaml, parse_js_object

ROOT = Path(__file__).resolve().parent.parent


class El:
    def __init__(self, role, title=None, children=(), value=None, pos=(0, 0), size=(10, 10), **kw):
        self.a = {"AXRole": role, "AXTitle": title, "AXValue": value, "AXPosition": pos,
                  "AXSize": size, "AXEnabled": True, **kw}
        self.kids = list(children)
        self.presses = 0

    def attr(self, n):
        if n == "AXChildren":
            return self.kids
        return self.a.get(n)

    def set_attr(self, n, v):
        self.a[n] = v
        return True

    def perform(self, action):
        if action != "AXPress":
            return True
        self.presses += 1
        if self.a["AXRole"] == "AXCheckBox":
            self.a["AXValue"] = 0 if self.a["AXValue"] else 1
        if self.a["AXRole"] == "AXRadioButton":
            self.a["AXValue"] = 1
        if self.on_press:
            self.on_press()
        return True

    on_press = None


def import_dialog():
    cb = lambda t, v: El("AXCheckBox", t, value=v)  # noqa: E731
    return El("AXWindow", "Import Session Data", [
        El("AXGroup", "Session Data", [
            El("AXGroup", None, [cb("HEAT Master Settings", 1), cb("Tempo / Meter Map", 1)]),
            cb("Key Signature / Chord Map", 0), cb("Memory Locations (Non-Markers)", 1),
            cb("Window Configurations", 1), cb("Mic PRE Settings", 1),
        ]),
        El("AXGroup", "Timecode Mapping Options", [cb("Adjust Session Start Time to Match Source Start Time", 0)]),
        El("AXGroup", "Main Playlist Options", [El("AXRadioButton", "Import - Replace", value=1),
                                                El("AXRadioButton", "Do Not Import", value=0)]),
        El("AXButton", "Cancel"), El("AXButton", "OK"),
    ], pos=(100, 200))


class FakeSys:
    def __init__(self, app):
        self._app = app
        self.t = 0.0
        self.keys, self.clicks, self.typed = [], [], []

    def app(self):
        return self._app

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def activate(self):
        pass

    def key(self, code, flags=0):
        self.keys.append((code, flags))

    def type_text(self, t):
        self.typed.append(t)

    def click(self, x, y, button="left", count=1, flags=0):
        self.clicks.append((x, y, button, count, flags))


def make_app(windows, menubar=None):
    return El("AXApplication", "Pro Tools", AXWindows=windows, AXMainWindow=windows[0] if windows else None,
              AXMenuBar=menubar)


def lib_with(tmp_path, **macros):
    for name, text in macros.items():
        (tmp_path / f"{name}.yaml").write_text(text)
    return Library(tmp_path)


# ---------- keys ----------

def test_keys():
    assert parse_combo("cmd+a") == (0, CMD)
    assert parse_combo("Cmd+Shift+N") == (45, CMD | SHIFT)
    assert parse_combo("numpad 1") == (83, 0)
    assert parse_combo("return") == (36, 0)
    assert len(parse_sequence("cmd+a, return")) == 2
    with pytest.raises(ValueError):
        parse_combo("cmd+banana")


# ---------- SoundFlow import + running it ----------

def test_import_users_script_and_run_it(tmp_path):
    js = (ROOT / "soundflow-scripts" / "eas-session-data.js").read_text()
    macro, warnings = convert(js, "EAS Session Data")
    actions = [next(iter(s)) for s in macro["steps"]]
    assert actions == ["run macro", "wait for window", "press"] + ["checkbox"] * 7 + ["click", "click"]
    assert macro["steps"][0]["run macro"] == "2025 Import Session Data"   # commented-out commands ignored
    assert not any("todo" in s for s in macro["steps"])
    assert len(warnings) == 1

    (tmp_path / "eas.yaml").write_text(to_yaml(macro))
    (tmp_path / "pre.yaml").write_text("name: 2025 Import Session Data\nsteps:\n- note: opens the dialog\n")
    dlg = import_dialog()
    sysm = FakeSys(make_app([El("AXWindow", "Edit: Song"), dlg]))
    Runner(sysm, Library(tmp_path), log=lambda m: None).run("EAS Session Data")

    vals = {E.labels(c)[0]: c.attr("AXValue") for c in E.find_all(dlg, "AXCheckBox")}
    assert vals == {"HEAT Master Settings": 0, "Tempo / Meter Map": 0, "Key Signature / Chord Map": 0,
                    "Memory Locations (Non-Markers)": 0, "Window Configurations": 0, "Mic PRE Settings": 0,
                    "Adjust Session Start Time to Match Source Start Time": 1}
    assert E.find_all(dlg, "AXRadioButton", "Do Not Import")[0].attr("AXValue") == 1
    assert E.find_all(dlg, "AXButton", "OK")[0].presses == 1
    assert sysm.keys == [(0, CMD)]


def test_waits_for_window_that_appears_later(tmp_path):
    lib = lib_with(tmp_path, m="steps:\n- wait for window: Import Session Data\n- click: OK\n  window: Import Session Data\n")
    app = make_app([El("AXWindow", "Edit: Song")])
    sysm = FakeSys(app)
    real_sleep = sysm.sleep

    def sleep(s):
        real_sleep(s)
        if sysm.t > 1.0 and len(app.a["AXWindows"]) == 1:
            app.a["AXWindows"].append(import_dialog())
    sysm.sleep = sleep
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert sysm.t >= 1.0


def test_missing_element_gives_clear_error(tmp_path):
    lib = lib_with(tmp_path, m="steps:\n- click: Nope\n  window: Import Session Data\n  timeout: 1\n")
    sysm = FakeSys(make_app([import_dialog()]))
    with pytest.raises(MacroError) as e:
        Runner(sysm, lib, log=lambda m: None).run("m")
    assert "step 1" in str(e.value) and "Nope" in str(e.value)


def test_optional_step_is_skipped(tmp_path):
    lib = lib_with(tmp_path, m="steps:\n- click: Nope\n  window: Import Session Data\n  timeout: 0.1\n  optional: true\n- press: return\n")
    sysm = FakeSys(make_app([import_dialog()]))
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert sysm.keys == [(36, 0)]


def test_menu_click(tmp_path):
    new = El("AXMenuItem", "New…")
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "Track", [El("AXMenu", None, [new])])])
    lib = lib_with(tmp_path, m="steps:\n- menu: Track > New...\n")
    Runner(FakeSys(make_app([El("AXWindow", "Edit: x")], bar)), lib, log=lambda m: None).run("m")
    assert new.presses == 1


def test_click_zone_relative_to_window(tmp_path):
    lib = lib_with(tmp_path, m="steps:\n- click at: [10, 20]\n  window: Import Session Data\n  double: true\n")
    sysm = FakeSys(make_app([import_dialog()]))
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert sysm.clicks == [(110, 220, "left", 2, 0)]


def test_popup(tmp_path):
    stereo = El("AXMenuItem", "Stereo")
    pop = El("AXPopUpButton", "Format", [El("AXMenu", None, [El("AXMenuItem", "Mono"), stereo])])
    lib = lib_with(tmp_path, m="steps:\n- popup: Format\n  choose: Stereo\n  window: New Tracks\n")
    Runner(FakeSys(make_app([El("AXWindow", "New Tracks", [pop])])), lib, log=lambda m: None).run("m")
    assert pop.presses == 1 and stereo.presses == 1


def test_converter_marks_unknown_code_as_todo():
    js = 'sf.ui.proTools.appActivateMainWindow();\nconst x = 5;\nsf.wait({intervalMs: 200});\n' \
         'sf.ui.proTools.mainWindow.groups.whoseTitle.startsWith("Track").first.buttons[1].mouseClickElement({relativePosition:{x:5,y:6}});'
    macro, warnings = convert(js, "t")
    assert macro["steps"][0] == {"activate": "Pro Tools"}
    assert "todo" in macro["steps"][1]
    assert macro["steps"][2] == {"wait": "200ms"}
    assert macro["steps"][3] == {"click at": [5, 6], "element": "#2", "kind": "button", "group": "Track*"}
    assert len(warnings) == 1


def test_parse_js_object():
    assert parse_js_object("{ keys: 'cmd+a', n: 2, ok: true, path: [\"A\", 'B'], }") == \
        {"keys": "cmd+a", "n": 2, "ok": True, "path": ["A", "B"]}


def test_validate_catches_typos(tmp_path):
    lib = lib_with(tmp_path, m="steps:\n- clik: OK\n- press: cmd+banana\n- click: OK\n  kind: buton\n")
    probs = validate(lib.get("m"), lib)
    assert len(probs) == 3


def test_shipped_files_are_valid():
    lib = Library(ROOT / "macros")
    for m in lib.all():
        assert not [p for p in validate(m) if "todo" not in p], m["name"]
    cfg = D.load_config(ROOT / "deck.yaml")
    assert D.check_config(cfg, ROOT) == []


# ---------- deck ----------

def test_layout_and_folders():
    cfg = {"home": "Home", "pages": {
        "Home": [{"label": "A", "macro": "x"}, {"label": "F", "folder": "Sub"}, {"label": "Z", "key": 5}],
        "Sub": ["blank", {"label": "B", "macro": "y"}]}}
    home = D.layout(cfg, "Home", 6)
    assert [b and b["label"] for b in home] == ["A", "F", None, None, "Z", None]
    sub = D.layout(cfg, "Sub", 6)
    assert sub[0]["back"] and sub[1] is None and sub[2]["label"] == "B"


def test_controller_navigation(tmp_path):
    (tmp_path / "deck.yaml").write_text(
        "home: Home\npages:\n  Home:\n    - {label: F, folder: Sub}\n    - {label: M, macro: x}\n  Sub:\n    - {label: B, macro: y}\n")
    c = D.DeckController(tmp_path, runner=None, log=lambda m: None)
    c.draw()
    c.pressed(1)
    assert c.jobs.get_nowait()[2]["macro"] == "x"
    c.pressed(0)
    assert c.page == "Sub"
    c.pressed(0)          # Back
    assert c.page == "Home"


def test_render_sizes():
    for size in (72, 80, 96, 120):
        img = D.render({"label": "Import Session Data", "icon": "import.png", "color": "#123456"}, size, ROOT, "error")
        assert img.size == (size, size)


# ---------- Pro Tools Scripting SDK ----------

from ptdeck import ptsl as P  # noqa: E402


def test_ptsl_encoding_roundtrip():
    raw = P.encode_request(153, '{"a": 1}', "S1")
    msg = P.decode_message(raw)
    header = P.decode_message(msg[1][0])
    assert header[2] == [153] and header[3] == [2026] and header[4] == [b"S1"] and header[5] == [4]
    assert msg[2] == [b'{"a": 1}']
    # A response: header{status=3}, body
    resp = P._field_bytes(1, P._field_varint(3, 3)) + P._field_bytes(2, b'{"ok": true}')
    assert P.decode_response(resp) == (3, '{"ok": true}', "")


def test_ptsl_command_names():
    assert P.command_number("SetTrackColor") == 153
    assert P.command_number("CId_SaveSession") == P.COMMANDS["SaveSession"]
    with pytest.raises(P.PTSLError):
        P.command_number("MakeItSoundGood")


class FakePTSL:
    def __init__(self):
        self.sent = []

    def run(self, cmd, body=None):
        self.sent.append((cmd, body))
        return {}

    def tracks(self, which="selected"):
        return ["Kick", "Snare"] if which == "selected" else P.PTSL.tracks(self, which)

    def palette(self):
        return [(44, 0, 252), (255, 0, 0), (0, 255, 0)]


def test_track_colour_steps(tmp_path):
    lib = lib_with(tmp_path, m="steps:\n- track color: '#00ee00'\n- track colour: 12\n  tracks: Bass, Gtr\n"
                                  "- track color: none\n- pro tools: SaveSession\n")
    sysm = FakeSys(make_app([]))
    pt = FakePTSL()
    sysm.ptsl = lambda: pt
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert pt.sent == [
        ("SetTrackColor", {"track_names": ["Kick", "Snare"], "color_index": 2 + P.COLOUR_BASE}),
        ("SetTrackColor", {"track_names": ["Bass", "Gtr"], "color_index": 12}),
        ("SetTrackColor", {"track_names": ["Kick", "Snare"], "color_index": -1}),
        ("SaveSession", {}),
    ]


# ---------- newer steps ----------

class SessionPTSL(FakePTSL):
    def run(self, cmd, body=None):
        self.sent.append((cmd, body))
        return {
            "GetSessionName": {"session_name": "My Song.07"},
            "GetSessionPath": {"session_path": {"path": "/Users/me/Sessions/My Song/My Song.07.ptx"}},
            "GetSessionSampleRate": {"sample_rate": "SRate_48000"},
            "GetTrackList": {"track_list": [
                {"name": "Vox", "type": "TType_Audio", "track_attributes": {"contains_clips": True}},
                {"name": "Audio 3", "type": "TType_Audio", "track_attributes": {"contains_clips": False}},
                {"name": "Bus", "type": "TType_Aux", "track_attributes": {"contains_clips": False}}]},
        }.get(cmd, {})


def run_steps(tmp_path, yaml_text, pt=None):
    lib = lib_with(tmp_path, m=yaml_text)
    sysm = FakeSys(make_app([]))
    sysm.ptsl = lambda: pt
    sysm.midi = []
    sysm.midi_cc = lambda port, ch, cc, val: sysm.midi.append((port, ch, cc, val))
    Runner(sysm, lib, log=lambda m: None).run("m")
    return sysm


def test_save_new_version(tmp_path):
    pt = SessionPTSL()
    run_steps(tmp_path, "steps:\n- save new version\n", pt)
    assert pt.sent[0] == ("SaveSession", None) or pt.sent[0][0] == "SaveSession"
    assert pt.sent[-1] == ("SaveSessionAs", {"session_name": "My Song.08",
                                             "session_location": "/Users/me/Sessions/My Song"})


def test_delete_empty_audio_tracks(tmp_path):
    pt = SessionPTSL()
    run_steps(tmp_path, "steps:\n- delete empty audio tracks:\n  tracks: selected\n", pt)
    assert pt.sent[-1][0] == "DeleteTracks" and pt.sent[-1][1]["track_names"] == ["Audio 3"]


def test_bounce_mix_name(tmp_path):
    import datetime
    pt = SessionPTSL()
    run_steps(tmp_path, 'steps:\n- bounce mix: "{date}_{session}_EASMIX_{rate}_{bits}"\n  source: Main Out\n', pt)
    cmd, body = pt.sent[-1]
    assert cmd == "ExportMix"
    assert body["file_name"] == f"{datetime.date.today():%y%m%d}_My Song.07_EASMIX_48_24b"
    assert body["audio_info"]["bit_depth"] == "BDepth_24" and body["audio_info"]["sample_rate"] == "SRate_48000"
    assert body["mix_source_list"] == [{"source_type": "EMSType_Output", "name": "Main Out"}]


def test_midi_from_soundflow(tmp_path):
    js = ("function setCab() {\n  sf.midi.sendCC({ externalMidiPort: 'Maschine MK3', midiChannel: 1, midiCC: 104, value: 127, });\n"
          "  sf.midi.sendCC({ externalMidiPort: 'Maschine MK3', midiChannel: 1, midiCC: 105, value: 0, });\n}\n\nsetCab();\n")
    macro, _ = convert(js, "m")
    (tmp_path / "m.yaml").write_text(to_yaml(macro))
    lib = Library(tmp_path)
    sysm = FakeSys(make_app([]))
    sysm.midi = []
    sysm.midi_cc = lambda port, ch, cc, val: sysm.midi.append((port, ch, cc, val))
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert sysm.midi == [("Maschine MK3", 1, 104, 127), ("Maschine MK3", 1, 105, 0)]


def test_audiosuite_found_in_any_submenu(tmp_path):
    plug = El("AXMenuItem", "RX 11 De-click")
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "AudioSuite", [El("AXMenu", None, [
        El("AXMenuItem", "EQ", [El("AXMenu", None, [El("AXMenuItem", "EQ3")])]),
        El("AXMenuItem", "Noise Reduction", [El("AXMenu", None, [plug])])])])])
    app = make_app([El("AXWindow", "Edit: x")], bar)
    plug.on_press = lambda: app.a["AXWindows"].append(El("AXWindow", "Audio Suite: RX 11 De-click"))
    lib = lib_with(tmp_path, m="steps:\n- audiosuite: RX 11 De-click\n")
    Runner(FakeSys(app), lib, log=lambda m: None).run("m")
    assert plug.presses == 1


def test_rebuilt_macros_are_valid():
    for f in (ROOT / "rebuilt").glob("*.yaml"):
        m = Library(ROOT / "rebuilt").load(f)
        assert validate(m) == [], f.name


def test_slider_toggle(tmp_path):
    sl = El("AXSlider", "AB Switch", value=0.0, AXMinValue=0.0)
    acts = []
    sl.perform = lambda a: acts.append(a) or True
    win = El("AXWindow", "Plug-in: ADPTR MetricAB", [El("AXGroup", "FXTDMEditView", [sl])])
    lib = lib_with(tmp_path, m="steps:\n- slider: AB Switch\n  window: 'Plug-in: ADPTR MetricAB'\n")
    Runner(FakeSys(make_app([win])), lib, log=lambda m: None).run("m")
    sl.a["AXValue"] = 1.0
    Runner(FakeSys(make_app([win])), lib, log=lambda m: None).run("m")
    assert acts == ["AXIncrement", "AXDecrement"]


# ---------- track headers (modelled on a real Pro Tools 2026.4 Edit window) ----------

def header(name, kind="Audio", inserts=None, sends=None, output="(PRINT)"):
    inserts, sends = inserts or {}, sends or {}
    ins, snd = [], []
    for L in "ABCDEFGHIJ":
        state, plug = inserts.get(L, ("unassigned", "unassigned"))
        ins.append(El("AXButton", f"Insert selector {L}", value=state))
        ins.append(El("AXButton", f"Insert Assignment {L}", value=plug))
        s_state, s_name = sends.get(L, ("unassigned", "unassigned"))
        snd.append(El("AXButton", f"Send selector {L}", value=s_state))
        snd.append(El("AXButton", f"Send Assignment {L}", value=s_name))
    io = El("AXGroup", "Audio IO", [El("AXPopUpButton", f"Audio Output Path selector\n{output} (Stereo)", value=output)])
    return El("AXGroup", f"{name} - {kind} Track", [
        El("AXGroup", "Inserts A-E", ins[:10]), El("AXGroup", "Inserts F-J", ins[10:]),
        El("AXGroup", "Sends A-E", snd[:10]), El("AXGroup", "Sends F-J", snd[10:]), io])


def plugin_menu(*names):
    return El("AXMenu", None, [El("AXMenuItem", "no insert"), El("AXMenuItem", "plug-in", [El("AXMenu", None, [
        El("AXMenuItem", cat, [El("AXMenu", None, [El("AXMenuItem", n) for n in plugs])]) for cat, plugs in names])])])


class TrackSys(FakeSys):
    def __init__(self, app, selected):
        super().__init__(app)
        pt = FakePTSL()
        pt.tracks = lambda which="selected": selected if which == "selected" else P.PTSL.tracks(pt, which)
        self._pt = pt
        self.held = []

    def ptsl(self):
        return self._pt

    def hold(self, flags, down):
        self.held.append((flags, down))


def edit_app(*headers):
    win = El("AXWindow", "Edit: My Song", list(headers))
    return make_app([win]), win


def menu_on_press(app, el, menu):
    """Pro Tools shows plug-in/bus menus as a free-floating menu of the app."""
    def opened():
        app.kids = [k for k in app.kids if k.attr("AXRole") != "AXMenu"] + [menu]
    el.on_press = opened


def test_plugin_window_by_name_and_slot(tmp_path):
    out = header("-OUT MASTER", "Master", {"H": ("", "ADPTR MetricAB")})
    app, _ = edit_app(header("drums"), out)
    asg = E.find_one(out, "button", "Insert Assignment H")
    lib = lib_with(tmp_path, a="steps:\n- plugin window: ADPTR MetricAB\n  track: '-OUT MASTER'\n  set: open\n",
                   b="steps:\n- plugin window: 8\n  track: '-OUT MASTER'\n")
    Runner(TrackSys(app, []), lib, log=lambda m: None).run("a")
    Runner(TrackSys(app, []), lib, log=lambda m: None).run("b")
    assert asg.presses == 2
    E.find_one(out, "button", "Insert selector H").a["AXValue"] = "open"
    lib2 = lib_with(tmp_path, c="steps:\n- plugin window: ADPTR MetricAB\n  track: '-OUT MASTER'\n  set: open\n")
    Runner(TrackSys(app, []), lib2, log=lambda m: None).run("c")
    assert asg.presses == 2            # already open: left alone


def test_insert_plugin_first_free(tmp_path):
    gtr = header("Gtr", inserts={"A": ("", "Pro-Q 4"), "B": ("", "Comp")})
    app, _ = edit_app(gtr)
    menu = plugin_menu(("EQ", ["Pro-Q 4"]), ("SubMission Audio", ["LockOn"]))
    sel_c = E.find_one(gtr, "button", "Insert selector C")
    menu_on_press(app, sel_c, menu)
    lib = lib_with(tmp_path, m="steps:\n- insert plugin: LockOn\n  slot: first free\n")
    Runner(TrackSys(app, ["Gtr"]), lib, log=lambda m: None).run("m")
    lockon = E.find_all(menu, "AXMenuItem", "LockOn")[0]
    assert sel_c.presses == 1 and lockon.presses == 1


def test_send_to_bus_for_all_selected(tmp_path):
    t1, t2 = header("Kick"), header("Snare")
    app, _ = edit_app(t1, t2)
    target = El("AXMenuItem", "//[PARA DRUMS]")
    menu = El("AXMenu", None, [El("AXMenuItem", "no send"), El("AXMenuItem", "Stereo", [El("AXMenu", None, [
        El("AXMenuItem", "track", [El("AXMenu", None, [El("AXMenuItem", "//[PARA DRUMS]")])]),
        El("AXMenuItem", "bus", [El("AXMenu", None, [target])])])])])
    sel = E.find_one(t1, "button", "Send selector A")
    menu_on_press(app, sel, menu)
    lib = lib_with(tmp_path, m="steps:\n- send: Stereo > bus > //[PARA DRUMS]\n  slot: 1\n  all selected: true\n")
    sysm = TrackSys(app, ["Kick", "Snare"])
    Runner(sysm, lib, log=lambda m: None).run("m")
    from ptdeck.keys import ALT, SHIFT
    assert target.presses == 1 and sysm.held == [(ALT | SHIFT, True), (ALT | SHIFT, False)]


def test_output_found_without_exact_path(tmp_path):
    t = header("Kick")
    app, _ = edit_app(t)
    target = El("AXMenuItem", "[DRUMS]")
    menu = El("AXMenu", None, [El("AXMenuItem", "bus", [El("AXMenu", None, [target])])])
    menu_on_press(app, E.find_one(t, None, "Audio Output Path selector*"), menu)
    lib = lib_with(tmp_path, m="steps:\n- output: Stereo > bus > [DRUMS]\n")
    Runner(TrackSys(app, ["Kick"]), lib, log=lambda m: None).run("m")
    assert target.presses == 1


def test_remove_inactive(tmp_path):
    t = header("Vox", inserts={"A": ("inactive", "Old EQ"), "B": ("", "Comp")},
               sends={"C": ("inactive", "//[ROOM]")})
    app, _ = edit_app(t)
    no_insert, no_send = El("AXMenuItem", "no insert"), El("AXMenuItem", "no send")
    menu_on_press(app, E.find_one(t, "button", "Insert selector A"), El("AXMenu", None, [no_insert]))
    menu_on_press(app, E.find_one(t, "button", "Send selector C"), El("AXMenu", None, [no_send]))
    confirm = El("AXButton", "Remove")
    dialog = El("AXWindow", "", [confirm])
    no_insert.on_press = lambda: app.a["AXWindows"].append(dialog)
    confirm.on_press = lambda: app.a["AXWindows"].remove(dialog)
    lib = lib_with(tmp_path, m="steps:\n- remove inactive: both\n")
    Runner(TrackSys(app, ["Vox"]), lib, log=lambda m: None).run("m")
    assert no_insert.presses == 1 and no_send.presses == 1 and confirm.presses == 1
    assert E.find_one(t, "button", "Insert selector B").presses == 0


# ---------- Manager ----------

def test_manager_edits_keep_layout(tmp_path):
    import shutil
    from ptdeck.manager import Manager
    shutil.copy(ROOT / "deck.yaml", tmp_path / "deck.yaml")
    shutil.copytree(ROOT / "icons", tmp_path / "icons")
    (tmp_path / "macros").mkdir()
    m = Manager(tmp_path)
    before = m.state()["pages"]
    m.set_button("Home", 2, {"macro": "Colour Drums", "label": "Drums", "color": "#aa2200"})
    after = m.state()["pages"]
    assert after["Home"][2]["macro"] == "Colour Drums"
    strip = lambda pg: [b and {k: v for k, v in b.items() if k not in ("_status", "key")} for b in pg]  # noqa: E731
    assert [x for i, x in enumerate(strip(after["Home"])) if i != 2] == [x for i, x in enumerate(strip(before["Home"])) if i != 2]
    m.move_button("Home", 2, 3)
    assert m.state()["pages"]["Home"][3]["macro"] == "Colour Drums" and m.state()["pages"]["Home"][2] is None
    with pytest.raises(ValueError):
        m.set_button("Mix Prep", 0, {"macro": "x"})          # Back button
    m.set_button("Home", 2, {"folder": "Brand New", "label": "New"})
    assert "Brand New" in m.state()["pages"]
    m.page_action("rename", "Brand New", "Renamed")
    assert m.state()["pages"]["Home"][2]["folder"] == "Renamed"
    m.page_action("delete", "Renamed")
    assert m.state()["pages"]["Home"][2] is None
    m.set_button("Home", 2, None)
    # Every other page is unchanged after all that.
    for name in before:
        if name != "Home":
            assert strip(m.state()["pages"][name]) == strip(before[name])
