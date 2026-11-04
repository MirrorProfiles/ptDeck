# PT Deck — what to bring over from this conversation

Every file below is in the snapshot folder next to this report, complete and final, at the same path as in your PT Deck folder. All of PT Deck's code, macros in rebuilt/, additions and generated pictures were created in this conversation, so every one is listed as **new** (nothing existed before it). 'fp' is a short fingerprint (SHA-1) so you can check whether your copy is identical: in Terminal, `shasum <file> | cut -c1-10`.

**Most likely missing on your Mac** (the in-app 'Install update' never copies them): `tools/make_icons.py`, the latest `tests/test_ptdeck.py`, `tests/fixtures/`, `.gitignore`. Everything else matches the last update I sent (2 Nov 12:41) if you installed it.

## 1. Code changes

| Path | New/changed | What it does | fp |
|---|---|---|---|
| `ptdeck/__init__.py` | new | Marks the ptdeck folder as a Python package. | 3184ad4f39 |
| `ptdeck/__main__.py` | new | Command line: start, menubar, make-app, install-update, run, import, check, inspect, probes, metric-names; applies additions; stops duplicate copies. | 55426f3c55 |
| `ptdeck/deck.py` | new | The Stream Deck itself: page layout, key drawing, title banners and Room 237 carpet, live insert/track-name keys, Metric keys, polling, self-reconnecting connection, mirror support. | 3ea0b0e538 |
| `ptdeck/look.py` | new | The 'designed' key style: Barlow fonts, the line-picture (glyph) library, AudioSuite strips, send strips, folder style, text fitting and size matching. | c44162edf6 |
| `ptdeck/macros.py` | new | Macro loading and every step action (menus, clicks, popups, plug-in windows, inserts, sends, bounce dialog, Metric A/B, hardware-insert scan, scrolling, presets, etc.). | 1236c50736 |
| `ptdeck/manager.py` | new | The Manager web server: deck editing, macros, install update, plug-in buttons/pictures, picture paste/URL, mirror endpoints, deck.yaml backups. | 74069084af |
| `ptdeck/manager.html` | new | The Manager web page: deck grid, inspector, macros, editor, importer, Mirror deck, Plug-in buttons window, plug-in picture picker, picture paste/drag. | 95398cf859 |
| `ptdeck/mac.py` | new | macOS layer: Accessibility elements, keys, mouse, scroll wheel, drag, paste, window capture (screencapture), text recognition (Vision). | 962b09f4c4 |
| `ptdeck/elements.py` | new | Finding Accessibility elements and windows by role/name/path. | c8b9b95472 |
| `ptdeck/keys.py` | new | Key names and modifier parsing (cmd+shift+n, semicolon, etc.). | 7ce32dd27b |
| `ptdeck/ptsl.py` | new | Pro Tools Scripting SDK (PTSL) client over gRPC, with reconnect, track list/colours, palette. | 25b85d548c |
| `ptdeck/ptsl_commands.py` | new | PTSL command name -> number table (from the 2026.04 SDK). | 64c1d4005d |
| `ptdeck/metric.py` | new | Metric A/B: slots, A/B, Sides/Match buttons and their click positions, song-name reading by picture + text recognition. | 40ee71476f |
| `ptdeck/menubar.py` | new | PT Deck as a menu bar app: PT Deck.app bundle, menu, permissions, open at login, install update. | 8a3c255b18 |
| `ptdeck/plugins.py` | new | Plug-in folder + Waves scan, name tidying, matching plug-ins to existing macros, 'Assign' macro writer. | 314d7afa2a |
| `ptdeck/soundflow.py` | new | Converts pasted SoundFlow scripts into PT Deck macros. | d8e73eeec9 |
| `ptdeck/settings.py` | new | Small remembered values in settings.json. | ab3d286c2a |
| `ptdeck/results.py` | new | Tested / not tested results (test-results.json). | ee99273cb7 |
| `ptdeck/proq.py` | new | Old Pro-Q 3 -> 4 converter (no longer used; you removed that macro). | 314dccc05a |
| `tools/make_icons.py` | new | Draws PT Deck's own pictures (title keys, folder art, route/marker/keycap/cabinetron, Beat Detective) at high resolution. | eeb12e5bc0 |
| `tests/test_ptdeck.py` | new | The automated tests (110), using fake Pro Tools windows. | 50dbddba16 |
| `tests/fixtures/eas-session-data.js` | new | Your SoundFlow Import Session Data script, used by a converter test. | de282ccc5a |
| `requirements.txt` | new | Python packages to install (adds pyobjc-framework-Vision for song names). | 4ebc668dd9 |
| `README.md` | new | How to install and use PT Deck (not updated for the latest features). | 43d86df16b |
| `.gitignore` | new | Keeps .venv, caches, logs, settings.json and test results out of git. | 1b654d053d |
| `Install.command` | new | Installs Python, the venv and packages, then makes PT Deck.app. | 75e1a66ce4 |
| `Start PT Deck.command` | new | Starts PT Deck in Terminal (deck + Manager). | 980fa195a0 |
| `Open Manager.command` | new | Opens the Manager in your browser. | 7e26125ff1 |
| `Import From SoundFlow.command` | new | Converts pasted SoundFlow scripts. | d8638827b4 |
| `Pick Element.command` | new | Shows what's under the mouse (for building macros). | 4368139ab3 |
| `Check Macros.command` | new | Checks every macro for problems. | a5f487d724 |
| `Update Macros.command` | new | Re-converts saved SoundFlow scripts with the latest importer. | 276141036a |
| `macros/example.yaml` | new | Example macro shipped with PT Deck. | 9cc17323e8 |

## 2. Macros, deck layout, additions and pictures

### rebuilt/ (macros written by hand for PT Deck — 118 files)

| Path | What it does | fp |
|---|---|---|
| `rebuilt/2025-import-session-data.yaml` | **2025 Import Session Data** — opens File > Import > Session Data and picks the template. | f5c2fab6c0 |
| `rebuilt/afl-x-or.yaml` | **AFL X-OR** — sets Pro Tools' solo mode (Options > Solo Mode). | 8a755c7d43 |
| `rebuilt/audio-files-folder.yaml` | **Audio Files Folder** — opens the current session's Audio Files folder in Finder. | b5ed4bf29e |
| `rebuilt/bd-tidy-up.yaml` | **BD Tidy Up** — Rebuilt for PT Deck from your SoundFlow script. With the drum tracks' edit selection: | 51f96faf35 |
| `rebuilt/bounce-mix-at-24-bit-and-rename-real-time.yaml` | **Bounce Mix at 24 Bit and Rename (Real-time)** — opens Bounce Mix and fills it in, then leaves it open for you to | bb8575403b |
| `rebuilt/bounce-mix-at-24-bit-and-rename.yaml` | **Bounce Mix at 24 Bit and Rename** — opens Bounce Mix and fills it in, then leaves it open for you to | a56b50d7a5 |
| `rebuilt/bounce-mix-at-32-bit-float-and-rename.yaml` | **Bounce Mix at 32 Bit Float and Rename** — opens Bounce Mix and fills it in, then leaves it open for you to | 6b1f3dd186 |
| `rebuilt/bounced-files-folder.yaml` | **Bounced Files Folder** — opens the current session's Bounced Files folder in Finder. | a2d4847e97 |
| `rebuilt/buffer-1024.yaml` | **Buffer 1024** — Setup > Playback Engine > H/W Buffer Size = 1024 samples, then OK. | b60abb3588 |
| `rebuilt/buffer-128.yaml` | **Buffer 128** — Setup > Playback Engine > H/W Buffer Size = 128 samples, then OK. | f2f5b54930 |
| `rebuilt/bypass-open-plugin.yaml` | **Bypass Open Plugin** — Bypasses (or un-bypasses) the plug-in window that's open, on any track (the front one if | 5e9891c4fd |
| `rebuilt/bypass-open-print-plugin.yaml` | **Bypass Open Print Plugin** — Bypasses (or un-bypasses) whichever plug-in window is open (any track, not just (PRINT)). | 51230c0267 |
| `rebuilt/clear-all-plugins-on-track.yaml` | **Clear All Plugins on Track** — removes every plug-in from the selected tracks. | 3d43893b7a |
| `rebuilt/clear-all-sends.yaml` | **Clear All Sends** — removes every send from the selected tracks. | 50e76f9da7 |
| `rebuilt/clip-gain-reduce-5db.yaml` | **Clip Gain - Reduce 5dB** — lowers the selected clips' clip gain by 5 dB. | 1b70f0ccb2 |
| `rebuilt/close-first-audiosuite-plugin.yaml` | **Close First AudioSuite plugin** — Rebuilt for PT Deck (replaces SoundFlow's Pro Tools package command) | 53c4a56fa3 |
| `rebuilt/colour-aux.yaml` | **Colour Aux** — colours the selected tracks (closest Pro Tools colour to #00495a). | dbaf0eac9f |
| `rebuilt/colour-bass.yaml` | **Colour Bass** — colours the selected tracks (closest Pro Tools colour to #240d46). | 2167139998 |
| `rebuilt/colour-drums.yaml` | **Colour Drums** — colours the selected tracks (closest Pro Tools colour to #4e0a00). | ea9c42d3a3 |
| `rebuilt/colour-fx.yaml` | **Colour FX** — colours the selected tracks (closest Pro Tools colour to #621662). | 0182bc1324 |
| `rebuilt/colour-gtrs.yaml` | **Colour Gtrs** — colours the selected tracks (closest Pro Tools colour to #004011). | 5679d58864 |
| `rebuilt/colour-synths.yaml` | **Colour Synths** — colours the selected tracks (closest Pro Tools colour to #610d0b). | 80cfe0ed59 |
| `rebuilt/colour-vocals.yaml` | **Colour Vocals** — colours the selected tracks (closest Pro Tools colour to #624200). | cc31d7d588 |
| `rebuilt/commit-edit-sel-offline-delete.yaml` | **Commit - Edit Sel - Offline - Delete** — Track > Commit with | 133c9f48ea |
| `rebuilt/commit-edit-sel-offline-do-nothing.yaml` | **Commit - Edit Sel - Offline - Do Nothing** — Track > Commit with | 553bc743a9 |
| `rebuilt/commit-edit-sel-offline-hide.yaml` | **Commit - Edit Sel - Offline - Hide** — Track > Commit with | 858e4e5cfd |
| `rebuilt/commit-edit-sel-realtime-delete.yaml` | **Commit - Edit Sel - Realtime - Delete** — Track > Commit with | 0614247e1b |
| `rebuilt/commit-edit-sel-realtime-do-nothing.yaml` | **Commit - Edit Sel - Realtime - Do Nothing** — Track > Commit with | a3626d7037 |
| `rebuilt/commit-edit-sel-realtime-hide.yaml` | **Commit - Edit Sel - Realtime - Hide** — Track > Commit with | 2066585be5 |
| `rebuilt/commit-entire-track-offline-delete.yaml` | **Commit - Entire Track - Offline - Delete** — Track > Commit with | 310ccf655e |
| `rebuilt/commit-entire-track-offline-do-nothing.yaml` | **Commit - Entire Track - Offline - Do Nothing** — Track > Commit with | 62262e4ea0 |
| `rebuilt/commit-entire-track-offline-hide.yaml` | **Commit - Entire Track - Offline - Hide** — Track > Commit with | 2a5635b792 |
| `rebuilt/commit-entire-track-realtime-delete.yaml` | **Commit - Entire Track - Realtime - Delete** — Track > Commit with | ed4fba4b50 |
| `rebuilt/commit-entire-track-realtime-do-nothing.yaml` | **Commit - Entire Track - Realtime - Do Nothing** — Track > Commit with | 7fd38ebcee |
| `rebuilt/commit-entire-track-realtime-hide.yaml` | **Commit - Entire Track - Realtime - Hide** — Track > Commit with | 6245e6bb5d |
| `rebuilt/commit-track.yaml` | **Commit Track** — Rebuilt for PT Deck (replaces SoundFlow's "Commit or Freeze up to Selected Insert"): | 7fa4360223 |
| `rebuilt/create-click-track.yaml` | **Create Click Track** — Rebuilt for PT Deck (replaces SoundFlow's Pro Tools package command) | 8e3a8ca38b |
| `rebuilt/delete-empty-audio-tracks-in-selection.yaml` | **Delete Empty Audio Tracks in Selection** — Rebuilt for PT Deck (uses the Pro Tools Scripting SDK) | 2579521184 |
| `rebuilt/duplicate-plugins-to-new-track.yaml` | **Duplicate Plug-ins to New Track** — Makes a new track with just the selected track's plug-ins (and their settings): Track > | ecb94698f2 |
| `rebuilt/edit-selection-down.yaml` | **Edit Selection Down** — Moves the Edit window's selection down a track (the ; key in Pro Tools). | cb2ad825eb |
| `rebuilt/edit-selection-up.yaml` | **Edit Selection Up** — Moves the Edit window's selection up a track (the P key in Pro Tools). | 6a91333547 |
| `rebuilt/file-save.yaml` | **File Save** — Rebuilt for PT Deck (uses the Pro Tools Scripting SDK) | ecbad02dd4 |
| `rebuilt/finder.yaml` | **Finder** — Macro: Finder | f15fea23dc |
| `rebuilt/import-io-setup-based-on-sample-rate.yaml` | **Import IO Setup based on Sample Rate** — imports your default I/O settings to match the session's sample rate. | 0c1e21d7b9 |
| `rebuilt/insert-1-toggle.yaml` | **Insert 1 Toggle** — opens/closes the plug-in window in insert 1 on the selected track. | 6488455025 |
| `rebuilt/insert-10-toggle.yaml` | **Insert 10 Toggle** — opens/closes the plug-in window in insert 10 on the selected track. | a1fbbe5c89 |
| `rebuilt/insert-2-toggle.yaml` | **Insert 2 Toggle** — opens/closes the plug-in window in insert 2 on the selected track. | 70243a26fa |
| `rebuilt/insert-3-toggle.yaml` | **Insert 3 Toggle** — opens/closes the plug-in window in insert 3 on the selected track. | 76ff347de0 |
| `rebuilt/insert-4-toggle.yaml` | **Insert 4 Toggle** — opens/closes the plug-in window in insert 4 on the selected track. | 2604f38f6a |
| `rebuilt/insert-5-toggle.yaml` | **Insert 5 Toggle** — opens/closes the plug-in window in insert 5 on the selected track. | f25f9f735d |
| `rebuilt/insert-6-toggle.yaml` | **Insert 6 Toggle** — opens/closes the plug-in window in insert 6 on the selected track. | 081e17d550 |
| `rebuilt/insert-7-toggle.yaml` | **Insert 7 Toggle** — opens/closes the plug-in window in insert 7 on the selected track. | 715e33a8a3 |
| `rebuilt/insert-8-toggle.yaml` | **Insert 8 Toggle** — opens/closes the plug-in window in insert 8 on the selected track. | cdec73c94d |
| `rebuilt/insert-9-toggle.yaml` | **Insert 9 Toggle** — opens/closes the plug-in window in insert 9 on the selected track. | ea2732bf24 |
| `rebuilt/low-latency-monitoring.yaml` | **Low Latency Monitoring** — Macro: Low Latency Monitoring | b55163d2e6 |
| `rebuilt/metric-loudness-match.yaml` | **Metric Loudness Match** — Toggles MetricAB's Loudness Match for the selected reference. | 1a47185a3c |
| `rebuilt/metric-match-all-references.yaml` | **Metric Match All References** — MetricAB's two-speaker button: matches the loudness of ALL references to your mix. | 32ef623f22 |
| `rebuilt/metric-sides.yaml` | **Metric Sides** — Toggles MetricAB's Sides (listen without the centre). | e25e485fde |
| `rebuilt/mono.yaml` | **Mono** — right-click each selected track > Change Track Width > Mono. | dc3365f070 |
| `rebuilt/nam.yaml` | **NAM** — Adds Waves StudioVerse Audio Effects (mono) to insert 2 of the selected track (or the first | 2f50c56516 |
| `rebuilt/new-comp-playlist.yaml` | **New .Comp Playlist** — new playlist on the selected tracks, renamed Kick.01 -> Kick.Comp | 81ff5a30bc |
| `rebuilt/new-playlist-from-comp-to-edit.yaml` | **New Playlist from .Comp to .Edit** — duplicates the playlist on the selected tracks, renamed Kick.Comp.01 -> Kick.Edit | b9d2408000 |
| `rebuilt/open-eas-cabs.yaml` | **Open EAS Cabs** — opens the EAS CABS impulse folder in Finder. | ce8e60963b |
| `rebuilt/open-fmusic.yaml` | **Open fMusic** — opens fMusic (stem export). | 0034d2d2b0 |
| `rebuilt/open-mix-bus-plugin-1.yaml` | **Open Mix Bus Plugin 1** — opens/closes insert 1 on the (PRINT) track, from the Edit or Mix window. | d56b97e161 |
| `rebuilt/open-mix-bus-plugin-10.yaml` | **Open Mix Bus Plugin 10** — opens/closes insert 10 on the (PRINT) track, from the Edit or Mix window. | a543dfeed0 |
| `rebuilt/open-mix-bus-plugin-2.yaml` | **Open Mix Bus Plugin 2** — opens/closes insert 2 on the (PRINT) track, from the Edit or Mix window. | f0c3fce4af |
| `rebuilt/open-mix-bus-plugin-3.yaml` | **Open Mix Bus Plugin 3** — opens/closes insert 3 on the (PRINT) track, from the Edit or Mix window. | 4d367ff4a5 |
| `rebuilt/open-mix-bus-plugin-4.yaml` | **Open Mix Bus Plugin 4** — opens/closes insert 4 on the (PRINT) track, from the Edit or Mix window. | 84075ea8ef |
| `rebuilt/open-mix-bus-plugin-5.yaml` | **Open Mix Bus Plugin 5** — opens/closes insert 5 on the (PRINT) track, from the Edit or Mix window. | a8b02416be |
| `rebuilt/open-mix-bus-plugin-6.yaml` | **Open Mix Bus Plugin 6** — opens/closes insert 6 on the (PRINT) track, from the Edit or Mix window. | e2cc27a2fd |
| `rebuilt/open-mix-bus-plugin-7.yaml` | **Open Mix Bus Plugin 7** — opens/closes insert 7 on the (PRINT) track, from the Edit or Mix window. | 440be9c587 |
| `rebuilt/open-mix-bus-plugin-8.yaml` | **Open Mix Bus Plugin 8** — opens/closes insert 8 on the (PRINT) track, from the Edit or Mix window. | 201fa58390 |
| `rebuilt/open-mix-bus-plugin-9.yaml` | **Open Mix Bus Plugin 9** — opens/closes insert 9 on the (PRINT) track, from the Edit or Mix window. | 39fe4fb695 |
| `rebuilt/rearrange-inserts-to-beginning.yaml` | **Rearrange inserts to beginning** — on each selected track, drags the plug-ins up into the | 1fd1a03961 |
| `rebuilt/remove-inactive-plugins-from-session.yaml` | **Remove Inactive Plugins From Session** — Removes inactive plug-ins and sends from every shown track in the session. | 4d13f4b4a4 |
| `rebuilt/remove-inactive-plugins.yaml` | **Remove Inactive Plugins** — Removes inactive plug-ins and sends from the selected tracks. | 9c39257978 |
| `rebuilt/remove-open-plugin.yaml` | **Remove Open Plugin** — Takes the plug-in whose window is open out of its insert slot ('no insert'). | 78023c0aff |
| `rebuilt/rename-to-c.yaml` | **Rename to .C** — duplicates the playlist on the selected tracks, renamed Kick.Edit.01 -> Kick.C | 99387afa0d |
| `rebuilt/save-as-1.yaml` | **Save As +1** — Rebuilt for PT Deck (uses the Pro Tools Scripting SDK) | ea89557df3 |
| `rebuilt/send-to-1-8-delay.yaml` | **Send to 1/8 DELAY** — adds a send to the //[1/8DLY] bus on the selected tracks (first free send). | 16135f8c63 |
| `rebuilt/send-to-chamber.yaml` | **Send to CHAMBER** — adds a send to the //[CHAMBER] bus on the selected tracks (first free send). | cce7b3bddc |
| `rebuilt/send-to-chorus.yaml` | **Send to CHORUS** — adds a send to the //[CHORUS] bus on the selected tracks (first free send). | 8a852319c7 |
| `rebuilt/send-to-flanger.yaml` | **Send to FLANGER** — adds a send to the //[FLANGER] bus on the selected tracks (first free send). | ca74bedecd |
| `rebuilt/send-to-h3000.yaml` | **Send to H3000** — adds a send to the //[H3000] bus on the selected tracks (first free send). | a132c0b62d |
| `rebuilt/send-to-nonlin.yaml` | **Send to NONLIN** — adds a send to the //[NONLIN] bus on the selected tracks (first free send). | a47041ce4d |
| `rebuilt/send-to-plate.yaml` | **Send to PLATE** — adds a send to the //[PLATE] bus on the selected tracks (first free send). | 9a07ced6b4 |
| `rebuilt/send-to-room.yaml` | **Send to ROOM** — adds a send to the //[ROOM] bus on the selected tracks (first free send). | bf35617d90 |
| `rebuilt/send-to-shimmer.yaml` | **Send to SHIMMER** — adds a send to the //[SHIMMER] bus on the selected tracks (first free send). | 8ee1a4c9ab |
| `rebuilt/send-to-slap-delay.yaml` | **Send to SLAP DELAY** — adds a send to the //[SLAPDLY] bus on the selected tracks (first free send). | 743aa5d6ff |
| `rebuilt/send-to-spring.yaml` | **Send to SPRING** — adds a send to the //[SPRING] bus on the selected tracks (first free send). | 9bf7949a23 |
| `rebuilt/send-to-voxverb.yaml` | **Send to VOXVERB** — adds a send to the //[VOXVERB] bus on the selected tracks (first free send). | bfc5afe5dd |
| `rebuilt/set-input-to-rme-l.yaml` | **Set Input to RME L** — sets the selected tracks' input to the RME's S/PDIF L side. | 95b2142c30 |
| `rebuilt/set-input-to-rme-r.yaml` | **Set Input to RME R** — sets the selected tracks' input to the RME's S/PDIF R side. | 8cef836c65 |
| `rebuilt/sip-latch.yaml` | **SIP Latch** — sets Pro Tools' solo mode (Options > Solo Mode). | 6e266361d8 |
| `rebuilt/sip-x-or.yaml` | **SIP X-OR** — sets Pro Tools' solo mode (Options > Solo Mode). | 6f0ac158ef |
| `rebuilt/slot-a1.yaml` | **Slot A1** — Picks reference slot A1 in MetricAB (column A, row 1) by setting the plug-in's own | 4b508547e0 |
| `rebuilt/slot-a2.yaml` | **Slot A2** — Picks reference slot A2 in MetricAB (column A, row 2) by setting the plug-in's own | bc70055bbc |
| `rebuilt/slot-a3.yaml` | **Slot A3** — Picks reference slot A3 in MetricAB (column A, row 3) by setting the plug-in's own | 8cb5d4938e |
| `rebuilt/slot-a4.yaml` | **Slot A4** — Picks reference slot A4 in MetricAB (column A, row 4) by setting the plug-in's own | cf481c4f55 |
| `rebuilt/slot-b1.yaml` | **Slot B1** — Picks reference slot B1 in MetricAB (column B, row 1) by setting the plug-in's own | 931a0cc703 |
| `rebuilt/slot-b2.yaml` | **Slot B2** — Picks reference slot B2 in MetricAB (column B, row 2) by setting the plug-in's own | f503e7b67a |
| `rebuilt/slot-b3.yaml` | **Slot B3** — Picks reference slot B3 in MetricAB (column B, row 3) by setting the plug-in's own | 2f5cce1c73 |
| `rebuilt/slot-b4.yaml` | **Slot B4** — Picks reference slot B4 in MetricAB (column B, row 4) by setting the plug-in's own | 47a91bed68 |
| `rebuilt/slot-c1.yaml` | **Slot C1** — Picks reference slot C1 in MetricAB (column C, row 1) by setting the plug-in's own | 3733dec1ee |
| `rebuilt/slot-c2.yaml` | **Slot C2** — Picks reference slot C2 in MetricAB (column C, row 2) by setting the plug-in's own | fd504f87df |
| `rebuilt/slot-c3.yaml` | **Slot C3** — Picks reference slot C3 in MetricAB (column C, row 3) by setting the plug-in's own | 3aa5fa2f94 |
| `rebuilt/slot-c4.yaml` | **Slot C4** — Picks reference slot C4 in MetricAB (column C, row 4) by setting the plug-in's own | 1a15ad22da |
| `rebuilt/slot-d1.yaml` | **Slot D1** — Picks reference slot D1 in MetricAB (column D, row 1) by setting the plug-in's own | 9a9178468d |
| `rebuilt/slot-d2.yaml` | **Slot D2** — Picks reference slot D2 in MetricAB (column D, row 2) by setting the plug-in's own | dfbe7a1598 |
| `rebuilt/slot-d3.yaml` | **Slot D3** — Picks reference slot D3 in MetricAB (column D, row 3) by setting the plug-in's own | 222c2d6441 |
| `rebuilt/slot-d4.yaml` | **Slot D4** — Picks reference slot D4 in MetricAB (column D, row 4) by setting the plug-in's own | 4f4890fbd5 |
| `rebuilt/stereo.yaml` | **Stereo** — right-click each selected track > Change Track Width > Stereo. | 1d1f4b6fec |
| `rebuilt/superior-drummer.yaml` | **Superior Drummer** — New track from your Track Preset INSTRUMENTS > SD3 (Track > New, type: Track Presets). | 469518e2e3 |
| `rebuilt/toggle-metric-a-b.yaml` | **Toggle Metric A/B** — Flips MetricAB's A/B switch on -OUT MASTER. If the window wasn't open, it's opened for a | 0944b0fc9c |
| `rebuilt/toggle-open-plugin-active.yaml` | **Toggle Open Plugin Active** — Makes the open plug-in window's plug-in inactive (or active again), whichever track it's on. | c4f41234bb |
| `rebuilt/toggle-tce-and-smart-tool.yaml` | **Toggle TCE and Smart Tool** — switches the Trim tool between Standard and TCE. | 88baced8ff |
| `rebuilt/tom-clean-bleed.yaml` | **Tom Clean Bleed** — Converted from your SoundFlow script: EQ3 7-Band "EAS Bleed Filter" via AudioSuite, then fades: | 367f78910b |

### additions/ (one-off changes PT Deck applies to your deck.yaml / macros, once each)

| Path | What it does | fp |
|---|---|---|
| `additions/audio-files-folder-key.yaml` | Bounce Mix: an Audio Files folder key beside Bounced Files - Folder. | e2a0568561 |
| `additions/beat-detective-icon.yaml` | The Beat Detective folder gets its new high-resolution detective picture. | f38916ce3b |
| `additions/beat-detective-keys.yaml` | Beat Detective page: the BD keys get a BEAT DETECTIVE strip (and lose the 'BD' prefix); | 9b6d827538 |
| `additions/bounce-24-auto-in-your-macro.yaml` | Your own copy of 'Bounce Mix at 24 Bit and Rename' still forced Offline: make it choose | 555895a425 |
| `additions/bounce-auto-labels.yaml` | Bounce Mix: the 'Offline' bounce keys now choose for themselves (Real-time if a hardware | 7b3d93662d |
| `additions/bounce-mix-page.yaml` | Tidied Bounce Mix page (replaces the page once; the top row shows the page name). | 8ea88a8716 |
| `additions/commit-tracks.yaml` |  | f5dfbc83dd |
| `additions/home-folder-icons.yaml` | Home: the main folders get pictures in the new style (old ones are in icons/classic). | fa03a98e5d |
| `additions/home-title.yaml` | Home: an EAS STUDIOS title across the top row (Overlook carpet, Black Lodge floor). | ce8265f201 |
| `additions/icon-style.yaml` | Switch on PT Deck's own key style (set 'icon style: classic' in deck.yaml for the old look). | 8b9338ab3e |
| `additions/metric-ab-more-keys.yaml` | Metric A/B: Sides and Loudness Match (light up when on) and Match All, under the A/B key. | 0f18067ba8 |
| `additions/metric-ab-page.yaml` | Metric A/B: all 16 reference slots as a 4x4 grid on the right (A-D across, 1-4 down). | 23264795a1 |
| `additions/metric-ab-toggle-key.yaml` | The Metric A/B toggle key shows which side is playing: a big A (orange) or B (dark). | 393ee67f4a |
| `additions/mix-bus-bypass-key.yaml` | Mix Bus: a key on the right that bypasses whichever (PRINT) plug-in window is open. | 19ec4e3c84 |
| `additions/mix-bus-live.yaml` | Makes the Open Mix Bus Plugin keys show what's on the (PRINT) track, live. | 3cabc7897a |
| `additions/mix-bus-page.yaml` | Mix Bus: the top half follows the SELECTED track, the bottom half the (PRINT) track. | cf9400ed4b |
| `additions/mixing-1-rename.yaml` | The Mix Bus page becomes 'Mixing' (it now covers the selected track as well as (PRINT)). | 141fde66f9 |
| `additions/mixing-2-keys.yaml` | Mixing: tools for the open plug-in window, down the right-hand side with Bypass: | 444287d08d |
| `additions/mixing-3-home-icon.yaml` | Home: the Mixing folder's picture says MIXING. | 102ba0bb5f |
| `additions/mixing-4-selection-keys.yaml` | Mixing: move the Edit window selection up / down a track (Pro Tools' P and ; keys). | d727704e95 |
| `additions/recording-keys.yaml` | Recording: new Cabinetron picture; Copy Track Data + Paste Inserts become one key that | 0535ae68f2 |
| `additions/solo-modes-icon.yaml` | Home: the SOLO MODES folder gets the Pro Tools solo-button picture. | aa4875466c |

### deck.yaml

Not included as a file to use: your Mac's deck.yaml is newer than any copy I have. All my layout changes reached it through the additions above (PT Deck applies each once and records it under 'additions applied'). The copy in `for-reference-only/` is your 1 Nov upload.

### icons/

| Picture(s) | What it is / how it was made |
|---|---|
| `icons/home-title-1.png … home-title-8.png` | EAS STUDIOS title row: your Black Lodge picture (icons/source/black-lodge.png) with a longer, darker curtain, letters in dark green with a soft neon outline. Made by tools/make_icons.py (lodge_title). |
| `icons/home-title-carpet-1.png … -8.png` | Earlier carpet version of the title (kept, unused). tools/make_icons.py (home_title). |
| `icons/folder-mix-prep.png / -mix-sends / -mix-bus / -mixing / -bounce-mix / -ampete / -solo-modes` | Folder art: folder outline with tab, a picture (checklist, three send-coloured knobs, VU meter, tape reels, amp head, yellow S solo buttons), name in Barlow Condensed caps. tools/make_icons.py (folder_frame + art_*). |
| `icons/beat-detective.png` | Noir detective with a magnifier over a drum transient, BEAT DETECTIVE strip. tools/make_icons.py. |
| `icons/cabinetron.png` | 2x2 speaker cabinet with gold CABINETRON nameplate. tools/make_icons.py. |
| `icons/route-drums.png, route-print.png` | Pro Tools-style output selector reading [DRUMS] / (PRINT). tools/make_icons.py. |
| `icons/renumber-markers.png` | Yellow numbered markers on a Markers ruler. tools/make_icons.py. |
| `icons/import-mix-template.png` | EAS .ptx session file. tools/make_icons.py. |
| `icons/copy-track-data.png, paste-inserts.png` | Keycaps C / V (Copy Track Data key now runs Duplicate Plug-ins; Paste Inserts key removed). tools/make_icons.py. |
| `icons/eas-track-colours.png` | Folder with your 7 track colours. tools/make_icons.py. |
| `icons/insert-1.png … insert-10.png` | 'Open (Toggle) / INSERT n' keys (no longer on the deck: the Mixing page uses live keys). |
| `icons/clip-gain-down-5.png` | Waveform with arrow and -5 dB (drawn in code earlier in the conversation). |
| `icons/classic/` | Your previous versions of the 8 replaced pictures (backup). |
| `icons/source/black-lodge.png, source/carpet-237.png` | Your uploaded images, used to build the title row and the top-row carpet. |
| `icons/fonts/Barlow*.ttf + Barlow-OFL.txt` | Barlow / Barlow Condensed fonts (SIL Open Font Licence) from Google Fonts. |
| `icons/plugins/README.txt` | Explains plug-in pictures (Manager > Plug-in buttons > Picture saves them here). |
| `icons/all other .png` | Your own pictures: cropped from your SoundFlow screenshots / uploads (not made by me). |

To recreate the generated pictures: `cd ~/Documents/ptdeck && .venv/bin/python tools/make_icons.py` (needs icons/source/ and icons/fonts/; it overwrites the generated files listed above).


## 3. Decisions and findings (not captured in a file)

**How Pro Tools 2026 behaves (and the workaround each needed)**
- Pop-up menus are separate windows; each submenu is a window inside its item. Pro Tools leaves invisible "ghost" menu windows behind, so a menu only counts as open if it's visibly on screen.
- Pressing a pop-up, menu item or some buttons through Accessibility can make macOS wait up to 3 seconds for Pro Tools to confirm. PT Deck therefore presses in the background and moves on after 0.6 s.
- Asking Pro Tools about the element you just clicked while its menu is open also stalls, so PT Deck checks the app's menu windows first.
- Pro Tools ignores text set in its dialog text boxes behind its back (Bounce name, Batch Rename, Scroll to Track). PT Deck clicks the box, selects all, pastes and checks instead.
- Return is never pressed in dialogs (it would click the default button, e.g. Bounce). Escape is only sent when PT Deck knows a menu of its own is open: a stray Escape cancelled the Bounce dialog once.
- Option+Shift (do it to all selected tracks) and Cmd+Ctrl (make inactive) only work with a real mouse click, not an Accessibility press. So those clicks need the slot on screen.
- For **inactive and bypassed** plug-ins, picking "no insert" behind Pro Tools' back is ignored. PT Deck falls back to real clicks: the slot, then "no insert".
- An inactive plug-in opens a small window that doesn't say which track or slot it's on. PT Deck remembers the slot from the insert key you pressed.
- With a plug-in window open, the insert slot only reports "open", not whether it's bypassed. PT Deck reads the window's Effect Bypass button instead (see section 5).
- Track headers are groups called "<name> - <type> Track". Each "Inserts A-E/F-J" group lists the 5 selectors first, then the 5 slot names.
- The Scroll to Track dialog was unreliable and slow. PT Deck now scrolls with the mouse wheel over the Edit window until the slot is in view, using the dialog only as a fallback.
- Hardware inserts are listed under **i/o** in an insert slot's menu. They appear on tracks by their I/O Setup name (e.g. RNC.L).
- Bounce Mix Mix Source names change with I/O Setup. After **Default I/O** your main output is "Analog 1-2 (Stereo)"; before, it was "Built-in Output 1-2 (Stereo)". Both are accepted.
- Metric A/B's settings (Selected Track, AB Switch, Stereo Mode, Loudness Match…) are readable, but Pro Tools ignores setting them directly, and stepping through slots flips A/B each step. So the slot, A/B, Sides and Match keys click the plug-in's own buttons. The positions are fractions of the plug-in area, measured from your screenshot. The song names aren't readable at all, so they're read from a window picture with text recognition.
- The PTSL scripting connection can go stale after opening a session or restarting Pro Tools. Read-only commands now reconnect and retry. Commands that change things only retry if the error is about the connection.
- PTSL has no commands for plug-ins, inserts or I/O lists. It does give track colours, used for the Mixing page colour bars.
- Saving with PTSL's SaveSessionAs crashes Pro Tools 2026 (an assertion). Save As +1 uses the keyboard and dialog instead.
- Waves plug-ins can't be listed from Pro Tools' plug-in folder (they're in WaveShells). The list comes from /Applications/Waves/Plug-Ins V*.
- Plug-in folder names differ from the names Pro Tools shows (iZotope, UADx…). The Mixing page records names as seen on your tracks.

**macOS / app**
- Only one program can drive the Stream Deck. SoundFlow's helper keeps running after you quit its window, so PT Deck waits and retries instead of quitting.
- PT Deck.app is a launcher for PT Deck's Python. macOS lists its permissions as **python3** (Accessibility, Screen Recording).
- Two PT Deck copies running at once caused the mixed-up pages. Starting PT Deck now stops any other copy.

**Choices made**
- The deck's look: 'icon style: designed' (Barlow fonts, glyph library, AudioSuite strip naming the plug-in, folders with tabs, auto text colour). `icon style: classic` in deck.yaml turns it off.
- The Metric A/B song keys went back to the system font (Barlow looked blurry there).
- Title row: Black Lodge style for EAS STUDIOS, toned-down neon. Folder pages: Room 237 carpet behind titles and in empty top-row keys (`title pattern: none` turns it off).
- The Mix Bus page was renamed to **Mixing**: the top half follows the selected track, the bottom half (PRINT). The track-colour bars and SELECTED name key come from Pro Tools.
- Copy Track Data and Paste Inserts became one key: Track > Duplicate with only Inserts ticked.
- The "Offline" bounce keys became **Auto**: Real-time if a hardware insert is active, otherwise Offline. If PT Deck can't tell, it chooses Real-time.
- Layout changes reach your deck.yaml only through additions/, applied once each and recorded under "additions applied". deck.yaml is backed up to backups/ before every change.
- Organisation of pages was left as yours (you asked to keep your muscle memory).

## 4. Unfinished work, and things I asked you to test

**Not started / open**
- **Your latest report:** after updating Pro Tools, macros that move between tracks feel slow compared with your keyboard shortcuts. Not investigated yet. Next step: paste the log for one of those presses, and say which keys/macros.

**Built but not yet confirmed on your Mac** (I asked you to test these)
- Auto bounce: the hardware-insert scan now reads fresh every time, and finds the track headers once per session (warmed up when the Bounce Mix page opens). Check it picks Real-time/Offline correctly and how quickly the dialog opens.
- Default I/O speed after the 0.6 s background presses.
- Active/Inactive and Remove Plug-in on (PRINT) with mouse-wheel scrolling.
- Remove Plug-in for inactive/bypassed plug-ins (the real-click fallback).
- Mixing page colours / SELECTED after opening another session (PTSL reconnect).
- Menu bar app: first run, Screen Recording permission for python3, Install Update from the menu, Open at Login.
- Superior Drummer (New Tracks > Track Presets > INSTRUMENTS > SD3). The dialog after picking a preset type was never seen.
- Duplicate Plug-ins to New Track.
- Metric A/B Sides / Loudness Match / Match All keys (click positions from your screenshot).
- Selection Up / Down keys (P and ;) on the Mixing page.
- RME inputs: SPDIF L/R.L / .R for mono tracks, SPDIF L/R (Stereo) for stereo tracks.
- Audio Files Folder key (Bounce Mix page, key 23).
- Plug-in buttons window: Sync, Waves listing, Make button, plug-in pictures.
- Tom Clean Bleed (EQ3 AudioSuite, Batch Fades / Crossfade): you said you'd test it more.

**Things that need you**
- **NAM:** `rebuilt/nam.yaml` still says `insert plugin: StudioVerse Audio Effects (mono)`. You said the "(mono)" made it fail and fixed it by hand. If you fixed it in `rebuilt/nam.yaml`, the next update will overwrite your fix. Remove "(mono)" in the repo copy, or keep your fix in `macros/`.
- README.md doesn't yet describe the newer features (menu bar app, Mixing page, plug-in tools, Metric keys).

## 5. Unsure / unconfirmed

- The hardware-insert detection relies on your hardware inserts being named the same on tracks as under i/o, and on the slot order (5 selectors then 5 names). It worked for RNC.L; **unconfirmed** for others.
- AudioSuite strip themes (RX / EQ3 / Pro-Q) are guessed from plug-in names. **Unconfirmed** beyond your RX and EQ3 keys.
- Manufacturer guesses in the Plug-in buttons window (e.g. "Universal Audio (UADx)", "Plugin Alliance") are guesses at Pro Tools' insert-menu folder names. **Unconfirmed.**
- Waves names come from the .bundle file names. **Unconfirmed** that they match the insert menu.
- That the plug-in window's Effect Bypass button reports "Selected" when bypassed (used to colour live keys while a window is open): a guess from your plug-in file, **unconfirmed**.
- That **Match All** (the two-speaker button) is a one-press action, not an on/off: assumed, **unconfirmed**.
- Metric A/B slot numbering (rows vs columns) is learned automatically. Assumed rows until learned.
- The Edit window wheel-scroll direction self-corrects. **Unconfirmed** with natural scrolling settings.
- Destructive keys forced to white CAPS text: suggested, never answered (not done). **Unconfirmed.**
- More keys redrawn to look like what they do (clip gain, buffer keys, AFL/SIP, Recording page photos): suggested, not done. **Unconfirmed.**
- A picture picker for glyphs in the Manager (choosing a key's line picture): suggested, not done. **Unconfirmed.**
- Organising the Home page by workflow: suggested, and you chose to keep your layout (agreed: not doing it).
