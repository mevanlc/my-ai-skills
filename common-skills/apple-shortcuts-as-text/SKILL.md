---
name: Apple Shortcuts as Text
description: Use when the user invokes or mentions this skill.
---

# Apple Shortcuts as Text

Apple's `.shortcut` files are opaque AEA-signed archives wrapping a binary plist. This skill strips the signing wrapper to expose an editable XML plist, and reseals edits using Apple's own `shortcuts sign` CLI. Everything uses approved Apple tooling — no signature forgery, no reverse-engineered crypto.

## When to use

- User wants to read, diff, edit, or version-control a `.shortcut` file.
- User has a shortcut exported from Shortcuts.app and wants its "source".
- User wants to programmatically generate or modify a shortcut via an LLM.
- User mentions `Shortcut.wflow`, `WFWorkflowActions`, or the signed/unsigned shortcut distinction.

Skip this skill for: writing a shortcut from scratch without a template (just build the plist directly), running shortcuts (use `shortcuts run`), or anything involving the Shortcuts app UI.

## Prerequisites

- macOS (uses `aea`, `aa`, `plutil`, `shortcuts`, `openssl` — all bundled with macOS 13+).
- Python 3 (for the bundled scripts; stdlib only).

Verify up front: `which aea aa plutil shortcuts openssl`. If any are missing, stop and tell the user.

## Unpacking a signed shortcut → text

Signed shortcuts start with the magic `AEA1`. The pipeline is:

```
My.shortcut (AEA1, signed)
  → aea decrypt       → My.aar       (Apple Archive, LZFSE)
  → aa extract        → Shortcut.wflow  (binary plist)
  → plutil -convert xml1 → Shortcut.wflow.xml  (editable)
```

Use the bundled script — it handles the fiddly step of extracting the signing public key from the file's own embedded certificate chain (required by `aea decrypt` even for profile-0 "signed, not encrypted" archives):

```bash
python3 scripts/shortcut_unpack.py My.shortcut
# → produces My.unpacked/ containing:
#     auth.plist              (signing metadata, incl. cert chain)
#     My.aar                  (the Apple Archive payload)
#     extracted/Shortcut.wflow      (binary plist — the actual shortcut)
#     extracted/Shortcut.wflow.xml  (XML plist — edit this)
```

Flags: `-o <dir>` for output location, `--force` to overwrite, `--no-convert` to skip XML conversion.

For unsigned shortcuts (older export format or raw `.wflow`), the magic will be `bplist00` — skip directly to `plutil -convert xml1 -o out.xml in.shortcut`.

## Packing text → signed shortcut

```bash
python3 scripts/shortcut_pack.py Shortcut.wflow.xml -o My.shortcut
```

(`scripts/` paths are relative to this skill's directory — cd into it first, or use the absolute path resolved via `readlink ~/.claude/skills/apple-shortcuts-as-text` / `~/.codex/skills/apple-shortcuts-as-text`.)

This converts XML→binary plist via `plutil`, then calls `shortcuts sign`. The script defaults to `--mode anyone`; pass `--mode people-who-know-me` to restrict sharing. **Signing sends a copy to Apple for validation** — this is Apple's design, not optional.

Manual equivalent if the script isn't available:

```bash
plutil -convert binary1 -o /tmp/unsigned.shortcut Shortcut.wflow.xml
shortcuts sign --mode anyone --input /tmp/unsigned.shortcut --output My.shortcut
```

`shortcuts sign` prints some harmless `Unrecognized attribute string flag '?'` warnings to stderr — ignore them. Output succeeds iff the file starts with `AEA1`.

## Structure of the XML plist

The top-level dict has a few keys that matter:

| Key | What it is |
|---|---|
| `WFWorkflowActions` | Array of action dicts — **this is the program**. |
| `WFWorkflowTypes` | Where the shortcut appears: `QuickActions`, `MenuBar`, `Watch`, `ActionExtension`, `Services`, etc. |
| `WFWorkflowInputContentItemClasses` | Accepted input types (`WFGenericFileContentItem`, `WFURLContentItem`, …). |
| `WFWorkflowIcon` | Glyph number + color integer for the Shortcuts app tile. |
| `WFWorkflowClientVersion` / `WFWorkflowMinimumClientVersion` | Shortcuts.app compatibility. Leave alone when editing. |
| `WFQuickActionSurfaces` | For Quick Actions: `Services`, `Finder`, `TouchBar`. |

Each element of `WFWorkflowActions` is a dict with:
- `WFWorkflowActionIdentifier` — e.g. `is.workflow.actions.runshellscript`, `is.workflow.actions.notification`, `is.workflow.actions.conditional`, `is.workflow.actions.delay`.
- `WFWorkflowActionParameters` — per-action dict. Every action has its own parameter schema.

For anything beyond trivial edits (variable references, conditionals, magic variables, token attachments), load `references/shortcut-plist-structure.md` — it has the patterns you'll actually encounter, with worked examples.

## Editing rules of thumb

- **UUIDs matter.** Actions reference each other's outputs by UUID (`OutputUUID` pointing at another action's `UUID`). When duplicating an action, regenerate the UUID; when deleting, also delete any `OutputUUID` references to it.
- **Don't rename outputs blindly.** `OutputName` is a display label but it's paired with the producing action's `UUID`. Both must match.
- **Conditionals are three separate actions** (`WFControlFlowMode` = 0/1/2 for if/else/end) sharing a `GroupingIdentifier`. Don't reorder one without the others.
- **Preserve the plist DTD line and `<plist version="1.0">`** — `plutil` needs them to parse.
- **Don't hand-edit the binary `.wflow`.** Edit `.wflow.xml`, repack.

## A full round-trip test

```bash
SKILL=$(cd "$(dirname "$(readlink -f ~/.claude/skills/apple-shortcuts-as-text)")" && pwd)

python3 "$SKILL/scripts/shortcut_unpack.py" Orig.shortcut -o /tmp/orig.unpacked
# ... edit /tmp/orig.unpacked/extracted/Shortcut.wflow.xml ...
python3 "$SKILL/scripts/shortcut_pack.py" /tmp/orig.unpacked/extracted/Shortcut.wflow.xml -o Edited.shortcut
# Optional: open in Shortcuts.app to verify
open Edited.shortcut
```

## What this skill does NOT do

- **Bypass Apple's signature enforcement.** If `shortcuts sign` rejects a file, fix the file; don't try to forge signatures.
- **Work on Linux/Windows.** The whole pipeline depends on macOS-only Apple CLIs.
- **Round-trip a shortcut exported by a different Apple ID without resigning.** The output is re-signed under the current user.
- **Pretty-print or normalize the plist for diffing.** You may want to do that as a separate step; `plutil -convert xml1` preserves Apple's key ordering but volatile UUIDs will still churn diffs.
