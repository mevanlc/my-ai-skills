#!/usr/bin/env python3
"""
Pack an edited shortcut plist (XML or binary) back into a signed .shortcut file.

Pipeline:
  1. If input is XML plist, convert to binary plist via `plutil`.
  2. Feed to `shortcuts sign` to produce an AEA1-signed .shortcut.

Requires macOS CLIs: plutil, shortcuts.
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def detect_plist_kind(path: Path) -> str:
    with path.open("rb") as f:
        head = f.read(16)
    if head.startswith(b"bplist00"):
        return "binary"
    stripped = head.lstrip()
    if stripped.startswith(b"<?xml") or stripped.startswith(b"<plist"):
        return "xml"
    return "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pack an edited shortcut plist into a signed .shortcut file."
    )
    parser.add_argument("input", help="Path to Shortcut.wflow / .wflow.xml / edited plist")
    parser.add_argument(
        "-o", "--out", required=True, help="Output .shortcut path"
    )
    parser.add_argument(
        "--mode",
        choices=("anyone", "people-who-know-me"),
        default="anyone",
        help="Signing mode (default: anyone)",
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing output"
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        die(f"input not found: {input_path}")

    out_path = Path(args.out).expanduser().resolve()
    if out_path.exists() and not args.force:
        die(f"output exists: {out_path} (use --force to overwrite)")

    kind = detect_plist_kind(input_path)
    if kind == "unknown":
        die(
            f"input does not look like a plist (neither 'bplist00' nor XML): {input_path}"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        if kind == "xml":
            binary_path = tmpdir_path / "unsigned.shortcut"
            try:
                subprocess.check_call(
                    ["plutil", "-convert", "binary1", "-o", str(binary_path), str(input_path)]
                )
            except subprocess.CalledProcessError as e:
                die(f"plutil conversion failed (exit {e.returncode})")
            sign_input = binary_path
        else:
            sign_input = input_path

        try:
            subprocess.check_call(
                [
                    "shortcuts",
                    "sign",
                    "--mode",
                    args.mode,
                    "--input",
                    str(sign_input),
                    "--output",
                    str(out_path),
                ]
            )
        except subprocess.CalledProcessError as e:
            die(f"`shortcuts sign` failed (exit {e.returncode})")

    with out_path.open("rb") as f:
        magic = f.read(4)
    if magic != b"AEA1":
        die(f"output does not have AEA1 magic (got {magic!r}); signing may have failed")

    print(f"done: {out_path} (mode={args.mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
