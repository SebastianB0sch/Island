# 03 — Timed puzzles, result idempotence and title integration

Branch: `refactor/code-review-pass` (pass 3, stacked on uncommitted pass-1/2 work).

## 1. Scope and constraints

Owned files edited:

- `DAExamSubsystem.*`, `DAExamUI.*`, `DAExamSelfTest.cpp`, `DAExamTests.cpp`
- `DAPuzzleRuntime.*`, `DAPuzzleSelfTest.cpp`, `DAPuzzleTests.cpp`
- `DAProfileSubsystem.*`, `DAProfileSelfTest.cpp`
- `DADuelUI.*`, `DAHUD.*`
- this report

No UnrealBuildTool, UnrealEditor, Blender or other Unreal process was run. No
commit or staging was performed. Game data, manifests, saves and unrelated UI
files were not edited. The uncommitted pass-1/2 tree is the baseline and was not
reverted or reformatted.

The timed puzzle remains the authored fixed-board duel from
`Content/Data/Puzzles`; it is not re-implemented in the runtime. `FDAPuzzleRuntime`
still owns no rewards or profile state.

## 2. Findings

| # | Severity | Location | Finding | Status |
|---|---|---|---|---|
| P3-03-01 | High | `DAExamUI.cpp` `StartTimed` / `DrawTimed` | Pass 2 correctly recorded that `BeginTimed` selected a puzzle but no live UI launched it; only `DebugResolveTimed` could submit a result. Normal play could never earn `timed_clears` or 100 timed points. | Fixed: the timed phase loads the selected puzzle, builds the authored scenario, launches it through `ADAHUD`/`FDADuelUI`, tracks scenario turns/seconds/time limit and submits the terminal result once. `DebugResolveTimed` remains for tests. |
| P3-03-02 | High | `DAProfileSubsystem.cpp` `RecordDuelResult` | Every call incremented `duels_total`, win/loss counters, `timed_clears`, DP and title progress. Caller booleans were the only protection. | Fixed additively: persisted result tokens, `RecordDuelResultOnce`, `TryMarkResultTokenApplied`, `IsResultTokenApplied`; `FDADuelUI` now uses the once API with one token per duel. |
| P3-03-03 | High | `DAExamSubsystem.cpp` `SubmitTimedResult` | Repeated submission was only rejected because the phase changed; a recreated caller could not distinguish “already recorded” from an error and there was no result identity. | Fixed additively: `SubmitTimedResultOnce` with a caller token; same token returns `bAlreadyApplied` without changing turns/seconds/score, a different token is rejected. The legacy `SubmitTimedResult` delegates with an empty token. |
| P3-03-04 | High | `DAExamUI.cpp` `FinishPracticalAndResult` | Written counters, exam DP and `ApplyExamOutcome` (which increments `exams_passed`/`exams_failed` and can promote a dorm) were only guarded by a transient `bOutcomeApplied`. Reopening the result screen could apply them again. | Fixed: one persisted `exam_outcome:<attempt-token>` claim covers counters, DP and title/dorm outcome. `StartExam`/`BeginWritten` generate a new attempt token. |
| P3-03-05 | Medium | `DAExamUI.cpp` timed panel | ESC closed the exam while a timed duel was live, leaving a duel running over the island; there was no cancellation path and no result input handling for scenario duels. | Fixed: the timed board owns input; ESC/P cancels, records a failed timed section and returns to the timed panel. Reopening the screen adopts an already-live timed duel instead of launching a second one. |
| P3-03-06 | Medium | `DAPuzzleRuntime.cpp` `Replay` | Final validation required the opponent to be at 0 LP. Alternate wins (Exodia, deck-out, scenario objective completion) are valid engine wins and were rejected. | Fixed: validation trusts `IsOver()` plus a player winner. |
| P3-03-07 | Medium | `DAPuzzleRuntime.cpp` `BuildScenario` | Hand-built definitions accepted zero/negative card ids, invalid field zones, duplicate zones and non-monster/SpellTrap field entries. The engine silently relocated duplicate monster zones. | Fixed: validates all card-id arrays, field card ids, zone kinds, zone indices and duplicate zones. |
| P3-03-08 | Medium | `DAPuzzleRuntime.cpp` `Replay` | Starting state was checked by counts only; a card in the wrong zone, wrong battle position or wrong face-up state could still replay. | Fixed: every authored field card is matched to its engine zone, id, face-up state and battle position. |
| P3-03-09 | Medium | `DAPuzzleRuntime.cpp` / `DAExamUI.cpp` | The exam path would have had to concatenate `Content/Data/Puzzles/<id>.json` itself. `ReplayById` had a safe whitelist but no reusable loader entry point. | Fixed additively: `LoadPuzzleById` validates the slug and loads one definition; `ReplayById` now uses it. The live timed path uses it before `BuildScenario`. |
| P3-03-10 | Medium | `DADuelUI.cpp` scenario path | There was no way to start a fixed scenario without the deck picker, no scenario clock, no terminal payload and the result screen offered a rematch that would leave the exam. | Fixed: `StartScenarioDuel`, scenario elapsed time/turn tracking, held `FDAScenarioDuelResult`, `ConsumeScenarioDuelResult`, `AbortScenarioDuel`, and a scenario-specific CONTINUE result screen. |
| P3-03-11 | Low | `DAProfileSelfTest.cpp` title tests | Dropout Boy precedence over an active temporary title was implemented in pass 2 but had no regression. | Fixed: regression added beside the temporary-title and exam-outcome tests. |
| P3-03-12 | Low | `DAProfileSubsystem.cpp` persistence | New idempotence tokens had to survive save/load to be useful after a restore. | Fixed: tokens are written in the profile object and read additively; duplicate tokens and over-cap arrays are normalised. |
| P3-03-13 | Info | `DAPuzzleRuntime` reward ownership | Runtime still parses `reward.dp` for data validation but never grants it. | No change; the live duel uses the existing profile reward path exactly once through the result token. |

## 3. Changes made

### Timed exam path (`DAExamUI`, `DAHUD`, `DADuelUI`)

- `FDAExamUI::StartTimed` now calls `BeginTimed` and immediately
  `LaunchTimedDuel`. The launch:
  - loads the selected puzzle with `FDAPuzzleRuntime::LoadPuzzleById`;
  - requires `bEngineReady`;
  - builds the `FDuelScenario` with `BuildScenario`;
  - starts it through `ADAHUD::StartExamTimedDuel`.
- `ADAHUD::StartExamTimedDuel` starts a fixed scenario without the deck picker
  and leaves the exam screen mounted behind the board. `IsExamTimedDuelOpen`,
  `ConsumeExamTimedDuelResult` and `AbortExamTimedDuel` are the minimal bridge.
- `FDADuelUI` additions:
  - `StartScenarioDuel` sets mode `timed_puzzle`, opponent name/id and a unique
    per-duel result token;
  - `DuelScenarioElapsed` advances while the scenario board is live and calls
    `FDuelEngine::CheckScenarioTimeout`;
  - the terminal result is held in `FDAScenarioDuelResult` until consumed, so
    closing the result screen cannot lose it;
  - closing before a result records one failed/cancelled payload;
  - the result screen shows `CONTINUE` instead of `REMATCH` for scenario duels;
  - `NotifyDuelFinished` now uses `UDAProfileSubsystem::RecordDuelResultOnce`.
- `FDAExamUI` polls the payload once, closes the duel, restores GameAndUI input
  and calls `SubmitTimedResultOnce`. It also adopts a live timed duel if the
  screen is recreated, and ESC/P during the board cancels and records a failed
  timed section rather than leaving an orphan duel.
- `DebugResolveTimed` and the `-DAGameplayUITest` flow still work; debug
  resolution aborts an active board and submits the requested result.
- New headless regression switch `-DAExamTimedDuelTest`: prepares a profile,
  opens month 1, answers written, launches the real timed puzzle, forces a win,
  and asserts `TimedDone`, solved, token recorded and `timed_clears == 1`.

### Result idempotence (`DAProfileSubsystem`, `DAExamSubsystem`)

- Added `RecordDuelResultOnce`, `IsResultTokenApplied` and
  `TryMarkResultTokenApplied`. Tokens are trimmed, bounded to 160 characters,
  kept in a FIFO capped at 256 entries, and persisted as
  `profile.applied_result_tokens`.
- Empty tokens preserve the legacy callers (`RecordDuelResult`,
  `SubmitTimedResult`).
- `SubmitTimedResultOnce` records the token, clamps turns to 0..100000 and
  seconds to a finite 0..86400. The same token is idempotent; a different token
  is rejected.
- `BeginTimed`, `BeginWritten`, `StartExam`, `Reload` and `AbortExam` clear or
  rotate the relevant tokens. `GetAttemptToken` exposes the per-attempt id.
- The exam result block claims `exam_outcome:<attempt-token>` before applying
  `written_correct`, `written_total`, exam DP and `ApplyExamOutcome`, so a
  recreated result screen cannot double-count or double-promote.

### Puzzle runtime

- Added `LoadPuzzleById`, reused by `ReplayById`.
- `LoadPuzzleFile` now rejects a puzzle id that is not a plain file stem.
- `BuildScenario` validates all card-id lists and all fixed field entries
  (positive ids, monster/SpellTrap only, zone 0-4, no duplicate zones).
- `Replay` verifies the exact starting field (zone, id, face-up, position) and
  accepts any terminal player win rather than requiring 0 opponent LP.
- No reward/profile code was added to the runtime.

### Titles/profile regression coverage

- Dropout Boy remains terminal over an active temporary title; a self-test now
  grants a temporary title, applies a failed exam and asserts both the stored
  and evaluated title are `Dropout Boy`.
- Exam outcome token test asserts one `exams_passed`, one promotion, and no
  second application.
- Timed-clear token test asserts the first `timed_puzzle` win increments
  `timed_clears`, DP and counters once; duplicates change nothing.
- Save round-trip test asserts the applied token survives `WriteSaveData` /
  `ReadSaveData`.

## 4. Verification

Commands run (no Unreal process):

| Command | Result |
|---|---|
| `git diff --check -- <all owned source files + this report>` | **PASS** — exit 0; only Git's LF→CRLF advisory warnings |
| Python source balance scan (string/comment-aware braces/parens) over all changed `.cpp`/`.h` | **PASS** — all balanced |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 0 failures, 1 warning (duplicate card name, baseline) |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors, 15 warnings, 6 gaps (baseline set), 421 files read |
| `git status --short` review | Only owned files plus the pass-3 report were changed by this workstream; pre-existing pass-1/2 modifications remain untouched |

Not run here, owned by the parent: UnrealBuildTool/UnrealEditor build,
`-DAPuzzleExamSelfTest`, `-DAProfileSelfTest`, `-DAExamTimedDuelTest`, and the
`DuelAcademy.*` automation tests. The new tests are compile-ready but have not
been compiled/executed in this workstream.

## 5. API / serialization impact

- Additive C++ APIs:
  - `UDAProfileSubsystem::RecordDuelResultOnce`, `IsResultTokenApplied`,
    `TryMarkResultTokenApplied`
  - `UDAExamSubsystem::SubmitTimedResultOnce`, `GetAttemptToken`,
    `GetTimedResultToken`, `IsTimedSolved`
  - `FDAPuzzleRuntime::LoadPuzzleById`
  - `FDADuelUI::StartScenarioDuel`, `IsScenarioDuelActive`,
    `ConsumeScenarioDuelResult`, `AbortScenarioDuel`, `FDAScenarioDuelResult`
  - `ADAHUD::StartExamTimedDuel`, `IsExamTimedDuelOpen`,
    `ConsumeExamTimedDuelResult`, `AbortExamTimedDuel`
- Existing signatures are unchanged; no callers were broken.
- Save schema: additive `profile.applied_result_tokens` string array. No version
  bump. Older saves load with no tokens; the field is ignored by consumers that
  do not know it.

## 6. Remaining risks and cross-workstream follow-ups

1. **Save owner awareness (low).** `profile.applied_result_tokens` is a new
   additive field written by `DAProfileSubsystem`. The save schema version is
   unchanged; the save workstream should keep this field on migration and
   backups. Tokens are a bounded FIFO (256), so a result older than the window
   could be replayed only if a caller reuses its token after 256 newer results.
2. **Timed reward model (medium, design).** The live timed puzzle uses the
   normal duel result pipeline (`Mode = timed_puzzle`), so winning grants the
   formula DP and increments `duels_total`/`wins_total` as well as
   `timed_clears`. Puzzle `reward.dp` is still parsed but not paid. If product
   wants exam puzzles to pay only puzzle DP and not count as ordinary duels, the
   profile/duel result policy needs an explicit mode rule (not changed here).
3. **Abort semantics (low).** ESC during a live timed puzzle records a failed
   timed section. This is intentional, but it is a design choice; a “resume
   later” policy would need exam persistence, which does not exist.
4. **Time source (low).** The scenario clock uses HUD `DeltaSeconds`, so it
   stops during pause/loading and is not a wall-clock timer. This matches the
   rest of the Canvas UI.
5. **Result-screen payload lifetime (low).** A scenario payload is held in
   `FDADuelUI` until consumed. If a future caller starts another scenario or
   normal deck duel without consuming it, `StartScenarioDuel`/`OpenDeckSelect`
   clears it. The exam path always consumes before starting anything else.
6. **Headless UI coverage (medium).** The real timed path is covered by
   `-DAExamTimedDuelTest` rather than an automation test because it needs a
   world, HUD and Canvas update loop. The parent should run it once in the
   combined headless suite.

## 7. Integration follow-up — help input ownership over the map

Workstream 04 documented that help is drawn above the map but the map's input
block remained live underneath it. The fix is confined to `DAHUD.cpp`:

- `Tick` now has a help-top-layer block: when `bHelpOpen` is set and no duel,
  PDA, dialogue, title or gameplay screen is above it, Escape / gamepad Back
  clears `bHelpOpen` and returns before map input runs.
- The map key block is gated on `bMapOpen && !bHelpOpen`, so arrow navigation,
  travel, Escape-close and mouse travel cannot fire under help.
- `ToggleMap()` refuses while help is open. Modal openers clear `bHelpOpen`
  before their existing `ToggleMap()` close, so opening a shop/PDA/dialogue/
  title/deck/exam/duel still closes both help and map in the original order.
- F1/H still toggles help. Escape now closes help first; a second Escape closes
  the map.
- The title early-return stays before the help/map blocks (title is the topmost
  layer), and `OpenTitle` clears help before opening.

Verification:

| Command | Result |
|---|---|
| `git diff --check -- DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAHUD.cpp DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAHUD.h Docs/CodeReview/Pass3/03-timed-puzzle-idempotence.md` | **PASS** — exit 0, LF→CRLF advisory only |
| String/comment-aware brace/paren scan over `DAHUD.cpp`/`DAHUD.h` | **PASS** — both balanced |
| Source-order review of `Tick`, `ToggleMap`, `ToggleHelp` and all seven modal openers | **PASS** — title returns first, help consumes Escape before the map block, openers clear help before closing the map |

No Unreal process was run.

## 7. Parent integration follow-up

- The first combined `-DAExamTimedDuelTest` run failed at phase `None` because
  the test was not listed in `HasStartupHarness()`; the title overlay blocked
  `OpenExam()`. Added `DAExamTimedDuelTest` to that list. The final run passed
  with phase `TimedDone`, solved, token recorded and `timed_clears == 1`.
- The HUD help/map input policy requested by workstream 04 was implemented in
  `DAHUD::Tick`, `ToggleMap()` and all seven modal openers. The final tree
  passes `git diff --check` and the combined build.
- Final gates: `-DAProfileSelfTest`, `-DAPuzzleExamSelfTest` (105 puzzles /
  104 exams), `-DAExamTimedDuelTest`, story self-tests and automation 5/5 all
  pass.
