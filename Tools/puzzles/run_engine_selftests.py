#!/usr/bin/env python3
"""Run A07's in-engine puzzle and exam self-tests headless.

Usage:
    python Tools/puzzles/run_engine_selftests.py
    python Tools/puzzles/run_engine_selftests.py --mode puzzles
    python Tools/puzzles/run_engine_selftests.py --mode exams
    python Tools/puzzles/run_engine_selftests.py --ue-editor "C:/.../UnrealEditor-Cmd.exe"

The C++ switches are:
    -DAPuzzleExamSelfTest   both suites in one process (default here)
    -DAPuzzleSelfTest       puzzles only
    -DAExamSelfTest         exams only

The runner writes the full log, prints the exact PASS summaries and exits 0
only when the process and every requested suite pass.  It never launches PIE.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
from ue_common import (  # noqa: E402
    DEFAULT_UPROJECT,
    ROOT,
    SELFTEST_SWITCHES,
    headless_game_command,
    now_slug as _now_slug,
    parse_suite_summaries as _parse_summaries,
    resolve_editor as _resolve_editor,
    selftest_verdict,
)

# --mode -> ue_common self-test kind
MODES = {"puzzles": "puzzle", "exams": "exam", "combined": "a07"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run A07 puzzle/exam in-engine self-tests.")
    parser.add_argument("--mode", choices=sorted(MODES), default="combined")
    parser.add_argument("--ue-editor", default="", help="path to UnrealEditor-Cmd.exe (or set UE_EDITOR)")
    parser.add_argument("--uproject", default=str(DEFAULT_UPROJECT))
    parser.add_argument("--timeout", type=int, default=1800, help="process timeout in seconds")
    parser.add_argument("--log", default="", help="log path (default: Docs/Integration/reports/logs/...)")
    parser.add_argument("--json", action="store_true", help="print a JSON result")
    args = parser.parse_args(argv)
    if args.timeout < 1:
        print("error: --timeout must be >= 1", file=sys.stderr)
        return 2

    editor = _resolve_editor(args.ue_editor)
    if editor is None or not editor.exists():
        print("error: UnrealEditor-Cmd.exe not found; set UE_EDITOR or pass --ue-editor", file=sys.stderr)
        return 2
    uproject = Path(args.uproject).expanduser().resolve()
    if not uproject.exists():
        print(f"error: uproject not found: {uproject}", file=sys.stderr)
        return 2

    log_path = Path(args.log).expanduser() if args.log else (
        ROOT / "Docs" / "Integration" / "reports" / "logs" / f"a07-selftest-{args.mode}-{_now_slug()}.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)

    kind = MODES[args.mode]
    command = headless_game_command(editor, uproject, SELFTEST_SWITCHES[kind])
    started = _dt.datetime.now(_dt.timezone.utc)
    try:
        returncode, output, timed_out = _execute(command, ROOT, args.timeout)
    except OSError as exc:
        print(f"error: cannot execute {editor}: {exc}", file=sys.stderr)
        return 2

    try:
        _write_text_atomic(
            log_path,
            f"COMMAND: {subprocess.list2cmdline(command)}\n"
            f"STARTED: {started.isoformat()}\n"
            f"RETURNCODE: {returncode if returncode is not None else 'timeout'}\n\n{output}",
        )
    except OSError as exc:
        print(f"error: cannot write log {log_path}: {exc}", file=sys.stderr)
        return 2

    text = log_path.read_text(encoding="utf-8", errors="replace")
    summaries = _parse_summaries(text)
    failure_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("FAIL:")]
    combined_ok = "A07SelfTest: BOTH SUITES PASS" in text
    required = ["PuzzleSelfTest", "ExamSelfTest"] if args.mode == "combined" else (
        ["PuzzleSelfTest"] if args.mode == "puzzles" else ["ExamSelfTest"]
    )
    suites_ok, verdict_note = selftest_verdict(kind, text)
    passed = returncode == 0 and not timed_out and suites_ok

    for key in required:
        summary = summaries.get(key)
        if summary is None:
            print(f"{key}: MISSING (see {log_path})")
        else:
            print(f"{key}: {summary['passed']} passed, {summary['failed']} failed. {summary['status']}")
    if args.mode == "combined":
        print(f"A07SelfTest: {'BOTH SUITES PASS' if combined_ok else 'FAILURES PRESENT'}")
    print(f"Result: {'PASS' if passed else 'FAIL'}" + ("" if suites_ok else f" ({verdict_note})"))
    print(f"Log: {log_path}")

    if args.json:
        print(json.dumps({
            "mode": args.mode,
            "command": command,
            "returncode": returncode,
            "timed_out": timed_out,
            "summaries": summaries,
            "failure_lines": failure_lines[:20],
            "result": "PASS" if passed else "FAIL",
            "log": str(log_path),
        }, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
