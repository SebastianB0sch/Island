# World Data (A08)

Runtime data for portals, interiors, scene anchors and NPC schedules. All files are validated by
`Tools/world/validate_layout.py` and staged by `DefaultGame.ini` (`DirectoriesToAlwaysStageAsUFS = Data`).

## Files

| File | Contents |
|---|---|
| `location_map.json` | Every GBA Appendix B location → GX zone/point, status, bounds and rationale. |
| `interiors.json` | Portal-cell definitions: origin, bounds, floor/ceiling, entrance/exit portals, props, lighting/nav notes. |
| `portals.json` | 10 paired entrance/exit portals with target transforms, fade, cooldown and lock flags. |
| `anchors.json` | Named camera/player/NPC/stage/prop marks used by story scenes. |
| `spawns.json` | Schedule spawn points with role, dorm, wander radius, Z offset and event override. |

## Coordinate convention

All values are **UE centimetres**:

- `+X` east, `+Y` south (Blender `+Y` is negated), `+Z` up.
- Exterior building yaws are UE yaw: `0` faces `+X`, `90` faces `+Y`, `180` faces `-X`, `270`/`-90` faces `-Y`.
- Portal cells are at `Z = -30000` in a block starting at `(300000, 300000)`.
- `anchor_id` is the canonical way to refer to a position; spawns do not duplicate coordinates.

## C++ mapping

| Data | Class |
|---|---|
| `portals[]` | `ADAInteriorPortal` (`DAInteriorPortal.h`) |
| `anchors[]` | `ADASceneAnchor` (`DASceneAnchor.h`) — data `tags` maps to `AnchorTags` |
| `spawns[]` | `ADANpcSpawnPoint` (`DANpcSpawnPoint.h`) — data `role` maps to `SpawnRole` |
| schedule application | `ADANpcDirector` (`DANpcDirector.h`) |

`ADAInteriorPortal` implements `IDAInteractableInterface`, so the existing “E / interact” focus loop can
open a door prompt without any new UI. `bAutoTrigger` also lets the player walk through.
`GetSaveState()` / `ApplySaveState()` expose the portal lock/visited bits (A02 owns the save schema).

## Lock flags

Portals carry `lock.required_flag` as a data hook. The story/profile layer binds one delegate:

```cpp
ADAInteriorPortal::FlagQuery.BindLambda([](const FString& Flag) { return /* A02 profile query */ false; });
```

Until it is bound, `fail_closed: false` keeps development doors open. Once A02 is live, set
`fail_closed: true` for shipping data so a missing flag never silently unlocks a story door.

## Director contract (stub)

`ADANpcDirector::ApplySchedule(ScheduleId, Weekday, Period)` matches each spawn point if:

- its `event_override` equals the director's active event (event overrides win), or
- `event_override` is empty and `bEventOnly` is false (or an event is active), and
- any `schedule_tags` or the point's `schedule_id` equals any query value; a point with no tags/id is always active.

Weekday/period queries also derive the compact data tags: Monday-Friday add `weekday` plus
`weekday_am`/`weekday_pm`; Saturday/Sunday add `weekend`. The `weekday`/`weekend` schedule ids add the
same aliases. `SetActiveEvent("E24")` re-applies the current schedule. `RefreshSpawnPoints()` rebuilds
the registration map, releases NPCs for removed points, destroys unreachable orphans and re-applies the
current schedule/event (or the `spawn_on_begin_play` set before any schedule). The director is an actor,
does not tick, and only does work when a schedule/event changes or a refresh is requested.

Runtime coverage: `-DANpcScheduleTest` validates all 28 rows against this file, applies Monday-Sunday
AM/PM, exercises `E01`/`E24`/`tutorial_duel` and runs refresh/spawn leak cycles. See
`Docs/World/NPC_SCHEDULES.md`.

## Loading (implemented)

Gate 2 implements the full path:

1. `Tools/dai/assets/interiors.py` builds the 10 cell meshes (3 meshes per cell: Shell / Props / NoCol).
2. `Layout.place_interiors()` exports them at `origin_ue` and appends static/light/text/interact entries.
3. `level.py::Placer.world_actors()` spawns portals, anchors, spawn points and one director from these JSON files,
   tagged `GENERATED_TAG`; `build.py` calls it.
4. Run:

```powershell
python Tools/build_island.py layout
UnrealEditor-Cmd DuelAcademyIsland.uproject -ExecutePythonScript="C:/dev/GX/DuelAcademyIsland/Content/Python/build_island_cli.py"
python Tools/world/validate_layout.py --strict
python Tools/world/test_interiors.py
```

No `.umap` hand-editing and no Blueprint/UMG assets are required.

## ID rules

- Keep ids stable; A03 story commands reference `anchor_id` and portal ids in save data.
- Portal pairs must point at each other (`target_portal_id` symmetry is validated).
- Every `needs_interior` location must have one interior cell, one entrance portal and an anchor.
- Every opening anchor in `anchors.json.opening_anchor_requirements` must exist.
