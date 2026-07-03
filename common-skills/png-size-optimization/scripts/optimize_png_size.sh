#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  optimize_png_size.sh [--out-dir DIR | --in-place] [--lossless-only] [--quality MIN-MAX] FILE...
  optimize_png_size.sh --benchmark FILE...

Defaults:
  Writes optimized copies to ./pngquant-oxipng-out using pngquant --quality=80-95
  followed by oxipng. Pixel dimensions are preserved.

Options:
  --out-dir DIR       Write optimized copies into DIR.
  --in-place          Replace input files in place.
  --lossless-only     Use oxipng only; do not run pngquant.
  --quality MIN-MAX   pngquant quality range, default 80-95.
  --benchmark         Compare lossless tools and pngquant combinations on temp copies.
  -h, --help          Show this help.
USAGE
}

out_dir="pngquant-oxipng-out"
in_place=0
lossless_only=0
benchmark=0
quality="80-95"
files=()

while (($#)); do
  case "$1" in
    --out-dir)
      [[ $# -ge 2 ]] || { echo "missing value for --out-dir" >&2; exit 2; }
      out_dir="$2"
      shift 2
      ;;
    --in-place)
      in_place=1
      shift
      ;;
    --lossless-only)
      lossless_only=1
      shift
      ;;
    --quality)
      [[ $# -ge 2 ]] || { echo "missing value for --quality" >&2; exit 2; }
      quality="$2"
      shift 2
      ;;
    --benchmark)
      benchmark=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      files+=("$@")
      break
      ;;
    -*)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
    *)
      files+=("$1")
      shift
      ;;
  esac
done

[[ ${#files[@]} -gt 0 ]] || { usage >&2; exit 2; }
if [[ "$in_place" -eq 1 && "$out_dir" != "pngquant-oxipng-out" ]]; then
  echo "--out-dir and --in-place are mutually exclusive" >&2
  exit 2
fi

need() {
  which "$1" >/dev/null 2>&1 || { echo "required tool not found on PATH: $1" >&2; exit 127; }
}

have() {
  which "$1" >/dev/null 2>&1
}

size_bytes() {
  if stat -f '%z' "$1" >/dev/null 2>&1; then
    stat -f '%z' "$1"
  else
    stat -c '%s' "$1"
  fi
}

total_bytes() {
  local total=0 size
  for f in "$@"; do
    size=$(size_bytes "$f")
    total=$((total + size))
  done
  printf '%s\n' "$total"
}

dimensions() {
  if have sips; then
    sips -g pixelWidth -g pixelHeight "$1" 2>/dev/null | awk '
      /pixelWidth:/ {w=$2}
      /pixelHeight:/ {h=$2}
      END {if (w && h) printf "%sx%s", w, h}
    '
  elif have identify; then
    identify -format '%wx%h' "$1"
  else
    printf 'unknown'
  fi
}

copy_inputs() {
  local dest="$1"
  mkdir -p "$dest"
  for f in "${files[@]}"; do
    [[ -f "$f" ]] || { echo "not a file: $f" >&2; exit 2; }
    if [[ "$(cd "$(dirname "$f")" && pwd -P)/$(basename "$f")" == "$(cd "$dest" && pwd -P)/$(basename "$f")" ]]; then
      echo "output would overwrite input without --in-place: $f" >&2
      exit 2
    fi
    cp "$f" "$dest/"
  done
}

print_sizes() {
  local label="$1"
  shift
  printf '%s\n' "$label"
  for f in "$@"; do
    printf '  %8s  %s  %s\n' "$(size_bytes "$f")" "$(dimensions "$f")" "$f"
  done
  printf '  total: %s bytes\n' "$(total_bytes "$@")"
}

optimize_pngquant_oxipng() {
  local target_dir="$1"
  need pngquant
  need oxipng
  pngquant --speed 1 --strip "--quality=$quality" --force --ext .png "$target_dir"/*.png
  oxipng -o max --strip safe --quiet "$target_dir"/*.png
}

optimize_lossless() {
  local target_dir="$1"
  need oxipng
  oxipng -o max --strip safe --quiet "$target_dir"/*.png
}

run_benchmark() {
  need oxipng
  local base
  base=$(mktemp -d "${TMPDIR:-/tmp}/png-size-bench.XXXXXX")
  for d in orig oxipng optipng pngcrush pngquant pngquant-oxipng; do
    mkdir -p "$base/$d"
    cp "${files[@]}" "$base/$d/"
  done

  oxipng -o max --strip safe --quiet "$base/oxipng"/*.png

  if have optipng; then
    optipng -o7 -strip all -quiet "$base/optipng"/*.png
  else
    rm -rf "$base/optipng"
  fi

  if have pngcrush; then
    for f in "$base/pngcrush"/*.png; do
      pngcrush -q -brute -reduce -rem alla "$f" "$f.out" && mv "$f.out" "$f"
    done
  else
    rm -rf "$base/pngcrush"
  fi

  if have pngquant; then
    pngquant --speed 1 --strip "--quality=$quality" --force --ext .png "$base/pngquant"/*.png
    pngquant --speed 1 --strip "--quality=$quality" --force --ext .png "$base/pngquant-oxipng"/*.png
    oxipng -o max --strip safe --quiet "$base/pngquant-oxipng"/*.png
  else
    rm -rf "$base/pngquant" "$base/pngquant-oxipng"
  fi

  printf 'benchmark directory: %s\n' "$base"
  for d in "$base"/*; do
    [[ -d "$d" ]] || continue
    print_sizes "$(basename "$d")" "$d"/*.png
  done
}

if [[ "$benchmark" -eq 1 ]]; then
  run_benchmark
  exit 0
fi

original_total=$(total_bytes "${files[@]}")
if [[ "$in_place" -eq 1 ]]; then
  work_dir=$(mktemp -d "${TMPDIR:-/tmp}/png-size-opt.XXXXXX")
  copy_inputs "$work_dir"
else
  copy_inputs "$out_dir"
  work_dir="$out_dir"
fi

print_sizes "before" "${files[@]}"

if [[ "$lossless_only" -eq 1 ]]; then
  optimize_lossless "$work_dir"
else
  optimize_pngquant_oxipng "$work_dir"
fi

if [[ "$in_place" -eq 1 ]]; then
  for f in "${files[@]}"; do
    mv "$work_dir/$(basename "$f")" "$f"
  done
  rmdir "$work_dir"
  outputs=("${files[@]}")
else
  outputs=("$work_dir"/*.png)
fi

optimized_total=$(total_bytes "${outputs[@]}")
print_sizes "after" "${outputs[@]}"
awk -v before="$original_total" -v after="$optimized_total" 'BEGIN {
  if (before > 0) {
    printf "savings: %d bytes (%.1f%%)\n", before - after, (before - after) * 100 / before
  }
}'
