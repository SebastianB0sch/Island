# Code Review & Refactor Pass 4 — Overview

Branch: `refactor/code-review-pass`

Base: the pass 1–3 tree, committed as `77cc9c7`
("Checkpoint: code review passes 1-3"). This pass is fully stacked on that
checkpoint; nothing from earlier passes was reverted.

## Method

Seven **read-only discovery workstreams** ran a fresh-eyes review of the whole
tree (both C++ and project Python), each re-verifying pass 3's documented
residual risks against the current code and reporting new findings with file:line
evidence. The parent then partitioned the accepted findings into seven **fix
workstreams with strictly disjoint file ownership**, two pinned cross-workstream
API contracts, and a documented deferred list. After parallel execution the
parent reconciled integration hand-offs, fixed the cross-worksequence in seams
the compiler caught, built `DuelAcademyIslandEditor Win64 Development`, and ran
the full gate fleet.

| # | Workstream | Main files | Report |
|---|---|---|---|
| 01 | Duel engine | `DADuelEngine.*`, `DAEffectRuntime.*`, self-tests | [01-duel-engine.md](01-duel-engine.md) |
| 02 | Persistence & story | `DASaveGame.*`, `DAStorySubsystem.*`, `DAEventGraph.*`, `DAOpponentSubsystem.*`, `DACalendarSubsystem.*`, `DASettings.*`, `DAStoryPlaythroughTest.cpp` | [02-persistence-story.md](02-persistence-story.md) |
| 03 | Economy & profile | `DAProfileSubsystem.*`, `DAInventorySubsystem.*`, `DAShopSubsystem.*`, `DADeckLogic.*`, `DAEconomyJson.h`/`DAEconomyTypes.h` | [03-economy-profile.md](03-economy-profile.md) |
| 04 | UI & pawn input | `DAHUD.*`, `DAStudentCharacter.*`, UI screens, `DAAvatarComponent/AnimInstance`, `DAA02GateTests.cpp` | [04-ui-pawn.md](04-ui-pawn.md) |
| 05 | World & NPC | `DAIslandSubsystem.*`, `DAInteriorPortal.*`, `DANpcDirector.*`, `DAPortalTest.*`, `DANpcScheduleTest.*` | [05-world-npc.md](05-world-npc.md) |
| 06 | Python asset pipeline | `Tools/dai/**`, editor Python, `Tools/tests/test_python_pipeline.py` | [06-python-pipeline.md](06-python-pipeline.md) |
| 07 | Data tooling & CI | `Tools/{canon,economy,validate,puzzles,story,opponents,integration,world}/**`, CI, `.gitignore` | [07-data-tooling-ci.md](07-data-tooling-ci.md) |

## Pinned cross-workstream contracts (both landed and consumed)

1. `FDADuelUI::WasDeckSelectClosedWithoutResult()` — declared/implemented by
   WS-04; consumed by the story pending-duel tick (WS-02) so closing the deck
   select without a duel result re-presents instead of recording a phantom loss.
2. `ADAStudentCharacter::NotifyTeleportArrived()` — declared/implemented by
   WS-04; called by `DAInteriorPortal::ApplyArrival` (WS-05) so portal arrival
   cannot leave a stale interaction focus on the old cell's actor.

## Parent integration corrections

The first integrated build exposed five seams no single workstream could see;
all fixed by the parent before the gate fleet:

- `Containers/UniquePtr.h` does not exist in UE 5.8 (header lives in
  `Templates/UniquePtr.h`); `DAA02GateTests.cpp` include corrected.
- `UDAProfileSubsystem::RequestProgressionAutosave` was private while four
  progression producers (calendar day-change, story event-completion, shop
  purchase, exam outcome) must trigger it; moved to public with a contract
  comment ("only after a successful mutation").
- WS-02's story-side consume of contract #1, and the exam-atomic-save +
  `shop_purchase` / `exam_result` autosave hand-offs were wired into
  `DAExamUI.cpp` (deferred claim → one autosave) and `DAShopSubsystem.cpp`
  (success-only trigger), closing the documented P4-04 trigger set:
  day change, event completion, purchases (duel/result-token and exam paths
  persist through their own saves).
- `EJson::Type` was an illegal qualified name; the P4-05 fixture uses `EJson`.
- The golden-save fixture fetched `UDAIslandSubsystem` from `UGameInstance`
  although it is a world subsystem; the fetch goes through `GetWorld()`.

The calendar bridge (W2) needed three further integration iterations before
the schedule test went green; the final mechanism (per-tick suppression of
only the restore-materializing poll, producer notifications through
`NotifyScheduleApplied`, and a director-first baseline) plus the exact
failure history is documented in the [05-world-npc.md](05-world-npc.md)
integration addendum. The story test's bridge stage bookkeeping (counter
resets at stage edges) is part of the same addendum.

## Outcome (per-workstream summaries)

- **Duel engine.** AI turns now run `EffectRuntime->OnBattleEnd()`
  (`defense_at_end` no longer mis-flips one turn late); turn handoff defers
  behind a pending player prompt and resumes on answer; the AI spell-resolution
  path uses the shared chain-card cleanup; Kuriboh LV10 burn uses `GetAtk`;
  Card Destruction discards both hands before final draws; the attack visual
  goes through the capped `EmitVisual`; effect ops break on `bWinnerSet`;
  chain cards are re-fetched field-only; LP and script ints clamp; `Start()`
  validates decks fail-closed (all 37 shipped decks verified legal); shared
  `ApplyFieldStats`/`NormalizeOutbound` helpers replace two duplicated ladders.
  New rules-gate tests: RESULT-PASS assertion, queue-cap one-time warning, AI
  battle-end flip, prompt-across-handoff.
- **Persistence & story.** Golden saves now load (settings speed fields accept
  the schema's integer 0..3 and map to the canonical string; the fixture pins
  the full payload contract plus a `.sav` round trip); deck-select cancel is a
  re-present, never a phantom loss; refused duel-open asks retry before the
  10 s loss fallback; story ledgers validate before apply; in-memory loads
  migrate; `EvaluateTrigger` accepts the full condition vocabulary; opponent
  cooldown state survives backwards day jumps (validated + realigned test);
  duplicate scene/line keys warn; `story_events_cleared` increments on real
  completions (two canon titles were otherwise unreachable); calendar honors
  its saved hour, `SkipToDate` broadcasts once; starter-deck flags reward-ledger
  are only marked after a successful import.
- **Economy & profile.** Duel results persist claim+counters+DP in ONE autosave
  (the exam lane migrated to the deferred claim via the parent hand-off); at-cap
  card adds no longer poison `GetDistinctCardsOwned`; deck activation refuses
  rules-illegal decks while keeping the previous deck; the legacy
  internal-wallet flag can no longer detach the live wallet mid-session; ante
  ids fold case; zero-count struct payloads refresh; `MaxPlayerDecks`,
  pack sizes, versions and id normalization are unified (`RequireVersion`,
  `NormalizeIdKey`); temporary titles get a 7-day grace and clamped days.
- **UI & pawn input.** All non-movement pawn handlers share one
  `IsWorldInputAllowed()` gate (world hotkeys no longer act under modals; the
  `N` press no longer both creates a deck and skips three game hours); `P`/`B`
  cannot open an invisible PDA over the map; help owns its Escape; the dead
  menu handlers are deleted with a cross-reference to prevent reintroduction;
  exam Escape during a scenario duel is owned by the board; duel pose cannot
  survive a possession restart; the starter-deck picker pages (page 4,
  cap 6) instead of hard-coding 3 decks while the data ships 4; exam panel and
  deck grid layout budgets fixed; shop/deck have real wheel scrolling; PDA
  same-tab reopen refreshes mail. New `-DAPawnUIGateTest` covers the 128-mask
  input truth table, contract #1 state machine and pagination bounds.
- **World & NPC.** Fast travel during a pending portal teleport aborts the
  stale teleport instead of yanking the player back; the calendar now bridges
  weekday/period changes into the NPC schedule (the cast actually rotates in
  live play, with a no-re-apply guard and a test); unresolved portal ids retry
  within the bounded world-state window before expiring; schedule adoption
  despawns a foreign mapped actor; teleported NPCs occupy their destination;
  discovered-location restores union instead of replacing.
- **Python pipeline.** Partial cast builds merge into the previous manifest
  (the `only=` subset can no longer cause the next import to delete the cast);
  level/asset saves check results and fail the CLI; `gltf-transform` has a
  120 s timeout with `SubprocessError` handling; the vrm_tex cache validates
  freshness; terrain caches are stamped with `FIELD_RES` and refused on
  mismatch; VRM parsing is shape-validated; `set_props` gained strict mode;
  Pillow opens are with-managed; JSON/writer outputs route through the atomic
  kernel; the personal `/home/user` tool candidate is gone; stage runners
  fail closed with exit 2. Pipeline tests grew 126 → 186 total across the repo.
- **Data tooling & CI.** Effects-lane writers are atomic on engine-loaded data
  (`Tools/tooling/atomic.py` shared kernel); story audit scripts are portable
  and import-safe; the canon legal gate ignores the documented local-only
  dir; `--no-report` is now the DEFAULT for canon validation (no tree dirt);
  `import_canon_decks --check` fails closed; `run_engine_selftests` kills the
  whole process tree; per-record sha256 digests are validated (and the three
  starter decks now carry digests from the builder); `baseline.json` is
  regenerated by `Tools/integration/build_baseline.py`; schema_lite honors
  draft-07 semantics; validate_all exits 2 on internal errors; CI gained
  effects coverage/audit checks.

## Verification

All Unreal steps used `UnrealEditor-Cmd.exe`
(`C:\Program Files\Epic Games\UE_5.8`) with `-game -nullrhi -nosound
-unattended -nop4`; automation ran without `-game`. The editor build is the
integrated tree after the parent's six seam fixes and the calendar-bridge
integration.

| Check | Result |
|---|---|
| `DuelAcademyIslandEditor Win64 Development` build | **PASS** — clean incremental |
| `run_smoke.py --all` (validate gate, 24-iteration duel self-test, profile, rules, economy 446/446, A07 puzzle/exam, automation `DuelAcademy` 6 tests) | **PASS** |
| `-DAEffectRuntimeSelfTest` | **ALL PASS** |
| `-DAPawnUIGateTest` *(new)* — 128-mask input truth table, contract #1 state machine, picker pagination bounds | **PASSED** |
| `-DAExamTimedDuelTest` — real timed puzzle duel: `TimedDone`, solved, token recorded, submits exactly once | **PASS** (exit 0) |
| `-DAPortalTest` — portal interlock + queued-restore retry + P4-10 union | **PASS** — 333/0 |
| `-DANpcScheduleTest` — schedules + W2 calendar bridge stage machine (13 new checks) | **PASS** — 568/0 |
| `-DASaveFuzz=300` | **PASS** — 300 states, 100 corruption cases, 50 migration cases |
| `-DATwelveMonthTest` | **PASS** — 365 days, 12 months, overflow guards |
| `-DAStorySelfTest` | **PASS** — opening + full-campaign audit |
| `-DAFullStorySelfTest` | **PASS** |
| `-DAStoryPlaythroughTest` | **PASS** — 35/35 events, 40/40 story duels (39/39 full campaign), **109 checks passed, 0 failed**; golden-save fixtures included |
| `python -m unittest discover -s Tools/tests` | **PASS** — 186 tests (was 126 in pass 3) |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors / 15 warnings / 6 tracked gaps, 421 files |
| `python Tools/canon/validate_canon.py` | **PASS** — 298 checks, 0 errors, **1 warning** (starter-deck record digests now back-filled by the builder; 2 → 1) |
| `python Tools/economy/validate_decks.py` / `validate_packs.py` | **PASS** — 81 checks / 1,342 checks |
| `python Tools/opponents/import_canon_decks.py --check` | **PASS** — 32/32 runtime, 37/37 constructed, 32/32 references |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 1 warning |
| `python Tools/effects/validate_effects.py` | **PASS** — 253 scripts, 0 warnings |
| `python Tools/world/validate_layout.py` + `test_interiors.py` | **PASS** |
| `docs`: `Docs/Canon/VALIDATION.md` + `Docs/Integration/baseline.json` regenerated; `Tools/integration/build_baseline.py --check` | **PASS** |

## Size

The pass-4 delta against the checkpoint is **98 modified tracked files plus 16
new files** (workstream reports under `Docs/CodeReview/Pass4/`, the partial
manifest merge module, the VRM parser, `Tools/tooling/atomic.py`, the baseline
builder and the tooling-CI test suite): **+4,632 insertions / −953 deletions**
on top of the +22,381/−5,439 from passes 1–3 (committed as `77cc9c7`).

## Deferred by design (documented risks carried forward)

- Duel: name→descriptor table (C1), defensive-trap helper (C3), effect-state
  registry (C4); pre-existing AI End-Phase prompt stranding for opponent-owned
  optional triggers (D2 kept minimal).
- Avatar: third-slot crossfade pop (W4) and pose-context pooling (W10) need the
  renderer/animation thread to validate — not verifiable headless here.
- Story: modal-blocked pending-duel wait is a documented policy (P4-08); the
  choice-ledger key scheme (P4-12) needs a dual-key migration plan before any
  change (changing it would re-apply old outcomes for current saves).
- Inventory: importer category purge opt-out (T9) is engine-only verifiable.
- Tooling: `Tools/story` one-shot migrations remain archived-in-place (V2/V13
  fixes cover their portability/import-safety).
- UI: renderer/locomotion suites still not run (unchanged from pass 3); visual
  regression check for the new picker pagination recommended once screenshots
  are available.
