"""PT Deck's own key style ('icon style: designed' in deck.yaml).

One look for every key that doesn't have its own picture:
  - commands: a small line picture (a 'glyph') over a short label, in your key colour
  - folders: tall narrow capitals with a folder tab and outline, so they never look like commands
  - AudioSuite: a strip along the bottom naming the plug-in family, themed after it (RX, Pro-Q...)
Text is always black or white, whichever reads best on the key colour, in two sizes only.

Glyphs are drawn here as simple lines with one stroke weight, so they all match. Pick one with
'glyph: <name>' on a button (see GLYPHS), or let PT Deck guess from the label; 'glyph: none' for text only.
"""
from __future__ import annotations

import colorsys
import math
import re
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .paths import ASSETS

FONTS = ASSETS / "fonts"
SS = 4                        # draw 4x bigger, then shrink: smooth edges
COMMAND_BG = "#2a2f36"
FOLDER_BG = "#20242a"

_fonts: dict = {}


def font(kind: str, px: int):
    """kind: 'command' (Barlow Bold), 'narrow' (Barlow Condensed Bold), 'folder' (Condensed ExtraBold)."""
    files = {"command": "Barlow-Bold.ttf", "narrow": "BarlowCondensed-Bold.ttf",
             "folder": "BarlowCondensed-ExtraBold.ttf", "small": "Barlow-SemiBold.ttf"}
    key = (kind, px)
    if key not in _fonts:
        try:
            _fonts[key] = ImageFont.truetype(str(FONTS / files[kind]), px)
        except OSError:
            from .deck import font as fallback
            _fonts[key] = fallback(px)
    return _fonts[key]


# ---------- colour ----------

def rgb(c) -> tuple[int, int, int]:
    c = str(c or "#000000").lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    try:
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def luminance(c) -> float:
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(c)
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def ink(bg) -> str:
    """Black or white text, whichever contrasts more with the background."""
    lum = luminance(bg)
    return "#111111" if (lum + 0.05) / 0.05 > 1.05 / (lum + 0.05) else "#ffffff"


def shade(c, f: float):
    """Lighter (f > 0) or darker (f < 0) version of a colour."""
    r, g, b = (v / 255 for v in rgb(c))
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    l = max(0, min(1, l + f))
    return tuple(int(v * 255) for v in colorsys.hls_to_rgb(h, l, s))


def gradient(size, top, bottom):
    img = Image.new("RGB", (size, size), top)
    d = ImageDraw.Draw(img)
    t, b = rgb(top) if isinstance(top, str) else top, rgb(bottom) if isinstance(bottom, str) else bottom
    for y in range(size):
        k = y / max(1, size - 1)
        d.line([(0, y), (size, y)], fill=tuple(int(t[i] + (b[i] - t[i]) * k) for i in range(3)))
    return img


# ---------- glyphs: drawn in a 0-1 box, as lines ----------

def _g(d, box, col, w):
    x0, y0, x1, y1 = box
    sx, sy = x1 - x0, y1 - y0

    def P(x, y):
        return (x0 + x * sx, y0 + y * sy)

    def line(*pts, width=None):
        d.line([P(*p) for p in pts], fill=col, width=width or w, joint="curve")
        for p in (pts[0], pts[-1]):          # round ends
            c = P(*p)
            r = (width or w) / 2
            d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=col)

    def rect(a, b, c, e, fill=None, radius=0.08):
        d.rounded_rectangle([P(a, b), P(c, e)], radius=radius * sx, outline=col, width=w, fill=fill)

    def circle(cx, cy, r, fill=None):
        d.ellipse([P(cx - r, cy - r), P(cx + r, cy + r)], outline=col, width=w, fill=fill)

    def arc(cx, cy, r, a0, a1):
        d.arc([P(cx - r, cy - r), P(cx + r, cy + r)], a0, a1, fill=col, width=w)

    def curve(fn, a=0.05, b=0.95, n=40):
        line(*[(a + (b - a) * i / n, fn(a + (b - a) * i / n)) for i in range(n + 1)])

    def arrow(x0_, y0_, x1_, y1_, head=0.16):
        line((x0_, y0_), (x1_, y1_))
        ang = math.atan2(y1_ - y0_, x1_ - x0_)
        for s in (2.5, -2.5):
            line((x1_, y1_), (x1_ - head * math.cos(ang + s / 4.5), y1_ - head * math.sin(ang + s / 4.5)))
    return P, line, rect, circle, arc, curve, arrow


def _wave(x):
    return 0.5 + 0.32 * math.sin(x * 19) * math.sin(x * 3.1 + 0.4) * (1 - abs(x - 0.5))


GLYPHS = {}


def glyph(name):
    def reg(fn):
        GLYPHS[name] = fn
        return fn
    return reg


@glyph("waveform")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    for i in range(11):
        x = 0.06 + i * 0.088
        h = [0.18, 0.32, 0.22, 0.42, 0.3, 0.46, 0.26, 0.38, 0.2, 0.3, 0.14][i]
        line((x, 0.5 - h), (x, 0.5 + h))


@glyph("eq")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    curve(lambda x: 0.55 - 0.28 * math.exp(-((x - 0.3) / 0.11) ** 2) + 0.22 * math.exp(-((x - 0.72) / 0.09) ** 2))
    line((0.05, 0.9), (0.95, 0.9), width=max(1, w // 2))


@glyph("spectrum")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    for i, h in enumerate([0.35, 0.55, 0.75, 0.6, 0.8, 0.5, 0.65, 0.4, 0.3]):
        x = 0.08 + i * 0.105
        line((x, 0.92), (x, 0.92 - h))


@glyph("fade")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    line((0.05, 0.85), (0.95, 0.85), width=max(1, w // 2))
    curve(lambda x: 0.85 - 0.7 * math.sin(x * math.pi / 2), 0.05, 0.95)


@glyph("crossfade")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    curve(lambda x: 0.85 - 0.7 * math.sin(x * math.pi / 2), 0.05, 0.95)
    curve(lambda x: 0.85 - 0.7 * math.cos(x * math.pi / 2), 0.05, 0.95)
    line((0.05, 0.88), (0.95, 0.88), width=max(1, w // 2))


@glyph("grid")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    for i in range(5):
        x = 0.1 + i * 0.2
        line((x, 0.15), (x, 0.85), width=max(1, w if i % 2 == 0 else w // 2))
    line((0.05, 0.85), (0.95, 0.85))


@glyph("scissors")
def _(d, box, col, w):
    P, line, rect, circle, *_ = _g(d, box, col, w)
    circle(0.25, 0.75, 0.13)
    circle(0.75, 0.75, 0.13)
    line((0.33, 0.65), (0.75, 0.08))
    line((0.67, 0.65), (0.25, 0.08))


@glyph("trash")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    line((0.12, 0.22), (0.88, 0.22))
    line((0.38, 0.22), (0.42, 0.08), (0.58, 0.08), (0.62, 0.22))
    rect(0.22, 0.22, 0.78, 0.94, radius=0.05)
    for x in (0.4, 0.6):
        line((x, 0.38), (x, 0.8))


@glyph("save")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    rect(0.12, 0.08, 0.88, 0.92, radius=0.06)
    rect(0.3, 0.08, 0.7, 0.34, radius=0.02)
    rect(0.26, 0.56, 0.74, 0.92, radius=0.02)


@glyph("bounce")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    arrow(0.5, 0.06, 0.5, 0.62, head=0.2)
    line((0.12, 0.6), (0.12, 0.9), (0.88, 0.9), (0.88, 0.6))


@glyph("import")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    line((0.35, 0.25), (0.12, 0.25), (0.12, 0.92), (0.88, 0.92), (0.88, 0.25), (0.65, 0.25))
    arrow(0.5, 0.04, 0.5, 0.66, head=0.18)


@glyph("folder")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    line((0.08, 0.85), (0.08, 0.15), (0.38, 0.15), (0.46, 0.27), (0.92, 0.27), (0.92, 0.85), (0.08, 0.85))


@glyph("route")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    line((0.06, 0.5), (0.4, 0.5))
    arrow(0.4, 0.5, 0.92, 0.16)
    arrow(0.4, 0.5, 0.92, 0.84)
    circle(0.4, 0.5, 0.06, fill=col)


@glyph("send")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    circle(0.2, 0.5, 0.12)
    arrow(0.36, 0.5, 0.74, 0.5, head=0.16)
    line((0.88, 0.12), (0.88, 0.88), width=w * 2)


@glyph("mic")
def _(d, box, col, w):
    P, line, rect, circle, arc, *_ = _g(d, box, col, w)
    rect(0.36, 0.04, 0.64, 0.6, radius=0.14)
    arc(0.5, 0.45, 0.28, 0, 180)
    line((0.5, 0.73), (0.5, 0.92))
    line((0.32, 0.93), (0.68, 0.93))


@glyph("headphones")
def _(d, box, col, w):
    P, line, rect, circle, arc, *_ = _g(d, box, col, w)
    arc(0.5, 0.55, 0.38, 180, 360)
    rect(0.08, 0.55, 0.28, 0.92, radius=0.06)
    rect(0.72, 0.55, 0.92, 0.92, radius=0.06)


@glyph("power")
def _(d, box, col, w):
    P, line, rect, circle, arc, *_ = _g(d, box, col, w)
    arc(0.5, 0.55, 0.38, -50, 230)
    line((0.5, 0.06), (0.5, 0.5))


@glyph("eye")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    curve(lambda x: 0.5 - 0.3 * math.sin(math.pi * x), 0.04, 0.96)
    curve(lambda x: 0.5 + 0.3 * math.sin(math.pi * x), 0.04, 0.96)
    circle(0.5, 0.5, 0.12, fill=col)


@glyph("playlist")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    for i, y in enumerate((0.18, 0.42, 0.66, 0.9)):
        line((0.08, y), (0.92 - 0.18 * (i % 2), y))


@glyph("comp")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    for i, y in enumerate((0.12, 0.42, 0.72)):
        rect(0.06, y, 0.94, y + 0.18, radius=0.04)
    for a, b, y in ((0.1, 0.4, 0.21), (0.4, 0.7, 0.51), (0.7, 0.9, 0.81)):
        line((a, y), (b, y), width=w * 2)


@glyph("gear")
def _(d, box, col, w):
    P, line, rect, circle, *_ = _g(d, box, col, w)
    circle(0.5, 0.5, 0.3)
    circle(0.5, 0.5, 0.1)
    for i in range(8):
        a = i * math.pi / 4
        line((0.5 + 0.3 * math.cos(a), 0.5 + 0.3 * math.sin(a)), (0.5 + 0.43 * math.cos(a), 0.5 + 0.43 * math.sin(a)), width=int(w * 2.2))


@glyph("swatch")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    rect(0.08, 0.1, 0.46, 0.48, fill=col)
    rect(0.54, 0.1, 0.92, 0.48)
    rect(0.08, 0.54, 0.46, 0.92)
    rect(0.54, 0.54, 0.92, 0.92, fill=col)


@glyph("plug")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    rect(0.22, 0.28, 0.78, 0.62, radius=0.1)
    line((0.38, 0.06), (0.38, 0.28))
    line((0.62, 0.06), (0.62, 0.28))
    line((0.5, 0.62), (0.5, 0.94))


@glyph("stretch")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    rect(0.3, 0.25, 0.7, 0.75, radius=0.04)
    arrow(0.24, 0.5, 0.02, 0.5, head=0.12)
    arrow(0.76, 0.5, 0.98, 0.5, head=0.12)


@glyph("text")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    line((0.06, 0.12), (0.56, 0.12))
    line((0.31, 0.12), (0.31, 0.9))
    line((0.78, 0.18), (0.78, 0.86))
    line((0.68, 0.1), (0.72, 0.1), (0.78, 0.18), (0.84, 0.1), (0.88, 0.1))
    line((0.68, 0.94), (0.72, 0.94), (0.78, 0.86), (0.84, 0.94), (0.88, 0.94))


@glyph("commit")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    rect(0.08, 0.08, 0.92, 0.92, radius=0.1)
    line((0.26, 0.52), (0.43, 0.7), (0.76, 0.3))


@glyph("copy")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    line((0.62, 0.3), (0.62, 0.08), (0.08, 0.08), (0.08, 0.62), (0.3, 0.62))
    rect(0.38, 0.38, 0.92, 0.92, radius=0.06)


@glyph("paste")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    rect(0.16, 0.14, 0.84, 0.94, radius=0.06)
    rect(0.34, 0.04, 0.66, 0.22, radius=0.04)
    for y in (0.46, 0.64, 0.8):
        line((0.32, y), (0.68, y))


@glyph("flag")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    line((0.2, 0.94), (0.2, 0.06))
    line((0.2, 0.08), (0.84, 0.08), (0.68, 0.28), (0.84, 0.48), (0.2, 0.48))


@glyph("bolt")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    line((0.6, 0.04), (0.26, 0.54), (0.52, 0.54), (0.4, 0.96), (0.76, 0.42), (0.5, 0.42), (0.6, 0.04))


@glyph("buffer")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    for i in range(4):
        rect(0.06 + i * 0.235, 0.3, 0.24 + i * 0.235, 0.7, fill=col if i < 2 else None, radius=0.03)


@glyph("mono")
def _(d, box, col, w):
    P, line, rect, circle, *_ = _g(d, box, col, w)
    circle(0.5, 0.5, 0.36)


@glyph("stereo")
def _(d, box, col, w):
    P, line, rect, circle, *_ = _g(d, box, col, w)
    circle(0.34, 0.5, 0.3)
    circle(0.66, 0.5, 0.3)


@glyph("target")
def _(d, box, col, w):
    P, line, rect, circle, *_ = _g(d, box, col, w)
    circle(0.5, 0.5, 0.42)
    circle(0.5, 0.5, 0.22)
    circle(0.5, 0.5, 0.05, fill=col)


@glyph("plus")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    line((0.5, 0.1), (0.5, 0.9))
    line((0.1, 0.5), (0.9, 0.5))


@glyph("transient")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    curve(lambda x: 0.85 - 0.75 * math.exp(-((x - 0.28) / 0.03) ** 2 if x < 0.28 else -(x - 0.28) * 7), 0.04, 0.96, 60)
    line((0.28, 0.06), (0.28, 0.94), width=max(1, w // 2))


@glyph("speaker")
def _(d, box, col, w):
    P, line, rect, circle, arc, *_ = _g(d, box, col, w)
    line((0.08, 0.36), (0.26, 0.36), (0.5, 0.12), (0.5, 0.88), (0.26, 0.64), (0.08, 0.64), (0.08, 0.36))
    arc(0.5, 0.5, 0.2, -50, 50)
    arc(0.5, 0.5, 0.38, -50, 50)


@glyph("window")
def _(d, box, col, w):
    P, line, rect, *_ = _g(d, box, col, w)
    rect(0.06, 0.12, 0.94, 0.88, radius=0.06)
    line((0.06, 0.3), (0.94, 0.3))


@glyph("play")
def _(d, box, col, w):
    P, line, *_ = _g(d, box, col, w)
    line((0.24, 0.1), (0.84, 0.5), (0.24, 0.9), (0.24, 0.1))


@glyph("ab")
def _(d, box, col, w):
    P, line, rect, circle, *_ = _g(d, box, col, w)
    circle(0.5, 0.5, 0.44)
    line((0.5, 0.14), (0.5, 0.86), width=max(1, w // 2))


@glyph("breath")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    for k, y in enumerate((0.3, 0.5, 0.7)):
        curve(lambda x, y=y, k=k: y + 0.08 * math.sin(x * 9 + k), 0.06, 0.8 - k * 0.12)


@glyph("mono-stereo")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    circle(0.12, 0.5, 0.2)
    arrow(0.36, 0.5, 0.5, 0.5, head=0.08)
    circle(0.69, 0.5, 0.2)
    circle(0.86, 0.5, 0.2)


@glyph("stereo-mono")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    circle(0.14, 0.5, 0.2)
    circle(0.31, 0.5, 0.2)
    arrow(0.54, 0.5, 0.67, 0.5, head=0.08)
    circle(0.88, 0.5, 0.2)


@glyph("arrow-up")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    arrow(0.5, 0.92, 0.5, 0.1, head=0.3)


@glyph("arrow-down")
def _(d, box, col, w):
    P, line, rect, circle, arc, curve, arrow = _g(d, box, col, w)
    arrow(0.5, 0.08, 0.5, 0.9, head=0.3)


# Label words -> glyph, checked in order (first match wins).
GUESS = [
    (r"stereo.{0,12}to mono|stereo.?>.?mono", "stereo-mono"), (r"mono.{0,12}to stereo|mono.?>.?stereo", "mono-stereo"), (r"\bbypass", "power"), (r"\bclear|\bdelete|\bremove", "trash"),
    (r"de-?click|de-?plosive|declick|mouth", "transient"), (r"breath", "breath"),
    (r"\bbounce", "bounce"), (r"\bsave", "save"), (r"\bimport", "import"),
    (r"\bgrid", "grid"), (r"\bplaylist|\.comp", "playlist"), (r"\bcomp\b", "comp"),
    (r"\bfade", "fade"), (r"\bcrossfade", "crossfade"), (r"\broute|\boutput", "route"),
    (r"\bsend", "send"), (r"\binput|tracking|record", "mic"), (r"\bmono", "mono"), (r"\bstereo", "stereo"),
    (r"\bbuffer", "buffer"), (r"latency", "bolt"), (r"\bcolou?r", "swatch"), (r"\bplug-?in|insert", "plug"),
    (r"\btce|stretch", "stretch"), (r"\brename|\bname\b", "text"), (r"\bcommit", "commit"),
    (r"\bcopy", "copy"), (r"\bpaste", "paste"), (r"marker", "flag"), (r"\bview|\bshow", "eye"),
    (r"\btarget", "target"), (r"\bfolder|finder", "folder"), (r"\beq\b", "eq"),
    (r"playback|\bplay\b", "play"), (r"\bopen\b", "window"), (r"\bsplit|\bcut\b|\bcapture", "scissors"),
    (r"\bi/?o\b|setup", "gear"),
]


def guess_glyph(label: str):
    t = str(label).lower()
    for pat, g in GUESS:
        if re.search(pat, t):
            return g
    return None


# ---------- AudioSuite families ----------

THEMES = {
    # name: (background top, bottom, accent, strip label)
    "rx": ("#14162a", "#0b0c16", "#3fd1ff", "RX"),
    "fabfilter": ("#1a1d22", "#0e1013", "#f2c14e", "PRO-Q"),
    "avid": ("#1f2621", "#121714", "#62d26f", "AVID"),
    "waves": ("#1c2230", "#10141c", "#e8e8e8", "WAVES"),
    "audiosuite": ("#22262e", "#14171c", "#b88cff", "AUDIOSUITE"),
}
THEME_GUESS = [(r"\brx\b|izotope|de-?click|de-?plosive|breath|de-?hum|de-?noise|mouth|voice de", "rx"),
               (r"pro-?q|fabfilter", "fabfilter"), (r"\beq3|\bdyn3|\bavid|\bd-verb|time shift|reverse|gain\b", "avid"),
               (r"waves|\bcla\b|\bssl\b", "waves")]


def theme_for(text: str) -> str:
    t = str(text).lower()
    for pat, name in THEME_GUESS:
        if re.search(pat, t):
            return name
    return "audiosuite"


_as_cache: dict = {}


def audiosuite_of(base, macro) -> str | None:
    """The AudioSuite plug-in a button's macro uses (None if it doesn't use one). Cached for 10s."""
    if not macro:
        return None
    key = (str(base), str(macro))
    hit = _as_cache.get(key)
    if hit and time.time() - hit[0] < 10:
        return hit[1]
    found = None
    try:
        found = _find_audiosuite(Path(base), str(macro), 0)
    except Exception:  # noqa: BLE001 - unknown macro: no AudioSuite strip
        found = None
    _as_cache[key] = (time.time(), found)
    return found


AS_NAME = re.compile(r"(?i)\b(RX\s*\d*\s+[\w .'-]+|EQ3[\w -]*|Pro-Q\s*\d?)")


def _find_audiosuite(base, macro, depth):
    """Look through a macro (and macros it runs) for the AudioSuite plug-in it uses: an
    'audiosuite' step, a menu path through AudioSuite, or a plug-in name anywhere in a step."""
    from .macros import Library, step_action
    if depth > 3:
        return None
    steps = Library(base / "macros").get(macro).get("steps") or []
    hint = None
    stack = list(steps)
    while stack:
        st = stack.pop(0)
        action, value = step_action(st)
        if isinstance(st, dict):
            for k in ("then", "else"):
                if isinstance(st.get(k), list):
                    stack.extend(st[k])
        if action == "audiosuite" and value:
            return str(value)
        if action == "run macro" and value:
            inner = _find_audiosuite(base, str(value), depth + 1)
            if inner:
                return inner
        text = " ".join(str(v) for v in (st.values() if isinstance(st, dict) else [st]) if v)
        if "audiosuite" in text.lower() and ">" in text:          # menu: AudioSuite > Noise Reduction > RX ...
            hint = hint or text.split(">")[-1].strip()
        m = AS_NAME.search(text)
        if m and action not in ("note", "todo"):
            hint = hint or m.group(1).strip()
    return hint


# ---------- the key ----------

SEND_LABEL = re.compile(r"^\s*//\s*\[?\s*(.+?)\s*\]?\s*$")


def kind_of(button: dict, base) -> tuple[str, str | None]:
    """('folder' | 'audiosuite' | 'send' | 'command', detail or None)."""
    if button.get("folder"):
        return "folder", None
    style = str(button.get("style", "")).lower()
    if style == "command":
        return "command", None
    label = str(button.get("label", ""))
    m = SEND_LABEL.match(label.replace("\n", " "))
    if style == "send" or (m and label.strip().startswith("//")):
        return "send", (m.group(1) if m else label)
    plug = button.get("audiosuite") or audiosuite_of(base, button.get("macro"))
    if plug or style == "audiosuite":
        return "audiosuite", str(plug or label)
    return "command", None


def strip_name(plug: str, theme: str) -> str:
    """What the AudioSuite strip says: 'RX' for RX, otherwise the plug-in's own name."""
    if theme == "rx":
        return "RX"
    name = re.sub(r"(?i)\b(audiosuite|plug-?in|avid)\b", "", str(plug)).strip(" -")
    return (name or THEMES[theme][3]).upper()


# Text sizes (as a fraction of the key), biggest first. A label uses the biggest size that
# fits; at that size, fewer lines win (tall-narrow letters if they keep it on fewer lines).
SIZES = (0.20, 0.17, 0.15)
FOLDER_SIZES = (0.27, 0.21, 0.17)
_last_frac = [None]


def _fit(d, text, kind, width, height, max_lines, S, max_frac=1.0, min_frac=0.0):
    """Returns (font, lines, line height) or None if the whole label can't fit (never cut short)."""
    from .deck import _wrap
    sizes, fonts = (FOLDER_SIZES, ("folder",)) if kind == "folder" else (SIZES, ("command", "narrow"))
    sizes = [x for x in sizes if min_frac - 1e-6 <= x <= max_frac + 1e-6]
    # Short names (one or two words, like 'SLAP DELAY') stay on one line if any size allows;
    # longer labels keep the biggest size and wrap.
    short = "\n" not in text and len(text.split()) <= 2
    order = ([(n, x) for n in range(1, max_lines + 1) for x in sizes] if short
             else [(n, x) for x in sizes for n in range(1, max_lines + 1)])
    for n, frac in order:
        px = int(S * frac)
        for k in fonts:
            f = font(k, px)
            lines = _wrap(d, text, f, width)
            if (len(lines) == n and n * px <= height
                    and all(d.textlength(l, font=f) <= width for l in lines)):
                _last_frac[0] = frac
                return f, lines, px
    return None


def contrast(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_colour(button, bg):
    """Your text colour if it's readable on the key, otherwise black or white."""
    want = button.get("text color")
    return want if want and contrast(want, bg) >= 4.5 else ink(bg)


def _text(d, f, lines, lh, cx, top, height, col):
    y = top + (height - len(lines) * lh) / 2
    for line in lines:
        bb = d.textbbox((0, 0), line, font=f)
        d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], y + (lh - (bb[3] - bb[1])) / 2 - bb[1] * 0.55), line, fill=col, font=f)
        y += lh


def _strip(d, S, text, bg, fg=None):
    h = int(S * 0.2)
    d.rectangle([0, S - h, S, S], fill=bg)
    px = int(h * 0.72)
    f = font("narrow", px)
    while d.textlength(text, font=f) > S * 0.92 and px > 10:
        px -= 2
        f = font("narrow", px)
    _text(d, f, [text], h, S / 2, S - h, h, fg or ink(bg))
    return h


def render_designed(button: dict, size: int, base) -> Image.Image:
    S = size * SS
    kind, detail = kind_of(button, base)
    label = str(button.get("label", "")).replace("\\n", "\n").strip()
    pad = int(S * 0.08)
    cap = float(button.get("_maxfrac", 1.0))
    _last_frac[0] = None
    if kind == "folder":
        bg = button.get("color") or FOLDER_BG
        img = gradient(S, shade(bg, 0.05), shade(bg, -0.06))
        d = ImageDraw.Draw(img)
        fg = text_colour(button, bg)
        accent = button.get("outline") or (fg if bg != FOLDER_BG else "#d8d8d8")
        w = max(2, S // 40)
        tab_w, tab_h, top = S * 0.42, S * 0.09, S * 0.16          # folder outline with a tab
        pts = [(w, top), (w, w + tab_h * 0.2), (tab_w - tab_h, w + tab_h * 0.2), (tab_w, top - tab_h * 0.1),
               (S - w, top), (S - w, S - w), (w, S - w), (w, top)]
        d.line(pts, fill=accent, width=w, joint="curve")
        text = (label or str(button["folder"])).upper()
        fit = (_fit(d, text, "folder", S - 2 * pad, S - top - pad * 1.5, 4, S)
               or _fit(d, text, "command", S - 2 * pad, S - top - pad, 5, S))
        if fit:
            _text(d, *fit, S / 2, top + pad * 0.4, S - top - pad * 1.2, fg)
        return img.resize((size, size), Image.LANCZOS)

    if kind == "send":
        bg = button.get("color") or COMMAND_BG
        img = gradient(S, shade(bg, 0.04), shade(bg, -0.05))
        d = ImageDraw.Draw(img)
        h = _strip(d, S, "SEND", shade(bg, -0.2) if luminance(bg) > 0.06 else shade(bg, 0.15))
        _body(d, S, pad, detail.upper(), None, text_colour(button, bg), None, S - h, cap, max_lines=2)
        return img.resize((size, size), Image.LANCZOS)

    if kind == "audiosuite":
        theme = theme_for(detail)                       # the plug-in's own name decides...
        if theme == "audiosuite":
            theme = theme_for(label)                    # ...the label only if that says nothing
        th = THEMES[theme]
        img = gradient(S, th[0], th[1])
        d = ImageDraw.Draw(img)
        accent = th[2]
        if theme == "rx":          # RX-style spectrogram glow behind the glyph
            glow = Image.new("RGB", (S, S), (0, 0, 0))
            gd = ImageDraw.Draw(glow)
            for i in range(26):
                x = S * (0.06 + i * 0.034)
                h = S * (0.12 + 0.2 * abs(math.sin(i * 1.7)) * (1 - abs(i - 13) / 16))
                gd.line([(x, S * 0.36 - h), (x, S * 0.36 + h)], fill=(20, 90 + i * 4, 160), width=S // 50)
            img = Image.blend(img, glow, 0.35)
            d = ImageDraw.Draw(img)
        h = _strip(d, S, strip_name(detail, theme), accent)
        g = button.get("glyph") or guess_glyph(label) or ("eq" if "eq" in detail.lower() else "waveform")
        _body(d, S, pad, label, g if g in GLYPHS else None, "#ffffff", accent, S - h, cap)
        return img.resize((size, size), Image.LANCZOS)

    # command
    bg = button.get("color") or COMMAND_BG
    img = gradient(S, shade(bg, 0.04), shade(bg, -0.05))
    d = ImageDraw.Draw(img)
    fg = text_colour(button, bg)
    chosen = button.get("glyph")
    g = None if chosen == "none" else (chosen or guess_glyph(label))
    bottom = S
    if button.get("strip"):          # e.g. 'BEAT DETECTIVE' along the bottom: which tool this is
        sbg = button.get("strip color") or "#0e0e10"
        bottom -= _strip(d, S, str(button["strip"]).upper(), sbg, button.get("strip text color") or
                         ("#ece8de" if sbg == "#0e0e10" else None))
    if not label and g in GLYPHS:
        gs = S * 0.56
        GLYPHS[g](d, ((S - gs) / 2, (S - gs) / 2, (S + gs) / 2, (S + gs) / 2), fg, max(3, S // 22))
    else:
        _body(d, S, pad, label, g if g in GLYPHS else None, fg, fg, bottom, cap, force=bool(chosen))
    return img.resize((size, size), Image.LANCZOS)


def _body(d, S, pad, label, g, fg, glyph_col, bottom, cap=1.0, max_lines=4, force=False):
    """A glyph over the label when the label still fits under it at a good size (up to 2 lines);
    otherwise just the label, as big as it can be. A glyph you picked yourself (force) always
    shows: it gets smaller and the label may take 3 lines."""
    width = S - 2 * pad
    if g:
        gs = S * 0.3
        top = pad * 1.1 + gs + pad * 0.45
        fit = _fit(d, label, "command", width, bottom - top - pad * 0.6, 2, S, cap, 0.17) if label else None
        if not fit and label:
            gs = S * 0.2
            top = pad * 0.9 + gs + pad * 0.35
            fit = _fit(d, label, "command", width, bottom - top - pad * 0.4, 3, S, cap)
        if fit or not label:
            gy = pad * 1.1 if gs > S * 0.25 else pad * 0.9
            GLYPHS[g](d, (S / 2 - gs / 2, gy, S / 2 + gs / 2, gy + gs), glyph_col, max(3, S // 26))
            if fit:
                _text(d, *fit, S / 2, top, bottom - top - pad * 0.6, fg)
            return
    fit = _fit(d, label, "command", width, bottom - 2 * pad, max_lines, S, cap) or \
        _fit(d, label, "command", width, bottom - 2 * pad, 6, S)
    if fit:
        _text(d, *fit, S / 2, pad, bottom - 2 * pad, fg)
    else:   # far too long for a key: show it at the smallest size
        from .deck import _wrap
        f = font("narrow", int(S * SIZES[-1]))
        _text(d, f, _wrap(d, label, f, width), int(S * SIZES[-1]), S / 2, pad, bottom - 2 * pad, fg)


_size_cache: dict = {}


def text_size_of(button: dict, base) -> float | None:
    """The text size a key would use on its own (for matching sizes across a group of keys)."""
    import json
    b = {k: v for k, v in button.items() if k != "_maxfrac"}
    key = json.dumps(b, sort_keys=True, default=str) + str(audiosuite_of(base, b.get("macro")))
    if key not in _size_cache:
        if len(_size_cache) > 2000:
            _size_cache.clear()
        render_designed(dict(b, _maxfrac=1.0), 48, base)
        _size_cache[key] = _last_frac[0]
    return _size_cache[key]


def match_sizes(slots, base, cols=8):
    """Keys that look alike and sit in the same row (same kind, colour, strip and picture) share
    one text size: the smallest any of them needs. So a row of sends, or the Set Grid keys,
    read the same instead of some big and some small."""
    groups = {}
    for i, b in enumerate(slots):
        if not b or b.get("_look") != "designed" or b.get("icon") or "corner" in b or b.get("live"):
            continue
        kind, _ = kind_of(b, base)
        if kind == "folder":
            continue
        g = b.get("glyph") or guess_glyph(b.get("label", ""))
        groups.setdefault((i // cols, kind, str(b.get("color", "")).lower(), str(b.get("strip", "")),
                           str(g if g != "none" else "")), []).append(i)
    for idx in groups.values():
        if len(idx) < 2:
            continue
        sizes = [text_size_of(slots[i], base) for i in idx]
        sizes = [x for x in sizes if x]
        if sizes:
            for i in idx:
                slots[i] = dict(slots[i], _maxfrac=min(sizes))


def library_sheet(size=96, cols=8) -> Image.Image:
    """Every glyph with its name: the picture library."""
    names = sorted(GLYPHS)
    rows = math.ceil(len(names) / cols)
    gap = 10
    sheet = Image.new("RGB", (cols * (size + gap) + gap, rows * (size + gap + 16) + gap), "#111111")
    d = ImageDraw.Draw(sheet)
    for i, n in enumerate(names):
        r, c = divmod(i, cols)
        x, y = gap + c * (size + gap), gap + r * (size + gap + 16)
        sheet.paste(render_designed({"glyph": n, "label": ""}, size, "."), (x, y))
        f = font("small", 13)
        tw = d.textlength(n, font=f)
        d.text((x + (size - tw) / 2, y + size + 1), n, fill="#bbbbbb", font=f)
    return sheet
