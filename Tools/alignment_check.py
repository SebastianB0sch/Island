"""World-space alignment check for the Duel Academy Island layout.

Builds the layout in memory (no export) and checks
  * location base/wall vertices against the terrain or flat pad under them,
  * every non-location prop / vegetation instance against the terrain,
  * every automatic-door threshold against the world floor,
  * vegetation that lands inside a building volume or within 1.6 m of a door.

Run with Blender (the layout stage needs bpy / scipy):

    blender --background --factory-startup --python Tools/alignment_check.py

The script prints the findings and exits 1 when a location base, door threshold
or building-intersection check fails. Scatter sink groups are reported for
review; the deliberate rock sinks are not failures.
"""

import math
import os
import sys

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
BLENDER_SITE = os.path.join(TOOLS, ".blender_site")
if os.path.isdir(BLENDER_SITE):
    sys.path.insert(0, BLENDER_SITE)

import bpy  # noqa: E402,F401
from mathutils import Vector  # noqa: E402

from dai import blend, layout, placement  # noqa: E402
from dai.assets import props as P  # noqa: E402

TOL_FLOAT = 0.20
TOL_SINK = 0.60
TOL_EDGE = 0.35
# structures that intentionally stand over water / outside their pad
OVER_WATER = {"harbor", "lighthouse", "obelisk_girls"}
# known exceptions already accepted by Tools/spec_check.py
ACCEPTED_DOORS = ("academy door academy 3.00x3.80", "abandoned door abandoned 2.40x3.20")


def world_bounds(aset, xf):
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for mb in aset.meshes.values():
        if not mb.verts:
            continue
        (x0, y0, z0), (x1, y1, z1) = mb.bounds()
        for x in (x0, x1):
            for y in (y0, y1):
                w = xf.point((x, y, z0))
                mn.x, mn.y, mn.z = min(mn.x, w[0]), min(mn.y, w[1]), min(mn.z, w[2])
                w = xf.point((x, y, z1))
                mx.x, mx.y, mx.z = max(mx.x, w[0]), max(mx.y, w[1]), max(mx.z, w[2])
    return mn, mx


def main():
    blend.reset_scene()
    lay = layout.Layout(lambda *a, **k: None)
    lay.place_world()
    lay.place_locations(export=False)
    lay.place_path_dressing(export=False)
    lay.scatter()
    ck = lay.build_checker()
    # invisible furniture collision boxes are not walking surfaces at a threshold
    placement.SOFT = tuple(placement.SOFT) + ("Blocker",)

    failures = 0

    print("=== LOCATION BASE vs TERRAIN / PAD")
    for key, aset in lay.assets.items():
        xf = lay.location_xforms[key]
        if getattr(aset, "absolute", False):
            print(f"  {key:14s} absolute-height feature: skipped")
            continue
        if key in OVER_WATER:
            print(f"  {key:14s} over-water structure: base check skipped")
            continue
        mn, mx = world_bounds(aset, xf)
        pad = lay.info["pads"].get(key)
        issues = []
        if pad is not None and abs(xf.z - pad) > 0.01:
            issues.append(f"placed at z={xf.z:.2f} but pad height is {pad:.2f}")
        base = []
        for mb in aset.meshes.values():
            if not mb.verts:
                continue
            n = len(mb.verts)
            stride = max(1, n // 1500)
            for i in range(0, n, stride):
                v = mb.verts[i]
                if -0.5 <= v.z <= 0.5:
                    w = xf.point((v.x, v.y, v.z))
                    base.append((w[0], w[1], lay.ground(w[0], w[1]) - xf.z))
        if base:
            lo = min(base, key=lambda t: t[2])
            hi = max(base, key=lambda t: t[2])
            if lo[2] < -TOL_EDGE:
                issues.append(f"terrain {lo[2]:+.2f} m below the base at ({lo[0]:.1f}, {lo[1]:.1f})")
            if hi[2] > TOL_EDGE:
                issues.append(f"terrain {hi[2]:+.2f} m above the base at ({hi[0]:.1f}, {hi[1]:.1f})")
        print(f"  {key:14s} z={xf.z:7.2f} base={len(base):5d}  "
              f"{'OK' if not issues else 'CHECK'}")
        for line in issues:
            print(f"       - {line}")
            failures += 1

    print("\n=== WORLD PROPS / VEGETATION vs TERRAIN")
    names = {it[0] for it in lay.inst_raw}
    bounds = placement.prop_bounds(names, log=lambda m: None)
    groups = {}
    checked = 0
    for asset, p, yaw, scale in lay.inst_raw:
        if asset in P.FLOATING_PROPS:
            continue
        b = bounds.get(asset)
        if not b:
            continue
        bottom = p[2] + b[0][2] * scale
        g = lay.ground(p[0], p[1])
        checked += 1
        d = bottom - g
        if d > TOL_FLOAT or d < -TOL_SINK:
            rec = groups.setdefault(asset, [0, 0.0, 0.0, None])
            rec[0] += 1
            rec[1] = min(rec[1], d)
            rec[2] = max(rec[2], d)
            if rec[3] is None or abs(d) > abs(rec[3][0]):
                rec[3] = (d, p, g, bottom)
    print(f"  checked {checked} instances; {sum(v[0] for v in groups.values())} "
          f"outside [{ -TOL_SINK:+.2f}, {TOL_FLOAT:+.2f}] m in {len(groups)} groups")
    for asset, (n, dmin, dmax, ex) in sorted(groups.items(), key=lambda kv: -kv[1][0]):
        d, p, g, bottom = ex
        print(f"    {asset:24s} n={n:5d} delta {dmin:+.2f}..{dmax:+.2f} m  "
              f"worst at ({p[0]:7.1f},{p[1]:7.1f}) base {bottom:7.2f} ground {g:7.2f}")
    # only positive floats are suspicious; the negative sinks are deliberate scatter sinks
    for asset, (n, dmin, dmax, ex) in groups.items():
        if dmax > TOL_FLOAT:
            failures += 1

    print("\n=== DOOR THRESHOLDS vs WORLD FLOOR")
    n_doors = 0
    for key, aset in lay.assets.items():
        xf = lay.location_xforms[key]
        for s in aset.sockets:
            if s["type"] != "door":
                continue
            n_doors += 1
            p = Vector(xf.point(s["pos"]))
            a = math.radians(xf.yaw + s["yaw"])
            n_out = Vector((math.sin(a), -math.cos(a), 0.0))
            pr = s["props"]
            label = f"{key} door {pr['style']} {pr['width']:.2f}x{pr['height']:.2f} @ ({p.x:.1f},{p.y:.1f},{p.z:.2f})"
            for side, sgn in (("outside", 1), ("inside", -1)):
                q = p + n_out * sgn * 0.7
                top = Vector((q.x, q.y, q.z + 0.6))
                hit = ck._hit(top, Vector((0, 0, -1)), 1.8, ck.spaces_at(q), through_props=True)
                f = (top.z - hit[0], hit[2]) if hit else None
                if f is None or abs(f[0] - p.z) > 0.21:
                    what = "none" if f is None else f"{100 * (f[0] - p.z):+.0f} cm"
                    accepted = label.startswith(ACCEPTED_DOORS)
                    print(f"    {label}: no floor at threshold height {side} ({what})"
                          + ("  [accepted]" if accepted else ""))
                    if not accepted:
                        failures += 1
    print(f"  checked {n_doors} doors")

    print("\n=== VEGETATION INSIDE BUILDINGS / DOORS")
    inside = []
    near_door = []
    doors_world = [(Vector((d["loc"][0] / 100.0, -d["loc"][1] / 100.0, d["loc"][2] / 100.0)),
                    d.get("group", "")) for d in lay.doors]
    for asset, p, yaw, scale in lay.inst_raw:
        if asset in P.FLOATING_PROPS:
            continue
        q = Vector(p)
        for sp in lay.spaces:
            if sp.near(q, 0.8) and sp.ray(q + Vector((0, 0, 0.6)), Vector((0, 0, 1)), 2.0):
                inside.append((asset, p, sp.name))
                break
        for dp, group in doors_world:
            if math.hypot(q.x - dp.x, q.y - dp.y) < 1.6 and abs(q.z - dp.z) < 2.0:
                near_door.append((asset, p, group))
                break
    for asset, p, name in inside:
        print(f"    {asset:24s} at ({p[0]:7.1f},{p[1]:7.1f},{p[2]:7.2f}) in {name}")
    for asset, p, group in near_door:
        print(f"    {asset:24s} at ({p[0]:7.1f},{p[1]:7.1f},{p[2]:7.2f}) near {group}")
    print(f"  inside building volumes: {len(inside)}; within 1.6 m of a door: {len(near_door)}")
    failures += len(inside) + len(near_door)

    print(f"\nALIGNMENT FAILURES: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
