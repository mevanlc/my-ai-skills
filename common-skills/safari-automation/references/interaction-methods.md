# Safari Interaction Methods — Detailed Reference

Six methods for interacting with web page elements in Safari, ranked from most "real" (closest to actual user input) to least.

## 1. OS-Level Keystrokes (System Events)

Most "real" — indistinguishable from user input at the OS level.

### Usage

```applescript
tell application "System Events"
    tell process "Safari"
        keystroke "01"           -- type text
        key code 125             -- down arrow
        key code 126             -- up arrow
        key code 124             -- right arrow
        key code 123             -- left arrow
        key code 49              -- spacebar
        key code 53              -- escape
        key code 36              -- return/enter
        keystroke tab            -- tab
        keystroke "a" using command down  -- Cmd+A
    end tell
end tell
```

### Key Points

- Target `tell process "Safari"` to send keystrokes regardless of frontmost app
- Activate Safari first for reliability: `tell application "Safari" to activate`
- Add delays between keystrokes for native widgets: `delay 0.1` to `delay 0.3`
- Works with native date picker segments (arrow keys change values)
- Spacebar opens native date picker and reifies injected values

### Limitations

- If Safari window is minimized, keystrokes may not land
- Cannot target a specific tab — goes to whichever tab/field is focused
- Need to manage focus via JavaScript before sending keystrokes

## 2. OS-Level Mouse Clicks (System Events)

Real clicks at absolute screen coordinates.

### Usage

```applescript
tell application "System Events"
    click at {screenX, screenY}
end tell
```

### Converting Viewport to Screen Coordinates

```javascript
// In Safari JavaScript:
var btn = document.querySelector('#myButton');
var rect = btn.getBoundingClientRect();
var toolbarHeight = window.outerHeight - window.innerHeight;
JSON.stringify({
    viewX: Math.round(rect.left + rect.width/2),
    viewY: Math.round(rect.top + rect.height/2),
    screenX: window.screenX,
    screenY: window.screenY,
    toolbarHeight: toolbarHeight
});

// Screen position = screenX + viewX, screenY + toolbarHeight + viewY
```

### Limitations

- Screen coordinates shift if window moves or resizes
- Toolbar height varies (bookmarks bar, tab bar state)
- Cannot click inside shadow DOM elements (native pickers)

## 3. Synthetic JS Mouse Events

JavaScript-dispatched mouse events on DOM elements.

### Usage

```javascript
var element = document.getElementById('target');
var rect = element.getBoundingClientRect();
var x = rect.left + rect.width / 2;
var y = rect.top + rect.height / 2;

var opts = {
    bubbles: true,
    cancelable: true,
    view: window,
    clientX: x,
    clientY: y,
    button: 0,      // primary button
    buttons: 1       // primary button pressed
};

element.dispatchEvent(new MouseEvent('mousedown', opts));
element.dispatchEvent(new MouseEvent('mouseup', opts));
element.dispatchEvent(new MouseEvent('click', opts));
```

### Key Points

- Works for opening native date pickers (the calendar appears)
- Provides coordinate info that some handlers require
- Fires event handlers attached to the element

### Limitations

- Does NOT work for interacting with native picker calendar UI (rendered in shadow DOM)
- Browser does not treat these as "trusted" events — some handlers check `event.isTrusted`

## 4. JavaScript `.click()`

Simplest programmatic click.

### Usage

```javascript
document.getElementById('myButton').click();

// Finding and clicking
var btn = Array.from(document.querySelectorAll('button'))
    .find(b => b.textContent.trim() === 'Search');
if (btn) btn.click();
```

### Key Points

- Works for buttons, links, most interactive elements
- Fires `click` event handlers
- No coordinate info provided

### Limitations

- Some handlers need coordinates (e.g., canvas clicks, custom widgets)
- Does not open native date pickers
- `isTrusted` is false

## 5. JavaScript `.value` Injection

Direct DOM property manipulation.

### Usage

```javascript
// CRITICAL: focus first
var input = document.getElementById('myInput');
input.focus();
input.value = 'new value';
input.dispatchEvent(new Event('input', {bubbles: true}));
input.dispatchEvent(new Event('change', {bubbles: true}));
```

### For Select Dropdowns

```javascript
var select = document.getElementById('mySelect');
select.selectedIndex = 2;  // or find by text
select.dispatchEvent(new Event('change', {bubbles: true}));
```

### Using Native Value Setter (for React/framework-managed inputs)

```javascript
var nativeSet = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
).set;
nativeSet.call(input, 'new value');
input.dispatchEvent(new Event('input', {bubbles: true}));
input.dispatchEvent(new Event('change', {bubbles: true}));
```

### Key Points

- Fast and reliable for standard text inputs, textareas, selects
- **Must focus field first** — otherwise native widgets won't register the value
- Fire `input` and `change` events after setting
- For date inputs, may need spacebar press after to reify

### Limitations

- Native date pickers may not sync with `.value` — DOM property and picker state can diverge
- Some frameworks intercept value changes and need the native setter approach

## 6. Synthetic JS Keyboard Events

JavaScript-dispatched keyboard events.

### Usage

```javascript
element.dispatchEvent(new KeyboardEvent('keydown', {
    key: 'ArrowDown',
    code: 'ArrowDown',
    bubbles: true
}));
```

### Key Points

- **Least effective method** — native form controls generally ignore these
- Browser does not treat them as trusted input events
- The input's value does NOT change from these events

### When It Might Work

- Custom JavaScript widgets that listen for keydown/keyup
- Libraries that process keyboard events without checking `isTrusted`

### When It Definitely Doesn't Work

- Native date picker segment navigation
- Native select dropdowns
- Any native form control value changes

## Native Date Input (`type="date"`) Compatibility Matrix

| Approach | Works? | Notes |
|----------|--------|-------|
| `.value = '2026-01-01'` without focus | No | Value set in DOM but not recognized by native picker on submit |
| `.value` with `focus()` first | Yes | Focus the field before injecting |
| `.value` + spacebar (OS keystroke) after | Yes | Spacebar opens picker which reifies the injected value |
| `.value` + synthetic mouse click after | Sometimes | Inconsistent; click may open calendar that overrides value |
| OS arrow keys on focused segments | Yes | Down/up arrows change month/day/year reliably |
| Synthetic JS arrow key events | No | Native picker ignores them completely |
| OS digit keystrokes | Partial | Works when no calendar popup is open; calendar intercepts keystrokes |
| Tab into field | Yes | Reifies placeholder to actual value; month segment gets focus |

### Recommended Date Input Strategy

```applescript
-- Step 1: Focus and inject via JavaScript
tell application "Safari"
    tell window 1
        do JavaScript "
            var dateField = document.getElementById('myDate');
            dateField.focus();
            dateField.value = '2026-01-01';
        " in current tab
    end tell
end tell

-- Step 2 (if needed): Press spacebar to reify
delay 0.3
tell application "Safari" to activate
delay 0.3
tell application "System Events"
    tell process "Safari"
        key code 49 -- spacebar
    end tell
end tell
```

### Date Picker Segment Navigation

When the date field is focused (via Tab, not mouse click to avoid calendar popup):

1. **Month segment** is focused first
2. **Right arrow** moves to day segment, then year segment
3. **Left arrow** moves back
4. **Up/down arrows** increment/decrement the current segment
5. Segment values wrap (month: 12 → 01, day: 31 → 01, etc.)

To calculate arrow presses needed, verify the starting value first:
```javascript
document.getElementById('myDate').value  // e.g., "2026-03-19"
```

Then compute: if starting month is 03 and target is 01, press down arrow 2 times.

## Choosing the Right Method

### Decision Flow

1. **Need to type text or navigate native widgets?** → OS Keystrokes (#1)
2. **Need to click at precise screen location?** → OS Mouse Click (#2)
3. **Need to click a DOM element with coordinates?** → Synthetic JS Mouse (#3)
4. **Need to click a button or link?** → `.click()` (#4)
5. **Need to set a form field value?** → `.value` injection with focus (#5)
6. **Last resort for custom JS widgets** → Synthetic JS Keyboard (#6)

### Combining Methods

Most form filling requires combining methods:

1. **Select dropdowns**: `.selectedIndex` + `dispatchEvent` (#5)
2. **Text inputs**: `focus()` + `.value` + events (#5)
3. **Date inputs**: `focus()` + `.value` + spacebar keystroke (#5 + #1)
4. **Submission**: Synthetic mouse click on button (#3) or OS click (#2)
5. **Navigation between fields**: OS Tab keystroke (#1)
