# Shortcut plist structure reference

A Shortcut is a plist dict whose program lives in `WFWorkflowActions` (an array of action dicts). Everything else is metadata/config.

## Top-level keys

| Key | Type | Purpose |
|---|---|---|
| `WFWorkflowActions` | array | The action graph. Executes top-to-bottom. |
| `WFWorkflowTypes` | array of strings | Where the shortcut is exposed. Common values: `QuickActions`, `MenuBar`, `NCWidget`, `Watch`, `ActionExtension`, `Services`, `Sharing`. Empty = "in Shortcuts app only". |
| `WFQuickActionSurfaces` | array | Subset of `Services`, `Finder`, `TouchBar`. Only when `WFWorkflowTypes` contains `QuickActions`. |
| `WFWorkflowInputContentItemClasses` | array | Classes the shortcut can accept as input (`WFGenericFileContentItem`, `WFFolderContentItem`, `WFURLContentItem`, `WFStringContentItem`, `WFImageContentItem`, …). |
| `WFWorkflowOutputContentItemClasses` | array | Mirror for output. Usually empty. |
| `WFWorkflowHasOutputFallback` | bool | True if shortcut yields its input unchanged when actions produce nothing. |
| `WFWorkflowHasShortcutInputVariables` | bool | True if the shortcut references the "Shortcut Input" magic variable. |
| `WFWorkflowIcon` | dict | `WFWorkflowIconGlyphNumber` (int, SF Symbols-ish) + `WFWorkflowIconStartColor` (int, signed 32-bit RGBA). |
| `WFWorkflowImportQuestions` | array | Interactive prompts shown at import time (paths, API keys, etc.). |
| `WFWorkflowClientVersion` | string | App version that wrote this file. Informational. |
| `WFWorkflowMinimumClientVersion` / `MinimumClientVersionString` | int / string | Minimum Shortcuts.app build required. Leave alone unless you know why you're editing it. |

## Action dict shape

Each entry in `WFWorkflowActions` is:

```xml
<dict>
    <key>WFWorkflowActionIdentifier</key>
    <string>is.workflow.actions.SOMETHING</string>
    <key>WFWorkflowActionParameters</key>
    <dict>
        <!-- action-specific parameters -->
    </dict>
</dict>
```

`WFWorkflowActionIdentifier` is a reverse-DNS string. Apple-provided actions live under `is.workflow.actions.*`. Third-party actions are namespaced to the providing app's bundle id (e.g. `com.toketaware.ios.ithoughts.AddIdea`).

### Common Apple action identifiers

| Identifier | What it does |
|---|---|
| `is.workflow.actions.notification` | Show a notification (title, body, input to attach). |
| `is.workflow.actions.runshellscript` | Run a shell script (macOS only). |
| `is.workflow.actions.runscriptovercr` | Run a shell script over SSH. |
| `is.workflow.actions.conditional` | If/else/end. See "Conditionals" below. |
| `is.workflow.actions.choosefrommenu` | Menu prompt with labeled branches. |
| `is.workflow.actions.repeat.count` / `repeat.each` | Loops. Similar three-action grouping as conditional. |
| `is.workflow.actions.delay` | Sleep. Param: `WFDelayTime` (real, seconds). |
| `is.workflow.actions.gettext` | Inline text literal, often used as a variable source. |
| `is.workflow.actions.setvariable` / `appendvariable` / `getvariable` | Named variable scope. |
| `is.workflow.actions.dictionary` | Build a dict literal. |
| `is.workflow.actions.gettype` | Introspect a value's type. |
| `is.workflow.actions.showresult` | Display text in-place. |
| `is.workflow.actions.comment` | Non-executing note. |
| `is.workflow.actions.url` | URL literal. |
| `is.workflow.actions.downloadurl` | HTTP request. |
| `is.workflow.actions.ask` | Prompt the user for input. |
| `is.workflow.actions.exit` | Early return from the shortcut. |

Parameter names (within `WFWorkflowActionParameters`) are per-action and stable but undocumented. When editing an unfamiliar action, **first build the action in Shortcuts.app**, export, unpack, and read the resulting plist. That's the authoritative schema.

## UUIDs and data flow

Most actions have a `UUID` key (8-4-4-4-12 hex, uppercase). It's the address of this action's output. Other actions reference it via:

```xml
<key>OutputUUID</key><string>9CCC2CE5-A8F5-4994-9A3B-3F8D8B1D5D8C</string>
<key>OutputName</key><string>Shell Script Result</string>
<key>Type</key><string>ActionOutput</string>
```

`OutputName` is human-readable ("Shell Script Result", "Contents of URL") and mirrors Shortcuts.app's label for that action's output. Keep it in sync — the app may display stale names otherwise, though execution goes by UUID.

**Regenerate UUIDs when duplicating an action.** Python: `python3 -c 'import uuid; print(str(uuid.uuid4()).upper())'`.

## Token attachments (the string-with-variables idiom)

A "string that contains a variable" is not just a string — it's a structured dict:

```xml
<key>WFNotificationActionBody</key>
<dict>
    <key>Value</key>
    <dict>
        <key>string</key>
        <string>Hello ￼!</string>               <!-- OBJ char (U+FFFC) marks each slot -->
        <key>attachmentsByRange</key>
        <dict>
            <key>{6, 1}</key>                      <!-- NSRange: offset 6, length 1 -->
            <dict>
                <key>Type</key><string>ActionOutput</string>
                <key>OutputUUID</key><string>...</string>
                <key>OutputName</key><string>Name</string>
            </dict>
        </dict>
    </dict>
    <key>WFSerializationType</key>
    <string>WFTextTokenString</string>
</dict>
```

Rules:
- Every placeholder is the single character `￼` (U+FFFC, "OBJECT REPLACEMENT CHARACTER") in the `string`.
- Keys in `attachmentsByRange` are NSRange strings `"{location, length}"`. Length is always `1`.
- When a field holds **only** a variable (no surrounding text), the `WFSerializationType` is `WFTextTokenAttachment` instead, and the structure collapses to just a `Value` with `Type`/`Variable`/`OutputUUID`.

## Variable and magic-variable references

Four `Type` values cover most references:

| `Type` | Meaning |
|---|---|
| `ActionOutput` | Output of a preceding action, selected by `OutputUUID`. |
| `Variable` | User-defined named variable (set by `setvariable`). Uses `VariableName`. |
| `ExtensionInput` | The shortcut's own input (from whatever invoked it). |
| `CurrentDate` / `Clipboard` / `Ask` / `Input` / `DeviceDetails` | Built-in magic variables. |

A variable reference inside an action's parameter:

```xml
<key>WFInput</key>
<dict>
    <key>Value</key>
    <dict>
        <key>Type</key><string>Variable</string>
        <key>VariableName</key><string>myvar</string>
    </dict>
    <key>WFSerializationType</key>
    <string>WFTextTokenAttachment</string>
</dict>
```

## Conditionals (and other block structures)

`is.workflow.actions.conditional` appears **three times** to form one if/else/end:

- `WFControlFlowMode` `<integer>0</integer>` — **if** (carries the predicate).
- `WFControlFlowMode` `<integer>1</integer>` — **else** (optional).
- `WFControlFlowMode` `<integer>2</integer>` — **end**.

All three share one `GroupingIdentifier` UUID. Do not reorder one without the others; do not change the `GroupingIdentifier` of just one.

The `if` carries a `WFConditions` dict whose `Value.WFActionParameterFilterTemplates` array holds the predicate clauses. Each clause has a `WFCondition` integer (Apple's predicate enum) and type-specific operands (`WFDate`, `WFNumberValue`, `WFEnumeration`, etc.).

`repeat.count`, `repeat.each`, `choosefrommenu`, and a few other actions follow the same three-(or-more-)part grouped pattern.

## Serialization types (quick reference)

`WFSerializationType` seen in the wild:

| Value | Carried by |
|---|---|
| `WFTextTokenString` | A templated string with `{string, attachmentsByRange}`. |
| `WFTextTokenAttachment` | A single variable reference with no surrounding text. |
| `WFDictionaryFieldValue` | Key/value in a `dictionary` action. |
| `WFArrayParameterState` | Arrays with item-level metadata. |
| `WFContentPredicateTableTemplate` | Wraps the predicate table of a conditional. |
| `WFNumberSubstitutableState` | A number that might be a variable. |

## Gotchas

- **Volatile UUIDs churn diffs.** If you're diffing two shortcuts, consider a pre-pass that normalizes UUIDs by first-appearance order.
- **Signing sends a copy to Apple.** Don't embed secrets. Use `WFWorkflowImportQuestions` to prompt at import for paths/keys.
- **Third-party action parameters can change when the app updates.** A shortcut unpacked and repacked on a newer macOS may look slightly different even without edits — Shortcuts.app may rewrite optional keys. This is normal.
- **Quick Action input types are enforced.** A shortcut with `WFWorkflowInputContentItemClasses = [WFURLContentItem]` won't appear in Finder's right-click menu on a plain folder.
- **`shortcuts sign` warnings on stderr** (`Unrecognized attribute string flag '?'`) are harmless. The signed output is still valid if it starts with `AEA1`.

## If you're generating a shortcut from scratch

Don't. Build a template shortcut in the Shortcuts app, export it, unpack it, and use that plist as your starting skeleton. Apple's action schemas have too much implicit state (default parameter values that only appear when non-default, order-sensitive keys, UI-only parameters that must be present but blank) to synthesize reliably from a textual spec.
