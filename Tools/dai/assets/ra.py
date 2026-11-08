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

Interior (walk-in, every exterior door leads somewhere):
    ground floor  x -5..5  entrance hall (reception / mail desk, notice board, Ra emblem, staircase,
                           back door to the sea side);  west: common lounge (fireplace, sofas, TV, books)
                           and the duel practice room;  east: corridor -> study room, dorm supervisor's
                           office, laundry and the dorm kitchen (pass door into the cafeteria servery)
    floors 2 + 3  x -5..5  stair hall + landing lounge (floor 2: French door onto the portico balcony,
                           floor 3: study library);  both wings: central corridor y -0.9..0.9 with twin
                           dorm rooms in front and behind (the back rooms open onto the balconies),
                           a washroom at the east front;  Bastion Misawa's room is 3F east, back (309)
    cafeteria     serving line + servery, kitchen pass door, dining tables, sea terrace door

Meshes: Ra_Main (shell), Ra_Cafeteria, Ra_Grounds, Ra_NoCol, Ra_Interior, Ra_Interior_NoCol.
"""

import math
import random
from contextlib import ExitStack, contextmanager

from . import AssetSet
from . import with_travel
from . import detail as DT
from . import interior as K
from .. import palette

palette.register({
    "M_RaStone": dict(kind="opaque", color=(0.80, 0.76, 0.67), rough=0.9, detail="Concrete", tiling=0.5),
    "M_RaChimney": dict(kind="opaque", color=(0.62, 0.34, 0.24), rough=0.9, detail="Bricks", tiling=0.5),
})

WALL, ROOF, TRIM, FRAME = "M_RaWall", "M_RaRoof", "M_RaTrim", "M_WindowFrame"
STONE, GLASS, GLASSC = "M_RaStone", "M_Glass", "M_GlassClear"

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
GROUPS = [(-20.0, -17.3), (-14.6, -11.9), (-9.2, -6.5), (-2.8, 0.0, 2.8), (6.5, 9.2), (11.9, 14.6),
          (17.3, 20.0)]
FRONT_X = sorted([-x for x in BAYS] + BAYS)
BACK_X = [x for g in GROUPS for x in g]
END_Y = (-4.0, 0.0, 4.0)
WIN_H = (1.9, 1.9, 1.6)

# interior
TE = 0.3                         # exterior wall thickness (walls sit inside the footprint)
TP = 0.15                        # partition thickness
IX0, IX1, IY0, IY1 = -W2 + TE, W2 - TE, -D2 + TE, D2 - TE
CEILS = (3.95, 7.45, 11.0)       # ceiling height of each storey
CY = 0.975                       # corridor wall centre lines (clear corridor 1.8 m)
RYF, RYB = -(CY + TP / 2), CY + TP / 2     # room faces of the corridor walls
PART = (5.0, 10.55, 15.95)       # partition lines of each wing (|x|)
HOLE_A = (-5.0 + TP / 2 - 0.0, 2.4, -3.65, 5.90)    # stairwell 1F -> 2F (in the 2F floor)
HOLE_B = (3.65, 2.4, 5.0 - TP / 2, 5.90)            # stairwell 2F -> 3F (in the 3F floor)
HOLE_C = (-5.0 + TP / 2, 1.1, -3.7, 4.65)           # stairwell 3F -> attic (in the 3F ceiling / top cap)
IN_CREAM, IN_YELLOW, IN_WHITE = K.PLASTER_CREAM, K.PLASTER_YELLOW, K.PLASTER_WHITE

# cafeteria wing
CX0, CX1, CY0, CY1 = 22.0, 37.0, -6.0, 6.0
CZ = 0.45
CWH = 4.2
FOUND = -4.0
KDOOR_Y = 2.6                    # dorm kitchen <-> cafeteria servery door


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


def window(mb, u, z, w, h, head="flat", door=False, cut=None):
    """Facade window dressing. cut=None: decorative (opaque glass on a solid face); cut="window": the wall
    has a real opening with clear glass (K.Window) - no facade glass; cut="door": real doorway (a door leaf
    socket fills it) - only the surround, side + head frames are drawn."""
    fw = 0.08
    if cut is None:
        mb.box((u, -0.02, z + h / 2), (w, 0.04, h), GLASS, skip=("+y",))
    mb.box((u - w / 2 - fw / 2, -0.05, z + h / 2), (fw, 0.1, h + 2 * fw), FRAME, skip=("+y",))
    mb.box((u + w / 2 + fw / 2, -0.05, z + h / 2), (fw, 0.1, h + 2 * fw), FRAME, skip=("+y",))
    mb.box((u, -0.05, z + h + fw / 2), (w, 0.1, fw), FRAME, skip=("+y",))
    if cut != "door":
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


# ------------------------------------------------------------------ interior helpers
@contextmanager
def lift(z, *mbs):
    """Raise kit furniture (modelled at z = 0) to a storey's floor level."""
    with ExitStack() as st:
        for m in mbs:
            st.enter_context(m.at((0.0, 0.0, z)))
        yield


def _strip(mb, x0, y0, x1, y1, z0, z1, mat, along, cuts=()):
    """Box strip along x or y with gaps (cuts = [(a, b), ...] along the strip axis)."""
    lo, hi = (x0, x1) if along == "x" else (y0, y1)
    u = lo
    for a, b in sorted(cuts) + [(hi, hi)]:
        if a - u > 1e-3:
            if along == "x":
                mb.box_mm((u, y0, z0), (a, y1, z1), mat)
            else:
                mb.box_mm((x0, u, z0), (x1, a, z1), mat)
        u = max(u, b)


def pwall(aset, mb, p0, p1, z0, h, mat_r, mat_l, doors=(), t=TP, trim=K.TRIM_WHITE, base=K.TRIM_WOOD):
    """Partition centred on the line p0 -> p1. mat_l faces the room on the LEFT of p0 -> p1, mat_r the right.
    Skirting boards on both faces (cut at the doorways)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    q0 = (p0[0] - nx * t / 2, p0[1] - ny * t / 2)
    q1 = (p1[0] - nx * t / 2, p1[1] - ny * t / 2)
    K.wall(aset, mb, q0, q1, z0, h, t, mat_r, inner=mat_l, openings=doors, trim=trim, trim_in=trim)
    if base:
        yaw = math.degrees(math.atan2(dy, dx))
        cuts = sorted((d.c - d.w / 2 - 0.1, d.c + d.w / 2 + 0.1) for d in doors)
        with mb.at((q0[0], q0[1], z0), rot=yaw):
            for yy in (-0.012, t + 0.012):
                u = 0.0
                for a, b in cuts + [(L, L)]:
                    if a - u > 0.05:
                        mb.box(((u + a) / 2, yy, 0.06), (a - u, 0.024, 0.12), base)
                    u = max(u, b)


def finish(mb, x0, y0, x1, y1, z, mat, holes=()):
    """Floor finish (3 cm) whose top is the walking level z, split around stairwell holes."""
    xs = sorted({x0, x1, *[v for hh in holes for v in (hh[0], hh[2])]})
    ys = sorted({y0, y1, *[v for hh in holes for v in (hh[1], hh[3])]})
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(hh[0] < cx < hh[2] and hh[1] < cy < hh[3] for hh in holes):
                continue
            if xs[i + 1] - xs[i] < 1e-4 or ys[j + 1] - ys[j] < 1e-4:
                continue
            mb.box_mm((xs[i], ys[j], z - 0.03), (xs[i + 1], ys[j + 1], z), mat, skip=("-z",))


def P(aset, name, x, y, z, yaw=0.0, s=1.0):
    aset.prop(name, (x, y, z), yaw, s)


def _rot(dx, dy, yaw):
    a = math.radians(yaw)
    return dx * math.cos(a) - dy * math.sin(a), dx * math.sin(a) + dy * math.cos(a)


def curtain(nc, x, y, z0, z1, yaw, w, mat, frac=0.22):
    """Pair of drawn-back curtains + rod in front of a window / glazed door. (x, y) = opening centre on the
    inner wall face, yaw: local -Y into the room."""
    cw = (w + 0.4) * frac
    with nc.at((x, y, 0.0), rot=yaw):
        nc.box((0, -0.1, z1 + 0.14), (w + 0.55, 0.03, 0.03), K.TRIM_WOOD)
        for s in (-1, 1):
            cx = s * (w / 2 + 0.2 - cw / 2)
            for k in range(3):
                fx = cx - cw / 2 + cw * (k + 0.5) / 3
                nc.box((fx, -0.08 + (0.02 if k % 2 else -0.02), (z0 - 0.12 + z1 + 0.12) / 2),
                       (cw / 3 + 0.01, 0.025, z1 - z0 + 0.24), mat)
            nc.box((s * (w / 2 + 0.2 - cw * 0.6), -0.09, z0 + (z1 - z0) * 0.45), (cw * 0.5, 0.05, 0.05), K.TRIM_GOLD)


def chairs_around(aset, x, y, z, yaw, length, side, n_per=2, chair="SM_Int_WoodChair", ends=False):
    """Chairs along both long sides (local x) of a table centred at (x, y)."""
    for i in range(n_per):
        dx = -length / 2 + length * (i + 0.5) / n_per
        for s in (-1, 1):
            ox, oy = _rot(dx, s * side, yaw)
            P(aset, chair, x + ox, y + oy, z, yaw + (180 if s < 0 else 0))
    if ends:
        for s in (-1, 1):
            ox, oy = _rot(s * (length / 2 + 0.45), 0, yaw)
            P(aset, chair, x + ox, y + oy, z, yaw - s * 90)


def ra_emblem(nc, x, y, z, r, yaw=0.0, mat="M_IntCarpetYellow"):
    """Ra Yellow sun emblem inlay (floor rugs / wall plaques), lying in the XY plane at height z."""
    nc.cylinder((x, y, z), r, 0.012, mat, seg=28)
    nc.cylinder((x, y, z + 0.012), r * 0.5, 0.004, K.TRIM_GOLD, seg=24)
    nc.cylinder((x, y, z + 0.016), r * 0.36, 0.004, "M_IntCarpetRed", seg=20)
    for k in range(12):
        a = k / 12 * math.tau + math.radians(yaw)
        L = r * (0.32 if k % 2 == 0 else 0.22)
        cx, cy = x + math.cos(a) * (r * 0.5 + L / 2 + 0.03), y + math.sin(a) * (r * 0.5 + L / 2 + 0.03)
        with nc.at((cx, cy, z + 0.012), rot=math.degrees(a)):
            nc.box((0, 0, 0.002), (L, r * 0.07, 0.004), K.TRIM_GOLD)
    nc.torus((x, y, z + 0.014), r - 0.07, 0.025, K.TRIM_GOLD, seg=28, tube_seg=4)


# ------------------------------------------------------------------ main block (exterior dressing)
def _ring(mb, z0, z1, out, front_cuts=(), back_cuts=(), east_cuts=()):
    """Moulding band around the main block, just outside the wall line (the block is hollow now)."""
    d = 0.1     # tuck into the wall
    _strip(mb, -W2 - out, -D2 - out, -BAYX, -D2 + d, z0, z1, TRIM, "x")
    _strip(mb, BAYX, -D2 - out, W2 + out, -D2 + d, z0, z1, TRIM, "x")
    _strip(mb, -W2 - out, D2 - d, W2 + out, D2 + out, z0, z1, TRIM, "x", back_cuts)
    _strip(mb, -W2 - out, -D2 + d, -W2 + d, D2 - d, z0, z1, TRIM, "y")
    _strip(mb, W2 - d, -D2 + d, W2 + out, D2 - d, z0, z1, TRIM, "y", east_cuts)


def _bay_ring(mb, z0, z1, out, cuts=()):
    d = 0.1
    _strip(mb, -BAYX - out, YBAY - out, BAYX + out, YBAY + d, z0, z1, TRIM, "x", cuts)
    _strip(mb, -BAYX - out, YBAY + d, -BAYX + d, -D2, z0, z1, TRIM, "y")
    _strip(mb, BAYX - d, YBAY + d, BAYX + out, -D2, z0, z1, TRIM, "y")


def _main(aset, mb, nc):
    # plinth (its top is the sub-floor under the ground floor finishes)
    mb.box_mm((-W2 - 0.12, -D2 - 0.12, FOUND), (W2 + 0.12, D2 + 0.12, ZG - 0.03), STONE)
    mb.box_mm((-BAYX - 0.12, YBAY - 0.12, FOUND), (BAYX + 0.12, -D2, ZG - 0.03), STONE)
    _shell(aset, mb)
    # base course + belt course + cornice (rings around the hollow block, cut at the doorways)
    door_b = [(-0.8, 0.8)]
    door_k = [(KDOOR_Y - 0.55, KDOOR_Y + 0.55)]
    _ring(mb, ZG - 0.14, ZG + 0.06, 0.18, back_cuts=door_b, east_cuts=door_k)
    _ring(mb, FLOORS[1] - 0.2, FLOORS[1] + 0.02, 0.07)
    _ring(mb, ZC - 0.6, ZC - 0.42, 0.1)
    _ring(mb, ZC - 0.42, ZC, 0.34)
    _bay_ring(mb, ZG - 0.14, ZG + 0.06, 0.18, cuts=[(-1.0, 1.0)])
    _bay_ring(mb, FLOORS[1] - 0.2, FLOORS[1] + 0.02, 0.07, cuts=[(-0.7, 0.7)])
    _bay_ring(mb, ZC - 0.6, ZC - 0.42, 0.1)
    _bay_ring(mb, ZC - 0.42, ZC, 0.34)
    # rusticated ground floor lines on the central bay (interrupted by the entrance)
    for k in range(6):
        z = ZG + 0.55 * (k + 1)
        for xa, xb in ((-BAYX - 0.02, -1.12), (1.12, BAYX + 0.02)):
            mb.box_mm((xa, YBAY - 0.02, z - 0.03), (xb, YBAY + 0.01, z), STONE)

    # ---------------- front facade
    heads = ("flat", "ped", "key")
    with mb.at((0, -D2, 0)):
        for fi, zf in enumerate(FLOORS):
            h = WIN_H[fi]
            for x in BAYS:
                for s in (-1, 1):
                    window(mb, s * x, zf + 0.85, 1.2, h, heads[fi], cut="window")
        for u, d in ((W2, -1), (-W2, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65)
    with mb.at((0, YBAY, 0)):
        for fi, zf in enumerate(FLOORS[1:]):
            for x in (-3.0, 3.0):
                window(mb, x, zf + 0.85, 1.2, 1.9 if fi == 0 else 1.6, "ped" if fi == 0 else "key", cut="window")
        window(mb, 0.0, FLOORS[1], 1.4, 2.6, "ped", door=True, cut="door")   # French door -> portico
        window(mb, 0.0, FLOORS[2] + 0.85, 1.2, 1.6, "key", cut="window")
        for u, d in ((BAYX, -1), (-BAYX, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65, phase=1)
        # main double door (the leaves are door sockets; the surround + glazed transom stay)
        dw, dh = 2.0, 2.7
        for sx in (-dw / 2 - 0.12, dw / 2 + 0.12):
            mb.box((sx, -0.08, ZG + (dh + 0.75) / 2), (0.24, 0.16, dh + 0.75), TRIM)
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

    # ---------------- back facade (sea side): balconies with French doors (real doorways)
    with mb.at((0, D2, 0), rot=180):           # local u = -x
        for fi, zf in enumerate(FLOORS):
            for g in GROUPS:
                for x in g:
                    if fi == 0:
                        if x == 0.0:
                            continue
                        window(mb, -x, zf + 0.85, 1.2, 1.9, "flat", cut="window")
                    else:
                        window(mb, -x, zf, 1.2, 2.45, "key", door=True, cut="door")
        for u, d in ((W2, -1), (-W2, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65)
        # back door surround (the double leaf is a door socket)
        mb.box((0, -0.07, ZG + 2.75), (2.2, 0.14, 0.18), TRIM)
        for sx in (-0.92, 0.92):
            mb.box((sx, -0.06, ZG + 1.35), (0.2, 0.12, 2.7), TRIM)
    mb.box_mm((-2.2, D2, FOUND), (2.2, D2 + 1.4, ZG), STONE, mats={"+z": "M_Paving"})
    for k in range(2):
        y0 = D2 + 1.4 + 0.36 * k
        mb.box_mm((-2.2, y0, FOUND), (2.2, y0 + 0.36, ZG - 0.25 * (k + 1)), STONE, mats={"+z": "M_Paving"})
    mb.box((-1.4, D2 + 0.12, ZG + 2.4), (0.18, 0.24, 0.3), "M_DarkMetal")
    nc.box((-1.4, D2 + 0.3, ZG + 2.2), (0.18, 0.18, 0.3), "M_LampGlow")
    aset.light((-1.4, D2 + 0.9, ZG + 2.2), (1.0, 0.82, 0.55), 3000.0, 8.0, night_only=True)
    for fi, zf in enumerate(FLOORS[1:]):
        for g in GROUPS:
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
                window(mb, u, zf + 0.85, 1.2, WIN_H[fi], heads[fi], cut="window")
        for u, d in ((D2, -1), (-D2, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65, phase=1)
    with mb.at((W2, 0, 0), rot=90):             # outward +x, u = y
        for u in (-4.0, 0.0, 4.0):
            window(mb, u, FLOORS[2] + 0.85, 1.2, 1.6, "key", cut="window")
        for u, d in ((D2, -1), (-D2, 1)):
            quoins(mb, u, d, ZG + 0.1, ZC - 0.65, phase=1)

    # ---------------- roof: hollow hip roof (walk-in attic below), walk-in dormers, chimneys
    _roof_hollow(mb)
    ridge = W2 - D2
    mb.box((0, 0, ZRB + RH + 0.05), (2 * ridge + 0.3, 0.3, 0.14), "M_RaChimney")
    for xd in DORMER_X:
        for side in (-1, 1):
            _dormer(mb, xd, side)
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


# ------------------------------------------------------------------ hollow hip roof + walk-in dormers
DORMER_X = (-15.0, -9.0, 9.0, 15.0)
DRM_HW, DRM_YF, DRM_YB, DRM_ZT = 0.85, 4.6, 1.4, 14.75     # dormer half width, |y| of face / back, wall top
RTH = 0.3                        # roof thickness (top surface -> attic lining)
RIDGE = W2 - D2
ZA = ZC + 0.03                   # attic floor (boards on the top cap)
R_OV = 0.6                       # eave overhang


def _rz(x, y):
    """Top surface of the hip roof at (x, y) (long slopes + hips share the pitch)."""
    return ZRB + RH - max(abs(y), abs(x) - RIDGE, 0.0) * RPITCH


def _y_at(z):
    """|y| where the top surface of a long slope reaches height z."""
    return (ZRB + RH - z) / RPITCH


# dormer holes: top surface between the dormer face and where the slope reaches the dormer wall top;
# lining between the face and where the lining reaches the underside of the dormer roof at the cheeks
_HOLE_TOP = (_y_at(DRM_ZT), DRM_YF)
_HOLE_LIN = (_y_at(DRM_ZT - 0.12 + RTH), DRM_YF)


def _poly2(mb, pts, mat, mat_back=None):
    mb.poly(pts, mat)
    mb.poly(list(reversed(pts)), mat_back or mat)


def _roof_band(mb, ya, yb, cuts, dz, mat, down):
    """Long-slope strip between signed ya < yb (one side of the ridge), x clipped to the hip lines, minus
    the x intervals in `cuts`; dz = vertical offset (underside: -RTH), down = faces down."""
    edges = [None] + sorted(v for c in cuts for v in c) + [None]
    for i in range(0, len(edges), 2):
        lo, hi = edges[i], edges[i + 1]
        pts = []
        for x_, y in ((lo, ya), (hi, ya), (hi, yb), (lo, yb)):
            xe = RIDGE + abs(y)
            x = -xe if (x_ is None and len(pts) in (0, 3)) else xe if x_ is None else x_
            pts.append((x, y, ZRB + RH - abs(y) * RPITCH + dz))
        mb.poly(list(reversed(pts)) if down else pts, mat)


def _roof_hollow(mb):
    """Same outside as mb.hip_roof(.., overhang=0.6, thick=0.3) but hollow: sloped underside (eave soffit
    outside the wall line, plank lining inside = the attic ceiling) and real holes behind the dormers."""
    hw, hd = W2 + R_OV, D2 + R_OV
    lining = "M_IntCeilingWood"
    for s in (-1, 1):
        def band(a, b):         # |y| a..b -> signed, ordered
            return (s * b, s * a) if s < 0 else (s * a, s * b)
        cuts = [(x - DRM_HW, x + DRM_HW) for x in DORMER_X]
        # top
        for a, b, c in ((DRM_YF, hd, ()), (_HOLE_TOP[0], DRM_YF, cuts), (0.0, _HOLE_TOP[0], ())):
            _roof_band(mb, *band(a, b), c, 0.0, ROOF, False)
        # underside: soffit outside the wall line, lining inside (with the dormer holes)
        _roof_band(mb, *band(D2, hd), (), -RTH, ROOF, True)
        for a, b, c in ((DRM_YF, D2, ()), (_HOLE_LIN[0], DRM_YF, cuts), (0.0, _HOLE_LIN[0], ())):
            _roof_band(mb, *band(a, b), c, -RTH, lining, True)
    ze = _rz(hw, hd)
    for sx in (-1, 1):
        def m(pts):             # mirror an east-end CCW polygon to the west end (keeps CCW)
            return pts if sx > 0 else [(-x, y, z) for (x, y, z) in reversed(pts)]
        top = [(hw, -hd, ze), (hw, hd, ze), (RIDGE, 0.0, ZRB + RH)]
        mb.poly(m(top), ROOF)
        inner = [(W2, -D2, ZRB - RTH), (W2, D2, ZRB - RTH), (RIDGE, 0.0, ZRB + RH - RTH)]
        mb.poly(list(reversed(m(inner))), lining)
        outer = [(W2, -D2, ZRB - RTH), (hw, -hd, ze - RTH), (hw, hd, ze - RTH), (W2, D2, ZRB - RTH)]
        mb.poly(list(reversed(m(outer))), ROOF)
    a, b, c, e = (-hw, -hd, ze), (hw, -hd, ze), (hw, hd, ze), (-hw, hd, ze)

    def lo(p):
        return (p[0], p[1], p[2] - RTH)
    for p, q in ((a, b), (b, c), (c, e), (e, a)):
        mb.quad(lo(p), lo(q), q, p, ROOF)


def _dormer(mb, xd, side):
    """Walk-in dormer: front wall with a real window, cheeks down to the roof lining, little gable roof."""
    with mb.at((xd, 0, 0), rot=0 if side < 0 else 180):
        yf, yb = -DRM_YF, -DRM_YB
        zb = _rz(0, DRM_YF) - RTH
        zt = DRM_ZT
        mb.wall((-DRM_HW, yf), (DRM_HW, yf), zb, zt - zb, 0.1, WALL, inner_mat=IN_WHITE,
                openings=[dict(u=DRM_HW, w=0.8, z0=0.5, z1=1.25, glass=GLASSC)])
        with mb.at((0, yf, 0)):
            window(mb, 0, zb + 0.5, 0.8, 0.75, head=None, cut="window")
        # cheeks: triangles from the face down along the lining line up to the wall top
        yc = -_y_at(zt + RTH)
        for sx in (-1, 1):
            xo, xi = sx * DRM_HW, sx * (DRM_HW - 0.1)
            to = [(xo, yf, zb), (xo, yc, zt), (xo, yf, zt)]
            ti = [(xi, yf, zb), (xi, yc, zt), (xi, yf, zt)]
            _poly2(mb, to, WALL)
            _poly2(mb, ti, IN_WHITE)
            _poly2(mb, [(xo, yf, zb), (xo, yc, zt), (xi, yc, zt), (xi, yf, zb)], IN_WHITE)
        # little gable roof (as mb.gable_roof(.., overhang=0.18, thick=0.12)), ending where the attic lining
        # hole ends so nothing of it hangs below the lining inside the attic
        ov, th, zr_t = 0.18, 0.12, zt + 0.75
        xe, ze = DRM_HW + ov, zt - 0.75 * ov / DRM_HW
        ya, yz = yf - ov, -_HOLE_LIN[0]
        for sx in (-1, 1):
            for dz, mat in ((0.0, ROOF), (-th, IN_WHITE)):
                _poly2(mb, [(sx * xe, ya, ze + dz), (0.0, ya, zr_t + dz), (0.0, yz, zr_t + dz), (sx * xe, yz, ze + dz)],
                       mat)
            _poly2(mb, [(sx * xe, ya, ze - th), (sx * xe, ya, ze), (sx * xe, yz, ze), (sx * xe, yz, ze - th)], ROOF)
            _poly2(mb, [(sx * xe, ya, ze - th), (0.0, ya, zr_t - th), (0.0, ya, zr_t), (sx * xe, ya, ze)], ROOF)
        _poly2(mb, [(-DRM_HW, yf, zt), (DRM_HW, yf, zt), (0.0, yf, zr_t)], WALL)
        # inside: gable triangle over the front wall; closure at the back (white inside, wall colour outside)
        _poly2(mb, [(-DRM_HW, yf + 0.1, zt - th), (DRM_HW, yf + 0.1, zt - th), (0.0, yf + 0.1, zr_t - th)], IN_WHITE)
        _poly2(mb, [(-DRM_HW, yz, zt - th), (DRM_HW, yz, zt - th), (0.0, yz, zr_t)], IN_WHITE, WALL)


# ------------------------------------------------------------------ main block: hollow shell
class _TallDoor(K.Door):
    """Doorway whose wall cut continues above the leaf (glazed transom over the main entrance)."""

    def __init__(self, *a, cut_top=None, **kw):
        super().__init__(*a, **kw)
        self.cut_top = cut_top

    def opening(self):
        d = super().opening()
        d["z1"] = self.cut_top
        return d


def _win(c, fi, z0=0.85, w=1.2):
    return K.Window(c, w, z0, z0 + WIN_H[fi], glass=GLASSC, frame=FRAME, mullions=1, sill=K.TRIM_WHITE)


def _shell(aset, mb):
    """Exterior walls of the three storeys with real window / door openings, floor slabs and top cap.
    The facade dressing (frames, surrounds, heads, quoins, bands) is drawn in _main on top of these."""
    kw = dict(inner=IN_CREAM, base=K.TRIM_WOOD)
    for fi, zf in enumerate(FLOORS):
        zt = FLOORS[fi + 1] if fi < 2 else ZC
        h = zt - zf
        # front (either side of the bay)
        K.wall(aset, mb, (-W2, -D2), (-BAYX + TE, -D2), zf, h, TE, WALL,
               openings=[_win(x + W2, fi) for x in FRONT_X if x < 0], **kw)
        K.wall(aset, mb, (BAYX - TE, -D2), (W2, -D2), zf, h, TE, WALL,
               openings=[_win(x - (BAYX - TE), fi) for x in FRONT_X if x > 0], **kw)
        # back (sea side): ground floor windows + back door, balcony French doors above
        if fi == 0:
            ops = [_win(W2 - x, 0) for x in BACK_X if x != 0.0]
            ops.append(K.Door(W2, 1.6, 2.6, "ra", double=True, trim=None, trim_in=K.TRIM_WHITE))
        else:
            ops = [K.Door(W2 - x, 1.2, 2.51, "ra", double=True, trim=None, trim_in=K.TRIM_WHITE) for x in BACK_X]
        K.wall(aset, mb, (W2, D2), (-W2, D2), zf, h, TE, WALL, openings=ops, **kw)
        # west end
        K.wall(aset, mb, (-W2, D2), (-W2, -D2), zf, h, TE, WALL, openings=[_win(D2 - y, fi) for y in END_Y], **kw)
        # east end: the cafeteria wing covers the ground floor (kitchen pass door), windows on 3F only
        if fi == 0:
            ops = [K.Door(KDOOR_Y + D2, 1.0, 2.15, "ra_inner", trim=None, trim_in=K.TRIM_WHITE)]
        elif fi == 2:
            ops = [_win(y + D2, fi) for y in END_Y]
        else:
            ops = []
        K.wall(aset, mb, (W2, -D2), (W2, D2), zf, h, TE, WALL, openings=ops, **kw)
        # central bay front: entrance (+ transom), French door, windows
        zt_b = FLOORS[fi + 1] if fi < 2 else ZRB
        if fi == 0:
            ops = [_TallDoor(BAYX, 2.0, 2.7, "ra", double=True, trim=None, trim_in=K.TRIM_WHITE, cut_top=3.345)]
        elif fi == 1:
            ops = [K.Door(BAYX, 1.4, 2.65, "ra", double=True, trim=None, trim_in=K.TRIM_WHITE),
                   _win(BAYX - 3.0, 1), _win(BAYX + 3.0, 1)]
        else:
            ops = [_win(BAYX - 3.0, 2), _win(BAYX, 2), _win(BAYX + 3.0, 2)]
        K.wall(aset, mb, (-BAYX, YBAY), (BAYX, YBAY), zf, zt_b - zf, TE, WALL, openings=ops, **kw)
    # bay side walls (full height up to the pediment base)
    K.wall(aset, mb, (-BAYX, -D2), (-BAYX, YBAY), ZG, ZRB - ZG, TE, WALL, inner=IN_CREAM)
    K.wall(aset, mb, (BAYX, YBAY), (BAYX, -D2), ZG, ZRB - ZG, TE, WALL, inner=IN_CREAM)
    # entrance transom: lintel + clear glass with glazing bars
    mb.box_mm((-1.0, YBAY, ZG + 2.7), (1.0, YBAY + TE, ZG + 2.795), TRIM)
    mb.box_mm((-1.0, YBAY + 0.13, ZG + 2.795), (1.0, YBAY + 0.17, ZG + 3.345), GLASSC)
    for sx in (-0.5, 0.0, 0.5):
        mb.box((sx, YBAY + 0.15, ZG + 3.07), (0.04, 0.08, 0.55), FRAME)
    # thresholds of the ground floor doorways (the plinth sits 3 cm below the finished floor)
    mb.box_mm((-1.0, YBAY, ZG - 0.03), (1.0, YBAY + TE, ZG), "M_Marble")
    mb.box_mm((-0.8, D2 - TE, ZG - 0.03), (0.8, D2, ZG), "M_Marble")
    mb.box_mm((W2 - TE, KDOOR_Y - 0.5, ZG - 0.03), (W2, KDOOR_Y + 0.5, ZG), "M_Marble")
    # floor slabs (bay strip slab is thinner so the entrance transom clears the hall ceiling)
    for fi, hole in ((1, HOLE_A), (2, HOLE_B)):
        zf = FLOORS[fi]
        K.slab(mb, IX0, IY0, IX1, IY1, zf - 0.03, zf - 0.03 - CEILS[fi - 1], top=K.WOODFLOOR, bottom=K.CEIL,
               side=K.CEIL, holes=[hole])
        K.slab(mb, -BAYX + TE, YBAY + TE, BAYX - TE, IY0, zf - 0.03, 0.12, top=K.WOODFLOOR, bottom=K.CEIL,
               side=K.CEIL)
    # top cap (3F ceiling); the hip roof sits above
    K.slab(mb, IX0, IY0, IX1, IY1, ZC, ZC - CEILS[2], top=WALL, bottom=K.CEIL, side=K.CEIL, holes=[HOLE_C])
    mb.box_mm((-BAYX + TE, YBAY + TE, CEILS[2]), (BAYX - TE, IY0, ZRB), WALL, mats={"-z": K.CEIL})


# ------------------------------------------------------------------ interior: shared bits
POSTER_TEXT = ["RA YELLOW PRIDE", "STUDY HARD, DUEL HARDER", "THEORY WINS", "SUN DECK", "TOP 10 COMBOS",
               "DUEL MONTHLY", "SPELL SPEED 2", "KEEP CALM & DRAW", "FUSION 101", "SCHOOL DUEL CUP"]
BLANKETS = ("M_IntFabricYellow", "M_IntFabricOrange", "M_IntFabricYellow", "M_IntFabricBeige", "M_IntFabricWhite",
            "M_IntFabricGreen", "M_IntFabricYellow", "M_IntFabricBlue")


def _side_x(x0, x1):
    """Inner faces of a room between two partition / exterior lines."""
    xa = x0 + (TP / 2 if abs(x0) < IX1 - 1e-3 else 0.0)
    xb = x1 - (TP / 2 if abs(x1) < IX1 - 1e-3 else 0.0)
    return xa, xb


def pigeonholes(mb, nc, x, y, z, yaw, w=1.6, h=1.5, d=0.32, cols=6, rows=5, rng_seed=0, z0=0.9):
    """Mail pigeonholes (wall unit, back at local +Y) with a few letters + parcels."""
    rnd = random.Random(rng_seed)
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, 0, z0 / 2), (w, d, z0), K.WOOD_DARK)                       # cabinet base
        mb.box((0, d / 2 - 0.01, z0 + h / 2), (w, 0.02, h), K.WOOD)
        for i in range(cols + 1):
            mb.box((-w / 2 + w * i / cols, 0, z0 + h / 2), (0.025, d, h), K.WOOD)
        for k in range(rows + 1):
            mb.box((0, 0, z0 + h * k / rows), (w, d, 0.025), K.WOOD)
    with nc.at((x, y, z), rot=yaw):
        for i in range(cols):
            for k in range(rows):
                if rnd.random() < 0.55:
                    cx = -w / 2 + w * (i + 0.5) / cols
                    nc.box((cx, 0.0, z0 + h * k / rows + 0.05), (w / cols * 0.7, d * 0.7, 0.05),
                           rnd.choice(("M_IntPaper", "M_IntPaper", "M_IntPoster3", "M_IntPoster2")))
        nc.box((0, -d / 2 - 0.003, z0 - 0.15), (w * 0.6, 0.006, 0.12), K.TRIM_GOLD)


def washer(mb, nc, x, y, z, yaw, dryer=False):
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, 0, 0.43), (0.6, 0.6, 0.86), K.TRIM_WHITE)
        mb.box((0, 0.05, 0.89), (0.6, 0.5, 0.06), K.METAL)
        with mb.at((0, -0.3, 0.45), rot_x=90):
            mb.cylinder((0, 0, 0), 0.2, 0.03, K.METAL, seg=16)
            mb.cylinder((0, 0, 0.03), 0.15, 0.01, "M_IntGlassClear" if not dryer else K.BLACK, seg=16)
    with nc.at((x, y, z), rot=yaw):
        nc.box((0.18, -0.302, 0.8), (0.16, 0.004, 0.06), "M_IntScreen")
        nc.box((-0.18, -0.302, 0.8), (0.1, 0.004, 0.04), K.BLACK)


def duel_table(mb, nc, aset, x, y, z, yaw):
    """Practice duel table: wooden table with two play mats, monster / spell zones and decks."""
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, 0, 0.74), (2.4, 0.95, 0.05), K.WOOD_DARK)
        for sx in (-1, 1):
            mb.box((sx * 1.05, 0, 0.36), (0.08, 0.8, 0.72), K.WOOD_DARK)
        mb.box((0, 0, 0.12), (2.0, 0.06, 0.06), K.WOOD_DARK)
    with nc.at((x, y, z), rot=yaw):
        for s in (-1, 1):
            nc.box((s * 0.6, 0, 0.766), (1.05, 0.85, 0.004), "M_IntChalkboard" if s < 0 else "M_IntCarpetBlue")
            for k in range(5):
                for r in (0.18, 0.4):
                    zx = s * r
                    nc.box((s * 0.6 + zx * 0.0 + s * (r - 0.29) * 0.9, -0.32 + k * 0.16, 0.77),
                           (0.12, 0.09, 0.003), "M_IntTrimWhite")
            nc.box((s * 1.05, 0.33, 0.79), (0.09, 0.065, 0.05), K.BLACK)             # deck
            nc.box((s * 0.82, -0.05, 0.775), (0.09, 0.065, 0.01), "M_IntPoster3")     # face-up card
    P(aset, "SM_Int_Stool", *wp(x, y, yaw, -1.55, 0), z, yaw)
    P(aset, "SM_Int_Stool", *wp(x, y, yaw, 1.55, 0), z, yaw)


def wp(x, y, yaw, dx, dy):
    ox, oy = _rot(dx, dy, yaw)
    return x + ox, y + oy


def fridge(mb, nc, x, y, z, yaw, w=0.9):
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, 0, 1.0), (w, 0.7, 2.0), K.METAL)
        mb.box((0, -0.352, 1.3), (w - 0.04, 0.005, 0.01), K.BLACK)
        for sx in (-0.08, 0.08):
            mb.box((sx, -0.38, 1.3), (0.03, 0.04, 0.5), "M_IntSteelBlue")
    with nc.at((x, y, z), rot=yaw):
        nc.box((-0.2, -0.353, 1.7), (0.16, 0.004, 0.2), "M_IntPoster3")


def chalk_lines(aset, x, y, yaw, z_top, lines, size=0.11, step=1.9, dx=0.0):
    a = math.radians(yaw)
    for i, line in enumerate(lines):
        px, py, pz = K.wall_point(x + math.cos(a) * dx, y + math.sin(a) * dx, yaw, 0.03, z_top - i * size * step)
        aset.text(line, (px, py, pz), yaw, size=size, color=(0.97, 0.97, 0.92))


def chalk_panel(mb, x, y, z0, z1, yaw, w):
    """Chalkboard panel on a wall face ((x, y) on the face, local -Y into the room)."""
    with mb.at((x, y, z0), rot=yaw):
        mb.box((0, -0.012, (z1 - z0) / 2), (w, 0.024, z1 - z0), "M_IntChalkboard")
        mb.box((0, -0.03, z1 - z0 + 0.02), (w + 0.06, 0.06, 0.04), K.WOOD)
        mb.box((0, -0.035, -0.02), (w + 0.06, 0.07, 0.04), K.WOOD)


# ------------------------------------------------------------------ detail helpers (lived-in layer)
def crown(mb, x0, y0, x1, y1, ceil, mat=K.TRIM_WHITE, d=0.12):
    """Crown moulding round a room's ceiling (inner wall faces x0..x1, y0..y1)."""
    for a, b, c, e in ((x0, y0, x1, y0 + d), (x0, y1 - d, x1, y1), (x0, y0 + d, x0 + d, y1 - d),
                       (x1 - d, y0 + d, x1, y1 - d)):
        mb.box_mm((a, b, ceil - d), (c, e, ceil), mat)


def coffers(mb, x0, y0, x1, y1, ceil, step=2.0, w=0.22, h=0.2, mat=K.TRIM_WHITE, skip=(), nx=None, ny=None):
    """Coffered ceiling: a grid of cased beams under the ceiling (+ crown moulding round the edge).
    skip: [(xa, ya, xb, yb)] areas (stairwells) the beams stop at."""
    def cut(a, b, along, fixed):
        segs, u = [], a
        for xa, ya, xb, yb in skip:
            lo, hi, f0, f1 = (xa, xb, ya, yb) if along == "x" else (ya, yb, xa, xb)
            if f0 - w < fixed < f1 + w and hi > u and lo < b:
                segs.append((u, max(u, lo - w)))
                u = max(u, hi + w)
        segs.append((u, b))
        return [(p, q) for p, q in segs if q - p > 0.3]
    nx = nx or max(1, round((x1 - x0) / step))
    ny = ny or max(1, round((y1 - y0) / step))
    for i in range(1, nx):
        x = x0 + (x1 - x0) * i / nx
        for a, b in cut(y0, y1, "y", x):
            mb.box_mm((x - w / 2, a, ceil - h), (x + w / 2, b, ceil), mat)
    for j in range(1, ny):
        y = y0 + (y1 - y0) * j / ny
        for a, b in cut(x0, x1, "x", y):
            mb.box_mm((a, y - w / 2, ceil - h * 0.8), (b, y + w / 2, ceil), mat)
    crown(mb, x0, y0, x1, y1, ceil, mat, d=0.14)


def fill_books(nc, aset, x, y, z_levels, yaw, w, d, seed=0):
    """Books standing on boards (unit centred at (x, y), back at local +Y) + a small thing at the end.
    (Local stand-in for DT.shelf_fill(kind="books"), whose book rows land off the shelf.)"""
    rnd = random.Random(seed)
    for i, z in enumerate(z_levels):
        sx, sy = DT._P(x, y, yaw, -w / 2 + 0.03, 0.0)
        L = w * rnd.uniform(0.55, 0.8)
        DT.book_row(nc, sx, sx + L, sy, z, d * 0.8, yaw=yaw, max_h=0.27, seed=seed * 7 + i)
        px, py = DT._P(x, y, yaw, -w / 2 + L + 0.15, 0.0)
        if w / 2 - (-w / 2 + L + 0.15) > 0.1:
            if rnd.random() < 0.5:
                DT.book_stack(nc, px, py, z, yaw, rnd.randint(2, 4), seed + i)
            else:
                aset.prop(rnd.choice(("SM_Int_PhotoFrame", "SM_Int_AlarmClock", "SM_Int_Candlestick")), (px, py, z),
                          yaw + 180.0 + rnd.uniform(-20, 20))


def frames(aset, items):
    """Pictures on walls: (asset, x, y, z, yaw) - (x, y) on the wall face, back at local +Y."""
    for name, x, y, z, yaw in items:
        aset.prop(name, (x, y, z), yaw)


def banner(nc, aset, x, y, z, yaw, w, h, text=None, mat="M_IntFabricYellow"):
    """Fabric banner hung on a wall from a rod ((x, y) on the face, top at z), gold fringe, sun emblem."""
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.03, 0.02), (w + 0.2, 0.03, 0.03), K.TRIM_GOLD)
        nc.box((0, -0.015, -h / 2), (w, 0.012, h), mat)
        nc.box((0, -0.017, -h + 0.03), (w, 0.014, 0.06), K.TRIM_GOLD)
    cx, cy, _ = K.wall_point(x, y, yaw, 0.025, 0.0)
    with nc.at((cx, cy, z - h * 0.42), rot=yaw, rot_x=90.0):
        nc.cylinder((0, 0, 0), min(w, h) * 0.2, 0.006, K.TRIM_GOLD, seg=16)
        nc.cylinder((0, 0, 0.004), min(w, h) * 0.12, 0.006, "M_IntFabricRed", seg=12)
    if text:
        aset.text(text, K.wall_point(x, y, yaw, 0.03, z - h * 0.82), yaw, size=min(0.12, w * 0.12),
                  color=(0.55, 0.3, 0.02))


def getabako(mb, nc, x, y, z, yaw, w=2.4, h=1.1, d=0.36, cols=8, rows=4, seed=0):
    """Shoe lockers (getabako) at a Japanese dorm entrance: back at local +Y, little doors, a few left open
    with shoes / slippers inside."""
    rnd = random.Random(seed)
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, 0, 0.06), (w, d - 0.04, 0.12), K.WOOD_DARK)
        mb.box((0, 0, 0.12 + (h - 0.12) / 2), (w, d, h - 0.12), K.WOOD)
        mb.box((0, -0.01, h + 0.015), (w + 0.04, d + 0.04, 0.03), K.WOOD_DARK)
    cw, rh = w / cols, (h - 0.16) / rows
    with nc.at((x, y, z), rot=yaw):
        for i in range(cols):
            for k in range(rows):
                cx, cz = -w / 2 + cw * (i + 0.5), 0.14 + rh * (k + 0.5)
                if rnd.random() < 0.18:      # open cubby: dark inside + shoes
                    nc.box((cx, -d / 2 - 0.002, cz), (cw - 0.03, 0.004, rh - 0.03), K.BLACK)
                    nc.box((cx, -d / 2 - 0.03, cz - rh / 2 + 0.05), (cw * 0.6, 0.06, 0.07),
                           rnd.choice(("M_IntFabricWhite", "M_IntFabricRed", "M_IntFabricBlue")))
                else:
                    nc.box((cx, -d / 2 - 0.004, cz), (cw - 0.025, 0.008, rh - 0.025), K.TRIM_WOOD)
                    nc.box((cx + cw * 0.3, -d / 2 - 0.012, cz), (0.015, 0.012, 0.06), K.METAL)
                    nc.box((cx - cw * 0.15, -d / 2 - 0.009, cz + rh * 0.3), (0.06, 0.004, 0.025), "M_IntPaper")
        for k in range(3):                   # slippers lined up in front
            nc.box((-w / 2 + 0.4 + k * 0.32, -d / 2 - 0.25, 0.025), (0.11, 0.26, 0.05), "M_IntFabricYellow")
            nc.box((-w / 2 + 0.53 + k * 0.32, -d / 2 - 0.25, 0.025), (0.11, 0.26, 0.05), "M_IntFabricYellow")


def stair_runner(nc, x, y, z0, z1, yaw, width=0.75, run=0.27, mat="M_IntFabricRed"):
    """Carpet runner with brass rods on a K.stairs flight (same origin / yaw / run)."""
    n = max(2, int(round((z1 - z0) / 0.18)))
    rise = (z1 - z0) / n
    with nc.at((x, y, z0), rot=yaw):
        for i in range(n):
            zt = rise * (i + 1)
            nc.box((run * i + run / 2 + 0.01, 0, zt + 0.004), (run, width, 0.008), mat)
            nc.box((run * i + 0.012, 0, zt - rise / 2), (0.008, width, rise), mat)
            nc.box((run * i + 0.03, 0, zt + 0.012), (0.018, width + 0.06, 0.018), K.TRIM_GOLD)


def wall_shelf(mb, nc, aset, x, y, z, yaw, w=1.0, d=0.22, kind="books", seed=0):
    """Wall-hung shelf board with brackets at height z ((x, y) on the wall, local -Y into the room)."""
    cx, cy, _ = K.wall_point(x, y, yaw, d / 2, 0.0)
    with mb.at((cx, cy, z), rot=yaw):
        mb.box((0, 0, -0.012), (w, d, 0.025), K.WOOD)
        for s in (-1, 1):
            mb.box((s * (w / 2 - 0.08), d / 2 - 0.08, -0.09), (0.025, 0.14, 0.14), K.METAL)
    if kind == "books":
        fill_books(nc, aset, cx, cy, [z], yaw, w, d, seed=seed)
    else:
        DT.shelf_fill(nc, aset, cx, cy, [z], yaw, w - 0.22, d, kind, seed=seed)  # (decor items sit at u + 0.1)


def laundry_line(nc, x0, x1, y, z, mats, seed=0):
    """Clothes hanging from a line / rail between x0 and x1 at height z (shirts, towels, a dorm jacket)."""
    rnd = random.Random(seed)
    nc.box(((x0 + x1) / 2, y, z), (x1 - x0, 0.015, 0.015), K.METAL)
    x = x0 + 0.2
    while x < x1 - 0.25:
        m = rnd.choice(mats)
        w, h = rnd.uniform(0.3, 0.5), rnd.uniform(0.35, 0.7)
        nc.box((x + w / 2, y, z - h / 2 - 0.02), (w, 0.02, h), m)
        x += w + rnd.uniform(0.05, 0.15)


# ------------------------------------------------------------------ dorm rooms
def dorm_room(aset, mb, nc, x0, x1, fi, side, num, rnd, misawa=False):
    """Twin dorm room between partition lines x0 < x1. side -1: front room (windows), +1: back room (balcony
    doors). Beds against the side walls (headboards at the corridor wall), wardrobes, desks + chairs.
    misawa=True keeps only the bed half (misawa_room() furnishes the rest)."""
    zf, ceil = FLOORS[fi], CEILS[fi]
    xa, xb = _side_x(x0, x1)
    s = side
    yc = RYF if s < 0 else RYB             # corridor wall face
    ye = IY0 if s < 0 else IY1             # exterior wall face
    cx, cy = (xa + xb) / 2, (yc + ye) / 2
    outer_a = xa <= IX0 + 1e-3
    end_win = outer_a or (xb >= IX1 - 1e-3 and fi == 2)     # window in the outer side wall (y = +-4)
    ya_, yb_ = (ye, -CY) if s < 0 else (CY, ye)
    K.floor_planks(mb, x0 if not outer_a else xa, ya_, x1 if xb < IX1 - 1e-3 else xb, yb_, zf,
                   mat=K.WOODFLOOR, along="y", pitch=0.24)
    K.rug(nc, cx - 1.2, cy - 1.0, cx + 1.2, cy + 1.0, zf + 0.001,
          rnd.choice(("M_IntCarpetYellow", "M_IntCarpetYellow", "M_IntCarpetBlue", "M_IntCarpetRose")),
          border=K.TRIM_GOLD)
    K.pendant(aset, cx, cy, ceil, "lamp")
    wall_c = 0.0 if s < 0 else 180.0       # yaw of things with their back on the corridor wall
    blank = rnd.sample(BLANKETS, 2)
    for i, bx in enumerate((xa, xb)):
        sgn = 1 if bx == xa else -1        # inward direction in x
        side_yaw = 90.0 * sgn              # back against this side wall
        outer = end_win and (bx == xa) == outer_a
        if misawa and bx == xb:
            continue
        with lift(zf, mb, nc):
            K.single_bed(mb, nc, bx + sgn * 0.52, yc + s * 1.02, 90.0 * s, blanket=blank[i], frame=K.WOOD,
                         width=0.98)
        nx_ = bx + sgn * 1.32
        P(aset, "SM_Int_NightstandB" if i else "SM_Int_Nightstand", nx_, yc + s * 0.3, zf, wall_c)
        P(aset, "SM_Int_DeskLamp", nx_, yc + s * 0.3, zf + (0.62 if i else 0.70), wall_c)
        if misawa:
            continue
        K.poster(nc, aset, bx, yc + s * 1.1, zf + 1.65, side_yaw, 0.62, 0.85, rnd.choice(K.POSTERS),
                 text=rnd.choice(POSTER_TEXT), text_size=0.06)
        if s < 0:   # front room: wardrobe mid side wall (window corner for the end rooms)
            P(aset, "SM_Int_Wardrobe", bx + sgn * 0.43, ye + 0.66 if outer else yc + s * 2.85, zf, side_yaw, 0.8)
            if outer:   # low bookcase under the end window
                with lift(zf, mb, nc):
                    K.bookcase(mb, nc, bx + sgn * 0.17, -4.0, side_yaw, w=1.2, d=0.3, h=0.78, shelves=2,
                               rng_seed=num)
            else:
                P(aset, rnd.choice(("SM_Int_Suitcase", "SM_Int_Box", "SM_Int_Basket")), bx + sgn * 0.35,
                  ye + 1.35, zf, side_yaw)
        else:       # back room: desk + wardrobe on the side walls, clear of the balcony doors
            dy, wy = (yc + 2.95, yc + 4.35) if outer else (yc + 4.4, yc + 2.85)
            P(aset, "SM_Int_Wardrobe", bx + sgn * 0.43, wy, zf, side_yaw, 0.8)
            P(aset, "SM_Int_Suitcase", bx + sgn * 0.43, wy, zf + 1.89, side_yaw + 90.0)
            with lift(zf, mb, nc):
                K.desk(mb, nc, bx + sgn * 0.3, dy, side_yaw, w=1.0, hutch=False, clutter=False,
                       rng_seed=num * 3 + sgn)
            if outer:       # under the end window: keep the things clear of the inside sill
                DT.desk_set(nc, aset, bx + sgn * 0.37, dy, zf + 0.76, side_yaw, "student", seed=num * 3 + i, w=1.0,
                            d=0.42)
            else:
                wall_shelf(mb, nc, aset, bx, dy, zf + 1.8, side_yaw, w=0.9, d=0.22, kind="books", seed=num + i)
                DT.desk_set(nc, aset, bx + sgn * 0.3, dy, zf + 0.76, side_yaw, "student", seed=num * 3 + i, w=1.0,
                            d=0.6)
            P(aset, "SM_Int_SchoolChair", bx + sgn * 0.95, dy, zf, -side_yaw)
    into = 180.0 if s < 0 else 0.0         # yaw facing into the room from the exterior wall
    if s < 0:
        for k, wx in enumerate(x for x in FRONT_X if xa < x < xb):
            curtain(nc, wx, ye, zf + 0.85, zf + 0.85 + WIN_H[fi], into, 1.2, "M_IntFabricWhite")
            if misawa:
                continue
            with lift(zf, mb, nc):
                K.desk(mb, nc, wx, ye + 0.31, 180.0, w=1.1, hutch=False, clutter=False, rng_seed=num * 5 + k)
            P(aset, "SM_Int_SchoolChair", wx, ye + 0.95, zf, 0.0)
            DT.desk_set(nc, aset, wx, ye + 0.38, zf + 0.76, 180.0, "student", seed=num * 5 + k, w=1.1, d=0.42)
    else:
        for wx in [x for x in BACK_X if xa < x < xb]:
            curtain(nc, wx, ye, zf, zf + 2.51, into, 1.2, "M_IntFabricYellow", frac=0.16)
    if end_win:
        curtain(nc, xa if outer_a else xb, -4.0 if s < 0 else 4.0, zf + 0.85, zf + 0.85 + WIN_H[fi],
                90.0 if outer_a else -90.0, 1.2, "M_IntFabricWhite")
    if not misawa:
        P(aset, "SM_Int_WallClock", cx + 1.0, yc, zf + 2.45, wall_c)
        pxc = xb - 0.3 if (end_win and outer_a) else xa + 0.3
        P(aset, "SM_Int_PottedPlant", pxc, ye - s * 0.3, zf, 0.0)
    # ---- the lived-in layer: fixtures, jackets, shelves, clutter (real sizes)
    y0, y1 = min(yc, ye), max(yc, ye)
    keep = [(xa, yc + s * 0.6, xa + 0.1, yc + s * 1.6), (xb - 0.1, yc + s * 0.6, xb, yc + s * 1.6)]   # posters
    for bx in (xa, xb):
        sgn = 1 if bx == xa else -1
        wy = (ye + 0.66 if (end_win and (bx == xa) == outer_a) else yc + s * 2.85) if s < 0 else \
            (yc + 4.35 if (end_win and (bx == xa) == outer_a) else yc + 2.85)
        keep.append((bx, wy - 0.75, bx + sgn * 0.1, wy + 0.75))
    keep += [(wx - 0.8, ye - 0.1, wx + 0.8, ye + 0.1) for wx in FRONT_X if s < 0 and xa < wx < xb]
    if end_win:
        ew = xa if outer_a else xb
        keep.append((ew - 0.1, s * 4.0 - 0.8, ew + 0.1, s * 4.0 + 0.8))
    DT.dress_room(aset, mb, nc, xa, y0, xb, y1, zf, ceil, style="dorm", seed=num, keep_clear=keep)
    hx = cx + (0.95 if s < 0 else -0.95)
    DT.coat_hooks(nc, hx, yc, zf + 1.75, wall_c, n=2, dorm="ra", jackets=1 if misawa else 2, seed=num)
    if not misawa:
        # wall shelf with manga / deck boxes over the bed head, a duel disk on one bed, bags + shoes on the floor
        shelf_x = xa + 0.55
        wall_shelf(mb, nc, aset, shelf_x, yc, zf + 1.6, wall_c, w=0.8, d=0.2, kind="books", seed=num)
        DT.duel_disk(nc, xb - 0.5, yc + s * 1.5, zf + 0.565, 70.0 + num * 13)
        DT.card_spread(nc, xa + 0.5, yc + s * 1.6, zf + 0.57, 90.0 * s, n=4, seed=num)
        clear = [(xa, y0, xa + 1.65, y1) if s > 0 else (xa, yc - 2.2, xa + 1.65, yc),
                 (xb - 1.65, y0, xb, y1) if s > 0 else (xb - 1.65, yc - 2.2, xb, yc),
                 (cx - 0.8, yc - 1.0, cx + 0.8, yc + 1.0)]
        if s < 0:
            clear.append((xa, ye, xb, ye + 0.7))
        else:
            clear += [(x - 0.8, ye - 0.9, x + 0.8, ye) for x in BACK_X if xa < x < xb]
        DT.floor_clutter(nc, aset, xa, y0, xb, y1, zf, "dorm", n=4, seed=num, clear=clear)


def misawa_room(aset, mb, nc, x0, x1, fi, side, num):
    """Bastion Misawa's room (a back room): the scholar's den - he turned the walls into chalkboards and
    covered them in equations. Bed + bookcases on the west wall, desk and the big equation wall east."""
    zf = FLOORS[fi]
    xa, xb = _side_x(x0, x1)
    yc, ye = RYB, IY1
    z0, z1 = zf + 1.05, zf + 2.95
    with lift(zf, mb, nc):
        K.desk(mb, nc, xb - 0.31, yc + 1.2, -90.0, w=1.2, hutch=False, rng_seed=31)
        K.bookcase(mb, nc, xa + 0.17, yc + 2.8, 90.0, w=1.0, d=0.3, h=2.0, rng_seed=32)
        K.bookcase(mb, nc, xa + 0.17, yc + 3.85, 90.0, w=1.0, d=0.3, h=2.0, rng_seed=33)
    P(aset, "SM_Int_OfficeChair", xb - 1.2, yc + 1.2, zf, 90.0)
    P(aset, "SM_Int_DeskLamp", xb - 0.3, yc + 0.8, zf + 0.76, -90.0)
    P(aset, "SM_Int_Chalkboard", (xa + xb) / 2 + 0.4, yc + 3.4, zf, 200.0)
    P(aset, "SM_Int_Books", xb - 0.3, yc + 1.55, zf + 0.76, -90.0)
    for k, (px, py) in enumerate(((xb - 1.2, yc + 2.3), (xb - 1.3, yc + 4.4), (xa + 1.6, yc + 3.6))):
        for j in range(3 + k):
            nc.box((px + 0.02 * j, py, zf + 0.025 + j * 0.05), (0.32, 0.24, 0.05),
                   ("M_IntPaper", "M_IntPoster2", "M_IntPaper", "M_IntPoster3")[j % 4])
    for k in range(9):    # crumpled papers on the floor
        nc.sphere((xa + 1.6 + (k * 0.37) % 2.4, yc + 2.3 + (k * 0.61) % 2.0, zf + 0.05), 0.05,
                  "M_IntPaper", seg=6, rings=4)
    # chalkboard walls
    chalk_panel(mb, xb, (yc + ye) / 2, z0, z1, -90.0, (ye - yc) - 0.4)            # east wall
    chalk_panel(mb, xa, yc + 1.15, z0 + 0.1, z1, 90.0, 1.9)                       # above the bed
    dc = (xa + xb) / 2
    halves = ((xa + 0.15, dc - 0.7), (dc + 0.7, xb - 0.15))
    for a, b in halves:                                                            # corridor wall
        chalk_panel(mb, (a + b) / 2, yc, z0, z1, 180.0, b - a)
    east = ["x = (-b +- sqrt(b^2 - 4ac)) / 2a", "P(draw k) = C(3,k) C(37,5-k) / C(40,5)", "e^(i pi) + 1 = 0",
            "LP(t) = 4000 - SUM dmg(i)", "ATK' = 2 ATK - DEF / 2 ?", "int_0^1 x^2 dx = 1/3",
            "lim (1 + 1/n)^n = e", "F(water) + F(fire) = steam", "dS >= 0", "6 attributes -> 6 decks !",
            "sigma = sqrt( SUM (x - mu)^2 / N )"]
    chalk_lines(aset, xb, (yc + ye) / 2, -90.0, z1 - 0.18, east, size=0.1, step=1.6)
    chalk_lines(aset, xa, yc + 1.15, 90.0, z1 - 0.2, ["a^2 + b^2 = c^2", "E = mc^2", "d/dx sin x = cos x",
                                                      "P(A|B) = P(B|A) P(A) / P(B)", "Q.E.D."], size=0.09, step=1.7)
    for (a, b), lines in zip(halves, (["f(x) = SUM a_n x^n", "Tribute: lv 5-6 -> 1", "lv 7+ -> 2",
                                       "Ra != Obelisk ... yet"],
                                      ["Deck = 40 cards", "E[hand] = 5 x 3/40", "= 0.375", "Optimize !"])):
        chalk_lines(aset, (a + b) / 2, yc, 180.0, z1 - 0.2, lines, size=0.09, step=1.7)
    aset.text("BASTION MISAWA", K.wall_point(dc, yc, 180.0, 0.03, zf + 2.4), 180.0, size=0.08,
              color=(0.98, 0.85, 0.3))


# ------------------------------------------------------------------ corridor + upper floors
def corridor(aset, mb, nc, xs, xe, fi, doors_f, doors_b, numbers):
    """Corridor floor, runner, lights, wainscot, room number plates."""
    zf, ceil = FLOORS[fi], CEILS[fi]
    lo, hi = min(xs, xe), max(xs, xe)
    K.floor_planks(mb, lo, -CY, hi, CY, zf, mat=K.WOOD_DARK, seam=K.TRIM_WOOD, along="x", pitch=0.3)
    K.rug(nc, lo + 0.3, -0.5, hi - 0.3, 0.5, zf + 0.001, "M_IntCarpetYellow", border="M_IntCarpetRed", bw=0.08)
    n = max(2, int((hi - lo) / 4.2))
    for k in range(n):
        x = lo + (hi - lo) * (k + 0.5) / n
        K.panel_light(aset, nc, x, 0.0, ceil, w=0.9, d=0.4, intensity=2200.0, radius=6.0)
    for (y, yaw, doors) in ((-0.9, 180.0, doors_f), (0.9, 0.0, doors_b)):
        gaps = []
        for dx in doors:
            gaps.append((dx - 0.6, dx + 0.6))
        # wainscot along the corridor faces (p0 -> p1 with the corridor on the left)
        if y < 0:
            K.wainscot(mb, (lo, y), (hi, y), zf, 0.95, K.WOOD, cap=K.TRIM_WOOD,
                       gaps=[(a - lo, b - lo) for a, b in gaps])
        else:
            K.wainscot(mb, (hi, y), (lo, y), zf, 0.95, K.WOOD, cap=K.TRIM_WOOD,
                       gaps=[(hi - b, hi - a) for a, b in gaps])
    for (dx, y, yaw), num in zip([(d, -0.9, 180.0) for d in doors_f] + [(d, 0.9, 0.0) for d in doors_b], numbers):
        if num:
            K.nameplate(mb, aset, dx + 0.78, y, zf + 1.55, yaw, num, mat=K.TRIM_WHITE, color=(0.45, 0.28, 0.05))


def upper_floor(aset, mb, nc, fi, rnd):
    zf, ceil = FLOORS[fi], CEILS[fi]
    h = ceil - zf
    fl = fi + 1
    # ---- x = +-5 walls (wings | central stair hall), open arch at the corridor
    pwall(aset, mb, (-BAYX, IY0), (-BAYX, IY1), zf, h, IN_CREAM, IN_YELLOW,
          doors=[K.Door(-IY0, 1.8, 2.6, None)])
    pwall(aset, mb, (BAYX, IY1), (BAYX, IY0), zf, h, IN_CREAM, IN_YELLOW,
          doors=[K.Door(IY1, 1.8, 2.6, None)])
    num_i = 1
    misawa_done = False
    for wing in (-1, 1):
        lines = [wing * v for v in PART] + [wing * IX1]
        segs = [tuple(sorted((lines[i], lines[i + 1]))) for i in range(3)]
        df, db, nums_f, nums_b = [], [], [], []
        for side in (-1, 1):
            for (x0, x1) in (segs if wing > 0 else list(reversed(segs))):
                washroom = side < 0 and wing > 0 and x0 > 15.0
                dxc = 17.0 if washroom else (x0 + x1) / 2
                mat_room = IN_WHITE if washroom else IN_YELLOW
                door = K.Door((dxc - x0) if side < 0 else (x1 - dxc), 0.95, 2.15, "ra_inner")
                if side < 0:
                    pwall(aset, mb, (x0, -CY), (x1, -CY), zf, h, mat_room, IN_CREAM, doors=[door])
                    df.append(dxc)
                else:
                    pwall(aset, mb, (x1, CY), (x0, CY), zf, h, mat_room, IN_CREAM, doors=[door])
                    db.append(dxc)
                num = f"{fl}{num_i:02d}"
                misawa = fi == 2 and side > 0 and wing > 0 and x0 < 6.0
                if washroom:
                    washroom_room(aset, mb, nc, x0, x1, fi)
                    (nums_f if side < 0 else nums_b).append("WC")
                else:
                    (nums_f if side < 0 else nums_b).append(num)
                    num_i += 1
                    if misawa:
                        dorm_room(aset, mb, nc, x0, x1, fi, side, int(num), rnd, misawa=True)
                        misawa_room(aset, mb, nc, x0, x1, fi, side, int(num))
                        misawa_done = True
                    else:
                        dorm_room(aset, mb, nc, x0, x1, fi, side, int(num), rnd)
        # partitions between the rooms (front + back)
        for v in PART[1:]:
            x = wing * v
            wash_r = wing > 0 and v == PART[2]
            if wing > 0:
                pwall(aset, mb, (x, IY0), (x, -CY), zf, h, IN_WHITE if wash_r else IN_YELLOW, IN_YELLOW)
                pwall(aset, mb, (x, CY), (x, IY1), zf, h, IN_YELLOW, IN_YELLOW)
            else:
                pwall(aset, mb, (x, IY0), (x, -CY), zf, h, IN_YELLOW, IN_YELLOW)
                pwall(aset, mb, (x, CY), (x, IY1), zf, h, IN_YELLOW, IN_YELLOW)
        xs, xe = wing * BAYX, wing * IX1
        corridor(aset, mb, nc, xs, xe, fi, df, db, nums_f + nums_b)
        # corridor end: window (west always, east on 3F) or a notice board + extinguisher
        endx = wing * (IX1 - 0.02)
        if wing < 0 or fi == 2:
            curtain(nc, wing * IX1, 0.0, zf + 0.85, zf + 0.85 + WIN_H[fi], -90.0 * wing, 1.2, "M_IntFabricYellow")
        else:
            K.bulletin(nc, aset, IX1, 0.0, zf + 1.1, -90.0, w=1.3, h=0.9, title="2F NOTICES", rng_seed=fi * 7)
        P(aset, "SM_Int_Extinguisher", endx - wing * 0.2, 0.7, zf, -90.0 * wing)
        P(aset, "SM_Int_PottedPlant", endx - wing * 0.3, -0.62, zf, 0.0)
        K.bulletin(nc, aset, wing * 10.8, -0.9, zf + 1.15, 180.0, w=1.2, h=0.8,
                   title="RA YELLOW NEWS" if wing < 0 else "LOST & FOUND", rng_seed=fi * 3 + wing)
    return misawa_done


def washroom_room(aset, mb, nc, x0, x1, fi):
    zf, ceil = FLOORS[fi], CEILS[fi]
    xa, xb = _side_x(x0, x1)
    yc, ye = RYF, IY0
    finish(mb, x0, ye, xb, -CY, zf, K.TILE)
    K.wainscot(mb, (xa, yc), (xa, ye), zf, 1.3, "M_IntTileBlue", cap=K.TRIM_WHITE)
    K.panel_light(aset, nc, (xa + xb) / 2, (yc + ye) / 2, ceil, w=1.2, d=0.4, intensity=2600.0)
    # sinks along the west wall + mirrors
    with lift(zf, mb, nc):
        K.counter(mb, xa, ye + 0.35, xa + 0.55, yc - 1.5, 0.85, body=K.TRIM_WHITE, top="M_IntTileBlue")
    for k in range(3):
        sy = ye + 0.95 + k * 0.95
        mb.box_mm((xa + 0.12, sy - 0.22, zf + 0.82), (xa + 0.45, sy + 0.22, zf + 0.855), "M_IntSteelBlue")
        nc.box((xa + 0.08, sy, zf + 0.95), (0.03, 0.03, 0.18), K.METAL)
        nc.box((xa + 0.15, sy, zf + 1.02), (0.14, 0.025, 0.025), K.METAL)
        nc.box((xa + 0.012, sy, zf + 1.6), (0.02, 0.6, 0.75), K.METAL)
        nc.box((xa + 0.02, sy, zf + 1.6), (0.02, 0.66, 0.81), K.TRIM_WHITE)
    # stalls (2 WCs + shower) along the corridor wall
    sx0 = 18.0
    sw = (xb - sx0) / 3
    sy0 = yc - 1.45
    for k in range(4):
        x = sx0 + k * sw
        if k < 3:
            mb.box_mm((x - 0.025, sy0, zf + 0.12), (x + 0.025, yc, zf + 2.05), K.TRIM_WHITE)
    for k in range(3):
        xl, xr = sx0 + k * sw, sx0 + (k + 1) * sw
        # front panels with an opening (stall doors are light panels in the opening, ajar)
        mb.box_mm((xl, sy0 - 0.025, zf + 0.12), (xl + 0.2, sy0 + 0.025, zf + 2.05), K.TRIM_WHITE)
        mb.box_mm((xr - 0.15, sy0 - 0.025, zf + 0.12), (xr, sy0 + 0.025, zf + 2.05), K.TRIM_WHITE)
        mb.box_mm((xl, sy0 - 0.025, zf + 1.95), (xr, sy0 + 0.025, zf + 2.05), K.TRIM_WHITE)
        if k < 2:
            with lift(zf, mb, nc):
                mb.box(((xl + xr) / 2, yc - 0.35, 0.2), (0.38, 0.5, 0.4), K.TRIM_WHITE)     # toilet
                mb.box(((xl + xr) / 2, yc - 0.1, 0.6), (0.4, 0.18, 0.4), K.TRIM_WHITE)      # cistern
            with nc.at((xl + 0.2, sy0, zf), rot=-60.0):
                nc.box((0.42, 0, 1.05), (0.84, 0.03, 1.8), "M_IntPlasterYellow")
        else:
            finish(mb, xl + 0.03, sy0 + 0.03, xr, yc, zf + 0.02, "M_IntTileBlue")
            nc.box(((xl + xr) / 2, yc - 0.12, zf + 2.0), (0.04, 0.2, 0.04), K.METAL)
            nc.cylinder(((xl + xr) / 2, yc - 0.25, zf + 1.92), 0.09, 0.03, K.METAL, seg=10)
            nc.box(((xl + xr) / 2 + 0.2, sy0 - 0.05, zf + 1.15), (sw * 0.5, 0.02, 1.7), "M_IntFabricYellow")
    P(aset, "SM_Int_Bench", 19.4, ye + 1.25, zf, 180.0)
    P(aset, "SM_Int_Basket", 21.2, ye + 0.4, zf, 15.0)
    P(aset, "SM_Int_WetFloor", 17.8, -3.8, zf, 40.0)
    P(aset, "SM_Int_RubberDuck", xa + 0.3, ye + 1.9, zf + 0.86, 30.0)
    for wx in (17.3, 20.0):
        curtain(nc, wx, ye, zf + 0.85, zf + 0.85 + WIN_H[fi], 180.0, 1.2, "M_IntFabricWhite", frac=0.18)
    aset.text("WASHROOM", K.wall_point(17.0 + 0.0, -0.9, 180.0, 0.02, zf + 2.3), 180.0, size=0.1,
              color=(0.45, 0.28, 0.05))


def _stair(mb, x, y, z0, z1, rail_side):
    """Straight oak flight climbing +y along a wall, white risers, closed sides (stringers)."""
    L = K.stairs(mb, x, y, z0, z1, 90.0, 1.1, mat=K.WOOD, riser=K.TRIM_WHITE, rail=K.TRIM_WOOD, run=0.27,
                 rail_sides=(rail_side,))
    n = max(2, int(round((z1 - z0) / 0.18)))
    rise = (z1 - z0) / n
    with mb.at((x, y, z0), rot=90.0):
        for s in (-1, 1):
            mb.beam((0.0, s * 0.58, rise * 0.45), (L, s * 0.58, z1 - z0 - rise * 0.55), 0.06, 0.36, K.TRIM_WOOD)
    return L


def center_upper(aset, mb, nc, fi):
    """Stair hall + landing lounge (2F, French door to the portico) / study library (3F) between the wings."""
    zf, ceil = FLOORS[fi], CEILS[fi]
    hole = HOLE_A if fi == 1 else HOLE_B
    finish(mb, -BAYX, IY0, BAYX, IY1, zf, K.WOODFLOOR, holes=[hole])
    finish(mb, -BAYX + TE, YBAY + TE, BAYX - TE, IY0, zf, K.WOODFLOOR)
    hx = hole[2] if fi == 1 else hole[0]
    K.railing(mb, [(hole[0] if fi == 1 else hole[2], hole[1]), (hx, hole[1]), (hx, 5.6)], zf, h=1.0,
              mat=K.TRIM_WOOD, spacing=0.13)
    if fi == 1:
        _stair(mb, 4.25, 0.75, FLOORS[1], FLOORS[2], 1)
    K.rug(nc, -1.0, -0.7, 1.0, 0.7, zf + 0.001, "M_IntCarpetYellow", border=K.TRIM_GOLD)
    ra_emblem(nc, 0.0, 0.0, zf + 0.014, 0.6)
    for x, txt in ((-BAYX + TP / 2, "WEST WING"), (BAYX - TP / 2, "EAST WING")):
        yaw = 90.0 if x < 0 else -90.0
        aset.text(txt, K.wall_point(x, 0.0, yaw, 0.03, zf + 2.75), yaw, size=0.13, color=(0.5, 0.32, 0.06))
    # balcony doors + bay windows / French door: curtains
    for x in (-2.8, 0.0, 2.8):
        curtain(nc, x, IY1, zf, zf + 2.51, 0.0, 1.2, "M_IntFabricYellow", frac=0.16)
    by = YBAY + TE
    if fi == 1:
        curtain(nc, 0.0, by, zf, zf + 2.65, 180.0, 1.4, "M_IntFabricYellow", frac=0.15)
        for x in (-3.0, 3.0):
            curtain(nc, x, by, zf + 0.85, zf + 2.75, 180.0, 1.2, "M_IntFabricWhite")
    else:
        for x in (-3.0, 0.0, 3.0):
            curtain(nc, x, by, zf + 0.85, zf + 2.45, 180.0, 1.2, "M_IntFabricWhite")
    P(aset, "SM_Int_PottedPlantB", -3.15, 1.6, zf, 20.0)
    P(aset, "SM_Int_PottedPlantB", 4.3 if fi == 1 else 3.15, 6.3 if fi == 1 else 1.6, zf, 80.0)
    if fi == 1:
        # landing lounge: sofa group (west), TV corner (east), portico French door in the middle
        P(aset, "SM_Int_Sofa", -3.0, -2.2, zf, 0.0)
        P(aset, "SM_Int_CoffeeTable", -3.0, -3.55, zf, 0.0)
        P(aset, "SM_Int_Armchair", -4.35, -3.9, zf, 90.0)
        P(aset, "SM_Int_Armchair", -1.65, -3.9, zf, -90.0)
        P(aset, "SM_Int_TeaSet", -3.0, -3.55, zf + 0.49, 30.0)
        K.rug(nc, -4.6, -5.0, -1.4, -1.6, zf + 0.001, "M_IntCarpetRed", border=K.TRIM_GOLD)
        P(aset, "SM_Int_Console", 4.63, -4.0, zf, -90.0)
        P(aset, "SM_Int_TV", 4.62, -4.0, zf + 0.95, -90.0)
        P(aset, "SM_Int_SofaB", 2.2, -4.0, zf, 90.0)
        for dy, m in ((-0.5, "M_IntFabricYellow"), (0.45, "M_IntFabricRed")):     # cushions
            with nc.at((2.45, -4.0 + dy, zf + 0.62), rot=90.0, rot_x=-15.0):
                nc.box((0, 0, 0), (0.4, 0.13, 0.38), m)
        for x in (-1.75, 1.75):
            P(aset, "SM_Int_PottedPlantB", x, -6.88, zf, 0.0)
        K.bulletin(nc, aset, -BAYX + TP / 2, -5.7, zf + 1.0, 90.0, w=1.2, h=0.85, title="2F NOTICES", rng_seed=21)
        P(aset, "SM_Int_RoundTable", 0.4, 3.3, zf, 0.0)
        for a in (0.0, 120.0, 240.0):
            ox, oy = _rot(0.0, -0.8, a)
            P(aset, "SM_Int_WoodChair", 0.4 + ox, 3.3 + oy, zf, a + 180.0)
        K.pendant(aset, -3.0, -3.6, ceil, "chandelier")
        K.pendant(aset, 2.2, -4.0, ceil, "lamp")
        K.pendant(aset, 0.4, 3.3, ceil, "lamp")
        K.camera(aset, "landing2", (4.0, -6.6, zf + 1.65), (-2.5, 2.5, zf + 0.9), 16.0)
    else:
        # study library: bookcases on both side walls, two reading tables, armchairs in the bay corners
        with lift(zf, mb, nc):
            for k, y in enumerate((-6.15, -5.1, -4.05, -3.0, -1.95)):
                K.bookcase(mb, nc, -BAYX + TP / 2 + 0.17, y, 90.0, w=1.0, d=0.32, h=2.4, shelves=6, rng_seed=50 + k)
                K.bookcase(mb, nc, BAYX - TP / 2 - 0.17, y, -90.0, w=1.0, d=0.32, h=2.4, shelves=6, rng_seed=60 + k)
        for k, y in enumerate((-5.2, -2.8)):
            study_table(mb, 0.0, y, zf, 90.0)
            chairs_around(aset, 0.0, y, zf, 90.0, 1.0, 0.7, chair="SM_Int_SchoolChair")
            P(aset, "SM_Int_DeskLamp", 0.15, y - 0.4, zf + 0.76, 90.0)
            P(aset, "SM_Int_Books", -0.15, y + 0.35, zf + 0.76, 90.0)
            K.pendant(aset, 0.0, y, ceil, "lamp")
        for x in (-3.6, 3.6):
            P(aset, "SM_Int_Armchair", x, -6.65, zf, 180.0 + (25.0 if x < 0 else -25.0))
        K.rug(nc, -1.6, -6.4, 1.6, -1.6, zf + 0.001, "M_IntCarpetBlue", border=K.TRIM_GOLD)
        aset.text("LIBRARY - QUIET PLEASE", K.wall_point(0.0, by, 180.0, 0.03, zf + 2.8), 180.0, size=0.14,
                  color=(0.5, 0.32, 0.06))
        # stair-hall lounge (between the attic stair on the west wall and the 2F stair well)
        P(aset, "SM_Int_SofaB", -0.9, 3.4, zf, -90.0)
        P(aset, "SM_Int_CoffeeTable", -2.35, 3.4, zf, 0.0)
        P(aset, "SM_Int_TeaSet", -2.35, 3.4, zf + 0.49, 15.0)
        P(aset, "SM_Int_Armchair", -2.35, 1.85, zf, 180.0)
        mb.box_mm((-2.0, 6.25, zf), (-0.85, 6.7, zf + 0.9), K.WOOD_DARK)          # trophy cabinet
        mb.box_mm((-2.03, 6.22, zf + 0.9), (-0.82, 6.7, zf + 0.94), K.TRIM_GOLD)
        for k in range(3):
            trophy(nc, -1.75 + k * 0.33, 6.47, zf + 0.94, 1.0 + 0.3 * (k == 1))
        K.poster(nc, aset, -1.42, IY1, zf + 1.65, 0.0, 0.8, 0.55, "M_IntPoster3", text="RA CUP",
                 text_color=(0.55, 0.3, 0.02), text_size=0.11)
        K.rug(nc, -3.4, 2.4, -1.3, 4.4, zf + 0.001, "M_IntCarpetYellow", border=K.TRIM_GOLD)
        P(aset, "SM_Int_Bench", 0.6, 1.6, zf, 180.0)
        K.pendant(aset, -2.35, 3.4, ceil, "lamp")
        aset.text("ATTIC  ^", K.wall_point(-BAYX + TP / 2, 3.2, 90.0, 0.03, zf + 2.6), 90.0, size=0.1,
                  color=(0.5, 0.32, 0.06))
        K.pendant(aset, 1.0, 3.6, ceil, "lamp")
        K.camera(aset, "library3", (3.6, -0.6, zf + 1.7), (-1.0, -6.6, zf + 0.8), 16.0)


def study_table(mb, x, y, z, yaw, L=1.6, W=0.8, top=K.WOOD, legs=K.WOOD_DARK, h=0.76):
    """Plain study / work table (long side along local x)."""
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, 0, h - 0.02), (L, W, 0.04), top)
        mb.box((0, 0, h - 0.1), (L - 0.12, W - 0.12, 0.12), legs)
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * (L / 2 - 0.08), sy * (W / 2 - 0.08), (h - 0.04) / 2), (0.06, 0.06, h - 0.04), legs)


def trophy(nc, x, y, z, s=1.0):
    nc.cylinder((x, y, z), 0.07 * s, 0.05 * s, K.WOOD_DARK, seg=8)
    nc.lathe([(0.025 * s, 0.05 * s), (0.02 * s, 0.14 * s), (0.08 * s, 0.22 * s), (0.09 * s, 0.32 * s)],
             K.TRIM_GOLD, seg=10, cap_bottom=False, center=(x, y, z))


# ------------------------------------------------------------------ ground floor
def ground_floor(aset, mb, nc, rnd):
    zf, ceil = FLOORS[0], CEILS[0]
    h = ceil - zf
    # ---- walls
    pwall(aset, mb, (-BAYX, IY0), (-BAYX, IY1), zf, h, IN_CREAM, IN_YELLOW,
          doors=[K.Door(-3.5 - IY0, 1.6, 2.4, "ra_inner", double=True)])
    pwall(aset, mb, (-PART[2], IY0), (-PART[2], IY1), zf, h, IN_YELLOW, IN_CREAM,
          doors=[K.Door(-IY0, 1.4, 2.3, "ra_inner", double=True)])
    pwall(aset, mb, (BAYX, IY1), (BAYX, IY0), zf, h, IN_CREAM, IN_CREAM,
          doors=[K.Door(IY1, 1.6, 2.4, "ra_inner", double=True)])
    pwall(aset, mb, (BAYX, -CY), (PART[2], -CY), zf, h, IN_YELLOW, IN_CREAM,
          doors=[K.Door(7.0 - BAYX, 0.95, 2.15, "ra_inner"), K.Door(14.0 - BAYX, 0.95, 2.15, "ra_inner")])
    pwall(aset, mb, (PART[2], -CY), (IX1, -CY), zf, h, K.PLASTER_PEACH, IN_CREAM,
          doors=[K.Door(17.2 - PART[2], 0.95, 2.15, "ra_inner")])
    pwall(aset, mb, (PART[1], CY), (BAYX, CY), zf, h, K.PLASTER_SKY, IN_CREAM,
          doors=[K.Door(PART[1] - 7.8, 0.95, 2.15, "ra_inner")])
    pwall(aset, mb, (IX1, CY), (PART[1], CY), zf, h, IN_WHITE, IN_CREAM,
          doors=[K.Door(IX1 - 12.3, 0.95, 2.15, "ra_inner")])
    pwall(aset, mb, (PART[2], IY0), (PART[2], -CY), zf, h, K.PLASTER_PEACH, IN_YELLOW)
    pwall(aset, mb, (PART[1], CY), (PART[1], IY1), zf, h, IN_WHITE, K.PLASTER_SKY)

    # ================= entrance hall
    finish(mb, -BAYX, IY0, BAYX, IY1, zf, K.MARBLEFLOOR)
    finish(mb, -BAYX + TE, YBAY + TE, BAYX - TE, IY0, zf, K.MARBLEFLOOR)
    for x0 in (-BAYX + TP / 2, BAYX - TP / 2):
        gaps = [(IY1 - (-2.65), IY1 - (-4.35))] if x0 < 0 else [(-0.85 - IY0, 0.85 - IY0)]
        if x0 < 0:
            K.wainscot(mb, (x0, IY1), (x0, IY0), zf, 1.0, K.WOOD, cap=K.TRIM_WOOD, gaps=gaps)
        else:
            K.wainscot(mb, (x0, IY0), (x0, IY1), zf, 1.0, K.WOOD, cap=K.TRIM_WOOD, gaps=gaps)
    ra_emblem(nc, 0.0, -3.4, zf + 0.001, 1.5)
    K.rug(nc, -0.85, -7.25, 0.85, -4.95, zf + 0.001, "M_IntCarpetRed", border=K.TRIM_GOLD)
    K.rug(nc, -0.85, -1.85, 0.85, 5.6, zf + 0.001, "M_IntCarpetRed", border=K.TRIM_GOLD)
    _stair(mb, -4.25, 0.75, FLOORS[0], FLOORS[1], -1)
    K.pendant(aset, 0.0, -3.4, ceil, "chandelier")
    K.pendant(aset, 0.0, 2.6, ceil, "chandelier")
    # reception / mail desk (east, front) with pigeonholes behind
    with lift(zf, mb, nc):
        K.counter(mb, 2.55, -5.7, 3.2, -2.3, 1.05, body=K.WOOD_DARK, top=K.TRIM_WHITE)
        mb.box_mm((2.5, -5.55, 0.15), (2.53, -2.45, 0.92), "M_IntPlasterYellow")
    with nc.at((2.49, -4.0, zf + 0.55), rot_y=90.0):
        nc.cylinder((0, 0, 0), 0.22, 0.012, K.TRIM_GOLD, seg=16)
    pigeonholes(mb, nc, BAYX - TP / 2 - 0.19, -4.0, zf, -90.0, w=2.6, h=1.3, cols=8, rows=4, rng_seed=3)
    P(aset, "SM_Int_OfficeChair", 3.8, -3.6, zf, -90.0)
    P(aset, "SM_Int_Books", 2.85, -5.3, zf + 1.05, -90.0)
    P(aset, "SM_Int_DeskLamp", 2.85, -2.7, zf + 1.05, -90.0)
    nc.sphere((2.85, -4.4, zf + 1.09), 0.045, K.TRIM_GOLD, seg=8, rings=6, hemi=True)      # desk bell
    aset.text("RECEPTION  -  MAIL", K.wall_point(BAYX - TP / 2, -4.0, -90.0, 0.03, zf + 2.55), -90.0, size=0.16,
              color=(0.45, 0.28, 0.05))
    # student mailboxes (back, east wall), notice board + bench (west), clock, plants
    pigeonholes(mb, nc, BAYX - TP / 2 - 0.19, 3.6, zf, -90.0, w=2.4, h=1.5, cols=8, rows=6, rng_seed=4, z0=0.6)
    aset.text("STUDENT MAILBOXES", K.wall_point(BAYX - TP / 2, 3.6, -90.0, 0.03, zf + 2.4), -90.0, size=0.12,
              color=(0.45, 0.28, 0.05))
    K.bulletin(nc, aset, -BAYX + TP / 2, -5.6, zf + 1.05, 90.0, w=1.5, h=1.0, title="RA YELLOW NOTICE BOARD",
               rng_seed=11)
    P(aset, "SM_Int_Bench", -4.55, -1.3, zf, 90.0)
    P(aset, "SM_Int_GrandfatherClock", -4.66, 0.2, zf, 90.0)
    for x in (-1.45, 1.45):
        P(aset, "SM_Int_PottedPlantB", x, -6.92, zf, 0.0)
    for x in (-1.45, 1.45):
        P(aset, "SM_Int_PottedPlant", x, 6.35, zf, x * 50)
    aset.text("WELCOME HOME, RA YELLOW!", K.wall_point(0.0, IY1, 0.0, 0.03, zf + 2.9), 0.0, size=0.15,
              color=(0.55, 0.36, 0.06))
    for x in (-2.8, 2.8):
        curtain(nc, x, IY1, zf + 0.85, zf + 2.75, 0.0, 1.2, "M_IntFabricYellow")
    K.camera(aset, "hall", (-3.3, -6.6, zf + 1.65), (1.5, 3.0, zf + 1.2), 15.0)

    # ================= common lounge (west)
    xa, xb = -PART[2] + TP / 2, -BAYX - TP / 2
    K.floor_planks(mb, -PART[2], IY0, -BAYX, IY1, zf, mat=K.WOODFLOOR, along="x", pitch=0.24)
    mb.box_mm((xb - 0.9, -0.85, zf), (xb, 0.85, ceil), IN_CREAM)                  # chimney breast
    mb.box_mm((xb - 0.95, -0.9, zf), (xb, 0.9, zf + 0.12), K.TRIM_WOOD)
    with lift(zf, mb, nc):
        K.fireplace(mb, nc, aset, xb - 0.9, 0.0, -90.0, w=1.4, h=1.25)
    aset.sockets[-1]["pos"][2] += zf
    P(aset, "SM_Int_Painting", xb - 0.9, 0.0, zf + 1.6, -90.0)
    for y in (-0.55, 0.55):
        P(aset, "SM_Int_Candelabra", xb - 1.05, y, zf + 1.35, -90.0)
    P(aset, "SM_Int_Sofa", -9.5, 0.0, zf, 90.0)
    P(aset, "SM_Int_CoffeeTable", -8.0, 0.0, zf, 0.0)
    P(aset, "SM_Int_Armchair", -7.6, -1.75, zf, 180.0)
    P(aset, "SM_Int_Armchair", -7.6, 1.75, zf, 0.0)
    P(aset, "SM_Int_TeaSet", -8.0, 0.0, zf + 0.49, 10.0)
    K.rug(nc, -10.3, -2.6, -6.6, 2.6, zf + 0.001, "M_IntCarpetRed", border=K.TRIM_GOLD)
    # TV corner (north-west)
    P(aset, "SM_Int_Console", xa + 0.29, 4.6, zf, 90.0)
    P(aset, "SM_Int_TV", xa + 0.3, 4.6, zf + 0.95, 90.0)
    P(aset, "SM_Int_SofaB", -12.6, 4.6, zf, -90.0)
    P(aset, "SM_Int_LowTable", -14.0, 4.6, zf, 90.0)
    P(aset, "SM_Int_Ottoman", -13.9, 3.3, zf, 0.0)
    K.rug(nc, -15.0, 3.2, -11.8, 6.0, zf + 0.001, "M_IntCarpetYellow", border=K.TRIM_GOLD)
    # bookcases on the west wall (front half) + card tables by the front windows
    with lift(zf, mb, nc):
        for k, y in enumerate((-5.6, -4.5, -3.4)):
            K.bookcase(mb, nc, xa + 0.17, y, 90.0, w=1.0, d=0.32, h=2.3, shelves=6, rng_seed=70 + k)
    with lift(zf, mb, nc):
        K.bookcase(mb, nc, xa + 0.17, -2.3, 90.0, w=1.0, d=0.32, h=2.3, shelves=6, rng_seed=74)
    for tx in (-8.4, -12.0):
        P(aset, "SM_Int_RoundTable", tx, -4.4, zf, 0.0)
        for a in (45.0, 135.0, 225.0, 315.0):
            ox, oy = _rot(0.0, -0.85, a)
            P(aset, "SM_Int_WoodChair", tx + ox, -4.4 + oy, zf, a + 180.0)
        P(aset, "SM_Int_Books", tx + 0.1, -4.4, zf + 0.75, 30.0)
        K.pendant(aset, tx, -4.4, ceil, "lamp")
    # piano by the back windows
    with lift(zf, mb, nc):
        K.piano(mb, nc, -8.2, 4.7, 0.0)
    P(aset, "SM_Int_PottedPlantB", xb - 0.45, IY0 + 0.42, zf, 0.0)
    P(aset, "SM_Int_PottedPlantB", xb - 0.45, IY1 - 0.45, zf, 90.0)
    P(aset, "SM_Int_Vitrine", xb - 0.36, 3.6, zf, -90.0)                       # trophy / card display cabinet
    P(aset, "SM_Int_Frame", xb, -5.6, zf + 1.6, -90.0)
    P(aset, "SM_Int_CeilingFan", -10.8, 0.0, ceil, 0.0)
    K.pendant(aset, -8.0, 0.0, ceil, "chandelier")
    K.pendant(aset, -13.4, 4.6, ceil, "lamp")
    for x in (-6.5, -9.2, -11.9, -14.6):
        curtain(nc, x, IY0, zf + 0.85, zf + 2.75, 180.0, 1.2, "M_IntFabricYellow")
        curtain(nc, x, IY1, zf + 0.85, zf + 2.75, 0.0, 1.2, "M_IntFabricYellow")
    aset.npc((-9.0, -1.2, zf), 90.0, dorm="ra", wander=1.5)
    K.camera(aset, "lounge", (-14.9, -6.0, zf + 1.7), (-6.5, 1.5, zf + 0.9), 15.0)

    # ================= duel practice room (west end)
    xa, xb = IX0, -PART[2] - TP / 2
    K.floor_planks(mb, IX0, IY0, -PART[2], IY1, zf, mat=K.WOODFLOOR, along="y", pitch=0.24)
    for y in (-3.4, 3.4):
        K.rug(nc, -20.6, y - 1.0, -17.1, y + 1.0, zf + 0.001, "M_IntCarpetBlue", border="M_IntCarpetYellow")
        duel_table(mb, nc, aset, -18.85, y, zf, 0.0)
        P(aset, "SM_Int_IndustrialLamp", -18.85, y, ceil, 0.0)
    K.blackboard(mb, nc, aset, xb, -3.6, zf + 0.95, -90.0, w=2.6, h=1.2,
                 lines=["TODAY'S DRILL:", "CHAIN RESOLUTION", "SPELL SPEED 1 < 2 < 3", "READ THE FIELD !"])
    P(aset, "SM_Int_DisplayShelves", xb - 0.25, 3.4, zf, -90.0)
    with lift(zf, mb, nc):
        K.lockers(mb, nc, aset, xb - 0.24, 5.6, -90.0, n=3, w=0.4, d=0.45)
    for k in range(3):
        trophy(nc, xb - 0.24, 5.2 + k * 0.4, zf + 1.9, 1.2 + 0.3 * (k == 1))
    for y, t in ((-1.6, "DUEL!"), (1.6, "THEORY + HEART")):
        K.poster(nc, aset, xb, y, zf + 1.7, -90.0, 0.6, 0.85, rnd.choice(K.POSTERS), text=t, text_size=0.06)
    for y in (-2.0, 2.0):
        P(aset, "SM_Int_Bench", xa + 0.37, y, zf, 90.0)
    for x in (-17.3, -20.0):
        curtain(nc, x, IY0, zf + 0.85, zf + 2.75, 180.0, 1.2, "M_IntFabricWhite")
        curtain(nc, x, IY1, zf + 0.85, zf + 2.75, 0.0, 1.2, "M_IntFabricWhite")
    for y in END_Y:
        curtain(nc, IX0, y, zf + 0.85, zf + 2.75, 90.0, 1.2, "M_IntFabricWhite")
    aset.text("DUEL PRACTICE ROOM", K.wall_point(xb, 0.0, -90.0, 0.03, zf + 2.7), -90.0, size=0.13,
              color=(0.45, 0.28, 0.05))
    aset.npc((-19.0, 0.6, zf), 180.0, dorm="ra", wander=1.5)
    K.camera(aset, "duel", (-16.6, -6.1, zf + 1.7), (-20.5, 2.5, zf + 0.7), 15.0)

    # ================= east corridor + rooms
    corridor(aset, mb, nc, BAYX, IX1, 0, [7.0, 14.0, 17.2], [7.8, 12.3],
             ["STUDY", "STUDY", "OFFICE", "LAUNDRY", "KITCHEN"])
    K.bulletin(nc, aset, IX1, 0.0, zf + 1.1, -90.0, w=1.3, h=0.9, title="MEAL TIMES", rng_seed=5)
    P(aset, "SM_Int_Extinguisher", IX1 - 0.2, 0.7, zf, -90.0)
    # study room
    xa, xb = BAYX + TP / 2, PART[2] - TP / 2
    K.floor_planks(mb, BAYX, IY0, PART[2], -CY, zf, mat=K.WOODFLOOR, along="y", pitch=0.24)
    for k, tx in enumerate((7.6, 10.4, 13.2)):
        study_table(mb, tx, -4.1, zf, 0.0)
        chairs_around(aset, tx, -4.1, zf, 0.0, 1.0, 0.7, chair="SM_Int_SchoolChair")
        P(aset, "SM_Int_DeskLamp", tx - 0.5, -4.1, zf + 0.76, 0.0)
        P(aset, "SM_Int_Books", tx + 0.3, -4.0, zf + 0.76, 0.0)
        K.panel_light(aset, nc, tx, -4.1, ceil, w=1.2, d=0.35, intensity=2600.0)
        nc.box((tx - 0.15, -4.3, zf + 0.765), (0.3, 0.22, 0.01), "M_IntPaper")
    with lift(zf, mb, nc):
        for k, y in enumerate((-5.75, -4.7, -3.65, -2.6)):
            K.bookcase(mb, nc, xa + 0.17, y, 90.0, w=1.0, d=0.32, h=2.3, shelves=6, rng_seed=80 + k)
    K.blackboard(mb, nc, aset, xb, -3.9, zf + 0.95, -90.0, w=3.0, h=1.2,
                 lines=["EXAM WEEK !", "Fusion: material A + B", "Ritual: tributes >= level",
                        "Quiet please - Ra Yellow study hall"])
    P(aset, "SM_Int_WallClock", 10.4, RYF, zf + 2.35, 0.0)
    P(aset, "SM_Int_PottedPlantB", xb - 0.45, IY0 + 0.45, zf, 0.0)
    for x in (6.5, 9.2, 11.9, 14.6):
        curtain(nc, x, IY0, zf + 0.85, zf + 2.75, 180.0, 1.2, "M_IntFabricWhite")
    aset.npc((10.4, -3.2, zf), 180.0, dorm="ra", wander=1.0)
    K.camera(aset, "study", (5.7, -1.6, zf + 1.7), (14.0, -6.0, zf + 0.8), 15.0)
    # dorm supervisor's office
    xa, xb = PART[2] + TP / 2, IX1
    K.floor_planks(mb, PART[2], IY0, IX1, -CY, zf, mat=K.WOOD_DARK, seam=K.TRIM_WOOD, along="x", pitch=0.2)
    K.rug(nc, 17.4, -5.6, 20.6, -2.6, zf + 0.001, "M_IntCarpetRed", border=K.TRIM_GOLD)
    P(aset, "SM_Int_OfficeDesk", 18.95, -4.3, zf, 0.0)
    P(aset, "SM_Int_OfficeChair", 18.95, -5.05, zf, 180.0)
    for x in (18.45, 19.45):
        P(aset, "SM_Int_DiningChair", x, -3.3, zf, 0.0)
    P(aset, "SM_Int_DeskLamp", 18.4, -4.45, zf + 0.76, 0.0)
    P(aset, "SM_Int_Books", 19.4, -4.4, zf + 0.76, 0.0)
    nc.box((18.95, -4.25, zf + 0.765), (0.4, 0.3, 0.01), "M_IntPaper")
    with lift(zf, mb, nc):
        K.bookcase(mb, nc, xb - 0.17, -2.65, -90.0, w=1.1, d=0.32, h=2.1, shelves=5, rng_seed=91, fill=0.7)
    P(aset, "SM_Int_Cabinet", xb - 0.5, -5.4, zf, -90.0)
    P(aset, "SM_Int_TeaSet", xb - 0.5, -5.4, zf + 1.18, -90.0)
    P(aset, "SM_Int_PottedPlantB", xa + 0.45, IY0 + 0.45, zf, 0.0)
    P(aset, "SM_Int_Painting", xa, -4.0, zf + 1.4, 90.0)
    K.poster(nc, aset, xa, -2.3, zf + 1.6, 90.0, 0.7, 0.9, "M_IntPoster3", text="RA", text_color=(0.6, 0.3, 0.02),
             text_size=0.22)
    K.pendant(aset, 18.95, -3.9, ceil, "lamp")
    for x in (17.3, 20.0):
        curtain(nc, x, IY0, zf + 0.85, zf + 2.75, 180.0, 1.2, "M_IntFabricRed")
    aset.text("DORM SUPERVISOR", K.wall_point(17.2, -0.9, 180.0, 0.02, zf + 2.35), 180.0, size=0.09,
              color=(0.45, 0.28, 0.05))
    K.camera(aset, "office", (16.5, -1.6, zf + 1.65), (20.5, -6.0, zf + 0.9), 16.0)
    # laundry
    xa, xb = BAYX + TP / 2, PART[1] - TP / 2
    finish(mb, BAYX, CY, PART[1], IY1, zf, "M_IntTileBlue")
    for k, y in enumerate((2.1, 2.75, 3.4, 4.05, 4.7, 5.35)):
        washer(mb, nc, xa + 0.32, y, zf, 90.0, dryer=k >= 4)
    study_table(mb, 8.2, 3.9, zf, 90.0, L=1.6, W=0.9, top=K.TRIM_WHITE, h=0.9)
    for k, (x, y) in enumerate(((8.1, 3.4), (8.3, 4.4))):
        P(aset, "SM_Int_Basket", x, y, zf + 0.9, k * 50.0)
    P(aset, "SM_Int_SteelShelves", xb - 0.3, 3.9, zf, -90.0)
    P(aset, "SM_Int_Box", xb - 0.3, 3.9, zf + 2.14, -90.0)
    for k in range(5):       # drying rack with towels
        x = 7.0 + k * 0.35
        nc.box((x, 5.75, zf + 0.75), (0.02, 0.5, 1.5), K.METAL)
        nc.box((x + 0.17, 5.75, zf + 1.2), (0.3, 0.02, 0.5), ("M_IntFabricYellow", "M_IntFabricWhite",
                                                                 "M_IntFabricBlue", "M_IntFabricOrange")[k % 4])
    nc.box((7.7, 5.75, zf + 1.5), (1.6, 0.03, 0.03), K.METAL)
    K.panel_light(aset, nc, 7.8, 3.9, ceil, w=1.0, d=0.35, intensity=2200.0)
    for x in (6.5, 9.2):
        curtain(nc, x, IY1, zf + 0.85, zf + 2.75, 0.0, 1.2, "M_IntFabricWhite")
    # detergent shelf over the machines, folded laundry, baskets waiting on the floor
    mb.box_mm((xa, 1.9, zf + 1.45), (xa + 0.3, 5.7, zf + 1.48), K.WOOD)
    for k in range(9):
        nc.cylinder((xa + 0.15, 2.05 + k * 0.4, zf + 1.48), 0.055, 0.2 + 0.05 * (k % 3),
                    ("M_IntFabricBlue", "M_IntTrimWhite", "M_IntFabricOrange", "M_IntFabricGreen")[k % 4], seg=8)
    for k, (x, y) in enumerate(((7.9, 3.55), (8.45, 4.25), (7.95, 4.35))):
        for j in range(3 + k % 2):
            nc.box((x, y, zf + 0.92 + j * 0.05), (0.32, 0.26, 0.045),
                   ("M_IntFabricWhite", "M_IntFabricBlue", "M_IntFabricYellow")[(j + k) % 3])
    for k, (x, y) in enumerate(((9.4, 5.3), (9.0, 2.3))):
        P(aset, "SM_Int_Basket", x, y, zf, 20.0 + k * 70.0)
        nc.sphere((x, y, zf + 0.12), 0.16, ("M_IntFabricWhite", "M_IntFabricBlue")[k], seg=8, rings=5)
    aset.text("LAUNDRY  -  6:00 - 22:00", K.wall_point(7.8, IY1, 0.0, 0.03, zf + 2.55), 0.0, size=0.1,
              color=(0.35, 0.22, 0.05))
    K.camera(aset, "laundry", (10.0, 1.5, zf + 1.65), (5.6, 5.6, zf + 0.7), 16.0)
    # dorm kitchen
    xa, xb = PART[1] + TP / 2, IX1
    finish(mb, PART[1], CY, IX1, IY1, zf, K.TILE)
    K.wainscot(mb, (IX1, IY1), (xa, IY1), zf, 0.78, "M_IntTileBlue", cap=K.TRIM_WHITE)
    with lift(zf, mb, nc):
        K.kitchen_run(mb, nc, 11.4, IY1, 16.4, against="+y", upper=False)
        K.kitchen_run(mb, nc, 17.6, IY1, 19.6, against="+y", upper=False)
        K.counter(mb, 14.0, 3.4, 17.6, 4.3, 0.9, body=K.TRIM_WHITE, top=K.METAL)
    for y in (3.7, 4.4):
        P(aset, "SM_Int_Stove", xa + 0.38, y, zf, 90.0)
        nc.cylinder((xa + 0.38, y, zf + 0.91), 0.17, 0.3, K.METAL, seg=12)
    fridge(mb, nc, xb - 0.38, 5.7, zf, -90.0)
    P(aset, "SM_Int_SteelShelves", 15.4, RYB + 0.3, zf, 180.0)
    P(aset, "SM_Int_SteelShelves", 16.7, RYB + 0.3, zf, 180.0)
    for k, x in enumerate((15.1, 15.7, 16.4, 17.0)):
        P(aset, "SM_Int_Box" if k % 2 else "SM_Int_Basket", x, RYB + 0.3, zf + 2.14, k * 20.0)
    P(aset, "SM_Int_Microwave", 18.6, IY1 - 0.32, zf + 0.9, 0.0)
    P(aset, "SM_Int_Kettle", 19.2, IY1 - 0.3, zf + 0.9, 0.0)
    P(aset, "SM_Int_Kettle", 12.3, IY1 - 0.3, zf + 0.9, 60.0)
    # prep island dressing: chopping board, vegetables, pot rack above
    mb.box_mm((14.5, 3.6, zf + 0.9), (15.1, 4.0, zf + 0.93), K.WOOD)
    for k in range(5):
        nc.sphere((15.4 + k * 0.17, 3.85 + (k % 2) * 0.1, zf + 0.95), 0.05,
                  ("M_IntFabricOrange", "M_IntFabricGreen", "M_IntFabricRed")[k % 3], seg=8, rings=6)
    nc.box((15.8, 3.85, ceil - 0.6), (2.6, 0.06, 0.04), K.METAL)
    for k in range(5):
        x = 14.8 + k * 0.5
        nc.box((x, 3.85, ceil - 0.3), (0.02, 0.02, 0.6), K.METAL)
        nc.cylinder((x, 3.85, ceil - 0.95), 0.13 - 0.01 * k, 0.07, K.METAL, seg=10)
        nc.box((x, 3.85, ceil - 0.78), (0.03, 0.03, 0.18), K.WOOD_DARK)
    for x in (13.0, 17.0, 20.0):
        K.panel_light(aset, nc, x, 3.9, ceil, w=1.2, d=0.35, intensity=2600.0)
    aset.text("TO CAFETERIA", K.wall_point(IX1, KDOOR_Y, -90.0, 0.02, zf + 2.4), -90.0, size=0.1,
              color=(0.45, 0.28, 0.05))
    K.poster(nc, aset, IX1, 3.45, zf + 1.7, -90.0, 0.6, 0.8, "M_IntPaper", text="RA CURRY", text_color=(0.7, 0.35, 0.05),
             text_size=0.09)
    for x in (11.9, 14.6, 17.3, 20.0):
        curtain(nc, x, IY1, zf + 0.85, zf + 2.75, 0.0, 1.2, "M_IntFabricYellow", frac=0.15)
    K.camera(aset, "kitchen", (12.0, 1.6, zf + 1.7), (20.0, 5.5, zf + 0.8), 15.0)


def _dress_ground(aset, mb, nc):
    """Detail + scale pass for the ground floor: fixtures, ceilings, panelling, wall decor, surfaces, clutter."""
    zf, ceil = FLOORS[0], CEILS[0]
    hx0, hx1 = -BAYX + TP / 2, BAYX - TP / 2
    # ================= entrance hall: coffered ceiling, panelling, shoe lockers, pictures, banners
    coffers(mb, hx0, IY0, hx1, IY1, ceil, step=2.0, skip=[HOLE_A])
    K.wainscot(mb, (hx1, IY1), (hx0, IY1), zf, 0.8, K.WOOD, cap=K.TRIM_WOOD, gaps=[(hx1 - 0.9, hx1 + 0.9)])
    for sx in (-1, 1):
        getabako(mb, nc, sx * 3.1, YBAY + TE + 0.18, zf, 180.0, w=2.6, h=1.1, d=0.36, cols=8, rows=4,
                 seed=7 + sx)
        aset.text("SHOES OFF - SLIPPERS ON", K.wall_point(sx * 3.1, YBAY + TE, 180.0, 0.03, zf + 1.45), 180.0,
                  size=0.07, color=(0.45, 0.28, 0.05))
    # umbrella stand by the door
    nc.cylinder((-1.45, -6.35, zf), 0.15, 0.5, "M_IntSteelBlue", seg=12, cap_top=False)
    for k, (dx, dy, m) in enumerate(((-0.05, 0.03, "M_IntFabricYellow"), (0.06, -0.02, K.BLACK),
                                     (0.0, 0.07, "M_IntFabricBlue"))):
        nc.beam((-1.45 + dx, -6.35 + dy, zf + 0.05), (-1.45 + dx * 2, -6.35 + dy * 2, zf + 0.85), 0.03, 0.03, m)
    frames(aset, [("SM_Int_Painting", hx0, -1.3, zf + 1.45, 90.0), ("SM_Int_Frame", hx1, -0.0, zf + 2.5, -90.0),
                  ("SM_Int_Painting", -1.55, IY1, zf + 1.45, 0.0), ("SM_Int_Painting", 1.55, IY1, zf + 1.45, 0.0),
                  ("SM_Int_Frame", hx1, 5.6, zf + 1.4, -90.0)])
    banner(nc, aset, hx0, -5.6, zf + 3.55, 90.0, 1.0, 1.25, "RA")
    banner(nc, aset, hx1, -1.25, zf + 3.5, -90.0, 0.7, 1.1)
    banner(nc, aset, hx1, 1.25, zf + 3.5, -90.0, 0.7, 1.1)
    DT.dress_room(aset, mb, nc, hx0, IY0, hx1, IY1, zf, ceil, style="palace", seed=1,
                  keep_clear=[(hx0 - 0.1, 0.6, hx0 + 0.1, IY1), (hx0 - 0.1, -6.4, hx0 + 0.1, -4.8),
                              (hx1 - 0.1, -5.4, hx1 + 0.1, -2.6), (hx1 - 0.1, 2.3, hx1 + 0.1, 4.9)])
    DT.switch(nc, -1.35, YBAY + TE, zf + 1.1, 180.0)
    DT.exit_sign(nc, aset, 0.0, YBAY + TE, zf + 3.5, 180.0)
    DT.desk_set(nc, aset, 2.88, -4.0, zf + 1.05, 90.0, "office", seed=4, w=1.6, d=0.5)
    DT.calendar(nc, hx1, -1.0, zf + 1.5, -90.0, seed=2)
    # the stair: runner, gallery of photos going up, sloped panelling
    stair_runner(nc, -4.25, 0.75, FLOORS[0], FLOORS[1], 90.0, width=0.75)
    rz = lambda y: zf + (y - 0.75) / 0.27 * (FLOORS[1] - zf) / 19
    for k, (y, a) in enumerate(((1.3, "SM_Int_Frame"), (2.25, "SM_Int_Frame"), (3.1, "SM_Int_Painting"),
                                (4.0, "SM_Int_Frame"), (4.9, "SM_Int_Frame"))):
        aset.prop(a, (hx0, y, rz(y) + 1.45), 90.0)
    _poly2(mb, [(hx0 + 0.012, 0.75, zf), (hx0 + 0.012, 5.88, FLOORS[1]), (hx0 + 0.012, 5.88, FLOORS[1] + 0.9),
                (hx0 + 0.012, 0.75, zf + 0.9)], K.WOOD)
    mb.beam((hx0 + 0.03, 0.75, zf + 0.92), (hx0 + 0.03, 5.88, FLOORS[1] + 0.92), 0.05, 0.06, K.TRIM_WOOD)

    # ================= common lounge
    xa, xb = -PART[2] + TP / 2, -BAYX - TP / 2
    coffers(mb, xa, IY0, xb, IY1, ceil, step=2.7, mat=K.WOOD_DARK, w=0.2, h=0.18)
    K.wainscot(mb, (xa, IY0), (xb, IY0), zf, 0.8, K.WOOD, cap=K.TRIM_WOOD)
    K.wainscot(mb, (xb, IY1), (xa, IY1), zf, 0.8, K.WOOD, cap=K.TRIM_WOOD)
    K.wainscot(mb, (xb, IY0), (xb, IY1), zf, 0.8, K.WOOD, cap=K.TRIM_WOOD,
               gaps=[(2.2, 4.2), (IY1 - 0.95 - 0.05, IY1 + 0.95 + 0.05)])
    K.wainscot(mb, (xa, -1.8), (xa, IY1), zf, 0.8, K.WOOD, cap=K.TRIM_WOOD, gaps=[(0.9, 2.7)])
    frames(aset, [("SM_Int_Frame", -7.85, IY1, zf + 1.85, 0.0), ("SM_Int_Frame", -10.55, IY1, zf + 1.55, 0.0),
                  ("SM_Int_Painting", -13.25, IY1, zf + 1.5, 0.0), ("SM_Int_Frame", -7.85, IY0, zf + 1.6, 180.0),
                  ("SM_Int_Frame", -13.25, IY0, zf + 1.6, 180.0), ("SM_Int_WallClock", -10.55, IY0, zf + 2.4, 180.0)])
    for y in (-1.15, 1.15):
        P(aset, "SM_Int_SideTable", -9.55, y, zf, 0.0)
        P(aset, "SM_Int_OilLamp", -9.55, y, zf + 0.55, 0.0)
    DT.paper_stack(nc, -8.25, 0.35, zf + 0.49, 20.0, 4, seed=3)
    DT.book_stack(nc, -7.7, -0.3, zf + 0.49, 10.0, 3, seed=4)
    for k, tx in enumerate((-8.4, -12.0)):
        DT.card_spread(nc, tx - 0.15, -4.55, zf + 0.75, 15.0 + k * 30, n=5, seed=k)
        DT.card_spread(nc, tx + 0.1, -4.2, zf + 0.75, 195.0, n=5, seed=k + 5)
        DT.deck_box(nc, tx + 0.25, -4.6, zf + 0.75, 30.0, ("M_IntFabricYellow", "M_IntFabricRed")[k])
        DT.deck_box(nc, tx - 0.3, -4.15, zf + 0.75, 70.0, "M_IntFabricBlue")
    P(aset, "SM_Int_Ukulele", -10.2, 0.95, zf, 80.0)
    DT.paper_stack(nc, -14.1, 4.45, zf + 0.5, 0.0, 3, seed=9)
    DT.card_spread(nc, -13.95, 4.85, zf + 0.5, 90.0, n=6, seed=13)
    nc.box((-13.85, 4.3, zf + 0.51), (0.15, 0.1, 0.02), K.BLACK)                         # game controller
    DT.dress_room(aset, mb, nc, xa, IY0, xb, IY1, zf, ceil, style="dorm", seed=2,
                  keep_clear=[(xa - 0.1, -6.2, xa + 0.1, -1.7), (xb - 0.95, -1.0, xb, 1.0)])
    DT.floor_clutter(nc, aset, xa, IY0, xb, IY1, zf, "dorm", n=3, seed=12,
                     clear=[(xa, -6.7, xa + 0.5, -1.7), (xb - 1.0, -1.0, xb, 1.0), (xa, 3.6, -11.6, 6.7),
                            (-9.2, 3.8, -7.2, 6.7), (xa, -0.8, xa + 0.6, 0.8), (xb - 0.6, -4.4, xb, -2.6)])

    # ================= duel practice room
    xa, xb = IX0, -PART[2] - TP / 2
    DT.dress_room(aset, mb, nc, xa, IY0, xb, IY1, zf, ceil, style="school", seed=3,
                  keep_clear=[(xb - 0.1, -5.0, xb + 0.1, 6.2)])
    for y in (-2.0, 2.0):
        DT.coat_hooks(nc, xa, y, zf + 1.78, 90.0, n=3, dorm="ra", jackets=2, seed=int(y + 5))
    for y in (-3.4, 3.4):
        DT.duel_disk(nc, -18.85, y + 0.62, zf + 0.765, 10.0)
        DT.card_spread(nc, -19.5, y - 0.2, zf + 0.77, 0.0, n=4, seed=int(y + 9))
    P(aset, "SM_Int_Ball", -17.4, -6.2, zf, 0.0)
    K.poster(nc, aset, xa, -5.6, zf + 1.75, 90.0, 0.6, 0.85, "M_IntPoster2", text="SPELL SPEED", text_size=0.06)

    # ================= study room
    xa, xb = BAYX + TP / 2, PART[2] - TP / 2
    K.wainscot(mb, (xa, IY0), (xb, IY0), zf, 0.8, K.WOOD, cap=K.TRIM_WOOD)
    DT.dress_room(aset, mb, nc, xa, IY0, xb, RYF, zf, ceil, style="school", seed=4,
                  keep_clear=[(xa - 0.1, -6.3, xa + 0.1, -2.0), (xb - 0.1, -5.5, xb + 0.1, -2.3)])
    for k, tx in enumerate((7.6, 10.4, 13.2)):
        for s in (-1, 1):
            DT.paper_stack(nc, tx + s * 0.35, -4.1 + s * 0.2, zf + 0.76, 0.0, 3 + k, seed=k * 2 + s)
            DT.book_stack(nc, tx - s * 0.1, -4.1 + s * 0.25, zf + 0.76, 90.0, 2 + k % 2, seed=k + s)
            DT.mug(nc, tx + s * 0.6, -4.1 - s * 0.22, zf + 0.76, seed=k + 3 * s)
        DT.deck_box(nc, tx + 0.15, -4.35, zf + 0.76, 20.0 * k, "M_IntFabricYellow")
    with lift(zf, mb, nc):
        K.lockers(mb, nc, aset, 10.5, RYF - 0.23, 0.0, n=12, w=0.4, d=0.45, h=1.85, mat="M_IntFabricYellow")
    for k in range(12):
        nc.box((8.3 + k * 0.4, RYF - 0.457, zf + 1.6), (0.12, 0.004, 0.05), "M_IntPaper")       # name tags
    frames(aset, [("SM_Int_Frame", 8.75, RYF, zf + 2.4, 0.0), ("SM_Int_Frame", 12.2, RYF, zf + 2.4, 0.0)])
    K.bulletin(nc, aset, 15.2, RYF, zf + 1.1, 0.0, w=1.0, h=0.8, title="EXAM PLAN", rng_seed=41)
    nc.sphere((xa + 0.17, -2.6, zf + 2.45), 0.15, "M_IntCarpetBlue", seg=12, rings=8)        # globe on a case
    nc.cylinder((xa + 0.17, -2.6, zf + 2.3), 0.05, 0.05, K.TRIM_GOLD, seg=8)

    # ================= dorm supervisor's office
    xa, xb = PART[2] + TP / 2, IX1
    DT.dress_room(aset, mb, nc, xa, IY0, xb, RYF, zf, ceil, style="office", seed=5,
                  keep_clear=[(xb - 0.1, -3.3, xb + 0.1, -2.0), (xa - 0.1, -4.6, xa + 0.1, -1.8)])
    DT.paper_stack(nc, 19.45, -4.15, zf + 0.79, 10.0, 7, seed=5)
    DT.mug(nc, 19.65, -4.55, zf + 0.79, seed=6)
    DT.book_stack(nc, 18.0, -4.0, zf + 0.79, 90.0, 3, seed=7)
    DT.trophy(nc, xb - 0.5, -5.15, zf + 1.18, 1.1)
    DT.coat_hooks(nc, xa, -6.0, zf + 1.75, 90.0, n=2, dorm="white", jackets=1, seed=3)
    K.wainscot(mb, (xa, IY0), (xb, IY0), zf, 0.8, K.WOOD_DARK, cap=K.TRIM_WOOD)

    # ================= laundry
    xa, xb = BAYX + TP / 2, PART[1] - TP / 2
    DT.dress_room(aset, mb, nc, xa, RYB, xb, IY1, zf, ceil, style="service", seed=6,
                  keep_clear=[(xa - 0.1, 1.7, xa + 0.1, 5.7), (xb - 0.1, 3.2, xb + 0.1, 4.6)])
    mb.box_mm((xa, 1.85, zf + 1.55), (xa + 0.36, 5.65, zf + 2.25), K.TRIM_WHITE)              # wall cupboards
    for k in range(6):
        nc.box((xa + 0.362, 2.17 + k * 0.63, zf + 1.9), (0.004, 0.6, 0.66), "M_IntTrimWhite")
        nc.box((xa + 0.37, 2.17 + k * 0.63 + 0.24, zf + 1.65), (0.015, 0.03, 0.08), K.METAL)
    rnd = random.Random(5)
    for k, y in enumerate((2.1, 2.75, 3.4, 4.05, 4.7, 5.35)):                                  # detergent
        for j in range(rnd.randint(1, 2)):
            nc.cylinder((xa + 0.2 + j * 0.13, y + 0.15, zf + 0.92), 0.05, 0.22,
                        rnd.choice(("M_IntFabricBlue", "M_IntFabricOrange", "M_IntTrimWhite")), seg=8)
        nc.box((xa + 0.65, y, zf + 0.75), (0.004, 0.18, 0.05), "M_IntPaper")
    for k, (x, y) in enumerate(((7.4, 1.6), (9.4, 5.6), (6.6, 6.2))):
        P(aset, "SM_Int_Basket", x, y, zf, k * 40.0)
        nc.sphere((x, y, zf + 0.1), 0.15, ("M_IntFabricWhite", "M_IntFabricYellow")[k % 2], seg=8, rings=5)
    laundry_line(nc, 6.0, 9.7, 1.45, zf + 2.1, ("M_DetJacketYellow", "M_IntFabricWhite", "M_IntFabricBlue",
                                                 "M_IntFabricYellow"), seed=3)
    # ironing board + iron
    with nc.at((9.0, 2.4, zf), rot=0.0):
        nc.box((0, 0, 0.86), (1.2, 0.36, 0.03), "M_IntFabricBlue")
        nc.beam((-0.35, -0.12, 0.0), (0.3, 0.12, 0.85), 0.03, 0.03, K.METAL)
        nc.beam((0.3, -0.12, 0.0), (-0.35, 0.12, 0.85), 0.03, 0.03, K.METAL)
        nc.box((0.4, 0, 0.93), (0.22, 0.11, 0.1), K.TRIM_WHITE)
    K.poster(nc, aset, xb, 5.6, zf + 1.6, -90.0, 0.6, 0.8, "M_IntPaper", text="LAUNDRY RULES",
             text_color=(0.45, 0.28, 0.05), text_size=0.05)
    nc.box((8.2, 3.9, zf + 0.91), (0.5, 0.35, 0.03), "M_IntFabricWhite")                    # folded clothes
    nc.box((8.25, 3.95, zf + 0.94), (0.45, 0.3, 0.03), "M_DetJacketYellow")

    # ================= dorm kitchen
    xa, xb = PART[1] + TP / 2, IX1
    DT.dress_room(aset, mb, nc, xa, RYB, xb, IY1, zf, ceil, style="service", seed=7,
                  keep_clear=[(xa - 0.1, 3.3, xa + 0.1, 4.8), (xb - 0.1, 5.2, xb + 0.1, IY1),
                              (14.8, RYB - 0.1, 17.3, RYB + 0.1)])
    for px in (13.25, 15.95, 18.65):                       # open shelves in the piers between the windows
        for zz in (1.5, 1.95):
            wall_shelf(mb, nc, aset, px, IY1, zf + zz, 0.0, w=1.2, d=0.24, kind="kitchen", seed=int(px * 10 + zz))
    DT.table_set(nc, aset, 15.8, 3.85, zf + 0.9, 0.0, "kitchen", seed=2)
    with mb.at((0, 0, 0)):
        study_table(mb, 19.6, 1.55, zf, 0.0, L=1.2, W=0.7)
    for x in (19.2, 20.0):
        P(aset, "SM_Int_MetalStool", x, 2.2, zf, 0.0)
    DT.mug(nc, 19.3, 1.6, zf + 0.76, seed=1)
    DT.mug(nc, 19.9, 1.5, zf + 0.76, seed=2)
    DT.paper_stack(nc, 19.6, 1.45, zf + 0.76, 15.0, 2, seed=3)
    for k in range(6):                                                    # utensil rail over the left run
        nc.box((12.0 + k * 0.12, IY1 - 0.03, zf + 1.25), (0.02, 0.01, 0.22), (K.METAL, K.WOOD)[k % 2])
    nc.box((12.3, IY1 - 0.02, zf + 1.38), (0.9, 0.02, 0.02), K.METAL)
    nc.cylinder((13.25, IY1 - 0.35, zf + 0.9), 0.15, 0.25, K.TRIM_WHITE, seg=12)        # rice cooker
    nc.cylinder((13.25, IY1 - 0.35, zf + 1.15), 0.12, 0.03, "M_IntSteelBlue", seg=12)
    K.blackboard(mb, nc, aset, 18.3, RYB, zf + 1.3, 180.0, w=1.4, h=0.9,
                 lines=["MENU", "Mon: curry", "Tue: fish", "Wed: omurice"], size=0.08)
    DT.calendar(nc, 14.2, RYB, zf + 1.55, 180.0, seed=8)
    P(aset, "SM_Int_WallClock", 21.69, 4.4, zf + 2.4, -90.0)
    P(aset, "SM_Int_Extinguisher", 21.45, 1.4, zf, -90.0)
    with lift(zf, mb, nc):
        K.counter(mb, 12.95, RYB, 14.75, RYB + 0.62, 0.9, body=K.TRIM_WHITE, top=K.METAL)
        mb.box_mm((12.95, RYB, 1.5), (14.75, RYB + 0.35, 2.2), K.TRIM_WHITE)
    for k in range(4):
        cx = 13.175 + k * 0.45
        nc.box((cx, RYB + 0.625, zf + 0.5), (0.42, 0.01, 0.7), K.TRIM_WHITE)
        nc.box((cx, RYB + 0.355, zf + 1.85), (0.42, 0.01, 0.66), K.TRIM_WHITE)
        nc.box((cx + 0.15, RYB + 0.64, zf + 0.78), (0.12, 0.02, 0.025), K.METAL)
        nc.box((cx + 0.15, RYB + 0.37, zf + 1.56), (0.12, 0.02, 0.025), K.METAL)
    P(aset, "SM_Int_Microwave", 13.4, RYB + 0.3, zf + 0.9, 180.0)
    DT.shelf_fill(nc, aset, 14.3, RYB + 0.35, [zf + 0.9], 180.0, 0.9, 0.4, "kitchen", seed=5)
    for x0_, x1_, y_ in ((11.4, 16.4, IY1 - 0.95), (17.6, 19.6, IY1 - 0.95), (12.95, 14.75, RYB + 0.95)):
        nc.box(((x0_ + x1_) / 2, y_, zf + 0.006), (x1_ - x0_ - 0.2, 0.55, 0.012), K.BLACK)       # rubber mats
    for k, m in enumerate(("M_IntFabricBlue", "M_IntFabricGreen", "M_IntFabricYellow")):         # recycling bins
        mb.box_mm((17.4 + k * 0.42, RYB + 0.05, zf), (17.77 + k * 0.42, RYB + 0.45, zf + 0.62), m)
        nc.box((17.585 + k * 0.42, RYB + 0.25, zf + 0.63), (0.3, 0.3, 0.02), K.TRIM_WHITE)
    P(aset, "SM_Int_Drawers", 21.4, 4.4, zf, -90.0)


def _dress_upper(aset, mb, nc, fi):
    """Detail pass for the 2F / 3F stair hall (landing lounge / library), the corridors and the washroom."""
    zf, ceil = FLOORS[fi], CEILS[fi]
    hx0, hx1 = -BAYX + TP / 2, BAYX - TP / 2
    by = YBAY + TE
    # ---- stair hall: coffered ceiling, panelling, stair runner + sloped dado + gallery
    if fi == 1:
        coffers(mb, hx0, IY0, hx1, IY1, ceil, skip=[HOLE_B], nx=4, ny=6)
    else:
        coffers(mb, hx0, IY0, hx1, IY1, ceil, skip=[HOLE_C], nx=3, ny=6)
    K.wainscot(mb, (hx1, IY1), (hx0, IY1), zf, 0.8, K.WOOD, cap=K.TRIM_WOOD,
               gaps=[(hx1 - x - 0.75, hx1 - x + 0.75) for x in (-2.8, 0.0, 2.8)])
    if fi == 1:     # the 2F -> 3F flight climbs along the east wall
        stair_runner(nc, 4.25, 0.75, FLOORS[1], FLOORS[2], 90.0, width=0.75)
        rz = lambda y: zf + (y - 0.75) / 0.27 * (FLOORS[2] - zf) / 19
        _poly2(mb, [(hx1 - 0.012, 0.75, zf), (hx1 - 0.012, 0.75, zf + 0.9), (hx1 - 0.012, 5.88, FLOORS[2] + 0.9),
                    (hx1 - 0.012, 5.88, FLOORS[2])], K.WOOD)
        mb.beam((hx1 - 0.03, 0.75, zf + 0.92), (hx1 - 0.03, 5.88, FLOORS[2] + 0.92), 0.05, 0.06, K.TRIM_WOOD)
        for y in (1.4, 2.5, 3.6, 4.7):
            aset.prop("SM_Int_Frame" if y < 3 else "SM_Int_Painting", (hx1, y, rz(y) + 1.45), -90.0)
        # landing lounge dressing
        banner(nc, aset, hx0, -3.0, zf + 2.95, 90.0, 1.0, 1.45, "RA YELLOW")
        with lift(zf, mb, nc):
            K.bookcase(mb, nc, hx0 + 0.17, 1.65, 90.0, w=1.3, d=0.32, h=2.0, shelves=5, rng_seed=120)
        P(aset, "SM_Int_SideTable", -1.25, -2.2, zf, 0.0)
        P(aset, "SM_Int_OilLamp", -1.25, -2.2, zf + 0.55, 0.0)
        DT.paper_stack(nc, -3.2, -3.35, zf + 0.49, 30.0, 3, seed=7)
        DT.card_spread(nc, 0.4, 3.15, zf + 0.75, 10.0, n=5, seed=4)
        DT.mug(nc, 0.7, 3.5, zf + 0.75, seed=5)
        DT.mug(nc, 0.1, 3.55, zf + 0.75, seed=6)
        DT.deck_box(nc, 0.45, 3.5, zf + 0.75, 40.0, "M_IntFabricYellow")
        frames(aset, [("SM_Int_Frame", hx0, -5.7, zf + 2.25, 90.0), ("SM_Int_Mirror", -1.6, by, zf + 1.5, 180.0),
                      ("SM_Int_Painting", -1.45, IY1, zf + 1.55, 0.0), ("SM_Int_Painting", 1.45, IY1, zf + 1.55, 0.0),
                      ("SM_Int_WallClock", 1.75, by, zf + 2.3, 180.0)])
        DT.floor_clutter(nc, aset, -4.6, -6.6, -1.4, -1.2, zf, "dorm", n=2, seed=31)
        DT.dress_room(aset, mb, nc, hx0, IY0, hx1, IY1, zf, ceil, style="palace", seed=20 + fi,
                      keep_clear=[(hx0 - 0.1, -6.4, hx0 + 0.1, -1.0), (hx1 - 0.1, 0.6, hx1 + 0.1, IY1),
                                  (hx0 - 0.1, 0.9, hx0 + 0.1, 6.7)])
    else:           # 3F: library + the attic stair on the west wall
        stair_runner(nc, (HOLE_C[0] + HOLE_C[2]) / 2 - 0.02, 6.5, FLOORS[2], ZA, -90.0, width=0.75)
        _poly2(mb, [(hx0 + 0.012, 6.5, zf), (hx0 + 0.012, 0.83, ZA), (hx0 + 0.012, 0.83, ZA + 0.9),
                    (hx0 + 0.012, 6.5, zf + 0.9)], K.WOOD)
        # window seats in the bay + low bookcases between them
        for x in (-3.0, 0.0, 3.0):
            mb.box_mm((x - 0.72, by, zf), (x + 0.72, by + 0.45, zf + 0.42), K.WOOD)
            nc.box((x, by + 0.24, zf + 0.47), (1.4, 0.42, 0.1), "M_IntFabricYellow")
            for k, m in enumerate(("M_IntFabricRed", "M_IntFabricWhite")):
                with nc.at((x - 0.45 + k * 0.9, by + 0.12, zf + 0.68), rot=8 - 16 * k, rot_x=-12):
                    nc.box((0, 0, 0), (0.38, 0.12, 0.36), m)
        with lift(zf, mb, nc):
            for x in (-1.5, 1.5):
                K.bookcase(mb, nc, x, by + 0.16, 180.0, w=1.3, d=0.3, h=0.8, shelves=2, rng_seed=int(x * 10) + 140)
        DT.book_stack(nc, -1.5, by + 0.16, zf + 0.8, 0.0, 3, seed=2)
        P(aset, "SM_Int_PottedPlant", 1.8, by + 0.16, zf + 0.8, 0.0)
        for y in (-5.2, -2.8):
            for s in (-1, 1):
                DT.book_stack(nc, s * 0.2, y + s * 0.45, zf + 0.76, 90.0, 2, seed=int(y * 10) + s)
                DT.paper_stack(nc, -s * 0.2, y - s * 0.2, zf + 0.76, 90.0, 4, seed=int(-y * 10) + s)
            nc.box((-0.05, y + 0.1, zf + 0.765), (0.42, 0.3, 0.012), "M_IntPaper")       # open book
            nc.box((-0.05, y + 0.1, zf + 0.772), (0.01, 0.3, 0.004), K.WOOD_DARK)
            DT.mug(nc, 0.3, y - 0.55, zf + 0.76, seed=int(-y))
        P(aset, "SM_Int_Ladder", -4.3, -4.6, zf, 90.0)
        nc.cylinder((3.9, -1.55, zf), 0.18, 0.05, K.WOOD_DARK, seg=10)                    # globe on a stand
        nc.cylinder((3.9, -1.55, zf + 0.05), 0.03, 0.75, K.WOOD_DARK, seg=8)
        nc.sphere((3.9, -1.55, zf + 0.98), 0.24, "M_IntCarpetBlue", seg=14, rings=10)
        nc.torus((3.9, -1.55, zf + 0.98), 0.27, 0.012, K.TRIM_GOLD, seg=20, tube_seg=4)
        frames(aset, [("SM_Int_WallClock", -1.5, by, zf + 2.6, 180.0)])
        DT.dress_room(aset, mb, nc, hx0, IY0, hx1, IY1, zf, ceil, style="school", seed=20 + fi,
                      keep_clear=[(hx0 - 0.1, -6.7, hx0 + 0.1, IY1), (hx1 - 0.1, -6.7, hx1 + 0.1, -1.4)])
    # ---- corridors (both wings): crown moulding, cross beams at the partitions, pictures, fixtures
    for wing in (-1, 1):
        lo, hi = sorted((wing * BAYX, wing * IX1))
        crown(mb, lo, -CY + TP / 2, hi, CY - TP / 2, ceil, d=0.1)
        for v in PART[1:]:
            x = wing * v
            mb.box_mm((x - 0.12, -CY + TP / 2, ceil - 0.24), (x + 0.12, CY - TP / 2, ceil), K.TRIM_WHITE)
            for yy, yaw in ((-CY + TP / 2, 180.0), (CY - TP / 2, 0.0)):       # pilasters under the beams
                mb.box_mm((x - 0.12, min(yy, yy + (0.06 if yaw == 180.0 else -0.06)), zf + 0.95),
                          (x + 0.12, max(yy, yy + (0.06 if yaw == 180.0 else -0.06)), ceil - 0.24), K.TRIM_WHITE)
        for x, y, yaw in ((wing * 15.95 - wing * 0.6, -CY + TP / 2, 180.0), (wing * 10.55 + wing * 0.6, CY - TP / 2, 0.0),
                          (wing * 15.95 + wing * 0.6, CY - TP / 2, 0.0)):
            aset.prop("SM_Int_Frame", (x, y, zf + 1.65), yaw)
        DT.exit_sign(nc, aset, wing * (BAYX + 0.4), CY - TP / 2, ceil - 0.25, 0.0)
        for k in range(3):
            x = wing * (BAYX + 2.8 + k * 5.4)
            DT.ceiling_fixture(nc, x, 0.0, ceil, "smoke")
            DT.outlet(nc, x + 0.9, -CY + TP / 2, zf + 0.3, 180.0)
        P(aset, "SM_Int_Bench", wing * 6.3, -0.62, zf, 180.0)
        DT.floor_clutter(nc, aset, lo + 0.6, -0.9, hi - 0.6, 0.9, zf, "dorm", n=3, seed=fi * 10 + wing,
                         clear=[(x - 0.8, -1.0, x + 0.8, 1.0) for x in
                                (wing * 7.775, wing * 13.25, wing * 17.0, wing * 18.8, wing * 6.3)])
    # ---- washroom (east front)
    xa, xb = PART[2] + TP / 2, IX1
    yc, ye = RYF, IY0
    DT.dress_room(aset, mb, nc, xa, ye, xb, yc, zf, ceil, style="service", seed=40 + fi,
                  keep_clear=[(xa - 0.1, ye, xa + 0.1, yc - 1.4), (17.9, yc - 0.1, xb, yc + 0.1)])
    for k in range(4):                                    # towels on a rail along the east wall
        with nc.at((xb - 0.04, -5.05 + k * 0.42, zf + 1.35), rot=-90.0):
            nc.box((0, 0, 0), (0.34, 0.03, 0.55), ("M_IntFabricWhite", "M_IntFabricYellow", "M_IntFabricBlue")[k % 3])
    nc.box((xb - 0.05, -4.4, zf + 1.63), (0.03, 1.7, 0.03), K.METAL)
    rack(mb, nc, aset, xb - 0.22, -6.0, zf, -90.0, w=1.0, d=0.4, levels=(0.1, 0.55, 1.0, 1.45), kind="store",
         seed=fi + 3)
    for k in range(3):                                    # soap dispensers + hand dryer
        nc.box((xa + 0.03, ye + 0.95 + k * 0.95 + 0.3, zf + 1.15), (0.06, 0.1, 0.18), K.TRIM_WHITE)
    nc.box((xa + 0.08, yc - 1.1, zf + 1.2), (0.16, 0.3, 0.3), K.TRIM_WHITE)
    for k, (x, y) in enumerate(((18.55, ye + 0.35), (18.6, -3.4), (19.05, -3.4))):
        P(aset, "SM_Int_Bucket", x, y, zf, k * 30.0)
        nc.cylinder((x + 0.22, y + 0.32, zf), 0.15, 0.22, "M_IntFabricYellow", seg=10)        # bath stools
    for k in range(2):
        nc.box((16.2 + k * 0.32, -1.35, zf + 0.025), (0.11, 0.26, 0.05), "M_IntFabricYellow")
        nc.box((16.34 + k * 0.32, -1.35, zf + 0.025), (0.11, 0.26, 0.05), "M_IntFabricYellow")
    K.poster(nc, aset, 18.65, IY0, zf + 1.65, 180.0, 0.5, 0.7, "M_IntPaper", text="KEEP IT CLEAN",
             text_color=(0.2, 0.3, 0.6), text_size=0.045)


def _dress_more(aset, mb, nc):
    """Second detail layer where the first pass still left big bare surfaces (floor mats, cubbies, door boards)."""
    zf = FLOORS[0]
    # ---- laundry: rubber mat in front of the machines, coin box signs, tall cupboard, utility sink
    xa, xb = BAYX + TP / 2, PART[1] - TP / 2
    nc.box((xa + 0.95, 3.7, zf + 0.006), (0.6, 3.8, 0.012), K.BLACK)
    for k, y in enumerate((2.1, 2.75, 3.4, 4.05, 4.7, 5.35)):
        nc.box((xa + 0.005, y, zf + 1.25), (0.01, 0.4, 0.22), "M_IntPoster3" if k % 2 else "M_IntPaper")
    aset.text("WASH 200 / DRY 100", K.wall_point(xa, 3.7, 90.0, 0.02, zf + 1.42), 90.0, size=0.07,
              color=(0.45, 0.28, 0.05))
    with lift(zf, mb, nc):
        K.wardrobe(mb, 7.85, IY1 - 0.3, 0.0, w=1.0, d=0.55, h=2.1, mat=K.TRIM_WHITE)
        K.counter(mb, xb - 0.6, 5.45, xb, 6.35, 0.88, body=K.TRIM_WHITE, top="M_IntSteelBlue")
    nc.box((xb - 0.3, 5.9, zf + 0.89), (0.45, 0.6, 0.01), K.METAL)
    nc.cylinder((xb - 0.08, 5.9, zf + 0.88), 0.02, 0.32, K.METAL, seg=8)
    P(aset, "SM_Int_Bucket", xb - 0.3, 5.0, zf, 20.0)
    # ---- lounge: games sideboard between the duel-room door and the TV corner
    P(aset, "SM_Int_Cabinet", -PART[2] + TP / 2 + 0.31, 2.1, zf, 90.0)
    P(aset, "SM_Int_Books", -PART[2] + TP / 2 + 0.3, 1.8, zf + 1.18, 90.0)
    P(aset, "SM_Int_Radio", -PART[2] + TP / 2 + 0.3, 2.45, zf + 1.18, 90.0)
    with lift(zf, mb, nc):                                  # alcove shelves either side of the chimney breast
        for y in (-1.8, 1.75):
            K.bookcase(mb, nc, -BAYX - TP / 2 - 0.16, y, -90.0, w=1.3, d=0.3, h=2.2, shelves=5, rng_seed=int(y * 10) + 160)
    # ---- library: second reading corner, book cart, piles by the chairs
    z3 = FLOORS[2]
    P(aset, "SM_Int_Armchair", 3.6, -5.75, z3, 200.0)
    P(aset, "SM_Int_SideTable", 3.75, -4.75, z3, 0.0)
    P(aset, "SM_Int_OilLamp", 3.75, -4.75, z3 + 0.55, 0.0)
    P(aset, "SM_Int_Armchair", -3.6, -5.75, z3, 160.0)
    for x in (-3.0, 3.0):
        DT.book_stack(nc, x, -5.2, z3, 30.0, 5, seed=int(x + 7))
    mb.box_mm((-3.3, -4.6, z3 + 0.62), (-2.7, -4.0, z3 + 0.66), K.WOOD_DARK)          # chess table
    mb.box_mm((-3.05, -4.35, z3), (-2.95, -4.25, z3 + 0.62), K.WOOD_DARK)
    P(aset, "SM_Int_Chess", -3.0, -4.3, z3 + 0.66, 10.0)
    for dx in (-0.6, 0.6):
        P(aset, "SM_Int_FoldingStool", -3.0 + dx, -4.3, z3, 90.0)
    with nc.at((-2.4, -1.9, z3), rot=20.0):                 # book cart
        nc.box((0, 0, 0.35), (0.8, 0.4, 0.03), K.WOOD)
        nc.box((0, 0, 0.75), (0.8, 0.4, 0.03), K.WOOD)
        for sx in (-1, 1):
            nc.box((sx * 0.39, 0, 0.42), (0.03, 0.4, 0.84), K.WOOD_DARK)
        for zz in (0.365, 0.765):
            for k in range(14):
                nc.box((-0.35 + k * 0.05, 0, zz + 0.12), (0.04, 0.28, 0.24), K.FABRICS[(k * 3) % 7])
    # ---- washroom: cleaning cart parked mid-room
    for fi in (1, 2):
        P(aset, "SM_Int_ToolCart", 19.4, -4.4, FLOORS[fi], 0.0)
        with lift(FLOORS[fi], mb, nc):
            K.wardrobe(mb, IX1 - 0.28, -3.0, -90.0, w=0.8, d=0.55, h=2.0, mat=K.TRIM_WHITE)
        nc.cylinder((20.6, -4.4, FLOORS[fi]), 0.18, 0.5, "M_IntSteelBlue", seg=12, cap_top=False)
    # ---- corridor ends: tall plants
    for fi in (1, 2):
        for wing in (-1, 1):
            P(aset, "SM_Int_PottedPlantC", wing * (IX1 - 0.4), -0.5, FLOORS[fi], 0.0)
    # ---- attic hangout: old sofa + low cabinet with a radio east of the study nook
    P(aset, "SM_Int_SofaB", 3.3, 0.0, ZA, -90.0)
    P(aset, "SM_Int_MediaCabinet", 4.2, -1.95, ZA, 180.0)
    P(aset, "SM_Int_Radio", 4.6, -1.95, ZA + 0.68, 180.0)
    P(aset, "SM_Int_Books", 3.6, -1.95, ZA + 0.68, 180.0)
    # ---- lounge: low bookcases under the front windows
    with lift(zf, mb, nc):
        for x in (-6.5, -9.2, -11.9, -14.6):
            K.bookcase(mb, nc, x, IY0 + 0.16, 180.0, w=1.2, d=0.3, h=0.8, shelves=2, rng_seed=int(-x * 10) + 170)
    for x in (-6.5, -11.9):
        P(aset, "SM_Int_PottedPlant", x + 0.3, IY0 + 0.16, zf + 0.8, 0.0)
    # ---- library: reading sofa facing the bay
    P(aset, "SM_Int_Sofa", 0.0, -1.45, z3, 0.0)
    # ---- attic: boxes + trunks along the back slope behind the nook
    for k, x in enumerate((-2.6, -1.9, -0.6, 0.4, 1.6, 2.4, 4.9)):
        P(aset, "SM_Int_Box", x, 4.75 + 0.2 * (k % 2), ZA, 12.0 * k)
    for x in (-1.2, 3.4):
        mb.box_mm((x - 0.45, 4.1, ZA), (x + 0.45, 4.6, ZA + 0.5), K.WOOD_DARK, mats={"+z": K.WOOD})   # trunks
        nc.box((x, 4.09, ZA + 0.35), (0.12, 0.02, 0.1), K.TRIM_GOLD)
    # ---- attic: retired school furniture east of the chimney
    for k, x in enumerate((5.0, 7.7)):
        P(aset, "SM_Int_SchoolDesk", x, -1.5, ZA, 10.0 * k)
        P(aset, "SM_Int_SchoolChair", x, -0.85, ZA, 180.0 - 15.0 * k)
    P(aset, "SM_Int_Drawers", 8.6, -2.4, ZA, 0.0)
    # ---- servery: lamps over the serving line, tray cart
    for y in (-3.2, -0.6, 1.0):
        aset.prop("SM_Int_IndustrialLamp", (24.25, y, CZ + CWH - 0.3), 0.0)
    P(aset, "SM_Int_ToolCart", 23.65, -5.25, CZ, 0.0)
    for k in range(6):                                                    # queue posts + rope
        y = -4.0 + k * 1.0
        nc.cylinder((25.35, y, CZ), 0.12, 0.03, K.METAL, seg=10)
        nc.cylinder((25.35, y, CZ + 0.03), 0.025, 0.9, K.TRIM_GOLD, seg=8)
        if k < 5:
            nc.beam((25.35, y, CZ + 0.86), (25.35, y + 1.0, CZ + 0.86), 0.03, 0.03, "M_IntFabricRed")
    nc.box((25.0, -1.4, CZ + 3.4), (0.05, 2.4, 0.45), "M_AcademyYellow")      # hanging sign
    nc.box((25.0, -1.4, CZ + 3.8), (0.01, 2.0, 0.4), K.BLACK)
    aset.text("SERVING LINE", (24.97, -1.4, CZ + 3.3), -90.0, size=0.2, color=(0.45, 0.25, 0.05))
    aset.text("SERVING LINE", (25.03, -1.4, CZ + 3.3), 90.0, size=0.2, color=(0.45, 0.25, 0.05))
    for k in range(6):
        nc.box((23.65, -5.25, CZ + 0.97 + k * 0.025), (0.42, 0.32, 0.02), "M_AcademyYellow")
    # ---- cafeteria: exposed ceiling beams (dining hall under the gable roof)
    for x in (25.6, 28.6, 31.8, 35.0):
        mb.box_mm((x - 0.12, CY0 + 0.25, CZ + CWH - 0.6), (x + 0.12, CY1 - 0.25, CZ + CWH - 0.3), K.WOOD_DARK)
    mb.box_mm((CX0 + 0.25, -0.12, CZ + CWH - 0.55), (CX1 - 0.25, 0.12, CZ + CWH - 0.3), K.WOOD_DARK)
    # ---- washroom (2F + 3F): bath mats, toiletry cubbies under the windows, shelf over the mirrors
    for fi in (1, 2):
        z = FLOORS[fi]
        xa2, xb2 = PART[2] + TP / 2, IX1
        nc.box((xa2 + 0.9, -4.6, z + 0.006), (0.55, 2.6, 0.012), "M_IntFabricBlue")
        nc.box((19.85, -2.75, z + 0.006), (3.3, 0.45, 0.012), "M_IntFabricBlue")
        wall_shelf(mb, nc, aset, xa2, -4.55, z + 2.1, 90.0, w=2.6, d=0.22, kind="store", seed=fi + 30)
        for wx in (17.3, 20.0):
            rack(mb, nc, aset, wx, IY0 + 0.21, z, 180.0, w=1.1, d=0.38, levels=(0.08, 0.4, 0.72), kind="store",
                 seed=int(wx) + fi, mat=K.TRIM_WHITE)
            for k in range(3):
                nc.box((wx - 0.35 + k * 0.35, IY0 + 0.2, z + 0.49), (0.3, 0.28, 0.17),
                       ("M_IntFabricYellow", "M_IntFabricBlue", "M_IntFabricWhite")[k])
    # ---- corridors: a little cork board + photos beside every dorm room door, plants at the pilasters
    rnd = random.Random(77)
    for fi in (1, 2):
        z = FLOORS[fi]
        for wing in (-1, 1):
            for dx in (7.775, 13.25, 18.825):
                for y, yaw in ((-CY + TP / 2, 180.0), (CY - TP / 2, 0.0)):
                    if wing > 0 and dx > 18 and y < 0:
                        continue                          # washroom door
                    bx = wing * dx - 0.85
                    with nc.at((bx, y, z + 1.5), rot=yaw):
                        nc.box((0, -0.01, 0), (0.42, 0.02, 0.32), "M_IntCork")
                        nc.box((0, -0.012, 0), (0.46, 0.016, 0.36), K.TRIM_WOOD)
                        for k in range(3):
                            nc.box((-0.12 + k * 0.12, -0.022, rnd.uniform(-0.06, 0.06)), (0.09, 0.004, 0.12),
                                   rnd.choice(("M_IntPaper", "M_IntPoster1", "M_IntPoster2", "M_IntPoster4")))
            for v in PART[1:]:
                P(aset, "SM_Int_PottedPlant", wing * v + 0.3, -0.75, z, 0.0)
    # ---- cafeteria / servery: panelling, table settings, posters, drinks cooler, banners
    xi = CX0 + 0.25
    K.wainscot(mb, (CX1 - 0.25, CY1 - 0.25), (xi, CY1 - 0.25), CZ, 0.7, K.WOOD, cap=K.TRIM_WOOD,
               gaps=[(12.25 - 0.95, 12.25 + 0.95)])
    K.wainscot(mb, (xi, CY0 + 0.25), (CX1 - 0.25, CY0 + 0.25), CZ, 0.7, K.WOOD, cap=K.TRIM_WOOD,
               gaps=[(4.25 - 1.15, 4.25 + 1.15)])
    K.wainscot(mb, (CX1 - 0.25, CY0 + 0.25), (CX1 - 0.25, CY1 - 0.25), CZ, 0.7, K.WOOD, cap=K.TRIM_WOOD)
    for k, (tx, ty) in enumerate([(tx, ty) for tx in (27.0, 30.2, 33.4) for ty in (-2.8, 0.4, 3.4)]):
        if (tx, ty) == (27.0, -2.8):
            continue
        for s in (-1, 1):
            nc.cylinder((tx + s * 0.3, ty - 0.3 * s, CZ + 0.77), 0.12, 0.012, K.TRIM_WHITE, seg=14)
            DT.mug(nc, tx - s * 0.35, ty + 0.3 * s, CZ + 0.77, seed=k + s)
        nc.box((tx - 0.05, ty + 0.05, CZ + 0.82), (0.1, 0.06, 0.1), K.TRIM_WHITE)            # napkin box
        nc.cylinder((tx + 0.08, ty + 0.12, CZ + 0.77), 0.02, 0.08, "M_IntFabricRed", seg=6)  # sauce bottles
        nc.cylinder((tx + 0.12, ty + 0.08, CZ + 0.77), 0.02, 0.08, K.BLACK, seg=6)
    with lift(CZ, mb, nc):
        K.counter(mb, xi, 3.4, xi + 0.65, CY1 - 0.4, 0.9, body="M_AcademyYellow", top=K.TRIM_WHITE)
    mb.box_mm((xi, 3.55, CZ + 0.9), (xi + 0.6, 4.35, CZ + 2.05), K.METAL)                     # drinks cooler
    mb.box_mm((xi + 0.6, 3.6, CZ + 0.95), (xi + 0.61, 4.3, CZ + 2.0), "M_IntGlassClear")
    for k in range(4):
        for j in range(5):
            nc.cylinder((xi + 0.5, 3.68 + j * 0.13, CZ + 1.0 + k * 0.26), 0.035, 0.16,
                        ("M_IntFabricRed", "M_IntFabricGreen", "M_IntFabricYellow", "M_IntFabricBlue")[(j + k) % 4], seg=8)
    for k in range(4):                                                     # cutlery + tray station
        nc.box((xi + 0.33, 4.6 + k * 0.18, CZ + 0.95), (0.14, 0.14, 0.1), K.METAL)
    aset.text("DRINKS / CUTLERY", K.wall_point(xi, 4.3, 90.0, 0.02, CZ + 2.35), 90.0, size=0.11,
              color=(0.45, 0.25, 0.05))
    for k, x in enumerate((25.95, 29.45, 32.75)):
        banner(nc, aset, x, CY1 - 0.25, CZ + 3.75, 0.0, 0.7, 0.85, None, mat=("M_IntFabricYellow", "M_IntFabricRed",
                                                                            "M_IntFabricYellow")[k])
    K.poster(nc, aset, CX1 - 0.25, -1.9, CZ + 1.6, -90.0, 0.7, 0.95, "M_IntPoster3", text="TODAY'S SPECIAL",
             text_color=(0.55, 0.3, 0.02), text_size=0.06)
    DT.dress_room(aset, mb, nc, xi, CY0 + 0.25, CX1 - 0.25, CY1 - 0.25, CZ, CZ + CWH - 0.3, style="school", seed=60, ac=False,
                  keep_clear=[(xi - 0.1, -6.0, xi + 0.1, 6.0), (CX1 - 0.4, 0.8, CX1, 3.0)])


# ------------------------------------------------------------------ attic (under the hip roof)
def _lin(y):
    """Height of the attic ceiling lining (underside of a long roof slope) at depth y."""
    return ZRB + RH - RTH - abs(y) * RPITCH


def rack(mb, nc, aset, x, y, z, yaw, w=1.2, d=0.45, levels=(0.08, 0.5, 0.92, 1.34), kind="store", seed=0,
         mat=K.METAL):
    """Open shelving unit standing at floor z (boards at `levels` above it), back at local +Y, filled with
    real-size things."""
    h = levels[-1] + 0.03
    with mb.at((x, y, z), rot=yaw):
        for s in (-1, 1):
            for t in (-1, 1):
                mb.box((s * (w / 2 - 0.02), t * (d / 2 - 0.02), h / 2), (0.035, 0.035, h), mat)
        for lv in levels:
            mb.box((0, 0, lv), (w, d, 0.025), K.WOOD if mat == K.METAL else mat)
    zl = [z + lv + 0.0125 for lv in levels]
    if kind == "books":
        fill_books(nc, aset, x, y, zl, yaw, w, d, seed=seed)
    else:
        DT.shelf_fill(nc, aset, x, y, zl, yaw, w - 0.22, d, kind, seed=seed)


def attic(aset, mb, nc):
    """The roof space is a real attic: 5 m under the ridge, standing height over a 8 m wide strip, light from
    eight walk-in dormers. Reached by a stair from the 3F stair hall. West: dorm storage (suitcases, boxes,
    festival gear, retired furniture); centre: an attic study nook; east, under the back dormer x = 9:
    Bastion Misawa's observatory corner (raised platform with steps, telescope at the window, star charts)."""
    z = ZA
    hx0, hy0, hx1, hy1 = HOLE_C
    # floor boards (around the stairwell), stair from 3F (climbs towards the ridge, -y)
    for (a, b, c, d) in ((IX0, IY0, hx0, IY1), (hx1, IY0, IX1, IY1), (hx0, IY0, hx1, 0.83), (hx0, hy1, hx1, IY1)):
        K.floor_planks(mb, a, b, c, d, z, mat=K.WOODFLOOR, along="x", pitch=0.3)
    sx = (hx0 + hx1) / 2 - 0.02
    K.stairs(mb, sx, 6.5, FLOORS[2], z, -90.0, 1.1, mat=K.WOOD, riser=K.TRIM_WHITE, rail=K.TRIM_WOOD, run=0.27,
             rail_sides=(1,))
    for xs in (sx - 0.58, sx + 0.58):          # stringers
        mb.beam((xs, 6.5, FLOORS[2] + 0.08), (xs, 0.83, z - 0.1), 0.06, 0.36, K.TRIM_WOOD)
    # closed side under the stair (3F) + guard rails round the stairwell in the attic
    _poly2(mb, [(sx + 0.6, 6.5, FLOORS[2]), (sx + 0.6, 3.45, FLOORS[2]), (sx + 0.6, 3.45, FLOORS[2] + 2.0)],
           K.WOOD)
    K.railing(mb, [(hx1, 0.95), (hx1, hy1), (hx0, hy1)], z, h=1.0, mat=K.TRIM_WOOD, spacing=0.13)
    # walls closing off the void under the front cross gable (pediment)
    yk = -2.2
    mb.box_mm((-5.55, yk - 0.1, z), (5.55, yk, _lin(yk) + 0.05), IN_WHITE)
    for x in (-5.5, 5.5):
        _poly2(mb, [(x, yk, z), (x, -_y_at(z + RTH), z), (x, yk, _lin(yk))], IN_WHITE)
    # roof structure: ridge beam, rafters, hip rafters, collar ties; chimney stacks; light
    zr = ZRB + RH - RTH
    mb.box_mm((-RIDGE - 0.1, -0.1, zr - 0.22), (RIDGE + 0.1, 0.1, zr), K.WOOD_DARK)
    for k in range(int(2 * RIDGE / 0.9) + 1):
        x = -RIDGE + k * 0.9
        if any(abs(x - xd) < DRM_HW + 0.12 for xd in DORMER_X):
            continue
        for s in (-1, 1):
            mb.beam((x, s * 6.9, _lin(6.9) - 0.08), (x, s * 0.1, zr - 0.08), 0.07, 0.15, K.WOOD_DARK)
    for sx in (-1, 1):
        for s in (-1, 1):
            mb.beam((sx * RIDGE, 0.0, zr - 0.1), (sx * (W2 - 0.3), s * (D2 - 0.3), _lin(D2 - 0.3) - 0.1), 0.1, 0.2,
                    K.WOOD_DARK)
    zt = z + 2.35
    ties = [x for x in (-13.5, -11.7, -7.2, -3.6, -1.8, 0.0, 1.8, 3.6, 7.2, 11.7, 13.5)]
    for x in ties:
        mb.box_mm((x - 0.05, -_y_at(zt + 0.18 + RTH), zt), (x + 0.05, _y_at(zt + 0.18 + RTH), zt + 0.18), K.WOOD_DARK)
    for cx in (-6.5, 6.5):
        mb.box_mm((cx - 0.5, -0.6, z), (cx + 0.5, 0.6, ZRB + RH - 0.95), "M_RaChimney")
    for x in (-11.7, 0.0, 11.7):
        aset.prop("SM_Int_IndustrialLamp", (x, 0.0, zt), 0.0)
    for x in (-17.0, -9.0, 9.0):
        aset.light((x, 0.0, z + 2.0), (1.0, 0.86, 0.62), 2500.0, 8.0, night_only=False)
    DT.switch(nc, -5.0, yk, z + 1.1, 180.0)
    DT.outlet(nc, -3.0, yk, z + 0.3, 180.0)
    DT.outlet(nc, 3.0, yk, z + 0.3, 180.0)
    for x in (-9.0, 0.9, 9.9):
        DT.ceiling_fixture(nc, x, 0.4, zt, "smoke")
    # ---- west: storage
    rnd = random.Random(23)
    for x in (-13.0, -11.5, -7.6):
        rack(mb, nc, aset, x, -3.55, z, 180.0, w=1.2, d=0.45, seed=int(-x * 10))
    for x in (-12.2, -10.4):
        rack(mb, nc, aset, x, 3.55, z, 0.0, w=1.2, d=0.45, kind="books", seed=int(-x * 7))
    for k, x in enumerate((-20.5, -19.6, -18.0, -16.6, -14.2, -12.6, -10.3, -8.0, -7.2)):
        for s in (-1, 1):
            if (s > 0 and -11.0 < x < -9.5) or rnd.random() < 0.25:
                continue
            y = s * rnd.uniform(5.0, 5.6)
            P(aset, "SM_Int_Box", x, y, z, rnd.uniform(-15, 15))
            if rnd.random() < 0.5:          # a smaller carton on top
                with nc.at((x, y, z + 0.34), rot=rnd.uniform(-25, 25)):
                    nc.box((0, 0, 0.13), (0.34, 0.3, 0.26), "M_ShopShelf")
                    nc.box((0, -0.151, 0.15), (0.16, 0.004, 0.08), "M_IntPaper")
    for k, (x, y, yaw) in enumerate(((-16.8, -4.6, 0.0), (-15.0, 4.7, 180.0), (-8.6, 4.75, 180.0))):
        P(aset, "SM_Int_Suitcase", x, y, z, yaw)
    P(aset, "SM_Int_OldBed", -19.0, 0.0, z, 90.0)
    P(aset, "SM_Int_RockingChair", -16.6, 1.6, z, 130.0)
    P(aset, "SM_Int_Dresser", -16.8, -2.6, z, 0.0)
    P(aset, "SM_Int_FoldingScreen", -14.2, 0.9, z, 75.0)
    P(aset, "SM_Int_Ladder", -10.4, -1.9, z, 20.0)
    P(aset, "SM_Int_HandTruck", -8.4, 2.0, z, 200.0)
    P(aset, "SM_Int_Wardrobe", -12.4, 0.2, z, 90.0, 0.85)
    P(aset, "SM_Int_TrashBag", -7.5, -2.2, z, 30.0)
    P(aset, "SM_Int_Broom", -7.0, -2.7, z, 10.0)
    for k, x in enumerate((-15.4, -14.9, -14.4)):                       # rolled-up futons
        with nc.at((x, -2.0, z + 0.21), rot_x=90):
            nc.cylinder((0, 0, -0.5), 0.2, 1.0, ("M_IntFabricYellow", "M_IntFabricWhite", "M_IntFabricBlue")[k], seg=10)
    for k in range(4):                                                    # festival lanterns on a line
        nc.sphere((-11.2 + k * 0.8, 0.0, zt - 0.25), 0.16, ("M_IntFabricRed", "M_IntFabricYellow")[k % 2], seg=8, rings=6)
    nc.beam((-11.7, 0.0, zt - 0.05), (-8.4, 0.0, zt - 0.05), 0.01, 0.01, K.BLACK)
    DT.floor_clutter(nc, aset, -21.0, -4.6, -5.8, 4.6, z, "store", n=8, seed=4,
                     clear=[(-21.0, -1.2, -17.0, 1.2), (-17.4, -3.2, -16.2, 2.2)])
    aset.text("STORAGE - LABEL YOUR BOXES!", K.wall_point(-7.0, 0.0, -90.0, 0.02, z + 1.9), -90.0, size=0.07,
              color=(0.97, 0.9, 0.7))
    # ---- centre: attic study nook at the top of the stair
    with lift(z, mb, nc):
        for x in (-2.4, -1.3, 1.3, 2.4):
            K.bookcase(mb, nc, x, yk + 0.17, 180.0, w=1.0, d=0.3, h=1.6, shelves=4, rng_seed=int(x * 10) + 90)
    K.rug(nc, -1.8, -1.6, 1.8, 1.4, z + 0.001, "M_IntCarpetYellow", border=K.TRIM_GOLD)
    ra_emblem(nc, 0.0, -0.1, z + 0.014, 0.45)
    P(aset, "SM_Int_LowTable", 0.0, -0.1, z, 0.0)
    P(aset, "SM_Int_TeaSet", 0.1, 0.0, z + 0.5, 20.0)
    for a in (90.0, -90.0):
        ox, oy = _rot(0.0, -1.1, a)
        P(aset, "SM_Int_Armchair", ox, -0.1 + oy, z, a + 180.0)
    P(aset, "SM_Int_Ottoman", 0.0, 1.0, z, 0.0)
    DT.card_spread(nc, -0.15, -0.3, z + 0.5, 10.0, n=6, seed=8)
    DT.deck_box(nc, 0.25, -0.35, z + 0.5, 30.0, "M_IntFabricYellow")
    K.poster(nc, aset, 0.0, yk, z + 2.15, 180.0, 1.6, 0.5, "M_IntPoster2", text="ATTIC STUDY CLUB", text_size=0.11)
    DT.calendar(nc, 3.5, yk, z + 1.4, 180.0, seed=5)
    # ---- east: Bastion's observatory corner under the back dormer at x = 9
    xd = 9.0
    zp = z + 1.32
    mb.box_mm((xd - 0.9, 2.5, z), (xd + 0.9, 4.45, zp), K.WOOD_DARK, mats={"+z": K.WOODFLOOR})
    with lift(z, mb, nc):
        K.stairs(mb, xd, 0.54, 0.0, zp - z, 90.0, 1.2, mat=K.WOOD, riser=K.TRIM_WHITE, run=0.28)
    for x in (xd - 0.9, xd + 0.9):
        K.railing(mb, [(x, 2.55), (x, 3.6)], zp, h=0.9, mat=K.TRIM_WOOD, spacing=0.13)
    # telescope on a tripod, aimed out of the window at the sea sky
    tz = zp + 1.0
    for a in (0.0, 120.0, 240.0):
        fx, fy = _rot(0.0, 0.35, a)
        nc.beam((xd + fx, 3.75 + fy, zp), (xd, 3.75, tz), 0.03, 0.03, K.WOOD)
    nc.beam((xd, 3.45, tz - 0.12), (xd, 4.25, tz + 0.28), 0.12, 0.12, "M_DetSilver")
    nc.beam((xd, 4.2, tz + 0.255), (xd, 4.32, tz + 0.31), 0.15, 0.15, K.BLACK)
    nc.beam((xd, 3.3, tz - 0.17), (xd, 3.45, tz - 0.12), 0.05, 0.05, K.BLACK)
    P(aset, "SM_Int_FoldingStool", xd - 0.35, 3.1, zp, 20.0)
    P(aset, "SM_Int_Binoculars", xd + 0.55, 2.75, zp, 40.0)
    for dx, txt in ((-1, "STAR MAP - N"), (1, "ORBITS")):
        K.poster(nc, aset, xd + dx * (DRM_HW - 0.1), 3.95, 14.05, -90.0 * dx, 0.55, 0.4, "M_IntChalkboard",
                 text=txt, text_size=0.05)
    # desk + chalkboard + charts beside the platform
    with lift(z, mb, nc):
        K.desk(mb, nc, 10.95, 2.4, 0.0, w=1.2, d=0.6, hutch=False, clutter=False)
        K.bookcase(mb, nc, 7.3, 2.6, 0.0, w=1.0, d=0.3, h=1.5, shelves=4, rng_seed=99)
    DT.desk_set(nc, aset, 10.95, 2.4, z + 0.76, 0.0, kind="student", seed=31, w=1.2, d=0.6)
    P(aset, "SM_Int_OfficeChair", 10.95, 1.5, z, 180.0)
    nc.sphere((7.3, 2.6, z + 1.68), 0.14, "M_IntCarpetBlue", seg=12, rings=8)              # star globe
    nc.cylinder((7.3, 2.6, z + 1.5), 0.05, 0.04, K.TRIM_GOLD, seg=8)
    P(aset, "SM_Int_Chalkboard", 12.5, 1.3, z, -110.0)
    chalk_panel(mb, 7.0, 0.0, z + 0.9, z + 2.0, 90.0, 1.1)
    chalk_lines(aset, 7.0, 0.0, 90.0, z + 1.82, ["T^2 / a^3 = const", "m = -2.5 log(F/F0)", "Sirius: -1.46",
                                                 "Misawa - do not erase!"], size=0.07, step=1.6)
    aset.text("MISAWA OBSERVATORY", (xd, DRM_YF - 0.12, 13.3), 0.0, size=0.08, color=(0.98, 0.85, 0.3))
    K.rug(nc, 9.9, 0.6, 12.2, 2.9, z + 0.001, "M_IntCarpetBlue", border=K.TRIM_GOLD)
    for k in range(6):
        nc.sphere((7.6 + (k * 0.41) % 1.7, -1.0 + (k * 0.67) % 1.6, z + 0.05), 0.05, "M_IntPaper", seg=6, rings=4)
    P(aset, "SM_Int_Box", 13.0, 4.9, z, 10.0)
    P(aset, "SM_Int_Box", 13.6, -5.0, z, -20.0)
    P(aset, "SM_Int_Suitcase", 16.6, 3.6, z, 160.0)
    P(aset, "SM_Int_RockingChair", 14.2, -1.6, z, -60.0)
    DT.floor_clutter(nc, aset, 12.5, -4.8, 21.0, 4.8, z, "store", n=6, seed=9, clear=[(12.0, 0.5, 13.2, 2.0)])
    # the middle of the attic: a rag rug, old trunks and a lantern on the collar tie
    nc.box_mm((0.6, 0.9, z + 0.001), (3.4, 2.9, z + 0.012), "M_IntFabricRed")
    nc.box_mm((0.75, 1.05, z + 0.012), (3.25, 2.75, z + 0.016), "M_IntFabricYellow")
    for k, (x, y, yaw) in enumerate(((0.2, 0.6, 10.0), (3.9, 3.1, -15.0), (4.3, 0.5, 30.0))):
        P(aset, "SM_Int_Suitcase", x, y, z, yaw)
    P(aset, "SM_Int_RockingChair", 2.0, 1.5, z, 150.0)
    P(aset, "SM_Int_Lantern", 2.6, 2.6, z, 0.0)
    nc.box((2.0, 1.9, z + 2.9), (0.02, 0.02, 0.6), K.BLACK)
    nc.cylinder((2.0, 1.9, z + 2.35), 0.12, 0.25, "M_IntWarmGlow", seg=8)
    K.camera(aset, "attic", (-4.3, 0.2, z + 1.65), (6.0, 2.6, z + 1.2), 16.0)
    K.camera(aset, "attic_obs", (12.0, -1.6, z + 1.6), (8.8, 3.6, z + 1.6), 16.0)
    K.camera(aset, "attic_west", (-5.6, -1.6, z + 1.65), (-17.0, 0.5, z + 0.9), 16.0)


def _interior(aset, mb, nc):
    rnd = random.Random(11)
    ground_floor(aset, mb, nc, rnd)
    _dress_ground(aset, mb, nc)
    for fi in (1, 2):
        center_upper(aset, mb, nc, fi)
        upper_floor(aset, mb, nc, fi, rnd)
        _dress_upper(aset, mb, nc, fi)
    attic(aset, mb, nc)
    _dress_more(aset, mb, nc)
    # Misawa's door sign (corridor side) + an NPC or two upstairs
    aset.text("B. MISAWA", K.wall_point(7.775 - 0.78, 0.9, 0.0, 0.02, FLOORS[2] + 1.55), 0.0, size=0.06,
              color=(0.45, 0.28, 0.05))
    aset.npc((-12.0, 0.0, FLOORS[1]), 90.0, dorm="ra", wander=3.0)
    aset.npc((1.0, -3.6, FLOORS[1]), 200.0, dorm="ra", wander=1.5)
    # preview cameras for the upper floors
    z2, z3 = FLOORS[1], FLOORS[2]
    K.camera(aset, "corridor2", (5.6, 0.0, z2 + 1.65), (21.0, 0.0, z2 + 1.2), 16.0)
    K.camera(aset, "dorm_front", (7.2, -1.35, z2 + 1.7), (8.2, -6.5, z2 + 0.6), 14.0)
    K.camera(aset, "dorm_back", (-13.25, 1.35, z2 + 1.7), (-13.25, 6.6, z2 + 0.9), 14.0)
    K.camera(aset, "misawa", (8.3, 6.3, z3 + 1.7), (8.0, 1.3, z3 + 1.4), 13.0)
    K.camera(aset, "misawa_eq", (6.2, 3.0, z3 + 1.6), (10.5, 4.6, z3 + 1.9), 16.0)
    K.camera(aset, "washroom", (20.9, -6.2, z3 + 1.7), (17.2, -1.6, z3 + 0.9), 14.0)
    K.camera(aset, "stairs", (3.0, -0.4, ZG + 1.6), (-4.2, 5.5, ZG + 2.4), 14.0)


# ------------------------------------------------------------------ cafeteria wing
def _cafeteria(aset, mb, nc, inc):
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
        # pass door from the dorm kitchen (its floor is 0.3 m higher: raised threshold + step inside)
        3: [dict(u=CY1 - KDOOR_Y, w=1.0, z0=ZG - CZ, z1=ZG - CZ + 2.15)],
    }
    mb.room([(CX0, CY0), (CX1, CY0), (CX1, CY1), (CX0, CY1)], CZ, CWH, 0.25, WALL, openings=ops,
            floor_mat="M_MarbleFloor", inner_mat="M_CreamWall")
    zt = CZ + CWH
    mb.poly([(CX0, CY0, zt - 0.3), (CX0, CY1, zt - 0.3), (CX1, CY1, zt - 0.3), (CX1, CY0, zt - 0.3)],
            "M_WhiteWall")
    # automatic doors in the existing doorways (front entrance + sea terrace)
    aset.door((CX0 + 4.5, CY0 + 0.125, CZ), 0.0, 2.0, 2.85, "ra", double=True)
    aset.door((CX1 - 12.5, CY1 - 0.125, CZ), 180.0, 1.6, 2.6, "ra", double=True)
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
            # the wall opening already carries its own sill (geo.wall); no second sill here
    mull((CX0, CY0), (CX1, CY0), [(1.8, 2.0), (7.7, 2.3), (10.5, 2.3), (13.3, 2.3)])
    mull((CX1, CY0), (CX1, CY1), [(2.2, 2.6), (6.0, 2.6), (9.8, 2.6)])
    mull((CX1, CY1), (CX0, CY1), [(2.6, 2.4), (5.9, 2.4), (9.2, 2.4)])
    for x in (CX0 + 3.15, CX0 + 6.0, CX0 + 9.1, CX0 + 11.9, CX1):
        mb.box((x, CY0 - 0.05, (CZ + zt) / 2), (0.3, 0.14, CWH), TRIM)
    for y in (CY0, -1.9, 1.9, CY1):
        mb.box((CX1 + 0.05, y, (CZ + zt) / 2), (0.14, 0.3, CWH), TRIM)
    for x in (CX1 - 4.25, CX1 - 7.55, CX1 - 11.05):
        mb.box((x, CY1 + 0.05, (CZ + zt) / 2), (0.3, 0.14, CWH), TRIM)
    for z0, z1, out in ((CZ - 0.1, CZ + 0.18, 0.12), (zt - 0.45, zt - 0.15, 0.3), (zt - 0.6, zt - 0.45, 0.12)):
        base = z0 < CZ
        _strip(mb, CX0, CY0 - out, CX1 + out, CY0 + 0.1, z0, z1, TRIM, "x",
               [(CX0 + 3.5, CX0 + 5.5)] if base else ())
        _strip(mb, CX0, CY1 - 0.1, CX1 + out, CY1 + out, z0, z1, TRIM, "x",
               [(CX1 - 13.3, CX1 - 11.7)] if base else ())
        mb.box_mm((CX1 - 0.1, CY0 + 0.1, z0), (CX1 + out, CY1 - 0.1, z1), TRIM)
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
    _cafeteria_interior(aset, mb, inc, zt)

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


def _cafeteria_interior(aset, mb, inc, zt):
    """Servery along the west wall (serving line in Ra yellow, back counter, kitchen pass door), dining tables,
    yellow pendant lamps, menu board, plants and a sun banner."""
    xi = CX0 + 0.25                              # inner face of the west wall
    # kitchen pass door: architrave + a step down from the raised threshold
    mb.box_mm((xi, KDOOR_Y - 0.6, CZ), (xi + 0.32, KDOOR_Y + 0.6, ZG - 0.15), "M_Marble")
    for s in (-1, 1):
        mb.box((xi + 0.015, KDOOR_Y + s * 0.545, ZG + 1.1), (0.03, 0.09, 2.2), TRIM)
    mb.box((xi + 0.015, KDOOR_Y, ZG + 2.195), (0.03, 1.18, 0.09), TRIM)
    aset.text("STAFF ONLY", K.wall_point(xi, KDOOR_Y, -90.0, 0.02, ZG + 2.32), -90.0, size=0.09,
              color=(0.45, 0.25, 0.05))
    # back counter along the west wall (hot plates, rice cooker, pots) + menu board above
    y0b, y1b = CY0 + 0.4, KDOOR_Y - 0.75
    with lift(CZ, mb, inc):
        K.counter(mb, xi, y0b, xi + 0.65, y1b, 0.92, body=K.TRIM_WHITE, top=K.METAL)
        K.counter(mb, 23.9, -4.4, 24.6, 1.6, 0.95, body="M_AcademyYellow", top=K.TRIM_WHITE)
    for k in range(5):
        y = y0b + 0.6 + k * 1.15
        mb.box_mm((xi + 0.08, y - 0.4, CZ + 0.92), (xi + 0.58, y + 0.4, CZ + 0.96), "M_IntSteelBlue")
        inc.cylinder((xi + 0.33, y, CZ + 0.96), 0.2 - 0.02 * (k % 2), 0.28 + 0.06 * (k % 3), K.METAL, seg=12)
        inc.cylinder((xi + 0.33, y, CZ + 1.24 + 0.06 * (k % 3)), 0.21, 0.02, K.METAL, seg=12)
    mb.box_mm((xi, -3.0, CZ + 2.1), (xi + 0.07, 1.4, CZ + 3.1), "M_DarkWood")       # menu board
    aset.text("TODAY: GRILLED FISH SET", (xi + 0.1, -0.8, CZ + 2.75), 90.0, size=0.2, color=(1.0, 0.95, 0.75))
    aset.text("CURRY  -  RAMEN  -  OMURICE", (xi + 0.1, -0.8, CZ + 2.4), 90.0, size=0.16, color=(1.0, 0.95, 0.75))
    # serving line: pans under a sneeze guard, tray rail, tray stack + cutlery at the start
    mb.box_mm((24.6, -4.4, CZ + 0.82), (24.9, 1.6, CZ + 0.86), K.METAL)               # tray rail
    for y in (-4.2, 1.4):
        mb.box_mm((24.5, y - 0.02, CZ + 0.95), (24.54, y + 0.02, CZ + 1.45), K.METAL)
    mb.box_mm((24.42, -4.2, CZ + 1.4), (24.58, 1.4, CZ + 1.43), "M_IntGlassClear")
    for k in range(6):
        y = -3.6 + k * 0.85
        mb.box_mm((23.98, y - 0.33, CZ + 0.95), (24.42, y + 0.33, CZ + 0.98), K.METAL)
        inc.box((24.2, y, CZ + 0.985), (0.36, 0.56, 0.01),
               ("M_IntFabricOrange", "M_IntFabricGreen", "M_IntFabricYellow", "M_IntFabricBeige",
                "M_IntFabricRed", "M_IntTrimWhite")[k])
    for k in range(8):
        inc.box((24.75, -4.2 + 0.0, CZ + 0.87 + k * 0.025), (0.32, 0.42, 0.02), "M_AcademyYellow")
    inc.cylinder((24.3, 1.35, CZ + 0.95), 0.08, 0.16, K.METAL, seg=10)
    P(aset, "SM_Int_Register", 24.25, 1.1, CZ + 0.95, 90.0)
    aset.text("RA YELLOW CAFETERIA", (24.62, -1.4, CZ + 0.55), 90.0, size=0.14, color=(0.5, 0.25, 0.04))
    # hanging menu boards over the line + plate stacks and a condiment caddy on the counter
    for k, (y, txt) in enumerate(((-3.2, "CURRY  300"), (-1.4, "TODAY: OMURICE"), (0.4, "UDON  250"))):
        inc.box((24.4, y, CZ + 2.55), (0.04, 1.3, 0.55), ("M_AcademyYellow", "M_IntChalkboard", "M_AcademyYellow")[k])
        for dy in (-0.55, 0.55):
            inc.box((24.4, y + dy, CZ + 3.1), (0.01, 0.01, 0.55), K.BLACK)
        aset.text(txt, (24.36, y, CZ + 2.48), 90.0, size=0.1, color=(0.35, 0.18, 0.02) if k != 1 else (1, 1, 1))
    for k, y in enumerate((-2.4, -0.4)):
        for j in range(6):
            inc.cylinder((24.35, y, CZ + 0.95 + j * 0.02), 0.12, 0.018, FRAME, seg=12)
    # dining tables (yellow chairs) - shifted east of the serving line
    for tx in (27.0, 30.2, 33.4):
        for ty in (-2.8, 0.4, 3.4):
            if (tx, ty) == (27.0, -2.8):
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
            inc.box((tx + 0.25, ty - 0.3, CZ + 0.775), (0.42, 0.3, 0.01), "M_AcademyYellow")     # tray
    for lx in (27.0, 30.2, 33.4):
        for ly in (-1.2, 2.0):
            inc.box((lx, ly, zt - 0.6), (0.02, 0.02, 0.7), "M_Black")
            inc.cylinder((lx, ly, zt - 1.2), 0.32, 0.25, "M_AcademyYellow", seg=12, radius_top=0.12)
            inc.sphere((lx, ly, zt - 1.2), 0.12, "M_LampGlow", seg=8, rings=6)
    aset.light((30.2, 0.4, zt - 1.0), (1.0, 0.88, 0.65), 9000.0, 14.0, night_only=False)
    aset.light((23.6, -1.4, zt - 1.2), (1.0, 0.9, 0.7), 3500.0, 7.0, night_only=False)
    # sun banner on the west wall, clock / tray return / water dispenser in the piers between the windows
    mb.box_mm((xi, -5.4, CZ + 2.25), (xi + 0.03, -3.6, CZ + 3.55), "M_AcademyYellow")
    with mb.at((xi + 0.035, -4.5, CZ + 2.9), rot_y=90.0):
        mb.cylinder((0, 0, 0), 0.36, 0.012, "M_Gold", seg=20)
    for k in range(12):
        a = k / 12 * math.tau
        mb.box((xi + 0.04, -4.5 + math.cos(a) * 0.5, CZ + 2.9 + math.sin(a) * 0.5), (0.012, 0.07, 0.07), "M_Gold")
    P(aset, "SM_Int_WallClock", 29.45, CY1 - 0.25, CZ + 3.0, 0.0)
    for p in ((36.35, 5.35), (36.35, -5.35)):
        P(aset, "SM_Int_PottedPlantB", p[0], p[1], CZ, 0.0)
    xe = CX1 - 0.25
    P(aset, "SM_Int_SteelShelves", xe - 0.25, 1.9, CZ, -90.0)
    for k in range(3):
        inc.box((xe - 0.25, 1.9, CZ + 0.45 + k * 0.48), (0.4, 1.0, 0.04), "M_AcademyYellow")
    aset.text("TRAY RETURN", K.wall_point(xe, 1.9, -90.0, 0.02, CZ + 2.3), -90.0, size=0.12,
              color=(0.45, 0.25, 0.05))
    mb.box_mm((33.7, CY0 + 0.25, CZ), (34.1, CY0 + 0.7, CZ + 1.1), K.TRIM_WHITE)     # water dispenser
    inc.cylinder((33.9, CY0 + 0.47, CZ + 1.1), 0.14, 0.4, "M_IntGlassClear", seg=10)
    K.camera(aset, "cafeteria", (35.8, -5.0, CZ + 1.7), (24.0, 1.0, CZ + 1.0), 18.0)
    K.camera(aset, "servery", (27.2, -4.8, CZ + 1.6), (23.0, 1.5, CZ + 1.0), 16.0)
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
    inner = aset.mesh("Ra_Interior")
    inner_nc = aset.mesh("Ra_Interior_NoCol")
    _main(aset, main, nc)
    _interior(aset, inner, inner_nc)
    _cafeteria(aset, caf, nc, inner_nc)
    _grounds(aset, grounds, nc)
    _sockets(aset)
    return aset


PLACEMENTS = {"ra": with_travel(build, [
    ("hall", "ra_hall", "Ra Yellow Hall", "The dorm's entrance hall, with the lounge and the practice duel tables next door."),
    ("cafeteria", "ra_cafeteria", "Ra Cafeteria", "Curry day every day. The best canteen on the island, say the Ra students."),
])}
