"""Unit tests for Tools/integration/run_smoke.py.

Stdlib only: these run in CI on ubuntu-latest without Unreal or extra packages.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from Tools.integration import run_smoke  # noqa: E402  (path setup)


def _step(name: str, log_dir: Path, text: str, *, status: str = "pass", returncode: int | None = 0) -> run_smoke.Step:
    log_path = log_dir / f"{name}.log"
    log_path.write_text(text, encoding="utf-8")
    return run_smoke.Step(name=name, command=["demo"], status=status,
                          returncode=returncode, log=str(log_path))


def _pid_alive(pid: int) -> bool:
    """Cross-platform liveness check for the process-tree fixture."""
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_until_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_alive(pid)


def _force_kill(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


class DuelSelftestParsingTests(unittest.TestCase):
    def test_current_summary_passes(self) -> None:
        summary = ("Duel self-test: 24 iterations, 12 player wins, 12 opponent wins, 0 stalls, "
                   "average turns 11.7, invariant failures 0, gate deck failures 0, deck audit 6/36, "
                   "puzzle audit 100/100, elapsed 1.5s, RESULT PASS")
        self.assertEqual(run_smoke._duel_selftest_failure_reason(summary), "")

    def test_result_fail(self) -> None:
        summary = "Duel self-test: 24 iterations, 12 player wins, 12 opponent wins, 0 stalls, RESULT FAIL"
        self.assertEqual(run_smoke._duel_selftest_failure_reason(summary), "RESULT FAIL")

    def test_stalls_fail(self) -> None:
        summary = "Duel self-test: 24 iterations, 1 player wins, 23 opponent wins, 2 stalls, RESULT PASS"
        self.assertEqual(run_smoke._duel_selftest_failure_reason(summary), "stalls 2")

    def test_unparsable_summary_fails(self) -> None:
        self.assertEqual(run_smoke._duel_selftest_failure_reason("Duel self-test: card database missing."),
                         "missing stalls field")
        self.assertEqual(run_smoke._duel_selftest_failure_reason("Duel self-test: x stalls"),
                         "unparsable stalls field")

    def test_log_inspection_keeps_nonzero_returncode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("duel-selftest", Path(tmp), "Duel self-test: 24 iterations, 12 player wins, "
                         "12 opponent wins, 0 stalls, RESULT PASS", status="fail", returncode=1)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_missing_summary_fails_a_passing_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("duel-selftest", Path(tmp), "editor started and exited cleanly")
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("missing", step.note)


class NamedSelftestParsingTests(unittest.TestCase):
    def test_economy_summary_passes(self) -> None:
        text = ("DAEconomySelfTest: scheduled; waiting for the card database.\n"
                "DAEconomySelfTest: 119 passed, 0 failed.\n"
                "DAEconomySelfTest: finished; requesting exit.\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("economy-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "pass")
            self.assertIn("119 passed, 0 failed", step.note)

    def test_per_check_failure_beats_early_pass_line(self) -> None:
        # Story logs emit "StorySelfTest: PASS <check>" per check; the final
        # "PASS in" summary is the gate and must not be masked by an early pass.
        text = ("StorySelfTest: PASS E01 completed\n"
                "StorySelfTest: FAIL command guard (4096)\n"
                "StorySelfTest: FAIL in 0.123s\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("story-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("FAIL", step.note)

    def test_truncated_story_log_with_failure_line_fails(self) -> None:
        text = "StorySelfTest: FAIL command guard (4096)\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("story-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_profile_fail_line_not_overridden_by_summary(self) -> None:
        text = ("[2026.10.31-15.47.58:933][107]LogDuelAcademyIsland: [FAIL] save round trip\n"
                "DAProfileSelfTest PASSED.\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("profile-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_failed_summary_downgrades_passing_step(self) -> None:
        text = "PuzzleSelfTest: 101 passed, 1 failed. FAILURES PRESENT\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("puzzle-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_failed_process_is_not_upgraded_by_pass_summary(self) -> None:
        text = "PuzzleSelfTest: 102 passed, 0 failed. ALL PASS\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("puzzle-selftest", Path(tmp), text, status="fail", returncode=1)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertNotIn("102 passed", step.note)

    def test_missing_summary_fails_a_passing_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("exam-selftest", Path(tmp), "nothing useful here")
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("ExamSelfTest:", step.note)

    def test_zero_check_summary_fails(self) -> None:
        text = "PuzzleSelfTest: 0 passed, 0 failed. ALL PASS\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("puzzle-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("0 checks", step.note)

    def test_timed_out_step_is_not_upgraded_by_pass_summary(self) -> None:
        text = "ExamSelfTest: 12 passed, 0 failed. ALL PASS\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("exam-selftest", Path(tmp), text, status="fail", returncode=None)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")


class A07AndAutomationParsingTests(unittest.TestCase):
    def test_a07_both_suites_pass(self) -> None:
        text = ("PuzzleSelfTest: 100 passed, 0 failed. ALL PASS\n"
                "ExamSelfTest: 12 passed, 0 failed. ALL PASS\n"
                "A07SelfTest: BOTH SUITES PASS\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("a07-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "pass")
            self.assertIn("BOTH SUITES PASS", step.note)

    def test_a07_missing_second_suite_fails(self) -> None:
        text = ("PuzzleSelfTest: 100 passed, 0 failed. ALL PASS\n"
                "A07SelfTest: BOTH SUITES PASS\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("a07-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_a07_failures_present_fails(self) -> None:
        text = ("PuzzleSelfTest: 100 passed, 0 failed. ALL PASS\n"
                "ExamSelfTest: 11 passed, 1 failed. FAILURES PRESENT\n"
                "A07SelfTest: FAILURES PRESENT\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("a07-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_a07_failed_suite_count_beats_both_suites_marker(self) -> None:
        text = ("PuzzleSelfTest: 100 passed, 1 failed. ALL PASS\n"
                "ExamSelfTest: 12 passed, 0 failed. ALL PASS\n"
                "A07SelfTest: BOTH SUITES PASS\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("a07-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_a07_malformed_suite_summary_fails(self) -> None:
        text = ("PuzzleSelfTest: 100 passed\n"
                "ExamSelfTest: 12 passed, 0 failed. ALL PASS\n"
                "A07SelfTest: BOTH SUITES PASS\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("a07-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_a07_zero_check_suites_fail(self) -> None:
        text = ("PuzzleSelfTest: 0 passed, 0 failed. ALL PASS\n"
                "ExamSelfTest: 0 passed, 0 failed. ALL PASS\n"
                "A07SelfTest: BOTH SUITES PASS\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("a07-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("0 checks", step.note)

    def test_a07_one_empty_suite_fails_even_if_other_ran(self) -> None:
        text = ("PuzzleSelfTest: 0 passed, 0 failed. ALL PASS\n"
                "ExamSelfTest: 12 passed, 0 failed. ALL PASS\n"
                "A07SelfTest: BOTH SUITES PASS\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("a07-selftest", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_a07_pass_summary_does_not_upgrade_failed_process(self) -> None:
        text = ("PuzzleSelfTest: 100 passed, 0 failed. ALL PASS\n"
                "ExamSelfTest: 12 passed, 0 failed. ALL PASS\n"
                "A07SelfTest: BOTH SUITES PASS\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("a07-selftest", Path(tmp), text, status="fail", returncode=1)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_automation_exit_code_text_does_not_override_failure(self) -> None:
        text = "**** TEST COMPLETE. EXIT CODE: 0 ****\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text, status="fail", returncode=1)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_automation_no_tests_is_skip(self) -> None:
        # This is the real UE shape: an empty filter sets GIsCriticalError and
        # exits non-zero, but still logs TEST COMPLETE.
        text = ("LogAutomationCommandLine: Error: No automation tests matched 'DuelAcademy.IntegrationSmoke'\n"
                "LogAutomationCommandLine: Display: **** TEST COMPLETE. EXIT CODE: -1 ****\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text, status="fail", returncode=255)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "skip")
            self.assertIn("no automation tests", step.note)

    def test_automation_no_tests_without_completion_fails(self) -> None:
        text = "No automation tests matched 'DuelAcademy.IntegrationSmoke'\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("TEST COMPLETE", step.note)

    def test_automation_no_tests_does_not_mask_nonzero_exit(self) -> None:
        text = "No automation tests matched 'DuelAcademy.IntegrationSmoke'\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text, status="fail", returncode=7)
            step.note = "exit code 7"
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertEqual(step.note, "exit code 7")

    def test_automation_no_tests_does_not_mask_timeout(self) -> None:
        text = "No tests found\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text, status="fail", returncode=None)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_automation_no_tests_and_completion_do_not_mask_timeout(self) -> None:
        text = ("No automation tests matched 'DuelAcademy.IntegrationSmoke'\n"
                "**** TEST COMPLETE. EXIT CODE: -1 ****\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text, status="fail", returncode=None)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_automation_no_tests_with_unexpected_exit_is_not_a_skip(self) -> None:
        # A real empty filter exits -1/255. A crash code (7) with a stale
        # completion line must stay a failure rather than becoming a skip.
        text = ("No automation tests matched 'DuelAcademy.IntegrationSmoke'\n"
                "**** TEST COMPLETE. EXIT CODE: -1 ****\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text, status="fail", returncode=7)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("unexpected", step.note)

    def test_automation_no_tests_with_successful_exit_is_a_skip(self) -> None:
        text = ("No tests found\n"
                "**** TEST COMPLETE. EXIT CODE: 0 ****\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "skip")

    def test_automation_missing_completion_marker_fails_clean_exit(self) -> None:
        text = "LogAutomationCommandLine: Running tests...\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("TEST COMPLETE", step.note)

    def test_automation_nonzero_completion_marker_fails(self) -> None:
        text = "**** TEST COMPLETE. EXIT CODE: 3 ****\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("EXIT CODE: 3", step.note)

    def test_automation_negative_completion_marker_fails(self) -> None:
        text = "**** TEST COMPLETE. EXIT CODE: -1 ****\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")
            self.assertIn("EXIT CODE: -1", step.note)

    def test_automation_zero_completion_marker_passes(self) -> None:
        text = "**** TEST COMPLETE. EXIT CODE: 0 ****\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "pass")
            self.assertIn("completed", step.note)

    def test_automation_zero_failed_count_is_not_a_no_tests_skip(self) -> None:
        text = ("Automation: 102 tests run, 0 tests failed\n"
                "**** TEST COMPLETE. EXIT CODE: 0 ****\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "pass")

    def test_automation_failed_test_fails(self) -> None:
        text = "Automation Test Failed - DuelAcademy.Sample\n"
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")

    def test_automation_failed_test_beats_no_tests_text(self) -> None:
        text = ("No automation tests matched 'DuelAcademy.Sample'\n"
                "Automation Test Failed - DuelAcademy.Sample\n")
        with tempfile.TemporaryDirectory() as tmp:
            step = _step("automation", Path(tmp), text)
            run_smoke._inspect_log(step)
            self.assertEqual(step.status, "fail")


class RunStepTests(unittest.TestCase):
    def test_dry_run_does_not_create_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_dir = Path(tmp) / "logs"
            step = run_smoke.Step(name="demo", command=[sys.executable, "-c", "raise SystemExit(9)"])
            result = run_smoke._run_step(step, timeout=5, log_dir=log_dir, dry_run=True)
            self.assertEqual(result.status, "skip")
            self.assertIsNone(result.returncode)
            self.assertEqual(result.log, "")
            self.assertFalse(log_dir.exists())

    def test_nonzero_exit_is_recorded(self) -> None:
        code = "import sys; print('stdout-line'); print('stderr-line', file=sys.stderr); sys.exit(3)"
        with tempfile.TemporaryDirectory() as tmp:
            step = run_smoke.Step(name="demo", command=[sys.executable, "-c", code])
            result = run_smoke._run_step(step, timeout=30, log_dir=Path(tmp), dry_run=False)
            self.assertEqual(result.status, "fail")
            self.assertEqual(result.returncode, 3)
            log = Path(result.log).read_text(encoding="utf-8")
            self.assertIn("RETURNCODE: 3", log)
            self.assertIn("stdout-line", log)
            self.assertIn("stderr-line", log)

    def test_timeout_writes_command_and_partial_output(self) -> None:
        code = (
            "import sys, time; "
            "print('partial stdout', flush=True); "
            "print('partial stderr', file=sys.stderr, flush=True); "
            "time.sleep(60)"
        )
        with tempfile.TemporaryDirectory() as tmp:
            step = run_smoke.Step(name="demo", command=[sys.executable, "-c", code])
            result = run_smoke._run_step(step, timeout=2, log_dir=Path(tmp), dry_run=False)
            self.assertEqual(result.status, "fail")
            self.assertIsNone(result.returncode)
            log = Path(result.log).read_text(encoding="utf-8")
            self.assertIn(f"COMMAND: {subprocess.list2cmdline(step.command)}", log)
            self.assertIn("TIMEOUT after 2s", log)
            self.assertIn("partial stdout", log)
            self.assertIn("partial stderr", log)

    def test_missing_executable_is_blocked_and_logged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "does-not-exist.exe")
            step = run_smoke.Step(name="demo", command=[missing])
            result = run_smoke._run_step(step, timeout=5, log_dir=Path(tmp) / "logs", dry_run=False)
            self.assertEqual(result.status, "blocked")
            self.assertTrue(Path(result.log).exists())
            self.assertIn("EXECUTABLE NOT FOUND", Path(result.log).read_text(encoding="utf-8"))

    def test_output_text_normalises_bytes(self) -> None:
        self.assertEqual(run_smoke._output_text(None), "")
        self.assertEqual(run_smoke._output_text("text"), "text")
        self.assertEqual(run_smoke._output_text(b"bytes"), "bytes")


class ProcessTreeTests(unittest.TestCase):
    _TREE_SCRIPT = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(str(child.pid))
print("parent-ready", flush=True)
print("parent-stderr", file=sys.stderr, flush=True)
time.sleep(60)
"""

    def test_popen_tree_kwargs_isolate_the_child(self) -> None:
        self.assertEqual(run_smoke._popen_tree_kwargs("posix"), {"start_new_session": True})
        nt_kwargs = run_smoke._popen_tree_kwargs("nt")
        self.assertIn("creationflags", nt_kwargs)
        self.assertTrue(nt_kwargs["creationflags"])

    def test_timeout_terminates_child_process_tree(self) -> None:
        # The fixture spawns a long-lived grandchild and writes its PID, so the
        # test fails if only the direct UnrealEditor-style parent is killed.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pid_file = tmp_path / "child.pid"
            step = run_smoke.Step(
                name="tree",
                command=[sys.executable, "-c", self._TREE_SCRIPT, str(pid_file)],
            )
            result = run_smoke._run_step(
                step, timeout=4, log_dir=tmp_path / "logs", dry_run=False
            )
            self.assertEqual(result.status, "fail")
            self.assertIn("timeout after 4s", result.note)
            log = Path(result.log).read_text(encoding="utf-8")
            self.assertIn("TIMEOUT after 4s", log)
            self.assertIn("parent-ready", log)
            self.assertIn("parent-stderr", log)
            self.assertTrue(pid_file.exists(), "child fixture did not start")
            child_pid = int(pid_file.read_text(encoding="utf-8").strip())
            self.addCleanup(_force_kill, child_pid)
            self.assertTrue(_wait_until_dead(child_pid),
                            f"child process {child_pid} survived the timeout")


class CommandAndMainTests(unittest.TestCase):
    def test_automation_paths_with_spaces_stay_single_arguments(self) -> None:
        editor = Path("C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe")
        uproject = Path("C:/work/Duel Academy/DuelAcademyIsland.uproject")
        report_dir = Path("C:/work/Duel Academy/reports")
        step = run_smoke._automation_step(editor, uproject, "DuelAcademy.UI", report_dir)
        self.assertEqual(step.command[0], str(editor))
        self.assertEqual(step.command[1], str(uproject))
        self.assertIn(f"-ReportExportPath={report_dir / 'automation'}", step.command)
        self.assertIn("-ExecCmds=Automation RunTests DuelAcademy.UI; Quit", step.command)

    def test_validator_strict_flag(self) -> None:
        report = Path("C:/tmp/validate.json")
        normal = run_smoke._validator_step(report, strict=False)
        strict = run_smoke._validator_step(report, strict=True)
        self.assertNotIn("--strict", normal.command)
        self.assertIn("--strict", strict.command)

    def test_dry_run_all_works_without_editor_or_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            argv = [
                "--all", "--dry-run",
                "--ue-editor", str(tmp_path / "UnrealEditor-Cmd.exe"),
                "--uproject", str(tmp_path / "missing.uproject"),
                "--report-dir", str(tmp_path / "reports"),
                "--report", str(tmp_path / "smoke.json"),
            ]
            with redirect_stdout(StringIO()) as out:
                rc = run_smoke.main(argv)
            self.assertEqual(rc, 0, out.getvalue())
            report = json.loads((tmp_path / "smoke.json").read_text(encoding="utf-8"))
            self.assertEqual(report["result"], "PASS")
            self.assertEqual({step["name"] for step in report["steps"]},
                             {"validate", "duel-selftest", "profile-selftest", "duelrules-selftest",
                              "economy-selftest", "a07-selftest", "automation"})
            self.assertTrue(all(step["command"] for step in report["steps"]))
            self.assertTrue(all(step["status"] == "skip" for step in report["steps"]))

    def test_profile_selftest_requires_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            argv = ["--profile-selftest", "--uproject", str(Path(tmp) / "missing.uproject"),
                    "--report-dir", str(Path(tmp) / "reports")]
            with redirect_stderr(StringIO()) as err:
                rc = run_smoke.main(argv)
            self.assertEqual(rc, 2)
            self.assertIn("uproject not found", err.getvalue())

    def test_relative_report_paths_resolve_against_current_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            previous_cwd = Path.cwd()
            os.chdir(tmp_path)
            try:
                argv = [
                    "--validate", "--dry-run",
                    "--report-dir", "reports",
                    "--report", "out/smoke.json",
                    "--validate-report", "out/validate.json",
                ]
                with redirect_stdout(StringIO()):
                    rc = run_smoke.main(argv)
            finally:
                os.chdir(previous_cwd)
            self.assertEqual(rc, 0)
            self.assertTrue((tmp_path / "reports").is_dir())
            report = json.loads((tmp_path / "out" / "smoke.json").read_text(encoding="utf-8"))
            self.assertEqual(report["result"], "PASS")
            validate_step = next(step for step in report["steps"] if step["name"] == "validate")
            self.assertIn(str(tmp_path / "out" / "validate.json"), validate_step["command"])

    def test_now_slug_has_subsecond_and_pid_precision(self) -> None:
        first = run_smoke._now_slug()
        second = run_smoke._now_slug()
        self.assertRegex(first, r"^\d{8}-\d{6}-\d{6}-\d+-\d+$")
        self.assertNotEqual(first, second)

    def test_report_path_defaults_into_report_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp).resolve()
            path = run_smoke._report_path("smoke", "", report_dir)
            self.assertEqual(path.parent, report_dir)
            self.assertRegex(path.name, r"^smoke-\d{8}-\d{6}-\d{6}-\d+-\d+\.json$")

    def test_atomic_writer_leaves_no_temp_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "out.txt"
            run_smoke._write_text_atomic(path, "hello")
            self.assertEqual(path.read_text(encoding="utf-8"), "hello")
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_unwritable_report_path_returns_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            report_dir = tmp_path / "reports"
            report_dir.mkdir()
            argv = [
                "--validate", "--dry-run",
                "--report-dir", str(tmp_path / "logs"),
                "--report", str(report_dir),  # a directory, not a file
            ]
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                rc = run_smoke.main(argv)
            self.assertEqual(rc, 2)
            self.assertIn("cannot write smoke report", err.getvalue())


class ReportResultTests(unittest.TestCase):
    def test_failure_beats_blocked(self) -> None:
        report = run_smoke.SmokeReport()
        report.add(run_smoke.Step(name="a", command=[], status="blocked"))
        report.add(run_smoke.Step(name="b", command=[], status="fail"))
        self.assertEqual(report.result(), "FAIL")

    def test_blocked_only_is_blocked(self) -> None:
        report = run_smoke.SmokeReport()
        report.add(run_smoke.Step(name="a", command=[], status="blocked"))
        self.assertEqual(report.result(), "BLOCKED")


if __name__ == "__main__":
    unittest.main()
