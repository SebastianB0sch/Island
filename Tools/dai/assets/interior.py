"""
Interior kit - shared building blocks for the walk-in rooms of every building.

Look: the anime-background style of the exteriors carried inside. Architectural surfaces use cel materials
(M_DA_Toon: flat colour + soft fill light, with a faint plank / tile / weave detail), furniture comes from the
CC0 Poly Haven catalog (SM_Int_*, cel-painted with an ink outline, see furniture.py) plus the GX-specific
pieces modelled here (triple bunk beds, kotatsu, lecture tiers, lockers, blackboards ...).

Conventions (same as the location modules): metres, local space of the AssetSet, z up, walls follow
MeshBuilder.wall(): walking p0 -> p1 the INSIDE is on the LEFT (+y local), outside on the right.

    from . import interior as K
    K.wall(aset, mb, (x0, y0), (x1, y0), z, h, 0.2, "M_RaWall", inner=K.PLASTER_CREAM,
           openings=[K.Door(4.0, 1.0, 2.2, "ra"), K.Window(9.0, 1.4, 0.9, 2.2)])

Door(...) openings also place an automatic door (aset.door) in the middle of the wall thickness.
"""

import math

from .. import palette

# ----------------------------------------------------------------------------- palette (cel materials)
def _t(color, detail=None, tiling=1.0, strength=0.5, fill=0.3, rough=0.85):
    d = dict(kind="toon", color=color, rough=rough, fill=fill)
    if detail:
        d.update(detail=detail, tiling=tiling, detail_strength=strength)
    return d


palette.register({
    # walls
    "M_IntPlasterCream":  _t((0.97, 0.91, 0.78), "Plaster", 0.5, 0.25),
    "M_IntPlasterWhite":  _t((0.95, 0.95, 0.93), "Plaster", 0.5, 0.2),
    "M_IntPlasterPeach":  _t((0.98, 0.84, 0.72), "Plaster", 0.5, 0.25),
    "M_IntPlasterSky":    _t((0.76, 0.86, 0.97), "Plaster", 0.5, 0.2),
    "M_IntPlasterRose":   _t((0.98, 0.85, 0.88), "Plaster", 0.5, 0.2),
    "M_IntPlasterYellow": _t((0.99, 0.91, 0.62), "Plaster", 0.5, 0.25),
    "M_IntPlasterMint":   _t((0.80, 0.93, 0.86), "Plaster", 0.5, 0.2),
    "M_IntWallpaperBlue": _t((0.62, 0.73, 0.93), "Fabric", 1.5, 0.3),
    "M_IntWallpaperRed":  _t((0.70, 0.22, 0.22), "Fabric", 1.5, 0.3),
    "M_IntWoodPanel":     _t((0.60, 0.40, 0.24), "Planks", 0.6, 0.45),
    "M_IntConcrete":      _t((0.70, 0.71, 0.72), "Concrete", 0.3, 0.45),
    "M_IntCeiling":       _t((0.97, 0.96, 0.93), None, fill=0.35),
    "M_IntCeilingWood":   _t((0.78, 0.60, 0.40), "Planks", 0.6, 0.4),
    # floors
    "M_IntWoodFloor":     _t((0.80, 0.58, 0.36), "Planks", 0.6, 0.5, rough=0.5),
    "M_IntWoodFloorDark": _t((0.52, 0.33, 0.20), "Planks", 0.6, 0.5, rough=0.45),
    "M_IntTatami":        _t((0.80, 0.80, 0.52), "Fabric", 2.0, 0.45),
    "M_IntTatamiEdge":    _t((0.20, 0.28, 0.22), None),
    "M_IntTileWhite":     _t((0.93, 0.94, 0.95), "FloorTiles", 0.8, 0.45, rough=0.3),
    "M_IntTileBlue":      _t((0.55, 0.72, 0.90), "FloorTiles", 0.8, 0.45, rough=0.3),
    "M_IntLinoleum":      _t((0.66, 0.78, 0.70), "Concrete", 0.5, 0.25, rough=0.4),
    "M_IntMarbleFloor":   _t((0.93, 0.92, 0.90), "Marble", 0.3, 0.45, rough=0.15),
    "M_IntCarpetRed":     _t((0.68, 0.10, 0.12), "Fabric", 1.0, 0.5),
    "M_IntCarpetBlue":    _t((0.16, 0.28, 0.62), "Fabric", 1.0, 0.5),
    "M_IntCarpetRose":    _t((0.90, 0.62, 0.70), "Fabric", 1.0, 0.5),
    "M_IntCarpetYellow":  _t((0.92, 0.72, 0.22), "Fabric", 1.0, 0.5),
    # trims / furniture surfaces
    "M_IntTrimWhite":     _t((0.98, 0.97, 0.94)),
    "M_IntTrimWood":      _t((0.45, 0.28, 0.16), "Planks", 0.6, 0.3),
    "M_IntTrimGold":      _t((0.96, 0.76, 0.30), rough=0.35),
    "M_IntWood":          _t((0.70, 0.48, 0.28), "Planks", 0.6, 0.35),
    "M_IntWoodDark":      _t((0.36, 0.22, 0.13), "Planks", 0.6, 0.35),
    "M_IntMetal":         _t((0.70, 0.73, 0.77), rough=0.4),
    "M_IntSteelBlue":     _t((0.40, 0.52, 0.66), rough=0.45),
    "M_IntBlack":         _t((0.07, 0.07, 0.08)),
    "M_IntChalkboard":    _t((0.13, 0.30, 0.22), "Concrete", 0.5, 0.25),
    "M_IntChalk":         dict(kind="emissive", color=(0.95, 0.95, 0.90), strength=0.6),
    "M_IntCork":          _t((0.72, 0.52, 0.32), "Sand", 1.0, 0.5),
    "M_IntPaper":         _t((0.98, 0.97, 0.92)),
    "M_IntPoster1":       _t((0.95, 0.40, 0.30)),
    "M_IntPoster2":       _t((0.30, 0.55, 0.95)),
    "M_IntPoster3":       _t((0.98, 0.80, 0.25)),
    "M_IntPoster4":       _t((0.55, 0.30, 0.75)),
    "M_IntScreen":        dict(kind="emissive", color=(0.45, 0.70, 1.00), strength=2.5),
    "M_IntWindowSky":     dict(kind="emissive", color=(0.78, 0.90, 1.00), strength=2.2),
    "M_IntLightPanel":    dict(kind="emissive", color=(1.00, 0.97, 0.90), strength=6.0),
    "M_IntWarmGlow":      dict(kind="emissive", color=(1.00, 0.80, 0.50), strength=6.0),
    "M_IntFire":          dict(kind="emissive", color=(1.00, 0.45, 0.12), strength=10.0),
    # fabrics (beds, curtains, cushions)
    "M_IntFabricRed":     _t((0.82, 0.16, 0.14), "Fabric", 2.0, 0.35),
    "M_IntFabricYellow":  _t((0.98, 0.82, 0.25), "Fabric", 2.0, 0.35),
    "M_IntFabricBlue":    _t((0.22, 0.38, 0.80), "Fabric", 2.0, 0.35),
    "M_IntFabricNavy":    _t((0.10, 0.16, 0.42), "Fabric", 2.0, 0.35),
    "M_IntFabricWhite":   _t((0.97, 0.96, 0.93), "Fabric", 2.0, 0.3),
    "M_IntFabricPink":    _t((0.97, 0.66, 0.76), "Fabric", 2.0, 0.35),
    "M_IntFabricGreen":   _t((0.36, 0.64, 0.38), "Fabric", 2.0, 0.35),
    "M_IntFabricOrange":  _t((0.98, 0.58, 0.22), "Fabric", 2.0, 0.35),
    "M_IntFabricPurple":  _t((0.56, 0.38, 0.78), "Fabric", 2.0, 0.35),
    "M_IntFabricBeige":   _t((0.90, 0.82, 0.66), "Fabric", 2.0, 0.35),
    "M_IntGlassClear":    dict(kind="glass", color=(0.70, 0.85, 0.95), rough=0.02, opacity=0.18),
    "M_IntWater":         dict(kind="pool", color=(0.45, 0.78, 0.80), rough=0.05, ripple=0.3, wave_strength=0.3),
})

PLASTER_CREAM, PLASTER_WHITE, PLASTER_PEACH, PLASTER_SKY = ("M_IntPlasterCream", "M_IntPlasterWhite",
                                                            "M_IntPlasterPeach", "M_IntPlasterSky")
PLASTER_ROSE, PLASTER_YELLOW, PLASTER_MINT = "M_IntPlasterRose", "M_IntPlasterYellow", "M_IntPlasterMint"
CEIL, WOODFLOOR, TATAMI, TILE, MARBLEFLOOR = ("M_IntCeiling", "M_IntWoodFloor", "M_IntTatami", "M_IntTileWhite",
                                              "M_IntMarbleFloor")
TRIM_WHITE, TRIM_WOOD, TRIM_GOLD = "M_IntTrimWhite", "M_IntTrimWood", "M_IntTrimGold"
WOOD, WOOD_DARK, METAL, BLACK = "M_IntWood", "M_IntWoodDark", "M_IntMetal", "M_IntBlack"
GLOW, PANEL_LIGHT, SKY = "M_IntWarmGlow", "M_IntLightPanel", "M_IntWindowSky"
FABRICS = ("M_IntFabricRed", "M_IntFabricBlue", "M_IntFabricYellow", "M_IntFabricGreen", "M_IntFabricPink",
           "M_IntFabricOrange", "M_IntFabricPurple", "M_IntFabricWhite")
POSTERS = ("M_IntPoster1", "M_IntPoster2", "M_IntPoster3", "M_IntPoster4")


# ----------------------------------------------------------------------------- openings
class Door:
    """Doorway in a wall(): c = centre distance from p0 along the wall, w x h clear opening. style=None leaves
    an open doorway (arch / passage) without a door leaf."""

    def __init__(self, c, w=0.95, h=2.15, style="wood", double=False, mode=None, swing="auto", z0=0.0,
                 trim=None, trim_in=None):
        self.c, self.w, self.h, self.style, self.double = c, w, h, style, double
        self.mode, self.swing, self.z0, self.trim, self.trim_in = mode, swing, z0, trim, trim_in

    def opening(self):
        return dict(u=self.c, w=self.w, z0=self.z0, z1=self.z0 + self.h)


class Window:
    """Window opening (real hole + clear glass). z0/z1 relative to the wall base."""

    def __init__(self, c, w, z0, z1, glass="M_IntGlassClear", frame=None, mullions=1, transoms=0, sill=None):
        self.c, self.w, self.z0, self.z1, self.glass = c, w, z0, z1, glass
        self.frame, self.mullions, self.transoms, self.sill = frame, mullions, transoms, sill

    def opening(self):
        return dict(u=self.c, w=self.w, z0=self.z0, z1=self.z1)


def _frame2d(p0, p1):
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    return L, (ux, uy), (-uy, ux), math.degrees(math.atan2(dy, dx))


def wall(aset, mb, p0, p1, z0, h, thick, mat, inner=None, openings=(), trim=None, trim_in=None, base=None,
         base_h=0.12):
    """Wall with real openings. Door openings place automatic doors (centred in the thickness) and get
    architraves (trim outside, trim_in inside); windows get clear glass + frame. base: skirting board
    material on the inside face."""
    L, (ux, uy), (nx, ny), yaw = _frame2d(p0, p1)
    ops = []
    for o in openings:
        ops.append(o.opening())
    # glass is placed by us (centred) so the frame can sit on both faces
    mb.wall(p0, p1, z0, h, thick, mat, ops, inner_mat=inner or mat)
    for o in openings:
        cx, cy = p0[0] + ux * o.c + nx * thick / 2, p0[1] + uy * o.c + ny * thick / 2
        if isinstance(o, Door):
            if o.style:
                aset.door((cx, cy, z0 + o.z0), yaw, o.w, o.h, o.style, o.double, o.mode, o.swing)
            elif hasattr(aset, "openings"):
                aset.openings.append(((cx, cy, z0 + o.z0), yaw, o.w, o.h))
            with mb.at((p0[0], p0[1], z0), rot=yaw):
                _architrave(mb, o.c, o.z0, o.w, o.h, -0.0, -1, o.trim or trim)
                _architrave(mb, o.c, o.z0, o.w, o.h, thick, 1, o.trim_in or trim_in)
                # reveal lining (jambs + head) so the cut through the wall looks finished
                lm = o.trim_in or trim_in or inner or mat
                # 5 mm proud of the cut faces (inside the opening) so the two surfaces never z-fight
                mb.box((o.c - o.w / 2 + 0.0025, thick / 2, o.z0 + o.h / 2), (0.005, thick, o.h), lm)
                mb.box((o.c + o.w / 2 - 0.0025, thick / 2, o.z0 + o.h / 2), (0.005, thick, o.h), lm)
                mb.box((o.c, thick / 2, o.z0 + o.h - 0.0025), (o.w, thick, 0.005), lm)
        else:
            with mb.at((p0[0], p0[1], z0), rot=yaw):
                fr = o.frame or trim or "M_WindowFrame"
                cz = (o.z0 + o.z1) / 2
                mb.box((o.c, thick / 2, cz), (o.w, 0.03, o.z1 - o.z0), o.glass)
                fw = 0.06
                for s in (-1, 1):
                    mb.box((o.c + s * (o.w / 2 - fw / 2), thick / 2, cz), (fw, 0.09, o.z1 - o.z0), fr)
                mb.box((o.c, thick / 2, o.z1 - fw / 2), (o.w, 0.09, fw), fr)
                mb.box((o.c, thick / 2, o.z0 + fw / 2), (o.w, 0.09, fw), fr)
                for k in range(1, o.mullions + 1):
                    mb.box((o.c - o.w / 2 + o.w * k / (o.mullions + 1), thick / 2, cz), (0.045, 0.07, o.z1 - o.z0), fr)
                for k in range(1, o.transoms + 1):
                    mb.box((o.c, thick / 2, o.z0 + (o.z1 - o.z0) * k / (o.transoms + 1)), (o.w, 0.07, 0.045), fr)
                sm = o.sill or trim_in or fr
                # inside sill, top flush with the opening; it starts at the wall face (not 4 cm into the opening,
                # where its top z-fought with the opening's bottom face)
                mb.box((o.c, thick + 0.06, o.z0 - 0.025), (o.w + 0.16, 0.12, 0.05), sm)
    if base:
        _skirting(mb, p0, p1, z0, thick, base, base_h, [o for o in openings if isinstance(o, Door)])
    return yaw


def _architrave(mb, c, z0, w, h, y, side, mat, bw=0.09):
    if not mat:
        return
    yy = y + side * 0.015
    mb.box((c - w / 2 - bw / 2, yy, z0 + (h + bw) / 2), (bw, 0.03, h + bw), mat)
    mb.box((c + w / 2 + bw / 2, yy, z0 + (h + bw) / 2), (bw, 0.03, h + bw), mat)
    mb.box((c, yy, z0 + h + bw / 2), (w + 2 * bw, 0.03, bw), mat)


def _skirting(mb, p0, p1, z0, thick, mat, h, doors):
    L, (ux, uy), (nx, ny), yaw = _frame2d(p0, p1)
    cuts = sorted((d.c - d.w / 2 - 0.1, d.c + d.w / 2 + 0.1) for d in doors if d.z0 < 0.05)
    u = 0.0
    with mb.at((p0[0], p0[1], z0), rot=yaw):
        for a, b in cuts + [(L, L)]:
            if a - u > 0.05:
                mb.box(((u + a) / 2, thick + 0.012, h / 2), (a - u, 0.024, h), mat)
            u = max(u, b)


def shell(aset, mb, x0, y0, x1, y1, z0, h, thick, mat, inner=None, sides=None, trim=None, trim_in=None,
          base=None):
    """Four walls of an axis aligned block; the walls sit INSIDE the footprint. sides: dict 's','e','n','w' ->
    list of Door / Window with c given in WORLD coordinates (x for s/n, y for e/w)."""
    sides = sides or {}
    defs = {
        "s": ((x0, y0), (x1, y0), lambda v: v - x0),
        "e": ((x1, y0), (x1, y1), lambda v: v - y0),
        "n": ((x1, y1), (x0, y1), lambda v: x1 - v),
        "w": ((x0, y1), (x0, y0), lambda v: y1 - v),
    }
    for k, (p0, p1, conv) in defs.items():
        ops = []
        for o in sides.get(k, ()):
            o2 = _copy(o)
            o2.c = conv(o.c)
            ops.append(o2)
        wall(aset, mb, p0, p1, z0, h, thick, mat, inner, ops, trim, trim_in, base)


def _copy(o):
    n = object.__new__(type(o))
    n.__dict__.update(o.__dict__)
    return n


def slab(mb, x0, y0, x1, y1, z_top, thick, top, bottom=None, side=None, holes=()):
    """Floor / ceiling slab with rectangular holes (stairwells): split into a grid of cells."""
    xs = sorted({x0, x1, *[v for hh in holes for v in (hh[0], hh[2])]})
    ys = sorted({y0, y1, *[v for hh in holes for v in (hh[1], hh[3])]})
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if any(hh[0] < cx < hh[2] and hh[1] < cy < hh[3] for hh in holes):
                continue
            if xs[i + 1] - xs[i] < 1e-4 or ys[j + 1] - ys[j] < 1e-4:
                continue
            mb.box_mm((xs[i], ys[j], z_top - thick), (xs[i + 1], ys[j + 1], z_top), side or top,
                      mats={"+z": top, "-z": bottom or CEIL})
    for hh in holes:   # finished edges around the hole
        mb.box_mm((hh[0], hh[1], z_top - thick), (hh[2], hh[1] + 0.001, z_top), side or TRIM_WHITE, skip=("-y",))


def floor_planks(mb, x0, y0, x1, y1, z, mat=WOODFLOOR, seam="M_IntWoodDark", along="x", pitch=0.18):
    """Wooden floor surface with thin seams (cel look reads the boards from the lines)."""
    mb.box_mm((x0, y0, z - 0.03), (x1, y1, z), mat, skip=("-z",))
    if along == "x":
        n = int((y1 - y0) / pitch)
        for k in range(1, n):
            y = y0 + k * (y1 - y0) / n
            mb.box_mm((x0, y - 0.004, z), (x1, y + 0.004, z + 0.002), seam, skip=("-z",))
    else:
        n = int((x1 - x0) / pitch)
        for k in range(1, n):
            x = x0 + k * (x1 - x0) / n
            mb.box_mm((x - 0.004, y0, z), (x + 0.004, y1, z + 0.002), seam, skip=("-z",))


def tatami(mb, x0, y0, x1, y1, z, mat=TATAMI, edge="M_IntTatamiEdge", mat_w=0.9, mat_l=1.8):
    """Tatami mats laid in a simple pattern with dark cloth edges."""
    mb.box_mm((x0, y0, z - 0.04), (x1, y1, z), mat, skip=("-z",))
    nx = max(1, round((x1 - x0) / mat_l))
    ny = max(1, round((y1 - y0) / mat_w))
    for i in range(1, nx):
        x = x0 + (x1 - x0) * i / nx
        mb.box_mm((x - 0.015, y0, z), (x + 0.015, y1, z + 0.004), edge, skip=("-z",))
    for j in range(1, ny):
        y = y0 + (y1 - y0) * j / ny
        mb.box_mm((x0, y - 0.015, z), (x1, y + 0.015, z + 0.004), edge, skip=("-z",))


def rug(mb, x0, y0, x1, y1, z, mat, border=None, bw=0.12):
    mb.box_mm((x0, y0, z), (x1, y1, z + 0.012), mat, skip=("-z",))
    if border:
        for (a, b, c, d) in ((x0, y0, x1, y0 + bw), (x0, y1 - bw, x1, y1), (x0, y0, x0 + bw, y1), (x1 - bw, y0, x1, y1)):
            mb.box_mm((a, b, z + 0.012), (c, d, z + 0.016), border, skip=("-z",))


def ceiling(mb, x0, y0, x1, y1, z, mat=CEIL, cornice=None):
    mb.poly([(x0, y0, z), (x0, y1, z), (x1, y1, z), (x1, y0, z)], mat)
    if cornice:
        for (a, b) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            L, (ux, uy), (nx, ny), yaw = _frame2d(a, b)
            with mb.at((a[0], a[1], z), rot=yaw):
                mb.box((L / 2, 0.05, -0.05), (L, 0.1, 0.1), cornice)


def wainscot(mb, p0, p1, z0, h, mat, cap=None, gaps=()):
    """Panelling on the inside face of a wall (the wall surface is at p0->p1, room on the left)."""
    L, (ux, uy), (nx, ny), yaw = _frame2d(p0, p1)
    cuts = sorted(gaps)
    u = 0.0
    with mb.at((p0[0], p0[1], z0), rot=yaw):
        for a, b in cuts + [(L, L)]:
            if a - u > 0.05:
                # 18 mm boards: the 24 mm skirting stands proud of them; no faces against the wall / floor
                # (under a cap the boards stop at its underside: their ends do not share the cap's end faces)
                hb = h - 0.02 if cap else h
                mb.box(((u + a) / 2, 0.009, hb / 2), (a - u, 0.018, hb), mat, skip=("-y", "-z"))
                if cap:
                    mb.box(((u + a) / 2, 0.025, h), (a - u, 0.05, 0.04), cap, skip=("-y",))
            u = max(u, b)


# ----------------------------------------------------------------------------- circulation
def stairs(mb, x, y, z0, z1, yaw, width, mat=WOOD, riser=None, stringer=None, rail=None, run=0.28,
           rail_sides=(1,)):
    """Straight flight starting at (x, y, z0) (front edge centre), climbing along local +x to z1.
    Returns the top landing point (x, y, z1) in local space of the caller."""
    n = max(2, int(round((z1 - z0) / 0.18)))
    rise = (z1 - z0) / n
    with mb.at((x, y, z0), rot=yaw):
        for i in range(n):
            zt = rise * (i + 1)
            mb.box_mm((run * i, -width / 2, zt - 0.05), (run * (i + 1) + 0.02, width / 2, zt), mat)
            mb.box_mm((run * i, -width / 2, zt - rise), (run * i + 0.03, width / 2, zt - 0.05), riser or mat)
        L = run * n
        if stringer:
            for s in (-1, 1):
                mb.beam((0, s * (width / 2 + 0.03), -0.05), (L, s * (width / 2 + 0.03), z1 - z0 - 0.05), 0.06, 0.3,
                        stringer)
        else:   # closed underside (sloped soffit)
            mb.quad((L, -width / 2, z1 - z0 - 0.06), (0, -width / 2, 0.0 - 0.01), (0, width / 2, -0.01),
                    (L, width / 2, z1 - z0 - 0.06), riser or mat)
        if rail:
            for s in rail_sides:
                y = s * (width / 2 - 0.04)
                for k in range(0, n + 1, 2):
                    mb.box((run * k + 0.1, y, rise * (k + 1) + 0.45), (0.04, 0.04, 0.9), rail)
                mb.beam((0.05, y, rise + 0.95), (L, y, z1 - z0 + 0.95), 0.06, 0.05, rail)
    return run * n


def spiral_stairs(mb, cx, cy, z0, z1, r_in, r_out, a0=0.0, step_deg=20.0, mat=METAL, core=None, rail=None):
    """Spiral staircase around a central post, climbing CCW from angle a0 (deg)."""
    n = max(4, int(round((z1 - z0) / 0.19)))
    rise = (z1 - z0) / n
    if core:
        mb.cylinder((cx, cy, z0), r_in, z1 - z0 + 1.0, core, seg=12)
    for i in range(n):
        a = math.radians(a0 + step_deg * i)
        b = math.radians(a0 + step_deg * (i + 1) + 2.0)
        z = z0 + rise * (i + 1)
        pts = []
        for ang in (a, b):
            pts.append((cx + math.cos(ang) * r_in, cy + math.sin(ang) * r_in))
        for ang in (b, a):
            pts.append((cx + math.cos(ang) * r_out, cy + math.sin(ang) * r_out))
        pts_ccw = [pts[0], pts[3], pts[2], pts[1]]
        mb.prism(pts_ccw if _ccw(pts_ccw) else list(reversed(pts_ccw)), z - 0.06, z, mat)
        if rail:
            am = (a + b) / 2
            px, py = cx + math.cos(am) * (r_out - 0.05), cy + math.sin(am) * (r_out - 0.05)
            mb.box((px, py, z + 0.45), (0.035, 0.035, 0.9), rail)
            if i:
                ap = math.radians(a0 + step_deg * (i - 0.5) + 1.0)
                mb.beam((cx + math.cos(ap) * (r_out - 0.05), cy + math.sin(ap) * (r_out - 0.05), z - rise + 0.92),
                        (px, py, z + 0.92), 0.05, 0.05, rail)
    return a0 + step_deg * n


def _ccw(pts):
    a = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        a += x0 * y1 - x1 * y0
    return a > 0


def railing(mb, pts, z, h=1.0, mat=TRIM_WOOD, post=0.06, spacing=0.14, rail=0.07):
    for i in range(len(pts) - 1):
        (x0, y0), (x1, y1) = pts[i], pts[i + 1]
        L = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(L / spacing))
        for k in range(n + 1):
            t = k / n
            w = post if k in (0, n) else 0.025
            mb.box((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z + h / 2), (w, w, h), mat)
        mb.beam((x0, y0, z + h), (x1, y1, z + h), rail, rail * 0.8, mat)


# ----------------------------------------------------------------------------- light
def panel_light(aset, nc, x, y, z, w=1.2, d=0.3, intensity=3500.0, radius=8.0, color=(1.0, 0.96, 0.9),
                mat=PANEL_LIGHT, frame=TRIM_WHITE):
    """Flush ceiling light (classrooms, offices, corridors). z = ceiling height."""
    nc.box((x, y, z - 0.03), (w + 0.06, d + 0.06, 0.04), frame)
    nc.box((x, y, z - 0.055), (w, d, 0.012), mat)
    aset.light((x, y, z - 0.35), color, intensity, radius, night_only=False)


def pendant(aset, x, y, z, kind="lamp"):
    """Catalog fixture hung from the ceiling at height z (lights come with it)."""
    asset = {"lamp": "SM_Int_CeilingLamp", "chandelier": "SM_Int_Chandelier", "industrial": "SM_Int_IndustrialLamp",
             "fan": "SM_Int_CeilingFan"}[kind]
    aset.prop(asset, (x, y, z), 0.0)


def room_light(aset, x, y, z, intensity=3000.0, radius=8.0, color=(1.0, 0.9, 0.75)):
    aset.light((x, y, z), color, intensity, radius, night_only=False)


# ----------------------------------------------------------------------------- windows / walls decor
def curtains(nc, p0, p1, c, w, z0, z1, mat, inset=0.12, rod=TRIM_WOOD, open_frac=0.3, wall_thick=0.2):
    """Curtains on the inside of a window (window centre c along p0->p1)."""
    L, (ux, uy), (nx, ny), yaw = _frame2d(p0, p1)
    with nc.at((p0[0], p0[1], 0.0), rot=yaw):
        y = wall_thick + inset
        nc.box((c, y, z1 + 0.12), (w + 0.5, 0.03, 0.03), rod)
        cw = (w + 0.4) * open_frac
        for s in (-1, 1):
            cx = c + s * (w / 2 + 0.2 - cw / 2)
            for k in range(3):   # folds
                fx = cx - cw / 2 + cw * (k + 0.5) / 3
                nc.box((fx, y + (0.02 if k % 2 else -0.02), (z0 - 0.15 + z1 + 0.1) / 2), (cw / 3 + 0.01, 0.025,
                       z1 - z0 + 0.25), mat)


def fake_window(mb, nc, p0, p1, c, z0, w, h, frame=TRIM_WHITE, mat=SKY, curtain=None):
    """Bright sky panel in a frame on an inside wall face (rooms whose outside wall is solid)."""
    L, (ux, uy), (nx, ny), yaw = _frame2d(p0, p1)
    with nc.at((p0[0], p0[1], z0), rot=yaw):
        nc.box((c, 0.01, h / 2), (w, 0.02, h), mat)
    with mb.at((p0[0], p0[1], z0), rot=yaw):
        for s in (-1, 1):
            mb.box((c + s * (w / 2 + 0.04), 0.04, h / 2), (0.08, 0.08, h + 0.16), frame)
        mb.box((c, 0.04, h + 0.04), (w + 0.16, 0.08, 0.08), frame)
        mb.box((c, 0.08, -0.03), (w + 0.25, 0.16, 0.06), frame)
        mb.box((c, 0.04, h / 2), (0.05, 0.06, h), frame)
        mb.box((c, 0.04, h * 0.55), (w, 0.06, 0.05), frame)
    if curtain:
        curtains(nc, p0, p1, c, w, z0, z0 + h, curtain, wall_thick=0.0)


def poster(nc, aset, x, y, z, yaw, w, h, mat, text=None, text_color=(1, 1, 1), text_size=None):
    """Poster on a wall: (x, y) on the wall surface, yaw so that local -Y points INTO the room."""
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.006, 0), (w, 0.012, h), mat)
        nc.box((0, -0.004, 0), (w + 0.04, 0.008, h + 0.04), "M_IntPaper")
    if text:
        aset.text(text, wall_point(x, y, yaw, 0.02, z - (text_size or h * 0.18) * 0.5), yaw,
                  size=text_size or h * 0.18, color=text_color)


def wall_point(x, y, yaw, out, z):
    """Point `out` metres in front of a wall (towards local -Y) at height z."""
    a = math.radians(yaw)
    return (x + math.sin(a) * out, y - math.cos(a) * out, z)


def blackboard(mb, nc, aset, x, y, z, yaw, w=4.0, h=1.2, lines=(), frame=WOOD, tray=True, size=0.13):
    """Green chalkboard with chalk writing (text sockets). (x, y) on the wall, local -Y into the room."""
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, -0.03, h / 2), (w, 0.06, h), "M_IntChalkboard")
        for s in (-1, 1):
            mb.box((s * (w / 2 + 0.03), -0.04, h / 2), (0.06, 0.08, h + 0.12), frame)
        mb.box((0, -0.04, h + 0.03), (w + 0.12, 0.08, 0.06), frame)
        if tray:
            mb.box((0, -0.1, -0.02), (w, 0.14, 0.04), frame)
            for k in range(4):
                nc.box((-w * 0.3 + k * 0.12, -0.12, 0.01), (0.08, 0.015, 0.015), "M_IntPaper")
    for i, line in enumerate(lines):
        aset.text(line, wall_point(x, y, yaw, 0.065, z + h - 0.25 - i * size * 1.6), yaw, size=size,
                  color=(0.96, 0.96, 0.9))


def bulletin(nc, aset, x, y, z, yaw, w=1.4, h=0.9, title=None, rng_seed=1):
    import random
    rnd = random.Random(rng_seed)
    with nc.at((x, y, z), rot=yaw):
        nc.box((0, -0.015, h / 2), (w, 0.03, h), "M_IntCork")
        nc.box((0, -0.02, h / 2), (w + 0.08, 0.025, h + 0.08), "M_IntTrimWood")
        for k in range(6):
            pw, ph = rnd.uniform(0.18, 0.32), rnd.uniform(0.2, 0.3)
            px = rnd.uniform(-w / 2 + pw / 2 + 0.05, w / 2 - pw / 2 - 0.05)
            pz = rnd.uniform(ph / 2 + 0.05, h - ph / 2 - 0.12)
            # (each sheet 1.5 mm in front of the one before: overlapping sheets on one plane z-fought)
            nc.box((px, -0.036 - 0.0015 * k, pz), (pw, 0.004, ph), rnd.choice(("M_IntPaper",) * 3 + POSTERS))
            nc.box((px, -0.042 - 0.0015 * k, pz + ph / 2 - 0.03), (0.02, 0.006, 0.02), "M_IntFabricRed")
    if title:
        aset.text(title, wall_point(x, y, yaw, 0.05, z + h - 0.08), yaw, size=0.07, color=(0.2, 0.12, 0.06))


def nameplate(mb, aset, x, y, z, yaw, text, mat=TRIM_WHITE, color=(0.15, 0.1, 0.08), w=0.36, h=0.13):
    """Small sign next to a door (room numbers, 'NURSE', ...). (x, y) on the wall face, -Y outwards."""
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, -0.01, 0), (w, 0.02, h), mat)
    aset.text(text, wall_point(x, y, yaw, 0.025, z - h * 0.18), yaw, size=h * 0.55, color=color)


# ----------------------------------------------------------------------------- GX furniture (procedural)
def _at(mb, x, y, z, yaw):
    return mb.at((x, y, z), rot=yaw)


def bunk_bed(mb, nc, x, y, yaw, levels=3, blankets=("M_IntFabricRed", "M_IntFabricYellow", "M_IntFabricBlue"),
             frame=WOOD, length=2.0, width=0.95, gap=0.82, ladder=True):
    """Stacked bunks (the Slifer triple bunk). Footprint: length along local x, width along y; origin at the
    centre of the footprint on the floor; the ladder is on the local -y side at +x end."""
    with _at(mb, x, y, 0.0, yaw), _at(nc, x, y, 0.0, yaw):
        top = 0.25 + gap * levels + 0.25
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * (length / 2 - 0.04), sy * (width / 2 - 0.04), top / 2), (0.08, 0.08, top), frame)
        for i in range(levels):
            z = 0.25 + gap * i
            mb.box((0, 0, z), (length, width, 0.06), frame)                                   # deck
            mb.box((0, width / 2 - 0.04, z + 0.12), (length, 0.05, 0.18), frame)              # wall-side rail
            for sx in (-1, 1):
                mb.box((sx * (length / 2 - 0.04), 0, z + 0.25), (0.05, width, 0.4), frame)   # head/foot boards
            if i > 0:
                mb.box((0.15, -(width / 2 - 0.04), z + 0.2), (length - 0.5, 0.05, 0.1), frame)   # guard rail
            bl = blankets[i % len(blankets)]
            mb.box((0.05, 0, z + 0.1), (length - 0.15, width - 0.12, 0.12), "M_IntFabricWhite")   # mattress
            nc.box((0.25, 0, z + 0.2), (length - 0.6, width - 0.08, 0.09), bl)                    # blanket
            nc.box((-(length / 2 - 0.3), 0, z + 0.21), (0.35, width - 0.3, 0.1), "M_IntFabricWhite")  # pillow
        if ladder:
            lx = length / 2 - 0.3
            ly = -(width / 2 + 0.04)
            for s in (-1, 1):
                mb.box((lx + s * 0.2, ly, top / 2 - 0.1), (0.05, 0.05, top - 0.2), frame)
            k = 0
            z = 0.35
            while z < top - 0.3:
                mb.box((lx, ly, z), (0.4, 0.04, 0.04), frame)
                z += 0.3
                k += 1


def single_bed(mb, nc, x, y, yaw, blanket="M_IntFabricBlue", frame=WOOD, length=2.0, width=1.0, head=0.9):
    """Bed with headboard at local -x end. origin at footprint centre."""
    with _at(mb, x, y, 0.0, yaw), _at(nc, x, y, 0.0, yaw):
        mb.box((0, 0, 0.18), (length, width, 0.3), frame)
        mb.box((-(length / 2 - 0.03), 0, head / 2), (0.06, width + 0.04, head), frame)
        mb.box((length / 2 - 0.03, 0, 0.3), (0.06, width + 0.04, 0.6), frame)
        mb.box((0, 0, 0.42), (length - 0.1, width - 0.06, 0.18), "M_IntFabricWhite")
        nc.box((0.25, 0, 0.53), (length - 0.55, width + 0.02, 0.07), blanket)
        nc.box((0.25, 0, 0.36), (length - 0.55, width + 0.04, 0.3), blanket)
        nc.box((-(length / 2 - 0.3), 0, 0.56), (0.35, width - 0.3, 0.12), "M_IntFabricWhite")


def futon(nc, x, y, yaw, mat="M_IntFabricBlue"):
    with _at(nc, x, y, 0.0, yaw):
        nc.box((0, 0, 0.06), (2.0, 0.95, 0.12), "M_IntFabricWhite")
        nc.box((0.25, 0, 0.14), (1.4, 0.98, 0.07), mat)
        nc.box((-0.8, 0, 0.16), (0.3, 0.55, 0.1), "M_IntFabricWhite")


def kotatsu(mb, nc, x, y, yaw=0.0, quilt="M_IntFabricOrange", w=0.9, d=0.9):
    """Low heated table with a quilt and cushions (zabuton) around it."""
    with _at(mb, x, y, 0.0, yaw):
        mb.box((0, 0, 0.38), (w + 0.1, d + 0.1, 0.03), WOOD)
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * (w / 2 - 0.05), sy * (d / 2 - 0.05), 0.18), (0.06, 0.06, 0.36), WOOD)
    with _at(nc, x, y, 0.0, yaw):
        nc.box((0, 0, 0.36), (w + 0.5, d + 0.5, 0.04), quilt)
        for sx in (-1, 1):
            nc.box((sx * (w / 2 + 0.25), 0, 0.18), (0.04, d + 0.5, 0.36), quilt)
        for sy in (-1, 1):
            nc.box((0, sy * (d / 2 + 0.25), 0.18), (w + 0.5, 0.04, 0.36), quilt)
        # (5 cm clear of the quilt's skirt: touching it, the cushions merged with the quilt into one rotated
        # collision box reaching 1.5 m out - dai/collision.py; on their own they are flat and walkable)
        for (cx, cy) in ((0, -(d / 2 + 0.6)), (0, d / 2 + 0.6), (-(w / 2 + 0.6), 0)):
            nc.box((cx, cy, 0.04), (0.55, 0.55, 0.08), "M_IntFabricRed")
        nc.cylinder((0.15, 0.1, 0.395), 0.12, 0.012, "M_IntPaper", seg=10)
        nc.sphere((0.15, 0.1, 0.44), 0.05, "M_IntFabricOrange", seg=8, rings=6)   # mikan
        nc.sphere((0.25, 0.05, 0.44), 0.05, "M_IntFabricOrange", seg=8, rings=6)


def desk(mb, nc, x, y, yaw, w=1.1, d=0.6, top=WOOD, legs=WOOD_DARK, hutch=True, clutter=True, rng_seed=0):
    """Study desk, user side local -Y, back against a wall at +Y. Optional shelf hutch with books."""
    import random
    rnd = random.Random(rng_seed)
    with _at(mb, x, y, 0.0, yaw):
        mb.box((0, 0, 0.74), (w, d, 0.04), top)
        mb.box((w / 2 - 0.22, 0, 0.36), (0.42, d - 0.04, 0.72), legs)        # drawer pedestal
        for k in range(3):
            mb.box((w / 2 - 0.22, -d / 2 + 0.005, 0.12 + k * 0.22), (0.38, 0.01, 0.18), top)
        mb.box((-(w / 2 - 0.03), 0, 0.36), (0.04, d - 0.04, 0.72), legs)
        if hutch:
            mb.box((0, d / 2 - 0.12, 1.2), (w, 0.24, 0.03), top)
            for s in (-1, 1):
                mb.box((s * (w / 2 - 0.015), d / 2 - 0.12, 0.98), (0.03, 0.24, 0.48), top)
    with _at(nc, x, y, 0.0, yaw):
        if hutch:
            bx = -w / 2 + 0.08
            while bx < w / 2 - 0.1:
                bw = rnd.uniform(0.03, 0.06)
                nc.box((bx + bw / 2, d / 2 - 0.12, 1.215 + 0.11), (bw, 0.18, rnd.uniform(0.17, 0.24)),
                       rnd.choice(FABRICS[:7]))
                bx += bw + 0.005
        if clutter:
            nc.box((-0.15, -0.05, 0.765), (0.3, 0.22, 0.01), "M_IntPaper")
            nc.box((0.1, 0.0, 0.77), (0.24, 0.17, 0.02), rnd.choice(POSTERS))
            nc.cylinder((-0.4, 0.12, 0.76), 0.04, 0.1, rnd.choice(FABRICS), seg=8)


def wardrobe(mb, x, y, yaw, w=1.0, d=0.6, h=2.0, mat=WOOD, handle=METAL):
    """Built-in style wardrobe, doors at local -Y."""
    with _at(mb, x, y, 0.0, yaw):
        mb.box((0, 0, h / 2), (w, d, h), mat)
        mb.box((0, -d / 2 - 0.005, h / 2), (0.01, 0.01, h - 0.1), WOOD_DARK)
        for s in (-1, 1):
            mb.box((s * 0.06, -d / 2 - 0.02, h * 0.5), (0.025, 0.03, 0.25), handle)


def bookcase(mb, nc, x, y, yaw, w=1.0, d=0.32, h=2.0, shelves=5, mat=WOOD, rng_seed=0, fill=0.85):
    """Open bookcase stuffed with colourful books; back at local +Y."""
    import random
    rnd = random.Random(rng_seed)
    with _at(mb, x, y, 0.0, yaw):
        mb.box((0, d / 2 - 0.01, h / 2), (w, 0.02, h), mat)
        for s in (-1, 1):
            mb.box((s * (w / 2 - 0.015), 0, h / 2), (0.03, d, h), mat)
        for k in range(shelves + 1):       # boards between the sides, 1 cm behind their front edge
            z = 0.06 + (h - 0.08) * k / shelves
            mb.box((0, -0.005, z), (w - 0.06, d - 0.03, 0.03), mat)
    with _at(nc, x, y, 0.0, yaw):
        for k in range(shelves):
            z = 0.075 + (h - 0.08) * k / shelves
            sh = (h - 0.08) / shelves - 0.06
            bx = -w / 2 + 0.05
            while bx < w / 2 - 0.08:
                if rnd.random() > fill:
                    bx += 0.12
                    continue
                bw = rnd.uniform(0.025, 0.055)
                bh = min(sh, rnd.uniform(0.18, 0.3))
                nc.box((bx + bw / 2, 0.0, z + bh / 2), (bw, d * 0.75, bh), rnd.choice(FABRICS[:7] + (WOOD_DARK,)))
                bx += bw + 0.004


def counter(mb, x0, y0, x1, y1, h=0.95, body=WOOD, top="M_IntTrimWhite", kick=WOOD_DARK):
    mb.box_mm((x0, y0, 0.0), (x1, y1, 0.1), kick)
    mb.box_mm((x0 + 0.03, y0 + 0.03, 0.1), (x1 - 0.03, y1 - 0.03, h - 0.04), body)
    mb.box_mm((x0 - 0.03, y0 - 0.03, h - 0.04), (x1 + 0.03, y1 + 0.03, h), top)


def kitchen_run(mb, nc, x0, y, x1, depth=0.62, against="+y", body="M_IntTrimWhite", top="M_IntMetal",
                upper=True):
    """Fitted kitchen along a wall: base units, worktop, sink, hob, upper cabinets, hood."""
    s = 1 if against == "+y" else -1
    yb = y - s * depth
    lo, hi = min(y, yb), max(y, yb)
    counter(mb, x0, lo, x1, hi, 0.9, body, top)
    n = max(1, int((x1 - x0) / 0.6))
    for k in range(n):
        cx = x0 + (x1 - x0) * (k + 0.5) / n
        nc.box((cx, yb - s * 0.012, 0.5), (0.56, 0.01, 0.7), body)
        nc.box((cx, yb - s * 0.03, 0.78), (0.12, 0.02, 0.025), METAL)
    sx = x0 + (x1 - x0) * 0.3
    mb.box((sx, (lo + hi) / 2, 0.88), (0.6, depth * 0.6, 0.05), "M_IntSteelBlue")
    nc.cylinder((sx, hi - 0.08 if s > 0 else lo + 0.08, 0.9), 0.02, 0.3, METAL, seg=8)
    hx = x0 + (x1 - x0) * 0.72
    for dx in (-0.12, 0.12):
        for dy in (-0.1, 0.1):
            nc.cylinder((hx + dx, (lo + hi) / 2 + dy, 0.9), 0.08, 0.012, BLACK, seg=12)
    if upper:
        ul, uh = (y - s * 0.35, y) if s > 0 else (y, y + 0.35)
        mb.box_mm((x0, min(ul, uh), 1.5), (x1, max(ul, uh), 2.2), body)
        mb.box_mm((hx - 0.35, min(ul, uh) - s * 0.15, 1.45), (hx + 0.35, max(ul, uh), 1.6), METAL)


def lockers(mb, nc, aset, x, y, yaw, n=6, w=0.4, d=0.45, h=1.85, mat="M_IntSteelBlue", label0=None):
    """Row of steel lockers along local x, doors facing -Y. origin = centre of the row on the floor."""
    with _at(mb, x, y, 0.0, yaw):
        mb.box((0, 0, h / 2 + 0.05), (n * w, d, h), mat)
        mb.box((0, 0, 0.025), (n * w, d - 0.05, 0.05), BLACK)
    with _at(nc, x, y, 0.0, yaw):
        for i in range(n):
            cx = -n * w / 2 + w * (i + 0.5)
            nc.box((cx + w / 2, -d / 2 - 0.002, h / 2 + 0.05), (0.008, 0.005, h), BLACK)
            for k in range(4):
                nc.box((cx, -d / 2 - 0.004, h - 0.15 - k * 0.04), (w * 0.5, 0.005, 0.012), BLACK)
            nc.box((cx + w * 0.3, -d / 2 - 0.02, h * 0.55), (0.03, 0.03, 0.12), METAL)


def lecture_tiers(mb, nc, aset, cx, cy, z0, r0, rows, depth, rise, a0, a1, desk_mat=WOOD, seat_mat="M_IntFabricBlue",
                  step_mat="M_IntWoodFloor", aisle_deg=()):
    """Curved, stepped lecture-hall seating (the GX classroom): concentric tiers facing the centre
    (cx, cy), from radius r0 outwards, angles a0..a1 (deg, CCW). Each tier: platform + curved desk."""
    seg_deg = 6.0
    for i in range(rows):
        r_in, r_out = r0 + i * depth, r0 + (i + 1) * depth
        zt = z0 + rise * (i + 1)
        n = max(2, int((a1 - a0) / seg_deg))
        for k in range(n):
            aa = math.radians(a0 + (a1 - a0) * k / n)
            bb = math.radians(a0 + (a1 - a0) * (k + 1) / n)
            pts = [(cx + math.cos(aa) * r_in, cy + math.sin(aa) * r_in), (cx + math.cos(bb) * r_in, cy + math.sin(bb) * r_in),
                   (cx + math.cos(bb) * r_out, cy + math.sin(bb) * r_out), (cx + math.cos(aa) * r_out, cy + math.sin(aa) * r_out)]
            pts = pts if _ccw(pts) else list(reversed(pts))
            mb.prism(pts, z0 - 0.05, zt, step_mat, top_mat=step_mat)
            mid = (a0 + (a1 - a0) * (k + 0.5) / n)
            if any(abs(mid - a) < 4.0 for a in aisle_deg):
                continue
            # desk on the inner edge of the NEXT tier up (faces the centre), seats behind it
            if i < rows - 1:
                rd0, rd1 = r_out + 0.05, r_out + 0.45
                zd = zt + rise + 0.72
                dp = [(cx + math.cos(aa) * rd0, cy + math.sin(aa) * rd0), (cx + math.cos(bb) * rd0, cy + math.sin(bb) * rd0),
                      (cx + math.cos(bb) * rd1, cy + math.sin(bb) * rd1), (cx + math.cos(aa) * rd1, cy + math.sin(aa) * rd1)]
                dp = dp if _ccw(dp) else list(reversed(dp))
                mb.prism(dp, zd - 0.04, zd, desk_mat)
                # modesty panel (front of the desk, seen from below)
                fp = [(cx + math.cos(aa) * rd0, cy + math.sin(aa) * rd0), (cx + math.cos(bb) * rd0, cy + math.sin(bb) * rd0),
                      (cx + math.cos(bb) * (rd0 + 0.03), cy + math.sin(bb) * (rd0 + 0.03)),
                      (cx + math.cos(aa) * (rd0 + 0.03), cy + math.sin(aa) * (rd0 + 0.03))]
                fp = fp if _ccw(fp) else list(reversed(fp))
                mb.prism(fp, zt + rise, zd - 0.04, "M_IntWoodDark")
                # bench seat
                rs0, rs1 = r_out + 0.75, r_out + 1.15
                sp = [(cx + math.cos(aa) * rs0, cy + math.sin(aa) * rs0), (cx + math.cos(bb) * rs0, cy + math.sin(bb) * rs0),
                      (cx + math.cos(bb) * rs1, cy + math.sin(bb) * rs1), (cx + math.cos(aa) * rs1, cy + math.sin(aa) * rs1)]
                sp = sp if _ccw(sp) else list(reversed(sp))
                mb.prism(sp, zt + rise + 0.4, zt + rise + 0.46, seat_mat)
                mb.prism(sp, zt + rise, zt + rise + 0.4, "M_IntWoodDark")


def sofa_set(aset, x, y, yaw, table=True, chairs=True, sofa="SM_Int_Sofa", rug_mb=None, rug_mat=None, z=0.0):
    """Sofa facing local -Y at (x, y, z), coffee table and two armchairs in front, turned towards the table."""
    def P(dx, dy):
        a = math.radians(yaw)
        return (x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a))
    px, py = P(0, 0)
    aset.prop(sofa, (px, py, z), yaw)
    if table:
        tx, ty = P(0, -1.3)
        aset.prop("SM_Int_CoffeeTable", (tx, ty, z), yaw)
    if chairs:
        for s in (-1, 1):
            cx, cy = P(s * 1.7, -1.4)
            aset.prop("SM_Int_Armchair", (cx, cy, z), yaw + 180 + s * 70)
    if rug_mb is not None and rug_mat:
        cx, cy = P(0, -1.2)
        rug(rug_mb, cx - 1.9, cy - 1.3, cx + 1.9, cy + 1.3, z, rug_mat, "M_IntTrimGold")


def dining_table(aset, x, y, yaw, chairs=6, table="SM_Int_Table", chair="SM_Int_WoodChair", length=1.8, side=0.55,
                 z=0.0):
    """Table (long side along local x) at floor height z with chairs on both long sides (+ one end when chairs
    is odd), every chair facing the table."""
    a = math.radians(yaw)

    def P(dx, dy):
        return (x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a))
    aset.prop(table, (x, y, z), yaw)
    per = chairs // 2
    for i in range(per):
        dx = -length / 2 + length * (i + 0.5) / per
        for s in (-1, 1):
            px, py = P(dx, s * side)
            aset.prop(chair, (px, py, z), yaw + (180 if s < 0 else 0))
    if chairs % 2:
        px, py = P(length / 2 + 0.45, 0)
        aset.prop(chair, (px, py, z), yaw - 90)


def fireplace(mb, nc, aset, x, y, yaw, w=1.6, h=1.3, mat="M_IntMarbleFloor", trim=TRIM_GOLD, z=0.0):
    """Fireplace against a wall (back at +Y local), glowing embers + warm light. Geometry is built at z = 0 of
    the builders' current frame (wrap in mb.at for upper floors); z lifts the light socket to match."""
    with _at(mb, x, y, 0.0, yaw):
        mb.box((0, 0.15, h / 2), (w, 0.3, h), mat)
        mb.box((0, 0.0, h + 0.05), (w + 0.3, 0.45, 0.1), mat)
        mb.box((0, -0.25, 0.05), (w + 0.4, 0.5, 0.1), mat)
        mb.box((0, -0.01, h * 0.42), (w * 0.55, 0.04, h * 0.62), BLACK)
        mb.box((0, -0.02, h * 0.75), (w * 0.62, 0.05, 0.06), trim)
    with _at(nc, x, y, 0.0, yaw):
        for k in range(3):
            nc.box((-0.2 + k * 0.2, -0.05, 0.16), (0.14, 0.4, 0.08), WOOD_DARK)
        nc.box((0, -0.06, 0.25), (w * 0.4, 0.05, 0.22), "M_IntFire")
    lx, ly, _ = wall_point(x, y, yaw, 0.6, 0.0)
    aset.light((lx, ly, z + 0.5), (1.0, 0.55, 0.25), 2500.0, 6.0, night_only=False)


def piano(mb, nc, x, y, yaw, mat=BLACK):
    """Grand piano (keyboard towards local -Y)."""
    with _at(mb, x, y, 0.0, yaw):
        body = [(-0.75, -0.7), (0.75, -0.7), (0.75, 0.2), (0.45, 0.9), (0.0, 1.15), (-0.55, 1.0), (-0.75, 0.6)]
        mb.prism(body, 0.62, 1.0, mat)
        for (px, py) in ((-0.65, -0.55), (0.65, -0.55), (0.0, 0.95)):
            mb.box((px, py, 0.31), (0.1, 0.1, 0.62), mat)
        mb.box((0, -0.78, 0.86), (1.45, 0.18, 0.08), mat)
        mb.box((0, -0.78, 0.905), (1.35, 0.15, 0.01), "M_IntTrimWhite")
        mb.box((0, -1.25, 0.25), (0.8, 0.38, 0.5), mat)              # bench
    with _at(nc, x, y, 0.0, yaw):
        for k in range(18):
            nc.box((-0.6 + k * 0.07, -0.77, 0.915), (0.025, 0.08, 0.012), BLACK)
        nc.box((0, -0.62, 1.12), (0.5, 0.02, 0.24), "M_IntPaper")


def toilet_room(mb, x0, y0, x1, y1, tile="M_IntTileBlue"):
    """Small WC: tiled floor, toilet and a wash basin (dressing only)."""
    mb.box_mm((x0, y0, 0.0), (x1, y1, 0.015), tile, skip=("-z",))
    cx = (x0 + x1) / 2
    mb.box((cx, y1 - 0.35, 0.2), (0.38, 0.5, 0.4), "M_IntTrimWhite")
    mb.box((cx, y1 - 0.1, 0.6), (0.4, 0.18, 0.4), "M_IntTrimWhite")
    mb.box((x0 + 0.3, (y0 + y1) / 2, 0.82), (0.4, 0.45, 0.12), "M_IntTrimWhite")


def bath_tub(mb, x, y, yaw, l=1.6, w=0.75, water=None):
    with _at(mb, x, y, 0.0, yaw):
        mb.box((0, 0, 0.27), (l, w, 0.54), "M_IntTrimWhite")
        if water:
            mb.box((0, 0, 0.45), (l - 0.12, w - 0.12, 0.02), water)


def plant_corner(aset, x, y, big=True, z=0.0):
    aset.prop("SM_Int_PottedPlantB" if big else "SM_Int_PottedPlant", (x, y, z), (x * 53 + y * 31) % 360)


def camera(aset, label, pos, target, lens=18.0):
    """Interior preview camera (Tools/preview_asset.py <module> --views inside)."""
    aset.special("camera", pos, target=target, lens=lens, label=label)
