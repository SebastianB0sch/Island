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
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_UPROJECT = ROOT / "DuelAcademyIsland" / "DuelAcademyIsland.uproject"
DEFAULT_UE_EDITOR = Path(r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")
MODES = {
    "puzzles": "-DAPuzzleSelfTest",
    "exams": "-DAExamSelfTest",
    "combined": "-DAPuzzleExamSelfTest",
}


def _now_slug() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def _resolve_editor(explicit: str) -> Path | None:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("UE_EDITOR") or os.environ.get("UNREAL_EDITOR")
    if env:
        return Path(env).expanduser().resolve()
    if DEFAULT_UE_EDITOR.exists():
        return DEFAULT_UE_EDITOR
    return None


def _parse_summaries(text: str) -> dict[str, dict[str, int | str]]:
    result: dict[str, dict[str, int | str]] = {}
    pattern = re.compile(r"(PuzzleSelfTest|ExamSelfTest): (\d+) passed, (\d+) failed\.\s*(ALL PASS|FAILURES PRESENT)")
    for match in pattern.finditer(text):
        result[match.group(1)] = {
            "passed": int(match.group(2)),
            "failed": int(match.group(3)),
            "status": match.group(4),
        }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run A07 puzzle/exam in-engine self-tests.")
    parser.add_argument("--mode", choices=sorted(MODES), default="combined")
    parser.add_argument("--ue-editor", default="", help="path to UnrealEditor-Cmd.exe (or set UE_EDITOR)")
    parser.add_argument("--uproject", default=str(DEFAULT_UPROJECT))
    parser.add_argument("--timeout", type=int, default=1800, help="process timeout in seconds")
    parser.add_argument("--log", default="", help="log path (default: Docs/Integration/reports/logs/...)")
    parser.add_argument("--json", action="store_true", help="print a JSON result")
    args = parser.parse_args(argv)

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

    command = [
        str(editor),
        str(uproject),
        "-game",
        "-nullrhi",
        "-nosound",
        "-unattended",
        "-nop4",
        MODES[args.mode],
        "-log",
        "-stdout",
        "-FullStdOutLogOutput",
    ]
    started = _dt.datetime.now(_dt.timezone.utc)
    try:
        completed = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=args.timeout,
        )
        returncode: int | None = completed.returncode
        output = f"--- stdout ---\n{completed.stdout}\n\n--- stderr ---\n{completed.stderr}\n"
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        returncode = None
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        output = f"TIMEOUT after {args.timeout}s\n\n{stdout}\n\n{stderr}\n"
        timed_out = True
    except OSError as exc:
        print(f"error: cannot execute {editor}: {exc}", file=sys.stderr)
        return 2

    log_path.write_text(
        f"COMMAND: {subprocess.list2cmdline(command)}\n"
        f"STARTED: {started.isoformat()}\n"
        f"RETURNCODE: {returncode if returncode is not None else 'timeout'}\n\n{output}",
        encoding="utf-8",
    )

    text = log_path.read_text(encoding="utf-8", errors="replace")
    summaries = _parse_summaries(text)
    failure_lines = [line.strip() for line in text.splitlines() if line.strip().startswith("FAIL:")]
    combined_ok = "A07SelfTest: BOTH SUITES PASS" in text
    required = ["PuzzleSelfTest", "ExamSelfTest"] if args.mode == "combined" else (
        ["PuzzleSelfTest"] if args.mode == "puzzles" else ["ExamSelfTest"]
    )
    suites_ok = all(
        key in summaries and summaries[key]["failed"] == 0 and summaries[key]["status"] == "ALL PASS"
        for key in required
    )
    passed = returncode == 0 and not timed_out and suites_ok and not failure_lines
    if args.mode == "combined":
        passed = passed and combined_ok

    for key in required:
        summary = summaries.get(key)
        if summary is None:
            print(f"{key}: MISSING (see {log_path})")
        else:
            print(f"{key}: {summary['passed']} passed, {summary['failed']} failed. {summary['status']}")
    if args.mode == "combined":
        print(f"A07SelfTest: {'BOTH SUITES PASS' if combined_ok else 'FAILURES PRESENT'}")
    print(f"Result: {'PASS' if passed else 'FAIL'}")
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
