#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy",
#   "pillow",
#   "scikit-image>=0.26",
# ]
# ///
"""Diff two UI screenshots and emit several complementary visualizations.

Given a current-state and a target-state screenshot, writes an output
directory containing:

  01-blend.png         50/50 onion-skin blend of both images
  02-absdiff.png       amplified grayscale subtractive difference
  03-heat.png          CIEDE2000 delta-E perceptual difference heatmap
  04-mask.png          cleaned binary change mask
  05-boxes-current.png current image annotated with change-cluster boxes
  06-boxes-target.png  target image annotated with change-cluster boxes
  07-edges.png         edge diff (red: current-only, green: target-only)
  08-ssim.png          structural dissimilarity map (SSIM-based)
  summary.json         metrics and cluster inventory

Exit status: 0 when no changes survive the threshold, 1 when changes were
found, 2 on usage or processing errors.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from skimage import color, feature, filters, measure, morphology
from skimage.metrics import structural_similarity
from skimage.registration import phase_cross_correlation

PAD_COLOR = (255, 0, 255)  # magenta: pixels that exist in only one image
HEAT_SCALE_DELTA_E = 25.0  # delta-E mapped to the top of the heat colormap
# black -> deep purple -> red -> orange -> yellow -> white
HEAT_ANCHORS = np.array(
    [
        (0.00, (0, 0, 0)),
        (0.25, (80, 0, 120)),
        (0.50, (200, 40, 30)),
        (0.75, (255, 160, 20)),
        (0.90, (255, 230, 90)),
        (1.00, (255, 255, 255)),
    ],
    dtype=object,
)


def load_rgb(path: Path) -> np.ndarray:
    img = Image.open(path).convert("RGBA")
    background = Image.new("RGBA", img.size, (255, 255, 255, 255))
    return np.asarray(Image.alpha_composite(background, img).convert("RGB"))


def pad_to_canvas(arr: np.ndarray, canvas_hw: tuple[int, int]) -> np.ndarray:
    canvas = np.empty((*canvas_hw, 3), dtype=np.uint8)
    canvas[:, :] = PAD_COLOR
    canvas[: arr.shape[0], : arr.shape[1]] = arr
    return canvas


def colormap(norm: np.ndarray) -> np.ndarray:
    stops = np.array([float(s) for s, _ in HEAT_ANCHORS])
    colors = np.array([c for _, c in HEAT_ANCHORS], dtype=float)
    out = np.empty((*norm.shape, 3), dtype=np.uint8)
    for ch in range(3):
        out[..., ch] = np.interp(norm, stops, colors[:, ch]).astype(np.uint8)
    return out


def to_image(arr: np.ndarray) -> Image.Image:
    return Image.fromarray(arr.astype(np.uint8))


def load_font(size: int = 14) -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def draw_boxes(base: np.ndarray, clusters: list[dict]) -> Image.Image:
    img = to_image(base).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = load_font()
    for cl in clusters:
        x, y, w, h = cl["bbox"]
        draw.rectangle([x - 1, y - 1, x + w, y + h], outline=(255, 0, 0), width=2)
        label = str(cl["id"])
        tx, ty = x + 2, max(0, y - 16)
        bbox = draw.textbbox((tx, ty), label, font=font)
        draw.rectangle(bbox, fill=(255, 0, 0))
        draw.text((tx, ty), label, fill=(255, 255, 255), font=font)
    return img


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diff two UI screenshots into multiple visualizations.",
    )
    parser.add_argument("current", type=Path, help="screenshot of the current state")
    parser.add_argument("target", type=Path, help="screenshot of the desired state")
    parser.add_argument(
        "-o", "--outdir", type=Path, default=Path("screenshot-diff"),
        help="output directory (default: ./screenshot-diff)",
    )
    parser.add_argument(
        "--threshold", type=float, default=4.0,
        help="CIEDE2000 delta-E change threshold (default: 4.0; ~2 is the "
        "perceptibility limit, higher tolerates more rendering noise)",
    )
    parser.add_argument(
        "--blur", type=float, default=0.5,
        help="Gaussian sigma applied before comparison to damp anti-aliasing "
        "and subpixel noise (default: 0.5; 0 disables)",
    )
    parser.add_argument(
        "--min-area", type=int, default=12,
        help="ignore change clusters smaller than this many pixels (default: 12)",
    )
    parser.add_argument(
        "--max-clusters", type=int, default=40,
        help="cap on reported/annotated clusters, largest first (default: 40)",
    )
    parser.add_argument(
        "--gain", type=float, default=4.0,
        help="brightness multiplier for the subtractive diff (default: 4.0)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the summary as JSON to stdout instead of human-readable text",
    )
    args = parser.parse_args()

    for path in (args.current, args.target):
        if not path.is_file():
            print(f"error: not a file: {path}", file=sys.stderr)
            return 2

    cur = load_rgb(args.current)
    tgt = load_rgb(args.target)
    size_mismatch = cur.shape != tgt.shape
    canvas_hw = (max(cur.shape[0], tgt.shape[0]), max(cur.shape[1], tgt.shape[1]))
    valid = np.zeros(canvas_hw, dtype=bool)
    valid[: min(cur.shape[0], tgt.shape[0]), : min(cur.shape[1], tgt.shape[1])] = True
    cur = pad_to_canvas(cur, canvas_hw)
    tgt = pad_to_canvas(tgt, canvas_hw)

    cur_f = cur.astype(np.float64) / 255.0
    tgt_f = tgt.astype(np.float64) / 255.0
    if args.blur > 0:
        cur_f = filters.gaussian(cur_f, sigma=args.blur, channel_axis=-1)
        tgt_f = filters.gaussian(tgt_f, sigma=args.blur, channel_axis=-1)
    cur_gray = color.rgb2gray(cur_f)
    tgt_gray = color.rgb2gray(tgt_f)

    delta_e = color.deltaE_ciede2000(color.rgb2lab(cur_f), color.rgb2lab(tgt_f))
    delta_e[~valid] = 0.0

    mask = delta_e > args.threshold
    mask = morphology.remove_small_objects(mask, max_size=max(0, args.min_area - 1))

    # Merge nearby fragments so one logical change reads as one cluster.
    merged = morphology.dilation(mask, morphology.disk(3))
    labels = measure.label(merged)
    clusters = []
    for region in measure.regionprops(labels):
        rr0, cc0, rr1, cc1 = region.bbox
        region_mask = mask[rr0:rr1, cc0:cc1] & (labels[rr0:rr1, cc0:cc1] == region.label)
        area = int(region_mask.sum())
        if area < args.min_area:
            continue
        clusters.append(
            {
                "bbox": [int(cc0), int(rr0), int(cc1 - cc0), int(rr1 - rr0)],
                "area_px": area,
                "mean_delta_e": round(float(delta_e[rr0:rr1, cc0:cc1][region_mask].mean()), 2),
            }
        )
    clusters.sort(key=lambda c: c["area_px"], reverse=True)
    dropped = max(0, len(clusters) - args.max_clusters)
    clusters = clusters[: args.max_clusters]
    for i, cl in enumerate(clusters, start=1):
        cl["id"] = i

    ssim_score, ssim_map = structural_similarity(
        cur_gray, tgt_gray, data_range=1.0, gaussian_weights=True, full=True
    )
    shift, _, _ = phase_cross_correlation(tgt_gray, cur_gray, normalization=None)

    # A phase-correlation peak can come from one large moved element rather
    # than a genuine global scroll. Only report the shift when applying it
    # actually removes most of the difference.
    dy, dx = int(round(float(shift[0]))), int(round(float(shift[1])))
    shift_explains = False
    if (dx or dy) and abs(dy) < canvas_hw[0] and abs(dx) < canvas_hw[1]:
        rolled = np.roll(cur_gray, (dy, dx), axis=(0, 1))
        unwrapped = valid.copy()
        if dy > 0:
            unwrapped[:dy, :] = False
        elif dy < 0:
            unwrapped[dy:, :] = False
        if dx > 0:
            unwrapped[:, :dx] = False
        elif dx < 0:
            unwrapped[:, dx:] = False
        if unwrapped.any():
            base_err = np.abs(cur_gray - tgt_gray)[unwrapped].mean()
            shifted_err = np.abs(rolled - tgt_gray)[unwrapped].mean()
            shift_explains = bool(shifted_err < 0.5 * base_err)

    # sigma kept low so 1px hairlines and dividers still register
    edge_dilate = morphology.disk(1)
    cur_edges = morphology.dilation(feature.canny(cur_gray, sigma=1.0), edge_dilate)
    tgt_edges = morphology.dilation(feature.canny(tgt_gray, sigma=1.0), edge_dilate)
    edge_img = np.zeros((*canvas_hw, 3), dtype=np.uint8)
    edge_img[cur_edges & tgt_edges] = (110, 110, 110)
    edge_img[cur_edges & ~tgt_edges] = (255, 60, 60)
    edge_img[~cur_edges & tgt_edges] = (60, 220, 60)

    outdir = args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    abs_diff = np.abs(cur.astype(np.int16) - tgt.astype(np.int16)).mean(axis=2)
    outputs = {
        "blend": "01-blend.png",
        "absdiff": "02-absdiff.png",
        "heat": "03-heat.png",
        "mask": "04-mask.png",
        "boxes_current": "05-boxes-current.png",
        "boxes_target": "06-boxes-target.png",
        "edges": "07-edges.png",
        "ssim": "08-ssim.png",
    }
    to_image((cur.astype(np.float64) + tgt.astype(np.float64)) / 2).save(outdir / outputs["blend"])
    to_image(np.clip(abs_diff * args.gain, 0, 255)).save(outdir / outputs["absdiff"])
    to_image(colormap(np.clip(delta_e / HEAT_SCALE_DELTA_E, 0, 1))).save(outdir / outputs["heat"])
    to_image(mask * np.uint8(255)).save(outdir / outputs["mask"])
    draw_boxes(cur, clusters).save(outdir / outputs["boxes_current"])
    draw_boxes(tgt, clusters).save(outdir / outputs["boxes_target"])
    to_image(edge_img).save(outdir / outputs["edges"])
    to_image(colormap(np.clip((1.0 - ssim_map) / 2.0, 0, 1))).save(outdir / outputs["ssim"])

    valid_count = int(valid.sum())
    changed_count = int((mask & valid).sum())
    summary = {
        "current": {"path": str(args.current), "size": [cur.shape[1], cur.shape[0]]},
        "target": {"path": str(args.target), "size": [tgt.shape[1], tgt.shape[0]]},
        "size_mismatch": size_mismatch,
        "params": {
            "threshold_delta_e": args.threshold,
            "blur_sigma": args.blur,
            "min_area_px": args.min_area,
        },
        "metrics": {
            "percent_changed": round(100.0 * changed_count / valid_count, 3),
            "mean_delta_e": round(float(delta_e[valid].mean()), 3),
            "p99_delta_e": round(float(np.percentile(delta_e[valid], 99)), 2),
            "ssim": round(float(ssim_score), 4),
            "estimated_shift_xy": [dx, dy],
            "shift_explains_diff": shift_explains,
        },
        "clusters": clusters,
        "clusters_dropped_over_cap": dropped,
        "outputs": {k: str(outdir / v) for k, v in outputs.items()},
    }
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")

    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        m = summary["metrics"]
        print(f"canvas {canvas_hw[1]}x{canvas_hw[0]}"
              + ("  (size mismatch — padded area excluded from stats)" if size_mismatch else ""))
        print(f"changed {m['percent_changed']}% of pixels | mean dE {m['mean_delta_e']} "
              f"| p99 dE {m['p99_delta_e']} | SSIM {m['ssim']}")
        if shift_explains:
            print(f"note: content appears globally shifted by ({dx:+}, {dy:+}) px — "
                  "check scroll position or layout offset before reading per-pixel diffs")
        print(f"{len(clusters)} change cluster(s)"
              + (f" ({dropped} more dropped over --max-clusters cap)" if dropped else ""))
        for cl in clusters:
            x, y, w, h = cl["bbox"]
            print(f"  #{cl['id']:>2}  x={x:<5} y={y:<5} {w}x{h}  "
                  f"area={cl['area_px']}px  mean dE={cl['mean_delta_e']}")
        print(f"outputs in {outdir}/ (01-blend, 02-absdiff, 03-heat, 04-mask, "
              "05/06-boxes, 07-edges, 08-ssim, summary.json)")

    return 1 if clusters else 0


if __name__ == "__main__":
    sys.exit(main())
