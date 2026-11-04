"""Where things live.

APP is the PT Deck folder itself (code, launchers, PT Deck.app, .venv, logs).
DATA is your own deck: deck.yaml, settings, macros, rebuilt, additions, icons, SoundFlow scripts.
Set PTDECK_DATA to use a deck folder somewhere else.
"""
import os
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("PTDECK_DATA") or APP / "my-deck").expanduser()
ASSETS = APP / "assets"
