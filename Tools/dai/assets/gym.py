"""
Duel Gym - beachside sports hall with practice duel fields.

A 60 x 40 m hall with a segmented barrel roof (axis along X, crown 14.5 m),
a white-mullioned glass front, concrete piers, an entrance canopy and a big
roof sign. Inside (walkable through the 6 m wide entrance): wooden court with
line markings, two raised practice duel fields with glowing outlines and
bleachers along the back wall. Outside: entrance plaza, outdoor practice court
with duel dummies, and a path to the beach behind (+Y).

Local space: origin = pad centre at ground level, front faces -Y; the road
arrives at about (0, -60).
"""

import math
import random

from . import AssetSet
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
def _shell(mb, nc):
    # foundation slab down to -4 (top = court floor), concrete skirt outside
    mb.box_mm((GX0, GY0, -4.0), (GX1, GY1, FLG), CONC, mats={"+z": "M_CourtFloor"})
    mb.box_mm((GX0 - 0.35, GY0 - 0.35, -4.0), (GX1 + 0.35, GY1 + 0.35, 0.08), CONC)

    hz = EZ - FLG
    # front wall: big opening for the curtain wall, high windows in the white end bays
    win = lambda u: dict(u=u, w=3.0, z0=5.3, z1=8.1, glass=GLASS, frame=FRAME)
    front_ops = [dict(u=30.0, w=32.0, z0=0.0, z1=hz - 0.5)] + [win(u) for u in (3.5, 9.5, 50.5, 56.5)]
    front_ops += [dict(u=u, w=3.0, z0=1.2, z1=2.6, glass=GLASS, frame=FRAME) for u in (3.5, 9.5, 50.5, 56.5)]
    mb.wall((GX0, GY0), (GX1, GY0), FLG, hz, WT, WALL, openings=front_ops, inner_mat=WALL)
    # back wall (closed double door is decoration only)
    back_ops = [win(3.0 + 6.0 * k) for k in range(10) if k not in (4, 5)]
    mb.wall((GX1, GY1), (GX0, GY1), FLG, hz, WT, WALL, openings=back_ops, inner_mat=WALL)
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
                    mb.box((o["u"], WT / 2, o["z0"] + h * 0.62), (o["w"], WT + 0.08, 0.1), FRAME)

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
                    mb.box((u, -0.2, (EZ - 0.2) / 2), (0.8, 0.4, EZ - 0.2), CONC, skip=("+y",))
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
    # parked sliding door leaves (open, behind the fixed glass)
    for s in (-1, 1):
        mb.box((s * 4.4, y + 0.3, (FLG + 3.8) / 2), (2.9, 0.06, 3.6), GLASS)
        mb.box((s * 4.4, y + 0.3, FLG + 0.05), (2.9, 0.1, 0.1), FRAME)


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
    for (x0, y0, x1, y1) in ((GX0 + WT, GY0 + WT, GX0 + WT + 0.06, GY1 - WT), (GX1 - WT - 0.06, GY0 + WT, GX1 - WT, GY1 - WT),
                             (GX0 + WT, GY1 - WT - 0.06, GX1 - WT, GY1 - WT)):
        mb.box_mm((x0, y0, FLG), (x1, y1, FLG + 1.8), "M_Wood")
    for (a, b) in ((GX0 + WT, -16.5), (16.5, GX1 - WT)):
        mb.box_mm((a, GY0 + WT, FLG), (b, GY0 + WT + 0.06, FLG + 1.8), "M_Wood")

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
    # shoe lockers in the front corners
    for sx in (-1, 1):
        x = sx * (GX1 - WT - 0.3)
        mb.box((x, -9.0, FLG + 0.95), (0.6, 7.0, 1.9), "M_Metal")
        for k in range(14):
            mb.box((x - sx * 0.31, -12.25 + k * 0.5, FLG + 0.95), (0.02, 0.44, 1.8), "M_DarkMetal")
    # reception counter
    mb.box_mm((-9.5, -12.4, FLG), (-5.5, -11.6, FLG + 1.1), "M_Wood")
    mb.box_mm((-9.6, -12.5, FLG + 1.1), (-5.4, -11.5, FLG + 1.16), FRAME)


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
    # back door (closed) + step
    with mb.at((0, GY1, 0), rot=180):
        mb.box((0, -0.06, FLG + 1.5), (3.2, 0.12, 3.0), "M_Metal")
        mb.box((0, -0.09, FLG + 1.5), (0.05, 0.08, 2.9), "M_DarkMetal")
        mb.box((0, -0.15, FLG + 3.25), (4.2, 0.3, 0.2), FRAME)
        mb.box((0, -0.8, 3.4), (5.0, 1.6, 0.2), ROOF)
    with mb.at((0, GY1 - WT, 0)):
        mb.box((0, -0.06, FLG + 1.5), (3.2, 0.12, 3.0), "M_Metal")
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
    aset.special("camera", (-24.0, -11.0, 5.5), target=(6.0, 12.0, 1.0), lens=18)


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
    _grounds(grounds, nc, rng)
    _sockets(aset, rng)
    return aset


PLACEMENTS = {"gym": build}
