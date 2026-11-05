# GBA → GX Location Map

> **Owner:** A08 — Architect. **Status:** audited against the generated island layout on `port/baseline`.
> **Data:** `DuelAcademyIsland/Content/Data/World/location_map.json`.
> **Scope:** every location row in `Docs/PORT_MASTERPLAN.md` Appendix B, plus the interior/common-room rows required by the A08 brief.

## 1. Coordinate contract

- The island is authored in Blender metres with **+X east, +Y north, +Z up**, then converted to UE as `(x, -y, z) * 100 cm` with `yaw_ue = -yaw_blender`.
- All coordinates in this document and in `Content/Data/World/*.json` are **UE centimetres**.
- Building bounds are axis-aligned world bounds including foundations/roof overhangs. They are audit aids, not collision volumes.
- Portal cells live below the island at **Z = -30,000 cm** in a dedicated block; they are never visible from the island and are reached only through portals.

## 2. Summary

| Metric | Count |
|---|---|
| GBA/Appendix B rows mapped | 36 |
| Existing geometry (walk-in or exterior) | 20 |
| Needs a new interior cell | 10 |
| Merged with another location | 6 |
| Missing | 0 |
| New interior cells implemented | 10 |

**Result:** every Appendix B row has a credible GX home. There are no `missing` locations in this pass. The ten new cells are all portal cells; six rows are deliberately merged to avoid duplicate, half-used rooms.

## 3. Location table

| ID | GBA location | GX target | Zone | Status | UE point (cm) | Primary anchor | Interior / merged into |
|---|---|---|---|---|---|---|---|
| `academy_front` | Duel Academy front | Duel Academy - Main Entrance / Plaza | `plaza` | existing | (0, -6500, 3400) | `academy_front_steps` | — |
| `academy_lobby` | Duel Academy front (registration) | Academy Lobby / Registration | `academy` | existing | (-1500, -10500, 3600) | `academy_registration_player` | — |
| `academy_classroom` | Classroom | Academy Classroom | `academy` | needs_interior | (6400, -15200, 3600) | `academy_classroom_teacher` | `academy_classroom` |
| `academy_test_room` | Test room | Academy Exam Room | `academy` | needs_interior | (-6400, -15200, 3600) | `academy_test_room_proctor` | `academy_test_room` |
| `academy_arena` | Duel Arena | Grand Duel Arena | `academy` | existing | (0, -16500, 3650) | `academy_arena_field_player` | — |
| `academy_gym` | Gym | Duel Gym - Assembly Hall | `gym` | existing | (67711, 72547, 620) | `gym_assembly_stage` | — |
| `academy_crowler_office` | Dr. Crowler's room | Crowler's Staff Office | `academy` | needs_interior | (-8770, -13100, 3600) | `crowler_office_desk` | `academy_crowler_office` |
| `academy_chancellor_office` | Chancellor's office | Chancellor Sheppard's Office | `academy` | needs_interior | (8770, -13100, 3600) | `chancellor_office_desk` | `academy_chancellor_office` |
| `academy_card_shop` | Card shop | Academy Card Shop | `academy` | existing | (2130, -10500, 3600) | `academy_card_shop_player` | — |
| `slifer_front` | Slifer Red - front | Slifer Red Dorm Exterior | `slifer` | existing | (-103300, 26200, 2900) | `slifer_front_gate` | — |
| `slifer_cafeteria` | Slifer Red - cafeteria | Slifer Dining Hall | `slifer` | existing | (-106500, 27800, 2945) | `slifer_cafeteria_player` | — |
| `slifer_common_room` | Slifer Red - common room | Slifer Common Room | `slifer` | merged | (-106500, 27800, 2945) | `slifer_cafeteria_player` | → `slifer_cafeteria` |
| `slifer_player_room` | Slifer Red - your room | Slifer Room 101 (Player) | `slifer` | needs_interior | (-106800, 24505, 3025) | `slifer_player_room_save` | `slifer_player_room` |
| `slifer_banner_room` | Slifer Red - Banner's room | Banner's Room | `slifer` | needs_interior | (-106800, 26671.7, 3025) | `slifer_banner_room_desk` | `slifer_banner_room` |
| `slifer_jaden_room` | Slifer Red - Jaden's room | Jaden / Syrus / Chumley Bunk Room | `slifer` | needs_interior | (-106800, 24505, 3300) | `slifer_jaden_room_jaden` | `slifer_jaden_room` |
| `ra_front` | Ra Yellow - front | Ra Yellow Dorm Exterior | `ra` | existing | (-63000, 60000, 2365.5) | `ra_front_gate` | — |
| `ra_cafeteria` | Ra Yellow - cafeteria | Ra Cafeteria | `ra` | existing | (-71259.8, 64103.8, 2295) | `ra_cafeteria_player` | — |
| `ra_common_room` | Ra Yellow - common room | Ra Common Room | `ra` | merged | (-71259.8, 64103.8, 2295) | `ra_cafeteria_player` | → `ra_cafeteria` |
| `ra_player_room` | Ra Yellow - your room | Ra Room (Player) | `ra` | needs_interior | (-68013.6, 65835.6, 2425) | `ra_player_room_bed` | `ra_player_room` |
| `obelisk_boys_front` | Obelisk Blue boys - front | Obelisk Blue Boys' Dorm Exterior | `obelisk_boys` | existing | (-50000, -44000, 3413.5) | `obelisk_front_gate` | — |
| `obelisk_dining` | Obelisk Blue boys - dining | Obelisk Dining Room | `obelisk_boys` | needs_interior | (-59846.8, -51871.4, 3150) | `obelisk_dining_player` | `obelisk_dining` |
| `obelisk_common_room` | Obelisk Blue boys - common room | Obelisk Common Room | `obelisk_boys` | merged | (-59846.8, -51871.4, 3150) | `obelisk_dining_player` | → `obelisk_dining` |
| `obelisk_player_room` | Obelisk Blue boys - your room | Obelisk Room (Player) | `obelisk_boys` | needs_interior | (-57649, -54335.1, 3150) | `obelisk_player_room_bed` | `obelisk_player_room` |
| `obelisk_girls_front` | Obelisk Blue girls - front | Obelisk Blue Girls' Dorm | `obelisk_girls` | existing | (-12000, -84000, 2945.3) | `obelisk_girls_gate` | — |
| `harbor` | Harbor | Duel Academy Harbor | `harbor` | existing | (4000, 104000, 420) | `harbor_dock` | — |
| `ocean_shore` | Ocean / next to ocean | Shoreline / Lake Overlook | `beach` | merged | (82000, 56000, 911) | `beach_shore` | → `beach` |
| `beach` | Ocean / next to ocean (beach) | South-East Beach | `beach` | existing | (82000, 56000, 911) | `beach_shore` | — |
| `lake` | Ocean / next to ocean (lake) | Academy Lake | `lake` | existing | (-4000, -76000, 2824.5) | `lake_shore` | — |
| `volcano_crater` | Volcano - near crater | Volcano Crater Rim | `volcano` | existing | (90500, -64000, 12719.2) | `volcano_crater` | — |
| `abandoned_dorm` | Abandoned dorm | Abandoned Dorm | `abandoned` | existing | (91930, 6000, 1960) | `abandoned_dorm_hall` | — |
| `hot_springs` | Hot springs | Volcanic Hot Springs | `hotsprings` | existing | (103500, -30000, 5971.7) | `hot_springs` | — |
| `forest` | Forest | Duel Academy Forest | `forest` | existing | (71392.8, -35029.8, 12865.1) | `forest_shrine` | — |
| `lighthouse` | Lighthouse | Harbor Lighthouse | `lighthouse` | existing | (25500, 119500, 500) | `lighthouse_view` | — |
| `cliffs` | West cliffs / sunset point | West Cliffs - Sunset Point | `cliffs` | existing | (-105850, -15350, 3084.1) | `cliffs_sunset` | — |
| `academy_arena_backstage` | Duel Arena - backstage | Arena Backstage / Threshold | `academy` | merged | (0, -12773, 3700) | `academy_arena_field_player` | → `academy_arena` |
| `harbor_office` | Harbor office | Harbor Terminal / Warehouse Office | `harbor` | merged | (6000, 107000, 300) | `harbor_office` | → `harbor` |

### 3.1 Why each status

**Existing (20)**

- `academy_front` — The plaza and academy portico already exist. Only a named arrival/cutscene mark is needed.
- `academy_lobby` — The lobby is fully modelled and walk-in from the portico; reception and the arena threshold are already in the mesh.
- `academy_arena` — The arena is a finished walk-in interior with a duel field and 15 tiers. Add field/podium/camera marks only.
- `academy_gym` — The 60 x 40 m gym hall already has a court, bleachers and two practice fields. It is the best stand-in for the opening assembly.
- `academy_card_shop` — Dorothy's shop is already modelled inside the lobby (x 18-29 m local). Economy work is A06/A09; the room exists.
- `slifer_front` — The two-storey dorm block and its dining annex already exist on the west cliff.
- `slifer_cafeteria` — The 9 x 8 m dining annex is a real interior room with tables, a serving counter and a kitchen. Reuse it.
- `ra_front` — The three-storey Ra block and its cafeteria wing already exist.
- `ra_cafeteria` — The cafeteria wing is a real interior room with serving counter and windows. Reuse it.
- `obelisk_boys_front` — The palace-scale Obelisk boys' block, courtyard and gate already exist.
- `obelisk_girls_front` — Exterior and garden exist. Appendix B only needs a story trigger here; no enterable girls' dorm is required in this pass.
- `harbor` — Quay, terminal, warehouse, breakwater and heliport already exist. The terminal/warehouse covers harbor-office scenes.
- `beach` — Existing beach zone with a duel court and shore anchors.
- `lake` — Existing lake zone; the girls' dorm jetty and lake walk are already modelled.
- `volcano_crater` — Crater rim and trail already exist. Add a Titan/Shadow Game anchor on the rim.
- `abandoned_dorm` — The entrance hall, broken staircase and gallery are already modelled as a walk-in interior. Add hall/Titan marks.
- `hot_springs` — Existing onsen zone; flavor and optional schedules only.
- `forest` — Existing forest zone and shrine; optional schedules and flavor.
- `lighthouse` — Existing breakwater lighthouse; a view anchor covers the Kaiser scene.
- `cliffs` — Existing cliff zone; useful for quiet character beats and sunset shots.

**Needs interior (10)**

- `academy_classroom` — The east classroom wing is a solid shell. A portal cell gives a 14 x 10 m room without touching the exterior mesh.
- `academy_test_room` — Written exams need a controlled room. The west wing door is the natural entrance; the exam UI is A07/A09.
- `academy_crowler_office` — The west end block has a side door. A portal cell avoids carving the existing academy shell.
- `academy_chancellor_office` — Top-floor office and ending trigger. The east end block side door is a sensible entrance; the cell can be dressed as a top-floor room.
- `slifer_player_room` — Ground-floor room 101 door exists on the seaward facade but the block is solid. Portal cell carries bed, desk, save/sleep point.
- `slifer_banner_room` — Ground-floor east room by the dining passage. New cell holds the headmaster desk, bookshelf and Pharaoh tank.
- `slifer_jaden_room` — Upper-floor room directly above the player room. New 7 x 5.5 m bunk room for Jaden, Syrus and Chumley scenes.
- `ra_player_room` — Ra's main block is solid. A portal cell at the front bay gives the promoted player a room without rebuilding the facade.
- `obelisk_dining` — The main block is a solid shell. A 14 x 9 m portal cell gives the five-star dining room a stage.
- `obelisk_player_room` — East pavilion front has a first-floor door; the room cell is dressed as an elite dorm suite.

**Merged (6)**

- `slifer_common_room` — GBA common-room beats are staged in the existing dining hall and covered deck; a second lounge would duplicate the only Slifer social space.
- `ra_common_room` — No GBA Appendix B row; the existing cafeteria doubles as Ra's common room. Keep one social space per dorm in the vertical slice.
- `obelisk_common_room` — Merged into the planned Obelisk dining room to keep one large social cell instead of two half-used rooms.
- `ocean_shore` — The island's beach, lake shore and cliff overlook already cover the GBA 'next to the ocean' scenes; use location-specific anchors.
- `academy_arena_backstage` — The lobby-to-arena threshold and the field steps already provide entrance staging; a separate corridor is deferred.
- `harbor_office` — The harbor terminal and warehouse are existing shells; use their interior volumes for office beats instead of a new cell.

## 4. Required interiors

| Cell | Room | W × D × H | Origin (UE cm) | Entrance portal | Kind | Status |
|---|---|---|---|---|---|---|
| `academy_classroom` | Academy Classroom | 14 × 10 × 4 m | (300000, 300000, -30000) | `portal_academy_classroom_entrance` | classroom | implemented |
| `academy_test_room` | Academy Exam Room | 12 × 9 × 3.8 m | (300000, 325000, -30000) | `portal_academy_test_room_entrance` | exam | implemented |
| `academy_crowler_office` | Crowler's Staff Office | 9 × 7 × 3.5 m | (300000, 347000, -30000) | `portal_crowler_office_entrance` | office | implemented |
| `academy_chancellor_office` | Chancellor Sheppard's Office | 10 × 8 × 3.6 m | (300000, 365000, -30000) | `portal_chancellor_office_entrance` | office | implemented |
| `slifer_player_room` | Slifer Room 101 (Player) | 6 × 5 × 3.2 m | (330000, 300000, -30000) | `portal_slifer_player_room_entrance` | dorm_room | implemented |
| `slifer_banner_room` | Banner's Room | 6.5 × 5.5 × 3.2 m | (330000, 315000, -30000) | `portal_slifer_banner_room_entrance` | headmaster_room | implemented |
| `slifer_jaden_room` | Jaden / Syrus / Chumley Bunk Room | 7 × 5.5 × 3.2 m | (330000, 330000, -30000) | `portal_slifer_jaden_room_entrance` | dorm_room | implemented |
| `ra_player_room` | Ra Room (Player) | 6.5 × 5.5 × 3.4 m | (360000, 300000, -30000) | `portal_ra_player_room_entrance` | dorm_room | implemented |
| `obelisk_dining` | Obelisk Dining Room | 14 × 9 × 4.2 m | (390000, 300000, -30000) | `portal_obelisk_dining_entrance` | dining | implemented |
| `obelisk_player_room` | Obelisk Room (Player) | 7 × 6 × 3.6 m | (390000, 320000, -30000) | `portal_obelisk_player_room_entrance` | dorm_room | implemented |

Room-by-room purpose, lighting, collision/nav and reuse are in [`Docs/World/INTERIORS.md`](../World/INTERIORS.md).

## 5. Existing building bounds (audit)

These are the world-space AABBs derived from the procedural assets plus their pad heights. Use them to place new doors, portals and scene cameras without intersecting the existing shells.

| Zone / asset | UE AABB min | UE AABB max | Notes |
|---|---|---|---|
| Academy (main + wings + end blocks) | (-11400, -22600, 3400) | (11400, -7340, 7400) | Lobby, arena, card shop and gym-sized end blocks are existing interiors. |
| Slifer Red (main + dining + yard) | (-107140, 24205, 2900) | (-105940, 28325, 3600) | Two storeys, 6 rooms per floor, 8 m deep; dining annex is an existing interior. |
| Ra Yellow (main + cafeteria wing) | (-72284, 62794, 2250) | (-65471, 68915, 3900) | Three storeys; cafeteria wing is enterable, main block is solid. |
| Obelisk Blue boys (main + courtyard) | (-65470, -57519, 2850) | (-56254, -47927, 5250) | Palace block; no modelled interior rooms yet. |
| Duel Gym (hall + grounds) | (65840, 68223, 600) | (72566, 75606, 2100) | 60 × 40 m hall, two indoor practice fields, bleachers. |
| Abandoned Dorm (shell + hall) | (91900, 4000, 1900) | (94000, 8000, 4100) | Entrance hall and gallery are already modelled. |

## 6. Candidate portal positions

Every new interior has a paired entrance/exit portal. Exterior coordinates are the door/threshold; interior targets are 2.5 m inside the cell, past the exit trigger. Yaw is UE yaw (0 = +X).

| Entrance portal | Interior | Exterior UE (cm) | Yaw | Interior arrival UE | Yaw | Return portal | Required flag |
|---|---|---|---|---|---|---|---|
| `portal_academy_classroom_entrance` | `academy_classroom` | (6400, -15200, 3700) | 90 | (300000, 299750, -29900) | 90 | `portal_academy_classroom_exit` | registered |
| `portal_academy_test_room_entrance` | `academy_test_room` | (-6400, -15200, 3700) | 90 | (300000, 324800, -29900) | 90 | `portal_academy_test_room_exit` | exam_day |
| `portal_crowler_office_entrance` | `academy_crowler_office` | (-8770, -13100, 3700) | 0 | (300000, 346900, -29900) | 90 | `portal_crowler_office_exit` | crowler_office_unlocked |
| `portal_chancellor_office_entrance` | `academy_chancellor_office` | (8770, -13100, 3700) | 180 | (300000, 364850, -29900) | 90 | `portal_chancellor_office_exit` | chancellor_office_unlocked |
| `portal_slifer_player_room_entrance` | `slifer_player_room` | (-106800, 24505, 3025) | 180 | (330000, 300000, -29900) | 90 | `portal_slifer_player_room_exit` | registered |
| `portal_slifer_banner_room_entrance` | `slifer_banner_room` | (-106800, 26671.7, 3025) | 180 | (330000, 314975, -29900) | 90 | `portal_slifer_banner_room_exit` | met_banner |
| `portal_slifer_jaden_room_entrance` | `slifer_jaden_room` | (-106800, 24505, 3300) | 180 | (330000, 329975, -29900) | 90 | `portal_slifer_jaden_room_exit` | met_jaden |
| `portal_ra_player_room_entrance` | `ra_player_room` | (-68013.6, 65835.6, 2425) | -130 | (360000, 299975, -29900) | 90 | `portal_ra_player_room_exit` | dorm_ra |
| `portal_obelisk_dining_entrance` | `obelisk_dining` | (-59846.8, -51871.4, 3150) | 140 | (390000, 299800, -29900) | 90 | `portal_obelisk_dining_exit` | dorm_obelisk |
| `portal_obelisk_player_room_entrance` | `obelisk_player_room` | (-57649, -54335.1, 3150) | 140 | (390000, 319950, -29900) | 90 | `portal_obelisk_player_room_exit` | dorm_obelisk |

Lock flags are data hooks for A02/A03. Until `ADAInteriorPortal::FlagQuery` is bound, the portals are configured with `fail_closed: false`, so a missing flag service does not seal the level during development.

## 7. Opening vertical-slice anchors

These ids are the minimum A03/A09 contract for the opening hour. They all exist in `anchors.json`.

| Anchor | Name | Location | Kind | UE position (cm) | Yaw |
|---|---|---|---|---|---|
| `gym_assembly_stage` | Gym Assembly Stage | `academy_gym` | stage | (68263.6, 72312.6, 620) | -23 |
| `academy_registration_player` | Registration Player | `academy_lobby` | player | (-1500, -10500, 3600) | 180 |
| `academy_registration_camera` | Registration Camera | `academy_lobby` | camera | (-700, -7600, 5000) | 0 |
| `slifer_cafeteria_player` | Slifer Cafeteria Player | `slifer_cafeteria` | player | (-106500, 27800, 2945) | 0 |
| `slifer_player_room_save` | Player Room Save Point | `slifer_player_room` | player | (330050, 300050, -29900) | 180 |
| `slifer_banner_room_desk` | Banner Desk | `slifer_banner_room` | npc | (330000, 315100, -29900) | -90 |
| `slifer_jaden_room_jaden` | Jaden Room Jaden | `slifer_jaden_room` | npc | (329900, 329950, -29900) | 0 |
| `academy_classroom_teacher` | Classroom Teacher | `academy_classroom` | npc | (300000, 300300, -29900) | -90 |
| `academy_card_shop_player` | Card Shop Player | `academy_card_shop` | player | (1500, -10500, 3600) | 0 |
| `academy_arena_field_player` | Arena Duelist | `academy_arena` | player | (-1060, -16500, 3650) | 0 |

## 8. Validation

```powershell
python Tools/world/validate_layout.py          # human report
python Tools/world/validate_layout.py --json   # machine report for A10
python Tools/world/validate_layout.py --strict # warnings are failures
python Tools/world/test_interiors.py           # portal route + optional bpy mesh check
```

Current result: **PASS** — 36 locations, 10 interiors, 20 portals, 89 anchors, 28 spawns, 0 missing anchors.

## 9. Merge decisions (explicit)

- **Slifer common room → cafeteria/dining hall.** The existing 9 × 8 m dining annex already has tables, a serving counter, a kitchen and a covered deck. A second lounge would split the only Slifer social space.
- **Ra common room → Ra cafeteria.** No Appendix B common-room row; the existing cafeteria is the natural social space.
- **Obelisk common room → Obelisk dining.** One large implemented dining cell serves both dining and common-room scenes.
- **Ocean / next to ocean → beach + lake + cliffs.** The three existing shoreline zones cover the GBA ocean beats; use location-specific anchors.
- **Arena backstage → arena.** The lobby-to-arena threshold and field steps already provide entrance staging; a corridor is deferred.
- **Harbor office → harbor terminal/warehouse.** Existing harbor shells cover office/ferry/Dorothy-truck beats.

## 10. Open mapping questions / blockers

- **Interior geometry builder implemented; FBX/level build pending.** `Tools/dai/assets/interiors.py` + `Layout.place_interiors()` are in place and pass the headless geometry smoke test. The orchestrator still needs to run `python Tools/build_island.py layout` and the editor build.
- **Ra/Obelisk room portals sit on facade bays.** Cell door leaves/steps are generated; the exterior facade doors still need a later facade pass.
- **Chancellor's office is reached through the east end-block side door.** It reads as a ground-floor room; a future stair/elevator transition is needed for the top-floor fiction.
- **Slifer room doors are decorative on a solid block.** The cell has its own generated door leaf; the exterior trigger sits at the existing facade door plane. This is deliberate for the vertical slice.
- **Gym assembly uses the Duel Gym.** It is the largest existing hall and already has bleachers; the GBA school-gym look is approximated, not replicated.

---

_Generated from `Content/Data/World/*.json`; edit the JSON and re-run the validator rather than hand-editing coordinates here._
