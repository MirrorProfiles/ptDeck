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

Each macro is saved in the `macros` folder, and the original script is kept in
`soundflow-scripts`.

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
`deck.yaml` and the Stream Deck updates within a second. It only works on this Mac.

## 3. Setting up the buttons

Edit **deck.yaml** in any text editor (TextEdit works; BBEdit or VS Code are
nicer). Save it, and the deck updates within a second. Instructions are at
the top of the file.

- Pages work like folders. A button with `folder: Mix` opens the page called `Mix`.
- Folder pages get a **Back** button on key 1 automatically.
- Icons are PNG files in the `icons` folder. Any size works; transparent backgrounds look best.
- **Check Macros.command** checks everything for mistakes and saves pictures
  of each page in the `previews` folder, so you can see the layout without the deck.

## 4. Step reference

Every step starts with an action. The lines below it are settings.

| Action | What it does | Example |
|---|---|---|
| `activate:` | Brings Pro Tools to the front | `activate: Pro Tools` |
| `menu:` | Clicks a menu item | `menu: Track > New...` |
| `press:` | Keyboard shortcut(s) | `press: cmd+shift+n` or `press: cmd+a, return` |
| `type:` | Types text | `type: Lead Vox` |
| `wait:` | Pauses | `wait: 500ms` / `wait: 2s` |
| `wait for window:` | Waits for a window to open (add `gone: true` to wait for it to close) | `wait for window: New Tracks` |
| `wait for:` | Waits for a button, checkbox, etc. to appear (or `gone: true`) | |
| `click:` | Clicks a button, radio button, etc. by its name | `click: OK` |
| `checkbox:` | Turns a checkbox `on`, `off` or `toggle` (it checks first, so it never flips the wrong way) | `checkbox: Mic PRE Settings` + `set: off` |
| `popup:` | Picks from a pop-up menu | `popup: Format` + `choose: Stereo` |
| `set text:` | Fills in a text box | `set text: Name` + `to: Lead Vox` |
| `click at:` | **Click zone**: clicks a spot measured from a window's top-left | `click at: [120, 40]` + `window: main` |
| `raise window:` | Brings a Pro Tools window to the front | |
| `run macro:` | Runs another macro | `run macro: EAS Session Data` |
| `note:` | A comment; does nothing | |

### Steps that talk to Pro Tools directly

These use Avid's Pro Tools Scripting SDK instead of clicking through windows,
so a Pro Tools update won't break them, and they don't need Pro Tools in front.

| Action | What it does | Example |
|---|---|---|
| `track color:` | Colours tracks. Use a colour like `"#3366ff"` (the closest Pro Tools colour is used), a palette number, `none` or `default` | `track color: "#d03030"` |
| `select tracks:` | Selects tracks by name | `select tracks: Kick, Snare` |
| `pro tools:` | Any SDK command, with its settings under `body:` | `pro tools: SaveSession` |

| `save new version` | Saves, then Save As with the next number (Song.03 → Song.04) | |
| `delete empty audio tracks:` | Deletes selected audio tracks with no clips (`tracks: all` for every track) | |
| `bounce mix:` | Bounces with a name built from `{date}` `{session}` `{rate}` `{bits}`. Needs `source:` (the output name) | see `macros/bounce-mix-at-24-bit-and-rename.yaml` |

### Other steps

| Action | What it does | Example |
|---|---|---|
| `audiosuite:` | Opens an AudioSuite plug-in, wherever it is in the menu | `audiosuite: RX 11 De-click` |
| `audiosuite preset:` | Picks a preset in the open AudioSuite window | `audiosuite preset: EAS Default` |
| `audiosuite render` | Clicks Render and waits until it's finished | |
| `close window:` | Closes a window | `close window: "Audio*Suite*"` |
| `midi cc:` | Sends a MIDI CC (`value`, `channel`, `port`) | `midi cc: 80` + `value: 127` + `port: Maschine MK3` |
| `open:` | Opens a file, folder or app | `open: /Volumes/T7/Refs` |
| `quit app:` | Quits an app | `quit app: QuickTime Player` |

### Track steps (inserts, sends, routing)

These work on the **selected tracks** unless you add `track:` (one track) or `tracks:`.

| Action | What it does | Example |
|---|---|---|
| `plugin window:` | Opens/closes a plug-in window, by plug-in name or slot (1–10 / A–J). `set: toggle` (default), `open` or `close` | `plugin window: ADPTR MetricAB` + `track: "-OUT MASTER"` |
| `insert plugin:` | Adds a plug-in. `slot:` a number, a letter or `first free`. `category:` optional | `insert plugin: Cabinetron` + `slot: 10` |
| `send:` | Sets a send (`slot:` 1–10, or `first free`, the default) to a bus | `send: //[PARA DRUMS]` + `slot: 1` |
| `output:` / `input:` | Sets the track output / input | `output: (PRINT)` |
| `remove inactive:` | Removes inactive `plugins`, `sends` or `both` | `remove inactive: both` + `tracks: all` |
| `clear:` | Removes **all** `plugins`, `sends` or `both` | `clear: sends` |
| `bypass plugin:` | Bypasses / un-bypasses a plug-in (slot or name) | `bypass plugin: 1` |
| `toggle plugin active:` | Makes a plug-in active / inactive | `toggle plugin active: 10` |
| `open session folder:` | Opens a folder inside the session folder | `open session folder: Bounced Files` |
| `slider:` | Moves a plug-in control: `set: toggle`, `up`, `down` or a number | `slider: AB Switch` + `window: "Plug-in: ADPTR MetricAB"` |

With several tracks selected, `send:` and `output:` apply to all of them
(like holding Option+Shift in Pro Tools). Names are found anywhere in the
menu, so `send: //[PARA DRUMS]` works without the full `Stereo > bus >` path.

Add `app: com.apple.QuickTimePlayerX` (or another app's ID) to `menu:`, `click:`
and similar steps to use them in an app other than Pro Tools.

`track color:` colours the **selected** tracks unless you add `tracks:`, e.g.
`tracks: all` or `tracks: Kick, Snare`.

A whole "colour selected tracks red" button is just:

```yaml
name: Colour Red
steps:
- track color: "#d03030"
```

To see Pro Tools' colours with their numbers, run
`.venv/bin/python -m ptdeck colours`. To check the connection, run
`.venv/bin/python -m ptdeck test-pro-tools`. It shows the open session and the selected tracks.

Settings you can add to most steps:

- `window:` the window's title. `main` means the Edit/Mix window. Titles that
  start with the text also match, so `Edit:` finds `Edit: My Song`.
- `group:` the titled box the item sits in (like "Session Data"). Optional;
  use it when the same name appears more than once.
- `kind:` button, checkbox, radio button, popup, text field, slider…
  Optional; it narrows the search.
- `timeout:` how long to keep looking before giving up (default 5s; windows 15s).
- `optional: true` skips the step instead of stopping if the item isn't there.
  Handy for dialogs that only sometimes appear.
- `pause:` waits after this step, e.g. `pause: 200ms`.
- For `click at:` you can also use `double: true`, `button: right`, `modifiers: cmd+option`.
- Names can use `*` as a wildcard: `window: Edit: *`.

**Waiting is built in.** Each step keeps looking for its window or button for
a few seconds before giving up. You rarely need fixed `wait:` steps, and the
macros don't break when a dialog is slow to open.

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
