---
name: termux-latest-screenshot
description: Use when the user wants the most recent Android screenshot located in the standard DCIM Screenshots directory to be found and viewed quickly.
---

# Termux Latest Screenshot

Find the newest screenshot in the standard Android screenshots folder and view it.

## Default Path

`/storage/emulated/0/DCIM/Screenshots`

## Environment Check

First decide whether you are running **on the phone** or **on another machine**:

- If the screenshots directory exists locally, you are on the phone — use the [On-Device Workflow](#on-device-workflow).
- Otherwise, fetch the screenshot from the phone over SSH — use the [Remote Workflow](#remote-workflow-not-on-the-phone).

```bash
test -d /storage/emulated/0/DCIM/Screenshots && echo on-device || echo remote
```

## On-Device Workflow

1. Confirm the screenshots directory exists.
2. Find the most recent file in that directory.
3. If no screenshot exists, stop and tell the user.
4. View the image with the tool available in the current environment.

Prefer a timestamp-safe command over parsing `ls` output:

```bash
find /storage/emulated/0/DCIM/Screenshots -maxdepth 1 -type f -printf '%T@ %p\n' | sort -nr | head -n 1
```

The path is the part after the first space.

## Remote Workflow (not on the phone)

The phone runs Termux with an SSH server reachable via the host alias `android.local`.
This skill assumes `~/.ssh/config` is already set up correctly for that alias (port,
identity/key, and any other options), so plain `ssh android.local` / `scp` just work —
do not pass `-p`/`-P`, `-i`, or other connection flags. Run the find command remotely
to locate the newest screenshot, then copy it down locally.

1. Find the newest screenshot on the phone over SSH:

   ```bash
   ssh android.local 'find /storage/emulated/0/DCIM/Screenshots -maxdepth 1 -type f -printf "%T@ %p\n" | sort -nr | head -n 1'
   ```

   The remote path is the part after the first space. If the command returns
   nothing, no screenshot exists — stop and tell the user.

2. Copy that file to a local temp path with `scp` (quote the remote path; preserve
   the original filename):

   ```bash
   scp android.local:"/storage/emulated/0/DCIM/Screenshots/<filename>" /tmp/
   ```

3. View the local copy with the environment's image-reading tool.

## Viewing

- In Codex, use `view_image` with the absolute screenshot path when you need to inspect the image.
- In other agents, use the environment's image-reading or image-opening tool with the same absolute path.
