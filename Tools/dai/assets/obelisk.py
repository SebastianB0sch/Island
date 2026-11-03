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
import os
from contextlib import contextmanager

from . import AssetSet
from . import interior as K
from .. import palette

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
    """Local frame on a face running p0 -> p1 (outside to the RIGHT): x along, -y outwards.
    While a hollow building is planned (_P), windows/doors drawn on a face listed in _P["faces"] are
    recorded as real openings (see _record) instead of getting opaque glass / a painted leaf."""
    global _FACE
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    old = _FACE
    _FACE = (tuple(p0), tuple(p1), z)
    try:
        with mb.at((p0[0], p0[1], z), rot=math.degrees(math.atan2(dy, dx))):
            yield math.hypot(dx, dy)
    finally:
        _FACE = old


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
           sill_mat=None, mullion=True, shutter_mat=None, keystone=None, fw=0.15, fd=0.12, seg=8,
           rect_glass=True, as_door=None):
    """Framed window on a facade frame (wall plane y=0, outside -y). z = sill height, h = height
    of the rectangular part (arched windows add a semicircle of radius w/2 on top).
    rect_glass=False leaves the rectangle unglazed (a real opening cut by the caller); as_door=<door style>
    turns it into a French door (no sill, no mullion) when the face is cut."""
    gy = -0.03
    hm = head_mat or frame
    cut = _cut_here(z)
    if cut:
        _record("door" if as_door else "win", u, z, z + h, w, w / 2.0 if arch else 0.0, style=as_door,
                double=bool(as_door) and w > 1.2)
        if as_door:
            mullion = False
    if rect_glass and not cut:
        mb.poly([(u - w / 2, gy, z), (u + w / 2, gy, z), (u + w / 2, gy, z + h), (u - w / 2, gy, z + h)], glass)
    r = w / 2.0
    top = z + h
    if arch:
        pts = [(u + math.cos(math.pi * i / seg) * r, gy, top + math.sin(math.pi * i / seg) * r)
               for i in range(seg + 1)]
        if not cut:
            mb.poly(pts, glass)
        arc_band(mb, u, top, r, r + fw, 0.0, math.pi, seg, -fd, 0.0, frame)
        top_ext = top + r + fw
    else:
        mb.box((u, -fd / 2, top + fw / 2), (w + 2 * fw, fd, fw), frame, skip=("+y",))
        top_ext = top + fw
    for s in (-1, 1):
        mb.box((u + s * (w / 2 + fw / 2), -fd / 2, z + h / 2), (fw, fd, h), frame, skip=("+y",))
    if not (cut and as_door):
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
         panel_mat=None, depth=0.3, style="obelisk"):
    """Double door with a moulded surround and an optional arched fanlight (facade frame). On a cut face
    the painted leaf is replaced by a real doorway with an automatic door of `style`."""
    pm = panel_mat or handle
    if _cut_here(z):
        _record("door", u, z, z + h, w, style=style, double=True)
    else:
        _door_leaf(mb, u, z, w, h, leaf, handle, pm)
    return _door_surround(mb, u, z, w, h, surround, fan_glass, fan, depth)


def _door_leaf(mb, u, z, w, h, leaf, handle, pm):
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


def _door_surround(mb, u, z, w, h, surround, fan_glass, fan, depth):
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
    mb.box_mm((x0 - 0.5, y0 - 0.5, top - 0.6), (x1 + 0.5, y1 + 0.5, top), cornice[1])
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


# ============================================================================= interiors: infrastructure
# The dorms are walk-in: every block is a shell of thick walls (outer face exactly where the old solid block
# face was) with real window / door openings cut where the facade helpers draw them, floor slabs, ceilings,
# partitions with automatic doors, and furnished rooms (catalog props SM_Int_* + the interior kit).
palette.register({
    "M_ObIntWallNavy":   K._t((0.26, 0.36, 0.68), "Fabric", 1.5, 0.3),
    "M_ObIntWallIvory":  K._t((0.97, 0.93, 0.84), "Fabric", 1.5, 0.25),
    "M_ObIntWallRose":   K._t((0.99, 0.84, 0.89), "Fabric", 1.5, 0.25),
    "M_ObIntWallLilac":  K._t((0.88, 0.84, 0.98), "Fabric", 1.5, 0.25),
    "M_ObIntMarbleNavy": K._t((0.15, 0.22, 0.45), "Marble", 0.3, 0.45, rough=0.15),
    "M_ObIntMarbleRose": K._t((0.97, 0.79, 0.85), "Marble", 0.3, 0.45, rough=0.15),
    "M_ObIntDuelMat":    dict(kind="emissive", color=(0.25, 0.55, 1.0), strength=1.4),
    "M_ObIntCrystal":    dict(kind="emissive", color=(0.80, 0.92, 1.0), strength=2.0),
})
WALL_NAVY, WALL_IVORY, WALL_ROSE, WALL_LILAC = ("M_ObIntWallNavy", "M_ObIntWallIvory", "M_ObIntWallRose",
                                                "M_ObIntWallLilac")
MARBLE_NAVY, MARBLE_ROSE = "M_ObIntMarbleNavy", "M_ObIntMarbleRose"
WARM_IN = (1.0, 0.86, 0.66)
E_IN = 0.1           # floors / ceilings run this far under the surrounding walls (no slits)

_P = None            # plan of the building being built: faces to cut, recorded holes, rooms, openings
_FACE = None         # facade currently being drawn (p0, p1, z)


def _plan_reset(faces=None):
    """faces: {(x0, y0, x1, y1) rounded: zmax} - windows/doors below zmax on those faces get real openings."""
    global _P
    _P = dict(faces={_fkey(k[:2], k[2:]): v for k, v in (faces or {}).items()}, holes=[], rooms=[], open=[])


def _plan_end():
    global _P
    _P = None


def _fkey(p0, p1):
    return (round(p0[0], 2), round(p0[1], 2), round(p1[0], 2), round(p1[1], 2))


def _cut_here(z):
    if _P is None or _FACE is None:
        return False
    zmax = _P["faces"].get(_fkey(_FACE[0], _FACE[1]))
    return zmax is not None and _FACE[2] + z < zmax


def _record(kind, u, z0, z1, w, r=0.0, style=None, double=False):
    p0, p1, fz = _FACE
    L = math.dist(p0, p1)
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    _P["holes"].append(dict(kind=kind, x=p0[0] + ux * u, y=p0[1] + uy * u, z0=z0 + fz, z1=z1 + fz, w=w, r=r,
                            style=style, double=double))


def _dir(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    return L, dx / L, dy / L, math.degrees(math.atan2(dy, dx))


def _face(mb, pts, mat, want):
    """Planar polygon whose normal is turned towards the direction `want`."""
    n = [0.0, 0.0, 0.0]
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    if n[0] * want[0] + n[1] * want[1] + n[2] * want[2] < 0:
        pts = list(reversed(pts))
    mb.poly(pts, mat)


class _XfSet:
    """AssetSet stand-in for furniture placed in a room Frame (moves sockets into the frame)."""

    def __init__(self, aset, f):
        self.aset, self.f = aset, f

    def socket(self, type, pos, yaw=0.0, **props):
        p = self.f.P(pos[0], pos[1], pos[2] if len(pos) > 2 else 0.0)
        if "target" in props:
            props = dict(props, target=self.f.P(*props["target"]))
        self.aset.socket(type, p, yaw + self.f.rot, **props)

    prop, light, text, interact, npc = AssetSet.prop, AssetSet.light, AssetSet.text, AssetSet.interact, AssetSet.npc
    door, special, emitter, audio = AssetSet.door, AssetSet.special, AssetSet.emitter, AssetSet.audio


class Frame:
    """Room frame: origin (cx, cy) on the floor at height z, rotated by rot (deg). Inside `with f:` the
    builders mb / nc work in local coordinates; f.a is the matching AssetSet stand-in."""

    def __init__(self, aset, mb, nc, cx, cy, z, rot=0.0):
        self.aset, self.mb, self.nc, self.cx, self.cy, self.z, self.rot = aset, mb, nc, cx, cy, z, rot
        self.a = _XfSet(aset, self)
        self._ctx = []

    def P(self, x, y, z=0.0):
        a = math.radians(self.rot)
        c, s = math.cos(a), math.sin(a)
        return (self.cx + c * x - s * y, self.cy + s * x + c * y, self.z + z)

    def prop(self, name, x, y, yaw=0.0, z=0.0, scale=1.0):
        self.a.prop(name, (x, y, z), yaw, scale)

    def light(self, x, y, z, intensity=3000.0, radius=8.0, color=WARM_IN):
        self.a.light((x, y, z), color, intensity, radius, night_only=False)

    def text(self, txt, x, y, z, yaw=0.0, size=0.2, color=(1, 1, 1)):
        self.a.text(txt, (x, y, z), yaw, size=size, color=color)

    def __enter__(self):
        c1 = self.mb.at((self.cx, self.cy, self.z), rot=self.rot)
        c2 = self.nc.at((self.cx, self.cy, self.z), rot=self.rot)
        c1.__enter__()
        c2.__enter__()
        self._ctx.append((c1, c2))
        return self

    def __exit__(self, *exc):
        c1, c2 = self._ctx.pop()
        c2.__exit__(*exc)
        c1.__exit__(*exc)
        return False


def _wall_yaw(side):
    """Yaw for a catalog piece whose back (+Y) goes against the room wall on `side` (local frame)."""
    return {"n": 0.0, "s": 180.0, "e": -90.0, "w": 90.0}[side]


# ----------------------------------------------------------------------------- rooms registry
def _room(name, fl, rect, z, zc, wall, floor, ceil=K.CEIL, cornice=K.TRIM_GOLD, dado=None, dado_h=0.6,
          skirting=K.TRIM_WHITE, levels=None, slab=True, holes=(), gaps=None, cut_ceiling=(), open="", coffer=None,
          panels=None, seams=None):
    """Register a room. rect = clear inner area (x0, y0, x1, y1); fl = storey index used to pick the inner
    finish of the outer walls; levels = storeys whose outer-wall finish this room provides (double height)."""
    r = dict(name=name, fl=fl, x0=rect[0], y0=rect[1], x1=rect[2], y1=rect[3], z=z, zc=zc, wall=wall, floor=floor,
             ceil=ceil, cornice=cornice, dado=dado, dado_h=dado_h, skirting=skirting, levels=levels or (fl,),
             slab=slab, holes=holes, gaps=gaps or {}, cut_ceiling=cut_ceiling, open=open, coffer=coffer, panels=panels,
             seams=seams)
    _P["rooms"].append(r)
    return r


def _room_at(x, y, fl):
    for r in _P["rooms"]:
        if fl in r["levels"] and r["x0"] - 1e-3 <= x <= r["x1"] + 1e-3 and r["y0"] - 1e-3 <= y <= r["y1"] + 1e-3:
            return r
    return None


def _open(x, y, z0, z1, w, axis):
    _P["open"].append(dict(x=x, y=y, z0=z0, z1=z1, w=w, axis=axis))


def _build_rooms(mb, nc):
    for r in _P["rooms"]:
        x0, y0, x1, y1, z = r["x0"], r["y0"], r["x1"], r["y1"], r["z"]
        e = E_IN
        if r["slab"]:
            K.slab(mb, x0 - e, y0 - e, x1 + e, y1 + e, z, 0.3, top=r["floor"], bottom=K.CEIL, side=r["wall"],
                   holes=r["holes"])
        if r["ceil"]:
            zc = r["zc"]
            cells = _cells(x0 - e, y0 - e, x1 + e, y1 + e, r["cut_ceiling"])
            for (a, b, c, d) in cells:
                mb.poly([(a, b, zc), (a, d, zc), (c, d, zc), (c, b, zc)], r["ceil"])
            if r["cornice"]:
                for side, (p0, p1) in _sides(r).items():
                    if side not in r["open"]:
                        _strip(mb, p0, p1, zc - 0.16, 0.16, 0.1, r["cornice"], r, ceiling=True)
        if r["coffer"]:
            _coffers(mb, r, *r["coffer"])
        if r["panels"]:
            _wall_panels(mb, r, r["panels"])
        if r["seams"]:
            _plank_seams(mb, r, r["seams"])
        if r["skirting"]:
            _dress_sides(mb, r, r["skirting"], 0.13, 0.02, None)
        if r["dado"]:
            _dress_sides(mb, r, r["dado"][0], r["dado_h"], 0.03, r["dado"][1])


def _coffers(mb, r, step, mat, edge=None):
    """Coffered ceiling: a grid of beams under the ceiling (cells about `step` wide)."""
    x0, y0, x1, y1, zc = r["x0"], r["y0"], r["x1"], r["y1"], r["zc"]
    nx, ny = max(1, round((x1 - x0) / step)), max(1, round((y1 - y0) / step))
    d, w = 0.2, 0.24
    for i in range(1, nx):
        x = x0 + (x1 - x0) * i / nx
        mb.box_mm((x - w / 2, y0, zc - d), (x + w / 2, y1, zc), mat, skip=("+z",))
        if edge:
            mb.box_mm((x - 0.03, y0, zc - d - 0.01), (x + 0.03, y1, zc - d), edge, skip=("+z",))
    for j in range(1, ny):
        y = y0 + (y1 - y0) * j / ny
        mb.box_mm((x0, y - w / 2, zc - d), (x1, y + w / 2, zc), mat, skip=("+z",))
        if edge:
            mb.box_mm((x0, y - 0.03, zc - d - 0.01), (x1, y + 0.03, zc - d), edge, skip=("+z",))


def _wall_panels(mb, r, mat, bar=0.05):
    """Moulded wall panels (thin frames) between the openings of every wall above the dado."""
    za = (r["dado_h"] if r["dado"] else 0.3) + 0.3
    zb = r["zc"] - r["z"] - 0.55
    if zb - za < 0.8:
        return
    for side, (p0, p1) in _sides(r).items():
        if side in r["open"]:
            continue
        L, ux, uy, yaw = _dir(p0, p1)
        gaps = sorted(_side_gaps(r, side, 99.0))
        free, u = [], 0.25
        for (a, b) in gaps + [(L - 0.25, L)]:
            if a - u > 0.9:
                free.append((u, a))
            u = max(u, b)
        with mb.at((p0[0], p0[1], r["z"]), rot=yaw):
            for (a, b) in free:
                n = max(1, round((b - a) / 2.2))
                pw = (b - a) / n
                for k in range(n):
                    c = a + pw * (k + 0.5)
                    w = pw - 0.35
                    # one raised moulding frame: an outer and an inner ring of quads (8 faces)
                    o = (c - w / 2, za, c + w / 2, zb)
                    i_ = (o[0] + bar, o[1] + bar, o[2] - bar, o[3] - bar)
                    y = 0.015
                    ring = [(o[0], o[1]), (o[2], o[1]), (o[2], o[3]), (o[0], o[3])]
                    inn = [(i_[0], i_[1]), (i_[2], i_[1]), (i_[2], i_[3]), (i_[0], i_[3])]
                    for k in range(4):
                        a0, a1, b1, b0 = ring[k], ring[(k + 1) % 4], inn[(k + 1) % 4], inn[k]
                        _face(mb, [(a0[0], y, a0[1]), (a1[0], y, a1[1]), (b1[0], y, b1[1]), (b0[0], y, b0[1])], mat,
                              (0, 1, 0))


def _plank_seams(mb, r, mat, pitch=0.22):
    x0, y0, x1, y1, z = r["x0"], r["y0"], r["x1"], r["y1"], r["z"]
    if x1 - x0 >= y1 - y0:
        n = int((y1 - y0) / pitch)
        for k in range(1, n):
            y = y0 + (y1 - y0) * k / n
            mb.poly([(x0, y - 0.006, z + 0.002), (x1, y - 0.006, z + 0.002), (x1, y + 0.006, z + 0.002),
                     (x0, y + 0.006, z + 0.002)], mat)
    else:
        n = int((x1 - x0) / pitch)
        for k in range(1, n):
            x = x0 + (x1 - x0) * k / n
            mb.poly([(x - 0.006, y0, z + 0.002), (x + 0.006, y0, z + 0.002), (x + 0.006, y1, z + 0.002),
                     (x - 0.006, y1, z + 0.002)], mat)


def _cells(x0, y0, x1, y1, holes):
    xs = sorted({x0, x1, *[v for h in holes for v in (h[0], h[2])]})
    ys = sorted({y0, y1, *[v for h in holes for v in (h[1], h[3])]})
    out = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(h[0] < cx < h[2] and h[1] < cy < h[3] for h in holes):
                continue
            out.append((xs[i], ys[j], xs[i + 1], ys[j + 1]))
    return out


def _sides(r):
    x0, y0, x1, y1 = r["x0"], r["y0"], r["x1"], r["y1"]
    return {"s": ((x0, y0), (x1, y0)), "e": ((x1, y0), (x1, y1)), "n": ((x1, y1), (x0, y1)), "w": ((x0, y1), (x0, y0))}


def _side_gaps(r, side, zmax):
    """u-intervals (from the side's p0) blocked by openings on that side below zmax (relative to the floor)."""
    p0, p1 = _sides(r)[side]
    L, ux, uy, _ = _dir(p0, p1)
    axis = "x" if abs(ux) > 0.5 else "y"
    gaps = []
    for o in _P["open"]:
        if o["axis"] != axis or o["z0"] - r["z"] > zmax or o["z1"] < r["z"] + 0.05 or o["z0"] > r["zc"]:
            continue
        if axis == "x":
            if not (p0[1] - 1.0 <= o["y"] <= p0[1] + 1.0) or abs(o["y"] - p0[1]) > 0.95:
                continue
            if (o["y"] - p0[1]) * (1 if side == "s" else -1) > 0.05:
                continue
            u = (o["x"] - p0[0]) * ux
        else:
            if abs(o["x"] - p0[0]) > 0.95 or (o["x"] - p0[0]) * (1 if side == "w" else -1) > 0.05:
                continue
            u = (o["y"] - p0[1]) * uy
        if -0.5 < u < L + 0.5:
            gaps.append((u - o["w"] / 2 - 0.12, u + o["w"] / 2 + 0.12))
    for (a, b) in r["gaps"].get(side, ()):
        ua, ub = sorted((_along(p0, ux, uy, a), _along(p0, ux, uy, b)))
        gaps.append((ua, ub))
    return gaps


def _along(p0, ux, uy, v):
    """World coordinate v (x for walls along x, y for walls along y) -> distance from p0 along the side."""
    return (v - p0[0]) * ux if abs(ux) > 0.5 else (v - p0[1]) * uy


def _dress_sides(mb, r, mat, h, depth, cap):
    for side, (p0, p1) in _sides(r).items():
        if side in r["open"]:
            continue
        gaps = _side_gaps(r, side, h)
        K.wainscot(mb, (p0[0], p0[1]), (p1[0], p1[1]), r["z"], h, mat, cap=cap, gaps=gaps) if depth >= 0.024 else \
            _strip(mb, p0, p1, r["z"], h, depth, mat, r, gaps=gaps)


def _strip(mb, p0, p1, z, h, depth, mat, r, ceiling=False, gaps=()):
    L, ux, uy, yaw = _dir(p0, p1)
    with mb.at((p0[0], p0[1], z), rot=yaw):
        u = 0.0
        for a, b in sorted(gaps) + [(L, L)]:
            if a - u > 0.05:
                mb.box(((u + a) / 2, depth / 2, h / 2), (a - u, depth, h), mat)
            u = max(u, b)


# ----------------------------------------------------------------------------- outer walls with real openings
def _ext_walls(aset, mb, segs, bands, T=0.4, outer=WALL, frame=FRAME, sill=MARBLE, trim_in=K.TRIM_GOLD):
    """segs: [(p0, p1, top)] outline of the building (outside on the right). bands: [(za, zb, storey)];
    the last band is stretched to each segment's top. Recorded holes on a segment become openings."""
    for (p0, p1, top) in segs:
        L, ux, uy, yaw = _dir(p0, p1)
        nx, ny = -uy, ux
        holes = []
        for h in _P["holes"]:
            dx, dy = h["x"] - p0[0], h["y"] - p0[1]
            u = dx * ux + dy * uy
            if abs(dx * nx + dy * ny) < 0.03 and -0.01 < u < L + 0.01:
                holes.append(dict(h, u=u))
        for bi, (za, zb, fl) in enumerate(bands):
            if bi == len(bands) - 1:
                zb = top
            if zb <= za + 1e-3:
                continue
            cuts = {0.0, L}
            for r in _P["rooms"]:
                if fl is None or fl not in r["levels"]:
                    continue
                # only rooms that actually touch this wall split it
                if abs(ux) > 0.5:
                    dist = min(abs(r["y0"] - p0[1]), abs(r["y1"] - p0[1]))
                else:
                    dist = min(abs(r["x0"] - p0[0]), abs(r["x1"] - p0[0]))
                if dist > T + 0.3:
                    continue
                for v in ((r["x0"], r["x1"]) if abs(ux) > 0.5 else (r["y0"], r["y1"])):
                    uu = _along(p0, ux, uy, v)
                    if 0.05 < uu < L - 0.05:
                        cuts.add(uu)
            cuts = sorted(cuts)
            for i in range(len(cuts) - 1):
                ua, ub = cuts[i], cuts[i + 1]
                um = (ua + ub) / 2
                room = _room_at(p0[0] + ux * um + nx * (T + 0.2), p0[1] + uy * um + ny * (T + 0.2), fl) \
                    if fl is not None else None
                inner = room["wall"] if room else outer
                ops = []
                mine = [h for h in holes if ua <= h["u"] < ub and za - 1e-3 <= h["z0"] and h["z1"] + h["r"] <= zb + 1e-3]
                for h in mine:
                    ops.append(dict(u=h["u"] - ua, w=h["w"], z0=h["z0"] - za, z1=h["z1"] + h["r"] - za))
                a = (p0[0] + ux * ua, p0[1] + uy * ua)
                b = (p0[0] + ux * ub, p0[1] + uy * ub)
                mb.wall(a, b, za, zb - za, T, outer, ops, inner_mat=inner)
                for h in mine:
                    _dress_hole(aset, mb, p0, yaw, h, T, outer, inner, frame, sill, trim_in, room)


def _dress_hole(aset, mb, p0, yaw, h, T, outer, inner, frame, sill, trim_in, room):
    u, w, z0, z1, r = h["u"], h["w"], h["z0"], h["z1"], h["r"]
    axis = "x" if abs(math.cos(math.radians(yaw))) > 0.5 else "y"
    a = math.radians(yaw)
    wx, wy = p0[0] + math.cos(a) * u - math.sin(a) * T / 2, p0[1] + math.sin(a) * u + math.cos(a) * T / 2
    _open(wx, wy, z0, z1 + r, w, axis)
    with mb.at((p0[0], p0[1], 0.0), rot=yaw):
        if h["kind"] == "door":
            aset.door((wx, wy, z0), yaw, w, z1 - z0, h["style"] or "obelisk", h["double"])
            # threshold (the room floor runs E_IN under the wall, the rest of the depth is marble)
            mb.box_mm((u - w / 2, 0.0, z0 - 0.3), (u + w / 2, T - E_IN, z0), MARBLE, skip=("-z",))
            if trim_in:
                bw = 0.12
                yy = T + 0.015
                mb.box((u - w / 2 - bw / 2, yy, z0 + (z1 - z0 + bw) / 2), (bw, 0.03, z1 - z0 + bw), trim_in)
                mb.box((u + w / 2 + bw / 2, yy, z0 + (z1 - z0 + bw) / 2), (bw, 0.03, z1 - z0 + bw), trim_in)
                mb.box((u, yy, z1 + bw / 2), (w + 2 * bw, 0.03, bw), trim_in)
            return
        g = "M_GlassClear"
        mb.box((u, T / 2, (z0 + z1) / 2), (w, 0.02, z1 - z0), g)
        fw = 0.06
        for s in (-1, 1):
            mb.box((u + s * (w / 2 - fw / 2), T / 2, (z0 + z1) / 2), (fw, 0.08, z1 - z0), frame)
        mb.box((u, T / 2, z0 + fw / 2), (w, 0.08, fw), frame)
        mb.box((u, T / 2, z1 - fw / 2), (w, 0.08, fw), frame)
        if w > 1.0:
            mb.box((u, T / 2, (z0 + z1) / 2), (0.05, 0.07, z1 - z0), frame)
        mb.box((u, T + 0.05, z0 - 0.03), (w + 0.24, 0.14, 0.06), sill)
        if r > 0:
            seg = 8
            arc = [(u + math.cos(math.pi * i / seg) * r, z1 + math.sin(math.pi * i / seg) * r) for i in range(seg + 1)]
            prism_xz(mb, arc, T / 2 - 0.01, T / 2 + 0.01, g)
            for s in (-1, 1):
                corner = (u + s * r, z1 + r)
                pts = arc[: seg // 2 + 1] if s > 0 else arc[seg // 2:]
                for k in range(len(pts) - 1):
                    A, B = pts[k], pts[k + 1]
                    _face(mb, [(corner[0], 0.0, corner[1]), (A[0], 0.0, A[1]), (B[0], 0.0, B[1])], outer, (0, -1, 0))
                    _face(mb, [(corner[0], T, corner[1]), (A[0], T, A[1]), (B[0], T, B[1])], inner, (0, 1, 0))
                    mx, mz = (A[0] + B[0]) / 2, (A[1] + B[1]) / 2
                    _face(mb, [(A[0], 0.0, A[1]), (B[0], 0.0, B[1]), (B[0], T, B[1]), (A[0], T, A[1])], inner,
                          (u - mx, 0, z1 - mz))
            mb.box((u, T / 2, z1), (w, 0.08, 0.05), frame)


# ----------------------------------------------------------------------------- partitions, hollow block parts
def _pw(aset, mb, a, b, z0, z1, t, right, left, doors=(), trim=K.TRIM_GOLD, trim_in=K.TRIM_GOLD):
    """Partition on the CENTRE line a -> b (z0..z1, thickness t); `right` / `left` = finish on each side.
    doors: [(v, w, h, style, double, zfloor)] with v the world x (walls along x) or y (walls along y)."""
    L, ux, uy, yaw = _dir(a, b)
    rx, ry = uy, -ux
    p0 = (a[0] + rx * t / 2, a[1] + ry * t / 2)
    p1 = (b[0] + rx * t / 2, b[1] + ry * t / 2)
    ops = []
    axis = "x" if abs(ux) > 0.5 else "y"
    for (v, w, h, style, double, zf) in doors:
        c = _along(a, ux, uy, v)
        ops.append(K.Door(c, w, h, style, double, z0=zf - z0, trim=trim, trim_in=trim_in))
        cx, cy = a[0] + ux * c, a[1] + uy * c
        _open(cx, cy, zf, zf + h, w, axis)
        # threshold under the part of the wall the room floors do not reach
        if t - 2 * E_IN > 0.01:
            with mb.at((p0[0], p0[1], 0.0), rot=yaw):
                mb.box_mm((c - w / 2, E_IN, zf - 0.3), (c + w / 2, t - E_IN, zf), MARBLE, skip=("-z",))
    K.wall(aset, mb, p0, p1, z0, z1 - z0, t, right, inner=left, openings=ops)


def _base_ring(mb, x0, y0, x1, y1, z0, z1, d, mat, gaps=(), skip=("-z",)):
    """Moulded course around a block (outside only, so the inside stays free): four slabs, optional gaps
    [(side, a, b)] for low doors and the junctions with neighbouring blocks."""
    sides = {"s": (x0 - d, y0 - d, x1 + d, y0), "n": (x0 - d, y1, x1 + d, y1 + d),
             "w": (x0 - d, y0, x0, y1), "e": (x1, y0, x1 + d, y1)}
    for k, (a, b, c, e) in sides.items():
        cuts = sorted((g[1], g[2]) for g in gaps if g[0] == k)
        if k in ("s", "n"):
            u = a
            for (ga, gb) in cuts + [(c, c)]:
                if ga - u > 1e-3:
                    mb.box_mm((u, b, z0), (ga, e, z1), mat, skip=skip)
                u = max(u, gb)
        else:
            u = b
            for (ga, gb) in cuts + [(e, e)]:
                if ga - u > 1e-3:
                    mb.box_mm((a, u, z0), (c, ga, z1), mat, skip=skip)
                u = max(u, gb)


def hollow_shell(mb, x0, y0, x1, y1, top, fl, bands, base=MARBLE, band_mat=TRIM, cornice=(MARBLE, TRIM),
                 pilasters=True, pil_mat=MARBLE, base_band=None, T=0.4, base_gaps=(), joins=()):
    """block_shell() for a walk-in block: same outside, but the walls are built by _ext_walls, the base
    course / string courses are rings of slabs around the walls (left out along `joins` [(side, a, b)], the
    stretches shared with a neighbouring block, so no ledge crosses the doorways there) and the corner
    pilasters are clipped to the wall."""
    _base_ring(mb, x0, y0, x1, y1, -4.0, fl + 0.3, 0.2, base, tuple(base_gaps) + tuple(joins))
    if base_band:
        _base_ring(mb, x0, y0, x1, y1, fl + 0.3, fl + 0.45, 0.24, base_band, joins, skip=())
    for z in bands:
        _base_ring(mb, x0, y0, x1, y1, z - 0.14, z + 0.14, 0.1, band_mat, joins, skip=())
    mb.box_mm((x0 - 0.22, y0 - 0.22, top - 0.95), (x1 + 0.22, y1 + 0.22, top - 0.6), cornice[0], skip=("+z",))
    mb.box_mm((x0 - 0.5, y0 - 0.5, top - 0.6), (x1 + 0.5, y1 + 0.5, top), cornice[1])
    if pilasters:
        tc = T - 0.02
        for (cx, cy, sx, sy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1)):
            for (xa, xb, ya, yb) in ((cx - sx * 0.12, cx + sx * 0.75, cy - sy * 0.12, cy + sy * tc),
                                     (cx - sx * 0.12, cx + sx * tc, cy + sy * tc, cy + sy * 0.75)):
                mb.box_mm((min(xa, xb), min(ya, yb), fl + 0.3), (max(xa, xb), max(ya, yb), top - 0.95), pil_mat,
                          skip=("-z", "+z"))


# ----------------------------------------------------------------------------- stairs, rails, small pieces
def _flight(mb, x, y, z0, z1, yaw, width, run=0.3, mat=MARBLE, carpet=None, cw=None, base=None, nose=None):
    """Solid flight climbing along local +x from the front edge centre (x, y) at z0 up to z1 (risers
    <= 0.185 m). Optional carpet runner (width cw). Returns the run length."""
    n = max(2, math.ceil((z1 - z0) / 0.185 - 1e-6))
    rise = (z1 - z0) / n
    base = z0 - 0.3 if base is None else base
    with mb.at((x, y, 0.0), rot=yaw):
        for i in range(n):
            zt = z0 + rise * (i + 1)
            mb.box_mm((run * i, -width / 2, base), (run * (i + 1), width / 2, zt), mat, skip=("-z",))
            if nose:
                mb.box_mm((run * i - 0.02, -width / 2, zt - 0.03), (run * i + 0.02, width / 2, zt + 0.004), nose)
            if carpet:
                mb.box_mm((run * i + 0.02, -cw / 2, zt), (run * (i + 1), cw / 2, zt + 0.012), carpet, skip=("-z",))
                mb.box_mm((run * i, -cw / 2, zt - rise + 0.01), (run * i + 0.012, cw / 2, zt), carpet, skip=("-z",))
    return run * n


def _rail(mb, p0, p1, post=K.TRIM_GOLD, rail=K.WOOD_DARK, h=0.95, spacing=0.28, newel=None):
    """Balustrade between two 3D points on a floor / stair nosing line (may slope)."""
    L = math.dist(p0[:2], p1[:2])
    n = max(1, int(L / spacing))
    for k in range(n + 1):
        t = k / n
        x, y, z = (p0[i] + (p1[i] - p0[i]) * t for i in range(3))
        mb.box((x, y, z + h / 2), (0.04, 0.04, h), post)
    mb.beam((p0[0], p0[1], p0[2] + h), (p1[0], p1[1], p1[2] + h), 0.09, 0.07, rail)
    mb.beam((p0[0], p0[1], p0[2] + 0.1), (p1[0], p1[1], p1[2] + 0.1), 0.05, 0.05, post)
    if newel:
        for p in (p0, p1):
            mb.box((p[0], p[1], p[2] + (h + 0.1) / 2), (0.16, 0.16, h + 0.1), newel)
            mb.sphere((p[0], p[1], p[2] + h + 0.18), 0.1, post, seg=8, rings=6)


def _plinth_bust(f, mb, x, y, yaw=0.0, mat=MARBLE, cap=K.TRIM_GOLD):
    """Marble plinth with a catalog bust on top (local frame of f, inside `with f:`)."""
    mb.box((x, y, 0.55), (0.5, 0.5, 1.1), mat)
    mb.box((x, y, 1.13), (0.6, 0.6, 0.06), cap)
    f.prop("SM_Int_Bust", x, y, yaw, z=1.16)


def _chandelier(f, x, y, zc, scale=1.0):
    f.prop("SM_Int_Chandelier", x, y, 0.0, z=zc, scale=scale)
    f.nc.cylinder((x, y, zc - 0.012), 0.24 * scale, 0.012, K.TRIM_GOLD, seg=10)


_CANVAS = (("M_IntPlasterSky", "M_IntFabricBlue", "M_IntFabricWhite"),       # sea + sail
           ("M_IntPlasterSky", "M_IntFabricGreen", "M_IntFabricRed"),        # hills + cottage
           ("M_IntFabricNavy", "M_IntFabricNavy", K.TRIM_GOLD),               # crest on navy
           ("M_IntPlasterPeach", "M_IntFabricPurple", "M_IntFabricYellow"))  # sunset


def _portrait(f, x, y, z, side, scale=1.2, kind=None):
    """Gilded painting hung on the wall `side` with its centre line at (x, y), bottom at height z; a simple
    painted canvas fills the catalog frame."""
    f.prop("SM_Int_Painting", x, y, _wall_yaw(side), z=z, scale=scale)
    k = kind if kind is not None else int(abs(x * 7.0 + y * 3.0 + z)) % len(_CANVAS)
    top, low, spot = _CANVAS[k]
    s = scale
    with f.nc.at((x, y, z), rot=_wall_yaw(side)):
        f.nc.box((0.0, -0.006, 0.33 * s), (0.84 * s, 0.008, 0.48 * s), top)
        f.nc.box((0.0, -0.01, 0.2 * s), (0.84 * s, 0.006, 0.22 * s), low)
        if k == 2:
            f.nc.box((0.0, -0.012, 0.33 * s), (0.16 * s, 0.006, 0.26 * s), spot)
            f.nc.box((0.0, -0.012, 0.36 * s), (0.3 * s, 0.006, 0.05 * s), spot)
        else:
            f.nc.box((0.12 * s, -0.012, 0.33 * s), (0.12 * s, 0.006, 0.1 * s), spot)


def _long_table(mb, nc, x, y, length, width, cloth="M_IntFabricWhite", runner=None, mat=K.WOOD_DARK, h=0.76):
    """Banquet table along local x with a draped cloth (local frame)."""
    n = max(1, int(length / 2.2))
    for k in range(n + 1):
        lx = x - length / 2 + 0.15 + (length - 0.3) * k / n
        for sy in (-1, 1):
            mb.box((lx, y + sy * (width / 2 - 0.12), (h - 0.04) / 2), (0.08, 0.08, h - 0.04), mat)
    mb.box((x, y, h - 0.02), (length, width, 0.04), mat)
    nc.box((x, y, h + 0.003), (length + 0.12, width + 0.12, 0.012), cloth)
    for sy in (-1, 1):
        nc.box((x, y + sy * (width / 2 + 0.06), h - 0.12), (length + 0.12, 0.012, 0.24), cloth)
    for sx in (-1, 1):
        nc.box((x + sx * (length / 2 + 0.06), y, h - 0.12), (0.012, width + 0.12, 0.24), cloth)
    if runner:
        nc.box((x, y, h + 0.012), (length - 0.4, width * 0.3, 0.006), runner)


def _place_setting(nc, x, y, yaw, mat="M_IntTrimWhite", rim=K.TRIM_GOLD, h=0.77):
    with nc.at((x, y, h), rot=yaw):
        nc.cylinder((0, 0, 0.0), 0.14, 0.012, rim, seg=10, cap_bottom=False)
        nc.cylinder((0, 0, 0.012), 0.11, 0.004, mat, seg=10, cap_bottom=False)
        nc.box((0.2, 0.0, 0.006), (0.02, 0.18, 0.006), "M_IntMetal", skip=("-z",))
        nc.box((-0.2, 0.0, 0.006), (0.02, 0.18, 0.006), "M_IntMetal", skip=("-z",))
        nc.cylinder((0.16, 0.16, 0.0), 0.03, 0.16, "M_IntGlassClear", seg=6, cap_bottom=False)


def _cabinet_case(mb, nc, x, y, w=1.2, d=0.5, h=1.9, frame=K.WOOD_DARK, glass="M_IntGlassClear", items=None,
                  shelves=3, rng=None):
    """Glass display case (local frame, back at +y) with trophies / card boxes on the shelves."""
    mb.box((x, y, 0.15), (w, d, 0.3), frame)
    mb.box((x, y, h - 0.04), (w + 0.04, d + 0.04, 0.08), frame)
    mb.box((x, y + d / 2 - 0.02, h / 2), (w, 0.04, h), frame)
    for s in (-1, 1):
        mb.box((x + s * (w / 2 - 0.03), y, h / 2), (0.06, d, h), frame)
    mb.box((x, y - d / 2 + 0.01, (h + 0.3) / 2), (w - 0.1, 0.02, h - 0.38), glass)
    for k in range(shelves):
        z = 0.3 + (h - 0.4) * (k + 0.3) / shelves
        mb.box((x, y, z), (w - 0.1, d - 0.08, 0.02), "M_IntGlassClear")
        if items:
            for j in range(2):
                ix = x - w / 4 + w / 2 * j
                items(nc, ix, y, z + 0.01, rng.random() if rng else 0.5)


def _trophy(nc, x, y, z, t=0.5, mat=K.TRIM_GOLD):
    s = 0.8 + t * 0.5
    nc.box((x, y, z + 0.03 * s), (0.12 * s, 0.12 * s, 0.06 * s), K.WOOD_DARK)
    nc.box((x, y, z + 0.11 * s), (0.03 * s, 0.03 * s, 0.1 * s), mat)
    nc.lathe([(0.03 * s, 0.0), (0.09 * s, 0.06 * s), (0.1 * s, 0.14 * s)], mat, 8, cap_top=False,
             center=(x, y, z + 0.16 * s))
    for sx in (-1, 1):
        nc.box((x + sx * 0.11 * s, y, z + 0.24 * s), (0.03 * s, 0.015 * s, 0.07 * s), mat)


def _card_boxes(nc, x, y, z, t=0.5):
    cols = (K.POSTERS[int(t * 4) % 4], "M_IntFabricNavy", K.TRIM_GOLD)
    for k in range(3):
        nc.box((x - 0.12 + k * 0.12, y, z + 0.06), (0.08, 0.06, 0.12), cols[k % 3])


def _vase(nc, x, y, z, s=1.0, mat="M_IntTrimWhite", flowers=("M_FlowerRed", "M_FlowerWhite")):
    nc.lathe([(0.06 * s, 0.0), (0.11 * s, 0.1 * s), (0.07 * s, 0.24 * s), (0.08 * s, 0.3 * s)], mat, 8,
             cap_top=False, center=(x, y, z))
    for k in range(3):
        a = TAU * k / 3
        nc.sphere((x + math.cos(a) * 0.08 * s, y + math.sin(a) * 0.08 * s, z + 0.36 * s), 0.08 * s,
                  flowers[k % len(flowers)], seg=6, rings=4)
    nc.sphere((x, y, z + 0.44 * s), 0.08 * s, flowers[-1], seg=6, rings=4)


def _sconce(f, x, y, z, side):
    """Wall light (gilded bracket + warm glow) on wall `side` of the local frame."""
    with f.nc.at((x, y, z), rot=_wall_yaw(side)):
        f.nc.box((0, -0.05, 0), (0.08, 0.1, 0.2), K.TRIM_GOLD)
        f.nc.cylinder((0, -0.14, 0.02), 0.06, 0.16, K.GLOW, seg=8)
    a = math.radians(_wall_yaw(side))
    f.light(x + math.sin(a) * 0.3, y - math.cos(a) * 0.3, z + 0.1, 900.0, 4.0)


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
                if f1_doors:      # French doors onto the end-pavilion balcony
                    window(mb, u, B_Z1, 1.5, 10.2 - B_Z1, FRAME, head="pediment", head_mat=TRIM, sill_mat=MARBLE,
                           as_door="obelisk")
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
    joins = {"C": [("e", 0.0, 28.0), ("w", 0.0, 28.0)], "WL": [("e", -0.5, 28.5), ("w", -0.5, 28.5)],
             "WR": [("e", -0.5, 28.5), ("w", -0.5, 28.5)], "EL": [("e", 0.0, 28.0)], "ER": [("w", 0.0, 28.0)]}
    for key, (x0, y0, x1, y1, top) in B_BLOCKS.items():
        hollow_shell(mb, x0, y0, x1, y1, top, FL, B_BANDS, base_band=TRIM, joins=joins[key])

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
    # centre block: front behind the portico (GF + F1), back three floors
    with facade(mb, (-13.0, -2.0), (13.0, -2.0)):
        for x in (-9.0, -5.0, 5.0, 9.0):
            window(mb, x + 13.0, 2.65, 1.5, 2.55, FRAME, arch=True, keystone=GOLD, sill_mat=MARBLE)
            window(mb, x + 13.0, 7.65, 1.5, 2.55, FRAME, head="pediment", head_mat=TRIM, sill_mat=MARBLE)
        door(mb, 13.0, FL, 2.8, 3.4, leaf=TRIM, surround=MARBLE, handle=GOLD)
        window(mb, 13.0, 8.6, 1.6, 1.6, FRAME, head="lintel", head_mat=TRIM, sill_mat=MARBLE)
    with facade(mb, (13.0, 30.0), (-13.0, 30.0)):
        for x in (-10.8, -7.2, -3.6, 3.6, 7.2, 10.8):
            u = 13.0 - x
            window(mb, u, 2.65, 1.5, 2.55, FRAME, arch=True, keystone=GOLD, sill_mat=MARBLE)
        for x in (-10.8, -7.2, -3.6, 0.0, 3.6, 7.2, 10.8):
            u = 13.0 - x
            window(mb, u, 7.65, 1.5, 2.55, FRAME, head="pediment", head_mat=TRIM, sill_mat=MARBLE)
            window(mb, u, 12.05, 1.4, 2.1, FRAME, head="lintel", head_mat=TRIM, sill_mat=MARBLE)
        door(mb, 13.0, FL, 2.6, 3.4, leaf=TRIM, surround=MARBLE, handle=GOLD)
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


# ----------------------------------------------------------------------------- boys: walk-in palace
# Storeys: ground floor at B_FL (2.0, the portico level), first floor at B_Z1 (7.05, the end-pavilion balcony
# level), second floor and attics stay closed (their windows remain facade dressing on a solid wall).
B_Z1 = 7.05
B_C0 = 6.74          # ground floor ceilings (just under the first floor slabs)
B_C1 = 11.15         # first floor ceilings
B_BANDS_INT = [(1.7, 6.8, 0), (6.8, 11.2, 1), (11.2, 99.0, None)]
B_DOOR = "obelisk_inner"
NAVY_TXT = (0.12, 0.2, 0.5)


def _boys_faces():
    f = {(-13.0, -2.0, 13.0, -2.0): 11.0, (13.0, 30.0, -13.0, 30.0): 7.0}
    for sx in (-1, 1):
        def X(a, b):
            return (a, b) if sx > 0 else (-b, -a)
        wx0, wx1 = X(13.0, 29.0)
        rf = rect_faces(wx0, 0.0, wx1, 28.0)
        for k in ("front", "back"):
            f[(*rf[k][0], *rf[k][1])] = 11.0
        ex0, ex1 = X(29.0, 41.0)
        rf = rect_faces(ex0, -3.0, ex1, 31.0)
        for k in ("front", "back", "right" if sx > 0 else "left"):
            f[(*rf[k][0], *rf[k][1])] = 11.0
    return f


def _boys_segments():
    right = [((13.0, -2.0), (13.0, 0.0), 17.4), ((13.0, 0.0), (29.0, 0.0), 15.6), ((29.0, 0.0), (29.0, -3.0), 16.6),
             ((29.0, -3.0), (41.0, -3.0), 16.6), ((41.0, -3.0), (41.0, 31.0), 16.6), ((41.0, 31.0), (29.0, 31.0), 16.6),
             ((29.0, 31.0), (29.0, 28.0), 16.6), ((29.0, 28.0), (13.0, 28.0), 15.6), ((13.0, 28.0), (13.0, 30.0), 17.4)]
    left = [((-b[0], b[1]), (-a[0], a[1]), t) for (a, b, t) in right]
    return [((-13.0, -2.0), (13.0, -2.0), 17.4), ((13.0, 30.0), (-13.0, 30.0), 17.4)] + right + left


def _mx(rect, sx):
    x0, y0, x1, y1 = rect
    return rect if sx > 0 else (-x1, y0, -x0, y1)


def _boys_rooms():
    Z0, Z1 = B_FL, B_Z1
    R = {}
    cof = (3.2, K.TRIM_WHITE, K.TRIM_GOLD)
    R["foyer"] = _room("foyer", 0, (-12.6, -1.6, 12.6, 15.8), Z0, B_C1, WALL_IVORY, K.MARBLEFLOOR, levels=(0, 1),
                       dado=(MARBLE, K.TRIM_GOLD), dado_h=0.6, skirting=None, coffer=cof, panels=K.TRIM_GOLD)
    R["library"] = _room("library", 0, (-12.6, 16.2, 12.6, 29.6), Z0, B_C0, "M_IntWoodPanel", "M_IntWoodFloorDark",
                         dado=(K.WOOD_DARK, K.TRIM_GOLD), coffer=(2.8, K.WOOD_DARK, K.TRIM_GOLD), seams=K.WOOD_DARK)
    R["lounge"] = _room("lounge", 0, (-28.6, 0.4, -13.4, 13.9), Z0, B_C0, WALL_NAVY, "M_IntWoodFloorDark",
                        dado=(K.TRIM_WHITE, K.TRIM_GOLD), coffer=cof, panels=K.TRIM_GOLD, seams=K.WOOD_DARK)
    R["music"] = _room("music", 0, (-28.6, 14.1, -13.4, 27.6), Z0, B_C0, WALL_IVORY, K.WOODFLOOR,
                       dado=(K.TRIM_WHITE, K.TRIM_GOLD), coffer=cof, panels=K.TRIM_GOLD, seams=K.WOOD_DARK)
    R["dining"] = _room("dining", 0, (13.4, 0.4, 28.6, 27.6), Z0, B_C0, "M_IntWallpaperBlue", K.MARBLEFLOOR,
                        dado=(K.TRIM_WHITE, K.TRIM_GOLD), coffer=cof, panels=K.TRIM_WHITE)
    R["duel"] = _room("duel", 0, (-40.6, -2.6, -29.4, 12.0), Z0, B_C0, WALL_NAVY, "M_IntCarpetBlue",
                      dado=(K.WOOD_DARK, K.TRIM_GOLD), panels=K.TRIM_GOLD)
    R["trophy"] = _room("trophy", 0, (-40.6, 12.2, -29.4, 30.6), Z0, B_C0, "M_IntWallpaperRed", K.MARBLEFLOOR,
                        dado=(K.WOOD_DARK, K.TRIM_GOLD), coffer=(3.0, K.TRIM_WHITE, K.TRIM_GOLD), panels=K.TRIM_GOLD)
    R["kitchen"] = _room("kitchen", 0, (29.4, -2.6, 40.6, 12.0), Z0, B_C0, K.TILE, "M_IntTileBlue", cornice=K.TRIM_WHITE)
    R["pantry"] = _room("pantry", 0, (29.4, 12.2, 40.6, 30.6), Z0, B_C0, K.PLASTER_CREAM, K.WOODFLOOR,
                        cornice=K.TRIM_WHITE, dado=(K.WOOD, K.TRIM_WOOD), seams=K.WOOD_DARK)
    themes = [WALL_NAVY, "M_IntWallpaperBlue", WALL_IVORY, WALL_NAVY, WALL_IVORY, "M_IntWallpaperBlue"]
    for sx in (-1, 1):
        s = "w" if sx < 0 else "e"
        R["landing_" + s] = _room("landing_" + s, 1, _mx((6.8, 12.2, 12.6, 15.8), sx), Z1, None, WALL_IVORY,
                                  K.MARBLEFLOOR, ceil=None, cornice=None, skirting=None, levels=())
        R["corr_" + s] = _room("corr_" + s, 1, _mx((13.4, 12.2, 28.6, 15.6), sx), Z1, B_C1, WALL_IVORY,
                               K.WOODFLOOR, dado=(K.TRIM_WHITE, K.TRIM_GOLD), dado_h=0.9, seams=K.WOOD_DARK,
                               coffer=(3.4, K.TRIM_WHITE, None))
        R["pcorr_" + s] = _room("pcorr_" + s, 1, _mx((29.4, 12.2, 40.6, 15.6), sx), Z1, B_C1, WALL_IVORY,
                                K.WOODFLOOR, dado=(K.TRIM_WHITE, K.TRIM_GOLD), dado_h=0.9, seams=K.WOOD_DARK,
                                coffer=(3.4, K.TRIM_WHITE, None))
        for i, (k, rect) in enumerate((("A", (13.4, 0.4, 22.5, 12.0)), ("B", (22.7, 0.4, 28.6, 12.0)),
                                       ("C", (13.4, 15.8, 22.5, 27.6)), ("D", (22.7, 15.8, 28.6, 27.6)),
                                       ("SF", (29.4, -2.6, 40.6, 12.0)), ("SB", (29.4, 15.8, 40.6, 30.6)))):
            wall = themes[(i + (3 if sx > 0 else 0)) % len(themes)]
            R[k + "_" + s] = _room(k + "_" + s, 1, _mx(rect, sx), Z1, B_C1, wall,
                                   "M_IntCarpetBlue" if i % 2 else K.WOODFLOOR, dado=(K.TRIM_WHITE, K.TRIM_GOLD),
                                   panels=K.TRIM_GOLD if wall != WALL_IVORY else K.TRIM_WHITE,
                                   seams=None if i % 2 else K.WOOD_DARK)
    return R


def _boys_partitions(aset, mb, R):
    Z0, Z1 = B_FL, B_Z1
    D = B_DOOR
    W = WALL
    for sx in (-1, 1):
        s = "w" if sx < 0 else "e"
        wing0 = R["lounge"]["wall"] if sx < 0 else R["dining"]["wall"]
        wing1 = R["music"]["wall"] if sx < 0 else R["dining"]["wall"]

        def J(x, y0, y1, z0, z1, wing, cside, doors, t=0.8):
            # junction wall on x = sx * x; `wing` = finish on the outer (|x| larger) side
            a, b = ((x, y0), (x, y1)) if sx > 0 else ((-x, y1), (-x, y0))
            _pw(aset, mb, a, b, z0, z1, t, wing, cside, doors)

        # centre block | wing (x = 13)
        J(13.0, 0.0, 14.0, Z0, 6.8, wing0, R["foyer"]["wall"], [(6.5, 2.0, 3.2, D, True, Z0)])
        J(13.0, 14.0, 16.0, Z0, 6.8, wing1, R["foyer"]["wall"], [])
        J(13.0, 16.0, 28.0, Z0, 6.8, wing1, R["library"]["wall"], [(22.5, 1.8, 3.0, D, True, Z0)])
        J(13.0, 0.0, 12.1, 6.8, 11.2, R["A_" + s]["wall"], R["foyer"]["wall"], [])
        J(13.0, 12.1, 15.7, 6.8, 11.2, R["corr_" + s]["wall"], R["foyer"]["wall"],
          [(13.9, 1.6, 2.8, D, True, Z1)])
        J(13.0, 15.7, 16.0, 6.8, 11.2, R["C_" + s]["wall"], R["foyer"]["wall"], [])
        J(13.0, 16.0, 28.0, 6.8, 11.2, R["C_" + s]["wall"], W, [])
        J(13.0, 0.0, 28.0, 11.2, 15.6, W, W, [])
        a, b = ((13.0, 0.0), (13.0, 28.0)) if sx > 0 else ((-13.0, 28.0), (-13.0, 0.0))
        mb.wall(a, b, 15.6, 17.4 - 15.6, 0.4, W)                       # centre block wall above the wing
        # wing | end pavilion (x = 29)
        pav0, pav1 = (R["duel"], R["trophy"]) if sx < 0 else (R["kitchen"], R["pantry"])
        J(29.0, 0.0, 12.1, Z0, 6.8, pav0["wall"], wing0, [(9.0 if sx < 0 else 6.0, 1.8, 3.0, D, True, Z0)])
        if sx < 0:
            J(29.0, 12.1, 14.0, Z0, 6.8, pav1["wall"], R["lounge"]["wall"], [])
            J(29.0, 14.0, 28.0, Z0, 6.8, pav1["wall"], R["music"]["wall"], [(21.0, 1.8, 3.0, D, True, Z0)])
        else:
            J(29.0, 12.1, 28.0, Z0, 6.8, pav1["wall"], R["dining"]["wall"], [(21.0, 1.8, 3.0, D, True, Z0)])
        J(29.0, 0.0, 12.1, 6.8, 11.2, R["SF_" + s]["wall"], R["B_" + s]["wall"], [])
        J(29.0, 12.1, 15.7, 6.8, 11.2, R["pcorr_" + s]["wall"], R["corr_" + s]["wall"],
          [(13.9, 1.6, 2.8, D, True, Z1)])
        J(29.0, 15.7, 28.0, 6.8, 11.2, R["SB_" + s]["wall"], R["D_" + s]["wall"], [])
        J(29.0, 0.0, 28.0, 11.2, 15.6, W, W, [])
        a, b = ((29.0, 28.0), (29.0, 0.0)) if sx > 0 else ((-29.0, 0.0), (-29.0, 28.0))
        mb.wall(a, b, 15.6, 16.6 - 15.6, 0.4, W)                       # end pavilion wall above the wing

        # first floor: corridor walls, room splits (thin partitions, on centre lines)
        def H(y, xa, xb, z0, z1, south, north, doors, t=0.2):
            a, b = (sx * xa, y), (sx * xb, y)
            if sx < 0:
                a, b = b, a
            _pw(aset, mb, a, b, z0, z1, t, south, north, doors)

        H(12.1, 13.4, 22.6, Z1, 11.2, R["A_" + s]["wall"], R["corr_" + s]["wall"], [(sx * 18.0, 1.0, 2.4, D, False, Z1)])
        H(12.1, 22.6, 28.6, Z1, 11.2, R["B_" + s]["wall"], R["corr_" + s]["wall"], [(sx * 25.6, 1.0, 2.4, D, False, Z1)])
        H(15.7, 13.4, 22.6, Z1, 11.2, R["corr_" + s]["wall"], R["C_" + s]["wall"], [(sx * 18.0, 1.0, 2.4, D, False, Z1)])
        H(15.7, 22.6, 28.6, Z1, 11.2, R["corr_" + s]["wall"], R["D_" + s]["wall"], [(sx * 25.6, 1.0, 2.4, D, False, Z1)])
        H(12.1, 29.4, 40.6, Z1, 11.2, R["SF_" + s]["wall"], R["pcorr_" + s]["wall"], [(sx * 35.0, 1.2, 2.5, D, False, Z1)])
        H(15.7, 29.4, 40.6, Z1, 11.2, R["pcorr_" + s]["wall"], R["SB_" + s]["wall"], [(sx * 35.0, 1.2, 2.5, D, False, Z1)])
        for (ya, yb, lo, hi) in ((0.4, 12.0, "A", "B"), (15.8, 27.6, "C", "D")):
            a, b = (sx * 22.6, ya), (sx * 22.6, yb)
            inner_side, outer_side = R[lo + "_" + s]["wall"], R[hi + "_" + s]["wall"]
            if sx > 0:
                _pw(aset, mb, a, b, Z1, 11.2, 0.2, outer_side, inner_side)
            else:
                _pw(aset, mb, a, b, Z1, 11.2, 0.2, inner_side, outer_side)
        # ground floor of the end pavilion: front room | back room
        front, back = (R["duel"], R["trophy"]) if sx < 0 else (R["kitchen"], R["pantry"])
        H(12.1, 29.4, 40.6, Z0, 6.8, front["wall"], back["wall"],
          [(sx * (35.0 if sx < 0 else 38.5), 1.8 if sx < 0 else 1.0, 3.0 if sx < 0 else 2.4, D, sx < 0, Z0)])
    # west wing ground floor: lounge | music room
    _pw(aset, mb, (-28.6, 14.0), (-13.4, 14.0), Z0, 6.8, 0.2, R["lounge"]["wall"], R["music"]["wall"],
        [(-21.0, 2.4, 3.0, D, True, Z0)])
    # centre block: foyer | library (foyer side runs up to the first floor ceiling)
    _pw(aset, mb, (-12.6, 16.0), (12.6, 16.0), Z0, 6.8, 0.4, R["foyer"]["wall"], R["library"]["wall"],
        [(-9.7, 1.8, 3.0, D, True, Z0), (9.7, 1.8, 3.0, D, True, Z0)])
    _pw(aset, mb, (-12.6, 16.0), (12.6, 16.0), 6.8, 11.2, 0.4, R["foyer"]["wall"], W)


def _boys_stairs(aset, mb, nc):
    """Imperial staircase at the back of the foyer: a wide central flight to a half landing against the back
    wall, then two flights along the wall up to the first-floor landings (one per wing)."""
    Z0, Z1 = B_FL, B_Z1
    zm = Z0 + (Z1 - Z0) / 2
    red = "M_IntCarpetRed"
    _flight(mb, 0.0, 8.0, Z0, zm, 90.0, 4.0, carpet=red, cw=2.4, base=Z0, nose=K.TRIM_GOLD)
    mb.box_mm((-2.6, 12.2, Z0), (2.6, 15.8, zm), MARBLE, skip=("-z",), mats={"+z": K.MARBLEFLOOR})
    K.rug(mb, -1.2, 12.2, 1.2, 15.6, zm, red, K.TRIM_GOLD)
    for sx in (-1, 1):
        _flight(mb, sx * 2.6, 14.8, zm, Z1, 0.0 if sx > 0 else 180.0, 2.0, carpet=red, cw=1.3, base=Z0,
                nose=K.TRIM_GOLD)
        # balustrades
        _rail(mb, (sx * 1.95, 8.0, Z0), (sx * 1.95, 12.2, zm), newel=MARBLE)
        _rail(mb, (sx * 2.0, 12.25, zm), (sx * 2.55, 12.25, zm))
        _rail(mb, (sx * 2.55, 12.25, zm), (sx * 2.55, 13.8, zm), newel=MARBLE)
        _rail(mb, (sx * 2.6, 13.85, zm), (sx * 6.8, 13.85, Z1), newel=MARBLE)
        _rail(mb, (sx * 6.85, 12.25, Z1), (sx * 6.85, 13.8, Z1))
        _rail(mb, (sx * 6.85, 12.25, Z1), (sx * 12.55, 12.25, Z1), newel=MARBLE)
        # columns carrying the first-floor landings
        for x in (7.1, 10.0):
            column(mb, sx * x, 12.5, Z0, 0.26, B_C0 - Z0 + 0.01, MARBLE, cap_mat=K.TRIM_GOLD, seg=12)
        mb.box_mm((sx * 6.8 if sx > 0 else -12.6, 12.2, B_C0 - 0.35), (12.6 if sx > 0 else -6.8, 12.5, B_C0 + 0.01),
                  MARBLE)


def _boys_interior(aset, main, mb, nc):
    R = _boys_rooms()
    _ext_walls(aset, main, _boys_segments(), B_BANDS_INT)
    _boys_partitions(aset, mb, R)
    _build_rooms(mb, nc)
    _boys_stairs(aset, mb, nc)
    _boys_furnish(aset, mb, nc, R)


# ----------------------------------------------------------------------------- shared furnishing helpers
def _side_openings(r, side, windows=True, doors=True):
    """[(u, opening)] on a side of room r (u = distance from the side's p0)."""
    p0, p1 = _sides(r)[side]
    L, ux, uy, _ = _dir(p0, p1)
    axis = "x" if abs(ux) > 0.5 else "y"
    out = []
    for o in _P["open"]:
        if o["axis"] != axis or o["z1"] < r["z"] + 0.05 or o["z0"] > r["zc"] - 0.1:
            continue
        is_door = o["z0"] - r["z"] < 0.3
        if (is_door and not doors) or (not is_door and not windows):
            continue
        if axis == "x":
            d = (o["y"] - p0[1]) * (1 if side == "s" else -1)
            u = (o["x"] - p0[0]) * ux
        else:
            d = (o["x"] - p0[0]) * (1 if side == "w" else -1)
            u = (o["y"] - p0[1]) * uy
        if -0.95 <= d <= 0.05 and -0.5 < u < L + 0.5:
            out.append((u, o))
    return out


def _curtains(nc, r, mat, rod=K.TRIM_GOLD, open_frac=0.3):
    """Tied-back drapes on a rod in front of every window of room r (light: two folded panels per side)."""
    for side, (p0, p1) in _sides(r).items():
        L, ux, uy, yaw = _dir(p0, p1)
        for (u, o) in _side_openings(r, side, doors=False):
            z0, z1 = o["z0"] - 0.15, min(o["z1"] + 0.25, r["zc"] - 0.2)
            w = o["w"]
            cw = (w + 0.4) * open_frac
            with nc.at((p0[0], p0[1], 0.0), rot=yaw):
                nc.box((u, 0.12, z1 + 0.04), (w + 0.6, 0.03, 0.03), rod, skip=("-z", "+z"))
                for s_ in (-1, 1):
                    cx = u + s_ * (w / 2 + 0.2 - cw / 2)
                    for k, dy in ((0, -0.02), (1, 0.02)):
                        fx = cx - cw / 4 + k * cw / 2
                        nc.box((fx, 0.12 + dy, (z0 + z1) / 2), (cw / 2 + 0.01, 0.025, z1 - z0), mat,
                               skip=("-z", "+z"))


def _frame_room(aset, mb, nc, r, rot=0.0):
    return Frame(aset, mb, nc, (r["x0"] + r["x1"]) / 2, (r["y0"] + r["y1"]) / 2, r["z"], rot)


def _bedroom(aset, mb, nc, r, door_side, door_v, bed_side, rng, curtain="M_IntFabricNavy", blanket="M_IntFabricNavy",
             label=None, girls=False):
    """Lavish single room. door_side = room side ('n'/'s') holding the entrance (at world x = door_v);
    bed_side = world side ('e'/'w') whose wall takes the headboard."""
    rot = 0.0 if door_side == "n" else 180.0
    f = _frame_room(aset, mb, nc, r, rot)
    W, D = r["x1"] - r["x0"], r["y1"] - r["y0"]
    hw, hd = W / 2, D / 2
    dx = (door_v - f.cx) * (1 if rot == 0 else -1)
    b = (1 if bed_side == "e" else -1) * (1 if rot == 0 else -1)
    bs, os_ = ("e", "w") if b > 0 else ("w", "e")
    zc = r["zc"] - r["z"]
    wood = K.WOOD_DARK if not girls else K.TRIM_WHITE
    with f:
        by = -hd * 0.12
        K.rug(mb, min(b * (hw - 3.4), b * (hw - 0.2)), by - 2.0, max(b * (hw - 3.4), b * (hw - 0.2)), by + 2.0, 0.0,
              "M_IntCarpetRed" if not girls else "M_IntCarpetRose", K.TRIM_GOLD)
        f.prop("SM_Int_GrandBed", b * (hw - 1.2), by, _wall_yaw(bs))
        for s in (-1, 1):
            f.prop("SM_Int_Nightstand" if not girls else "SM_Int_NightstandB", b * (hw - 0.3), by + s * 1.5,
                   _wall_yaw(bs))
            f.prop("SM_Int_OilLamp", b * (hw - 0.3), by + s * 1.5, 0.0, z=0.6)
        _portrait(f, b * hw, by, 1.65, bs, 1.1)
        if girls:     # canopy over the bed
            for sx in (-1, 1):
                for sy in (-1, 1):
                    mb.box((b * (hw - 1.2) + sx * 1.15, by + sy * 1.15, 1.25), (0.07, 0.07, 2.5), K.TRIM_WHITE)
            nc.box((b * (hw - 1.2), by, 2.5), (2.4, 2.4, 0.06), "M_IntFabricPink")
            for sy in (-1, 1):
                nc.box((b * (hw - 1.2), by + sy * 1.2, 2.25), (2.4, 0.02, 0.5), "M_IntFabricPink")
            nc.box((b * (hw - 1.2) - b * 1.2, by, 2.25), (0.02, 2.4, 0.5), "M_IntFabricPink")
        # wardrobe + mirror on the door wall, bed side corner
        f.prop("SM_Int_Wardrobe" if not girls else "SM_Int_Cabinet", b * (hw - 0.9), hd - 0.35, 0.0)
        if abs(b * (hw - 2.3) - dx) > 1.6:
            f.prop("SM_Int_Mirror", b * (hw - 2.3), hd, 0.0, z=0.9)
        if abs(-b * (hw - 0.75) - dx) > 1.7:
            f.prop("SM_Int_Bookshelf" if not girls else "SM_Int_Shelves", -b * (hw - 0.75), hd - 0.2, 0.0)
        # desk near the window on the other side wall
        K.desk(mb, nc, -b * (hw - 0.33), -hd + 1.6, _wall_yaw(os_), w=1.2, d=0.6, top=wood,
               legs=wood, hutch=W > 7.0, rng_seed=rng.randint(0, 99))
        f.prop("SM_Int_OfficeChair" if not girls else "SM_Int_WoodChair", -b * (hw - 1.05), -hd + 1.6,
               _wall_yaw(os_) + 180.0)
        f.prop("SM_Int_DeskLamp", -b * (hw - 0.3), -hd + 1.2, _wall_yaw(os_), z=0.76)
        # sitting corner
        if W > 7.0:
            sx_ = -b * hw * 0.15
            sy_ = -hd + 2.6
            K.rug(mb, sx_ - 1.6, sy_ - 1.2, sx_ + 1.6, sy_ + 1.2, 0.0, "M_IntCarpetBlue" if not girls else "M_IntCarpetYellow",
                  K.TRIM_GOLD)
            f.prop("SM_Int_CoffeeTable", sx_, sy_, 0.0)
            f.prop("SM_Int_Armchair" if not girls else "SM_Int_GreenChair", sx_ - 1.1, sy_, -90.0)
            f.prop("SM_Int_Armchair" if not girls else "SM_Int_GreenChair", sx_ + 1.1, sy_, 90.0)
            f.prop("SM_Int_TeaSet" if girls else "SM_Int_Books", sx_, sy_, 30.0, z=0.45)
        else:
            f.prop("SM_Int_Armchair" if not girls else "SM_Int_GreenChair", b * (hw - 0.7), -hd + 1.3, 220.0 * b)
        f.prop("SM_Int_PottedPlantB", b * (hw - 0.45), -hd + 0.45, 0.0)
        _chandelier(f, 0.0, 0.0, zc, 0.9)
        f.light(0.0, 0.0, zc - 1.2, 1800.0, 7.0)
    _curtains(nc, r, curtain)
    if label:
        # nameplate on the corridor side of the entrance wall
        yy = r["y1"] + 0.2 if door_side == "n" else r["y0"] - 0.2
        K.nameplate(mb, aset, door_v + (0.85 if door_v > 0 else -0.85), yy, r["z"] + 1.55, 180.0 if door_side == "n" else 0.0,
                    label, mat=K.TRIM_GOLD if not girls else "M_IntFabricPink", color=(0.12, 0.1, 0.25), w=0.62, h=0.16)


# ----------------------------------------------------------------------------- boys: rooms
def _boys_furnish(aset, mb, nc, R):
    import random
    rng = random.Random(7)
    _boys_foyer(aset, mb, nc, R["foyer"])
    _boys_library(aset, mb, nc, R["library"])
    _boys_lounge(aset, mb, nc, R["lounge"])
    _boys_music(aset, mb, nc, R["music"])
    _boys_dining(aset, mb, nc, R["dining"])
    _boys_kitchen(aset, mb, nc, R["kitchen"])
    _boys_pantry(aset, mb, nc, R["pantry"])
    _boys_duel(aset, mb, nc, R["duel"])
    _boys_trophy(aset, mb, nc, R["trophy"])
    num = 201
    for sx in (-1, 1):
        s = "w" if sx < 0 else "e"
        _boys_corridor(aset, mb, nc, R["corr_" + s], R["pcorr_" + s], sx)
        inner, outer = ("e", "w") if sx < 0 else ("w", "e")
        for (k, side, dv) in (("A", "n", 18.0), ("B", "n", 25.6), ("C", "s", 18.0), ("D", "s", 25.6)):
            _bedroom(aset, mb, nc, R[k + "_" + s], side, sx * dv, outer if k in ("A", "C") else inner, rng,
                     label=str(num))
            num += 1
        for (k, side, lab) in (("SF", "n", "KING SUITE" if sx > 0 else "EMPEROR SUITE"),
                               ("SB", "s", "ROYAL SUITE" if sx > 0 else "GRAND SUITE")):
            _bedroom(aset, mb, nc, R[k + "_" + s], side, sx * 35.0, inner, rng, label=lab)
    # first-floor balcony of the suites: a couple of chairs outside the French doors
    for sx in (-1, 1):
        for x in (31.0, 39.0):
            aset.prop("SM_Int_WoodChair", (sx * x + sx * 0.0, -4.0, B_Z1), 180.0 + 20.0 * sx)
        aset.prop("SM_Int_SideTable", (sx * 33.0, -4.1, B_Z1), 0.0)
    K.camera(aset, "suite", (36.0, 11.2, B_Z1 + 1.65), (33.0, -2.0, B_Z1 + 1.0), 15.0)
    K.camera(aset, "room201", (-14.0, 11.4, B_Z1 + 1.65), (-21.0, 1.5, B_Z1 + 0.9), 15.0)


def _boys_foyer(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    red = "M_IntCarpetRed"
    with f:
        # navy marble border and the red carpet from the door to the staircase
        for (a, b, c, d) in ((-11.0, -0.4, 11.0, 0.0), (-11.0, 7.6, 11.0, 8.0), (-11.0, -0.4, -10.6, 8.0),
                             (10.6, -0.4, 11.0, 8.0)):
            mb.box_mm((a, b, 0.0), (c, d, 0.004), MARBLE_NAVY, skip=("-z",))
        for (cx, cy) in ((-6.0, 3.8), (6.0, 3.8)):
            mb.prism(circle(24, 1.6, cx, cy), 0.0, 0.004, MARBLE_NAVY, cap_bottom=False)
            mb.slab_ring(circle(24, 1.75, cx, cy), circle(24, 1.6, cx, cy), 0.0, 0.006, K.TRIM_GOLD)
        K.rug(mb, -1.3, -1.55, 1.3, 8.0, 0.006, red, K.TRIM_GOLD)
        # busts guarding the entrance, benches, plants
        for sx in (-1, 1):
            _plinth_bust(f, mb, sx * 3.2, -0.9, 0.0)
            f.prop("SM_Int_Bench", sx * 7.0, -1.25, 180.0)
            f.prop("SM_Int_PottedPlantB", sx * 11.9, -0.9, 0.0)
            f.prop("SM_Int_PottedPlantB", sx * 3.0, 7.6, 0.0)
            # portraits + sconces on the side walls, upper portraits seen from the gallery
            for y in (2.2, 10.6):
                _portrait(f, sx * 12.6, y, 1.6, "e" if sx > 0 else "w", 1.6)
            for y in (3.5, 9.5):
                _portrait(f, sx * 12.6, y, B_Z1 - r["z"] + 1.4, "e" if sx > 0 else "w", 1.8)
            for y in (0.5, 4.4, 8.6):
                _sconce(f, sx * 12.6, y, 2.6, "e" if sx > 0 else "w")
            # under the landings: console + mirror, armchairs
            f.prop("SM_Int_Armchair", sx * 11.6, 13.4, -90.0 * sx)
            f.prop("SM_Int_SideTable", sx * 11.9, 14.6, 0.0)
            f.prop("SM_Int_Candelabra", sx * 11.9, 14.6, 0.0, z=0.6)
            # banners flanking the crest
            nc.box((sx * 4.6, 15.77, 9.6 - r["z"] + 0.0), (1.3, 0.02, 3.6), TRIM)
            nc.box((sx * 4.6, 15.76, 11.35 - r["z"]), (1.4, 0.03, 0.1), K.TRIM_GOLD)
            nc.box((sx * 4.6, 15.76, 9.6 - r["z"] - 1.6), (1.3, 0.03, 0.08), K.TRIM_GOLD)
            with nc.at((sx * 4.6, 15.75, 9.8 - r["z"]), rot_x=90):
                nc.cylinder((0, 0, 0), 0.38, 0.02, K.TRIM_GOLD, seg=14)
        f.prop("SM_Int_GrandfatherClock", -12.25, 4.3, 90.0)
        f.prop("SM_Int_Console", 12.3, 4.3, -90.0)
        f.prop("SM_Int_Candelabra", 12.3, 4.3, -90.0, z=0.85)
        f.prop("SM_Int_Mirror", 12.6, 4.3, -90.0, z=1.2)
        for (x, y, s) in ((0.0, 1.0, 1.8), (0.0, 6.0, 1.8), (-9.6, 6.0, 1.2), (9.6, 6.0, 1.2)):
            _chandelier(f, x, y, zc, s)
        f.light(0.0, 3.5, 5.0, 6000.0, 16.0)
        f.light(0.0, 12.0, 6.5, 3000.0, 10.0)
    emblem(mb, 0.0, 15.79, 9.55, 1.15)
    aset.text("OBELISK BLUE", (0.0, 15.7, 8.05), 0.0, size=0.55, color=GOLD_RGB)
    aset.text("Noblesse oblige - duel with honour", (0.0, 15.7, 7.75), 0.0, size=0.16, color=NAVY_TXT)
    aset.npc((-4.0, 2.5, r["z"]), 30.0, dorm="obelisk", wander=4.0)
    aset.npc((5.0, 5.0, r["z"]), -120.0, dorm="obelisk", wander=4.0)
    K.camera(aset, "foyer", (0.0, -1.0, r["z"] + 1.75), (0.0, 12.0, r["z"] + 3.6), 14.0)
    K.camera(aset, "foyer_landing", (11.8, 15.2, B_Z1 + 1.7), (-3.0, 1.0, r["z"] + 1.2), 15.0)


def _boys_library(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, -3.0, 17.4, 3.0, 28.0, 0.0, "M_IntCarpetBlue", K.TRIM_GOLD)
        # bookshelves along the foyer wall and the side walls
        for x in (-7.5, -6.4, -5.3, -4.2, 4.2, 5.3, 6.4, 7.5):
            f.prop("SM_Int_Bookshelf", x, 16.4, 180.0)
        K.bookcase(mb, nc, 0.0, 16.4, 180.0, w=2.4, h=2.4, shelves=6, rng_seed=3)
        for sx in (-1, 1):
            for y in (17.6, 18.7, 19.8, 25.2, 26.3, 27.4):
                f.prop("SM_Int_Bookshelf", sx * 12.4, y, -90.0 * sx)
            # reading tables with lamps and chairs
            for (y) in (20.6, 24.2):
                f.prop("SM_Int_Table", sx * 6.0, y, 0.0)
                for cx in (-0.55, 0.55):
                    f.prop("SM_Int_DiningChair", sx * 6.0 + cx, y - 0.8, 0.0)
                    f.prop("SM_Int_DiningChair", sx * 6.0 + cx, y + 0.8, 180.0)
                f.prop("SM_Int_DeskLamp", sx * 6.0 + 0.5, y, 180.0, z=0.76)
                f.prop("SM_Int_Books", sx * 6.0 - 0.3, y + 0.1, 10.0, z=0.76)
            # a reading corner by the windows
            f.prop("SM_Int_Armchair", sx * 2.4, 27.9, 180.0 + sx * 25.0)
            _plinth_bust(f, mb, sx * 9.7, 28.9, 180.0)
            _chandelier(f, sx * 6.0, 22.4, zc, 1.0)
            f.prop("SM_Int_PottedPlantB", sx * 12.0, 29.0, 0.0)
        # trophy case and a globe-like display in the middle
        mb.box((0.0, 22.4, 0.45), (1.4, 0.8, 0.9), K.WOOD_DARK)
        mb.box((0.0, 22.4, 0.92), (1.5, 0.9, 0.04), K.TRIM_GOLD)
        nc.sphere((0.0, 22.4, 1.35), 0.4, "M_IntFabricBlue", seg=16, rings=10)
        nc.torus((0.0, 22.4, 1.35), 0.46, 0.025, K.TRIM_GOLD, seg=20, tube_seg=4)
        f.light(0.0, 22.4, 3.0, 2500.0, 10.0)
    aset.text("LIBRARY", (0.0, 16.25, r["z"] + 3.35), 180.0, size=0.3, color=GOLD_RGB)
    _curtains(nc, r, "M_IntFabricRed")
    K.camera(aset, "library", (11.6, 17.0, r["z"] + 1.75), (-4.0, 27.0, r["z"] + 1.0), 15.0)


def random_mod(seed):
    import random
    return random.Random(seed)


def _boys_lounge(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, -27.0, 1.8, -19.0, 8.6, 0.0, "M_IntCarpetRed", K.TRIM_GOLD)
        K.fireplace(mb, nc, f.a, -28.6, 4.8, 90.0, w=2.0, h=1.4, mat=MARBLE)
        _portrait(f, -28.6, 4.8, 1.9, "w", 1.7)
        K.sofa_set(f.a, -22.4, 4.8, -90.0)
        # billiards, and a pair of club chairs by the windows
        K.rug(mb, -19.6, 6.4, -14.6, 11.8, 0.0, "M_IntCarpetBlue", K.TRIM_GOLD)
        _billiard(mb, nc, -17.1, 9.1, 90.0)
        f.prop("SM_Int_Bench", -14.0, 9.1, -90.0)
        f.prop("SM_Int_SofaB", -17.0, 1.25, 0.0)
        f.prop("SM_Int_CoffeeTable", -17.0, 2.7, 0.0)
        f.prop("SM_Int_TeaSet", -17.0, 2.7, 20.0, z=0.45)
        f.prop("SM_Int_Armchair", -15.2, 3.3, 120.0)
        # cabinet, plants, clock, piano corner
        f.prop("SM_Int_DisplayShelves", -26.8, 13.65, 180.0)
        f.prop("SM_Int_DisplayShelves", -15.4, 13.65, 180.0)
        f.prop("SM_Int_PottedPlantB", -28.1, 0.9, 0.0)
        f.prop("SM_Int_PottedPlantB", -13.9, 0.9, 0.0)
        f.prop("SM_Int_GrandfatherClock", -13.65, 2.6, -90.0)
        _chandelier(f, -24.0, 6.2, zc, 1.1)
        _chandelier(f, -16.5, 8.1, zc, 1.1)
        for y in (3.0, 10.0):
            _sconce(f, -13.4, y, 2.4, "e")
    aset.npc((-17.5, 8.0, r["z"]), 90.0, dorm="obelisk", wander=2.0)
    _curtains(nc, r, "M_IntFabricRed")
    K.camera(aset, "lounge", (-14.0, 12.9, r["z"] + 1.75), (-26.0, 3.0, r["z"] + 0.9), 15.0)


def _boys_music(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, -26.6, 17.0, -18.4, 25.6, 0.0, "M_IntCarpetBlue", K.TRIM_GOLD)
        K.piano(mb, nc, -22.5, 22.6, 200.0)
        # music stands
        for (x, y, a) in ((-19.6, 23.4, 120.0), (-19.0, 21.4, 90.0), (-25.4, 19.8, -40.0)):
            with mb.at((x, y, 0.0), rot=a):
                mb.cylinder((0, 0, 0), 0.18, 0.03, K.BLACK, seg=8)
                mb.box((0, 0, 0.6), (0.03, 0.03, 1.2), K.BLACK)
                mb.box((0, 0.0, 1.2), (0.5, 0.03, 0.34), K.BLACK)
            with nc.at((x, y, 0.0), rot=a):
                nc.box((0, -0.025, 1.22), (0.42, 0.01, 0.28), "M_IntPaper")
        # audience chairs
        for i in range(4):
            for j in range(2):
                f.prop("SM_Int_DiningChair", -24.2 + i * 1.0, 17.4 + j * 1.1, 180.0)
        # string quartet corner: chairs + stands in a half circle, a harp
        for k in range(4):
            a = math.radians(200.0 + k * 45.0)
            qx, qy = -16.6 + math.cos(a) * 1.6, 23.4 + math.sin(a) * 1.6
            f.prop("SM_Int_WoodChair", qx, qy, math.degrees(a) + 90.0)
        _harp(mb, nc, -15.2, 25.6, 30.0)
        # sitting group by the front partition, sheet-music shelves along the west wall
        K.rug(mb, -20.0, 14.6, -14.2, 18.4, 0.0, "M_IntCarpetRed", K.TRIM_GOLD)
        f.prop("SM_Int_SofaB", -14.1, 16.6, -90.0)
        f.prop("SM_Int_CoffeeTable", -15.6, 16.6, 0.0)
        f.prop("SM_Int_Armchair", -17.4, 16.0, -110.0)
        f.prop("SM_Int_Armchair", -17.4, 17.6, -70.0)
        for y in (22.6, 23.7, 24.8, 25.9):
            f.prop("SM_Int_Shelves", -28.4, y, 90.0)
        f.prop("SM_Int_DisplayShelves", -14.0, 20.6, -90.0)
        for y in (16.4, 19.2):
            _portrait(f, -28.6, y, 1.7, "w", 1.2)
        f.prop("SM_Int_GrandfatherClock", -28.25, 21.0 - 2.4, 90.0)
        f.prop("SM_Int_PottedPlantB", -28.1, 27.1, 0.0)
        f.prop("SM_Int_PottedPlantB", -13.9, 14.6, 0.0)
        _chandelier(f, -21.0, 21.0, zc, 1.2)
    _curtains(nc, r, "M_IntFabricNavy")
    K.camera(aset, "music", (-14.2, 15.0, r["z"] + 1.75), (-24.0, 24.5, r["z"] + 0.9), 15.0)


def _boys_dining(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, 18.2, 4.6, 23.8, 23.4, 0.0, "M_IntCarpetRed", K.TRIM_GOLD)
        with mb.at((21.0, 14.0, 0.0), rot=90.0), nc.at((21.0, 14.0, 0.0), rot=90.0):
            _long_table(mb, nc, 0.0, 0.0, 14.0, 1.6, runner="M_IntFabricNavy")
        for i in range(13):
            y = 8.0 + i * 1.0
            for sx in (-1, 1):
                f.prop("SM_Int_DiningChair", 21.0 + sx * 1.15, y, 90.0 * sx)
                _place_setting(nc, 21.0 + sx * 0.5, y, 90.0)
            if i % 3 == 0:
                f.prop("SM_Int_Candelabra", 21.0, y + 0.5, 0.0, z=0.78)
            elif i % 3 == 1:
                _vase(nc, 21.0, y + 0.5, 0.78, 0.9, flowers=("M_FlowerWhite", "M_IntFabricBlue"))
        for y in (6.3, 21.7):
            f.prop("SM_Int_Armchair", 21.0, y, 0.0 if y < 10 else 180.0)
            _place_setting(nc, 21.0, y + (0.6 if y < 10 else -0.6), 0.0)
        K.fireplace(mb, nc, f.a, 13.4, 14.5, 90.0, w=2.0, h=1.4, mat=MARBLE)
        _portrait(f, 13.4, 14.5, 1.9, "w", 1.8)
        f.prop("SM_Int_Console", 28.35, 14.0, -90.0)
        f.prop("SM_Int_Candelabra", 28.35, 13.4, -90.0, z=0.85)
        _vase(nc, 28.35, 14.6, 0.85, 1.2, flowers=("M_FlowerWhite", "M_FlowerRed"))
        _portrait(f, 28.6, 14.0, 1.8, "e", 1.8)
        for (x, y) in ((13.9, 0.9), (28.1, 0.9), (13.9, 27.1), (28.1, 27.1)):
            f.prop("SM_Int_PottedPlantB", x, y, 0.0)
        f.prop("SM_Int_GrandfatherClock", 28.3, 10.0, -90.0)
        for y in (8.0, 14.0, 20.0):
            _chandelier(f, 21.0, y, zc, 1.25)
        # after-dinner corner by the front windows
        K.rug(mb, 16.4, 0.9, 25.6, 4.4, 0.0, "M_IntCarpetBlue", K.TRIM_GOLD)
        f.prop("SM_Int_SofaB", 18.2, 2.6, 90.0)
        f.prop("SM_Int_SofaB", 23.8, 2.6, -90.0)
        f.prop("SM_Int_CoffeeTable", 21.0, 2.6, 0.0)
        f.prop("SM_Int_TeaSet", 21.0, 2.6, 0.0, z=0.45)
        _chandelier(f, 21.0, 2.6, zc, 0.9)
        # buffet at the back
        with mb.at((21.0, 26.6, 0.0)), nc.at((21.0, 26.6, 0.0)):
            _long_table(mb, nc, 0.0, 0.0, 5.4, 0.8, runner="M_IntFabricRed")
            for k in range(5):
                if k % 2:
                    _cake_stand(nc, -2.0 + k * 1.0, 0.0, 0.77)
                else:
                    nc.cylinder((-2.0 + k * 1.0, 0.0, 0.77), 0.18, 0.1, K.METAL, seg=10)
                    nc.sphere((-2.0 + k * 1.0, 0.0, 0.87), 0.17, K.METAL, seg=10, rings=6, hemi=True)
        _chandelier(f, 21.0, 25.4, zc, 0.9)
    _curtains(nc, r, "M_IntFabricNavy")
    aset.npc((18.0, 3.0, r["z"]), 40.0, dorm="obelisk", wander=3.0)
    K.camera(aset, "dining", (14.4, 1.4, r["z"] + 1.85), (24.0, 20.0, r["z"] + 0.6), 15.0)


def _boys_kitchen(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        # chequered floor tiles
        for i in range(11):
            for j in range(14):
                if (i + j) % 2 == 0:
                    mb.box_mm((29.4 + i * 1.0 + 0.02, -2.6 + j * 1.04 + 0.02, 0.0), (30.4 + i * 1.0 - 0.02, -1.56 + j * 1.04 - 0.02, 0.003),
                              K.TILE, skip=("-z",))
        K.kitchen_run(mb, nc, 29.6, 12.0, 37.6, against="+y")
        with mb.at((29.4, 0.0, 0.0), rot=90.0), nc.at((29.4, 0.0, 0.0), rot=90.0):
            K.kitchen_run(mb, nc, -2.4, 0.0, 4.0, against="+y", upper=False)
        # central island + stools
        K.counter(mb, 32.4, 3.4, 37.6, 4.6, 0.92, body=K.TRIM_WHITE, top=MARBLE)
        for x in (33.2, 34.4, 35.6, 36.8):
            f.prop("SM_Int_BarStool", x, 2.75, 0.0)
        for (x, a) in ((33.0, 0.0), (35.0, 40.0)):
            nc.cylinder((x, 4.0, 0.92), 0.16, 0.18, K.METAL, seg=12)
        nc.cylinder((36.6, 4.0, 0.92), 0.22, 0.06, "M_IntWood", seg=12)
        for k in range(5):
            nc.sphere((36.5 + 0.08 * (k % 3), 3.95 + 0.07 * (k // 3), 1.0), 0.06, ("M_FlowerRed", "M_IntFabricOrange")[k % 2],
                      seg=8, rings=5)
        f.prop("SM_Int_Stove", 40.2, 8.3, -90.0)
        f.prop("SM_Int_Microwave", 31.0, 11.65, 0.0, z=0.9)
        f.prop("SM_Int_Kettle", 36.4, 11.7, 0.0, z=0.9)
        f.prop("SM_Int_SteelShelves", 33.0, -2.25, 180.0)
        f.prop("SM_Int_SteelShelves", 37.0, -2.25, 180.0)
        f.prop("SM_Int_Extinguisher", 40.3, 11.6, 0.0)
        for (x, y) in ((32.0, 1.0), (37.0, 1.0), (32.0, 7.5), (37.0, 7.5)):
            f.prop("SM_Int_IndustrialLamp", x, y, 0.0, z=zc)
        # chef's pass with plates waiting
        for k in range(4):
            _place_setting(nc, 33.0 + k * 1.2, 4.0, 0.0, h=0.93) if k % 2 else None
    K.nameplate(mb, aset, 28.6, 7.6, r["z"] + 2.0, 90.0, "KITCHEN", mat=K.TRIM_GOLD, color=(0.1, 0.1, 0.3), w=0.9, h=0.2)
    aset.npc((34.5, 6.0, r["z"]), 180.0, dorm="obelisk", wander=2.5)
    K.camera(aset, "kitchen", (40.1, 9.6, r["z"] + 1.75), (30.0, 2.0, r["z"] + 0.8), 15.0)


def _boys_pantry(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    import random
    rng = random.Random(11)
    with f:
        for y in (16.0, 19.0, 22.0):
            f.prop("SM_Int_SteelShelves", 31.6, y, 90.0)
            with mb.at((33.0, y, 0.0), rot=-90.0), nc.at((33.0, y, 0.0), rot=-90.0):
                _store_shelf(mb, nc, rng)
        for y in (16.6, 18.8, 21.0):
            for k in range(2):
                f.prop("SM_Int_Box", 31.0 + k * 0.1, y + k * 0.5, rng.uniform(-15, 15), z=0.0)
        for y in (26.0, 28.4):
            f.prop("SM_Int_Cabinet", 29.75, y, 90.0)
        for k in range(8):
            f.prop("SM_Int_Box", 36.0 + (k % 3) * 0.55, 26.0 + (k // 3) * 0.6, rng.uniform(-20, 20), z=0.0)
        for (x, y) in ((38.8, 18.0), (39.6, 18.6), (38.9, 19.4)):
            mb.cylinder((x, y, 0.0), 0.32, 0.95, K.WOOD, seg=12)
            mb.torus((x, y, 0.2), 0.33, 0.02, K.METAL, seg=12, tube_seg=4)
            mb.torus((x, y, 0.75), 0.33, 0.02, K.METAL, seg=12, tube_seg=4)
        f.prop("SM_Int_Table", 35.5, 21.5, 90.0)
        f.prop("SM_Int_Basket", 35.4, 21.0, 0.0, z=0.76)
        f.prop("SM_Int_Basket", 35.6, 22.2, 40.0, z=0.76)
        f.prop("SM_Int_Bucket", 37.0, 23.6, 0.0)
        f.prop("SM_Int_HandTruck", 39.8, 29.6, 200.0)
        f.prop("SM_Int_Stool", 36.6, 21.0, 0.0)
        for (x, y) in ((33.0, 17.5), (33.0, 24.0), (37.5, 20.0), (36.0, 28.0)):
            f.prop("SM_Int_IndustrialLamp", x, y, 0.0, z=zc)
    K.camera(aset, "pantry", (39.8, 13.0, r["z"] + 1.75), (32.0, 25.0, r["z"] + 0.8), 15.0)


def _harp(mb, nc, x, y, yaw, h=1.75):
    """Concert harp: gilded column, curved neck, sound box and strings (local frame of the caller)."""
    with mb.at((x, y, 0.0), rot=yaw), nc.at((x, y, 0.0), rot=yaw):
        mb.box((0.0, 0.0, 0.06), (0.5, 0.36, 0.12), K.TRIM_GOLD)
        mb.cylinder((-0.2, 0.0, 0.12), 0.04, h - 0.2, K.TRIM_GOLD, seg=8)
        mb.beam((0.2, 0.0, 0.12), (-0.05, 0.0, h - 0.35), 0.2, 0.14, K.WOOD)
        pts = [(-0.2, h - 0.08), (0.0, h - 0.15), (0.15, h - 0.3), (0.05, h - 0.45), (-0.05, h - 0.35)]
        for i in range(len(pts) - 1):
            mb.beam((pts[i][0], 0.0, pts[i][1]), (pts[i + 1][0], 0.0, pts[i + 1][1]), 0.07, 0.06, K.TRIM_GOLD)
        for k in range(9):
            t = (k + 0.5) / 9
            xb, zb = 0.2 - 0.25 * t, 0.14 + (h - 0.5) * t
            nc.beam((xb - 0.06, 0.0, zb), (-0.18 + 0.33 * t, 0.0, h - 0.12 - 0.3 * t), 0.006, 0.006, "M_IntPaper")


def _billiard(mb, nc, x, y, yaw, L=2.7, W=1.5):
    """Billiard table along local x: carved dark frame, green cloth, pockets, racked balls and two cues."""
    with mb.at((x, y, 0.0), rot=yaw), nc.at((x, y, 0.0), rot=yaw):
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * (L / 2 - 0.2), sy * (W / 2 - 0.2), 0.33), (0.16, 0.16, 0.66), K.WOOD_DARK)
        mb.box((0, 0, 0.72), (L, W, 0.14), K.WOOD_DARK)
        mb.box((0, 0, 0.795), (L - 0.24, W - 0.24, 0.012), "M_IntFabricGreen")
        for sx in (-1, 1):
            mb.box((sx * (L / 2 - 0.08), 0, 0.82), (0.16, W, 0.06), K.WOOD_DARK)
        for sy in (-1, 1):
            mb.box((0, sy * (W / 2 - 0.08), 0.82), (L, 0.16, 0.06), K.WOOD_DARK)
        mb.box((0, 0, 0.66), (L + 0.04, W + 0.04, 0.03), K.TRIM_GOLD)
        for px in (-1, 0, 1):
            for sy in (-1, 1):
                nc.box((px * (L / 2 - 0.14), sy * (W / 2 - 0.14), 0.803), (0.1, 0.1, 0.004), K.BLACK)
        cols = ("M_IntFabricYellow", "M_IntFabricBlue", "M_IntFabricRed", "M_IntFabricPurple", "M_IntFabricOrange",
                "M_IntFabricGreen", K.BLACK, "M_IntFabricRed", "M_IntFabricYellow", "M_IntFabricBlue")
        k = 0
        for row in range(4):
            for j in range(row + 1):
                nc.sphere((0.5 + row * 0.052, (j - row / 2) * 0.06, 0.83), 0.028, cols[k % len(cols)], seg=6, rings=4)
                k += 1
        nc.sphere((-0.6, 0.05, 0.83), 0.028, "M_IntFabricWhite", seg=6, rings=4)
        nc.beam((-1.0, -0.3, 0.84), (0.2, -0.45, 0.84), 0.025, 0.025, K.WOOD)
        nc.beam((L / 2 + 0.1, W / 2 - 0.1, 0.0), (L / 2 + 0.16, W / 2 - 0.3, 1.45), 0.025, 0.025, K.WOOD)


def _store_shelf(mb, nc, rng, w=1.8, d=0.5, h=2.0, shelves=4):
    """Pantry shelving (back at local +y) stocked with jars, tins and sacks."""
    mb.box((0, d / 2 - 0.01, h / 2), (w, 0.02, h), K.WOOD)
    for s in (-1, 1):
        mb.box((s * (w / 2 - 0.02), 0, h / 2), (0.04, d, h), K.WOOD)
    for k in range(shelves):
        z = 0.08 + (h - 0.1) * k / (shelves - 1) if k else 0.08
        mb.box((0, 0, z), (w - 0.04, d, 0.03), K.WOOD)
        if k == shelves - 1:
            continue
        x = -w / 2 + 0.12
        while x < w / 2 - 0.15:
            kind = rng.random()
            if kind < 0.5:
                nc.cylinder((x, -0.05, z + 0.015), 0.06, 0.18, ("M_IntGlassClear", "M_IntFabricOrange", "M_IntFabricRed")[k % 3],
                            seg=6, cap_bottom=False)
                x += 0.15
            elif kind < 0.8:
                nc.box((x + 0.06, -0.02, z + 0.12), (0.2, 0.3, 0.21), "M_IntPaper" if k % 2 else "M_IntCork")
                x += 0.26
            else:
                nc.box((x + 0.1, -0.02, z + 0.1), (0.26, 0.32, 0.17), "M_IntFabricBeige")
                x += 0.3


def _duel_table(mb, nc, f, x, y, yaw, L=2.6, W=1.2):
    """Duel table: dark wood frame, glowing blue mat with card zones, a chair at each end."""
    with mb.at((x, y, 0.0), rot=yaw), nc.at((x, y, 0.0), rot=yaw):
        mb.box((0, 0, 0.42), (L - 0.3, W - 0.3, 0.84), K.WOOD_DARK)
        mb.box((0, 0, 0.86), (L, W, 0.06), K.WOOD_DARK)
        mb.box((0, 0, 0.895), (L - 0.12, W - 0.12, 0.012), "M_IntCarpetBlue")
        nc.box((0, 0, 0.903), (L - 0.3, W - 0.3, 0.006), "M_ObIntDuelMat")
        for s in (-1, 1):
            for k in range(5):
                for row, mat in ((0.28, "M_IntPaper"), (0.62, K.TRIM_GOLD)):
                    nc.box((s * row, (k - 2) * 0.18, 0.909), (0.13, 0.1, 0.004), mat)
            nc.box((s * (L / 2 - 0.25), 0.4, 0.92), (0.1, 0.14, 0.04), K.POSTERS[1 if s > 0 else 0])
        nc.box((0, 0, 0.91), (0.03, W - 0.3, 0.004), K.TRIM_GOLD)
    for s in (-1, 1):
        a = math.radians(yaw)
        f.prop("SM_Int_DiningChair", x + math.cos(a) * s * (L / 2 + 0.45), y + math.sin(a) * s * (L / 2 + 0.45),
               yaw + (90.0 if s > 0 else -90.0))


def _boys_duel(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, -38.4, 0.0, -31.6, 9.0, 0.0, "M_IntCarpetRed", K.TRIM_GOLD)
        _duel_table(mb, nc, f, -35.0, 2.6, 0.0)
        _duel_table(mb, nc, f, -35.0, 6.8, 0.0)
        K.blackboard(mb, nc, f.a, -29.4, 2.4, 1.0, -90.0, w=3.0, h=1.2, frame=K.WOOD_DARK,
                     lines=("TODAY'S MATCH-UPS", "Chain resolution: last in, first out", "Fusion > Ritual?"))
        with mb.at((-29.9, 5.6, 0.0), rot=-90.0), nc.at((-29.9, 5.6, 0.0), rot=-90.0):
            _cabinet_case(mb, nc, 0.0, 0.0, 1.4, 0.5, 1.9, items=_card_boxes, rng=random_mod(3))
        f.prop("SM_Int_Console", -40.35, 4.6, 90.0)
        f.prop("SM_Int_TV", -40.35, 4.6, 90.0, z=0.85)
        f.prop("SM_Int_Armchair", -38.9, 9.8, 230.0)
        f.prop("SM_Int_Armchair", -31.2, 9.8, 130.0)
        f.prop("SM_Int_PottedPlantB", -40.1, 11.5, 0.0)
        f.prop("SM_Int_PottedPlantB", -29.9, -2.1, 0.0)
        _chandelier(f, -35.0, 2.6, zc, 1.0)
        _chandelier(f, -35.0, 6.8, zc, 1.0)
    aset.interact("info", (-35.0, 4.7, r["z"] + 1.0), 0.0, title="Duel Salon",
                  text="Obelisk Blue's private duel salon. Only the elite may sit at these tables - "
                       "and the losers polish the trophies next door.")
    K.nameplate(mb, aset, -28.6, 10.5, r["z"] + 2.0, -90.0, "DUEL SALON", mat=K.TRIM_GOLD, color=(0.1, 0.1, 0.3),
                w=1.1, h=0.2)
    aset.npc((-35.0 - 1.75, 2.6, r["z"]), -90.0, dorm="obelisk", wander=0.5)
    aset.npc((-35.0 + 1.75, 2.6, r["z"]), 90.0, dorm="obelisk", wander=0.5)
    _curtains(nc, r, "M_IntFabricRed")
    K.camera(aset, "duel_salon", (-30.0, 11.4, r["z"] + 1.8), (-37.5, 1.0, r["z"] + 0.6), 15.0)


def _boys_trophy(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, -36.4, 13.4, -33.6, 29.6, 0.0, "M_IntCarpetBlue", K.TRIM_GOLD)
        rng = random_mod(9)
        for (y0, n) in ((14.3, 3), (23.2, 3)):
            for k in range(n):
                with mb.at((-29.95, y0 + k * 1.5, 0.0), rot=-90.0), nc.at((-29.95, y0 + k * 1.5, 0.0), rot=-90.0):
                    _cabinet_case(mb, nc, 0.0, 0.0, 1.4, 0.5, 2.0, items=_trophy, rng=rng)
        for y in (15.0, 19.5, 24.0):
            _plinth_bust(f, mb, -37.6, y, -90.0)
        # the great trophy on a pedestal
        mb.box((-35.0, 26.0, 0.5), (1.2, 1.2, 1.0), MARBLE)
        mb.box((-35.0, 26.0, 1.03), (1.3, 1.3, 0.06), K.TRIM_GOLD)
        _trophy(nc, -35.0, 26.0, 1.06, 2.2)
        f.light(-35.0, 26.0, 2.6, 1500.0, 5.0)
        for y in (16.0, 21.0, 26.0):
            _chandelier(f, -35.0, y, zc, 1.0)
        f.prop("SM_Int_PottedPlantB", -40.1, 30.1, 0.0)
        f.prop("SM_Int_PottedPlantB", -29.9, 30.1, 0.0)
    aset.text("CHAMPIONS OF OBELISK BLUE", (-35.0, 25.38, r["z"] + 0.55), 0.0, size=0.08, color=GOLD_RGB)
    _curtains(nc, r, "M_IntFabricNavy")
    K.camera(aset, "trophy", (-35.0, 12.9, r["z"] + 1.75), (-35.0, 28.0, r["z"] + 1.0), 15.0)


def _boys_corridor(aset, mb, nc, r, rp, sx):
    for rr in (r, rp):
        f = Frame(aset, mb, nc, 0.0, 0.0, rr["z"])
        zc = rr["zc"] - rr["z"]
        with f:
            yc = (rr["y0"] + rr["y1"]) / 2
            K.rug(mb, rr["x0"] + 0.4, yc - 0.8, rr["x1"] - 0.4, yc + 0.8, 0.0, "M_IntCarpetRed", K.TRIM_GOLD)
            n = max(2, int((rr["x1"] - rr["x0"]) / 4.0))
            for k in range(n):
                x = rr["x0"] + (rr["x1"] - rr["x0"]) * (k + 0.5) / n
                f.prop("SM_Int_CeilingLamp", x, yc, 0.0, z=zc)
        _curtains(nc, rr, "M_IntFabricNavy")
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    with f:
        # portraits and busts between the room doors
        for x in (15.6, 21.0, 27.6):
            _portrait(f, sx * x, 15.6, 1.4, "n", 1.0)
        for x in (21.0,):
            _portrait(f, sx * x, 12.2, 1.4, "s", 1.0)
        f.prop("SM_Int_Console", sx * 15.3, 12.45, 180.0)
        _vase(nc, sx * 15.3, 12.45, 0.85, 1.1, flowers=("M_FlowerWhite", "M_IntFabricBlue"))
        f.prop("SM_Int_PottedPlantB", sx * 40.1, 12.7, 0.0)
        f.prop("SM_Int_Console", sx * 37.8, 15.35, 0.0)
        f.prop("SM_Int_Candelabra", sx * 37.8, 15.35, 0.0, z=0.85)
    if sx < 0:
        K.camera(aset, "corridor", (-13.8, 13.0, r["z"] + 1.7), (-40.0, 14.4, r["z"] + 1.2), 18.0)


def build_boys():
    aset = AssetSet("obelisk_boys")
    main = aset.mesh("ObeliskBoys_Main")
    yard = aset.mesh("ObeliskBoys_Courtyard")
    gate = aset.mesh("ObeliskBoys_Gate")
    nc = aset.mesh("ObeliskBoys_NoCol")
    inner = aset.mesh("ObeliskBoys_Interior")
    inc = aset.mesh("ObeliskBoys_Interior_NoCol")
    _plan_reset(_boys_faces())
    try:
        _boys_building(main, nc, aset)
        _boys_interior(aset, main, inner, inc)
    finally:
        _plan_end()
    _boys_courtyard(yard, nc, aset)
    _boys_gate(gate, nc, aset)
    _ext_cams(aset, "boys")
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


def _turret(mb, cx, cy, r, angles, top=15.2, roof_h=8.6, hollow=False):
    """Round corner turret. hollow=True: the two lower storeys are built as a thick ring wall with real
    windows elsewhere (_girls_turrets_inside); here only the upper wall, rings and the roof."""
    mb.lathe([(r, 9.2 if hollow else -4.0), (r, top)], WALL, 28, cap_top=False, cap_bottom=False, center=(cx, cy, 0.0))
    lathe_crisp(mb, [(r + 0.2, -4.0), (r + 0.2, G_FL + 0.3), (r + 0.05, G_FL + 0.45)], MARBLE, 28,
                center=(cx, cy, 0.0))
    for z in G_BANDS:
        lathe_crisp(mb, [(r + 0.1, z - 0.14), (r + 0.1, z + 0.14)], GTRIM, 28, center=(cx, cy, 0.0),
                    cap_top=not hollow, cap_bottom=not hollow)
        if hollow:      # annular caps instead of discs, so the rooms inside stay free
            mb.slab_ring(circle(28, r + 0.1, cx, cy), circle(28, r, cx, cy), z - 0.14, z + 0.14, GTRIM)
    lathe_crisp(mb, [(r + 0.05, top - 0.9), (r + 0.2, top - 0.6), (r + 0.45, top - 0.35), (r + 0.45, top)],
                GTRIM, 28, center=(cx, cy, 0.0), cap_bottom=True)
    mb.lathe([(r + 0.75, top - 0.05), (r + 0.5, top + 0.4), (r * 0.62, top + roof_h * 0.45),
              (r * 0.2, top + roof_h * 0.88), (0.08, top + roof_h)], GROOF, 28, cap_bottom=True,
             center=(cx, cy, 0.0))
    finial(mb, cx, cy, top + roof_h - 0.15, 1.3)
    for a_deg in angles:
        a = math.radians(a_deg)
        with mb.at((cx + math.cos(a) * r, cy + math.sin(a) * r, 0.0), rot=a_deg + 90):
            window(mb, 0.0, 1.85, 1.0, 2.6, GTRIM, arch=True, keystone=GTRIM, sill_mat=MARBLE, seg=6,
                   rect_glass=not hollow)
            window(mb, 0.0, 6.0, 1.0, 2.3, GTRIM, arch=True, sill_mat=MARBLE, seg=6, rect_glass=not hollow)
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
    hollow_shell(mb, x0, y0, x1, y1, G_TOP, FL, G_BANDS, band_mat=GTRIM, cornice=(MARBLE, GTRIM),
                 pilasters=False, base_gaps=_girls_base_gaps())
    px0, py0, px1, py1, ptop = G_PAV
    hollow_shell(mb, px0, py0, px1, py1, ptop, FL, G_BANDS, band_mat=GTRIM, cornice=(MARBLE, GTRIM),
                 joins=[("w", 4.0, 26.0), ("e", 4.0, 26.0)])
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
        _turret(mb, tx, ty, G_TURRET_R, angs, hollow=True)
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
        door(mb, 7.0, FL, 2.2, 2.9, leaf=WALL, surround=GTRIM, handle=GOLD, panel_mat=GTRIM, fan=False, style="girls")
        window(mb, 7.0, G_Z1, 1.5, 8.52 - G_Z1, GTRIM, head="pediment", head_mat=GTRIM, sill_mat=MARBLE,
               as_door="girls")         # French door onto the porch balcony
        window(mb, 7.0, 10.0, 1.4, 1.9, GTRIM, arch=True, keystone=GOLD, sill_mat=MARBLE)
    with facade(mb, (x1, y1), (x0, y1)):
        for x in (-17.0, -12.9, -8.9, 8.9, 12.9, 17.0):
            for row in ("gf", "f1", "f2"):
                _g_window(mb, x1 - x, row, nc, flowers=fl)
    with facade(mb, (px1, py1), (px0, py1)):
        for x in (-4.4, 0.0, 4.4):
            for row in (("f1", "f2") if x == 0.0 else ("gf", "f1", "f2")):
                _g_window(mb, px1 - x, row, nc, flowers=fl2)
        door(mb, px1, FL, 2.0, 2.8, leaf=WALL, surround=GTRIM, handle=GOLD, panel_mat=GTRIM, fan=False, style="girls")
    with facade(mb, (x0, y1), (x0, y0)):  # west (conservatory side: ground floor hidden)
        for y in (9.6, 13.1, 16.6, 20.1):
            _g_window(mb, y1 - y, "f1", nc, flowers=fl2)
            _g_window(mb, y1 - y, "f2")
        door(mb, y1 - 15.0, 0.15, 1.8, 2.7, leaf=WALL, surround=GTRIM, handle=GOLD, panel_mat=GTRIM, fan=False,
             style="girls")     # conservatory -> garden hall (steps up inside)
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
    sw = 4.35                                              # half width of the front steps
    for (a, b) in (((tx0 - 0.12, ty0 - 0.12), (-sw, ty0)), ((sw, ty0 - 0.12), (tx1 + 0.12, ty0)),
                   ((tx0 - 0.12, ty0), (tx0, ty1)), ((tx1, ty0), (tx1 + 0.12, ty1))):  # pink coping strips
        mb.box_mm((a[0], a[1], FL - 0.22), (b[0], b[1], FL), GTRIM)
    mb.box_mm((tx0 - 0.15, ty0 - 0.15, -4.0), (tx1 + 0.15, ty1, 0.3), MARBLE, skip=("-z",))
    flight(mb, (0.0, ty0 - 5 * 0.5, 0.0), 90, 2 * sw, 5, 0.24, 0.5, MARBLE)
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
        xa, xb = sorted((sx * sw, sx * (sw + 0.5)))
        mb.box_mm((xa, ty0 - 2.6, -0.5), (xb, ty0, FL - 0.1), WALL, skip=("-z",))
        xa, xb = sorted((sx * (sw - 0.02), sx * (sw + 0.56)))
        mb.box_mm((xa, ty0 - 2.65, FL - 0.1), (xb, ty0 - 0.12, FL), GTRIM)
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
            mb.box_mm((x - 0.08, -L, dz - 0.34), (x + 0.08, 0.0, dz - 0.08), PIER)
        for x in (-2.8, -2.0, 2.0, 2.8):
            mb.box_mm((x - 0.08, -L, dz - 0.34), (x + 0.08, head, dz - 0.08), PIER)
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


# ----------------------------------------------------------------------------- girls: walk-in mansion
# Ground floor at G_FL (1.2, the terrace level), first floor at G_Z1 (5.6, the porch balcony level). The
# round corner turrets open into the corner rooms of both storeys; the attic storey stays closed.
G_Z1 = 5.6
G_C0 = 5.24
G_C1 = 9.15
G_BANDS_INT = [(-0.3, 5.35, 0), (5.35, 9.2, 1), (9.2, 99.0, None)]
G_RT = 0.4           # turret wall thickness
G_DOOR = "girls_inner"
PINK_TXT = (0.85, 0.35, 0.5)
G_TURRET_OPEN = {(-22.0, 4.0): (90.0, 360.0), (22.0, 4.0): (-180.0, 90.0), (-22.0, 26.0): (0.0, 270.0),
                 (22.0, 26.0): (-90.0, 180.0)}


def _girls_faces():
    x0, y0, x1, y1 = G_MAIN
    px0, py0, px1, py1, _ = G_PAV
    f = {}
    for (a, b) in (((x0, y0), (x1, y0)), ((px0, py0), (px1, py0)), ((x1, y1), (x0, y1)), ((px1, py1), (px0, py1)),
                   ((x0, y1), (x0, y0)), ((x1, y0), (x1, y1))):
        f[(*a, *b)] = 9.0
    return f


def _girls_segments():
    rr = G_TURRET_R - G_RT
    m, p = 13.6, 14.4
    return [((-22.0 + rr, 4.0), (-7.0, 4.0), m), ((-7.0, 4.0), (-7.0, 1.0), p), ((-7.0, 1.0), (7.0, 1.0), p),
            ((7.0, 1.0), (7.0, 4.0), p), ((7.0, 4.0), (22.0 - rr, 4.0), m), ((22.0, 4.0 + rr), (22.0, 26.0 - rr), m),
            ((22.0 - rr, 26.0), (7.0, 26.0), m), ((7.0, 26.0), (7.0, 27.0), p), ((7.0, 27.0), (-7.0, 27.0), p),
            ((-7.0, 27.0), (-7.0, 26.0), p), ((-7.0, 26.0), (-22.0 + rr, 26.0), m),
            ((-22.0, 26.0 - rr), (-22.0, 4.0 + rr), m)]


def _girls_base_gaps():
    rr = G_TURRET_R - G_RT
    g = []
    for side in ("s", "n"):
        g += [(side, -22.3, -22.0 + rr), (side, -7.0, 7.0), (side, 22.0 - rr, 22.3)]
    for side in ("w", "e"):
        g += [(side, 3.7, 4.0 + rr), (side, 26.0 - rr, 26.3)]
    g.append(("w", 14.05, 15.95))
    return g


def _ring_point(cx, cy, r, seg, phi):
    """Point at angle phi (deg) on the regular seg-gon of radius r (vertices at multiples of 360/seg)."""
    step = 360.0 / seg
    i = math.floor(phi / step + 1e-9)
    a0, a1 = math.radians(i * step), math.radians((i + 1) * step)
    p0 = (math.cos(a0) * r, math.sin(a0) * r)
    p1 = (math.cos(a1) * r, math.sin(a1) * r)
    d = (math.cos(math.radians(phi)), math.sin(math.radians(phi)))
    # intersect ray t*d with segment p0 + s (p1 - p0)
    ex, ey = p1[0] - p0[0], p1[1] - p0[1]
    den = d[0] * ey - d[1] * ex
    t = (p0[0] * ey - p0[1] * ex) / den if abs(den) > 1e-12 else r
    return (cx + d[0] * t, cy + d[1] * t)


def _ring_wall(mb, cx, cy, r, T, a0, a1, z0, z1, outer, inner, wins, seg=28, frame=GTRIM, sill=MARBLE):
    """Thick round wall (outer face = the turret's 28-gon) from angle a0 to a1 (deg, CCW) between z0 and z1.
    wins: [(angle, width, zs, ze)] real window openings (radial reveals, clear glass at mid thickness)."""
    step = 360.0 / seg
    br = {a0, a1}
    k = math.ceil(a0 / step - 1e-9)
    while k * step < a1 - 1e-9:
        br.add(k * step)
        k += 1
    edges = []
    for (a, w, zs, ze) in wins:
        d = math.degrees(math.atan((w / 2) / r))
        edges.append((a - d, a + d, zs, ze))
        br.update((a - d, a + d))
    br = sorted(b for b in br if a0 - 1e-9 <= b <= a1 + 1e-9)
    ri = (r - T) / r
    for i in range(len(br) - 1):
        t0, t1 = br[i], br[i + 1]
        tm = (t0 + t1) / 2
        o0, o1 = _ring_point(cx, cy, r, seg, t0 + 1e-7), _ring_point(cx, cy, r, seg, t1 - 1e-7)
        i0 = (cx + (o0[0] - cx) * ri, cy + (o0[1] - cy) * ri)
        i1 = (cx + (o1[0] - cx) * ri, cy + (o1[1] - cy) * ri)
        holes = sorted((zs, ze) for (ea, eb, zs, ze) in edges if ea - 1e-6 <= tm <= eb + 1e-6)
        pieces, z = [], z0
        for (zs, ze) in holes:
            pieces.append((z, zs))
            z = ze
        pieces.append((z, z1))
        for (za, zb) in pieces:
            if zb - za < 1e-4:
                continue
            mb.quad((o0[0], o0[1], za), (o1[0], o1[1], za), (o1[0], o1[1], zb), (o0[0], o0[1], zb), outer)
            mb.quad((i1[0], i1[1], za), (i0[0], i0[1], za), (i0[0], i0[1], zb), (i1[0], i1[1], zb), inner)
            if za > z0 + 1e-4:      # head of an opening below this piece
                mb.quad((o0[0], o0[1], za), (i0[0], i0[1], za), (i1[0], i1[1], za), (o1[0], o1[1], za), inner)
            if zb < z1 - 1e-4:      # sill of an opening above this piece
                mb.quad((o0[0], o0[1], zb), (o1[0], o1[1], zb), (i1[0], i1[1], zb), (i0[0], i0[1], zb), MARBLE)
        for (zs, ze) in holes:      # glass at mid thickness, both faces
            m0 = ((o0[0] + i0[0]) / 2, (o0[1] + i0[1]) / 2)
            m1 = ((o1[0] + i1[0]) / 2, (o1[1] + i1[1]) / 2)
            mb.quad((m0[0], m0[1], zs), (m1[0], m1[1], zs), (m1[0], m1[1], ze), (m0[0], m0[1], ze), "M_GlassClear")
            mb.quad((m1[0], m1[1], zs), (m0[0], m0[1], zs), (m0[0], m0[1], ze), (m1[0], m1[1], ze), "M_GlassClear")
    for (ea, eb, zs, ze) in edges:  # radial reveals
        for (ang, sgn) in ((ea, 1), (eb, -1)):
            o = _ring_point(cx, cy, r, seg, ang)
            ii = (cx + (o[0] - cx) * ri, cy + (o[1] - cy) * ri)
            tx, ty = -math.sin(math.radians(ang)) * sgn, math.cos(math.radians(ang)) * sgn
            _face(mb, [(o[0], o[1], zs), (ii[0], ii[1], zs), (ii[0], ii[1], ze), (o[0], o[1], ze)], inner, (tx, ty, 0))
        a = math.radians((ea + eb) / 2)
        with mb.at((cx + math.cos(a) * (r - T), cy + math.sin(a) * (r - T), 0.0), rot=math.degrees(a) + 90.0):
            mb.box((0.0, 0.06, zs - 0.03), (2 * r * math.tan(math.radians((eb - ea) / 2)) + 0.2, 0.14, 0.06), sill)
            mb.box((0.0, -T / 2, zs + (ze - zs) * 0.62), (2 * r * math.tan(math.radians((eb - ea) / 2)), 0.06, 0.05),
                   frame)


def _turret_floor(mb, cx, cy, r_in, a0, a1, z, top, bottom=K.CEIL, ceiling=None, qx=1, qy=1, T=G_RT):
    """Floor slab (or ceiling face when ceiling=material) of the part of a turret outside the block corner:
    quarter sectors between a0 and a1 plus two strips where the block walls were."""
    q = []
    a = a0
    while a < a1 - 1e-6:
        q.append((a, min(a + 90.0, a1)))
        a += 90.0
    rr = r_in + E_IN
    for (s0, s1) in q:
        pts = [(cx, cy)] + [_ring_point(cx, cy, rr, 28, s0 + (s1 - s0) * k / 7) for k in range(8)]
        if ceiling:
            mb.poly([(p[0], p[1], z) for p in reversed(pts)], ceiling)
        else:
            mb.prism(pts, z - 0.3, z, bottom, top_mat=top)
    e = T - E_IN
    strips = [(cx, cy, cx + qx * e, cy + qy * (r_in)), (cx + qx * e, cy, cx + qx * r_in, cy + qy * e)]
    for (xa, ya, xb, yb) in strips:
        x0_, x1_ = sorted((xa, xb))
        y0_, y1_ = sorted((ya, yb))
        if ceiling:
            mb.poly([(x0_, y0_, z), (x0_, y1_, z), (x1_, y1_, z), (x1_, y0_, z)], ceiling)
        else:
            mb.box_mm((x0_, y0_, z - 0.3), (x1_, y1_, z), bottom, mats={"+z": top})


def _girls_turrets_inside(mb, R):
    """Hollow turret storeys: ring walls with real windows, floors and ceilings."""
    rooms = {(-22.0, 4.0): ("parlour", "wfb"), (22.0, 4.0): ("tea", "efb"), (-22.0, 26.0): ("library", "wbb"),
             (22.0, 26.0): ("dining", "ebb")}
    for (tx, ty), (g0, g1) in rooms.items():
        a0, a1 = G_TURRET_OPEN[(tx, ty)]
        angs = _turret_angles(tx, ty)
        qx, qy = (1 if tx < 0 else -1), (1 if ty < 10 else -1)
        r_in = G_TURRET_R - G_RT
        _ring_wall(mb, tx, ty, G_TURRET_R, G_RT, a0, a1, -0.3, 5.35, WALL, R[g0]["wall"],
                   [(a, 1.0, 1.85, 4.45) for a in angs])
        _ring_wall(mb, tx, ty, G_TURRET_R, G_RT, a0, a1, 5.35, 9.2, WALL, R[g1]["wall"],
                   [(a, 1.0, 6.0, 8.3) for a in angs])
        _turret_floor(mb, tx, ty, r_in, a0, a1, G_FL, R[g0]["floor"], qx=qx, qy=qy)
        _turret_floor(mb, tx, ty, r_in, a0, a1, G_C0, None, ceiling=K.CEIL, qx=qx, qy=qy)
        _turret_floor(mb, tx, ty, r_in, a0, a1, G_Z1, R[g1]["floor"], qx=qx, qy=qy)
        _turret_floor(mb, tx, ty, r_in, a0, a1, G_C1, None, ceiling=K.CEIL, qx=qx, qy=qy)


def _turret_angles(tx, ty):
    if ty < 10:
        return (-90.0, -45.0, 0.0) if tx > 0 else (-90.0, -135.0, 180.0)
    return (90.0, 45.0, 0.0) if tx > 0 else (90.0, 135.0, 180.0)


def _girls_rooms():
    Z0, Z1 = G_FL, G_Z1
    rr = G_TURRET_R - G_RT
    R = {}

    def tg(rect, tx, ty):
        """Skirting gaps where the corner of `rect` opens into the turret at (tx, ty)."""
        x0, y0, x1, y1 = rect
        ys = (ty, ty + rr) if ty < 10 else (ty - rr, ty)
        xs = (tx, tx + rr) if tx < 0 else (tx - rr, tx)
        sx_side = "w" if tx < 0 else "e"
        sy_side = "s" if ty < 10 else "n"
        return {sx_side: [ys], sy_side: [xs]}

    def room(name, fl, rect, wall, floor, turret=None, **kw):
        if turret:
            kw["gaps"] = tg(rect, *turret)
        R[name] = _room(name, fl, rect, Z0 if fl == 0 else Z1, G_C0 if fl == 0 else G_C1, wall, floor, **kw)
        return R[name]

    room("foyer", 0, (-6.6, 1.4, 6.6, 26.6), K.PLASTER_WHITE, K.MARBLEFLOOR, dado=(K.TRIM_WHITE, GTRIM), dado_h=0.6,
         cut_ceiling=[(-6.7, 16.4, -4.85, 23.6), (4.85, 16.4, 6.7, 23.6)], cornice=GTRIM, panels=GTRIM)
    room("parlour", 0, (-21.6, 4.4, -7.4, 13.4), WALL_ROSE, K.WOODFLOOR, turret=(-22.0, 4.0),
         dado=(K.TRIM_WHITE, K.TRIM_GOLD), panels=K.TRIM_WHITE, seams=K.WOOD_DARK,
         coffer=(2.9, K.TRIM_WHITE, K.TRIM_GOLD))
    room("gcorr", 0, (-18.7, 13.6, -7.4, 16.4), K.PLASTER_MINT, K.TILE, dado=(K.TRIM_WHITE, GTRIM), cornice=K.TRIM_WHITE,
         open="w")
    R["vest"] = _room("vest", 0, (-21.6, 13.6, -20.5, 16.4), 0.15, G_C0, K.PLASTER_MINT, K.TILE, cornice=K.TRIM_WHITE,
                      open="e")
    room("library", 0, (-21.6, 16.6, -7.4, 25.6), WALL_LILAC, "M_IntWoodFloorDark", turret=(-22.0, 26.0),
         dado=(K.WOOD, K.TRIM_GOLD), panels=K.TRIM_WHITE, seams=K.WOOD_DARK)
    room("tea", 0, (7.4, 4.4, 21.6, 13.4), WALL_IVORY, "M_IntCarpetRose", turret=(22.0, 4.0),
         dado=(K.TRIM_WHITE, GTRIM), panels=GTRIM, coffer=(2.9, K.TRIM_WHITE, GTRIM))
    room("ecorr", 0, (7.4, 13.6, 21.6, 16.4), K.PLASTER_MINT, K.TILE, dado=(K.TRIM_WHITE, GTRIM), cornice=K.TRIM_WHITE)
    room("dining", 0, (7.4, 16.6, 21.6, 25.6), K.PLASTER_SKY, K.MARBLEFLOOR, turret=(22.0, 26.0),
         dado=(K.TRIM_WHITE, K.TRIM_GOLD), panels=K.TRIM_WHITE, coffer=(2.9, K.TRIM_WHITE, K.TRIM_GOLD))
    room("salon", 1, (-6.6, 1.4, 6.6, 13.4), "M_IntWallpaperBlue", K.WOODFLOOR, dado=(K.TRIM_WHITE, K.TRIM_GOLD),
         dado_h=0.3, panels=K.TRIM_WHITE, seams=K.WOOD_DARK, coffer=(2.6, K.TRIM_WHITE, K.TRIM_GOLD))
    room("fcorr", 1, (-6.6, 13.6, 6.6, 16.4), K.PLASTER_WHITE, MARBLE_ROSE, cornice=GTRIM, open="n")
    room("gallery", 1, (-6.6, 16.4, 6.6, 26.6), K.PLASTER_WHITE, MARBLE_ROSE, cornice=GTRIM, open="s",
         holes=[(-6.7, 16.4, -4.85, 23.6), (4.85, 16.4, 6.7, 23.6)],
         gaps={"w": [(16.3, 23.65)], "e": [(16.3, 23.65)]})
    themes = {"wfs": WALL_ROSE, "wfb": "M_IntWallpaperBlue", "wbs": WALL_LILAC, "wbb": WALL_ROSE,
              "efs": K.PLASTER_MINT, "efb": WALL_LILAC, "ebs": "M_IntWallpaperBlue", "ebb": WALL_ROSE}
    for sx in (-1, 1):
        s = "w" if sx < 0 else "e"
        room(s + "fs", 1, _mx((7.4, 4.4, 14.1, 14.9), sx), themes[s + "fs"], K.WOODFLOOR, dado=(K.TRIM_WHITE, GTRIM),
             dado_h=0.3, panels=K.TRIM_WHITE, seams=K.WOOD_DARK)
        room(s + "fb", 1, _mx((14.3, 4.4, 21.6, 14.9), sx), themes[s + "fb"], "M_IntCarpetRose",
             turret=(sx * 22.0, 4.0), panels=K.TRIM_WHITE)
        room(s + "bs", 1, _mx((7.4, 15.1, 14.9, 25.6), sx), themes[s + "bs"], K.WOODFLOOR, dado=(K.TRIM_WHITE, GTRIM),
             dado_h=0.3, panels=K.TRIM_WHITE, seams=K.WOOD_DARK)
        room(s + "bb", 1, _mx((15.1, 15.1, 21.6, 25.6), sx), themes[s + "bb"], "M_IntCarpetRose",
             turret=(sx * 22.0, 26.0), panels=K.TRIM_WHITE)
    return R


def _girls_partitions(aset, mb, R):
    Z0, Z1 = G_FL, G_Z1
    D = G_DOOR
    W = WALL
    for sx in (-1, 1):
        s = "w" if sx < 0 else "e"
        g_front, g_corr, g_back = (R["parlour"], R["gcorr"], R["library"]) if sx < 0 else (R["tea"], R["ecorr"], R["dining"])

        def J(y0, y1, z0, z1, wing, cside, doors):
            a, b = ((7.0, y0), (7.0, y1)) if sx > 0 else ((-7.0, y1), (-7.0, y0))
            _pw(aset, mb, a, b, z0, z1, 0.8, wing, cside, doors, trim=GTRIM, trim_in=GTRIM)

        J(4.0, 13.5, -0.3, 5.35, g_front["wall"], R["foyer"]["wall"], [(8.5, 1.6, 2.7, D, True, Z0)])
        J(13.5, 16.5, -0.3, 5.35, g_corr["wall"], R["foyer"]["wall"], [(15.0, 1.6, 2.7, D, True, Z0)])
        J(16.5, 26.0, -0.3, 5.35, g_back["wall"], R["foyer"]["wall"], [])
        J(4.0, 13.5, 5.35, 9.2, R[s + "fs"]["wall"], R["salon"]["wall"], [(9.0, 1.0, 2.4, D, False, Z1)])
        J(13.5, 15.0, 5.35, 9.2, R[s + "fs"]["wall"], R["fcorr"]["wall"], [(14.2, 1.0, 2.4, D, False, Z1)])
        J(15.0, 16.4, 5.35, 9.2, R[s + "bs"]["wall"], R["fcorr"]["wall"], [(15.75, 1.0, 2.4, D, False, Z1)])
        J(16.4, 26.0, 5.35, 9.2, R[s + "bs"]["wall"], R["gallery"]["wall"], [])
        J(4.0, 26.0, 9.2, 13.6, W, W, [])
        a, b = ((7.0, 4.0), (7.0, 26.0)) if sx > 0 else ((-7.0, 26.0), (-7.0, 4.0))
        mb.wall(a, b, 13.6, 14.4 - 13.6, 0.4, W)                    # pavilion wall above the main roof line

        def H(y, xa, xb, z0, z1, south, north, doors, t=0.2):
            a, b = (sx * xa, y), (sx * xb, y)
            if sx < 0:
                a, b = b, a
            _pw(aset, mb, a, b, z0, z1, t, south, north, doors, trim=GTRIM, trim_in=GTRIM)

        H(13.5, 7.4, 21.6, -0.3, G_C0 + 0.06, g_front["wall"], g_corr["wall"], [(sx * 12.0, 1.2, 2.5, D, False, Z0)])
        H(16.5, 7.4, 21.6, -0.3, G_C0 + 0.06, g_corr["wall"], g_back["wall"], [(sx * 12.0, 1.2, 2.5, D, False, Z0)])
        H(15.0, 7.4, 21.6, Z1, 9.2, R[s + "fs"]["wall"], R[s + "bs"]["wall"], [])
        # sitting room | bedroom splits
        for (xs, ya, yb, si, bi, dv) in ((14.2, 4.4, 14.9, "fs", "fb", 10.0), (15.0, 15.1, 25.6, "bs", "bb", 20.0)):
            a, b = (sx * xs, ya), (sx * xs, yb)
            inner_m, outer_m = R[s + si]["wall"], R[s + bi]["wall"]
            right, left = (outer_m, inner_m) if sx > 0 else (inner_m, outer_m)
            _pw(aset, mb, a, b, Z1, 9.2, 0.2, right, left, [(dv, 1.0, 2.4, D, False, Z1)], trim=GTRIM, trim_in=GTRIM)
    # F1 salon | landing corridor
    _pw(aset, mb, (-6.6, 13.5), (6.6, 13.5), Z1, 9.2, 0.2, R["salon"]["wall"], R["fcorr"]["wall"],
        [(0.0, 1.6, 2.6, D, True, Z1)], trim=GTRIM, trim_in=GTRIM)


def _girls_stairs(aset, mb, nc):
    """Twin flights along the foyer side walls, climbing from the back of the hall to the landing."""
    Z0, Z1 = G_FL, G_Z1
    for sx in (-1, 1):
        _flight(mb, sx * 5.75, 23.6, Z0, Z1, -90.0, 1.6, carpet="M_IntCarpetRose", cw=1.0, base=Z0, nose=K.TRIM_GOLD)
        _rail(mb, (sx * 4.98, 23.6, Z0), (sx * 4.98, 16.45, Z1), post=K.TRIM_WHITE, rail=GTRIM, newel=MARBLE)
        _rail(mb, (sx * 4.88, 16.45, Z1), (sx * 4.88, 23.62, Z1), post=K.TRIM_WHITE, rail=GTRIM)
        _rail(mb, (sx * 4.88, 23.62, Z1), (sx * 6.55, 23.62, Z1), post=K.TRIM_WHITE, rail=GTRIM, newel=MARBLE)
    # the vestibule steps from the conservatory door up to the garden hall
    _flight(mb, -20.5, 15.0, 0.15, Z0, 0.0, 2.8, carpet="M_IntCarpetRose", cw=1.4, base=-0.2, nose=K.TRIM_WHITE)
    for y in (13.68, 16.32):
        _rail(mb, (-20.5, y, 0.15), (-18.7, y, Z0), post=K.TRIM_WHITE, rail=GTRIM, h=0.9)


def _girls_interior(aset, main, mb, nc):
    R = _girls_rooms()
    _ext_walls(aset, main, _girls_segments(), G_BANDS_INT, outer=WALL, frame=GTRIM, trim_in=GTRIM)
    _girls_turrets_inside(main, R)
    _girls_partitions(aset, mb, R)
    _build_rooms(mb, nc)
    _girls_stairs(aset, mb, nc)
    _girls_furnish(aset, mb, nc, R)


# ----------------------------------------------------------------------------- girls: rooms
def _cake_stand(nc, x, y, z, s=1.0):
    nc.cylinder((x, y, z), 0.015 * s, 0.42 * s, K.TRIM_GOLD, seg=6)
    for k, (r, zz) in enumerate(((0.16, 0.04), (0.12, 0.2), (0.08, 0.35))):
        nc.cylinder((x, y, z + zz * s), r * s, 0.012, "M_IntTrimWhite", seg=12)
        for j in range(5):
            a = TAU * j / 5 + k
            nc.sphere((x + math.cos(a) * r * 0.6 * s, y + math.sin(a) * r * 0.6 * s, z + (zz + 0.03) * s), 0.025 * s,
                      ("M_IntFabricPink", "M_IntFabricYellow", "M_FlowerRed")[(j + k) % 3], seg=6, rings=4)


def _tea_table(f, x, y, chairs=3, chair="SM_Int_WoodChair", stand=True, a0=0.0):
    f.prop("SM_Int_RoundTable", x, y, a0)
    f.nc.cylinder((x, y, 0.755), 0.52, 0.006, "M_IntFabricWhite", seg=16)
    f.prop("SM_Int_TeaSet", x + 0.1, y - 0.05, a0 + 20.0, z=0.76)
    if stand:
        _cake_stand(f.nc, x - 0.25, y + 0.15, 0.76)
    for k in range(chairs):
        a = math.radians(a0 + 90.0 + 360.0 * k / chairs)
        cx, cy = x + math.cos(a) * 0.85, y + math.sin(a) * 0.85
        f.prop(chair, cx, cy, math.degrees(a) - 90.0)


def _girls_furnish(aset, mb, nc, R):
    _girls_foyer(aset, mb, nc, R["foyer"])
    _girls_parlour(aset, mb, nc, R["parlour"])
    _girls_halls(aset, mb, nc, R)
    _girls_library(aset, mb, nc, R["library"])
    _girls_tearoom(aset, mb, nc, R["tea"])
    _girls_dining(aset, mb, nc, R["dining"])
    _girls_salon(aset, mb, nc, R["salon"], R["fcorr"], R["gallery"])
    num = 1
    for sx in (-1, 1):
        s = "w" if sx < 0 else "e"
        for (k, front) in (("f", True), ("b", False)):
            _girls_sitting(aset, mb, nc, R[s + k + "s"], sx, front)
            _girls_bedroom(aset, mb, nc, R[s + k + "b"], sx, front, num)
            num += 1
    _girls_conservatory_door(aset, mb)


def _girls_foyer(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        # rose / white marble chequer and the pink runner through the hall
        for i in range(13):
            for j in range(25):
                if (i + j) % 2 == 0 and not (abs(-6.1 + i * 1.0) < 1.2):
                    x, y = -6.6 + i * 1.015, 1.4 + j * 1.008
                    mb.box_mm((x + 0.01, y + 0.01, 0.0), (x + 1.005, y + 0.998, 0.003), MARBLE_ROSE, skip=("-z",))
        K.rug(mb, -1.0, 1.45, 1.0, 26.55, 0.004, "M_IntCarpetRose", K.TRIM_GOLD)
        # centre table with a big bouquet
        f.prop("SM_Int_RoundTable", 0.0, 8.8, 0.0)
        nc.cylinder((0.0, 8.8, 0.755), 0.55, 0.006, "M_IntFabricPink", seg=16)
        _vase(nc, 0.0, 8.8, 0.76, 2.0, mat=K.TRIM_GOLD, flowers=("M_FlowerRed", "M_FlowerWhite", "M_IntFabricPink"))
        for sx in (-1, 1):
            f.prop("SM_Int_Console", sx * 6.35, 5.0, -90.0 * sx)
            f.prop("SM_Int_Mirror", sx * 6.6, 5.0, -90.0 * sx, z=1.0)
            _vase(nc, sx * 6.35, 5.5, 0.85, 1.0, flowers=("M_FlowerWhite", "M_IntFabricPink"))
            f.prop("SM_Int_Candelabra", sx * 6.35, 4.5, 0.0, z=0.85)
            f.prop("SM_Int_PottedPlantB", sx * 6.1, 1.9, 0.0)
            f.prop("SM_Int_Bench", sx * 6.25, 11.5, -90.0 * sx)
            f.prop("SM_Int_PottedPlantB", sx * 3.4, 25.9, 0.0)
            _portrait(f, sx * 6.6, 11.5, 1.7, "e" if sx > 0 else "w", 1.3)
            for y in (3.3, 7.0, 12.6):
                _sconce(f, sx * 6.6, y, 2.3, "e" if sx > 0 else "w")
        _portrait(f, 0.0, 26.6, 2.75, "n", 1.0)
        for y in (5.0, 12.5, 20.2):
            _chandelier(f, 0.0, y, zc, 1.2)
        f.light(0.0, 20.0, 2.0, 2500.0, 9.0)
    aset.npc((-2.5, 6.0, r["z"]), 160.0, dorm="obelisk", wander=3.0)
    aset.npc((2.0, 18.0, r["z"]), 20.0, dorm="obelisk", wander=3.0)
    K.camera(aset, "foyer", (0.0, 1.9, r["z"] + 1.7), (0.0, 22.0, r["z"] + 2.2), 15.0)
    K.camera(aset, "stairs", (3.0, 26.2, r["z"] + 1.7), (-5.5, 16.0, r["z"] + 3.0), 15.0)


def _girls_parlour(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, -15.8, 5.6, -9.8, 10.8, 0.0, "M_IntCarpetRose", K.TRIM_GOLD)
        K.fireplace(mb, nc, f.a, -12.8, 4.4, 180.0, w=1.8, h=1.3, mat="M_IntTrimWhite", trim=GTRIM)
        f.prop("SM_Int_Mirror", -12.8, 4.4, 180.0, z=1.55)
        K.sofa_set(f.a, -12.8, 8.6, 0.0)
        f.prop("SM_Int_Pillows", -12.8, 8.75, 0.0, z=0.42)
        K.piano(mb, nc, -18.6, 10.6, 160.0, mat="M_IntTrimWhite")
        _tea_table(f, -23.0, 3.0, chairs=2, chair="SM_Int_GreenChair", a0=45.0)
        f.prop("SM_Int_FoldingScreen", -21.0, 12.6, 30.0)
        f.prop("SM_Int_Cabinet", -9.0, 13.15, 180.0)
        f.prop("SM_Int_Shelves", -15.0, 13.2, 180.0)
        f.prop("SM_Int_PottedPlantB", -7.9, 4.9, 0.0)
        f.prop("SM_Int_WallClock", -7.4, 11.0, -90.0, z=2.2)
        _chandelier(f, -12.8, 8.0, zc, 1.0)
        _chandelier(f, -19.6, 6.4, zc, 0.8)
    _curtains(nc, r, "M_IntFabricPink", rod=K.TRIM_GOLD)
    aset.npc((-12.0, 6.6, r["z"]), 180.0, dorm="obelisk", wander=1.5)
    K.camera(aset, "parlour", (-7.9, 11.4, r["z"] + 1.7), (-20.0, 5.0, r["z"] + 0.8), 15.0)


def _girls_halls(aset, mb, nc, R):
    for key, sx in (("gcorr", -1), ("ecorr", 1)):
        r = R[key]
        f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
        zc = r["zc"] - r["z"]
        with f:
            K.rug(mb, r["x0"] + 0.3, 14.3, r["x1"] - 0.3, 15.7, 0.0, "M_IntCarpetRose", K.TRIM_GOLD)
            for x in (10.0, 17.0):
                _portrait(f, sx * x, 16.4, 1.5, "n", 0.9)
                _portrait(f, sx * x, 13.6, 1.5, "s", 0.9)
                f.prop("SM_Int_CeilingLamp", sx * x, 15.0, 0.0, z=zc)
            if sx > 0:
                f.prop("SM_Int_Console", 21.35, 15.0, -90.0)
                f.prop("SM_Int_Mirror", 21.6, 15.0, -90.0, z=1.0)
                _vase(nc, 21.35, 15.0, 0.85, 1.3, flowers=("M_IntFabricPink", "M_FlowerWhite"))
                f.prop("SM_Int_PottedPlantB", 20.9, 14.0, 0.0)
                f.prop("SM_Int_PottedPlantB", 20.9, 16.0, 0.0)
            else:
                f.prop("SM_Int_PottedPlant", -18.2, 14.0, 0.0)
                f.prop("SM_Int_PottedPlant", -18.2, 16.0, 0.0)
    r = R["vest"]
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    with f:
        f.prop("SM_Int_CeilingLamp", -21.0, 15.0, 0.0, z=r["zc"] - r["z"])
    K.camera(aset, "garden_hall", (-8.0, 15.0, G_FL + 1.65), (-22.0, 15.0, G_FL + 0.6), 16.0)


def _girls_library(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, -16.6, 18.6, -10.4, 23.6, 0.0, "M_IntCarpetBlue", K.TRIM_GOLD)
        for x in (-19.6, -18.6, -15.0, -11.0, -10.0):
            f.prop("SM_Int_Bookshelf", x, 25.4, 0.0)
        for y in (17.8, 19.0, 20.2, 21.4):
            f.prop("SM_Int_Bookshelf", -21.4, y, 90.0)
        K.bookcase(mb, nc, -7.6, 18.6, -90.0, w=2.2, h=2.3, shelves=5, mat="M_IntTrimWhite", rng_seed=12)
        K.bookcase(mb, nc, -7.6, 22.6, -90.0, w=2.2, h=2.3, shelves=5, mat="M_IntTrimWhite", rng_seed=13)
        f.prop("SM_Int_Table", -13.5, 21.1, 0.0)
        for x in (-14.1, -12.9):
            f.prop("SM_Int_DiningChair", x, 20.3, 0.0)
            f.prop("SM_Int_DiningChair", x, 21.9, 180.0)
        f.prop("SM_Int_DeskLamp", -13.0, 21.2, 180.0, z=0.76)
        f.prop("SM_Int_Books", -14.0, 21.0, 15.0, z=0.76)
        f.prop("SM_Int_RockingChair", -23.0, 27.0, 135.0)
        f.prop("SM_Int_SideTable", -23.8, 25.6, 0.0)
        f.prop("SM_Int_OilLamp", -23.8, 25.6, 0.0, z=0.6)
        f.prop("SM_Int_GreenChair", -9.2, 17.6, 200.0)
        f.prop("SM_Int_FoldingScreen", -17.5, 17.2, 0.0)
        f.prop("SM_Int_PottedPlantB", -8.0, 25.0, 0.0)
        _chandelier(f, -13.5, 21.1, zc, 1.0)
        _chandelier(f, -20.0, 24.6, zc, 0.7)
    _curtains(nc, r, "M_IntFabricPurple", rod=K.TRIM_GOLD)
    K.camera(aset, "library", (-8.0, 17.2, r["z"] + 1.7), (-20.0, 25.0, r["z"] + 1.0), 15.0)


def _girls_tearoom(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        for (x, y, a) in ((10.3, 7.0, 0.0), (15.3, 7.2, 30.0), (12.6, 11.0, 10.0), (18.6, 10.6, 50.0)):
            _tea_table(f, x, y, chairs=3, chair="SM_Int_WoodChair" if x < 14 else "SM_Int_GreenChair", a0=a)
        _tea_table(f, 23.0, 3.0, chairs=2, chair="SM_Int_GreenChair", a0=-45.0)
        f.prop("SM_Int_Console", 7.65, 11.0, 90.0)
        f.prop("SM_Int_TeaSet", 7.65, 10.7, 90.0, z=0.85)
        f.prop("SM_Int_Kettle", 7.65, 11.5, 90.0, z=0.85)
        _cake_stand(nc, 7.65, 11.9, 0.85, 1.2)
        f.prop("SM_Int_FoldingScreen", 20.6, 12.5, -30.0)
        f.prop("SM_Int_PottedPlantB", 7.9, 4.9, 0.0)
        f.prop("SM_Int_PottedPlantB", 21.1, 12.9, 0.0)
        f.prop("SM_Int_Cabinet", 16.0, 13.15, 180.0)
        _portrait(f, 12.8, 4.4, 1.6, "s", 1.2)
        _chandelier(f, 11.5, 8.8, zc, 1.0)
        _chandelier(f, 17.6, 8.8, zc, 1.0)
    _curtains(nc, r, "M_IntFabricPink", rod=K.TRIM_GOLD)
    aset.npc((15.3, 6.2, r["z"]), 0.0, dorm="obelisk", wander=0.6)
    aset.npc((12.0, 10.3, r["z"]), 150.0, dorm="obelisk", wander=0.6)
    K.camera(aset, "tea_room", (8.0, 12.9, r["z"] + 1.7), (19.5, 5.0, r["z"] + 0.7), 15.0)


def _girls_dining(aset, mb, nc, r):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, 9.4, 18.8, 19.6, 23.2, 0.0, "M_IntCarpetRose", K.TRIM_GOLD)
        _long_table(mb, nc, 14.5, 21.0, 7.6, 1.4, cloth="M_IntFabricWhite", runner="M_IntFabricPink", mat=K.TRIM_WHITE)
        for i in range(7):
            x = 11.5 + i * 1.0
            for sy in (-1, 1):
                f.prop("SM_Int_DiningChair", x, 21.0 + sy * 1.05, 0.0 if sy < 0 else 180.0)
                _place_setting(nc, x, 21.0 + sy * 0.42, 0.0)
            if i % 3 == 0:
                f.prop("SM_Int_Candelabra", x + 0.5, 21.0, 0.0, z=0.78)
            elif i % 3 == 1:
                _vase(nc, x + 0.5, 21.0, 0.78, 0.9, flowers=("M_IntFabricPink", "M_FlowerWhite"))
        for x in (10.0, 19.0):
            f.prop("SM_Int_Armchair", x, 21.0, 90.0 if x < 14 else -90.0)
        f.prop("SM_Int_Console", 7.65, 21.0, 90.0)
        f.prop("SM_Int_Mirror", 7.4, 21.0, 90.0, z=1.0)
        f.prop("SM_Int_Candelabra", 7.65, 20.4, 90.0, z=0.85)
        _vase(nc, 7.65, 21.6, 0.85, 1.2, flowers=("M_FlowerWhite", "M_IntFabricPink"))
        f.prop("SM_Int_PottedPlantB", 7.9, 25.1, 0.0)
        f.prop("SM_Int_PottedPlantB", 7.9, 17.1, 0.0)
        f.prop("SM_Int_GreenChair", 23.0, 27.0, 45.0)
        f.prop("SM_Int_SideTable", 23.6, 25.9, 0.0)
        _vase(nc, 23.6, 25.9, 0.6, 1.0)
        _chandelier(f, 12.6, 21.0, zc, 1.0)
        _chandelier(f, 16.4, 21.0, zc, 1.0)
    _curtains(nc, r, "M_IntFabricBlue", rod=K.TRIM_GOLD)
    K.camera(aset, "dining", (8.0, 17.2, r["z"] + 1.75), (20.0, 24.6, r["z"] + 0.6), 15.0)


def _girls_salon(aset, mb, nc, r, rc, rg):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    with f:
        K.rug(mb, -4.2, 4.6, 4.2, 10.6, 0.0, "M_IntCarpetRose", K.TRIM_GOLD)
        f.prop("SM_Int_Sofa", 0.0, 10.2, 180.0)
        f.prop("SM_Int_SofaB", -3.2, 7.4, -90.0)
        f.prop("SM_Int_SofaB", 3.2, 7.4, 90.0)
        f.prop("SM_Int_CoffeeTable", 0.0, 7.6, 0.0)
        f.prop("SM_Int_TeaSet", 0.0, 7.6, 15.0, z=0.45)
        f.prop("SM_Int_Pillows", 0.0, 10.35, 180.0, z=0.42)
        for sx in (-1, 1):
            f.prop("SM_Int_PottedPlantB", sx * 6.1, 1.9, 0.0)
            f.prop("SM_Int_DisplayShelves", sx * 4.6, 13.2, 180.0)
            f.prop("SM_Int_GreenChair", sx * 2.6, 2.6, 180.0 - sx * 30.0)
        _chandelier(f, 0.0, 7.4, zc, 1.1)
    _curtains(nc, r, "M_IntFabricPink", rod=K.TRIM_GOLD)
    K.camera(aset, "salon", (5.6, 12.8, r["z"] + 1.7), (-2.0, 1.5, r["z"] + 1.0), 15.0)
    # landing + music gallery
    f = Frame(aset, mb, nc, 0.0, 0.0, rg["z"])
    zc = rg["zc"] - rg["z"]
    with f:
        K.rug(mb, -1.0, 13.7, 1.0, 26.4, 0.004, "M_IntCarpetRose", K.TRIM_GOLD)
        K.piano(mb, nc, -2.6, 20.0, 150.0, mat="M_IntTrimWhite")
        f.prop("SM_Int_WoodChair", 2.6, 19.0, -60.0)
        for x in (-5.8, -3.0, 3.0, 5.8):
            if abs(x) > 4:
                f.prop("SM_Int_Bookshelf", x, 26.4, 0.0)
        f.prop("SM_Int_GreenChair", 2.4, 24.9, 160.0)
        f.prop("SM_Int_GreenChair", -2.4, 24.9, 200.0)
        f.prop("SM_Int_PottedPlantB", 4.3, 17.0, 0.0)
        _chandelier(f, 0.0, 15.0, zc, 1.0)
        _chandelier(f, 0.0, 21.5, zc, 1.0)
    _curtains(nc, rg, "M_IntFabricPink", rod=K.TRIM_GOLD)
    K.camera(aset, "gallery", (0.0, 13.9, rg["z"] + 1.7), (0.0, 25.0, rg["z"] + 0.6), 15.0)


def _girls_sitting(aset, mb, nc, r, sx, front):
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    cx, cy = (r["x0"] + r["x1"]) / 2, (r["y0"] + r["y1"]) / 2
    win_y = r["y0"] if front else r["y1"]          # outer wall (windows)
    inner_y = r["y1"] if front else r["y0"]        # suite partition
    sy = 1 if front else -1
    with f:
        K.rug(mb, cx - 2.2, cy - 2.0, cx + 2.2, cy + 2.0, 0.0, "M_IntCarpetYellow" if front else "M_IntCarpetRose",
              K.TRIM_GOLD)
        f.prop("SM_Int_Sofa", cx, inner_y - sy * 0.55, 0.0 if front else 180.0)
        f.prop("SM_Int_CoffeeTable", cx, cy + sy * 0.6, 0.0)
        f.prop("SM_Int_TeaSet", cx, cy + sy * 0.6, 40.0, z=0.45)
        for s in (-1, 1):
            f.prop("SM_Int_GreenChair", cx + s * 1.6, cy - sy * 0.1, s * 70.0 + (180.0 if front else 0.0))
        xo = r["x1"] if sx < 0 else r["x0"]         # partition to the bedroom (inner side, mirrored)
        xo = r["x0"] if sx < 0 else r["x1"]
        K.desk(mb, nc, xo - sx * 0.33, win_y + sy * 1.6, 90.0 if sx < 0 else -90.0, w=1.2, d=0.6, top=K.TRIM_WHITE,
               legs=K.TRIM_WHITE, hutch=True, rng_seed=int(abs(cx * 10)))
        f.prop("SM_Int_WoodChair", xo - sx * 1.0, win_y + sy * 1.6, 90.0 if sx > 0 else -90.0)
        f.prop("SM_Int_Shelves", xo - sx * 0.2, inner_y - sy * 1.9, 90.0 if sx < 0 else -90.0)
        f.prop("SM_Int_PottedPlantB", (r["x1"] - 0.45) if sx < 0 else (r["x0"] + 0.45), win_y + sy * 0.45, 0.0)
        f.prop("SM_Int_PottedPlant", xo - sx * 0.3, win_y + sy * 0.45, 0.0)
        _chandelier(f, cx, cy, zc, 0.8)
    _curtains(nc, r, "M_IntFabricPink" if front else "M_IntFabricPurple", rod=K.TRIM_GOLD)


def _girls_bedroom(aset, mb, nc, r, sx, front, num):
    """Corner bedroom with a canopy bed and the round turret bay (tea for two)."""
    f = Frame(aset, mb, nc, 0.0, 0.0, r["z"])
    zc = r["zc"] - r["z"]
    tx, ty = sx * 22.0, (4.0 if front else 26.0)
    qy = 1 if front else -1
    inner_y = r["y1"] if front else r["y0"]
    door_x = r["x1"] if sx < 0 else r["x0"]
    cx = (r["x0"] + r["x1"]) / 2
    by = inner_y - qy * 1.25
    with f:
        K.rug(mb, cx - 2.0, min(by - qy * 3.6, by + qy * 1.0), cx + 2.0, max(by - qy * 3.6, by + qy * 1.0), 0.0,
              "M_IntCarpetRose", K.TRIM_GOLD)
        f.prop("SM_Int_GrandBed", cx, by, 0.0 if front else 180.0)
        for s in (-1, 1):
            f.prop("SM_Int_NightstandB", cx + s * 1.55, inner_y - qy * 0.3, 0.0 if front else 180.0)
            f.prop("SM_Int_OilLamp", cx + s * 1.55, inner_y - qy * 0.3, 0.0, z=0.55)
        for sxx in (-1, 1):
            for syy in (-1, 1):
                mb.box((cx + sxx * 1.12, by + syy * 1.15, 1.3), (0.07, 0.07, 2.6), K.TRIM_WHITE)
        nc.box((cx, by, 2.6), (2.35, 2.4, 0.05), "M_IntFabricPink")
        for sxx in (-1, 1):
            nc.box((cx + sxx * 1.17, by, 2.3), (0.02, 2.4, 0.55), "M_IntFabricPink")
        nc.box((cx, by - qy * 1.2, 2.3), (2.35, 0.02, 0.55), "M_IntFabricPink")
        # vanity + wardrobe on the wall shared with the sitting room
        vy = (r["y0"] + 2.0) if front else (r["y1"] - 2.0)
        f.prop("SM_Int_Console", door_x + sx * 0.25, vy, 90.0 if sx > 0 else -90.0)
        f.prop("SM_Int_Mirror", door_x, vy, 90.0 if sx > 0 else -90.0, z=1.0)
        f.prop("SM_Int_Ottoman", door_x + sx * 0.8, vy, 0.0)
        _vase(nc, door_x + sx * 0.25, vy + 0.4, 0.85, 0.8, flowers=("M_IntFabricPink", "M_FlowerWhite"))
        wy = inner_y - qy * 1.0
        f.prop("SM_Int_Cabinet", door_x + sx * 0.3, wy, 90.0 if sx > 0 else -90.0)
        # tea for two in the turret
        _tea_table(f, tx + sx * 1.0, ty - qy * 1.0, chairs=2, chair="SM_Int_GreenChair", stand=False,
                   a0=45.0 * sx * qy)
        _chandelier(f, cx, (r["y0"] + r["y1"]) / 2, zc, 0.8)
        f.light(tx + sx * 0.8, ty - qy * 0.8, 2.6, 900.0, 4.0)
    _curtains(nc, r, "M_IntFabricPink", rod=K.TRIM_GOLD)
    if num in (1, 4):
        K.camera(aset, "bedroom%d" % num, (door_x - sx * 0.6, (r["y0"] + 0.6) if not front else (r["y1"] - 0.6),
                                           r["z"] + 1.7), (tx + sx * 0.5, ty, r["z"] + 0.9), 15.0)


def _girls_conservatory_door(aset, mb):
    """Glass conservatory: the doorway in the glass front gets a double door, a marble step outside."""
    aset.door((-27.5, 8.75, 0.15), 0.0, 2.0, 2.55, "girls", True)
    mb.box_mm((-28.8, 7.7, -0.3), (-26.2, 8.6, 0.15), MARBLE, skip=("-z",))       # landing + step outside
    mb.box_mm((-28.8, 7.35, -0.3), (-26.2, 7.7, 0.075), MARBLE, skip=("-z",))
    K.camera(aset, "conservatory", (-23.0, 20.6, 1.85), (-30.0, 10.0, 0.8), 15.0)


def build_girls():
    aset = AssetSet("obelisk_girls")
    main = aset.mesh("ObeliskGirls_Main")
    garden = aset.mesh("ObeliskGirls_Garden")
    gazebo = aset.mesh("ObeliskGirls_Gazebo")
    jetty = aset.mesh("ObeliskGirls_Jetty")
    nc = aset.mesh("ObeliskGirls_NoCol")
    inner = aset.mesh("ObeliskGirls_Interior")
    inc = aset.mesh("ObeliskGirls_Interior_NoCol")
    _plan_reset(_girls_faces())
    try:
        _girls_building(main, nc, aset)
        _girls_interior(aset, main, inner, inc)
    finally:
        _plan_end()
    _girls_garden(garden, nc, aset)
    _gazebo(gazebo, nc, aset, *G_GAZEBO)
    _girls_jetty(jetty, nc, aset)
    _ext_cams(aset, "girls")
    return aset


def _ext_cams(aset, which):
    """Exterior check cameras (preview only, DAI_OBELISK_EXTCAM=1) to compare facades before/after."""
    if not os.environ.get("DAI_OBELISK_EXTCAM"):
        return
    cams = {"boys": [("ext_front", (8.0, -40.0, 9.0), (0.0, 5.0, 8.0)),
                     ("ext_wing", (48.0, -22.0, 8.0), (28.0, 6.0, 8.0)),
                     ("ext_back", (-20.0, 58.0, 10.0), (-8.0, 20.0, 8.0))],
            "girls": [("ext_front", (6.0, -24.0, 6.0), (0.0, 10.0, 5.5)),
                      ("ext_west", (-44.0, -6.0, 6.0), (-24.0, 12.0, 4.0)),
                      ("ext_back", (14.0, 50.0, 7.0), (4.0, 18.0, 5.0))]}[which]
    for (label, pos, tgt) in cams:
        aset.special("camera", pos, target=tgt, lens=24.0, label=label)


PLACEMENTS = {"obelisk_boys": build_boys, "obelisk_girls": build_girls}
