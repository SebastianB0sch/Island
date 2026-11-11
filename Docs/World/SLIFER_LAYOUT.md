# Slifer Red dorm layout pass - 2026-11-11

The same pass as the Academy (`ACADEMY_LAYOUT.md`) for the Slifer Red dorm. The goals were the same: every
path walkable, doors scaled and framed, no NPC inside furniture, walls aligned and complete, and rooms laid out
properly. It covers the in-place dorm (`Tools/dai/assets/slifer.py`: twelve dorm rooms, the walkway and stair,
the dining hall and kitchen) and the three Slifer portal rooms (`Tools/dai/assets/interiors.py`: the player's
room 101, Banner's room, and Jaden / Syrus / Chumley's room).

## Check

`Tools/academy_check.py` now takes a location:

```powershell
python Tools/academy_check.py --location slifer                   # the dorm (~3 min)
python Tools/academy_check.py --location cell:slifer_jaden_room   # a portal room, with its anchors.json marks
python Tools/academy_check.py                                     # the academy, as before
```

What changed in the check (it applies to the Academy too):

- **Invisible collision boxes.** Furniture modelled into no-collision meshes gets invisible collision boxes
  in the level (`dai/collision.py`, written by the layout as `<Location>_Blockers`). The walk grid now
  includes them, because they block players and NPCs in game exactly like the visible furniture.
- **Narrow doorways.** A 0.8-0.9 m door is narrower than the 0.2 m walk grid can resolve. When the grid
  reaches one side of a door but not the other, an exact person-sized test is run along the door's centre
  line.
- **Outdoor spots.** A spot that sees the open sky over a wide arc, or straight along a compass line at
  standing height, is outdoors (walkway, outside stair, porch). Leak rays are no longer tested from such spots.
- **Furniture tops.** The tops of furniture (a kotatsu over its table) are recognised by the lowest upward
  surface under them, so they are not reported as unreachable floor.
- **Back faces and sloped beams.** Back-face hits on prop bounding boxes are ignored. Sloped beam sides are no
  longer treated as rectangles in the z-fighting test.
- **Portal rooms.** `cell:<id>` builds a portal room and checks its story marks from `anchors.json`.

## What was wrong and what changed

### Doors
- **Front doors (12): the leaf filled the genkan.** The rooms' 0.95 m deep entry swung a 0.9 m leaf over the
  shoes on the concrete. The doors now open outwards onto the stoop / walkway (`swing="out"`), as apartment
  doors do. On the ground floor the facade's base board ran across all six doorways as an 18 cm sill; it
  stops at the doors now.
- **WC doors (12): too narrow, partly in the side wall, and blocked.** They were 0.75 m, narrower than a
  person, and the WC's side wall stood 3 cm into the opening. They are now 0.85 m, fully inside the opening,
  and open into the WC. Before, the leaf swung into the room and hit the wardrobe corner, a jacket on the
  drying cord, or clutter. The wardrobes stand 15 cm further forward, and the approach to the WC door is kept
  free of clutter.
- **Dining hall.** Architraves were added inside the entrance and on both faces of the kitchen door. A ball
  in the kitchen door's swing and a tea towel floating in mid-air in front of it were moved; the towel now
  hangs on the oven bar.

### Paths
- **Drying cord across every dorm room.** Clothes hung at 1.4-2.0 m right across the room, in everyone's
  face and in the WC door's swing. The cord now runs along the back wall over the colour-box shelf.
- **The way past the WC to the back window** was blocked by a random laundry basket in room 101. The
  clutter routine treated that open edge as a wall; the nook mouth is kept clear now.
- **Banner's room 206.** The armchair, side table and Pharaoh's basket stood in a row across the middle,
  leaving only 0.77 m beside the book case. That is 1 cm wider than the in-game capsule. The reading
  corner (armchair, side table, tea set, basket and rug) is now against the right wall in front of the bed,
  leaving a 2.4 m walkway through the room.
- **Kotatsu collision.** The kotatsu's cushions touched its quilt, so the three became one collision box
  rotated 45 degrees, with corners 1.56 m from the table. That box blocked the middle of all twelve rooms,
  and in Jaden's portal room it hit Chumley's mark. The cushions sit 5 cm clear of the quilt now
  (`interior.kotatsu`), so the collision box is the table itself. A duel disk on the floor that bridged the
  table and a cushion now lies on the colour-box shelf.

### Walls, decor and z-fighting
- **Duplicate cushions.** `_room_more` laid a second set of cushions on top of the kotatsu's own; removed.
- **Posters.** In every dorm room a poster hung under the Slifer tapestry. It now hangs beside the tapestry,
  and the poster it displaced moved to the front wall between the door and the window. In Banner's room a
  poster hung behind his book case; it is on the front wall now.
- **End rooms (101 / 201 west, 106 / 206 east).** The end-wall window was covered by decor:
  - In 106, the Slifer tapestry hung over it, and the window sill cut into the colour-box tower.
  - In 206, a picture frame and the alchemy poster covered it.
  - In 101 / 201, the mirror covered it, and in 101 so did the edge of Jaden's poster.

  The east window moved to the back of the end wall, behind the bunk / bed; the exterior frame moved with
  it. In the west rooms the mirror and clock hang over the tansu, Jaden's DUEL ACADEMY poster is above the
  TV shelf, and a single coat hook fits between the corner and the window. In every room the coat-hook
  jackets reached into the front corner post; the rail moved along.
- **Party walls** ran through the floor slab into the room above. They stop at the slab and ceiling now.
  The raised floors' faces against the walls are left out.
- **Dining deck** overlapped the foundation at the entrance threshold (a flickering 9 m strip); it now
  abuts it. The kitchen ceiling joist cut through the ceiling vent; the joist and the light panel were moved.
  Details: the shoe-rack shelf is proud of its cabinet, and the dining-gable board's back faces were
  separated.
- **Shared fixes (every location):**
  - Window sills built by `interior.wall` started 4 cm inside the opening, so their tops z-fought with the
    opening's bottom face. They now start at the wall face.
  - Window and door frames from `MeshBuilder.wall` reached 3-4 cm into their openings; they now stand on
    the outer face.
  - Overlapping pinned sheets on notice boards (`interior.bulletin`) and overlapping jackets on coat hooks
    (`detail.coat_hooks`) are staggered in depth.

### Portal rooms
- **Jaden / Syrus / Chumley's room** (`_slifer_bunk_room`) is a Slifer room now, not a generic bedroom with
  one single bed:
  - the Slifer triple bunk in the back-left corner, with the ladder on the room side;
  - a kotatsu on tatami in the middle, with the three story marks standing round it;
  - Jaden's desk under the window, a wardrobe, a colour-box shelf with deck boxes, a duel disk stand,
    card posters, jackets on hooks by the door, and clothes on the floor.

  The side windows are only in the front half (`WINDOW_SLOTS`), so the bunk stands on a clear wall.
- **Banner's room:** his mark said "behind his desk" but stood in front of it. The desk is now 1.35 m off
  the back wall, and the mark (`slifer_banner_room_desk`, now `(330045, 315208)`) stands behind it beside
  his chair. The guest chair is set aside, so the player's mark faces him with nothing in between. Card
  binders lie on the desk.
- **The player's room:** the save mark ("beside the bed") stood 2.1 m from the bed. `slifer_player_room_save`
  is now `(329895, 300060)`, beside the bed. The room has Slifer dressing: a poster and a red jacket on the
  hooks by the door.

## Results

| Check | First run | Final |
|---|---|---|
| `academy_check --location slifer`: doors (size / plane / frame / swing / head) | 45 | **0** |
| paths (doors with an unreachable side, unreachable floor), with the collision boxes | 16 (+2 once the boxes were counted) | **0** |
| NPC spots | 0 | **0** |
| walls (leaks from enclosed rooms, back faces, visible z-fighting, wall steps) | 115 z-fighting + 70 back faces (+ walkway rays) | **0** |
| `cell:slifer_player_room` / `cell:slifer_banner_room` / `cell:slifer_jaden_room` | 0 / 0 / 0 (Jaden: one bed for three) | **0 / 0 / 0** |
| `spec_check.py slifer` | - | **PASS** (0 issues, all views on target) |
| `audit_interiors.py` (every location: shared helpers changed) | academy 4 accepted, others 0 / 2 accepted | unchanged |
| `validate_layout.py --strict`, `test_interiors.py` | PASS | PASS |

Not done here:
- Regenerate the FBXs and the level (`python Tools/build_island.py layout`, then the editor build).
- `ADAStudentNPC::IsClearWalk` from the Academy pass is still uncompiled.
