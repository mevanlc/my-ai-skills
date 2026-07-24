---
name: bgshells
description: Use when you need to find, audit, or clean up Claude Code background shells (Bash run_in_background) — especially after a context compaction, when the task ids and pids of already-launched background runs are gone from memory. The harness can read/stop/wait on a background task only once you have its id, and exposes no way to enumerate what's still running, so leaked waiters (a stuck `until … do sleep; done` poller, an orphaned test worker) accumulate invisibly. This lists live background shells by asking the OS which processes still hold a `<session>/tasks/*.output` file open, correlates each with its age/parent/command, and can kill the stale ones.
---

# bgshells

Claude Code streams every `Bash(run_in_background)` shell to
`<session-dir>/tasks/<taskid>.output`. You can `TaskStop <id>` / `TaskOutput <id>`
a background run **once you know its id** — but nothing surfaces the set of
still-running shells. After a compaction those ids and pids are lost, so this
recovers them from the OS side: a live process holding a `.../tasks/*.output`
open *is* a live background shell.

## Prefer the harness when you still have the id

If the task id is still in context, use the native tools — `TaskStop <id>` to
stop, `TaskOutput <id>` to read. Reach for this skill when you **don't** have the
id: post-compaction cleanup, or auditing what leaked over a long session.

## Helper location

The helper is bundled at `scripts/bgshells.sh` in this skill directory. Resolve
it once (claude-only skill, so it links under `~/.claude`):

```bash
BGSHELLS=~/.claude/skills/bgshells/scripts/bgshells.sh
```

## Usage

```bash
$BGSHELLS                 # list live background shells (PID PPID ELAPSED TASKID CMD)
$BGSHELLS stale 30m       # only those older than a duration (bare number = minutes)
$BGSHELLS kill <pid|taskid>...   # TERM then KILL specific shells
$BGSHELLS reap 30m        # dry-run: show everything older than 30m that reap would kill
$BGSHELLS reap 30m --yes  # actually kill the stale ones
$BGSHELLS help
```

- `list` shows the eval'd body of each shell (the shell-snapshot boilerplate is
  stripped), so a stuck waiter reads as e.g. `until grep -q 'Result:' …; do
  sleep 15; done` — you can see exactly what it's blocked on.
- `reap` is dry-run unless `--yes`, so it's safe to run first and eyeball.
- Only your own processes are inspected; task paths with spaces are unsupported
  (Claude session dirs don't contain spaces).

## Typical flow after a compaction

```bash
BGSHELLS=~/.claude/skills/bgshells/scripts/bgshells.sh
$BGSHELLS                 # what's actually still alive?
$BGSHELLS reap 30m        # preview the stale ones
$BGSHELLS reap 30m --yes  # clear them
```

## How it works (so you can do it by hand if the skill isn't linked)

```bash
# 1. Every background run's output persists here, keyed by task id:
ls -lat "$SESSION_DIR/tasks/"*.output
# 2. Which are still LIVE = which of those files a process still holds open:
lsof -nP -u "$(id -un)" | grep '/tasks/.*\.output'
# 3. Correlate a pid with ps, then TaskStop <id> or kill <pid>:
ps -o pid,ppid,etime,command -p <PID>
```

`lsof` on the tasks directory is the move that turns "which background shells
are still running?" from unanswerable into a one-liner — memory or no memory.
