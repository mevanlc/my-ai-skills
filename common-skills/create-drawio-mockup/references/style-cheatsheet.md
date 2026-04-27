# drawio style cheat-sheet (mockup-focused)

Style is a `;`-separated list of `key=value` (or bare-flag) pairs on `mxCell.style`. Below: the subset that pulls real weight in mockup files.

## Shape selectors (first token)

| Token | Meaning |
|---|---|
| *(none)* | Default rectangle (most common for filled panels). |
| `rounded` | Bare flag → rounded rectangle. Pair with `arcSize=N`. |
| `text` | Pure text shape — set `strokeColor=none;fillColor=none;` for a transparent label. |
| `ellipse` | Circle/ellipse. |
| `line` | Horizontal line; height becomes line thickness. |
| `mxgraph.mockup.*` | drawio's mockup stencils (window chrome, buttons, etc.). Most hand-authored mockups skip these in favor of plain rects + Unicode. |

## Layout & shape

| Key | Notes |
|---|---|
| `rounded=1` | Rounded corners. Implied if first token is `rounded`. |
| `arcSize=N` | Corner radius scaled to the shorter side (`radius ≈ N/200 × min(w,h)`) — *not* size-invariant. Larger shape → smaller `arcSize`; smaller shape → larger `arcSize`. Real-mockup buckets: ~12–15 thin strips/chips, ~6–8 mid panels, ~2 large frames (all ≈ 2–8px visual radius). |
| `absoluteArcSize=1` | Reinterpret `arcSize` as **pixels** so radius stays constant across rect sizes. |
| `whiteSpace=wrap` | Wrap long values. Almost always set. |
| `html=1` | Treat `value` as HTML. Almost always set. |
| `shadow=1` | Drop shadow on this cell. |
| `rotation=DEG` | Rotate cell + label. |
| `direction=west\|east\|north\|south` | Reorient the shape (combine with `rotation` for sideways glyphs). |
| `glass=1` | Glassy gradient (rare in mockups). |

## Color

Accepts `#RRGGBB`, `none`, `default`, or `light-dark(#LIGHT,#DARK)` for theme-adaptive.

| Key | What it colors |
|---|---|
| `fillColor` | Interior of the shape. |
| `strokeColor` | Border. |
| `fontColor` | Label text. |
| `labelBackgroundColor` | Solid bg behind label only — used for the "title sits on the border line" effect. |
| `gradientColor` | Gradient fill secondary. |

## Text & alignment

| Key | Notes |
|---|---|
| `align=left\|center\|right` | Horizontal label alignment. |
| `verticalAlign=top\|middle\|bottom` | Vertical label alignment. |
| `fontFamily=...` | `Courier New` for TUI mockups; `Helvetica` / `Verdana` otherwise. |
| `fontSize=N` | Px. |
| `fontStyle=N` | Bitmask: `1`=bold, `2`=italic, `4`=underline, `8`=strike. Add. |
| `spacing=N` | Padding all sides. |
| `spacingLeft / spacingTop / spacingRight / spacingBottom` | Per-side. |

## Behavior / interaction

| Key | Notes |
|---|---|
| `editable=0` | Lock label text editing. |
| `movable=0` | Pin in place. |
| `resizable=0` | Lock geometry. |
| `rotatable=0` | Disable rotate handle. |
| `deletable=0` | Survive accidental Delete. |
| `connectable=0` | No edges allowed in/out. |
| `pointerEvents=0` | Clicks fall through — set on transparent overlay text so it doesn't eat clicks. |
| `noLabel=1` | Render shape without rendering `value`. |

## HTML in `value` (when `html=1`)

`value` is XML-escaped HTML. Key entities (the literal text you write):

| You write | Renders |
|---|---|
| `&amp;lt;` `&amp;gt;` | `<` `>` |
| `&amp;quot;` | `"` |
| `&amp;amp;` | `&` |
| `&amp;nbsp;` | non-breaking space (use for column alignment in TUIs) |
| `&lt;br&gt;` | line break |
| `&lt;b&gt;…&lt;/b&gt;` | bold |
| `&lt;font color=&quot;#XXXXXX&quot;&gt;…&lt;/font&gt;` | colored span |
| `&lt;span style=&quot;background-color:#XXX;color:#YYY;&quot;&gt;…&lt;/span&gt;` | inline CSS, including `light-dark(...)` |

## Geometry quirks

- `<mxGeometry x y width height as="geometry"/>` is required on every vertex.
- `<mxPoint x y as="offset"/>` *inside* the geometry shifts the label only — used to lift a title onto the top border line (`y` negative).
- `<mxPoint as="sourcePoint"/>` / `as="targetPoint"` apply to edges, not vertices.
- Origin (0,0) is top-left; positive Y goes down. No z-index — z-order is document order in `<root>`.

## Edges (rare in mockups, but for completeness)

```xml
<mxCell id="e1" parent="1" edge="1" source="srcId" target="tgtId"
        style="endArrow=classic;html=1;edgeStyle=orthogonalEdgeStyle;rounded=0;">
  <mxGeometry relative="1" as="geometry"/>
</mxCell>
```

Useful edge styles: `endArrow=none|classic|open`, `dashed=1`, `edgeStyle=orthogonalEdgeStyle|elbowEdgeStyle`, `curved=1`, `exitX/exitY/entryX/entryY` (0–1 floats) for fixed connection points.
