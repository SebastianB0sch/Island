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

Self-test and automation steps pass only when their summary line is present
and reports zero failures (see ue_common.py); a log with no summary, or an
automation filter that matches no tests, is a failure.

Exit codes:
    0  every requested step passed
    1  a requested step failed
    2  configuration error (missing project/editor), or nothing ran (--dry-run)
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ue_common import (  # noqa: E402
    DEFAULT_UPROJECT,
    ROOT,
    SELFTEST_SWITCHES,
    automation_verdict,
    headless_game_command,
    now_slug as _now_slug,
    resolve_editor,
    selftest_verdict,
)

DEFAULT_REPORT_DIR = ROOT / "Docs" / "Integration" / "reports"
TOOL_VERSION = "1.1.0"


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
        if all(step.status == "skip" for step in self.steps):
            return "SKIPPED"
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
        completed = subprocess.run(
            step.command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        step.returncode = completed.returncode
        log_path.write_text(
            f"COMMAND: {subprocess.list2cmdline(step.command)}\n"
            f"RETURNCODE: {completed.returncode}\n\n"
            f"--- stdout ---\n{completed.stdout}\n\n--- stderr ---\n{completed.stderr}\n",
            encoding="utf-8",
        )
        step.status = "pass" if completed.returncode == 0 else "fail"
        step.note = "" if completed.returncode == 0 else f"exit code {completed.returncode}"
    except subprocess.TimeoutExpired as exc:
        step.returncode = None
        step.status = "fail"
        step.note = f"timeout after {timeout}s"
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        log_path.write_text(f"TIMEOUT\n\n{stdout}\n\n{stderr}\n", encoding="utf-8")
    except FileNotFoundError as exc:
        step.returncode = None
        step.status = "blocked"
        step.note = f"executable not found: {exc.filename}"
    except OSError as exc:
        step.returncode = None
        step.status = "blocked"
        step.note = f"cannot execute: {exc}"
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
    command = headless_game_command(editor, uproject, f"{SELFTEST_SWITCHES['duel']}={iterations}")
    return Step(name="duel-selftest", command=command)


def _selftest_step(name: str, switch: str, editor: Path, uproject: Path) -> Step:
    return Step(name=name, command=headless_game_command(editor, uproject, switch))


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


# run_smoke step name -> ue_common self-test kind
STEP_KINDS = {
    "duel-selftest": "duel",
    "profile-selftest": "profile",
    "duelrules-selftest": "duelrules",
    "economy-selftest": "economy",
    "story-selftest": "story",
    "puzzle-selftest": "puzzle",
    "exam-selftest": "exam",
    "a07-selftest": "a07",
}


def _inspect_log(step: Step) -> None:
    """Judge a captured UE log with the strict summary parser (ue_common)."""
    if step.status in ("blocked", "skip"):
        return
    log_path = Path(step.log) if step.log else None
    if not log_path or not log_path.exists():
        return
    text = log_path.read_text(encoding="utf-8", errors="replace")
    if step.name == "automation":
        step.status, note = automation_verdict(text, step.returncode)
        step.note = note or step.note
        return
    kind = STEP_KINDS.get(step.name)
    if kind is None:
        return
    if step.returncode is None:  # timeout: keep the failure from _run_step
        return
    passed, note = selftest_verdict(kind, text)
    if passed and step.returncode != 0:
        step.status = "fail"
        step.note = f"{note} (but exit code {step.returncode})"
    else:
        step.status = "pass" if passed else "fail"
        step.note = note


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
    parser.add_argument("--report", default="", help="smoke JSON report path (default: reports/smoke-<timestamp>.json)")
    parser.add_argument("--validate-report", default="", help="validator JSON report path (default: reports/validate-<timestamp>.json)")
    parser.add_argument("--report-dir", default=str(DEFAULT_REPORT_DIR), help="report/log directory")
    parser.add_argument("--timeout", type=int, default=1800, help="per-step timeout in seconds")
    parser.add_argument("--dry-run", action="store_true", help="print commands without launching anything")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--version", action="version", version=f"run_smoke {TOOL_VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = ROOT
    uproject = Path(args.uproject).expanduser().resolve()
    report_dir = Path(args.report_dir).expanduser().resolve()
    report_dir.mkdir(parents=True, exist_ok=True)

    if not uproject.exists() and (args.duel_selftest or args.automation or args.all
                                  or args.puzzle_selftest or args.exam_selftest or args.a07_selftest):
        print(f"error: uproject not found: {uproject}", file=sys.stderr)
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
    run_validate = not args.no_validate and (
        args.validate or run_all or not (wants_selftests or args.automation)
    )
    editor = resolve_editor(args.ue_editor) if (wants_selftests or args.automation) else None

    report = SmokeReport(
        generated_at=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        editor=str(editor) if editor else "",
        uproject=str(uproject),
    )

    if run_validate:
        report_path = Path(args.validate_report) if args.validate_report else report_dir / f"validate-{_now_slug()}.json"
        if not report_path.is_absolute():
            report_path = root / report_path
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
        selftest_jobs.append(("duel-selftest", SELFTEST_SWITCHES["duel"]))
    if args.profile_selftest or run_selftests:
        selftest_jobs.append(("profile-selftest", SELFTEST_SWITCHES["profile"]))
    if args.duelrules_selftest or run_selftests:
        selftest_jobs.append(("duelrules-selftest", SELFTEST_SWITCHES["duelrules"]))
    if args.economy_selftest or run_selftests:
        selftest_jobs.append(("economy-selftest", SELFTEST_SWITCHES["economy"]))
    if args.story_selftest:
        selftest_jobs.append(("story-selftest", SELFTEST_SWITCHES["story"]))
    if run_all and not args.a07_selftest and not args.puzzle_selftest and not args.exam_selftest:
        selftest_jobs.append(("a07-selftest", SELFTEST_SWITCHES["a07"]))
    if args.a07_selftest:
        selftest_jobs.append(("a07-selftest", SELFTEST_SWITCHES["a07"]))
    else:
        if args.puzzle_selftest:
            selftest_jobs.append(("puzzle-selftest", SELFTEST_SWITCHES["puzzle"]))
        if args.exam_selftest:
            selftest_jobs.append(("exam-selftest", SELFTEST_SWITCHES["exam"]))

    for name, switch in selftest_jobs:
        if editor is None:
            report.add(Step(name=name, command=[], status="blocked", note="UnrealEditor-Cmd.exe not found; set UE_EDITOR"))
            continue
        if name == "duel-selftest":
            step = _duel_selftest_step(editor, uproject, args.iterations)
        else:
            step = _selftest_step(name, switch, editor, uproject)
        step = _run_step(
            step,
            timeout=args.timeout,
            log_dir=report_dir / "logs",
            dry_run=args.dry_run,
        )
        _inspect_log(step)
        report.add(step)

    if args.automation or run_all:
        if editor is None:
            report.add(Step(name="automation", command=[], status="blocked", note="UnrealEditor-Cmd.exe not found; set UE_EDITOR"))
        else:
            step = _run_step(
                _automation_step(editor, uproject, args.automation_filter, report_dir),
                timeout=args.timeout,
                log_dir=report_dir / "logs",
                dry_run=args.dry_run,
            )
            _inspect_log(step)
            report.add(step)

    if not report.steps:
        report.add(Step(name="none", command=[], status="skip", note="no steps selected"))

    _print_human(report, json_output=args.json)

    report_path = Path(args.report) if args.report else report_dir / f"smoke-{_now_slug()}.json"
    if not report_path.is_absolute():
        report_path = root / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not args.json:
        print(f"Report: {report_path}")

    result = report.result()
    if result == "PASS":
        return 0
    return 1 if result == "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
