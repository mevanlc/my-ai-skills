#!/usr/bin/env bash
#
# Symlink skills from this repo into ~/.claude/, ~/.codex/, and ~/.gemini/antigravity-cli/.
#
# Usage:
#   ./link.sh          # create symlinks (default), then prune dead ones
#   ./link.sh --dry    # show what would be done without doing it
#   ./link.sh --unlink # remove symlinks (restore nothing; just unlink)
#   ./link.sh --prune  # only prune dead symlinks pointing into this repo
#   ./link.sh [--no-claude] [--no-codex] [--no-gemini]
#
# Pruning removes symlinks in ~/.claude/skills, ~/.codex/skills, and
# ~/.gemini/antigravity-cli/skills that point into this repo but whose target
# no longer exists (skill renamed or deleted).
#
set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
DRY=false
UNLINK=false
PRUNE_ONLY=false
NO_CLAUDE=false
NO_CODEX=false
NO_GEMINI=false
BACKUP_DIR="$REPO/.backups/$(date +%Y%m%d-%H%M%S)"

for arg in "$@"; do
  case "$arg" in
    --dry)        DRY=true ;;
    --unlink)     UNLINK=true ;;
    --prune)      PRUNE_ONLY=true ;;
    --no-claude)  NO_CLAUDE=true ;;
    --no-codex)   NO_CODEX=true ;;
    --no-gemini)  NO_GEMINI=true ;;
    -h|--help)    echo "Usage: ./link.sh [--dry] [--unlink] [--prune] [--no-claude] [--no-codex] [--no-gemini]"; exit 0 ;;
    *)            echo "Unknown arg: $arg"; exit 1 ;;
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

# Remove symlinks in $1 that point into this repo but whose target is gone.
prune_dir() {
  local dir="$1"
  [[ -d "$dir" ]] || return 0

  local link target
  for link in "$dir"/*; do
    [[ -L "$link" ]] || continue
    target="$(readlink "$link")"
    # Only touch links we manage (pointing into this repo).
    [[ "$target" == "$REPO"/* ]] || continue
    # -e follows the link: true means the target still exists.
    if [[ -e "$link" ]]; then continue; fi
    echo "prune  $link -> $target (missing)"
    $DRY || rm "$link"
  done
}

prune_all() {
  echo "=== Prune dead links ==="
  if ! $NO_CLAUDE; then
    prune_dir "$HOME/.claude/skills"
  fi
  if ! $NO_CODEX; then
    prune_dir "$HOME/.codex/skills"
  fi
  if ! $NO_GEMINI; then
    prune_dir "$HOME/.gemini/antigravity-cli/skills"
  fi
}

if $PRUNE_ONLY; then
  prune_all
  echo ""
  echo "Done."
  exit 0
fi

# --- Common skills (installed to Claude, Codex, and Gemini) ---
if ! $NO_CLAUDE || ! $NO_CODEX || ! $NO_GEMINI; then
  echo "=== Common skills ==="
  if ! $DRY && ! $UNLINK; then
    if ! $NO_CLAUDE; then mkdir -p ~/.claude/skills; fi
    if ! $NO_CODEX; then mkdir -p ~/.codex/skills; fi
    if ! $NO_GEMINI; then mkdir -p ~/.gemini/antigravity-cli/skills; fi
  fi
  for item in "$REPO"/common-skills/*/; do
    [[ -d "$item" ]] || continue
    name="$(basename "$item")"
    if ! $NO_CLAUDE; then
      do_link "$REPO/common-skills/$name" "$HOME/.claude/skills/$name"
    fi
    if ! $NO_CODEX; then
      do_link "$REPO/common-skills/$name" "$HOME/.codex/skills/$name"
    fi
    if ! $NO_GEMINI; then
      do_link "$REPO/common-skills/$name" "$HOME/.gemini/antigravity-cli/skills/$name"
    fi
  done
fi

# --- Claude-only skills ---
if ! $NO_CLAUDE && [[ -d "$REPO/claude-skills" ]]; then
  echo "=== Claude skills ==="
  for item in "$REPO"/claude-skills/*/; do
    [[ -d "$item" ]] || continue
    name="$(basename "$item")"
    [[ "$name" == "skills" ]] && continue  # skip nested 'skills' dir if present
    is_skipped "$name" "${SKIP_CLAUDE_SKILLS[@]}" && continue
    do_link "$REPO/claude-skills/$name" "$HOME/.claude/skills/$name"
  done
fi

# --- Codex-only skills ---
if ! $NO_CODEX && [[ -d "$REPO/codex-skills" ]]; then
  echo "=== Codex skills ==="
  for item in "$REPO"/codex-skills/*/; do
    [[ -d "$item" ]] || continue
    name="$(basename "$item")"
    do_link "$REPO/codex-skills/$name" "$HOME/.codex/skills/$name"
  done
fi

# --- Gemini-only skills ---
if ! $NO_GEMINI && [[ -d "$REPO/gemini-skills" ]]; then
  echo "=== Gemini skills ==="
  for item in "$REPO"/gemini-skills/*/; do
    [[ -d "$item" ]] || continue
    name="$(basename "$item")"
    do_link "$REPO/gemini-skills/$name" "$HOME/.gemini/antigravity-cli/skills/$name"
  done
fi

prune_all

echo ""
echo "Done."
