#!/usr/bin/env bash
#
# Symlink skills and commands from this repo into
# ~/.claude/ and ~/.codex/.
#
# Usage:
#   ./link.sh          # create symlinks (default)
#   ./link.sh --dry    # show what would be done without doing it
#   ./link.sh --unlink # remove symlinks (restore nothing; just unlink)
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
DRY=false
UNLINK=false

for arg in "$@"; do
  case "$arg" in
    --dry)    DRY=true ;;
    --unlink) UNLINK=true ;;
    *)        echo "Unknown arg: $arg"; exit 1 ;;
  esac
done

# Items managed by other repos (agent-commit-command, etc.) — skip these.
SKIP_CLAUDE_SKILLS=(macos-automation-skill)
SKIP_CLAUDE_COMMANDS=(commit.md gdf-commit.md)

is_skipped() {
  local name="$1"; shift
  for skip in "$@"; do
    [[ "$name" == "$skip" ]] && return 0
  done
  return 1
}

do_link() {
  local src="$1" dest="$2"

  if $UNLINK; then
    if [[ -L "$dest" ]]; then
      echo "unlink $dest"
      $DRY || rm "$dest"
    fi
    return
  fi

  # If dest is already a correct symlink, skip.
  if [[ -L "$dest" ]] && [[ "$(readlink "$dest")" == "$src" ]]; then
    echo "ok     $dest -> $src"
    return
  fi

  # If dest exists and is NOT a symlink, back it up.
  if [[ -e "$dest" ]] && [[ ! -L "$dest" ]]; then
    local backup="${dest}.bak.$(date +%s)"
    echo "backup $dest -> $backup"
    $DRY || mv "$dest" "$backup"
  elif [[ -L "$dest" ]]; then
    # Symlink exists but points elsewhere — remove it.
    echo "relink $dest"
    $DRY || rm "$dest"
  fi

  echo "link   $dest -> $src"
  $DRY || ln -s "$src" "$dest"
}

# --- Claude skills ---
echo "=== Claude skills ==="
mkdir -p ~/.claude/skills
for item in "$REPO"/claude-skills/*/; do
  name="$(basename "$item")"
  [[ "$name" == "skills" ]] && continue  # skip nested 'skills' dir if present
  is_skipped "$name" "${SKIP_CLAUDE_SKILLS[@]}" && continue
  do_link "$REPO/claude-skills/$name" "$HOME/.claude/skills/$name"
done

# --- Claude commands ---
echo "=== Claude commands ==="
mkdir -p ~/.claude/commands
for item in "$REPO"/claude-commands/*; do
  name="$(basename "$item")"
  is_skipped "$name" "${SKIP_CLAUDE_COMMANDS[@]}" && continue
  do_link "$REPO/claude-commands/$name" "$HOME/.claude/commands/$name"
done

# --- Codex skills ---
echo "=== Codex skills ==="
mkdir -p ~/.codex/skills
for item in "$REPO"/codex-skills/*/; do
  name="$(basename "$item")"
  do_link "$REPO/codex-skills/$name" "$HOME/.codex/skills/$name"
done

echo ""
echo "Done."
