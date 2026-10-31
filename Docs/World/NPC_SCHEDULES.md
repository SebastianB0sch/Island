# NPC Schedules and Gate 3 Runtime

> **Owner:** A08. **Test switch:** `-DANpcScheduleTest` (GameInstanceSubsystem, headless, exits after the summary).
> **Data:** `Content/Data/World/spawns.json` (28 spawn points). **Code:** `DANpcSpawnPoint`, `DANpcDirector`, `DANpcScheduleTest`.
> **Build placement:** `Content/Python/duel_academy/level.py::Placer.interior_nav()` for the ten interior nav volumes.

## Run

```powershell
# Editor/headless build (orchestrator): regenerates actors, nav volumes and saves the level.
UnrealEditor-Cmd DuelAcademyIsland.uproject -ExecutePythonScript="C:/dev/GX/DuelAcademyIsland/Content/Python/build_island_cli.py"

# PIE/standalone runtime checks.
UnrealEditor.exe DuelAcademyIsland.uproject -game -DANpcScheduleTest -log
# or PIE with the same switch in the editor command line.
```

The test waits for `UWorld::HasBegunPlay`, finds the single `ADANpcDirector` and all `ADANpcSpawnPoint` actors, then runs its checks in one pass and requests exit after logging the summary.

Expected healthy summary line:

```text
NPC schedule test: 414 passed, 0 failed. ALL PASS
```

Every individual line is `PASS: ...` on `LogDuelAcademyIsland`; failures are `FAIL: ...` at `Error` severity. A failure summary ends with `FAILURES PRESENT`. The exact total is 414 with the current 28 spawn rows and 8 opening requirements; adding rows increases the registration checks.

## What the test verifies

1. **Registration and data parity**
   - one director, 28 spawn actors and 28 registered ids (auto-registration from `BeginPlay`);
   - data ids unique, runtime ids unique, every runtime id exists in JSON and vice versa;
   - all 8 `opening_spawn_requirements` are registered;
   - per row: `ScheduleId`, `ScheduleTags`, `EventOverride`, `bEnabled`, `bEventOnly` and `bSpawnOnBeginPlay` match `spawns.json`.
2. **Full week** — applies `ApplySchedule("default", <weekday>, <AM|PM>)` for Monday through Sunday. The expected active set is recomputed from the JSON with the same contract as `MatchesSchedule`:
   - `EventOverride` wins;
   - `bEnabled == false` never activates;
   - `bEventOnly` requires a non-empty active event when there is no override;
   - Monday–Friday derive `weekday`, `weekday_am`/`weekday_pm`; Saturday/Sunday derive `weekend`;
   - tags or `ScheduleId` match any query value, case-insensitively.
   With the current data the sets are Monday–Friday AM = 12, Monday–Friday PM = 10, Saturday/Sunday AM/PM = 7.
3. **Events** — `tutorial_duel` activates `academy_arena_jaden`; `E24` activates `abandoned_dorm_titan` and `volcano_shadow_duelist`; `E01` activates the four gym assembly points; restoring the empty event returns the default Monday AM set.
4. **Deterministic spawn/despawn** — `DespawnAtPoint`/`SpawnAtPoint` are idempotent, an unknown id returns null, a temporary `bEnabled = false` and a temporary `bEventOnly = true` behave correctly, and the NPC count returns to the baseline after each cycle.
5. **Refresh cycles** — three `RefreshSpawnPoints()` calls must keep 28 registrations, preserve existing NPCs without churn, re-apply the active schedule, apply PM from AM, restore AM, and leave zero orphan NPCs.

## Director fixes in Gate 3

- `RefreshSpawnPoints()` now snapshots the old registrations/active map, rebuilds registrations, releases NPCs for removed points, destroys unreachable orphans, and re-applies the current schedule/event. It only falls back to `bSpawnOnBeginPlay` when no schedule has ever been applied.
- `MatchesSchedule()` derives the compact `weekday`, `weekday_am`, `weekday_pm` and `weekend` aliases from the weekday/period query, so story calls such as `("default", "Monday", "AM")` reach the existing data without duplicating seven day tags on every row.
- `level.py` now maps the data flags `enabled` / `event_only` (defaults `true` / `false`) instead of hard-coding `enabled=true`.

## Interior nav coverage

`Placer.interior_nav()` reads `interiors.json` and spawns one `NavMeshBoundsVolume` per implemented cell:

| Item | Value |
|---|---|
| Actor | `unreal.NavMeshBoundsVolume`, label `Nav_<cell_id>`, folder `Gameplay/nav`, `DA_Generated` tag |
| Count | 10 (one per cell: classroom, exam, Crowler, Chancellor, three Slifer rooms, Ra room, Obelisk dining, Obelisk room) |
| XY coverage | `bounds_ue` centre ± (cell half-size + 150 cm) |
| Z coverage | `bounds_ue` centre ± (cell half-height + 250 cm), so the floor and full shell are inside |
| Save | `build.py` calls `Placer.world_actors()` and then `level.save()`; `clear_generated()` removes old volumes on rebuild |

No `.umap` is hand-edited. Rebuild navigation after the editor build (`Build > Build Paths`, or the headless `-nav` equivalent) before judging reachability.

## Remaining blockers

| Blocker | Impact | Mitigation |
|---|---|---|
| UE build/PIE is orchestrator-only here | The C++ changes, nav volumes and test have not been compiled/run by A08 | Run the build then `-DANpcScheduleTest`; expected summary is `414 passed, 0 failed. ALL PASS` |
| Nav bounds are placed but navmesh is not rebuilt in this environment | Interior reachability still needs a PIE pass | Rebuild paths after the editor build and check exit → every spawn anchor → exit per cell |
| `ADAInteriorPortal::FlagQuery` still unbound | Story/dorm doors fail open | A02 binds it; keep `fail_closed:false` until then |
| Named cast overrides | Spawns are generic `ADAStudentNPC` | Add cast/portrait mapping later; A09 owns appearance |
| Performance | 28 spawn points and 10 nav volumes unprofiled | Director never ticks; profile nav rebuild/load in the orchestrator pass |

## Headless data checks

```powershell
python Tools/world/validate_layout.py --strict
python Tools/world/test_interiors.py
```

Both should stay green; they validate ids, anchors, portal geometry and cell bounds that drive the spawn/nav placement.
