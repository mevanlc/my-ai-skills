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
