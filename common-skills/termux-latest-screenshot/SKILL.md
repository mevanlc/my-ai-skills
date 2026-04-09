---
name: termux-latest-screenshot
description: Use when the user wants the most recent Android screenshot located in the standard DCIM Screenshots directory to be found and viewed quickly.
---

# Termux Latest Screenshot

Find the newest screenshot in the standard Android screenshots folder and view it.

## Default Path

`/storage/emulated/0/DCIM/Screenshots`

## Workflow

1. Confirm the screenshots directory exists.
2. Find the most recent file in that directory.
3. If no screenshot exists, stop and tell the user.
4. View the image with the tool available in the current environment.

## Recommended Command

Prefer a timestamp-safe command over parsing `ls` output:

```bash
find /storage/emulated/0/DCIM/Screenshots -maxdepth 1 -type f -printf '%T@ %p\n' | sort -nr | head -n 1
```

The path is the part after the first space.

## Viewing

- In Codex, use `view_image` with the absolute screenshot path when you need to inspect the image.
- In other agents, use the environment's image-reading or image-opening tool with the same absolute path.
