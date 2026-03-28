# my-ai-skills

Central repo for Claude and Codex skills/commands. Each subdirectory maps to a target location:

| Directory | Symlinked into |
|---|---|
| `claude-skills/` | `~/.claude/skills/` |
| `claude-commands/` | `~/.claude/commands/` |
| `codex-skills/` | `~/.codex/skills/` |

## Tools

- `./link.sh` — batch-create symlinks (`--dry` to preview, `--unlink` to remove)
- `./skill-selector.py` — interactive TUI for choosing what to link (run with `uv run skill-selector.py`)

## External repos

`~/p/my/agent-commit-command/` manages `commit.md` and `gdf-commit.md` for both Claude and Codex. Those are in the SKIP lists in `link.sh` and `skill-selector.py` — don't duplicate them here.

## Syncing after edits to ~/.claude or ~/.codex

If a skill/command is added or changed directly in `~/.claude/` or `~/.codex/` rather than here:

1. Copy or move the new/changed item into the appropriate subdirectory in this repo
2. Run `./link.sh` (or the TUI) to replace the original with a symlink
3. Commit

If both locations have diverged, diff them first (`diff -r`) and reconcile manually before linking.
