#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "textual>=3.0",
#   "pyyaml>=6.0",
# ]
# ///
"""TUI for selecting which skills/commands to symlink from this repo."""

import os
from pathlib import Path

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Label, SelectionList
from textual.widgets.selection_list import Selection


REPO = Path(__file__).resolve().parent

CATEGORIES = [
    ("Claude Skills", "claude-skills", Path.home() / ".claude" / "skills"),
    ("Claude Commands", "claude-commands", Path.home() / ".claude" / "commands"),
    ("Codex Skills", "codex-skills", Path.home() / ".codex" / "skills"),
]

# Items managed by other repos — don't touch these.
SKIP = {
    "claude-skills": {"macos-automation-skill"},
    "claude-commands": {"commit.md", "gdf-commit.md"},
}


def get_description(path: Path) -> str:
    """Extract the description from YAML frontmatter of a skill/command."""
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


def is_linked(category: str, name: str, dest_dir: Path) -> bool:
    dest = dest_dir / name
    if dest.is_symlink():
        return dest.resolve() == (REPO / category / name).resolve()
    return False


def apply_link(category: str, name: str, dest_dir: Path) -> None:
    src = REPO / category / name
    dest = dest_dir / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    if dest.is_symlink():
        if dest.resolve() == src.resolve():
            return
        dest.unlink()
    elif dest.exists():
        backup = dest.with_suffix(dest.suffix + ".bak")
        dest.rename(backup)
    dest.symlink_to(src)


def remove_link(category: str, name: str, dest_dir: Path) -> None:
    dest = dest_dir / name
    if dest.is_symlink() and dest.resolve() == (REPO / category / name).resolve():
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
    for label, category, dest_dir in CATEGORIES:
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
            linked = is_linked(category, name, dest_dir)
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
            dest_dir = next(d for _, c, d in CATEGORIES if c == category)
            if value in selected:
                if not is_linked(category, name, dest_dir):
                    apply_link(category, name, dest_dir)
                    created += 1
            else:
                if is_linked(category, name, dest_dir):
                    remove_link(category, name, dest_dir)
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
