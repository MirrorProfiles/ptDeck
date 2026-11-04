#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "PT Deck isn't installed yet. Double-click Install.command first."
  read -p "Press Return to close."; exit 1
fi
echo "PT Deck is running. Close this window (or press Ctrl+C) to stop."
.venv/bin/python -m ptdeck start
read -p "Stopped. Press Return to close."
