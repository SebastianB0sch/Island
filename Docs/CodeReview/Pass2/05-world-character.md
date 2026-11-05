# 05 — World, character, NPC and portal layer (pass 2)

Branch: `refactor/code-review-pass`

## Scope and constraints

Scope: `DAStudentCharacter.*`, `DAAvatarComponent.*`, `DAAvatarAnimInstance.*`,
`DAStudentNPC.*`, `DANpcDirector.*`, `DANpcSpawnPoint.*`, `DAWorldActors.*`,
`DAInteractable.*`, `DAInteriorPortal.*`, `DAPortalTest.*`, `DAIslandManager.*`,
`DAIslandSubsystem.*`, `DALocationVolume.*`, `DASceneAnchor.*`, `DASettings.*`,
and this report.

The uncommitted pass-1 work is the baseline. No UI, duel, persistence, effect,
Python, asset or generated-data files were changed. Public API additions are
limited to `ADAStudentNPC::SetWanderHome`; other changes are private helpers,
member state or behaviour inside existing functions. No serialized format was
changed. No UnrealBuildTool/UnrealEditor run was attempted; the parent owns the
combined build and headless runs.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| P2-WORLD-01 | High | `DANpcSpawnPoint::SpawnNpc` | The spawn point configured `Dorm`, `WanderRadius` and `DisplayName` **after** `SpawnActor`, which already runs NPC `BeginPlay`. NPCs therefore always began with the default Slifer dorm, 800 cm wander radius and no display name. The named-duelist mapping (`bDuelist`, opponent id, deck id) never ran for scheduled named NPCs. | Fixed: deferred spawn (`SpawnActorDeferred`), configure the NPC, then `FinishSpawning`. |
| P2-WORLD-02 | High | `ADAStudentCharacter::FastTravelTo` | Fast travel did not clear `bInInterior`. After travelling from an interior cell the character stayed flagged as indoors: swimming was disabled and the fall-out-of-world rescue never ran again. | Fixed: clear interior/sprint/focus, re-anchor the safe location at the destination. |
| P2-WORLD-03 | Medium | `DAStudentCharacter::Tick` / `PawnClientRestart` | Sprint was only cleared by the shift-released event. A map/duel/PDA input mode can swallow that event, leaving `bSprinting` true after closing the UI; a repossessed pawn also inherited the old sprint flag. | Fixed: clear sprint while movement is blocked or the pawn has no controller, and on client restart. |
| P2-WORLD-04 | Medium | `DAStudentCharacter::UpdateFocus` | Focus used the character's facing (last movement direction), not the camera/control rotation, and ignored `CanInteract` and hidden actors. Turning the camera without moving could select an object behind the player. | Fixed: use control yaw, skip hidden actors and actors that currently reject interaction. |
| P2-WORLD-05 | Medium | `DAAvatarAnimInstance::SetAction` / `NativeUpdateAnimation` | A one-shot action (notably `Land`) that had faded out kept its clamped `ActionTimeA`; re-triggering the same take resumed its last frame instead of restarting. Rapid Jump -> Fall -> Land switches also overwrote the outgoing crossfade slot with a barely-visible pose. | Fixed: restart cleared one-shots, keep the stronger outgoing action, and release finished action slots at zero weight. |
| P2-WORLD-06 | Medium | `DAAvatarComponent::TickNative` | Landing detection required `VerticalSpeed < -50` on the frame after `IsFalling()` became false, by which time character movement has usually zeroed vertical velocity. The `Land` take could be skipped entirely. | Fixed: remember the last airborne descent speed and use it on touchdown. |
| P2-WORLD-07 | Medium | `DANpcDirector::RegisterSpawnPoint` / `RefreshSpawnPoints` | A duplicate spawn-point id overwrote the first registration (or kept an arbitrary first actor on refresh), orphaning the NPC already spawned by the replaced point. | Fixed: keep the first valid registration, warn, release the losing point's NPC, and sort spawn points by id/name before resolving duplicates. |
| P2-WORLD-08 | Medium | `DANpcDirector::SetActiveEvent` | Calling `SetActiveEvent` before any schedule had been applied re-ran an empty (wildcard) filter, spawning every spawn point. | Fixed: record the event and defer re-application until a schedule exists. |
| P2-WORLD-09 | Medium | `DANpcDirector::ApplySchedule` | Spawn order came from `TMap` key iteration, which is not a deterministic spawn contract. A destroyed spawn point also dropped its `ActiveNpcs` entry without destroying the NPC, leaving an owner-only orphan. | Fixed: sort ids, and destroy/broadcast the orphan when its point is gone. The active map is also re-adopted from the point if it was stale. |
| P2-WORLD-10 | Medium | `DANpcDirector::TeleportNpcToPoint` / `MoveNpcToLocation` | Moving an NPC did not update the wander anchor; it immediately strolled back to its BeginPlay location. | Fixed: `ADAStudentNPC::SetWanderHome` re-anchors home/target and stops residual movement. |
| P2-WORLD-11 | Medium | `DAInteriorPortal::ApplySaveState` | An empty `FDAPortalSaveState::PortalId` was treated as a wildcard and applied to every portal, so a malformed payload could overwrite all door locks/used flags. | Fixed: only apply an exact non-empty id. |
| P2-WORLD-12 | Medium | `DAInteriorPortal::FindLinkedPortal` / begin play | Portal links were never validated: missing targets, self-links, one-sided pairs and duplicate ids silently fell back or resolved by actor iteration order. | Fixed: one-time pairing validation with warnings and deterministic (name-ordered) duplicate resolution; duplicate-target and reciprocity checks added to `-DAPortalTest`. |
| P2-WORLD-13 | Medium | `DAInteriorPortal::FinishTeleport` / `EndPlay` | If the user disappeared during the fade-out, or the portal was destroyed mid-transition, the camera stayed faded to black because the fade-in only ran for a live pending user. | Fixed: always fade back in, and clear the fade when a pending teleport is cancelled by `EndPlay`. |
| P2-WORLD-14 | Low | `DAInteriorPortal::TryUse` / `SuppressFor` | An unconfigured portal teleported to world origin; stacked suppression timers could clear a newer suppression. | Fixed: refuse a portal with no reachable destination, and refresh the suppression timer. Preserve look pitch on arrival (yaw only from the door). |
| P2-WORLD-15 | Low | `DAInteractable::OpenBoosterPack` | The card catalogue was indexed without an empty/range guard. | Fixed: message and return on an empty catalogue; skip an invalid pull index. |
| P2-WORLD-16 | Low | `DAInteractable` RoomBed | Sleeping advanced the calendar but not the visual time-of-day manager, so lighting/clock stayed on the old day. | Fixed: set the manager hour from the calendar after `Sleep()`. |
| P2-WORLD-17 | Low | `DAIslandManager::SetHour` / `AdjustTimeSpeed` | `SetHour` accepted NaN/negative input and rolled the visual day label only in `Tick`; a period skip across midnight left the label one day behind. `AdjustTimeSpeed` could latch a NaN. | Fixed: validate input, count whole-day and midnight-crossing jumps, and recover a non-finite speed. |
| P2-WORLD-18 | Low | `DAIslandSubsystem::UpdateCurrentZone` / `GetZones` | Equal-volume zones and equal `SortOrder` entries resolved by registration/iteration order; a negative extent could win the smallest-zone test. | Fixed: deterministic volume -> `SortOrder` -> `LocationId` tie-break; `GetZoneVolume`/`ContainsPoint` use absolute extents. |
| P2-WORLD-19 | Low | `DASettings::ReadJson` | Settings were mutated field by field while parsing; a wrong-typed field could leave a partially applied settings object. Numeric values were not type-checked before coercion. | Fixed: strict optional-field type validation into locals, clamp volumes, commit and broadcast only after the whole object validates. |
| P2-WORLD-20 | Low | `DAWorldActors` | Negative/NaN emitter `Rate`, `EffectScale`, floating `Period`/`Amplitude`, lighthouse length/speed or ambience radius/volume could produce NaN transforms or invalid attenuation. | Fixed: finite/clamped normalisation at begin play. |
| P2-WORLD-21 | Low | `DAPortalTest` | A missing pawn/portal during `BeginEntry` advanced the index but stayed in the “wait for entry” stage, cascading misleading failures. Portal pairing and save-state contracts were untested. | Fixed: reset the stage on failure; added pairing/duplicate/reciprocity, cooldown and save-state round-trip checks. |
| P2-WORLD-22 | Info | `DASceneAnchor.*` | No lifecycle/state defect found. | Audited; no change. |

## Changes made

### Character, avatar and animation
- `DAStudentCharacter.cpp`: sprint cleanup on blocked input/no controller and
  `PawnClientRestart`; fast travel clears interior/swim/focus/sprint state and
  re-anchors `SafeLocation`; focus uses control yaw, ignores hidden actors and
  checks `CanInteract`; swimming falls back safely when the island subsystem is
  unavailable; leaving an interior cell re-anchors the fall rescue.
- `DAAvatarComponent.*`: track the last airborne vertical speed for reliable
  landing takes.
- `DAAvatarAnimInstance.cpp`: restart a cleared one-shot, preserve the stronger
  outgoing crossfade pose during rapid action switches, and release finished
  action slots.

### NPC schedule/director
- `DANpcSpawnPoint.cpp`: deferred spawn so all per-point properties exist before
  the NPC's `BeginPlay`. This restores dorm tint, wander radius, display names
  and the named-duelist deck/opponent id.
- `DAStudentNPC.*`: additive `SetWanderHome` used by director moves; null-world
  guards around interaction timestamps.
- `DANpcDirector.cpp`: deterministic duplicate registration/refresh, sorted
  schedule evaluation, destroyed-point orphan cleanup, active-map re-adoption,
  event-before-schedule guard, and wander re-anchoring on teleport/move.

### Portals and interiors
- `DAInteriorPortal.*`: pairing validation, deterministic duplicate link
  resolution, destination validation, exact-id save application, suppression
  timer refresh, camera fade recovery, and pitch-preserving arrival yaw.
- `DAPortalTest.*`: new pairing/reciprocity/duplicate-target checks, cooldown
  check at use time, save-state contract checks, and a stage-reset fix.

### World actors, zones, interactables
- `DAInteractable.cpp`: empty-catalogue guard, safe pull index, visual hour sync
  after resting.
- `DAWorldActors.cpp`: finite/clamped emitter, floating, lighthouse and ambience
  parameters.
- `DAIslandManager.cpp`: validated hour/time-speed input and day-label rollover.
- `DAIslandSubsystem.cpp`, `DALocationVolume.cpp`: deterministic zone selection
  and absolute extents/volume.
- `DASettings.cpp/.h`: transactional, type-checked JSON read with clamped
  volumes and a single change broadcast.

## Verification performed

| Check | Result |
|---|---|
| `git diff --check` on every scoped source file | **PASS** (only Git's LF→CRLF notices) |
| Data contract scan: `portals.json` | 20 portals, 10 entrance / 10 exit, all ids unique, all reciprocal targets present |
| Data contract scan: `spawns.json` | 38 spawn points; 16 `spawn_on_begin_play` entries exercised by the deferred-spawn path |
| `DANpcScheduleTest` / `DAPortalTest` execution | Not run here — both require an Unreal process, which this workstream is not allowed to start. The parent must run them after the combined build. |
| Scoped compiler syntax check | Not possible from the cached UBT response files: the `Intermediate/.../*.generated.h` files are stale relative to the current headers (`DASaveGame.generated.h`, etc.), so `cl /Zs` fails in UHT boilerplate before reaching the changed code. The parent UBT build will regenerate them. |

`DAPortalTest` gained checks beyond the pass-1 baseline (188/188); the exact
count will be reported by the parent's headless run.

## Remaining risks / contracts

1. **NPC schedules are not production-wired or saved.** `ADANpcDirector::ApplySchedule`
   has no gameplay caller outside tests; only `bSpawnOnBeginPlay` points are
   active in a normal session. `CurrentScheduleId`, `CurrentWeekday`,
   `CurrentPeriod`, `ActiveEvent` and spawned/despawned NPC state are not in the
   save payload. Contract: the story/game-mode owner must reapply the current
   schedule and event after loading, or the director needs an additive save
   payload provider (persistence-layer work).
2. **Portal save state is defined but not wired.** `FDAPortalSaveState` is not
   included in the save payload. Contract: apply states by exact `PortalId`;
   empty ids are ignored. A future save section should collect each portal's
   `GetSaveState()` and call `ApplySaveState` after level load.
3. **Zone discovery is session-only.** `UDAIslandSubsystem::Discovered` is not
   persisted, so “Explored n / m” and map fog reset on load. This is a
   save-layer contract, not changed here.
4. **Legacy card-shop interaction remains cosmetic.** The `CardShop` prop's
   `[E]` pull uses the legacy 32-card list and the character's transient
   `TSet`; it does not touch `UDAInventorySubsystem`. The real shop/inventory
   path is separate (out of scope for this workstream).
5. **Interaction focus has no occlusion test.** Camera direction and
   `CanInteract` are respected, but a target behind a counter/wall can still be
   focused. A visibility trace was deliberately not added because counters and
   shop desks would then block otherwise valid NPC interactions.
6. **Visual day label is heuristic.** `ADAIslandManager::GetClockText` uses a
   session day counter, not the campaign date. Crossing midnight through `N`
   and long backwards jumps are counted, but sleeping from afternoon to morning
   can leave the visual day label one behind the calendar. The calendar remains
   authoritative for gameplay gates.
7. **NPC talk/pack counters are transient.** `ADAStudentNPC::bHasTalked` and
   `ADAInteractable::PacksOpened` are not saved; talk progress is reconstructed
   from story/profile state where applicable.
8. **Runtime moves of floating actors snap back.** `ADAFloatingActor` captures
   its base transform at `BeginPlay`; a runtime relocation should update the
   base (no such caller exists today).
9. **Multiple directors.** `ADANpcDirector::Get` returns the first actor found;
   multiple directors in one level are not merged or diagnosed beyond the
   per-id duplicate warnings.
10. **Content mismatch (not changed here).** `settings.json` / `BuildDefaultControls`
    still advertise `DuelDisk = J`, while the character binds duel disk to `F`
    and jacket to `J`; data/UI ownership is outside this scope.
