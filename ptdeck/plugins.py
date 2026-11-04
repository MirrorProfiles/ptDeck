"""Your installed plug-ins, for the Manager's 'Plug-in buttons' tool.

Reads Pro Tools' plug-in folder, turns file names into the names Pro Tools shows (as near as
can be guessed: you can correct a name before making its button), and spots which plug-ins
already have an 'insert plugin' macro and a key on the deck.
"""
from __future__ import annotations

import re
from pathlib import Path

FOLDER = Path("/Library/Application Support/Avid/Audio/Plug-Ins")
WAVES = Path("/Applications/Waves")      # Waves keeps the real list here ('Plug-Ins V15' etc.)
SKIP = re.compile(r"(?i)^waveshell")      # Waves shells hold many plug-ins: they can't be listed

# File-name prefix -> (how the name starts in Pro Tools, manufacturer menu in Pro Tools)
VENDORS = [
    (r"^iZ", "", "iZotope"),
    (r"^uaudio_", "UADx ", "Universal Audio (UADx)"),
    (r"^FabFilter ", "FabFilter ", "FabFilter"),
    (r"^bx_", "bx_", "Plugin Alliance"),
    (r"^SSL ", "SSL ", "Solid State Logic"),
    (r"^Valhalla", "Valhalla", "Valhalla DSP, LLC"),
    (r"^TemeculaDSP", "", "Temecula DSP"),
    (r"^Unfiltered Audio ", "Unfiltered Audio ", "Unfiltered Audio"),
    (r"^Archetype ", "Archetype ", "Neural DSP"),
    (r"^STL ", "STL ", "STL Tones"),
    (r"^Oxford ", "Oxford ", "Sonnox"),
    (r"^elysia ", "elysia ", "Plugin Alliance"),
    (r"^Lindell ", "Lindell ", "Plugin Alliance"),
    (r"^AIR", "AIR ", "AIR"),
    (r"^NA ", "NA ", "Nembrini Audio"),
    (r"^TDR ", "TDR ", "Tokyo Dawn Labs"),
    (r"^Tube-Tech ", "Tube-Tech ", "Softube"),
]
UA_UPPER = {"ua", "ssl", "la", "api", "emt", "eq", "eqp", "meq", "hlf", "atr", "vt", "dbx", "vog", "b3", "a800"}


def split_words(text: str) -> list[str]:
    """'RX11De-click' -> ['RX', '11', 'De-click']; 'MouthDe-click' -> ['Mouth', 'De-click']."""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = re.sub(r"([A-Za-z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([A-Za-z]{2,})", r"\1 \2", text)
    return text.split()


def display_name(file_name: str) -> tuple[str, str]:
    """(name as Pro Tools probably shows it, manufacturer menu guess) from a .aaxplugin name."""
    stem = re.sub(r"\.aaxplugin$", "", file_name)
    for pat, lead, vendor in VENDORS:
        if re.match(pat, stem):
            if pat == r"^iZ":
                core = re.sub(r"AAXHook$", "", stem[2:])
                return " ".join(split_words(core)), vendor
            if pat == r"^uaudio_":
                words = stem[len("uaudio_"):].split("_")
                return lead + " ".join(w.upper() if w in UA_UPPER else w.capitalize() for w in words), vendor
            return stem.replace("_", " ") if not stem.startswith("bx_") else stem, vendor
    return stem.replace("_", " "), ""


VENDOR_WORDS = {"ua", "uadx", "uaudio", "iz", "izotope", "plugin", "plug", "in", "v6", "aax"}


def tokens(text: str) -> set[str]:
    words = re.split(r"[^a-z0-9]+", " ".join(split_words(str(text))).lower())
    return {w for w in words if w and w not in VENDOR_WORDS}


def same_plugin(a: str, b: str) -> bool:
    """True if two names look like the same plug-in (all words of the shorter in the longer)."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return False
    small, big = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if small <= big:
        return True
    # Same model number (e.g. 1073, 1176): 'UADx Neve 1073' = 'UADx 1073 Preamp and EQ'
    return any(w.isdigit() and len(w) >= 3 for w in ta & tb)


def scan(folder: Path | None = None) -> list[dict]:
    """Every .aaxplugin in the folder (and one level of vendor sub-folders), plus Waves."""
    folder = Path(folder or FOLDER)
    found = []
    if not folder.is_dir():
        return found
    for p in sorted(folder.rglob("*.aaxplugin")):
        if len(p.relative_to(folder).parts) > 2 or SKIP.match(p.stem):
            continue
        name, vendor = display_name(p.name)
        found.append({"file": p.name, "name": name, "vendor": vendor})
    found += scan_waves()
    return found


def scan_waves(folder: Path | None = None) -> list[dict]:
    """Waves plug-ins all hide inside one 'WaveShell' in Pro Tools' folder; the real list is the
    .bundle files in Waves' own 'Plug-Ins V..' folder (the newest version you have)."""
    folder = Path(folder or WAVES)
    if not folder.is_dir():
        return []
    versions = sorted((d for d in folder.glob("Plug-Ins V*") if d.is_dir()),
                      key=lambda d: [int(x) for x in re.findall(r"\d+", d.name)] or [0])
    if not versions:
        return []
    out, seen = [], set()
    for d in reversed(versions):                     # newest first; older-only plug-ins still count
        for b in sorted(d.glob("*.bundle")):
            if b.stem.lower() in seen or re.match(r"(?i)waves(shell|lib)|^lib", b.stem):
                continue
            seen.add(b.stem.lower())
            out.append({"file": f"{b.stem} (Waves)", "name": b.stem, "vendor": "Waves"})
    return out


def with_buttons(plugins: list[dict], macros: list[dict], on_deck: set[str]) -> list[dict]:
    """Mark each plug-in with the macros that already insert it, and whether one is on the deck.
    macros: [{'name', 'inserts': [plug-in names]}]."""
    for p in plugins:
        hits = [m["name"] for m in macros if any(same_plugin(p["name"], i) or same_plugin(p["file"], i)
                                                 for i in m["inserts"])]
        p["macros"] = hits
        p["on_deck"] = any(h.lower() in on_deck for h in hits)
    return plugins


def macro_yaml(name: str, plugin: str, category: str, slot) -> str:
    lines = ["# Made with PT Deck's Plug-in buttons tool",
             f"name: {_q(name)}", "steps:", f"- insert plugin: {_q(plugin)}",
             f"  slot: {slot if slot not in (None, '') else 'first free'}"]
    if category:
        lines.append(f"  category: {_q(category)}")
    return "\n".join(lines) + "\n"


def _q(s) -> str:
    import json
    s = str(s)
    return json.dumps(s) if re.search(r"[:#'\"\[\]{}&*!|>%@`]|^\s|\s$", s) else s
