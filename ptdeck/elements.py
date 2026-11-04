"""Finding things in Pro Tools' interface: windows, groups, buttons, checkboxes...

Works on any element object with:
    attr(name)          -> value of an Accessibility attribute (or None)
    set_attr(name, v)   -> bool
    perform(action)     -> bool
The real macOS version is in mac.py; tests use fake elements.
"""
from __future__ import annotations

import fnmatch
import re

# Friendly names used in macro files -> macOS Accessibility roles.
KINDS = {
    "button": "AXButton",
    "checkbox": "AXCheckBox",
    "radio button": "AXRadioButton",
    "radio": "AXRadioButton",
    "group": "AXGroup",
    "popup": "AXPopUpButton",
    "menu button": "AXMenuButton",
    "text field": "AXTextField",
    "text area": "AXTextArea",
    "text": "AXStaticText",
    "slider": "AXSlider",
    "scroll area": "AXScrollArea",
    "table": "AXTable",
    "row": "AXRow",
    "cell": "AXCell",
    "list": "AXList",
    "outline": "AXOutline",
    "tab group": "AXTabGroup",
    "split group": "AXSplitGroup",
    "image": "AXImage",
    "window": "AXWindow",
    "sheet": "AXSheet",
    "menu item": "AXMenuItem",
    "any": None,
}
ROLE_TO_KIND = {v: k for k, v in reversed(list(KINDS.items())) if v}


class NotFound(Exception):
    pass


def norm(s) -> str:
    s = "" if s is None else str(s)
    return s.replace("…", "...").replace(" ", " ").strip()


def kind_role(kind: str | None) -> str | None:
    if not kind:
        return None
    k = kind.strip().lower()
    if k not in KINDS:
        raise ValueError(f"Unknown kind '{kind}'. Use one of: {', '.join(KINDS)}")
    return KINDS[k]


def labels(el) -> list[str]:
    """The names an element can be found by: title first, then description."""
    out = []
    for a in ("AXTitle", "AXDescription"):
        v = norm(el.attr(a))
        if v:
            out.append(v)
    if el.attr("AXRole") == "AXStaticText":
        v = norm(el.attr("AXValue"))
        if v:
            out.append(v)
    return out


def name_matches(el, pattern: str) -> bool:
    """Exact match, or wildcard match if the pattern contains * or ?."""
    p = norm(pattern)
    wild = "*" in p or "?" in p
    for lab in labels(el):
        if (fnmatch.fnmatchcase(lab, p) if wild else lab == p):
            return True
    return False


def children(el) -> list:
    return list(el.attr("AXChildren") or [])


def find_all(root, role: str | None = None, name: str | None = None, max_depth: int = 25) -> list:
    """Search everything inside root (closest first) for matching elements."""
    found, level, depth = [], children(root), 0
    while level and depth < max_depth:
        nxt = []
        for el in level:
            if (role is None or el.attr("AXRole") == role) and (name is None or name_matches(el, name)):
                found.append(el)
            nxt.extend(children(el))
        level, depth = nxt, depth + 1
    return found


_NTH = re.compile(r"^#(\d+)$")


def find_one(root, kind: str | None, name: str | None):
    """name may be '#3' meaning 'the 3rd one of this kind directly inside root'."""
    role = kind_role(kind)
    m = _NTH.match(norm(name)) if name is not None else None
    if m:
        n = int(m.group(1))
        direct = [c for c in children(root) if role is None or c.attr("AXRole") == role]
        if len(direct) >= n:
            return direct[n - 1]
        raise NotFound(f"no {kind or 'element'} #{n}")
    hits = find_all(root, role, name)
    if not hits:
        raise NotFound(f"{kind or 'element'} '{name}'" if name else f"any {kind}")
    return hits[0]


def parse_path_entry(entry: str) -> tuple[str, str | None]:
    """'group: Session Data' -> ('group', 'Session Data');  'scroll area #1' -> ('scroll area', '#1')."""
    entry = str(entry).strip()
    if ":" in entry:
        kind, name = entry.split(":", 1)
        return kind.strip(), name.strip()
    m = re.match(r"^(.*?)\s*(#\d+)$", entry)
    if m:
        return m.group(1), m.group(2)
    return entry, None


def window_list(app) -> list:
    """All of the app's windows, including dialogs Pro Tools only lists among its children."""
    wins = list(app.attr("AXWindows") or [])
    for c in children(app):
        if c.attr("AXRole") in ("AXWindow", "AXSheet") and not any(c == w for w in wins):
            wins.append(c)
    return wins


def find_window(app, name: str | None):
    if name is None or norm(name).lower() in ("main", "main window"):
        w = app.attr("AXMainWindow") or app.attr("AXFocusedWindow")
        if w is None:
            raise NotFound("Pro Tools main window")
        return w
    if norm(name).lower() in ("front", "focused", "front window"):
        w = app.attr("AXFocusedWindow")
        if w is None:
            raise NotFound("a focused window")
        return w
    wins = window_list(app)
    for w in wins:
        if name_matches(w, name):
            return w
    # Fall back to "title starts with" so 'Edit:' finds 'Edit: My Session'.
    for w in wins:
        if any(lab.startswith(norm(name)) for lab in labels(w)):
            return w
    raise NotFound(f"window '{name}'")


def resolve(app, window=None, group=None, path=None, kind=None, name=None):
    """Find an element from the fields used in macro steps."""
    root = find_window(app, window)
    containers = []
    if group:
        containers += [("group", g) for g in (group if isinstance(group, list) else [group])]
    if path:
        containers += [parse_path_entry(p) for p in (path if isinstance(path, list) else [path])]
    for k, n in containers:
        try:
            root = find_one(root, k, n)
        except NotFound as e:
            raise NotFound(f"{e} (in window '{window or 'main'}')") from None
    if name is None and kind is None:
        return root
    try:
        return find_one(root, kind, name)
    except NotFound as e:
        where = f"window '{window or 'main'}'" + (f", {containers[-1][0]} '{containers[-1][1]}'" if containers else "")
        raise NotFound(f"{e} in {where}") from None


def describe(el) -> str:
    role = el.attr("AXRole") or "?"
    kind = ROLE_TO_KIND.get(role, role)
    labs = labels(el)
    return f"{kind} '{labs[0]}'" if labs else kind
