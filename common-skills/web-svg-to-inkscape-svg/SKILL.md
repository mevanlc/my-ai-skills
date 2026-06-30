---
name: web-svg-to-inkscape-svg
description: Convert browser-oriented SVG into Inkscape-compatible SVG. Use when an SVG copied or generated from a web app, browser DOM, React/JSX, HTML page, inline CSS, CSS variables, currentColor, foreignObject, external styles, or modern browser color/CSS features needs to open and remain editable in Inkscape with visual fidelity checked against a browser rendering.
---

# Web SVG to Inkscape SVG

## Overview

Convert from browser rendering semantics to an SVG document Inkscape can parse, display, and edit predictably. Treat this as a fidelity workflow: first make the markup XML/SVG-compatible, then resolve browser-only styling where needed, then round-trip through Inkscape as Plain SVG, and finally compare browser and Inkscape outputs.

## Workflow

### 1. Preserve the input

Work from a copy. Do not overwrite the source SVG until the converted output has been opened or rendered successfully.

Check context:

```bash
which inkscape
inkscape --version
```

If you need source-backed confirmation for Inkscape behavior, inspect `~/p/gh/inkscape/man/inkscape.pod.in` for `--export-plain-svg` and `~/p/gh/inkscape/src/extension/internal/svg.cpp` for the distinction between `Inkscape SVG (*.svg)` and `Plain SVG (*.svg)`.

If you need browser-side reference, inspect `~/p/gh/mdn-docs-repo-full/files/en-us/web/svg/` and `~/p/gh/mdn-docs-repo-full/files/en-us/web/css/`.

### 2. Classify the SVG

Look for constructs that browsers handle differently from Inkscape:

```bash
rg -n "<foreignObject|<style|class=|var\\(|currentColor|<script|xml-stylesheet|@import|https?://" input.svg
```

Decision points:

- JSX or React-exported attribute names such as `strokeWidth`, `stopColor`, `fontSize`, `textAnchor`, `className`, or `xlinkHref`: normalize to XML/SVG names before any renderer test.
- `<style>`, `class`, CSS variables, `currentColor`, external stylesheets, or modern CSS color functions: render in a browser or otherwise inline computed styles before expecting Inkscape fidelity.
- `<foreignObject>`: decide explicitly. For editable output, replace the embedded HTML with SVG text/shapes manually or with a browser-assisted extraction. For visual-only output, rasterize that region or the whole SVG.
- Remote images, web fonts, scripts, animations, and interaction: freeze to static local assets or remove. Inkscape is not a browser runtime.

MDN notes that `foreignObject` includes content from another XML namespace, most often XHTML in browsers. MDN also documents that SVG presentation attributes can have CSS-property counterparts and that CSS takes priority when both are present. Use a browser-computed pass whenever that precedence matters.

### 3. Run the helper normalization

Use the bundled helper for the deterministic first pass:

```bash
python3 common-skills/web-svg-to-inkscape-svg/scripts/web_svg_to_inkscape_svg.py \
  input.svg \
  output.inkscape.svg \
  --json-report output.inkscape.report.json \
  --keep-work
```

The helper:

- normalizes common JSX-style SVG attributes to standalone SVG/XML names
- adds missing root `xmlns` and `xmlns:xlink` declarations when needed
- replaces a few HTML-only whitespace entities with XML numeric entities
- validates XML parsing before invoking Inkscape
- runs `inkscape --export-type=svg --export-plain-svg --export-filename=<output>` unless `--no-inkscape` is passed
- reports risk markers that still need browser-assisted handling

Useful flags:

```bash
python3 common-skills/web-svg-to-inkscape-svg/scripts/web_svg_to_inkscape_svg.py input.svg output.svg --no-inkscape
python3 common-skills/web-svg-to-inkscape-svg/scripts/web_svg_to_inkscape_svg.py input.svg output.svg --text-to-path
python3 common-skills/web-svg-to-inkscape-svg/scripts/web_svg_to_inkscape_svg.py input.svg output.svg --area-drawing
python3 common-skills/web-svg-to-inkscape-svg/scripts/web_svg_to_inkscape_svg.py input.svg output.svg --strip-scripts
```

Use `--text-to-path` only when editability of text is less important than preserving appearance without the original fonts.

### 4. Resolve browser styling when needed

If the report flags CSS-dependent constructs, do not assume the Inkscape output is visually correct. Open the original SVG in a browser and extract or recreate the static computed result.

Prefer these strategies, in order:

1. Inline CSS into presentation attributes or `style` attributes on the actual SVG elements.
2. Expand `var(...)`, `currentColor`, inherited group presentation attributes, and CSS geometry properties to concrete values on affected elements.
3. Convert unsupported HTML-in-SVG regions to native SVG text/shapes if editability matters.
4. Rasterize only the unsupported region when exact visual fidelity matters more than editability.
5. Rasterize the whole SVG only as the last resort.

For browser-computed extraction, use the browser DOM as the authority for computed values, not hand-written selector parsing. Save a static SVG from the rendered DOM, then run the helper and Inkscape pass again.

### 5. Verify fidelity

Always verify both parseability and visual output:

```bash
inkscape output.inkscape.svg --export-type=png --export-filename=output.inkscape.png
```

Also render the original in a browser to PNG if visual fidelity matters. Compare the original-browser PNG against the Inkscape-exported PNG. If the original uses filters, masks, blend modes, `foreignObject`, CSS variables, or web fonts, visual comparison is mandatory.

## Common Fixes

- Browser preview is correct but saved `.svg` has thin strokes, missing glow, or wrong colors: inspect the exported markup for JSX-style names such as `strokeWidth`, `stopColor`, `fontSize`, and `textAnchor`; normalize them before debugging filters.
- Inkscape opens the file but classes or CSS variables are ignored or stale: inline browser-computed styles and remove dependency on selectors or custom properties.
- Inkscape drops or fails to render HTML inside `<foreignObject>`: replace that content with SVG elements or rasterize the region.
- Output differs only in text layout: install the same fonts or rerun with `--text-to-path`.
- External images disappear: download them, update `href` to local or data URLs, and rerun.

## Safety Rules

- Preserve the original SVG and produce a new file.
- Prefer editable SVG output, but state when a raster fallback was used.
- Treat browser rendering as the source of truth for web CSS features.
- Treat Inkscape Plain SVG export as the compatibility pass, not as proof of visual fidelity.
- Report remaining risk markers and verification commands in the final answer.
