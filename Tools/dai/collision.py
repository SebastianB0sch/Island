"""
Collision for the furniture that is modelled into the no-collision meshes (<Location>_NoCol): tables, desks,
beds, benches, counters, cabinets, planters, ... built procedurally next to the decor that must stay walk-through
(rugs, trims, wall art, lamps, books, foliage, water).

The mesh is cut into pieces (faces welded by shared corners), touching pieces are grouped into items (a table
and its legs, the plates on it), and every item a person would bump into gets one oriented box. The boxes are
exported as UCX_ convex hulls with the mesh (UE: simple collision; the visual triangles stay non-colliding), so
the player and the NPCs stop at the furniture instead of walking through it.

An item gets no box when it is
  * flat on the floor (lower than 0.15 m: rugs, mats, floor decals) - you walk over it,
  * hung on a wall or from the ceiling (its bottom over 1.0 m above the floor under it),
  * architecture rather than furniture (longer than 6 m: trims, cornices, rails, beams),
  * mostly air (pieces fill < 2 % of its box: railings, frames, mobiles),
  * standing in a doorway,
  * made only of see-through / soft materials (water, light, smoke, foliage).
"""

import math

import numpy as np

from . import palette

SOFT_KINDS = {"water", "smoke", "beam", "hologram", "waterfall", "flow", "lava", "foliage", "glass"}
MIN_H, MAX_LEN, MAX_LIFT, MIN_FILL, MIN_SIZE = 0.15, 6.0, 1.0, 0.02, 0.25
MIN_THICK = 0.03      # window linings / thin trim boards are not furniture
GAP = 0.03            # pieces closer than this belong to one item


def _soft(mat):
    return palette.MATERIALS.get(mat, {}).get("kind", "opaque") in SOFT_KINDS or "Water" in mat or "Glow" in mat


def pieces(mb):
    """Connected pieces of a MeshBuilder: list of (min, max, vertex array)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    fidx = [i for i, (f, m) in enumerate(zip(mb.faces, mb.face_mats)) if len(f) >= 3 and not _soft(m)]
    if not fidx:
        return []
    owner, pts = [], []
    for k, i in enumerate(fidx):
        for vi in mb.faces[i]:
            v = mb.verts[vi]
            pts.append((v.x, v.y, v.z))
            owner.append(k)
    pts = np.asarray(pts, np.float64)
    owner = np.asarray(owner)
    key = np.round(pts * 1000.0).astype(np.int64)
    _, weld = np.unique(key, axis=0, return_inverse=True)
    weld = weld.ravel()
    nf, nv = len(fidx), int(weld.max()) + 1
    g = coo_matrix((np.ones(len(owner)), (owner, nf + weld)), shape=(nf + nv, nf + nv))
    n, lab = connected_components(g, directed=False)
    plab = lab[owner]
    order = np.argsort(plab, kind="stable")
    plab, pts_s = plab[order], pts[order]
    cuts = np.flatnonzero(np.diff(plab)) + 1
    out = []
    for chunk in np.split(pts_s, cuts):
        out.append((chunk.min(0), chunk.max(0), chunk))
    return out


def _union_find(n):
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    return find, union


def _obb(points):
    """Smallest-footprint box round the points, yaw searched in 3 deg steps: (centre, half, yaw_deg)."""
    p = points if len(points) <= 3000 else points[np.random.default_rng(0).choice(len(points), 3000, replace=False)]
    best = None
    for k in range(30):
        a = math.radians(k * 3.0)
        c, s = math.cos(a), math.sin(a)
        u = p[:, 0] * c + p[:, 1] * s
        v = -p[:, 0] * s + p[:, 1] * c
        area = (u.max() - u.min()) * (v.max() - v.min())
        if best is None or area < best[0] - 1e-9:
            best = (area, k * 3.0, (u.min(), u.max(), v.min(), v.max()))
    _, yaw, (u0, u1, v0, v1) = best
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
    z0, z1 = points[:, 2].min(), points[:, 2].max()
    return ((uc * c - vc * s, uc * s + vc * c, (z0 + z1) / 2), ((u1 - u0) / 2, (v1 - v0) / 2, (z1 - z0) / 2), yaw)


def _rect_overlap(c0, h0, y0, c1, h1, y1):
    """2D oriented rectangles overlap (separating axes)."""
    def axes(y):
        a = math.radians(y)
        return [(math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))]

    def proj(c, h, y, ax):
        (ux, uy), (vx, vy) = axes(y)
        m = c[0] * ax[0] + c[1] * ax[1]
        r = h[0] * abs(ux * ax[0] + uy * ax[1]) + h[1] * abs(vx * ax[0] + vy * ax[1])
        return m - r, m + r
    for ax in axes(y0) + axes(y1):
        a0, a1 = proj(c0, h0, y0, ax)
        b0, b1 = proj(c1, h1, y1, ax)
        if a1 <= b0 or b1 <= a0:
            return False
    return True


def blockers(mb, floor=None, doors=(), log=None):
    """Oriented boxes [(centre, half extents, yaw_deg)] for the furniture in a no-collision mesh.
    floor(x, y, z) -> height of the floor under a point (None: unknown); doors: [(pos, yaw, width, height)]."""
    ps = pieces(mb)
    keep = []
    for (mn, mx, pts) in ps:
        d = mx - mn
        if max(d[0], d[1]) > MAX_LEN or max(d) < 0.02:
            continue
        if d[2] < 0.06 and max(d[0], d[1]) > 0.3 and mn[2] < 0.15:   # a rug / mat on the floor
            continue
        if min(d) < MIN_THICK:                         # window linings / thin trim boards
            continue
        keep.append((mn, mx, pts))
    n = len(keep)
    find, union = _union_find(n)
    cells = {}
    for i, (mn, mx, _) in enumerate(keep):
        for cx in range(int(math.floor((mn[0] - GAP) / 1.0)), int(math.floor((mx[0] + GAP) / 1.0)) + 1):
            for cy in range(int(math.floor((mn[1] - GAP) / 1.0)), int(math.floor((mx[1] + GAP) / 1.0)) + 1):
                for cz in range(int(math.floor((mn[2] - GAP) / 1.0)), int(math.floor((mx[2] + GAP) / 1.0)) + 1):
                    cells.setdefault((cx, cy, cz), []).append(i)
    for members in cells.values():
        if len(members) < 2:
            continue
        for a_i in range(len(members)):
            a = members[a_i]
            amn, amx = keep[a][0], keep[a][1]
            for b in members[a_i + 1:]:
                bmn, bmx = keep[b][0], keep[b][1]
                if (amn[0] - GAP <= bmx[0] and bmn[0] - GAP <= amx[0] and amn[1] - GAP <= bmx[1]
                        and bmn[1] - GAP <= amx[1] and amn[2] - GAP <= bmx[2] and bmn[2] - GAP <= amx[2]):
                    union(a, b)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    out, why = [], {}
    for members in groups.values():
        pts = np.concatenate([keep[i][2] for i in members])
        mn, mx = pts.min(0), pts.max(0)
        d = mx - mn
        reason = None
        if max(d[0], d[1]) > MAX_LEN:
            reason = "architecture"
        elif d[2] < MIN_H:
            reason = "flat"
        elif max(d) < MIN_SIZE:
            reason = "small"
        if reason is None:
            c, h, yaw = _obb(pts)
            vol = 8.0 * max(h[0], 0.01) * max(h[1], 0.01) * max(h[2], 0.01)
            fill = sum(float(np.prod(np.maximum(keep[i][1] - keep[i][0], 0.01))) for i in members) / vol
            if fill < MIN_FILL:
                reason = "airy"
            elif floor is not None:
                fz = floor(c[0], c[1], mn[2] - 0.02)
                if fz is not None and mn[2] - fz > MAX_LIFT:
                    reason = "hung"
            if reason is None:
                for (dp, dyaw, dw, dh) in doors:
                    if (c[2] - h[2] < dp[2] + dh and c[2] + h[2] > dp[2] + 0.05 and
                            _rect_overlap(c, h, yaw, dp, (dw / 2 + 0.15, 0.7), dyaw)):
                        reason = "doorway"
                        break
        if reason:
            why[reason] = why.get(reason, 0) + 1
            continue
        out.append((c, h, yaw))
    if log:
        log(f"    {mb.name}: {len(ps)} pieces -> {len(groups)} items -> {len(out)} collision boxes "
            f"(skipped {', '.join(f'{v} {k}' for k, v in sorted(why.items()))})")
    return out


def box_soup(boxes, tag="Blocker"):
    """(verts, polys, tags) of the boxes, for the standing-room checks."""
    from mathutils import Vector
    verts, polys, tags = [], [], []
    for (c, h, yaw) in boxes:
        a = math.radians(yaw)
        ca, sa = math.cos(a), math.sin(a)
        base = len(verts)
        for (x, y, z) in ((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1), (-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)):
            lx, ly = x * h[0], y * h[1]
            verts.append(Vector((c[0] + lx * ca - ly * sa, c[1] + lx * sa + ly * ca, c[2] + z * h[2])))
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            polys.append([base + i for i in f])
            tags.append(tag)
    return verts, polys, tags


def ucx_objects(boxes, mesh_name):
    """UCX_<mesh>_NN box objects for FBX export (UE turns them into the mesh's simple collision)."""
    import bpy
    from .geo import MeshBuilder
    objs = []
    for i, (c, h, yaw) in enumerate(boxes):
        b = MeshBuilder(f"UCX_{mesh_name}_{i:03d}")
        with b.at((c[0], c[1], 0.0), rot=yaw):
            b.box((0.0, 0.0, c[2]), (2 * h[0], 2 * h[1], 2 * h[2]), "M_Concrete")
        o = b.build(f"UCX_{mesh_name}_{i:03d}")
        o.data.materials.clear()
        objs.append(o)
    return objs


def floor_fn(meshes):
    """floor(x, y, z): top of the collision geometry (the location's floors) below z."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    verts, polys = [], []
    for mb in meshes:
        base = len(verts)
        verts.extend(mb.verts)
        polys.extend([[base + i for i in f] for f in mb.faces if len(f) >= 3])
    if not polys:
        return None
    bvh = BVHTree.FromPolygons(verts, polys, all_triangles=False)

    def floor(x, y, z):
        loc, *_ = bvh.ray_cast(Vector((x, y, z)), Vector((0, 0, -1)), 30.0)
        return loc.z if loc is not None else None
    return floor


def asset_blockers(aset, log=None):
    """{no-collision mesh name: boxes} for an AssetSet (cached on it)."""
    if getattr(aset, "_blockers", None) is not None:
        return aset._blockers
    floating = {s["props"].get("mesh") for s in aset.sockets if s["type"] == "floating"}
    solid = [mb for n, mb in aset.meshes.items() if mb.verts and not n.endswith("_NoCol") and n not in floating]
    floor = floor_fn(solid)
    doors = [(s["pos"], s["yaw"], s["props"]["width"], s["props"]["height"]) for s in aset.sockets if s["type"] == "door"]
    out = {}
    for n, mb in aset.meshes.items():
        if n.endswith("_NoCol") and "_Glass" not in n and mb.verts and n not in floating:
            out[n] = blockers(mb, floor, doors, log)
    aset._blockers = out
    return out
