"""MetricAB's 16 reference slots: which one is selected, and the song names.

The plug-in shows its slots as a 4 x 4 grid (A-D across, 1-4 down). The selected slot comes
from its 'Selected Track' setting (0-15). The song names aren't readable by other apps, so
PT Deck takes a picture of the plug-in window and reads the text with macOS's own text
recognition (needs Screen Recording permission). Names are remembered in settings.json, so
the deck keeps showing them after the window is closed.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from . import elements as E
from . import settings

BASE = Path(__file__).resolve().parent.parent
WINDOW = "Plug-in: ADPTR MetricAB*"
LETTERS = "ABCD"

# Where the slot grid sits inside the plug-in area (the 'FXTDMEditView' group), as fractions
# of its width/height. Measured from a screenshot; the plug-in scales as one piece.
GRID = {"left": 0.2525, "right": 0.986, "top": 0.8296, "bottom": 0.9526}


def parse_slot(name) -> tuple[int, int]:
    """'B3' -> (column 1, row 2)."""
    m = re.fullmatch(r"\s*([A-Da-d])\s*([1-4])\s*", str(name))
    if not m:
        raise ValueError(f"MetricAB slots are A1 to D4 (got {name!r})")
    return LETTERS.index(m.group(1).upper()), int(m.group(2)) - 1


def slot_name(col: int, row: int) -> str:
    return f"{LETTERS[col]}{row + 1}"


def order(base=BASE) -> str:
    """How MetricAB numbers its slots: 'rows' (A1 B1 C1 D1 A2 ...) or 'columns' (A1 A2 A3 A4 B1 ...).
    PT Deck works this out by itself the first time it sees a slot selected."""
    return settings.get(base, "metric order", "rows")


def index_of(col: int, row: int, how: str) -> int:
    return row * 4 + col if how == "rows" else col * 4 + row


def cell_of(index: int, how: str) -> tuple[int, int]:
    a, b = divmod(int(index), 4)
    return (b, a) if how == "rows" else (a, b)


# The big A|B button's letters, as fractions of the plug-in area.
AB_LETTERS = {"A": (0.088, 0.660), "B": (0.148, 0.660)}


# Buttons around the A|B button (fractions of the plug-in area, measured from a screenshot),
# and the setting each one changes (so PT Deck can check it worked and light the deck key).
BUTTONS = {
    "sides": ((0.170, 0.5008), "Stereo Mode"),          # Sides: listen without the centre
    "match all": ((0.2085, 0.5008), "Loudness Match All"),  # two speakers: match all references
    "match": ((0.3385, 0.7846), "Loudness Match"),       # LOUDNESS Match (the selected reference)
}


def button_center(gpos, gsize, which: str) -> tuple[float, float]:
    (fx, fy), _ = BUTTONS[which]
    return gpos[0] + gsize[0] * fx, gpos[1] + gsize[1] * fy


def is_on(which: str, slider) -> bool:
    """Is Sides / Loudness Match on, from the plug-in's own setting?"""
    desc = str(slider.attr("AXValueDescription") or "").strip().lower()
    if which == "sides":
        return desc == "sides" or desc.startswith("side")
    if desc in ("on", "off"):
        return desc == "on"
    v, hi = float(slider.attr("AXValue") or 0), float(slider.attr("AXMaxValue") or 1)
    return v > hi / 2


def ab_center(gpos, gsize, side: str = "A") -> tuple[float, float]:
    fx, fy = AB_LETTERS[side]
    return gpos[0] + gsize[0] * fx, gpos[1] + gsize[1] * fy


def cell_center(gpos, gsize, col: int, row: int) -> tuple[float, float]:
    """Screen point in the middle of a slot's name, from the plug-in area's position/size."""
    w = (GRID["right"] - GRID["left"]) / 4
    h = (GRID["bottom"] - GRID["top"]) / 4
    fx = GRID["left"] + w * (col + 0.45)          # a little left of centre, clear of the ≡ menu
    fy = GRID["top"] + h * (row + 0.5)
    return gpos[0] + gsize[0] * fx, gpos[1] + gsize[1] * fy


def clean(text: str) -> str:
    t = re.sub(r"[\s=≡|]+$", "", text.strip())
    t = re.sub(r"\.(wav|flac|mp3|aiff?|m4a|ogg)$", "", t, flags=re.I).strip()
    return t.replace("_", " ")


def ab_from(slider) -> str:
    desc = str(slider.attr("AXValueDescription") or "").strip().upper()
    if desc in ("A", "B"):
        return desc
    v, hi = float(slider.attr("AXValue") or 0), float(slider.attr("AXMaxValue") or 1)
    return "B" if v > hi / 2 else "A"


class MetricReader:
    """Reads MetricAB through a Runner (for Accessibility) and its system (for pictures/text)."""

    def __init__(self, runner, base=BASE, log=lambda m: None):
        self.runner, self.base, self.log = runner, Path(base), log
        self._last_hash = None
        self.paused = lambda: False      # the deck sets this: True while a button's macro runs
        self._warned = False

    def window(self):
        try:
            return E.find_window(self.runner.app(), WINDOW)
        except Exception:  # noqa: BLE001 - Pro Tools closed
            return None

    def selected_index(self, win):
        try:
            el = E.find_one(win, "slider", "Selected Track")
            return int(round(float(el.attr("AXValue"))))
        except Exception:  # noqa: BLE001
            return None

    def ab(self, win):
        """'A' or 'B' from the plug-in's A/B switch, or None."""
        try:
            return ab_from(E.find_one(win, "slider", "AB Switch"))
        except Exception:  # noqa: BLE001
            return None

    def grid_image(self, win):
        """The slot grid, cut out of a picture of the plug-in window (None if it can't be taken)."""
        pos, size = win.attr("AXPosition"), win.attr("AXSize")
        group = E.find_one(win, "group", "FXTDMEditView")
        gpos, gsize = group.attr("AXPosition"), group.attr("AXSize")
        if not (pos and size and gpos and gsize):
            return None
        img = self.runner.sys.window_image(pos[0], pos[1], size[0], size[1])
        if img is None:
            return None
        k = img.width / float(size[0])
        gx, gy = (gpos[0] - pos[0]) * k, (gpos[1] - pos[1]) * k
        gw, gh = gsize[0] * k, gsize[1] * k
        box = (int(gx + GRID["left"] * gw), int(gy + GRID["top"] * gh),
               int(gx + GRID["right"] * gw), int(gy + GRID["bottom"] * gh))
        return img.crop(box).convert("RGB")

    @staticmethod
    def cells(grid):
        """16 (col, row, picture) — just the text part of each cell (not the ≡ menu on the right)."""
        w, h = grid.width / 4, grid.height / 4
        for row in range(4):
            for col in range(4):
                x, y = col * w, row * h
                yield col, row, grid.crop((int(x + w * 0.03), int(y + h * 0.1),
                                           int(x + w * 0.88), int(y + h * 0.9)))

    @staticmethod
    def highlighted(grid):
        """The (col, row) drawn orange (MetricAB's selected slot), or None."""
        best, score = None, 0
        for col, row, cell in MetricReader.cells(grid):
            small = cell.resize((16, 4))
            px = [small.getpixel((x, y)) for y in range(4) for x in range(16)]
            r = sum(p[0] for p in px) / len(px)
            b = sum(p[2] for p in px) / len(px)
            if r - b > score:
                best, score = (col, row), r - b
        return best if score > 60 else None

    def learn_order(self, grid, index):
        """Compare the orange cell with the 'Selected Track' number to see how slots are counted."""
        cell = self.highlighted(grid)
        if cell is None or index is None or cell[0] == cell[1]:
            return
        col, row = cell
        how = "rows" if index_of(col, row, "rows") == index else (
            "columns" if index_of(col, row, "columns") == index else None)
        if how and how != order(self.base):
            settings.put(self.base, "metric order", how)
            self.log(f"MetricAB counts its slots by {how}")

    def read_names(self, grid):
        names = {}
        for col, row, cell in self.cells(grid):
            text = " ".join(t for t, *_ in self.runner.sys.read_text(cell))
            names[slot_name(col, row)] = clean(text)
        return names

    def poll(self, want_names=True):
        """{'open': bool, 'selected': 'B2' or None, 'names': {...}} — names fall back to the
        remembered ones when the window is closed or can't be read."""
        names = settings.get(self.base, "metric names", {}) or {}
        sel = settings.get(self.base, "metric selected")
        ab = settings.get(self.base, "metric ab")
        win = self.window()
        if win is None:
            return {"open": False, "selected": sel, "names": names, "ab": ab}
        if want_names:
            index = self.selected_index(win)
            try:
                grid = self.grid_image(win)
            except Exception as e:  # noqa: BLE001
                grid = None
                self.log(f"✗ MetricAB picture: {e}")
            if grid is None:
                if not self._warned:
                    self._warned = True
                    self.log("Can't take a picture of MetricAB for the song names. In System Settings > "
                             "Privacy & Security > Screen Recording, turn on Terminal, then restart PT Deck.")
            else:
                if not self.paused() and self.selected_index(win) == index:
                    self.learn_order(grid, index)
                h = hashlib.md5(grid.resize((200, 40)).tobytes()).hexdigest()
                if h != self._last_hash:
                    self._last_hash = h
                    try:
                        found = self.read_names(grid)
                    except Exception as e:  # noqa: BLE001
                        found = {}
                        if not self._warned:
                            self._warned = True
                            self.log(f"✗ reading MetricAB song names: {e}")
                    if any(found.values()) and found != names:
                        names = found
                        settings.put(self.base, "metric names", names)
        # The selected slot and A/B are read last, and not saved if a button press started
        # meanwhile (it records its own result, which an older reading mustn't overwrite).
        if self.paused():
            return {"open": True, "selected": sel, "names": names, "ab": ab}
        now = self.ab(win)
        index = self.selected_index(win)
        for which in ("sides", "match"):
            try:
                on = is_on(which, E.find_one(win, "slider", BUTTONS[which][1]))
            except Exception:  # noqa: BLE001
                continue
            if on != settings.get(self.base, f"metric {which}"):
                settings.put(self.base, f"metric {which}", on)
        if self.paused():
            return {"open": True, "selected": sel, "names": names, "ab": ab}
        if now and now != ab:
            ab = now
            settings.put(self.base, "metric ab", ab)
        if index is not None:
            sel = slot_name(*cell_of(index, order(self.base)))
            if sel != settings.get(self.base, "metric selected"):
                settings.put(self.base, "metric selected", sel)
        return {"open": True, "selected": sel, "names": names, "ab": ab}
