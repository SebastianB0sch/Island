# Puzzle and Exam Engine Self-Tests (A07 / Gate 3)

This pass adds two headless, in-engine suites so the 100 authored puzzles and
the 12 monthly exam cycles are proven through the real `FDuelEngine` and
`UDAExamSubsystem`, not only through `Tools/puzzles/validate.py`.

No UI, save, profile or story state is required. The suites create transient
objects and exit; they never launch PIE and never write a save.

## 1. Switches

| Entry point | Scope |
| --- | --- |
| `-DAPuzzleSelfTest` | Loads and replays all 100 puzzles, then exits. |
| `-DAExamSelfTest` | Runs all 12 exam cycles, then exits. |
| `-DAPuzzleExamSelfTest` | Runs both suites in one process, then exits. |
| `da.PuzzleSelfTest` | Same puzzle suite from the console; does not exit. |
| `da.ExamSelfTest` | Same exam suite from the console; does not exit. |
| `da.PuzzleExamSelfTest` | Both suites from the console; does not exit. |

Implementation:

- `Public/DAPuzzleRuntime.h`, `Private/DAPuzzleRuntime.cpp` — JSON → `FDuelScenario` loader and authored-line replay.
- `Public/DAPuzzleSelfTest.h`, `Private/DAPuzzleSelfTest.cpp` — 100-puzzle suite and the three command-line/console hooks.
- `Public/DAExamSelfTest.h`, `Private/DAExamSelfTest.cpp` — 12-cycle exam suite.
- `Private/DAExamSubsystem.cpp` — now loads `Content/Data/Exams/exams.json` and uses its authored cycle data.

## 2. Headless invocation

The dedicated A07 runner writes a full log and prints the exact summaries:

```powershell
python Tools/puzzles/run_engine_selftests.py
python Tools/puzzles/run_engine_selftests.py --mode puzzles
python Tools/puzzles/run_engine_selftests.py --mode exams
```

It resolves `UnrealEditor-Cmd.exe` from `--ue-editor`, `UE_EDITOR`,
`UNREAL_EDITOR`, or the default UE 5.8 path. The processes use
`-game -nullrhi -nosound -unattended -nop4 -log -stdout
-FullStdOutLogOutput`; this is the same headless pattern as the existing
profile/rules/economy suites.

The integration smoke runner also accepts:

```powershell
python Tools/integration/run_smoke.py --a07-selftest
python Tools/integration/run_smoke.py --puzzle-selftest
python Tools/integration/run_smoke.py --exam-selftest
```

`--a07-selftest` is the combined single-process run and is the preferred gate
command.

## 3. Expected output

Puzzle suite (all 100 pass):

```text
PASS: P001 Opening Strike: win in 1 step(s), 30ms budget
PASS: P002 Two Beats: win in 2 step(s), 45ms budget
...
PASS: P100 Special Summon L5-2: win in 4 step(s), 90ms budget
INFO: 100/100 authored puzzles won in the engine
PuzzleSelfTest: 102 passed, 0 failed. ALL PASS
```

The `102` is the number of assertions in this suite (one directory check,
100 per-puzzle checks and one unique-id check). The stable acceptance marker
is `0 failed. ALL PASS`; per-puzzle lines are deliberately explicit so a
failure names the puzzle and the first rejected step.

Exam suite (all 12 cycles pass):

```text
PASS: EXAM_01 month 1 perfect cycle: 500 / S
PASS: EXAM_01 month 1 failing mix: 120 / F / dropout
...
PASS: EXAM_12 month 12 perfect cycle: 500 / S
PASS: EXAM_12 month 12 failing mix: 120 / F / dropout
PASS: EXAM_01 partial pass: 330 / C / retain
...
ExamSelfTest: <N> passed, 0 failed. ALL PASS
```

The exam pass count is the number of individual assertions and can grow when
new assertions are added; the stable contract is the per-cycle lines plus
`0 failed. ALL PASS`.

Combined suite (both pass):

```text
PuzzleSelfTest: 102 passed, 0 failed. ALL PASS
ExamSelfTest: <N> passed, 0 failed. ALL PASS
A07SelfTest: BOTH SUITES PASS
```

Any rejected action, malformed JSON, unsupported action, early win/loss,
timer failure or unexpected score emits `FAIL:` and the process summary says
`FAILURES PRESENT`. No puzzle or cycle is skipped.

## 4. Puzzle coverage

For every `P001`..`P100` the suite:

1. Loads the JSON and checks `id`, one-turn objective, positive `seed`,
   `time_limit >= 10`, positive DP reward and `engine_ready`.
2. Builds `FDuelScenario` with the authored LP, hand, deck, graveyard, Extra
   Deck, monster positions/face-down state and Spell/Trap zones.
3. Starts the scenario and checks the authored objective, seed, turn limit,
   time limit, starting LP, board counts, first-player turn count and the
   no-first-turn-draw rule.
4. Probes the timer on a separate engine instance: it must not fire at
   `time_limit - 0.5` and must end the duel as an opponent win after
   `time_limit + 0.01`.
5. Replays every authored step through `FDuelEngine` (`normal_summon`,
   `activate_spell`, `set_spell_trap`, `activate_trap`, `change_position`,
   `attack`), requiring the player to win on the final authored step and no
   pending choice to remain.
6. Emits one PASS/FAIL line per puzzle and a `100/100` count.

The engine test is intentionally stricter than the Python simulator: it uses
the real effect runtime, automatic Trap timing (Mirror Force / Seven Tools),
battle resolution, equip bonuses and fusion/ritual paths.

## 5. Exam coverage

For every month `1..12` the suite runs two complete cycles through
`UDAExamSubsystem`:

- **Perfect cycle:** 10/10 written answers (200), the authored timed puzzle
  is selected from `exams.json` and actually solved through `FDuelEngine`
  (100), all seven practical objectives complete (200) → 500/S/pass,
  `promotion_eligible`, `promotion_candidate`, `exam_passed`,
  `practical_passed`.
- **Failing mix:** six correct and four wrong written answers (120), timed
  puzzle entered but failed (0), empty practical (0) → 120/F/fail,
  `Dropout Boy`, `dropout`, `exam_failed`, `practical_failed`,
  `dropout_boy`.

It also checks:

- the authored cycle question set, timed puzzle id and practical focus id;
- deterministic timed-puzzle selection (same input = same id);
- repeat behavior: `BeginWritten` after a result clears answers, selected
  puzzle and result while keeping the month;
- next-cycle behavior: month 12 → month 1 starts a clean written phase;
- invalid months 0 and 13 are rejected;
- a partial pass (200 written + 100 timed + one 30-point objective = 330/C,
  `retain`, `practical_failed` but `exam_passed`) to exercise the grade
  bands and independent practical flag;
- `DPReward` is carried from the cycle data. Current content has no verified
  exam DP amount, so it is 0; A02/A03 remain free to grant story DP.

## 6. Defects fixed in this pass

| Defect | Fix |
| --- | --- |
| `UDAExamSubsystem` ignored `Exams/exams.json`: every month used the formula-selected puzzle instead of the authored `timed_puzzle_id`, and cycle question sets were not the authority. | Added `FDAExamCycle`, `LoadCyclesFile`, `GetCycles`/`GetCycle`, and made `StartExam`/`PickTimedPuzzle` use the authored cycle. |
| `P015` asked the harness to `set_spell_trap` Black Pendant (an Equip Spell). A04's `SetSpellTrap` accepts only Traps and Quick-Play Spells, so the authored line could not run. | P015 now Sets `Seven Tools of the Bandit` (still two Spell/Trap cards for Mage Power, still exactly 2600 damage). This is a data workaround for the A04 API limitation; the intended rules behavior of Setting any Spell remains an A04 item. |
| `P047` ritual line had a Level 4 field body and Level 4 hand tributes. A04's ritual tribute selection is level-sorted, so the field body could be consumed and the later authored attack would have no attacker. | Replaced the field body with Level 5 `Jack's Knight` (1900 ATK, same 4300 exact damage) and updated the generator table so regeneration keeps the deterministic split. |
| Exam results had no explicit DP field even though A02 consumes the payload. | Added `FDAExamResult::DPReward` and cycle-level optional `dp_reward`/`reward.dp`, defaulting to 0 until A01 verifies an exam DP amount. |

## 7. Remaining blockers / risks

- **No UE build or PIE run in this pass.** The orchestrator owns the build.
  The code is compile-safe by inspection only; the first real run must confirm
  the expected summaries.
- **Canonical puzzle boards and timers are unknown.** A01 has canonical
  solutions but no decoded fixed-board table. P001–P020 remain authored
  fallbacks; P021–P100 remain generated templates. The suite proves the
  authored data, not GBA fidelity.
- **Actual wall-clock timer UI is not exercised.** The test drives
  `FDuelEngine::CheckScenarioTimeout` directly. The HUD timer/visual warning
  remains an A09/manual item.
- **A04 SetSpellTrap limitation.** Setting a non-Quick-Play Spell is legal in
  the real game but rejected by the current engine. P015 avoids it; A04 should
  lift the restriction before any future puzzle uses that action.
- **A04 ritual tribute ordering.** The engine chooses the lowest-level
  tributes. P047 now avoids the ambiguous Level 4 field body; future ritual
  puzzles should keep the field body above the intended hand tribute levels.
- **Exam DP reward is unverified.** The payload carries 0. A01 should publish
  any canonical exam DP amount before A02 starts granting it.
- **Exam pass mark.** Content still uses 300; the 250/300 dispute remains open
  in `scoring.json` and `exams.json`.
- **Effect coverage.** Puzzles use only cards already supported by the
  current engine/effect runtime. New puzzle cards that depend on unscripted
  A05 effects will fail the suite until those effects land.
