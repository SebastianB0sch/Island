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
from . import with_travel
from . import interior as K
from . import detail as DT
from .. import config as C
from .. import palette

palette.register({
    "M_WarehouseRoof": dict(kind="opaque", color=(0.30, 0.34, 0.39), rough=0.6, metallic=0.3,
                            detail="Corrugated", tiling=0.5),
    "M_LifeboatOrange": dict(kind="opaque", color=(0.98, 0.45, 0.08), rough=0.5, detail=None),
    "M_HelipadLight": dict(kind="emissive", color=(0.35, 1.00, 0.45), strength=8.0),
    "M_HarborHiVis": dict(kind="toon", color=(0.86, 1.00, 0.12), rough=0.8, fill=0.4),
    "M_HarborReflect": dict(kind="toon", color=(0.86, 0.88, 0.90), rough=0.2, metallic=0.6, fill=0.35),
    "M_HarborWrap": dict(kind="glass", color=(0.92, 0.95, 0.98), rough=0.1, opacity=0.25),
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

    def special(self, kind, pos, yaw=0.0, **props):
        t = props.get("target")
        if t is not None:      # preview cameras aim at a point given in the same (shifted) space
            props["target"] = (t[0] + self.off[0], t[1] + self.off[1], (t[2] if len(t) > 2 else 0.0) + self.off[2])
        self.socket(kind, pos, yaw, **props)


# ================================================================== interior helpers (walk-in buildings)
GLASS_IN = "M_IntGlassClear"
STEEL = "M_IntSteelBlue"
ORANGE = "M_LifeboatOrange"
WH_IN = "M_IntMetal"          # inside face of the warehouse cladding (light cel grey)
CARTONS = ("M_IntCork", "M_IntCork", "M_IntPaper", "M_IntPoster1", "M_IntPoster2", "M_IntPoster3", "M_IntCork")


def _slots(L, count, w):
    """Window centres along a facade (same spacing as MeshBuilder.facade_windows)."""
    margin = (L / count - w) / 2
    step = (L - 2 * margin) / count
    return [margin + step * (i + 0.5) for i in range(count)]


def _frames(mb, p0, p1, z, count, w, h, frame=TRIM, depth=0.06):
    """facade_windows() look (frame + sill on the outside face) WITHOUT the opaque glass panel - for windows
    that are cut through the wall. Returns the window centres (distance from p0)."""
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    yaw = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    us = _slots(L, count, w)
    fw = 0.1
    with mb.at((p0[0], p0[1], 0.0), rot=yaw):
        for u in us:
            mb.box((u - w / 2 - fw / 2, -depth, z + h / 2), (fw, depth * 2, h + 2 * fw), frame, skip=("+y",))
            mb.box((u + w / 2 + fw / 2, -depth, z + h / 2), (fw, depth * 2, h + 2 * fw), frame, skip=("+y",))
            mb.box((u, -depth, z + h + fw / 2), (w, depth * 2, fw), frame, skip=("+y",))
            mb.box((u, -depth * 2, z - fw / 2), (w + 0.3, depth * 4, fw), frame, skip=("+y",))
    return us


def _wins(us, w, z0, z1, frame=TRIM, mullions=0, glass=GLASS_IN, off=0.0):
    return [K.Window(u + off, w, z0, z1, glass=glass, frame=frame, mullions=mullions) for u in us]


def _tri_in(mb, x, y0, y1, z0, z1, mat, facing):
    """Inside face of a gable triangle (gable_roof only draws the outside one). facing = +1 (+x) / -1 (-x)."""
    tri = [(x, y0, z0), (x, y1, z0), (x, (y0 + y1) / 2, z1)]
    mb.poly(tri if facing > 0 else list(reversed(tri)), mat)


def _pallet(mb, x, y, yaw=0.0, mat="M_IntWood", z=0.0):
    """Euro pallet 1.2 x 1.0 x 0.14 (top at z + 0.14)."""
    with mb.at((x, y, z), rot=yaw):
        for sy in (-0.42, 0.0, 0.42):
            mb.box((0, sy, 0.05), (1.2, 0.14, 0.1), "M_IntWoodDark")
        for k in range(5):
            mb.box((-0.5 + k * 0.25, 0, 0.12), (0.14, 1.0, 0.04), mat)


def _cartons(nc, rnd, x0, x1, y, depth, z, hmax, fill=0.85):
    """A row of cardboard cartons standing on a shelf (NoCol dressing)."""
    x = x0 + 0.03
    while x < x1 - 0.2:
        cw = rnd.uniform(0.25, 0.5)
        if x + cw > x1 - 0.03:
            break
        if rnd.random() < fill:
            ch = min(hmax, rnd.uniform(0.18, 0.42))
            cd = depth * rnd.uniform(0.7, 0.92)
            nc.box((x + cw / 2, y, z + ch / 2), (cw - 0.02, cd, ch), rnd.choice(CARTONS))
            if ch < hmax - 0.25 and rnd.random() < 0.4:
                nc.box((x + cw / 2, y, z + ch + 0.1), (cw * 0.7, cd * 0.7, 0.2), rnd.choice(CARTONS))
        x += cw + 0.02


def _shelf_unit(mb, nc, rnd, x, y, yaw=0.0, w=1.8, d=0.6, h=2.2, levels=4, post=STEEL, deck="M_IntMetal"):
    """Bolted steel shelving (procedural, known shelf heights) stocked with cartons. Front at local -Y."""
    with mb.at((x, y, 0.0), rot=yaw), nc.at((x, y, 0.0), rot=yaw):
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * (w / 2 - 0.03), sy * (d / 2 - 0.03), h / 2), (0.05, 0.05, h), post)
        for k in range(levels):
            z = 0.12 + k * (h - 0.25) / (levels - 1)
            mb.box((0, 0, z), (w, d, 0.03), deck)
            if k < levels - 1:
                _cartons(nc, rnd, -w / 2 + 0.05, w / 2 - 0.05, 0.0, d, z + 0.015, (h - 0.25) / (levels - 1) - 0.08)
            else:
                _cartons(nc, rnd, -w / 2 + 0.05, w / 2 - 0.05, 0.0, d, z + 0.015, 0.45, fill=0.5)


def _rack(mb, nc, aset, rnd, x0, yc, bays, bay=2.75, depth=1.2, levels=(1.5, 3.0, 4.5), height=5.3,
          goods=True):
    """Pallet racking (blue uprights, orange beams) along +x from x0, centred on yc; goods on every level."""
    xs = [x0 + bay * i for i in range(bays + 1)]
    for x in xs:
        for s in (-1, 1):
            mb.box((x, yc + s * (depth / 2 - 0.05), height / 2), (0.09, 0.09, height), STEEL)
        for z in (0.4, 2.2, 4.0):
            mb.beam((x, yc - depth / 2 + 0.05, z), (x, yc + depth / 2 - 0.05, z + 1.2), 0.04, 0.04, STEEL)
    for z in levels:
        for s in (-1, 1):
            mb.box_mm((xs[0], yc + s * (depth / 2 - 0.05) - 0.03, z - 0.12), (xs[-1], yc + s * (depth / 2 - 0.05) + 0.03,
                      z), ORANGE)
        mb.box_mm((xs[0], yc - depth / 2 + 0.05, z - 0.02), (xs[-1], yc + depth / 2 - 0.05, z), "M_IntMetal")
    if not goods:
        return
    for i in range(bays):
        for z in (0.0,) + tuple(levels):
            for s in (-1, 1):
                if rnd.random() < (0.25 if z < 4.0 else 0.45):
                    continue
                px = xs[i] + bay / 2 + s * 0.66
                r = rnd.random()
                if r < 0.45:
                    aset.prop("SM_Crate", (px, yc, z), rnd.choice((0.0, 90.0, 180.0)))
                elif r < 0.6 and z == 0.0:
                    for bx in (-0.28, 0.28):
                        for by in (-0.28, 0.28):
                            if rnd.random() < 0.8:
                                aset.prop("SM_Barrel", (px + bx, yc + by, 0.0), rnd.uniform(0, 360), scale=0.62)
                else:
                    _pallet(mb, px, yc, 90.0, z=z)
                    _wrapped_load(nc, rnd, px, yc, z + 0.14, 90.0, rnd.uniform(0.6, 1.15) if z < 4.0 else 0.7,
                                  simple=z > 0.0)


def _fill_light(aset, x, y, z, intensity=3000.0, radius=9.0):
    aset.light((x, y, z), (1.0, 0.86, 0.66), intensity, radius, night_only=False)


# ================================================================== detail helpers (working-harbour life)
def _abs_off(A):
    """Total socket offset of a (nested) _Shifted view."""
    ox = oy = oz = 0.0
    while isinstance(A, _Shifted):
        ox, oy, oz = ox + A.off[0], oy + A.off[1], oz + A.off[2]
        A = A.base
    return ox, oy, oz


def _dress(A, mb, nc, x0, y0, x1, y1, z, z_ceil, style, seed=0, **kw):
    """DT.dress_room for rooms built in a shifted frame: the door sockets are looked up in the same local
    space as the room bounds (dress_room reads aset.sockets, which hold placement coordinates)."""
    ox, oy, oz = _abs_off(A)
    view = _Shifted(A, (0.0, 0.0, 0.0))
    view.sockets = [dict(s, pos=[s["pos"][0] - ox, s["pos"][1] - oy, s["pos"][2] - oz]) for s in A.sockets
                    if s["type"] == "door"]
    DT.dress_room(view, mb, nc, x0, y0, x1, y1, z, z_ceil, style=style, seed=seed, **kw)


def _wrapped_load(nc, rnd, x, y, z, yaw, hgt, w=1.0, d=1.18, simple=False):
    """Cartons stacked on a pallet top (z) in layers, shrink-wrapped (clear film + white top sheet).
    simple: one carton block (out-of-reach rack levels; keeps the triangle count down)."""
    with nc.at((x, y, z), rot=yaw):
        if simple:
            nc.box((0, 0, hgt / 2), (d - 0.02, w - 0.02, hgt - 0.01), rnd.choice(CARTONS[:3]))
            nc.box((0, 0, hgt + 0.012), (d + 0.01, w + 0.01, 0.006), "M_IntFabricWhite")
            nc.box((d / 2 + 0.002, 0.0, hgt * 0.6), (0.004, 0.21, 0.15), "M_IntPaper")
            return
        layers = max(1, int(hgt / 0.3))
        lh = hgt / layers
        for k in range(layers):
            for i in range(3):
                for j in range(2):
                    if k == layers - 1 and rnd.random() < 0.25:
                        continue
                    nc.box((-d / 3 + i * d / 3, -w / 4 + j * w / 2, k * lh + lh / 2), (d / 3 - 0.015, w / 2 - 0.015,
                           lh - 0.012), rnd.choice(CARTONS[:3]))
        nc.box((0, 0, hgt / 2 + 0.01), (d + 0.02, w + 0.02, hgt + 0.02), "M_HarborWrap")
        nc.box((0, 0, hgt + 0.025), (d + 0.03, w + 0.03, 0.006), "M_IntFabricWhite")
        nc.box((d / 2 + 0.012, 0.0, hgt * 0.6), (0.004, 0.21, 0.15), "M_IntPaper")       # shipping label


def _forklift(mb, nc, x, y, yaw, fork_z=0.08, load=None, rnd=None):
    """Counterbalance forklift (2.3 m body + 1.1 m forks along local +x, 1.1 m wide, guard 2.15 m)."""
    with mb.at((x, y, 0.0), rot=yaw), nc.at((x, y, 0.0), rot=yaw):
        mb.box_mm((-1.0, -0.52, 0.18), (0.85, 0.52, 0.95), CRANE_Y)                       # chassis
        mb.box_mm((-1.2, -0.55, 0.15), (-0.8, 0.55, 1.08), DMETAL)                         # counterweight
        mb.box_mm((0.45, -0.55, 0.18), (0.9, 0.55, 0.62), CRANE_Y)                          # front fenders
        for wx, r in ((0.6, 0.31), (-0.85, 0.26)):
            for s in (-1, 1):
                with mb.at((wx, s * 0.47, r), rot_x=90):
                    mb.cylinder((0, 0, -0.11), r, 0.22, "M_Black", seg=12)
                    mb.cylinder((0, 0, -0.115 if s < 0 else 0.11), r * 0.55, 0.005, "M_IntMetal", seg=10)
        mb.box_mm((-0.62, -0.25, 0.95), (-0.25, 0.25, 1.06), "M_IntBlack")                 # seat
        mb.box_mm((-0.66, -0.25, 1.06), (-0.58, 0.25, 1.5), "M_IntBlack")
        mb.box_mm((0.12, -0.2, 0.95), (0.42, 0.2, 1.2), CRANE_Y)                           # dash
        with mb.at((0.15, 0.0, 1.38), rot_y=-35):
            mb.torus((0, 0, 0), 0.17, 0.02, "M_IntBlack", seg=12, tube_seg=4)
        mb.cylinder((0.25, 0.0, 1.15), 0.025, 0.22, "M_IntBlack", seg=6)
        for k in range(3):                                                                  # levers
            nc.box((0.38, -0.12 + k * 0.08, 1.32), (0.02, 0.02, 0.2), "M_IntBlack")
            nc.sphere((0.38, -0.12 + k * 0.08, 1.43), 0.025, "M_IntFabricRed", seg=6, rings=4)
        for gx in (-0.85, 0.52):                                                            # overhead guard
            for s in (-1, 1):
                mb.box((gx, s * 0.48, 1.55), (0.07, 0.07, 1.2), DMETAL)
        mb.box_mm((-0.9, -0.52, 2.13), (0.57, 0.52, 2.18), DMETAL)
        for k in range(6):
            mb.box((-0.75 + k * 0.24, 0.0, 2.12), (0.05, 0.98, 0.04), DMETAL)
        nc.cylinder((-0.3, 0.0, 2.18), 0.06, 0.06, "M_LifeboatOrange", seg=8)               # beacon
        for s in (-1, 1):                                                                   # mast
            mb.box((0.98, s * 0.32, 1.15), (0.1, 0.12, 2.15), DMETAL)
        for zz in (0.25, 1.2, 2.15):
            mb.box((0.98, 0.0, zz), (0.1, 0.76, 0.08), DMETAL)
        mb.box_mm((1.05, -0.5, fork_z), (1.1, 0.5, fork_z + 0.55), DMETAL)                  # carriage
        for s in (-1, 1):
            mb.box_mm((1.1, s * 0.3 - 0.06, fork_z), (2.2, s * 0.3 + 0.06, fork_z + 0.05), DMETAL)
        nc.box((-1.21, 0.0, 0.85), (0.005, 0.35, 0.12), "M_IntBlack")
        if load:
            _pallet(mb, 1.65, 0.0, 0.0, z=fork_z + 0.05)
            _wrapped_load(nc, rnd or random.Random(1), 1.65, 0.0, fork_z + 0.19, 0.0, load)


def _pallet_jack(mb, x, y, yaw):
    """Hand pallet truck: forks along local +x (1.15 m), tiller handle at the -x end."""
    with mb.at((x, y, 0.0), rot=yaw):
        for s in (-1, 1):
            mb.box_mm((0.0, s * 0.28 - 0.08, 0.04), (1.15, s * 0.28 + 0.08, 0.085), "M_LifeboatOrange")
        mb.box_mm((-0.3, -0.36, 0.04), (0.02, 0.36, 0.3), "M_LifeboatOrange")
        mb.cylinder((-0.2, 0.0, 0.3), 0.07, 0.25, "M_LifeboatOrange", seg=8)
        mb.beam((-0.2, 0.0, 0.5), (-0.55, 0.0, 1.15), 0.035, 0.035, "M_IntBlack")
        mb.box((-0.57, 0.0, 1.17), (0.06, 0.28, 0.06), "M_IntBlack")
        with mb.at((-0.2, 0.0, 0.09), rot_x=90):
            mb.cylinder((0, 0, -0.12), 0.09, 0.24, "M_Black", seg=10)


def _crate_mesh(mb, x, y, z, yaw=0.0, s=0.96):
    """Slatted wooden crate (mesh, so things can be stacked on it) - same size as SM_Crate."""
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, 0, s / 2), (s - 0.04, s - 0.04, s - 0.02), "M_IntWood")
        for k in (-1, 1):
            mb.box((0, k * (s / 2 - 0.01), s * 0.5), (s, 0.03, s), "M_IntWoodDark")
            mb.box((k * (s / 2 - 0.01), 0, s * 0.5), (0.03, s, s), "M_IntWoodDark")
        mb.box((0, 0, s - 0.01), (s, s, 0.02), "M_IntWoodDark")
        for k in range(3):
            mb.box((0, -s / 2 - 0.012, s * (0.2 + k * 0.3)), (s - 0.1, 0.02, 0.12), "M_IntWood")


def _ticket_machine(mb, nc, A, x, y, yaw, label="TICKETS"):
    """Self-service ticket machine (0.7 x 0.45 x 1.7 m), screen + keypad + slots facing local -Y."""
    with mb.at((x, y, 0.0), rot=yaw):
        mb.box((0, 0, 0.85), (0.7, 0.45, 1.7), BLUE)
        mb.box((0, -0.05, 1.72), (0.74, 0.5, 0.06), TRIM)
        mb.box((0, -0.25, 1.05), (0.6, 0.1, 0.06), TRIM)                         # keypad shelf
    with nc.at((x, y, 0.0), rot=yaw):
        nc.box((0, -0.227, 1.38), (0.46, 0.006, 0.34), "M_IntScreen")
        nc.box((0, -0.228, 1.62), (0.6, 0.006, 0.1), "M_IntTrimWhite")
        for i in range(3):
            for j in range(4):
                nc.box((-0.08 + i * 0.06, -0.28 - j * 0.02, 1.085), (0.045, 0.018, 0.012), "M_IntMetal")
        nc.box((0.2, -0.29, 1.085), (0.12, 0.05, 0.012), "M_IntBlack")             # card reader
        nc.box((0.0, -0.227, 0.55), (0.3, 0.006, 0.05), "M_IntBlack")              # ticket slot
        nc.box((0.0, -0.24, 0.45), (0.36, 0.03, 0.12), "M_IntMetal")
        nc.box((0.22, -0.227, 0.85), (0.08, 0.006, 0.16), "M_IntBlack")            # coin slot
    A.text(label, K.wall_point(x, y, yaw, 0.235, 1.6), yaw, size=0.07, color=(0.1, 0.25, 0.62))


def _luggage_cart(mb, nc, x, y, yaw, bags=2, seed=0):
    """Airport-style luggage trolley (1.0 x 0.6 m, handle at local -x) with a couple of bags."""
    rnd = random.Random(seed)
    with mb.at((x, y, 0.0), rot=yaw):
        mb.box((0.05, 0, 0.2), (0.9, 0.58, 0.04), "M_IntMetal")
        for s in (-1, 1):
            mb.box((0.5, s * 0.27, 0.45), (0.04, 0.04, 0.5), "M_IntMetal")
            mb.beam((-0.4, s * 0.27, 0.2), (-0.5, s * 0.27, 1.0), 0.035, 0.035, "M_IntMetal")
        mb.box((-0.5, 0, 1.0), (0.05, 0.6, 0.05), BLUE)
        mb.box((0.5, 0, 0.68), (0.04, 0.58, 0.04), "M_IntMetal")
        for wx in (-0.35, 0.4):
            for s in (-1, 1):
                with mb.at((wx, s * 0.24, 0.08), rot_x=90):
                    mb.cylinder((0, 0, -0.025), 0.08, 0.05, "M_Black", seg=8)
    with nc.at((x, y, 0.0), rot=yaw):
        z = 0.22
        for k in range(bags):
            h = rnd.uniform(0.2, 0.3)
            c = rnd.choice(("M_IntFabricRed", "M_IntFabricNavy", "M_IntFabricGreen", "M_IntWoodDark", "M_IntFabricPurple"))
            nc.box((0.05, 0, z + h / 2), (rnd.uniform(0.6, 0.8), rnd.uniform(0.4, 0.5), h), c)
            nc.box((0.05, 0, z + h + 0.02), (0.18, 0.03, 0.04), "M_IntBlack")
            z += h


def _card_spinner(mb, nc, x, y, seed=0):
    """Rotating postcard / trading-card stand (0.55 m across, 1.75 m high)."""
    rnd = random.Random(seed)
    mb.cylinder((x, y, 0.0), 0.28, 0.03, "M_IntMetal", seg=12)
    mb.cylinder((x, y, 0.0), 0.025, 1.75, "M_IntMetal", seg=8)
    mb.sphere((x, y, 1.77), 0.04, "M_IntFabricRed", seg=8, rings=4)
    for t in range(4):
        z = 0.55 + t * 0.3
        for f in range(4):
            a = f * 90.0 + t * 20.0
            with nc.at((x, y, z), rot=a):
                nc.box((0, -0.2, 0.0), (0.34, 0.012, 0.012), "M_IntMetal")
                for c in range(3):
                    nc.box((-0.11 + c * 0.11, -0.21, 0.08), (0.1, 0.006, 0.15),
                           rnd.choice(K.POSTERS + ("M_IntPaper", "M_CardBack")))


def _souvenir_table(mb, nc, A, x, y, yaw, seed=0):
    """Tiered souvenir display (1.4 x 0.7 m): plush toys, mugs, keychain board, booster packs, island snow globes."""
    rnd = random.Random(seed)
    with mb.at((x, y, 0.0), rot=yaw):
        mb.box((0, 0, 0.4), (1.4, 0.7, 0.8), "M_IntWood")
        mb.box((0, 0.12, 0.95), (1.4, 0.4, 0.3), "M_IntWood")
        mb.box((0, 0.22, 1.25), (1.4, 0.2, 0.3), "M_IntWood")
        mb.box((0, 0.33, 1.5), (1.4, 0.04, 0.8), BLUE)                             # back board
    with nc.at((x, y, 0.0), rot=yaw):
        for k in range(6):                                                         # plushies
            px = -0.58 + k * 0.23
            c = rnd.choice(("M_IntFabricRed", "M_IntFabricYellow", "M_IntFabricBlue", "M_IntFabricPink"))
            nc.sphere((px, -0.2, 0.89), 0.08, c, seg=8, rings=5)
            nc.sphere((px, -0.2, 1.0), 0.06, c, seg=8, rings=5)
        for k in range(8):                                                         # mugs on tier 1
            DT.mug(nc, -0.6 + k * 0.17, 0.0, 1.1, seed=seed + k, coffee=False)
        for k in range(10):                                                        # booster packs on tier 2
            nc.box((-0.62 + k * 0.135, 0.17, 1.47), (0.09, 0.02, 0.15), K.POSTERS[k % 4])
        for k in range(5):                                                         # snow globes
            nc.sphere((-0.5 + k * 0.25, 0.27, 1.45), 0.05, "M_IntGlassClear", seg=8, rings=5)
        for i in range(5):                                                         # keychains on the board
            for j in range(3):
                nc.box((-0.55 + i * 0.27, 0.305, 1.65 + j * 0.14), (0.05, 0.01, 0.07),
                       rnd.choice(K.FABRICS + ("M_IntTrimGold",)))
    A.text("SOUVENIRS", K.wall_point(*DT._P(x, y, yaw, 0.0, 0.31), yaw, 0.0, 1.85), yaw, size=0.09, color=(1.0, 0.9, 0.3))


def _vest_hooks(nc, x, y, z, yaw, n=4, vests=3, helmets=True):
    """Hook rail with hi-vis vests (and hard hats on a shelf above): (x, y) on the wall, local -Y into the room."""
    w = n * 0.3
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.01, 0), (w, 0.02, 0.08), "M_IntWood")
        for k in range(n):
            u = -w / 2 + 0.15 + k * 0.3
            nc.box((u, -0.05, 0.0), (0.02, 0.07, 0.02), "M_DetSilver")
            if k < vests:
                m = "M_HarborHiVis" if k % 3 != 2 else "M_LifeboatOrange"
                nc.box((u, -0.07, -0.33), (0.26, 0.05, 0.6), m)
                nc.box((u, -0.072, -0.42), (0.265, 0.05, 0.035), "M_HarborReflect")
                nc.box((u, -0.072, -0.25), (0.265, 0.05, 0.035), "M_HarborReflect")
                for s in (-1, 1):
                    nc.box((u + s * 0.08, -0.068, -0.04), (0.05, 0.04, 0.12), m)
        if helmets:
            nc.box((0, -0.12, 0.3), (w, 0.24, 0.02), "M_IntWood")
            for k in range(min(n, 3)):
                u = -w / 2 + 0.2 + k * 0.35
                nc.sphere((u, -0.12, 0.31), 0.13, ("M_CrateYellow", "M_IntTrimWhite", "M_LifeboatOrange")[k % 3],
                          seg=10, rings=5, hemi=True)
                nc.cylinder((u, -0.12, 0.31), 0.15, 0.012, ("M_CrateYellow", "M_IntTrimWhite", "M_LifeboatOrange")[k % 3],
                            seg=10)


def _wall_clipboards(nc, x, y, z, yaw, n=3, seed=0):
    """Clipboards hanging on nails along a wall / rack post (x, y on the face, local -Y outwards)."""
    rnd = random.Random(seed)
    with nc.at((x, y, z), rot=yaw):
        for k in range(n):
            u = (k - (n - 1) / 2) * 0.32
            dz = rnd.uniform(-0.04, 0.04)
            nc.box((u, -0.01, dz), (0.23, 0.012, 0.32), "M_IntWoodDark")
            nc.box((u, -0.018, dz - 0.02), (0.2, 0.004, 0.26), "M_IntPaper")
            nc.box((u, -0.022, dz + 0.13), (0.09, 0.012, 0.035), "M_DetSilver")
            for r in range(4):
                nc.box((u - 0.02, -0.0205, dz + 0.06 - r * 0.045), (0.13, 0.002, 0.008), "M_IntBlack")


def _wall_shelf(nc, aset, x, y, z, yaw, w, items, d=0.25, seed=0):
    """Short wall shelf with brackets; items: sequence of catalog names placed along it."""
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -d / 2, -0.015), (w, d, 0.03), "M_IntWood")
        for s in (-1, 1):
            nc.box((s * (w / 2 - 0.08), -0.09, -0.1), (0.02, 0.16, 0.16), "M_IntMetal")
    for i, it in enumerate(items):
        u = -w / 2 + w * (i + 0.5) / len(items)
        px, py = DT._P(x, y, yaw, u, -d / 2)
        aset.prop(it, (px, py, z), yaw + random.Random(seed + i).uniform(-12, 12))


def _wall_map(nc, aset, x, y, z, yaw, w=1.2, h=0.85, title=None, seed=0):
    """Framed sea chart / island map on a wall: sea, island, routes, pins (x, y on the wall, -Y into room)."""
    rnd = random.Random(seed)
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.012, 0), (w + 0.08, 0.024, h + 0.08), "M_IntWoodDark")
        nc.box((0, -0.026, 0), (w, 0.006, h), "M_IntPoster2")
        nc.box((-w * 0.1, -0.031, -h * 0.05), (w * 0.34, 0.004, h * 0.42), "M_IntFabricGreen")
        nc.box((-w * 0.05, -0.032, h * 0.08), (w * 0.12, 0.004, h * 0.14), "M_IntFabricYellow")
        for k in range(6):
            nc.box((rnd.uniform(-w * 0.42, w * 0.42), -0.034, rnd.uniform(-h * 0.4, h * 0.4)), (0.025, 0.006, 0.025),
                   "M_IntFabricRed")
        for k in range(3):
            nc.box((rnd.uniform(-w * 0.3, w * 0.3), -0.033, rnd.uniform(-h * 0.35, h * 0.35)),
                   (rnd.uniform(0.2, 0.5), 0.003, 0.008), "M_IntTrimWhite")
    if title:
        aset.text(title, K.wall_point(x, y, yaw, 0.04, z + h / 2 - 0.09), yaw, size=0.06, color=(1, 1, 1))


def _first_aid(nc, aset, x, y, z, yaw):
    """Wall first-aid cabinet (white box, green cross) at centre height z."""
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.06, 0), (0.4, 0.12, 0.45), "M_IntTrimWhite")
        nc.box((0, -0.122, 0.02), (0.16, 0.004, 0.05), "M_DetExit")
        nc.box((0, -0.122, 0.02), (0.05, 0.004, 0.16), "M_DetExit")


def _whiteboard(nc, aset, x, y, z, yaw, w=1.2, h=0.8, lines=(), seed=0):
    """Whiteboard with marker writing (text) and a tray (x, y on the wall, local -Y into the room)."""
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.012, h / 2), (w + 0.04, 0.024, h + 0.04), "M_IntMetal")
        nc.box((0, -0.026, h / 2), (w, 0.005, h), "M_IntTrimWhite")
        nc.box((0, -0.05, -0.01), (w * 0.7, 0.06, 0.02), "M_IntMetal")
        for k, m in enumerate(("M_IntFabricRed", "M_IntFabricBlue", "M_IntBlack")):
            nc.box((-0.2 + k * 0.14, -0.05, 0.005), (0.12, 0.018, 0.018), m)
        for k in range(3):
            nc.box((w * 0.3, -0.03, h - 0.2 - k * 0.2), (0.25, 0.004, 0.16), ("M_IntPoster3", "M_IntPaper", "M_IntPoster1")[k])
    for i, t in enumerate(lines):
        aset.text(t, K.wall_point(x, y, yaw, 0.035, z + h - 0.14 - i * 0.12), yaw, size=0.065, color=(0.1, 0.15, 0.45))


def _water_cooler(mb, nc, x, y, yaw):
    with mb.at((x, y, 0.0), rot=yaw):
        mb.box((0, 0, 0.5), (0.32, 0.32, 1.0), "M_IntTrimWhite")
    with nc.at((x, y, 0.0), rot=yaw):
        nc.cylinder((0, 0, 1.0), 0.13, 0.42, "M_HarborWrap", seg=12)
        nc.cylinder((0, 0, 1.0), 0.12, 0.3, "M_IntWater", seg=12)
        for s, m in ((-1, "M_IntFabricBlue"), (1, "M_IntFabricRed")):
            nc.box((s * 0.07, -0.17, 0.78), (0.04, 0.03, 0.05), m)
        nc.box((0, -0.17, 0.62), (0.22, 0.04, 0.02), "M_IntMetal")
        nc.cylinder((0.22, 0, 0.0), 0.04, 0.6, "M_IntTrimWhite", seg=8)                    # cup dispenser


def _fridge(mb, nc, x, y, yaw, h=1.75):
    with mb.at((x, y, 0.0), rot=yaw):
        mb.box((0, 0, h / 2), (0.6, 0.65, h), "M_IntTrimWhite")
    with nc.at((x, y, 0.0), rot=yaw):
        nc.box((0, -0.326, h * 0.62), (0.58, 0.004, 0.006), "M_IntMetal")
        nc.box((0.24, -0.34, h * 0.75), (0.03, 0.03, 0.3), "M_IntMetal")
        nc.box((0.24, -0.34, h * 0.4), (0.03, 0.03, 0.25), "M_IntMetal")
        for k in range(4):
            nc.box((-0.12 + k * 0.08, -0.328, h * 0.8 - (k % 2) * 0.1), (0.06, 0.004, 0.06), K.POSTERS[k % 4])


def _coffee_machine(nc, x, y, z, yaw):
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, 0, 0.19), (0.26, 0.32, 0.38), "M_IntBlack")
        nc.box((0, -0.05, 0.06), (0.22, 0.2, 0.02), "M_IntMetal")
        nc.cylinder((0, -0.05, 0.07), 0.05, 0.1, "M_IntGlassClear", seg=10)
        nc.box((0, -0.162, 0.3), (0.12, 0.004, 0.05), "M_IntScreen")


def _round_switch(nc, ang, z, r):
    """Light switch / outlet on a curved wall at polar angle ang (deg), radius r (wall face)."""
    x, y, _ = _polar(r, ang)
    DT.switch(nc, x, y, z, ang - 90.0)


def _round_outlet(nc, ang, z, r):
    x, y, _ = _polar(r, ang)
    DT.outlet(nc, x, y, z, ang - 90.0)


def _hall_services(A, mb, nc, x0, y0, x1, y1, zc, seed=0):
    """dress_room for a tall industrial hall + the pipework it implies: sprinkler mains along x (the heads hang
    from them at zc) and ducts from the two ceiling vents to the nearest gable wall."""
    _dress(A, mb, nc, x0, y0, x1, y1, 0.0, zc, "service", seed=seed)
    ny = max(1, int((y1 - y0) / 3.0))
    for j in range(ny):
        y = y0 + (y1 - y0) * (j + 0.5) / ny
        nc.box_mm((x0, y - 0.03, zc + 0.065), (x1, y + 0.03, zc + 0.125), "M_IntFabricRed")
    for fx, fy in ((0.25, 0.7), (0.75, 0.3)):
        vx, vy = x0 + (x1 - x0) * fx, y0 + (y1 - y0) * fy
        xe = x0 if fx < 0.5 else x1
        nc.box_mm((min(vx, xe), vy - 0.3, zc + 0.02), (max(vx, xe), vy + 0.3, zc + 0.5), "M_IntMetal")


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
    # shelter life: notice + tide boards on the screen, rod rack, cooler, tackle, bucket, boots, life ring
    fy = sy_1 - 0.09
    K.bulletin(nc, aset, PIER_X - 1.75, fy, 1.05, 0.0, 0.8, 0.75, title="PIER RULES", rng_seed=41)
    with nc.at((PIER_X + 1.75, fy, 1.05)):
        nc.box((0, -0.015, 0.4), (0.8, 0.03, 0.8), BLUE)
        nc.box((0, -0.032, 0.36), (0.7, 0.004, 0.6), "M_IntTrimWhite")
        for k in range(6):
            nc.box((0, -0.035, 0.6 - k * 0.09), (0.6, 0.002, 0.012), "M_IntBlack")
    aset.text("TIDE TABLE", (PIER_X + 1.75, fy - 0.04, 1.73), 0.0, size=0.07, color=(1, 1, 1))
    aset.prop("SM_Int_Lifebuoy", (PIER_X, sy_1 - 0.01, 0.95), 180.0)
    with mb.at((sx0 + 0.35, -106.0, 0.0)):                                              # fishing-rod rack
        for dy in (-0.5, 0.5):
            mb.box((0, dy, 0.6), (0.06, 0.06, 1.2), "M_DarkWood")
        mb.box((0, 0, 1.15), (0.08, 1.1, 0.06), "M_DarkWood")
        mb.box((0, 0, 0.25), (0.25, 1.1, 0.05), "M_DarkWood")
    for k in range(4):
        yy = -106.4 + k * 0.27
        nc.beam((sx0 + 0.38, yy, 0.27), (sx0 + 0.3, yy + 0.05, 2.3), 0.025, 0.025, ("M_IntBlack", "M_IntFabricRed")[k % 2])
        nc.cylinder((sx0 + 0.42, yy, 0.55), 0.05, 0.06, "M_IntMetal", seg=8)
    with nc.at((PIER_X + 1.9, -105.4, 0.0), rot=10.0):                                  # cooler box
        nc.box((0, 0, 0.2), (0.62, 0.4, 0.4), "M_IntFabricBlue")
        nc.box((0, 0, 0.42), (0.64, 0.42, 0.05), "M_IntTrimWhite")
    aset.prop("SM_Int_Toolbox", (PIER_X + 1.95, -104.45, 0.0), -20.0)
    aset.prop("SM_Int_Bucket", (PIER_X - 1.95, -104.3, 0.0), 0.0)
    aset.prop("SM_Int_Boots", (PIER_X - 1.6, -105.3, 0.0), 30.0)
    K.camera(aset, "pier_shelter", (sx0 + 0.6, sy_0 + 0.3, 1.6), (PIER_X + 0.5, sy_1 - 0.3, 0.7), 15.0)
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


PORT_Z, PORT_R = 1.3, 0.22
PORTHOLES = [-30.0 + 2.4 * k for k in range(20)]          # x of every porthole (both sides)
LD_Z, LD_C = 0.2, 2.9                                     # lower (cabin) deck floor / ceiling, ship-local
LD_X0, LD_X1 = -31.2, 16.8
LD_HOLE = (-7.15, -1.0, -3.4, 1.0)                        # stairwell saloon -> cabin deck (x0, y0, x1, y1)


def _hull_hw(x, z):
    """Hull half width at ship-local x (not station xn) and height z."""
    xb = 35.0 - (F_DECK - z) * 0.45
    xs = -35.0 + max(0.0, -z) * 0.55
    xn = (x - xs) / (xb - xs) * 70.0 - 35.0
    return _f_plan(xn) * _f_factor(z)


def _ld_lining(x):
    """Inner lining of the cabin deck (0.25 m inside the hull at its narrowest height)."""
    return min(_hull_hw(x, LD_Z), _hull_hw(x + 1.2, LD_Z), _hull_hw(x - 1.2, LD_Z)) - 0.25


def _holed_quad(mb, a, b, c, d, m, holes, v0, v1, flip=False):
    """Quad a-b-c-d (u along a->b, v along a->d) minus rectangular holes [(u0, u1)] spanning v0..v1."""
    if not holes:
        if flip:
            mb.quad(a, d, c, b, m, smooth=True)
        else:
            mb.quad(a, b, c, d, m, smooth=True)
        return

    def P(u, v):
        return tuple((1 - u) * (1 - v) * a[k] + u * (1 - v) * b[k] + u * v * c[k] + (1 - u) * v * d[k] for k in range(3))

    def rect(u0, u1, w0, w1):
        if u1 - u0 < 1e-4 or w1 - w0 < 1e-4:
            return
        A, B, C, D = P(u0, w0), P(u1, w0), P(u1, w1), P(u0, w1)
        if flip:
            mb.quad(A, D, C, B, m, smooth=True)
        else:
            mb.quad(A, B, C, D, m, smooth=True)
    rect(0.0, 1.0, 0.0, v0)
    rect(0.0, 1.0, v1, 1.0)
    u = 0.0
    for h0, h1 in sorted(holes):
        rect(u, h0, v0, v1)
        u = h1
    rect(u, 1.0, v0, v1)


def _deck_around_hole(mb, xa, xb, hw, z, mat):
    """Main-deck quad xa..xb (half width hw, height z) with the LD_HOLE stairwell left open."""
    hx0, hy0, hx1, hy1 = LD_HOLE
    pieces = [(xa, -hw, xb, hy0), (xa, hy1, xb, hw)]
    if xa < hx0:
        pieces.append((xa, hy0, min(xb, hx0), hy1))
    if xb > hx1:
        pieces.append((max(xa, hx1), hy0, xb, hy1))
    for x0, y0, x1, y1 in pieces:
        if x1 - x0 > 1e-4:
            mb.quad((x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z), mat)


def _ferry(mb, aset):
    nl, ns = len(_F_LEVELS), len(_F_XN)

    def V(i, j, s):
        xn = _F_XN[i]
        z, f = _F_LEVELS[j]
        x = _f_xmap(xn, z)
        if j == nl - 1:
            z = _f_sheer(x)
        return (x, s * _f_plan(xn) * f, z)

    # ---------------------------------------------------------------- hull shell
    jp = [k for k, (zz, f) in enumerate(_F_LEVELS) if zz == 0.9][0]          # band holding the portholes
    pv0, pv1 = (PORT_Z - PORT_R - 0.9) / 0.95, (PORT_Z + PORT_R - 0.9) / 0.95
    for i in range(ns - 1):
        for j in range(nl - 1):
            for s in (-1, 1):
                a, b, c, d = V(i, j, s), V(i + 1, j, s), V(i + 1, j + 1, s), V(i, j + 1, s)
                m = _hull_mat((a[2] + c[2]) / 2)
                holes = []
                if j == jp:            # real porthole openings: cut square holes (the brass rings cover the corners)
                    vm = (pv0 + pv1) / 2
                    xl, xr = a[0] + vm * (d[0] - a[0]), b[0] + vm * (c[0] - b[0])
                    for xp in PORTHOLES:
                        u0, u1 = (xp - PORT_R - xl) / (xr - xl), (xp + PORT_R - xl) / (xr - xl)
                        if u1 > 0.0 and u0 < 1.0:
                            holes.append((max(u0, 0.0), min(u1, 1.0)))
                _holed_quad(mb, a, b, c, d, m, holes, pv0, pv1, flip=s > 0)
        # keel
        mb.quad(V(i, 0, -1), V(i, 0, 1), V(i + 1, 0, 1), V(i + 1, 0, -1), BOTTOM)
        # main deck (stairwell down to the cabin deck cut out)
        qa, qb = V(i, nl - 1, -1), V(i + 1, nl - 1, 1)
        if qb[0] <= LD_HOLE[0] or qa[0] >= LD_HOLE[2]:
            mb.quad(V(i, nl - 1, -1), V(i + 1, nl - 1, -1), V(i + 1, nl - 1, 1), V(i, nl - 1, 1), DECK)
        else:
            _deck_around_hole(mb, qa[0], qb[0], qb[1], qa[2], DECK)
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

    # portholes along the hull (above the blue stripes): real openings, clear glass, brass rings, reveal tubes
    for s in (-1, 1):
        for x in PORTHOLES:
            hw = _hull_hw(x, PORT_Z)
            yl = _ld_lining(x)
            L = hw - yl
            with mb.at((x, s * hw, PORT_Z), rot_x=90):
                k = 1 if s > 0 else -1                              # local z towards the inside (rot_x 90: +z -> -y)
                mb.cylinder((0, 0, -0.01 if k > 0 else -L + 0.01), PORT_R, L, "M_IntMetal", seg=12, smooth=False,
                            cap_top=False, cap_bottom=False)
                mb.cylinder((0, 0, k * 0.08 - 0.005), PORT_R + 0.01, 0.01, "M_GlassClear", seg=10, smooth=False,
                            cap_bottom=False)
                mb.torus((0, 0, -k * 0.02), PORT_R + 0.06, 0.055, TRIM, seg=12, tube_seg=3)
                mb.torus((0, 0, k * (L + 0.01)), PORT_R + 0.06, 0.05, "M_IntTrimGold", seg=12, tube_seg=3)
    # anchors / hawse plates at the bow
    for s in (-1, 1):
        xa = 30.0
        hw = _f_plan(xa) * _f_factor(3.0)
        slope = (_f_plan(xa + 0.5) - _f_plan(xa - 0.5))
        ang = math.degrees(math.atan2(s * slope, 1.0))
        with mb.at((xa, s * hw, 3.0), rot=ang):
            mb.box((0, 0, 0), (1.4, 0.3, 1.0), DMETAL)
            mb.box((0, s * 0.12, -0.75), (0.5, 0.25, 0.6), DMETAL)

    # ---------------------------------------------------------------- superstructure (walk-in: real walls)
    # Every doorway is a real opening. The ferry bobs (floating actor), so instead of automatic door actors
    # (which would not move with the ship) the weather doors are modelled hooked open against the outer wall.
    d1 = _rounded_rect(-24.0, 10.5, 5.6, 3.8)
    ops = {i: [K.Window(_edge_len(d1, i) / 2, _edge_len(d1, i) - 0.12, 1.05, 2.2, frame=TRIM, mullions=0)]
           for i in range(1, 9)}
    for s in (-1, 1):
        edge, ex0, dx = (0, -24.0, 1.0) if s < 0 else (9, 10.5, -1.0)
        ops[edge] = [K.Door((GANG_SHIP_X - ex0) * dx, 1.1, 2.1, None, z0=0.05, trim_in=K.TRIM_WOOD)]
        for xa, xb, n in ((-22.5, -6.8, 6), (-3.2, 9.6, 5)):
            p0, p1 = ((xa, -5.6), (xb, -5.6)) if s < 0 else ((xb, 5.6), (xa, 5.6))
            for u in _frames(mb, p0, p1, 4.95, n, 1.5, 1.25):
                ops[edge].append(K.Window((p0[0] + u * dx - ex0) * dx, 1.5, 1.0, 2.25, frame=TRIM, mullions=0))
        # side door at the gangway: frame + leaf hooked open aft
        xd0, xd1 = GANG_SHIP_X - 0.55, GANG_SHIP_X + 0.55
        ya, yb = sorted((s * 5.6, s * 5.66))
        mb.box_mm((xd0 - 0.1, ya, F_DECK), (xd0, yb, 6.2), TRIM)
        mb.box_mm((xd1, ya, F_DECK), (xd1 + 0.1, yb, 6.2), TRIM)
        mb.box_mm((xd0, ya, 6.1), (xd1, yb, 6.2), TRIM)
        ya, yb = sorted((s * 5.67, s * 5.73))
        mb.box_mm((xd0 - 1.2, ya, F_DECK + 0.02), (xd0 - 0.12, yb, 6.08), STRIPE)
        mb.box((xd0 - 0.66, s * 5.74, 5.5), (0.4, 0.02, 0.4), "M_GlassClear")
        mb.box((xd0 - 1.25, s * 5.68, 5.0), (0.1, 0.08, 0.05), DMETAL)                  # hook
    ops[10] = [K.Door(5.6, 1.9, 2.1, None, z0=0.05, trim_in=K.TRIM_WOOD)]
    _ship_walls(mb, d1, 3.95, 3.05, ops, K.PLASTER_CREAM)
    _band(mb, [(-24.0, -5.6), (10.5, -5.6)], 6.6, 6.8, STRIPE, off=0.02)
    _band(mb, [(10.5, 5.6), (-24.0, 5.6)], 6.6, 6.8, STRIPE, off=0.02)
    # aft wall of deck 1: double doors (glass leaves hooked open)
    _aft_doors(mb, -24.0, F_DECK, 1.9, 2.1)

    # deck 2 slab (overhangs the side walkways)
    d2s = _rounded_rect(-27.0, 12.0, 7.0, 4.5)
    mb.prism(d2s, 7.0, 7.3, HULL, top_mat=DECK)
    # deck 2 cabin with ribbon windows
    d2 = _rounded_rect(-15.0, 9.5, 5.6, 3.5)
    ops = {i: [K.Window(_edge_len(d2, i) / 2, _edge_len(d2, i) - (0.3 if i in (0, 9) else 0.12), 0.7, 1.95,
                        frame=TRIM, mullions=14 if i in (0, 9) else 0)] for i in range(10)}
    ops[10] = [K.Door(5.6, 1.9, 2.05, None, trim_in=K.TRIM_WOOD)]
    _ship_walls(mb, d2, 7.3, 2.7, ops, K.PLASTER_WHITE)
    for s in (-1, 1):
        x = -13.6
        while x < 9.0:
            mb.box((x, s * 5.66, 8.62), (0.12, 0.1, 1.3), TRIM)
            x += 1.7
    _aft_doors(mb, -15.0, 7.3, 1.9, 2.05)

    # deck 3 slab + bridge
    d3s = _rounded_rect(-16.0, 9.0, 6.2, 4.0)
    mb.prism(d3s, 10.0, 10.3, HULL, top_mat=DECK)
    br = _rounded_rect(4.0, 10.0, 6.0, 2.6)
    ops = {i: [K.Window(_edge_len(br, i) / 2, _edge_len(br, i) - 0.12, 1.0, 2.35, frame=TRIM, mullions=0)]
           for i in range(1, 9)}
    ops[0] = [K.Window(4.25, 3.35, 1.0, 2.35, frame=TRIM, mullions=1)]
    ops[9] = [K.Window(1.75, 3.35, 1.0, 2.35, frame=TRIM, mullions=1)]
    ops[10] = [K.Door(6.0, 1.0, 2.1, None, trim_in=K.TRIM_WOOD)]
    _ship_walls(mb, br, 10.3, 2.7, ops, K.PLASTER_WHITE)
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
    # bridge aft door: frame + leaf hooked open
    mb.box_mm((3.94, -0.6, 10.3), (4.0, -0.5, 12.5), TRIM)
    mb.box_mm((3.94, 0.5, 10.3), (4.0, 0.6, 12.5), TRIM)
    mb.box_mm((3.94, -0.5, 12.4), (4.0, 0.5, 12.5), TRIM)
    mb.box_mm((3.87, -1.68, 10.32), (3.93, -0.62, 12.38), STRIPE)
    mb.box((3.86, -1.15, 11.75), (0.02, 0.35, 0.35), "M_GlassClear")
    _ferry_interior(mb, aset, d1, d2, br)

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


def _edge_len(pts, i):
    a, b = pts[i], pts[(i + 1) % len(pts)]
    return math.hypot(b[0] - a[0], b[1] - a[1])


def _ship_walls(mb, pts, z0, h, ops, inner, thick=0.2):
    """Cabin walls along a CCW footprint (outer face on the footprint line, as the old prism)."""
    for i in range(len(pts)):
        K.wall(None, mb, pts[i], pts[(i + 1) % len(pts)], z0, h, thick, HULL, inner=inner, openings=ops.get(i, ()),
               trim=None, trim_in=K.TRIM_WOOD)


def _aft_doors(mb, x, z, w, h):
    """Frame of a double doorway in an aft wall (outer face at x, outside = -x) + both glass leaves hooked open
    flat against the wall."""
    hw = w / 2
    for s in (-1, 1):
        a, b = sorted((s * hw, s * (hw + 0.12)))
        mb.box_mm((x - 0.06, a, z), (x, b, z + h + 0.12), TRIM)
        a, b = sorted((s * (hw + 0.14), s * (w + 0.14)))
        mb.box_mm((x - 0.12, a, z + 0.02), (x - 0.07, b, z + 0.14), TRIM)
        mb.box_mm((x - 0.12, a, z + h - 0.1), (x - 0.07, b, z + h - 0.02), TRIM)
        mb.box_mm((x - 0.12, a, z + 0.14), (x - 0.07, a + 0.07, z + h - 0.1), TRIM)
        mb.box_mm((x - 0.12, b - 0.07, z + 0.14), (x - 0.07, b, z + h - 0.1), TRIM)
        mb.box_mm((x - 0.1, a + 0.07, z + 0.14), (x - 0.09, b - 0.07, z + h - 0.1), GLASS_IN)
        mb.box((x - 0.1, s * (w + 0.2), z + 1.0), (0.08, 0.1, 0.05), DMETAL)              # hook
    mb.box_mm((x - 0.06, -hw, z + h), (x, hw, z + h + 0.12), TRIM)


def _seat_block(mb, x, yc, n, w=0.55):
    """Row of ferry seats facing +x (blue cushions, white headrest covers, metal frame)."""
    L = n * w
    with mb.at((x, yc, 0.0)):
        mb.box((0.0, 0, 0.22), (0.42, L, 0.06), "M_IntMetal")
        for sy in (-1, 1):
            mb.box((0.0, sy * (L / 2 - 0.05), 0.11), (0.36, 0.06, 0.22), "M_IntMetal")
        for i in range(n):
            yy = -L / 2 + w * (i + 0.5)
            mb.box((0.03, yy, 0.37), (0.48, w - 0.06, 0.12), "M_IntFabricBlue")
            mb.box((-0.24, yy, 0.76), (0.1, w - 0.06, 0.68), "M_IntFabricBlue")
            mb.box((-0.225, yy, 1.0), (0.13, w - 0.1, 0.14), "M_IntFabricWhite")
        for i in range(n + 1):
            mb.box((0.02, -L / 2 + w * i, 0.62), (0.44, 0.05, 0.05), "M_IntMetal")


def _booth(mb, x, y, length, facing):
    """Upholstered bench (lounge booth) along y, sitting side towards local +x * facing."""
    with mb.at((x, y, 0.0), rot=0.0 if facing > 0 else 180.0):
        mb.box((0.0, 0, 0.22), (0.5, length, 0.44), "M_IntWoodDark")
        mb.box((0.02, 0, 0.49), (0.5, length - 0.04, 0.1), "M_IntFabricRed")
        mb.box((-0.2, 0, 0.82), (0.12, length - 0.04, 0.6), "M_IntFabricRed")


def _ship_table(mb, x, y, w, d, h=0.74, top="M_IntWood"):
    mb.box((x, y, h - 0.02), (w, d, 0.04), top)
    mb.cylinder((x, y, 0.0), 0.05, h - 0.04, "M_IntMetal", seg=8)
    mb.cylinder((x, y, 0.0), 0.25, 0.03, "M_IntMetal", seg=10)


def _ship_cam(aset, label, pos, target):
    """Preview camera in SHIP-LOCAL space: the preview renders the floating ferry mesh at the placement origin
    (in the game it is moved to FERRY_POS; cameras are preview-only)."""
    aset.special("camera", pos, target=target, lens=15.0, label=label)


def _ship_fixtures(mb, aset, W, x0, x1, hw, z, zc, exits=(), outlets=True, seed=0, skip_y=None):
    """What dress_room adds to a building, for a ship deck (everything in the floating mesh, z = deck level):
    sprinklers + smoke detector on the ceiling, outlets under the side windows, green exit signs over doors
    (exits: [(x, y, yaw)] points on the inner wall face, local -Y into the room)."""
    nx, ny = max(1, int((x1 - x0) / 3.0)), max(1, int(2 * hw / 3.0))
    for i in range(nx):
        for j in range(ny):
            sx_, sy_ = x0 + (x1 - x0) * (i + 0.5) / nx, -hw + 2 * hw * (j + 0.5) / ny
            if skip_y and abs(sy_) < skip_y:
                continue
            mb.cylinder((sx_, sy_, zc - 0.07), 0.008, 0.07, "M_DetSilver", seg=4, cap_top=False)   # sprinkler head
            mb.cylinder((sx_, sy_, zc - 0.075), 0.025, 0.006, "M_DetSilver", seg=6)
    DT.ceiling_fixture(mb, (x0 + x1) / 2 + 0.6, 0.4, zc, "smoke")
    if outlets:
        n = max(1, int((x1 - x0) / 3.2))
        for k in range(n):
            px = x0 + (x1 - x0) * (k + 0.5) / n
            DT.outlet(mb, px, -hw, z + 0.3, 180.0)
            DT.outlet(mb, px, hw, z + 0.3, 0.0)
    for ex, ey, yaw in exits:
        with mb.at((ex, ey, z + 2.38), rot=yaw):
            mb.box((0, -0.04, 0), (0.36, 0.08, 0.16), "M_DetSwitch")
            mb.box((0, -0.081, 0), (0.32, 0.004, 0.12), "M_DetExit")
        p = K.wall_point(ex, ey, yaw, 0.09, z + 2.345)
        aset.text("EXIT", W(p[0], p[1], p[2]), yaw, size=0.07, color=(1, 1, 1))


def _ferry_lower_deck(mb, aset, W, lights):
    """Cabin deck inside the hull (floor 0.2, ceiling 2.9, behind the portholes): a stair lobby under the saloon's
    cross aisle, side corridors along the engine casing, and 18 four-berth cabins (two portholes each). All of it
    is modelled into the floating ferry mesh."""
    z0, zc = LD_Z, LD_C
    h = zc - z0
    hx0, hy0, hx1, hy1 = LD_HOLE
    bounds = [LD_X0 + 2.4 * k for k in range(21)]                          # -31.2 .. 16.8 (between portholes)
    # floor / ceiling strips following the lining, hull lining with porthole openings, end bulkheads
    for xa, xb in zip(bounds, bounds[1:]):
        ya, yb = _ld_lining(xa), _ld_lining(xb)
        pieces = [(-1, 1)] if (xb <= hx0 or xa >= hx1) else [(-1, None), (None, 1)]
        for zz, mat, up in ((z0, "M_IntLinoleum", True), (zc, K.CEIL, False)):
            def q(x0, x1, y0a, y0b, y1a, y1b):
                pts = [(x0, y0a, zz), (x1, y0b, zz), (x1, y1b, zz), (x0, y1a, zz)]
                mb.poly(pts if up else pts[::-1], mat)
            if xb <= hx0 or xa >= hx1 or zz == z0:
                q(xa, xb, -ya, -yb, ya, yb)
            else:
                q(xa, xb, -ya, -yb, hy0, hy0)
                q(xa, xb, hy1, hy1, ya, yb)
                if xa < hx0:
                    q(xa, hx0, hy0, hy0, hy1, hy1)
                if xb > hx1:
                    q(hx1, xb, hy0, hy0, hy1, hy1)
        xp = (xa + xb) / 2
        v0, v1 = (PORT_Z - PORT_R - z0) / h, (PORT_Z + PORT_R - z0) / h
        u0, u1 = 0.5 - PORT_R / (xb - xa), 0.5 + PORT_R / (xb - xa)
        for sgn in (-1, 1):
            a, b = (xa, sgn * ya, z0), (xb, sgn * yb, z0)
            c, d = (xb, sgn * yb, zc), (xa, sgn * ya, zc)
            _holed_quad(mb, a, b, c, d, K.PLASTER_CREAM, [(u0, u1)], v0, v1, flip=sgn < 0)
            mb.box((xp, sgn * (ya - 0.12), z0 + 0.06), (xb - xa, 0.03, 0.12), K.TRIM_WOOD)          # skirting
    for xe, sgn in ((LD_X0, 1), (LD_X1, -1)):
        ye = _ld_lining(xe)
        pts = [(xe, -ye, z0), (xe, ye, z0), (xe, ye, zc), (xe, -ye, zc)]
        mb.poly(pts if sgn > 0 else pts[::-1], K.PLASTER_CREAM)
    # stair shaft between the cabin-deck ceiling and the saloon floor + the switchback stair
    for (p0, p1) in (((hx0, hy0), (hx1, hy0)), ((hx1, hy0), (hx1, hy1)), ((hx1, hy1), (hx0, hy1)), ((hx0, hy1), (hx0, hy0))):
        pts = [(p0[0], p0[1], zc), (p1[0], p1[1], zc), (p1[0], p1[1], F_DECK - 0.01), (p0[0], p0[1], F_DECK - 0.01)]
        mb.poly(pts[::-1], K.PLASTER_CREAM)
    zm = z0 + 11 * (F_DECK - z0) / 21
    mb.box_mm((hx0, hy0, zm - 0.12), (hx0 + 0.95, hy1, zm), "M_IntWoodDark", mats={"+z": "M_IntLinoleum"})
    K.stairs(mb, hx1 + 0.28, -0.5, z0, zm, 180.0, 0.95, mat="M_IntWood", riser="M_IntWoodDark", rail=K.TRIM_WOOD,
             rail_sides=(1, -1))
    K.stairs(mb, hx0 + 0.95, 0.5, zm, F_DECK, 0.0, 0.95, mat="M_IntWood", riser="M_IntWoodDark", rail=K.TRIM_WOOD,
             rail_sides=(1, -1))
    for yy in (hy0 + 0.03, hy1 - 0.03):
        K.railing(mb, [(hx0 + 0.02, yy), (hx0 + 0.95, yy)], zm, h=1.0, mat=K.TRIM_WOOD)
    K.railing(mb, [(hx1, -0.02), (hx1, hy0), (hx0, hy0), (hx0, hy1), (hx1, hy1)], F_DECK, h=1.0, mat=K.TRIM_WOOD)
    # walls: engine casing (|y| < 2.3) with the lobby cut out, corridor walls (|y| = 3.5) with cabin doorways,
    # partitions every two portholes
    lob0, lob1 = -7.2, -2.4
    kw = dict(trim_in=K.TRIM_WOOD, trim=K.TRIM_WOOD)
    for sgn in (-1, 1):
        for xa, xb in ((LD_X0, lob0), (lob1, LD_X1)):
            p0, p1 = ((xa, sgn * 2.3), (xb, sgn * 2.3)) if sgn > 0 else ((xb, sgn * 2.3), (xa, sgn * 2.3))
            K.wall(None, mb, p0, p1, z0, h, 0.1, K.PLASTER_CREAM, inner=K.PLASTER_CREAM, **kw)
            cab = [(c0, c0 + 4.8) for c0 in bounds[::2][:-1] if xa <= c0 < xb]
            ops = [K.Door((c0 + 2.4 - xa) if sgn < 0 else (xb - c0 - 2.4), 0.9, 2.05, None) for c0, c1 in cab]
            p0, p1 = ((xb, sgn * 3.5), (xa, sgn * 3.5)) if sgn > 0 else ((xa, sgn * 3.5), (xb, sgn * 3.5))
            K.wall(None, mb, p0, p1, z0, h, 0.1, K.PLASTER_CREAM, inner=K.PLASTER_CREAM, openings=ops, **kw)
        for xe in (lob0, lob1):
            K.wall(None, mb, (xe, -2.3), (xe, 2.3), z0, h, 0.1, K.PLASTER_CREAM, inner=K.PLASTER_CREAM)
            K.wall(None, mb, (xe, 2.3), (xe, -2.3), z0, h, 0.1, K.PLASTER_CREAM, inner=K.PLASTER_CREAM)
        for xb_ in bounds[::2]:
            if xb_ in (LD_X0, LD_X1):
                continue
            yl = _ld_lining(xb_)
            K.wall(None, mb, (xb_, sgn * 3.55), (xb_, sgn * (yl - 0.01)), z0, h, 0.1, K.PLASTER_CREAM,
                   inner=K.PLASTER_CREAM)
    # cabins: two bunks, porthole table with stools, lockers, coat hooks with dorm jackets, luggage
    rnd = random.Random(77)
    dorms = ("slifer", "ra", "obelisk", "slifer", "ra")
    blank = {"slifer": "M_IntFabricRed", "ra": "M_IntFabricYellow", "obelisk": "M_IntFabricBlue"}
    num = 0
    for sgn in (-1, 1):
        for c0 in bounds[::2][:-1]:
            if lob0 <= c0 < lob1:
                continue
            num += 1
            c1 = c0 + 4.8
            yl = _ld_lining(c0 + 2.4)
            dorm = dorms[num % len(dorms)]
            bc = blank[dorm]
            with mb.at((0.0, 0.0, z0)):
                yb = sgn * (yl - 1.05)
                for xbk in (c0 + 0.5, c1 - 0.5):                                  # two-tier ship bunks
                    with mb.at((xbk, yb, 0.0)):
                        for sx in (-1, 1):
                            for sy in (-1, 1):
                                mb.box((sx * 0.4, sy * 0.97, 0.9), (0.05, 0.05, 1.8), "M_IntWood")
                        for zb_, m_ in ((0.25, bc), (1.25, "M_IntFabricWhite")):
                            mb.box((0, 0, zb_), (0.85, 2.0, 0.12), "M_IntWoodDark")
                            mb.box((0, 0.05, zb_ + 0.12), (0.78, 1.85, 0.12), m_)
                            mb.box((0, -0.8, zb_ + 0.22), (0.5, 0.3, 0.1), "M_IntFabricWhite")
                mb.box((c0 + 2.4, sgn * (yl - 0.3), 0.72), (0.9, 0.55, 0.04), "M_IntWood")
                mb.box((c0 + 2.4, sgn * (yl - 0.1), 0.36), (0.08, 0.08, 0.72), "M_IntMetal")
                for dx in (-0.5, 0.5):
                    mb.cylinder((c0 + 2.4 + dx, sgn * (yl - 0.55), 0.0), 0.17, 0.45, "M_IntWoodDark", seg=8)
                DT.mug(mb, c0 + 2.2, sgn * (yl - 0.35), 0.74, seed=num)
                if num % 2:
                    DT.card_spread(mb, c0 + 2.5, sgn * (yl - 0.3), 0.742, 0.0, 4, seed=num)
                    DT.deck_box(mb, c0 + 2.8, sgn * (yl - 0.2), 0.74, 15.0, bc)
                else:
                    DT.book_stack(mb, c0 + 2.6, sgn * (yl - 0.3), 0.74, 0.0, 2, seed=num)
                K.lockers(mb, mb, None, c0 + 3.4, sgn * 3.8, 0.0 if sgn < 0 else 180.0, n=2, w=0.45, d=0.5, h=1.8)
                DT.coat_hooks(mb, c0 + 1.25, sgn * 3.5, 1.7, 0.0 if sgn < 0 else 180.0, n=2, dorm=dorm, seed=num,
                              jackets=1)
                if rnd.random() < 0.7:
                    mb.box((c0 + 1.5, sgn * (yl - 2.4), 0.25), (0.45, 0.25, 0.5), rnd.choice(K.FABRICS))
                mb.box((c0 + 2.4, sgn * (3.6 + 0.6), 0.004), (1.4, 0.9, 0.008), bc)                  # rug
                mb.box((c0 + 2.4, sgn * (yl - 1.0), h - 0.03), (0.6, 0.3, 0.03), K.PANEL_LIGHT)
                # timber wainscot round the cabin (below the portholes), shelf, mirror, picture
                px0, px1 = c0 + (0.1 if sgn < 0 else 0.0), c1 - (0.1 if sgn > 0 else 0.0)
                if sgn > 0:
                    loop = [((px0, 3.5), (px1, 3.5), [(c0 + 1.95 - px0, c0 + 2.85 - px0)]),
                            ((px1, 3.5), (px1, yl), []), ((px1, yl), (px0, yl), []), ((px0, yl), (px0, 3.5), [])]
                else:
                    loop = [((px0, -yl), (px1, -yl), []), ((px1, -yl), (px1, -3.5), []),
                            ((px1, -3.5), (px0, -3.5), [(px1 - c0 - 2.85, px1 - c0 - 1.95)]), ((px0, -3.5), (px0, -yl), [])]
                for a_, b_, g_ in loop:
                    K.wainscot(mb, a_, b_, 0.0, 0.95, "M_IntWood", cap=K.TRIM_WOOD, gaps=g_)
                mb.box((c0 + 2.4, sgn * (yl - 0.13), 1.75), (1.4, 0.24, 0.03), "M_IntWood")
                DT.book_stack(mb, c0 + 2.1, sgn * (yl - 0.13), 1.765, 90.0, 3, seed=num)
                for xpic in (px0 + 0.02, px1 - 0.02):
                    mb.box((xpic, sgn * (yl - 1.05), 2.15), (0.02, 0.5, 0.36), "M_IntWoodDark")
                    mb.box((xpic + (0.012 if xpic < c0 + 2.4 else -0.012), sgn * (yl - 1.05), 2.15), (0.004, 0.42, 0.28),
                           K.POSTERS[(num + int(xpic)) % 4])
            lights([(c0 + 2.4, sgn * (yl - 1.2))], z0 + 2.3, 1200.0, 4.5)
            mb.box((c0 + 3.15, sgn * 3.39, z0 + 1.7), (0.32, 0.02, 0.12), K.TRIM_WHITE)
            aset.text(f"CABIN {num:02d}", W(c0 + 3.15, sgn * 3.375, z0 + 1.67), 0.0 if sgn > 0 else 180.0,
                      size=0.055, color=(0.15, 0.1, 0.08))
    # corridors: panel lights, fire points, notices; lobby: benches, vending, deck plan, life-jacket locker
    with mb.at((0.0, 0.0, z0)):
        for sgn in (-1, 1):
            for xa, xb in ((LD_X0, lob0), (lob1, LD_X1)):
                x = xa + 2.4
                while x < xb - 1.0:
                    mb.box((x, sgn * 2.9, h - 0.03), (1.0, 0.25, 0.03), K.PANEL_LIGHT)
                    x += 4.8
                cab_x = [c0 + 2.4 for c0 in bounds[::2][:-1] if xa <= c0 < xb]
                if sgn > 0:
                    K.wainscot(mb, (xa, 2.4), (xb, 2.4), 0.0, 1.0, "M_IntWood", cap=K.TRIM_WOOD)
                    K.wainscot(mb, (xb, 3.4), (xa, 3.4), 0.0, 1.0, "M_IntWood", cap=K.TRIM_WOOD,
                               gaps=[(xb - cx - 0.5, xb - cx + 0.5) for cx in cab_x])
                else:
                    K.wainscot(mb, (xb, -2.4), (xa, -2.4), 0.0, 1.0, "M_IntWood", cap=K.TRIM_WOOD)
                    K.wainscot(mb, (xa, -3.4), (xb, -3.4), 0.0, 1.0, "M_IntWood", cap=K.TRIM_WOOD,
                               gaps=[(cx - xa - 0.5, cx - xa + 0.5) for cx in cab_x])
                mb.box_mm((xa, sgn * 2.47 - 0.025, 0.93), (xb, sgn * 2.47 + 0.025, 0.98), "M_IntTrimGold")   # handrail
                for k, (dy, rr, m) in enumerate(((0.12, 0.05, "M_IntMetal"), (0.26, 0.035, "M_AcademyRed"),
                                                 (0.38, 0.03, "M_IntMetal"))):                  # ceiling services
                    with mb.at((xa, sgn * (2.4 + dy), h - 0.08 - k * 0.02), rot_y=90):
                        mb.cylinder((0, 0, 0), rr, xb - xa, m, seg=6, cap_top=False, cap_bottom=False)
                mb.box_mm((xa + 0.2, sgn * 2.75 - 0.4, 0.003), (xb - 0.2, sgn * 2.75 + 0.4, 0.009), "M_IntCarpetBlue")
                for edge in (-0.42, 0.42):                       # anti-slip edge strips along the runner
                    mb.box_mm((xa + 0.2, sgn * 2.9 + edge - 0.04, 0.003), (xb - 0.2, sgn * 2.9 + edge + 0.04, 0.012),
                              "M_AcademyYellow")
                xx = xa + 0.6
                while xx < xb - 0.3:                             # deck beams overhead + framing ribs on the walls
                    mb.box((xx, sgn * 2.9, h - 0.11), (0.12, 1.0, 0.16), "M_IntWoodDark")
                    for wy in (2.42, 3.38):
                        if wy > 3 and any(abs(xx - cx) < 0.6 for cx in cab_x):
                            continue                             # never inside a cabin doorway
                        mb.box((xx, sgn * wy, (1.0 + h - 0.18) / 2), (0.08, 0.05, h - 1.18), "M_IntWood")
                    xx += 1.2
                for k, cx in enumerate(cab_x):
                    if k % 2 == 0:                                                              # hanging signs
                        mb.box((cx + 1.2, sgn * 2.9, h - 0.3), (0.05, 0.7, 0.18), K.TRIM_WHITE)
                        mb.box((cx + 1.2, sgn * 2.9, h - 0.15), (0.02, 0.02, 0.12), "M_IntMetal")
                for k, cx in enumerate(cab_x):                     # framed pictures opposite the doors, sconces
                    with mb.at((cx, sgn * 2.4, 1.6), rot=180.0 if sgn > 0 else 0.0):
                        mb.box((0, -0.012, 0), (0.62, 0.024, 0.78), "M_IntWoodDark")
                        mb.box((0, -0.026, 0), (0.52, 0.006, 0.68), K.POSTERS[(k + (sgn > 0)) % 4])
                        mb.box((0.05, -0.03, -0.05), (0.3, 0.004, 0.3), ("M_IntFabricGreen", "M_IntTrimWhite")[k % 2])
                    for dxs in (-1.2, 1.2):
                        with mb.at((cx + dxs, sgn * 2.4, 1.9), rot=180.0 if sgn > 0 else 0.0):
                            mb.box((0, -0.05, 0), (0.14, 0.1, 0.06), "M_IntTrimGold")
                            mb.box((0, -0.09, 0.09), (0.16, 0.16, 0.2), K.GLOW)
                xm = (xa + xb) / 2
                with mb.at((xm, sgn * 2.4, 1.2), rot=180.0 if sgn > 0 else 0.0):
                    mb.box((0, -0.06, 0.0), (0.5, 0.12, 0.7), "M_AcademyRed")                 # fire-hose cabinet
                    mb.box((0, -0.122, 0.05), (0.4, 0.004, 0.5), "M_GlassClear")
                _wall_map(mb, aset, xm - 2.0, sgn * 2.4, 1.2, 180.0 if sgn > 0 else 0.0, 0.7, 0.5, None, seed=int(xm))
            lights([(x_, sgn * 2.9) for x_ in (-24.0, -12.0, 2.4, 12.0)], z0 + 2.4, 1500.0, 6.0)
            for xb_ in ((-6.0, -3.6) if sgn < 0 else (-3.6,)):                                 # lobby benches
                mb.box((xb_, sgn * (_ld_lining(xb_) - 0.3), 0.42), (1.6, 0.45, 0.08), "M_IntFabricBlue")
                mb.box((xb_, sgn * (_ld_lining(xb_) - 0.1), 0.25), (1.6, 0.1, 0.5), "M_IntWoodDark")
        # purser's desk (starboard), drinks machine, waiting table with a card game, luggage rack, plants
        K.counter(mb, -6.9, 4.9, -4.9, 5.5, h=1.0, body=BLUE, top=K.TRIM_WHITE)
        mb.box_mm((-6.9, 6.4, 0.0), (-4.9, _ld_lining(-6.0) - 0.02, 0.9), "M_IntWoodDark")
        mb.cylinder((-5.9, 6.0, 0.0), 0.2, 0.5, "M_IntMetal", seg=8)
        mb.box((-5.9, 6.0, 0.55), (0.45, 0.45, 0.08), "M_IntFabricNavy")
        DT.paper_stack(mb, -6.4, 5.2, 1.0, 10.0, 4, seed=3)
        mb.box((-5.4, 5.25, 1.04), (0.3, 0.2, 0.08), "M_IntBlack")
        mb.box((-5.4, 5.32, 1.22), (0.32, 0.03, 0.22), "M_IntScreen")
        DT.mug(mb, -5.0, 5.3, 1.0, seed=8)
        mb.box_mm((-3.3, 4.0, 0.0), (-2.5, 4.9, 1.8), "M_IntFabricBlue")                      # drinks machine
        mb.box_mm((-3.31, 4.1, 0.7), (-3.29, 4.8, 1.6), "M_IntGlassClear")
        for k in range(4):
            for j in range(3):
                mb.cylinder((-3.15, 4.2 + k * 0.17, 0.75 + j * 0.3), 0.035, 0.14, K.FABRICS[(k + j) % 7], seg=6)
        mb.cylinder((-4.6, -4.3, 0.0), 0.06, 0.72, "M_IntMetal", seg=8)
        mb.cylinder((-4.6, -4.3, 0.72), 0.45, 0.04, "M_IntWood", seg=16)
        for a in (0.0, 120.0, 240.0):
            r_ = math.radians(a)
            mb.cylinder((-4.6 + math.cos(r_) * 0.75, -4.3 + math.sin(r_) * 0.75, 0.0), 0.18, 0.45, "M_IntFabricRed", seg=8)
        DT.card_spread(mb, -4.6, -4.3, 0.762, 30.0, 5, seed=21)
        DT.deck_box(mb, -4.35, -4.1, 0.76, 0.0, "M_IntFabricYellow")
        DT.duel_disk(mb, -4.9, -4.55, 0.76, 60.0)
        with mb.at((-3.0, -2.2, 0.0), rot=90.0):                                              # luggage rack
            for zz in (0.3, 1.0):
                mb.box((0, 0, zz), (1.4, 0.5, 0.04), "M_IntMetal")
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.box((sx * 0.68, sy * 0.23, 0.7), (0.04, 0.04, 1.4), "M_IntMetal")
            for k, c in enumerate(("M_IntFabricRed", "M_IntFabricNavy", "M_IntFabricGreen")):
                mb.box((-0.42 + k * 0.42, 0, 0.32 + 0.22), (0.36, 0.22, 0.44), c)
            mb.box((0.2, 0, 1.02 + 0.15), (0.6, 0.4, 0.3), "M_IntWoodDark")
        for (px_, py_) in ((-6.85, -6.2), (-6.75, 3.5)):
            mb.cylinder((px_, py_, 0.0), 0.22, 0.45, "M_IntWoodDark", seg=10)
            mb.sphere((px_, py_, 0.95), 0.45, "M_IntFabricGreen", seg=10, rings=6)
        for k, yy in enumerate((-5.6, 3.9)):
            K.poster(mb, aset, lob0 + (0.1 if yy < 0 else 0.0), yy, 1.6, 90.0, 0.6, 0.85, K.POSTERS[k + 1])
        mb.box((-5.9, 5.2, h - 0.35), (1.4, 0.06, 0.3), BLUE)
        for sy in (-0.6, 0.6):
            mb.box((-5.9 + sy, 5.2, h - 0.1), (0.02, 0.02, 0.2), "M_IntMetal")
        mb.box_mm((-7.1, -4.6, 0.0), (-6.25, -3.8, 1.8), "M_IntFabricRed")                      # vending machine
        mb.box_mm((-6.26, -4.5, 0.75), (-6.24, -3.9, 1.65), "M_IntScreen")
        mb.box_mm((-7.1, 1.6, 0.0), (-6.5, 2.9, 0.9), ORANGE)                                  # life-jacket locker
        _wall_map(mb, aset, lob1 - 0.1, 4.6, 1.0, -90.0, 1.0, 0.7, None, seed=12)
        mb.box_mm((lob0 + 0.1, -2.2, 1.1), (lob0 + 0.11, -1.25, 1.8), "M_IntCork")
        for k in range(3):
            mb.box_mm((lob0 + 0.11, -2.1 + k * 0.28, 1.25 + (k % 2) * 0.15), (lob0 + 0.115, -1.9 + k * 0.28,
                       1.55 + (k % 2) * 0.15), ("M_IntPaper", "M_IntPoster1", "M_IntPaper")[k])
        for xx in (-5.0, -3.0):
            mb.box((xx, -4.2, h - 0.03), (1.0, 0.3, 0.03), K.PANEL_LIGHT)
            mb.box((xx, 4.2, h - 0.03), (1.0, 0.3, 0.03), K.PANEL_LIGHT)
        mb.cylinder((-2.65, -2.5, 0.0), 0.09, 0.6, "M_AcademyRed", seg=8)
        _ship_fixtures(mb, aset, W, LD_X0, LD_X1, 6.7, 0.0, h, exits=[(lob0 + 0.1, 1.65, 90.0), (lob1 - 0.1, -1.65, -90.0)],
                       outlets=False, seed=4, skip_y=2.3)
    aset.text("BOOSTER PACKS", W(-6.23, -4.2, z0 + 1.72), -90.0, size=0.08, color=(1, 1, 1), emissive=True)
    aset.text("FORWARD CABINS", W(lob1 - 0.12, 1.65, z0 + 2.0), -90.0, size=0.08, color=(0.1, 0.25, 0.62))
    aset.text("AFT CABINS", W(lob0 + 0.12, -1.65, z0 + 2.0), 90.0, size=0.08, color=(0.1, 0.25, 0.62))
    aset.text("LIFE JACKETS", W(-6.48, 2.25, z0 + 0.6), 90.0, size=0.07, color=(1, 1, 1))
    aset.text("PURSER", W(-5.9, 5.165, z0 + h - 0.38), 0.0, size=0.12, color=(1, 1, 1))
    aset.text("INFORMATION", W(-5.9, 4.88, z0 + 0.75), 0.0, size=0.08, color=(1, 1, 1))
    aset.text("NOTICES", W(lob0 + 0.12, -1.72, z0 + 1.88), 90.0, size=0.06, color=(0.2, 0.12, 0.06))
    lights([(-5.0, 0.0)], z0 + 2.4, 2500.0, 7.0)
    _ship_cam(aset, "ferry_lower_lobby", (-4.4, 6.1, z0 + 1.7), (-5.5, -3.0, z0 + 0.8))
    _ship_cam(aset, "ferry_lower_cabin", (-14.4, -3.75, z0 + 1.65), (-12.4, -6.4, z0 + 0.7))
    _ship_cam(aset, "ferry_lower_corridor", (-8.0, 2.9, z0 + 1.65), (-28.0, 2.9, z0 + 0.9))


def _ferry_interior(mb, aset, d1, d2, br):
    """Passenger saloon (deck 1), sky lounge with duel tables (deck 2) and the bridge (deck 3). Everything is
    part of the floating ferry mesh so it bobs with the hull (catalog props would not)."""
    fx, fy, fz = FERRY_POS

    def W(x, y, z):
        return (fx + x, fy + y, fz + z)

    def lights(pts, z, intensity=3000.0, radius=9.0):
        for x, y in pts:
            aset.light(W(x, y, z), (1.0, 0.88, 0.7), intensity, radius, night_only=False)

    # ---------------------------------------------------------------- deck 1: passenger saloon
    z = F_DECK
    hx0, hy0, hx1, hy1 = LD_HOLE                    # stairwell down to the cabin deck
    for x0_, y0_, x1_, y1_ in ((-23.8, -5.4, 10.5, hy0), (-23.8, hy1, 10.5, 5.4), (-23.8, hy0, hx0, hy1),
                               (hx1, hy0, 10.5, hy1)):
        mb.box_mm((x0_, y0_, z - 0.01), (x1_, y1_, z + 0.008), "M_IntCarpetBlue", skip=("-z",))
    mb.prism(_rounded_rect(10.5, 10.5, 5.4, 3.6)[1:-1], z - 0.01, z + 0.008, "M_IntCarpetBlue", cap_bottom=False)
    for xa_, xb_ in ((-23.8, hx0), (hx1, 10.0)):
        mb.box_mm((xa_, -0.6, z + 0.008), (xb_, 0.6, z + 0.012), "M_IntCarpetRed")
    _ferry_lower_deck(mb, aset, W, lights)
    mb.poly([(x, y, 6.95) for x, y in reversed(d1)], K.CEIL)
    for yy in (-2.2, 2.2):
        mb.box_mm((-22.5, yy - 0.12, 6.93), (9.5, yy + 0.12, 6.95), K.PANEL_LIGHT)
    K.wainscot(mb, (-23.8, -5.4), (10.5, -5.4), z, 0.92, "M_IntWoodPanel", cap=K.TRIM_WOOD, gaps=[(18.1, 19.5)])
    K.wainscot(mb, (10.5, 5.4), (-23.8, 5.4), z, 0.92, "M_IntWoodPanel", cap=K.TRIM_WOOD, gaps=[(14.8, 16.2)])
    with mb.at((0.0, 0.0, z)):
        for k in range(13):
            x = -21.8 + k * 1.0
            for s in (-1, 1):
                _seat_block(mb, x, s * 1.85, 4)
                _seat_block(mb, x, s * 4.43, 3)
        for k in range(6):
            x = -1.5 + k * 1.0
            for s in (-1, 1):
                _seat_block(mb, x, s * 1.85, 4)
                _seat_block(mb, x, s * 4.43, 3)
        # snack bar in the bow
        K.counter(mb, 7.0, -2.2, 7.7, 2.2, h=1.0, body="M_IntWood", top=K.TRIM_WHITE)
        mb.box_mm((9.3, -2.0, 0.0), (9.7, 2.0, 1.5), "M_IntWoodDark")
        for k in range(14):
            mb.cylinder((9.5, -1.8 + k * 0.27, 1.5), 0.04, 0.22, K.FABRICS[k % 7], seg=6)
            mb.cylinder((9.5, -1.75 + k * 0.27, 0.95), 0.045, 0.2, K.FABRICS[(k + 3) % 7], seg=6)
        mb.box_mm((9.3, -2.0, 0.92), (9.7, 2.0, 0.95), "M_IntWood")
        for yy in (-1.5, -0.5, 0.5, 1.5):
            mb.cylinder((6.6, yy, 0.0), 0.17, 0.7, "M_IntMetal", seg=8)
            mb.cylinder((6.6, yy, 0.7), 0.2, 0.06, "M_IntFabricRed", seg=10)
        mb.box((8.3, 0.0, 2.55), (0.06, 2.2, 0.5), "M_IntBlack")
        for s in (-1, 1):
            mb.box((8.3, s * 0.9, 2.85), (0.02, 0.02, 0.3), "M_IntMetal")
        # TV screens over the cross aisle, life jacket chests on the aft wall, luggage racks
        for s in (-1, 1):
            mb.box((-7.0, s * 2.2, 2.45), (0.08, 1.0, 0.6), "M_IntBlack")
            mb.box((-7.05, s * 2.2, 2.45), (0.01, 0.9, 0.5), "M_IntScreen")
            mb.box((-7.0, s * 2.2, 2.85), (0.03, 0.03, 0.2), "M_IntMetal")
            ya, yb = sorted((s * 2.4, s * 4.4))
            mb.box_mm((-23.8, ya, 0.0), (-23.3, yb, 0.9), ORANGE)
            mb.box_mm((-23.82, ya, 0.86), (-23.28, yb, 0.92), TRIM)
            for xa, xb in ((-22.6, -7.6), (-3.0, 9.5)):
                ya, yb = sorted((s * 5.4, s * 4.95))
                mb.box_mm((xa, ya, 2.48), (xb, yb, 2.52), "M_IntMetal")
                mb.box_mm((xa, s * 4.95 - 0.02, 2.48), (xb, s * 4.95 + 0.02, 2.62), "M_IntMetal")
    for s in (-1, 1):
        aset.text("DUEL ACADEMY ISLAND - ETA 10:00", W(-7.07, s * 2.2, z + 2.42), -90.0, size=0.07,
                  color=(1, 1, 1), emissive=True)
        aset.text("LIFE JACKETS", W(-23.27, s * 3.4, z + 0.5), 90.0, size=0.14, color=(1, 1, 1))
    aset.text("SNACK BAR", W(8.26, 0.0, z + 2.5), -90.0, size=0.24, color=(1.0, 0.85, 0.3), emissive=True)
    lights([(-19.0, 0.0), (-12.0, 0.0), (-5.0, 0.0), (2.0, 0.0), (8.0, 0.0)], z + 2.6)
    with mb.at((0.0, 0.0, 0.0)):
        _ship_fixtures(mb, aset, W, -23.8, 10.5, 5.4, z, 6.95, exits=[(-23.8, 0.0, 90.0), (GANG_SHIP_X, -5.4, 180.0),
                                                                       (GANG_SHIP_X, 5.4, 0.0)], outlets=False, seed=1)
    rs = random.Random(91)
    for k in range(9):                                                                  # passengers' things
        sx = rs.choice((-1, 1))
        px, py = -21.8 + rs.randint(0, 12) * 1.0 + 0.03, sx * (1.85 + rs.choice((-0.55, 0.0, 0.55)))
        if rs.random() < 0.5:
            DT.paper_stack(mb, px, py, z + 0.43, rs.uniform(0, 90), 3, seed=k)
        else:
            mb.box((px, py, z + 0.55), (0.3, 0.38, 0.24), rs.choice(K.FABRICS))
    _ship_cam(aset, "ferry_saloon", (-23.0, 3.4, z + 1.8), (6.0, -1.5, z + 0.8))

    # ---------------------------------------------------------------- deck 2: sky lounge (duel tables, cafe)
    z = 7.3
    mb.prism(_rounded_rect(-14.8, 9.5, 5.4, 3.3), z - 0.01, z + 0.006, "M_IntWoodFloor", cap_bottom=False)
    mb.poly([(x, y, 9.95) for x, y in reversed(d2)], K.CEIL)
    with mb.at((0.0, 0.0, z)):
        for x in (-8.5, -3.0):
            mb.box((x, 0, 0.76), (2.0, 1.0, 0.05), "M_IntWoodDark")
            for sx in (-1, 1):
                mb.box((x + sx * 0.85, 0, 0.37), (0.1, 0.8, 0.74), "M_IntWoodDark")
            mb.box((x, 0, 0.79), (1.85, 0.85, 0.01), "M_IntChalkboard")
            for sx in (-1, 1):
                for k in range(5):
                    mb.box((x + sx * 0.6, -0.32 + k * 0.16, 0.797), (0.13, 0.1, 0.005), "M_IntPaper")
                mb.box((x + sx * 0.35, 0.0, 0.797), (0.13, 0.1, 0.005), "M_IntPoster1")
                mb.cylinder((x + sx * 1.35, 0, 0.0), 0.2, 0.62, "M_IntMetal", seg=8)
                mb.cylinder((x + sx * 1.35, 0, 0.62), 0.24, 0.07, "M_IntFabricBlue", seg=12)
        for s in (-1, 1):
            for x in (-12.6, -6.0, 0.6):
                _ship_table(mb, x, s * 4.75, 0.8, 0.7)
                _booth(mb, x - 1.0, s * 4.75, 1.3, 1)
                _booth(mb, x + 1.0, s * 4.75, 1.3, -1)
        # cafe bar in the bow
        mb.box_mm((8.4, -2.6, 0.0), (9.0, 2.6, 1.05), "M_IntWood")
        mb.box_mm((8.35, -2.65, 1.05), (9.05, 2.65, 1.1), K.TRIM_WHITE)
        for yy in (-1.8, -0.6, 0.6, 1.8):
            mb.cylinder((7.8, yy, 0.0), 0.16, 0.72, "M_IntMetal", seg=8)
            mb.cylinder((7.8, yy, 0.72), 0.2, 0.06, "M_IntFabricYellow", seg=10)
        for k in range(6):
            mb.cylinder((8.75, -2.2 + k * 0.85, 1.1), 0.05, 0.12, "M_IntTrimWhite", seg=8)
        for s in (-1, 1):                                                              # potted palms
            mb.cylinder((-14.3, s * 4.9, 0.0), 0.25, 0.5, "M_IntWoodDark", seg=10)
            mb.sphere((-14.3, s * 4.9, 1.0), 0.5, "M_IntFabricGreen", seg=10, rings=6)
    aset.text("SKY LOUNGE", W(-14.78, 2.2, z + 2.0), 90.0, size=0.2, color=(1.0, 0.85, 0.3))
    aset.text("DUEL TABLES - PLEASE RETURN YOUR CARDS", W(-14.78, -2.4, z + 2.0), 90.0, size=0.1, color=(1, 1, 1))
    lights([(-11.0, 0.0), (-5.5, 0.0), (0.5, 0.0), (6.5, 0.0)], z + 2.3)
    with mb.at((0.0, 0.0, z)):
        # ceiling: varnished beams (skip the light panels) and pendant shades over the booths
        bx = -13.6
        while bx < 9.2:
            if all(abs(bx - lx) > 0.75 for lx in (-11.0, -5.5, 0.5, 6.5)):
                mb.box((bx, 0.0, 2.6), (0.14, 10.8, 0.1), "M_IntWood")
            bx += 1.7
        mb.box_mm((-14.8, -0.08, 2.58), (9.5, 0.08, 2.65), "M_IntWoodDark")
        for s in (-1, 1):
            for x in (-12.6, -6.0, 0.6):
                mb.cylinder((x, s * 4.75, 2.1), 0.01, 0.55, "M_IntBlack", seg=4)
                mb.cylinder((x, s * 4.75, 1.92), 0.22, 0.18, "M_IntTrimWhite", seg=12, radius_top=0.08, cap_bottom=False)
                mb.cylinder((x, s * 4.75, 1.91), 0.12, 0.02, K.GLOW, seg=8)
                # table settings: mugs, a card game, menu tent
                DT.mug(mb, x - 0.22, s * 4.75 - 0.18, 0.74, seed=int(x * 3) + s)
                DT.mug(mb, x + 0.22, s * 4.75 + 0.15, 0.74, seed=int(x * 5) - s)
                DT.card_spread(mb, x, s * 4.75 - 0.05, 0.742, 90.0, 4, seed=int(x) + s)
                with mb.at((x, s * 4.75 + 0.25, 0.74)):
                    mb.box((0, 0, 0.06), (0.12, 0.05, 0.12), "M_IntPoster3")
        # duel tables: decks, duel disks, life-point notepads
        for x in (-8.5, -3.0):
            for sx in (-1, 1):
                DT.deck_box(mb, x + sx * 0.75, -0.3, 0.795, 10.0 * sx, "M_IntFabricRed" if sx < 0 else "M_IntFabricBlue")
                mb.box((x + sx * 0.6, 0.38, 0.8), (0.1, 0.14, 0.006), "M_IntPaper")
        # cafe: espresso machine, cake dome, cups, back bar with shelves, hanging menu
        mb.box((8.7, -1.9, 1.3), (0.4, 0.5, 0.4), "M_IntMetal")
        mb.box((8.55, -1.9, 1.2), (0.12, 0.3, 0.02), "M_IntBlack")
        mb.cylinder((8.7, 1.2, 1.1), 0.2, 0.02, "M_IntTrimWhite", seg=12)
        mb.cylinder((8.7, 1.2, 1.12), 0.08, 0.06, "M_IntFabricPink", seg=10)
        mb.sphere((8.7, 1.2, 1.12), 0.18, "M_IntGlassClear", seg=10, rings=5, hemi=True)
        mb.box_mm((9.9, -1.8, 0.0), (10.5, 1.8, 0.9), "M_IntWoodDark")
        mb.box_mm((9.88, -1.82, 0.9), (10.52, 1.82, 0.94), K.TRIM_WHITE)
        for zz in (1.35, 1.75):
            mb.box_mm((10.2, -1.8, zz - 0.03), (10.5, 1.8, zz), "M_IntWood")
            for k in range(12):
                mb.cylinder((10.35, -1.65 + k * 0.3, zz), 0.045, 0.1 + (k % 3) * 0.04,
                            ("M_IntTrimWhite", "M_IntFabricRed", "M_IntGlassClear", "M_IntFabricGreen")[k % 4], seg=8)
        mb.box((9.0, 0.0, 2.15), (0.06, 2.2, 0.55), "M_IntBlack")
        for sy in (-0.9, 0.9):
            mb.box((9.0, sy, 2.52), (0.02, 0.02, 0.2), "M_IntMetal")
        # stern wall: booster-pack vending machine, notice board + island chart, extinguisher
        mb.box_mm((-14.8, -3.65, 0.0), (-14.0, -2.75, 1.8), "M_IntFabricRed")
        mb.box_mm((-14.01, -3.5, 0.75), (-13.99, -2.9, 1.65), "M_IntScreen")
        mb.box_mm((-14.02, -3.55, 0.15), (-13.98, -2.85, 0.4), "M_IntBlack")
        _wall_map(mb, aset, -14.8, 3.1, 0.9, 90.0, 1.0, 0.75, None, seed=5)
        mb.box_mm((-14.8, 1.55, 0.95), (-14.77, 2.35, 1.65), "M_IntCork")
        for k in range(4):
            mb.box_mm((-14.77, 1.62 + k * 0.18, 1.2 + (k % 2) * 0.2), (-14.765, 1.76 + k * 0.18, 1.4 + (k % 2) * 0.2),
                      ("M_IntPaper", "M_IntPoster1", "M_IntPaper", "M_IntPoster3")[k])
        mb.cylinder((-14.6, -1.4, 0.0), 0.09, 0.6, "M_AcademyRed", seg=8)
        mb.cylinder((-14.6, -1.4, 0.6), 0.03, 0.1, "M_IntBlack", seg=6)
        _ship_fixtures(mb, aset, W, -14.8, 9.5, 5.4, 0.0, 2.65, exits=[(-14.8, 0.0, 90.0)], outlets=False, seed=2)
    aset.text("BOOSTER PACKS", W(-13.98, -3.2, z + 1.72), 90.0, size=0.09, color=(1, 1, 1), emissive=True)
    aset.text("NOTICES", W(-14.75, 1.95, z + 1.68), 90.0, size=0.07, color=(0.2, 0.12, 0.06))
    aset.text("TODAY: CURRY BREAD 150", W(8.96, 0.0, z + 2.25), -90.0, size=0.08, color=(1.0, 0.9, 0.4), emissive=True)
    aset.text("ISLAND CAFE", W(8.96, 0.0, z + 2.05), -90.0, size=0.11, color=(1, 1, 1), emissive=True)
    for x in (-11.0, -5.5, 0.5, 6.5):
        mb.box((x, 0.0, 9.93), (1.2, 0.3, 0.03), K.PANEL_LIGHT)
    _ship_cam(aset, "ferry_lounge", (-14.4, -4.0, z + 1.75), (8.0, 2.0, z + 0.7))

    # ---------------------------------------------------------------- deck 3: bridge
    z = 10.3
    mb.prism(_rounded_rect(4.2, 10.0, 5.8, 2.4), z - 0.01, z + 0.006, "M_IntLinoleum", cap_bottom=False)
    mb.poly([(x, y, 12.95) for x, y in reversed(br)], K.CEIL)
    with mb.at((0.0, 0.0, z)):
        # helm console across the windows
        mb.box_mm((10.5, -3.4, 0.0), (11.15, 3.4, 0.95), STEEL)
        with mb.at((10.75, 0.0, 0.95), rot_y=-20.0):
            mb.box((0, 0, 0.05), (0.7, 6.8, 0.1), "M_IntBlack")
            for k in range(5):
                mb.box((0, -2.6 + k * 1.3, 0.105), (0.4, 0.7, 0.01), "M_IntScreen")
            for k in range(12):
                mb.box((0.25, -2.9 + k * 0.5, 0.11), (0.05, 0.05, 0.02), K.FABRICS[k % 5])
        # wheel on its pedestal, telegraph, binnacle
        mb.cylinder((9.8, 0.0, 0.0), 0.18, 0.95, STEEL, seg=10)
        with mb.at((9.68, 0.0, 1.2), rot_y=90.0):
            mb.torus((0, 0, 0), 0.38, 0.035, "M_IntWoodDark", seg=16, tube_seg=5)
            for k in range(8):
                a = math.tau * k / 8
                mb.beam((0, 0, 0), (math.cos(a) * 0.48, math.sin(a) * 0.48, 0), 0.04, 0.04, "M_IntWoodDark")
            mb.cylinder((0, 0, -0.06), 0.07, 0.14, K.TRIM_GOLD, seg=8)
        for yy, top in ((1.3, K.TRIM_GOLD), (-1.3, K.TRIM_GOLD)):
            mb.cylinder((9.9, yy, 0.0), 0.12, 1.0, "M_IntWoodDark", seg=8)
            mb.sphere((9.9, yy, 1.12), 0.17, top, seg=10, rings=6)
        # captain's chair
        mb.cylinder((8.3, 0.0, 0.0), 0.1, 0.6, STEEL, seg=8)
        mb.box((8.3, 0, 0.66), (0.6, 0.6, 0.14), "M_IntFabricNavy")
        mb.box((7.98, 0, 1.05), (0.12, 0.6, 0.7), "M_IntFabricNavy")
        for s in (-1, 1):
            mb.box((8.3, s * 0.33, 0.85), (0.5, 0.06, 0.08), STEEL)
        # chart table + radio station along the aft wall
        mb.box_mm((4.3, -5.0, 0.0), (5.4, -3.4, 0.92), "M_IntWood")
        mb.box_mm((4.35, -4.9, 0.92), (5.35, -3.5, 0.925), "M_IntPaper")
        mb.box_mm((4.45, -4.8, 0.925), (5.25, -3.6, 0.93), "M_IntPoster2")
        mb.box_mm((4.3, 3.4, 0.0), (5.0, 5.2, 0.78), STEEL)
        mb.box_mm((4.35, 3.6, 0.78), (4.75, 4.4, 1.1), "M_IntBlack")
        mb.box_mm((4.74, 3.7, 0.86), (4.76, 4.3, 1.02), "M_IntScreen")
        mb.box((4.6, 4.8, 0.85), (0.12, 0.2, 0.08), "M_IntBlack")
        mb.box_mm((4.2, 3.4, 1.5), (4.45, 5.2, 1.55), "M_IntWood")                 # shelf with logbooks
        for k in range(8):
            mb.box((4.32, 3.55 + k * 0.2, 1.67), (0.2, 0.06, 0.24), K.FABRICS[k % 7])
    with mb.at((0.0, 0.0, z)):
        # overhead panel above the helm, radar pedestal, officer's chair, floor mat
        for sy in (-2.4, 2.4):
            mb.box((10.35, sy, 2.54), (0.04, 0.04, 0.22), "M_IntMetal")
        mb.box_mm((10.0, -2.6, 2.25), (10.7, 2.6, 2.43), STEEL)
        for k in range(20):
            mb.box((10.0 - 0.005, -2.4 + k * 0.25, 2.34), (0.01, 0.06, 0.04), K.FABRICS[k % 6])
        for k in range(4):
            mb.box((10.0 - 0.006, -1.95 + k * 1.3, 2.3), (0.01, 0.4, 0.06), "M_IntScreen")
        mb.box_mm((9.35, -3.3, 0.0), (10.45, 3.3, 0.012), "M_IntBlack")
        mb.cylinder((9.2, -3.5, 0.0), 0.2, 0.95, STEEL, seg=10)
        with mb.at((9.2, -3.5, 1.05), rot_y=25.0):
            mb.box((0, 0, 0), (0.55, 0.55, 0.2), STEEL)
            mb.cylinder((-0.0, 0.0, 0.1), 0.2, 0.012, "M_IntScreen", seg=16)
        mb.cylinder((8.3, -2.1, 0.0), 0.1, 0.6, STEEL, seg=8)
        mb.box((8.3, -2.1, 0.66), (0.55, 0.55, 0.12), "M_IntFabricBlue")
        mb.box((8.02, -2.1, 1.0), (0.1, 0.55, 0.6), "M_IntFabricBlue")
        # chart table: drawers, chart work (rulers, dividers), logbook, binoculars, coffee
        for k in range(4):
            mb.box_mm((5.4, -4.9 + k * 0.38, 0.1), (5.41, -4.6 + k * 0.38, 0.8), "M_IntWoodDark")
        mb.box((4.85, -4.2, 0.935), (0.06, 0.6, 0.008), "M_IntTrimWhite")
        mb.beam((4.6, -4.5, 0.94), (4.75, -4.3, 0.94), 0.01, 0.01, "M_IntMetal")
        mb.box((4.6, -3.65, 0.95), (0.22, 0.3, 0.035), "M_IntFabricNavy")
        DT.mug(mb, 5.2, -3.6, 0.93, seed=7)
        for sx in (-0.04, 0.04):
            with mb.at((5.15, -4.75 + sx, 0.97), rot_y=90):
                mb.cylinder((0, 0, -0.08), 0.03, 0.16, "M_IntBlack", seg=8)
        # radio corner: headphones, clock + barometer on the aft wall, deck box + duel disk of the mate
        mb.torus((4.7, 4.75, 0.82), 0.08, 0.015, "M_IntBlack", seg=10, tube_seg=4)
        for k, (yy, m) in enumerate(((3.0, "M_IntTrimWhite"), (2.4, "M_IntTrimGold"))):
            with mb.at((4.24, yy, 1.85), rot_y=90):
                mb.cylinder((0, 0, -0.03), 0.14, 0.04, "M_IntWoodDark", seg=14)
                mb.cylinder((0, 0, 0.01), 0.11, 0.01, m, seg=14)
        DT.deck_box(mb, 4.6, 3.55, 0.78, 20.0, "M_IntFabricYellow")
        # aft wall: flag locker, life jackets, notice board, extinguisher
        mb.box_mm((4.2, 0.9, 0.9), (4.6, 2.0, 1.8), "M_IntWood")
        for i in range(4):
            for j in range(3):
                mb.box((4.61, 1.0 + i * 0.27 + 0.1, 1.05 + j * 0.28), (0.02, 0.18, 0.12),
                       K.FABRICS[(i + j * 2) % 7])
        for k in range(3):
            mb.box((4.3, -1.0 - k * 0.42, 1.35), (0.18, 0.36, 0.55), ORANGE)
            mb.box((4.22, -1.0 - k * 0.42, 1.64), (0.04, 0.04, 0.04), "M_IntMetal")
        mb.box_mm((4.2, -3.3, 1.0), (4.23, -2.4, 1.7), "M_IntCork")
        for k in range(3):
            mb.box_mm((4.23, -3.2 + k * 0.28, 1.1 + (k % 2) * 0.15), (4.235, -3.0 + k * 0.28, 1.4 + (k % 2) * 0.15),
                      ("M_IntPaper", "M_IntPoster2", "M_IntPaper")[k])
        mb.cylinder((4.4, -0.85, 0.0), 0.09, 0.6, "M_AcademyRed", seg=8)
        # low chart cabinets under the side windows with an Aldis signal lamp and the log books
        mb.box_mm((5.6, -5.8, 0.0), (7.9, -5.3, 0.9), "M_IntWood")
        mb.box_mm((5.6, 5.3, 0.0), (9.6, 5.8, 0.9), "M_IntWood")
        mb.cylinder((7.3, -5.55, 0.9), 0.12, 0.25, "M_IntBlack", seg=10)
        mb.cylinder((7.3, -5.55, 1.15), 0.1, 0.02, "M_IntTrimGold", seg=10)
        DT.book_stack(mb, 6.2, -5.55, 0.9, 0.0, 4, seed=3)
        DT.book_stack(mb, 8.8, 5.55, 0.9, 90.0, 3, seed=4)
        DT.paper_stack(mb, 6.6, 5.55, 0.9, 0.0, 5, seed=5)
        # ECDIS / navigation console island, rubber floor matting, ceiling beams + cable tray
        mb.box_mm((6.6, 1.3, 0.0), (7.4, 3.1, 0.9), STEEL)
        with mb.at((7.0, 2.2, 0.9), rot_y=15.0):
            mb.box((0, 0, 0.02), (0.7, 1.7, 0.04), "M_IntBlack")
            for k in range(2):
                mb.box((0, -0.42 + k * 0.84, 0.045), (0.5, 0.7, 0.006), "M_IntScreen")
        mb.box_mm((5.2, -1.6, 0.006), (9.35, 1.1, 0.014), "M_IntBlack")
        for bxx in (5.5, 7.6, 9.6):
            mb.box((bxx, 0.0, 2.6), (0.14, 11.6, 0.1), "M_IntWood")
        mb.box_mm((4.2, -0.2, 2.55), (10.0, 0.2, 2.62), "M_IntMetal")
        for k in range(6):
            mb.box((4.6 + k * 0.95, 0.0, 2.54), (0.04, 0.36, 0.02), "M_IntBlack")
        _ship_fixtures(mb, aset, W, 4.2, 10.0, 5.8, 0.0, 2.65, exits=[(4.2, 0.0, 90.0)], outlets=False, seed=3)
    aset.text("WATCH ROTA", W(4.25, -2.85, z + 1.62), 90.0, size=0.06, color=(0.2, 0.12, 0.06))
    aset.text("LIFE JACKETS", W(4.42, -1.42, z + 1.0), 90.0, size=0.06, color=(1, 1, 1))
    lights([(7.0, 0.0), (5.0, 3.0)], z + 2.2, 2500.0, 7.0)
    mb.box((7.0, 0.0, 12.93), (1.0, 0.3, 0.03), K.PANEL_LIGHT)
    _ship_cam(aset, "ferry_bridge", (4.7, -2.6, z + 1.75), (11.0, 1.2, z + 0.9))


# ================================================================== WAREHOUSES
def _warehouse(aset, mb, nc, im, inc, cx, cy, number, dock):
    """Corrugated steel warehouse, hollow: walls with real doorways / clerestory windows, steel roof trusses,
    a storage hall inside (01: pallet racks + site office, 02: raised dock floor, card distribution)."""
    w, d, H, rh = 40.0, 20.0, 9.0, 3.0
    x0, x1, y0, y1 = cx - w / 2, cx + w / 2, cy - d / 2, cy + d / 2
    T = 0.3                                   # wall thickness (walls sit inside the footprint)
    fz = 1.2 if dock else 0.0                 # interior floor (02: dock level)
    door_mat = "M_CrateRed" if number == "01" else "M_CrateBlue"
    if not dock:
        doors = [(cx - 9.0, 6.4, 0.0, 6.4, True, "slide"), (cx + 9.0, 6.4, 0.0, 6.4, True, "slide"),
                 (cx, 1.1, 0.0, 2.25, False, None)]
    else:
        doors = [(cx + k * 9.0, 4.0, fz, 4.0, True, "slide") for k in (-1, 0, 1)]

    # plinth band (ring) - ground-level doorways cut through it with flush thresholds
    gaps = [(x - dw / 2, x + dw / 2) for x, dw, dz, dh, dbl, md in doors if dz < 0.7]
    for a, b in _gap_runs(x0 - 0.12, x1 + 0.12, gaps):
        mb.box_mm((a, y0 - 0.12, -0.3), (b, y0 + T, 0.7), WCONC, skip=("-z",))
    for a, b in gaps:
        mb.box_mm((a, y0 - 0.12, -0.3), (b, y0 + T, 0.0), WCONC, mats={"+z": DCONC}, skip=("-z",))
    mb.box_mm((x0 - 0.12, y1 - T, -0.3), (x1 + 0.12, y1 + 0.12, 0.7), WCONC, skip=("-z",))
    mb.box_mm((x0 - 0.12, y0 + T, -0.3), (x0 + T, y1 - T, 0.7), WCONC, skip=("-z",))
    mb.box_mm((x1 - T, y0 + T, -0.3), (x1 + 0.12, y1 - T, 0.7), WCONC, skip=("-z",))
    # floor slab (02: raised to the loading dock)
    mb.box_mm((x0 + T, y0 + T, -0.3), (x1 - T, y1 - T, fz + 0.005), WCONC, mats={"+z": "M_IntConcrete"},
              skip=("-z",))

    # walls 0.7 .. H with the real openings (doors, clerestory + gable windows)
    hw = H - 0.7
    s_ops = [K.Door(x - x0, dw, dh, "metal", dbl, md, z0=dz - 0.7) for x, dw, dz, dh, dbl, md in doors]
    n_ops = _wins(_frames(mb, (x1, y1), (x0, y1), H - 2.3, 8, 2.2, 1.1), 2.2, H - 2.3 - 0.7, H - 1.2 - 0.7,
                  mullions=1)
    e_ops = _wins(_frames(mb, (x1, y0), (x1, y1), H - 1.6, 3, 1.6, 1.0), 1.6, H - 1.6 - 0.7, H - 0.6 - 0.7)
    w_ops = _wins(_frames(mb, (x0, y1), (x0, y0), H - 1.6, 3, 1.6, 1.0), 1.6, H - 1.6 - 0.7, H - 0.6 - 0.7)
    for p0, p1, ops in (((x0, y0), (x1, y0), s_ops), ((x1, y0), (x1, y1), e_ops), ((x1, y1), (x0, y1), n_ops),
                        ((x0, y1), (x0, y0), w_ops)):
        K.wall(aset, mb, p0, p1, 0.7, hw, T, "M_WarehouseWall", inner=WH_IN, openings=ops,
               trim=None, trim_in=STEEL)
    mb.gable_roof((cx, cy, H), w, d, rh, "M_WarehouseRoof", overhang=0.7, thick=0.3, gable_mat="M_WarehouseWall")
    _tri_in(mb, x0 + T, y0, y1, H, H + rh - 0.3, WH_IN, 1)
    _tri_in(mb, x1 - T, y0, y1, H, H + rh - 0.3, WH_IN, -1)
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
    # downspouts
    for px in (x0 + 0.5, x1 - 0.5):
        for py, s in ((y0, -1), (y1, 1)):
            mb.box((px, py + s * 0.25, H / 2), (0.18, 0.18, H), DMETAL)

    if not dock:
        # two big sliding doorways (automatic metal doors slide along the old track) + a personnel door
        for dx in (-9.0, 9.0):
            xc = cx + dx
            for sx in (-1, 1):                                                          # painted jambs
                mb.box_mm((xc + sx * 3.2 - (0.3 if sx < 0 else 0.0), y0 - 0.15, 0.0),
                          (xc + sx * 3.2 + (0.3 if sx > 0 else 0.0), y0, 6.6), door_mat)
            mb.box_mm((xc - 3.5, y0 - 0.15, 6.4), (xc + 3.5, y0, 6.6), door_mat)
            mb.box_mm((xc - 7.2, y0 - 0.5, 6.6), (xc + 7.2, y0 - 0.1, 7.0), DMETAL)      # track
            mb.box_mm((xc - 3.6, y0 - 0.45, 0.0), (xc + 3.6, y0 - 0.1, 0.012), DMETAL)   # floor guide (flush)
            aset.light((xc, y0 - 1.2, 7.4), (1.0, 0.92, 0.75), 6000.0, 18.0, night_only=True)
            mb.box((xc, y0 - 0.45, 7.35), (0.7, 0.5, 0.3), DMETAL)
            nc.box((xc, y0 - 0.45, 7.18), (0.55, 0.38, 0.04), GLOW)
        for x, dw, dz, dh, dbl, md in doors:                                            # entrance aprons
            mb.box_mm((x - dw / 2 - 0.3, y0 - 1.8, -0.2), (x + dw / 2 + 0.3, y0 - 0.46 if md else y0 - 0.12, 0.01),
                      DCONC, skip=("-z",))
        for sx in (-1, 1):
            mb.box_mm((cx + sx * 0.55 - (0.1 if sx < 0 else 0.0), y0 - 0.1, 0.0),
                      (cx + sx * 0.55 + (0.1 if sx > 0 else 0.0), y0, 2.35), TRIM)
        mb.box_mm((cx - 0.65, y0 - 0.1, 2.25), (cx + 0.65, y0, 2.35), TRIM)
        mb.box_mm((cx - 1.0, y0 - 1.0, 2.6), (cx + 1.0, y0, 2.75), TRIM)
        aset.text(number, (cx, y0 - 0.05, 6.7), 0.0, size=3.6, color=(0.97, 0.97, 0.97))
    else:
        # raised loading dock with three (automatic) roller doors and a canopy
        dz = fz
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
            mb.box_mm((xc - 2.25, y0 - 0.16, dz), (xc - 2.0, y0, dz + 4.3), TRIM)
            mb.box_mm((xc + 2.0, y0 - 0.16, dz), (xc + 2.25, y0, dz + 4.3), TRIM)
            mb.box_mm((xc - 2.0, y0 - 0.16, dz + 4.0), (xc + 2.0, y0, dz + 4.3), TRIM)
            mb.box((xc, y0 - 0.35, dz + 4.35), (4.6, 0.5, 0.5), DMETAL)                  # roller box
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

    # ---------------------------------------------------------------- inside
    _wh_trusses(aset, im, x0, x1, y0, y1, H, rh, T)
    # concrete dado with a yellow safety stripe
    gaps = [(x - x0 - T - dw / 2 - 0.1, x - x0 - T + dw / 2 + 0.1) for x, dw, dz, dh, dbl, md in doors]
    for (p0, p1), gg in ((((x0 + T, y0 + T), (x1 - T, y0 + T)), gaps), (((x1 - T, y0 + T), (x1 - T, y1 - T)), ()),
                         (((x1 - T, y1 - T), (x0 + T, y1 - T)), ()), (((x0 + T, y1 - T), (x0 + T, y0 + T)), ())):
        K.wainscot(im, p0, p1, fz, 1.1, "M_IntConcrete", cap=YELLOW, gaps=gg)
    A = _Shifted(aset, (cx, cy, fz))
    with im.at((cx, cy, fz)), inc.at((cx, cy, fz)):
        if dock:
            _wh02_interior(A, im, inc, number)
        else:
            _wh01_interior(A, im, inc, number)
        _hall_services(A, im, inc, -w / 2 + T, -d / 2 + T, w / 2 - T, d / 2 - T, H - 0.62 - 0.11 - fz, seed=len(number))


def _wh_trusses(aset, mb, x0, x1, y0, y1, H, rh, T):
    """Steel roof trusses every 5 m (tie beam, rafters, king post, struts), purlins and hanging lamps."""
    cy = (y0 + y1) / 2
    half = (y1 - y0) / 2
    zt = H - 0.62

    def zr(y):           # rafter centre line just under the roof underside
        return H - 0.45 + (half - abs(y - cy)) / half * rh

    for k in range(1, 8):
        x = x0 + 5.0 * k
        mb.box((x, cy, zt), (0.16, y1 - y0 - 2 * T, 0.22), STEEL)
        for s in (-1, 1):
            ye = cy + s * (half - T)
            mb.beam((x, ye, zr(ye)), (x, cy, zr(cy)), 0.14, 0.2, STEEL)
            for t in (0.35, 0.7):
                yb = cy + s * (half - T) * t
                mb.beam((x, yb, zt + 0.1), (x, cy + s * (half - T) * (t - 0.17), zr(cy + s * (half - T) * (t - 0.17)) - 0.1),
                        0.07, 0.07, STEEL)
        mb.box((x, cy, (zt + zr(cy)) / 2), (0.12, 0.12, zr(cy) - zt), STEEL)
    for s in (-1, 0, 1):
        y = cy + s * 5.5
        mb.box_mm((x0 + T, y - 0.06, zr(y) + 0.03), (x1 - T, y + 0.06, zr(y) + 0.15), STEEL)
    for k in (1, 3, 5, 7):
        for s in (-1, 1):
            aset.prop("SM_Int_IndustrialLamp", (x0 + 5.0 * k, cy + s * 4.5, zt - 0.11), 0.0)


def _wh01_interior(A, mb, nc, number):
    """Warehouse 01 (local: centre of the hall, floor z 0): pallet racks, staging area, container, workbench,
    lockers and a glazed site office in the NE corner."""
    rnd = random.Random(101)
    # racks: along the north wall and a back-to-back double row
    _rack(mb, nc, A, rnd, -19.2, 9.05, 10)
    _rack(mb, nc, A, rnd, -16.6, 3.2, 8)
    _rack(mb, nc, A, rnd, -16.6, 2.0, 8)
    # shipping container being unpacked (doors open towards the hall)
    A.prop("SM_Container_Blue", (-17.6, -3.0, 0.0), 90.0)
    for i, (px, py) in enumerate(((-15.4, -4.6), (-15.4, -3.2), (-14.0, -4.0))):
        _pallet(mb, px, py, 0.0)
        A.prop("SM_Crate" if i != 1 else "SM_Int_Box", (px, py, 0.14), rnd.uniform(-8, 8))
    # staging area: pallets with crates and boxes
    for i, (px, py) in enumerate(((-3.2, -4.4), (-1.8, -4.4), (1.8, -4.4), (3.2, -4.4), (-2.5, -2.4), (2.5, -2.4))):
        _pallet(mb, px, py, 90.0)
        if i % 3 == 0:
            A.prop("SM_Crate", (px, py, 0.14), rnd.uniform(-6, 6))
            if i == 0:
                A.prop("SM_Int_Box", (px, py, 1.10), 20.0)
        else:
            for bx in (-0.25, 0.25):
                for by in (-0.3, 0.3):
                    A.prop("SM_Int_Box", (px + bx, py + by, 0.14), rnd.uniform(-10, 10))
                    if rnd.random() < 0.5:                                      # second layer (NoCol cartons)
                        nc.box((px + bx, py + by, 0.14 + 0.36 + 0.17), (0.38, 0.5, 0.34), CARTONS[0])
    A.prop("SM_Int_HandTruck", (1.7, -8.7, 0.0), 25.0)
    A.prop("SM_Int_Extinguisher", (1.3, -9.45, 0.0), 0.0)
    A.prop("SM_Int_Extinguisher", (-19.4, 0.6, 0.0), 90.0)
    # barrels in the SE corner (on a drip tray)
    mb.box_mm((14.6, -9.6, 0.0), (19.6, -6.6, 0.06), YELLOW)
    for i in range(7):
        A.prop("SM_Barrel", (15.2 + (i % 4) * 1.1 + (0.5 if i >= 4 else 0.0), -9.0 + (i // 4) * 1.0 + 0.2, 0.06),
               rnd.uniform(0, 360))
    # workbench + pegboard on the east wall
    with mb.at((19.22, -0.4, 0.0), rot=-90.0), nc.at((19.22, -0.4, 0.0), rot=-90.0):
        mb.box((0, 0, 0.88), (2.4, 0.8, 0.06), "M_IntWood")
        for sx in (-1, 1):
            mb.box((sx * 1.1, 0, 0.43), (0.08, 0.7, 0.85), STEEL)
        mb.box((0, 0, 0.2), (2.3, 0.7, 0.03), STEEL)
        mb.box((0.85, -0.25, 0.97), (0.2, 0.18, 0.12), STEEL)                          # vise
        nc.box((0, 0.38, 1.7), (2.2, 0.03, 1.0), "M_IntCork")                         # pegboard
        rt = random.Random(5)
        for k in range(9):
            nc.box((-0.95 + k * 0.24, 0.35, rt.uniform(1.4, 2.0)), (0.04, 0.02, rt.uniform(0.15, 0.35)),
                   rt.choice((STEEL, "M_IntFabricRed", "M_IntBlack", ORANGE)))
        nc.box((-0.6, 0.0, 0.95), (0.4, 0.25, 0.08), "M_IntFabricRed")                # tool box
        nc.box((0.2, -0.1, 0.92), (0.3, 0.2, 0.02), "M_IntPaper")
    A.prop("SM_Int_DeskLamp", (19.4, 0.4, 0.91), -90.0)
    A.prop("SM_Int_Stool", (18.4, -0.4, 0.0), 0.0)
    K.lockers(mb, nc, A, 19.4, 2.6, -90.0, n=5)
    # site office + crew break room (NE corner): glazed partition walls, flat roof used as storage
    ox0, oy0 = 9.5, 4.5
    K.wall(A, mb, (ox0, oy0), (19.7, oy0), 0.0, 3.0, 0.15, K.PLASTER_WHITE, inner=K.PLASTER_CREAM,
           openings=[K.Door(2.0, 0.95, 2.1, "office"), K.Window(3.75, 1.9, 1.0, 2.2), K.Door(5.9, 0.95, 2.1, "office"),
                     K.Window(8.15, 2.6, 1.0, 2.2)],
           trim=K.TRIM_WHITE, trim_in=K.TRIM_WHITE, base=K.TRIM_WOOD)
    K.wall(A, mb, (ox0, 9.7), (ox0, oy0), 0.0, 3.0, 0.15, K.PLASTER_WHITE, inner=K.PLASTER_CREAM,
           openings=[K.Window(2.6, 2.4, 1.0, 2.2)], trim=K.TRIM_WHITE, trim_in=K.TRIM_WHITE, base=K.TRIM_WOOD)
    px_ = 14.6                                                     # office | break room partition
    K.wall(A, mb, (px_, 9.64), (px_, oy0 + 0.15), 0.0, 3.0, 0.12, K.PLASTER_CREAM, inner=K.PLASTER_CREAM,
           openings=[K.Door(9.64 - 5.75, 0.9, 2.1, "office")], trim=K.TRIM_WHITE, trim_in=K.TRIM_WHITE,
           base=K.TRIM_WOOD)
    mb.box_mm((ox0, oy0, 3.0), (19.7, 9.7, 3.14), STEEL, mats={"-z": K.CEIL})
    mb.box_mm((ox0 + 0.15, oy0 + 0.15, 0.0), (19.7, 9.7, 0.01), "M_IntLinoleum", skip=("-z",))
    K.wainscot(mb, (19.64, oy0 + 0.15), (19.64, 9.64), 0.01, 2.99, K.PLASTER_CREAM)    # cover the steel walls
    K.wainscot(mb, (19.64, 9.64), (ox0 + 0.15, 9.64), 0.01, 2.99, K.PLASTER_CREAM)
    for px, py in ((11.0, 4.9), (16.0, 3.9), (18.5, 4.2)):
        A.prop("SM_Int_Box", (px + 0.3, py + 2.0, 3.14), rnd.uniform(0, 90))
    A.prop("SM_Crate", (12.6, 7.6, 3.14), 0.0)
    K.nameplate(mb, A, 12.9, oy0, 1.85, 0.0, "SITE OFFICE", w=0.7, h=0.16)
    K.nameplate(mb, A, 17.2, oy0, 1.85, 0.0, "CREW ROOM", w=0.6, h=0.16)
    fx0, fy0, fx1, fy1 = ox0 + 0.15, oy0 + 0.15, px_, 9.64                  # office inner box
    bx0, bx1 = px_ + 0.12, 19.64                                            # break room inner x
    _dress(A, mb, nc, fx0, fy0, fx1, fy1, 0.0, 3.0, "office", seed=12, ac=False)
    _dress(A, mb, nc, bx0, fy0, bx1, fy1, 0.0, 3.0, "office", seed=13)
    for wx, ww in ((12.3 + 0.95, 1.9), (16.35 + 1.3, 2.6)):
        DT.blinds(nc, wx, fy0, 1.0, 2.2, 180.0, ww - 0.1, 0.45)
    DT.blinds(nc, fx0, 7.1, 1.0, 2.2, 90.0, 2.3, 0.3)
    # -- office: desk, files, shipping schedule
    K.desk(mb, nc, 12.0, 9.22, 0.0, w=1.8, d=0.8, top=K.TRIM_WHITE, legs=STEEL, hutch=False, clutter=False)
    DT.desk_set(nc, A, 12.0, 9.22, 0.76, 0.0, "office", seed=21, w=1.8, d=0.8)
    A.prop("SM_Int_OfficeChair", (12.0, 8.3, 0.0), 180.0)
    A.prop("SM_Int_PlasticChair", (13.3, 7.4, 0.0), 160.0)
    A.prop("SM_Int_Cabinet", (10.3, 9.31, 0.0), 0.0)
    A.prop("SM_Int_Radio", (10.3, 9.38, 1.18), 0.0)
    A.prop("SM_Int_Drawers", (13.85, 9.37, 0.0), 0.0)
    DT.paper_stack(nc, 13.7, 9.37, 1.88, 0.0, 9, seed=3)
    K.bookcase(mb, nc, fx1 - 0.18, 8.05, -90.0, w=1.0, d=0.34, h=1.9, shelves=5, mat=STEEL, rng_seed=6)
    _whiteboard(nc, A, fx1, 6.85, 0.95, -90.0, 1.1, 0.8, ("ETA FERRY  MON 10:00", "WH02: 412 CRATES", "CALL CRANE 3"))
    K.bulletin(nc, A, 10.3, fy1, 1.7, 0.0, 1.1, 0.75, title="SHIPPING SCHEDULE", rng_seed=11)
    A.prop("SM_Int_WallClock", (12.0, fy1, 2.35), 0.0)
    K.poster(nc, A, fx0, 5.4, 1.7, 90.0, 0.6, 0.85, "M_IntPoster4", "KC-7")
    _wall_map(nc, A, fx0, 9.0, 1.45, 90.0, 0.9, 0.65, "SEA ROUTES", seed=4)
    A.prop("SM_Int_PottedPlant", (13.3, 4.95, 0.0), 0.0)
    A.prop("SM_Int_Extinguisher", (fx0 + 0.25, 4.95, 0.0), 90.0)
    nc.cylinder((10.75, 8.45, 0.0), 0.15, 0.32, STEEL, seg=12, cap_top=False)          # waste bin
    DT.paper_stack(nc, 10.75, 8.45, 0.25, 30.0, 2, seed=8)
    A.prop("SM_Int_Box", (10.2, 8.3, 0.0), 10.0)
    nc.box_mm((11.1, 7.8, 0.01), (12.9, 9.1, 0.016), "M_HarborWrap")                    # chair mat
    _wall_shelf(nc, A, 12.0, fy1, 1.75, 0.0, 1.5, (), d=0.28)
    for k in range(14):                                                                    # binders
        nc.box((11.4 + k * 0.065, fy1 - 0.15, 1.75 + 0.16), (0.055, 0.26, 0.32),
               ("M_IntFabricBlue", "M_IntFabricRed", "M_IntTrimWhite", "M_IntFabricYellow")[k % 4])
    A.prop("SM_Int_Frame", (13.85, fy1, 2.15), 0.0)
    mb.box((10.0, 6.9, 0.35), (0.5, 0.6, 0.7), STEEL)                                      # printer stand
    nc.box((10.0, 6.9, 0.85), (0.45, 0.45, 0.3), "M_IntTrimWhite")
    nc.box((10.0, 6.66, 0.9), (0.3, 0.01, 0.02), "M_IntBlack")
    DT.paper_stack(nc, 10.0, 6.9, 1.0, 90.0, 3, seed=31)
    A.prop("SM_Int_Box", (10.0, 7.75, 0.0), 5.0)
    A.prop("SM_Int_RoundTableB", (11.4, 6.25, 0.0), 0.0)
    for a in (180.0, 0.0):
        A.prop("SM_Int_PlasticChair", (11.4 + math.cos(math.radians(a)) * 0.72, 6.25, 0.0), a - 90.0)
    DT.paper_stack(nc, 11.3, 6.2, 0.75, 20.0, 5, seed=41)
    DT.mug(nc, 11.6, 6.0, 0.75, seed=42)
    K.panel_light(A, nc, 12.1, 7.1, 3.0)
    # -- break room: kitchenette, lockers with hi-vis vests, sofa corner, card table
    K.kitchen_run(mb, nc, 15.0, fy1, 17.55, against="+y")
    A.prop("SM_Int_Kettle", (15.25, 9.3, 0.9), 20.0)
    _coffee_machine(nc, 16.35, 9.35, 0.9, 0.0)
    A.prop("SM_Int_Microwave", (17.25, 9.33, 0.9), 0.0)
    for k in range(3):
        DT.mug(nc, 16.62 + k * 0.1, 9.1, 0.9, seed=k + 4, coffee=False)
    _fridge(mb, nc, 18.0, 9.3, 0.0)
    _water_cooler(mb, nc, 19.38, 5.0, -90.0)
    K.lockers(mb, nc, A, bx0 + 0.235, 7.9, 90.0, n=5)
    _vest_hooks(nc, bx1, 8.45, 1.75, -90.0, n=3, vests=3)
    A.prop("SM_Int_SofaB", (19.2, 6.4, 0.0), -90.0)
    A.prop("SM_Int_CoffeeTableB", (18.05, 6.4, 0.0), 90.0)
    DT.mug(nc, 18.0, 6.1, 0.39, seed=9)
    DT.paper_stack(nc, 18.05, 6.7, 0.39, 80.0, 3, seed=19)
    K.bulletin(nc, A, bx1, 6.4, 1.25, -90.0, 1.3, 0.8, title="CREW NOTICES", rng_seed=14)
    with mb.at((px_ + 0.12, 7.9, 2.38), rot=90.0):                                     # wall TV over the lockers
        mb.box((0, -0.03, 0), (1.0, 0.06, 0.58), "M_IntBlack")
    nc.box((px_ + 0.185, 7.9, 2.38), (0.004, 0.92, 0.5), "M_IntScreen")
    A.prop("SM_Int_RoundTableB", (16.85, 6.75, 0.0), 0.0)
    for a in (200.0, 320.0, 80.0):
        r = math.radians(a)
        A.prop("SM_Int_PlasticChair", (16.85 + math.cos(r) * 0.72, 6.75 + math.sin(r) * 0.72, 0.0), a - 90.0)
    DT.card_spread(nc, 16.75, 6.7, 0.75, 10.0, 5, seed=2)
    DT.deck_box(nc, 17.05, 6.95, 0.75, 30.0, "M_IntFabricBlue")
    DT.mug(nc, 16.6, 7.0, 0.75, seed=1)
    nc.cylinder((18.6, 5.0, 0.0), 0.16, 0.34, "M_IntFabricGreen", seg=12, cap_top=False)   # recycling bin
    A.prop("SM_Int_PottedPlantB", (19.25, 9.25, 0.0), 0.0)
    A.prop("SM_Int_WallClock", (17.2, fy1, 2.45), 0.0)
    K.panel_light(A, nc, 17.2, 7.1, 3.0)
    # -- hall life: forklift, pallet jack, vests by the personnel door, clipboards, first aid, rota
    _forklift(mb, nc, 7.6, -3.3, 180.0, load=0.9, rnd=rnd)
    _pallet_jack(mb, -13.2, -6.8, 15.0)
    _vest_hooks(nc, -1.7, -9.7, 1.75, 180.0, n=3, vests=2)
    _first_aid(nc, A, 1.4, -9.7, 1.55, 180.0)
    _wall_clipboards(nc, 5.45, 2.6, 1.35, 90.0, n=1, seed=3)
    K.bulletin(nc, A, -19.7, 5.6, 1.2, 90.0, 1.3, 0.85, title="SHIFT ROTA", rng_seed=17)
    _first_aid(nc, A, -19.7, 7.0, 1.55, 90.0)
    A.prop("SM_Int_ToolCart", (17.6, -2.9, 0.0), 90.0)
    A.prop("SM_Int_Broom", (19.3, -5.4, 0.0), -90.0)
    A.prop("SM_Int_Dustpan", (19.0, -5.9, 0.0), -60.0)
    A.prop("SM_Int_TrashBag", (-12.0, -9.2, 0.0), 30.0)
    A.prop("SM_Int_WetFloor", (-1.4, -6.6, 0.0), 20.0)
    # signs, posters, floor markings
    K.poster(nc, A, -3.4, -9.7, 2.1, 180.0, 1.0, 1.4, "M_IntPoster3", "SAFETY FIRST!", text_color=(0.2, 0.1, 0.05))
    K.poster(nc, A, 3.4, -9.7, 2.1, 180.0, 1.0, 1.4, "M_IntPoster1", "NO SMOKING")
    K.poster(nc, A, -19.7, -7.5, 2.2, 90.0, 1.1, 1.5, "M_IntPoster2", "DUEL ACADEMY SUPPLY")
    A.text("WAREHOUSE " + number, (-5.0, 9.6, 6.1), 0.0, size=1.0, color=(0.98, 0.85, 0.2))
    A.text("CARDS  -  DORM SUPPLIES  -  KITCHEN", (-5.0, 9.6, 5.5), 0.0, size=0.38, color=(0.95, 0.95, 0.95))
    for xx in (-0.9, 0.9):                                                           # walkway from the door
        nc.box_mm((xx - 0.06, -9.7, 0.0), (xx + 0.06, -5.9, 0.012), YELLOW)
    for yy in (-5.6, 0.9, 4.15, 8.1):
        nc.box_mm((-16.6, yy - 0.06, 0.0), (8.3 if yy > 6 else 5.4, yy + 0.06, 0.012), YELLOW)
    K.camera(A, "wh01_hall", (13.5, -8.6, 3.2), (-8.0, 4.5, 1.4), 15.0)
    K.camera(A, "wh01_office", (9.95, 5.15, 1.65), (13.4, 9.3, 0.9), 16.0)
    K.camera(A, "wh01_crew", (15.1, 5.05, 1.65), (19.0, 8.7, 0.9), 16.0)


def _wh02_interior(A, mb, nc, number):
    """Warehouse 02 (local: centre of the hall, raised floor at dock level = z 0 here): card distribution -
    conveyor + packing tables, steel shelving aisles, a caged rare-card vault, staff break corner."""
    rnd = random.Random(202)
    # conveyor from the middle dock door to the packing tables
    with mb.at((0.0, -3.4, 0.0)):
        mb.box_mm((-0.5, -2.6, 0.72), (-0.42, 2.6, 0.8), STEEL)
        mb.box_mm((0.42, -2.6, 0.72), (0.5, 2.6, 0.8), STEEL)
        for yy in (-2.4, 0.0, 2.4):
            for xx in (-0.46, 0.46):
                mb.box((xx, yy, 0.36), (0.06, 0.06, 0.72), STEEL)
        for k in range(21):
            with mb.at((0.0, -2.5 + k * 0.25, 0.77), rot_y=90):
                mb.cylinder((0, 0, -0.42), 0.035, 0.84, "M_IntMetal", seg=6, cap_top=False, cap_bottom=False)
        mb.box_mm((-0.4, -2.55, 0.805), (0.4, 2.55, 0.815), "M_IntBlack")                       # belt
    for k, yy in enumerate((-5.2, -3.9, -2.4, -1.4)):
        A.prop("SM_Int_Box", (rnd.uniform(-0.12, 0.12), yy, 0.815), rnd.uniform(-20, 20))
    # packing tables
    for px in (-2.4, 2.4):
        mb.box((px, 0.6, 0.88), (1.8, 0.8, 0.04), "M_IntWood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((px + sx * 0.85, 0.6 + sy * 0.35, 0.43), (0.05, 0.05, 0.86), STEEL)
        mb.box((px, 0.6, 0.18), (1.75, 0.75, 0.03), STEEL)
        for k in range(3):
            A.prop("SM_Int_Box", (px - 0.56 + k * 0.56, 0.6, 0.195), 90.0 + k * 3)
        with mb.at((px, 0.95, 1.25)):                                                   # kraft paper roll
            for sx in (-1, 1):
                mb.box((sx * 0.8, 0.05, 0.0), (0.04, 0.04, 0.74), STEEL)
            with mb.at((0, 0.05, 0.3), rot_y=90):
                mb.cylinder((0, 0, -0.75), 0.07, 1.5, "M_IntCork", seg=10)
        A.prop("SM_Int_MetalStool", (px - 0.4, -0.25, 0.0), 0.0)
        A.prop("SM_Int_MetalStool", (px + 0.5, -0.25, 0.0), 0.0)
        A.prop("SM_Int_Box", (px + 0.45, 0.65, 0.9), 15.0)
        nc.box((px - 0.3, 0.55, 0.91), (0.45, 0.35, 0.02), "M_IntCork")
        nc.cylinder((px - 0.6, 0.85, 0.9), 0.06, 0.05, "M_IntPaper", seg=10)       # tape roll
        nc.box((px - 0.2, 0.9, 0.93), (0.3, 0.2, 0.06), "M_IntMetal")                # parcel scale
        nc.box((px - 0.2, 0.8, 0.931), (0.12, 0.004, 0.04), "M_IntScreen")
        A.prop("SM_Int_Clipboard", (px + 0.05, 0.3, 0.9), 10.0 + px * 5)
        DT.card_spread(nc, px - 0.45, 0.25, 0.9, 5.0, 4, seed=int(px * 10))
    # steel shelving aisles (procedural shelves stocked with card cartons)
    for row_y, yaw in ((9.35, 0.0), (6.95, 0.0), (6.35, 180.0), (3.95, 0.0), (3.35, 180.0)):
        x = -12.2
        while x < 7.5:
            _shelf_unit(mb, nc, rnd, x, row_y, yaw)
            x += 1.85
    # rare card vault (wire cage) in the NE corner with a gate
    cx0, cy0 = 9.6, 2.4
    gate = (12.2, 1.0)
    bars = []
    for (ax, ay), (bx, by) in (((cx0, 9.7), (cx0, cy0)), ((cx0, cy0), (19.7, cy0))):
        L = math.hypot(bx - ax, by - ay)
        n = int(L / 0.12)
        for i in range(n + 1):
            t = i / n
            px, py = ax + (bx - ax) * t, ay + (by - ay) * t
            if ay == by and abs(px - gate[0]) < gate[1] / 2 + 0.06:
                continue
            bars.append((px, py))
        mb.beam((ax, ay, 2.6), (bx, by, 2.6), 0.06, 0.06, STEEL)
        if ay == by:            # bottom rail stops at the gate
            for a, b in ((ax, gate[0] - gate[1] / 2 - 0.1), (gate[0] + gate[1] / 2 + 0.1, bx)):
                mb.beam((a, ay, 0.1), (b, ay, 0.1), 0.06, 0.12, STEEL)
        else:
            mb.beam((ax, ay, 0.1), (bx, by, 0.1), 0.06, 0.12, STEEL)
        for i in range(int(L / 2.0) + 1):
            t = min(i * 2.0 / L, 1.0)
            mb.box((ax + (bx - ax) * t, ay + (by - ay) * t, 1.35), (0.08, 0.08, 2.7), STEEL)
    for px, py in bars:
        mb.box((px, py, 1.35), (0.02, 0.02, 2.5), "M_IntMetal")
    for sx in (-1, 1):
        mb.box((gate[0] + sx * (gate[1] / 2 + 0.05), cy0, 1.35), (0.1, 0.1, 2.7), STEEL)
    mb.box((gate[0], cy0, 2.25), (gate[1] + 0.2, 0.1, 0.1), STEEL)
    A.door((gate[0], cy0, 0.0), 0.0, gate[1], 2.15, "metal")
    mb.box_mm((cx0, cy0, 0.0), (19.7, 9.7, 0.01), "M_IntTileBlue", skip=("-z",))
    A.text("RARE CARD VAULT", (gate[0] + 2.4, cy0 - 0.08, 2.35), 0.0, size=0.26, color=(0.98, 0.85, 0.2))
    A.text("AUTHORIZED STAFF ONLY", (gate[0] + 2.4, cy0 - 0.08, 2.05), 0.0, size=0.16, color=(0.95, 0.3, 0.25))
    nc.box((gate[0] + 2.4, cy0 - 0.03, 2.22), (2.4, 0.02, 0.62), "M_IntBlack")
    for i, px in enumerate((14.2, 15.6, 17.0, 18.4)):
        _pallet(mb, px, 8.8, 0.0)
        for k in range(3):
            nc.box((px, 8.8, 0.14 + 0.2 + k * 0.42), (1.1, 0.9, 0.4), K.POSTERS[(i + k) % 4])
    A.prop("SM_Int_DisplayShelves", (11.0, 9.45, 0.0), 0.0)
    A.prop("SM_Int_DisplayShelves", (12.1, 9.45, 0.0), 0.0)
    mb.box((18.9, 4.0, 0.5), (1.0, 0.8, 1.0), "M_IntBlack")                         # safe
    mb.box((18.9, 3.58, 0.55), (0.18, 0.04, 0.18), "M_IntTrimGold")
    mb.box((16.0, 5.6, 0.45), (0.6, 0.6, 0.9), "M_IntMarbleFloor")                  # plinth + founder bust
    A.prop("SM_Int_Bust", (16.0, 5.6, 0.9), 200.0)
    A.text("THE FOUNDER", (16.0, 5.28, 0.55), 0.0, size=0.08, color=(0.2, 0.15, 0.1))
    # break corner (NW)
    A.prop("SM_VendingMachine", (-19.15, 8.4, 0.0), 90.0)
    A.prop("SM_Int_RoundTable", (-17.0, 6.0, 0.0), 0.0)
    for a in (0.0, 120.0, 240.0):
        r = math.radians(a)
        A.prop("SM_Int_WoodChair", (-17.0 + math.cos(r) * 0.8, 6.0 + math.sin(r) * 0.8, 0.0), a - 90.0)
    A.prop("SM_Int_TeaSet", (-17.0, 6.0, 0.75), 30.0)
    A.prop("SM_Int_Bench", (-17.0, 9.35, 0.0), 180.0)
    A.prop("SM_Int_SideTable", (-14.6, 9.35, 0.0), 0.0)
    A.prop("SM_Int_TV", (-14.6, 9.35, 0.56), 0.0)
    K.lockers(mb, nc, A, -19.4, 2.6, 90.0, n=6)
    K.bulletin(nc, A, -19.62, 5.6, 1.2, 90.0, 1.4, 0.9, title="BREAK ROOM", rng_seed=4)
    A.prop("SM_Int_PottedPlantB", (-14.6, 7.6, 0.0), 0.0)
    # outgoing pallets (SW) and inbound crates (SE)
    for i, (px, py) in enumerate(((-17.8, -4.2), (-16.2, -4.2), (-17.8, -2.6), (-16.2, -2.6), (-14.6, -4.2))):
        _pallet(mb, px, py, 90.0)
        hgt = 0.9 + (i % 3) * 0.2
        nc.box((px, py, 0.14 + hgt / 2), (1.0, 1.15, hgt), CARTONS[i % 3])
        nc.box((px, py, 0.15 + hgt), (1.02, 1.17, 0.02), "M_IntFabricWhite")
    A.prop("SM_Int_HandTruck", (-13.8, -2.2, 0.0), -30.0)
    for px in (15.2, 16.6):
        _crate_mesh(mb, px, -5.4, 0.0, 0.0)
    for i, (px, py, pz) in enumerate(((18.0, -5.4, 0.0), (15.2, -5.4, 0.96), (16.6, -5.4, 0.96), (17.8, -3.6, 0.0))):
        A.prop("SM_Crate", (px, py, pz), (i * 17) % 20 - 10)
    A.prop("SM_Int_Extinguisher", (-6.0, -9.45, 0.0), 0.0)
    A.prop("SM_Int_Extinguisher", (6.0, -9.45, 0.0), 0.0)
    K.poster(nc, A, -4.5, -9.7, 2.0, 180.0, 1.0, 1.4, "M_IntPoster2", "PACK WITH CARE")
    K.poster(nc, A, 4.5, -9.7, 2.0, 180.0, 1.0, 1.4, "M_IntPoster3", "LIFT SAFELY!", text_color=(0.2, 0.1, 0.05))
    A.text("WAREHOUSE " + number, (-3.0, 9.6, 6.0), 0.0, size=1.0, color=(0.3, 0.6, 1.0))
    A.text("BOOSTER PACKS  -  DUEL DISKS  -  ACADEMY MAIL", (-3.0, 9.6, 5.4), 0.0, size=0.36,
           color=(0.95, 0.95, 0.95))
    for xx in (-9.0, 0.0, 9.0):
        nc.box_mm((xx - 2.0, -6.4, 0.0), (xx + 2.0, -6.28, 0.012), YELLOW)
    # hall life: forklift with a load, pallet jack, hi-vis vests, dispatch board, clipboards, first aid
    _forklift(mb, nc, -8.6, -2.9, 180.0, fork_z=0.35, load=1.0, rnd=rnd)
    _pallet_jack(mb, 7.6, -4.6, 160.0)
    _vest_hooks(nc, -19.7, -0.2, 1.75, 90.0, n=4, vests=3)
    _first_aid(nc, A, -19.7, -1.6, 1.55, 90.0)
    _whiteboard(nc, A, -13.5, -9.7, 1.0, 180.0, 1.6, 0.9, ("DISPATCH - TODAY", "BOOSTERS  412 CRATES", "DUEL DISKS  36",
                                                            "ACADEMY MAIL  2 BAGS"))
    _wall_clipboards(nc, 9.6 - 0.04, 6.0, 1.4, -90.0, n=2, seed=9)
    K.bulletin(nc, A, 13.5, -9.7, 1.2, 180.0, 1.3, 0.85, title="SAFETY NOTICES", rng_seed=23)
    A.prop("SM_Int_TrashBag", (-11.0, -9.2, 0.0), 10.0)
    A.prop("SM_Int_Broom", (19.3, -1.4, 0.0), -90.0)
    A.prop("SM_Int_WetFloor", (-4.2, -6.0, 0.0), 30.0)
    DT.card_spread(nc, -17.0, 5.68, 0.75, 0.0, 5, seed=7)
    DT.deck_box(nc, -16.6, 6.3, 0.75, -15.0, "M_IntFabricYellow")
    K.camera(A, "wh02_hall", (-15.5, -8.4, 3.0), (6.0, 6.0, 1.0), 15.0)
    K.camera(A, "wh02_vault", (10.1, 2.9, 1.7), (17.5, 8.6, 0.8), 16.0)


def _warehouses(aset, mb, nc, im, inc):
    _warehouse(aset, mb, nc, im, inc, -100.0, 32.0, "01", dock=False)
    _warehouse(aset, mb, nc, im, inc, -55.0, 32.0, "02", dock=True)


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
    # (walk-in: built by _crane_machinery from the cab code, which knows the stair tower)
    # trolley, operator cab, ropes and spreader with a container
    ty = -45.0
    mb.box_mm((x - 3.3, ty - 1.6, top - 0.5), (x + 3.3, ty + 1.6, top), DMETAL)
    # operator cab (hollow, walk-in) hanging under the trolley, reached by a steel stair tower + catwalk
    _crane_cab(aset, mb, nc, x, ty, top, by1)
    sz = 6.6
    mb.box_mm((x - 3.1, ty - 1.25, sz), (x + 3.1, ty + 1.25, sz + 0.4), Y)
    mb.box_mm((x - 1.0, ty - 0.6, sz + 0.4), (x + 1.0, ty + 0.6, sz + 0.9), Y)
    for rx in (-0.7, 0.7):
        for ryy in (-0.4, 0.4):
            nc.beam((x + rx, ty + ryy, sz + 0.9), (x + rx * 1.2, ty + ryy, top - 0.5), 0.05, 0.05, DMETAL)
    aset.prop("SM_Container_Yellow", (x, ty, sz - 2.62), 0.0)
    aset.light((x, ty, top - 0.6), (1.0, 0.95, 0.85), 8000.0, 25.0, night_only=True)


def _crane_cab(aset, mb, nc, x, ty, top, by1):
    """Operator cab under the trolley (floor 9.0, glass front + floor window towards the sea), the catwalk from
    the stair tower on the land side, and the switchback stair (0.18 m risers, 0.28 m treads, 5 flights)."""
    Y = CRANE_Y
    X0, X1, Y0, Y1 = x + 0.9, x + 3.0, ty - 1.2, ty + 1.2
    fz, cz = top - 3.0, top - 0.6                  # cab floor 9.0, ceiling 11.4
    cx = (X0 + X1) / 2
    # floor slab with a glazed hatch in front of the seat (operators look straight down at the spreader)
    hx0, hx1, hy0, hy1 = cx - 0.45, cx + 0.45, Y0 + 0.15, Y0 + 0.85
    for a, b in (((X0 - 0.1, Y0 - 0.05), (X1 + 0.1, hy0)), ((X0 - 0.1, hy1), (X1 + 0.1, Y1 + 0.05)),
                 ((X0 - 0.1, hy0), (hx0, hy1)), ((hx1, hy0), (X1 + 0.1, hy1))):
        mb.box_mm((a[0], a[1], fz - 0.1), (b[0], b[1], fz), BLUE, mats={"+z": "M_IntMetal"})
    mb.box_mm((hx0, hy0, fz - 0.06), (hx1, hy1, fz - 0.03), GLASS_IN)
    for a, b in (((hx0 - 0.04, hy0 - 0.04), (hx1 + 0.04, hy0)), ((hx0 - 0.04, hy1), (hx1 + 0.04, hy1 + 0.04))):
        mb.box_mm((a[0], a[1], fz - 0.1), (b[0], b[1], fz + 0.01), "M_IntBlack")
    kw = dict(trim=TRIM, trim_in=K.TRIM_WHITE)
    h = cz - fz
    for p0, p1, ops in (((X0, Y0), (X1, Y0), [K.Window(1.05, 1.8, 0.35, 2.1, frame=TRIM, mullions=1)]),
                        ((X1, Y0), (X1, Y1), [K.Window(1.0, 1.2, 0.9, 2.0, frame=TRIM)]),
                        ((X1, Y1), (X0, Y1), [K.Door(1.05, 0.9, 2.05, "metal", swing="out")]),
                        ((X0, Y1), (X0, Y0), [K.Window(1.4, 1.2, 0.9, 2.0, frame=TRIM)])):
        K.wall(aset, mb, p0, p1, fz, h, 0.1, WHITE, inner=K.PLASTER_WHITE, openings=ops, **kw)
    mb.box_mm((X0 - 0.05, Y0 - 0.05, cz), (X1 + 0.05, Y1 + 0.05, top - 0.5), WHITE, mats={"-z": K.CEIL})
    mb.box_mm((X0 - 0.15, Y0 - 0.35, cz + 0.02), (X1 + 0.15, Y0, cz + 0.08), BLUE)            # sun visor
    # ---- inside: seat with joystick armrests, side consoles, radio shelf, extinguisher, vest, clipboard
    ix0, ix1, iy0, iy1 = X0 + 0.1, X1 - 0.1, Y0 + 0.1, Y1 - 0.1
    sy = ty
    with mb.at((cx, sy, fz)), nc.at((cx, sy, fz)):
        mb.cylinder((0, 0, 0.0), 0.22, 0.04, "M_IntMetal", seg=10)
        mb.cylinder((0, 0, 0.04), 0.05, 0.38, "M_IntMetal", seg=8)
        mb.box((0, 0, 0.47), (0.5, 0.5, 0.1), "M_IntBlack")
        mb.box((0, 0.27, 0.85), (0.5, 0.08, 0.7), "M_IntBlack")
        mb.box((0, 0.29, 1.27), (0.28, 0.08, 0.16), "M_IntBlack")                              # headrest
        for s in (-1, 1):
            mb.box((s * 0.34, -0.05, 0.6), (0.16, 0.5, 0.12), STEEL)
            mb.box((s * 0.34, 0.1, 0.33), (0.08, 0.08, 0.3), STEEL)
            nc.box((s * 0.34, -0.12, 0.665), (0.12, 0.2, 0.01), "M_IntBlack")
            nc.cylinder((s * 0.34, -0.15, 0.665), 0.02, 0.15, "M_IntBlack", seg=8)               # joysticks
            nc.sphere((s * 0.34, -0.15, 0.83), 0.035, "M_IntFabricRed" if s < 0 else "M_IntBlack", seg=8, rings=5)
            for k in range(3):
                nc.box((s * 0.34 + (k - 1) * 0.035, -0.25, 0.67), (0.025, 0.025, 0.012), K.FABRICS[k + (s > 0) * 3])
    for s, xa, xb in ((-1, ix0, ix0 + 0.38), (1, ix1 - 0.38, ix1)):                             # side consoles
        mb.box_mm((xa, iy0, fz), (xb, iy0 + 1.15, fz + 0.75), STEEL)
        with nc.at(((xa + xb) / 2, iy0 + 0.6, fz + 0.75), rot_y=-s * 18):
            nc.box((0, 0, 0.01), (0.32, 1.05, 0.02), "M_IntBlack")
            nc.box((0, -0.25, 0.022), (0.24, 0.3, 0.004), "M_IntScreen")
            nc.box((0, 0.2, 0.022), (0.24, 0.3, 0.004), "M_IntScreen")
            for k in range(6):
                nc.box((-0.08 + (k % 3) * 0.08, 0.45 - (k // 3) * 0.06 - 0.05, 0.025), (0.04, 0.035, 0.01),
                       K.FABRICS[k])
    with mb.at((ix1, iy1 - 0.35, fz + 1.15), rot=-90.0), nc.at((ix1, iy1 - 0.35, fz + 1.15), rot=-90.0):
        mb.box((0, -0.15, -0.015), (0.6, 0.3, 0.03), STEEL)                                  # radio shelf
        nc.box((0.05, -0.14, 0.07), (0.32, 0.22, 0.14), "M_IntBlack")                        # VHF radio
        nc.box((0.05, -0.252, 0.08), (0.12, 0.004, 0.05), "M_IntScreen")
        for k in range(3):
            nc.cylinder((-0.06 + k * 0.08, -0.255, 0.045), 0.012, 0.01, "M_IntMetal", seg=6)
        nc.box((-0.2, -0.17, 0.05), (0.06, 0.1, 0.1), "M_IntBlack")                           # handset
        nc.cylinder((0.18, -0.12, 0.14), 0.006, 0.35, "M_IntBlack", seg=4)                    # antenna
    nc.cylinder((ix1 - 0.19, iy0 + 1.0, fz + 0.75), 0.04, 0.24, "M_IntFabricGreen", seg=8)    # thermos
    with nc.at((ix0 + 0.19, iy0 + 0.95, fz + 0.75)):                                          # logbook
        nc.box((0, 0, 0.012), (0.2, 0.28, 0.024), "M_IntFabricNavy")
    aset.prop("SM_Int_Extinguisher", (ix0 + 0.18, iy1 - 0.2, fz), 90.0)
    _vest_hooks(nc, ix0, iy1 - 0.4, fz + 1.75, 90.0, n=1, vests=1, helmets=False)
    _wall_clipboards(nc, ix0 + 0.15, iy1, fz + 1.5, 0.0, n=1, seed=4)
    DT.blinds(nc, cx, iy0, fz + 0.35, fz + 2.1, 180.0, 1.7, 0.2)
    _dress(aset, mb, nc, ix0, iy0, ix1, iy1, fz, cz, "service", seed=71)
    K.panel_light(aset, nc, cx, iy0 + 0.55, cz, w=0.6, d=0.25, intensity=1500.0, radius=4.0)
    aset.text("CRANE 3", (X1 + 0.03, ty + 0.3, cz - 0.25), -90.0 + 180.0, size=0.18, color=(0.1, 0.25, 0.62))
    K.camera(aset, "crane_cab", (X1 - 0.75, Y1 - 0.4, fz + 1.65), (cx - 0.2, Y0 - 0.4, fz + 0.4), 13.0)
    # ---- catwalk from the cab door to the stair tower (hangs from the boom girder above)
    cw0, cw1 = cx - 0.55, cx + 0.55
    yc0, yc1 = Y1, RAIL_LAND + 0.8
    mb.box_mm((cw0, yc0, fz - 0.06), (cw1, yc1, fz), "M_IntMetal", mats={"-z": DMETAL})
    for xx in (cw0 + 0.03, cw1 - 0.03):
        mb.railing([(xx, yc0 + 0.05, fz), (xx, yc1, fz)], 1.0, Y, post_spacing=1.2, post_size=0.05, rail_size=0.05)
    yh = yc0 + 0.6
    while yh < yc1:
        for xx in (cw0, cw1):
            mb.box((xx, yh, (fz + top) / 2), (0.05, 0.05, top - fz), DMETAL)
        mb.box_mm((cw0 - 0.05, yh - 0.04, top - 0.08), (x + 2.85, yh + 0.04, top), DMETAL)
        yh += 2.4
    # ---- stair tower (land side of the rail): lane A climbs south, lane B north
    la, lb, wd = cx - 0.5, cx + 0.5, 0.9
    ys, yn = yc1, yc1 + 1.0 + 2.8 + 1.0           # south / north faces of the tower
    tx0, tx1 = la - 0.45, lb + 0.45
    for (k, lane, yaw, ystart) in ((0, la, -90.0, yn - 1.0), (1, lb, 90.0, ys + 1.0), (2, la, -90.0, yn - 1.0),
                                   (3, lb, 90.0, ys + 1.0), (4, la, -90.0, yn - 1.0)):
        K.stairs(mb, lane, ystart, k * 1.8, (k + 1) * 1.8, yaw, wd, mat="M_IntMetal", riser=None, stringer=DMETAL,
                 rail=Y, run=0.28, rail_sides=(1, -1))
    for z in (1.8, 5.4, fz):                                                              # south landings
        mb.box_mm((tx0, ys, z - 0.08), (tx1, ys + 1.0, z), "M_IntMetal", mats={"-z": DMETAL})
    for z in (3.6, 7.2):                                                                  # north landings
        mb.box_mm((tx0, yn - 1.0, z - 0.08), (tx1, yn, z), "M_IntMetal", mats={"-z": DMETAL})
    rk = dict(post_spacing=0.8, post_size=0.05, rail_size=0.05)
    for z in (1.8, 5.4):
        mb.railing([(tx0 + 0.03, ys + 1.0, z), (tx0 + 0.03, ys + 0.03, z), (tx1 - 0.03, ys + 0.03, z),
                    (tx1 - 0.03, ys + 1.0, z)], 1.0, Y, **rk)
    mb.railing([(tx0 + 0.03, yn - 1.0, 3.6), (tx0 + 0.03, yn - 0.03, 3.6), (tx1 - 0.03, yn - 0.03, 3.6),
                (tx1 - 0.03, yn - 1.0, 3.6)], 1.0, Y, **rk)
    for xx in (tx0 + 0.03, tx1 - 0.03):                         # 7.2 m landing opens north onto the bridge
        mb.railing([(xx, yn - 1.0, 7.2), (xx, yn, 7.2)], 1.0, Y, **rk)
    mb.railing([(cw0, ys + 0.03, fz), (tx0 + 0.03, ys + 0.03, fz), (tx0 + 0.03, ys + 1.0, fz)], 1.0, Y, **rk)
    mb.railing([(cw1, ys + 0.03, fz), (tx1 - 0.03, ys + 0.03, fz), (tx1 - 0.03, ys + 1.0, fz),
                (lb - wd / 2, ys + 1.0, fz)], 1.0, Y, **rk)
    for px in (tx0 - 0.06, tx1 + 0.06):                                                   # tower posts
        for py in (ys - 0.06, yn + 0.06):
            mb.box((px, py, (fz + 1.1) / 2), (0.12, 0.12, fz + 1.1), Y)
    for z in (1.8, 3.6, 5.4, 7.2):
        for px in (tx0 - 0.06, tx1 + 0.06):
            mb.beam((px, ys - 0.06, z - 1.7), (px, yn + 0.06, z), 0.06, 0.06, Y)
    nc.box((cx - 0.5, yn + 0.08, 1.5), (0.6, 0.02, 0.4), "M_CrateYellow")
    aset.text("CRANE CAB - STAFF ONLY", (cx - 0.5, yn + 0.1, 1.48), 180.0, size=0.06, color=(0.1, 0.1, 0.1))
    _crane_machinery(aset, mb, nc, x, top, by1, tx0, tx1, la, lb, yn)


def _crane_machinery(aset, mb, nc, x, top, by1, tx0, tx1, la, lb, yn):
    """Walk-in machinery house on the back reach (floor 13.5, real windows towards the sea): hoist winch, trolley
    drives, switch cabinets, workbench. Reached from the stair tower: a bridge at the 7.2 m landing leads to a
    second stair stack north of the house (flights 7.2 -> 13.5) and a door in the house's land-side wall."""
    Y = CRANE_Y
    X0, X1, Y0, Y1 = x - 3.3, x + 3.3, -33.5, by1 + 0.3
    fz, cz = top + 1.5, top + 4.3
    mb.box_mm((X0, Y0, fz - 0.1), (X1, Y1, fz), WHITE, mats={"+z": "M_IntMetal"})
    us = _frames(mb, (X0, Y0), (X1, Y0), top + 2.6, 3, 1.2, 0.8)
    dc = X1 - la
    for p0, p1, ops in (((X0, Y0), (X1, Y0), _wins(us, 1.2, top + 2.6 - fz, top + 3.4 - fz)),
                        ((X1, Y0), (X1, Y1), []), ((X1, Y1), (X0, Y1), [K.Door(dc, 0.9, 2.05, "metal")]),
                        ((X0, Y1), (X0, Y0), [])):
        K.wall(aset, mb, p0, p1, fz, cz - fz, 0.15, WHITE, inner=K.PLASTER_WHITE, openings=ops, trim=TRIM,
               trim_in=K.TRIM_WHITE)
    mb.box_mm((X0 - 0.2, Y0 - 0.2, cz), (X1 + 0.2, Y1 + 0.2, cz + 0.2), BLUE, mats={"-z": K.CEIL})
    ix0, ix1, iy0, iy1 = X0 + 0.15, X1 - 0.15, Y0 + 0.15, Y1 - 0.15
    with mb.at((0.0, 0.0, fz)), nc.at((0.0, 0.0, fz)):
        # hoist winch: drum on two pedestals, motor, gearbox, brake
        for sx in (-1.4, 1.4):
            mb.box((x + sx, -30.6, 0.4), (0.3, 1.0, 0.8), STEEL)
        with mb.at((x - 1.3, -30.6, 0.9), rot_y=90):
            mb.cylinder((0, 0, 0), 0.55, 2.6, Y, seg=16)
            for k in range(9):
                mb.torus((0, 0, 0.25 + k * 0.26), 0.56, 0.025, "M_IntBlack", seg=16, tube_seg=3)
        mb.box((x + 1.9, -30.6, 0.55), (0.6, 0.8, 1.1), DMETAL)                               # gearbox
        with mb.at((x + 2.2, -30.6, 0.65), rot_y=90):
            mb.cylinder((0, 0, 0), 0.35, 0.8, "M_AcademyBlue", seg=14)                       # motor
        with mb.at((x - 1.45, -30.6, 0.9), rot_y=90):
            mb.cylinder((0, 0, -0.08), 0.62, 0.06, "M_IntMetal", seg=16)                     # brake disc
        mb.box_mm((x - 1.9, -31.4, 0.0), (x + 2.8, -29.8, 0.06), Y)                           # drip tray / plinth
        # trolley-drive motors by the sea wall
        for xx in (x - 2.2, x + 2.2):
            mb.box((xx, iy0 + 0.6, 0.3), (0.8, 0.6, 0.6), DMETAL)
            with mb.at((xx, iy0 + 0.6, 0.75), rot_y=90):
                mb.cylinder((0, 0, -0.35), 0.22, 0.7, "M_AcademyBlue", seg=12)
        # switch cabinets along the north wall (west of the door)
        for k in range(4):
            cxk = ix0 + 0.35 + k * 0.65
            mb.box((cxk, iy1 - 0.25, 1.0), (0.6, 0.5, 2.0), "M_IntSteelBlue")
            for j in range(3):
                nc.box((cxk - 0.15 + j * 0.15, iy1 - 0.505, 1.6), (0.05, 0.01, 0.05),
                       ("M_DetExit", "M_DetLed", "M_IntTrimGold")[j])
            nc.box((cxk, iy1 - 0.505, 1.15), (0.3, 0.01, 0.2), "M_IntScreen")
            nc.box((cxk + 0.22, iy1 - 0.52, 0.9), (0.03, 0.03, 0.15), "M_IntBlack")
        # workbench + tool board on the east wall, oil drums, rope reel, desk with the log
        with mb.at((ix1 - 0.35, -29.4, 0.0), rot=-90.0), nc.at((ix1 - 0.35, -29.4, 0.0), rot=-90.0):
            mb.box((0, 0, 0.88), (1.8, 0.7, 0.05), "M_IntWood")
            for sx in (-1, 1):
                mb.box((sx * 0.85, 0, 0.43), (0.06, 0.6, 0.86), STEEL)
            mb.box((0, 0, 0.2), (1.7, 0.6, 0.03), STEEL)
            nc.box((0, 0.36, 1.6), (1.6, 0.02, 0.9), "M_IntCork")
            rt = random.Random(3)
            for k in range(7):
                nc.box((-0.6 + k * 0.2, 0.34, rt.uniform(1.4, 1.8)), (0.04, 0.02, rt.uniform(0.15, 0.35)),
                       rt.choice((STEEL, "M_IntFabricRed", "M_IntBlack", ORANGE)))
            nc.box((-0.4, 0.0, 0.94), (0.4, 0.22, 0.08), "M_IntFabricRed")
            nc.cylinder((0.5, 0.1, 0.905), 0.06, 0.18, "M_IntMetal", seg=8)
        aset.prop("SM_Barrel", (ix0 + 0.4, -31.6, fz), 10.0, scale=0.62)
        aset.prop("SM_Barrel", (ix0 + 0.4, -32.15, fz), 70.0, scale=0.62)
        with mb.at((ix0 + 0.5, -28.6, 0.0)):                                                  # spare wire-rope reel
            with mb.at((0, 0, 0.45), rot_x=90):
                mb.cylinder((0, 0, -0.3), 0.45, 0.04, "M_IntWood", seg=12)
                mb.cylinder((0, 0, 0.26), 0.45, 0.04, "M_IntWood", seg=12)
                mb.cylinder((0, 0, -0.26), 0.32, 0.52, "M_IntMetal", seg=12)
        K.desk(mb, nc, x + 0.35, iy1 - 0.32, 0.0, w=1.0, d=0.55, top="M_IntWood", legs=STEEL, hutch=False, clutter=False)
        DT.desk_set(nc, _Shifted(aset, (0.0, 0.0, fz)), x + 0.35, iy1 - 0.32, 0.76, 0.0, "office", seed=81,
                    w=1.0, d=0.55)
        mb.cylinder((x + 0.35, iy1 - 0.95, 0.0), 0.2, 0.45, STEEL, seg=8)
    aset.prop("SM_Int_Extinguisher", (x + 2.4, iy1 - 0.2, fz), 180.0)
    _vest_hooks(nc, ix0, -29.3, fz + 1.75, 90.0, n=3, vests=2)
    _first_aid(nc, aset, ix0, -30.4, fz + 1.55, 90.0)
    _whiteboard(nc, aset, ix1, -31.6, fz + 1.0, -90.0, 1.0, 0.75, ("ROPE CHECK  MON", "GREASE DRUM  WED",
                                                                 "BRAKE TEST  FRI"))
    _dress(aset, mb, nc, ix0, iy0, ix1, iy1, fz, cz, "service", seed=82)
    for px_ in (x - 1.6, x + 1.6):
        K.panel_light(aset, nc, px_, -30.1, cz, w=1.2, d=0.3, intensity=2500.0, radius=7.0)
    aset.text("MACHINERY", (X1 - 1.0, Y1 + 0.03, cz - 0.3), 0.0 + 180.0, size=0.16, color=(0.1, 0.25, 0.62))
    K.camera(aset, "crane_machinery", (ix0 + 0.4, iy1 - 0.9, fz + 1.65), (x + 1.8, -31.4, fz + 0.6), 14.0)
    # ---- bridge from the 7.2 m landing + second stair stack north of the house (7.2 -> 13.5)
    rk = dict(post_spacing=0.8, post_size=0.05, rail_size=0.05)
    wd = 0.9
    s0 = Y1 + 0.1                                      # south face of the new stack (-26.6)
    s1 = s0 + 1.0 + 2.8 + 1.0                          # north face
    mb.box_mm((tx0, yn, 7.12), (tx1, s0, 7.2), "M_IntMetal", mats={"-z": DMETAL})
    for xx in (tx0 + 0.03, tx1 - 0.03):
        mb.railing([(xx, yn, 7.2), (xx, s0 + 1.0, 7.2)], 1.0, Y, **rk)
    for k, (lane, yaw, ystart, za) in enumerate(((lb, 90.0, s0 + 1.0, 7.2), (la, -90.0, s1 - 1.0, 9.0),
                                                (lb, 90.0, s0 + 1.0, 10.8))):
        K.stairs(mb, lane, ystart, za, za + 1.8, yaw, wd, mat="M_IntMetal", stringer=DMETAL, rail=Y, run=0.28,
                 rail_sides=(1, -1))
    K.stairs(mb, la, s1 - 1.0, 12.6, fz, -90.0, wd, mat="M_IntMetal", stringer=DMETAL, rail=Y, run=0.28,
             rail_sides=(1, -1))
    top_y = s1 - 1.0 - 0.28 * round((fz - 12.6) / 0.18)
    mb.box_mm((tx0, s0, 7.12), (tx1, s0 + 1.0, 7.2), "M_IntMetal", mats={"-z": DMETAL})
    mb.box_mm((tx0, s0, 10.72), (tx1, s0 + 1.0, 10.8), "M_IntMetal", mats={"-z": DMETAL})
    for z in (9.0, 12.6):
        mb.box_mm((tx0, s1 - 1.0, z - 0.08), (tx1, s1, z), "M_IntMetal", mats={"-z": DMETAL})
        mb.railing([(tx0 + 0.03, s1 - 1.0, z), (tx0 + 0.03, s1 - 0.03, z), (tx1 - 0.03, s1 - 0.03, z),
                    (tx1 - 0.03, s1 - 1.0, z)], 1.0, Y, **rk)
    mb.railing([(tx0 + 0.03, s0 + 1.0, 10.8), (tx0 + 0.03, s0 + 0.03, 10.8), (tx1 - 0.03, s0 + 0.03, 10.8),
                (tx1 - 0.03, s0 + 1.0, 10.8)], 1.0, Y, **rk)
    for xx in (tx1 - 0.03,):
        mb.railing([(xx, s0, 7.2), (xx, s0 + 1.0, 7.2)], 1.0, Y, **rk)
    mb.box_mm((tx0, Y1, fz - 0.08), (la + wd / 2, top_y, fz), "M_IntMetal", mats={"-z": DMETAL})   # top landing
    mb.railing([(la + wd / 2 - 0.03, Y1 + 0.05, fz), (la + wd / 2 - 0.03, top_y, fz)], 1.0, Y, **rk)
    mb.railing([(tx0 + 0.03, Y1 + 0.05, fz), (tx0 + 0.03, top_y, fz)], 1.0, Y, **rk)
    for px in (tx0 - 0.06, tx1 + 0.06):
        for py in (s0 - 0.06, s1 + 0.06):
            mb.box((px, py, (fz + 1.1) / 2), (0.12, 0.12, fz + 1.1), Y)
    for z in (9.0, 10.8, 12.6):
        for px in (tx0 - 0.06, tx1 + 0.06):
            mb.beam((px, s0 - 0.06, z - 1.7), (px, s1 + 0.06, z), 0.06, 0.06, Y)
    K.camera(aset, "crane_stair", (tx1 - 0.2, s0 + 0.3, 7.2 + 1.65), (la, s1 - 0.5, 9.5), 14.0)


# ================================================================== TERMINAL
def _terminal(aset, mb, nc, im, inc):
    """Ferry terminal: waiting hall (glass doors north + south) and the harbor-master tower (ticket office +
    stair lobby on the ground floor, glazed control room upstairs). All walls are real, windows are cut."""
    hx0, hx1, hy0, hy1, hh = 22.0, 38.0, 12.0, 24.0, 5.0
    tx0, tx1, ty0, ty1, th = 38.0, 46.0, 13.0, 23.0, 9.0
    WT = 0.25
    HALL_IN, TOWER_IN = K.PLASTER_WHITE, K.PLASTER_SKY
    tz = 6.0                       # control room floor (the blue band at 5.6 .. 6.0 is the slab edge)
    # ---------------------------------------------------------------- hall shell
    for (a, b), (c, e) in ((((21.92, 11.92), (28.6, 12.0)), ((31.4, 11.92), (38.08, 12.0))),
                           (((21.92, 24.0), (28.6, 24.08)), ((31.4, 24.0), (38.0, 24.08)))):
        mb.box_mm((a[0], a[1], 0.0), (b[0], b[1], 0.45), CONC)                                # plinth strips
        mb.box_mm((c[0], c[1], 0.0), (e[0], e[1], 0.45), CONC)
    mb.box_mm((21.92, 12.0, 0.0), (22.0, 24.0, 0.45), CONC)
    mb.box_mm((38.0, 12.0, 0.0), (38.08, 12.92, 0.45), CONC)
    mb.box_mm((38.0, 23.08, 0.0), (38.08, 24.0, 0.45), CONC)
    mb.box_mm((hx0 + WT, hy0 + WT, -0.2), (hx1 - WT, hy1 - WT, 0.005), "M_IntTileWhite", skip=("-z",))
    for yy in (hy0, hy1):                                                                  # door thresholds
        mb.box_mm((28.88, yy - 0.12, -0.2), (31.12, yy + 0.12, 0.005), "M_IntTileWhite", skip=("-z",))
    mb.box_mm((28.4, hy0 - 1.6, -0.2), (31.6, hy0 - 0.12, 0.01), DCONC, skip=("-z",))      # entrance aprons
    mb.box_mm((28.4, hy1 + 0.12, -0.2), (31.6, hy1 + 1.6, 0.01), DCONC, skip=("-z",))
    s1 = _frames(mb, (hx0, hy0), (28.6, hy0), 1.0, 2, 1.8, 2.0)
    s2 = _frames(mb, (31.4, hy0), (hx1, hy0), 1.0, 2, 1.8, 2.0)
    n1 = _frames(mb, (hx1, hy1), (31.4, hy1), 1.0, 2, 1.8, 2.0)
    n2 = _frames(mb, (28.6, hy1), (hx0, hy1), 1.0, 2, 1.8, 2.0)
    w1 = _frames(mb, (hx0, hy1), (hx0, hy0), 1.0, 3, 1.8, 2.0)
    glass_door = dict(w=2.24, h=2.55, style="glass", double=True)
    kw = dict(trim=None, trim_in=K.TRIM_WHITE)
    K.wall(aset, mb, (hx0, hy0), (hx1, hy0), 0.0, hh, WT, WHITE, inner=HALL_IN,
           openings=_wins(s1, 1.8, 1.0, 3.0) + _wins(s2, 1.8, 1.0, 3.0, off=9.4) + [K.Door(8.0, **glass_door)], **kw)
    K.wall(aset, mb, (hx1, hy1), (hx0, hy1), 0.0, hh, WT, WHITE, inner=HALL_IN,
           openings=_wins(n1, 1.8, 1.0, 3.0) + _wins(n2, 1.8, 1.0, 3.0, off=9.4) + [K.Door(8.0, **glass_door)], **kw)
    K.wall(aset, mb, (hx0, hy1), (hx0, hy0), 0.0, hh, WT, WHITE, inner=HALL_IN, openings=_wins(w1, 1.8, 1.0, 3.0),
           **kw)
    K.wall(aset, mb, (hx1, hy0), (hx1, ty0), 0.0, hh, WT, WHITE, inner=HALL_IN, **kw)
    K.wall(aset, mb, (hx1, ty1), (hx1, hy1), 0.0, hh, WT, WHITE, inner=HALL_IN, **kw)
    # shared wall hall | tower: ticket pass-through window + door to the stair lobby
    K.wall(aset, mb, (hx1, ty0), (hx1, ty1), 0.0, 5.6, WT, TOWER_IN, inner=HALL_IN,
           openings=[K.Window(1.8, 1.6, 1.0, 2.2, frame=K.TRIM_WHITE, mullions=0),
                     K.Door(8.0, 1.0, 2.1, "office")], trim=K.TRIM_WHITE, trim_in=K.TRIM_WHITE)
    mb.box_mm((hx0 - 0.12, hy0 - 0.12, hh - 0.45), (hx1, hy1 + 0.12, hh), BLUE)
    mb.hip_roof(((hx0 + hx1) / 2, (hy0 + hy1) / 2, hh), hx1 - hx0, hy1 - hy0, 1.8, ROOF_BLUE, overhang=0.7)
    for yy, s in ((hy0, -1), (hy1, 1)):                                                    # blue door frames
        y_a, y_b = sorted((yy + s * 0.01, yy + s * 0.11))
        mb.box_mm((28.6, y_a, 0.0), (28.88, y_b, 2.7), BLUE)
        mb.box_mm((31.12, y_a, 0.0), (31.4, y_b, 2.7), BLUE)
        mb.box_mm((28.88, y_a, 2.55), (31.12, y_b, 2.7), BLUE)

    # ---------------------------------------------------------------- tower shell
    mb.box_mm((tx0, ty0 - 0.08, 0.0), (tx1 + 0.08, ty0, 0.45), CONC)
    mb.box_mm((tx0, ty1, 0.0), (tx1 + 0.08, ty1 + 0.08, 0.45), CONC)
    mb.box_mm((tx1, ty0, 0.0), (tx1 + 0.08, ty1, 0.45), CONC)
    mb.box_mm((tx0, ty0, -0.2), (tx1 - WT, ty1 - WT, 0.005), "M_IntLinoleum", skip=("-z",))
    e1 = _frames(mb, (tx1, ty0), (tx1, ty1), 1.2, 3, 1.4, 1.6)
    nn = _frames(mb, (tx1, ty1), (tx0, ty1), 1.2, 2, 1.4, 1.6)
    kt = dict(trim=None, trim_in=K.TRIM_WHITE)
    K.wall(aset, mb, (tx0, ty0), (tx1, ty0), 0.0, 5.6, WT, WHITE, inner=TOWER_IN,
           openings=[K.Window(4.0, 2.0, 1.05, 2.25, glass=GLASS_IN, frame=TRIM, mullions=0)], **kt)
    K.wall(aset, mb, (tx1, ty0), (tx1, ty1), 0.0, 5.6, WT, WHITE, inner=TOWER_IN, openings=_wins(e1, 1.4, 1.2, 2.8),
           **kt)
    K.wall(aset, mb, (tx1, ty1), (tx0, ty1), 0.0, 5.6, WT, WHITE, inner=TOWER_IN, openings=_wins(nn, 1.4, 1.2, 2.8),
           **kt)
    # floor slab of the control room (stairwell for the spiral stair), blue band = slab edge
    scx, scy = 44.45, 21.45
    K.slab(mb, tx0, ty0, tx1, ty1, tz, 0.4, "M_IntWoodFloor", bottom=K.CEIL, side=BLUE,
           holes=[(scx - 1.25, scy, tx1 - WT, ty1 - WT), (scx, scy - 1.25, tx1 - WT, scy)])
    for a, b in (((tx0 - 0.1, ty0 - 0.1), (tx1 + 0.1, ty0)), ((tx0 - 0.1, ty1), (tx1 + 0.1, ty1 + 0.1)),
                 ((tx0 - 0.1, ty0), (tx0, ty1)), ((tx1, ty0), (tx1 + 0.1, ty1))):
        mb.box_mm((a[0], a[1], 5.6), (b[0], b[1], tz), BLUE)
    # control room walls: wrap-around window band 6.25 .. 8.35
    up = dict(trim=None, trim_in=K.TRIM_WHITE)
    for p0, p1 in (((tx0, ty0), (tx1, ty0)), ((tx1, ty0), (tx1, ty1)), ((tx1, ty1), (tx0, ty1)),
                   ((tx0, ty1), (tx0, ty0))):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        K.wall(aset, mb, p0, p1, tz, th - tz, 0.2, WHITE, inner=K.PLASTER_WHITE,
               openings=[K.Window(L / 2, L - 0.3, 0.25, 2.35, glass=GLASS_IN, frame=TRIM, mullions=0)], **up)
    mb.box_mm((tx0 - 0.12, ty0 - 0.12, th - 0.4), (tx1 + 0.12, ty1 + 0.12, th), BLUE)
    loop = [(tx0, ty0), (tx1, ty0), (tx1, ty1), (tx0, ty1), (tx0, ty0)]
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
    # ticket window (south face of the tower): frame bars around the real opening
    mb.box_mm((40.9, ty0 - 0.06, 0.95), (41.0, ty0, 2.35), TRIM)
    mb.box_mm((43.0, ty0 - 0.06, 0.95), (43.1, ty0, 2.35), TRIM)
    mb.box_mm((41.0, ty0 - 0.06, 2.25), (43.0, ty0, 2.35), TRIM)
    mb.box_mm((40.8, ty0 - 0.5, 0.95), (43.2, ty0, 1.05), TRIM)
    mb.box_mm((40.6, ty0 - 0.9, 2.5), (43.4, ty0, 2.62), BLUE)
    nc.box((42.0, ty0 + WT / 2, 1.55), (0.2, 0.05, 0.2), "M_IntMetal")                      # speaking grille
    aset.text("TICKETS", (42.0, ty0 - 0.03, 2.95), 0.0, size=0.3, color=(0.10, 0.25, 0.62))
    aset.light((42.0, ty0 - 0.6, 2.4), (1.0, 0.9, 0.7), 2000.0, 5.0, night_only=True)
    aset.text("HARBOR OFFICE", (42.0, ty0 - 0.03, 4.75), 0.0, size=0.42, color=(0.10, 0.25, 0.62))

    # ---------------------------------------------------------------- outside: canopy, sign, timetable
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
    mb.sign_board((17.6, 5.4, 1.7), 1.8, 1.2, BLUE, TRIM, thick=0.12)
    aset.text("FERRY TIMETABLE", (17.6, 5.4 - 0.06 - 0.025, 2.05), 0.0, size=0.15, color=(1, 1, 1))
    aset.text("MON  10:00  DOMINO CITY", (17.6, 5.4 - 0.06 - 0.025, 1.6), 0.0, size=0.1, color=(1.0, 0.85, 0.3))
    aset.interact("sign", (17.6, 4.6, 1.0), 0.0, title="Ferry Timetable",
                  text="The ferry from Domino City arrives every Monday. Welcome to Duel Academy!")
    for i, f in enumerate(("SM_Flagpole_Red", "SM_Flagpole_Yellow", "SM_Flagpole_Blue")):
        aset.prop(f, (10.0 + i * 2.6, 8.0, 0.0), 0.0)
    for px in (19.0, 47.2):
        aset.prop("SM_Planter", (px, 13.0, 0.0), 0.0)

    _terminal_hall(aset, mb, im, inc, hx0 + WT, hy0 + WT, hx1 - WT, hy1 - WT)
    _terminal_tower(aset, mb, im, inc, tx0, ty0 + WT, tx1 - WT, ty1 - WT, scx, scy, tz)


def _terminal_hall(A, wm, mb, nc, x0, y0, x1, y1):
    """Waiting hall (inner box x0..x1, y0..y1, floor 0, ceiling 4.4)."""
    ch = 4.4
    rnd = random.Random(33)
    K.ceiling(wm, x0, y0, x1, y1, ch, cornice=K.TRIM_WHITE)
    # floor: blue border + Academy emblem inlay
    for a, b in (((x0, y0), (x1, y0 + 0.45)), ((x0, y1 - 0.45), (x1, y1)), ((x0, y0 + 0.45), (x0 + 0.45, y1 - 0.45)),
                 ((x1 - 0.45, y0 + 0.45), (x1, y1 - 0.45))):
        mb.box_mm((a[0], a[1], 0.005), (b[0], b[1], 0.009), "M_IntTileBlue", skip=("-z",))
    mb.cylinder((30.0, 18.0, 0.005), 1.6, 0.005, "M_IntTileBlue", seg=32, cap_bottom=False)
    mb.cylinder((30.0, 18.0, 0.007), 1.25, 0.005, "M_IntTrimGold", seg=32, cap_bottom=False)
    mb.cylinder((30.0, 18.0, 0.009), 1.1, 0.005, "M_IntTileBlue", seg=32, cap_bottom=False)
    star = [((0.95 if k % 2 == 0 else 0.4) * math.cos(math.pi / 2 + k * math.pi / 5),
             (0.95 if k % 2 == 0 else 0.4) * math.sin(math.pi / 2 + k * math.pi / 5)) for k in range(10)]
    mb.prism([(30.0 + px, 18.0 + py) for px, py in star], 0.011, 0.016, "M_IntTrimGold", cap_bottom=False)
    # blue dado
    for p0, p1, gaps in (((x0, y0), (x1, y0), [(6.5, 9.0)]), ((x1, y1), (x0, y1), [(6.5, 9.0)]),
                         ((x0, y1), (x0, y0), []), ((x1, y0), (x1, y1), [(8.1, 9.4)])):
        K.wainscot(mb, p0, p1, 0.0, 0.9, "M_IntWallpaperBlue", cap=K.TRIM_WHITE, gaps=gaps)
    # lights: panels + two ceiling fans (island breeze)
    for px in (25.0, 30.0, 35.0):
        for py in (15.0, 21.0):
            K.panel_light(A, nc, px, py, ch)
    A.prop("SM_Int_CeilingFan", (25.6, 18.0, ch), 0.0)
    A.prop("SM_Int_CeilingFan", (34.4, 18.0, ch), 15.0)
    # benches facing the departure board (east), suitcases
    for bx in (23.7, 25.5, 27.3):
        for by in (14.3, 16.1, 19.9, 21.7):
            A.prop("SM_Int_Bench", (bx, by, 0.0), 90.0)
    for (px, py, yw) in ((24.4, 15.2, 80.0), (26.3, 20.8, 100.0), (28.0, 16.9, 95.0)):
        A.prop("SM_Int_Suitcase", (px, py, 0.0), yw)
    A.prop("SM_Int_Basket", (24.6, 22.6, 0.0), 0.0)
    # departure board + clock on the tower wall
    bx = x1 - 0.01
    with mb.at((bx, 17.6, 3.0), rot=-90.0), nc.at((bx, 17.6, 3.0), rot=-90.0):
        mb.box((0, -0.04, 0), (3.4, 0.08, 1.45), BLUE)
        nc.box((0, -0.085, 0), (3.2, 0.012, 1.25), "M_IntBlack")
        nc.box((0, -0.09, 0.47), (3.2, 0.012, 0.03), "M_IntTrimGold")
    lines = [("DEPARTURES", (1.0, 1.0, 1.0)), ("10:00  DOMINO CITY       ON TIME", (1.0, 0.85, 0.3)),
             ("13:30  NORTH ACADEMY     BOARDING", (0.4, 1.0, 0.5)), ("16:00  BATTLE CITY PIER  ON TIME", (1.0, 0.85, 0.3)),
             ("18:45  DOMINO CITY       DELAYED", (1.0, 0.45, 0.35))]
    for i, (t, col) in enumerate(lines):
        A.text(t, (bx - 0.1, 17.6, 3.55 - i * 0.24 - (0.04 if i else 0.0)), -90.0, size=0.15 if i else 0.2, color=col,
               emissive=True)
    A.prop("SM_Int_WallClock", (bx, 17.6, 3.9), -90.0)
    A.prop("SM_VendingMachine", (x1 - 0.5, 18.3, 0.0), -90.0)
    # ticket counter at the pass-through window (the clerk sits in the tower)
    K.counter(mb, x1 - 0.7, 13.7, x1, 15.9, h=1.0, body=BLUE, top=K.TRIM_WHITE)
    with mb.at((x1 - 0.02, 14.8, 2.45), rot=-90.0):
        mb.box((0, -0.03, 0), (1.9, 0.06, 0.38), BLUE)
    A.text("TICKETS", (x1 - 0.08, 14.8, 2.38), -90.0, size=0.2, color=(1, 1, 1))
    for (px, py) in ((33.8, 14.15), (36.2, 14.15), (33.8, 15.45), (36.2, 15.45)):         # queue stanchions
        mb.cylinder((px, py, 0.0), 0.16, 0.03, "M_IntMetal", seg=10)
        mb.cylinder((px, py, 0.0), 0.03, 0.95, "M_IntMetal", seg=8)
    for yy in (14.15, 15.45):
        nc.box_mm((33.8, yy - 0.02, 0.86), (36.2, yy + 0.02, 0.92), "M_IntFabricBlue")
    # card kiosk island
    K.counter(mb, 32.6, 18.8, 35.0, 19.5, h=1.0, body="M_IntWood", top=K.TRIM_WHITE)
    A.prop("SM_Int_Register", (34.4, 19.15, 1.0), 180.0)
    for k in range(5):
        nc.box((32.9 + k * 0.28, 19.1, 1.07), (0.2, 0.3, 0.14), K.POSTERS[k % 4])          # booster boxes
    A.text("CARD PACKS", (33.8, 18.8, 0.6), 0.0, size=0.18, color=(1.0, 0.85, 0.3))
    A.prop("SM_Int_Stool", (33.8, 20.0, 0.0), 0.0)
    # plants, bin, extinguisher
    A.prop("SM_Int_PottedPlantB", (x0 + 0.5, y0 + 0.5, 0.0), 0.0)
    A.prop("SM_Int_PottedPlantB", (x0 + 0.5, y1 - 0.5, 0.0), 0.0)
    A.prop("SM_Int_PottedPlantB", (x1 - 0.5, y1 - 0.5, 0.0), 0.0)
    A.prop("SM_Int_PottedPlant", (32.2, y0 + 0.35, 0.0), 0.0)
    A.prop("SM_TrashBin", (27.6, y0 + 0.45, 0.0), 0.0)
    A.prop("SM_Int_Extinguisher", (32.0, y1 - 0.2, 0.0), 180.0)
    # posters between the west windows, door signs
    K.poster(nc, A, x0, 16.37, 2.0, 90.0, 1.0, 1.35, "M_IntPoster2", "WELCOME TO", text_size=0.11)
    A.text("DUEL ACADEMY!", K.wall_point(x0, 16.37, 90.0, 0.02, 1.75), 90.0, size=0.12, color=(1.0, 0.9, 0.3))
    K.poster(nc, A, x0, 19.63, 2.0, 90.0, 1.0, 1.35, "M_IntPoster1", "ENTRANCE EXAM", text_size=0.1)
    A.text("THIS WAY  >", K.wall_point(x0, 19.63, 90.0, 0.02, 1.75), 90.0, size=0.1, color=(1, 1, 1))
    for yy, yw, txt in ((y0, 180.0, "FERRY BOARDING"), (y1, 0.0, "DUEL ACADEMY  /  DORMS")):
        p = K.wall_point(30.0, yy, yw, 0.04, 3.25)
        with mb.at((30.0, yy, 3.25), rot=yw):
            mb.box((0, -0.03, 0), (2.6, 0.06, 0.5), BLUE)
        A.text(txt, (p[0], p[1], 3.17), yw, size=0.2, color=(1, 1, 1))
    # ---- detail pass: ticket machines, luggage carts, departures board, souvenir + card stand, posters
    _dress(A, mb, nc, x0, y0, x1, y1, 0.0, ch, "office", seed=31, ac=False, keep_clear=[(x0, 14.0, x0, 22.0)])
    for yy in (16.35, 17.15):
        _ticket_machine(mb, nc, A, x1 - 0.24, yy, -90.0)
    A.text("SELF-SERVICE TICKETS", (x1 - 0.02, 16.75, 2.0), -90.0, size=0.09, color=(0.1, 0.25, 0.62))
    _luggage_cart(mb, nc, 24.2, 12.85, 0.0, 2, seed=1)
    _luggage_cart(mb, nc, 24.7, 23.2, 180.0, 3, seed=2)
    _luggage_cart(mb, nc, 33.0, 12.95, 90.0, 0, seed=3)
    # hanging departures / arrivals board over the north entrance (double-sided)
    bz = 3.0
    for sx in (-1, 1):
        mb.box((30.0 + sx * 1.3, 21.4, (bz + 0.8 + ch) / 2), (0.03, 0.03, ch - bz - 0.8), "M_IntMetal")
    mb.box((30.0, 21.4, bz + 0.4), (3.0, 0.16, 0.85), BLUE)
    for sy, yw, head in ((-1, 0.0, "DEPARTURES"), (1, 180.0, "ARRIVALS")):
        nc.box((30.0, 21.4 + sy * 0.085, bz + 0.38), (2.8, 0.01, 0.7), "M_IntBlack")
        rows = [(head, (1, 1, 1)), ("10:00  DOMINO CITY      GATE 1", (1.0, 0.85, 0.3)),
                ("13:30  NORTH ACADEMY    GATE 1", (0.4, 1.0, 0.5)), ("16:00  BATTLE CITY      GATE 2", (1.0, 0.85, 0.3))]
        if sy > 0:
            rows = [(head, (1, 1, 1)), ("09:40  DOMINO CITY      LANDED", (0.4, 1.0, 0.5)),
                    ("12:15  KAIBA PORT       ON TIME", (1.0, 0.85, 0.3)), ("17:20  NORTH ACADEMY    ON TIME", (1.0, 0.85, 0.3))]
        for i, (t, col) in enumerate(rows):
            A.text(t, (30.0, 21.4 + sy * 0.095, bz + 0.62 - i * 0.16), yw, size=0.13 if i == 0 else 0.1, color=col,
                   emissive=True)
    # souvenir corner + card spinner by the kiosk
    _souvenir_table(mb, nc, A, 35.95, 23.33, 0.0, seed=5)
    _card_spinner(mb, nc, 32.1, 21.9, seed=6)
    A.prop("SM_Int_PottedPlantC", (36.75, 21.95, 0.0), 0.0)
    # posters on the window piers + east wall
    for (px, py, yw, mat, t1, t2) in ((25.3, y0, 180.0, "M_IntPoster3", "ISLAND", "SUMMER FEST"),
                                      (34.69, y0, 180.0, "M_IntPoster1", "DOMINO CITY", "BY SEA"),
                                      (25.3, y1, 0.0, "M_IntPoster4", "SPIRIT", "TOURS"),
                                      (34.69, y1, 0.0, "M_IntPoster2", "TOURNAMENT", "SAT 14:00"),
                                      (x1, 22.6, -90.0, "M_IntPoster1", "DUEL ACADEMY", "OPEN CAMPUS")):
        K.poster(nc, A, px, py, 1.95, yw, 0.62, 0.88, mat, t1, text_size=0.075)
        A.text(t2, K.wall_point(px, py, yw, 0.02, 1.7), yw, size=0.06, color=(1, 1, 1))
    A.prop("SM_Int_WetFloor", (29.1, 22.2, 0.0), 200.0)
    # dorm banners over the west windows, bunting across the hall, entrance mats, floor arrows
    for yy, mat, name in ((14.73, "M_IntFabricRed", "SLIFER"), (18.0, "M_IntFabricYellow", "RA"),
                          (21.27, "M_IntFabricBlue", "OBELISK")):
        nc.box((x0 + 0.02, yy, 4.27), (0.04, 1.0, 0.04), "M_IntTrimGold")
        nc.box((x0 + 0.03, yy, 3.65), (0.012, 0.8, 1.2), mat)
        nc.box((x0 + 0.032, yy, 3.75), (0.01, 0.4, 0.4), "M_IntTrimWhite")
        A.text(name, (x0 + 0.045, yy, 3.3), 90.0, size=0.12, color=(1, 1, 1))
    for by in (15.2, 20.8):
        n = 30
        for k in range(n):
            t = (k + 0.5) / n
            bxk = x0 + 0.3 + (x1 - x0 - 0.6) * t
            zz = 4.05 - 0.35 * math.sin(math.pi * t)
            with nc.at((bxk, by, zz)):
                nc.box((0, 0, -0.12), (0.2, 0.006, 0.24), K.FABRICS[k % 6])
        nc.box_mm((x0 + 0.3, by - 0.004, 4.04), (x1 - 0.3, by + 0.004, 4.05), "M_IntMetal")
    for yy, yw in ((y0 + 0.65, 0.0), (y1 - 0.65, 180.0)):
        nc.box((30.0, yy, 0.012), (2.4, 1.2, 0.012), "M_IntFabricNavy")
        nc.box((30.0, yy, 0.0185), (2.2, 1.0, 0.002), "M_IntFabricBlue")
    for k in range(4):                                                                   # "to the ferry" arrows
        with nc.at((30.0, 14.6 - k * 0.55 + 1.6, 0.012), rot=0.0):
            for sx in (-1, 1):
                with nc.at((sx * 0.14, 0, 0), rot=sx * 40.0):
                    nc.box((0, 0, 0.0), (0.42, 0.09, 0.004), "M_AcademyYellow")
    for (px, py, yw, c) in ((26.4, 15.15, 95.0, "M_IntFabricNavy"), (24.6, 21.0, 80.0, "M_IntFabricRed"),
                            (26.4, 18.95, 100.0, "M_IntFabricGreen")):
        with nc.at((px, py, 0.0), rot=yw):                                               # travellers' bags
            nc.box((0, 0, 0.2), (0.45, 0.25, 0.4), c)
            nc.box((0, 0, 0.43), (0.2, 0.04, 0.06), "M_IntBlack")
    K.camera(A, "terminal_hall", (23.0, 12.9, 1.8), (35.5, 21.5, 1.2), 15.0)
    K.camera(A, "terminal_hall_east", (37.3, 22.45, 1.95), (25.0, 13.5, 0.9), 15.0)


def _terminal_tower(A, wm, mb, nc, x0, y0, x1, y1, scx, scy, tz):
    """Ticket office + stair lobby (ground floor) and the harbor master's control room (floor tz).
    x0 is the hall wall line (the shared wall belongs to the hall)."""
    rnd = random.Random(44)
    gx0 = x0
    py = 16.3                                                   # ticket office | lobby partition
    K.wall(A, wm, (gx0, py), (x1, py), 0.0, 5.6, 0.15, K.PLASTER_SKY, inner=K.PLASTER_SKY,
           openings=[K.Door(3.25, 0.95, 2.1, "office")], trim=K.TRIM_WHITE, trim_in=K.TRIM_WHITE, base=K.TRIM_WOOD)
    # ---- ticket office (dropped ceiling 3.0)
    K.ceiling(wm, gx0, y0, x1, py, 3.0)
    K.counter(mb, 40.6, y0, 43.4, y0 + 0.62, h=0.95, body="M_IntWood", top=K.TRIM_WHITE)
    K.counter(mb, gx0, 13.7, gx0 + 0.55, 15.9, h=1.0, body="M_IntWood", top=K.TRIM_WHITE)
    A.prop("SM_Int_Register", (42.0, y0 + 0.32, 0.95), 180.0)
    A.prop("SM_Int_OfficeChair", (42.0, 14.4, 0.0), 0.0)
    A.prop("SM_Int_OfficeChair", (39.35, 14.8, 0.0), -90.0)
    nc.box((gx0 + 0.3, 15.2, 1.012), (0.35, 0.3, 0.025), "M_IntPaper")                  # ticket rolls
    nc.cylinder((gx0 + 0.3, 14.3, 1.0), 0.06, 0.1, "M_IntPaper", seg=10)
    nc.box((41.3, y0 + 0.3, 0.962), (0.4, 0.28, 0.012), "M_IntPoster2")
    A.prop("SM_Int_Cabinet", (44.7, py - 0.35, 0.0), 0.0)
    mb.box((x1 - 0.35, 13.9, 0.45), (0.6, 0.6, 0.9), "M_IntBlack")                       # safe
    mb.box((x1 - 0.66, 13.9, 0.55), (0.04, 0.16, 0.16), "M_IntTrimGold")
    A.prop("SM_Int_Kettle", (x1 - 0.35, 13.9, 0.9), 0.0)
    K.poster(nc, A, 40.0, py, 1.6, 0.0, 0.7, 0.9, "M_IntPoster3", "FARES", text_color=(0.2, 0.1, 0.05))
    A.prop("SM_Int_WallClock", (43.0, py, 2.25), 0.0)
    K.panel_light(A, nc, 42.0, 14.75, 3.0)
    _dress(A, mb, nc, gx0, y0, x1, py, 0.0, 3.0, "office", seed=41, ac=False)
    A.prop("SM_Int_Laptop", (40.95, y0 + 0.33, 0.95), 0.0)
    nc.box((43.0, y0 + 0.35, 1.0), (0.3, 0.3, 0.1), "M_IntTrimWhite")                     # ticket printer
    nc.box((43.0, y0 + 0.19, 1.03), (0.12, 0.01, 0.006), "M_IntBlack")
    DT.paper_stack(nc, 41.6, y0 + 0.22, 0.95, 90.0, 4, seed=5)
    A.prop("SM_Int_Stapler", (gx0 + 0.3, 13.95, 1.0), 90.0)
    nc.box((gx0 + 0.28, 15.6, 1.03), (0.18, 0.22, 0.06), "M_IntBlack")                    # desk phone
    nc.box((gx0 + 0.28, 15.6, 1.07), (0.05, 0.2, 0.04), "M_IntBlack")
    DT.mug(nc, 43.28, y0 + 0.42, 0.95, seed=3)
    DT.coat_hooks(nc, 38.9, py, 1.75, 0.0, n=2, dorm="obelisk", jackets=1, seed=2)
    _whiteboard(nc, A, 42.95, py, 1.05, 0.0, 1.0, 0.7, ("TODAY: 2 SAILINGS", "STUDENT FARE -50%"))
    with nc.at((x1, 13.9, 1.55), rot=-90.0):                                             # key cabinet
        nc.box((0, -0.04, 0), (0.4, 0.08, 0.5), "M_IntWoodDark")
        for i in range(3):
            for j in range(4):
                nc.box((-0.12 + i * 0.12, -0.085, 0.15 - j * 0.1), (0.02, 0.01, 0.05), "M_IntTrimGold")
    A.prop("SM_Int_Box", (44.6, 14.8, 0.0), 30.0)
    nc.cylinder((39.1, 13.55, 0.0), 0.15, 0.32, STEEL, seg=12, cap_top=False)
    # ---- stair lobby (harbor office reception)
    K.spiral_stairs(mb, scx, scy, 0.0, tz, 0.14, 1.15, a0=-100.0, step_deg=20.0, mat=STEEL, core=STEEL,
                    rail=K.TRIM_WOOD)
    mb.box_mm((gx0, py + 0.15, 0.0), (x1, y1, 0.01), "M_IntTileWhite", skip=("-z",))
    A.prop("SM_Int_Lifebuoy", (gx0 + 0.02, 18.4, 1.35), 90.0)
    A.prop("SM_Int_Lifebuoy", (gx0 + 0.02, 19.3, 1.35), 90.0)
    K.bulletin(nc, A, 39.4, py + 0.15, 1.15, 180.0, 1.4, 0.9, title="HARBOR NOTICES", rng_seed=8)
    A.prop("SM_Int_Bench", (43.5, py + 0.45, 0.0), 180.0)
    A.prop("SM_Int_PottedPlantB", (x1 - 0.45, py + 0.55, 0.0), 0.0)
    A.prop("SM_Int_Extinguisher", (gx0 + 0.25, py + 0.4, 0.0), 0.0)
    # ship model in a glass case
    mb.box((41.6, 19.6, 0.45), (1.2, 0.5, 0.9), "M_IntWoodDark")
    with nc.at((41.6, 19.6, 0.95)):
        nc.box((0, 0, 0.08), (0.8, 0.18, 0.12), "M_ShipHull")
        nc.box((-0.05, 0, 0.19), (0.45, 0.13, 0.1), TRIM)
        nc.cylinder((-0.1, 0, 0.24), 0.04, 0.12, "M_ShipStripe", seg=8)
    wm.box((41.6, 19.6, 1.22), (1.16, 0.46, 0.55), GLASS_IN)
    A.text("S.S. DUEL ACADEMY", (41.6, 19.33, 0.55), 0.0, size=0.07, color=(1.0, 0.85, 0.3))
    K.nameplate(wm, A, 42.0, y1, 1.95, 0.0, "HARBOR MASTER  2F", w=1.1, h=0.18)
    K.pendant(A, 41.2, 19.0, 5.6, "lamp")
    _fill_light(A, 41.5, 18.5, 2.6, 2500.0, 8.0)
    _dress(A, mb, nc, gx0, py + 0.15, x1, y1, 0.0, 5.6, "office", seed=42, ac=False)
    K.counter(mb, 38.55, 21.95, 40.35, 22.55, h=1.0, body=BLUE, top=K.TRIM_WHITE)            # reception
    nc.cylinder((39.95, 22.15, 1.0), 0.05, 0.03, "M_IntTrimGold", seg=10)                  # desk bell
    nc.sphere((39.95, 22.15, 1.03), 0.04, "M_IntTrimGold", seg=8, rings=4, hemi=True)
    DT.paper_stack(nc, 39.3, 22.2, 1.0, 10.0, 5, seed=7)
    with nc.at((38.95, 22.4, 1.0)):                                                        # brochure rack
        nc.box((0, 0.05, 0.15), (0.5, 0.06, 0.3), "M_IntMetal")
        for k in range(4):
            nc.box((-0.18 + k * 0.12, 0.0, 0.17), (0.1, 0.02, 0.22), K.POSTERS[k % 4])
    A.text("INFORMATION", (39.45, 21.93, 0.75), 0.0, size=0.1, color=(1, 1, 1))
    _wall_map(nc, A, gx0, 17.2, 1.35, 90.0, 1.0, 0.75, "ISLAND WATERS", seed=3)
    A.prop("SM_Int_Frame", (gx0 + 0.02, 18.85, 2.35), 90.0)
    A.prop("SM_Int_Frame", (gx0 + 0.02, 17.2, 2.45), 90.0)
    A.prop("SM_Int_WallClock", (42.0, y1, 2.45), 0.0)
    _water_cooler(mb, nc, x1 - 0.2, 19.3, -90.0)
    nc.cylinder((44.6, 16.95, 0.0), 0.13, 0.55, "M_IntWoodDark", seg=10, cap_top=False)    # umbrella stand
    for k, m in enumerate(("M_IntFabricRed", "M_IntFabricNavy", "M_IntFabricYellow")):
        nc.beam((44.6 + 0.04 * (k - 1), 16.95, 0.1), (44.6 + 0.09 * (k - 1), 16.95 + 0.05 * k - 0.05, 0.92), 0.05, 0.05, m)
    with nc.at((42.6, 19.6, 0.0)):                                                         # mooring-rope coil
        nc.torus((0, 0, 0.05), 0.3, 0.05, "M_IntCork", seg=14, tube_seg=5)
        nc.torus((0, 0, 0.14), 0.27, 0.05, "M_IntCork", seg=14, tube_seg=5)
    # ---- control room (harbor master's office)
    K.ceiling(wm, x0 + 0.2, y0 - 0.05, x1 + 0.05, y1 + 0.05, tz + 2.45, cornice=K.TRIM_WHITE)
    for a, b in (((scx - 1.25, scy), (scx - 1.25, y1)), ((scx, scy - 1.25), (scx, scy)),
                 ((scx, scy - 1.25), (x1, scy - 1.25))):
        K.railing(mb, [(a[0], a[1]), (b[0], b[1])], tz, h=1.0, mat=K.TRIM_WOOD)
    U = _Shifted(A, (0.0, 0.0, tz))
    with mb.at((0.0, 0.0, tz)), nc.at((0.0, 0.0, tz)):
        K.desk(mb, nc, 41.0, 13.63, 180.0, w=1.8, d=0.8, top="M_IntWood", legs="M_IntWoodDark", hutch=False,
               clutter=False)
        DT.desk_set(nc, U, 41.0, 13.63, 0.76, 180.0, "office", seed=47, w=1.8, d=0.8)
        U.prop("SM_Int_OfficeChair", (41.0, 14.55, 0.0), 0.0)
        U.text("HARBOR MASTER", (41.0, 14.04, 0.62), 180.0, size=0.08, color=(0.1, 0.2, 0.5))
        # chart table with a sea chart of the island
        mb.box((41.2, 18.6, 0.93), (1.8, 1.1, 0.05), "M_IntWood")
        for sx in (-1, 1):
            mb.box((41.2 + sx * 0.8, 18.6, 0.45), (0.1, 0.9, 0.9), "M_IntWoodDark")
        nc.box((41.2, 18.6, 0.957), (1.6, 0.9, 0.004), "M_IntPaper")
        nc.box((41.2, 18.6, 0.96), (1.5, 0.8, 0.004), "M_IntPoster2")
        nc.cylinder((41.1, 18.65, 0.962), 0.22, 0.004, "M_IntFabricGreen", seg=12)
        nc.beam((40.6, 18.3, 0.966), (41.05, 18.6, 0.966), 0.015, 0.003, "M_IntFabricRed")
        nc.beam((41.05, 18.6, 0.966), (41.8, 18.85, 0.966), 0.015, 0.003, "M_IntFabricRed")
        U.prop("SM_Int_Stool", (41.2, 17.8, 0.0), 0.0)
        U.prop("SM_Int_Stool", (40.0, 18.6, 0.0), 0.0)
        # radar / radio console along the east glass
        with mb.at((x1 - 0.3, 16.6, 0.0), rot=-90.0), nc.at((x1 - 0.3, 16.6, 0.0), rot=-90.0):
            mb.box((0, 0, 0.45), (1.6, 0.6, 0.9), STEEL)
            mb.box((0, 0.12, 1.05), (1.6, 0.35, 0.3), STEEL)
            nc.cylinder((-0.35, -0.05, 0.9), 0.2, 0.012, "M_IntScreen", seg=16)
            nc.box((0.35, -0.12, 0.91), (0.5, 0.25, 0.01), "M_IntScreen")
            for k in range(6):
                nc.box((-0.1 + k * 0.08, -0.22, 0.905), (0.04, 0.04, 0.02), K.FABRICS[k])
        U.prop("SM_Int_Radio", (x1 - 0.18, 17.0, 1.2), -90.0)
        nc.box((x1 - 0.4, 15.95, 0.93), (0.12, 0.2, 0.06), "M_IntBlack")                  # VHF handset
        DT.mug(nc, x1 - 0.5, 16.3, 0.9, seed=11)
        # telescope on a tripod looking out to sea
        with mb.at((39.0, 13.9, 0.0)):
            for a in (0.0, 120.0, 240.0):
                r = math.radians(a)
                mb.beam((0.35 * math.cos(r), 0.35 * math.sin(r), 0.0), (0, 0, 1.15), 0.03, 0.03, "M_IntWoodDark")
            with mb.at((0, 0, 1.2), rot=-90.0, rot_y=-80.0):
                mb.cylinder((0, 0, -0.3), 0.05, 0.75, "M_IntTrimGold", seg=10, radius_top=0.035)
        # logbook consoles under the north glass, coat stand, plant
        for px in (39.17, 40.77):
            U.prop("SM_Int_Console", (px, 22.47, 0.0), 0.0)
            U.prop("SM_Int_Books", (px - 0.3, 22.5, 0.96), 0.0)
        DT.book_stack(nc, 41.15, 22.45, 0.95, 10.0, 4, seed=3)
        mb.cylinder((38.6, 17.3, 0.0), 0.2, 0.03, "M_IntWoodDark", seg=10)                    # coat stand
        mb.cylinder((38.6, 17.3, 0.0), 0.025, 1.75, "M_IntWoodDark", seg=6)
        nc.cylinder((38.6, 17.3, 1.75), 0.14, 0.06, "M_IntFabricWhite", seg=12)              # captain's cap
        nc.cylinder((38.6, 17.3, 1.72), 0.17, 0.03, "M_IntBlack", seg=12)
        nc.box((38.6, 17.42, 1.25), (0.42, 0.08, 0.75), "M_IntFabricNavy")                   # uniform jacket
        U.prop("SM_Int_PottedPlant", (x1 - 0.35, y0 + 0.4, 0.0), 0.0)
        U.prop("SM_Int_Cabinet", (38.53, 20.2, 0.0), 90.0)
        U.prop("SM_Int_Kettle", (38.5, 19.85, 1.18), 90.0)
        _coffee_machine(nc, 38.5, 20.45, 1.18, 90.0)
        DT.mug(nc, 38.6, 20.68, 1.18, seed=13)
        U.prop("SM_Int_GreenChair", (39.6, 15.9, 0.0), 20.0)
        U.prop("SM_Int_Compass", (41.7, 18.85, 0.96), 0.0)
        U.prop("SM_Int_Binoculars", (41.85, 18.3, 0.96), 30.0)
        U.prop("SM_Int_Magnifier", (40.75, 18.4, 0.96), 40.0)
        DT.paper_stack(nc, 40.6, 18.9, 0.96, 30.0, 3, seed=9)
        _dress(U, mb, nc, 38.2, 13.2, 45.8, 22.8, 0.0, 2.45, "service", seed=43, skip_walls=("s", "n", "w", "e"))
        # signal-flag garland under the ceiling
        cols = ("M_IntFabricRed", "M_IntFabricYellow", "M_IntFabricBlue", "M_IntFabricWhite", "M_IntFabricGreen")
        for k in range(14):
            fx = x0 + 0.6 + k * 0.5
            nc.box((fx, y0 + 0.25, 2.2), (0.3, 0.01, 0.3), cols[k % 5])
    for px, py in ((40.5, 15.5), (40.5, 19.8), (44.0, 15.2)):
        K.panel_light(A, nc, px, py, tz + 2.45)
    K.camera(A, "ticket_office", (44.15, 15.0, 1.7), (38.6, 14.1, 1.0), 15.0)   # x < 44.28: outside the palm's AABB
    K.camera(A, "terminal_lobby", (39.0, 16.9, 1.7), (44.0, 21.6, 2.2), 15.0)
    K.camera(A, "harbor_master", (38.5, 21.5, tz + 1.7), (43.5, 14.0, tz + 0.6), 15.0)


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


def _heli_hut(aset, mb, nc, im, inc):
    """Heliport terminal hut west of the pad (harbor style: white walls, blue band, blue hip roof): a check-in /
    dispatch room with VIP waiting chairs (entrance north) and the pilot lounge (door east, towards the pad)."""
    X0, X1, Y0, Y1, H = -199.6, -190.4, 13.6, 20.0, 3.2
    WT = 0.2
    x0, x1, y0, y1 = X0 + WT, X1 - WT, Y0 + WT, Y1 - WT          # inner box
    px = -195.0                                                  # partition (west face)
    ch = 2.7                                                     # ceiling (the roof soffit sits at 2.75)
    # plinth strip, floor, entrance aprons
    for a, b in (((X0 - 0.08, Y0 - 0.08), (X1 + 0.08, Y0)), ((X0 - 0.08, Y1), (X1 + 0.08, Y1 + 0.08)),
                 ((X0 - 0.08, Y0), (X0, Y1)), ((X1, Y0), (X1 + 0.08, Y1))):
        mb.box_mm((a[0], a[1], 0.0), (b[0], b[1], 0.4), CONC)
    mb.box_mm((x0, y0, -0.2), (x1, y1, 0.005), "M_IntTileWhite", skip=("-z",))
    mb.box_mm((-198.0, Y1 + 0.08, -0.2), (-196.4, Y1 + 1.6, 0.01), DCONC, skip=("-z",))
    mb.box_mm((X1 + 0.08, 14.3, -0.2), (X1 + 1.6, 15.9, 0.01), DCONC, skip=("-z",))
    mb.box_mm((-198.0, Y1 - 0.12, -0.2), (-196.4, Y1 + 0.08, 0.005), "M_IntTileWhite", skip=("-z",))
    mb.box_mm((X1 - 0.12, 14.3, -0.2), (X1 + 0.08, 15.9, 0.005), "M_IntTileWhite", skip=("-z",))
    # walls with real windows + doors
    kw = dict(trim=TRIM, trim_in=K.TRIM_WHITE, base=K.TRIM_WOOD)
    s_ops = [K.Window(2.4, 1.6, 1.0, 2.2, frame=TRIM, mullions=1), K.Window(6.8, 1.6, 1.0, 2.2, frame=TRIM, mullions=1)]
    e_ops = [K.Door(15.1 - Y0, 1.0, 2.15, "glass"), K.Window(18.2 - Y0, 1.4, 1.0, 2.2, frame=TRIM, mullions=1)]
    n_ops = [K.Door(X1 - (-197.2), 1.0, 2.15, "glass"), K.Window(X1 - (-192.9), 1.4, 1.0, 2.2, frame=TRIM, mullions=1)]
    w_ops = [K.Window(Y1 - 16.8, 1.4, 1.0, 2.2, frame=TRIM, mullions=1)]
    for p0, p1, ops in (((X0, Y0), (X1, Y0), s_ops), ((X1, Y0), (X1, Y1), e_ops), ((X1, Y1), (X0, Y1), n_ops),
                        ((X0, Y1), (X0, Y0), w_ops)):
        K.wall(aset, mb, p0, p1, 0.0, H, WT, WHITE, inner=K.PLASTER_WHITE, openings=ops, **kw)
    mb.box_mm((X0 - 0.1, Y0 - 0.1, H - 0.35), (X1 + 0.1, Y1 + 0.1, H), BLUE)
    mb.hip_roof(((X0 + X1) / 2, (Y0 + Y1) / 2, H), X1 - X0, Y1 - Y0, 1.3, ROOF_BLUE, overhang=0.5)
    K.wall(aset, im, (px, y1), (px, y0), 0.0, ch, 0.12, K.PLASTER_WHITE, inner=K.PLASTER_WHITE,
           openings=[K.Door(y1 - 18.8, 0.9, 2.1, "office")], trim_in=K.TRIM_WHITE, trim=K.TRIM_WHITE, base=K.TRIM_WOOD)
    K.ceiling(im, x0, y0, x1, y1, ch, cornice=K.TRIM_WHITE)
    # outside: sign, door lamps, wind / weather board
    aset.text("HELIPORT TERMINAL", ((X0 + X1) / 2, Y1 + 0.03, H - 0.22), 180.0, size=0.22, color=(1, 1, 1))
    for lx, ly, ly2 in ((-197.2, Y1 + 0.12, Y1 + 0.7), (X1 + 0.12, 15.1, 15.1)):
        nc.box((lx, ly, 2.55), (0.25, 0.08, 0.15) if ly2 != ly else (0.08, 0.25, 0.15), GLOW)
    aset.light((-197.2, Y1 + 0.7, 2.5), (1.0, 0.88, 0.65), 1500.0, 6.0, night_only=True)
    aset.light((X1 + 0.7, 15.1, 2.5), (1.0, 0.88, 0.65), 1500.0, 6.0, night_only=True)

    A = aset
    rnd = random.Random(61)
    # ---------------------------------------------------------------- check-in / dispatch (west room)
    wx0, wx1 = x0, px
    _dress(A, im, inc, wx0, y0, wx1, y1, 0.0, ch, "office", seed=61)
    K.counter(im, -198.4, 14.75, -196.2, 15.35, h=1.0, body=BLUE, top=K.TRIM_WHITE)
    DT.desk_set(inc, A, -197.3, 15.05, 1.0, 0.0, "reception", seed=62, w=2.2, d=0.6)
    A.prop("SM_Int_OfficeChair", (-197.3, 14.32, 0.0), 0.0)
    A.text("CHECK-IN", (-197.3, 15.36, 0.72), 180.0, size=0.12, color=(1, 1, 1))
    with im.at((-195.75, 15.05, 0.0)):                                                  # luggage scale
        im.box((0, 0, 0.05), (0.6, 0.6, 0.1), "M_IntMetal")
        im.box((0.25, 0, 0.55), (0.06, 0.06, 1.0), "M_IntMetal")
    inc.box((-195.5, 15.05, 1.05), (0.04, 0.2, 0.14), "M_IntScreen")
    for i, yy in enumerate((16.35, 18.45)):
        A.prop("SM_Int_Armchair", (-198.9, yy, 0.0), 90.0)
    A.prop("SM_Int_SideTable", (-198.95, 17.4, 0.0), 90.0)
    DT.paper_stack(inc, -198.95, 17.4, 0.55, 20.0, 4, seed=4)
    A.prop("SM_Int_PottedPlantC", (-198.95, 19.3, 0.0), 0.0)
    _whiteboard(inc, A, wx1, 16.8, 1.0, -90.0, 1.4, 0.85, ("WEATHER  14:00", "WIND 220 / 12 KT", "VIS 10 KM  CLOUD FEW",
                                                          "NEXT ARRIVAL  15:30"))
    _wall_map(inc, A, wx1, 14.6, 1.3, -90.0, 0.8, 0.6, "APPROACH", seed=7)
    K.bulletin(inc, A, -198.6, y1, 1.15, 0.0, 0.9, 0.75, title="VISITOR INFO", rng_seed=31)
    A.prop("SM_Int_WallClock", (-196.0, y1, 2.35), 0.0)
    K.poster(inc, A, x0, 15.0, 1.6, 90.0, 0.55, 0.8, "M_IntPoster2", "FLY", text_size=0.08)
    A.prop("SM_Int_Extinguisher", (-195.4, 19.5, 0.0), -90.0)
    _luggage_cart(im, inc, -196.2, 17.4, 0.0, 2, seed=8)
    A.prop("SM_Int_CeilingFan", (-197.4, 18.3, ch), 0.0)
    A.prop("SM_Int_CoffeeTableB", (-198.05, 17.4, 0.0), 90.0)
    DT.paper_stack(inc, -198.1, 17.0, 0.39, 15.0, 4, seed=13)
    with inc.at((-198.0, 17.75, 0.39), rot=30.0):                                         # model helicopter
        inc.box((0, 0, 0.05), (0.22, 0.08, 0.08), "M_AcademyBlue")
        inc.box((-0.17, 0, 0.06), (0.16, 0.02, 0.03), "M_AcademyBlue")
        inc.box((0, 0, 0.1), (0.36, 0.02, 0.004), "M_IntBlack")
        inc.box((0, 0, 0.1), (0.02, 0.36, 0.004), "M_IntBlack")
        inc.box((0, 0, 0.002), (0.18, 0.12, 0.004), "M_IntMetal")
    with im.at((-195.6, y0, 1.85)):                                                       # flight-info screen
        im.box((0, 0.03, 0), (0.8, 0.06, 0.48), "M_IntBlack")
    inc.box((-195.6, y0 + 0.065, 1.85), (0.72, 0.004, 0.4), "M_IntScreen")
    A.text("FLIGHT INFO", (-195.6, y0 + 0.07, 2.0), 180.0, size=0.06, color=(1, 1, 1), emissive=True)
    A.prop("SM_Int_Painting", (x0, 18.75, 1.45), 90.0)
    A.prop("SM_Int_PottedPlantB", (-198.95, 14.25, 0.0), 0.0)
    K.panel_light(A, inc, -197.2, 16.8, ch)
    # ---------------------------------------------------------------- pilot lounge (east room)
    ex0, ex1 = px + 0.12, x1
    _dress(A, im, inc, ex0, y0, ex1, y1, 0.0, ch, "office", seed=63)
    K.lockers(im, inc, A, ex0 + 0.23, 17.4, 90.0, n=4)
    with im.at((ex0, 17.4, 2.3), rot=90.0):                                             # wall TV over the lockers
        im.box((0, -0.03, 0), (1.0, 0.06, 0.56), "M_IntBlack")
    inc.box((ex0 + 0.065, 17.4, 2.3), (0.004, 0.92, 0.48), "M_IntScreen")
    A.prop("SM_Int_Sofa", (-190.97, 17.35, 0.0), -90.0)
    A.prop("SM_Int_CoffeeTableB", (-192.05, 17.35, 0.0), 90.0)
    DT.mug(inc, -192.0, 17.0, 0.39, seed=5)
    DT.paper_stack(inc, -192.1, 17.7, 0.39, 60.0, 3, seed=6)
    K.kitchen_run(im, inc, -193.85, y1, -192.05, against="+y", upper=False)
    _coffee_machine(inc, -193.55, 19.5, 0.9, 0.0)
    A.prop("SM_Int_Kettle", (-192.35, 19.48, 0.9), 0.0)
    _fridge(im, inc, -191.55, 19.45, 0.0)
    A.prop("SM_Int_RoundTableB", (-193.15, 15.2, 0.0), 0.0)
    for a in (150.0, 30.0):
        r = math.radians(a)
        A.prop("SM_Int_PlasticChair", (-193.15 + math.cos(r) * 0.72, 15.2 + math.sin(r) * 0.72, 0.0), a - 90.0)
    DT.card_spread(inc, -193.2, 15.15, 0.75, 0.0, 5, seed=11)
    DT.deck_box(inc, -192.9, 15.35, 0.75, 20.0, "M_IntFabricBlue")
    DT.mug(inc, -193.45, 15.4, 0.75, seed=12)
    _vest_hooks(inc, ex1, 19.25, 1.75, -90.0, n=2, vests=2, helmets=True)
    K.bulletin(inc, A, -191.25, y0, 1.2, 180.0, 0.9, 0.7, title="FLIGHT NOTICES", rng_seed=33)
    A.prop("SM_Int_PottedPlantB", (-194.4, 14.25, 0.0), 0.0)
    K.panel_light(A, inc, -192.7, 16.8, ch)
    K.camera(A, "heli_checkin", (-195.5, 19.4, 1.65), (-198.6, 15.0, 0.9), 15.0)
    K.camera(A, "heli_lounge", (-194.6, 15.0, 1.65), (-191.0, 18.6, 0.9), 15.0)


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
    _ferry(aset.mesh("Harbor_Ferry"), aset)
    aset.special("floating", FERRY_POS, 0.0, mesh="Harbor_Ferry", amplitude=0.15, period=6.0, clear=45.0)
    im = aset.mesh("Harbor_Interior")
    inc = aset.mesh("Harbor_Interior_NoCol")
    _warehouses(aset, aset.mesh("Harbor_Warehouse"), nc, im, inc)
    _crane(aset, aset.mesh("Harbor_Crane"), nc)
    term = aset.mesh("Harbor_Terminal")
    with term.at(TERM_OFF), nc.at(TERM_OFF), im.at(TERM_OFF), inc.at(TERM_OFF):
        _terminal(_Shifted(aset, TERM_OFF), term, nc, im, inc)
    _heliport(aset, aset.mesh("Harbor_Heliport"), nc)
    _heli_hut(aset, aset.mesh("Harbor_Heliport"), nc, im, inc)
    _breakwater(aset, aset.mesh("Harbor_Breakwater"), nc)
    _dressing(aset)
    return aset


# ================================================================== LIGHTHOUSE
LH_LAMP_Z = 20.45


def _lh_r(z):
    """Tower radius (tapered shaft)."""
    return 3.2 - (z - 0.95) * (1.05 / 16.6)


LH_WALL = 0.3          # tower wall thickness (outer skin -> inner skin)
LH_DOOR = (70.0, 110.0, 0.95, 3.35)   # doorway through the shaft: angles (deg) and z range
LH_WATCH = 15.15       # watch room floor (top of the spiral stair)
LH_STAIR_R = 1.0       # spiral stair outer radius
LH_STEP = 22.5         # spiral step angle: 16 treads per turn -> 0.275 m run on the 0.7 m walk line, 3.0 m headroom


def _lh_ro(z):
    """Outer radius of the shaft (flared foot below 1.5)."""
    if z < 1.5:
        return 3.5 + (z - 0.95) / 0.55 * (_lh_r(1.5) - 3.5)
    return _lh_r(z)


def _lh_ri(z):
    """Inner radius (inner skin of the hollow tower)."""
    if z < 1.5:
        return _lh_r(1.5) - LH_WALL
    if z <= 17.55:
        return _lh_r(z) - LH_WALL
    rt = _lh_r(17.55)
    prof = [(17.55, rt - LH_WALL), (17.8, rt), (18.2, 2.55), (18.3, 2.7)]
    for (z0, r0), (z1, r1) in zip(prof, prof[1:]):
        if z <= z1:
            return r0 + (r1 - r0) * (z - z0) / (z1 - z0)
    return 2.7


LH_WINDOWS = [(4.4, 150.0), (7.6, 300.0), (10.8, 90.0), (13.9, 225.0), (16.4, 20.0)]   # (centre z, angle)
LH_WIN_H, LH_WIN_DA = 0.46, 5.0                            # half height, half angle of the openings


def _lh_rows(rows):
    """Shell rows plus the sill / head of every window inside their range."""
    lo, hi = min(rows), max(rows)
    extra = [z + s * LH_WIN_H for z, a in LH_WINDOWS for s in (-1, 1) if lo < z + s * LH_WIN_H < hi]
    return sorted(set(rows) | set(extra))


def _lh_shell(mb, rows, rfun, matfun, inward, seg=72):
    """Revolved skin (shared vertices -> smooth like MeshBuilder.lathe) with the doorway and the shaft windows
    left open: the cells inside LH_DOOR / LH_WINDOWS are skipped."""
    a0d, a1d, dz0, dz1 = LH_DOOR
    rows = _lh_rows(rows)
    base = len(mb.verts)
    for z in rows:
        r = rfun(z)
        for i in range(seg):
            a = math.tau * i / seg
            mb._add_vert((r * math.cos(a), r * math.sin(a), z))
    for j in range(len(rows) - 1):
        z0, z1 = rows[j], rows[j + 1]
        m = matfun((z0 + z1) / 2)
        for i in range(seg):
            ad0, ad1 = 360.0 * i / seg, 360.0 * (i + 1) / seg
            if z1 <= dz1 + 1e-6 and ad0 >= a0d - 1e-6 and ad1 <= a1d + 1e-6:
                continue
            if any(z0 >= wz - LH_WIN_H - 1e-6 and z1 <= wz + LH_WIN_H + 1e-6 and ad0 >= wa - LH_WIN_DA - 1e-6
                   and ad1 <= wa + LH_WIN_DA + 1e-6 for wz, wa in LH_WINDOWS):
                continue
            i2 = (i + 1) % seg
            f = (base + j * seg + i, base + j * seg + i2, base + (j + 1) * seg + i2, base + (j + 1) * seg + i)
            mb.faces.append(f[::-1] if inward else f)
            mb.face_mats.append(m)
            mb.face_smooth.append(True)


def _polar_slab(mb, r0, r1, a0, a1, z, t, top, bot, side, step=10.0, caps=True, outer=False):
    n = max(1, int(math.ceil((a1 - a0) / step)))
    P = lambda r, ang, zz: (r * math.cos(ang), r * math.sin(ang), zz)
    for i in range(n):
        a = math.radians(a0 + (a1 - a0) * i / n)
        b = math.radians(a0 + (a1 - a0) * (i + 1) / n)
        mb.quad(P(r0, a, z), P(r1, a, z), P(r1, b, z), P(r0, b, z), top)
        mb.quad(P(r0, b, z - t), P(r1, b, z - t), P(r1, a, z - t), P(r0, a, z - t), bot)
        mb.quad(P(r0, a, z), P(r0, b, z), P(r0, b, z - t), P(r0, a, z - t), side)
        if outer:
            mb.quad(P(r1, b, z), P(r1, a, z), P(r1, a, z - t), P(r1, b, z - t), side)
    if caps:
        a, b = math.radians(a0), math.radians(a1)
        mb.quad(P(r0, a, z - t), P(r1, a, z - t), P(r1, a, z), P(r0, a, z), side)
        mb.quad(P(r1, b, z - t), P(r0, b, z - t), P(r0, b, z), P(r1, b, z), side)


def _polar(r, adeg, z=0.0):
    a = math.radians(adeg)
    return (r * math.cos(a), r * math.sin(a), z)


def _ring_shelf(mb, nc, z, a0, a1, depth=0.22, seed=0, skip=()):
    """Curved wall shelf around the inside of the lighthouse shaft (top at z) with keeper's clutter on it: logbooks,
    jars, tins, a ship in a bottle, a storm lantern. skip: [(a, b)] angle ranges left free."""
    rw = _lh_ri(z + 0.2) - 0.01
    _polar_slab(mb, rw - depth, rw + 0.02, a0, a1, z, 0.03, "M_IntWood", "M_IntWoodDark", "M_IntWoodDark")
    rnd = random.Random(seed)
    a = a0 + 4.0
    while a < a1 - 4.0:
        if any(sa <= a <= sb for sa, sb in skip):
            a += 3.0
            continue
        x, y, _ = _polar(rw - depth / 2, a)
        nc.box(_polar(rw - 0.05, a, z - 0.08), (0.03, 0.03, 0.16), "M_IntMetal")
        pick = rnd.random()
        if pick < 0.4:
            DT.book_stack(nc, x, y, z, a, rnd.randint(2, 4), seed=int(a))
        elif pick < 0.65:
            for k in range(3):
                nc.cylinder(_polar(rw - depth / 2, a - 2.0 + k * 2.0, z), 0.04, rnd.uniform(0.1, 0.18),
                            rnd.choice(("M_IntGlassClear", "M_IntTrimGold", "M_AcademyRed", "M_IntFabricGreen")), seg=8)
        elif pick < 0.8:
            with nc.at((x, y, z), rot=a):                                                   # ship in a bottle
                with nc.at((0, 0, 0.06), rot_y=90):
                    nc.cylinder((0, 0, -0.14), 0.055, 0.28, "M_IntGlassClear", seg=10)
                nc.box((0, 0, 0.045), (0.035, 0.16, 0.03), "M_ShipHull")
                nc.box((0, 0, 0.08), (0.004, 0.08, 0.06), "M_IntTrimWhite")
        else:
            nc.cylinder((x, y, z), 0.07, 0.22, "M_IntBlack", seg=8)                           # storm lantern
            nc.cylinder((x, y, z + 0.05), 0.055, 0.12, K.GLOW, seg=8)
        a += rnd.uniform(9.0, 14.0)


def _lighthouse_tower_inside(aset, tw, mb, nc):
    """Hollow shaft: inner skin, doorway jambs, round ground room, spiral stair up to the watch room."""
    a0d, a1d, dz0, dz1 = LH_DOOR

    def inner_mat(z):
        return "M_IntWoodPanel" if z > 15.0 else (K.PLASTER_CREAM if z > 1.9 else "M_IntWallpaperRed")
    _lh_shell(tw, [0.95, 1.9, dz1, 6.0, 9.0, 12.0, 15.0, 17.55], _lh_ri, inner_mat, True)
    _lh_shell(tw, [17.55, 17.8, 18.2, 18.3], _lh_ri, inner_mat, True)
    # jambs + lintel of the doorway (close the cavity between the skins)
    for ad, flip in ((a0d, True), (a1d, False)):
        a = math.radians(ad)
        pr = [(_lh_ri(dz0), dz0), (_lh_ro(dz0), dz0), (_lh_ro(1.5), 1.5), (_lh_ro(dz1), dz1), (_lh_ri(dz1), dz1)]
        pts = [(r * math.cos(a), r * math.sin(a), z) for r, z in pr]
        tw.poly(pts[::-1] if flip else pts, LH_W)
    _polar_slab(tw, _lh_ri(dz1), _lh_ro(dz1) + 0.01, a0d, a1d, dz1 + 0.001, 0.001, LH_W, LH_W, LH_W, caps=False)
    # floors: round room + porch, watch room (annulus + landing beside the stair top)
    mb.prism([_polar(_lh_ri(1.0) + 0.02, 10.0 * k)[:2] for k in range(36)], 0.94, 0.955, K.WOODFLOOR, cap_bottom=False)
    mb.box_mm((-1.15, 2.6, 0.94), (1.15, 3.75, 0.955), K.WOODFLOOR, skip=("-z",))
    zt = LH_WATCH
    n_steps = int(round((zt - 0.95) / 0.19))
    a_start = 270.0
    a_top = (a_start + LH_STEP * n_steps) % 360.0           # end angle of the top step
    rh = LH_STAIR_R + 0.07
    _polar_slab(mb, rh, _lh_ri(zt) + 0.04, 0.0, 360.0, zt, 0.15, "M_IntWoodFloor", "M_IntCeilingWood",
                "M_IntWoodDark", caps=False)
    _polar_slab(mb, 0.15, rh, a_top, a_top + 110.0, zt, 0.15, "M_IntWoodFloor", "M_IntCeilingWood", "M_IntWoodDark")
    rail = [_polar(rh, a_top + 110.0 + k * 10.0)[:2] for k in range(int((360.0 - 130.0) / 10.0) + 1)]
    K.railing(mb, rail, zt, h=1.0, mat=K.TRIM_WOOD, spacing=0.18)
    K.spiral_stairs(mb, 0.0, 0.0, 0.95, zt, 0.15, LH_STAIR_R, a0=a_start, step_deg=LH_STEP, mat=STEEL,
                    core=LH_R, rail=None)
    # window galleries: annular platforms flush with a tread, so the shaft windows can be reached (and cleaned)
    rise = (zt - 0.95) / n_steps
    gals = []
    # G1 archive (300-deg window), G2 lamp store (225), G3 lookout (150), G4 weather room (90); the entry tread
    # (ta..tb) lies inside each ring, the inner edge is railed everywhere else
    for g_step, a0g, a1g in ((27, 157.5, 330.0), (60, 130.0, 240.0), (10, 112.0, 175.0), (44, 70.0, 202.5)):
        zg = 0.95 + rise * (g_step + 1)
        ta = (a_start + LH_STEP * g_step) % 360.0                                    # entry tread angles
        tb = ta + LH_STEP
        gals.append((g_step, zg, a0g, a1g, ta, tb))
        rout = _lh_ri(zg) + 0.04
        _polar_slab(mb, rh, rout, a0g, a1g, zg, 0.12, "M_IntWoodFloor", "M_IntWoodDark", "M_IntWoodDark", caps=True)
        for k in range(int((a1g - a0g) / 15.0) + 1):                                 # joists under the planks
            a = a0g + 2.0 + k * 15.0
            nc.beam(_polar(rh + 0.02, a, zg - 0.13), _polar(rout - 0.06, a, zg - 0.13), 0.08, 0.12, "M_IntWoodDark")
        for ra, rb in ((a0g, ta), (tb, a1g)):
            if rb - ra < 1.0:
                continue
            n_ = max(1, int((rb - ra) / 8.0))
            K.railing(mb, [_polar(rh + 0.03, ra + (rb - ra) * k / n_)[:2] for k in range(n_ + 1)], zg, h=1.0,
                      mat=K.TRIM_WOOD, spacing=0.18)
        for a, d_ in ((a0g, 0.5), (a1g, -0.5)):
            K.railing(mb, [_polar(rh + 0.03, a + d_)[:2], _polar(_lh_ri(zg + 0.5) - 0.05, a + d_)[:2]], zg, h=1.0,
                      mat=K.TRIM_WOOD, spacing=0.18)
    # stair hand rail (kit rail re-drawn with gaps at the gallery entries)
    skip = set()
    for g_step, *_ in gals:
        skip |= {g_step - 1, g_step, g_step + 1}
    prev = None
    for i in range(n_steps):
        am = math.radians(a_start + LH_STEP * (i + 0.5) + 1.0)
        z = 0.95 + rise * (i + 1)
        p = (math.cos(am) * (LH_STAIR_R - 0.05), math.sin(am) * (LH_STAIR_R - 0.05))
        if i in skip:
            prev = None
            continue
        mb.box((p[0], p[1], z + 0.45), (0.035, 0.035, 0.9), K.TRIM_WOOD)
        if prev is not None:
            mb.beam((prev[0], prev[1], prev[2] + 0.92), (p[0], p[1], z + 0.92), 0.05, 0.05, K.TRIM_WOOD)
        prev = (p[0], p[1], z)
    # ceiling of the watch room (under the gallery deck) with the hatch to the lantern
    tw.poly([_polar(2.72, 10.0 * k, 18.3) for k in reversed(range(36))], "M_IntCeilingWood")
    hx, hy, _ = _polar(1.55, 140.0)
    nc.box((hx, hy, 18.29), (0.75, 0.75, 0.02), "M_IntWoodDark")
    nc.box((hx, hy, 18.28), (0.65, 0.65, 0.02), "M_IntWood")
    with nc.at((hx, hy, zt), rot=140.0 - 90.0):                                     # ladder to the hatch
        for sx in (-0.22, 0.22):
            nc.box((sx, 0.05, 1.6), (0.05, 0.05, 3.2), "M_IntWoodDark")
        for k in range(10):
            nc.box((0, 0.05, 0.3 + k * 0.3), (0.44, 0.04, 0.04), "M_IntWoodDark")

    # windows: real openings (see the shell), inner trim frame + transom
    for z, adeg in LH_WINDOWS:
        d = _lh_ri(z) - 0.035
        x, y, _ = _polar(d, adeg)
        with nc.at((x, y, z), rot=adeg - 90.0):
            for sx in (-1, 1):
                nc.box((sx * 0.34, -0.03, 0), (0.06, 0.06, 1.04), K.TRIM_WHITE)
            nc.box((0, -0.03, 0.49), (0.74, 0.06, 0.06), K.TRIM_WHITE)
            nc.box((0, -0.06, -0.49), (0.8, 0.12, 0.06), K.TRIM_WHITE)
            nc.box((0, -0.015, 0.05), (0.62, 0.03, 0.035), K.TRIM_WHITE)
    # wall lamps along the climb (+ light sockets)
    for z, adeg in ((3.0, 300.0), (6.6, 120.0), (10.4, 300.0), (13.6, 120.0), (17.2, 250.0)):
        x, y, _ = _polar(_lh_ri(z) - 0.08, adeg)
        with nc.at((x, y, z), rot=adeg - 90.0):
            nc.box((0, 0.0, 0), (0.22, 0.12, 0.3), "M_IntBlack")
            nc.box((0, -0.07, 0), (0.15, 0.04, 0.2), K.GLOW)
        lx, ly, _ = _polar(_lh_ri(z) - 0.5, adeg)
        aset.light((lx, ly, z), (1.0, 0.82, 0.58), 2500.0, 8.0, night_only=False)

    # ground room: store + workshop of the keeper
    def wall_prop(asset, adeg, depth, width, z=0.95, inset=0.02):
        r = math.sqrt(max(_lh_ri(z + 1.0) ** 2 - (width / 2) ** 2, 0.0)) - inset - depth / 2
        x, y, _ = _polar(r, adeg)
        aset.prop(asset, (x, y, z), adeg - 90.0)
    wall_prop("SM_Int_Shelves", 262.0, 0.37, 0.51)       # angles near 90-degree multiples keep the AABBs tight
    sx_, sy_, _ = _polar(math.sqrt(_lh_ri(2.95) ** 2 - 0.55 ** 2) - 0.02 - 0.225, 180.0)
    with mb.at((0.0, 0.0, 0.95)), nc.at((0.0, 0.0, 0.95)):
        _shelf_unit(mb, nc, random.Random(31), sx_, sy_, 90.0, w=1.1, d=0.45, h=2.0, levels=5)
    for adeg, z in ((40.0, 2.1), (130.0, 2.1)):
        x, y, _ = _polar(_lh_ri(z) - 0.03, adeg)
        aset.prop("SM_Int_Lifebuoy", (x, y, z - 0.4), adeg - 90.0)
    for adeg, r in ((292.0, 2.35), (306.0, 2.3)):
        x, y, _ = _polar(r, adeg)
        aset.prop("SM_Barrel", (x, y, 0.95), adeg * 3.0)
    x, y, _ = _polar(1.72, 12.0)
    aset.prop("SM_Crate", (x, y, 0.95), 12.0 + 45.0)
    # workbench against the wall at 335 deg
    r = math.sqrt(_lh_ri(1.9) ** 2 - 0.65 ** 2) - 0.02 - 0.28
    x, y, _ = _polar(r, 335.0)
    with mb.at((x, y, 0.95), rot=335.0 - 90.0), nc.at((x, y, 0.95), rot=335.0 - 90.0):
        mb.box((0, 0, 0.86), (1.2, 0.55, 0.06), "M_IntWood")
        for sx in (-1, 1):
            mb.box((sx * 0.55, 0, 0.42), (0.07, 0.5, 0.84), "M_IntWoodDark")
        mb.box((0, 0, 0.18), (1.1, 0.5, 0.03), "M_IntWoodDark")
        nc.box((-0.3, 0.0, 0.93), (0.35, 0.2, 0.08), "M_IntFabricRed")              # tool box
        nc.box((0.25, -0.05, 0.9), (0.3, 0.22, 0.01), "M_IntPaper")
        nc.cylinder((0.4, 0.12, 0.89), 0.06, 0.16, "M_IntMetal", seg=8)             # oil can
        nc.box((0.0, 0.2, 0.25), (0.6, 0.15, 0.12), "M_IntMetal")
    aset.prop("SM_Int_OilLamp", (x, y, 0.95 + 0.89), 0.0)
    rx, ry, _ = _polar(2.2, 55.0)
    nc.torus((rx, ry, 1.0), 0.28, 0.06, "M_IntCork", seg=14, tube_seg=5)              # coil of rope
    nc.torus((rx, ry, 1.1), 0.25, 0.06, "M_IntCork", seg=14, tube_seg=5)
    bx, by, _ = _polar(2.55, 215.0)
    aset.prop("SM_Int_Bucket", (bx, by, 0.95), 0.0)
    # watch room: the keeper's desk with the radio, logbook, binoculars
    zr = zt
    r = math.sqrt(_lh_ri(zr + 0.75) ** 2 - 0.45 ** 2) - 0.03 - 0.22
    x, y, _ = _polar(r, 200.0)
    with mb.at((x, y, zr), rot=200.0 - 90.0), nc.at((x, y, zr), rot=200.0 - 90.0):
        mb.box((0, 0, 0.74), (0.9, 0.44, 0.04), "M_IntWood")
        for sx in (-1, 1):
            mb.box((sx * 0.42, 0, 0.36), (0.05, 0.4, 0.72), "M_IntWoodDark")
        nc.box((0.2, -0.05, 0.775), (0.3, 0.22, 0.03), "M_IntFabricNavy")            # logbook
        nc.box((0.2, -0.05, 0.792), (0.27, 0.2, 0.004), "M_IntPaper")
        for sx in (-0.05, 0.05):                                                   # binoculars
            with nc.at((-0.05 + sx, -0.1, 0.8), rot_x=90):
                nc.cylinder((0, 0, -0.08), 0.03, 0.16, "M_IntBlack", seg=8)
    aset.prop("SM_Int_Radio", _polar(r + 0.05, 205.0, zr + 0.76), 200.0 + 90.0)
    aset.prop("SM_Int_Stool", _polar(1.45, 200.0, zr), 0.0)
    x, y, _ = _polar(_lh_ri(zr + 1.2) - 0.03, 80.0)
    aset.prop("SM_Int_Lifebuoy", (x, y, zr + 0.9), 80.0 - 90.0)
    x, y, _ = _polar(_lh_ri(zr + 1.5) - 0.03, 305.0)
    aset.prop("SM_Int_WallClock", (x, y, zr + 1.35), 305.0 - 90.0)
    aset.text("LAMP ROOM - KEEPER ONLY", _polar(_lh_ri(zr + 2.2) - 0.03, 125.0, zr + 2.2), 125.0 - 90.0, size=0.07,
              color=(0.85, 0.15, 0.1))
    aset.prop("SM_Int_CeilingLamp", _polar(1.5, 40.0, 18.3), 0.0)
    aset.prop("SM_Int_CeilingLamp", _polar(1.55, 212.0, 18.3), 0.0)
    # ---------------------------------------------------------------- detail pass
    ri0 = _lh_ri(1.9)
    # ground room: switch by the door, outlets, oilskins + boots, tool board over the bench, storm lantern
    _round_switch(nc, 116.0, 0.95 + 1.1, _lh_ri(2.05) - 0.005)
    for adeg in (20.0, 240.0, 300.0):
        _round_outlet(nc, adeg, 0.95 + 0.3, _lh_ri(1.25) - 0.005)
    for k, adeg in enumerate((143.0, 150.0, 157.0)):
        x, y, _ = _polar(_lh_ri(2.6) - 0.06, adeg)
        with nc.at((x, y, 2.75), rot=adeg - 90.0):
            nc.box((0, 0.03, 0.0), (0.03, 0.06, 0.03), "M_DetSilver")
            nc.box((0, -0.04, -0.4), (0.38, 0.08, 0.75), "M_IntFabricYellow" if k != 1 else ORANGE)
            nc.box((0, -0.045, -0.06), (0.16, 0.06, 0.1), "M_IntFabricYellow" if k != 1 else ORANGE)
    bx, by, _ = _polar(2.2, 138.0)
    aset.prop("SM_Int_Boots", (bx, by, 0.95), 0.0)
    for zc_, rr, adeg in ((0.95, 2.4, 161.0), (LH_WATCH, 1.66, 160.0)):                   # sea chests
        with mb.at(_polar(rr, adeg, zc_), rot=adeg - 90.0):
            mb.box((0, 0, 0.21), (0.62, 0.4, 0.42), "M_IntWoodDark")
            mb.box((0, 0, 0.44), (0.64, 0.42, 0.05), "M_IntWood")
            for sx in (-1, 1):
                mb.box((sx * 0.22, -0.205, 0.22), (0.05, 0.01, 0.4), "M_IntTrimGold")
            mb.box((0, -0.21, 0.36), (0.08, 0.02, 0.06), "M_IntTrimGold")
        DT.book_stack(nc, *_polar(rr, adeg)[:2], zc_ + 0.465, adeg, 2, seed=int(adeg))
    x, y, _ = _polar(ri0 - 0.02, 335.0)
    with nc.at((x, y, 1.95), rot=335.0 - 90.0):                                         # tool board
        nc.box((0, -0.01, 0.4), (1.1, 0.02, 0.75), "M_IntCork")
        rt = random.Random(12)
        for k in range(8):
            nc.box((-0.42 + k * 0.12, -0.03, rt.uniform(0.2, 0.55)), (0.03, 0.02, rt.uniform(0.15, 0.3)),
                   rt.choice((STEEL, "M_IntFabricRed", "M_IntBlack", "M_IntTrimGold")))
    lx, ly, _ = _polar(2.5, 35.0)
    aset.prop("SM_Int_Lantern", (lx, ly, 0.95), 30.0)
    tx, ty_, _ = _polar(2.05, 237.0)
    with mb.at((tx, ty_, 0.95)):                                                         # retired Fresnel lens on show
        mb.box((0, 0, 0.4), (0.55, 0.55, 0.8), "M_IntWoodDark")
        mb.box((0, 0, 0.82), (0.6, 0.6, 0.04), "M_IntTrimGold")
    nc.lathe([(0.18, 0.0), (0.24, 0.12), (0.26, 0.3), (0.24, 0.48), (0.18, 0.6)], "M_IntGlassClear", seg=14,
             cap_bottom=True, cap_top=True, center=(tx, ty_, 0.95 + 0.84))
    for k in range(5):
        nc.torus((tx, ty_, 0.95 + 0.9 + k * 0.1), 0.25 + (0.02 if k in (1, 2, 3) else 0.0), 0.012, "M_IntTrimGold",
                 seg=14, tube_seg=3)
    aset.text("FIRST-ORDER LENS 1962-1998", (tx + 0.33 * math.cos(math.radians(237.0 + 180.0)),
              ty_ + 0.33 * math.sin(math.radians(237.0 + 180.0)), 0.95 + 0.6), 237.0 + 90.0, size=0.035,
              color=(1.0, 0.9, 0.5))
    x, y, _ = _polar(_lh_ri(3.3) - 0.05, 200.0)
    with nc.at((x, y, 3.3), rot=200.0 - 90.0):                                           # crossed oars
        for sgn in (-1, 1):
            with nc.at((0, 0, 0), rot_y=sgn * 35.0):
                nc.box((0, 0, 0), (0.05, 0.04, 2.0), "M_IntWood")
                nc.box((0, 0, 0.85), (0.16, 0.03, 0.42), "M_IntWood")
    x, y, _ = _polar(_lh_ri(3.4) - 0.07, 285.0)
    with nc.at((x, y, 3.4), rot=285.0 - 90.0, rot_x=90):                                 # ship's wheel
        nc.torus((0, 0, 0), 0.38, 0.03, "M_IntWoodDark", seg=16, tube_seg=4)
        for k in range(8):
            a = math.tau * k / 8
            nc.beam((0, 0, 0), (math.cos(a) * 0.5, math.sin(a) * 0.5, 0), 0.035, 0.035, "M_IntWoodDark")
        nc.cylinder((0, 0, -0.04), 0.07, 0.08, "M_IntTrimGold", seg=8)
    for k in range(26):                                                                  # signal-flag garland
        a = 180.0 + k * 3.4
        zz = 3.75 - 0.2 * math.sin(math.pi * k / 25)
        x, y, _ = _polar(_lh_ri(zz) - 0.06, a)
        with nc.at((x, y, zz), rot=a - 90.0):
            nc.box((0, 0, -0.12), (0.18, 0.006, 0.22), K.FABRICS[k % 7])
    x, y, _ = _polar(_lh_ri(1.7) - 0.02, 250.0)
    with nc.at((x, y, 1.7), rot=250.0 - 90.0, rot_x=90):                                 # coiled hose on a hook
        for k in range(3):
            nc.torus((0, -0.12, 0.0 + k * 0.035), 0.2 - k * 0.01, 0.025, "M_IntFabricGreen", seg=14, tube_seg=4)
    x, y, _ = _polar(_lh_ri(1.7) - 0.01, 278.0)
    with nc.at((x, y, 1.7), rot=278.0 - 90.0):                                           # fuse box
        nc.box((0, -0.06, 0), (0.4, 0.12, 0.5), "M_IntMetal")
        nc.box((0, -0.122, 0.0), (0.34, 0.004, 0.42), STEEL)
        nc.box((0.12, -0.13, 0.0), (0.03, 0.02, 0.08), "M_IntBlack")
    x, y, _ = _polar(_lh_ri(2.0) - 0.015, 228.0)
    with nc.at((x, y, 2.0), rot=228.0 - 90.0):                                          # framed tide chart
        nc.box((0, -0.01, 0), (0.55, 0.02, 0.42), "M_IntWoodDark")
        nc.box((0, -0.022, 0), (0.47, 0.005, 0.34), "M_IntPoster2")
    x, y, _ = _polar(_lh_ri(2.6) - 0.01, 92.0)                                       # plaque over the door
    with nc.at((x, y, 3.65), rot=92.0 - 90.0):
        nc.box((0, -0.01, 0), (0.7, 0.02, 0.22), "M_IntTrimGold")
    x, y, _ = _polar(_lh_ri(2.3) - 0.03, 15.0)
    aset.prop("SM_Int_WallClock", (x, y, 2.15), 15.0 - 90.0)
    aset.text("DUEL ACADEMY LIGHT  EST. 1962", _polar(_lh_ri(3.6) - 0.04, 90.0, 3.6), 0.0, size=0.045,
              color=(0.25, 0.15, 0.05))
    # hoist: a rope + tackle from a beam under the watch-room floor down to the store (hauls lamp oil up)
    hx_, hy_, _ = _polar(1.75, 60.0)
    nc.box((hx_, hy_, LH_WATCH - 0.23), (0.12, 0.12, 0.1), "M_IntWoodDark")
    nc.cylinder((hx_, hy_, LH_WATCH - 0.45), 0.09, 0.2, STEEL, seg=10)
    nc.cylinder((hx_ - 0.04, hy_, 7.6), 0.012, LH_WATCH - 0.45 - 7.6, "M_IntCork", seg=4)
    nc.cylinder((hx_ + 0.04, hy_, 2.2), 0.012, LH_WATCH - 0.45 - 2.2, "M_IntCork", seg=4)
    nc.cylinder((hx_ - 0.04, hy_, 7.15), 0.2, 0.45, "M_IntWood", seg=10, cap_top=False)      # basket on the rope
    nc.cylinder((hx_ + 0.04, hy_, 2.0), 0.05, 0.2, STEEL, seg=8)                           # cleat end
    # stair shaft: framed charts and keepers' photographs beside every window, a brass ship's bell
    for z, adeg in ((4.4, 150.0), (7.6, 300.0), (10.8, 90.0), (13.9, 225.0)):
        for k, da in enumerate((-24.0, 24.0)):
            a = adeg + da
            x, y, _ = _polar(_lh_ri(z) - 0.015, a)
            with nc.at((x, y, z - 0.1), rot=a - 90.0):
                w, h = (0.62, 0.48) if k == 0 else (0.42, 0.56)
                nc.box((0, -0.01, 0), (w + 0.08, 0.02, h + 0.08), "M_IntWoodDark")
                nc.box((0, -0.022, 0), (w, 0.005, h), ("M_IntPoster2", "M_IntPaper", "M_IntPoster4", "M_IntPoster3")[
                    (int(adeg) // 10 + k) % 4])
                if k == 0:
                    nc.box((-0.08, -0.026, 0.02), (w * 0.4, 0.004, h * 0.4), "M_IntFabricGreen")
    bx, by, _ = _polar(_lh_ri(6.2) - 0.18, 30.0)
    with nc.at((bx, by, 6.2), rot=30.0 - 90.0):
        nc.box((0, 0.13, 0.25), (0.05, 0.12, 0.05), "M_IntWoodDark")
        nc.lathe([(0.03, 0.0), (0.1, 0.05), (0.12, 0.18), (0.11, 0.22)], "M_IntTrimGold", seg=12, cap_bottom=False,
                 cap_top=True, center=(0, 0, 0.02))
    _ring_shelf(mb, nc, 2.3, 165.0, 300.0, seed=3)
    with mb.at(_polar(2.2, 205.0, 0.95)):                                                 # lamp-oil tank
        mb.cylinder((0, 0, 0.0), 0.34, 0.95, "M_AcademyRed", seg=14)
        mb.cylinder((0, 0, 0.95), 0.3, 0.06, "M_IntMetal", seg=14)
    tx_, ty2, _ = _polar(1.86, 205.0)
    nc.box((tx_, ty2, 1.2), (0.06, 0.06, 0.06), "M_IntTrimGold")
    aset.text("LAMP OIL", _polar(2.2 - 0.35, 205.0, 1.55), 205.0 + 90.0, size=0.07, color=(1, 1, 1))
    for k, adeg in enumerate((22.0, 28.0)):                                               # sacks of sand / rags
        with nc.at(_polar(2.45, adeg, 0.95), rot=adeg):
            nc.box((0, 0, 0.18), (0.5, 0.35, 0.36), "M_IntFabricBeige")
            nc.box((0.0, 0, 0.38), (0.12, 0.2, 0.06), "M_IntFabricBeige")
    x, y, _ = _polar(_lh_ri(2.3) - 0.02, 112.0)
    with nc.at((x, y, 1.9), rot=112.0 - 90.0):                                            # storm notice
        nc.box((0, -0.01, 0), (0.42, 0.02, 0.55), "M_IntTrimWhite")
        for k in range(6):
            nc.box((0, -0.022, 0.18 - k * 0.07), (0.32, 0.004, 0.02), "M_IntBlack" if k else "M_AcademyRed")
    # gallery 1 (archive, under the 300-degree window) and gallery 2 (lamp store, by the 225-degree window)
    (_, z1g, *_), (_, z2g, *_), (_, z3g, *_), (_, z4g, *_) = gals

    def gpos(zg, adeg, depth, width):
        r = math.sqrt(max(_lh_ri(zg + 1.6) ** 2 - (width / 2) ** 2, 0.0)) - 0.02 - depth / 2
        return _polar(r, adeg)

    for adeg in (205.0, 238.0):
        p = gpos(z1g, adeg, 0.32, 0.9)
        with mb.at((0.0, 0.0, z1g)), nc.at((0.0, 0.0, z1g)):
            K.bookcase(mb, nc, p[0], p[1], adeg - 90.0, w=0.9, d=0.32, h=1.9, shelves=5, rng_seed=int(adeg))
    p = gpos(z1g, 270.0, 0.6, 1.0)
    with mb.at((p[0], p[1], z1g), rot=180.0), nc.at((p[0], p[1], z1g), rot=180.0):        # chart chest
        mb.box((0, 0, 0.4), (1.0, 0.6, 0.8), "M_IntWoodDark")
        for k in range(4):
            nc.box((0, -0.302, 0.12 + k * 0.18), (0.9, 0.004, 0.14), "M_IntWood")
            nc.box((0, -0.31, 0.16 + k * 0.18), (0.12, 0.02, 0.025), "M_IntTrimGold")
        nc.box((0, 0, 0.805), (0.85, 0.5, 0.004), "M_IntPaper")
        nc.box((0.05, 0, 0.81), (0.75, 0.42, 0.004), "M_IntPoster2")
        nc.box((-0.1, 0.05, 0.814), (0.25, 0.18, 0.003), "M_IntFabricGreen")
    aset.prop("SM_Int_Magnifier", (p[0] - 0.15, p[1] + 0.1, z1g + 0.8), 20.0)
    p = gpos(z1g, 300.0, 0.4, 1.0)
    with mb.at((p[0], p[1], z1g), rot=300.0 - 90.0):                                     # window bench
        mb.box((0, 0, 0.42), (1.0, 0.4, 0.06), "M_IntWood")
        for sx in (-1, 1):
            mb.box((sx * 0.45, 0, 0.2), (0.06, 0.36, 0.4), "M_IntWoodDark")
    DT.book_stack(nc, *DT._P(p[0], p[1], 300.0 - 90.0, 0.3, 0.0), z1g + 0.45, 300.0, 3, seed=8)
    for adeg in (318.0, 326.0):
        aset.prop("SM_Barrel", _polar(2.0, adeg, z1g), adeg * 2.0, scale=0.62)
    x, y, _ = _polar(_lh_ri(z1g + 1.95) - 0.08, 252.0)
    with nc.at((x, y, z1g + 1.95), rot=252.0 - 90.0):
        nc.box((0, 0.0, 0), (0.22, 0.12, 0.3), "M_IntBlack")
        nc.box((0, -0.07, 0), (0.15, 0.04, 0.2), K.GLOW)
    aset.light(_polar(_lh_ri(z1g + 1.9) - 0.5, 252.0, z1g + 1.9), (1.0, 0.82, 0.58), 2000.0, 6.0, night_only=False)
    aset.text("ARCHIVE", _polar(_lh_ri(z1g + 2.15) - 0.02, 222.0, z1g + 2.15), 222.0 - 90.0, size=0.1,
              color=(0.3, 0.18, 0.08))
    p = gpos(z2g, 150.0, 0.35, 0.9)
    with mb.at((0.0, 0.0, z2g)), nc.at((0.0, 0.0, z2g)):
        _shelf_unit(mb, nc, random.Random(5), p[0], p[1], 150.0 - 90.0, w=0.9, d=0.35, h=1.6, levels=4)
    with nc.at((*_polar(1.72, 232.0)[:2], z2g), rot=232.0):                               # crate of spare prisms
        nc.box((0, 0, 0.17), (0.5, 0.4, 0.34), "M_IntWood")
        for k in range(3):
            nc.box((-0.14 + k * 0.14, 0, 0.36), (0.1, 0.3, 0.06), "M_IntGlassClear")
    for k, adeg in enumerate((136.0, 140.5)):
        with nc.at((*_polar(1.8, adeg)[:2], z2g), rot=adeg):                               # lamp-oil cans
            nc.box((0, 0, 0.2), (0.24, 0.16, 0.4), "M_AcademyRed")
            nc.cylinder((0.06, 0, 0.4), 0.025, 0.05, "M_IntMetal", seg=6)
    aset.light(_polar(1.7, 170.0, z2g + 1.9), (1.0, 0.82, 0.58), 1500.0, 5.0, night_only=False)
    aset.text("LAMP STORE", _polar(_lh_ri(z2g + 2.0) - 0.02, 180.0, z2g + 2.0), 180.0 - 90.0, size=0.08,
              color=(0.3, 0.18, 0.08))
    K.camera(aset, "lh_gallery", _polar(1.45, 182.0, z1g + 1.6), _polar(2.1, 285.0, z1g + 0.7), 14.0)
    p = gpos(z2g, 172.0, 0.35, 0.5)
    with mb.at((p[0], p[1], z2g), rot=172.0 - 90.0), nc.at((p[0], p[1], z2g), rot=172.0 - 90.0):
        mb.box((0, 0, 0.65), (0.5, 0.35, 1.3), "M_IntWoodDark")                              # mantle cabinet
        for k in range(4):
            nc.box((0, -0.177, 0.18 + k * 0.3), (0.44, 0.006, 0.26), "M_IntWood")
            nc.box((0, -0.19, 0.28 + k * 0.3), (0.08, 0.02, 0.025), "M_IntTrimGold")
    _ring_shelf(mb, nc, z2g + 1.45, 182.0, 238.0, seed=29)
    _ring_shelf(mb, nc, z2g + 0.85, 205.0, 238.0, seed=31)
    for k, adeg in enumerate((176.0, 186.0, 196.0)):                                      # lantern hooks
        x, y, _ = _polar(_lh_ri(z2g + 2.0) - 0.12, adeg)
        nc.box((x, y, z2g + 2.17), (0.03, 0.03, 0.12), "M_IntMetal")
        nc.cylinder((x, y, z2g + 1.85), 0.07, 0.24, "M_IntBlack", seg=8)
        nc.cylinder((x, y, z2g + 1.89), 0.055, 0.14, K.GLOW, seg=8)
    for adeg, sd in ((118.0, 41), (98.0, 43)):                       # charts of the lamp's flash pattern
        _wall_map(nc, aset, *_polar(_lh_ri(z2g + 1.5) - 0.02, adeg)[:2], z2g + 1.15, adeg - 90.0, 0.5, 0.6, None, seed=sd)
    _ring_shelf(mb, nc, z2g + 0.85, 100.0, 138.0, seed=37)
    for k, adeg in enumerate((132.0, 142.0, 152.0, 162.0)):           # spare storm lanterns on hooks
        x, y, _ = _polar(_lh_ri(z2g + 2.0) - 0.12, adeg)
        nc.box((x, y, z2g + 2.17), (0.03, 0.03, 0.12), "M_IntMetal")
        nc.cylinder((x, y, z2g + 1.85), 0.07, 0.24, ("M_IntBlack", "M_AcademyRed")[k % 2], seg=8)
        nc.cylinder((x, y, z2g + 1.89), 0.055, 0.14, "M_IntGlassClear", seg=8)
    x, y, _ = _polar(_lh_ri(z2g + 1.9) - 0.02, 172.0)
    K.poster(nc, aset, x, y, z2g + 1.95, 172.0 - 90.0, 0.55, 0.32, "M_IntChalkboard", text="FL(2) W 10s",
             text_size=0.05)                                         # the light's character, chalked up
    _ring_shelf(mb, nc, z2g + 2.05, 100.0, 128.0, seed=39)            # top shelf for the light stock
    _ring_shelf(mb, nc, z2g + 1.45, 140.0, 172.0, seed=33)            # more stock along the far wall
    _ring_shelf(mb, nc, z2g + 0.85, 140.0, 168.0, seed=35)
    for k, adeg in enumerate((146.0, 156.0)):                         # spare lamp glasses in crates
        with nc.at((*_polar(1.85, adeg)[:2], z2g), rot=adeg):
            nc.box((0, 0, 0.15), (0.34, 0.26, 0.3), "M_IntWood")
            for j in range(3):
                nc.cylinder((-0.1 + j * 0.1, 0, 0.3), 0.04, 0.12, "M_IntGlassClear" if j % 2 else K.GLOW, seg=8)
    # standing on the gallery (the old spot hung over the open stair well and looked 13 m down the shaft)
    K.camera(aset, "lh_g2_lampstore", _polar(2.0, 232.0, z2g + 1.6), _polar(1.9, 150.0, z2g + 1.1), 17.0)
    # gallery 3: lookout nook under the 150-degree window (window seat, spyglass, tide tables)
    p = gpos(z3g, 150.0, 0.4, 1.0)
    with mb.at((p[0], p[1], z3g), rot=150.0 - 90.0):
        mb.box((0, 0, 0.42), (1.0, 0.4, 0.06), "M_IntWood")
        mb.box((0, 0.0, 0.2), (0.96, 0.36, 0.4), "M_IntWoodDark")
    with nc.at((p[0], p[1], z3g + 0.45), rot=150.0 - 90.0):
        nc.box((0.25, 0.0, 0.04), (0.4, 0.3, 0.08), "M_IntFabricRed")                         # cushion
        nc.box((-0.3, 0.02, 0.012), (0.22, 0.3, 0.024), "M_IntFabricNavy")                   # tide tables
    with mb.at(_polar(1.55, 130.0, z3g)):                                                 # spyglass on a tripod
        for a in (0.0, 120.0, 240.0):
            r_ = math.radians(a)
            mb.beam((0.3 * math.cos(r_), 0.3 * math.sin(r_), 0.0), (0, 0, 1.15), 0.03, 0.03, "M_IntWoodDark")
        with mb.at((0, 0, 1.2), rot=150.0, rot_y=-85.0):
            mb.cylinder((0, 0, -0.3), 0.045, 0.7, "M_IntTrimGold", seg=10, radius_top=0.03)
    p = gpos(z3g, 168.0, 0.3, 0.5)
    with mb.at((p[0], p[1], z3g)), nc.at((p[0], p[1], z3g)):
        mb.box((0, 0, 0.35), (0.4, 0.3, 0.7), "M_IntWood")
        DT.mug(nc, 0.05, 0.0, 0.7, seed=31)
    x, y, _ = _polar(_lh_ri(z3g + 1.4) - 0.015, 120.0)
    with nc.at((x, y, z3g + 1.3), rot=120.0 - 90.0):
        nc.box((0, -0.01, 0), (0.4, 0.02, 0.5), "M_IntWoodDark")
        nc.box((0, -0.022, 0), (0.32, 0.005, 0.42), "M_IntPoster2")
    aset.light(_polar(1.7, 140.0, z3g + 1.9), (1.0, 0.82, 0.58), 1500.0, 5.0, night_only=False)
    K.camera(aset, "lh_g3_lookout", _polar(1.35, 170.0, z3g + 1.6), _polar(2.2, 135.0, z3g + 0.6), 14.0)
    # gallery 4: weather room under the 90-degree window (desk with the weather log, barograph, books)
    p = gpos(z4g, 90.0, 0.55, 1.1)
    with mb.at((p[0], p[1], z4g), rot=90.0 - 90.0), nc.at((p[0], p[1], z4g), rot=90.0 - 90.0):
        mb.box((0, 0, 0.74), (1.1, 0.55, 0.04), "M_IntWood")
        for sx in (-1, 1):
            mb.box((sx * 0.5, 0, 0.36), (0.05, 0.5, 0.72), "M_IntWoodDark")
        mb.box((0.0, 0.05, 0.84), (0.36, 0.22, 0.16), "M_IntWoodDark")                       # barograph case
        with nc.at((0.0, 0.05, 0.92), rot_y=90):
            nc.cylinder((0, 0, -0.12), 0.06, 0.24, "M_IntPaper", seg=10)
        nc.box((-0.35, -0.08, 0.775), (0.24, 0.32, 0.03), "M_IntFabricNavy")                  # weather log
        nc.box((-0.35, -0.08, 0.792), (0.22, 0.3, 0.004), "M_IntPaper")
        nc.box((0.38, -0.05, 0.77), (0.12, 0.18, 0.02), "M_IntScreen")                       # anemometer readout
    DT.mug(nc, p[0] + 0.3, p[1] - 0.2, z4g + 0.76, seed=33)
    aset.prop("SM_Int_WoodChair", _polar(1.45, 90.0, z4g), 90.0 + 90.0)
    p = gpos(z4g, 135.0, 0.3, 0.9)
    with mb.at((0.0, 0.0, z4g)), nc.at((0.0, 0.0, z4g)):
        K.bookcase(mb, nc, p[0], p[1], 135.0 - 90.0, w=0.9, d=0.3, h=1.8, shelves=5, rng_seed=44)
    x, y, _ = _polar(_lh_ri(z4g + 1.5) - 0.02, 70.0 + 6.0)
    _wall_map(nc, aset, x, y, z4g + 1.2, 76.0 - 90.0, 0.5, 0.4, None, seed=6)
    p = gpos(z4g, 175.0, 0.4, 0.5)
    with nc.at((p[0], p[1], z4g), rot=175.0):                                              # wind-instrument crate
        nc.box((0, 0, 0.2), (0.45, 0.4, 0.4), "M_IntWood")
        nc.cylinder((0, 0, 0.4), 0.02, 0.4, "M_IntMetal", seg=6)
        for k in range(3):
            a = math.radians(k * 120.0)
            nc.sphere((0.12 * math.cos(a), 0.12 * math.sin(a), 0.8), 0.04, "M_IntTrimWhite", seg=6, rings=4, hemi=True)
    aset.light(_polar(1.7, 120.0, z4g + 1.9), (1.0, 0.82, 0.58), 1500.0, 5.0, night_only=False)
    aset.text("WEATHER ROOM", _polar(_lh_ri(z4g + 2.1) - 0.02, 160.0, z4g + 2.1), 160.0 - 90.0, size=0.08,
              color=(0.3, 0.18, 0.08))
    K.camera(aset, "lh_g4_weather", _polar(1.4, 175.0, z4g + 1.6), _polar(2.0, 95.0, z4g + 0.7), 14.0)
    _ring_shelf(mb, nc, LH_WATCH + 1.95, 250.0, 370.0, seed=9, skip=[(355.0, 385.0)])
    _ring_shelf(mb, nc, LH_WATCH + 1.45, 186.0, 221.0, seed=19)
    x, y, _ = _polar(_lh_ri(LH_WATCH + 1.4) - 0.015, 178.0)
    with nc.at((x, y, LH_WATCH + 1.35), rot=178.0 - 90.0):                               # keepers' photograph
        nc.box((0, -0.01, 0), (0.36, 0.02, 0.28), "M_IntWoodDark")
        nc.box((0, -0.022, 0), (0.3, 0.005, 0.22), "M_IntPaper")
        nc.box((0, -0.025, -0.02), (0.22, 0.004, 0.12), "M_IntWoodDark")
    for k, (adeg, mat) in enumerate(((280.0, "M_IntPoster3"), (325.0, "M_IntPaper"))):
        x, y, _ = _polar(_lh_ri(LH_WATCH + 1.2) - 0.015, adeg)
        with nc.at((x, y, LH_WATCH + 1.15), rot=adeg - 90.0):
            nc.box((0, -0.01, 0), (0.46, 0.02, 0.4), "M_IntWoodDark")
            nc.box((0, -0.022, 0), (0.38, 0.005, 0.32), mat)
            for j in range(6 if k == 0 else 0):
                nc.box((-0.13 + (j % 3) * 0.13, -0.026, 0.07 - (j // 3) * 0.13), (0.09, 0.004, 0.08), K.FABRICS[j])
    aset.text("SIGNAL FLAGS", _polar(_lh_ri(LH_WATCH + 1.45) - 0.04, 280.0, LH_WATCH + 1.42), 280.0 - 90.0, size=0.04,
              color=(0.2, 0.12, 0.06))
    # watch room: logbook case, chart rack, lens-maintenance bench + tool board, spare lamps, barometer,
    # first aid, extinguisher, switch / outlets / smoke detector
    zr = zt
    rw = _lh_ri(zr + 1.0)

    def ring_pos(adeg, depth, width, z=0.0):
        r = math.sqrt(max(_lh_ri(zr + 1.6) ** 2 - (width / 2) ** 2, 0.0)) - 0.02 - depth / 2
        return _polar(r, adeg, z)

    p = ring_pos(255.0, 0.28, 0.8)
    K.bookcase(mb, nc, p[0], p[1], 255.0 - 90.0, w=0.8, d=0.28, h=1.5, shelves=4, rng_seed=17)
    p = ring_pos(40.0, 0.4, 0.9)
    with mb.at((p[0], p[1], zr), rot=40.0 - 90.0), nc.at((p[0], p[1], zr), rot=40.0 - 90.0):
        mb.box((0, 0, 0.86), (0.9, 0.4, 0.04), "M_IntWood")                                 # lens bench
        for sx in (-1, 1):
            mb.box((sx * 0.42, 0, 0.42), (0.05, 0.36, 0.84), "M_IntWoodDark")
        mb.box((0, 0, 0.2), (0.85, 0.36, 0.03), "M_IntWoodDark")
        nc.box((-0.25, 0.0, 0.89), (0.3, 0.22, 0.02), "M_IntFabricWhite")                    # chamois cloths
        nc.box((-0.25, 0.0, 0.91), (0.26, 0.2, 0.02), "M_IntFabricYellow")
        for k in range(3):                                                                    # polish tins
            nc.cylinder((0.05 + k * 0.09, -0.08, 0.88), 0.035, 0.05, ("M_IntTrimGold", "M_IntFabricRed", STEEL)[k], seg=10)
        nc.box((0.3, 0.05, 0.9), (0.16, 0.05, 0.04), "M_IntWoodDark")                       # lens brush
        nc.box((0.3, 0.0, 0.9), (0.12, 0.06, 0.02), "M_IntFabricWhite")
        nc.sphere((0.2, 0.1, 0.94), 0.06, "M_IntGlassClear", seg=8, rings=5)                # spare lamp bulb
        nc.box((-0.2, 0.05, 0.27), (0.4, 0.28, 0.14), "M_IntWood")                          # bulb crate
        for k in range(3):
            nc.sphere((-0.33 + k * 0.13, 0.05, 0.38), 0.05, "M_IntGlassClear", seg=8, rings=5)
    x, y, _ = _polar(_lh_ri(zr + 1.6) - 0.02, 40.0)
    with nc.at((x, y, zr + 1.25), rot=40.0 - 90.0):                                     # lens tool board
        nc.box((0, -0.01, 0.3), (0.85, 0.02, 0.6), "M_IntCork")
        for k in range(6):
            nc.box((-0.32 + k * 0.13, -0.03, 0.3), (0.035, 0.02, 0.28), ("M_IntTrimGold", STEEL, "M_IntWoodDark")[k % 3])
    aset.text("LENS CARE", _polar(_lh_ri(zr + 1.6) - 0.05, 40.0, zr + 1.95), 40.0 - 90.0, size=0.06,
              color=(0.2, 0.12, 0.06))
    p = ring_pos(110.0, 0.35, 0.35)
    with mb.at((p[0], p[1], zr)), nc.at((p[0], p[1], zr)):                                 # chart rack (rolled charts)
        mb.cylinder((0, 0, 0), 0.17, 0.55, "M_IntWood", seg=10, cap_top=False)
        for k in range(6):
            a = k * 60.0
            nc.cylinder((0.07 * math.cos(math.radians(a)), 0.07 * math.sin(math.radians(a)), 0.1), 0.03, 0.85,
                        ("M_IntPaper", "M_IntPoster2", "M_IntPaper")[k % 3], seg=6)
    x, y, _ = _polar(_lh_ri(zr + 1.5) - 0.02, 345.0)
    with nc.at((x, y, zr + 1.5), rot=345.0 - 90.0):                                     # barometer
        nc.box((0, -0.015, 0), (0.12, 0.03, 0.6), "M_IntWoodDark")
    with nc.at((x, y, zr + 1.62), rot=345.0 - 90.0, rot_x=90):
        nc.cylinder((0, 0, 0.03), 0.1, 0.02, "M_IntTrimGold", seg=14)
        nc.cylinder((0, 0, 0.05), 0.085, 0.003, "M_IntTrimWhite", seg=14)
    _wall_map(nc, aset, *_polar(_lh_ri(zr + 1.5) - 0.02, 160.0)[:2], zr + 1.15, 160.0 - 90.0, 0.6, 0.5, None, seed=2)
    x, y, _ = _polar(_lh_ri(zr + 1.5) - 0.02, 230.0)
    _first_aid(nc, aset, x, y, zr + 1.45, 230.0 - 90.0)
    ex, ey, _ = _polar(1.75, 175.0)
    aset.prop("SM_Int_Extinguisher", (ex, ey, zr), 175.0 - 90.0)
    _round_switch(nc, a_top + 8.0, zr + 1.1, _lh_ri(zr + 1.1) - 0.005)
    for adeg in (200.0, 30.0):
        _round_outlet(nc, adeg + 18.0, zr + 0.3, _lh_ri(zr + 0.3) - 0.005)
    DT.ceiling_fixture(nc, *_polar(1.6, 300.0)[:2], 18.3, "smoke")
    DT.book_stack(nc, *_polar(1.62, 195.0)[:2], zr + 0.76, 200.0, 3, seed=5)
    DT.mug(nc, *_polar(1.55, 213.0)[:2], zr + 0.76, seed=6)
    # cameras
    K.camera(aset, "lh_ground", _polar(2.2, 75.0, 2.55), _polar(2.2, 220.0, 1.6), 14.0)
    K.camera(aset, "lh_stair", _polar(2.3, 250.0, 2.0), _polar(1.2, 40.0, 9.0), 14.0)
    _wall_map(nc, aset, *_polar(_lh_ri(zr + 1.5) - 0.02, 252.0)[:2], zr + 1.2, 252.0 - 90.0, 0.55, 0.45, None, seed=7)
    aset.prop("SM_Int_Compass", _polar(1.62, 204.0, zr + 0.76), 30.0)
    DT.paper_stack(nc, *_polar(1.6, 186.0)[:2], zr + 0.76, 186.0, 4, seed=8)        # the keeper's logbook
    K.camera(aset, "lh_watch", _polar(1.5, 112.0, zr + 1.65), _polar(1.65, 215.0, zr + 0.8), 14.0)


def _keeper_hut(aset, pf, mb, nc):
    """Keeper's cottage on the platform: whitewashed walls, vaulted wooden ceiling, stove, bed, radio desk."""
    hx0, hx1, hy0, hy1 = 6.0, 10.6, -0.4, 3.2
    fz = 0.355
    pf.box_mm((hx0 - 0.1, hy0 - 0.1, 0.0), (hx1 + 0.1, hy1 + 0.1, 0.35), "M_OldStone", skip=("-z",))
    s_us = _frames(pf, (hx0, hy0), (hx1, hy0), 1.2, 2, 0.9, 0.9)
    e_us = _frames(pf, (hx1, hy0), (hx1, hy1), 1.2, 1, 0.9, 0.9)
    w_us = _frames(pf, (hx0, hy1), (hx0, hy0), 1.2, 1, 0.9, 0.9)
    hk = dict(trim=None, trim_in=K.TRIM_WOOD, base=K.TRIM_WOOD)
    for p0, p1, ops in (((hx0, hy0), (hx1, hy0), _wins(s_us, 0.9, 0.85, 1.75, mullions=1)),
                        ((hx1, hy0), (hx1, hy1), _wins(e_us, 0.9, 0.85, 1.75, mullions=1)),
                        ((hx1, hy1), (hx0, hy1), [K.Door(hx1 - 8.05, 0.9, 2.05, "wood")]),
                        ((hx0, hy1), (hx0, hy0), _wins(w_us, 0.9, 0.85, 1.75, mullions=1))):
        K.wall(aset, pf, p0, p1, 0.35, 2.4, 0.2, LH_W, inner=K.PLASTER_CREAM, openings=ops, **hk)
    cy = (hy0 + hy1) / 2
    pf.gable_roof(((hx0 + hx1) / 2, cy, 2.75), hx1 - hx0, hy1 - hy0, 1.2, LH_R, overhang=0.35,
                  thick=0.18, gable_mat=LH_W)
    _tri_in(pf, hx0 + 0.2, hy0, hy1, 2.75, 3.77, K.PLASTER_CREAM, 1)
    _tri_in(pf, hx1 - 0.2, hy0, hy1, 2.75, 3.77, K.PLASTER_CREAM, -1)
    pf.box_mm((hx1 - 1.4, hy0 + 0.8, 3.0), (hx1 - 0.8, hy0 + 1.4, 4.2), "M_OldStone")      # chimney
    # door frame (the leaf is the automatic door)
    pf.box_mm((7.5, hy1, 0.35), (7.6, hy1 + 0.08, 2.5), TRIM)
    pf.box_mm((8.5, hy1, 0.35), (8.6, hy1 + 0.08, 2.5), TRIM)
    pf.box_mm((7.6, hy1, 2.4), (8.5, hy1 + 0.08, 2.5), TRIM)
    aset.light((8.05, hy1 + 0.6, 2.6), (1.0, 0.85, 0.6), 2000.0, 6.0, night_only=True)
    # stone stoop + two steps down to the platform (the hut floor sits on a 0.35 m plinth)
    pf.box_mm((7.35, hy1 + 0.1, 0.0), (8.75, hy1 + 0.95, 0.35), "M_OldStone", skip=("-z",))
    pf.box_mm((7.35, hy1 + 0.95, 0.0), (8.75, hy1 + 1.25, 0.205), "M_OldStone", skip=("-z",))
    nc.box((8.05, hy1 + 0.12, 2.65), (0.25, 0.08, 0.15), GLOW)
    # vaulted wooden ceiling under the roof planes + ridge beam
    xa, xb = hx0 + 0.2, hx1 - 0.2
    zr_ = 3.77 - 0.02
    for yw in (hy0 + 0.2, hy1 - 0.2):
        zw = 2.57 + 0.2 / ((hy1 - hy0) / 2) * 1.2 - 0.02
        q = [(xa, yw, zw), (xa, cy, zr_), (xb, cy, zr_), (xb, yw, zw)]
        pf.poly(q if yw < cy else q[::-1], "M_IntCeilingWood")
    mb.box((8.3, cy, zr_ - 0.08), (xb - xa, 0.14, 0.14), "M_IntWoodDark")
    K.floor_planks(mb, xa, hy0 + 0.2, xb, hy1 - 0.2, fz)
    H = _Shifted(aset, (0.0, 0.0, fz))
    with mb.at((0.0, 0.0, fz)), nc.at((0.0, 0.0, fz)):
        K.single_bed(mb, nc, 6.72, 0.85, 90.0, blanket="M_IntFabricRed", length=1.9, width=0.95)
        K.desk(mb, nc, 8.1, 0.12, 180.0, w=1.0, d=0.55, hutch=False, rng_seed=3)
        H.prop("SM_Int_Radio", (8.38, 0.12, 0.76), 180.0)
        H.prop("SM_Int_OilLamp", (7.75, 0.15, 0.76), 0.0)
        H.prop("SM_Int_WoodChair", (8.1, 0.78, 0.0), 0.0)
        # pot-belly stove under the chimney
        mb.box((9.95, 0.5, 0.02), (0.8, 0.8, 0.04), "M_OldStone")
        mb.cylinder((9.95, 0.5, 0.04), 0.3, 0.7, "M_IntBlack", seg=14)
        mb.cylinder((9.95, 0.5, 0.74), 0.34, 0.06, "M_IntBlack", seg=14)
        mb.cylinder((9.95, 0.5, 0.8), 0.07, 2.07, "M_IntBlack", seg=8)
        nc.box((9.95, 0.19, 0.3), (0.2, 0.02, 0.14), "M_IntFire")
        H.prop("SM_Int_Kettle", (9.8, 0.42, 0.8), 0.0)
        aset.light((9.95, 0.9, fz + 0.5), (1.0, 0.55, 0.25), 1500.0, 4.0, night_only=False)
        H.prop("SM_Int_RockingChair", (9.3, 1.85, 0.0), 25.0)
        K.rug(mb, 7.4, 0.95, 9.7, 2.25, 0.0, "M_IntCarpetRed", K.TRIM_GOLD)
        H.prop("SM_Int_SideTable", (8.55, 1.45, 0.0), 0.0)
        H.prop("SM_Int_TeaSet", (8.55, 1.45, 0.56), 20.0)
        # keeper's things: logbooks, binoculars, mug, sea chart, boots, nightstand, fishing rod, sea chest
        nc.box((8.35, 0.0, 0.775), (0.22, 0.3, 0.03), "M_IntFabricNavy")
        nc.box((8.35, 0.0, 0.792), (0.2, 0.28, 0.004), "M_IntPaper")
        H.prop("SM_Int_Binoculars", (7.9, -0.02, 0.76), 160.0)
        DT.mug(nc, 7.72, 0.25, 0.76, seed=4)
        H.prop("SM_Int_NightstandB", (6.5, 2.35, 0.0), 90.0)
        H.prop("SM_Int_Books", (6.5, 2.35, 0.62), 90.0)
        H.prop("SM_Int_Boots", (9.25, 2.78, 0.0), 0.0)
        nc.beam((10.3, 2.95, 0.02), (10.25, 2.9, 2.0), 0.02, 0.02, "M_IntWoodDark")         # fishing rod
        _wall_map(nc, H, 9.2, hy1 - 0.2, 1.3, 0.0, 0.6, 0.45, None, seed=8)
        H.prop("SM_Int_Shelves", (10.23, 2.45, 0.0), -90.0)
        H.prop("SM_Int_Lifebuoy", (6.85, hy1 - 0.2, 0.95), 0.0)
        H.prop("SM_Int_Frame", (hx0 + 0.2, 2.5, 1.4), 90.0)
        H.prop("SM_Int_WallClock", (9.5, hy1 - 0.2, 1.75), 0.0)
        K.poster(nc, H, hx0 + 0.2, 0.3, 1.55, 90.0, 0.4, 0.55, "M_IntPoster2", "TIDES", text_size=0.08)
        nc.box((7.05, hy1 - 0.27, 1.25), (0.38, 0.1, 0.8), "M_IntFabricYellow")       # raincoat on a hook
        nc.box((7.05, hy1 - 0.22, 1.68), (0.06, 0.06, 0.06), "M_IntWoodDark")
        K.pendant(H, 8.3, cy, zr_ - 0.15 - fz, "lamp")
    DT.dress_room(aset, mb, nc, hx0 + 0.2, hy0 + 0.2, hx1 - 0.2, hy1 - 0.2, fz, 3.45, style="dorm", seed=7, ac=False)
    K.camera(aset, "lh_hut", (6.5, 2.75, fz + 1.65), (10.0, 0.4, fz + 0.7), 15.0)


def build_lighthouse():
    aset = AssetSet("lighthouse")
    tw = aset.mesh("Lighthouse_Tower")
    pf = aset.mesh("Lighthouse_Platform")
    nc = aset.mesh("Lighthouse_NoCol")
    im = aset.mesh("Lighthouse_Interior")
    inc = aset.mesh("Lighthouse_Interior_NoCol")

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
    # (hollow: outer skin with the doorway cut out, inner skin + rooms in _lighthouse_tower_inside)
    def band(z):
        return LH_R if (6.0 < z < 9.0 or 12.0 < z < 15.0) else LH_W
    _lh_shell(tw, [0.95, 1.5], _lh_ro, band, False)
    _lh_shell(tw, [1.5, LH_DOOR[3], 6.0, 9.0, 12.0, 15.0, 17.55], _lh_ro, band, False)
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
    # hollow vestibule: side walls, front wall with the doorway, ceiling slab under the little roof
    for sx in (-1, 1):
        tw.box_mm((min(sx * 1.35, sx * 1.15), 2.6, 0.95), (max(sx * 1.35, sx * 1.15), 3.95, 3.9), LH_W,
                  mats={"+x" if sx < 0 else "-x": K.PLASTER_CREAM})
        tw.box_mm((min(sx * 1.15, sx * 0.75), 3.75, 0.95), (max(sx * 1.15, sx * 0.75), 3.95, 3.9), LH_W,
                  mats={"-y": K.PLASTER_CREAM})
    tw.box_mm((-0.75, 3.75, 3.35), (0.75, 3.95, 3.9), LH_W, mats={"-y": K.PLASTER_CREAM, "-z": K.TRIM_WOOD})
    tw.box_mm((-1.15, 2.9, 3.45), (1.15, 3.75, 3.9), LH_W, mats={"-z": K.CEIL})
    tw.gable_roof((0.0, 3.125, 3.9), 2.7, 1.65, 0.75, LH_R, overhang=0.2, thick=0.15, gable_mat=LH_W,
                  ridge_axis="y")
    tw.box_mm((-0.92, 3.95, 0.95), (-0.75, 4.03, 3.5), TRIM)
    tw.box_mm((0.75, 3.95, 0.95), (0.92, 4.03, 3.5), TRIM)
    tw.box_mm((-0.75, 3.95, 3.35), (0.75, 4.03, 3.5), TRIM)
    aset.door((0.0, 3.85, 0.95), 180.0, 1.5, 2.4, "lighthouse", double=True)
    aset.arrival((0.0, 7.5, 0.95), -90.0)           # on the rock apron outside the door, facing it
    tw.box((0.0, 4.02, 3.62), (0.4, 0.12, 0.2), DMETAL)
    nc.box((0.0, 4.09, 3.55), (0.3, 0.04, 0.06), GLOW)
    aset.light((0.0, 4.6, 3.4), (1.0, 0.85, 0.6), 2000.0, 7.0, night_only=True)
    # small windows spiralling up
    for z, adeg in LH_WINDOWS:                    # real openings: frame ring, clear pane, reveals through the wall
        r = _lh_r(z)
        a = math.radians(adeg)
        with tw.at((math.cos(a) * (r - 0.1), math.sin(a) * (r - 0.1), z), rot=adeg + 90.0):
            for sx in (-1, 1):
                tw.box((sx * (0.31 + 0.0825), 0, 0), (0.165, 0.32, 1.25), TRIM)
                tw.box((0, 0, sx * (0.46 + 0.0825)), (0.62, 0.32, 0.165), TRIM)
            tw.box((0, 0.02, 0), (0.62, 0.03, 0.92), "M_GlassClear")
        z0w, z1w = z - LH_WIN_H, z + LH_WIN_H
        for ad, flip in ((adeg - LH_WIN_DA, False), (adeg + LH_WIN_DA, True)):
            pts = [_polar(_lh_ri(z0w), ad, z0w), _polar(_lh_ro(z0w), ad, z0w), _polar(_lh_ro(z1w), ad, z1w),
                   _polar(_lh_ri(z1w), ad, z1w)]
            tw.poly(pts[::-1] if flip else pts, LH_W)
        for zz in (z0w, z1w):
            _polar_slab(tw, _lh_ri(zz), _lh_ro(zz), adeg - LH_WIN_DA, adeg + LH_WIN_DA, zz + 0.0005, 0.001, LH_W, LH_W,
                        LH_W, step=5.0, caps=False)

    # ---------------------------------------------------------------- keeper's hut + tower interior
    _keeper_hut(aset, pf, im, inc)
    _lighthouse_tower_inside(aset, tw, im, inc)
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


PLACEMENTS = {"harbor": with_travel(build_harbor, [
    ("terminal_hall", "harbor_terminal", "Ferry Terminal", "Departure hall, ticket office and the harbor master upstairs."),
]), "lighthouse": with_travel(build_lighthouse, [
    ("lh_watch", "lighthouse_top", "Lighthouse Watch Room", "The top of the tower, under the lantern - the whole harbor below."),
])}
