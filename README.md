# PT Deck

Runs your Pro Tools macros from the Stream Deck, without SoundFlow. It handles
the Stream Deck itself (pages, folders, icons, labels), so neither SoundFlow
nor the Elgato app needs to be running.

Macros are plain text lists of steps, written in a simple step format.
**You don't need to know JavaScript or Python to use or edit them.**

```yaml
- wait for window: Import Session Data
- checkbox: HEAT Master Settings
  set: off
  window: Import Session Data
  group: Session Data
- click: OK
  window: Import Session Data
```

---

## What's in this folder

| Folder | What it is |
|---|---|
| `ptdeck/` | PT Deck's code (Python) and the Manager page (`manager.html`) |
| `assets/` | PT Deck's own fonts |
| `tools/` | `make_icons.py`, which redraws the generated key pictures |
| `tests/` | Automated tests (`.venv/bin/pip install -r requirements-dev.txt`, then `.venv/bin/python -m pytest tests`) |
| `PTDECK_LANGUAGE_AND_RULES.md` | **How PT Deck works:** the macro language, key settings and the rules for adding macros and keys |
| `docs/` | Notes from the first build (Pro Tools findings, things still to test) |
| `my-deck/` | **Your deck:** `deck.yaml`, `macros/`, `rebuilt/`, `additions/`, `icons/`, `soundflow-scripts/` |
| `*.command` | Double-click launchers |

Inside `my-deck/`, `settings.json`, `test-results.json`, `backups/` and `previews/` change every time
you use the deck, so they're kept out of git. To keep your deck somewhere else, set `PTDECK_DATA`
to that folder.

---

## 1. One-time setup

1. Install **Homebrew** if you don't have it: https://brew.sh
2. Put this `ptdeck` folder somewhere permanent (e.g. your Documents folder).
3. Double-click **Install.command**. It installs Python and the Stream Deck driver.
   - If macOS says it can't be opened, right-click the file → **Open** → **Open**.
     (Or in Terminal: `xattr -dr com.apple.quarantine ~/Documents/ptdeck`.)
4. **Quit SoundFlow** (and the Elgato Stream Deck app if it's running). Only one
   program can use the Stream Deck at a time.
5. Double-click **Start PT Deck.command**. The first time, macOS asks for
   **Accessibility** permission: System Settings → Privacy & Security →
   Accessibility → turn on **Terminal**. Then start it again.

The deck lights up with your buttons. Leave that Terminal window open while you
work; closing it stops PT Deck.

While a macro runs, its key gets a **yellow** border. It flashes **green** when
it finishes, or **red** if something went wrong. The reason is shown in the
Terminal window and saved in `ptdeck.log`.

## 2. Bringing scripts over from SoundFlow

> After installing a new version of PT Deck, double-click **Update Macros.command**.
> It re-converts every script you've already imported with the improved importer
> (no copying again), adds the hand-rebuilt macros, and lists anything left to fix.


1. Double-click **Import From SoundFlow.command** and leave its window open.
2. In SoundFlow, open a script, click inside it, press **Cmd+A**, then **Cmd+C**.
3. The Import window notices the copy and asks for a name. Type it and press Return.
4. Copy the next script. Repeat until you're done, then close the window.

Each macro is saved in `my-deck/macros`, and the original script is kept in
`my-deck/soundflow-scripts`.

If a script calls another SoundFlow command (`sf.soundflow.runCommand`), it
becomes a `run macro:` step. The Import window lists these under
"Still needed", and suggests the first one as the name, so you only have to press Return.

Anything the importer doesn't understand becomes a `todo:` step. The macro
won't run until that step is fixed, so nothing is skipped by accident. Send me
the script if that happens.

> Macros made in SoundFlow's visual editor need converting first: use
> **Convert to Script** in SoundFlow, then copy.

## Manager

The Manager is a page in your web browser for seeing and changing everything:

- **Stream Deck view:** click a key to set its macro or folder, label, picture and
  colours. Drag one key onto another to swap them. Double-click a folder to open it.
  A red dot means the key's macro hasn't been imported yet; orange means it needs fixing.
- **Macros list:** every macro with its status (Working / Needs fixing / Not imported),
  whether it's on the deck, and buttons to **Edit** its steps or **Test** it.
  A test brings Pro Tools to the front and runs the macro; any error appears next to it.
- **Recent activity:** the last lines of `ptdeck.log`.

**Install update…** (top of the Manager): choose a PT Deck download (.zip). It installs
only PT Deck's own files, never your macros, layout or imported scripts, adds any new
folders to your deck, and restarts PT Deck.

It opens automatically at **http://localhost:8765** while PT Deck is running
(bookmark it), or double-click **Open Manager.command**. Changes are saved to
`my-deck/deck.yaml` and the Stream Deck updates within a second. It only works on this Mac.

## 3. Setting up the buttons

Edit **deck.yaml** in any text editor (TextEdit works; BBEdit or VS Code are
nicer). Save it, and the deck updates within a second. Instructions are at
the top of the file.

- Pages work like folders. A button with `folder: Mix` opens the page called `Mix`.
- Folder pages get a **Back** button on key 1 automatically.
- Icons are PNG files in `my-deck/icons`. Any size works; transparent backgrounds look best.
- **Check Macros.command** checks everything for mistakes and saves pictures
  of each page in `my-deck/previews`, so you can see the layout without the deck.

## 4. Step reference

Every step, option and key setting, how to add a macro and a key, and the rules that
keep macros reliable are in **[PTDECK_LANGUAGE_AND_RULES.md](PTDECK_LANGUAGE_AND_RULES.md)**.

A whole "colour selected tracks red" button is just:

```yaml
name: Colour Red
steps:
- track color: "#d03030"
```

## 5. When a Pro Tools update breaks something

1. Press the button. The Terminal shows which step failed and what it couldn't
   find, e.g. `stopped at step 4 (checkbox): checkbox 'HEAT Master Settings' not found`.
2. Open that dialog in Pro Tools and double-click **Pick Element.command**. Hover over
   the item within 4 seconds. It prints the item's current name and a step you can
   paste, plus the `click at` numbers for that spot.
3. If Avid renamed something used in many macros, fix all of them at once in Terminal:
   ```
   cd ~/Documents/ptdeck
   .venv/bin/python -m ptdeck rename "Old Name" "New Name"
   ```
   Add `--dry-run` to preview the change first.

To see everything inside a window: `.venv/bin/python -m ptdeck inspect "Import Session Data"`.
To test a macro without the deck: `.venv/bin/python -m ptdeck run "EAS Session Data" --delay 3`.

## 6. Not built yet

- **If/else logic and loops** (e.g. "for each selected track"). The importer
  marks those scripts as `todo`.
- More friendly SDK steps (mute, solo, hide, memory locations...). They all
  already work through `pro tools:` with a `body:`.
- Stream Deck+ dials and the touch strip (the keys work).
- Starting automatically at login.
