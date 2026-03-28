---
name: Safari Browser Automation
description: This skill should be used when automating Safari browser interactions via AppleScript, including form filling, page reading, navigation, clicking elements, typing into fields, handling native date pickers, or taking screenshots of Safari pages. Trigger on "fill form in Safari", "read Safari page", "automate Safari", "click button in Safari", "type in Safari", "Safari screenshot", "Safari date picker", or when interacting with web pages through Safari automation.
---

# Safari Browser Automation

Techniques for automating Safari browser interactions via AppleScript and JavaScript injection. Covers reading pages, filling forms, navigating, and handling native UI widgets.

## Scroll Position Tracking

**Include scroll position in every page read operation.** Pages often have more content below the fold. Always check and report scroll state to avoid missing data.

```javascript
var sh = document.documentElement.scrollHeight;
var sy = Math.round(window.scrollY);
var ih = window.innerHeight;
JSON.stringify({
    yScroll: sy + '/' + sh,
    canScroll: sh > (sy + ih + 10),
    remaining: sh - (sy + ih)
});
```

### Scroll-and-read loop

When reading long pages (search results, transaction lists, etc.):

1. Read content at current position
2. Check `canScroll`
3. If true: `window.scrollTo(0, window.scrollY + window.innerHeight)`, wait, read again
4. Repeat until `canScroll` is false
5. Check for truncation messages (e.g., "first 100 results displayed")

### Pagination vs infinite scroll

Some sites paginate, some load more on scroll, some show everything at once. After scrolling to bottom, check for:
- "Next page" / "Load more" links
- "Showing X of Y results" messages
- Truncation warnings ("first 100 results")

## Reading Page Content

### Text Extraction

```applescript
tell application "Safari"
    tell window 1
        set pageText to do JavaScript "document.body.innerText" in current tab
    end tell
end tell
```

### Finding Elements

```applescript
tell application "Safari"
    tell window 1
        do JavaScript "
            JSON.stringify(
                Array.from(document.querySelectorAll('a, button')).
                filter(a => /keyword/i.test(a.textContent)).
                map(a => ({text: a.textContent.trim().substring(0, 80), href: a.getAttribute('href') || ''}))
            )
        " in current tab
    end tell
end tell
```

### Screenshots for Verification

Take screenshots before nontrivial navigations (new pages, popups, modals). For repeated actions on identical UI elements, screenshot the first one then shortcut the rest. Re-screenshot after scrolling or pagination.

```bash
osascript -e 'tell application "Safari" to activate' && sleep 0.5 && screencapture -x -o /tmp/screenshot.png
```

Requires Screen Recording permission for Terminal in System Settings > Privacy & Security.

## Interaction Methods

Six methods ranked from most "real" to least. Prefer methods higher on this list.

For detailed descriptions, examples, and compatibility notes for each method, see `references/interaction-methods.md`.

### Quick Reference

| Method | Best For | Native Widget Support |
|--------|----------|----------------------|
| OS Keystrokes (System Events) | Typing, arrow keys, tab navigation | Yes |
| OS Mouse Clicks (System Events) | Clicking at screen coordinates | Yes |
| Synthetic JS Mouse Events | Clicking page elements, opening pickers | Partial |
| `.click()` | Buttons, links | No native widgets |
| `.value` injection | Text inputs, selects | Needs focus first |
| Synthetic JS Keyboard Events | Almost nothing | No |

## Form Filling

### Key Principles

1. **Always focus the field before filling it** — `element.focus()` before `.value =`
2. **Fill forms in tab order** — mimic real user flow through the form
3. **Verify state before and after** — read `.value` of all fields at each step

### Standard Pattern

```javascript
// 1. Select dropdown
var select = document.getElementById('mySelect');
for (var i = 0; i < select.options.length; i++) {
    if (select.options[i].text.includes('target')) {
        select.selectedIndex = i;
        break;
    }
}
select.dispatchEvent(new Event('change', {bubbles: true}));

// 2. Focus, then fill text input
var input = document.getElementById('myInput');
input.focus();
input.value = 'my value';
input.dispatchEvent(new Event('input', {bubbles: true}));
input.dispatchEvent(new Event('change', {bubbles: true}));
```

### Native Date Inputs (`type="date"`)

These are the hardest to automate. The DOM `.value` and the native picker's internal state can be out of sync.

**Recommended strategy:**
1. Focus the field (`element.focus()`)
2. Inject the value (`element.value = '2026-01-01'`)
3. Press spacebar via OS keystroke to "reify" the value (opens picker which registers it)

**Arrow key navigation** (when needing fine control):
- Tab into the field focuses the month segment
- Right arrow moves: month → day → year
- Up/down arrows increment/decrement the focused segment
- The field "reifies" from placeholder to actual value on first focus

For a full compatibility table of what works and doesn't with date inputs, see `references/interaction-methods.md`.

### Form Submission

Prefer clicking the submit button via synthetic mouse event or OS click over `form.submit()` or `.click()`. Direct `form.submit()` bypasses validation and event handlers.

## Element Identification & Visual Confirmation

### The Ambiguity Problem

Pages often have multiple elements with the same text (e.g., two "Search" buttons — one for site search, one for a form). Always disambiguate before clicking.

### Identification Priority

1. **`id`** — `document.getElementById('js-next')` — most reliable
2. **Form context** — `document.querySelector('#myForm button[type=submit]')` — narrows by parent
3. **CSS path with specificity** — combine tag, class, attributes: `button[name="next"].expand`
4. **XPath** — for complex DOM positions: use when CSS selectors aren't specific enough
5. **Text match** — least reliable, always check for duplicates first

### Duplicate Check (required before text-based selection)

```javascript
var matches = Array.from(document.querySelectorAll('button'))
    .filter(b => /search/i.test(b.textContent));
// If matches.length > 1, disambiguate by id, form, class, or position
JSON.stringify(matches.map(b => ({
    id: b.id, text: b.textContent.trim().substring(0, 40),
    className: b.className.substring(0, 60),
    formId: b.form ? b.form.id : 'none'
})));
```

### Visual Confirmation (highlight before clicking)

Before clicking any element found by text or ambiguous selector, highlight it and take a screenshot to verify the right element will be clicked:

```javascript
// Highlight the target element
var el = document.getElementById('js-next');
el.style.outline = '4px solid red';
el.style.outlineOffset = '2px';
el.scrollIntoView({block: 'center'});
```

Then take a screenshot, verify visually, and remove the highlight before clicking:

```javascript
el.style.outline = '';
el.style.outlineOffset = '';
el.focus();
el.click();
```

### When to Highlight

- **Always highlight** when selecting by text content and duplicates exist
- **Always highlight** on first interaction with a new page or form
- **Skip highlight** when using a known unique `id` on a page already verified

## Navigation

### Rules

- **Never guess or construct URLs** — only navigate using real links found on the page
- **Use `.click()` or synthetic events** — do not set URLs directly (`window.location =`, tab URL assignment)
- Get explicit approval before any direct URL navigation

### Clicking Links

```javascript
var link = Array.from(document.querySelectorAll('a'))
    .find(a => a.textContent.trim() === 'Target Link');
if (link) { link.click(); }
```

### Tab Management

```applescript
-- List all tabs
tell application "Safari"
    tell window 1
        repeat with t in tabs
            set end of tabInfo to {name of t, URL of t}
        end repeat
    end tell
end tell

-- Open new tab (when approved)
tell application "Safari"
    tell window 1
        set current tab to (make new tab with properties {URL:"https://example.com"})
    end tell
end tell
```

## Targeting Keystrokes

Always target the Safari process to avoid focus issues:

```applescript
tell application "System Events"
    tell process "Safari"
        keystroke "text"
        key code 125 -- down arrow
        key code 124 -- right arrow
        key code 49  -- spacebar
        key code 53  -- escape
        keystroke tab
    end tell
end tell
```

## Prerequisites

- **Allow JavaScript from Apple Events**: Safari > Settings > Advanced (or Developer)
- **Screen Recording permission**: For `screencapture` — System Settings > Privacy & Security > Screen Recording > Terminal
- **Automation permission**: System Settings > Privacy & Security > Automation > Terminal > Safari

## Additional Resources

### Reference Files

- **`references/interaction-methods.md`** — Detailed breakdown of all six interaction methods with code examples, compatibility notes, and native date picker specifics
