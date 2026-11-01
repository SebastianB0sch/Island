# Code Review & Refactor Pass 2 — Overview

> A third pass, stacked on this work, is documented in
> [../Pass3/00-overview.md](../Pass3/00-overview.md).

Branch: `refactor/code-review-pass`
Base: the uncommitted first pass described in [../00-overview.md](../00-overview.md).
This pass is stacked on that work; nothing from pass 1 was reverted.

## Method

Eight disjoint workstreams reviewed and changed separate parts of the
repository. The parent session then integrated them, fixed compile/test drift,
built the editor target, and ran the complete headless and Python gate set.

| # | Workstream | Main files | Report |
|---|---|---|---|
| 01 | Effect semantics | `DAEffectRuntime.*`, `Tools/effects/` | [01-effect-semantics.md](01-effect-semantics.md) |
| 02 | Duel engine, rules and AI | `DADuelEngine.*`, `DADuelEngineDiagnostics.cpp`, `DADuelistAI.*`, `DADuelRulesSelfTest.*` | [02-duel-engine.md](02-duel-engine.md) |
| 03 | UI layer | `DADuelUI.*`, `DAHUD.*`, `DAPDAUI.*`, title/dialogue/deck/shop/exam UI | [03-ui-layer.md](03-ui-layer.md) |
| 04 | Save, story and progression | `DASaveGame.*`, `DAStorySubsystem.*`, profile/calendar/event/opponent/inventory/shop/deck logic | [04-save-story.md](04-save-story.md) |
| 05 | World, character and NPCs | character/avatar animation, NPC director/spawns, portals, interactables, island/world, settings | [05-world-character.md](05-world-character.md) |
| 06 | Puzzles, titles and cards | puzzle runtime/tests, title system, card records/art/portraits, game mode | [06-puzzle-title-cards.md](06-puzzle-title-cards.md) |
| 07 | Python/Blender pipeline | `Tools/dai`, `Content/Python`, generators and pipeline tests | [07-python-pipeline.md](07-python-pipeline.md) |
| 08 | CI and integration harness | `Tools/integration`, `ci.yml`, ignore rules and harness tests | [08-ci-harness.md](08-ci-harness.md) |

Each workstream was constrained to its own paths and wrote its own report. The
parent session reviewed the combined diff, fixed the defects that only appear
when the workstreams are compiled/tested together, and reran the gates.

## Integration corrections

The first combined build exposed four merge-level defects, all fixed:

- `DADialogueUI.cpp`: a new visible-option loop shadowed the typed-text string
  `Visible`; renamed the loop index.
- `DADuelEngine.cpp`: a counter-trap local reused the `TrapUid` parameter name;
  renamed it to `CounterTrapUid`.
- `DANpcSpawnPoint.cpp`: `FinishSpawning` returns `void` in this engine
  version; removed the invalid return-value check.
- `DAStoryPlaythroughTest.cpp`: persistence-test locals shadowed function-scope
  snapshots and the `CommandIndex` member; renamed the test locals.

The headless automation run also exposed pre-existing stale tests, now fixed:

- `FDAExamCycleTest` and `FDAOpponentRosterTest` created `GameInstanceSubsystem`
  objects directly in the transient package, violating their `ClassWithin`
  and raising an ensure. They now use a real `UGameInstance` outer.
- `FDAOpponentRosterTest` still expected 31 runtime decks; the shipped roster
  has 32 after the pass-1 `sheppard_year1` mapping. Updated.
- `FDAPuzzleDataTest` still assumed 20 level-1 files; the shipped set is 100
  puzzles with 20 per level. It now validates all five levels and their counts.

Integration also fixed a real NPC regression: deferred NPC spawning lost the
owner during `FinishSpawning`, so the director's orphan census reported zero.
The owner is now restored after `FinishSpawning`; `-DANpcScheduleTest` is green.

No generated data, manifest or asset was changed by this pass.

## Verification

All commands were run from `C:\dev\GX` unless noted. The editor build used UE
5.8, Win64 Development.

| Check | Result |
|---|---|
| `DuelAcademyIslandEditor Win64 Development` | **PASS** — final incremental build clean, no compiler warnings |
| `-DADuelSelfTest=24` | **PASS** — 24 iterations, 12 player / 12 opponent, 0 draws, 0 stalls, 0 invariant failures, 37/37 decks, 100/100 puzzles |
| `-DAProfileSelfTest` | **PASS** |
| `-DADuelRulesSelfTest` | **PASS** — 86/86 |
| `-DAEconomySelfTest` | **PASS** — 213/213 |
| `-DAPuzzleExamSelfTest` | **PASS** — puzzles 105/105, exams 104/104, both suites pass |
| `-DAEffectRuntimeSelfTest` | **PASS** — 166/166 |
| `-DAStorySelfTest` | **PASS** — summary logged, editor intentionally left open and then terminated |
| `-DAFullStorySelfTest` | **PASS** — 35 events, 44 scenes, summary logged, editor intentionally left open and then terminated |
| `-DAStoryPlaythroughTest` | **PASS** — 35/35 events, 40/40 story duels (39/39 full campaign), 55 checks, 0 failures |
| `-DAPortalTest` | **PASS** — 302/302 |
| `-DANpcScheduleTest` | **PASS** — 514/514 |
| `-DASaveFuzz=300` | **PASS** — 300 states, 100 corruption cases, 50 migration cases, 67,496 checks, 0 failures |
| `-DATwelveMonthTest` | **PASS** — 365 days, 12 months, 10,947 checks, 0 failures |
| Unreal automation `DuelAcademy` | **PASS** — 5 tests, 0 failures |
| `python -m unittest discover -s Tools/tests` | **PASS** — 71 tests (also 71 under Python 3.12) |
| `python Tools/effects/test_effects.py` | **PASS** — 9 tests |
| `python Tools/effects/validate_effects.py` | **PASS** — 253 scripts, fusion 75/76, ritual 22/22, 0 warnings |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors, 15 warnings, 6 tracked gaps |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 0 failures, 1 warning |
| `python Tools/opponents/import_canon_decks.py --check` | **PASS** — 32/32 runtime, 37/37 constructed, 32/32 references |
| `python Tools/economy/validate_decks.py` / `validate_packs.py` | **PASS** — 81 checks / 1,342 checks |
| `python Tools/world/validate_layout.py` | **PASS** — 20 existing, 6 merged, 0 missing, 10 needs-interior |
| `python Tools/audit_story_fidelity.py` | **PASS** — 39/39 duels, 44 scenes, no missing scenes |
| `python Tools/integration/run_smoke.py --validate` | **PASS** |
| `python Tools/integration/run_smoke.py --all --dry-run` | **PASS** — 7 planned steps |
| `git diff --check` | **PASS** — no whitespace errors (line-ending advisories only) |

The two open-ended story audits do not request their own exit. Their final
summaries were observed and the process trees were terminated, matching the
documented pass-1 procedure.

## Outcome

- **Effect events are no longer dropped during effect execution.** A bounded
  FIFO dispatches nested summon/destroy/damage/leave-field events after the
  current script. Graveyard notifications are destination-aware, so a banish
  replacement no longer masquerades as a Graveyard move.
- **Duel outcomes have a first-class draw.** Double KO and simultaneous
  deck-out use `EndDuelAsDraw`, and `ResultStats.bDraw` is consistent. Battle
  bookkeeping now uses one damage pipeline with correct source/receiver ids.
- **The worst remaining UI function was split.** `DrawDuelFx` is now 12
  event-family helpers, and the winner-beat skip hint is truthful.
- **Save loading is transactional.** Provider sections are validated before
  calendar/profile/settings are mutated. Pending-duel state and an outcome
  ledger are persisted; nested story state is canonical.
- **World/NPC lifecycle bugs were fixed.** Deferred spawn configuration now
  survives `BeginPlay`, ownership is restored, spawn/despawn order is
  deterministic, and portal pairing/save contracts are validated.
- **Puzzle/title/card loaders are stricter.** Duplicate or malformed data is
  rejected or skipped deterministically; the puzzle runtime validates scenario
  and replay input; title ordering is stable.
- **The Python pipeline is more portable and safer.** Geometry edge cases were
  fixed, several generators write atomically, the level CLI no longer requests
  interactive mode, and 11 new pipeline tests cover the changes.
- **CI fails closed.** Timed-out editors are killed as a process tree, parser
  results cannot be upgraded to PASS, report paths are unambiguous, and the
  real validator/test gates run in CI.

## Remaining risks

These are deliberately not hidden by the green gates:

1. **Effect cascade semantics (high):** the event queue is bounded and FIFO,
   not a full Yu-Gi-Oh! chain model. `MoveToGrave` still has no central engine
   hook, and destruction destination inference should become an explicit
   parameter.
2. **Duel draw compatibility (medium):** `GetWinner()` on a draw still returns
   the opponent for legacy callers; new callers must use `IsDraw()` or
   `ResultStats.bDraw`. `Card Destruction`'s both-short branch ends before
   moving hands, and battle-damage stats still record requested rather than
   LP-clamped damage.
3. **Save compatibility (medium):** pre-ledger saves can duplicate one
   interrupted event outcome, `LastRequestDay` remains transient, and
   `DuelRequest.UnlockFlag` is still caller-gated. Whole-file bytes still vary
   because `saved_at` is regenerated.
4. **UI validation (medium):** no renderer/screenshot or locomotion suite was
   run. Dialogue overflow is keyboard-following rather than mouse-scrollable,
   map keys remain live under Help, and the draw presentation depends on
   `ResultStats.bDraw`.
5. **World state (medium):** NPC schedule and portal save state are still
   session-only; `ApplySchedule` has no production caller; the legacy `[E]`
   card-shop pull remains cosmetic.
6. **Puzzle content path (medium):** the timed-puzzle live path is still not
   wired through the exam UI; reward idempotence remains caller-owned; missing
   card art is cached as null until restart.
7. **Python/Binary outputs (medium):** FBX/PNG/WAV/heightfield writes are not
   all transactional, Unreal imports are not rollback-safe, and stale cast
   meshes are not pruned when `cast.json` shrinks.
8. **CI portability (low):** the Windows fallback degrades to a direct-child
   kill if `taskkill` is unavailable; the POSIX process-group path is only
   exercised by Ubuntu CI. `validate_canon.py` still fails locally on stale
   manifest hashes and remains out of CI.
9. **Content baseline unchanged:** 493 pending Tier-2 effects and the existing
   15 validator warnings / 6 gaps remain tracked content work, not regressions.

## Size

The combined pass-1 + pass-2 working tree has 126 modified tracked files plus
the new diagnostics/story self-test, `jsonio`, tests and review documents:
**6,117 insertions, 3,688 deletions**. The pass-2 reports above list the
individual file-level changes and rationale.
