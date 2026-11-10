"""
Parametric bridges for the path / river crossings (placed by the layout stage, one per crossing).

Both builders work in a local frame the caller sets up with MeshBuilder.at():

    X  along the bridge, from -length / 2 to +length / 2
    Y  across it
    Z  up; z = 0 is the walking surface - one flat, continuous slab over the whole length (people, NPCs and
       the motorcycle cross it; nothing sticks up between the parapets / handrails)

    stone_arch(mb, length, width, drop, water_half, nocol=None)
    wood_trestle(mb, length, width, drop, water_half, nocol=None)

  length      end to end (m), any 8 .. 45
  width       clear width between the parapets / handrails
  drop        height of the deck above the river bed at mid-span; the piers, bents and abutments reach down to
              -drop - 1.0 so nothing floats over uneven banks
  water_half  half-width of the water under the middle: that opening stays free of piers where the height
              allows a span that wide (a low stone bridge over wide water gets piers with cutwaters instead)
  mb          MeshBuilder for everything with collision
  nocol       MeshBuilder for the fine detail that needs none (None: it goes into mb)

Each returns dict(lamps=[(x, y, z)], ...): the lanterns modelled on the bridge (local positions of their
glass), for the caller to put warm night lights at.
"""

import math

from .. import palette

palette.register({
    "M_BridgeStone":      dict(kind="opaque", color=(0.53, 0.50, 0.45), rough=0.92, detail="Bricks", tiling=0.5),
    "M_BridgeStoneLight": dict(kind="opaque", color=(0.75, 0.72, 0.65), rough=0.9, detail="Rock", tiling=0.6),
    "M_BridgeStoneDark":  dict(kind="opaque", color=(0.47, 0.45, 0.41), rough=0.95, detail="Rock", tiling=0.6),
    "M_BridgeCoping":     dict(kind="opaque", color=(0.70, 0.68, 0.63), rough=0.85, detail="Concrete", tiling=0.5),
    "M_BridgeTimber":     dict(kind="opaque", color=(0.40, 0.29, 0.19), rough=0.9, detail="Planks", tiling=0.6),
    "M_BridgeTimberDark": dict(kind="opaque", color=(0.26, 0.19, 0.13), rough=0.92, detail="Planks", tiling=0.6),
})

STONE, STONE_L, STONE_D, COPING = "M_BridgeStone", "M_BridgeStoneLight", "M_BridgeStoneDark", "M_BridgeCoping"
PAVING = "M_Paving"
TIMBER, TIMBER_D, PLANK = "M_BridgeTimber", "M_BridgeTimberDark", "M_PierWood"
IRON, GLOW = "M_DarkMetal", "M_LampGlow"

PARAPET_T = 0.42        # stone parapet thickness
PARAPET_H = 1.08
CROWN = 0.55            # arch crown (intrados) below the walking surface: ring + fill + paving
DEEP = 1.0              # how far below the river bed the structure goes


# --------------------------------------------------------------------------- shared bits
def _lantern(mb, nc, x, y, z, post=0.55):
    """Small iron lantern on a post standing at (x, y, z). Returns the position of its glass."""
    mb.box((x, y, z + post / 2), (0.07, 0.07, post), IRON)
    nc.box((x, y, z + post + 0.02), (0.24, 0.24, 0.04), IRON)
    nc.box((x, y, z + post + 0.17), (0.17, 0.17, 0.26), GLOW)
    for sx in (-1, 1):
        for sy in (-1, 1):
            nc.box((x + sx * 0.095, y + sy * 0.095, z + post + 0.17), (0.02, 0.02, 0.28), IRON)
    nc.pyramid((x, y, z + post + 0.3), 0.3, 0.3, 0.16, IRON)
    return (x, y, z + post + 0.17)


def _layout_spans(length, centre, pier, end, max_side):
    """Openings of a symmetric bridge: a centre span plus k side spans each side, piers `pier` thick between
    them, at least `end` of abutment at both ends. Returns [(x0, x1)] sorted along X (centre span included)."""
    half = length / 2.0
    centre = max(min(centre, length - 2.0 * end), 1.0)
    rem = half - centre / 2.0 - end                 # room for side spans (and their piers) on one side
    k = 0
    side = 0.0
    if rem > pier + 2.2:
        k = max(1, int(math.ceil((rem) / (max_side + pier))))
        side = rem / k - pier
        while k > 1 and side < 2.2:
            k -= 1
            side = rem / k - pier
        if side < 2.2:
            k, side = 0, 0.0
    spans = [(-centre / 2.0, centre / 2.0)]
    x = centre / 2.0
    for _ in range(k):
        spans.append((x + pier, x + pier + side))
        spans.insert(0, (-(x + pier + side), -(x + pier)))
        x += pier + side
    return spans


# --------------------------------------------------------------------------- stone arch bridge
def _arch(x0, x1, rise, n):
    """Intrados of a segmental arch over [x0, x1] with its crown at z = -CROWN: [(x, z)] with n segments."""
    span = x1 - x0
    rise = min(rise, span / 2.0)
    r = (span * span / 4.0 + rise * rise) / (2.0 * rise)
    cx, cz = (x0 + x1) / 2.0, -CROWN - r
    a = math.asin(min(1.0, span / (2.0 * r)))
    return [(cx + r * math.sin(-a + 2.0 * a * i / n), cz + r * math.cos(-a + 2.0 * a * i / n)) for i in range(n + 1)], \
        (cx, cz, r)


def stone_arch(mb, length, width, drop, water_half, nocol=None):
    """Masonry bridge: segmental arches with voussoir rings and keystones, piers with pointed cutwaters,
    solid parapets with coping and refuges over the piers, a paved deck."""
    nc = nocol if nocol is not None else mb
    length, width, drop = float(length), float(width), max(float(drop), 1.6)
    half = length / 2.0
    wt = width + 2.0 * PARAPET_T             # overall width of the masonry
    yo = wt / 2.0
    bottom = -drop - DEEP
    deck_t = 0.14

    # ---- how the openings are laid out: the highest arch the drop allows, as wide as the water where it can be
    rise_max = max(0.9, drop - CROWN - 0.55)             # springing stays just above the bed
    pier = min(1.6, max(0.9, drop * 0.22))
    end = max(1.3, min(2.4, length * 0.07))
    want = 2.0 * water_half + 0.8
    centre = max(3.4, min(want, 5.2 * rise_max, length - 2.0 * end))
    spans = _layout_spans(length, centre, pier, end, max_side=max(centre, 3.0))
    arches = []
    for (x0, x1) in spans:
        n = max(8, min(20, int((x1 - x0) * 1.6)))
        pts, circ = _arch(x0, x1, rise_max, n)
        arches.append((x0, x1, pts, circ))

    # ---- deck: one slab, its top the walking surface
    mb.box((0, 0, -deck_t / 2), (length, wt, deck_t), PAVING, mats={"-y": STONE, "+y": STONE, "-x": STONE, "+x": STONE})
    top = -deck_t

    # ---- masonry between and above the arches (spandrels + fill), piers and abutments
    def solid(x0, x1):
        if x1 - x0 > 1e-3:
            mb.box_mm((x0, -yo, bottom), (x1, yo, top), STONE, skip=("+z",))

    x = -half
    for (x0, x1, pts, _c) in arches:
        solid(x, x0)
        x = x1
    solid(x, half)
    for (x0, x1, pts, _c) in arches:
        for (xa, za), (xb, zb) in zip(pts, pts[1:]):
            # block over one arch segment: sloped soffit (the intrados), flat top under the deck
            mb.quad((xa, yo, za), (xb, yo, zb), (xb, -yo, zb), (xa, -yo, za), STONE_D, smooth=True)       # soffit
            mb.quad((xa, -yo, za), (xb, -yo, zb), (xb, -yo, top), (xa, -yo, top), STONE)                  # -y face
            mb.quad((xb, yo, zb), (xa, yo, za), (xa, yo, top), (xb, yo, top), STONE)                      # +y face
    # ---- voussoir rings, keystones, string course (proud of the faces)
    for (x0, x1, pts, (cx, cz, r)) in arches:
        ring = min(0.42, max(0.28, (x1 - x0) * 0.045))
        for s in (-1, 1):
            y_in, y_out = s * yo, s * (yo + 0.06)
            for i, ((xa, za), (xb, zb)) in enumerate(zip(pts, pts[1:])):
                mat = STONE_L if i % 2 == 0 else COPING
                oa = (xa + (xa - cx) / r * ring, za + (za - cz) / r * ring)
                ob = (xb + (xb - cx) / r * ring, zb + (zb - cz) / r * ring)
                face = [(xa, y_out, za), (xb, y_out, zb), (ob[0], y_out, ob[1]), (oa[0], y_out, oa[1])]
                nc.poly(face if s < 0 else list(reversed(face)), mat)
                edge = [(oa[0], y_out, oa[1]), (ob[0], y_out, ob[1]), (ob[0], y_in, ob[1]), (oa[0], y_in, oa[1])]
                nc.poly(edge if s < 0 else list(reversed(edge)), mat)
            kx = (x0 + x1) / 2.0
            nc.box((kx, s * (yo + 0.05), -CROWN + ring * 0.55), (0.34, 0.2, ring * 1.5), STONE_L)
        # springer blocks where the ring lands on the pier
        for xs in (x0, x1):
            nc.box((xs, 0, pts[0][1] - 0.09), (0.3, wt + 0.2, 0.18), COPING)
    nc.box((0, -(yo + 0.04), top + 0.02), (length, 0.1, 0.16), COPING)
    nc.box((0, (yo + 0.04), top + 0.02), (length, 0.1, 0.16), COPING)

    # ---- cutwaters on the piers (pointed up- and downstream), capped under the parapet refuges
    piers = [(a[1] + b[0]) / 2.0 for a, b in zip(spans, spans[1:])]
    pier_w = spans[1][0] - spans[0][1] if len(spans) > 1 else pier
    cw_top = min(top - 0.25, arches[0][2][0][1] + 0.9)           # a little over the springing
    for px in piers:
        for s in (-1, 1):
            nose = 0.9 + 0.25 * pier_w
            a = (px - pier_w / 2.0, s * yo)
            b = (px + pier_w / 2.0, s * yo)
            c = (px, s * (yo + nose))
            tri = [a, b, c] if s > 0 else [b, a, c]
            mb.prism(tri, bottom, cw_top, STONE, top_mat=COPING)
            mb.poly([(tri[0][0], tri[0][1], cw_top), (tri[1][0], tri[1][1], cw_top), (px, s * yo, cw_top + 0.45)],
                    COPING)                                       # weathered cap sloping back to the wall
            mb.poly([(tri[1][0], tri[1][1], cw_top), (tri[2][0], tri[2][1], cw_top), (px, s * yo, cw_top + 0.45)],
                    COPING)
            mb.poly([(tri[2][0], tri[2][1], cw_top), (tri[0][0], tri[0][1], cw_top), (px, s * yo, cw_top + 0.45)],
                    COPING)

    # ---- parapets with coping; taller pilasters at the ends and over the piers
    yp = width / 2.0 + PARAPET_T / 2.0
    for s in (-1, 1):
        mb.box((0, s * yp, PARAPET_H / 2 - 0.02), (length, PARAPET_T, PARAPET_H), STONE)
        mb.box((0, s * yp, PARAPET_H + 0.04), (length + 0.1, PARAPET_T + 0.14, 0.12), COPING)
    lamps = []
    posts = [-half + 0.45, half - 0.45]
    lamp_x = list(piers)
    if len(lamp_x) > 2:                                           # long bridge: lanterns on every other pier
        lamp_x = lamp_x[::2]
    for px in posts + piers:
        for s in (-1, 1):
            mb.box((px, s * (yp + 0.03), (PARAPET_H + 0.3) / 2 - 0.02), (0.7, PARAPET_T + 0.16, PARAPET_H + 0.3), STONE_L)
            mb.box((px, s * (yp + 0.03), PARAPET_H + 0.33), (0.84, PARAPET_T + 0.3, 0.1), COPING)
    for px in sorted(set(lamp_x + posts)):
        for s in (-1, 1):
            lamps.append(_lantern(mb, nc, px, s * (yp + 0.03), PARAPET_H + 0.38))
    # worn stone setts across the deck at the ends (flush - a visual threshold, nothing to trip on)
    for sx in (-1, 1):
        nc.box((sx * (half - 0.3), 0, 0.004), (0.6, width, 0.008), COPING, skip=("-z",))
    return dict(lamps=lamps, spans=spans, piers=piers, overall_width=wt + 0.3)


# --------------------------------------------------------------------------- timber trestle bridge
def wood_trestle(mb, length, width, drop, water_half, nocol=None):
    """Timber bridge: plank deck on stringers, trestle bents (battered posts, cap, sill and cross bracing)
    clear of the water where a timber span can reach across it, handrails with lantern posts."""
    nc = nocol if nocol is not None else mb
    length, width, drop = float(length), float(width), max(float(drop), 1.2)
    half = length / 2.0
    bottom = -drop - DEEP
    deck_w = width + 0.5                      # the rails stand outside the clear width
    yr = width / 2.0 + 0.11                   # handrail line
    deck_t = 0.09

    # ---- deck: one continuous slab (the walking surface), plank joints as flush dark lines, edge beams
    mb.box((0, 0, -deck_t / 2), (length, deck_w, deck_t), PLANK)
    n_planks = int(length / 0.32)
    for i in range(1, n_planks):
        x = -half + length * i / n_planks
        nc.box((x, 0, 0.002), (0.022, deck_w - 0.36, 0.004), TIMBER_D, skip=("-z",))
    for s in (-1, 1):
        mb.box((0, s * (deck_w / 2 - 0.09), 0.05), (length, 0.18, 0.1 + deck_t * 2), TIMBER)   # kerb beam under the rail
    # stringers
    ny = max(3, int(round(deck_w / 1.1)) + 1)
    for i in range(ny):
        y = -deck_w / 2 + 0.2 + (deck_w - 0.4) * i / (ny - 1)
        mb.box((0, y, -deck_t - 0.17), (length, 0.2, 0.34), TIMBER_D)
    under = -deck_t - 0.34

    # ---- bents
    free = min(max(2.0 * water_half + 1.0, 3.6), 9.5)            # what a timber span carries
    free = min(free, max(length - 3.0, 2.4))
    xs = []
    x = free / 2.0
    rem = half - 0.7 - x
    if rem > 0:
        k = max(1, int(math.ceil(rem / 4.6)))
        step = rem / k
        xs = [x + step * i for i in range(k + 1)]
    else:
        xs = [half - 0.7]
    bents = sorted([-v for v in xs] + xs)
    h = under - bottom                                            # post length
    batter = min(0.9, 0.11 * h)
    post = 0.26 if h < 6.0 else 0.32
    yb = deck_w / 2 - 0.25
    for bx in bents:
        mb.box((bx, 0, under - 0.14), (0.3, deck_w + 0.5, 0.28), TIMBER)                       # cap beam
        feet = []
        for s in (-1, 1):
            p_top, p_bot = (bx, s * yb, under - 0.28), (bx, s * (yb + batter), bottom)
            mb.beam(p_bot, p_top, post, post, TIMBER)
            feet.append((p_top, p_bot))
        if deck_w > 4.4:                                           # a wide deck gets a centre post
            mb.beam((bx, 0, bottom), (bx, 0, under - 0.28), post, post, TIMBER)
        # cross bracing in tiers of ~2.6 m, horizontal ties between them
        tiers = max(1, int(round((h - 0.6) / 2.6)))
        zt, zb = under - 0.5, bottom + DEEP + 0.25
        if zt - zb > 0.9:
            def at(z, s):
                t = (z - (under - 0.28)) / (bottom - (under - 0.28))
                return (bx, s * (yb + batter * t), z)
            for i in range(tiers):
                z1 = zt - (zt - zb) * i / tiers
                z0 = zt - (zt - zb) * (i + 1) / tiers
                mb.beam(at(z0, -1), at(z1, 1), 0.07, 0.2, TIMBER_D)
                mb.beam(at(z0, 1), at(z1, -1), 0.07, 0.2, TIMBER_D)
                a, b = at(z0, -1), at(z0, 1)
                mb.beam((a[0], a[1] - 0.25, a[2]), (b[0], b[1] + 0.25, b[2]), 0.12, 0.2, TIMBER)
    # knee braces under the long centre span, longitudinal braces between the side bents
    inner = [b for b in bents if abs(abs(b) - free / 2.0) < 1e-6]
    for bx in inner:
        sgn = -1.0 if bx > 0 else 1.0
        reach = min(free * 0.3, 2.2)
        for s in (-1, 1):
            nc.beam((bx, s * yb, under - 0.28 - reach * 0.9), (bx + sgn * reach, s * yb, under), 0.16, 0.16, TIMBER_D)
    for a, b in zip(bents, bents[1:]):
        if a * b < 0 or b - a < 2.0 or h < 2.6:
            continue
        zc = under - 0.6
        for s in (-1, 1):
            nc.beam((a, s * (yb + 0.16), max(zc - (b - a) * 0.8, bottom + DEEP)), (b, s * (yb + 0.16), zc), 0.07, 0.18,
                    TIMBER_D)
    # ---- bulkheads at both ends: sheet planking that keeps the bank back under the deck
    for sx in (-1, 1):
        mb.box((sx * (half - 0.09), 0, (under + bottom) / 2), (0.18, deck_w + 0.6, under - bottom), TIMBER_D)
        for s in (-1, 1):
            mb.box((sx * (half - 0.22), s * (deck_w / 2 + 0.12), (0.0 + bottom) / 2), (0.3, 0.3, -bottom), TIMBER)

    # ---- handrails: posts, top + mid rail, lantern posts at the ends and over the inner bents
    rail_h = 1.1
    n_post = max(2, int(round(length / 2.0)) + 1)
    px = [-half + 0.14 + (length - 0.28) * i / (n_post - 1) for i in range(n_post)]
    lamp_at = {0, n_post - 1}
    if length > 16.0:
        lamp_at |= {min(range(n_post), key=lambda i: abs(px[i] - b)) for b in inner}
    lamps = []
    for s in (-1, 1):
        for i, x in enumerate(px):
            tall = i in lamp_at
            ph = 2.15 if tall else rail_h + 0.06
            mb.box((x, s * yr, ph / 2 - 0.05), (0.13, 0.13, ph + 0.1), TIMBER)
            if tall:                                               # bracket + hanging lantern over the deck edge
                nc.beam((x, s * yr, 2.05), (x, s * (yr - 0.42), 2.05), 0.06, 0.06, TIMBER_D)
                nc.beam((x, s * yr, 1.7), (x, s * (yr - 0.34), 2.03), 0.05, 0.05, TIMBER_D)
                lx, ly, lz = x, s * (yr - 0.38), 1.82
                nc.box((lx, ly, lz + 0.17), (0.2, 0.2, 0.03), IRON)
                nc.box((lx, ly, lz), (0.15, 0.15, 0.26), GLOW)
                nc.box((lx, ly, lz - 0.15), (0.2, 0.2, 0.03), IRON)
                nc.box((lx, ly, lz + 0.21), (0.02, 0.02, 0.08), IRON)
                lamps.append((lx, ly, lz))
        mb.box((0, s * yr, rail_h), (length - 0.1, 0.16, 0.09), TIMBER)                        # hand rail
        mb.box((0, s * yr, rail_h * 0.52), (length - 0.1, 0.07, 0.14), TIMBER_D)               # mid rail
        mb.box((0, s * yr, 0.2), (length - 0.1, 0.06, 0.12), TIMBER_D)                         # toe board
        for a, b in zip(px, px[1:]):                                                           # X balusters
            nc.beam((a + 0.07, s * yr, 0.28), (b - 0.07, s * yr, rail_h * 0.52 - 0.08), 0.04, 0.06, TIMBER_D)
            nc.beam((a + 0.07, s * yr, rail_h * 0.52 - 0.08), (b - 0.07, s * yr, 0.28), 0.04, 0.06, TIMBER_D)
    return dict(lamps=lamps, bents=bents, free_span=free, overall_width=deck_w + 0.6)
