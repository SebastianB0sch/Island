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

Run with the Blender-as-a-module interpreter, like the other audits. What it checks:

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

## Results

See the end of this file (filled in by the final run).
