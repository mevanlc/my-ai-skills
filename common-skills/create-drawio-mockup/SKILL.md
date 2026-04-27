---
name: Create draw.io Mockup
description: Author or edit `.drawio` (mxGraph XML) files for UI mockups, wireframes, and TUI/CLI screen mockups. Use when the user asks to "make a drawio mockup", "create a wireframe in drawio", "mock up a screen as a .drawio file", "edit a .drawio mockup", "round-trip a drawio file by hand", or hands you a `.drawio`/`.xml` mxGraph file to read or modify. Covers the mxfile/mxGraphModel/mxCell schema, the style mini-language, HTML-in-value rich text, theme-aware colors, and the composition tricks used in real mockups (TUIs, settings dialogs, dark UIs).
---

# Create draw.io Mockup

draw.io files are plain XML (`mxfile` → `diagram` → `mxGraphModel` → `root` → many `mxCell`). For mockups, almost every cell is one of: a filled/stroked rectangle, a text overlay, or a "border with title" rounded rect. Master those three plus the style mini-language and you can author or edit mockups directly without opening the app.

## When to use

- Producing a `.drawio` mockup of a UI screen, dialog, settings panel, or TUI/CLI layout.
- Editing an existing `.drawio` file (renaming labels, adjusting colors, restyling) without opening drawio.
- Reviewing a mockup file and explaining what each cell does.
- Round-tripping a mockup with a human collaborator who edits in the app.

Skip this skill for: actual flowcharts/architecture diagrams (drawio's stencil libraries are better suited; just open the app), or anything that needs interactive layout — hand-authoring is for static mockups.

## File format at a glance

A drawio file is one of:

1. **Uncompressed XML** (the easy case — what every mockup in the wild uses, and what you should write). Looks like the example below.
2. **Compressed**: `<diagram>` body is base64(deflate(xml)). Web-app exports do this. To edit by hand, open in drawio and "Extras → Edit Diagram" or save with compression off.

Minimal uncompressed skeleton:

```xml
<mxfile host="Electron" version="29.6.6">
  <diagram name="Page-1" id="any-stable-id">
    <mxGraphModel dx="1100" dy="700" grid="0" gridSize="10" guides="1" tooltips="1"
                  connect="0" arrows="0" fold="0" page="1" pageScale="1"
                  pageWidth="1100" pageHeight="600" background="#000000" math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
        <!-- your cells here, all with parent="1" (or another container's id) -->
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>
```

Hard requirements:

- The two sentinel cells `id="0"` and `id="1" parent="0"` must exist exactly once. All user cells use `parent="1"` (or nest under another cell's id).
- Each `mxCell` is `vertex="1"` (a shape) or `edge="1"` (a connector). Mockups are 99% vertices.
- Every vertex needs `<mxGeometry x y width height as="geometry"/>`. Attribute order doesn't matter; `as="geometry"` does.
- IDs must be unique within the file. Any string works (drawio uses random base64-ish IDs; for hand-authored files, use readable slugs like `theme-label`, `modal-border`).
- Z-order is document order — later cells render on top. To put text over a box, the text cell must come *after* the box in `<root>`.

## The mxCell anatomy

```xml
<mxCell id="theme-label" parent="1" vertex="1"
        value="&lt;b&gt;Theme&lt;/b&gt;"
        style="text;html=1;strokeColor=none;fillColor=none;align=left;verticalAlign=middle;fontFamily=Courier New;fontSize=12;fontColor=#888888;">
  <mxGeometry x="97" y="26" width="600" height="18" as="geometry"/>
</mxCell>
```

Three things carry all the information:

- **`value`**: the visible text. With `html=1` in the style, `value` is HTML — but XML-escaped (`&lt;`, `&gt;`, `&quot;`, `&amp;`, `&amp;nbsp;`). Use this for any rich formatting (mixed colors, bold, font sizes, line breaks via `&lt;br&gt;`).
- **`style`**: a `;`-separated list of `key=value` (or bare flag) pairs. The first token is the *shape name* (`rounded`, `text`, `ellipse`, `mxgraph.mockup.containers.window`, etc.) — but for mockups you mostly want the implicit rectangle (just start with a key) or `text` for text-only cells.
- **`mxGeometry`**: position and size in page units. Origin is top-left, +Y down. `gridSize` (default 10) is just the snap grid; nothing forces alignment.

## Style mini-language: the keys you actually need

Layout / shape:

- `rounded=1;arcSize=N` — rounded rectangle, `arcSize` is corner percentage (try 2–15).
- `whiteSpace=wrap;html=1` — wrap long text and let `value` be HTML. Almost always set both.
- `text;` — the dedicated text shape. Combine with `strokeColor=none;fillColor=none;` for an invisible-background label.
- `shadow=1` — per-cell drop shadow.
- `rotation=90`, `direction=west|east|north|south` — rotate the shape *and* its text. Useful for vertical labels and rotated glyph icons.

Color (any of these accept `#RRGGBB`, `none`, or `light-dark(#LIGHT,#DARK)`):

- `fillColor`, `strokeColor`, `fontColor`
- `labelBackgroundColor` — solid color *behind* the text only (useful for "title sitting on a border" — see below).

Text:

- `align=left|center|right`, `verticalAlign=top|middle|bottom`
- `fontFamily=Courier New` (for TUI/CLI mockups), `fontSize=N`
- `fontStyle=N` where N is a bitmask: `1`=bold, `2`=italic, `4`=underline, `8`=strikethrough. Add them: bold-italic = `3`.
- `spacing=N` (all sides), or per-side: `spacingLeft`, `spacingTop`, `spacingRight`, `spacingBottom`.

Behavior (useful for keeping a finished mockup tidy):

- `editable=0`, `movable=0`, `resizable=0`, `rotatable=0`, `deletable=0`, `connectable=0` — lock cells.
- `pointerEvents=0` — clicks fall through to the cell underneath (great for transparent text overlays).
- `noLabel=1` — render the shape but ignore `value`.

## HTML inside `value` (the workhorse for mockups)

Once `html=1` is in the style, `value` is rendered as HTML. This is how every realistic mockup gets multi-color text, mixed weights, and inline icons:

```xml
value="&lt;font color=&quot;#55CCCC&quot;&gt;🤖 Sonnet 4.5&lt;/font&gt;&lt;font color=&quot;#666666&quot;&gt; | &lt;/font&gt;&lt;font color=&quot;#55CC55&quot;&gt;🌿 main ✓&lt;/font&gt;"
```

Tips:

- Entities are double-escaped because they live in an XML attribute: `&lt;` becomes `&amp;lt;` only if you *want a literal `&lt;` to render*. To produce a `<` in the rendered text, you write `&amp;lt;` in the attribute → `&lt;` in the HTML → `<` on screen.
- Whitespace collapses like in a browser. Use `&amp;nbsp;` for hard spaces (renders as `&nbsp;` → ` `). Multiple `&amp;nbsp;` in a row is the standard way to align columns in a TUI mockup.
- Line breaks: `&lt;br&gt;` (HTML break), not real newlines.
- Supported tags: `<b>`, `<i>`, `<u>`, `<span>`, `<font>`, `<div>`, `<br>`, `<sub>`, `<sup>`. CSS in `style="..."` works (background-color, font-size, line-height, color).
- Unicode glyphs (✓ ✎ ⌨ ⏎ ↑ ↓ ← → 🤖 📁 🌿 etc.) render fine — paste them literally into `value` (the XML is UTF-8). Common in TUI mockups for icons.

## Theme-aware colors

`light-dark(#LIGHTVALUE, #DARKVALUE)` works in any color attribute (style *or* inline HTML CSS). drawio picks the active value based on UI theme. Sample from a real mockup:

```
fontColor=light-dark(#000000,#888888)
strokeColor=light-dark(#000000,#5588FF)
```

```html
<font style="color: light-dark(rgb(136,136,136), rgb(85,136,255));">…</font>
```

Use this to make one mockup file render correctly against both light and dark backgrounds.

## Composition: how real mockups are built

Almost every panel in the sample mockups is the same three-cell sandwich:

1. **Filled background rect** (`rounded=1;fillColor=#0D1117;strokeColor=none;...`) — sized to the panel.
2. **Bordered title rect** (`rounded=1;fillColor=none;strokeColor=#555555;`, with a value like `<b>Preview</b>`, `align=left;verticalAlign=top;spacingTop=0;spacingLeft=6;`). This is *just a border with the title baked in as the rect's own label* — no separate text cell needed.
3. **Text overlay** (`text;html=1;strokeColor=none;fillColor=none;...` with rich HTML in `value`) — sized to fit *inside* the border rect. This holds the actual content.

### The titled-border trick (top groupbox label on the line)

The title is *the rect's own label* — you don't add a separate text cell for it. The full pattern:

- Set the value to your title (HTML allowed, e.g. `&lt;b&gt;Preview&lt;/b&gt;`).
- In the style: `align=left;verticalAlign=top;spacingTop=0;spacingLeft=6;labelBackgroundColor=#000000;` (matching `labelBackgroundColor` to the page/parent background "cuts" the border line behind the text).
- In the geometry, lift the label above the top edge with `<mxPoint as="offset">`:

```xml
<mxGeometry height="52" width="970" x="15" y="9" as="geometry">
  <mxPoint y="-13" as="offset"/>
</mxGeometry>
```

`<mxPoint as="offset">` shifts the *label only*, by x,y. Negative y lifts the title above the box's top edge so it overlaps the border line. Together with `labelBackgroundColor` matching the background, this is the classic dialog/groupbox titled-frame look. Tune the offset to roughly half the label height (e.g. `-13` for ~14px text).

## Tips and techniques (most-useful first)

1. **Stack three cells per panel** (filled bg → bordered title → text overlay). Don't try to cram fill + border + multi-color text into one cell — it fights you.
2. **Put rich content in HTML in `value`, not in the style.** The style is for the *container* (font size baseline, alignment, color of plain text). The `value` is where you mix colors and weights with `<font color="…">` and `<b>`.
3. **For TUI/CLI mockups, use `fontFamily=Courier New` + `&amp;nbsp;` columns.** Every row of the mockup is one `text` cell whose value is a string of nbsp-padded segments wrapped in colored `<font>` tags. This matches how real terminals render and aligns perfectly.
4. **Use `light-dark(...)` everywhere a viewer might switch themes.** Light-only mockups break ugly when pasted into a dark doc.
5. **Lock finished cells with `editable=0;movable=0;resizable=0`** before handing the file off — keeps a collaborator (or you, two months later) from nudging things accidentally.
6. **Add `pointerEvents=0` to all transparent text overlays** so clicks reach the panel underneath. Otherwise the overlay swallows clicks across its whole bounding box.
7. **Coordinate plan first.** Pick `pageWidth`/`pageHeight` to roughly match the target screen aspect, then sketch the panel boxes' x/y/width/height in a comment or scratchpad. Once panels are placed, text overlays just fill them.
8. **IDs can be human-readable.** drawio doesn't care — `modal-border`, `theme-label`, `help-keys` is fine and makes the file diff-friendly. Stable IDs across edits = clean PR diffs.
9. **Z-order = document order.** If a label is hidden behind a panel, move its `<mxCell>` *down* in the file. There's no z-index attribute.
10. **`gridSize=10` is the default snap grid; with `grid="0"` the grid is hidden but snapping still applies.** For pixel-perfect TUI alignment, set both `grid="0"` and place coordinates by hand.
11. **Round-tripping safely**: open in drawio, edit, save *uncompressed* (`File → Properties → Compressed: off`, or set this once globally) so the next text-edit pass still works. Compressed diagrams collapse to a single base64 blob.
12. **Inline icons from Unicode** (✎ ⌨ ⏎ ⏡ ⌫ ⏎ ↑ ↓ ← → ⇆ ●) are simpler than drawio's mockup stencils for most UI affordances and travel cleanly across themes. Bump `fontSize` on a single-glyph cell to scale.
13. **`fontStyle` is a bitmask, not an enum.** `fontStyle=5` = bold + underline (1+4). Easy to forget.
14. **Use `direction=west;rotation=90` together** to rotate a glyph (like a pencil ✎) and have it still read upright when oriented sideways.
15. **`arcSize` is *not* size-invariant.** It scales with the shorter side (`radius ≈ arcSize/200 × min(w,h)`), so the same value that looks fine on a small button comes out *over*-rounded on a large panel. Recipe to keep visual radius consistent across differently-sized rects: **larger shape → smaller `arcSize`; smaller shape → larger `arcSize`**. Real-mockup buckets that all land at ~2–8px radius: `arcSize=2` on full-screen frames (660×527), `~6` on mid panels (160×340), `~12–15` on thin strips and small chips (970×52, 60×30). If you want truly fixed pixel radius regardless of size, use `absoluteArcSize=1;arcSize=PX` (then `arcSize` is interpreted in pixels).

## Reading order when reviewing an existing file

1. Look at `<mxGraphModel>` attributes for canvas size and `background`.
2. Skim `<mxCell>` IDs — readable IDs tell you the panel structure.
3. For each cell, the trio `(value, style, geometry)` tells you *what / how / where*. Decode `style` first (it sets the rendering mode), then read `value` (which is HTML once `html=1` is set), then geometry (placement).
4. Cells appear in z-order (back to front) — the last text cells overlay everything earlier.

## Reference

- Minimal annotated template: `references/minimal-template.drawio`
- Style key list (pulled from real mockup files): `references/style-cheatsheet.md`
