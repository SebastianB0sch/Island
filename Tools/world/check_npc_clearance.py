#!/usr/bin/env python3
"""Check every scheduled NPC mark for standing room against the generated world.

Run inside Blender (the layout stage needs bpy / scipy from Tools/.blender_site):

    blender --background --factory-startup --python Tools/world/check_npc_clearance.py

Checks
------
* every interior mark is inside its portal cell, on the cell floor, with a clear
  NPC capsule (walls, furniture and built-in fixtures; the _NoCol dressing is
  ignored because it does not collide),
* every exterior mark has a clear NPC capsule against the whole generated island
  (buildings, furniture collision boxes, trees, rocks, terrain and water),
* no two scheduled spawns share an anchor or stand closer than two NPC capsules,
* a spawn does not use a player mark, and
* each spawn's Z offset follows the data convention (0 for interior cells,
  90 cm for exterior floor marks).

The in-engine `-DANpcScheduleTest` covers schedule behaviour; this check covers
the geometry that the schedule test cannot see without a built navmesh.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "Tools"
# Blender does not add the local wheelhouse to sys.path; the rest of the
# pipeline does the same in build_island_blender.py.
BLENDER_SITE = TOOLS / ".blender_site"
if BLENDER_SITE.is_dir():
    sys.path.insert(0, str(BLENDER_SITE))
sys.path.insert(0, str(TOOLS))

try:
    import bpy  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover - exercised by humans
    print("check_npc_clearance: run this with Blender "
          "(blender --background --factory-startup --python Tools/world/check_npc_clearance.py)",
          file=sys.stderr)
    raise SystemExit(2)

from mathutils import Vector  # noqa: E402

try:
    from dai import blend, layout, placement  # noqa: E402
    from dai.assets import interiors as interior_assets  # noqa: E402
except ModuleNotFoundError as error:  # scipy / numpy from the local wheelhouse
    print(f"check_npc_clearance: missing Python dependency '{error.name}'.\n"
          "Install the pipeline requirements into Blender's interpreter "
          "(see README: bpy / numpy / scipy / pillow) or populate Tools/.blender_site.",
          file=sys.stderr)
    raise SystemExit(2)


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def ue_to_layout(point: list[float]) -> Vector:
    """UE centimetres (+X east, +Y south) -> layout metres (+X east, +Y north)."""
    return Vector((float(point[0]) / 100.0, -float(point[1]) / 100.0, float(point[2]) / 100.0))


def interior_space(cell: dict):
    aset = interior_assets.build_cell(cell)
    solid = [mesh for name, mesh in aset.meshes.items()
             if mesh.verts and not name.endswith("_NoCol")]
    return placement.Checker([placement.mesh_space(solid, name=cell["id"])],
                             ground=lambda x, y: 0.0, ground_fallback=True)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Check authored NPC marks for standing room")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument("--json", action="store_true", help="print a machine-readable report")
    # Blender puts its own flags in sys.argv; ignore everything this parser
    # does not recognise (the documented command passes no extra flags).
    args, _unknown = parser.parse_known_args(argv)

    world = ROOT / "DuelAcademyIsland" / "Content" / "Data" / "World"
    anchors_doc = read_json(world / "anchors.json")
    interiors_doc = read_json(world / "interiors.json")
    spawns_doc = read_json(world / "spawns.json")

    anchors = {entry["id"]: entry for entry in anchors_doc.get("anchors", [])}
    cells = {entry["id"]: entry for entry in interiors_doc.get("cells", [])}
    spawns = spawns_doc.get("spawns", [])

    problems: list[str] = []
    warnings: list[str] = []
    checked_interior = 0
    checked_exterior = 0

    checked: dict[str, tuple[Vector, str]] = {}
    anchor_id_by_spawn: dict[str, str] = {}
    for spawn in spawns:
        spawn_id = str(spawn.get("id", ""))
        anchor_id = str(spawn.get("anchor_id", ""))
        anchor_id_by_spawn[spawn_id] = anchor_id
        anchor = anchors.get(anchor_id)
        if anchor is None:
            problems.append(f"spawn '{spawn_id}' references a missing anchor")
            continue
        point = ue_to_layout(anchor.get("position_ue", [0, 0, 0]))
        checked[spawn_id] = (point, str(anchor.get("interior_id") or ""))
        if anchor.get("kind") == "player":
            problems.append(f"spawn '{spawn_id}' stands on player mark '{anchor.get('id')}'")

        expected_z = 0.0 if anchor.get("interior_id") else 90.0
        offset = spawn.get("spawn_z_offset_cm")
        if not isinstance(offset, (int, float)) or abs(float(offset) - expected_z) > 0.1:
            warnings.append(f"spawn '{spawn_id}' has spawn_z_offset_cm={offset}; "
                            f"the convention is {expected_z:.0f}")

    # ---------------------------------------------------------------- interior cells
    by_cell: dict[str, list[dict]] = {}
    for spawn in spawns:
        anchor = anchors.get(str(spawn.get("anchor_id", "")))
        if anchor and anchor.get("interior_id"):
            by_cell.setdefault(str(anchor["interior_id"]), []).append(spawn)

    for cell_id, cell_spawns in sorted(by_cell.items()):
        cell = cells.get(cell_id)
        if cell is None:
            problems.append(f"spawns use unknown interior cell '{cell_id}'")
            continue
        box = [float(v) for v in cell.get("bounds_ue", [0] * 6)]
        origin = [float(v) for v in cell.get("origin_ue", [0, 0, 0])]
        checker = interior_space(cell)
        for spawn in cell_spawns:
            spawn_id = str(spawn.get("id", ""))
            anchor = anchors[str(spawn.get("anchor_id"))]
            ue = [float(v) for v in anchor.get("position_ue", [0, 0, 0])]
            if not (box[0] <= ue[0] <= box[3] and box[1] <= ue[1] <= box[4] and box[2] <= ue[2] <= box[5]):
                problems.append(f"{spawn_id}: anchor is outside interior cell '{cell_id}'")
                continue
            local = Vector(((ue[0] - origin[0]) / 100.0,
                            -(ue[1] - origin[1]) / 100.0))
            # Highest surface under the mark: a table/chair/desk shows up here.
            floor = checker.floor(Vector((local.x, local.y, 1.0)), above=1.0, below=1.6)
            if floor is None or abs(floor[0]) > 0.15:
                what = f"{floor[0]:+.2f} m" if floor else "none"
                problems.append(f"{spawn_id}: not on the {cell_id} floor ({what})")
                continue
            why = checker.capsule(Vector((local.x, local.y, 0.0)))
            if why:
                problems.append(f"{spawn_id}: {why} in {cell_id}")
            checked_interior += 1

    # ---------------------------------------------------------------- exterior island
    exterior_spawns = [spawn for spawn in spawns
                       if not (anchors.get(str(spawn.get("anchor_id", ""))) or {}).get("interior_id")]
    if exterior_spawns:
        blend.reset_scene()
        lay = layout.Layout(lambda *a, **k: None)
        lay.place_world()
        lay.place_locations(export=False)
        lay.place_path_dressing(export=False)
        lay.scatter()
        checker = lay.build_checker()
        for spawn in exterior_spawns:
            spawn_id = str(spawn.get("id", ""))
            anchor = anchors[str(spawn.get("anchor_id"))]
            point = ue_to_layout(anchor.get("position_ue", [0, 0, 0]))
            why = checker.capsule(point)
            if why:
                problems.append(f"{spawn_id}: {why} at {tuple(round(v, 1) for v in point)}")
            checked_exterior += 1

    # ---------------------------------------------------------------- duplicate / overlapping marks
    users: dict[str, list[str]] = {}
    for spawn_id in checked:
        users.setdefault(anchor_id_by_spawn.get(spawn_id, ""), []).append(spawn_id)
    for anchor_id, spawn_ids in sorted(users.items()):
        if len(spawn_ids) > 1:
            problems.append(f"anchor '{anchor_id}' is shared by {', '.join(sorted(spawn_ids))}")

    ids = sorted(checked)
    for i, left_id in enumerate(ids):
        left, _left_cell = checked[left_id]
        for right_id in ids[i + 1:]:
            right, _right_cell = checked[right_id]
            horizontal = math.hypot(left.x - right.x, left.y - right.y)
            if horizontal < 0.72 and abs(left.z - right.z) < 2.0:
                problems.append(f"spawns '{left_id}' and '{right_id}' are {horizontal * 100:.0f} cm apart "
                                "(capsules overlap)")

    failed = bool(problems) or (args.strict and bool(warnings))
    report = {
        "ok": not failed,
        "interior_marks": checked_interior,
        "exterior_marks": checked_exterior,
        "problems": problems,
        "warnings": warnings,
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("NPC clearance audit")
        print(f"  interior marks: {checked_interior}")
        print(f"  exterior marks: {checked_exterior}")
        if warnings:
            print(f"WARNINGS ({len(warnings)}):")
            for warning in warnings:
                print("  - " + warning)
        if problems:
            print(f"PROBLEMS ({len(problems)}):")
            for problem in problems:
                print("  - " + problem)
        print("PASS" if not failed else "FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
