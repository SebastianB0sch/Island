"""
Duel Academy - the main academy building and the fountain plaza in front of it.

Placements
  academy : Grand Duel Arena (16-sided drum + stepped blue pyramid with a glass/gold apex),
            entrance hall with a colossal portico, classroom wings, end pavilions with four
            obelisk towers and a rear annex.  Walkable route:
            steps -> portico -> lobby (card shop east, reception west) -> arena portal ->
            arena floor -> duel field / aisles -> stands -> upper concourse.
  plaza   : fountain courtyard with gardens, flagpoles, direction board and the south
            entrance gate where the harbor road arrives.

Local space: metres, origin = footprint centre on finished ground (z=0), front faces -Y.
Everything here is an original, anime-inspired interpretation (no official blueprints).
"""

import math

from . import AssetSet
from .. import palette

palette.register({
    "M_AcademyStone":   dict(kind="opaque", color=(0.80, 0.78, 0.73), rough=0.8, detail="Concrete", tiling=0.25),
    "M_CardPackBlue":   dict(kind="opaque", color=(0.18, 0.35, 0.85), rough=0.35, metallic=0.3, detail=None),
    "M_CardPackPurple": dict(kind="opaque", color=(0.50, 0.22, 0.72), rough=0.35, metallic=0.3, detail=None),
    "M_PlazaLawn":      dict(kind="opaque", color=(0.30, 0.52, 0.18), rough=0.95, detail="Grass", tiling=1.0),
})

D2R = math.pi / 180.0
SQ2 = math.sqrt(2.0)

# ---------------------------------------------------------------------------- layout constants
FLOOR = 2.0                       # lobby / portico / arena floor (10 steps x 0.2 m)
DC = (0.0, 15.0)                  # drum (arena) centre
DR = 38.0                         # drum outer vertex radius (16-gon)
DA0 = 11.25                       # first vertex angle -> flat faces centred on 0/90/180/270
DT = 1.2                          # drum wall thickness
COS_H = math.cos(11.25 * D2R)
DAPO = DR * COS_H                 # outer apothem (37.27)
DIN = DAPO - DT                   # inner apothem (36.07)
DRIN = DIN / COS_H                # inner vertex radius (36.78)
DH = 32.0                         # drum parapet top
ROOF_Z = 30.0                     # arena ceiling (underside of roof slab)
OCULUS = 9.0                      # half size of the square oculus / pyramid shaft
LY0, LY1 = -66.0, DC[1] - DAPO    # lobby block front / back (back = drum south face plane)
LX = 30.0                         # lobby block half width
LWALL = 1.0
LTOP = 18.5                       # lobby wall top (hip roof eave)
LCEIL = 16.5                      # lobby ceiling
FIELD = (24.0, 14.0, 0.5)         # duel field size / height
T_N, T_R0, T_D, T_RISE = 15, 20.0, 0.9, 0.45   # arena tiers


# ---------------------------------------------------------------------------- small helpers
def polar(r, a, c=(0.0, 0.0)):
    return (c[0] + r * math.cos(a * D2R), c[1] + r * math.sin(a * D2R))


def ngon(n, r, a0=0.0, c=(0.0, 0.0)):
    return [polar(r, a0 + 360.0 * i / n, c) for i in range(n)]


def rot2(x, y, yaw):
    ca, sa = math.cos(yaw * D2R), math.sin(yaw * D2R)
    return (x * ca - y * sa, x * sa + y * ca)


def local_to_world(origin, yaw, p):
    dx, dy = rot2(p[0], p[1], yaw)
    return (origin[0] + dx, origin[1] + dy, (origin[2] if len(origin) > 2 else 0.0) + p[2])


def square_pt(h, a, c=(0.0, 0.0)):
    ca, sa = math.cos(a * D2R), math.sin(a * D2R)
    k = h / max(abs(ca), abs(sa))
    return (c[0] + ca * k, c[1] + sa * k)


def drum_pts32(r_vertex, c=DC):
    """16-gon (vertex radius r_vertex, first vertex at DA0) sampled at 32 angles (vertices + edge
    midpoints) so it can be paired with a square sampled at the same angles."""
    out = []
    for k in range(32):
        a = k * 11.25
        r = r_vertex if k % 2 == 1 else r_vertex * COS_H
        out.append(polar(r, a, c))
    return out


def inset_poly(pts, d):
    """Inset a convex CCW polygon by d."""
    n = len(pts)
    lines = []
    for i in range(n):
        (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
        ex, ey = x1 - x0, y1 - y0
        L = math.hypot(ex, ey)
        nx, ny = -ey / L, ex / L          # inward normal (left of edge)
        lines.append(((x0 + nx * d, y0 + ny * d), (ex, ey)))
    out = []
    for i in range(n):
        (p, r), (q, s) = lines[i - 1], lines[i]
        den = r[0] * s[1] - r[1] * s[0]
        t = ((q[0] - p[0]) * s[1] - (q[1] - p[1]) * s[0]) / den
        out.append((p[0] + r[0] * t, p[1] + r[1] * t))
    return out


def ring_sector(mb, c, r0, r1, a0, a1, z0, z1, mat, top=None, inner=None, faces="tioab",
                n=None, iz0=None, step=4.0):
    """Solid annular sector between radii r0..r1 and angles a0..a1 (deg, CCW).
    faces: t=top d=bottom o=outer i=inner a=cap at a0 b=cap at a1. iz0: inner face bottom."""
    if n is None:
        n = max(1, int(math.ceil((a1 - a0) / step - 1e-6)))
    angs = [a0 + (a1 - a0) * i / n for i in range(n + 1)]
    O = [polar(r1, a, c) for a in angs]
    I = [polar(r0, a, c) for a in angs]
    tm, im = top or mat, inner or mat
    zi = z0 if iz0 is None else iz0
    for i in range(n):
        o0, o1, i0, i1 = O[i], O[i + 1], I[i], I[i + 1]
        if "t" in faces:
            mb.quad((*o0, z1), (*o1, z1), (*i1, z1), (*i0, z1), tm)
        if "d" in faces:
            mb.quad((*i0, z0), (*i1, z0), (*o1, z0), (*o0, z0), mat)
        if "o" in faces:
            mb.quad((*o0, z0), (*o1, z0), (*o1, z1), (*o0, z1), mat)
        if "i" in faces:
            mb.quad((*i1, zi), (*i0, zi), (*i0, z1), (*i1, z1), im)
    if "a" in faces:
        mb.quad((*I[0], z0), (*O[0], z0), (*O[0], z1), (*I[0], z1), mat)
    if "b" in faces:
        mb.quad((*O[-1], z0), (*I[-1], z0), (*I[-1], z1), (*O[-1], z1), mat)


def ring_between(mb, outer, inner, z0, z1, top=None, bottom=None, side=None,
                 outer_side=True, inner_side=True):
    """Slab between two CCW polygons with equal vertex counts (per-face materials)."""
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        o0, o1, i0, i1 = outer[i], outer[j], inner[i], inner[j]
        if top:
            mb.quad((*o0, z1), (*o1, z1), (*i1, z1), (*i0, z1), top)
        if bottom:
            mb.quad((*i0, z0), (*i1, z0), (*o1, z0), (*o0, z0), bottom)
        if side and outer_side:
            mb.quad((*o0, z0), (*o1, z0), (*o1, z1), (*o0, z1), side)
        if side and inner_side:
            mb.quad((*i1, z0), (*i0, z0), (*i0, z1), (*i1, z1), side)


def drum_band(mb, r_out, r_in, z0, z1, mat, outer=True, inner=False):
    ring_between(mb, ngon(16, r_out, DA0, DC), ngon(16, r_in, DA0, DC), z0, z1, mat, mat, mat,
                 outer_side=outer, inner_side=inner)


def drum_band_inner(mb, r_wall, r_in, z0, z1, mat, skip_mid=()):
    """Band on the inside of the drum wall (faces the arena), optionally skipping faces by centre angle."""
    O, I = ngon(16, r_wall, DA0, DC), ngon(16, r_in, DA0, DC)
    for i in range(16):
        mid = (22.5 * (i + 1)) % 360.0
        if any(abs(mid - m) < 0.1 for m in skip_mid):
            continue
        j = (i + 1) % 16
        o0, o1, i0, i1 = O[i], O[j], I[i], I[j]
        mb.quad((*o0, z1), (*o1, z1), (*i1, z1), (*i0, z1), mat)
        mb.quad((*i0, z0), (*i1, z0), (*o1, z0), (*o0, z0), mat)
        mb.quad((*i1, z0), (*i0, z0), (*i0, z1), (*i1, z1), mat)
        # end caps where a neighbouring face is skipped
        prev_mid = (22.5 * i) % 360.0
        next_mid = (22.5 * (i + 2)) % 360.0
        if any(abs(prev_mid - m) < 0.1 for m in skip_mid):
            mb.quad((*i0, z0), (*o0, z0), (*o0, z1), (*i0, z1), mat)
        if any(abs(next_mid - m) < 0.1 for m in skip_mid):
            mb.quad((*o1, z0), (*i1, z0), (*i1, z1), (*o1, z1), mat)


def rect_band(mb, x0, y0, x1, y1, z0, z1, proud, mat, back=0.3, sides="nesw"):
    """Horizontal trim band around the outside of an axis-aligned rectangle."""
    o = proud
    if "s" in sides:
        mb.box_mm((x0 - o, y0 - o, z0), (x1 + o, y0 + back, z1), mat)
    if "n" in sides:
        mb.box_mm((x0 - o, y1 - back, z0), (x1 + o, y1 + o, z1), mat)
    ya = y0 + back if "s" in sides else y0 - o
    yb = y1 - back if "n" in sides else y1 + o
    if "w" in sides:
        mb.box_mm((x0 - o, ya, z0), (x0 + back, yb, z1), mat)
    if "e" in sides:
        mb.box_mm((x1 - back, ya, z0), (x1 + o, yb, z1), mat)


def square_frame(mb, cx, cy, z0, z1, ho, hi, mat, inner_mat=None, top_mat=None):
    """Hollow square ring (outer half ho, hole half hi)."""
    im = inner_mat or mat
    tm = top_mat or mat
    mb.box_mm((cx - ho, cy - ho, z0), (cx + ho, cy - hi, z1), mat, mats={"+z": tm, "+y": im})
    mb.box_mm((cx - ho, cy + hi, z0), (cx + ho, cy + ho, z1), mat, mats={"+z": tm, "-y": im})
    mb.box_mm((cx - ho, cy - hi, z0), (cx - hi, cy + hi, z1), mat, mats={"+z": tm, "+x": im},
              skip=("-y", "+y"))
    mb.box_mm((cx + hi, cy - hi, z0), (cx + ho, cy + hi, z1), mat, mats={"+z": tm, "-x": im},
              skip=("-y", "+y"))


def xz_prism(mb, pts, y0, y1, mat, cap_mat=None):
    """Extrude a convex polygon drawn CCW in the local XZ plane (seen from -Y) along +Y."""
    cm = cap_mat or mat
    mb.poly([(x, y0, z) for x, z in pts], cm)
    mb.poly([(x, y1, z) for x, z in reversed(pts)], cm)
    n = len(pts)
    for i in range(n):
        (xa, za), (xb, zb) = pts[i], pts[(i + 1) % n]
        mb.quad((xa, y1, za), (xb, y1, zb), (xb, y0, zb), (xa, y0, za), mat)


def flat_rect(mb, x0, y0, x1, y1, z, mat):
    mb.poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], mat)


def disc(mb, c, r, z, mat, seg=24):
    mb.poly([(x, y, z) for x, y in ngon(seg, r, 0.0, c)], mat)


def emblem(mb, center, radius, yaw=0.0, depth=0.35, tilt=0.0, backing=True):
    """Original academy crest: blue disc, gold ring with three dorm gems, glowing core and a gold
    triangle. Faces local -Y rotated by yaw (same convention as text sockets)."""
    R = radius
    with mb.at(center, rot=yaw, rot_x=90.0 - tilt):
        # local frame: x right, y up, z towards the viewer
        if backing:
            mb.cylinder((0, 0, 0), R, depth, "M_AcademyBlue", seg=32)
        mb.torus((0, 0, depth), R * 0.92, R * 0.075, "M_Gold", seg=40, tube_seg=8)
        mb.cylinder((0, 0, depth), R * 0.64, R * 0.05, "M_EmblemGlow", seg=32, cap_bottom=False)
        zt = depth + R * 0.05 + R * 0.035
        tri = [polar(R * 0.55, 90 + 120 * i) for i in range(3)]
        for i in range(3):
            a, b = tri[i], tri[(i + 1) % 3]
            mb.beam((a[0], a[1], zt), (b[0], b[1], zt), R * 0.085, R * 0.07, "M_Gold")
            gx, gy = polar(R * 0.92, 90 + 120 * i)
            mb.beam((a[0], a[1], zt), (gx * 0.88, gy * 0.88, zt), R * 0.05, R * 0.05, "M_Gold")
        mb.cylinder((0, 0, depth), R * 0.17, R * 0.14, "M_Gold", seg=16, cap_bottom=False)
        for i, m in enumerate(("M_AcademyBlue", "M_AcademyRed", "M_AcademyYellow")):
            gx, gy = polar(R * 0.92, 90 + 120 * i)
            mb.cylinder((gx, gy, depth), R * 0.17, R * 0.11, "M_Gold", seg=16)
            mb.cylinder((gx, gy, depth + R * 0.11), R * 0.12, R * 0.05, m, seg=16, cap_bottom=False)


def roundel(mb, center, yaw, r, mat_core, tilt=0.0):
    with mb.at(center, rot=yaw, rot_x=90.0 - tilt):
        mb.cylinder((0, 0, 0), r, 0.12, "M_Gold", seg=20)
        mb.cylinder((0, 0, 0.12), r * 0.75, 0.05, mat_core, seg=20, cap_bottom=False)
        mb.cylinder((0, 0, 0.17), r * 0.28, 0.06, "M_Gold", seg=12, cap_bottom=False)


def banner(mb, top_center, yaw, w, h, mat, notch=0.7, rod=True):
    """Hanging pennant banner (two-sided) with a gold crest; front faces local -Y rotated by yaw."""
    with mb.at(top_center, rot=yaw):
        pts = [(-w / 2, -h + notch), (0.0, -h), (w / 2, -h + notch), (w / 2, 0.0), (-w / 2, 0.0)]
        mb.poly([(x, -0.004, z) for x, z in pts], mat)
        mb.poly([(x, 0.004, z) for x, z in reversed(pts)], mat)
        # crest (gold ring + core) on both sides
        cz = -min(h * 0.32, w * 0.9)
        rr = w * 0.3
        for side in (-1, 1):
            ring_o = [(math.cos(TA) * rr, cz + math.sin(TA) * rr) for TA in
                      [2 * math.pi * k / 20 for k in range(20)]]
            ring_i = [(math.cos(TA) * rr * 0.72, cz + math.sin(TA) * rr * 0.72) for TA in
                      [2 * math.pi * k / 20 for k in range(20)]]
            yy = side * 0.012
            for k in range(20):
                o0, o1, i0, i1 = ring_o[k], ring_o[(k + 1) % 20], ring_i[k], ring_i[(k + 1) % 20]
                quad = [(o0[0], yy, o0[1]), (o1[0], yy, o1[1]), (i1[0], yy, i1[1]), (i0[0], yy, i0[1])]
                mb.poly(quad if side < 0 else list(reversed(quad)), "M_Gold")
            tri = [(math.cos(TA) * rr * 0.5, cz + math.sin(TA) * rr * 0.5) for TA in
                   (math.pi / 2, math.pi / 2 + 2.0944, math.pi / 2 + 4.1888)]
            mb.poly([(x, yy, z) for x, z in (tri if side < 0 else list(reversed(tri)))], "M_Gold")
        # bottom hem stripe
        if rod:
            mb.beam((-w / 2 - 0.25, 0, 0.06), (w / 2 + 0.25, 0, 0.06), 0.12, 0.12, "M_Gold")
            for sx in (-1, 1):
                mb.box((sx * (w / 2 + 0.3), 0, 0.06), (0.18, 0.18, 0.18), "M_Gold")


def door(mb, pos, yaw, w=2.8, h=3.6, mat="M_AcademyBlue", frame="M_Gold", glass=True):
    """Closed double door on a wall face. pos = bottom centre on the wall face, front = local -Y."""
    hw = w / 2
    with mb.at(pos, rot=yaw):
        for sx in (-1, 1):
            mb.box((sx * hw / 2, -0.06, h / 2), (hw - 0.05, 0.12, h), mat, skip=("+y",))
            if glass:
                mb.box((sx * hw / 2, -0.125, h * 0.68), (hw * 0.55, 0.02, h * 0.38), "M_Glass", skip=("+y",))
            mb.box((sx * 0.16, -0.17, h * 0.45), (0.07, 0.08, 0.6), "M_Gold", skip=("+y",))
        mb.box((-hw - 0.15, -0.12, (h + 0.3) / 2), (0.3, 0.24, h + 0.3), frame, skip=("+y",))
        mb.box((hw + 0.15, -0.12, (h + 0.3) / 2), (0.3, 0.24, h + 0.3), frame, skip=("+y",))
        mb.box((0, -0.12, h + 0.15), (w + 0.6, 0.24, 0.3), frame, skip=("+y",))


def entry_steps(mb, pos, yaw, width, rise_total=FLOOR, landing=1.6, run=0.32, mat="M_AcademyStone"):
    """Landing + steps (riser 0.2 m) in front of a door at `pos` (wall face, ground level)."""
    n = int(round(rise_total / 0.2))
    x, y = pos[0], pos[1]
    with mb.at((x, y, 0.0), rot=yaw):
        mb.box_mm((-width / 2, -landing, -4.0), (width / 2, 0.2, rise_total + 0.01), mat)
        mb.box_mm((-width / 2, -landing - n * run, -4.0), (width / 2, -landing, 0.0), mat)
        mb.stairs((0, -landing - n * run, 0), 90, width, n, rise_total / n, run, mat)
        for sx in (-1, 1):   # cheek walls
            mb.box_mm((sx * (width / 2 + 0.2) - 0.2, -landing - n * run, -4.0),
                      (sx * (width / 2 + 0.2) + 0.2, 0.2, rise_total + 0.9), "M_AcademyWall")
            mb.box_mm((sx * (width / 2 + 0.2) - 0.25, -landing - n * run - 0.05, rise_total + 0.9),
                      (sx * (width / 2 + 0.2) + 0.25, 0.2, rise_total + 1.0), "M_Gold")


def dormer(mb, pos, yaw, eave, slope):
    """Roof dormer on a hip roof slope. pos = point on the wall line at the eave, front = local -Y."""
    with mb.at((pos[0], pos[1], 0.0), rot=yaw):
        y0 = 2.2
        zf = eave + slope * y0
        ztop = zf + 2.1
        y1 = (ztop + 1.0 - eave) / slope
        mb.box_mm((-1.3, y0, zf - 0.8), (1.3, y1, ztop), "M_AcademyWall")
        mb.box((0, y0 - 0.03, zf + 0.95), (1.3, 0.08, 1.4), "M_Glass", skip=("+y",))
        mb.box((0, y0 - 0.06, zf + 0.2), (1.7, 0.14, 0.1), "M_WindowFrame", skip=("+y",))
        mb.box((0, y0 - 0.06, zf + 1.72), (1.5, 0.12, 0.08), "M_WindowFrame", skip=("+y",))
        mb.gable_roof((0, (y0 + y1) / 2, ztop), 2.6, y1 - y0, 1.0, "M_AcademyRoof",
                      overhang=0.25, thick=0.12, gable_mat="M_AcademyWall", ridge_axis="y")


def garden_bed(mb, aset, pts, flowers, tree="SM_BroadTree_C", palms=()):
    """Raised garden: stone edging with marble cap, lawn, clipped hedge ring, flower rosette island."""
    n = len(pts)
    for i in range(n):
        mb.wall(pts[i], pts[(i + 1) % n], -0.3, 0.85, 0.45, "M_AcademyStone", cap_mat="M_Marble")
    mb.prism(inset_poly(pts, 0.44), -0.3, 0.38, "M_Soil", top_mat="M_PlazaLawn", cap_bottom=False)
    mb.slab_ring(inset_poly(pts, 0.5), inset_poly(pts, 1.3), 0.38, 1.05, "M_Hedge")
    cx = sum(p[0] for p in pts) / n
    cy = sum(p[1] for p in pts) / n
    ring_sector(mb, (cx, cy), 3.0, 3.4, 0.0, 360.0, 0.38, 0.75, "M_Marble", faces="tio", n=24)
    mb.cylinder((cx, cy, 0.38), 3.0, 0.3, "M_Soil", seg=24, cap_bottom=False)
    for k in range(12):
        a0 = k * 30.0
        ring_sector(mb, (cx, cy), 4.8, 7.2, a0 + 1.5, a0 + 28.5, 0.38, 0.6, flowers[k % 2], faces="tioab", n=4)
    aset.prop(tree, (cx, cy, 0.68), 0.0)
    for (px, py) in palms:
        aset.prop("SM_PalmTree_B", (px, py, 0.38), (px * 7 + py * 3) % 360)


# ============================================================================ ACADEMY
def _podium_and_steps(mb):
    # lobby + portico podium (floor of the walkable interior route)
    mb.box_mm((-LX, LY0, -4.0), (LX, LY1, FLOOR), "M_AcademyStone", mats={"+z": "M_MarbleFloor"})
    mb.box_mm((-25.0, -76.0, -4.0), (25.0, LY0, FLOOR), "M_AcademyStone")
    # gold inlay line at the portico threshold
    mb.box_mm((-25.0, -76.05, FLOOR - 0.06), (25.0, -75.85, FLOOR + 0.005), "M_Gold")
    # monumental front steps: 10 x 0.2 m risers, 0.6 m treads
    mb.box_mm((-25.0, -82.0, -4.0), (25.0, -76.0, 0.0), "M_AcademyStone")
    mb.stairs((0.0, -82.0, 0.0), 90, 50.0, 10, 0.2, 0.6, "M_AcademyStone")
    # stair cheeks with lamp pedestals
    for s in (-1, 1):
        xa, xb = sorted((s * 25.0, s * 29.5))
        mb.box_mm((xa, -82.0, -4.0), (xb, LY0, FLOOR + 0.9), "M_AcademyStone")
        mb.box_mm((xa - 0.1, -82.1, FLOOR + 0.9), (xb + 0.1, LY0, FLOOR + 1.05), "M_Gold")
        # pedestal with a small obelisk lamp
        cx = s * 27.25
        mb.box_mm((cx - 1.3, -81.6, FLOOR + 1.05), (cx + 1.3, -79.0, FLOOR + 2.4), "M_AcademyWall")
        mb.box_mm((cx - 1.4, -81.7, FLOOR + 2.4), (cx + 1.4, -78.9, FLOOR + 2.6), "M_AcademyBlue")
        mb.lathe([(0.75 * SQ2, FLOOR + 2.6), (0.45 * SQ2, FLOOR + 6.4)], "M_AcademyWall", seg=4,
                 angle0=math.pi / 4, smooth=False, center=(cx, -80.3, 0.0), cap_bottom=False)
        mb.box_mm((cx - 0.55, -80.85, FLOOR + 6.4), (cx + 0.55, -79.75, FLOOR + 7.3), "M_LampGlow")
        mb.pyramid((cx, -80.3, FLOOR + 7.3), 1.3, 1.3, 1.1, "M_Gold")


def _lobby_shell(mb):
    split = 9.0                       # wall built in two layers so windows can stack
    win = dict(glass="M_Glass", frame="M_WindowFrame")
    low = {0: [dict(u=LX, w=10.0, z0=0.0, z1=split)], 1: [], 2: [dict(u=LX, w=12.0, z0=0.0, z1=split)], 3: []}
    up = {0: [], 1: [], 2: [], 3: []}
    for x in (11.0, 19.0, 26.8):
        for sx in (-1, 1):
            w = 3.0 if x < 26 else 2.4
            low[0].append(dict(u=LX + sx * x, w=w, z0=1.6, z1=6.8, **win))
            up[0].append(dict(u=LX + sx * x, w=w, z0=0.6, z1=4.4, **win))
    t = LWALL
    for y in (-51.0, -39.0):
        low[1].append(dict(u=y - (LY0 + t), w=2.6, z0=1.6, z1=6.8, **win))
        low[3].append(dict(u=(LY1 - t) - y, w=2.6, z0=1.6, z1=6.8, **win))
    for y in (-57.0, -45.0, -33.0):
        up[1].append(dict(u=y - (LY0 + t), w=2.6, z0=0.6, z1=4.4, **win))
        up[3].append(dict(u=(LY1 - t) - y, w=2.6, z0=0.6, z1=4.4, **win))
    # front/back walls run full width, side walls butt between them (no coplanar corner overlaps)
    segs = [((-LX, LY0), (LX, LY0)), ((LX, LY0 + t), (LX, LY1 - t)), ((LX, LY1), (-LX, LY1)),
            ((-LX, LY1 - t), (-LX, LY0 + t))]
    for z0, hh, ops in ((FLOOR, split, low), (FLOOR + split, LTOP - FLOOR - split, up)):
        for i, (a, b) in enumerate(segs):
            mb.wall(a, b, z0, hh, t, "M_AcademyWall", openings=ops[i])
    # ceiling slab
    mb.box_mm((-LX + LWALL, LY0 + LWALL, LCEIL), (LX - LWALL, LY1 - LWALL, LCEIL + 1.0), "M_AcademyWall")
    # exterior trims: base band, gold line, blue cornice
    rect_band(mb, -LX, LY0, LX, LY1, FLOOR, FLOOR + 0.45, 0.12, "M_AcademyBlue", sides="ew")
    rect_band(mb, -LX, LY0, LX, LY1, 16.2, 16.45, 0.25, "M_Gold", sides="sew")
    rect_band(mb, -LX, LY0, LX, LY1, 16.45, 18.0, 0.45, "M_AcademyBlue", sides="sew")
    # pilasters on the side walls
    for s in (-1, 1):
        for y in (-63.0, -45.0, -27.0):
            xa, xb = sorted((s * LX, s * (LX + 0.35)))
            mb.box_mm((xa, y - 0.6, FLOOR), (xb, y + 0.6, 16.2), "M_AcademyWall")
    # hipped roof over the entrance hall
    cy = (LY0 + LY1) / 2
    mb.hip_roof((0.0, cy, LTOP), 2 * LX, LY1 - LY0, 5.0, "M_AcademyRoof", overhang=1.0)
    r = (2 * LX - (LY1 - LY0)) / 2
    mb.beam((-r, cy, LTOP + 5.0), (r, cy, LTOP + 5.0), 0.4, 0.4, "M_Gold")
    # threshold strips in the portal passages
    mb.box_mm((-6.0, LY1 - LWALL, FLOOR), (6.0, LY1 + DT, FLOOR + 0.02), "M_MarbleFloor")
    mb.box_mm((-5.0, LY0, FLOOR), (5.0, LY0 + LWALL, FLOOR + 0.02), "M_Gold")


def _portico(mb, aset):
    yc = -73.0
    ch = 13.0                                   # column height (z 2..15)
    ze = FLOOR + ch
    for x in (7.0, 15.0, 23.0):
        for s in (-1, 1):
            mb.column((s * x, yc, FLOOR), 0.9, ch, "M_AcademyWall", seg=16, cap_mat="M_Gold")
            # antae on the facade behind each column
            mb.box_mm((s * x - 0.9, LY0 - 0.4, FLOOR), (s * x + 0.9, LY0, ze), "M_AcademyWall")
    # entrance surround (gold) on the facade
    mb.box_mm((-5.6, LY0 - 0.25, FLOOR), (-5.0, LY0 + 0.02, 11.6), "M_Gold")
    mb.box_mm((5.0, LY0 - 0.25, FLOOR), (5.6, LY0 + 0.02, 11.6), "M_Gold")
    mb.box_mm((-5.6, LY0 - 0.25, 11.0), (5.6, LY0 + 0.02, 11.6), "M_Gold")
    mb.box_mm((-4.5, LY0 - 0.3, 12.1), (4.5, LY0, 13.7), "M_AcademyBlue")   # transom plaque
    mb.box_mm((-4.6, LY0 - 0.35, 11.95), (4.6, LY0, 12.1), "M_Gold")
    mb.box_mm((-4.6, LY0 - 0.35, 13.7), (4.6, LY0, 13.85), "M_Gold")
    # entablature
    mb.box_mm((-25.5, -75.8, ze), (25.5, LY0, ze + 1.0), "M_AcademyWall")
    mb.box_mm((-25.5, -75.85, ze + 1.0), (25.5, LY0, ze + 1.15), "M_Gold")
    mb.box_mm((-25.3, -75.6, ze + 1.15), (25.3, LY0, ze + 2.55), "M_AcademyBlue")
    mb.box_mm((-26.2, -76.6, ze + 2.55), (26.2, LY0, ze + 3.3), "M_AcademyWall")
    mb.box_mm((-26.25, -76.65, ze + 3.3), (26.25, LY0, ze + 3.45), "M_Gold")
    # coffer beams under the portico ceiling
    mb.box_mm((-25.0, -70.4, ze - 0.6), (25.0, -69.6, ze), "M_AcademyBlue")
    for x in (-19.0, -11.0, -3.0, 3.0, 11.0, 19.0):
        mb.box_mm((x - 0.3, -75.6, ze - 0.5), (x + 0.3, LY0, ze), "M_AcademyBlue")
    # stepped attic carrying the crest
    za = ze + 3.45
    mb.box_mm((-11.5, -75.6, za), (11.5, LY0, za + 5.0), "M_AcademyWall")
    mb.box_mm((-11.6, -75.7, za + 5.0), (11.6, LY0, za + 5.2), "M_Gold")
    mb.box_mm((-7.5, -75.0, za + 5.2), (7.5, LY0, za + 7.0), "M_AcademyWall")
    mb.box_mm((-7.6, -75.1, za + 7.0), (7.6, LY0, za + 7.2), "M_Gold")
    mb.box_mm((-3.5, -74.5, za + 7.2), (3.5, LY0, za + 8.0), "M_AcademyBlue")
    mb.box_mm((-3.6, -74.6, za + 8.0), (3.6, LY0, za + 8.15), "M_Gold")
    emblem(mb, (0.0, -75.6, za + 3.2), 3.3, yaw=0.0, depth=0.4)
    for s in (-1, 1):
        xa, xb = sorted((s * 11.5, s * 18.0))
        mb.prism([(xa, -75.6), (xb, -75.6), (xb, LY0), (xa, LY0)], za, za + 0.9, "M_AcademyWall")
        mb.box_mm((xa, -75.7, za + 0.9), (xb, LY0, za + 1.05), "M_Gold")
    aset.text("DUEL ACADEMY", (0.0, -75.63, ze + 1.85), 0.0, size=1.1, color=(1.0, 0.82, 0.35), emissive=True)
    aset.text("WELCOME, DUELISTS", (0.0, LY0 - 0.33, 12.9), 0.0, size=0.55, color=(1.0, 0.85, 0.4))


def _drum(mb, nocol):
    pts = ngon(16, DR, DA0, DC)
    win_faces = {45.0, 67.5, 90.0, 112.5, 135.0, 225.0, 247.5, 292.5, 315.0}
    low_faces = {45.0, 135.0, 225.0, 247.5, 292.5, 315.0}
    for i in range(16):
        a, b = pts[i], pts[(i + 1) % 16]
        mid = (22.5 * (i + 1)) % 360.0
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        ops = []
        if abs(mid - 270.0) < 0.1:
            ops = [dict(u=L / 2, w=12.0, z0=FLOOR + 4.0, z1=FLOOR + 4.0 + 9.0)]
        mb.wall(a, b, -4.0, DH + 4.0, DT, "M_AcademyWall", openings=ops)
        if mid in win_faces:
            mb.facade_windows(a, b, [12.6], 2, 2.2, 8.6)
        if mid in low_faces:
            mb.facade_windows(a, b, [4.0], 2, 1.8, 4.4)
        # frieze roundels
        roundel(mb, (*polar(DAPO + 0.18, mid, DC), 25.4), mid + 90.0, 1.25, "M_AcademyYellow"
                if mid in (270.0,) else "M_AcademyBlue")
    # pilasters at the vertices
    for i in range(16):
        ang = DA0 + 22.5 * i
        vx, vy = polar(DR, ang, DC)
        with mb.at((vx, vy, 0.0), rot=ang):
            mb.box((-0.05, 0.0, (FLOOR + 22.8) / 2), (0.8, 1.7, 22.8 - FLOOR), "M_AcademyWall")
            mb.box((0.0, 0.0, 22.2), (0.95, 1.9, 0.5), "M_Gold")
    # horizontal bands
    drum_band(mb, DR + 0.4, DR - 0.6, -4.0, FLOOR - 0.1, "M_AcademyStone")
    drum_band(mb, DR + 0.3, DR - 0.6, 22.8, 23.15, "M_Gold")
    drum_band(mb, DR + 0.18, DR - 0.6, 23.15, 27.6, "M_AcademyBlue")
    drum_band(mb, DR + 0.3, DR - 0.6, 27.6, 27.9, "M_Gold")
    drum_band(mb, DR + 1.3, DR - 0.6, 27.9, 29.3, "M_AcademyRoof")
    drum_band(mb, DR + 0.25, DR - 0.6, 29.3, 29.5, "M_Gold")
    drum_band(mb, DR + 0.15, DR - 0.6, DH - 0.1, DH + 0.15, "M_AcademyBlue")
    # roof slab ring with the square oculus (ceiling of the arena)
    outer = drum_pts32(DR - 0.6)
    inner = [square_pt(OCULUS, k * 11.25, DC) for k in range(32)]
    ring_between(mb, outer, inner, ROOF_Z, ROOF_Z + 1.0, top="M_AcademyRoof", bottom="M_AcademyBlue",
                 side="M_AcademyWall", outer_side=False)


def _pyramid(mb):
    cx, cy = DC
    z = ROOF_Z + 1.0
    steps, rise, inset = 7, 3.6, 2.5
    for i in range(steps):
        ho = 26.0 - inset * i
        square_frame(mb, cx, cy, z, z + rise, ho, OCULUS, "M_AcademyRoof", inner_mat="M_AcademyWall")
        rect_band(mb, cx - ho, cy - ho, cx + ho, cy + ho, z + rise - 0.4, z + rise, 0.1, "M_Gold")
        # small blue-glass slits on each riser (Egyptian rhythm)
        if i < steps - 1:
            nwin = max(2, int(ho * 2 / 6.0))
            for k in range(4):
                ang = -90.0 + 90.0 * k
                with mb.at((cx, cy, 0.0), rot=ang + 90.0):
                    # local -Y faces outward
                    for j in range(nwin):
                        u = -ho + (j + 0.5) * (2 * ho / nwin)
                        mb.box((u, -ho - 0.04, z + rise * 0.45), (0.9, 0.1, rise * 0.5), "M_Glass")
                        mb.box((u, -ho - 0.07, z + rise * 0.45 + rise * 0.25 + 0.06),
                               (1.2, 0.14, 0.12), "M_Gold")
        z += rise
    # glass apex
    top = z
    hb = 26.0 - inset * (steps - 1)
    H = 13.0
    apex = (cx, cy, top + H)
    mb.pyramid((cx, cy, top), hb * 2, hb * 2, H, "M_GlassClear", base=False)
    corners = [(cx - hb, cy - hb), (cx + hb, cy - hb), (cx + hb, cy + hb), (cx - hb, cy + hb)]
    for (x, y) in corners:
        mb.beam((x, y, top), apex, 0.45, 0.45, "M_Gold")
    for k in range(4):
        (x0, y0), (x1, y1) = corners[k], corners[(k + 1) % 4]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        mb.beam((mx, my, top), apex, 0.25, 0.25, "M_Gold")
        for t in (0.33, 0.62):
            pa = (x0 + (cx - x0) * t, y0 + (cy - y0) * t, top + H * t)
            pb = (x1 + (cx - x1) * t, y1 + (cy - y1) * t, top + H * t)
            mb.beam(pa, pb, 0.25, 0.25, "M_Gold")
    cap_h = 3.3
    cap_w = hb * 2 * (cap_h - 0.1) / H + 0.35
    mb.pyramid((cx, cy, top + H - cap_h + 0.1), cap_w, cap_w, cap_h + 0.25, "M_Gold")


def _wing_facade_common(mb, xa, xb, y0, y1, eave, roof_h, ridge_axis="x"):
    mb.box_mm((xa, y0, -4.0), (xb, y1, eave - 1.4), "M_AcademyWall")
    rect_band(mb, xa, y0, xb, y1, -4.0, FLOOR, 0.25, "M_AcademyStone")
    for z in (6.4, 10.9, 15.4):
        rect_band(mb, xa, y0, xb, y1, z, z + 0.2, 0.16, "M_AcademyBlue")
    rect_band(mb, xa, y0, xb, y1, eave - 1.4, eave - 1.15, 0.3, "M_Gold")
    rect_band(mb, xa, y0, xb, y1, eave - 1.15, eave, 0.7, "M_AcademyBlue")
    cx, cy = (xa + xb) / 2, (y0 + y1) / 2
    w, d = xb - xa, y1 - y0
    if ridge_axis == "x":
        mb.hip_roof((cx, cy, eave), w, d, roof_h, "M_AcademyRoof", overhang=1.0)
        r = max(0.0, (w - d) / 2)
        mb.beam((cx - r, cy, eave + roof_h), (cx + r, cy, eave + roof_h), 0.4, 0.4, "M_Gold")
    else:
        with mb.at((cx, cy, eave), rot=90):
            mb.hip_roof((0, 0, 0), d, w, roof_h, "M_AcademyRoof", overhang=1.0)
            r = max(0.0, (d - w) / 2)
            mb.beam((-r, 0, roof_h), (r, 0, roof_h), 0.4, 0.4, "M_Gold")


ROWS = [3.0, 7.5, 12.0, 16.5]


RM = DR - DT / 2                  # drum mid-wall vertex radius (37.4)


def drum_mid_x(y, face_mid):
    """x on the drum mid-wall plane of the face centred at `face_mid` (deg) for a given y."""
    ca, sa = math.cos(face_mid * D2R), math.sin(face_mid * D2R)
    return DC[0] + (RM * COS_H - (y - DC[1]) * sa) / ca


def drum_mid_y(x, face_mid):
    ca, sa = math.cos(face_mid * D2R), math.sin(face_mid * D2R)
    return DC[1] + (RM * COS_H - (x - DC[0]) * ca) / sa


def _wings(mb, nocol):
    """Classroom wings E/W of the drum. Their inner end follows the drum mid-wall so nothing pokes
    into the arena."""
    y0, y1, xo, eave, rh = 2.0, 28.0, 88.5, 20.5, 6.5
    xa_ = drum_mid_x(y0, -22.5)
    v1 = polar(RM, -11.25, DC)
    v2 = polar(RM, 11.25, DC)
    base = [(xa_, y0), (xo, y0), (xo, y1), (xa_, y1), v2, v1]
    for s in (-1, 1):
        pts = [(x * s, y) for x, y in base]
        if s < 0:
            pts.reverse()
        mb.prism(pts, -4.0, eave - 1.4, "M_AcademyWall", cap_top=False, cap_bottom=False)
        bx0, bx1 = sorted((s * 34.7, s * xo))
        side_out = "e" if s > 0 else "w"
        rect_band(mb, bx0, y0, bx1, y1, -4.0, FLOOR, 0.25, "M_AcademyStone", sides="sn" + side_out)
        for z in (6.4, 10.9, 15.4):
            rect_band(mb, bx0, y0, bx1, y1, z, z + 0.2, 0.16, "M_AcademyBlue", sides="sn" + side_out)
        rect_band(mb, bx0, y0, bx1, y1, eave - 1.4, eave - 1.15, 0.3, "M_Gold", sides="sn" + side_out)
        rect_band(mb, bx0, y0, bx1, y1, eave - 1.15, eave, 0.7, "M_AcademyBlue", sides="sn" + side_out)
        # hip roof starts just inside the drum wall (overhang 1 m)
        ra, rb = sorted((s * 37.2, s * xo))
        cx, w = (ra + rb) / 2, rb - ra
        mb.hip_roof((cx, (y0 + y1) / 2, eave), w, y1 - y0, rh, "M_AcademyRoof", overhang=1.0)
        r = (w - (y1 - y0)) / 2
        mb.beam((cx - r, (y0 + y1) / 2, eave + rh), (cx + r, (y0 + y1) / 2, eave + rh), 0.4, 0.4, "M_Gold")
        # windows (only on the free part of the facade)
        wa, wb = sorted((s * 40.0, s * 88.0))
        n = 14
        mb.facade_windows((wa, y0), (wb, y0), ROWS, n, 1.7, 2.5)
        mb.facade_windows((wb, y1), (wa, y1), ROWS, n, 1.7, 2.5)
        bay = (wb - wa) / n
        for k in range(0, n + 1, 2):
            x = wa + k * bay
            mb.box_mm((x - 0.45, y0 - 0.35, FLOOR), (x + 0.45, y0 + 0.1, 19.1), "M_AcademyWall")
            mb.box_mm((x - 0.45, y1 - 0.1, FLOOR), (x + 0.45, y1 + 0.35, 19.1), "M_AcademyWall")
        # roof dormers on both long slopes
        for x in (47.5, 54.4, 68.1, 75.0):
            dormer(mb, (s * x, y0), 0.0, eave, rh / 13.0)
            dormer(mb, (s * x, y1), 180.0, eave, rh / 13.0)
        # central door with steps
        xd = s * 64.0
        mb.box_mm((xd - 2.4, y0 - 0.3, FLOOR), (xd + 2.4, y0 + 0.1, 6.0), "M_AcademyBlue")
        door(mb, (xd, y0 - 0.3, FLOOR), 0.0, 2.8, 3.4)
        entry_steps(mb, (xd, y0 - 0.3), 0.0, 4.2)
        # dorm banners on the pilasters
        cols = ("M_AcademyRed", "M_AcademyYellow") if s < 0 else ("M_AcademyBlue", "M_AcademyYellow")
        for j, xx in enumerate((s * 53.71, s * 74.29)):
            banner(nocol, (xx, y0 - 0.5, 18.6), 0.0, 2.2, 9.0, cols[j])


def _end_blocks(mb):
    y0, y1 = -40.0, 50.0
    for s in (-1, 1):
        xa, xb = sorted((s * 88.0, s * 114.0))
        _wing_facade_common(mb, xa, xb, y0, y1, 22.4, 8.0, ridge_axis="y")
        xo, xi = s * 114.0, s * 88.0
        rows = ROWS + [19.6]
        if s > 0:
            mb.facade_windows((xo, y0), (xo, y1), rows, 26, 1.7, 2.5)
            mb.facade_windows((xi, 2.0), (xi, y0), rows, 12, 1.7, 2.5)
            mb.facade_windows((xi, y1), (xi, 28.0), rows, 6, 1.7, 2.5)
            segs_s = [((88.0, y0), (94.0, y0)), ((108.0, y0), (114.0, y0))]
            segs_n = [((94.0, y1), (88.0, y1)), ((114.0, y1), (108.0, y1))]
        else:
            mb.facade_windows((xo, y1), (xo, y0), rows, 26, 1.7, 2.5)
            mb.facade_windows((xi, y0), (xi, 2.0), rows, 12, 1.7, 2.5)
            mb.facade_windows((xi, 28.0), (xi, y1), rows, 6, 1.7, 2.5)
            segs_s = [((-114.0, y0), (-108.0, y0)), ((-94.0, y0), (-88.0, y0))]
            segs_n = [((-108.0, y1), (-114.0, y1)), ((-88.0, y1), (-94.0, y1))]
        for p0, p1 in segs_s + segs_n:
            mb.facade_windows(p0, p1, rows, 1, 1.7, 2.5)
        # pilasters on the forecourt face
        for k in range(0, 13, 3):
            y = y0 + k * (2.0 - y0) / 12
            xa_, xb_ = sorted((xi, xi - s * 0.35))
            mb.box_mm((xa_, y - 0.45, FLOOR), (xb_, y + 0.45, 21.0), "M_AcademyWall")
        # roof dormers (outer slope + forecourt slope)
        sl = 8.0 / 13.0
        for y in (-26.0, -14.0, -2.0, 10.0, 22.0, 34.0):
            dormer(mb, (xo, y), 90.0 * s, 22.4, sl)
        for y in (-26.0, -12.0, 38.0):
            dormer(mb, (xi, y), -90.0 * s, 22.4, sl)
        # side door into the forecourt
        yd = -19.0
        with mb.at((xi, yd, 0.0), rot=-90.0 * s):
            mb.box((0.0, -0.15, 4.0), (4.8, 0.3, 4.0), "M_AcademyBlue")
        door(mb, (xi - s * 0.3, yd, FLOOR), -90.0 * s, 2.8, 3.4)
        entry_steps(mb, (xi - s * 0.3, yd), -90.0 * s, 4.2)


def _rear_annex(mb):
    """Two-storey service annex behind the arena (flat roof); its south side follows the drum wall."""
    xa, xb, y1, top = -20.0, 20.0, 76.0, 10.0
    ys = drum_mid_y(xb, 67.5)
    w1, e1 = polar(RM, 101.25, DC), polar(RM, 78.75, DC)
    pts = [(xa, ys), w1, e1, (xb, ys), (xb, y1), (xa, y1)]
    mb.prism(pts, -4.0, top, "M_AcademyWall", cap_top=False, cap_bottom=False)
    for piece in ([(xa, ys), w1, (w1[0], y1), (xa, y1)], [w1, e1, (e1[0], y1), (w1[0], y1)],
                  [e1, (xb, ys), (xb, y1), (e1[0], y1)]):
        mb.poly([(x, y, top) for x, y in piece], "M_AcademyRoof")
    yb = 47.2
    rect_band(mb, xa, yb, xb, y1, -4.0, FLOOR, 0.25, "M_AcademyStone", sides="enw")
    rect_band(mb, xa, yb, xb, y1, 6.4, 6.6, 0.16, "M_AcademyBlue", sides="enw")
    rect_band(mb, xa, yb, xb, y1, 8.6, 8.85, 0.3, "M_Gold", sides="enw")
    rect_band(mb, xa, yb, xb, y1, 8.85, top + 1.0, 0.45, "M_AcademyBlue", sides="enw")
    rect_band(mb, xa, yb, xb, y1, top + 1.0, top + 1.15, 0.5, "M_Gold", sides="enw")
    # rooftop: parapet railing and plant
    mb.railing([(xb - 0.3, yb + 1.0, top), (xb - 0.3, y1 - 0.3, top), (xa + 0.3, y1 - 0.3, top),
                (xa + 0.3, yb + 1.0, top)], 1.1, "M_Metal", post_spacing=2.5)
    for x, y in ((-10.0, 64.0), (10.0, 64.0), (0.0, 70.0)):
        mb.box_mm((x - 2.0, y - 1.4, top), (x + 2.0, y + 1.4, top + 1.5), "M_Metal")
        mb.box_mm((x - 1.3, y - 0.8, top + 1.5), (x + 1.3, y + 0.8, top + 1.8), "M_DarkMetal")
    mb.facade_windows((xb, y1), (3.2, y1), [3.0], 4, 1.7, 2.5)
    mb.facade_windows((-3.2, y1), (xa, y1), [3.0], 4, 1.7, 2.5)
    mb.facade_windows((xb, y1), (xa, y1), [7.0], 9, 1.7, 1.6)
    mb.facade_windows((xb, 54.0), (xb, y1), [3.0, 7.0], 5, 1.7, 2.0)
    mb.facade_windows((xa, y1), (xa, 54.0), [3.0, 7.0], 5, 1.7, 2.0)
    # rear entrance (closed) with canopy
    door(mb, (0.0, y1, FLOOR), 180.0, 2.8, 3.4)
    entry_steps(mb, (0.0, y1), 180.0, 5.0)
    mb.box_mm((-3.4, y1, 5.9), (3.4, y1 + 2.4, 6.25), "M_AcademyBlue")
    mb.box_mm((-3.5, y1, 6.25), (3.5, y1 + 2.5, 6.4), "M_Gold")
    for sx in (-1, 1):
        mb.cylinder((sx * 3.0, y1 + 2.0, FLOOR), 0.18, 3.9, "M_Gold", seg=10)


def _tower(mb, nocol, aset, cx, cy, accent, front):
    h = 6.0
    zt = 11.0
    mb.box_mm((cx - h, cy - h, -4.0), (cx + h, cy + h, zt), "M_AcademyWall")
    rect_band(mb, cx - h, cy - h, cx + h, cy + h, -4.0, FLOOR - 1.0, 0.3, "M_AcademyStone")
    rect_band(mb, cx - h, cy - h, cx + h, cy + h, 8.3, 9.5, 0.18, "M_AcademyBlue")
    rect_band(mb, cx - h, cy - h, cx + h, cy + h, 9.5, 9.75, 0.3, "M_Gold")
    rect_band(mb, cx - h, cy - h, cx + h, cy + h, 9.75, zt, 0.65, "M_AcademyRoof")
    # balcony railing around the shaft
    e = h - 0.3
    mb.railing([(cx - e, cy - e, zt), (cx + e, cy - e, zt), (cx + e, cy + e, zt), (cx - e, cy + e, zt),
                (cx - e, cy - e, zt)], 1.1, "M_Gold", post_spacing=1.7)
    # door on the outer face, windows on the sides
    fy = cy - h if front else cy + h
    door(mb, (cx, fy, 0.0), 0.0 if front else 180.0, 3.0, 3.8)
    for p0, p1 in (((cx + h, cy - h), (cx + h, cy + h)), ((cx - h, cy + h), (cx - h, cy - h))):
        mb.facade_windows(p0, p1, [3.0], 3, 1.4, 3.6)
    # tapered obelisk shaft
    z0, z1 = zt, 47.0
    b0, b1 = 4.1, 2.5

    def half(z):
        return b0 + (b1 - b0) * (z - z0) / (z1 - z0)

    mb.lathe([(b0 * SQ2, z0), (b1 * SQ2, z1)], "M_AcademyWall", seg=4, angle0=math.pi / 4,
             center=(cx, cy, 0.0), smooth=False, cap_bottom=False)
    tilt = math.degrees(math.atan((b0 - b1) / (z1 - z0)))
    for m in (-90.0, 0.0, 90.0, 180.0):
        pa = polar(half(13.0) + 0.02, m, (cx, cy))
        pb = polar(half(31.5) + 0.02, m, (cx, cy))
        mb.beam((pa[0], pa[1], 13.0), (pb[0], pb[1], 31.5), 0.8, 0.12, "M_AcademyBlue")
        roundel(mb, (*polar(half(35.5), m, (cx, cy)), 35.5), m + 90.0, 1.25, accent, tilt=tilt)
    for za, zb, mat, extra in ((39.5, 41.8, "M_AcademyBlue", 0.12), (41.8, 42.15, "M_Gold", 0.2),
                               (46.3, 47.2, "M_Gold", 0.22)):
        hh = half(za) + extra
        mb.box_mm((cx - hh, cy - hh, za), (cx + hh, cy + hh, zb), mat)
    hp = half(47.0) + 0.3
    mb.pyramid((cx, cy, 47.2), hp * 2, hp * 2, 5.8, "M_Gold")
    aset.light((cx, cy - (h + 3.0) * (1 if front else -1), 45.0), (1.0, 0.8, 0.45), 9000, 22,
               night_only=True)


def _towers(mb, nocol, aset):
    _tower(mb, nocol, aset, -101.0, -46.0, "M_AcademyRed", True)
    _tower(mb, nocol, aset, 101.0, -46.0, "M_AcademyYellow", True)
    _tower(mb, nocol, aset, -101.0, 56.0, "M_AcademyBlue", False)
    _tower(mb, nocol, aset, 101.0, 56.0, "M_AcademyBlue", False)


# ---------------------------------------------------------------------------- interior: lobby
def _lobby_interior(mb, nocol, aset):
    inx = LX - LWALL
    # columns
    col_y = (-59.0, -51.0, -43.0, -35.0, -27.0)
    for s in (-1, 1):
        for y in col_y:
            mb.column((s * 11.0, y, FLOOR), 0.9, LCEIL - FLOOR, "M_AcademyWall", seg=16, cap_mat="M_Gold")
    # ceiling beams (blue with gold soffit line)
    for s in (-1, 1):
        mb.box_mm((s * 11.0 - 0.7, LY0 + LWALL, LCEIL - 0.9), (s * 11.0 + 0.7, LY1 - LWALL, LCEIL), "M_AcademyBlue")
        mb.box_mm((s * 11.0 - 0.35, LY0 + LWALL, LCEIL - 1.0), (s * 11.0 + 0.35, LY1 - LWALL, LCEIL - 0.9), "M_Gold")
    for y in col_y:
        mb.box_mm((-inx, y - 0.5, LCEIL - 0.7), (inx, y + 0.5, LCEIL), "M_AcademyBlue")
    # floor: nave border strips + academy crest inlay
    for s in (-1, 1):
        xa, xb = sorted((s * 8.6, s * 9.2))
        mb.box_mm((xa, LY0 + LWALL, FLOOR), (xb, LY1 - LWALL, FLOOR + 0.012), "M_AcademyBlue")
    ec = (0.0, -44.0)
    mb.cylinder((*ec, FLOOR), 4.4, 0.01, "M_Gold", seg=40, cap_bottom=False)
    mb.cylinder((*ec, FLOOR), 4.1, 0.02, "M_AcademyBlue", seg=40, cap_bottom=False)
    mb.cylinder((*ec, FLOOR), 2.5, 0.025, "M_Gold", seg=40, cap_bottom=False)
    mb.cylinder((*ec, FLOOR), 2.3, 0.03, "M_MarbleFloor", seg=40, cap_bottom=False)
    tri = [polar(2.1, 90 + 120 * i, ec) for i in range(3)]
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        mb.beam((a[0], a[1], FLOOR + 0.035), (b[0], b[1], FLOOR + 0.035), 0.22, 0.02, "M_Gold")
    for i, m in enumerate(("M_AcademyBlue", "M_AcademyRed", "M_AcademyYellow")):
        g = polar(3.3, 90 + 120 * i, ec)
        mb.cylinder((*g, FLOOR), 0.45, 0.03, m, seg=16, cap_bottom=False)
    # wainscot on the long walls
    for s in (-1, 1):
        xa, xb = sorted((s * inx, s * (inx - 0.06)))
        mb.box_mm((xa, LY0 + LWALL, FLOOR), (xb, -61.5, FLOOR + 1.2), "M_AcademyBlue")
        mb.box_mm((xa, -29.0 + 2.0, FLOOR), (xb, LY1 - LWALL, FLOOR + 1.2), "M_AcademyBlue")
    # arena portal surround (lobby side) + sign
    yb = LY1 - LWALL
    mb.box_mm((-6.6, yb - 0.3, FLOOR), (-6.0, yb, 11.6), "M_Gold")
    mb.box_mm((6.0, yb - 0.3, FLOOR), (6.6, yb, 11.6), "M_Gold")
    mb.box_mm((-6.6, yb - 0.3, 11.0), (6.6, yb, 11.6), "M_Gold")
    mb.box_mm((-7.5, yb - 0.3, 12.2), (7.5, yb, 14.0), "M_AcademyBlue")
    mb.box_mm((-7.6, yb - 0.35, 12.05), (7.6, yb, 12.2), "M_Gold")
    mb.box_mm((-7.6, yb - 0.35, 14.0), (7.6, yb, 14.15), "M_Gold")
    aset.text("GRAND DUEL ARENA", (0.0, yb - 0.33, 13.1), 0.0, size=0.95, color=(1.0, 0.85, 0.4), emissive=True)
    # pendant ring chandeliers
    for y in (-55.0, -44.0, -33.0):
        mb.torus((0.0, y, 11.0), 2.4, 0.14, "M_Gold", seg=28, tube_seg=6)
        mb.torus((0.0, y, 10.75), 2.1, 0.12, "M_LampGlow", seg=28, tube_seg=6)
        mb.cylinder((0.0, y, 10.1), 0.5, 0.9, "M_LampGlow", seg=12)
        for k in range(3):
            px, py = polar(2.4, 90 + 120 * k, (0.0, y))
            mb.beam((px, py, 11.0), (0.0, y, LCEIL - 0.1), 0.05, 0.05, "M_Gold")
        aset.light((0.0, y, 9.5), (1.0, 0.88, 0.7), 9000, 24)
    for s in (-1, 1):
        for y in (-55.0, -33.0):
            aset.light((s * 20.0, y, 11.0), (1.0, 0.9, 0.75), 5000, 16)
    # dorm banners hanging between the columns, facing the nave
    west = ("M_AcademyRed", "M_AcademyYellow", "M_AcademyBlue", "M_AcademyRed")
    east = ("M_AcademyBlue", "M_AcademyYellow", "M_AcademyRed", "M_AcademyBlue")
    for s, cols in ((-1, west), (1, east)):
        for y, m in zip((-55.0, -47.0, -39.0, -31.0), cols):
            banner(nocol, (s * 11.0, y, LCEIL - 1.1), 90.0 if s < 0 else -90.0, 2.6, 7.4, m)
    # reception (west side)
    x0 = -21.0
    mb.box_mm((x0, -50.0, FLOOR), (x0 + 1.0, -40.0, FLOOR + 1.1), "M_Wood", mats={"+x": "M_AcademyBlue"})
    for y in (-51.0, -40.0):
        mb.box_mm((-24.5, y, FLOOR), (x0 + 1.0, y + 1.0, FLOOR + 1.1), "M_Wood",
                  mats={"+x": "M_AcademyBlue", "-y": "M_AcademyBlue", "+y": "M_AcademyBlue"})
    mb.box_mm((-24.6, -51.1, FLOOR + 1.1), (x0 + 1.15, -38.9, FLOOR + 1.2), "M_Marble")
    mb.box_mm((x0 + 1.0, -50.0, FLOOR + 0.9), (x0 + 1.04, -40.0, FLOOR + 0.98), "M_Gold")
    mb.box_mm((x0 + 0.2, -42.0, FLOOR + 1.2), (x0 + 0.6, -41.4, FLOOR + 1.6), "M_DarkMetal")
    mb.box_mm((x0 + 0.15, -46.0, FLOOR + 1.2), (x0 + 0.45, -45.2, FLOOR + 1.27), "M_ShojiPaper")
    # back board (notice board + reception sign) on the west wall
    wx = -inx
    mb.box_mm((wx, -48.8, 3.6), (wx + 0.2, -41.2, 8.0), "M_AcademyBlue")
    mb.box_mm((wx, -49.0, 3.45), (wx + 0.26, -41.0, 3.6), "M_Gold")
    mb.box_mm((wx, -49.0, 8.0), (wx + 0.26, -41.0, 8.15), "M_Gold")
    mb.box_mm((wx + 0.2, -48.2, 3.9), (wx + 0.24, -41.8, 6.3), "M_ShojiPaper")
    aset.text("RECEPTION", (wx + 0.23, -45.0, 7.2), 90.0, size=0.75, color=(1.0, 0.85, 0.4))
    aset.text("STUDENT AFFAIRS", (wx + 0.27, -45.0, 6.75), 90.0, size=0.25, color=(1.0, 1.0, 1.0))
    aset.npc((-22.6, -45.0, FLOOR), 90.0, dorm="white", wander=0.5)
    aset.interact("sign", (-19.4, -45.0, FLOOR + 1.0), 90.0, title="Reception",
                  text="Welcome to Duel Academy! The Grand Duel Arena is straight ahead, "
                       "the Card Shop is on your right.")
    # staff doors
    for y in (-61.0, -28.0):
        door(mb, (wx, y, FLOOR), 90.0, 2.4, 3.4, mat="M_DarkWood")
    # trophy case near the arena portal (west) and vending machines (east)
    mb.box_mm((-24.0, -27.4, FLOOR), (-15.0, -24.3, FLOOR + 0.9), "M_DarkWood")
    mb.box_mm((-23.8, -27.2, FLOOR + 0.9), (-15.2, -24.5, FLOOR + 2.6), "M_GlassClear")
    mb.box_mm((-24.0, -27.4, FLOOR + 2.6), (-15.0, -24.3, FLOOR + 2.75), "M_DarkWood")
    for i, x in enumerate((-22.5, -19.5, -16.5)):
        mb.cylinder((x, -25.8, FLOOR + 0.9), 0.25, 0.25, "M_DarkWood", seg=8)
        mb.lathe([(0.12, FLOOR + 1.15), (0.1, FLOOR + 1.5), (0.35, FLOOR + 1.9), (0.3, FLOOR + 2.0)],
                 "M_Gold", seg=12, center=(x, -25.8, 0.0))
    aset.prop("SM_VendingMachine", (24.0, -24.4, FLOOR), 0.0)
    aset.prop("SM_VendingMachine", (21.5, -24.4, FLOOR), 0.0)
    aset.prop("SM_Bench", (-15.0, -55.0, FLOOR), 90.0)
    aset.prop("SM_Bench", (-15.0, -33.0, FLOOR), 90.0)
    aset.prop("SM_TrashBin", (16.0, -62.5, FLOOR), 0.0)
    aset.prop("SM_Planter", (-7.5, -63.5, FLOOR), 0.0)
    aset.prop("SM_Planter", (7.5, -63.5, FLOOR), 0.0)
    # students in the lobby
    for p, yaw, d in (((-4.0, -50.0), 20.0, "slifer"), ((5.0, -38.0), 160.0, "obelisk"),
                      ((14.5, -45.0), -90.0, "ra"), ((-13.0, -30.0), 0.0, "obelisk")):
        aset.npc((p[0], p[1], FLOOR), yaw, dorm=d, wander=4.0)
    aset.special("camera", (0.0, -63.5, 5.0), target=(0.0, -26.0, 8.5), lens=16)


# ---------------------------------------------------------------------------- interior: card shop
def _card_shop(mb, aset):
    X0, X1, Y0, Y1 = 18.0, LX - LWALL, -60.0, -30.0
    SH = 6.5
    clear = dict(glass="M_GlassClear", frame="M_Gold")
    mb.wall((X0, Y1), (X0, Y0), FLOOR, SH, 0.5, "M_AcademyWall",
            openings=[dict(u=15.0, w=9.0, z0=0.0, z1=4.2),
                      dict(u=4.6, w=5.4, z0=0.9, z1=3.9, **clear),
                      dict(u=25.4, w=5.4, z0=0.9, z1=3.9, **clear)])
    mb.wall((X1, Y1), (X0 + 0.5, Y1), FLOOR, SH, 0.5, "M_AcademyWall")
    mb.wall((X0 + 0.5, Y0), (X1, Y0), FLOOR, SH, 0.5, "M_AcademyWall")
    mb.box_mm((X0, Y0, FLOOR + SH), (X1, Y1, FLOOR + SH + 0.4), "M_AcademyWall")
    # shop front fascia, sign and gold trims (lobby side faces -X)
    mb.box_mm((X0 - 0.35, Y0 - 0.3, 7.0), (X0, Y1 + 0.3, FLOOR + SH + 0.4), "M_AcademyBlue")
    mb.box_mm((X0 - 0.45, Y0 - 0.35, 6.85), (X0, Y1 + 0.35, 7.0), "M_Gold")
    mb.box_mm((X0 - 0.45, Y0 - 0.35, FLOOR + SH + 0.4), (X0, Y1 + 0.35, FLOOR + SH + 0.55), "M_Gold")
    mb.box_mm((X0 - 0.6, -50.5, 7.1), (X0 - 0.35, -39.5, 8.75), "M_AcademyRed")
    mb.box_mm((X0 - 0.66, -50.65, 6.98), (X0 - 0.35, -39.35, 7.1), "M_Gold")
    mb.box_mm((X0 - 0.66, -50.65, 8.75), (X0 - 0.35, -39.35, 8.87), "M_Gold")
    for y in (-50.65, -39.47):
        mb.box_mm((X0 - 0.66, y, 6.98), (X0 - 0.35, y + 0.12, 8.87), "M_Gold")
    mb.box_mm((X0 - 0.3, -49.65, FLOOR), (X0, -49.35, 6.3), "M_Gold")
    mb.box_mm((X0 - 0.3, -40.65, FLOOR), (X0, -40.35, 6.3), "M_Gold")
    aset.text("CARD SHOP", (X0 - 0.63, -45.0, 7.9), -90.0, size=1.05, color=(1.0, 0.88, 0.35), emissive=True)
    mb.railing([(X0 + 0.25, Y0 + 0.25, FLOOR + SH + 0.4), (X0 + 0.25, Y1 - 0.25, FLOOR + SH + 0.4)],
               1.0, "M_Gold", post_spacing=1.5)
    # floor
    mb.box_mm((X0 + 0.5, Y0 + 0.5, FLOOR), (X1, Y1 - 0.5, FLOOR + 0.02), "M_Wood")
    # counter (customer side faces -X)
    cx0, cx1 = 22.0, 23.0
    mb.box_mm((cx0, -50.0, FLOOR), (cx1, -40.0, FLOOR + 1.0), "M_ShopShelf", mats={"-x": "M_AcademyBlue"})
    mb.box_mm((cx0, -52.0, FLOOR), (cx1 + 2.5, -50.0, FLOOR + 1.0), "M_ShopShelf",
              mats={"-x": "M_AcademyBlue", "-y": "M_AcademyBlue"})
    mb.box_mm((cx0 - 0.1, -52.1, FLOOR + 1.0), (cx1 + 2.6, -39.9, FLOOR + 1.07), "M_Marble")
    mb.box_mm((cx0 - 0.04, -52.0, FLOOR + 0.84), (cx0, -40.0, FLOOR + 0.92), "M_Gold")
    mb.box_mm((cx0 + 0.15, -49.0, FLOOR + 1.07), (cx1 - 0.15, -46.0, FLOOR + 1.45), "M_GlassClear")
    mb.box_mm((cx0 + 0.3, -41.4, FLOOR + 1.07), (cx0 + 0.75, -40.6, FLOOR + 1.35), "M_DarkMetal")
    mb.box_mm((cx0 + 0.32, -41.35, FLOOR + 1.35), (cx0 + 0.7, -41.05, FLOOR + 1.6), "M_Screen")
    packs = ("M_CardPack", "M_CardPackBlue", "M_CardPackPurple", "M_AcademyRed")
    for i in range(9):
        y = -48.7 + i * 0.32
        mb.box((cx0 + 0.45, y, FLOOR + 1.07 + 0.11), (0.05, 0.22, 0.22), packs[i % 4], skip=("-z",))
    for i in range(6):
        with mb.at((cx0 + 0.35, -44.5 + i * 0.28, FLOOR + 1.07), rot=-15 + i * 6):
            mb.box((0, 0, 0.012), (0.17, 0.24, 0.024), packs[(i + 1) % 4], skip=("-z",))
    # wall shelves full of booster boxes
    def shelf_unit(origin, yaw, length, levels=4, depth=0.55, height=2.7):
        with mb.at(origin, rot=yaw):
            # local: x along the unit, -y towards the customer, z up; back panel at y=0
            mb.box((0, 0.03, height / 2), (length, 0.06, height), "M_ShopShelf", skip=("+y",))
            for sx in (-1, 1):
                mb.box((sx * (length / 2 - 0.03), -depth / 2, height / 2), (0.06, depth, height), "M_ShopShelf")
            mb.box((0, -depth / 2, height + 0.03), (length + 0.1, depth + 0.05, 0.06), "M_AcademyBlue")
            for lv in range(levels):
                zb = 0.35 + lv * (height - 0.45) / levels
                mb.box((0, -depth / 2, zb), (length - 0.06, depth, 0.04), "M_ShopShelf")
                nb = int((length - 0.3) / 0.36)
                for k in range(nb):
                    u = -length / 2 + 0.24 + k * 0.36
                    mb.box((u, -0.2, zb + 0.02 + 0.17), (0.3, 0.22, 0.34), packs[(k + lv) % 4],
                           skip=("-z", "+y"))
            mb.box((0, -depth - 0.01, 0.17), (length - 0.1, 0.02, 0.3), "M_Gold", skip=("+y",))

    for yc, ln in ((-55.4, 5.2), (-45.0, 8.6), (-34.6, 5.2)):     # leaves the east windows free
        shelf_unit((X1, yc, FLOOR), -90.0, ln)
    shelf_unit((22.6, Y0 + 0.5, FLOOR), 180.0, 7.0, levels=3, height=2.2)
    shelf_unit((25.0, Y1 - 0.5, FLOOR), 0.0, 6.0, levels=3, height=2.2)
    # display table with fanned packs
    mb.box_mm((24.4, -57.0, FLOOR), (26.4, -54.6, FLOOR + 0.85), "M_AcademyBlue")
    mb.box_mm((24.3, -57.1, FLOOR + 0.85), (26.5, -54.5, FLOOR + 0.92), "M_ShopShelf")
    for i in range(12):
        with mb.at((24.8 + (i % 4) * 0.45, -56.5 + (i // 4) * 0.7, FLOOR + 0.92), rot=(i * 23) % 40 - 20):
            mb.box((0, 0, 0.012), (0.17, 0.24, 0.024), packs[i % 4], skip=("-z",))
    # poster board on the north wall (inside)
    mb.box_mm((19.4, Y1 - 0.55, 4.9), (21.4, Y1 - 0.5, 6.2), "M_CardPack")
    aset.text("NEW PACKS!", (20.4, Y1 - 0.58, 5.55), 0.0, size=0.28, color=(1, 1, 1))
    # light panels
    for y in (-54.0, -45.0, -36.0):
        mb.box_mm((21.5, y - 1.5, FLOOR + SH - 0.08), (26.5, y + 1.5, FLOOR + SH), "M_LampGlow")
        aset.light((24.0, y, FLOOR + SH - 0.6), (1.0, 0.92, 0.8), 4500, 12)
    aset.interact("card_shop", (21.3, -45.0, FLOOR + 1.0), -90.0, title="Card Shop",
                  text="Booster packs, fresh from the mainland! Trade, buy and build your deck.")
    aset.npc((24.0, -45.0, FLOOR), -90.0, dorm="white", wander=1.0)
    aset.npc((20.5, -55.0, FLOOR), 0.0, dorm="ra", wander=2.0)
    aset.special("camera", (11.0, -38.0, 4.2), target=(26.0, -47.0, 3.4), lens=18)


# ---------------------------------------------------------------------------- interior: arena
def _arena(mb, nocol, aset):
    C = DC
    # floor (podium inside the drum) + inlaid rings
    mb.prism(ngon(16, DRIN + 0.25, DA0, C), -4.0, FLOOR, "M_ArenaFloor")
    ring_sector(mb, C, 17.2, 17.6, 0.0, 360.0, FLOOR, FLOOR + 0.012, "M_Gold", faces="t", n=64)
    ring_sector(mb, C, 17.6, 19.8, 0.0, 360.0, FLOOR, FLOOR + 0.01, "M_AcademyBlue", faces="t", n=64)
    # ---- duel field
    fx, fy, fh = FIELD
    x0, x1, y0, y1 = C[0] - fx / 2, C[0] + fx / 2, C[1] - fy / 2, C[1] + fy / 2
    zf = FLOOR + fh
    mb.box_mm((x0, y0, FLOOR), (x1, y1, zf), "M_AcademyBlue", mats={"+z": "M_ArenaFloor"})
    rect_band(mb, x0, y0, x1, y1, zf - 0.1, zf, 0.06, "M_Gold")
    # steps (2 x 0.25 m) on all four sides
    mb.stairs((x1 + 1.0, C[1], FLOOR), 180.0, 4.0, 2, 0.25, 0.5, "M_AcademyBlue")
    mb.stairs((x0 - 1.0, C[1], FLOOR), 0.0, 4.0, 2, 0.25, 0.5, "M_AcademyBlue")
    mb.stairs((C[0], y0 - 1.0, FLOOR), 90.0, 6.0, 2, 0.25, 0.5, "M_AcademyBlue")
    mb.stairs((C[0], y1 + 1.0, FLOOR), -90.0, 6.0, 2, 0.25, 0.5, "M_AcademyBlue")
    # glow markings (no collision)
    zg = zf + 0.006
    w = 0.14
    i0 = 0.35
    for (ax, ay, bx, by) in ((x0 + i0, y0 + i0, x1 - i0, y0 + i0 + w), (x0 + i0, y1 - i0 - w, x1 - i0, y1 - i0),
                             (x0 + i0, y0 + i0, x0 + i0 + w, y1 - i0), (x1 - i0 - w, y0 + i0, x1 - i0, y1 - i0),
                             (C[0] - w / 2, y0 + i0, C[0] + w / 2, y1 - i0)):
        flat_rect(nocol, ax, ay, bx, by, zg, "M_DuelFieldGlow")
    ring_sector(nocol, C, 1.9, 2.05, 0.0, 360.0, zg - 0.006, zg, "M_DuelFieldGlow", faces="t", n=32)
    for side in (-1, 1):
        for row_x in (5.6, 8.0):
            for k in range(5):
                zx = C[0] + side * row_x
                zy = C[1] + (k - 2) * 2.5
                ax, bx, ay, by = zx - 0.8, zx + 0.8, zy - 1.08, zy + 1.08
                t = 0.07
                for (qa, qb, qc, qd) in ((ax, ay, bx, ay + t), (ax, by - t, bx, by), (ax, ay, ax + t, by),
                                         (bx - t, ay, bx, by)):
                    flat_rect(nocol, qa, qb, qc, qd, zg, "M_DuelFieldGlow")
        # duelist position
        dx = C[0] + side * 10.6
        ring_sector(nocol, (dx, C[1]), 0.85, 1.0, 0.0, 360.0, zg - 0.006, zg, "M_DuelFieldGlow", faces="t", n=24)
        disc(nocol, (dx, C[1]), 0.85, zg - 0.002, "M_Hologram", seg=24)
    # LED ribbon around the field sides
    for (ax, ay, bx, by, sk) in ((x0, y0 - 0.03, x1, y0, "+y"), (x0, y1, x1, y1 + 0.03, "-y"),
                                 (x0 - 0.03, y0, x0, y1, "+x"), (x1, y0, x1 + 0.03, y1, "-x")):
        nocol.box_mm((ax, ay, FLOOR + 0.22), (bx, by, FLOOR + 0.3), "M_DuelFieldGlow", skip=(sk, "-z"))
    # projector pylons at the corners
    for sx in (-1, 1):
        for sy in (-1, 1):
            px, py = C[0] + sx * (fx / 2 + 1.6), C[1] + sy * (fy / 2 + 1.6)
            mb.cylinder((px, py, FLOOR), 0.55, 0.4, "M_DarkMetal", seg=12)
            mb.cylinder((px, py, FLOOR + 0.4), 0.28, 2.6, "M_DarkMetal", seg=12)
            mb.cylinder((px, py, FLOOR + 3.0), 0.42, 0.25, "M_Gold", seg=12)
            nocol.sphere((px, py, FLOOR + 3.5), 0.32, "M_DuelFieldGlow", seg=12, rings=8)
            aset.light((px, py, FLOOR + 4.0), (0.4, 0.85, 1.0), 2500, 8)
    aset.interact("duel_field", (C[0], C[1], zf + 0.1), 0.0, title="Grand Duel Arena",
                  text="Step onto the field to start a holographic duel!", radius=6.0)

    # ---- stands
    gaps = [(252.0, 288.0), (-9.0, 9.0), (171.0, 189.0)]
    blocks = [(9.0, 171.0, (50.0, 90.0, 130.0)), (189.0, 252.0, (220.5,)), (288.0, 351.0, (319.5,))]
    AH = 2.4    # aisle half-angle (deg)
    r_out_last = DRIN + 0.5
    z_top = FLOOR + T_RISE * T_N
    sections, aisles = [], []
    for a0, a1, ais in blocks:
        cur = a0
        for a in ais:
            sections.append((cur, a - AH))
            aisles.append((a - AH, a + AH))
            cur = a + AH
        sections.append((cur, a1))

    def tier_r(k):
        return T_R0 + T_D * k

    for (a0, a1) in sections:
        for k in range(T_N):
            r0 = tier_r(k)
            r1 = tier_r(k + 1) if k < T_N - 1 else r_out_last
            z = FLOOR + T_RISE * (k + 1)
            ring_sector(mb, C, r0, r1, a0, a1, FLOOR, z, "M_AcademyWall", top="M_Concrete",
                        faces="tiab", iz0=z - T_RISE)
        # front parapet with gold cap
        ring_sector(mb, C, T_R0 - 0.25, T_R0, a0, a1, FLOOR, FLOOR + 1.15, "M_AcademyBlue", faces="tioab")
        ring_sector(mb, C, T_R0 - 0.3, T_R0 + 0.05, a0, a1, FLOOR + 1.15, FLOOR + 1.22, "M_Gold", faces="tioab")
        ring_sector(nocol, C, T_R0 - 0.27, T_R0 - 0.26, a0 + 0.3, a1 - 0.3, FLOOR + 0.75, FLOOR + 0.85,
                    "M_DuelFieldGlow", faces="i")
        # seats
        for k in range(T_N):
            rs = tier_r(k) + 0.58
            z = FLOOR + T_RISE * (k + 1)
            arc = (a1 - a0) * D2R * rs
            margin = 0.45
            ns = int((arc - 2 * margin) / 0.66)
            if ns <= 0:
                continue
            span = (ns - 1) * 0.66
            start = (a0 + a1) / 2 - (span / 2) / rs / D2R
            for j in range(ns):
                ang = start + (j * 0.66) / rs / D2R
                px, py = polar(rs, ang, C)
                with mb.at((px, py, z), rot=ang - 90.0):
                    mb.box((0, 0, 0.21), (0.5, 0.42, 0.42), "M_ArenaSeat", skip=("-z",))
                    mb.box((0, 0.19, 0.67), (0.5, 0.08, 0.5), "M_ArenaSeat", skip=("-z",))
    # aisles: two 0.225 m steps per tier
    for (a0, a1) in aisles:
        for k in range(T_N):
            r0 = tier_r(k)
            r1 = tier_r(k + 1) if k < T_N - 1 else r_out_last
            z = FLOOR + T_RISE * (k + 1)
            rm = r0 + T_D / 2
            ring_sector(mb, C, r0, rm, a0, a1, FLOOR, z - T_RISE / 2, "M_AcademyWall", top="M_Concrete",
                        faces="ti", iz0=z - T_RISE, n=1)
            ring_sector(mb, C, rm, r1, a0, a1, FLOOR, z, "M_AcademyWall", top="M_Concrete",
                        faces="ti", iz0=z - T_RISE / 2, n=1)
            ring_sector(mb, C, r0, r0 + 0.06, a0, a1, z - T_RISE / 2, z - T_RISE / 2 + 0.005,
                        "M_AcademyYellow", faces="t", n=1)
            ring_sector(mb, C, rm, rm + 0.06, a0, a1, z, z + 0.005, "M_AcademyYellow", faces="t", n=1)
    # gap cheek walls (vomitory + duelist tunnels) with gold coping
    zt1 = z_top + 1.0
    for (g0, g1) in gaps:
        main_gap = (g1 - g0) > 30.0
        r_end = r_out_last if main_gap else tier_r(T_N - 1)
        for ang, y0_, y1_ in ((g0, 0.0, 0.35), (g1, -0.35, 0.0)):
            with mb.at((C[0], C[1], 0.0), rot=ang):
                if main_gap:
                    pts = [(T_R0, FLOOR), (r_end, FLOOR), (r_end, zt1), (tier_r(T_N - 1), zt1),
                           (T_R0, FLOOR + T_RISE + 1.0)]
                else:
                    pts = [(T_R0, FLOOR), (r_end, FLOOR), (r_end, zt1), (T_R0, FLOOR + T_RISE + 1.0)]
                xz_prism(mb, pts, y0_, y1_, "M_AcademyWall")
                # blue wainscot + gold line on the passage side
                yo = y1_ if y0_ == 0.0 else y0_
                sg = 1.0 if y0_ == 0.0 else -1.0
                ya_, yb_ = sorted((yo, yo + sg * 0.05))
                mb.box_mm((T_R0 + 0.05, ya_, FLOOR), (r_end, yb_, FLOOR + 1.3), "M_AcademyBlue", skip=("-z",))
                mb.box_mm((T_R0 + 0.05, ya_ - 0.01, FLOOR + 1.3), (r_end, yb_ + 0.01, FLOOR + 1.42), "M_Gold",
                          skip=("-z",))
                yc = (y0_ + y1_) / 2
                mb.beam((T_R0, yc, FLOOR + T_RISE + 1.0), (tier_r(T_N - 1), yc, zt1), 0.5, 0.1, "M_Gold")
                if main_gap:
                    mb.box_mm((tier_r(T_N - 1), yc - 0.25, zt1 - 0.05), (r_end, yc + 0.25, zt1 + 0.05), "M_Gold")
        if not main_gap:
            # concourse bridge over the duelist tunnel
            ring_sector(mb, C, tier_r(T_N - 1), r_out_last, g0, g1, z_top - 0.5, z_top, "M_AcademyWall",
                        top="M_Concrete", faces="tdi", n=2)
            ring_sector(mb, C, tier_r(T_N - 1), tier_r(T_N - 1) + 0.25, g0, g1, z_top, zt1, "M_AcademyBlue",
                        faces="tio", n=2)
            ring_sector(mb, C, tier_r(T_N - 1) - 0.03, tier_r(T_N - 1) + 0.28, g0, g1, zt1, zt1 + 0.08,
                        "M_Gold", faces="tio", n=2)
            # duelist door in the drum wall
            mid = (g0 + g1) / 2
            dpos = polar(DIN - 0.02, mid, C)
            door(mb, (dpos[0], dpos[1], FLOOR), mid + 270.0, 4.4, 5.0)
            aset.light((*polar(DIN - 3.0, mid, C), 7.0), (1.0, 0.6, 0.3), 3000, 10)
    # ---- inner drum wall decoration
    drum_band_inner(mb, DRIN + 0.3, DRIN - 0.25, 10.0, 11.0, "M_AcademyBlue", skip_mid=(270.0,))
    drum_band_inner(mb, DRIN + 0.3, DRIN - 0.3, 11.0, 11.15, "M_Gold", skip_mid=(270.0,))
    ring_between(mb, ngon(16, DRIN + 0.3, DA0, C), ngon(16, DRIN - 0.35, DA0, C), ROOF_Z - 1.2, ROOF_Z,
                 "M_AcademyBlue", "M_AcademyBlue", "M_AcademyBlue", outer_side=False)
    ring_between(mb, ngon(16, DRIN + 0.3, DA0, C), ngon(16, DRIN - 0.4, DA0, C), ROOF_Z - 1.35, ROOF_Z - 1.2,
                 "M_Gold", "M_Gold", "M_Gold", outer_side=False)
    # pilasters (inner) at the polygon vertices above the concourse
    for i in range(16):
        ang = DA0 + 22.5 * i
        vx, vy = polar(DRIN, ang, C)
        with mb.at((vx, vy, 0.0), rot=ang):
            mb.box((-0.15, 0.0, (11.15 + ROOF_Z - 1.35) / 2), (0.5, 1.2, ROOF_Z - 1.35 - 11.15), "M_AcademyWall")
    # big screens on the diagonals
    for m in (45.0, 135.0, 225.0, 315.0):
        p = polar(DIN, m, C)
        with mb.at((p[0], p[1], 0.0), rot=m + 90.0):
            # local -Y = outward; the arena side is +Y
            mb.box((0, 0.25, 19.8), (13.6, 0.5, 8.1), "M_Black")
            mb.box((0, 0.52, 19.8), (13.0, 0.06, 7.5), "M_Screen", skip=("-y",))
            mb.box((0, 0.3, 15.55), (13.8, 0.6, 0.2), "M_Gold")
            mb.box((0, 0.3, 24.05), (13.8, 0.6, 0.2), "M_Gold")
        tp = polar(DIN - 0.58, m, C)
        aset.text("GRAND DUEL ARENA", (tp[0], tp[1], 21.6), m - 90.0, size=0.9, color=(1, 1, 1), emissive=True)
        aset.text("DUEL!", (tp[0], tp[1], 18.6), m - 90.0, size=2.2, color=(1.0, 0.85, 0.3), emissive=True)
        aset.light((*polar(DIN - 6.0, m, C), 19.0), (0.45, 0.65, 1.0), 4000, 18)
    # crests above the portal (south) and on the north wall, facing the field
    for m in (270.0, 90.0):
        p = polar(DIN, m, C)
        emblem(mb, (p[0], p[1], 19.5), 3.4, yaw=m - 90.0, depth=0.35)
    # hanging dorm banners
    cols = ("M_AcademyRed", "M_AcademyYellow", "M_AcademyBlue")
    for k, m in enumerate((22.5, 67.5, 112.5, 157.5, 202.5, 247.5, 292.5, 337.5)):
        p = polar(DIN - 0.5, m, C)
        banner(nocol, (p[0], p[1], ROOF_Z - 1.5), m - 90.0, 4.0, 11.0, cols[k % 3])
    # ceiling: oculus trim, light panels, lighting ring
    square_frame(mb, C[0], C[1], ROOF_Z - 0.5, ROOF_Z, OCULUS + 0.9, OCULUS, "M_Gold")
    for k in range(16):
        a = 11.25 + 22.5 * k
        p = polar(27.0, a, C)
        with mb.at((p[0], p[1], ROOF_Z), rot=a):
            mb.box((0, 0, -0.06), (0.9, 3.2, 0.12), "M_LampGlow", skip=("+z",))
    mb.torus((C[0], C[1], 24.0), 15.5, 0.3, "M_DarkMetal", seg=48, tube_seg=6)
    mb.torus((C[0], C[1], 23.6), 15.5, 0.14, "M_LampGlow", seg=48, tube_seg=6)
    for k in range(8):
        p = polar(15.5, 22.5 + 45 * k, C)
        mb.beam((p[0], p[1], 24.0), (p[0], p[1], ROOF_Z), 0.06, 0.06, "M_DarkMetal")
    # ---- lights / audio / npcs / cameras
    for k in range(8):
        p = polar(25.0, 22.5 + 45 * k, C)
        aset.light((p[0], p[1], 25.0), (1.0, 0.95, 0.88), 14000, 38)
    for sx in (-1, 1):
        for sy in (-1, 1):
            aset.light((C[0] + sx * 7.0, C[1] + sy * 4.0, 16.0), (0.85, 0.92, 1.0), 16000, 26)
    aset.light((C[0], C[1], 40.0), (1.0, 0.98, 0.95), 12000, 30)
    aset.audio("A_Crowd", (C[0], C[1], 8.0), radius=48.0)
    dorms = ("slifer", "ra", "obelisk")
    # spectators: on the upper concourse (2.7 m wide walkway) and around the arena floor
    for i, ang in enumerate((25.0, 62.0, 105.0, 148.0, 200.0, 236.0, 305.0, 338.0, 120.0, 30.0)):
        p = polar(34.6, ang, C)
        aset.npc((p[0], p[1], z_top), ang - 90.0, dorm=dorms[i % 3], wander=2.0)
    for i, ang in enumerate((40.0, 140.0, 215.0, 325.0, 95.0)):
        p = polar(18.4, ang, C)
        aset.npc((p[0], p[1], FLOOR), ang - 90.0, dorm=dorms[(i + 1) % 3], wander=2.5)
    aset.npc((C[0] - 10.6, C[1], zf), -90.0 + 180.0, dorm="obelisk", wander=0.5)
    aset.npc((C[0] - 3.0, C[1] - 12.0, FLOOR), 0.0, dorm="slifer", wander=3.0)
    aset.special("camera", (C[0] + 21.0, C[1] - 25.0, 12.5), target=(C[0], C[1], 4.0), lens=16)
    aset.special("camera", (C[0], C[1] - 33.5, 4.2), target=(C[0], C[1] + 20.0, 14.0), lens=16)


def _academy_dressing(mb, aset):
    # entrance lighting (night)
    for x in (-9.0, 9.0, -17.0, 17.0):
        aset.light((x, LY0 - 1.0, 9.0), (1.0, 0.82, 0.55), 6000, 16, night_only=True)
    aset.light((0.0, -71.0, 14.0), (1.0, 0.85, 0.6), 9000, 22, night_only=True)
    aset.light((0.0, -80.0, 12.0), (1.0, 0.85, 0.55), 14000, 30, night_only=True)
    for s in (-1, 1):
        aset.light((s * 27.25, -80.3, FLOOR + 7.0), (1.0, 0.8, 0.5), 5000, 14, night_only=True)
        aset.light((s * 33.0, -60.0, 2.0), (0.9, 0.9, 1.0), 7000, 24, night_only=True)
    aset.light((0.0, 15.0, 64.0), (1.0, 0.85, 0.5), 18000, 40, night_only=True)
    # forecourt gardens between the entrance hall and the end pavilions
    for s in (-1, 1):
        base = [(48.0, -34.0), (74.0, -34.0), (76.0, -32.0), (76.0, -14.0), (74.0, -12.0), (48.0, -12.0),
                (46.0, -14.0), (46.0, -32.0)]
        pts = [(x * s, y) for x, y in base]
        if s < 0:
            pts.reverse()
        flowers = ("M_FlowerRed", "M_FlowerYellow") if s < 0 else ("M_FlowerBlue", "M_FlowerWhite")
        garden_bed(mb, aset, pts, flowers, palms=((s * 49.5, -30.5), (s * 72.5, -15.5), (s * 72.5, -30.5),
                                                  (s * 49.5, -15.5)))
        for x in (43.0, 79.0):
            for y in (-37.0, -9.0):
                aset.prop("SM_LampPost", (s * x, y, 0.0), 0.0)
        for x in (55.0, 67.0):
            aset.prop("SM_Bench", (s * x, -37.0, 0.0), 180.0)
            aset.prop("SM_Bench", (s * x, -9.0, 0.0), 0.0)
        aset.prop("SM_TrashBin", (s * 61.0, -37.2, 0.0), 0.0)
        # approach / perimeter lamps
        for x, y in ((14.0, -89.0), (32.0, -86.0), (45.0, -72.0), (45.0, -50.0), (75.0, -50.0),
                     (118.0, -30.0), (118.0, 20.0), (60.0, 40.0), (30.0, 70.0), (60.0, 75.0)):
            aset.prop("SM_LampPost", (s * x, y, 0.0), 0.0)
        for x, y in ((38.0, -85.0), (52.0, -82.0), (62.0, -62.0), (82.0, -62.0), (118.0, -55.0),
                     (120.0, 64.0), (40.0, 52.0), (75.0, 62.0)):
            aset.prop("SM_PalmTree_A" if (x + y) % 2 == 0 else "SM_PalmTree_B", (s * x, y, 0.0), s * 30.0)
        aset.prop("SM_Planter", (s * 31.0, -84.0, 0.0), 0.0)
        aset.prop("SM_Planter", (s * 22.0, -84.0, 0.0), 0.0)
        aset.prop("SM_FlowerBush_Red" if s < 0 else "SM_FlowerBush_Blue", (s * 36.0, -64.0, 0.0), 0.0)
        aset.prop("SM_FlowerBush_Yellow", (s * 36.0, -58.0, 0.0), 0.0)
        aset.prop("SM_FlowerBush_White", (s * 36.0, -40.0, 0.0), 0.0)
        aset.prop("SM_VendingMachine", (s * 86.6, -30.0, 0.0), -90.0 * s)
        aset.prop("SM_VendingMachine", (s * 86.6, -32.0, 0.0), -90.0 * s)
    # students outside
    for p, yaw, d in (((-6.0, -88.0), 0.0, "slifer"), ((8.0, -79.0), 180.0, "ra"), ((-60.0, -38.5), 0.0, "obelisk"),
                      ((62.0, -7.0), 180.0, "ra"), ((0.0, 84.0), 0.0, "obelisk"), ((-90.0, -60.0), 45.0, "slifer"),
                      ((40.0, -24.0), -90.0, "obelisk"), ((-82.0, -22.0), 90.0, "ra")):
        aset.npc((p[0], p[1], 0.0 if abs(p[1]) > 77 or abs(p[0]) > 32 else FLOOR), yaw, dorm=d, wander=6.0)


def build_academy():
    aset = AssetSet("academy")
    main = aset.mesh("Academy_Main")
    inter = aset.mesh("Academy_Interior")
    arena = aset.mesh("Academy_Arena")
    towers = aset.mesh("Academy_Towers")
    nocol = aset.mesh("Academy_NoCol")
    _podium_and_steps(main)
    _lobby_shell(main)
    _portico(main, aset)
    _drum(main, nocol)
    _pyramid(main)
    _wings(main, nocol)
    _end_blocks(main)
    _rear_annex(main)
    _towers(towers, nocol, aset)
    _lobby_interior(inter, nocol, aset)
    _card_shop(inter, aset)
    _arena(arena, nocol, aset)
    _academy_dressing(main, aset)
    return aset


# ============================================================================ PLAZA
FK = 1.3        # fountain scale
FR = 14.3 * FK  # kerb outer radius


def _fountain(mb, nocol, aset):
    seg = 48
    with mb.at((0, 0, 0), scale=FK), nocol.at((0, 0, 0), scale=FK):
        # outer basin: outer wall + rim (marble), inner wall + floor (blue tiles)
        mb.lathe([(9.4, -0.4), (9.4, 0.45)], "M_Marble", seg=seg, cap_top=False, cap_bottom=False)
        mb.lathe([(9.4, 0.45), (9.25, 0.62), (8.95, 0.68), (8.7, 0.62), (8.6, 0.5)], "M_Marble", seg=seg,
                 cap_top=False, cap_bottom=False)
        mb.lathe([(8.6, 0.5), (8.6, 0.1)], "M_AcademyBlue", seg=seg, cap_top=False, cap_bottom=False)
        mb.lathe([(8.6, 0.1), (1.6, 0.1)], "M_AcademyBlue", seg=seg, cap_top=True, cap_bottom=False)
        # gold rim inlay
        ring_sector(mb, (0, 0), 8.9, 9.0, 0.0, 360.0, 0.6, 0.685, "M_Gold", faces="t", n=seg)
        # pedestal, middle bowl, upper column, top bowl
        mb.lathe([(1.6, 0.1), (1.6, 0.4), (1.2, 0.55)], "M_Marble", seg=32, cap_top=False, cap_bottom=False)
        mb.lathe([(1.2, 0.55), (0.9, 0.9), (0.85, 2.0), (1.2, 2.35)], "M_Marble", seg=32, cap_top=False,
                 cap_bottom=False)
        mb.lathe([(1.2, 2.35), (2.4, 2.6), (3.25, 2.95), (3.4, 3.25)], "M_Marble", seg=seg, cap_top=False,
                 cap_bottom=False)
        mb.lathe([(3.4, 3.25), (3.2, 3.32), (3.05, 3.2)], "M_Gold", seg=seg, cap_top=False, cap_bottom=False)
        mb.lathe([(3.05, 3.2), (2.4, 3.0), (0.6, 2.85)], "M_AcademyBlue", seg=seg, cap_top=False, cap_bottom=False)
        mb.lathe([(0.6, 2.85), (0.5, 3.1), (0.45, 4.3), (0.75, 4.55)], "M_Marble", seg=24, cap_top=False,
                 cap_bottom=False)
        mb.lathe([(0.75, 4.55), (1.5, 4.75), (1.8, 4.98)], "M_Marble", seg=32, cap_top=False, cap_bottom=False)
        mb.lathe([(1.8, 4.98), (1.68, 5.05), (1.55, 4.98)], "M_Gold", seg=32, cap_top=False, cap_bottom=False)
        mb.lathe([(1.55, 4.98), (0.45, 4.85)], "M_AcademyBlue", seg=32, cap_top=False, cap_bottom=False)
        mb.lathe([(0.45, 4.85), (0.38, 5.6), (0.6, 5.72), (0.6, 5.9)], "M_Gold", seg=16, cap_top=True,
                 cap_bottom=False)
        # crest statue on top (two-sided)
        emblem(mb, (0.0, 0.0, 7.65), 1.75, yaw=0.0, depth=0.18)
        emblem(mb, (0.0, 0.0, 7.65), 1.75, yaw=180.0, depth=0.18)
        # water (no collision)
        disc(nocol, (0, 0), 8.62, 0.5, "M_LakeWater", seg=seg)
        disc(nocol, (0, 0), 3.1, 3.12, "M_LakeWater", seg=seg)
        disc(nocol, (0, 0), 1.6, 4.96, "M_LakeWater", seg=32)
        nocol.cylinder((0, 0, 0.5), 3.47, 2.75, "M_Waterfall", seg=seg, cap_top=False, cap_bottom=False)
        nocol.cylinder((0, 0, 3.12), 1.86, 1.9, "M_Waterfall", seg=32, cap_top=False, cap_bottom=False)
        for k in range(12):
            p = polar(7.4, 15 + 30 * k)
            nocol.cone((p[0], p[1], 0.5), 0.12, 1.4, "M_Waterfall", seg=6, cap_bottom=False)
        # paving rosette and kerb around the fountain
        for k in range(24):
            a0 = k * 15.0
            ring_sector(mb, (0, 0), 9.4, 13.8, a0, a0 + 15.0, 0.0, 0.03,
                        "M_Marble" if k % 2 == 0 else "M_AcademyStone", faces="t", n=2)
        ring_sector(mb, (0, 0), 13.0, 13.3, 0.0, 360.0, 0.0, 0.04, "M_AcademyBlue", faces="t", n=64)
        ring_sector(mb, (0, 0), 13.8, 14.3, 0.0, 360.0, -0.3, 0.14, "M_AcademyStone", faces="tio", n=64)
    aset.emitter("mist", (0.0, 0.0, 3.5 * FK), scale=1.6 * FK)
    aset.emitter("mist", (0.0, 0.0, 0.9 * FK), scale=2.4 * FK)
    aset.audio("A_Waterfall", (0.0, 0.0, 1.5), radius=25.0 * FK)
    for k in range(4):
        p = polar(6.0 * FK, 45 + 90 * k)
        aset.light((p[0], p[1], 0.7 * FK), (0.6, 0.85, 1.0), 2500, 9, night_only=True)
    aset.light((0.0, 0.0, 10.0 * FK), (1.0, 0.85, 0.55), 5000, 12, night_only=True)


def _paving(mb):
    """Stone processional bands on both axes with marble borders (2 cm inlays over the terrain paving)."""
    r0 = math.sqrt(FR * FR - 7.0 * 7.0) - 0.6
    for sgn in (-1, 1):
        ya, yb = sorted((sgn * r0, sgn * 54.5))
        mb.box_mm((-7.0, ya, -0.1), (7.0, yb, 0.02), "M_AcademyStone", skip=("-z",))
        xa, xb = sorted((sgn * r0, sgn * 97.0))
        mb.box_mm((xa, -7.0, -0.1), (xb, 7.0, 0.02), "M_AcademyStone", skip=("-z",))
        for e in (-1, 1):
            mb.box_mm((e * 7.0 - 0.35, ya, -0.1), (e * 7.0 + 0.35, yb, 0.03), "M_Marble", skip=("-z",))
            mb.box_mm((xa, e * 7.0 - 0.35, -0.1), (xb, e * 7.0 + 0.35, 0.03), "M_Marble", skip=("-z",))
        # cross strips every 6 m
        for k in range(int((54.5 - r0) // 6.0)):
            y = sgn * (r0 + 3.0 + 6.0 * k)
            mb.box_mm((-6.65, y - 0.15, -0.1), (6.65, y + 0.15, 0.025), "M_Marble", skip=("-z",))
        for k in range(int((97.0 - r0) // 6.0)):
            x = sgn * (r0 + 3.0 + 6.0 * k)
            mb.box_mm((x - 0.15, -6.65, -0.1), (x + 0.15, 6.65, 0.025), "M_Marble", skip=("-z",))


def _bed(mb, aset, sx, sy):
    # quadrant garden bed, inner corner chamfered toward the fountain
    base = [(30.0, 14.0), (72.0, 14.0), (72.0, 46.0), (24.0, 46.0), (24.0, 20.0)]
    pts = [(x * sx, y * sy) for x, y in base]
    if sx * sy < 0:
        pts.reverse()
    n = len(pts)
    for i in range(n):
        mb.wall(pts[i], pts[(i + 1) % n], -0.3, 0.85, 0.45, "M_AcademyStone", cap_mat="M_Marble")
    fill = inset_poly(pts, 0.44)
    mb.prism(fill, -0.3, 0.38, "M_Soil", top_mat="M_PlazaLawn", cap_bottom=False)
    # clipped hedge border
    mb.slab_ring(inset_poly(pts, 0.5), inset_poly(pts, 1.3), 0.38, 1.05, "M_Hedge")
    # central flower island with a rosette of flower rings
    c = (sx * 49.0, sy * 30.0)
    pal = {(1, 1): ("M_FlowerBlue", "M_FlowerWhite"), (-1, 1): ("M_FlowerRed", "M_FlowerYellow"),
           (1, -1): ("M_FlowerYellow", "M_FlowerWhite"), (-1, -1): ("M_FlowerRed", "M_FlowerWhite")}[(sx, sy)]
    ring_sector(mb, c, 3.6, 4.0, 0.0, 360.0, 0.38, 0.75, "M_Marble", faces="tio", n=24)
    mb.cylinder((*c, 0.38), 3.6, 0.3, "M_Soil", seg=24, cap_bottom=False)
    for k in range(12):
        a0 = k * 30.0
        ring_sector(mb, c, 6.0, 9.0, a0 + 1.5, a0 + 28.5, 0.38, 0.6, pal[k % 2], faces="tioab", n=4)
    ring_sector(mb, c, 9.6, 10.4, 0.0, 360.0, 0.38, 0.62, "M_FlowerYellow" if sx > 0 else "M_FlowerRed",
                faces="tio", n=48)
    aset.prop("SM_BroadTree_C", (c[0], c[1], 0.68), 0.0)
    # topiaries
    for dx, dy in ((14.5, 0.0), (-14.5, 0.0), (0.0, 12.5), (0.0, -12.5)):
        tx, ty = c[0] + dx, c[1] + dy
        mb.cylinder((tx, ty, 0.38), 0.7, 0.5, "M_AcademyStone", seg=8, smooth=False, cap_bottom=False)
        mb.cone((tx, ty, 0.88), 1.0, 3.0, "M_Hedge", seg=10, smooth=False)
        mb.sphere((tx, ty, 4.1), 0.35, "M_Gold", seg=8, rings=6)
    # palms in the outer corners, flower bushes along the inner edge
    aset.prop("SM_PalmTree_A", (sx * 67.5, sy * 41.5, 0.38), sx * 20.0)
    aset.prop("SM_PalmTree_B", (sx * 67.5, sy * 18.5, 0.38), -sx * 35.0)
    aset.prop("SM_PalmTree_B", (sx * 29.0, sy * 41.5, 0.38), sx * 60.0)
    for k, x in enumerate((34.0, 42.0, 56.0, 64.0)):
        aset.prop(("SM_FlowerBush_Red", "SM_FlowerBush_Yellow", "SM_FlowerBush_Blue", "SM_FlowerBush_White")[k],
                  (sx * x, sy * 17.2, 0.38), 0.0)


def build_plaza():
    aset = AssetSet("plaza")
    mb = aset.mesh("Plaza_Main")
    nocol = aset.mesh("Plaza_NoCol")
    _fountain(mb, nocol, aset)
    _paving(mb)
    for sx in (-1, 1):
        for sy in (-1, 1):
            _bed(mb, aset, sx, sy)
    # ---- south entrance gate (road arrives at (0, -55))
    gy = -55.0
    for s in (-1, 1):
        px = s * 9.0
        mb.box_mm((px - 1.6, gy - 1.6, -1.0), (px + 1.6, gy + 1.6, 0.8), "M_AcademyStone")
        mb.box_mm((px - 1.4, gy - 1.4, 0.8), (px + 1.4, gy + 1.4, 11.2), "M_AcademyWall")
        rect_band(mb, px - 1.4, gy - 1.4, px + 1.4, gy + 1.4, 6.6, 7.6, 0.12, "M_AcademyBlue")
        rect_band(mb, px - 1.4, gy - 1.4, px + 1.4, gy + 1.4, 7.6, 7.75, 0.18, "M_Gold")
        rect_band(mb, px - 1.4, gy - 1.4, px + 1.4, gy + 1.4, 10.8, 11.2, 0.2, "M_Gold")
        mb.pyramid((px, gy, 11.2), 3.2, 3.2, 2.6, "M_Gold")
        for yy, yw in ((gy - 1.4, 0.0), (gy + 1.4, 180.0)):
            roundel(mb, (px, yy, 4.4), yw, 0.8, "M_AcademyRed" if s < 0 else "M_AcademyYellow")
        aset.light((px, gy - 2.4, 6.0), (1.0, 0.82, 0.55), 6000, 16, night_only=True)
        aset.light((px, gy + 2.4, 6.0), (1.0, 0.82, 0.55), 4000, 14, night_only=True)
        # low planter walls along the south edge
        xa, xb = sorted((s * 10.6, s * 44.0))
        mb.box_mm((xa, gy - 0.5, -0.3), (xb, gy + 0.5, 0.85), "M_AcademyStone")
        mb.box_mm((xa, gy - 0.6, 0.85), (xb, gy + 0.6, 0.97), "M_Marble")
        mb.box_mm((xa + 0.2, gy - 0.35, 0.97), (xb - 0.2, gy + 0.35, 1.55), "M_Hedge")
        ex = s * 44.0
        mb.box_mm((ex - 0.8, gy - 0.8, -0.3), (ex + 0.8, gy + 0.8, 1.4), "M_AcademyWall")
        mb.box_mm((ex - 0.9, gy - 0.9, 1.4), (ex + 0.9, gy + 0.9, 1.55), "M_Gold")
        aset.prop("SM_StoneLantern", (ex, gy, 1.55), 0.0)
    mb.box_mm((-10.6, gy - 1.0, 8.6), (10.6, gy + 1.0, 10.6), "M_AcademyBlue")
    mb.box_mm((-10.7, gy - 1.1, 8.45), (10.7, gy + 1.1, 8.6), "M_Gold")
    mb.box_mm((-10.7, gy - 1.1, 10.6), (10.7, gy + 1.1, 10.8), "M_Gold")
    mb.box_mm((-1.0, gy - 0.3, 10.8), (1.0, gy + 0.3, 11.4), "M_Gold")
    emblem(mb, (0.0, gy, 13.25), 1.95, yaw=0.0, depth=0.2)
    emblem(mb, (0.0, gy, 13.25), 1.95, yaw=180.0, depth=0.2)
    aset.text("DUEL ACADEMY", (0.0, gy - 1.03, 9.6), 0.0, size=1.2, color=(1.0, 0.85, 0.35), emissive=True)
    aset.text("WELCOME BACK", (0.0, gy + 1.03, 9.6), 180.0, size=0.9, color=(1.0, 0.85, 0.35), emissive=True)
    # ---- flagpoles on octagonal bases (north edge, facing the academy steps)
    for x, y, f in ((-8.0, 48.0, "SM_Flagpole_Red"), (0.0, 49.0, "SM_Flagpole_Blue"),
                    (8.0, 48.0, "SM_Flagpole_Yellow")):
        mb.cylinder((x, y, -0.3), 1.2, 0.75, "M_Marble", seg=8, cap_bottom=False, smooth=False)
        mb.cylinder((x, y, 0.32), 1.25, 0.1, "M_Gold", seg=8, cap_bottom=False, smooth=False)
        aset.prop(f, (x, y, 0.45), 0.0)
        aset.light((x, y - 2.0, 1.0), (1.0, 0.9, 0.7), 2500, 10, night_only=True)
    # ---- direction board (west of the main axis, facing the arriving road)
    bo, byaw = (-15.0, -41.0, 0.0), 20.0
    with mb.at(bo, rot=byaw):
        for sx in (-1, 1):
            mb.box((sx * 3.4, 0.0, 0.3), (0.9, 0.9, 1.2), "M_AcademyStone")
            mb.box((sx * 3.4, 0.0, 2.6), (0.4, 0.4, 4.2), "M_AcademyWall")
        mb.box((0.0, 0.0, 3.05), (6.4, 0.22, 3.1), "M_AcademyBlue")
        mb.box((0.0, 0.0, 4.65), (6.9, 0.3, 0.14), "M_Gold")
        mb.box((0.0, 0.0, 1.45), (6.9, 0.3, 0.14), "M_Gold")
        mb.gable_roof((0.0, 0.0, 4.95), 7.4, 0.8, 0.55, "M_AcademyRoof", overhang=0.3, thick=0.15,
                      gable_mat="M_AcademyBlue")
        mb.box((0.0, 0.0, 4.85), (7.2, 0.6, 0.2), "M_AcademyBlue")
    lines = [
        ("ACADEMY ISLAND - DIRECTIONS", 0.3, (1.0, 0.85, 0.35)),
        ("^   DUEL ACADEMY  /  GRAND DUEL ARENA", 0.19, (1, 1, 1)),
        ("^   GIRLS' DORM  &  ACADEMY LAKE  (N)", 0.19, (1, 1, 1)),
        ("^>  VOLCANO  /  HOT SPRINGS  (NE)", 0.19, (1, 1, 1)),
        (">   FOREST  /  ABANDONED DORM - OFF LIMITS!  (E)", 0.19, (1.0, 0.6, 0.55)),
        ("<^  OBELISK BLUE DORM  (NW)", 0.19, (0.6, 0.75, 1.0)),
        ("<   SLIFER RED DORM  /  WEST CLIFFS  (W)", 0.19, (1.0, 0.55, 0.5)),
        ("<v  RA YELLOW DORM  (SW)", 0.19, (1.0, 0.9, 0.45)),
        ("v   HARBOR  /  LIGHTHOUSE  /  HELIPORT  (S)", 0.19, (1, 1, 1)),
        ("v>  BEACH  &  DUEL GYM  (SE)", 0.19, (1, 1, 1)),
    ]
    z = 4.25
    for i, (t, sz, col) in enumerate(lines):
        aset.text(t, local_to_world(bo, byaw, (0.0, -0.14, z)), byaw, size=sz, color=col)
        z -= 0.42 if i == 0 else 0.28
    aset.text("HAVE A GREAT DUEL!", local_to_world(bo, byaw, (0.0, 0.14, 3.2)), byaw + 180.0, size=0.32,
              color=(1.0, 0.85, 0.35))
    aset.interact("sign", local_to_world(bo, byaw, (0.0, -1.6, 1.0)), byaw, title="Academy Island Directions",
                  text="N: Duel Academy, Girls' Dorm & Lake  |  NE: Volcano, Hot Springs  |  "
                       "E: Forest, Abandoned Dorm (off limits!)  |  NW: Obelisk Blue Dorm  |  "
                       "W: Slifer Red Dorm, West Cliffs  |  SW: Ra Yellow Dorm  |  "
                       "S: Harbor, Lighthouse, Heliport  |  SE: Beach & Duel Gym")
    aset.light(local_to_world(bo, byaw, (0.0, -2.5, 5.5)), (1.0, 0.9, 0.75), 3000, 9, night_only=True)
    # ---- street furniture
    for s in (-1, 1):
        for y in (-44.0, -26.0, 24.0, 40.0):
            aset.prop("SM_LampPost", (s * 9.5, y, 0.0), 0.0)
        for x in (28.0, 56.0, 84.0):
            aset.prop("SM_LampPost", (s * x, 52.0, 0.0), 0.0)
            aset.prop("SM_LampPost", (s * x, -51.0, 0.0), 0.0)
        for y in (-30.0, 0.0, 30.0):
            aset.prop("SM_LampPost", (s * 96.0, y, 0.0), 0.0)
        for y in (-16.0, 16.0):
            aset.prop("SM_LampPost", (s * 20.0, y, 0.0), 0.0)
        aset.prop("SM_Bench", (s * 12.5, -34.0, 0.0), -90.0 * s)
        aset.prop("SM_Bench", (s * 12.5, 32.0, 0.0), -90.0 * s)
        aset.prop("SM_Bench", (s * 48.0, 11.0, 0.0), 0.0)
        aset.prop("SM_Bench", (s * 48.0, -11.0, 0.0), 180.0)
        aset.prop("SM_TrashBin", (s * 12.5, -31.0, 0.0), -90.0 * s)
        aset.prop("SM_Planter", (s * 22.0, -10.0, 0.0), 0.0)
        aset.prop("SM_Planter", (s * 22.0, 10.0, 0.0), 0.0)
        aset.prop("SM_Planter", (s * 76.0, -10.0, 0.0), 0.0)
        aset.prop("SM_Planter", (s * 76.0, 10.0, 0.0), 0.0)
    for k in range(8):
        a = 22.5 + 45.0 * k
        p = polar(FR + 2.2, a)
        aset.prop("SM_Bench", (p[0], p[1], 0.0), a - 90.0)
    aset.prop("SM_VendingMachine", (-97.0, -42.0, 0.0), 90.0)
    aset.prop("SM_Signpost", (-93.0, -16.0, 0.0), 90.0)
    aset.prop("SM_Signpost", (92.0, 18.0, 0.0), -90.0)
    # ---- students
    dorms = ("slifer", "ra", "obelisk")
    spots = [(5.0, -18.0, 180.0), (-11.0, -12.0, 60.0), (16.0, 6.0, 120.0), (-4.0, 18.0, 0.0),
             (-16.0, -36.0, 200.0), (3.0, -48.0, 0.0), (-40.0, 8.0, 90.0), (44.0, -6.0, -90.0),
             (0.0, 40.0, 0.0), (-80.0, -20.0, 60.0), (85.0, 30.0, -120.0), (25.0, -30.0, 30.0)]
    for i, (x, y, yaw) in enumerate(spots):
        aset.npc((x, y, 0.0), yaw, dorm=dorms[i % 3], wander=8.0)
    return aset


PLACEMENTS = {"academy": build_academy, "plaza": build_plaza}
