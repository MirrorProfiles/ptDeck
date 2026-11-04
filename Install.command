#!/bin/bash
cd "$(dirname "$0")"
set -e
mkdir -p my-deck/macros my-deck/soundflow-scripts my-deck/icons

# Homebrew (a free installer for Mac tools) is how PT Deck gets Python and the Stream Deck driver.
for p in /opt/homebrew/bin /usr/local/bin; do [ -x "$p/brew" ] && export PATH="$p:$PATH"; done
if ! command -v brew >/dev/null 2>&1; then
  echo "PT Deck needs Homebrew first (free, from brew.sh)."
  echo "It will install now. It may ask for your Mac password (typing won't show) and to press Return."
  echo
  read -p "Press Return to install Homebrew, or close this window to stop. "
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  for p in /opt/homebrew/bin /usr/local/bin; do [ -x "$p/brew" ] && export PATH="$p:$PATH"; done
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew didn't finish installing. Run this file again, or install it from https://brew.sh"
    read -p "Press Return to close."; exit 1
  fi
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
