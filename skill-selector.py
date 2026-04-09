#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "textual>=3.0",
#   "pyyaml>=6.0",
# ]
# ///
"""TUI for selecting which skills to symlink from this repo."""

import os
from pathlib import Path

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Label, SelectionList
from textual.widgets.selection_list import Selection


REPO = Path(__file__).resolve().parent
BACKUP_DIR = REPO / ".backups"

CLAUDE_SKILLS = Path.home() / ".claude" / "skills"
CODEX_SKILLS = Path.home() / ".codex" / "skills"

# (display label, source subdirectory, list of destination directories)
CATEGORIES = [
    ("Common Skills", "common-skills", [CLAUDE_SKILLS, CODEX_SKILLS]),
    ("Claude Skills", "claude-skills", [CLAUDE_SKILLS]),
    ("Codex Skills", "codex-skills", [CODEX_SKILLS]),
]

# Items managed by other repos — don't touch these.
SKIP = {
    "claude-skills": {"macos-automation-skill"},
}


def get_description(path: Path) -> str:
    """Extract the description from YAML frontmatter of a skill."""
    if path.is_dir():
        path = path / "SKILL.md"
    if not path.is_file():
        return ""
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return ""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(text[3:end])
                if isinstance(fm, dict) and fm.get("description"):
                    # Collapse multiline YAML strings to single line
                    return " ".join(str(fm["description"]).split())
            except yaml.YAMLError:
                pass
    # Fallback: first non-empty line of content
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("---") and not stripped.startswith("#!"):
            return stripped
    return ""


def get_items(category: str) -> list[tuple[str, str]]:
    """Return (name, description) pairs for items in a category."""
    src_dir = REPO / category
    if not src_dir.exists():
        return []
    items = []
    for entry in sorted(src_dir.iterdir()):
        name = entry.name
        if name.startswith("."):
            continue
        if name in SKIP.get(category, set()):
            continue
        desc = get_description(entry)
        items.append((name, desc))
    return items


def is_linked(category: str, name: str, dest_dirs: list[Path]) -> bool:
    src = (REPO / category / name).resolve()
    return all(
        (d / name).is_symlink() and (d / name).resolve() == src
        for d in dest_dirs
    )


def apply_link(category: str, name: str, dest_dirs: list[Path]) -> None:
    src = REPO / category / name
    for dest_dir in dest_dirs:
        dest = dest_dir / name
        dest_dir.mkdir(parents=True, exist_ok=True)
        if dest.is_symlink():
            if dest.resolve() == src.resolve():
                continue
            dest.unlink()
        elif dest.exists():
            from datetime import datetime
            ts_dir = BACKUP_DIR / datetime.now().strftime("%Y%m%d-%H%M%S")
            ts_dir.mkdir(parents=True, exist_ok=True)
            dest.rename(ts_dir / dest.name)
        dest.symlink_to(src)


def remove_link(category: str, name: str, dest_dirs: list[Path]) -> None:
    src = (REPO / category / name).resolve()
    for dest_dir in dest_dirs:
        dest = dest_dir / name
        if dest.is_symlink() and dest.resolve() == src:
            dest.unlink()


def build_selections() -> list[Selection]:
    """Build selections with category headers on their own rows."""
    try:
        term_width = os.get_terminal_size().columns
    except OSError:
        term_width = 80
    # SelectionList chrome: 2 border + 1 padding + 4 checkbox+space ≈ 7 cols
    avail = term_width - 7

    # Find the longest item name across all categories for alignment.
    all_items = []
    for _, category, _ in CATEGORIES:
        all_items.extend(get_items(category))
    max_name = max((len(name) for name, _ in all_items), default=0)

    # Space for description: what's left after name column + 2 separator chars
    desc_budget = avail - max_name - 2

    selections = []
    first = True
    for label, category, dest_dirs in CATEGORIES:
        items = get_items(category)
        if not items:
            continue
        if not first:
            selections.append(Selection("", f"spacer::{category}", disabled=True))
        first = False
        # Category header row (non-selectable separator)
        header = f"[bold]{label}[/bold]"
        selections.append(Selection(header, f"header::{category}", disabled=True))
        for name, desc in items:
            linked = is_linked(category, name, dest_dirs)
            name_col = name.ljust(max_name)
            if desc and desc_budget > 10:
                short = desc[:desc_budget] + ("..." if len(desc) > desc_budget else "")
                display = f"{name_col}  [dim]{short}[/dim]"
            else:
                display = name_col
            value = f"{category}::{name}"
            selections.append(Selection(display, value, initial_state=linked))
    return selections


class SkillSelector(App):
    dark = True

    BINDINGS = [
        Binding("enter", "apply", "Apply"),
        Binding("q", "quit", "Quit"),
    ]

    TITLE = "Skill Selector"

    def compose(self) -> ComposeResult:
        yield Header()
        yield SelectionList[str](*build_selections())
        yield Label("", id="status")
        yield Footer()

    def action_apply(self) -> None:
        sel_list = self.query_one(SelectionList)
        selected = set(sel_list.selected)
        all_values = {sel.value for sel in build_selections()}

        created = 0
        removed = 0
        for value in all_values:
            category, name = value.split("::", 1)
            dest_dirs = next(d for _, c, d in CATEGORIES if c == category)
            if value in selected:
                if not is_linked(category, name, dest_dirs):
                    apply_link(category, name, dest_dirs)
                    created += 1
            else:
                if is_linked(category, name, dest_dirs):
                    remove_link(category, name, dest_dirs)
                    removed += 1

        status = self.query_one("#status", Label)
        parts = []
        if created:
            parts.append(f"{created} linked")
        if removed:
            parts.append(f"{removed} unlinked")
        if parts:
            status.update(f" {', '.join(parts)}")
        else:
            status.update(" No changes needed.")


if __name__ == "__main__":
    app = SkillSelector()
    app.run()
