# PT Deck language and rules

This is the complete reference for adding a macro (what a key does) and a key (where it
sits on the Stream Deck and how it looks). It's written so that someone, or an AI agent,
starting from nothing but this repository can do it correctly.

**Keep this file current.** `tests/test_ptdeck.py::test_language_and_rules_are_complete` fails
if any step, option, key setting, picture, addition type or command in the code is missing
from this guide. When you add a feature, document it here in the same change.

Contents:
1. [How PT Deck fits together](#1-how-pt-deck-fits-together)
2. [Adding a macro and a key: the process](#2-adding-a-macro-and-a-key-the-process)
3. [Macro files](#3-macro-files)
4. [Step reference](#4-step-reference)
5. [Options](#5-options)
6. [Keys and pages (deck.yaml)](#6-keys-and-pages-deckyaml)
7. [Additions: changing the layout by file](#7-additions-changing-the-layout-by-file)
8. [Rules and recommendations](#8-rules-and-recommendations)
9. [How Pro Tools behaves](#9-how-pro-tools-behaves)
10. [Commands](#10-commands)

---

## 1. How PT Deck fits together

PT Deck drives the Stream Deck itself (no SoundFlow, no Elgato app) and runs **macros**:
plain YAML lists of steps. It controls Pro Tools in three ways, in order of preference:

1. **The Pro Tools Scripting SDK (PTSL)**, over gRPC. Doesn't depend on window layout and
   survives Pro Tools updates. Used for track info, colours, selection, saving and more.
2. **macOS Accessibility**: finds buttons, menus, checkboxes and pop-ups by name and presses them.
3. **Real keyboard and mouse events**: shortcuts, and clicks at measured positions.

| Where | What |
|---|---|
| `ptdeck/` | The code. `macros.py` runs steps; `deck.py` draws keys and runs the deck; `look.py` is the key style; `manager.py` + `manager.html` are the Manager web page; `paths.py` says where things live |
| `my-deck/deck.yaml` | The layout: pages and keys |
| `my-deck/macros/` | Macros written or edited by the user, plus SoundFlow imports |
| `my-deck/rebuilt/` | Macros written for PT Deck (start with `# Rebuilt for PT Deck`) |
| `my-deck/additions/` | One-off layout changes, applied to deck.yaml once each |
| `my-deck/icons/` | Key pictures (PNG). `icons/plugins/` holds pictures named after plug-ins |
| `my-deck/soundflow-scripts/` | Original SoundFlow scripts kept from imports |
| `assets/fonts/` | Barlow fonts for the designed key style |
| `tools/make_icons.py` | Redraws the generated key pictures |

**Which macro wins.** Macros are looked up by name (the `name:` line, case-insensitive) or
by file name. A file in `macros/` overrides a file of the same name in `rebuilt/`, unless
it's an untouched SoundFlow import (`# Imported from SoundFlow`) or an old copy of the
rebuilt one (`# Rebuilt for PT Deck`). A user's edit of a rebuilt macro starts with
`# Edited by you (started from PT Deck's rebuilt version)` and always wins.

**Reloading.** Macros are re-read on every press, and deck.yaml within a second of saving.
Only Python changes need a restart (menu bar icon → Restart).

## 2. Adding a macro and a key: the process

1. **Check it doesn't already exist.** `.venv/bin/python -m ptdeck list`, and look in
   `my-deck/rebuilt/` and `my-deck/macros/`.
2. **Find the names Pro Tools uses.** Open the window in Pro Tools, then
   `.venv/bin/python -m ptdeck inspect "Window Title"` lists everything in it, or
   `.venv/bin/python -m ptdeck pick` describes whatever is under the mouse after 3 seconds
   and prints a step you can paste. Menu paths are as shown in Pro Tools' menu bar.
3. **Pick the most robust step** (see [rules](#8-rules-and-recommendations)): a PTSL or
   dedicated step first, then named elements, then shortcuts, and `click at` last.
4. **Write the file** `my-deck/macros/<name-in-lowercase-with-dashes>.yaml`:
   ```yaml
   # One line saying what it does and anything surprising about how.
   name: Colour Vocals
   steps:
   - track color: "#624200"
   ```
5. **Check it**: `.venv/bin/python -m ptdeck check` must not list it.
6. **Try it in Pro Tools**: `.venv/bin/python -m ptdeck run "Colour Vocals" --delay 3`
   (3 seconds to click into Pro Tools first). The log shows each step.
7. **Add the key** to a page in `my-deck/deck.yaml`, in an empty key:
   ```yaml
   - {key: 12, label: "Colour\nVocals", macro: Colour Vocals, color: '#624200', glyph: swatch}
   ```
8. **Preview it**: `.venv/bin/python -m ptdeck preview "Page Name"` saves
   `my-deck/previews/<page>.png`. Look at it.
9. **Run the tests** if any code changed: `.venv/bin/python -m pytest -q tests`.
10. **Commit** the macro and deck.yaml together, describing what the key does.

## 3. Macro files

```yaml
# Comment lines at the top describe the macro (shown nowhere, read by people).
name: Bounce Mix at 24 Bit and Rename      # what keys and run macro refer to
steps:
- activate: Pro Tools                      # each step: exactly one action...
- menu: File > Bounce Mix...
- wait for window: Bounce Mix
  timeout: 10s                             # ...plus any options, indented under it
- popup: File Type
  choose: WAV
  window: Bounce Mix
```

- A step is one action (`click:`, `menu:`...) with its value, plus options on the following
  lines. A step with two actions, or a word that's neither action nor option, is an error.
- Times can be `0.5`, `500ms` or `2s`.
- Names can use `*` and `?` wildcards. Titles also match by their start, so
  `window: Edit:` finds `Edit: My Song`.
- Text is matched against an element's title, then its description (and the text of
  static text).

## 4. Step reference

### Basics

| Step | What it does | Example |
|---|---|---|
| `activate:` | Brings Pro Tools to the front (does nothing if it already is) | `activate: Pro Tools` |
| `menu:` | Clicks a menu-bar item by path. `set: on/off` only clicks if the tick needs changing | `menu: Track > New...` |
| `press:` | Keyboard shortcut(s), comma-separated. `times:` repeats | `press: cmd+shift+n` / `press: cmd+a, return` |
| `type:` | Types text with key events | `type: Lead Vox` |
| `paste:` | Puts text on the clipboard and pastes it | `paste: Lead Vox` |
| `wait:` | Fixed pause (avoid; see rules) | `wait: 500ms` |
| `wait for window:` | Waits for a window (default 15 s). `gone: true` waits for it to close | `wait for window: New Tracks` |
| `wait for:` | Waits for an element to appear (or `gone: true`) | `wait for: OK` + `window: Bounce Mix` |
| `click:` | Presses a button, radio button etc. by name. `all: true` presses every match | `click: OK` |
| `checkbox:` | Sets a checkbox `on`, `off` or `toggle` (reads it first) | `checkbox: Offline` + `set: on` |
| `popup:` | Picks from a pop-up menu. `choose:` can be a path `A > B` | `popup: Format` + `choose: Stereo` |
| `set text:` | Fills a text box. Pro Tools dialogs need `typing: true` | `set text: Name` + `to: Lead Vox` + `typing: true` |
| `click at:` | Clicks `[x, y]` measured from a window, element or the screen (`relative to:`) | `click at: [120, 40]` + `window: main` |
| `raise window:` | Brings a Pro Tools window to the front | `raise window: Mix:` |
| `close window:` | Closes a window with its close button | `close window: "Audio*Suite*"` |
| `if window:` | Waits briefly (default 3 s) for a window; runs `then:` steps if it appears, else `else:` steps. `or:` lists other windows that mean "no" straight away | see below |
| `if menu:` | Runs `then:` steps if a menu-bar item is ticked, else `else:` steps. `ticked: false` flips it; `ticked: any` asks whether the item exists at all. Uses the tick the deck believes first (see `lit menu`) | see below |
| `accept dialog:` | If a small dialog appears within `timeout` (default 2 s), accepts it. Nothing happens otherwise | `accept dialog:` |
| `run macro:` | Runs another macro (up to 10 deep) | `run macro: EAS Session Data` |
| `note:` | A comment; does nothing | `note: needs the Edit window` |
| `todo:` | Marks a step still to write; stops the macro with that message | `todo: drag inserts up` |

```yaml
- if window: Batch Fades
  or: Fades
  then:
  - click: OK
  else:
  - note: no fades needed

- if menu: Options > Solo Mode > AFL*          # a toggle: AFL on → SIP, otherwise → AFL
  then:
  - menu: Options > Solo Mode > SIP*
  else:
  - menu: Options > Solo Mode > AFL*
```

### Pro Tools Scripting SDK (no window clicking)

| Step | What it does | Example |
|---|---|---|
| `track color:` / `track colour:` | Colours tracks by palette position: a number (1 = the first swatch; `ptdeck colours` shows them), `none` or `default`. A `"#hex"` also works (nearest colour in this Mac's palette) | `track color: 54` |
| `select tracks:` | Selects tracks by name (`all`, or a comma list) | `select tracks: Kick, Snare` |
| `pro tools:` | Any SDK command by name, settings under `body:` | `pro tools: SaveSession` |
| `save new version` | Saves, then Save As with the next number (Song.03 → Song.04) | `save new version:` |
| `delete empty audio tracks:` | Deletes selected audio tracks with no clips (`tracks: all` for every one) | |
| `bounce mix:` | Bounces with a name from `{date}` `{session}` `{rate}` `{bits}`. `source:` (output name), `source type:` (default Output), `bits:`, `sample rate:` (default session), `folder:` (default session) | `bounce mix: "{date}_{session}_EASMIX_{rate}_{bits}"` + `source: Analog 1-2` |

### Tracks, inserts, sends, routing

These work on the **selected tracks** unless `track:` (one) or `tracks:` (several, or `all`) says otherwise.

| Step | What it does | Example |
|---|---|---|
| `plugin window:` | Opens/closes a plug-in window by name or slot (1–10 / A–J). `set: toggle` (default), `open`, `close` or `restore` (close only what this press opened). `if empty: choose plug-in` opens the empty slot's menu to type into | `plugin window: 3` + `if empty: choose plug-in` |
| `insert plugin:` | Adds a plug-in. `slot:` number, letter, `first free`, or `2 or first free`. `category:` optional | `insert plugin: Cabinetron` + `slot: 10` |
| `plugin preset:` | Picks a preset from Pro Tools' preset (Librarian) menu in the open plug-in window. `Folder > Preset` works | `plugin preset: EAS NAM` |
| `bypass plugin:` | Bypasses / un-bypasses a plug-in by slot or name (Cmd-click) | `bypass plugin: 1` |
| `toggle plugin active:` | Makes a plug-in inactive / active (Cmd-Ctrl-click) | `toggle plugin active: 10` |
| `bypass open plugin:` | Presses Bypass in the open plug-in window for that track (the front one if several). Empty value: any track | `bypass open plugin: (PRINT)` |
| `toggle open plugin active:` | Makes the open plug-in inactive (or active again). With no window open, works on the last plug-in that had one | `toggle open plugin active:` |
| `remove open plugin:` | Takes the open plug-in out of its slot ("no insert") | `remove open plugin:` |
| `send:` | Sets a send (`slot:` 1–10, default `first free`) to a bus, found anywhere in the menu | `send: //[PARA DRUMS]` |
| `output:` / `input:` | Sets track output / input. `input:` takes `stereo:` for the name stereo tracks use | `output: (PRINT)` |
| `remove inactive:` | Removes inactive `plugins`, `sends` or `both` (default) | `remove inactive: both` + `tracks: all` |
| `clear:` | Removes **all** `plugins`, `sends` or `both` | `clear: sends` |
| `compact inserts:` | Moves each track's plug-ins up into the earliest empty slots, keeping their order | `compact inserts:` |
| `track menu:` | Right-clicks each selected track's name and picks from its menu | `track menu: Change Track Width > Mono` |
| `new track preset:` | Track > New, type Track Presets, picks category and preset, then Create | `new track preset: INSTRUMENTS > SD3` |
| `open session folder:` | Opens a folder inside the session folder in Finder | `open session folder: Bounced Files` |

With several tracks selected, `send:` and `output:` apply to all of them, as Option+Shift
would. `output:` sets the first track through its menu and copies to the rest with the SDK.

### Setup and dialogs

| Step | What it does | Example |
|---|---|---|
| `set buffer size:` | Setup > Playback Engine > H/W Buffer Size, then OK | `set buffer size: 128` |
| `import io settings:` | Imports an I/O settings file picked by the session's sample rate | `import io settings: {44100: /path/a.pio, 48000: /path/b.pio}` |
| `bounce dialog:` | Opens Bounce Mix and fills it in (`name:`, `source:`, `bits:`, session rate, `offline:` on / off / `auto`), then leaves it open. `click bounce: true` also clicks Bounce | `bounce dialog:` + `offline: auto` |
| `toggle tce trim:` | Switches the Trim tool between Standard and TCE, keeping Smart mode | `toggle tce trim:` |
| `convert pro-q 3 to 4:` | Old converter (no longer on the deck). `scope:` and `scale:` options | |

`offline: auto` bounces in real time if any hardware insert is active, otherwise offline;
if it can't tell, real time.

### AudioSuite

| Step | What it does | Example |
|---|---|---|
| `audiosuite:` | Opens an AudioSuite plug-in wherever it sits in the menu | `audiosuite: RX 11 De-click` |
| `audiosuite preset:` | Picks a preset in the open AudioSuite window | `audiosuite preset: EAS Default` |
| `audiosuite render:` | Clicks Render and waits until done. `processing: clip by clip` or `entire selection` | `audiosuite render:` |

### Plug-in controls and MetricAB

| Step | What it does | Example |
|---|---|---|
| `slider:` | Moves a plug-in control: `set: toggle`, `up`, `down` or a number | `slider: AB Switch` + `window: "Plug-in: ADPTR MetricAB"` |
| `metric slot:` | Picks a MetricAB reference slot (A1–D4) by clicking it (window must be open) | `metric slot: B2` |
| `metric ab:` | Clicks MetricAB's A/B button: `toggle`, `A` or `B` | `metric ab: toggle` |
| `metric button:` | Clicks `sides`, `match` or `match all` and checks it changed | `metric button: sides` |

### Other apps and hardware

| Step | What it does | Example |
|---|---|---|
| `open:` | Opens a file, folder or app | `open: /Volumes/T7/Refs` |
| `quit app:` | Quits an app | `quit app: QuickTime Player` |
| `midi cc:` | Sends a MIDI CC: `value:` (default 127), `channel:` (default 1), `port:` | `midi cc: 80` + `value: 127` + `port: Maschine MK3` |

## 5. Options

| Option | Used with | Meaning |
|---|---|---|
| `window:` | most | Window title (wildcards and start-of-title match). `main` = the Edit/Mix window |
| `group:` | most | A titled box the element sits in, when a name appears twice |
| `path:` | most | Containers to search through in order (a list, each `kind name`), down to the element |
| `kind:` | most | Narrows the element type: button, checkbox, radio button, popup, text field, slider… |
| `timeout:` | most | How long to keep looking (default 5 s; windows 15 s) |
| `optional:` | any | `true`: skip the step instead of stopping if it fails |
| `pause:` | any | Wait after this step |
| `app:` | element steps | Another app's bundle id, e.g. `com.apple.QuickTimePlayerX` |
| `set:` | checkbox, menu, plugin window, slider | Target state (`on` / `off` / `toggle` / `open` / `close` / `restore` / `up` / `down` / number) |
| `choose:` | popup | Item (or `A > B` path) to pick |
| `to:` | set text | The text |
| `typing:` | set text | Click into the box and type (needed in Pro Tools dialogs) |
| `times:` | press | Repeat count |
| `gone:` | wait for, wait for window | Wait for it to disappear instead |
| `all:` | click | Press every match |
| `mouse:` | click and plug-in steps | Use a real mouse click instead of an Accessibility press |
| `button:` | click at | `right` for a right-click |
| `double:` | click at | Double-click |
| `modifiers:` | click at | Keys held during the click, e.g. `cmd+option` |
| `relative to:` | click at | `window` (default), `element` or `screen` |
| `element:` | click at | The element to measure from |
| `then:` / `else:` / `or:` | if window, if menu | Steps to run / other windows meaning "no" |
| `ticked:` | if menu | `true` (default), `false`, or `any` (the item just has to exist) |
| `track:` / `tracks:` | track steps | Which tracks (default: selected) |
| `slot:` | insert plugin, send | Slot number, letter or `first free` |
| `all selected:` | track steps | Written by the SoundFlow importer; accepted but has no effect (track steps already cover all selected tracks) |
| `category:` | insert plugin | Plug-in menu category |
| `if empty:` | plugin window | `choose plug-in`: open the empty slot's menu |
| `stereo:` | input | Input name for stereo tracks |
| `source:` / `source type:` | bounce mix, bounce dialog | What to bounce |
| `bits:` / `sample rate:` / `folder:` / `name:` | bounce mix, bounce dialog | File settings |
| `offline:` | bounce dialog | `true`, `false` or `auto` |
| `click bounce:` | bounce dialog | Also click Bounce |
| `keep window:` | none | Accepted for older macros; has no effect |
| `processing:` | audiosuite render | `clip by clip` or `entire selection` |
| `body:` | pro tools | SDK command settings |
| `value:` / `channel:` / `port:` | midi cc | MIDI settings |
| `scope:` / `scale:` | convert pro-q 3 to 4 | Old converter settings |

## 6. Keys and pages (deck.yaml)

```yaml
brightness: 70
model: xl                 # mini, original, mk2, xl, plus, neo
home: Home                # the page shown at start
icon style: designed      # PT Deck's key style; 'classic' for plain keys
pages:
  Home:
  - {key: 1, label: Mix Prep, folder: Mix Prep, icon: folder-mix-prep.png}
  - {key: 2, label: "Colour\nDrums", macro: Colour Drums, color: '#4e0a00'}
```

Keys are numbered from 1 at top-left, left to right (an XL has 8 per row, 32 in all).
Pages other than home get a back key on key 1 automatically, and a page-title banner
across the empty top-row keys.

Deck-wide settings: `brightness`, `model`, `home`, `icon style`, `key font` (any installed font by name, for
keys that don't set `font`), `page settings` (see below), `back button` (true/false),
`back label`, `back color`, `back font size`, `page titles` (true/false),
`title pattern` (`none` turns off the carpet behind titles), `additions applied`
(kept by PT Deck; don't edit).

`page settings` gives single pages their own values for `back button`, `back label`, `back color`,
`back font size`, `page titles`, `title pattern`, `icon style` and `key font`, so one deck can mix
plain pages with designed ones:

```yaml
page settings:
  Main: {page titles: false, icon style: classic, key font: Futura PT Medium}
```

### Key settings

| Setting | Meaning |
|---|---|
| `key` | Position, 1 = top-left |
| `label` | Text; `\n` for a new line |
| `macro` | Macro to run (by name) |
| `folder` | Page to open (makes the key a folder) |
| `back` | `true`: this key goes back a page |
| `home` | `true`: this key goes to the home page |
| `icon` | PNG in `my-deck/icons`. With no label it fills the key |
| `glyph` | A line picture drawn by PT Deck (list below) |
| `color` | Background, e.g. `'#204060'` |
| `text color` | Label colour (default: white or black, whichever reads better) |
| `font size` | Label size in pixels |
| `font` | `narrow` for the condensed font, or any installed font by its Font Book name (e.g. `Futura PT Medium`). Found through macOS like an app's font menu, so Adobe Fonts and font managers work; if that exact font isn't installed, the same family with fewer words is tried (`Futura PT Medium` → `Futura PT` → `Futura Medium` → `Futura`) and the log says which was used; a name with no match at all is logged once and the standard font is used |
| `outline` | Outline colour, or `none` (folders get one by default) |
| `style` | Force the designed look: `command` or `send` |
| `strip` | Text on a band along the bottom naming the tool (e.g. `BEAT DETECTIVE`) |
| `strip color` | That band's background colour |
| `strip text color` | That band's text colour |
| `audiosuite` | Name of the AudioSuite plug-in, for the AudioSuite look (normally found from the macro) |
| `color bar` | `true`: track-colour stripe along the top |
| `palette color` | A Pro Tools track-colour number (as `track color:` takes and the `colours` chart shows): the key shows that exact colour once PT Deck has read Pro Tools' palette; `color` is shown until then |
| `gradient` | Background blended left to right through a list of colours, e.g. `['#1b3fae', '#e0242a']` (classic look) |
| `lit menu` | A menu-bar path (`View > Clip > Name`): the key shows its lit look while that item is ticked. A list of paths lights only when every one is ticked (e.g. `['Options > Solo Mode > AFL*', 'Options > Solo Mode > X-OR*']`; in the Manager, join them with ` + `). The deck follows ticks its own keys change straight away, and re-reads Pro Tools every few seconds |
| `lit when` | Values PT Deck remembers that must all match for the key to light, e.g. `{buffer size: 128}`. `buffer size` is recorded by `set buffer size:` steps (Pro Tools can't report it otherwise), so a change made in Pro Tools itself shows after the next buffer key press. Can be combined with `lit menu` |
| `lit color` | Background while lit |
| `lit label` | Label while lit (default: the normal label) |
| `lit text color` | Label colour while lit |
| `lit outline` | Outline colour while lit; use it on picture keys, where a lit background is hidden by the picture |
| `corner` | Small label top-left (live insert keys use the slot letter) |
| `live` | Insert slot 1–10 to show live: plug-in name and state (active, bypassed, inactive, open) |
| `live track` | Track for `live`: a name, `selected`, or `(PRINT)` (default) |
| `live name` | Shows a track's name live: `selected` or a name |
| `if empty` | Accepted on keys but has no effect; put `if empty:` in the macro's `plugin window:` step instead |
| `metric` | MetricAB slot (A1–D4): shows its song name and lights when selected |
| `metric ab` | `true`: shows MetricAB's A/B state |
| `metric toggle` | MetricAB toggle to show lit: `sides` or `match` (the label defaults to SIDES / LOUDNESS MATCH) |
| `note` | A comment |

**Glyphs:** ab, arrow-down, arrow-up, bolt, bounce, breath, buffer, commit, comp, copy,
crossfade, eq, eye, fade, flag, folder, gear, grid, headphones, import, mic, mono,
mono-stereo, paste, play, playlist, plug, plus, power, route, save, scissors, send,
speaker, spectrum, stereo, stereo-mono, stretch, swatch, target, text, transient,
trash, waveform, window.

Plug-in pictures: a PNG in `my-deck/icons/plugins/` named exactly as Pro Tools shows the
plug-in (e.g. `UADx Manley Massive Passive EQ.png`) appears on live insert keys.

## 7. Additions: changing the layout by file

A YAML file in `my-deck/additions/` is applied to deck.yaml **once** (recorded under
`additions applied` by file name), when PT Deck installs an update or runs
`ptdeck update`. Use one when a layout change has to reach a deck you can't edit directly;
on this Mac, editing deck.yaml is simpler. Each file starts with a comment saying what it
changes. Types, by their first key:

| First key | Does |
|---|---|
| `add to page:` + `buttons:` | Adds keys to an existing page, **only into empty keys** |
| `update buttons on:` + `buttons:` | Finds keys on a page by `macro:` (or `folder:`) and applies `set:` (settings to change), `remove:` (settings to drop) or `delete: true` |
| `rename page:` with `from:` / `to:` | Renames a page and every folder key pointing at it |
| `settings:` | Deck-wide settings, e.g. `icon style: designed` |
| `fix macro:` + `replace:` | Replaces lines in one of the user's own macros (`{old line: new line}`) |
| `page:` + `buttons:` | A whole page. Replaces an existing page only if `version:` is higher than last applied. `keep others:` (true) keeps the user's keys the new layout doesn't use (minus any in `replaces:`); `link:` (`page`, `key`, `button`) also puts a folder key on another page |

```yaml
# Mixing: move the Edit window selection up / down a track.
add to page: Mixing
buttons:
- {key: 24, label: "Selection\nUp", macro: Edit Selection Up, color: '#3a3f46', glyph: arrow-up}
```

## 8. Rules and recommendations

**Layout**
- Don't move or rename existing keys or pages unless asked: the user works from muscle memory.
  Put new keys in empty keys.
- Destructive keys (remove, delete, clear) are dark red (`'#6d0b0a'`) and go away from
  everyday keys (e.g. bottom right). Neutral tool keys use `'#3a3f46'`.
- Preview every page you change.

**Macros**
- New macros go in `my-deck/macros/`. Hand-written ones that replace a SoundFlow script go
  in `my-deck/rebuilt/` starting with `# Rebuilt for PT Deck`.
- Never leave an empty or placeholder macro: a file in `macros/` hides the `rebuilt/` macro
  of the same name. (An empty "Audio Files Folder" did exactly that.)
- Don't edit a user's macro marked `# Edited by you`; it is theirs.
- Start each file with a comment saying what it does and why any odd step is there.
- `name:` should match the key's purpose; the file name is that name in lowercase with dashes.

**Choosing steps**
- Colour tracks by palette number (`track color: 54`), not hex: a number picks the same swatch
  position on every Mac, even where palettes are customised, so colour keys stay shareable.
- Prefer an SDK or dedicated step over clicking through windows, then named elements,
  then shortcuts. `click at:` is a last resort; it breaks when windows move.
- Don't use fixed `wait:` steps. Every step waits for its window or element; use
  `wait for window:` / `wait for:` when you need to wait for something specific.
- Never `press: return` to confirm a Pro Tools dialog: it clicks the default button
  (e.g. Bounce). Click the named button, or use `accept dialog:` for a dialog that's expected.
- Never press Escape unless a menu PT Deck opened itself is showing: a stray Escape
  cancelled a Bounce dialog.
- Text boxes in Pro Tools dialogs need `typing: true`.
- Option+Shift (all selected tracks) and Cmd+Ctrl (inactive) only work with a real click
  (`mouse: true`), and the slot must be on screen.
- Use `optional: true` for dialogs that only sometimes appear.

**Code (new step types and live keys)**
- A new step needs: its word in `ACTIONS` (and new options in `OPTIONS`) in
  `ptdeck/macros.py`, a branch in `Runner.do`, a test in `tests/test_ptdeck.py` using the
  fake Pro Tools, and a row in this guide.
- A new key setting needs: its word in `BUTTON_FIELDS` in `ptdeck/deck.py`, drawing code,
  and a row in section 6.
- Anything that reads Pro Tools repeatedly (live keys, polling) must stay light: Pro Tools
  answers Accessibility requests on the thread that handles the user's keys and mouse.
  Remember what you found, re-check with one request, never search a whole window or retry
  for seconds on every poll, and leave Pro Tools alone for a moment after a key press.
- Waiting for a Pro Tools button press to confirm can block for up to 3 seconds; PT Deck
  presses in the background and moves on after 0.6 s (`PRESS_WAIT`).
- Paths come from `ptdeck/paths.py` (`APP`, `DATA`, `ASSETS`); don't build them from `__file__`.

**Before committing**
- `.venv/bin/python -m ptdeck check`: no new problems.
- `.venv/bin/python -m pytest -q tests`: all pass.
- Python changes: restart PT Deck and try the key in Pro Tools.
- Never commit `settings.json`, `test-results.json`, `backups/`, `previews/` or logs
  (`.gitignore` covers them).

## 9. How Pro Tools behaves

Learned the hard way; each has a workaround in the code.

- Pop-up menus are separate windows, and each submenu is a window inside its item. Pro
  Tools leaves invisible "ghost" menu windows behind, so a menu only counts as open if it's
  visibly on screen.
- Asking about an element while its menu is open stalls; PT Deck checks the app's menu
  windows first.
- Pro Tools ignores text set in its dialog text boxes behind its back (Bounce name, Batch
  Rename, Scroll to Track): click the box, select all, paste, then check.
- For inactive and bypassed plug-ins, choosing "no insert" behind Pro Tools' back is
  ignored; PT Deck falls back to real clicks.
- An inactive plug-in opens a small window that doesn't say its track or slot.
- With a plug-in window open, the insert slot only says "open"; the window's Effect Bypass
  button says whether it's bypassed ("Selected" when on).
- Track headers are groups named `<name> - <type> Track`. Each "Inserts A-E/F-J" group lists
  the 5 selectors first, then the 5 assignment buttons.
- Scroll to Track is slow and unreliable; PT Deck scrolls the Edit window with the mouse
  wheel instead.
- Hardware inserts are under **i/o** in an insert slot's menu and appear on tracks by their
  I/O Setup name (e.g. RNC.L).
- Bounce Mix source names change with the I/O Setup ("Analog 1-2 (Stereo)" after Default I/O,
  "Built-in Output 1-2 (Stereo)" before).
- MetricAB's settings can be read but setting them is ignored, so keys click its own buttons
  at measured positions. Song names are only readable from a window picture (text recognition).
- A tick in a closed menu can lag behind a change a key just made (seen while building CHP), so the deck
  remembers ticks its own menu steps changed and only lets a re-read override that when the re-read itself
  changes. Items in a `… Mode` submenu are pick-one **within their group**: Solo Mode has two groups split by
  a separator (SIP / AFL / PFL and Latch / Momentary / X-OR), so X-OR unticks Latch but not AFL. The deck
  reads the groups from the menu once; if it can't, it forgets the other items' ticks rather than guessing.
- Fonts switched on through Adobe Fonts live in a hidden Creative Cloud folder under meaningless file names, so
  key fonts are looked up through macOS (CoreText) first, then by scanning the font folders.
- Sending a character with Option held can type a different character (Option + minus types "–") instead
  of triggering the shortcut; PT Deck's `press:` sends physical key codes, which is right.
- Track colour numbers start at 1: `SetTrackColor` N applies the Nth colour of the palette list
  (`COLOUR_BASE` in `ptdeck/ptsl.py`). Until Nov 2026 PT Deck counted from 0, so its hex colour keys
  landed one swatch early; the Colour keys now name the numbers they were actually applying.
- The PTSL connection can go stale after opening a session or restarting Pro Tools;
  read-only commands reconnect and retry.
- PTSL has no commands for plug-ins, inserts or I/O lists. Its SaveSessionAs crashes Pro Tools
  2026, so Save As uses the keyboard and dialog.
- Waves plug-ins can't be listed from the plug-in folder (they're inside WaveShells); the
  list comes from `/Applications/Waves/Plug-Ins V*`.
- Only one program can drive the Stream Deck. SoundFlow's helper keeps running after its
  window is closed, and it also queries Pro Tools; quit it fully.

## 10. Commands

Run from the PT Deck folder as `.venv/bin/python -m ptdeck <command>`.

| Command | Does |
|---|---|
| `start` | Runs the deck in Terminal |
| `menubar` | Runs the deck from the menu bar (what PT Deck.app runs) |
| `make-app` | Rebuilds PT Deck.app |
| `manager` | Opens the Manager web page |
| `run "Name" --delay 3` | Runs one macro now |
| `list` | Lists macros |
| `check` | Checks every macro and deck.yaml for mistakes |
| `preview [page]` | Saves pictures of pages to `my-deck/previews` |
| `import` | Converts a SoundFlow script (clipboard or .js file; `--watch` keeps importing) |
| `update` | Re-converts imported scripts and applies additions |
| `rename "Old" "New"` | Replaces a name in every macro (`--dry-run` first) |
| `pick` | Describes whatever is under the mouse |
| `inspect "Window"` | Lists everything inside a Pro Tools window |
| `probe-menu` / `probe-tools` / `probe-plugin` | Describe an open pop-up menu / the toolbar tools / a plug-in window |
| `metric-names` | Reads MetricAB's song names now |
| `colours` | Shows Pro Tools' track colours with their numbers |
| `test-pro-tools` | Checks the SDK connection (open session, selected tracks) |
| `pro-tools` | Sends one SDK command |
| `install-update file.zip` | Installs a PT Deck download |

Tests: `.venv/bin/pip install -r requirements-dev.txt` once, then `.venv/bin/python -m pytest -q tests`.
