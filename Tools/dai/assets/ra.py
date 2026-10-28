"""
Ra Yellow Dorm - the tidy, European-style middle-class dormitory with the famous cafeteria.

Local space (metres): origin = centre of the pad at finished ground level, front (-Y) faces the
arriving academy path (which ends around (0, -45)); the sea lies behind (+Y), far beyond the pad.

Layout:
    x -22 .. 22, y -7 .. 7    three-storey main block, hip roof with dormers + two chimneys
    x  -5 ..  5, y -7.6       central bay with pediment + clock, portico (y -10.8) and steps
    x  22 .. 37, y -6 .. 6    single-storey cafeteria wing (walk-in), sea terrace behind it
    y -15.5 .. -9             paved forecourt;  walkway x -2 .. 2 from y -46 to the forecourt
    y  7 .. 8.5               wooden balconies on the sea side (floors 2 and 3)

Meshes: Ra_Main, Ra_Cafeteria, Ra_Grounds, Ra_NoCol.
"""

import math

from . import AssetSet
from .. import palette

palette.register({
    "M_RaStone": dict(kind="opaque", color=(0.80, 0.76, 0.67), rough=0.9, detail="Concrete", tiling=0.5),
    "M_RaChimney": dict(kind="opaque", color=(0.62, 0.34, 0.24), rough=0.9, detail="Bricks", tiling=0.5),
})

WALL, ROOF, TRIM, FRAME = "M_RaWall", "M_RaRoof", "M_RaTrim", "M_WindowFrame"
STONE, GLASS = "M_RaStone", "M_Glass"

W2, D2 = 22.0, 7.0               # half width / half depth of the main block
ZG = 0.75                        # ground floor level
FLOORS = (0.75, 4.25, 7.75)
ZC = 11.45                       # wall top (= cornice top)
ZRB = 11.75                      # roof base (top surface above the wall line)
RH = 5.0                         # roof height
RPITCH = RH / D2
YBAY = -7.6                      # central bay face
BAYX = 5.0
YPOR = -10.8                     # portico front
BAYS = [6.5 + 2.7 * i for i in range(6)]

# cafeteria wing
CX0, CX1, CY0, CY1 = 22.0, 37.0, -6.0, 6.0
CZ = 0.45
CWH = 4.2
FOUND = -4.0


def roof_z(y):
    """Top surface height of the main hip roof's long slopes at depth y."""
    return ZRB + (D2 - abs(y)) * RPITCH


# ------------------------------------------------------------------ helpers (local face frame:
# face at y = 0, outside towards -y, u along +x)
def tri_prism(mb, u, zb, w, h, d, mat):
    ax, bx, cx = u - w / 2, u + w / 2, u
    az, bz, cz = zb, zb, zb + h
    mb.poly([(ax, -d, az), (bx, -d, bz), (cx, -d, cz)], mat)
    mb.poly([(bx, -d, bz), (bx, 0, bz), (cx, 0, cz), (cx, -d, cz)], mat)
    mb.poly([(cx, -d, cz), (cx, 0, cz), (ax, 0, az), (ax, -d, az)], mat)
    mb.poly([(ax, -d, az), (ax, 0, az), (bx, 0, bz), (bx, -d, bz)], mat)


def window(mb, u, z, w, h, head="flat", door=False):
    fw = 0.08
    mb.box((u, -0.02, z + h / 2), (w, 0.04, h), GLASS, skip=("+y",))
    mb.box((u - w / 2 - fw / 2, -0.05, z + h / 2), (fw, 0.1, h + 2 * fw), FRAME, skip=("+y",))
    mb.box((u + w / 2 + fw / 2, -0.05, z + h / 2), (fw, 0.1, h + 2 * fw), FRAME, skip=("+y",))
    mb.box((u, -0.05, z + h + fw / 2), (w, 0.1, fw), FRAME, skip=("+y",))
    mb.box((u, -0.05, z - fw / 2), (w, 0.1, fw), FRAME, skip=("+y",))
    mb.box((u, -0.05, z + h / 2), (0.05, 0.08, h), FRAME, skip=("+y",))
    mb.box((u, -0.05, z + h * (0.72 if not door else 0.75)), (w, 0.08, 0.05), FRAME, skip=("+y",))
    if door:
        mb.box((u, -0.05, z + 0.45), (w, 0.08, 0.9), FRAME, skip=("+y",))   # solid kick panel
    # plaster surround
    s = 0.14
    mb.box((u - w / 2 - fw - s / 2, -0.03, z + h / 2), (s, 0.06, h + 2 * fw + 2 * s), TRIM, skip=("+y",))
    mb.box((u + w / 2 + fw + s / 2, -0.03, z + h / 2), (s, 0.06, h + 2 * fw + 2 * s), TRIM, skip=("+y",))
    mb.box((u, -0.03, z + h + fw + s / 2), (w + 2 * fw, 0.06, s), TRIM, skip=("+y",))
    if not door:
        mb.box((u, -0.1, z - fw - 0.05), (w + 0.55, 0.2, 0.1), TRIM, skip=("+y",))       # sill
        mb.box((u, -0.04, z - fw - 0.22), (w + 0.3, 0.08, 0.25), TRIM, skip=("+y",))     # apron
    top = z + h + fw + s
    if head == "flat":
        mb.box((u, -0.06, top + 0.12), (w + 0.5, 0.12, 0.24), TRIM, skip=("+y",))
        mb.box((u, -0.12, top + 0.28), (w + 0.75, 0.24, 0.1), TRIM, skip=("+y",))
    elif head == "ped":
        mb.box((u, -0.1, top + 0.06), (w + 0.6, 0.2, 0.12), TRIM, skip=("+y",))
        tri_prism(mb, u, top + 0.12, w + 0.6, 0.42, 0.16, TRIM)
    elif head == "key":
        mb.box((u, -0.07, top - 0.05), (0.26, 0.14, 0.36), TRIM, skip=("+y",))


def quoins(mb, u_edge, direction, z0, z1, phase=0):
    k = 0
    z = z0
    while z + 0.42 <= z1 + 1e-3:
        long_ = (k + phase) % 2 == 0
        L = 0.85 if long_ else 0.5
        a, b = u_edge - 0.06 * direction, u_edge + L * direction
        mb.box(((a + b) / 2, -0.03, z + 0.21), (abs(b - a), 0.06, 0.42), TRIM, skip=("+y",))
        z += 0.48
        k += 1


def balusters(mb, p0, p1, h, mat, spacing=0.3, rail_w=0.2, vase=True):
    """Classical balustrade between two 2D points at height z (p = (x, y, z))."""
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    L = math.dist((x0, y0), (x1, y1))
    n = max(1, int(L / spacing))
    mb.beam((x0, y0, z0 + h - 0.06), (x1, y1, z1 + h - 0.06), rail_w, 0.12, mat)
    mb.beam((x0, y0, z0 + 0.06), (x1, y1, z1 + 0.06), rail_w * 0.9, 0.12, mat)
    for k in range(n):
        t = (k + 0.5) / n
        x, y, z = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t
        if vase:
            hh = h - 0.24
            prof = [(0.05, 0.0), (0.075, hh * 0.25), (0.045, hh * 0.55), (0.04, hh * 0.85), (0.06, hh)]
            mb.lathe(prof, mat, seg=8, cap_top=False, cap_bottom=False, center=(x, y, z + 0.12))
        else:
            mb.box((x, y, z + h / 2), (0.05, 0.05, h - 0.2), mat, skip=("+z", "-z"))


def wood_railing(mb, p0, p1, h, spacing=0.16):
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    L = math.dist((x0, y0), (x1, y1))
    n = max(1, int(L / spacing))
    mb.beam((x0, y0, z0 + h), (x1, y1, z1 + h), 0.12, 0.07, "M_Wood")
    mb.beam((x0, y0, z0 + 0.12), (x1, y1, z1 + 0.12), 0.07, 0.06, "M_Wood")
    for k in range(1, n):
        t = k / n
        mb.box((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + 0.12 + (h - 0.12) / 2),
               (0.045, 0.045, h - 0.15), "M_Wood", skip=("+z", "-z"))
    for t in (0.0, 1.0):
        mb.box((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (h + 0.04) / 2), (0.1, 0.1, h + 0.04), "M_DarkWood")


# ------------------------------------------------------------------ main block
def _main(aset, mb, nc):
    # plinth + body
    mb.box_mm((-W2 - 0.12, -D2 - 0.12, FOUND), (W2 + 0.12, D2 + 0.12, ZG), STONE)
    mb.box_mm((-W2, -D2, ZG), (W2, D2, ZC), WALL, skip=("-z",))
    mb.box_mm((-BAYX - 0.12, YBAY - 0.12, FOUND), (BAYX + 0.12, -D2, ZG), STONE)
    mb.box_mm((-BAYX, YBAY, ZG), (BAYX, -D2, ZRB), WALL, skip=("-z", "+y"))
    # base course + belt course + cornice (main block)
    def band(z0, z1, out, mat=TRIM):
        mb.box_mm((-W2 - out, -D2 - out, z0), (W2 + out, D2 + out, z1), mat)
    band(ZG - 0.14, ZG + 0.06, 0.18)
    band(FLOORS[1] - 0.2, FLOORS[1] + 0.02, 0.07)
    band(ZC - 0.6, ZC - 0.42, 0.1)
    band(ZC - 0.42, ZC, 0.34)
    mb.box_mm((-BAYX - 0.18, YBAY - 0.18, ZG - 0.14), (BAYX + 0.18, -D2, ZG + 0.06), TRIM)
    mb.box_mm((-BAYX - 0.07, YBAY - 0.07, FLOORS[1] - 0.2), (BAYX + 0.07, -D2, FLOORS[1] + 0.02), TRIM)
    mb.box_mm((-BAYX - 0.1, YBAY - 0.1, ZC - 0.6), (BAYX + 0.1, -D2, ZC - 0.42), TRIM)
    mb.box_mm((-BAYX - 0.34, YBAY - 0.34, ZC - 0.42), (BAYX + 0.34, -D2, ZC), TRIM)
    # rusticated ground floor lines on the central bay
    for k in range(6):
        z = ZG + 0.55 * (k + 1)
        mb.box_mm((-BAYX - 0.02, YBAY - 0.02, z - 0.03), (BAYX + 0.02, YBAY + 0.01, z), STONE)

    # ---------------- front facade
    heads = ("flat", "ped", "key")
    with mb.at((0, -D2, 0)):
        for fi, zf in enumerate(FLOORS):
            h = 1.9 if fi < 2 else 1.6
            for x in BAYS:
                for s in (-1, 1):
                    window(mb, s * x, zf + 0.85, 1.2, h, heads[fi])
        for u, d in ((W2, -1), (-W2, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65)
    with mb.at((0, YBAY, 0)):
        for fi, zf in enumerate(FLOORS[1:]):
            for x in (-3.0, 3.0):
                window(mb, x, zf + 0.85, 1.2, 1.9 if fi == 0 else 1.6, "ped" if fi == 0 else "key")
        window(mb, 0.0, FLOORS[1] + 0.05, 1.4, 2.6, "ped", door=True)   # French door onto the portico
        window(mb, 0.0, FLOORS[2] + 0.85, 1.2, 1.6, "key")
        for u, d in ((BAYX, -1), (-BAYX, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65, phase=1)
        # main double door
        dw, dh = 2.0, 2.7
        mb.box((0, -0.03, ZG + dh / 2), (dw, 0.06, dh), "M_DarkWood", skip=("+y",))
        for sx in (-0.5, 0.5):
            for zz in (ZG + 0.7, ZG + 1.9):
                mb.box((sx, -0.07, zz), (0.7, 0.03, 0.85 if zz < 1.5 else 1.0), "M_Wood")
        mb.box((0, -0.065, ZG + dh / 2), (0.03, 0.04, dh), "M_Black")
        for sx in (-0.12, 0.12):
            mb.box((sx, -0.1, ZG + 1.15), (0.04, 0.05, 0.3), "M_Gold")
        for sx in (-dw / 2 - 0.12, dw / 2 + 0.12):
            mb.box((sx, -0.08, ZG + (dh + 0.75) / 2), (0.24, 0.16, dh + 0.75), TRIM)
        mb.box((0, -0.02, ZG + dh + 0.37), (dw, 0.04, 0.55), GLASS)                     # transom
        mb.box((0, -0.08, ZG + dh + 0.06), (dw + 0.48, 0.16, 0.12), TRIM)
        mb.box((0, -0.08, ZG + dh + 0.72), (dw + 0.48, 0.16, 0.12), TRIM)
        for sx in (-0.5, 0.0, 0.5):
            mb.box((sx, -0.05, ZG + dh + 0.37), (0.04, 0.06, 0.55), FRAME)
        # wall lanterns either side of the door
        for sx in (-1.75, 1.75):
            mb.box((sx, -0.1, ZG + 2.35), (0.1, 0.2, 0.1), "M_DarkMetal")
            mb.box((sx, -0.25, ZG + 2.3), (0.26, 0.26, 0.05), "M_DarkMetal")
            mb.cone((sx, -0.25, ZG + 2.75), 0.2, 0.18, "M_DarkMetal", seg=4)
            nc.box((sx, -0.25, ZG + 2.52), (0.2, 0.2, 0.42), "M_LampGlow")
    for sx in (-1.75, 1.75):
        aset.light((sx, YBAY - 0.6, ZG + 2.4), (1.0, 0.82, 0.55), 3500.0, 8.0, night_only=True)

    # ---------------- central pediment with clock (cross gable)
    ph = 2.7
    mb.gable_roof((0.0, (YBAY - 2.6) / 2, ZRB), 2 * BAYX + 0.0, abs(YBAY - (-2.6)), ph, ROOF,
                  overhang=0.35, thick=0.3, gable_mat=WALL, ridge_axis="y")
    with mb.at((0, YBAY, 0)):
        # raking cornices + base cornice of the pediment
        mb.box((0, -0.2, ZRB + 0.06), (2 * BAYX + 0.3, 0.4, 0.14), TRIM)
        for s in (-1, 1):
            mb.beam((s * (BAYX + 0.25), -0.25, ZRB - 0.3), (0, -0.25, ZRB + ph * (BAYX + 0.25) / BAYX - 0.3),
                    0.5, 0.24, TRIM)
        # clock
        cz = ZRB + 1.1
        with mb.at((0, -0.02, cz), rot_x=90):
            mb.cylinder((0, 0, 0), 0.92, 0.12, "M_Gold", seg=28)
            mb.cylinder((0, 0, 0.12), 0.8, 0.04, TRIM, seg=28)
        for k in range(12):
            a = k / 12 * math.tau
            l = 0.16 if k % 3 == 0 else 0.08
            with mb.at((math.sin(a) * 0.68, -0.19, cz + math.cos(a) * 0.68), rot_y=math.degrees(a)):
                mb.box((0, 0, 0), (0.04, 0.02, l), "M_Black")
        with mb.at((0, -0.21, cz), rot_y=300):      # hour hand (~10 o'clock)
            mb.box((0, 0, 0.2), (0.07, 0.02, 0.4), "M_Black")
        with mb.at((0, -0.22, cz), rot_y=60):       # minute hand
            mb.box((0, 0, 0.3), (0.05, 0.02, 0.6), "M_Black")
        with mb.at((0, -0.18, cz), rot_x=90):
            mb.cylinder((0, 0, 0), 0.06, 0.08, "M_Gold", seg=8)
        # gold sun emblem on the frieze under the pediment
        ez = ZRB - 0.35
        with mb.at((0, -0.36, ez), rot_x=90):
            mb.cylinder((0, 0, 0), 0.22, 0.05, "M_Gold", seg=16)
        for k in range(10):
            a = k / 10 * math.tau
            with mb.at((math.sin(a) * 0.32, -0.37, ez + math.cos(a) * 0.32), rot_y=math.degrees(a)):
                mb.box((0, 0, 0), (0.06, 0.03, 0.14), "M_Gold")

    # ---------------- portico + steps
    mb.box_mm((-4.3, YPOR, FOUND), (4.3, YBAY - 0.12, ZG), STONE, mats={"+z": "M_Paving"})
    for k in range(2):
        y1 = YPOR - 0.36 * k
        mb.box_mm((-4.8, y1 - 0.36, FOUND), (4.8, y1, ZG - 0.25 * (k + 1)), STONE, mats={"+z": "M_Paving"})
    PZ1 = 3.75
    for x in (-3.55, -1.55, 1.55, 3.55):
        mb.column((x, YPOR + 0.45, ZG), 0.24, PZ1 - ZG, TRIM, seg=14, cap_mat=TRIM)
        mb.box((x, YBAY - 0.06, (ZG + PZ1) / 2), (0.5, 0.12, PZ1 - ZG), TRIM)          # pilaster
    FL1 = FLOORS[1]
    mb.box_mm((-4.25, YPOR, PZ1), (4.25, YBAY, FL1 - 0.12), TRIM)                      # entablature
    mb.box_mm((-4.4, YPOR - 0.15, FL1 - 0.12), (4.4, YBAY, FL1), TRIM)
    mb.box_mm((-4.25, YPOR - 0.02, PZ1 + 0.05), (4.25, YPOR, PZ1 + 0.1), "M_RaWall")
    aset.text("RA YELLOW DORM", (0, YPOR - 0.05, PZ1 + 0.24), 0.0, size=0.3, color=(0.55, 0.38, 0.08))
    mb.box_mm((-4.2, YPOR + 0.05, PZ1 - 0.02), (4.2, YBAY, PZ1), "M_RaWall")           # soffit
    # balustrade on the portico roof (balcony of the French door)
    bz = FL1
    balusters(mb, (-4.25, YPOR - 0.05, bz), (4.25, YPOR - 0.05, bz), 0.95, TRIM)
    balusters(mb, (-4.25, YPOR - 0.05, bz), (-4.25, YBAY, bz), 0.95, TRIM)
    balusters(mb, (4.25, YPOR - 0.05, bz), (4.25, YBAY, bz), 0.95, TRIM)
    for x in (-4.25, 4.25):
        mb.box((x, YPOR - 0.05, bz + 0.55), (0.32, 0.32, 1.1), TRIM)
        mb.cylinder((x, YPOR - 0.05, bz + 1.1), 0.18, 0.08, TRIM, seg=10)
        mb.sphere((x, YPOR - 0.05, bz + 1.3), 0.15, TRIM, seg=10, rings=6)
    # hanging lantern in the portico
    nc.box((0, (YPOR + YBAY) / 2, PZ1 - 0.35), (0.03, 0.03, 0.7), "M_Black")
    nc.box((0, (YPOR + YBAY) / 2, PZ1 - 0.9), (0.3, 0.3, 0.42), "M_LampGlow")
    nc.box((0, (YPOR + YBAY) / 2, PZ1 - 0.66), (0.4, 0.4, 0.06), "M_DarkMetal")
    aset.light((0, (YPOR + YBAY) / 2, PZ1 - 1.1), (1.0, 0.85, 0.6), 5000.0, 10.0, night_only=True)

    # ---------------- back facade (sea side): balconies with French doors
    groups = [(-20.0, -17.3), (-14.6, -11.9), (-9.2, -6.5), (-2.8, 0.0, 2.8), (6.5, 9.2), (11.9, 14.6),
              (17.3, 20.0)]
    with mb.at((0, D2, 0), rot=180):           # local u = -x
        for fi, zf in enumerate(FLOORS):
            for g in groups:
                for x in g:
                    if fi == 0:
                        if x == 0.0:
                            continue
                        window(mb, -x, zf + 0.85, 1.2, 1.9, "flat")
                    else:
                        window(mb, -x, zf + 0.06, 1.2, 2.45, "key", door=True)
        for u, d in ((W2, -1), (-W2, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65)
        # back door
        mb.box((0, -0.03, ZG + 1.3), (1.6, 0.06, 2.6), "M_DarkWood", skip=("+y",))
        mb.box((0, -0.07, ZG + 2.75), (2.2, 0.14, 0.18), TRIM)
        for sx in (-0.92, 0.92):
            mb.box((sx, -0.06, ZG + 1.35), (0.2, 0.12, 2.7), TRIM)
        mb.box((0.45, -0.08, ZG + 1.2), (0.05, 0.05, 0.25), "M_Gold")
    mb.box_mm((-2.2, D2, FOUND), (2.2, D2 + 1.4, ZG), STONE, mats={"+z": "M_Paving"})
    for k in range(2):
        y0 = D2 + 1.4 + 0.36 * k
        mb.box_mm((-2.2, y0, FOUND), (2.2, y0 + 0.36, ZG - 0.25 * (k + 1)), STONE, mats={"+z": "M_Paving"})
    mb.box((-1.4, D2 + 0.12, ZG + 2.4), (0.18, 0.24, 0.3), "M_DarkMetal")
    nc.box((-1.4, D2 + 0.3, ZG + 2.2), (0.18, 0.18, 0.3), "M_LampGlow")
    aset.light((-1.4, D2 + 0.9, ZG + 2.2), (1.0, 0.82, 0.55), 3000.0, 8.0, night_only=True)
    for fi, zf in enumerate(FLOORS[1:]):
        for g in groups:
            xa, xb = min(g) - 1.0, max(g) + 1.0
            y1 = D2 + 1.45
            mb.box_mm((xa, D2, zf - 0.2), (xb, y1, zf), "M_DarkWood", mats={"+z": "M_Wood"})
            for x in (xa + 0.25, xb - 0.25):
                mb.beam((x, D2, zf - 1.2), (x, y1 - 0.2, zf - 0.2), 0.12, 0.12, "M_DarkWood")
                mb.box((x, D2 + 0.08, zf - 0.75), (0.14, 0.16, 1.1), "M_DarkWood")
            wood_railing(mb, (xa + 0.05, y1 - 0.05, zf), (xb - 0.05, y1 - 0.05, zf), 1.0)
            wood_railing(mb, (xa + 0.05, D2 + 0.05, zf), (xa + 0.05, y1 - 0.05, zf), 1.0)
            wood_railing(mb, (xb - 0.05, D2 + 0.05, zf), (xb - 0.05, y1 - 0.05, zf), 1.0)
    # flower boxes + a towel on some balconies (no collision for the cloth/flowers)
    for k, (gx, fi) in enumerate(((-13.4, 1), (7.8, 2), (19.0, 1), (-18.9, 2), (0.0, 2))):
        zf = FLOORS[fi]
        mb.box((gx, D2 + 1.55, zf + 0.85), (1.1, 0.25, 0.25), "M_Wood")
        nc.box((gx, D2 + 1.55, zf + 1.02), (1.0, 0.2, 0.14),
               ("M_FlowerRed", "M_FlowerYellow", "M_FlowerWhite")[k % 3])
    nc.box((-7.8, D2 + 1.47, FLOORS[1] + 0.75), (0.7, 0.03, 0.6), "M_FlowerYellow")

    # ---------------- ends
    with mb.at((-W2, 0, 0), rot=-90):           # outward -x, u = -y
        for fi, zf in enumerate(FLOORS):
            for u in (-4.0, 0.0, 4.0):
                window(mb, u, zf + 0.85, 1.2, 1.9 if fi < 2 else 1.6, heads[fi])
        for u, d in ((D2, -1), (-D2, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65, phase=1)
    with mb.at((W2, 0, 0), rot=90):             # outward +x, u = y
        for u in (-4.0, 0.0, 4.0):
            window(mb, u, FLOORS[2] + 0.85, 1.2, 1.6, "key")
        for u, d in ((D2, -1), (-D2, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65, phase=1)

    # ---------------- roof: hip roof, dormers, chimneys
    mb.hip_roof((0, 0, ZRB), 2 * W2, 2 * D2, RH, ROOF, overhang=0.6, thick=0.3)
    ridge = W2 - D2
    mb.box((0, 0, ZRB + RH + 0.05), (2 * ridge + 0.3, 0.3, 0.14), "M_RaChimney")
    for xd in (-15.0, -9.0, 9.0, 15.0):
        for side in (-1, 1):
            with mb.at((xd, 0, 0), rot=0 if side < 0 else 180):
                yf = -4.6
                zb = roof_z(yf) - 0.3
                zt = 14.75
                mb.box_mm((-0.85, yf, zb), (0.85, -1.4, zt), WALL, skip=("-z",))
                mb.gable_roof((0, (yf - 1.4) / 2, zt), 1.7, abs(yf + 1.4), 0.75, ROOF, overhang=0.18,
                              thick=0.12, gable_mat=WALL, ridge_axis="y")
                with mb.at((0, yf, 0)):
                    window(mb, 0, zb + 0.5, 0.8, 0.75, head=None)
    for cx in (-6.5, 6.5):
        mb.box_mm((cx - 0.5, -0.6, ZRB + RH - 1.0), (cx + 0.5, 0.6, ZRB + RH + 1.6), "M_RaChimney")
        mb.box_mm((cx - 0.6, -0.7, ZRB + RH + 1.45), (cx + 0.6, 0.7, ZRB + RH + 1.7), TRIM)
        for dx in (-0.22, 0.22):
            mb.cylinder((cx + dx, 0, ZRB + RH + 1.7), 0.13, 0.4, ROOF, seg=10)
        if cx > 0:
            aset.emitter("smoke", (cx + 0.22, 0, ZRB + RH + 2.2), scale=0.4, rate=0.3)
    # hip + ridge caps
    hx, hy, hz = W2 + 0.6, D2 + 0.6, ZRB - 0.6 * RPITCH
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.beam((sx * hx, sy * hy, hz + 0.06), (sx * ridge, 0, ZRB + RH + 0.06), 0.22, 0.12, "M_RaChimney")


# ------------------------------------------------------------------ cafeteria wing
def _cafeteria(aset, mb, nc):
    mb.box_mm((CX0, CY0 - 0.1, FOUND), (CX1 + 0.1, CY1 + 0.1, CZ), STONE)
    ops = {
        0: [dict(u=1.8, w=2.0, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME),
            dict(u=4.5, w=2.0, z0=0.0, z1=2.85, frame=FRAME),
            dict(u=7.7, w=2.3, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME),
            dict(u=10.5, w=2.3, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME),
            dict(u=13.3, w=2.3, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME)],
        1: [dict(u=2.2, w=2.6, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME),
            dict(u=6.0, w=2.6, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME),
            dict(u=9.8, w=2.6, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME)],
        2: [dict(u=2.6, w=2.4, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME),
            dict(u=5.9, w=2.4, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME),
            dict(u=9.2, w=2.4, z0=0.75, z1=3.35, glass="M_GlassClear", frame=FRAME),
            dict(u=12.5, w=1.6, z0=0.0, z1=2.6, frame=FRAME)],
    }
    mb.room([(CX0, CY0), (CX1, CY0), (CX1, CY1), (CX0, CY1)], CZ, CWH, 0.25, WALL, openings=ops,
            floor_mat="M_MarbleFloor", inner_mat="M_CreamWall")
    zt = CZ + CWH
    mb.poly([(CX0, CY0, zt - 0.3), (CX0, CY1, zt - 0.3), (CX1, CY1, zt - 0.3), (CX1, CY0, zt - 0.3)],
            "M_WhiteWall")
    # window mullions (outside), pilasters, base, cornice
    def mull(p0, p1, specs):
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        ux, uy = dx / L, dy / L
        nx, ny = uy, -ux                       # outward normal
        for u, w in specs:
            for t in (-w / 6, w / 6):
                cx, cy = p0[0] + ux * (u + t), p0[1] + uy * (u + t)
                mb.box((cx + nx * 0.02, cy + ny * 0.02, CZ + 2.05), (0.07 if abs(nx) < 0.5 else 0.08,
                       0.08 if abs(nx) < 0.5 else 0.07, 2.6), FRAME)
            cx, cy = p0[0] + ux * u, p0[1] + uy * u
            mb.box((cx + nx * 0.02, cy + ny * 0.02, CZ + 2.75), (w if abs(nx) < 0.5 else 0.08,
                   0.08 if abs(nx) < 0.5 else w, 0.06), FRAME)
            mb.box((cx + nx * 0.1, cy + ny * 0.1, CZ + 0.68), (w + 0.4 if abs(nx) < 0.5 else 0.22,
                   0.22 if abs(nx) < 0.5 else w + 0.4, 0.1), TRIM)
    mull((CX0, CY0), (CX1, CY0), [(1.8, 2.0), (7.7, 2.3), (10.5, 2.3), (13.3, 2.3)])
    mull((CX1, CY0), (CX1, CY1), [(2.2, 2.6), (6.0, 2.6), (9.8, 2.6)])
    mull((CX1, CY1), (CX0, CY1), [(2.6, 2.4), (5.9, 2.4), (9.2, 2.4)])
    for x in (CX0 + 3.15, CX0 + 6.0, CX0 + 9.1, CX0 + 11.9, CX1):
        mb.box((x, CY0 - 0.05, (CZ + zt) / 2), (0.3, 0.14, CWH), TRIM)
    for y in (CY0, -1.9, 1.9, CY1):
        mb.box((CX1 + 0.05, y, (CZ + zt) / 2), (0.14, 0.3, CWH), TRIM)
    for x in (CX1 - 4.25, CX1 - 7.55, CX1 - 11.05):
        mb.box((x, CY1 + 0.05, (CZ + zt) / 2), (0.3, 0.14, CWH), TRIM)
    mb.box_mm((CX0, CY0 - 0.12, CZ - 0.1), (CX1 + 0.12, CY1 + 0.12, CZ + 0.18), TRIM)
    mb.box_mm((CX0, CY0 - 0.3, zt - 0.45), (CX1 + 0.3, CY1 + 0.3, zt - 0.15), TRIM)
    mb.box_mm((CX0, CY0 - 0.12, zt - 0.6), (CX1 + 0.12, CY1 + 0.12, zt - 0.45), TRIM)
    # gable roof, ridge along x, gable faces the sea-side terrace end (+x)
    mb.gable_roof(((CX0 + CX1) / 2, 0, zt), CX1 - CX0, CY1 - CY0, 2.6, ROOF, overhang=0.6, thick=0.25,
                  gable_mat=WALL)
    with mb.at((CX1, 0, 0), rot=90):
        with mb.at((0, -0.02, zt + 0.95), rot_x=90):
            mb.cylinder((0, 0, 0), 0.62, 0.08, "M_Gold", seg=20)
            mb.cylinder((0, 0, 0.08), 0.42, 0.04, "M_AcademyYellow", seg=20)
        for k in range(12):
            a = k / 12 * math.tau
            with mb.at((math.sin(a) * 0.82, -0.08, zt + 0.95 + math.cos(a) * 0.82), rot_y=math.degrees(a)):
                mb.box((0, 0, 0), (0.1, 0.05, 0.3 if k % 2 == 0 else 0.18), "M_Gold")
    # entrance: landing, steps, canopy, sign
    ex = CX0 + 4.5
    mb.box_mm((ex - 1.8, CY0 - 1.6, FOUND), (ex + 1.8, CY0, CZ), STONE, mats={"+z": "M_Paving"})
    mb.box_mm((ex - 1.8, CY0 - 1.95, FOUND), (ex + 1.8, CY0 - 1.6, 0.25), STONE, mats={"+z": "M_Paving"})
    mb.box_mm((ex - 1.9, CY0 - 1.9, 3.45), (ex + 1.9, CY0, 3.62), TRIM)
    mb.box_mm((ex - 1.95, CY0 - 2.0, 3.35), (ex + 1.95, CY0 - 1.9, 3.85), "M_AcademyYellow")
    for s in (-1, 1):
        mb.beam((ex + s * 1.6, CY0, 2.6), (ex + s * 1.6, CY0 - 1.6, 3.45), 0.1, 0.12, "M_DarkMetal")
    aset.text("CAFETERIA", (ex, CY0 - 2.03, 3.58), 0.0, size=0.32, color=(0.45, 0.25, 0.05))
    nc.box((ex, CY0 - 0.9, 3.4), (0.4, 0.4, 0.06), "M_LampGlow")
    aset.light((ex, CY0 - 1.0, 3.1), (1.0, 0.85, 0.6), 3500.0, 8.0, night_only=True)

    # ---------------- interior
    mb.box_mm((CX0 + 0.25, -4.6, CZ), (CX0 + 1.15, 3.6, CZ + 1.0), "M_ShopShelf")            # counter
    mb.box_mm((CX0 + 0.2, -4.7, CZ + 1.0), (CX0 + 1.25, 3.7, CZ + 1.06), "M_Marble")
    mb.box_mm((CX0 + 1.05, -4.5, CZ + 1.06), (CX0 + 1.09, 3.5, CZ + 1.5), "M_GlassClear")
    for k in range(6):
        y = -3.8 + k * 1.3
        mb.box_mm((CX0 + 0.4, y, CZ + 1.06), (CX0 + 0.95, y + 0.9, CZ + 1.16), "M_Metal")
    mb.box_mm((CX0 + 0.25, -3.0, CZ + 2.1), (CX0 + 0.32, 2.0, CZ + 3.1), "M_DarkWood")       # menu board
    aset.text("TODAY: GRILLED FISH SET", (CX0 + 0.35, -0.5, CZ + 2.75), 90.0, size=0.2,
              color=(1.0, 0.95, 0.75))
    aset.text("CURRY  -  RAMEN  -  OMURICE", (CX0 + 0.35, -0.5, CZ + 2.4), 90.0, size=0.16,
              color=(1.0, 0.95, 0.75))
    for tx in (26.0, 29.4, 32.8):
        for ty in (-2.8, 0.4, 3.4):
            if (tx, ty) == (26.0, -2.8):
                continue
            mb.box_mm((tx - 0.6, ty - 0.6, CZ + 0.72), (tx + 0.6, ty + 0.6, CZ + 0.77), "M_Wood")
            mb.cylinder((tx, ty, CZ), 0.07, 0.72, "M_DarkMetal", seg=8)
            mb.cylinder((tx, ty, CZ), 0.3, 0.03, "M_DarkMetal", seg=10)
            for dx, dy in ((-0.85, 0), (0.85, 0), (0, -0.85), (0, 0.85)):
                cx, cy = tx + dx, ty + dy
                mb.box_mm((cx - 0.21, cy - 0.21, CZ + 0.42), (cx + 0.21, cy + 0.21, CZ + 0.47), "M_AcademyYellow")
                for lx in (-0.17, 0.17):
                    for ly in (-0.17, 0.17):
                        mb.box((cx + lx, cy + ly, CZ + 0.21), (0.04, 0.04, 0.42), "M_DarkMetal",
                               skip=("+z", "-z"))
                bx, by = (cx + (0.19 if dx > 0 else -0.19 if dx < 0 else 0),
                          cy + (0.19 if dy > 0 else -0.19 if dy < 0 else 0))
                if dx:
                    mb.box_mm((bx - 0.025, cy - 0.21, CZ + 0.47), (bx + 0.025, cy + 0.21, CZ + 0.95), "M_AcademyYellow")
                else:
                    mb.box_mm((cx - 0.21, by - 0.025, CZ + 0.47), (cx + 0.21, by + 0.025, CZ + 0.95), "M_AcademyYellow")
            mb.cylinder((tx + 0.25, ty, CZ + 0.77), 0.12, 0.05, FRAME, seg=10)
            mb.cylinder((tx - 0.2, ty + 0.2, CZ + 0.77), 0.04, 0.14, "M_GlassClear", seg=8)
    for lx in (26.0, 29.4, 32.8):
        for ly in (-1.2, 2.0):
            nc.box((lx, ly, zt - 0.6), (0.02, 0.02, 0.7), "M_Black")
            nc.cylinder((lx, ly, zt - 1.2), 0.32, 0.25, "M_AcademyYellow", seg=12, radius_top=0.12)
            nc.sphere((lx, ly, zt - 1.2), 0.12, "M_LampGlow", seg=8, rings=6)
    aset.light((29.4, 0.4, zt - 1.0), (1.0, 0.88, 0.65), 9000.0, 14.0, night_only=False)
    aset.light((23.5, -0.5, zt - 1.2), (1.0, 0.9, 0.7), 3000.0, 7.0, night_only=False)
    aset.special("camera", (35.8, -5.0, CZ + 1.7), target=(24.0, 2.0, CZ + 1.0), lens=18.0)

    # ---------------- sea-side terrace behind the cafeteria
    TY1 = CY1 + 6.0
    mb.box_mm((CX0 + 0.5, CY1 + 0.1, FOUND), (CX1 + 0.1, TY1, CZ), STONE, mats={"+z": "M_Paving"})
    for k in range(2):
        y0 = TY1 + 0.36 * k
        mb.box_mm((CX0 + 9.0, y0, FOUND), (CX0 + 12.0, y0 + 0.36, CZ - 0.15 * (k + 1)), STONE,
                  mats={"+z": "M_Paving"})
    balusters(mb, (CX0 + 0.6, TY1 - 0.12, CZ), (CX0 + 8.9, TY1 - 0.12, CZ), 0.9, TRIM, spacing=0.32)
    balusters(mb, (CX0 + 12.1, TY1 - 0.12, CZ), (CX1 - 0.02, TY1 - 0.12, CZ), 0.9, TRIM, spacing=0.32)
    balusters(mb, (CX1 - 0.02, CY1 + 0.15, CZ), (CX1 - 0.02, TY1 - 0.12, CZ), 0.9, TRIM, spacing=0.32)
    balusters(mb, (CX0 + 0.62, D2 + 0.3, CZ), (CX0 + 0.62, TY1 - 0.12, CZ), 0.9, TRIM, spacing=0.32)
    for x in (CX0 + 0.6, CX0 + 8.9, CX0 + 12.1, CX1 - 0.02):
        mb.box((x, TY1 - 0.12, CZ + 0.5), (0.3, 0.3, 1.0), TRIM)
    mb.box((CX0 + 0.62, D2 + 0.3, CZ + 0.5), (0.3, 0.3, 1.0), TRIM)
    nc.box((CX0 + 12.5, CY1 + 0.15, CZ + 2.6), (0.18, 0.18, 0.28), "M_LampGlow")
    aset.light((CX0 + 12.5, CY1 + 0.8, CZ + 2.4), (1.0, 0.82, 0.55), 3000.0, 8.0, night_only=True)


# ------------------------------------------------------------------ grounds
def _grounds(aset, mb, nc):
    # forecourt + walkway (thin paved slabs on top of the terrain)
    mb.box_mm((-24.0, -15.5, -0.4), (39.0, -11.0, 0.05), "M_Paving")
    mb.box_mm((-24.0, -11.0, -0.4), (-4.3, -9.0, 0.05), "M_Paving")
    mb.box_mm((4.3, -11.0, -0.4), (39.0, -9.0, 0.05), "M_Paving")
    mb.box_mm((CX0, -9.0, -0.4), (CX1 + 2.0, CY0, 0.05), "M_Paving")
    mb.box_mm((-2.0, -46.0, -0.4), (2.0, -15.5, 0.05), "M_Paving")
    for s in (-1, 1):
        mb.box_mm((s * 2.0 - 0.1, -46.0, -0.2), (s * 2.0 + 0.1, -15.5, 0.1), TRIM)
    mb.box_mm((-24.0, -15.6, -0.2), (-2.0, -15.4, 0.1), TRIM)
    mb.box_mm((2.0, -15.6, -0.2), (39.0, -15.4, 0.1), TRIM)
    # cross path to the benches
    mb.box_mm((-9.0, -31.0, -0.4), (9.0, -28.6, 0.04), "M_Paving")
    # flower beds along the facade
    for xa, xb in ((-22.0, -4.5), (4.5, 22.0)):
        mb.box_mm((xa, -9.0, -0.3), (xb, -D2, 0.3), STONE, mats={"+z": "M_Soil"})
    # hedges lining the walkway
    for s in (-1, 1):
        for ya, yb in ((-43.5, -31.6), (-28.0, -17.0)):
            x = s * 3.0
            mb.box_mm((x - 0.45, ya, -0.1), (x + 0.45, yb, 0.85), "M_Hedge")
            mb.box_mm((x - 0.38, ya + 0.07, 0.85), (x + 0.38, yb - 0.07, 0.95), "M_Hedge")
    # low hedges framing the lawn in front of the forecourt
    for xa, xb in ((-23.0, -9.5), (9.5, 23.0)):
        mb.box_mm((xa, -17.0, -0.1), (xb, -16.2, 0.7), "M_Hedge")
    # round flower bed on each lawn
    for cx in (-14.0, 14.0):
        mb.cylinder((cx, -24.0, -0.2), 2.6, 0.5, STONE, seg=20, smooth=False)
        mb.cylinder((cx, -24.0, 0.3), 2.45, 0.02, "M_Soil", seg=20, cap_bottom=False)
    # sign board where the path arrives
    sx, sy = -7.5, -44.0
    mb.box((sx, sy, 0.35), (4.6, 0.7, 0.7), STONE)
    mb.box((sx, sy, 0.75), (4.8, 0.8, 0.1), TRIM)
    mb.box((sx, sy, 1.55), (4.2, 0.18, 1.3), "M_AcademyYellow")
    mb.box((sx, sy, 2.28), (4.5, 0.26, 0.16), TRIM)
    for dx in (-2.15, 2.15):
        mb.box((sx + dx, sy, 1.55), (0.2, 0.26, 1.5), TRIM)
    with mb.at((sx, sy - 0.12, 2.45), rot_x=90):
        mb.cylinder((0, 0, -0.05), 0.3, 0.2, "M_Gold", seg=16)
    aset.text("RA YELLOW DORM", (sx, sy - 0.115, 1.55), 0.0, size=0.5, color=(0.45, 0.22, 0.05))
    aset.text("RA YELLOW DORM", (sx, sy + 0.115, 1.55), 180.0, size=0.5, color=(0.45, 0.22, 0.05))
    aset.interact("sign", (sx, sy - 1.0, 1.0), 0.0, title="Ra Yellow Dorm",
                  text="Ra Yellow Dorm - comfortable rooms, a proper cafeteria, and at least one student "
                       "whose walls are covered in equations.")


def _sockets(aset):
    for y in (-40.0, -33.0, -26.0, -19.0):
        for s in (-1, 1):
            aset.prop("SM_LampPost", (s * 4.0, y, 0.0), 0.0 if s > 0 else 180.0)
    for x in (-18.0, 18.0, 30.0):
        aset.prop("SM_LampPost", (x, -13.0, 0.05), 0.0)
    for s in (-1, 1):
        aset.prop("SM_Bench", (s * 7.0, -32.3, 0.0), 180.0)
        aset.prop("SM_Bench", (s * 7.0, -27.3, 0.0), 0.0)
        aset.prop("SM_Planter", (s * 5.4, -11.2, 0.05), 0.0)
    aset.prop("SM_Bench", (-12.0, -14.6, 0.05), 180.0)
    aset.prop("SM_Bench", (12.0, -14.6, 0.05), 180.0)
    aset.prop("SM_Flagpole_Yellow", (-20.0, -20.5, 0.0), 0.0)
    aset.prop("SM_Bench", (30.6, -6.7, 0.05), 0.0)
    aset.prop("SM_Bench", (33.4, -6.7, 0.05), 0.0)
    aset.prop("SM_Planter", (23.4, -7.2, 0.05), 0.0)
    aset.prop("SM_TrashBin", (5.0, -14.8, 0.05), 0.0)
    aset.prop("SM_VendingMachine", (CX1 - 1.0, CY0 - 0.55, 0.05), 0.0)
    aset.prop("SM_TrashBin", (CX1 - 2.1, CY0 - 0.5, 0.05), 0.0)
    # cafeteria terrace furniture
    for x in (25.5, 30.0, 34.0):
        aset.prop("SM_PicnicTable", (x, 9.2, CZ), 90.0)
        aset.prop("SM_BeachUmbrella", (x, 9.2, CZ), 0.0)
    # beds along the facade
    for k, x in enumerate((-20.5, -17.0, -13.5, -10.0, -6.5, 6.5, 10.0, 13.5, 17.0, 20.5)):
        a = ("SM_FlowerBush_Yellow", "SM_FlowerBush_White", "SM_FlowerBush_Red")[k % 3]
        aset.prop(a, (x, -8.0, 0.3), k * 40.0, 0.8)
    for cx in (-14.0, 14.0):
        aset.prop("SM_BroadTree_C", (cx, -24.0, 0.3), cx * 3)
        for k in range(5):
            a = k / 5 * math.tau
            aset.prop("SM_FlowerBush_Yellow" if k % 2 else "SM_FlowerBush_Red",
                      (cx + math.cos(a) * 1.7, -24.0 + math.sin(a) * 1.7, 0.3), k * 70.0, 0.7)
    # trees and greenery on the pad
    for a, p in (("SM_BroadTree_A", (-34.0, -18.0)), ("SM_BroadTree_B", (-36.0, 8.0)),
                 ("SM_PalmTree_A", (44.0, -12.0)), ("SM_PalmTree_B", (46.0, 6.0)),
                 ("SM_BroadTree_A", (34.0, -30.0)), ("SM_BroadTree_C", (-26.0, -34.0)),
                 ("SM_BroadTree_C", (24.0, -38.0)), ("SM_PalmTree_A", (-30.0, 20.0)),
                 ("SM_BroadTree_B", (10.0, 24.0)), ("SM_PalmTree_B", (-8.0, 22.0)),
                 ("SM_BroadTree_C", (-26.0, 0.0))):
        aset.prop(a, (p[0], p[1], 0.0), (p[0] * 13) % 360)
    for a, p in (("SM_Bush_A", (-23.5, -8.0)), ("SM_Bush_A", (23.0, -14.5)), ("SM_Bush_B", (-23.5, 4.0)),
                 ("SM_Bush_B", (-12.0, 9.5)), ("SM_Bush_A", (8.0, 9.0)), ("SM_FlowerBush_Blue", (-5.0, 9.0)),
                 ("SM_FlowerBush_Blue", (5.0, 9.0)), ("SM_Bush_B", (40.0, 0.0)), ("SM_Bush_A", (-40.0, -6.0))):
        aset.prop(a, (p[0], p[1], 0.0), (p[0] * 29) % 360)
    aset.npc((-5.0, -20.0, 0.0), 30.0, dorm="ra", wander=8.0)
    aset.npc((9.0, -13.0, 0.05), 200.0, dorm="ra", wander=6.0)
    aset.npc((29.0, -8.5, 0.05), 0.0, dorm="ra", wander=5.0)
    aset.npc((32.0, 10.5, CZ), 90.0, dorm="ra", wander=3.0)
    aset.npc((28.0, 0.4, CZ), 90.0, dorm="ra", wander=2.0)
    aset.audio("A_Crowd", (29.5, 0.0, 1.5), radius=14.0, volume=0.35)
    aset.audio("A_Wind", (0.0, 0.0, 14.0), radius=40.0, volume=0.4)


def build():
    aset = AssetSet("ra")
    main = aset.mesh("Ra_Main")
    caf = aset.mesh("Ra_Cafeteria")
    grounds = aset.mesh("Ra_Grounds")
    nc = aset.mesh("Ra_NoCol")
    _main(aset, main, nc)
    _cafeteria(aset, caf, nc)
    _grounds(aset, grounds, nc)
    _sockets(aset)
    return aset


PLACEMENTS = {"ra": build}
