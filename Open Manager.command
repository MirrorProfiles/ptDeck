#!/bin/bash
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "PT Deck isn't installed yet. Double-click Install.command first."
  read -p "Press Return to close."; exit 1
fi
.venv/bin/python -m ptdeck manager
