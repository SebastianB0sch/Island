# 06 — CI & integration harness

Branch: `refactor/code-review-pass`

Scope: `.github/workflows/ci.yml`, `Tools/integration/**`, new
`Tools/tests/**`, this report. No C++, game data, `Tools/validate`,
`Tools/effects`, or other pipeline files were changed.

## Summary

CI previously checked only merge markers, `compileall`, and two JSON globs. The
repository's real validators were never run, so a PR could pass CI while
`validate_all.py`, the puzzle/exam validator, or the effects validator failed.

CI now runs, on `ubuntu-latest` with Python 3.13:

1. merge-marker and compile checks (kept);
2. the new stdlib unit tests for the integration harness;
3. `Tools/validate/validate_all.py` in baseline mode;
4. `Tools/puzzles/validate.py`;
5. `Tools/opponents/import_canon_decks.py --check` (added during integration,
   after the missing `sheppard_year1` mapping was fixed);
6. `Tools/effects/validate_effects.py` and the read-only
   `Tools/effects/test_effects.py` regression suite;
7. the existing JSON parse check.

All actions are pinned to commit SHAs, the job has a 10-minute ceiling, and
checkout no longer persists credentials. No secrets, Windows-only tools, Unreal
launches, or local assets are required.

Reviewing `run_smoke.py` found a real merge-gate hazard: log inspection could
turn a failed, timed-out, or partially completed run into `PASS` (story per-check
lines, profile `[FAIL]` lines, and the automation "EXIT CODE: 0" fallback). The
parser was split into focused helpers that only ever downgrade a step, require
the final suite summary, and preserve the subprocess return code. `--dry-run`
also produced empty/blocked commands when no editor was installed; it now plans
all commands without requiring a real editor or project.

## Findings

| ID | Severity | Location | Finding |
|---|---|---|---|
| F1 | High | `Tools/integration/run_smoke.py:308-393` (old `_inspect_log` 228-325) | Log inspection could mark a failed step as pass. The named-selftest loop broke on the first `PASS` line, so `story-selftest` per-check `StorySelfTest: PASS …` lines masked later failures; a profile `[FAIL]` line was overwritten by a later `PASSED` summary; `TEST COMPLETE. EXIT CODE: 0` flipped a nonzero return code to pass; timeout/blocked steps were inspected too. |
| F2 | High | `.github/workflows/ci.yml:30-38` (old 20-38) | CI did not run `validate_all.py`, `Tools/puzzles/validate.py`, or `Tools/effects/validate_effects.py`; only syntax/JSON checks existed. |
| F3 | Medium | `Tools/integration/run_smoke.py:474-481` (old 389-392, 455-458, 473-474) | `--dry-run` still required the project to exist and only used the default editor if it existed, so `--all --dry-run` on a clean Linux/Windows box reported blocked steps with empty commands. |
| F4 | Medium | `Tools/integration/run_smoke.py:474-477` (old 389-390) | The uproject existence check covered only duel/puzzle/exam/A07/automation. `--profile-selftest`, `--duelrules-selftest`, `--economy-selftest`, `--story-selftest`, and `--self-tests` could launch Unreal against a missing project. |
| F5 | Medium | `Tools/integration/run_smoke.py:172-199` (old 142-148) | Timeout logs contained only partial output: no command, no timeout value, and byte output was discarded. `FileNotFoundError`/`OSError` left `step.log` pointing at a file that was never written. |
| F6 | Low | `Tools/integration/run_smoke.py:454, 490-492, 558-560` | Relative path semantics differ: `--report-dir` resolves against the current directory, while `--report`/`--validate-report` resolve against the repository root. Running from outside the root can put reports in surprising places. |
| F7 | Low | `.github/workflows/ci.yml:18-21` | Actions used floating major tags (`@v4`, `@v5`) and checkout persisted the workflow token in `.git/config`. |
| F8 | Low | `Tools/integration/README.md:147, 178-185` | Stale docs: two sections numbered `4`, a claim that the duel self-test always runs 24 duels (it supports `-DADuelSelfTest=N` and `--iterations`), and duel rules listed as 57/57 versus 58/58 in current evidence. |
| F9 | Low | `Tools/integration/run_smoke.py:114-115` | `_now_slug()` has one-second resolution; two invocations in the same second can overwrite same-named report/log files. |
| F10 | Low | `Tools/integration/run_smoke.py:38`; `.gitignore` | Generated smoke logs/reports are not ignored, so a default `run_smoke.py` run dirties `git status` (observed pre-existing untracked `reports/logs/*.log`). |
| F11 | Info | `Tools/integration/run_smoke.py:363-372` | "No automation tests matched" sets `skip` even when the editor returned nonzero. This is documented behavior, but it hides other nonzero exits whose log happens to contain a no-tests marker. |

## Changes

### CI (`.github/workflows/ci.yml`)

- Pinned `actions/checkout` to `11d5960a326750d5838078e36cf38b85af677262`
  (`v4`) and `actions/setup-python` to
  `a26af69be951a213d495a4c3e4e4022e16d87065` (`v5`).
- Set `persist-credentials: false` on checkout.
- Added `timeout-minutes: 10`.
- Added steps for `python -m unittest discover -s Tools/tests -v`,
  `validate_all.py` (baseline), `Tools/puzzles/validate.py`,
  `Tools/opponents/import_canon_decks.py --check`,
  `Tools/effects/validate_effects.py`, and the read-only
  `Tools/effects/test_effects.py`, each as a separate named step so a failure
  points at the gate.
- Kept the existing merge-marker, compileall, and JSON checks.

### Integration harness (`Tools/integration/run_smoke.py`)

- Replaced the single log parser with focused helpers:
  `_duel_selftest_failure_reason`, `_inspect_duel_selftest`,
  `_inspect_named_selftest`, `_inspect_a07_selftest`, `_inspect_automation`,
  and `_inspect_log`.
- Log inspection now only downgrades status. It never turns `fail`, `blocked`,
  or a timeout into `pass`, even if the log contains `PASSED`/`EXIT CODE: 0`.
- Named self-tests are judged by their final summary
  (`N passed, M failed.`, `PASSED.`, `StorySelfTest: PASS in …s`), not the first
  per-check PASS line. Missing summaries fail a step that otherwise exited 0.
- Story per-check `FAIL` lines and profile `[FAIL]` lines fail the step.
- Duel parsing fails on `RESULT FAIL`, `stalls > 0`, unparsable stalls, or a
  missing summary instead of silently accepting the line.
- Timeout logs now include the command, timeout value, and partial
  stdout/stderr; missing/OSError launches write a log file with the command and
  reason.
- `_output_text()` normalises `None`/`bytes`/`str` captured output.
- `_resolve_editor(..., require_exists=False)` lets `--dry-run` plan commands
  without an installed editor; the uproject check is skipped in dry-run.
- Project existence now covers every self-test mode via `needs_project`.
- Added `_output_text`, `_duel_selftest_failure_reason`, and the parser helpers
  as pure testable units.

### Tests (`Tools/tests/test_run_smoke.py`)

30 stdlib `unittest` cases, no external dependencies:

- duel summary pass/fail/stalls/malformed/missing;
- named suite pass/fail, story per-check failure, profile `[FAIL]`, missing
  summary, failed process not upgraded;
- A07 combined pass/fail/missing suite;
- automation failure, no-tests skip, and EXIT CODE text not overriding failure;
- dry-run side-effect-free behaviour, nonzero return code, timeout log content,
  missing executable log, byte normalisation;
- command construction keeps paths with spaces as single argv entries;
- real `main()` dry-run with a missing project/editor and project-required
  validation for `--profile-selftest`;
- report result precedence.

### Docs (`Tools/integration/README.md`)

- Fixed the duplicate `### 4` (package section is now `### 5`).
- Added a "Harness tests" section with the unittest command.
- Corrected the duel self-test limitation (counted switch, default 24) and
  duel-rules count (58/58), pointing at the existing gate evidence.

## Verification

Environment: Windows, Python 3.14.6 (tests also run under 3.12). All commands
were run from `C:\dev\GX`. Unreal/UBT were not launched. Smoke artifacts were
written to `%TEMP%` and deleted.

| Command | Result |
|---|---|
| `python -m compileall -q Tools DuelAcademyIsland/Content/Python` | exit 0, ~6.4 s (cold caches) |
| `python -m unittest discover -s Tools/tests -v` | **30 tests, OK**, exit 0, 0.07 s test time |
| `py -3.12 -m unittest discover -s Tools/tests -v` | **30 tests, OK**, exit 0 |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors, 15 warnings, 6 gaps, 304 info; 420 files; ~1.0 s |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 0 failures, 1 warning; ~0.24 s |
| `python Tools/effects/validate_effects.py` | **OK** — 253 scripts, fusion 75/76, ritual 22/22, 0 warnings; ~0.55 s |
| Effects validator with `jsonschema` import blocked (fallback path) | **OK**, same counts, exit 0 |
| `python Tools/integration/run_smoke.py --validate --report-dir %TEMP%\… --report %TEMP%\…` | **PASS**, exit 0, ~1.05 s; report/log/validator JSON only in temp |
| `python Tools/integration/run_smoke.py --all --dry-run` with a fake editor and missing project | exit 0; 7 steps (`validate`, four self-tests, `a07-selftest`, `automation`), all `skip` with populated commands |
| `git grep -nI -E '^(<<<<<<< \|>>>>>>> \|=======$)' -- . ':!*.md'` | no output; exit 1 (no markers) |
| YAML parse of `ci.yml` | valid; 9 steps |
| `git status` after verification | only intended files changed; no smoke reports/logs added by this work |

The four untracked `Docs/Integration/reports/logs/*-20261031-1647/1648.log`
files predate this work and were left untouched. GitHub Actions itself was not
executed locally; the table above is the CI-equivalent command set.

## Follow-ups

1. **Timeout process tree (medium):** `subprocess.run(timeout=…)` kills the
   direct child only. On Windows, `UnrealEditor-Cmd` can leave editor children
   alive after a timeout. Move to `Popen` plus a Job Object or
   `taskkill /T` (process-group on POSIX) so a timed-out step cannot leak
   processes. Not changed here because it needs an Unreal run to validate.
2. **Report artifacts (low):** add ignore rules for generated
   `Docs/Integration/reports/logs/*.log` and ad-hoc `smoke-*.json` /
   `validate-*.json`, while keeping curated gate evidence tracked.
3. **Report path semantics (low):** make `--report`/`--validate-report` resolve
   against the current directory like `--report-dir`, or document the
   repository-root rule explicitly.
4. **Log filename collisions (low):** add PID or microsecond precision to
   `_now_slug()`.
5. **Automation no-tests handling (low):** once real suites exist, require a
   successful `TEST COMPLETE` marker and consider Unreal's `-TestExit` instead
   of treating any no-tests text plus nonzero exit as a skip.
6. **Effects schema determinism (low):** CI uses the built-in schema subset when
   `jsonschema` is absent; both paths pass today, but pinning the dependency
   would make local and CI validation identical.
7. **Strict gate:** do not add `--strict`/`--fail-on-gaps` until the 15 warnings
   and 6 content gaps are resolved; the baseline gate is intentionally
   non-strict.
8. **Opponent deck gate (fixed during integration):** the `sheppard_year1`
   runtime deck existed but was missing from the importer's `DECK_MAP`. Adding
   the mapping makes `import_canon_decks.py --check` pass, so CI now runs it as
   a separate gate.
