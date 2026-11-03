"""
Duel Gym - beachside sports hall with practice duel fields.

A 60 x 40 m hall with a segmented barrel roof (axis along X, crown 14.5 m),
a white-mullioned glass front, concrete piers, an entrance canopy and a big
roof sign. Inside (walkable through the 6 m wide entrance): wooden court with
line markings, two raised practice duel fields with glowing outlines and
bleachers along the back wall. Automatic sliding glass doors at the entrance, a
metal double door at the back (between the bleacher blocks). Two single-storey
annexes stand inside the hall against the front wall: west = coach's office +
equipment store, east = locker room + showers. Outside: entrance plaza, outdoor
practice court with duel dummies, and a path to the beach behind (+Y).

Local space: origin = pad centre at ground level, front faces -Y; the road
arrives at about (0, -60).
"""

import math
import random

from . import AssetSet
from . import interior as K
from .. import palette

palette.register({
    "M_GymCeiling":   dict(kind="opaque", color=(0.80, 0.73, 0.60), rough=0.8, detail="Planks", tiling=0.5),
    "M_GymRib":       dict(kind="opaque", color=(0.88, 0.90, 0.90), rough=0.5, metallic=0.4, detail=None),
    "M_CourtPaint":   dict(kind="opaque", color=(0.16, 0.36, 0.62), rough=0.6, detail="Concrete", tiling=0.25),
})

WALL = "M_WhiteWall"
CONC = "M_Concrete"
FRAME = "M_WindowFrame"
GLASS = "M_Glass"
ROOF = "M_GymRoof"
CEIL = "M_GymCeiling"
LINE = "M_CourtLine"
GLOW = "M_DuelFieldGlow"

FLG = 0.2                     # hall floor level
GX0, GX1, GY0, GY1 = -30.0, 30.0, -14.0, 26.0
WT = 0.4                      # wall thickness
EZ = 9.5                      # eave (wall top) height
CZ = 14.5                     # roof crown (underside)
YC = (GY0 + GY1) / 2
HALF = (GY1 - GY0) / 2
R = (HALF ** 2 + (CZ - EZ) ** 2) / (2 * (CZ - EZ))
ZC = CZ - R
TH_W = math.asin(HALF / R)
OH = 1.3                      # roof overhang front/back
OHX = 1.0                     # roof overhang at the gable ends
RTH = 0.4                     # roof thickness
FIELDS = ((-13.0, 2.5), (13.0, 2.5))
FIELD_W, FIELD_D = 12.0, 7.0
ENT_W, ENT_H = 5.7, 3.6       # entrance (between the curtain-wall door posts)
BACK_W, BACK_H = 3.2, 3.0     # back door
AX, AY0, AY1 = 16.8, GY0 + WT, -9.9   # annexes: |x| from AX to the side wall, y from the front wall to AY1
AT, AH = 0.15, 3.0            # annex wall thickness, room height (ceiling at FLG + AH)
PART = 23.25                  # |x| of the partition inside each annex


def rbox(mb, center, size, mat, yaw=0.0, pitch=0.0, roll=0.0, mats=None):
    with mb.at(center, rot=yaw, rot_y=pitch, rot_x=roll):
        mb.box((0, 0, 0), size, mat, mats=mats)


def flat_quad(mb, x0, y0, x1, y1, z, mat):
    mb.poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], mat)


def outline(mb, x0, y0, x1, y1, z, w, mat):
    flat_quad(mb, x0, y0, x1, y0 + w, z, mat)
    flat_quad(mb, x0, y1 - w, x1, y1, z, mat)
    flat_quad(mb, x0, y0 + w, x0 + w, y1 - w, z, mat)
    flat_quad(mb, x1 - w, y0 + w, x1, y1 - w, z, mat)


def ring(mb, cx, cy, r, w, z, mat, seg=24):
    for i in range(seg):
        a0, a1 = math.tau * i / seg, math.tau * (i + 1) / seg
        p = [(cx + math.cos(a0) * (r - w / 2), cy + math.sin(a0) * (r - w / 2)),
             (cx + math.cos(a0) * (r + w / 2), cy + math.sin(a0) * (r + w / 2)),
             (cx + math.cos(a1) * (r + w / 2), cy + math.sin(a1) * (r + w / 2)),
             (cx + math.cos(a1) * (r - w / 2), cy + math.sin(a1) * (r - w / 2))]
        mb.poly([(p[0][0], p[0][1], z), (p[1][0], p[1][1], z), (p[2][0], p[2][1], z), (p[3][0], p[3][1], z)], mat)


def arc_pt(theta, rad):
    return YC + rad * math.sin(theta), ZC + rad * math.cos(theta)


# ---------------------------------------------------------------- shell
def _wall_stacked(mb, p0, p1, z0, height, thick, mat, openings, inner_mat=None):
    """Like MeshBuilder.wall() but openings may share the same stretch of wall (a low and a high window
    above each other in one bay) - MeshBuilder.wall() would fill one with the other's wall pieces."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    yaw = math.degrees(math.atan2(dy, dx))
    ops = [dict(o) for o in openings]
    for o in ops:
        o["a"], o["b"] = max(0.0, o["u"] - o["w"] / 2), min(length, o["u"] + o["w"] / 2)
        o.setdefault("z0", 0.0)
    cuts = sorted({0.0, length, *[o["a"] for o in ops], *[o["b"] for o in ops]})
    with mb.at((p0[0], p0[1], z0), rot=yaw):
        def piece(u0, u1, v0, v1):
            if u1 - u0 > 1e-4 and v1 - v0 > 1e-4:
                mb.box(((u0 + u1) / 2, thick / 2, (v0 + v1) / 2), (u1 - u0, thick, v1 - v0), mat,
                       mats={"+y": inner_mat} if inner_mat else None)
        for u0, u1 in zip(cuts[:-1], cuts[1:]):
            holes = sorted((o["z0"], o["z1"]) for o in ops if o["a"] <= u0 + 1e-6 and o["b"] >= u1 - 1e-6)
            v = 0.0
            for (h0, h1) in holes:
                piece(u0, u1, v, h0)
                v = max(v, h1)
            piece(u0, u1, v, height)
        for o in ops:
            ou0, ou1, z0o, z1o = o["a"], o["b"], o["z0"], o["z1"]
            fr = o.get("frame")
            if fr:
                fw = 0.08
                mb.box((ou0 - fw / 2, -0.03, (z0o + z1o) / 2), (fw, 0.12, z1o - z0o + fw), fr)
                mb.box((ou1 + fw / 2, -0.03, (z0o + z1o) / 2), (fw, 0.12, z1o - z0o + fw), fr)
                mb.box(((ou0 + ou1) / 2, -0.03, z1o + fw / 2), (ou1 - ou0 + 2 * fw, 0.12, fw), fr)
                if z0o > 0.01:
                    mb.box(((ou0 + ou1) / 2, -0.06, z0o - fw / 2), (ou1 - ou0 + 2 * fw, 0.2, fw), fr)
            if o.get("glass"):
                mb.box(((ou0 + ou1) / 2, thick / 2, (z0o + z1o) / 2), (ou1 - ou0, 0.04, z1o - z0o), o["glass"])


def _shell(mb, nc):
    # foundation slab down to -4 (top = court floor), concrete skirt outside
    mb.box_mm((GX0, GY0, -4.0), (GX1, GY1, FLG), CONC, mats={"+z": "M_CourtFloor"})
    mb.box_mm((GX0 - 0.35, GY0 - 0.35, -4.0), (GX1 + 0.35, GY1 + 0.35, 0.08), CONC)

    hz = EZ - FLG
    # front wall: big opening for the curtain wall, high windows in the white end bays
    win = lambda u: dict(u=u, w=3.0, z0=5.3, z1=8.1, glass=GLASS, frame=FRAME)
    front_ops = [dict(u=30.0, w=32.0, z0=0.0, z1=hz - 0.5)] + [win(u) for u in (3.5, 9.5, 50.5, 56.5)]
    # the low windows look into the annex rooms: clear glass (blinds inside the locker room / showers)
    front_ops += [dict(u=u, w=3.0, z0=1.2, z1=2.6, glass="M_GlassClear", frame=FRAME) for u in (3.5, 9.5, 50.5, 56.5)]
    _wall_stacked(mb, (GX0, GY0), (GX1, GY0), FLG, hz, WT, WALL, front_ops, inner_mat=WALL)
    # back wall (closed double door is decoration only)
    back_ops = [win(3.0 + 6.0 * k) for k in range(10) if k not in (4, 5)]
    mb.wall((GX1, GY1), (GX0, GY1), FLG, hz, WT, WALL, openings=back_ops + [dict(u=GX1, w=BACK_W, z0=0.0, z1=BACK_H)],
            inner_mat=WALL)
    # side walls
    side_ops = [dict(u=GY1 - GY0 - (3.33 + 6.667 * k), w=3.2, z0=5.2, z1=8.1, glass=GLASS, frame=FRAME)
                for k in range(6)]
    mb.wall((GX1, GY0), (GX1, GY1), FLG, hz, WT, WALL, openings=side_ops, inner_mat=WALL)
    mb.wall((GX0, GY1), (GX0, GY0), FLG, hz, WT, WALL, openings=side_ops, inner_mat=WALL)
    # mullions in the punched windows
    for (p0, p1, ops) in (((GX0, GY0), (GX1, GY0), front_ops[1:]), ((GX1, GY1), (GX0, GY1), back_ops),
                          ((GX1, GY0), (GX1, GY1), side_ops), ((GX0, GY1), (GX0, GY0), side_ops)):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        ln = math.hypot(dx, dy)
        yaw = math.degrees(math.atan2(dy, dx))
        with mb.at((p0[0], p0[1], FLG), rot=yaw):
            for o in ops:
                h = o["z1"] - o["z0"]
                mb.box((o["u"], WT / 2, o["z0"] + h / 2), (0.1, WT + 0.08, h), FRAME)
                if h > 2.0:
                    mb.box((o["u"], WT / 2, o["z0"] + h * 0.62), (o["w"], WT + 0.05, 0.1), FRAME)

    # gable infill under the barrel at both ends (outer + inner face)
    n = 24
    arc = [arc_pt(-TH_W + 2 * TH_W * i / n, R) for i in range(n + 1)]
    for sx in (-1, 1):
        for x, outward in ((sx * GX1, True), (sx * (GX1 - WT), False)):
            pts = [(x, y, z) for (y, z) in [(GY0, EZ), (GY1, EZ)] + list(reversed(arc[1:-1]))]
            facing_pos_x = (sx > 0) == outward
            mb.poly(pts if facing_pos_x else list(reversed(pts)), WALL)
        # teal louvre band in the gable
        for k in range(5):
            z = EZ + 0.8 + k * 0.55
            half = math.sqrt(max(0.0, R ** 2 - (z - ZC) ** 2))
            half = min(half, HALF) - 0.9
            if half > 1:
                mb.box((sx * (GX1 + 0.05), YC, z), (0.12, 2 * half, 0.18), ROOF)

    # accent band below the eave + concrete base band (outside only)
    for (a, b, yaw, ln) in (((GX0, GY0), None, 0, GX1 - GX0), ((GX1, GY0), None, 90, GY1 - GY0),
                            ((GX1, GY1), None, 180, GX1 - GX0), ((GX0, GY1), None, -90, GY1 - GY0)):
        with mb.at(a, rot=yaw):
            if yaw == 0:
                for (u0, u1) in ((0, 14.0), (46.0, 60.0)):
                    mb.box(((u0 + u1) / 2, -0.04, 0.65), (u1 - u0, 0.08, 1.1), CONC, skip=("+y",))
                    mb.box(((u0 + u1) / 2, -0.05, EZ - 0.55), (u1 - u0, 0.1, 0.5), ROOF, skip=("+y",))
            else:
                mb.box((ln / 2, -0.04, 0.65), (ln, 0.08, 1.1), CONC, skip=("+y",))
                mb.box((ln / 2, -0.05, EZ - 0.55), (ln + 0.1, 0.1, 0.5), ROOF, skip=("+y",))
            # piers
            step = 6.0 if ln > 50 else ln / 6
            k = 0
            while k * step <= ln + 0.01:
                u = k * step
                if not (yaw == 0 and 14.5 < u < 45.5) and not (yaw == 180 and abs(u - 30.0) < 1.0):
                    mb.box((u, -0.21, (EZ - 0.2) / 2), (0.8, 0.42, EZ - 0.2), CONC, skip=("+y",))
                k += 1
    # curtain wall frame posts at the glass edges
    for x in (-16.0, 16.0):
        mb.box((x, GY0 - 0.15, EZ / 2), (1.0, 0.7, EZ), CONC)


def _curtain(mb):
    """Glass front between x=-16..16 with white mullions; 6 m door opening in the middle."""
    y = GY0 + WT / 2
    z0, z1 = FLG, EZ - 0.5
    rows = (z0, 3.9, 6.6, z1)
    xs = [-16.0 + 2.0 * k for k in range(17)]
    for i in range(16):
        xa, xb = xs[i], xs[i + 1]
        for j in range(3):
            za, zb = rows[j], rows[j + 1]
            if j == 0 and -3.0 <= (xa + xb) / 2 <= 3.0:
                continue   # entrance
            mb.box(((xa + xb) / 2, y, (za + zb) / 2), (xb - xa, 0.04, zb - za), GLASS)
    for x in xs:
        if -3.0 < x < 3.0:
            mb.box((x, y, (3.9 + z1) / 2), (0.14, 0.32, z1 - 3.9), FRAME)
        else:
            mb.box((x, y, (z0 + z1) / 2), (0.14 if abs(x) < 15 else 0.3, 0.32, z1 - z0), FRAME)
    for z in rows:
        mb.box((0, y, z), (32.0, 0.34, 0.16), FRAME)
    # door posts + threshold
    for x in (-3.0, 3.0):
        mb.box((x, y, (FLG + 3.9) / 2), (0.3, 0.45, 3.9 - FLG), FRAME)
    # (the sliding glass leaves are an automatic door, see _sockets)


def _roof(mb, nc):
    th_e = math.asin((HALF + OH) / (R + RTH / 2))
    n = 30
    LX = (GX1 - GX0) + 2 * OHX
    sky = []
    for i in range(n):
        t0 = -th_e + 2 * th_e * i / n
        t1 = t0 + 2 * th_e / n
        tm = (t0 + t1) / 2
        rm = R + RTH / 2
        chord = 2 * rm * math.sin((t1 - t0) / 2) + 0.03
        y, z = arc_pt(tm, rm)
        is_sky = abs(math.sin(tm) * rm) < 3.2
        with mb.at((0, y, z), rot_x=-math.degrees(tm)):
            if is_sky:
                # skylight band: glass with white edge bars
                mb.box((0, 0, 0), (LX - 6.0, chord, RTH * 0.5), GLASS, mats={"-z": GLASS})
                mb.box((-(LX - 3.0) / 2, 0, 0), (3.0, chord, RTH), ROOF, mats={"-z": CEIL})
                mb.box(((LX - 3.0) / 2, 0, 0), (3.0, chord, RTH), ROOF, mats={"-z": CEIL})
                sky.append(i)
            else:
                mb.box((0, 0, 0), (LX, chord, RTH), ROOF, mats={"-z": CEIL, "+x": FRAME, "-x": FRAME})
        # standing ribs on top + steel arches below (every 6 m)
        for k in range(11):
            x = GX0 + 6.0 * k
            yr, zr = arc_pt(tm, R + RTH + 0.12)
            with mb.at((x, yr, zr), rot_x=-math.degrees(tm)):
                mb.box((0, 0, 0), (0.22, chord, 0.24), FRAME)
            if 0 < k < 10:
                yi, zi = arc_pt(tm, R - 0.3)
                with mb.at((x, yi, zi), rot_x=-math.degrees(tm)):
                    if abs(math.sin(tm) * R) < HALF:
                        mb.box((0, 0, 0), (0.3, chord, 0.6), "M_GymRib")
    # eave fascia / gutters front and back
    for sgn in (-1, 1):
        y, z = arc_pt(sgn * th_e, R + RTH / 2)
        mb.box((0, y + sgn * 0.12, z - 0.05), (LX, 0.24, 0.5), FRAME)
    # light panels hanging under the arches (no collision)
    for k in range(1, 10):
        x = GX0 + 6.0 * k
        for yy in (-6.0, 0.0, 6.0, 12.0, 18.0):
            zz = ZC + math.sqrt(R ** 2 - (yy - YC) ** 2) - 1.4
            nc.box((x + 1.2, yy, zz), (1.6, 0.5, 0.12), "M_LampGlow")
            nc.box((x + 1.2, yy, zz + 0.1), (1.7, 0.6, 0.08), FRAME)
            nc.box((x + 1.2, yy, zz + 0.75), (0.04, 0.04, 1.3), "M_DarkMetal")


def _interior(mb, nc, rng):
    zf = FLG + 0.004
    w = 0.08
    # main court lines
    outline(mb, -26.0, -9.5, 26.0, 14.5, zf, w, LINE)
    flat_quad(mb, -w / 2, -9.5 + w, w / 2, 14.5 - w, zf, LINE)
    ring(mb, 0.0, 2.5, 3.0, w, zf, LINE, seg=32)
    ring(mb, 0.0, 2.5, 0.9, w, zf, "M_AcademyRed", seg=20)
    for sx in (-1, 1):
        ring(mb, sx * 22.5, 2.5, 2.3, w, zf, LINE, seg=28)
        outline(mb, min(sx * 26.0, sx * 21.0), 0.0, max(sx * 26.0, sx * 21.0), 5.0, zf, w, "M_AcademyYellow")
    # wainscot (sports padding) along the side and back walls
    for (x0, y0, x1, y1) in ((GX0 + WT, AY1, GX0 + WT + 0.06, GY1 - WT), (GX1 - WT - 0.06, AY1, GX1 - WT, GY1 - WT),
                             (GX0 + WT, GY1 - WT - 0.06, -BACK_W / 2 - 0.3, GY1 - WT),
                             (BACK_W / 2 + 0.3, GY1 - WT - 0.06, GX1 - WT, GY1 - WT)):
        mb.box_mm((x0, y0, FLG), (x1, y1, FLG + 1.8), "M_Wood")

    # practice duel fields (raised 0.3 m) with glowing outlines
    for (cx, cy) in FIELDS:
        x0, x1 = cx - FIELD_W / 2, cx + FIELD_W / 2
        y0, y1 = cy - FIELD_D / 2, cy + FIELD_D / 2
        mb.box_mm((x0, y0, FLG), (x1, y1, FLG + 0.3), "M_AcademyBlue", mats={"+z": "M_ArenaFloor"})
        mb.box_mm((x0 - 0.12, y0 - 0.12, FLG), (x1 + 0.12, y1 + 0.12, FLG + 0.08), FRAME)
        zt = FLG + 0.305
        outline(nc, x0 + 0.25, y0 + 0.25, x1 - 0.25, y1 - 0.25, zt, 0.1, GLOW)
        flat_quad(nc, cx - 0.04, y0 + 0.35, cx + 0.04, y1 - 0.35, zt, GLOW)
        for side in (-1, 1):
            # card zones: 5 monster zones + 5 spell/trap zones per player
            for row, off in ((0, 1.6), (1, 3.1)):
                for k in range(5):
                    zy = cy - 2.4 + k * 1.2
                    zx = cx + side * off
                    outline(nc, zx - 0.55, zy - 0.42, zx + 0.55, zy + 0.42, zt, 0.05, GLOW)
            # duelist circle at each end
            ring(nc, cx + side * (FIELD_W / 2 - 1.0), cy, 0.6, 0.08, zt, GLOW, seg=16)
            # glow strip on the platform edges
            nc.box((cx, cy + side * (FIELD_D / 2 + 0.005), FLG + 0.2), (FIELD_W - 0.4, 0.02, 0.06), GLOW)
        for side in (-1, 1):
            nc.box((cx + side * (FIELD_W / 2 + 0.005), cy, FLG + 0.2), (0.02, FIELD_D - 0.4, 0.06), GLOW)

    # bleachers along the back wall: 6 tiers x 0.42 m, aisles with 0.21 m steps
    tiers, rise = 6, 0.42
    yb0, yb1 = 18.0, GY1 - WT
    depth = (yb1 - yb0) / tiers
    for (bx0, bx1) in ((-26.6, -2.9), (2.9, 26.6)):
        mid = (bx0 + bx1) / 2
        segs = [(True, bx0 + 0.15, bx0 + 1.55), (False, bx0 + 1.55, mid - 0.7), (True, mid - 0.7, mid + 0.7),
                (False, mid + 0.7, bx1 - 1.55), (True, bx1 - 1.55, bx1 - 0.15)]
        for (is_aisle, xa, xb) in segs:
            for t in range(tiers):
                ya = yb0 + t * depth
                top = FLG + rise * (t + 1)
                if not is_aisle:
                    mb.box_mm((xa, ya, FLG), (xb, yb1, top), CONC, mats={"-y": "M_ArenaSeat"})
                    mb.box_mm((xa + 0.05, ya + 0.02, top), (xb - 0.05, ya + 0.48, top + 0.05), "M_ArenaSeat")
                else:
                    for h in range(2):
                        mb.box_mm((xa, ya + h * depth / 2, FLG), (xb, yb1, top - rise / 2 * (1 - h)), CONC,
                                  mats={"+z": "M_Paving"})
        # end walls of the bleacher block + rails
        for x in (bx0, bx1):
            mb.box_mm((x - 0.15, yb0, FLG), (x + 0.15, yb1, FLG + rise * tiers + 1.0), CONC)
        mb.railing([(bx0, yb1 - 0.3, FLG + rise * tiers), (bx1, yb1 - 0.3, FLG + rise * tiers)], 1.0, "M_Metal",
                   post_spacing=2.0)
    # front rail of the bleachers (gaps at aisles)
    # scoreboard above the bleachers
    with mb.at((0, GY1 - WT, 0)):
        mb.box((0, -0.25, 6.4), (10.4, 0.5, 3.4), "M_DarkMetal")
        mb.box((0, -0.52, 6.5), (9.6, 0.04, 2.6), "M_Screen")
        mb.box((0, -0.25, 4.5), (0.3, 0.5, 0.6), "M_DarkMetal")
    # dorm banners on the side walls
    cols = ("M_Fabric", "M_AcademyYellow", "M_ObeliskTrim")
    for sx in (-1, 1):
        for k, y in enumerate((-0.67, 6.0, 12.67)):
            x = sx * (GX1 - WT - 0.06)
            nc.box((x, y, 6.9), (0.04, 1.6, 2.6), cols[k])
            nc.box((x, y, 8.3), (0.08, 1.8, 0.1), "M_Gold")
            nc.box((x - sx * 0.01, y, 6.9), (0.04, 0.7, 0.7), FRAME)
    # shoe lockers along the side walls, next to the annexes
    for sx in (-1, 1):
        x = sx * (GX1 - WT - 0.3)
        mb.box((x, -7.5, FLG + 0.95), (0.6, 4.0, 1.9), "M_Metal")
        for k in range(8):
            mb.box((x - sx * 0.31, -9.25 + k * 0.5, FLG + 0.95), (0.02, 0.44, 1.8), "M_DarkMetal")
    # reception counter
    mb.box_mm((-9.5, -12.4, FLG), (-5.5, -11.6, FLG + 1.1), "M_Wood")
    mb.box_mm((-9.6, -12.5, FLG + 1.1), (-5.4, -11.5, FLG + 1.16), FRAME)


# ---------------------------------------------------------------- annexes: walk-in rooms inside the hall
def _floor(mb, x0, y0, x1, y1, mat):
    mb.box_mm((x0, y0, FLG - 0.01), (x1, y1, FLG + 0.006), mat, skip=("-z",))


def _trophy(mb, x, y, z, s=1.0, mat="M_Gold"):
    mb.cylinder((x, y, z), 0.06 * s, 0.04 * s, "M_DarkWood", seg=8)
    mb.lathe([(0.02 * s, 0.04 * s), (0.02 * s, 0.12 * s), (0.08 * s, 0.17 * s), (0.09 * s, 0.3 * s)], mat, seg=10,
             center=(x, y, z), cap_top=False)
    for sx in (-1, 1):
        mb.torus((x + sx * 0.1 * s, y, z + 0.23 * s), 0.035 * s, 0.01 * s, mat, seg=8, tube_seg=4)


def _duel_disk(mb, x, y, z, yaw):
    """Spare duel disk hanging on a wall rack (wall at +Y local)."""
    with mb.at((x, y, z), rot=yaw), mb.at((0, -0.08, 0), rot_x=90):
        mb.cylinder((0, 0, 0), 0.17, 0.05, "M_DuelDisk", seg=12)
        mb.cylinder((0, 0, 0.05), 0.07, 0.02, "M_AcademyRed", seg=10)
        mb.box((0.0, 0.3, 0.02), (0.14, 0.45, 0.04), "M_DuelDisk")             # blade
        for k in range(5):
            mb.box((-0.28 + 0.14 * k, 0.05 * (k % 2), 0.045), (0.11, 0.15, 0.01), "M_AcademyBlue")   # card zones


def _shower(mb, nc, x, y, yaw):
    """Wall shower: pipe, head, mixer, drain; (x, y) on the wall face, local -Y into the room."""
    with mb.at((x, y, FLG), rot=yaw), nc.at((x, y, FLG), rot=yaw):
        mb.cylinder((0, -0.05, 0.95), 0.02, 1.25, "M_Metal", seg=6)
        mb.beam((0, -0.05, 2.2), (0, -0.32, 2.12), 0.035, 0.035, "M_Metal")
        mb.cylinder((0, -0.36, 2.04), 0.08, 0.06, "M_Metal", seg=10)
        mb.box((0, -0.06, 1.05), (0.24, 0.06, 0.1), "M_Metal")
        for s in (-1, 1):
            mb.box((s * 0.09, -0.1, 1.05), (0.05, 0.06, 0.05), "M_AcademyRed" if s < 0 else "M_AcademyBlue")
        nc.box((0, -0.55, 0.008), (0.22, 0.22, 0.006), "M_DarkMetal")                    # drain
        nc.box((0.22, -0.04, 1.35), (0.18, 0.06, 0.03), "M_IntTrimWhite")               # soap shelf
        nc.cylinder((0.18, -0.04, 1.365), 0.025, 0.12, "M_IntFabricBlue", seg=6)
        nc.cylinder((0.26, -0.04, 1.365), 0.025, 0.1, "M_IntFabricPink", seg=6)


def _blinds(nc, xc, w=3.0, z0=FLG + 1.2, z1=FLG + 2.6, y=AY0 + 0.07):
    """Closed venetian blinds inside one of the low front windows."""
    nc.box((xc, y, z1 + 0.05), (w + 0.1, 0.06, 0.07), K.TRIM_WHITE)
    z = z1 - 0.04
    while z > z0 + 0.02:
        with nc.at((xc, y, z), rot_x=25):
            nc.box((0, 0, 0), (w, 0.05, 0.004), K.TRIM_WHITE)
        z -= 0.05
    nc.box((xc, y, z0 + 0.02), (w, 0.05, 0.025), K.TRIM_WHITE)
    for dx in (-w * 0.3, w * 0.3):
        nc.box((xc + dx, y, (z0 + z1) / 2 + 0.02), (0.004, 0.004, z1 - z0), K.TRIM_WHITE)


def _annexes(aset, mb, nc):
    z0, zc = FLG, FLG + AH
    TILE = "M_IntTileWhite"
    off_in, store_in, lock_in = K.PLASTER_SKY, "M_IntConcrete", K.PLASTER_WHITE
    dw = 2.1   # door height

    # ---------------- shells: walls (with real doorways), roof slab, blue band + signs on the hall side
    K.wall(aset, mb, (-PART - AT / 2, AY1), (-(GX1 - WT), AY1), z0, AH, AT, WALL, inner=off_in,
           openings=[K.Door(-PART - AT / 2 + 25.0, 1.0, dw, "office", trim=K.TRIM_WHITE, trim_in=K.TRIM_WHITE)])
    K.wall(aset, mb, (-AX, AY1), (-PART - AT / 2, AY1), z0, AH, AT, WALL, inner=store_in,
           openings=[K.Door(-AX + 19.8, 1.8, 2.3, "metal", double=True, trim="M_DarkMetal", trim_in="M_DarkMetal")])
    K.wall(aset, mb, (-AX, AY0), (-AX, AY1), z0, AH, AT, WALL, inner=store_in)
    K.wall(aset, mb, (-PART, AY0), (-PART, AY1 - AT), z0, AH, AT, store_in, inner=off_in)
    K.wall(aset, mb, (GX1 - WT, AY1), (PART + AT / 2, AY1), z0, AH, AT, WALL, inner=TILE)
    K.wall(aset, mb, (PART + AT / 2, AY1), (AX, AY1), z0, AH, AT, WALL, inner=lock_in,
           openings=[K.Door(PART + AT / 2 - 18.2, 1.0, dw, "academy_wood", trim=K.TRIM_WOOD, trim_in=K.TRIM_WOOD)])
    K.wall(aset, mb, (AX, AY1), (AX, AY0), z0, AH, AT, WALL, inner=lock_in)
    K.wall(aset, mb, (PART, AY1 - AT), (PART, AY0), z0, AH, AT, lock_in, inner=TILE,
           openings=[K.Door((AY1 - AT) - (-11.2), 1.0, dw, None, trim_in=K.TRIM_WHITE)])
    for sx in (-1, 1):
        lo, hi = sorted((sx * AX, sx * (GX1 - WT)))
        mb.box_mm((lo, AY0, zc), (hi, AY1, zc + 0.25), WALL, mats={"-z": K.CEIL, "+z": CONC})
        mb.box_mm((lo - 0.04, AY1 - 0.04, zc + 0.15), (hi + 0.04, AY1 + 0.04, zc + 0.3), FRAME)
        mb.box_mm((lo, AY1, zc - 0.45), (hi, AY1 + 0.025, zc - 0.15), "M_AcademyBlue")
        xe = sx * AX
        mb.box_mm((min(xe, xe - sx * 0.025), AY0, zc - 0.45), (max(xe, xe - sx * 0.025), AY1, zc - 0.15),
                  "M_AcademyBlue")
    for (x, txt, w) in ((-25.0, "COACH'S OFFICE", 1.5), (-19.8, "EQUIPMENT", 1.3), (18.2, "LOCKER ROOM", 1.4)):
        K.nameplate(mb, aset, x, AY1, FLG + dw + 0.42, 180.0, txt, mat=K.TRIM_WHITE, color=(0.1, 0.2, 0.5), w=w,
                    h=0.2)

    # ---------------- coach's office (west, by the window)
    x0, x1, y0, y1 = -(GX1 - WT), -PART - AT, AY0, AY1 - AT
    K.floor_planks(mb, x0, y0, x1, y1, FLG + 0.006)
    K.wainscot(mb, (x0, y0), (x1, y0), FLG, 0.1, K.TRIM_WOOD)
    aset.prop("SM_Int_OfficeDesk", (-27.6, -11.9, FLG), 0.0)
    aset.prop("SM_Int_OfficeChair", (-27.6, -12.75, FLG), 180.0)
    for x in (-28.1, -27.1):
        aset.prop("SM_Int_WoodChair", (x, -10.85, FLG), 0.0 + (x + 27.6) * 20)
    aset.prop("SM_Int_DeskLamp", (-28.15, -11.75, FLG + 0.76), 30.0)
    aset.prop("SM_Int_Books", (-27.0, -11.7, FLG + 0.76), 0.0)
    nc.box((-27.55, -12.0, FLG + 0.765), (0.42, 0.3, 0.01), "M_IntPaper")
    nc.box((-27.45, -11.95, FLG + 0.775), (0.3, 0.21, 0.01), "M_IntPoster2")
    _trophy(nc, -27.05, -12.1, FLG + 0.76, 0.8)
    for y in (-12.95, -11.95):
        aset.prop("SM_Int_Cabinet", (x0 + 0.24, y, FLG), 90.0)
    mb.box_mm((x1 - 0.5, -13.3, FLG), (x1, -11.3, FLG + 0.9), K.WOOD)                       # trophy sideboard
    mb.box_mm((x1 - 0.52, -13.32, FLG + 0.9), (x1, -11.28, FLG + 0.94), K.TRIM_WHITE)
    for k, y in enumerate((-13.0, -12.55, -12.05, -11.6)):
        _trophy(nc, x1 - 0.25, y, FLG + 0.94, (1.4, 1.0, 1.8, 1.1)[k], ("M_Gold", "M_Metal", "M_Gold", "M_RustMetal")[k])
    K.bulletin(nc, aset, x1, -12.3, FLG + 1.35, -90.0, 1.6, 0.9, title="TEAM NOTICES", rng_seed=5)
    K.blackboard(mb, nc, aset, -28.1, y1, FLG + 1.0, 0.0, 2.2, 1.0,
                 ["PRACTICE PLAN", "MON - deck building", "WED - field drills", "FRI - mock duels!"], size=0.11)
    aset.prop("SM_Int_WallClock", (-26.3, y1, FLG + 2.3), 0.0)
    aset.prop("SM_Int_PottedPlantB", (-24.25, -13.15, FLG), 0.0)
    aset.prop("SM_Int_Extinguisher", (x1 - 0.2, -10.4, FLG), -90.0)
    K.poster(nc, aset, x0, -12.45, FLG + 2.4, 90.0, 0.6, 0.8, "M_IntPoster3", "GET YOUR GAME ON!", (0.2, 0.1, 0.0), 0.06)
    K.panel_light(aset, nc, -26.5, -11.8, zc)
    K.camera(aset, "office", (-24.0, -10.6, FLG + 1.7), (-28.5, -12.9, FLG + 0.9), 18.0)

    # ---------------- equipment store
    x0, x1 = -PART, -AX - AT
    _floor(mb, x0, y0, x1, y1, "M_IntConcrete")
    for y in (-12.8, -11.55):
        aset.prop("SM_Int_SteelShelves", (x0 + 0.27, y, FLG), 90.0)
        aset.prop("SM_Int_SteelShelves", (x1 - 0.27, y - 0.2, FLG), -90.0)
    for k in range(4):   # stacked gym mats under the window
        mb.box_mm((-21.9 + 0.03 * k, y0 + 0.05, FLG + 0.15 * k), (-19.5 + 0.03 * k, y0 + 1.05, FLG + 0.15 * (k + 1) - 0.01),
                  "M_IntFabricBlue" if k % 2 == 0 else "M_IntFabricNavy")
    with mb.at((-20.7, -12.0, FLG)), nc.at((-20.7, -12.0, FLG)):    # ball cart
        mb.box_mm((-0.45, -0.3, 0.15), (0.45, 0.3, 0.2), "M_Metal")
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * 0.43, sy * 0.28, 0.45), (0.03, 0.03, 0.75), "M_Metal")
                nc.cylinder((sx * 0.4, sy * 0.25, 0.0), 0.05, 0.05, "M_Black", seg=8)
            mb.box((sx * 0.43, 0, 0.8), (0.03, 0.6, 0.03), "M_Metal")
        mb.box((0, -0.28, 0.8), (0.9, 0.03, 0.03), "M_Metal")
        mb.box((0, 0.28, 0.8), (0.9, 0.03, 0.03), "M_Metal")
        k = 0
        for iz in range(2):
            for ix in range(3):
                for iy in range(2):
                    nc.sphere((-0.26 + ix * 0.26, -0.13 + iy * 0.26, 0.33 + iz * 0.24), 0.12,
                              ("M_IntFabricOrange", "M_IntFabricWhite", "M_IntFabricYellow")[k % 3], seg=10, rings=6)
                    k += 1
    for k in range(4):   # traffic cones stack
        nc.cone((-18.1, -13.1, FLG + 0.06 * k), 0.16, 0.45, "M_IntFabricOrange", seg=10)
    nc.box((-18.1, -13.1, FLG + 0.01), (0.34, 0.34, 0.02), "M_IntFabricOrange")
    for (x, y, a) in ((-22.6, -10.6, 10), (-22.3, -13.15, -15), (-18.1, -12.0, 5)):
        aset.prop("SM_Int_Box", (x, y, FLG), a)
    aset.prop("SM_Int_HandTruck", (-17.9, -10.5, FLG), -90.0)
    aset.prop("SM_Int_Extinguisher", (x0 + 0.25, -10.35, FLG), 90.0)
    mb.box_mm((-22.95, y1 - 0.04, FLG + 1.1), (-21.45, y1, FLG + 2.1), K.WOOD)              # duel disk rack
    for k, x in enumerate((-22.6, -21.8)):
        for j, z in enumerate((FLG + 1.35, FLG + 1.8)):
            _duel_disk(mb, x + 0.1 * j, y1 - 0.04, z, 0.0)
    aset.text("SPARE DUEL DISKS", K.wall_point(-22.2, y1, 0.0, 0.03, FLG + 2.2), 0.0, size=0.09, color=(0.1, 0.2, 0.5))
    K.panel_light(aset, nc, -20.1, -11.8, zc)
    K.camera(aset, "store", (-17.5, -10.45, FLG + 1.8), (-22.2, -13.0, FLG + 0.6), 18.0)

    # ---------------- locker room
    x0, x1 = AX + AT, PART
    _floor(mb, x0, y0, x1, y1, "M_IntLinoleum")
    K.lockers(mb, nc, aset, 21.2, y1 - 0.235, 0.0, n=9)
    K.lockers(mb, nc, aset, x0 + 0.235, -12.3, 90.0, n=6, mat="M_IntSteelBlue")
    for y in (-11.75, -12.95):
        aset.prop("SM_Int_Bench", (20.6, y, FLG), 0.0)
    nc.box((20.1, -11.75, FLG + 0.47), (0.5, 0.32, 0.03), "M_IntFabricWhite")             # towels
    nc.box((21.2, -12.95, FLG + 0.47), (0.45, 0.3, 0.04), "M_IntFabricYellow")
    for (x, y, a, m) in ((19.0, -13.3, 10, "M_IntFabricRed"), (22.4, -12.9, 20, "M_IntFabricBlue")):   # sports bags
        with mb.at((x, y, FLG + 0.15), rot=a), mb.at((0, 0, 0), rot_y=90):
            mb.cylinder((0, 0, -0.3), 0.15, 0.6, m, seg=10)
    aset.prop("SM_Int_WetFloor", (22.6, -12.2, FLG), -60.0)
    K.poster(nc, aset, x0, -12.3, FLG + 2.4, 90.0, 0.9, 0.55, "M_IntPoster1", "KEEP IT CLEAN!", (1, 1, 1), 0.08)
    aset.text("SHOWERS", K.wall_point(x1, -11.2, -90.0, 0.02, FLG + 2.3), -90.0, size=0.14, color=(0.1, 0.2, 0.5))
    _blinds(nc, 20.5)
    K.panel_light(aset, nc, 20.1, -11.8, zc)
    K.camera(aset, "lockers", (17.4, -13.25, FLG + 1.7), (22.6, -10.7, FLG + 0.9), 18.0)

    # ---------------- showers
    x0, x1 = PART + AT, GX1 - WT
    _floor(mb, x0, y0, x1, y1, TILE)
    for (a, b, c, d) in ((x0 + 0.3, y0 + 0.3, x1 - 0.3, y0 + 0.36), (x0 + 0.3, y1 - 0.36, x1 - 0.3, y1 - 0.3)):
        mb.box_mm((a, b, FLG + 0.006), (c, d, FLG + 0.009), "M_IntTileBlue")
    gaps = {"w": [((y1) - (-11.2) - 0.6, (y1) - (-11.2) + 0.6)]}
    for (k, (p0, p1)) in (("s", ((x0, y0), (x1, y0))), ("e", ((x1, y0), (x1, y1))), ("n", ((x1, y1), (x0, y1))),
                          ("w", ((x0, y1), (x0, y0)))):
        K.wainscot(mb, p0, p1, FLG, 1.1, "M_IntTileBlue", cap=K.TRIM_WHITE, gaps=gaps.get(k, ()))
    for y in (-13.0, -12.0, -11.0):
        _shower(mb, nc, x1 - 0.024, y, -90.0)
    for x in (24.9, 26.0, 27.1, 28.2):
        _shower(mb, nc, x, y1 - 0.024, 0.0)
    for x in (25.45, 26.55, 27.65):   # stall dividers
        mb.box_mm((x - 0.025, y1 - 1.0, FLG + 0.15), (x + 0.025, y1, FLG + 2.0), "M_IntTileBlue")
    aset.prop("SM_Int_RubberDuck", (28.4, -12.6, FLG), 200.0)
    aset.prop("SM_Int_Bucket", (24.1, -13.2, FLG), 0.0)
    aset.prop("SM_Int_WetFloor", (24.6, -12.5, FLG), 30.0)
    _blinds(nc, 26.5)
    K.panel_light(aset, nc, 26.5, -11.8, zc)
    K.camera(aset, "showers", (23.8, -13.3, FLG + 1.8), (28.5, -10.7, FLG + 0.8), 18.0)


def _canopy_and_sign(mb, nc):
    # entrance canopy on four columns
    cz0, cz1 = 4.4, 4.9
    mb.box_mm((-9.0, -21.6, cz0), (9.0, GY0, cz1), WALL, mats={"-y": ROOF, "-x": ROOF, "+x": ROOF, "-z": FRAME})
    for x in (-8.2, -4.0, 4.0, 8.2):
        mb.box((x, -20.8, FLG + 0.2), (0.9, 0.9, 0.4), CONC)
        mb.cylinder((x, -20.8, FLG + 0.4), 0.28, cz0 - FLG - 0.4, FRAME, seg=14)
    for x in (-6.0, -2.0, 2.0, 6.0):
        for y in (-19.5, -16.5):
            nc.cylinder((x, y, cz0 - 0.04), 0.25, 0.03, "M_LampGlow", seg=10)
    # roof sign "DUEL GYM": blue board with yellow frame, braced to the roof
    yb = GY0 - OH - 0.45
    mb.box((0, yb, 10.3), (17.0, 0.3, 2.2), "M_AcademyBlue")
    mb.box((0, yb - 0.02, 11.45), (17.4, 0.36, 0.16), "M_AcademyYellow")
    mb.box((0, yb - 0.02, 9.15), (17.4, 0.36, 0.16), "M_AcademyYellow")
    for s in (-1, 1):
        mb.box((s * 8.62, yb - 0.02, 10.3), (0.16, 0.36, 2.46), "M_AcademyYellow")
    for x in (-6.0, -2.0, 2.0, 6.0):
        mb.beam((x, yb + 0.15, 9.6), (x, GY0 + 1.8, 11.0), 0.12, 0.12, "M_DarkMetal")
        mb.beam((x, yb + 0.15, 11.0), (x, GY0 + 1.5, 10.9), 0.12, 0.12, "M_DarkMetal")


def _grounds(mb, nc, rng):
    # entrance plaza (flush with the hall floor, one 0.2 m step at its edge)
    mb.box_mm((-21.0, -32.0, -0.5), (21.0, GY0, FLG), "M_Paving")
    for x in (-10.5, -4.5, 4.5, 10.5):
        flat_quad(mb, x - 0.1, -32.0, x + 0.1, GY0 - 0.3, FLG + 0.003, CONC)
    flat_quad(mb, -21.0, -24.1, 21.0, -23.9, FLG + 0.003, CONC)
    # concrete apron around the building + paths
    ap = 3.0
    mb.box_mm((GX0 - ap, GY0, -0.4), (GX0, GY1 + ap, 0.06), CONC)
    mb.box_mm((GX1, GY0, -0.4), (GX1 + ap, GY1 + ap, 0.06), CONC)
    mb.box_mm((GX0, GY1, -0.4), (GX1, GY1 + ap, 0.06), CONC)
    mb.box_mm((-1.8, GY1 + ap + 4.0, -0.4), (1.8, 64.0, 0.06), "M_Paving")      # to the beach
    mb.box_mm((-6.0, GY1 + ap, -0.4), (6.0, GY1 + ap + 4.0, 0.06), "M_Paving")
    mb.box_mm((GX1 + ap, -15.0, -0.4), (37.5, -11.0, 0.06), "M_Paving")   # to the outdoor court
    mb.box_mm((21.0, -31.0, -0.4), (40.0, -24.5, 0.06), "M_Paving")
    # back door (automatic metal double door, see _sockets): frame, canopy, step, exit light inside
    with mb.at((0, GY1, 0), rot=180):
        for s in (-1, 1):
            mb.box((s * (BACK_W / 2 + 0.06), -0.06, FLG + BACK_H / 2), (0.12, 0.12, BACK_H), "M_DarkMetal")
        mb.box((0, -0.15, FLG + 3.25), (4.2, 0.3, 0.2), FRAME)
        mb.box((0, -0.8, 3.4), (5.0, 1.6, 0.2), ROOF)
        mb.box_mm((-2.0, -1.2, 0.0), (2.0, 0.0, FLG - 0.07), CONC)
    with mb.at((0, GY1 - WT, 0)):
        for s in (-1, 1):
            mb.box((s * (BACK_W / 2 + 0.06), -0.04, FLG + BACK_H / 2), (0.12, 0.08, BACK_H), "M_DarkMetal")
        mb.box((0, -0.15, FLG + 3.25), (3.6, 0.1, 0.2), "M_LampGlow")

    # outdoor practice court
    cx0, cx1, cy0, cy1 = 37.5, 64.0, -25.0, 7.0
    mb.box_mm((cx0, cy0, -0.5), (cx1, cy1, 0.1), CONC)
    zl = 0.104
    outline(mb, cx0 + 1.0, cy0 + 1.0, cx1 - 1.0, cy1 - 1.0, zl, 0.1, LINE)
    for (fx, fy) in ((50.75, -16.0), (50.75, -2.0)):
        x0, x1, y0, y1 = fx - 6.0, fx + 6.0, fy - 3.0, fy + 3.0
        flat_quad(mb, x0, y0, x1, y1, zl - 0.002, "M_CourtPaint")
        outline(mb, x0, y0, x1, y1, zl, 0.12, LINE)
        flat_quad(mb, fx - 0.05, y0 + 0.12, fx + 0.05, y1 - 0.12, zl, LINE)
        for side in (-1, 1):
            for k in range(5):
                zy = fy - 2.2 + k * 1.1
                outline(mb, fx + side * 1.6 - 0.45, zy - 0.38, fx + side * 1.6 + 0.45, zy + 0.38, zl, 0.05, LINE)
            ring(mb, fx + side * 5.0, fy, 0.55, 0.08, zl, "M_AcademyYellow", seg=16)
    # low railing around three sides of the court
    mb.railing([(cx0 + 0.2, cy0 + 0.2, 0.1), (cx1 - 0.2, cy0 + 0.2, 0.1), (cx1 - 0.2, cy1 - 0.2, 0.1),
                (cx0 + 0.2, cy1 - 0.2, 0.1)], 1.1, "M_Metal", post_spacing=2.5)


def _sockets(aset, rng):
    # interior lights (always on) + field glow
    for x in (-18.0, 0.0, 18.0):
        for y in (-4.0, 10.0):
            aset.light((x, y, 11.0), (1.0, 0.97, 0.9), 9000.0, 30.0)
    for (cx, cy) in FIELDS:
        aset.light((cx, cy, 1.4), (0.25, 0.85, 1.0), 1500.0, 9.0)
        aset.interact("duel_field", (cx, cy, FLG + 0.5), 0.0, title="Practice Field",
                      text="Practice duels welcome!", radius=6.0)
    aset.light((0.0, -18.0, 4.0), (1.0, 0.9, 0.7), 4000.0, 14.0, night_only=True)
    aset.light((0.0, GY0 - OH - 2.5, 12.0), (1.0, 0.95, 0.85), 6000.0, 16.0, night_only=True)
    aset.light((0.0, GY1 + 2.0, 3.0), (1.0, 0.9, 0.7), 2500.0, 10.0, night_only=True)
    # texts
    aset.text("DUEL GYM", (0.0, GY0 - OH - 0.45 - 0.15 - 0.03, 10.3), 0.0, size=1.6, color=(1.0, 1.0, 1.0))
    aset.text("DUEL ACADEMY", (0.0, -21.6 - 0.03, 4.65), 0.0, size=0.38, color=(1.0, 1.0, 1.0))
    aset.text("HOME", (-3.4, GY1 - WT - 0.56, 7.4), 0.0, size=0.45, color=(1.0, 0.8, 0.2), emissive=True)
    aset.text("GUEST", (3.4, GY1 - WT - 0.56, 7.4), 0.0, size=0.45, color=(1.0, 0.8, 0.2), emissive=True)
    aset.text("8000", (-3.4, GY1 - WT - 0.56, 6.2), 0.0, size=0.8, color=(1.0, 0.3, 0.2), emissive=True)
    aset.text("8000", (3.4, GY1 - WT - 0.56, 6.2), 0.0, size=0.8, color=(1.0, 0.3, 0.2), emissive=True)
    # outdoor court
    for (fx, fy) in ((50.75, -16.0), (50.75, -2.0)):
        aset.prop("SM_DuelDummy", (fx + 5.0, fy, 0.1), -90.0)
        aset.interact("duel_field", (fx, fy, 0.5), 0.0, title="Outdoor Practice Court",
                      text="Duel the practice stands - or a friend!", radius=6.0)
    for y in (-22.0, -19.5, 4.0):
        aset.prop("SM_DuelDummy", (62.2, y, 0.1), -90.0)
    for y in (-19.0, -9.0, 1.0):
        aset.prop("SM_Bench", (38.8, y, 0.1), 90.0)
    for (x, y) in ((cx, cy) for cx in (36.5, 65.0) for cy in (-26.0, 8.0)):
        aset.prop("SM_LampPost", (x, y, 0.0), 0.0)
    aset.prop("SM_TrashBin", (38.8, -14.0, 0.1), 90.0)
    # plaza: flags, vending machines, benches, planters, lamps, palms
    for k, fl in enumerate(("SM_Flagpole_Red", "SM_Flagpole_Yellow", "SM_Flagpole_Blue")):
        aset.prop(fl, (-17.0 + 2.5 * k, -28.5, FLG), 0.0)
    aset.prop("SM_VendingMachine", (18.0, GY0 - 0.75, FLG), 0.0)
    aset.prop("SM_VendingMachine", (19.3, GY0 - 0.75, FLG), 0.0)
    aset.prop("SM_TrashBin", (20.6, GY0 - 0.7, FLG), 0.0)
    for x in (-14.0, 14.0):
        aset.prop("SM_Bench", (x, -25.0, FLG), 0.0)
    for x in (-11.0, 11.0):
        aset.prop("SM_Planter", (x, -17.0, FLG), 0.0)
    for (x, y) in ((-7.0, -36.0), (7.0, -36.0), (-7.0, -48.0), (7.0, -48.0), (-24.0, -18.0), (24.0, -18.0)):
        aset.prop("SM_LampPost", (x, y, 0.0), 0.0)
    for (x, y, a) in ((-36.0, -20.0, "SM_PalmTree_A"), (-38.0, 6.0, "SM_PalmTree_B"), (-35.0, 30.0, "SM_PalmTree_A"),
                      (36.0, 33.0, "SM_PalmTree_B"), (8.0, 36.0, "SM_PalmTree_A"), (-9.0, 40.0, "SM_PalmTree_B"),
                      (-26.0, -34.0, "SM_PalmTree_B"), (26.0, -36.0, "SM_PalmTree_A"), (68.0, -10.0, "SM_PalmTree_A")):
        aset.prop(a, (x, y, 0.0), rng.uniform(0, 360), round(rng.uniform(0.9, 1.15), 2))
    for (x, y) in ((-33.5, -10.0), (-33.5, 18.0), (33.5, 20.0), (-22.0, 31.0), (22.0, 31.0)):
        aset.prop("SM_Bush_A", (x, y, 0.0), rng.uniform(0, 360))
    for (x, y) in ((-4.0, 45.0), (4.0, 52.0), (-3.5, 58.0)):
        aset.prop("SM_BeachUmbrella" if x < 0 else "SM_BeachChair", (x, y, 0.0), rng.uniform(0, 360))
    # inside benches along the side walls
    for y in (-4.0, 6.0):
        aset.prop("SM_Bench", (GX0 + WT + 0.8, y, FLG), 90.0)
        aset.prop("SM_Bench", (GX1 - WT - 0.8, y, FLG), -90.0)
    # students
    aset.npc((-13.0, -2.5, FLG), 90.0, "slifer", 4.0)
    aset.npc((13.0, 8.0, FLG), -90.0, "ra", 4.0)
    aset.npc((-8.0, 20.5, FLG + 0.84), 180.0, "obelisk", 2.0)
    aset.npc((10.0, 21.5, FLG + 1.26), 180.0, "slifer", 2.0)
    aset.npc((45.0, -8.0, 0.1), 90.0, "ra", 6.0)
    aset.npc((6.0, -26.0, FLG), 0.0, "obelisk", 6.0)
    aset.npc((17.0, -16.5, FLG), 0.0, "white", 2.0)
    # ambience + interior camera
    aset.audio("A_Crowd", (0.0, 20.0, 3.0), radius=30.0, volume=0.5)
    aset.audio("A_Ocean", (0.0, 60.0, 2.0), radius=45.0)
    K.camera(aset, "court", (-24.0, -8.0, 5.5), (6.0, 12.0, 1.0), 18.0)
    # doors: sliding glass at the entrance, metal double door at the back
    aset.door((0.0, GY0 + WT / 2, FLG), 0.0, ENT_W, ENT_H, "glass", double=True)
    aset.door((0.0, GY1 - WT / 2, FLG), 180.0, BACK_W, BACK_H, "metal", double=True)


def build():
    rng = random.Random(720)
    aset = AssetSet("gym")
    hall = aset.mesh("Gym_Hall")
    roof = aset.mesh("Gym_Roof")
    inner = aset.mesh("Gym_Interior")
    grounds = aset.mesh("Gym_Grounds")
    nc = aset.mesh("Gym_NoCol")
    _shell(hall, nc)
    _curtain(hall)
    _canopy_and_sign(hall, nc)
    _roof(roof, nc)
    _interior(inner, nc, rng)
    _annexes(aset, aset.mesh("Gym_Annex"), aset.mesh("Gym_Annex_NoCol"))
    _grounds(grounds, nc, rng)
    _sockets(aset, rng)
    return aset


PLACEMENTS = {"gym": build}
