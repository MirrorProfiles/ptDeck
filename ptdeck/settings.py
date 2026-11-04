"""Small remembered choices (e.g. your bounce source), kept in settings.json next to deck.yaml."""
from __future__ import annotations

import json
from pathlib import Path


def _path(base) -> Path:
    return Path(base) / "settings.json"


def get(base, key, default=None):
    try:
        return json.loads(_path(base).read_text(encoding="utf-8")).get(key, default)
    except (OSError, ValueError):
        return default


def put(base, key, value):
    try:
        data = json.loads(_path(base).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data[key] = value
    _path(base).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
