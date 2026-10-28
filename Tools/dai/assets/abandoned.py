"""
Abandoned Dorm - the old "Special Dorm" deep in the eastern jungle.

A once-grand three storey stone dormitory (40 x 18 m) with a central square
clock tower, now rotting: holed slate roof with exposed rafters, boarded and
shuttered windows, crooked chimneys, ivy, a sagging porch and a walkable,
creepy entrance hall behind the open front door.

Local space: origin = pad centre at ground level, front (door) faces -Y.
The forest trail arrives at about (0, -55); the gate sits at (0, -38).
"""

import math
import random

from . import AssetSet
from .. import palette

palette.register({
    "M_OldStoneTrim":   dict(kind="opaque", color=(0.43, 0.42, 0.44), rough=0.9, detail="Concrete", tiling=0.5),
    "M_DarkVoid":       dict(kind="opaque", color=(0.012, 0.010, 0.016), rough=1.0, detail=None),
    "M_DarkWallpaper":  dict(kind="opaque", color=(0.24, 0.17, 0.27), rough=0.95, detail="Grunge", tiling=0.5),
    "M_TarnishedGold":  dict(kind="opaque", color=(0.46, 0.36, 0.17), rough=0.45, metallic=0.8, detail="Grunge", tiling=1.0),
    "M_PortraitCanvas": dict(kind="opaque", color=(0.17, 0.11, 0.15), rough=0.9, detail="Grunge", tiling=1.0),
    "M_PortraitFace":   dict(kind="opaque", color=(0.46, 0.40, 0.42), rough=0.9, detail=None),
    "M_GhostGlow":      dict(kind="emissive", color=(0.62, 0.42, 1.00), strength=8.0),
    "M_RottenCurtain":  dict(kind="foliage", color=(0.17, 0.05, 0.09), rough=0.95, detail=None),
})

STONE = "M_OldStone"
TRIM = "M_OldStoneTrim"
WALLP = "M_DarkWallpaper"
ROT = "M_RottenWood"
BOARD = "M_Boards"
RUST = "M_RustMetal"
VOID = "M_DarkVoid"

# ---------------------------------------------------------------- dimensions
FL = 0.6                      # ground floor level (plinth top)
EAVE = 11.4                   # wall top
ROOF_Z = 11.75                # roof underside at the eave line
PITCH = 30.0
TAN = math.tan(math.radians(PITCH))
COS = math.cos(math.radians(PITCH))
X0, X1, Y0, Y1 = -20.0, 20.0, -8.0, 10.0
EAVE_YF, EAVE_YB, RIDGE_Y = -8.6, 10.6, 1.0
RUN = RIDGE_Y - EAVE_YF
RIDGE_Z = ROOF_Z + RUN * TAN
VERGE = 0.6
TX, TY0, TY1, TTOP = 4.6, -11.0, -2.0, 21.5     # tower (outer)
HX, HY0, HY1, HZ1 = 4.0, -10.4, 4.0, 7.8        # entrance hall cavity
GAL_Y, GAL_Z = 1.6, 4.2                          # gallery front edge / floor

FLOOR_BANDS = (4.4, 7.85)
WIN_ROWS = ((1.5, 2.2), (5.0, 2.0), (8.6, 1.8))  # (sill z, height)


# ---------------------------------------------------------------- helpers
def rbox(mb, center, size, mat, yaw=0.0, pitch=0.0, roll=0.0, mats=None):
    with mb.at(center, rot=yaw, rot_y=pitch, rot_x=roll):
        mb.box((0, 0, 0), size, mat, mats=mats)


def leaf_card(mb, center, size, mat, rng, yaw=0.0):
    """Irregular hexagonal leaf cluster facing local -Y."""
    s = size / 2
    with mb.at(center, rot=yaw, rot_y=rng.uniform(0, 60), rot_x=rng.uniform(-25, 25)):
        pts = []
        for i in range(6):
            a = math.tau * i / 6 + 0.3
            r = s * rng.uniform(0.75, 1.1)
            pts.append((math.cos(a) * r, 0.0, math.sin(a) * r))
        # CCW seen from -Y means CCW in (x, z) -> reverse of the angle order in (x, z)? angle grows x->z
        mb.poly(pts, mat)


def window(mb, nc, u, z0, w, h, style, rng, dark=True, hood="key"):
    """Window in a facade frame (wall face at y=0, outside = -y, u along the facade)."""
    zc = z0 + h / 2
    if dark:
        mb.box((u, -0.02, zc), (w, 0.04, h), VOID, skip=("+y",))
    for s in (-1, 1):
        mb.box((u + s * (w / 2 + 0.1), -0.11, zc), (0.2, 0.22, h + 0.02), TRIM, skip=("+y",))
    mb.box((u, -0.15, z0 - 0.08), (w + 0.6, 0.3, 0.16), TRIM, skip=("+y",))
    if hood == "key":
        mb.box((u, -0.13, z0 + h + 0.12), (w + 0.5, 0.26, 0.24), TRIM, skip=("+y",))
        mb.box((u, -0.17, z0 + h + 0.14), (0.28, 0.34, 0.36), TRIM, skip=("+y",))
    elif hood == "pediment":
        mb.box((u, -0.13, z0 + h + 0.1), (w + 0.6, 0.26, 0.2), TRIM, skip=("+y",))
        a = (w + 0.8) / 2
        zb = z0 + h + 0.22
        mb.beam((u - a, -0.15, zb), (u + 0.02, -0.15, zb + 0.5), 0.3, 0.16, TRIM)
        mb.beam((u + a, -0.15, zb), (u - 0.02, -0.15, zb + 0.5), 0.3, 0.16, TRIM)
    elif hood == "arch":
        mb.arch((u, -0.13, z0 + h - w / 2), w, w, 0.26, 0.18, TRIM, seg=8)
        if dark:
            r = w / 2
            pts = [(u + math.cos(math.pi * k / 8) * r, -0.02, z0 + h + math.sin(math.pi * k / 8) * r) for k in range(9)]
            mb.poly(pts, VOID)

    if style == "boarded":
        n = rng.randint(3, 5)
        for i in range(n):
            zz = z0 + h * (i + 0.5) / n + rng.uniform(-0.1, 0.1)
            rbox(mb, (u + rng.uniform(-0.1, 0.1), -0.27, zz), (w + 0.5, 0.05, rng.uniform(0.18, 0.27)),
                 BOARD, pitch=rng.uniform(-12, 12))
    elif style == "cross":
        ang = math.degrees(math.atan2(h, w))
        for k, s in enumerate((-1, 1)):
            rbox(mb, (u, -0.27 - 0.05 * k, zc), (math.hypot(w, h) + 0.1, 0.05, 0.22), BOARD, pitch=s * ang)
        rbox(mb, (u, -0.37, zc + rng.uniform(-0.4, 0.4)), (w + 0.5, 0.05, 0.22), BOARD,
             pitch=rng.uniform(-6, 6))
    elif style == "shutter":
        lw = w / 2 + 0.05
        # one leaf open flat against the wall, the other hanging from its top hinge
        side = rng.choice((-1, 1))
        mb.box((u + side * (w / 2 + 0.22 + lw / 2), -0.25, zc), (lw, 0.05, h), ROT)
        for k in range(3):
            mb.box((u + side * (w / 2 + 0.22 + lw / 2), -0.28, z0 + h * (k + 0.5) / 3), (lw, 0.02, 0.06), ROT)
        hx = u - side * (w / 2 + 0.22 + lw)
        with mb.at((hx, -0.3, z0 + h), rot_y=side * rng.uniform(18, 32)):
            mb.box((side * lw / 2, 0, -h / 2), (lw, 0.05, h), ROT)
        # broken glass
        _shards(mb, u, z0, w, h, rng)
    elif style == "closed":
        lw = w / 2 - 0.01
        for s in (-1, 1):
            if rng.random() < 0.25:
                continue  # leaf missing
            mb.box((u + s * (lw / 2 + 0.01), -0.25, zc), (lw, 0.05, h), ROT)
            for k in range(4):
                mb.box((u + s * (lw / 2 + 0.01), -0.28, z0 + h * (k + 0.5) / 4), (lw - 0.06, 0.02, 0.05), ROT)
    elif style == "broken":
        _shards(mb, u, z0, w, h, rng)
        if rng.random() < 0.5:
            return
        # tattered curtain hanging inside
        n = rng.randint(3, 5)
        side = rng.choice((-1, 1))
        for i in range(n):
            sw = w * 0.45 / n
            x = u + side * (w / 2 - sw * (i + 0.5))
            ln = h * rng.uniform(0.45, 0.95)
            nc.box((x, -0.05, z0 + h - ln / 2), (sw * 0.95, 0.02, ln), "M_RottenCurtain")


def _shards(mb, u, z0, w, h, rng):
    x0, x1, za, zb = u - w / 2, u + w / 2, z0, z0 + h
    y = -0.05
    s1, s2 = w * rng.uniform(0.25, 0.45), h * rng.uniform(0.15, 0.3)
    mb.poly([(x0, y, za), (x0 + s1, y, za), (x0, y, za + s2)], "M_Glass")
    mb.poly([(x1, y, zb), (x1 - s1 * 0.8, y, zb), (x1, y, zb - s2 * 1.3)], "M_Glass")
    mb.poly([(x0, y, zb), (x0, y, zb - s2), (x0 + s1 * 0.6, y, zb)], "M_Glass")


def facade_trim(mb, origin, yaw, length, courses=(), cornice=None, quoins=(0.6, 11.4), q_ends=(True, True)):
    with mb.at(origin, rot=yaw):
        for z in courses:
            mb.box((length / 2, -0.09, z), (length + 0.32, 0.18, 0.2), TRIM, skip=("+y",))
        if cornice is not None:
            mb.box((length / 2, -0.225, cornice - 0.25), (length + 0.86, 0.45, 0.5), TRIM, skip=("+y",))
            mb.box((length / 2, -0.13, cornice - 0.65), (length + 0.5, 0.26, 0.3), TRIM, skip=("+y",))
        if quoins:
            z, i = quoins[0], 0
            while z < quoins[1] - 0.3:
                hq = 0.45
                wq = 0.62 if i % 2 == 0 else 0.38
                for end, on in ((0.0, q_ends[0]), (length, q_ends[1])):
                    if not on:
                        continue
                    sg = 1 if end == 0.0 else -1
                    mb.box((end + sg * (wq / 2 - 0.06), -0.04, z + hq / 2), (wq, 0.08, hq - 0.05), TRIM,
                           skip=("+y",))
                z += hq
                i += 1


def rubble(mb, center, radius, n, rng, mats=(STONE, TRIM), zc=0.0, size=(0.15, 0.55)):
    cx, cy = center[0], center[1]
    for _ in range(n):
        a = rng.uniform(0, math.tau)
        r = radius * math.sqrt(rng.random())
        s = rng.uniform(*size)
        rbox(mb, (cx + math.cos(a) * r, cy + math.sin(a) * r, zc + s * 0.25),
             (s * rng.uniform(0.8, 1.6), s * rng.uniform(0.7, 1.3), s * rng.uniform(0.5, 0.9)),
             rng.choice(mats), yaw=rng.uniform(0, 180), pitch=rng.uniform(-20, 20), roll=rng.uniform(-20, 20))


def planks(mb, center, radius, n, rng, mat=ROT, zc=0.0, length=(1.2, 3.0)):
    cx, cy = center[0], center[1]
    for i in range(n):
        a = rng.uniform(0, math.tau)
        r = radius * math.sqrt(rng.random())
        ln = rng.uniform(*length)
        rbox(mb, (cx + math.cos(a) * r, cy + math.sin(a) * r, zc + 0.05 + 0.06 * i),
             (ln, rng.uniform(0.18, 0.3), 0.05), mat, yaw=rng.uniform(0, 180), pitch=rng.uniform(-8, 8))


# ---------------------------------------------------------------- building shell
def _shell(mb):
    # plinths down to -4 m (terrain slopes away at the pad edge)
    mb.box_mm((X0 - 0.4, Y0 - 0.4, -4.0), (X1 + 0.4, Y1 + 0.4, FL), STONE, mats={"+z": TRIM})
    mb.box_mm((-TX - 0.4, TY0 - 0.4, -4.0), (TX + 0.4, Y0 - 0.4, FL), STONE, mats={"+z": TRIM})
    # solid wings + centre (their faces towards the hall cavity are wallpapered)
    mb.box_mm((X0, Y0, FL), (-HX, Y1, EAVE), STONE, mats={"+x": WALLP, "+z": VOID})
    mb.box_mm((HX, Y0, FL), (X1, Y1, EAVE), STONE, mats={"-x": WALLP, "+z": VOID})
    mb.box_mm((-HX, HY1, FL), (HX, Y1, EAVE), STONE, mats={"-y": WALLP, "+z": VOID})
    mb.box_mm((-HX, TY1, HZ1), (HX, HY1, EAVE), STONE, mats={"-z": ROT, "+z": VOID})
    # wall plates closing the gap between wall top and roof underside
    zp = ROOF_Z + (Y0 - EAVE_YF) * TAN
    mb.box_mm((X0 + 0.01, Y0, EAVE), (X1 - 0.01, Y0 + 0.5, zp), STONE)
    mb.box_mm((X0 + 0.01, Y1 - 0.5, EAVE), (X1 - 0.01, Y1, zp), STONE)
    # gable walls
    for sx in (-1, 1):
        x = sx * X1
        pts = [(x, Y0, EAVE), (x, Y1, EAVE), (x, Y1, zp), (x, RIDGE_Y, RIDGE_Z - 0.02), (x, Y0, zp)]
        mb.poly(pts if sx > 0 else list(reversed(pts)), STONE)
        # attic oculus
        with mb.at((x, RIDGE_Y, 14.0), rot=90 if sx > 0 else -90):
            with mb.at((0, 0, 0), rot_x=90):
                mb.cylinder((0, 0, 0), 0.75, 0.06, VOID, seg=12)
                mb.torus((0, 0, 0.08), 0.85, 0.12, TRIM, seg=14, tube_seg=6)
            for k in range(2):
                rbox(mb, (0, -0.25, 0.25 - 0.45 * k), (1.7, 0.05, 0.2), BOARD, pitch=(-14, 9)[k])
    # tower: lower hollow walls around the hall, solid above
    door = dict(u=TX, w=2.4, z0=0.0, z1=3.2)
    wins = [dict(u=TX - 3.0, w=1.2, z0=1.0, z1=3.4), dict(u=TX + 3.0, w=1.2, z0=1.0, z1=3.4),
            dict(u=TX - 3.0, w=1.2, z0=5.0, z1=6.8), dict(u=TX + 3.0, w=1.2, z0=5.0, z1=6.8),
            dict(u=TX, w=1.6, z0=5.1, z1=6.8)]
    mb.wall((-TX, TY0), (TX, TY0), FL, HZ1 - FL, 0.6, STONE, openings=[door] + wins, inner_mat=WALLP)
    mb.wall((-TX, Y0), (-TX, HY0), FL, HZ1 - FL, 0.6, STONE, inner_mat=WALLP)
    mb.wall((TX, HY0), (TX, Y0), FL, HZ1 - FL, 0.6, STONE, inner_mat=WALLP)
    mb.box_mm((-TX, TY0, HZ1), (TX, TY1, TTOP), STONE, mats={"-z": ROT})


def _facades(mb, nc, rng):
    st_ground = ["boarded", "boarded", "cross", "closed"]
    st_upper = ["boarded", "cross", "shutter", "closed", "broken", "broken", "shutter"]
    bays_wing = [2.3, 5.9, 9.5, 13.1]
    bays_side = [2.4, 6.8, 11.2, 15.6]
    bays_back = [2.0 + 4.0 * i for i in range(10)]

    def windows(origin, yaw, bays, skip=()):
        with mb.at(origin, rot=yaw), nc.at(origin, rot=yaw):
            for fi, (z0, h) in enumerate(WIN_ROWS):
                for bi, u in enumerate(bays):
                    if (fi, bi) in skip:
                        continue
                    st = rng.choice(st_ground if fi == 0 else st_upper)
                    window(mb, nc, u, z0, 1.25, h, st, rng)

    windows((X0, Y0), 0, bays_wing)
    windows((TX, Y0), 0, bays_wing)
    windows((X1, Y0), 90, bays_side)
    windows((X0, Y1), -90, bays_side)
    windows((X1, Y1), 180, bays_back, skip={(0, 4), (0, 5)})
    # trims
    for org, yaw, ln, qe in (((X0, Y0), 0, X1 - TX, (True, False)), ((TX, Y0), 0, X1 - TX, (False, True)),
                             ((X1, Y0), 90, Y1 - Y0, (True, True)), ((X1, Y1), 180, X1 - X0, (True, True)),
                             ((X0, Y1), -90, Y1 - Y0, (True, True))):
        facade_trim(mb, org, yaw, ln, courses=FLOOR_BANDS, cornice=ROOF_Z, q_ends=qe)
    # back door (closed, boarded)
    with mb.at((0, Y1, 0), rot=180):
        mb.box((0, -0.03, FL + 1.5), (2.2, 0.06, 3.0), VOID, skip=("+y",))
        for s in (-1, 1):
            mb.box((s * 0.55, -0.1, FL + 1.5), (1.05, 0.1, 2.95), "M_DarkWood")
        for k in range(3):
            rbox(mb, (0, -0.2, FL + 0.7 + k * 0.9), (2.6, 0.05, 0.24), BOARD, pitch=rng.uniform(-10, 10))
        window(mb, nc, 0, FL, 2.2, 3.0, "none", rng, dark=False, hood="pediment")
        mb.stairs((0, -2.0, 0.0), 90, 3.0, 3, 0.2, 0.5, STONE)
    # sagging, broken gutter on the front eave
    gz = ROOF_Z - 0.05
    mb.box_mm((X0 - 0.6, EAVE_YF - 0.3, gz - 0.15), (-10.0, EAVE_YF - 0.12, gz), RUST)
    mb.beam((-10.0, EAVE_YF - 0.21, gz - 0.07), (-7.4, EAVE_YF - 0.6, gz - 2.2), 0.16, 0.16, RUST)
    mb.box_mm((10.5, EAVE_YF - 0.3, gz - 0.15), (X1 + 0.6, EAVE_YF - 0.12, gz), RUST)
    mb.box_mm((X1 - 0.3, EAVE_YF - 0.12, FL), (X1 - 0.12, EAVE_YF + 0.06, gz), RUST)  # downpipe


def _roof(mb, rng):
    """Two slate slopes (individual staggered slates), ragged holes with exposed rafters, dormers."""
    slope_len = RUN / COS
    rows = 15
    rh = slope_len / rows
    xl, xr = X0 - VERGE, X1 + VERGE
    sw = 0.85
    # (f0, f1, x0, x1): f = fraction of the slope length, x in world metres
    holes = {"front": [(0.2, 0.68, -10.5, -6.0), (0.55, 0.92, 8.0, 10.6)],
             "back": [(0.1, 0.62, 4.0, 9.8), (0.45, 0.9, -8.5, -3.8), (0.05, 0.3, -12.5, -11.0)]}
    dormers = {"front": [(-13.5, 0.22, "boarded"), (13.5, 0.22, "broken")],
               "back": [(-15.0, 0.22, "broken"), (15.0, 0.22, "boarded")]}
    dorm_h, dorm_w = 2.2, 1.9
    dorm_f = (dorm_h / TAN) / RUN
    for slope in ("front", "back"):
        sgn = 1 if slope == "front" else -1
        origin = (0, EAVE_YF if slope == "front" else EAVE_YB, ROOF_Z)
        yaw = 0 if slope == "front" else 180
        hl = []
        for (f0, f1, a, b) in holes[slope]:
            a, b = sorted((sgn * a, sgn * b))
            hl.append((f0, f1, a, b))
        dl = [(sgn * xc, f0) for (xc, f0, _) in dormers[slope]]
        with mb.at(origin, rot=yaw, rot_x=PITCH):
            for r in range(rows):
                f_lo, f_hi = r / rows, (r + 1) / rows
                cuts = []
                y_end = EAVE_YF + f_hi * RUN
                if slope == "front" and y_end < TY1 + 0.3:
                    cuts.append((-TX + 0.05, TX - 0.05))
                for (f0, f1, a, b) in hl:
                    if f0 <= (f_lo + f_hi) / 2 <= f1:
                        mid = ((f_lo + f_hi) / 2 - f0) / max(1e-3, f1 - f0)
                        shrink = (b - a) * 0.3 * abs(mid - 0.5) * 2
                        cuts.append((a + shrink * rng.uniform(0.3, 1.0) + rng.uniform(-0.3, 0.3),
                                     b - shrink * rng.uniform(0.3, 1.0) + rng.uniform(-0.3, 0.3)))
                for (xc, f0) in dl:
                    if f0 - 0.01 <= f_lo and f_hi <= f0 + dorm_f + 0.08:
                        cuts.append((xc - dorm_w / 2 + 0.05, xc + dorm_w / 2 - 0.05))
                cuts.sort()
                segs, x = [], xl
                for a, b in cuts:
                    if a > x:
                        segs.append((x, a))
                    x = max(x, b)
                if x < xr:
                    segs.append((x, xr))
                top = (r == rows - 1)
                with mb.at((0, r * rh, 0), rot_x=-2.0):
                    for a, b in segs:
                        # stagger slates; the first/last slate of a run is cut to fit
                        x = xl + (sw / 2 if r % 2 else 0.0)
                        edges = [a]
                        while x < b:
                            if x > a + 0.12:
                                edges.append(x)
                            x += sw
                        edges.append(b)
                        for k in range(len(edges) - 1):
                            x0, x1 = edges[k] + 0.015, edges[k + 1] - 0.015
                            if x1 - x0 < 0.1:
                                continue
                            if rng.random() < 0.012 and 2 < r < rows - 2:
                                continue  # single missing slate
                            jz = rng.uniform(-0.012, 0.012)
                            mb.box(((x0 + x1) / 2, (rh + 0.1) / 2, 0.06 + jz), (x1 - x0, rh + 0.1, 0.12),
                                   "M_OldRoof", skip=() if top else ("-z", "+y"))
            # exposed rafters / laths in the holes
            for (f0, f1, a, b) in hl:
                ya = max(0.0, f0 * slope_len - 0.5)
                yb = min(slope_len, f1 * slope_len + 0.5)
                x = a - 0.2
                while x < b + 0.3:
                    if rng.random() < 0.85:
                        broken = rng.random() < 0.25
                        yy1 = yb if not broken else ya + (yb - ya) * rng.uniform(0.4, 0.7)
                        mb.box((x, (ya + yy1) / 2, -0.12), (0.12, yy1 - ya, 0.2), ROT)
                    x += 0.6
                yy = ya + 0.4
                while yy < yb - 0.3:
                    if rng.random() < 0.6:
                        mb.box(((a + b) / 2 + rng.uniform(-0.5, 0.5), yy, 0.0),
                               (rng.uniform(0.5, 0.9) * (b - a), 0.06, 0.04), ROT)
                    yy += 0.75
                for _ in range(5):   # loose slates hanging over the edge
                    rbox(mb, (rng.choice((a, b)) + rng.uniform(-0.3, 0.3), rng.uniform(ya + 0.5, yb - 0.5), 0.1),
                         (0.8, 0.7, 0.04), "M_OldRoof", yaw=rng.uniform(-30, 30), roll=rng.uniform(-15, 15))
        # dormers (world space)
        for (xc, f0, style) in dormers[slope]:
            yf = (EAVE_YF + f0 * RUN) if slope == "front" else (EAVE_YB - f0 * RUN)
            zf = ROOF_Z + f0 * RUN * TAN
            depth = dorm_h / TAN + 0.6
            with mb.at((xc, yf, zf), rot=yaw):
                mb.box((0, depth / 2, dorm_h / 2 - 0.15), (dorm_w, depth, dorm_h + 0.3), STONE)
                mb.box((0, -0.02, 0.95), (1.0, 0.04, 1.3), VOID, skip=("+y",))
                for s in (-1, 1):
                    mb.box((s * 0.6, -0.08, 0.95), (0.2, 0.16, 1.4), TRIM, skip=("+y",))
                mb.box((0, -0.1, 0.22), (1.5, 0.2, 0.14), TRIM, skip=("+y",))
                mb.gable_roof((0, depth / 2 - 0.2, dorm_h), dorm_w, depth + 0.4, 0.95, "M_OldRoof", overhang=0.22,
                              thick=0.14, gable_mat=TRIM, ridge_axis="y")
                if style == "boarded":
                    for k in range(3):
                        rbox(mb, (0, -0.2, 0.55 + k * 0.4), (1.35, 0.05, 0.2), BOARD, pitch=rng.uniform(-14, 14))
                else:
                    _shards(mb, 0.0, 0.3, 1.0, 1.3, rng)

    # ridge cap (with a gap) and barge boards
    mb.box_mm((xl, RIDGE_Y - 0.28, RIDGE_Z + 0.05), (-6.0, RIDGE_Y + 0.28, RIDGE_Z + 0.3), "M_OldRoof")
    mb.box_mm((-4.5, RIDGE_Y - 0.28, RIDGE_Z + 0.05), (xr, RIDGE_Y + 0.28, RIDGE_Z + 0.3), "M_OldRoof")
    for sx in (-1, 1):
        x = sx * (X1 + VERGE + 0.04)
        mb.beam((x, EAVE_YF - 0.05, ROOF_Z - 0.05), (x, RIDGE_Y, RIDGE_Z + 0.2), 0.08, 0.38, ROT)
        mb.beam((x, EAVE_YB + 0.05, ROOF_Z - 0.05), (x, RIDGE_Y, RIDGE_Z + 0.2), 0.08, 0.38, ROT)
    # chimneys: gable-end stacks and two through the back slope (one collapsed)
    for (x, y, zb, h, lean, broken) in ((-18.9, RIDGE_Y + 2.2, EAVE, 9.4, (5.0, -3.0), False),
                                         (18.9, RIDGE_Y + 2.2, EAVE, 8.6, (-8.0, 3.0), False),
                                         (-10.0, 5.2, 14.0, 4.6, (4.0, 7.0), False),
                                         (10.0, 5.2, 14.0, 2.6, (0.0, 0.0), True)):
        with mb.at((x, y, zb), rot_y=lean[0], rot_x=lean[1]):
            mb.box((0, 0, h / 2), (1.1, 1.5, h), STONE)
            if not broken:
                mb.box((0, 0, h - 0.5), (1.35, 1.75, 0.18), TRIM)
                mb.box((0, 0, h + 0.1), (1.3, 1.7, 0.2), TRIM)
                mb.cylinder((0, -0.35, h + 0.2), 0.18, 0.55, RUST, seg=8)
                mb.cylinder((0, 0.35, h + 0.2), 0.18, 0.4, RUST, seg=8, radius_top=0.14)
            else:
                rbox(mb, (0.25, 0.2, h + 0.15), (0.6, 0.9, 0.3), STONE, yaw=12, pitch=18)
        if broken:
            rubble(mb, (x + 1.2, y - 1.6), 1.0, 8, rng, zc=ROOF_Z + (EAVE_YB - (y - 1.6)) * TAN, size=(0.15, 0.35))


def _tower(mb, roof, nc, rng):
    # facade windows on the tower (front, sides, back) - upper storeys
    with mb.at((-TX, TY0), rot=0), nc.at((-TX, TY0), rot=0):
        # lower front: real openings (boards over them), door surround
        window(mb, nc, 1.6, FL + 1.0, 1.2, 2.4, "boarded", rng, dark=False)
        window(mb, nc, 7.6, FL + 1.0, 1.2, 2.4, "cross", rng, dark=False)
        window(mb, nc, 1.6, FL + 5.0, 1.2, 1.8, "shutter", rng, dark=False)
        window(mb, nc, 7.6, FL + 5.0, 1.2, 1.8, "broken", rng, dark=False)
        window(mb, nc, TX, FL + 5.1, 1.6, 1.7, "none", rng, dark=False)
        rbox(mb, (TX + 0.1, -0.3, FL + 5.9), (2.1, 0.05, 0.22), BOARD, pitch=-16)
        # door surround + pediment + name plaque
        for s in (-1, 1):
            mb.box((TX + s * 1.38, -0.15, FL + 1.6), (0.36, 0.3, 3.24), TRIM, skip=("+y",))
        mb.box((TX, -0.17, FL + 3.4), (3.2, 0.34, 0.4), TRIM, skip=("+y",))
        mb.beam((TX - 1.7, -0.2, FL + 3.6), (TX + 0.02, -0.2, FL + 4.1), 0.4, 0.2, TRIM)
        mb.beam((TX + 1.7, -0.2, FL + 3.6), (TX - 0.02, -0.2, FL + 4.1), 0.4, 0.2, TRIM)
        # third level + upper tower
        window(mb, nc, 2.4, 8.6, 1.2, 1.8, "closed", rng)
        window(mb, nc, 6.8, 8.6, 1.2, 1.8, "boarded", rng)
        for u in (3.6, 5.6):
            window(mb, nc, u, 12.6, 0.8, 2.2, "broken" if u < 4 else "boarded", rng, hood="arch")
        # clock face (stopped, one hand gone)
        with mb.at((TX, 0, 17.6), rot_x=90):
            mb.cylinder((0, 0, 0), 1.55, 0.2, TRIM, seg=20)
            mb.cylinder((0, 0, 0.2), 1.3, 0.04, "M_PortraitFace", seg=20)
            for k in range(12):
                a = math.tau * k / 12
                rbox(mb, (math.cos(a) * 1.12, math.sin(a) * 1.12, 0.26), (0.2 if k % 3 else 0.32, 0.07, 0.04),
                     "M_Black", yaw=math.degrees(a))
            rbox(mb, (0.28, -0.32, 0.3), (0.12, 0.85, 0.05), "M_Black", yaw=-40)
            mb.cylinder((0, 0, 0.24), 0.1, 0.1, RUST, seg=8)
    facade_trim(mb, (-TX, TY0), 0, 2 * TX, courses=(7.85, 15.6, 19.6), cornice=TTOP, quoins=(FL, TTOP))
    facade_trim(mb, (TX, TY0), 90, TY1 - TY0, courses=FLOOR_BANDS + (15.6, 19.6), cornice=TTOP, quoins=(FL, TTOP))
    facade_trim(mb, (-TX, TY1), -90, TY1 - TY0, courses=FLOOR_BANDS + (15.6, 19.6), cornice=TTOP, quoins=(FL, TTOP))
    facade_trim(mb, (TX, TY1), 180, 2 * TX, courses=(15.6, 19.6), cornice=TTOP, quoins=(13.0, TTOP))
    for org, yaw in (((TX, TY0), 90), ((-TX, TY1), -90), ((TX, TY1), 180)):
        with mb.at(org, rot=yaw), nc.at(org, rot=yaw):
            ln = 2 * TX if yaw == 180 else TY1 - TY0
            for u in (ln / 2 - 1.0, ln / 2 + 1.0):
                window(mb, nc, u, 16.0, 0.8, 2.6, rng.choice(("boarded", "broken", "closed")), rng, hood="arch")
            if yaw != 180:
                window(mb, nc, 3.2 if yaw == 90 else ln - 3.2, 13.5, 1.2, 1.6, rng.choice(("boarded", "cross")), rng)
    # pyramid roof with a dormer and a crooked finial
    cy = (TY0 + TY1) / 2
    roof.box_mm((-TX - 0.55, TY0 - 0.55, TTOP), (TX + 0.55, TY1 + 0.55, TTOP + 0.3), TRIM)
    roof.pyramid((0, cy, TTOP + 0.3), 2 * TX + 1.0, (TY1 - TY0) + 1.0, 8.5, "M_OldRoof")
    for sx in (-1, 1):
        for sy in (-1, 1):
            roof.beam((sx * (TX + 0.5), cy + sy * ((TY1 - TY0) / 2 + 0.5), TTOP + 0.35), (0, cy, TTOP + 8.85),
                      0.2, 0.2, "M_DarkMetal")
    # slate courses on the four faces of the spire
    pw, pd, ph = 2 * TX + 1.0, (TY1 - TY0) + 1.0, 8.5
    for k, (yaw, w, d) in enumerate(((0, pw, pd), (90, pd, pw), (180, pw, pd), (270, pd, pw))):
        a = math.radians(yaw)
        ox, oy = math.sin(a) * d / 2, -math.cos(a) * d / 2
        pitch = math.degrees(math.atan2(ph, d / 2))
        L = math.hypot(ph, d / 2)
        with roof.at((ox, cy + oy, TTOP + 0.3), rot=yaw, rot_x=pitch):
            n = 11
            for i in range(1, n):
                t = i / n
                roof.box((0, t * L, 0.0), (w * (1 - t) - 0.1, 0.08, 0.1), "M_OldRoof")
    with roof.at((0, TY0 + 1.5, TTOP + 1.6)):
        roof.box((0, 0, 0.8), (1.4, 2.2, 1.6), "M_OldRoof")
        roof.box((0, -1.11, 0.75), (0.8, 0.04, 1.0), VOID)
        roof.gable_roof((0, 0, 1.6), 1.4, 2.2, 0.8, "M_OldRoof", overhang=0.15, thick=0.12,
                        gable_mat="M_OldRoof", ridge_axis="y")
    with roof.at((0, cy, TTOP + 8.6), rot_y=7, rot_x=-4):
        roof.cylinder((0, 0, 0), 0.08, 2.4, RUST, seg=6)
        roof.sphere((0, 0, 0.9), 0.18, RUST, seg=8, rings=6)
        rbox(roof, (0.35, 0, 1.9), (0.9, 0.03, 0.35), RUST, yaw=20)
        rbox(roof, (0, 0, 1.5), (0.7, 0.04, 0.04), RUST, yaw=-35)


def _porch(mb, nc, rng):
    deck = FL + 0.02
    py0, py1, px = -14.6, TY0, 6.0

    def sag(x):
        s = 0.0
        if abs(x) > 1.8:
            s += 0.09 * ((abs(x) - 1.8) / 4.2) ** 1.3
        if x > 3.4:
            s += 0.28 * ((x - 3.4) / 2.6) ** 2
        return s

    L = py1 - py0
    n = 40
    w = 2 * px / n
    for i in range(n):
        x = -px + w * (i + 0.5)
        if abs(x - 3.45) < 0.1 or abs(x - 4.65) < 0.1:
            continue  # missing boards
        ln = L if abs(x - 3.75) > 0.1 else L * 0.45
        a = math.degrees(math.asin(min(0.9, sag(x) / L)))
        with mb.at((x, py1, deck), rot_x=a):
            mb.box((0, -ln / 2, -0.03), (w - 0.025, ln, 0.06), ROT)
    # a broken board on the ground
    rbox(mb, (4.9, -15.4, 0.12), (0.27, 2.2, 0.05), ROT, yaw=24, roll=6)
    # frame: rim beams, piers and a broken skirt
    mb.beam((-px, py0 + 0.1, deck - 0.2), (2.0, py0 + 0.1, deck - 0.2), 0.16, 0.24, ROT)
    mb.beam((2.0, py0 + 0.1, deck - 0.2), (px, py0 + 0.1, deck - 0.2 - sag(px) * 0.95), 0.16, 0.24, ROT)
    for x in (-5.8, -2.0, 2.0, 5.8):
        h = deck - 0.32 - sag(x)
        mb.box((x, py0 + 0.15, h / 2), (0.22, 0.22, h), ROT)
    for (a, b) in ((-6.0, -4.2), (-3.9, -1.9), (2.1, 2.9), (4.3, 5.0)):
        mb.box_mm((a, py0 - 0.02, 0.0), (b, py0 + 0.03, deck - 0.3 - sag(b)), ROT)
    for sx in (-1, 1):
        mb.box_mm((sx * px - 0.03, py0, 0.0), (sx * px + 0.03, py1, deck - 0.3 - sag(sx * px) * 0.5), ROT)
    # steps (risers 0.2 m)
    mb.box_mm((-1.6, -15.8, -0.4), (1.6, -15.2, 0.2), ROT)
    mb.box_mm((-1.6, -15.2, -0.4), (1.6, py0, 0.41), ROT)
    for sx in (-1, 1):
        mb.box_mm((sx * 1.6 - 0.1, -15.85, -0.2), (sx * 1.6 + 0.1, py0, 0.5), ROT)

    # railings with missing balusters
    def rail(p0, p1, broken=None):
        p0, p1 = list(p0), list(p1)
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        ln = math.hypot(dx, dy)
        nb = int(ln / 0.24)
        for k in range(nb + 1):
            t = k / nb
            x, y = p0[0] + dx * t, p0[1] + dy * t
            zb = deck - sag(x)
            if k in (0, nb):
                mb.box((x, y, zb + 0.55), (0.14, 0.14, 1.1), ROT)
            elif rng.random() > 0.28 and not (broken and broken[0] < t < broken[1]):
                mb.box((x, y, zb + 0.45), (0.05, 0.05, 0.9), ROT)
        if broken:
            ta, tb = broken
            a = (p0[0] + dx * ta, p0[1] + dy * ta)
            b = (p0[0] + dx * tb, p0[1] + dy * tb)
            mb.beam((p0[0], p0[1], deck - sag(p0[0]) + 0.95), (a[0], a[1], deck - sag(a[0]) + 0.95), 0.08, 0.08, ROT)
            mb.beam((a[0], a[1], deck - sag(a[0]) + 0.95), (a[0] + dx * 0.25, a[1] + dy * 0.25 - 0.1,
                    deck - sag(a[0]) + 0.1), 0.08, 0.08, ROT)
            mb.beam((b[0], b[1], deck - sag(b[0]) + 0.95), (p1[0], p1[1], deck - sag(p1[0]) + 0.95), 0.08, 0.08, ROT)
        else:
            mb.beam((p0[0], p0[1], deck - sag(p0[0]) + 0.95), (p1[0], p1[1], deck - sag(p1[0]) + 0.95), 0.08, 0.08, ROT)
        mb.beam((p0[0], p0[1], deck - sag(p0[0]) + 0.12), (p1[0], p1[1], deck - sag(p1[0]) + 0.12), 0.06, 0.06, ROT)

    rail((-px, py0 + 0.1), (-1.75, py0 + 0.1))
    rail((1.75, py0 + 0.1), (px, py0 + 0.1), broken=(0.35, 0.7))
    rail((-px, py1 - 0.1), (-px, py0 + 0.1), broken=(0.3, 0.55))
    rail((px, py0 + 0.1), (px, py1 - 0.1))

    # lean-to roof on four posts, right corner drooping (post broken)
    ztop, ln = 5.15, 4.2
    for x in (-5.8, -2.0, 2.0):
        mb.box((x, py0 + 0.15, (deck + 3.95 - sag(x) * 0.3) / 2), (0.2, 0.2, 3.95 - deck - sag(x) * 0.3), ROT)
        for s in (-1, 1):
            mb.beam((x, py0 + 0.15, 3.3), (x + s * 0.5, py0 + 0.15, 3.85), 0.1, 0.1, ROT)
    mb.box((5.8, py0 + 0.15, (deck - sag(5.8)) + 0.6), (0.2, 0.2, 1.2), ROT)
    rbox(mb, (5.75, py0 + 0.2, deck - sag(5.8) + 1.3), (0.2, 0.2, 0.25), ROT, pitch=25)
    mb.beam((5.75, py0 + 0.12, 3.35), (5.3, py0 + 0.4, 2.0), 0.2, 0.2, ROT)

    def droop(x):
        return 0.0 if x < 1.5 else 0.75 * ((x - 1.5) / 4.8) ** 1.5

    mb.beam((-6.3, py0 + 0.15, 3.97), (2.0, py0 + 0.15, 3.97), 0.22, 0.24, ROT)
    mb.beam((2.0, py0 + 0.15, 3.97), (6.3, py0 + 0.15, 3.97 - droop(6.3) * 0.85), 0.22, 0.24, ROT)
    strips = 14
    sw = 12.6 / strips
    base_a = math.degrees(math.atan2(ztop - 4.1, ln))
    for i in range(strips):
        x = -6.3 + sw * (i + 0.5)
        a = base_a + math.degrees(math.atan2(droop(x), ln))
        with mb.at((x, py1, ztop), rot_x=a):
            if i in (11,):
                for k in range(3):  # exposed rafters
                    mb.box((-sw / 2 + sw * (k + 0.5) / 3, -ln / 2, -0.12), (0.08, ln, 0.14), ROT)
                continue
            seg = ln if i != 12 else ln * 0.55
            mb.box((0, -seg / 2, -0.08), (sw + 0.02, seg, 0.16), "M_OldRoof", mats={"-z": ROT})
    # flickering wall lantern by the door
    with mb.at((1.95, TY0, FL + 2.9)), nc.at((1.95, TY0, FL + 2.9)):
        mb.box((0, -0.15, 0.0), (0.06, 0.3, 0.06), RUST)
        mb.box((0, -0.3, -0.25), (0.28, 0.28, 0.04), RUST)
        mb.box((0, -0.3, 0.25), (0.32, 0.32, 0.05), RUST)
        mb.pyramid((0, -0.3, 0.275), 0.32, 0.32, 0.2, RUST)
        nc.box((0, -0.3, 0.0), (0.2, 0.2, 0.46), "M_GhostGlow")


def _hall(mb, nc, rng):
    # chequered floor with broken tiles
    t = 0.8
    nx, ny = int(2 * HX / t), int(round((HY1 - HY0) / t))
    for i in range(nx):
        for j in range(ny):
            x0, y0 = -HX + i * t, HY0 + j * t
            r = rng.random()
            if r < 0.07:
                mat, z = "M_Soil", FL + 0.002
            else:
                mat, z = (TRIM if (i + j) % 2 == 0 else VOID), FL + 0.006
            mb.poly([(x0, y0, z), (x0 + t, y0, z), (x0 + t, y0 + t, z), (x0, y0 + t, z)], mat)
    # torn carpet runner door -> stairs
    for (y0, y1, w) in ((-10.3, -8.2, 1.6), (-8.0, -6.9, 1.45), (-6.6, -4.1, 1.6)):
        mb.poly([(-w / 2, y0, FL + 0.012), (w / 2, y0, FL + 0.012), (w / 2, y1, FL + 0.012), (-w / 2, y1, FL + 0.012)],
                "M_Carpet")
    # wainscot
    zw = FL + 0.95
    mb.box_mm((-HX - 0.02, HY0, FL), (-HX + 0.05, HY1, zw), "M_DarkWood")
    mb.box_mm((-HX - 0.02, HY0, zw), (-HX + 0.08, HY1, zw + 0.08), "M_DarkWood")
    mb.box_mm((HX - 0.05, HY0, FL), (HX + 0.02, HY1, zw), "M_DarkWood")
    mb.box_mm((HX - 0.08, HY0, zw), (HX + 0.02, HY1, zw + 0.08), "M_DarkWood")
    for (a, b) in ((-HX, -1.25), (1.25, HX)):
        mb.box_mm((a, HY0 - 0.02, FL), (b, HY0 + 0.05, zw), "M_DarkWood")
    mb.box_mm((-HX, HY1 - 0.05, FL), (HX, HY1 + 0.02, zw), "M_DarkWood")
    # ceiling beams, one fallen
    for y in (-9.0, -7.0, -5.0, -3.0, -1.0, 1.0, 3.0):
        if y == -3.0:
            mb.box_mm((-HX, y - 0.15, HZ1 - 0.4), (2.2, y + 0.15, HZ1), ROT)
            mb.beam((2.4, y, HZ1 - 0.25), (3.4, y - 1.9, FL + 0.15), 0.3, 0.35, ROT)
            continue
        mb.box_mm((-HX, y - 0.15, HZ1 - 0.4), (HX, y + 0.15, HZ1), ROT)
    # a hole in the ceiling (dark void) with hanging boards
    hole = [(1.0, -6.6), (2.6, -6.9), (3.7, -5.8), (3.4, -3.6), (1.8, -3.3), (0.8, -4.6)]
    mb.poly([(x, y, HZ1 - 0.01) for (x, y) in reversed(hole)], VOID)
    for (x, y, a) in ((1.3, -6.2, 25), (3.0, -4.0, -35), (2.0, -3.6, 15)):
        rbox(mb, (x, y, HZ1 - 0.7), (0.22, 0.05, 1.4), ROT, yaw=rng.uniform(0, 90), pitch=a)
    rubble(mb, (2.4, -5.2), 1.3, 14, rng, mats=(STONE, TRIM, ROT), zc=FL)
    planks(mb, (2.6, -5.0), 1.0, 5, rng, zc=FL)

    # ---- broken grand staircase up to a gallery
    run, rise, nst = (GAL_Y - (-4.0)) / 18, 0.2, 18
    sy0 = GAL_Y - run * nst
    for i in range(nst):
        y0, y1 = sy0 + run * i, sy0 + run * (i + 1)
        top = FL + rise * (i + 1)
        if 8 <= i <= 11:
            continue
        zb = FL if i < 8 else top - 0.22
        mb.box_mm((-1.2, y0, zb), (1.2, y1, top), "M_DarkWood")
        mb.box_mm((-0.7, y0, top), (0.7, y1 - 0.02, top + 0.01), "M_Carpet")
    for k in range(4):   # collapsed treads on the floor
        rbox(mb, (rng.uniform(-1.5, 1.8), rng.uniform(-2.2, -0.6), FL + 0.12 + 0.1 * k), (2.3, 0.32, 0.08),
             "M_DarkWood", yaw=rng.uniform(-40, 40), pitch=rng.uniform(-12, 12), roll=rng.uniform(-10, 10))
    rubble(mb, (0.0, -1.2), 1.2, 8, rng, mats=("M_DarkWood", TRIM), zc=FL)
    # stringers
    for sx in (-1, 1):
        a = (sx * 1.27, sy0 - 0.05, FL)
        b = (sx * 1.27, GAL_Y, GAL_Z)
        if sx < 0:
            mb.beam(a, b, 0.14, 0.32, "M_DarkWood")
        else:
            m1 = (sx * 1.27, sy0 + run * 8, FL + rise * 8)
            m2 = (sx * 1.27, sy0 + run * 12, FL + rise * 12)
            mb.beam(a, m1, 0.14, 0.32, "M_DarkWood")
            mb.beam((sx * 1.27, m2[1] - 0.2, m2[2] - 0.55), b, 0.14, 0.32, "M_DarkWood")
    # handrails + balusters (right one broken)
    for sx in (-1, 1):
        for i in range(0, nst, 2):
            if 7 <= i <= 12 or (sx > 0 and rng.random() < 0.3):
                continue
            y = sy0 + run * (i + 0.5)
            top = FL + rise * (i + 1)
            mb.box((sx * 1.27, y, top + 0.45), (0.05, 0.05, 0.9), "M_DarkWood")
        if sx < 0:
            mb.beam((sx * 1.27, sy0, FL + 1.1), (sx * 1.27, sy0 + run * 7, FL + rise * 7 + 0.95), 0.08, 0.09, "M_DarkWood")
            mb.beam((sx * 1.27, sy0 + run * 13, FL + rise * 13 + 0.95), (sx * 1.27, GAL_Y, GAL_Z + 0.95),
                    0.08, 0.09, "M_DarkWood")
        else:
            mb.beam((sx * 1.27, sy0 + run * 13, FL + rise * 13 + 0.95), (sx * 1.27, GAL_Y, GAL_Z + 0.95),
                    0.08, 0.09, "M_DarkWood")
            mb.beam((sx * 1.27, sy0 + run * 13, FL + rise * 13 + 0.95), (1.9, sy0 + run * 9, FL + 0.3),
                    0.08, 0.09, "M_DarkWood")
    # newel posts (right one toppled)
    mb.box((-1.3, sy0 - 0.1, FL + 0.65), (0.22, 0.22, 1.3), "M_DarkWood")
    mb.sphere((-1.3, sy0 - 0.1, FL + 1.42), 0.15, "M_DarkWood", seg=8, rings=6)
    rbox(mb, (2.1, sy0 - 0.6, FL + 0.12), (1.3, 0.22, 0.22), "M_DarkWood", yaw=30)
    mb.sphere((2.8, sy0 - 0.2, FL + 0.15), 0.15, "M_DarkWood", seg=8, rings=6)
    # gallery + balustrade + columns
    mb.box_mm((-HX, GAL_Y, GAL_Z - 0.25), (HX, HY1, GAL_Z), "M_DarkWood")
    mb.box_mm((-HX, GAL_Y - 0.06, GAL_Z - 0.4), (HX, GAL_Y + 0.02, GAL_Z - 0.05), TRIM)
    for sx in (-1, 1):
        mb.column((sx * 3.0, GAL_Y + 0.3, FL), 0.18, GAL_Z - 0.4 - FL, TRIM, seg=10)
        x0, x1 = sorted((sx * 1.3, sx * HX))
        x = x0
        while x <= x1:
            if not (sx > 0 and 2.3 < x < 3.2):
                mb.box((x, GAL_Y + 0.1, GAL_Z + 0.45), (0.05, 0.05, 0.9), "M_DarkWood")
            x += 0.25
        if sx < 0:
            mb.box_mm((x0, GAL_Y + 0.05, GAL_Z + 0.9), (x1, GAL_Y + 0.15, GAL_Z + 0.98), "M_DarkWood")
        else:
            mb.box_mm((x0, GAL_Y + 0.05, GAL_Z + 0.9), (2.3, GAL_Y + 0.15, GAL_Z + 0.98), "M_DarkWood")
            mb.beam((2.3, GAL_Y + 0.1, GAL_Z + 0.94), (2.9, GAL_Y - 0.5, FL + 0.1), 0.08, 0.08, "M_DarkWood")
    # dark doorways in the back wall (below and above the gallery)
    with mb.at((0, HY1, 0)):
        for (u, z0, w, h) in ((2.7, FL, 1.3, 2.5), (-2.7, FL, 1.3, 2.5), (0.0, GAL_Z, 1.6, 2.8)):
            mb.box((u, -0.02, z0 + h / 2), (w, 0.04, h), VOID, skip=("+y",))
            for s in (-1, 1):
                mb.box((u + s * (w / 2 + 0.08), -0.06, z0 + h / 2), (0.16, 0.12, h), "M_DarkWood", skip=("+y",))
            mb.box((u, -0.06, z0 + h + 0.1), (w + 0.4, 0.12, 0.2), "M_DarkWood", skip=("+y",))

    # ---- portrait (crooked, with glowing eyes) on the left wall, a fallen one on the right
    with mb.at((-HX + 0.01, -5.6, FL + 3.0), rot=90, rot_y=7), nc.at((-HX + 0.01, -5.6, FL + 3.0), rot=90, rot_y=7):
        fw, fh, b = 1.5, 2.0, 0.16
        mb.box((0, -0.02, 0), (fw - 2 * b, 0.04, fh - 2 * b), "M_PortraitCanvas")
        for s in (-1, 1):
            mb.box((s * (fw / 2 - b / 2), -0.05, 0), (b, 0.1, fh), "M_TarnishedGold")
            mb.box((0, -0.05, s * (fh / 2 - b / 2)), (fw - 2 * b, 0.1, b), "M_TarnishedGold")
        mb.sphere((0, -0.04, 0.25), 0.3, "M_PortraitFace", seg=10, rings=6, scale=(0.8, 0.15, 1.0))
        mb.box((0, -0.04, -0.45), (0.9, 0.03, 0.6), "M_Black")
        for s in (-1, 1):
            nc.box((s * 0.09, -0.1, 0.3), (0.05, 0.02, 0.025), "M_GhostGlow")
    with mb.at((HX - 0.35, -1.8, FL), rot=-90, rot_x=-12):
        fw, fh, b = 1.2, 1.6, 0.14
        mb.box((0, 0, fh / 2), (fw - 2 * b, 0.04, fh - 2 * b), "M_PortraitCanvas")
        for s in (-1, 1):
            mb.box((s * (fw / 2 - b / 2), -0.03, fh / 2), (b, 0.1, fh), "M_TarnishedGold")
            mb.box((0, -0.03, fh / 2 + s * (fh / 2 - b / 2)), (fw - 2 * b, 0.1, b), "M_TarnishedGold")

    # ---- toppled chair, broken chair, fallen chandelier
    def chair(mb_):
        mb_.box((0, 0, 0.47), (0.5, 0.5, 0.06), "M_DarkWood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb_.box((sx * 0.21, sy * 0.21, 0.22), (0.06, 0.06, 0.44), "M_DarkWood")
            mb_.box((sx * 0.21, 0.22, 0.75), (0.06, 0.06, 0.6), "M_DarkWood")
        mb_.box((0, 0.22, 0.9), (0.45, 0.04, 0.3), "M_Carpet")
        mb_.box((0, 0.22, 1.06), (0.5, 0.06, 0.06), "M_DarkWood")

    with mb.at((2.4, -2.6, FL + 0.27), rot=-35, rot_x=-90):
        chair(mb)
    with mb.at((-3.2, -8.6, FL), rot=60, rot_y=6):
        chair(mb)
    with mb.at((-2.3, -6.9, FL + 0.08), rot=20, rot_x=10):
        mb.torus((0, 0, 0.2), 0.85, 0.05, "M_TarnishedGold", seg=16, tube_seg=5)
        mb.torus((0, 0, 0.5), 0.45, 0.04, "M_TarnishedGold", seg=12, tube_seg=5)
        mb.cylinder((0, 0, 0.0), 0.08, 0.9, "M_TarnishedGold", seg=8)
        for k in range(6):
            a = math.tau * k / 6
            mb.beam((0, 0, 0.6), (math.cos(a) * 0.85, math.sin(a) * 0.85, 0.2), 0.04, 0.04, "M_TarnishedGold")
            mb.cylinder((math.cos(a) * 0.85, math.sin(a) * 0.85, 0.22), 0.05, 0.18, "M_ShojiPaper", seg=6)
    mb.box((-2.1, -6.9, HZ1 - 0.7), (0.05, 0.05, 1.4), RUST)  # broken chain stub
    # debris piles along the walls
    rubble(mb, (-3.2, -9.6), 0.8, 7, rng, zc=FL)
    rubble(mb, (3.3, -0.2), 0.9, 8, rng, zc=FL)
    planks(mb, (-3.0, -6.5), 0.8, 4, rng, zc=FL, length=(0.8, 1.8))
    # a dusty side table, knocked over
    with mb.at((3.2, -9.0, FL + 0.3), rot=-20, rot_y=90):
        mb.box((0, 0, 0.72), (0.9, 0.6, 0.05), "M_DarkWood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * 0.38, sy * 0.24, 0.35), (0.05, 0.05, 0.7), "M_DarkWood")
    # door leaves: one swung wide open, the other ajar and hanging off a hinge
    for (hx, yaw, tilt) in ((-1.2, 82, 0.0), (1.2, 180 - 55, 4.0)):
        with mb.at((hx, HY0 + 0.05, FL + 0.03), rot=yaw, rot_y=tilt):
            mb.box((0.59, 0, 1.55), (1.16, 0.08, 3.1), "M_DarkWood")
            for k in range(3):
                mb.box((0.59, -0.05, 0.55 + k * 1.0), (0.8, 0.03, 0.75), ROT)
            mb.box((1.0, -0.07, 1.4), (0.08, 0.05, 0.08), RUST)


def _ivy(nc, rng):
    def patch(origin, yaw, u0, u1, z0, z1, density=2.6):
        with nc.at(origin, rot=yaw):
            n = int((u1 - u0) * (z1 - z0) * density)
            for _ in range(n):
                u = rng.uniform(u0, u1)
                t = (u - u0) / (u1 - u0)
                lim = z0 + (z1 - z0) * (0.35 + 0.65 * math.sin(t * math.pi) ** 0.7) * rng.uniform(0.75, 1.0)
                z = z0 + (lim - z0) * rng.random() ** 0.85
                leaf_card(nc, (u, -rng.uniform(0.06, 0.3), z), rng.uniform(0.45, 0.8), "M_Ivy", rng)

    patch((X0, Y0), 0, -0.3, 6.5, FL, 11.6, density=3.0)
    patch((X0, Y0), 0, 10.5, 14.5, FL, 5.5)
    patch((TX, Y0), 0, 7.5, 12.5, FL, 8.5)
    patch((-TX, TY0), 0, 7.6, 9.4, FL, 18.0, density=3.4)
    patch((-TX, TY0), 0, -0.2, 1.0, FL, 4.0, density=3.0)
    patch((X1, Y0), 90, 0.0, 4.5, FL, 6.0)
    patch((X1, Y0), 90, 9.0, 17.0, FL, 11.6, density=3.0)
    patch((X0, Y1), -90, 3.0, 9.0, FL, 8.5)
    patch((X1, Y1), 180, 12.0, 23.0, FL, 11.4, density=3.0)
    patch((X1, Y1), 180, 30.0, 35.0, FL, 5.5)
    for sx in (-1, 1):   # gate pillars
        patch((sx * 3.0 - 0.43, -38.43), 0, 0.0, 0.86, 0.0, 2.2 + 0.6 * sx, density=4.0)


def _grounds(mb, nc, rng):
    fy = -38.0
    # stone gate pillars (one ball finial fallen)
    for sx in (-1, 1):
        x = sx * 3.0
        mb.box((x, fy, 1.25), (0.85, 0.85, 3.5), STONE)
        mb.box((x, fy, 0.1), (1.05, 1.05, 0.4), TRIM)
        mb.box((x, fy, 3.1), (1.05, 1.05, 0.2), TRIM)
        mb.pyramid((x, fy, 3.2), 0.9, 0.9, 0.35, TRIM)
        if sx < 0:
            mb.sphere((x, fy, 3.75), 0.28, TRIM, seg=10, rings=6)
        else:
            mb.sphere((x + 1.1, fy - 0.9, 0.24), 0.28, TRIM, seg=10, rings=6)
            rbox(mb, (x + 0.7, fy - 0.5, 0.08), (0.3, 0.2, 0.15), TRIM, yaw=30)

    def gate_wing(width, height):
        mb.box((width / 2, 0, 0.15), (width, 0.06, 0.08), RUST)
        mb.box((width / 2, 0, height - 0.1), (width, 0.06, 0.08), RUST)
        mb.box((width / 2, 0, height * 0.55), (width, 0.05, 0.06), RUST)
        mb.box((0.03, 0, height / 2), (0.08, 0.08, height), RUST)
        mb.box((width - 0.03, 0, height / 2), (0.08, 0.08, height), RUST)
        k = 0
        x = 0.18
        while x < width - 0.1:
            hh = height + 0.25 * math.sin(math.pi * x / width)
            mb.box((x, 0, hh / 2), (0.035, 0.035, hh), RUST)
            mb.cone((x, 0, hh), 0.05, 0.16, RUST, seg=4)
            x += 0.16
            k += 1
        # scroll ring
        with mb.at((width / 2, 0, height * 0.78), rot_x=90):
            mb.torus((0, 0, 0), 0.32, 0.03, RUST, seg=12, tube_seg=4)

    with mb.at((-2.55, fy, 0.02), rot=58, rot_y=-2.5):
        gate_wing(2.5, 2.3)
    with mb.at((0.4, fy + 1.4, 0.14), rot=-18, rot_x=-86):   # fallen wing lying on the ground
        gate_wing(2.5, 2.3)
    rbox(mb, (1.6, fy + 1.0, 0.1), (0.4, 0.3, 0.2), STONE, yaw=20)

    # KEEP OUT board next to the gate
    bx, by, byaw = 5.6, fy - 1.6, -12.0
    with mb.at((bx, by, 0), rot=byaw):
        for s in (-1, 1):
            mb.box((s * 1.0, 0.04, 0.9), (0.12, 0.12, 1.8 + 0.2 * s), ROT)
        mb.box((0, 0, 1.45), (2.3, 0.06, 0.32), BOARD)
        mb.box((0.05, 0, 1.12), (2.25, 0.06, 0.3), BOARD)
        mb.box((-0.15, 0, 0.8), (1.9, 0.06, 0.28), BOARD)
        rbox(mb, (0.9, -0.05, 0.62), (0.9, 0.05, 0.24), BOARD, pitch=-25)

    # cracked flagstone walkway gate -> porch steps
    y = fy + 0.5
    row = 0
    while y < -16.0:
        d = rng.uniform(0.55, 0.8)
        x = -1.7 + (0.35 if row % 2 else 0.0)
        while x < 1.6:
            w = min(rng.uniform(0.7, 1.1), 1.75 - x)
            if w > 0.25 and rng.random() > 0.12:
                rbox(mb, (x + w / 2, y + d / 2, -0.06 + rng.uniform(0.0, 0.03)), (w - 0.06, d - 0.06, 0.18), TRIM,
                     yaw=rng.uniform(-4, 4), pitch=rng.uniform(-2, 2), roll=rng.uniform(-2, 2))
            x += w
        y += d
        row += 1

    # debris around the building
    for (c, r, n) in (((-14.0, -10.5), 2.5, 7), ((12.0, -10.2), 2.0, 6), ((21.8, 3.0), 2.0, 6),
                      ((-6.0, 12.5), 2.5, 7), ((-22.5, -2.0), 1.8, 5)):
        rubble(mb, c, r, n, rng)
    for (c, r, n) in (((-9.0, -11.5), 2.0, 4), ((8.5, -12.5), 2.2, 4), ((16.0, 12.0), 2.5, 5),
                      ((-21.5, 6.0), 1.5, 3), ((-6.5, -21.0), 2.0, 3)):
        planks(mb, c, r, n, rng)
    for k in range(18):   # fallen slates under the roof holes
        x = rng.uniform(-17, 15)
        yy = rng.choice((rng.uniform(-10.5, -9.0), rng.uniform(10.8, 12.5)))
        rbox(mb, (x, yy, 0.03), (0.5, 0.32, 0.04), "M_OldRoof", yaw=rng.uniform(0, 180), pitch=rng.uniform(-6, 6))
    # a fallen shutter and a toppled urn
    rbox(mb, (-17.0, -9.6, 0.08), (0.7, 2.1, 0.05), ROT, yaw=70, pitch=4)
    with mb.at((-7.5, -18.0, 0.0)):
        mb.box((0, 0, 0.25), (1.0, 1.0, 0.5), TRIM)
        mb.lathe([(0.25, 0.5), (0.45, 0.8), (0.5, 1.1), (0.35, 1.3)], TRIM, seg=10)
    with mb.at((7.5, -18.0, 0.0)):
        mb.box((0, 0, 0.25), (1.0, 1.0, 0.5), TRIM)
    with mb.at((8.3, -18.9, 0.42), rot=-30, rot_x=90):
        mb.lathe([(0.25, -0.4), (0.45, -0.1), (0.5, 0.2), (0.35, 0.4)], TRIM, seg=10)


def _sockets(aset, rng):
    fy = -38.0
    purple = (0.6, 0.4, 1.0)
    # iron fence along the pad edge (rectangle, gaps + skewed panels + a missing stretch)
    fx, fb = 40.0, 34.0
    segs = []
    for side in (-1, 1):
        x = side * 3.4
        while abs(x) < fx - 1.9:
            segs.append(((x + side * 2.0, fy), 0.0))
            x += side * 4.0
        y = fy + 2.0
        while y < fb - 1.0:
            segs.append(((side * fx, y), 90.0))
            y += 4.0
    x = -fx + 2.0
    while x < fx - 1.0:
        segs.append(((x, fb), 180.0))
        x += 4.0
    for (p, yaw) in segs:
        r = rng.random()
        if r < 0.1 or (p[0] > 30 and p[1] > 10 and p[1] < 26 and abs(yaw - 90) < 1):
            continue
        if r < 0.3:
            yaw += rng.uniform(-9, 9)
        aset.prop("SM_Fence_Iron", (p[0], p[1], 0.0), yaw)
    # dead trees, old lamps
    for (x, y) in ((-28, -24), (25, -28), (-33, 16), (31, 21), (-14, 27), (16, -31), (-24, -6), (29, -6),
                   (8, 25), (-36, -33)):
        aset.prop("SM_DeadTree_A", (x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5), 0), rng.uniform(0, 360),
                  round(rng.uniform(0.8, 1.3), 2))
    for (x, y, yaw) in ((-3.2, -31.0, 10), (3.2, -26.0, 170), (-3.2, -20.0, -5), (7.0, -15.5, 200)):
        aset.prop("SM_LampPost_Old", (x, y, 0), yaw)
    # overgrowth: weeds along the walls, ferns and bushes in the yard
    def free(x, y):
        return not (abs(x) < 2.4 and y < -14.0) and not (X0 - 0.5 < x < X1 + 0.5 and Y0 - 0.5 < y < Y1 + 0.5) \
            and not (-6.5 < x < 6.5 and -16.2 < y < -10.5)
    n = 0
    while n < 70:
        side = rng.random()
        if side < 0.6:   # hugging the plinth
            t = rng.random()
            per = 2 * (X1 - X0) + 2 * (Y1 - Y0)
            d = t * per
            if d < X1 - X0:
                x, y = X0 + d, Y0 - 0.9
            elif d < 2 * (X1 - X0):
                x, y = X0 + d - (X1 - X0), Y1 + 0.9
            elif d < 2 * (X1 - X0) + (Y1 - Y0):
                x, y = X0 - 0.9, Y0 + d - 2 * (X1 - X0)
            else:
                x, y = X1 + 0.9, Y0 + d - 2 * (X1 - X0) - (Y1 - Y0)
            x += rng.uniform(-0.4, 0.4)
            y += rng.uniform(-0.4, 0.4)
        else:
            x, y = rng.uniform(-37, 37), rng.uniform(-35, 31)
        if not free(x, y):
            continue
        r = rng.random()
        asset = "SM_GrassClump_A" if r < 0.55 else ("SM_Fern_A" if r < 0.85 else "SM_Bush_B")
        aset.prop(asset, (x, y, 0), rng.uniform(0, 360), round(rng.uniform(0.9, 1.6), 2))
        n += 1
    for k in range(14):   # weeds poking between the flagstones
        aset.prop("SM_GrassClump_A", (rng.uniform(-1.9, 1.9), rng.uniform(-37, -16.5), 0), rng.uniform(0, 360),
                  round(rng.uniform(0.6, 1.0), 2))
    # texts
    by, byaw = fy - 1.6, -12.0
    nx, ny = math.sin(math.radians(byaw)), -math.cos(math.radians(byaw))
    aset.text("KEEP OUT", (5.6 + nx * 0.06, by + ny * 0.06, 1.2), byaw, size=0.42, color=(0.78, 0.08, 0.05))
    aset.text("SPECIAL DORM", (0.0, TY0 - 0.34 - 0.025, FL + 3.4), 0.0, size=0.26, color=(0.32, 0.30, 0.33))
    # lights: dim purple inside, a flickery lantern by the door
    aset.light((0.0, -6.5, HZ1 - 0.8), purple, 1300.0, 14.0)
    aset.light((0.0, 1.0, 3.0), purple, 900.0, 9.0)
    aset.light((-2.6, 3.0, GAL_Z + 1.5), purple, 800.0, 7.0)
    aset.light((1.95, TY0 - 0.35, FL + 2.9), (0.72, 0.5, 1.0), 1100.0, 9.0)
    # atmosphere
    for (x, y) in ((-13.0, -22.0), (15.0, -19.0), (-2.0, 20.0)):
        aset.emitter("mist", (x, y, 0.5), 2.0)
    aset.emitter("mist", (0.0, -5.0, FL + 0.3), 1.0, rate=0.5)
    aset.audio("A_Wind", (0.0, -5.0, 6.0), radius=70.0)
    aset.interact("sign", (5.6, by - 0.8, 1.0), byaw, title="Abandoned Dorm",
                  text="The old Special Dorm. Students who stayed here vanished without a trace... Turn back.")
    aset.special("camera", (2.3, -10.0, FL + 1.5), target=(-0.6, 2.5, FL + 2.6), lens=18)


def build():
    rng = random.Random(1331)
    aset = AssetSet("abandoned")
    dorm = aset.mesh("Abandoned_Dorm")
    roof = aset.mesh("Abandoned_Roof")
    hall = aset.mesh("Abandoned_Hall")
    grounds = aset.mesh("Abandoned_Grounds")
    nc = aset.mesh("Abandoned_NoCol")
    _shell(dorm)
    _facades(dorm, nc, rng)
    _roof(roof, rng)
    _tower(dorm, roof, nc, rng)
    _porch(dorm, nc, rng)
    _hall(hall, nc, rng)
    _ivy(nc, rng)
    _grounds(grounds, nc, rng)
    _sockets(aset, rng)
    return aset


PLACEMENTS = {"abandoned": build}
