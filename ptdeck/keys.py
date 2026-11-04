"""Turns key names like "cmd+shift+n" or "numpad 1" into macOS key codes."""
from __future__ import annotations

CMD, SHIFT, ALT, CTRL, FN = 0x100000, 0x20000, 0x80000, 0x40000, 0x800000

MODIFIERS = {
    "cmd": CMD, "command": CMD, "⌘": CMD,
    "shift": SHIFT, "⇧": SHIFT,
    "alt": ALT, "option": ALT, "opt": ALT, "⌥": ALT,
    "ctrl": CTRL, "control": CTRL, "⌃": CTRL,
    "fn": FN,
}

# Key codes for the modifier keys themselves (pressed around the main key).
MODIFIER_KEYCODES = {CMD: 55, SHIFT: 56, ALT: 58, CTRL: 59, FN: 63}

KEYCODES = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17, "1": 18, "2": 19,
    "3": 20, "4": 21, "6": 22, "5": 23, "=": 24, "9": 25, "7": 26, "-": 27, "8": 28,
    "0": 29, "]": 30, "o": 31, "u": 32, "[": 33, "i": 34, "p": 35, "return": 36,
    "l": 37, "j": 38, "'": 39, "k": 40, ";": 41, "\\": 42, ",": 43, "/": 44, "n": 45,
    "m": 46, ".": 47, "tab": 48, "space": 49, "`": 50, "backspace": 51, "escape": 53,
    "numpad .": 65, "numpad *": 67, "numpad +": 69, "numpad clear": 71, "numpad /": 75,
    "numpad enter": 76, "numpad -": 78, "numpad =": 81,
    "numpad 0": 82, "numpad 1": 83, "numpad 2": 84, "numpad 3": 85, "numpad 4": 86,
    "numpad 5": 87, "numpad 6": 88, "numpad 7": 89, "numpad 8": 91, "numpad 9": 92,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98, "f8": 100,
    "f9": 101, "f10": 109, "f11": 103, "f12": 111, "f13": 105, "f14": 107, "f15": 113,
    "f16": 106, "f17": 64, "f18": 79, "f19": 80, "f20": 90,
    "help": 114, "home": 115, "page up": 116, "forward delete": 117, "end": 119,
    "page down": 121, "left": 123, "right": 124, "down": 125, "up": 126,
}

ALIASES = {
    "enter": "numpad enter", "esc": "escape", "delete": "backspace", "del": "forward delete",
    "forwarddelete": "forward delete", "pageup": "page up", "pagedown": "page down",
    "left arrow": "left", "right arrow": "right", "up arrow": "up", "down arrow": "down",
    "arrow left": "left", "arrow right": "right", "arrow up": "up", "arrow down": "down",
    "minus": "-", "equal": "=", "equals": "=", "comma": ",", "period": ".", "dot": ".",
    "slash": "/", "backslash": "\\", "semicolon": ";", "quote": "'", "grave": "`",
    "left bracket": "[", "right bracket": "]", "spacebar": "space", "space bar": "space",
    "numpad plus": "numpad +", "numpad minus": "numpad -", "numpad multiply": "numpad *",
    "numpad divide": "numpad /", "numpad period": "numpad .", "numpad decimal": "numpad .",
    "numpad equals": "numpad =", "numpad equal": "numpad =", "clear": "numpad clear",
    "numlock": "numpad clear",
}
for _i in range(10):
    ALIASES[f"numpad{_i}"] = f"numpad {_i}"
    ALIASES[f"num {_i}"] = f"numpad {_i}"


class KeyError_(ValueError):
    pass


def parse_combo(combo: str) -> tuple[int, int]:
    """'cmd+shift+n' -> (keycode, modifier flags)."""
    text = combo.strip().lower()
    parts = [p.strip() for p in text.split("+")]
    # "cmd++" or "numpad+" style: an empty part means the "+" key itself.
    if text.endswith("+") and len(parts) >= 2 and parts[-1] == "" and parts[-2] == "":
        parts = parts[:-2] + ["="]  # plain "+" lives on the "=" key (with shift)
    flags = 0
    key = None
    for p in parts:
        if not p:
            continue
        if p in MODIFIERS:
            flags |= MODIFIERS[p]
            continue
        if key is not None:
            raise KeyError_(f"'{combo}' has more than one main key")
        key = ALIASES.get(p, p)
    if key is None:
        raise KeyError_(f"'{combo}' has no main key")
    if key not in KEYCODES:
        raise KeyError_(f"Unknown key '{key}' in '{combo}'")
    return KEYCODES[key], flags


def parse_sequence(keys: str) -> list[tuple[int, int]]:
    """'cmd+a, return' -> two key presses. Use ', ' (comma + space) between presses."""
    return [parse_combo(c) for c in str(keys).split(", ") if c.strip()]
