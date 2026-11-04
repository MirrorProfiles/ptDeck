"""Remembers how each macro did: its last run (from the deck or the Manager) and
whether you've confirmed it works. Stored in test-results.json next to deck.yaml."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

_lock = threading.Lock()


def _path(base: Path) -> Path:
    return Path(base) / "test-results.json"


def load(base: Path) -> dict:
    try:
        return json.loads(_path(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(base: Path, data: dict):
    p = _path(base)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def record_run(base: Path, name: str, ok: bool, message: str = ""):
    with _lock:
        data = load(base)
        entry = data.setdefault(str(name), {})
        entry.update({"last_run": time.strftime("%d %b %H:%M"), "last_result": "ok" if ok else "error",
                      "message": message[:300]})
        _save(base, data)


def set_verdict(base: Path, name: str, verdict: str | None):
    """verdict: 'works', 'broken' or None (clear)."""
    with _lock:
        data = load(base)
        entry = data.setdefault(str(name), {})
        if verdict:
            entry["verdict"] = verdict
            entry["verdict_at"] = time.strftime("%d %b %H:%M")
        else:
            entry.pop("verdict", None)
            entry.pop("verdict_at", None)
        _save(base, data)
