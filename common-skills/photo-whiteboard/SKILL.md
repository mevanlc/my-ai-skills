---
name: Photo to Whiteboard
description: Use when the user invokes the skill or wants to apply a whiteboard effect to an image.
---

# Photo to Whiteboard

Convert phone photos of documents (tax forms, statements, receipts, letters) into clean,
compressed, whiteboard-style images. Applies lighting normalization, contrast enhancement,
and color reduction to produce scanlike output at 85-90% smaller file sizes.

## When to Use

- Processing photos of paper documents for archival
- Preparing document images for a git repo (size matters)
- Cleaning up uneven lighting, shadows, and background clutter from phone photos
- Batch processing a folder of document photos

## Requirements

ImageMagick 7+ must be available as `magick`. Install with `brew install imagemagick` on
macOS or equivalent on other platforms.

## Quick Start

The bundled script handles both single files and batch directories:

```bash
# Single file
scripts/whiteboard.sh photo.jpg                    # → photo.png (same dir)
scripts/whiteboard.sh photo.jpg clean.png          # → clean.png

# Batch — all images in a directory
scripts/whiteboard.sh /path/to/photos/ /path/to/output/
```

## Default Pipeline

The default processing pipeline, tuned for document photos:

1. **Resize 80%** — reduce pixel count while preserving text legibility
2. **Auto-trim** — crop background/desk from edges
3. **Grayscale** — documents don't need color
4. **Normalize** — stretch histogram to full range
5. **Sigmoidal contrast (15, 60%)** — enhance text/line contrast with an S-curve (gentler than threshold)
6. **Posterize 3** — reduce to 3 tonal levels (black, gray, white)
7. **PNG8 output** — indexed-color PNG compresses well for low-color images

This produces clean, legible images at ~150-350KB per document photo (down from 1.5-2.5MB originals).

## Tuning Parameters

All parameters are controlled via environment variables:

| Variable       | Default | Description                                            |
|----------------|---------|--------------------------------------------------------|
| `WB_RESIZE`    |      80 | Resize percentage (clamped by WB_MIN_DIM)              |
| `WB_MIN_DIM`   |     800 | Minimum output dimension in px (prevents over-shrink)  |
| `WB_CONTRAST`  |      15 | Sigmoidal contrast strength (higher = harsher)         |
| `WB_MIDPOINT`  |      60 | Sigmoidal midpoint (higher = whiter background)    |
| `WB_COLORS`    |       3 | Posterize levels (2=mono, 3=default, 4=softer)     |
| `WB_FORMAT`    |     png | Output format: png or jpg                          |
| `WB_QUALITY`   |      75 | JPEG quality (only when WB_FORMAT=jpg)             |
| `WB_MONO`      |       0 | Set to 1 for hard black/white threshold            |
| `WB_THRESHOLD` |      60 | Threshold % for mono mode (higher = whiter)        |
| `WB_SKIP_TRIM` |       0 | Set to 1 to disable auto-trim                     |

### Common Presets

**Maximum compression (mono, smallest files):**
```bash
WB_MONO=1 WB_THRESHOLD=60 scripts/whiteboard.sh input/ output/
```

**Softer output (4 gray levels, more detail preserved):**
```bash
WB_COLORS=4 scripts/whiteboard.sh input/ output/
```

**Higher resolution (for fine print or dense tables):**
```bash
WB_RESIZE=100 scripts/whiteboard.sh input/ output/
```

**Quick comparison (generate multiple variants for user review):**
```bash
for pct in 60 80 100; do
  WB_RESIZE=$pct scripts/whiteboard.sh doc.jpg /tmp/compare/doc_${pct}.png
done
```

## Iterative Tuning Workflow

When processing a new batch of document photos, use this workflow:

1. **Process one sample image** with defaults to check quality
2. **Generate comparison variants** if defaults aren't ideal — vary resize, contrast, or colors
3. **Crop a detail region** for side-by-side comparison of small text legibility
4. **Apply chosen settings** to the full batch

To crop a detail region for comparison:
```bash
magick input.png -crop WxH+X+Y +repage cropped.png
```

## Troubleshooting

**Large dark regions / blown-out areas:** The source photo has very uneven lighting. Try the
divide-normalize approach instead of sigmoidal contrast:
```bash
magick input.jpg -resize 80% -trim +repage -colorspace gray \
  \( +clone -blur 0x30 \) -compose divide -composite \
  -normalize -level 15%,95% -posterize 3 \
  PNG8:output.png
```

**Text too faint:** Lower the midpoint to darken: `WB_MIDPOINT=50`

**Text too bold/bleeding:** Raise the midpoint: `WB_MIDPOINT=70`

**Background not clean white:** Increase contrast strength: `WB_CONTRAST=20`

## Script Reference

The processing script is at `scripts/whiteboard.sh`. Run without arguments for usage.
It reports per-file and total compression ratios when processing.
