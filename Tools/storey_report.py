"""
Per-storey report: which floors of each building are real interiors and which are still closed.

A window that is still an opaque painted pane (M_Glass on a facade) has no room behind it; a real window is
an opening with clear glass (M_GlassClear / M_IntGlassClear). For every location this lists, per 1 m height
band, the painted vs real window panes, the interior cameras (rooms) on that level and the floor surfaces,
so closed storeys stand out. Works on the AssetSets directly (no Blender scene build): fast.

    python Tools/storey_report.py                 # every location module
    python Tools/storey_report.py academy obelisk
"""

import importlib
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,F401  (mathutils)

from dai.assets import LOCATION_MODULES  # noqa: E402

PAINTED = {"M_Glass"}
REAL = {"M_GlassClear", "M_IntGlassClear"}


def report(key, aset, band=1.0):
    painted, real, cams = defaultdict(float), defaultdict(float), defaultdict(list)
    for name, mb in aset.meshes.items():
        for f, m in zip(mb.faces, mb.face_mats):
            if m not in PAINTED and m not in REAL:
                continue
            vs = [mb.verts[i] for i in f]
            zc = sum(v.z for v in vs) / len(vs)
            # face area (fan triangulation)
            a = 0.0
            for i in range(1, len(vs) - 1):
                a += (vs[i] - vs[0]).cross(vs[i + 1] - vs[0]).length / 2
            if a < 0.05:
                continue
            (painted if m in PAINTED else real)[int(zc // band)] += a
    for s in aset.sockets:
        if s["type"] == "camera" and s["props"].get("label"):
            cams[int((s["pos"][2] - 1.5) // band)].append(s["props"]["label"])
    levels = sorted(set(painted) | set(real) | set(cams))
    if not levels:
        return 0
    print(f"=== {key}")
    print("   height    painted m2   real m2   rooms (interior cameras on that level)")
    closed = 0
    for lv in levels:
        p, r = painted.get(lv, 0.0), real.get(lv, 0.0)
        flag = "  <-- painted windows (closed storey?)" if p > 2.0 else ""
        closed += p > 2.0
        rooms = ", ".join(cams.get(lv, [])[:6]) + (" ..." if len(cams.get(lv, [])) > 6 else "")
        print(f"   {lv * band:5.0f} m   {p:9.1f}   {r:8.1f}   {rooms}{flag}")
    return closed


def main(argv):
    mods = argv or LOCATION_MODULES
    total = 0
    for m in mods:
        mod = importlib.import_module(f"dai.assets.{m}")
        for key, fn in getattr(mod, "PLACEMENTS", {}).items():
            total += report(key, fn())
    print(f"levels with painted windows: {total}")


if __name__ == "__main__":
    main(sys.argv[1:])
