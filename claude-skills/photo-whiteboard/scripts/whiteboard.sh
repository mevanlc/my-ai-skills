#!/usr/bin/env bash
#
# whiteboard.sh — Convert document photos to clean, compressed whiteboard-style images.
#
# Applies: resize → trim → grayscale → sigmoidal contrast → posterize → PNG8
# Typical compression: 85-90% size reduction vs original phone photos.
#
# Usage:
#   whiteboard.sh <input> [output]           # single file
#   whiteboard.sh <input_dir> <output_dir>   # batch (all jpg/png/heic in dir)
#
# Options (via environment variables):
#   WB_RESIZE=80       # resize percentage (default: 80, clamped to WB_MIN_DIM)
#   WB_MIN_DIM=800     # minimum output dimension in px (default: 800)
#   WB_CONTRAST=15     # sigmoidal contrast strength (default: 15)
#   WB_MIDPOINT=60     # sigmoidal midpoint percentage (default: 60)
#   WB_COLORS=3        # posterize color count (default: 3)
#   WB_FORMAT=png      # output format: png, jpg (default: png)
#   WB_QUALITY=75      # JPEG quality if format=jpg (default: 75)
#   WB_MONO=0          # set to 1 for hard mono threshold instead of posterize
#   WB_THRESHOLD=60    # mono threshold percentage (default: 60, only if WB_MONO=1)
#   WB_SKIP_TRIM=0     # set to 1 to skip auto-trim
#
# Requires: ImageMagick 7+ (magick command)

set -euo pipefail

# Find magick binary — handle imagemagick-full (homebrew) or standard install
if command -v magick &>/dev/null; then
  MAGICK=magick
elif [[ -x "$(brew --prefix imagemagick-full 2>/dev/null)/bin/magick" ]]; then
  MAGICK="$(brew --prefix imagemagick-full)/bin/magick"
elif [[ -x /opt/homebrew/bin/magick ]]; then
  MAGICK=/opt/homebrew/bin/magick
else
  echo "Error: ImageMagick 7+ (magick) not found. Install with: brew install imagemagick" >&2
  exit 1
fi

# Defaults
RESIZE="${WB_RESIZE:-80}"
MIN_DIM="${WB_MIN_DIM:-800}"
CONTRAST="${WB_CONTRAST:-15}"
MIDPOINT="${WB_MIDPOINT:-60}"
COLORS="${WB_COLORS:-3}"
FORMAT="${WB_FORMAT:-png}"
QUALITY="${WB_QUALITY:-75}"
MONO="${WB_MONO:-0}"
THRESHOLD="${WB_THRESHOLD:-60}"
SKIP_TRIM="${WB_SKIP_TRIM:-0}"

usage() {
  echo "Usage: whiteboard.sh <input> [output]"
  echo "       whiteboard.sh <input_dir> <output_dir>"
  echo ""
  echo "Environment variables: WB_RESIZE, WB_MIN_DIM, WB_CONTRAST, WB_MIDPOINT,"
  echo "  WB_COLORS, WB_FORMAT, WB_QUALITY, WB_MONO, WB_THRESHOLD, WB_SKIP_TRIM"
  exit 1
}

convert_one() {
  local src="$1" dst="$2"

  local trim_args=()
  if [[ "$SKIP_TRIM" != "1" ]]; then
    trim_args=(-trim +repage)
  fi

  local style_args=()
  if [[ "$MONO" == "1" ]]; then
    style_args=(-normalize -threshold "${THRESHOLD}%")
  else
    style_args=(-normalize -sigmoidal-contrast "${CONTRAST},${MIDPOINT}%" -posterize "$COLORS")
  fi

  local out_args=()
  if [[ "$FORMAT" == "jpg" || "$FORMAT" == "jpeg" ]]; then
    out_args=(-quality "$QUALITY" "$dst")
  else
    out_args=("PNG8:$dst")
  fi

  # Calculate resize: use percentage but clamp so the smallest dimension >= MIN_DIM
  local resize_arg="${RESIZE}%"
  if [[ "$MIN_DIM" -gt 0 ]]; then
    local dims
    dims=$("$MAGICK" identify -format "%w %h" "$src" 2>/dev/null | head -1)
    local w h
    w=$(echo "$dims" | cut -d' ' -f1)
    h=$(echo "$dims" | cut -d' ' -f2)
    local target_w=$(( w * RESIZE / 100 ))
    local target_h=$(( h * RESIZE / 100 ))
    local min_target=$(( target_w < target_h ? target_w : target_h ))
    if [[ "$min_target" -lt "$MIN_DIM" && "$w" -ge "$MIN_DIM" && "$h" -ge "$MIN_DIM" ]]; then
      # Clamp: resize so smallest side = MIN_DIM
      resize_arg="${MIN_DIM}x${MIN_DIM}^"
    elif [[ "$w" -lt "$MIN_DIM" || "$h" -lt "$MIN_DIM" ]]; then
      # Source already smaller than minimum — don't resize at all
      resize_arg="100%"
    fi
  fi

  "$MAGICK" "$src" \
    -resize "$resize_arg" \
    "${trim_args[@]}" \
    -colorspace gray \
    "${style_args[@]}" \
    "${out_args[@]}"
}

output_name() {
  local base="$1" dir="$2"
  local name="${base%.*}"
  if [[ "$FORMAT" == "jpg" || "$FORMAT" == "jpeg" ]]; then
    echo "${dir}/${name}.jpg"
  else
    echo "${dir}/${name}.png"
  fi
}

# --- Main ---

[[ $# -lt 1 ]] && usage

INPUT="$1"
OUTPUT="${2:-}"

if [[ -f "$INPUT" ]]; then
  # Single file mode
  if [[ -z "$OUTPUT" ]]; then
    OUTPUT="$(output_name "$(basename "$INPUT")" "$(dirname "$INPUT")")"
  fi
  convert_one "$INPUT" "$OUTPUT"
  in_size=$(stat -f%z "$INPUT" 2>/dev/null || stat -c%s "$INPUT" 2>/dev/null)
  out_size=$(stat -f%z "$OUTPUT" 2>/dev/null || stat -c%s "$OUTPUT" 2>/dev/null)
  pct=$((100 - (out_size * 100 / in_size)))
  echo "$OUTPUT  (${pct}% smaller)"

elif [[ -d "$INPUT" ]]; then
  # Batch mode
  [[ -z "$OUTPUT" ]] && { echo "Error: output directory required for batch mode"; usage; }
  mkdir -p "$OUTPUT"

  total_in=0
  total_out=0
  count=0

  for src in "$INPUT"/*.{jpg,jpeg,png,heic,JPG,JPEG,PNG,HEIC} ; do
    [[ -f "$src" ]] || continue
    base="$(basename "$src")"
    dst="$(output_name "$base" "$OUTPUT")"
    convert_one "$src" "$dst"

    in_size=$(stat -f%z "$src" 2>/dev/null || stat -c%s "$src" 2>/dev/null)
    out_size=$(stat -f%z "$dst" 2>/dev/null || stat -c%s "$dst" 2>/dev/null)
    total_in=$((total_in + in_size))
    total_out=$((total_out + out_size))
    count=$((count + 1))
    echo "  $base → $(basename "$dst")"
  done

  if [[ $count -gt 0 ]]; then
    pct=$((100 - (total_out * 100 / total_in)))
    echo ""
    echo "$count files processed. ${pct}% total reduction ($(( total_in / 1024 ))KB → $(( total_out / 1024 ))KB)"
  else
    echo "No image files found in $INPUT"
  fi
else
  echo "Error: $INPUT is not a file or directory"
  usage
fi
