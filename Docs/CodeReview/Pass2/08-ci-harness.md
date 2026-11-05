# 08 — CI & integration harness (pass 2)

Branch: `refactor/code-review-pass`

Scope: `.github/workflows/ci.yml`, `.gitignore`, `Tools/integration/**`,
`Tools/tests/test_run_smoke.py`, `Docs/Integration/README.md`, this report.
The uncommitted pass-1 changes were treated as the baseline. No C++ runtime,
game data, other `Tools` packages, or other workstream reports were edited.

Constraints honoured: UnrealBuildTool and UnrealEditor were not launched. Smoke
artifacts were written only to `%TEMP%` and removed. The harness still works with
no Unreal install (`--dry-run`, `--validate`).

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| F1 | High | `run_smoke.py`, old `_inspect_automation` (363-372) | Any log text `"No automation tests matched"`, `"No tests found"` or `"0 tests"` set the step to `skip` regardless of the process result. A crashed or timed-out automation run whose partial log contained one of those phrases still produced overall `PASS`. | Fixed |
| F2 | High | `run_smoke.py`, old `_inspect_a07_selftest` (341-360) | `A07SelfTest: BOTH SUITES PASS` plus any suite marker was accepted without checking the per-suite counts. `PuzzleSelfTest: 100 passed, 1 failed.` was therefore masked by the final marker; `0 passed, 0 failed` suites also passed. | Fixed |
| F3 | Medium | `run_smoke.py`, old `_run_step` (154-203) | `subprocess.run(timeout=…)` kills only the direct child. A timed-out `UnrealEditor-Cmd` can leave editor helpers alive and holding the captured pipes. Pass-1 follow-up #1. | Fixed |
| F4 | Low | `run_smoke.py`, old `main` (490-492, 558-560) | `--report`/`--validate-report` resolved relative paths against the repository root while `--report-dir` and `--uproject` used the current directory. Pass-1 follow-up #3. | Fixed |
| F5 | Low | `run_smoke.py`, old `_now_slug` (114-115) | One-second resolution allowed log/report filename collisions. Pass-1 follow-up #4. | Fixed |
| F6 | Low | `run_smoke.py`, old `_inspect_named_selftest` (308-338); `_inspect_automation` (363-372) | A named suite reporting `0 passed, 0 failed` was a pass, and a successful automation run without a `TEST COMPLETE` marker was a pass. Missing/malformed output is now a failure. | Fixed |
| F7 | Low | `.gitignore`; `Docs/Integration/reports/**` | Generated logs and `smoke-*.json` / `validate-*.json` dirtied `git status`; curated evidence had no explicit exclusion rule. Pass-1 follow-up #2. | Fixed |
| F8 | Low | `.github/workflows/ci.yml` | CI ran the data contract, puzzle, opponent and effects gates but not `Tools/economy/validate_decks.py`, `validate_packs.py`, `Tools/world/validate_layout.py`, `test_interiors.py`, or the harness itself. | Fixed |
| F9 | Low | `Tools/integration/README.md`; `Docs/Integration/README.md` | Stale counts (duel rules 57/57, economy 119/119), no path-resolution rule, no description of the new process-tree/automation behaviour, and the old "no-tests is always a skip" wording. | Fixed |
| F10 | Info | `Tools/canon/validate_canon.py` | Fails locally with 3 errors: `cards_manifest.json` and `exams.json` manifest hashes no longer match, plus `manifest.hashes`. The script also rewrites `Docs/Canon/VALIDATION.md`. It is **not** a safe CI gate until the canon owner regenerates the manifest; the generated report write from inspection was reverted. | Open (owned by canon/data workstream) |

## Changes

### Process-tree timeout (`Tools/integration/run_smoke.py`)

- `_run_step` now uses `subprocess.Popen` plus `communicate(timeout=…)` instead
  of `subprocess.run(timeout=…)`.
- `_popen_tree_kwargs()` starts the step in a killable unit:
  `CREATE_NEW_PROCESS_GROUP` on Windows and `start_new_session=True` (POSIX
  session/process-group leader).
- `_terminate_process_tree(proc)` uses `taskkill /F /T /PID` on Windows (falling
  back to `proc.kill()` if the utility is unavailable) and
  `os.killpg(SIGTERM)` → grace → `os.killpg(SIGKILL)` on POSIX.
- After termination the runner reaps the process and drains stdout/stderr; the
  timeout log still contains the command, timeout value and partial output.
- Log formatting is shared through `_format_step_log`; missing-executable and
  cannot-execute paths use the same format.

### Report/log hygiene

- `_now_slug()` is now `YYYYMMDD-HHMMSS-ffffff-PID-N` (microseconds, process id
  and an in-process sequence), eliminating same-second overwrites.
- `--report`, `--validate-report`, `--report-dir` and `--uproject` all resolve
  relative paths against the **current directory** through `_resolve_cli_path`.
  This is an intentional change from repository-root resolution for
  `--report`/`--validate-report`; the documented gate commands run from the
  repository root and are unchanged. `_report_path` centralises the explicit vs.
  default report path logic.
- `.gitignore` now ignores generated `Docs/Integration/reports/logs/*.log`,
  `reports/automation/`, `reports/smoke*.json` and `reports/validate*.json`,
  while re-including `smoke_selftests.json`, `validate_baseline.json` and
  `validate_strict.json`. Already-tracked evidence stays tracked; new curated
  artifacts can be force-added.

### Parser robustness

- `_inspect_named_selftest`: a `0 passed, 0 failed` summary is a failure
  (`0 checks reported`); missing/malformed summaries still fail a passing step.
- `_inspect_a07_selftest`: both suite summaries must be present, each must
  report at least one check, per-suite `failed` counts must be zero, and
  `A07SelfTest: BOTH SUITES PASS` is required.
- `_inspect_automation`:
  - failure markers (`Automation Test Failed`, `Result: Failed`) always win;
  - a nonzero `TEST COMPLETE. EXIT CODE: N` fails a run that executed tests;
  - a no-tests phrase becomes `skip` only when the step did not time out
    (`returncode is not None`), the same log contains a `TEST COMPLETE` marker,
    and no failed-test marker was seen. Without the completion marker the step
    fails. Unreal exits `-1`/255 for an empty filter, so this preserves the
    documented skip while rejecting timeouts and interrupted/crashed runs;
  - a normal successful run must log `TEST COMPLETE. EXIT CODE: 0`, otherwise
    it fails with a missing-marker note; a negative completion code is parsed
    and fails unless it is the no-tests path above;
  - the no-tests regex was narrowed so `0 tests failed` is not mistaken for an
    empty suite.
- `_run_and_inspect` and `_report_path` remove the duplicated step-run/report
  blocks in `main`.

### CI (`.github/workflows/ci.yml`)

- Added separate gates for `Tools/economy/validate_decks.py` (81 checks) and
  `validate_packs.py` (1,342 checks).
- Added `Tools/world/validate_layout.py` and `Tools/world/test_interiors.py`;
  the latter skips the Blender mesh phase when `bpy` is absent.
- Added an integration-harness step that runs the real validator through
  `run_smoke.py --validate` and the no-Unreal `--all --dry-run` planner, with
  all artifacts under `$RUNNER_TEMP`.
- Kept actions pinned, checkout non-persistent, the 10-minute job ceiling, and
  the existing compileall/unit-test/data/effects gates. No Unreal or renderer is
  required.

### Tests (`Tools/tests/test_run_smoke.py`)

`Tools/tests/test_run_smoke.py` now has 52 stdlib `unittest` cases (was 30).
New coverage:

- real timeout fixture that prints partial stdout/stderr;
- real child-process fixture that spawns a long-lived grandchild, writes its
  PID, and must be dead after a timed-out `_run_step` (no Unreal required);
- platform-specific `_popen_tree_kwargs`;
- zero-check and malformed named summaries; failed/timed-out steps are not
  upgraded by a pass summary;
- A07 failed counts, malformed summaries, all-empty and one-empty suites;
- automation no-tests vs. nonzero exit/timeout, the real empty-filter
  `TEST COMPLETE. EXIT CODE: -1` skip, no-tests without a completion marker
  failing, no-tests plus completion still not masking a timeout, failed markers
  beating no-tests text, missing completion marker, nonzero/negative completion
  code, `0 tests failed` not being a skip;
- relative report/validate-report/report-dir paths resolving against the
  current directory;
- slug format/uniqueness and default report path construction.

### Documentation

- `Tools/integration/README.md`: `<run>` naming, CWD-relative path rule,
  process-tree timeout behaviour, generated-artifact ignore rules, accurate
  automation skip/completion semantics, 52-case harness description, corrected
  economy 213/213 and duel rules 58/58 counts.
- `Docs/Integration/README.md`: ignore/curation rules, current-directory path
  semantics, duel rules 58/58, economy 213/213, state date 2026-10-31.

## Verification

Environment: Windows, Python 3.14.6 and 3.12.10. All commands were run from
`C:\dev\GX` unless noted. Unreal/UBT were not launched.

| Command | Result |
|---|---|
| `python -m compileall -q Tools DuelAcademyIsland/Content/Python` | exit 0 |
| `python -m unittest Tools.tests.test_run_smoke -v` | **52 harness tests, OK**, exit 0, 6.4 s |
| `python -m unittest discover -s Tools/tests -v` | **71 tests, OK** (52 harness + concurrently expanded pipeline tests), exit 0 |
| `py -3.12 -m unittest discover -s Tools/tests` | **71 tests, OK**, exit 0 |
| `python Tools/integration/run_smoke.py --validate --report-dir %TEMP%\…` | **PASS**, exit 0, ~0.8 s; report/validator JSON/log only in temp |
| `python Tools/integration/run_smoke.py --all --dry-run --report-dir %TEMP%\…` | exit 0; 7 planned steps, all `skip`, commands populated |
| Same command from `%TEMP%` with relative `reports`, `out/smoke.json`, `out/validate.json` | exit 0; files created under the current directory, not the repo root |
| `python Tools/economy/validate_decks.py` | **PASS** — 81 checks, 0 failures |
| `python Tools/economy/validate_packs.py` | **PASS** — 1,342 checks, 0 failures |
| `python Tools/world/validate_layout.py` | **PASS** — 17 zones, 36 locations, 10 interiors, 20 portals |
| `python Tools/world/test_interiors.py` | **PASS** — 10 portal routes; Blender mesh phase correctly skipped without `bpy` |
| YAML parse of `ci.yml` | valid; 15 steps |
| `git check-ignore` generated vs. curated paths | generated log/JSON ignored; curated JSON and `GATE*_TEST_RESULTS.md` not ignored |
| `git diff --check` on changed tracked files | exit 0 (only line-ending conversion warnings from the global checkout config) |
| `git status --short` | only intended harness/CI/docs files and the pre-existing pass-1 tree |

The process-tree fixture was exercised on Windows (`taskkill /T` path). The
POSIX `killpg` branch cannot run on this host; the same test runs on the
Ubuntu CI job. GitHub Actions itself was not executed locally.

## Remaining risks / follow-ups

1. **Windows Job Object vs. taskkill:** `taskkill /T` is a best-effort tree kill.
   If `taskkill` is unavailable or denied, the fallback kills only the direct
   child. A Job Object with kill-on-close would be stronger but needs Windows
   API plumbing and a real editor run to justify.
2. **POSIX branch verification:** the `killpg` path has unit coverage only via
   the future ubuntu CI run, not on this Windows host.
3. **Automation marker assumption:** the parser requires
   `TEST COMPLETE. EXIT CODE: N` for both success and the no-tests skip. If a
   future UE version/filter changes that marker, automation runs fail closed
   (safe but noisy) until the parser is updated.
4. **No-tests text remains heuristic:** `"No tests found"` from an unrelated
   subsystem in a log that also has `TEST COMPLETE` would still produce `skip`.
   The regex is narrower but not log-category-aware.
5. **No-tests is still an overall PASS:** a completed empty-filter run is
   intentionally `skip` (Unreal exits `-1`/255), even though the process return
   code is nonzero. This preserves the documented harness contract but means a
   filter typo is not a merge-gate failure. A future `--strict` automation mode
   could turn that skip into a failure once suites exist.
6. **`validate_canon.py` is still not in CI:** it fails on stale manifest hashes
   for `cards_manifest.json` and `exams.json`. This should be fixed by the canon
   owner; adding it now would make CI red for data unrelated to the harness.
7. **Path semantics change:** external scripts that passed a relative
   `--report`/`--validate-report` while running outside the repository root now
   write relative to their current directory instead of the repository root.
   This is documented as intentional.
8. **Existing tracked logs:** `.gitignore` does not untrack already-committed
   reference logs; it only prevents new generated logs from being added
   accidentally.
9. **No Unreal validation of the timeout path:** the fixture proves the tree
   kill logic, but a real `UnrealEditor-Cmd` timeout remains a parent-session
   gate item (it requires an editor launch, which this pass deliberately avoids).
