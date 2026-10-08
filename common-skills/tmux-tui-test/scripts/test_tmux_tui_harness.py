import argparse
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path
from unittest import mock

import tmux_tui_harness as harness

FREEZE_EXEC = Path(__file__).with_name("freeze_exec.sh")
HARNESS = Path(harness.__file__)


class CliTests(unittest.TestCase):
    def parse(self, *argv: str) -> argparse.Namespace:
        return harness.build_parser().parse_args(argv)

    def test_native_aliases_and_short_option_forms(self) -> None:
        cases = [
            (("new", "-dsdemo", "-x80", "-y24", "--", "echo", "ok"), "new-session"),
            (("send", "-t%2", "-l", "-N3", "text"), "send-keys"),
            (("capturep", "-t%2", "-peJN", "-S-20", "-E-"), "capture-pane"),
            (("resizew", "-t@1", "-x80"), "resize-window"),
            (("ls",), "list-sessions"),
        ]
        for argv, action in cases:
            with self.subTest(argv=argv):
                self.assertEqual(self.parse(*argv).action, action)

    def test_creation_preserves_command_arguments_and_session_environment(self) -> None:
        args = self.parse(
            "new-session",
            "-s",
            "demo",
            "-c",
            "/tmp",
            "-e",
            "A=one two",
            "-e",
            "B=three",
            "--",
            "app",
            "argument with spaces",
        )
        with (
            mock.patch.object(
                harness, "run_tmux", return_value=harness.CommandResult("%4", "")
            ) as run,
            mock.patch.object(
                harness, "pane_info", return_value={"pane": "%4"}
            ) as info,
            mock.patch.object(harness, "emit") as emit,
        ):
            harness.cmd_new_session(args)
        command = run.call_args.args[0]
        self.assertEqual(
            command[command.index("--") + 1 : command.index(";")],
            ["app", "argument with spaces"],
        )
        self.assertIn("A=one two", command)
        self.assertIn("B=three", command)
        self.assertEqual(command.count("-e"), 2)
        info.assert_called_once_with("%4")
        self.assertEqual(emit.call_args.args[0]["action"], "new-session")

    def test_send_keeps_key_text_order_and_native_literal_repeat_flags(self) -> None:
        for flags in ([], ["-l", "-N", "3"]):
            args = self.parse("send-keys", "-t", "%4", *flags, "Enter", "hello", "Down")
            with (
                mock.patch.object(harness, "run_tmux") as run,
                mock.patch.object(harness, "pane_info", return_value={}),
                mock.patch.object(harness, "emit") as emit,
            ):
                harness.cmd_send_keys(args)
            self.assertEqual(
                run.call_args.args[0],
                [
                    "send-keys",
                    "-t",
                    "%4",
                    "-N",
                    "3" if flags else "1",
                    *(["-l"] if flags else []),
                    "--",
                    "Enter",
                    "hello",
                    "Down",
                ],
            )
            self.assertEqual(emit.call_args.args[0]["action"], "send-keys")

    def test_capture_forwards_native_flags_without_trimming(self) -> None:
        text = "styled   \n\n\n"
        with mock.patch.object(
            harness, "run_tmux", return_value=harness.CommandResult(text, "")
        ) as run:
            result = harness.capture_text(
                "%2",
                ansi=True,
                start_line="-",
                end_line="4",
                join_wrapped=True,
                preserve_trailing_spaces=True,
            )
        self.assertEqual(result, text)
        run.assert_called_once_with(
            ["capture-pane", "-t", "%2", "-p", "-J", "-e", "-N", "-S", "-", "-E", "4"],
            preserve_stdout=True,
        )

    def test_json_capture_keeps_native_text_and_defaults_to_plain(self) -> None:
        args = self.parse("capture-pane", "-t", "%2")
        text = "short\n\n"
        with (
            mock.patch.object(harness, "capture_text", return_value=text),
            mock.patch.object(harness, "pane_info", return_value={"width": "80"}),
            mock.patch.object(harness, "emit") as emit,
        ):
            harness.cmd_capture_pane(args)
        payload = emit.call_args.args[0]
        self.assertFalse(payload["ansi"])
        self.assertEqual(payload["text"], text)
        self.assertEqual(payload["line_count"], 2)

    def test_raw_capture_has_no_json_or_padding(self) -> None:
        args = self.parse("capture-pane", "-t", "%2", "-pe")
        text = "\x1b[31mred   \n\n\n"
        output = io.StringIO()
        with (
            mock.patch.object(harness, "capture_text", return_value=text),
            contextlib.redirect_stdout(output),
        ):
            harness.cmd_capture_pane(args)
        self.assertEqual(output.getvalue(), text)

    def test_raw_capture_rejects_json_presentation(self) -> None:
        for flag in (
            "--tokens",
            "--ruler",
            "--number-lines",
            "--repr",
            "--lines",
            "--cols",
        ):
            argv = ["capture-pane", "-t", "%2", "-p", flag]
            if flag in ("--lines", "--cols"):
                argv.append("1:2")
            with (
                self.subTest(flag=flag),
                self.assertRaisesRegex(harness.HarnessError, "JSON presentation"),
            ):
                harness.cmd_capture_pane(self.parse(*argv))

    def test_raw_failure_is_only_on_stderr(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(
                sys, "argv", ["harness", "capture-pane", "-t", "missing", "-p"]
            ),
            mock.patch.object(
                harness, "pane_info", side_effect=harness.HarnessError("missing target")
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as error,
        ):
            harness.main()
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("missing target", stderr.getvalue())

    def test_empty_tmux_metadata_does_not_resolve_to_implicit_target(self) -> None:
        with (
            mock.patch.object(
                harness,
                "run_tmux",
                return_value=harness.CommandResult("session=\tpane=\tsession_id=", ""),
            ),
            self.assertRaisesRegex(harness.HarnessError, "failed to inspect target"),
        ):
            harness.pane_info("missing")

    def test_shared_guard_also_covers_explicit_default_label(self) -> None:
        for socket in (None, "default"):
            with (
                mock.patch.object(harness, "TMUX_SOCKET", socket),
                mock.patch.object(harness, "run_tmux") as run,
                self.assertRaisesRegex(harness.HarnessError, "refusing to kill-server"),
            ):
                harness.cmd_kill_server(argparse.Namespace(i_am_sure=False))
            run.assert_not_called()

    def test_server_selection_is_explicit_and_cannot_be_empty(self) -> None:
        for argv in (
            ("-L", "", "list-sessions"),
            ("--shared", "-L", "other", "list-sessions"),
        ):
            with (
                self.subTest(argv=argv),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                self.parse(*argv)

    def test_snapshot_namespace_uses_resolved_server_instance_and_pane(self) -> None:
        info = {
            "socket_path": "/tmp/socket",
            "server_pid": "123",
            "server_start": "456",
            "pane": "%1",
        }
        with (
            tempfile.TemporaryDirectory() as directory,
            mock.patch.object(harness, "SNAPSHOT_DIR", Path(directory)),
        ):
            with mock.patch.object(harness, "pane_info", return_value=info):
                first = harness.snapshot_path("session", "before")
                self.assertEqual(first, harness.snapshot_path("%1", "before"))
            for key, value in (
                ("socket_path", "/tmp/other"),
                ("server_pid", "789"),
                ("server_start", "999"),
                ("pane", "%2"),
            ):
                with mock.patch.object(
                    harness, "pane_info", return_value={**info, key: value}
                ):
                    self.assertNotEqual(
                        first, harness.snapshot_path("session", "before")
                    )


class CellTests(unittest.TestCase):
    def rows(self, text: str, width: int = 20) -> list:
        return harness.build_rows_from_tokens(harness.tokenize_ansi(text), width)

    def test_wide_combining_and_emoji_cells(self) -> None:
        for glyph, width in (
            ("中", 2),
            ("e\u0301", 1),
            ("👩‍💻", 2),
            ("🇺🇸", 2),
            ("✈️", 2),
            ("👍🏽", 2),
            ("한", 2),
        ):
            with self.subTest(glyph=glyph):
                row = self.rows(glyph + "X")[0]
                self.assertEqual(row[0]["char"], glyph)
                self.assertEqual(row[width]["char"], "X")
                self.assertEqual(row[0]["continuation"], False)
                for continuation in row[1:width]:
                    self.assertEqual(continuation["char"], "")
                    self.assertTrue(continuation["continuation"])

    def test_tmux_width_policy_and_variation_selector(self) -> None:
        tokens = harness.tokenize_ansi("·✈️X")
        policy = harness.CellPolicy({"·": 2, "✈": 1, "️": 0}, False)
        row = harness.build_rows_from_tokens(tokens, 10, policy)[0]
        self.assertTrue(row[1]["continuation"])
        self.assertEqual(row[2]["char"], "✈️")
        self.assertEqual(row[3]["char"], "X")

    def test_crops_blank_partial_glyphs_and_preserve_complete_glyphs(self) -> None:
        rows = self.rows("A中B")
        for cols, expected in (((2, 3), "中"), ((3, 4), " B"), ((1, 2), "A ")):
            with self.subTest(cols=cols):
                crop = harness.crop_rows(rows, (1, 1), cols)
                self.assertEqual(harness.rows_to_text(crop, ansi=False), expected)
                self.assertEqual(len(crop[0]), cols[1] - cols[0] + 1)

    def test_match_columns_include_full_glyph_and_casefold_expansion(self) -> None:
        rows = self.rows("中éß👩‍💻END")
        for text, ignore_case, start, end in (
            ("é", False, 3, 3),
            ("e", False, 3, 3),
            ("SS", True, 4, 4),
            ("👩‍💻", False, 5, 6),
            ("END", False, 7, 9),
        ):
            with self.subTest(text=text):
                match = harness.find_matches_in_rows(
                    rows, text, ignore_case=ignore_case
                )[0]
                self.assertEqual((match["start_col"], match["end_col"]), (start, end))

    def test_snapshot_keeps_original_cells_after_width_policy_changes(self) -> None:
        rows = self.rows("中X", 10)
        saved = harness.build_screen_from_snapshot(
            {"info": {"width": "10"}, "ansi_text": "中X", "rows": rows}
        )
        self.assertEqual(saved.rows, rows)
        self.assertEqual(saved.rows[0][2]["char"], "X")

    def test_diff_reports_both_cells_of_a_wide_glyph(self) -> None:
        changes = harness.diff_changes(
            self.rows("中X", 4),
            self.rows("文X", 4),
            row_offset=1,
            col_offset=1,
            style_only=False,
        )
        self.assertEqual([change["col"] for change in changes], [1])
        changes = harness.diff_changes(
            self.rows("中X", 4),
            self.rows("  X", 4),
            row_offset=1,
            col_offset=1,
            style_only=False,
        )
        self.assertEqual([change["col"] for change in changes], [1, 2])
        self.assertTrue(changes[1]["before_continuation"])


class ObservationTests(unittest.TestCase):
    def frame(self, text: str, *, alive: bool = True) -> harness.CapturedScreen:
        tokens = harness.tokenize_ansi(text)
        rows = harness.build_rows_from_tokens(tokens, 20)
        return harness.CapturedScreen(
            {
                "pane": "%4",
                "width": "20",
                "alive": alive,
                "exit_status": 7 if not alive else None,
            },
            text,
            tokens,
            rows,
            20,
            len(rows),
        )

    def run_send(self, frames: list, *flags: str) -> tuple:
        args = harness.build_parser().parse_args(
            ["send-keys", "-t", "%4", *flags, "Enter"]
        )
        events = []

        def capture(*unused, **kwargs):
            events.append("capture")
            result = frames.pop(0) if len(frames) > 1 else frames[0]
            if isinstance(result, Exception):
                raise result
            return result

        with (
            mock.patch.object(harness, "capture_screen", side_effect=capture),
            mock.patch.object(
                harness, "run_tmux", side_effect=lambda *a, **k: events.append("send")
            ),
            mock.patch.object(harness, "emit") as emit,
        ):
            harness.cmd_send_keys(args)
        return events, emit.call_args.args

    def test_baseline_precedes_input_and_first_sample_detects_immediate_redraw(
        self,
    ) -> None:
        events, (payload, status) = self.run_send(
            [self.frame("Before"), self.frame("Saved")],
            "--wait",
            "change",
            "--poll-ms",
            "500",
        )
        self.assertEqual(events, ["capture", "send", "capture"])
        self.assertEqual(status, 0)
        self.assertTrue(payload["observation"]["changed"])
        self.assertIn("Before", payload["observation"]["baseline_text"])
        self.assertIn("Saved", payload["observation"]["text"])
        self.assertEqual(payload["observation"]["samples"], 1)

    def test_all_presence_and_absence_conditions_must_hold(self) -> None:
        _, (payload, status) = self.run_send(
            [
                self.frame("Loading"),
                self.frame("Saved Loading"),
                self.frame("Saved Ready"),
            ],
            "--wait",
            "condition",
            "--expect-text",
            "Saved",
            "--expect-text",
            "Ready",
            "--expect-absent",
            "Loading",
            "--poll-ms",
            "1",
        )
        self.assertEqual(status, 0)
        self.assertEqual(payload["observation"]["samples"], 2)
        self.assertTrue(payload["observation"]["conditions_met"])

    def test_already_satisfied_condition_is_not_claimed_as_a_change(self) -> None:
        _, (payload, status) = self.run_send(
            [self.frame("Saved")], "--wait", "condition", "--expect-text", "Saved"
        )
        self.assertEqual(status, 0)
        self.assertFalse(payload["observation"]["changed"])

    def test_timeout_contains_last_capture_and_unsatisfied_conditions(self) -> None:
        _, (payload, status) = self.run_send(
            [self.frame("Before"), self.frame("Error")],
            "--wait",
            "condition",
            "--expect-text",
            "Saved",
            "--timeout-ms",
            "5",
            "--poll-ms",
            "2",
        )
        result = payload["observation"]
        self.assertEqual(status, 2)
        self.assertFalse(payload["ok"])
        self.assertEqual(result["reason"], "timeout")
        self.assertEqual(result["missing_text"], ["Saved"])
        self.assertIn("Error", result["text"])

    def test_pane_exit_retains_final_capture_and_process_status(self) -> None:
        _, (payload, status) = self.run_send(
            [self.frame("Before"), self.frame("CRASH", alive=False)],
            "--wait",
            "condition",
            "--expect-text",
            "Saved",
        )
        self.assertEqual(status, 2)
        self.assertEqual(payload["observation"]["reason"], "pane-exited")
        self.assertIn("CRASH", payload["observation"]["text"])
        self.assertEqual(payload["exit_status"], 7)

    def test_capture_error_explicitly_labels_retained_baseline(self) -> None:
        _, (payload, status) = self.run_send(
            [self.frame("Before"), harness.HarnessError("pane gone")],
            "--wait",
            "change",
        )
        self.assertEqual(status, 2)
        self.assertTrue(payload["observation"]["last_capture_is_baseline"])
        self.assertEqual(payload["observation"]["detail"], "pane gone")

    def test_invalid_conditions_are_rejected_before_input(self) -> None:
        for flags in (
            ("--wait", "condition"),
            ("--expect-text", "Saved"),
            ("--wait", "condition", "--expect-text", ""),
            ("--wait", "stable", "--lines", "25"),
        ):
            with self.subTest(flags=flags):
                args = harness.build_parser().parse_args(
                    ["send-keys", "-t", "%4", *flags, "Enter"]
                )
                with (
                    mock.patch.object(harness, "run_tmux") as send,
                    mock.patch.object(
                        harness, "capture_screen", return_value=self.frame("Before")
                    ),
                    self.assertRaises(harness.HarnessError),
                ):
                    harness.cmd_send_keys(args)
                send.assert_not_called()

    def test_plain_comparison_ignores_style_only_redraw(self) -> None:
        frames = [self.frame("\x1b[31mReady"), self.frame("\x1b[34mReady")]
        _, (payload, status) = self.run_send(
            frames, "--wait", "stable", "--stable-ms", "0", "--plain"
        )
        self.assertEqual(status, 0)
        self.assertFalse(payload["observation"]["changed"])
        frames = [self.frame("\x1b[31mReady"), self.frame("\x1b[34mReady")]
        _, (payload, status) = self.run_send(frames, "--wait", "change")
        self.assertEqual(status, 0)
        self.assertTrue(payload["observation"]["changed"])

    def test_require_change_rejects_an_already_satisfied_condition(self) -> None:
        _, (payload, status) = self.run_send(
            [self.frame("Saved")],
            "--wait",
            "condition",
            "--expect-text",
            "Saved",
            "--require-change",
            "--timeout-ms",
            "5",
            "--poll-ms",
            "2",
        )
        self.assertEqual(status, 2)
        self.assertTrue(payload["observation"]["conditions_met"])
        self.assertFalse(payload["observation"]["changed"])

    def test_mouse_variants_capture_baseline_before_first_event(self) -> None:
        for variant, flags in (
            ("click", ["--row", "1", "--col", "1"]),
            ("scroll", ["--row", "1", "--col", "1", "--direction", "down"]),
            (
                "drag",
                [
                    "--start-row",
                    "1",
                    "--start-col",
                    "1",
                    "--end-row",
                    "1",
                    "--end-col",
                    "3",
                ],
            ),
        ):
            with self.subTest(variant=variant):
                args = harness.build_parser().parse_args(
                    [
                        "mouse",
                        variant,
                        "-t",
                        "%4",
                        *flags,
                        "--wait",
                        "condition",
                        "--expect-text",
                        "Saved",
                    ]
                )
                events = []

                def capture(*unused, **kwargs):
                    events.append("capture")
                    return self.frame("Saved" if "send" in events else "Before")

                with (
                    mock.patch.object(harness, "capture_screen", side_effect=capture),
                    mock.patch.object(
                        harness,
                        "send_literal",
                        side_effect=lambda *a: events.append("send"),
                    ),
                    mock.patch.object(harness, "emit") as emit,
                ):
                    args.func(args)
                self.assertEqual(events[:3], ["capture", "capture", "send"])
                self.assertEqual(events[-1], "capture")
                self.assertEqual(emit.call_args.args[1], 0)

    def test_invalid_polling_parameters_are_rejected(self) -> None:
        for flags in (
            ("--poll-ms", "0"),
            ("--timeout-ms", "-1"),
            ("--stable-ms", "-1"),
        ):
            with (
                self.subTest(flags=flags),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit),
            ):
                harness.build_parser().parse_args(
                    ["send-keys", "-t", "%4", "--wait", "stable", *flags, "Enter"]
                )


FIXTURE = """
import os, sys, termios
settings = termios.tcgetattr(0)
settings[3] &= ~termios.ECHO
termios.tcsetattr(0, termios.TCSANOW, settings)
for i in range(35):
    print('HISTORY-%02d' % i)
print('WRAP-' + 'w' * 95)
print('\\x1b[31mFIXTURE   \\x1b[0m')
print('ENV=' + os.environ.get('HARNESS_FIXTURE', 'missing'))
print('CWD=' + os.getcwd())
print('READY', flush=True)
for line in sys.stdin:
    print('INPUT=' + repr(line), flush=True)
"""


@unittest.skipUnless(shutil.which("tmux"), "tmux is required for integration tests")
class TmuxIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.socket = "harness-cli-test-" + uuid.uuid4().hex[:12]
        self.addCleanup(self.native, "kill-server", check=False)
        # Bootstrap only our unique server with an empty config; never read or
        # mutate the user's interactive server/config during fixture tests.
        self.native("-f", "/dev/null", "new-session", "-d", "-s", "bootstrap")
        self.info = self.call(
            "new-session",
            "-s",
            "demo",
            "-c",
            self.directory.name,
            "-x",
            "60",
            "-y",
            "16",
            "-e",
            "HARNESS_FIXTURE=present",
            "--",
            sys.executable,
            "-u",
            "-c",
            FIXTURE,
        )
        self.pane = self.info["pane"]
        self.stable(self.pane)

    def native(self, *argv: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["tmux", "-L", self.socket, *argv], capture_output=True, check=check
        )

    def invoke(self, *argv: str, check: bool = True) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-B", str(HARNESS), "-L", self.socket, *argv],
            capture_output=True,
            check=check,
        )

    def call(self, *argv: str) -> dict:
        result = self.invoke(*argv)
        return json.loads(result.stdout)

    def stable(self, target: str) -> dict:
        return self.call(
            "wait",
            "-t",
            target,
            "--stable-ms",
            "100",
            "--poll-ms",
            "20",
            "--timeout-ms",
            "3000",
            "--plain",
        )

    def qualified(self, pane: str) -> str:
        return (
            self.native(
                "display-message",
                "-p",
                "-t",
                pane,
                "#{session_name}:#{window_index}.#{pane_index}",
            )
            .stdout.decode()
            .strip()
        )

    def snapshot(self, target: str, name: str) -> dict:
        result = self.call("snapshot", "-t", target, "--name", name)
        self.addCleanup(Path(result["snapshot_path"]).unlink, missing_ok=True)
        return result

    def test_raw_and_json_capture_match_tmux(self) -> None:
        for flags in (
            [],
            ["-e"],
            ["-N"],
            ["-J"],
            ["-e", "-J"],
            ["-S", "-5", "-E", "2"],
            ["-S", "-", "-E", "-"],
            ["-S", "0", "-E", "2"],
        ):
            with self.subTest(flags=flags):
                expected = self.native(
                    "capture-pane", "-p", "-t", self.pane, *flags
                ).stdout
                self.assertEqual(
                    self.invoke("capture-pane", "-p", "-t", self.pane, *flags).stdout,
                    expected,
                )
                self.assertEqual(
                    self.call("capture-pane", "-t", self.pane, *flags)["text"],
                    expected.decode(),
                )

    def test_execution_environment_and_ordered_input(self) -> None:
        initial = self.call("capture-pane", "-t", self.pane, "-J")["text"]
        self.assertIn("ENV=present", initial)
        self.assertIn("CWD=" + str(Path(self.directory.name).resolve()), initial)
        self.call("send-keys", "-t", self.pane, "first", "Enter", "second", "Enter")
        self.call("send-keys", "-t", self.pane, "-l", "Enter")
        self.call("send-keys", "-t", self.pane, "Enter")
        self.call("send-keys", "-t", self.pane, "-l", "-N", "3", "x")
        self.call("send-keys", "-t", self.pane, "Enter")
        self.stable(self.pane)
        text = self.call("capture-pane", "-t", self.pane, "-S", "-")["text"]
        self.assertLess(text.index("INPUT='first"), text.index("INPUT='second"))
        self.assertIn("INPUT='Enter", text)
        self.assertIn("INPUT='xxx", text)

    def test_active_and_qualified_targets_and_pane_dimensions(self) -> None:
        other = (
            self.native(
                "split-window",
                "-h",
                "-t",
                self.pane,
                "-P",
                "-F",
                "#{pane_id}",
                sys.executable,
                "-u",
                "-c",
                FIXTURE,
            )
            .stdout.decode()
            .strip()
        )
        self.stable(other)
        active = self.call("info", "-t", "demo")
        self.assertEqual(active["pane"], other)
        expected_width = (
            self.native("display-message", "-p", "-t", other, "#{pane_width}")
            .stdout.decode()
            .strip()
        )
        self.assertEqual(active["width"], expected_width)
        self.assertLess(int(active["width"]), 60)
        original = self.call("info", "-t", self.qualified(self.pane))
        self.assertEqual(original["pane"], self.pane)
        self.call(
            "send-keys", "-t", self.qualified(self.pane), "original-only", "Enter"
        )
        self.stable(self.pane)
        self.assertIn(
            "original-only", self.call("capture-pane", "-t", self.pane)["text"]
        )
        self.assertNotIn(
            "original-only", self.call("capture-pane", "-t", other)["text"]
        )
        before = self.snapshot(self.qualified(self.pane), "before")
        same = self.call("diff", "-t", self.pane, "--before", "before")
        self.assertEqual(same["changed_cell_count"], 0)
        second = self.snapshot(other, "before")
        self.assertNotEqual(before["snapshot_path"], second["snapshot_path"])

    def test_wait_stays_bound_when_active_pane_changes(self) -> None:
        other = (
            self.native("split-window", "-h", "-t", self.pane, "-P", "-F", "#{pane_id}")
            .stdout.decode()
            .strip()
        )
        self.native("select-pane", "-t", self.pane)
        with subprocess.Popen(
            [
                sys.executable,
                "-B",
                str(HARNESS),
                "-L",
                self.socket,
                "wait",
                "-t",
                "demo",
                "--stable-ms",
                "500",
                "--poll-ms",
                "20",
                "--timeout-ms",
                "3000",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ) as process:
            time.sleep(0.2)
            self.native("select-pane", "-t", other)
            stdout, stderr = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(json.loads(stdout)["pane"], self.pane)

    def test_style_inspection_crop_and_snapshot_diff(self) -> None:
        match = self.call("find-text", "-t", self.pane, "--text", "FIXTURE")["matches"][
            0
        ]
        row = str(match["row"])
        cell = self.call("cell", "-t", self.pane, "--row", row, "--col", "1")
        self.assertEqual(cell["char"], "F")
        self.assertEqual(cell["resolved_style"]["resolved_fg"], "red")
        crop = self.call(
            "capture-pane",
            "-t",
            self.pane,
            "--lines",
            row,
            "--cols",
            "1:7",
            "--number-lines",
            "--ruler",
            "--tokens",
        )
        self.assertEqual(crop["text"], "FIXTURE")
        self.assertIn(row + ":", crop["display_text"])
        self.assertTrue(crop["tokens"])
        self.snapshot(self.pane, "before")
        self.call("send-keys", "-t", self.pane, "updated", "Enter")
        self.stable(self.pane)
        diff = self.call("diff", "-t", self.qualified(self.pane), "--before", "before")
        self.assertGreater(diff["text_change_count"], 0)

    def test_one_dimension_resize_and_window_targets(self) -> None:
        window = self.info["window"]
        result = self.call("resize-window", "-t", window, "-x", "80")
        self.assertEqual(result["width"], "80")
        self.assertEqual(result["height"], "16")
        result = self.call("resizew", "-t", "demo", "-y", "20")
        self.assertEqual(result["width"], "80")
        self.assertEqual(result["height"], "20")

    def test_qualified_window_target_does_not_resize_another_window(self) -> None:
        window, pane = (
            self.native(
                "new-window",
                "-d",
                "-t",
                "demo",
                "-P",
                "-F",
                "#{window_id} #{pane_id}",
                sys.executable,
                "-u",
                "-c",
                FIXTURE,
            )
            .stdout.decode()
            .strip()
            .split()
        )
        self.stable(pane)
        qualified_window = (
            self.native(
                "display-message", "-p", "-t", pane, "#{session_name}:#{window_index}"
            )
            .stdout.decode()
            .strip()
        )
        result = self.call("resize-window", "-t", qualified_window, "-x", "90")
        self.assertEqual(result["window"], window)
        self.assertEqual(result["width"], "90")
        self.assertEqual(self.call("info", "-t", self.pane)["width"], "60")

    def test_immediate_exit_is_retained_and_cleanup_is_idempotent(self) -> None:
        result = self.call(
            "new-session", "-s", "exited", "--", "printf 'POSTMORTEM\\n'; exit 7"
        )
        self.stable(result["pane"])
        dead = self.call("info", "-t", result["pane"])
        self.assertFalse(dead["alive"])
        self.assertEqual(dead["exit_status"], 7)
        self.assertIn(
            "POSTMORTEM",
            self.call("capture-pane", "-t", result["pane"], "-S", "-")["text"],
        )
        self.assertTrue(
            self.call("kill-session", "-t", result["session_id"])["stopped"]
        )
        self.assertFalse(
            self.call("kill-session", "-t", "exited", "--ignore-missing")["stopped"]
        )

    def test_new_server_instance_cannot_reuse_snapshot(self) -> None:
        before = self.snapshot(self.pane, "before")
        self.native("kill-server")
        self.native("-f", "/dev/null", "new-session", "-d", "-s", "bootstrap")
        result = self.call(
            "new-session", "-s", "demo", "--", sys.executable, "-u", "-c", FIXTURE
        )
        self.stable(result["pane"])
        after = self.snapshot(result["pane"], "before")
        self.assertNotEqual(before["snapshot_path"], after["snapshot_path"])

    def test_default_shell_startup_and_direct_argv(self) -> None:
        shell = self.call("new-session", "-s", "shell")
        self.assertTrue(shell["alive"])
        command = "import sys; print(repr(sys.argv[1:]), flush=True)"
        direct = self.call(
            "new-session",
            "-s",
            "argv",
            "--",
            sys.executable,
            "-c",
            command,
            "argument with spaces",
            "$literal",
            "*",
        )
        self.stable(direct["pane"])
        captured = self.call("capture-pane", "-t", direct["pane"], "-J", "-S", "-")[
            "text"
        ]
        self.assertIn("['argument with spaces', '$literal', '*']", captured)

    def test_raw_missing_target_uses_stderr_and_nonzero_status(self) -> None:
        result = self.invoke(
            "capture-pane", "-t", "nonexistent-session", "-p", check=False
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"")
        self.assertTrue(result.stderr)

    def test_style_only_diff_detects_background_change(self) -> None:
        code = "import sys; print('\\x1b[2J\\x1b[H\\x1b[41mSTYLE\\x1b[0m', flush=True); sys.stdin.readline(); print('\\x1b[H\\x1b[44mSTYLE\\x1b[0m', flush=True); sys.stdin.readline()"
        styled = self.call(
            "new-session", "-s", "styled", "--", sys.executable, "-u", "-c", code
        )
        self.stable(styled["pane"])
        self.snapshot(styled["pane"], "before")
        self.call("send-keys", "-t", styled["pane"], "Enter")
        self.stable(styled["pane"])
        diff = self.call(
            "diff", "-t", styled["pane"], "--before", "before", "--style-only"
        )
        self.assertGreater(diff["style_change_count"], 0)
        self.assertEqual(diff["text_change_count"], 0)

    def start_fixture(self, name: str, code: str, *, width: int = 60) -> dict:
        return self.call(
            "new-session",
            "-s",
            name,
            "-x",
            str(width),
            "-y",
            "16",
            "--",
            sys.executable,
            "-u",
            "-c",
            code,
        )

    def test_unicode_coordinates_agree_with_tmux_cursor(self) -> None:
        for index, glyph in enumerate(("中", "é", "👩‍💻", "🇺🇸", "✈️", "👍🏽", "한")):
            with self.subTest(glyph=glyph):
                code = (
                    "import sys; sys.stdout.write('\\x1b[2J\\x1b[H\\x1b[31m' + "
                    + repr(glyph)
                    + " + '\\x1b[0mEND'); sys.stdout.flush(); sys.stdin.readline()"
                )
                pane = self.start_fixture("unicode" + str(index), code)["pane"]
                self.stable(pane)
                cursor = int(
                    self.native(
                        "display-message", "-p", "-t", pane, "#{cursor_x}"
                    ).stdout
                )
                match = self.call("find-text", "-t", pane, "--text", "END")["matches"][
                    0
                ]
                self.assertEqual(match["start_col"], cursor - 2)
                self.assertEqual(match["end_col"], cursor)
                width = cursor - 3
                cell = self.call("cell", "-t", pane, "--row", "1", "--col", "1")
                self.assertEqual(cell["glyph"], glyph)
                self.assertEqual(cell["glyph_width"], width)
                self.assertEqual(cell["resolved_style"]["resolved_fg"], "red")
                if width == 2:
                    tail = self.call("cell", "-t", pane, "--row", "1", "--col", "2")
                    self.assertTrue(tail["continuation"])
                    self.assertEqual(tail["glyph"], glyph)
                    self.assertEqual(tail["glyph_col"], 1)
                    crop = self.call(
                        "capture-pane", "-t", pane, "--lines", "1", "--cols", "2:3"
                    )
                    self.assertEqual(crop["text"], " E")
                click = self.call(
                    "mouse", "click", "-t", pane, "--text", "END", "--anchor", "start"
                )
                self.assertEqual(click["col"], cursor - 2)

    def test_server_width_overrides_and_variation_selector_policy(self) -> None:
        self.native("set-option", "-s", "codepoint-widths", "U+00B7=2")
        self.native("set-option", "-g", "variation-selector-always-wide", "off")
        code = "import sys; sys.stdout.write('·✈️END'); sys.stdout.flush(); sys.stdin.readline()"
        pane = self.start_fixture("width-policy", code)["pane"]
        self.stable(pane)
        match = self.call("find-text", "-t", pane, "--text", "END")["matches"][0]
        cursor = int(
            self.native("display-message", "-p", "-t", pane, "#{cursor_x}").stdout
        )
        self.assertEqual(match["start_col"], cursor - 2)
        self.assertEqual(match["start_col"], 4)
        self.snapshot(pane, "unicode-before")
        self.assertEqual(
            self.call("diff", "-t", pane, "--before", "unicode-before")[
                "changed_cell_count"
            ],
            0,
        )

    def test_wide_glyph_wrap_preserves_physical_rows(self) -> None:
        pane = self.start_fixture(
            "wide-wrap",
            "import sys; sys.stdout.write('1234567中Z'); sys.stdout.flush(); sys.stdin.readline()",
            width=8,
        )["pane"]
        self.stable(pane)
        self.assertEqual(
            self.call("cell", "-t", pane, "--row", "2", "--col", "3")["char"], "Z"
        )
        match = self.call("find-text", "-t", pane, "--text", "中Z")["matches"][0]
        self.assertEqual(
            (match["row"], match["start_col"], match["end_col"]), (2, 1, 3)
        )

    def test_observation_ignores_animation_outside_selected_region(self) -> None:
        code = """
import select, sys, termios
settings = termios.tcgetattr(0)
settings[3] &= ~termios.ECHO
termios.tcsetattr(0, termios.TCSANOW, settings)
saved, tick = False, 0
sys.stdout.write('\\x1b[2J')
while True:
    if select.select([sys.stdin], [], [], .01)[0]:
        sys.stdin.readline()
        saved = True
    tick += 1
    sys.stdout.write('\\x1b[1;1H' + ('Saved Ready' if saved else 'Idle') + '\\x1b[K\\x1b[2;1HTICK=' + str(tick))
    sys.stdout.flush()
"""
        pane = self.start_fixture("animated", code)["pane"]
        self.call("wait", "-t", pane, "--mode", "condition", "--expect-text", "Idle")
        result = self.call(
            "send-keys",
            "-t",
            pane,
            "--wait",
            "stable",
            "--expect-text",
            "Saved",
            "--expect-absent",
            "Idle",
            "--lines",
            "1",
            "--cols",
            "1:11",
            "--stable-ms",
            "100",
            "--poll-ms",
            "20",
            "--timeout-ms",
            "1500",
            "Enter",
        )
        self.assertTrue(result["observation"]["changed"])
        self.assertEqual(result["observation"]["plain_text"], "Saved Ready")
        self.assertGreaterEqual(result["observation"]["stable_for_ms"], 100)
        failed = self.invoke(
            "wait",
            "-t",
            pane,
            "--stable-ms",
            "300",
            "--timeout-ms",
            "150",
            "--poll-ms",
            "20",
            check=False,
        )
        self.assertEqual(failed.returncode, 2)
        failure = json.loads(failed.stdout)
        self.assertEqual(failure["reason"], "timeout")
        self.assertIn("TICK=", failure["text"])
        self.assertGreater(failure["change_count"], 0)

    def test_action_condition_does_not_accept_quiet_wrong_screen(self) -> None:
        failed = self.invoke(
            "send-keys",
            "-t",
            self.pane,
            "--wait",
            "stable",
            "--expect-text",
            "NEVER-APPEARS",
            "--timeout-ms",
            "180",
            "--stable-ms",
            "30",
            "--poll-ms",
            "10",
            "wrong",
            "Enter",
            check=False,
        )
        self.assertEqual(failed.returncode, 2)
        result = json.loads(failed.stdout)
        self.assertEqual(result["observation"]["missing_text"], ["NEVER-APPEARS"])
        self.assertIn("INPUT='wrong", result["observation"]["text"])

    def test_condition_returns_final_output_from_exiting_process(self) -> None:
        pane = self.start_fixture(
            "exit-condition",
            "import sys; print('READY', flush=True); sys.stdin.readline(); print('DONE', flush=True); sys.exit(7)",
        )["pane"]
        self.call("wait", "-t", pane, "--mode", "condition", "--expect-text", "READY")
        result = self.call(
            "send-keys",
            "-t",
            pane,
            "--wait",
            "condition",
            "--expect-text",
            "DONE",
            "Enter",
        )
        self.assertTrue(result["observation"]["conditions_met"])
        self.assertIn("DONE", result["observation"]["text"])
        self.stable(pane)
        self.assertEqual(self.call("info", "-t", pane)["exit_status"], 7)

    def test_pane_exit_fails_unmet_action_condition_with_final_output(self) -> None:
        pane = self.start_fixture(
            "exit-unmet",
            "import sys; print('READY', flush=True); sys.stdin.readline(); print('CRASH', flush=True); sys.exit(7)",
        )["pane"]
        self.call("wait", "-t", pane, "--mode", "condition", "--expect-text", "READY")
        failed = self.invoke(
            "send-keys",
            "-t",
            pane,
            "--wait",
            "condition",
            "--expect-text",
            "Saved",
            "--poll-ms",
            "20",
            "Enter",
            check=False,
        )
        self.assertEqual(failed.returncode, 2)
        result = json.loads(failed.stdout)
        self.assertEqual(result["observation"]["reason"], "pane-exited")
        self.assertIn("CRASH", result["observation"]["text"])
        self.assertEqual(result["exit_status"], 7)

    def test_mouse_action_observes_condition(self) -> None:
        code = """
import os, sys, tty
tty.setraw(0)
sys.stdout.write('\\x1b[2J\\x1b[H\\x1b[?1000h\\x1b[?1006hBUTTON')
sys.stdout.flush()
data = b''
while not data.endswith(b'm'):
    data += os.read(0, 1)
sys.stdout.write('\\x1b[2;1HClicked')
sys.stdout.flush()
os.read(0, 1)
"""
        pane = self.start_fixture("mouse-observe", code)["pane"]
        self.call("wait", "-t", pane, "--mode", "condition", "--expect-text", "BUTTON")
        result = self.call(
            "mouse",
            "click",
            "-t",
            pane,
            "--text",
            "BUTTON",
            "--wait",
            "condition",
            "--expect-text",
            "Clicked",
        )
        self.assertEqual(result["mouse_action"], "click")
        self.assertTrue(result["observation"]["changed"])


def screenshot_args(output: Path, **overrides: object) -> argparse.Namespace:
    values = {
        "target": "demo",
        "output": str(output),
        "freeze_config": "terminal",
        "rasterizer": "auto",
        "scale": None,
        "start_line": None,
        "end_line": None,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class ScreenshotTests(unittest.TestCase):
    def test_parser_exposes_screenshot_command(self) -> None:
        args = harness.build_parser().parse_args(
            ["screenshot", "-t", "demo", "--output", "pane.png"]
        )

        self.assertIs(args.func, harness.cmd_screenshot)
        self.assertEqual(args.freeze_config, "terminal")
        self.assertEqual(args.rasterizer, "auto")

    def test_parser_accepts_rsvg_pdf_rasterizer(self) -> None:
        args = harness.build_parser().parse_args(
            [
                "screenshot",
                "-t",
                "demo",
                "--output",
                "pane.png",
                "--rasterizer",
                "rsvg-pdf",
            ]
        )

        self.assertEqual(args.rasterizer, "rsvg-pdf")

    def test_missing_freeze_explains_requirement_and_installation(self) -> None:
        with (
            mock.patch.object(harness.shutil, "which", return_value=None),
            self.assertRaisesRegex(
                harness.HarnessError,
                r"freeze is required for raster screenshots; the user must install freeze",
            ),
        ):
            harness.cmd_screenshot(screenshot_args(Path("pane.png")))

    def test_screenshot_captures_ansi_and_runs_freeze(self) -> None:
        ansi_text = "\x1b[31mred\x1b[0m   "
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "screenshots" / "pane.png"
            resolved_output = output.resolve()

            def run_freeze(
                command: list[str], **kwargs: object
            ) -> subprocess.CompletedProcess[str]:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"\x89PNG\r\n\x1a\n")
                return subprocess.CompletedProcess(
                    command, 0, stdout="WROTE pane.png\n", stderr=""
                )

            with (
                mock.patch.object(
                    harness.shutil, "which", return_value="/opt/bin/freeze"
                ),
                mock.patch.object(
                    harness,
                    "pane_info",
                    return_value={"ok": True, "session": "demo"},
                ),
                mock.patch.object(
                    harness, "capture_text", return_value=ansi_text
                ) as capture,
                mock.patch.object(
                    harness.subprocess, "run", side_effect=run_freeze
                ) as run,
                mock.patch.object(harness, "emit") as emit,
            ):
                harness.cmd_screenshot(
                    screenshot_args(output, rasterizer="chromium", scale=2.0)
                )

            capture.assert_called_once_with(
                "demo",
                ansi=True,
                start_line=None,
                end_line=None,
                join_wrapped=False,
                preserve_trailing_spaces=True,
            )
            command = run.call_args.args[0]
            self.assertEqual(
                command,
                [
                    str(FREEZE_EXEC),
                    "-c",
                    "terminal",
                    "--rasterizer",
                    "chromium",
                    "--scale",
                    "2.0",
                    "-o",
                    str(resolved_output),
                ],
            )
            self.assertEqual(
                run.call_args.kwargs["env"]["FREEZE_BIN"], "/opt/bin/freeze"
            )
            self.assertEqual(run.call_args.kwargs["input"], ansi_text)
            payload = emit.call_args.args[0]
            self.assertEqual(payload["action"], "screenshot")
            self.assertEqual(payload["screenshot_path"], str(resolved_output))
            self.assertEqual(payload["rasterizer"], "chromium")
            self.assertEqual(payload["scale"], 2.0)

    def test_freeze_failure_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "pane.png"
            failed = subprocess.CompletedProcess(
                ["freeze"], 1, stdout="", stderr="renderer unavailable\n"
            )

            with (
                mock.patch.object(
                    harness.shutil, "which", return_value="/opt/bin/freeze"
                ),
                mock.patch.object(harness, "pane_info", return_value={"ok": True}),
                mock.patch.object(harness, "capture_text", return_value="pane"),
                mock.patch.object(harness.subprocess, "run", return_value=failed),
                self.assertRaisesRegex(
                    harness.HarnessError,
                    "freeze failed to render raster screenshot: renderer unavailable",
                ),
            ):
                harness.cmd_screenshot(screenshot_args(output))


class FreezeExecTests(unittest.TestCase):
    def test_helper_forces_ansi_language_and_forwards_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_freeze = Path(temp_dir) / "freeze"
            fake_freeze.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$@\"\n",
                encoding="utf-8",
            )
            fake_freeze.chmod(0o755)
            environment = os.environ.copy()
            environment.pop("FREEZE_BIN", None)
            environment["PATH"] = f"{temp_dir}{os.pathsep}{environment['PATH']}"

            completed = subprocess.run(
                [str(FREEZE_EXEC), "-c", "terminal", "-o", "pane.png"],
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(
            completed.stdout.splitlines(),
            ["--language", "ansi", "-c", "terminal", "-o", "pane.png"],
        )

    def test_helper_reports_invalid_explicit_executable(self) -> None:
        environment = os.environ.copy()
        environment["FREEZE_BIN"] = "/missing/freeze"

        completed = subprocess.run(
            [str(FREEZE_EXEC)],
            capture_output=True,
            text=True,
            check=False,
            env=environment,
        )

        self.assertEqual(completed.returncode, 126)
        self.assertIn("freeze executable is not executable", completed.stderr)


if __name__ == "__main__":
    unittest.main()
