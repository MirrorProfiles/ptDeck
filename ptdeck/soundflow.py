"""Converts SoundFlow scripts (JavaScript) into PT Deck macro files.

Handles the straight-line scripts SoundFlow's editor produces. Anything it
doesn't recognise becomes a 'todo' step, so nothing is silently dropped.
"""
from __future__ import annotations

import json
import re

import yaml

COLLECTIONS = {
    "windows": "window", "groups": "group", "buttons": "button", "checkBoxes": "checkbox",
    "radioButtons": "radio button", "popupButtons": "popup", "menuButtons": "menu button",
    "textFields": "text field", "textAreas": "text area", "staticTexts": "text",
    "sliders": "slider", "scrollAreas": "scroll area", "tables": "table", "rows": "row",
    "cells": "cell", "tabGroups": "tab group", "splitGroups": "split group",
    "images": "image", "lists": "list", "outlines": "outline", "children": "any",
    "sheets": "sheet",
}


# ---------- reading the JavaScript ----------

def _split(js: str):
    """Remove comments, split into statements. Returns [(statement, command_name_from_comment)]."""
    out, buf, depth, i, n = [], [], 0, 0, len(js)
    pending_name = None
    stmt_name = None

    def flush():
        nonlocal buf, stmt_name
        s = "".join(buf).strip()
        if s:
            out.append((s, stmt_name))
        buf, stmt_name = [], None

    while i < n:
        c = js[i]
        if c in "\"'`":
            j = i + 1
            while j < n and js[j] != c:
                j += 2 if js[j] == "\\" else 1
            buf.append(js[i:j + 1])
            i = j + 1
            continue
        if js.startswith("/*", i):
            end = js.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if js.startswith("//", i):
            end = js.find("\n", i)
            end = n if end < 0 else end
            m = re.search(r'Calling command\s+"([^"]+)"', js[i:end])
            if m:
                pending_name = m.group(1)
            i = end
            continue
        if c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
            if c == "}" and depth == 0 and "".join(buf).lstrip().startswith("function"):
                buf.append(c)
                flush()
                i += 1
                continue
        if depth == 0 and c == ";":
            flush()
            i += 1
            continue
        if depth == 0 and c == "\n":
            rest = js[i + 1:].lstrip()
            if "".join(buf).strip() and (rest.startswith("sf.") or rest.startswith("//")) \
                    and not "".join(buf).rstrip().endswith((".", "+", "=", ",", "(")):
                flush()
                i += 1
                continue
        if not "".join(buf).strip() and not c.isspace():
            stmt_name, pending_name = pending_name, None
        buf.append(c)
        i += 1
    flush()
    return out


def _js_string(lit: str) -> str:
    q = lit[0]
    body = lit[1:-1]
    if q == '"':
        try:
            return json.loads(lit)
        except ValueError:
            pass
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), body)


def parse_js_object(src: str):
    """A small JS object/array literal -> Python. Raises ValueError if it's anything fancier."""
    src = src.strip()
    if not src:
        return {}
    out, i, n = [], 0, len(src)
    while i < n:
        c = src[i]
        if c in "\"'`":
            j = i + 1
            while j < n and src[j] != c:
                j += 2 if src[j] == "\\" else 1
            if c == "`" and "${" in src[i:j]:
                raise ValueError("template string")
            out.append(json.dumps(_js_string('"' + src[i + 1:j] + '"' if c != "'" else src[i:j + 1])))
            i = j + 1
        elif c.isalpha() or c == "_" or c == "$":
            m = re.match(r"[A-Za-z_$][\w$]*", src[i:])
            word = m.group(0)
            after = src[i + len(word):].lstrip()
            if after.startswith(":"):
                out.append(json.dumps(word))
            elif word in ("true", "false", "null"):
                out.append(word)
            else:
                raise ValueError(f"uses a variable or function ({word})")
            i += len(word)
        else:
            out.append(c)
            i += 1
    text = re.sub(r",\s*([}\]])", r"\1", "".join(out))
    return json.loads(text)


_STR = r'(?:"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')'
_SEG = re.compile(r"\.(\w+)")
_FILTER = re.compile(r"\.whose(Title|Description|Value)\.(is|startsWith|contains|endsWith)\((" + _STR + r")\)")
_PICK = re.compile(r"\.first\b|\[(\d+)\]|\.allItems\[(\d+)\]")


def _pattern(op: str, text: str) -> str:
    text = re.sub(r"([*?\[])", r"[\1]", text)
    return {"is": text, "startsWith": text + "*", "endsWith": "*" + text, "contains": f"*{text}*"}[op]


def _parse_chain(chain: str):
    """'.windows.whoseTitle.is("X").first.groups...' -> [(kind, name)], first item is the window."""
    segs, i = [], 0
    while i < len(chain):
        m = _SEG.match(chain, i)
        if not m:
            raise ValueError("unrecognised element path")
        coll = m.group(1)
        i = m.end()
        if coll in ("invalidate",):
            continue
        if coll in ("mainWindow", "focusedWindow"):
            segs.append(("window", "main" if coll == "mainWindow" else "front"))
            continue
        if coll not in COLLECTIONS:
            raise ValueError(f"'{coll}' isn't supported yet")
        name = None
        f = _FILTER.match(chain, i)
        if f:
            name = _pattern(f.group(2), _js_string(f.group(3)))
            i = f.end()
        p = _PICK.match(chain, i)
        if p:
            idx = p.group(1) or p.group(2)
            if idx is not None:
                if name is not None:
                    raise ValueError("picks the Nth of several same-named elements")
                name = f"#{int(idx) + 1}"
            elif name is None:
                name = "#1"
            i = p.end()
        elif name is None:
            raise ValueError("element path without .first")
        segs.append((COLLECTIONS[coll], name))
    if not segs or segs[0][0] != "window":
        raise ValueError("doesn't start from a Pro Tools window")
    return segs


def _target(segs):
    """Split parsed chain into step fields (window/group/path) + target (kind, name)."""
    window = segs[0][1]
    fields = {} if window == "main" else {"window": window}
    inner = segs[1:]
    if not inner:
        return fields, None
    containers, target = inner[:-1], inner[-1]
    if containers:
        if all(k == "group" and not n.startswith("#") for k, n in containers):
            gs = [n for _, n in containers]
            fields["group"] = gs[0] if len(gs) == 1 else gs
        else:
            fields["path"] = [f"{k} {n}" if n.startswith("#") else f"{k}: {n}" for k, n in containers]
    return fields, target


_ELEMENT_CALL = re.compile(r"^sf\.ui\.proTools((?:\.\w+.*?)?)\.(elementClick|checkboxSet|elementWaitFor|popupMenuSelect|"
                           r"mouseClickElement|elementSetTextFieldWithAreaValue|elementSetTextAreaValue|elementRaise)"
                           r"\((.*)\)$", re.S)


def _args(s):
    return parse_js_object(s) if s.strip() else {}


_APP_ROOT = re.compile(r"^sf\.ui\.app\((" + _STR + r")\)")


def convert_statement(stmt: str, cmd_name: str | None):
    s = stmt.strip()
    m = _APP_ROOT.match(s)
    if m:                                   # another app, e.g. sf.ui.app('com.apple.QuickTimePlayerX')
        bundle = _js_string(m.group(1))
        rest = "sf.ui.proTools" + s[m.end():]
        if re.match(r"^sf\.ui\.proTools\.appQuit\(", rest):
            return {"quit app": bundle}
        if re.match(r"^sf\.ui\.proTools\.(appActivateMainWindow|appActivate)\(\s*\)$", rest):
            return {"open": bundle_name(bundle)}
        step = _convert(rest, cmd_name)
        if step is not None:
            step["app"] = bundle
        return step
    return _convert(s, cmd_name)


def bundle_name(bundle: str) -> str:
    known = {"com.apple.QuickTimePlayerX": "QuickTime Player", "com.apple.finder": "Finder"}
    return known.get(bundle, bundle)


def _convert(s: str, cmd_name: str | None):
    m = re.match(r"^sf\.midi\.sendCC\((.*)\)$", s, re.S)
    if m:
        a = _args(m.group(1))
        step = {"midi cc": int(a["midiCC"]), "value": int(a.get("value", 127)),
                "channel": int(a.get("midiChannel", 1))}
        if a.get("externalMidiPort"):
            step["port"] = a["externalMidiPort"]
        return step
    m = re.match(r"^sf\.(?:app\.launch|directory\.open|file\.open)\((.*)\)$", s, re.S)
    if m:
        return {"open": _args(m.group(1))["path"]}
    if re.match(r"^sf\.(?:app|ui)\.proTools\.saveSession\(\s*\)$", s) or re.search(r"\)\.saveSession\(\s*\)$", s):
        return {"pro tools": "SaveSession"}
    m = re.match(r"^sf\.ui\.proTools\.selectedTrack\.trackInsertOrSendSelect\((.*)\)$", s, re.S)
    if m:
        a = _args(m.group(1))
        path = [str(p) for p in a["pluginPath"]]
        kind = str(a.get("insertOrSend", "Insert")).lower()
        if path and path[-1].lower() in ("no insert", "no send"):
            raise ValueError("removes an insert/send")
        if kind == "send":
            step = {"send": " > ".join(path), "slot": int(a.get("pluginNumber", 1))}
        else:
            step = {"insert plugin": path[-1], "slot": int(a.get("pluginNumber", 1))}
        if a.get("selectForAllSelectedTracks"):
            step["all selected"] = True
        return step
    m = re.match(r"^sf\.ui\.proTools\.trackGetByName\((.*?)\)\.track\.trackInsertToggleShow\((.*)\)$", s, re.S)
    if m:
        t, a = _args(m.group(1)), _args(m.group(2))
        return {"plugin window": int(a.get("insertNumber", 1)), "track": t["name"],
                "set": _onoff(a.get("targetValue", "Toggle")).replace("on", "open").replace("off", "close")}
    m = re.match(r"^sf\.ui\.proTools\.audioSuiteOpenPlugin\((.*)\)$", s, re.S)
    if m:
        a = _args(m.group(1))
        return {"audiosuite": a["name"]}
    m = re.match(r"^sf\.ui\.proTools\.firstAudioSuiteWindow\.audioSuiteSelectPreset\((.*)\)$", s, re.S)
    if m:
        return {"audiosuite preset": " > ".join(_args(m.group(1))["presetMenuPath"])}
    if re.match(r"^sf\.ui\.proTools\.firstAudioSuiteWindow\.audioSuiteRender\(\s*\)$", s):
        return {"audiosuite render": None}
    m = re.match(r"^sf\.ui\.proTools\.(appActivateMainWindow|appActivate)\(\s*\)$", s)
    if m:
        return {"activate": "Pro Tools"}
    if re.match(r"^sf\.ui\.proTools(\.mainWindow)?\.invalidate\(\s*\)$", s):
        return None
    m = re.match(r"^sf\.ui\.proTools\.menuClick\((.*)\)$", s, re.S)
    if m:
        a = _args(m.group(1))
        step = {"menu": " > ".join(a["menuPath"])}
        if "targetValue" in a:
            step["set"] = _onoff(a["targetValue"])
        return step
    m = re.match(r"^sf\.keyboard\.press\((.*)\)$", s, re.S)
    if m:
        a = _args(m.group(1))
        step = {"press": a["keys"]}
        if int(a.get("repetitions", 1)) > 1:
            step["times"] = int(a["repetitions"])
        return step
    m = re.match(r"^sf\.keyboard\.type\((.*)\)$", s, re.S)
    if m:
        return {"type": _args(m.group(1))["text"]}
    m = re.match(r"^sf\.wait\((.*)\)$", s, re.S)
    if m:
        ms = _args(m.group(1)).get("intervalMs", 500)
        return {"wait": f"{ms}ms"}
    m = re.match(r"^sf\.soundflow\.runCommand\((.*)\)$", s, re.S)
    if m:
        a = _args(m.group(1))
        props = a.get("props") or {}
        if "pluginName" in props:          # SoundFlow's "insert plug-in" command
            slot = str(props.get("pluginSlot", "firstFree"))
            step = {"insert plugin": props["pluginName"],
                    "slot": "first free" if slot.lower() == "firstfree" else int(slot) if slot.isdigit() else slot}
            if props.get("pluginCatagory") or props.get("pluginCategory"):
                step["category"] = props.get("pluginCatagory") or props.get("pluginCategory")
            return step
        if "outputPath" in props:          # SoundFlow's "set output" command
            return {"output": " > ".join(props["outputPath"])}
        if "inputPath" in props:
            return {"input": " > ".join(props["inputPath"])}
        if props:
            raise ValueError("passes settings (props) to a SoundFlow command PT Deck doesn't know yet")
        return {"run macro": cmd_name or f"UNKNOWN COMMAND {a.get('commandId')}"}
    m = re.match(r"^sf\.mouse\.click\((.*)\)$", s, re.S)
    if m:
        a = _args(m.group(1))
        step = {"click at": [a["position"]["x"], a["position"]["y"]], "relative to": "screen"}
        if a.get("button") == "right":
            step["button"] = "right"
        if int(a.get("clickCount", 1)) > 1:
            step["double"] = True
        return step
    m = _ELEMENT_CALL.match(s)
    if m:
        chain, method, a = m.group(1), m.group(2), _args(m.group(3))
        fields, target = _target(_parse_chain(chain))
        if method == "elementWaitFor" and target is None:
            step = {"wait for window": fields.pop("window", "main"), **fields}
        elif method == "elementRaise" and target is None:
            step = {"raise window": fields.pop("window", "main")}
        elif target is None:
            raise ValueError(f"{method} on a whole window")
        else:
            kind, name = target
            if method == "elementClick":
                step = {"click": name, "kind": kind, **fields}
            elif method == "checkboxSet":
                step = {"checkbox": name, "set": _onoff(a.get("targetValue", "Enable")), **fields}
                if kind != "checkbox":
                    step["kind"] = kind
            elif method == "elementWaitFor":
                step = {"wait for": name, "kind": kind, **fields}
            elif method == "popupMenuSelect":
                if a.get("isRightClick") or a.get("isOption") or a.get("isShift"):
                    raise ValueError("popup with modifier/right click")
                step = {"popup": name, "choose": " > ".join(a["menuPath"]), "kind": kind, **fields}
            elif method == "mouseClickElement":
                rp = a.get("relativePosition")
                step = {"click at": [rp["x"], rp["y"]] if rp else None, "element": name, "kind": kind, **fields}
                if a.get("isRightClick"):
                    step["button"] = "right"
                if int(a.get("clickCount", 1)) > 1:
                    step["double"] = True
                mods = [k for k, f in (("cmd", "isCommand"), ("shift", "isShift"), ("option", "isOption"),
                                       ("ctrl", "isControl")) if a.get(f)]
                if mods:
                    step["modifiers"] = "+".join(mods)
            elif method in ("elementSetTextFieldWithAreaValue", "elementSetTextAreaValue"):
                step = {"set text": name, "to": a.get("value", ""), "kind": kind, **fields}
            else:
                raise ValueError(method)
        if method == "elementWaitFor":
            if str(a.get("waitType", "")).lower() == "disappear":
                step["gone"] = True
            if "timeout" in a:
                step["timeout"] = f"{a['timeout']}ms"
        return step
    raise ValueError("not recognised")


def _onoff(v):
    v = str(v).lower()
    return {"enable": "on", "disable": "off", "toggle": "toggle"}.get(v, v)


_FUNC = re.compile(r"^function\s+(\w+)\s*\(\s*\)\s*\{(.*)\}$", re.S)
_CALL = re.compile(r"^(\w+)\(\s*\)$")


def convert(js: str, name: str):
    """Returns (macro dict, list of warnings)."""
    steps, warnings = [], []
    statements = _split(js)
    # Simple helper functions (no inputs, only straightforward steps) are expanded
    # where they're called, e.g. 'function setCab() { sf.midi.sendCC(...); ... } setCab();'
    functions = {}
    for stmt, _ in statements:
        m = _FUNC.match(stmt.strip())
        if m:
            try:
                body = [convert_statement(st, cn) for st, cn in _split(m.group(2))]
                functions[m.group(1)] = [b for b in body if b is not None]
            except (ValueError, KeyError, TypeError):
                pass
    for stmt, cmd_name in statements:
        m = _FUNC.match(stmt.strip())
        if m and m.group(1) in functions:
            continue
        m = _CALL.match(stmt.strip())
        if m and m.group(1) in functions:
            steps.extend(dict(x) for x in functions[m.group(1)])
            continue
        try:
            step = convert_statement(stmt, cmd_name)
        except (ValueError, KeyError, TypeError) as e:
            one_line = re.sub(r"\s+", " ", stmt)
            steps.append({"todo": one_line})
            warnings.append(f"Couldn't convert ({e}): {one_line[:120]}")
            continue
        if step is not None:
            steps.append(step)
            if "run macro" in step:
                warnings.append(f"Calls another SoundFlow command: '{step['run macro']}'. Import that one too.")
    return {"name": name, "steps": steps}, warnings


def to_yaml(macro: dict, source_note: str = "Imported from SoundFlow") -> str:
    body = yaml.safe_dump(macro, sort_keys=False, allow_unicode=True, width=1000, default_flow_style=False)
    body = re.sub(r"(\n  set: )'(on|off)'", r"\1\2", body)
    body = re.sub(r"(?m)^- ([^:\n]+): null$", r"- \1", body)
    return f"# {source_note}\n" + body.replace("\n- ", "\n\n- ").replace("steps:\n\n- ", "steps:\n- ")
