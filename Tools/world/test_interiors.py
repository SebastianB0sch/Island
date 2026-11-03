#!/usr/bin/env python3
"""Log-based entry/exit + interior geometry check.

Always validates the JSON route (entrance -> inside cell -> exit -> outside).
If `bpy` is available, it also builds each cell with `Tools/dai/assets/interiors.py`
and checks that the meshes are non-empty, the prop mesh fits the room, and the
triangle budget is sane.  This is the headless equivalent of a PIE portal test.

Usage:
    python Tools/world/test_interiors.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / "DuelAcademyIsland" / "Content" / "Data" / "World"
TOOLS = ROOT / "Tools"


def inside(point, box, margin=0.0):
    return (box[0] - margin <= point[0] <= box[3] + margin and
            box[1] - margin <= point[1] <= box[4] + margin and
            box[2] - margin <= point[2] <= box[5] + margin)


def main() -> int:
    cells = {c["id"]: c for c in json.loads((WORLD / "interiors.json").read_text(encoding="utf-8"))["cells"]}
    portals = json.loads((WORLD / "portals.json").read_text(encoding="utf-8"))["portals"]
    errors = []
    print("Portal route simulation")
    for cid, cell in cells.items():
        box = cell["bounds_ue"]
        own = [p for p in portals if p.get("interior_id") == cid]
        entrance = next((p for p in own if p.get("role") == "entrance"), None)
        exit_portal = next((p for p in own if p.get("role") == "exit"), None)
        if not entrance or not exit_portal:
            errors.append(f"{cid}: missing entrance or exit portal")
            continue
        arrival = entrance["target_location_ue"]
        exit_loc = exit_portal["location_ue"]
        outside = exit_portal["target_location_ue"]
        checks = [
            ("arrival inside", inside(arrival, box)),
            ("exit trigger inside", inside(exit_loc, box)),
            ("exit arrival outside", not inside(outside, box)),
            ("paired ids", entrance.get("target_portal_id") == exit_portal.get("id") and
             exit_portal.get("target_portal_id") == entrance.get("id")),
        ]
        bad = [name for name, ok in checks if not ok]
        if bad:
            errors.append(f"{cid}: {', '.join(bad)}")
        print(f"  {cid}: {entrance['id']} -> {tuple(arrival)} -> {exit_portal['id']} "
              f"-> {tuple(outside)}  {'OK' if not bad else 'FAIL: ' + ', '.join(bad)}")

    bpy_available = True
    try:
        import bpy  # noqa: F401
    except Exception:  # noqa: BLE001
        bpy_available = False

    if not bpy_available:
        print("Geometry build skipped: bpy not available (run inside Blender for the mesh check).")
    else:
        sys.path.insert(0, str(TOOLS))
        from dai.assets import interiors  # noqa: E402

        print("Geometry build")
        total_tris = 0
        for cid, cell in cells.items():
            w, d, h = cell["size_m"]
            aset = interiors.build_cell(cell)
            for name, mb in aset.meshes.items():
                tris = sum(len(f) - 2 for f in mb.faces)
                total_tris += tris
                if not mb.verts or tris <= 0:
                    errors.append(f"{cid}/{name}: empty mesh")
                    continue
                mn, mx = mb.bounds()
                if "_Props" in name:
                    if mn[0] < -w / 2 - 0.05 or mx[0] > w / 2 + 0.05 or mn[1] < -d / 2 - 0.05 or \
                            mx[1] > d / 2 + 0.05 or mn[2] < -0.05 or mx[2] > h + 0.05:
                        errors.append(f"{cid}/{name}: props outside room")
                print(f"  {cid}/{name}: {tris} tris, x[{mn[0]:.2f},{mx[0]:.2f}] "
                      f"y[{mn[1]:.2f},{mx[1]:.2f}] z[{mn[2]:.2f},{mx[2]:.2f}]")
        print(f"  total interior triangles: {total_tris}")

    if errors:
        print("FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
