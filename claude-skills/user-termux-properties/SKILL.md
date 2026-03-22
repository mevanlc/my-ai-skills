---
name: user-termux-properties
description: Use when the user wants to edit, configure, or ask questions about their Termux terminal settings in ~/.termux/termux.properties. Covers extra-keys (focus), bell, back key, cursor, fullscreen, margins, and all other termux.properties settings.
version: 0.1.0
---

# Termux Properties Editor

## Target File

`~/.termux/termux.properties`

## Before Editing

1. **Read the current file** — always read `~/.termux/termux.properties` before making changes.
2. **Back up** — copy to `~/.termux/termux.properties.bak` (overwrite is fine; the directory is git-tracked).

## After Editing

Ask the user before running `termux-reload-settings`. Some changes require force-stopping the Termux app from Android settings.

## Source Code Reference

When you need to verify exact syntax, valid values, or behavior, read these files from the termux-app repo:

- **All property keys & valid values:**
  `~/p/gh/termux/termux-app/termux-shared/src/main/java/com/termux/shared/termux/settings/properties/TermuxPropertyConstants.java`

- **Extra-keys JSON parsing & syntax (key, macro, popup, display):**
  `~/p/gh/termux/termux-app/termux-shared/src/main/java/com/termux/shared/termux/extrakeys/ExtraKeysInfo.java`

- **Valid key names, aliases, and key code mappings:**
  `~/p/gh/termux/termux-app/termux-shared/src/main/java/com/termux/shared/termux/extrakeys/ExtraKeysConstants.java`

- **Macro execution & modifier handling (CTRL, ALT, SHIFT, FN, SLEEP):**
  `~/p/gh/termux/termux-app/termux-shared/src/main/java/com/termux/shared/termux/terminal/io/TerminalExtraKeys.java`

## Extra-Keys Quick Reference

### Format

The `extra-keys` value is a JSON array of arrays. Each inner array is one row of buttons. Use `\` for line continuation in the .properties file.

### Button Syntax

| Form | Tap action | Swipe-up (popup) action |
|------|-----------|------------------------|
| `KEY` | Sends KEY | (none) |
| `{key: 'KEY'}` | Sends KEY | (none) |
| `{key: 'KEY', popup: 'POPUP'}` | Sends KEY | Sends POPUP |
| `{key: 'KEY', popup: {macro: 'K1 K2', display: 'label'}}` | Sends KEY | Runs macro K1 then K2 |
| `{macro: 'K1 K2', display: 'label'}` | Runs macro | (none) |
| `{macro: 'K1 K2', display: 'label', popup: ...}` | Runs macro | Sends popup |

### Valid Key Names

Special keys: `ESC`, `TAB`, `HOME`, `END`, `PGUP`, `PGDN`, `INS`, `DEL`, `BKSP`, `UP`, `DOWN`, `LEFT`, `RIGHT`, `ENTER`, `SPACE`, `F1`-`F12`

Modifier keys: `CTRL`, `ALT`, `SHIFT`, `FN`

Special buttons: `KEYBOARD` (toggle soft keyboard), `DRAWER` (toggle session drawer), `PASTE`, `SCROLL`

### Key Aliases

These aliases are accepted: `ESCAPE`=`ESC`, `CONTROL`=`CTRL`, `RETURN`=`ENTER`, `BACKSPACE`=`BKSP`, `DELETE`=`DEL`, `PAGEUP`=`PGUP`, `PAGEDOWN`=`PGDN`, `BACKSLASH`=`\`, `QUOTE`=`"`, `APOSTROPHE`=`'`, `LT`=`LEFT`, `RT`=`RIGHT`, `DN`=`DOWN`

### Macros

- Space-separated sequence of keys: `{macro: "CTRL c", display: "C-c"}`
- Supports `SLEEP\d{1,4}` for delays: `{macro: "ESC SLEEP250 :wq ENTER", display: ":wq"}`
- A running sleep-macro is cancelled by any user input

### Display Styles (`extra-keys-style`)

Values: `default`, `arrows-only`, `arrows-all`, `all`, `none`

### Capitalize Labels (`extra-keys-text-all-caps`)

Values: `true` (default), `false`

## All Properties Quick Reference

### Boolean Properties (uncomment to enable)

| Key | Effect | Default |
|-----|--------|---------|
| `allow-external-apps` | Allow external apps to run commands in Termux | false |
| `disable-terminal-session-change-toast` | Suppress toast on session switch | false |
| `enforce-char-based-input` | Fix Samsung letter input issue | false |
| `extra-keys-text-all-caps` | Auto-capitalize extra key labels | true |
| `fullscreen` | Start in fullscreen mode | false |
| `use-fullscreen-workaround` | Fix fullscreen layout issues | false |
| `hide-soft-keyboard-on-startup` | Hide keyboard on app start | false |
| `ctrl-space-workaround` | Fix ctrl+space on some ROMs | false |
| `terminal-onclick-url-open` | Open URLs on click vs tap | false |
| `run-termux-am-socket-server` | Run am socket server at startup | true |

### String/Enum Properties

| Key | Values | Default |
|-----|--------|---------|
| `back-key` | `back`, `escape` | `back` |
| `volume-keys` | `virtual`, `volume` | `virtual` |
| `bell-character` | `vibrate`, `beep`, `ignore` | `vibrate` |
| `soft-keyboard-toggle-behaviour` | `show/hide`, `enable/disable` | `show/hide` |
| `terminal-cursor-style` | `block`, `underline`, `bar` | `block` |
| `night-mode` | `true`, `false`, `system` | `system` |
| `default-working-directory` | any path | `$HOME` |

### Numeric Properties

| Key | Range | Default |
|-----|-------|---------|
| `terminal-cursor-blink-rate` | 0, 100-2000 | 0 |
| `terminal-transcript-rows` | up to 50000 | 2000 |
| `terminal-margin-horizontal` | 0-100 (dp) | 3 |
| `terminal-margin-vertical` | 0-100 (dp) | 0 |
| `terminal-toolbar-height` | 0.4-3.0 (scale) | 1 |
| `delete-tmpdir-files-older-than-x-days-on-exit` | -1 to 100000 | 3 |

### Notes

- The user does NOT use a hardware keyboard — skip HW keyboard shortcut suggestions.
- The file uses Java `.properties` format. Lines starting with `#` are comments.
- After saving, `termux-reload-settings` applies most changes. Some (like `run-termux-am-socket-server`) require force-stopping the app.
