# 02 - Persistence, opponent state and world state (pass 3)

Branch: `refactor/code-review-pass` (pass 3, stacked on the uncommitted
pass-1/2 tree).

## 1. Scope and constraints

Owned files edited:

- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DASaveGame.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DASaveGame.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAStorySubsystem.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAStorySubsystem.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAStoryPlaythroughTest.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAOpponentSubsystem.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAOpponentSubsystem.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DANpcDirector.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DANpcDirector.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAInteriorPortal.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAInteriorPortal.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAIslandSubsystem.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAIslandSubsystem.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAPortalTest.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAPortalTest.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DANpcScheduleTest.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DANpcScheduleTest.cpp`
- this report

`DANpcSpawnPoint.*` was read and reviewed but needed no edit. No
UnrealBuildTool, UnrealEditor, Blender or other Unreal process was run. No
commit or staging was performed. Game data, manifests, saves, UI, duel/effect
runtime, build files and unrelated source files were not edited. The
uncommitted pass-1/2 tree is the baseline and was not reverted or reformatted.

The save format stays at version 1. All new state lives in additive root
sections (`opponents`, `world`); old payloads that lack them still load, and
builds that predate these sections ignore them as unknown root keys.

## 2. Findings

| # | Severity | Location | Finding | Status |
|---|---|---|---|---|
| P3-02-01 | High | `DAOpponentSubsystem` / `FDAOpponentRuntimeState` | Pass 2 recorded `LastRequestDay` but left the whole runtime state transient, so duel-request cooldowns, per-day limits, opponent duel counters and email read/unlock state reset on load. | Fixed: `UDAOpponentSubsystem` is an `IDASavePayloadProvider` (`section = "opponents"`). It writes/reads `Wins`, `Losses`, `Draws`, `RequestsToday`, `LastRequestDay`, `RequestDay` and email runtime state; registration is ordered with `Collection.InitializeDependency<UDASaveSubsystem>()`. |
| P3-02-02 | High | `DAIslandSubsystem`, `DAInteriorPortal`, `DANpcDirector` | Portal used/locked flags, discovered zone ids and the NPC schedule/event filter were session-only (pass-2 follow-ups 1-3). | Fixed: additive `"world"` section owned by `UDAIslandSubsystem`: portal states keyed by non-empty `PortalId`, sorted `discovered` ids, and the director's `CurrentScheduleId`/`CurrentWeekday`/`CurrentPeriod`/`ActiveEvent` plus `HasAppliedSchedule`. State is queued by `ReadSaveSection` and applied by an idempotent deferred pass (`Tick` / `ApplyPendingWorldState`). |
| P3-02-03 | Medium | `DAInteriorPortal` save contract | There was no batch apply path; only a single-portal helper existed. Duplicate rows, empty ids, unknown ids and a load before actors exist had no defined behavior or regression coverage. | Fixed: `CollectSaveStates` (sorted, duplicate actor ids keep the first by actor name) and `ApplySaveStates` (empty ids are not wildcards, duplicate rows keep the first, unknown ids are ignored, re-apply is idempotent). `ApplySaveState` keeps its exact-id semantics. |
| P3-02-04 | Medium | `DAStorySubsystem::LoadState` / `Tick` | A pending story duel against any opponent other than Jaden/Syrus was inferred as a loss because only `wins_jaden`/`wins_syrus` were compared. The recorded-result load path already used `wins_total`, so the two paths disagreed. | Fixed: new `InferPendingDuelResult` compares `draws_total`, then `wins_total` (with per-opponent fallbacks) and is used by both the live `bOpened` tick path and the recorded-result load path. |
| P3-02-05 | Medium | `DAStorySubsystem::Tick` | A restored pending duel with `bResumePendingDuel` and no HUD never resolved (`else if (!bResumePendingDuel ...)` skipped it), soft-locking the event queue in headless/dedicated loads. | Fixed: the no-HUD path now resolves the restored duel as a loss after the same 10-second grace used for "duel UI did not open". |
| P3-02-06 | Medium | `DANpcDirector::RestoreScheduleState` | Restoring a save whose director had no applied schedule left NPCs spawned by the previous session's schedule in place. | Fixed: the no-schedule restore despawns points that are not `bSpawnOnBeginPlay` and re-spawns the missing begin-play baseline. Applying an existing schedule still runs `ApplySchedule` once. |
| P3-02-07 | Low | `DASaveGame` provider contract | An absent provider section was always treated as "keep live state", so a player who loaded an old save kept the previous session's cooldown counters. | Fixed additively: `IDASavePayloadProvider::ResetSaveSectionState()` (default no-op) is called for absent sections during apply. `UDAOpponentSubsystem` overrides it to reset runtime state. Other providers keep the historical behavior. |
| P3-02-08 | Info | `DAStorySubsystem` outcome ledger | Re-reviewed pre-ledger save duplication: outcomes apply only at event completion or choice selection; no autosave path exists between those writes and the completion/command-index bookkeeping. A save made before a choice replays the choice once (correct); a save made after it starts after the choice. | No heuristic added; adding one would risk skipping legitimate first-time outcomes. Old saves without `applied_outcomes` keep the pass-2 empty-ledger behavior. |
| P3-02-09 | Info | `UDASaveSubsystem::ApplyPayload`/`ValidatePayload`/`ApplyPayloadInPlace` | Re-reviewed provider validation ordering and rollback. Validation still runs before any live mutation, the snapshot still includes every registered provider, and a failed apply still restores the snapshot. | No change needed; new sections have const structural validators, so they are rejected in the pre-apply phase. |
| P3-02-10 | Info | `DANpcDirector` / `DANpcSpawnPoint` lifecycle | Duplicate spawn-point ids, deferred spawn configuration, active-map re-adoption, destroyed-point orphan cleanup and refresh churn were re-checked. | No further change; the restore contract is documented in section 5. |

## 3. Changes made

### Save subsystem (`DASaveGame.*`)

- Added `IDASavePayloadProvider::ResetSaveSectionState()`. The default is a
  no-op so existing providers (inventory, decks, shop, story) keep the pass-2
  "absent section = live state" behavior.
- `ApplyPayloadInPlace` calls `ResetSaveSectionState()` when a payload has no
  section for a registered provider. Rollback snapshots always contain every
  section, so they are not affected.
- No version bump: the new state is additive root sections.

### Opponent persistence (`DAOpponentSubsystem.*`)

- `UDAOpponentSubsystem` now implements `IDASavePayloadProvider`, section
  `"opponents"`, and registers in `Initialize` after
  `Collection.InitializeDependency<UDASaveSubsystem>()` so subsystem creation
  order cannot silently drop the section. `Deinitialize` unregisters.
- Section shape (version 1):

  ```json
  "opponents": {
    "version": 1,
    "wins":            { "<opponent-id>": 4 },
    "losses":          { "<opponent-id>": 2 },
    "draws":           { "<opponent-id>": 1 },
    "requests_today":  { "<opponent-id>": 1 },
    "last_request_day":{ "<opponent-id>": 10 },
    "request_day": 10,
    "emails": {
      "<opponent-id>": {
        "unlocked": true,
        "unlocked_threads": ["jaden_01"],
        "read_threads": ["jaden_01"]
      }
    }
  }
  ```

- Read starts from a fresh `FDAOpponentRuntimeState` (replace, not merge);
  non-finite/non-numeric values are skipped and integer maps are clamped.
  Thread arrays are de-duplicated and sorted on write. The canonical serializer
  keeps object keys deterministic.
- `ValidateSaveSection` checks the version, map fields, `request_day` and email
  entries before apply. `ResetSaveSectionState` clears the runtime state when an
  old payload has no section.

### World persistence (`DAIslandSubsystem.*`, `DAInteriorPortal.*`, `DANpcDirector.*`)

- `UDAIslandSubsystem` now implements `IDASavePayloadProvider`, section
  `"world"` (not reserved). It registers from `Initialize` and retries from
  `Tick`, then unregisters in `Deinitialize`.
- Section shape (version 1):

  ```json
  "world": {
    "version": 1,
    "portals": [
      { "id": "academy_classroom_entrance", "locked": false, "used": true }
    ],
    "discovered": ["academy", "academy_arena"],
    "npc_schedule_applied": true,
    "npc_schedule_id": "default",
    "npc_weekday": "Monday",
    "npc_period": "AM",
    "npc_active_event": ""
  }
  ```

  `portals` and `discovered` are always written (possibly empty). The
  `npc_*` fields are written only when a director exists; a section without
  `npc_schedule_applied` leaves the live director untouched.
- `ReadSaveSection` only validates and queues `FDAWorldSaveState`; it does not
  assume actors exist. `ApplyPendingWorldState` is the single idempotent apply
  path and is called from `Tick` (or by a game-mode/test hook):
  - portal state applies through `ADAInteriorPortal::ApplySaveStates`;
  - `discovered` replaces `Discovered` through the new
    `RestoreDiscoveredLocationIds`;
  - an NPC schedule waits for `ADANpcDirector`, then calls
    `RestoreScheduleState`. If no director appears for 10 seconds the schedule
    is dropped (portal/discovery state was already applied) instead of retrying
    forever.
- `ADAInteriorPortal::CollectSaveStates` sorts by id/actor name, skips empty ids
  and keeps one entry per id. `ApplySaveStates` applies only exact ids, keeps the
  first duplicate row, ignores unknown ids and is safe to retry.
- `ADANpcDirector` gained `HasAppliedSchedule()` and
  `RestoreScheduleState(bApplied, ScheduleId, Weekday, Period, ActiveEvent)`.
  The event is set before the schedule so the restored filter is evaluated once;
  a saved "not applied" state restores the `bSpawnOnBeginPlay` baseline rather
  than spawning the wildcard set (P2-WORLD-08).
- Discovery API is additive: `GetDiscoveredLocationIds()` (sorted) and
  `RestoreDiscoveredLocationIds()`.

### Story transactionality (`DAStorySubsystem.*`)

- `InferPendingDuelResult` centralises the counter-based result inference:
  draw first, then tutorial (`wins_syrus`), then `wins_total` with
  `wins_jaden`/`wins_syrus` fallbacks. `Tick`'s open-duel path and the
  recorded-result load path use it.
- The no-HUD restored-pending-duel path resolves as a loss after 10 seconds.
- No story save format change; `SaveState`/`LoadState` remain version 1 with the
  pass-2 additive fields.

## 4. Verification

Commands run (no Unreal process):

| Command | Result |
|---|---|
| `git diff --check -- <all 17 owned source files>` | **PASS** - exit 0; only Git's LF->CRLF advisory warnings |
| Python string/comment-aware brace/paren balance scan over all 17 owned source files | **PASS** - `balanced`, exit 0 |
| `python Tools/validate/validate_all.py` | **PASS** - 0 errors, 15 warnings, 6 gaps, 304 info, 421 files read (baseline warning/gap set; no data changed here) |
| `git status --porcelain` review | Only owned files were changed by this workstream; the pre-existing pass-1/2 working tree remains untouched |

Not run here, owned by the parent: UnrealBuildTool/UnrealEditor and the
headless suites. The new/changed coverage is compile-ready but has not been
compiled or executed in this workstream.

Expected additional checks once the parent runs the suites (baseline -> expected
minimum):

| Switch | Baseline | Added by this workstream |
|---|---|---|
| `-DAPortalTest` | 188 | +25 world save-state checks (round trip, deferred apply, duplicate/unknown/empty ids, missing actor, discovery, restore) -> about 213 |
| `-DANpcScheduleTest` | 514 | +29 world schedule restore checks (queue/apply, idempotency, legacy no-NPC section, no-schedule baseline, snapshot restore, active-set checks) -> about 543 |
| `-DAStoryPlaythroughTest` | 28 | +17 persistence checks (real payload contains `opponents`/`world`, opponent slot round-trip incl. cooldown after load, absent-section defaults, malformed world section rejected before mutation, non-Jaden pending-duel win, draw precedence, calendar untouched) -> about 45 |

`-DAPortalTest` is the PIE/windowed suite; the other two run with
`-game -nullrhi -nosound` as documented in `Docs/PORT_STATUS.md`.

### Test coverage added

- `DAStoryPlaythroughTest` persistence section:
  - malformed `story` section still rejected before profile/calendar mutation;
  - malformed `world` section rejected before mutation (proves new provider
    validation ordering);
  - a real named-slot save is parsed back and asserted to contain the
    `opponents` and `world` root sections;
  - opponent runtime state round-trips through
    `SaveNamedSlotWithContext`/`LoadNamedSlotWithContext`, and the loaded
    `LastRequestDay` still blocks day 11 and allows day `10 + CooldownDays`;
  - a payload without an `opponents` section loads defaults instead of stale
    cooldowns;
  - pending-duel inference recognises a non-Jaden win (`wins_total`) and
    prefers a draw.
- `DAPortalTest`:
  - portal save-state round trip through the world provider;
  - read queues state and does not apply before the deferred pass;
  - re-apply is idempotent;
  - duplicate rows keep the first entry, unknown and empty ids are ignored;
  - an id with no live actor is accepted and does not touch other doors
    (the "actors not there yet" case);
  - discovered ids round-trip;
  - the live world is restored after the probe.
- `DANpcScheduleTest`:
  - schedule/event state round-trips through `WriteSaveSection` /
    `ReadSaveSection` + `ApplyPendingWorldState`;
  - the state is not applied during read;
  - re-apply is idempotent and the active NPC set is re-derived without
    orphans/duplicates;
  - a section without NPC state leaves the live director untouched;
  - a saved `npc_schedule_applied=false` restores the begin-play spawn
    baseline;
  - the live snapshot restores at the end.

## 5. API / serialization impact

Additive C++ APIs (no existing signatures changed):

- `IDASavePayloadProvider::ResetSaveSectionState()` (default no-op).
- `UDAOpponentSubsystem`: `Deinitialize`, save-provider overrides.
- `UDAIslandSubsystem`: `GetDiscoveredLocationIds`,
  `RestoreDiscoveredLocationIds`, `ApplyPendingWorldState`,
  `HasPendingWorldState`, save-provider overrides.
- `ADAInteriorPortal::CollectSaveStates`, `ADAInteriorPortal::ApplySaveStates`.
- `ADANpcDirector::HasAppliedSchedule`, `ADANpcDirector::RestoreScheduleState`.
- `UDAStorySubsystem::InferPendingDuelResult` (private).

Serialization:

- New additive root sections `"opponents"` and `"world"`, both version 1.
- Save schema version stays 1; no migration is required. Older payloads have
  no sections: opponent runtime state resets to defaults, while story,
  inventory, decks, shop and world state keep the pass-2 "live state"
  behavior (world state is deliberately not reset because an old save never
  described it).
- A save written by this build is readable by older builds: unknown root
  sections are ignored. A newer/unknown version inside a section is accepted
  structurally today; the section readers only use known fields.

## 6. Remaining risks and cross-workstream follow-ups

1. **World scope is the current world.** `UDAIslandSubsystem` is a
   world subsystem, so the `"world"` section is registered only while a game
   world exists. The current game loads saves in-place on the single island map
   (the title screen is an overlay), and the deferred pass runs on the next
   world tick. If a future flow loads a slot *before* creating the gameplay
   world, the pending world state would be lost with that world. The clean
   follow-up is a GameInstance-level world-state provider or a loader hook that
   re-reads/reapplies the section after the map exists.
2. **Portal actors must exist by the first deferred apply.** Unknown portal ids
   are dropped by design (content removal, hand-edited saves). If a future
   version streams door actors in later, the provider should keep unresolved
   ids for a bounded grace window instead of applying immediately.
3. **NPC identity is reconstructed, not serialized.** The save persists the
   schedule inputs and `ApplySchedule` re-derives the cast from spawn-point
   configuration. If content changes between save and load, the reconstructed
   cast can differ (documented contract, per the brief's safe-subset option).
   Multiple directors are still not merged: `ADANpcDirector::Get` saves/restores
   the first one only.
4. **Pending-duel HUD contract.** A restored pending duel is re-presented
   through `ADAHUD::OpenDuelDeckSelect` as in pass 2. The new 10-second no-HUD
   fallback records a loss; it is a soft-lock guard, not a headless duel
   simulation. The HUD must still tolerate being asked to reopen the selector
   after a title-screen continue.
5. **Optional immediate-apply hook.** The world state applies on the next world
   tick. If the parent wants the PDA/map fog updated in the same frame as
   `UDASaveSubsystem::LoadSlot`, call
   `UDAIslandSubsystem::ApplyPendingWorldState()` after a successful load (it
   is idempotent). No HUD change is required.
6. **New section names are reserved in practice.** Other workstreams must not
   add providers named `"opponents"` or `"world"`; `BuildPayload` rejects
   duplicate section names and the save would fail.
7. **Absent-section semantics.** `ResetSaveSectionState` is opt-in. If another
   lane adds transient state in its own section, it should override the hook or
   an old save will inherit the previous session's values. The default was left
   as no-op to preserve pass-2 behavior for story/inventory/decks/shop.
8. **Pre-ledger saves.** No compatibility heuristic was added. The reasoning is
   in P3-02-08: event outcomes apply at completion (guarded by the persisted
   completion flag) and choice outcomes apply before the command index advances.
   A save without `applied_outcomes` can still replay a choice only if the save
   was taken at the choice itself, in which case the outcome had not been
   applied yet.
9. **No build/headless run here.** The parent must regenerate UHT headers,
   build, and run the three suites. Expected counts are in section 4; any
   failure in the world provider registration would surface as the
   malformed-world test failing to reject (and as the payload-inspection checks
   failing).
10. **Save rollback of queued world state.** A load that queues world state and
    then fails in a later provider is rolled back by re-queueing the pre-load
    snapshot; the failed load's portal state was not applied at that point. A
    second load in the same frame (before the first deferred apply) is the only
    window where the previous pending state is replaced; normal HUD loads are
    separated by at least one world tick.
