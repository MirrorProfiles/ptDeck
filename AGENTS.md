# PT Deck: notes for AI agents

PT Deck runs Pro Tools macros from an Elgato Stream Deck on macOS (Python, no SoundFlow).

**To add or change a macro or a key, read [PTDECK_LANGUAGE_AND_RULES.md](PTDECK_LANGUAGE_AND_RULES.md) first.** It is
the reference for the step language, key settings, the process and the rules.

Essentials:
- App code is in `ptdeck/`. The owner's deck (layout, macros, pictures) is in `my-deck/`.
  Paths come from `ptdeck/paths.py`.
- Don't move or rename existing keys or pages unless asked. Put new keys in empty keys.
- Never leave an empty placeholder macro in `my-deck/macros/`: it hides the working macro of
  the same name in `my-deck/rebuilt/`.
- Never commit `my-deck/settings.json`, `test-results.json`, `backups/`, `previews/` or logs.
- Before committing, run `.venv/bin/python -m ptdeck check` and
  `.venv/bin/python -m pytest -q tests` (install pytest from `requirements-dev.txt` once).
- After Python changes, restart PT Deck (menu bar → Restart) and try the key in Pro Tools.
- Anything that polls Pro Tools must stay light (see "Code" in PTDECK_LANGUAGE_AND_RULES.md section 8).

**Keep PTDECK_LANGUAGE_AND_RULES.md current.** A new step, option, key setting, glyph, addition type or
command needs a line there in the same change; `test_language_and_rules_are_complete` fails until it
has one. Add new Pro Tools quirks to section 9 and new house rules to section 8.

**Shared engine.** Chris's CHP (github.com/CFH1313/chp, git remote `chp`) runs this same engine with
his own deck, so macros and keys can move between the two. To keep that easy:
- Keep engine changes (`ptdeck/`, `tests/`, `PTDECK_LANGUAGE_AND_RULES.md`, `requirements.txt`, the
  launchers) in commits separate from `my-deck/` changes, so either side can take them cleanly.
- Take CHP's engine changes file by file: `git fetch chp`, then
  `git checkout chp/main -- <engine paths>`. Never merge chp/main as a whole: it would replace
  this deck with Chris's.
- CHP-specific tests go in `tests/test_chp.py`; neither test file may read a real deck.
- Before committing engine changes, compare `ptdeck preview` pictures before and after, so the
  deck still looks the same.

`docs/cloud-session-notes.md` is the record from the conversation that first built PT Deck,
including things still to test.
