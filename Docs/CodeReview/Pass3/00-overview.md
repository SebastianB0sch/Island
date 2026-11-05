# Code Review & Refactor Pass 3 — Overview

Branch: `refactor/code-review-pass`

Base: the uncommitted pass-1 and pass-2 tree. This pass is stacked on that
work; nothing from the earlier passes was reverted.

## Method

Eight disjoint workstreams reviewed and changed separate vertical slices. The
parent session then reviewed the combined diff, fixed integration-only defects,
built the editor target, and ran the headless and Python gates.

| # | Workstream | Main files | Report |
|---|---|---|---|
| 01 | Duel and effect semantics | `DADuelEngine.*`, `DAEffectRuntime.*`, duel/effect tests | [01-duel-effect-semantics.md](01-duel-effect-semantics.md) |
| 02 | Persistence and world state | `DASaveGame.*`, story/opponent, NPC director, portals, island subsystem | [02-persistence-world-state.md](02-persistence-world-state.md) |
| 03 | Timed puzzles and idempotence | exam/puzzle runtime, profile result tokens, duel UI bridge | [03-timed-puzzle-idempotence.md](03-timed-puzzle-idempotence.md) |
| 04 | UI interaction | dialogue, title, PDA, deck/shop UI, shared screen helpers | [04-ui-interaction.md](04-ui-interaction.md) |
| 05 | Economy, inventory and decks | inventory/shop/deck/card records, economy tests | [05-economy-inventory-decks.md](05-economy-inventory-decks.md) |
| 06 | Character, world and animation | character/avatar animation, NPC actors, world actors, settings | [06-character-world-animation.md](06-character-world-animation.md) |
| 07 | Python asset pipeline | `Tools/dai`, editor Python, pipeline tests | [07-python-asset-pipeline.md](07-python-asset-pipeline.md) |
| 08 | Data, CI and build integrity | canon/story/validator tools, CI, smoke harness, build config | [08-data-tooling-ci-build.md](08-data-tooling-ci-build.md) |

## Integration corrections

The first combined gates exposed one stale harness assumption and several
cross-workstream hand-offs. All are fixed in the final tree:

- **`-DAExamTimedDuelTest` was blocked by the title screen.** The test was not
  in `HasStartupHarness()`, so `OpenExam()` correctly refused while the title
  overlay was open and the test ended at phase `None`. Added it to the harness
  list; the live timed-puzzle path now passes.
- **Help no longer leaks input to the map.** Workstream 04 documented the
  required HUD policy. Workstream 03 implemented it: Escape closes help first,
  map navigation/travel/close are gated on `!bHelpOpen`, `ToggleMap()` refuses
  under help, and all modal openers clear help before closing the map.
- **Canon manifest was raced by concurrent validators.** An early workstream
  restored the pre-pass manifest after workstream 08 had refreshed it. The
  parent reran `Tools/canon/build_manifest.py --refresh-hashes`; the manifest
  now matches the committed `cards_manifest.json` and `exams.json` bytes.
- **Starter deck selection was not reaching the deck/inventory.** Added
  `UDADeckLogic::EnsureStarterDeck` (stable recipe-id deck, idempotent) and
  changed `UDAStorySubsystem::ApplyDeckGrant` to import the player deck, grant
  its cards once, and activate the real player-deck id. A fresh opening also
  resets inventory, shop purchase state and player decks before granting.
  `-DAStorySelfTest` now asserts the imported deck and granted collection.
- **Shop restocks now use the absolute campaign day.** `WireEconomySystems`
  was rebuilding a year-relative day; it now uses
  `UDACalendarSubsystem::GetAbsoluteDay()`.
- **Legacy saves without provider sections reset transient economy state.**
  Inventory, shop and deck providers now implement
  `ResetSaveSectionState()`; the shop reset preserves the HUD wallet handlers.
- **Generic fusion recipes render correctly.** The deck-editor recipe overlay
  prints `"N <type> monsters"` for `AnyCount` recipes (F.G.D.) instead of an
  empty material line.
- **Duel-disk default is consistent.** `settings.json` now uses `F`, matching
  the character binding and the code fallback.
- **`Tools/build_island.py` CLI hardening.** Unknown stage names now exit 2,
  `--help` exits before importing the pipeline, stage order is normalized, and
  three regression tests cover the parser.
- **Golden new-game fixture wrapped.** `golden_new_game.json` now uses the
  provider-shaped `inventory` and `decks` sections required by the current
  validators; the stale `story: null` key was removed.

## Verification

All Unreal commands used `UnrealEditor-Cmd.exe` from UE 5.8 with
`-game -nullrhi -nosound -unattended -nop4`; automation ran without `-game`.
The editor build used Win64 Development.

| Check | Result |
|---|---|
| `DuelAcademyIslandEditor Win64 Development` | **PASS** — final incremental build clean |
| `-DADuelSelfTest=24` | **PASS** — 24 iterations, 12 player / 12 opponent, 0 draws, 0 stalls, 0 invariant failures, 37/37 decks, 100/100 puzzles |
| `-DAProfileSelfTest` | **PASS** |
| `-DADuelRulesSelfTest` | **PASS** — 102/102 |
| `-DAEconomySelfTest` | **PASS** — 446/446 |
| `-DAPuzzleExamSelfTest` | **PASS** — puzzles 105/105, exams 104/104 |
| `-DAEffectRuntimeSelfTest` | **PASS** — 180/180 |
| `-DAStorySelfTest` | **PASS** — opening audit, including starter-deck import/grant |
| `-DAFullStorySelfTest` | **PASS** — 35 canonical events, 44 full scenes, 65 reward records, 84 duel refs |
| `-DAStoryPlaythroughTest` | **PASS** — 35/35 events, 40/40 story duels (39/39 full campaign), 72 checks |
| `-DAExamTimedDuelTest` | **PASS** — real timed puzzle duel, `TimedDone`, solved, token recorded, `timed_clears == 1` |
| `-DAPortalTest` | **PASS** — 327/327 |
| `-DANpcScheduleTest` | **PASS** — 543/543 |
| `-DASaveFuzz=300` | **PASS** — 300 states, 100 corruption cases, 50 migration cases, 67,505 checks |
| `-DATwelveMonthTest` | **PASS** — 365 days, 12 months, 10,948 checks |
| Unreal automation `DuelAcademy` | **PASS** — 5 tests, 0 failures |
| `python -m unittest discover -s Tools/tests` | **PASS** — 126 tests (Python 3.14) |
| Same suite under Python 3.12 | **PASS** — 126 tests |
| `python Tools/canon/validate_canon.py --no-report` | **PASS** — 290 checks, 0 errors, 1 warning |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors, 15 warnings, 6 tracked gaps, 304 info, 421 files |
| `python Tools/effects/test_effects.py` | **PASS** — 9 tests |
| `python Tools/effects/validate_effects.py` | **PASS** — 253 scripts, fusion 75/76, ritual 22/22, 0 warnings |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 0 failures, 1 warning |
| `python Tools/economy/validate_decks.py` / `validate_packs.py` | **PASS** — 81 checks / 1,342 checks |
| `python Tools/opponents/import_canon_decks.py --check` | **PASS** — 32/32 runtime, 37/37 constructed, 32/32 references |
| `python Tools/world/validate_layout.py` | **PASS** — 17 zones, 36 locations, 20 portals, 97 anchors |
| `python Tools/integration/run_smoke.py --validate` | **PASS** |
| `Tools/integration/run_smoke.py --all --dry-run` | **PASS** — 7 planned steps (workstream 08) |
| `git diff --check` | **PASS** — no whitespace errors |

The two open-ended story audits (`-DAStorySelfTest`, `-DAFullStorySelfTest`)
log their summaries but do not request their own exit. They were observed and
their process trees terminated, matching the earlier pass procedure.

## Outcome

- **Graveyard and damage semantics are centralized.** `MoveToGrave` is the one
  notifying path, destruction carries an explicit destination, and damage
  statistics/scenario objectives use actual LP loss instead of overkill.
- **Timed puzzles are finally playable end-to-end.** The exam UI launches the
  authored scenario through the duel UI, tracks turns/time, and submits the
  result exactly once. Persisted result tokens prevent duplicate DP, counters,
  exam outcomes and title/dorm progress.
- **Persistence now covers the world.** Opponent cooldowns/counters/emails,
  portal locks/used flags, discovered zones and NPC schedule/event inputs
  round-trip. State is queued during apply and restored on a later tick when
  actors exist.
- **The UI interaction model is safer.** Dialogue/title wheel and arrow
  scrolling, empty-choice guards, stale hit-target resets, modal input
  ownership and help-over-map behavior are fixed; long labels are clipped with
  one shared measured-ellipsis contract.
- **Economy input is strict and transactional.** Save sections are validated
  before apply; malformed ids/counts/arrays are rejected; pack opening rolls
  back; arithmetic saturates; starter decks are imported and granted; shop
  restocks use an absolute clock.
- **World/character state is more robust.** Calendar-bound time, swim/landing
  state, interaction radius/focus, deterministic spawn scheduling, location
  extents and settings parsing were hardened.
- **The Python pipeline is safer and more testable.** Atomic FBX/PNG/WAV/NPY
  writers, cache validation, cast-asset ownership/pruning, import preflight,
  path-traversal rejection and CLI error codes landed with new tests.
- **The data/CI gate is broader.** Canon manifest hashes are enforced, story
  migrations no longer write on import, generator CLIs fail closed, and CI
  covers canon, economy, world and harness checks on Python 3.12/3.13.

## Remaining risks

1. **Effect chain semantics (medium):** the event queue is a bounded FIFO, not
   a full Yu-Gi-Oh! chain model. It is intentionally bounded at 64 pending /
   128 dispatched events per cascade.
2. **Draw compatibility (low):** `GetWinner()` still returns the opponent on a
   draw for legacy callers; use `IsDraw()`, `GetResultStats().bDraw` or the new
   `TryGetWinner()`.
3. **Damage contract change (low):** statistics and scenario damage objectives
   now use actual LP loss. Historical balance/report snapshots may move.
4. **Save compatibility (medium):** old saves without a ledger can duplicate
   one interrupted event outcome; pending-duel restore is covered but the HUD
   must still tolerate being asked to reopen the selector. World state is
   applied on the next world tick, and an absent `world` section deliberately
   keeps live world state for legacy payloads.
5. **World reconstruction (low):** NPC identities are reconstructed from
   schedule inputs, not serialized actor references; unknown portal ids are
   dropped; a future streaming loader would need a bounded unresolved-id queue.
6. **Timed-puzzle policy (medium):** a timed win uses the normal duel result
   pipeline, so it also increments ordinary duel/win counters. Puzzle
   `reward.dp` remains parsed but unpaid. The result-token FIFO holds 256
   entries.
7. **UI validation (medium):** no renderer/screenshot or locomotion suite was
   run. The mouse wheel may still reach the pawn camera zoom through
   `MouseWheelAxis` while a modal is open; that needs a visual/input check.
8. **Python/binary outputs (medium):** individual asset writes are atomic, but
   the anime stage and Unreal import are not fully transactional; level saves
   use the editor API. `gltf-transform` still has no timeout.
9. **Data/tooling (low):** `Docs/Integration/baseline.json` is still stale.
   `run_engine_selftests.py` still uses a child-only timeout; the merge gate
   path has process-tree termination. `validate_canon.py` refreshes
   `Docs/Canon/VALIDATION.md` by default unless `--no-report` is used.
10. **Content baseline unchanged:** 493 Tier-2 effects remain pending, and the
    existing 15 validator warnings / 6 tracked gaps remain content work.
11. **Golden save load path:** `golden_new_game.json` is now provider-shaped
    and schema-valid, but the parent did not add a runtime load fixture for it;
    the save fuzz and story persistence tests cover generated payloads.

## Size

The combined pass-1 to pass-3 working tree has **162 modified tracked files plus
39 untracked new files** (review reports, the diagnostics/story audit
extractions, pipeline helpers, and Python tests): **13,789 insertions and 5,439
deletions** against the branch base. The pass-3 reports above describe the
individual file-level changes and rationale.
