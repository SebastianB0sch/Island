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
from contextlib import contextmanager

from . import AssetSet
from . import interior as K
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
DUEL_W, DUEL_H = 4.4, 4.4         # duelist gate (arena -> waiting room)
# classroom wings (east coords; the west wing is the mirror image)
WY0, WY1, WXO = 2.0, 28.0, 88.5
W_TOP = 10.9                      # top of the hollow part of the wings (lid underside = W_CEIL)
W_CEIL = 10.6
CORR_Y = (2.4, 7.0)               # wing corridor (inside faces)
DR_X = (37.77, 47.5)              # duelist waiting room
HALL_A = (47.8, 67.75)
HALL_B = (68.05, 87.85)
HALL_Y = (7.3, 27.6)
EB_TOP = 6.4                      # end blocks / annex: ground floor ceiling


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


def door_frame(mb, pos, yaw, w=2.8, h=3.6, frame="M_Gold"):
    """Gold portal frame around a real doorway (w x h clear opening) on a wall face.
    pos = bottom centre on the wall face, front = local -Y. The leaves are automatic doors (aset.door)."""
    hw = w / 2
    with mb.at(pos, rot=yaw):
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


# ============================================================================ interior toolkit
WARM = (1.0, 0.9, 0.75)
IN_WALL = K.PLASTER_WHITE          # inside face of the academy walls
BLUE_T = "M_IntAcadBlue"           # cel versions of the academy blue for interiors
NAVY_T = "M_IntAcadNavy"
palette.register({
    "M_IntAcadBlue": dict(kind="toon", color=(0.16, 0.33, 0.78), rough=0.6, fill=0.3),
    "M_IntAcadNavy": dict(kind="toon", color=(0.09, 0.15, 0.40), rough=0.6, fill=0.3),
    "M_IntDuelMat":  dict(kind="toon", color=(0.10, 0.22, 0.45), rough=0.8, fill=0.3, detail="Fabric",
                          tiling=2.0, detail_strength=0.3),
    "M_IntFlaskGlow": dict(kind="emissive", color=(0.45, 1.0, 0.65), strength=3.0),
})


def win_us(L, count, w):
    """Window centres along a facade segment, exactly as MeshBuilder.facade_windows spaces them."""
    margin = (L / count - w) / 2
    step = (L - 2 * margin) / count
    return [margin + step * (i + 0.5) for i in range(count)]


def fwin(mb, p0, p1, z, count, w, h, cut=None, glass="M_Glass", frame="M_WindowFrame", depth=0.06):
    """One row of MeshBuilder.facade_windows. Windows for which cut((x, y)) is true are real openings in a
    hollow wall: they keep their exterior frame + sill but lose the opaque facade pane (the clear pane sits
    in the wall opening, see K.Window)."""
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    yaw = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0]))
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    fw = 0.1
    with mb.at((p0[0], p0[1], 0.0), rot=yaw):
        for u in win_us(L, count, w):
            c = (p0[0] + ux * u, p0[1] + uy * u)
            if not (cut and cut(c)):
                mb.box((u, -depth / 2, z + h / 2), (w, depth, h), glass, skip=("+y",))
            mb.box((u - w / 2 - fw / 2, -depth, z + h / 2), (fw, depth * 2, h + 2 * fw), frame, skip=("+y",))
            mb.box((u + w / 2 + fw / 2, -depth, z + h / 2), (fw, depth * 2, h + 2 * fw), frame, skip=("+y",))
            mb.box((u, -depth, z + h + fw / 2), (w, depth * 2, fw), frame, skip=("+y",))
            mb.box((u, -depth * 2, z - fw / 2), (w + 0.3, depth * 4, fw), frame, skip=("+y",))


def win_pos(p0, p1, count, w):
    """World centres (x, y) of the windows of a facade_windows segment."""
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    return [(p0[0] + ux * u, p0[1] + uy * u) for u in win_us(L, count, w)]


def WIN(c, w, z0, z1):
    """Cut window (clear pane + frame + inside sill) for K.wall."""
    return K.Window(c, w, z0, z1, glass="M_IntGlassClear", frame="M_WindowFrame", mullions=0,
                    sill=K.TRIM_WHITE)


class Fr:
    """2D authoring frame: local (x, y) -> world, a rotation (multiples of 90 deg) and an optional mirror.
    Used so one interior can be authored once and placed on both (mirrored) sides of the academy."""

    def __init__(self, m=(1.0, 0.0, 0.0, 1.0), o=(0.0, 0.0)):
        self.m, self.o = m, o

    @staticmethod
    def make(ox=0.0, oy=0.0, rot=0.0, mx=False):
        ca, sa = round(math.cos(rot * D2R), 9), round(math.sin(rot * D2R), 9)
        a, b, c, d = ca, -sa, sa, ca
        if mx:
            a, c = -a, -c
        return Fr((a, b, c, d), (ox, oy))

    def sub(self, ox, oy, rot=0.0, mx=False):
        L = Fr.make(ox, oy, rot, mx)
        a, b, c, d = self.m
        e, f, g, h = L.m
        return Fr((a * e + b * g, a * f + b * h, c * e + d * g, c * f + d * h), self.p(*L.o))

    def p(self, x, y):
        a, b, c, d = self.m
        return (a * x + b * y + self.o[0], c * x + d * y + self.o[1])

    def v(self, x, y):
        a, b, c, d = self.m
        return (a * x + b * y, c * x + d * y)

    @property
    def mirrored(self):
        a, b, c, d = self.m
        return a * d - b * c < 0

    def yaw(self, t):
        fx, fy = self.v(math.sin(t * D2R), -math.cos(t * D2R))
        return round(math.degrees(math.atan2(fx, -fy)), 6)

    def rect(self, x0, y0, x1, y1):
        ax, ay = self.p(x0, y0)
        bx, by = self.p(x1, y1)
        return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)

    def side(self, s):
        v = {"+x": (1, 0), "-x": (-1, 0), "+y": (0, 1), "-y": (0, -1)}.get(s)
        if v is None:
            return s
        wx, wy = self.v(*v)
        if abs(wx) > abs(wy):
            return "+x" if wx > 0 else "-x"
        return "+y" if wy > 0 else "-y"


class Ctx:
    """Everything an interior needs: the AssetSet, the collision mesh, the no-collision dressing mesh and
    an authoring frame. All coordinates passed to the methods are LOCAL to the frame."""

    def __init__(self, aset, mb, nc, F=None):
        self.a, self.mb, self.nc, self.F = aset, mb, nc, F or Fr()

    def sub(self, ox, oy, rot=0.0, mx=False):
        return Ctx(self.a, self.mb, self.nc, self.F.sub(ox, oy, rot, mx))

    def P(self, x, y, z):
        return (*self.F.p(x, y), z)

    # --- geometry
    def box(self, x0, y0, z0, x1, y1, z1, mat, mats=None, skip=(), nc=False):
        a, b, c, d = self.F.rect(x0, y0, x1, y1)
        (self.nc if nc else self.mb).box_mm(
            (a, b, z0), (c, d, z1), mat, skip=tuple(self.F.side(s) for s in skip),
            mats={self.F.side(k): v for k, v in mats.items()} if mats else None)

    def wall(self, p0, p1, z0, h, t, mat, inner=None, ops=(), mb=None, **kw):
        a, b = self.F.p(*p0), self.F.p(*p1)
        if self.F.mirrored:
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            new = []
            for o in ops:
                o2 = K._copy(o)
                o2.c = L - o.c
                new.append(o2)
            ops, a, b = new, b, a
        return K.wall(self.a, mb or self.mb, a, b, z0, h, t, mat, inner, ops, **kw)

    def poly_prism(self, pts, z0, z1, mat, top=None, bottom=True, nc=False):
        w = [self.F.p(*q) for q in pts]
        if not K._ccw(w):
            w.reverse()
        (self.nc if nc else self.mb).prism(w, z0, z1, mat, top_mat=top, cap_bottom=bottom)

    @contextmanager
    def at(self, x, y, z, yaw=0.0):
        """Local transform for small compound pieces (rotated, never mirrored)."""
        with self.mb.at(self.P(x, y, z), rot=self.F.yaw(yaw)), self.nc.at(self.P(x, y, z), rot=self.F.yaw(yaw)):
            yield

    @contextmanager
    def zat(self, z):
        with self.mb.at((0, 0, z)), self.nc.at((0, 0, z)):
            yield

    def kit(self, fn, x, y, yaw, z=FLOOR, **kw):
        """Kit furniture that is modelled at z = 0 (beds, desks, bookcases, lockers ...)."""
        with self.zat(z):
            fn(self.mb, self.nc, *self.F.p(x, y), self.F.yaw(yaw), **kw)

    def floor(self, x0, y0, x1, y1, mat, z=FLOOR, planks=False, along="x"):
        a, b, c, d = self.F.rect(x0, y0, x1, y1)
        if planks:
            if along in ("x", "y") and abs(self.F.m[0]) < 0.5:
                along = "y" if along == "x" else "x"
            K.floor_planks(self.mb, a, b, c, d, z + 0.004, mat, along=along, pitch=0.3)
        else:
            self.mb.box_mm((a, b, z - 0.02), (c, d, z + 0.004), mat, skip=("-z",))

    def rug(self, x0, y0, x1, y1, mat, border=None, z=FLOOR + 0.005):
        a, b, c, d = self.F.rect(x0, y0, x1, y1)
        K.rug(self.nc, a, b, c, d, z, mat, border)

    def wainscot(self, p0, p1, z0, h, mat, cap=K.TRIM_GOLD, gaps=()):
        """Panelling on the face p0->p1 (room on the LEFT, local)."""
        a, b = self.F.p(*p0), self.F.p(*p1)
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if self.F.mirrored:
            a, b = b, a
            gaps = [(L - g1, L - g0) for g0, g1 in gaps]
        K.wainscot(self.nc, a, b, z0, h, mat, cap, gaps)

    # --- sockets
    def prop(self, name, x, y, z=FLOOR, yaw=0.0, scale=1.0):
        self.a.prop(name, self.P(x, y, z), self.F.yaw(yaw), scale)

    def light(self, x, y, z, intensity=3000.0, radius=9.0, color=WARM):
        self.a.light(self.P(x, y, z), color, intensity, radius, night_only=False)

    def panel(self, x, y, z, w=1.2, d=0.3, intensity=3500.0, radius=9.0, light=True):
        x_, y_ = self.F.p(x, y)
        ww, dd = (w, d) if abs(self.F.m[0]) > 0.5 else (d, w)
        self.nc.box((x_, y_, z - 0.03), (ww + 0.06, dd + 0.06, 0.04), K.TRIM_WHITE)
        self.nc.box((x_, y_, z - 0.055), (ww, dd, 0.012), K.PANEL_LIGHT)
        if light:
            self.a.light((x_, y_, z - 0.4), (1.0, 0.95, 0.85), intensity, radius, night_only=False)

    def text(self, s, x, y, z, yaw, size=0.2, color=(0.15, 0.1, 0.08), emissive=False):
        self.a.text(s, self.P(x, y, z), self.F.yaw(yaw), size=size, color=color, emissive=emissive)

    def wtext(self, s, x, y, z, yaw, size=0.2, color=(0.15, 0.1, 0.08), out=0.03, emissive=False):
        """Text on a wall face at (x, y) (local), standing `out` metres proud towards local -Y of yaw."""
        a = math.radians(yaw)
        self.text(s, x + math.sin(a) * out, y - math.cos(a) * out, z, yaw, size, color, emissive)

    def door(self, x, y, z, yaw, w, h, style, double=False, swing="auto"):
        self.a.door(self.P(x, y, z), self.F.yaw(yaw), w, h, style, double, None, swing)

    def npc(self, x, y, yaw, dorm, wander=2.0, z=FLOOR):
        self.a.npc(self.P(x, y, z), self.F.yaw(yaw), dorm=dorm, wander=wander)

    def cam(self, label, pos, target, lens=18.0):
        K.camera(self.a, label, self.P(*pos), self.P(*target), lens)

    # --- kit wrappers that take world coordinates
    def poster(self, x, y, z, yaw, w, h, mat, text=None, color=(1, 1, 1), size=None):
        K.poster(self.nc, self.a, *self.F.p(x, y), z, self.F.yaw(yaw), w, h, mat, text, color, size)

    def bulletin(self, x, y, z, yaw, w=1.4, h=0.9, title=None, seed=1):
        K.bulletin(self.nc, self.a, *self.F.p(x, y), z, self.F.yaw(yaw), w, h, title, seed)

    def blackboard(self, x, y, z, yaw, w, h, lines=(), size=0.13):
        K.blackboard(self.mb, self.nc, self.a, *self.F.p(x, y), z, self.F.yaw(yaw), w, h, lines, size=size)

    def plate(self, x, y, z, yaw, s, w=0.9, h=0.2, mat=BLUE_T, color=(1.0, 0.88, 0.45)):
        K.nameplate(self.nc, self.a, *self.F.p(x, y), z, self.F.yaw(yaw), s, mat, color, w, h)

    def lockers(self, x, y, yaw, n, **kw):
        with self.zat(kw.pop("z", FLOOR)):
            K.lockers(self.mb, self.nc, self.a, *self.F.p(x, y), self.F.yaw(yaw), n=n, **kw)


def clip_rect(poly, x0, y0, x1, y1):
    """Sutherland-Hodgman clip of a convex polygon against an axis aligned rectangle."""
    def clip(pts, inside, inter):
        out = []
        for i in range(len(pts)):
            cur, prev = pts[i], pts[i - 1]
            if inside(cur):
                if not inside(prev):
                    out.append(inter(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(inter(prev, cur))
        return out

    def ix(xv):
        return lambda p, q: (xv, p[1] + (q[1] - p[1]) * (xv - p[0]) / (q[0] - p[0]))

    def iy(yv):
        return lambda p, q: (p[0] + (q[0] - p[0]) * (yv - p[1]) / (q[1] - p[1]), yv)

    for inside, inter in ((lambda p: p[0] >= x0 - 1e-9, ix(x0)), (lambda p: p[0] <= x1 + 1e-9, ix(x1)),
                          (lambda p: p[1] >= y0 - 1e-9, iy(y0)), (lambda p: p[1] <= y1 + 1e-9, iy(y1))):
        poly = clip(poly, inside, inter)
        if len(poly) < 3:
            return []
    out = []
    for p in poly:
        if not out or math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) > 1e-5:
            out.append(p)
    if len(out) > 2 and math.hypot(out[0][0] - out[-1][0], out[0][1] - out[-1][1]) < 1e-5:
        out.pop()
    if len(out) < 3:
        return []
    area = 0.0
    for i in range(len(out)):
        area += out[i - 1][0] * out[i][1] - out[i][0] * out[i - 1][1]
    return out if abs(area) > 1e-4 else []


def sector(c, r0, r1, a, b):
    return [polar(r0, a, c), polar(r0, b, c), polar(r1, b, c), polar(r1, a, c)]


def lecture_tiers(C, c, rect, z0, r0, rows, depth, rise, aisles, ahalf=5.0, seg=10.0,
                  step="M_IntWoodFloor", riser="M_IntWood", desk="M_IntWood", seat="M_IntFabricBlue"):
    """Curved stepped seating of the GX lecture hall, clipped to the room rectangle (local coords).
    Tiers face the centre c (the teacher's podium), span 0..180 deg, the last tier runs on to the back wall.
    Radial aisles at the given angles climb in half steps (rise / 2 <= 0.2 m). Every tier carries a curved
    desk on its inner edge with a bench behind it."""
    x0, y0, x1, y1 = rect
    spans, cur = [], 0.0
    for a in sorted(aisles):
        spans.append((cur, a - ahalf))
        cur = a + ahalf
    spans.append((cur, 180.0))

    def piece(r_in, r_out, a, b, za, zb, mat, top, bottom=False):
        pts = clip_rect(sector(c, r_in, r_out, a, b), x0, y0, x1, y1)
        if pts:
            C.poly_prism(pts, za, zb, mat, top=top, bottom=bottom)

    for k in range(rows):
        r_in = r0 + depth * k
        r_out = r_in + depth if k < rows - 1 else 60.0
        zt = z0 + rise * (k + 1)
        for (a0, a1) in spans:
            n = max(1, int(math.ceil((a1 - a0) / seg - 1e-6)))
            for i in range(n):
                a = a0 + (a1 - a0) * i / n
                b = a0 + (a1 - a0) * (i + 1) / n
                piece(r_in, r_out, a, b, z0, zt, riser, step)
                piece(r_in + 0.05, r_in + 0.45, a, b, zt + 0.68, zt + 0.72, desk, desk, True)    # desk top
                piece(r_in + 0.05, r_in + 0.08, a, b, zt, zt + 0.68, "M_IntWoodDark", None)     # modesty panel
                piece(r_in + 0.78, r_in + 1.13, a, b, zt, zt + 0.44, "M_IntWoodDark", seat)      # bench
        for a in aisles:
            rm = r_in + min(depth, 2.0) / 2
            piece(r_in, rm, a - ahalf, a + ahalf, z0, zt - rise / 2, riser, step)
            piece(rm, r_out if k < rows - 1 else r_in + depth, a - ahalf, a + ahalf, z0, zt, riser, step)
            if k == rows - 1:
                piece(r_in + depth, 60.0, a - ahalf, a + ahalf, z0, zt, riser, step)
            # gold nosing on the aisle steps
            piece(r_in, r_in + 0.05, a - ahalf, a + ahalf, zt - rise / 2, zt - rise / 2 + 0.006, K.TRIM_GOLD,
                  None)
            piece(rm, rm + 0.05, a - ahalf, a + ahalf, zt, zt + 0.006, K.TRIM_GOLD, None)


def duel_disk(C, x, y, z, yaw):
    """Small GX style duel disk lying on a shelf / table (dressing)."""
    with C.at(x, y, z, yaw):
        C.nc.cylinder((0, 0, 0), 0.09, 0.06, "M_IntMetal", seg=10)
        C.nc.box((0.0, 0.0, 0.035), (0.32, 0.1, 0.03), "M_IntMetal")
        C.nc.box((0.33, 0.0, 0.02), (0.5, 0.17, 0.02), BLUE_T)
        for k in range(5):
            C.nc.box((0.13 + k * 0.1, 0.0, 0.032), (0.07, 0.1, 0.006), "M_IntPaper")
        C.nc.cylinder((0, 0, 0.06), 0.05, 0.01, "M_IntScreen", seg=10)


def card_fan(C, x, y, z, n=5, yaw=0.0, mats=("M_CardPack", "M_CardPackBlue", "M_CardPackPurple", "M_IntPaper")):
    """A few duel monster cards scattered on a table (dressing)."""
    for i in range(n):
        with C.at(x + (i - n / 2) * 0.09, y + ((i * 37) % 5) * 0.02, z, yaw + (i * 23) % 50 - 25):
            C.nc.box((0, 0, 0.003), (0.06, 0.087, 0.006), mats[i % len(mats)])


def plinth_bust(C, x, y, yaw, mat="M_Marble", z=FLOOR):
    C.box(x - 0.3, y - 0.3, z, x + 0.3, y + 0.3, z + 1.05, mat)
    C.box(x - 0.34, y - 0.34, z + 1.05, x + 0.34, y + 0.34, z + 1.1, K.TRIM_GOLD)
    C.prop("SM_Int_Bust", x, y, z + 1.1, yaw)


def trophy(C, x, y, z, s=1.0, mat=K.TRIM_GOLD):
    C.nc.lathe([(0.07 * s, 0.0), (0.07 * s, 0.03 * s), (0.025 * s, 0.05 * s), (0.02 * s, 0.14 * s),
                (0.09 * s, 0.22 * s), (0.08 * s, 0.3 * s)], mat, seg=10, center=C.P(x, y, z))


def chair_row(C, x0, x1, y, z, yaw, name="SM_Int_WoodChair", step=0.7):
    n = max(1, int((x1 - x0) / step) + 1)
    for i in range(n):
        C.prop(name, x0 + (x1 - x0) * (i / (n - 1) if n > 1 else 0.5), y, z, yaw)


def dining(C, x, y, yaw=0.0, chairs=6, table="SM_Int_Table", chair="SM_Int_WoodChair", length=1.6, side=0.6,
           z=FLOOR):
    """Table (long side along local x of yaw) with chairs on both long sides."""
    a = math.radians(yaw)

    def Pp(dx, dy):
        return (x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a))
    C.prop(table, x, y, z, yaw)
    per = chairs // 2
    for i in range(per):
        dx = -length / 2 + length * (i + 0.5) / per
        for s in (-1, 1):
            px, py = Pp(dx, s * side)
            C.prop(chair, px, py, z, yaw + (180 if s < 0 else 0))      # sitter faces the table
    if chairs % 2:
        px, py = Pp(length / 2 + 0.5, 0)
        C.prop(chair, px, py, z, yaw - 90)


def sofa_corner(C, x, y, yaw, z=FLOOR, rug=None):
    """Sofa facing local -Y (of yaw) with a coffee table and two armchairs (catalog props)."""
    a = math.radians(yaw)

    def Pp(dx, dy):
        return (x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a))
    C.prop("SM_Int_Sofa", x, y, z, yaw)
    C.prop("SM_Int_CoffeeTable", *Pp(0, -1.3), z, yaw)
    for s in (-1, 1):
        C.prop("SM_Int_Armchair", *Pp(s * 1.7, -1.5), z, yaw + 180 + s * 70)     # turned towards the table
    if rug:
        cx, cy = Pp(0, -1.2)
        hw, hd = (1.9, 1.3) if abs(math.cos(a)) > 0.5 else (1.3, 1.9)
        C.rug(cx - hw, cy - hd, cx + hw, cy + hd, rug, K.TRIM_GOLD, z + 0.01)


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


def glass_screen(mb, aset, pos, yaw, W, H, dw, dh, style, frame="M_AcademyBlue", trim="M_Gold"):
    """Glazed screen filling a W x H opening (pos = bottom centre on the wall's middle plane, local -Y outside)
    with a central double automatic door dw x dh, side lights with kick plates and a transom light."""
    hw = W / 2
    with mb.at(pos, rot=yaw):
        for sx in (-1, 1):
            mb.box((sx * (dw / 2 + 0.1), 0, H / 2), (0.2, 0.22, H), trim)            # door posts
            mb.box((sx * (hw - 0.06), 0, H / 2), (0.12, 0.18, H), frame)             # edge posts
            side = hw - 0.12 - (dw / 2 + 0.2)
            cx = sx * (dw / 2 + 0.2 + side / 2)
            mb.box((cx, 0, 0.09), (side, 0.16, 0.18), frame)                          # kick rail
            mb.box((cx, 0, (0.18 + dh) / 2), (side, 0.03, dh - 0.18), "M_GlassClear")
            if side > 2.0:
                mb.box((cx, 0, dh / 2), (0.08, 0.14, dh), frame)                      # mullion
            mb.box((cx, 0, dh * 0.5), (side, 0.12, 0.08), frame)                      # mid rail
        mb.box((0, 0, dh + 0.1), (W - 0.24, 0.22, 0.2), trim)                         # transom bar
        if H - dh > 0.6:
            mb.box((0, 0, (dh + 0.2 + H) / 2), (W - 0.24, 0.03, H - dh - 0.2), "M_GlassClear")
            n = max(1, int(W / 2.5))
            for k in range(1, n):
                mb.box((-hw + W * k / n, 0, (dh + 0.2 + H) / 2), (0.08, 0.14, H - dh - 0.2), frame)
        mb.box((0, 0, H - 0.06), (W, 0.18, 0.12), frame)
    aset.door(pos, yaw, dw, dh, style, double=True)


def _lobby_shell(mb, aset):
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
    mb.box_mm((-6.0, LY1 - LWALL, FLOOR - 0.05), (6.0, LY1 + DT, FLOOR + 0.005), "M_MarbleFloor")
    mb.box_mm((-5.0, LY0, FLOOR - 0.05), (5.0, LY0 + LWALL, FLOOR + 0.005), "M_Gold")
    # glazed screens with automatic doors in the two monumental openings
    glass_screen(mb, aset, (0.0, LY0 + LWALL / 2, FLOOR), 0.0, 10.0, 9.0, 4.0, 4.4, "academy")
    glass_screen(mb, aset, (0.0, LY1 + 0.1, FLOOR), 0.0, 12.0, 9.0, 5.0, 4.6, "academy")


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
        elif mid in (0.0, 180.0):    # duelist passages into the waiting rooms of the classroom wings
            ops = [dict(u=L / 2, w=DUEL_W, z0=FLOOR + 4.0, z1=FLOOR + 4.0 + DUEL_H)]
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


def _wing_facade_common(mb, xa, xb, y0, y1, eave, roof_h, ridge_axis="x", hollow=None):
    if hollow:      # (z0, z1): a walk-in storey; its walls are built separately
        mb.box_mm((xa, y0, -4.0), (xb, y1, hollow[0]), "M_AcademyWall", mats={"+z": K.MARBLEFLOOR})
        mb.box_mm((xa, y0, hollow[1]), (xb, y1, eave - 1.4), "M_AcademyWall", mats={"-z": K.CEIL})
    else:
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


def _wings(mb, nocol, aset):
    """Classroom wings E/W of the drum. Their inner end follows the drum mid-wall so nothing pokes
    into the arena."""
    y0, y1, xo, eave, rh = WY0, WY1, WXO, 20.5, 6.5
    xa_ = drum_mid_x(y0, -22.5)
    for s in (-1, 1):
        # outer skin of the solid parts (below the floor, above the hollow storey). The drum-side faces sit
        # inside the drum wall and the outer end inside the end block, so only the long faces are needed.
        for (za, zb) in ((-4.0, FLOOR), (W_TOP, eave - 1.4)):
            for (ax, ay), (bx, by) in (((xa_, y0), (xo, y0)), ((xo, y1), (xa_, y1))):
                (pa, pb) = ((s * ax, ay), (s * bx, by)) if s > 0 else ((s * bx, by), (s * ax, ay))
                mb.quad((*pa, za), (*pb, za), (*pb, zb), (*pa, zb), "M_AcademyWall")
        _wing_shell(mb, nocol, aset, s)
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
        # windows (only on the free part of the facade); the ground row (and the hall clerestory) are real
        wa, wb = sorted((s * 40.0, s * 88.0))
        n = 14
        mb.facade_windows((wa, y0), (wb, y0), ROWS[1:], n, 1.7, 2.5)
        mb.facade_windows((wb, y1), (wa, y1), ROWS[2:], n, 1.7, 2.5)
        fwin(mb, (wa, y0), (wb, y0), ROWS[0], n, 1.7, 2.5, cut=lambda c: abs(abs(c[0]) - 64.0) > 2.4)
        fwin(mb, (wb, y1), (wa, y1), ROWS[0], n, 1.7, 2.5, cut=lambda c: abs(c[0]) < DR_X[1])
        fwin(mb, (wb, y1), (wa, y1), ROWS[1], n, 1.7, 2.5, cut=lambda c: abs(c[0]) > DR_X[1])
        bay = (wb - wa) / n
        xd = s * 64.0
        for k in range(0, n + 1, 2):
            x = wa + k * bay
            z0p = 6.0 if abs(x - xd) < 0.5 else FLOOR      # the pilaster at the door starts above the portal
            mb.box_mm((x - 0.45, y0 - 0.35, z0p), (x + 0.45, y0 + 0.1, 19.1), "M_AcademyWall")
            mb.box_mm((x - 0.45, y1 - 0.1, FLOOR), (x + 0.45, y1 + 0.35, 19.1), "M_AcademyWall")
        # roof dormers on both long slopes
        for x in (47.5, 54.4, 68.1, 75.0):
            dormer(mb, (s * x, y0), 0.0, eave, rh / 13.0)
            dormer(mb, (s * x, y1), 180.0, eave, rh / 13.0)
        # central portal with steps: blue surround around the real doorway, gold frame, automatic doors
        for (a, b, za, zb) in ((xd - 2.4, xd - 1.4, FLOOR, 6.0), (xd + 1.4, xd + 2.4, FLOOR, 6.0),
                               (xd - 1.4, xd + 1.4, FLOOR + 3.4, 6.0)):
            mb.box_mm((a, y0 - 0.3, za), (b, y0 + 0.1, zb), "M_AcademyBlue")
        door_frame(mb, (xd, y0 - 0.3, FLOOR), 0.0, 2.8, 3.4)
        mb.box_mm((xd - 1.4, y0 - 0.32, FLOOR - 0.2), (xd + 1.4, CORR_Y[0] + 0.02, FLOOR + 0.01), "M_Marble")
        aset.door((xd, (y0 - 0.3 + CORR_Y[0]) / 2, FLOOR), 0.0, 2.8, 3.4, "academy", double=True)
        entry_steps(mb, (xd, y0 - 0.3), 0.0, 4.2)
        # dorm banners on the pilasters
        cols = ("M_AcademyRed", "M_AcademyYellow") if s < 0 else ("M_AcademyBlue", "M_AcademyYellow")
        for j, xx in enumerate((s * 53.71, s * 74.29)):
            banner(nocol, (xx, y0 - 0.5, 18.6), 0.0, 2.2, 9.0, cols[j])


def _end_blocks(mb, nocol, aset):
    y0, y1 = -40.0, 50.0
    for s in (-1, 1):
        xa, xb = sorted((s * 88.0, s * 114.0))
        _wing_facade_common(mb, xa, xb, y0, y1, 22.4, 8.0, ridge_axis="y", hollow=(FLOOR, EB_TOP))
        xo, xi = s * 114.0, s * 88.0
        rows = ROWS[1:] + [19.6]
        yd = -19.0

        def cut(c):     # every ground-floor window is real except the two hidden behind the side portal
            return not (abs(abs(c[0]) - 88.0) < 0.1 and abs(c[1] - yd) < 2.4)
        if s > 0:
            segs = [((xo, y0), (xo, y1), 26), ((xi, 2.0), (xi, y0), 12), ((xi, y1), (xi, 28.0), 6)]
            segs_s = [((88.0, y0), (94.0, y0)), ((108.0, y0), (114.0, y0))]
            segs_n = [((94.0, y1), (88.0, y1)), ((114.0, y1), (108.0, y1))]
        else:
            segs = [((xo, y1), (xo, y0), 26), ((xi, y0), (xi, 2.0), 12), ((xi, 28.0), (xi, y1), 6)]
            segs_s = [((-114.0, y0), (-108.0, y0)), ((-94.0, y0), (-88.0, y0))]
            segs_n = [((-108.0, y1), (-114.0, y1)), ((-88.0, y1), (-94.0, y1))]
        segs += [(p0, p1, 1) for p0, p1 in segs_s + segs_n]
        for p0, p1, n in segs:
            mb.facade_windows(p0, p1, rows, n, 1.7, 2.5)
            fwin(mb, p0, p1, ROWS[0], n, 1.7, 2.5, cut=cut)
        # pilasters on the forecourt face (the one on the portal axis starts above the portal)
        for k in range(0, 13, 3):
            y = y0 + k * (2.0 - y0) / 12
            xa_, xb_ = sorted((xi, xi - s * 0.35))
            mb.box_mm((xa_, y - 0.45, 6.0 if abs(y - yd) < 0.1 else FLOOR), (xb_, y + 0.45, 21.0), "M_AcademyWall")
        _end_block_shell(mb, nocol, aset, s)
        # roof dormers (outer slope + forecourt slope)
        sl = 8.0 / 13.0
        for y in (-26.0, -14.0, -2.0, 10.0, 22.0, 34.0):
            dormer(mb, (xo, y), 90.0 * s, 22.4, sl)
        for y in (-26.0, -12.0, 38.0):
            dormer(mb, (xi, y), -90.0 * s, 22.4, sl)
        # side portal into the forecourt: blue surround around the real doorway
        with mb.at((xi, yd, 0.0), rot=-90.0 * s):
            for (cx, w, za, zb) in ((-1.9, 1.0, FLOOR, 6.0), (1.9, 1.0, FLOOR, 6.0), (0.0, 2.8, FLOOR + 3.4, 6.0)):
                mb.box((cx, -0.15, (za + zb) / 2), (w, 0.3, zb - za), "M_AcademyBlue")
            mb.box((0.0, 0.1, FLOOR - 0.095), (2.8, 0.85, 0.21), "M_Marble")
        door_frame(mb, (xi - s * 0.3, yd, FLOOR), -90.0 * s, 2.8, 3.4)
        aset.door((xi + s * 0.1, yd, FLOOR), -90.0 * s, 2.8, 3.4, "academy", double=True)
        entry_steps(mb, (xi - s * 0.3, yd), -90.0 * s, 4.2)


def _wing_shell(mb, nocol, aset, s):
    """Hollow storey of a classroom wing (east coords, mirrored for s < 0): outer walls with the real
    ground-floor / clerestory windows and the main portal, floor slab and the lid under the solid upper part."""
    C = Ctx(aset, mb, nocol, Fr.make(mx=s < 0))
    x_in = 34.6                       # wall ends are buried in the drum wall
    hz = W_TOP - FLOOR
    ops = [WIN(x - x_in, 1.7, 1.0, 3.5) for x, _ in win_pos((40.0, WY0), (88.0, WY0), 14, 1.7)
           if abs(x - 64.0) > 2.4]
    ops.append(K.Door(64.0 - x_in, 2.8, 3.4, style=None, trim_in=K.TRIM_GOLD))
    C.wall((x_in, WY0), (88.0, WY0), FLOOR, hz, CORR_Y[0] - WY0, "M_AcademyWall", inner=IN_WALL, ops=ops,
           base=BLUE_T)
    ops = []
    for x, _ in win_pos((88.0, WY1), (40.0, WY1), 14, 1.7):
        ops.append(WIN(88.0 - x, 1.7, 1.0, 3.5) if x < DR_X[1] else WIN(88.0 - x, 1.7, 5.5, 8.0))
    C.wall((88.0, WY1), (x_in, WY1), FLOOR, hz, WY1 - HALL_Y[1], "M_AcademyWall", inner=IN_WALL, ops=ops,
           base=BLUE_T)
    C.box(37.27, WY0, FLOOR - 0.3, 88.0, WY1, FLOOR, "M_AcademyStone", mats={"+z": K.MARBLEFLOOR},
          skip=("-y", "+y"))
    C.box(37.27, WY0, W_CEIL, 88.0, WY1, W_TOP, "M_AcademyWall", mats={"-z": K.CEIL}, skip=("-y", "+y"))


EB_T = 0.5
EB_CX = (99.0, 103.0)             # end block corridor (inside faces)
EB_WX = (88.5, 98.75)             # west rooms (forecourt side)
EB_EX = (103.25, 113.5)           # east rooms (outer side)


def _end_block_shell(mb, nocol, aset, s):
    """Ground storey walls of an end pavilion (east coords, mirrored for s < 0)."""
    C = Ctx(aset, mb, nocol, Fr.make(mx=s < 0))
    h, t = EB_TOP - FLOOR, EB_T
    outer = [y for _, y in win_pos((114.0, -40.0), (114.0, 50.0), 26, 1.7)]
    fc_s = [y for _, y in win_pos((88.0, 2.0), (88.0, -40.0), 12, 1.7)]
    fc_n = [y for _, y in win_pos((88.0, 50.0), (88.0, 28.0), 6, 1.7)]
    kw = dict(inner=IN_WALL, base=BLUE_T)
    tower = K.Door(13.0, 2.2, 2.7, "academy", double=True, trim_in=K.TRIM_GOLD, trim=K.TRIM_GOLD)
    C.wall((88.0, -40.0), (114.0, -40.0), FLOOR, h, t, "M_AcademyWall",
           ops=[WIN(3.0, 1.7, 1.0, 3.5), tower, WIN(23.0, 1.7, 1.0, 3.5)], **kw)
    C.wall((114.0, 50.0), (88.0, 50.0), FLOOR, h, t, "M_AcademyWall",
           ops=[WIN(3.0, 1.7, 1.0, 3.5), tower, WIN(23.0, 1.7, 1.0, 3.5)], **kw)
    C.wall((114.0, -39.5), (114.0, 49.5), FLOOR, h, t, "M_AcademyWall",
           ops=[WIN(y + 39.5, 1.7, 1.0, 3.5) for y in outer], **kw)
    C.wall((88.0, 49.5), (88.0, 28.0), FLOOR, h, t, "M_AcademyWall",
           ops=[WIN(49.5 - y, 1.7, 1.0, 3.5) for y in fc_n], **kw)
    C.wall((88.0, 28.0), (88.0, 2.0), FLOOR, h, t, IN_WALL,
           ops=[K.Door(28.0 - 4.7, 2.0, 2.8, "academy_wood", double=True, trim=K.TRIM_GOLD,
                       trim_in=K.TRIM_GOLD)], **kw)
    C.wall((88.0, 2.0), (88.0, -39.5), FLOOR, h, t, "M_AcademyWall",
           ops=[WIN(2.0 - y, 1.7, 1.0, 3.5) for y in fc_s if abs(y + 19.0) > 2.4]
           + [K.Door(21.0, 2.8, 3.4, style=None, trim_in=K.TRIM_GOLD)], **kw)


ANX_Y = (53.0, 75.5)              # rear annex ground floor (inside faces)


def _rear_annex(mb, nocol, aset):
    """Two-storey service annex behind the arena (flat roof); its south side follows the drum wall.
    The ground floor is walk-in (faculty offices), the upper floor stays solid."""
    xa, xb, y1, top = -20.0, 20.0, 76.0, 10.0
    ys = drum_mid_y(xb, 67.5)
    w1, e1 = polar(RM, 101.25, DC), polar(RM, 78.75, DC)
    pts = [(xa, ys), w1, e1, (xb, ys), (xb, y1), (xa, y1)]
    mb.prism(pts, -4.0, FLOOR, "M_AcademyWall", cap_top=False, cap_bottom=False)
    mb.prism(pts, EB_TOP, top, "M_AcademyWall", cap_top=False, cap_bottom=False)
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
    allcut = lambda c: True  # noqa: E731
    fwin(mb, (xb, y1), (3.2, y1), 3.0, 4, 1.7, 2.5, cut=allcut)
    fwin(mb, (-3.2, y1), (xa, y1), 3.0, 4, 1.7, 2.5, cut=allcut)
    mb.facade_windows((xb, y1), (xa, y1), [7.0], 9, 1.7, 1.6)
    mb.facade_windows((xb, 54.0), (xb, y1), [7.0], 5, 1.7, 2.0)
    mb.facade_windows((xa, y1), (xa, 54.0), [7.0], 5, 1.7, 2.0)
    fwin(mb, (xb, 54.0), (xb, y1), 3.0, 5, 1.7, 2.0, cut=allcut)
    fwin(mb, (xa, y1), (xa, 54.0), 3.0, 5, 1.7, 2.0, cut=allcut)
    # ground floor walls (inside the footprint, outer faces on the old skin)
    C = Ctx(aset, mb, nocol)
    h, kw = EB_TOP - FLOOR, dict(inner=IN_WALL, base=BLUE_T)
    nx = [x for x, _ in win_pos((xb, y1), (3.2, y1), 4, 1.7) + win_pos((-3.2, y1), (xa, y1), 4, 1.7)]
    sy = [y for _, y in win_pos((xb, 54.0), (xb, y1), 5, 1.7)]
    C.wall((xb, y1), (xa, y1), FLOOR, h, 0.5, "M_AcademyWall",
           ops=[WIN(xb - x, 1.7, 1.0, 3.5) for x in nx]
           + [K.Door(xb, 2.8, 3.4, "academy", double=True, trim_in=K.TRIM_GOLD)], **kw)
    C.wall((xb, 46.6), (xb, y1 - 0.5), FLOOR, h, 0.5, "M_AcademyWall",
           ops=[WIN(y - 46.6, 1.7, 1.0, 3.0) for y in sy], **kw)
    C.wall((xa, y1 - 0.5), (xa, 46.6), FLOOR, h, 0.5, "M_AcademyWall",
           ops=[WIN(y1 - 0.5 - y, 1.7, 1.0, 3.0) for y in sy], **kw)
    C.box(xa + 0.5, ANX_Y[0], FLOOR - 0.3, xb - 0.5, ANX_Y[1], FLOOR, "M_AcademyStone", mats={"+z": K.MARBLEFLOOR})
    C.box(xa + 0.5, ANX_Y[0] - 0.5, EB_TOP, xb - 0.5, ANX_Y[1], EB_TOP + 0.3, "M_AcademyWall", mats={"-z": K.CEIL})
    # rear entrance with canopy
    door_frame(mb, (0.0, y1, FLOOR), 180.0, 2.8, 3.4)
    entry_steps(mb, (0.0, y1), 180.0, 5.0)
    mb.box_mm((-3.4, y1, 5.9), (3.4, y1 + 2.4, 6.25), "M_AcademyBlue")
    mb.box_mm((-3.5, y1, 6.25), (3.5, y1 + 2.5, 6.4), "M_Gold")
    for sx in (-1, 1):
        mb.cylinder((sx * 3.0, y1 + 2.0, FLOOR), 0.18, 3.9, "M_Gold", seg=10)


TW_H, TW_CEIL = 6.0, 8.3           # tower base half size / ground hall ceiling


def tower_frame(cx, cy, front):
    """Local frame of a tower base: origin at the centre, the entrance in the local south (-y) wall."""
    return Fr.make(cx, cy, 0.0 if front else 180.0, mx=cx < 0)


def _tower(mb, nocol, aset, cx, cy, accent, front):
    h = TW_H
    zt = 11.0
    # walk-in ground hall: solid plinth below, solid top (balcony floor) above the hall ceiling
    mb.box_mm((cx - h, cy - h, -4.0), (cx + h, cy + h, 0.0), "M_AcademyWall", mats={"+z": K.MARBLEFLOOR})
    mb.box_mm((cx - h, cy - h, TW_CEIL), (cx + h, cy + h, zt), "M_AcademyWall", mats={"-z": K.CEIL})
    C = Ctx(aset, mb, nocol, tower_frame(cx, cy, front))
    kw = dict(inner=IN_WALL, base=BLUE_T)
    wy = [2.8667 - 6.0, 0.0, 6.0 - 2.8667]          # side window centres (local y), as facade_windows spaces them
    C.wall((-h, -h), (h, -h), 0.0, TW_CEIL, 0.5, "M_AcademyWall",
           ops=[K.Door(h, 3.0, 3.8, "academy", double=True, trim_in=K.TRIM_GOLD)], **kw)
    C.wall((h, -h + 0.5), (h, h), 0.0, TW_CEIL, 0.5, "M_AcademyWall",
           ops=[WIN(y + h - 0.5, 1.4, 3.0, 6.6) for y in wy], **kw)
    C.wall((-h, h), (-h, -h + 0.5), 0.0, TW_CEIL, 0.5, "M_AcademyWall",
           ops=[WIN(h - y, 1.4, 3.0, 6.6) for y in wy], **kw)
    # stone plinth band, interrupted by the doorway
    rect_band(mb, cx - h, cy - h, cx + h, cy + h, -4.0, FLOOR - 1.0, 0.3, "M_AcademyStone",
              sides="new" if front else "sew")
    o = 0.3
    yb0, yb1 = (cy - h - o, cy - h + 0.3) if front else (cy + h - 0.3, cy + h + o)
    for xa_, xb_ in ((cx - h - o, cx - 1.8), (cx + 1.8, cx + h + o)):
        mb.box_mm((xa_, yb0, -4.0), (xb_, yb1, FLOOR - 1.0), "M_AcademyStone")
    ys0, ys1 = (cy - h - o, cy - h) if front else (cy + h, cy + h + o)
    mb.box_mm((cx - 1.8, ys0, -4.0), (cx + 1.8, ys1, 0.0), "M_AcademyStone")
    rect_band(mb, cx - h, cy - h, cx + h, cy + h, 8.3, 9.5, 0.18, "M_AcademyBlue")
    rect_band(mb, cx - h, cy - h, cx + h, cy + h, 9.5, 9.75, 0.3, "M_Gold")
    rect_band(mb, cx - h, cy - h, cx + h, cy + h, 9.75, zt, 0.65, "M_AcademyRoof")
    # balcony railing around the shaft
    e = h - 0.3
    mb.railing([(cx - e, cy - e, zt), (cx + e, cy - e, zt), (cx + e, cy + e, zt), (cx - e, cy + e, zt),
                (cx - e, cy - e, zt)], 1.1, "M_Gold", post_spacing=1.7)
    # portal frame on the outer face, real windows on the sides
    fy = cy - h if front else cy + h
    door_frame(mb, (cx, fy, 0.0), 0.0 if front else 180.0, 3.0, 3.8)
    for p0, p1 in (((cx + h, cy - h), (cx + h, cy + h)), ((cx - h, cy + h), (cx - h, cy - h))):
        fwin(mb, p0, p1, 3.0, 3, 1.4, 3.6, cut=lambda c: True)
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
    for s in (1,):      # (the west wall has the admissions office / duel disk service rooms in front)
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
    # (the staff doors open into the rooms built by _lobby_rooms)
    # trophy case near the arena portal (west) and vending machines (east)
    mb.box_mm((-19.6, -27.4, FLOOR), (-12.6, -24.3, FLOOR + 0.9), "M_DarkWood")
    mb.box_mm((-19.4, -27.2, FLOOR + 0.9), (-12.8, -24.5, FLOOR + 2.6), "M_GlassClear")
    mb.box_mm((-19.6, -27.4, FLOOR + 2.6), (-12.6, -24.3, FLOOR + 2.75), "M_DarkWood")
    for i, x in enumerate((-17.7, -16.1, -14.5)):
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
    K.camera(aset, "lobby", (0.0, -63.5, 5.0), (0.0, -26.0, 8.5), 16)


# ---------------------------------------------------------------------------- interior: card shop
def _card_shop(mb, aset):
    X0, X1, Y0, Y1 = 18.0, LX - LWALL, -60.0, -30.0
    SH = 6.5
    clear = dict(glass="M_GlassClear", frame="M_Gold")
    glass_screen(mb, aset, (X0 + 0.25, -45.0, FLOOR), -90.0, 9.0, 4.2, 3.0, 2.8, "glass", frame="M_Gold")
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
    K.camera(aset, "card_shop", (11.0, -38.0, 4.2), (26.0, -47.0, 3.4), 18)


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
            door_frame(mb, (dpos[0], dpos[1], FLOOR), mid + 270.0, DUEL_W, DUEL_H)
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
    K.camera(aset, "arena", (C[0] + 21.0, C[1] - 25.0, 12.5), (C[0], C[1], 4.0), 16)
    K.camera(aset, "arena_portal", (C[0], C[1] - 33.5, 4.2), (C[0], C[1] + 20.0, 14.0), 16)


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
    inc = aset.mesh("Academy_Interior_NoCol")
    _podium_and_steps(main)
    _lobby_shell(main, aset)
    _portico(main, aset)
    _drum(main, nocol)
    _pyramid(main)
    _wings(main, nocol, aset)
    _end_blocks(main, nocol, aset)
    _rear_annex(main, nocol, aset)
    _towers(towers, nocol, aset)
    _lobby_interior(inter, nocol, aset)
    _card_shop(inter, aset)
    _arena(arena, nocol, aset)
    _academy_dressing(main, aset)
    _interiors(aset, inter, inc)
    return aset


# ---------------------------------------------------------------------------- interiors: classroom wings
def _plate_door(C, x, y, yaw, s, z=FLOOR + 2.55):
    """Room sign above / beside a door (x, y on the corridor face, yaw: -Y towards the corridor)."""
    C.plate(x, y, z, yaw, s, w=max(1.0, 0.13 * len(s) + 0.3), h=0.26)


def _wing_interior(C, s):
    side = "EAST" if s > 0 else "WEST"
    cy0, cy1 = CORR_Y
    hall_doors = {HALL_A: (49.5, 66.0), HALL_B: (70.0, 86.0)}
    # ---------------- corridor (y 2.4 .. 7.0) along the south facade
    C.box(37.5, cy0, FLOOR, 38.0, cy1, 6.2, IN_WALL)
    C.box(38.0, cy0, 6.2, 88.0, cy1, 6.4, IN_WALL, mats={"-z": K.CEIL})
    hz = W_CEIL - FLOOR
    kw = dict(base=BLUE_T, trim=K.TRIM_WOOD, trim_in=K.TRIM_WOOD)
    C.wall((37.77, cy1), (47.65, cy1), FLOOR, hz, 0.3, IN_WALL, inner=IN_WALL,
           ops=[K.Door(42.5 - 37.77, 1.0, 2.2, "classroom")], **kw)
    for (x0, x1), xs in hall_doors.items():
        a, b = (47.65, 67.9) if x0 == HALL_A[0] else (67.9, 88.0)
        C.wall((a, cy1), (b, cy1), FLOOR, hz, 0.3, IN_WALL, inner=IN_WALL,
               ops=[K.Door(x - a, 1.0, 2.2, "classroom") for x in xs], **kw)
    doors = [42.5] + [x for xs in hall_doors.values() for x in xs]
    C.wainscot((88.0, cy1), (38.0, cy1), FLOOR, 0.9, BLUE_T,
               gaps=[(88.0 - x - 0.62, 88.0 - x + 0.62) for x in doors])
    C.wainscot((38.0, cy0), (88.0, cy0), FLOOR, 0.85, BLUE_T, gaps=[(64.0 - 38.0 - 1.55, 64.0 - 38.0 + 1.55)])
    C.rug(38.6, 4.0, 86.8, 5.4, BLUE_T, K.TRIM_GOLD)
    for x in range(41, 88, 5):
        C.panel(x, 4.7, 6.2, 1.2, 0.35, light=(x - 41) % 10 == 0, intensity=3500, radius=10)
    # lockers, notice boards, benches under the windows, plants
    C.lockers(54.8, cy1 - 0.24, 0.0, 18, d=0.45)
    C.lockers(75.3, cy1 - 0.24, 0.0, 18, d=0.45)
    C.bulletin(61.6, cy1, FLOOR + 1.2, 0.0, 2.4, 1.1, "ACADEMY NOTICES", seed=3 + s)
    C.bulletin(81.6, cy1, FLOOR + 1.2, 0.0, 1.6, 1.0, "CLUBS", seed=5 + s)
    C.poster(45.2, cy1, FLOOR + 1.7, 0.0, 1.0, 1.4, "M_IntPoster2", "DUEL!")
    for x in (44.2, 57.4, 71.0, 80.5):
        C.prop("SM_Int_Bench", x, cy0 + 0.35, FLOOR, 180.0)
    for x in (38.6, 87.4):
        C.prop("SM_Int_PottedPlantB", x, cy0 + 0.5, FLOOR, 0.0)
    C.prop("SM_Int_Extinguisher", 67.6, cy1 - 0.2, FLOOR, 0.0)
    C.prop("SM_Int_WallClock", 64.0, cy1, FLOOR + 3.2, 0.0)
    C.wtext(f"{side} WING - LECTURE HALLS", 38.0, 4.7, FLOOR + 3.3, 90.0, 0.3, (0.1, 0.2, 0.55))
    C.plate(38.0, 4.7, FLOOR + 2.8, 90.0, "<- GRAND DUEL ARENA", w=2.4, h=0.3)
    _plate_door(C, 42.5, cy1, 0.0, "DUELIST WAITING ROOM")
    for (x0, x1), xs in hall_doors.items():
        for x in xs:
            _plate_door(C, x, cy1, 0.0, "LECTURE HALL " + ("A" if x0 == HALL_A[0] else "B"))
    for x, yy, d in ((52.0, 4.2, "slifer"), (70.5, 5.6, "ra"), (79.0, 3.6, "obelisk")):
        C.npc(x, yy, 90.0, d, 3.0)
    C.cam(f"wing{side[0]}_corridor", (38.6, 2.9, FLOOR + 1.75), (70.0, 6.0, FLOOR + 1.0), 18)
    _duelist_room(C, side)
    _lecture_hall(C, HALL_A, f"LECTURE HALL {side[0]}-A", hall_doors[HALL_A], side, 0)
    _lecture_hall(C, HALL_B, f"LECTURE HALL {side[0]}-B", hall_doors[HALL_B], side, 1)
    # hall partitions and the lining against the end pavilion
    C.wall((HALL_B[0], HALL_Y[0]), (HALL_B[0], HALL_Y[1]), FLOOR, W_CEIL - FLOOR, 0.3, IN_WALL, inner=IN_WALL,
           base=BLUE_T)
    C.box(87.85, HALL_Y[0], FLOOR, 88.0, HALL_Y[1], W_CEIL, IN_WALL)


def _duelist_room(C, side):
    x0, x1 = DR_X
    y0, y1 = HALL_Y
    zc = 7.0
    C.wall((37.27, y1), (37.27, y0), FLOOR, W_CEIL - FLOOR, 0.5, IN_WALL, inner=IN_WALL,
           ops=[K.Door(y1 - DC[1], DUEL_W, DUEL_H, None, trim_in=K.TRIM_GOLD)], base=BLUE_T)
    C.door((37.27 + DIN) / 2 + 0.25, DC[1], FLOOR, -90.0, DUEL_W, DUEL_H, "academy", double=True)
    C.wall((x1 + 0.3, y0), (x1 + 0.3, y1), FLOOR, W_CEIL - FLOOR, 0.3, IN_WALL, inner=IN_WALL, base=BLUE_T)
    C.box(x0, y0, zc, x1, y1, zc + 0.2, IN_WALL, mats={"-z": K.CEIL})
    C.floor(x0, y0, x1, y1, "M_IntTileBlue")
    C.rug(40.3, 9.0, 46.6, 26.4, NAVY_T, K.TRIM_GOLD)
    C.wainscot((x0, y1), (x0, y0), FLOOR, 1.0, BLUE_T, gaps=[(y1 - 17.4, y1 - 12.6)])
    C.wainscot((x1, y0), (x1, y1), FLOOR, 1.0, BLUE_T)
    # gate sign + light strip over the duelist gate
    C.plate(x0 + 0.01, DC[1], FLOOR + 4.75, 90.0, f"{side} GATE  -  GRAND DUEL ARENA", w=3.6, h=0.32,
            mat=NAVY_T)
    C.box(x0, DC[1] - 2.4, FLOOR + 4.55, x0 + 0.05, DC[1] + 2.4, FLOOR + 4.6, "M_DuelFieldGlow", nc=True)
    # lockers + benches
    C.lockers(x1 - 0.24, 11.6, -90.0, 10)
    C.lockers(x1 - 0.24, 21.8, -90.0, 10)
    for y in (11.6, 21.8):
        C.prop("SM_Int_Bench", 45.2, y, FLOOR, 90.0)
    # deck-check table with duel disks and cards
    dining(C, 41.6, 21.6, 90.0, chairs=4, length=1.4, side=0.75)
    card_fan(C, 41.6, 21.4, FLOOR + 0.79, 6)
    duel_disk(C, 41.5, 22.2, FLOOR + 0.78, 30.0)
    # duel disk rack on the west wall
    for z in (FLOOR + 1.3, FLOOR + 1.9):
        C.box(x0, 23.0, z - 0.03, x0 + 0.42, 26.6, z, "M_IntWood", nc=True)
        for k in range(3):
            duel_disk(C, x0 + 0.22, 23.6 + k * 1.2, z, 90.0)
    C.plate(x0 + 0.01, 24.8, FLOOR + 2.45, 90.0, "LOANER DUEL DISKS", w=1.9, h=0.22)
    # live feed monitor on the corridor wall, sofa corner under the windows
    C.box(44.0, y0, FLOOR + 1.9, 47.2, y0 + 0.08, FLOOR + 3.7, "M_IntBlack", nc=True)
    C.box(44.1, y0 + 0.08, FLOOR + 2.0, 47.1, y0 + 0.1, FLOOR + 3.6, "M_IntScreen", nc=True)
    C.wtext("LIVE  -  ARENA", 45.6, y0 + 0.1, FLOOR + 3.1, 180.0, 0.24, (1, 1, 1), emissive=True)
    sofa_corner(C, 42.2, y1 - 0.55, 0.0)
    C.prop("SM_VendingMachine", x0 + 0.5, 8.9, FLOOR, 90.0)
    C.prop("SM_Int_PottedPlantB", x1 - 0.5, y1 - 0.5, FLOOR, 0.0)
    C.prop("SM_Int_PottedPlant", x0 + 0.5, 18.3, FLOOR, 0.0)
    C.poster(x1, 16.7, FLOOR + 2.3, -90.0, 1.0, 1.4, "M_IntPoster1", "WIN WITH HONOR", size=0.1)
    for y in (12.0, 22.0):
        C.panel(42.6, y, zc, 1.4, 0.4, intensity=3500, radius=10)
    C.npc(44.5, 16.5, -90.0, "obelisk" if side == "EAST" else "slifer", 2.0)
    C.cam(f"wing{side[0]}_duelist_room", (46.8, 26.8, FLOOR + 1.8), (38.0, 13.0, FLOOR + 1.6), 16)


def _lecture_hall(C, xr, title, doors, side, idx):
    x0, x1 = xr
    y0, y1 = HALL_Y
    xc = (x0 + x1) / 2
    zc = W_CEIL
    C.floor(x0, y0, x1, y1, "M_IntWoodFloor")
    # stage: dais, lectern, teacher's desk, blackboard and the big screen
    C.box(xc - 3.2, y0, FLOOR, xc + 3.2, 9.3, FLOOR + 0.2, "M_IntWood", mats={"+z": BLUE_T})
    C.box(xc - 3.2, 9.3, FLOOR + 0.17, xc + 3.2, 9.36, FLOOR + 0.2, K.TRIM_GOLD)
    C.box(xc + 1.6, 8.25, FLOOR + 0.2, xc + 2.3, 8.75, FLOOR + 1.25, "M_IntWoodDark", mats={"+y": BLUE_T})
    C.box(xc + 1.55, 8.2, FLOOR + 1.25, xc + 2.35, 8.8, FLOOR + 1.3, K.TRIM_GOLD)
    C.prop("SM_Int_OfficeDesk", xc - 1.2, 8.5, FLOOR + 0.2, 0.0)
    C.prop("SM_Int_OfficeChair", xc - 1.2, 7.85, FLOOR + 0.2, 180.0)
    C.prop("SM_Int_Books", xc - 1.5, 8.5, FLOOR + 0.96, 0.0)
    lines = ([title, "DUEL THEORY 101", "ATK 2400 vs DEF 2100 -> destroyed!", "Tribute: Lv 5-6 = 1  /  Lv 7+ = 2",
              "Traps: set first - activate later!"] if idx == 0 else
             [title, "MONSTER TYPES & ATTRIBUTES", "LIGHT / DARK / EARTH / WATER / FIRE / WIND",
              "Fusion = Polymerization + materials", "Homework: build a 40 card deck"])
    C.blackboard(xc, y0, FLOOR + 1.0, 180.0, 9.0, 1.5, lines, size=0.15)
    C.box(xc - 3.6, y0, FLOOR + 3.2, xc + 3.6, y0 + 0.08, FLOOR + 6.9, "M_IntBlack", nc=True)
    C.box(xc - 3.45, y0 + 0.08, FLOOR + 3.35, xc + 3.45, y0 + 0.1, FLOOR + 6.75, "M_IntScreen", nc=True)
    C.wtext("DUEL ACADEMY", xc, y0 + 0.1, FLOOR + 5.4, 180.0, 0.55, (1, 1, 1), emissive=True)
    C.wtext(title, xc, y0 + 0.1, FLOOR + 4.5, 180.0, 0.3, (1.0, 0.9, 0.5), emissive=True)
    roundel(C.nc, C.P(xc, y0 + 0.02, FLOOR + 7.6), C.F.yaw(180.0), 0.55, "M_AcademyYellow")
    # the GX tiers
    lecture_tiers(C, (xc, 9.6), (x0, y0, x1, y1), FLOOR, 4.5, 9, 1.25, 0.4, (45.0, 90.0, 135.0))
    # side walls: wainscot, dorm banners, clock; ceiling beams and lights
    C.wainscot((x0, y1), (x0, y0), FLOOR, 1.0, BLUE_T)
    C.wainscot((x1, y0), (x1, y1), FLOOR, 1.0, BLUE_T)
    cols = ("M_AcademyRed", "M_AcademyYellow", "M_AcademyBlue")
    for k, y in enumerate((15.5, 21.5)):
        banner(C.nc, C.P(x0 + 0.08, y, zc - 0.4), C.F.yaw(90.0), 1.8, 3.6, cols[(k + idx) % 3])
        banner(C.nc, C.P(x1 - 0.08, y, zc - 0.4), C.F.yaw(-90.0), 1.8, 3.6, cols[(k + idx + 1) % 3])
    C.prop("SM_Int_WallClock", x0 + 0.03, 10.4, FLOOR + 3.4, 90.0)
    for bx in (xc - 5.0, xc + 5.0):
        C.box(bx - 0.25, y0, zc - 0.45, bx + 0.25, y1, zc, BLUE_T, nc=True)
    for by in (13.5, 20.5):
        C.box(x0, by - 0.2, zc - 0.35, x1, by + 0.2, zc, BLUE_T, nc=True)
    for px in (xc - 7.5, xc - 2.5, xc + 2.5, xc + 7.5):
        for py in (10.5, 17.0, 24.0):
            C.panel(px, py, zc, 1.4, 0.45, light=abs(px - xc) < 3, intensity=7000, radius=15)
    # a few students on the tiers
    dorms = ("slifer", "ra", "obelisk")
    for k, (a, r) in enumerate(((70.0, 7.05), (112.0, 9.55), (30.0, 12.05), (150.0, 8.3))):
        px, py = polar(r, a, (xc, 9.6))
        if x0 + 0.5 < px < x1 - 0.5:
            C.npc(px, py, a - 90.0, dorms[(k + idx) % 3], 0.5, z=FLOOR + 0.4 * (int((r - 4.5) / 1.25) + 1))
    C.npc(xc, 8.2, 0.0, "white", 1.0, z=FLOOR + 0.2)
    lbl = f"wing{side[0]}_hall{'AB'[idx]}"
    C.cam(lbl, (xc + 7.0, y1 - 1.0, FLOOR + 3.6 + 1.7), (xc - 1.0, y0, FLOOR + 2.4), 16)
    C.cam(lbl + "_tiers", (xc - 2.0, y0 + 0.6, FLOOR + 1.9), (xc + 1.5, y1, FLOOR + 3.5), 16)


# ---------------------------------------------------------------------------- interiors: end pavilions
# room rectangles (east coords, inside faces); partitions are 0.25 m
EB_W = {"W1": (-39.5, -25.825), "W2": (-25.575, -12.425), "W3": (-12.175, 2.15), "W4": (2.4, 7.0),
        "W5": (7.25, 28.0), "W6": (28.25, 49.5)}
EB_E = {"E1": (-39.5, -8.7), "E2": (-8.45, 11.66), "E3": (11.91, 28.63), "E4": (28.88, 49.5)}
# corridor doors: y -> (width, height, style, double, sign)
EB_DOORS_W = [(-28.0, "classroom"), (-37.4, "classroom"), (-5.0, "office"), (10.5, "office"), (25.4, "office"),
              (31.6, "classroom")]
EB_DOORS_E = [(-24.0, "academy_wood"), (1.6, "classroom"), (14.4, "classroom"), (26.4, "classroom"),
              (39.0, "academy_wood")]


def _end_block_interior(C, s):
    side = "EAST" if s > 0 else "WEST"
    z, h = FLOOR, EB_TOP - FLOOR
    cx0, cx1 = EB_CX
    kw = dict(base=BLUE_T, trim=K.TRIM_WOOD, trim_in=K.TRIM_WOOD)

    def D(y, style, c):
        wide = style == "academy_wood"
        return K.Door(c, 1.8 if wide else 1.0, 2.4 if wide else 2.2, style, double=wide)
    opsw = [D(y, st, y + 39.5) for y, st in EB_DOORS_W]
    opsw += [K.Door(-19.0 + 39.5, 2.4, 2.6, "glass", double=True, trim=K.TRIM_GOLD, trim_in=K.TRIM_GOLD),
             K.Door(4.7 + 39.5, 3.6, 3.0, None, trim=K.TRIM_GOLD, trim_in=K.TRIM_GOLD)]
    C.wall((cx0, -39.5), (cx0, 49.5), z, h, 0.25, IN_WALL, inner=IN_WALL, ops=opsw, **kw)
    C.wall((cx1, 49.5), (cx1, -39.5), z, h, 0.25, IN_WALL, inner=IN_WALL,
           ops=[D(y, st, 49.5 - y) for y, st in EB_DOORS_E], **kw)
    for (ya, yb) in ((-25.825, -25.575), (-12.425, -12.175), (2.15, 2.4), (7.0, 7.25), (28.0, 28.25)):
        C.box(EB_WX[0], ya, z, EB_WX[1], yb, EB_TOP, IN_WALL)
    for (ya, yb) in ((-8.7, -8.45), (11.66, 11.91), (28.63, 28.88)):
        C.box(EB_EX[0], ya, z, EB_EX[1], yb, EB_TOP, IN_WALL)
    # ---------------- corridor (tower to tower)
    gaps_w = [(y + 39.5 - 0.62, y + 39.5 + 0.62) for y, _ in EB_DOORS_W] + [(20.5 - 1.3, 20.5 + 1.3),
                                                                              (44.2 - 1.9, 44.2 + 1.9)]
    C.wainscot((cx0, 49.5), (cx0, -39.5), z, 0.9, BLUE_T,
               gaps=[(89.0 - b, 89.0 - a) for a, b in gaps_w])
    C.wainscot((cx1, -39.5), (cx1, 49.5), z, 0.9, BLUE_T,
               gaps=[(y + 39.5 - 1.02, y + 39.5 + 1.02) for y, _ in EB_DOORS_E])
    C.rug(100.0, -38.2, 102.0, 48.2, BLUE_T, K.TRIM_GOLD)
    for y in range(-36, 48, 6):
        C.panel(101.0, y, EB_TOP, 1.2, 0.35, light=(y + 36) % 12 == 0, intensity=3500, radius=10)
    # corridor dressing between the doors
    C.lockers(cx0 + 0.24, -9.0, 90.0, 9)
    C.lockers(cx1 - 0.24, -15.5, -90.0, 12)
    C.lockers(cx1 - 0.24, 33.0, -90.0, 8)
    C.bulletin(cx0, 17.0, z + 1.1, 90.0, 2.0, 1.0, "STUDENT COUNCIL NEWS", seed=11 + s)
    C.bulletin(cx1, 7.0, z + 1.1, -90.0, 2.0, 1.0, "EXAM SCHEDULE", seed=13 + s)
    C.bulletin(cx1, 44.5, z + 1.1, -90.0, 1.6, 1.0, "DUEL RANKINGS", seed=17 + s)
    C.poster(cx0, 38.5, z + 1.6, 90.0, 0.9, 1.2, "M_IntPoster3", "SPRING FESTIVAL", (0.3, 0.1, 0.0), 0.08)
    C.poster(cx0, -32.5, z + 1.6, 90.0, 0.9, 1.2, "M_IntPoster4", "DUEL CLUB", size=0.1)
    for y in (-32.0, 21.0, 46.0):
        C.prop("SM_Int_Bench", cx1 - 0.3, y, z, -90.0)
    for y in (-38.9, 48.9):
        for x in (cx0 + 0.45, cx1 - 0.45):
            C.prop("SM_Int_PottedPlantB", x, y, z, 0.0)
    C.prop("SM_Int_Extinguisher", cx0 + 0.2, 0.6, z, 0.0)
    C.prop("SM_Int_WallClock", cx1 - 0.03, -2.0, z + 2.9, -90.0)
    C.wtext(f"{side} PAVILION", cx1, -24.0 - 2.4, z + 3.4, -90.0, 0.26, (0.1, 0.2, 0.55))
    for y, d in ((-30.0, "ra"), (5.0, "slifer"), (36.0, "obelisk")):
        C.npc(101.0, y, 0.0, d, 6.0)
    C.cam(f"pav{side[0]}_corridor", (101.0, -38.8, z + 1.75), (101.0, 20.0, z + 1.2), 18)
    # door signs
    names_w = {"W1": "CLASSROOM 1-A" if s > 0 else "CLASSROOM 2-A",
               "W3": "INFIRMARY" if s > 0 else "STUDENT COUNCIL",
               "W5": "STAFF ROOM" if s > 0 else "CAFETERIA",
               "W6": "ALCHEMY LAB" if s > 0 else "DUEL PRACTICE"}
    names_e = {"E1": "LIBRARY" if s > 0 else "HALL OF LEGENDS", "E2": "MUSIC ROOM" if s > 0 else "COMPUTER ROOM",
               "E3": "CLASSROOM 1-B" if s > 0 else "CLASSROOM 2-B",
               "E4": "STUDENT LOUNGE" if s > 0 else "DUEL CLUB"}
    for y, n in ((-28.0, "W1"), (-5.0, "W3"), (10.5, "W5"), (31.6, "W6")):
        _plate_door(C, cx0, y, 90.0, names_w[n])
    for y, n in ((-24.0, "E1"), (1.6, "E2"), (14.4, "E3"), (39.0, "E4")):
        _plate_door(C, cx1, y, -90.0, names_e[n], z=z + 2.75 if n in ("E1", "E4") else z + 2.55)
    _plate_door(C, cx0, -19.0, 90.0, "ENTRANCE", z=z + 2.95)
    _plate_door(C, cx0, 4.7, 90.0, f"{side} WING", z=z + 3.4)
    # ---------------- rooms
    W, E = EB_W, EB_E
    Cw1 = C.sub((EB_WX[0] + EB_WX[1]) / 2, (W["W1"][0] + W["W1"][1]) / 2, 180.0)
    room_classroom(Cw1, EB_WX[1] - EB_WX[0], W["W1"][1] - W["W1"][0], names_w["W1"],
                   f"pav{side[0]}_classroom_a", s, back_window=(EB_WX[0] + EB_WX[1]) / 2 - 91.0)
    Ce3 = C.sub((EB_EX[0] + EB_EX[1]) / 2, (E["E3"][0] + E["E3"][1]) / 2, 0.0)
    room_classroom(Ce3, EB_EX[1] - EB_EX[0], E["E3"][1] - E["E3"][0], names_e["E3"],
                   f"pav{side[0]}_classroom_b", -s)
    room_genkan(C, side)
    room_link(C, side)
    if s > 0:
        room_infirmary(C)
        room_staff(C)
        room_alchemy(C)
        room_library(C)
        room_music(C)
        room_lounge(C, "STUDENT LOUNGE", "pavE_lounge")
    else:
        room_council(C)
        room_cafeteria(C)
        room_practice(C)
        room_legends(C)
        room_computers(C)
        room_lounge(C, "DUEL CLUB", "pavW_club")


def room_classroom(C, w, d, name, cam, seed, back_window=None):
    """Ordinary classroom in a frame centred on the room: blackboard on local -y, windows on +x, corridor
    doors on -x (one near the front, one near the back)."""
    hw, hd = w / 2, d / 2
    z = FLOOR
    C.floor(-hw, -hd, hw, hd, "M_IntWoodFloor", planks=True, along="y")
    C.box(-2.8, -hd, z, 2.8, -hd + 1.3, z + 0.18, "M_IntWood", mats={"+z": "M_IntWoodFloor"})
    lines = [name, "Card effects resolve LAST IN, FIRST OUT", "Chain Link 1 -> 2 -> 3 ... resolve 3 -> 2 -> 1",
             "Quiz on Friday!"]
    C.blackboard(0.0, -hd, z + 0.95, 180.0, min(5.0, w - 3.4), 1.25, lines, size=0.12)
    C.prop("SM_Int_OfficeDesk", 0.0, -hd + 0.75, z + 0.18, 0.0)
    C.prop("SM_Int_Books", -0.3, -hd + 0.75, z + 0.94, 0.0)
    C.prop("SM_Int_WallClock", 0.0, -hd + 0.03, z + 3.0, 180.0)
    C.prop("SM_Int_Chalkboard", hw - 0.7, -hd + 1.0, z, -30.0)
    cols = 5
    xs = [-hw + 1.9 + i * (w - 3.0) / (cols - 1) for i in range(cols)]
    nrow = max(3, min(8, int((d - 5.2) / 1.25) + 1))
    for j in range(nrow):
        y = -hd + 3.0 + j * 1.25
        for x in xs:
            C.prop("SM_Int_SchoolDesk", x, y, z, 180.0)
            C.prop("SM_Int_SchoolChair", x, y + 0.48, z, 0.0)
    lx1 = hw if back_window is None else back_window - 1.0
    n = int((lx1 - (-hw + 1.4)) / 0.4)
    C.lockers(-hw + 1.4 + n * 0.2, hd - 0.24, 0.0, n)
    C.bulletin(-1.6, hd, z + 2.25, 0.0, 2.6, 0.9, "CLASS NEWS", seed=21 + seed)
    C.poster(-hw, -hd + 2.6, z + 1.7, 90.0, 0.7, 1.0, "M_IntPoster2", "RULES", size=0.09)
    C.wainscot((hw, -hd), (hw, hd), z, 0.85, BLUE_T)
    for px in (-hw / 2, hw / 2):
        for py in (-hd / 2, hd / 2):
            C.panel(px, py, EB_TOP, 1.2, 0.4, intensity=3000, radius=9)
    C.npc(xs[1], -hd + 3.0 + 0.48, 0.0, "slifer", 0.3)
    C.npc(xs[3], -hd + 3.0 + 1.25 * 2 + 0.48, 0.0, "ra", 0.3)
    C.npc(1.4, -hd + 1.0, 180.0, "white", 1.0, z=z + 0.18)
    C.cam(cam, (hw - 0.7, hd - 0.9, z + 1.8), (-0.8, -hd, z + 1.1), 17)


def _shoe_rack(C, x0, x1, y, face, h=1.8, d=0.4):
    """Getabako (shoe lockers) along local x; back on y, cubbies facing +y (face=1) or -y (face=-1)."""
    ya, yb = sorted((y, y + face * d))
    yf = y + face * d
    C.box(x0, ya, FLOOR, x1, yb, FLOOR + h, "M_IntWood")
    n = int((x1 - x0) / 0.32)
    for i in range(1, n):
        x = x0 + (x1 - x0) * i / n
        C.box(x - 0.01, min(yf, yf + face * 0.01), FLOOR + 0.1, x + 0.01, max(yf, yf + face * 0.01), FLOOR + h - 0.05,
              "M_IntWoodDark", nc=True)
    for k in range(1, 6):
        zz = FLOOR + 0.1 + (h - 0.15) * k / 6
        C.box(x0, min(yf, yf + face * 0.012), zz - 0.012, x1, max(yf, yf + face * 0.012), zz + 0.012,
              "M_IntWoodDark", nc=True)


def room_genkan(C, side):
    x0, x1 = EB_WX
    y0, y1 = EB_W["W2"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, K.TILE)
    C.rug(90.0, -20.6, 92.2, -17.4, "M_IntWoodDark")
    for k in range(10):         # sunoko duck-board
        C.box(90.15 + k * 0.2, -20.4, z + 0.02, 90.28 + k * 0.2, -17.6, z + 0.06, "M_IntWood", nc=True)
    _shoe_rack(C, 90.6, 97.6, y0, 1)
    _shoe_rack(C, 90.6, 97.6, y1, -1)
    for y in (-22.9, -15.1):
        C.prop("SM_Int_Bench", 94.0, y, z, 0.0 if y > -19 else 180.0)
    C.prop("SM_Int_Bucket", 89.1, -23.2, z, 0.0)
    C.prop("SM_Int_PottedPlantB", 89.0, -13.0, z, 0.0)
    C.prop("SM_Int_PottedPlantB", 98.2, -25.0, z, 0.0)
    C.prop("SM_Int_WetFloor", 91.4, -20.8, z, 60.0)
    C.plate(94.1, y1, z + 2.35, 0.0, "PLEASE CHANGE INTO YOUR INDOOR SHOES!", w=3.6, h=0.24)
    C.bulletin(94.1, y0, z + 2.1, 180.0, 2.4, 0.9, "LOST & FOUND", seed=31)
    C.wtext(f"DUEL ACADEMY - {side} PAVILION", 98.75, -19.0, z + 3.35, -90.0, 0.24, (0.1, 0.2, 0.55))
    for x in (91.5, 96.0):
        K.pendant(C.a, *C.F.p(x, -19.0), EB_TOP, "lamp")
    C.npc(93.0, -18.0, 90.0, "ra", 2.0)
    C.cam(f"pav{side[0]}_entrance", (98.3, -13.0, z + 1.75), (88.5, -21.0, z + 1.4), 17)


def room_link(C, side):
    """Short gallery between the end pavilion corridor and the wing corridor."""
    y0, y1 = EB_W["W4"]
    z = FLOOR
    C.rug(89.8, 3.9, 98.4, 5.5, BLUE_T, K.TRIM_GOLD)
    C.wainscot((EB_WX[0], y0), (EB_WX[1], y0), z, 0.9, BLUE_T)
    C.wainscot((EB_WX[1], y1), (EB_WX[0], y1), z, 0.9, BLUE_T)
    for x in (91.0, 96.0):
        C.prop("SM_Int_Painting", x, y1 - 0.03, z + 1.5, 0.0)
        C.prop("SM_Int_Frame", x, y0 + 0.03, z + 1.6, 180.0)
    C.panel(93.6, 4.7, EB_TOP, 1.2, 0.35, intensity=3000, radius=9)


def room_infirmary(C):
    x0, x1 = EB_WX
    y0, y1 = EB_W["W3"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, "M_IntLinoleum")
    C.wainscot((x1, y0), (x1, y1), z, 1.0, "M_IntPlasterMint", K.TRIM_WHITE, gaps=[(-5.0 - y0 - 0.62, -5.0 - y0 + 0.62)])
    C.wainscot((x1, y1), (x0, y1), z, 1.0, "M_IntPlasterMint", K.TRIM_WHITE)
    # three beds with curtain rails
    for k, x in enumerate((90.0, 92.7, 95.4)):
        C.kit(K.single_bed, x, y1 - 1.1, -90.0, blanket="M_IntFabricWhite" if k != 1 else "M_IntFabricBlue",
              frame=K.METAL)
        C.prop("SM_Int_NightstandB", x + 0.85, y1 - 0.35, z, 0.0)
    for x in (91.35, 94.05, 96.75):     # curtain dividers on ceiling rails
        C.box(x - 0.015, y1 - 2.3, z + 0.3, x + 0.015, y1, z + 2.4, "M_IntFabricWhite", nc=True)
        C.box(x - 0.02, y1 - 2.35, z + 2.4, x + 0.02, y1, z + 2.45, K.METAL, nc=True)
        C.box(x - 0.01, y1 - 2.33, z + 2.45, x + 0.01, y1 - 2.31, z + 4.4, K.METAL, nc=True)
    C.box(96.75, y1 - 2.35, z + 2.4, 98.0, y1 - 2.3, z + 2.45, K.METAL, nc=True)
    C.box(96.8, y1 - 2.33, z + 0.3, 97.9, y1 - 2.31, z + 2.4, "M_IntFabricWhite", nc=True)
    # nurse's desk, cabinets, sink, screen
    C.prop("SM_Int_OfficeDesk", 96.7, -10.0, z, 90.0)
    C.prop("SM_Int_OfficeChair", 97.6, -10.0, z, -90.0)
    C.prop("SM_Int_DeskLamp", 96.6, -10.5, z + 0.76, 0.0)
    for x in (91.4, 92.4):
        C.prop("SM_Int_Cabinet", x, y0 + 0.25, z, 180.0)
    C.box(89.1, y0, z, 90.6, y0 + 0.6, z + 0.9, K.TRIM_WHITE, mats={"+z": K.METAL})
    C.box(89.4, y0 + 0.1, z + 0.86, 90.3, y0 + 0.5, z + 0.92, "M_IntSteelBlue", nc=True)
    C.prop("SM_Int_Mirror", 89.85, y0 + 0.03, z + 1.25, 180.0)
    C.prop("SM_Int_FoldingScreen", 93.6, -6.3, z, 90.0)
    C.prop("SM_Int_Ottoman", 92.0, -8.0, z, 0.0)
    C.prop("SM_Int_PottedPlantB", 98.2, y1 - 0.5, z, 0.0)
    C.poster(x1, -8.8, z + 1.6, -90.0, 0.8, 1.1, K.TRIM_WHITE, "E  F P  T O Z", (0.1, 0.1, 0.1), 0.08)
    C.poster(x1, 0.4, z + 1.6, -90.0, 0.8, 1.1, "M_IntPoster2", "WASH YOUR HANDS!", size=0.07)
    C.poster(93.5, y0, z + 1.9, 180.0, 1.3, 0.8, "M_IntPoster1", "GET WELL SOON, DUELISTS!", size=0.07)
    for py in (-8.0, -1.5):
        C.panel(93.6, py, EB_TOP, 1.4, 0.4, intensity=3000, radius=9)
    C.npc(96.0, -9.6, 0.0, "white", 1.5)
    C.cam("pavE_infirmary", (98.2, -11.6, z + 1.8), (90.0, 1.2, z + 0.8), 17)


def room_staff(C):
    x0, x1 = EB_WX
    y0, y1 = EB_W["W5"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, "M_IntCarpetBlue")
    for yc in (14.0, 21.4):
        for k in range(3):
            y = yc - 1.45 + k * 1.45
            C.prop("SM_Int_OfficeDesk", 93.0, y, z, -90.0)
            C.prop("SM_Int_OfficeDesk", 94.4, y, z, 90.0)
            C.prop("SM_Int_OfficeChair", 92.1, y, z, 90.0)
            C.prop("SM_Int_OfficeChair", 95.3, y, z, -90.0)
            C.prop("SM_Int_Books", 93.2, y + 0.3, z + 0.76, 90.0)
        C.prop("SM_Int_DeskLamp", 94.3, yc + 1.2, z + 0.76, 0.0)
    C.prop("SM_Int_OfficeDesk", 93.7, 9.0, z, 0.0)
    C.prop("SM_Int_OfficeChair", 93.7, 8.35, z, 180.0)
    for k in range(18):
        C.prop("SM_Int_Bookshelf" if k < 9 else "SM_Int_Cabinet", x0 + 0.22, 8.4 + k * 1.05, z, 90.0)
    C.box(90.6, y1 - 0.06, z + 1.0, 96.4, y1, z + 2.3, K.TRIM_WHITE, nc=True)
    C.box(90.5, y1 - 0.05, z + 0.97, 96.5, y1 - 0.01, z + 2.33, K.METAL, nc=True)
    for i, t in enumerate(("STAFF SCHEDULE", "Mon: Duel Theory / Alchemy", "Tue: Card History / P.E.",
                           "Wed: School-wide duel tournament!", "Thu: Field trip - volcano (be careful)")):
        C.wtext(t, 93.5, y1 - 0.06, z + 2.1 - i * 0.24, 0.0, 0.11 if i else 0.16, (0.1, 0.15, 0.4))
    C.box(97.4, y1 - 0.6, z, 98.7, y1 - 0.01, z + 0.9, "M_IntWood", mats={"+z": K.TRIM_WHITE})
    C.prop("SM_Int_Kettle", 97.7, y1 - 0.3, z + 0.9, 0.0)
    C.prop("SM_Int_TeaSet", 98.2, y1 - 0.3, z + 0.9, 0.0)
    C.box(97.6, 16.8, z, 98.6, 17.8, z + 1.15, K.TRIM_WHITE, mats={"+z": "M_IntSteelBlue"})    # copier
    C.prop("SM_Int_PottedPlantB", 98.1, 7.9, z, 0.0)
    C.prop("SM_Int_WallClock", 93.6, y0 + 0.03, z + 2.9, 180.0)
    for py in (11.0, 17.7, 24.4):
        C.panel(93.6, py, EB_TOP, 1.4, 0.4, intensity=3200, radius=9)
    C.npc(92.1, 14.0, 90.0, "white", 0.5)
    C.npc(95.3, 21.4, -90.0, "white", 0.5)
    C.cam("pavE_staff_room", (98.1, 27.4, z + 1.8), (90.5, 9.0, z + 0.9), 17)


def _flask(C, x, y, z, mat="M_IntFlaskGlow"):
    C.nc.lathe([(0.06, 0.0), (0.06, 0.06), (0.02, 0.14), (0.02, 0.2)], "M_IntGlassClear", seg=8,
               center=C.P(x, y, z))
    C.nc.cylinder(C.P(x, y, z + 0.005), 0.052, 0.05, mat, seg=8)


def room_alchemy(C):
    x0, x1 = EB_WX
    y0, y1 = EB_W["W6"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, "M_IntTileBlue")
    for yc in (33.4, 37.6, 41.8):
        C.box(91.2, yc - 0.55, z, 96.2, yc + 0.55, z + 0.9, "M_IntWood", mats={"+z": "M_IntBlack"})
        for k, x in enumerate((91.8, 93.0, 94.4, 95.6)):
            _flask(C, x, yc + (0.2 if k % 2 else -0.15), z + 0.9,
                   ("M_IntFlaskGlow", "M_IntFabricPurple", "M_IntFabricOrange", "M_IntScreen")[k])
            for sy in (-1, 1):
                C.prop("SM_Int_Stool", x, yc + sy * 0.95, z, 0.0)
    # teacher's bench with the bubbling cauldron, blackboard on the north wall
    C.box(92.6, 45.6, z, 97.4, 46.6, z + 0.9, "M_IntWoodDark", mats={"+z": "M_IntBlack"})
    C.mb.lathe([(0.3, 0.0), (0.45, 0.12), (0.5, 0.4), (0.42, 0.62)], "M_IntBlack", seg=14,
               center=C.P(96.0, 47.6, z), cap_top=False)
    C.nc.cylinder(C.P(96.0, 47.6, z + 0.52), 0.42, 0.02, "M_IntFlaskGlow", seg=14)
    C.light(96.0, 47.6, z + 1.0, 1200.0, 4.0, (0.5, 1.0, 0.6))
    C.blackboard(95.6, y1, z + 1.0, 0.0, 4.4, 1.3,
                 ["ALCHEMY  -  Prof. Banner", "Fusion = Polymerization + 2 materials",
                  "Fe + S -> FeS   (do NOT eat it)", "Homework: p. 42 - 48"], size=0.12)
    for k in range(6):
        C.prop("SM_Int_Shelves", x1 - 0.18, 34.4 + k * 1.0 if k < 3 else 35.0 + k * 1.0 + 2.6, z, -90.0)
    C.poster(x0, 29.2, z + 1.6, 90.0, 0.8, 1.1, "M_IntPoster4", "THE ART OF ALCHEMY", size=0.06)
    # the professor's cat on its cushion
    C.prop("SM_Int_Basket", 89.6, 47.9, z, 20.0)
    C.nc.sphere(C.P(89.6, 47.9, z + 0.28), 0.17, "M_IntFabricYellow", seg=10, rings=6, scale=(1.3, 1.0, 0.8))
    C.nc.sphere(C.P(89.82, 47.75, z + 0.42), 0.1, "M_IntFabricYellow", seg=10, rings=6)
    for px in (91.0, 94.4, 97.0):
        K.pendant(C.a, *C.F.p(px, 37.6), EB_TOP, "industrial")
    C.npc(94.9, 46.1, 0.0, "white", 1.0)
    C.npc(92.9, 36.8, 180.0, "slifer", 1.0)
    C.cam("pavE_alchemy_lab", (98.2, 29.0, z + 1.8), (91.5, 47.0, z + 1.0), 17)


def room_library(C):
    x0, x1 = EB_EX
    y0, y1 = EB_E["E1"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, "M_IntCarpetRed")
    C.rug(104.5, -21.6, 112.6, -9.6, "M_IntCarpetYellow", K.TRIM_GOLD)
    # book stacks (double sided) in the south half, wall shelves along the corridor wall
    for yc in (-37.0, -33.6, -30.2):
        for k in range(5):
            x = 105.6 + k * 1.0
            C.prop("SM_Int_Bookshelf", x, yc - 0.18, z, 0.0)
            C.prop("SM_Int_Bookshelf", x, yc + 0.18, z, 180.0)
    for y in [-38.8 + k * 1.05 for k in range(11)] + [-21.6 + k * 1.05 for k in range(12)]:
        if not (-25.4 < y < -22.6):
            C.prop("SM_Int_Bookshelf", x0 + 0.18, y, z, 90.0)
    # reading tables by the windows and in the north half
    for y in (-37.2, -33.6, -30.0):
        C.prop("SM_Int_RoundTable", 112.0, y, z, 0.0)
        C.prop("SM_Int_WoodChair", 112.0, y - 0.85, z, 180.0)
        C.prop("SM_Int_WoodChair", 112.0, y + 0.85, z, 0.0)
    for x in (107.0, 111.0):
        for y in (-19.6, -15.6, -11.6):
            dining(C, x, y, 0.0, chairs=4, length=1.2, side=0.7)
            C.prop("SM_Int_DeskLamp", x + 0.45, y + 0.15, z + 0.76, 200.0)
            C.prop("SM_Int_Books", x - 0.3, y - 0.1, z + 0.76, 15.0)
    # librarian's counter by the door
    C.box(104.6, -27.6, z, 107.6, -26.9, z + 1.05, "M_IntWoodDark", mats={"+z": "M_IntWood"})
    C.prop("SM_Int_Register", 105.2, -27.25, z + 1.05, 180.0)
    C.prop("SM_Int_Books", 106.6, -27.25, z + 1.05, 0.0)
    C.npc(106.0, -28.2, 0.0, "white", 0.5)
    C.prop("SM_Int_GrandfatherClock", 104.4, y1 - 0.2, z, 0.0)
    C.mb.cylinder(C.P(112.8, -24.0, z), 0.18, 0.9, "M_IntWoodDark", seg=8)              # globe
    C.nc.sphere(C.P(112.8, -24.0, z + 1.15), 0.28, "M_IntPoster2", seg=12, rings=8)
    C.plate(108.6, y1, z + 3.1, 0.0, "LIBRARY  -  QUIET PLEASE", w=3.2, h=0.3, mat=NAVY_T)
    for py in (-33.6, -15.6):
        K.pendant(C.a, *C.F.p(108.4, py), EB_TOP, "chandelier")
    for py in (-24.0,):
        C.panel(108.4, py, EB_TOP, 1.4, 0.4, intensity=3000, radius=10)
    C.npc(111.0, -15.0, 90.0, "obelisk", 0.5)
    C.npc(108.0, -35.3, 0.0, "ra", 1.5)
    C.cam("pavE_library", (113.0, -9.3, z + 1.9), (105.5, -30.0, z + 0.9), 17)
    C.cam("pavE_library_stacks", (110.6, -38.9, z + 1.7), (104.0, -28.0, z + 1.2), 17)


def room_music(C):
    x0, x1 = EB_EX
    y0, y1 = EB_E["E2"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, "M_IntWoodFloor", planks=True)
    cen = (111.2, 0.5)
    C.box(cen[0] - 0.6, cen[1] - 0.6, z, cen[0] + 0.6, cen[1] + 0.6, z + 0.15, "M_IntWood")      # conductor
    C.box(cen[0] - 0.4, cen[1] - 0.05, z + 0.15, cen[0] - 0.36, cen[1] + 0.05, z + 1.2, K.METAL, nc=True)
    for r, n in ((3.4, 7), (5.0, 9)):
        for i in range(n):
            a = 125.0 + 110.0 * i / (n - 1)
            px, py = polar(r, a, cen)
            C.prop("SM_Int_WoodChair", px, py, z, a - 90.0)
            if r < 4:
                mx, my = polar(r - 0.7, a, cen)
                with C.at(mx, my, z, a - 90.0):
                    C.nc.box((0, 0, 0.55), (0.02, 0.02, 1.1), K.METAL)
                    C.nc.box((0, 0, 1.12), (0.45, 0.02, 0.32), K.BLACK)
    C.kit(K.piano, 110.6, 8.4, -60.0)
    C.blackboard(107.6, y0, z + 1.0, 180.0, 4.6, 1.2,
                 ["MUSIC", "Do  Re  Mi  Fa  So  La  Ti  Do", "Academy anthem - practice for the festival!"],
                 size=0.12)
    for k, x in enumerate((105.0, 106.6, 108.2, 109.8)):
        C.prop("SM_Int_Frame", x, y1 - 0.03, z + 1.9, 0.0)
    C.prop("SM_Int_Cabinet", x0 + 0.3, -6.6, z, 90.0)
    C.prop("SM_Int_Cabinet", x0 + 0.3, -5.6, z, 90.0)
    C.prop("SM_Int_Radio", x0 + 0.35, -6.1, z + 1.8, 90.0)
    C.prop("SM_Int_PottedPlantB", 113.0, y0 + 0.5, z, 0.0)
    for py in (-4.0, 6.0):
        C.panel(108.4, py, EB_TOP, 1.4, 0.4, intensity=3000, radius=10)
    C.npc(cen[0], cen[1], 90.0, "white", 0.3, z=z + 0.15)
    C.cam("pavE_music_room", (x0 + 0.6, y1 - 0.6, z + 1.8), (112.0, -2.0, z + 1.0), 17)


def room_lounge(C, title, cam):
    x0, x1 = EB_EX
    y0, y1 = EB_E["E4"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, "M_IntWoodFloor", planks=True)
    sofa_corner(C, 109.0, y1 - 0.6, 0.0, rug="M_IntCarpetBlue")
    C.box(107.9, 44.3, z, 110.1, 44.8, z + 0.5, "M_IntWoodDark")
    C.prop("SM_Int_TV", 109.0, 44.55, z + 0.5, 180.0)
    # duel table with a play mat in the middle
    C.box(106.2, 34.4, z, 110.6, 36.6, z + 0.74, "M_IntWoodDark", mats={"+z": "M_IntDuelMat"})
    for sx in (-1, 1):
        for k in range(5):
            cxk, cyk = 108.4 + (k - 2) * 0.36, 35.5 + sx * 0.5
            C.box(cxk - 0.12, cyk - 0.16, z + 0.741, cxk + 0.12, cyk + 0.16, z + 0.745, "M_DuelFieldGlow", nc=True)
        C.prop("SM_Int_WoodChair", 108.4, 35.5 + sx * 1.6, z, 0.0 if sx > 0 else 180.0)
    card_fan(C, 108.0, 35.0, z + 0.75, 5)
    card_fan(C, 108.8, 36.0, z + 0.75, 5, 180.0)
    duel_disk(C, 107.0, 35.5, z + 0.75, 0.0)
    for y in (31.0, 32.3):
        C.prop("SM_VendingMachine", x0 + 0.5, y, z, 90.0)
    for k in range(4):
        C.prop("SM_Int_DisplayShelves", x0 + 0.2, 43.0 + k * 1.05, z, 90.0)
    for y in (39.6, 41.0):
        C.prop("SM_Int_Ottoman", 112.2, y, z, 0.0)
    C.prop("SM_Int_PottedPlantB", 113.0, y0 + 0.5, z, 0.0)
    C.poster(110.5, y0, z + 1.6, 180.0, 1.4, 1.0, "M_IntPoster1", title, size=0.12)
    C.poster(106.5, y0, z + 1.6, 180.0, 0.8, 1.1, "M_IntPoster3", "TOURNAMENT SIGN-UP", (0.2, 0.1, 0.0), 0.06)
    for py in (33.0, 42.0):
        K.pendant(C.a, *C.F.p(108.4, py), EB_TOP, "fan")
        C.panel(105.0, py, EB_TOP, 1.2, 0.35, intensity=3000, radius=10)
    C.npc(108.4, 37.1, 180.0, "slifer", 0.3)
    C.npc(108.4, 33.9, 0.0, "obelisk", 0.3)
    C.cam(cam, (x0 + 0.7, y0 + 0.6, z + 1.8), (111.0, 46.0, z + 0.7), 17)


def room_council(C):
    x0, x1 = EB_WX
    y0, y1 = EB_W["W3"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, "M_IntWoodFloorDark", planks=True)
    C.rug(90.4, -8.6, 96.4, -0.4, "M_IntCarpetRed", K.TRIM_GOLD)
    for y in (-5.8, -3.2):
        C.prop("SM_Int_Table", 93.4, y, z, 90.0)
    for y in (-6.6, -5.0, -3.4, -1.8):
        C.prop("SM_Int_DiningChair", 92.55, y + 0.4, z, 90.0)
        C.prop("SM_Int_DiningChair", 94.25, y + 0.4, z, -90.0)
    C.prop("SM_Int_OfficeChair", 93.4, -0.9, z, 0.0)
    C.prop("SM_Int_OfficeChair", 93.4, -8.1, z, 180.0)
    for y in (-6.0, -3.0):
        C.prop("SM_Int_Books", 93.4, y, z + 0.76, 90.0)
    C.mb.lathe([(0.25, 0.0), (0.25, 0.08), (0.04, 0.12), (0.04, 2.4)], K.TRIM_GOLD, seg=8,
               center=C.P(89.2, y1 - 0.5, z))
    for k, (x, col) in enumerate(((90.6, "M_AcademyRed"), (93.4, "M_AcademyYellow"), (96.2, "M_AcademyBlue"))):
        banner(C.nc, C.P(x, y1 - 0.06, z + 4.0), C.F.yaw(0.0), 1.3, 2.6, col)
    for k in range(4):
        C.prop("SM_Int_DisplayShelves", 90.6 + k * 1.05, y0 + 0.2, z, 180.0)
    for k in range(5):
        trophy(C, 90.4 + k * 0.85 + (k > 1) * 0.6, y0 + 0.2, z + 1.8, 1.0 + 0.3 * (k % 2))
    C.box(97.0, y0 + 0.4, z + 1.0, 98.7, y0 + 0.44, z + 2.2, K.TRIM_WHITE, nc=True)
    C.prop("SM_Int_PottedPlantB", 98.1, y1 - 0.5, z, 0.0)
    C.poster(x0, -3.0, z + 1.7, 90.0, 1.2, 0.8, "M_IntPoster3", "SCHOOL FESTIVAL PLAN", (0.2, 0.1, 0.0), 0.07)
    for py in (-8.0, -1.5):
        K.pendant(C.a, *C.F.p(93.4, py), EB_TOP, "chandelier")
    C.npc(93.4, -1.2, 180.0, "obelisk", 0.5)
    C.npc(92.6, -5.4, 90.0, "ra", 0.3)
    C.cam("pavW_council", (98.2, -11.6, z + 1.8), (91.0, 1.0, z + 0.9), 17)


def room_cafeteria(C):
    x0, x1 = EB_WX
    y0, y1 = EB_W["W5"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, K.TILE)
    # serving counter along the west wall with the menu board above it
    C.box(88.5, 9.0, z, 89.4, 22.0, z + 0.95, "M_IntWood", mats={"+z": K.METAL})
    C.box(89.4, 9.0, z + 0.95, 89.9, 22.0, z + 1.0, K.TRIM_WHITE)
    C.box(88.5, 9.0, z + 1.5, 88.9, 22.0, z + 1.55, K.METAL, nc=True)
    for k in range(6):
        C.nc.box(C.P(89.0, 10.5 + k * 2.0, z + 0.98), (0.45, 0.6, 0.06), K.METAL)
    C.box(88.5, 12.0, z + 2.3, 88.56, 19.0, z + 3.9, K.BLACK, nc=True)
    for i, t in enumerate(("TODAY'S MENU", "Curry rice ......... 300 DP", "Ramen ............. 250 DP",
                           "Golden egg bread .. SOLD OUT!", "Onigiri set ........ 150 DP")):
        C.wtext(t, 88.56, 15.5, z + 3.6 - i * 0.32, 90.0, 0.24 if i == 0 else 0.15,
                (1.0, 0.85, 0.35) if i == 0 else (1, 1, 1), out=0.02)
    for x in (91.6, 95.4):
        for y in (10.2, 14.4, 18.6, 22.8):
            dining(C, x, y, 90.0, chairs=6, length=1.4, side=0.7)
    for k in range(3):
        C.prop("SM_VendingMachine", 90.4 + k * 1.15, y1 - 0.5, z, 0.0)
    C.prop("SM_Int_Bucket", 89.0, 8.0, z, 0.0)
    C.prop("SM_Int_PottedPlantB", 98.1, y1 - 0.6, z, 0.0)
    C.poster(x1, 18.0, z + 1.7, -90.0, 0.9, 1.2, "M_IntPoster1", "EAT WELL, DUEL WELL!", size=0.07)
    for py in (11.0, 17.7, 24.4):
        C.panel(93.6, py, EB_TOP, 1.4, 0.4, intensity=3200, radius=9)
    C.npc(88.9, 16.0, 90.0, "white", 0.5)
    for (x, y, d) in ((91.0, 14.4, "slifer"), (95.9, 18.6, "ra"), (94.7, 10.2, "obelisk")):
        C.npc(x, y, 90.0, d, 0.5)
    C.cam("pavW_cafeteria", (98.1, 27.3, z + 1.8), (89.5, 11.0, z + 1.0), 17)


def room_practice(C):
    x0, x1 = EB_WX
    y0, y1 = EB_W["W6"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, "M_IntCarpetBlue")
    for (xc, yc) in ((91.6, 33.6), (95.6, 33.6), (91.6, 39.6), (95.6, 39.6), (93.6, 45.4)):
        C.box(xc - 0.75, yc - 1.25, z, xc + 0.75, yc + 1.25, z + 0.72, "M_IntWoodDark", mats={"+z": "M_IntDuelMat"})
        for sy in (-1, 1):
            for k in range(3):
                cx = xc + (k - 1) * 0.42
                cy = yc + sy * 0.5
                C.box(cx - 0.15, cy - 0.11, z + 0.721, cx + 0.15, cy + 0.11, z + 0.725, "M_DuelFieldGlow", nc=True)
            C.prop("SM_Int_Stool", xc, yc + sy * 1.65, z, 0.0)
        card_fan(C, xc, yc - 0.85, z + 0.73, 4, 90.0)
    C.blackboard(95.0, y1, z + 1.0, 0.0, 4.0, 1.2, ["DUEL PRACTICE", "Summon sickness? Not in this room!",
                                                     "Tournament ladder posted Friday"], size=0.12)
    for k in range(5):
        C.prop("SM_Int_SteelShelves", x1 - 0.3, 35.0 + k * 1.3, z, -90.0)
        for j in range(3):
            C.nc.box(C.P(x1 - 0.3, 35.0 + k * 1.3 - 0.35 + j * 0.35, z + 1.05), (0.2, 0.25, 0.12),
                     ("M_CardPackBlue", "M_CardPackPurple", "M_CardPack")[j])
    C.poster(x0, 29.2, z + 1.6, 90.0, 0.8, 1.1, "M_IntPoster2", "DECK RULES: 40-60", size=0.06)
    for py in (34.0, 40.0, 46.0):
        C.panel(93.6, py, EB_TOP, 1.4, 0.4, intensity=3200, radius=9)
    C.npc(91.6, 31.95, 0.0, "slifer", 0.3)
    C.npc(91.6, 35.25, 180.0, "obelisk", 0.3)
    C.npc(95.6, 41.25, 180.0, "ra", 0.3)
    C.cam("pavW_practice", (98.2, 29.0, z + 1.8), (90.5, 46.0, z + 0.8), 17)


def _vitrine(C, x, y, w=1.2, d=0.7, content="cards", seed=0):
    C.box(x - w / 2, y - d / 2, FLOOR, x + w / 2, y + d / 2, FLOOR + 0.9, "M_IntWoodDark")
    C.box(x - w / 2 + 0.03, y - d / 2 + 0.03, FLOOR + 0.9, x + w / 2 - 0.03, y + d / 2 - 0.03, FLOOR + 1.45,
          "M_IntGlassClear")
    C.box(x - w / 2, y - d / 2, FLOOR + 1.45, x + w / 2, y + d / 2, FLOOR + 1.5, K.TRIM_GOLD)
    if content == "cards":
        card_fan(C, x, y, FLOOR + 0.91, 4, (seed * 37) % 90)
    else:
        trophy(C, x, y, FLOOR + 0.9, 1.4)


def room_legends(C):
    """Hall of Legends: the academy's duel museum (west pavilion, in place of the library)."""
    x0, x1 = EB_EX
    y0, y1 = EB_E["E1"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, K.MARBLEFLOOR)
    C.rug(105.2, -38.0, 111.6, -10.2, "M_IntCarpetRed", K.TRIM_GOLD)
    # giant card replica on the south wall
    C.box(105.9, y0, z + 0.4, 111.1, y0 + 0.15, z + 3.9, K.TRIM_GOLD)
    C.box(106.1, y0 + 0.15, z + 0.6, 110.9, y0 + 0.18, z + 3.7, "M_CardPack", nc=True)
    C.box(106.4, y0 + 0.18, z + 1.7, 110.6, y0 + 0.2, z + 3.4, "M_IntPoster2", nc=True)
    C.wtext("THE LEGENDARY DRAGON", 108.5, y0 + 0.2, z + 1.2, 180.0, 0.18, (0.15, 0.1, 0.05))
    for y in (-35.0, -29.0, -23.0, -17.0, -11.0):
        _vitrine(C, 106.4, y, content="cards", seed=int(-y))
        _vitrine(C, 110.6, y, content="trophy" if int(-y) % 2 else "cards", seed=int(-y) + 1)
    for y in (-32.0, -20.0):
        plinth_bust(C, 108.5, y, 0.0)
    for k, y in enumerate((-36.5, -31.0, -18.0, -12.5)):
        C.prop("SM_Int_Painting", x0 + 0.05, y, z + 1.4, 90.0)
        C.wtext(("FIRST CHAMPION", "THE KING OF GAMES", "GX CUP WINNERS", "FOUNDER'S DUEL")[k], x0, y, z + 1.15,
                90.0, 0.08, (0.15, 0.1, 0.05))
    C.plate(108.5, y1, z + 3.1, 0.0, "HALL OF LEGENDS", w=2.8, h=0.32, mat=NAVY_T)
    for py in (-33.6, -15.6):
        K.pendant(C.a, *C.F.p(108.5, py), EB_TOP, "chandelier")
    C.panel(108.5, -24.6, EB_TOP, 1.4, 0.4, intensity=3000, radius=10)
    C.npc(108.5, -26.0, 90.0, "obelisk", 3.0)
    C.cam("pavW_hall_of_legends", (112.9, -9.4, z + 1.9), (106.5, -38.0, z + 1.6), 17)


def room_computers(C):
    x0, x1 = EB_EX
    y0, y1 = EB_E["E2"]
    z = FLOOR
    C.floor(x0, y0, x1, y1, "M_IntLinoleum")
    for y in (-5.6, -2.6, 0.4, 3.4, 6.4):
        for x in (106.2, 109.8):
            C.prop("SM_Int_OfficeDesk", x, y, z, 180.0)
            C.prop("SM_Int_OfficeChair", x, y + 0.6, z, 0.0)
            for dx in (-0.35, 0.35):
                C.nc.box(C.P(x + dx, y + 0.05, z + 0.76), (0.4, 0.38, 0.36), K.TRIM_WHITE)
                C.nc.box(C.P(x + dx, y + 0.245, z + 0.96), (0.3, 0.01, 0.22), "M_IntScreen")
    C.prop("SM_Int_ProjectorScreen", 108.0, y0 + 0.4, z, 180.0)
    for k in range(3):
        C.prop("SM_Int_SteelShelves", x0 + 0.3, -6.8 + k * 1.3, z, 90.0)
        C.nc.box(C.P(x0 + 0.3, -6.8 + k * 1.3, z + 1.0), (0.4, 0.9, 1.6), K.BLACK)
        C.nc.box(C.P(x0 + 0.51, -6.8 + k * 1.3, z + 1.5), (0.01, 0.6, 0.04), "M_DuelFieldGlow")
    C.poster(108.0, y1, z + 1.7, 0.0, 1.6, 0.9, "M_IntPoster2", "DUEL DATABASE v2", size=0.09)
    C.prop("SM_Int_PottedPlantB", 113.0, y1 - 0.5, z, 0.0)
    for py in (-4.0, 1.6, 7.2):
        C.panel(108.0, py, EB_TOP, 1.4, 0.4, intensity=3000, radius=9)
    C.npc(106.2, 1.0, 0.0, "ra", 0.2)
    C.npc(109.8, 4.0, 0.0, "slifer", 0.2)
    C.cam("pavW_computer_room", (x0 + 0.6, y1 - 0.6, z + 1.8), (112.0, -7.0, z + 0.8), 17)


# ---------------------------------------------------------------------------- interiors: rear annex
def _exec_desk(C, x, y, yaw, w=2.4, d=1.0, mat="M_IntWoodDark"):
    """Big executive desk (user side local -Y), gold trimmed."""
    with C.at(x, y, FLOOR, yaw):
        C.mb.box((0, 0, 0.76), (w, d, 0.05), "M_IntWood")
        C.mb.box((0, 0.1, 0.37), (w - 0.1, d - 0.25, 0.74), mat)
        C.nc.box((0, d / 2 - 0.12 + 0.005, 0.5), (w - 0.3, 0.01, 0.06), K.TRIM_GOLD)
        C.nc.box((0, 0.0, 0.79), (0.5, 0.35, 0.01), "M_IntPaper")


def _gear(C, x, y, z, r=0.45, mat=K.TRIM_GOLD):
    """'Ancient gear' model on a stand (vertical, facing local -Y)."""
    with C.mb.at(C.P(x, y, z), rot=C.F.yaw(0.0), rot_x=90.0):
        C.mb.cylinder((0, 0, -0.05), r, 0.1, mat, seg=16)
        C.mb.cylinder((0, 0, -0.07), r * 0.35, 0.14, K.METAL, seg=10)
        for k in range(12):
            a = k * 30.0
            px, py = polar(r + 0.06, a)
            with C.mb.at((px, py, 0.0), rot=a):
                C.mb.box((0, 0, 0), (0.14, 0.12, 0.1), mat)


def _annex_interior(C):
    z = FLOOR
    y0, y1 = ANX_Y
    h = EB_TOP - z
    kw = dict(base=BLUE_T, trim=K.TRIM_GOLD, trim_in=K.TRIM_WOOD)

    def DD(c):
        return K.Door(c, 1.8, 2.6, "academy_wood", double=True)
    C.box(-19.5, 52.5, z, 19.5, y0, EB_TOP, IN_WALL)
    C.wall((-4.0, y0), (-4.0, y1), z, h, 0.25, IN_WALL, inner=IN_WALL, ops=[DD(58.0 - y0), DD(68.5 - y0)], **kw)
    C.wall((4.0, y1), (4.0, y0), z, h, 0.25, IN_WALL, inner=IN_WALL, ops=[DD(y1 - 68.5), DD(y1 - 58.0)], **kw)
    for s in (-1, 1):
        a, b = sorted((s * 4.25, s * 19.5))
        C.box(a, 62.6, z, b, 62.85, EB_TOP, IN_WALL)
    # ---------------- faculty hall
    C.rug(-1.3, 53.6, 1.3, 73.8, "M_IntCarpetRed", K.TRIM_GOLD)
    emblem(C.nc, (0.0, y0, z + 2.45), 1.1, yaw=180.0, depth=0.18)
    C.prop("SM_Int_Console", 0.0, y0 + 0.25, z, 180.0)
    C.prop("SM_Int_PottedPlant", -0.4, y0 + 0.25, z + 0.85, 0.0)
    trophy(C, 0.35, y0 + 0.25, z + 0.85, 1.2)
    C.wtext("DUEL ACADEMY  -  FACULTY", 0.0, y0, z + 4.05, 180.0, 0.24, (0.1, 0.2, 0.55))
    for s in (-1, 1):
        x = s * 4.0
        for y in (54.6, 63.3, 73.4):
            C.prop("SM_Int_Painting", x - s * 0.04, y, z + 1.5, -90.0 * s)
        C.prop("SM_Int_Bench", x - s * 0.3, 63.3, z, -90.0 * s)
        plinth_bust(C, s * 2.9, 55.6, 180.0)
        C.prop("SM_Int_PottedPlantB", s * 3.4, 74.9, z, 0.0)
    for y in (58.5, 69.5):
        K.pendant(C.a, 0.0, y, EB_TOP, "chandelier")
    _plate_door(C, -4.0, 68.5, 90.0, "CHANCELLOR SHEPPARD", z=z + 2.95)
    _plate_door(C, -4.0, 58.0, 90.0, "FACULTY MEETING ROOM", z=z + 2.95)
    _plate_door(C, 4.0, 68.5, -90.0, "DR. CROWLER", z=z + 2.95)
    _plate_door(C, 4.0, 58.0, -90.0, "FACULTY LOUNGE", z=z + 2.95)
    C.npc(0.0, 65.0, 180.0, "white", 4.0)
    C.cam("annex_faculty_hall", (0.0, 74.3, z + 1.75), (0.0, 53.0, z + 2.0), 18)
    # ---------------- Chancellor Sheppard's office
    C.floor(-19.5, 62.85, -4.25, y1, "M_IntCarpetBlue")
    C.rug(-17.6, 65.2, -10.4, 72.6, "M_IntCarpetRed", K.TRIM_GOLD)
    C.wainscot((-19.5, y1), (-19.5, 62.85), z, 1.0, "M_IntWoodPanel", K.TRIM_GOLD)
    C.wainscot((-4.25, 62.85), (-4.25, y1), z, 1.0, "M_IntWoodPanel", K.TRIM_GOLD, gaps=[(4.65, 6.65)])
    _exec_desk(C, -15.4, 69.0, -90.0)
    C.prop("SM_Int_OfficeChair", -16.6, 69.0, z, 90.0)
    C.prop("SM_Int_DeskLamp", -15.5, 70.0, z + 0.79, 0.0)
    C.prop("SM_Int_Books", -15.5, 68.0, z + 0.79, 90.0)
    duel_disk(C, -15.3, 69.1, z + 0.79, 20.0)
    for y in (68.2, 69.8):
        C.prop("SM_Int_GreenChair", -13.5, y, z, -90.0)
    for k, (y, col) in enumerate(((66.93, "M_AcademyRed"), (70.79, "M_AcademyYellow"), (63.6, "M_AcademyBlue"))):
        C.mb.lathe([(0.2, 0.0), (0.2, 0.06), (0.03, 0.1), (0.03, 3.6)], K.TRIM_GOLD, seg=8,
                   center=C.P(-18.9, y, z))
        banner(C.nc, C.P(-18.75, y, z + 3.4), C.F.yaw(90.0), 0.9, 1.6, col, notch=0.35)
    # the big video wall
    C.box(-14.2, 62.85, z + 1.15, -8.2, 62.95, z + 3.75, "M_IntBlack", nc=True)
    C.box(-14.05, 62.95, z + 1.3, -8.35, 62.97, z + 3.6, "M_IntScreen", nc=True)
    C.wtext("INCOMING VIDEO CALL ...", -11.2, 62.97, z + 2.4, 180.0, 0.2, (1, 1, 1), emissive=True)
    for y in (63.5, 64.55, 65.6, 70.9, 71.95, 73.0, 74.05):
        C.prop("SM_Int_Bookshelf", -4.43, y, z, -90.0)
    sofa_corner(C, -10.8, y1 - 0.55, 0.0)
    C.prop("SM_Int_Console", -6.2, 63.1, z, 180.0)
    for k in range(3):
        trophy(C, -6.8 + k * 0.6, 63.1, z + 0.85, 1.0 + 0.4 * (k == 1))
    C.prop("SM_Int_GrandfatherClock", -18.9, 63.15, z, 180.0)
    C.prop("SM_Int_PottedPlantB", -18.9, 74.9, z, 0.0)
    K.pendant(C.a, -12.0, 69.0, EB_TOP, "chandelier")
    C.light(-12.0, 64.5, EB_TOP - 0.5, 2500, 8)
    C.npc(-16.6, 69.0, 90.0, "white", 0.5)
    C.cam("annex_chancellor", (-4.9, 63.5, z + 1.8), (-17.5, 72.5, z + 1.0), 17)
    # ---------------- faculty meeting room
    C.floor(-19.5, y0, -4.25, 62.6, "M_IntCarpetBlue")
    for x in (-12.9, -11.1):
        C.prop("SM_Int_Table", x, 57.8, z, 0.0)
    for x in (-13.6, -12.6, -11.4, -10.4):
        C.prop("SM_Int_DiningChair", x, 57.05, z, 180.0)
        C.prop("SM_Int_DiningChair", x, 58.55, z, 0.0)
    C.prop("SM_Int_DiningChair", -14.6, 57.8, z, 90.0)
    C.prop("SM_Int_DiningChair", -9.4, 57.8, z, -90.0)
    C.prop("SM_Int_ProjectorScreen", -12.0, y0 + 0.4, z, 180.0)
    for k in range(3):
        C.prop("SM_Int_Cabinet", -5.0, 54.2 + k * 0.95 if k < 2 else 61.6, z, -90.0)
    C.prop("SM_Int_PottedPlantB", -18.9, 53.6, z, 0.0)
    C.poster(-11.0, 62.6, z + 1.7, 0.0, 1.4, 0.9, "M_IntPoster3", "SCHOOL YEAR PLAN", (0.2, 0.1, 0.0), 0.08)
    for x in (-14.0, -10.0):
        K.pendant(C.a, x, 57.8, EB_TOP, "lamp")
    C.cam("annex_meeting_room", (-4.9, 62.0, z + 1.8), (-17.0, 55.0, z + 0.9), 17)
    # ---------------- Dr. Crowler's office
    C.floor(4.25, 62.85, 19.5, y1, "M_IntCarpetRed")
    C.rug(10.4, 65.2, 17.6, 72.6, "M_IntCarpetBlue", K.TRIM_GOLD)
    C.wainscot((19.5, 62.85), (19.5, y1), z, 1.2, "M_IntWallpaperBlue", K.TRIM_GOLD)
    C.wainscot((4.25, y1), (4.25, 62.85), z, 1.2, "M_IntWallpaperBlue", K.TRIM_GOLD, gaps=[(5.95, 7.95)])
    _exec_desk(C, 15.4, 69.0, 90.0, mat=NAVY_T)
    C.prop("SM_Int_OfficeChair", 16.6, 69.0, z, -90.0)
    C.prop("SM_Int_Candelabra", 15.5, 70.0, z + 0.79, 0.0)
    C.prop("SM_Int_Books", 15.5, 68.0, z + 0.79, 90.0)
    for y in (68.2, 69.8):
        C.prop("SM_Int_DiningChair", 13.5, y, z, 90.0)
    C.prop("SM_Int_Mirror", 10.5, 62.88, z + 1.0, 180.0)
    C.prop("SM_Int_Wardrobe", 6.0, 63.25, z, 180.0)
    C.prop("SM_Int_Wardrobe", 7.3, 63.25, z, 180.0)
    C.box(12.2, 72.0, z, 12.8, 72.6, z + 0.9, K.MARBLEFLOOR)
    _gear(C, 12.5, 72.3, z + 1.45)
    C.wtext("ANCIENT GEAR - MODEL", 12.5, 72.0, z + 0.55, 0.0, 0.07, (0.15, 0.1, 0.05))
    C.kit(K.piano, 8.0, 72.4, 160.0)
    for x in (8.0, 11.6, 15.2):
        banner(C.nc, C.P(x, y1 - 0.06, EB_TOP - 0.2), C.F.yaw(0.0), 0.9, 2.2, "M_AcademyBlue", notch=0.35)
    C.prop("SM_Int_Painting", 4.29, 73.0, z + 1.6, 90.0)
    C.prop("SM_Int_PottedPlantB", 18.9, 74.9, z, 0.0)
    K.pendant(C.a, 12.0, 69.0, EB_TOP, "chandelier")
    C.light(12.0, 64.5, EB_TOP - 0.5, 2500, 8)
    C.npc(16.6, 69.0, -90.0, "white", 0.5)
    C.cam("annex_crowler", (4.9, 63.5, z + 1.8), (17.5, 72.5, z + 1.0), 17)
    # ---------------- faculty lounge
    C.floor(4.25, y0, 19.5, 62.6, "M_IntWoodFloor", planks=True)
    with C.zat(z):
        K.kitchen_run(C.mb, C.nc, 9.4, y0, 14.6, against="-y")
    C.box(14.7, y0, z, 15.6, y0 + 0.7, z + 1.9, K.TRIM_WHITE)                     # fridge
    C.box(14.68, y0 + 0.7, z + 1.1, 14.72, y0 + 0.72, z + 1.6, K.METAL, nc=True)
    C.prop("SM_Int_Microwave", 10.0, y0 + 0.3, z + 0.9, 180.0)
    C.prop("SM_Int_Kettle", 13.9, y0 + 0.3, z + 0.9, 0.0)
    dining(C, 8.5, 58.5, 0.0, chairs=4, length=1.2, side=0.7)
    C.prop("SM_Int_TeaSet", 8.5, 58.5, z + 0.76, 0.0)
    sofa_corner(C, 15.5, 62.0, 0.0, rug="M_IntCarpetYellow")
    C.box(14.4, 57.3, z, 16.6, 57.8, z + 0.5, "M_IntWoodDark")
    C.prop("SM_Int_TV", 15.5, 57.55, z + 0.5, 180.0)
    C.prop("SM_Int_PottedPlantB", 18.9, 53.6, z, 0.0)
    C.prop("SM_Int_WallClock", 19.47, 58.0, z + 2.8, -90.0)
    C.poster(4.25, 54.6, z + 1.7, 90.0, 0.8, 1.0, "M_IntPoster4", "STAFF ONLY", size=0.08)
    for py in (55.5, 60.0):
        K.pendant(C.a, 11.5, py, EB_TOP, "lamp")
    C.npc(8.0, 58.0, 0.0, "white", 1.0)
    C.cam("annex_faculty_lounge", (4.9, 62.0, z + 1.8), (17.0, 54.0, z + 0.9), 17)


# ---------------------------------------------------------------------------- interiors: lobby side rooms
def _lobby_room(C, y0, y1, ydoor, title, hall_side):
    """Small room against the lobby's west wall (inside x -29 .. -22.25, y y0 .. y1) with a blue / gold fascia
    like the card shop. hall_side: 'n' or 's' - the second wall that faces the lobby."""
    z, h = FLOOR, 5.0
    kw = dict(base=BLUE_T, trim="M_Gold", trim_in=K.TRIM_WOOD)
    ya, yb = (y0, y1 + 0.25) if hall_side == "n" else (y0 - 0.25, y1)
    C.wall((-22.0, ya), (-22.0, yb), z, h, 0.25, "M_AcademyWall", inner=K.PLASTER_CREAM,
           ops=[K.Door(ydoor - ya, 1.8, 2.8, "academy_wood", double=True)], **kw)
    if hall_side == "n":
        C.wall((-22.25, yb), (-29.0, yb), z, h, 0.25, "M_AcademyWall", inner=K.PLASTER_CREAM, **kw)
    else:
        C.wall((-29.0, ya), (-22.25, ya), z, h, 0.25, "M_AcademyWall", inner=K.PLASTER_CREAM, **kw)
    C.box(-29.0, ya, z + h, -22.0, yb, z + h + 0.35, "M_AcademyWall", mats={"-z": K.CEIL})
    # fascia: blue band with gold lines on the two hall-facing sides
    e0, e1 = (ya, yb + 0.18) if hall_side == "n" else (ya - 0.18, yb)
    C.box(-22.0, e0, z + h - 0.6, -21.82, e1, z + h + 0.35, "M_AcademyBlue")
    f0, f1 = (yb, yb + 0.18) if hall_side == "n" else (ya - 0.18, ya)
    C.box(-29.0, f0, z + h - 0.6, -22.0, f1, z + h + 0.35, "M_AcademyBlue")
    for zz in (z + h - 0.66, z + h + 0.35):
        C.box(-21.84, e0 - 0.02, zz, -21.78, e1 + 0.02, zz + 0.06, "M_Gold")
    C.text(title, -21.77, (y0 + y1) / 2, z + h - 0.38, 90.0, 0.42, (1.0, 0.86, 0.4), emissive=True)
    C.floor(-29.0, y0, -22.25, y1, "M_IntCarpetBlue")
    C.wainscot((-29.0, y1), (-29.0, y0), z, 1.0, BLUE_T)


def _lobby_rooms(C):
    z = FLOOR
    # ---------------- admissions office (south-west corner)
    y0, y1 = LY0 + LWALL, -54.25
    _lobby_room(C, y0, y1, -61.0, "ADMISSIONS", "n")
    C.box(-25.2, -63.6, z, -24.6, -58.4, z + 1.0, "M_IntWood", mats={"+x": BLUE_T})
    C.box(-25.3, -63.7, z + 1.0, -24.5, -58.3, z + 1.06, "M_Marble")
    for y in (-62.4, -59.6):
        C.prop("SM_Int_OfficeDesk", -27.4, y, z, -90.0)
        C.prop("SM_Int_OfficeChair", -28.25, y, z, 90.0)
        C.prop("SM_Int_DeskLamp", -27.4, y + 0.45, z + 0.76, 0.0)
    for x in (-28.4, -27.5, -26.6):
        C.prop("SM_Int_Cabinet", x, y1 - 0.25, z, 0.0)
    C.poster(-24.4, y1, z + 2.6, 0.0, 1.6, 1.0, "M_IntPoster2", "ENTRANCE EXAM RESULTS", size=0.08)
    C.box(-23.0, y1 - 0.6, z, -22.4, y1 - 0.05, z + 1.2, K.TRIM_WHITE)                       # water cooler
    C.nc.cylinder(C.P(-22.7, y1 - 0.33, z + 1.2), 0.15, 0.4, "M_IntGlassClear", seg=10)
    C.prop("SM_Int_PottedPlantB", -23.0, y0 + 0.5, z, 0.0)
    C.prop("SM_Int_WallClock", -28.97, -57.5, z + 3.2, 90.0)
    for y in (-62.0, -57.0):
        K.pendant(C.a, -25.6, y, z + 5.0, "lamp")
    C.npc(-26.6, -60.0, 90.0, "white", 0.5)
    C.cam("lobby_admissions", (-22.9, -54.9, z + 1.8), (-28.5, -63.5, z + 0.9), 17)
    # ---------------- duel disk service (north-west corner)
    y0, y1 = -33.75, LY1 - LWALL
    _lobby_room(C, y0, y1, -28.0, "DUEL DISK SERVICE", "s")
    C.box(-29.0, -32.4, z, -28.2, -25.0, z + 0.95, K.METAL, mats={"+z": "M_IntWood"})
    for k in range(4):
        duel_disk(C, -28.6, -31.6 + k * 1.6, z + 0.95, 90.0 + 15 * k)
    C.box(-28.98, -30.0, z + 1.4, -28.94, -27.0, z + 2.6, "M_IntBlack", nc=True)
    C.box(-28.94, -29.9, z + 1.5, -28.92, -27.1, z + 2.5, "M_IntScreen", nc=True)
    C.wtext("DISK DIAGNOSTICS: OK", -28.92, -28.5, z + 2.0, 90.0, 0.12, (1, 1, 1), out=0.01, emissive=True)
    for k in range(4):
        C.prop("SM_Int_SteelShelves", -27.6 + k * 1.3, y1 - 0.3, z, 0.0)
        for j in range(2):
            duel_disk(C, -27.75 + k * 1.3, y1 - 0.3, z + 0.7 + j * 0.6, 0.0)
    C.box(-25.0, -31.6, z, -24.4, -25.4, z + 1.0, BLUE_T, mats={"+x": "M_IntWood"})
    C.box(-25.1, -31.7, z + 1.0, -24.3, -25.3, z + 1.06, K.TRIM_WHITE)
    duel_disk(C, -24.7, -27.0, z + 1.06, 70.0)
    for k in range(2):
        C.prop("SM_Int_Stool", -27.6, -31.0 + k * 3.0, z, 0.0)
    C.prop("SM_Int_Box", -25.8, y0 + 0.4, z, 10.0)
    C.prop("SM_Int_Box", -25.2, y0 + 0.4, z, -20.0)
    C.prop("SM_Int_HandTruck", -23.0, y0 + 0.5, z, 30.0)
    C.poster(-26.0, y0, z + 2.2, 180.0, 1.8, 1.0, "M_IntPoster1", "REPAIRS & UPGRADES", size=0.09)
    K.pendant(C.a, -25.6, -30.6, z + 5.0, "industrial")
    K.pendant(C.a, -25.6, -26.4, z + 5.0, "industrial")
    C.npc(-25.6, -28.4, 90.0, "white", 0.5)
    C.cam("lobby_duel_disk_service", (-22.9, -33.2, z + 1.8), (-28.6, -24.0, z + 0.9), 17)


# ---------------------------------------------------------------------------- interiors: towers
TOWER_NAMES = {(-1, True): "SLIFER TOWER", (1, True): "RA TOWER", (-1, False): "OBELISK TOWER (NORTH-WEST)",
               (1, False): "OBELISK TOWER (NORTH-EAST)"}


def _tower_interior(C, accent, name, cam):
    """Stair hall in a tower base (tower frame: entrance in the local south wall at ground level, the landing
    at FLOOR in the back leads through the end pavilion wall into its corridor)."""
    i = TW_H - 0.5          # inside half width
    C.box(-i, 2.5, 0.0, i, TW_H, FLOOR, "M_AcademyWall", mats={"+z": K.MARBLEFLOOR, "-y": IN_WALL})
    C.box(-i, 2.45, FLOOR - 0.12, i, 2.55, FLOOR + 0.004, K.TRIM_GOLD)
    n, run = 10, 0.3
    ys = 2.5 - n * run
    a = math.degrees(math.atan2(*reversed(C.F.v(0.0, 1.0))))
    with C.mb.at(C.P(0.0, ys, 0.0), rot=a):
        C.mb.stairs((0, 0, 0), 0.0, 3.6, n, FLOOR / n, run, K.MARBLEFLOOR)
    for k in range(n):        # red carpet runner
        C.box(-1.1, ys + k * run, FLOOR / n * (k + 1), 1.1, ys + (k + 1) * run, FLOOR / n * (k + 1) + 0.01,
              "M_IntCarpetRed", nc=True)
    C.rug(-1.1, 2.55, 1.1, 5.0, "M_IntCarpetRed", K.TRIM_GOLD, z=FLOOR + 0.005)
    for sx in (-1, 1):
        x = sx * 1.9
        C.mb.beam(C.P(x, ys - 0.1, 0.95), C.P(x, 2.5, FLOOR + 0.95), 0.07, 0.06, K.TRIM_GOLD)
        for k in range(0, n + 1, 2):
            C.box(x - 0.02, ys + k * run + 0.1, FLOOR / n * k, x + 0.02, ys + k * run + 0.14, FLOOR / n * k + 0.95,
                  K.TRIM_GOLD)
        K.railing(C.mb, [C.F.p(sx * i, 2.6), C.F.p(sx * 1.9, 2.6)], FLOOR, 1.0, K.TRIM_GOLD, spacing=0.3)
        plinth_bust(C, sx * 3.3, ys - 0.6, 0.0, z=0.0)
        C.prop("SM_Int_Bench", sx * (i - 0.3), -2.0, 0.0, -90.0 * sx)
        C.prop("SM_Int_PottedPlantB", sx * (i - 0.5), -i + 0.5, 0.0, 0.0)
        C.prop("SM_Int_PottedPlant", sx * (i - 0.4), TW_H - 0.4, FLOOR, 0.0)
    C.rug(-2.0, -3.9, 2.0, -1.2, accent, K.TRIM_GOLD, z=0.005)
    banner(C.nc, C.P(0.0, TW_H - 0.06, TW_CEIL - 0.3), C.F.yaw(0.0), 1.8, 2.6, accent)
    C.wtext(name, 0.0, -i, 5.0, 180.0, 0.3, (0.1, 0.2, 0.55))
    C.wtext("PAVILION  ^", 0.0, TW_H, FLOOR + 3.1, 0.0, 0.2, (0.1, 0.2, 0.55))
    K.pendant(C.a, *C.F.p(0.0, -1.8), TW_CEIL, "chandelier")
    C.light(0.0, 4.2, FLOOR + 3.0, 2500, 8)
    C.cam(cam, (-i + 0.7, -i + 0.6, 1.7), (1.2, TW_H, 3.0), 17)


def _interiors(aset, mb, nc):
    for (cx, cy, accent, front) in ((-101.0, -46.0, "M_AcademyRed", True), (101.0, -46.0, "M_AcademyYellow", True),
                                    (-101.0, 56.0, "M_AcademyBlue", False), (101.0, 56.0, "M_AcademyBlue", False)):
        s = 1 if cx > 0 else -1
        name = TOWER_NAMES[(s, front)]
        cam = f"tower_{'E' if s > 0 else 'W'}{'S' if front else 'N'}"
        _tower_interior(Ctx(aset, mb, nc, tower_frame(cx, cy, front)), accent, name, cam)
    _annex_interior(Ctx(aset, mb, nc))
    _lobby_rooms(Ctx(aset, mb, nc))
    for s in (-1, 1):
        C = Ctx(aset, mb, nc, Fr.make(mx=s < 0))
        _wing_interior(C, s)
        _end_block_interior(C, s)


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
