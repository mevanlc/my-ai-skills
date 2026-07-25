---
name: screenshot-based-visual-refactoring
description: Diff screenshots of an interface's current state against its desired target state by decomposing each screen into corresponding semantic regions, inspecting focused crop pairs, tracing relocations and interaction changes, and synthesizing the result into a coherent refactor description — then, unless the user asks for analysis only, implement the refactor in the associated codebase, iterating until the rendered UI matches the target. Use when a user supplies current and target screenshots and wants the interface change implemented, or wants a detailed visual comparison, mutation inventory, design-archaeology account, implementation brief, or review of how an interface changed.
---

# Screenshot-based Visual Refactoring

## Purpose

Use two screenshots — the interface's current state and its desired target
state — as evidence for describing how the visual organization changes, and as
the diff that steers implementation from one to the other. Reduce the cognitive
load of a whole-screen comparison by isolating corresponding semantic regions,
examining one pair at a time, and building an evolving written account. The
same technique describes an already-completed refactor: treat the earlier
screenshot as current and the later one as target.

Treat this as an adaptable analysis technique rather than a rigid pipeline.
Choose region granularity, tooling, output structure, and measurement precision
to suit the screenshots and the user's goal.

## Implementing the refactor

Unless the user requests analysis only, treat invocation of this skill as a
request to implement the refactoring in the associated codebase. The comparison
workflow below then plays two roles: first it specifies the desired end state,
then it checks the work. After each change, capture fresh screenshots of the
application's current state and diff them against the target using the same
region-pair techniques, treating the remaining deltas as the next round of
changes.

If computer-use skills or tools can give visual screenshot access to your code
revisions, use them rather than reasoning about the rendered result from the
code alone. When more than one computer-use toolset is available and one is not
working for the app in question, try the others; do not assume they will also
fail.

Expect a number of iterations as the current state converges on the target.
Judge each iteration by the visual and design deltas it removes, not by the
code diff alone.

## Bundled diff tool

`scripts/screenshot-diff.py` (resolved relative to this skill's directory)
mechanizes the pixel-level comparison. It is a self-contained uv script:

```bash
uv run <skill-dir>/scripts/screenshot-diff.py current.png target.png -o diffs/
```

It accepts full screenshots or individual region-crop pairs. One invocation
writes several complementary views plus `summary.json`:

| Output | Use it to |
| --- | --- |
| `01-blend.png` | See both states at once; relocations appear as ghosting |
| `02-absdiff.png` | Amplified subtractive difference; fast "where did anything change" |
| `03-heat.png` | Perceptual CIEDE2000 delta-E magnitude; separates real change from rendering noise |
| `04-mask.png` | Binary change mask after thresholding and noise cleanup |
| `05/06-boxes-*.png` | Current and target annotated with numbered change-cluster boxes matching `summary.json` |
| `07-edges.png` | Structure diff: red edges exist only in current, green only in target, gray shared |
| `08-ssim.png` | Structural dissimilarity; emphasizes layout and texture change over flat color shifts |

The stdout report and `summary.json` include percent of pixels changed,
mean and p99 delta-E, an SSIM score, per-cluster bounding boxes, and a
global-shift estimate that is flagged only when shifting the current image
actually explains most of the diff — use that flag to catch scroll or layout
offsets before chasing per-pixel deltas. Exit status is 0 when nothing
survives the threshold and 1 when changes were found, so an implementation
loop can gate on it.

Tune `--threshold` (delta-E, default 4.0) and `--blur` when anti-aliasing or
subpixel rendering produces false positives, and `--min-area` to ignore
scattered noise. Treat the outputs as attention guides for the region-pair
workflow, not as a replacement for inspecting the native crops: the tool
localizes change but cannot classify a relocation, restyle, or removal.

## Guiding ideas

- Prefer semantic correspondence over equal coordinates. A region can move,
  resize, split, merge, or change row number while retaining the same purpose.
- Inspect focused crops without losing awareness of the full screens. Local
  attention reveals details; whole-screen context reveals relocations and gaps.
- Preserve literal on-screen evidence. Distinguish text, values, state, and
  behavior instead of smoothing them into a generic interpretation.
- Separate observation from inference. A static screenshot shows appearance and
  state, but usually cannot prove what a control does or whether absent
  functionality was removed.
- Let the written description evolve. Later regions or user clarifications may
  explain an earlier apparent removal as a relocation or overloaded interaction.
- Favor useful qualitative conclusions over false pixel precision. Record exact
  crop rectangles, but use approximate component coordinates when antialiasing,
  shadows, or soft boundaries make exactness unhelpful.

## Suggested workflow

### Orient on the full screenshots

View both originals before cropping. Prefer native resolution when available.

- Record each image's pixel dimensions and note differing viewport sizes, device
  scale factors, browser chrome, system chrome, or captured scroll positions.
- Identify the application bounds and decide which surrounding chrome belongs in
  scope.
- Notice the broad layout skeleton: primary columns, sidebars, header stacks,
  content panes, fixed footers, modals, and large blank or repeated areas.
- Note obvious state differences such as selection, hover, loading, animation,
  scroll position, or different underlying content. Avoid treating those as
  refactoring until the evidence supports it.

### Sketch a semantic region map

Name areas by responsibility rather than location alone. Names such as
`navigation-sidebar`, `document-header`, `view-controls`, or `status-footer`
usually survive layout changes better than `upper-strip-2`.

Allow asymmetric pairings:

- Pair regions with different rectangles and dimensions.
- Pair a later apparent row in the current screen with an earlier row in the
  target when preceding rows were removed or absorbed elsewhere.
- Pair several stacked current-screen bands with one consolidated target
  toolbar when their roles merge.
- Represent non-contiguous consolidation as one-to-many or many-to-one when a
  new region draws from several distant old regions. Do not force unrelated
  source areas into one rectangular crop merely to preserve a one-pair model.
- Split one broad current-screen area into several target areas, or the
  reverse, when that better represents the change.
- Allow crops to overlap when one control or destination participates in more
  than one useful semantic comparison. The region map is an analysis aid, not a
  destructive partition that must tile each screenshot exactly once.
- Keep unmatched regions on a short audit list rather than forcing a misleading
  pair.

Start with a manageable map. Refine boundaries when close inspection shows that
a crop combines unrelated responsibilities or cuts through a meaningful control.

### Create and verify focused crops

Preserve the originals and write crops to clearly paired locations when the
workspace permits, for example:

```text
current/navigation-sidebar.png
target/navigation-sidebar.png
current/document-header.png
target/document-header.png
```

Record crop rectangles as `(x, y, width, height)` in native-image pixels. For a
simple pair, keep the two rectangles independent. When correspondence spans
non-contiguous areas, choose whichever representation keeps the evidence clear:

- create several source crops that point to the same destination crop,
- reuse or overlap a crop in more than one semantic pairing,
- create a clearly labeled analysis-only composite or contact view, or
- keep one primary crop pair and record the other origins in the relocation
  ledger.

Treat composites as navigation or explanation aids rather than spatially exact
screenshots. Preserve the individual native crops so their true positions and
pixel geometry remain available.

Use any reliable image tool. With ImageMagick, a minimal pattern is:

```bash
magick identify current.png target.png
magick current.png -crop WIDTHxHEIGHT+X+Y +repage current/region.png
magick target.png -crop WIDTHxHEIGHT+X+Y +repage target/region.png
```

Avoid resizing the deliverable crops. Magnified temporary copies can help inspect
small text or icons, and a contact sheet can help navigate the set, but neither
should replace native-resolution inspection of each pair.

Assign shared borders and divider pixels consistently. Including a separator in
the sidebar crop and excluding it from the adjacent header crop is often clearer
than duplicating it, but either choice can work when documented and applied
consistently.

After cropping, verify that each file:

- contains the full intended responsibility,
- excludes unrelated neighboring content where practical,
- preserves native pixels and aspect ratio,
- has not clipped focus rings, shadows, labels, or edge controls, and
- forms a meaningful comparison with its counterpart.

### Examine one region pair at a time

Give each pair a dedicated pass. View the complete crop first, then zoom into
subareas when the region is tall or dense. Consider whichever lenses illuminate
the change:

| Lens | Useful observations |
| --- | --- |
| Content | Added, removed, retained, renamed, reordered, or dynamically changed information |
| Hierarchy | Primary heading, secondary metadata, emphasis, scanning order, and grouping |
| Geometry | Dimensions, padding, alignment, density, row count, and reclaimed space |
| Controls | Added, moved, consolidated, relabeled, iconified, or apparently absent actions |
| Style | Typography, color roles, borders, fills, radii, icons, and contrast |
| State | Selection, scroll, hover, disabled appearance, counters, and data-dependent values |
| Continuity | Components and conventions deliberately preserved across the refactor |
| Evidence | What is directly visible, reasonably inferred, or behaviorally confirmed |

Describe the observed outcome before interpreting its design intent. When exact
numbers help, compare region dimensions or major offsets. When they do not,
describe relative movement and density instead.

### Trace relocations across regions

Maintain a lightweight mapping ledger as the analysis grows. For each apparently
missing item, consider whether it was:

- moved to another visible region,
- folded into a modal, menu, tooltip, or expandable surface,
- overloaded onto an icon or larger clickable target,
- made implicit by the new layout,
- replaced by a related control, or
- genuinely removed.

Use careful language until behavior is known:

- Prefer “no visible counterpart in this screenshot” over “removed” when only
  static evidence is available.
- Prefer “the text label disappears while the action moves to the icon” when
  behavior has been confirmed.
- Identify values that vary by record, run, user, or state as dynamic values—not
  static labels merely because one screenshot shows one instance.
- Incorporate user or source-code clarification explicitly, and revise earlier
  sections that it changes.

For example, the current screen might show three stacked toolbar bands while
the target consolidates all three into one line. Treat the union as the
meaningful pair. Likewise, a vanished `Open` label need not mean the action was
removed if a nearby document icon now carries it.

### Build the document incrementally

Append one region section after each focused comparison. Use a consistent shape
without forcing empty headings. A flexible pattern is:

```markdown
## <Semantic region>

Region dimensions: current is ...; target is ...

### Summary

<The main change in purpose or composition.>

### Content and hierarchy

<Literal additions, removals, movements, and preserved information.>

### Controls and layout

<Geometry, interaction surfaces, grouping, and density.>

### Retained styling and uncertainties

<Continuities, evidence limits, and unresolved details.>
```

Keep the document coherent rather than append-only in meaning. Update earlier
sections when a later crop reveals an origin or destination, when dynamic content
was mistaken for static text, or when behavior clarifies an icon-only control.

### Return to the full screens

After all planned pairs, perform a whole-screen audit.

- Revisit unmatched areas, especially extra rows in one version that disappeared
  from the pairing scheme.
- Trace every significant relocation across region boundaries.
- Compare cumulative header/sidebar dimensions and calculate reclaimed content
  space when that supports the design story.
- Account for differing screenshot heights before claiming that one layout shows
  more content.
- Confirm that blank, unchanged, or out-of-scope areas are intentionally omitted.
- Summarize the overall strategy, retained visual language, and usability or
  discoverability tradeoffs.

A compact cross-region mapping table often makes the final synthesis clearer:

```markdown
| Current element | Target treatment |
| --- | --- |
| Run summary | Moved into the corner dashboard |
| Labeled action | Overloaded onto the adjacent icon |
| Three control bands | Consolidated into one toolbar |
```

Use only enough examples to show the mapping pattern; keep the final document
grounded in the application actually being analyzed.

## Evidence discipline

Use three implicit evidence levels throughout the narrative:

1. **Visible:** directly supported by pixels, dimensions, or literal text.
2. **Inferred:** a plausible design interpretation, labeled as such.
3. **Confirmed behavior:** supplied by the user, implementation, or an interactive
   test beyond the static screenshots.

Do not let polished prose erase ambiguity. Preserve anomalies such as a counter
that renders unexpectedly, a selection marker that disagrees with a selected
card, or a control whose destination is unknown. These details can reveal bugs,
unfinished work, or useful follow-up questions.

When the screenshot state differs, describe the difference separately from the
refactor. A changed selected row, scroll thumb, timestamp, dataset, or variable
value may be incidental even when it is visually prominent.

## Common traps

- Avoid forcing equal crop sizes or coordinates merely to make a contact sheet
  look tidy.
- Avoid pairing rows by ordinal position when semantic roles shifted.
- Avoid analyzing the entire screen at full detail in one pass; local details and
  cross-region movements are easier to miss.
- Avoid treating every absent label as removed functionality.
- Avoid treating sample data or run-specific values as fixed interface copy.
- Avoid drawing behavioral conclusions from icon appearance alone.
- Avoid finalizing before returning to the uncropped originals.
- Avoid turning the report into an implementation prescription unless the user
  asks for one. Describe the refactor faithfully before recommending changes.

## Completion check

Consider the analysis complete when:

- each planned semantic pair has a focused comparison,
- unmatched full-screen regions have been reviewed,
- important moved elements have origins and destinations,
- visible changes are separated from confirmed behavior and inference,
- dynamic state is not mislabeled as static design,
- cumulative geometry claims account for viewport differences,
- user clarifications are reflected everywhere they matter, and
- the final synthesis explains both the local mutations and the larger design
  direction without overfitting to one application's terminology.
