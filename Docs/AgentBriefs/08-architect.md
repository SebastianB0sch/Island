# A08 — Architect

> **Read first:** `Docs/PORT_MASTERPLAN.md` (location map, interiors).
> **Role:** world, interiors, portals, scene anchors, NPC placement.
> **Baseline branch:** `port/baseline` → work branch `port/a08-world`.

## Mission

Make every GBA story location a real place in the 3D island, and give the story a stage: enterable rooms, doors, camera anchors and schedule-driven NPC marks.

## Inputs

- `Docs/PORT_MASTERPLAN.md` Appendix B (location map).
- `Tools/dai/config.py`, `Tools/dai/layout.py`, `Tools/dai/assets/*.py`, `Tools/dai/geo.py`, `Tools/dai/palette.py`.
- `DuelAcademyIsland/Content/Python/duel_academy/level.py`.
- `DuelAcademyIsland/Content/Data/layout.json` / generated layout.
- Donor: `C:\dev\argh\ue5\Source\DuelAcademy\AcademyInterior.cpp`, `SliferDorm.cpp` (layout/scale/furniture references), `IslandEnvironment.cpp`.
- A01: `LOCATION_MAP.md`; A03: anchors/schedules.

## Owned files

- `Tools/dai/assets/**`, `Tools/dai/layout.py`, `Tools/dai/config.py`
- `DuelAcademyIsland/Content/Python/duel_academy/level.py` (interior/portal additions only)
- `.../DAInterior*.h/.cpp`, `DADoor*`, `DASceneAnchor*`, `DANpcSpawnPoint*`, `DANpcDirector*`
- `.../DAWorldActors.*`, `DAStudentNPC.*`, `DAInteractable.*`, `DALocationVolume.*`
- `Content/Data/World/**`
- Tests: `DAWorldTests.cpp`, `DAInteriorTests.cpp`, `Tools/world/validate_layout.py`

Shared files (`DAGameMode.*`, `DAStudentCharacter.*`, `DAIslandSubsystem.*`) only via A10.

## Deliverables

1. **Location mapping**
   - Implement Appendix B in `Content/Data/World/location_map.json` + `Docs/Canon/LOCATION_MAP.md`.
   - Mark every original location: existing exterior, new interior, or merged; record rationale.

2. **Interiors**
   - Academy: lobby, classroom, test room, Grand Duel Arena backstage/field, Crowler's office, Chancellor's office.
   - Slifer: cafeteria, your room, Banner's room, Jaden's room, common room.
   - Ra: cafeteria, your room, common room.
   - Obelisk: dining room, your room, common room.
   - Gym, card shop interior (if needed), harbor office, abandoned dorm/Titan room.
   - Collision, lighting, nav, props, signage, spawn points, save/sleep points.
   - Reuse the procedural kit; no hand-made `.umap` edits; regenerate via `Tools/build_island.py` + editor build.

3. **Portals/doors**
   - `ADAInteriorPortal`: interaction radius, fade, teleport to interior cell, return portal, occupancy/cooldown, save state.
   - Door prompts and lock conditions (dorm access, event locks).
   - No loading-screen dependency; <2 s transition.

4. **Scene support**
   - `ADASceneAnchor`: named camera marks (position/rotation/FOV), NPC marks, player marks, look-at targets.
   - `ADANpcSpawnPoint`: schedule tags, dorm/role, wander radius, event overrides.
   - `DANpcDirector`: spawn/despawn/teleport based on A03 schedules; no per-frame cost when static.
   - Validation: every anchor referenced by A03 exists; every schedule location has a spawn point.

5. **World data**
   - `Content/Data/World/anchors.json`, `portals.json`, `spawns.json`, `interiors.json`.
   - Map/fast-travel zone metadata; location discovery consistency.
   - Regeneration test: `Tools/build_island.py` produces identical layout + interiors.

## Work plan

1. Audit existing buildings/coordinates; map GBA locations to GX zones (Appendix B).
2. Build one vertical-slice interior (Slifer common room/your room) + portal; test entry/exit.
3. Build academy classroom/test room/arena backstage + offices.
4. Build remaining dorm interiors and gym/harbor/abandoned dorm rooms.
5. Add anchors/spawns/director; validate against A03 schedules.
6. Add all locations to map/fast travel; run world tests.
7. Polish lighting/collision/performance; regenerate and capture screenshots.

## Acceptance criteria

- [ ] Every Appendix B location reachable/enterable (or explicitly merged with rationale).
- [ ] Portals entry/exit, no loops, no fall-through, no nav dead zones; tests pass.
- [ ] Every A03 scene anchor/schedule spawn exists; validator passes.
- [ ] No manual `.umap` edits; regeneration reproducible.
- [ ] Interior load <2 s; no permanent tick cost when empty; performance budget met.
- [ ] Map/fast-travel labels match the original locations.
- [ ] No UI/rules/story/save edits; APIs stable.

## Non-goals

- Dialogue/UI (A09), story scripts (A03), duel rules (A04), card/economy data (A05/A06), AI (A07).

## Handoff report

Report: locations/interiors/portals/anchors/spawns counts, regeneration command, perf numbers, missing assets, blockers.
