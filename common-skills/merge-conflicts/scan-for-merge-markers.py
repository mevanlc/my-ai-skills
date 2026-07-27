#!/usr/bin/env python3
"""Report Git merge markers found in files or a Git worktree."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

MERGE_MARKER_RE = re.compile(r"^(?:<{7,}|\|{7,}|>{7,})(?:[ \t].*)?$|^={7,}[ \t]*$")


class GitCommandError(RuntimeError):
    """Raised when Git cannot provide the paths to scan."""


@dataclass(frozen=True)
class ScanTarget:
    display_path: str
    file_path: Path


def scan_file(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []

    with path.open(encoding="utf-8", errors="replace", newline="") as file:
        for line_number, line in enumerate(file, start=1):
            line_text = line.rstrip("\r\n")
            if MERGE_MARKER_RE.fullmatch(line_text):
                hits.append((line_number, line_text))

    return hits


def run_git(directory: Path, *arguments: str) -> bytes:
    command = ("git", "-C", os.fspath(directory), *arguments)
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise GitCommandError(f"could not run git: {error}") from error

    if completed.returncode != 0:
        detail = os.fsdecode(completed.stderr).strip()
        raise GitCommandError(
            detail or f"git exited with status {completed.returncode}"
        )

    return completed.stdout


def decode_nul_paths(output: bytes) -> list[str]:
    return [os.fsdecode(path) for path in output.split(b"\0") if path]


def git_paths(repository_root: Path, *arguments: str) -> list[str]:
    return decode_nul_paths(run_git(repository_root, *arguments, "-z", "--"))


def git_scan_targets(
    repodir: Path, *, no_untracked: bool, no_unstaged: bool
) -> list[ScanTarget]:
    root_output = run_git(repodir, "rev-parse", "--show-toplevel")
    repository_root = Path(os.fsdecode(root_output.rstrip(b"\r\n")))

    selected_paths = git_paths(
        repository_root,
        "diff",
        "--cached",
        "--name-only",
        "--diff-filter=d",
    )
    if not no_unstaged:
        selected_paths.extend(
            git_paths(
                repository_root,
                "diff",
                "--name-only",
                "--diff-filter=d",
            )
        )
        if not no_untracked:
            selected_paths.extend(
                git_paths(
                    repository_root,
                    "ls-files",
                    "--others",
                    "--exclude-standard",
                )
            )

    targets: list[ScanTarget] = []
    seen: set[str] = set()
    for relative_path in selected_paths:
        if relative_path in seen:
            continue
        seen.add(relative_path)

        file_path = repository_root / relative_path
        if file_path.is_symlink() or not file_path.is_file():
            continue
        targets.append(ScanTarget(relative_path, file_path))

    return targets


def files_scan_targets(file_names: list[str]) -> list[ScanTarget]:
    return [ScanTarget(file_name, Path(file_name)) for file_name in file_names]


def print_report(targets: list[ScanTarget]) -> int:
    results: list[tuple[str, list[tuple[int, str]]]] = []
    for target in targets:
        try:
            hits = scan_file(target.file_path)
        except OSError as error:
            print(
                f"{Path(sys.argv[0]).name}: {target.display_path}: {error}",
                file=sys.stderr,
            )
            return 2
        results.append((target.display_path, hits))

    files_with_hits = sum(1 for _, hits in results if hits)
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Report Git merge markers found in files or a Git worktree."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    git_parser = subparsers.add_parser(
        "git", help="scan modified and untracked files in a Git worktree"
    )
    git_parser.add_argument(
        "--no-untracked",
        action="store_true",
        help="skip untracked files",
    )
    git_parser.add_argument(
        "--no-unstaged",
        action="store_true",
        help="scan only paths with staged changes",
    )
    git_parser.add_argument(
        "repodir",
        nargs="?",
        type=Path,
        default=Path.cwd(),
        help="repository directory (default: current directory)",
    )

    files_parser = subparsers.add_parser("files", help="scan specified files")
    files_parser.add_argument("files", nargs="+", help="files to scan")

    return parser


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)

    try:
        if args.mode == "git":
            targets = git_scan_targets(
                args.repodir,
                no_untracked=args.no_untracked,
                no_unstaged=args.no_unstaged,
            )
        else:
            targets = files_scan_targets(args.files)
    except GitCommandError as error:
        print(f"{Path(sys.argv[0]).name}: {error}", file=sys.stderr)
        return 2

    return print_report(targets)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
