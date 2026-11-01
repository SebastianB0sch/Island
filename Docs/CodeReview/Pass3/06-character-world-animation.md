# 06 - Character, avatar/animation, NPC, world actors, time and settings (pass 3)

Branch: `refactor/code-review-pass`

## Scope and constraints

Scope: `DAStudentCharacter.*`, `DAAvatarComponent.*`, `DAAvatarAnimInstance.*`,
`DAStudentNPC.*`, `DAWorldActors.*`, `DAInteractable.*`, `DAIslandManager.*`,
`DALocationVolume.*`, `DASettings.*`, and this report.

The uncommitted pass-1/pass-2 tree is the baseline; those edits were not
reverted or reformatted. Files owned by workstream 02 (`DANpcDirector`,
`DANpcSpawnPoint`, `DAInteriorPortal`, `DAIslandSubsystem`, `DASaveGame`) were
read but not edited. No game data, save payload, UI, asset or build file was
changed. No UnrealBuildTool/UnrealEditor/Blender run was attempted; the parent
owns the combined build, headless runs and renderer checks.

Public API impact: one additive method, `ADAIslandManager::SetCalendarTime`,
plus an `EndPlay` override and a private calendar handler. No existing public
signature was removed or changed. No serialized format changed.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| P3-06-01 | High | `ADAIslandManager::Tick` | Day rollover used `while (Hour >= 24)`. A tiny `DayLengthMinutes` (including a serialized/Blueprint value below the editor minimum) or a long hitch could make one frame hang. `Hour`, `TimeSpeed` and `DayLengthMinutes` were used without finite/recovery checks. | Fixed: double-precision arithmetic rollover, saturating day count, and finite/clamped time settings. |
| P3-06-02 | High | `ADAIslandManager::BeginPlay` / `GetClockText` | The visual "Day N" label started at 1 and only guessed at midnight crossings. A loaded campaign day, a story date jump and a sleep from afternoon to morning left the label behind the calendar. The existing `OnVisualHourChanged` bridge was never bound. | Fixed: bind the calendar's visual-hour delegate and set both campaign day and hour; `Day` is now authoritative while a calendar is bound. |
| P3-06-03 | Medium | `ADAStudentCharacter::OnInteract` | The 0.3 s "ignore the key press that just opened a message" guard was bypassed by a fallback branch that dismissed any active message, so the guard had no effect. | Fixed: a message with no focused target now returns, and only dismisses after 0.3 s. |
| P3-06-04 | Medium | `ADAStudentCharacter::FastTravelTo` / fall rescue / `SetInInterior` / `UpdateSwimming` | Fast travel and fall rescue cleared `bSwimming` but not `SwimAlpha` (avatar stayed prone while standing) and could leave a stale flying/swimming movement mode. Entering an interior left the prone pose to fade out indoors. When the island subsystem was missing, `UpdateSwimming` returned before its `SwimAlpha` interpolation, so a previously swimming avatar could stay prone forever. | Fixed: snap `SwimAlpha`/avatar swim alpha to zero, clear stale fly/swim modes, and keep fading the swim blend on the no-subsystem path; the existing destination rescue anchor is preserved. |
| P3-06-05 | Medium | `ADAStudentCharacter::Tick` focus update | Focus was recomputed while the map/duel/PDA/dialogue UI was open. `ADAHUD::DrawPrompt` does not check UI state, so a hidden target behind a modal could still be shown/interacted with after closing the UI. | Fixed: clear focus and skip acquisition while `IsMovementBlocked()`. |
| P3-06-06 | Medium | `DAAvatarComponent::TickNative` | A `Land` take that was still counting down could replay (or hold its tail) after a later short hop or soft step-down, because `LandTimer` was only replaced on a hard landing. | Fixed: clear `LandTimer` when a new air phase starts; documented the `-50 cm/s` soft-step heuristic. |
| P3-06-07 | Medium | `DAAvatarComponent::BeginPlay` | `BodyScale` of zero/NaN makes the figure invisible or emits NaN transforms; a zero `StrideSpeed` can divide by zero in the procedural gait. | Fixed: clamp `BodyScale` to a finite positive range and `StrideSpeed` to at least 1. |
| P3-06-08 | Low | `DAAvatarAnimInstance::NativeInitializeAnimation` | A reinitialised instance inherited action slots, loops, play rates and blend values from its previous mesh/source. | Fixed: reset action and locomotion blend state on initialization. |
| P3-06-09 | Medium | `ADAStudentNPC::BeginPlay` | A negative/NaN `WanderRadius` produced NaN wander targets; NaN never compares below the stop distance, so the NPC kept pushing forever. `StrollSpeed` was also unvalidated. | Fixed: finite, non-negative radius and finite positive stroll speed. |
| P3-06-10 | Low | `ADAInteractable::BeginPlay` | A NaN `Radius` passes the focus distance comparison (`Horizontal > NaN` is false) and makes the actor interactable from anywhere. | Fixed: finite, non-negative radius with a 300 cm fallback. |
| P3-06-11 | Low | `ADAAmbientSound::BeginPlay` | The random start offset was always `0..5 s`; a sound shorter than that could be seeked past its end and stay silent. | Fixed: clamp the start offset below the clip duration. |
| P3-06-12 | Low | `ADALighthouseBeam::Tick` | A non-finite or out-of-range night factor propagated NaN/invalid intensity into both spotlights. | Fixed: finite clamp to `[0, 1]`. |
| P3-06-13 | Low | `ADALocationVolume::OnConstruction/BeginPlay` | Negative or non-finite extents poisoned the box and the smallest-zone volume test; a non-finite spawn location/yaw could teleport the player to NaN. | Fixed: absolute/finite extents, finite yaw, and a centre fallback for a non-finite spawn point. |
| P3-06-14 | Low | `UDASettings::ReadJson/ResetControl` | Control action keys were not trimmed or validated (a whitespace-only key was stored), and `ResetControl` broadcast a change even when the control was already at its default or did not exist. | Fixed: normalize/reject empty action keys and only broadcast a real change. |
| P3-06-15 | Low | `UDASettings::BuildDefaultControls` | The default control display string said `DuelDisk = J`, but the character binds duel disk to `F`; the same stale value remains in `settings.json`. | Fixed in code to `F`; the data file still needs the cross-workstream update noted below. |
| P3-06-16 | Info | `ADAEmitter`, `ADAFloatingActor` | Pass-2 finite/period/rate clamps and fixed particle counts already cover the NaN, zero/negative-period and unbounded-spawn cases. Re-audited; no new defect. | Audited; no change. |
| P3-06-17 | Info | `DAAvatarAnimInstance::SetAction/Evaluate` | Pass-2 crossfade retention, one-shot restart and zero-weight slot release are internally consistent; remaining choices are intentional heuristics. | Audited; comments only. |
| P3-06-18 | Info | `UDASettings::ReadJson` | Type-checked optional fields, volume clamping, transactional commit and a single post-commit broadcast are already in place. Existing `DAA02GateTests`/`DAProfileSelfTest` paths cover round-trip and malformed data. | Audited; no additional defect. |
| P3-06-19 | Info | `DALocationVolume` zone tie-break | Pass 2's absolute-extent containment/volume and the subsystem's volume -> `SortOrder` -> `LocationId` order remain correct. Extents are now normalized at construction as well. | Audited; hardening in P3-06-13. |

## Changes made

### Movement / input lifecycle (`DAStudentCharacter.cpp`)
- `OnInteract`: fixed the ineffective 0.3 s message guard (P3-06-03).
- `FastTravelTo`: resets swim state/visual alpha, clears a stale flying or
  swimming movement mode, keeps the destination rescue anchor, and keeps the
  existing interior/sprint/focus cleanup.
- Tick focus update: clears focus and skips acquisition while any modal UI
  blocks movement (P3-06-05).
- Fall rescue: full swim/mode reset before moving to the safe point.
- `SetInInterior(true)`: snaps the swim pose off when entering a cell.
- `UpdateSwimming` without an island subsystem: still interpolates `SwimAlpha`
  to zero instead of returning with a stuck prone pose.
- `OnTimeSkip` and `DAInteractable` room rest now pass the calendar's absolute
  day and hour through the new `SetCalendarTime` instead of only setting the
  hour.

### Avatar / animation (`DAAvatarComponent.cpp`, `DAAvatarAnimInstance.cpp`)
- Clear `LandTimer` on a new air phase and document the soft-landing threshold.
- Validate `BodyScale`/`StrideSpeed` before the skeletal or procedural path runs.
- Reset all action-slot and blend state in `NativeInitializeAnimation`.
- No action-selection or crossfade behavior was rewritten; the pass-2 two-slot
  action layer is unchanged.

### NPC / interactables (`DAStudentNPC.cpp`, `DAInteractable.cpp`)
- Sanitize wander radius/stroll speed, guard the ledge trace against a missing
  world, and sanitize interaction radius.
- Room rest uses the calendar day/hour sync path. Existing empty-catalogue,
  pull-index, talk-timer and reward paths were re-audited; no new persistence
  state was added (workstream 02 owns saving talk/pack state).

### World actors (`DAWorldActors.cpp`)
- Ambient start offset respects the clip duration; lighthouse intensity
  rejects a non-finite night factor. Emitter/floating maths were re-audited and
  left as pass 2 (finite values, clamped periods/rates, fixed counts).

### Island manager / location volumes (`DAIslandManager.*`, `DALocationVolume.cpp`)
- Replaced the day-rollover loop with arithmetic and saturating day counts
  (P3-06-01), added finite settings recovery, and made clock text defensive.
- Bound `UDACalendarSubsystem::OnVisualHourChanged` in `BeginPlay` and unbound it
  in `EndPlay`; `SetCalendarTime` sets campaign day and visual hour from the
  calendar. When a calendar is bound, neither the tick nor `SetHour` changes the
  day label; the calendar remains authoritative. Without a calendar, the old
  session-day fallback still applies.
- Sanitized negative/NaN zone extents in construction/begin play, validated
  spawn yaw, and replaced a non-finite spawn location with the zone centre.

### Settings (`DASettings.cpp`)
- Trim/reject empty control action keys during JSON read, normalize reset
  broadcasts, and correct the fallback `DuelDisk` display string to `F`.
- JSON schema, types, clamping, defaults and commit order remain unchanged.

## Verification performed

| Check | Command | Result |
|---|---|---|
| Whitespace / diff sanity on every scoped file | `git diff --check -- <10 changed files>` | **PASS** (only Git LF->CRLF notices; no whitespace errors) |
| Structure / brace balance | `python C:\Users\Sebas\AppData\Local\Temp\opencode\gx_ws06_brace_check.py <10 changed files>` | **PASS** - all 10 files reported `balanced` |
| Duel-disk default consistency | `Select-String ... DuelDisk` over `DASettings.cpp`, `DAStudentCharacter.cpp`, `settings.json` | C++ default and binding both `F`; JSON still `J` (cross-workstream item below) |
| Unreal self-tests / headless run | not run | Forbidden for this workstream; parent must run `DAA02GateTests`, `DAProfileSelfTest`, `DANpcScheduleTest`, `DAPortalTest` after the combined build |
| Renderer / visual checks | not run | No Unreal process; animation, swim pose, lighthouse and camera behaviour still need a renderer |

Changed files:

- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAStudentCharacter.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAAvatarComponent.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAAvatarAnimInstance.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAStudentNPC.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAWorldActors.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAInteractable.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAIslandManager.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/DAIslandManager.h`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DALocationVolume.cpp`
- `DuelAcademyIsland/Source/DuelAcademyIsland/Private/DASettings.cpp`
- `Docs/CodeReview/Pass3/06-character-world-animation.md` (this report)

No file outside this list was edited.

## Remaining risks and cross-workstream follow-ups

1. **Data/UI must update the duel-disk default.** `DASettings.cpp` now defaults
   `DuelDisk` to `F`, matching `ADAStudentCharacter` (F) and its header. The
   loaded value in `DuelAcademyIsland/Content/Data/Profile/settings.json` is
   still `"DuelDisk": "J"` and overrides the default; any title/PDA help text
   that says J for the duel disk should also change. The data/UI owner must
   update the JSON (game data is outside this workstream).
2. **Visual time is still a 24-real-minute loop, while calendar periods advance
   only on story/N/sleep events.** With a calendar bound, the clock's `Day` is
   now the campaign day and only the calendar moves it; the hour still loops.
   Confirm with design/HUD that a fixed campaign day across repeated visual
   midnights is the intended presentation. Without a calendar the old
   session-day fallback remains.
3. **Calendar binding needs the parent's runtime check.** The delegate is
   unbound in `EndPlay` and the manager reads the calendar on `BeginPlay`, so
   save-load order should be safe (the calendar persists in the GameInstance).
   The parent should verify loading a save at a later date shows the matching
   day/hour rather than `Day 1`.
4. **Focus still has no occlusion trace.** This pass only stops focus behind
   modal UI; a target behind a counter can still be focused, as documented in
   pass 2. A visibility probe was deliberately not added because counters and
   shop desks would block valid interactions.
5. **Fall rescue and fast-travel anchors remain heuristic.** A runtime move of
   a floating actor, moving platform or streamed landing pad can still leave an
   old anchor; no such caller exists today. Rescue also assumes `SafeLocation`
   is a valid island point.
6. **NPC talk/pack counters remain transient.** `bHasTalked`,
   `ADAInteractable::PacksOpened` and `ADALocationVolume` discovery are not in
   the save payload; workstream 02 owns persistence. No new save state was
   wired here.
7. **Test coverage is outside this workstream's file set.** Existing
   `DAA02GateTests` (settings/type/fuzz/save round-trip) and
   `DAProfileSelfTest` (settings persistence) should be run by the parent.
   There is no character/world/animation self-test file in the owned scope, so
   no new Unreal test source was added. Suggested parent-side checks: clock
   day/hour after `SetCalendarTime`, no day move when `SetHour` is called with a
   bound calendar, a tiny `DayLengthMinutes` tick does not hang, and the
   `OnVisualHourChanged` binding survives save load.
8. **No renderer validation.** Swim-pose snap, land-take suppression, ambient
   phase offsets and lighthouse intensity are verified only by source review;
   the parent must inspect them in a running build.

## Parent integration follow-up

- `settings.json` now uses `"DuelDisk": "F"`, matching the code fallback and the
  character binding.
- The calendar-bound visual clock, starter-deck/economy reset and the world
  persistence providers were exercised by `-DAStorySelfTest`,
  `-DAStoryPlaythroughTest`, `-DANpcScheduleTest` and `-DAPortalTest`; all pass.
- `DAA02GateTests` compiled and the save-fuzz suite passed 67,505 checks.
