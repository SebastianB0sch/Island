"""
Hot Springs - a small Japanese onsen on the volcano foothills.

A raised stone-paved terrace (deck at DECK = +1.2 m so the 1 m deep basins stay
above the flattened terrain) holding three irregular rock-rimmed pools, a wooden
bathhouse with shoji walls, red/blue noren and a dark tiled hip roof with
upturned eaves, a bamboo water spout, bamboo fence screens, a rest pavilion and
a red tea umbrella looking out over the sea (local +X / +Y). A small wooden
torii-like gate with a "HOT SPRINGS" plaque marks the entrance at ground level.

The bathhouse is walk-in: each genkan (blue noren = men, red = women) has sliding
shoji doors into a changing room (wooden cubbies with baskets, lockers, vanity,
bench, scales, coffee-milk fridge) with the bandai reception booth straddling the
partition between both sides; sliding glass doors lead on into the washing areas
(low taps, stools, buckets, a mural of the volcano) whose shoji side doors open
onto the terrace and the pools.

Local space: origin = pad centre at ground level, front faces -Y; the trail
arrives at about (0, -45).
"""

import math
import random

from . import AssetSet
from . import interior as K
from . import detail as DT
from .. import palette

palette.register({
    "M_OnsenRoof":      dict(kind="opaque", color=(0.20, 0.21, 0.25), rough=0.7, detail="RoofTiles", tiling=0.5),
    "M_OnsenPaving":    dict(kind="opaque", color=(0.53, 0.52, 0.49), rough=0.9, detail="Paving", tiling=0.5),
    "M_OnsenPaving2":   dict(kind="opaque", color=(0.44, 0.43, 0.42), rough=0.9, detail="Paving", tiling=0.5),
    "M_OnsenStoneEdge": dict(kind="opaque", color=(0.50, 0.48, 0.45), rough=0.9, detail="Concrete", tiling=0.5),
    "M_NorenBlue":      dict(kind="foliage", color=(0.10, 0.20, 0.52), rough=0.95, detail=None),
    "M_NorenRed":       dict(kind="foliage", color=(0.74, 0.12, 0.12), rough=0.95, detail=None),
    "M_Bamboo":         dict(kind="opaque", color=(0.66, 0.62, 0.34), rough=0.55, detail=None),
    "M_MuralSky":       dict(kind="toon", color=(0.62, 0.80, 0.97), rough=0.9, fill=0.35),
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
WT = 0.15                       # bathhouse wall thickness (walls sit inside the facade line)
GEN_Y = BY0 + 1.45              # back wall line of the genkan alcoves (doors)
DIV_Y = -8.1                    # changing room | washing area divider (south face)
PART_X = -9.4                   # men | women partition (centre)
CEIL_Z = BFL + 3.0              # interior ceiling
SIDE_DOOR_Y = -6.0              # side exits from the washing areas (west = men, east = women)


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
    # front wall blocks between / beside the genkan alcoves (solid), alcove ceilings; the rest of the
    # house is hollow (walls + rooms: _bath_interior)
    xs = [BX0]
    for b in ent:
        xs += [BX0 + b * bw + 0.11, BX0 + (b + 1) * bw - 0.11]
    xs.append(BX1)
    for i in range(len(xs) - 1):
        xa, xb = xs[i], xs[i + 1]
        if i % 2 == 1:   # alcove column
            mb.box_mm((xa, BY0, NAGESHI), (xb, BY0 + gd, BTOP), "M_CreamWall", mats={"-z": DARK})
        else:
            mb.box_mm((xa, BY0, BFL), (xb, BY0 + gd, BTOP), "M_CreamWall", mats={"+y": K.PLASTER_CREAM})

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
    face((BX1, BY0), 90, BY1 - BY0, 4, (3,))        # bay 3 = women's side exit
    face((BX1, BY1), 180, BX1 - BX0, nb)
    face((BX0, BY1), -90, BY1 - BY0, 4, (0,))       # bay 0 = men's side exit
    # side exits from the washing areas: transom panel over the sliding door, short noren, step stones
    for (org, yaw, u, mat, sx) in (((BX1, BY0), 90, SIDE_DOOR_Y - BY0, "M_NorenRed", 1),
                                   ((BX0, BY1), -90, BY1 - SIDE_DOOR_Y, "M_NorenBlue", -1)):
        with mb.at((org[0], org[1], 0), rot=yaw), nc.at((org[0], org[1], 0), rot=yaw):
            mb.box((u, -0.03, (BFL + 2.2 + NAGESHI) / 2), (1.78, 0.06, NAGESHI - BFL - 2.2), "M_ShojiPaper", skip=("+y",))
            mb.box((u, -0.08, BFL + 2.25), (1.78, 0.08, 0.1), DARK, skip=("+y",))
            for k in range(1, 4):
                mb.box((u - 0.89 + 1.78 * k / 4, -0.07, (BFL + 2.3 + NAGESHI) / 2), (0.025, 0.03, NAGESHI - BFL - 2.3),
                       DARK, skip=("+y",))
            for j in range(2):
                nc.box((u - 0.42 + 0.84 * j, -0.14, NAGESHI - 0.3), (0.8, 0.02, 0.6), mat)
            mb.beam((u - 0.95, -0.14, NAGESHI + 0.02), (u + 0.95, -0.14, NAGESHI + 0.02), 0.05, 0.05, "M_Bamboo")
        ex = BX1 + 1.1 if sx > 0 else BX0 - 0.6
        for k, top in enumerate((DECK + 0.30, DECK + 0.15)):
            a, b = sorted((ex + sx * 0.42 * k, ex + sx * 0.42 * (k + 1)))
            mb.box_mm((a, SIDE_DOOR_Y - 0.7, DECK - 0.1), (b, SIDE_DOOR_Y + 0.7, top), EDGE)
    # genkan: closed sliding doors at the back, shoe shelves, step stones, noren
    for k, b in enumerate(ent):
        u0, u1 = BX0 + b * bw + 0.11, BX0 + (b + 1) * bw - 0.11
        ucen = (u0 + u1) / 2
        # (the closed shoji panels are a real doorway with sliding shoji doors now, see _bath_interior)
        mb.box((ucen, GEN_Y - 0.05, BFL + 2.25), (u1 - u0, 0.1, 0.1), DARK)
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


# ---------------------------------------------------------------- bathhouse interior
def _cubbies(mb, aset, x, y, yaw, cols=6, rows=3, cw=0.47, ch=0.55, d=0.45, seed=0, nc=None):
    """Open wooden cubby shelves with a wicker basket in every cubby (origin bottom centre, back at +Y, open side
    -Y); with nc, some baskets hold a folded towel or a yukata."""
    rnd = random.Random(seed)
    w, h = cols * cw, rows * ch + 0.08
    a = math.radians(yaw)
    with mb.at((x, y, BFL), rot=yaw):
        mb.box((0, d / 2 - 0.01, h / 2), (w, 0.02, h), WOOD)
        for i in range(cols + 1):
            mb.box((-w / 2 + i * cw, 0, h / 2), (0.03, d, h), WOOD)
        for k in range(rows + 1):
            mb.box((0, 0, 0.04 + k * ch), (w + 0.03, d, 0.03), WOOD)
        mb.box((0, 0, h + 0.03), (w + 0.1, d + 0.06, 0.05), DARK)
        mb.box((0, -d / 2 + 0.02, 0.02), (w, 0.04, 0.04), DARK)
    for k in range(rows):
        for i in range(cols):
            r = rnd.random()
            lx, ly = -w / 2 + cw * (i + 0.5), -0.02
            px, py = x + lx * math.cos(a) - ly * math.sin(a), y + lx * math.sin(a) + ly * math.cos(a)
            aset.prop("SM_Int_Basket", (px, py, BFL + 0.055 + k * ch), yaw + rnd.uniform(-8, 8), 0.95)
            if nc is not None and r < 0.6:
                with nc.at((px, py, BFL + 0.06 + k * ch + 0.08), rot=yaw + rnd.uniform(-10, 10)):
                    m = rnd.choice(("M_IntFabricWhite", "M_IntFabricBlue", "M_IntFabricWhite", "M_NorenBlue",
                                    "M_IntFabricPink"))
                    nc.box((0, 0, 0.02), (0.3, 0.2, 0.05 + 0.03 * (r < 0.3)), m)
                    if r < 0.15:
                        nc.box((0.05, -0.02, 0.07), (0.16, 0.1, 0.04), "M_IntFabricYellow")


def _key_lockers(mb, nc, x, y, yaw, cols=5, rows=3, cw=0.4, d=0.45, h=1.8):
    """Wooden shoe-box style lockers with brass key tags (doors at -Y)."""
    w = cols * cw
    with mb.at((x, y, BFL), rot=yaw), nc.at((x, y, BFL), rot=yaw):
        mb.box((0, 0, h / 2 + 0.05), (w, d, h), WOOD)
        mb.box((0, 0, 0.025), (w, d - 0.05, 0.05), DARK)
        rh = h / rows
        for k in range(rows):
            for i in range(cols):
                cx, cz = -w / 2 + cw * (i + 0.5), 0.05 + rh * (k + 0.5)
                nc.box((cx, -d / 2 - 0.006, cz), (cw - 0.04, 0.012, rh - 0.04), "M_IntWoodDark")
                nc.box((cx, -d / 2 - 0.015, cz + rh * 0.2), (0.05, 0.01, 0.08), "M_Gold")
                nc.box((cx, -d / 2 - 0.016, cz + rh * 0.12), (0.035, 0.008, 0.04), "M_RedFelt")


def _washi_light(aset, nc, x, y, z=CEIL_Z):
    """Square paper ceiling lamp (andon style) + its light."""
    nc.box((x, y, z - 0.03), (0.7, 0.7, 0.06), DARK)
    nc.box((x, y, z - 0.2), (0.6, 0.6, 0.28), "M_ShojiPaper")
    nc.box((x, y, z - 0.345), (0.56, 0.56, 0.01), "M_IntWarmGlow")
    for s in (-1, 1):
        nc.box((x + s * 0.3, y, z - 0.2), (0.03, 0.62, 0.3), DARK)
        nc.box((x, y + s * 0.3, z - 0.2), (0.62, 0.03, 0.3), DARK)
    aset.light((x, y, z - 0.6), (1.0, 0.85, 0.62), 2600.0, 7.0, night_only=False)


def _jp_room(mb, x0, y0, x1, y1, z_rail=BFL + 2.2):
    """Japanese room trim: wooden ceiling with battens, corner posts and a nageshi rail."""
    K.ceiling(mb, x0, y0, x1, y1, CEIL_Z, "M_IntCeilingWood")
    x = x0 + 0.6
    while x < x1 - 0.3:
        mb.box_mm((x - 0.025, y0, CEIL_Z - 0.04), (x + 0.025, y1, CEIL_Z), DARK)
        x += 0.6
    for (cx, cy) in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        mb.box((cx + (0.05 if cx == x0 else -0.05), cy + (0.05 if cy == y0 else -0.05), (BFL + CEIL_Z) / 2),
               (0.1, 0.1, CEIL_Z - BFL), DARK)
    for (a, b, c, d) in ((x0, y0, x1, y0 + 0.05), (x0, y1 - 0.05, x1, y1), (x0, y0, x0 + 0.05, y1), (x1 - 0.05, y0, x1, y1)):
        mb.box_mm((a, b, z_rail), (c, d, z_rail + 0.1), DARK)


def _wash_station(mb, nc, aset, x, y_wall, rng):
    """Low tap + mirror on the back wall (wall face at y_wall, room towards -y), stool and bucket."""
    mb.box((x, y_wall - 0.012, BFL + 1.18), (0.46, 0.02, 0.55), "M_IntMetal")                  # mirror
    mb.box((x, y_wall - 0.012, BFL + 1.18), (0.52, 0.015, 0.61), "M_IntTrimWhite")
    for s in (-1, 1):
        mb.box((x + s * 0.12, y_wall - 0.33, BFL + 0.72), (0.05, 0.06, 0.06), "M_IntMetal")      # taps
        mb.box((x + s * 0.12, y_wall - 0.36, BFL + 0.74), (0.07, 0.02, 0.02), "M_IntFabricRed" if s < 0 else "M_IntFabricBlue")
    mb.box((x, y_wall - 0.28, BFL + 0.66), (0.4, 0.06, 0.06), "M_IntMetal")
    mb.cylinder((x + 0.3, y_wall - 0.04, BFL + 0.75), 0.015, 0.45, "M_IntMetal", seg=6)          # hand shower
    mb.cylinder((x + 0.3, y_wall - 0.06, BFL + 1.18), 0.035, 0.12, "M_IntMetal", seg=8)
    for k, m in enumerate(("M_IntFabricPink", "M_IntFabricGreen", "M_IntFabricWhite")):
        nc.cylinder((x - 0.18 + 0.08 * k, y_wall - 0.12, BFL + 0.6), 0.03, rng.uniform(0.12, 0.18), m, seg=6)
    stool(mb, (x, y_wall - 0.85, BFL), rng.uniform(-8, 8))
    bucket(mb, (x - 0.32, y_wall - 0.6, BFL), r=0.13, h=0.18)


def _mural(mb, nc, xf, yc, yaw, w=2.5, z0=BFL + 1.15, h=1.75):
    """Sento wall painting of the island's volcano over the sea; (xf, yc) on the wall face."""
    with nc.at((xf, yc, z0), rot=yaw):
        nc.box((0, -0.006, h / 2), (w, 0.012, h), "M_MuralSky")
        nc.box((0, -0.008, h * 0.12), (w, 0.012, h * 0.24), "M_IntFabricBlue")                    # sea
        for k in range(5):                                                                        # wave crests
            nc.box((-w / 2 + w * (k + 0.5) / 5, -0.016, h * 0.22), (w * 0.12, 0.006, 0.03), "M_IntFabricWhite")
        y = -0.016
        pts = [(-w * 0.42, h * 0.24), (w * 0.38, h * 0.24), (w * 0.08, h * 0.82), (-w * 0.12, h * 0.82)]
        nc.poly([(p[0], y, p[1]) for p in pts], "M_IntSteelBlue")                                 # volcano
        cap = [(-w * 0.2, h * 0.66), (w * 0.15, h * 0.66), (w * 0.08, h * 0.82), (-w * 0.12, h * 0.82)]
        nc.poly([(p[0], y - 0.004, p[1]) for p in cap], "M_IntFabricWhite")                        # ash cap
        nc.box((-0.02 * w, y - 0.008, h * 0.86), (w * 0.12, 0.006, h * 0.07), "M_IntFabricOrange")  # glow / smoke
        for (cx, cz, cw) in ((-w * 0.33, h * 0.85, w * 0.22), (w * 0.3, h * 0.7, w * 0.26)):
            nc.box((cx, y, cz), (cw, 0.006, h * 0.08), "M_IntFabricWhite")                        # clouds
        nc.box((0, -0.004, h / 2), (w + 0.1, 0.008, h + 0.1), DARK)                                 # frame


def _bath_interior(aset, mb, nc):
    rng = random.Random(77)
    PL, TILE = K.PLASTER_CREAM, "M_IntTileWhite"
    pxw, pxe = PART_X - WT / 2, PART_X + WT / 2
    ym = DIV_Y + WT / 2
    gy1 = BY0 + 1.6                      # room side of the front blocks
    # ---------------- walls
    bw = (BX1 - BX0) / 6
    for b in (1, 4):                     # genkan doorways (sliding shoji)
        xa, xb = BX0 + b * bw + 0.11, BX0 + (b + 1) * bw - 0.11
        K.wall(aset, mb, (xa, GEN_Y), (xb, GEN_Y), BFL, BTOP - BFL, WT, "M_CreamWall", inner=PL,
               openings=[K.Door((xb - xa) / 2 + 0.1, 1.4, 2.2, "shoji", trim=DARK, trim_in=DARK)])
    K.wall(aset, mb, (BX1, BY1), (BX0, BY1), BFL, BTOP - BFL, WT, "M_CreamWall", inner=TILE)
    K.wall(aset, mb, (BX0, BY1), (BX0, ym), BFL, BTOP - BFL, WT, "M_CreamWall", inner=TILE,
           openings=[K.Door(BY1 - SIDE_DOOR_Y, 1.6, 2.2, "shoji", trim=DARK, trim_in=DARK)])
    K.wall(aset, mb, (BX0, ym), (BX0, gy1), BFL, BTOP - BFL, WT, "M_CreamWall", inner=PL)
    K.wall(aset, mb, (BX1, gy1), (BX1, ym), BFL, BTOP - BFL, WT, "M_CreamWall", inner=PL)
    K.wall(aset, mb, (BX1, ym), (BX1, BY1), BFL, BTOP - BFL, WT, "M_CreamWall", inner=TILE,
           openings=[K.Door(SIDE_DOOR_Y - ym, 1.6, 2.2, "shoji", trim=DARK, trim_in=DARK)])
    K.wall(aset, mb, (pxe, -10.0), (pxe, DIV_Y), BFL, BTOP - BFL, WT, PL, inner=PL)
    K.wall(aset, mb, (pxe, DIV_Y), (pxe, BY1 - WT), BFL, BTOP - BFL, WT, TILE, inner=TILE)
    K.wall(aset, mb, (BX0 + WT, DIV_Y), (pxw, DIV_Y), BFL, BTOP - BFL, WT, PL, inner=TILE,
           openings=[K.Door(-12.2 - (BX0 + WT), 1.2, 2.1, "glass", trim_in=K.TRIM_WOOD, trim=K.TRIM_WOOD)])
    K.wall(aset, mb, (pxe, DIV_Y), (BX1 - WT, DIV_Y), BFL, BTOP - BFL, WT, PL, inner=TILE,
           openings=[K.Door(-6.6 - pxe, 1.2, 2.1, "glass", trim_in=K.TRIM_WOOD, trim=K.TRIM_WOOD)])

    rooms = {"men_ch": (BX0 + WT, gy1, pxw, DIV_Y), "wom_ch": (pxe, gy1, BX1 - WT, DIV_Y),
             "men_wa": (BX0 + WT, DIV_Y + WT, pxw, BY1 - WT), "wom_wa": (pxe, DIV_Y + WT, BX1 - WT, BY1 - WT)}
    for key, (x0, y0, x1, y1) in rooms.items():
        _jp_room(mb, x0, y0, x1, y1)
        if key.endswith("ch"):
            K.floor_planks(mb, x0, y0, x1, y1, BFL + 0.004, mat=K.WOODFLOOR, seam="M_IntWoodDark")
            K.wainscot(mb, (x0, y0), (x1, y0), BFL, 0.1, DARK, gaps=[(1.0, 5.2)])
        else:
            mb.box_mm((x0, y0, BFL - 0.01), (x1, y1, BFL + 0.004), "M_IntTileBlue", skip=("-z",))
            for t in range(1, int((x1 - x0) / 0.6)):
                mb.box_mm((x0 + t * 0.6 - 0.006, y0, BFL + 0.004), (x0 + t * 0.6 + 0.006, y1, BFL + 0.006),
                          "M_IntTileWhite", skip=("-z",))
            gap = {"men_wa": ("w", (y1 - SIDE_DOOR_Y - 0.95, y1 - SIDE_DOOR_Y + 0.95), "s", (-12.2 - x0 - 0.75, -12.2 - x0 + 0.75)),
                   "wom_wa": ("e", (SIDE_DOOR_Y - y0 - 0.95, SIDE_DOOR_Y - y0 + 0.95), "s", (-6.6 - x0 - 0.75, -6.6 - x0 + 0.75))}[key]
            gaps = {gap[0]: [gap[1]], gap[2]: [gap[3]]}
            for (k, (p0, p1)) in (("s", ((x0, y0), (x1, y0))), ("e", ((x1, y0), (x1, y1))), ("n", ((x1, y1), (x0, y1))),
                                  ("w", ((x0, y1), (x0, y0)))):
                K.wainscot(mb, p0, p1, BFL, 0.9, "M_IntTileBlue", cap=K.TRIM_WHITE, gaps=gaps.get(k, ()))

    # ---------------- changing rooms (men west / women east, mirrored about the partition)
    def mx(x, side):
        return x if side < 0 else 2 * PART_X - x

    for side in (-1, 1):
        x_out = BX0 + WT if side < 0 else BX1 - WT
        _cubbies(mb, aset, x_out - side * 0.225, -9.75, 90.0 if side < 0 else -90.0, seed=3 + side, nc=nc)
        _key_lockers(mb, nc, mx(-14.2, side), DIV_Y - 0.235, 0.0)
        aset.prop("SM_Int_Bench", (mx(-14.2, side), -9.35, BFL), 90.0 if side < 0 else -90.0)
        nc.box((mx(-14.2, side), -9.1, BFL + 0.47), (0.3, 0.45, 0.04), "M_IntFabricWhite" if side < 0 else "M_IntFabricPink")
        # vanity counter with mirrors and stools on the partition
        xv = pxw if side < 0 else pxe
        a, b = sorted((xv, xv - side * 0.45))
        mb.box_mm((a, -9.9, BFL), (b, -8.35, BFL + 0.72), WOOD)
        mb.box_mm((a - 0.02, -9.92, BFL + 0.72), (b + 0.02, -8.33, BFL + 0.76), K.TRIM_WHITE)
        for y in (-9.5, -8.75):
            aset.prop("SM_Int_Mirror", (xv, y, BFL + 0.95), -90.0 if side < 0 else 90.0)
            aset.prop("SM_Int_Stool", (xv - side * 0.85, y, BFL), 0.0)
        nc.box((xv - side * 0.2, -9.15, BFL + 0.78), (0.18, 0.12, 0.05), "M_IntPaper")       # tissue box
        if side < 0:   # hair dryer
            nc.cylinder((xv - side * 0.25, -8.55, BFL + 0.76), 0.045, 0.1, "M_IntFabricWhite", seg=8)
        else:
            aset.prop("SM_Int_PottedPlant", (xv - side * 0.22, -8.55, BFL + 0.76), 0.0)
        # bathroom scales
        sxs = mx(-11.0, side)
        mb.box((sxs, -8.6, BFL + 0.05), (0.38, 0.32, 0.1), K.TRIM_WHITE)
        mb.box((sxs, -8.73, BFL + 0.5), (0.06, 0.06, 0.9), K.TRIM_WHITE)
        mb.cylinder((sxs, -8.73, BFL + 0.95), 0.14, 0.06, K.TRIM_WHITE, seg=12)
        nc.cylinder((sxs, -8.66, BFL + 0.96), 0.11, 0.01, "M_IntPaper", seg=12)
        aset.prop("SM_Int_CeilingFan", (mx(-12.7, side), -9.75, CEIL_Z), 0.0)
        _washi_light(aset, nc, mx(-14.0, side), -9.75)
        _washi_light(aset, nc, mx(-11.2, side), -9.75)
    # men: coffee-milk fridge; women: folding screen and a plant
    with mb.at((-14.75, -11.07, BFL)), nc.at((-14.75, -11.07, BFL)):
        mb.box((0, 0, 0.8), (0.7, 0.6, 1.6), K.TRIM_WHITE)
        nc.box((0, 0.305, 0.85), (0.56, 0.01, 1.1), "M_IntGlassClear")
        nc.box((0, 0.2, 0.85), (0.56, 0.01, 1.1), "M_IntLightPanel")
        for k in range(3):
            for i in range(5):
                nc.cylinder((-0.22 + 0.11 * i, 0.25, 0.38 + k * 0.36), 0.035, 0.14, ("M_IntPaper", "M_IntWood")[(i + k) % 2], seg=6)
        nc.box((0, 0.31, 1.5), (0.6, 0.01, 0.12), "M_IntPoster1")
    aset.text("COFFEE MILK", (-14.75, -11.07 + 0.33, BFL + 1.47), 180.0, size=0.07, color=(1, 1, 1))
    for (x, txt, col) in ((-14.75, "BATH MANNERS", "M_IntPoster2"), (mx(-14.75, 1), "BATH MANNERS", "M_IntPoster4")):
        K.poster(nc, aset, x, gy1, BFL + 2.0, 180.0, 0.62, 0.42, col, txt, (1, 1, 1), 0.06)
        for k, line in enumerate(("1. Wash before you soak", "2. No towels in the water", "3. No duel disks in the bath!")):
            aset.text(line, K.wall_point(x, gy1, 180.0, 0.02, BFL + 1.92 - k * 0.06), 180.0, size=0.035, color=(1, 1, 1))

    # ---------------- bandai: the raised reception booth overlooking both changing rooms
    bx0, bx1, by0, by1 = PART_X - 1.15, PART_X + 1.15, gy1, -10.0
    mb.box_mm((bx0, by0, BFL), (bx1, by1, BFL + 0.75), WOOD, mats={"+z": "M_IntTatami"})
    for (a, b, c, d) in ((bx0, by0, bx0 + 0.1, by1), (bx1 - 0.1, by0, bx1, by1), (bx0, by1 - 0.1, bx1, by1)):
        mb.box_mm((a, b, BFL + 0.75), (c, d, BFL + 1.05), WOOD)
        mb.box_mm((a - 0.05, b, BFL + 1.05), (c + 0.05, d + (0.05 if d == by1 else 0.0), BFL + 1.09), DARK)
    nc.box((PART_X, -10.85, BFL + 0.79), (0.5, 0.5, 0.08), "M_RedFelt")                          # zabuton
    aset.prop("SM_Int_TeaSet", (PART_X + 0.45, -10.45, BFL + 0.75), 10.0)
    aset.prop("SM_Int_Kettle", (PART_X - 0.65, -11.05, BFL + 0.75), 0.0)
    aset.prop("SM_Int_Register", (PART_X - 0.55, -10.35, BFL + 0.75), 0.0)
    mb.box((PART_X, by1 - 0.05, BFL + 2.45), (0.04, 0.04, 0.5), DARK)
    nc.box((PART_X, -10.7, BFL + 2.3), (0.04, 1.2, 0.32), WOOD)
    for (dx, yaw) in ((-0.03, -90.0), (0.03, 90.0)):
        aset.text("RECEPTION", (PART_X + dx, -10.7, BFL + 2.24), yaw, size=0.14, color=(0.2, 0.1, 0.05))
    aset.text("Towel 100 DP - Coffee milk 120 DP", (PART_X - 0.62, -10.7, BFL + 1.12), -90.0, size=0.05,
              color=(0.2, 0.1, 0.05))
    aset.npc((PART_X, -10.8, BFL + 0.75), 0.0, "white", 0.0)

    # ---------------- washing areas
    for side in (-1, 1):
        x0, y0, x1, y1 = rooms["men_wa" if side < 0 else "wom_wa"]
        xs = (-13.6, -12.4, -11.2, -10.0)
        a, b = sorted((mx(-14.2, side), mx(-9.6, side)))
        mb.box_mm((a, y1 - 0.24, BFL + 0.55), (b, y1, BFL + 0.6), TILE)                         # ledge
        for x in xs:
            _wash_station(mb, nc, aset, mx(x, side), y1, rng)
        xf = pxw if side < 0 else pxe
        _mural(mb, nc, xf, (y0 + y1) / 2, -90.0 if side < 0 else 90.0)
        for k in range(3):   # bucket pyramid by the glass door
            bucket(mb, (mx(-10.2 + 0.36 * (k % 2) + (0.18 if k == 2 else 0.0), side), y0 + 0.35 + (0.0 if k < 2 else 0.0),
                        BFL + (0.0 if k < 2 else 0.24)))
        aset.prop("SM_Int_RubberDuck", (mx(-11.75, side), y1 - 0.12, BFL + 0.6), 160.0 if side < 0 else 200.0)
        aset.prop("SM_Int_RubberDuck", (mx(-12.9, side), y1 - 1.3, BFL), 120.0)
        _washi_light(aset, nc, mx(-13.6, side), (y0 + y1) / 2)
        _washi_light(aset, nc, mx(-10.9, side), (y0 + y1) / 2)
        aset.emitter("steam", (mx(-12.0, side), (y0 + y1) / 2, BFL + 1.6), 0.35, rate=0.4)

    # a family of rubber ducks escaped into the big outdoor pool
    for (x, y, yaw) in ((6.2, 4.4, 30.0), (6.6, 4.1, 60.0), (6.95, 3.9, 75.0), (10.5, 8.2, 200.0)):
        aset.prop("SM_Int_RubberDuck", (x, y, WATER - 0.02), yaw)

    # ---------------- preview cameras
    K.camera(aset, "changing_men", (-11.0, -8.45, BFL + 1.7), (-15.2, -10.9, BFL + 0.7), 16.0)
    K.camera(aset, "changing_women", (-7.8, -8.45, BFL + 1.7), (-3.6, -10.9, BFL + 0.7), 16.0)
    K.camera(aset, "bandai", (-12.6, -8.6, BFL + 1.8), (-9.4, -10.8, BFL + 1.0), 18.0)
    K.camera(aset, "wash_men", (-12.2, -7.65, BFL + 1.65), (-14.8, -5.2, BFL + 0.9), 16.0)
    K.camera(aset, "wash_women", (-6.6, -7.65, BFL + 1.65), (-4.0, -5.2, BFL + 0.9), 16.0)


# ---------------------------------------------------------------- detail pass (changing rooms, bandai, washing, pavilion)
def _massage_chair(mb, nc, x, y, yaw, mat="M_IntWoodDark"):
    """Coin-op massage chair (faces local -Y): padded seat, high back, leg rest, armrests with a coin box."""
    with mb.at((x, y, BFL), rot=yaw), nc.at((x, y, BFL), rot=yaw):
        mb.box((0, 0.05, 0.22), (0.72, 0.75, 0.44), "M_Black")
        mb.box((0, 0.0, 0.5), (0.56, 0.62, 0.14), mat)
        with mb.at((0, 0.36, 0.5), rot_x=-14.0):
            mb.box((0, 0.05, 0.5), (0.6, 0.22, 1.0), mat)
            mb.box((0, -0.04, 0.92), (0.4, 0.1, 0.2), mat)
        with mb.at((0, -0.32, 0.45), rot_x=35.0):
            mb.box((0, -0.18, -0.12), (0.42, 0.3, 0.42), mat)
        for s in (-1, 1):
            mb.box((s * 0.33, 0.05, 0.68), (0.12, 0.62, 0.18), "M_Black")
        nc.box((0.33, -0.27, 0.78), (0.1, 0.08, 0.06), "M_IntMetal")
        nc.box((-0.33, -0.27, 0.78), (0.08, 0.06, 0.03), "M_IntScreen")


def _noren(nc, x, y, yaw, w, z_top, mat, drop=0.6, panels=2):
    with nc.at((x, y, z_top), rot=yaw):
        nc.box((0, -0.04, 0.02), (w + 0.1, 0.03, 0.03), "M_Bamboo")
        for j in range(panels):
            pw = w / panels
            nc.box((-w / 2 + pw * (j + 0.5), -0.05, -drop / 2), (pw - 0.02, 0.012, drop), mat)
        nc.box((0, -0.058, -drop * 0.45), (0.16, 0.004, 0.16), "M_IntFabricWhite")


def _kakeyu(mb, nc, x, y0, rng):
    """Tiled pouring basin against the divider (room towards +y): hot water, wooden ladles."""
    with mb.at((x, y0, BFL)), nc.at((x, y0, BFL)):
        mb.box((0, 0.3, 0.06), (1.3, 0.6, 0.12), "M_IntTileBlue")
        for s in (-1, 1):
            mb.box((s * 0.61, 0.3, 0.32), (0.08, 0.6, 0.4), "M_IntTileBlue")
        mb.box((0, 0.04, 0.32), (1.3, 0.08, 0.4), "M_IntTileBlue")
        mb.box((0, 0.56, 0.32), (1.3, 0.08, 0.4), "M_IntTileBlue")
        for (a, b, c, d) in ((-0.67, 0.0, 0.67, 0.08), (-0.67, 0.52, 0.67, 0.6), (-0.67, 0.0, -0.57, 0.6),
                             (0.57, 0.0, 0.67, 0.6)):
            mb.box_mm((a, b, 0.52), (c, d, 0.55), DARK)
        nc.box((0, 0.3, 0.46), (1.14, 0.44, 0.02), "M_IntWater")
        for k in range(2):
            with nc.at((-0.3 + 0.55 * k, 0.32, 0.56), rot=20 + 40 * k):
                nc.cylinder((0, 0, 0), 0.06, 0.08, WOOD, seg=8)
                nc.box((0.2, 0, 0.06), (0.36, 0.02, 0.02), "M_Bamboo")
        mb.box((0.45, 0.04, 0.75), (0.08, 0.08, 0.4), "M_IntMetal")                    # hot-water spout
        mb.beam((0.45, 0.04, 0.95), (0.45, 0.2, 0.9), 0.05, 0.05, "M_IntMetal")


def _bath_more(aset, mb, nc):
    rng = random.Random(91)
    pxw, pxe = PART_X - WT / 2, PART_X + WT / 2
    gy1 = BY0 + 1.6

    def mx(x, side):
        return x if side < 0 else 2 * PART_X - x

    rooms = {"men_ch": (BX0 + WT, gy1, pxw, DIV_Y), "wom_ch": (pxe, gy1, BX1 - WT, DIV_Y),
             "men_wa": (BX0 + WT, DIV_Y + WT, pxw, BY1 - WT), "wom_wa": (pxe, DIV_Y + WT, BX1 - WT, BY1 - WT)}
    for k, (key, (x0, y0, x1, y1)) in enumerate(rooms.items()):
        side = -1 if key.startswith("men") else 1
        xo = x0 if side < 0 else x1
        if key.endswith("ch"):
            clear = [(xo, -11.2, xo, -8.3), (mx(-13.2, side), y1, mx(-11.6, side), y1)]
        else:
            clear = [(xo, -7.0, xo, -5.0)]
        DT.dress_room(aset, mb, nc, x0, y0, x1, y1, BFL, CEIL_Z, style="japanese", seed=20 + k, keep_clear=clear,
                      ac=key.endswith("ch"))

    for side in (-1, 1):
        x0, y0, x1, y1 = rooms["men_ch" if side < 0 else "wom_ch"]
        # massage chair corner by the front wall (next to the drinks fridge), a coin sign over it
        _massage_chair(mb, nc, mx(-14.0, side), -10.85, 180.0, "M_IntWoodDark" if side < 0 else "M_NorenRed")
        K.poster(nc, aset, mx(-14.0, side), gy1, BFL + 1.9, 180.0, 0.42, 0.3, "M_IntPoster3", "MASSAGE 100 DP",
                 (0.2, 0.1, 0.0), 0.04)
        # noren over the glass door into the washing area
        _noren(nc, mx(-12.2, side), DIV_Y, 0.0, 1.3, BFL + 2.15, "M_NorenBlue" if side < 0 else "M_NorenRed")
        # sento clock over the vanity, a TV on top of the key lockers, a yukata basket on the cubbies
        xv = pxw if side < 0 else pxe
        aset.prop("SM_Int_WallClock", (xv, -9.1, BFL + 2.45), -90.0 if side < 0 else 90.0)
        aset.prop("SM_Int_TVB", (mx(-14.2, side), DIV_Y - 0.25, BFL + 1.85), 0.0)
        xo = (BX0 + WT + 0.225) if side < 0 else (BX1 - WT - 0.225)
        for j, yy in enumerate((-10.6, -9.6, -8.7)):
            if j != 1:
                aset.prop("SM_Int_Basket", (xo, yy, BFL + 1.79), rng.uniform(0, 30))
                nc.box((xo, yy, BFL + 1.9), (0.26, 0.2, 0.06), ("M_NorenBlue", "M_IntFabricWhite")[j % 2])
        # more house rules
        K.poster(nc, aset, mx(-11.0, side), DIV_Y, BFL + 1.95, 0.0, 0.5, 0.36, "M_IntPaper", "NO DUELING IN THE BATH",
                 (0.6, 0.05, 0.05), 0.035)
        # rush mat by the washing-area door, a laundry hamper for used towels
        nc.box((mx(-12.2, side), -8.55, BFL + 0.012), (1.2, 0.6, 0.012), "M_Bamboo")
        for j in range(6):
            nc.box((mx(-12.7 + 0.2 * j, side), -8.55, BFL + 0.02), (0.02, 0.58, 0.004), "M_IntWoodDark")
        with mb.at((mx(-11.2, side), -10.95, BFL)):
            mb.cylinder((0, 0, 0), 0.24, 0.55, "M_Bamboo", seg=12, cap_top=False)
            nc.sphere((0, 0, 0.52), 0.2, "M_IntFabricWhite", seg=8, rings=5)
    # women: a drinks vending fridge in the corner (the men have the coffee-milk fridge)
    with mb.at((mx(-14.75, 1), -11.07, BFL)), nc.at((mx(-14.75, 1), -11.07, BFL)):
        mb.box((0, 0, 0.9), (0.75, 0.6, 1.8), "M_AcademyRed")
        nc.box((0, 0.305, 1.05), (0.5, 0.01, 1.2), "M_IntGlassClear")
        nc.box((0, 0.2, 1.05), (0.5, 0.01, 1.2), "M_IntLightPanel")
        for k in range(4):
            for i in range(4):
                nc.cylinder((-0.18 + 0.12 * i, 0.25, 0.5 + k * 0.3), 0.03, 0.16,
                            ("M_IntFabricOrange", "M_IntFabricGreen", "M_IntPaper", "M_IntFabricPink")[(i + k) % 4], seg=6)
        for k in range(6):
            nc.box((0.33, 0.31, 0.7 + 0.08 * k), (0.05, 0.01, 0.04), "M_IntMetal")
    aset.text("COLD DRINKS", (mx(-14.75, 1), -11.07 + 0.33, BFL + 1.7), 180.0, size=0.07, color=(1, 1, 1))

    # ---------------- bandai: maneki-neko, a small TV, flowers, towels and shampoo for sale
    bx0, bx1 = PART_X - 1.15, PART_X + 1.15
    aset.prop("SM_Int_CatStatue", (bx0 + 0.05, -10.45, BFL + 1.09), -90.0)
    aset.prop("SM_Int_VaseB", (bx1 - 0.05, -10.5, BFL + 1.09), 0.0)
    aset.prop("SM_Int_TVB", (PART_X + 0.55, -11.15, BFL + 0.75), 200.0)
    for k in range(3):
        nc.box((PART_X - 0.6 + 0.3 * k, -10.05, BFL + 1.12 + 0.0), (0.26, 0.09, 0.06), ("M_IntFabricWhite", "M_NorenBlue",
               "M_IntFabricPink")[k])
        nc.box((PART_X - 0.6 + 0.3 * k, -10.05, BFL + 1.18), (0.24, 0.08, 0.05), ("M_NorenBlue", "M_IntFabricWhite",
               "M_IntFabricWhite")[k])
    nc.cylinder((PART_X + 0.5, -10.05, BFL + 1.09), 0.04, 0.05, "M_Gold", seg=10)               # desk bell
    nc.box((PART_X + 0.15, -10.05, BFL + 1.1), (0.22, 0.09, 0.02), "M_IntPaper")
    with mb.at((PART_X, gy1, BFL + 1.55)), nc.at((PART_X, gy1, BFL + 1.55)):
        mb.box((0, 0.1, 0.0), (1.6, 0.2, 0.03), WOOD)
        for k in range(10):
            nc.cylinder((-0.7 + 0.155 * k, 0.1, 0.015), 0.035, 0.15 + 0.03 * (k % 3),
                        ("M_IntFabricPink", "M_IntFabricGreen", "M_IntTrimWhite", "M_IntFabricBlue", "M_IntFabricOrange")[k % 5],
                        seg=8)
    K.poster(nc, aset, PART_X, gy1, BFL + 2.25, 180.0, 0.9, 0.3, "M_IntPaper", "SHAMPOO 80 DP", (0.2, 0.1, 0.05), 0.05)
    for dx, mat, txt in ((-1.75, "M_IntPoster2", "BATH RULES"), (1.75, "M_IntPoster3", "ADULTS 450 DP")):
        K.poster(nc, aset, PART_X + dx, gy1, BFL + 1.75, 180.0, 0.7, 0.95, mat, txt, (0.15, 0.08, 0.04), 0.06)
    with nc.at((PART_X, gy1 - 0.02, BFL + 2.6)):                    # noren-style banner over the booth
        nc.box((0, 0, 0), (2.4, 0.02, 0.45), "M_NorenBlue")
        nc.box((0, -0.012, 0.0), (0.5, 0.004, 0.3), "M_IntTrimWhite")

    # ---------------- washing areas
    for side in (-1, 1):
        x0, y0, x1, y1 = rooms["men_wa" if side < 0 else "wom_wa"]
        # tiled dividers between the back-wall stations, pump bottles on the ledge
        for xd in (-13.0, -11.8, -10.6):
            mb.box((mx(xd, side), y1 - 0.25, BFL + 0.9), (0.08, 0.5, 0.6), "M_IntTileBlue")
        for xs in (-13.6, -12.4, -11.2, -10.0):
            for j, m in enumerate(("M_IntTrimWhite", "M_IntFabricBlue")):
                xb = mx(xs + 0.22 + 0.09 * j, side)
                nc.cylinder((xb, y1 - 0.12, BFL + 0.6), 0.035, 0.18, m, seg=8)
                nc.cylinder((xb, y1 - 0.12, BFL + 0.78), 0.008, 0.05, "M_Black", seg=4)
                nc.box((xb, y1 - 0.15, BFL + 0.83), (0.01, 0.06, 0.01), "M_Black")
            nc.box((mx(xs - 0.2, side), y1 - 0.12, BFL + 0.61), (0.12, 0.08, 0.02), "M_IntFabricWhite")  # face towel
        # the pouring basin and one more station on the divider, a potted bamboo by the side door
        _kakeyu(mb, nc, mx(-14.2, side), y0, rng)
        with mb.at((mx(-10.4, side), y0, 0.0), rot=180.0), nc.at((mx(-10.4, side), y0, 0.0), rot=180.0):
            _wash_station(mb, nc, aset, 0.0, 0.0, rng)
        aset.prop("SM_Int_PottedPlant", (mx(-14.7, side), y0 + 0.04, BFL + 0.55), rng.uniform(0, 360))
        # towel bar by the side door, a sento clock + rules over the glass door
        xw = x0 if side < 0 else x1
        nc.box((xw - side * 0.05, -7.3, BFL + 1.6), (0.04, 0.8, 0.03), "M_IntMetal")
        for j in range(2):
            nc.box((xw - side * 0.07, -7.5 + 0.4 * j, BFL + 1.35), (0.03, 0.32, 0.5), ("M_IntFabricWhite", "M_NorenBlue")[j])
        aset.prop("SM_Int_WallClock", (mx(-15.25, side), y0, BFL + 1.5), 180.0)
        K.poster(nc, aset, mx(-14.2, side), y0, BFL + 1.6, 180.0, 0.7, 0.45, "M_IntPoster2", "RINSE FIRST, THEN SOAK",
                 (1, 1, 1), 0.04)
        for k in range(3):   # stacked stools by the door
            stool(mb, (mx(-11.15, side), y0 + 0.4, BFL + 0.33 * k), 8.0 * k)
        # a row of little local adverts over the mirrors (a sento tradition), a drain grate, a duckboard
        ads = (("CARD SHOP", "M_IntPoster1"), ("ISLAND CLINIC", "M_IntPaper"), ("TOME BAKERY", "M_IntPoster3"),
               ("DUEL DISK REPAIR", "M_IntPoster2"), ("FERRY TIMES", "M_IntPaper"), ("SEA VIEW INN", "M_IntPoster4"))
        for j, xa in enumerate((-14.4, -13.6, -12.8, -12.0, -11.2, -10.4)):
            txt, m = ads[(j + (side > 0) * 2) % len(ads)]
            K.poster(nc, aset, mx(xa, side), y1, BFL + 1.85, 0.0, 0.7, 0.32, m, txt,
                     (0.15, 0.08, 0.05) if m == "M_IntPaper" else (1, 1, 1), 0.045)
        for j, xa in enumerate((-15.1, -11.0)):
            txt, m = ads[(j + 3 + (side > 0)) % len(ads)]
            K.poster(nc, aset, mx(xa, side), y0, BFL + 2.45, 180.0, 0.7, 0.32, m, txt,
                     (0.15, 0.08, 0.05) if m == "M_IntPaper" else (1, 1, 1), 0.045)
        # slatted ranma (ventilation transom) above the rail: steam escapes into the roof space
        for (p0, p1) in (((x1, y1), (x0, y1)), ((x0, y1), (x0, y0)) if side < 0 else ((x1, y0), (x1, y1)),
                         ((x0, y0), (x1, y0))):
            L, _, _, yaw = K._frame2d(p0, p1)
            with nc.at((p0[0], p0[1], BFL + 2.32), rot=yaw):
                nc.box((L / 2, 0.015, 0.0), (L, 0.03, 0.04), DARK)
                nc.box((L / 2, 0.015, 0.56), (L, 0.03, 0.04), DARK)
                nc.box((L / 2, 0.004, 0.28), (L, 0.008, 0.52), "M_IntWoodDark")
                for j in range(int(L / 0.12)):
                    nc.box((0.06 + 0.12 * j, 0.025, 0.28), (0.025, 0.02, 0.52), WOOD)
        a_, b_ = sorted((mx(-14.6, side), mx(-9.7, side)))
        nc.box_mm((a_, y1 - 0.5, BFL + 0.003), (b_, y1 - 0.36, BFL + 0.009), "M_IntMetal")
        for j in range(int((b_ - a_) / 0.06)):
            nc.box((a_ + 0.03 + 0.06 * j, y1 - 0.43, BFL + 0.0095), (0.02, 0.12, 0.002), "M_Black")
        for j in range(8):
            nc.box((mx(-12.2, side) - 0.42 + 0.12 * j, y0 + 0.5, BFL + 0.02), (0.08, 0.7, 0.025), WOOD)

    # ---------------- rest pavilion: cushions, low table with tea and a duel in progress, lantern, sandals
    ax, ay, z = 19.0, 13.5, DECK + 0.08
    for k in range(4):
        nc.box((17.95 + 0.75 * k, ay + 1.35, DECK + 0.47), (0.5, 0.42, 0.06), ("M_RedFelt", "M_NorenBlue")[k % 2])
    for k in range(3):
        nc.box((ax + 1.35, 12.75 + 0.7 * k, DECK + 0.47), (0.42, 0.5, 0.06), ("M_NorenBlue", "M_RedFelt")[k % 2])
    with mb.at((18.7, 13.4, z)):
        mb.box((0, 0, 0.38), (1.0, 0.65, 0.05), WOOD)
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * 0.42, sy * 0.26, 0.18), (0.06, 0.06, 0.36), DARK)
    aset.prop("SM_Int_TeaSet", (18.45, 13.45, z + 0.405), 15.0)
    DT.card_spread(nc, 18.95, 13.3, z + 0.406, 90.0, 5, 3)
    DT.deck_box(nc, 19.05, 13.6, z + 0.405, 30.0, "M_IntFabricRed")
    for k in range(2):
        nc.box((18.0 + 0.6 * k, 12.4, z + 0.006), (0.4, 0.4, 0.04), ("M_RedFelt", "M_NorenBlue")[k])
    for (x, y, a) in ((17.6, 12.0, 20.0), (20.6, 12.2, -30.0)):                                   # geta
        with nc.at((x, y, z), rot=a):
            for s in (-1, 1):
                nc.box((s * 0.07, 0, 0.05), (0.1, 0.24, 0.025), WOOD)
                nc.box((s * 0.07, -0.06, 0.02), (0.1, 0.02, 0.04), DARK)
                nc.box((s * 0.07, 0.06, 0.02), (0.1, 0.02, 0.04), DARK)
    for (x, y, a) in ((19.9, 14.85, 30.0), (20.35, 13.9, -60.0)):                                  # uchiwa fans
        with nc.at((x, y, DECK + 0.5), rot=a):
            nc.cylinder((0, 0, 0), 0.13, 0.006, "M_IntPoster1", seg=12)
            nc.box((0.2, 0, 0.003), (0.16, 0.02, 0.006), "M_Bamboo")
    nc.box((17.5, 14.85, DECK + 0.52), (0.35, 0.28, 0.08), "M_NorenBlue")                       # folded yukata
    nc.cylinder((ax, ay, DECK + 2.7), 0.01, 0.5, "M_DarkMetal", seg=4)                          # hanging lantern
    nc.lathe([(0.1, -0.2), (0.17, -0.1), (0.18, 0.05), (0.14, 0.17), (0.08, 0.2)], "M_ShojiPaper", seg=10,
             center=(ax, ay, DECK + 2.45))
    nc.cylinder((ax, ay, DECK + 2.24), 0.09, 0.03, "M_Black", seg=10)
    aset.light((ax, ay, DECK + 2.3), (1.0, 0.8, 0.55), 900.0, 6.0)
    K.camera(aset, "pavilion", (17.3, 11.9, DECK + 1.6), (20.2, 14.9, DECK + 0.5), 16.0)


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
        mb.box((x, y + 0.05, BFL + 1.25), (0.5, 0.04, 0.6), "M_IntMetal")          # mirror (not a window)
        mb.box((x, y + 0.04, BFL + 1.25), (0.56, 0.03, 0.66), "M_IntTrimWhite")
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
    _bath_interior(aset, aset.mesh("Onsen_Interior"), aset.mesh("Onsen_Interior_NoCol"))
    _bath_more(aset, aset.mesh("Onsen_Interior"), aset.mesh("Onsen_Interior_NoCol"))
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
