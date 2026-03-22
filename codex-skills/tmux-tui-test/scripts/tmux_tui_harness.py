#!/usr/bin/env python3

import argparse
import json
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unicodedata
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class HarnessError(Exception):
    pass


@dataclass
class CommandResult:
    stdout: str
    stderr: str


@dataclass
class CapturedScreen:
    info: Dict[str, Any]
    ansi_text: str
    tokens: List[Dict[str, Any]]
    rows: List[List[Dict[str, Any]]]
    width: int
    height: int


BUTTON_CODES = {
    "left": 0,
    "middle": 1,
    "right": 2,
}

SCROLL_CODES = {
    "up": 64,
    "down": 65,
    "left": 66,
    "right": 67,
}

ANCHORS = ("start", "center", "end")
DEFAULT_STYLE = {
    "fg": "default",
    "bg": "default",
    "bold": False,
    "dim": False,
    "italic": False,
    "underline": False,
    "blink": False,
    "reverse": False,
    "hidden": False,
    "strike": False,
}
STYLE_FLAGS = (
    "bold",
    "dim",
    "italic",
    "underline",
    "blink",
    "reverse",
    "hidden",
    "strike",
)
ANSI_COLORS = [
    "black",
    "red",
    "green",
    "yellow",
    "blue",
    "magenta",
    "cyan",
    "white",
]
BRIGHT_ANSI_COLORS = [f"bright-{name}" for name in ANSI_COLORS]
SNAPSHOT_DIR = Path(tempfile.gettempdir()) / "tmux-tui-test-snapshots"


def emit(payload: Dict[str, Any], exit_code: int = 0) -> None:
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    raise SystemExit(exit_code)


def fail(message: str, *, detail: Optional[str] = None, exit_code: int = 1) -> None:
    payload: Dict[str, Any] = {"ok": False, "error": message}
    if detail:
        payload["detail"] = detail
    emit(payload, exit_code)


def run_tmux(args: List[str], *, check: bool = True) -> CommandResult:
    try:
        completed = subprocess.run(
            ["tmux", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise HarnessError("tmux is not installed or not on PATH") from exc

    stdout = completed.stdout.rstrip("\n")
    stderr = completed.stderr.rstrip("\n")
    if check and completed.returncode != 0:
        detail = stderr or stdout or f"tmux exited with status {completed.returncode}"
        raise HarnessError(detail)
    return CommandResult(stdout=stdout, stderr=stderr)


def session_exists(session: str) -> bool:
    result = run_tmux(["has-session", "-t", session], check=False)
    return result.stderr == "" and result.stdout == ""


def parse_kv_line(line: str) -> Dict[str, str]:
    if not line:
        return {}
    payload: Dict[str, str] = {}
    for part in line.split("\t"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        payload[key] = value
    return payload


def maybe_int(value: Optional[str]) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except ValueError:
        return None


def session_info(session: str) -> Dict[str, Any]:
    fmt = "\t".join(
        [
            "session=#{session_name}",
            "pane=#{pane_id}",
            "width=#{window_width}",
            "height=#{window_height}",
            "pid=#{pane_pid}",
            "command=#{pane_current_command}",
            "dead=#{pane_dead}",
            "exit_status=#{pane_dead_status}",
            "exit_signal=#{pane_dead_signal}",
            "cursor_x=#{cursor_x}",
            "cursor_y=#{cursor_y}",
            "cursor_flag=#{cursor_flag}",
            "cursor_shape=#{cursor_shape}",
            "cursor_blinking=#{cursor_blinking}",
            "cursor_very_visible=#{cursor_very_visible}",
            "pane_in_mode=#{pane_in_mode}",
            "pane_key_mode=#{pane_key_mode}",
            "mouse_all_flag=#{mouse_all_flag}",
            "mouse_any_flag=#{mouse_any_flag}",
            "mouse_button_flag=#{mouse_button_flag}",
            "mouse_sgr_flag=#{mouse_sgr_flag}",
            "mouse_standard_flag=#{mouse_standard_flag}",
            "mouse_utf8_flag=#{mouse_utf8_flag}",
        ]
    )
    result = run_tmux(["list-panes", "-t", session, "-F", fmt])
    line = result.stdout.splitlines()[0] if result.stdout else ""
    info = parse_kv_line(line)
    if not info:
        raise HarnessError(f"failed to inspect session {session!r}")

    info["ok"] = True
    dead = info.get("dead") == "1"
    info["alive"] = not dead

    exit_status = maybe_int(info.get("exit_status"))
    exit_signal = maybe_int(info.get("exit_signal"))
    if dead:
        if exit_status is not None:
            info["exit_status"] = exit_status
        else:
            info.pop("exit_status", None)
        if exit_signal is not None:
            info["exit_signal"] = exit_signal
        else:
            info.pop("exit_signal", None)
    else:
        info.pop("exit_status", None)
        info.pop("exit_signal", None)

    for key in ("cursor_x", "cursor_y"):
        value = maybe_int(info.get(key))
        if value is not None:
            info[key] = value

    return info


def parse_dimension(value: Any, label: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HarnessError(f"invalid {label} value from tmux: {value!r}") from exc


def capture_text(
    session: str,
    *,
    ansi: bool = True,
    history: Optional[int] = None,
    full_history: bool = False,
) -> str:
    args = ["capture-pane", "-t", session, "-p", "-J"]
    if ansi:
        args.append("-e")
    if full_history:
        args.extend(["-S", "-"])
    elif history is not None:
        args.extend(["-S", f"-{history}"])
    return run_tmux(args).stdout


def send_literal(session: str, text: str) -> None:
    run_tmux(["send-keys", "-t", session, "-l", "--", text])


def normalize_command(command: List[str]) -> List[str]:
    if command and command[0] == "--":
        return command[1:]
    return command


def build_command(command: List[str], env_items: List[str]) -> str:
    argv = normalize_command(command)
    if not argv:
        raise HarnessError("start requires a command after --")

    extra = []
    for item in env_items:
        if "=" not in item:
            raise HarnessError(f"invalid env assignment: {item!r}")
        extra.append(item)

    if extra:
        return shlex.join(["env", *extra, *argv])
    return shlex.join(argv)


def clone_style(style: Dict[str, Any]) -> Dict[str, Any]:
    return dict(style)


def default_style() -> Dict[str, Any]:
    return clone_style(DEFAULT_STYLE)


def resolve_extended_color(codes: List[int], index: int) -> Tuple[str, int]:
    if index + 1 >= len(codes):
        return "default", len(codes)
    mode = codes[index + 1]
    if mode == 5 and index + 2 < len(codes):
        return f"index:{codes[index + 2]}", index + 3
    if mode == 2 and index + 4 < len(codes):
        red, green, blue = codes[index + 2 : index + 5]
        return f"#{red:02x}{green:02x}{blue:02x}", index + 5
    return "default", len(codes)


def apply_sgr_codes(style: Dict[str, Any], codes: List[int]) -> Dict[str, Any]:
    result = clone_style(style)
    values = codes or [0]
    index = 0
    while index < len(values):
        code = values[index]
        if code == 0:
            result = default_style()
        elif code == 1:
            result["bold"] = True
        elif code == 2:
            result["dim"] = True
        elif code == 3:
            result["italic"] = True
        elif code == 4:
            result["underline"] = True
        elif code == 5:
            result["blink"] = True
        elif code == 7:
            result["reverse"] = True
        elif code == 8:
            result["hidden"] = True
        elif code == 9:
            result["strike"] = True
        elif code in (21, 22):
            result["bold"] = False
            result["dim"] = False
        elif code == 23:
            result["italic"] = False
        elif code == 24:
            result["underline"] = False
        elif code == 25:
            result["blink"] = False
        elif code == 27:
            result["reverse"] = False
        elif code == 28:
            result["hidden"] = False
        elif code == 29:
            result["strike"] = False
        elif 30 <= code <= 37:
            result["fg"] = ANSI_COLORS[code - 30]
        elif code == 39:
            result["fg"] = "default"
        elif 40 <= code <= 47:
            result["bg"] = ANSI_COLORS[code - 40]
        elif code == 49:
            result["bg"] = "default"
        elif 90 <= code <= 97:
            result["fg"] = BRIGHT_ANSI_COLORS[code - 90]
        elif 100 <= code <= 107:
            result["bg"] = BRIGHT_ANSI_COLORS[code - 100]
        elif code == 38:
            result["fg"], index = resolve_extended_color(values, index)
            continue
        elif code == 48:
            result["bg"], index = resolve_extended_color(values, index)
            continue
        index += 1
    return result


def tokenize_ansi(text: str) -> List[Dict[str, Any]]:
    tokens: List[Dict[str, Any]] = []
    index = 0

    def append_text(value: str) -> None:
        if not value:
            return
        if tokens and tokens[-1]["type"] == "text":
            tokens[-1]["text"] += value
        else:
            tokens.append({"type": "text", "text": value})

    while index < len(text):
        char = text[index]
        if char != "\x1b":
            next_escape = text.find("\x1b", index)
            if next_escape == -1:
                next_escape = len(text)
            append_text(text[index:next_escape])
            index = next_escape
            continue

        if index + 1 >= len(text):
            append_text(text[index])
            break

        next_char = text[index + 1]
        if next_char == "[":
            final_index = index + 2
            while final_index < len(text) and not (0x40 <= ord(text[final_index]) <= 0x7E):
                final_index += 1
            if final_index >= len(text):
                append_text(text[index:])
                break
            raw = text[index : final_index + 1]
            params = text[index + 2 : final_index]
            final = text[final_index]
            if final == "m" and all(part.isdigit() or part == "" for part in params.split(";")):
                codes = [int(part) if part else 0 for part in params.split(";")] if params else [0]
                tokens.append({"type": "sgr", "raw": raw, "codes": codes})
            else:
                tokens.append(
                    {
                        "type": "escape",
                        "kind": "csi",
                        "raw": raw,
                        "params": params,
                        "final": final,
                    }
                )
            index = final_index + 1
            continue

        if next_char == "]":
            end_index = index + 2
            while end_index < len(text):
                if text[end_index] == "\x07":
                    end_index += 1
                    break
                if text[end_index] == "\x1b" and end_index + 1 < len(text) and text[end_index + 1] == "\\":
                    end_index += 2
                    break
                end_index += 1
            raw = text[index:end_index]
            tokens.append({"type": "escape", "kind": "osc", "raw": raw})
            index = end_index
            continue

        raw = text[index : index + 2]
        tokens.append({"type": "escape", "kind": "other", "raw": raw})
        index += 2

    return tokens


def char_width(char: str) -> int:
    if char == "\u200d":
        return 0
    if unicodedata.combining(char):
        return 0
    return 1


def build_rows_from_tokens(tokens: List[Dict[str, Any]], width_hint: Optional[int]) -> List[List[Dict[str, Any]]]:
    rows: List[List[Dict[str, Any]]] = [[]]
    style = default_style()

    def current_row() -> List[Dict[str, Any]]:
        return rows[-1]

    for token in tokens:
        if token["type"] == "sgr":
            style = apply_sgr_codes(style, token["codes"])
            continue
        if token["type"] != "text":
            continue
        for char in token["text"]:
            if char == "\r":
                continue
            if char == "\n":
                rows.append([])
                continue
            width = char_width(char)
            if width == 0 and current_row():
                current_row()[-1]["char"] += char
                continue
            current_row().append({"char": char, "style": clone_style(style), "continuation": False})

    if rows and rows[-1] == []:
        rows.pop()

    width = width_hint if width_hint is not None else max((len(row) for row in rows), default=0)
    for row in rows:
        while len(row) < width:
            row.append({"char": " ", "style": default_style(), "continuation": False})
    return rows


def capture_screen(
    session: str,
    *,
    history: Optional[int] = None,
    full_history: bool = False,
) -> CapturedScreen:
    info = session_info(session)
    width_hint = parse_dimension(info["width"], "width")
    ansi_text = capture_text(session, ansi=True, history=history, full_history=full_history)
    tokens = tokenize_ansi(ansi_text)
    rows = build_rows_from_tokens(tokens, width_hint=width_hint)
    width = width_hint if rows else width_hint
    height = len(rows)
    return CapturedScreen(
        info=info,
        ansi_text=ansi_text,
        tokens=tokens,
        rows=rows,
        width=width,
        height=height,
    )


def style_to_sgr_codes(style: Dict[str, Any]) -> List[str]:
    codes = ["0"]
    if style["bold"]:
        codes.append("1")
    if style["dim"]:
        codes.append("2")
    if style["italic"]:
        codes.append("3")
    if style["underline"]:
        codes.append("4")
    if style["blink"]:
        codes.append("5")
    if style["reverse"]:
        codes.append("7")
    if style["hidden"]:
        codes.append("8")
    if style["strike"]:
        codes.append("9")

    def append_color(channel: str, is_background: bool) -> None:
        value = style[channel]
        if value == "default":
            return
        if value in ANSI_COLORS:
            base = 40 if is_background else 30
            codes.append(str(base + ANSI_COLORS.index(value)))
            return
        if value in BRIGHT_ANSI_COLORS:
            base = 100 if is_background else 90
            codes.append(str(base + BRIGHT_ANSI_COLORS.index(value)))
            return
        if value.startswith("index:"):
            index = value.split(":", 1)[1]
            prefix = "48" if is_background else "38"
            codes.extend([prefix, "5", index])
            return
        if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
            red = int(value[1:3], 16)
            green = int(value[3:5], 16)
            blue = int(value[5:7], 16)
            prefix = "48" if is_background else "38"
            codes.extend([prefix, "2", str(red), str(green), str(blue)])

    append_color("fg", False)
    append_color("bg", True)
    return codes


def style_to_sgr(style: Dict[str, Any]) -> str:
    return f"\x1b[{';'.join(style_to_sgr_codes(style))}m"


def rows_to_text(rows: List[List[Dict[str, Any]]], *, ansi: bool) -> str:
    rendered_lines: List[str] = []
    for row in rows:
        if not ansi:
            rendered_lines.append("".join(cell["char"] for cell in row))
            continue
        pieces: List[str] = []
        current_style = default_style()
        for cell in row:
            if cell["style"] != current_style:
                pieces.append(style_to_sgr(cell["style"]))
                current_style = clone_style(cell["style"])
            pieces.append(cell["char"])
        if current_style != DEFAULT_STYLE:
            pieces.append("\x1b[0m")
        rendered_lines.append("".join(pieces))
    return "\n".join(rendered_lines)


def plain_lines(rows: List[List[Dict[str, Any]]]) -> List[str]:
    return ["".join(cell["char"] for cell in row) for row in rows]


def resolve_range(spec: Optional[str], maximum: int, label: str) -> Tuple[int, int]:
    if maximum < 1:
        raise HarnessError(f"no {label} are available in the current capture")
    if spec is None:
        return 1, maximum
    if ":" not in spec:
        value = int(spec)
        if value < 1 or value > maximum:
            raise HarnessError(f"{label} {value} is outside 1:{maximum}")
        return value, value
    start_text, end_text = spec.split(":", 1)
    start = int(start_text) if start_text else 1
    end = int(end_text) if end_text else maximum
    start = max(1, start)
    end = min(maximum, end)
    if start > end:
        raise HarnessError(f"invalid {label} range {spec!r} for maximum {maximum}")
    return start, end


def crop_rows(
    rows: List[List[Dict[str, Any]]],
    row_range: Tuple[int, int],
    col_range: Tuple[int, int],
) -> List[List[Dict[str, Any]]]:
    row_start, row_end = row_range
    col_start, col_end = col_range
    cropped: List[List[Dict[str, Any]]] = []
    for row in rows[row_start - 1 : row_end]:
        cropped.append(
            [
                {
                    "char": cell["char"],
                    "style": clone_style(cell["style"]),
                    "continuation": cell.get("continuation", False),
                }
                for cell in row[col_start - 1 : col_end]
            ]
        )
    return cropped


def visible_repr_char(char: str) -> str:
    if char == "\x1b":
        return "\\x1b"
    if char == "\t":
        return "\\t"
    if char == "\\":
        return "\\\\"
    if char == "\r":
        return "\\r"
    if ord(char) < 32 or ord(char) == 127:
        return f"\\x{ord(char):02x}"
    return char


def visible_repr_text(text: str) -> str:
    return "\n".join("".join(visible_repr_char(char) for char in line) for line in text.splitlines())


def build_ruler_lines(start_col: int, end_col: int) -> List[str]:
    digits = len(str(end_col))
    lines: List[str] = []
    for power in range(digits - 1, -1, -1):
        line_chars: List[str] = []
        threshold = 10**power
        for col in range(start_col, end_col + 1):
            if power > 0 and col < threshold:
                line_chars.append(" ")
            else:
                line_chars.append(str((col // threshold) % 10))
        lines.append("".join(line_chars))
    return lines


def display_text(
    text: str,
    *,
    start_row: int,
    start_col: int,
    number_lines: bool,
    ruler: bool,
    repr_mode: bool,
) -> str:
    lines = text.splitlines()
    if repr_mode:
        lines = ["".join(visible_repr_char(char) for char in line) for line in lines]

    prefix_width = len(str(start_row + max(len(lines) - 1, 0))) + 2 if number_lines else 0
    output: List[str] = []

    if ruler and lines:
        prefix = " " * prefix_width
        end_col = start_col + max(len(line) for line in lines) - 1
        for ruler_line in build_ruler_lines(start_col, end_col):
            output.append(f"{prefix}{ruler_line}")

    for offset, line in enumerate(lines):
        if number_lines:
            output.append(f"{start_row + offset:>{prefix_width - 2}}: {line}")
        else:
            output.append(line)
    return "\n".join(output)


def serialize_tokens(tokens: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    serialized: List[Dict[str, Any]] = []
    for token in tokens:
        if token["type"] == "text":
            serialized.append(
                {
                    "type": "text",
                    "text": token["text"],
                    "repr": visible_repr_text(token["text"]),
                }
            )
        else:
            payload = dict(token)
            payload["repr"] = visible_repr_text(token["raw"])
            serialized.append(payload)
    return serialized


def style_payload(style: Dict[str, Any]) -> Dict[str, Any]:
    payload = {
        "fg": style["fg"],
        "bg": style["bg"],
    }
    for flag in STYLE_FLAGS:
        payload[flag] = style[flag]
    return payload


def resolved_style_payload(style: Dict[str, Any]) -> Dict[str, Any]:
    fg = style["fg"]
    bg = style["bg"]
    if style["reverse"]:
        fg, bg = bg, fg
    payload = style_payload(style)
    payload["resolved_fg"] = fg
    payload["resolved_bg"] = bg
    return payload


def ensure_cell_bounds(screen: CapturedScreen, row: int, col: int, label: str) -> None:
    if row < 1 or row > screen.height:
        raise HarnessError(f"{label} row={row} is outside 1:{screen.height}")
    if col < 1 or col > screen.width:
        raise HarnessError(f"{label} col={col} is outside 1:{screen.width}")


def find_matches_in_lines(
    lines: List[str],
    needle: str,
    *,
    ignore_case: bool = False,
    max_results: Optional[int] = None,
) -> List[Dict[str, Any]]:
    if needle == "":
        raise HarnessError("search text must not be empty")
    haystack_lines = lines
    search_needle = needle
    if ignore_case:
        haystack_lines = [line.lower() for line in lines]
        search_needle = needle.lower()

    matches: List[Dict[str, Any]] = []
    for row_index, haystack in enumerate(haystack_lines, start=1):
        start = 0
        while True:
            found = haystack.find(search_needle, start)
            if found == -1:
                break
            start_col = found + 1
            end_col = found + len(search_needle)
            match = {
                "row": row_index,
                "start_col": start_col,
                "end_col": end_col,
                "line": lines[row_index - 1],
            }
            matches.append(match)
            if max_results is not None and len(matches) >= max_results:
                return matches
            start = found + 1
    return matches


def anchor_col(match: Dict[str, Any], anchor: str) -> int:
    if anchor == "start":
        return match["start_col"]
    if anchor == "end":
        return match["end_col"]
    return match["start_col"] + ((match["end_col"] - match["start_col"]) // 2)


def resolve_click_like_target(
    screen: CapturedScreen,
    *,
    row: Optional[int],
    col: Optional[int],
    text: Optional[str],
    anchor: str,
    match_index: int,
    ignore_case: bool,
) -> Tuple[int, int, Optional[Dict[str, Any]]]:
    if text:
        matches = find_matches_in_lines(plain_lines(screen.rows), text, ignore_case=ignore_case)
        if not matches:
            raise HarnessError(f"could not find text target {text!r}")
        if match_index < 1 or match_index > len(matches):
            raise HarnessError(f"match index {match_index} is outside 1:{len(matches)}")
        match = matches[match_index - 1]
        target_row = match["row"]
        target_col = anchor_col(match, anchor)
        ensure_cell_bounds(screen, target_row, target_col, "text target")
        return target_row, target_col, match

    if row is None or col is None:
        raise HarnessError("provide either --text or both --row and --col")
    ensure_cell_bounds(screen, row, col, "mouse target")
    return row, col, None


def resolve_drag_endpoint(
    screen: CapturedScreen,
    *,
    row: Optional[int],
    col: Optional[int],
    text: Optional[str],
    anchor: str,
    match_index: int,
    ignore_case: bool,
    label: str,
) -> Tuple[int, int, Optional[Dict[str, Any]]]:
    if text:
        matches = find_matches_in_lines(plain_lines(screen.rows), text, ignore_case=ignore_case)
        if not matches:
            raise HarnessError(f"could not find {label} text target {text!r}")
        if match_index < 1 or match_index > len(matches):
            raise HarnessError(f"{label} match index {match_index} is outside 1:{len(matches)}")
        match = matches[match_index - 1]
        resolved_row = match["row"]
        resolved_col = anchor_col(match, anchor)
        ensure_cell_bounds(screen, resolved_row, resolved_col, label)
        return resolved_row, resolved_col, match

    if row is None or col is None:
        raise HarnessError(f"provide either {label} text or both {label} coordinates")
    ensure_cell_bounds(screen, row, col, label)
    return row, col, None


def sgr_mouse(code: int, row: int, col: int, *, release: bool = False) -> str:
    suffix = "m" if release else "M"
    return f"\x1b[<{code};{col};{row}{suffix}"


def drag_points(
    start_row: int,
    start_col: int,
    end_row: int,
    end_col: int,
    steps: Optional[int],
) -> List[Tuple[int, int]]:
    row_delta = end_row - start_row
    col_delta = end_col - start_col
    total_steps = steps if steps is not None else max(abs(row_delta), abs(col_delta))
    total_steps = max(1, total_steps)

    points: List[Tuple[int, int]] = []
    for index in range(1, total_steps + 1):
        ratio = index / total_steps
        row = round(start_row + (row_delta * ratio))
        col = round(start_col + (col_delta * ratio))
        point = (row, col)
        if not points or points[-1] != point:
            points.append(point)
    return points


def payload_for_rows(
    screen: CapturedScreen,
    rows: List[List[Dict[str, Any]]],
    *,
    row_range: Tuple[int, int],
    col_range: Tuple[int, int],
    ansi: bool,
    number_lines: bool,
    ruler: bool,
    repr_mode: bool,
    include_tokens: bool,
) -> Dict[str, Any]:
    text = rows_to_text(rows, ansi=ansi)
    plain_text = rows_to_text(rows, ansi=False)
    payload: Dict[str, Any] = {
        "ansi": ansi,
        "text": text,
        "plain_text": plain_text,
        "line_count": len(rows),
        "col_count": col_range[1] - col_range[0] + 1,
        "rows": f"{row_range[0]}:{row_range[1]}",
        "cols": f"{col_range[0]}:{col_range[1]}",
    }
    if number_lines or ruler or repr_mode:
        payload["display_text"] = display_text(
            text if ansi else plain_text,
            start_row=row_range[0],
            start_col=col_range[0],
            number_lines=number_lines,
            ruler=ruler,
            repr_mode=repr_mode,
        )
    if repr_mode:
        payload["repr_text"] = visible_repr_text(text if ansi else plain_text)
    if include_tokens:
        payload["tokens"] = serialize_tokens(tokenize_ansi(text if ansi else plain_text))
    return payload


def load_snapshot(session: str, name: str) -> Dict[str, Any]:
    path = snapshot_path(session, name)
    if not path.exists():
        raise HarnessError(f"snapshot {name!r} for session {session!r} does not exist")
    return json.loads(path.read_text())


def sanitize_snapshot_name(name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-")
    if not sanitized:
        raise HarnessError(f"invalid snapshot name {name!r}")
    return sanitized


def snapshot_path(session: str, name: str) -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    safe_session = sanitize_snapshot_name(session)
    safe_name = sanitize_snapshot_name(name)
    return SNAPSHOT_DIR / f"{safe_session}--{safe_name}.json"


def build_screen_from_snapshot(data: Dict[str, Any]) -> CapturedScreen:
    info = dict(data["info"])
    width_hint = parse_dimension(info["width"], "width")
    tokens = tokenize_ansi(data["ansi_text"])
    rows = build_rows_from_tokens(tokens, width_hint=width_hint)
    return CapturedScreen(
        info=info,
        ansi_text=data["ansi_text"],
        tokens=tokens,
        rows=rows,
        width=width_hint,
        height=len(rows),
    )


def cell_diff(before: Dict[str, Any], after: Dict[str, Any]) -> Tuple[bool, bool]:
    text_changed = before["char"] != after["char"]
    style_changed = before["style"] != after["style"]
    return text_changed, style_changed


def diff_changes(
    before_rows: List[List[Dict[str, Any]]],
    after_rows: List[List[Dict[str, Any]]],
    *,
    row_offset: int,
    col_offset: int,
    style_only: bool,
) -> List[Dict[str, Any]]:
    changes: List[Dict[str, Any]] = []
    max_rows = max(len(before_rows), len(after_rows))
    max_cols = max((len(row) for row in before_rows + after_rows), default=0)

    def get(rows: List[List[Dict[str, Any]]], row_index: int, col_index: int) -> Dict[str, Any]:
        if row_index >= len(rows) or col_index >= len(rows[row_index]):
            return {"char": " ", "style": default_style(), "continuation": False}
        return rows[row_index][col_index]

    for row_index in range(max_rows):
        for col_index in range(max_cols):
            before = get(before_rows, row_index, col_index)
            after = get(after_rows, row_index, col_index)
            text_changed, style_changed = cell_diff(before, after)
            if style_only:
                if before["char"] != after["char"] or not style_changed:
                    continue
            elif not text_changed and not style_changed:
                continue
            changes.append(
                {
                    "row": row_offset + row_index,
                    "col": col_offset + col_index,
                    "before_char": before["char"],
                    "after_char": after["char"],
                    "text_changed": text_changed,
                    "style_changed": style_changed,
                    "before_style": style_payload(before["style"]),
                    "after_style": style_payload(after["style"]),
                    "before_resolved_style": resolved_style_payload(before["style"]),
                    "after_resolved_style": resolved_style_payload(after["style"]),
                }
            )
    return changes


def bounding_box(changes: List[Dict[str, Any]]) -> Optional[Dict[str, int]]:
    if not changes:
        return None
    rows = [change["row"] for change in changes]
    cols = [change["col"] for change in changes]
    return {
        "start_row": min(rows),
        "end_row": max(rows),
        "start_col": min(cols),
        "end_col": max(cols),
    }


def cmd_start(args: argparse.Namespace) -> None:
    session = args.session or f"codex-tui-{uuid.uuid4().hex[:8]}"
    command = build_command(args.argv, args.env)

    tmux_args = [
        "new-session",
        "-d",
        "-P",
        "-F",
        "#{session_name}",
        "-s",
        session,
        "-x",
        str(args.width),
        "-y",
        str(args.height),
    ]
    if args.cwd:
        tmux_args.extend(["-c", args.cwd])
    tmux_args.append(command)

    run_tmux(tmux_args)
    run_tmux(["set-window-option", "-t", session, "remain-on-exit", "on"])
    info = session_info(session)
    info["action"] = "start"
    info["command_line"] = command
    emit(info)


def cmd_send(args: argparse.Namespace) -> None:
    if not args.literal and not args.key:
        raise HarnessError("send requires at least one --literal or --key")

    for text in args.literal:
        send_literal(args.session, text)
    if args.key:
        run_tmux(["send-keys", "-t", args.session, *args.key])
    if args.pause_ms > 0:
        time.sleep(args.pause_ms / 1000.0)

    info = session_info(args.session)
    info["action"] = "send"
    emit(info)


def cmd_mouse_click(args: argparse.Namespace) -> None:
    screen = capture_screen(args.session)
    row, col, match = resolve_click_like_target(
        screen,
        row=args.row,
        col=args.col,
        text=args.text,
        anchor=args.anchor,
        match_index=args.match_index,
        ignore_case=args.ignore_case,
    )
    button_code = BUTTON_CODES[args.button]
    send_literal(args.session, sgr_mouse(button_code, row, col))
    if args.hold_ms > 0:
        time.sleep(args.hold_ms / 1000.0)
    send_literal(args.session, sgr_mouse(button_code, row, col, release=True))
    if args.pause_ms > 0:
        time.sleep(args.pause_ms / 1000.0)

    info = session_info(args.session)
    info["action"] = "mouse"
    info["mouse_action"] = "click"
    info["button"] = args.button
    info["row"] = row
    info["col"] = col
    if match:
        info["target_match"] = {
            "text": args.text,
            "row": match["row"],
            "start_col": match["start_col"],
            "end_col": match["end_col"],
            "anchor": args.anchor,
            "match_index": args.match_index,
        }
    emit(info)


def cmd_mouse_scroll(args: argparse.Namespace) -> None:
    if args.amount < 1:
        raise HarnessError(f"scroll amount must be at least 1, got {args.amount}")
    screen = capture_screen(args.session)
    row, col, match = resolve_click_like_target(
        screen,
        row=args.row,
        col=args.col,
        text=args.text,
        anchor=args.anchor,
        match_index=args.match_index,
        ignore_case=args.ignore_case,
    )
    code = SCROLL_CODES[args.direction]
    for _ in range(args.amount):
        send_literal(args.session, sgr_mouse(code, row, col))
    if args.pause_ms > 0:
        time.sleep(args.pause_ms / 1000.0)

    info = session_info(args.session)
    info["action"] = "mouse"
    info["mouse_action"] = "scroll"
    info["direction"] = args.direction
    info["amount"] = args.amount
    info["row"] = row
    info["col"] = col
    if match:
        info["target_match"] = {
            "text": args.text,
            "row": match["row"],
            "start_col": match["start_col"],
            "end_col": match["end_col"],
            "anchor": args.anchor,
            "match_index": args.match_index,
        }
    emit(info)


def cmd_mouse_drag(args: argparse.Namespace) -> None:
    if args.steps is not None and args.steps < 1:
        raise HarnessError(f"drag steps must be at least 1, got {args.steps}")
    screen = capture_screen(args.session)
    start_row, start_col, start_match = resolve_drag_endpoint(
        screen,
        row=args.start_row,
        col=args.start_col,
        text=args.start_text,
        anchor=args.start_anchor,
        match_index=args.start_match_index,
        ignore_case=args.ignore_case,
        label="drag start",
    )
    end_row, end_col, end_match = resolve_drag_endpoint(
        screen,
        row=args.end_row,
        col=args.end_col,
        text=args.end_text,
        anchor=args.end_anchor,
        match_index=args.end_match_index,
        ignore_case=args.ignore_case,
        label="drag end",
    )
    button_code = BUTTON_CODES[args.button]

    send_literal(args.session, sgr_mouse(button_code, start_row, start_col))
    points = drag_points(start_row, start_col, end_row, end_col, args.steps)
    motion_code = button_code + 32
    for row, col in points:
        send_literal(args.session, sgr_mouse(motion_code, row, col))
        if args.step_pause_ms > 0:
            time.sleep(args.step_pause_ms / 1000.0)
    send_literal(args.session, sgr_mouse(button_code, end_row, end_col, release=True))
    if args.pause_ms > 0:
        time.sleep(args.pause_ms / 1000.0)

    info = session_info(args.session)
    info["action"] = "mouse"
    info["mouse_action"] = "drag"
    info["button"] = args.button
    info["start_row"] = start_row
    info["start_col"] = start_col
    info["end_row"] = end_row
    info["end_col"] = end_col
    info["events_sent"] = len(points) + 2
    if start_match:
        info["start_match"] = {
            "text": args.start_text,
            "row": start_match["row"],
            "start_col": start_match["start_col"],
            "end_col": start_match["end_col"],
            "anchor": args.start_anchor,
            "match_index": args.start_match_index,
        }
    if end_match:
        info["end_match"] = {
            "text": args.end_text,
            "row": end_match["row"],
            "start_col": end_match["start_col"],
            "end_col": end_match["end_col"],
            "anchor": args.end_anchor,
            "match_index": args.end_match_index,
        }
    emit(info)


def cmd_read(args: argparse.Namespace) -> None:
    screen = capture_screen(args.session, history=args.history, full_history=args.full_history)
    row_range = resolve_range(args.lines, screen.height, "line")
    col_range = resolve_range(args.cols, screen.width, "column")
    rows = crop_rows(screen.rows, row_range, col_range)

    payload = dict(screen.info)
    payload["action"] = "read"
    payload.update(
        payload_for_rows(
            screen,
            rows,
            row_range=row_range,
            col_range=col_range,
            ansi=args.ansi,
            number_lines=args.number_lines,
            ruler=args.ruler,
            repr_mode=args.repr_mode,
            include_tokens=args.tokens,
        )
    )
    emit(payload)


def cmd_wait(args: argparse.Namespace) -> None:
    baseline = capture_text(args.session, ansi=args.ansi, history=args.history, full_history=args.full_history)
    last = baseline
    stable_since = time.monotonic()
    saw_change = False
    deadline = time.monotonic() + (args.timeout_ms / 1000.0)

    while time.monotonic() <= deadline:
        time.sleep(args.poll_ms / 1000.0)
        current = capture_text(args.session, ansi=args.ansi, history=args.history, full_history=args.full_history)

        if args.mode == "change":
            if current != baseline:
                payload = session_info(args.session)
                payload["action"] = "wait"
                payload["mode"] = args.mode
                payload["changed"] = True
                payload["text"] = current
                emit(payload)
            continue

        if current != last:
            saw_change = True
            last = current
            stable_since = time.monotonic()
            continue

        stable_enough = (time.monotonic() - stable_since) * 1000.0 >= args.stable_ms
        if stable_enough and (saw_change or not args.require_change):
            payload = session_info(args.session)
            payload["action"] = "wait"
            payload["mode"] = args.mode
            payload["changed"] = saw_change
            payload["text"] = current
            emit(payload)

    fail(
        f"timed out waiting for session {args.session!r}",
        detail=f"mode={args.mode} timeout_ms={args.timeout_ms}",
        exit_code=2,
    )


def cmd_cell(args: argparse.Namespace) -> None:
    screen = capture_screen(args.session, history=args.history, full_history=args.full_history)
    ensure_cell_bounds(screen, args.row, args.col, "cell")
    cell = screen.rows[args.row - 1][args.col - 1]
    payload = dict(screen.info)
    payload["action"] = "cell"
    payload["row"] = args.row
    payload["col"] = args.col
    payload["char"] = cell["char"]
    payload["line"] = plain_lines(screen.rows)[args.row - 1]
    payload["style"] = style_payload(cell["style"])
    payload["resolved_style"] = resolved_style_payload(cell["style"])
    emit(payload)


def cmd_region(args: argparse.Namespace) -> None:
    screen = capture_screen(args.session, history=args.history, full_history=args.full_history)
    row_range = resolve_range(args.rows, screen.height, "row")
    col_range = resolve_range(args.cols, screen.width, "column")
    rows = crop_rows(screen.rows, row_range, col_range)

    payload = dict(screen.info)
    payload["action"] = "region"
    payload.update(
        payload_for_rows(
            screen,
            rows,
            row_range=row_range,
            col_range=col_range,
            ansi=args.ansi,
            number_lines=args.number_lines,
            ruler=args.ruler,
            repr_mode=args.repr_mode,
            include_tokens=args.tokens,
        )
    )
    if args.styles:
        styled_rows: List[List[Dict[str, Any]]] = []
        for row_offset, row in enumerate(rows, start=row_range[0]):
            styled_row: List[Dict[str, Any]] = []
            for col_offset, cell in enumerate(row, start=col_range[0]):
                styled_row.append(
                    {
                        "row": row_offset,
                        "col": col_offset,
                        "char": cell["char"],
                        "style": style_payload(cell["style"]),
                        "resolved_style": resolved_style_payload(cell["style"]),
                    }
                )
            styled_rows.append(styled_row)
        payload["cells"] = styled_rows
    emit(payload)


def cmd_find_text(args: argparse.Namespace) -> None:
    screen = capture_screen(args.session, history=args.history, full_history=args.full_history)
    matches = find_matches_in_lines(
        plain_lines(screen.rows),
        args.text,
        ignore_case=args.ignore_case,
        max_results=args.max_results,
    )
    payload = dict(screen.info)
    payload["action"] = "find-text"
    payload["search_text"] = args.text
    payload["match_count"] = len(matches)
    payload["matches"] = [
        {
            **match,
            "anchor_cols": {
                "start": match["start_col"],
                "center": anchor_col(match, "center"),
                "end": match["end_col"],
            },
        }
        for match in matches
    ]
    emit(payload)


def cmd_snapshot(args: argparse.Namespace) -> None:
    screen = capture_screen(args.session, history=args.history, full_history=args.full_history)
    name = sanitize_snapshot_name(args.name)
    path = snapshot_path(args.session, name)
    if path.exists() and not args.overwrite:
        raise HarnessError(f"snapshot {name!r} for session {args.session!r} already exists")

    data = {
        "session": args.session,
        "name": name,
        "captured_at_epoch_ms": int(time.time() * 1000),
        "info": screen.info,
        "ansi_text": screen.ansi_text,
        "plain_text": rows_to_text(screen.rows, ansi=False),
    }
    path.write_text(json.dumps(data, indent=2, sort_keys=True))

    payload = dict(screen.info)
    payload["action"] = "snapshot"
    payload["snapshot_name"] = name
    payload["snapshot_path"] = str(path)
    payload["line_count"] = screen.height
    payload["col_count"] = screen.width
    emit(payload)


def cmd_diff(args: argparse.Namespace) -> None:
    before_snapshot = load_snapshot(args.session, args.before)
    before_screen = build_screen_from_snapshot(before_snapshot)

    if args.after:
        after_snapshot = load_snapshot(args.session, args.after)
        after_screen = build_screen_from_snapshot(after_snapshot)
        after_label = args.after
    else:
        after_screen = capture_screen(args.session)
        after_label = "current"

    max_height = max(before_screen.height, after_screen.height)
    max_width = max(before_screen.width, after_screen.width)
    row_range = resolve_range(args.lines, max_height, "line")
    col_range = resolve_range(args.cols, max_width, "column")

    before_rows = crop_rows(before_screen.rows, row_range, col_range)
    after_rows = crop_rows(after_screen.rows, row_range, col_range)
    changes = diff_changes(
        before_rows,
        after_rows,
        row_offset=row_range[0],
        col_offset=col_range[0],
        style_only=args.style_only,
    )
    bbox = bounding_box(changes)

    preview_row_range = row_range
    preview_col_range = col_range
    if bbox and not args.lines and not args.cols:
        preview_row_range = (bbox["start_row"], bbox["end_row"])
        preview_col_range = (bbox["start_col"], bbox["end_col"])
        before_rows = crop_rows(before_screen.rows, preview_row_range, preview_col_range)
        after_rows = crop_rows(after_screen.rows, preview_row_range, preview_col_range)

    payload = dict(after_screen.info)
    payload["action"] = "diff"
    payload["before"] = args.before
    payload["after"] = after_label
    payload["style_only"] = args.style_only
    payload["changed_cell_count"] = len(changes)
    payload["style_change_count"] = sum(1 for change in changes if change["style_changed"])
    payload["text_change_count"] = sum(1 for change in changes if change["text_changed"])
    payload["bounding_box"] = bbox
    payload["changes"] = changes[: args.max_changes]
    payload["changes_truncated"] = len(changes) > args.max_changes
    payload["before_preview"] = payload_for_rows(
        before_screen,
        before_rows,
        row_range=preview_row_range,
        col_range=preview_col_range,
        ansi=args.ansi,
        number_lines=args.number_lines,
        ruler=args.ruler,
        repr_mode=args.repr_mode,
        include_tokens=False,
    )
    payload["after_preview"] = payload_for_rows(
        after_screen,
        after_rows,
        row_range=preview_row_range,
        col_range=preview_col_range,
        ansi=args.ansi,
        number_lines=args.number_lines,
        ruler=args.ruler,
        repr_mode=args.repr_mode,
        include_tokens=False,
    )
    emit(payload)


def cmd_resize(args: argparse.Namespace) -> None:
    run_tmux(
        [
            "resize-window",
            "-t",
            args.session,
            "-x",
            str(args.width),
            "-y",
            str(args.height),
        ]
    )
    info = session_info(args.session)
    info["action"] = "resize"
    emit(info)


def cmd_info(args: argparse.Namespace) -> None:
    info = session_info(args.session)
    info["action"] = "info"
    emit(info)


def cmd_stop(args: argparse.Namespace) -> None:
    if not session_exists(args.session):
        if args.ignore_missing:
            emit({"action": "stop", "ok": True, "session": args.session, "stopped": False})
        raise HarnessError(f"session {args.session!r} does not exist")

    run_tmux(["kill-session", "-t", args.session])
    emit({"action": "stop", "ok": True, "session": args.session, "stopped": True})


def add_capture_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--history", type=int, help="Include N lines of scrollback")
    parser.add_argument(
        "--full-history",
        action="store_true",
        help="Include full scrollback history",
    )


def add_display_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--plain",
        dest="ansi",
        action="store_false",
        help="Strip ANSI escape codes and render plain text only",
    )
    parser.set_defaults(ansi=True)
    parser.add_argument(
        "--number-lines",
        action="store_true",
        help="Include line numbers in display_text",
    )
    parser.add_argument(
        "--ruler",
        action="store_true",
        help="Include a column ruler in display_text",
    )
    parser.add_argument(
        "--repr",
        dest="repr_mode",
        action="store_true",
        help="Expose control characters and ANSI escapes in visible repr form",
    )
    parser.add_argument(
        "--tokens",
        action="store_true",
        help="Include parsed ANSI/text tokens for the extracted text",
    )


def add_range_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--lines", help="Inclusive line range like 10:20")
    parser.add_argument("--cols", help="Inclusive column range like 5:80")


def add_text_target_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--row", type=int, help="1-based row in the pane")
    parser.add_argument("--col", type=int, help="1-based column in the pane")
    parser.add_argument("--text", help="Click or scroll at a matching text span instead of row,col")
    parser.add_argument(
        "--anchor",
        choices=ANCHORS,
        default="center",
        help="Anchor within a text match when --text is used",
    )
    parser.add_argument(
        "--match-index",
        type=int,
        default=1,
        help="1-based match occurrence when --text is used",
    )
    parser.add_argument(
        "--ignore-case",
        action="store_true",
        help="Match text targets case-insensitively",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Launch and inspect TUIs in tmux with JSON output."
    )
    subparsers = parser.add_subparsers(dest="action", required=True)

    start = subparsers.add_parser("start", help="Start a detached tmux session")
    start.add_argument("--session", help="Explicit tmux session name")
    start.add_argument("--cwd", help="Working directory for the command")
    start.add_argument("--width", type=int, default=120, help="Pane width")
    start.add_argument("--height", type=int, default=40, help="Pane height")
    start.add_argument(
        "--env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Environment variable to inject into the command",
    )
    start.add_argument("argv", nargs=argparse.REMAINDER, help="Command to run after --")
    start.set_defaults(func=cmd_start)

    send = subparsers.add_parser("send", help="Send keys or literal text to a session")
    send.add_argument("session", help="tmux session name")
    send.add_argument(
        "--literal",
        action="append",
        default=[],
        help="Literal text to send verbatim",
    )
    send.add_argument(
        "--key",
        action="append",
        default=[],
        help="Named tmux key such as Enter or C-c",
    )
    send.add_argument(
        "--pause-ms",
        type=int,
        default=0,
        help="Optional pause after sending input",
    )
    send.set_defaults(func=cmd_send)

    mouse = subparsers.add_parser("mouse", help="Send mouse events to a session")
    mouse_subparsers = mouse.add_subparsers(dest="mouse_action", required=True)

    click = mouse_subparsers.add_parser("click", help="Send a mouse click")
    click.add_argument("session", help="tmux session name")
    add_text_target_args(click)
    click.add_argument(
        "--button",
        choices=tuple(BUTTON_CODES.keys()),
        default="left",
        help="Mouse button to click",
    )
    click.add_argument("--hold-ms", type=int, default=0, help="Optional press duration before release")
    click.add_argument("--pause-ms", type=int, default=0, help="Optional pause after the click sequence")
    click.set_defaults(func=cmd_mouse_click)

    scroll = mouse_subparsers.add_parser("scroll", help="Send mouse wheel events")
    scroll.add_argument("session", help="tmux session name")
    add_text_target_args(scroll)
    scroll.add_argument(
        "--direction",
        choices=tuple(SCROLL_CODES.keys()),
        required=True,
        help="Scroll direction",
    )
    scroll.add_argument("--amount", type=int, default=1, help="Number of wheel events to send")
    scroll.add_argument("--pause-ms", type=int, default=0, help="Optional pause after the scroll sequence")
    scroll.set_defaults(func=cmd_mouse_scroll)

    drag = mouse_subparsers.add_parser("drag", help="Send a click-and-drag gesture")
    drag.add_argument("session", help="tmux session name")
    drag.add_argument("--start-row", type=int, help="1-based drag start row")
    drag.add_argument("--start-col", type=int, help="1-based drag start column")
    drag.add_argument("--end-row", type=int, help="1-based drag end row")
    drag.add_argument("--end-col", type=int, help="1-based drag end column")
    drag.add_argument("--start-text", help="Resolve drag start from matching text")
    drag.add_argument("--end-text", help="Resolve drag end from matching text")
    drag.add_argument(
        "--start-anchor",
        choices=ANCHORS,
        default="center",
        help="Anchor within the start text match",
    )
    drag.add_argument(
        "--end-anchor",
        choices=ANCHORS,
        default="center",
        help="Anchor within the end text match",
    )
    drag.add_argument("--start-match-index", type=int, default=1, help="1-based start text match occurrence")
    drag.add_argument("--end-match-index", type=int, default=1, help="1-based end text match occurrence")
    drag.add_argument(
        "--ignore-case",
        action="store_true",
        help="Match drag text targets case-insensitively",
    )
    drag.add_argument(
        "--button",
        choices=tuple(BUTTON_CODES.keys()),
        default="left",
        help="Mouse button used for the drag",
    )
    drag.add_argument(
        "--steps",
        type=int,
        help="Number of motion events between start and end; defaults to path length",
    )
    drag.add_argument("--step-pause-ms", type=int, default=0, help="Optional pause between motion events")
    drag.add_argument("--pause-ms", type=int, default=0, help="Optional pause after the drag sequence")
    drag.set_defaults(func=cmd_mouse_drag)

    read = subparsers.add_parser("read", help="Capture the current pane text")
    read.add_argument("session", help="tmux session name")
    add_capture_args(read)
    add_display_flags(read)
    add_range_flags(read)
    read.set_defaults(func=cmd_read)

    wait = subparsers.add_parser("wait", help="Wait for screen change or stability")
    wait.add_argument("session", help="tmux session name")
    wait.add_argument(
        "--mode",
        choices=("stable", "change"),
        default="stable",
        help="Wait for stability or for any change from the baseline capture",
    )
    wait.add_argument("--timeout-ms", type=int, default=2000, help="Overall timeout")
    wait.add_argument("--poll-ms", type=int, default=100, help="Polling interval")
    wait.add_argument(
        "--stable-ms",
        type=int,
        default=300,
        help="How long the screen must remain unchanged in stable mode",
    )
    wait.add_argument(
        "--require-change",
        action="store_true",
        help="Only succeed in stable mode after at least one redraw",
    )
    wait.add_argument(
        "--plain",
        dest="ansi",
        action="store_false",
        help="Strip ANSI escape codes and compare plain-text captures only",
    )
    wait.set_defaults(ansi=True)
    add_capture_args(wait)
    wait.set_defaults(func=cmd_wait)

    cell = subparsers.add_parser("cell", help="Inspect one cell at row,col")
    cell.add_argument("session", help="tmux session name")
    cell.add_argument("--row", type=int, required=True, help="1-based row")
    cell.add_argument("--col", type=int, required=True, help="1-based column")
    add_capture_args(cell)
    cell.set_defaults(func=cmd_cell)

    region = subparsers.add_parser("region", help="Inspect a cropped region of the pane")
    region.add_argument("session", help="tmux session name")
    region.add_argument("--rows", help="Inclusive row range like 10:20")
    region.add_argument("--cols", help="Inclusive column range like 5:80")
    region.add_argument("--styles", action="store_true", help="Include per-cell style information")
    add_capture_args(region)
    add_display_flags(region)
    region.set_defaults(func=cmd_region)

    find_text = subparsers.add_parser("find-text", help="Find text and return row,col spans")
    find_text.add_argument("session", help="tmux session name")
    find_text.add_argument("--text", required=True, help="Text to search for")
    find_text.add_argument("--ignore-case", action="store_true", help="Search case-insensitively")
    find_text.add_argument("--max-results", type=int, default=20, help="Maximum matches to return")
    add_capture_args(find_text)
    find_text.set_defaults(func=cmd_find_text)

    snapshot = subparsers.add_parser("snapshot", help="Save the current screen for later diffing")
    snapshot.add_argument("session", help="tmux session name")
    snapshot.add_argument("--name", required=True, help="Snapshot name")
    snapshot.add_argument("--overwrite", action="store_true", help="Replace an existing snapshot of the same name")
    add_capture_args(snapshot)
    snapshot.set_defaults(func=cmd_snapshot)

    diff = subparsers.add_parser("diff", help="Compare saved snapshots or a snapshot against the current screen")
    diff.add_argument("session", help="tmux session name")
    diff.add_argument("--before", required=True, help="Snapshot name for the baseline state")
    diff.add_argument("--after", help="Snapshot name for the comparison state; defaults to the current screen")
    diff.add_argument("--style-only", action="store_true", help="Only report cells with style changes and identical text")
    diff.add_argument("--max-changes", type=int, default=200, help="Maximum changed cells to include in the JSON payload")
    add_display_flags(diff)
    add_range_flags(diff)
    diff.set_defaults(func=cmd_diff)

    resize = subparsers.add_parser("resize", help="Resize the tmux window")
    resize.add_argument("session", help="tmux session name")
    resize.add_argument("--width", type=int, required=True, help="Pane width")
    resize.add_argument("--height", type=int, required=True, help="Pane height")
    resize.set_defaults(func=cmd_resize)

    info = subparsers.add_parser("info", help="Inspect the session metadata")
    info.add_argument("session", help="tmux session name")
    info.set_defaults(func=cmd_info)

    stop = subparsers.add_parser("stop", help="Kill the tmux session")
    stop.add_argument("session", help="tmux session name")
    stop.add_argument("--ignore-missing", action="store_true", help="Treat a missing session as a successful no-op")
    stop.set_defaults(func=cmd_stop)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except HarnessError as exc:
        fail(str(exc))


if __name__ == "__main__":
    main()
