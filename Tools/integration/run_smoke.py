#!/usr/bin/env python3
"""Duel Academy integration smoke runner.

This is the single entry point A10 uses at a merge gate:

    python Tools/integration/run_smoke.py --validate
    python Tools/integration/run_smoke.py --validate --duel-selftest
    python Tools/integration/run_smoke.py --all --automation-filter DuelAcademy

The validator step always runs first and is the only step that works without an
Unreal install. The UE steps are explicit because they launch the editor
headless and can take minutes; they are stubs for automation suites that A02,
A03, A04, A07 and A09 have not published yet.

Exit codes:
    0  every requested step passed (or was intentionally skipped)
    1  a requested step failed
    2  configuration error (missing project/editor)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_UPROJECT = ROOT / "DuelAcademyIsland" / "DuelAcademyIsland.uproject"
DEFAULT_REPORT_DIR = ROOT / "Docs" / "Integration" / "reports"
DEFAULT_UE_EDITOR = Path(r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
TOOL_VERSION = "1.0.0"

# Log markers and final-summary formats emitted by the in-engine self-tests.
# The summary (not the first "PASS" line) decides the outcome; per-check lines
# can pass while later checks fail.
_SELFTEST_MARKERS = {
    "profile-selftest": "DAProfileSelfTest",
    "duelrules-selftest": "Duel rules self-test:",
    "economy-selftest": "DAEconomySelfTest:",
    "story-selftest": "StorySelfTest:",
    "puzzle-selftest": "PuzzleSelfTest:",
    "exam-selftest": "ExamSelfTest:",
}
_SELFTEST_SUMMARIES = {
    "profile-selftest": re.compile(r"DAProfileSelfTest (PASSED|FAILED)\."),
    "duelrules-selftest": re.compile(r"Duel rules self-test: (\d+) passed, (\d+) failed\."),
    "economy-selftest": re.compile(r"DAEconomySelfTest: (\d+) passed, (\d+) failed\."),
    "story-selftest": re.compile(r"StorySelfTest: (PASS|FAIL) in [\d.]+s"),
    "puzzle-selftest": re.compile(r"PuzzleSelfTest: (\d+) passed, (\d+) failed\."),
    "exam-selftest": re.compile(r"ExamSelfTest: (\d+) passed, (\d+) failed\."),
}
# Unreal automation markers. A definitive completion line wins over "no tests
# matched" text: a crashed run can still contain a no-tests sentence.
_NO_AUTOMATION_TESTS = re.compile(
    r"No automation tests matched|No tests found|No automation tests (?:were )?found"
    r"|\b0 tests? (?:run|matched|found)\b",
    re.IGNORECASE,
)
_AUTOMATION_COMPLETE = re.compile(r"TEST COMPLETE\. EXIT CODE:\s*(-?\d+)")
_SLUG_SEQUENCE = 0


def _now_slug() -> str:
    """Return a collision-resistant run id for report and log filenames."""
    global _SLUG_SEQUENCE
    _SLUG_SEQUENCE += 1
    now = _dt.datetime.now()
    return (
        f"{now:%Y%m%d-%H%M%S}-{now.microsecond:06d}-"
        f"{os.getpid()}-{_SLUG_SEQUENCE}"
    )


@dataclass
class Step:
    name: str
    command: list[str]
    status: str = "pending"
    returncode: int | None = None
    duration_seconds: float = 0.0
    log: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "status": self.status,
            "returncode": self.returncode,
            "duration_seconds": round(self.duration_seconds, 3),
            "log": self.log,
            "note": self.note,
        }


@dataclass
class SmokeReport:
    steps: list[Step] = field(default_factory=list)
    generated_at: str = ""
    editor: str = ""
    uproject: str = ""

    def add(self, step: Step) -> None:
        self.steps.append(step)

    def result(self) -> str:
        if any(step.status == "fail" for step in self.steps):
            return "FAIL"
        if any(step.status == "blocked" for step in self.steps):
            return "BLOCKED"
        return "PASS"

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": "run_smoke",
            "tool_version": TOOL_VERSION,
            "generated_at": self.generated_at,
            "result": self.result(),
            "editor": self.editor,
            "uproject": self.uproject,
            "steps": [step.to_dict() for step in self.steps],
        }


def _resolve_editor(args: argparse.Namespace, *, require_exists: bool = True) -> Path | None:
    if args.ue_editor:
        return Path(args.ue_editor).expanduser().resolve()
    env = os.environ.get("UE_EDITOR") or os.environ.get("UNREAL_EDITOR")
    if env:
        return Path(env).expanduser().resolve()
    if DEFAULT_UE_EDITOR.exists() or not require_exists:
        return DEFAULT_UE_EDITOR
    return None


def _resolve_cli_path(value: str, *, base: Path | None = None) -> Path:
    """Resolve a CLI path against the current directory unless it is absolute.

    ``--report``, ``--validate-report``, ``--report-dir`` and ``--uproject``
    all follow this rule so relative paths mean the same thing before and
    after a run started from outside the repository.
    """
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()


def _output_text(value: str | bytes | None) -> str:
    """Normalise captured subprocess output for log files."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _write_text_atomic(path: Path, text: str) -> None:
    """Write UTF-8 text through a same-directory temp file.

    Reports and step logs are gate evidence; an interrupted run must not leave
    a half-written JSON report that later parses as valid-but-empty.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def _popen_tree_kwargs(platform: str | None = None) -> dict[str, Any]:
    """Popen kwargs that isolate a step in a killable process group."""
    if (platform or os.name) == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)}
    return {"start_new_session": True}


def _terminate_process_tree(proc: subprocess.Popen, *, grace_seconds: float = 2.0) -> None:
    """Terminate ``proc`` and its descendants; safe after the child exited.

    ``subprocess.run(timeout=...)`` only kills the direct child. Editors such
    as ``UnrealEditor-Cmd`` spawn helpers that would otherwise keep running
    and hold the captured pipes open.
    """
    if proc.poll() is not None:
        return
    if os.name == "nt":
        # taskkill /T walks the child tree. Fall back to proc.kill() when the
        # utility is unavailable or the process exits mid-call.
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=grace_seconds,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        try:
            proc.wait(timeout=grace_seconds)
        except subprocess.TimeoutExpired:
            pass
        return

    # POSIX: start_new_session=True made the child a process-group leader, so
    # killing the group also kills its helpers.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        try:
            proc.kill()
        except OSError:
            pass
        return
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(proc.pid, getattr(signal, "SIGKILL", signal.SIGTERM))
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=grace_seconds)
    except subprocess.TimeoutExpired:
        pass


def _format_step_log(command: list[str], status_line: str, stdout: str = "", stderr: str = "") -> str:
    text = f"COMMAND: {subprocess.list2cmdline(command)}\n{status_line}\n"
    if stdout or stderr:
        text += f"\n--- stdout ---\n{stdout}\n\n--- stderr ---\n{stderr}\n"
    return text


def _run_step(
    step: Step,
    *,
    timeout: int,
    log_dir: Path,
    dry_run: bool,
) -> Step:
    if dry_run:
        step.status = "skip"
        step.note = "dry run"
        return step
    started = time.monotonic()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{step.name}-{_now_slug()}.log"
    step.log = str(log_path)
    try:
        proc = subprocess.Popen(
            step.command,
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            **_popen_tree_kwargs(),
        )
    except FileNotFoundError as exc:
        step.returncode = None
        step.status = "blocked"
        step.note = f"executable not found: {exc.filename}"
        _write_text_atomic(
            log_path,
            _format_step_log(step.command, f"EXECUTABLE NOT FOUND: {exc.filename}"),
        )
    except OSError as exc:
        step.returncode = None
        step.status = "blocked"
        step.note = f"cannot execute: {exc}"
        _write_text_atomic(
            log_path,
            _format_step_log(step.command, f"CANNOT EXECUTE: {exc}"),
        )
    else:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            partial_stdout = _output_text(exc.output)
            partial_stderr = _output_text(exc.stderr)
            _terminate_process_tree(proc)
            try:
                stdout, stderr = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                stdout, stderr = "", ""
            stdout = _output_text(stdout) or partial_stdout
            stderr = _output_text(stderr) or partial_stderr
            step.returncode = None
            step.status = "fail"
            step.note = f"timeout after {timeout}s"
            _write_text_atomic(
                log_path,
                _format_step_log(step.command, f"TIMEOUT after {timeout}s", stdout, stderr),
            )
        else:
            step.returncode = proc.returncode
            _write_text_atomic(
                log_path,
                _format_step_log(step.command, f"RETURNCODE: {proc.returncode}", stdout, stderr),
            )
            step.status = "pass" if proc.returncode == 0 else "fail"
            step.note = "" if proc.returncode == 0 else f"exit code {proc.returncode}"
    finally:
        step.duration_seconds = time.monotonic() - started
    return step


def _validator_step(report_path: Path, *, strict: bool) -> Step:
    command = [
        sys.executable,
        str(ROOT / "Tools" / "validate" / "validate_all.py"),
        "--report",
        str(report_path),
    ]
    if strict:
        command.append("--strict")
    return Step(name="validate", command=command)


def _duel_selftest_step(editor: Path, uproject: Path, iterations: int) -> Step:
    # A04: the counted form is owned by UDADuelRulesSelfTestSubsystem so it also
    # works when the HUD is not the launch path.
    command = [
        str(editor),
        str(uproject),
        "-game",
        "-nullrhi",
        "-nosound",
        "-unattended",
        "-nop4",
        f"-DADuelSelfTest={iterations}",
        "-log",
        "-stdout",
        "-FullStdOutLogOutput",
    ]
    return Step(name="duel-selftest", command=command)


def _selftest_step(name: str, switch: str, editor: Path, uproject: Path) -> Step:
    command = [
        str(editor),
        str(uproject),
        "-game",
        "-nullrhi",
        "-nosound",
        "-unattended",
        "-nop4",
        switch,
        "-log",
        "-stdout",
        "-FullStdOutLogOutput",
    ]
    return Step(name=name, command=command)


def _automation_step(editor: Path, uproject: Path, filter_name: str, report_dir: Path) -> Step:
    automation_dir = report_dir / "automation"
    command = [
        str(editor),
        str(uproject),
        f"-ExecCmds=Automation RunTests {filter_name}; Quit",
        f"-ReportExportPath={automation_dir}",
        "-unattended",
        "-nop4",
        "-nullrhi",
        "-nosound",
        "-log",
        "-stdout",
        "-FullStdOutLogOutput",
    ]
    return Step(name="automation", command=command)


def _mark_failed(step: Step, note: str) -> None:
    step.status = "fail"
    step.note = note


def _duel_selftest_failure_reason(summary: str) -> str:
    """Return why a ``Duel self-test:`` summary line failed, or "" if it passed."""
    if "RESULT FAIL" in summary:
        return "RESULT FAIL"
    if "stalls" not in summary:
        return "missing stalls field"
    try:
        stalls = int(summary.split("stalls")[0].strip().split()[-1])
    except (ValueError, IndexError):
        return "unparsable stalls field"
    if stalls > 0:
        return f"stalls {stalls}"
    return ""


def _inspect_duel_selftest(step: Step, text: str) -> None:
    summary = ""
    for raw_line in text.splitlines():
        if "Duel self-test:" in raw_line:
            summary = raw_line.strip()
    if not summary:
        if step.status == "pass":
            _mark_failed(step, "missing 'Duel self-test:' summary in log")
        return
    reason = _duel_selftest_failure_reason(summary)
    if reason:
        _mark_failed(step, f"{summary} ({reason})")
    elif step.status == "pass":
        step.note = summary


def _inspect_named_selftest(step: Step, text: str) -> None:
    marker = _SELFTEST_MARKERS[step.name]
    summary_re = _SELFTEST_SUMMARIES[step.name]
    failure_line = ""
    summary_line = ""
    summary_seen = False
    summary_failed = False
    zero_check_line = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if step.name == "profile-selftest" and "[FAIL]" in line:
            failure_line = line
        if step.name == "story-selftest" and re.search(r"StorySelfTest:\s+FAIL\b", line):
            failure_line = line
        match = summary_re.search(line)
        if not match:
            continue
        summary_line = line
        summary_seen = True
        if step.name in {"profile-selftest", "story-selftest"}:
            summary_failed = summary_failed or match.group(1) not in {"PASSED", "PASS"}
        else:
            passed, failed = int(match.group(1)), int(match.group(2))
            summary_failed = summary_failed or failed != 0
            if passed + failed == 0:
                zero_check_line = line
    if failure_line:
        _mark_failed(step, failure_line)
    elif summary_seen and summary_failed:
        _mark_failed(step, summary_line)
    elif not summary_seen:
        if step.status == "pass":
            _mark_failed(step, f"missing {marker} summary in log")
    elif zero_check_line:
        _mark_failed(step, f"{zero_check_line} (0 checks reported)")
    elif step.status == "pass":
        step.note = summary_line


def _inspect_a07_selftest(step: Step, text: str) -> None:
    suites = {
        "PuzzleSelfTest:": _SELFTEST_SUMMARIES["puzzle-selftest"],
        "ExamSelfTest:": _SELFTEST_SUMMARIES["exam-selftest"],
    }
    seen: set[str] = set()
    checks_by_suite: dict[str, int] = {}
    failure_line = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "A07SelfTest: FAILURES PRESENT" in line:
            failure_line = line
        for marker, summary_re in suites.items():
            match = summary_re.search(line)
            if not match:
                continue
            seen.add(marker)
            passed, failed = int(match.group(1)), int(match.group(2))
            checks_by_suite[marker] = passed + failed
            if failed:
                failure_line = line
    if failure_line:
        _mark_failed(step, failure_line)
    elif "A07SelfTest: BOTH SUITES PASS" in text and seen == set(suites) and all(checks_by_suite.values()):
        if step.status == "pass":
            step.note = "A07SelfTest: BOTH SUITES PASS"
    elif seen and any(checks == 0 for checks in checks_by_suite.values()):
        _mark_failed(step, "A07 suites reported 0 checks")
    elif step.status == "pass":
        _mark_failed(step, "missing one or both A07 suite summaries")


def _inspect_automation(step: Step, text: str) -> None:
    failures = [line.strip() for line in text.splitlines()
                if "Automation Test Failed" in line or "Result: Failed" in line]
    if failures:
        _mark_failed(step, failures[0])
        return
    completion = _AUTOMATION_COMPLETE.search(text)
    if _NO_AUTOMATION_TESTS.search(text):
        # Unreal exits non-zero (-1 / 255) when a filter matches nothing, so
        # the no-tests marker and a completion line are the skip contract.
        # A timeout or an interrupted/crashed run must never become an
        # intentional skip, even if a partial log happens to contain both.
        if step.returncode is None:
            return
        if completion is None:
            if step.status == "pass":
                _mark_failed(step, "no tests matched but the log has no TEST COMPLETE marker")
            return
        completion_code = int(completion.group(1))
        if completion_code not in {0, -1} or step.returncode not in {0, -1, 255}:
            _mark_failed(
                step,
                f"no-tests text with unexpected completion/exit "
                f"({completion.group(0)}, process exit {step.returncode})",
            )
            return
        step.status = "skip"
        step.note = "no automation tests matched the filter"
        return
    if completion and int(completion.group(1)) != 0:
        _mark_failed(step, completion.group(0))
        return
    if step.status != "pass":
        return
    if completion:
        step.note = "automation completed with exit code 0"
    else:
        _mark_failed(step, "missing 'TEST COMPLETE. EXIT CODE:' marker in log")


def _inspect_log(step: Step) -> None:
    """Extract a known self-test / automation summary from a captured log.

    The process return code is authoritative for failures: inspection may
    downgrade a passing step when the log reports a failed check, but it never
    turns a failed, timed-out or blocked step into a pass.
    """
    log_path = Path(step.log) if step.log else None
    if not log_path or not log_path.exists():
        return
    text = log_path.read_text(encoding="utf-8", errors="replace")
    if step.name == "duel-selftest":
        _inspect_duel_selftest(step, text)
    elif step.name in _SELFTEST_MARKERS:
        _inspect_named_selftest(step, text)
    elif step.name == "a07-selftest":
        _inspect_a07_selftest(step, text)
    elif step.name == "automation":
        _inspect_automation(step, text)


def _run_and_inspect(
    step: Step,
    *,
    timeout: int,
    report_dir: Path,
    dry_run: bool,
) -> Step:
    step = _run_step(step, timeout=timeout, log_dir=report_dir / "logs", dry_run=dry_run)
    _inspect_log(step)
    return step


def _report_path(prefix: str, explicit: str, report_dir: Path) -> Path:
    """Resolve an explicit report path or build the default under ``report_dir``."""
    if explicit:
        return _resolve_cli_path(explicit)
    return report_dir / f"{prefix}-{_now_slug()}.json"


def _print_human(report: SmokeReport, *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return
    print(f"Duel Academy smoke runner {TOOL_VERSION}")
    print(f"  root:     {ROOT}")
    print(f"  uproject: {report.uproject}")
    print(f"  editor:   {report.editor or '(not requested)'}")
    print()
    for step in report.steps:
        print(f"  [{step.status.upper():7}] {step.name}: {step.duration_seconds:.1f}s")
        print(f"            {subprocess.list2cmdline(step.command)}")
        if step.note:
            print(f"            {step.note}")
        if step.log:
            print(f"            log: {step.log}")
    print()
    print(f"Result: {report.result()}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Duel Academy integration smoke suite.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--validate", action="store_true", help="run validate_all.py (default if no step is selected)")
    parser.add_argument("--no-validate", action="store_true", help="skip validate_all.py")
    parser.add_argument("--strict", action="store_true", help="pass --strict to validate_all.py")
    parser.add_argument("--duel-selftest", action="store_true", help="run the headless -DADuelSelfTest smoke")
    parser.add_argument("--profile-selftest", action="store_true", help="run A02's -DAProfileSelfTest")
    parser.add_argument("--duelrules-selftest", action="store_true", help="run A04's -DADuelRulesSelfTest")
    parser.add_argument("--economy-selftest", action="store_true", help="run A06's -DAEconomySelfTest")
    parser.add_argument("--story-selftest", action="store_true", help="run A03's -DAStorySelfTest (explicit; the editor may stay open)")
    parser.add_argument("--puzzle-selftest", action="store_true", help="run A07's -DAPuzzleSelfTest (100 authored puzzles)")
    parser.add_argument("--exam-selftest", action="store_true", help="run A07's -DAExamSelfTest (12 exam cycles)")
    parser.add_argument("--a07-selftest", action="store_true", help="run both A07 suites with -DAPuzzleExamSelfTest")
    parser.add_argument("--self-tests", action="store_true", help="run the four stable headless self-tests")
    parser.add_argument("--automation", action="store_true", help="run Unreal automation tests matching --automation-filter")
    parser.add_argument("--all", action="store_true", help="validate + all self-tests + automation")
    parser.add_argument("--automation-filter", default="DuelAcademy", help="Unreal automation test filter")
    parser.add_argument("--iterations", type=int, default=24, help="requested duel self-test iterations (passed as -DADuelSelfTest=N)")
    parser.add_argument("--ue-editor", default="", help="path to UnrealEditor-Cmd.exe (or set UE_EDITOR)")
    parser.add_argument("--uproject", default=str(DEFAULT_UPROJECT), help="path to the .uproject")
    parser.add_argument("--report", default="", help="smoke JSON report path, relative to the current directory (default: <report-dir>/smoke-<run>.json)")
    parser.add_argument("--validate-report", default="", help="validator JSON report path, relative to the current directory (default: <report-dir>/validate-<run>.json)")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="report/log directory, relative to the current directory")
    parser.add_argument("--timeout", type=int, default=1800, help="per-step timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="print commands without launching anything")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--version", action="version", version=f"run_smoke {TOOL_VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    uproject = _resolve_cli_path(args.uproject)
    report_dir = _resolve_cli_path(args.report_dir)
    try:
        report_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot create report directory {report_dir}: {exc}", file=sys.stderr)
        return 2

    if args.iterations < 1:
        print("error: --iterations must be >= 1", file=sys.stderr)
        return 2

    run_all = args.all
    run_selftests = args.self_tests or run_all
    wants_selftests = (
        args.duel_selftest
        or args.profile_selftest
        or args.duelrules_selftest
        or args.economy_selftest
        or args.story_selftest
        or args.puzzle_selftest
        or args.exam_selftest
        or args.a07_selftest
        or run_selftests
    )
    needs_project = wants_selftests or args.automation
    if needs_project and not args.dry_run and not uproject.exists():
        print(f"error: uproject not found: {uproject}", file=sys.stderr)
        return 2
    run_validate = not args.no_validate and (
        args.validate or run_all or not needs_project
    )
    editor = _resolve_editor(args, require_exists=not args.dry_run) if needs_project else None

    report = SmokeReport(
        generated_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        editor=str(editor) if editor else "",
        uproject=str(uproject),
    )

    if run_validate:
        report_path = _report_path("validate", args.validate_report, report_dir)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        step = _run_step(
            _validator_step(report_path, strict=args.strict),
            timeout=args.timeout,
            log_dir=report_dir / "logs",
            dry_run=args.dry_run,
        )
        report.add(step)

    selftest_jobs: list[tuple[str, str]] = []
    if args.duel_selftest or run_selftests:
        selftest_jobs.append(("duel-selftest", "-DADuelSelfTest"))
    if args.profile_selftest or run_selftests:
        selftest_jobs.append(("profile-selftest", "-DAProfileSelfTest"))
    if args.duelrules_selftest or run_selftests:
        selftest_jobs.append(("duelrules-selftest", "-DADuelRulesSelfTest"))
    if args.economy_selftest or run_selftests:
        selftest_jobs.append(("economy-selftest", "-DAEconomySelfTest"))
    if args.story_selftest:
        selftest_jobs.append(("story-selftest", "-DAStorySelfTest"))
    if run_all and not args.a07_selftest and not args.puzzle_selftest and not args.exam_selftest:
        selftest_jobs.append(("a07-selftest", "-DAPuzzleExamSelfTest"))
    if args.a07_selftest:
        selftest_jobs.append(("a07-selftest", "-DAPuzzleExamSelfTest"))
    else:
        if args.puzzle_selftest:
            selftest_jobs.append(("puzzle-selftest", "-DAPuzzleSelfTest"))
        if args.exam_selftest:
            selftest_jobs.append(("exam-selftest", "-DAExamSelfTest"))

    for name, switch in selftest_jobs:
        if editor is None:
            report.add(Step(name=name, command=[], status="blocked", note="UnrealEditor-Cmd.exe not found; set UE_EDITOR"))
            continue
        if name == "duel-selftest":
            step = _duel_selftest_step(editor, uproject, args.iterations)
        else:
            step = _selftest_step(name, switch, editor, uproject)
        step = _run_and_inspect(
            step,
            timeout=args.timeout,
            report_dir=report_dir,
            dry_run=args.dry_run,
        )
        report.add(step)

    if args.automation or run_all:
        if editor is None:
            report.add(Step(name="automation", command=[], status="blocked", note="UnrealEditor-Cmd.exe not found; set UE_EDITOR"))
        else:
            step = _run_and_inspect(
                _automation_step(editor, uproject, args.automation_filter, report_dir),
                timeout=args.timeout,
                report_dir=report_dir,
                dry_run=args.dry_run,
            )
            report.add(step)

    if not report.steps:
        report.add(Step(name="none", command=[], status="skip", note="no steps selected"))

    _print_human(report, json_output=args.json)

    report_path = _report_path("smoke", args.report, report_dir)
    try:
        _write_text_atomic(
            report_path,
            json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        )
    except OSError as exc:
        print(f"error: cannot write smoke report {report_path}: {exc}", file=sys.stderr)
        return 2
    if not args.json:
        print(f"Report: {report_path}")

    if report.result() == "PASS":
        return 0
    return 1 if report.result() == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
