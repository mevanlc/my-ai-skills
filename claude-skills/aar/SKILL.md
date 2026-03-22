---
name: python-uv
description: Use `uv` as a fast, unified Python project + dependency + tool runner: create projects, manage deps + lockfiles, run commands in a synced env, run/install Python tools, and work with standalone scripts via inline metadata. Use instead of `python -m venv`, `pip`, `pipx`, pdm, poetry, etc.
---

# uv

## If you’re trying to build a tiny standalone script (core workflow)
When you want a single `.py` file that carries its own dependency metadata:

```bash
uv init --script newtool.py
uv add --script newtool.py <dependency1> [dependencyN...]
uv run newtool.py [scriptargs]
```

Notes that tend to matter in practice:
- `uv run <file>.py` treats the file as a script (and script arguments go after the filename).
- Script inline metadata is “self-contained”: when present, it runs with its own declared deps rather than your current project’s deps.

## If you’re trying to start a new repo (project workflow)
- Create a project:
  ```bash
  uv init my-app
  cd my-app
  ```

- Run code inside the project environment:
  ```bash
  uv run main.py
  ```

What to expect structurally:
- `pyproject.toml` holds declared requirements.
- `.venv/` and `uv.lock` appear the first time you run a project command like `uv run`, `uv sync`, or `uv lock`.
- `uv.lock` is the “exact resolved versions” record; it’s meant to be checked in.

## If you’re trying to keep installs and runs consistent (CI / disciplined dev)
In a project, `uv run` aims to keep `pyproject.toml` -> `uv.lock` -> `.venv` in sync automatically before the command executes.

## If you’re trying to add, remove, or update dependencies
- Add a dependency (updates `pyproject.toml`, and updates lock/env as needed):
  ```bash
  uv add httpx
  ```

- Remove:
  ```bash
  uv remove httpx
  ```

- Upgrade one package while keeping everything else stable:
  ```bash
  uv lock --upgrade-package httpx
  ```

- Import from a legacy requirements file (migration-friendly):
  ```bash
  uv add -r requirements.txt
  ```

## If you’re trying to run a command (not a script)
Use `uv run -- <command...>` when you want the command to execute “in the uv-managed environment”:

```bash
uv run -- python -c "print('hi')"
uv run -- pytest -q
```

(Everything after `--` is treated as command arguments, not uv flags.)

## If you’re trying to run one-off Python tools (ruff/black/etc.) without installing them into your project
Use `uvx` for ephemeral, isolated tool runs:

```bash
uvx ruff check .
uvx black --version
```

## uv's take on `npm install -g`
If the user has their PATH setup correctly, this will install the tool globally for the user.
```bash
uv tool install ruff
uv tool upgrade ruff
```

## uv's take on `npx`
Download and run a Python tool in an isolated environment without installing it globally.
(Unlike `npx`, this isn't used to run in-project bins; for that, use `uv run`.)
```bash
uvx ruff -- --version
uvx black --help
```

# Further reading
`{SKILL_DIR}/docs/**/*.md`
