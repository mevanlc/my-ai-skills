---
name: tmux-tui-test
description: Use when Codex needs to launch, drive, or inspect a terminal UI or other interactive CLI that requires a real TTY. Covers detached tmux sessions, deterministic terminal sizing, key injection, text screen capture, redraw/stability waits, and clean teardown. Use for autonomous testing and debugging of TUIs, curses apps, full-screen CLIs, or any command that breaks under plain stdout capture.
---

# Tmux TUI Test

Use `tmux` as the TTY backend for interactive terminal apps. Prefer the bundled harness over ad hoc `tmux` commands so session lifecycle, captures, waits, targeting, diffs, and post-exit inspection stay consistent.

## Quick Start

1. Start the app in a detached session.

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py start --cwd /abs/project --width 120 --height 40 -- cargo run -- -g
```

2. Save the `session` value from the JSON response.

3. Wait for the first stable screen.

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py wait SESSION --mode stable --timeout-ms 5000
```

4. Read the current screen with line numbers and a ruler when you need targeting help.

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py read SESSION --plain --number-lines --ruler
```

5. Interact, then wait and read again.

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py send SESSION --literal "query"
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py wait SESSION --mode stable --timeout-ms 3000 --plain
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py read SESSION --plain
```

6. Stop the session when done.

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py stop SESSION
```

## What The Harness Returns

- `read` returns the rendered pane contents, not a screenshot and not a raw PTY transcript.
- `read` preserves ANSI escape codes by default so color and style state remain visible.
- Use `--plain` when you want stripped text that is easier to reason over.
- `read --lines`, `read --cols`, `--number-lines`, and `--ruler` help isolate and target specific cells.
- `read --repr` exposes control characters and ANSI escapes as visible text like `\x1b[44m`.
- `read --tokens` returns parsed text and ANSI tokens for the extracted region.
- `cell` returns the exact character and style state at one `row,col`, including `resolved_bg` and `resolved_fg`.
- `region --styles` returns a cropped block plus per-cell style objects.
- `find-text` returns row and column spans for matching text, which is useful before text-anchored mouse actions.
- `snapshot` saves the current screen for later comparison.
- `diff` compares snapshots or a snapshot against the current screen and supports `--style-only`.
- `info` returns pane metadata such as `width`, `height`, `pid`, `command`, `alive`, `dead`, cursor fields, pane mode, and tmux mouse flags.
- When the pane is dead, `info`, `read`, and `wait` include `exit_status` and `exit_signal` when tmux provides them.

## Fine-Grained Inspection Workflow

Use this order when you need exact style or selection-state evidence:

1. Use `read --plain --number-lines --ruler` to map the screen.
2. Use `find-text` when a stable text anchor exists.
3. Use `cell` or `region --styles` to inspect resolved colors or other style flags.
4. Save a `snapshot` before the interaction.
5. Interact with keyboard or mouse.
6. Save another `snapshot`.
7. Run `diff --style-only --repr` to isolate style-only changes such as selected-row backgrounds.

Example:

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py snapshot SESSION --name before
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py mouse click SESSION --text "main ↑1" --anchor center
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py snapshot SESSION --name after
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py diff SESSION --before before --after after --style-only --lines 15:17 --cols 1:40 --repr
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py cell SESSION --row 16 --col 6
```

## Mouse Input Model

- Mouse coordinates are 1-based pane coordinates: `row=1 col=1` is the top-left cell of the visible pane.
- The harness emits SGR mouse-reporting sequences, which modern TUIs commonly use.
- Use mouse commands only when the app has enabled terminal mouse support. Otherwise the app may ignore the events or interpret them as plain escape sequences.
- Re-read the screen after mouse input the same way you would after keyboard input.
- Use `find-text` or `read --plain --number-lines --ruler` before coordinate-based mouse input.
- Use text-targeted mouse input when a stable string exists instead of guessing columns.

## Command Notes

- `start`: Prefer a fixed size such as `120x40` so captures are repeatable. Always pass `--cwd` for the correct project root.
- `wait`: Use `--mode stable` after startup or after input. Use `--mode change` only when you want to detect any redraw relative to the capture taken at the start of `wait`.
- `wait --require-change`: Use only when a redraw is expected after the `wait` call begins. It will time out if the redraw already happened.
- `read`: Use `--history 200` to include recent scrollback. Use `--full-history` when the visible pane is insufficient.
- `read --lines 10:20 --cols 1:80`: Crop to the rows and columns you actually care about.
- `read --number-lines --ruler`: Best option when you are choosing exact `row,col` targets.
- `read --repr`: Best option when you need to inspect ANSI or control codes directly.
- `read --tokens`: Best option when you need a structured token stream instead of manual ANSI parsing.
- `cell`: Best option for one exact coordinate. Look at `resolved_bg` and `resolved_fg` when selection or focus is color-driven.
- `region --styles`: Best option when a whole row or pane header may have style changes.
- `find-text --text "...":` Use before text-targeted mouse input or when you need exact spans for a selected label.
- `mouse click`: Send a press and release at a single `row,col`, or use `--text "..." --anchor start|center|end`.
- `mouse scroll`: Send wheel events at a single `row,col`, or use `--text "..."` to scroll over a matched label or pane.
- `mouse drag`: Send press, motion, and release events from start to end coordinates. You can also use `--start-text` and `--end-text`.
- `snapshot`: Save a named screen state under the current session so `diff` can compare it later.
- `diff`: Compare named snapshots, or compare a named snapshot to the current screen by omitting `--after`.
- `diff --style-only`: Use when the text is unchanged but the style changed, such as focus borders or selected-row backgrounds.
- `resize`: Use only when layout coverage matters. Re-read after resizing because wrapping and pane balance will change.
- `stop`: Stop the session in the same turn unless the user explicitly wants it left running.

## Examples

### Cropped Read With Ruler

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py read SESSION --plain --lines 15:17 --cols 1:60 --number-lines --ruler
```

### Find Text Then Click It

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py find-text SESSION --text "main ↑1"
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py mouse click SESSION --text "main ↑1" --anchor center
```

### Inspect Selected-Row Background

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py cell SESSION --row 16 --col 6
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py region SESSION --rows 15:17 --cols 1:40 --styles --plain
```

### Compare Before/After Style State

```bash
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py snapshot SESSION --name before
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py send SESSION --literal 3
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py snapshot SESSION --name after
python3 ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py diff SESSION --before before --after after --style-only --repr
```

## Crash And Exit Handling

- The harness enables tmux `remain-on-exit`, so dead panes stay readable.
- After a crash or normal exit, call `info` first to confirm `alive: false`.
- Inspect `exit_status` and `exit_signal` instead of scraping only the `Pane is dead ...` footer text.
- Use `read --history 200` after exit to capture the final screen, panic, traceback, or stderr output.
- Stop the dead session after inspection so stale sessions do not accumulate.

## Failure Triage

- If the app appears not to react to keys, verify the expected focus before changing code.
- If the app appears not to react to mouse input, verify the app actually enables mouse mode.
- Call `info` to confirm the process is still alive, whether the pane is in tmux mode, and what cursor position tmux is reporting.
- Call `read --history 200` before restarting; the useful failure output is often just above the visible screen.
- Switch to `--plain` if ANSI-heavy output is making the capture hard to read.
- Switch to `--repr` when you need to inspect style codes directly.
- Use `find-text` before coordinate-based clicks if the screen content is still moving.
- Restart with a fixed size if the app layout depends on terminal dimensions.
- Confirm `--cwd` is correct before assuming the app itself is broken.

## Operating Rules

- Prefer the bundled harness over raw `tmux` subcommands.
- Prefer the default ANSI capture first. Use `--plain` only when you specifically want stripped text.
- Use `cell`, `region`, and `diff --style-only` before falling back to screenshots for selection-state questions.
- Do not add a screenshot path unless the task actually requires visual rendering rather than terminal style state.
- Keep one TUI per tmux session.
- Use fixed dimensions during debugging so diffs are meaningful.

## Resources

### scripts/

- `tmux_tui_harness.py`: JSON CLI wrapper around `tmux` for launching, inspecting, targeting, snapshotting, and diffing interactive terminal apps.
