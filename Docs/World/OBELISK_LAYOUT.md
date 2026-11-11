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
    stop them), 1.5 m above the spiral's treads. Coffer beams stop at every ceiling cut now (`_coffers`).
- **Cupola** (`ALIGNMENT_AUDIT.md`): the rail round the stair opening was one segment off and covered part of the
  top tread, and the floor ring started 10 cm outside the treads. The rail opening is over the top tread now,
  and a landing joins the top tread to the floor ring.
- **Box room:** three rolled carpets stood in the door's swing. They stand in the corner.
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
  beside the architraves.
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

RESULTS_PLACEHOLDER
