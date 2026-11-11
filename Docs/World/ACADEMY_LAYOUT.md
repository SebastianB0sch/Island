# Duel Academy layout pass — 2026-11-10

Goal: every path in the Academy walkable (no asset in the way), doors scaled and framed, no NPC inside
furniture, walls aligned and complete, and the classrooms, lecture halls, offices and other rooms laid out
properly. Covers the in-place academy building (`Tools/dai/assets/academy.py`) and the four Academy portal
rooms (classroom, exam room, Crowler's and the Chancellor's offices — `Tools/dai/assets/interiors.py`).

## New check: `Tools/academy_check.py`

```powershell
python Tools/academy_check.py                       # everything (~15 min: builds the academy + every prop)
python Tools/academy_check.py --only doors,npcs     # a subset
python Tools/academy_check.py --only paths --region 80,0,104,10,101,3,6.6   # one spot, flooded from (101,3,6.6)
```

Run with the Blender-as-a-module interpreter, like the other audits. `--location slifer` checks the Slifer Red
dorm, `--location ra` the Ra Yellow dorm and `--location cell:<interior id>` a portal room with its
`anchors.json` marks. `SLIFER_LAYOUT.md` and `RA_LAYOUT.md` list the refinements made to the check on 2026-11-11:
- the furniture collision boxes are part of the walk grid;
- narrow doorways get an exact test;
- outdoor spots are not leak-tested, and trees and bushes don't count as walls;
- back faces are confirmed by neighbouring rays.

What it checks:

| Check | How |
|---|---|
| **doors** | For every door socket: the leaf against the real wall opening (jambs and head found by rays, 2 cm), the leaf on the opening's middle plane (faces found from the room side, framing skipped), an architrave round the opening on both faces (or flush posts + transom for doors in glazed screens), person-sized proportions, nothing in the leaf's 92° swing (walls, built-ins, furniture, props) and nothing lower than the leaf head over the swing area. A doorway that is walled up (solid inside the opening) is reported. |
| **paths** | A 0.2 m walk grid over every storey (stairs, tiers and ramps included; a person is a 0.34 m radius, 1.85 m column that steps up to 0.45 m), flood-filled from the fast-travel arrivals and the front steps. Both sides of every door, every NPC spot, every arrival and every room camera must be reachable; big enclosed floor areas nobody can reach are listed (roofs excluded). |
| **npcs** | Every NPC spot as authored: standing room (the layout stage's capsule test), not in a doorway, and room to wander. |
| **walls** | Rays from the floors that leave the building without passing a door or window (a gap), rays that hit the inside of a solid (a missing face), visible coplanar faces with different materials (z-fighting) and wall faces that meet 0.3–4 cm out of line. |

## What was wrong and what changed

### Paths blocked
- **Wall openings that overlapped each other were refilled with wall.** `MeshBuilder.wall` cut openings one after the
  other, so a door under an offset window (or two doors stacked on two storeys) got the solid above/below the
  other opening back. That walled up the lecture-hall doors (x 49.5 / 66 / 70 / 86 on both wings), the duelist
  room doors on both storeys (x 42.5) and narrowed the wing portals to 1.61 m. `geo.py` now cuts such walls
  in columns (only when openings overlap; every other wall is built exactly as before).
- **Pavilion stairs above 2F were unclimbable.** The next storey's half landing was a solid block down to the
  floor, overhanging the first treads of the flight below: a 1.84 m person stepping up hit its edge. Landings
  are 0.3 m slabs now. The cased ceiling beams of the 3F–5F stair halls also ran across the stairwell
  (1.75 m headroom on the landing) — they stop at the well now. A potted plant stood at the foot of the
  2F→3F flight — removed.
- **The pavilion ↔ wing galleries on 2F–4F were closed** by a wainscot panel running across the open archways
  (wainscots only left gaps at door *sockets*). Walls now record their open doorways (`AssetSet.openings`)
  and `detail._doors_on` returns them too, so wainscots, skirting and wall fixtures keep clear of every
  opening island-wide. The wing interiors are built after the pavilions, so they see the openings at x 88.
- **Painted facade panes covered 0.54 m of each wing portal.** Windows next to a portal are left out
  (`fwin(omit=...)`).
- **Classroom desks were 0.64 m apart** — less than a person. The pavilion classrooms use a 1.36 m column pitch
  (0.8 m aisles); `room_lite` classrooms keep ≥ 0.84 m aisles.
- Things standing in doorways or swings: the council-room agenda board hung across the inner office door, a
  painting hung on the annex office door leaf, canvases and shelves leaned across art-room doors, a club
  poster over the club hall door, store boxes in front of the annex store door (it used the pavilion's door
  list), a music-booth piano stool in the swing (the piano also stood backwards with its bench in the wall),
  a lab poster overlapping its door. `room_lite` rooms keep a 1.3 m zone clear in front of every door for
  fixtures, clutter, loose stock and plants.

### Doors scaled and framed
- Wing and pavilion side portals: 2.8 × 2.9 m (were 3.4 m, taller than the 3.3 m corridor ceilings and swinging
  into the 2.98 m ceiling beams). Duelist gates 4.4 × 4.2 m (they met the 4.4 m waiting-room ceiling).
- Lecture-hall doors open into the hall (trophy cases and lockers stand beside them in the corridor).
- Portal rooms: the door is a real leaf (or pair) — the same mesh as the automatic doors — closed on the wall's
  middle plane and filling a framed opening (architrave on the room face, reveal linings): 1.0 × 2.15 m single
  for the offices, 1.8 × 2.25 m pair for the classroom and exam room. Before: a 2.25 m wide single slab, 14 cm
  narrower and 10 cm shorter than its opening, off the wall plane.

### NPCs inside assets
- `build_academy()` now settles every NPC spot that clashes with a mesh face or prop (desk chairs, stools,
  sofas) to the nearest clear spot on the same floor in sight of the authored one (`_settle_npcs`); `room_lite`
  picks a clear spot near the room centre instead of dropping its NPC into the desk grid (`Ctx.npc_clear`).
  Lecture-hall students stand in the radial aisles (a tier leaves 0.33 m between desk and bench).
- In engine, NPCs without a precomputed route (the scheduled story NPCs from `spawns.json`) only take a random
  stroll target their capsule can reach in a straight line (`ADAStudentNPC::IsClearWalk`, a capsule sweep against
  static and dynamic geometry); otherwise they stand. They no longer push into desks until the stuck timer fires.
- Portal-room marks moved clear of furniture: classroom student 02, the Chancellor (now behind his desk, as the
  note says), Chumley.

### Walls, decor and room layout (portal rooms)
- Windows, skirting, crown moulding, blackboards (now facing the room), clocks, banners, posters, crests and the
  room sign sit on the wall faces instead of inside the 0.18 m walls; ceiling beams are flush with the ceiling.
- Furniture stands on the finished floor; lamps hang from the ceiling on stems; book cases are open shelves with
  the books standing on them; sideboards, wardrobes and book cases stand against walls without clipping; desks
  have their modesty panel on the front.
- Classroom: board, clock and the teacher's desk with the chair between desk and board; 6 × 5 student desks with
  1.07 m aisles; notice board. Exam room: 6 × 4 desks with 0.87 m aisles. Crowler's office: desk facing the
  door, display cabinet, trophy shelf. Chancellor's office: desk set back so the ending mark has 1 m clear all
  round, guest chairs, two book cases, globe, crest. Office side windows are in the door half of the room, so
  the book cases and cabinets stand on clear walls.

## Results (final run, 2026-11-11)

| Check | First run | Final |
|---|---|---|
| doors (size / plane / frame / swing / head) | 98 findings | **0** |
| NPC spots inside furniture | 27 | **0** |
| doors with a side nobody can reach | whole pavilions 3F-5F and wing 2F-4F cut off | **0** (the rear annex door's outside is terrain, not modelled) |
| room leaks (rays leaving a room through a gap) | - | **0** (262 reported rays all start in the open portico or on facade ledges) |
| `audit_interiors.py academy` | 4 accepted | 4 accepted (tower thresholds stand on terrain) |
| other locations (`audit_interiors.py`) | 2 accepted | 2 accepted (harbor) - the `geo` / `_doors_on` changes regress nothing |
| `spec_check.py academy` (audit + detail coverage + people + painted windows) | - | **PASS** (0 failures) |
| `validate_layout.py --strict`, `test_interiors.py` | PASS | PASS |

**Re-check 2026-11-11** (with the refined check of `SLIFER_LAYOUT.md`): doors 0 and NPC spots 0 as before.
Counting the furniture collision boxes added no unreachable door, NPC spot or arrival. Path entries went from
354 to 154: the old furniture-top rule had listed table tops and collision-box tops, and had hidden floor-level
pockets inside the lecture halls' hollow tier blocks, which are now listed. The shared sill and frame fixes cut
the z-fighting list from 2,376 to 1,168. The 72 leak rays all start in the open entrance portico (x ±14,
y -67).

**Re-check after the Ra pass** (`RA_LAYOUT.md`): NPC spots 0, doors 0, and the same 154 path entries.
- Leak rays 72 → 0: the portico counts as outdoors once tree and bush prop boxes no longer act as walls.
- Back faces 71 → 25: a back face must now repeat on rays 1 cm beside it.
- z-fighting 1,168 → 882: panelling boards are now 18 mm, behind the 24 mm skirting.
- The pavilion corridors got one more hanging dorm banner near the camera, keeping their views at the 35 %
  detail target.

Known leftovers (reported by the check, not defects of the building):

- *paths:* NPC spots in the 0.8 m classroom aisles show as "not reachable" because the 0.2 m grid with a 0.34 m
  radius cannot resolve a 0.8 m aisle; the exact capsule test passes them. The two arrival points in the hall
  and the arena are put on the floor by the layout stage. The three plaza NPCs stand on terrain.
- *unreachable floor:* the remaining areas are roofs, the inside of the pyramid, the space under the arena
  stands, closed tier blocks in the lecture halls, table tops, and a few 5-6 m2 corners behind racks in
  4F/5F store and club rooms.
- *walls:* the z-fighting list (2,376 visible coplanar overlaps) is mostly trim against trim; the back-face list
  is rays starting inside prop bounding boxes. Neither is a gap.
- The C++ change (`ADAStudentNPC::IsClearWalk`) could not be compiled in this environment; build the editor
  target once and run `-DANpcScheduleTest`.
- The FBXs / level are not regenerated here: run `python Tools/build_island.py layout` and the editor
  build (see `INTERIORS.md` / `ALIGNMENT_AUDIT.md`).
