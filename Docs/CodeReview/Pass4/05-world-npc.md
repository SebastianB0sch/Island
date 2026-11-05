# Pass 4 — WS-05 World & NPC report

Workstream: World & NPC (`DAIslandSubsystem`, `DAInteriorPortal`, `DAInteractable`,
`DALocationVolume`, `DANpcDirector`, `DANpcSpawnPoint`, `DAStudentNPC`,
`DAWorldActors`, `DAPortalTest`, `DANpcScheduleTest`).
Branch `refactor/code-review-pass`, baseline checkpoint `77cc9c7`.

## Scope & constraints

- Static-only verification: no Unreal process was run (per brief). Edits are
  confined to the owned file list; `DACalendarSubsystem`, `DASaveGame`,
  `DAStudentCharacter`, `DAIslandManager`, `DAHUD` were read but never edited.
- Pinned contract #2 (`ADAStudentCharacter::NotifyTeleportArrived()`) is
  consumed portal-side. During my edit window WS-04 landed the declaration
  in `DAStudentCharacter.h:62` with the exact pinned signature; their
  `.cpp` implementation was not yet present at check time. See hand-offs.
- Pinned contract #1 (`FDADuelUI::WasDeckSelectClosedWithoutResult`) does not
  touch WS-05 files; nothing to implement.
- Two workstream overlaps honored: WS-02 owns `DACalendarSubsystem` (I only
  call its public API) and WS-04 owns `DAStudentCharacter` (no edits).

## Findings table

| Id | Sev | Location (as reported) | Status | Notes |
|----|-----|------------------------|--------|-------|
| W1 | MED | `DAInteriorPortal.cpp:299-342`, `:366-369` | **fixed** | Portal-side relocation check; no character edits |
| W2 | MED | `DAIslandSubsystem.cpp` Tick ~100-114 / `DANpcDirector::ApplySchedule` | **fixed** | Calendar→director bridge; dedup + save-restore guard |
| W3 | MED | `DAIslandSubsystem.cpp:568-612` | **fixed** | Unresolved portal ids retry; 10 s window reused/shared |
| W6 | LOW | `DANpcDirector.cpp:257-262` | **fixed** | Re-adopt despawns the previously mapped, still-valid actor |
| W7 | LOW | `DANpcDirector.cpp:425-451` | **fixed** | Destination occupancy recorded; departure claims released |
| W12 | LOW | `DAInteriorPortal.cpp:344-380` | **fixed** | Calls pinned contract #2 (declaration observed in-tree at `DAStudentCharacter.h:62` during my window; implementation still pending WS-04's `.cpp` pass) |
| P4-10 | LOW | `DAIslandSubsystem.cpp:568-612` (restore replace) | **fixed** | Apply path unions discoveries; `RestoreDiscoveredLocationIds` itself keeps its documented "replace" contract (public/test API; also what the probe restore uses) |
| P4-10 tests | LOW | `DAPortalTest.cpp` world-save contract probe | **fixed** | Union + retry/expiry assertions added |
| Extra (scope item 8) | — | `DALocationVolume.*`, `DAInteractable.cpp`, `DAWorldActors.cpp` | **deferred (no action needed)** | Quick-wins pass reviewed: DALocationVolume extent/center sanitization is already sound; interactable bookkeeping (register/Unregister on EndPlay, stale-actor filtering in `UpdateFocus` via `IsValid`+`CanInteract`) already covers focus staleness; no flagged finding offered a change worth the churn |
| All findings | — | as listed | none refused | No proposal was wrong on inspection; nothing deferred among W-findings |

## Changes & rationale

### W1 — no fast-travel cancellation of pending portal teleports (fixed)

`DAInteriorPortal.cpp`:

- `BeginTeleport` now records `TeleportCaptureLocation` (new private member,
  `DAInteriorPortal.h`) — the user's actor location at arm time.
- `FinishTeleport` aborts when the user is farther than
  `PortalRelocationCancelDistance = 500 cm` from that point
  (anonymous-namespace constant). On abort it: logs a warning with the drift,
  **explicitly** `ClearTimer(TeleportTimer)` (the abort must never leave a live
  finish behind), fades in from the camera manager's **current** `FadeAmount`
  (`StartCameraFade(FadeAmount, 0, FadeInSeconds, ...)`, only when the camera
  is still dark) so the screen never stays black, resets `PendingUser`/
  `bTeleportPending`, and returns **without** `ApplyArrival`, without a
  `SetInInterior` change and **without** broadcasting `OnPortalUsed` (no
  in-tree listener; an aborted door use must not record a story beat).
  The linked portal's suppression/cooldown simply expire (cheap, avoids
  ping-pong if the player walks back).
- Rationale for 500 cm: a fast travel moves the player tens to hundreds of
  metres within the 0.35 s fade; human pace covers ≤ ~4 m. Nothing else
  relocates the pawn short-range inside that window (checked: movers are the
  portal itself, `FastTravelTo` and per-frame input).
- Also de-duplicated the PC/camera lookup into a file-local
  `FindFadeController()` helper used by `BeginTeleport`/`FinishTeleport`
  (both code paths had identical 8-line lookups).

### W2 — weekday/period schedule bridge is dead in live play (fixed)

`DAIslandSubsystem.cpp` (+ header):

- New `UpdateScheduleBridge()`, running inside the existing throttled
  (0.25 s) zone-poll block in `Tick`, gated on `!bWorldStatePending` —
  **held while a save restore is queued**; resumes after apply or expiry.
- On its first evaluation it only **primes** the
  (weekday, period) cache (no initial apply — begin play and the save
  restore own the initial cast).
- When `GetWeekdayName(GetWeekday())`/`GetPeriodName(GetPeriod())` change, it
  calls `DANpcDirector::ApplySchedule(Director->GetCurrentScheduleId(),
  Weekday, Period)` — i.e. the director's *strait* current schedule id is
  re-applied against the calendar's filter (save-restored schedules and
  story-pinned ids keep their id). Identical combos are never re-applied
  (cache compare, case-insensitive), and a missing director is a no-op (combo
  is still recorded; first real application stays with its owner).
- The director lookup is only paid when the combo actually changed (zero per
  poll when idle). `Tick` already returns early for non-game worlds
  (headless/editor windows guarded).
- Called with the calendar read-only: `UDACalendarSubsystem::Get(this)`
  (null-safe, verified), `GetWeekdayName`, `GetPeriodName`.

### W3 — partial portal-state restore is permanent (fixed)

`DAInteriorPortal.cpp/.h` + `DAIslandSubsystem.cpp`:

- `ADAInteriorPortal::ApplySaveStates` gained an optional
  `TArray<FString>* OutUnresolvedIds = nullptr` reporting the ids that
  resolved to no live actor (default parameter keeps existing callers
  unchanged; duplicate/empty-id rules untouched).
- `ApplyPendingWorldState` was restructured:
  - portals apply and the queue is **trimmed to exactly the unresolved ids**
    (resolved rows are not re-run — their assignment is idempotent, so the
    idempotency requirement is doubly satisfied);
  - discovery applies merge-once (`bHasDiscoveredState` cleared after the
    pass, `Discovered` reset in retried payloads);
  - the NPC schedule applies once and flips `bHasNpcSchedule` off so a retry
    pass never re-runs `RestoreScheduleState` (its *no-schedule* baseline
    branch is not re-entrant on an already-cleared filter);
  - returns `false` (queue stays alive) while any unresolved row or the
    schedule remains; Tick retries within the same
    `WorldStateDirectorWaitSeconds` (10 s) window and then drops the
    remainder with one generalised warning.
- The tick-time drop logic was extracted into new public
  `UDAIslandSubsystem::ExpirePendingWorldState()` (BlueprintCallable,
  no-op-when-idle) — the same pass, so tests can end the wait deterministically.

### W6 — schedule adoption clobbers foreign NPC (fixed)

`DANpcDirector.cpp` `ApplySchedule`, the `bShouldBeActive && bHasNpc` branch:
if `ActiveNpcs[Id]` holds a *different* still-valid actor than the point's
occupant, broadcast `OnNpcDespawned(Id, Previous)` and destroy it, mirroring
`DespawnAtPoint`'s mismatch handling (`:390-393`), then adopt `PointNpc`. The
normal case (map entry == point occupant) is untouched — verified against
`RunRefreshCases`' "preserves existing NPCs without churn" contract.

### W7 — teleport destination occupancy (fixed)

`DANpcDirector::TeleportNpcToPoint`, before/after the move:

- If the destination point already holds a *different* valid NPC (either in
  the point's own bookkeeping or the active map), the release goes through
  the existing state machine: `DespawnAtPoint(SpawnPointId)` (broadcast,
  bookkeeping release, mismatch destroy). Guard: when the destination already
  records the teleported NPC itself, `DespawnAtPoint` is **not** used (it
  would destroy the actor being moved — it destroys the point's own
  SpawnedNpc).
- After the move, all departure claims are released: any other point whose
  `GetSpawnedNpc == Npc` gets `SetSpawnedNpc(nullptr)` and any other
  `ActiveNpcs` entry valued as that NPC is removed — so the NPC can never be
  double-booked (an `ApplySchedule` at the old point would otherwise re-adopt
  it there; `VerifyActiveSet`'s "no NPC on two points" contract).
- Finally the destination is recorded per `SpawnAtPoint` semantics:
  `ActiveNpcs.Add(SpawnPointId, Npc)` (point id → NPC) and
  `Point->SetSpawnedNpc(Npc)`. A later `ApplySchedule` then either adopts or
  schedule-despawns a single deterministic occupant; the double-spawn bug is
  gone. The moved NPC is *re-keyed* silently (no spawn/despawn broadcast) —
  no in-tree consumer binds those delegates (grep-verified); noted as a
  potential future signal in Remaining risks.

### W12 — pinned contract #2 consumption (fixed)

`DAInteriorPortal::ApplyArrival` now calls
`Character->NotifyTeleportArrived()` right after `SetInInterior(...)`.
Signature per the brief (not present in my read; see hand-offs). Verified
`FastTravelTo` (character, WS-04 scope, `DAStudentCharacter.cpp:544-588`) has
its own focus reset (`FocusedInteractable.Reset()` at `:561`) — **no
hand-off needed for that part**.

### P4-10 — discovered-locations restore wipes same-frame discoveries (fixed)

`DAIslandSubsystem::ApplyPendingWorldState` no longer calls the public
`RestoreDiscoveredLocationIds` (replace) on the queued payload; it unions the
saved ids into the live `Discovered` set, logs the merge
(`"merged %d saved discovered location id(s) ..."`) and clears the discovery
slice of the pending state. The zone poll that ran earlier in the same frame
keeps its discovery. `RestoreDiscoveredLocationIds` itself is unchanged (its
header contract says replace; used by the portal test to restore the probe's
original state).

## Tests

- `DANpcScheduleTest` (`DANpcScheduleTest.h/.cpp`):
  - New W2 case `RunCalendarBridgeCases` + `BridgeCaseTick` stage machine
    (runs after the persistence cases): binds the director's
    `OnScheduleApplied` (UFUNCTION handler `HandleScheduleApplied`), drives
    one `UDACalendarSubsystem::AdvancePeriod()` (PM), waits ≤5 s for the
    island tick's bridge, then asserts (weekday+period gate on **both**
    fields, so a coincidental partial match cannot pass), schedule id/base id
    preserved, event empty, `VerifyActiveSet` against `spawns.json`. Then a
    1 s quiet window asserts **zero** re-applies (identical-schedule dedup),
    `AdvanceDay()` (weekday change; expected period read back from the
    calendar), a second quiet window, unbind, finish. Fully data-driven — no
    assumption about the boot date (expectations are read back from the
    calendar at assert time).
  - W7 case appended to `RunSpawnDespawnCases`: two hops via
    `TeleportNpcToPoint` (empty destination, then occupied destination) —
    occupancy moves without a count change, previous occupant despawned,
    schedule then re-norms both points, and the Monday-AM baseline
    (`VerifyActiveSet`) is restored before the persistence cases.
  - Persistence probes (`RunWorldStatePersistenceCases`) needed no changes:
    every portal id in those sections resolves, so they return true as
    before.
- `DAPortalTest` (`VerifyWorldSaveStateContract`): the hostile-id and
  missing-actor probes now expect the W3 semantics — stay queued (`false`),
  retry stably, resolved flags never re-toggled, and
  `ExpirePendingWorldState()` ends the queue. Two new expiry assertions and
  the P4-10 union assertions (`__test_zone_a__/b` keep any pre-union live
  discoveries). Case totals are counter-derived; no printed totals to update.

## API impact

| Symbol | Change | Compat |
|--------|--------|--------|
| `ADAInteriorPortal::ApplySaveStates` | adds optional `TArray<FString>* OutUnresolvedIds = nullptr` | call-compatible (existing callers unchanged) |
| `UDAIslandSubsystem::ExpirePendingWorldState()` | new BlueprintCallable, no-op when idle | additive |
| `UDAIslandSubsystem::ApplyPendingWorldState` | return `false` now also means "unresolved portal rows pending" (before: director missing only) — documented in header | call-compatible; in-tree callers updated (tests) |
| `ADANpcDirector::TeleportNpcToPoint` | now records destination occupancy + releases departure claims (header doc updated) | signature unchanged |
| `UDAIslandSubsystem::UpdateScheduleBridge` (private) + bridge cache members | new | — |
| `UDANpcScheduleTestSubsystem` | `RunCalendarBridgeCases` / `BridgeCaseTick` / UFUNCTION `HandleScheduleApplied` + stage state | module-internal test |

## Verification (static only)

- All edited files re-read end to end; grep sweeps for stray identifiers
  (`FDAMorld` typo introduced and fixed during editing), leftover
  placeholders, and trailing whitespace (clean).
- Engine header cross-checked: `APlayerCameraManager::FadeAmount` is public
  in `UE_5.8` (`PlayerCameraManager.h:233`, inside `public:` from `:224`) —
  used by the W1 abort path.
- Calendar API semantics verified read-only (`AdvancePeriod` AM→PM→Night→
  `AdvanceDay`; `AdvanceDay` ends in AM; `Get` is null-safe) — both the
  bridge and the test use only those public members.
- W1 drift logic re-checked against every pawn mover in-tree; the portal
  test's `SetActorLocation`-then-`TryUse` flow records the capture **after**
  the move, so no test regression.
- Compilation of `ApplyArrival` depends on pinned contract #2 landing
  (WS-04) — see hand-offs.
- No formatter/whitespace rewrites; `git diff --check` is left to the parent.

## Remaining risks

1. **W12 compile dependency (updated in-flight)**: `NotifyTeleportArrived()`
   is now **declared** (`DAStudentCharacter.h:62`, exact pinned signature,
   landed by WS-04 during my window) but not yet **implemented** in
   `DAStudentCharacter.cpp`. The portal call site resolves once WS-04 lands
   that `.cpp` implementation; nothing further is needed from WS-05.
2. **W1 threshold** (500 cm) is a judgement call: it cannot cancel human
   movement in the fade window and reliably cancels any map fast travel. A
   scripted relocation shorter than 500 cm inside the 0.35 s window would
   still complete the arrival (no such mover exists today).
3. **W2 first application is change-driven**: in a fresh live game the cast
   spawns only on the first weekday/period change (start-up cast remains the
   begin-play baseline, exactly as the P2-WORLD-08 restore semantics expect).
   If A03 later wants day-zero application to the current calendar date, call
   `ApplySchedule(CalendarId, Weekday, Period)` once at story start.
4. **W3 queue lifetime**: `HasPendingWorldState()` may stay `true` up to 10 s
   when portal actors stream in late, even after the schedule/discovery
   slices have applied (they are cleared from the pending state). In-tree
   callers are tests (updated).
5. **W7 silent re-key**: the moved NPC's arrival at the destination is not
   broadcast (`OnNpcSpawned`/spawn-point delegates). No consumer exists;
   if AI/audio start caring, add a broadcast later.
6. **W1 abort leaves the linked portal suppressed** for the remaining
   safety window (seconds). Harmless (auto-expires) and avoids re-trigger
   ping-pong if the player walks right back.

## Integration hand-offs

1. **WS-04 (updated in-flight): pinned contract #2 — declaration already
   landed at `DAStudentCharacter.h:62`; only the implementation remains.**
   Suggested `.cpp` body (near `SetInInterior`, `DAStudentCharacter.cpp:767`):

   ```cpp
   void ADAStudentCharacter::NotifyTeleportArrived()
   {
       // Strictly focus-clearing per the pinned contract; the next focus poll
       // re-acquires from the arrival point.
       FocusedInteractable.Reset();
   }
   ```

   No WS-05 edits depend on any specific implementation beyond "it clears the
   focus"; the exact body is WS-04's call.

2. **Verified, no hand-off**: `FastTravelTo` already resets focus itself
   (`DAStudentCharacter.cpp:561`), so portal W1/W12 need nothing more from
   WS-04. If WS-04 refactors that method in the pass, keep the
   `FocusedInteractable.Reset()` line.

3. **WS-02 note (no edit required by them)**: the bridge reads only public
   calendar getters; if `GetWeekdayName/GetPeriodName` ever rename, the
   compile breaks in `DAIslandSubsystem.cpp` (`UpdateScheduleBridge`) and
   `DANpcScheduleTest.cpp` (both mine).

## Integration addendum (parent)

The W2 bridge as originally landed held while `bWorldStatePending`, which the
W3 portal retry legitimately extends to 10 s — longer than the schedule test's
5 s stage timeout — and every baseline re-prime taken from the calendar
respectively swallowed a calendar change the game mode / test had already
performed. Final integrated mechanism (parent, verified by the full gate
fleet):

- The bridge is suppressed only on the single zone poll that follows a pass
  of `ApplyPendingWorldState` that materializes the saved NPC schedule
  (apply-once or a missing-director hold). The suppression flag is consumed
  on read; unresolved portal-id retries never block the bridge.
- `ADANpcDirector::ApplySchedule` — the single notifying path per pass 3 —
  now reports to the island via `UDAIslandSubsystem::NotifyScheduleApplied`,
  so any producer (director begin play, save restore, event override, tests)
  re-baselines the bridge to the combo it just applied.
- When un-primed (cold start or post-hold resume), the baseline is the
  director's own applied combo if it has one; the calendar is only the
  fallback while no director has ever applied a schedule. A calendar-based
  baseline would swallow the difference between the director's state and the
  current calendar moment.
- `DANpcScheduleTest`'s bridge stage machine resets `BridgeApplications` at
  each stage-pass edge; the quiet-window dedup assertions assumed that reset.
- Final result: `-DANpcScheduleTest` 568 passed / 0 failed (the 13 new bridge
  checks included), `DAPortalTest` 333/0 unchanged.
