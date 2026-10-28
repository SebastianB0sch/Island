"""
Obelisk Blue dormitories.

  obelisk_boys  - the boys' palace: a white three-storey mansion with deep blue mansard
                  roofs, a columned portico with a gilded pediment, a domed centre, end
                  pavilions, and a formal courtyard (tiered fountain, hedge parterres,
                  iron gate) in front.
  obelisk_girls - the girls' lakeside mansion: white walls, light blue roofs, pink trims,
                  four round corner turrets, a glass conservatory, a front terrace, a
                  garden with a domed gazebo and a wooden lake jetty.

Local space (metres): origin = centre of the pad at finished ground level, front = -Y.
"""

import math
from contextlib import contextmanager

from . import AssetSet

TAU = math.pi * 2.0

# ----------------------------------------------------------------------------- tunables
# Girls' dorm lake jetty: local XY of the jetty ROOT (where the ramp meets the deck, i.e.
# roughly the shore line).  The deck runs from there towards -Y (rotated by JETTY_YAW, CCW
# degrees) for JETTY_LENGTH metres; the ramp climbs from the deck (z=-2.4) back towards +Y
# up to JETTY_LAND_Z over 6 m and ends in a 3 m landing.  Stone sides reach down to -6, so
# whatever the bank height is, the causeway reads as a little stone pier.
JETTY_OFFSET = (10.0, -100.0)
JETTY_YAW = 0.0
JETTY_LAND_Z = -1.2
JETTY_LENGTH = 25.0
JETTY_DECK_Z = -2.4
LAKE_Z = -3.0

# ----------------------------------------------------------------------------- materials
WALL = "M_ObeliskWall"
ROOF = "M_ObeliskRoof"
TRIM = "M_ObeliskTrim"
GROOF = "M_GirlsRoof"
GTRIM = "M_GirlsTrim"
GOLD = "M_Gold"
MARBLE = "M_Marble"
FLOOR = "M_MarbleFloor"
GLASS = "M_Glass"
CLEAR = "M_GlassClear"
FRAME = "M_WindowFrame"
PAVE = "M_Paving"
HEDGE = "M_Hedge"
WATER = "M_LakeWater"
FALLS = "M_Waterfall"
GLOW = "M_LampGlow"
IRON = "M_DarkMetal"
PIER = "M_PierWood"
SOIL = "M_Soil"

GOLD_RGB = (1.0, 0.78, 0.28)
# paving tops: overlapping paving layers never share a plane (no z-fighting)
P_LOW, P_RING = 0.035, 0.07
WARM = (1.0, 0.82, 0.58)


# ============================================================================= helpers
def circle(n, r, cx=0.0, cy=0.0, a0=0.0, sx=1.0, sy=1.0):
    """CCW ring of n points."""
    return [(cx + math.cos(a0 + TAU * i / n) * r * sx, cy + math.sin(a0 + TAU * i / n) * r * sy)
            for i in range(n)]


def xf(origin, yaw, p):
    """Transform a local point p (x, y[, z]) of a frame at origin (x, y[, z]) rotated by yaw."""
    a = math.radians(yaw)
    c, s = math.cos(a), math.sin(a)
    x, y = p[0], p[1]
    z = (p[2] if len(p) > 2 else 0.0) + (origin[2] if len(origin) > 2 else 0.0)
    return (origin[0] + c * x - s * y, origin[1] + s * x + c * y, z)


def face_yaw(px, py, tx, ty):
    """Yaw that makes a -Y facing socket (bench, text) look from (px, py) towards (tx, ty)."""
    return math.degrees(math.atan2(tx - px, -(ty - py)))


@contextmanager
def facade(mb, p0, p1, z=0.0):
    """Local frame on a face running p0 -> p1 (outside to the RIGHT): x along, -y outwards."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    with mb.at((p0[0], p0[1], z), rot=math.degrees(math.atan2(dy, dx))):
        yield math.hypot(dx, dy)


@contextmanager
def follow(mb, other):
    """Put `other` (e.g. the NoCol builder, at identity) into mb's current frame (translation + yaw)."""
    m = mb.matrix
    with other.at(tuple(m.translation), rot=math.degrees(m.to_euler().z)):
        yield other


def rect_faces(x0, y0, x1, y1):
    """The four outward faces of an axis aligned block, each as (p0, p1) with outside right."""
    return {"front": ((x0, y0), (x1, y0)), "right": ((x1, y0), (x1, y1)),
            "back": ((x1, y1), (x0, y1)), "left": ((x0, y1), (x0, y0))}


def lathe_crisp(mb, profile, mat, seg=24, center=(0, 0, 0), cap_top=False, cap_bottom=False):
    """Lathe where every profile segment is shaded separately (crisp mouldings)."""
    for i in range(len(profile) - 1):
        mb.lathe([profile[i], profile[i + 1]], mat, seg, cap_top=False, cap_bottom=False, center=center)
    cx, cy, cz = center
    if cap_top and profile[-1][0] > 1e-4:
        r, z = profile[-1]
        mb.poly([(x, y, cz + z) for x, y in circle(seg, r, cx, cy)], mat)
    if cap_bottom and profile[0][0] > 1e-4:
        r, z = profile[0]
        mb.poly([(x, y, cz + z) for x, y in reversed(circle(seg, r, cx, cy))], mat)


def lathe_arc(mb, profile, mat, a0, a1, seg=12, center=(0, 0, 0), smooth=True):
    """Partial surface of revolution between angles a0..a1 (radians, a1 > a0)."""
    cx, cy, cz = center
    rows = []
    for r, z in profile:
        rows.append([(cx + math.cos(a0 + (a1 - a0) * i / seg) * r,
                      cy + math.sin(a0 + (a1 - a0) * i / seg) * r, cz + z) for i in range(seg + 1)])
    mb.grid_faces(rows, mat, smooth=smooth, closed_u=False)


def disc(mb, cx, cy, z, r, mat, seg=32, down=False):
    pts = [(x, y, z) for x, y in circle(seg, r, cx, cy)]
    mb.poly(list(reversed(pts)) if down else pts, mat)


def arc_band(mb, cx, cz, r_in, r_out, a0, a1, seg, y0, y1, mat):
    """Curved band in the XZ plane (front face at y0 facing -y), angles a0 < a1 in radians."""
    for i in range(seg):
        t0 = a0 + (a1 - a0) * i / seg
        t1 = a0 + (a1 - a0) * (i + 1) / seg
        o0 = (cx + math.cos(t0) * r_out, cz + math.sin(t0) * r_out)
        o1 = (cx + math.cos(t1) * r_out, cz + math.sin(t1) * r_out)
        i0 = (cx + math.cos(t0) * r_in, cz + math.sin(t0) * r_in)
        i1 = (cx + math.cos(t1) * r_in, cz + math.sin(t1) * r_in)
        mb.quad((i0[0], y0, i0[1]), (o0[0], y0, o0[1]), (o1[0], y0, o1[1]), (i1[0], y0, i1[1]), mat)
        mb.quad((i1[0], y1, i1[1]), (o1[0], y1, o1[1]), (o0[0], y1, o0[1]), (i0[0], y1, i0[1]), mat)
        mb.quad((o0[0], y0, o0[1]), (o0[0], y1, o0[1]), (o1[0], y1, o1[1]), (o1[0], y0, o1[1]), mat)
        mb.quad((i1[0], y0, i1[1]), (i1[0], y1, i1[1]), (i0[0], y1, i0[1]), (i0[0], y0, i0[1]), mat)


def segmental_arc(mb, half_w, z_chord, rise, thick, y0, y1, mat, seg=10):
    """Flat (segmental) arch band over a chord of 2*half_w at z_chord; rise = apex height above."""
    R = (half_w * half_w + rise * rise) / (2.0 * rise)
    zc = z_chord + rise - R
    a = math.atan2(z_chord - zc, half_w)
    arc_band(mb, 0.0, zc, R - thick, R, a, math.pi - a, seg, y0, y1, mat)
    return R, zc, a


def prism_xz(mb, pts, y0, y1, mat, front=True, back=True, front_mat=None):
    """Extrude a CCW (seen from -Y) XZ polygon from y0 (front) to y1."""
    n = len(pts)
    if front:
        mb.poly([(x, y0, z) for x, z in pts], front_mat or mat)
    if back:
        mb.poly([(x, y1, z) for x, z in reversed(pts)], mat)
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % n]
        mb.quad((p[0], y0, p[1]), (p[0], y1, p[1]), (q[0], y1, q[1]), (q[0], y0, q[1]), mat)


def prism_yz(mb, pts, x0, x1, mat, caps=True):
    """Extrude a CCW (seen from +X) YZ polygon along X from x0 to x1."""
    n = len(pts)
    for i in range(n):
        p, q = pts[i], pts[(i + 1) % n]
        mb.quad((x0, p[0], p[1]), (x0, q[0], q[1]), (x1, q[0], q[1]), (x1, p[0], p[1]), mat)
    if caps:
        mb.poly([(x1, y, z) for y, z in pts], mat)
        mb.poly([(x0, y, z) for y, z in reversed(pts)], mat)


def frustum(mb, b, t, z0, z1, mat, cap_mat=None, bottom=True):
    """Sloped sides from rectangle b=(x0,y0,x1,y1) at z0 up to rectangle t at z1."""
    B = [(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])]
    T = [(t[0], t[1]), (t[2], t[1]), (t[2], t[3]), (t[0], t[3])]
    for i in range(4):
        j = (i + 1) % 4
        mb.quad((B[i][0], B[i][1], z0), (B[j][0], B[j][1], z0), (T[j][0], T[j][1], z1),
                (T[i][0], T[i][1], z1), mat)
    if bottom:
        mb.poly([(p[0], p[1], z0) for p in reversed(B)], mat)
    if cap_mat:
        mb.poly([(p[0], p[1], z1) for p in T], cap_mat)


def hip_top(mb, x0, y0, x1, y1, z0, h, mat, double=False):
    """Hipped cap over a rectangle (no overhang, no underside); ridge along the long axis.
    Returns the ridge end points."""
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, d = x1 - x0, y1 - y0
    top = z0 + h
    a, b, c, e = (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)
    if w >= d:
        rl = (w - d) / 2
        r0, r1 = (cx - rl, cy, top), (cx + rl, cy, top)
        faces = [[a, b, r1, r0], [b, c, r1], [c, e, r0, r1], [e, a, r0]]
    else:
        rl = (d - w) / 2
        r0, r1 = (cx, cy - rl, top), (cx, cy + rl, top)
        faces = [[a, b, r0], [b, c, r1, r0], [c, e, r1], [e, a, r0, r1]]
    for f in faces:
        if len(f) == 4 and rl < 1e-3:
            f = [f[0], f[1], f[2]]
        mb.poly(f, mat)
        if double:
            mb.poly(list(reversed(f)), mat)
    return r0, r1


def slab(mb, x0, y0, x1, y1, top=0.05, mat=PAVE, depth=0.35, mats=None):
    """Paving slab whose top is at `top` (default a few cm above the pad)."""
    mb.box_mm((x0, y0, top - depth), (x1, y1, top), mat, skip=("-z",), mats=mats)


def strip(mb, p0, p1, width, top=0.05, mat=PAVE, depth=0.35):
    """Paved strip of `width` between two XY points (any direction)."""
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    with mb.at((p0[0], p0[1], 0), rot=math.degrees(math.atan2(dy, dx))):
        mb.box_mm((0, -width / 2, top - depth), (L, width / 2, top), mat, skip=("-z",))


def ring_slab(mb, cx, cy, r_in, r_out, top=0.05, mat=PAVE, seg=40, depth=0.35):
    mb.slab_ring(circle(seg, r_out, cx, cy), circle(seg, r_in, cx, cy), top - depth, top, mat)


def flight(mb, origin, yaw, width, n, rise, run, mat, z_base=-0.6, top_mat=None):
    """Straight stairs climbing along local +x from origin (bottom front edge centre)."""
    with mb.at(origin, rot=yaw):
        for i in range(n):
            mb.box_mm((run * i, -width / 2, z_base), (run * (i + 1), width / 2, rise * (i + 1)), mat,
                      skip=("-z",), mats={"+z": top_mat} if top_mat else None)


def baluster(mb, x, y, z, h, mat, seg=6):
    mb.lathe([(0.065, 0.0), (0.105, h * 0.22), (0.05, h * 0.62), (0.075, h * 0.86), (0.06, h)],
             mat, seg, cap_top=False, cap_bottom=False, center=(x, y, z))


def balustrade(mb, pts, z, mat=MARBLE, rail_mat=None, h=1.0, spacing=0.3, posts=True, closed=False,
               post_mat=None, post_every=None):
    """Classical balustrade along a 2D polyline at height z (bottom rail, vase balusters, top rail)."""
    rail_mat = rail_mat or mat
    post_mat = post_mat or rail_mat
    P = list(pts) + ([pts[0]] if closed else [])
    post_pts = []
    for i in range(len(P) - 1):
        (x0, y0), (x1, y1) = P[i], P[i + 1]
        L = math.hypot(x1 - x0, y1 - y0)
        if L < 0.3:
            continue
        mb.beam((x0, y0, z + 0.08), (x1, y1, z + 0.08), 0.3, 0.16, rail_mat)
        mb.beam((x0, y0, z + h - 0.07), (x1, y1, z + h - 0.07), 0.32, 0.14, rail_mat)
        n = max(1, int(L / spacing))
        for k in range(n):
            t = (k + 0.5) / n
            baluster(mb, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z + 0.16, h - 0.30, mat)
        post_pts.append((x0, y0))
        if post_every:
            m = int(L / post_every)
            for k in range(1, m):
                post_pts.append((x0 + (x1 - x0) * k / m, y0 + (y1 - y0) * k / m))
        if i == len(P) - 2 and not closed:
            post_pts.append((x1, y1))
    if posts:
        for (x, y) in post_pts:
            mb.box((x, y, z + (h + 0.08) / 2), (0.38, 0.38, h + 0.08), post_mat)
            mb.box((x, y, z + h + 0.1), (0.46, 0.46, 0.08), rail_mat)


def iron_railing(mb, pts, z, h=1.0, mat=IRON, spacing=0.14, tip_mat=None):
    """Light wrought-iron railing (vertical bars, two rails, optional gilded tips)."""
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(L / spacing))
        for k in range(n + 1):
            t = k / n
            x, y = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            mb.box((x, y, z + h / 2), (0.035, 0.035, h), mat, skip=("-z",))
            if tip_mat and k % 2 == 0:
                mb.pyramid((x, y, z + h), 0.07, 0.07, 0.14, tip_mat, base=False)
        mb.beam((x0, y0, z + h - 0.05), (x1, y1, z + h - 0.05), 0.05, 0.05, mat)
        mb.beam((x0, y0, z + 0.12), (x1, y1, z + 0.12), 0.05, 0.05, mat)


def finial(mb, x, y, z, s=1.0, mat=GOLD, seg=10):
    mb.lathe([(0.2 * s, 0.0), (0.26 * s, 0.08 * s), (0.1 * s, 0.22 * s), (0.09 * s, 0.42 * s),
              (0.22 * s, 0.56 * s), (0.27 * s, 0.72 * s), (0.22 * s, 0.88 * s), (0.08 * s, 1.0 * s),
              (0.05 * s, 1.45 * s), (0.004 * s, 1.85 * s)], mat, seg, center=(x, y, z))


def ball_finial(mb, x, y, z, r=0.3, mat=GOLD):
    mb.lathe([(r * 0.6, 0.0), (r * 0.35, r * 0.3)], mat, 10, cap_bottom=True, cap_top=False, center=(x, y, z))
    mb.sphere((x, y, z + r * 1.2), r, mat, seg=12, rings=8)


def urn(mb, x, y, z, s=1.0, mat=MARBLE):
    lathe_crisp(mb, [(0.28 * s, 0.0), (0.28 * s, 0.12 * s), (0.14 * s, 0.2 * s), (0.12 * s, 0.35 * s),
                     (0.38 * s, 0.6 * s), (0.45 * s, 0.85 * s), (0.36 * s, 1.0 * s), (0.42 * s, 1.08 * s)],
                mat, seg=14, center=(x, y, z), cap_top=True)


def column(mb, x, y, z, r, h, mat=MARBLE, cap_mat=None, seg=16):
    """Classical column: square plinth, moulded base, tapered shaft, flared capital + abacus."""
    cm = cap_mat or mat
    mb.box((x, y, z + 0.18), (r * 2.7, r * 2.7, 0.36), cm, skip=("-z",))
    lathe_crisp(mb, [(r * 1.28, 0.36), (r * 1.28, 0.5), (r * 1.06, 0.66)], mat, seg, center=(x, y, z))
    mb.lathe([(r * 1.06, 0.66), (r, 0.8), (r * 0.97, h * 0.4), (r * 0.86, h - 0.75)], mat, seg,
             cap_top=False, cap_bottom=False, center=(x, y, z))
    lathe_crisp(mb, [(r * 0.86, h - 0.75), (r * 0.95, h - 0.62), (r * 1.3, h - 0.38)], cm, seg, center=(x, y, z))
    mb.box((x, y, z + h - 0.19), (r * 2.8, r * 2.8, 0.38), cm)


def window(mb, u, z, w, h, frame=FRAME, glass=GLASS, arch=False, head=None, head_mat=None,
           sill_mat=None, mullion=True, shutter_mat=None, keystone=None, fw=0.15, fd=0.12, seg=8):
    """Framed window on a facade frame (wall plane y=0, outside -y). z = sill height, h = height
    of the rectangular part (arched windows add a semicircle of radius w/2 on top)."""
    gy = -0.03
    hm = head_mat or frame
    mb.poly([(u - w / 2, gy, z), (u + w / 2, gy, z), (u + w / 2, gy, z + h), (u - w / 2, gy, z + h)], glass)
    r = w / 2.0
    top = z + h
    if arch:
        pts = [(u + math.cos(math.pi * i / seg) * r, gy, top + math.sin(math.pi * i / seg) * r)
               for i in range(seg + 1)]
        mb.poly(pts, glass)
        arc_band(mb, u, top, r, r + fw, 0.0, math.pi, seg, -fd, 0.0, frame)
        top_ext = top + r + fw
    else:
        mb.box((u, -fd / 2, top + fw / 2), (w + 2 * fw, fd, fw), frame, skip=("+y",))
        top_ext = top + fw
    for s in (-1, 1):
        mb.box((u + s * (w / 2 + fw / 2), -fd / 2, z + h / 2), (fw, fd, h), frame, skip=("+y",))
    mb.box((u, -0.13, z - 0.07), (w + 2 * fw + 0.2, 0.26, 0.14), sill_mat or frame, skip=("+y",))
    if mullion:
        mh = h + (r if arch else 0.0)
        mb.box((u, -0.05, z + mh / 2), (0.07, 0.05, mh), frame, skip=("+y",))
        mb.box((u, -0.05, z + h * 0.68), (w, 0.05, 0.07), frame, skip=("+y",))
    if head in ("lintel", "pediment"):
        mb.box((u, -0.15, top_ext + 0.09), (w + 2 * fw + 0.4, 0.3, 0.18), hm, skip=("+y",))
        if head == "pediment":
            hw = w / 2 + fw + 0.2
            prism_xz(mb, [(u - hw, top_ext + 0.18), (u + hw, top_ext + 0.18), (u, top_ext + 0.62)],
                     -0.26, 0.0, hm, back=False)
    elif head == "segment":
        with mb.at((u, 0, 0)):
            segmental_arc(mb, w / 2 + fw + 0.12, top_ext - 0.05, 0.32, 0.2, -0.22, 0.0, hm, seg=6)
    if keystone:
        kz = top_ext if not arch else top + r + fw
        mb.box((u, -0.1, kz - 0.05), (0.32, 0.2, 0.46), keystone, skip=("+y",))
    if shutter_mat:
        for s in (-1, 1):
            mb.box((u + s * (w / 2 + fw + w * 0.27), -0.05, z + h / 2), (w * 0.5, 0.06, h), shutter_mat,
                   skip=("+y",))
    return top_ext


def door(mb, u, z, w, h, leaf=TRIM, surround=MARBLE, handle=GOLD, fan_glass=GLASS, fan=True,
         panel_mat=None, depth=0.3):
    """Closed double door with a moulded surround and an optional arched fanlight (facade frame)."""
    pm = panel_mat or handle
    mb.box((u, -0.05, z + h / 2), (w, 0.1, h), leaf, skip=("+y",))
    for s in (-1, 1):
        cx = u + s * w / 4
        for (zz, hh) in ((z + h * 0.08, h * 0.36), (z + h * 0.52, h * 0.4)):
            # thin gilded panel mouldings
            pw = w / 2 - 0.3
            mb.box((cx, -0.115, zz + hh / 2), (pw, 0.03, 0.05), pm, skip=("+y",))
            mb.box((cx, -0.115, zz + 0.025), (pw, 0.03, 0.05), pm, skip=("+y",))
            mb.box((cx, -0.115, zz + hh - 0.025), (pw, 0.03, 0.05), pm, skip=("+y",))
            mb.box((cx - pw / 2 + 0.025, -0.115, zz + hh / 2), (0.05, 0.03, hh), pm, skip=("+y",))
            mb.box((cx + pw / 2 - 0.025, -0.115, zz + hh / 2), (0.05, 0.03, hh), pm, skip=("+y",))
        mb.box((u + s * 0.12, -0.16, z + h * 0.48), (0.06, 0.1, 0.5), handle, skip=("+y",))
    mb.box((u, -0.11, z + h / 2), (0.04, 0.02, h), "M_Black", skip=("+y",))
    sw = 0.4
    for s in (-1, 1):
        mb.box((u + s * (w / 2 + sw / 2), -depth / 2, z + h / 2), (sw, depth, h), surround, skip=("+y",))
    if fan:
        r = w / 2 + 0.02
        pts = [(u + math.cos(math.pi * i / 10) * r, -0.03, z + h + math.sin(math.pi * i / 10) * r)
               for i in range(11)]
        mb.poly(pts, fan_glass)
        for k in range(1, 4):
            a = math.pi * k / 4
            mb.beam((u, -0.06, z + h), (u + math.cos(a) * r, -0.06, z + h + math.sin(a) * r), 0.05, 0.05, surround)
        mb.box((u, -0.06, z + h + 0.03), (w, 0.06, 0.06), surround, skip=("+y",))
        arc_band(mb, u, z + h, r, r + sw, 0.0, math.pi, 10, -depth, 0.0, surround)
        mb.box((u, -depth / 2 - 0.05, z + h + r + sw / 2), (0.42, depth + 0.1, 0.6), GOLD)
        return z + h + r + sw
    mb.box((u, -depth / 2, z + h + sw / 2), (w + 2 * sw, depth, sw), surround, skip=("+y",))
    return z + h + sw


def dormer(mb, w, h, depth, z0, wall, roof, frame, glass=GLASS, arch=False, finial_mat=None,
           head_mat=None):
    """Dormer in a frame whose origin is the dormer's front-centre at the eave (front faces -y)."""
    mb.box_mm((-w / 2, 0.0, z0), (w / 2, depth, z0 + h), wall, skip=("-z",))
    mb.gable_roof((0.0, depth / 2, z0 + h), w, depth, w * 0.42, roof, overhang=0.18, thick=0.12,
                  gable_mat=wall, ridge_axis="y")
    ww = w - 0.75
    if arch:
        window(mb, 0.0, z0 + 0.3, ww, h - 0.75 - ww / 2, frame, glass, arch=True, fw=0.12, seg=6,
               sill_mat=head_mat or frame)
    else:
        window(mb, 0.0, z0 + 0.3, ww, h - 0.65, frame, glass, fw=0.12, sill_mat=head_mat or frame)
    if finial_mat:
        finial(mb, 0.0, -0.1, z0 + h + w * 0.42 - 0.05, 0.35, finial_mat, seg=8)


def emblem(mb, x, y, z, s=1.0, mat=GOLD):
    """Generic gilded crest (ring, small obelisk, two wings) facing -Y; centre at (x, y, z)."""
    with mb.at((x, y, z)):
        with mb.at((0, 0, 0), rot_x=90):
            mb.torus((0, 0, 0), 0.9 * s, 0.09 * s, mat, seg=20, tube_seg=6)
        prism_xz(mb, [(-0.16 * s, -0.75 * s), (0.16 * s, -0.75 * s), (0.11 * s, 0.45 * s),
                      (0.0, 0.72 * s), (-0.11 * s, 0.45 * s)], -0.12 * s, 0.0, mat, back=False)
        for sx in (-1, 1):
            for feather in ([(0.95, -0.15), (1.75, 0.0), (1.65, 0.45), (0.95, 0.15)],
                            [(0.9, -0.4), (1.45, -0.4), (1.6, -0.12), (0.95, -0.18)]):
                pts = [(sx * x * s, z * s) for x, z in feather]     # convex, CCW seen from -Y
                if sx < 0:
                    pts = list(reversed(pts))                         # mirrored -> keep CCW
                prism_xz(mb, pts, -0.08 * s, 0.0, mat, back=False)


def lantern(mb, nc, x, y, z, s=1.0, frame=IRON, glow=GLOW, cap=GOLD):
    """Small lantern (glass glow in the no-collision mesh) standing on (x, y, z)."""
    mb.box((x, y, z + 0.05 * s), (0.36 * s, 0.36 * s, 0.1 * s), frame)
    with follow(mb, nc):
        nc.box((x, y, z + 0.33 * s), (0.28 * s, 0.28 * s, 0.46 * s), glow)
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box((x + sx * 0.15 * s, y + sy * 0.15 * s, z + 0.33 * s), (0.04 * s, 0.04 * s, 0.46 * s), frame)
    mb.pyramid((x, y, z + 0.56 * s), 0.46 * s, 0.46 * s, 0.26 * s, frame)
    mb.sphere((x, y, z + 0.86 * s), 0.06 * s, cap, seg=8, rings=4)


def block_shell(mb, x0, y0, x1, y1, top, fl, bands, wall=WALL, base=MARBLE, band_mat=TRIM,
                cornice=(MARBLE, TRIM), pilasters=True, pil_mat=MARBLE, base_band=None):
    """Solid building block with base course, string courses, two-step cornice, corner pilasters."""
    mb.box_mm((x0, y0, -4.0), (x1, y1, top), wall, skip=("-z", "+z"))
    mb.box_mm((x0 - 0.2, y0 - 0.2, -4.0), (x1 + 0.2, y1 + 0.2, fl + 0.3), base, skip=("-z",))
    if base_band:
        mb.box_mm((x0 - 0.24, y0 - 0.24, fl + 0.3), (x1 + 0.24, y1 + 0.24, fl + 0.45), base_band)
    for z in bands:
        mb.box_mm((x0 - 0.1, y0 - 0.1, z - 0.14), (x1 + 0.1, y1 + 0.1, z + 0.14), band_mat)
    mb.box_mm((x0 - 0.22, y0 - 0.22, top - 0.95), (x1 + 0.22, y1 + 0.22, top - 0.6), cornice[0], skip=("+z",))
    mb.box_mm((x0 - 0.5, y0 - 0.5, top - 0.6), (x1 + 0.5, y1 + 0.5, top), cornice[1], skip=("+z",))
    if pilasters:
        for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1)):
            xa, xb = cx - sx * 0.12, cx + sx * 0.75
            ya, yb = cy - sy * 0.12, cy + sy * 0.75
            mb.box_mm((min(xa, xb), min(ya, yb), fl + 0.3), (max(xa, xb), max(ya, yb), top - 0.95), pil_mat,
                      skip=("-z", "+z"))


def mansard_x(mb, x0, x1, y0, y1, z0, ov, h1, in1, h2, mat, kink_mat=None, crest_mat=None):
    """Mansard roof extruded along X (open ends hidden in neighbouring blocks)."""
    ya, yb, yc = y0 - ov, y1 + ov, (y0 + y1) / 2
    prof = [(ya, z0), (yb, z0), (yb - in1, z0 + h1), (yc, z0 + h1 + h2), (ya + in1, z0 + h1)]
    prism_yz(mb, prof, x0, x1, mat)
    if kink_mat:
        for y in (ya + in1, yb - in1):
            mb.box_mm((x0, y - 0.13, z0 + h1 - 0.1), (x1, y + 0.13, z0 + h1 + 0.1), kink_mat)
    if crest_mat:
        mb.box_mm((x0, yc - 0.07, z0 + h1 + h2 - 0.05), (x1, yc + 0.07, z0 + h1 + h2 + 0.2), crest_mat)


def pavilion_roof(mb, x0, y0, x1, y1, z0, ov, h1, in1, h2, mat, kink_mat=None, crest_mat=None,
                  flat_mat=None):
    """Steep French pavilion roof: sloped frustum + hipped (or flat) top. Returns top rect & ridge."""
    b = (x0 - ov, y0 - ov, x1 + ov, y1 + ov)
    t = (b[0] + in1, b[1] + in1, b[2] - in1, b[3] - in1)
    frustum(mb, b, t, z0, z0 + h1, mat, cap_mat=flat_mat)
    ridge = None
    if not flat_mat:
        ridge = hip_top(mb, t[0], t[1], t[2], t[3], z0 + h1, h2, mat)
        if crest_mat and ridge:
            r0, r1 = ridge
            if math.dist(r0, r1) > 0.1:
                mb.beam((r0[0], r0[1], r0[2] + 0.05), (r1[0], r1[1], r1[2] + 0.05), 0.14, 0.22, crest_mat)
    if kink_mat:
        z = z0 + h1
        for (p, q) in (((t[0], t[1]), (t[2], t[1])), ((t[2], t[1]), (t[2], t[3])),
                       ((t[2], t[3]), (t[0], t[3])), ((t[0], t[3]), (t[0], t[1]))):
            mb.beam((p[0], p[1], z), (q[0], q[1], z), 0.26, 0.2, kink_mat)
    return t, ridge


def chimney(mb, x, y, z0, z1, w=1.1, d=2.2, mat=WALL, cap=TRIM):
    mb.box_mm((x - w / 2, y - d / 2, z0), (x + w / 2, y + d / 2, z1), mat, skip=("-z",))
    mb.box_mm((x - w / 2 - 0.15, y - d / 2 - 0.15, z1), (x + w / 2 + 0.15, y + d / 2 + 0.15, z1 + 0.3), cap)
    for k in (-1, 1):
        mb.cylinder((x, y + k * d * 0.22, z1 + 0.3), 0.16, 0.45, "M_DarkConcrete", seg=8)


def topiary(mb, x, y, z=0.0, h=1.8, mat=HEDGE, pot=None):
    if pot:
        mb.box((x, y, z + 0.25), (0.8, 0.8, 0.5), pot)
        z += 0.5
    mb.lathe([(0.55 * h / 1.8, 0.0), (0.42 * h / 1.8, h * 0.45), (0.2 * h / 1.8, h * 0.8), (0.02, h)],
             mat, 10, center=(x, y, z))


def hedge_box(mb, x0, y0, x1, y1, h=0.8, mat=HEDGE):
    mb.box_mm((min(x0, x1), min(y0, y1), -0.2), (max(x0, x1), max(y0, y1), h), mat, skip=("-z",))


def flower_clump(nc, x, y, z, mat, r=0.28):
    nc.sphere((x, y, z + r * 0.5), r, mat, seg=6, rings=4, scale=(1.0, 1.0, 0.7))


# ============================================================================= BOYS
B_FL = 2.0
B_BANDS = (7.0, 11.4)
B_BLOCKS = {
    "C": (-13.0, -2.0, 13.0, 30.0, 17.4),
    "WL": (-29.0, 0.0, -13.0, 28.0, 15.6),
    "WR": (13.0, 0.0, 29.0, 28.0, 15.6),
    "EL": (-41.0, -3.0, -29.0, 31.0, 16.6),
    "ER": (29.0, -3.0, 41.0, 31.0, 16.6),
}
B_GATE_Y = -84.0
B_FOUNTAIN = (0.0, -50.0)


def _boys_windows(mb, p0, p1, n=None, us=None, rows=("gf", "f1", "f2"), balconettes=False, f1_doors=False):
    with facade(mb, p0, p1) as L:
        if us is None:
            us = [L * (i + 0.5) / n for i in range(n)]
        for u in us:
            if "gf" in rows:
                window(mb, u, 2.65, 1.5, 2.55, FRAME, arch=True, keystone=GOLD, sill_mat=MARBLE)
            if "f1" in rows:
                if f1_doors:
                    window(mb, u, 7.15, 1.5, 3.05, FRAME, head="pediment", head_mat=TRIM, sill_mat=MARBLE)
                else:
                    window(mb, u, 7.65, 1.5, 2.55, FRAME, head="pediment", head_mat=TRIM, sill_mat=MARBLE)
                if balconettes:
                    mb.box((u, -0.4, 7.5), (2.3, 0.8, 0.2), MARBLE, skip=("+y",))
                    for s in (-1, 1):
                        mb.box((u + s * 0.75, -0.25, 7.2), (0.22, 0.5, 0.4), MARBLE, skip=("+y",))
                    balustrade(mb, [(u - 1.0, -0.62), (u + 1.0, -0.62)], 7.6, MARBLE, MARBLE, h=0.85,
                               spacing=0.28, post_mat=MARBLE)
            if "f2" in rows:
                window(mb, u, 12.05, 1.4, 2.1, FRAME, head="lintel", head_mat=TRIM, sill_mat=MARBLE)


def _boys_building(mb, nc, aset):
    FL = B_FL
    for k, (x0, y0, x1, y1, top) in B_BLOCKS.items():
        block_shell(mb, x0, y0, x1, y1, top, FL, B_BANDS, base_band=TRIM)

    # --------------------------------------------------------------- facades
    for sx in (-1, 1):
        def X(a, b):
            return (a, b) if sx > 0 else (-b, -a)
        # wings 13..29
        wx0, wx1 = X(13.0, 29.0)
        f = rect_faces(wx0, 0.0, wx1, 28.0)
        _boys_windows(mb, *f["front"], n=5, balconettes=True)
        _boys_windows(mb, *f["back"], n=5, balconettes=True)
        # end pavilions 29..41
        ex0, ex1 = X(29.0, 41.0)
        f = rect_faces(ex0, -3.0, ex1, 31.0)
        _boys_windows(mb, *f["front"], n=3, f1_doors=True)
        _boys_windows(mb, *f["back"], n=3)
        _boys_windows(mb, *(f["right"] if sx > 0 else f["left"]), n=9)
        # end pavilion front balcony
        bx0, bx1 = X(29.9, 40.1)
        mb.box_mm((bx0, -4.75, 6.75), (bx1, -3.0, 7.05), MARBLE)
        mb.box_mm((bx0 - 0.05, -4.85, 6.6), (bx1 + 0.05, -3.0, 6.75), TRIM)
        for k in range(4):
            cx = bx0 + 0.6 + k * (bx1 - bx0 - 1.2) / 3
            prism_yz(mb, [(-3.0, 5.6), (-3.0, 6.6), (-4.6, 6.6)], cx - 0.17, cx + 0.17, MARBLE)  # console
        balustrade(mb, [(bx0 + 0.2, -3.05), (bx0 + 0.2, -4.55), (bx1 - 0.2, -4.55), (bx1 - 0.2, -3.05)],
                   7.05, MARBLE, MARBLE, h=1.0, post_every=3.5)
        # side faces of the centre block above / beside wings are plain
    # centre block: front behind the portico (GF + F1), back three floors
    with facade(mb, (-13.0, -2.0), (13.0, -2.0)) as L:
        for x in (-9.0, -5.0, 5.0, 9.0):
            window(mb, x + 13.0, 2.65, 1.5, 2.55, FRAME, arch=True, keystone=GOLD, sill_mat=MARBLE)
            window(mb, x + 13.0, 7.65, 1.5, 2.55, FRAME, head="pediment", head_mat=TRIM, sill_mat=MARBLE)
        door(mb, 13.0, FL, 3.2, 4.2, leaf=TRIM, surround=MARBLE, handle=GOLD)
        window(mb, 13.0, 8.6, 1.6, 1.6, FRAME, head="lintel", head_mat=TRIM, sill_mat=MARBLE)
    with facade(mb, (13.0, 30.0), (-13.0, 30.0)) as L:
        for x in (-10.8, -7.2, -3.6, 3.6, 7.2, 10.8):
            u = 13.0 - x
            window(mb, u, 2.65, 1.5, 2.55, FRAME, arch=True, keystone=GOLD, sill_mat=MARBLE)
        for x in (-10.8, -7.2, -3.6, 0.0, 3.6, 7.2, 10.8):
            u = 13.0 - x
            window(mb, u, 7.65, 1.5, 2.55, FRAME, head="pediment", head_mat=TRIM, sill_mat=MARBLE)
            window(mb, u, 12.05, 1.4, 2.1, FRAME, head="lintel", head_mat=TRIM, sill_mat=MARBLE)
        door(mb, 13.0, FL, 2.6, 3.6, leaf=TRIM, surround=MARBLE, handle=GOLD)
    # attic oculi on the centre block above the wing roofs (front strip beside the pediment)
    # --------------------------------------------------------------- roofs
    for sx in (-1, 1):
        x0, x1 = (12.7, 29.3) if sx > 0 else (-29.3, -12.7)
        mansard_x(mb, x0, x1, 0.0, 28.0, 15.6, 0.55, 4.2, 1.7, 1.5, ROOF, kink_mat=TRIM, crest_mat=GOLD)
        # dormers front and back
        for xd in (16.6, 21.0, 25.4):
            xx = sx * xd
            with mb.at((xx, -0.5, 0.0)):
                dormer(mb, 1.8, 2.7, 2.6, 15.6, WALL, ROOF, FRAME, head_mat=TRIM)
            with mb.at((xx, 28.5, 0.0), rot=180):
                dormer(mb, 1.8, 2.7, 2.6, 15.6, WALL, ROOF, FRAME, head_mat=TRIM)
        for xc in (17.0, 25.0):
            chimney(mb, sx * xc, 14.0, 20.0, 24.2)
        # end pavilion roofs
        ex0, ex1 = (29.0, 41.0) if sx > 0 else (-41.0, -29.0)
        t, ridge = pavilion_roof(mb, ex0, -3.0, ex1, 31.0, 16.6, 0.55, 6.4, 2.3, 1.6, ROOF,
                                 kink_mat=TRIM, crest_mat=GOLD)
        for r in ridge:
            finial(mb, r[0], r[1], r[2] + 0.1, 1.2)
        ecx = (ex0 + ex1) / 2
        with mb.at((ecx, -3.5, 0.0)):
            dormer(mb, 2.0, 3.0, 3.0, 16.6, WALL, ROOF, FRAME, arch=True, finial_mat=GOLD, head_mat=TRIM)
        with mb.at((ecx, 31.5, 0.0), rot=180):
            dormer(mb, 2.0, 3.0, 3.0, 16.6, WALL, ROOF, FRAME, arch=True, finial_mat=GOLD, head_mat=TRIM)
        xo = ex1 + 0.5 if sx > 0 else ex0 - 0.5
        for yd in (2.0, 9.0, 16.0, 23.0):
            with mb.at((xo, yd + 2.0, 0.0), rot=90 if sx > 0 else -90):
                dormer(mb, 1.8, 2.8, 3.0, 16.6, WALL, ROOF, FRAME, head_mat=TRIM)

    # centre: pavilion roof with flat top, balustrade and the dome
    t, _ = pavilion_roof(mb, -13.0, -2.0, 13.0, 30.0, 17.4, 0.55, 4.4, 1.8, 0.0, ROOF, kink_mat=TRIM,
                         flat_mat=ROOF)
    ztop = 17.4 + 4.4
    iron_railing(mb, [(t[0] + 0.3, t[1] + 0.3), (t[2] - 0.3, t[1] + 0.3), (t[2] - 0.3, t[3] - 0.3),
                      (t[0] + 0.3, t[3] - 0.3), (t[0] + 0.3, t[1] + 0.3)], ztop, 0.9, GOLD, spacing=0.5)
    for xd in (-7.5, 7.5):
        with mb.at((xd, -2.5, 0.0)):
            dormer(mb, 2.0, 2.9, 2.6, 17.4, WALL, ROOF, FRAME, arch=True, head_mat=TRIM)
    for xd in (-7.5, 0.0, 7.5):
        with mb.at((xd, 30.5, 0.0), rot=180):
            dormer(mb, 2.0, 2.9, 2.6, 17.4, WALL, ROOF, FRAME, arch=True, head_mat=TRIM)
    _boys_dome(mb, nc, 0.0, 14.0, ztop)

    # --------------------------------------------------------------- portico
    mb.box_mm((-12.0, -10.5, -4.0), (12.0, -2.0, FL), MARBLE, skip=("-z",), mats={"+z": FLOOR})
    flight(mb, (0.0, -10.5 - 8 * 0.45, 0.0), 90, 24.0, 8, 0.25, 0.45, MARBLE)
    for sx in (-1, 1):
        # stair cheeks with urns
        xa, xb = sorted((sx * 12.0, sx * 13.6))
        mb.box_mm((xa, -14.4, -0.5), (xb, -2.0, FL + 0.55), MARBLE, skip=("-z",))
        xa, xb = sorted((sx * 11.95, sx * 13.7))
        mb.box_mm((xa, -14.5, FL + 0.55), (xb, -2.0, FL + 0.7), TRIM)
        mb.box((sx * 12.8, -13.6, FL + 1.1), (0.9, 0.9, 0.8), MARBLE)
        urn(mb, sx * 12.8, -13.6, FL + 1.5, 1.3, GOLD)
    for i in range(8):
        column(mb, -10.5 + 3.0 * i, -9.0, FL, 0.55, 9.4)
    for sx in (-1, 1):
        column(mb, sx * 10.5, -5.5, FL, 0.55, 9.4)
        mb.box_mm((sx * 10.0 - 0.55, -2.25, FL), (sx * 10.0 + 0.55, -2.0, 11.4), MARBLE)  # pilaster
    mb.box_mm((-11.9, -9.85, 11.4), (11.9, -2.0, 12.0), MARBLE)
    mb.box_mm((-12.0, -10.0, 12.0), (12.0, -2.0, 12.5), TRIM)
    mb.box_mm((-12.4, -10.4, 12.5), (12.4, -2.0, 12.8), MARBLE)
    mb.gable_roof((0.0, -6.2, 12.8), 24.8, 8.4, 3.3, ROOF, overhang=0.3, thick=0.3, gable_mat=MARBLE,
                  ridge_axis="y")
    for sx in (-1, 1):
        mb.beam((sx * 12.45, -10.5, 12.95), (0.0, -10.5, 12.8 + 3.3 - 0.1), 0.28, 0.32, TRIM)
    emblem(mb, 0.0, -10.4, 14.0, 0.95)
    for x in (-10.5, 10.5):
        finial(mb, x * 1.15, -10.2, 12.8, 0.9)
    finial(mb, 0.0, -10.2, 12.8 + 3.3 - 0.05, 1.0)
    aset.text("OBELISK BLUE", (0.0, -10.03, 12.25), 0.0, size=0.42, color=GOLD_RGB)
    # hanging portico lantern
    mb.beam((0.0, -6.0, 11.4), (0.0, -6.0, 9.9), 0.05, 0.05, GOLD)
    lantern(mb, nc, 0.0, -6.0, 9.0, 1.6, frame=GOLD, cap=GOLD)
    for x in (-6.0, 0.0, 6.0):
        aset.light((x, -6.0, 10.6), WARM, 9000, 14, night_only=True)
    aset.light((0.0, -3.0, 6.0), WARM, 6000, 10, night_only=True)
    # banners between the outer column pairs
    for sx in (-1, 1):
        bx = sx * 9.0
        nc.box((bx, -8.95, 11.28), (1.9, 0.1, 0.1), GOLD)
        prism_xz(nc, [(bx - 0.75, 6.7), (bx, 6.15), (bx + 0.75, 6.7), (bx + 0.75, 11.22), (bx - 0.75, 11.22)],
                 -8.98, -8.92, TRIM)
        for z in (10.85, 7.15):
            nc.box((bx, -8.995, z), (1.5, 0.02, 0.1), GOLD)
        with nc.at((bx, -9.0, 9.4), rot_x=90):
            nc.cylinder((0, 0, 0), 0.42, 0.04, GOLD, seg=14)

    # --------------------------------------------------------------- back terrace
    mb.box_mm((-10.0, 30.0, -4.0), (10.0, 37.0, FL), MARBLE, skip=("-z",), mats={"+z": FLOOR})
    flight(mb, (0.0, 37.0 + 8 * 0.45, 0.0), -90, 8.0, 8, 0.25, 0.45, MARBLE)
    balustrade(mb, [(-4.2, 36.8), (-9.8, 36.8), (-9.8, 30.2)], FL, MARBLE, MARBLE, post_every=3.0)
    balustrade(mb, [(9.8, 30.2), (9.8, 36.8), (4.2, 36.8)], FL, MARBLE, MARBLE, post_every=3.0)
    for sx in (-1, 1):
        urn(mb, sx * 4.2, 36.8, FL + 1.1, 0.9, MARBLE)
    aset.light((0.0, 33.0, 6.0), WARM, 5000, 12, night_only=True)



def _boys_dome(mb, nc, cx, cy, z0):
    R = 5.6
    mb.lathe([(R + 0.6, 0.0), (R + 0.6, 0.5)], MARBLE, 32, cap_top=True, cap_bottom=False, center=(cx, cy, z0))
    mb.lathe([(R, 0.5), (R, 4.0)], WALL, 32, cap_top=False, cap_bottom=False, center=(cx, cy, z0))
    lathe_crisp(mb, [(R + 0.15, 1.2), (R + 0.15, 1.45)], TRIM, 32, center=(cx, cy, z0), cap_bottom=True,
                cap_top=True)
    lathe_crisp(mb, [(R + 0.05, 3.7), (R + 0.3, 4.0), (R + 0.55, 4.25), (R + 0.55, 4.6)], TRIM, 32,
                center=(cx, cy, z0), cap_top=True, cap_bottom=True)
    # pilasters + windows on the drum
    for i in range(12):
        a = TAU * (i + 0.5) / 12
        px, py = cx + math.cos(a) * R, cy + math.sin(a) * R
        with mb.at((px, py, z0), rot=math.degrees(a) + 90):
            mb.box((0.0, -0.08, 2.4), (0.5, 0.3, 3.3), MARBLE, skip=("+y",))
        a2 = TAU * i / 12
        px, py = cx + math.cos(a2) * (R + 0.02), cy + math.sin(a2) * (R + 0.02)
        with mb.at((px, py, z0), rot=math.degrees(a2) + 90):
            window(mb, 0.0, 1.75, 0.9, 1.0, FRAME, arch=True, mullion=False, fw=0.1, seg=6)
    zd = z0 + 4.6
    rings = 9
    hs = 1.12
    prof = [(R + 0.25) * math.cos(math.pi / 2 * i / rings) for i in range(rings + 1)]
    prof = [(max(r, 0.9), zd + (R + 0.25) * hs * math.sin(math.pi / 2 * i / rings)) for i, r in enumerate(prof)]
    prof = [p for p in prof if p[0] > 0.9] + [(0.9, prof[-1][1])]
    mb.lathe(prof, ROOF, 32, cap_top=True, cap_bottom=False, center=(cx, cy, 0.0))
    # gilded ribs
    for k in range(8):
        a = TAU * k / 8
        for i in range(len(prof) - 2):
            r0, z0_ = prof[i]
            r1, z1_ = prof[i + 1]
            mb.beam((cx + math.cos(a) * (r0 + 0.04), cy + math.sin(a) * (r0 + 0.04), z0_),
                    (cx + math.cos(a) * (r1 + 0.04), cy + math.sin(a) * (r1 + 0.04), z1_), 0.18, 0.12, GOLD)
    zt = prof[-1][1] - 0.4
    # lantern
    mb.lathe([(1.2, 0.0), (1.2, 1.9)], WALL, 16, cap_top=False, cap_bottom=False, center=(cx, cy, zt))
    for i in range(8):
        a = TAU * i / 8
        with mb.at((cx + math.cos(a) * 1.21, cy + math.sin(a) * 1.21, zt), rot=math.degrees(a) + 90):
            mb.box((0.0, -0.06, 0.95), (0.18, 0.12, 1.9), MARBLE, skip=("+y",))
    lathe_crisp(mb, [(1.45, 1.9), (1.45, 2.15)], TRIM, 16, center=(cx, cy, zt), cap_top=True, cap_bottom=True)
    mb.lathe([(1.35, 2.15), (1.2, 2.6), (0.85, 3.0), (0.3, 3.3)], GOLD, 16, cap_top=True, cap_bottom=False,
             center=(cx, cy, zt))
    finial(mb, cx, cy, zt + 3.25, 1.4)
    for i in range(4):
        a = TAU * (i + 0.5) / 4
        nc.box((cx + math.cos(a) * 1.17, cy + math.sin(a) * 1.17, zt + 0.95), (0.5, 0.5, 1.3), GLOW)


def _boys_fountain(mb, nc, aset, cx, cy):
    R = 8.6
    # basin wall (solid on the left of the profile)
    lathe_crisp(mb, [(R + 0.4, -0.3), (R + 0.4, 0.5), (R + 0.6, 0.6), (R + 0.6, 0.8), (R - 0.35, 0.8),
                     (R - 0.35, 0.1)], MARBLE, 48, center=(cx, cy, 0.0))
    disc(mb, cx, cy, 0.12, R - 0.35, TRIM, seg=48)                      # blue tiled floor
    nc.poly([(x, y, 0.62) for x, y in circle(48, R - 0.34, cx, cy)], WATER)
    # tier 1
    lathe_crisp(mb, [(1.7, 0.12), (1.7, 0.7), (1.3, 0.85), (0.8, 1.0), (0.65, 1.7), (0.75, 1.95),
                     (1.4, 2.15), (3.3, 2.55), (3.5, 2.65), (3.5, 2.9), (3.2, 2.9), (3.15, 2.72)], MARBLE, 32,
                center=(cx, cy, 0.0), cap_top=True)
    nc.poly([(x, y, 2.82) for x, y in circle(32, 3.17, cx, cy)], WATER)
    for i in range(16):
        a = TAU * (i + 0.5) / 16
        ca, sa = math.cos(a), math.sin(a)
        mb.sphere((cx + ca * (R - 0.1), cy + sa * (R - 0.1), 0.86), 0.13, GOLD, seg=6, rings=4)
        prev = None
        for k in range(9):
            t = k / 8
            r = (R - 0.15) + (4.0 - (R - 0.15)) * t
            z = 0.9 + 2.3 * 4 * t * (1 - t) - 0.3 * t
            p = (cx + ca * r, cy + sa * r, z)
            if prev:
                nc.beam(prev, p, 0.09, 0.09, FALLS)
            prev = p
    # tier 2
    lathe_crisp(mb, [(0.55, 2.72), (0.45, 3.6), (0.55, 3.85), (1.0, 4.0), (1.9, 4.35), (2.05, 4.5),
                     (2.05, 4.68), (1.85, 4.68), (1.8, 4.52)], MARBLE, 24, center=(cx, cy, 0.0), cap_top=True)
    nc.poly([(x, y, 4.62) for x, y in circle(24, 1.82, cx, cy)], WATER)
    nc.lathe([(2.1, 2.84), (2.1, 4.64)], FALLS, 24, cap_top=False, cap_bottom=False, center=(cx, cy, 0.0))
    # little white obelisk with a gold pyramidion on top
    frustum(mb, (cx - 0.45, cy - 0.45, cx + 0.45, cy + 0.45), (cx - 0.45, cy - 0.45, cx + 0.45, cy + 0.45),
            4.52, 4.9, MARBLE, bottom=False, cap_mat=MARBLE)
    frustum(mb, (cx - 0.3, cy - 0.3, cx + 0.3, cy + 0.3), (cx - 0.18, cy - 0.18, cx + 0.18, cy + 0.18),
            4.9, 7.0, WALL, bottom=False)
    mb.pyramid((cx, cy, 7.0), 0.36, 0.36, 0.45, GOLD, base=False)
    # four gilded spouts on tier 1 pedestal
    for i in range(4):
        a = TAU * (i + 0.5) / 4
        mb.sphere((cx + math.cos(a) * 1.7, cy + math.sin(a) * 1.7, 0.95), 0.22, GOLD, seg=8, rings=6)
    aset.emitter("mist", (cx, cy, 3.0), 1.6)
    aset.emitter("mist", (cx, cy, 0.9), 2.2)
    aset.audio("A_Waterfall", (cx, cy, 1.5), radius=24.0, volume=0.6)
    aset.light((cx, cy, 1.2), (0.6, 0.8, 1.0), 4000, 14, night_only=True)


def _parterre(mb, aset, x0, y0, x1, y1, rng_flip=False, flowers=("SM_FlowerBush_Blue", "SM_FlowerBush_White")):
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    w, d = x1 - x0, y1 - y0
    t, hh, gap = 0.7, 0.8, 2.6
    # border with entry gaps in the middle of every side
    hedge_box(mb, x0, y0, cx - gap / 2, y0 + t, hh)
    hedge_box(mb, cx + gap / 2, y0, x1, y0 + t, hh)
    hedge_box(mb, x0, y1 - t, cx - gap / 2, y1, hh)
    hedge_box(mb, cx + gap / 2, y1 - t, x1, y1, hh)
    hedge_box(mb, x0, y0 + t, x0 + t, cy - gap / 2, hh)
    hedge_box(mb, x0, cy + gap / 2, x0 + t, y1 - t, hh)
    hedge_box(mb, x1 - t, y0 + t, x1, cy - gap / 2, hh)
    hedge_box(mb, x1 - t, cy + gap / 2, x1, y1 - t, hh)
    # corner topiaries
    for (x, y) in ((x0 + t / 2, y0 + t / 2), (x1 - t / 2, y0 + t / 2), (x1 - t / 2, y1 - t / 2), (x0 + t / 2, y1 - t / 2)):
        topiary(mb, x, y, hh, 1.6)
    # inner diamond (low hedge)
    ix, iy = w / 2 - 2.6, d / 2 - 2.6
    pts = [(cx, cy - iy), (cx + ix, cy), (cx, cy + iy), (cx - ix, cy)]
    for i in range(4):
        p, q = pts[i], pts[(i + 1) % 4]
        # leave a gap at every diamond corner
        f0, f1 = 0.14, 0.86
        a = (p[0] + (q[0] - p[0]) * f0, p[1] + (q[1] - p[1]) * f0, 0.25)
        b = (p[0] + (q[0] - p[0]) * f1, p[1] + (q[1] - p[1]) * f1, 0.25)
        mb.beam(a, b, 0.6, 0.9, HEDGE)
    # central round bed with curb
    lathe_crisp(mb, [(2.4, -0.2), (2.4, 0.35), (2.1, 0.35), (2.1, 0.25)], MARBLE, 24, center=(cx, cy, 0.0))
    disc(mb, cx, cy, 0.25, 2.1, SOIL, seg=24)
    aset.prop("SM_BroadTree_C", (cx, cy, 0.25), 0.0, 1.0)
    for i in range(6):
        a = TAU * i / 6
        aset.prop(flowers[i % 2], (cx + math.cos(a) * 1.5, cy + math.sin(a) * 1.5, 0.25), math.degrees(a), 0.7)
    # flower bushes in the four triangles
    for (sx, sy) in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        for k, (u, v) in enumerate(((0.36, 0.22), (0.22, 0.36), (0.42, 0.4))):
            aset.prop(flowers[k % 2], (cx + sx * u * w, cy + sy * v * d, 0.0), 0.0, 0.9)


def _boys_courtyard(mb, nc, aset):
    fx, fy = B_FOUNTAIN
    gy = B_GATE_Y
    # paving: forecourt, central axis, fountain ring, cross axis
    slab(mb, -22.0, -26.0, 22.0, -13.9)
    slab(mb, -5.0, gy + 0.3, 5.0, fy - 14.6)
    slab(mb, -5.0, fy + 14.6, 5.0, -26.0)
    ring_slab(mb, fx, fy, 9.15, 15.0, top=P_RING, seg=48)
    slab(mb, -48.0, fy - 3.0, -14.6, fy + 3.0, top=P_LOW)
    slab(mb, 14.6, fy - 3.0, 48.0, fy + 3.0, top=P_LOW)
    # paths along the wings to the side lawns
    slab(mb, -44.0, -12.0, -22.0, -8.0)
    slab(mb, 22.0, -12.0, 44.0, -8.0)
    slab(mb, -26.0, -26.0, -22.0, -12.0)
    slab(mb, 22.0, -26.0, 26.0, -12.0)
    _boys_fountain(mb, nc, aset, fx, fy)
    for sx in (-1, 1):  # foundation hedges along the wing fronts
        hedge_box(mb, sx * 14.0, -2.6, sx * 28.0, -1.2, 1.0)
    # parterres (four quadrants)
    _parterre(mb, aset, 17.0, -45.0, 45.0, -29.0)
    _parterre(mb, aset, -45.0, -45.0, -17.0, -29.0)
    _parterre(mb, aset, 17.0, -73.0, 43.0, -55.0, flowers=("SM_FlowerBush_White", "SM_FlowerBush_Blue"))
    _parterre(mb, aset, -43.0, -73.0, -17.0, -55.0, flowers=("SM_FlowerBush_White", "SM_FlowerBush_Blue"))
    # topiary cones along the central axis
    for y in (-30.0, -76.0):
        for sx in (-1, 1):
            topiary(mb, sx * 6.4, y, 0.0, 2.2, pot=MARBLE)
    # lawn edging hedges between axis and fountain ring
    for sx in (-1, 1):
        hedge_box(mb, sx * 5.6, -80.5, sx * 6.3, -66.0, 0.6)
        hedge_box(mb, sx * 5.6, -33.5, sx * 6.3, -27.0, 0.6)
    # forecourt urns
    for sx in (-1, 1):
        mb.box((sx * 20.8, -25.0, 0.6), (1.0, 1.0, 1.2), MARBLE)
        mb.box((sx * 20.8, -25.0, 1.25), (1.2, 1.2, 0.1), TRIM)
        urn(mb, sx * 20.8, -25.0, 1.3, 1.1, MARBLE)
        aset.prop("SM_FlowerBush_Blue", (sx * 20.8, -25.0, 2.35), 0.0, 0.6)

    # ---- props: lamps, benches, flags, trees, flowers
    lamps = [(sx * 6.4, y) for sx in (-1, 1) for y in (-80.0, -70.0, -36.0)]
    lamps += [(fx + math.cos(a) * 15.6, fy + math.sin(a) * 15.6) for a in (math.radians(d) for d in (45, 135, 225, 315))]
    lamps += [(sx * 21.0, -14.6) for sx in (-1, 1)]
    lamps += [(sx * 47.0, fy - 3.6) for sx in (-1, 1)]
    lamps += [(sx * 33.0, -10.0 - 2.6) for sx in (-1, 1)]
    for (x, y) in lamps:
        aset.prop("SM_LampPost", (x, y, 0.05), 0.0)
    for ang in (30, 60, 120, 150, 210, 240, 300, 330):
        a = math.radians(ang)
        bx, by = fx + math.cos(a) * 13.9, fy + math.sin(a) * 13.9
        aset.prop("SM_Bench", (bx, by, 0.05), face_yaw(bx, by, fx, fy))
    for sx in (-1, 1):
        aset.prop("SM_Flagpole_Blue", (sx * 16.5, -16.0, 0.05), 0.0)
        for k in range(5):
            aset.prop("SM_FlowerBush_Blue", (sx * (15.0 + k * 3.0), -3.4, 0.0), 0.0, 0.9)
        for k in range(4):
            aset.prop("SM_FlowerBush_White", (sx * (31.0 + k * 2.6), -5.0, 0.0), 0.0, 0.9)
    trees = [(sx * 52.0, -20.0) for sx in (-1, 1)] + [(sx * 55.0, -36.0) for sx in (-1, 1)]
    trees += [(sx * 12.0, -80.0) for sx in (-1, 1)] + [(sx * 50.0, -60.0) for sx in (-1, 1)]
    for i, (x, y) in enumerate(trees):
        aset.prop("SM_BroadTree_C", (x, y, 0.0), (i * 47) % 360, 1.1 + 0.1 * (i % 3))
    big = [(sx * 62.0, 0.0) for sx in (-1, 1)] + [(sx * 66.0, 22.0) for sx in (-1, 1)]
    big += [(sx * 58.0, 46.0) for sx in (-1, 1)] + [(sx * 30.0, 62.0) for sx in (-1, 1)]
    big += [(sx * 12.0, 72.0) for sx in (-1, 1)] + [(sx * 48.0, 66.0) for sx in (-1, 1)]
    for i, (x, y) in enumerate(big):
        aset.prop("SM_BroadTree_A" if i % 3 else "SM_BroadTree_B", (x, y, 0.0), (i * 71) % 360, 0.9 + 0.08 * (i % 4))

    # back garden: lawn walks, benches, lamps
    slab(mb, -2.0, 40.5, 2.0, 60.0)
    mb.prism(circle(32, 5.0, 0.0, 64.0), -0.3, P_RING, PAVE, cap_bottom=False)
    lathe_crisp(mb, [(2.2, -0.2), (2.2, 0.4), (1.9, 0.4), (1.9, 0.3)], MARBLE, 24, center=(0.0, 64.0, 0.0))
    disc(mb, 0.0, 64.0, 0.3, 1.9, SOIL, seg=24)
    aset.prop("SM_BroadTree_C", (0.0, 64.0, 0.3), 0.0, 1.2)
    for ang in (0, 90, 180):
        a = math.radians(ang)
        bx, by = math.cos(a) * 4.0, 64.0 + math.sin(a) * 4.0
        aset.prop("SM_Bench", (bx, by, 0.05), face_yaw(bx, by, 0.0, 64.0) + 180.0)
    for sx in (-1, 1):
        aset.prop("SM_LampPost", (sx * 3.0, 50.0, 0.05), 0.0)
        for k in range(4):
            aset.prop("SM_FlowerBush_Blue", (sx * (11.5 + k * 2.4), 34.0, 0.0), 0.0, 0.9)

    # NPCs
    for (p, yaw) in (((3.0, -19.0), 180.0), ((11.0, -45.0), 120.0), ((-12.0, -56.0), -60.0),
                     ((-30.0, -50.0), 90.0), ((26.0, -50.0), -90.0), ((-4.0, -6.5), 0.0),
                     ((4.0, -78.0), 0.0), ((0.0, 52.0), 180.0), ((-34.0, -10.0), -90.0)):
        z = B_FL if p[1] > -10.6 and abs(p[0]) < 12 and p[1] < -2 else 0.05
        aset.npc((p[0], p[1], z), yaw, dorm="obelisk", wander=6.0)


def _boys_gate(mb, nc, aset):
    gy = B_GATE_Y
    # main pillars
    for sx in (-1, 1):
        x = sx * 5.0
        mb.box_mm((x - 1.0, gy - 1.0, -1.0), (x + 1.0, gy + 1.0, 0.5), MARBLE, skip=("-z",))
        mb.box_mm((x - 0.8, gy - 0.8, 0.5), (x + 0.8, gy + 0.8, 4.4), MARBLE, skip=("-z",))
        mb.box_mm((x - 0.86, gy - 0.86, 3.6), (x + 0.86, gy + 0.86, 3.95), TRIM)
        mb.box_mm((x - 0.95, gy - 0.95, 4.4), (x + 0.95, gy + 0.95, 4.75), MARBLE)
        mb.box_mm((x - 0.7, gy - 0.7, 4.75), (x + 0.7, gy + 0.7, 4.95), TRIM)
        # recessed blue panels on the pillar front/back
        for s in (-1, 1):
            mb.box((x, gy + s * 0.81, 2.1), (1.0, 0.04, 2.4), TRIM)
        ball_finial(mb, x, gy, 4.95, 0.42)
        # lantern on a bracket in front of the pillar
        mb.box((x, gy - 0.98, 3.0), (0.14, 0.4, 0.14), IRON)
        lantern(mb, nc, x, gy - 1.2, 2.55, 1.1)
        aset.light((x, gy - 1.2, 2.9), WARM, 4000, 10, night_only=True)
    # iron gate leaves, swung open inwards
    leaf_w, leaf_h = 4.15, 2.9
    for sx in (-1, 1):
        hinge = (sx * 4.2, gy + 0.1, 0.0)
        rot = 95.0 if sx < 0 else 85.0
        with mb.at(hinge, rot=rot):
            n = 20
            for k in range(n + 1):
                u = leaf_w * k / n
                t = u / leaf_w
                hh = leaf_h + 0.75 * t * t
                mb.box((u, 0.0, 0.1 + hh / 2), (0.045, 0.045, hh), IRON)
                mb.pyramid((u, 0.0, 0.1 + hh), 0.1, 0.1, 0.2, GOLD, base=False)
            for z in (0.18, 1.0, 2.6):
                mb.box((leaf_w / 2, 0.0, z), (leaf_w, 0.07, 0.08), IRON)
            for k in range(n):
                u0, u1 = leaf_w * k / n, leaf_w * (k + 1) / n
                z0 = 0.1 + leaf_h + 0.75 * (u0 / leaf_w) ** 2 - 0.25
                z1 = 0.1 + leaf_h + 0.75 * (u1 / leaf_w) ** 2 - 0.25
                mb.beam((u0, 0.0, z0), (u1, 0.0, z1), 0.07, 0.07, IRON)
            with mb.at((leaf_w / 2, 0.0, 1.8), rot_x=90):
                mb.torus((0, 0, 0), 0.55, 0.05, GOLD, seg=16, tube_seg=5)
                mb.torus((0, 0, 0), 0.25, 0.04, GOLD, seg=12, tube_seg=5)
            mb.box((0.0, 0.0, 1.6), (0.12, 0.12, 3.2), IRON)
    # overhead iron arch with the name board
    segmental_arc(mb, 4.2, 4.3, 1.3, 0.16, gy - 0.07, gy + 0.07, IRON, seg=12)
    segmental_arc(mb, 4.2, 4.9, 2.0, 0.16, gy - 0.07, gy + 0.07, IRON, seg=12)
    for k in range(-6, 7):
        x = k * 0.6
        # bars between the two arcs
        R1 = (4.2 ** 2 + 1.3 ** 2) / 2.6
        z1 = 4.3 + 1.3 - R1 + math.sqrt(max(R1 * R1 - x * x, 0))
        R2 = (4.2 ** 2 + 2.0 ** 2) / 4.0
        z2 = 4.9 + 2.0 - R2 + math.sqrt(max(R2 * R2 - x * x, 0))
        mb.box((x, gy, (z1 + z2) / 2), (0.05, 0.05, z2 - z1), IRON)
    mb.sign_board((0.0, gy, 6.75), 5.8, 0.72, TRIM, GOLD, thick=0.16, posts=False)
    emblem(mb, 0.0, gy - 0.05, 7.75, 0.4)
    aset.text("OBELISK BLUE DORM", (0.0, gy - 0.08 - 0.025, 6.75), 0.0, size=0.45, color=GOLD_RGB)
    aset.text("OBELISK BLUE DORM", (0.0, gy + 0.08 + 0.025, 6.75), 180.0, size=0.45, color=GOLD_RGB)

    # low wall + pillars, iron fence segments as props
    runs = [(5.8, gy), (34.0, gy), (56.0, -70.0), (66.0, -46.0)]
    for sx in (-1, 1):
        pts = [(sx * x, y) for x, y in runs]
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            L = math.hypot(x1 - x0, y1 - y0)
            mb.beam((x0, y0, 0.05), (x1, y1, 0.05), 0.6, 1.1, MARBLE)
            mb.beam((x0, y0, 0.66), (x1, y1, 0.66), 0.75, 0.12, TRIM)
            n = max(1, round(L / 4.8))
            yaw = math.degrees(math.atan2(y1 - y0, x1 - x0))
            for k in range(n + 1):
                t = k / n
                px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                if k > 0:   # the start of every run is the previous run's end (or the gate pillar)
                    mb.box((px, py, 1.3), (0.8, 0.8, 2.6), MARBLE, skip=("-z",))
                    mb.box((px, py, 2.65), (0.95, 0.95, 0.12), TRIM)
                    ball_finial(mb, px, py, 2.71, 0.2)
                if k < n:
                    seg_len = L / n
                    mx, my = x0 + (x1 - x0) * (k + 0.5) / n, y0 + (y1 - y0) * (k + 0.5) / n
                    aset.prop("SM_Fence_Iron", (mx, my, 0.72), yaw if sx > 0 else yaw + 180.0,
                              round((seg_len - 0.8) / 4.0, 3))
    # monument sign outside the gate (right of the path)
    sx_, sy_ = 10.5, -89.0
    mb.box_mm((sx_ - 2.2, sy_ - 0.6, -0.5), (sx_ + 2.2, sy_ + 0.6, 0.35), MARBLE, skip=("-z",))
    mb.box_mm((sx_ - 1.9, sy_ - 0.35, 0.35), (sx_ + 1.9, sy_ + 0.35, 1.75), MARBLE)
    mb.box_mm((sx_ - 2.0, sy_ - 0.45, 1.75), (sx_ + 2.0, sy_ + 0.45, 1.9), TRIM)
    mb.box_mm((sx_ - 1.6, sy_ - 0.4, 0.55), (sx_ + 1.6, sy_ - 0.35, 1.55), TRIM)
    emblem(mb, sx_, sy_ - 0.05, 2.35, 0.3)
    aset.text("OBELISK BLUE DORM", (sx_, sy_ - 0.4 - 0.025, 1.12), 0.0, size=0.28, color=GOLD_RGB)
    aset.interact("sign", (sx_, sy_ - 1.2, 1.0), 0.0, title="Obelisk Blue Dorm",
                  text="Obelisk Blue Dorm - reserved for the academy's elite. Marble halls, a five-star "
                       "kitchen and a view worthy of a king.")


def build_boys():
    aset = AssetSet("obelisk_boys")
    main = aset.mesh("ObeliskBoys_Main")
    yard = aset.mesh("ObeliskBoys_Courtyard")
    gate = aset.mesh("ObeliskBoys_Gate")
    nc = aset.mesh("ObeliskBoys_NoCol")
    _boys_building(main, nc, aset)
    _boys_courtyard(yard, nc, aset)
    _boys_gate(gate, nc, aset)
    return aset


# ============================================================================= GIRLS
G_FL = 1.2
G_BANDS = (5.4, 9.4)
G_TOP = 13.6
G_MAIN = (-22.0, 4.0, 22.0, 26.0)
G_PAV = (-7.0, 1.0, 7.0, 27.0, 14.4)
G_TURRETS = [(-22.0, 4.0), (22.0, 4.0), (-22.0, 26.0), (22.0, 26.0)]
G_TURRET_R = 3.4
G_GAZEBO = (0.0, -44.0)
# the academy path arrives from local (-58, -77) heading to (-30, -42): rose arch straddles it
G_ARCH = (-38.4, -52.5)
G_ARCH_YAW = -38.5
ROCK = "M_Rock"


def _g_window(mb, u, row, nc=None, w=None, flowers=None):
    """Girls' dorm window rows: gf (tall), f1 (shutters + flower box), f2 (arched)."""
    if row == "gf":
        window(mb, u, 1.85, w or 1.4, 2.75, GTRIM, head="segment", head_mat=GTRIM, sill_mat=MARBLE)
    elif row == "f1":
        window(mb, u, 5.95, w or 1.3, 2.55, GTRIM, head="lintel", head_mat=GTRIM, sill_mat=MARBLE,
               shutter_mat=GROOF)
        if flowers:
            ww = (w or 1.3) + 0.6
            mb.box((u, -0.25, 5.7), (ww, 0.46, 0.38), GTRIM, skip=("+y",))
            mb.box((u, -0.49, 5.86), (ww + 0.04, 0.04, 0.06), WALL, skip=("+y",))
            with follow(mb, nc):
                for k in range(6):
                    mat = "M_LeavesBush" if k % 3 == 1 else flowers[(k // 3) % len(flowers)]
                    flower_clump(nc, u - ww / 2 + ww * (k + 0.5) / 6, -0.28, 5.84, mat, 0.27)
    elif row == "f2":
        window(mb, u, 10.0, w or 1.2, 1.75, GTRIM, arch=True, keystone=GTRIM, sill_mat=MARBLE)


def _turret(mb, cx, cy, r, angles, top=15.2, roof_h=8.6):
    mb.lathe([(r, -4.0), (r, top)], WALL, 28, cap_top=False, cap_bottom=False, center=(cx, cy, 0.0))
    lathe_crisp(mb, [(r + 0.2, -4.0), (r + 0.2, G_FL + 0.3), (r + 0.05, G_FL + 0.45)], MARBLE, 28,
                center=(cx, cy, 0.0))
    for z in G_BANDS:
        lathe_crisp(mb, [(r + 0.1, z - 0.14), (r + 0.1, z + 0.14)], GTRIM, 28, center=(cx, cy, 0.0),
                    cap_top=True, cap_bottom=True)
    lathe_crisp(mb, [(r + 0.05, top - 0.9), (r + 0.2, top - 0.6), (r + 0.45, top - 0.35), (r + 0.45, top)],
                GTRIM, 28, center=(cx, cy, 0.0), cap_bottom=True)
    mb.lathe([(r + 0.75, top - 0.05), (r + 0.5, top + 0.4), (r * 0.62, top + roof_h * 0.45),
              (r * 0.2, top + roof_h * 0.88), (0.08, top + roof_h)], GROOF, 28, cap_bottom=True,
             center=(cx, cy, 0.0))
    finial(mb, cx, cy, top + roof_h - 0.15, 1.3)
    for a_deg in angles:
        a = math.radians(a_deg)
        with mb.at((cx + math.cos(a) * r, cy + math.sin(a) * r, 0.0), rot=a_deg + 90):
            window(mb, 0.0, 1.85, 1.0, 2.6, GTRIM, arch=True, keystone=GTRIM, sill_mat=MARBLE, seg=6)
            window(mb, 0.0, 6.0, 1.0, 2.3, GTRIM, arch=True, sill_mat=MARBLE, seg=6)
            window(mb, 0.0, 10.0, 1.0, 2.0, GTRIM, arch=True, sill_mat=MARBLE, seg=6)
            window(mb, 0.0, 13.05, 0.8, 0.45, GTRIM, arch=True, sill_mat=MARBLE, seg=6, mullion=False)


def _bay_canted(mb, xc, yw, depth=1.4, wb=4.6, wf=2.8, z0=-1.0, z1=9.4):
    """Two-storey canted bay window on the front wall plane y=yw (projects to -y)."""
    yf = yw - depth
    fp = [(xc - wf / 2, yf), (xc + wf / 2, yf), (xc + wb / 2, yw), (xc - wb / 2, yw)]
    mb.prism(fp, z0, z1, WALL, cap_top=False, cap_bottom=False)
    e = [(xc - wf / 2 - 0.08, yf - 0.1), (xc + wf / 2 + 0.08, yf - 0.1), (xc + wb / 2 + 0.14, yw),
         (xc - wb / 2 - 0.14, yw)]
    mb.prism(e, G_BANDS[0] - 0.16, G_BANDS[0] + 0.16, GTRIM)
    e = [(xc - wf / 2 - 0.2, yf - 0.25), (xc + wf / 2 + 0.2, yf - 0.25), (xc + wb / 2 + 0.35, yw),
         (xc - wb / 2 - 0.35, yw)]
    mb.prism(e, z1 - 0.35, z1, GTRIM, cap_top=False)
    F0, F1 = (e[0][0], e[0][1], z1), (e[1][0], e[1][1], z1)
    B1, B0 = (e[2][0], e[2][1], z1), (e[3][0], e[3][1], z1)
    T0, T1 = (xc - wf / 2 - 0.2, yw, z1 + 1.2), (xc + wf / 2 + 0.2, yw, z1 + 1.2)
    mb.quad(F0, F1, T1, T0, GROOF)
    mb.poly([F1, B1, T1], GROOF)
    mb.poly([B0, F0, T0], GROOF)
    for (p0, p1, w) in (((xc - wf / 2, yf), (xc + wf / 2, yf), 1.6),
                        ((xc + wf / 2, yf), (xc + wb / 2, yw), 0.75),
                        ((xc - wb / 2, yw), (xc - wf / 2, yf), 0.75)):
        with facade(mb, p0, p1) as L:
            window(mb, L / 2, 1.85, w, 2.8, GTRIM, sill_mat=MARBLE, head="lintel", head_mat=GTRIM,
                   mullion=w > 1.0)
            window(mb, L / 2, 6.0, w, 2.5, GTRIM, sill_mat=MARBLE, head="lintel", head_mat=GTRIM,
                   mullion=w > 1.0)


def _girls_building(mb, nc, aset):
    FL = G_FL
    x0, y0, x1, y1 = G_MAIN
    block_shell(mb, x0, y0, x1, y1, G_TOP, FL, G_BANDS, band_mat=GTRIM, cornice=(MARBLE, GTRIM),
                pilasters=False)
    px0, py0, px1, py1, ptop = G_PAV
    block_shell(mb, px0, py0, px1, py1, ptop, FL, G_BANDS, band_mat=GTRIM, cornice=(MARBLE, GTRIM))
    # ------------------------------------------------------------ roofs
    rh = 6.8
    mb.hip_roof((0.0, (y0 + y1) / 2, G_TOP), x1 - x0, y1 - y0, rh, GROOF, overhang=0.8, thick=0.3)
    mb.box_mm((-11.0, 14.93, G_TOP + rh - 0.02), (11.0, 15.07, G_TOP + rh + 0.18), GOLD)
    gh = 6.0
    mb.gable_roof((0.0, (py0 + py1) / 2, ptop), px1 - px0, py1 - py0, gh, GROOF, overhang=0.6, thick=0.3,
                  gable_mat=WALL, ridge_axis="y")
    for (yw, rot) in ((py0, 0.0), (py1, 180.0)):
        with mb.at((0.0, yw, 0.0), rot=rot):
            for sx in (-1, 1):
                mb.beam((sx * 7.1, -0.12, ptop - 0.05), (0.0, -0.12, ptop + gh - 0.38), 0.24, 0.3, GTRIM)
            pts = [(math.cos(TAU * i / 16) * 0.9, -0.03, 17.2 + math.sin(TAU * i / 16) * 0.9) for i in range(16)]
            mb.poly(pts, GLASS)
            arc_band(mb, 0.0, 17.2, 0.9, 1.15, 0.0, TAU, 16, -0.14, 0.0, GTRIM)
            mb.box((0.0, -0.06, 17.2), (0.06, 0.05, 1.8), GTRIM, skip=("+y",))
            mb.box((0.0, -0.06, 17.2), (1.8, 0.05, 0.06), GTRIM, skip=("+y",))
            finial(mb, 0.0, -0.55, ptop + gh - 0.2, 0.9)
    # turrets
    for (tx, ty) in G_TURRETS:
        if ty < 10:
            angs = (-90.0, -45.0, 0.0) if tx > 0 else (-90.0, -135.0, 180.0)
        else:
            angs = (90.0, 45.0, 0.0) if tx > 0 else (90.0, 135.0, 180.0)
        _turret(mb, tx, ty, G_TURRET_R, angs)
    # dormers + chimneys
    for xd in (-12.8, 12.8):
        with mb.at((xd, y0 - 0.1, 0.0)):
            dormer(mb, 1.8, 2.5, 5.8, G_TOP, WALL, GROOF, GTRIM, arch=True, finial_mat=GOLD, head_mat=MARBLE)
        with mb.at((xd, y1 + 0.1, 0.0), rot=180):
            dormer(mb, 1.8, 2.5, 5.8, G_TOP, WALL, GROOF, GTRIM, arch=True, finial_mat=GOLD, head_mat=MARBLE)
    for xc in (-15.0, 15.0):
        chimney(mb, xc, 19.0, 15.5, 21.6, 1.0, 1.8, WALL, GTRIM)

    # ------------------------------------------------------------ facades
    fl = ("M_FlowerRed", "M_FlowerWhite")
    fl2 = ("M_FlowerWhite", "M_FlowerRed")
    with facade(mb, (x0, y0), (x1, y0)):
        for x in (-16.9, -8.6, 8.6, 16.9):
            for row in ("gf", "f1", "f2"):
                _g_window(mb, x - x0, row, nc, flowers=fl)
        for x in (-12.8, 12.8):
            _g_window(mb, x - x0, "f2")
    for x in (-12.8, 12.8):
        _bay_canted(mb, x, y0)
    with facade(mb, (px0, py0), (px1, py0)):
        for x in (-4.6, 4.6):
            for row in ("gf", "f1", "f2"):
                _g_window(mb, x - px0, row, nc, flowers=fl2)
        door(mb, 7.0, FL, 2.2, 2.9, leaf=WALL, surround=GTRIM, handle=GOLD, panel_mat=GTRIM, fan=False)
        window(mb, 7.0, 5.62, 1.5, 2.9, GTRIM, head="pediment", head_mat=GTRIM, sill_mat=MARBLE)
        window(mb, 7.0, 10.0, 1.4, 1.9, GTRIM, arch=True, keystone=GOLD, sill_mat=MARBLE)
    with facade(mb, (x1, y1), (x0, y1)):
        for x in (-17.0, -12.9, -8.9, 8.9, 12.9, 17.0):
            for row in ("gf", "f1", "f2"):
                _g_window(mb, x1 - x, row, nc, flowers=fl)
    with facade(mb, (px1, py1), (px0, py1)):
        for x in (-4.4, 0.0, 4.4):
            for row in (("f1", "f2") if x == 0.0 else ("gf", "f1", "f2")):
                _g_window(mb, px1 - x, row, nc, flowers=fl2)
        door(mb, px1, FL, 2.0, 2.8, leaf=WALL, surround=GTRIM, handle=GOLD, panel_mat=GTRIM, fan=False)
    with facade(mb, (x0, y1), (x0, y0)):  # west (conservatory side: ground floor hidden)
        for y in (9.6, 13.1, 16.6, 20.1):
            _g_window(mb, y1 - y, "f1", nc, flowers=fl2)
            _g_window(mb, y1 - y, "f2")
        door(mb, y1 - 15.0, 0.15, 1.8, 2.7, leaf=WALL, surround=GTRIM, handle=GOLD, panel_mat=GTRIM, fan=False)
    with facade(mb, (x1, y0), (x1, y1)):  # east
        for y in (9.2, 20.8):
            for row in ("gf", "f1", "f2"):
                _g_window(mb, y - y0, row, nc, flowers=fl)
        _g_window(mb, 15.0 - y0, "f2")
    # east round bay (two storeys)
    bx, by, br = x1, 15.0, 2.6
    hp = (-math.pi / 2, math.pi / 2)
    lathe_arc(mb, [(br, -4.0), (br, 9.4)], WALL, *hp, 12, center=(bx, by, 0.0))
    lathe_arc(mb, [(br + 0.2, -4.0), (br + 0.2, FL + 0.3)], MARBLE, *hp, 12, center=(bx, by, 0.0))
    lathe_arc(mb, [(br + 0.2, FL + 0.3), (br, FL + 0.3)], MARBLE, *hp, 12, center=(bx, by, 0.0))
    lathe_arc(mb, [(br + 0.1, 5.25), (br + 0.1, 5.55)], GTRIM, *hp, 12, center=(bx, by, 0.0))
    lathe_arc(mb, [(br + 0.1, 5.55), (br, 5.55)], GTRIM, *hp, 12, center=(bx, by, 0.0))
    lathe_arc(mb, [(br, 9.05), (br + 0.4, 9.05)], GTRIM, *hp, 12, center=(bx, by, 0.0))
    lathe_arc(mb, [(br + 0.4, 9.05), (br + 0.4, 9.4)], GTRIM, *hp, 12, center=(bx, by, 0.0))
    lathe_arc(mb, [(br + 0.5, 9.4), (br * 0.6, 10.4), (0.05, 11.0)], GROOF, *hp, 12, center=(bx, by, 0.0))
    for a_deg in (-55.0, 0.0, 55.0):
        a = math.radians(a_deg)
        with mb.at((bx + math.cos(a) * br, by + math.sin(a) * br, 0.0), rot=a_deg + 90):
            window(mb, 0.0, 1.85, 1.0, 2.8, GTRIM, sill_mat=MARBLE, head="lintel", head_mat=GTRIM, mullion=False)
            window(mb, 0.0, 6.0, 1.0, 2.5, GTRIM, sill_mat=MARBLE, head="lintel", head_mat=GTRIM, mullion=False)

    # ------------------------------------------------------------ entrance porch with balcony
    for x in (-3.9, -1.9, 1.9, 3.9):
        column(mb, x, -2.6, FL, 0.26, 3.8, MARBLE, seg=12)
    mb.box_mm((-4.6, -3.3, 5.0), (4.6, py0, 5.5), GTRIM, mats={"+z": FLOOR})
    mb.box_mm((-4.7, -3.4, 5.5), (4.7, py0, 5.6), MARBLE)
    balustrade(mb, [(-4.45, py0), (-4.45, -3.15), (4.45, -3.15), (4.45, py0)], 5.6, MARBLE, GTRIM, h=0.95,
               post_mat=MARBLE)
    for x in (-4.45, 4.45):
        urn(mb, x, -3.15, 6.65, 0.55, MARBLE)
        for k in range(3):
            flower_clump(nc, x + (k - 1) * 0.14, -3.15 + (k % 2) * 0.12, 7.15, "M_FlowerRed", 0.18)
    aset.light((0.0, -1.0, 4.5), WARM, 6000, 10, night_only=True)

    # ------------------------------------------------------------ front terrace + steps
    tx0, ty0, tx1, ty1 = -16.4, -10.0, 16.4, y0
    mb.box_mm((tx0, ty0, -4.0), (tx1, ty1, FL), WALL, skip=("-z",), mats={"+z": FLOOR})
    mb.box_mm((tx0 - 0.12, ty0 - 0.12, FL - 0.22), (tx1 + 0.12, ty1, FL), GTRIM, skip=("-z", "+z"))
    mb.box_mm((tx0 - 0.15, ty0 - 0.15, -4.0), (tx1 + 0.15, ty1, 0.3), MARBLE, skip=("-z",))
    flight(mb, (0.0, ty0 - 5 * 0.5, 0.0), 90, 9.2, 5, 0.24, 0.5, MARBLE)
    balustrade(mb, [(-4.75, ty0 + 0.2), (tx0 + 0.2, ty0 + 0.2), (tx0 + 0.2, ty1 - 0.4)], FL, MARBLE, GTRIM,
               post_every=3.0, post_mat=MARBLE)
    balustrade(mb, [(tx1 - 0.2, ty1 - 0.4), (tx1 - 0.2, ty0 + 0.2), (4.75, ty0 + 0.2)], FL, MARBLE, GTRIM,
               post_every=3.0, post_mat=MARBLE)
    for sx in (-1, 1):
        mb.box((sx * 4.75, ty0 + 0.2, FL + 0.7), (0.55, 0.55, 1.4), MARBLE)
        mb.box((sx * 4.75, ty0 + 0.2, FL + 1.45), (0.65, 0.65, 0.1), GTRIM)
        mb.cylinder((sx * 4.75, ty0 + 0.2, FL + 1.5), 0.08, 0.5, IRON, seg=8)
        nc.sphere((sx * 4.75, ty0 + 0.2, FL + 2.25), 0.3, GLOW, seg=12, rings=8)
        aset.light((sx * 4.75, ty0 + 0.2, FL + 2.3), WARM, 3500, 10, night_only=True)
        xa, xb = sorted((sx * 4.35, sx * 4.85))
        mb.box_mm((xa, ty0 - 2.6, -0.5), (xb, ty0, FL - 0.1), WALL, skip=("-z",))
        xa, xb = sorted((sx * 4.3, sx * 4.9))
        mb.box_mm((xa, ty0 - 2.65, FL - 0.1), (xb, ty0, FL), GTRIM)
    # back stoop + steps
    mb.box_mm((-2.6, py1, -4.0), (2.6, py1 + 2.0, FL), MARBLE, skip=("-z",), mats={"+z": FLOOR})
    flight(mb, (0.0, py1 + 2.0 + 5 * 0.5, 0.0), -90, 5.2, 5, 0.24, 0.5, MARBLE)
    aset.light((0.0, py1 + 1.0, 4.4), WARM, 3000, 8, night_only=True)

    _girls_conservatory(mb, aset)


def _girls_conservatory(mb, aset):
    cx0, cy0, cx1, cy1 = -33.0, 8.6, -22.0, 21.4
    zf, zw, ze, zr = 0.15, 0.7, 4.0, 6.6
    mb.box_mm((cx0, cy0, -1.0), (cx1, cy1, zf), MARBLE, skip=("-z",), mats={"+z": FLOOR})
    nb = 10                       # bays along the front (1.1 m)
    bay = (cx1 - cx0) / nb
    d0, d1 = cx0 + 4 * bay, cx0 + 6 * bay        # doorway = two bays (2.2 m)
    # low walls (front with the doorway gap, west, back) + pink coping
    for (a, b) in (((cx0, cy0), (d0, cy0 + 0.3)), ((d1, cy0), (cx1, cy0 + 0.3)),
                   ((cx0, cy0 + 0.3), (cx0 + 0.3, cy1 - 0.3)), ((cx0, cy1 - 0.3), (cx1, cy1))):
        mb.box_mm((a[0], a[1], zf), (b[0], b[1], zw), WALL)
        mb.box_mm((a[0] - 0.04, a[1] - 0.04, zw), (b[0] + 0.04, b[1] + 0.04, zw + 0.08), GTRIM)
    sides = [((cx0, cy0 + 0.15), (cx1, cy0 + 0.15)), ((cx0 + 0.15, cy1), (cx0 + 0.15, cy0)),
             ((cx1, cy1 - 0.15), (cx0, cy1 - 0.15))]
    for si, (p0, p1) in enumerate(sides):
        L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
        n = nb if si != 1 else max(2, round(L / 1.1))
        with facade(mb, p0, p1):
            for k in range(n + 1):
                u = L * k / n
                if si == 0 and k == 5:
                    mb.box((u, 0.0, (2.8 + ze) / 2), (0.12, 0.16, ze - 2.8), FRAME)
                    continue
                zb = zf if (si == 0 and k in (4, 6)) else zw + 0.08
                mb.box((u, 0.0, (zb + ze) / 2), (0.12, 0.16, ze - zb), FRAME)
            for k in range(n):
                u0, u1 = L * k / n + 0.06, L * (k + 1) / n - 0.06
                um = (u0 + u1) / 2
                if si == 0 and k in (4, 5):
                    mb.box((um, 0.0, (2.8 + ze) / 2), (u1 - u0, 0.03, ze - 2.8), CLEAR)
                    continue
                mb.box((um, 0.0, (zw + 0.08 + ze) / 2), (u1 - u0, 0.03, ze - zw - 0.08), CLEAR)
            mb.box((L / 2, 0.0, 2.8), (L, 0.14, 0.1), FRAME)
            mb.box((L / 2, 0.0, ze + 0.1), (L + 0.2, 0.3, 0.2), FRAME)
    # glass roof (double sided) with white ribs and a gilded crest
    ov = 0.25
    r0, r1 = hip_top(mb, cx0 - ov, cy0 - ov, cx1 + ov, cy1 + ov, ze + 0.2, zr - ze - 0.2, CLEAR, double=True)
    for (x, y) in ((cx0 - ov, cy0 - ov), (cx1 + ov, cy0 - ov), (cx0 - ov, cy1 + ov), (cx1 + ov, cy1 + ov)):
        mb.beam((x, y, ze + 0.22), r0 if y < (cy0 + cy1) / 2 else r1, 0.14, 0.12, FRAME)
    for k in range(1, 8):
        y = cy0 + (cy1 - cy0) * k / 8
        yr = min(max(y, r0[1]), r1[1])
        mb.beam((cx0 - ov, y, ze + 0.22), (r0[0], yr, zr - 0.02), 0.08, 0.1, FRAME)
    mb.beam((r0[0], r0[1] - 0.1, zr + 0.05), (r1[0], r1[1] + 0.1, zr + 0.05), 0.14, 0.2, GOLD)
    for r in (r0, r1):
        finial(mb, r[0], r[1], r[2] + 0.1, 0.6)
    # interior dressing
    for (x, y) in ((-31.6, 12.0), (-31.6, 18.0), (-24.0, 19.9)):
        aset.prop("SM_Planter", (x, y, zf), 0.0)
    for i, (x, y) in enumerate(((-31.0, 10.2), (-23.6, 10.4), (-31.6, 15.0), (-27.0, 20.2))):
        aset.prop(("SM_FlowerBush_Red", "SM_FlowerBush_White", "SM_Fern_A", "SM_FlowerBush_Yellow")[i],
                  (x, y, zf), 0.0)
    aset.prop("SM_Bench", (-27.5, 17.4, zf), 180.0)
    aset.prop("SM_BroadTree_C", (-27.5, 14.2, zf), 0.0, 0.7)
    aset.light((-27.5, 15.0, 3.6), WARM, 3500, 10, night_only=True)
    aset.npc((-25.5, 15.5, zf), 90.0, dorm="obelisk", wander=3.0)


def _gazebo(mb, nc, aset, cx, cy):
    lathe_crisp(mb, [(4.9, -0.6), (4.9, 0.25), (4.4, 0.25), (4.4, 0.5)], MARBLE, 32, center=(cx, cy, 0.0),
                cap_top=True)
    disc(mb, cx, cy, 0.52, 3.2, FLOOR, seg=32)
    ang = [math.radians(22.5 + 45 * i) for i in range(8)]
    pts = [(cx + math.cos(a) * 3.7, cy + math.sin(a) * 3.7) for a in ang]
    for (x, y) in pts:
        column(mb, x, y, 0.5, 0.22, 3.3, MARBLE, seg=12)
    for i in range(0, 8, 2):   # diagonal bays get a balustrade, the four cardinal bays are open
        balustrade(mb, [pts[i], pts[i + 1]], 0.5, MARBLE, GTRIM, h=0.9, posts=False, spacing=0.28)
    lathe_crisp(mb, [(4.1, 3.8), (4.1, 4.15)], MARBLE, 32, center=(cx, cy, 0.0), cap_bottom=True)
    lathe_crisp(mb, [(4.15, 4.15), (4.15, 4.5)], GTRIM, 32, center=(cx, cy, 0.0))
    lathe_crisp(mb, [(4.15, 4.5), (4.5, 4.7), (4.5, 4.85)], MARBLE, 32, center=(cx, cy, 0.0), cap_top=True)
    prof = [(4.3, 4.85)]
    for i in range(1, 9):
        a = math.pi / 2 * i / 9
        prof.append((max(4.1 * math.cos(a), 0.45), 4.85 + 3.0 * math.sin(a)))
    mb.lathe(prof, GROOF, 32, cap_top=True, cap_bottom=False, center=(cx, cy, 0.0))
    for a in ang:
        for i in range(len(prof) - 1):
            r0, z0 = prof[i]
            r1, z1 = prof[i + 1]
            mb.beam((cx + math.cos(a) * (r0 + 0.03), cy + math.sin(a) * (r0 + 0.03), z0),
                    (cx + math.cos(a) * (r1 + 0.03), cy + math.sin(a) * (r1 + 0.03), z1), 0.14, 0.1, GTRIM)
    finial(mb, cx, cy, prof[-1][1] - 0.05, 1.1)
    mb.beam((cx, cy, 3.8), (cx, cy, 3.25), 0.04, 0.04, GOLD)
    lantern(mb, nc, cx, cy, 2.45, 0.9, frame=GOLD, cap=GOLD)
    aset.light((cx, cy, 2.8), WARM, 4500, 12, night_only=True)


def _girls_garden(mb, nc, aset):
    gx, gy = G_GAZEBO
    # ---- walks
    slab(mb, -2.6, gy + 8.6, 2.6, -12.45)
    ring_slab(mb, gx, gy, 5.0, 9.0, top=P_RING, seg=40)
    slab(mb, -2.6, -62.5, 2.6, gy - 8.6)
    slab(mb, -33.0, gy - 2.0, gx - 8.7, gy + 2.0)
    slab(mb, gx + 8.7, gy - 2.0, 35.0, gy + 2.0)
    slab(mb, -21.0, -27.6, 21.0, -26.4, top=P_LOW)
    mb.prism(circle(24, 4.4, 38.5, gy), -0.3, P_RING, PAVE, cap_bottom=False)
    a_out = xf(G_ARCH, G_ARCH_YAW, (0.0, -4.0))
    strip(mb, a_out, (-29.5, gy + 0.6), 4.6, top=P_LOW)
    # ---- flower beds (raised, marble curb, soil top; the flowers are props)
    beds = [(5.0, -25.4, 19.5, -14.6), (5.0, -40.6, 19.5, -28.6)]
    beds += [(-x1, y0, -x0, y1) for (x0, y0, x1, y1) in beds]
    cols = ("SM_FlowerBush_Red", "SM_FlowerBush_White", "SM_FlowerBush_Blue", "SM_FlowerBush_Yellow")
    for bi, (x0, y0, x1, y1) in enumerate(beds):
        outer = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        inner = [(x0 + 0.3, y0 + 0.3), (x1 - 0.3, y0 + 0.3), (x1 - 0.3, y1 - 0.3), (x0 + 0.3, y1 - 0.3)]
        mb.slab_ring(outer, inner, -0.2, 0.4, MARBLE)
        mb.slab_ring([(x0 - 0.05, y0 - 0.05), (x1 + 0.05, y0 - 0.05), (x1 + 0.05, y1 + 0.05), (x0 - 0.05, y1 + 0.05)],
                     [(x0 + 0.3, y0 + 0.3), (x1 - 0.3, y0 + 0.3), (x1 - 0.3, y1 - 0.3), (x0 + 0.3, y1 - 0.3)],
                     0.4, 0.47, GTRIM)
        mb.poly([(p[0], p[1], 0.3) for p in inner], SOIL)
        nx, ny = int((x1 - x0) / 2.1), int((y1 - y0) / 2.1)
        for i in range(nx):
            for j in range(ny):
                px = x0 + (x1 - x0) * (i + 0.5) / nx
                py = y0 + (y1 - y0) * (j + 0.5) / ny
                aset.prop(cols[(j + bi) % 4], (px, py, 0.3), (i * 37 + j * 53) % 360, 0.85)
    # ---- low hedges framing the beds and the terrace foot
    for sx in (-1, 1):
        hedge_box(mb, sx * 21.0, -41.0, sx * 21.8, -13.0, 0.7)
        hedge_box(mb, sx * 6.0, -11.6, sx * 16.0, -10.7, 0.8)
    # ---- lantern pillars where the walk leaves the pad toward the lake
    for sx in (-1, 1):
        x, y = sx * 3.4, -61.8
        mb.box_mm((x - 0.4, y - 0.4, -0.5), (x + 0.4, y + 0.4, 1.6), MARBLE, skip=("-z",))
        mb.box_mm((x - 0.48, y - 0.48, 1.6), (x + 0.48, y + 0.48, 1.72), GTRIM)
        lantern(mb, nc, x, y, 1.72, 1.1, frame=IRON, cap=GOLD)
        aset.light((x, y, 2.2), WARM, 3000, 9, night_only=True)
    # ---- rose arch with the name board, straddling the arriving academy path
    ax, ay = G_ARCH
    hw = 3.0
    with mb.at((ax, ay, 0.0), rot=G_ARCH_YAW):
        for sx in (-1, 1):
            mb.box_mm((sx * hw - 0.25, -0.25, -0.5), (sx * hw + 0.25, 0.25, 3.4), FRAME, skip=("-z",))
            mb.box_mm((sx * hw - 0.32, -0.32, 3.4), (sx * hw + 0.32, 0.32, 3.55), GTRIM)
            mb.box_mm((sx * hw - 0.32, -0.32, -0.5), (sx * hw + 0.32, 0.32, 0.35), GTRIM, skip=("-z",))
        arc_band(mb, 0.0, 3.55, hw - 0.1, hw + 0.2, 0.0, math.pi, 16, -0.16, 0.16, FRAME)
        mb.sign_board((0.0, 0.0, 4.15), 5.4, 0.75, GTRIM, FRAME, thick=0.14, posts=False)
        finial(mb, 0.0, 0.0, 3.55 + hw + 0.15, 0.6)
    for i in range(18):
        a = math.pi * i / 17
        for s in (-1, 1):
            p = xf(G_ARCH, G_ARCH_YAW, (math.cos(a) * (hw + 0.05), s * 0.16, 3.55 + math.sin(a) * (hw + 0.05)))
            flower_clump(nc, p[0], p[1], p[2] - 0.12, "M_FlowerWhite" if (i + (s > 0)) % 3 == 0 else "M_FlowerRed", 0.22)
        if i % 2 == 0:
            p = xf(G_ARCH, G_ARCH_YAW, (math.cos(a) * (hw + 0.05), 0.0, 3.55 + math.sin(a) * (hw + 0.05)))
            flower_clump(nc, p[0], p[1], p[2] - 0.1, "M_LeavesBush", 0.3)
    for s in (-1, 1):
        for k in range(5):
            for f in (-1, 1):
                p = xf(G_ARCH, G_ARCH_YAW, (s * hw, f * 0.3, 0.5 + k * 0.62))
                flower_clump(nc, p[0], p[1], p[2], "M_LeavesBush" if (k + (f > 0)) % 2 else "M_FlowerRed", 0.22)
    aset.text("OBELISK BLUE GIRLS' DORM", xf(G_ARCH, G_ARCH_YAW, (0.0, -0.07 - 0.025, 4.15)), G_ARCH_YAW,
              size=0.3, color=(1.0, 1.0, 1.0))
    aset.text("OBELISK BLUE GIRLS' DORM", xf(G_ARCH, G_ARCH_YAW, (0.0, 0.07 + 0.025, 4.15)), G_ARCH_YAW + 180.0,
              size=0.3, color=(1.0, 1.0, 1.0))
    aset.interact("sign", xf(G_ARCH, G_ARCH_YAW, (hw + 1.2, -1.2, 1.0)), G_ARCH_YAW,
                  title="Obelisk Blue Girls' Dorm",
                  text="Obelisk Blue Girls' Dorm - boys caught near the lake answer to the Queen of Obelisk Blue.")
    for sx in (-1, 1):
        p = xf(G_ARCH, G_ARCH_YAW, (sx * (hw + 1.6), 0.6))
        aset.prop("SM_LampPost", (p[0], p[1], 0.0), G_ARCH_YAW)

    # ---- props
    lamps = [(sx * 3.7, y) for sx in (-1, 1) for y in (-17.0, -31.0)]
    lamps += [(x, gy - 2.7) for x in (-28.0, -18.0, 18.0, 30.0)]
    for (x, y) in lamps:
        aset.prop("SM_LampPost", (x, y, 0.05), 0.0)
    for sx in (-1, 1):
        aset.prop("SM_Bench", (sx * 5.6, gy - 7.6, 0.05), 0.0)
        bx, by = sx * 7.0, gy + 4.4
        aset.prop("SM_Bench", (bx, by, 0.05), face_yaw(bx, by, gx, gy))
    for ang in (-60, 0, 60):
        a = math.radians(ang - 90)
        bx, by = 38.5 + math.cos(a) * 3.2, gy + math.sin(a) * 3.2
        aset.prop("SM_Bench", (bx, by, 0.05), face_yaw(38.5, gy, bx, by))
    aset.prop("SM_BroadTree_C", (40.8, gy + 4.6, 0.0), 30.0, 1.2)
    trees = [(sx * 23.5, -13.0) for sx in (-1, 1)] + [(sx * 23.5, -40.0) for sx in (-1, 1)]
    trees += [(sx * 14.0, -54.0) for sx in (-1, 1)] + [(30.0, -56.0), (-24.0, -60.0)]
    trees += [(sx * 46.0, -24.0) for sx in (-1, 1)]
    for i, (x, y) in enumerate(trees):
        aset.prop("SM_BroadTree_C", (x, y, 0.0), (i * 53) % 360, 1.0 + 0.1 * (i % 3))
    big = [(sx * 40.0, 36.0) for sx in (-1, 1)] + [(sx * 18.0, 44.0) for sx in (-1, 1)]
    big += [(sx * 55.0, 10.0) for sx in (-1, 1)] + [(0.0, 48.0), (52.0, -8.0)]
    for i, (x, y) in enumerate(big):
        aset.prop("SM_BroadTree_A" if i % 2 else "SM_BroadTree_B", (x, y, 0.0), (i * 71) % 360, 0.9 + 0.08 * (i % 3))
    for sx in (-1, 1):
        for k in range(5):
            aset.prop("SM_FlowerBush_Red" if k % 2 else "SM_FlowerBush_White", (sx * 17.8, -9.0 + k * 2.4, 0.0),
                      0.0, 0.8)
    for (p, yaw) in (((5.0, -5.0), 0.0), ((-9.0, -7.0), 30.0), ((12.0, -27.0), 90.0), ((-20.0, gy + 0.5), -90.0),
                     ((gx + 1.0, gy - 1.5), 0.0), ((38.5, gy - 1.0), 0.0), ((0.0, -58.0), 0.0)):
        if p[1] > -10.0 and abs(p[0]) < 16.0:
            z = G_FL
        elif math.dist(p, (gx, gy)) < 4.0:
            z = 0.52
        else:
            z = 0.05
        aset.npc((p[0], p[1], z), yaw, dorm="obelisk", wander=5.0)


def _girls_jetty(mb, nc, aset):
    O = (JETTY_OFFSET[0], JETTY_OFFSET[1], 0.0)
    Y = JETTY_YAW
    L = JETTY_LENGTH
    dz = JETTY_DECK_Z
    lz = JETTY_LAND_Z
    nb = max(2, round(L / 3.0))
    bents = [-L * i / nb for i in range(nb + 1)]
    head = -L + 4.0                        # the last 4 m are a 6 m wide platform
    moor = [y for i, y in enumerate(bents) if i % 2 == 1 and y > head + 0.5]
    with mb.at(O, rot=Y):
        # stone causeway: ramp section, landing section (convex pieces), down to -6
        prism_yz(mb, [(-0.4, -6.0), (6.0, -6.0), (6.0, lz - 0.12), (0.0, dz - 0.12), (-0.4, dz - 0.12)],
                 -2.0, 2.0, ROCK)
        mb.box_mm((-2.0, 6.0, -6.0), (2.0, 9.0, lz - 0.12), ROCK, skip=("-z",))
        mb.ramp((0.0, 0.0, dz), (0.0, 6.0, lz), 3.0, PIER, thick=0.12)
        mb.box_mm((-1.5, 6.0, lz - 0.12), (1.5, 9.0, lz), PIER, skip=("-z",))
        for sx in (-1, 1):
            mb.railing([(sx * 1.6, 0.3, dz), (sx * 1.6, 6.0, lz), (sx * 1.6, 8.8, lz)], 0.95, PIER,
                       post_spacing=1.5, post_size=0.12, rail_size=0.08)
        # deck planks
        for i in range(int(L / 0.3)):
            y = -0.15 - i * 0.3
            mb.box((0.0, y, dz - 0.04), (6.0 if y < head else 3.0, 0.26, 0.08), PIER)
        # stringers, cross beams (caps), posts down to z=-6, mooring posts through the deck edge
        for x in (-1.2, -0.4, 0.4, 1.2):
            mb.box_mm((x - 0.08, -L, dz - 0.34), (x + 0.08, 0.0, dz - 0.08), PIER, skip=("-z",))
        for x in (-2.8, -2.0, 2.0, 2.8):
            mb.box_mm((x - 0.08, -L, dz - 0.34), (x + 0.08, head, dz - 0.08), PIER, skip=("-z",))
        for y in bents:
            wide = y < head + 0.01
            xs = (-2.85, -1.45, 1.45, 2.85) if wide else (-1.45, 1.45)
            mb.box_mm((xs[0] - 0.14, y - 0.12, dz - 0.5), (xs[-1] + 0.14, y + 0.12, dz - 0.34), PIER)
            for x in xs:
                top = dz + 0.7 if (y in moor) else dz - 0.34
                mb.cylinder((x, y, -6.0), 0.15, top + 6.0, PIER, seg=8, cap_bottom=False)
                if y in moor:
                    mb.cylinder((x, y, top), 0.18, 0.08, IRON, seg=8, cap_bottom=False)
        # end rail, lamp post with lantern
        mb.railing([(-3.0, -L + 0.12, dz), (3.0, -L + 0.12, dz)], 0.9, PIER, post_spacing=1.5, post_size=0.12,
                   rail_size=0.08)
        lx, ly = 2.6, -L + 0.5
        mb.box((lx, ly, dz + 1.6), (0.2, 0.2, 3.2), PIER)
        mb.box((lx - 0.4, ly, dz + 3.1), (0.9, 0.12, 0.12), PIER)
        mb.beam((lx - 0.75, ly, dz + 3.05), (lx - 0.75, ly, dz + 2.9), 0.03, 0.03, IRON)
        lantern(mb, nc, lx - 0.75, ly, dz + 2.1, 0.9, frame=IRON, cap=GOLD)
        # warning board at the landing, readable from the shore side
        mb.box((-1.85, 8.75, lz + 1.25), (0.14, 0.14, 2.5), PIER)
        with mb.at((-1.85, 8.75, lz), rot=180.0):
            mb.sign_board((0.0, 0.0, 2.25), 1.9, 0.6, PIER, GTRIM, thick=0.08, posts=False)
    # mooring ropes (no collision)
    boats = [(2.9, moor[0] - 1.2), (-2.9, moor[1] - 1.2), (2.9, moor[1] - 1.2)] if len(moor) > 1 else []
    with nc.at(O, rot=Y):
        for (bx, by) in boats:
            sx = 1 if bx > 0 else -1
            my = by + 1.2
            nc.beam((sx * 1.45, my, dz + 0.55), (sx * 2.3, my + 0.4, LAKE_Z + 0.45), 0.04, 0.04, "M_Fabric")
    aset.light(xf(O, Y, (lx - 0.75, ly, dz + 2.4)), WARM, 4000, 14, night_only=True)
    aset.light(xf(O, Y, (0.0, 4.0, lz + 2.6)), WARM, 2000, 8, night_only=True)
    tz = lz + 2.25
    aset.text("GIRLS' DORM PIER", xf(O, Y, (-1.85, 8.75 + 0.04 + 0.025, tz + 0.12)), Y + 180.0, size=0.16,
              color=(0.95, 0.66, 0.74))
    aset.text("NO BOYS ALLOWED", xf(O, Y, (-1.85, 8.75 + 0.04 + 0.025, tz - 0.14)), Y + 180.0, size=0.16,
              color=(0.95, 0.66, 0.74))
    for (bx, by) in boats:
        aset.prop("SM_Rowboat", xf(O, Y, (bx, by, LAKE_Z)), Y + 90.0)
    aset.prop("SM_Bench", xf(O, Y, (-1.4, -L + 0.9, dz)), Y)
    aset.npc(xf(O, Y, (0.5, -L + 2.2, dz)), Y, dorm="obelisk", wander=2.5)


def build_girls():
    aset = AssetSet("obelisk_girls")
    main = aset.mesh("ObeliskGirls_Main")
    garden = aset.mesh("ObeliskGirls_Garden")
    gazebo = aset.mesh("ObeliskGirls_Gazebo")
    jetty = aset.mesh("ObeliskGirls_Jetty")
    nc = aset.mesh("ObeliskGirls_NoCol")
    _girls_building(main, nc, aset)
    _girls_garden(garden, nc, aset)
    _gazebo(gazebo, nc, aset, *G_GAZEBO)
    _girls_jetty(jetty, nc, aset)
    return aset


PLACEMENTS = {"obelisk_boys": build_boys, "obelisk_girls": build_girls}
