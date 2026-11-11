"""World-space alignment check for the Duel Academy Island layout.

Builds the layout in memory (no export) and checks, against the terrain *as it is drawn* (the triangles of
the exported mesh, terrain.MeshField - not the finer heightfield behind it):
  * road ribbons: clearance over the ground under every cross-section, level across the road;
  * ribbon ends: flush with the bridge deck, the main road or the ground they end on;
  * bridges: deck ends level with the road on both sides, abutments on the ground, the road straight under
    the deck, clearance over the water, piers down to the bed;
  * location base/wall vertices against the terrain or flat pad under them, and - for the locations that
    are built onto the terrain (villages, landmarks) - no gap under any footing;
  * every prop / vegetation instance outside buildings against the terrain,
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
from dai import terrain as T  # noqa: E402
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


# road ribbons: the paving lies Layout.RIBBON_LIFT above the ground; these are the limits of "lies on it"
RIBBON_MIN = 0.015       # less: the terrain shows through the paving
RIBBON_MAX = 0.20        # more: the paving visibly floats (the kerb skirt hides it, a step at the end does not)
RIM_MIN = -0.04          # the rim strip is drawn as the ground itself (paving coverage 0 at its edge) and its
RIM_EDGE = 0.0           # edge lies just under the ground (Layout.RIBBON_RIM_LIFT): it must not sink deeper than
                         # RIM_MIN, and its edge must nowhere stand more than RIM_EDGE out of the ground
JOINT_STEP = 0.03        # height step allowed where a ribbon meets a deck / another ribbon / the ground
BRIDGE_SIDE = 0.05       # sideways distance allowed between the road's centre line and the deck's


def check_roads(lay):
    """Ribbons vs the terrain triangles under them, and what each ribbon end meets."""
    failures = 0
    print("=== ROAD RIBBONS vs TERRAIN")
    decks = {}
    for bi in lay.bridge_info:
        b = bi["rec"]
        decks[(b["path"], round(b["s0"], 3))] = b["a"][2] + bi["lift"]
        decks[(b["path"], round(b["s1"], 3))] = b["b"][2] + bi["lift"]
    paths = {p["id"]: p for p in lay.meta["paths"]}
    tops = {p["id"]: lay.ribbon_sections(p) for p in lay.meta["paths"] if T.road_has_ribbon(p)}

    def ribbon_height(pid, x, y):
        """(distance to the nearest fully paved ribbon vertex of `pid`, its height)."""
        best = None
        for run in tops.get(pid, []):
            for _s, row in run:
                for q in row:
                    d = math.hypot(q[0] - x, q[1] - y)
                    if q[3] >= 1.0 and (best is None or d < best[0]):
                        best = (d, q[2])
        return best

    for pid, runs in tops.items():
        lo, hi, n = 1e9, -1e9, 0
        rim_lo, edge_hi = 1e9, -1e9
        worst_lo = worst_hi = worst_rim = worst_edge = None
        for run in runs:
            for (s0, r0), (s1, r1) in zip(run, run[1:]):
                for c in (0, len(r0) - 1):
                    # along both outer edges (rim on the ground: not where the paving meets a bridge deck)
                    if r0[c][3] >= 1.0 or r1[c][3] >= 1.0:
                        continue
                    for t in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
                        q = [r0[c][k] * (1 - t) + r1[c][k] * t for k in range(3)]
                        cl = q[2] - lay.ground(q[0], q[1])
                        if cl > edge_hi:
                            edge_hi, worst_edge = cl, (s0, q[0], q[1])
                for c in range(len(r0) - 1):
                    # a quad with a corner of coverage 0 belongs to the rim, where the paving thins out
                    rim = min(r0[c][3], r0[c + 1][3], r1[c][3], r1[c + 1][3]) < 1.0
                    # bilinear over the ribbon quad, 4 x 4 samples
                    for t in (0.0, 0.25, 0.5, 0.75):
                        for f in (0.0, 0.25, 0.5, 0.75):
                            q = [(r0[c][k] * (1 - f) + r0[c + 1][k] * f) * (1 - t)
                                 + (r1[c][k] * (1 - f) + r1[c + 1][k] * f) * t for k in range(3)]
                            cl = q[2] - lay.ground(q[0], q[1])
                            n += 1
                            if rim and cl < rim_lo:
                                rim_lo, worst_rim = cl, (s0, q[0], q[1])
                            if not rim and cl < lo:
                                lo, worst_lo = cl, (s0, q[0], q[1])
                            if cl > hi:
                                hi, worst_hi = cl, (s0, q[0], q[1])
        bad = []
        if lo < RIBBON_MIN:
            bad.append(f"ground within {lo * 100:+.1f} cm of the paving at s={worst_lo[0]:.0f} ({worst_lo[1]:.1f}, {worst_lo[2]:.1f})")
        if rim_lo < RIM_MIN:
            bad.append(f"rim {-rim_lo * 100:.1f} cm in the ground at s={worst_rim[0]:.0f} ({worst_rim[1]:.1f}, {worst_rim[2]:.1f})")
        if edge_hi > RIM_EDGE:
            bad.append(f"edge {edge_hi * 100:.1f} cm out of the ground at s={worst_edge[0]:.0f} ({worst_edge[1]:.1f}, {worst_edge[2]:.1f})")
        if hi > RIBBON_MAX:
            bad.append(f"paving {hi * 100:.0f} cm over the ground at s={worst_hi[0]:.0f} ({worst_hi[1]:.1f}, {worst_hi[2]:.1f})")
        print(f"  {pid:14s} {len(runs)} run(s), {n:6d} samples: clearance {lo * 100:5.1f} .. {hi * 100:5.1f} cm, "
              f"rim from {rim_lo * 100:4.1f} cm, edge {edge_hi * 100:+4.1f} cm  {'OK' if not bad else 'CHECK'}")
        for line in bad:
            print(f"       - {line}")
            failures += 1

    print("\n=== RIBBON ENDS (what the paving meets)")
    order = [q["id"] for q in lay.meta["paths"]]
    for pid, runs in tops.items():
        for run in runs:
            for (s_, row), where in ((run[0], "start"), (run[-1], "end")):
                mid = row[len(row) // 2]
                key = (pid, round(s_, 3))
                meets = None
                if key in decks:
                    meets, step = "bridge deck", max(abs(q[2] - decks[key]) for q in row)
                else:
                    for qid in tops:
                        if order.index(qid) >= order.index(pid):
                            continue
                        hit = ribbon_height(qid, mid[0], mid[1])
                        if hit and hit[0] < 2.5:
                            # every paved vertex of the end against the main road's paving beside it
                            step = max(abs(q[2] - ribbon_height(qid, q[0], q[1])[1]) for q in row if q[3] >= 1.0)
                            meets = f"road {qid}"
                            break
                if meets is None:
                    # a pad, a quay or open ground: the paving thins out into whatever lies there, and the
                    # whole end is rim - drawn as that ground and down on it
                    meets = "ground"
                    step = max(abs(q[2] - lay.ground(q[0], q[1]) - lay.RIBBON_RIM_LIFT) for q in row)
                    step = max(step, max(q[3] for q in row))       # (any paving left at the end counts as a step)
                ok = step <= JOINT_STEP + (0.03 if meets.startswith("road") else 0.0)
                print(f"  {pid:14s} {where:5s} s={s_:7.1f} meets {meets:22s} step {step * 100:4.1f} cm  "
                      f"{'OK' if ok else 'CHECK'}")
                failures += 0 if ok else 1
    return failures


def check_bridges(lay):
    failures = 0
    print("\n=== BRIDGES")
    paths = {p["id"]: p for p in lay.meta["paths"]}
    for bi in lay.bridge_info:
        b, name = bi["rec"], bi["name"]
        (ax, ay, az), (bx, by, bz) = b["a"], b["b"]
        run = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / run, (by - ay) / run
        nx, ny = -uy, ux
        issues = []
        # 1. the road is straight under the deck
        p = paths[b["path"]]
        smp = p["samples"]
        arc = [0.0]
        for i in range(1, len(smp)):
            arc.append(arc[-1] + math.hypot(smp[i][0] - smp[i - 1][0], smp[i][1] - smp[i - 1][1]))
        side = 0.0
        for (x, y, z), s_ in zip(smp, arc):
            if b["s0"] <= s_ <= b["s1"]:
                side = max(side, abs((x - ax) * nx + (y - ay) * ny))
        if side > BRIDGE_SIDE:
            issues.append(f"road centre line up to {side:.2f} m off the deck's")
        # 2. deck ends: level with the road, and on the ground (the abutment is buried, never hanging)
        half_w = bi["width"] / 2.0
        for label, (ex, ey, ez), sgn in (("start", b["a"], -1.0), ("end", b["b"], 1.0)):
            # the deck's own line carried half a metre on (road and deck are on a grade) against the road there
            slope = (bz - az) / max(run, 1e-6)
            deck = ez + slope * sgn * 0.5 + bi["lift"]
            for off in (-half_w * 0.8, 0.0, half_w * 0.8):
                road = lay.ground(ex + ux * sgn * 0.5 + nx * off, ey + uy * sgn * 0.5 + ny * off) \
                    + (bi["lift"] if b["surface"] == "paved" else 0.0)
                if abs(deck - road) > JOINT_STEP + 0.02:
                    issues.append(f"{label}: deck {100 * (deck - road):+.0f} cm against the road beyond it "
                                  f"({off:+.1f} m off centre)")
            for off in (-half_w, 0.0, half_w):
                for back in (0.3, 2.0, 3.5):
                    x, y = ex - ux * sgn * back + nx * off, ey - uy * sgn * back + ny * off
                    z_deck = ez + (az - bz if sgn > 0 else bz - az) * (back / max(run, 1e-6)) + bi["lift"]
                    gap = z_deck - lay.ground(x, y)
                    if gap > 0.45 and back <= 2.0:
                        issues.append(f"{label}: {gap:.2f} m of air under the deck {back:.1f} m in, {off:+.1f} m off centre")
                    if gap < -0.02:
                        issues.append(f"{label}: ground {-gap:.2f} m above the deck {back:.1f} m in, {off:+.1f} m off centre")
        # 3. over the water, and standing on something
        mid = bi["mid"]
        clear = mid[2] - b["water"]
        need = 1.75 if b["surface"] != "paved" else 2.25
        if clear < need:
            issues.append(f"only {clear:.2f} m over the water (wants {need:.2f})")
        (mn, mx) = bi["mb"].bounds()
        if mn[2] > b["bed"] - 0.3:
            issues.append(f"lowest masonry at {mn[2]:.2f} m does not reach the bed at {b['bed']:.2f} m")
        deck_top = max(az, bz) + bi["lift"]
        if mx[2] - deck_top < 0.95:
            issues.append(f"parapet / rail only {mx[2] - deck_top:.2f} m above the deck")
        print(f"  {name:22s} {b['kind']:5s} {bi['length']:5.1f} m  deck {clear:4.1f} m over the water, road off centre "
              f"{side * 100:4.1f} cm  {'OK' if not issues else 'CHECK'}")
        for line in dict.fromkeys(issues):
            print(f"       - {line}")
            failures += 1
    return failures


def check_footings(lay):
    """Locations built onto the terrain (absolute sets: villages, landmarks): no piece may hang in the air.
    Every separate piece of a collision mesh (a plinth, a post, a step, a boulder) must reach the ground with
    its lowest point, stand in water, or rest on another piece of its location."""
    import numpy as np
    from scipy.spatial import cKDTree
    failures = 0
    print("\n=== FOOTINGS OF TERRAIN-BUILT LOCATIONS")
    for key, aset in lay.assets.items():
        if not getattr(aset, "absolute", False):
            continue
        xf = lay.location_xforms[key]
        pieces = []                                   # (mesh name, world vertices of one connected piece)
        for name, mb in aset.meshes.items():
            if not mb.verts or name.endswith("_NoCol"):
                continue
            parent = list(range(len(mb.verts)))

            def find(i):
                while parent[i] != i:
                    parent[i] = parent[parent[i]]
                    i = parent[i]
                return i

            for f in mb.faces:
                r0 = find(f[0])
                for i in f[1:]:
                    parent[find(i)] = r0
            groups = {}
            for i, v in enumerate(mb.verts):
                groups.setdefault(find(i), []).append(xf.point((v.x, v.y, v.z)))
            pieces += [(name, np.asarray(g)) for g in groups.values()]
        if not pieces:
            print(f"  {key:14s}     0 pieces  OK")
            continue
        allv = np.vstack([g for _n, g in pieces])
        owner = np.concatenate([np.full(len(g), i) for i, (_n, g) in enumerate(pieces)])
        tree = cKDTree(allv[:, :2])
        bad = []
        for i, (name, g) in enumerate(pieces):
            gaps = g[:, 2] - np.array([lay.ground(x, y) for x, y, _z in g])
            j = int(np.argmin(gaps))
            if gaps[j] <= 0.05:
                continue                              # in the ground
            low = g[int(np.argmin(g[:, 2]))]
            if lay.water_at(low[0], low[1]) > lay.ground(low[0], low[1]):
                continue                              # a pile standing in water
            # resting on another piece: something of this location right under its lowest point
            near = [k for k in tree.query_ball_point(low[:2], 0.9) if owner[k] != i]
            if any(low[2] - 0.6 <= allv[k][2] <= low[2] + 0.08 for k in near):
                continue
            # or its bottom lies within the footprint of a bigger piece below it (a slab on a deck)
            if any(owner[k] != i and allv[k][2] < low[2] + 0.08 for k in tree.query_ball_point(low[:2], 3.0)):
                continue
            bad.append((float(gaps[j]), name, g[j]))
        if bad:
            bad.sort(key=lambda t: -t[0])
            print(f"  {key:14s} {len(pieces):5d} pieces  CHECK ({len(bad)} off the ground)")
            for gap, name, w in bad[:4]:
                print(f"       - {name}: a piece {gap * 100:.0f} cm above the ground at ({w[0]:.1f}, {w[1]:.1f}, {w[2]:.2f})")
            failures += len(bad)
        else:
            print(f"  {key:14s} {len(pieces):5d} pieces  OK")
    return failures


def check_world_points(lay):
    """Story anchors on open ground (Content/Data/World/anchors.json, kind "player" outside every pad): a
    player anchor is authored on or up to ~1.2 m above the surface it stands on. Regrading the ground under
    one must not leave the player buried in it or dropped onto it from a height."""
    import json
    failures = 0
    print("\n=== STORY ANCHORS ON OPEN GROUND")
    path = os.path.join(layout.C.UE_PROJECT_DIR, "Content", "Data", "World", "anchors.json")
    try:
        with open(path, "r", encoding="utf-8") as fp:
            anchors = json.load(fp).get("anchors", [])
    except OSError:
        print("  anchors.json not found: skipped")
        return 0
    import numpy as np
    from scipy.spatial import cKDTree
    trees = {}

    def on_structure(x, y, z):
        """Is there a walking surface of a nearby location 0.4 - 2 m under the anchor (a deck, a quay)?"""
        for key, aset in lay.assets.items():
            lx, ly = layout.C.LOCATIONS[key]["pos"]
            if math.hypot(lx - x, ly - y) > 450.0:
                continue
            if key not in trees:
                xf = lay.location_xforms[key]
                pts = np.asarray([xf.point((v.x, v.y, v.z)) for name, mb in aset.meshes.items()
                                  if not name.endswith("_NoCol") for v in mb.verts])
                trees[key] = (cKDTree(pts[:, :2]), pts) if len(pts) else None
            if trees[key] is None:
                continue
            tree, pts = trees[key]
            if any(z - 2.0 <= pts[i][2] <= z - 0.4 for i in tree.query_ball_point([x, y], 2.5)):
                return True
        return False

    n = 0
    for a in anchors:
        p = a.get("position_ue")
        if a.get("kind") != "player" or a.get("interior_id") or not p or p[2] < -2000:
            continue
        x, y, z = p[0] / 100.0, -p[1] / 100.0, p[2] / 100.0
        if lay.in_any_pad(x, y, 6.0) is not None:
            continue                               # on a building's own floors (audit_interiors.py)
        n += 1
        above = z - lay.ground(x, y)
        if 0.95 <= above <= 1.45:
            continue
        if above < -0.05:
            print(f"    {a.get('id')}: buried {-above:.2f} m in the ground at ({x:.0f}, {y:.0f})  CHECK")
            failures += 1
        elif above > 1.45 and not on_structure(x, y, z):
            print(f"    {a.get('id')}: {above:.2f} m of air under it at ({x:.0f}, {y:.0f})  CHECK")
            failures += 1
        else:
            print(f"    {a.get('id')}: {above:+.2f} m above the terrain at ({x:.0f}, {y:.0f}) "
                  f"({'on a structure' if above > 1.45 else 'authored that way'})")
    print(f"  checked {n} anchors")
    return failures


def main():
    blend.reset_scene()
    lay = layout.Layout(lambda *a, **k: None)
    lay.place_world()
    lay.place_locations(export=False)
    lay.place_bridges(export=False)
    lay.place_path_dressing(export=False)
    lay.place_life(export=False)
    lay.scatter()
    ck = lay.build_checker()
    # invisible furniture collision boxes are not walking surfaces at a threshold
    placement.SOFT = tuple(placement.SOFT) + ("Blocker",)

    failures = 0
    failures += check_roads(lay)
    failures += check_bridges(lay)
    failures += check_footings(lay)
    failures += check_world_points(lay)
    print()

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
    # world props, plus the props of the locations that are built onto the terrain (their own floors are
    # the ground); props of the pad locations stand on building floors and are audited by audit_interiors.py
    absolute = {key for key, aset in lay.assets.items() if getattr(aset, "absolute", False)}
    outdoor = [(a, p, yaw, sc, key) for a, p, yaw, sc, key in lay.inst_all
               if (key is None or key in absolute) and not a.startswith("SM_Int_")]
    names = {it[0] for it in outdoor}
    bounds = placement.prop_bounds(names, log=lambda m: None)
    # a prop of a terrain-built location may stand on that location's own decks, steps and plinths
    from scipy.spatial import cKDTree
    import numpy as np
    structure = {}
    for key in absolute:
        xf = lay.location_xforms[key]
        pts = [xf.point((v.x, v.y, v.z)) for name, mb in lay.assets[key].meshes.items()
               if not name.endswith("_NoCol") for v in mb.verts]
        structure[key] = (cKDTree(np.asarray(pts)[:, :2]), np.asarray(pts)) if pts else None
    groups = {}
    checked = 0
    vx, vy = layout.C.VOLCANO_CENTER
    for asset, p, yaw, scale, key in outdoor:
        if asset in P.FLOATING_PROPS:
            continue
        if key == "volcano" and math.hypot(p[0] - vx, p[1] - vy) < 70.0:
            continue                               # crust islands drifting on the lava lake
        if key is not None and structure.get(key):
            tree, pts = structure[key]
            near = tree.query_ball_point([p[0], p[1]], 1.8)
            base = p[2] + (bounds.get(asset) or ((0, 0, 0),))[0][2] * scale
            if any(base - 0.4 <= pts[i][2] <= base + 0.15 for i in near):
                continue                       # on a deck / a step / a plinth of its location
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
