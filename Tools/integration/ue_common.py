"""Shared helpers for the headless Unreal runners.

Used by Tools/integration/run_smoke.py and Tools/puzzles/run_engine_selftests.py:
editor resolution, the headless command line, and one strict parser for the
in-engine self-test summaries. A self-test only passes when its summary line is
present and reports zero failures; a log without a summary is a failure (a
misspelled switch or a crash before the test ran must not read as green).
"""

from __future__ import annotations

import datetime as _dt
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Tools/, for the shared common package
from common.paths import REPO_ROOT, UPROJECT  # noqa: E402

ROOT = REPO_ROOT
DEFAULT_UPROJECT = UPROJECT
DEFAULT_UE_EDITOR = Path(r"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe")

# Launch switch for each self-test kind.
SELFTEST_SWITCHES = {
    "duel": "-DADuelSelfTest",
    "profile": "-DAProfileSelfTest",
    "duelrules": "-DADuelRulesSelfTest",
    "economy": "-DAEconomySelfTest",
    "story": "-DAStorySelfTest",
    "puzzle": "-DAPuzzleSelfTest",
    "exam": "-DAExamSelfTest",
    "a07": "-DAPuzzleExamSelfTest",
}

_SUITE_RE = re.compile(
    r"(PuzzleSelfTest|ExamSelfTest): (\d+) passed, (\d+) failed\.\s*(ALL PASS|FAILURES PRESENT)"
)
_DUEL_RE = re.compile(r"Duel self-test: (\d+) iterations,.*?(\d+) stalls[^\n]*")
_DUELRULES_RE = re.compile(r"Duel rules self-test: (\d+) passed, (\d+) failed\.\s*(ALL PASS|FAILURES PRESENT)")
_ECONOMY_RE = re.compile(r"DAEconomySelfTest: (\d+) passed, (\d+) failed\.")
_PROFILE_RE = re.compile(r"DAProfileSelfTest (PASSED|FAILED)\.")
_STORY_SUMMARY_RE = re.compile(r"StorySelfTest: (PASS|FAIL) in [\d.]+s")


def now_slug() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def resolve_editor(explicit: str = "") -> Path | None:
    """--ue-editor, then UE_EDITOR / UNREAL_EDITOR, then the default install path."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("UE_EDITOR") or os.environ.get("UNREAL_EDITOR")
    if env:
        return Path(env).expanduser().resolve()
    if DEFAULT_UE_EDITOR.exists():
        return DEFAULT_UE_EDITOR
    return None


def headless_game_command(editor: Path, uproject: Path, *switches: str) -> list[str]:
    """`UnrealEditor-Cmd <uproject> -game` with no RHI/sound, logging to stdout."""
    return [
        str(editor),
        str(uproject),
        "-game",
        "-nullrhi",
        "-nosound",
        "-unattended",
        "-nop4",
        *switches,
        "-log",
        "-stdout",
        "-FullStdOutLogOutput",
    ]


def parse_suite_summaries(text: str) -> dict[str, dict[str, int | str]]:
    """A07 suite summaries: {"PuzzleSelfTest": {"passed", "failed", "status"}, ...} (last one wins)."""
    result: dict[str, dict[str, int | str]] = {}
    for match in _SUITE_RE.finditer(text):
        result[match.group(1)] = {
            "passed": int(match.group(2)),
            "failed": int(match.group(3)),
            "status": match.group(4),
        }
    return result


def _suite_ok(summaries: dict, key: str) -> bool:
    summary = summaries.get(key)
    return bool(summary) and summary["failed"] == 0 and summary["status"] == "ALL PASS"


def selftest_verdict(kind: str, text: str) -> tuple[bool, str]:
    """Judge a self-test log. Returns (passed, note); a missing summary is a failure."""
    if kind == "duel":
        matches = list(_DUEL_RE.finditer(text))
        if not matches:
            return False, "summary line missing ('Duel self-test: ...')"
        line = matches[-1].group(0).strip()
        stalls = int(matches[-1].group(2))
        invariant = re.search(r"invariant failures (\d+)", line)
        if stalls > 0:
            return False, f"{line} (stalls > 0)"
        if invariant and int(invariant.group(1)) > 0:
            return False, f"{line} (invariant failures > 0)"
        if "RESULT FAIL" in line:
            return False, line
        return True, line

    if kind == "profile":
        for marker in ("[FAIL]", "Assertion failed"):
            bad = next((ln.strip() for ln in text.splitlines() if marker in ln), None)
            if bad:
                return False, bad
        matches = list(_PROFILE_RE.finditer(text))
        if not matches:
            return False, "summary line missing ('DAProfileSelfTest PASSED.')"
        return matches[-1].group(1) == "PASSED", matches[-1].group(0)

    if kind in ("duelrules", "economy"):
        pattern = _DUELRULES_RE if kind == "duelrules" else _ECONOMY_RE
        matches = list(pattern.finditer(text))
        if not matches:
            return False, f"summary line missing ('{pattern.pattern.split(':')[0]}: N passed, M failed.')"
        match = matches[-1]
        ok = int(match.group(2)) == 0 and (kind == "economy" or match.group(3) == "ALL PASS")
        return ok, match.group(0)

    if kind == "story":
        failed = next((ln.strip() for ln in text.splitlines() if "StorySelfTest: FAIL" in ln), None)
        matches = list(_STORY_SUMMARY_RE.finditer(text))
        if not matches:
            return False, failed or "summary line missing ('StorySelfTest: PASS in ...s')"
        if failed or matches[-1].group(1) != "PASS":
            return False, failed or matches[-1].group(0)
        return True, matches[-1].group(0)

    if kind in ("puzzle", "exam", "a07"):
        summaries = parse_suite_summaries(text)
        required = {"puzzle": ["PuzzleSelfTest"], "exam": ["ExamSelfTest"]}.get(kind, ["PuzzleSelfTest", "ExamSelfTest"])
        missing = [key for key in required if key not in summaries]
        if missing:
            return False, f"summary line missing for {', '.join(missing)}"
        fail_lines = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("FAIL:")]
        if fail_lines:
            return False, fail_lines[0]
        if not all(_suite_ok(summaries, key) for key in required):
            bad = next(key for key in required if not _suite_ok(summaries, key))
            s = summaries[bad]
            return False, f"{bad}: {s['passed']} passed, {s['failed']} failed. {s['status']}"
        if kind == "a07":
            if "A07SelfTest: BOTH SUITES PASS" not in text:
                return False, "A07SelfTest combined summary missing or FAILURES PRESENT"
            return True, "A07SelfTest: BOTH SUITES PASS"
        s = summaries[required[0]]
        return True, f"{required[0]}: {s['passed']} passed, {s['failed']} failed. {s['status']}"

    raise ValueError(f"unknown self-test kind: {kind}")


_AUTOMATION_FOUND_RE = re.compile(r"Found (\d+) automation tests?", re.I)


def automation_verdict(text: str, returncode: int | None) -> tuple[str, str]:
    """Judge an `Automation RunTests` log. Returns (status, note); status is pass or fail."""
    failures = [ln.strip() for ln in text.splitlines() if "Automation Test Failed" in ln or "Result: Failed" in ln]
    if failures:
        return "fail", failures[0]
    if "No automation tests matched" in text or any(int(m.group(1)) == 0 for m in _AUTOMATION_FOUND_RE.finditer(text)):
        # Unreal itself exits non-zero here; a filter that runs nothing is not a pass.
        return "fail", "no automation tests matched the filter"
    if "**** TEST COMPLETE. EXIT CODE: 0 ****" in text:
        return "pass", "automation completed with exit code 0"
    if returncode == 0:
        return "pass", ""
    return "fail", f"exit code {returncode}"
