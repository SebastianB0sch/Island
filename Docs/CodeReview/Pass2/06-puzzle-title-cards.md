# 06 — Puzzle runtime, titles, card records and asset lookups

Branch: `refactor/code-review-pass` (pass 2, stacked on the uncommitted first pass).

## 1. Scope and constraints

Owned files:

- `DAPuzzleRuntime.*`, `DAPuzzleSelfTest.*`, `DAPuzzleTests.cpp`
- `DATitleSystem.*`
- `DACardRecords.*`, `DACardArtSubsystem.*`, `DACharacterPortraitSubsystem.*`
- `DAGameMode.*`
- this report

No UI, duel-engine, story/save or effect-runtime files were edited. Public APIs and
serialized formats are unchanged; all changes are behavioral hardening inside the
existing signatures. The Unreal editor and UnrealBuildTool were not run.

A note on terminology: `FDAPuzzleRuntime` is a **data loader and authored-line
replay validator**, not an interactive puzzle state machine. The timed-puzzle
lifecycle (`BeginTimed` / `SubmitTimedResult`) is owned by `UDAExamSubsystem`,
and the puzzle board is played by `FDuelEngine`. The audit therefore covers the
runtime's parse → scenario → replay → result path and its callers' idempotence
contracts, and records the missing interactive completion path as a cross-team
contract gap (R1).

## 2. Findings

| # | Severity | Location | Finding | Status |
|---|---|---|---|---|
| P1 | High | `DAPuzzleRuntime.cpp` `LoadPuzzleDirectory` | Appended into the caller's array instead of replacing it and returned with partially loaded records on a later file failure. Reusing an output array duplicated puzzles; a failed load left a corrupt catalog. | Fixed: resets output, builds a local array, swaps on success, rejects duplicate ids. |
| P2 | High | `DAPuzzleRuntime.cpp` `ReplayById` | Puzzle id was concatenated directly into a path; `..`, `/` and `\` escaped `Content/Data/Puzzles`. | Fixed with a slug whitelist (letters/digits/`_`/`-`, max 64). |
| P3 | Medium | `DAPuzzleRuntime.cpp` `Replay` | Auto-answered at most one pending choice per step. Chained trigger choices stayed pending and turned valid authored lines into failures. | Fixed: `PuzzleAutoAnswerChoices` drains the queue with a 64-answer guard. |
| P4 | Medium | `DAPuzzleRuntime.cpp` `BuildScenario` | Always returned true for hand-built definitions, including empty id, zero LP and zero turn limit. `Replay` then failed with misleading engine errors or a "did not win" message. | Fixed: validates id, both LP totals, turn limit and non-negative time limit. |
| P5 | Medium | `DAPuzzleRuntime.cpp` `PuzzleReadSide` / `PuzzleReadSolution` | Malformed JSON was silently defaulted: non-numeric or zero card ids became 0, a non-scalar `target` became a direct attack, and `change_position` accepted an empty position. | Fixed: card-id arrays, targets, required `card_id`/`attacker_card_id` and change-position values are validated with field-specific errors. |
| P6 | Medium | `DAPuzzleRuntime.cpp` `Replay` | `FDAPuzzleReplayResult::Error` was never populated; callers only had the separate `OutError`. | Fixed: every failure path now mirrors the message into the result object. |
| P7 | Low | `DAPuzzleRuntime.cpp` `LoadPuzzleDirectory` | Duplicate puzzle ids were accepted; only the self-test detected them after the fact. | Fixed: duplicate ids in different files are now a load error. |
| P8 | Low | `DAPuzzleSelfTest.cpp` `ProbeTimeout` | Timer-probe asserted the first expiry but not that a second tick leaves the result stable. | Fixed: second tick must return false and preserve the opponent win. |
| P9 | Low | `DAPuzzleSelfTest.cpp` | No regression coverage for retry/statelessness, null database or invalid scenario definitions. | Fixed: null-DB and invalid-id checks, per-puzzle replay determinism check, and a failed-attempt-then-retry check. |
| P10 | Medium | `DATitleSystem.cpp` `LoadDefinitions` | Parsed config was committed incrementally; a malformed titles array could leave `DefaultTitleId`/dorm rules from a failed file. Duplicate ids were accepted and equal `Order` values had no deterministic tie-break (`prince_of_games` and `duel_academy_champion` both use 90). | Fixed: transactional locals, duplicate-id rejection, sorted by `Order` then id, configured default/dropout ids resolved or warned/fallback. |
| P11 | Medium | `DATitleSystem.cpp` `EvaluateTitle` | An active temporary story title hid the Dropout Boy fail state, contradicting `ApplyExamOutcome` / `RecoverFromDropout` which promise Dropout Boy on failure. | Fixed: dropout flags are evaluated before temporary titles; header comment updated. |
| P12 | Low | `DATitleSystem.cpp` lookups / defaults | Title id/name lookups were whitespace-sensitive, and `GetDefaultTitle` / `GetDropoutTitleName` returned hardcoded names even when a usable definition existed under a different id. | Fixed: inputs are trimmed, and defaults fall back to the first permanent non-fail / fail-state definition. |
| P13 | Medium | `DACardRecords.cpp` all loaders | A repeated or failed load left stale `CardsById`/`Decks`/`Fusions`; malformed card ids became `0` and were accepted into decks/fusions. | Fixed: maps are reset at the start of each load, integer arrays are type/range checked, malformed entries are skipped with warnings. |
| P14 | Low | `DACardRecords.cpp` `RegisterDeck` | A registered deck id colliding with a starter id returned true but was unreachable because `FindDeck` resolves starters first. Duplicate starter deck ids silently made `GetDecks()` ambiguous. | Fixed: starter collisions return false with a warning; duplicate starter ids keep the first and warn. |
| P15 | Medium | `DACharacterPortraitSubsystem.cpp` | Character/expression ids were concatenated into file paths, so a malformed story id could traverse outside `Content/Data/Portraits`. Lookup was also case-sensitive. | Fixed: ids are trimmed/lowercased, restricted to slug characters, and used as normalized cache keys. |
| P16 | Low | `DACardArtSubsystem.cpp` / portrait subsystem | `Initialize` did not clear caches; `HasCardArt` probed `0.jpg`/negative ids. | Fixed: lifecycle resets and an early invalid-id return. |
| P17 | Info | `DAGameMode.*` | Constructor only assigns the default pawn/HUD/player controller; `DefaultEngine.ini` points at `ADAGameMode` and no subsystem ordering dependency exists here. | No change. |
| P18 | High (out of scope) | `DAExamSubsystem.cpp` / `DAExamUI.cpp` | `BeginTimed` selects a puzzle and `SubmitTimedResult` accepts a result, but the only caller of `SubmitTimedResult` is the debug path `DebugResolveTimed`; the live timed-puzzle duel is not launched and no completion/reward transition exists. | Documented as cross-team contract (R1); files not edited. |
| P19 | Medium (out of scope) | `DAProfileSubsystem::RecordDuelResult` | The function is not idempotent (each call increments `duels_total`, `timed_clears`, etc.). Callers currently guard it: `DADuelUI` with `bDuelResultNotified`, `DAExamUI` outcome application with `bOutcomeApplied`. | Documented (R2); profile/UI not edited. |

## 3. Changes made

### Puzzle runtime and tests

- `FDAPuzzleRuntime::LoadPuzzleDirectory` now resets `OutPuzzles`, loads into a
  local array, rejects duplicate ids case-insensitively, and only publishes the
  catalog after every file loads.
- `FDAPuzzleRuntime::BuildScenario` validates the minimum scenario contract.
- `FDAPuzzleRuntime::Replay`:
  - rejects an empty solution and null database with populated `Result.Error`;
  - parses/validates card-id arrays, targets and action-specific fields;
  - drains chained pending choices after each step and after the solution;
  - normalizes actions/positions (trim + lowercase);
  - keeps the existing metadata, board, turn-counter and final-win assertions.
- `FDAPuzzleRuntime::ReplayById` rejects path traversal and populates result
  errors.
- Added `PuzzleAutoAnswerChoices`, `PuzzleReadCardIdArray` and `PuzzleIdIsSafe`
  helpers; no public signatures changed.
- `DAPuzzleSelfTest` now checks timer idempotence, null DB, invalid scenario,
  per-puzzle replay determinism and failed-attempt retry cleanup. The retry
  checks re-run the authored line through a fresh engine and compare steps/LP/
  turns; the failed-attempt check uses an unsupported first action.
- `DAPuzzleTests.cpp` adds `DuelAcademy.Puzzles.RuntimeLoader`, covering:
  directory reset/idempotent reload, deterministic P001→P100 order, traversal
  rejection, `BuildScenario` validation, duplicate-id rejection, and malformed
  hand/target/LP fixtures. Fixtures are written under
  `Saved/CodeReviewPass2/PuzzleRuntimeAutomation` and removed by the test.

### Title system

- `LoadDefinitions` is transactional, trims ids/names/flags, skips malformed
  entries with a warning, rejects duplicate ids (first wins), and sorts by
  `Order` then id for deterministic equal-order evaluation.
- Configured `default_title`/`dropout_title` are resolved against the loaded
  table with deterministic fallbacks; empty flags/recovery ids fall back to the
  existing defaults.
- `EvaluateTitle` gives the Dropout Boy fail state precedence over temporary
  titles, matching `ApplyExamOutcome` and `RecoverFromDropout`.
- Id/name lookups trim input; default/dropout display names fall back to usable
  definitions. `PromoteDorm` reads the current dorm once.

### Card records and art

- Card/deck/fusion loaders reset their containers, validate integer arrays, skip
  malformed entries with warnings, and expose a load error when no valid cards
  exist. Duplicate card ids keep the last record (previous behavior) with a
  warning; duplicate deck ids keep the first.
- `RegisterDeck` trims ids and refuses starter-deck collisions instead of
  silently shadowing them.
- Card art and portrait caches are cleared on `Initialize`; `HasCardArt`
  rejects non-positive ids.
- Portrait lookups normalize ids to lowercase slug keys and reject separators/
  parent components. All shipped portrait/expression names are lowercase and
  match the 25 story speaker/portrait ids audited.

## 4. Verification

| Check | Result |
|---|---|
| `git diff --check` on all owned files | **PASS** — no whitespace errors (only Git's LF→CRLF autocrlf notices) |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 0 failures, 1 warning |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors, 15 warnings, 6 gaps (baseline set) |
| Python audit of all 100 puzzle JSONs against the new loader rules | **PASS** — 0 invalid card arrays/targets/actions/positions, 0 duplicate ids |
| Python audit of `titles.json` | **PASS** — 17 titles, 0 duplicate ids/names, default and dropout ids resolve; one intentional equal-order pair (90) |
| Unreal editor build / `-DAPuzzleExamSelfTest` / automation tests | **Not run** — forbidden in this workstream (parent owns the combined build/headless run) |

The new automation test and self-test additions are compile-ready but have not
been executed here. The parent should run `-DAPuzzleExamSelfTest` (now includes
the per-puzzle retry checks) and the `DuelAcademy.Puzzles.RuntimeLoader`
automation test in the editor.

## 5. Remaining risks and follow-ups

1. **R1 — timed-puzzle completion path (high, cross-team).** `BeginTimed` and
   `SubmitTimedResult` exist, but the live UI never launches the selected puzzle
   or submits a real duel result; only `DebugResolveTimed` does. Until that is
   wired, `timed_clears` rewards and `MinTimedClears` title unlocks cannot be
   earned through normal play. Contract for the owning workstream:
   - launch `FDAPuzzleRuntime::Replay`/an interactive duel from `BeginTimed`;
   - call `SubmitTimedResult` exactly once on the terminal result;
   - grant DP/rewards once on the success transition, never from `Replay`.
2. **R2 — reward idempotence is caller-owned (medium).** `FDAPuzzleRuntime`
   owns no profile or reward state. `RecordDuelResult` and `ApplyExamOutcome`
   are not intrinsically idempotent; the current UI guards (`bDuelResultNotified`,
   `bOutcomeApplied`) are the only protection. A result token persisted with the
   save, or a `RecordDuelResultOnce` keyed by a result id, would remove the risk
   if the result screen can be recreated or resumed.
3. **R3 — title duplicate display names (low).** Duplicate ids are rejected, but
   duplicate display names are only warned; `FindDefinition(id-or-name)` returns
   the first. Current data has none.
4. **R4 — title active-temp + dropout precedence changed (low).** Dropout Boy now
   wins over an active temporary title. This matches the exam-failure contract
   but is not covered by an existing self-test; the profile workstream should add
   that regression beside its title tests.
5. **R5 — portrait case normalization (low).** Lookup now lowercases ids and
   expression names. All shipped assets and story ids are lowercase; future
   content with uppercase filenames must be renamed or the normalizer extended.
6. **R6 — art cache invalidation (low).** Missing card art is cached as null for
   the session; adding or replacing art requires a session restart. There is no
   invalidation API. This is intentional to keep per-frame draw code cheap, and
   is documented in the header.
7. **R7 — card/deck reload policy (low).** Card ids keep last-wins (existing
   behavior), deck ids keep first-wins; both now warn. If content generation ever
   emits duplicates, validators should fail before packaging rather than relying
   on these warnings.
