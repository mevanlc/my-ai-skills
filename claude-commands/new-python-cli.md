---
name: py-new-cli
description: Creates a Python CLI tool project using uv with argparse, ruff, and MIT license. Use when user wants to create a new Python CLI tool
 or command-line application.
argument-hint: [additional instructions or clarifications]
---

# Python CLI Tool Creator

Creates a Python CLI tool project using `uv` as the project manager.

## Inputs

- **project-name** (required): lowercase, hyphenated (e.g., `my-tool`)
- **description** (optional): defaults to project-name

## Workflow

### 1. Pre-flight checks
- The user should have created the project directory and `cd`'d into it.
- If not, stop and let the user know to do that first.
- Read the Python uv skill (if it exists)

### 2. Initialize project

```bash
uv init --package .
```

### 3. Edit pyproject.toml

- Set `license = "MIT"`
- Set `requires-python = ">=3.14"`
- Set `description = "{description}"` (or project-name if not provided)
- Add script entry point under `[project.scripts]`:
  ```toml
  [project.scripts]
  {project-name} = "{pkg}.cli:main"
  ```
  (where `{pkg}` is project-name with hyphens replaced by underscores)
- If `authors` is empty/missing, set to `[{name = "Example User", email = "user@example.com"}]`

### 4. Create src/{pkg}/cli.py

```python
import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="{description}")
    parser.add_argument("--version", action="version", version="0.1.0")
    args = parser.parse_args()
    print("Hello from {project-name}")
```

### 5. Update README.md

Set first line to `# {project-name}`

### 6. Create .github/instructions/ABOUT.md

```markdown
# {project-name}

## uv Commands

- `uv sync` - refresh .venv/
- `uv add <pkg>` - add a dependency
- `uv add --dev <pkg>` - add a dev dependency
- `uv remove <pkg>` - remove a dependency
- `uv run <bin> <args>` - run a binary with venv activated
- `uv run python <args>` - run python with venv activated
- `uv tool install -e .` - editable-install project bins to ~/.local/bin
- `source .venv/bin/activate` - activate venv (nix-likes)
- `.venv/Scripts/activate.ps1` - activate venv (PowerShell)

## ruff Commands

- `ruff check .` - lint
- `ruff check --fix .` - lint and auto-fix
- `ruff format .` - format code

Or with `uv run` prefix if venv not activated.

## Agent Instructions

- type hints everywhere
- follow ruff defaults (or overrides in pyproject.toml/ruff.toml)
- prefer stdlib over adding dependencies (when reasonable)
- use argparse parser.error() for expected errors
- no try/except unless needed for 'continue processing' logic
- no docstrings
- terse, high-value, "why" comments only
- f-strings for string formatting
- no tests until asked
- conventional commits, no co-author
- user instructions preempt these
```

### 7. Add dev dependencies

```bash
uv add --dev ruff
```

### 8. Initial commit

```bash
git add -A
git commit -m "initial commit"
```

### 9. Install and verify

```bash
uv tool install -e .
{project-name}
```

The CLI should print: `Hello from {project-name}`
