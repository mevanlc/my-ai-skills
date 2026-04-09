---
name: termux-open
description: Use when the user wants to open a local file from Termux in an Android app, especially for images, PDFs, or HTML files that should be handed off to the system viewer.
---

# Termux Open

Open a local file from Termux in the Android app associated with that file type.

## When to Use

- The user wants a local file opened in Android rather than read in the terminal
- The target is an image, PDF, HTML file, or similar document
- Direct local opening is unreliable and a temporary HTTP server is needed

## Workflow

1. Resolve the requested path to an absolute file path.
2. If the path does not exist, stop and tell the user.
3. Prefer `termux-open "$FILE"` if that is sufficient in the current environment.
4. If direct open is unreliable, temporarily serve the parent directory over localhost and open the file URL with `termux-open`.
5. Shut down the temporary server after the handoff so it does not linger.

## Safe HTTP Fallback

Use a localhost-only server and clean it up automatically:

```bash
FILE="/absolute/path/to/file"
DIR="$(dirname "$FILE")"
BASE="$(basename "$FILE")"
PORT=8765

cd "$DIR"
python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT
sleep 1
termux-open "http://127.0.0.1:$PORT/$BASE"
sleep 3
```

## Notes

- Use `$PREFIX/tmp` or `$TMPDIR` for temporary files, not `/tmp`
- Works best when the file path is already local to the device
