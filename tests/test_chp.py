"""Tests for what CHP adds on top of PT Deck: 'if menu', menu-tick keys, page settings, key fonts,
and gradients (from Chris's CHP). Kept in their own file so changes merge cleanly between the two repos.
No test here reads a real deck: each builds its own."""
from pathlib import Path

import yaml

from ptdeck import deck as D
from ptdeck.macros import Library, Runner, validate

from test_ptdeck import El, FakeSys, make_app, lib_with

ROOT = Path(__file__).resolve().parent.parent


def solo_menu(afl_ticked=False):
    sip = El("AXMenuItem", "SIP (Solo In Place)", AXMenuItemMarkChar=None if afl_ticked else "✓")
    afl = El("AXMenuItem", "AFL (After Fader Listen)", AXMenuItemMarkChar="✓" if afl_ticked else None)
    mode = El("AXMenuItem", "Solo Mode", [El("AXMenu", None, [sip, afl])])
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "Options", [El("AXMenu", None, [mode])])])
    return bar, sip, afl


TOGGLE = """steps:
- if menu: Options > Solo Mode > AFL*
  then:
  - menu: Options > Solo Mode > SIP*
  else:
  - menu: Options > Solo Mode > AFL*
"""


def test_if_menu_reads_the_tick(tmp_path):
    bar, sip, afl = solo_menu(afl_ticked=False)
    r = Runner(FakeSys(make_app([El("AXWindow", "Edit: x")], bar)), lib_with(tmp_path, solo=TOGGLE), log=lambda m: None)
    r.run("solo")
    assert (sip.presses, afl.presses) == (0, 1)
    assert r.menu_changes == [("options > solo mode > afl*", None)]


def test_if_menu_trusts_what_the_deck_believes(tmp_path):
    bar, sip, afl = solo_menu(afl_ticked=False)           # Pro Tools' closed menu still says SIP...
    r = Runner(FakeSys(make_app([El("AXWindow", "Edit: x")], bar)), lib_with(tmp_path, solo=TOGGLE), log=lambda m: None)
    r.believed = {"options > solo mode > afl*": True}       # ...but CHP just switched it to AFL
    r.run("solo")
    assert (sip.presses, afl.presses) == (1, 0)


def test_if_menu_validates_its_branches(tmp_path):
    lib = lib_with(tmp_path, m="steps:\n- if menu: View > Clip > Name\n  ticked: false\n  then:\n  - frobnicate: x\n")
    assert any("frobnicate" in p for p in validate(lib.get("m"), lib))


def test_menu_set_records_the_state(tmp_path):
    name = El("AXMenuItem", "Name", AXMenuItemMarkChar="✓")
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "View", [El("AXMenu", None, [
        El("AXMenuItem", "Clip", [El("AXMenu", None, [name])])])])])
    r = Runner(FakeSys(make_app([El("AXWindow", "Edit: x")], bar)),
               lib_with(tmp_path, m="steps:\n- menu: View > Clip > Name\n  set: off\n"), log=lambda m: None)
    r.run("m")
    assert name.presses == 1 and r.menu_changes == [("view > clip > name", False)]


def deck_with(tmp_path, cfg):
    (tmp_path / "deck.yaml").write_text(yaml.safe_dump(cfg))
    return D.DeckController(tmp_path, runner=None, log=lambda m: None)


def test_lit_menu_keys_follow_changes_and_pick_one_modes(tmp_path):
    c = deck_with(tmp_path, {"home": "Main", "pages": {"Main": [
        {"key": 1, "label": "SIP", "lit label": "AFL", "lit menu": "Options > Solo Mode > AFL*", "color": "#37a83b", "macro": "x"},
        {"key": 2, "label": "Clip\\nName", "color": "#4a0032", "lit color": "#a3006e", "lit menu": "View > Clip > Name", "macro": "y"},
    ]}})
    c.slots = D.layout(c.cfg, "Main", 32)
    assert c.shown(0, c.slots[0])["label"] == "SIP"
    c.note_menu_changes([("options > solo mode > afl*", None)])
    assert c.shown(0, c.slots[0])["label"] == "AFL"
    c.note_menu_changes([("options > solo mode > sip*", None)])       # same submenu: AFL goes off
    assert c.shown(0, c.slots[0])["label"] == "SIP"
    c.note_menu_changes([("view > clip > name", None)])
    assert c.shown(1, c.slots[1])["color"] == "#a3006e"
    c.note_menu_changes([("view > clip > name", False)])
    assert c.shown(1, c.slots[1])["color"] == "#4a0032"


def test_poll_menus_ignores_a_stale_tick_but_not_a_real_change(tmp_path):
    item = El("AXMenuItem", "Name", AXMenuItemMarkChar=None)
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "View", [El("AXMenu", None, [
        El("AXMenuItem", "Clip", [El("AXMenu", None, [item])])])])])
    runner = Runner(FakeSys(make_app([El("AXWindow", "Edit: x")], bar)), Library(tmp_path), log=lambda m: None)
    (tmp_path / "deck.yaml").write_text(yaml.safe_dump({"home": "Main", "pages": {"Main": [
        {"key": 1, "label": "Clip", "lit menu": "View > Clip > Name", "lit color": "#a3006e", "macro": "x"}]}}))
    c = D.DeckController(tmp_path, runner, log=lambda m: None)
    c.slots = D.layout(c.cfg, "Main", 32)
    assert c.poll_menus(fresh=True) == [0] and c.menu_lit["view > clip > name"] is False
    c.note_menu_changes([("view > clip > name", None)])       # a key turned it on
    assert c.poll_menus(fresh=True) == []                    # closed menu still says off: keep "on"
    assert c.menu_lit["view > clip > name"] is True
    item.a["AXMenuItemMarkChar"] = "✓"                        # Pro Tools catches up
    c.poll_menus(fresh=True)
    item.a["AXMenuItemMarkChar"] = None                       # then turned off in Pro Tools itself
    assert c.poll_menus(fresh=True) == [0] and c.menu_lit["view > clip > name"] is False


def test_page_settings_and_key_font(tmp_path):
    cfg = {"home": "Main", "page titles": True, "icon style": "designed",
           "page settings": {"Plain": {"page titles": False, "icon style": "classic", "key font": "Futura PT Medium"}},
           "pages": {"Main": [], "Plain": [{"key": 9, "label": "Hi", "macro": "x"}], "Fancy": [{"key": 9, "label": "Hi", "macro": "x"}]}}
    plain = D.layout(cfg, "Plain", 32)
    assert plain[1] is None and plain[0]["back"]                    # no title banner, still a Back key
    assert plain[8]["_font"] == "Futura PT Medium" and "_look" not in plain[8]
    fancy = D.layout(cfg, "Fancy", 32)
    assert fancy[1] and fancy[1].get("banner") and fancy[8]["_look"] == "designed"
    img = D.render(plain[8], 96, tmp_path)                          # unknown font falls back, still draws
    assert img.size == (96, 96)


def test_gradient_key(tmp_path):
    img = D.render({"label": "Color\\nPalette", "gradient": ["#1b3fae", "#e0242a"], "macro": "x"}, 96, tmp_path)
    assert img.getpixel((2, 2)) != img.getpixel((93, 2))


DEJAVU = Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf")


def test_key_font_found_in_a_hidden_adobe_style_file(tmp_path, monkeypatch):
    import shutil
    import pytest
    if not DEJAVU.exists():
        pytest.skip("needs a test font")
    hidden = tmp_path / "livetype" / ".r"
    hidden.mkdir(parents=True)
    shutil.copy(DEJAVU, hidden / ".18304.ttf")                   # Adobe Fonts style: no clue in the file name
    monkeypatch.setattr(D, "FONT_DIRS", [str(tmp_path / "livetype")])
    monkeypatch.setattr(D, "_named_index", None)
    monkeypatch.setattr(D, "_coretext_font", lambda name: None)
    assert D.find_font("DejaVu Sans Mono") == (str(hidden / ".18304.ttf"), 0)


def test_key_font_asks_macos_first(monkeypatch):
    import sys
    import types
    import pytest
    if not DEJAVU.exists():
        pytest.skip("needs a test font")

    class URL:
        def path(self):
            return str(DEJAVU)
    ct = types.SimpleNamespace(
        kCTFontURLAttribute="url",
        CTFontCreateWithName=lambda name, size, m: name,
        CTFontCopyFullName=lambda f: "Futura PT Medium" if f == "Futura PT Medium" else "Helvetica",
        CTFontCopyPostScriptName=lambda f: "FuturaPT-Medium" if f == "Futura PT Medium" else "Helvetica",
        CTFontCopyAttribute=lambda f, k: URL())
    monkeypatch.setitem(sys.modules, "CoreText", ct)
    assert D._coretext_font("Futura PT Medium") == (str(DEJAVU), 0)
    assert D._coretext_font("Gill Sans Nova") is None            # macOS's stand-in font doesn't count


def test_missing_key_font_is_logged_once(tmp_path, monkeypatch):
    monkeypatch.setattr(D, "find_font", lambda name: None)
    monkeypatch.setattr(D, "missing_fonts", set())
    logs = []
    (tmp_path / "deck.yaml").write_text(yaml.safe_dump({"home": "Main", "key font": "Nope Sans",
                                                        "pages": {"Main": [{"key": 1, "label": "Hi", "macro": "x"}]}}))
    c = D.DeckController(tmp_path, runner=None, log=logs.append)
    D.render(D.layout(c.cfg, "Main", 32)[0], 96, tmp_path)
    c.draw(); c.draw()
    assert len([m for m in logs if "Nope Sans" in m]) == 1


def test_font_candidates_fall_back_like_the_old_chp():
    assert D.font_candidates("Futura PT Medium") == ["Futura PT Medium", "Futura PT", "Futura Medium", "Futura"]
    assert D.font_candidates("Helvetica") == ["Helvetica"]
    assert D.font_candidates("Avenir Next Demi Bold")[:2] == ["Avenir Next Demi Bold", "Avenir Next Demi"]


def test_missing_futura_pt_uses_apples_futura_medium(monkeypatch):
    installed = {"futuramedium": ("/System/Library/Fonts/Supplemental/Futura.ttc", 1)}   # as on a Mac
    monkeypatch.setattr(D, "_coretext_font", lambda name: None)
    monkeypatch.setattr(D, "_font_index", lambda: installed)
    monkeypatch.setattr(D, "font_substitutes", {})
    assert D.find_font("Futura PT Medium") == ("/System/Library/Fonts/Supplemental/Futura.ttc", 1)
    assert D.font_substitutes == {"Futura PT Medium": "Futura Medium"}


def test_palette_color_keys_show_pro_tools_colours(tmp_path):
    from ptdeck import settings
    from ptdeck.ptsl import COLOUR_BASE

    class PT:
        def palette(self):
            return [(10, 20, 30), (200, 0, 0), (0, 200, 0)]

    class Sys:
        def ptsl(self):
            return PT()

    class R:
        sys = Sys()
    (tmp_path / "deck.yaml").write_text(yaml.safe_dump({"home": "Main", "pages": {"Main": [
        {"key": 1, "macro": "x", "color": "#123456", "palette color": 1 + COLOUR_BASE}]}}))
    c = D.DeckController(tmp_path, R(), log=lambda m: None)
    c.slots = D.layout(c.cfg, "Main", 32)
    assert D.render(c.slots[0], 96, tmp_path).getpixel((48, 48)) == (0x12, 0x34, 0x56)   # before reading
    assert c.poll_palette() == [0]
    assert settings.get(tmp_path, "track palette")[1] == "#c80000"
    assert D.render(c.slots[0], 96, tmp_path).getpixel((48, 48)) == (200, 0, 0)
    assert c.poll_palette() == []                                   # read once per run


def solo_mode_bar():
    """Pro Tools' Solo Mode menu: two groups split by a separator."""
    names = ["SIP (Solo In Place)", "AFL (After Fader Listen)", "PFL (Pre Fader Listen)", "",
             "Latch", "Momentary", "X-OR (Cancels Previous Solo)"]
    items = {n: El("AXMenuItem", n, AXMenuItemMarkChar=None) for n in names}
    mode = El("AXMenuItem", "Solo Mode", [El("AXMenu", None, list(items.values()))])
    bar = El("AXMenuBar", None, [El("AXMenuBarItem", "Options", [El("AXMenu", None, [mode])])])
    return bar, items


def test_solo_mode_has_two_pick_one_groups(tmp_path):
    bar, _ = solo_mode_bar()
    runner = Runner(FakeSys(make_app([El("AXWindow", "Edit: x")], bar)), Library(tmp_path), log=lambda m: None)
    (tmp_path / "deck.yaml").write_text(yaml.safe_dump({"home": "Main", "pages": {"Main": [
        {"key": 1, "label": "AFL X-OR", "macro": "a", "lit color": "#ffaa00",
         "lit menu": ["Options > Solo Mode > AFL*", "Options > Solo Mode > X-OR*"]},
        {"key": 2, "label": "SIP Latch", "macro": "b", "lit color": "#ffaa00",
         "lit menu": ["Options > Solo Mode > SIP*", "Options > Solo Mode > Latch*"]}]}}))
    c = D.DeckController(tmp_path, runner, log=lambda m: None)
    c.slots = D.layout(c.cfg, "Main", 32)
    key = Runner.menu_key
    c.menu_lit.update({key("Options > Solo Mode > SIP*"): True, key("Options > Solo Mode > Latch*"): True,
                       key("Options > Solo Mode > AFL*"): False, key("Options > Solo Mode > X-OR*"): False})
    assert c.shown(1, c.slots[1])["color"] == "#ffaa00" and c.shown(0, c.slots[0]).get("color") != "#ffaa00"
    # the AFL X-OR key: two menu steps
    c.note_menu_changes([(key("Options > Solo Mode > AFL*"), None), (key("Options > Solo Mode > X-OR*"), None)])
    assert c.menu_lit[key("Options > Solo Mode > AFL*")] is True          # X-OR didn't untick AFL
    assert c.menu_lit[key("Options > Solo Mode > SIP*")] is False
    assert c.menu_lit[key("Options > Solo Mode > Latch*")] is False
    assert c.shown(0, c.slots[0])["color"] == "#ffaa00" and c.shown(1, c.slots[1]).get("color") != "#ffaa00"


def test_unknown_menu_groups_are_forgotten_not_guessed(tmp_path):
    c = deck_with(tmp_path, {"home": "Main", "pages": {"Main": [{"key": 1, "label": "x", "macro": "x"}]}})
    c.menu_lit.update({"options > solo mode > afl*": True, "options > solo mode > latch*": True})
    c.note_menu_changes([("options > solo mode > x-or*", None)])          # no Pro Tools to read groups from
    assert c.menu_lit == {"options > solo mode > x-or*": True}           # others re-read later, not set off


def test_lit_menu_list_needs_every_item_ticked(tmp_path):
    bar, items = solo_mode_bar()
    runner = Runner(FakeSys(make_app([El("AXWindow", "Edit: x")], bar)), Library(tmp_path), log=lambda m: None)
    (tmp_path / "deck.yaml").write_text(yaml.safe_dump({"home": "Main", "pages": {"Main": [
        {"key": 1, "label": "SIP X-OR", "macro": "a", "lit color": "#ffaa00",
         "lit menu": ["Options > Solo Mode > SIP*", "Options > Solo Mode > X-OR*"]}]}}))
    c = D.DeckController(tmp_path, runner, log=lambda m: None)
    c.slots = D.layout(c.cfg, "Main", 32)
    items["SIP (Solo In Place)"].a["AXMenuItemMarkChar"] = "✓"
    items["Latch"].a["AXMenuItemMarkChar"] = "✓"
    c.poll_menus(fresh=True)
    assert c.shown(0, c.slots[0]).get("color") != "#ffaa00"                   # SIP + Latch: not this key
    items["Latch"].a["AXMenuItemMarkChar"] = None
    items["X-OR (Cancels Previous Solo)"].a["AXMenuItemMarkChar"] = "✓"
    assert c.poll_menus(fresh=True) == [0] and c.shown(0, c.slots[0])["color"] == "#ffaa00"


def test_lit_outline_shows_on_picture_keys(tmp_path):
    from PIL import Image
    (tmp_path / "icons").mkdir()
    Image.new("RGB", (96, 96), (10, 10, 10)).save(tmp_path / "icons" / "pic.png")
    b = {"icon": "pic.png", "macro": "x", "lit menu": "View > Clip > Name", "lit outline": "#22b8f0"}
    off = D.render(D.lit_button(b, False), 96, tmp_path)
    on = D.render(D.lit_button(b, True), 96, tmp_path)
    assert off.getpixel((5, 48)) == (10, 10, 10) and on.getpixel((5, 48)) == (34, 184, 240)


def test_lit_when_follows_a_remembered_value(tmp_path):
    from ptdeck import settings
    c = deck_with(tmp_path, {"home": "Main", "pages": {"Main": [
        {"key": 1, "label": "Buffer\\n128", "macro": "x", "color": "#606060", "lit when": {"buffer size": 128},
         "lit color": "#2e8b57"}]}})
    c.slots = D.layout(c.cfg, "Main", 32)
    assert c.shown(0, c.slots[0])["color"] == "#606060"                   # not known yet
    settings.put(tmp_path, "buffer size", 128)
    assert c.shown(0, c.slots[0])["color"] == "#2e8b57"
    settings.put(tmp_path, "buffer size", 1024)
    assert c.shown(0, c.slots[0])["color"] == "#606060"
