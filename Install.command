#!/bin/bash
cd "$(dirname "$0")"
set -e
mkdir -p macros soundflow-scripts icons
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is needed first. Install it from https://brew.sh then run this again."
  read -p "Press Return to close."; exit 1
fi
brew install python@3.12 hidapi
"$(brew --prefix)/bin/python3.12" -m venv .venv
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m ptdeck make-app
echo
echo "Installed. Next: double-click \"PT Deck.app\" (it lives in the menu bar)."
echo "Or, to see everything in Terminal, double-click \"Start PT Deck.command\"."
read -p "Press Return to close."
