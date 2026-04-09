#!/usr/bin/env bash
#
# Symlink skills from this repo into ~/.claude/ and ~/.codex/.
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
BACKUP_DIR="$REPO/.backups/$(date +%Y%m%d-%H%M%S)"

for arg in "$@"; do
  case "$arg" in
    --dry)    DRY=true ;;
    --unlink) UNLINK=true ;;
    *)        echo "Unknown arg: $arg"; exit 1 ;;
  esac
done

# Items managed by other repos (agent-commit-command, etc.) — skip these.
SKIP_CLAUDE_SKILLS=(macos-automation-skill)

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
    echo "backup $dest -> $BACKUP_DIR/$(basename "$dest")"
    $DRY || { mkdir -p "$BACKUP_DIR"; mv "$dest" "$BACKUP_DIR/"; }
  elif [[ -L "$dest" ]]; then
    # Symlink exists but points elsewhere — remove it.
    echo "relink $dest"
    $DRY || rm "$dest"
  fi

  echo "link   $dest -> $src"
  $DRY || ln -s "$src" "$dest"
}

# --- Common skills (installed to both Claude and Codex) ---
echo "=== Common skills ==="
mkdir -p ~/.claude/skills ~/.codex/skills
for item in "$REPO"/common-skills/*/; do
  name="$(basename "$item")"
  do_link "$REPO/common-skills/$name" "$HOME/.claude/skills/$name"
  do_link "$REPO/common-skills/$name" "$HOME/.codex/skills/$name"
done

# --- Claude-only skills ---
echo "=== Claude skills ==="
for item in "$REPO"/claude-skills/*/; do
  name="$(basename "$item")"
  [[ "$name" == "skills" ]] && continue  # skip nested 'skills' dir if present
  is_skipped "$name" "${SKIP_CLAUDE_SKILLS[@]}" && continue
  do_link "$REPO/claude-skills/$name" "$HOME/.claude/skills/$name"
done

# --- Codex-only skills ---
echo "=== Codex skills ==="
for item in "$REPO"/codex-skills/*/; do
  name="$(basename "$item")"
  do_link "$REPO/codex-skills/$name" "$HOME/.codex/skills/$name"
done

echo ""
echo "Done."
