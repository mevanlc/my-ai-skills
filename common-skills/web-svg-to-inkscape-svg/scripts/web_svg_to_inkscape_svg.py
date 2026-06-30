#!/usr/bin/env python3
"""Normalize browser-authored SVG and optionally round-trip it through Inkscape."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree import ElementTree


XLINK_NS = "http://www.w3.org/1999/xlink"
SVG_NS = "http://www.w3.org/2000/svg"

JSX_ATTRIBUTE_MAP = {
    "accentHeight": "accent-height",
    "alignmentBaseline": "alignment-baseline",
    "baselineShift": "baseline-shift",
    "className": "class",
    "clipPath": "clip-path",
    "clipRule": "clip-rule",
    "colorInterpolation": "color-interpolation",
    "colorInterpolationFilters": "color-interpolation-filters",
    "colorProfile": "color-profile",
    "colorRendering": "color-rendering",
    "dominantBaseline": "dominant-baseline",
    "enableBackground": "enable-background",
    "fillOpacity": "fill-opacity",
    "fillRule": "fill-rule",
    "floodColor": "flood-color",
    "floodOpacity": "flood-opacity",
    "fontFamily": "font-family",
    "fontSize": "font-size",
    "fontSizeAdjust": "font-size-adjust",
    "fontStretch": "font-stretch",
    "fontStyle": "font-style",
    "fontVariant": "font-variant",
    "fontWeight": "font-weight",
    "glyphOrientationHorizontal": "glyph-orientation-horizontal",
    "glyphOrientationVertical": "glyph-orientation-vertical",
    "imageRendering": "image-rendering",
    "letterSpacing": "letter-spacing",
    "lightingColor": "lighting-color",
    "markerEnd": "marker-end",
    "markerMid": "marker-mid",
    "markerStart": "marker-start",
    "paintOrder": "paint-order",
    "pointerEvents": "pointer-events",
    "shapeRendering": "shape-rendering",
    "stopColor": "stop-color",
    "stopOpacity": "stop-opacity",
    "strokeDasharray": "stroke-dasharray",
    "strokeDashoffset": "stroke-dashoffset",
    "strokeLinecap": "stroke-linecap",
    "strokeLinejoin": "stroke-linejoin",
    "strokeMiterlimit": "stroke-miterlimit",
    "strokeOpacity": "stroke-opacity",
    "strokeWidth": "stroke-width",
    "textAnchor": "text-anchor",
    "textDecoration": "text-decoration",
    "textRendering": "text-rendering",
    "vectorEffect": "vector-effect",
    "wordSpacing": "word-spacing",
    "writingMode": "writing-mode",
    "xHeight": "x-height",
    "xlinkHref": "xlink:href",
    "xmlnsXlink": "xmlns:xlink",
    "xmlSpace": "xml:space",
}

HTML_ENTITY_MAP = {
    "&nbsp;": "&#160;",
    "&ensp;": "&#8194;",
    "&emsp;": "&#8195;",
    "&thinsp;": "&#8201;",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize a browser/React-oriented SVG, then optionally export it "
            "through Inkscape as Plain SVG."
        )
    )
    parser.add_argument("input", type=Path, help="Input .svg file")
    parser.add_argument("output", type=Path, help="Output .svg file")
    parser.add_argument(
        "--no-inkscape",
        action="store_true",
        help="Only write the normalized intermediate SVG; skip Inkscape export",
    )
    parser.add_argument(
        "--inkscape",
        default=None,
        help="Path to inkscape binary. Defaults to PATH lookup.",
    )
    parser.add_argument(
        "--text-to-path",
        action="store_true",
        help="Pass --export-text-to-path to Inkscape for font-independent output",
    )
    parser.add_argument(
        "--area-drawing",
        action="store_true",
        help="Pass --export-area-drawing to Inkscape",
    )
    parser.add_argument(
        "--strip-scripts",
        action="store_true",
        help="Remove <script>...</script> blocks before writing the intermediate",
    )
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="Keep the normalized intermediate file and report its path",
    )
    parser.add_argument(
        "--json-report",
        type=Path,
        help="Write a JSON report with detected browser-only risk markers",
    )
    return parser.parse_args()


def replace_html_entities(text: str) -> str:
    for entity, numeric in HTML_ENTITY_MAP.items():
        text = text.replace(entity, numeric)
    return text


def normalize_jsx_attributes(text: str) -> tuple[str, list[str]]:
    found: list[str] = []
    for jsx_name, svg_name in JSX_ATTRIBUTE_MAP.items():
        pattern = re.compile(rf"(?P<prefix>[\s<]){re.escape(jsx_name)}(?=\s*=)")
        if pattern.search(text):
            found.append(jsx_name)
            text = pattern.sub(rf"\g<prefix>{svg_name}", text)

    def fix_style(match: re.Match[str]) -> str:
        body = match.group("body")
        for jsx_name, svg_name in JSX_ATTRIBUTE_MAP.items():
            body = re.sub(rf"(?<![-\w]){re.escape(jsx_name)}\s*:", f"{svg_name}:", body)
        return f'{match.group("name")}="{body}"'

    text = re.sub(
        r'(?P<name>style)\s*=\s*"(?P<body>[^"]*)"',
        fix_style,
        text,
        flags=re.IGNORECASE,
    )
    return text, found


def ensure_root_namespaces(text: str) -> str:
    root_match = re.search(r"<svg(?P<attrs>[\s>/])", text)
    if not root_match:
        return text

    insertions: list[str] = []
    root_start = text[: root_match.end()]
    root_tag_end = text.find(">", root_match.start())
    root_tag = text[root_match.start() : root_tag_end] if root_tag_end != -1 else root_start

    if "xmlns=" not in root_tag:
        insertions.append(f' xmlns="{SVG_NS}"')
    if "xlink:" in text and "xmlns:xlink=" not in root_tag:
        insertions.append(f' xmlns:xlink="{XLINK_NS}"')
    if not insertions:
        return text

    return text[: root_match.end() - 1] + "".join(insertions) + text[root_match.end() - 1 :]


def strip_script_blocks(text: str) -> str:
    return re.sub(
        r"<script\b[^>]*>.*?</script\s*>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def analyze_svg(text: str, jsx_attrs: list[str]) -> dict[str, object]:
    lowered = text.lower()
    report: dict[str, object] = {
        "jsx_attributes_normalized": sorted(jsx_attrs),
        "has_style_element": bool(re.search(r"<style\b", text, re.IGNORECASE)),
        "has_class_attributes": bool(re.search(r"\sclass\s*=", text)),
        "has_foreign_object": "foreignobject" in lowered,
        "has_script": bool(re.search(r"<script\b", text, re.IGNORECASE)),
        "has_css_custom_properties": bool(re.search(r"(--[-_a-zA-Z0-9]+\s*:|var\()", text)),
        "has_current_color": bool(re.search(r"\bcurrentColor\b", text)),
        "has_external_stylesheet": bool(
            re.search(r"<\?xml-stylesheet\b|<link\b|@import\b", text, re.IGNORECASE)
        ),
        "has_remote_image_href": bool(
            re.search(r"\b(?:href|xlink:href)\s*=\s*['\"]https?://", text, re.IGNORECASE)
        ),
        "xml_parse_ok": False,
        "xml_parse_error": None,
    }
    try:
        ElementTree.fromstring(text)
        report["xml_parse_ok"] = True
    except ElementTree.ParseError as exc:
        report["xml_parse_error"] = str(exc)
    return report


def run_inkscape(args: argparse.Namespace, intermediate: Path, output: Path) -> dict[str, object]:
    inkscape = args.inkscape or shutil.which("inkscape")
    if not inkscape:
        raise RuntimeError("inkscape was not found on PATH; rerun with --no-inkscape or --inkscape")

    cmd = [
        inkscape,
        str(intermediate),
        "--export-type=svg",
        "--export-plain-svg",
        f"--export-filename={output}",
    ]
    if args.text_to_path:
        cmd.append("--export-text-to-path")
    if args.area_drawing:
        cmd.append("--export-area-drawing")

    proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
    }


def write_report(report_path: Path | None, report: dict[str, object]) -> None:
    if report_path:
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    source = args.input.read_text(encoding="utf-8")
    text = replace_html_entities(source)
    text, jsx_attrs = normalize_jsx_attributes(text)
    text = ensure_root_namespaces(text)
    if args.strip_scripts:
        text = strip_script_blocks(text)

    report = analyze_svg(text, jsx_attrs)
    if not report["xml_parse_ok"]:
        write_report(args.json_report, report)
        print(f"XML parse failed: {report['xml_parse_error']}", file=sys.stderr)
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="web-svg-to-inkscape-") as tmpdir:
        intermediate = Path(tmpdir) / "normalized.svg"
        intermediate.write_text(text, encoding="utf-8")

        if args.no_inkscape:
            shutil.copyfile(intermediate, args.output)
            report["inkscape"] = {"skipped": True}
        else:
            result = run_inkscape(args, intermediate, args.output)
            report["inkscape"] = result
            if result["returncode"] != 0:
                write_report(args.json_report, report)
                print(result["stderr"], file=sys.stderr, end="")
                return int(result["returncode"])

        if args.keep_work:
            kept = args.output.with_suffix(args.output.suffix + ".normalized-input.svg")
            shutil.copyfile(intermediate, kept)
            report["normalized_intermediate"] = str(kept)

    write_report(args.json_report, report)

    risk_keys = [
        "has_style_element",
        "has_class_attributes",
        "has_foreign_object",
        "has_css_custom_properties",
        "has_current_color",
        "has_external_stylesheet",
        "has_remote_image_href",
    ]
    risks = [key for key in risk_keys if report.get(key)]
    if risks:
        print("Risk markers:", ", ".join(risks), file=sys.stderr)
    print(str(args.output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
