#!/usr/bin/env python3
"""Report Git merge markers found in one or more files."""

from __future__ import annotations

import re
import sys
from pathlib import Path


MERGE_MARKER_RE = re.compile(r"^(?:<{7,}|\|{7,}|>{7,})(?:[ \t].*)?$|^={7,}[ \t]*$")


def scan_file(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []

    with path.open(encoding="utf-8", errors="replace", newline="") as file:
        for line_number, line in enumerate(file, start=1):
            line_text = line.rstrip("\r\n")
            if MERGE_MARKER_RE.fullmatch(line_text):
                hits.append((line_number, line_text))

    return hits


def main(argv: list[str]) -> int:
    if not argv:
        print(
            f"usage: {Path(sys.argv[0]).name} <file> [file...]",
            file=sys.stderr,
        )
        return 2

    results: list[tuple[str, list[tuple[int, str]]]] = []
    for file_name in argv:
        try:
            hits = scan_file(Path(file_name))
        except OSError as error:
            print(f"{Path(sys.argv[0]).name}: {file_name}: {error}", file=sys.stderr)
            return 2
        results.append((file_name, hits))

    files_with_hits = sum(bool(hits) for _, hits in results)
    total_hits = sum(len(hits) for _, hits in results)
    report_attributes = (
        f'n-files-scanned="{len(results)}" '
        f'n-files-with-hits="{files_with_hits}" '
        f'total-hits="{total_hits}"'
    )

    if total_hits == 0:
        print(f"<scan-files-for-merge-markers-report {report_attributes}/>")
        return 0

    print(f"<scan-files-for-merge-markers-report {report_attributes}>")
    for file_name, hits in results:
        for line_number, line_text in hits:
            print(f"{file_name}:{line_number}:{line_text}")
    print("</scan-files-for-merge-markers-report>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
