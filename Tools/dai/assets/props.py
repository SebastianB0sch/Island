"""
Shared prop + vegetation catalog geometry (see catalog.py for the name list).

Each builder returns (MeshBuilder, [collision MeshBuilders]) - collision pieces
are exported as UCX_<name>_NN convex hulls so instanced foliage / props get
cheap simple collision in Unreal. An empty list means "no collision".
Stylised anime look: chunky shapes, solid leaf blobs instead of alpha cards.
"""

import math
import os
import random

from mathutils import Matrix, Vector

from ..geo import MeshBuilder, TAU
from .. import blend, palette
from .catalog import CATALOG

palette.register({
    "M_FlagRed":    dict(kind="foliage", color=(0.80, 0.10, 0.08), rough=0.9, detail="Fabric", tiling=1.0),
    "M_FlagYellow": dict(kind="foliage", color=(0.98, 0.80, 0.15), rough=0.9, detail="Fabric", tiling=1.0),
    "M_FlagBlue":   dict(kind="foliage", color=(0.12, 0.30, 0.78), rough=0.9, detail="Fabric", tiling=1.0),
    "M_Coconut":    dict(kind="opaque", color=(0.35, 0.25, 0.12), rough=0.8, detail=None),
    "M_Umbrella":   dict(kind="opaque", color=(0.95, 0.35, 0.25), rough=0.8, detail="Fabric", tiling=1.0),
    "M_Vending":    dict(kind="opaque", color=(0.80, 0.12, 0.15), rough=0.4, detail=None),
})


# --------------------------------------------------------------------------- helpers
def _frame(t, prev_n=None):
    t = t.normalized()
    if prev_n is None:
        up = Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((1, 0, 0))
        n = t.cross(up).normalized()
    else:
        n = (prev_n - t * prev_n.dot(t)).normalized()
    b = t.cross(n).normalized()
    return n, b


def tube(mb, pts, radii, mat, seg=8, cap_top=True, smooth=True):
    """Generalised cylinder along a 3D polyline with per-point radius (parallel transport frames)."""
    pts = [Vector(p) for p in pts]
    rows = []
    n_prev = None
    for i, p in enumerate(pts):
        if i == 0:
            t = pts[1] - pts[0]
        elif i == len(pts) - 1:
            t = pts[-1] - pts[-2]
        else:
            t = pts[i + 1] - pts[i - 1]
        n, b = _frame(t, n_prev)
        n_prev = n
        r = radii[i]
        rows.append([tuple(p + (n * math.cos(TAU * k / seg) + b * math.sin(TAU * k / seg)) * r) for k in range(seg)])
    # orientation: grid_faces expects rows ordered along the tube with CCW rings around +t
    mb.grid_faces(rows, mat, smooth=smooth, closed_u=True)
    if cap_top and radii[-1] > 1e-3:
        mb.poly(rows[-1], mat)


def blob(mb, center, radius, mat, seed=0, seg=10, rings=8, scale=(1, 1, 1), rough=0.18, flat_bottom=0.0):
    """Lumpy sphere (leaf clusters, rocks)."""
    rnd = random.Random(seed)
    ph = [rnd.uniform(0, TAU) for _ in range(6)]
    fr = [rnd.uniform(1.5, 3.5) for _ in range(6)]
    cx, cy, cz = center
    rows = []
    for j in range(rings + 1):
        phi = -math.pi / 2 + math.pi * j / rings
        row = []
        for i in range(seg):
            th = TAU * i / seg
            d = Vector((math.cos(phi) * math.cos(th), math.cos(phi) * math.sin(th), math.sin(phi)))
            n = (math.sin(d.x * fr[0] + ph[0]) * math.sin(d.y * fr[1] + ph[1]) +
                 math.sin(d.z * fr[2] + ph[2]) * 0.7 + math.sin((d.x + d.z) * fr[3] + ph[3]) * 0.5)
            r = radius * (1.0 + rough * n * 0.5)
            p = Vector((d.x * r * scale[0], d.y * r * scale[1], d.z * r * scale[2]))
            if flat_bottom > 0 and p.z < -radius * scale[2] * (1 - flat_bottom):
                p.z = -radius * scale[2] * (1 - flat_bottom)
            row.append((cx + p.x, cy + p.y, cz + p.z))
        rows.append(row)
    mb.grid_faces(rows, mat, smooth=True, closed_u=True)


def box_col(mn, mx):
    c = MeshBuilder("col")
    c.box_mm(mn, mx, "M_Black")
    return c


def cyl_col(base, r, h, seg=8):
    c = MeshBuilder("col")
    c.cylinder(base, r, h, "M_Black", seg=seg, smooth=False)
    return c


def bezier(p0, p1, p2, n):
    out = []
    for i in range(n + 1):
        t = i / n
        a = (1 - t) ** 2
        b = 2 * (1 - t) * t
        c = t * t
        out.append(Vector(p0) * a + Vector(p1) * b + Vector(p2) * c)
    return out


# --------------------------------------------------------------------------- vegetation
def palm(seed, height, lean):
    mb = MeshBuilder("palm")
    rnd = random.Random(seed)
    yaw = rnd.uniform(0, TAU)
    top = Vector((math.cos(yaw) * lean, math.sin(yaw) * lean, height))
    mid = Vector((math.cos(yaw) * lean * 0.15, math.sin(yaw) * lean * 0.15, height * 0.55))
    pts = bezier((0, 0, -0.5), mid, top, 10)
    radii = [0.34 - 0.16 * (i / 10) for i in range(11)]
    tube(mb, pts, radii, "M_PalmBark", seg=9)
    # trunk rings
    for i in range(1, 10):
        tube(mb, [pts[i] - (pts[i] - pts[i - 1]).normalized() * 0.05, pts[i] + (pts[i] - pts[i - 1]).normalized() * 0.08],
             [radii[i] * 1.12, radii[i] * 1.12], "M_PalmBark", seg=9, cap_top=False)
    # crown
    blob(mb, tuple(top), 0.45, "M_PalmBark", seed, seg=8, rings=6)
    nf = rnd.randint(8, 10)
    for k in range(nf):
        a = TAU * k / nf + rnd.uniform(-0.2, 0.2)
        L = rnd.uniform(4.0, 5.2)
        up = rnd.uniform(0.5, 1.2)
        droop = rnd.uniform(2.2, 3.4)
        d = Vector((math.cos(a), math.sin(a), 0))
        p0 = top + Vector((0, 0, 0.2))
        p1 = p0 + d * L * 0.5 + Vector((0, 0, up))
        p2 = p0 + d * L + Vector((0, 0, up - droop))
        spine = bezier(p0, p1, p2, 7)
        side = Vector((-d.y, d.x, 0))
        rows_l, rows_r, rows_c = [], [], []
        for i, sp in enumerate(spine):
            t = i / 7
            w = 0.75 * math.sin(math.pi * min(1.0, t * 1.15 + 0.05))
            rows_c.append(tuple(sp))
            rows_l.append(tuple(sp + side * w + Vector((0, 0, -0.18 * w))))
            rows_r.append(tuple(sp - side * w + Vector((0, 0, -0.18 * w))))
        for i in range(7):
            mb.quad(rows_c[i], rows_l[i], rows_l[i + 1], rows_c[i + 1], "M_LeavesPalm", smooth=True)
            mb.quad(rows_r[i], rows_c[i], rows_c[i + 1], rows_r[i + 1], "M_LeavesPalm", smooth=True)
    for k in range(rnd.randint(3, 5)):
        a = rnd.uniform(0, TAU)
        mb.sphere(tuple(top + Vector((math.cos(a) * 0.45, math.sin(a) * 0.45, -0.35))), 0.2, "M_Coconut", seg=8, rings=6)
    col = [cyl_col((0, 0, 0), 0.35, height * 0.6)]
    return mb, col


def broadleaf(seed, height, crown, tiers=1, leaves="M_LeavesBroad"):
    mb = MeshBuilder("tree")
    rnd = random.Random(seed)
    trunk_h = height * 0.45
    bend = Vector((rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 0))
    pts = bezier((0, 0, -0.5), (bend.x * 0.5, bend.y * 0.5, trunk_h * 0.5), (bend.x, bend.y, trunk_h), 6)
    radii = [0.55 * (height / 12) * (1 - 0.45 * i / 6) for i in range(7)]
    radii[0] *= 1.4
    tube(mb, pts, radii, "M_Bark", seg=9)
    top = pts[-1]
    # branches
    nb = rnd.randint(3, 5)
    tips = []
    for k in range(nb):
        a = TAU * k / nb + rnd.uniform(-0.4, 0.4)
        L = crown * rnd.uniform(0.45, 0.7)
        d = Vector((math.cos(a), math.sin(a), rnd.uniform(0.5, 0.9))).normalized()
        b0 = top - Vector((0, 0, rnd.uniform(0.2, 1.0)))
        b1 = b0 + d * L
        tube(mb, [b0, b0 + d * L * 0.5 + Vector((0, 0, 0.3)), b1], [radii[-1] * 0.6, radii[-1] * 0.4, radii[-1] * 0.2], "M_Bark", seg=6)
        tips.append(b1)
    # canopy
    cz = top.z + crown * 0.45
    for t in range(tiers):
        tz = cz + t * crown * 0.55
        rr = crown * (1.0 - 0.25 * t)
        blob(mb, (top.x, top.y, tz), rr * 0.75, leaves, seed * 7 + t, seg=12, rings=8, scale=(1, 1, 0.7), rough=0.25)
        for k in range(5 - t):
            a = TAU * k / (5 - t) + rnd.uniform(-0.3, 0.3) + t
            off = Vector((math.cos(a) * rr * 0.7, math.sin(a) * rr * 0.7, rnd.uniform(-0.4, 0.2) * rr))
            blob(mb, tuple(Vector((top.x, top.y, tz)) + off), rr * rnd.uniform(0.42, 0.58), leaves, seed * 13 + k + t * 5,
                 seg=10, rings=7, scale=(1, 1, 0.75), rough=0.3)
    col = [cyl_col((0, 0, 0), radii[1] * 1.1, trunk_h)]
    return mb, col


def pine(seed, height):
    mb = MeshBuilder("pine")
    rnd = random.Random(seed)
    tube(mb, [(0, 0, -0.5), (0, 0, height * 0.5), (0, 0, height * 0.95)], [0.42, 0.28, 0.08], "M_Bark", seg=8)
    n = 6
    for i in range(n):
        t = i / n
        z = height * (0.22 + 0.72 * t)
        r = height * 0.26 * (1 - t * 0.8)
        h = height * 0.28 * (1 - t * 0.4)
        off = (rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15))
        mb.cone((off[0], off[1], z - h * 0.35), r, h, "M_LeavesPine", seg=11)
    col = [cyl_col((0, 0, 0), 0.45, height * 0.5)]
    return mb, col


def dead_tree(seed, height):
    mb = MeshBuilder("dead")
    rnd = random.Random(seed)

    def branch(p, d, L, r, depth):
        pts = [p]
        cur = Vector(p)
        dd = Vector(d).normalized()
        for _ in range(4):
            dd = (dd + Vector((rnd.uniform(-0.35, 0.35), rnd.uniform(-0.35, 0.35), rnd.uniform(-0.15, 0.25)))).normalized()
            cur = cur + dd * (L / 4)
            pts.append(cur.copy())
        radii = [r * (1 - 0.7 * i / 4) for i in range(5)]
        tube(mb, pts, radii, "M_DeadBark", seg=6 if depth == 0 else 5)
        if depth < 2:
            for _ in range(rnd.randint(2, 3)):
                k = rnd.randint(2, 4)
                a = rnd.uniform(0, TAU)
                nd = Vector((math.cos(a), math.sin(a), rnd.uniform(0.2, 0.9)))
                branch(pts[k], nd, L * 0.55, radii[k] * 0.8, depth + 1)

    branch(Vector((0, 0, -0.5)), Vector((0, 0, 1)), height * 0.75, 0.35, 0)
    col = [cyl_col((0, 0, 0), 0.38, height * 0.5)]
    return mb, col


def bush(seed, size, leaves="M_LeavesBush", flowers=None):
    mb = MeshBuilder("bush")
    rnd = random.Random(seed)
    n = rnd.randint(3, 5)
    for k in range(n):
        a = TAU * k / n + rnd.uniform(-0.3, 0.3)
        r = size * rnd.uniform(0.35, 0.5)
        off = size * 0.28
        blob(mb, (math.cos(a) * off, math.sin(a) * off, r * 0.7), r, leaves, seed * 3 + k, seg=9, rings=6,
             scale=(1, 1, 0.85), rough=0.3, flat_bottom=0.3)
    blob(mb, (0, 0, size * 0.55), size * 0.42, leaves, seed * 5, seg=9, rings=6, rough=0.3)
    if flowers:
        for k in range(14):
            a = rnd.uniform(0, TAU)
            el = rnd.uniform(0.1, 1.2)
            rr = size * 0.55
            p = (math.cos(a) * rr * math.cos(el), math.sin(a) * rr * math.cos(el), size * 0.45 + math.sin(el) * rr * 0.8)
            mb.sphere(p, size * 0.07, flowers, seg=6, rings=4)
    return mb, []


def fern(seed):
    mb = MeshBuilder("fern")
    rnd = random.Random(seed)
    for k in range(9):
        a = TAU * k / 9 + rnd.uniform(-0.2, 0.2)
        d = Vector((math.cos(a), math.sin(a), 0))
        L = rnd.uniform(0.7, 1.0)
        spine = bezier((0, 0, 0.05), tuple(d * L * 0.4 + Vector((0, 0, 0.6))), tuple(d * L + Vector((0, 0, 0.15))), 5)
        side = Vector((-d.y, d.x, 0))
        for i in range(5):
            w0 = 0.14 * math.sin(math.pi * (i / 5 * 0.9 + 0.1))
            w1 = 0.14 * math.sin(math.pi * ((i + 1) / 5 * 0.9 + 0.1))
            mb.quad(tuple(spine[i] - side * w0), tuple(spine[i] + side * w0),
                    tuple(spine[i + 1] + side * w1), tuple(spine[i + 1] - side * w1), "M_LeavesBroad", smooth=True)
    return mb, []


def grass_clump(seed):
    mb = MeshBuilder("grass")
    rnd = random.Random(seed)
    for k in range(14):
        a = rnd.uniform(0, TAU)
        r = rnd.uniform(0.0, 0.25)
        base = Vector((math.cos(a) * r, math.sin(a) * r, 0))
        lean = Vector((math.cos(a) * 0.25, math.sin(a) * 0.25, 0))
        h = rnd.uniform(0.4, 0.75)
        w = 0.05
        side = Vector((-math.sin(a), math.cos(a), 0)) * w
        tip = base + lean + Vector((0, 0, h))
        mb.poly([tuple(base - side), tuple(base + side), tuple(tip)], "M_Grass", smooth=True)
    return mb, []


def rock(seed, size, mat="M_Rock", squash=(1.0, 0.85, 0.7), rough=0.35, seg=11, rings=8):
    mb = MeshBuilder("rock")
    blob(mb, (0, 0, size * squash[2] * 0.35), size * 0.5, mat, seed, seg=seg, rings=rings, scale=squash, rough=rough,
         flat_bottom=0.15)
    col = MeshBuilder("col")
    blob(col, (0, 0, size * squash[2] * 0.35), size * 0.48, "M_Black", seed, seg=7, rings=5, scale=squash, rough=0.0)
    return mb, [col]


def rock_cluster(seed, size, mat="M_Rock"):
    mb = MeshBuilder("rocks")
    rnd = random.Random(seed)
    cols = []
    for k in range(4):
        a = TAU * k / 4 + rnd.uniform(-0.4, 0.4)
        r = size * rnd.uniform(0.25, 0.4)
        off = Vector((math.cos(a), math.sin(a), 0)) * size * 0.25
        blob(mb, (off.x, off.y, r * 0.4), r, mat, seed + k, seg=10, rings=7, scale=(1, 0.9, 0.75), rough=0.35, flat_bottom=0.2)
        c = MeshBuilder("col")
        blob(c, (off.x, off.y, r * 0.4), r * 0.95, "M_Black", seed + k, seg=7, rings=5, scale=(1, 0.9, 0.75), rough=0.0)
        cols.append(c)
    return mb, cols


# --------------------------------------------------------------------------- street furniture
def lamp_post(old=False):
    mb = MeshBuilder("lamp")
    metal = "M_RustMetal" if old else "M_DarkMetal"
    mb.cylinder((0, 0, -0.3), 0.22, 0.6, metal, seg=10)
    mb.cylinder((0, 0, 0.3), 0.14, 0.25, metal, seg=10)
    mb.cylinder((0, 0, 0.5), 0.07, 3.4, metal, seg=8, radius_top=0.055)
    mb.torus((0, 0, 1.2), 0.08, 0.025, metal, seg=10, tube_seg=5)
    if old:
        with mb.at((0, 0, 3.9), rot_y=12):
            mb.cylinder((0, 0, 0), 0.06, 0.25, metal, seg=8)
            mb.cylinder((0, 0, 0.25), 0.24, 0.05, metal, seg=8)
            mb.cylinder((0, 0, 0.3), 0.2, 0.35, "M_Glass", seg=8, radius_top=0.24)
            mb.cone((0, 0, 0.65), 0.3, 0.3, metal, seg=8)
    else:
        mb.cylinder((0, 0, 3.9), 0.24, 0.06, metal, seg=8)
        mb.cylinder((0, 0, 3.96), 0.18, 0.5, "M_LampGlow", seg=8, radius_top=0.24)
        for k in range(4):
            a = TAU * k / 4 + math.pi / 4
            mb.box((math.cos(a) * 0.2, math.sin(a) * 0.2, 4.21), (0.03, 0.03, 0.52), metal)
        mb.cone((0, 0, 4.46), 0.34, 0.3, metal, seg=8)
        mb.sphere((0, 0, 4.82), 0.06, "M_Gold", seg=6, rings=4)
    return mb, [cyl_col((0, 0, 0), 0.2, 4.4)]


def bench():
    mb = MeshBuilder("bench")
    for x in (-0.85, 0.85):
        mb.box((x, 0, 0.22), (0.08, 0.5, 0.44), "M_DarkMetal")
        mb.box((x, 0.2, 0.62), (0.08, 0.06, 0.5), "M_DarkMetal")
    for k in range(4):
        mb.box((0, -0.18 + k * 0.12, 0.46), (2.0, 0.1, 0.04), "M_Wood")
    for k in range(3):
        mb.box((0, 0.23, 0.6 + k * 0.13), (2.0, 0.03, 0.1), "M_Wood")
    return mb, [box_col((-1.0, -0.25, 0), (1.0, 0.28, 0.9))]


def signpost():
    mb = MeshBuilder("signpost")
    mb.box((0, 0, 1.3), (0.14, 0.14, 2.9), "M_DarkWood")
    rnd = random.Random(5)
    for k, (z, a) in enumerate([(2.45, 15), (2.05, -25), (1.65, 160)]):
        with mb.at((0, 0, z), rot=a):
            mb.box((0.6, 0, 0), (1.15, 0.05, 0.28), "M_Wood")
            mb.poly([(1.18, -0.03, -0.14), (1.18, -0.03, 0.14), (1.35, -0.03, 0.0)], "M_Wood")
            mb.poly([(1.18, 0.03, 0.14), (1.18, 0.03, -0.14), (1.35, 0.03, 0.0)], "M_Wood")
    mb.pyramid((0, 0, 2.75), 0.2, 0.2, 0.15, "M_DarkWood")
    return mb, [box_col((-0.1, -0.1, 0), (0.1, 0.1, 2.8))]


def trash_bin():
    mb = MeshBuilder("bin")
    mb.cylinder((0, 0, 0), 0.3, 0.9, "M_DarkMetal", seg=12)
    mb.cylinder((0, 0, 0.9), 0.33, 0.08, "M_Metal", seg=12)
    return mb, [cyl_col((0, 0, 0), 0.32, 1.0)]


def fence_wood():
    mb = MeshBuilder("fence")
    for x in (-1.95, 0.0, 1.95):
        mb.box((x, 0, 0.5), (0.12, 0.12, 1.3), "M_Wood")
        mb.pyramid((x, 0, 1.15), 0.12, 0.12, 0.08, "M_Wood")
    for z in (0.45, 0.9):
        mb.box((0, 0.07, z), (4.0, 0.04, 0.14), "M_Wood")
    return mb, [box_col((-2.0, -0.1, 0), (2.0, 0.12, 1.15))]


def fence_iron():
    mb = MeshBuilder("fence_iron")
    mb.box((-1.95, 0, 0.9), (0.14, 0.14, 2.2), "M_RustMetal")
    mb.box((1.95, 0, 0.9), (0.14, 0.14, 2.2), "M_RustMetal")
    for z in (0.25, 1.75):
        mb.box((0, 0, z), (3.9, 0.05, 0.06), "M_RustMetal")
    for k in range(14):
        x = -1.75 + k * 0.27
        mb.box((x, 0, 1.0), (0.03, 0.03, 1.9), "M_RustMetal")
        mb.cone((x, 0, 1.95), 0.04, 0.14, "M_RustMetal", seg=4)
    return mb, [box_col((-2.0, -0.08, 0), (2.0, 0.08, 2.0))]


def bollard():
    mb = MeshBuilder("bollard")
    mb.lathe([(0.25, 0.0), (0.2, 0.08), (0.17, 0.5), (0.24, 0.6), (0.24, 0.66), (0.0, 0.7)], "M_DarkMetal", seg=12)
    return mb, [cyl_col((0, 0, 0), 0.25, 0.7)]


def crate():
    mb = MeshBuilder("crate")
    mb.box((0, 0, 0.6), (1.2, 1.2, 1.2), "M_Wood")
    for s in (-1, 1):
        for axis in ("x", "y"):
            if axis == "x":
                mb.box((0, s * 0.61, 0.6), (1.24, 0.03, 0.12), "M_DarkWood")
                mb.box((0, s * 0.61, 0.6), (0.12, 0.03, 1.24), "M_DarkWood")
            else:
                mb.box((s * 0.61, 0, 0.6), (0.03, 1.24, 0.12), "M_DarkWood")
                mb.box((s * 0.61, 0, 0.6), (0.03, 0.12, 1.24), "M_DarkWood")
    return mb, [box_col((-0.6, -0.6, 0), (0.6, 0.6, 1.2))]


def driftwood():
    mb = MeshBuilder("driftwood")
    mb.beam((-2.2, 0, 0.22), (2.2, 0.15, 0.3), 0.42, 0.4, "M_Bark")
    mb.beam((0.8, 0.05, 0.3), (1.6, 0.7, 0.45), 0.16, 0.14, "M_Bark")
    return mb, [box_col((-2.3, -0.25, 0.0), (2.3, 0.4, 0.5))]


def stump():
    mb = MeshBuilder("stump")
    mb.lathe([(0.55, 0.0), (0.42, 0.12), (0.38, 0.7), (0.36, 0.85)], "M_Bark", seg=12)
    return mb, [cyl_col((0, 0, 0), 0.45, 0.85)]


def pebbles():
    mb = MeshBuilder("pebbles")
    rnd = random.Random(7)
    for k in range(7):
        a, r = rnd.uniform(0, TAU), rnd.uniform(0.0, 0.7)
        s = rnd.uniform(0.12, 0.3)
        blob(mb, (math.cos(a) * r, math.sin(a) * r, s * 0.25), s, "M_Rock", 40 + k, seg=8, rings=5,
             scale=(1, 0.8, 0.55), rough=0.3, flat_bottom=0.2)
    return mb, []


def barrel():
    mb = MeshBuilder("barrel")
    mb.lathe([(0.29, 0.0), (0.31, 0.45), (0.29, 0.9)], "M_CrateBlue", seg=14)
    for z in (0.15, 0.75):
        mb.torus((0, 0, z), 0.305, 0.02, "M_DarkMetal", seg=14, tube_seg=4)
    return mb, [cyl_col((0, 0, 0), 0.31, 0.9)]


def container(mat):
    mb = MeshBuilder("container")
    mb.box((0, 0, 1.3), (6.0, 2.4, 2.6), mat)
    for k in range(12):
        x = -2.75 + k * 0.5
        for s in (-1, 1):
            mb.box((x, s * 1.22, 1.3), (0.12, 0.05, 2.4), mat)
    mb.box((3.02, 0, 1.3), (0.06, 2.3, 2.5), "M_DarkMetal")
    for s in (-0.5, 0.5):
        mb.box((3.06, s, 1.3), (0.04, 0.05, 2.3), "M_Metal")
    return mb, [box_col((-3, -1.2, 0), (3, 1.2, 2.6))]


def rowboat():
    mb = MeshBuilder("rowboat")
    # hull: lofted sections along X
    secs = []
    n = 8
    for i in range(n + 1):
        t = i / n
        x = -2.0 + 4.0 * t
        w = 0.75 * math.sin(math.pi * (0.08 + 0.84 * t)) ** 0.7
        d = 0.45 * (0.6 + 0.4 * math.sin(math.pi * t))
        secs.append([(x, -w, 0.35), (x, -w * 0.8, -d * 0.6), (x, 0, -d), (x, w * 0.8, -d * 0.6), (x, w, 0.35)])
    # outer skin
    for i in range(n):
        for k in range(4):
            a, b = secs[i][k], secs[i][k + 1]
            c, d = secs[i + 1][k + 1], secs[i + 1][k]
            mb.quad(a, b, c, d, "M_Wood", smooth=True)
            # inner skin (slightly inset upward)
            ai = (a[0], a[1] * 0.92, a[2] + 0.05)
            bi = (b[0], b[1] * 0.92, b[2] + 0.05)
            ci = (c[0], c[1] * 0.92, c[2] + 0.05)
            di = (d[0], d[1] * 0.92, d[2] + 0.05)
            mb.quad(ai, di, ci, bi, "M_ShipHull", smooth=True)
    for x in (-0.6, 0.5):
        mb.box((x, 0, 0.12), (0.25, 1.3, 0.05), "M_Wood")
    mb.box((0.0, 0, 0.36), (4.0, 0.06, 0.04), "M_DarkWood")
    return mb, [box_col((-2.0, -0.75, -0.4), (2.0, 0.75, 0.4))]


def buoy():
    mb = MeshBuilder("buoy")
    mb.lathe([(0.5, -0.4), (0.6, 0.0), (0.5, 0.35), (0.0, 0.4)], "M_LighthouseRed", seg=12)
    mb.cylinder((0, 0, 0.35), 0.08, 0.8, "M_LighthouseWhite", seg=8)
    mb.sphere((0, 0, 1.2), 0.12, "M_LampGlow", seg=8, rings=6)
    return mb, [cyl_col((0, 0, -0.4), 0.6, 1.2)]


def beach_umbrella():
    mb = MeshBuilder("umbrella")
    mb.cylinder((0, 0, -0.3), 0.04, 2.9, "M_Metal", seg=6)
    rows = []
    for k in range(8):
        a0 = TAU * k / 8
        a1 = TAU * (k + 1) / 8
        mat = "M_Umbrella" if k % 2 == 0 else "M_WhiteWall"
        mb.poly([(0, 0, 2.65), (math.cos(a0) * 1.4, math.sin(a0) * 1.4, 2.2), (math.cos(a1) * 1.4, math.sin(a1) * 1.4, 2.2)], mat)
        mb.poly([(0, 0, 2.62), (math.cos(a1) * 1.4, math.sin(a1) * 1.4, 2.18), (math.cos(a0) * 1.4, math.sin(a0) * 1.4, 2.18)], mat)
    return mb, [cyl_col((0, 0, 0), 0.1, 2.5)]


def beach_chair():
    mb = MeshBuilder("chair")
    mb.ramp((0, -0.6, 0.3), (0, 0.3, 0.3), 0.6, "M_Umbrella", thick=0.04)
    mb.ramp((0, 0.3, 0.3), (0, 0.7, 0.95), 0.6, "M_Umbrella", thick=0.04)
    for x in (-0.3, 0.3):
        mb.box((x, -0.55, 0.15), (0.04, 0.04, 0.3), "M_Wood")
        mb.box((x, 0.3, 0.15), (0.04, 0.04, 0.3), "M_Wood")
    return mb, [box_col((-0.32, -0.62, 0), (0.32, 0.72, 0.9))]


def flagpole(mat):
    mb = MeshBuilder("flag")
    mb.cylinder((0, 0, -0.3), 0.3, 0.5, "M_Concrete", seg=8)
    mb.cylinder((0, 0, 0.2), 0.08, 9.8, "M_Metal", seg=8, radius_top=0.05)
    mb.sphere((0, 0, 10.05), 0.12, "M_Gold", seg=8, rings=6)
    # waving flag (zig-zag strip), two-sided via foliage material
    pts = []
    for i in range(7):
        t = i / 6
        pts.append((0.06 + t * 3.0, math.sin(t * 5.0) * 0.18 * t, 0.0))
    for i in range(6):
        a, b = pts[i], pts[i + 1]
        mb.quad((a[0], a[1], 8.2), (b[0], b[1], 8.2), (b[0], b[1], 9.9), (a[0], a[1], 9.9), mat, smooth=True)
    return mb, [cyl_col((0, 0, 0), 0.3, 9.5)]


def vending():
    mb = MeshBuilder("vending")
    mb.box((0, 0, 0.95), (1.0, 0.8, 1.9), "M_Vending")
    mb.box((-0.12, -0.41, 1.25), (0.65, 0.04, 0.85), "M_Screen")
    for r in range(3):
        for c in range(4):
            mb.box((-0.36 + c * 0.16, -0.44, 0.95 + r * 0.28), (0.1, 0.03, 0.18), "M_CardPack")
    mb.box((0.32, -0.42, 1.2), (0.18, 0.04, 0.5), "M_Metal")
    mb.box((-0.1, -0.42, 0.35), (0.6, 0.06, 0.2), "M_Black")
    return mb, [box_col((-0.5, -0.4, 0), (0.5, 0.4, 1.9))]


def stone_lantern():
    mb = MeshBuilder("lantern")
    mb.lathe([(0.35, 0.0), (0.3, 0.15), (0.12, 0.2), (0.1, 0.75), (0.3, 0.8), (0.3, 0.9)], "M_OnsenRock", seg=6)
    mb.box((0, 0, 1.08), (0.42, 0.42, 0.36), "M_OnsenRock")
    mb.box((0, -0.215, 1.08), (0.2, 0.02, 0.2), "M_LampGlow")
    mb.box((0, 0.215, 1.08), (0.2, 0.02, 0.2), "M_LampGlow")
    mb.pyramid((0, 0, 1.26), 0.8, 0.8, 0.3, "M_OnsenRock")
    mb.sphere((0, 0, 1.6), 0.08, "M_OnsenRock", seg=6, rings=4)
    return mb, [box_col((-0.35, -0.35, 0), (0.35, 0.35, 1.6))]


def picnic_table():
    mb = MeshBuilder("picnic")
    mb.box((0, 0, 0.75), (1.8, 0.8, 0.06), "M_Wood")
    for y in (-0.65, 0.65):
        mb.box((0, y, 0.45), (1.8, 0.3, 0.05), "M_Wood")
    for x in (-0.7, 0.7):
        mb.box((x, 0, 0.37), (0.08, 1.5, 0.06), "M_DarkWood")
        mb.box((x, 0, 0.4), (0.08, 0.08, 0.75), "M_DarkWood")
    return mb, [box_col((-0.9, -0.8, 0), (0.9, 0.8, 0.8))]


def planter():
    mb = MeshBuilder("planter")
    mb.box((0, 0, 0.35), (1.5, 1.5, 0.7), "M_Paving")
    mb.box((0, 0, 0.71), (1.35, 1.35, 0.02), "M_Soil")
    b, _ = bush(77, 1.1, "M_LeavesBush", "M_FlowerRed")
    mb.extend(b, (0, 0, 0.7))
    return mb, [box_col((-0.75, -0.75, 0), (0.75, 0.75, 0.8))]


def duel_dummy():
    mb = MeshBuilder("dummy")
    mb.cylinder((0, 0, 0), 0.3, 0.15, "M_Concrete", seg=10)
    mb.cylinder((0, 0, 0.15), 0.06, 1.1, "M_Metal", seg=8)
    with mb.at((0, 0, 1.25), rot_x=-25):
        mb.cylinder((0, 0, -0.04), 0.22, 0.08, "M_DuelDisk", seg=14)
        mb.box((0.38, 0, 0), (0.55, 0.35, 0.05), "M_DuelDisk")
        for k in range(5):
            mb.box((0.18 + k * 0.1, 0, 0.035), (0.08, 0.12, 0.01), "M_DuelFieldGlow")
    return mb, [cyl_col((0, 0, 0), 0.3, 1.4)]


# --------------------------------------------------------------------------- registry
def _registry():
    R = {
        "SM_PalmTree_A": lambda: palm(11, 11.0, 2.2),
        "SM_PalmTree_B": lambda: palm(23, 8.0, 0.8),
        "SM_BroadTree_A": lambda: broadleaf(3, 12.0, 4.2, 1),
        "SM_BroadTree_B": lambda: broadleaf(7, 16.0, 4.6, 2, "M_LeavesDark"),
        "SM_BroadTree_C": lambda: broadleaf(19, 6.0, 2.3, 1),
        "SM_PineTree_A": lambda: pine(5, 14.0),
        "SM_DeadTree_A": lambda: dead_tree(9, 9.0),
        "SM_Bush_A": lambda: bush(1, 1.6),
        "SM_Bush_B": lambda: bush(2, 1.0, "M_LeavesDark"),
        "SM_FlowerBush_Red": lambda: bush(3, 1.2, "M_LeavesBush", "M_FlowerRed"),
        "SM_FlowerBush_Yellow": lambda: bush(4, 1.2, "M_LeavesBush", "M_FlowerYellow"),
        "SM_FlowerBush_Blue": lambda: bush(5, 1.2, "M_LeavesBush", "M_FlowerBlue"),
        "SM_FlowerBush_White": lambda: bush(6, 1.2, "M_LeavesBush", "M_FlowerWhite"),
        "SM_Fern_A": lambda: fern(3),
        "SM_GrassClump_A": lambda: grass_clump(4),
        "SM_Rock_A": lambda: rock(1, 2.0),
        "SM_Rock_B": lambda: rock(2, 3.0, squash=(1.2, 1.0, 0.35)),
        "SM_Rock_C": lambda: rock(3, 4.0, squash=(0.7, 0.6, 1.3)),
        "SM_Rock_D": lambda: rock_cluster(4, 5.0),
        "SM_CliffRock_A": lambda: rock(5, 14.0, squash=(1.0, 0.8, 0.9), rough=0.45, seg=14, rings=10),
        "SM_VolcanicRock_A": lambda: rock(6, 4.0, "M_VolcanicRock", squash=(0.9, 0.8, 0.9), rough=0.6),
        "SM_LampPost": lambda: lamp_post(False),
        "SM_LampPost_Old": lambda: lamp_post(True),
        "SM_Bench": bench,
        "SM_Signpost": signpost,
        "SM_TrashBin": trash_bin,
        "SM_Fence_Wood": fence_wood,
        "SM_Fence_Iron": fence_iron,
        "SM_Bollard": bollard,
        "SM_Crate": crate,
        "SM_Barrel": barrel,
        "SM_Container_Red": lambda: container("M_CrateRed"),
        "SM_Container_Blue": lambda: container("M_CrateBlue"),
        "SM_Container_Yellow": lambda: container("M_CrateYellow"),
        "SM_Rowboat": rowboat,
        "SM_Buoy": buoy,
        "SM_BeachUmbrella": beach_umbrella,
        "SM_BeachChair": beach_chair,
        "SM_Flagpole_Red": lambda: flagpole("M_FlagRed"),
        "SM_Flagpole_Yellow": lambda: flagpole("M_FlagYellow"),
        "SM_Flagpole_Blue": lambda: flagpole("M_FlagBlue"),
        "SM_VendingMachine": vending,
        "SM_StoneLantern": stone_lantern,
        "SM_PicnicTable": picnic_table,
        "SM_Planter": planter,
        "SM_DuelDummy": duel_dummy,
        "SM_Driftwood_A": driftwood,
        "SM_Stump_A": stump,
        "SM_Pebbles_A": pebbles,
    }
    missing = set(CATALOG) - set(R)
    assert not missing, f"catalog entries without geometry: {missing}"
    return R


REGISTRY = _registry()

# Props that carry an automatic light in UE (offset from origin, colour, intensity, radius)
PROP_LIGHTS = {
    "SM_LampPost": dict(offset=(0, 0, 4.2), color=(1.0, 0.82, 0.55), intensity=4000.0, radius=18.0, night_only=True),
    "SM_StoneLantern": dict(offset=(0, 0, 1.08), color=(1.0, 0.7, 0.4), intensity=600.0, radius=6.0, night_only=True),
    "SM_Buoy": dict(offset=(0, 0, 1.2), color=(1.0, 0.3, 0.2), intensity=300.0, radius=8.0, night_only=True),
}

# Props that bob on water in UE
FLOATING_PROPS = {"SM_Rowboat", "SM_Buoy"}

_cache = {}


def get(name):
    if name not in _cache:
        _cache[name] = REGISTRY[name]()
    return _cache[name]


def is_thirdparty(name):
    from .. import thirdparty
    return thirdparty.has_prop(name)


def build_object(name, obj_name=None, collection=None):
    """bpy object for a catalog entry: the curated third-party asset when one is registered
    (Tools/thirdparty/registry.json), otherwise the procedural fallback."""
    if is_thirdparty(name):
        from .. import thirdparty
        o = thirdparty.build_prop(name)
        if obj_name:
            o.name = obj_name
        if collection is not None and collection not in o.users_collection:
            for c in list(o.users_collection):
                c.objects.unlink(o)
            collection.objects.link(o)
        return o
    mb, _ = get(name)
    return mb.build(obj_name or name, collection=collection)


def collision_objects(name, obj):
    if is_thirdparty(name):
        from .. import thirdparty
        return thirdparty.collision_meshes(obj, thirdparty.registry()["props"][name])
    _, cols = get(name)
    return [c.build("col") for c in cols]


def export_all(out_dir, log=print):
    """Export every prop as SM_<name>.fbx with UCX collision hulls."""
    os.makedirs(out_dir, exist_ok=True)
    n_tp = 0
    for name in REGISTRY:
        obj = build_object(name, name)
        objs = [obj]
        for i, co in enumerate(collision_objects(name, obj)):
            co.name = f"UCX_{name}_{i:02d}"
            co.data.materials.clear()
            objs.append(co)
        blend.export_fbx(objs, os.path.join(out_dir, name + ".fbx"))
        blend.delete(objs)
        n_tp += is_thirdparty(name)
    log(f"  props: {len(REGISTRY)} meshes exported ({n_tp} from curated third-party packs)")


def instance_props_for_preview(aset):
    """Create linked-duplicate preview objects for every prop socket of an AssetSet."""
    import bpy
    objs = []
    proto = {}
    for s in aset.sockets:
        if s["type"] != "prop":
            continue
        name = s["props"]["asset"]
        if name not in REGISTRY:
            print("   !! unknown prop", name)
            continue
        if name not in proto:
            proto[name] = build_object(name, name + "_proto")
            proto[name].hide_render = True
        o = bpy.data.objects.new(name, proto[name].data)
        bpy.context.scene.collection.objects.link(o)
        o.location = s["pos"]
        o.rotation_euler = (0, 0, math.radians(s["yaw"]))
        sc = s["props"].get("scale", 1.0)
        o.scale = (sc, sc, sc)
        objs.append(o)
    return objs


def build_catalog_preview():
    """AssetSet laying out the whole catalog in a grid (for preview_asset.py props)."""
    from . import AssetSet
    a = AssetSet("catalog")
    names = list(REGISTRY)
    cols = 8
    for i, n in enumerate(names):
        a.prop(n, ((i % cols) * 9.0 - 32.0, (i // cols) * 9.0 - 20.0, 0.0), 0.0)
    # anchor mesh so preview has bounds
    a.mesh("Catalog_Ground").box((0, 0, -0.05), (80, 60, 0.1), "M_Paving")
    return a
