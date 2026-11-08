"""
Abandoned Dorm - the old "Special Dorm" deep in the eastern jungle.

A once-grand three storey stone dormitory (40 x 18 m) with a central square
clock tower, now rotting: holed slate roof with exposed rafters, boarded and
shuttered windows, crooked chimneys, ivy, a sagging porch and a walkable,
creepy entrance hall behind the front door.

Walk-in interiors (ground storey hollowed out, upper storeys stay solid):
  entrance hall (two storeys, broken grand staircase - someone laid planks over the gap - and a gallery),
  west wing: the dusty LIBRARY (toppled bookcases, cold fireplace, reading table),
  east wing: the PORTRAIT SALON (dust-sheeted furniture, grand piano, staring portraits),
  behind the hall: the RITUAL ROOM with a chalk-drawn shadow duel field (also reached by the back door),
  above it (through the gallery door): the old DORM ROOM with iron beds and a "missing" board.

Local space: origin = pad centre at ground level, front (door) faces -Y.
The forest trail arrives at about (0, -55); the gate sits at (0, -38).
"""

import math
import random

from . import AssetSet
from . import with_travel
from . import interior as K
from . import detail as DT
from .. import palette

palette.register({
    "M_OldStoneTrim":   dict(kind="opaque", color=(0.43, 0.42, 0.44), rough=0.9, detail="Concrete", tiling=0.5),
    "M_DarkVoid":       dict(kind="opaque", color=(0.012, 0.010, 0.016), rough=1.0, detail=None),
    "M_DarkWallpaper":  dict(kind="opaque", color=(0.24, 0.17, 0.27), rough=0.95, detail="Grunge", tiling=0.5),
    "M_TarnishedGold":  dict(kind="opaque", color=(0.46, 0.36, 0.17), rough=0.45, metallic=0.8, detail="Grunge", tiling=1.0),
    "M_PortraitCanvas": dict(kind="opaque", color=(0.17, 0.11, 0.15), rough=0.9, detail="Grunge", tiling=1.0),
    "M_PortraitFace":   dict(kind="opaque", color=(0.46, 0.40, 0.42), rough=0.9, detail=None),
    "M_GhostGlow":      dict(kind="emissive", color=(0.62, 0.42, 1.00), strength=8.0),
    "M_RottenCurtain":  dict(kind="foliage", color=(0.17, 0.05, 0.09), rough=0.95, detail=None),
    # interiors
    "M_LibWallpaper":   dict(kind="opaque", color=(0.17, 0.24, 0.19), rough=0.95, detail="Grunge", tiling=0.5),
    "M_SalonWallpaper": dict(kind="opaque", color=(0.33, 0.11, 0.15), rough=0.95, detail="Grunge", tiling=0.5),
    "M_FadedWallpaper": dict(kind="opaque", color=(0.46, 0.25, 0.27), rough=0.95, detail="Grunge", tiling=0.5),
    "M_RitualWall":     dict(kind="opaque", color=(0.19, 0.08, 0.09), rough=0.95, detail="Grunge", tiling=0.5),
    "M_DustSheet":      K._t((0.84, 0.83, 0.79), "Fabric", 1.5, 0.35),
    "M_Cobweb":         K._t((0.86, 0.86, 0.90)),
    "M_CobwebVeil":     dict(kind="glass", color=(0.90, 0.90, 0.94), rough=0.9, opacity=0.12, detail=None),
    "M_OldBookRed":     K._t((0.45, 0.13, 0.12)),
    "M_OldBookGreen":   K._t((0.20, 0.32, 0.22)),
    "M_OldBookBrown":   K._t((0.42, 0.28, 0.16)),
    "M_OldBookBlue":    K._t((0.18, 0.22, 0.38)),
    "M_OldPaper":       K._t((0.80, 0.74, 0.58)),
    "M_CandleWax":      K._t((0.93, 0.89, 0.76)),
    "M_CandleFlame":    dict(kind="emissive", color=(1.00, 0.70, 0.32), strength=9.0),
    "M_ChalkGlow":      dict(kind="emissive", color=(0.86, 0.80, 1.00), strength=1.6),
    "M_MoonSlit":       dict(kind="emissive", color=(0.42, 0.52, 0.85), strength=0.9),
    # first floor + tower (architecture names end in Wall / Ceiling so the detail audit counts them as bare)
    "M_RuinWall":         dict(kind="opaque", color=(0.40, 0.31, 0.30), rough=0.95, detail="Grunge", tiling=0.5),
    "M_RuinCorridorWall": dict(kind="opaque", color=(0.22, 0.27, 0.24), rough=0.95, detail="Grunge", tiling=0.5),
    "M_RuinTileWall":     dict(kind="opaque", color=(0.72, 0.74, 0.70), rough=0.5, detail="FloorTiles", tiling=1.0),
    "M_RuinCorridorPatch": dict(kind="opaque", color=(0.31, 0.37, 0.32), rough=0.95, detail="Grunge", tiling=0.5),
    "M_RuinCeiling":      dict(kind="opaque", color=(0.55, 0.52, 0.47), rough=0.95, detail="Grunge", tiling=0.5),
    "M_PeelPlaster":      K._t((0.74, 0.69, 0.60), "Plaster", 0.5, 0.35),
    "M_WaterStain":       K._t((0.36, 0.29, 0.21)),
    "M_MurkyWater":       dict(kind="water", color=(0.20, 0.24, 0.16), rough=0.1),
    "M_BirdMess":         K._t((0.90, 0.89, 0.84)),
    "M_OldBrass":         dict(kind="opaque", color=(0.55, 0.42, 0.20), rough=0.4, metallic=0.85, detail="Grunge", tiling=1.0),
})

STONE = "M_OldStone"
TRIM = "M_OldStoneTrim"
WALLP = "M_DarkWallpaper"
ROT = "M_RottenWood"
BOARD = "M_Boards"
RUST = "M_RustMetal"
VOID = "M_DarkVoid"

# ---------------------------------------------------------------- dimensions
FL = 0.6                      # ground floor level (plinth top)
EAVE = 11.4                   # wall top
ROOF_Z = 11.75                # roof underside at the eave line
PITCH = 30.0
TAN = math.tan(math.radians(PITCH))
COS = math.cos(math.radians(PITCH))
X0, X1, Y0, Y1 = -20.0, 20.0, -8.0, 10.0
EAVE_YF, EAVE_YB, RIDGE_Y = -8.6, 10.6, 1.0
RUN = RIDGE_Y - EAVE_YF
RIDGE_Z = ROOF_Z + RUN * TAN
VERGE = 0.6
TX, TY0, TY1, TTOP = 4.6, -11.0, -2.0, 21.5     # tower (outer)
HX, HY0, HY1, HZ1 = 4.0, -10.4, 4.0, 7.8        # entrance hall cavity
GAL_Y, GAL_Z = 1.6, 4.2                          # gallery front edge / floor

FLOOR_BANDS = (4.4, 7.85)
CZ1 = 3.95                    # ceiling of the ground-storey rooms (underside of the first floor slab)
BED_Z, BED_TOP = GAL_Z, 7.5   # dorm room above the ritual room (gallery level)
WT = 0.6                      # stone wall thickness
LIB = (-12.0, -7.4, -4.6, 4.0)   # library interior (x0, y0, x1, y1)
SAL = (4.6, -7.4, 12.0, 4.0)     # portrait salon interior
RIT = (-4.0, 4.6, 4.0, 9.4)      # ritual room / dorm room interior
SDY, SDW, SDH = -2.6, 1.2, 2.4   # side doors hall -> library / salon (centre y, width, height)
BACK_DOORS = (-2.7, 2.7)         # hall -> ritual room doorways (x), 1.3 x 2.5
FZ = FL + 0.01                   # finished floor of the ground-storey rooms
RITW = "M_RitualWall"
OLD_BOOKS = ("M_OldBookRed", "M_OldBookGreen", "M_OldBookBrown", "M_OldBookBlue", "M_DarkWood", "M_OldPaper")
WIN_ROWS = ((1.5, 2.2), (5.0, 2.0), (8.6, 1.8))  # (sill z, height)


# ---------------------------------------------------------------- helpers
def rbox(mb, center, size, mat, yaw=0.0, pitch=0.0, roll=0.0, mats=None):
    with mb.at(center, rot=yaw, rot_y=pitch, rot_x=roll):
        mb.box((0, 0, 0), size, mat, mats=mats)


def leaf_card(mb, center, size, mat, rng, yaw=0.0):
    """Irregular hexagonal leaf cluster facing local -Y."""
    s = size / 2
    with mb.at(center, rot=yaw, rot_y=rng.uniform(0, 60), rot_x=rng.uniform(-25, 25)):
        pts = []
        for i in range(6):
            a = math.tau * i / 6 + 0.3
            r = s * rng.uniform(0.75, 1.1)
            pts.append((math.cos(a) * r, 0.0, math.sin(a) * r))
        # CCW seen from -Y means CCW in (x, z) -> reverse of the angle order in (x, z)? angle grows x->z
        mb.poly(pts, mat)


def window(mb, nc, u, z0, w, h, style, rng, dark=True, hood="key"):
    """Window in a facade frame (wall face at y=0, outside = -y, u along the facade)."""
    zc = z0 + h / 2
    if dark is True:    # dark="open": a real opening (only the arch head stays dark)
        mb.box((u, -0.02, zc), (w, 0.04, h), VOID, skip=("+y",))
    for s in (-1, 1):
        mb.box((u + s * (w / 2 + 0.1), -0.11, zc), (0.2, 0.22, h + 0.02), TRIM, skip=("+y",))
    mb.box((u, -0.15, z0 - 0.08), (w + 0.6, 0.3, 0.16), TRIM, skip=("+y",))
    if hood == "key":
        mb.box((u, -0.13, z0 + h + 0.12), (w + 0.5, 0.26, 0.24), TRIM, skip=("+y",))
        mb.box((u, -0.17, z0 + h + 0.14), (0.28, 0.34, 0.36), TRIM, skip=("+y",))
    elif hood == "pediment":
        mb.box((u, -0.13, z0 + h + 0.1), (w + 0.6, 0.26, 0.2), TRIM, skip=("+y",))
        a = (w + 0.8) / 2
        zb = z0 + h + 0.22
        mb.beam((u - a, -0.15, zb), (u + 0.02, -0.15, zb + 0.5), 0.3, 0.16, TRIM)
        mb.beam((u + a, -0.15, zb), (u - 0.02, -0.15, zb + 0.5), 0.3, 0.16, TRIM)
    elif hood == "arch":
        mb.arch((u, -0.13, z0 + h - w / 2), w, w, 0.26, 0.18, TRIM, seg=8)
        if dark:
            r = w / 2
            pts = [(u + math.cos(math.pi * k / 8) * r, -0.02, z0 + h + math.sin(math.pi * k / 8) * r) for k in range(9)]
            mb.poly(pts, VOID)

    if style == "boarded":
        n = rng.randint(3, 5)
        for i in range(n):
            zz = z0 + h * (i + 0.5) / n + rng.uniform(-0.1, 0.1)
            rbox(mb, (u + rng.uniform(-0.1, 0.1), -0.27, zz), (w + 0.5, 0.05, rng.uniform(0.18, 0.27)),
                 BOARD, pitch=rng.uniform(-12, 12))
    elif style == "cross":
        ang = math.degrees(math.atan2(h, w))
        for k, s in enumerate((-1, 1)):
            rbox(mb, (u, -0.27 - 0.05 * k, zc), (math.hypot(w, h) + 0.1, 0.05, 0.22), BOARD, pitch=s * ang)
        rbox(mb, (u, -0.37, zc + rng.uniform(-0.4, 0.4)), (w + 0.5, 0.05, 0.22), BOARD,
             pitch=rng.uniform(-6, 6))
    elif style == "shutter":
        lw = w / 2 + 0.05
        # one leaf open flat against the wall, the other hanging from its top hinge
        side = rng.choice((-1, 1))
        mb.box((u + side * (w / 2 + 0.22 + lw / 2), -0.25, zc), (lw, 0.05, h), ROT)
        for k in range(3):
            mb.box((u + side * (w / 2 + 0.22 + lw / 2), -0.28, z0 + h * (k + 0.5) / 3), (lw, 0.02, 0.06), ROT)
        hx = u - side * (w / 2 + 0.22 + lw)
        with mb.at((hx, -0.3, z0 + h), rot_y=side * rng.uniform(18, 32)):
            mb.box((side * lw / 2, 0, -h / 2), (lw, 0.05, h), ROT)
        # broken glass
        _shards(mb, u, z0, w, h, rng)
    elif style == "closed":
        lw = w / 2 - 0.01
        for s in (-1, 1):
            if rng.random() < 0.25:
                continue  # leaf missing
            mb.box((u + s * (lw / 2 + 0.01), -0.25, zc), (lw, 0.05, h), ROT)
            for k in range(4):
                mb.box((u + s * (lw / 2 + 0.01), -0.28, z0 + h * (k + 0.5) / 4), (lw - 0.06, 0.02, 0.05), ROT)
    elif style == "broken":
        _shards(mb, u, z0, w, h, rng)
        if rng.random() < 0.5:
            return
        # tattered curtain hanging inside
        n = rng.randint(3, 5)
        side = rng.choice((-1, 1))
        for i in range(n):
            sw = w * 0.45 / n
            x = u + side * (w / 2 - sw * (i + 0.5))
            ln = h * rng.uniform(0.45, 0.95)
            nc.box((x, -0.05, z0 + h - ln / 2), (sw * 0.95, 0.02, ln), "M_RottenCurtain")


def _shards(mb, u, z0, w, h, rng):
    x0, x1, za, zb = u - w / 2, u + w / 2, z0, z0 + h
    y = -0.05
    s1, s2 = w * rng.uniform(0.25, 0.45), h * rng.uniform(0.15, 0.3)
    mb.poly([(x0, y, za), (x0 + s1, y, za), (x0, y, za + s2)], "M_GlassClear")
    mb.poly([(x1, y, zb), (x1 - s1 * 0.8, y, zb), (x1, y, zb - s2 * 1.3)], "M_GlassClear")
    mb.poly([(x0, y, zb), (x0, y, zb - s2), (x0 + s1 * 0.6, y, zb)], "M_GlassClear")


def facade_trim(mb, origin, yaw, length, courses=(), cornice=None, quoins=(0.6, 11.4), q_ends=(True, True)):
    with mb.at(origin, rot=yaw):
        for z in courses:
            mb.box((length / 2, -0.09, z), (length + 0.32, 0.18, 0.2), TRIM, skip=("+y",))
        if cornice is not None:
            mb.box((length / 2, -0.225, cornice - 0.25), (length + 0.86, 0.45, 0.5), TRIM, skip=("+y",))
            mb.box((length / 2, -0.13, cornice - 0.65), (length + 0.5, 0.26, 0.3), TRIM, skip=("+y",))
        if quoins:
            z, i = quoins[0], 0
            while z < quoins[1] - 0.3:
                hq = 0.45
                wq = 0.62 if i % 2 == 0 else 0.38
                for end, on in ((0.0, q_ends[0]), (length, q_ends[1])):
                    if not on:
                        continue
                    sg = 1 if end == 0.0 else -1
                    mb.box((end + sg * (wq / 2 - 0.06), -0.04, z + hq / 2), (wq, 0.08, hq - 0.05), TRIM,
                           skip=("+y",))
                z += hq
                i += 1


def rubble(mb, center, radius, n, rng, mats=(STONE, TRIM), zc=0.0, size=(0.15, 0.55)):
    cx, cy = center[0], center[1]
    for _ in range(n):
        a = rng.uniform(0, math.tau)
        r = radius * math.sqrt(rng.random())
        s = rng.uniform(*size)
        rbox(mb, (cx + math.cos(a) * r, cy + math.sin(a) * r, zc + s * 0.25),
             (s * rng.uniform(0.8, 1.6), s * rng.uniform(0.7, 1.3), s * rng.uniform(0.5, 0.9)),
             rng.choice(mats), yaw=rng.uniform(0, 180), pitch=rng.uniform(-20, 20), roll=rng.uniform(-20, 20))


def planks(mb, center, radius, n, rng, mat=ROT, zc=0.0, length=(1.2, 3.0)):
    cx, cy = center[0], center[1]
    for i in range(n):
        a = rng.uniform(0, math.tau)
        r = radius * math.sqrt(rng.random())
        ln = rng.uniform(*length)
        rbox(mb, (cx + math.cos(a) * r, cy + math.sin(a) * r, zc + 0.05 + 0.06 * i),
             (ln, rng.uniform(0.18, 0.3), 0.05), mat, yaw=rng.uniform(0, 180), pitch=rng.uniform(-8, 8))


# ---------------------------------------------------------------- building shell
def _shell(aset, mb):
    # plinths down to -4 m (terrain slopes away at the pad edge)
    mb.box_mm((X0 - 0.4, Y0 - 0.4, -4.0), (X1 + 0.4, Y1 + 0.4, FL), STONE, mats={"+z": TRIM})
    mb.box_mm((-TX - 0.4, TY0 - 0.4, -4.0), (TX + 0.4, Y0 - 0.4, FL), STONE, mats={"+z": TRIM})
    # wings: the ground storey next to the hall is hollow (library west, portrait salon east), the rest of
    # the wing stays solid; the upper storeys are one solid block whose underside is the room ceiling
    for sx in (-1, 1):
        inner = "M_LibWallpaper" if sx < 0 else "M_SalonWallpaper"
        toward_hall = "+x" if sx < 0 else "-x"
        a, b = sorted((sx * 12.0, sx * HX))
        mb.box_mm((a, Y0, FL), (b, Y0 + WT, CZ1), STONE, mats={"+y": inner, "+z": VOID})          # front wall
        _ground_ends_shell(aset, mb, sx, inner, toward_hall)
        _upper_wing_shell(aset, mb, sx, toward_hall)
        # hall <-> room partition with a real doorway
        if sx < 0:
            p0, p1, c = (-HX, Y0 + WT), (-HX, HY1), SDY - (Y0 + WT)
        else:
            p0, p1, c = (HX, HY1), (HX, Y0 + WT), HY1 - SDY
        K.wall(aset, mb, p0, p1, FL, CZ1 - FL, WT, WALLP, inner=inner,
               openings=[K.Door(c, SDW, SDH, "abandoned", trim="M_DarkWood", trim_in="M_DarkWood")])
    # centre block behind the hall: ritual room (ground) + dorm room (gallery level) + solid attic storey
    hall_doors = [K.Door(x + HX, 1.3, 2.5, "abandoned", trim_in="M_DarkWood") for x in BACK_DOORS]
    K.wall(aset, mb, (-HX, HY1), (HX, HY1), FL, CZ1 - FL, WT, WALLP, inner=RITW, openings=hall_doors)
    K.wall(aset, mb, (-HX, HY1), (HX, HY1), CZ1, BED_TOP - CZ1, WT, WALLP, inner=WALLP,
           openings=[K.Door(HX, 1.6, 2.8, "abandoned", double=True, z0=BED_Z - CZ1, trim_in="M_DarkWood")])
    K.wall(aset, mb, (HX, Y1), (-HX, Y1), FL, CZ1 - FL, WT, STONE, inner=RITW,
           openings=[K.Door(HX, 2.2, 3.0, "abandoned", double=True, swing="in", trim_in="M_DarkWood")])
    K.wall(aset, mb, (HX, Y1), (-HX, Y1), CZ1, BED_TOP - CZ1, WT, STONE, inner=WALLP)
    mb.box_mm((-HX, HY1 + WT, CZ1), (HX, Y1 - WT, BED_Z - 0.015), ROT, mats={"-z": ROT})      # floor slab
    _centre_shell(aset, mb)
    # wall plates closing the gap between wall top and roof underside
    zp = ROOF_Z + (Y0 - EAVE_YF) * TAN
    for (a, b) in ((X0 + 0.01, -TX), (TX, X1 - 0.01)):      # (not through the tower rooms)
        mb.box_mm((a, Y0, EAVE), (b, Y0 + 0.5, zp), STONE)
    mb.box_mm((X0 + 0.01, Y1 - 0.5, EAVE), (X1 - 0.01, Y1, zp), STONE)
    # gable walls
    for sx in (-1, 1):
        x = sx * X1
        pts = [(x, Y0, EAVE), (x, Y1, EAVE), (x, Y1, zp), (x, RIDGE_Y, RIDGE_Z - 0.02), (x, Y0, zp)]
        mb.poly(pts if sx > 0 else list(reversed(pts)), STONE)
        # attic oculus
        with mb.at((x, RIDGE_Y, 14.0), rot=90 if sx > 0 else -90):
            with mb.at((0, 0, 0), rot_x=90):
                mb.cylinder((0, 0, 0), 0.75, 0.06, VOID, seg=12)
                mb.torus((0, 0, 0.08), 0.85, 0.12, TRIM, seg=14, tube_seg=6)
            for k in range(2):
                rbox(mb, (0, -0.25, 0.25 - 0.45 * k), (1.7, 0.05, 0.2), BOARD, pitch=(-14, 9)[k])
    # tower: lower hollow walls around the hall, solid above
    door = dict(u=TX, w=2.4, z0=0.0, z1=3.2)
    wins = [dict(u=TX - 3.0, w=1.2, z0=1.0, z1=3.4), dict(u=TX + 3.0, w=1.2, z0=1.0, z1=3.4),
            dict(u=TX - 3.0, w=1.2, z0=5.0, z1=6.8), dict(u=TX + 3.0, w=1.2, z0=5.0, z1=6.8),
            dict(u=TX, w=1.6, z0=5.1, z1=6.8)]
    mb.wall((-TX, TY0), (TX, TY0), FL, HZ1 - FL, 0.6, STONE, openings=[door] + wins, inner_mat=WALLP)
    mb.wall((-TX, Y0), (-TX, HY0), FL, HZ1 - FL, 0.6, STONE, inner_mat=WALLP)
    mb.wall((TX, HY0), (TX, Y0), FL, HZ1 - FL, 0.6, STONE, inner_mat=WALLP)
    _tower_shell(mb)


GF_KIT = (4.6, 4.6, 12.0, Y1 - WT)          # behind the salon / library (east-wing coordinates, |x|)
GF_A = (12.6, Y0 + WT, X1 - WT, -1.6)
GF_B = (12.6, -1.45, X1 - WT, 3.6)
GF_C = (12.6, 3.75, X1 - WT, Y1 - WT)
GF_DOOR_SIDE = {1: 1.2, -1: -3.05}           # y of the doorway from the salon (east) / library (west)
GF_DOOR_BACK = {1: 7.5, -1: 5.6}             # |x| of the doorway from the salon / library into the back room


def _ground_ends_shell(aset, mb, sx, inner, toward_hall):
    """The ground storey beyond the library / salon and behind them used to be solid: now four ruined rooms
    per wing behind the (still boarded) windows."""
    a, b = sorted((sx * 12.0, sx * X1))
    mb.box_mm((a, Y0, FL), (b, Y0 + WT, CZ1), STONE, mats={"+y": U_WALL, "+z": VOID})
    mb.box_mm((a, Y1 - WT, FL), (b, Y1, CZ1), STONE, mats={"-y": U_WALL, "+z": VOID})
    g0, g1 = sorted((sx * (X1 - WT), sx * X1))
    mb.box_mm((g0, Y0 + WT, FL), (g1, Y1 - WT, CZ1), STONE, mats={("-x" if sx > 0 else "+x"): U_WALL, "+z": VOID})
    k0, k1 = sorted((sx * HX, sx * (HX + WT)))
    mb.box_mm((k0, HY1, FL), (k1, Y1, CZ1), STONE, mats={toward_hall: RITW, ("+x" if sx > 0 else "-x"): U_WALL,
                                                       "+z": VOID})
    k0, k1 = sorted((sx * (HX + WT), sx * 12.0))
    mb.box_mm((k0, Y1 - WT, FL), (k1, Y1, CZ1), STONE, mats={"-y": U_WALL, "+z": VOID})
    h = CZ1 - FL
    door = lambda u: K.Door(u, 0.95, 2.15, "abandoned", z0=FZ - FL, trim="M_DarkWood", trim_in="M_DarkWood")  # noqa
    ys = GF_DOOR_SIDE[sx]
    _mwall(aset, mb, sx, (12.0, HY1), (12.0, Y0 + WT), FL, h, WT, inner, U_WALL, [door(HY1 - ys)])
    _mwall(aset, mb, sx, (12.0, Y1 - WT), (12.0, HY1), FL, h, WT, U_WALL, U_WALL, [door(Y1 - WT - 7.0)])
    _mwall(aset, mb, sx, (HX + WT, HY1), (12.0, HY1), FL, h, WT, inner, U_WALL,
           [door(GF_DOOR_BACK[sx] - (HX + WT))])
    for y in (GF_A[3], GF_C[1] - 0.15):
        _mwall(aset, mb, sx, (12.6, y), (X1 - WT, y), FL, h, 0.15, U_WALL, U_WALL, [door(14.0 - 12.6)])

# ---------------------------------------------------------------- first floor (dorm corridor) + tower shells
U_FZ, U_TOP = BED_Z, BED_TOP          # finished floor / ceiling of the first-floor dorm storey (gallery level)
U_WB = U_FZ - 0.03                     # wall base (under the floor boards)
U_CORR = (2.0, 4.0)                    # corridor partition lines (clear width 2.15 .. 3.85)
U_PARTS = (8.3, 12.0, 15.7)            # cross partitions (|x|), 0.15 thick towards +|x|
U_ROOMS = ((4.6, 8.3), (8.45, 12.0), (12.15, 15.7), (15.85, 19.4))   # |x| spans of the rooms
U_WALL, U_CWALL, U_CEIL = "M_RuinWall", "M_RuinCorridorWall", "M_RuinCeiling"
WIN_FRONT = (6.9, 10.5, 14.1, 17.7)    # |x| of the first-floor front windows
WIN_BACK = (6.0, 10.0, 14.0, 18.0)     # |x| of the back windows (18 = the stairwell bay)
WIN_GABLE = (-5.6, -1.2, 3.2, 7.6)     # y of the gable windows (7.6 = the stairwell bay)
T_FZ, T_TOP = 7.85, 11.0               # second floor (behind the 8.6 m window row): finished floor / ceiling
T_WB = T_FZ - 0.03
FL2 = dict(fz=U_FZ, top=U_TOP, row=1, tag="")
FL3 = dict(fz=T_FZ, top=T_TOP, row=2, tag="_3f")
STAIR_LAND = 4.65                      # stairwell bay: top landing strip y 4.0 .. 4.65, flights beyond
TFL = (HZ1 + 0.2, 11.8, 15.6)          # tower floors: store room, keeper's room, clockwork room
TCEIL = (11.6, 15.4, 19.5)
TIN = (-TX + 0.6, TY0 + 0.6, TX - 0.6, TY1 - 0.6)   # tower inner faces (x0, y0, x1, y1)
SPIRAL = (-2.9, -9.3, 1.0)             # hall -> tower spiral stair (centre x, y, outer radius)
SPIRAL_HOLE = (TIN[0], TIN[1], -1.85, -8.25)
FLIGHT_A = (3.4, -9.9)                 # store room -> keeper's room (climbs +y along the east wall)
FLIGHT_B = (-3.4, -3.1)                # keeper's room -> clockwork room (climbs -y along the west wall)


def _mwall(aset, mb, sx, p0, p1, z0, h, thick, mat, inner=None, openings=(), plain=False):
    """Wall given in EAST-wing coordinates; for the west wing (sx < 0) it is mirrored (and reversed, so the
    inside stays on the left). plain=True: openings are dicts for MeshBuilder.wall (bare holes)."""
    L = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
    if sx < 0:
        p0, p1 = (-p1[0], p1[1]), (-p0[0], p0[1])
        if plain:
            openings = [dict(o, u=L - o["u"]) for o in openings]
        else:
            ops = []
            for o in openings:
                o2 = K._copy(o)
                o2.c = L - o.c
                ops.append(o2)
            openings = ops
    if plain:
        mb.wall(p0, p1, z0, h, thick, mat, openings, inner_mat=inner)
    else:
        K.wall(aset, mb, p0, p1, z0, h, thick, mat, inner=inner, openings=openings)


def _upper_wing_shell(aset, mb, sx, toward_hall):
    """The upper storeys of a wing used to be one solid block - now two walkable dorm floors (first floor at the
    gallery level, second floor behind the 8.6 m window row): slabs, outer walls with real window openings, the
    corridor + room partitions, and the stairwell bay (B4) that links them."""
    a, b = sorted((sx * X1, sx * HX))
    mb.box_mm((a, Y0, CZ1), (b, Y1, U_WB), STONE, mats={toward_hall: WALLP, "-z": ROT})            # floor slab
    a2 = sorted((sx * X1, sx * (HX + WT)))
    a3 = sorted((sx * HX, sx * (HX + WT)))
    s0, s1 = sorted((sx * U_ROOMS[3][0], sx * U_ROOMS[3][1]))                                       # stairwell bay
    # slab between the floors (open over the stairwell flights), the solid roof-plate block above the 2nd floor
    K.slab(mb, a2[0], Y0, a2[1], Y1, T_WB, T_WB - U_TOP, STONE, bottom=U_CEIL, side=ROT,
           holes=[(s0, STAIR_LAND, s1, Y1 - WT)])
    mb.box_mm((a3[0], TY1, U_TOP), (a3[1], Y1, T_WB), STONE, mats={toward_hall: WALLP, "-z": U_CEIL})
    mb.box_mm((a2[0], Y0, T_TOP), (a2[1], Y1, EAVE), STONE, mats={"+z": VOID, "-z": U_CEIL})
    mb.box_mm((a3[0], TY1, T_TOP), (a3[1], Y1, EAVE), STONE, mats={toward_hall: WALLP, "+z": VOID, "-z": U_CEIL})
    mb.box_mm((a3[0], Y0, U_TOP), (a3[1], TY1, HZ1), STONE, mats={toward_hall: WALLP, "-z": U_CEIL})
    xo = HX + WT
    for fl in (FL2, FL3):
        wb, top, row = fl["fz"] - 0.03, fl["top"], fl["row"]
        h = top - wb
        wz0, wz1 = WIN_ROWS[row][0] - wb, WIN_ROWS[row][0] + WIN_ROWS[row][1] - wb
        # outer walls (east-wing coordinates, mirrored for the west wing)
        _mwall(aset, mb, sx, (xo, Y0), (X1, Y0), wb, h, WT, STONE, U_WALL,
               [dict(u=x - xo, w=1.25, z0=wz0, z1=wz1) for x in WIN_FRONT], plain=True)
        _mwall(aset, mb, sx, (X1, Y1), (xo, Y1), wb, h, WT, STONE, U_WALL,
               [dict(u=X1 - x, w=1.25, z0=wz0, z1=wz1) for x in WIN_BACK], plain=True)
        _mwall(aset, mb, sx, (X1, Y0 + WT), (X1, Y1 - WT), wb, h, WT, STONE, U_WALL,
               [dict(u=y - (Y0 + WT), w=1.25, z0=wz0, z1=wz1) for y in WIN_GABLE], plain=True)
        if fl is FL2:   # hall wall with the doorway from the gallery
            _mwall(aset, mb, sx, (HX, Y1), (HX, Y0), wb, h, WT, WALLP, U_WALL,
                   [K.Door(Y1 - 3.0, 1.0, 2.15, "abandoned", z0=0.03, trim="M_DarkWood", trim_in="M_DarkWood")])
        else:           # 2nd floor: doorway into the centre corridor (the lounge floor bridges the two wings)
            _mwall(aset, mb, sx, (HX, Y1), (HX, TY1), wb, h, WT, U_CWALL, U_WALL,
                   [K.Door(Y1 - 3.0, 1.0, 2.15, "abandoned", z0=0.03, trim="M_DarkWood", trim_in="M_DarkWood")])
        # corridor walls with the room doors (B4 = the stairwell, its boards pried off)
        c0, c1 = U_CORR
        _mwall(aset, mb, sx, (xo, c0), (X1 - WT, c0), wb, h, 0.15, U_WALL, U_CWALL,
               [K.Door(r0 + 0.75 - xo, 0.95, 2.15, "abandoned", z0=0.03, trim_in="M_DarkWood", trim="M_DarkWood")
                for (r0, r1) in U_ROOMS])
        _mwall(aset, mb, sx, (X1 - WT, c1), (xo, c1), wb, h, 0.15, U_WALL, U_CWALL,
               [K.Door(X1 - WT - (r0 + 0.75), 0.95, 2.15, "abandoned", z0=0.03, trim_in="M_DarkWood", trim="M_DarkWood")
                for (r0, r1) in U_ROOMS])
        for x in U_PARTS:
            _mwall(aset, mb, sx, (x, c0), (x, Y0 + WT), wb, h, 0.15, U_WALL, U_WALL)
            _mwall(aset, mb, sx, (x, Y1 - WT), (x, c1), wb, h, 0.15, U_WALL, U_WALL)


def _centre_shell(aset, mb):
    """Above the dorm room and the back of the hall: the 2nd-floor centre corridor and the floor lounge."""
    mb.box_mm((-HX, HY1, BED_TOP), (HX, Y1, T_WB), STONE, mats={"-y": WALLP, "-z": ROT})            # lounge floor slab
    mb.box_mm((-HX, TY1, HZ1), (HX, U_CORR[0] + 0.15, EAVE), STONE, mats={"-z": ROT, "+z": VOID, "+y": U_CWALL})
    mb.box_mm((-HX, U_CORR[0] + 0.15, HZ1), (HX, HY1, T_WB), STONE, mats={"-z": ROT})               # corridor floor
    mb.box_mm((-HX, U_CORR[0] + 0.15, T_TOP), (HX, Y1, EAVE), STONE, mats={"-z": U_CEIL, "+z": VOID})
    K.wall(aset, mb, (-HX, U_CORR[1] - 0.15), (HX, U_CORR[1] - 0.15), T_WB, T_TOP - T_WB, 0.15, U_CWALL, inner=U_WALL,
           openings=[K.Door(HX, 1.6, 2.3, "abandoned", double=True, z0=0.03, trim="M_DarkWood", trim_in="M_DarkWood")])
    wz0, wz1 = WIN_ROWS[2][0] - T_WB, WIN_ROWS[2][0] + WIN_ROWS[2][1] - T_WB
    mb.wall((HX, Y1), (-HX, Y1), T_WB, T_TOP - T_WB, WT, STONE, [dict(u=HX - x, w=1.25, z0=wz0, z1=wz1) for x in (2.0, -2.0)],
            inner_mat=U_WALL)


def _tower_shell(mb):
    """The tower above the hall: three rooms (store, keeper's room, clockwork) behind real window openings."""
    x0, y0, x1, y1 = TIN
    h = TTOP - HZ1
    rel = lambda z: z - HZ1   # noqa: E731
    front = [dict(u=u, w=1.2, z0=rel(8.6), z1=rel(10.4)) for u in (2.4, 6.8)] + \
            [dict(u=u, w=0.8, z0=rel(12.6), z1=rel(14.8)) for u in (3.6, 5.6)]
    mb.wall((-TX, TY0), (TX, TY0), HZ1, h, WT, STONE, front, inner_mat=U_WALL)
    zb = TCEIL[1]     # the side walls are built in two bands: their 13.5 m and 16 m windows overlap along the wall
    mb.wall((TX, y0), (TX, y1), HZ1, zb - HZ1, WT, STONE, [dict(u=2.6, w=1.2, z0=13.5 - HZ1, z1=15.1 - HZ1)],
            inner_mat=U_WALL)
    mb.wall((TX, y0), (TX, y1), zb, TTOP - zb, WT, STONE,
            [dict(u=u, w=0.8, z0=16.0 - zb, z1=18.6 - zb) for u in (2.9, 4.9)], inner_mat=U_WALL)
    mb.wall((-TX, y1), (-TX, y0), HZ1, zb - HZ1, WT, STONE, [dict(u=5.2, w=1.2, z0=13.5 - HZ1, z1=15.1 - HZ1)],
            inner_mat=U_WALL)
    mb.wall((-TX, y1), (-TX, y0), zb, TTOP - zb, WT, STONE,
            [dict(u=u, w=0.8, z0=16.0 - zb, z1=18.6 - zb) for u in (2.9, 4.9)], inner_mat=U_WALL)
    mb.wall((TX, TY1), (-TX, TY1), HZ1, h, WT, STONE,
            [dict(u=u, w=0.8, z0=rel(16.0), z1=rel(18.6)) for u in (3.6, 5.6)], inner_mat=U_WALL)
    # floors (with the stair holes) and the solid spire base above the clockwork room
    K.slab(mb, x0, y0, x1, y1, TFL[0] - 0.03, TFL[0] - 0.03 - HZ1, ROT, bottom=ROT, side=ROT, holes=[SPIRAL_HOLE])
    K.slab(mb, x0, y0, x1, y1, TFL[1] - 0.03, 0.2, ROT, bottom=U_CEIL, side=ROT, holes=[(2.85, -8.0, x1, -4.02)])
    K.slab(mb, x0, y0, x1, y1, TFL[2] - 0.03, 0.2, ROT, bottom=U_CEIL, side=ROT, holes=[(x0, -8.98, -2.85, -5.3)])
    mb.box_mm((x0, y0, TCEIL[2]), (x1, y1, TTOP), STONE, mats={"-z": U_CEIL})


def _facades(mb, nc, rng):
    st_ground = ["boarded", "boarded", "cross", "closed"]
    st_upper = ["boarded", "cross", "shutter", "closed", "broken", "broken", "shutter"]
    bays_wing = [2.3, 5.9, 9.5, 13.1]
    bays_side = [2.4, 6.8, 11.2, 15.6]
    bays_back = [2.0 + 4.0 * i for i in range(10)]

    def windows(origin, yaw, bays, skip=(), shut=()):
        # the first-floor windows are real openings now (the dorm corridor storey is walkable), except
        # the bays listed in `shut` (rooms behind them have their own boarded inside)
        with mb.at(origin, rot=yaw), nc.at(origin, rot=yaw):
            for fi, (z0, h) in enumerate(WIN_ROWS):
                for bi, u in enumerate(bays):
                    if (fi, bi) in skip:
                        continue
                    st = rng.choice(st_ground if fi == 0 else st_upper)
                    window(mb, nc, u, z0, 1.25, h, st, rng,
                           dark="open" if (fi == 2 or (fi == 1 and bi not in shut)) else True)

    windows((X0, Y0), 0, bays_wing)
    windows((TX, Y0), 0, bays_wing)
    windows((X1, Y0), 90, bays_side)
    windows((X0, Y1), -90, bays_side)
    windows((X1, Y1), 180, bays_back, skip={(0, 4), (0, 5)}, shut=(4, 5))
    # trims
    for org, yaw, ln, qe in (((X0, Y0), 0, X1 - TX, (True, False)), ((TX, Y0), 0, X1 - TX, (False, True)),
                             ((X1, Y0), 90, Y1 - Y0, (True, True)), ((X1, Y1), 180, X1 - X0, (True, True)),
                             ((X0, Y1), -90, Y1 - Y0, (True, True))):
        facade_trim(mb, org, yaw, ln, courses=FLOOR_BANDS, cornice=ROOF_Z, q_ends=qe)
    # back door: a real doorway into the ritual room (the door itself is placed by _shell); the boards that
    # once sealed it have been pried off - one still hangs from a nail, two lie on the steps
    with mb.at((0, Y1, 0), rot=180):
        tilt = [rng.uniform(-10, 10) for k in range(3)]
        rbox(mb, (-1.42, -0.2, FL + 1.55), (0.24, 0.05, 2.6), BOARD, pitch=4.0 + tilt[0] * 0.3)
        rbox(mb, (0.5, -1.8, 0.24), (2.6, 0.24, 0.05), BOARD, yaw=8.0 + tilt[1], roll=-6.0)
        rbox(mb, (-0.9, -2.7, 0.04), (2.6, 0.24, 0.05), BOARD, yaw=-24.0 + tilt[2])
        window(mb, nc, 0, FL, 2.2, 3.0, "none", rng, dark=False, hood="pediment")
        mb.stairs((0, -2.0, 0.0), 90, 3.0, 3, 0.2, 0.5, STONE)
        mb.box_mm((-1.6, -1.1, FL - 0.4), (1.6, -0.3, FL + 0.01), TRIM)        # threshold landing
    # sagging, broken gutter on the front eave
    gz = ROOF_Z - 0.05
    mb.box_mm((X0 - 0.6, EAVE_YF - 0.3, gz - 0.15), (-10.0, EAVE_YF - 0.12, gz), RUST)
    mb.beam((-10.0, EAVE_YF - 0.21, gz - 0.07), (-7.4, EAVE_YF - 0.6, gz - 2.2), 0.16, 0.16, RUST)
    mb.box_mm((10.5, EAVE_YF - 0.3, gz - 0.15), (X1 + 0.6, EAVE_YF - 0.12, gz), RUST)
    mb.box_mm((X1 - 0.3, EAVE_YF - 0.12, FL), (X1 - 0.12, EAVE_YF + 0.06, gz), RUST)  # downpipe


def _roof(mb, rng):
    """Two slate slopes (individual staggered slates), ragged holes with exposed rafters, dormers."""
    slope_len = RUN / COS
    rows = 15
    rh = slope_len / rows
    xl, xr = X0 - VERGE, X1 + VERGE
    sw = 0.85
    # (f0, f1, x0, x1): f = fraction of the slope length, x in world metres
    holes = {"front": [(0.2, 0.68, -10.5, -6.0), (0.55, 0.92, 8.0, 10.6)],
             "back": [(0.1, 0.62, 4.0, 9.8), (0.45, 0.9, -8.5, -3.8), (0.05, 0.3, -12.5, -11.0)]}
    dormers = {"front": [(-13.5, 0.22, "boarded"), (13.5, 0.22, "broken")],
               "back": [(-15.0, 0.22, "broken"), (15.0, 0.22, "boarded")]}
    dorm_h, dorm_w = 2.2, 1.9
    dorm_f = (dorm_h / TAN) / RUN
    for slope in ("front", "back"):
        sgn = 1 if slope == "front" else -1
        origin = (0, EAVE_YF if slope == "front" else EAVE_YB, ROOF_Z)
        yaw = 0 if slope == "front" else 180
        hl = []
        for (f0, f1, a, b) in holes[slope]:
            a, b = sorted((sgn * a, sgn * b))
            hl.append((f0, f1, a, b))
        dl = [(sgn * xc, f0) for (xc, f0, _) in dormers[slope]]
        with mb.at(origin, rot=yaw, rot_x=PITCH):
            for r in range(rows):
                f_lo, f_hi = r / rows, (r + 1) / rows
                cuts = []
                y_end = EAVE_YF + f_hi * RUN
                if slope == "front" and y_end < TY1 + 0.3:
                    cuts.append((-TX + 0.05, TX - 0.05))
                for (f0, f1, a, b) in hl:
                    if f0 <= (f_lo + f_hi) / 2 <= f1:
                        mid = ((f_lo + f_hi) / 2 - f0) / max(1e-3, f1 - f0)
                        shrink = (b - a) * 0.3 * abs(mid - 0.5) * 2
                        cuts.append((a + shrink * rng.uniform(0.3, 1.0) + rng.uniform(-0.3, 0.3),
                                     b - shrink * rng.uniform(0.3, 1.0) + rng.uniform(-0.3, 0.3)))
                for (xc, f0) in dl:
                    if f0 - 0.01 <= f_lo and f_hi <= f0 + dorm_f + 0.08:
                        cuts.append((xc - dorm_w / 2 + 0.05, xc + dorm_w / 2 - 0.05))
                cuts.sort()
                segs, x = [], xl
                for a, b in cuts:
                    if a > x:
                        segs.append((x, a))
                    x = max(x, b)
                if x < xr:
                    segs.append((x, xr))
                top = (r == rows - 1)
                with mb.at((0, r * rh, 0), rot_x=-2.0):
                    for a, b in segs:
                        # stagger slates; the first/last slate of a run is cut to fit
                        x = xl + (sw / 2 if r % 2 else 0.0)
                        edges = [a]
                        while x < b:
                            if x > a + 0.12:
                                edges.append(x)
                            x += sw
                        edges.append(b)
                        for k in range(len(edges) - 1):
                            x0, x1 = edges[k] + 0.015, edges[k + 1] - 0.015
                            if x1 - x0 < 0.1:
                                continue
                            if rng.random() < 0.012 and 2 < r < rows - 2:
                                continue  # single missing slate
                            jz = rng.uniform(-0.012, 0.012)
                            mb.box(((x0 + x1) / 2, (rh + 0.1) / 2, 0.06 + jz), (x1 - x0, rh + 0.1, 0.12),
                                   "M_OldRoof", skip=() if top else ("-z", "+y"))
            # exposed rafters / laths in the holes
            for (f0, f1, a, b) in hl:
                ya = max(0.0, f0 * slope_len - 0.5)
                yb = min(slope_len, f1 * slope_len + 0.5)
                x = a - 0.2
                while x < b + 0.3:
                    if rng.random() < 0.85:
                        broken = rng.random() < 0.25
                        yy1 = yb if not broken else ya + (yb - ya) * rng.uniform(0.4, 0.7)
                        mb.box((x, (ya + yy1) / 2, -0.12), (0.12, yy1 - ya, 0.2), ROT)
                    x += 0.6
                yy = ya + 0.4
                while yy < yb - 0.3:
                    if rng.random() < 0.6:
                        mb.box(((a + b) / 2 + rng.uniform(-0.5, 0.5), yy, 0.0),
                               (rng.uniform(0.5, 0.9) * (b - a), 0.06, 0.04), ROT)
                    yy += 0.75
                for _ in range(5):   # loose slates hanging over the edge
                    rbox(mb, (rng.choice((a, b)) + rng.uniform(-0.3, 0.3), rng.uniform(ya + 0.5, yb - 0.5), 0.1),
                         (0.8, 0.7, 0.04), "M_OldRoof", yaw=rng.uniform(-30, 30), roll=rng.uniform(-15, 15))
        # dormers (world space)
        for (xc, f0, style) in dormers[slope]:
            yf = (EAVE_YF + f0 * RUN) if slope == "front" else (EAVE_YB - f0 * RUN)
            zf = ROOF_Z + f0 * RUN * TAN
            depth = dorm_h / TAN + 0.6
            with mb.at((xc, yf, zf), rot=yaw):
                mb.box((0, depth / 2, dorm_h / 2 - 0.15), (dorm_w, depth, dorm_h + 0.3), STONE)
                mb.box((0, -0.02, 0.95), (1.0, 0.04, 1.3), VOID, skip=("+y",))
                for s in (-1, 1):
                    mb.box((s * 0.6, -0.08, 0.95), (0.2, 0.16, 1.4), TRIM, skip=("+y",))
                mb.box((0, -0.1, 0.22), (1.5, 0.2, 0.14), TRIM, skip=("+y",))
                mb.gable_roof((0, depth / 2 - 0.2, dorm_h), dorm_w, depth + 0.4, 0.95, "M_OldRoof", overhang=0.22,
                              thick=0.14, gable_mat=TRIM, ridge_axis="y")
                if style == "boarded":
                    for k in range(3):
                        rbox(mb, (0, -0.2, 0.55 + k * 0.4), (1.35, 0.05, 0.2), BOARD, pitch=rng.uniform(-14, 14))
                else:
                    _shards(mb, 0.0, 0.3, 1.0, 1.3, rng)

    # ridge cap (with a gap) and barge boards
    mb.box_mm((xl, RIDGE_Y - 0.28, RIDGE_Z + 0.05), (-6.0, RIDGE_Y + 0.28, RIDGE_Z + 0.3), "M_OldRoof")
    mb.box_mm((-4.5, RIDGE_Y - 0.28, RIDGE_Z + 0.05), (xr, RIDGE_Y + 0.28, RIDGE_Z + 0.3), "M_OldRoof")
    for sx in (-1, 1):
        x = sx * (X1 + VERGE + 0.04)
        mb.beam((x, EAVE_YF - 0.05, ROOF_Z - 0.05), (x, RIDGE_Y, RIDGE_Z + 0.2), 0.08, 0.38, ROT)
        mb.beam((x, EAVE_YB + 0.05, ROOF_Z - 0.05), (x, RIDGE_Y, RIDGE_Z + 0.2), 0.08, 0.38, ROT)
    # chimneys: gable-end stacks and two through the back slope (one collapsed)
    for (x, y, zb, h, lean, broken) in ((-18.9, RIDGE_Y + 2.2, EAVE, 9.4, (5.0, -3.0), False),
                                         (18.9, RIDGE_Y + 2.2, EAVE, 8.6, (-8.0, 3.0), False),
                                         (-10.0, 5.2, 14.0, 4.6, (4.0, 7.0), False),
                                         (10.0, 5.2, 14.0, 2.6, (0.0, 0.0), True)):
        with mb.at((x, y, zb), rot_y=lean[0], rot_x=lean[1]):
            mb.box((0, 0, h / 2), (1.1, 1.5, h), STONE)
            if not broken:
                mb.box((0, 0, h - 0.5), (1.35, 1.75, 0.18), TRIM)
                mb.box((0, 0, h + 0.1), (1.3, 1.7, 0.2), TRIM)
                mb.cylinder((0, -0.35, h + 0.2), 0.18, 0.55, RUST, seg=8)
                mb.cylinder((0, 0.35, h + 0.2), 0.18, 0.4, RUST, seg=8, radius_top=0.14)
            else:
                rbox(mb, (0.25, 0.2, h + 0.15), (0.6, 0.9, 0.3), STONE, yaw=12, pitch=18)
        if broken:
            rubble(mb, (x + 1.2, y - 1.6), 1.0, 8, rng, zc=ROOF_Z + (EAVE_YB - (y - 1.6)) * TAN, size=(0.15, 0.35))


def _tower(mb, roof, nc, rng):
    # facade windows on the tower (front, sides, back) - upper storeys
    with mb.at((-TX, TY0), rot=0), nc.at((-TX, TY0), rot=0):
        # lower front: real openings (boards over them), door surround
        window(mb, nc, 1.6, FL + 1.0, 1.2, 2.4, "boarded", rng, dark=False)
        window(mb, nc, 7.6, FL + 1.0, 1.2, 2.4, "cross", rng, dark=False)
        window(mb, nc, 1.6, FL + 5.0, 1.2, 1.8, "shutter", rng, dark=False)
        window(mb, nc, 7.6, FL + 5.0, 1.2, 1.8, "broken", rng, dark=False)
        window(mb, nc, TX, FL + 5.1, 1.6, 1.7, "none", rng, dark=False)
        rbox(mb, (TX + 0.1, -0.3, FL + 5.9), (2.1, 0.05, 0.22), BOARD, pitch=-16)
        # door surround + pediment + name plaque
        for s in (-1, 1):
            mb.box((TX + s * 1.38, -0.15, FL + 1.6), (0.36, 0.3, 3.24), TRIM, skip=("+y",))
        mb.box((TX, -0.17, FL + 3.4), (3.2, 0.34, 0.4), TRIM, skip=("+y",))
        mb.beam((TX - 1.7, -0.2, FL + 3.6), (TX + 0.02, -0.2, FL + 4.1), 0.4, 0.2, TRIM)
        mb.beam((TX + 1.7, -0.2, FL + 3.6), (TX - 0.02, -0.2, FL + 4.1), 0.4, 0.2, TRIM)
        # third level + upper tower
        window(mb, nc, 2.4, 8.6, 1.2, 1.8, "closed", rng, dark="open")
        window(mb, nc, 6.8, 8.6, 1.2, 1.8, "boarded", rng, dark="open")
        for u in (3.6, 5.6):
            window(mb, nc, u, 12.6, 0.8, 2.2, "broken" if u < 4 else "boarded", rng, hood="arch", dark="open")
        # clock face (stopped, one hand gone)
        with mb.at((TX, 0, 17.6), rot_x=90):
            mb.cylinder((0, 0, 0), 1.55, 0.2, TRIM, seg=20)
            mb.cylinder((0, 0, 0.2), 1.3, 0.04, "M_PortraitFace", seg=20)
            for k in range(12):
                a = math.tau * k / 12
                rbox(mb, (math.cos(a) * 1.12, math.sin(a) * 1.12, 0.26), (0.2 if k % 3 else 0.32, 0.07, 0.04),
                     "M_Black", yaw=math.degrees(a))
            rbox(mb, (0.28, -0.32, 0.3), (0.12, 0.85, 0.05), "M_Black", yaw=-40)
            mb.cylinder((0, 0, 0.24), 0.1, 0.1, RUST, seg=8)
    facade_trim(mb, (-TX, TY0), 0, 2 * TX, courses=(7.85, 15.6, 19.6), cornice=TTOP, quoins=(FL, TTOP))
    facade_trim(mb, (TX, TY0), 90, TY1 - TY0, courses=FLOOR_BANDS + (15.6, 19.6), cornice=TTOP, quoins=(FL, TTOP))
    facade_trim(mb, (-TX, TY1), -90, TY1 - TY0, courses=FLOOR_BANDS + (15.6, 19.6), cornice=TTOP, quoins=(FL, TTOP))
    facade_trim(mb, (TX, TY1), 180, 2 * TX, courses=(15.6, 19.6), cornice=TTOP, quoins=(13.0, TTOP))
    for org, yaw in (((TX, TY0), 90), ((-TX, TY1), -90), ((TX, TY1), 180)):
        with mb.at(org, rot=yaw), nc.at(org, rot=yaw):
            ln = 2 * TX if yaw == 180 else TY1 - TY0
            for u in (ln / 2 - 1.0, ln / 2 + 1.0):
                window(mb, nc, u, 16.0, 0.8, 2.6, rng.choice(("boarded", "broken", "closed")), rng, hood="arch",
                       dark="open")
            if yaw != 180:
                window(mb, nc, 3.2 if yaw == 90 else ln - 3.2, 13.5, 1.2, 1.6, rng.choice(("boarded", "cross")), rng,
                       dark="open")
    # pyramid roof with a dormer and a crooked finial
    cy = (TY0 + TY1) / 2
    roof.box_mm((-TX - 0.55, TY0 - 0.55, TTOP), (TX + 0.55, TY1 + 0.55, TTOP + 0.3), TRIM)
    roof.pyramid((0, cy, TTOP + 0.3), 2 * TX + 1.0, (TY1 - TY0) + 1.0, 8.5, "M_OldRoof")
    for sx in (-1, 1):
        for sy in (-1, 1):
            roof.beam((sx * (TX + 0.5), cy + sy * ((TY1 - TY0) / 2 + 0.5), TTOP + 0.35), (0, cy, TTOP + 8.85),
                      0.2, 0.2, "M_DarkMetal")
    # slate courses on the four faces of the spire
    pw, pd, ph = 2 * TX + 1.0, (TY1 - TY0) + 1.0, 8.5
    for k, (yaw, w, d) in enumerate(((0, pw, pd), (90, pd, pw), (180, pw, pd), (270, pd, pw))):
        a = math.radians(yaw)
        ox, oy = math.sin(a) * d / 2, -math.cos(a) * d / 2
        pitch = math.degrees(math.atan2(ph, d / 2))
        L = math.hypot(ph, d / 2)
        with roof.at((ox, cy + oy, TTOP + 0.3), rot=yaw, rot_x=pitch):
            n = 11
            for i in range(1, n):
                t = i / n
                roof.box((0, t * L, 0.0), (w * (1 - t) - 0.1, 0.08, 0.1), "M_OldRoof")
    with roof.at((0, TY0 + 1.5, TTOP + 1.6)):
        roof.box((0, 0, 0.8), (1.4, 2.2, 1.6), "M_OldRoof")
        roof.box((0, -1.11, 0.75), (0.8, 0.04, 1.0), VOID)
        roof.gable_roof((0, 0, 1.6), 1.4, 2.2, 0.8, "M_OldRoof", overhang=0.15, thick=0.12,
                        gable_mat="M_OldRoof", ridge_axis="y")
    with roof.at((0, cy, TTOP + 8.6), rot_y=7, rot_x=-4):
        roof.cylinder((0, 0, 0), 0.08, 2.4, RUST, seg=6)
        roof.sphere((0, 0, 0.9), 0.18, RUST, seg=8, rings=6)
        rbox(roof, (0.35, 0, 1.9), (0.9, 0.03, 0.35), RUST, yaw=20)
        rbox(roof, (0, 0, 1.5), (0.7, 0.04, 0.04), RUST, yaw=-35)


def _porch(mb, nc, rng):
    deck = FL + 0.02
    py0, py1, px = -14.6, TY0, 6.0

    def sag(x):
        s = 0.0
        if abs(x) > 1.8:
            s += 0.09 * ((abs(x) - 1.8) / 4.2) ** 1.3
        if x > 3.4:
            s += 0.28 * ((x - 3.4) / 2.6) ** 2
        return s

    L = py1 - py0
    n = 40
    w = 2 * px / n
    for i in range(n):
        x = -px + w * (i + 0.5)
        if abs(x - 3.45) < 0.1 or abs(x - 4.65) < 0.1:
            continue  # missing boards
        ln = L if abs(x - 3.75) > 0.1 else L * 0.45
        a = math.degrees(math.asin(min(0.9, sag(x) / L)))
        with mb.at((x, py1, deck), rot_x=a):
            mb.box((0, -ln / 2, -0.03), (w - 0.025, ln, 0.06), ROT)
    # a broken board on the ground
    rbox(mb, (4.9, -15.4, 0.12), (0.27, 2.2, 0.05), ROT, yaw=24, roll=6)
    # frame: rim beams, piers and a broken skirt
    mb.beam((-px, py0 + 0.1, deck - 0.2), (2.0, py0 + 0.1, deck - 0.2), 0.16, 0.24, ROT)
    mb.beam((2.0, py0 + 0.1, deck - 0.2), (px, py0 + 0.1, deck - 0.2 - sag(px) * 0.95), 0.16, 0.24, ROT)
    for x in (-5.8, -2.0, 2.0, 5.8):
        h = deck - 0.32 - sag(x)
        mb.box((x, py0 + 0.15, h / 2), (0.22, 0.22, h), ROT)
    for (a, b) in ((-6.0, -4.2), (-3.9, -1.9), (2.1, 2.9), (4.3, 5.0)):
        mb.box_mm((a, py0 - 0.02, 0.0), (b, py0 + 0.03, deck - 0.3 - sag(b)), ROT)
    for sx in (-1, 1):
        mb.box_mm((sx * px - 0.03, py0, 0.0), (sx * px + 0.03, py1, deck - 0.3 - sag(sx * px) * 0.5), ROT)
    # steps (risers 0.2 m)
    mb.box_mm((-1.6, -15.8, -0.4), (1.6, -15.2, 0.2), ROT)
    mb.box_mm((-1.6, -15.2, -0.4), (1.6, py0, 0.41), ROT)
    for sx in (-1, 1):
        mb.box_mm((sx * 1.6 - 0.1, -15.85, -0.2), (sx * 1.6 + 0.1, py0, 0.5), ROT)

    # railings with missing balusters
    def rail(p0, p1, broken=None):
        p0, p1 = list(p0), list(p1)
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        ln = math.hypot(dx, dy)
        nb = int(ln / 0.24)
        for k in range(nb + 1):
            t = k / nb
            x, y = p0[0] + dx * t, p0[1] + dy * t
            zb = deck - sag(x)
            if k in (0, nb):
                mb.box((x, y, zb + 0.55), (0.14, 0.14, 1.1), ROT)
            elif rng.random() > 0.28 and not (broken and broken[0] < t < broken[1]):
                mb.box((x, y, zb + 0.45), (0.05, 0.05, 0.9), ROT)
        if broken:
            ta, tb = broken
            a = (p0[0] + dx * ta, p0[1] + dy * ta)
            b = (p0[0] + dx * tb, p0[1] + dy * tb)
            mb.beam((p0[0], p0[1], deck - sag(p0[0]) + 0.95), (a[0], a[1], deck - sag(a[0]) + 0.95), 0.08, 0.08, ROT)
            mb.beam((a[0], a[1], deck - sag(a[0]) + 0.95), (a[0] + dx * 0.25, a[1] + dy * 0.25 - 0.1,
                    deck - sag(a[0]) + 0.1), 0.08, 0.08, ROT)
            mb.beam((b[0], b[1], deck - sag(b[0]) + 0.95), (p1[0], p1[1], deck - sag(p1[0]) + 0.95), 0.08, 0.08, ROT)
        else:
            mb.beam((p0[0], p0[1], deck - sag(p0[0]) + 0.95), (p1[0], p1[1], deck - sag(p1[0]) + 0.95), 0.08, 0.08, ROT)
        mb.beam((p0[0], p0[1], deck - sag(p0[0]) + 0.12), (p1[0], p1[1], deck - sag(p1[0]) + 0.12), 0.06, 0.06, ROT)

    rail((-px, py0 + 0.1), (-1.75, py0 + 0.1))
    rail((1.75, py0 + 0.1), (px, py0 + 0.1), broken=(0.35, 0.7))
    rail((-px, py1 - 0.1), (-px, py0 + 0.1), broken=(0.3, 0.55))
    rail((px, py0 + 0.1), (px, py1 - 0.1))

    # lean-to roof on four posts, right corner drooping (post broken)
    ztop, ln = 5.15, 4.2
    for x in (-5.8, -2.0, 2.0):
        mb.box((x, py0 + 0.15, (deck + 3.95 - sag(x) * 0.3) / 2), (0.2, 0.2, 3.95 - deck - sag(x) * 0.3), ROT)
        for s in (-1, 1):
            mb.beam((x, py0 + 0.15, 3.3), (x + s * 0.5, py0 + 0.15, 3.85), 0.1, 0.1, ROT)
    mb.box((5.8, py0 + 0.15, (deck - sag(5.8)) + 0.6), (0.2, 0.2, 1.2), ROT)
    rbox(mb, (5.75, py0 + 0.2, deck - sag(5.8) + 1.3), (0.2, 0.2, 0.25), ROT, pitch=25)
    mb.beam((5.75, py0 + 0.12, 3.35), (5.3, py0 + 0.4, 2.0), 0.2, 0.2, ROT)

    def droop(x):
        return 0.0 if x < 1.5 else 0.75 * ((x - 1.5) / 4.8) ** 1.5

    mb.beam((-6.3, py0 + 0.15, 3.97), (2.0, py0 + 0.15, 3.97), 0.22, 0.24, ROT)
    mb.beam((2.0, py0 + 0.15, 3.97), (6.3, py0 + 0.15, 3.97 - droop(6.3) * 0.85), 0.22, 0.24, ROT)
    strips = 14
    sw = 12.6 / strips
    base_a = math.degrees(math.atan2(ztop - 4.1, ln))
    for i in range(strips):
        x = -6.3 + sw * (i + 0.5)
        a = base_a + math.degrees(math.atan2(droop(x), ln))
        with mb.at((x, py1, ztop), rot_x=a):
            if i in (11,):
                for k in range(3):  # exposed rafters
                    mb.box((-sw / 2 + sw * (k + 0.5) / 3, -ln / 2, -0.12), (0.08, ln, 0.14), ROT)
                continue
            seg = ln if i != 12 else ln * 0.55
            mb.box((0, -seg / 2, -0.08), (sw + 0.02, seg, 0.16), "M_OldRoof", mats={"-z": ROT})
    # flickering wall lantern by the door
    with mb.at((1.95, TY0, FL + 2.9)), nc.at((1.95, TY0, FL + 2.9)):
        mb.box((0, -0.15, 0.0), (0.06, 0.3, 0.06), RUST)
        mb.box((0, -0.3, -0.25), (0.28, 0.28, 0.04), RUST)
        mb.box((0, -0.3, 0.25), (0.32, 0.32, 0.05), RUST)
        mb.pyramid((0, -0.3, 0.275), 0.32, 0.32, 0.2, RUST)
        nc.box((0, -0.3, 0.0), (0.2, 0.2, 0.46), "M_GhostGlow")


def _hall(mb, nc, rng):
    # chequered floor with broken tiles
    t = 0.8
    nx, ny = int(2 * HX / t), int(round((HY1 - HY0) / t))
    for i in range(nx):
        for j in range(ny):
            x0, y0 = -HX + i * t, HY0 + j * t
            r = rng.random()
            if r < 0.07:
                mat, z = "M_Soil", FL + 0.002
            else:
                mat, z = (TRIM if (i + j) % 2 == 0 else VOID), FL + 0.006
            mb.poly([(x0, y0, z), (x0 + t, y0, z), (x0 + t, y0 + t, z), (x0, y0 + t, z)], mat)
    # torn carpet runner door -> stairs
    for (y0, y1, w) in ((-10.3, -8.2, 1.6), (-8.0, -6.9, 1.45), (-6.6, -4.1, 1.6)):
        mb.poly([(-w / 2, y0, FL + 0.012), (w / 2, y0, FL + 0.012), (w / 2, y1, FL + 0.012), (-w / 2, y1, FL + 0.012)],
                "M_Carpet")
    # wainscot
    zw = FL + 0.95
    gap = SDW / 2 + 0.1   # side doorways (architraves sit in the gaps)
    for (ya, yb) in ((HY0, SDY - gap), (SDY + gap, HY1)):
        mb.box_mm((-HX - 0.02, ya, FL), (-HX + 0.05, yb, zw), "M_DarkWood")
        mb.box_mm((-HX - 0.02, ya, zw), (-HX + 0.08, yb, zw + 0.08), "M_DarkWood")
        mb.box_mm((HX - 0.05, ya, FL), (HX + 0.02, yb, zw), "M_DarkWood")
        mb.box_mm((HX - 0.08, ya, zw), (HX + 0.02, yb, zw + 0.08), "M_DarkWood")
    for (a, b) in ((-HX, -1.25), (1.25, HX)):
        mb.box_mm((a, HY0 - 0.02, FL), (b, HY0 + 0.05, zw), "M_DarkWood")
    for (a, b) in ((-HX, -3.5), (-1.9, 1.9), (3.5, HX)):   # back wall, gaps at the two doorways
        mb.box_mm((a, HY1 - 0.05, FL), (b, HY1 + 0.02, zw), "M_DarkWood")
    # ceiling beams, one fallen
    for y in (-9.0, -7.0, -5.0, -3.0, -1.0, 1.0, 3.0):
        if y == -9.0:   # cut back for the spiral stair, carried by a trimmer
            mb.box_mm((SPIRAL_HOLE[2], y - 0.15, HZ1 - 0.4), (HX, y + 0.15, HZ1), ROT)
            mb.box_mm((SPIRAL_HOLE[2], HY0, HZ1 - 0.36), (SPIRAL_HOLE[2] + 0.24, SPIRAL_HOLE[3] + 0.1, HZ1), ROT)
            continue
        if y == -3.0:
            mb.box_mm((-HX, y - 0.15, HZ1 - 0.4), (2.2, y + 0.15, HZ1), ROT)
            mb.beam((2.4, y, HZ1 - 0.25), (3.4, y - 1.9, FL + 0.15), 0.3, 0.35, ROT)
            continue
        mb.box_mm((-HX, y - 0.15, HZ1 - 0.4), (HX, y + 0.15, HZ1), ROT)
    # a hole in the ceiling (dark void) with hanging boards
    hole = [(1.0, -6.6), (2.6, -6.9), (3.7, -5.8), (3.4, -3.6), (1.8, -3.3), (0.8, -4.6)]
    mb.poly([(x, y, HZ1 - 0.01) for (x, y) in reversed(hole)], VOID)
    for (x, y, a) in ((1.3, -6.2, 25), (3.0, -4.0, -35), (2.0, -3.6, 15)):
        rbox(mb, (x, y, HZ1 - 0.7), (0.22, 0.05, 1.4), ROT, yaw=rng.uniform(0, 90), pitch=a)
    rubble(mb, (2.4, -5.2), 1.3, 14, rng, mats=(STONE, TRIM, ROT), zc=FL)
    planks(mb, (2.6, -5.0), 1.0, 5, rng, zc=FL)

    # ---- broken grand staircase up to a gallery
    # 20 risers of 0.18 m on 0.28 m treads (it used to be 18 x 0.2 / 0.31); treads 9-12 are gone
    run, rise, nst = (GAL_Y - (-4.0)) / 20, (GAL_Z - FL) / 20, 20
    sy0 = GAL_Y - run * nst
    G0, G1 = 9, 12
    for i in range(nst):
        y0, y1 = sy0 + run * i, sy0 + run * (i + 1)
        top = FL + rise * (i + 1)
        if G0 <= i <= G1:
            continue
        zb = FL if i < G0 else top - 0.22
        mb.box_mm((-1.2, y0, zb), (1.2, y1, top), "M_DarkWood")
        mb.box_mm((-0.7, y0, top), (0.7, y1 - 0.02, top + 0.01), "M_Carpet")
    for k in range(4):   # collapsed treads on the floor
        rbox(mb, (rng.uniform(-1.5, 1.8), rng.uniform(-2.2, -0.6), FL + 0.12 + 0.1 * k), (2.3, 0.32, 0.08),
             "M_DarkWood", yaw=rng.uniform(-40, 40), pitch=rng.uniform(-12, 12), roll=rng.uniform(-10, 10))
    rubble(mb, (0.0, -1.2), 1.2, 8, rng, mats=("M_DarkWood", TRIM), zc=FL)
    # stringers
    for sx in (-1, 1):
        a = (sx * 1.27, sy0 - 0.05, FL)
        b = (sx * 1.27, GAL_Y, GAL_Z)
        if sx < 0:
            mb.beam(a, b, 0.14, 0.32, "M_DarkWood")
        else:
            m1 = (sx * 1.27, sy0 + run * G0, FL + rise * G0)
            m2 = (sx * 1.27, sy0 + run * (G1 + 1), FL + rise * (G1 + 1))
            mb.beam(a, m1, 0.14, 0.32, "M_DarkWood")
            mb.beam((sx * 1.27, m2[1] - 0.2, m2[2] - 0.55), b, 0.14, 0.32, "M_DarkWood")
    # handrails + balusters (right one broken)
    missing = [rng.random() < 0.3 for _ in range(6)]   # same random draws as the old 18-step stair
    missing += [missing[k] for k in range(5)]
    for sx in (-1, 1):
        for k, i in enumerate(range(0, nst, 2)):
            if G0 - 1 <= i <= G1 + 1 or (sx > 0 and missing[k]):
                continue
            y = sy0 + run * (i + 0.5)
            top = FL + rise * (i + 1)
            mb.box((sx * 1.27, y, top + 0.45), (0.05, 0.05, 0.9), "M_DarkWood")
        r0, r1 = G0 - 1, G1 + 2
        if sx < 0:
            mb.beam((sx * 1.27, sy0, FL + 1.1), (sx * 1.27, sy0 + run * r0, FL + rise * r0 + 0.95), 0.08, 0.09, "M_DarkWood")
            mb.beam((sx * 1.27, sy0 + run * r1, FL + rise * r1 + 0.95), (sx * 1.27, GAL_Y, GAL_Z + 0.95),
                    0.08, 0.09, "M_DarkWood")
        else:
            mb.beam((sx * 1.27, sy0 + run * r1, FL + rise * r1 + 0.95), (sx * 1.27, GAL_Y, GAL_Z + 0.95),
                    0.08, 0.09, "M_DarkWood")
            mb.beam((sx * 1.27, sy0 + run * r1, FL + rise * r1 + 0.95), (1.9, sy0 + run * (G0 + 1), FL + 0.3),
                    0.08, 0.09, "M_DarkWood")
    # newel posts (right one toppled)
    mb.box((-1.3, sy0 - 0.1, FL + 0.65), (0.22, 0.22, 1.3), "M_DarkWood")
    mb.sphere((-1.3, sy0 - 0.1, FL + 1.42), 0.15, "M_DarkWood", seg=8, rings=6)
    rbox(mb, (2.1, sy0 - 0.6, FL + 0.12), (1.3, 0.22, 0.22), "M_DarkWood", yaw=30)
    mb.sphere((2.8, sy0 - 0.2, FL + 0.15), 0.15, "M_DarkWood", seg=8, rings=6)
    # gallery + balustrade + columns
    mb.box_mm((-HX, GAL_Y, GAL_Z - 0.25), (HX, HY1, GAL_Z), "M_DarkWood")
    mb.box_mm((-HX, GAL_Y - 0.06, GAL_Z - 0.4), (HX, GAL_Y + 0.02, GAL_Z - 0.05), TRIM)
    for sx in (-1, 1):
        mb.column((sx * 3.0, GAL_Y + 0.3, FL), 0.18, GAL_Z - 0.4 - FL, TRIM, seg=10)
        x0, x1 = sorted((sx * 1.3, sx * HX))
        x = x0
        while x <= x1:
            if not (sx > 0 and 2.3 < x < 3.2):
                mb.box((x, GAL_Y + 0.1, GAL_Z + 0.45), (0.05, 0.05, 0.9), "M_DarkWood")
            x += 0.25
        if sx < 0:
            mb.box_mm((x0, GAL_Y + 0.05, GAL_Z + 0.9), (x1, GAL_Y + 0.15, GAL_Z + 0.98), "M_DarkWood")
        else:
            mb.box_mm((x0, GAL_Y + 0.05, GAL_Z + 0.9), (2.3, GAL_Y + 0.15, GAL_Z + 0.98), "M_DarkWood")
            mb.beam((2.3, GAL_Y + 0.1, GAL_Z + 0.94), (2.9, GAL_Y - 0.5, FL + 0.1), 0.08, 0.08, "M_DarkWood")
    # doorway surrounds in the back wall (below and above the gallery) - real openings, see _shell
    with mb.at((0, HY1, 0)):
        for (u, z0, w, h) in ((2.7, FL, 1.3, 2.5), (-2.7, FL, 1.3, 2.5), (0.0, GAL_Z, 1.6, 2.8)):
            for s in (-1, 1):
                mb.box((u + s * (w / 2 + 0.08), -0.06, z0 + h / 2), (0.16, 0.12, h), "M_DarkWood", skip=("+y",))
            mb.box((u, -0.06, z0 + h + 0.1), (w + 0.4, 0.12, 0.2), "M_DarkWood", skip=("+y",))

    # ---- portrait (crooked, with glowing eyes) on the left wall, a fallen one on the right
    with mb.at((-HX + 0.01, -5.6, FL + 3.0), rot=90, rot_y=7), nc.at((-HX + 0.01, -5.6, FL + 3.0), rot=90, rot_y=7):
        fw, fh, b = 1.5, 2.0, 0.16
        mb.box((0, -0.02, 0), (fw - 2 * b, 0.04, fh - 2 * b), "M_PortraitCanvas")
        for s in (-1, 1):
            mb.box((s * (fw / 2 - b / 2), -0.05, 0), (b, 0.1, fh), "M_TarnishedGold")
            mb.box((0, -0.05, s * (fh / 2 - b / 2)), (fw - 2 * b, 0.1, b), "M_TarnishedGold")
        mb.sphere((0, -0.04, 0.25), 0.3, "M_PortraitFace", seg=10, rings=6, scale=(0.8, 0.15, 1.0))
        mb.box((0, -0.04, -0.45), (0.9, 0.03, 0.6), "M_Black")
        for s in (-1, 1):
            nc.box((s * 0.09, -0.1, 0.3), (0.05, 0.02, 0.025), "M_GhostGlow")
    with mb.at((HX - 0.35, -0.55, FL), rot=-90, rot_x=-12):
        fw, fh, b = 1.2, 1.6, 0.14
        mb.box((0, 0, fh / 2), (fw - 2 * b, 0.04, fh - 2 * b), "M_PortraitCanvas")
        for s in (-1, 1):
            mb.box((s * (fw / 2 - b / 2), -0.03, fh / 2), (b, 0.1, fh), "M_TarnishedGold")
            mb.box((0, -0.03, fh / 2 + s * (fh / 2 - b / 2)), (fw - 2 * b, 0.1, b), "M_TarnishedGold")

    # ---- toppled chair, broken chair, fallen chandelier
    def chair(mb_):
        mb_.box((0, 0, 0.47), (0.5, 0.5, 0.06), "M_DarkWood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb_.box((sx * 0.21, sy * 0.21, 0.22), (0.06, 0.06, 0.44), "M_DarkWood")
            mb_.box((sx * 0.21, 0.22, 0.75), (0.06, 0.06, 0.6), "M_DarkWood")
        mb_.box((0, 0.22, 0.9), (0.45, 0.04, 0.3), "M_Carpet")
        mb_.box((0, 0.22, 1.06), (0.5, 0.06, 0.06), "M_DarkWood")

    with mb.at((2.4, -2.6, FL + 0.27), rot=-35, rot_x=-90):
        chair(mb)
    with mb.at((-3.3, -0.6, FL), rot=60, rot_y=6):
        chair(mb)
    with mb.at((-2.3, -6.9, FL + 0.08), rot=20, rot_x=10):
        mb.torus((0, 0, 0.2), 0.85, 0.05, "M_TarnishedGold", seg=16, tube_seg=5)
        mb.torus((0, 0, 0.5), 0.45, 0.04, "M_TarnishedGold", seg=12, tube_seg=5)
        mb.cylinder((0, 0, 0.0), 0.08, 0.9, "M_TarnishedGold", seg=8)
        for k in range(6):
            a = math.tau * k / 6
            mb.beam((0, 0, 0.6), (math.cos(a) * 0.85, math.sin(a) * 0.85, 0.2), 0.04, 0.04, "M_TarnishedGold")
            mb.cylinder((math.cos(a) * 0.85, math.sin(a) * 0.85, 0.22), 0.05, 0.18, "M_ShojiPaper", seg=6)
    mb.box((-2.1, -6.9, HZ1 - 0.7), (0.05, 0.05, 1.4), RUST)  # broken chain stub
    # debris piles along the walls
    rubble(mb, (-3.3, -4.4), 0.7, 7, rng, zc=FL)
    rubble(mb, (3.1, 0.9), 0.9, 8, rng, zc=FL)
    planks(mb, (-3.0, -6.5), 0.8, 4, rng, zc=FL, length=(0.8, 1.8))
    # a dusty side table, knocked over
    with mb.at((3.2, -9.0, FL + 0.3), rot=-20, rot_y=90):
        mb.box((0, 0, 0.72), (0.9, 0.6, 0.05), "M_DarkWood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * 0.38, sy * 0.24, 0.35), (0.05, 0.05, 0.7), "M_DarkWood")
    # (the front door leaves are an automatic "abandoned" door now, see _sockets)
    # someone laid planks over the missing treads of the staircase - the only way up to the gallery
    ya, za = sy0 + run * (G0 - 0.4), FL + rise * G0 + 0.03
    yb, zb = sy0 + run * (G1 + 1.4), FL + rise * (G1 + 1) + 0.03
    for k, x in enumerate((-0.78, -0.45, -0.12)):
        dy = (-0.04, 0.05, 0.0)[k]
        mb.beam((x, ya + dy, za), (x, yb + dy, zb), 0.31, 0.05, ROT)
        for (yy, zz) in ((ya + 0.12 + dy, za + 0.04), (yb - 0.12 + dy, zb + 0.04)):
            mb.box((x, yy, zz), (0.05, 0.05, 0.02), RUST)   # nail heads


# ---------------------------------------------------------------- interiors: dressing helpers
def _cobwebs(nc, x0, y0, x1, y1, z, rng, size=(0.5, 0.9)):
    """Cobwebs in the four upper corners of a room: radial threads fanning out of the corner, sagging
    spiral threads between them and a faint veil."""
    W = "M_Cobweb"
    for (cx, cy, ux, uy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1)):
        s = rng.uniform(*size)
        a = (cx + ux * s, cy, z - 0.01)                                  # along wall 1
        b = (cx, cy + uy * s, z - 0.01)                                  # along wall 2
        d = (cx, cy, z - s * rng.uniform(0.8, 1.1))                      # down the corner
        m = (cx + ux * s * 0.5, cy + uy * s * 0.5, z - s * 0.55)         # out into the room
        anchors = [a, ((a[0] + m[0]) / 2, (a[1] + m[1]) / 2, (a[2] + m[2]) / 2 + 0.05), m,
                   ((b[0] + m[0]) / 2, (b[1] + m[1]) / 2, (b[2] + m[2]) / 2 + 0.05), b, d]
        hub = (cx + ux * 0.04, cy + uy * 0.04, z - 0.05)
        for p in anchors:
            nc.beam(hub, p, 0.007, 0.007, W)
        for t in (0.3, 0.55, 0.8):
            pts = [(hub[0] + (p[0] - hub[0]) * t, hub[1] + (p[1] - hub[1]) * t, hub[2] + (p[2] - hub[2]) * t - 0.02 * t)
                   for p in (a, m, b)]
            nc.beam(pts[0], pts[1], 0.006, 0.006, W)
            nc.beam(pts[1], pts[2], 0.006, 0.006, W)
        nc.poly([a, m, b], "M_CobwebVeil")
        nc.poly([b, m, a], "M_CobwebVeil")


def _candle(nc, x, y, z, h=0.18, r=0.024):
    nc.cylinder((x, y, z), r, h, "M_CandleWax", seg=6)
    nc.cylinder((x, y, z), r * 1.6, 0.012, "M_CandleWax", seg=6)          # wax puddle
    nc.cone((x, y, z + h + 0.004), r * 0.65, 0.07, "M_CandleFlame", seg=5)


def _candles(nc, x, y, z, rng, n=3):
    for k in range(n):
        a = rng.uniform(0, math.tau)
        r = 0.0 if k == 0 else rng.uniform(0.06, 0.12)
        _candle(nc, x + math.cos(a) * r, y + math.sin(a) * r, z, h=rng.uniform(0.08, 0.26))


def _boarded_inside(mb, nc, x, y, yaw, w, z0, h, rng):
    """Inside of a boarded window on a solid wall: dark reveal, boards nailed across, moonlight leaking
    through the gaps. (x, y) = point on the inner wall face, local -Y points into the room."""
    with mb.at((x, y, 0.0), rot=yaw), nc.at((x, y, 0.0), rot=yaw):
        nc.box((0, -0.01, z0 + h / 2), (w, 0.02, h), "M_MoonSlit")
        for s in (-1, 1):
            mb.box((s * (w / 2 + 0.06), -0.04, z0 + h / 2), (0.12, 0.08, h + 0.12), "M_DarkWood")
        mb.box((0, -0.04, z0 + h + 0.06), (w + 0.24, 0.08, 0.12), "M_DarkWood")
        mb.box((0, -0.09, z0 - 0.04), (w + 0.34, 0.18, 0.08), "M_DarkWood")         # sill
        n = 5
        for i in range(n):
            if rng.random() < 0.12:
                continue
            zz = z0 + h * (i + 0.5) / n + rng.uniform(-0.04, 0.04)
            rbox(mb, (rng.uniform(-0.05, 0.05), -0.05, zz), (w + 0.3, 0.035, h / n - 0.07), BOARD,
                 pitch=rng.uniform(-7, 7))


def _portrait(mb, nc, x, y, zc, yaw, w, h, eyes=False, tilt=0.0, sitter=True, canvas="M_PortraitCanvas"):
    """Gilded portrait hanging on a wall: (x, y) on the wall face, local -Y into the room, zc = centre."""
    b = min(0.14, w * 0.12)
    with mb.at((x, y, zc), rot=yaw, rot_y=tilt), nc.at((x, y, zc), rot=yaw, rot_y=tilt):
        mb.box((0, -0.025, 0), (w - 2 * b, 0.03, h - 2 * b), canvas)
        for s in (-1, 1):
            mb.box((s * (w / 2 - b / 2), -0.05, 0), (b, 0.08, h), "M_TarnishedGold")
            mb.box((0, -0.05, s * (h / 2 - b / 2)), (w - 2 * b, 0.08, b), "M_TarnishedGold")
        if sitter:
            hs = min(w, h) * 0.2
            mb.sphere((0, -0.045, h * 0.12), hs, "M_PortraitFace", seg=10, rings=6, scale=(0.8, 0.12, 1.0))
            mb.box((0, -0.045, -h * 0.24), (w * 0.62, 0.025, h * 0.32), "M_Black")
            if eyes:
                for s in (-1, 1):
                    nc.box((s * hs * 0.32, -0.075, h * 0.12 + hs * 0.15), (hs * 0.2, 0.01, hs * 0.1), "M_GhostGlow")


def _old_bookcase(mb, nc, rng, w=1.0, d=0.36, h=2.1, shelves=5, fill=0.8):
    """Dusty bookcase in the CURRENT local frame: origin bottom centre, back at +Y, books in muted colours,
    some leaning or fallen over."""
    mb.box((0, d / 2 - 0.01, h / 2), (w, 0.02, h), "M_DarkWood")
    for s in (-1, 1):
        mb.box((s * (w / 2 - 0.02), 0, h / 2), (0.04, d, h), "M_DarkWood")
    for k in range(shelves + 1):
        mb.box((0, 0, 0.05 + (h - 0.07) * k / shelves), (w - 0.04, d, 0.03), "M_DarkWood")
    mb.box((0, 0, h + 0.03), (w + 0.08, d + 0.06, 0.06), "M_DarkWood")
    for k in range(shelves):
        z = 0.065 + (h - 0.07) * k / shelves
        sh = (h - 0.07) / shelves - 0.05
        bx = -w / 2 + 0.05
        while bx < w / 2 - 0.08:
            if rng.random() > fill:
                bx += rng.uniform(0.08, 0.2)
                continue
            bw = rng.uniform(0.03, 0.06)
            bh = min(sh, rng.uniform(0.17, 0.28))
            lean = rng.random() < 0.08
            rbox(nc, (bx + bw / 2 + (bh * 0.25 if lean else 0), 0.0, z + bh / 2 - (0.02 if lean else 0)),
                 (bw, d * 0.75, bh), rng.choice(OLD_BOOKS), pitch=(28 if lean else 0))
            bx += bw + 0.004 + (bh * 0.4 if lean else 0)


def _spilled_books(nc, cx, cy, z, r, n, rng):
    for _ in range(n):
        a = rng.uniform(0, math.tau)
        rr = r * math.sqrt(rng.random())
        th = rng.uniform(0.03, 0.06)
        rbox(nc, (cx + math.cos(a) * rr, cy + math.sin(a) * rr, z + th / 2), (rng.uniform(0.15, 0.24), rng.uniform(0.2, 0.3), th),
             rng.choice(OLD_BOOKS), yaw=rng.uniform(0, 180))
        if rng.random() < 0.3:   # an open book
            nc.box((cx + math.cos(a) * rr + 0.25, cy + math.sin(a) * rr, z + 0.012), (0.34, 0.22, 0.02), "M_OldPaper")


def _papers(nc, cx, cy, z, r, n, rng):
    for _ in range(n):
        a = rng.uniform(0, math.tau)
        rr = r * math.sqrt(rng.random())
        rbox(nc, (cx + math.cos(a) * rr, cy + math.sin(a) * rr, z + 0.003), (0.21, 0.29, 0.004), "M_OldPaper",
             yaw=rng.uniform(0, 180))


def _toppled_chair(mb, pos, yaw, rng):
    with mb.at(pos, rot=yaw), mb.at((0, 0, 0.25), rot_x=-90 + rng.uniform(-6, 6)):
        mb.box((0, 0, 0.47), (0.46, 0.46, 0.05), "M_DarkWood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * 0.2, sy * 0.2, 0.22), (0.05, 0.05, 0.44), "M_DarkWood")
            mb.box((sx * 0.2, 0.2, 0.75), (0.05, 0.05, 0.6), "M_DarkWood")
        mb.box((0, 0.2, 0.95), (0.46, 0.05, 0.12), "M_DarkWood")


def _sheeted(mb, x, y, z, yaw, w, d, h, kind="chair"):
    """Furniture hidden under a dust sheet (front = local -Y)."""
    S = "M_DustSheet"
    with mb.at((x, y, z), rot=yaw):
        mb.box((0, 0, 0.05), (w + 0.1, d + 0.1, 0.1), S)                        # sheet skirt on the floor
        mb.box((0, 0, 0.26), (w, d, 0.32), S)                                    # seat
        mb.box((0, d / 2 - 0.13, (0.42 + h) / 2), (w - 0.04, 0.26, h - 0.42), S)  # backrest
        mb.box((0, d / 2 - 0.16, h + 0.02), (w - 0.18, 0.2, 0.06), S)
        for s in (-1, 1):                                                        # arms
            mb.box((s * (w / 2 - 0.1), -0.03, 0.5), (0.2, d - 0.06, 0.36), S)
        if kind == "sofa":
            for s in (-1, 1):
                mb.box((s * w * 0.18, -0.05, 0.43), (w * 0.3, d - 0.4, 0.04), S)  # sagging cushions


def _cold_fireplace(mb, nc, x, y, yaw, rng):
    """Stone fireplace against a wall (back at +Y), long dead: ash, charred logs, a cracked mirror-less
    over-mantel. Origin on the wall face at the room floor."""
    with mb.at((x, y, FZ), rot=yaw), nc.at((x, y, FZ), rot=yaw):
        mb.box((0, -0.2, 0.65), (1.9, 0.4, 1.3), TRIM)
        mb.box((0, -0.24, 1.38), (2.2, 0.56, 0.12), "M_DarkWood")                 # mantel shelf
        mb.box((0, -0.41, 0.48), (1.0, 0.02, 0.86), VOID)                         # firebox
        mb.box((0, -0.55, 0.04), (2.1, 0.7, 0.08), TRIM)                          # hearth
        mb.box((0, -0.42, 0.93), (1.2, 0.05, 0.1), "M_TarnishedGold")
        nc.box((0, -0.5, 0.085), (0.9, 0.3, 0.01), "M_Soil")                      # ash
        for k in range(3):
            rbox(nc, (-0.2 + 0.2 * k, -0.48, 0.13), (0.5, 0.09, 0.09), "M_Black", yaw=rng.uniform(-30, 30))


def _hanging_chandelier(mb, x, y, zc, tilt=8.0):
    """Dead brass chandelier hanging crooked from the ceiling (no light)."""
    with mb.at((x, y, zc), rot_y=tilt):
        mb.cylinder((0, 0, -0.9), 0.015, 0.9, RUST, seg=5)
        mb.cylinder((0, 0, -1.3), 0.05, 0.42, "M_TarnishedGold", seg=8)
        mb.torus((0, 0, -1.25), 0.45, 0.025, "M_TarnishedGold", seg=14, tube_seg=4)
        for k in range(6):
            a = math.tau * k / 6
            mb.beam((0, 0, -1.05), (math.cos(a) * 0.45, math.sin(a) * 0.45, -1.25), 0.025, 0.025, "M_TarnishedGold")
            if k % 3:
                mb.cylinder((math.cos(a) * 0.45, math.sin(a) * 0.45, -1.24), 0.022, 0.1, "M_CandleWax", seg=5)
        mb.torus((0, 0, -0.95), 0.2, 0.02, "M_TarnishedGold", seg=10, tube_seg=4)


def _ring(nc, cx, cy, r, w, z, mat, seg=32):
    for i in range(seg):
        a0, a1 = math.tau * i / seg, math.tau * (i + 1) / seg
        p = [(cx + math.cos(a) * rr, cy + math.sin(a) * rr) for (a, rr) in ((a0, r - w / 2), (a0, r + w / 2),
                                                                              (a1, r + w / 2), (a1, r - w / 2))]
        nc.poly([(p[0][0], p[0][1], z), (p[1][0], p[1][1], z), (p[2][0], p[2][1], z), (p[3][0], p[3][1], z)], mat)


def _line(nc, p, q, w, z, mat):
    dx, dy = q[0] - p[0], q[1] - p[1]
    ln = math.hypot(dx, dy)
    nx, ny = -dy / ln * w / 2, dx / ln * w / 2
    nc.poly([(p[0] - nx, p[1] - ny, z), (q[0] - nx, q[1] - ny, z), (q[0] + nx, q[1] + ny, z), (p[0] + nx, p[1] + ny, z)], mat)


def _rect(nc, x0, y0, x1, y1, w, z, mat):
    for (p, q) in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        dx, dy = q[0] - p[0], q[1] - p[1]
        ln = math.hypot(dx, dy)
        ext = (dx / ln * w / 2, dy / ln * w / 2)
        _line(nc, (p[0] - ext[0], p[1] - ext[1]), (q[0] + ext[0], q[1] + ext[1]), w, z, mat)


def _room_wainscot(mb, x0, y0, x1, y1, z, h, gaps=None):
    """Dark panelling around a room; gaps: dict side -> list of (a, b) along that wall (from its start)."""
    gaps = gaps or {}
    for k, (p0, p1) in (("s", ((x0, y0), (x1, y0))), ("e", ((x1, y0), (x1, y1))), ("n", ((x1, y1), (x0, y1))),
                        ("w", ((x0, y1), (x0, y0)))):
        K.wainscot(mb, p0, p1, z, h, "M_IntWoodDark", cap="M_DarkWood", gaps=gaps.get(k, ()))


def _beams(mb, x0, y0, x1, y1, z, step=1.9, along="x"):
    if along == "x":
        y = y0 + step / 2
        while y < y1 - 0.2:
            mb.box_mm((x0, y - 0.12, z - 0.28), (x1, y + 0.12, z), "M_DarkWood")
            y += step
    else:
        x = x0 + step / 2
        while x < x1 - 0.2:
            mb.box_mm((x - 0.12, y0, z - 0.28), (x + 0.12, y1, z), "M_DarkWood")
            x += step


WARM = (1.0, 0.62, 0.32)
MOON = (0.55, 0.65, 1.0)
PURPLE = (0.6, 0.4, 1.0)


# ---------------------------------------------------------------- interiors: rooms
def _library(aset, mb, nc, rng):
    x0, y0, x1, y1 = LIB
    K.floor_planks(mb, x0, y0, x1, y1, FZ, mat="M_IntWoodFloorDark", seam=VOID, along="y")
    _room_wainscot(mb, x0, y0, x1, y1, FZ, 1.0, gaps={"e": [(SDY - y0 - SDW / 2 - 0.12, SDY - y0 + SDW / 2 + 0.12)],
                                                      "w": [(y1 - GF_DOOR_SIDE[-1] - 0.6, y1 - GF_DOOR_SIDE[-1] + 0.6)],
                                                      "n": [(x1 + GF_DOOR_BACK[-1] - 0.6, x1 + GF_DOOR_BACK[-1] + 0.6)]})
    _beams(mb, x0, y0, x1, y1, CZ1)
    K.rug(nc, -11.0, -3.3, -8.6, 0.5, FZ, "M_Carpet", "M_TarnishedGold")
    # boarded windows of the front facade, seen from inside
    for x in (-10.5, -6.9):
        _boarded_inside(mb, nc, x, y0, 180.0, 1.25, 1.5, 2.2, rng)
    aset.light((-8.7, y0 + 0.8, 2.6), MOON, 450.0, 6.0)
    # west wall: cold fireplace under the old headmaster's portrait (his eyes follow you)
    _cold_fireplace(mb, nc, x0, -1.4, 90.0, rng)
    _portrait(mb, nc, x0, -1.4, FZ + 2.45, 90.0, 1.1, 1.3, eyes=True, tilt=-4.0)
    aset.light((x0 + 0.5, -1.4, FZ + 2.6), PURPLE, 250.0, 3.0)
    for dy in (-0.75, 0.75):
        aset.prop("SM_Int_Candelabra", (x0 + 0.22, -1.4 + dy, FZ + 1.44), 90.0)
    _candles(nc, x0 + 0.3, -1.1, FZ + 1.44, rng, 2)
    aset.prop("SM_Int_Armchair", (-10.0, -0.3, FZ), -90.0 - 25.0)
    aset.prop("SM_Int_RockingChair", (-10.1, -2.6, FZ), -90.0 + 20.0)
    aset.prop("SM_Int_SideTable", (-10.7, -1.45, FZ), 0.0)
    aset.prop("SM_Int_OilLamp", (-10.7, -1.45, FZ + 0.55), 0.0)
    aset.light((-10.4, -1.45, FZ + 1.1), WARM, 650.0, 6.0)
    # bookcases: catalog shelves along the north and west walls, our own dusty ones toppled in the room
    for x in (-11.4, -10.35, -9.3, -6.9):
        with mb.at((x, y1 - 0.19, FZ)), nc.at((x, y1 - 0.19, FZ)):
            _old_bookcase(mb, nc, rng, fill=0.85)
    for y in (1.15, 2.6, -4.45, -5.9):
        aset.prop("SM_Int_Bookshelf", (x0 + 0.32, y, FZ), 90.0)
    with mb.at((-8.15, y1 - 0.4, FZ), rot=0), nc.at((-8.15, y1 - 0.4, FZ), rot=0):
        with mb.at((0, 0, 0.18), rot_x=84), nc.at((0, 0, 0.18), rot_x=84):     # fell forward off the wall
            _old_bookcase(mb, nc, rng)
    _spilled_books(nc, -8.2, 1.0, FZ, 0.9, 14, rng)
    with mb.at((-10.8, -6.2, FZ), rot=75), nc.at((-10.8, -6.2, FZ), rot=75):
        with mb.at((0, 0, 0.18), rot_x=86), nc.at((0, 0, 0.18), rot_x=86):
            _old_bookcase(mb, nc, rng, fill=0.5)
    _spilled_books(nc, -9.3, -5.6, FZ, 0.8, 10, rng)
    # library ladder against the shelves
    for dx in (-0.22, 0.22):
        mb.beam((-10.85 + dx, y1 - 1.05, FZ), (-10.85 + dx, y1 - 0.42, FZ + 2.3), 0.05, 0.06, "M_DarkWood")
    for k in range(1, 7):
        t = k / 7
        mb.box((-10.85, y1 - 1.05 + 0.63 * t, FZ + 2.3 * t), (0.44, 0.04, 0.04), "M_DarkWood")
    # reading table with an open book, an oil lamp and a knocked-over chair
    aset.prop("SM_Int_RoundTableB", (-7.6, -4.6, FZ), 90.0)
    aset.prop("SM_Int_WoodChair", (-8.35, -4.75, FZ), -90.0)
    aset.prop("SM_Int_WoodChair", (-6.85, -4.3, FZ), 90.0 + 12.0)
    _toppled_chair(mb, (-6.6, -5.6, FZ), 30.0, rng)
    aset.prop("SM_Int_OilLamp", (-7.45, -4.35, FZ + 0.75), 0.0)
    aset.prop("SM_Int_Books", (-7.75, -4.85, FZ + 0.75), 90.0)
    nc.box((-7.6, -4.6, FZ + 0.76), (0.42, 0.3, 0.02), "M_OldPaper")
    _papers(nc, -7.2, -3.4, FZ, 1.0, 9, rng)
    aset.light((-7.6, -4.2, FZ + 1.2), WARM, 600.0, 6.0)
    # globe, grandfather clock (stopped at midnight), bust on a plinth
    with mb.at((-5.6, 1.6, FZ)):
        mb.cylinder((0, 0, 0), 0.25, 0.05, "M_DarkWood", seg=8)
        mb.cylinder((0, 0, 0.05), 0.04, 0.75, "M_DarkWood", seg=6)
        mb.torus((0, 0, 1.08), 0.33, 0.02, "M_TarnishedGold", seg=14, tube_seg=4)
        mb.sphere((0, 0, 1.08), 0.3, "M_OldBookBlue", seg=12, rings=8)
        mb.sphere((0.05, -0.02, 1.12), 0.302, "M_OldPaper", seg=6, rings=4, scale=(0.6, 1.0, 0.7))
    aset.prop("SM_Int_GrandfatherClock", (-5.75, y0 + 0.25, FZ), 180.0)
    mb.box((-11.5, -6.85, FZ + 0.5), (0.5, 0.5, 1.0), TRIM)
    aset.prop("SM_Int_Bust", (-11.5, -6.85, FZ + 1.0), 45.0)
    _cobwebs(nc, x0, y0, x1, y1, CZ1 - 0.28, rng)
    K.nameplate(mb, aset, -HX, SDY + SDW / 2 + 0.45, FL + 1.75, 90.0, "LIBRARY", mat="M_TarnishedGold",
                color=(0.12, 0.08, 0.05))
    K.camera(aset, "library", (-5.1, -6.85, FZ + 1.75), (-11.0, 2.0, FZ + 0.8), 16.0)


def _salon(aset, mb, nc, rng):
    x0, y0, x1, y1 = SAL
    K.floor_planks(mb, x0, y0, x1, y1, FZ, mat="M_IntWoodFloorDark", seam=VOID)
    _room_wainscot(mb, x0, y0, x1, y1, FZ, 1.0, gaps={"w": [(y1 - SDY - SDW / 2 - 0.12, y1 - SDY + SDW / 2 + 0.12)],
                                                      "n": [(x1 - GF_DOOR_BACK[1] - 0.6, x1 - GF_DOOR_BACK[1] + 0.6)],
                                                      "e": [(GF_DOOR_SIDE[1] - y0 - 0.6, GF_DOOR_SIDE[1] - y0 + 0.6)]})
    _beams(mb, x0, y0, x1, y1, CZ1, along="y")
    K.rug(nc, 6.0, -5.6, 10.8, -1.4, FZ, "M_Carpet", "M_TarnishedGold")
    for x in (6.9, 10.5):
        _boarded_inside(mb, nc, x, y0, 180.0, 1.25, 1.5, 2.2, rng)
    aset.light((8.7, y0 + 0.8, 2.6), MOON, 450.0, 6.0)
    # the portrait gallery: former dorm masters along the north wall, one frame left empty
    for k, x in enumerate((5.7, 7.5, 9.3, 11.0)):
        if k == 1:   # (the doorway to the old kitchen is here now)
            continue
        _portrait(mb, nc, x, y1, FZ + 2.15, 0.0, 0.95, 1.25, eyes=(k == 2), tilt=(0.0, 0.0, 0.0, -9.0)[k])
    # the founder above the console on the east wall - with glowing eyes
    _portrait(mb, nc, x1, -1.5, FZ + 2.25, -90.0, 1.5, 1.9, eyes=True)
    aset.light((x1 - 0.6, -1.5, FZ + 2.5), PURPLE, 300.0, 3.5)
    aset.prop("SM_Int_Console", (x1 - 0.32, -1.5, FZ), -90.0)
    for dy in (-0.45, 0.45):
        aset.prop("SM_Int_Candelabra", (x1 - 0.3, -1.5 + dy, FZ + 0.95), -90.0)
    _candles(nc, x1 - 0.35, -1.5, FZ + 0.95, rng, 3)
    aset.light((x1 - 0.7, -1.5, FZ + 1.3), WARM, 700.0, 6.5)
    # dust-sheeted sitting group around a coffee table, a forgotten tea set
    _sheeted(mb, 8.4, -5.7, FZ, 180.0, 2.1, 0.9, 0.85, kind="sofa")
    _sheeted(mb, 6.6, -3.5, FZ, 90.0, 0.95, 0.85, 0.95)
    _sheeted(mb, 10.4, -3.4, FZ, -90.0, 0.95, 0.85, 0.95)
    aset.prop("SM_Int_CoffeeTable", (8.4, -3.6, FZ), 0.0)
    aset.prop("SM_Int_TeaSet", (8.3, -3.6, FZ + 0.49), 20.0)
    _candle(nc, 8.75, -3.35, FZ + 0.49, h=0.12)
    aset.light((8.6, -3.5, FZ + 0.9), WARM, 380.0, 4.0)
    # grand piano, half covered, and a crooked dead chandelier
    with mb.at((0, 0, FZ)), nc.at((0, 0, FZ)):
        K.piano(mb, nc, 9.6, 1.5, 0.0)
        rbox(nc, (9.9, 2.0, 1.03), (1.2, 1.3, 0.03), "M_DustSheet", yaw=12.0)
        rbox(nc, (10.45, 2.1, 0.75), (0.03, 1.1, 0.55), "M_DustSheet", yaw=12.0)
    _hanging_chandelier(mb, 8.4, -2.4, CZ1, tilt=9.0)
    aset.prop("SM_Int_Mirror", (x0, 1.6, FZ + 0.9), 90.0)
    aset.prop("SM_Int_GrandfatherClock", (8.7, y0 + 0.18, FZ), 180.0)
    aset.prop("SM_Int_GreenChair", (5.4, 2.9, FZ), 135.0)
    # a portrait that fell off the wall, leaning against the corner
    with mb.at((11.4, 3.3, FZ), rot=-35, rot_x=-14):
        mb.box((0, 0, 0.65), (0.72, 0.03, 1.0), "M_PortraitCanvas")
        for s in (-1, 1):
            mb.box((s * 0.42, -0.02, 0.65), (0.12, 0.07, 1.3), "M_TarnishedGold")
            mb.box((0, -0.02, 0.65 + s * 0.59), (0.72, 0.07, 0.12), "M_TarnishedGold")
    _papers(nc, 7.0, 0.2, FZ, 1.2, 6, rng)
    _cobwebs(nc, x0, y0, x1, y1, CZ1 - 0.28, rng)
    K.nameplate(mb, aset, HX, SDY + SDW / 2 + 0.45, FL + 1.75, -90.0, "SALON", mat="M_TarnishedGold",
                color=(0.12, 0.08, 0.05))
    K.camera(aset, "portraits", (5.2, -6.85, FZ + 1.75), (11.0, 2.2, FZ + 1.3), 16.0)


def _ritual_room(aset, mb, nc, rng):
    x0, y0, x1, y1 = RIT
    K.floor_planks(mb, x0, y0, x1, y1, FZ, mat="M_RottenWood", seam=VOID)
    _room_wainscot(mb, x0, y0, x1, y1, FZ, 0.16, gaps={"s": [(0.5, 2.1), (5.9, 7.5)], "n": [(2.75, 5.25)]})
    _beams(mb, x0, y0, x1, y1, CZ1, step=1.6, along="y")
    # the shadow duel field, drawn in chalk that still glows faintly
    z = FZ + 0.004
    C = "M_ChalkGlow"
    cx, cy = 0.0, 7.0
    _rect(nc, cx - 3.0, cy - 1.5, cx + 3.0, cy + 1.5, 0.05, z, C)
    _rect(nc, cx - 3.15, cy - 1.65, cx + 3.15, cy + 1.65, 0.025, z, C)
    _line(nc, (cx, cy - 1.5), (cx, cy - 0.75), 0.04, z, C)
    _line(nc, (cx, cy + 0.75), (cx, cy + 1.5), 0.04, z, C)
    for side in (-1, 1):
        for off in (1.1, 2.0):
            for k in range(5):
                zy = cy - 1.1 + k * 0.55
                _rect(nc, side * off - 0.2, zy - 0.17, side * off + 0.2, zy + 0.17, 0.025, z, C)
        _ring(nc, side * 2.65, cy, 0.25, 0.04, z, C, seg=16)
    _ring(nc, cx, cy, 0.72, 0.045, z, C, seg=36)
    star = [(cx + math.cos(math.radians(90 + 144 * k)) * 0.68, cy + math.sin(math.radians(90 + 144 * k)) * 0.68)
            for k in range(6)]
    for k in range(5):
        _line(nc, star[k], star[k + 1], 0.035, z, C)
    # scattered cards around the field
    for _ in range(16):
        a = rng.uniform(0, math.tau)
        r = rng.uniform(0.3, 2.2)
        rbox(nc, (cx + math.cos(a) * r * 1.4, cy + math.sin(a) * r * 0.6, FZ + 0.006), (0.06, 0.088, 0.003),
             rng.choice(("M_CardBack", "M_CardBack", "M_OldPaper")), yaw=rng.uniform(0, 180))
    # candles around it
    for (x, y) in ((-3.45, 6.0), (-3.45, 8.0), (3.45, 6.0), (3.45, 8.0), (-1.6, 8.95), (1.6, 8.95)):
        _candles(nc, x, y, FZ, rng, 3)
    aset.prop("SM_Int_Candelabra", (3.5, 7.0, FZ), 0.0)
    # altar on the west wall: stone slab, black cloth, the cursed card on a stand
    mb.box_mm((x0, 6.2, FZ), (x0 + 0.6, 7.8, FZ + 0.85), TRIM)
    mb.box_mm((x0, 6.15, FZ + 0.85), (x0 + 0.66, 7.85, FZ + 0.92), STONE)
    nc.box_mm((x0, 6.5, FZ + 0.6), (x0 + 0.68, 7.5, FZ + 0.925), "M_Black")
    with nc.at((x0 + 0.35, 7.0, FZ + 0.925), rot=90.0, rot_x=-12):
        nc.box((0, 0.03, 0.09), (0.15, 0.03, 0.18), "M_DarkWood")
        nc.box((0, 0.0, 0.11), (0.12, 0.006, 0.17), "M_GhostGlow")
    for dy in (-0.55, 0.55):
        aset.prop("SM_Int_Candelabra", (x0 + 0.3, 7.0 + dy, FZ + 0.92), 90.0)
    _candles(nc, x0 + 0.3, 6.6, FZ + 0.92, rng, 2)
    aset.light((x0 + 0.8, 7.0, FZ + 1.4), WARM, 450.0, 4.5)
    # east wall: the rule of the shadow game, scrawled in red; an old trunk with a suitcase on it
    for k, line in enumerate(("THE ONE WHO LOSES", "LOSES THEIR SOUL")):
        aset.text(line, K.wall_point(x1, 7.0, -90.0, 0.02, FZ + 2.25 - k * 0.36), -90.0, size=0.24,
                  color=(0.55, 0.03, 0.04))
    mb.box_mm((x1 - 0.55, 8.2, FZ), (x1 - 0.02, 9.25, FZ + 0.55), "M_DarkWood")
    mb.box_mm((x1 - 0.57, 8.18, FZ + 0.3), (x1, 9.27, FZ + 0.34), RUST)
    aset.prop("SM_Int_Suitcase", (x1 - 0.3, 8.45, FZ + 0.55), -90.0)
    aset.prop("SM_Int_Box", (x1 - 0.3, 9.02, FZ + 0.55), 10.0)
    # light: the faint purple of the field + candles
    aset.light((cx, cy, FZ + 0.7), PURPLE, 900.0, 7.0)
    aset.light((-3.3, 7.0, FZ + 0.6), WARM, 350.0, 4.0)
    aset.light((3.3, 7.0, FZ + 0.6), WARM, 350.0, 4.0)
    aset.interact("duel_field", (cx, cy, FZ + 0.5), 0.0, title="Shadow Duel Field",
                  text="A duel field drawn in chalk. The candles are still burning... who lit them?", radius=4.0)
    _cobwebs(nc, x0, y0, x1, y1, CZ1 - 0.28, rng)
    _ritual_extras(aset, mb, nc, rng)
    K.camera(aset, "ritual", (-3.4, 9.0, FZ + 2.6), (0.8, 6.4, FZ + 0.1), 16.0)


def _drapes(nc, p0, p1, z0, z1, rng, gaps=(), mat="M_RottenCurtain"):
    """Moth-eaten black/red hangings along a wall (p0 -> p1, room on the left), torn to different lengths."""
    L, _, _, yaw = K._frame2d(p0, p1)
    with nc.at((p0[0], p0[1], 0.0), rot=yaw):
        nc.box((L / 2, 0.06, z1 + 0.03), (L, 0.03, 0.03), RUST)
        u = 0.1
        while u < L - 0.1:
            w = rng.uniform(0.2, 0.34)
            if not any(a < u < b for (a, b) in gaps):
                ln = (z1 - z0) * rng.uniform(0.55, 1.0)
                nc.box((u + w / 2, 0.05 + 0.02 * (int(u * 10) % 2), z1 - ln / 2), (w, 0.015, ln),
                       mat if rng.random() < 0.7 else "M_SalonWallpaper")
            u += w + 0.02


def _ritual_extras(aset, mb, nc, rng):
    x0, y0, x1, y1 = RIT
    top = CZ1 - 0.3
    _drapes(nc, (x1, y0), (x1, y1), FZ + 0.4, top, rng, gaps=[(1.3, 3.5)])
    _drapes(nc, (x0, y1), (x0, y0), FZ + 1.0, top, rng)
    _drapes(nc, (x1, y1), (x0, y1), FZ + 0.4, top, rng, gaps=[(2.7, 5.3)])
    # robes on hooks between the two doorways, tall candle stands around the field, grimoires
    for k in range(4):
        x = -1.1 + 0.73 * k
        nc.box((x, y0 + 0.03, FZ + 1.9), (0.04, 0.06, 0.04), RUST)
        nc.box((x, y0 + 0.07, FZ + 1.3), (0.5, 0.06, 1.2), "M_Black")
        nc.box((x, y0 + 0.08, FZ + 1.75), (0.22, 0.08, 0.25), "M_Black")
    for (x, y) in ((-3.3, 5.3), (3.3, 5.3), (-3.3, 8.7), (3.3, 8.7)):
        mb.cylinder((x, y, FZ), 0.14, 0.04, "M_TarnishedGold", seg=8)
        mb.cylinder((x, y, FZ + 0.04), 0.025, 1.15, "M_TarnishedGold", seg=6)
        mb.cylinder((x, y, FZ + 1.19), 0.08, 0.03, "M_TarnishedGold", seg=8)
        _candle(nc, x, y, FZ + 1.22, h=0.2, r=0.03)
    aset.light((0.0, 9.0, FZ + 1.6), WARM, 300.0, 4.0)
    with mb.at((-2.55, 9.2, FZ)), nc.at((-2.55, 9.2, FZ)):
        _old_bookcase(mb, nc, rng, w=0.8, h=1.7, shelves=4, fill=0.7)
    _spilled_books(nc, -2.6, 8.6, FZ, 0.5, 6, rng)
    _papers(nc, 1.0, 5.4, FZ, 1.4, 8, rng)
    nc.box((0.0, 7.0, FZ + 0.002), (6.6, 3.6, 0.002), "M_Black")     # the field is drawn on a soot-black board
    _toppled_chair(mb, (2.3, 5.2, FZ), 200.0, rng)
    _toppled_chair(mb, (-1.2, 8.7, FZ), 20.0, rng)
    for k in range(3):                     # dropped robes and a mask on the floor
        rbox(nc, (rng.uniform(-2.5, 2.5), rng.uniform(5.2, 8.8), FZ + 0.02), (0.6, 0.9, 0.04), "M_Black",
             yaw=rng.uniform(0, 180))

def _dorm_room(aset, mb, nc, rng):
    x0, y0, x1, y1 = RIT
    z0 = BED_Z
    K.floor_planks(mb, x0, y0, x1, y1, z0, mat="M_IntWoodFloorDark", seam=VOID, along="y")
    _room_wainscot(mb, x0, y0, x1, y1, z0, 0.9, gaps={"s": [(3.0, 5.0)]})
    _beams(mb, x0, y0, x1, y1, BED_TOP, step=1.6, along="y")
    for x in (-2.0, 2.0):
        _boarded_inside(mb, nc, x, y1, 0.0, 1.25, 5.0, 2.0, rng)
        for k in range(3):   # rotten curtains
            hk = (1.8, 1.4, 1.1)[k]
            nc.box((x + (-0.75 if k < 2 else 0.72) + 0.09 * k, y1 - 0.12, z0 + 2.9 - hk / 2), (0.18, 0.02, hk),
                   "M_RottenCurtain")
        nc.box((x, y1 - 0.12, 7.15), (1.8, 0.03, 0.03), RUST)
    aset.light((0.0, y1 - 0.9, z0 + 2.3), MOON, 550.0, 7.0)
    # three iron beds, one stripped bare; nightstands with candles
    for k, x in enumerate((-3.1, -0.5, 2.2)):
        aset.prop("SM_Int_OldBed", (x, y1 - 1.05, z0), 0.0)
    nc.box((-0.5, y1 - 1.1, z0 + 0.62), (0.9, 1.4, 0.06), "M_IntFabricWhite")
    for x in (-1.8, 0.85):
        aset.prop("SM_Int_NightstandB", (x, y1 - 0.3, z0), 0.0)
    _candles(nc, -1.8, y1 - 0.3, z0 + 0.55, rng, 2)
    aset.light((-1.8, y1 - 0.6, z0 + 1.0), WARM, 420.0, 4.5)
    with mb.at((0, 0, z0)), nc.at((0, 0, z0)):
        _wardrobe_ajar(mb, nc, x1 - 0.32, 6.4, -90.0, rng)
    aset.prop("SM_Int_Suitcase", (-3.5, 5.6, z0), 90.0)
    aset.prop("SM_Int_RockingChair", (2.4, 6.5, z0), 160.0)
    aset.prop("SM_Int_Mirror", (x1, 8.15, z0 + 0.9), -90.0)
    # the board of missing students (and a photo that fell)
    K.bulletin(nc, aset, x0, 7.0, z0 + 1.2, 90.0, 1.6, 1.0, title="MISSING", rng_seed=13)
    aset.text("HAVE YOU SEEN THEM?", K.wall_point(x0, 7.0, 90.0, 0.03, z0 + 1.02), 90.0, size=0.09,
              color=(0.55, 0.05, 0.05))
    _papers(nc, -2.6, 6.2, z0, 0.9, 7, rng)
    _cobwebs(nc, x0, y0, x1, y1, BED_TOP - 0.28, rng, size=(0.6, 1.1))
    K.camera(aset, "dormroom", (-3.4, 5.0, z0 + 1.7), (1.8, 8.6, z0 + 0.5), 16.0)


# ---------------------------------------------------------------- first floor: helpers
class _Fr:
    """Room frame: origin on the inner face of the window wall (left end), local +y into the room."""

    def __init__(self, ox, oy, rot, W, D, z):
        self.ox, self.oy, self.rot, self.W, self.D, self.z = ox, oy, rot, W, D, z

    def P(self, u, v, dz=None):
        a = math.radians(self.rot)
        x, y = self.ox + u * math.cos(a) - v * math.sin(a), self.oy + u * math.sin(a) + v * math.cos(a)
        return (x, y) if dz is None else (x, y, self.z + dz)

    def Y(self, yaw):
        return self.rot + yaw

    def ctx(self, *builders):
        return _Multi([b.at((self.ox, self.oy, self.z), rot=self.rot) for b in builders])


class _Multi:
    def __init__(self, cms):
        self.cms = cms

    def __enter__(self):
        for c in self.cms:
            c.__enter__()
        return self

    def __exit__(self, *a):
        for c in reversed(self.cms):
            c.__exit__(*a)
        return False


def _crate(mb, nc, x, y, z, s, yaw):
    """Slatted wooden crate (size s) standing at (x, y, z)."""
    with mb.at((x, y, z), rot=yaw), nc.at((x, y, z), rot=yaw):
        mb.box((0, 0, s / 2), (s * 0.94, s * 0.94, s * 0.98), "M_DarkWood")
        for k in range(3):
            zz = s * (0.15 + 0.35 * k)
            for (dx, dy, w, d) in ((0, -s / 2, s, 0.02), (0, s / 2, s, 0.02), (-s / 2, 0, 0.02, s), (s / 2, 0, 0.02, s)):
                nc.box((dx, dy, zz), (w + 0.01, d, s * 0.2), ROT)


def _sconce(mb, nc, aset, x, y, z, yaw, lit=True):
    """Tarnished brass candle sconce on a wall ((x, y) on the face, local -Y into the room)."""
    with mb.at((x, y, z), rot=yaw), nc.at((x, y, z), rot=yaw):
        mb.box((0, -0.01, 0.0), (0.1, 0.02, 0.24), "M_TarnishedGold")
        mb.beam((0, -0.02, -0.06), (0, -0.16, 0.02), 0.02, 0.02, "M_TarnishedGold")
        mb.cylinder((0, -0.16, 0.0), 0.05, 0.03, "M_TarnishedGold", seg=8)
        if lit:
            _candle(nc, 0, -0.16, 0.03, h=0.12)
        else:
            nc.cylinder((0, -0.16, 0.03), 0.022, 0.05, "M_CandleWax", seg=6)
    if lit:
        aset.light(K.wall_point(x, y, yaw, 0.3, z + 0.25), WARM, 260.0, 4.0)


def _win_inside(mb, nc, x, y, yaw, w, z0, h, rng, depth=WT, curtain=True):
    """Inside of a real (open) window in a thick stone wall: (x, y) on the inner face, local -Y into the room.
    Rotten sash with a few panes left, deep sill, dark frame, tattered curtains, a cobweb in the corner."""
    with mb.at((x, y, z0), rot=yaw), nc.at((x, y, z0), rot=yaw):
        for s in (-1, 1):
            mb.box((s * (w / 2 + 0.05), -0.03, h / 2), (0.1, 0.06, h + 0.1), "M_DarkWood")
        mb.box((0, -0.03, h + 0.05), (w + 0.2, 0.06, 0.1), "M_DarkWood")
        mb.box((0, -0.04, -0.03), (w + 0.3, 0.2, 0.06), "M_DarkWood")                 # sill board
        # sash frame halfway into the wall: stiles, meeting rail, bars
        yy = depth * 0.45
        for s in (-1, 1):
            nc.box((s * (w / 2 - 0.03), yy, h / 2), (0.06, 0.06, h), ROT)
        nc.box((0, yy, h - 0.03), (w, 0.06, 0.06), ROT)
        nc.box((0, yy, 0.03), (w, 0.06, 0.06), ROT)
        nc.box((0, yy, h * 0.5), (w, 0.07, 0.06), ROT)
        nc.box((0, yy, h * 0.5), (0.04, 0.05, h), ROT)
        for k in range(4):     # four panes: some intact, some gone, one cracked
            px, pz = (-w / 4, w / 4)[k % 2], (h * 0.25, h * 0.75)[k // 2]
            r = rng.random()
            if r < 0.4:
                nc.box((px, yy, pz), (w / 2 - 0.06, 0.01, h / 2 - 0.06), "M_IntGlassClear")
            elif r < 0.7:
                nc.poly([(px - w / 4 + 0.03, yy, pz - h / 4 + 0.03), (px + w / 4 - 0.03, yy, pz - h / 4 + 0.03),
                         (px - w / 4 + 0.03, yy, pz + h * rng.uniform(0.0, 0.2))], "M_IntGlassClear")
        # glass shards on the sill and the floor below
        for k in range(rng.randint(2, 4)):
            rbox(nc, (rng.uniform(-w / 2, w / 2), -rng.uniform(0.0, 0.1), 0.004), (0.07, 0.05, 0.004), "M_IntGlassClear",
                 yaw=rng.uniform(0, 90))
        for k in range(rng.randint(1, 3)):
            rbox(nc, (rng.uniform(-w / 2, w / 2), -rng.uniform(0.3, 0.8), -z0 + 0.004), (0.06, 0.05, 0.004),
                 "M_IntGlassClear", yaw=rng.uniform(0, 90))
        if curtain:
            nc.box((0, -0.12, h + 0.16), (w + 0.6, 0.03, 0.03), RUST)
            for s in (-1, 1):
                if rng.random() < 0.25:
                    continue
                n = rng.randint(2, 4)
                for i in range(n):
                    ln = (h + 0.2) * rng.uniform(0.45, 1.05)
                    nc.box((s * (w / 2 + 0.22 - 0.1 * i), -0.13 - 0.02 * (i % 2), h + 0.15 - ln / 2),
                           (0.12, 0.02, ln), "M_RottenCurtain")
        # cobweb in the top corner of the reveal
        c = (w / 2 - 0.02, -0.01, h - 0.02)
        for (dx, dz) in ((-0.35, 0.0), (0.0, -0.4), (-0.22, -0.22)):
            nc.beam(c, (c[0] + dx, -0.01, c[2] + dz), 0.006, 0.006, "M_Cobweb")
        nc.poly([c, (c[0] - 0.35, -0.012, c[2]), (c[0], -0.012, c[2] - 0.4)], "M_CobwebVeil")


def _peel(nc, p0, p1, z0, z1, rng, n=6):
    """Peeling wallpaper, bare plaster patches, damp stains and curling strips on the inside face of a wall
    (p0 -> p1, room on the left)."""
    L, (ux, uy), (nx, ny), yaw = K._frame2d(p0, p1)
    with nc.at((p0[0], p0[1], 0.0), rot=yaw):
        for _ in range(n):
            u = rng.uniform(0.3, L - 0.3)
            z = rng.uniform(z0 + 0.4, z1 - 0.3)
            r = rng.random()
            if r < 0.45:
                nc.box((u, 0.004, z), (rng.uniform(0.25, 0.8), 0.006, rng.uniform(0.2, 0.7)), "M_PeelPlaster")
            elif r < 0.75:
                hh = rng.uniform(0.6, 1.4)
                nc.box((u, 0.003, z1 - hh / 2), (rng.uniform(0.15, 0.5), 0.004, hh), "M_WaterStain")
            else:
                with nc.at((u, 0.01, z), rot_x=-rng.uniform(15, 40)):
                    nc.box((0, 0, -0.25), (rng.uniform(0.12, 0.3), 0.004, 0.5), WALLP)


def _ceiling_damage(nc, x0, y0, x1, y1, z, rng, n=3, hole=None):
    """Water stains on the ceiling, hanging laths; hole = (x, y, r): a dark hole into the floor above."""
    for _ in range(n):
        cx, cy = rng.uniform(x0 + 0.5, x1 - 0.5), rng.uniform(y0 + 0.5, y1 - 0.5)
        nc.box((cx, cy, z - 0.004), (rng.uniform(0.5, 1.3), rng.uniform(0.4, 1.1), 0.006), "M_WaterStain")
    if hole:
        hx, hy, r = hole
        pts = [(hx + math.cos(a) * r * rng.uniform(0.7, 1.15), hy + math.sin(a) * r * rng.uniform(0.7, 1.15))
               for a in [math.tau * k / 9 for k in range(9)]]
        nc.poly([(x, y, z - 0.008) for (x, y) in reversed(pts)], VOID)
        for k in range(5):
            a = rng.uniform(0, math.tau)
            px, py = hx + math.cos(a) * r * 0.8, hy + math.sin(a) * r * 0.8
            rbox(nc, (px, py, z - 0.35), (0.03, 0.04, 0.7), ROT, yaw=rng.uniform(0, 180), pitch=rng.uniform(-35, 35))


def _iron_bed(aset, nc, fr, u, v, yaw, rng, state="slept"):
    """Old iron bed (catalog) with a stained mattress; state: slept | made | bare | sheeted."""
    x, y = fr.P(u, v)
    aset.prop("SM_Int_OldBed", (x, y, fr.z), fr.Y(yaw))
    with fr.ctx(nc), nc.at((u, v, 0.0), rot=yaw):
        if state == "bare":
            nc.box((0, 0, 0.45), (0.82, 1.86, 0.02), RUST)
            for k in range(9):
                nc.box((0, -0.8 + k * 0.2, 0.465), (0.8, 0.015, 0.01), "M_DetSilver")
            return
        nc.box((0, -0.02, 0.5), (0.84, 1.9, 0.14), "M_DustSheet" if state == "sheeted" else "M_OldPaper")
        nc.box((rng.uniform(-0.2, 0.2), -0.3, 0.571), (0.35, 0.5, 0.004), "M_WaterStain")
        if state == "sheeted":
            nc.box((0, -0.02, 0.8), (0.95, 2.0, 0.6), "M_DustSheet")
            return
        nc.box((0, 0.72, 0.62), (0.56, 0.32, 0.12), "M_IntFabricWhite")               # pillow
        if state == "made":
            nc.box((0, -0.25, 0.6), (0.88, 1.3, 0.06), "M_IntFabricNavy")
            nc.box((0, 0.42, 0.61), (0.88, 0.12, 0.06), "M_IntFabricWhite")
        else:                                                                           # thrown back
            with nc.at((rng.uniform(-0.1, 0.1), -0.35, 0.62), rot=rng.uniform(-14, 14)):
                nc.box((0, 0, 0), (0.86, 0.9, 0.07), "M_IntFabricNavy")
                nc.box((0.05, 0.5, 0.04), (0.8, 0.25, 0.12), "M_IntFabricNavy")
            with nc.at((0.48, -0.5, 0.45), rot_y=-70):                                   # sliding to the floor
                nc.box((0, 0, 0), (0.5, 0.7, 0.04), "M_IntFabricNavy")


def _old_desk(mb, nc, aset, fr, u, v, yaw, rng, w=1.1, d=0.6, stuff="papers"):
    """Writing desk (top 0.76 m) with a drawer, user side local -Y; its top is dressed. stuff: papers | gx | diary."""
    zt = 0.76
    with fr.ctx(mb, nc), mb.at((u, v, 0.0), rot=yaw), nc.at((u, v, 0.0), rot=yaw):
        mb.box((0, 0, zt - 0.02), (w, d, 0.04), "M_DarkWood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * (w / 2 - 0.04), sy * (d / 2 - 0.04), (zt - 0.04) / 2), (0.05, 0.05, zt - 0.04), "M_DarkWood")
        mb.box((w / 2 - 0.25, 0.0, zt - 0.14), (0.42, d - 0.06, 0.16), "M_DarkWood")
        nc.box((w / 2 - 0.25, -d / 2 - 0.004, zt - 0.14), (0.38, 0.008, 0.12), ROT)
        nc.box((w / 2 - 0.25, -d / 2 - 0.02, zt - 0.14), (0.08, 0.02, 0.02), "M_TarnishedGold")
        _papers(nc, 0.05, 0.0, zt, 0.25, rng.randint(3, 6), rng)
        DT.book_stack(nc, -w / 2 + 0.2, d / 2 - 0.18, zt, 0.0, rng.randint(2, 4), rng.randint(0, 99))
        _candle(nc, w / 2 - 0.12, d / 2 - 0.12, zt, h=rng.uniform(0.06, 0.16))
        nc.cylinder((w / 2 - 0.3, d / 2 - 0.1, zt), 0.025, 0.05, "M_Black", seg=8)       # ink pot
        nc.box((w / 2 - 0.36, d / 2 - 0.1, zt + 0.004), (0.14, 0.008, 0.006), "M_OldPaper")   # quill
        if stuff in ("gx", "diary"):
            DT.deck_box(nc, -0.25, -0.12, zt, rng.uniform(-30, 30), "M_IntFabricBlue")
            DT.card_spread(nc, 0.1, -0.15, zt, 0.0, 5, rng.randint(0, 99))
        if stuff == "diary":
            nc.box((-0.05, 0.08, zt + 0.02), (0.3, 0.22, 0.03), "M_OldBookRed")
    x, y = fr.P(*_rot2(u, v, yaw, -w / 2 + 0.2, -0.05))
    aset.prop("SM_Int_PhotoFrame", (x, y, fr.z + zt), fr.Y(yaw + 180 + rng.uniform(-20, 20)))


def _rot2(u, v, yaw, du, dv):
    a = math.radians(yaw)
    return (u + du * math.cos(a) - dv * math.sin(a), v + du * math.sin(a) + dv * math.cos(a))


def _wardrobe_ajar(mb, nc, u, v, yaw, rng, w=1.0, d=0.6, h=2.0, jackets=2):
    """Wardrobe (doors at local -Y), one door hanging open, dorm jackets and a shoe box inside."""
    with mb.at((u, v, 0.0), rot=yaw), nc.at((u, v, 0.0), rot=yaw):
        mb.box((0, d / 2 - 0.02, h / 2), (w, 0.04, h), "M_DarkWood")
        for s in (-1, 1):
            mb.box((s * (w / 2 - 0.02), 0, h / 2), (0.04, d, h), "M_DarkWood")
        mb.box((0, 0, h - 0.02), (w, d, 0.04), "M_DarkWood")
        mb.box((0, 0, 0.06), (w, d, 0.12), "M_DarkWood")
        mb.box((0, 0, h + 0.05), (w + 0.08, d + 0.06, 0.1), "M_DarkWood")
        mb.box((w / 4, -d / 2 + 0.02, h / 2 + 0.03), (w / 2 - 0.02, 0.03, h - 0.18), "M_DarkWood")   # shut leaf
        with mb.at((-w / 2, -d / 2, 0.0), rot=-rng.uniform(70, 115)):                                 # open leaf
            mb.box((w / 4, 0.015, h / 2 + 0.03), (w / 2 - 0.02, 0.03, h - 0.18), "M_DarkWood")
        nc.box((0, 0.0, h - 0.25), (w - 0.08, 0.02, 0.02), "M_DetSilver")                         # rail
        for k in range(jackets):
            with nc.at((-w / 2 + 0.2 + k * 0.17, 0.0, h - 0.3), rot=90 + rng.uniform(-8, 8)):
                nc.box((0, 0, -0.33), (0.4, 0.07, 0.62), ("M_DetJacketWhite", "M_DetJacketBlue")[k % 2])
        nc.box((-w / 4, -0.05, 0.2), (0.32, 0.22, 0.14), "M_IntFabricWhite")


def _trunk(mb, nc, u, v, yaw, w=0.85, d=0.48, h=0.46, open_=False):
    with mb.at((u, v, 0.0), rot=yaw), nc.at((u, v, 0.0), rot=yaw):
        mb.box((0, 0, h / 2), (w, d, h), "M_DarkWood")
        for s in (-1, 1):
            nc.box((s * w * 0.3, 0, h / 2), (0.05, d + 0.01, h + 0.01), RUST)
        nc.box((0, -d / 2 - 0.005, h - 0.08), (0.06, 0.01, 0.08), "M_TarnishedGold")
        if open_:
            with nc.at((0, d / 2, h), rot_x=-100):
                nc.box((0, -d / 2, 0.02), (w, d, 0.04), "M_DarkWood")


def _scrawl(aset, x, y, yaw, z, lines, size=0.16, color=(0.5, 0.04, 0.04)):
    for k, line in enumerate(lines):
        aset.text(line, K.wall_point(x, y, yaw, 0.02, z - k * size * 1.5), yaw, size=size, color=color)


# ---------------------------------------------------------------- first floor: rooms
def _room_rect(sx, k, back):
    r0, r1 = U_ROOMS[k]
    ya, yb = ((U_CORR[1], Y1 - WT) if back else (Y0 + WT, U_CORR[0]))
    xa, xb = sorted((sx * r0, sx * r1))
    return xa, ya, xb, yb, sx * (r0 + 0.75)


def _upper_room(aset, mb, nc, rng, sx, k, back, variant, number, cam=None, fl=FL2):
    """A ruined first-floor dorm room. variant: slept | made | collapsed | diary | sheeted."""
    x0, y0, x1, y1, door_x = _room_rect(sx, k, back)
    z = fl["fz"]
    W, D = x1 - x0, y1 - y0
    fr = _Fr(x1, y1, 180.0, W, D, z) if back else _Fr(x0, y0, 0.0, W, D, z)
    du = (door_x - x0) if not back else (x1 - door_x)
    far = 0.0 if du > W / 2 else W           # the side wall away from the door
    fs = 1 if far == 0.0 else -1             # inward direction from the far wall
    near = W - far
    ns = -fs
    K.floor_planks(mb, x0, y0, x1, y1, z, mat="M_IntWoodFloorDark", seam=VOID, along="y" if back else "x")
    DT.dress_room(aset, mb, nc, x0, y0, x1, y1, z, fl["top"], style="ruin", seed=k + (10 if back else 0))
    # windows of this room (world)
    wins = [(sx * a, y1 if back else y0) for a in (WIN_BACK if back else WIN_FRONT) if x0 < sx * a < x1]
    gable = []
    if k == 3 and not back:
        gable = [(x1 if sx > 0 else x0, y) for y in WIN_GABLE if y0 < y < y1]
    wz0, wh = WIN_ROWS[fl["row"]][0], WIN_ROWS[fl["row"]][1]
    for (wx, wy) in wins:
        _win_inside(mb, nc, wx, wy, 0.0 if back else 180.0, 1.25, wz0, wh, rng)
    for (wx, wy) in gable:
        _win_inside(mb, nc, wx, wy, -90.0 if sx > 0 else 90.0, 1.25, wz0, wh, rng)
    # walls: wainscot + peeling paper, ceiling damage, cobwebs
    wall_n = {"s": ((x0, y0), (x1, y0)), "e": ((x1, y0), (x1, y1)), "n": ((x1, y1), (x0, y1)), "w": ((x0, y1), (x0, y0))}
    door_side = "s" if back else "n"
    du_wall = (door_x - x0) if door_side == "s" else (x1 - door_x)
    gaps = {door_side: [(du_wall - 0.6, du_wall + 0.6)]}
    for (wx, wy) in wins:
        side = "n" if back else "s"
        uu = (wx - x0) if side == "s" else (x1 - wx)
        gaps.setdefault(side, []).append((uu - 0.75, uu + 0.75))
    _room_wainscot(mb, x0, y0, x1, y1, z, 0.9, gaps=gaps)
    for n_, (p0, p1) in wall_n.items():
        _peel(nc, p0, p1, z + 0.95, fl["top"], rng, n=4 if n_ in "ns" else 7)
    hole = None
    if variant == "collapsed":
        hole = fr.P(far + fs * 1.6, D * 0.45) + (1.0,)
    _ceiling_damage(nc, x0, y0, x1, y1, fl["top"], rng, n=3, hole=hole)
    _beams(mb, x0, y0, x1, y1, fl["top"], step=2.4, along="y" if back else "x")
    _cobwebs(nc, x0, y0, x1, y1, fl["top"] - 0.28, rng, size=(0.45, 0.85))
    with fr.ctx(mb, nc):
        # cornice + picture rail
        for (a, b) in (((0, 0), (W, 0)), ((W, 0), (W, D)), ((W, D), (0, D)), ((0, D), (0, 0))):
            L, _, (nx_, ny_), yaw = K._frame2d(a, b)
            with mb.at((a[0], a[1], fl["top"] - z), rot=yaw):
                mb.box((L / 2, 0.06, -0.06), (L, 0.12, 0.12), "M_DarkWood")
            with nc.at((a[0], a[1], 2.35), rot=yaw):
                nc.box((L / 2, 0.012, 0.0), (L, 0.024, 0.04), "M_DarkWood")
    long_room = D > 7.0
    vb = 0.62                                # bed head line (beds' heads at the window wall)
    beds = [(far + fs * 0.55, "far"), (near + ns * 0.55, "near")] if long_room else [(far + fs * 0.55, "far")]
    states = {"slept": ("slept", "bare"), "made": ("made", "made"), "collapsed": ("bare", "slept"),
              "diary": ("slept", "slept"), "sheeted": ("sheeted", "sheeted")}[variant]
    for i, (bu, _) in enumerate(beds):
        _iron_bed(aset, nc, fr, bu, vb + 1.0, 180.0, rng, states[i % 2])
    # nightstand + candle between the beds (or beside the single bed)
    nu = W / 2 if long_room else far + fs * 1.4
    x, y = fr.P(nu, 0.3)
    aset.prop("SM_Int_NightstandB", (x, y, z), fr.Y(180.0))
    with fr.ctx(nc):
        _candles(nc, nu + 0.1, 0.3, 0.62, rng, 2)
        DT.book_stack(nc, nu - 0.12, 0.28, 0.62, 10.0, 2, k)
    lx, ly = fr.P(nu, 0.9)
    aset.light((lx, ly, z + 1.0), WARM, 420.0, 5.0)
    # trunks at the bed feet
    with fr.ctx(mb, nc):
        for i, (bu, _) in enumerate(beds):
            _trunk(mb, nc, bu, vb + 2.35, 0.0, open_=(i == 0 and variant != "sheeted"))
    # wardrobe on the far wall, desk(s), chairs
    vw = 3.9 if long_room else 4.1
    with fr.ctx(mb, nc):
        if variant == "sheeted":
            mb.box((far + fs * 0.32, vw, 1.0), (0.64, 1.0, 2.0), "M_DustSheet")
        else:
            _wardrobe_ajar(mb, nc, far + fs * 0.32, vw, 90.0 * fs, rng)
    desks = [(near + ns * 0.32, (3.8 if long_room else 1.6))] + ([(far + fs * 0.32, 5.4)] if long_room else [])
    for i, (u, v) in enumerate(desks):
        dyaw = 90.0 if u < W / 2 else -90.0         # desk back to the side wall, user facing it
        stuff = "diary" if (variant == "diary" and i == 0) else ("gx" if i == 0 else "papers")
        if variant == "sheeted":
            with fr.ctx(mb):
                mb.box((u, v, 0.4), (0.62, 1.12, 0.8), "M_DustSheet")
            continue
        _old_desk(mb, nc, aset, fr, u, v, dyaw, rng, stuff=stuff)
        cu = u + (0.55 if u < W / 2 else -0.55)
        cx_, cy_ = fr.P(cu, v + 0.1)
        if variant in ("collapsed",) or (i == 1 and variant == "slept"):
            with fr.ctx(mb):
                _toppled_chair(mb, (cu + 0.2 * (1 if u < W / 2 else -1), v - 0.3, 0.0), rng.uniform(0, 180), rng)
        else:
            aset.prop("SM_Int_WoodChair", (cx_, cy_, z), fr.Y((-90.0 if u < W / 2 else 90.0) + rng.uniform(-25, 25)))
    # sitting corner on the far side by the door wall: sheeted armchair, side table, rug
    if long_room:
        with fr.ctx(mb, nc):
            K.rug(nc, W * 0.18, 3.2, W * 0.82, 6.6, 0.0, "M_Carpet", "M_TarnishedGold")
            _sheeted(mb, far + fs * 0.55, 7.6, 0.0, 90.0 * fs, 0.85, 0.8, 0.95)
        x, y = fr.P(far + fs * 0.45, 8.5)
        aset.prop("SM_Int_SideTable", (x, y, z), fr.Y(0.0))
        with fr.ctx(nc):
            _candle(nc, far + fs * 0.45, 8.5, 0.55, h=0.1)
            DT.mug(nc, far + fs * 0.32, 8.4, 0.55, seed=k, coffee=False)
        x, y = fr.P(far + fs * 0.3, D - 0.25)
        aset.prop("SM_Int_GrandfatherClock" if variant == "made" else "SM_Int_Shelves", (x, y, z), fr.Y(0.0))
    # walls: a portrait / photos / mirror, coat hooks with old dorm jackets by the door
    with fr.ctx(mb, nc):
        _portrait(mb, nc, far, (vb + 1.0), 1.75, (90.0 if fs > 0 else -90.0), 0.55, 0.7,
                  eyes=(variant in ("diary", "made")), tilt=rng.uniform(-8, 8))
        for j in range(3):
            _portrait(mb, nc, near, 4.6 + j * 0.42 if long_room else 2.4 + j * 0.42, 1.55 + 0.12 * (j % 2),
                      (90.0 if ns > 0 else -90.0), 0.26, 0.32, sitter=(j != 1), tilt=rng.uniform(-10, 10))
        cu = du + (1.25 if du < W / 2 else -1.25)
        DT.coat_hooks(nc, cu, D, 1.75, 0.0, n=3, dorm="white", jackets=1 + (k % 2), seed=k)
    mx, my = fr.P(near, 6.6 if long_room else 3.2)
    aset.prop("SM_Int_Mirror", (mx, my, z + 1.05), fr.Y(90.0 if ns > 0 else -90.0))
    # floor: papers, books, clutter
    with fr.ctx(nc, mb):
        _papers(nc, W / 2, D * 0.55, 0.0, 0.9, 6, rng)
        _spilled_books(nc, far + fs * 1.3, D * 0.62, 0.0, 0.4, 3, rng)
    def lrect(u0, v0, u1, v1):
        a, b = fr.P(u0, v0), fr.P(u1, v1)
        return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))
    furn = [lrect(far, 3.2, far + fs * 0.7, 6.1), lrect(near, 3.0, near + ns * 0.7, 4.5), lrect(0, 0, W, 3.3),
            lrect(far, 7.0, far + fs * 1.0, D)]
    DT.floor_clutter(nc, aset, x0, y0, x1, y1, z, kind="ruin", n=4, seed=31 * k + (7 if back else 0) + (sx > 0),
                     clear=furn + ([(hole[0] - 1.0, hole[1] - 1.0, hole[0] + 1.0, hole[1] + 1.0)] if hole else []) +
                     [(min(fr.P(du - 0.8, D - 1.3)[0], fr.P(du + 0.8, D)[0]),
                             min(fr.P(du - 0.8, D - 1.3)[1], fr.P(du + 0.8, D)[1]),
                             max(fr.P(du - 0.8, D - 1.3)[0], fr.P(du + 0.8, D)[0]),
                             max(fr.P(du - 0.8, D - 1.3)[1], fr.P(du + 0.8, D)[1]))])
    if variant == "collapsed":
        hx, hy, _ = hole
        rubble(mb, (hx, hy), 0.8, 12, rng, mats=(STONE, ROT, U_CEIL), zc=z)
        planks(mb, (hx, hy), 0.7, 4, rng, zc=z, length=(0.8, 1.6))
        aset.light((hx, hy, z + 2.4), MOON, 300.0, 4.0)
    if variant == "diary":
        # a loose floorboard by the far bed, the diary hidden underneath
        du2, dv2 = far + fs * 1.45, vb + 1.6
        with fr.ctx(mb, nc):
            nc.box((du2, dv2, -0.02), (0.2, 0.9, 0.04), VOID)
            rbox(mb, (du2 + fs * 0.25, dv2 + 0.1, 0.06), (0.18, 0.9, 0.03), "M_IntWoodFloorDark", yaw=12.0, roll=-25.0)
            rbox(nc, (du2, dv2 - 0.1, 0.012), (0.15, 0.21, 0.035), "M_OldBookRed", yaw=8.0)
            nc.box((du2, dv2 - 0.1, 0.031), (0.13, 0.19, 0.003), "M_OldPaper")
        ix, iy = fr.P(du2, dv2)
        aset.interact("diary", (ix, iy, z + 0.3), 0.0, title="A hidden diary",
                      text="Under a loose floorboard: a student's diary. The last entry: 'The candles were lit again "
                           "tonight. Someone keeps calling my name from the old tower. Tomorrow I'll find out who.'",
                      radius=1.6)
        wx, wy = fr.P(far, 6.6)
        _scrawl(aset, wx, wy, fr.Y(90.0 * fs), z + 1.95, ("DON'T GO UP", "THE TOWER"), 0.13)
    if variant == "made":
        with fr.ctx(nc):
            DT.duel_disk(nc, beds[0][0] - 0.1, vb + 1.6, 0.66, 70.0)
    # the door number on the corridor side
    pyaw = 180.0 if not back else 0.0
    ny = U_CORR[0] + 0.15 if not back else U_CORR[1] - 0.15
    K.nameplate(mb, aset, door_x + (0.8 if door_x > 0 else -0.8), ny, z + 1.6, pyaw, number, mat="M_TarnishedGold",
                color=(0.12, 0.08, 0.05))
    if cam:
        cu = du + (0.45 if du < W / 2 else -0.45)
        p = fr.P(cu, D - 0.45)
        t = fr.P(far + fs * 0.6, 0.8)
        K.camera(aset, cam, (p[0], p[1], z + 1.65), (t[0], t[1], z + 0.7), 16.0)


def _corridor(aset, mb, nc, rng, sx, fl=FL2):
    xa, xb = sorted((sx * (HX + WT), sx * (X1 - WT)))
    y0, y1 = U_CORR[0] + 0.15, U_CORR[1] - 0.15
    z = fl["fz"]
    K.floor_planks(mb, xa, y0, xb, y1, z, mat="M_IntWoodFloorDark", seam=VOID, along="y")
    DT.dress_room(aset, mb, nc, xa, y0, xb, y1, z, fl["top"], style="ruin", seed=40 + (sx > 0))
    doors_s = [sx * (r0 + 0.75) for (r0, r1) in U_ROOMS]
    doors_n = [sx * (r0 + 0.75) for (r0, r1) in U_ROOMS]
    gaps = {"s": [(x - xa - 0.6, x - xa + 0.6) for x in doors_s], "n": [(xb - x - 0.6, xb - x + 0.6) for x in doors_n],
            ("w" if sx > 0 else "e"): [(0.25, 1.45)],
            ("e" if sx > 0 else "w"): [(0.3, 1.8)] if sx > 0 else [(y1 - 3.95, y1 - 2.45)]}
    _room_wainscot(mb, xa, y0, xb, y1, z, 1.15, gaps=gaps)
    _peel(nc, (xa, y0), (xb, y0), z + 1.2, fl["top"], rng, n=16)
    _peel(nc, (xb, y1), (xa, y1), z + 1.2, fl["top"], rng, n=16)
    _ceiling_damage(nc, xa, y0, xb, y1, fl["top"], rng, n=5)
    _beams(mb, xa, y0, xb, y1, fl["top"], step=1.2, along="y")
    _cobwebs(nc, xa, y0, xb, y1, fl["top"] - 0.28, rng, size=(0.4, 0.7))
    # torn runner, a trail of papers
    x = xa + 0.4
    while x < xb - 0.5:
        ln = rng.uniform(1.0, 2.6)
        nc.box_mm((x, 2.62, z), (min(x + ln, xb - 0.4), 3.38, z + 0.012), "M_Carpet")
        nc.box_mm((x, 2.6, z + 0.012), (min(x + ln, xb - 0.4), 2.66, z + 0.016), "M_TarnishedGold")
        x += ln + rng.uniform(0.2, 0.7)
    _papers(nc, (xa + xb) / 2, 3.0, z, 3.5, 12, rng)
    # wall decor between the doors: portraits (one gone), MISSING posters, sconces (someone lit them)
    gaps_x = sorted(doors_s + [sx * (HX + WT), sx * (X1 - WT)])
    for i in range(len(gaps_x) - 1):
        xm = (gaps_x[i] + gaps_x[i + 1]) / 2
        if abs(gaps_x[i + 1] - gaps_x[i]) < 1.8:
            continue
        if i == 1:
            nc.box((xm, y0 + 0.004, z + 1.85), (0.75, 0.008, 0.95), "M_RuinCorridorPatch")
            nc.box((xm, y0 + 0.03, z + 2.42), (0.03, 0.06, 0.03), RUST)
        else:
            _portrait(mb, nc, xm, y0, z + 1.85, 180.0, 0.7, 0.9, eyes=(i == 2), tilt=rng.uniform(-6, 6))
        _sconce(mb, nc, aset, xm + 0.75, y0, z + 1.75, 180.0, lit=(i % 2 == 0))
    for xm in (sx * 10.9, sx * 14.6):
        K.poster(nc, aset, xm, y1, z + 1.55, 0.0, 0.42, 0.56, "M_OldPaper", text="MISSING", text_color=(0.4, 0.05, 0.05),
                 text_size=0.07)
        with nc.at((xm, y1 - 0.016, z + 1.45)):
            nc.box((0, 0, 0), (0.2, 0.004, 0.2), "M_PortraitFace")
    _sconce(mb, nc, aset, sx * 7.3, y1, z + 1.75, 0.0)
    _portrait(mb, nc, sx * 18.45, y1, z + 1.8, 0.0, 0.6, 0.8, eyes=True, tilt=-5.0)
    for k, xm in enumerate((sx * 7.3, sx * 11.0, sx * 14.6, sx * 18.0)):     # dead pendant lamps on chains
        with nc.at((xm, 3.0, fl["top"])):
            nc.cylinder((0, 0, -0.75), 0.008, 0.75, RUST, seg=4)
            nc.cylinder((0, 0, -0.95), 0.16, 0.2, "M_TarnishedGold", radius_top=0.05, seg=10, cap_bottom=False)
            if k != 2:
                nc.sphere((0, 0, -0.97), 0.06, "M_IntGlassClear", seg=8, rings=5)
        nc.cylinder((xm, 3.0, fl["top"] - 0.02), 0.08, 0.02, "M_TarnishedGold", seg=8)
    rbox(nc, (sx * 15.8, 3.25, z + 0.02), (0.18, 0.14, 0.04), "M_TarnishedGold", yaw=30)     # the fallen shade
    nc.lathe([(0.0, 0.0), (0.06, 0.0), (0.11, 0.12), (0.1, 0.24), (0.05, 0.34), (0.06, 0.4)], "M_PortraitCanvas", seg=10,
             cap_top=False, center=(sx * 11.12, y1 - 0.38, z + 0.55))
    for k in range(3):                       # dead flowers
        nc.beam((sx * 11.12, y1 - 0.38, z + 0.9), (sx * 11.12 + 0.1 * (k - 1), y1 - 0.38 - 0.05 * k, z + 1.15 - 0.08 * k),
                0.008, 0.008, "M_OldBookBrown")
    for k in range(3):                       # framed photos in a row over the side table
        _portrait(mb, nc, sx * (10.95 + 0.35 * k), y1, z + 1.55 + 0.08 * (k % 2), 0.0, 0.24, 0.3, sitter=(k != 1),
                  tilt=rng.uniform(-8, 8))
    # furniture: side table with a candelabra, a dust-sheeted bench, a toppled chair, a fallen door leaf
    aset.prop("SM_Int_SideTable", (sx * 11.3, y1 - 0.3, z), 0.0)
    aset.prop("SM_Int_Candelabra", (sx * 11.3, y1 - 0.3, z + 0.55), 0.0)
    _candles(nc, sx * 11.45, y1 - 0.25, z + 0.55, rng, 2)
    aset.light((sx * 11.3, 3.0, z + 1.2), WARM, 450.0, 5.0)
    _sheeted(mb, sx * 14.9, y0 + 0.3, z, 180.0, 1.3, 0.5, 0.85, kind="sofa")
    _toppled_chair(mb, (sx * 7.0, 2.6, z), rng.uniform(0, 180), rng)
    rbox(mb, (sx * 18.35, y0 + 0.35, z + 1.0), (0.9, 0.05, 2.05), ROT, yaw=8.0 * sx, roll=-18.0)
    _spilled_books(nc, sx * 12.8, 3.1, z, 0.4, 4, rng)
    # the gable window at the end, and the stairwell door (the boards that nailed it shut have been pried off)
    _win_inside(mb, nc, sx * (X1 - WT), 3.2, -90.0 * sx, 1.25, WIN_ROWS[fl["row"]][0], WIN_ROWS[fl["row"]][1], rng)
    sxd = sx * (U_ROOMS[3][0] + 0.75)
    for k, (dx, dy, a_) in enumerate(((-0.9, -0.5, 20.0), (0.75, -0.35, -35.0), (-0.2, -0.75, 70.0))):
        rbox(mb, (sxd + dx, y1 + dy, z + 0.03 + 0.04 * k), (1.4, 0.2, 0.04), BOARD, yaw=a_)
        nc.box((sxd + dx, y1 + dy, z + 0.06 + 0.04 * k), (0.03, 0.03, 0.04), RUST)
    if fl is FL2:
        _scrawl(aset, sxd - sx * 1.3, y1 - 0.0, 0.0, z + 1.42, ("DO NOT", "ENTER"), 0.12)
    K.nameplate(mb, aset, sxd + sx * 0.8, y1, z + 1.6, 0.0, "STAIRS", mat="M_TarnishedGold", color=(0.12, 0.08, 0.05))
    rubble(mb, (sxd, y1 - 0.4), 0.35, 5, rng, mats=(STONE, U_CEIL), zc=z, size=(0.08, 0.25))
    aset.light((sx * 17.5, 3.0, z + 2.2), MOON, 300.0, 5.0)
    aset.light((sx * 6.5, 3.0, z + 2.0), WARM, 350.0, 5.0)
    K.camera(aset, "corridor_" + ("e" if sx > 0 else "w") + fl["tag"], (sx * 6.2, 2.5, z + 1.65), (sx * 18.5, 3.2, z + 1.0), 18.0)


def _washroom(aset, mb, nc, rng, sx, fl=FL2):
    x0, y0, x1, y1, door_x = _room_rect(sx, 0, True)
    z = fl["fz"]
    W, D = x1 - x0, y1 - y0
    fr = _Fr(x1, y1, 180.0, W, D, z)
    du = x1 - door_x
    far = 0.0 if du > W / 2 else W
    fs = 1 if far == 0.0 else -1
    near, ns = W - far, -fs
    mb.box_mm((x0, y0, z - 0.03), (x1, y1, z), "M_IntTileWhite", skip=("-z",))
    DT.dress_room(aset, mb, nc, x0, y0, x1, y1, z, fl["top"], style="ruin", seed=50 + (sx > 0))
    with fr.ctx(mb, nc):
        for k in range(1, int(W / 0.3)):
            nc.box((k * 0.3, D / 2, 0.001), (0.008, D, 0.002), "M_Black")
        for k in range(1, int(D / 0.3)):
            nc.box((W / 2, k * 0.3, 0.001), (W, 0.008, 0.002), "M_Black")
        for _ in range(5):
            nc.box((rng.uniform(0.4, W - 0.4), rng.uniform(0.4, D - 0.4), 0.003), (rng.uniform(0.3, 0.9),
                   rng.uniform(0.3, 0.8), 0.002), "M_WaterStain")
        # tiled dado with a dark cap
        for (a, b) in (((0, 0), (W, 0)), ((W, 0), (W, D)), ((W, D), (0, D)), ((0, D), (0, 0))):
            L, _, _, yaw = K._frame2d(a, b)
            with nc.at((a[0], a[1], 0.0), rot=yaw):
                cuts = []
                if b == (0, D) and a == (W, D):
                    cuts = [(W - du - 0.6, W - du + 0.6)]
                if a == (0, 0):
                    wu = x1 - sx * 6.0
                    cuts = [(wu - 0.7, wu + 0.7)]
                u = 0.0
                for (c0, c1) in sorted(cuts) + [(L, L)]:
                    if c0 - u > 0.05:
                        nc.box(((u + c0) / 2, 0.006, 0.75), (c0 - u, 0.012, 1.5), "M_RuinTileWall")
                        nc.box(((u + c0) / 2, 0.018, 1.52), (c0 - u, 0.036, 0.05), "M_DarkWood")
                    u = max(u, c1)
        # three wash basins on the far wall (one smashed on the floor), pipes, mirrors
        for j, v in enumerate((1.3, 2.25, 3.2)):
            with mb.at((far + fs * 0.25, v, 0.0), rot=90.0 * fs):
                mb.box((0, 0.0, 0.42), (0.14, 0.14, 0.84) if j != 1 else (0.14, 0.14, 0.3), "M_IntTrimWhite")
                if j != 1:
                    mb.box((0, 0.02, 0.86), (0.55, 0.42, 0.14), "M_IntTrimWhite")
                    nc.box((0, 0.02, 0.935), (0.45, 0.32, 0.01), "M_WaterStain")
                    for s in (-1, 1):
                        nc.cylinder((s * 0.1, 0.18, 0.93), 0.015, 0.12, "M_DetSilver", seg=6)
                nc.cylinder((0.0, 0.2, 0.0), 0.02, 0.84, RUST, seg=6)
            if j == 1:
                rubble(nc, (far + fs * 0.6, v - 0.2), 0.35, 6, rng, mats=("M_IntTrimWhite",), zc=0.0, size=(0.08, 0.22))
        nc.box((far + fs * 0.05, D / 2, 2.4), (0.05, D - 0.4, 0.05), RUST)
        # a claw-foot bath under the window, full of murky water (and a rubber duck)
        tu = W / 2
        with mb.at((tu, 0.5, 0.0)):
            mb.box((0, 0, 0.15), (1.6, 0.74, 0.08), "M_IntTrimWhite")
            for s_ in (-1, 1):
                mb.box((s_ * 0.78, 0, 0.4), (0.08, 0.78, 0.48), "M_IntTrimWhite")
                mb.box((0, s_ * 0.37, 0.4), (1.64, 0.08, 0.48), "M_IntTrimWhite")
            nc.box((0, 0, 0.5), (1.48, 0.62, 0.02), "M_MurkyWater")
            for sx_ in (-1, 1):
                for sy_ in (-1, 1):
                    mb.sphere((sx_ * 0.66, sy_ * 0.26, 0.07), 0.07, "M_OldBrass", seg=6, rings=4)
        # two WC cubicles along the near wall, one door hanging off its hinge
        for j, v in enumerate((1.45, 2.5)):
            with mb.at((near + ns * 0.65, v, 0.0), rot=90.0 * ns):
                mb.box((0, 0.42, 0.2), (0.38, 0.52, 0.4), "M_IntTrimWhite")
                mb.box((0, 0.58, 0.6), (0.4, 0.16, 0.4), "M_IntTrimWhite")
            pu = near + ns * 0.65
            with mb.at((pu, v + 0.52, 0.0)):
                mb.box((0, 0, 1.0), (1.3, 0.04, 1.8), "M_DarkWood")
            if j == 0:
                with mb.at((pu, v - 0.5, 0.0)):
                    mb.box((0, 0, 1.0), (1.3, 0.04, 1.8), "M_DarkWood")
            hx = near + ns * 1.3
            if j == 0:      # door still hanging, ajar
                with mb.at((hx, v - 0.47, 0.15), rot=-25.0 * ns):
                    mb.box((0.0, 0.45, 0.85), (0.04, 0.9, 1.6), ROT)
            else:           # this one came off and lies on the floor
                with mb.at((hx + ns * 0.55, v + 0.1, 0.03), rot=15.0):
                    mb.box((0.0, 0.0, 0.0), (0.85, 1.6, 0.04), ROT)
        DT.coat_hooks(nc, far + fs * 1.6, D, 1.7, 0.0, n=3, dorm="white", jackets=0)
        for k in range(2):
            nc.box((far + fs * (1.35 + 0.25 * k), D - 0.08, 1.35), (0.22, 0.03, 0.55), ("M_IntFabricWhite", "M_DustSheet")[k])
    for j, v in enumerate((1.3, 3.2)):
        mx, my = fr.P(far, v)
        aset.prop("SM_Int_Mirror", (mx, my, z + 1.15), fr.Y(90.0 * fs))
    x, y = fr.P(W / 2 + 0.78, 0.5)
    aset.prop("SM_Int_RubberDuck", (x, y, z + 0.64), fr.Y(140.0))
    with fr.ctx(mb, nc):
        # shelf of bottles over the basins, pipes, a towel rail by the bath, a dead bulb, fallen tiles
        with mb.at((far + fs * 0.1, 2.25, 1.62), rot=90.0 * fs):
            mb.box((0, 0, 0), (2.4, 0.2, 0.03), "M_DarkWood")
        for k in range(9):
            if rng.random() < 0.25:
                continue
            bv = 1.2 + k * 0.24
            nc.cylinder((far + fs * 0.1, bv, 1.635), 0.03, rng.uniform(0.1, 0.22),
                        rng.choice(("M_IntGlassClear", "M_IntTrimWhite", "M_IntFabricBlue", "M_OldBookBrown")), seg=8)
        for vz in (0.3, 2.7):
            nc.box((far + fs * 0.04, D / 2, vz), (0.06, D - 0.2, 0.06), RUST)
        nc.box((W / 2, 0.06, 1.4), (1.2, 0.04, 0.03), "M_OldBrass")
        for k in range(2):
            nc.box((W / 2 - 0.25 + 0.5 * k, 0.07, 1.15), (0.4, 0.03, 0.5), ("M_IntFabricWhite", "M_DustSheet")[k])
        nc.cylinder((W / 2, D * 0.55, fl["top"] - z - 0.6), 0.006, 0.6, "M_Black", seg=4)
        nc.sphere((W / 2, D * 0.55, fl["top"] - z - 0.65), 0.05, "M_IntGlassClear", seg=8, rings=5)
        for _ in range(8):
            rbox(nc, (rng.uniform(0.4, W - 0.4), rng.uniform(1.0, D - 1.5), 0.006), (0.15, 0.15, 0.01), "M_RuinTileWall",
                 yaw=rng.uniform(0, 90))
    _beams(mb, x0, y0, x1, y1, fl["top"], step=1.2, along="x")
    with fr.ctx(mb, nc):
        # linen cupboard by the door, towel hooks over the cubicles, the bath rules, toiletry shelves
        with mb.at((near + ns * 0.3, D - 1.55, 0.0), rot=90.0 * ns):
            mb.box((0, 0, 1.0), (0.9, 0.5, 2.0), "M_DarkWood")
            mb.box((0, -0.255, 1.05), (0.02, 0.01, 1.8), VOID)
            for k in range(4):
                nc.box((0, -0.26, 0.3 + 0.5 * k), (0.84, 0.01, 0.02), ROT)
        for k in range(5):
            hu = near + ns * (0.25 + 0.0)
            hv = 0.95 + 0.42 * k
            nc.box((hu - ns * 0.0, hv, 1.95), (0.04, 0.04, 0.04), "M_OldBrass")
            if k % 2 == 0:
                nc.box((near + ns * 0.04, hv, 1.7), (0.05, 0.32, 0.5), ("M_IntFabricWhite", "M_DustSheet", "M_IntFabricBlue")[k // 2])
        with mb.at((near + ns * 0.25, 0.0, 0.0), rot=180.0):
            for k in range(4):
                mb.box((0, -0.15, 0.4 + 0.42 * k), (0.4, 0.28, 0.025), "M_DarkWood")
            for sxx in (-1, 1):
                mb.box((sxx * 0.2, -0.15, 0.9), (0.025, 0.28, 1.8), "M_DarkWood")
        for k in range(4):
            for j in range(2):
                if rng.random() < 0.3:
                    continue
                nc.cylinder((near + ns * 0.25 - 0.09 + 0.18 * j, 0.15, 0.425 + 0.42 * k), 0.035, rng.uniform(0.1, 0.2),
                            rng.choice(("M_IntGlassClear", "M_IntTrimWhite", "M_IntFabricBlue", "M_OldBookBrown")), seg=8)
    rx, ry = fr.P(far, 4.2)
    K.poster(nc, aset, rx, ry, z + 1.75, fr.Y(90.0 * fs), 0.45, 0.6, "M_OldPaper", text="BATH RULES",
             text_color=(0.25, 0.1, 0.05), text_size=0.06)
    x, y = fr.P(near + ns * 1.55, 3.4)
    aset.prop("SM_Int_Basket", (x, y, z), fr.Y(10.0))
    x, y = fr.P(far + fs * 0.42, 0.42)
    aset.prop("SM_Int_Stool", (x, y, z), fr.Y(20.0))
    x, y = fr.P(far + fs * 1.3, D - 1.3)
    aset.prop("SM_Int_Bucket", (x, y, z), 0.0)
    x, y = fr.P(far + fs * 0.35, D - 0.4)
    aset.prop("SM_Int_Broom", (x, y, z), fr.Y(0.0))
    x, y = fr.P(W / 2, 3.6)
    aset.prop("SM_Int_WetFloor", (x, y, z), fr.Y(rng.uniform(0, 360)))
    _win_inside(mb, nc, sx * 6.0, y1, 0.0, 1.25, WIN_ROWS[fl["row"]][0], WIN_ROWS[fl["row"]][1], rng, curtain=False)
    with fr.ctx(nc):
        _candles(nc, far + fs * 0.3, 3.15, 0.93, rng, 2)
    lx, ly = fr.P(far + fs * 0.9, 3.0)
    aset.light((lx, ly, z + 1.3), WARM, 380.0, 4.5)
    _cobwebs(nc, x0, y0, x1, y1, fl["top"] - 0.28, rng)
    _ceiling_damage(nc, x0, y0, x1, y1, fl["top"], rng, n=4)
    _peel(nc, (x0, y0), (x1, y0), z + 1.6, fl["top"], rng, n=3)
    K.nameplate(mb, aset, door_x + (0.8 if door_x > 0 else -0.8), U_CORR[1] - 0.15, z + 1.6, 0.0, "WASH",
                mat="M_TarnishedGold", color=(0.12, 0.08, 0.05))
    p = fr.P(far + fs * 0.45, D - 0.35)
    t = fr.P(near + ns * 1.2, 0.6)
    K.camera(aset, "washroom" + ("_e" if sx > 0 else "_w") + fl["tag"], (p[0], p[1], z + 1.65), (t[0], t[1], z + 1.0), 16.0)


def _stairwell(aset, mb, nc, rng, sx):
    """The old stairwell bay (B4) linking the two dorm floors: dog-leg timber stair, half landing, top landing
    strip on the 2nd floor; rotten treads, a snapped banister, plaster fallen from the ceiling."""
    xa, xb = sorted((sx * U_ROOMS[3][0], sx * U_ROOMS[3][1]))
    y0, y1 = U_CORR[1], Y1 - WT
    xi = xa if sx > 0 else xb               # side towards the hall (door side)
    xo = xb if sx > 0 else xa               # gable side
    zm = (U_FZ + T_FZ) / 2
    K.floor_planks(mb, xa, y0, xb, y1, U_FZ, mat="M_IntWoodFloorDark", seam=VOID, along="y")
    K.floor_planks(mb, xa, y0, xb, STAIR_LAND, T_FZ, mat="M_IntWoodFloorDark", seam=VOID)
    # flight 1 (door side) climbs to the half landing along the back wall, flight 2 (gable side) climbs back
    _room_wainscot(mb, xa, y0, xb, y1, U_FZ, 1.0, gaps={"s": [(0.0, 1.6)] if sx > 0 else [(xb - xa - 1.6, xb - xa)]})
    _flight(mb, nc, xi + sx * 0.6, STAIR_LAND, U_FZ, zm, 90.0, 1.05, skip=(4,), rail_side=-sx, rail_gap=(),
            mat="M_DarkWood")
    mb.box_mm((xa, STAIR_LAND + 2.8 - 0.02, zm - 0.2), (xb, y1, zm), ROT, mats={"+z": "M_IntWoodFloorDark"})
    _flight(mb, nc, xo - sx * 0.6, STAIR_LAND + 2.8, zm, T_FZ, -90.0, 1.05, skip=(6,), rail_side=-sx, rail_gap=(6, 9),
            mat="M_DarkWood")
    for xx in (xi + sx * 0.08, xo - sx * 0.08):
        mb.box((xx, y1 - 0.08, (U_FZ + zm) / 2), (0.12, 0.12, zm - U_FZ), ROT)
    _rail_line(mb, [(xi + sx * 0.05, STAIR_LAND + 0.04), (xo - sx * 1.15, STAIR_LAND + 0.04)], T_FZ)
    _rail_line(mb, [(xi + sx * 1.2, STAIR_LAND + 2.85), (xo - sx * 1.2, STAIR_LAND + 2.85)], zm)
    for (fl, zz) in ((FL2, U_FZ), (FL3, T_FZ)):
        _cobwebs(nc, xa, y0, xb, y1, fl["top"] - 0.28, rng, size=(0.6, 1.0))
        _peel(nc, (xb, y1), (xa, y1), zz + 0.4, fl["top"], rng, n=6)
        _win_inside(mb, nc, sx * 18.0, Y1 - WT, 0.0, 1.25, WIN_ROWS[fl["row"]][0], WIN_ROWS[fl["row"]][1], rng)
        _win_inside(mb, nc, xo, 7.6, -90.0 * sx, 1.25, WIN_ROWS[fl["row"]][0], WIN_ROWS[fl["row"]][1], rng,
                    curtain=False)
    _ceiling_damage(nc, xa, y0, xb, y1, T_TOP, rng, n=3, hole=((xa + xb) / 2, 7.0, 0.8))
    # debris: plaster and laths on the bottom landing, boards that once nailed the door, a dropped lantern
    rubble(mb, (xi + sx * 1.9, 5.2), 0.6, 9, rng, mats=(STONE, U_CEIL, ROT), zc=U_FZ, size=(0.08, 0.3))
    planks(mb, (xi + sx * 2.0, 6.2), 0.5, 3, rng, zc=U_FZ, length=(0.8, 1.4))
    aset.prop("SM_Int_Lantern", (xi + sx * 0.15, y0 + 0.25, T_FZ), 30.0)
    _portrait(mb, nc, xo, 5.2, zm + 1.55, -90.0 * sx, 0.6, 0.8, eyes=True, tilt=-6.0)
    _portrait(mb, nc, xi, 8.2, U_FZ + 1.7, 90.0 * sx, 0.5, 0.65, tilt=8.0)
    _sconce(mb, nc, aset, sx * 18.0, Y1 - WT, zm + 1.9, 0.0)
    aset.light(((xa + xb) / 2, 6.0, U_FZ + 2.0), WARM, 350.0, 5.0)
    K.camera(aset, "stair_" + ("e" if sx > 0 else "w") + "_1f", (xi + sx * 0.55, y0 + 0.3, U_FZ + 1.65),
             (xo - sx * 0.6, 8.0, zm + 0.6), 16.0)


def _lounge(aset, mb, nc, rng):
    """2nd-floor centre: the floor lounge over the dorm room, and the corridor joining both wings."""
    z = T_FZ
    c0, c1 = U_CORR[0] + 0.15, U_CORR[1] - 0.15
    K.floor_planks(mb, -HX, c0, HX, c1, z, mat="M_IntWoodFloorDark", seam=VOID, along="y")
    _room_wainscot(mb, -HX, c0, HX, c1, z, 1.15, gaps={"n": [(HX - 0.85, HX + 0.85)], "e": [(0.25, 1.45)],
                                                         "w": [(0.25, 1.45)]})
    _beams(mb, -HX, c0, HX, c1, T_TOP, step=1.2, along="y")
    _cobwebs(nc, -HX, c0, HX, c1, T_TOP - 0.28, rng, size=(0.4, 0.7))
    _peel(nc, (-HX, c0), (HX, c0), z + 1.2, T_TOP, rng, n=8)
    for k, x in enumerate((-2.4, 0.0, 2.4)):
        _portrait(mb, nc, x, c0, z + 1.85, 180.0, 0.7, 0.9, eyes=(k == 1), tilt=rng.uniform(-5, 5))
    nc.box_mm((-3.6, 2.62, z), (3.6, 3.38, z + 0.012), "M_Carpet")
    _sconce(mb, nc, aset, -1.2, c0, z + 1.75, 180.0)
    _sconce(mb, nc, aset, 1.2, c0, z + 1.75, 180.0, lit=False)
    K.camera(aset, "corridor_c_3f", (-3.5, 2.6, z + 1.65), (3.6, 3.4, z + 1.0), 18.0)
    # the lounge
    x0, y0, x1, y1 = -HX, HY1, HX, Y1 - WT
    K.floor_planks(mb, x0, y0, x1, y1, z, mat="M_IntWoodFloorDark", seam=VOID)
    DT.dress_room(aset, mb, nc, x0, y0, x1, y1, z, T_TOP, style="ruin", seed=70)
    _room_wainscot(mb, x0, y0, x1, y1, z, 1.0, gaps={"s": [(HX - 0.95, HX + 0.95)], "n": [(1.25, 2.75), (5.25, 6.75)]})
    _beams(mb, x0, y0, x1, y1, T_TOP, step=1.6, along="y")
    _cobwebs(nc, x0, y0, x1, y1, T_TOP - 0.28, rng, size=(0.6, 1.1))
    for (p0, p1) in (((x1, y0), (x1, y1)), ((x0, y1), (x0, y0))):
        _peel(nc, p0, p1, z + 1.05, T_TOP, rng, n=6)
    _ceiling_damage(nc, x0, y0, x1, y1, T_TOP, rng, n=4)
    for x in (-2.0, 2.0):
        _win_inside(mb, nc, x, y1, 0.0, 1.25, WIN_ROWS[2][0], WIN_ROWS[2][1], rng)
    # cold fireplace on the west wall under the founder's portrait, a sheeted sofa group, a card table where a
    # duel was never finished, bookcases, a dead chandelier, a gramophone
    with mb.at((0, 0, z - FZ)), nc.at((0, 0, z - FZ)):
        _cold_fireplace(mb, nc, x0, 6.8, 90.0, rng)
    _portrait(mb, nc, x0, 6.8, z + 2.3, 90.0, 0.9, 1.1, eyes=True)
    for dy in (-0.6, 0.6):
        _candles(nc, x0 + 0.25, 6.8 + dy, z + 1.44, rng, 2)
    aset.light((x0 + 0.8, 6.8, z + 1.6), WARM, 450.0, 5.0)
    _sheeted(mb, -1.6, 6.8, z, -90.0, 2.0, 0.9, 0.85, kind="sofa")
    _sheeted(mb, 0.6, 5.4, z, 30.0, 0.9, 0.85, 0.95)
    aset.prop("SM_Int_CoffeeTable", (-0.5, 6.8, z), 0.0)
    aset.prop("SM_Int_TeaSet", (-0.5, 6.8, z + 0.49), 40.0)
    aset.prop("SM_Int_RoundTableB", (2.3, 7.4, z), 0.0)
    for (cx, cy, a_) in ((1.6, 7.3, -80.0), (3.0, 7.5, 95.0)):
        aset.prop("SM_Int_WoodChair", (cx, cy, z), a_)
    DT.card_spread(nc, 2.15, 7.3, z + 0.751, 90.0, 5, 11)
    DT.card_spread(nc, 2.45, 7.5, z + 0.752, -90.0, 3, 12)
    DT.deck_box(nc, 2.3, 7.75, z + 0.75, 15.0, "M_OldBookRed")
    _candle(nc, 2.5, 7.1, z + 0.75, h=0.08)
    aset.light((2.3, 7.4, z + 1.3), WARM, 380.0, 4.5)
    with mb.at((x1 - 0.19, 5.0, z), rot=-90.0), nc.at((x1 - 0.19, 5.0, z), rot=-90.0):
        _old_bookcase(mb, nc, rng, w=1.0, fill=0.7)
    with mb.at((x1 - 0.19, 8.6, z), rot=-90.0), nc.at((x1 - 0.19, 8.6, z), rot=-90.0):
        _old_bookcase(mb, nc, rng, w=1.0, fill=0.55)
    _spilled_books(nc, 3.0, 6.0, z, 0.5, 6, rng)
    _hanging_chandelier(mb, 0.0, 6.7, T_TOP, tilt=-7.0)
    aset.prop("SM_Int_Radio", (-3.4, y1 - 0.4, z), 160.0)
    _toppled_chair(mb, (1.1, 4.6, z), 120.0, rng)
    _papers(nc, 0.5, 6.4, z, 1.6, 8, rng)
    aset.prop("SM_Int_GrandfatherClock", (3.2, y0 + 0.25, z), 180.0)
    K.camera(aset, "lounge_3f", (-3.4, 4.45, z + 1.65), (2.6, 8.6, z + 0.7), 16.0)


def _upper_floor(aset, mb, nc, rng):
    plan = {1: [("slept", "201"), ("diary", "202"), ("made", "203"), ("collapsed", "204")],
            -1: [("sheeted", "207"), ("slept", "208"), ("collapsed", "209"), ("made", "210")]}
    backs = {1: [("slept", "205"), ("sheeted", "206")], -1: [("made", "211"), ("slept", "212")]}
    plan3 = {1: [("sheeted", "301"), ("made", "302"), ("slept", "303"), ("sheeted", "304")],
             -1: [("collapsed", "308"), ("slept", "309"), ("sheeted", "310"), ("made", "311")]}
    backs3 = {1: [("slept", "305"), ("made", "306"), ("collapsed", "307")],
              -1: [("sheeted", "312"), ("slept", "313"), ("made", "314")]}
    for sx in (1, -1):
        _corridor(aset, mb, nc, rng, sx)
        _washroom(aset, mb, nc, rng, sx)
        for k, (var, num) in enumerate(plan[sx]):
            cam = None
            if (sx, k) in ((1, 1), (-1, 3), (1, 3)):
                cam = "room_" + num
            _upper_room(aset, mb, nc, rng, sx, k, False, var, num, cam)
        for k, (var, num) in enumerate(backs[sx]):
            _upper_room(aset, mb, nc, rng, sx, k + 1, True, var, num, "room_" + num if (sx, k) == (1, 0) else None)
        # second floor (8.6 m window row)
        _corridor(aset, mb, nc, rng, sx, fl=FL3)
        for k, (var, num) in enumerate(plan3[sx]):
            cam = "room_" + num + "_3f" if (sx, k) in ((1, 1), (-1, 0)) else None
            _upper_room(aset, mb, nc, rng, sx, k, False, var, num, cam, fl=FL3)
        for k, (var, num) in enumerate(backs3[sx]):
            cam = "room_" + num + "_3f" if (sx, k) == (1, 1) else None
            _upper_room(aset, mb, nc, rng, sx, k, True, var, num, cam, fl=FL3)
        _stairwell(aset, mb, nc, rng, sx)
    _lounge(aset, mb, nc, rng)


# ---------------------------------------------------------------- the clock tower
def _spiral(mb, nc, cx, cy, z0, z1, r_in, r_out, a0, step_deg, skip=(), rail_gap=(), mat="M_DarkMetal"):
    """Cast-iron spiral stair climbing CCW from angle a0; treads in `skip` have rusted away, the handrail is
    missing over `rail_gap`. The last tread is left out (a landing replaces it). Returns (n, rise)."""
    n = max(4, int(round((z1 - z0) / 0.185)))
    rise = (z1 - z0) / n
    mb.cylinder((cx, cy, z0), r_in, z1 - z0 + 1.0, mat, seg=10)
    posts = []
    for i in range(n - 1):
        a = math.radians(a0 + step_deg * i)
        b = math.radians(a0 + step_deg * (i + 1) + 1.5)
        zt = z0 + rise * (i + 1)
        am = (a + b) / 2
        px, py = cx + math.cos(am) * (r_out - 0.04), cy + math.sin(am) * (r_out - 0.04)
        posts.append((i, px, py, zt))
        if i in skip:
            nc.box((cx + math.cos(a) * r_in * 1.6, cy + math.sin(a) * r_in * 1.6, zt - 0.03), (0.06, 0.04, 0.05), RUST)
            continue
        pts = [(cx + math.cos(a) * r_in, cy + math.sin(a) * r_in), (cx + math.cos(a) * r_out, cy + math.sin(a) * r_out),
               (cx + math.cos(b) * r_out, cy + math.sin(b) * r_out), (cx + math.cos(b) * r_in, cy + math.sin(b) * r_in)]
        mb.prism(pts if K._ccw(pts) else list(reversed(pts)), zt - 0.05, zt, mat)
        # chequer-plate ribs on the tread
        nc.beam((cx + math.cos(am) * (r_in + 0.1), cy + math.sin(am) * (r_in + 0.1), zt + 0.004),
                (px, py, zt + 0.004), 0.03, 0.008, RUST)
    for k, (i, px, py, zt) in enumerate(posts):
        if i in rail_gap:
            continue
        mb.box((px, py, zt + 0.45), (0.03, 0.03, 0.9), mat)
        if k and posts[k - 1][0] not in rail_gap:
            q = posts[k - 1]
            mb.beam((q[1], q[2], q[3] + 0.92), (px, py, zt + 0.92), 0.045, 0.045, mat)
    return n, rise


def _flight(mb, nc, x, y, z0, z1, yaw, width, skip=(), mat=ROT, run=0.28, rail_side=1, rail_gap=()):
    """Straight timber flight from (x, y, z0) climbing along local +x; stringers both sides, a handrail on the
    open side (local +y * rail_side). Rotten treads in `skip` are missing."""
    n = max(2, int(round((z1 - z0) / 0.18)))
    rise = (z1 - z0) / n
    with mb.at((x, y, z0), rot=yaw), nc.at((x, y, z0), rot=yaw):
        for i in range(n):
            zt = rise * (i + 1)
            if i in skip:
                continue
            mb.box_mm((run * i, -width / 2, zt - 0.045), (run * (i + 1) + 0.02, width / 2, zt), mat)
        L = run * n
        for s in (-1, 1):
            mb.beam((-0.05, s * (width / 2 + 0.03), -0.12), (L, s * (width / 2 + 0.03), z1 - z0 - 0.12), 0.06, 0.28,
                    "M_DarkWood")
        yy = rail_side * (width / 2 + 0.03)
        for k in range(0, n + 1, 3):
            if k in rail_gap:
                continue
            mb.box((run * k + 0.1, yy, rise * k + 0.45), (0.05, 0.05, 0.9), "M_DarkWood")
        mb.beam((0.05, yy, 0.95), (L * 0.55, yy, (z1 - z0) * 0.55 + 0.95), 0.06, 0.05, "M_DarkWood")
        if not rail_gap:
            mb.beam((L * 0.55, yy, (z1 - z0) * 0.55 + 0.95), (L, yy, z1 - z0 + 0.95), 0.06, 0.05, "M_DarkWood")
        else:   # the upper handrail has snapped and hangs down
            mb.beam((L * 0.55, yy, (z1 - z0) * 0.55 + 0.95), (L * 0.7, yy + rail_side * 0.25, (z1 - z0) * 0.3), 0.06,
                    0.05, "M_DarkWood")
    return n, rise


def _rail_line(mb, pts, z, mat="M_DarkWood"):
    for (a, b) in zip(pts, pts[1:]):
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        nb = max(1, int(L / 0.3))
        for k in range(nb + 1):
            t = k / nb
            mb.box((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, z + 0.45), (0.05, 0.05, 0.9), mat)
        mb.beam((a[0], a[1], z + 0.95), (b[0], b[1], z + 0.95), 0.07, 0.06, mat)


def _gear(mb, nc, c, r, t, rot_axis, mat="M_OldBrass", teeth=None, spokes=4):
    """Clock wheel at centre c, radius r, thickness t; rot_axis 'x' or 'y' = the arbor direction."""
    rx, ry = (0.0, 90.0) if rot_axis == "x" else (90.0, 0.0)
    with mb.at(c, rot_x=rx, rot_y=ry), nc.at(c, rot_x=rx, rot_y=ry):
        mb.torus((0, 0, 0), r - 0.03, 0.03, mat, seg=20, tube_seg=4)
        mb.cylinder((0, 0, -t), 0.05 + r * 0.08, 2 * t + 0.08, mat, seg=8)
        for k in range(spokes):
            a = math.tau * k / spokes
            mb.beam((0, 0, 0), (math.cos(a) * (r - 0.03), math.sin(a) * (r - 0.03), 0), 0.03, t, mat)
        nt = teeth or max(10, int(r * 60))
        for k in range(nt):
            a = math.tau * k / nt
            with nc.at((math.cos(a) * r, math.sin(a) * r, 0), rot=math.degrees(a)):
                nc.box((0.0, 0, 0), (0.035, 0.022, t), mat)


def _bell(mb, nc, x, y, z, s=1.0, yaw=0.0, lying=False):
    prof = [(0.06 * s, 0.62 * s), (0.2 * s, 0.6 * s), (0.27 * s, 0.45 * s), (0.3 * s, 0.2 * s), (0.42 * s, 0.03 * s),
            (0.45 * s, 0.0)]
    with mb.at((x, y, z), rot=yaw, rot_x=(-80 if lying else 0)):
        mb.lathe(list(reversed(prof)), "M_OldBrass", seg=16, cap_top=True, cap_bottom=False)
        mb.box((0, 0, 0.66 * s), (0.08 * s, 0.2 * s, 0.1 * s), RUST)


def _tower_rooms(aset, mb, nc, rng):
    x0, y0, x1, y1 = TIN
    cx, cy, ro = SPIRAL
    # ---- spiral stair: hall floor -> store room (two rusted-through treads, the handrail broken off)
    n, rise = _spiral(mb, nc, cx, cy, FL, TFL[0], 0.1, ro, 98.0, 26.0, skip=(12, 23), rail_gap=range(19, 27))
    a_last = math.radians(98.0 + 26.0 * (n - 1))
    land = [(cx + math.cos(a_last) * 0.1, cy + math.sin(a_last) * 0.1),
            (cx + math.cos(a_last) * ro, cy + math.sin(a_last) * ro),
            (SPIRAL_HOLE[2], cy + math.sin(a_last) * ro), (SPIRAL_HOLE[2], SPIRAL_HOLE[3]),
            (cx, SPIRAL_HOLE[3]), (cx, cy + 0.1)]
    mb.prism(land if K._ccw(land) else list(reversed(land)), TFL[0] - 0.2, TFL[0], ROT)
    # someone laid a plank over the first missing tread
    a12 = math.radians(98.0 + 26.0 * 12.5)
    rbox(nc, (cx + math.cos(a12) * 0.65, cy + math.sin(a12) * 0.65, FL + rise * 13 - 0.02), (0.22, 0.75, 0.03), ROT,
         yaw=math.degrees(a12) + 90.0)
    _rail_line(mb, [(x0 + 0.05, SPIRAL_HOLE[3] + 0.05), (cx - 0.05, SPIRAL_HOLE[3] + 0.05)], TFL[0])
    _rail_line(mb, [(SPIRAL_HOLE[2] + 0.05, y0 + 0.05), (SPIRAL_HOLE[2] + 0.05, cy + math.sin(a_last) * ro - 0.05)],
               TFL[0])
    # ---- store room (old furniture taken up into the tower)
    z = TFL[0]
    K.slab(mb, x0, y0, x1, y1, z, 0.03, "M_IntWoodFloorDark", bottom=ROT, side=ROT, holes=[SPIRAL_HOLE])
    DT.dress_room(aset, mb, nc, x0, y0, x1, y1, z, TCEIL[0], style="ruin", seed=60)
    _flight(mb, nc, FLIGHT_A[0], FLIGHT_A[1], TFL[0], TFL[1], 90.0, 1.0, skip=(6, 14), rail_gap=())
    for xw in (-2.2, 2.2):
        _win_inside(mb, nc, xw, y0, 180.0, 1.2, 8.6, 1.8, rng)
    _beams(mb, x0, y0, x1, y1, TCEIL[0], step=1.9, along="x")
    _peel(nc, (x1, y1), (x0, y1), z + 0.3, TCEIL[0], rng, n=5)
    _cobwebs(nc, x0, y0, x1, y1, TCEIL[0] - 0.28, rng, size=(0.6, 1.1))
    # stacked school desks, dust-sheeted sofa and chairs, crates, rolled carpets, leaning portraits
    for k in range(3):
        with mb.at((-3.2 + 0.05 * k, -3.25, z + 0.78 * k), rot=6.0 * k - 4.0, rot_x=(180.0 if k % 2 else 0.0)):
            dz = 0.76 if k % 2 else 0.0
            mb.box((0, 0, dz + (-0.74 if k % 2 else 0.74)), (0.7, 0.5, 0.04), "M_DarkWood")
            for sx_ in (-1, 1):
                for sy_ in (-1, 1):
                    mb.box((sx_ * 0.3, sy_ * 0.2, dz + (-0.37 if k % 2 else 0.37)), (0.04, 0.04, 0.72), RUST)
    _sheeted(mb, -0.6, -3.15, z, 0.0, 1.9, 0.8, 0.85, kind="sofa")
    _sheeted(mb, 0.95, -4.6, z, -70.0, 0.85, 0.8, 0.95)
    _sheeted(mb, -2.0, -5.0, z, 110.0, 0.85, 0.8, 0.95)
    for (bx, by, bz, bs, byaw) in ((1.0, -9.85, 0.0, 0.62, 12.0), (1.05, -9.8, 0.62, 0.5, -20.0),
                                   (0.3, -9.9, 0.0, 0.5, 4.0)):
        _crate(mb, nc, bx, by, z + bz, bs, byaw)
    aset.prop("SM_Int_Box", (0.3, -9.9, z + 0.5), 35.0)
    aset.prop("SM_Int_Lantern", (1.05, -9.8, z + 1.12), 0.0)
    aset.light((1.0, -9.2, z + 1.6), WARM, 500.0, 6.0)
    for k in range(3):
        with mb.at((-3.7 + 0.04 * k, -7.6 + k * 0.4, z + 0.18 + (0.3 if k == 2 else 0.0))):
            with mb.at((0, 0, 0), rot_x=90.0, rot_y=90.0 if k < 2 else 70.0):
                mb.cylinder((0, 0, -0.0), 0.17, 1.6 if k else 1.3, ("M_Carpet", "M_IntFabricBeige", "M_Carpet")[k], seg=8)
    for k in range(3):
        with mb.at((-0.6 + 0.08 * k, y0 + 0.12 + 0.07 * k, z), rot_x=-10.0 - 3 * k):
            _portrait(mb, nc, 0.0, 0.0, 0.62 + 0.04 * k, 0.0, 0.9 - 0.1 * k, 1.15 - 0.1 * k, sitter=(k != 1))
    with mb.at((0, 0, z)), nc.at((0, 0, z)):
        _trunk(mb, nc, 1.6, -3.1, 0.0, open_=True)
        _trunk(mb, nc, -1.0, -7.4, 75.0)
    # the dressmaker's dummy (it was facing the wall... wasn't it?), the old tower bell lying on its side
    with mb.at((-0.4, -7.2, z), rot=35.0):
        mb.cylinder((0, 0, 0), 0.22, 0.04, "M_DarkWood", seg=8)
        mb.cylinder((0, 0, 0.04), 0.02, 0.9, "M_DarkWood", seg=6)
        mb.lathe([(0.0, 0.94), (0.16, 0.95), (0.19, 1.05), (0.15, 1.2), (0.19, 1.38), (0.12, 1.5), (0.05, 1.58),
                  (0.0, 1.6)], "M_DustSheet", seg=12, cap_top=False, cap_bottom=False)
    _bell(mb, nc, 0.6, -6.6, z + 0.3, 1.0, 20.0, lying=True)
    _papers(nc, 0.0, -6.0, z, 1.6, 8, rng)
    DT.floor_clutter(nc, aset, x0 + 0.2, y0 + 0.2, x1 - 1.4, y1, z, kind="ruin", n=4, seed=61,
                     clear=[(x0, y0, -1.6, -8.4), (x0, -8.0, -2.9, -5.6), (-0.2, y0, 2.0, -9.2)])
    _store_extras(aset, mb, nc, rng, z)
    K.camera(aset, "tower_store", (2.2, -3.1, z + 1.65), (-2.4, -8.6, z + 0.5), 16.0)

    # ---- the clock keeper's room
    z = TFL[1]
    K.slab(mb, x0, y0, x1, y1, z, 0.03, "M_IntWoodFloorDark", bottom=ROT, side=ROT,
           holes=[(2.85, -8.0, x1, -4.02)])
    DT.dress_room(aset, mb, nc, x0, y0, x1, y1, z, TCEIL[1], style="ruin", seed=61)
    _rail_line(mb, [(2.8, -4.05), (2.8, -8.05), (x1 - 0.05, -8.05)], z)
    _flight(mb, nc, FLIGHT_B[0], FLIGHT_B[1], TFL[1], TFL[2], -90.0, 1.0, skip=(9, 10, 16), rail_gap=(15, 18))
    rbox(nc, (FLIGHT_B[0], FLIGHT_B[1] - 0.28 * 9.9, z + 0.181 * 10 + 0.0), (0.7, 0.24, 0.03), ROT)   # plank bridge
    for xw in (-1.0, 1.0):
        _win_inside(mb, nc, xw, y0, 180.0, 0.8, 12.6, 2.2, rng)
    _win_inside(mb, nc, x1, -7.8, -90.0, 1.2, 13.5, 1.6, rng)
    _win_inside(mb, nc, x0, -7.8, 90.0, 1.2, 13.5, 1.6, rng, curtain=False)
    _peel(nc, (x1, y1), (x0, y1), z + 0.3, TCEIL[1], rng, n=5)
    _cobwebs(nc, x0, y0, x1, y1, TCEIL[1] - 0.02, rng, size=(0.5, 0.9))
    K.rug(nc, -1.6, -8.4, 1.6, -5.6, z, "M_Carpet", "M_TarnishedGold")
    aset.prop("SM_Int_OldBed", (-0.4, -9.88, z), 90.0)
    with nc.at((-0.4, -9.88, z), rot=90.0):
        nc.box((0, -0.02, 0.5), (0.84, 1.9, 0.14), "M_OldPaper")
        nc.box((0, 0.72, 0.62), (0.56, 0.32, 0.12), "M_IntFabricWhite")
        nc.box((0.1, -0.3, 0.6), (0.9, 1.1, 0.06), "M_IntFabricNavy")
    # keeper's desk: ledger, oil lamp, pocket watch, spectacles, keys
    _keeper_desk(mb, nc, aset, 0.9, y1 - 0.32, z, rng)
    aset.prop("SM_Int_WoodChair", (0.95, y1 - 0.95, z), 160.0)
    aset.prop("SM_Int_Stove", (-1.8, y1 - 0.35, z), 0.0)
    aset.prop("SM_Int_Kettle", (-1.8, y1 - 0.4, z + 0.86), 30.0)
    nc.cylinder((-1.8, y1 - 0.25, z + 0.86), 0.06, TCEIL[1] - z - 0.86, RUST, seg=8)
    aset.prop("SM_Int_Shelves", (2.2, y0 + 0.2, z), 180.0)
    DT.shelf_fill(nc, aset, 2.2, y0 + 0.2, [z + 0.05, z + 0.42, z + 0.78], 180.0, 0.5, 0.3, kind="kitchen", seed=62)
    aset.prop("SM_Int_RockingChair", (-1.9, -7.9, z), 140.0)
    aset.prop("SM_Int_Boots", (-1.1, y1 - 0.25, z), 0.0)
    DT.coat_hooks(nc, -0.5, y1, z + 1.75, 0.0, n=3, dorm="obelisk", jackets=1, seed=5)
    DT.calendar(nc, 1.3, y1, z + 1.65, 0.0, seed=8)
    aset.prop("SM_Int_WallClock", (0.0, y0, z + 2.45), 180.0)
    # the clock weights hang down from the movement above, on chains through the ceiling
    for (wx, wz) in ((0.4, 12.9), (1.0, 13.6)):
        nc.cylinder((wx, -6.8, wz), 0.12, 0.55, "M_DarkMetal", seg=10)
        mb.cylinder((wx, -6.8, wz + 0.55), 0.012, TCEIL[1] - wz - 0.55, RUST, seg=4)
    aset.prop("SM_Int_OilLamp", (0.45, y1 - 0.25, z + 0.76), 0.0)
    aset.light((0.5, y1 - 0.8, z + 1.3), WARM, 550.0, 6.0)
    _papers(nc, 0.4, -5.0, z, 1.2, 5, rng)
    _keeper_extras(aset, mb, nc, rng, z)
    K.camera(aset, "keeper", (2.3, -3.15, z + 1.65), (-1.0, -9.4, z + 0.5), 16.0)

    # ---- the clockwork room: stopped at the hour the students vanished
    z = TFL[2]
    K.slab(mb, x0, y0, x1, y1, z, 0.03, "M_IntWoodFloorDark", bottom=ROT, side=ROT,
           holes=[(x0, -8.98, -2.85, -5.3)])
    DT.dress_room(aset, mb, nc, x0, y0, x1, y1, z, TCEIL[2], style="ruin", seed=62)
    _rail_line(mb, [(x0 + 0.05, -5.25), (-2.8, -5.25), (-2.8, -8.9)], z)
    for (wx, wy, yaw) in ((x1, -7.5, -90.0), (x1, -5.5, -90.0), (x0, -7.5, 90.0), (x0, -5.5, 90.0),
                          (1.0, y1, 0.0), (-1.0, y1, 0.0)):
        _win_inside(mb, nc, wx, wy, yaw, 0.8, 16.0, 2.6, rng, curtain=False)
    _beams(mb, x0, y0, x1, y1, TCEIL[2], step=1.9, along="y")
    _cobwebs(nc, x0, y0, x1, y1, TCEIL[2] - 0.28, rng, size=(0.7, 1.3))
    # back of the dial on the front wall, motion works and the drive rod to the movement
    with mb.at((0.0, y0, 17.6), rot_x=-90.0), nc.at((0.0, y0, 17.6), rot_x=-90.0):
        mb.cylinder((0, 0, 0), 1.3, 0.04, "M_PortraitFace", seg=24)
        mb.torus((0, 0, 0.04), 1.28, 0.04, RUST, seg=24, tube_seg=4)
        for k in range(8):
            a = math.tau * k / 8
            mb.beam((0, 0, 0.06), (math.cos(a) * 1.25, math.sin(a) * 1.25, 0.06), 0.05, 0.05, RUST)
        mb.box((0, 0, 0.2), (0.4, 0.4, 0.3), "M_DarkMetal")
    mov = (0.4, -6.7)
    mb.beam((0.0, y0 + 0.3, 17.6), (mov[0] - 0.2, mov[1] - 0.5, z + 1.15), 0.05, 0.05, "M_DarkMetal")
    # the movement: iron cage frame with wheels, escapement, barrels, pendulum
    fx, fy, fw, fd, fh = mov[0], mov[1], 1.8, 1.0, 1.3
    with mb.at((fx, fy, z)):
        for sx_ in (-1, 1):
            for sy_ in (-1, 1):
                mb.box((sx_ * fw / 2, sy_ * fd / 2, fh / 2 + 0.2), (0.08, 0.08, fh), "M_DarkMetal")
            mb.box((sx_ * fw / 2, 0, fh + 0.2), (0.08, fd, 0.08), "M_DarkMetal")
            mb.box((sx_ * fw / 2, 0, 0.3), (0.08, fd, 0.08), "M_DarkMetal")
        for sy_ in (-1, 1):
            mb.box((0, sy_ * fd / 2, fh + 0.2), (fw, 0.08, 0.08), "M_DarkMetal")
            mb.box((0, sy_ * fd / 2, 0.3), (fw, 0.08, 0.08), "M_DarkMetal")
        mb.box((0, 0, 0.1), (fw + 0.3, fd + 0.3, 0.2), "M_DarkWood")
        for (ax, r, t) in ((-0.45, 0.42, 0.04), (0.15, 0.3, 0.035), (0.55, 0.2, 0.03)):
            _gear(mb, nc, (ax, 0.0, 0.85 if r > 0.4 else 1.0), r, t, "y")
            mb.beam((ax, -fd / 2, 0.85 if r > 0.4 else 1.0), (ax, fd / 2, 0.85 if r > 0.4 else 1.0), 0.03, 0.03, RUST)
        _gear(mb, nc, (-0.2, 0.25, 0.55), 0.22, 0.03, "x")
        for (bx_, by_) in ((0.0, -6.8 - fy), (0.6, -6.8 - fy)):
            with mb.at((bx_, by_, 0.6), rot_y=90.0):
                mb.cylinder((0, 0, -0.18), 0.1, 0.36, "M_DarkWood", seg=10)
        mb.box((0.62, 0.0, fh + 0.35), (0.08, 0.3, 0.25), "M_OldBrass")
        mb.beam((0.62, 0.0, fh + 0.3), (0.62, -0.05, 0.25), 0.02, 0.02, "M_OldBrass")
    for (wx, wz) in ((0.4, 0.6), (1.0, 0.6)):
        mb.cylinder((wx, -6.8, z - 0.25), 0.012, wz + 0.25, RUST, seg=4)
    with mb.at((fx + 0.62, fy - 0.05, z + 0.25)):
        with mb.at((0, 0, 0), rot_x=90.0):
            mb.cylinder((0, 0, -0.02), 0.17, 0.04, "M_OldBrass", seg=16)
    # the bell in its timber frame at the back, the hammer wire
    with mb.at((-0.4, y1 - 0.9, z)):
        for sx_ in (-1, 1):
            mb.beam((sx_ * 0.9, -0.5, 0.0), (sx_ * 0.6, 0.0, 2.4), 0.14, 0.14, "M_DarkWood")
            mb.beam((sx_ * 0.9, 0.5, 0.0), (sx_ * 0.6, 0.0, 2.4), 0.14, 0.14, "M_DarkWood")
        mb.box((0, 0, 2.45), (1.6, 0.18, 0.18), "M_DarkWood")
        for sx_ in (-1, 1):
            mb.box((sx_ * 0.9, 0, 0.06), (0.18, 1.2, 0.12), "M_DarkWood")
    _bell(mb, nc, -0.4, y1 - 0.9, z + 1.18, 1.25)
    nc.beam((-0.15, y1 - 0.9, z + 1.6), (fx - 0.3, fy + 0.45, z + 1.5), 0.012, 0.012, RUST)
    # keeper's workbench along the west wall (behind the stair rail)
    with mb.at((x0 + 0.32, -4.0, z), rot=90.0), nc.at((x0 + 0.32, -4.0, z), rot=90.0):
        mb.box((0, 0, 0.88), (1.6, 0.6, 0.06), "M_DarkWood")
        for sx_ in (-1, 1):
            for sy_ in (-1, 1):
                mb.box((sx_ * 0.74, sy_ * 0.24, 0.43), (0.07, 0.07, 0.86), "M_DarkWood")
        mb.box((0, 0.0, 0.18), (1.5, 0.5, 0.03), "M_DarkWood")
        nc.cylinder((0.3, 0.05, 0.91), 0.16, 0.02, "M_OldBrass", seg=16)
        nc.cylinder((0.55, -0.1, 0.91), 0.09, 0.02, "M_OldBrass", seg=12)
        nc.cylinder((-0.5, 0.12, 0.91), 0.05, 0.16, "M_DetGrille", seg=8)       # oil can
        nc.beam((-0.5, 0.12, 1.05), (-0.62, 0.0, 1.12), 0.012, 0.012, "M_DetGrille")
        nc.box((-0.15, -0.1, 0.915), (0.3, 0.2, 0.01), "M_OldPaper")
        nc.box((0.0, -0.2, 0.92), (0.22, 0.02, 0.02), "M_DetSilver")
        rbox(nc, (-0.3, -0.15, 0.92), (0.25, 0.18, 0.02), "M_IntFabricBeige", yaw=20)
    aset.prop("SM_Int_Toolbox", (x0 + 0.38, -4.45, z + 0.91), 80.0)
    aset.prop("SM_Int_OilLamp", (x0 + 0.35, -3.4, z + 0.91), 0.0)
    aset.prop("SM_Int_MetalStool", (x0 + 1.0, -4.0, z), 70.0)
    aset.prop("SM_Int_Ladder", (2.4, y0 + 0.35, z), 180.0)
    aset.light((x0 + 0.8, -3.6, z + 1.5), WARM, 550.0, 6.5)
    aset.light((0.4, -6.7, z + 2.6), (1.0, 0.85, 0.65), 400.0, 6.0)
    # pigeons have moved in: droppings under the windows, feathers, a nest on a sill
    for (wx, wy) in ((x1 - 0.4, -7.5), (x1 - 0.4, -5.5), (1.0, y1 - 0.4), (-1.0, y1 - 0.4), (x0 + 0.4, -7.0)):
        for _ in range(6):
            nc.cylinder((wx + rng.uniform(-0.4, 0.4), wy + rng.uniform(-0.3, 0.3), z + 0.001), rng.uniform(0.02, 0.06),
                        0.004, "M_BirdMess", seg=6)
        rbox(nc, (wx + rng.uniform(-0.3, 0.3), wy + rng.uniform(-0.3, 0.3), z + 0.005), (0.1, 0.025, 0.004),
             "M_OldPaper", yaw=rng.uniform(0, 180))
    nc.cylinder((1.0, y1 + 0.25, 16.02), 0.16, 0.08, "M_IntWood", seg=8)
    # spare wheels leaning on the west wall
    for k, r in enumerate((0.35, 0.25)):
        with mb.at((x0 + 0.12 + 0.06 * k, -3.6 + 0.5 * k, z + r), rot=90.0, rot_y=-8.0):
            mb.cylinder((0, 0, -0.02), r, 0.04, "M_OldBrass", seg=16)
    _papers(nc, 1.2, -8.8, z, 0.9, 5, rng)
    aset.interact("clock", (0.0, y0 + 0.8, z + 1.0), 0.0, title="The tower clock",
                  text="The clock stopped at 12:07 - the night the last students disappeared. Its pendulum hangs "
                       "still, but something has been oiling the wheels.", radius=2.5)
    _clock_extras(aset, mb, nc, rng, z)
    K.camera(aset, "clockwork", (3.1, -3.0, z + 1.65), (-1.6, -8.4, z + 0.9), 16.0)


def _timber_frame(mb, x0, y0, x1, y1, z, h, skip=()):
    """Posts, a wall plate and diagonal braces against the inside of the tower walls (wall name -> skip)."""
    for name, (p0, p1) in (("s", ((x0, y0), (x1, y0))), ("e", ((x1, y0), (x1, y1))), ("n", ((x1, y1), (x0, y1))),
                           ("w", ((x0, y1), (x0, y0)))):
        if name in skip:
            continue
        L, (ux, uy), (nx, ny), yaw = K._frame2d(p0, p1)
        with mb.at((p0[0], p0[1], z), rot=yaw):
            mb.box((L / 2, 0.08, h - 0.1), (L, 0.16, 0.2), "M_DarkWood")
            for u in (0.1, L / 2, L - 0.1):
                mb.box((u, 0.08, h / 2), (0.18, 0.16, h), "M_DarkWood")
            for u in (0.1, L / 2, L - 0.1):        # knee braces under the plate
                for sg in (-1, 1):
                    if 0.0 < u + sg * 0.7 < L:
                        mb.beam((u, 0.08, h - 1.0), (u + sg * 0.7, 0.08, h - 0.25), 0.1, 0.1, "M_DarkWood")


def _store_extras(aset, mb, nc, rng, z):
    x0, y0, x1, y1 = TIN
    _room_wainscot(mb, x0, y0, x1, y1, z, 0.9)
    # an old bookcase and a stack of chairs on the back wall, a mirror leaning on it
    with mb.at((-2.2, y1 - 0.2, z)), nc.at((-2.2, y1 - 0.2, z)):
        _old_bookcase(mb, nc, rng, w=1.0, fill=0.6)
    for k in range(3):
        with mb.at((2.6, -2.95, z + 0.47 * k), rot=12.0 * k, rot_x=(180.0 if k % 2 else 0.0)):
            dz = 0.94 if k % 2 else 0.0
            sg = -1 if k % 2 else 1
            mb.box((0, 0, dz + sg * 0.46), (0.44, 0.44, 0.04), "M_DarkWood")
            for sx_ in (-1, 1):
                for sy_ in (-1, 1):
                    mb.box((sx_ * 0.19, sy_ * 0.19, dz + sg * 0.22), (0.04, 0.04, 0.44), "M_DarkWood")
                mb.box((sx_ * 0.19, 0.19, dz + sg * 0.7), (0.04, 0.04, 0.5), "M_DarkWood")
            mb.box((0, 0.19, dz + sg * 0.9), (0.42, 0.04, 0.1), "M_DarkWood")
    for k, (cx, cy, s_, yaw) in enumerate(((-3.4, -4.3, 0.55, 10.0), (-3.35, -4.35, 0.45, -15.0), (1.9, -7.6, 0.5, 30.0))):
        _crate(mb, nc, cx, cy, z + (0.55 if k == 1 else 0.0), s_, yaw)
    aset.prop("SM_Int_Suitcase", (-0.2, -5.6, z), 75.0)
    aset.prop("SM_Int_HandTruck", (2.4, -6.3, z), -60.0)
    _spilled_books(nc, -1.6, -3.6, z, 0.4, 4, rng)
    aset.light((-0.5, -5.5, z + 2.6), MOON, 300.0, 5.0)


def _keeper_extras(aset, mb, nc, rng, z):
    x0, y0, x1, y1 = TIN
    _room_wainscot(mb, x0, y0, x1, y1, z, 0.9)
    _beams(mb, x0, y0, x1, y1, TCEIL[1], step=1.9, along="x")
    # table with two chairs: the keeper played cards with someone
    aset.prop("SM_Int_RoundTableB", (-0.8, -5.6, z), 0.0)
    aset.prop("SM_Int_WoodChair", (-1.4, -5.3, z), -120.0)
    aset.prop("SM_Int_WoodChair", (-0.2, -6.0, z), 70.0)
    DT.card_spread(nc, -0.85, -5.55, z + 0.75, 20.0, 5, 3)
    DT.card_spread(nc, -0.75, -5.75, z + 0.751, -160.0, 4, 4)
    DT.deck_box(nc, -0.55, -5.4, z + 0.75, 30.0, "M_IntFabricRed")
    DT.mug(nc, -1.05, -5.75, z + 0.75, seed=3)
    _candle(nc, -0.7, -5.35, z + 0.75, h=0.07)
    # bookcase on the east wall (between the stair hole and the front wall), firewood under the stair
    with mb.at((x1 - 0.19, -9.2, z), rot=-90.0), nc.at((x1 - 0.19, -9.2, z), rot=-90.0):
        _old_bookcase(mb, nc, rng, w=1.0, h=1.9, fill=0.75)
    for k in range(14):
        rbox(mb, (x0 + 0.25 + 0.17 * (k % 3), -8.6 + rng.uniform(-0.05, 0.05), z + 0.08 + 0.15 * (k // 3)),
             (0.14, 0.9, 0.14), "M_DarkWood" if k % 4 else ROT, roll=rng.uniform(-6, 6))
    with mb.at((0, 0, z)), nc.at((0, 0, z)):
        _trunk(mb, nc, 1.05, -9.9, 0.0)
    aset.prop("SM_Int_Bucket", (2.95, -9.95, z), 0.0)
    _portrait(mb, nc, -0.1, y1, z + 1.7, 0.0, 0.5, 0.4, sitter=False)
    nc.box((-0.1, y1 - 0.03, z + 1.7), (0.36, 0.006, 0.26), "M_PortraitFace")      # the class photo
    _papers(nc, -0.9, -6.3, z, 0.8, 4, rng)


def _clock_extras(aset, mb, nc, rng, z):
    x0, y0, x1, y1 = TIN
    _timber_frame(mb, x0, y0, x1, y1, z, TCEIL[2] - z, skip=("s",))
    # the striking train: a second, smaller cage, and the pendulum in its wooden case
    with mb.at((-1.6, -7.0, z)):
        for sx_ in (-1, 1):
            for sy_ in (-1, 1):
                mb.box((sx_ * 0.45, sy_ * 0.35, 0.6), (0.06, 0.06, 1.0), "M_DarkMetal")
            mb.box((sx_ * 0.45, 0, 1.1), (0.06, 0.7, 0.06), "M_DarkMetal")
        mb.box((0, 0, 0.08), (1.1, 0.9, 0.16), "M_DarkWood")
    _gear(mb, nc, (-1.6, -7.0, z + 0.7), 0.3, 0.03, "y", teeth=18)
    _gear(mb, nc, (-1.35, -7.0, z + 0.95), 0.14, 0.025, "y", teeth=12)
    with mb.at((1.9, -8.3, z)), nc.at((1.9, -8.3, z)):
        mb.box((0, 0, 1.2), (0.5, 0.35, 2.4), "M_DarkWood")
        nc.box((0, -0.18, 1.3), (0.34, 0.01, 1.7), "M_IntGlassClear")
        nc.box((0, -0.12, 1.7), (0.02, 0.02, 1.3), "M_OldBrass")
        nc.cylinder((0, -0.12, 0.95), 0.12, 0.03, "M_OldBrass", seg=14)
    # coiled spare chain, an oil drum, crates of spare parts
    for k in range(4):
        nc.torus((2.9, -6.0, z + 0.04 + 0.05 * k), 0.22 - 0.02 * k, 0.025, RUST, seg=12, tube_seg=4)
    mb.cylinder((3.3, -7.0, z), 0.28, 0.85, "M_RustMetal", seg=12)
    _crate(mb, nc, 3.2, -9.7, z, 0.55, 8.0)
    _crate(mb, nc, 3.25, -8.9, z, 0.45, -12.0)
    for k in range(3):
        rbox(nc, (3.2 + rng.uniform(-0.15, 0.15), -9.7 + rng.uniform(-0.15, 0.15), z + 0.57), (0.12, 0.12, 0.02),
             "M_OldBrass", yaw=rng.uniform(0, 90))
    # a hanging oil lantern over the movement (still burning)
    with mb.at((0.4, -6.0, TCEIL[2])), nc.at((0.4, -6.0, TCEIL[2])):
        mb.cylinder((0, 0, -0.8), 0.01, 0.8, RUST, seg=4)
        mb.box((0, 0, -0.85), (0.2, 0.2, 0.04), RUST)
        nc.box((0, 0, -1.0), (0.14, 0.14, 0.22), "M_CandleFlame")
        mb.box((0, 0, -1.13), (0.22, 0.22, 0.04), RUST)
    _papers(nc, -0.5, -4.5, z, 1.0, 5, rng)
    _spilled_books(nc, 2.3, -4.0, z, 0.3, 2, rng)
    # a spare minute hand leaning on the back wall, a ladder up to the spire hatch, crates under the dial
    with mb.at((1.9, y1 - 0.12, z), rot_x=8.0, rot_y=-6.0):
        mb.box((0, 0, 1.1), (0.12, 0.04, 2.2), "M_Black")
        mb.beam((0, 0, 2.2), (0, 0, 2.5), 0.22, 0.04, "M_Black")
        mb.box((0, 0, 0.2), (0.24, 0.05, 0.24), "M_Black")
    for dx in (-0.22, 0.22):
        mb.beam((x1 - 0.55 + dx * 0.0, -4.2 + dx, z), (x1 - 0.12, -4.2 + dx, TCEIL[2] - 0.05), 0.05, 0.06, "M_DarkWood")
    for k in range(1, 12):
        t = k / 12
        mb.box((x1 - 0.55 + 0.43 * t, -4.2, z + (TCEIL[2] - z - 0.05) * t), (0.04, 0.44, 0.04), "M_DarkWood")
    nc.box((x1 - 0.5, -4.2, TCEIL[2] - 0.005), (0.7, 0.7, 0.01), VOID)
    nc.box_mm((x1 - 0.9, -4.6, TCEIL[2] - 0.06), (x1 - 0.1, -4.55, TCEIL[2]), ROT)
    nc.box_mm((x1 - 0.9, -3.85, TCEIL[2] - 0.06), (x1 - 0.1, -3.8, TCEIL[2]), ROT)
    _crate(mb, nc, -0.9, -9.75, z, 0.55, 6.0)
    _crate(mb, nc, -0.85, -9.7, z + 0.55, 0.42, -14.0)
    _crate(mb, nc, 0.4, -9.8, z, 0.5, 20.0)
    _toppled_chair(mb, (1.5, -5.0, z), 50.0, rng)
    _candles(nc, -0.85, -9.7, z + 0.97, rng, 2)


def _keeper_desk(mb, nc, aset, x, y, z, rng):
    with mb.at((x, y, z)), nc.at((x, y, z)):
        mb.box((0, 0, 0.74), (1.2, 0.6, 0.04), "M_DarkWood")
        mb.box((-0.42, 0, 0.36), (0.34, 0.56, 0.72), "M_DarkWood")
        for s in (-1, 1):
            mb.box((0.56, s * 0.25, 0.36), (0.05, 0.05, 0.72), "M_DarkWood")
        nc.box((-0.1, -0.05, 0.775), (0.42, 0.3, 0.03), "M_OldBookBrown")             # the ledger, open
        nc.box((-0.1, -0.05, 0.792), (0.4, 0.28, 0.004), "M_OldPaper")
        nc.cylinder((0.3, -0.12, 0.76), 0.03, 0.012, "M_OldBrass", seg=12)            # pocket watch
        nc.torus((0.3, -0.12, 0.775), 0.015, 0.004, "M_OldBrass", seg=8, tube_seg=4)
        for s in (-1, 1):                                                             # spectacles
            nc.torus((0.15 + s * 0.035, 0.12, 0.765), 0.025, 0.004, "M_DetSilver", seg=10, tube_seg=4)
        nc.torus((0.42, 0.1, 0.765), 0.04, 0.005, RUST, seg=10, tube_seg=4)            # key ring
        for k in range(3):
            rbox(nc, (0.45 + 0.02 * k, 0.05 - 0.03 * k, 0.765), (0.07, 0.015, 0.005), RUST, yaw=40 * k)
        DT.book_stack(nc, -0.45, 0.15, 0.76, 0.0, 3, 9)
        _candle(nc, 0.5, 0.2, 0.76, h=0.1)


# ---------------------------------------------------------------- ground storey: the rooms beyond / behind the salon + library
def _gf_rect(sx, r):
    xa, xb = sorted((sx * r[0], sx * r[2]))
    return xa, r[1], xb, r[3]


def _gf_base(aset, mb, nc, rng, rect, wins, seed, wainscot=1.0, floor="M_IntWoodFloorDark"):
    """Shared shell dressing: boards, wainscot (open at the doorways), beams, cobwebs, peeling paper, the boarded
    windows from inside (moonlight through the gaps), a warm light."""
    x0, y0, x1, y1 = rect
    if floor == "tile":
        mb.box_mm((x0, y0, FZ - 0.03), (x1, y1, FZ), "M_IntTileWhite", skip=("-z",))
    else:
        K.floor_planks(mb, x0, y0, x1, y1, FZ, mat=floor, seam=VOID, along="x" if (x1 - x0) > (y1 - y0) else "y")
    DT.dress_room(aset, mb, nc, x0, y0, x1, y1, FZ, CZ1, style="ruin", seed=seed)
    gaps = {}
    for (side, px, py, w) in DT._doors_on(aset, x0, y0, x1, y1, FZ):
        u = {"s": px - x0, "e": py - y0, "n": x1 - px, "w": y1 - py}[side]
        gaps.setdefault(side, []).append((u - w / 2 - 0.12, u + w / 2 + 0.12))
    for (side, wx, wy) in wins:
        u = {"s": wx - x0, "e": wy - y0, "n": x1 - wx, "w": y1 - wy}[side]
        yaw = {"s": 180.0, "n": 0.0, "w": 90.0, "e": -90.0}[side]
        _boarded_inside(mb, nc, wx, wy, yaw, 1.25, WIN_ROWS[0][0], WIN_ROWS[0][1], rng)
        gaps.setdefault(side, []).append((u - 0.8, u + 0.8))
    _room_wainscot(mb, x0, y0, x1, y1, FZ, wainscot, gaps=gaps)
    _beams(mb, x0, y0, x1, y1, CZ1, step=1.9, along="x" if (x1 - x0) < (y1 - y0) else "y")
    _cobwebs(nc, x0, y0, x1, y1, CZ1 - 0.28, rng, size=(0.5, 0.9))
    for (p0, p1) in (((x0, y0), (x1, y0)), ((x1, y1), (x0, y1))):
        _peel(nc, p0, p1, FZ + wainscot + 0.1, CZ1, rng, n=4)
    if wins:
        side, wx, wy = wins[0]
        aset.light(K.wall_point(wx, wy, {"s": 180.0, "n": 0.0, "w": 90.0, "e": -90.0}[side], 0.8, 2.6), MOON, 350.0, 5.0)
    return (x0 + x1) / 2, (y0 + y1) / 2


def _jars(nc, x, y, yaw, levels, width, rng):
    """Jars, crocks and tins on the boards of a shelf unit centred at (x, y), back at local +Y."""
    with nc.at((x, y, 0.0), rot=yaw):
        for z in levels:
            u = -width / 2 + 0.08
            while u < width / 2 - 0.08:
                r = rng.uniform(0.04, 0.08)
                if rng.random() < 0.8:
                    nc.cylinder((u, 0.0, z), r, rng.uniform(0.1, 0.25), rng.choice(("M_IntGlassClear", "M_OldBrass",
                                "M_OldBookBrown", "M_IntTrimWhite", RUST)), seg=8)
                u += 2 * r + 0.04


def _dresser(mb, nc, x, y, yaw, rng, w=1.2, h=2.0, d=0.45):
    """Kitchen dresser / plate rack against a wall (back at local +Y): cupboard base, open rack with plates."""
    with mb.at((x, y, FZ), rot=yaw), nc.at((x, y, FZ), rot=yaw):
        mb.box((0, 0, 0.45), (w, d, 0.9), "M_DarkWood")
        mb.box((0, d / 2 - 0.12, (0.9 + h) / 2), (w, 0.04, h - 0.9), "M_DarkWood")
        for s_ in (-1, 1):
            mb.box((s_ * (w / 2 - 0.02), d / 2 - 0.15, (0.9 + h) / 2), (0.04, 0.3, h - 0.9), "M_DarkWood")
        for k in range(3):
            zz = 1.2 + 0.3 * k
            mb.box((0, d / 2 - 0.15, zz), (w, 0.3, 0.03), "M_DarkWood")
            n = int((w - 0.1) / 0.2)
            for j in range(n):
                if rng.random() < 0.2:
                    continue
                nc.box((-w / 2 + 0.15 + 0.2 * j, d / 2 - 0.2, zz + 0.11), (0.2, 0.015, 0.2), "M_IntTrimWhite")
        nc.box((0, -d / 2 - 0.005, 0.45), (w - 0.1, 0.01, 0.75), "M_IntWoodDark")

def _range(mb, nc, x, y, yaw):
    """Cast-iron kitchen range against a wall (back at +Y), with its hood and flue."""
    with mb.at((x, y, FZ), rot=yaw), nc.at((x, y, FZ), rot=yaw):
        mb.box((0, 0, 0.45), (1.6, 0.7, 0.9), "M_Black")
        mb.box((0, 0, 0.92), (1.66, 0.74, 0.04), "M_DarkMetal")
        for k in range(3):
            nc.box((-0.5 + 0.5 * k, -0.355, 0.45), (0.38, 0.01, 0.3), "M_DarkMetal")
            nc.box((-0.5 + 0.5 * k, -0.365, 0.62), (0.12, 0.02, 0.03), "M_TarnishedGold")
        mb.box((0, 0.15, 2.0), (1.8, 0.5, 0.7), "M_DarkMetal")
        mb.box((0, 0.3, 2.9), (0.4, 0.3, 1.2), "M_DarkMetal")
        nc.cylinder((-0.4, 0.0, 0.94), 0.16, 0.2, "M_DarkMetal", seg=10)
        nc.cylinder((0.35, -0.05, 0.94), 0.12, 0.14, RUST, seg=10)


def _ground_rooms(aset, mb, nc, rng):
    for sx in (1, -1):
        kit, a_, b_, c_ = (_gf_rect(sx, r) for r in (GF_KIT, GF_A, GF_B, GF_C))
        ox = sx * (X1 - WT)
        # ---------------- behind the salon: the old KITCHEN (east) / behind the library: the LAUNDRY (west)
        cx, cy = _gf_base(aset, mb, nc, rng, kit, [("n", sx * 6.0, Y1 - WT), ("n", sx * 10.0, Y1 - WT)], 80 + sx,
                          floor="tile")
        x0, y0, x1, y1 = kit
        if sx > 0:
            _range(mb, nc, 8.0, y1 - 0.36, 0.0)
            with mb.at((0, 0, FZ)):
                K.counter(mb, 4.62, y0 + 1.6, 5.22, y1 - 0.1, 0.9, "M_DarkWood", "M_OldStoneTrim")
            for k, y in enumerate((6.6, 7.4, 8.2, 9.0)):
                aset.prop(("SM_Int_Pot", "SM_Int_EnamelPot", "SM_Int_Jug", "SM_Int_Bowl")[k], (4.92, y, FZ + 0.9), 30 * k)
            aset.prop("SM_Int_CuttingBoard", (4.92, 7.8, FZ + 0.9), 90.0)
            _dresser(mb, nc, 11.72, 5.7, -90.0, rng)
            for k in range(5):                                             # strings of onions and herbs
                nc.box((6.4 + 0.25 * k, y1 - 0.06, CZ1 - 0.6), (0.06, 0.06, 0.8), ("M_OldBookBrown", "M_OldBookGreen")[k % 2])
            with mb.at((8.4, 6.6, FZ)):                                   # scrubbed work table
                mb.box((0, 0, 0.84), (2.2, 0.9, 0.08), "M_IntWood")
                for xx in (-1.0, 1.0):
                    for yy in (-0.38, 0.38):
                        mb.box((xx, yy, 0.4), (0.08, 0.08, 0.8), "M_DarkWood")
            DT.table_set(nc, aset, 8.4, 6.6, FZ + 0.88, 0.0, kind="kitchen", seed=3)
            aset.prop("SM_Int_Stool", (7.6, 5.8, FZ), 20.0)
            _toppled_chair(mb, (9.6, 5.5, FZ), 60.0, rng)
            aset.prop("SM_Int_SteelShelves", (11.7, 8.6, FZ), -90.0)
            _jars(nc, 11.7, 8.6, -90.0, [FZ + h for h in (0.08, 0.6, 1.12, 1.64)], 1.0, rng)
            with nc.at((8.4, 6.6, CZ1 - 0.6)):                            # pot rack over the table
                nc.box((0, 0, 0), (1.6, 0.04, 0.04), RUST)
                for k in range(5):
                    nc.cylinder((-0.6 + 0.3 * k, 0.0, -0.35), 0.1 - 0.01 * k, 0.16, ("M_TarnishedGold", RUST)[k % 2], seg=8)
                    nc.box((-0.6 + 0.3 * k, 0.0, -0.1), (0.01, 0.01, 0.2), RUST)
            for k in range(6):
                rbox(nc, (rng.uniform(6.0, 10.5), rng.uniform(5.0, 6.0), FZ + 0.01), (0.12, 0.08, 0.01),
                     "M_IntTrimWhite", yaw=rng.uniform(0, 180))           # broken plates
            for (x, y) in ((9.9, y1 - 0.4), (10.45, y1 - 0.45)):
                with mb.at((x, y, FZ)):
                    mb.cylinder((0, 0, 0), 0.25, 0.55, "M_IntFabricBeige", seg=8)   # flour sacks
            nc.box((8.0, 8.1, FZ + 0.006), (2.2, 1.1, 0.01), "M_Carpet")           # rag rug before the range
            with nc.at((0, y1 - 0.04, 0), rot_x=90.0):
                for k in range(6):
                    nc.cylinder((9.1 + 0.36 * (k % 3), FZ + 1.35 + 0.42 * (k // 3), 0.0), 0.15 - 0.015 * k, 0.03,
                                ("M_OldBrass", "M_TarnishedGold")[k % 2], seg=10)
            with nc.at((6.7, y1 - 0.03, FZ + 1.5)):                        # the cook's chalk board
                nc.box((0, 0, 0), (0.6, 0.02, 0.8), "M_IntChalkboard")
                nc.box((0, -0.005, 0), (0.66, 0.012, 0.86), "M_DarkWood")
            aset.prop("SM_Int_WallClock", (4.6, 5.4, FZ + 2.3), 90.0)
            aset.prop("SM_Int_Cabinet", (9.9, 4.6 + 0.33, FZ), 180.0)
            for zz in (1.55, 2.0):                                          # shelves over the counter
                mb.box((4.74, 7.75, FZ + zz), (0.28, 3.0, 0.03), "M_DarkWood")
                _jars(nc, 4.74, 7.75, 90.0, [FZ + zz + 0.015], 2.9, rng)
            aset.prop("SM_Int_Kettle", (9.7, 4.85, FZ + 1.18), 20.0)
            aset.prop("SM_Int_Jug", (10.2, 4.9, FZ + 1.18), 0.0)
            for _ in range(10):
                rbox(nc, (rng.uniform(5.6, 11.4), rng.uniform(5.0, 9.0), FZ + 0.004), (rng.uniform(0.3, 0.7),
                     rng.uniform(0.2, 0.5), 0.004), rng.choice(("M_Soil", "M_OldPaper", "M_WaterStain")), yaw=rng.uniform(0, 180))
            label, cam = "gf_kitchen", ((11.4, y0 + 0.4, FZ + 1.65), (6.5, y1 - 0.2, FZ + 1.1))
        else:
            for k, x in enumerate((-6.0, -8.3)):                      # copper wash coppers + tubs
                mb.cylinder((x, y1 - 0.55, FZ), 0.45, 0.85, "M_OldBrass", seg=12)
                nc.cylinder((x, y1 - 0.55, FZ + 0.75), 0.4, 0.02, "M_MurkyWater", seg=12)
            mb.box((-10.6, y1 - 0.5, FZ + 0.4), (1.4, 0.7, 0.8), "M_OldStoneTrim")       # stone sink
            nc.box((-10.6, y1 - 0.5, FZ + 0.79), (1.2, 0.5, 0.02), "M_MurkyWater")
            with mb.at((-7.4, 6.3, FZ)):                               # mangle
                for s_ in (-1, 1):
                    mb.box((s_ * 0.35, 0, 0.55), (0.08, 0.5, 1.1), "M_DarkMetal")
                for z_ in (0.8, 0.95):
                    with mb.at((0, 0, z_), rot_y=90.0):
                        mb.cylinder((0, 0, -0.32), 0.07, 0.64, "M_IntWood", seg=8)
                mb.torus((0.45, 0, 1.0), 0.25, 0.02, "M_DarkMetal", seg=12, tube_seg=4)
            with mb.at((-9.8, 6.0, FZ)):                               # ironing table
                mb.box((0, 0, 0.82), (1.6, 0.5, 0.05), "M_IntWood")
                for xx in (-0.6, 0.6):
                    mb.box((xx, 0, 0.4), (0.06, 0.4, 0.8), "M_DarkWood")
            nc.box((-9.6, 6.0, FZ + 0.85), (0.22, 0.12, 0.1), "M_Black")
            nc.box((-10.1, 6.0, FZ + 0.85), (0.7, 0.45, 0.01), "M_DustSheet")
            for k, yl in enumerate((5.4, 7.0, 8.4)):                       # lines of grey sheets still hanging
                nc.box((-8.3, yl, CZ1 - 0.6), (7.0, 0.01, 0.01), "M_Black")
                for j in range(3 + k % 2):
                    xs_ = -5.4 - 1.5 * j - 0.4 * k
                    if xs_ < -11.6:
                        continue
                    ln = rng.uniform(1.3, 2.0)
                    nc.box((xs_, yl, CZ1 - 0.6 - ln / 2), (1.1, 0.02, ln), "M_DustSheet")
            for (x, y) in ((-5.0, 7.8), (-11.6, 8.2), (-7.15, 8.2)):
                aset.prop("SM_Int_Basket", (x, y, FZ), rng.uniform(0, 360))
            aset.prop("SM_Int_Bucket", (-9.4, y1 - 0.4, FZ), 0.0)
            aset.prop("SM_Int_Broom", (-11.65, 5.1, FZ), 90.0)
            label, cam = "gf_laundry", ((-5.0, y0 + 0.4, FZ + 1.65), (-10.4, y1 - 0.8, FZ + 0.9))
        aset.light((cx, cy, FZ + 2.2), WARM, 420.0, 6.0)
        K.camera(aset, label, cam[0], cam[1], 16.0)
        # ---------------- C (back): SCULLERY (east) / BOILER ROOM (west)
        x0, y0, x1, y1 = c_
        cx, cy = _gf_base(aset, mb, nc, rng, c_, [("n", sx * 14.0, Y1 - WT), ("n", sx * 18.0, Y1 - WT),
                                                  ("e" if sx > 0 else "w", ox, 7.6)], 90 + sx, floor="tile")
        if sx > 0:
            for k, x in enumerate((14.0, 18.0)):                           # stone sinks under the windows
                mb.box((x, y1 - 0.35, FZ + 0.4), (1.3, 0.65, 0.8), "M_OldStoneTrim")
                nc.box((x, y1 - 0.35, FZ + 0.79), (1.1, 0.45, 0.02), "M_MurkyWater")
            with mb.at((16.0, y1 - 0.25, FZ)):                             # hand pump
                mb.cylinder((0, 0, 0.8), 0.08, 0.7, "M_DarkMetal", seg=8)
                mb.beam((0, 0, 1.45), (0.0, -0.4, 1.6), 0.04, 0.04, "M_DarkMetal")
            mb.box((x1 - 0.3, 5.6, FZ + 0.9), (0.55, 2.4, 0.04), "M_IntWood")       # draining board on brackets
            for k in range(7):
                nc.cylinder((x1 - 0.3, 4.7 + 0.3 * k, FZ + 0.92), 0.12, 0.02, "M_IntTrimWhite", seg=10)
            aset.prop("SM_Int_Shelves", (13.0, y0 + 0.2, FZ), 180.0)
            _jars(nc, 13.0, y0 + 0.2, 180.0, [FZ + 0.4, FZ + 0.75, FZ + 1.1], 0.45, rng)
            for (y_a, y_b) in ((4.3, 6.3), (7.9, 9.2)):                    # plate racks on the west wall
                _dresser(mb, nc, 12.85, (y_a + y_b) / 2, 90.0, rng, w=y_b - y_a, h=1.9, d=0.4)
            nc.box((16.0, 6.6, CZ1 - 0.5), (3.0, 0.6, 0.04), "M_IntWood")        # drying rack with cloths
            for k in range(6):
                nc.box((14.8 + 0.48 * k, 6.6, CZ1 - 0.85), (0.35, 0.02, 0.6), ("M_DustSheet", "M_IntFabricWhite")[k % 2])
            aset.prop("SM_Int_Cabinet", (16.8, y0 + 0.33, FZ), 180.0)
            for zz in (1.75, 2.15):                                         # shelves over the cupboard
                mb.box((16.8, y0 + 0.14, FZ + zz), (2.4, 0.26, 0.03), "M_DarkWood")
                _jars(nc, 16.8, y0 + 0.14, 180.0, [FZ + zz + 0.015], 2.3, rng)
            for (bx_, by_) in ((13.45, 8.0), (13.5, 8.65), (14.05, 8.3)):        # water barrels
                mb.cylinder((bx_, by_, FZ), 0.28, 0.8, "M_IntWood", seg=10)
                for zz in (0.15, 0.62):
                    nc.cylinder((bx_, by_, FZ + zz), 0.29, 0.04, RUST, seg=10, cap_top=False, cap_bottom=False)
            for k in range(4):                                             # aprons on pegs
                nc.box((x1 - 0.03, 8.4 + 0.25 * k, FZ + 1.75), (0.05, 0.03, 0.03), RUST)
                nc.box((x1 - 0.06, 8.4 + 0.25 * k, FZ + 1.35), (0.02, 0.22, 0.75), ("M_DustSheet", "M_IntFabricBlue")[k % 2])
            for (x, y) in ((15.0, 5.3), (15.5, 5.2), (17.4, 6.0)):
                aset.prop("SM_Int_Bucket", (x, y, FZ), rng.uniform(0, 90))
            with mb.at((16.6, 6.2, FZ)):                                   # wash tub on a stand
                for xx in (-0.4, 0.4):
                    mb.box((xx, 0, 0.3), (0.06, 0.6, 0.6), "M_DarkWood")
                mb.cylinder((0, 0, 0.6), 0.45, 0.3, "M_IntWood", seg=12, cap_top=False)
            for x in (14.0, 18.0):                                         # duckboards in front of the sinks
                for k in range(8):
                    nc.box((x - 0.63 + 0.18 * k, y1 - 1.1, FZ + 0.03), (0.12, 0.8, 0.025), "M_IntWood")
            for _ in range(6):
                rbox(nc, (rng.uniform(13.2, 19.0), rng.uniform(4.3, 7.8), FZ + 0.004), (rng.uniform(0.5, 1.2),
                     rng.uniform(0.4, 0.9), 0.004), rng.choice(("M_WaterStain", "M_Soil")), yaw=rng.uniform(0, 180))
            label, cam = "gf_scullery", ((13.2, y0 + 0.35, FZ + 1.65), (18.4, y1 - 0.5, FZ + 1.1))
        else:
            with mb.at((-16.6, 7.4, FZ)), nc.at((-16.6, 7.4, FZ)):        # the boiler
                with mb.at((0, 0, 0.9), rot_y=90.0):
                    mb.cylinder((0, 0, -1.3), 0.85, 2.6, "M_RustMetal", seg=16)
                mb.box((0, 0, 0.1), (2.8, 1.4, 0.2), "M_OldStoneTrim")
                mb.box((1.45, 0, 0.9), (0.1, 0.8, 0.8), "M_DarkMetal")
                nc.box((1.51, 0, 0.75), (0.02, 0.45, 0.35), "M_IntFire")
                for k in range(3):
                    nc.cylinder((-0.6 + 0.6 * k, -0.86, 1.4), 0.1, 0.03, "M_IntTrimWhite", seg=10)
                mb.cylinder((-0.8, 0.0, 1.7), 0.15, CZ1 - FZ - 1.7, "M_DarkMetal", seg=8)
            for k in range(3):                                             # pipes along the wall to the radiators
                nc.box((-15.6, y1 - 0.12, FZ + 2.2 + 0.18 * k), (5.6, 0.1, 0.1), ("M_RustMetal", "M_DarkMetal", RUST)[k])
            rubble(mb, (-13.4, 5.6), 0.6, 10, rng, mats=("M_Black", "M_DarkMetal"), zc=FZ, size=(0.1, 0.25))
            aset.prop("SM_Int_Bucket", (-14.5, 5.2, FZ), 0.0)
            aset.prop("SM_Int_Toolbox", (-18.9, 4.3, FZ), 30.0)
            aset.prop("SM_Int_Broom", (-13.0, 4.1, FZ), 0.0)
            nc.box((-14.3, 4.3, FZ + 0.6), (0.06, 0.06, 1.2), "M_IntWood")  # shovel
            nc.box((-14.3, 4.3, FZ + 0.08), (0.25, 0.3, 0.02), "M_DarkMetal")
            with mb.at((-18.7, 4.5, FZ)):                                  # coal bunker of boards
                for k in range(4):
                    mb.box((0.0, 0.7, 0.12 + 0.24 * k), (1.3, 0.05, 0.2), "M_DarkWood")
                    mb.box((0.65, 0.0, 0.12 + 0.24 * k), (0.05, 1.4, 0.2), "M_DarkWood")
                mb.box((0, 0, 0.3), (1.25, 1.35, 0.6), "M_Black")
            for x in (-19.2, -12.85):                                      # risers to the floors above
                nc.box((x, 8.8, (FZ + CZ1) / 2), (0.12, 0.12, CZ1 - FZ), "M_RustMetal")
            with nc.at((-12.65, 5.5, FZ + 1.6), rot=-90.0):                # gauge panel
                nc.box((0, -0.03, 0), (0.8, 0.06, 0.6), "M_DarkMetal")
                for k in range(3):
                    nc.box((-0.25 + 0.25 * k, -0.065, 0.05), (0.16, 0.01, 0.16), "M_IntTrimWhite")
            aset.prop("SM_Int_MetalRack", (-15.2, y1 - 0.35, FZ), 0.0)
            aset.prop("SM_Int_ToolCart", (-13.6, 8.6, FZ), 180.0)
            aset.prop("SM_Int_HandTruck", (-18.9, 6.0, FZ), 90.0)
            with nc.at((-12.65, 8.2, FZ + 1.5), rot=-90.0):                # tool board
                nc.box((0, -0.02, 0), (1.2, 0.04, 0.8), "M_IntWood")
                for k in range(6):
                    nc.box((-0.45 + 0.18 * k, -0.06, 0.05 * (k % 2)), (0.04, 0.03, 0.5 - 0.05 * k), ("M_DarkMetal", RUST)[k % 2])
            for k in range(4):                                             # pipes down to the floor
                nc.box((-17.0 + 1.2 * k, y1 - 0.15, (FZ + CZ1) / 2), (0.1, 0.1, CZ1 - FZ), ("M_RustMetal", "M_DarkMetal")[k % 2])
            aset.light((-15.07, 7.4, FZ + 0.8), (1.0, 0.45, 0.15), 500.0, 5.0)
            for _ in range(8):                                             # coal dust tracked across the floor
                rbox(nc, (rng.uniform(-19.0, -13.0), rng.uniform(4.2, 9.0), FZ + 0.004), (rng.uniform(0.5, 1.4),
                     rng.uniform(0.4, 1.0), 0.004), "M_Black", yaw=rng.uniform(0, 180))
            label, cam = "gf_boiler", ((-18.8, 5.6, FZ + 1.65), (-15.5, y1 - 0.6, FZ + 1.0))
        aset.light((cx, cy, FZ + 2.2), WARM, 380.0, 6.0)
        K.camera(aset, label, cam[0], cam[1], 16.0)
        # ---------------- B (middle): the WARDEN'S OFFICE (east) / the NIGHT WATCHMAN'S ROOM (west)
        x0, y0, x1, y1 = b_
        cx, cy = _gf_base(aset, mb, nc, rng, b_, [("e" if sx > 0 else "w", ox, -1.2), ("e" if sx > 0 else "w", ox, 3.2)],
                          100 + sx)
        fr = _Fr(x0, y0, 0.0, x1 - x0, y1 - y0, FZ)
        if sx > 0:
            _old_desk(mb, nc, aset, fr, 3.6, 2.6, 0.0, rng, w=1.5, d=0.75, stuff="papers")
            aset.prop("SM_Int_OfficeChair", (16.2, 0.4, FZ), 180.0 + 15.0)
            aset.prop("SM_Int_Drawers", (18.6, y1 - 0.27, FZ), 0.0)
            with mb.at((x1 - 0.3, -0.6, FZ)):                              # the safe, door ajar
                mb.box((0, 0, 0.45), (0.6, 0.6, 0.9), "M_DarkMetal")
                with mb.at((-0.3, -0.3, 0.0), rot=-50.0):
                    mb.box((0.27, -0.03, 0.45), (0.54, 0.06, 0.84), "M_DarkMetal")
            with mb.at((15.1, y1 - 0.19, FZ)), nc.at((15.1, y1 - 0.19, FZ)):
                _old_bookcase(mb, nc, rng, w=1.0, fill=0.75)
            K.bulletin(nc, aset, 16.55, y1, FZ + 1.2, 0.0, 1.0, 0.8, title="CURFEW 21:00", rng_seed=31)
            with nc.at((17.0, y0 + 0.02, FZ + 1.6), rot=180.0):           # key board
                nc.box((0, 0, 0), (0.7, 0.03, 0.5), "M_DarkWood")
                for k in range(12):
                    if k % 5 == 2:
                        continue
                    nc.box((-0.27 + 0.11 * (k % 6), -0.03, 0.12 - 0.22 * (k // 6)), (0.02, 0.01, 0.07), "M_TarnishedGold")
            _portrait(mb, nc, x1, 0.6, FZ + 2.05, -90.0, 0.8, 1.0, eyes=True)
            K.rug(nc, 14.4, -0.5, 18.2, 2.4, FZ + 0.004, "M_Carpet", "M_TarnishedGold")
            for k, y in enumerate((-0.6, 2.4)):                            # certificates either side of the door
                K.poster(nc, aset, 12.6, y, FZ + 1.7, 90.0, 0.45, 0.6, "M_OldPaper")
            aset.prop("SM_Int_Cabinet", (x1 - 0.33, 1.0, FZ), -90.0)
            for k in range(3):
                DT.trophy(nc, x1 - 0.3, 0.6 + 0.4 * k, FZ + 1.18, 1.0, "M_TarnishedGold")
            for k in range(4):
                rbox(mb, (13.0, 3.2, FZ + 0.17 + 0.33 * k), (0.4, 0.32, 0.32), "M_IntFabricBeige", yaw=8 * k)
            aset.prop("SM_Int_WoodChair", (15.0, 0.3, FZ), 35.0)
            aset.prop("SM_Int_GreenChair", (17.6, -0.8, FZ), 200.0)
            with mb.at((18.9, -1.0, FZ)):                                   # coat stand with the warden's coat
                mb.cylinder((0, 0, 0), 0.2, 0.04, "M_DarkWood", seg=8)
                mb.cylinder((0, 0, 0.04), 0.025, 1.75, "M_DarkWood", seg=6)
                mb.box((0, 0.1, 1.2), (0.45, 0.12, 0.85), "M_Black")
                mb.box((0, 0.0, 1.78), (0.3, 0.3, 0.12), "M_Black")
            _papers(nc, 16.0, 0.6, FZ, 1.3, 7, rng)
            label, cam = "gf_warden", ((13.1, y0 + 0.35, FZ + 1.65), (18.0, y1 - 0.9, FZ + 0.8))
        else:
            aset.prop("SM_Int_OldBed", (-18.9, 1.3, FZ), 0.0)
            nc.box((-18.9, 1.3, FZ + 0.52), (0.8, 1.8, 0.1), "M_OldPaper")
            nc.box((-18.9, 1.0, FZ + 0.6), (0.85, 1.0, 0.06), "M_IntFabricNavy")
            aset.prop("SM_Int_Stove", (-13.0, 3.15, FZ), 0.0)
            aset.prop("SM_Int_Kettle", (-13.0, 3.15, FZ + 0.86), 30.0)
            aset.prop("SM_Int_SmallTable", (-16.0, 3.25, FZ), 180.0)
            aset.prop("SM_Int_Lantern", (-15.7, 3.25, FZ + 0.53), 0.0)
            aset.prop("SM_Int_AlarmClock", (-16.3, 3.25, FZ + 0.53), 160.0)
            DT.paper_stack(nc, -16.05, 3.2, FZ + 0.53, 10.0, 6, 4)
            aset.prop("SM_Int_RockingChair", (-15.6, 2.2, FZ), 160.0)
            DT.coat_hooks(nc, -16.4, y0, FZ + 1.75, 180.0, n=3, dorm="white", jackets=1, seed=7)
            aset.prop("SM_Int_Boots", (-16.4, y0 + 0.3, FZ), 180.0)
            aset.prop("SM_Int_WallClock", (x0, 1.0, FZ + 2.3), 90.0)
            with mb.at((-17.6, y0 + 0.19, FZ), rot=180.0), nc.at((-17.6, y0 + 0.19, FZ), rot=180.0):
                _old_bookcase(mb, nc, rng, w=1.0, h=1.6, shelves=4, fill=0.6)
            K.rug(nc, -17.8, -0.6, -14.2, 2.2, FZ + 0.004, "M_Carpet", "M_TarnishedGold")
            _papers(nc, -15.0, 0.4, FZ, 1.2, 6, rng)
            label, cam = "gf_watchman", ((-13.1, y0 + 0.35, FZ + 1.65), (-18.4, y1 - 0.9, FZ + 0.8))
        aset.light((cx, cy, FZ + 2.2), WARM, 380.0, 6.0)
        K.camera(aset, label, cam[0], cam[1], 16.0)
        # ---------------- A (front): the COMMON ROOM (east) / the OLD DINING ROOM (west)
        x0, y0, x1, y1 = a_
        cx, cy = _gf_base(aset, mb, nc, rng, a_, [("s", sx * 14.1, Y0 + WT), ("s", sx * 17.7, Y0 + WT),
                                                  ("e" if sx > 0 else "w", ox, -5.6)], 110 + sx)
        if sx > 0:
            _cold_fireplace(mb, nc, x1, -3.6, -90.0, rng)
            _portrait(mb, nc, x1, -3.6, FZ + 2.35, -90.0, 0.9, 1.0)
            _sheeted(mb, 16.8, -3.6, FZ, 90.0, 2.0, 0.9, 0.85, kind="sofa")
            _sheeted(mb, 17.8, -5.6, FZ, 20.0, 0.9, 0.85, 0.95)
            with mb.at((15.0, -5.4, FZ)):                                  # billiard table (dust sheet half off)
                mb.box((0, 0, 0.7), (2.6, 1.45, 0.16), "M_DarkWood")
                mb.box((0, 0, 0.785), (2.4, 1.25, 0.01), "M_IntFabricGreen")
                for xx in (-1.15, 1.15):
                    for yy in (-0.6, 0.6):
                        mb.box((xx, yy, 0.31), (0.14, 0.14, 0.62), "M_DarkWood")
                rbox(mb, (0.5, 0.1, 0.8), (1.8, 1.6, 0.02), "M_DustSheet", yaw=8.0)
            for k in range(4):
                nc.sphere((14.3 + 0.12 * k, -5.6 + 0.05 * k, FZ + 0.82), 0.03, ("M_IntTrimWhite", "M_IntFabricRed")[k % 2],
                          seg=6, rings=4)
            nc.box((14.6, -4.9, FZ + 0.8), (1.4, 0.02, 0.02), "M_IntWood")
            aset.prop("SM_Int_Dartboard", (13.0, y1, FZ + 1.6), 0.0)
            aset.prop("SM_Int_CoffeeTableB", (15.2, -2.7, FZ), 0.0)
            DT.card_spread(nc, 15.2, -2.7, FZ + 0.39, 0.0, 5, 21)
            aset.prop("SM_Int_GrandfatherClock", (12.85, -5.0, FZ), 90.0)
            for k, y in enumerate((-6.6, -3.6, -2.4)):
                _portrait(mb, nc, 12.6, y, FZ + 1.95 + 0.1 * (k % 2), 90.0, 0.7, 0.9, eyes=(k == 1), tilt=rng.uniform(-6, 6))
            with mb.at((14.2, -2.1, FZ)):                                  # standard lamp, shade torn
                mb.cylinder((0, 0, 0), 0.18, 0.03, "M_TarnishedGold", seg=8)
                mb.cylinder((0, 0, 0.03), 0.015, 1.5, "M_TarnishedGold", seg=6)
                mb.cylinder((0, 0, 1.45), 0.25, 0.3, "M_DustSheet", seg=10, radius_top=0.15, cap_top=False, cap_bottom=False)
            aset.prop("SM_Int_Radio", (13.0, -6.9, FZ), 45.0)
            with mb.at((18.6, y1 - 0.19, FZ)), nc.at((18.6, y1 - 0.19, FZ)):
                _old_bookcase(mb, nc, rng, w=1.0, fill=0.6)
            label, cam = "gf_common", ((13.0, y1 - 0.4, FZ + 1.65), (18.4, -6.4, FZ + 0.8))
        else:
            for k, y in enumerate((-5.9, -3.1)):                           # two long tables, chairs pushed back
                aset.prop("SM_Int_DiningTable", (-16.0, y, FZ), 0.0)
                for j, dx in enumerate((-0.75, 0.0, 0.75)):
                    for s_ in (-1, 1):
                        if (j + k + (s_ > 0)) % 4 == 1:
                            continue
                        aset.prop("SM_Int_DiningChair", (-16.0 + dx, y + s_ * 0.95, FZ),
                                  (180.0 if s_ < 0 else 0.0) + rng.uniform(-15, 15))
                DT.table_set(nc, aset, -16.0, y, FZ + 0.88, 0.0, kind="dining", seats=4, seed=40 + k, length=1.6)
            _toppled_chair(mb, (-13.8, -4.5, FZ), 140.0, rng)
            aset.prop("SM_Int_Cabinet", (-19.4 + 0.33, -4.5, FZ), 90.0)
            aset.prop("SM_Int_Candelabra", (-19.4 + 0.33, -4.5, FZ + 1.18), 90.0)
            _candles(nc, -19.05, -4.1, FZ + 1.18, rng, 2)
            for k, x in enumerate((-17.8, -15.6)):
                _portrait(mb, nc, x, y1, FZ + 2.0, 0.0, 0.8, 1.0, eyes=(k == 0))
            _hanging_chandelier(mb, -16.0, -4.5, CZ1, tilt=6.0)
            label, cam = "gf_dining", ((-13.0, y1 - 0.4, FZ + 1.65), (-18.6, -6.6, FZ + 0.8))
        aset.light((cx, cy, FZ + 2.2), WARM, 420.0, 6.5)
        K.camera(aset, label, cam[0], cam[1], 16.0)

def _interiors(aset, mb, nc):
    rng = random.Random(4242)   # separate stream: the exterior keeps its own random sequence
    _library(aset, mb, nc, rng)
    _salon(aset, mb, nc, rng)
    _ritual_room(aset, mb, nc, rng)
    _dorm_room(aset, mb, nc, rng)
    _upper_floor(aset, mb, nc, rng)
    _tower_rooms(aset, mb, nc, rng)
    _ground_rooms(aset, mb, nc, random.Random(99))


def _ivy(nc, rng):
    def patch(origin, yaw, u0, u1, z0, z1, density=2.6):
        with nc.at(origin, rot=yaw):
            n = int((u1 - u0) * (z1 - z0) * density)
            for _ in range(n):
                u = rng.uniform(u0, u1)
                t = (u - u0) / (u1 - u0)
                lim = z0 + (z1 - z0) * (0.35 + 0.65 * math.sin(t * math.pi) ** 0.7) * rng.uniform(0.75, 1.0)
                z = z0 + (lim - z0) * rng.random() ** 0.85
                leaf_card(nc, (u, -rng.uniform(0.06, 0.3), z), rng.uniform(0.45, 0.8), "M_Ivy", rng)

    patch((X0, Y0), 0, -0.3, 6.5, FL, 11.6, density=3.0)
    patch((X0, Y0), 0, 10.5, 14.5, FL, 5.5)
    patch((TX, Y0), 0, 7.5, 12.5, FL, 8.5)
    patch((-TX, TY0), 0, 7.6, 9.4, FL, 18.0, density=3.4)
    patch((-TX, TY0), 0, -0.2, 1.0, FL, 4.0, density=3.0)
    patch((X1, Y0), 90, 0.0, 4.5, FL, 6.0)
    patch((X1, Y0), 90, 9.0, 17.0, FL, 11.6, density=3.0)
    patch((X0, Y1), -90, 3.0, 9.0, FL, 8.5)
    patch((X1, Y1), 180, 12.0, 23.0, FL, 11.4, density=3.0)
    patch((X1, Y1), 180, 30.0, 35.0, FL, 5.5)
    for sx in (-1, 1):   # gate pillars
        patch((sx * 3.0 - 0.43, -38.43), 0, 0.0, 0.86, 0.0, 2.2 + 0.6 * sx, density=4.0)


def _grounds(mb, nc, rng):
    fy = -38.0
    # stone gate pillars (one ball finial fallen)
    for sx in (-1, 1):
        x = sx * 3.0
        mb.box((x, fy, 1.25), (0.85, 0.85, 3.5), STONE)
        mb.box((x, fy, 0.1), (1.05, 1.05, 0.4), TRIM)
        mb.box((x, fy, 3.1), (1.05, 1.05, 0.2), TRIM)
        mb.pyramid((x, fy, 3.2), 0.9, 0.9, 0.35, TRIM)
        if sx < 0:
            mb.sphere((x, fy, 3.75), 0.28, TRIM, seg=10, rings=6)
        else:
            mb.sphere((x + 1.1, fy - 0.9, 0.24), 0.28, TRIM, seg=10, rings=6)
            rbox(mb, (x + 0.7, fy - 0.5, 0.08), (0.3, 0.2, 0.15), TRIM, yaw=30)

    def gate_wing(width, height):
        mb.box((width / 2, 0, 0.15), (width, 0.06, 0.08), RUST)
        mb.box((width / 2, 0, height - 0.1), (width, 0.06, 0.08), RUST)
        mb.box((width / 2, 0, height * 0.55), (width, 0.05, 0.06), RUST)
        mb.box((0.03, 0, height / 2), (0.08, 0.08, height), RUST)
        mb.box((width - 0.03, 0, height / 2), (0.08, 0.08, height), RUST)
        k = 0
        x = 0.18
        while x < width - 0.1:
            hh = height + 0.25 * math.sin(math.pi * x / width)
            mb.box((x, 0, hh / 2), (0.035, 0.035, hh), RUST)
            mb.cone((x, 0, hh), 0.05, 0.16, RUST, seg=4)
            x += 0.16
            k += 1
        # scroll ring
        with mb.at((width / 2, 0, height * 0.78), rot_x=90):
            mb.torus((0, 0, 0), 0.32, 0.03, RUST, seg=12, tube_seg=4)

    with mb.at((-2.55, fy, 0.02), rot=58, rot_y=-2.5):
        gate_wing(2.5, 2.3)
    with mb.at((0.4, fy + 1.4, 0.14), rot=-18, rot_x=-86):   # fallen wing lying on the ground
        gate_wing(2.5, 2.3)
    rbox(mb, (1.6, fy + 1.0, 0.1), (0.4, 0.3, 0.2), STONE, yaw=20)

    # KEEP OUT board next to the gate
    bx, by, byaw = 5.6, fy - 1.6, -12.0
    with mb.at((bx, by, 0), rot=byaw):
        for s in (-1, 1):
            mb.box((s * 1.0, 0.04, 0.9), (0.12, 0.12, 1.8 + 0.2 * s), ROT)
        mb.box((0, 0, 1.45), (2.3, 0.06, 0.32), BOARD)
        mb.box((0.05, 0, 1.12), (2.25, 0.06, 0.3), BOARD)
        mb.box((-0.15, 0, 0.8), (1.9, 0.06, 0.28), BOARD)
        rbox(mb, (0.9, -0.05, 0.62), (0.9, 0.05, 0.24), BOARD, pitch=-25)

    # cracked flagstone walkway gate -> porch steps
    y = fy + 0.5
    row = 0
    while y < -16.0:
        d = rng.uniform(0.55, 0.8)
        x = -1.7 + (0.35 if row % 2 else 0.0)
        while x < 1.6:
            w = min(rng.uniform(0.7, 1.1), 1.75 - x)
            if w > 0.25 and rng.random() > 0.12:
                rbox(mb, (x + w / 2, y + d / 2, -0.06 + rng.uniform(0.0, 0.03)), (w - 0.06, d - 0.06, 0.18), TRIM,
                     yaw=rng.uniform(-4, 4), pitch=rng.uniform(-2, 2), roll=rng.uniform(-2, 2))
            x += w
        y += d
        row += 1

    # debris around the building
    for (c, r, n) in (((-14.0, -10.5), 2.5, 7), ((12.0, -10.2), 2.0, 6), ((21.8, 3.0), 2.0, 6),
                      ((-6.0, 12.5), 2.5, 7), ((-22.5, -2.0), 1.8, 5)):
        rubble(mb, c, r, n, rng)
    for (c, r, n) in (((-9.0, -11.5), 2.0, 4), ((8.5, -12.5), 2.2, 4), ((16.0, 12.0), 2.5, 5),
                      ((-21.5, 6.0), 1.5, 3), ((-6.5, -21.0), 2.0, 3)):
        planks(mb, c, r, n, rng)
    for k in range(18):   # fallen slates under the roof holes
        x = rng.uniform(-17, 15)
        yy = rng.choice((rng.uniform(-10.5, -9.0), rng.uniform(10.8, 12.5)))
        rbox(mb, (x, yy, 0.03), (0.5, 0.32, 0.04), "M_OldRoof", yaw=rng.uniform(0, 180), pitch=rng.uniform(-6, 6))
    # a fallen shutter and a toppled urn
    rbox(mb, (-17.0, -9.6, 0.08), (0.7, 2.1, 0.05), ROT, yaw=70, pitch=4)
    with mb.at((-7.5, -18.0, 0.0)):
        mb.box((0, 0, 0.25), (1.0, 1.0, 0.5), TRIM)
        mb.lathe([(0.25, 0.5), (0.45, 0.8), (0.5, 1.1), (0.35, 1.3)], TRIM, seg=10)
    with mb.at((7.5, -18.0, 0.0)):
        mb.box((0, 0, 0.25), (1.0, 1.0, 0.5), TRIM)
    with mb.at((8.3, -18.9, 0.42), rot=-30, rot_x=90):
        mb.lathe([(0.25, -0.4), (0.45, -0.1), (0.5, 0.2), (0.35, 0.4)], TRIM, seg=10)


def _sockets(aset, rng):
    fy = -38.0
    purple = (0.6, 0.4, 1.0)
    # iron fence along the pad edge (rectangle, gaps + skewed panels + a missing stretch)
    fx, fb = 40.0, 34.0
    segs = []
    for side in (-1, 1):
        x = side * 3.4
        while abs(x) < fx - 1.9:
            segs.append(((x + side * 2.0, fy), 0.0))
            x += side * 4.0
        y = fy + 2.0
        while y < fb - 1.0:
            segs.append(((side * fx, y), 90.0))
            y += 4.0
    x = -fx + 2.0
    while x < fx - 1.0:
        segs.append(((x, fb), 180.0))
        x += 4.0
    for (p, yaw) in segs:
        r = rng.random()
        if r < 0.1 or (p[0] > 30 and p[1] > 10 and p[1] < 26 and abs(yaw - 90) < 1):
            continue
        if r < 0.3:
            yaw += rng.uniform(-9, 9)
        aset.prop("SM_Fence_Iron", (p[0], p[1], 0.0), yaw)
    # dead trees, old lamps
    for (x, y) in ((-28, -24), (25, -28), (-33, 16), (31, 21), (-14, 27), (16, -31), (-24, -6), (29, -6),
                   (8, 25), (-36, -33)):
        aset.prop("SM_DeadTree_A", (x + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5), 0), rng.uniform(0, 360),
                  round(rng.uniform(0.8, 1.3), 2))
    for (x, y, yaw) in ((-3.2, -31.0, 10), (3.2, -26.0, 170), (-3.2, -20.0, -5), (7.0, -15.5, 200)):
        aset.prop("SM_LampPost_Old", (x, y, 0), yaw)
    # overgrowth: weeds along the walls, ferns and bushes in the yard
    def free(x, y):
        return not (abs(x) < 2.4 and y < -14.0) and not (X0 - 0.5 < x < X1 + 0.5 and Y0 - 0.5 < y < Y1 + 0.5) \
            and not (-6.5 < x < 6.5 and -16.2 < y < -10.5)
    n = 0
    while n < 70:
        side = rng.random()
        if side < 0.6:   # hugging the plinth
            t = rng.random()
            per = 2 * (X1 - X0) + 2 * (Y1 - Y0)
            d = t * per
            if d < X1 - X0:
                x, y = X0 + d, Y0 - 0.9
            elif d < 2 * (X1 - X0):
                x, y = X0 + d - (X1 - X0), Y1 + 0.9
            elif d < 2 * (X1 - X0) + (Y1 - Y0):
                x, y = X0 - 0.9, Y0 + d - 2 * (X1 - X0)
            else:
                x, y = X1 + 0.9, Y0 + d - 2 * (X1 - X0) - (Y1 - Y0)
            x += rng.uniform(-0.4, 0.4)
            y += rng.uniform(-0.4, 0.4)
        else:
            x, y = rng.uniform(-37, 37), rng.uniform(-35, 31)
        if not free(x, y):
            continue
        r = rng.random()
        asset = "SM_GrassClump_A" if r < 0.55 else ("SM_Fern_A" if r < 0.85 else "SM_Bush_B")
        yaw_, sc = rng.uniform(0, 360), round(rng.uniform(0.9, 1.6), 2)
        n += 1
        if (abs(x) < TX + 0.4 and TY0 - 0.4 < y < Y0) or (abs(x) < 2.2 and Y1 < y < Y1 + 2.6):
            continue          # (would grow inside the entrance hall / on the back steps)
        reach = {"SM_GrassClump_A": 0.8, "SM_Fern_A": 1.0, "SM_Bush_B": 0.9}[asset] * sc
        m = 0.4 + reach
        if X0 - m < x < X1 + m and Y0 - m < y < Y1 + m:   # keep the foliage clear of the plinth and the eaves
            if y < Y0:
                y = min(y, Y0 - 0.4 - reach)
            elif y > Y1:
                y = max(y, Y1 + 0.4 + reach)
            elif x < X0:
                x = min(x, X0 - 0.4 - reach)
            else:
                x = max(x, X1 + 0.4 + reach)
        if abs(x) < TX + m and TY0 - m < y < Y0 + 0.5:
            continue          # (against the tower: the porch side is dressed by hand)
        aset.prop(asset, (x, y, 0), yaw_, sc)
    for k in range(14):   # weeds poking between the flagstones
        aset.prop("SM_GrassClump_A", (rng.uniform(-1.9, 1.9), rng.uniform(-37, -16.5), 0), rng.uniform(0, 360),
                  round(rng.uniform(0.6, 1.0), 2))
    # texts
    by, byaw = fy - 1.6, -12.0
    nx, ny = math.sin(math.radians(byaw)), -math.cos(math.radians(byaw))
    aset.text("KEEP OUT", (5.6 + nx * 0.06, by + ny * 0.06, 1.2), byaw, size=0.42, color=(0.78, 0.08, 0.05))
    aset.text("SPECIAL DORM", (0.0, TY0 - 0.34 - 0.025, FL + 3.4), 0.0, size=0.26, color=(0.32, 0.30, 0.33))
    # lights: dim purple inside, a flickery lantern by the door
    aset.light((0.0, -6.5, HZ1 - 0.8), purple, 1300.0, 14.0)
    aset.light((0.0, 1.0, 3.0), purple, 900.0, 9.0)
    aset.light((-2.6, 3.0, GAL_Z + 1.5), purple, 800.0, 7.0)
    aset.light((1.95, TY0 - 0.35, FL + 2.9), (0.72, 0.5, 1.0), 1100.0, 9.0)
    # atmosphere
    for (x, y) in ((-13.0, -22.0), (15.0, -19.0), (-2.0, 20.0)):
        aset.emitter("mist", (x, y, 0.5), 2.0)
    aset.emitter("mist", (0.0, -5.0, FL + 0.3), 1.0, rate=0.5)
    aset.audio("A_Wind", (0.0, -5.0, 6.0), radius=70.0)
    aset.interact("sign", (5.6, by - 0.8, 1.0), byaw, title="Abandoned Dorm",
                  text="The old Special Dorm. Students who stayed here vanished without a trace... Turn back.")
    K.camera(aset, "hall", (2.3, -10.0, FL + 1.5), (-0.6, 2.5, FL + 2.6), 18.0)
    # the front doors: rotten double door that creaks open inwards
    aset.door((0.0, TY0 + 0.3, FL), 0.0, 2.4, 3.2, "abandoned", double=True, swing="in")


def build():
    rng = random.Random(1331)
    aset = AssetSet("abandoned")
    dorm = aset.mesh("Abandoned_Dorm")
    roof = aset.mesh("Abandoned_Roof")
    hall = aset.mesh("Abandoned_Hall")
    grounds = aset.mesh("Abandoned_Grounds")
    nc = aset.mesh("Abandoned_NoCol")
    inner = aset.mesh("Abandoned_Interior")
    inner_nc = aset.mesh("Abandoned_Interior_NoCol")
    _shell(aset, dorm)
    _facades(dorm, nc, rng)
    _roof(roof, rng)
    _tower(dorm, roof, nc, rng)
    _porch(dorm, nc, rng)
    _hall(hall, nc, rng)
    _interiors(aset, inner, inner_nc)
    _ivy(nc, rng)
    _grounds(grounds, nc, rng)
    _sockets(aset, rng)
    return aset


PLACEMENTS = {"abandoned": with_travel(build, [
    ("hall", "abandoned_hall", "Abandoned Dorm Hall", "Dust, cobwebs and portraits that seem to follow you."),
    ("ritual", "abandoned_ritual", "Ritual Chamber", "The forbidden room below the dorm. The circle on the floor is still warm."),
])}
