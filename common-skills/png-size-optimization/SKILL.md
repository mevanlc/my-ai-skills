---
name: png-size-optimization
description: Optimize PNG image file size while preserving pixel dimensions. Use when the user asks to compress, compact, optimize, benchmark, or compare PNG screenshots or image assets without resizing, especially with oxipng, optipng, pngcrush, pngquant, or same-dimension PNG8/palette workflows.
---

# PNG Size Optimization

## Overview

Optimize PNGs without changing pixel dimensions. Treat lossless PNG recompression and lossy palette quantization as separate choices: `oxipng`, `optipng`, and `pngcrush` are lossless optimizers, while `pngquant` can produce much smaller indexed-color PNGs with slight visual loss.

## Workflow

1. Inspect the input files first:

```bash
file *.png
sips -g pixelWidth -g pixelHeight *.png 2>/dev/null || identify *.png
ls -lh *.png
```

2. Preserve originals unless the user explicitly asks to replace them. Prefer writing optimized copies to an output directory.

3. If the user wants lossless compression only, use `oxipng` first. It usually beats `optipng` and `pngcrush` on modern PNGs, and chaining the older tools before `oxipng` often yields only tiny extra savings.

```bash
oxipng -o max --strip safe output/*.png
```

4. If slight visual loss is acceptable, use `pngquant` followed by `oxipng`. This keeps dimensions unchanged but converts suitable images to indexed-color PNGs.

```bash
pngquant --speed 1 --strip --quality=80-95 --force --ext .png output/*.png
oxipng -o max --strip safe output/*.png
```

5. Verify dimensions and file type after optimization:

```bash
sips -g pixelWidth -g pixelHeight output/*.png
file output/*.png
ls -lh output/*.png
```

## Helper Script

Use the bundled helper for repeatable batch work:

```bash
common-skills/png-size-optimization/scripts/optimize_png_size.sh \
  --out-dir pngquant-oxipng-out \
  image1.png image2.png
```

Useful modes:

```bash
# Default: pngquant quality 80-95, then oxipng.
scripts/optimize_png_size.sh --out-dir optimized *.png

# Lossless only.
scripts/optimize_png_size.sh --lossless-only --out-dir optimized *.png

# Benchmark tools on temporary copies; originals are unchanged.
scripts/optimize_png_size.sh --benchmark *.png

# Replace originals only when explicitly requested by the user.
scripts/optimize_png_size.sh --in-place *.png
```

The script checks required tools with `which`, refuses to overwrite inputs unless `--in-place` is set, and reports byte sizes before and after.

## Tool Selection

- `oxipng`: best default lossless optimizer; use `-o max --strip safe` when runtime is not a concern.
- `optipng`: useful fallback if `oxipng` is unavailable; use `-o7 -strip all`.
- `pngcrush`: useful fallback or comparison tool; use `-brute -reduce -rem alla`.
- `pngquant`: best size reduction for screenshots, UI captures, forms, diagrams, and other low-color images when visually acceptable palette quantization is allowed.

## Reporting

In the final answer, include:

- output path or whether files were replaced in place
- before/after sizes and percent savings when available
- confirmation that dimensions were preserved
- whether the result is lossless or uses `pngquant` palette quantization
