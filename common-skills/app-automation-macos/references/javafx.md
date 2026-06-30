# JavaFX macOS Accessibility Notes

Use this reference when the target app is JavaFX, a Java app launched by Gradle or Maven, or a JavaFX app packaged with `jpackage`.

## Packaging

Prefer a real `.app` bundle when testing macOS automation. App identity, process discovery, and accessibility lookup are more reliable for `AXJFX.app`-style launches than for a raw `java` process.

For Gradle JavaFX projects, use the official OpenJFX Gradle plugin so platform-specific JavaFX native artifacts match the Mac architecture. If the app will be distributed or launched outside the development shell, use `jpackage` directly or through a Gradle runtime/jpackage plugin.

Use a plain launcher class whose `main` calls `Application.launch(ActualApp.class, args)` rather than pointing the application plugin directly at the class that extends `javafx.application.Application`.

Expect `open` or Finder-style launches to have a different working directory and a reduced environment. Prefer explicit absolute paths for logs, config files, and test fixtures.

Useful launch probes:

```bash
open -W -o /tmp/app-stdout.txt --stderr /tmp/app-stderr.txt -a /absolute/path/App.app
pgrep -fl 'AppName|CFBundleName|java'
plutil -p /absolute/path/App.app/Contents/Info.plist
```

## AX Probe Script

The skill bundles `scripts/axprobe.swift`, a small `ApplicationServices` utility for inspecting and invoking macOS Accessibility APIs:

```bash
scripts/axprobe.swift list --pid "$PID" --max-depth 14
scripts/axprobe.swift actions --pid "$PID" --contains "Settings" --role AXRadioButton
scripts/axprobe.swift attributes --pid "$PID" --contains "editable initial value" --role AXTextField
scripts/axprobe.swift perform --pid "$PID" --contains "Run primary action" --action AXPress
scripts/axprobe.swift focus --pid "$PID" --contains "Settings" --role AXRadioButton
scripts/axprobe.swift set-value --pid "$PID" --contains "Name" --role AXTextField --value "new text"
```

The terminal or host process running the script must have macOS Accessibility permission.

## Verified JavaFX Control Mappings

These mappings were observed on macOS arm64 with JDK 21 and JavaFX 21:

| JavaFX control | macOS AX role | Operation that changed state |
| --- | --- | --- |
| `Button` | `AXButton` | `AXPress` |
| `CheckBox` | `AXCheckBox` | `AXPress` |
| `ToggleButton` | `AXCheckBox` | `AXPress` |
| `RadioButton` | `AXRadioButton` | `AXPress` |
| `Slider` | `AXSlider` | `AXIncrement` / `AXDecrement` |
| `Spinner<Integer>` | `AXIncrementor` | `AXIncrement` / `AXDecrement` |
| `TextField` | `AXTextField` | set `AXFocused=true` for focus |
| `ComboBox` | `AXPopUpButton` | `AXPress` opens the popup |
| `TabPane` tabs | `AXTabGroup` with `AXRadioButton` tabs | set tab `AXFocused=true` |

`Node.setAccessibleText(...)` can expose stable text for buttons, checkboxes, toggles, radio buttons, and sliders. Avoid using it on editable value controls when the test needs to read or mutate the user-entered value, because it can hide the actual text value from the parent AX node.

## Negative Findings

Do not treat an AX success return as proof that JavaFX accepted the change.

Observed failures:

- `AXUIElementSetAttributeValue(..., AXValue, ...)` returned success for a JavaFX `TextField`, but the JavaFX `textProperty()` did not change.
- A JavaFX `ComboBox` popup exposed `AXRow` nodes and a row exposed settable `AXSelected`, but setting it did not commit the combo value.
- JavaFX `TabPane` tabs exposed `AXPress`, and `AXPress` returned success, but selection did not change. Setting `AXFocused=true` on the tab selected it.
- Synthetic keyboard events from the Swift probe did not reach the JavaFX app in the tested environment, even after activating and focusing the app.

## computer-use Notes

For JavaFX, packaging as a `.app` can be the difference between `get_app_state` resolving the app and failing to attach to a raw `java` process.

Observed behavior:

- `click(element_index=...)` worked for basic controls such as buttons and checkboxes.
- `perform_secondary_action(..., action="Increment")` worked for a slider.
- Tabs appeared as selectable tab elements. A single `click(element_index=...)`, `set_value`, and `perform_secondary_action(..., action="Press")` did not activate the tab in the test app, but a double-click by element index did.

When a direct computer-use action does not change the app, compare it with direct AX through `scripts/axprobe.swift` before concluding the control cannot be automated.

## Verification Pattern

Add app-level logs or visible state to GUI test apps so automation experiments have an oracle independent of screenshots and API return codes.

For JavaFX tests, log each expected state transition, then compare:

1. The AX action return value.
2. The next accessibility tree or app state snapshot.
3. The app's own log or visible state.

Use a native app such as TextEdit as a control case if a tool hangs, returns `procNotFound`, or seems unable to attach to any app.
