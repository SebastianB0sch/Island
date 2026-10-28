"""
Slifer Red Dorm - the humble two-storey wooden apartment block on the west cliff.

Local space (metres): origin = centre of the pad at finished ground level, front (-Y) faces the
sea / cliff edge (cliff around y = -32), the academy path arrives behind the block at (0, +32).

Layout (x along the coast):
    x -19.9 .. -18   exterior staircase + landing (west end)
    x -18   ..   8   main block, 6 rooms per floor, upper walkway along the front (y -4.8 .. -3)
    x   8   ..  11   passage between the buildings (vending machine)
    x  11   ..  20   dining hall annex with a covered deck/porch (y -6.4 .. -3)
    y  -22           wooden fence along the cliff side (gap at x = 0)

Meshes: Slifer_Main, Slifer_Dining, Slifer_Yard, Slifer_NoCol.
"""

import math

from . import AssetSet
from .. import palette

palette.register({
    "M_SliferLaundryWhite": dict(kind="opaque", color=(0.95, 0.94, 0.90), rough=0.95, detail="Fabric", tiling=2.0),
    "M_SliferLaundryBlue": dict(kind="opaque", color=(0.28, 0.45, 0.78), rough=0.95, detail="Fabric", tiling=2.0),
    "M_SliferCurry": dict(kind="opaque", color=(0.78, 0.50, 0.14), rough=0.5, detail=None),
})

WALL, ROOF, TRIM, DOOR = "M_SliferWall", "M_SliferRoof", "M_SliferTrim", "M_SliferDoor"
GLASS, CONC = "M_Glass", "M_Concrete"

# ------------------------------------------------------------------ main block dimensions
X0, X1 = -18.0, 8.0          # main block along the coast
YF, YB = -3.0, 5.0           # front (sea) / back wall faces
ZG = 0.25                    # ground floor level (top of plinth)
Z2 = 3.0                     # upper walkway / upper floor level
ZW = 5.95                    # wall top at front and back walls
YR = 1.0                     # ridge line
PITCH = 0.27                 # shallow corrugated roof
ZR = ZW + (YR - YF) * PITCH + 0.05
YWK = -4.8                   # outer edge of the upper walkway
ROOF_X0, ROOF_X1 = -19.95, 8.55
ROOF_YF, ROOF_YB = -5.4, 5.6
NROOMS = 6
RW = (X1 - X0) / NROOMS

# dining hall annex
DX0, DX1, DY0, DY1 = 11.0, 20.0, -3.0, 5.0
DZ = 0.45                    # dining floor / deck level
DWH = 3.2                    # wall height
DECK_Y = -6.4

FOUND = -4.0                 # foundations reach down to here


def roof_z(y):
    return ZR - abs(y - YR) * PITCH


# ------------------------------------------------------------------ small helpers
def slab(mb, pts, thick, mat, bottom_mat=None, side_mat=None):
    """Thick slab from a top polygon given CCW seen from above (any slope)."""
    top = [tuple(map(float, p)) for p in pts]
    bot = [(p[0], p[1], p[2] - thick) for p in top]
    mb.poly(top, mat)
    mb.poly(list(reversed(bot)), bottom_mat or mat)
    n = len(top)
    for i in range(n):
        a, b = top[i], top[(i + 1) % n]
        al, bl = bot[i], bot[(i + 1) % n]
        mb.poly([al, bl, b, a], side_mat or mat)


def railing(mb, p0, p1, h, mat, baluster=0.22, post_every=1.6, skip=(), post_mat=None):
    """Railing between two 3D points on the walking surface: posts, top + bottom rail, balusters."""
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    length = math.dist((x0, y0), (x1, y1))
    if length < 1e-3:
        return
    pm = post_mat or mat

    def at(t):
        return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t)

    npost = max(1, int(round(length / post_every)))
    for k in range(npost + 1):
        x, y, z = at(k / npost)
        mb.box((x, y, z + (h + 0.06) / 2), (0.11, 0.11, h + 0.06), pm)
    mb.beam((x0, y0, z0 + h), (x1, y1, z1 + h), 0.12, 0.07, mat)
    mb.beam((x0, y0, z0 + 0.14), (x1, y1, z1 + 0.14), 0.06, 0.06, mat)
    nb = max(1, int(length / baluster))
    for k in range(1, nb):
        if k in skip:
            continue
        x, y, z = at(k / nb)
        mb.box((x, y, z + 0.14 + (h - 0.14) / 2), (0.04, 0.04, h - 0.17), mat, skip=("+z", "-z"))


def door(mb, u, z, w=0.9, h=2.0, panel=DOOR, frame=TRIM, knob_side=1):
    """Door on a wall face at local y=0 (outside = -y), u along local x."""
    mb.box((u, -0.03, z + h / 2), (w, 0.06, h), panel, skip=("+y",))
    mb.box((u - w / 2 - 0.05, -0.05, z + h / 2 + 0.05), (0.1, 0.1, h + 0.1), frame, skip=("+y",))
    mb.box((u + w / 2 + 0.05, -0.05, z + h / 2 + 0.05), (0.1, 0.1, h + 0.1), frame, skip=("+y",))
    mb.box((u, -0.05, z + h + 0.05), (w + 0.2, 0.1, 0.1), frame, skip=("+y",))
    mb.box((u + knob_side * (w / 2 - 0.12), -0.09, z + 1.0), (0.06, 0.06, 0.06), "M_Metal")
    mb.box((u, -0.065, z + 0.85), (0.3, 0.01, 0.05), "M_DarkMetal")   # mail slot


def window(mb, u, z, w, h, frame=TRIM, glass=GLASS, mullion=True, sill=True):
    """Framed window on a wall face at local y=0 (outside = -y)."""
    mb.box((u, -0.02, z + h / 2), (w, 0.04, h), glass, skip=("+y",))
    fw = 0.09
    mb.box((u - w / 2 - fw / 2, -0.05, z + h / 2), (fw, 0.1, h + 2 * fw), frame, skip=("+y",))
    mb.box((u + w / 2 + fw / 2, -0.05, z + h / 2), (fw, 0.1, h + 2 * fw), frame, skip=("+y",))
    mb.box((u, -0.05, z + h + fw / 2), (w, 0.1, fw), frame, skip=("+y",))
    mb.box((u, -0.05, z - fw / 2), (w, 0.1, fw), frame, skip=("+y",))
    if mullion:
        mb.box((u, -0.05, z + h / 2), (0.05, 0.08, h), frame, skip=("+y",))
    if sill:
        mb.box((u, -0.1, z - fw - 0.03), (w + 0.3, 0.2, 0.06), frame, skip=("+y",))


# ------------------------------------------------------------------ main block
def _main_block(aset, mb, nc):
    # foundation / plinth and the concrete apron under the walkway
    mb.box_mm((X0 - 0.1, YF - 0.1, FOUND), (X1 + 0.1, YB + 0.1, ZG), CONC)
    mb.box_mm((ROOF_X0 + 0.15, YWK - 0.2, FOUND), (X1 + 0.25, YF - 0.1, 0.1), CONC)
    # body (solid, closed rooms)
    mb.box_mm((X0, YF, ZG), (X1, YB, ZW), WALL, skip=("-z",))
    for x, sgn in ((X0, -1), (X1, 1)):
        tri = [(x, YF, ZW), (x, YB, ZW), (x, YR, ZR - 0.16)]
        mb.poly(tri if sgn > 0 else list(reversed(tri)), WALL)
        # gable vent
        mb.box((x + sgn * 0.04, YR, ZW + 0.42), (0.08, 0.9, 0.5), TRIM)
        for k in range(3):
            mb.box((x + sgn * 0.09, YR, ZW + 0.26 + k * 0.14), (0.04, 0.8, 0.05), "M_DarkWood")
    # corner boards, belt course and base trim
    for x in (X0, X1):
        for y in (YF, YB):
            mb.box((x, y, (ZG + ZW) / 2), (0.16, 0.16, ZW - ZG), TRIM)
    mb.box_mm((X0 - 0.04, YB, Z2 - 0.12), (X1 + 0.04, YB + 0.06, Z2 + 0.04), TRIM)
    for x, s in ((X0, -1), (X1, 1)):
        mb.box_mm((min(x, x + s * 0.06), YF, Z2 - 0.12), (max(x, x + s * 0.06), YB, Z2 + 0.04), TRIM)
    mb.box_mm((X0 - 0.04, YB, ZG), (X1 + 0.04, YB + 0.05, ZG + 0.18), TRIM)
    mb.box_mm((X0 - 0.04, YF - 0.05, ZG), (X1 + 0.04, YF, ZG + 0.18), TRIM)
    # room dividers on the front (pilasters between units)
    for i in range(1, NROOMS):
        x = X0 + i * RW
        mb.box((x, YF - 0.04, (ZG + ZW) / 2), (0.14, 0.08, ZW - ZG), TRIM, skip=("+y",))

    # ---------------- front: doors, windows, plates, porch lamps
    for floor, z in ((1, ZG), (2, Z2)):
        for i in range(NROOMS):
            x0 = X0 + i * RW
            ud, uw = x0 + 1.05, x0 + 2.95
            with mb.at((0, YF, 0)):
                door(mb, ud, z)
                window(mb, uw, z + 0.95, 1.4, 1.0)
                mb.box((ud, -0.07, z + 1.62), (0.26, 0.02, 0.13), "M_WindowFrame")   # number plate
            # porch lamp next to the door
            with mb.at((0, YF, 0)):
                mb.box((ud + 0.8, -0.06, z + 2.2), (0.14, 0.12, 0.08), "M_DarkMetal", skip=("+y",))
                mb.box((ud + 0.8, -0.16, z + 2.12), (0.18, 0.18, 0.04), "M_DarkMetal")
            nc.box((ud + 0.8, YF - 0.16, z + 2.0), (0.12, 0.12, 0.16), "M_LampGlow")
            aset.light((ud + 0.8, YF - 0.35, z + 1.9), (1.0, 0.78, 0.48), 2500.0, 6.0, night_only=True)
            aset.text(f"{floor}0{i + 1}", (ud, YF - 0.105, z + 1.62), 0.0, size=0.09, color=(0.15, 0.08, 0.05))
            if floor == 1:   # concrete stoop
                mb.box_mm((ud - 0.65, YF - 0.45, 0.0), (ud + 0.65, YF, ZG), CONC)

    # ---------------- back: small windows, patched boards, mailboxes, sign
    with mb.at((0, YB, 0), rot=180):
        # local u runs -x in world: u = -x
        for z in (ZG + 1.15, Z2 + 1.0):
            for i in range(NROOMS):
                x = X0 + i * RW + 2.4
                window(mb, -x, z, 1.0, 0.75)
                window(mb, -(X0 + i * RW + 0.9), z + 0.35, 0.5, 0.4, mullion=False)   # bathroom vent
        # weathered patch boards (run-down charm)
        for k, (u, zz, ang) in enumerate(((-(-6.4), 1.2, 3), (-(-6.1), 1.6, -2), (-(2.5), 4.7, 2))):
            with mb.at((u, -0.03, zz), rot_y=ang):
                mb.box((0, 0, 0), (1.1, 0.05, 0.22), "M_Wood")
                mb.box((-0.45, -0.03, 0), (0.04, 0.02, 0.04), "M_DarkMetal")
                mb.box((0.45, -0.03, 0), (0.04, 0.02, 0.04), "M_DarkMetal")
        # mailbox rack near the west corner
        for r in range(2):
            for c in range(3):
                u = -(X0 + 0.8 + c * 0.45)
                zz = 1.05 + r * 0.38
                mb.box((u, -0.16, zz), (0.4, 0.3, 0.32), DOOR)
                mb.box((u, -0.32, zz + 0.06), (0.24, 0.02, 0.04), "M_Black")
        mb.box((-(X0 + 1.25), -0.16, 0.86), (1.45, 0.34, 0.06), TRIM)
        # dorm sign on the back wall (faces the arriving path)
        mb.box((-(-5.0), -0.08, 4.45), (6.0, 0.12, 0.9), DOOR)
        mb.box((-(-5.0), -0.05, 4.45), (6.25, 0.1, 1.1), TRIM)
    aset.text("SLIFER RED DORM", (-5.0, YB + 0.17, 4.42), 180.0, size=0.62, color=(1.0, 0.96, 0.86))
    for x in (-8.2, -1.8):
        mb.box((x, YB + 0.25, 5.15), (0.08, 0.5, 0.06), "M_DarkMetal")
        nc.box((x, YB + 0.5, 5.07), (0.18, 0.12, 0.1), "M_LampGlow")
    aset.light((-5.0, YB + 1.2, 5.0), (1.0, 0.8, 0.55), 3000.0, 8.0, night_only=True)

    # end walls: windows (east end faces the dining hall passage)
    with mb.at((X1, 0, 0), rot=90):
        # local u = world y ; outward = +x
        for z in (ZG + 1.1, Z2 + 1.0):
            window(mb, -1.0 + 0.0, z, 1.0, 0.9)
    with mb.at((X0, 0, 0), rot=-90):
        # local u = -y ; outward = -x
        window(mb, 1.6, Z2 + 1.0, 1.0, 0.9)
        window(mb, 1.6, ZG + 1.1, 1.0, 0.9)

    # ---------------- upper walkway along the front
    slab(mb, [(X0, YWK, Z2), (X1, YWK, Z2), (X1, YF, Z2), (X0, YF, Z2)], 0.2, "M_Wood",
         bottom_mat="M_DarkWood", side_mat=TRIM)
    # stair landing (west end, joins the walkway)
    LX = ROOF_X0 + 0.25    # outer x of landing
    slab(mb, [(LX, YWK, Z2), (X0, YWK, Z2), (X0, 0.6, Z2), (LX, 0.6, Z2)], 0.2, "M_Wood",
         bottom_mat="M_DarkWood", side_mat=TRIM)
    # fascia + joists + edge beam + posts
    mb.box_mm((LX - 0.04, YWK - 0.08, Z2 - 0.32), (X1 + 0.04, YWK, Z2 + 0.03), TRIM)
    nj = int((X1 - X0) / 1.0)
    for k in range(nj + 1):
        x = X0 + (X1 - X0) * k / nj
        mb.box_mm((x - 0.05, YWK, Z2 - 0.34), (x + 0.05, YF, Z2 - 0.2), "M_DarkWood")
    post_y = YWK + 0.14
    posts = [X0 + i * RW for i in range(NROOMS + 1)] + [LX + 0.12]
    for x in posts:
        xx = min(max(x, LX + 0.12), X1 - 0.12)
        mb.box((xx, post_y, (0.1 + Z2 - 0.32) / 2), (0.18, 0.18, Z2 - 0.32 - 0.1), TRIM)
        mb.box((xx, post_y, Z2 - 0.4), (0.5, 0.12, 0.12), TRIM)   # knee brace block
    mb.box((LX + 0.12, 0.45, (0.0 + Z2 - 0.2) / 2), (0.18, 0.18, Z2 - 0.2), TRIM)
    # walkway railing (a couple of balusters missing - it's the Slifer dorm)
    RZ = Z2
    railing(mb, (LX + 0.06, YWK + 0.06, RZ), (X1 - 0.06, YWK + 0.06, RZ), 1.05, TRIM,
            skip=(37, 38, 81))
    railing(mb, (X1 - 0.06, YWK + 0.06, RZ), (X1 - 0.06, YF - 0.06, RZ), 1.05, TRIM)
    railing(mb, (LX + 0.06, YWK + 0.06, RZ), (LX + 0.06, 0.6, RZ), 1.05, TRIM)

    # ---------------- exterior staircase (west end, climbs from the back towards the sea)
    SX0, SX1 = LX + 0.06, X0 - 0.04            # stair width ~1.6 m
    n_tread, rise, run = 11, Z2 / 12.0, 0.3     # 12 risers of 0.25 m
    y_start = 0.6 + n_tread * run               # bottom edge (y = 3.9)
    for i in range(n_tread):
        zt = rise * (i + 1)
        ya, yb2 = y_start - run * (i + 1), y_start - run * i
        mb.box_mm((SX0 + 0.08, ya - 0.02, zt - 0.06), (SX1 - 0.02, yb2, zt), "M_Wood")
        mb.box_mm((SX0 + 0.08, yb2 - 0.03, zt - rise + 0.02), (SX1 - 0.02, yb2, zt - 0.06), "M_DarkWood")
    for x in (SX0 + 0.04, SX1 - 0.04):     # stringers just under the nosing line
        mb.beam((x, y_start + run, -0.2), (x, 0.6, Z2 - 0.2), 0.08, 0.3, TRIM)
    mb.box((SX0 + 0.04, y_start - 0.1, 0.5), (0.12, 0.12, 1.0), TRIM)
    railing(mb, (SX0 + 0.0, y_start - 0.05, 0.25), (SX0 + 0.0, 0.65, Z2), 1.0, TRIM, baluster=0.28)
    mb.box_mm((SX0 - 0.2, y_start - 0.3, -0.3), (SX1 + 0.1, y_start + 0.6, 0.02), CONC)   # landing pad

    # ---------------- roof
    zfe, zbe = roof_z(ROOF_YF), roof_z(ROOF_YB)
    RT = 0.15
    slab(mb, [(ROOF_X0, ROOF_YF, zfe), (ROOF_X1, ROOF_YF, zfe), (ROOF_X1, YR, ZR), (ROOF_X0, YR, ZR)], RT, ROOF)
    slab(mb, [(ROOF_X0, YR, ZR), (ROOF_X1, YR, ZR), (ROOF_X1, ROOF_YB, zbe), (ROOF_X0, ROOF_YB, zbe)], RT, ROOF)
    # standing seams (corrugated look)
    nseam = int((ROOF_X1 - ROOF_X0) / 0.9)
    for k in range(1, nseam):
        x = ROOF_X0 + (ROOF_X1 - ROOF_X0) * k / nseam
        mb.beam((x, ROOF_YF, zfe + 0.025), (x, YR, ZR + 0.025), 0.06, 0.05, ROOF)
        mb.beam((x, YR, ZR + 0.025), (x, ROOF_YB, zbe + 0.025), 0.06, 0.05, ROOF)
    mb.box((0.5 * (ROOF_X0 + ROOF_X1), YR, ZR + 0.03), (ROOF_X1 - ROOF_X0 + 0.1, 0.45, 0.1), TRIM)
    # fascia boards + verge boards
    mb.box_mm((ROOF_X0 - 0.06, ROOF_YF - 0.08, zfe - 0.32), (ROOF_X1 + 0.06, ROOF_YF, zfe + 0.03), TRIM)
    mb.box_mm((ROOF_X0 - 0.06, ROOF_YB, zbe - 0.32), (ROOF_X1 + 0.06, ROOF_YB + 0.08, zbe + 0.03), TRIM)
    for x in (ROOF_X0 - 0.03, ROOF_X1 + 0.03):
        mb.beam((x, ROOF_YF, zfe - 0.1), (x, YR, ZR - 0.1), 0.08, 0.3, TRIM)
        mb.beam((x, YR, ZR - 0.1), (x, ROOF_YB, zbe - 0.1), 0.08, 0.3, TRIM)
    # gutters + downpipes
    for y, z, s in ((ROOF_YF - 0.2, zfe - 0.28, -1), (ROOF_YB + 0.2, zbe - 0.28, 1)):
        mb.box_mm((ROOF_X0, y - 0.1, z - 0.06), (ROOF_X1, y + 0.1, z + 0.1), "M_Metal")
        for x in (ROOF_X0 + 0.25, ROOF_X1 - 0.25):
            mb.cylinder((x, y, 0.0), 0.06, z, "M_Metal", seg=8)
            mb.box((x, y + s * 0.0, 0.08), (0.16, 0.16, 0.16), "M_Metal")
    # rafter tails under the front eave
    for k in range(int((ROOF_X1 - ROOF_X0) / 1.3) + 1):
        x = ROOF_X0 + 0.2 + k * 1.3
        if x > ROOF_X1 - 0.1:
            break
        mb.beam((x, YF, roof_z(YF) - RT - 0.05), (x, ROOF_YF + 0.1, zfe - RT - 0.05), 0.08, 0.12, "M_DarkWood")

    # ---------------- roof clutter: water tank, vent pipes, antenna
    tx = -12.0
    for dx in (-0.6, 0.6):
        for dy in (-0.6, 0.6):
            zb = roof_z(YR + dy)
            mb.box((tx + dx, YR + dy, (zb + ZR + 0.7) / 2), (0.1, 0.1, ZR + 0.7 - zb), "M_RustMetal")
    mb.box((tx, YR, ZR + 0.75), (1.6, 1.6, 0.1), "M_RustMetal")
    mb.cylinder((tx, YR, ZR + 0.8), 0.78, 1.3, "M_Metal", seg=16)
    mb.cone((tx, YR, ZR + 2.1), 0.8, 0.3, "M_Metal", seg=16)
    for zz in (ZR + 1.05, ZR + 1.7):
        mb.cylinder((tx, YR, zz), 0.8, 0.06, "M_RustMetal", seg=16)
    mb.beam((tx + 0.78, YR, ZR + 1.0), (tx + 1.6, YR, ZR + 1.0), 0.08, 0.08, "M_Metal")
    mb.beam((tx + 1.6, YR, ZR + 1.0), (tx + 1.6, YR + 2.0, roof_z(YR + 2.0) + 0.06), 0.08, 0.08, "M_Metal")
    for vx, vy in ((-6.5, 3.2), (1.5, 3.2), (5.5, 3.0)):
        zb = roof_z(vy) - 0.1
        mb.cylinder((vx, vy, zb), 0.09, 1.1, "M_DarkMetal", seg=8)
        mb.cone((vx, vy, zb + 1.1), 0.18, 0.16, "M_DarkMetal", seg=8)
    ax, ay = 3.5, 2.0
    mb.cylinder((ax, ay, roof_z(ay) - 0.1), 0.04, 2.2, "M_Metal", seg=6)
    for k, ln in enumerate((1.6, 1.2, 0.8)):
        mb.box((ax, ay, roof_z(ay) + 1.4 + k * 0.3), (0.03, ln, 0.03), "M_Metal")

    # dorm name board hung on the outside of the walkway railing (faces the yard / sea)
    bx = -5.4
    mb.box((bx, YWK - 0.04, Z2 + 0.6), (4.1, 0.08, 0.8), WALL)
    mb.box((bx, YWK - 0.1, Z2 + 0.6), (3.9, 0.06, 0.64), DOOR)
    aset.text("SLIFER RED DORM", (bx, YWK - 0.155, Z2 + 0.58), 0.0, size=0.4, color=(1.0, 0.96, 0.86))
    # curtains behind some windows (front side)
    for floor, z in ((0, ZG), (1, Z2)):
        for i in range(NROOMS):
            k = floor * NROOMS + i
            if k % 3 == 1:
                continue
            uw = X0 + i * RW + 2.95
            mat = ("M_SliferLaundryWhite", "M_Fabric", "M_SliferLaundryBlue")[k % 3]
            side = -1 if k % 2 else 1
            mb.box((uw + side * 0.4, YF - 0.045, z + 0.95 + 0.5), (0.55, 0.01, 0.98), mat)
    # rusty patches on the corrugated roof
    for (px, py, w, d) in ((-15.5, -2.5, 1.8, 1.6), (-3.0, 3.6, 2.2, 1.2), (5.2, -3.8, 1.4, 1.5), (-8.0, -0.9, 1.0, 1.2)):
        y0, y1 = py - d / 2, py + d / 2
        z0, z1 = roof_z(y0) + 0.012, roof_z(y1) + 0.012
        mb.poly([(px - w / 2, y0, z0), (px + w / 2, y0, z0), (px + w / 2, y1, z1), (px - w / 2, y1, z1)], "M_RustMetal")
    # ---------------- futons airing over the walkway railing (no collision)
    for fx, mat in ((-9.6, "M_SliferLaundryBlue"), (-1.2, "M_SliferLaundryWhite"), (4.6, "M_SliferLaundryBlue")):
        nc.box((fx, YWK - 0.04, Z2 + 0.55), (1.4, 0.06, 1.0), mat)
        nc.box((fx, YWK + 0.06, Z2 + 1.11), (1.4, 0.26, 0.06), mat)
        nc.box((fx, YWK + 0.16, Z2 + 0.85), (1.4, 0.06, 0.5), mat)
    # potted plants on the apron
    for px in (-15.6, -6.2, 6.8):
        mb.cylinder((px, YF - 0.45, 0.1), 0.22, 0.4, "M_RustMetal", seg=10, radius_top=0.26)
        nc.sphere((px, YF - 0.45, 0.72), 0.32, "M_LeavesBush", seg=8, rings=6)
    # stair landing lamp
    nc.box((LX + 0.12, -1.0, Z2 + 2.1), (0.14, 0.14, 0.18), "M_LampGlow")
    mb.box((LX + 0.12, -1.0, Z2 + 2.25), (0.2, 0.2, 0.08), "M_DarkMetal")
    aset.light((LX + 0.5, -1.0, Z2 + 1.9), (1.0, 0.78, 0.48), 3000.0, 7.0, night_only=True)


# ------------------------------------------------------------------ dining hall annex
def _dining(aset, mb, nc):
    cx = (DX0 + DX1) / 2
    cy = (DY0 + DY1) / 2
    mb.box_mm((DX0 - 0.1, DY0 - 0.1, FOUND), (DX1 + 0.1, DY1 + 0.1, DZ), CONC)
    ops = {
        0: [dict(u=2.5, w=1.6, z0=0.0, z1=2.55, frame=TRIM),
            dict(u=6.6, w=2.8, z0=0.95, z1=2.35, glass="M_GlassClear", frame=TRIM)],
        1: [dict(u=2.0, w=1.6, z0=1.0, z1=2.3, glass="M_GlassClear", frame=TRIM),
            dict(u=4.9, w=1.6, z0=1.0, z1=2.3, glass="M_GlassClear", frame=TRIM),
            dict(u=7.1, w=0.9, z0=1.35, z1=2.2, glass="M_GlassClear", frame=TRIM)],
        2: [dict(u=4.5, w=1.0, z0=1.35, z1=2.2, glass="M_GlassClear", frame=TRIM)],
        3: [dict(u=4.5, w=1.6, z0=1.0, z1=2.3, glass="M_GlassClear", frame=TRIM)],
    }
    mb.room([(DX0, DY0), (DX1, DY0), (DX1, DY1), (DX0, DY1)], DZ, DWH, 0.2, WALL, openings=ops,
            floor_mat="M_Wood", inner_mat="M_CreamWall")
    zt = DZ + DWH
    mb.poly([(DX0, DY0, zt - 0.22), (DX0, DY1, zt - 0.22), (DX1, DY1, zt - 0.22), (DX1, DY0, zt - 0.22)],
            "M_CreamWall")
    # mullions in the big front window
    for u in (DX0 + 6.6 - 0.47, DX0 + 6.6 + 0.47):
        mb.box((u, DY0 + 0.1, DZ + 1.65), (0.06, 0.24, 1.4), TRIM)
    # corner boards + base trim
    for x in (DX0, DX1):
        for y in (DY0, DY1):
            mb.box((x, y, (DZ + zt) / 2), (0.16, 0.16, DWH), TRIM)
    mb.box_mm((DX0 - 0.04, DY1, DZ), (DX1 + 0.04, DY1 + 0.05, DZ + 0.15), TRIM)
    mb.box_mm((DX1, DY0, DZ), (DX1 + 0.05, DY1, DZ + 0.15), TRIM)
    mb.box_mm((DX0 - 0.05, DY0, DZ), (DX0, DY1, DZ + 0.15), TRIM)
    # gable roof, ridge along Y (gable faces the sea)
    RH = 1.6
    mb.gable_roof((cx, cy, zt), DX1 - DX0, DY1 - DY0, RH, ROOF, overhang=0.5, thick=0.15,
                  gable_mat=WALL, ridge_axis="y")
    hw = (DX1 - DX0) / 2 + 0.5
    drop = RH * 0.5 / ((DX1 - DX0) / 2)
    ze = zt - drop
    for s in (-1, 1):
        nseam = 11
        for k in range(1, nseam):
            y = DY0 - 0.5 + (DY1 - DY0 + 1.0) * k / nseam
            mb.beam((cx + s * hw, y, ze + 0.025), (cx, y, zt + RH + 0.025), 0.06, 0.05, ROOF)
        mb.box((cx + s * hw, cy, ze - 0.12), (0.08, DY1 - DY0 + 1.1, 0.28), TRIM)   # fascia
        mb.box((cx + s * (hw + 0.15), cy, ze - 0.3), (0.2, DY1 - DY0 + 1.0, 0.16), "M_Metal")  # gutter
        mb.cylinder((cx + s * (hw + 0.15), DY1 + 0.3, 0.0), 0.06, ze - 0.3, "M_Metal", seg=8)
    mb.box((cx, cy, zt + RH + 0.03), (0.4, DY1 - DY0 + 1.1, 0.1), TRIM)
    for y in (DY0 - 0.53, DY1 + 0.53):
        mb.beam((cx - hw, y, ze - 0.1), (cx, y, zt + RH - 0.1), 0.3, 0.08, TRIM)
        mb.beam((cx, y, zt + RH - 0.1), (cx + hw, y, ze - 0.1), 0.3, 0.08, TRIM)

    # "DINING HALL" board on the front gable
    mb.box((cx, DY0 - 0.05, zt + 0.42), (3.4, 0.1, 0.55), DOOR)
    mb.box((cx, DY0 - 0.03, zt + 0.42), (3.6, 0.06, 0.7), TRIM)
    aset.text("DINING HALL", (cx, DY0 - 0.13, zt + 0.40), 0.0, size=0.38, color=(1.0, 0.95, 0.82))

    # ---------------- covered deck / porch with steps
    mb.box_mm((DX0, DECK_Y, FOUND), (DX1, DY0 - 0.01, DZ), "M_DarkWood", mats={"+z": "M_Wood"})
    for k in range(int((DX1 - DX0) / 0.25)):
        x = DX0 + 0.125 + k * 0.25
        mb.box((x, (DECK_Y + DY0) / 2, DZ + 0.005), (0.015, DY0 - DECK_Y - 0.02, 0.012), "M_DarkWood")
    sx0, sx1 = 12.6, 14.4
    mb.box_mm((sx0, DECK_Y - 0.35, FOUND), (sx1, DECK_Y, 0.30), "M_Wood")
    mb.box_mm((sx0, DECK_Y - 0.7, FOUND), (sx1, DECK_Y - 0.35, 0.15), "M_Wood")
    railing(mb, (DX0 + 0.06, DECK_Y + 0.06, DZ), (sx0 - 0.1, DECK_Y + 0.06, DZ), 0.9, "M_Wood",
            post_mat=TRIM)
    railing(mb, (sx1 + 0.1, DECK_Y + 0.06, DZ), (DX1 - 0.06, DECK_Y + 0.06, DZ), 0.9, "M_Wood",
            post_mat=TRIM)
    railing(mb, (DX1 - 0.06, DECK_Y + 0.06, DZ), (DX1 - 0.06, DY0 - 0.1, DZ), 0.9, "M_Wood",
            post_mat=TRIM)
    # porch roof (lean-to) on four posts
    pz0, pz1 = 2.98, 3.38
    slab(mb, [(DX0 - 0.15, DECK_Y - 0.25, pz0), (DX1 + 0.15, DECK_Y - 0.25, pz0),
              (DX1 + 0.15, DY0, pz1), (DX0 - 0.15, DY0, pz1)], 0.1, ROOF, bottom_mat="M_DarkWood")
    mb.box_mm((DX0 - 0.2, DECK_Y - 0.33, pz0 - 0.28), (DX1 + 0.2, DECK_Y - 0.25, pz0 + 0.03), TRIM)
    mb.box_mm((DX0 - 0.15, DECK_Y + 0.0, pz0 - 0.36), (DX1 + 0.15, DECK_Y + 0.2, pz0 - 0.14), TRIM)
    for x in (DX0 + 0.1, sx0 - 0.1, sx1 + 0.1, DX1 - 0.1):
        mb.box((x, DECK_Y + 0.1, (DZ + pz0 - 0.3) / 2), (0.16, 0.16, pz0 - 0.3 - DZ), TRIM)
    # porch lamp + bench-like crate
    mb.box((DX0 + 1.2, DY0 - 0.06, DZ + 2.35), (0.14, 0.12, 0.08), "M_DarkMetal")
    nc.box((DX0 + 1.2, DY0 - 0.16, DZ + 2.2), (0.12, 0.12, 0.16), "M_LampGlow")
    aset.light((DX0 + 1.2, DY0 - 0.6, DZ + 2.1), (1.0, 0.78, 0.48), 3000.0, 7.0, night_only=True)

    # ---------------- interior: tables, counter window, kitchen
    for ty in (-1.7, 1.0):
        mb.box_mm((15.2, ty - 0.45, DZ + 0.72), (19.2, ty + 0.45, DZ + 0.78), "M_Wood")
        for lx in (15.6, 18.8):
            mb.box_mm((lx - 0.05, ty - 0.35, DZ), (lx + 0.05, ty + 0.35, DZ + 0.72), "M_DarkWood")
        for s in (-1, 1):
            by = ty + s * 0.72
            mb.box_mm((15.2, by - 0.16, DZ + 0.42), (19.2, by + 0.16, DZ + 0.47), "M_Wood")
            for lx in (15.5, 18.9):
                mb.box_mm((lx - 0.04, by - 0.12, DZ), (lx + 0.04, by + 0.12, DZ + 0.42), "M_DarkWood")
        for bx in (15.8, 16.9, 18.0):
            for s in (-1, 1):
                p = (bx, ty + s * 0.25, DZ + 0.78)
                mb.cylinder(p, 0.12, 0.07, "M_WindowFrame", seg=10, radius_top=0.15)
                mb.cylinder((p[0], p[1], p[2] + 0.055), 0.12, 0.01, "M_SliferCurry", seg=10)
    # partition with the serving counter window
    PY = 3.0
    mb.wall((DX0 + 0.2, PY), (DX1 - 0.2, PY), DZ, DWH, 0.15, "M_CreamWall",
            openings=[dict(u=4.0, w=3.0, z0=0.95, z1=2.1), dict(u=7.4, w=0.9, z0=0.0, z1=2.1)])
    mb.box_mm((DX0 + 0.2 + 2.5, PY - 0.3, DZ + 0.9), (DX0 + 0.2 + 5.5, PY + 0.45, DZ + 0.97), "M_Wood")
    mb.box_mm((DX0 + 0.2 + 2.4, PY - 0.08, DZ + 2.1), (DX0 + 0.2 + 5.6, PY, DZ + 2.4), DOOR)  # menu header
    aset.text("CURRY  -  RICE  -  MISO", (DX0 + 0.2 + 4.0, PY - 0.11, DZ + 2.25), 0.0, size=0.14,
              color=(1.0, 0.95, 0.8))
    # kitchen
    mb.box_mm((16.4, 4.05, DZ), (18.2, 4.8, DZ + 0.88), "M_DarkMetal")
    mb.cylinder((17.3, 4.4, DZ + 0.88), 0.36, 0.5, "M_Metal", seg=14)
    mb.cylinder((17.3, 4.4, DZ + 1.38), 0.37, 0.04, "M_SliferCurry", seg=14)
    mb.box_mm((16.5, 3.9, DZ + 2.2), (18.1, 4.8, DZ + 2.55), "M_Metal")         # hood
    mb.cylinder((17.3, 4.4, DZ + 2.55), 0.13, 3.1, "M_DarkMetal", seg=10)       # stove pipe
    mb.cylinder((17.3, 4.4, DZ + 5.65), 0.22, 0.12, "M_DarkMetal", seg=10)
    mb.cone((17.3, 4.4, DZ + 5.85), 0.3, 0.22, "M_DarkMetal", seg=10)
    mb.box_mm((11.3, 4.3, DZ), (12.2, 4.8, DZ + 1.9), "M_WindowFrame")          # fridge
    mb.box_mm((12.5, 4.25, DZ), (15.8, 4.8, DZ + 0.9), "M_ShopShelf")           # worktop
    mb.box_mm((13.2, 4.3, DZ + 0.9), (14.0, 4.75, DZ + 0.92), "M_Metal")         # sink
    mb.box_mm((12.5, 4.55, DZ + 1.5), (15.8, 4.8, DZ + 1.55), "M_ShopShelf")    # shelf
    for k, x in enumerate((12.8, 13.3, 13.9, 14.6, 15.2)):
        mb.cylinder((x, 4.67, DZ + 1.55), 0.1, 0.2 + 0.05 * (k % 2), "M_WindowFrame" if k % 2 else "M_Metal", seg=8)
    aset.emitter("steam", (17.3, 4.4, DZ + 6.1), scale=0.6, rate=0.6)
    # hanging lamps (no collision)
    for ly in (-1.7, 1.0):
        nc.box((17.2, ly, DZ + DWH - 0.35), (0.02, 0.02, 0.7), "M_Black")
        nc.cone((17.2, ly, DZ + DWH - 0.95), 0.35, 0.3, TRIM, seg=12)
        nc.sphere((17.2, ly, DZ + DWH - 0.95), 0.13, "M_LampGlow", seg=8, rings=6)
    aset.light((16.0, -0.4, DZ + 2.6), (1.0, 0.8, 0.55), 5000.0, 11.0, night_only=False)
    aset.light((17.3, 4.0, DZ + 2.4), (1.0, 0.85, 0.65), 2000.0, 5.0, night_only=False)
    aset.special("camera", (12.6, -2.4, DZ + 1.7), target=(17.5, 2.5, DZ + 1.0), lens=18.0)


# ------------------------------------------------------------------ yard / site dressing
def _yard(aset, mb, nc):
    # laundry poles with clothes
    lx0, lx1, ly = -14.5, -8.5, -10.5
    for x in (lx0, lx1):
        mb.box((x, ly, -0.2), (0.5, 0.5, 0.5), CONC)
        mb.cylinder((x, ly, 0.0), 0.05, 2.3, "M_Metal", seg=8)
        mb.box((x, ly, 2.25), (0.06, 1.3, 0.06), "M_Metal")
    for dy in (-0.55, 0.55):
        nc.beam((lx0, ly + dy, 2.22), (lx1, ly + dy, 2.22), 0.015, 0.015, "M_Black")
    clothes = [  # (x, dy, w, h, mat)
        (-13.6, -0.55, 0.7, 0.75, "M_Jacket"), (-12.6, -0.55, 0.55, 0.65, "M_SliferLaundryWhite"),
        (-11.7, -0.55, 0.5, 0.9, "M_Pants"), (-10.6, -0.55, 0.6, 0.6, "M_SliferLaundryWhite"),
        (-9.5, -0.55, 0.25, 0.3, "M_SliferLaundryBlue"), (-9.1, -0.55, 0.25, 0.3, "M_SliferLaundryWhite"),
        (-13.0, 0.55, 1.1, 0.5, "M_SliferLaundryBlue"), (-11.4, 0.55, 0.7, 0.75, "M_Jacket"),
        (-10.0, 0.55, 0.9, 0.55, "M_SliferLaundryWhite"),
    ]
    for x, dy, w, h, mat in clothes:
        nc.box((x, ly + dy, 2.2 - h / 2), (w, 0.03, h), mat)
        if mat == "M_Jacket":
            nc.box((x, ly + dy, 2.2 - 0.18), (w + 0.5, 0.03, 0.3), mat)        # sleeves
    # standing sign board where the academy path arrives
    sx, sy = -3.6, 24.0
    mb.box((sx, sy, 1.75), (3.6, 0.14, 1.0), DOOR)
    mb.box((sx, sy, 2.32), (3.9, 0.2, 0.14), TRIM)
    mb.box((sx, sy, 1.18), (3.9, 0.2, 0.14), TRIM)
    for dx in (-1.85, 1.85):
        mb.box((sx + dx, sy, 1.15), (0.16, 0.16, 2.3), "M_Wood")
        mb.box((sx + dx, sy, -0.2), (0.4, 0.4, 0.4), CONC)
    mb.pyramid((sx, sy, 2.39), 4.2, 0.5, 0.35, ROOF)
    aset.text("SLIFER RED DORM", (sx, sy + 0.1, 1.72), 180.0, size=0.48, color=(1.0, 0.96, 0.86))
    aset.text("SLIFER RED DORM", (sx, sy - 0.1, 1.72), 0.0, size=0.48, color=(1.0, 0.96, 0.86))
    aset.interact("sign", (sx, sy + 0.8, 1.0), 180.0, title="Slifer Red Dorm",
                  text="Home of Duel Academy's newest - and most underestimated - duelists. "
                       "Cheap rooms, curry for dinner, and the best ocean view on the island.")
    # mailbox on a post by the sign
    mx, my = 0.2, 24.6
    mb.box((mx, my, 0.55), (0.1, 0.1, 1.1), "M_Wood")
    mb.box((mx, my, 1.25), (0.38, 0.5, 0.32), DOOR)
    with mb.at((mx, my, 1.41), rot_x=90):
        mb.cylinder((0, 0, -0.25), 0.19, 0.5, DOOR, seg=12)
    mb.box((mx, my + 0.26, 1.28), (0.2, 0.02, 0.04), "M_Black")
    mb.box((mx + 0.21, my, 1.45), (0.03, 0.05, 0.3), "M_Gold")
    # stepping stones: path arrival -> passage between buildings -> yard
    stones = []
    for k in range(14):
        t = k / 13
        stones.append((0.4 + (9.5 - 0.4) * t + math.sin(k * 1.7) * 0.25, 22.5 + (6.2 - 22.5) * t))
    for k in range(6):
        stones.append((9.5 + math.sin(k * 2.1) * 0.2, 4.8 - k * 1.25))
    for k in range(7):
        stones.append((-1.0 - k * 2.4 + math.sin(k) * 0.3, 7.0 + math.cos(k * 1.3) * 0.3))
    for k, (x, y) in enumerate(stones):
        r = 0.42 + 0.08 * math.sin(k * 2.3)
        mb.cylinder((x, y, -0.15), r, 0.2, CONC, seg=8, angle0=k * 0.4, smooth=False)
    # rain barrel under the back downpipe
    rb = (ROOF_X1 - 0.25, ROOF_YB + 0.75)
    mb.cylinder((rb[0], rb[1], 0.0), 0.38, 0.95, "M_Wood", seg=12, radius_top=0.34, cap_mat="M_DarkWood")
    for zz in (0.15, 0.75):
        mb.cylinder((rb[0], rb[1], zz), 0.39, 0.06, "M_DarkMetal", seg=12)
    # fishing rod leaning on the fence + bucket (no collision)
    nc.beam((-5.6, -21.6, 0.0), (-5.0, -22.05, 2.9), 0.03, 0.03, "M_DarkWood")
    nc.cylinder((-5.5, -21.68, 0.6), 0.05, 0.08, "M_Metal", seg=8)
    nc.beam((-5.0, -22.05, 2.9), (-4.7, -22.6, 1.0), 0.004, 0.004, "M_WindowFrame")
    mb.cylinder((-4.6, -21.3, 0.0), 0.2, 0.32, "M_SliferLaundryBlue", seg=10, radius_top=0.24)
    # small fire pit with log seats in the yard (students hang out here)
    fp = (2.0, -13.5)
    for k in range(9):
        a = k / 9 * math.tau
        mb.box((fp[0] + math.cos(a) * 0.75, fp[1] + math.sin(a) * 0.75, 0.1), (0.35, 0.3, 0.25), "M_Rock")
    mb.cylinder((fp[0], fp[1], -0.05), 0.6, 0.08, "M_DarkConcrete", seg=10)
    for a in (0.3, 2.4, 4.3):
        with mb.at((fp[0] + math.cos(a) * 2.2, fp[1] + math.sin(a) * 2.2, 0.24), rot=math.degrees(a) + 90, rot_y=90):
            mb.cylinder((0, 0, -0.75), 0.24, 1.5, "M_Bark", seg=10)
    nc.box((fp[0], fp[1], 0.15), (0.7, 0.1, 0.1), "M_DarkWood")
    nc.box((fp[0], fp[1], 0.15), (0.1, 0.7, 0.1), "M_DarkWood")


# ------------------------------------------------------------------ sockets (props, npc, audio)
def _sockets(aset):
    # fence along the cliff side, gap at x = 0
    for k in range(7):
        aset.prop("SM_Fence_Wood", (-3.5 - 4.0 * k, -22.0, 0.0), 0.0)
        aset.prop("SM_Fence_Wood", (3.5 + 4.0 * k, -22.0, 0.0), 0.0)
    aset.prop("SM_Bench", (-9.0, -19.6, 0.0), 0.0)
    aset.prop("SM_Bench", (8.0, -19.4, 0.0), 0.0)
    aset.prop("SM_VendingMachine", (10.5, -1.6, ZG - 0.25), -90.0)
    aset.prop("SM_TrashBin", (10.55, -0.35, 0.0), -90.0)
    aset.prop("SM_Crate", (21.2, 3.6, 0.0), 0.0)
    aset.prop("SM_Crate", (21.2, 2.3, 0.0), 8.0)
    aset.prop("SM_Crate", (21.25, 3.5, 1.2), -6.0, 0.85)
    aset.prop("SM_Barrel", (21.1, 0.9, 0.0), 0.0)
    aset.prop("SM_Crate", (-6.4, -20.6, 0.0), 12.0, 0.7)
    aset.prop("SM_PicnicTable", (16.0, -12.0, 0.0), 0.0)
    aset.prop("SM_DuelDummy", (-3.0, -15.5, 0.0), 180.0)
    aset.prop("SM_Flagpole_Red", (-25.0, -12.0, 0.0), 0.0)
    aset.prop("SM_LampPost", (3.2, 25.0, 0.0), 180.0)
    aset.prop("SM_LampPost", (-22.5, 3.0, 0.0), 90.0)
    aset.prop("SM_TrashBin", (-21.8, -6.6, 0.0), 0.0)
    # vegetation
    for a, p, yaw in (("SM_PalmTree_A", (-27.0, -18.5), 30), ("SM_PalmTree_B", (26.0, -19.0), 200),
                      ("SM_PalmTree_A", (25.5, 9.0), 120), ("SM_BroadTree_A", (-25.0, 17.0), 0),
                      ("SM_BroadTree_A", (22.0, 22.0), 90), ("SM_BroadTree_C", (-13.0, 21.0), 0),
                      ("SM_BroadTree_C", (13.0, 15.0), 45)):
        aset.prop(a, (p[0], p[1], 0.0), yaw)
    for a, p in (("SM_Bush_A", (-21.5, 7.5)), ("SM_Bush_B", (-10.0, 6.4)), ("SM_Bush_B", (-3.0, 6.3)),
                 ("SM_Bush_A", (12.0, 6.8)), ("SM_FlowerBush_Red", (21.0, -5.2)),
                 ("SM_FlowerBush_Red", (11.2, -7.6)), ("SM_FlowerBush_Yellow", (-22.6, -2.8)),
                 ("SM_GrassClump_A", (-17.0, -21.0)), ("SM_GrassClump_A", (12.5, -21.2)),
                 ("SM_GrassClump_A", (20.0, -21.0)), ("SM_Rock_A", (-28.0, -9.0)), ("SM_Rock_B", (27.0, -4.0)),
                 ("SM_Fern_A", (7.2, 6.4)), ("SM_GrassClump_A", (-24.0, -21.3))):
        aset.prop(a, (p[0], p[1], 0.0), (p[0] * 37) % 360)
    # people + ambience
    aset.npc((-6.5, -13.0, 0.0), 0.0, dorm="slifer", wander=6.0)
    aset.npc((14.5, -9.0, 0.0), 160.0, dorm="slifer", wander=5.0)
    aset.npc((-4.0, 9.5, 0.0), 200.0, dorm="slifer", wander=8.0)
    aset.audio("A_Ocean", (0.0, -24.0, 0.0), radius=60.0)
    aset.audio("A_Wind", (0.0, -2.0, 7.0), radius=35.0, volume=0.5)
    aset.special("camera", (-24.0, -20.0, 1.7), target=(-5.0, -2.0, 3.0), lens=24.0)


def build():
    aset = AssetSet("slifer")
    main = aset.mesh("Slifer_Main")
    din = aset.mesh("Slifer_Dining")
    yard = aset.mesh("Slifer_Yard")
    nc = aset.mesh("Slifer_NoCol")
    _main_block(aset, main, nc)
    _dining(aset, din, nc)
    _yard(aset, yard, nc)
    _sockets(aset)
    return aset


PLACEMENTS = {"slifer": build}
