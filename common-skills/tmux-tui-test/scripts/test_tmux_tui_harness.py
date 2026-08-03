import argparse
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tmux_tui_harness as harness

FREEZE_EXEC = Path(__file__).with_name("freeze_exec.sh")


def screenshot_args(output: Path, **overrides: object) -> argparse.Namespace:
    values = {
        "session": "demo",
        "output": str(output),
        "freeze_config": "terminal",
        "rasterizer": "auto",
        "scale": None,
        "history": None,
        "full_history": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


class ScreenshotTests(unittest.TestCase):
    def test_parser_exposes_screenshot_command(self) -> None:
        args = harness.build_parser().parse_args(
            ["screenshot", "demo", "--output", "pane.png"]
        )

        self.assertIs(args.func, harness.cmd_screenshot)
        self.assertEqual(args.freeze_config, "terminal")
        self.assertEqual(args.rasterizer, "auto")

    def test_parser_accepts_rsvg_pdf_rasterizer(self) -> None:
        args = harness.build_parser().parse_args(
            [
                "screenshot",
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
                    "session_info",
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
                history=None,
                full_history=False,
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
                mock.patch.object(harness, "session_info", return_value={"ok": True}),
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
