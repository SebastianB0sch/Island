# Ra Yellow dorm layout pass - 2026-11-11

The same pass as the Academy (`ACADEMY_LAYOUT.md`) and the Slifer Red dorm (`SLIFER_LAYOUT.md`) for the Ra
Yellow dorm. The goals were the same: every path walkable, doors scaled and framed, no NPC inside furniture,
walls aligned and complete, and rooms laid out properly. It covers the in-place dorm
(`Tools/dai/assets/ra.py`) and the Ra portal room (`Tools/dai/assets/interiors.py`: the player's room after
the promotion):
- the entrance hall, the lounge and the duel practice room;
- the study, the supervisor's office, the laundry and the dorm kitchen;
- the 2F / 3F corridors with 22 dorm rooms (Misawa's 309 included) and the washrooms;
- the landing lounge and the library, the attic, and the cafeteria with its terrace.

## Check

```powershell
python Tools/academy_check.py --location ra                   # the dorm (~4 min)
python Tools/academy_check.py --location cell:ra_player_room  # the portal room, with its anchors.json marks
```

What changed in the check (it applies to every location):

- **Trees are not walls.** The leak test skips spots that see open air. Outdoor tree / bush / lamp-post prop
  boxes made the back-door landing look enclosed, because each tree's box blocked its rays. A ray that meets
  only such a prop, with no architecture behind it, now counts as open air.
- **Back faces are confirmed.** A ray that grazes the exact edge where two faces meet can report either face
  (a case's front corner, a dormer side wall's bottom edge). A back face is now reported only when at least
  three of four rays 1 cm beside the first one repeat it, as a missing face does.

## What was wrong and what changed

### Paths
- **Nobody could go upstairs.** The grandfather clock stood on the foot of the hall staircase, so 2F, 3F and
  the attic were unreachable. The clock now stands on the hall's east wall, beside the student mailboxes.
- **The attic stair started 0.2 m from the 3F back wall,** too close to step onto. The flight now starts
  1.1 m off the wall (`ATTIC_Y`) and arrives further forward in the attic, beside the study nook. The
  stairwell (`HOLE_C`) moved with it. It now runs on to y 4.1, so a person climbing clears the slab edge with
  their head. Before, the stair cut through the top cap.
- **A 1.6 m suitcase** lay crosswise on every back-room wardrobe and stuck 0.4 m through the partition. On
  3F it blocked the attic stair. It is a storage box now.
- **Duel practice room.** The two duel tables with their end stools spanned the room, leaving one-cell gaps at
  the ends, and the north half was cut off. The tables now run along the room (rugs, duel disks and cards
  with them), leaving 2.4 m walkways either side.
- **Laundry.** The drying line hung across the doorway, with clothes down to 1.4 m. Two baskets stood in the
  door's swing, one under the ironing board and one on top of another basket. The line now hangs at 2.95 m
  (clothes clear 2.2 m), and the baskets stand by the east wall.
- **Washrooms (2F / 3F).** The white cupboard stood in front of the shower stall, and the cleaning cart in
  the middle of the room closed off the corner by the window. The cupboard, cart and bin are now against the
  east wall, and the towel rail is above the cart.
- **Crown mouldings** ran across the three stairwells in the hall, landing and library, hanging in the opening
  over the flights. They stop at the stairwells now (`crown(skip=...)`).

### Doors
- **Balcony French doors (30, floors 2-3):** 1.2 m double doors, 0.6 m leaves (below the 0.7 m minimum per
  leaf). Each leaf swung into its own curtain. They are 1.4 m now (`BALC_W`), and their curtains hang beside
  the opening (`curtain(door=True)`). The landing's portico French door got the same curtains.
- **Balcony brackets** sat exactly on the door surrounds. The balconies are 0.1 m longer each side, and the
  brackets stand clear of the surrounds. The deck's underside no longer lies flush with the string course.
- **Exit signs over tall doors** (shared `detail.dress_room`): the sign hung at the usual 2.45 m, inside a 2.51 m
  French door's swing. It now hangs over the door head. The hall's exit sign sat in the slab over the entrance
  transom; it is beside the door now.
- **Kitchen pass door.** The doorway runs through the main wall and the cafeteria wall (0.55 m). The leaf
  hung in the main wall's middle, 13 cm off the doorway's middle; it now hangs in the middle. The step on the
  cafeteria side is 0.5 m deep.
- **Cafeteria doors** (entrance and terrace) got architraves inside. Their leaves stood 2 cm below the
  cafeteria floor (`mb.room` lays its floor 2 cm above the slab). The doorways now start at that floor, over a
  5 mm marble threshold, and the leaves stand on it. Slifer's dining-hall entrance and kitchen door had the same
  fault and got the same fix.
- **Upper-floor doors.** `ALIGNMENT_AUDIT.md` listed a ~3.5 cm gap under the 2F / 3F leaves. A probe (rays
  straight down at and either side of every leaf) finds the floor flush under all of them now.
- **Upper-floor arches** at the wing entrances had architraves on the wing side that sat inside the corridor
  walls. Those are left out (`pwall(trim_l=None)`); the hall side keeps them.

### NPCs
- Lounge: on the sofa; now between the sofa and the card tables.
- Study: on a chair; now between the tables.
- Cafeteria: on a chair; now in the aisle.
- The walkway student: on the lawn, now on the path.

### Walls, decor and z-fighting
- **Panelling and skirting** (shared `interior.wainscot`) were both 24 mm thick, so their faces lay flush. 64
  places flickered. The boards are 18 mm now, so the skirting stands proud, and there are no faces against
  the wall or floor.
- **Lounge panelling** on the duel-room wall was drawn facing into the wall. It now faces the lounge.
- **Fireplace:** the mantel was exactly as wide as the chimney breast; the breast is 10 cm wider now. The
  alcove bookcases stand off the skirting.
- **Two-sided panels:** the stair dados, the closed side under the attic stair, and the dormers' side walls
  and gables drew both faces in the same place. The back copy now sits 2 mm behind (`_poly2`); the dados have
  one face, towards the hall.
- **Smaller fixes:**
  - corridor cork boards (frame flush with the cork);
  - pigeonhole base (ran into the bottom board);
  - observatory steps (the top tread lay on the platform);
  - edging past the paving ends;
  - the cafeteria base band;
  - the forecourt paving and the entrance landing against the cafeteria foundation;
  - switch and socket plates (no face inside the wall, shared `detail.switch` / `outlet`);
  - bookcase boards (shared `interior.bookcase`: between the sides, 1 cm back).
- **Attic void.** The closed void under the front pediment had walkable-looking floor under the hollow cross
  gable. A board at the pediment's base seals it.
- **Items from `ALIGNMENT_AUDIT.md` now fixed:**
  - the attic stair cut the 3F slab;
  - the hall banners went 35 cm into the 2F slab (they hang below the crown moulding, clear of the notice
    board);
  - the servery sign's backing board went through the cafeteria ceiling (hangers now);
  - dorm curtains cut the inside sills (they hang 15 cm off the wall and stop above the window, clear of the
    desks below).

### Portal room
- **`ra_player_room`** had no faults, but it was the bare generic dorm room. It now has Ra dressing like
  Slifer 101 (`_ra_player`): a RA YELLOW poster on the back wall, and a yellow jacket on the hooks beside
  the door. `_slifer_dressing` takes the dorm (`dorm="ra"`).

## Results

| Check | First run | Final |
|---|---|---|
| `academy_check --location ra`: NPC spots | 3 | **0** |
| doors (size / plane / frame / swing / head) | 65 | **0** |
| paths (unreachable doors, cameras, NPC spots, floor) | 78 (2F, 3F and the attic unreachable) | **0** |
| walls (leaks, back faces, z-fighting) | 142 | **0** |
| `cell:ra_player_room` | 0 | **0** |
| `spec_check.py ra` (audit + detail coverage + people + painted windows) | - | **PASS** (0/21 views below target) |
| `audit_interiors.py` (every location: shared helpers changed) | academy 4 accepted, harbor 2 accepted, others 0 | unchanged |
| `academy_check --location slifer`, the Slifer and Academy portal rooms | 0 | **0** |
| `validate_layout.py --strict`, `test_interiors.py` | PASS | PASS |

Two views fell just under the detail target after the clutter moved out of the walkways (laundry and
washroom, 43 % < 45 %). The laundry has a rubber mat at the folding table, and the washrooms have wooden
duckboards by the bench and mid-floor (4 cm, walkable).

**Academy re-check** with the refined check: NPC spots 0, doors 0, paths 154 (the known leftovers). The
shared panelling fix took the z-fighting list from 1,168 to 882. Treating trees as open
air removed the 72 portico leak rays. Confirming back faces took them from 71 to 25. The pavilion corridors
had been exactly at their 35 % detail target. One extra dorm banner near the camera keeps them on target.

Not done here:
- Regenerate the FBXs and the level (`python Tools/build_island.py layout`, then the editor build).
