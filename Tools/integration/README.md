# Integration smoke harness

Owner: **A10 Gatekeeper**.

`run_smoke.py` is the one command a lane runs before handing off and A10 runs at
every merge gate. It always starts with the Python validator; Unreal steps are
opt-in because they launch the editor headless.

## Quick start

```powershell
# Data/contract validation only (works without Unreal)
python Tools\integration\run_smoke.py --validate

# Validator + the existing -DADuelSelfTest smoke
python Tools\integration\run_smoke.py --validate --duel-selftest

# Four stable headless self-tests (duel, profile, rules, economy)
python Tools\integration\run_smoke.py --self-tests

# Opening story self-test (explicit; the editor harness may stay open)
python Tools\integration\run_smoke.py --story-selftest

# A07: authored puzzle replays + 12 exam cycles in one headless process
python Tools\integration\run_smoke.py --a07-selftest
python Tools\integration\run_smoke.py --puzzle-selftest
python Tools\integration\run_smoke.py --exam-selftest

# Full gate: validator + self-tests + A07 puzzle/exam suites + automation tests
python Tools\integration\run_smoke.py --all --automation-filter DuelAcademy

# Print commands without launching anything
python Tools\integration\run_smoke.py --all --dry-run
```

Reports and logs land in `Docs/Integration/reports/`:

```text
reports/
├─ validate-<run>.json
├─ smoke-<run>.json
├─ automation/
└─ logs/
   ├─ validate-<run>.log
   ├─ duel-selftest-<run>.log
   └─ automation-<run>.log
```

`<run>` is `YYYYMMDD-HHMMSS-ffffff-PID-N`, so two runs in the same second (or
two processes, or two steps in one process) cannot overwrite each other.
`--report PATH` overrides the smoke report path and `--validate-report PATH`
overrides the validator report; relative values for `--report`,
`--validate-report`, `--report-dir` and
`--uproject` resolve against the **current directory**. This changed in pass 2:
`--report`/`--validate-report` used to resolve against the repository root.
Running the commands below from the repository root is unchanged.

`--timeout N` sets the per-step timeout (default 1800 s). A timed-out step is
killed as a process tree: `taskkill /T` on Windows and the child process group
on POSIX. This matters because `UnrealEditor-Cmd` can leave helper processes
alive when only the direct child is killed.

`UE_EDITOR` or `--ue-editor` selects the editor executable; the default is
`C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe`.

Generated `logs/*.log` and `smoke*.json` / `validate*.json` files are ignored by
Git. Curated gate evidence (`GATE*_TEST_RESULTS.md`, `smoke_selftests.json`,
`validate_baseline.json`, `validate_strict.json`, and the tracked reference
logs) stays in the repository; use `git add -f` when a new artifact becomes
curated evidence.

## Exact commands

### 1. Python validator

```powershell
python Tools\validate\validate_all.py
python Tools\validate\validate_all.py --strict
python Tools\validate\validate_all.py --json --report Docs\Integration\reports\validate.json
```

`--strict` promotes known gaps and warnings to failures. Use baseline mode for
early lanes and strict mode at a content gate.

### 2. Duel self-test

Counted C++ switch (default 24; release gate uses 1000):

```powershell
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
  "C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  -game -nullrhi -nosound -unattended -nop4 -DADuelSelfTest=1000 `
  -log -stdout -FullStdOutLogOutput
```

The log must contain a line like:

```text
Duel self-test: 1000 iterations, N player wins, M opponent wins, 0 stalls, average turns X, invariant failures 0, gate deck failures 0, deck audit 6/36, puzzle audit 100/100, elapsed Xs, RESULT PASS
```

The runner fails the step if `stalls` is greater than zero or the summary contains
`RESULT FAIL`. `--iterations N` is passed through as `-DADuelSelfTest=N`;
the bare `-DADuelSelfTest` token still runs the legacy 24-duel HUD path.

There is also a console command once a world is loaded:

```text
da.DuelSelfTest 1000
```

It is clamped to 500 per call in the current implementation and is intended for
PIE/console use, not the headless switch.

### 3. A07 puzzle/exam self-tests

```powershell
python Tools\puzzles\run_engine_selftests.py
python Tools\puzzles\run_engine_selftests.py --mode puzzles
python Tools\puzzles\run_engine_selftests.py --mode exams
```

The dedicated runner and the `run_smoke.py --a07-selftest` wrapper launch
`UnrealEditor-Cmd` with `-DAPuzzleExamSelfTest`, `-DAPuzzleSelfTest` or
`-DAExamSelfTest`. The log must contain:

```text
PuzzleSelfTest: 102 passed, 0 failed. ALL PASS
ExamSelfTest: <N> passed, 0 failed. ALL PASS
A07SelfTest: BOTH SUITES PASS
```

`--a07-selftest` is the combined single-process gate command. It also drives
the 12 authored `Exams/exams.json` cycles through `UDAExamSubsystem`, including
the actual timed-puzzle solve. See `Docs/Puzzles/PUZZLE_ENGINE_TESTS.md`.

### 4. Unreal automation tests

```powershell
"C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" `
  "C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  "-ExecCmds=Automation RunTests DuelAcademy; Quit" `
  "-ReportExportPath=C:\dev\GX\Docs\Integration\reports\automation" `
  -unattended -nop4 -nullrhi -nosound -log -stdout -FullStdOutLogOutput
```

Do not add `-game` to the automation command: the current editor target then
reports "The game module 'DuelAcademyIsland' could not be found". `-TestExit`
is also omitted; `Quit` and the runner's log inspection are enough. Unreal treats
an empty filter as a critical error and exits non-zero, so the runner treats
"No automation tests matched" as a skip **only when the same log also contains a
`TEST COMPLETE` marker and no failed-test marker**. A timeout or interrupted run
without the completion marker stays failed even if its partial log contains a
no-tests sentence. A normal successful run must log
`TEST COMPLETE. EXIT CODE: 0`; a missing marker or a nonzero `EXIT CODE` on a
run that actually executed tests fails.

No `IMPLEMENT_SIMPLE_AUTOMATION_TEST` suites exist in the baseline yet. The
runner reports `skip` on a completed empty-filter run (including Unreal's
non-zero `-1` exit). Lane owners should add
tests under their own module/unit names and give A10 the filter string:

- A02 `DuelAcademy.Profile`, `DuelAcademy.Calendar`, `DuelAcademy.Save`
- A03 `DuelAcademy.Story`
- A04 `DuelAcademy.DuelRules`
- A05 `DuelAcademy.Effects`
- A06 `DuelAcademy.Economy`
- A07 `DuelAcademy.Opponents`, `DuelAcademy.Puzzles`, `DuelAcademy.Exams`
- A08 `DuelAcademy.World`
- A09 `DuelAcademy.UI`

### 5. Package (release gate, A10 only)

```powershell
"C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\RunUAT.bat" BuildCookRun `
  -project="C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  -noP4 -platform=Win64 -clientconfig=Shipping `
  -cook -build -stage -pak -archive `
  -archivedirectory="C:\dev\GX\Build"
```

## Harness tests

The runner's pure helpers (log parsing, step planning, report paths, timeout
handling) and a real child-process tree fixture have stdlib-only unit tests:

```powershell
python -m unittest discover -s Tools/tests -v
```

The suite does not need Unreal or a renderer. It covers failed/timed-out steps
that must not be upgraded by a `PASS` line, missing/zero-check/malformed
self-test summaries, automation no-tests vs. crashes, missing automation
completion markers, relative report paths, and whole-tree termination of a
fixture that spawns a long-lived grandchild. CI runs the same command on
ubuntu-latest plus `run_smoke.py --validate` and `--all --dry-run`.

## Gate workflow

1. Lane runs `python Tools\integration\run_smoke.py --validate` and attaches the
   summary/report to its handoff.
2. A10 runs the same command plus `--duel-selftest` and the lane's automation
   filter.
3. At a gate, A10 runs `--all` and `--validate --strict`; strict failures become
   blockers owned by the named lane.
4. No lane changes `Tools/integration/**` or `Tools/validate/**` without A10.

## Current limitations

- All four stable headless self-tests pass: duel 24/0 stalls, profile PASS,
  duel rules 102/102, economy 446/446. A07 reports puzzles 105/105 and exams
  104/104, A03's full-campaign playthrough passes, A09 generated 10 UI
  screenshots, and the `DuelAcademy` automation filter runs 5 tests.
- The duel self-test defaults to 24 duels; pass `--iterations 1000` (or
  `-DADuelSelfTest=1000`) for the release proof. The 1,000-duel gate evidence is
  in `Docs/PORT_STATUS.md` and `Docs/Integration/reports/GATE3_TEST_RESULTS.md`.
- The `DuelAcademy` automation filter currently runs 5 tests (exam cycles,
  exam scoring, opponent roster, puzzle level 1 and the puzzle runtime loader).
- The runner does not package; the BuildCookRun command above is the release
  command, run manually by A10.
- The runner never downloads assets or starts the editor GUI.
