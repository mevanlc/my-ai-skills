---
name: uv-script
description: >-
  Use when you or the user want to: create or run a PEP 723 inline-dependency
  Python script, or use "uv run" on a standalone .py file, or ask about inline
  script metadata, or mentions "uv script", "uv scripts".
---

# uv Scripts — PEP 723 Inline-Dependency Python Scripts

## Core Workflow

Create a standalone script with inline dependency metadata:

```bash
uv init --script example.py --python 3.12
uv add --script example.py 'requests<3' 'rich'
uv run example.py
```

## Inline Metadata Format

PEP 723 embeds dependency info directly in the script via a TOML comment block:

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "requests<3",
#   "rich",
# ]
# ///
```

- The `dependencies` field must be present even if empty.
- When inline metadata is present, `uv run` uses only those declared deps — project deps are ignored. No `--no-project` flag needed.

## Running Scripts

```bash
uv run example.py                       # run with declared inline deps
uv run --with rich example.py           # add an ad-hoc dep at invocation
uv run --with 'rich>12,<13' example.py  # constrained ad-hoc dep
uv run --python 3.10 example.py         # use a specific Python version
uv run --no-project example.py          # skip project install (no inline metadata)
echo 'print("hi")' | uv run -          # read from stdin
```

Arguments after the script name are passed to the script, not to uv. All uv flags must come before the script name.

## Making Scripts Executable (Shebang)

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///

import httpx
print(httpx.get("https://example.com"))
```

Then `chmod +x script` and run with `./script`.

## Locking Dependencies

```bash
uv lock --script example.py       # creates example.py.lock
uv run --script example.py        # uses lockfile if present
uv export --script example.py     # export locked deps
uv tree --script example.py       # view dependency tree
```

## Reproducibility

Pin resolution time via `exclude-newer` in inline metadata:

```python
# /// script
# dependencies = ["requests"]
# [tool.uv]
# exclude-newer = "2024-10-16T00:00:00Z"
# ///
```

## Alternative Package Indexes

```bash
uv add --index "https://example.com/simple" --script example.py 'mypkg'
```

Adds `[[tool.uv.index]]` to the inline metadata.

## Up-to-Date Documentation

A local clone of the consolidated Astral docs provides the latest reference material.

### Refresh Docs

```bash
if [ -d ~/p/gh/astral-sh-docs/ ]; then
  git -C ~/p/gh/astral-sh-docs/ pull --ff-only
else
  git clone https://github.com/astral-sh/docs ~/p/gh/astral-sh-docs/
fi
```

### Read Docs

Key files within `~/p/gh/astral-sh-docs/site/uv/`:

```bash
# Full scripts guide
cat ~/p/gh/astral-sh-docs/site/uv/guides/scripts/index.md

# uv run CLI reference (extract just the uv-run section)
rg -UNo '(^## .*uv-run[\s\S]+?)^## ' --replace '$1' ~/p/gh/astral-sh-docs/site/uv/reference/cli/index.md
```
