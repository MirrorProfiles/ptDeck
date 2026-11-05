"""Draws PT Deck's own picture icons at high resolution (run: python tools/make_icons.py)."""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ptdeck import look  # noqa: E402

from ptdeck.paths import DATA  # noqa: E402

OUT = DATA / "icons"
S = 576

try:                                   # draw in the deck's own fonts ('fonts:' in deck.yaml), if any
    import yaml
    look.set_fonts((yaml.safe_load((DATA / "deck.yaml").read_text(encoding="utf-8")) or {}).get("fonts"))
except (OSError, ValueError):
    pass


def bez(p0, p1, p2, p3, n=40):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def strip(img, text, bg, fg):
    d = ImageDraw.Draw(img)
    h = int(S * 0.2)
    d.rectangle([0, S - h, S, S], fill=bg)
    f = look.font("folder", int(h * 0.62))
    tw = d.textlength(text, font=f)
    while tw > S * 0.92:
        f = look.font("folder", f.size - 2)
        tw = d.textlength(text, font=f)
    bb = d.textbbox((0, 0), text, font=f)
    d.text(((S - tw) / 2, S - h + (h - (bb[3] - bb[1])) / 2 - bb[1]), text, fill=fg, font=f)


def beat_detective():
    W = S * 2                                    # draw big, shrink for smooth edges
    paper = (226, 222, 212)
    ink = (14, 14, 16)
    img = Image.new("RGB", (W, W), paper)
    # soft vignette
    v = Image.new("L", (W, W), 0)
    ImageDraw.Draw(v).ellipse([-W * 0.25, -W * 0.3, W * 1.25, W * 1.15], fill=255)
    v = v.filter(ImageFilter.GaussianBlur(W * 0.08))
    img = Image.composite(img, Image.new("RGB", (W, W), (150, 146, 138)), v)
    d = ImageDraw.Draw(img)
    k = W / 1000

    def T(x, y):                                  # scale the figure up to fill the key
        return ((x - 500) * 1.22 + 500) * k, ((y - 170) * 1.22 + 40) * k

    def P(pts):
        return [T(x, y) for x, y in pts]
    # coat / shoulders with upturned collar
    coat = P([(120, 820), (180, 640), (300, 580), (380, 600), (450, 660), (560, 660), (640, 600),
              (720, 585), (840, 650), (900, 820)])
    d.polygon(coat + [(900 * k, W), (120 * k, W)], fill=ink)
    d.polygon(P([(300, 585), (360, 470), (430, 640)]), fill=ink)          # left collar point
    d.polygon(P([(720, 590), (650, 470), (590, 650)]), fill=ink)          # right collar point
    # face (lit side) and shadowed jaw
    d.polygon(P([(400, 470), (420, 600), (470, 650), (540, 655), (600, 610), (615, 470)]), fill=(236, 232, 222))
    d.polygon(P([(505, 470), (520, 560), (560, 640), (600, 610), (615, 470)]), fill=ink)
    d.polygon(P([(400, 470), (615, 470), (612, 520), (402, 520)]), fill=ink)  # hat shadow over the eyes
    # fedora: crown with pinch, band, wide brim
    crown = bez((330, 420), (330, 230), (420, 170), (510, 190)) + bez((510, 190), (600, 170), (690, 230), (690, 420))
    d.polygon(P(crown), fill=ink)
    d.polygon(P([(335, 380), (685, 380), (688, 420), (332, 420)]), fill=(70, 66, 62))   # band
    brim = bez((170, 470), (260, 400), (760, 390), (860, 455)) + bez((860, 455), (760, 500), (260, 505), (170, 470))
    d.polygon(P(brim), fill=ink)
    # magnifying glass with a drum hit inside
    cx, cy = T(700, 640)
    r = 150 * k * 1.22
    d.line([(cx - r * 0.75, cy + r * 0.75), (cx - r * 1.55, cy + r * 1.6)], fill=(60, 44, 30), width=int(46 * k))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(245, 243, 236), outline=(40, 40, 44), width=int(26 * k))
    wave = []
    for i in range(80):
        x = -0.8 + 1.6 * i / 79
        env = 0 if x < -0.35 else math.exp(-(x + 0.35) * 3.2)
        wave.append((cx + x * r, cy - env * 0.7 * r * math.sin(i * 1.15)))
    d.line(wave, fill=(200, 40, 40), width=int(9 * k), joint="curve")
    d.line([(cx - 0.35 * r, cy - 0.85 * r), (cx - 0.35 * r, cy + 0.85 * r)], fill=(200, 40, 40), width=int(5 * k))
    img = img.resize((S, S), Image.LANCZOS)
    detective = img.copy()
    strip(img, "BEAT DETECTIVE", (14, 14, 16), (236, 232, 222))
    img.save(OUT / "beat-detective.png")
    return detective


def art_picture(picture, radius=0.06):
    """An art function that fits a picture (a PIL image or a file in icons/) into the box, with rounded corners."""
    def art(d, img, box):
        x0, y0, x1, y1 = box
        pic = (picture if isinstance(picture, Image.Image) else Image.open(OUT / picture)).convert("RGBA")
        side = int(min(x1 - x0, y1 - y0))
        pic = pic.resize((side, side), Image.LANCZOS)
        mask = Image.new("L", pic.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, side - 1, side - 1], radius=int(side * radius), fill=255)
        img.paste(pic, (int((x0 + x1) / 2 - side / 2), int((y0 + y1) / 2 - side / 2)), mask)
    return art


def art_swatches(d, img, box):
    """The track colour palette: a row of swatches."""
    x0, y0, x1, y1 = box
    colours = ["#4e0a00", "#240d46", "#004011", "#610d0b", "#621662", "#624200", "#00495a"]
    bw = (x1 - x0) / len(colours)
    cy = (y0 + y1) / 2
    h = (y1 - y0) * 0.55
    for i, c in enumerate(colours):
        d.rounded_rectangle([x0 + i * bw + 4, cy - h / 2, x0 + (i + 1) * bw - 4, cy + h / 2], radius=S * 0.012,
                            fill=look.shade(c, 0.12))


def base_key(top="#2c3138", bottom="#1b1f24"):
    return look.gradient(S, top, bottom)


def label(img, text, top, height, colour="#ffffff", kind="command", frac=(0.2, 0.17, 0.15)):
    d = ImageDraw.Draw(img)
    pad = S * 0.07
    for fr in frac:
        for k in (kind, "narrow"):
            f = look.font(k, int(S * fr))
            from ptdeck.deck import _wrap
            lines = _wrap(d, text, f, S - 2 * pad)
            if len(lines) * int(S * fr) <= height and all(d.textlength(l, font=f) <= S - 2 * pad for l in lines):
                look._text(d, f, lines, int(S * fr), S / 2, top, height, colour)
                return
    look._text(d, f, lines, int(S * fr), S / 2, top, height, colour)


def pt_selector(img, text, y, colour=None):
    """A Pro Tools-style output/bus selector button: grey pill with the name and a small arrow."""
    d = ImageDraw.Draw(img)
    x0, x1, h = S * 0.06, S * 0.94, S * 0.3
    face = Image.new("RGB", (int(x1 - x0), int(h)), 0)
    face = look.gradient(int(x1 - x0), "#5b6068", "#3b3f45").crop((0, 0, int(x1 - x0), int(h)))
    mask = Image.new("L", face.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, face.size[0] - 1, face.size[1] - 1], radius=h * 0.22, fill=255)
    img.paste(face, (int(x0), int(y)), mask)
    d.rounded_rectangle([x0, y, x1, y + h], radius=h * 0.22, outline="#1a1c1f", width=4)
    if colour:
        d.rectangle([x0 + 10, y + 10, x0 + 26, y + h - 10], fill=colour)
    f = look.font("narrow", int(h * 0.62))
    tw = d.textlength(text, font=f)
    while tw > (x1 - x0) * 0.78:
        f = look.font("narrow", f.size - 2)
        tw = d.textlength(text, font=f)
    look._text(d, f, [text], int(h), S / 2 - h * 0.15, y, h, "#f2f2f2")
    ax, ay = x1 - h * 0.45, y + h * 0.42
    d.polygon([(ax - h * 0.16, ay), (ax + h * 0.16, ay), (ax, ay + h * 0.2)], fill="#e6e6e6")


def route(name, out):
    img = base_key()
    label(img, "Route to", S * 0.1, S * 0.3, "#c9d1da", frac=(0.2,))
    pt_selector(img, name, S * 0.5)
    img.save(OUT / out)


def renumber_markers():
    img = base_key()
    d = ImageDraw.Draw(img)
    ry, rh = S * 0.12, S * 0.24                         # Pro Tools' Markers ruler
    d.rectangle([0, ry, S, ry + rh], fill="#3a3f46")
    d.line([(0, ry + rh), (S, ry + rh)], fill="#15171a", width=4)
    f = look.font("command", int(rh * 0.5))
    for i, x in enumerate((0.16, 0.5, 0.82)):
        cx = S * x
        d.polygon([(cx - rh * 0.28, ry + rh * 0.18), (cx + rh * 0.28, ry + rh * 0.18),
                   (cx + rh * 0.28, ry + rh * 0.62), (cx, ry + rh * 0.9), (cx - rh * 0.28, ry + rh * 0.62)], fill="#f5c518")
        look._text(d, f, [str(i + 1)], int(rh * 0.5), cx, ry + rh * 0.16, rh * 0.5, "#1a1a1a")
    label(img, "Renumber Markers", S * 0.44, S * 0.48)
    img.save(OUT / "renumber-markers.png")


def import_template():
    img = base_key()
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1, fold = S * 0.27, S * 0.05, S * 0.73, S * 0.52, S * 0.11    # a session file
    d.polygon([(x0, y0), (x1 - fold, y0), (x1, y0 + fold), (x1, y1), (x0, y1)], fill="#e9edf2")
    d.polygon([(x1 - fold, y0), (x1 - fold, y0 + fold), (x1, y0 + fold)], fill="#b6bec8")
    f = look.font("folder", int(S * 0.1))
    look._text(d, f, ["EAS"], int(S * 0.1), S / 2, y0 + S * 0.1, S * 0.12, "#bc2488")
    f2 = look.font("narrow", int(S * 0.075))
    look._text(d, f2, [".ptx"], int(S * 0.075), S / 2, y0 + S * 0.24, S * 0.1, "#55606c")
    label(img, "Import Mix Template", S * 0.55, S * 0.4)
    img.save(OUT / "import-mix-template.png")


def keycap(letter, text, out):
    img = base_key()
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = S * 0.3, S * 0.06, S * 0.7, S * 0.46
    d.rounded_rectangle([x0, y0 + 10, x1, y1 + 10], radius=S * 0.05, fill="#0c0d0f")
    d.rounded_rectangle([x0, y0, x1, y1], radius=S * 0.05, fill="#e8ebef")
    f = look.font("command", int(S * 0.3))
    look._text(d, f, [letter], int(S * 0.3), S / 2, y0 + S * 0.04, S * 0.34, "#1b1f24")
    label(img, text, S * 0.52, S * 0.42)
    img.save(OUT / out)


def track_colours_folder():
    colours = ["#4e0a00", "#240d46", "#004011", "#610d0b", "#621662", "#624200", "#00495a"]
    img = look.gradient(S, "#262a30", "#1a1d22")
    d = ImageDraw.Draw(img)
    top = S * 0.16
    bw = (S * 0.84) / len(colours)
    for i, c in enumerate(colours):                       # the track colour palette
        bright = look.shade(c, 0.12)
        d.rectangle([S * 0.08 + i * bw, top + S * 0.06, S * 0.08 + (i + 1) * bw - 6, top + S * 0.3], fill=bright)
    w = max(2, S // 40)
    tab_w, tab_h = S * 0.42, S * 0.09
    pts = [(w, top), (w, w + tab_h * 0.2), (tab_w - tab_h, w + tab_h * 0.2), (tab_w, top - tab_h * 0.1),
           (S - w, top), (S - w, S - w), (w, S - w), (w, top)]
    d.line(pts, fill="#d8d8d8", width=w, joint="curve")
    label(img, "TRACK COLOURS", top + S * 0.34, S * 0.44, "#ffffff", kind="folder", frac=(0.2, 0.17))
    img.save(OUT / "eas-track-colours.png")


def folder_frame(accent, title, art):
    """A folder key: a filled tab and frame in the folder's colour on a dark key, a picture of
    what's inside, the name in tall capitals in the same colour (white if the colour is too dark)."""
    img = look.gradient(S, "#23262b", "#17191c")
    d = ImageDraw.Draw(img)
    w = max(2, S // 40)
    tab_w, tab_h, top = S * 0.42, S * 0.09, S * 0.16
    d.rounded_rectangle([w, w, tab_w, top + tab_h], radius=S * 0.03, fill=accent)
    d.rounded_rectangle([w, top, S - w, S - w], radius=S * 0.04, fill="#1d2024", outline=accent, width=w)
    art(d, img, (S * 0.12, top + tab_h + S * 0.03, S * 0.88, S * 0.63))
    d = ImageDraw.Draw(img)
    name_col = accent if look.luminance(accent) > 0.12 else "#ffffff"
    label(img, title, S * 0.65, S * 0.28, name_col, kind="folder", frac=(0.2, 0.17, 0.15))
    return img


def art_checklist(d, img, box):
    x0, y0, x1, y1 = box
    cx = (x0 + x1) / 2
    bw, bh = (y1 - y0) * 0.78, (y1 - y0)
    d.rounded_rectangle([cx - bw / 2, y0 + bh * 0.06, cx + bw / 2, y1], radius=S * 0.025, fill="#f0e6cf")
    d.rounded_rectangle([cx - bw * 0.2, y0, cx + bw * 0.2, y0 + bh * 0.14], radius=S * 0.015, fill="#6b7480")
    for i in range(3):
        y = y0 + bh * (0.3 + i * 0.22)
        bx = cx - bw * 0.36
        d.line([(bx, y), (bx + bw * 0.08, y + bh * 0.07), (bx + bw * 0.2, y - bh * 0.07)], fill="#2a9d55", width=9)
        d.line([(bx + bw * 0.3, y), (cx + bw * 0.38, y)], fill="#8a8f96", width=8)


def art_knobs(d, img, box):
    x0, y0, x1, y1 = box
    cols = ["#c2207f", "#1fbf7f", "#22b8f0"]
    r = (x1 - x0) / 7.2
    for i, c in enumerate(cols):
        cx = x0 + (x1 - x0) * (0.17 + i * 0.33)
        cy = (y0 + y1) / 2
        d.ellipse([cx - r * 1.35, cy - r * 1.35, cx + r * 1.35, cy + r * 1.35], fill=c)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#22252a", outline="#4a4f56", width=4)
        a = math.radians(-60 + i * 50)
        d.line([(cx, cy), (cx + r * 0.85 * math.sin(a), cy - r * 0.85 * math.cos(a))], fill="#ffffff", width=9)


def art_vu(d, img, box):
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0, x1, y1], radius=S * 0.03, fill="#1a1a1a")
    m = S * 0.03
    face = look.gradient(int(x1 - x0 - 2 * m), "#ffd88a", "#e9a64a").crop((0, 0, int(x1 - x0 - 2 * m), int(y1 - y0 - 2 * m)))
    img.paste(face, (int(x0 + m), int(y0 + m)))
    cx, cy, r = (x0 + x1) / 2, y1 - m * 0.8, (y1 - y0) * 0.78
    d.arc([cx - r, cy - r, cx + r, cy + r], 215, 300, fill="#2b2b2b", width=7)
    d.arc([cx - r, cy - r, cx + r, cy + r], 300, 325, fill="#c62828", width=11)
    for k in range(9):
        a = math.radians(215 + k * 13.75)
        d.line([(cx + r * math.cos(a), cy + r * math.sin(a)), (cx + r * 0.88 * math.cos(a), cy + r * 0.88 * math.sin(a))],
               fill="#2b2b2b", width=5)
    a = math.radians(285)
    d.line([(cx, cy), (cx + r * 1.02 * math.cos(a), cy + r * 1.02 * math.sin(a))], fill="#111111", width=6)
    f = look.font("folder", int(S * 0.06))
    look._text(d, f, ["VU"], int(S * 0.06), cx, cy - r * 0.45, S * 0.07, "#2b2b2b")


def art_reels(d, img, box):
    x0, y0, x1, y1 = box
    r = (x1 - x0) * 0.22
    cy = y0 + (y1 - y0) * 0.45
    centres = [x0 + r * 1.05, x1 - r * 1.05]
    d.line([(centres[0], cy + r), (centres[1], cy + r)], fill="#5a3a22", width=8)
    for cx in centres:
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#c9ced6", outline="#7d848e", width=5)
        d.ellipse([cx - r * 0.72, cy - r * 0.72, cx + r * 0.72, cy + r * 0.72], fill="#4a2f1c")
        for k in range(3):
            a = math.radians(90 + k * 120)
            d.ellipse([cx + r * 0.45 * math.cos(a) - r * 0.17, cy + r * 0.45 * math.sin(a) - r * 0.17,
                       cx + r * 0.45 * math.cos(a) + r * 0.17, cy + r * 0.45 * math.sin(a) + r * 0.17], fill="#c9ced6")
        d.ellipse([cx - r * 0.12, cy - r * 0.12, cx + r * 0.12, cy + r * 0.12], fill="#2a2a2a")


def art_amp(d, img, box):
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0 + S * 0.03, x1, y1], radius=S * 0.03, fill="#151515", outline="#3a3a3a", width=4)
    d.rounded_rectangle([x0 + S * 0.25, y0, x1 - S * 0.25, y0 + S * 0.05], radius=S * 0.02, fill="#2a2a2a")   # handle
    gx0, gy0, gx1, gy1 = x0 + S * 0.04, y0 + S * 0.08, x1 - S * 0.04, y0 + (y1 - y0) * 0.55
    d.rectangle([gx0, gy0, gx1, gy1], fill="#b89a5a")
    for k in range(0, int(gx1 - gx0), 14):
        d.line([(gx0 + k, gy0), (gx0 + k, gy1)], fill="#9b7f45", width=3)
    panel_y = (gy1 + y1) / 2
    for k in range(6):
        cx = x0 + (x1 - x0) * (0.14 + k * 0.145)
        r = S * 0.03
        d.ellipse([cx - r, panel_y - r, cx + r, panel_y + r], fill="#e8e2d0")
        d.line([(cx, panel_y), (cx + r * 0.5, panel_y - r * 0.8)], fill="#151515", width=4)


# ----- Home title: EAS STUDIOS, Overlook carpet + Black Lodge floor -----
CARPET = {"bg": (196, 76, 32), "brown": (66, 30, 20), "orange": (226, 120, 44), "red": (150, 30, 24)}


def carpet(w, h, offset_x=0, r=None):
    """A nested-hexagon carpet pattern (the 'Room 237' look), continuous across keys via offset_x."""
    r = r or S * 0.2
    img = Image.new("RGB", (w, h), CARPET["bg"])
    d = ImageDraw.Draw(img)
    dx, dy = r * math.sqrt(3), r * 1.5

    def hexagon(cx, cy, rr, fill):
        d.polygon([(cx + rr * math.cos(math.radians(60 * k + 30)), cy + rr * math.sin(math.radians(60 * k + 30)))
                   for k in range(6)], fill=fill)
    row = 0
    y = -r
    while y < h + r:
        x0 = -((offset_x) % dx) - dx + (dx / 2 if row % 2 else 0)
        x = x0
        while x < w + dx:
            hexagon(x, y, r * 0.98, CARPET["brown"])
            hexagon(x, y, r * 0.78, CARPET["orange"])
            hexagon(x, y, r * 0.58, CARPET["red"])
            hexagon(x, y, r * 0.3, CARPET["brown"])
            x += dx
        y += dy
        row += 1
    return img


def chevrons(img, top, height):
    """The Black Lodge floor: black and white zigzag stripes along a band."""
    d = ImageDraw.Draw(img)
    d.rectangle([0, top, S, top + height], fill=(240, 236, 226))
    period, amp = height * 0.9, height * 0.22
    stripe = height / 4
    for k in range(-1, 5):
        y0 = top + k * stripe * 2 - stripe * 0.5
        if k % 1 == 0:
            pts_top, pts_bot = [], []
            x = -period
            i = 0
            while x <= S + period:
                yy = y0 + (amp if i % 2 else -amp)
                pts_top.append((x, yy))
                pts_bot.append((x, yy + stripe))
                x += period / 2
                i += 1
            d.polygon(pts_top + pts_bot[::-1], fill=(16, 14, 14))
    # keep the band tidy
    d.rectangle([0, top - S * 0.02, S, top], fill=None)
    return img


def home_title():
    floor = S * 0.16
    # key 1: the Black Lodge - dark, red curtain glow, EAS in Twin Peaks green
    img = look.gradient(S, (60, 6, 8), (18, 4, 6))
    d = ImageDraw.Draw(img)
    for k in range(9):                                   # curtain folds
        x = k * S / 8
        d.line([(x, 0), (x, S - floor)], fill=(110, 14, 16), width=int(S * 0.025))
    chevrons(img, S - floor, floor)
    f = look.font("folder", int(S * 0.5))
    look._text(d, f, ["EAS"], int(S * 0.5), S / 2 + 5, S * 0.1 + 5, S * 0.66, (8, 30, 10))
    look._text(d, f, ["EAS"], int(S * 0.5), S / 2, S * 0.1, S * 0.66, (96, 214, 108))
    img.save(OUT / "home-title-1.png")
    # keys 2-8: S T U D I O S on the carpet
    for i, letter in enumerate("STUDIOS"):
        img = carpet(S, S, offset_x=i * S * 1.08)
        chevrons(img, S - floor, floor)
        d = ImageDraw.Draw(img)
        f = look.font("folder", int(S * 0.62))
        look._text(d, f, [letter], int(S * 0.62), S / 2 + 6, S * 0.06 + 6, S * 0.72, (30, 10, 6))
        look._text(d, f, [letter], int(S * 0.62), S / 2, S * 0.06, S * 0.72, (246, 236, 214))
        img.save(OUT / f"home-title-{i + 2}.png")


def art_editing(d, img, box):
    """An audio clip: name bar, waveform, and a yellow clip-gain line with a breakpoint."""
    x0, y0, x1, y1 = box
    r = S * 0.03
    d.rounded_rectangle([x0, y0, x1, y1], radius=r, fill="#5a6f8c", outline="#c9d4e2", width=5)
    bar = y0 + (y1 - y0) * 0.2
    d.rounded_rectangle([x0, y0, x1, bar], radius=r, fill="#3c4c63")
    d.rectangle([x0 + 3, bar - r, x1 - 3, bar], fill="#3c4c63")
    cy, amp = (bar + y1) / 2, (y1 - bar) * 0.36
    n = 90
    for i in range(n + 1):
        t = i / n
        env = math.exp(-((t - 0.32) ** 2) / 0.02) + 0.55 * math.exp(-((t - 0.74) ** 2) / 0.01)
        a = amp * min(1.0, 0.18 + env) * abs(math.sin(i * 1.7) * 0.6 + math.sin(i * 0.53) * 0.4)
        x = x0 + (x1 - x0) * (0.04 + 0.92 * t)
        d.line([(x, cy - a), (x, cy + a)], fill="#e9eef5", width=4)
    g = [(x0 + (x1 - x0) * 0.04, cy - amp * 0.95), (x0 + (x1 - x0) * 0.55, cy - amp * 0.95),
         (x0 + (x1 - x0) * 0.7, cy - amp * 0.35), (x0 + (x1 - x0) * 0.96, cy - amp * 0.35)]
    d.line(g, fill="#f2c230", width=8, joint="curve")
    bx, by = g[2]
    d.ellipse([bx - 13, by - 13, bx + 13, by + 13], fill="#f2c230", outline="#3c4c63", width=4)


def art_recording(d, img, box):
    """A round record light, lit."""
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    r = (y1 - y0) * 0.4
    d.ellipse([cx - r * 1.3, cy - r * 1.3, cx + r * 1.3, cy + r * 1.3], fill="#2a2a2e", outline="#55585e", width=6)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#e23b2e")
    d.ellipse([cx - r * 0.55, cy - r * 0.75, cx - r * 0.05, cy - r * 0.35], fill="#ff8f85")


def art_solo(d, img, box):
    """Pro Tools' solo button: a yellow rounded square with an S."""
    x0, y0, x1, y1 = box
    h = (y1 - y0) * 0.92
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for k, (dx, a) in enumerate(((-h * 0.95, 0.45), (h * 0.95, 0.45), (0, 1.0))):
        bx = cx + dx
        sz = h * (0.62 if a < 1 else 0.8)
        fill = (232, 200, 40) if a == 1 else (120, 104, 30)
        d.rounded_rectangle([bx - sz / 2, cy - sz / 2, bx + sz / 2, cy + sz / 2], radius=sz * 0.14,
                            fill=fill, outline=(60, 50, 10), width=5)
        f = look.font("command", int(sz * 0.72))
        look._text(d, f, ["S"], int(sz * 0.72), bx, cy - sz / 2, sz, (30, 26, 6))


def cabinetron():
    img = look.gradient(S, "#2b2622", "#161311")
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = S * 0.08, S * 0.06, S * 0.92, S * 0.76
    d.rounded_rectangle([x0, y0, x1, y1], radius=S * 0.04, fill="#141414", outline="#3c3c3c", width=6)
    gx0, gy0, gx1, gy1 = x0 + S * 0.04, y0 + S * 0.04, x1 - S * 0.04, y1 - S * 0.04
    d.rectangle([gx0, gy0, gx1, gy1], fill="#2a2a28")                # grille cloth
    for k in range(0, int(gx1 - gx0), 9):
        d.line([(gx0 + k, gy0), (gx0 + k, gy1)], fill="#353532", width=2)
    r = (gx1 - gx0) * 0.2
    for cx in (gx0 + (gx1 - gx0) * 0.27, gx0 + (gx1 - gx0) * 0.73):     # 2x2 speakers
        for cy in (gy0 + (gy1 - gy0) * 0.27, gy0 + (gy1 - gy0) * 0.73):
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#0c0c0c", outline="#4a4a46", width=4)
            d.ellipse([cx - r * 0.35, cy - r * 0.35, cx + r * 0.35, cy + r * 0.35], fill="#2e2e2c")
    strip_h = S * 0.2
    d.rectangle([0, S - strip_h, S, S], fill="#c9a24a")
    f = look.font("folder", int(strip_h * 0.66))
    look._text(d, f, ["CABINETRON"], int(strip_h * 0.66), S / 2, S - strip_h, strip_h, "#17130c")
    img.save(OUT / "cabinetron.png")


def lodge_key(text, frac):
    """Your Black Lodge picture, with a longer, darker curtain, and neon lettering on it."""
    from PIL import ImageFilter as F
    src = Image.open(OUT / "source" / "black-lodge.png").convert("RGB")
    k = S / src.width
    cut = 150                                            # where the curtain meets the floor
    curtain_h = int(S * 0.74)
    curtain = src.crop((0, 0, src.width, cut)).resize((S, curtain_h), Image.LANCZOS)
    curtain = Image.eval(curtain, lambda v: int(v * 0.62))           # darker red
    floor = src.crop((0, cut, src.width, cut + int((S - curtain_h) / k))).resize((S, S - curtain_h), Image.LANCZOS)
    img = Image.new("RGB", (S, S))
    img.paste(floor, (0, curtain_h))
    img.paste(curtain, (0, 0))
    # neon lettering: a soft glow, a bright green outline, dark green inside
    px = int(S * frac)
    f = look.font("folder", px)
    d0 = ImageDraw.Draw(img)
    bb = d0.textbbox((0, 0), text, font=f, stroke_width=int(px * 0.06))
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    x, y = (S - tw) / 2 - bb[0], (curtain_h - th) / 2 - bb[1] - S * 0.01
    glow = Image.new("RGB", (S, S))
    ImageDraw.Draw(glow).text((x, y), text, font=f, fill=(40, 150, 60), stroke_width=int(px * 0.08),
                              stroke_fill=(40, 150, 60))
    glow = glow.filter(F.GaussianBlur(S * 0.022))
    from PIL import ImageChops
    img = ImageChops.screen(img, Image.eval(glow, lambda v: int(v * 0.3)))      # a soft neon glow
    d = ImageDraw.Draw(img)
    d.text((x, y), text, font=f, fill=(10, 58, 24), stroke_width=int(px * 0.05), stroke_fill=(74, 186, 96))
    return img


def lodge_title():
    lodge_key("EAS", 0.42).save(OUT / "home-title-1.png")
    for i, letter in enumerate("STUDIOS"):
        lodge_key(letter, 0.56).save(OUT / f"home-title-{i + 2}.png")


if __name__ == "__main__":
    detective = beat_detective()
    folder_frame("#c9b27a", "BEAT DETECTIVE", art_picture(detective)).save(OUT / "folder-beat-detective.png")
    folder_frame("#c8ccd2", "TRACK COLOURS", art_swatches).save(OUT / "folder-track-colours.png")
    folder_frame("#c9b9a2", "AIRPODS", art_picture("airpods.png")).save(OUT / "folder-airpods.png")
    folder_frame("#d9894f", "METRIC A/B", art_picture("metric-ab.png")).save(OUT / "folder-metric-ab.png")
    route("[DRUMS]", "route-drums.png")
    route("(PRINT)", "route-print.png")
    renumber_markers()
    import_template()
    keycap("C", "Copy Track Data", "copy-track-data.png")
    keycap("V", "Paste Inserts", "paste-inserts.png")
    track_colours_folder()
    folder_frame("#d08a2c", "MIX PREP", art_checklist).save(OUT / "folder-mix-prep.png")
    folder_frame("#7a3fa8", "MIX SENDS", art_knobs).save(OUT / "folder-mix-sends.png")
    folder_frame("#b0472c", "MIX BUS", art_vu).save(OUT / "folder-mix-bus.png")
    folder_frame("#3e7cb8", "BOUNCE MIX", art_reels).save(OUT / "folder-bounce-mix.png")
    folder_frame("#8d7a4a", "AMPETE", art_amp).save(OUT / "folder-ampete.png")
    home_title()                      # the Overlook carpet version (kept as home-title-carpet-*)
    for i in range(1, 9):
        (OUT / f"home-title-{i}.png").replace(OUT / f"home-title-carpet-{i}.png")
    lodge_title()
    folder_frame("#a8901c", "SOLO MODES", art_solo).save(OUT / "folder-solo-modes.png")
    cabinetron()
    folder_frame("#b0472c", "MIXING", art_vu).save(OUT / "folder-mixing.png")
    folder_frame("#2a8f8a", "EDITING", art_editing).save(OUT / "folder-editing.png")
    folder_frame("#b8342a", "RECORDING", art_recording).save(OUT / "folder-recording.png")
    print("done")
