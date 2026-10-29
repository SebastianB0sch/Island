"""
Duel Academy Harbor + Lighthouse (south coast).

Placements
  harbor      origin = world (60, -1075); quay top z = 0 (world 3 m); the sea is south (-Y) of
              the quay face at y = -51, water level z = -3, basin bottom ~ z -15.
  lighthouse  origin = world (300, -1235); round platform top z = 0 (world 4 m), radius ~15 m.

Harbor layout (local metres, x along the coast)
  x -187..-163  y   3..27   raised helipad (top z 1.0), stairs north, cart ramp east
  x -133..-127  y -51..-111 wooden pier with a 12 m T-head, shelter and a boat landing (z -2.2)
  x -120..-35   y  22..42   warehouses "01" and "02" (02 has a raised loading dock)
  x  -75        y -74..-27  rail-mounted gantry crane over the quay edge
  x   30..56    y   4..24   ferry terminal / harbor office, waiting canopy, rooftop sign
  x   55        y -47..-56  gangway to the ferry's main deck (z 0 -> 1.05)
  x   25..95    y -55..-69  ferry (own mesh, 'floating' socket at (60, -62, -3))
  (120,-5) -> lighthouse    breakwater crown walkway (top z 1.05), parapet, railings, tetrapods

Meshes (SM_<name>)
  Harbor_Quay, Harbor_Pier, Harbor_Ferry (own origin: centre/waterline), Harbor_Warehouse,
  Harbor_Crane, Harbor_Terminal, Harbor_Heliport, Harbor_Breakwater, Harbor_NoCol
  Lighthouse_Tower, Lighthouse_Platform, Lighthouse_NoCol
"""

import math
import random

from . import AssetSet
from .. import config as C
from .. import palette

palette.register({
    "M_WarehouseRoof": dict(kind="opaque", color=(0.30, 0.34, 0.39), rough=0.6, metallic=0.3,
                            detail="Corrugated", tiling=0.5),
    "M_LifeboatOrange": dict(kind="opaque", color=(0.98, 0.45, 0.08), rough=0.5, detail=None),
    "M_HelipadLight": dict(kind="emissive", color=(0.35, 1.00, 0.45), strength=8.0),
})

TAU = math.tau

# ------------------------------------------------------------------ materials
CONC, DCONC, WCONC = "M_HarborConcrete", "M_DarkConcrete", "M_Concrete"
PWOOD, RUB = "M_PierWood", "M_Rubber"
METAL, DMETAL = "M_Metal", "M_DarkMetal"
WHITE, TRIM = "M_WhiteWall", "M_WindowFrame"
GLASS = "M_Glass"
BLUE, ROOF_BLUE, YELLOW = "M_AcademyBlue", "M_AcademyRoof", "M_AcademyYellow"
HULL, STRIPE, BOTTOM = "M_ShipHull", "M_ShipStripe", "M_ShipBottom"
DECK = "M_Wood"
CRANE_Y = "M_CrateYellow"
MARK = "M_HelipadMark"
GLOW = "M_LampGlow"
LH_W, LH_R = "M_LighthouseWhite", "M_LighthouseRed"

# ------------------------------------------------------------------ layout constants
HARBOR_POS = C.LOCATIONS["harbor"]["pos"]
LH_POS = C.LOCATIONS["lighthouse"]["pos"]
LH_DZ = C.LOCATIONS["lighthouse"]["height"] - C.LOCATIONS["harbor"]["height"]   # +1 m

QX0, QX1 = -235.0, 235.0
QY = -51.0                  # quay face
WATER = -3.0
WALL_BOT = -16.0
BED = -15.0
COPE_Y0 = QY - 0.35         # coping nose
KERB = (QY - 0.3, QY + 0.15)
COPE_TOP = 0.03

FERRY_POS = (60.0, -62.0, WATER)
F_DECK = 4.0                # ferry main deck above the waterline (ship-local)
F_HW = 7.2                  # ferry half beam at deck level
GANG_X = 55.0               # gangway centre (ship-local x = -5)
GANG_SHIP_X = GANG_X - FERRY_POS[0]

PIER_X = -130.0
PIER_HW = 3.0
PIER_END = -111.0
THEAD = (-136.0, -124.0, -111.0, -101.0)

HELI = (-175.0, 15.0)
HELI_HALF = 12.0
HELI_TOP = 1.0

CRANE_X = -75.0
RAIL_SEA, RAIL_LAND = -49.0, -35.0

LADDERS = [-220.0, -175.0, -100.0, -40.0, 15.0, 110.0, 205.0]
TERM_OFF = (10.0, 0.0, 0.0)  # terminal block (modelled around x 20..46) shifted so the canopy meets the gangway
YOKOHAMA = [30.0, 60.0, 90.0]


# ================================================================== small helpers
def _gap_runs(x0, x1, gaps):
    """Split [x0, x1] into runs that avoid the (a, b) gap intervals."""
    out, cur = [], x0
    for a, b in sorted(gaps):
        if b <= cur or a >= x1:
            continue
        if a > cur:
            out.append((cur, a))
        cur = max(cur, b)
    if cur < x1:
        out.append((cur, x1))
    return out


def _near(x, gaps, pad=0.0):
    return any(a - pad <= x <= b + pad for a, b in gaps)


def _unit(dx, dy):
    l = math.hypot(dx, dy) or 1.0
    return dx / l, dy / l


def _offset_pts(pts, off):
    """Offset a 2D polyline to the LEFT by `off` with mitred joints."""
    n = len(pts)
    out = []
    for i in range(n):
        if i == 0 or i == n - 1:
            a, b = (pts[0], pts[1]) if i == 0 else (pts[-2], pts[-1])
            d = _unit(b[0] - a[0], b[1] - a[1])
            nx, ny, k = -d[1], d[0], 1.0
        else:
            d1 = _unit(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1])
            d2 = _unit(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            n1, n2 = (-d1[1], d1[0]), (-d2[1], d2[0])
            nx, ny = _unit(n1[0] + n2[0], n1[1] + n2[1])
            k = 1.0 / max(0.3, nx * n1[0] + ny * n1[1])
        out.append((pts[i][0] + nx * off * k, pts[i][1] + ny * off * k))
    return out


def _ribbon(mb, pts, o_lo, o_hi, zb, zt, mat, top_mat=None, cap0=True, cap1=True):
    """Closed prism strip along a 2D polyline between left-offsets o_lo < o_hi.
    zb / zt: scalars or per-station lists."""
    n = len(pts)
    A = _offset_pts(pts, o_lo)       # right edge
    B = _offset_pts(pts, o_hi)       # left edge
    zb = zb if isinstance(zb, (list, tuple)) else [zb] * n
    zt = zt if isinstance(zt, (list, tuple)) else [zt] * n
    tm = top_mat or mat
    P = lambda q, z: (q[0], q[1], z)
    for i in range(n - 1):
        mb.quad(P(A[i], zt[i]), P(A[i + 1], zt[i + 1]), P(B[i + 1], zt[i + 1]), P(B[i], zt[i]), tm)
        mb.quad(P(A[i], zb[i]), P(A[i + 1], zb[i + 1]), P(A[i + 1], zt[i + 1]), P(A[i], zt[i]), mat)
        mb.quad(P(B[i + 1], zb[i + 1]), P(B[i], zb[i]), P(B[i], zt[i]), P(B[i + 1], zt[i + 1]), mat)
    if cap0:
        mb.quad(P(B[0], zb[0]), P(A[0], zb[0]), P(A[0], zt[0]), P(B[0], zt[0]), mat)
    if cap1:
        mb.quad(P(A[-1], zb[-1]), P(B[-1], zb[-1]), P(B[-1], zt[-1]), P(A[-1], zt[-1]), mat)


def _wedge(mb, origin, yaw, length, width, z0, z1, mat, zb=-0.3):
    """Solid ramp rising along local +x from z0 (x=0) to z1 (x=length)."""
    w = width / 2.0
    with mb.at(origin, rot=yaw):
        mb.quad((0, -w, z0), (length, -w, z1), (length, w, z1), (0, w, z0), mat)
        mb.poly([(0, -w, zb), (length, -w, zb), (length, -w, z1), (0, -w, z0)], mat)
        mb.poly([(length, w, zb), (0, w, zb), (0, w, z0), (length, w, z1)], mat)
        mb.quad((0, w, zb), (0, -w, zb), (0, -w, z0), (0, w, z0), mat)
        mb.quad((length, -w, zb), (length, w, zb), (length, w, z1), (length, -w, z1), mat)


def _band(mb, pts, z0, z1, mat, off=0.03):
    """Thin flat band (e.g. ribbon windows) on the outside (RIGHT side) of a 2D polyline."""
    pts2 = _offset_pts(pts, -off)
    for a, b in zip(pts2, pts2[1:]):
        mb.quad((a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1), mat)


def _rounded_rect(x0, x1, hw, rx, n=8):
    """CCW footprint: square stern edge at x0, straight sides, elliptical front from x1 (radius rx)."""
    pts = [(x0, -hw), (x1, -hw)]
    for k in range(1, n):
        a = -math.pi / 2 + math.pi * k / n
        pts.append((x1 + rx * math.cos(a), hw * math.sin(a)))
    pts += [(x1, hw), (x0, hw)]
    return pts


def _arc_wall(mb, r0, r1, z0, z1, a0, a1, mat, seg_deg=7.5, top_mat=None):
    """Curved wall segment between radii r0 < r1 and angles a0 < a1 (degrees, CCW)."""
    n = max(1, int(math.ceil((a1 - a0) / seg_deg)))
    ang = [math.radians(a0 + (a1 - a0) * i / n) for i in range(n + 1)]
    P = lambda r, a, z: (r * math.cos(a), r * math.sin(a), z)
    tm = top_mat or mat
    for i in range(n):
        a, b = ang[i], ang[i + 1]
        mb.quad(P(r1, a, z0), P(r1, b, z0), P(r1, b, z1), P(r1, a, z1), mat, smooth=True)      # outer
        mb.quad(P(r0, b, z0), P(r0, a, z0), P(r0, a, z1), P(r0, b, z1), mat, smooth=True)      # inner
        mb.quad(P(r1, a, z1), P(r1, b, z1), P(r0, b, z1), P(r0, a, z1), tm)                     # top
    a, b = ang[0], ang[-1]
    mb.quad(P(r0, a, z0), P(r1, a, z0), P(r1, a, z1), P(r0, a, z1), mat)
    mb.quad(P(r1, b, z0), P(r0, b, z0), P(r0, b, z1), P(r1, b, z1), mat)


def _tetrapod(mb, c, size, yaw, mat=WCONC):
    """Classic 4-legged breakwater armour unit resting on three legs."""
    L, r0, r1 = 0.95 * size, 0.30 * size, 0.17 * size
    with mb.at(c, rot=yaw):
        mb.sphere((0, 0, 0), r0 * 1.08, mat, seg=8, rings=6)
        for pitch, az in ((0.0, 0.0), (109.47, 0.0), (109.47, 120.0), (109.47, 240.0)):
            with mb.at((0, 0, 0), rot=az, rot_y=pitch):
                mb.lathe([(r0, 0.0), (r1, L)], mat, seg=7, cap_top=True, cap_bottom=False)


def _life_ring(mb, pos, yaw, mat="M_LifeboatOrange"):
    """Life ring hanging vertically, facing local -Y rotated by yaw."""
    with mb.at(pos, rot=yaw, rot_x=90):
        mb.torus((0, 0, 0), 0.32, 0.07, mat, seg=14, tube_seg=6)


class _Shifted(AssetSet):
    """AssetSet view that offsets every socket position (pairs with `mb.at(offset)` for geometry)."""

    def __init__(self, base, off):
        self.base, self.off = base, off
        self.name, self.meshes, self.sockets = base.name, base.meshes, base.sockets

    def socket(self, type, pos, yaw=0.0, **props):
        z = pos[2] if len(pos) > 2 else 0.0
        self.base.socket(type, (pos[0] + self.off[0], pos[1] + self.off[1], z + self.off[2]), yaw, **props)


def _bw_path():
    for p in C.PATHS:
        if p["id"] == "breakwater":
            return [(x - HARBOR_POS[0], y - HARBOR_POS[1]) for x, y in p["pts"]]
    return [(120.0, -5.0), (235.0, -147.0)]


def _poly_len(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def _poly_at(pts, s):
    """Point and heading (radians) at arc length s along a 2D polyline."""
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if s <= acc + L or i == len(pts) - 2:
            t = (s - acc) / L if L > 0 else 0.0
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), math.atan2(b[1] - a[1], b[0] - a[0])
        acc += L
    return pts[-1], 0.0


def _vertex_s(pts):
    out, acc = [0.0], 0.0
    for a, b in zip(pts, pts[1:]):
        acc += math.hypot(b[0] - a[0], b[1] - a[1])
        out.append(acc)
    return out


# ================================================================== QUAY
def _quay(aset, mb, nc):
    # wall body: wet dark concrete below the splash zone, harbor concrete above
    mb.box_mm((QX0, QY, WALL_BOT), (QX1, QY + 3.0, -2.2), DCONC, skip=("+y", "-z"))
    mb.box_mm((QX0, QY, -2.2), (QX1, QY + 3.0, -0.55), CONC, skip=("+y", "-z", "+z"))
    # coping beam (edge strip), slightly proud of the paving
    mb.box_mm((QX0 - 0.35, COPE_Y0, -0.55), (QX1 + 0.35, QY + 1.4, COPE_TOP), CONC, skip=("-z",))
    # horizontal joint line / shadow groove under the coping nose
    mb.box_mm((QX0, QY - 0.06, -0.85), (QX1, QY, -0.72), WCONC, skip=("+y",))

    bw_gap = _bw_quay_gap()
    pier_gap = (PIER_X - PIER_HW - 0.6, PIER_X + PIER_HW + 0.6)
    gang_gap = (GANG_X - 1.5, GANG_X + 1.5)

    # mooring bollards every 15 m (props) + kerb (wheel guard) segments between them
    bollards = []
    for k in range(32):
        x = -232.5 + 15.0 * k
        if _near(x, [pier_gap, gang_gap, bw_gap], 1.5) or _near(x, [(l, l) for l in LADDERS], 1.6):
            continue
        bollards.append(x)
        aset.prop("SM_Bollard", (x, QY - 0.05, COPE_TOP), 0.0)
    gaps = [pier_gap, gang_gap, bw_gap] + [(l - 0.8, l + 0.8) for l in LADDERS] + \
           [(b - 0.55, b + 0.55) for b in bollards]
    for a, b in _gap_runs(QX0 + 0.3, QX1 - 0.3, gaps):
        mb.box_mm((a, KERB[0], COPE_TOP), (b, KERB[1], 0.24), CONC, mats={"+z": MARK}, skip=("-z",))
        # black/yellow end caps make the kerb ends readable
        for x in (a, b):
            mb.box_mm((x - 0.02, KERB[0] - 0.01, COPE_TOP), (x + 0.02, KERB[1] + 0.01, 0.245), "M_Black")

    # D-fenders on the sea face
    for k in range(32):
        x = -225.0 + 15.0 * k
        if x > QX1 - 2.0 or _near(x, [pier_gap, bw_gap], 3.0) or _near(x, [(l, l) for l in LADDERS], 2.0):
            continue
        mb.box_mm((x - 0.32, QY - 0.5, -4.3), (x + 0.32, QY, -0.75), RUB, skip=("+y",))
        mb.box_mm((x - 0.4, QY - 0.08, -0.9), (x + 0.4, QY, -0.6), DMETAL, skip=("+y",))

    # big floating (Yokohama type) fenders at the ferry berth
    for x in YOKOHAMA:
        yc, zc = QY - 1.45, -2.45
        with mb.at((x, yc, zc), rot_y=90):
            mb.lathe([(0.25, -2.0), (0.75, -1.86), (1.05, -1.55), (1.2, -1.1), (1.2, 1.1), (1.05, 1.55),
                      (0.75, 1.86), (0.25, 2.0)], RUB, seg=14)
        for sx in (-1, 1):
            mb.beam((x + sx * 2.0, yc, zc), (x + sx * 2.4, QY - 0.2, -0.3), 0.07, 0.07, DMETAL)
            mb.box_mm((x + sx * 2.4 - 0.12, QY - 0.4, -0.45), (x + sx * 2.4 + 0.12, QY, -0.25), DMETAL)

    # ladders down to the water
    for x in LADDERS:
        _ladder(mb, x)

    # cleats on the coping
    for x in (22.0, 40.0, 70.0, 98.0, PIER_X - 6.0, PIER_X + 6.0, 125.0, 190.0, -60.0, -205.0):
        _cleat(mb, x, QY + 0.75)


def _bw_quay_gap():
    """x interval where the breakwater cap crosses the quay edge."""
    pts = _bw_path()
    L = _poly_len(pts)
    xs = []
    s = 0.0
    while s < L:
        (x, y), _ = _poly_at(pts, s)
        if abs(y - QY) < 3.0:
            xs.append(x)
        s += 0.5
    if not xs:
        return (1e9, 1e9)
    return (min(xs) - 6.0, max(xs) + 6.0)


def _ladder(mb, x):
    y = COPE_Y0 - 0.07
    for sx in (-0.24, 0.24):
        mb.box_mm((x + sx - 0.035, y - 0.04, -4.6), (x + sx + 0.035, y + 0.04, COPE_TOP), METAL)
    z = -4.4
    while z < -0.2:
        mb.box((x, y, z), (0.48, 0.035, 0.035), METAL)
        z += 0.3
    for z in (-3.6, -2.0, -0.4):            # stand-off brackets to the wall face
        mb.box_mm((x - 0.3, QY - 0.1, z - 0.04), (x + 0.3, y + 0.04, z + 0.04), METAL)
    # grab hoops above the coping
    for sx in (-0.3, 0.3):
        p0 = (x + sx, y, COPE_TOP)
        p1 = (x + sx, y, 1.0)
        p2 = (x + sx, QY + 0.6, 1.0)
        p3 = (x + sx, QY + 0.6, COPE_TOP)
        mb.beam(p0, p1, 0.06, 0.06, YELLOW)
        mb.beam(p1, p2, 0.06, 0.06, YELLOW)
        mb.beam(p2, p3, 0.06, 0.06, YELLOW)


def _cleat(mb, x, y):
    z = COPE_TOP
    mb.box_mm((x - 0.32, y - 0.13, z), (x + 0.32, y + 0.13, z + 0.06), DMETAL)
    for sx in (-0.14, 0.14):
        mb.box((x + sx, y, z + 0.14), (0.1, 0.1, 0.16), DMETAL)
    mb.box((x, y, z + 0.26), (0.85, 0.12, 0.09), DMETAL)


def _markings(mb):
    """Painted quay markings (1.5 cm proud of the terrain paving)."""
    z0, z1 = 0.0, 0.015
    W, Y = "M_CourtLine", MARK
    lane = (-37.0, 8.0)                     # service lane centre y / width, x -30 .. 130
    lx0, lx1 = -30.0, 130.0
    zebra = (GANG_X - 3.0, GANG_X + 3.0)
    for yy in (lane[0] - lane[1] / 2, lane[0] + lane[1] / 2):
        for a, b in _gap_runs(lx0, lx1, [zebra]):
            mb.box_mm((a, yy - 0.08, z0), (b, yy + 0.08, z1), W)
    x = lx0 + 1.0
    while x < lx1 - 3.0:
        if not _near(x, [zebra], 3.2):
            mb.box_mm((x, lane[0] - 0.07, z0), (x + 3.0, lane[0] + 0.07, z1), W)
        x += 6.0
    x = zebra[0] + 0.25
    while x < zebra[1]:
        mb.box_mm((x, lane[0] - lane[1] / 2 + 0.4, z0), (x + 0.5, lane[0] + lane[1] / 2 - 0.4, z1), W)
        x += 1.0
    # dashed yellow guide lines gangway -> terminal canopy
    for xx in (GANG_X - 2.6, GANG_X + 2.6):
        y = QY + 5.0
        while y < 2.0:
            if not (lane[0] - lane[1] / 2 - 0.5 < y < lane[0] + lane[1] / 2 + 0.5):
                mb.box_mm((xx - 0.08, y, z0), (xx + 0.08, y + 1.5, z1), Y)
            y += 2.5
    # crane safety lines
    for yy in (RAIL_SEA + 1.2, RAIL_LAND + 1.2, RAIL_LAND - 1.2):
        mb.box_mm((-112.0, yy - 0.08, z0), (-38.0, yy + 0.08, z1), Y)


# ================================================================== GANGWAY (static, part of the quay)
def _gangway(aset, mb, nc):
    x = GANG_X
    ship_side = FERRY_POS[1] + F_HW              # -54.8
    y0, y1 = QY + 0.4, ship_side - 1.0              # quay end -> 1 m over the main deck
    z0, z1 = 0.1, FERRY_POS[2] + F_DECK + 0.06     # 1.06
    w = 2.2
    # landing plate on the quay
    mb.box_mm((x - 1.35, y0, 0.0), (x + 1.35, QY + 4.5, 0.1), DMETAL, skip=("-z",))
    # walking deck + side stringers
    mb.ramp((x, y0, z0), (x, y1, z1), w, METAL, thick=0.12)
    for sx in (-1, 1):
        mb.beam((x + sx * (w / 2 + 0.06), y0, z0 - 0.1), (x + sx * (w / 2 + 0.06), y1, z1 - 0.1), 0.12, 0.45, TRIM)
    # anti-slip cleats across the deck
    n = 9
    for i in range(1, n):
        t = i / n
        mb.box((x, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t + 0.015), (w - 0.1, 0.06, 0.03), DMETAL)
    # roller end on the ship deck
    with mb.at((x, y1 + 0.15, z1 - 0.02), rot_y=90):
        mb.cylinder((0, 0, -w / 2), 0.16, w, DMETAL, seg=10)
    # hand rails
    for sx in (-1, 1):
        rx = x + sx * (w / 2 + 0.06)
        mb.railing([(rx, y0, z0), (rx, y1 + 0.2, z1)], 1.1, TRIM, post_spacing=1.3)
    # entry portal with signs
    for sx in (-1, 1):
        mb.box((x + sx * 1.6, QY + 4.2, 1.6), (0.18, 0.18, 3.2), BLUE)
    mb.box((x, QY + 4.2, 3.05), (3.6, 0.16, 0.7), BLUE)
    mb.box((x, QY + 4.2, 3.45), (3.7, 0.22, 0.08), YELLOW)
    mb.box((x, QY + 4.2, 2.66), (3.7, 0.22, 0.08), YELLOW)
    aset.text("FERRY BOARDING", (x, QY + 4.2 + 0.11, 3.05), 180.0, size=0.34, color=(1, 1, 1))
    aset.text("WELCOME TO DUEL ACADEMY!", (x, QY + 4.2 - 0.11, 3.05), 0.0, size=0.26, color=(1, 1, 1))
    aset.light((x, QY + 3.6, 2.9), (1.0, 0.9, 0.7), 3000.0, 10.0, night_only=True)
    nc.box((x, QY + 4.2, 2.62), (1.8, 0.12, 0.05), GLOW)


# ================================================================== PIER
def _pier(aset, mb, nc):
    x0, x1 = PIER_X - PIER_HW, PIER_X + PIER_HW
    ys = COPE_Y0
    tx0, tx1, ty0, ty1 = THEAD
    # deck planks (across the pier), T-head planks are longer
    y = ys
    pw, gap = 0.28, 0.035
    while y - pw > ty0:
        a, b = (tx0, tx1) if y - pw < ty1 else (x0, x1)
        mb.box_mm((a, y - pw, -0.07), (b, y, 0.0), PWOOD)
        y -= pw + gap
    # fascia boards
    mb.box_mm((x0 - 0.08, ty1, -0.42), (x0, ys, 0.0), PWOOD)
    mb.box_mm((x1, ty1, -0.42), (x1 + 0.08, ys, 0.0), PWOOD)
    mb.box_mm((tx0 - 0.08, ty0 - 0.08, -0.42), (tx1 + 0.08, ty0, 0.0), PWOOD)
    mb.box_mm((tx0 - 0.08, ty0, -0.42), (tx0, ty1, 0.0), PWOOD)
    mb.box_mm((tx1, ty0, -0.42), (tx1 + 0.08, ty1, 0.0), PWOOD)
    mb.box_mm((tx0 - 0.08, ty1, -0.42), (x0, ty1 + 0.08, 0.0), PWOOD)
    mb.box_mm((x1, ty1, -0.42), (tx1 + 0.08, ty1 + 0.08, 0.0), PWOOD)
    # stringers
    for k in range(6):
        sx = x0 + 0.3 + k * (2 * PIER_HW - 0.6) / 5
        mb.box_mm((sx - 0.08, ty1, -0.37), (sx + 0.08, ys, -0.07), "M_DarkWood", skip=("+z",))
    for k in range(9):
        sx = tx0 + 0.3 + k * (tx1 - tx0 - 0.6) / 8
        mb.box_mm((sx - 0.08, ty0, -0.37), (sx + 0.08, ty1, -0.07), "M_DarkWood", skip=("+z",))
    # pile bents
    bents = []
    yb = ys - 2.0
    while yb > ty1 + 1.0:
        bents.append((yb, [x0 + 0.4, PIER_X, x1 - 0.4]))
        yb -= 4.0
    for yb in (ty1 - 0.5, (ty0 + ty1) / 2, ty0 + 0.5):
        bents.append((yb, [tx0 + 0.4, PIER_X - 3.0, PIER_X, PIER_X + 3.0, tx1 - 0.4]))
    for i, (yb, xs) in enumerate(bents):
        mb.box_mm((xs[0] - 0.35, yb - 0.2, -0.8), (xs[-1] + 0.35, yb + 0.2, -0.37), "M_DarkWood")
        for px in xs:
            mb.cylinder((px, yb, BED), 0.2, -0.8 - BED, "M_DarkWood", seg=8, cap_bottom=False, cap_top=False)
            # tide band: dark green-black growth at the waterline
            mb.cylinder((px, yb, WATER - 0.6), 0.215, 0.9, "M_RottenWood", seg=8, cap_bottom=False, cap_top=False)
        if i % 2 == 0 and len(xs) == 3:
            mb.beam((xs[0], yb, -1.0), (xs[-1], yb, -3.8), 0.12, 0.2, "M_DarkWood")
            mb.beam((xs[-1], yb, -1.0), (xs[0], yb, -3.8), 0.12, 0.2, "M_DarkWood")
    # railings (gap on the T-head south side for the landing stairs, open towards the quay)
    rz = 0.0
    mb.railing([(x0 + 0.08, ys - 0.3, rz), (x0 + 0.08, ty1 + 0.08, rz)], 1.05, PWOOD, post_spacing=2.0,
               post_size=0.12, rail_size=0.09)
    mb.railing([(x1 - 0.08, ys - 0.3, rz), (x1 - 0.08, ty1 + 0.08, rz)], 1.05, PWOOD, post_spacing=2.0,
               post_size=0.12, rail_size=0.09)
    mb.railing([(x0, ty1 - 0.08, rz), (tx0 + 0.08, ty1 - 0.08, rz), (tx0 + 0.08, ty0 + 0.08, rz),
                (PIER_X - 1.25, ty0 + 0.08, rz)], 1.05, PWOOD, post_spacing=2.0, post_size=0.12, rail_size=0.09)
    mb.railing([(x1, ty1 - 0.08, rz), (tx1 - 0.08, ty1 - 0.08, rz), (tx1 - 0.08, ty0 + 0.08, rz),
                (PIER_X + 1.25, ty0 + 0.08, rz)], 1.05, PWOOD, post_spacing=2.0, post_size=0.12, rail_size=0.09)
    # stairs down to the boat landing (z -2.2) south of the T-head
    land_z = -2.2
    steps = 9
    rise = (0.0 - land_z) / steps
    run = 0.3
    sy0 = ty0 - steps * run
    mb.stairs((PIER_X, sy0, land_z), 90.0, 2.2, steps, rise, run, PWOOD)
    for sx in (-1, 1):
        mb.railing([(PIER_X + sx * 1.15, sy0, land_z), (PIER_X + sx * 1.15, ty0, 0.0)], 1.0, PWOOD,
                   post_spacing=1.4, post_size=0.1, rail_size=0.08)
    lx0, lx1, ly0, ly1 = PIER_X - 4.0, PIER_X + 4.0, sy0 - 3.2, sy0
    mb.box_mm((lx0, ly0, land_z - 0.3), (lx1, ly1, land_z), PWOOD)
    for px in (lx0 + 0.3, lx1 - 0.3):
        for py in (ly0 + 0.3, ly1 - 0.3):
            mb.cylinder((px, py, BED), 0.18, land_z - 0.3 - BED + 1.2, "M_DarkWood", seg=8, cap_bottom=False)
    mb.railing([(lx0 + 0.1, ly0 + 0.1, land_z), (lx1 - 0.1, ly0 + 0.1, land_z)], 1.0, PWOOD,
               post_spacing=2.0, post_size=0.1, rail_size=0.08)
    for px in (lx0 + 0.4, lx1 - 0.4):
        mb.box((px, ly1 - 1.6, land_z + 0.15), (0.25, 0.25, 0.3), DMETAL)     # mooring posts
    aset.prop("SM_Rowboat", (lx0 - 2.2, (ly0 + ly1) / 2, WATER), 90.0)
    aset.prop("SM_Rowboat", (lx1 + 2.2, (ly0 + ly1) / 2 + 0.6, WATER), 95.0)
    # shelter on the T-head
    sx0, sx1, sy_0, sy_1 = PIER_X - 2.6, PIER_X + 2.6, -108.6, -103.4
    for px in (sx0, sx1):
        for py in (sy_0, sy_1):
            mb.box((px, py, 1.45), (0.2, 0.2, 2.9), TRIM)
    for py in (sy_0, sy_1):
        mb.box((PIER_X, py, 2.8), (5.4, 0.16, 0.2), TRIM)
    for px in (sx0, sx1):
        mb.box((px, (sy_0 + sy_1) / 2, 2.8), (0.16, 5.4, 0.2), TRIM)
    mb.hip_roof((PIER_X, (sy_0 + sy_1) / 2, 2.9), 5.6, 5.6, 1.5, ROOF_BLUE, overhang=0.5, thick=0.18)
    mb.box((PIER_X, sy_1 - 0.05, 1.15), (5.0, 0.08, 1.6), PWOOD)                      # back screen
    aset.prop("SM_Bench", (PIER_X, sy_1 - 0.9, 0.0), 0.0)
    aset.light((PIER_X, (sy_0 + sy_1) / 2, 2.6), (1.0, 0.85, 0.6), 2500.0, 9.0, night_only=True)
    nc.box((PIER_X, (sy_0 + sy_1) / 2, 2.66), (0.6, 0.6, 0.06), GLOW)
    # life rings
    _life_ring(mb, (x0 + 0.02, -70.0, 0.75), 90.0)
    _life_ring(mb, (x1 - 0.02, -90.0, 0.75), -90.0)
    _life_ring(mb, (tx0 + 0.02, -106.0, 0.75), 90.0)
    # lamps along the pier and on the T-head corners
    for i, y in enumerate((-58.0, -70.0, -82.0, -94.0)):
        aset.prop("SM_LampPost", (x0 + 0.45 if i % 2 == 0 else x1 - 0.45, y, 0.0), 0.0)
    aset.prop("SM_LampPost", (tx0 + 0.5, ty0 + 0.5, 0.0), 0.0)
    aset.prop("SM_LampPost", (tx1 - 0.5, ty0 + 0.5, 0.0), 0.0)
    # entrance sign
    mb.sign_board((PIER_X - 3.6, QY + 2.2, 2.2), 1.6, 0.6, PWOOD, "M_DarkWood")
    aset.text("PIER 1", (PIER_X - 3.6, QY + 2.2 + 0.09, 2.2), 180.0, size=0.32, color=(1, 1, 1))
    aset.interact("sign", (PIER_X - 3.6, QY + 3.0, 1.0), 180.0, title="Fishing Pier",
                  text="Fishing is allowed after classes. Please take your trash - and your cards - home with you.")


# ================================================================== FERRY (own origin: centre / waterline)
_F_LEVELS = [(-3.2, 0.36), (-2.95, 0.62), (-2.5, 0.8), (-1.8, 0.9), (-0.9, 0.95), (0.0, 0.97),
             (0.9, 0.985), (1.85, 0.995), (2.05, 0.997), (2.6, 1.0), (3.25, 1.0), (F_DECK, 1.0)]
_F_XN = [-35.0, -34.7, -34.2, -33.4, -32.2, -30.0, -26.0, -22.0, -18.0, -14.0, -10.0, -6.0, -2.0, 2.0,
         6.0, 10.0, 12.5, 15.0, 17.5, 20.0, 22.5, 25.0, 27.0, 29.0, 30.5, 32.0, 33.2, 34.1, 34.6, 35.0]


def _f_plan(xn):
    if xn < -32.0:
        t = (xn + 35.0) / 3.0
        return F_HW * (0.82 + 0.18 * (1.0 - (1.0 - t) ** 2))
    if xn <= 10.0:
        return F_HW
    t = min((xn - 10.0) / 25.0, 1.0)
    return max(F_HW * max(0.0, 1.0 - t ** 2.3) ** 0.7, 0.05)


def _f_xmap(xn, z):
    xb = 35.0 - (F_DECK - z) * 0.45
    xs = -35.0 + max(0.0, -z) * 0.55
    return xs + (xn + 35.0) / 70.0 * (xb - xs)


def _f_sheer(x):
    return F_DECK + (max(0.0, x - 12.0) / 23.0) ** 2 * 1.3


def _f_factor(z):
    L = _F_LEVELS
    if z <= L[0][0]:
        return L[0][1]
    for (z0, f0), (z1, f1) in zip(L, L[1:]):
        if z <= z1:
            return f0 + (f1 - f0) * (z - z0) / (z1 - z0)
    return 1.0


def _hull_mat(zc):
    if zc < 0.0:
        return BOTTOM
    if 1.85 <= zc <= 2.05 or 2.6 <= zc <= 3.25:
        return STRIPE
    return HULL


def _ferry(mb):
    nl, ns = len(_F_LEVELS), len(_F_XN)

    def V(i, j, s):
        xn = _F_XN[i]
        z, f = _F_LEVELS[j]
        x = _f_xmap(xn, z)
        if j == nl - 1:
            z = _f_sheer(x)
        return (x, s * _f_plan(xn) * f, z)

    # ---------------------------------------------------------------- hull shell
    for i in range(ns - 1):
        for j in range(nl - 1):
            for s in (-1, 1):
                a, b, c, d = V(i, j, s), V(i + 1, j, s), V(i + 1, j + 1, s), V(i, j + 1, s)
                m = _hull_mat((a[2] + c[2]) / 2)
                if s < 0:
                    mb.quad(a, b, c, d, m, smooth=True)
                else:
                    mb.quad(a, d, c, b, m, smooth=True)
        # keel
        mb.quad(V(i, 0, -1), V(i, 0, 1), V(i + 1, 0, 1), V(i + 1, 0, -1), BOTTOM)
        # main deck
        mb.quad(V(i, nl - 1, -1), V(i + 1, nl - 1, -1), V(i + 1, nl - 1, 1), V(i, nl - 1, 1), DECK)
    for j in range(nl - 1):
        a, b, c, d = V(0, j, -1), V(0, j + 1, -1), V(0, j + 1, 1), V(0, j, 1)
        mb.quad(a, b, c, d, _hull_mat((a[2] + b[2]) / 2))                       # transom
        a, b, c, d = V(ns - 1, j, 1), V(ns - 1, j + 1, 1), V(ns - 1, j + 1, -1), V(ns - 1, j, -1)
        mb.quad(a, b, c, d, _hull_mat((a[2] + b[2]) / 2))                       # stem
    # forecastle bulwark (raised bow)
    bi = [i for i in range(ns) if _F_XN[i] >= 17.5]
    bh = 1.1
    for s in (-1, 1):
        for i0, i1 in zip(bi, bi[1:]):
            p0, p1 = V(i0, nl - 1, s), V(i1, nl - 1, s)
            o0 = (p0[0], p0[1] + s * 0.04, p0[2] + bh)
            o1 = (p1[0], p1[1] + s * 0.04, p1[2] + bh)
            w0 = max(_f_plan(_F_XN[i0]) - 0.16, 0.0)
            w1 = max(_f_plan(_F_XN[i1]) - 0.16, 0.0)
            q0, q1 = (p0[0], s * w0, p0[2]), (p1[0], s * w1, p1[2])
            r0, r1 = (q0[0], q0[1], q0[2] + bh), (q1[0], q1[1], q1[2] + bh)
            if s < 0:
                mb.quad(p0, p1, o1, o0, HULL)
                mb.quad(q1, q0, r0, r1, HULL)
                mb.quad(o0, o1, r1, r0, TRIM)
            else:
                mb.quad(p0, o0, o1, p1, HULL)
                mb.quad(q0, q1, r1, r0, HULL)
                mb.quad(r0, r1, o1, o0, TRIM)
        p = V(bi[0], nl - 1, s)
        w0 = _f_plan(_F_XN[bi[0]]) - 0.16
        a, b = (p[0], s * w0, p[2]), (p[0], p[1] + s * 0.04, p[2])
        pts = [a, b, (b[0], b[1], b[2] + bh), (a[0], a[1], a[2] + bh)]
        mb.poly(pts if s < 0 else list(reversed(pts)), HULL)

    # portholes along the hull (above the blue stripes)
    for s in (-1, 1):
        x = -30.0
        while x <= 16.0:
            hw = _f_plan(x) * _f_factor(1.3)
            with mb.at((x, s * hw, 1.3), rot_x=90):
                mb.cylinder((0, 0, -0.06), 0.22, 0.12, GLASS, seg=10, smooth=False)
            x += 2.4
    # anchors / hawse plates at the bow
    for s in (-1, 1):
        xa = 30.0
        hw = _f_plan(xa) * _f_factor(3.0)
        slope = (_f_plan(xa + 0.5) - _f_plan(xa - 0.5))
        ang = math.degrees(math.atan2(s * slope, 1.0))
        with mb.at((xa, s * hw, 3.0), rot=ang):
            mb.box((0, 0, 0), (1.4, 0.3, 1.0), DMETAL)
            mb.box((0, s * 0.12, -0.75), (0.5, 0.25, 0.6), DMETAL)

    # ---------------------------------------------------------------- superstructure
    d1 = _rounded_rect(-24.0, 10.5, 5.6, 3.8)
    mb.prism(d1, 3.95, 7.0, HULL, cap_top=False, cap_bottom=False)
    for s in (-1, 1):
        for xa, xb, n in ((-22.5, -6.8, 6), (-3.2, 9.6, 5)):
            p0, p1 = ((xa, -5.6), (xb, -5.6)) if s < 0 else ((xb, 5.6), (xa, 5.6))
            mb.facade_windows(p0, p1, [4.95], n, 1.5, 1.25, glass=GLASS, frame=TRIM)
        # side door at the gangway
        mb.box((GANG_SHIP_X, s * 5.62, 5.15), (1.3, 0.06, 2.3), TRIM)
        mb.box((GANG_SHIP_X, s * 5.66, 5.1), (1.1, 0.06, 2.1), STRIPE)
        mb.box((GANG_SHIP_X, s * 5.7, 5.5), (0.6, 0.04, 0.6), GLASS)
    arc1 = [p for p in d1 if p[0] > 10.4]
    _band(mb, arc1, 5.0, 6.15, GLASS)
    _band(mb, [(-24.0, -5.6), (10.5, -5.6)], 6.6, 6.8, STRIPE, off=0.02)
    _band(mb, [(10.5, 5.6), (-24.0, 5.6)], 6.6, 6.8, STRIPE, off=0.02)
    # aft wall of deck 1: double doors
    mb.box((-24.04, 0.0, 5.1), (0.06, 2.2, 2.3), TRIM)
    mb.box((-24.07, 0.0, 5.05), (0.06, 1.9, 2.1), GLASS)

    # deck 2 slab (overhangs the side walkways)
    d2s = _rounded_rect(-27.0, 12.0, 7.0, 4.5)
    mb.prism(d2s, 7.0, 7.3, HULL, top_mat=DECK)
    # deck 2 cabin with ribbon windows
    d2 = _rounded_rect(-15.0, 9.5, 5.6, 3.5)
    mb.prism(d2, 7.3, 10.0, HULL, cap_top=False, cap_bottom=False)
    _band(mb, d2, 8.0, 9.25, GLASS)
    for s in (-1, 1):
        x = -13.6
        while x < 9.0:
            mb.box((x, s * 5.66, 8.62), (0.12, 0.1, 1.3), TRIM)
            x += 1.7
    mb.box((-15.04, 0.0, 8.4), (0.06, 2.2, 2.2), TRIM)
    mb.box((-15.07, 0.0, 8.35), (0.06, 1.9, 2.0), GLASS)

    # deck 3 slab + bridge
    d3s = _rounded_rect(-16.0, 9.0, 6.2, 4.0)
    mb.prism(d3s, 10.0, 10.3, HULL, top_mat=DECK)
    br = _rounded_rect(4.0, 10.0, 6.0, 2.6)
    mb.prism(br, 10.3, 13.0, HULL, cap_top=False, cap_bottom=False)
    _band(mb, [(6.5, -6.0), (10.0, -6.0)] + [p for p in br if p[0] > 10.0] + [(10.0, 6.0), (6.5, 6.0)],
          11.3, 12.65, GLASS)
    for p in [p for p in br if p[0] > 10.0]:
        a = math.atan2(p[1] / 6.0, (p[0] - 10.0) / 2.6)
        mb.box((p[0] + 0.03 * math.cos(a), p[1] + 0.03 * math.sin(a), 11.97), (0.1, 0.1, 1.35), TRIM)
    mb.prism(_rounded_rect(3.7, 10.0, 6.35, 2.95), 13.0, 13.25, HULL)               # bridge roof
    mb.prism(_rounded_rect(9.8, 10.0, 6.4, 3.4)[1:-1], 12.72, 12.82, TRIM)            # sun visor
    for s in (-1, 1):                                                                  # bridge wings
        mb.box_mm((7.2, 6.2, 10.0) if s > 0 else (7.2, -7.7, 10.0),
                  (10.6, 7.7, 10.3) if s > 0 else (10.6, -6.2, 10.3), HULL, mats={"+z": DECK})
        yo = s * 7.62
        mb.railing([(7.25, s * 6.25, 10.3), (7.25, yo, 10.3), (10.55, yo, 10.3), (10.55, s * 6.25, 10.3)],
                   1.05, TRIM, post_spacing=1.2, post_size=0.06, rail_size=0.05)
    mb.box((4.0 - 0.04, 0.0, 11.4), (0.06, 1.1, 2.1), STRIPE)                          # bridge aft door

    # funnel (blue, gold band, black top), raked aft
    with mb.at((-7.0, 0.0, 10.3), rot_y=-9.0):
        bands = [(0.0, 3.3, STRIPE), (3.3, 3.95, "M_Gold"), (3.95, 4.9, STRIPE), (4.9, 5.6, "M_Black")]
        for z0, z1, m in bands:
            r0, r1 = 1.0 - 0.012 * z0, 1.0 - 0.012 * z1
            mb.lathe([(r0, z0), (r1, z1)], m, seg=20, cap_top=(m == "M_Black"), cap_bottom=False,
                     sx=2.4, sy=1.45)
        mb.lathe([(0.75, 5.0), (0.75, 5.75)], "M_Black", seg=10, sx=1.6, sy=1.0)      # exhaust pipes
    # mast + radar on the bridge roof
    mb.cylinder((7.2, 0.0, 13.25), 0.14, 5.4, TRIM, seg=8, radius_top=0.09)
    mb.box((7.2, 0.0, 15.05), (1.4, 1.2, 0.12), TRIM)
    mb.box((7.2, 0.0, 15.55), (0.2, 0.2, 0.5), DMETAL)
    mb.box((7.2, 0.0, 15.85), (0.35, 2.8, 0.22), DMETAL)
    mb.box((7.2, 0.0, 17.3), (0.12, 3.4, 0.12), TRIM)
    mb.sphere((7.2, 0.0, 18.75), 0.16, GLOW, seg=8, rings=6)
    for s in (-1, 1):
        mb.box((7.2, s * 1.6, 17.42), (0.15, 0.15, 0.15), "M_AcademyRed" if s > 0 else "M_HelipadLight")

    # lifeboats in davits on the boat deck
    for xb in (-12.0, -2.8):
        for s in (-1, 1):
            yb = s * 7.25
            with mb.at((xb, yb, 10.45)):
                with mb.at((0, 0, 0), rot_x=180):
                    mb.sphere((0, 0, 0), 1.0, "M_LifeboatOrange", seg=16, rings=8, hemi=True,
                              scale=(3.0, 1.05, 0.85))
                mb.sphere((0, 0, 0), 1.0, "M_LifeboatOrange", seg=16, rings=8, hemi=True,
                          scale=(2.75, 0.97, 1.0))
                ell = [(3.0 * math.cos(TAU * k / 20), 1.05 * math.sin(TAU * k / 20)) for k in range(21)]
                _band(mb, ell, -0.12, 0.08, TRIM, off=0.03)
                for wx in (-1.5, -0.5, 0.5, 1.5):
                    t = 1.0 - (wx / 2.75) ** 2 - 0.45 ** 2
                    wy = 0.97 * math.sqrt(max(t, 0.0))
                    mb.box((wx, s * wy, 0.45), (0.5, 0.12, 0.28), GLASS)
            for dx in (-2.3, 2.3):
                mb.beam((xb + dx, s * 5.9, 10.3), (xb + dx, s * 5.9, 12.0), 0.16, 0.16, TRIM)
                mb.beam((xb + dx, s * 5.9, 12.0), (xb + dx, yb, 11.7), 0.14, 0.14, TRIM)
                mb.beam((xb + dx, yb, 11.7), (xb + dx, yb, 11.35), 0.04, 0.04, DMETAL)

    # windlass / mooring gear on the foredeck
    for s in (-1, 1):
        zd = _f_sheer(26.0)
        with mb.at((26.0, s * 1.6, zd + 0.55), rot_x=90):
            mb.cylinder((0, 0, -0.5), 0.45, 1.0, DMETAL, seg=12)
        mb.box((26.0, s * 1.6, zd + 0.2), (1.4, 1.4, 0.4), STRIPE)
        for xm in (20.5, -32.5):
            z = _f_sheer(xm)
            mb.cylinder((xm, s * 5.4, z), 0.2, 0.6, DMETAL, seg=8)
            mb.cylinder((xm + 0.6, s * 5.4, z), 0.2, 0.6, DMETAL, seg=8)
    mb.cylinder((34.4, 0.0, _f_sheer(34.4) + bh), 0.05, 2.6, TRIM, seg=6)            # jack staff
    mb.cylinder((-34.3, 0.0, F_DECK), 0.06, 4.0, TRIM, seg=6)                         # stern staff
    mb.box((-34.95, 0.0, F_DECK + 3.4), (1.3, 0.03, 0.85), STRIPE)                    # stern flag

    # benches on the open aft part of deck 2
    for s in (-1, 1):
        mb.box((-21.0, s * 4.6, 7.55), (3.0, 0.5, 0.5), DECK)
        mb.box((-21.0, s * 4.9, 8.0), (3.0, 0.1, 0.6), DECK)

    # ---------------------------------------------------------------- stairs
    st1 = 14
    run = 0.28
    mb.stairs((-27.0 - st1 * run, 0.0, F_DECK), 0.0, 1.6, st1, (7.3 - F_DECK) / st1, run, HULL)
    st2 = 12
    mb.stairs((-16.0 - st2 * run, 0.0, 7.3), 0.0, 1.6, st2, (10.3 - 7.3) / st2, run, HULL)
    for s in (-1, 1):
        mb.railing([(-27.0 - st1 * run, s * 0.86, F_DECK), (-27.0, s * 0.86, 7.3)], 1.0, TRIM,
                   post_spacing=1.3, post_size=0.06, rail_size=0.05)
        mb.railing([(-16.0 - st2 * run, s * 0.86, 7.3), (-16.0, s * 0.86, 10.3)], 1.0, TRIM,
                   post_spacing=1.3, post_size=0.06, rail_size=0.05)

    # ---------------------------------------------------------------- railings
    rk = dict(post_spacing=1.6, post_size=0.06, rail_size=0.05)
    for s in (-1, 1):
        xs = [x for x in _F_XN if -34.7 <= x <= 17.5]
        if s > 0:
            xs = sorted(set(xs + [GANG_SHIP_X - 1.3, GANG_SHIP_X + 1.3]))
        pts = [(x, s * (_f_plan(x) - 0.12), _f_sheer(x)) for x in xs]
        if s > 0:
            runs = [[p for p in pts if p[0] <= GANG_SHIP_X - 1.3], [p for p in pts if p[0] >= GANG_SHIP_X + 1.3]]
        else:
            runs = [pts]
        for r in runs:
            mb.railing(r, 1.1, TRIM, **rk)
    hs = _f_plan(-34.7) - 0.12
    mb.railing([(-34.75, -hs, F_DECK), (-34.75, hs, F_DECK)], 1.1, TRIM, **rk)
    # deck 2 edge
    e2 = _offset_pts([(p[0], p[1]) for p in d2s] + [d2s[0]], 0.1)
    e2 = [(x, y) for x, y in e2]
    left = [(-26.9, -0.9), (-26.9, -6.9)] + [p for p in e2[1:-2]] + [(-26.9, 6.9), (-26.9, 0.9)]
    mb.railing([(x, y, 7.3) for x, y in left], 1.05, TRIM, **rk)
    # deck 3 edge (aft + sides up to the bridge)
    for s in (-1, 1):
        mb.railing([(-15.9, s * 0.9, 10.3), (-15.9, s * 6.1, 10.3), (3.9, s * 6.1, 10.3)], 1.05, TRIM, **rk)
    # life rings on the deck 2 rail
    for s in (-1, 1):
        _life_ring(mb, (-24.0, s * 6.95, 7.95), 0.0 if s < 0 else 180.0)
        _life_ring(mb, (2.0, s * 6.95, 7.95), 0.0 if s < 0 else 180.0)


# ================================================================== WAREHOUSES
def _warehouse(aset, mb, nc, cx, cy, number, dock):
    w, d, H, rh = 40.0, 20.0, 9.0, 3.0
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2
    mb.box_mm((x0 - 0.12, y0 - 0.12, -0.3), (x1 + 0.12, y1 + 0.12, 0.7), WCONC, skip=("-z",))
    mb.box_mm((x0, y0, 0.7), (x1, y1, H), "M_WarehouseWall", skip=("-z", "+z"))
    mb.gable_roof((cx, cy, H), w, d, rh, "M_WarehouseRoof", overhang=0.7, thick=0.3, gable_mat="M_WarehouseWall")
    # ridge cap + vents
    mb.box((cx, cy, H + rh + 0.02), (w + 1.4, 0.6, 0.12), TRIM)
    for vx in (-12.0, 0.0, 12.0):
        mb.cylinder((cx + vx, cy, H + rh - 0.2), 0.55, 0.9, METAL, seg=10)
        mb.cone((cx + vx, cy, H + rh + 0.7), 0.8, 0.45, METAL, seg=10)
    # white corner trims, metal pilasters, eave fascia
    for px in (x0, x1):
        for py in (y0, y1):
            mb.box((px, py, (0.7 + H) / 2), (0.55, 0.55, H - 0.7), TRIM)
    for k in range(1, 8):           # pilasters on the back (the quay side carries doors + number)
        mb.box((x0 + k * 5.0, y1 + 0.1, (0.7 + H) / 2), (0.3, 0.2, H - 0.7), METAL)
    # clerestory windows (north) and gable windows
    mb.facade_windows((x1, y1), (x0, y1), [H - 2.3], 8, 2.2, 1.1, glass=GLASS, frame=TRIM)
    for gx, s in ((x0, -1), (x1, 1)):
        p0, p1 = ((gx, y1), (gx, y0)) if s < 0 else ((gx, y0), (gx, y1))
        mb.facade_windows(p0, p1, [H - 1.6], 3, 1.6, 1.0, glass=GLASS, frame=TRIM)
    # downspouts
    for px in (x0 + 0.5, x1 - 0.5):
        for py, s in ((y0, -1), (y1, 1)):
            mb.box((px, py + s * 0.25, H / 2), (0.18, 0.18, H), DMETAL)

    door_mat = "M_CrateRed" if number == "01" else "M_CrateBlue"
    if not dock:
        # two big sliding doors on the quay side
        for dx in (-9.0, 9.0):
            xc = cx + dx
            mb.box_mm((xc - 3.4, y0 - 0.36, 0.0), (xc + 3.4, y0 - 0.12, 6.6), door_mat)
            for zz in (1.7, 3.3, 4.9):
                mb.box((xc, y0 - 0.39, zz), (6.6, 0.06, 0.12), DMETAL)
            mb.box((xc, y0 - 0.39, 3.3), (0.12, 0.06, 6.4), DMETAL)
            mb.beam((xc - 3.2, y0 - 0.39, 0.3), (xc + 3.2, y0 - 0.39, 6.3), 0.05, 0.14, TRIM)
            mb.box_mm((xc - 7.2, y0 - 0.5, 6.6), (xc + 7.2, y0 - 0.1, 7.0), DMETAL)      # track
            mb.box_mm((xc - 3.6, y0 - 0.45, 0.0), (xc + 3.6, y0 - 0.1, 0.06), DMETAL)    # floor guide
            aset.light((xc, y0 - 1.2, 7.4), (1.0, 0.92, 0.75), 6000.0, 18.0, night_only=True)
            mb.box((xc, y0 - 0.45, 7.35), (0.7, 0.5, 0.3), DMETAL)
            nc.box((xc, y0 - 0.45, 7.18), (0.55, 0.38, 0.04), GLOW)
        # personnel door between them
        mb.box_mm((cx - 0.65, y0 - 0.1, 0.0), (cx + 0.65, y0 - 0.02, 2.35), TRIM)
        mb.box_mm((cx - 0.55, y0 - 0.14, 0.0), (cx + 0.55, y0 - 0.08, 2.25), door_mat)
        mb.box_mm((cx - 1.0, y0 - 1.0, 2.6), (cx + 1.0, y0, 2.75), TRIM)
        aset.text(number, (cx, y0 - 0.05, 6.7), 0.0, size=3.6, color=(0.97, 0.97, 0.97))
    else:
        # raised loading dock with three roll-up doors and a canopy
        dz = 1.2
        dx0, dx1, dy0 = cx - 14.0, cx + 14.0, y0 - 3.6
        mb.box_mm((dx0, dy0, -0.2), (dx1, y0, dz), WCONC, skip=("-z",))
        mb.box_mm((dx0, dy0 - 0.06, dz - 0.08), (dx1, dy0 + 0.06, dz + 0.01), DMETAL)
        for bx in range(5):
            xb = dx0 + 2.0 + bx * 6.0
            mb.box_mm((xb - 0.3, dy0 - 0.25, 0.35), (xb + 0.3, dy0, 1.0), RUB)
        # stairs (west) and ramp (east)
        nst = 5
        mb.stairs((dx0 - nst * 0.3, dy0 + 1.4, 0.0), 0.0, 2.4, nst, dz / nst, 0.3, WCONC)
        mb.railing([(dx0 - nst * 0.3, dy0 + 0.25, 0.0), (dx0, dy0 + 0.25, dz)], 1.0, YELLOW,
                   post_spacing=0.8, post_size=0.06, rail_size=0.05)
        _wedge(mb, (dx1 + 10.0, (dy0 + y0) / 2, 0.0), 180.0, 10.0, y0 - dy0, 0.0, dz, WCONC, zb=-0.2)
        for k in range(3):
            xc = cx - 9.0 + k * 9.0
            mb.box_mm((xc - 2.25, y0 - 0.16, dz), (xc + 2.25, y0 - 0.02, dz + 4.3), TRIM)
            mb.box_mm((xc - 2.0, y0 - 0.22, dz), (xc + 2.0, y0 - 0.12, dz + 4.0), METAL)
            z = dz + 0.35
            while z < dz + 4.0:
                mb.box((xc, y0 - 0.24, z), (4.0, 0.04, 0.05), DMETAL)
                z += 0.38
            mb.box((xc, y0 - 0.35, dz + 4.35), (4.6, 0.5, 0.5), DMETAL)
            aset.light((xc, y0 - 2.0, 5.8), (1.0, 0.92, 0.75), 4000.0, 12.0, night_only=True)
            nc.box((xc, y0 - 2.0, 5.88), (1.2, 0.4, 0.04), GLOW)
        mb.box_mm((dx0 - 0.5, dy0 - 0.6, 6.0), (dx1 + 0.5, y0, 6.3), "M_WarehouseRoof")
        mb.box_mm((dx0 - 0.5, dy0 - 0.7, 5.9), (dx1 + 0.5, dy0 - 0.5, 6.4), TRIM)
        for k in range(6):
            xb = dx0 + 0.5 + k * (dx1 - dx0 - 1.0) / 5
            mb.beam((xb, y0, 4.2), (xb, dy0 - 0.3, 6.0), 0.14, 0.14, DMETAL)
        aset.text(number, (cx, y0 - 0.05, 7.65), 0.0, size=2.4, color=(0.97, 0.97, 0.97))
    # big number on the outer gable end too
    if cx < -80:
        aset.text(number, (x0 - 0.05, cy, 5.2), -90.0, size=3.2, color=(0.97, 0.97, 0.97))
    else:
        aset.text(number, (x1 + 0.05, cy, 5.2), 90.0, size=3.2, color=(0.97, 0.97, 0.97))


def _warehouses(aset, mb, nc):
    _warehouse(aset, mb, nc, -100.0, 32.0, "01", dock=False)
    _warehouse(aset, mb, nc, -55.0, 32.0, "02", dock=True)


# ================================================================== GANTRY CRANE
def _crane(aset, mb, nc):
    x = CRANE_X
    Y = CRANE_Y
    for ry in (RAIL_SEA, RAIL_LAND):
        mb.box_mm((-112.0, ry - 0.09, -0.05), (-38.0, ry + 0.09, 0.05), METAL, skip=("-z",))
        mb.box_mm((-112.0, ry - 0.35, -0.05), (-38.0, ry + 0.35, 0.02), DCONC, skip=("-z",))
    top = 12.0
    for lx in (x - 6.0, x + 6.0):
        for ly in (RAIL_SEA, RAIL_LAND):
            mb.box_mm((lx - 1.8, ly - 0.55, 0.05), (lx + 1.8, ly + 0.55, 1.1), DMETAL)
            for wx in (-1.2, 1.2):
                with mb.at((lx + wx, ly, 0.42), rot_x=90):
                    mb.cylinder((0, 0, -0.6), 0.38, 1.2, "M_Black", seg=10)
            mb.box_mm((lx - 1.9, ly - 0.6, 1.1), (lx + 1.9, ly + 0.6, 1.7), Y)
            mb.box_mm((lx - 0.5, ly - 0.5, 1.7), (lx + 0.5, ly + 0.5, top), Y)
        mb.box_mm((lx - 0.4, RAIL_SEA, 6.2), (lx + 0.4, RAIL_LAND, 6.9), Y)               # portal tie
        mid = (RAIL_SEA + RAIL_LAND) / 2
        mb.beam((lx, RAIL_SEA + 0.4, 6.9), (lx, mid, top - 0.6), 0.3, 0.3, Y)
        mb.beam((lx, RAIL_LAND - 0.4, 6.9), (lx, mid, top - 0.6), 0.3, 0.3, Y)
    for ly in (RAIL_SEA, RAIL_LAND):
        mb.box_mm((x - 6.6, ly - 0.6, top - 1.0), (x + 6.6, ly + 0.6, top), Y)
        for s in (-1, 1):
            mb.beam((x + s * 5.6, ly, top - 3.0), (x + s * 3.0, ly, top - 1.0), 0.3, 0.3, Y)
    # boom girders over the water + back reach
    by0, by1 = -74.0, -27.0
    for gx in (x - 2.6, x + 2.6):
        mb.box_mm((gx - 0.45, by0, top), (gx + 0.45, by1, top + 1.4), Y)
        mb.box_mm((gx - 0.5, by0, top + 1.4), (gx + 0.5, by1, top + 1.5), METAL)
    yb = by0 + 1.0
    while yb < by1:
        mb.box_mm((x - 2.2, yb - 0.2, top + 1.0), (x + 2.2, yb + 0.2, top + 1.4), Y)
        yb += 6.0
    # A-frame and stays
    ay, az = -43.0, 21.0
    for gx in (x - 2.6, x + 2.6):
        mb.beam((gx, RAIL_SEA, top + 1.4), (gx, ay, az), 0.55, 0.55, Y)
        mb.beam((gx, RAIL_LAND, top + 1.4), (gx, ay, az), 0.55, 0.55, Y)
        mb.beam((gx, ay, az), (gx, by0 + 2.0, top + 1.4), 0.2, 0.2, METAL)
        mb.beam((gx, ay, az), (gx, by1 + 1.0, top + 1.4), 0.2, 0.2, METAL)
    mb.box_mm((x - 3.2, ay - 0.5, az - 0.4), (x + 3.2, ay + 0.5, az + 0.4), Y)
    mb.sphere((x, ay, az + 0.6), 0.25, "M_AcademyRed", seg=8, rings=6)
    aset.light((x, ay, az + 0.9), (1.0, 0.15, 0.1), 2000.0, 8.0, night_only=True)
    # machinery house on the back reach
    mb.box_mm((x - 3.3, -33.5, top + 1.5), (x + 3.3, by1 + 0.3, top + 4.3), WHITE)
    mb.box_mm((x - 3.5, -33.7, top + 4.3), (x + 3.5, by1 + 0.5, top + 4.5), BLUE)
    mb.facade_windows((x - 3.3, -33.5), (x + 3.3, -33.5), [top + 2.6], 3, 1.2, 0.8, glass=GLASS, frame=TRIM)
    # trolley, operator cab, ropes and spreader with a container
    ty = -45.0
    mb.box_mm((x - 3.3, ty - 1.6, top - 0.5), (x + 3.3, ty + 1.6, top), DMETAL)
    mb.box_mm((x + 0.9, ty - 1.2, top - 3.0), (x + 3.0, ty + 1.2, top - 0.5), WHITE)
    mb.box_mm((x + 0.85, ty - 1.25, top - 2.4), (x + 3.05, ty - 1.15, top - 1.0), GLASS)
    mb.box_mm((x + 0.8, ty - 1.25, top - 3.1), (x + 3.1, ty + 1.25, top - 3.0), BLUE)
    sz = 6.6
    mb.box_mm((x - 3.1, ty - 1.25, sz), (x + 3.1, ty + 1.25, sz + 0.4), Y)
    mb.box_mm((x - 1.0, ty - 0.6, sz + 0.4), (x + 1.0, ty + 0.6, sz + 0.9), Y)
    for rx in (-0.7, 0.7):
        for ryy in (-0.4, 0.4):
            nc.beam((x + rx, ty + ryy, sz + 0.9), (x + rx * 1.2, ty + ryy, top - 0.5), 0.05, 0.05, DMETAL)
    aset.prop("SM_Container_Yellow", (x, ty, sz - 2.62), 0.0)
    aset.light((x, ty, top - 0.6), (1.0, 0.95, 0.85), 8000.0, 25.0, night_only=True)


# ================================================================== TERMINAL
def _terminal(aset, mb, nc):
    hx0, hx1, hy0, hy1, hh = 22.0, 38.0, 12.0, 24.0, 5.0
    tx0, tx1, ty0, ty1, th = 38.0, 46.0, 13.0, 23.0, 9.0
    # hall
    mb.box_mm((hx0, hy0, 0.0), (hx1, hy1, hh), WHITE, skip=("-z", "+z"))
    mb.box_mm((hx0 - 0.08, hy0 - 0.08, 0.0), (hx1 + 0.08, hy1 + 0.08, 0.45), CONC, skip=("-z",))
    mb.box_mm((hx0 - 0.12, hy0 - 0.12, hh - 0.45), (hx1, hy1 + 0.12, hh), BLUE)
    mb.hip_roof(((hx0 + hx1) / 2, (hy0 + hy1) / 2, hh), hx1 - hx0, hy1 - hy0, 1.8, ROOF_BLUE, overhang=0.7)
    mb.facade_windows((hx0, hy0), (28.6, hy0), [1.0], 2, 1.8, 2.0, glass=GLASS, frame=TRIM)
    mb.facade_windows((31.4, hy0), (hx1, hy0), [1.0], 2, 1.8, 2.0, glass=GLASS, frame=TRIM)
    mb.facade_windows((hx1, hy1), (31.4, hy1), [1.0], 2, 1.8, 2.0, glass=GLASS, frame=TRIM)
    mb.facade_windows((28.6, hy1), (hx0, hy1), [1.0], 2, 1.8, 2.0, glass=GLASS, frame=TRIM)
    mb.facade_windows((hx0, hy1), (hx0, hy0), [1.0], 3, 1.8, 2.0, glass=GLASS, frame=TRIM)
    for yy, s in ((hy0, -1), (hy1, 1)):
        mb.box((30.0, yy + s * 0.06, 1.35), (2.8, 0.1, 2.7), BLUE)                       # door frame
        mb.box((29.4, yy + s * 0.1, 1.3), (1.12, 0.06, 2.55), GLASS)
        mb.box((30.6, yy + s * 0.1, 1.3), (1.12, 0.06, 2.55), GLASS)
        mb.box((30.0, yy + s * 0.13, 1.3), (0.06, 0.04, 2.55), TRIM)
    # harbor-master tower with a wrap-around control room
    mb.box_mm((tx0, ty0, 0.0), (tx1, ty1, th), WHITE, skip=("-z", "+z"))
    mb.box_mm((tx0, ty0 - 0.08, 0.0), (tx1 + 0.08, ty1 + 0.08, 0.45), CONC, skip=("-z",))
    mb.box_mm((tx0 - 0.1, ty0 - 0.1, 5.6), (tx1 + 0.1, ty1 + 0.1, 6.0), BLUE)
    mb.box_mm((tx0 - 0.12, ty0 - 0.12, th - 0.4), (tx1 + 0.12, ty1 + 0.12, th), BLUE)
    loop = [(tx0, ty0), (tx1, ty0), (tx1, ty1), (tx0, ty1), (tx0, ty0)]
    _band(mb, loop, 6.25, 8.35, GLASS)
    for (ax, ay), (bx, by) in zip(loop, loop[1:]):
        L = math.hypot(bx - ax, by - ay)
        n = int(L / 1.6)
        for k in range(n + 1):
            t = k / n
            px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            nx, ny = (by - ay) / L, -(bx - ax) / L
            mb.box((px + nx * 0.05, py + ny * 0.05, 7.3), (0.1, 0.1, 2.1), TRIM)
    mb.hip_roof(((tx0 + tx1) / 2, (ty0 + ty1) / 2, th), tx1 - tx0, ty1 - ty0, 1.6, ROOF_BLUE, overhang=0.6)
    mb.cylinder((44.5, 21.5, th + 1.0), 0.06, 3.5, METAL, seg=6)                        # antenna
    mb.facade_windows((tx1, ty0), (tx1, ty1), [1.2], 3, 1.4, 1.6, glass=GLASS, frame=TRIM)
    mb.facade_windows((tx1, ty1), (tx0, ty1), [1.2], 2, 1.4, 1.6, glass=GLASS, frame=TRIM)
    # ticket window (south face of the tower)
    mb.box_mm((40.9, ty0 - 0.06, 0.95), (43.1, ty0, 2.35), TRIM)
    mb.box_mm((41.0, ty0 - 0.09, 1.05), (43.0, ty0 - 0.05, 2.25), GLASS)
    mb.box_mm((40.8, ty0 - 0.5, 0.95), (43.2, ty0, 1.05), TRIM)
    mb.box_mm((40.6, ty0 - 0.9, 2.5), (43.4, ty0, 2.62), BLUE)
    aset.text("TICKETS", (42.0, ty0 - 0.03, 2.95), 0.0, size=0.3, color=(0.10, 0.25, 0.62))
    aset.light((42.0, ty0 - 0.6, 2.4), (1.0, 0.9, 0.7), 2000.0, 5.0, night_only=True)
    aset.text("HARBOR OFFICE", (42.0, ty0 - 0.03, 4.75), 0.0, size=0.42, color=(0.10, 0.25, 0.62))
    # waiting canopy
    cz = 3.4
    mb.box_mm((19.5, 3.8, cz), (hx1, hy0, cz + 0.25), WHITE)
    mb.box_mm((hx1, 3.8, cz), (46.5, ty0, cz + 0.25), WHITE)
    mb.box_mm((19.4, 3.7, cz - 0.05), (46.6, 3.9, cz + 0.35), BLUE)
    mb.box_mm((19.4, 3.7, cz - 0.05), (19.6, hy0, cz + 0.35), BLUE)
    mb.box_mm((46.4, 3.7, cz - 0.05), (46.6, ty0, cz + 0.35), BLUE)
    for px in (20.2, 26.6, 33.0, 39.4, 45.8):
        mb.cylinder((px, 4.3, 0.0), 0.13, cz, METAL, seg=10)
        mb.cylinder((px, 4.3, 0.0), 0.2, 0.3, BLUE, seg=10)
    for px in (23.4, 29.8, 36.2, 42.6):
        nc.box((px, 8.0, cz - 0.02), (2.4, 0.4, 0.04), GLOW)
        aset.light((px, 8.0, cz - 0.3), (1.0, 0.9, 0.72), 2500.0, 9.0, night_only=True)
    for bx in (23.0, 27.4, 33.0, 37.4):
        aset.prop("SM_Bench", (bx, 7.4, 0.0), 0.0)
    aset.prop("SM_VendingMachine", (44.8, ty0 - 0.55, 0.0), 0.0)
    aset.prop("SM_TrashBin", (39.6, ty0 - 0.5, 0.0), 0.0)
    aset.prop("SM_TrashBin", (20.6, 4.9, 0.0), 0.0)
    # rooftop "DUEL ACADEMY HARBOR" sign, readable from the sea and from the island
    sy, szc, sw, shh = 18.0, 8.25, 14.0, 1.8
    for px in (24.5, 28.0, 32.0, 35.5):
        mb.box((px, sy, (4.9 + szc - shh / 2) / 2), (0.16, 0.16, szc - shh / 2 - 4.9), METAL)
    mb.box((30.0, sy, szc), (sw, 0.25, shh), BLUE)
    mb.box((30.0, sy, szc + shh / 2 + 0.06), (sw + 0.25, 0.32, 0.12), YELLOW)
    mb.box((30.0, sy, szc - shh / 2 - 0.06), (sw + 0.25, 0.32, 0.12), YELLOW)
    for s in (-1, 1):
        mb.box((30.0 + s * (sw / 2 + 0.06), sy, szc), (0.12, 0.32, shh + 0.24), YELLOW)
    aset.text("DUEL ACADEMY HARBOR", (30.0, sy - 0.125 - 0.03, szc), 0.0, size=1.0, color=(1, 1, 1))
    aset.text("DUEL ACADEMY HARBOR", (30.0, sy + 0.125 + 0.03, szc), 180.0, size=1.0, color=(1, 1, 1))
    for s in (-1, 1):
        aset.light((30.0, sy + s * 2.0, szc - 1.4), (1.0, 0.95, 0.85), 3000.0, 8.0, night_only=True)
    # timetable board (interact) + flagpoles
    mb.sign_board((17.6, 5.4, 1.7), 1.8, 1.2, BLUE, TRIM, thick=0.12)
    aset.text("FERRY TIMETABLE", (17.6, 5.4 - 0.06 - 0.025, 2.05), 0.0, size=0.15, color=(1, 1, 1))
    aset.text("MON  10:00  DOMINO CITY", (17.6, 5.4 - 0.06 - 0.025, 1.6), 0.0, size=0.1, color=(1.0, 0.85, 0.3))
    aset.interact("sign", (17.6, 4.6, 1.0), 0.0, title="Ferry Timetable",
                  text="The ferry from Domino City arrives every Monday. Welcome to Duel Academy!")
    for i, f in enumerate(("SM_Flagpole_Red", "SM_Flagpole_Yellow", "SM_Flagpole_Blue")):
        aset.prop(f, (10.0 + i * 2.6, 8.0, 0.0), 0.0)
    for px in (19.0, 47.2):
        aset.prop("SM_Planter", (px, 13.0, 0.0), 0.0)


# ================================================================== HELIPORT
def _heliport(aset, mb, nc):
    cx, cy = HELI
    h, top = HELI_HALF, HELI_TOP
    x0, x1, y0, y1 = cx - h, cx + h, cy - h, cy + h
    mb.box_mm((x0, y0, -0.4), (x1, y1, top), CONC, mats={"+z": DCONC}, skip=("-z",))
    rim = 0.35
    for a, b in (((x0 - 0.15, y0 - 0.15), (x1 + 0.15, y0 + rim)), ((x0 - 0.15, y1 - rim), (x1 + 0.15, y1 + 0.15)),
                 ((x0 - 0.15, y0 + rim), (x0 + rim, y1 - rim)), ((x1 - rim, y0 + rim), (x1 + 0.15, y1 - rim))):
        mb.box_mm((a[0], a[1], top - 0.2), (b[0], b[1], top + 0.04), WCONC)
    mz = top + 0.025
    # white perimeter line
    e, lw = 0.7, 0.4
    for a, b in (((x0 + e, y0 + e), (x1 - e, y0 + e + lw)), ((x0 + e, y1 - e - lw), (x1 - e, y1 - e)),
                 ((x0 + e, y0 + e), (x0 + e + lw, y1 - e)), ((x1 - e - lw, y0 + e), (x1 - e, y1 - e))):
        mb.box_mm((a[0], a[1], top), (b[0], b[1], mz), "M_CourtLine")
    # yellow circle
    n = 48
    ro, ri = 8.3, 7.5
    outer = [(cx + ro * math.cos(TAU * k / n), cy + ro * math.sin(TAU * k / n)) for k in range(n)]
    inner = [(cx + ri * math.cos(TAU * k / n), cy + ri * math.sin(TAU * k / n)) for k in range(n)]
    mb.slab_ring(outer, inner, top, mz, MARK)
    # "H"
    hw, hh, bw = 2.2, 3.2, 0.95
    mb.box_mm((cx - hw, cy - hh, top), (cx - hw + bw, cy + hh, mz), MARK)
    mb.box_mm((cx + hw - bw, cy - hh, top), (cx + hw, cy + hh, mz), MARK)
    mb.box_mm((cx - hw + bw, cy - bw / 2, top), (cx + hw - bw, cy + bw / 2, mz), MARK)
    # touchdown bar markings at the corners (aiming chevrons)
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = cx + sx * 9.6, cy + sy * 9.6
            mb.box_mm((px - 0.9, py - 0.15, top), (px + 0.9, py + 0.15, mz), "M_CourtLine")
            mb.box_mm((px - 0.15, py - 0.9, top), (px + 0.15, py + 0.9, mz), "M_CourtLine")
    # stairs (north, towards the heliport path) and cart ramp (east)
    steps = 4
    mb.stairs((cx, y1 + steps * 0.32, 0.0), -90.0, 5.0, steps, top / steps, 0.32, CONC)
    for sx in (-1, 1):
        mb.railing([(cx + sx * 2.6, y1 + steps * 0.32, 0.0), (cx + sx * 2.6, y1, top)], 1.0, YELLOW,
                   post_spacing=1.0, post_size=0.07, rail_size=0.06)
    _wedge(mb, (x1 + 8.0, cy, 0.0), 180.0, 8.0, 3.2, 0.02, top, CONC, zb=-0.3)
    # edge lights
    for k in range(4):
        t = -h + 0.45 + k * (2 * h - 0.9) / 3
        for px, py in ((cx + t, y0 + 0.4), (cx + t, y1 - 0.4), (x0 + 0.4, cy + t), (x1 - 0.4, cy + t)):
            mb.cylinder((px, py, top), 0.13, 0.12, DMETAL, seg=8)
            nc.sphere((px, py, top + 0.13), 0.1, "M_HelipadLight", seg=8, rings=4, hemi=True)
    for px, py in ((x0 + 0.4, y0 + 0.4), (x1 - 0.4, y0 + 0.4), (x0 + 0.4, y1 - 0.4), (x1 - 0.4, y1 - 0.4),
                   (cx, y0 + 0.4), (cx, y1 - 0.4), (x0 + 0.4, cy), (x1 - 0.4, cy)):
        aset.light((px, py, top + 0.4), (0.35, 1.0, 0.45), 2000.0, 5.0, night_only=True)
    # windsock (pole: collision; sock fabric: NoCol)
    wx, wy = x0 - 2.5, y0 - 1.5
    mb.cylinder((wx, wy, 0.0), 0.35, 0.3, WCONC, seg=10)
    for i in range(6):
        mb.cylinder((wx, wy, 0.3 + i * 1.0), 0.08, 1.0, "M_LighthouseRed" if i % 2 else TRIM, seg=8,
                    cap_bottom=False, cap_top=(i == 5))
    mb.torus((wx, wy, 6.15), 0.5, 0.04, DMETAL, seg=12, tube_seg=4)
    _windsock(nc, (wx, wy, 6.15), 35.0)
    # fire cabinet + sign
    mb.box((x1 + 1.2, y1 - 1.0, 0.75), (0.9, 0.45, 1.5), "M_AcademyRed")
    mb.box((x1 + 1.2, y1 - 1.0 - 0.24, 1.0), (0.5, 0.04, 0.3), TRIM)
    mb.sign_board((cx - 6.5, y1 + 3.2, 2.0), 2.6, 0.8, BLUE, TRIM)
    aset.text("HELIPORT", (cx - 6.5, y1 + 3.2 + 0.06 + 0.025, 2.0), 180.0, size=0.42, color=(1, 1, 1))
    aset.interact("sign", (cx - 6.5, y1 + 4.0, 1.0), 180.0, title="Heliport",
                  text="Visiting pros and VIP guests of the Chancellor land here. Keep clear of the pad!")
    aset.prop("SM_LampPost", (cx + 3.4, y1 + 2.0, 0.0), 0.0)
    aset.prop("SM_LampPost", (cx - 3.4, y1 + 2.0, 0.0), 0.0)


def _windsock(nc, pivot, yaw):
    """Tapered striped sock pointing along local +x from the pivot ring (double sided)."""
    with nc.at(pivot, rot=yaw, rot_y=90 - 8):
        L = 3.0
        bands = 5
        for b in range(bands):
            z0, z1 = L * b / bands, L * (b + 1) / bands
            r0, r1 = 0.5 - 0.28 * z0 / L, 0.5 - 0.28 * z1 / L
            m = "M_LifeboatOrange" if b % 2 == 0 else TRIM
            rows = []
            for r, z in ((r0, z0), (r1, z1)):
                rows.append([(math.cos(TAU * i / 12) * r, math.sin(TAU * i / 12) * r, z) for i in range(12)])
            nc.grid_faces(rows, m, smooth=True, closed_u=True)
            nc.grid_faces(rows, m, smooth=True, closed_u=True, flip=True)


# ================================================================== BREAKWATER
def _breakwater(aset, mb, nc):
    path = _bw_path()
    L = _poly_len(path)
    lhc = (LH_POS[0] - HARBOR_POS[0], LH_POS[1] - HARBOR_POS[1])
    # trim the end so both cap corners stay outside the lighthouse paving disc
    s_end = L
    while s_end > L - 10.0:
        (px, py), hd = _poly_at(path, s_end)
        nx, ny = -math.sin(hd), math.cos(hd)
        ok = all(math.hypot(px + sgn * 4.0 * nx - lhc[0], py + sgn * 4.0 * ny - lhc[1]) >= 14.75
                 for sgn in (-1, 1))
        if ok:
            break
        s_end -= 0.1
    # where the walkway leaves the quay
    s_edge = 0.0
    while s_edge < s_end:
        if _poly_at(path, s_edge)[0][1] < QY:
            break
        s_edge += 0.25
    ramp = 12.0
    ss = sorted(set([0.0, ramp, s_end] + [s for s in _vertex_s(path) if s < s_end] +
                    [k * 6.0 for k in range(int(s_end / 6.0) + 1)] + [s_edge]))
    ss = [s for s in ss if s <= s_end]
    pts = [_poly_at(path, s)[0] for s in ss]
    top = [0.02 + 1.03 * min(s / ramp, 1.0) for s in ss]
    _ribbon(mb, pts, -4.0, 4.0, -3.6, top, CONC, top_mat="M_Paving")

    def sub(s0, s1):
        idx = [i for i, s in enumerate(ss) if s0 - 1e-6 <= s <= s1 + 1e-6]
        return [pts[i] for i in idx], [top[i] for i in idx]

    # harbor-side kerb + railing (right), sea-side parapet (left, beyond the quay) / kerb + railing on the quay
    stair_s = 35.0
    p_r, t_r = sub(ramp, s_end)
    _ribbon(mb, p_r, -4.0, -3.55, [t - 0.01 for t in t_r], [t + 0.16 for t in t_r], CONC)
    p_q, t_q = sub(ramp, s_edge)
    _ribbon(mb, p_q, 3.55, 4.0, [t - 0.01 for t in t_q], [t + 0.16 for t in t_q], CONC)
    p_p, t_p = sub(s_edge, s_end)
    _ribbon(mb, p_p, 3.3, 4.0, [t - 0.01 for t in t_p], [t + 1.0 for t in t_p], CONC, top_mat=WCONC)
    _ribbon(mb, p_p, 3.2, 4.1, [t + 1.0 for t in t_p], [t + 1.12 for t in t_p], TRIM)

    def rail(o, s0, s1, z_add):
        p, t = sub(s0, s1)
        q = _offset_pts(p, o)
        return [(a[0], a[1], z + z_add) for a, z in zip(q, t)]

    rk = dict(post_spacing=2.0, post_size=0.08, rail_size=0.07)
    for s0, s1 in ((ramp, stair_s - 1.8), (stair_s + 1.8, s_end - 0.2)):
        r = _rail_ends(rail(-3.78, s0, s1, 0.16), path, s0, s1, -3.78,
                       top_fn=lambda s: 0.02 + 1.03 * min(s / ramp, 1.0) + 0.16)
        mb.railing(r, 1.05, BLUE, **rk)
    for s0, s1 in ((ramp, stair_s - 1.8), (stair_s + 1.8, s_edge)):
        r = _rail_ends(rail(3.78, s0, s1, 0.16), path, s0, s1, 3.78,
                       top_fn=lambda s: 0.02 + 1.03 * min(s / ramp, 1.0) + 0.16)
        mb.railing(r, 1.05, BLUE, **rk)
    # cross-over stairs on both sides (the walkway is 1 m above the quay paving there)
    (sp, hd) = _poly_at(path, stair_s)
    nx, ny = -math.sin(hd), math.cos(hd)
    for sgn in (-1, 1):
        n = 5
        o = 4.0 + n * 0.3
        org = (sp[0] + sgn * nx * o, sp[1] + sgn * ny * o, 0.0)
        yaw = math.degrees(math.atan2(-sgn * ny, -sgn * nx))
        mb.stairs(org, yaw, 3.0, n, 1.05 / n, 0.3, CONC)
    # lamps, benches, mooring rings
    for s in (s_edge + 12.0, s_edge + 45.0, s_edge + 78.0, s_end - 8.0):
        (px, py), hd = _poly_at(path, s)
        nx, ny = -math.sin(hd), math.cos(hd)
        aset.prop("SM_LampPost", (px - nx * 3.15, py - ny * 3.15, 1.05), math.degrees(hd))
    for s in (s_edge + 28.0, s_edge + 62.0, s_edge + 96.0):
        (px, py), hd = _poly_at(path, s)
        nx, ny = -math.sin(hd), math.cos(hd)
        aset.prop("SM_Bench", (px + nx * 2.6, py + ny * 2.6, 1.05), math.degrees(hd))
    for s in (s_edge + 20.0, s_edge + 70.0):
        (px, py), hd = _poly_at(path, s)
        nx, ny = -math.sin(hd), math.cos(hd)
        _life_ring(mb, (px - nx * 3.7, py - ny * 3.7, 1.05 + 0.75), math.degrees(hd))
    (px, py), hd = _poly_at(path, 3.0)
    nx, ny = -math.sin(hd), math.cos(hd)
    aset.prop("SM_Signpost", (px - nx * 5.5, py - ny * 5.5, 0.0), math.degrees(hd) + 90.0)
    # tetrapods armouring the sea side
    rnd = random.Random(1996)
    s = s_edge + 14.0
    row = 0
    while s < s_end - 2.0:
        (px, py), hd = _poly_at(path, s)
        nx, ny = -math.sin(hd), math.cos(hd)
        for off in ((5.9, 8.3) if row % 2 == 0 else (7.1, 9.6)):
            o = off + rnd.uniform(-0.3, 0.3)
            g = 1.0 - max(o - 4.5, 0.0) * 0.7
            size = rnd.uniform(2.1, 2.6)
            c = (px + nx * o + rnd.uniform(-0.4, 0.4), py + ny * o, g + 0.32 * size - 0.35)
            _tetrapod(mb, c, size, rnd.uniform(0, 120))
        s += 2.9
        row += 1
    return s_end


def _rail_ends(r, path, s0, s1, off, top_fn):
    """Make sure a railing polyline starts/ends exactly at s0/s1 (stations may be coarser)."""
    def at(s):
        (px, py), hd = _poly_at(path, s)
        nx, ny = -math.sin(hd), math.cos(hd)
        return (px + nx * off, py + ny * off, top_fn(s))
    a, b = at(s0), at(s1)
    out = [a] + [p for p in r if math.hypot(p[0] - a[0], p[1] - a[1]) > 0.3 and
                 math.hypot(p[0] - b[0], p[1] - b[1]) > 0.3] + [b]
    return out


# ================================================================== dressing / sockets
def _dressing(aset):
    # quay lamps (skip the crane rails zone, the gangway and the breakwater root)
    bw = _bw_quay_gap()
    for k in range(16):
        x = -225.0 + 30.0 * k
        if -114.0 <= x <= -36.0 or _near(x, [(GANG_X - 3, GANG_X + 3), bw], 1.0):
            continue
        aset.prop("SM_LampPost", (x, QY + 4.5, 0.0), 0.0)
    for x, y in ((-12.0, 34.0), (-28.0, 34.0), (15.0, 2.0), (66.0, 1.0)):
        aset.prop("SM_LampPost", (x, y, 0.0), 0.0)
    # container yard + cargo
    yard = [
        ("SM_Container_Red", (-118.0, -27.0, 0.0), 0.0), ("SM_Container_Blue", (-111.6, -27.0, 0.0), 0.0),
        ("SM_Container_Yellow", (-105.2, -27.0, 0.0), 0.0), ("SM_Container_Blue", (-118.0, -24.4, 0.0), 0.0),
        ("SM_Container_Red", (-111.6, -24.4, 0.0), 0.0), ("SM_Container_Red", (-118.0, -27.0, 2.6), 0.0),
        ("SM_Container_Yellow", (-111.6, -25.7, 2.6), 0.0), ("SM_Container_Blue", (-118.0, -24.4, 2.6), 0.0),
        ("SM_Container_Blue", (-118.0, -25.7, 5.2), 0.0),
        ("SM_Container_Yellow", (-58.0, -22.0, 0.0), 0.0), ("SM_Container_Red", (-51.6, -22.0, 0.0), 0.0),
        ("SM_Container_Blue", (-58.0, -19.4, 0.0), 0.0), ("SM_Container_Blue", (-54.8, -20.7, 2.6), 0.0),
        ("SM_Container_Red", (-90.0, 8.0, 0.0), 90.0), ("SM_Container_Yellow", (-86.8, 8.0, 0.0), 90.0),
        ("SM_Container_Red", (195.0, 20.0, 0.0), 15.0), ("SM_Container_Blue", (196.0, 13.0, 0.0), 8.0),
    ]
    for a, p, yw in yard:
        aset.prop(a, p, yw)
    rnd = random.Random(7)
    for cx, cy, n in ((-96.0, 18.0, 6), (-64.0, 15.5, 7), (-138.0, -44.0, 4), (190.0, 4.0, 4), (-30.0, -30.0, 5)):
        for i in range(n):
            px, py = cx + rnd.uniform(-2.5, 2.5), cy + rnd.uniform(-1.5, 1.5)
            if i % 3 == 2:
                aset.prop("SM_Barrel", (px, py, 0.0), rnd.uniform(0, 360))
            else:
                aset.prop("SM_Crate", (px, py, 0.0), rnd.uniform(-15, 15))
    aset.prop("SM_Crate", (-64.0, 15.5, 1.2), 10.0)
    aset.prop("SM_Crate", (-96.5, 18.2, 1.2), -8.0)
    # benches facing the sea along the east waterfront, trash bins, planters
    for x in (178.0, 196.0, 214.0):
        aset.prop("SM_Bench", (x, QY + 3.0, 0.0), 0.0)
    aset.prop("SM_TrashBin", (187.0, QY + 3.2, 0.0), 0.0)
    for x in (-34.0, -6.0):
        aset.prop("SM_Planter", (x, 46.0, 0.0), 0.0)
    # palms along the landward edge and around the terminal / promenade (keep road mouths clear)
    def on_road(x, y):
        if abs(x + 20.0) < 10.0 and y > 30.0:                  # main road from the academy
            return True
        if abs(x + 175.0) < 7.0 and y > 25.0:                  # heliport path
            return True
        dx, dy = x - 120.0, y - 45.0                           # gym / beach road (heads NE)
        t = max(0.0, dx * 0.864 + dy * 0.504)
        return math.hypot(dx - 0.864 * t, dy - 0.504 * t) < 10.0
    rp = random.Random(11)
    for k in range(26):
        x = -228.0 + 18.0 * k
        if on_road(x, 62.0):
            continue
        aset.prop("SM_PalmTree_A" if k % 3 else "SM_PalmTree_B", (x + rp.uniform(-2, 2), 62.0 + rp.uniform(-2, 2), 0.0),
                  rp.uniform(0, 360), scale=rp.uniform(0.85, 1.1))
    for p in ((22.0, 27.0), (26.0, 20.0), (61.0, 27.0), (60.0, 16.0), (112.0, 6.0), (130.0, 14.0),
              (172.0, -36.0), (200.0, -34.0), (226.0, -38.0), (-150.0, 40.0), (-196.0, 40.0)):
        aset.prop("SM_PalmTree_B" if p[0] % 2 else "SM_PalmTree_A", (p[0], p[1], 0.0), rp.uniform(0, 360))
    bushes = ("SM_FlowerBush_Red", "SM_FlowerBush_Yellow", "SM_FlowerBush_Blue", "SM_Bush_A", "SM_Bush_B")
    for i, p in enumerate(((31.0, 25.6), (34.5, 25.6), (45.5, 25.6), (49.0, 25.6), (57.6, 18.0), (57.6, 21.5),
                           (24.0, 25.0), (-168.0, 31.5), (-182.0, 31.5), (110.0, 2.0), (133.0, 11.0))):
        aset.prop(bushes[i % len(bushes)], (p[0], p[1], 0.0), rp.uniform(0, 360))
    # small boats moored along the east quay
    aset.prop("SM_Rowboat", (185.0, QY - 3.2, WATER), 2.0)
    aset.prop("SM_Rowboat", (214.0, QY - 3.4, WATER), -4.0)
    aset.prop("SM_Rowboat", (-200.0, QY - 3.3, WATER), 3.0)
    # fishing trawlers tied up along the quay
    aset.prop("SM_FishingBoat", (150.0, QY - 3.4, WATER), 180.0)
    aset.prop("SM_FishingBoat", (-170.0, QY - 3.5, WATER), 0.0)
    # arrival from the academy road: signpost + harbor map board
    aset.prop("SM_Signpost", (-9.0, 42.0, 0.0), 180.0)
    aset.interact("sign", (-30.0, 40.0, 1.0), 180.0, title="Duel Academy Harbor",
                  text="Ferry terminal to the east, warehouses and the heliport to the west. "
                       "Follow the breakwater to reach the lighthouse.")
    # buoys marking the channel
    for p in ((-150.0, -150.0), (-40.0, -135.0), (40.0, -160.0), (120.0, -185.0), (205.0, -200.0),
              (-90.0, -210.0), (150.0, -110.0)):
        aset.prop("SM_Buoy", (p[0], p[1], WATER), 0.0)
    # ferry night lights (static: the ferry only bobs 0.15 m)
    fx, fy, fz = FERRY_POS
    for dx, dz in ((-21.0, 7.3 + 2.6), (0.0, F_DECK + 2.6), (7.2, 18.9)):
        aset.light((fx + dx, fy + 6.0, fz + dz), (1.0, 0.9, 0.7), 2500.0, 12.0, night_only=True)
    # ambience
    for p in ((-150.0, -60.0, -2.0), (0.0, -62.0, -2.0), (150.0, -60.0, -2.0), (205.0, -110.0, 1.0)):
        aset.audio("A_Ocean", p, radius=60.0)
    # students
    aset.npc((41.0, 7.0, 0.0), 0.0, "slifer", wander=6.0)
    aset.npc((48.0, -44.0, 0.0), 180.0, "obelisk", wander=5.0)
    aset.npc((PIER_X, -96.0, 0.0), 0.0, "ra", wander=6.0)
    aset.npc((-160.0, 33.0, 0.0), 90.0, "obelisk", wander=5.0)
    aset.npc((-70.0, -5.0, 0.0), 0.0, "slifer", wander=10.0)
    aset.npc((200.0, -110.0, 1.05), -50.0, "ra", wander=8.0)
    aset.npc((15.0, 30.0, 0.0), 0.0, "ra", wander=10.0)


# ================================================================== HARBOR build
def build_harbor():
    aset = AssetSet("harbor")
    quay = aset.mesh("Harbor_Quay")
    nc = aset.mesh("Harbor_NoCol")
    _quay(aset, quay, nc)
    _gangway(aset, quay, nc)
    _markings(quay)
    _pier(aset, aset.mesh("Harbor_Pier"), nc)
    _ferry(aset.mesh("Harbor_Ferry"))
    aset.special("floating", FERRY_POS, 0.0, mesh="Harbor_Ferry", amplitude=0.15, period=6.0)
    _warehouses(aset, aset.mesh("Harbor_Warehouse"), nc)
    _crane(aset, aset.mesh("Harbor_Crane"), nc)
    term = aset.mesh("Harbor_Terminal")
    with term.at(TERM_OFF), nc.at(TERM_OFF):
        _terminal(_Shifted(aset, TERM_OFF), term, nc)
    _heliport(aset, aset.mesh("Harbor_Heliport"), nc)
    _breakwater(aset, aset.mesh("Harbor_Breakwater"), nc)
    _dressing(aset)
    return aset


# ================================================================== LIGHTHOUSE
LH_LAMP_Z = 20.45


def _lh_r(z):
    """Tower radius (tapered shaft)."""
    return 3.2 - (z - 0.95) * (1.05 / 16.6)


def build_lighthouse():
    aset = AssetSet("lighthouse")
    tw = aset.mesh("Lighthouse_Tower")
    pf = aset.mesh("Lighthouse_Platform")
    nc = aset.mesh("Lighthouse_NoCol")

    # where the breakwater arrives (lighthouse-local)
    path = _bw_path()
    lhc = (LH_POS[0] - HARBOR_POS[0], LH_POS[1] - HARBOR_POS[1])
    ex, ey = path[-1][0] - lhc[0], path[-1][1] - lhc[1]
    ent = math.degrees(math.atan2(ey, ex)) if math.hypot(ex, ey) > 1 else 111.0

    # ---------------------------------------------------------------- platform
    R = 14.6
    n = 64
    disc = [(R * math.cos(TAU * k / n), R * math.sin(TAU * k / n)) for k in range(n)]
    pf.prism(disc, -0.8, 0.06, CONC, cap_bottom=False, top_mat="M_Paving")
    ring_o = [(6.2 * math.cos(TAU * k / 48), 6.2 * math.sin(TAU * k / 48)) for k in range(48)]
    ring_i = [(5.6 * math.cos(TAU * k / 48), 5.6 * math.sin(TAU * k / 48)) for k in range(48)]
    pf.slab_ring(ring_o, ring_i, 0.06, 0.08, DCONC)
    gap = 19.0
    _arc_wall(pf, 14.0, 14.6, 0.06, 0.95, ent + gap, ent + 360.0 - gap, CONC, top_mat=TRIM)
    # tetrapods around the seaward edge
    rnd = random.Random(4)
    a = ent + 32.0
    k = 0
    while a < ent + 360.0 - 32.0:
        for r in ((16.6, 19.2) if k % 2 == 0 else (17.8, 20.4)):
            rr = r + rnd.uniform(-0.3, 0.3)
            g = -(rr - 15.0) * 0.7
            size = rnd.uniform(2.2, 2.7)
            ar = math.radians(a + rnd.uniform(-2, 2))
            _tetrapod(pf, (rr * math.cos(ar), rr * math.sin(ar), g + 0.32 * size - 0.3), size, rnd.uniform(0, 120))
        a += 8.5
        k += 1

    # ---------------------------------------------------------------- plinth + stairs (door faces north)
    octa = [(5.0 * math.cos(math.radians(22.5 + 45 * k)), 5.0 * math.sin(math.radians(22.5 + 45 * k)))
            for k in range(8)]
    tw.prism(octa, -0.3, 0.82, "M_OldStone", cap_bottom=False, cap_top=False)
    octa2 = [(p[0] * 1.035, p[1] * 1.035) for p in octa]
    tw.prism(octa2, 0.82, 0.95, CONC, cap_bottom=False)
    apo = 5.0 * math.cos(math.radians(22.5))
    nst = 4
    tw.stairs((0.0, apo + nst * 0.3, 0.06), -90.0, 2.6, nst, (0.95 - 0.06) / nst, 0.3, CONC)

    # ---------------------------------------------------------------- tower shaft with red bands
    tw.lathe([(3.5, 0.95), (_lh_r(1.5), 1.5)], LH_W, seg=36, cap_top=False, cap_bottom=False)
    bands = [(1.5, 6.0, LH_W), (6.0, 9.0, LH_R), (9.0, 12.0, LH_W), (12.0, 15.0, LH_R), (15.0, 17.55, LH_W)]
    for z0, z1, m in bands:
        tw.lathe([(_lh_r(z0), z0), (_lh_r(z1), z1)], m, seg=36, cap_top=False, cap_bottom=False)
    rt = _lh_r(17.55)
    tw.lathe([(rt, 17.55), (rt + 0.25, 17.8), (2.85, 18.2), (3.05, 18.35)], LH_R, seg=36,
             cap_top=False, cap_bottom=False)
    # corbels under the gallery
    for k in range(16):
        a = TAU * k / 16
        with tw.at((math.cos(a) * (rt + 0.2), math.sin(a) * (rt + 0.2), 17.6), rot=math.degrees(a)):
            tw.beam((0.0, 0, -0.6), (0.75, 0, 0.7), 0.18, 0.22, LH_R)
    # gallery deck + railing
    tw.cylinder((0, 0, 18.35), 3.2, 0.25, DMETAL, seg=36, smooth=False)
    for k in range(24):
        a = TAU * k / 24
        tw.box((math.cos(a) * 3.05, math.sin(a) * 3.05, 19.1), (0.07, 0.07, 1.0), DMETAL)
    tw.torus((0, 0, 19.6), 3.05, 0.05, DMETAL, seg=36, tube_seg=4)
    tw.torus((0, 0, 19.1), 3.05, 0.035, DMETAL, seg=36, tube_seg=4)
    # lantern room
    tw.cylinder((0, 0, 18.6), 1.8, 0.85, LH_R, seg=16, smooth=False, cap_bottom=False)
    tw.cylinder((0, 0, 19.45), 1.7, 2.1, "M_GlassClear", seg=16, smooth=False, cap_bottom=False, cap_top=False)
    for k in range(16):
        a = TAU * k / 16
        tw.box((math.cos(a) * 1.72, math.sin(a) * 1.72, 20.5), (0.08, 0.08, 2.1), DMETAL)
    tw.torus((0, 0, 20.5), 1.73, 0.03, DMETAL, seg=16, tube_seg=4)
    tw.cylinder((0, 0, 21.55), 2.0, 0.2, LH_R, seg=24, smooth=False)
    tw.lathe([(2.0, 21.75), (1.88, 21.98), (1.55, 22.45), (1.05, 22.88), (0.5, 23.12), (0.18, 23.2)], LH_R,
             seg=24, cap_bottom=False)
    tw.cylinder((0, 0, 23.15), 0.12, 0.2, LH_R, seg=8)
    tw.sphere((0, 0, 23.55), 0.33, LH_R, seg=12, rings=8)
    tw.cylinder((0, 0, 23.85), 0.035, 1.9, DMETAL, seg=6)
    tw.box((0.15, 0.0, 25.05), (0.9, 0.03, 0.12), DMETAL)                     # weathervane
    tw.cylinder((0, 0, 18.6), 0.3, 1.2, DMETAL, seg=10)                       # lamp pedestal
    # the lamp (Fresnel lens) - glow, no collision
    nc.lathe([(0.5, 19.8), (0.72, 20.05), (0.8, LH_LAMP_Z), (0.72, 20.85), (0.5, 21.1)], "M_LighthouseLamp",
             seg=16)

    # ---------------------------------------------------------------- door porch (north)
    tw.box_mm((-1.35, 2.3, 0.95), (1.35, 3.95, 3.9), LH_W)
    tw.gable_roof((0.0, 3.125, 3.9), 2.7, 1.65, 0.75, LH_R, overhang=0.2, thick=0.15, gable_mat=LH_W,
                  ridge_axis="y")
    tw.box_mm((-0.92, 3.95, 0.95), (0.92, 4.03, 3.5), TRIM)
    tw.box_mm((-0.75, 4.0, 0.95), (0.75, 4.08, 3.35), "M_DarkWood")
    tw.box_mm((-0.06, 4.06, 0.95), (0.06, 4.1, 3.35), "M_DarkMetal")
    tw.sphere((0.45, 4.12, 2.1), 0.05, "M_Gold", seg=6, rings=4)
    tw.box((0.0, 4.02, 3.62), (0.4, 0.12, 0.2), DMETAL)
    nc.box((0.0, 4.09, 3.55), (0.3, 0.04, 0.06), GLOW)
    aset.light((0.0, 4.6, 3.4), (1.0, 0.85, 0.6), 2000.0, 7.0, night_only=True)
    # small windows spiralling up
    for z, adeg in ((4.4, 150.0), (7.6, 300.0), (10.8, 90.0), (13.9, 225.0), (16.4, 20.0)):
        r = _lh_r(z)
        a = math.radians(adeg)
        with tw.at((math.cos(a) * (r - 0.1), math.sin(a) * (r - 0.1), z), rot=adeg + 90.0):
            tw.box((0, 0, 0), (0.95, 0.32, 1.25), TRIM)
            tw.box((0, -0.03, 0), (0.62, 0.32, 0.92), GLASS)

    # ---------------------------------------------------------------- keeper's hut
    hx0, hx1, hy0, hy1 = 6.0, 10.6, -0.4, 3.2
    pf.box_mm((hx0 - 0.1, hy0 - 0.1, 0.0), (hx1 + 0.1, hy1 + 0.1, 0.35), "M_OldStone", skip=("-z",))
    pf.box_mm((hx0, hy0, 0.35), (hx1, hy1, 2.75), LH_W, skip=("-z", "+z"))
    pf.gable_roof(((hx0 + hx1) / 2, (hy0 + hy1) / 2, 2.75), hx1 - hx0, hy1 - hy0, 1.2, LH_R, overhang=0.35,
                  thick=0.18, gable_mat=LH_W)
    pf.box_mm((hx1 - 1.4, hy0 + 0.8, 3.0), (hx1 - 0.8, hy0 + 1.4, 4.2), "M_OldStone")      # chimney
    pf.box_mm((7.5, hy1, 0.35), (8.6, hy1 + 0.08, 2.5), TRIM)
    pf.box_mm((7.6, hy1 + 0.04, 0.35), (8.5, hy1 + 0.1, 2.4), "M_DarkWood")
    pf.facade_windows((hx0, hy0), (hx1, hy0), [1.2], 2, 0.9, 0.9, glass=GLASS, frame=TRIM)
    pf.facade_windows((hx1, hy0), (hx1, hy1), [1.2], 1, 0.9, 0.9, glass=GLASS, frame=TRIM)
    pf.facade_windows((hx0, hy1), (hx0, hy0), [1.2], 1, 0.9, 0.9, glass=GLASS, frame=TRIM)
    aset.light((8.05, hy1 + 0.6, 2.6), (1.0, 0.85, 0.6), 2000.0, 6.0, night_only=True)
    nc.box((8.05, hy1 + 0.12, 2.65), (0.25, 0.08, 0.15), GLOW)
    # life ring stand
    pf.box((-9.5, -6.2, 0.75), (0.12, 0.12, 1.4), PWOOD)
    pf.box((-9.5, -6.2, 1.1), (0.8, 0.1, 0.8), TRIM)
    _life_ring(pf, (-9.5, -6.29, 1.1), 0.0)

    # ---------------------------------------------------------------- props + sockets
    aset.prop("SM_Bench", (0.0, -9.6, 0.06), 0.0)
    aset.prop("SM_Bench", (-7.6, -6.4, 0.06), -45.0)
    aset.prop("SM_Bench", (7.6, -6.4, 0.06), 45.0)
    for sgn in (-1, 1):
        a = math.radians(ent + sgn * (gap + 4.0))
        aset.prop("SM_LampPost", (13.2 * math.cos(a), 13.2 * math.sin(a), 0.06), 0.0)
    ea = math.radians(ent - 34.0)
    bx, by = 11.0 * math.cos(ea), 11.0 * math.sin(ea)
    face = ent                      # the board faces the visitor arriving from the breakwater
    byaw = face + 90.0              # local -Y (board front) -> direction `face`
    with pf.at((bx, by, 0.06), rot=byaw):
        pf.sign_board((0, 0, 1.3), 1.4, 0.7, "M_DarkWood", TRIM, thick=0.1)
    bn = (math.cos(math.radians(face)), math.sin(math.radians(face)))
    aset.text("LIGHTHOUSE", (bx + bn[0] * 0.08, by + bn[1] * 0.08, 1.36), byaw, size=0.24, color=(1, 1, 1))
    aset.interact("sign", (bx + bn[0] * 0.8, by + bn[1] * 0.8, 1.0), byaw, title="Lighthouse",
                  text="A quiet place to think. Some say the Kaiser comes here to watch the sea.")
    aset.special("lighthouse_beam", (0.0, 0.0, LH_LAMP_Z), 0.0, beam_length=600.0)
    aset.light((0.0, 0.0, LH_LAMP_Z), (1.0, 0.92, 0.65), 20000.0, 40.0, night_only=True)
    aset.audio("A_Ocean", (0.0, -12.0, 0.5), radius=60.0)
    aset.audio("A_Wind", (0.0, 0.0, 19.0), radius=25.0, volume=0.6)
    aset.npc((1.5, -11.5, 0.06), 180.0, "obelisk", wander=3.0)
    return aset


PLACEMENTS = {"harbor": build_harbor, "lighthouse": build_lighthouse}
