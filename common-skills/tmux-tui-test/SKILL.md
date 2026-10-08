---
name: tmux-tui-test
description: Use when you need to launch, drive, or inspect a terminal UI or interactive CLI that requires a real TTY. Provides tmux command syntax, detached sessions, deterministic sizing, ordered input, text/style and raster captures, redraw waits, and clean teardown. Use for autonomous TUI testing and debugging or commands that break under plain stdout capture.
---

# Tmux TUI Test

Use the bundled harness for real-TTY testing. Operations shared with tmux use
its command names, flags, argument order, and targeting. Additional commands
provide synchronization, cell/style inspection, snapshots, and raster screenshots.
Consult `COMMAND --help` for the supported subset of tmux flags.

## Harness location

Resolve the harness and Freeze helper from this skill's `scripts/` directory:

```bash
if [ -f ~/.claude/skills/tmux-tui-test/scripts/tmux_tui_harness.py ]; then
  HARNESS=~/.claude/skills/tmux-tui-test/scripts/tmux_tui_harness.py
elif [ -f ~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py ]; then
  HARNESS=~/.codex/skills/tmux-tui-test/scripts/tmux_tui_harness.py
fi
FREEZE_EXEC="$(dirname "$HARNESS")/freeze_exec.sh"
```

## Differences from tmux

- The default server is private: `tmux -L tui-harness`. Its sessions are available
  for testing and cleanup without affecting the user's interactive server.
- Sessions are always detached; explicit `-d` is accepted. Names are generated
  when `-s` is omitted; default geometry is 120×40. The harness pins geometry
  with `window-size manual` and retains exited panes with `remain-on-exit`.
- Targets are explicit: pane, window, and session operations require `-t`.
  Reuse the returned `pane` ID to stay on the same pane even if focus changes.
- Results are JSON by default. `capture-pane -p` writes the exact tmux capture
  to stdout, including trailing newlines; errors go to stderr with nonzero status.
  Captures without `-p` do not create tmux paste buffers.
- Supported flags are listed in help; the harness is not a general command passthrough.

Global `-L LABEL` goes **before** the command and selects another server:

```bash
python3 "$HARNESS" -L my-test list-sessions
python3 "$HARNESS" -L my-test new-session -s demo -c /abs/project -x 120 -y 40 -- ./app
```

`--shared` selects the user's existing server and is mutually exclusive with
`-L`. Use it only when the user asks to inspect their actual sessions. Behave as
a guest: avoid killing sessions you did not create, resizing their windows, or
changing global options. `kill-server` requires `--i-am-sure` on `--shared` or
`-L default`; use that override only after the user explicitly confirms.

```bash
python3 "$HARNESS" --shared list-sessions
python3 "$HARNESS" --shared capture-pane -t their-session
```

## Quick start

Launch in the correct project directory with explicit dimensions:

```bash
python3 "$HARNESS" new-session -d -c /abs/project -x 120 -y 40 -- cargo run -- -g
```

Save `session` for lifecycle operations and `pane` for inspection/input. Examples
use `PANE` and `SESSION` as placeholders for those returned values.

```bash
python3 "$HARNESS" wait -t PANE --mode stable --timeout-ms 5000
python3 "$HARNESS" capture-pane -t PANE --number-lines --ruler
python3 "$HARNESS" send-keys -t PANE -l "query"
python3 "$HARNESS" send-keys -t PANE --wait stable --timeout-ms 3000 --plain Enter
python3 "$HARNESS" capture-pane -t PANE
python3 "$HARNESS" kill-session -t SESSION
```

Observation failures return status 2 with the last capture and a reason. Keep
any additional essential capture separate from a fallible wait; `wait &&
capture-pane` still suppresses that subsequent command on failure.

## Commands and targets

| Command | Supported tmux syntax / testing extensions |
| --- | --- |
| `new-session` (`new`) | `[-d] [-s NAME] [-c DIR] [-x WIDTH] [-y HEIGHT] [-e KEY=VALUE ...] [--] [shell-command [argument ...]]` |
| `send-keys` (`send`) | `-t TARGET [-l] [-N COUNT] [--pause-ms MS] [--wait MODE ...] [--] key ...` |
| `capture-pane` (`capturep`) | `-t TARGET [-e] [-J] [-N] [-S START] [-E END] [-p]`; JSON presentation flags below |
| `resize-window` (`resizew`) | `-t TARGET [-x WIDTH] [-y HEIGHT]`; at least one dimension |
| `kill-session` | `-t TARGET [--ignore-missing]` |
| `list-sessions` (`ls`) | List sessions on the selected server |
| `kill-server` | Tear down the selected server; shared-server guard above |
| `info`, `wait`, `mouse`, `cell`, `region`, `find-text`, `snapshot`, `diff`, `screenshot` | Harness inspection commands, all with `-t TARGET` |

Pane commands accept `SESSION`, `SESSION:WINDOW.PANE`, and `%ID`. A session
target selects its active pane, not its first pane. Window targets include
`SESSION:WINDOW` and `@ID`; session targets include names and `$ID`. Metadata
identifies the resolved session/window/pane and reports **pane** dimensions,
process state, cursor state, and mouse flags.

`new-session` follows tmux execution rules: one command argument is interpreted
by the shell, multiple arguments execute directly, and omission starts the
default shell. Repeat `-e KEY=VALUE` for session environment. `--` ends harness
option parsing before the command.

```bash
python3 "$HARNESS" new-session -c /abs/project -e MODE=test -e TERM=xterm-256color -- ./app --debug
python3 "$HARNESS" new-session -c /abs/project -- 'make build && exec ./app'
```

Input arguments are sent sequentially. Recognized key names become keys;
unrecognized strings become text. `-l` makes **every** argument literal, including
`Enter`. `-N` follows tmux's repeat semantics.

```bash
python3 "$HARNESS" send-keys -t PANE Down Down Enter
python3 "$HARNESS" send-keys -t PANE C-u "query" Enter
python3 "$HARNESS" send-keys -t PANE -N 3 Down
python3 "$HARNESS" send-keys -t PANE -l "Enter"
python3 "$HARNESS" send-keys -t PANE Enter --pause-ms 100
```

## Capture and coordinates

`capture-pane` returns plain text by default. `-e` includes ANSI attributes;
`-J` joins wrapped rows and preserves trailing spaces; `-N` preserves trailing
spaces without joining. Otherwise physical screen rows remain separate.

`-S` and `-E` select native tmux capture lines: **0 is the first visible row**,
negative values address scrollback, and endpoints are inclusive. `-S -` starts
at history's beginning; `-E -` ends at the visible bottom. The default captures
only the visible pane. These flags also work on other screen-capturing commands,
including `wait` and `screenshot`; on `diff` they apply to the current-screen
comparison when `--after` is omitted.

```bash
python3 "$HARNESS" capture-pane -t PANE -S -200
python3 "$HARNESS" capture-pane -t PANE -S -
python3 "$HARNESS" capture-pane -t PANE -S 0 -E 4 -e
python3 "$HARNESS" capture-pane -t PANE -pe -N
```

JSON presentation options have a separate coordinate system:

- `--lines` and `--cols` crop **one-based ranges within the captured result**.
- `--number-lines` and `--ruler` add targeting aids to `display_text`.
- `--repr` exposes control characters; `--tokens` includes parsed tokens.
- `text` reflects native flags unless an explicit JSON crop is requested.
- `-p` cannot be combined with those JSON presentation options.

Mouse, cell, region, and text-match coordinates are also one-based. The top-left
visible cell is row 1, column 1. History shifts coordinates within inspection
captures; use a fresh visible capture when targeting live input.

Coordinates count terminal cells, not Unicode codepoints. The harness queries
the selected tmux server's widths and accounts for combining characters, wide
glyphs, and tmux-combined emoji. `cell` reports `glyph`, `glyph_col`, `glyph_width`,
and `continuation`; a continuation cell has an empty `char`. Cropping through
only part of a wide glyph produces spaces for the clipped cells, not a displaced
or overhanging glyph. Text-match spans include every cell occupied by a match.

```bash
python3 "$HARNESS" capture-pane -t PANE --lines 15:17 --cols 1:60 --number-lines --ruler
python3 "$HARNESS" find-text -t PANE --text "main ↑1"
python3 "$HARNESS" mouse click -t PANE --text "main ↑1" --anchor center
python3 "$HARNESS" cell -t PANE --row 16 --col 6
python3 "$HARNESS" region -t PANE --rows 15:17 --cols 1:40 --styles --plain
```

## Synchronization, styles, and snapshots

For an input-driven transition, use `--wait` on `send-keys` or `mouse click`,
`scroll`, or `drag`. It captures a baseline **before** input, checks immediately
after the input sequence and any configured pause, then polls the same pane.
Standalone `wait --mode ...` uses the same observer but takes its baseline when
that command starts; use it for startup readiness, not to prove an earlier input
caused a redraw. These are harness extensions, not tmux's channel-based `wait-for`.

- `change`: require an observed difference from the baseline.
- `condition`: require the supplied text conditions, without a stability dwell.
- `stable`: require an unchanged region for `--stable-ms` (default 300), with any
  supplied conditions holding throughout that dwell.

Repeat `--expect-text TEXT` and `--expect-absent TEXT` for ANDed literal conditions
on plain text. `--lines`/`--cols` select the one-based observation region within
the capture; animation outside it does not reset stability. Comparisons include
styles unless `--plain` is supplied. The timeout defaults to 2000 ms and polling
to 100 ms; on input commands the timeout starts after input and its optional pause.

```bash
python3 "$HARNESS" send-keys -t PANE --wait condition --expect-text "Saved" --expect-absent "Saving…" C-s
python3 "$HARNESS" mouse click -t PANE --text "Search" --wait stable --expect-text "Results" --lines 3:18 --cols 1:70 --timeout-ms 5000
python3 "$HARNESS" send-keys -t PANE --wait change Down
python3 "$HARNESS" wait -t PANE --mode condition --expect-text "Ready" --timeout-ms 5000
```

An already-satisfied condition can succeed with `changed: false`; add
`--require-change` when a transition is required. A changed screen is not proof
of the intended outcome, and a quiet screen is not proof of readiness: supply
conditions for those claims. This samples screen state, not every redraw, and
does not establish causality or make input/capture atomic with the application.

Input results include an `observation` object; standalone `wait` returns its
fields at the top level. Both retain `baseline_text`, final `text`/`plain_text`,
`changed`, elapsed/stable times, and unmet conditions. Reasons are `satisfied`,
`timeout`, `pane-exited`, or `capture-error`; the latter includes error detail
and marks whether only baseline evidence survived. Unsatisfied observations
return status 2. A satisfied final condition can succeed even if the process
exits; otherwise input observations stop on exit. Plain standalone stability
waits can still inspect retained dead panes.

Inspect styles with `cell` or `region --styles`; check resolved foreground and
background values when reverse-video or selection matters. Regions and diff
previews preserve ANSI by default and accept `--plain`. Snapshots always preserve
styles independently of text presentation.

Snapshots are scoped to the resolved server instance and pane. Equivalent target
spellings access the same snapshots; other panes, servers, and restarted servers
cannot reuse them. Snapshots retain parsed cell data as well as ANSI text, so
diffs do not reinterpret saved glyph widths. Retake older snapshots that lack
cell data.

```bash
python3 "$HARNESS" snapshot -t PANE --name before
python3 "$HARNESS" mouse click -t PANE --text "main ↑1" --anchor center
python3 "$HARNESS" snapshot -t PANE --name after
python3 "$HARNESS" diff -t PANE --before before --after after --style-only --lines 15:17 --cols 1:40 --repr
```

Mouse commands emit SGR sequences; verify the app enables mouse reporting first.
`click` emits press/release, `scroll` emits wheel events, and `drag` emits
press/motion/release. Prefer text anchors and re-capture after input.

## Raster screenshots

When `freeze` is available on PATH, render and **open** a fresh PNG after each
feature or significant TUI code change. Writing an image alone does not validate
appearance. Repeat more often when iterating on layout, colors, glyphs, or spacing.
If Freeze is unavailable, continue with fresh text/style evidence and mention
missing raster validation when it matters; installation is not a prerequisite.

```bash
python3 "$HARNESS" screenshot -t PANE --output /absolute/path/pane.png
python3 "$HARNESS" screenshot -t PANE --output /absolute/path/pane.png --rasterizer chromium --scale 2
python3 "$HARNESS" screenshot -t PANE --output /absolute/path/pane.png --rasterizer rsvg-pdf
```

The harness captures ANSI with physical rows and trailing spaces preserved,
then uses `freeze_exec.sh` to select ANSI stdin explicitly. `rsvg-pdf` preserves
color emoji and requires `rsvg-convert` and `pdftocairo`. Use `--freeze-config NAME`
for another template. This re-renders captured ANSI, not an attached terminal's
pixels; fonts and renderer can affect glyph appearance. JSON includes the
absolute PNG path and renderer details.

To render an existing ANSI capture:

```bash
"$FREEZE_EXEC" -c terminal --rasterizer auto -o /absolute/path/pane.png < /absolute/path/pane.ansi
```

Set `FREEZE_BIN=/absolute/path/to/freeze` to select a particular installation.
Otherwise the helper resolves Freeze from PATH.

## Exit inspection and cleanup

- After a crash or exit, use `info -t PANE` to inspect `alive`, `exit_status`,
  and `exit_signal`, then `capture-pane -t PANE -S -200` for final output.
- Inspect focus, pane mode, and mouse flags before assuming input is broken.
- Capture failure output before restarting; verify `new-session -c` points at
  the correct project and keep dimensions fixed when comparing screens.
- Stop sessions in the same turn unless the user asks to keep them. Use
  `kill-session -t SESSION --ignore-missing` for stale-session cleanup.
- Prefer one TUI per session; use pane IDs when inspecting multiple panes.
  `list-sessions` and `kill-server` apply to the selected server only.

## Resources

- `scripts/tmux_tui_harness.py`: tmux-aligned CLI with JSON inspection and raw capture.
- `scripts/freeze_exec.sh`: ANSI stdin rendering helper.
- `scripts/test_tmux_tui_harness.py`: CLI, capture, target, lifecycle, snapshot,
  and screenshot coverage, including isolated tmux fixtures. Run with
  `uv run --no-project scripts/test_tmux_tui_harness.py`.
