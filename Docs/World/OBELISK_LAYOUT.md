# Obelisk Blue boys' dorm layout pass - 2026-11-11

The same pass as the Academy (`ACADEMY_LAYOUT.md`), the Slifer Red dorm (`SLIFER_LAYOUT.md`) and the Ra Yellow
dorm (`RA_LAYOUT.md`) for the Obelisk Blue boys' palace. The goals were the same: every path walkable, doors
scaled and framed, no NPC inside furniture, walls aligned and complete, and rooms laid out properly. It covers
the in-place palace (`Tools/dai/assets/obelisk.py`, `build_boys`) and the two Obelisk portal rooms
(`Tools/dai/assets/interiors.py`: the dining room and the player's room after the promotion):
- the ground floor: foyer with the imperial staircase, library, lounge, music room, dining room, duel salon,
  trophy room, kitchen and pantry;
- the first and second floors: 16 student rooms, 8 end-pavilion suites, the corridors, the games room, the
  stair hall and the study hall;
- the attic storey (wing rooms, studio and box room, servants' rooms, servants' hall, linen store) and the
  cupola lookout in the dome;
- the courtyard with the fountain and the gate.

The girls' mansion shares the module's helpers. Shared fixes are listed under "Shared helpers"; the girls'
mansion itself was not reviewed.

## Check

```powershell
python Tools/academy_check.py --location obelisk_boys              # the palace (~8 min)
python Tools/academy_check.py --location cell:obelisk_player_room  # a portal room, with its anchors.json marks
python Tools/academy_check.py --location cell:obelisk_dining
```

`--location obelisk_boys` is new in the check (seeds in the courtyard; the grid reaches y 70 for the garden
behind the palace).

## What was wrong and what changed

### Paths
- **The whole attic storey was unreachable** (wing rooms, studio, box room, servants' rooms, servants' hall,
  linen store and the cupola: nine room cameras). Three faults:
  - the second-floor corridor ceilings closed the stairwell of the attic flights: a person climbing hit it
    with their head halfway up. The corridors are open over the well now (`B_HOLE_W3`), and the cornice stops
    at it;
  - each of the three attic flights (corridor -> wing attic, wing -> pavilion, wing -> centre) arrived 4-5 cm
    short of the floor at the top: the holes ran past the last step. They end at the top steps now;
  - in the centre attic, the coffer beams ran straight across the cupola stairwell (the ceiling cut did not
    stop them), 1.5 m above the spiral's treads. Coffer beams stop at every ceiling cut now (`_coffers`). The
    hall's ceiling rose and smoke detector hung in the middle of the well too; ceiling fixtures now go beside
    a keep-clear area (shared `detail.dress_room`).
- **Cupola** (`ALIGNMENT_AUDIT.md`): the rail round the stair opening was one segment off and covered part of the
  top tread, and the floor ring started 10 cm outside the treads. The rail opening is over the top tread now,
  and a landing joins the top tread to the floor ring.
- **Box room:** three rolled carpets stood in the door's swing. They stand in the corner.
- **East servants' rooms (attic):** the walk-in dormers' cheeks reach 1.9 m into the room, and a bed with its
  nightstand closed the rest of the passage past the screen wall, so the north half was cut off (the west side
  is mirrored with the nightstands the other way and was open). The outer beds stand 1 m in from the cheeks and
  the nightstands are on the room side, on both sides.
- **Duel salon arrival:** the fast-travel spot was taken by an armchair. The armchair moved clear of the spot
  and of the door's swing.

### Doors
- **Main entrance and garden door.** The plinth and its band ran across both doorways: a 45 cm curb in front of
  the main door and the garden door. They stop at the door surrounds now. The doorways had no transom: the
  2.8 m leaves stood in a 4.8 m opening under the fanlight. A marble transom now runs through the wall and the
  surround at the leaf head. The leaves hang on the middle of the reveal (wall + 0.3 m surround), and the
  surrounds carry a gilded bead round the opening on their faces, as the architrave.
- **Balcony French doors (6, end pavilions):** the string course crossed their thresholds as a 9 cm curb. It
  stops at their frames now. The balustrade's end posts stood in the outer leaves' swing; the balconies reach
  the corner pilasters now, and the posts stand clear.
- **Suite and room nameplates** hung on the door architraves (the suites' in the leaf's swing). They hang
  beside the architraves. The KITCHEN and DUEL SALON plates faced into the wall (their text was inside it);
  they face the rooms they name the doors of.
- **Thresholds:** where the wall runs on below a doorway, its threshold was a marble box down into the wall,
  coinciding with it (the threshold's top and the cut's bottom flickered). Those are 5 mm marble plates on
  the cut now; the leaves start 5 mm above their sockets, so they stand on the plates.

### NPCs
- Lounge: in the billiard table; now beside it.
- Dining room: on a sofa; now at the sofas.
- Duel salon: the two duellists stood on the chairs at the table ends; now behind the chairs.
- Courtyard: on a bench round the fountain; now on the path inside the ring of benches.

### Walls and z-fighting
- **Window sills** inside the facade windows lay 2 cm into the opening's bottom face (every window of the three
  rows round the palace). They start at the wall face.
- **Junction walls** between the blocks ended in the facade plane, over the wing walls' ends: a 0.4 m strip of
  interior finish flickered on the facade at every wing corner, on every storey. They stop at the wings' inner
  faces; the half of each corner the wing wall leaves open is a short piece, and above the wing walls the
  whole corner is.
- **Plinth, bands and cornices** turned the corners into the neighbouring blocks' walls. They stop at the
  corners of blocks joined on that side.
- **Coffer beams** had end faces in the walls' plane, behind the cornices. They have none against the walls.
- **Dado panelling** (shared `interior.wainscot`) ended in the same plane as its cap and the skirting at every
  door. The boards stop under the cap, and the dado stops 1 cm short of the skirting's end.
- **Stair carpet** risers lay on the marble risers. They stand in front of them.
- **Ensuite floors** ran under the wall tiles to the same ends.
- **The outer walls** started at the ground floor slabs' underside (1.7 m): the walls start 2 cm lower.
- **Corner pilasters** were 5 cm wider than the gap to the wings' outer window frames, so the frames sat in
  the pilasters' face. They are 0.66 m wide.
- **Dormers:** the strip over each walk-in dormer niche ended in the attic ceiling's plane.
- **Fireplaces** (lounge, dining room, the suites): `K.fireplace` builds its firebox behind the point it is
  given, and the palace gave it points on the wall faces, so the marble surrounds lay in the walls' plane. The
  chimneypieces stand 0.3 m out on the walls now (`_fireplace`).
- **Rugs:** the music room's and the lounge's rugs overlapped their neighbours. They meet without overlapping.
- **Small fixes:** the suites' built-in bookcases stood on the skirting; the en-suite bath rims ran into the
  window sills over them; the servants' rooms' coat hooks faced into the wall; the ensuite wall tiles had faces
  against the walls.
- **Cupola windows:** the arched heads had spandrel faces outside and inside but no reveal along the arch; from
  inside the drum you saw the back of the outer face. They use `_spandrels` (with the reveal).

### Rooms
- **Duel salon:** the room the fast-travel point describes as "under the portraits of past champions" had no
  portrait and a plain 4.7 m ceiling (its view fell below the detail target once the armchair moved out of
  the arrival spot). A champion's portrait hangs in the one free stretch of the west wall (the rest is windows,
  the TV and the deck shelf), and the ceiling is coffered like the other state rooms.

### Portal rooms
- **`obelisk_player_room`** was the generic Slifer / Ra room with a single bed, though `interiors.json` lists a
  large bed and a balcony door. `_obelisk_player`: a double bed on the bed mark (`anchors.json`) with
  nightstands and a lamp, a glazed balcony door with navy drapes on the back wall, desk, wardrobe, card trunk,
  an OBELISK BLUE poster and a blue jacket by the door.
- **`obelisk_dining`** lists a portrait; it had none. Two gilded portraits hang either side of the crest.

### Shared helpers
These also change the girls' mansion, the Academy, Slifer and Ra:
- `interior.wainscot`: boards stop under the cap (every location with capped panelling).
- `obelisk.door` / `_door_surround`: the gilded bead on door surrounds (girls' mansion too).
- `obelisk.hollow_shell` / `_base_ring`: rings stop at joined corners; base gaps also cut the base band.
- `obelisk._coffers`, `_flight`, `_ensuite`, `_bedroom` nameplates, `_dress_hole` sills and thresholds.
- `detail.dress_room`: the ceiling rose / smoke detector go beside a keep-clear area under the room's centre.

### Check
- **Spiral stairs.** The cupola spiral's walking band is 0.32 m wide (core post to rail), narrower than the
  0.2 m walk grid resolves. As with narrow doorways, a spiral stair (`K.spiral_stairs`) whose foot is reached
  gets an exact test: a person-sized column (0.34 m radius, 1.85 m headroom) walked along the middle of the
  treads; when it passes, the flood goes on from the top.

## Results

| Check | First run | Final |
|---|---|---|
| `academy_check --location obelisk_boys`: NPC spots | 5 | **0** |
| doors (size / plane / frame / swing / head) | 19 | **0** |
| paths: rooms, doors and arrivals nobody can reach | the whole attic storey and the cupola (28 doors, 9 cameras), the duel salon arrival | **0** |
| paths: unreachable floor areas | 36 | 31 (see below) |
| walls: leaks / back faces | 0 / 0 (the attic and cupola were not reached, so not tested) | **0 / 0** |
| walls: z-fighting | 654 | 42 |
| `cell:obelisk_player_room`, `cell:obelisk_dining` | 0 | **0** |
| `spec_check.py obelisk` (both mansions: audit + detail coverage + people + painted windows) | - | **PASS** (boys 0/30, girls 0/21 views below target) |
| `audit_interiors.py` (every location) | academy 4 accepted, harbor 2 accepted, others 0 | unchanged |
| `academy_check --location ra` / `slifer` and the Ra / Slifer / Academy portal rooms | 0 | **0** |
| `validate_layout.py --strict`, `test_interiors.py` | PASS | PASS |

The 31 unreachable floor areas left are not floors anyone should reach:
- the tops of the four-poster bed canopies (2-2.6 m2 each, 1.5 m above the bedrooms' floors);
- the dining table top;
- the portico roof, the dome top, and the spaces over the attic ceilings behind the side dormers;
- closed voids inside solids: under the foyer's half landing, inside the portico stair cheeks;
- the fireside nook in four end-pavilion suite bedrooms (3.5-4 m2): the hearth sits behind the two armchairs
  facing it, between the en-suite wall and the window wall.

The 42 z-fighting entries are each 0.02-0.6 m2. Most are the backs of trim and fittings lying on wall faces
under the ceilings (frieze strips, panel and beam ends), which the visibility test cannot tell from visible
faces. Between two runs on the same geometry a few of them come and go with the test's ray sampling.

**Academy re-check** (shared helpers changed): NPC spots 0, doors 0, paths 153 (the known leftovers; 154
before), z-fighting 865 (882 before), back faces 25 (as before).

Not done here:
- Regenerate the FBXs and the level (`python Tools/build_island.py layout`, then the editor build).
- The girls' mansion only got the shared-helper changes; its own layout was not reviewed (its spec check and
  audit pass). Its two fireplaces call `K.fireplace` on wall points too and probably have the same surround-in-
  the-wall fault.
