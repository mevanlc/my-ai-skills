---
name: app-automation-macos
description: Use when automating local macOS GUI apps, inspecting or invoking app widgets, comparing computer-use, macos-mcp, AppleScript, shell, or Swift accessibility approaches, or preparing a GUI app as a real .app bundle so macOS automation tools can address it reliably.
---

# Intro

Automate macOS apps from the strongest available evidence path. Prefer app/accessibility state over screenshots when possible, but keep vision and coordinates available for apps that expose poor accessibility trees.

Before acting, identify the app by visible name, bundle id, bundle path, or PID, and decide how you will verify the result: app state, accessibility tree, output file, process state, logs, or screenshot.

## .app packaging and `open`

Many tools work better with a real `.app` bundle than with a raw executable, `java`, `npm`, or a development server process. If app identity matters, inspect `Contents/Info.plist` for `CFBundleName`, `CFBundleIdentifier`, and `CFBundleExecutable`.

When testing launch behavior, prefer:

```bash
open -n /absolute/path/App.app
osascript -e 'tell application "System Events" to get name of every process whose visible is true'
```

Remember that `open` and Finder-style launches may use a different working directory and a reduced environment. Do not assume shell `PATH`, relative paths, or repo-local files are available unless the app explicitly configures them.

## Tools & Techniques

### computer-use

Call `get_app_state` once before interacting. It returns a screenshot plus an accessibility tree with element indexes.

#### Vision-based

Use vision when the accessibility tree is missing, misleading, or too coarse. Treat it as evidence for what is visible, not as proof that an action succeeded. Re-read state after acting.

#### Accessibility-based

Prefer element-index operations when available:

- `click(element_index=...)` for primary widget actions.
- `perform_secondary_action(element_index=..., action=...)` for actions exposed as secondary accessibility actions, such as `Increment`, `Decrement`, `Raise`, or `zoom the window`.
- `set_value(element_index=..., value=...)` only when the tree says the element is settable; verify the app actually accepted the value.
- `select_text` and `scroll(element_index=...)` for text and scroll areas.

If `get_app_state` hangs or returns `procNotFound`, try a known native app such as TextEdit as a control case, then retry the target by app name, bundle id, and bundle path. If the tool session appears stale, restart the session before blaming tmux or the app.

### macos-mcp

Use `Snapshot` to inspect the desktop and interactive elements. Use `Shell` for deterministic probes, process checks, `osascript`, `screencapture`, and one-off Swift programs.

#### Vision-based

`Click`, `Move`, `Scroll`, and `Type` are coordinate-oriented. Use them when coordinate interaction is acceptable or when no accessibility-level operation exists. First capture a snapshot, then verify after each action.

### DIY

Use DIY automation when plugin tools are too coarse, hung, or do not expose the specific accessibility action needed.

#### osascript + shell

Use `osascript` and `System Events` for process discovery, app activation, menu operations, and simple keystrokes. Use shell commands for launch logs, `open`, `ps`, `pgrep`, `plutil`, and app bundle inspection.

Example probes:

```bash
osascript -e 'tell application "System Events" to get name of every process whose visible is true'
plutil -p /path/App.app/Contents/Info.plist
```

#### swift one-off programs

Use Swift with `ApplicationServices` when you need direct AX APIs:

- `AXUIElementCreateApplication(pid)` to attach to an app.
- `AXUIElementCopyAttributeValue` and `AXUIElementCopyActionNames` to inspect nodes.
- `AXUIElementPerformAction` for direct actions such as `AXPress`, `AXIncrement`, or `AXDecrement`.
- `AXUIElementSetAttributeValue` for settable attributes such as `AXFocused`, `AXValue`, or `AXSelected`.

Always verify with app-level evidence. Some controls report settable attributes but ignore the mutation.

## Other Notes

- macOS Accessibility, Automation, and Screen Recording permissions can differ by host app, terminal, MCP server, and session.
- Keep screenshots and coordinate clicks as fallback tools, not the default proof path.
- Distinguish "the API returned success" from "the app state changed."
- For GUI test apps, add explicit logs or observable state changes so automation experiments have a reliable oracle.
- Avoid irreversible UI actions unless the user has explicitly authorized that specific action.

# Conclusion

Start with the highest-level accessible state you can get, act through stable element or AX handles when possible, and verify from the app's own state. Fall back to vision, coordinates, or bespoke Swift/AppleScript only when the accessibility surface is incomplete or unreliable.
