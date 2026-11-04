"""Tests that run without a Mac: a fake Pro Tools window stands in for the real one."""
from pathlib import Path

import pytest

from ptdeck import elements as E
from ptdeck import deck as D
from ptdeck.keys import parse_combo, parse_sequence, CMD, SHIFT
from ptdeck.macros import Library, Runner, MacroError, validate
from ptdeck.soundflow import convert, to_yaml, parse_js_object

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "my-deck"                          # rebuilt macros and icons that ship with PT Deck
FIXTURES = ROOT / "tests" / "fixtures"
TEST_DECK = FIXTURES / "deck.yaml"               # a fixed deck layout, so tests don't follow your live deck


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
    js = (FIXTURES / "eas-session-data.js").read_text()
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
    lib = Library(DECK / "rebuilt")
    for m in lib.all():
        assert not [p for p in validate(m) if "todo" not in p], m["name"]
    cfg = D.load_config(TEST_DECK)
    assert D.check_config(cfg, DECK) == []


# ---------- deck ----------

def test_layout_and_folders():
    cfg = {"home": "Home", "pages": {
        "Home": [{"label": "A", "macro": "x"}, {"label": "F", "folder": "Sub"}, {"label": "Z", "key": 5}],
        "Sub": ["blank", {"label": "B", "macro": "y"}]}}
    home = D.layout(cfg, "Home", 6)
    assert [b and b["label"] for b in home] == ["A", "F", None, None, "Z", None]
    sub = D.layout(cfg, "Sub", 6)
    assert sub[0]["back"] and sub[1]["carpet"] and sub[1]["banner"] and sub[2]["label"] == "B"
    assert D.layout(dict(cfg, **{"title pattern": "none"}), "Sub", 6)[1] is None      # carpet can be off


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
        img = D.render({"label": "Import Session Data", "icon": "import.png", "color": "#123456"}, size, DECK, "error")
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

    def run(self, cmd, body=None, timeout=None):
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
    def run(self, cmd, body=None, timeout=None):
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
    field = El("AXTextField", None, value="My Song.07")
    dlg = El("AXWindow", "Save", [El("AXGroup", None, [field]), El("AXButton", "Save")])
    item = El("AXMenuItem", "Save As...")
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "File", [El("AXMenu", None, [item])])])
    app = make_app([El("AXWindow", "Edit: My Song.07")], bar)
    sysm = FakeSys(app)
    sysm.ptsl = lambda: pt
    sysm.pasted = []
    sysm.paste = sysm.pasted.append

    def key(code, flags=0):
        from ptdeck.keys import CTRL
        sysm.keys.append((code, flags))
        if (code, flags) == (1, CMD | CTRL):                  # Control+Cmd+S opens Save As
            app.a["AXWindows"].append(dlg)
        if code == 36 and dlg in app.a["AXWindows"]:          # Return saves and closes the dialog
            app.a["AXWindows"].remove(dlg)
    sysm.key = key
    Runner(sysm, lib_with(tmp_path, m="steps:\n- save new version\n"), log=lambda m: None).run("m")
    from ptdeck.keys import CTRL
    assert (1, CMD) in sysm.keys and (1, CMD | CTRL) in sysm.keys and sysm.pasted == ["My Song.08"]
    assert not any(c == "SaveSessionAs" for c, _ in pt.sent)


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
    for f in (DECK / "rebuilt").glob("*.yaml"):
        m = Library(DECK / "rebuilt").load(f)
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


def bus_menu(app, sel, name):
    """A Pro Tools 2026 style menu for one selector; choosing the bus closes it."""
    item = El("AXMenuItem", f"{name} (Stereo)")
    menu = El("AXWindow", None, [El("AXMenuItem", "search..."),
                                 El("AXMenuItem", "track", [El("AXWindow", None, [El("AXMenuItem", name)])]),
                                 El("AXMenuItem", "bus", [El("AXWindow", None, [item])])])
    menu_on_press(app, sel, menu)
    item.on_press = lambda: setattr(app, "kids", [])
    return item


def test_send_for_each_selected_track(tmp_path):
    """Sends: if the Option+Shift choice doesn't reach every track, each one missing it is set
    through its own menu, in the same slot (the bus, not the track)."""
    t1, t2 = header("Kick", sends={"A": ("", "//[ROOM]")}), header("Snare")
    app, _ = edit_app(t1, t2)
    i1 = bus_menu(app, E.find_one(t1, "button", "Send selector B"), "//[PARA DRUMS]")   # A is taken on Kick
    i2 = bus_menu(app, E.find_one(t2, "button", "Send selector B"), "//[PARA DRUMS]")       # same slot on every track
    lib = lib_with(tmp_path, m="steps:\n- send: Stereo > bus > //[PARA DRUMS]\n")
    sysm = TrackSys(app, ["Kick", "Snare"])
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert i1.presses == 1 and i2.presses == 1 and sysm.typed == []


def test_output_copied_to_other_tracks_with_sdk(tmp_path):
    t1, t2, t3 = header("Kick"), header("Snare"), header("Tom")
    app, _ = edit_app(t1, t2, t3)
    item = bus_menu(app, E.find_one(t1, None, "Audio Output Path selector*"), "[DRUMS]")
    sysm = TrackSys(app, ["Kick", "Snare", "Tom"])
    pt = sysm._pt
    pt.run = lambda cmd, body=None: (pt.sent.append((cmd, body)) or {
        "GetTrackList": {"track_list": [{"name": "Kick", "id": "{k}"}, {"name": "Snare", "id": "{s}"}, {"name": "Tom", "id": "{t}"}]},
        "GetTrackMainOutputAssignments": {"signalpath_ids": ["0x30000050"]}}.get(cmd, {}))
    lib = lib_with(tmp_path, m="steps:\n- output: Stereo > bus > [DRUMS]\n")
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert item.presses == 1
    assert ("GetTrackMainOutputAssignments", {"track_ids": ["{k}"]}) in pt.sent
    assert pt.sent[-1] == ("SetTrackMainOutputAssignments", {"track_names": ["Snare", "Tom"], "signalpath_ids": ["0x30000050"]})


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
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    shutil.copytree(DECK / "icons", tmp_path / "icons")
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


def pt2026_menu():
    """Pro Tools 2026's output menu, as the menu probe showed it: windows of menu items."""
    W = lambda items: El("AXWindow", None, items, AXSubrole="AXDialog")  # noqa: E731
    drums = El("AXMenuItem", "[DRUMS]")
    top = W([El("AXMenuItem", "no output"), El("AXMenuItem", "search..."),
             El("AXMenuItem", "bus", [W([El("AXMenuItem", "[DRUMS] (Stereo)"), El("AXMenuItem", "[DRUMS].L (Mono)")])]),
             El("AXMenuItem", "Stereo", [W([El("AXMenuItem", "bus", [W([El("AXMenuItem", "[LV]"), drums])])])]),
             El("AXMenuItem", "track", [W([El("AXMenuItem", "[DRUMS]")])])])
    return top, drums


def test_pro_tools_2026_menu_window(tmp_path):
    t = header("Kick")
    app, _ = edit_app(t)
    top, drums = pt2026_menu()
    sel = E.find_one(t, None, "Audio Output Path selector*")
    menu_on_press(app, sel, top)
    drums.on_press = lambda: setattr(app, "kids", [])
    lib = lib_with(tmp_path, m="steps:\n- output: Stereo > bus > [DRUMS]\n")
    sysm = TrackSys(app, ["Kick"])
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert drums.presses == 1 and sysm.typed == []


def test_menu_item_press_ignored_falls_back_to_search(tmp_path):
    """One track: if Pro Tools ignores the press, the menu is still open, so search it and click."""
    t = header("Kick")
    app, _ = edit_app(t)
    top, drums = pt2026_menu()
    sel = E.find_one(t, None, "Audio Output Path selector*")
    menu_on_press(app, sel, top)
    lib = lib_with(tmp_path, m="steps:\n- output: Stereo > bus > [DRUMS]\n")
    sysm = TrackSys(app, ["Kick"])
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert sysm.typed == ["[DRUMS]"] and sysm.clicks and sysm.clicks[-1][4] == 0 and sysm.held == []


def test_menu_that_never_opens_types_nothing(tmp_path):
    """Never type when no menu is open: the keys would hit Pro Tools shortcuts."""
    t = header("Kick")
    app, _ = edit_app(t)
    lib = lib_with(tmp_path, m="steps:\n- output: Stereo > bus > [DRUMS]\n")
    sysm = TrackSys(app, ["Kick"])
    with pytest.raises(MacroError):
        Runner(sysm, lib, log=lambda m: None).run("m")
    assert sysm.typed == []


def test_results_are_remembered(tmp_path):
    from ptdeck import results
    results.record_run(tmp_path, "A", False, "boom")
    results.set_verdict(tmp_path, "A", "broken")
    results.record_run(tmp_path, "B", True)
    results.set_verdict(tmp_path, "B", "works")
    results.set_verdict(tmp_path, "B", None)
    r = results.load(tmp_path)
    assert r["A"]["last_result"] == "error" and r["A"]["verdict"] == "broken"
    assert r["B"]["last_result"] == "ok" and "verdict" not in r["B"]


def test_send_option_shift_sets_all_tracks_at_once(tmp_path):
    t1, t2, t3 = header("Kick"), header("Snare"), header("Tom")
    app, _ = edit_app(t1, t2, t3)
    sel = E.find_one(t1, "button", "Send selector A")
    sel.a["AXPosition"], sel.a["AXSize"] = (100, 100), (60, 20)
    item = El("AXMenuItem", "//[PARA DRUMS] (Stereo)")
    menu = El("AXWindow", None, [El("AXMenuItem", "search..."), El("AXMenuItem", "bus", [El("AXWindow", None, [item])])])
    sysm = TrackSys(app, ["Kick", "Snare", "Tom"])
    from ptdeck.keys import ALT, SHIFT

    def click(x, y, button="left", count=1, flags=0):
        sysm.clicks.append((x, y, flags))
        if (x, y) == (130, 110) and flags == ALT | SHIFT:
            app.kids = [menu]

    def choose():                      # Pro Tools sets send A on every selected track
        app.kids = []
        for t in (t1, t2, t3):
            E.find_one(t, "button", "Send Assignment A").a["AXValue"] = "//[PARA DRUMS]"
    sysm.click = click
    item.on_press = choose
    lib = lib_with(tmp_path, m="steps:\n- send: Stereo > bus > //[PARA DRUMS]\n  slot: 1\n")
    logs = []
    Runner(sysm, lib, log=logs.append).run("m")
    assert item.presses == 1 and sysm.clicks == [(130, 110, ALT | SHIFT)]
    assert not any("one by one" in m for m in logs)


# ---------- Pro-Q 3 -> Pro-Q 4 converter ----------

def test_proq_converter_selected_tracks(tmp_path, monkeypatch):
    from ptdeck import proq
    from ptdeck.keys import CTRL
    monkeypatch.setattr(proq, "PRESET_DIR", tmp_path / "presets")
    (tmp_path / "presets").mkdir()
    (tmp_path / "presets" / f"{proq.TEMP_PRESET}.ffp").write_text("")
    gtr = header("Gtr", inserts={"B": ("", "FabFilter Pro-Q 3"), "C": ("inactive", "FabFilter Pro-Q 3")})
    app, _ = edit_app(gtr)
    asg = E.find_one(gtr, "button", "Insert Assignment B")
    q4_item = El("AXMenuItem", "FabFilter Pro-Q 4 (stereo)")
    sel_popup = El("AXPopUpButton", "Plugin Selector\nPackage: AAX Native", value="FabFilter Pro-Q 3")
    q3win = El("AXWindow", "Plug-in: FabFilter Pro-Q 3", [El("AXButton", "Effect Bypass", value="off"),
                                                         El("AXPopUpButton", "Track Selector", value="Gtr"), sel_popup],
               pos=(100, 100), size=(1000, 600))
    q4close = El("AXButton", "close")
    q4win = El("AXWindow", "Plug-in: FabFilter Pro-Q 4", [], pos=(100, 100), size=(1000, 600), AXCloseButton=q4close)
    save_btn = El("AXButton", "Save")
    save_win = El("AXWindow", "Save", [El("AXTextField", None, value=""), save_btn])
    wins = app.a["AXWindows"]
    asg.on_press = lambda: wins.append(q3win)
    menu = El("AXWindow", None, [El("AXMenuItem", "search..."), El("AXMenuItem", "multichannel plug-in", [
        El("AXWindow", None, [El("AXMenuItem", "EQ", [El("AXWindow", None, [q4_item])])])])])
    menu_on_press(app, sel_popup, menu)

    def swap():
        app.kids = []
        wins.remove(q3win)
        wins.append(q4win)
        asg.a["AXValue"] = "FabFilter Pro-Q 4"
    q4_item.on_press = swap
    save_btn.on_press = lambda: wins.remove(save_win)
    q4close.on_press = lambda: wins.remove(q4win)

    sysm = TrackSys(app, ["Gtr"])
    sysm.typed = []
    pt = sysm._pt
    pt.run = lambda cmd, body=None: (pt.sent.append((cmd, body)) or {
        "GetSessionName": {"session_name": "Song.02"},
        "GetSessionPath": {"session_path": {"path": "/S/Song/Song.02.ptx"}},
        "GetTrackList": {"track_list": [{"name": "Gtr", "format": "TFormat_Stereo"}]}}.get(cmd, {}))
    real_click = sysm.click

    def click(x, y, button="left", count=1, flags=0):
        real_click(x, y, button, count, flags)
        if flags == CTRL and save_win not in wins:
            wins.append(save_win)
    sysm.click = click
    sysm.alert = lambda *a, **k: None
    lib = lib_with(tmp_path, m="steps:\n- convert pro-q 3 to 4:\n  scope: selected\n")
    logs = []
    Runner(sysm, lib, log=logs.append).run("m")
    assert ("SaveSessionAs", {"session_name": "Song.02_q3q4Convert", "session_location": "/S/Song"}) in pt.sent
    assert sysm.clicks[0][:2] == (100 + 1000 * 0.69, 100 + 600 * 0.20) and sysm.clicks[0][4] == CTRL   # Q3 preset area
    assert save_win.kids[0].a["AXValue"] == proq.TEMP_PRESET
    assert q4_item.presses == 1
    assert sysm.clicks[-1][:2] == (100 + 1000 * 0.69, 100 + 600 * 0.18)                               # Q4 preset area
    assert sysm.typed[-1] == proq.TEMP_PRESET and q4close.presses == 1
    assert any("converted 1 Pro-Q 3" in m for m in logs)            # the inactive one in C was left alone


def test_rebuilt_replaces_raw_import_but_not_your_edits(tmp_path):
    (tmp_path / "macros").mkdir()
    (tmp_path / "rebuilt").mkdir()
    (tmp_path / "rebuilt" / "a.yaml").write_text("name: A\nsteps:\n- note: rebuilt\n")
    (tmp_path / "rebuilt" / "b.yaml").write_text("name: B\nsteps:\n- note: rebuilt\n")
    (tmp_path / "macros" / "a.yaml").write_text("# Imported from SoundFlow\nname: A\nsteps:\n- todo: x\n")
    (tmp_path / "macros" / "b.yaml").write_text("name: B\nsteps:\n- note: mine\n")
    (tmp_path / "rebuilt" / "c.yaml").write_text("name: Pro-Q 3 to Pro-Q 4 Converter\nsteps:\n- note: rebuilt\n")
    (tmp_path / "macros" / "proq-converter.yaml").write_text(
        "# Imported from SoundFlow\nname: Pro-Q 3 to Pro-Q 4 Converter\nsteps:\n- todo: x\n")
    lib = Library(tmp_path / "macros")
    assert lib.get("A")["_file"].parent.name == "rebuilt"
    assert lib.get("Pro-Q 3 to Pro-Q 4 Converter")["_file"].parent.name == "rebuilt"   # matched by name
    assert lib.get("B")["steps"] == [{"note": "mine"}]


def test_compact_inserts(tmp_path):
    t = header("Vox", inserts={"B": ("", "EQ"), "D": ("inactive", "Comp"), "F": ("", "Verb")})
    app, _ = edit_app(t)
    asg = {L: E.find_one(t, "button", f"Insert Assignment {L}") for L in "ABCDEFGHIJ"}
    for i, L in enumerate("ABCDEFGHIJ"):
        asg[L].a["AXPosition"] = (10, 100 + i * 20)
    sysm = TrackSys(app, ["Vox"])
    drags = []

    def drag(start, end):
        drags.append((start, end))
        src = next(b for b in asg.values() if b.a["AXPosition"] == (start[0] - 2, start[1] - 5))
        dst = next(b for b in asg.values() if b.a["AXPosition"] == (end[0] - 2, end[1] - 5))
        dst.a["AXValue"], src.a["AXValue"] = src.a["AXValue"], "unassigned"
    sysm.drag = drag
    lib = lib_with(tmp_path, m="steps:\n- compact inserts:\n  tracks: selected\n")
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert [asg[L].a["AXValue"] for L in "ABCD"] == ["EQ", "Comp", "Verb", "unassigned"]
    assert len(drags) == 3


def tool_cluster(smart_on, tce, current="Grabber tool (Time)"):
    """The Edit window toolbar as Pro Tools 2026 shows it (from the tool probe)."""
    trim_name = "Time Compression/Expansion Trim tool" if tce else "Trim tool"
    names = ["Zoom Toggle", "Smart tool", trim_name, "Selector tool", "Grabber tool (Time)", "Zoomer tool"]
    on = {"Smart tool", trim_name, "Selector tool", "Grabber tool (Time)"} if smart_on else {current}
    btns = [El("AXButton", n, value="Selected" if n in on else None) for n in names]
    win = El("AXWindow", "Edit: Song", [El("AXGroup", "Cursor Tool Cluster", btns)], size=(3000, 2000))
    return make_app([win])


def test_toggle_tce_keeps_smart_mode(tmp_path):
    cases = [(True, False, ["ET_TrimTce", "ET_SmartTool"]), (True, True, ["ET_TrimStandard", "ET_SmartTool"]),
             (False, False, ["ET_TrimTce", "ET_GrabberTime"]), (False, True, ["ET_TrimStandard", "ET_GrabberTime"])]
    for smart_on, tce, expect in cases:
        sysm = FakeSys(tool_cluster(smart_on, tce))
        pt = FakePTSL()
        sysm.ptsl = lambda pt=pt: pt
        lib = lib_with(tmp_path, m="steps:\n- toggle tce trim\n")
        Runner(sysm, lib, log=lambda m: None).run("m")
        assert [b["edit_tool"] for _, b in pt.sent] == expect, (smart_on, tce)
    # Pro Tools turns Smart on when the trim mode changes: it gets switched back off.
    app = tool_cluster(False, False, current="Trim tool")
    smart = E.find_all(app.a["AXWindows"][0], "AXButton", "Smart tool")[0]
    sysm = FakeSys(app)
    pt = FakePTSL()

    def run(cmd, body=None):
        pt.sent.append((cmd, body))
        smart.a["AXValue"] = "Selected" if body["edit_tool"] in ("ET_TrimTce", "ET_SmartTool") else None
        return {}
    pt.run = run
    sysm.ptsl = lambda: pt
    smart.on_press = lambda: smart.a.__setitem__("AXValue", None if smart.a["AXValue"] == "Selected" else "Selected")
    logs = []
    Runner(sysm, lib_with(tmp_path, m="steps:\n- toggle tce trim\n"), log=logs.append).run("m")
    assert smart.a["AXValue"] is None and any("correcting" in m for m in logs)
    # Trim already the selected tool (Smart off): just switch its mode.
    sysm = FakeSys(tool_cluster(False, True, current="Time Compression/Expansion Trim tool"))
    pt = FakePTSL()
    sysm.ptsl = lambda: pt
    Runner(sysm, lib_with(tmp_path, m="steps:\n- toggle tce trim\n"), log=lambda m: None).run("m")
    assert [b["edit_tool"] for _, b in pt.sent] == ["ET_TrimStandard"]


def test_commit_track_dialog(tmp_path):
    """Commit Tracks dialog as inspected in Pro Tools 2026: popups are named after their current value."""
    edit_sel = El("AXMenuItem", "Edit Selection")
    commit_popup = El("AXPopUpButton", "Selected Tracks")
    vol, pan = El("AXCheckBox", "Volume and Mute", value=0), El("AXCheckBox", "Pan", value=0)
    ok = El("AXButton", "OK")
    dlg = El("AXWindow", "Commit Tracks", [commit_popup, El("AXStaticText", "Commit:"), El("AXCheckBox", "Consolidate Clips", value=0),
                                           vol, pan, El("AXButton", "Cancel"), ok, El("AXPopUpButton", "Do Nothing")])
    item = El("AXMenuItem", "Commit...")
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "Track", [El("AXMenu", None, [item])])])
    app = make_app([El("AXWindow", "Edit: Song")], bar)
    item.on_press = lambda: app.a["AXWindows"].append(dlg)
    menu_on_press(app, commit_popup, El("AXWindow", None, [El("AXMenuItem", "Selected Tracks"), edit_sel]))
    edit_sel.on_press = lambda: setattr(app, "kids", [])
    ok.on_press = lambda: app.a["AXWindows"].remove(dlg)
    (tmp_path / "commit-track.yaml").write_text((DECK / "rebuilt" / "commit-track.yaml").read_text())
    Runner(FakeSys(app), Library(tmp_path), log=lambda m: None).run("Commit Track")
    assert edit_sel.presses == 1 and vol.a["AXValue"] == 1 and pan.a["AXValue"] == 1 and ok.presses == 1


def test_additions_add_and_update_pages(tmp_path, monkeypatch):
    import shutil
    from ptdeck import __main__ as M
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    (tmp_path / "additions").mkdir()
    monkeypatch.setattr(M, "BASE", tmp_path)
    add = tmp_path / "additions" / "x.yaml"
    add.write_text("page: Extra\nbuttons:\n- {key: 2, label: A, macro: A}\n"
                   "link: {page: Home, key: 4, button: {label: Extra, folder: Extra}}\n")
    assert M.apply_additions() == ["Extra"]
    assert M.apply_additions() == []                              # already there: left alone
    add.write_text("page: Extra\nversion: 2\nbuttons:\n- {key: 2, label: A, macro: A}\n- {key: 3, label: B, macro: B}\n")
    assert M.apply_additions() == ["Extra"]                       # newer version replaces the page
    cfg = D.load_config(tmp_path / "deck.yaml")
    assert [b["label"] for b in cfg["pages"]["Extra"]] == ["A", "B"]
    assert any(b.get("folder") == "Extra" for b in cfg["pages"]["Home"])


def test_slow_checkbox_is_not_clicked_twice(tmp_path):
    """Pro Tools updates a checkbox's state a moment after the click; don't 'fix' it back."""
    box = El("AXCheckBox", "Offline", value=1)
    win = El("AXWindow", "Commit Tracks", [box])
    sysm = FakeSys(make_app([win]))
    pending = {}

    def press(action):
        pending["at"] = sysm.t + 0.2              # state changes 0.2s later
        return True
    box.perform = press
    real_sleep = sysm.sleep

    def sleep(s):
        real_sleep(s)
        if "at" in pending and sysm.t >= pending["at"]:
            box.a["AXValue"] = 0
            pending.clear()
    sysm.sleep = sleep
    lib = lib_with(tmp_path, m="steps:\n- checkbox: Offline\n  set: off\n  window: Commit Tracks\n")
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert box.a["AXValue"] == 0 and sysm.clicks == []


def test_import_io_settings_by_sample_rate(tmp_path):
    btn = El("AXButton", "Import Settings...")
    io = El("AXWindow", "I/O Setup", [btn])
    item = El("AXMenuItem", "I/O...")
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "Setup", [El("AXMenu", None, [item])])])
    app = make_app([El("AXWindow", "Edit: Song")], bar)
    item.on_press = lambda: app.a["AXWindows"].append(io)
    sysm = FakeSys(app)
    pt = FakePTSL()
    pt.run = lambda cmd, body=None: {"sample_rate": "SRate_48000"} if cmd == "GetSessionSampleRate" else {}
    sysm.ptsl = lambda: pt
    sysm.pasted = []
    sysm.paste = sysm.pasted.append
    (tmp_path / "m.yaml").write_text((DECK / "rebuilt" / "import-io-setup-based-on-sample-rate.yaml").read_text())
    Runner(sysm, Library(tmp_path), log=lambda m: None).run("Import IO Setup based on Sample Rate")
    import time as _t
    _t.sleep(0.05)                                   # the button press runs in the background
    assert btn.presses == 1 and sysm.pasted[0].endswith("EAS DEFAULT 2025 48kHz.pio")
    pt.run = lambda cmd, body=None: {"sample_rate": "SRate_96000"}
    with pytest.raises(MacroError):
        Runner(sysm, Library(tmp_path), log=lambda m: None).run("Import IO Setup based on Sample Rate")


def test_set_buffer_size(tmp_path):
    item128 = El("AXMenuItem", "128 Samples")
    pop = El("AXPopUpButton", "1024 Samples", [El("AXMenu", None, [El("AXMenuItem", "64 Samples"), item128,
                                                                    El("AXMenuItem", "1024 Samples")])])
    ok = El("AXButton", "OK")
    win = El("AXWindow", "Playback Engine", [El("AXStaticText", "H/W Buffer Size:"), pop, ok])
    mi = El("AXMenuItem", "Playback Engine...")
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "Setup", [El("AXMenu", None, [mi])])])
    app = make_app([El("AXWindow", "Edit: Song")], bar)
    mi.on_press = lambda: app.a["AXWindows"].append(win)
    ok.on_press = lambda: app.a["AXWindows"].remove(win)
    (tmp_path / "b.yaml").write_text((DECK / "rebuilt" / "buffer-128.yaml").read_text())
    Runner(FakeSys(app), Library(tmp_path), log=lambda m: None).run("Buffer 128")
    assert item128.presses == 1 and ok.presses == 1


def test_install_update_keeps_your_files(tmp_path, monkeypatch):
    import base64 as b64
    import io as _io
    import zipfile
    from ptdeck.manager import Manager
    base = tmp_path / "ptdeck"
    (base / "macros").mkdir(parents=True)
    (base / "macros" / "mine.yaml").write_text("name: Mine\nsteps: []\n")
    (base / "deck.yaml").write_text("home: Home\npages:\n  Home: []\n")
    (base / "ptdeck").mkdir()
    (base / "ptdeck" / "old.py").write_text("old")
    buf = _io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ptdeck/ptdeck/__main__.py", "new main")
        z.writestr("ptdeck/rebuilt/x.yaml", "name: X\nsteps: []\n")
        z.writestr("ptdeck/macros/mine.yaml", "SHOULD NOT OVERWRITE")
        z.writestr("ptdeck/deck.yaml", "SHOULD NOT OVERWRITE")
        z.writestr("ptdeck/../evil.txt", "nope")
    m = Manager(base, app=base)
    monkeypatch.setattr(m, "restart_soon", lambda: None)
    r = m.install_update("data:application/zip;base64," + b64.b64encode(buf.getvalue()).decode())
    assert r["files"] == 2
    assert (base / "ptdeck" / "__main__.py").read_text() == "new main"
    assert (base / "macros" / "mine.yaml").read_text().startswith("name: Mine")
    assert (base / "deck.yaml").read_text().startswith("home: Home")
    assert not (tmp_path / "evil.txt").exists()


def test_clear_sends_fast_and_restores_heights(tmp_path):
    from ptdeck.keys import ALT, SHIFT
    t1 = header("Kick", sends={"A": ("", "//[ROOM]"), "C": ("", "//[PLATE]")})
    t2 = header("Snare", sends={"A": ("", "//[ROOM]")})
    app, _ = edit_app(t1, t2)
    sysm = TrackSys(app, ["Kick", "Snare"])
    pt = sysm._pt
    pt.run = lambda cmd, body=None: (pt.sent.append((cmd, body)) or {
        "GetTrackList": {"track_list": [{"name": "Kick", "height": "THeight_Small"},
                                        {"name": "Snare", "height": "THeight_Medium"}]}}.get(cmd, {}))
    for t in (t1, t2):
        for i, L in enumerate("ABCDEFGHIJ"):
            E.find_one(t, "button", f"Send selector {L}").a["AXPosition"] = (100 + i, 200 if t is t1 else 300)
    menus = {}

    def click(x, y, button="left", count=1, flags=0):
        sysm.clicks.append((x, y, flags))
        L = "ABCDEFGHIJ"[int(x - 100 - 5)]
        item = El("AXMenuItem", "no send")
        menu = El("AXWindow", None, [El("AXMenuItem", "search..."), item])

        def choose(L=L):
            app.kids = []
            targets = (t1, t2) if flags == ALT | SHIFT else ((t1,) if y < 250 else (t2,))
            for t in targets:
                E.find_one(t, "button", f"Send Assignment {L}").a["AXValue"] = "unassigned"
        item.on_press = choose
        app.kids = [menu]
        menus[L] = item
    sysm.click = click
    lib = lib_with(tmp_path, m="steps:\n- clear: sends\n  tracks: selected\n")
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert all(E.find_one(t, "button", f"Send Assignment {L}").a["AXValue"] == "unassigned" for t in (t1, t2) for L in "AC")
    assert len(sysm.clicks) == 2 and all(c[2] == ALT | SHIFT for c in sysm.clicks)       # one click per used slot
    heights = [b for c, b in pt.sent if c == "SetTrackHeight"]
    assert heights[0] == {"track_names": ["Kick", "Snare"], "height": "THeight_Medium"}
    assert heights[-1] == {"track_names": ["Kick"], "height": "THeight_Small"}            # Kick put back



def test_next_version_name():
    from ptdeck.macros import next_version_name
    assert next_version_name("Song.01") == "Song.02"
    assert next_version_name("Song.09") == "Song.10"
    assert next_version_name("Song.99") == "Song.100"
    assert next_version_name("Song.3") == "Song.4"
    assert next_version_name("Song") == "Song.01"
    assert next_version_name("Mix v1.2.03") == "Mix v1.2.04"
    assert next_version_name("EMMA LYNNE - I DON'T DRINK, I DON'T SMOKE.02.ptx") == "EMMA LYNNE - I DON'T DRINK, I DON'T SMOKE.03"
    assert next_version_name("Song.02 mix") == "Song.02 mix.01"



def test_bounce_source_asked_once_then_remembered(tmp_path):
    (tmp_path / "macros").mkdir()
    (tmp_path / "macros" / "b.yaml").write_text(
        'name: B\nsteps:\n- bounce mix: "{date}_{session}_EASMIX_{rate}_{bits}"\n  offline: false\n')
    pt = SessionPTSL()
    base_run = pt.run

    def run(cmd, body=None, timeout=None):
        if cmd == "GetExportMixSourceList":
            pt.sent.append((cmd, body))
            return {"source_list": ["Built-in Output 1-2"] if body["type"] == "EMSType_Output" else ["(PRINT)"]}
        if cmd == "ExportMix":
            pt.timeouts.append(timeout)
        return base_run(cmd, body, timeout)
    pt.timeouts = []
    pt.run = run
    sysm = FakeSys(make_app([]))
    sysm.ptsl = lambda: pt
    asked = []
    sysm.choose = lambda items, prompt, title="": asked.append(items) or "Bus: (PRINT)"
    lib = Library(tmp_path / "macros")
    Runner(sysm, lib, log=lambda m: None).run("B")
    Runner(sysm, lib, log=lambda m: None).run("B")
    exports = [b for c, b in pt.sent if c == "ExportMix"]
    assert len(asked) == 1 and asked[0] == ["Output: Built-in Output 1-2", "Bus: (PRINT)"]
    assert all(e["mix_source_list"] == [{"source_type": "EMSType_Bus", "name": "(PRINT)"}] for e in exports)
    assert all(e["offline_bounce"] == "TBool_False" for e in exports) and pt.timeouts[0] >= 3600


def test_additions_add_buttons_only_into_empty_keys(tmp_path, monkeypatch):
    import shutil
    from ptdeck import __main__ as M
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    (tmp_path / "additions").mkdir()
    monkeypatch.setattr(M, "BASE", tmp_path)
    (tmp_path / "additions" / "a.yaml").write_text(
        "add to page: Bounce Mix\nbuttons:\n- {key: 2, label: New, macro: N}\n- {key: 31, label: Clash, macro: C}\n")
    assert M.apply_additions() == ["1 button(s) on Bounce Mix"]
    assert M.apply_additions() == []
    keys = {b["key"]: b for b in D.load_config(tmp_path / "deck.yaml")["pages"]["Bounce Mix"]}
    assert keys[2]["label"] == "New" and keys[31]["label"] != "Clash"


def test_bounce_dialog_fills_in_and_leaves_it_open(tmp_path):
    import datetime
    from ptdeck.keys import CMD, ALT
    rows = {"File Name:": 186, "Mix Source:": 328, "Bit Depth:": 566, "Sample Rate:": 614}
    label = lambda t, y: El("AXStaticText", t, pos=(50, y - 10), size=(100, 20))  # noqa: E731
    name_field = El("AXTextField", None, value="TESTING 2", pos=(165, 176), size=(520, 22))
    src_item = El("AXMenuItem", "Built-in Output 1-2 (Stereo) -> Analog 1-2")
    bit_item, rate_item = El("AXMenuItem", "24 Bit"), El("AXMenuItem", "44.1 kHz")
    src = El("AXPopUpButton", "Analog 1-2 (Stereo)", pos=(165, 318), size=(520, 22))
    bitp = El("AXPopUpButton", "32 Bit Float", pos=(285, 556), size=(315, 22))
    ratep = El("AXPopUpButton", "48 kHz", pos=(285, 604), size=(315, 22))
    offline = El("AXCheckBox", "Offline", value=1)
    import_after = El("AXCheckBox", "Import After Bounce", value=1)
    bounce = El("AXButton", "Bounce")
    win = El("AXWindow", "Bounce Mix", [label("File Name:", rows["File Name:"]), name_field,
                                        label("Mix Source:", rows["Mix Source:"]), src,
                                        label("Bit Depth:", rows["Bit Depth:"]), bitp,
                                        label("Sample Rate:", rows["Sample Rate:"]), ratep, offline, import_after, bounce])
    app = make_app([El("AXWindow", "Edit: Song.03")])
    menus = {src: El("AXWindow", None, [El("AXMenuItem", "output", [El("AXWindow", None, [src_item])])]),
             bitp: El("AXWindow", None, [El("AXMenuItem", "16 Bit"), bit_item]),
             ratep: El("AXWindow", None, [rate_item, El("AXMenuItem", "48 kHz")])}
    for pop, menu in menus.items():
        menu_on_press(app, pop, menu)
    # Pro Tools keeps invisible menu windows around after a menu closes.
    ghost = El("AXWindow", None, [El("AXMenuItem", "Bus 1-2 (Stereo)")], pos=(0, 0), size=(0, 0))

    def chosen(pop, value):
        def f():
            app.kids = [ghost]
            pop.a["AXTitle"] = value
        return f
    src_item.on_press = chosen(src, "Built-in Output 1-2 (Stereo) -> Analog 1-2")
    bit_item.on_press = chosen(bitp, "24 Bit")
    rate_item.on_press = chosen(ratep, "44.1 kHz")
    sysm = FakeSys(app)
    pt = SessionPTSL()
    pt.run = lambda cmd, body=None, timeout=None: {
        "GetSessionSampleRate": {"sample_rate": "SRate_44100"}, "GetSessionName": {"session_name": "Song.03"},
        "GetSessionPath": {"session_path": {"path": "/S/Song.03.ptx"}}}.get(cmd, {})
    sysm.ptsl = lambda: pt

    def key(code, flags=0):
        sysm.keys.append((code, flags))
        if (code, flags) == (11, CMD | ALT):               # Cmd+Option+B opens Bounce Mix
            app.a["AXWindows"].append(win)
    sysm.key = key
    name_field.set_attr = lambda n, v: True              # like Pro Tools: 'succeeds' but is ignored
    sysm.paste = lambda text: name_field.a.__setitem__("AXValue", text)
    (tmp_path / "b.yaml").write_text((DECK / "rebuilt" / "bounce-mix-at-24-bit-and-rename-real-time.yaml").read_text())
    Runner(sysm, Library(tmp_path), log=lambda m: None).run("Bounce Mix at 24 Bit and Rename (Real-time)")
    assert name_field.a["AXValue"] == f"{datetime.date.today():%y%m%d}_Song.03_EASMIX_44_24b.wav"
    assert src_item.presses == 1 and bit_item.presses == 1 and rate_item.presses == 1
    assert offline.a["AXValue"] == 0 and import_after.a["AXValue"] == 0
    assert bounce.presses == 0 and (36, 0) not in sysm.keys and sysm.typed == []   # never Return: left open for you


def test_page_title_banner():
    cfg = {"home": "Home", "pages": {"Home": [], "Bounce Mix": [{"key": 10, "label": "Save", "macro": "s"}],
                                     "Full": [{"key": k, "label": str(k), "macro": "m"} for k in range(2, 9)]}}
    slots = D.layout(cfg, "Bounce Mix", 32)
    banner = [i for i, b in enumerate(slots) if b and b.get("banner")]
    assert banner == list(range(1, 8)) and slots[9]["label"] == "Save"
    assert not any(b and b.get("banner") for b in D.layout(cfg, "Full", 32))       # no room: no banner
    assert not any(b and b.get("banner") for b in D.layout(cfg, "Home", 32))       # never on Home
    assert D._banner_words("Bounce Mix", 7) == ["BOUNCE", "MIX"]
    assert D._banner_words("A B C D", 3) == ["A B", "C", "D"]
    for part in range(7):
        assert D.render(slots[1 + part], 96, DECK).size == (96, 96)
    cfg["page titles"] = False
    assert not any(b and b.get("banner") for b in D.layout(cfg, "Bounce Mix", 32))


def test_manager_move_between_pages(tmp_path):
    import shutil
    from ptdeck.manager import Manager
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    shutil.copytree(DECK / "icons", tmp_path / "icons")
    (tmp_path / "macros").mkdir()
    m = Manager(tmp_path)
    m.set_button("Home", 2, {"label": "Mover", "macro": "X"})
    m.move_between("Home", 2, "Mix Prep", 2)                       # empty key on Mix Prep
    pages = m.state()["pages"]
    assert pages["Home"][2] is None and pages["Mix Prep"][2]["label"] == "Mover"
    before = pages["Mix Prep"][16]["macro"]
    m.move_between("Mix Prep", 2, "Mix Prep", 16)                  # same page: swap
    assert m.state()["pages"]["Mix Prep"][16]["label"] == "Mover"
    m.move_between("Mix Prep", 16, "Home", 2)                      # back to Home
    st = m.state()["pages"]
    assert st["Home"][2]["label"] == "Mover"                         # Mix Prep key 17 is now empty,
    assert st["Mix Prep"][16] is None and st["Mix Prep"][2]["macro"] == before   # the swapped key stays on 3
    with pytest.raises(ValueError):
        m.move_between("Home", 2, "Mix Prep", 0)                    # Back button
    folder_key = next(i for i, b in enumerate(m.state()["pages"]["Home"]) if b and b.get("folder") == "Mix Prep")
    with pytest.raises(ValueError):
        m.move_between("Home", folder_key, "Mix Prep", 3)           # a folder into itself


def test_if_window_branches(tmp_path):
    eq_p = El("AXRadioButton", "Equal Power", value=0)
    ok = El("AXButton", "OK")
    crossfade = El("AXWindow", "Crossfade", [El("AXGroup", "Slope", [eq_p, El("AXRadioButton", "Equal Gain", value=1)]), ok])
    app = make_app([El("AXWindow", "Edit: Song"), crossfade])
    text = """steps:
- if window: Batch Fades
  or: Crossfade
  then:
  - click: Nope
    window: Batch Fades
  else:
  - click: Equal Power
    kind: radio button
    window: Crossfade
    group: Slope
  - click: OK
    window: Crossfade
"""
    lib = lib_with(tmp_path, m=text)
    assert validate(lib.get("m"), lib) == []
    sysm = FakeSys(app)
    Runner(sysm, lib, log=lambda m: None).run("m")
    assert eq_p.presses == 1 and ok.presses == 1 and sysm.t < 0.5      # decided straight away


def test_tom_clean_bleed_is_valid():
    lib = Library(DECK / "rebuilt")
    m = lib.load(DECK / "rebuilt" / "tom-clean-bleed.yaml")
    assert validate(m, lib) == []


def test_audiosuite_clip_by_clip(tmp_path):
    item = El("AXMenuItem", "clip by clip")
    mode = El("AXPopUpButton", "entire selection", [El("AXMenu", None, [El("AXMenuItem", "entire selection"), item])])
    render = El("AXButton", "Render")
    win = El("AXWindow", "Audio Suite: EQ3 7-Band", [mode, render])
    app = make_app([El("AXWindow", "Edit: Song"), win])
    item.on_press = lambda: mode.a.__setitem__("AXTitle", "clip by clip")
    lib = lib_with(tmp_path, m="steps:\n- audiosuite render:\n  processing: clip by clip\n")
    Runner(FakeSys(app), lib, log=lambda m: None).run("m")
    assert item.presses == 1 and render.presses == 1
    # Already on Clip by Clip: left alone.
    Runner(FakeSys(app), lib, log=lambda m: None).run("m")
    assert item.presses == 1 and render.presses == 2


def batch_rename_window():
    """Batch Track Rename as inspected in Pro Tools 2026 (text boxes have no names)."""
    kids, fields = [], []
    order = ["Replace", "#Find", "#Replace", "Clear Existing Name", "Regular Expressions", "Trim", "#From Beginning",
             "#From End", "Range", "#From", "#To", "Add", "Prefix:", "#prefix", "Insert:", "#insert", "#At index",
             "Suffix:", "#suffix", "Numbering", "#Index", "#Starting", "#Places", "#Increment", "#Separate"]
    for i, n in enumerate(order):
        if n.startswith("#"):
            f = El("AXTextField", None, value="0", pos=(300, 20 * i), size=(100, 18))
            f.label = n[1:]
            fields.append(f)
            kids.append(f)
        else:
            kids.append(El("AXCheckBox", n, value=1 if n in ("Replace", "Trim", "Add", "Prefix:", "Insert:", "Suffix:") else 0))
    kids.append(El("AXButton", "OK"))
    return El("AXWindow", "Batch Track Rename", kids), fields


def test_new_comp_playlist(tmp_path):
    from ptdeck.keys import CTRL, ALT, SHIFT
    rename, fields = batch_rename_window()
    name_dialog = El("AXWindow", "", [El("AXTextField", None, value="Kick.02"), El("AXButton", "OK")])
    app = make_app([El("AXWindow", "Edit: Song")])
    sysm = FakeSys(app)
    focused = {}

    def key(code, flags=0):
        sysm.keys.append((code, flags))
        wins = app.a["AXWindows"]
        if (code, flags) == (42, CTRL):                       # Ctrl+\\ : new playlist asks for a name
            wins.append(name_dialog)
        elif code == 36 and name_dialog in wins:              # Return accepts it
            wins.remove(name_dialog)
        elif (code, flags) == (15, ALT | SHIFT):              # Option+Shift+R
            wins.append(rename)
    sysm.key = key

    def click(x, y, button="left", count=1, flags=0):
        focused["f"] = next((f for f in fields if f.a["AXPosition"] == (x - 50, y - 9)), None)
    sysm.click = click
    sysm.paste = lambda text: focused["f"].a.__setitem__("AXValue", text)
    rename.kids[-1].on_press = lambda: app.a["AXWindows"].remove(rename)
    (tmp_path / "c.yaml").write_text((DECK / "rebuilt" / "new-comp-playlist.yaml").read_text())
    Runner(sysm, Library(tmp_path), log=lambda m: None).run("New .Comp Playlist")
    vals = {f.label: f.a["AXValue"] for f in fields}
    assert vals["From Beginning"] == "0" and vals["From End"] == "2" and vals["suffix"] == "Comp"
    assert name_dialog not in app.a["AXWindows"] and rename not in app.a["AXWindows"]
    boxes = {c.attr("AXTitle"): c.attr("AXValue") for c in rename.kids if c.attr("AXRole") == "AXCheckBox"}
    assert boxes["Replace"] == 0 and boxes["Prefix:"] == 0 and boxes["Insert:"] == 0 and boxes["Suffix:"] == 1


def test_playlist_macros_valid():
    lib = Library(DECK / "rebuilt")
    for f in ("new-comp-playlist.yaml", "new-playlist-from-comp-to-edit.yaml", "rename-to-c.yaml"):
        assert validate(lib.load(DECK / "rebuilt" / f), lib) == [], f


def test_track_menu_change_width(tmp_path):
    t1, t2 = header("Gtr"), header("Vox")
    for t in (t1, t2):
        t.kids.insert(0, El("AXPopUpButton", f'Track name\n"{t.attr("AXTitle").split(" - ")[0]}"', pos=(10, 10), size=(80, 20)))
    app, win = edit_app(t1, t2)
    win.a["AXPosition"], win.a["AXSize"] = (0, 0), (2000, 2000)
    mono = El("AXMenuItem", "Mono")
    blocked = El("AXMenuItem", "Mono", AXEnabled=False)
    W = lambda items: El("AXWindow", None, items)  # noqa: E731
    menus = iter([W([El("AXMenuItem", "Rename..."), El("AXMenuItem", "Split into Mono"),          # decoy
                     El("AXMenuItem", "Track", [W([El("AXMenuItem", "Change Track Width",      # nested sub-menu
                                                    [W([mono, El("AXMenuItem", "Stereo")])])])])]),
                  El("AXWindow", None, [El("AXMenuItem", "Change Track Width", [El("AXWindow", None, [blocked])])])])
    sysm = TrackSys(app, ["Gtr", "Vox"])

    def click(x, y, button="left", count=1, flags=0):
        sysm.clicks.append((x, y, button))
        if button == "right":
            app.kids = [next(menus)]
    sysm.click = click
    mono.on_press = lambda: setattr(app, "kids", [])
    logs = []
    lib = lib_with(tmp_path, m="steps:\n- track menu: Change Track Width > Mono\n  tracks: selected\n")
    Runner(sysm, lib, log=logs.append).run("m")
    assert mono.presses == 1 and blocked.presses == 0
    assert any("isn't available on 'Vox'" in m for m in logs)


def test_plugin_window_from_mix_window_only(tmp_path):
    prt = header("(PRINT)", "Aux", {"C": ("", "Pultec EQP-1A")})
    mix = El("AXWindow", "Mix: Song", [prt])
    app = make_app([mix])                                   # Edit window closed
    asg = E.find_one(prt, "button", "Insert Assignment C")
    lib = lib_with(tmp_path, m='steps:\n- plugin window: 3\n  track: "(PRINT)"\n')
    Runner(TrackSys(app, []), lib, log=lambda m: None).run("m")
    assert asg.presses == 1


def test_old_rebuilt_copies_never_hide_fixes(tmp_path):
    from ptdeck.manager import Manager
    from ptdeck import __main__ as M
    (tmp_path / "macros").mkdir()
    (tmp_path / "rebuilt").mkdir()
    (tmp_path / "deck.yaml").write_text("home: Home\npages:\n  Home: []\n")
    new = '# Rebuilt for PT Deck: fixed\nname: Open Mix Bus Plugin 4\nsteps:\n- plugin window: 4\n  track: "(PRINT)"\n'
    old = '# Rebuilt for PT Deck: old\nname: Open Mix Bus Plugin 4\nsteps:\n- plugin window: 4\n  track: "[[OUTPUTBUS]]"\n'
    (tmp_path / "rebuilt" / "open-mix-bus-plugin-4.yaml").write_text(new)
    (tmp_path / "macros" / "open-mix-bus-plugin-4.yaml").write_text(old)      # copied by an old Update Macros
    lib = Library(tmp_path / "macros")
    assert lib.get("Open Mix Bus Plugin 4")["steps"][0]["track"] == "(PRINT)"
    assert M.remove_stale_rebuilt_copies(tmp_path) == 1
    # Your own edit of a rebuilt macro (saved in the Manager) is kept and wins.
    m = Manager(tmp_path)
    m.save_macro("open-mix-bus-plugin-4.yaml", new.replace("(PRINT)", "My Bus"))
    assert (tmp_path / "macros" / "open-mix-bus-plugin-4.yaml").read_text().startswith("# Edited by you")
    assert lib.get("Open Mix Bus Plugin 4")["steps"][0]["track"] == "My Bus"
    assert M.remove_stale_rebuilt_copies(tmp_path) == 0


def test_live_insert_keys(tmp_path):
    import shutil
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    shutil.copytree(DECK / "icons", tmp_path / "icons")
    cfg = (tmp_path / "deck.yaml").read_text().replace(
        "macro: Open Mix Bus Plugin 4}", "macro: Open Mix Bus Plugin 4, live: 4, live track: (PRINT)}")
    (tmp_path / "deck.yaml").write_text(cfg)
    data = {"D": ("UADx Manley Massive Passive EQ", "open")}

    class R:
        sys = lib = None

        def __init__(self, *a, **k):
            pass

        def read_inserts(self, track):
            assert track == "(PRINT)"
            return data
    c = D.DeckController(tmp_path, R(), log=lambda m: None)
    c.key_count = lambda: 32
    c.page = "Mix Bus"
    c.draw()
    key = next(i for i, b in enumerate(c.slots) if b and b.get("live") == 4 and b.get("live track") == "(PRINT)")
    assert key in c.poll_live() and c.poll_live() == []                  # only redraws on change
    shown = c.shown(key, c.slots[key])
    assert shown["label"] == "UADx Manley Massive Passive EQ" and shown["outline"] == "#ffffff"
    (tmp_path / "icons" / "uadx-manley-massive-passive-eq.png").write_bytes((DECK / "icons" / "manley.png").read_bytes())
    assert c.shown(key, c.slots[key])["icon"] == "uadx-manley-massive-passive-eq.png"
    data["D"] = ("Oxford Inflator", "bypassed")
    assert c.poll_live() == [key] and c.shown(key, c.slots[key])["color"] == D.LIVE_STYLES["bypassed"][0]
    assert D.render(c.shown(key, c.slots[key]), 96, tmp_path).size == (96, 96)


def test_plugin_window_restore_only_closes_what_it_opened(tmp_path):
    out = header("-OUT MASTER", "Master", {"H": ("", "ADPTR MetricAB")})
    app, _ = edit_app(out)
    asg = E.find_one(out, "button", "Insert Assignment H")
    sel = E.find_one(out, "button", "Insert selector H")
    steps = ("steps:\n- plugin window: ADPTR MetricAB\n  track: '-OUT MASTER'\n  set: open\n"
             "- plugin window: ADPTR MetricAB\n  track: '-OUT MASTER'\n  set: restore\n")
    lib = lib_with(tmp_path, m=steps)

    def opens():
        sel.a["AXValue"] = "" if sel.a.get("AXValue") == "open" else "open"
    asg.on_press = opens
    Runner(TrackSys(app, []), lib, log=lambda m: None).run("m")
    assert asg.presses == 2 and sel.a.get("AXValue") == ""     # opened, then closed again
    sel.a["AXValue"] = "open"
    Runner(TrackSys(app, []), lib, log=lambda m: None).run("m")
    assert asg.presses == 2 and sel.a["AXValue"] == "open"     # was already open: left open


def test_metric_slot_macros_and_page():
    from ptdeck.macros import Library
    import yaml as _y
    base = DECK
    for name in ("a1", "c3", "b1", "d4"):
        m = _y.safe_load((base / "rebuilt" / f"slot-{name}.yaml").read_text())
        assert m["steps"][1]["metric slot"].lower() == name
    page = _y.safe_load((base / "additions" / "metric-ab-page.yaml").read_text())
    keys = [b["key"] for b in page["buttons"]]
    assert len(keys) == len(set(keys)) == 19 and 1 not in keys


def test_metric_numbering_and_names(tmp_path):
    from ptdeck import metric as M
    assert M.parse_slot("c3") == (2, 2)
    assert M.index_of(*M.parse_slot("A1"), "rows") == 0 and M.index_of(*M.parse_slot("C3"), "rows") == 10
    assert M.index_of(*M.parse_slot("B1"), "rows") == 1 and M.index_of(*M.parse_slot("B1"), "columns") == 4
    for how in ("rows", "columns"):
        assert all(M.index_of(*M.cell_of(i, how), how) == i for i in range(16))
    assert M.clean("Mayday Parade_Kids In Love.wav ≡") == "Mayday Parade Kids In Love"
    with pytest.raises(ValueError):
        M.parse_slot("E1")


def test_metric_learns_order_from_orange_cell(tmp_path):
    from PIL import Image, ImageDraw
    from ptdeck import metric as M, settings
    grid = Image.new("RGB", (400, 80), "#24262c")
    ImageDraw.Draw(grid).rectangle([100, 20, 199, 39], fill="#d9894f")   # column B, row 2
    r = M.MetricReader(None, tmp_path)
    assert r.highlighted(grid) == (1, 1)
    grid2 = Image.new("RGB", (400, 80), "#24262c")
    ImageDraw.Draw(grid2).rectangle([100, 0, 199, 19], fill="#d9894f")   # column B, row 1
    r.learn_order(grid2, 4)                                                # B1 is number 4 -> columns
    assert settings.get(tmp_path, "metric order") == "columns"
    r.learn_order(grid2, 1)
    assert settings.get(tmp_path, "metric order") == "rows"


def metric_window():
    track = El("AXSlider", "Selected Track")
    track.a.update({"AXValue": 9, "AXMinValue": 0, "AXMaxValue": 15})
    ab = El("AXSlider", "AB Switch")
    ab.a.update({"AXValue": 0, "AXMaxValue": 2047, "AXValueDescription": "A"})
    group = El("AXGroup", "FXTDMEditView", [track, ab])
    group.a.update({"AXPosition": (632, 348), "AXSize": (1500, 933)})
    return El("AXWindow", "Plug-in: ADPTR MetricAB", [group]), track


class ClickSys(TrackSys):
    """Clicking a MetricAB cell selects that slot (counted by rows)."""
    def __init__(self, app, track):
        super().__init__(app, [])
        self.track = track

    def click(self, x, y, button="left", count=1, flags=0):
        super().click(x, y, button, count, flags)
        from ptdeck import metric as M
        for i in range(16):
            col, row = M.cell_of(i, "rows")
            cx, cy = M.cell_center((632, 348), (1500, 933), col, row)
            if abs(cx - x) < 1 and abs(cy - y) < 1:
                self.track.a["AXValue"] = i


def test_metric_slot_clicks_the_cell_once(tmp_path):
    from ptdeck import settings
    win, track = metric_window()
    sys_ = ClickSys(make_app([win]), track)
    lib = lib_with(tmp_path, m="steps:\n- metric slot: C2\n")
    Runner(sys_, lib, log=lambda m: None).run("m")
    assert len(sys_.clicks) == 1 and track.a["AXValue"] == 6
    # The click lands inside the C2 cell of the screenshot-measured grid.
    x, y = sys_.clicks[0][:2]
    assert 632 + 1500 * 0.62 < x < 632 + 1500 * 0.80 and 348 + 933 * 0.86 < y < 348 + 933 * 0.894
    assert settings.get(lib.folder.parent, "metric selected") == "C2"


def test_metric_slot_learns_column_order(tmp_path):
    from ptdeck import settings, metric as M
    win, track = metric_window()
    sys_ = ClickSys(make_app([win]), track)
    orig = M.cell_of
    sys_.click = lambda x, y, *a, **k: track.a.update(AXValue=4)        # B1 is number 4 -> columns
    lib = lib_with(tmp_path, m="steps:\n- metric slot: B1\n")
    Runner(sys_, lib, log=lambda m: None).run("m")
    assert settings.get(lib.folder.parent, "metric order") == "columns" and M.cell_of is orig


def test_metric_keys_show_names_and_selection():
    btn = {"key": 5, "metric": "B2", "macro": "Slot B2"}
    out = D.metric_button(btn, {"B2": "Breakout"}, "B2")
    assert out["label"] == "Breakout" and out["color"] == D.METRIC_STYLES["selected"][0]
    out = D.metric_button(btn, {}, None)
    assert out["label"] == "B2" and out["corner"] == "B2"
    D.render(btn, 96, Path("."))


def test_restore_leaves_a_window_you_opened(tmp_path):
    # The selector doesn't say 'open', but the plug-in window is on screen: never touch it.
    out = header("-OUT MASTER", "Master", {"H": ("", "ADPTR MetricAB")})
    plug = El("AXWindow", "Plug-in: ADPTR MetricAB")
    app = make_app([El("AXWindow", "Edit: My Song", [out]), plug])
    asg = E.find_one(out, "button", "Insert Assignment H")
    steps = ("steps:\n- plugin window: ADPTR MetricAB\n  track: '-OUT MASTER'\n  set: open\n"
             "- plugin window: ADPTR MetricAB\n  track: '-OUT MASTER'\n  set: restore\n")
    r = Runner(TrackSys(app, []), lib_with(tmp_path, m=steps), log=lambda m: None)
    for _ in range(3):
        r.run("m")
    assert asg.presses == 0


def test_metric_ab_key_and_toggle_remembers(tmp_path):
    from ptdeck import settings
    a = D.metric_ab_button({"metric ab": True, "macro": "t"}, "A")
    b = D.metric_ab_button({"metric ab": True, "macro": "t"}, "B")
    assert a["label"] == "A" and b["label"] == "B"
    assert a["color"] == b["text color"] and b["color"] == a["text color"]   # inverted
    D.render({"metric ab": True, "macro": "t"}, 96, Path("."))
    sw = El("AXSlider", "AB Switch")
    sw.a.update({"AXValue": 0, "AXMinValue": 0, "AXMaxValue": 2047})
    sw.perform = lambda act: sw.a.update(AXValue=2047 if act == "AXIncrement" else 0) or True
    app = make_app([El("AXWindow", "Plug-in: ADPTR MetricAB", [El("AXGroup", "FXTDMEditView", [sw])])])
    lib = lib_with(tmp_path, m="steps:\n- slider: AB Switch\n  window: 'Plug-in: ADPTR MetricAB'\n  set: toggle\n")
    Runner(TrackSys(app, []), lib, log=lambda m: None).run("m")
    assert settings.get(lib.folder.parent, "metric ab") == "B"


def test_metric_ab_clicks_the_other_letter(tmp_path):
    from ptdeck import settings, metric as M
    win, _ = metric_window()
    ab = E.find_one(win, "slider", "AB Switch")
    sys_ = TrackSys(make_app([win]), [])
    bx, _y = M.ab_center((632, 348), (1500, 933), "B")

    def click(x, y, *a, **k):
        sys_.clicks.append((x, y))
        ab.a["AXValueDescription"] = "B" if abs(x - bx) < 1 else "A"
    sys_.click = click
    lib = lib_with(tmp_path, m="steps:\n- metric ab: toggle\n")
    Runner(sys_, lib, log=lambda m: None).run("m")
    assert ab.a["AXValueDescription"] == "B" and settings.get(lib.folder.parent, "metric ab") == "B"
    Runner(sys_, lib, log=lambda m: None).run("m")
    assert ab.a["AXValueDescription"] == "A" and len(sys_.clicks) == 2
    lib2 = lib_with(tmp_path, n="steps:\n- metric ab: A\n")
    Runner(sys_, lib2, log=lambda m: None).run("n")
    assert len(sys_.clicks) == 2                         # already A: no click


def test_metric_poll_never_overwrites_a_button_press(tmp_path):
    from ptdeck import settings, metric as M
    win, track = metric_window()
    track.a["AXValue"] = 0                                   # plug-in still says A1...
    settings.put(tmp_path, "metric selected", "C2")          # ...but a press just chose C2
    r = M.MetricReader(Runner(TrackSys(make_app([win]), []), lib_with(tmp_path), log=lambda m: None), tmp_path)
    r.paused = lambda: True
    assert r.poll(want_names=False)["selected"] == "C2"
    assert settings.get(tmp_path, "metric selected") == "C2"
    r.paused = lambda: False
    assert r.poll(want_names=False)["selected"] == "A1"      # normal reading when nothing's running


def test_deck_skips_live_reading_while_busy(tmp_path):
    c = D.DeckController.__new__(D.DeckController)
    c.busy, c.slots, c.runner = True, [{"metric": "A1"}], object()
    assert c.poll_live() == []


def test_bypass_open_plugin_picks_the_print_window(tmp_path):
    def plug(name, track):
        sel = El("AXPopUpButton", "Track Selector")
        sel.a["AXValue"] = track
        return El("AXWindow", f"Plug-in: {name}", [sel, El("AXButton", "Effect Bypass")])
    other, prn = plug("Pro-Q 4", "Vox"), plug("Oxford Inflator", "(PRINT)")
    app = make_app([El("AXWindow", "Edit: Song"), other, prn])
    lib = lib_with(tmp_path, m="steps:\n- bypass open plugin: (PRINT)\n")
    Runner(TrackSys(app, []), lib, log=lambda m: None).run("m")
    assert E.find_one(prn, "button", "Effect Bypass").presses == 1
    assert E.find_one(other, "button", "Effect Bypass").presses == 0
    app2 = make_app([El("AXWindow", "Edit: Song"), other])
    with pytest.raises(MacroError):
        Runner(TrackSys(app2, []), lib, log=lambda m: None).run("m")


def test_live_key_shows_bypass_with_window_open(tmp_path):
    prn = header("(PRINT)", "Aux", {"F": ("open", "Oxford Inflator"), "G": ("open", "Ampex")})
    def plug(letter, bypassed):
        sel, pos = El("AXPopUpButton", "Track Selector"), El("AXPopUpButton", "Insert Position selector")
        sel.a["AXValue"], pos.a["AXValue"] = "(PRINT)", letter.lower()
        byp = El("AXButton", "Effect Bypass")
        if bypassed:
            byp.a["AXValue"] = "Selected"
        return El("AXWindow", f"Plug-in: {letter}", [sel, pos, byp])
    app = make_app([El("AXWindow", "Edit: Song", [prn], size=(3000, 2000)), plug("F", True), plug("G", False)])
    ins = Runner(TrackSys(app, []), lib_with(tmp_path), log=lambda m: None).read_inserts("(PRINT)")
    assert ins["F"][1] == "open bypassed" and ins["G"][1] == "open active"
    b = D.live_button({"live": 6}, ins["F"], Path("."))
    assert b["color"] == D.LIVE_STYLES["bypassed"][0] and b["outline"] == "#ffffff"
    assert D.live_button({"live": 7}, ins["G"], Path("."))["color"] == D.LIVE_STYLES["active"][0]


def test_designed_look_basics():
    from ptdeck import look
    assert look.ink("#ffcc00") == "#111111" and look.ink("#1a1a1a") == "#ffffff"
    assert look.text_colour({"text color": "#ffffff"}, "#22c0ff") == "#111111"     # unreadable: overridden
    assert look.text_colour({"text color": "#ffffff"}, "#6d0b0a") == "#ffffff"     # readable: kept
    assert look.guess_glyph("Bounce 24 Bit Offline") == "bounce" and look.guess_glyph("Clear All Sends") == "trash"
    assert look.theme_for("RX 11 Mouth De-click") == "rx" and look.theme_for("EQ3 7-Band") == "avid"
    for b in ({"label": "Delete Empty Audio Tracks in Selection", "macro": "x"},
              {"folder": "Commit Tracks", "label": "Commit Tracks"},
              {"label": "Mouth De-Click", "audiosuite": "RX 11 Mouth De-click"}, {"glyph": "eq"}):
        img = look.render_designed(b, 96, ".")
        assert img.size == (96, 96)
    assert len(look.GLYPHS) >= 40


def test_designed_style_is_opt_in():
    cfg = {"home": "Home", "pages": {"Home": [{"key": 2, "label": "Hi", "macro": "m"}]}}
    assert "_look" not in (D.layout(cfg, "Home", 32)[1] or {})
    cfg["icon style"] = "designed"
    assert D.layout(cfg, "Home", 32)[1]["_look"] == "designed"


def test_style_sends_strips_and_names():
    from ptdeck import look
    assert look.kind_of({"label": "//[SLAP DELAY]", "macro": "x"}, ".") == ("send", "SLAP DELAY")
    assert look.strip_name("EQ3 7-Band", "avid") == "EQ3 7-BAND"
    assert look.strip_name("RX 11 De-click", "rx") == "RX"
    look.render_designed({"label": "//[SLAP DELAY]", "color": "#1fbf7f"}, 96, ".")
    assert look._last_frac[0] is not None
    b = D.live_name_button({"live name": "selected"}, ("Lead Vox", 3))
    assert b["label"].startswith("Lead Vox") and "+2 more" in b["label"] and b["corner"] == "SELECTED"
    D.render({"live name": "(PRINT)"}, 96, Path("."))


def test_additions_settings_and_keep_others(tmp_path):
    from ptdeck.__main__ import apply_additions
    import yaml as _y
    (tmp_path / "deck.yaml").write_text(_y.safe_dump({"home": "Home", "pages": {
        "Home": [{"key": 2, "folder": "Mix Bus"}],
        "Mix Bus": [{"key": 2, "macro": "Insert 1 Toggle"}, {"key": 24, "macro": "Drum EQ"},
                    {"key": 16, "macro": "Bypass Open Print Plugin"}, {"key": 3, "macro": "Mine"}]}}))
    (tmp_path / "additions").mkdir()
    (tmp_path / "additions" / "s.yaml").write_text("settings:\n  icon style: designed\n")
    (tmp_path / "additions" / "p.yaml").write_text(
        "page: Mix Bus\nversion: 2\nkeep others: true\nreplaces: [Bypass Open Print Plugin]\nbuttons:\n"
        "- {key: 2, live: 1, live track: selected, macro: Insert 1 Toggle}\n- {key: 16, macro: Bypass Open Plugin}\n")
    apply_additions(base=tmp_path)
    cfg = _y.safe_load((tmp_path / "deck.yaml").read_text())
    assert cfg["icon style"] == "designed"
    keys = {b["key"]: b.get("macro") for b in cfg["pages"]["Mix Bus"]}
    assert keys == {2: "Insert 1 Toggle", 16: "Bypass Open Plugin", 24: "Drum EQ", 3: "Mine"}   # yours kept


def test_strip_and_chosen_glyph_and_row_matching():
    from ptdeck import look
    look.render_designed({"label": "16th Note Triplet", "strip": "Beat Detective"}, 96, ".")
    assert look._last_frac[0] is not None
    look.render_designed({"label": "Copy Selection to Target Playlist", "glyph": "playlist"}, 96, ".")
    assert look._last_frac[0] is not None              # a chosen glyph keeps the full label
    slots = [None] * 16
    slots[1] = {"label": "Set Grid to 1/4", "_look": "designed"}
    slots[2] = {"label": "Set Grid to 1/32", "_look": "designed"}
    slots[9] = {"label": "Delete Empty Audio Tracks in Selection", "_look": "designed"}   # another row
    look.match_sizes(slots, ".", cols=8)
    assert slots[1]["_maxfrac"] == slots[2]["_maxfrac"] and "_maxfrac" not in slots[9]


def test_audiosuite_found_in_other_macro_forms(tmp_path):
    from ptdeck import look
    (tmp_path / "macros").mkdir()
    (tmp_path / "macros" / "a.yaml").write_text(
        "name: A\nsteps:\n- menu: AudioSuite > Noise Reduction > RX 11 Mouth De-click\n")
    (tmp_path / "macros" / "b.yaml").write_text("name: B\nsteps:\n- run macro: A\n")
    (tmp_path / "macros" / "c.yaml").write_text("name: C\nsteps:\n- key: cmd+s\n")
    assert look.audiosuite_of(tmp_path, "A") == "RX 11 Mouth De-click"
    assert look.audiosuite_of(tmp_path, "B") == "RX 11 Mouth De-click"
    assert look.audiosuite_of(tmp_path, "C") is None
    assert look.kind_of({"label": "Mouth De-Click", "macro": "B"}, tmp_path)[0] == "audiosuite"


def test_deck_waits_and_reconnects(tmp_path):
    c = D.DeckController.__new__(D.DeckController)
    c.cfg, c.deck, c.log, c.page = {"model": "xl", "home": "Home", "pages": {"Home": []}}, None, (lambda m: None), "Home"
    assert c.key_count() == 32                       # no deck yet: uses the configured model, not 15 keys

    class Gone:
        def connected(self):
            return False

        def close(self):
            self.closed = True
    c.deck = Gone()
    assert not c._still_connected()
    c._lost("test")
    assert c.deck is None
    c.blockers = lambda: ["SoundFlow"]
    assert c.blockers() == ["SoundFlow"]


def test_start_stops_other_copies(monkeypatch):
    import os
    import signal
    from ptdeck import __main__ as M
    killed = []

    class R:
        stdout = f"{os.getpid()}\n424242\n"
    monkeypatch.setattr(M.subprocess, "run", lambda *a, **k: R())

    def fake_kill(pid, sig):
        if sig == 0:
            raise OSError("gone")
        killed.append((pid, sig))
    monkeypatch.setattr(os, "kill", fake_kill)
    assert M.stop_other_copies() == 1 and killed == [(424242, signal.SIGTERM)]   # never itself


def test_mirror_follows_what_the_deck_draws(tmp_path):
    import shutil
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    c = D.DeckController(tmp_path, None, log=lambda m: None)
    c.draw()
    v = c.mirror()["version"]
    c.go("Mix Sends")
    m = c.mirror()
    assert m["page"] == "Mix Sends" and m["version"] > v and m["connected"] is False
    c.draw(9, "running")
    assert c.key_states[("Mix Sends", 9)] == "running"
    assert c.mirror_key(9).size == (96, 96)


def test_new_track_preset_picks_category_then_preset(tmp_path):
    fmt, kind, tb = El("AXPopUpButton", "Mono"), El("AXPopUpButton", "Audio Track"), El("AXPopUpButton", "Samples")
    create = El("AXButton", "Create")
    win = El("AXWindow", "New Tracks", [fmt, kind, tb, create])
    app = make_app([El("AXWindow", "Edit: Song")])
    sys_ = TrackSys(app, [])
    sys_.key = lambda *a, **k: app.kids.append(win) if win not in app.kids else None
    create.on_press = lambda: app.kids.remove(win)
    preset = El("AXPopUpButton", "Addictive Drums")
    picks = []

    def choose(el, path, *a, **k):
        picks.append((el.a.get("AXTitle"), path))
        if path[0] == "Track Presets":
            kind.a["AXTitle"] = "Track Presets"
            win.kids.insert(2, El("AXPopUpButton", "INSTRUMENTS"))
            win.kids.insert(3, preset)
        elif el is preset:
            preset.a["AXTitle"] = path[0]
        else:
            raise E.NotFound("not here")
    r = Runner(sys_, lib_with(tmp_path, m="steps:\n- new track preset: INSTRUMENTS > SD3\n"), log=lambda m: None)
    r.choose_from = choose
    r.run("m")
    assert picks[0] == ("Audio Track", ["Track Presets", "INSTRUMENTS"])
    assert ("Addictive Drums", ["SD3"]) in picks and create.presses == 1


def test_plugin_names_and_matching(tmp_path, monkeypatch):
    from ptdeck import plugins as P
    assert P.display_name("iZRX11De-clickAAXHook.aaxplugin") == ("RX 11 De-click", "iZotope")
    assert P.display_name("uaudio_ua_1176_rev_a.aaxplugin")[0] == "UADx UA 1176 Rev A"
    assert P.same_plugin("UADx UA 1176 Rev A", "UADx 1176 Rev A Compressor")
    assert P.same_plugin("UADx Neve 1073", "UADx 1073 Preamp and EQ")
    assert not P.same_plugin("FabFilter Pro-Q 3", "FabFilter Pro-Q 4")
    for n in ("FabFilter Pro-Q 4.aaxplugin", "WaveShell1-AAX 15.5.aaxplugin", "Soundtoys/EchoBoy.aaxplugin"):
        (tmp_path / n).mkdir(parents=True)
    monkeypatch.setattr(P, "WAVES", tmp_path / "no-waves")      # don't list the Waves plug-ins on this Mac
    names = [p["name"] for p in P.scan(tmp_path)]
    assert names == ["FabFilter Pro-Q 4", "EchoBoy"] or sorted(names) == ["EchoBoy", "FabFilter Pro-Q 4"]
    y = P.macro_yaml("Assign X: Y", "X: Y", "Vendor", "first free")
    import yaml as _y
    m = _y.safe_load(y)
    assert m["name"] == "Assign X: Y" and m["steps"][0] == {"insert plugin": "X: Y", "slot": "first free", "category": "Vendor"}


def test_manager_makes_plugin_button(tmp_path):
    import shutil
    from ptdeck.manager import Manager
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    (tmp_path / "macros").mkdir()
    (tmp_path / "icons").mkdir()
    mgr = Manager(tmp_path, log=lambda m: None)
    r = mgr.plugin_button("FabFilter Pro-C 3", "FabFilter", "first free", "Recording")
    assert r["macro"] == "Assign FabFilter Pro-C 3" and (tmp_path / "macros" / r["file"]).exists()
    keys = {b["key"]: b for b in D.load_config(tmp_path / "deck.yaml")["pages"]["Recording"]}
    assert keys[r["key"] + 1]["macro"] == "Assign FabFilter Pro-C 3"
    a = mgr.save_icon("pic", "data:image/png;base64," + __import__("base64").b64encode(
        _png_bytes()).decode())
    b = mgr.save_icon("pic", "data:image/png;base64," + __import__("base64").b64encode(_png_bytes()).decode())
    assert a == "pic.png" and b == "pic-2.png"                                  # never overwrites


def _png_bytes():
    import io as _io
    from PIL import Image
    buf = _io.BytesIO()
    Image.new("RGB", (60, 30), "red").save(buf, "PNG")
    return buf.getvalue()


def _plugin_win(name, track, letter):
    sel, pos = El("AXPopUpButton", "Track Selector"), El("AXPopUpButton", "Insert Position selector")
    sel.a["AXValue"], pos.a["AXValue"] = track, letter.lower()
    return El("AXWindow", f"Plug-in: {name}", [sel, pos, El("AXButton", "Effect Bypass")])


def test_open_plugin_active_toggle_and_remove(tmp_path):
    prn = header("(PRINT)", "Aux", {"F": ("open", "Oxford Inflator")})
    app = make_app([El("AXWindow", "Edit: Song", [prn], size=(3000, 2000)), _plugin_win("Oxford Inflator", "(PRINT)", "F")])
    sys_ = TrackSys(app, [])
    lib = lib_with(tmp_path, a="steps:\n- toggle open plugin active:\n", r="steps:\n- remove open plugin:\n")
    r = Runner(sys_, lib, log=lambda m: None)
    r.run("a")
    from ptdeck.keys import CMD, CTRL
    assert sys_.clicks and sys_.clicks[-1][4] == CMD | CTRL                 # Cmd+Ctrl-click = inactive/active
    chosen = []
    asg = E.find_one(prn, "button", "Insert Assignment F")

    def choose(el, path, *a, **k):
        chosen.append((el.a.get("AXTitle"), path))
        asg.a["AXValue"] = "unassigned"
    r.choose_from = choose
    r.run("r")
    assert chosen == [("Insert selector F", ["no insert"])]

    # Inactive plug-ins lose their window: the key then works on the last one it saw.
    asg.a["AXValue"] = "Oxford Inflator"
    sel = E.find_one(prn, "button", "Insert selector F")
    sel.a["AXValue"] = "inactive"
    app.kids = [k for k in app.kids if not str(k.attr("AXTitle")).startswith("Plug-in")]
    n = len(sys_.clicks)

    def click(x, y, button="left", count=1, flags=0):
        sys_.clicks.append((x, y, button, count, flags))
        sel.a["AXValue"] = ""
    sys_.click = click
    r.run("a")
    assert len(sys_.clicks) == n + 1 and sel.a["AXValue"] == ""
    app2 = make_app([El("AXWindow", "Edit: Song", [prn], size=(3000, 2000))])
    with pytest.raises(MacroError):
        Runner(TrackSys(app2, []), lib, log=lambda m: None).run("r")


def test_empty_slot_opens_its_plugin_menu(tmp_path):
    prn = header("(PRINT)", "Aux")
    app = make_app([El("AXWindow", "Edit: Song", [prn], size=(3000, 2000))])
    lib = lib_with(tmp_path, m="steps:\n- plugin window: 3\n  track: '(PRINT)'\n  if empty: choose plug-in\n",
                   n="steps:\n- plugin window: 3\n  track: '(PRINT)'\n")
    sys_ = TrackSys(app, [])
    sel = E.find_one(prn, "button", "Insert selector C")
    sel.a.update({"AXPosition": (100, 200), "AXSize": (40, 10)})
    r = Runner(sys_, lib, log=lambda m: None)
    r.run("m")
    assert sys_.clicks == [(120, 205, "left", 1, 0)] and sel.presses == 0     # one real click, nothing else
    assert r.hold_live_until > __import__("time").time()                    # live keys stay quiet
    c = D.DeckController.__new__(D.DeckController)
    c.busy, c.runner, c.slots = False, r, [{"live": 1, "live track": "(PRINT)"}]
    r.menu_on_screen = lambda: True
    assert c.poll_live() == []                                              # menu still open: hands off
    r.menu_on_screen = lambda: False
    c.poll_metric = lambda fresh=False: ["menu closed: reading again"]
    c.live, c.page, c.log = {}, "Mixing", (lambda m: None)
    c._poller = r
    r.read_inserts = lambda track: {}
    assert c.poll_live()[0] == "menu closed: reading again" and r.hold_live_until == 0
    with pytest.raises(MacroError):
        r.run("n")                                     # without 'if empty' it's still an error


def test_waves_plugins_listed_from_waves_folder(tmp_path):
    from ptdeck import plugins as P
    for n in ("Plug-Ins V14/CLA-76.bundle", "Plug-Ins V14/OldOnly.bundle", "Plug-Ins V15/CLA-76.bundle",
              "Plug-Ins V15/SSLComp.bundle", "Plug-Ins V15/WavesLib.bundle"):
        (tmp_path / n).mkdir(parents=True)
    got = P.scan_waves(tmp_path)
    assert sorted(p["name"] for p in got) == ["CLA-76", "OldOnly", "SSLComp"]
    assert all(p["vendor"] == "Waves" for p in got)


def test_inactive_plugin_opened_by_insert_key_can_be_toggled_and_removed(tmp_path):
    trk = header("//dly", "Aux", {"B": ("inactive", "TSAR-1R Reverb")})
    small = El("AXWindow", "Plug-in: TSAR-1R Reverb")            # inactive: no track/slot pop-ups
    app = make_app([El("AXWindow", "Edit: Song", [trk], size=(3000, 2000))])
    sys_ = TrackSys(app, [])
    sel = E.find_one(trk, "button", "Insert selector B")
    asg = E.find_one(trk, "button", "Insert Assignment B")
    asg.on_press = lambda: app.kids.append(small)
    lib = lib_with(tmp_path, k="steps:\n- plugin window: 2\n  track: '//dly'\n",
                   a="steps:\n- toggle open plugin active:\n", r="steps:\n- remove open plugin:\n")
    r = Runner(sys_, lib, log=lambda m: None)
    r.run("k")                                       # opens the small window, remembers //dly slot B

    def click(x, y, button="left", count=1, flags=0):
        sys_.clicks.append(flags)
        sel.a["AXValue"] = "" if sel.a.get("AXValue") == "inactive" else "inactive"
    sys_.click = click
    r.run("a")
    assert sel.a["AXValue"] == ""                     # active again
    r.choose_from = lambda el, path, *a, **k: asg.a.update(AXValue="unassigned")
    r.run("r")
    assert asg.a["AXValue"] == "unassigned"
    with pytest.raises(MacroError):
        r.run("a")                                    # slot is empty now: says so


def test_remove_falls_back_to_real_clicks_for_inactive_plugins(tmp_path):
    trk = header("//dly", "Aux", {"B": ("inactive", "PT93")})
    app = make_app([El("AXWindow", "Edit: Song", [trk], size=(3000, 2000))])
    sys_ = TrackSys(app, [])
    sel = E.find_one(trk, "button", "Insert selector B")
    asg = E.find_one(trk, "button", "Insert Assignment B")
    sel.a.update({"AXPosition": (100, 300), "AXSize": (60, 14)})
    item = El("AXMenuItem", "no insert")
    item.a.update({"AXPosition": (110, 320), "AXSize": (100, 16)})
    menu = El("AXWindow", "", [item])

    def click(x, y, button="left", count=1, flags=0):
        sys_.clicks.append((x, y))
        if (x, y) == (130, 307):
            app.kids.append(menu)                 # the slot's menu opens
        elif (x, y) == (160, 328):
            asg.a["AXValue"] = "unassigned"       # 'no insert' clicked
    sys_.click = click
    from ptdeck import settings
    lib = lib_with(tmp_path, r="steps:\n- remove open plugin:\n")
    settings.put(lib.folder.parent, "last plugin", {"track": "//dly", "slot": "B", "name": "PT93"})
    r = Runner(sys_, lib, log=lambda m: None)
    r.choose_from = lambda *a, **k: None          # the quick way is ignored for inactive plug-ins
    r.run("r")
    assert asg.a["AXValue"] == "unassigned" and sys_.clicks == [(130, 307), (160, 328)]


def test_plugin_search_takes_a_close_match():
    R = Runner
    item = El("AXMenuItem", "Renaissance Axx Mono")
    assert R._close_plugin_match(item, "Renaissance Axx")
    assert R._close_plugin_match(El("AXMenuItem", "UADx 1176 Rev A"), "UADx 1176 Rev A Compressor")
    assert not R._close_plugin_match(El("AXMenuItem", "Renaissance Bass"), "Renaissance Axx")
    cat = El("AXMenuItem", "EQ", [El("AXWindow", "")])
    assert not R._close_plugin_match(cat, "SSL EQ")          # a category, not a plug-in


def test_plugin_preset_from_pro_tools_preset_menu(tmp_path):
    lib_pop = El("AXPopUpButton", "Librarian menu", value="<factory default>")
    win = El("AXWindow", "Plug-in: Studio Verse Audio Effects", [lib_pop])
    app = make_app([El("AXWindow", "Edit: Song"), win])
    picks = []
    r = Runner(TrackSys(app, []), lib_with(tmp_path, m="steps:\n- plugin preset: EAS NAM\n"), log=lambda m: None)

    def choose(el, path, *a, **k):
        picks.append((el.a["AXTitle"], path))
        el.a["AXValue"] = path[-1]
    r.choose_from = choose
    r.run("m")
    assert picks == [("Librarian menu", ["EAS NAM"])]
    r.run("m")
    assert len(picks) == 1                              # already loaded: left alone
    lib_pop.a["AXValue"] = "<factory default>"
    r.choose_from = lambda *a, **k: None                # the pick doesn't take
    with pytest.raises(MacroError):
        r.run("m")
    assert Runner._item_matches(El("AXMenuItem", "Studio Verse Audio Effects (mono)"), "Studio Verse Audio Effects")


def test_insert_plugin_preferred_slot_or_first_free(tmp_path):
    trk = header("Gtr", inserts={"A": ("", "LockOn"), "B": ("", "Comp")})
    app, _ = edit_app(trk)
    picked = []
    lib = lib_with(tmp_path, m="steps:\n- insert plugin: NAM\n  slot: 2 or first free\n")
    r = Runner(TrackSys(app, ["Gtr"]), lib, log=lambda m: None)
    r.choose_from = lambda el, path, *a, **k: picked.append(el.a["AXTitle"])
    r.run("m")
    assert picked == ["Insert selector C"]                       # 2 taken -> first free (C)
    E.find_one(trk, "button", "Insert selector B").a["AXValue"] = "unassigned"
    E.find_one(trk, "button", "Insert Assignment B").a["AXValue"] = "unassigned"
    r.run("m")
    assert picked[-1] == "Insert selector B"                     # 2 free -> slot 2


def test_ptsl_reconnects_for_reads_but_not_for_changes():
    from ptdeck import ptsl as PT
    calls = []

    class Fake(PT.PTSL):
        def __init__(self):
            self.session_id = "old"

        def connect(self):
            calls.append("connect")
            self.session_id = "new"

        def _send(self, num, body, timeout=None):
            calls.append(num)
            if self.session_id == "old":
                raise PT.PTSLError("command failed (Failed)")
            return {"ok": True}
    f = Fake()
    assert f.run("GetTrackList", {}) == {"ok": True} and "connect" in calls   # reads: reconnect + retry
    g = Fake()
    with pytest.raises(PT.PTSLError):
        g.run("SaveSession", {})                                             # changes: never twice


def test_inactive_and_remove_wheel_scroll_to_the_track_but_opening_does_not(tmp_path):
    prn = header("(PRINT)", "Aux", {"F": ("open", "Oxford Inflator")})
    win = _plugin_win("Oxford Inflator", "(PRINT)", "F")
    app = make_app([El("AXWindow", "Edit: Song", [prn], size=(3000, 2000)), win])
    sys_ = TrackSys(app, [])
    sel = E.find_one(prn, "button", "Insert selector F")
    asg = E.find_one(prn, "button", "Insert Assignment F")
    wheel = []

    def scroll(x, y, dy):                      # the wheel moves the track's slots by dy
        wheel.append(dy)
        for el in (sel, asg):
            el.a["AXPosition"] = (el.a["AXPosition"][0], el.a["AXPosition"][1] + dy)
    sys_.scroll, sys_.move_mouse, sys_.mouse_position = scroll, (lambda x, y: None), (lambda: (5, 5))
    lib = lib_with(tmp_path, a="steps:\n- toggle open plugin active:\n", r="steps:\n- remove open plugin:\n",
                   o="steps:\n- plugin window: 6\n  track: '(PRINT)'\n")
    r = Runner(sys_, lib, log=lambda m: None)
    dialog = []
    r.scroll_to_track = lambda t: dialog.append(t)
    r.run("o")
    r.run("a")
    assert wheel == [] and dialog == []                      # already in view: no scrolling
    for el in (sel, asg):
        el.a["AXPosition"] = (100, 5000)                     # (PRINT) scrolled out of view
    r.run("a")
    assert wheel and dialog == [] and 0 <= sel.a["AXPosition"][1] <= 2000    # wheel brought it in
    for el in (sel, asg):
        el.a["AXPosition"] = (100, -3000)
    r.choose_from = lambda *a, **k: asg.a.update(AXValue="unassigned")
    r.run("r")
    assert dialog == [] and 0 <= sel.a["AXPosition"][1] <= 2000


def test_scroll_to_track_types_the_name_and_never_leaves_the_dialog_stuck(tmp_path):
    field = El("AXTextField", "Track")
    dialog = El("AXWindow", "Scroll to Track", [field, El("AXButton", "OK")])
    app = make_app([El("AXWindow", "Edit: Song")])
    sys_ = TrackSys(app, [])
    keys = []

    def key(code, flags=0):
        keys.append(code)
    sys_.key = key
    r = Runner(sys_, lib_with(tmp_path), log=lambda m: None)
    r._safe_menu = lambda path: app.kids.append(dialog)
    typed = []
    r.type_into = lambda el, text: typed.append(text)
    with pytest.raises(MacroError):                        # Return didn't close it -> Escape, error
        r.scroll_to_track("(PRINT)")
    from ptdeck.keys import parse_combo
    assert typed == ["(PRINT)"] and keys[-1] == parse_combo("escape")[0]


def test_carpet_keys_render_and_are_never_saved(tmp_path):
    import shutil
    from ptdeck.manager import Manager
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    shutil.copytree(DECK / "icons", tmp_path / "icons")
    (tmp_path / "macros").mkdir()
    cfg = D.load_config(tmp_path / "deck.yaml")
    slots = D.layout(cfg, "Metric A/B", 32, tmp_path)
    carpet = next(i for i, b in enumerate(slots) if b and b.get("carpet"))
    img = D.render(slots[carpet], 96, tmp_path)
    assert img.getpixel((48, 48)) != (0, 0, 0)                 # the carpet, not a black key
    mgr = Manager(tmp_path, log=lambda m: None)
    mgr.move_button("Metric A/B", 1, 2)                         # rewrites the page
    saved = D.load_config(tmp_path / "deck.yaml")["pages"]["Metric A/B"]
    assert not any(b.get("carpet") or b.get("banner") for b in saved)


def test_plugin_pictures_from_the_manager(tmp_path):
    import shutil
    from ptdeck.manager import Manager
    from ptdeck import settings
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    shutil.copytree(DECK / "icons", tmp_path / "icons")
    (tmp_path / "macros").mkdir()
    (tmp_path / "macros" / "a.yaml").write_text("name: Assign Oxford Inflator\nsteps:\n- insert plugin: Oxford Inflator\n")
    cfg = D.load_config(tmp_path / "deck.yaml")
    cfg["pages"]["Recording"].append({"key": 3, "label": "Inflator", "macro": "Assign Oxford Inflator"})
    from ptdeck.manager import save_config
    save_config(tmp_path / "deck.yaml", cfg)
    settings.put(tmp_path, "seen plugins", ["Oxford Inflator", "UAD Neve 33609 C"])
    mgr = Manager(tmp_path, log=lambda m: None)
    names = [p["name"] for p in mgr.plugins()["plugins"]]
    assert "UAD Neve 33609 C" in names                                     # seen on your tracks
    r = mgr.plugin_picture("Oxford Inflator", icon="manley.png", on_buttons=True)
    assert r["icon"] == "plugins/Oxford Inflator.png" and r["buttons"] == 1
    assert D.plugin_icon(tmp_path, "Oxford Inflator") == "plugins/Oxford Inflator.png"
    keys = {b["key"]: b for b in D.load_config(tmp_path / "deck.yaml")["pages"]["Recording"]}
    assert keys[3]["icon"] == "plugins/Oxford Inflator.png"
    mgr.plugin_picture("Oxford Inflator", data="data:image/png;base64," + __import__("base64").b64encode(_png_bytes()).decode())
    assert D.plugin_icon(tmp_path, "Oxford Inflator")
    mgr.plugin_picture("Oxford Inflator", remove=True)
    assert D.plugin_icon(tmp_path, "Oxford Inflator") is None
    with pytest.raises(ValueError):
        mgr.plugin_picture("X", icon="../../etc/passwd")


def test_live_keys_remember_seen_plugins(tmp_path):
    from ptdeck import settings
    c = D.DeckController.__new__(D.DeckController)
    c.base = tmp_path
    c._saw_plugin("Oxford Inflator")
    c._saw_plugin("unassigned")
    assert settings.get(tmp_path, "seen plugins") == ["Oxford Inflator"]


def test_metric_sides_match_buttons(tmp_path):
    from ptdeck import settings, metric as M
    win, _ = metric_window()
    group = E.find_one(win, "group", "FXTDMEditView")
    mode = El("AXSlider", "Stereo Mode")
    mode.a.update({"AXValue": 0, "AXMaxValue": 4, "AXValueDescription": "Stereo"})
    match = El("AXSlider", "Loudness Match")
    match.a.update({"AXValue": 0, "AXMaxValue": 2047, "AXValueDescription": "Off"})
    group.kids += [mode, match]
    sys_ = TrackSys(make_app([win]), [])
    sx, sy = M.button_center((632, 348), (1500, 933), "sides")

    def click(x, y, *a, **k):
        sys_.clicks.append((x, y))
        if abs(x - sx) < 1 and abs(y - sy) < 1:
            mode.a["AXValueDescription"] = "Stereo" if mode.a["AXValueDescription"] == "Sides" else "Sides"
    sys_.click = click
    lib = lib_with(tmp_path, s="steps:\n- metric button: sides\n", m="steps:\n- metric button: match\n",
                   a="steps:\n- metric button: match all\n")
    r = Runner(sys_, lib, log=lambda m: None)
    r.run("s")
    assert mode.a["AXValueDescription"] == "Sides" and settings.get(lib.folder.parent, "metric sides") is True
    r.run("s")
    assert settings.get(lib.folder.parent, "metric sides") is False
    r.run("a")                                            # momentary: just clicks
    with pytest.raises(MacroError):
        r.run("m")                                        # nothing changed: says so
    on = D.metric_toggle_button({"metric toggle": "sides"}, True)
    off = D.metric_toggle_button({"metric toggle": "sides"}, False)
    assert on["label"] == "SIDES" and on["color"] != off["color"]
    D.render({"metric toggle": "match"}, 96, Path("."))


def test_bounce_auto_goes_real_time_only_with_active_hardware_inserts(tmp_path):
    gtr = header("Gtr", inserts={"A": ("", "Pro-Q 4"), "B": ("", "1176 HW")})
    vox = header("Vox", inserts={"A": ("inactive", "LA2A HW")})
    app, win = edit_app(gtr, vox)
    r = Runner(TrackSys(app, []), lib_with(tmp_path), log=lambda m: None)
    r.hardware_insert_names = lambda force=False: ["1176 HW", "LA2A HW"]
    assert r.active_hardware_inserts() == ["Gtr B: 1176 HW"]           # inactive ones don't count
    E.find_one(gtr, "button", "Insert selector B").a["AXValue"] = "inactive"
    assert r.active_hardware_inserts() == []                          # always read fresh
    E.find_one(vox, "button", "Insert selector A").a["AXValue"] = ""
    assert r.active_hardware_inserts() == ["Vox A: LA2A HW"]


def test_hardware_insert_names_learned_from_the_io_menu(tmp_path):
    from ptdeck import settings
    gtr = header("Gtr", inserts={"A": ("", "Pro-Q 4")})
    app, win = edit_app(gtr)
    io = El("AXMenuItem", "i/o", [El("AXWindow", "", [El("AXMenuItem", "1176 HW (Stereo)"), El("AXMenuItem", "LA2A HW")])])
    root = El("AXWindow", "", [El("AXMenuItem", "no insert"), El("AXMenuItem", "plug-in"), io])
    lib = lib_with(tmp_path)
    r = Runner(TrackSys(app, []), lib, log=lambda m: None)
    opened = []
    r.open_menu = lambda el: opened.append(el.a["AXTitle"]) or root
    r.close_menus = lambda: None
    assert r.hardware_insert_names() == ["1176 HW", "LA2A HW"]
    assert opened == ["Insert selector B"]                             # an empty slot's menu
    assert r.hardware_insert_names() == ["1176 HW", "LA2A HW"] and len(opened) == 1   # remembered
    assert settings.get(lib.folder.parent, "hardware inserts")["names"] == ["1176 HW", "LA2A HW"]


def test_fix_macro_addition_changes_only_that_line(tmp_path):
    import shutil
    from ptdeck.__main__ import apply_additions
    shutil.copy(TEST_DECK, tmp_path / "deck.yaml")
    (tmp_path / "macros").mkdir()
    m = tmp_path / "macros" / "b.yaml"
    m.write_text("name: B\nsteps:\n- bounce dialog:\n  offline: true\n  bits: 24\n")
    (tmp_path / "additions").mkdir()
    (tmp_path / "additions" / "f.yaml").write_text('fix macro: b.yaml\nreplace:\n  "  offline: true": "  offline: auto"\n')
    apply_additions(base=tmp_path)
    assert m.read_text() == "name: B\nsteps:\n- bounce dialog:\n  offline: auto\n  bits: 24\n"
    m.write_text("name: B\nsteps:\n- bounce dialog:\n  offline: true\n")
    apply_additions(base=tmp_path)
    assert "offline: true" in m.read_text()                 # only ever once


def test_bounce_keeps_going_when_the_output_name_is_missing(tmp_path):
    from ptdeck.keys import parse_combo
    src = El("AXPopUpButton", "Analog 1-2 (Stereo)")
    bitp, ratep = El("AXPopUpButton", "32 Bit Float"), El("AXPopUpButton", "48 kHz")
    win = El("AXWindow", "Bounce Mix", [El("AXTextField", None), src, bitp, ratep,
                                        El("AXCheckBox", "Offline", value=1)])
    app = make_app([El("AXWindow", "Edit: Song"), win])
    sys_ = TrackSys(app, [])
    r = Runner(sys_, lib_with(tmp_path, m="steps:\n- bounce dialog:\n  source: 'Built-in Output 1-2 (Stereo)*'\n"
                                          "  bits: 24\n  offline: false\n"), log=lambda m: None)
    r.session_sample_rate = lambda: 48000
    r.session_info = lambda: ("Song.ptx", "/S/Song.ptx")
    r.type_into = lambda el, t: None
    r.popup_by_label = lambda w, lab: {"Mix Source:": src, "Bit Depth:": bitp, "Sample Rate:": ratep}[lab]
    picks = []

    def choose(pop, path, *a, **k):
        if pop is src:
            raise E.NotFound("'Built-in Output 1-2 (Stereo)*' in the pop-up menu")
        picks.append(path)
        pop.a["AXTitle"] = path
    r.choose_from = choose
    r.run("m")
    assert "24 Bit" in picks and src.a["AXTitle"] == "Analog 1-2 (Stereo)"     # carried on, kept 1-2
    assert (parse_combo("escape")[0], 0) not in sys_.keys                      # never Escaped the dialog


def test_hardware_scan_reads_pro_tools_slot_order_and_skips_vca(tmp_path):
    # Real Pro Tools: 5 selectors, then 5 slot names, in each 'Inserts' group.
    sel = [El("AXButton", f"Insert selector {L}", value="") for L in "ABCDE"]
    asg = [El("AXButton", f"Insert Assignment {L}", value=v) for L, v in zip("ABCDE", ["Pro-Q 4", "unassigned", "RNC.L", "unassigned", "unassigned"])]
    trk = El("AXGroup", "Gtr - Audio Track", [El("AXGroup", "Inserts A-E", sel + asg)])
    vca = El("AXGroup", "<DRUMS> - VCA Track", [El("AXGroup", "Inserts A-E", [])])
    app, _ = edit_app(trk, vca)
    r = Runner(TrackSys(app, []), lib_with(tmp_path), log=lambda m: None)
    r.hardware_insert_names = lambda force=False: ["RNC.L"]
    assert r.active_hardware_inserts() == ["Gtr C: RNC.L"]


def test_insert_slots_found_once_per_session(tmp_path):
    gtr = header("Gtr", inserts={"A": ("", "RNC.L")})
    app, _ = edit_app(gtr)
    r = Runner(TrackSys(app, []), lib_with(tmp_path), log=lambda m: None)
    Runner._slots_cache = None
    r.session_info = lambda: ("Song.ptx", "/S/Song.ptx")
    r.sys.ptsl().track_info = lambda which="all": [{"name": "Gtr", "color": None}]
    searches = []
    real = E.find_all
    def counting(root, role=None, name=None, max_depth=25):
        if name == "* - * Track":
            searches.append(1)
        return real(root, role, name, max_depth)
    import ptdeck.macros as MM
    MM.E.find_all, saved = counting, MM.E.find_all
    try:
        r.hardware_insert_names = lambda force=False: ["RNC.L"]
        assert r.active_hardware_inserts() == ["Gtr A: RNC.L"]
        E.find_one(gtr, "button", "Insert selector A").a["AXValue"] = "inactive"
        assert r.active_hardware_inserts() == []
        assert len(searches) == 1                                     # headers found once
        r.sys.ptsl().track_info = lambda which="all": [{"name": "Gtr"}, {"name": "New"}]
        r.active_hardware_inserts()
        assert len(searches) == 2                                     # a track added: found again
    finally:
        MM.E.find_all = saved
        Runner._slots_cache = None
