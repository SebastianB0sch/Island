"""
Hot Springs - a small Japanese onsen on the volcano foothills.

A raised stone-paved terrace (deck at DECK = +1.2 m so the 1 m deep basins stay
above the flattened terrain) holding three irregular rock-rimmed pools, a wooden
bathhouse with shoji walls, red/blue noren and a dark tiled hip roof with
upturned eaves, a bamboo water spout, bamboo fence screens, a rest pavilion and
a red tea umbrella looking out over the sea (local +X / +Y). A small wooden
torii-like gate with a "HOT SPRINGS" plaque marks the entrance at ground level.

Local space: origin = pad centre at ground level, front faces -Y; the trail
arrives at about (0, -45).
"""

import math
import random

from . import AssetSet
from .. import palette

palette.register({
    "M_OnsenRoof":      dict(kind="opaque", color=(0.20, 0.21, 0.25), rough=0.7, detail="RoofTiles", tiling=0.5),
    "M_OnsenPaving":    dict(kind="opaque", color=(0.53, 0.52, 0.49), rough=0.9, detail="Paving", tiling=0.5),
    "M_OnsenPaving2":   dict(kind="opaque", color=(0.44, 0.43, 0.42), rough=0.9, detail="Paving", tiling=0.5),
    "M_OnsenStoneEdge": dict(kind="opaque", color=(0.50, 0.48, 0.45), rough=0.9, detail="Concrete", tiling=0.5),
    "M_NorenBlue":      dict(kind="foliage", color=(0.10, 0.20, 0.52), rough=0.95, detail=None),
    "M_NorenRed":       dict(kind="foliage", color=(0.74, 0.12, 0.12), rough=0.95, detail=None),
    "M_Bamboo":         dict(kind="opaque", color=(0.66, 0.62, 0.34), rough=0.55, detail=None),
    "M_RedFelt":        dict(kind="opaque", color=(0.72, 0.10, 0.10), rough=1.0, detail="Fabric", tiling=1.0),
})

DECK = 1.2                      # terrace top (finished deck level)
WATER = DECK - 0.2
FLOOR = DECK - 1.0
ROCK = "M_OnsenRock"
EDGE = "M_OnsenStoneEdge"
PAVE = "M_OnsenPaving"
WOOD = "M_Wood"
DARK = "M_DarkWood"
RTILE = "M_OnsenRoof"
TAU = math.tau

# terrace outline (rounded rectangle, CCW)
TX0, TX1, TY0, TY1, TCR = -21.0, 24.0, -16.0, 21.0, 4.0
# pools: centre, radii, phases, entry angle (deg)
POOLS = [
    dict(c=(8.0, 6.0), r=(6.5, 4.8), ph=(0.4, 2.1), entry=205.0),
    dict(c=(17.5, -7.5), r=(3.8, 3.0), ph=(1.3, 0.2), entry=180.0),
    dict(c=(-8.0, 13.0), r=(3.4, 2.8), ph=(2.4, 1.0), entry=268.0),
]
# bathhouse walls
BX0, BX1, BY0, BY1 = -15.8, -3.0, -13.0, -5.0
BFL = DECK + 0.45               # bathhouse floor
BTOP = BFL + 3.25               # wall top
NAGESHI = BFL + 2.65


# ---------------------------------------------------------------- helpers
def rbox(mb, center, size, mat, yaw=0.0, pitch=0.0, roll=0.0, mats=None):
    with mb.at(center, rot=yaw, rot_y=pitch, rot_x=roll):
        mb.box((0, 0, 0), size, mat, mats=mats)


def rounded_rect(x0, x1, y0, y1, r, n=5, off=0.0):
    pts = []
    for (cx, cy, a0) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + math.cos(a) * (r + off), cy + math.sin(a) * (r + off)))
    return pts


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def pool_radius(p, th):
    rx, ry = p["r"]
    base = rx * ry / math.sqrt((ry * math.cos(th)) ** 2 + (rx * math.sin(th)) ** 2)
    return base * (1.0 + 0.10 * math.sin(3 * th + p["ph"][0]) + 0.06 * math.sin(5 * th + p["ph"][1]))


def pool_outline(p, n=36, grow=0.0):
    cx, cy = p["c"]
    out = []
    for i in range(n):
        th = TAU * i / n
        r = pool_radius(p, th) + grow
        out.append((cx + math.cos(th) * r, cy + math.sin(th) * r))
    return out


def in_pool(x, y, grow=0.0):
    for p in POOLS:
        cx, cy = p["c"]
        dx, dy = x - cx, y - cy
        if math.hypot(dx, dy) < pool_radius(p, math.atan2(dy, dx)) + grow:
            return True
    return False


def rock(mb, center, size, rng, mat=ROCK, seg=7):
    """Faceted low-poly rock. size = (radius x, radius y, half height)."""
    cx, cy, cz = center
    sx, sy, sz = size
    prof = ((0.78, -1.0), (1.0, -0.25), (0.9, 0.45), (0.55, 0.92))
    jit = [rng.uniform(0.82, 1.12) for _ in range(seg)]
    a0 = rng.uniform(0, TAU)
    rows = []
    for (rf, zf) in prof:
        row = []
        for i in range(seg):
            a = a0 + TAU * i / seg + rng.uniform(-0.1, 0.1)
            r = rf * jit[i] * rng.uniform(0.94, 1.06)
            row.append((cx + math.cos(a) * r * sx, cy + math.sin(a) * r * sy, cz + zf * sz + rng.uniform(-0.05, 0.05) * sz))
        rows.append(row)
    mb.grid_faces(rows, mat, smooth=False, closed_u=True)
    top = rows[-1]
    c = (sum(p[0] for p in top) / seg, sum(p[1] for p in top) / seg, sum(p[2] for p in top) / seg + 0.06 * sz)
    for i in range(seg):
        mb.poly([c, top[i], top[(i + 1) % seg]], mat)
    mb.poly(list(reversed(rows[0])), mat)


def bucket(mb, pos, r=0.17, h=0.24):
    x, y, z = pos
    mb.cylinder((x, y, z), r, h, WOOD, seg=10, radius_top=r * 1.1)
    mb.cylinder((x, y, z + 0.04), r * 1.02, 0.03, "M_DarkMetal", seg=10, cap_top=False, cap_bottom=False)
    mb.cylinder((x, y, z + h - 0.07), r * 1.09, 0.03, "M_DarkMetal", seg=10, cap_top=False, cap_bottom=False)


def stool(mb, pos, yaw=0.0):
    with mb.at(pos, rot=yaw):
        mb.box((0, 0, 0.3), (0.38, 0.3, 0.05), WOOD)
        for s in (-1, 1):
            mb.box((s * 0.16, 0, 0.14), (0.05, 0.28, 0.28), WOOD)


def jp_roof(mb, c, hw, hd, ze, rise, wall_hw, wall_hd, wall_top, m=12, rings=6, lift=0.45, ribs=True, ridge=True):
    """Hipped Japanese roof: concave slopes, upturned flared corners, fascia, soffit, ribs, ridge."""
    cx, cy = c
    rh = max(hw - hd, 0.0) + 0.06

    def ring(ax, ay, z, lift_amt, flare):
        pts = []
        corners = ((-ax, -ay), (ax, -ay), (ax, ay), (-ax, ay))
        for e in range(4):
            p0, p1 = corners[e], corners[(e + 1) % 4]
            for k in range(m):
                u = k / m
                w = (2 * u - 1) ** 4
                x = p0[0] + (p1[0] - p0[0]) * u
                y = p0[1] + (p1[1] - p0[1]) * u
                f = 1.0 + flare * w
                pts.append((cx + x * f, cy + y * f, z + lift_amt * w))
        return pts

    rows = []
    for j in range(rings + 1):
        t = j / rings
        ax = hw - t * (hw - rh)
        ay = hd - t * (hd - 0.06)
        rows.append(ring(ax, ay, ze + rise * t ** 1.5, lift * (1 - t) ** 2, 0.05 * (1 - t) ** 2))
    mb.grid_faces(rows, RTILE, smooth=False, closed_u=True)
    mb.poly(rows[-1], RTILE)
    low = [(p[0], p[1], p[2] - 0.24) for p in rows[0]]
    mb.grid_faces([low, rows[0]], DARK, smooth=False, closed_u=True)
    wall = ring(wall_hw, wall_hd, wall_top, 0.0, 0.0)
    mb.grid_faces([low, wall], DARK, smooth=False, closed_u=True, flip=True)
    n = len(rows[0])
    if ribs:
        for i in range(n):
            corner = i % m == 0
            for j in range(rings):
                a, b = rows[j][i], rows[j + 1][i]
                if corner:
                    mb.beam((a[0], a[1], a[2] + 0.1), (b[0], b[1], b[2] + 0.1), 0.26, 0.24, RTILE)
                elif j < rings - 1 or i % 2 == 0:
                    mb.beam((a[0], a[1], a[2] + 0.03), (b[0], b[1], b[2] + 0.03), 0.07, 0.07, RTILE)
    # rafter tails under the eaves
    for i in range(n):
        if i % m == 0:
            continue
        a, b = wall[i], low[i]
        mb.beam((a[0], a[1], a[2] - 0.1), (b[0] + (b[0] - a[0]) * -0.04, b[1] + (b[1] - a[1]) * -0.04, b[2] - 0.08),
                0.09, 0.11, DARK)
    zt = rows[-1][0][2]
    if not ridge:   # pyramid roof: finial instead of a ridge
        mb.cylinder((cx, cy, zt - 0.05), 0.22, 0.3, RTILE, seg=8)
        mb.sphere((cx, cy, zt + 0.45), 0.2, "M_Gold", seg=8, rings=6)
        mb.cone((cx, cy, zt + 0.6), 0.08, 0.35, "M_Gold", seg=6)
        return zt
    # ridge with end blocks
    mb.box((cx, cy, zt + 0.16), (2 * rh + 0.5, 0.34, 0.34), RTILE)
    mb.box((cx, cy, zt + 0.36), (2 * rh + 0.3, 0.2, 0.08), "M_WhiteWall")
    mb.box((cx, cy, zt + 0.46), (2 * rh + 0.5, 0.36, 0.14), RTILE)
    for s in (-1, 1):
        rbox(mb, (cx + s * (rh + 0.25), cy, zt + 0.5), (0.3, 0.5, 0.75), RTILE, pitch=-s * 12)
    return zt


def bamboo_fence(mb, pts, h, rng, mat=WOOD):
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        n = max(1, int(ln / 0.12))
        z0 = a[2] if len(a) > 2 else DECK
        for k in range(n):
            t = (k + 0.5) / n
            r = rng.uniform(0.045, 0.06)
            hh = h + rng.uniform(-0.08, 0.05)
            mb.cylinder((a[0] + dx * t, a[1] + dy * t, z0), r, hh, mat, seg=6, cap_bottom=False)
        nx, ny = -dy / ln * 0.07, dx / ln * 0.07
        for zz in (0.35, h * 0.5, h - 0.25):
            for s in (-1, 1):
                mb.beam((a[0] + nx * s, a[1] + ny * s, z0 + zz), (b[0] + nx * s, b[1] + ny * s, z0 + zz), 0.05, 0.06, DARK)
        npost = max(1, int(ln / 1.8))
        for k in range(npost + 1):
            t = k / npost
            mb.box((a[0] + dx * t, a[1] + dy * t, z0 + (h + 0.1) / 2), (0.14, 0.14, h + 0.1), DARK)
        mb.beam((a[0], a[1], z0 + h + 0.06), (b[0], b[1], z0 + h + 0.06), 0.16, 0.08, DARK)


# ---------------------------------------------------------------- terrace + pools
def _terrace(mb, nc, rng):
    outline = rounded_rect(TX0, TX1, TY0, TY1, TCR)
    outer = rounded_rect(TX0, TX1, TY0, TY1, TCR, off=0.45)
    inner = rounded_rect(TX0, TX1, TY0, TY1, TCR, off=-0.6)
    # retaining wall down to -4 and a dressed coping
    mb.prism(outer, -4.0, DECK - 0.3, ROCK, cap_top=False, cap_bottom=False)
    mb.slab_ring(outer, inner, DECK - 0.3, DECK + 0.1, EDGE)
    for i in range(len(outer)):
        a, b = outer[i], outer[(i + 1) % len(outer)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        with mb.at((a[0], a[1], 0), rot=math.degrees(math.atan2(dy, dx))):
            for ci, zc in enumerate((-1.25, -0.75, -0.25, 0.25, 0.68)):
                u = -rng.uniform(0.0, 0.6) if ci % 2 else 0.0
                while u < ln - 0.05:
                    sl = rng.uniform(0.7, 1.5)
                    u0, u1 = max(u, 0.0), min(u + sl, ln)
                    if u1 - u0 > 0.15:
                        hh = 0.44 if ci < 4 else 0.38
                        mb.box(((u0 + u1) / 2, -0.04 - rng.uniform(0, 0.04), zc), (u1 - u0 - 0.05, 0.12, hh), ROCK,
                               skip=("+y",))
                    u += sl
    # natural stone paving (running bond, random lengths), skipping pools and the bathhouse base
    y = TY0 + 0.1
    row = 0
    while y < TY1 - 0.1:
        d = rng.uniform(0.85, 1.15)
        x = TX0 + 0.4 - (0.5 if row % 2 else 0.0)
        while x < TX1 - 0.1:
            w = rng.uniform(0.8, 1.5)
            x0, x1, y0, y1 = max(x, TX0 + 0.1), min(x + w, TX1 - 0.1), y, min(y + d, TY1 - 0.1)
            x += w
            if x1 - x0 < 0.2:
                continue
            corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
            if not all(point_in_poly(px, py, outer) for px, py in corners):
                continue
            if any(in_pool(px, py, 0.12) for px, py in corners + (((x0 + x1) / 2, (y0 + y1) / 2),)):
                continue
            if x0 > BX0 - 0.6 and x1 < BX1 + 1.1 and y0 > BY0 - 1.3 and y1 < BY1:
                continue   # fully under the bathhouse base
            zt = DECK + rng.uniform(-0.008, 0.008)
            mat = PAVE if rng.random() < 0.7 else "M_OnsenPaving2"
            mb.box_mm((x0 + 0.025, y0 + 0.025, DECK - 0.3), (x1 - 0.025, y1 - 0.025, zt), mat, skip=("-z",))
        y += d
        row += 1

    # front stairs up to the terrace (risers 0.22 m, the coping is the top step)
    sx0, sx1 = -4.6, -1.4
    for k in range(5):
        top = 0.22 * (k + 1)
        y1 = TY0 - 0.45 - 0.32 * (4 - k)
        mb.box_mm((sx0, y1 - 0.34, -0.3), (sx1, y1, top), EDGE)
    for s, x in ((-1, sx0 - 0.5), (1, sx1 + 0.5)):
        rock(mb, (x, TY0 - 1.4, 0.4), (0.7, 1.2, 0.75), rng)
    # boulders along the base of the retaining wall
    for i in range(0, len(outer), 1):
        p = outer[i]
        q = outer[(i + 1) % len(outer)]
        for t in (0.0, 0.5):
            x, y2 = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
            if abs(x - (sx0 + sx1) / 2) < 3.2 and y2 < TY0:
                continue
            if rng.random() < 0.55:
                s = rng.uniform(0.5, 1.0)
                rock(mb, (x + rng.uniform(-0.3, 0.3), y2 + rng.uniform(-0.3, 0.3), 0.15), (s * 1.3, s, s * 0.7), rng)

    # pools
    for pi, p in enumerate(POOLS):
        cx, cy = p["c"]
        ol = pool_outline(p)
        n = len(ol)
        # inner walls (visible side faces into the pool) and floor
        for i in range(n):
            a, b = ol[i], ol[(i + 1) % n]
            mb.quad((a[0], a[1], DECK), (b[0], b[1], DECK), (b[0], b[1], FLOOR), (a[0], a[1], FLOOR), ROCK)
        for i in range(n):
            a, b = ol[i], ol[(i + 1) % n]
            mb.poly([(cx, cy, FLOOR - 0.05), (a[0], a[1], FLOOR), (b[0], b[1], FLOOR)], ROCK)
            nc.poly([(cx, cy, WATER), (a[0], a[1], WATER), (b[0], b[1], WATER)], "M_HotWater")
        # dark bedding ring under the paving around the rim
        ring_out = pool_outline(p, grow=1.4)
        mb.slab_ring(ring_out, ol, DECK - 0.32, DECK - 0.03, ROCK)
        # entry steps
        ea = math.radians(p["entry"])
        er = pool_radius(p, ea)
        ux, uy = math.cos(ea), math.sin(ea)
        for k in range(3):
            top = DECK - 0.25 * (k + 1)
            d0, d1 = er - 0.45 * k, er - 0.45 * (k + 1)
            c = (cx + ux * (d0 + d1) / 2, cy + uy * (d0 + d1) / 2)
            rbox(mb, (c[0], c[1], (FLOOR + top) / 2), (0.47, 1.5, top - FLOOR), EDGE, yaw=math.degrees(ea))
        # rim rocks (gap at the entry)
        perim = sum(math.hypot(ol[(i + 1) % n][0] - ol[i][0], ol[(i + 1) % n][1] - ol[i][1]) for i in range(n))
        count = int(perim / 0.85)
        for k in range(count):
            th = TAU * (k + rng.uniform(-0.2, 0.2)) / count
            dth = math.atan2(math.sin(th - ea), math.cos(th - ea))
            if abs(dth) * er < 1.0:
                continue
            r = pool_radius(p, th) + 0.22
            big = (math.sin(th) > 0.6 and pi == 0) or rng.random() < 0.1
            s = rng.uniform(0.42, 0.62)
            hz = rng.uniform(0.17, 0.26) if not big else rng.uniform(0.45, 0.75)
            with mb.at((cx + math.cos(th) * r, cy + math.sin(th) * r, DECK + 0.04 + (0.15 if big else 0.0)),
                       rot=math.degrees(th) + 90):
                rock(mb, (0, 0, 0), (s * 1.35, s, hz), rng)
        # submerged seat rocks
        for k in range(4):
            th = ea + math.pi + rng.uniform(-0.9, 0.9)
            r = pool_radius(p, th) - 0.6
            rock(mb, (cx + math.cos(th) * r, cy + math.sin(th) * r, FLOOR + 0.2), (0.55, 0.45, 0.3), rng)


def _waterfall(mb, nc, rng):
    """Rock pile behind the big pool with a bamboo spout pouring into it."""
    p = POOLS[0]
    cx, cy = p["c"]
    th = math.radians(78)
    r = pool_radius(p, th)
    bx, by = cx + math.cos(th) * (r + 1.2), cy + math.sin(th) * (r + 1.2)
    for (dx, dy, s, h) in ((0, 0.2, 1.3, 1.1), (-1.3, 0.5, 1.0, 0.8), (1.4, 0.3, 1.0, 0.7), (0.3, 1.2, 1.1, 1.4),
                           (-0.6, -0.5, 0.8, 0.55), (0.9, -0.6, 0.7, 0.45)):
        rock(mb, (bx + dx, by + dy, DECK + h * 0.6), (s, s * 0.85, h), rng)
    # bamboo pipe on two crossed supports, tip over the water
    tip = (bx + math.cos(th + math.pi) * 2.0, by + math.sin(th + math.pi) * 2.0, DECK + 1.45)
    base = (bx + 0.4 * math.cos(th), by + 0.4 * math.sin(th), DECK + 1.75)
    mb.beam(base, tip, 0.16, 0.16, "M_Bamboo")
    for t in (0.3, 0.65):
        q = (base[0] + (tip[0] - base[0]) * t, base[1] + (tip[1] - base[1]) * t, base[2] + (tip[2] - base[2]) * t)
        mb.beam((q[0] - 0.1, q[1] - 0.1, q[2] - 0.05), (q[0] + 0.1, q[1] + 0.1, q[2] + 0.05), 0.2, 0.2, "M_Bamboo")
    sup = (base[0] + (tip[0] - base[0]) * 0.55, base[1] + (tip[1] - base[1]) * 0.55)
    for s in (-1, 1):
        ox, oy = -math.sin(th) * 0.35 * s, math.cos(th) * 0.35 * s
        mb.beam((sup[0] + ox, sup[1] + oy, WATER - 0.2), (sup[0] - ox * 0.3, sup[1] - oy * 0.3, tip[2] + 0.35),
                0.08, 0.08, "M_Bamboo")
    # falling water ribbon (no collision)
    dx, dy = math.cos(th + math.pi), math.sin(th + math.pi)
    prev = None
    steps = 6
    for k in range(steps + 1):
        t = k / steps
        d = 0.05 + 0.35 * t
        z = tip[2] - 0.02 - (tip[2] - WATER) * t ** 1.6
        x, y = tip[0] + dx * d, tip[1] + dy * d
        ox, oy = -dy * 0.07, dx * 0.07
        cur = ((x - ox, y - oy, z), (x + ox, y + oy, z))
        if prev:
            nc.quad(prev[0], prev[1], cur[1], cur[0], "M_Waterfall")
            nc.quad(prev[1], prev[0], cur[0], cur[1], "M_Waterfall")
        prev = cur
    return tip


# ---------------------------------------------------------------- bathhouse
def _bathhouse(mb, nc, rng):
    # stone base + wooden floor / engawa
    px0, px1, py0, py1 = BX0 - 0.6, BX1 + 1.1, BY0 - 1.3, BY1
    mb.box_mm((px0, py0, DECK - 0.3), (px1, py1, DECK + 0.25), ROCK)
    mb.box_mm((px0, py0, DECK + 0.25), (px1, py1, BFL), DARK, mats={"+z": WOOD})
    for k in range(int((px1 - px0) / 0.3)):
        x = px0 + 0.15 + k * 0.3
        mb.box((x, (py0 + BY0) / 2, BFL + 0.003), (0.02, BY0 - py0 - 0.05, 0.006), DARK)
    # entrances (genkan alcoves) in bays 1 and 4 of the front
    nb = 6
    bw = (BX1 - BX0) / nb
    ent = (1, 4)
    gd = 1.6
    # interior core with alcoves cut out
    xs = [BX0]
    for b in ent:
        xs += [BX0 + b * bw + 0.11, BX0 + (b + 1) * bw - 0.11]
    xs.append(BX1)
    for i in range(len(xs) - 1):
        xa, xb = xs[i], xs[i + 1]
        if i % 2 == 1:   # alcove column
            mb.box_mm((xa, BY0 + gd, BFL), (xb, BY1, BTOP), "M_CreamWall")
            mb.box_mm((xa, BY0, NAGESHI), (xb, BY0 + gd, BTOP), "M_CreamWall", mats={"-z": DARK})
        else:
            mb.box_mm((xa, BY0, BFL), (xb, BY1, BTOP), "M_CreamWall")

    def shoji_bay(u0, u1, z0, frame_yaw_face=True):
        w = u1 - u0
        # lower boards
        mb.box(((u0 + u1) / 2, -0.04, z0 + 0.4), (w, 0.08, 0.8), WOOD, skip=("+y",))
        for k in range(1, 3):
            mb.box(((u0 + u1) / 2, -0.085, z0 + 0.27 * k), (w, 0.01, 0.025), DARK, skip=("+y",))
        # shoji panels with kumiko lattice
        za, zb = z0 + 0.8, z0 + 2.65
        mb.box(((u0 + u1) / 2, -0.03, (za + zb) / 2), (w, 0.06, zb - za), "M_ShojiPaper", skip=("+y",))
        nv = max(2, int(w / 0.32))
        for k in range(1, nv):
            mb.box((u0 + w * k / nv, -0.07, (za + zb) / 2), (0.025, 0.03, zb - za), DARK, skip=("+y",))
        for k in range(1, 6):
            mb.box(((u0 + u1) / 2, -0.07, za + (zb - za) * k / 6), (w, 0.03, 0.025), DARK, skip=("+y",))
        mb.box(((u0 + u1) / 2, -0.09, (za + zb) / 2), (0.07, 0.05, zb - za), DARK, skip=("+y",))
        mb.box(((u0 + u1) / 2, -0.08, za), (w, 0.06, 0.06), DARK, skip=("+y",))

    def face(origin, yaw, length, bays, entrances=()):
        bwl = length / bays
        with mb.at((origin[0], origin[1], 0), rot=yaw):
            for b in range(bays):
                u0, u1 = b * bwl + 0.11, (b + 1) * bwl - 0.11
                if b in entrances:
                    continue
                shoji_bay(u0, u1, BFL)
            for b in range(bays + 1):
                mb.box((b * bwl, -0.06, (BFL + BTOP) / 2), (0.24, 0.24, BTOP - BFL), DARK)
            mb.box((length / 2, -0.1, NAGESHI + 0.08), (length + 0.24, 0.16, 0.16), DARK)
            mb.box((length / 2, -0.1, BTOP - 0.1), (length + 0.24, 0.16, 0.2), DARK)
            mb.box((length / 2, -0.1, BFL + 0.06), (length + 0.24, 0.16, 0.12), DARK)

    face((BX0, BY0), 0, BX1 - BX0, nb, ent)
    face((BX1, BY0), 90, BY1 - BY0, 4)
    face((BX1, BY1), 180, BX1 - BX0, nb)
    face((BX0, BY1), -90, BY1 - BY0, 4)
    # genkan: closed sliding doors at the back, shoe shelves, step stones, noren
    for k, b in enumerate(ent):
        u0, u1 = BX0 + b * bw + 0.11, BX0 + (b + 1) * bw - 0.11
        ucen = (u0 + u1) / 2
        yb = BY0 + gd
        for s in (-1, 1):
            mb.box((ucen + s * (u1 - u0) / 4, yb - 0.04, BFL + 1.1), ((u1 - u0) / 2 - 0.04, 0.06, 2.2), "M_ShojiPaper")
            for kk in range(1, 4):
                mb.box((ucen + s * (u1 - u0) / 4, yb - 0.08, BFL + 2.2 * kk / 4), ((u1 - u0) / 2 - 0.1, 0.03, 0.03), DARK)
        mb.box((ucen, yb - 0.05, BFL + 2.25), (u1 - u0, 0.1, 0.1), DARK)
        mb.box((u0 + 0.22, BY0 + 0.95, BFL + 0.6), (0.4, 0.9, 1.2), WOOD)
        for kk in range(3):
            mb.box((u0 + 0.43, BY0 + 0.95, BFL + 0.25 + kk * 0.38), (0.02, 0.85, 0.02), DARK)
        mb.box_mm((ucen - 0.7, py0 - 0.55, DECK), (ucen + 0.7, py0 + 0.05, DECK + 0.22), EDGE)
        # noren (blue = men, red = women) with a white hot-spring mark
        mat = ("M_NorenBlue", "M_NorenRed")[k]
        w = u1 - u0
        for j in range(3):
            xa = u0 + w * j / 3 + 0.02
            xb = u0 + w * (j + 1) / 3 - 0.02
            nc.box(((xa + xb) / 2, BY0 - 0.14, NAGESHI - 0.6), (xb - xa, 0.02, 1.2), mat)
        zc = NAGESHI - 0.75
        nc.box((ucen, BY0 - 0.16, zc - 0.2), (0.5, 0.01, 0.06), "M_WhiteWall")
        for s in (-1, 1):
            nc.box((ucen + s * 0.25, BY0 - 0.16, zc - 0.05), (0.06, 0.01, 0.3), "M_WhiteWall")
        for s in (-1, 0, 1):
            for q in range(3):
                rbox(nc, (ucen + s * 0.14 + (0.03 if q % 2 else -0.03), BY0 - 0.16, zc + 0.12 + q * 0.11),
                     (0.04, 0.01, 0.12), "M_WhiteWall", pitch=25 if q % 2 else -25)
        mb.beam((u0 - 0.1, BY0 - 0.14, NAGESHI + 0.02), (u1 + 0.1, BY0 - 0.14, NAGESHI + 0.02), 0.05, 0.05, "M_Bamboo")
    # roof
    cx, cy = (BX0 + BX1) / 2, (BY0 + BY1) / 2
    hw, hd = (BX1 - BX0) / 2, (BY1 - BY0) / 2
    zt = jp_roof(mb, (cx, cy), hw + 1.5, hd + 1.5, BTOP + 0.15, 3.1, hw + 0.12, hd + 0.12, BTOP - 0.05)
    # red paper lanterns under the front eave
    lanterns = []
    for x in (BX0 + bw * 0.5, BX0 + bw * 3.0, BX0 + bw * 5.5):
        lx, ly, lz = x, BY0 - 0.85, BTOP - 0.75
        mb.beam((lx, ly, lz + 0.4), (lx, ly, BTOP + 0.05), 0.03, 0.03, "M_DarkMetal")
        mb.cylinder((lx, ly, lz + 0.3), 0.14, 0.08, "M_Black", seg=10)
        mb.lathe([(0.16, -0.32), (0.27, -0.12), (0.29, 0.06), (0.24, 0.24), (0.15, 0.3)], "M_RedFelt", seg=12,
                 center=(lx, ly, lz))
        mb.cylinder((lx, ly, lz - 0.38), 0.15, 0.07, "M_Black", seg=10)
        lanterns.append((lx, ly, lz))
    return lanterns


def _beds_and_paths(mb, rng):
    """Raked gravel bed, planting beds and stepping-stone paths to the pool entries. Returns planting spots."""
    spots = []

    def bed(cx, cy, rx, ry, mat, top):
        pts = [(cx + math.cos(TAU * i / 14) * rx, cy + math.sin(TAU * i / 14) * ry) for i in range(14)]
        mb.prism(pts, DECK - 0.1, top, mat, cap_bottom=False)
        n = int(TAU * (rx + ry) / 2 / 0.75)
        for k in range(n):
            a = TAU * (k + rng.uniform(-0.2, 0.2)) / n
            with mb.at((cx + math.cos(a) * rx, cy + math.sin(a) * ry, DECK + 0.05), rot=math.degrees(a) + 90):
                rock(mb, (0, 0, 0), (rng.uniform(0.3, 0.42) * 1.3, rng.uniform(0.25, 0.35), rng.uniform(0.1, 0.16)), rng)

    # dry garden: raked gravel with three standing stones
    gx, gy, grx, gry = 6.5, -10.5, 4.2, 2.3
    bed(gx, gy, grx, gry, "M_Sand", DECK + 0.08)
    for k in range(-3, 4):
        yy = gy + k * 0.5
        half = grx * math.sqrt(max(0.0, 1 - ((yy - gy) / gry) ** 2)) - 0.35
        if half > 0.3:
            mb.poly([(gx - half, yy - 0.025, DECK + 0.085), (gx + half, yy - 0.025, DECK + 0.085),
                     (gx + half, yy + 0.025, DECK + 0.085), (gx - half, yy + 0.025, DECK + 0.085)], "M_OnsenPaving2")
    rock(mb, (gx - 1.4, gy + 0.2, DECK + 0.65), (0.45, 0.4, 0.75), rng)
    rock(mb, (gx - 0.6, gy - 0.3, DECK + 0.3), (0.45, 0.35, 0.3), rng)
    rock(mb, (gx + 1.6, gy + 0.4, DECK + 0.25), (0.55, 0.4, 0.22), rng)
    # planting beds
    for (cx, cy, rx, ry) in ((-16.5, 4.5, 2.4, 1.8), (3.2, 17.0, 2.6, 1.5), (21.0, 7.0, 1.4, 2.2)):
        bed(cx, cy, rx, ry, "M_Soil", DECK + 0.12)
        spots.append((cx, cy, DECK + 0.12))
    # stepping stones to the pool entries
    starts = ((-1.2, -9.5), (-1.2, -7.0), (-10.0, -3.6))
    for p, st in zip(POOLS, starts):
        ea = math.radians(p["entry"])
        er = pool_radius(p, ea) + 0.9
        ex, ey = p["c"][0] + math.cos(ea) * er, p["c"][1] + math.sin(ea) * er
        dx, dy = ex - st[0], ey - st[1]
        ln = math.hypot(dx, dy)
        n = max(2, int(ln / 0.95))
        for k in range(n + 1):
            t = k / n
            wob = math.sin(t * math.pi * 2) * 0.35
            x = st[0] + dx * t - dy / ln * wob
            y = st[1] + dy * t + dx / ln * wob
            if in_pool(x, y, 0.5):
                continue
            rock(mb, (x, y, DECK + 0.0), (rng.uniform(0.38, 0.48), rng.uniform(0.32, 0.4), 0.07), rng, seg=8)
    return spots


def _washplace(mb, rng):
    """Outdoor wash station along the bathhouse back wall: counter, taps, stools, buckets."""
    y = BY1
    mb.box_mm((-14.6, y, DECK), (-6.4, y + 0.5, DECK + 0.55), EDGE)
    mb.box_mm((-14.7, y, DECK + 0.55), (-6.3, y + 0.6, DECK + 0.62), WOOD)
    for k in range(5):
        x = -13.8 + k * 1.75
        mb.box((x, y - 0.04 + 0.08, BFL + 0.75), (0.05, 0.16, 0.05), "M_Metal")
        mb.box((x, y + 0.14, BFL + 0.72), (0.04, 0.04, 0.1), "M_Metal")
        mb.box((x, y + 0.05, BFL + 1.25), (0.5, 0.04, 0.6), "M_Glass")
        if k < 4:
            stool(mb, (x, y + 1.3, DECK), rng.uniform(-10, 10))
            bucket(mb, (x + 0.25, y + 0.35, DECK + 0.62), r=0.14, h=0.2)
    # bucket stacks and stools by the pools
    for (x, yy) in ((3.6, -2.6), (13.5, 13.2), (-3.4, 9.6), (13.0, -11.5)):
        bucket(mb, (x, yy, DECK))
        bucket(mb, (x + 0.38, yy + 0.1, DECK))
        bucket(mb, (x + 0.19, yy + 0.05, DECK + 0.24))
    stool(mb, (4.5, -2.0, DECK), 20)
    stool(mb, (-4.0, 9.2, DECK), -15)


def _garden(mb, nc, rng):
    # torii-like gate at ground level
    gy, gx = -28.0, 1.95
    for s in (-1, 1):
        mb.cylinder((s * gx, gy, 0.0), 0.18, 4.3, DARK, seg=12, radius_top=0.16)
        mb.cylinder((s * gx, gy, 0.0), 0.28, 0.35, "M_OnsenStoneEdge", seg=10)
    mb.box((0, gy, 3.25), (4.9, 0.18, 0.24), DARK)                 # nuki
    mb.box((0, gy, 4.32), (5.2, 0.32, 0.22), DARK)                 # shimaki
    for s in (-1, 1):                                               # kasagi with upturned ends
        mb.box((s * 1.4, gy, 4.55), (2.85, 0.42, 0.24), RTILE)
        rbox(mb, (s * 3.0, gy, 4.66), (0.5, 0.42, 0.24), RTILE, pitch=-s * 14)
    mb.box((0, gy, 4.62), (0.4, 0.42, 0.18), RTILE)
    mb.box((0, gy, 3.82), (3.06, 0.12, 0.96), DARK)                # plaque: black lacquer, gold letters
    mb.box((0, gy, 3.82), (2.86, 0.16, 0.78), "M_Black")
    # stepping stones: gate -> terrace stairs
    pts = [(0.0, gy + 1.2), (-0.6, gy + 2.6), (-1.4, gy + 4.0), (-2.2, gy + 5.4), (-2.8, gy + 6.8), (-3.0, gy + 8.1)]
    for (x, y) in pts:
        rbox(mb, (x, y, -0.04), (1.1, 0.85, 0.16), EDGE, yaw=rng.uniform(-20, 20))
    # notice board (lore sign) beside the gate
    with mb.at((3.6, gy - 0.6, 0), rot=-15):
        mb.box((0, 0.05, 0.9), (0.14, 0.14, 1.8), DARK)
        mb.box((0, 0, 1.55), (1.3, 0.08, 0.8), WOOD)
        mb.box((0, -0.01, 2.02), (1.5, 0.3, 0.1), RTILE)
    # bamboo fence screens (west + north edges, partition between the big pool and the private pool)
    bamboo_fence(mb, [(TX0 + 0.9, -3.5), (TX0 + 0.9, TY1 - 3.2), (TX0 + 3.2, TY1 - 0.9), (6.5, TY1 - 0.9)], 2.3, rng)
    bamboo_fence(mb, [(-1.2, 19.8), (-1.2, 12.5), (0.2, 8.0)], 2.1, rng)
    # low railing along the sea-view edges (east / south-east)
    rail = [(6.5, TY1 - 0.75), (TX1 - TCR, TY1 - 0.75)]
    for k in range(6):
        a = math.radians(90 - 90 * (k + 1) / 6)
        rail.append((TX1 - TCR + math.cos(a) * (TCR - 0.75), TY1 - TCR + math.sin(a) * (TCR - 0.75)))
    rail.append((TX1 - 0.75, TY0 + TCR))
    for k in range(6):
        a = math.radians(0 - 90 * (k + 1) / 6)
        rail.append((TX1 - TCR + math.cos(a) * (TCR - 0.75), TY0 + TCR + math.sin(a) * (TCR - 0.75)))
    rail.append((1.0, TY0 + 0.75))
    mb.railing([(x, y, DECK) for (x, y) in rail], 0.9, DARK, post_spacing=1.6, post_size=0.1, rail_size=0.08)

    # rest pavilion (azumaya) near the sea edge
    ax, ay = 19.0, 13.5
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((ax + sx * 1.6, ay + sy * 1.6, DECK + 1.35), (0.18, 0.18, 2.7), DARK)
    mb.box_mm((ax - 1.9, ay - 1.9, DECK - 0.05), (ax + 1.9, ay + 1.9, DECK + 0.08), EDGE)
    for (dx, dy, w, d) in ((0, 1.35, 3.0, 0.45), (1.35, 0, 0.45, 2.2)):
        mb.box((ax + dx, ay + dy, DECK + 0.42), (w, d, 0.06), WOOD)
        mb.box((ax + dx, ay + dy, DECK + 0.2), (w - 0.2, d - 0.1, 0.4), DARK)
    jp_roof(mb, (ax, ay), 2.6, 2.6, DECK + 2.85, 1.7, 1.7, 1.7, DECK + 2.7, m=6, rings=5, lift=0.3, ridge=False)

    # red tea umbrella + felt bench overlooking the sea
    ux, uy = 20.5, -2.0
    mb.box((ux, uy, DECK + 0.42), (2.0, 0.7, 0.08), "M_RedFelt")
    for sx in (-1, 1):
        mb.box((ux + sx * 0.85, uy, DECK + 0.19), (0.08, 0.6, 0.38), DARK)
    mb.cylinder((ux - 0.2, uy + 0.55, DECK), 0.04, 2.6, "M_Bamboo", seg=6)
    mb.cone((ux - 0.2, uy + 0.55, DECK + 2.25), 1.7, 0.55, "M_RedFelt", seg=16, cap_bottom=True)
    for k in range(16):
        a = TAU * k / 16
        mb.beam((ux - 0.2, uy + 0.55, DECK + 2.05), (ux - 0.2 + math.cos(a) * 1.6, uy + 0.55 + math.sin(a) * 1.6,
                DECK + 2.27), 0.02, 0.02, "M_Bamboo")


def _sockets(aset, rng, lanterns, spout):
    gy = -28.0
    # stone lanterns (lights are added automatically by the prop)
    for (x, y, z) in ((-3.2, gy + 0.6, 0.0), (3.0, gy + 1.4, 0.0), (2.6, -4.2, DECK), (22.0, 2.5, DECK),
                      (-13.0, 9.0, DECK), (15.0, 16.0, DECK), (-0.2, -14.6, DECK), (-17.5, 0.5, DECK)):
        aset.prop("SM_StoneLantern", (x, y, z), rng.uniform(-20, 20))
    # garden planting outside the terrace and in corners
    for (x, y, a, s) in ((-26.0, 6.0, "SM_PineTree_A", 0.9), (-24.0, 22.0, "SM_PineTree_A", 1.0),
                         (-10.0, 26.0, "SM_PineTree_A", 0.85), (5.0, 26.5, "SM_BroadTree_C", 1.0),
                         (-6.5, -26.0, "SM_BroadTree_C", 1.0), (6.5, -25.0, "SM_BroadTree_C", 0.9),
                         (-19.0, -19.0, "SM_BroadTree_C", 1.1), (-18.0, 18.0, "SM_BroadTree_C", 0.7)):
        z = DECK if (TX0 < x < TX1 and TY0 < y < TY1) else 0.0
        aset.prop(a, (x, y, z), rng.uniform(0, 360), s)
    for (x, y) in ((-5.5, -19.0), (0.5, -19.5), (-9.0, -18.5), (4.0, -18.5), (-24.0, -6.0), (27.0, 0.0),
                   (26.5, 12.0), (-23.5, 12.0), (12.0, -18.5)):
        aset.prop(rng.choice(("SM_Bush_A", "SM_Fern_A", "SM_Bush_B")), (x, y, 0.0), rng.uniform(0, 360))
    for (x, y) in ((-14.0, 18.5), (-3.0, 18.5)):
        aset.prop(rng.choice(("SM_Fern_A", "SM_Bush_B")), (x, y, DECK), rng.uniform(0, 360))
    for (x, y, a) in ((-28.0, -10.0, "SM_Rock_D"), (28.5, -8.0, "SM_Rock_A"), (27.0, 20.0, "SM_Rock_B"),
                      (-25.0, 28.0, "SM_VolcanicRock_A"), (12.0, 27.0, "SM_Rock_C")):
        aset.prop(a, (x, y, 0.0), rng.uniform(0, 360))
    # text: gate plaque + notice board
    aset.text("HOT SPRINGS", (0.0, gy - 0.08 - 0.03, 3.82), 0.0, size=0.34, color=(1.0, 0.8, 0.35))
    by = -15.0
    nx, ny = math.sin(math.radians(by)), -math.cos(math.radians(by))
    aset.text("ONSEN", (3.6 + nx * 0.07, gy - 0.6 + ny * 0.07, 1.55), by, size=0.28, color=(0.15, 0.08, 0.04))
    aset.interact("sign", (3.6 + nx * 0.8, gy - 0.6 + ny * 0.8, 1.2), by, title="Hot Springs",
                  text="Water heated by the volcano itself. Relax after a long day of duels.")
    # steam over each pool (scale ~ pool radius / 2) + at the spout
    for p in POOLS:
        rad = (p["r"][0] + p["r"][1]) / 2
        aset.emitter("steam", (p["c"][0], p["c"][1], WATER + 0.1), round(rad / 2, 2))
    aset.emitter("steam", (spout[0], spout[1], WATER + 0.1), 0.6)
    aset.audio("A_HotSpring", (8.0, 6.0, DECK), radius=40.0)
    aset.audio("A_Waterfall", (spout[0], spout[1], DECK), radius=12.0, volume=0.6)
    # lights: paper lanterns, pool glow, pavilion (night only)
    for (x, y, z) in lanterns:
        aset.light((x, y, z), (1.0, 0.45, 0.2), 1500.0, 8.0, night_only=True)
    for p in POOLS:
        aset.light((p["c"][0], p["c"][1], DECK + 2.0), (1.0, 0.8, 0.55), 1200.0, 9.0, night_only=True)
    aset.light((19.0, 13.5, DECK + 2.4), (1.0, 0.75, 0.45), 1200.0, 7.0, night_only=True)
    aset.light((0.0, gy - 0.6, 3.6), (1.0, 0.7, 0.4), 1200.0, 7.0, night_only=True)
    # bathers
    aset.npc((3.0, 1.6, DECK), 30.0, "obelisk", 2.0)
    aset.npc((-9.0, -14.0, BFL), 0.0, "slifer", 3.0)
    aset.npc((20.5, -2.6, DECK), 0.0, "ra", 1.5)
    aset.special("camera", (-1.5, -3.5, DECK + 1.8), target=(10.0, 8.0, DECK + 0.4), lens=22)


def build():
    rng = random.Random(330)
    aset = AssetSet("hotsprings")
    terrace = aset.mesh("Onsen_Terrace")
    house = aset.mesh("Onsen_Bathhouse")
    garden = aset.mesh("Onsen_Garden")
    nc = aset.mesh("Onsen_NoCol")
    _terrace(terrace, nc, rng)
    spout = _waterfall(terrace, nc, rng)
    lanterns = _bathhouse(house, nc, rng)
    _washplace(garden, rng)
    spots = _beds_and_paths(terrace, rng)
    _garden(garden, nc, rng)
    _sockets(aset, rng, lanterns, spout)
    for k, (x, y, z) in enumerate(spots):
        aset.prop(("SM_BroadTree_C", "SM_Fern_A", "SM_Bush_A")[k], (x, y, z), rng.uniform(0, 360),
                  (0.75, 1.3, 1.0)[k])
        aset.prop("SM_Fern_A", (x + 0.9, y - 0.4, z), rng.uniform(0, 360), 0.9)
    return aset


PLACEMENTS = {"hotsprings": build}
