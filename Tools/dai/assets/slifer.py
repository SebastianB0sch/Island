"""
Slifer Red Dorm - the humble two-storey wooden apartment block on the west cliff.

Local space (metres): origin = centre of the pad at finished ground level, front (-Y) faces the
sea / cliff edge (cliff around y = -32), the academy path arrives behind the block at (0, +32).

Layout (x along the coast):
    x -19.9 .. -18   exterior staircase + landing (west end)
    x -18   ..   8   main block, 6 rooms per floor, upper walkway along the front (y -4.8 .. -3)
    x   8   ..  11   passage between the buildings (vending machine)
    x  11   ..  20   dining hall annex with a covered deck/porch (y -6.4 .. -3)
    y  -22           wooden fence along the cliff side (gap at x = 0)

Interiors: every front door opens into a dorm room (101-106 downstairs, 201-206 off the walkway): genkan
with a shoe shelf, a tiny WC, tatami, the famous Slifer triple bunk bed, a kotatsu, a desk under the window,
TV, posters. 101 is Jaden, Syrus and Chumley's room, 206 Professor Banner's study (with Pharaoh's basket).
The dining hall gets doors for its entrance and kitchen.

Meshes: Slifer_Main, Slifer_Dining, Slifer_Yard, Slifer_NoCol, Slifer_Interior, Slifer_Interior_NoCol.
"""

import math

import random

from . import AssetSet
from . import with_travel
from . import detail as DT
from . import interior as K
from .. import palette

palette.register({
    "M_SliferLaundryWhite": dict(kind="opaque", color=(0.95, 0.94, 0.90), rough=0.95, detail="Fabric", tiling=2.0),
    "M_SliferLaundryBlue": dict(kind="opaque", color=(0.28, 0.45, 0.78), rough=0.95, detail="Fabric", tiling=2.0),
    "M_SliferCurry": dict(kind="opaque", color=(0.78, 0.50, 0.14), rough=0.5, detail=None),
})

WALL, ROOF, TRIM, DOOR = "M_SliferWall", "M_SliferRoof", "M_SliferTrim", "M_SliferDoor"
GLASS, CONC = "M_Glass", "M_Concrete"

# ------------------------------------------------------------------ main block dimensions
X0, X1 = -18.0, 8.0          # main block along the coast
YF, YB = -3.0, 5.0           # front (sea) / back wall faces
ZG = 0.25                    # ground floor level (top of plinth)
Z2 = 3.0                     # upper walkway / upper floor level
ZW = 5.95                    # wall top at front and back walls
YR = 1.0                     # ridge line
PITCH = 0.27                 # shallow corrugated roof
ZR = ZW + (YR - YF) * PITCH + 0.05
YWK = -4.8                   # outer edge of the upper walkway
ROOF_X0, ROOF_X1 = -19.95, 8.55
ROOF_YF, ROOF_YB = -5.4, 5.6
NROOMS = 6
RW = (X1 - X0) / NROOMS

# dining hall annex
DX0, DX1, DY0, DY1 = 11.0, 20.0, -3.0, 5.0
DZ = 0.45                    # dining floor / deck level
DWH = 3.2                    # wall height
DECK_Y = -6.4

FOUND = -4.0                 # foundations reach down to here


def roof_z(y):
    return ZR - abs(y - YR) * PITCH


# ------------------------------------------------------------------ small helpers
def slab(mb, pts, thick, mat, bottom_mat=None, side_mat=None):
    """Thick slab from a top polygon given CCW seen from above (any slope)."""
    top = [tuple(map(float, p)) for p in pts]
    bot = [(p[0], p[1], p[2] - thick) for p in top]
    mb.poly(top, mat)
    mb.poly(list(reversed(bot)), bottom_mat or mat)
    n = len(top)
    for i in range(n):
        a, b = top[i], top[(i + 1) % n]
        al, bl = bot[i], bot[(i + 1) % n]
        mb.poly([al, bl, b, a], side_mat or mat)


def railing(mb, p0, p1, h, mat, baluster=0.22, post_every=1.6, skip=(), post_mat=None):
    """Railing between two 3D points on the walking surface: posts, top + bottom rail, balusters."""
    x0, y0, z0 = p0
    x1, y1, z1 = p1
    length = math.dist((x0, y0), (x1, y1))
    if length < 1e-3:
        return
    pm = post_mat or mat

    def at(t):
        return (x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, z0 + (z1 - z0) * t)

    npost = max(1, int(round(length / post_every)))
    for k in range(npost + 1):
        x, y, z = at(k / npost)
        mb.box((x, y, z + (h + 0.06) / 2), (0.11, 0.11, h + 0.06), pm)
    mb.beam((x0, y0, z0 + h), (x1, y1, z1 + h), 0.12, 0.07, mat)
    mb.beam((x0, y0, z0 + 0.14), (x1, y1, z1 + 0.14), 0.06, 0.06, mat)
    nb = max(1, int(length / baluster))
    for k in range(1, nb):
        if k in skip:
            continue
        x, y, z = at(k / nb)
        mb.box((x, y, z + 0.14 + (h - 0.14) / 2), (0.04, 0.04, h - 0.17), mat, skip=("+z", "-z"))


def door(mb, u, z, w=0.9, h=2.0, panel=DOOR, frame=TRIM, knob_side=1):
    """Door on a wall face at local y=0 (outside = -y), u along local x."""
    mb.box((u, -0.03, z + h / 2), (w, 0.06, h), panel, skip=("+y",))
    mb.box((u - w / 2 - 0.05, -0.05, z + h / 2 + 0.05), (0.1, 0.1, h + 0.1), frame, skip=("+y",))
    mb.box((u + w / 2 + 0.05, -0.05, z + h / 2 + 0.05), (0.1, 0.1, h + 0.1), frame, skip=("+y",))
    mb.box((u, -0.05, z + h + 0.05), (w + 0.2, 0.1, 0.1), frame, skip=("+y",))
    mb.box((u + knob_side * (w / 2 - 0.12), -0.09, z + 1.0), (0.06, 0.06, 0.06), "M_Metal")
    mb.box((u, -0.065, z + 0.85), (0.3, 0.01, 0.05), "M_DarkMetal")   # mail slot


def window(mb, u, z, w, h, frame=TRIM, glass=GLASS, mullion=True, sill=True):
    """Framed window on a wall face at local y=0 (outside = -y). glass=None: frame only (the wall has a real
    opening with its own glass)."""
    if glass:
        mb.box((u, -0.02, z + h / 2), (w, 0.04, h), glass, skip=("+y",))
    fw = 0.09
    mb.box((u - w / 2 - fw / 2, -0.05, z + h / 2), (fw, 0.1, h + 2 * fw), frame, skip=("+y",))
    mb.box((u + w / 2 + fw / 2, -0.05, z + h / 2), (fw, 0.1, h + 2 * fw), frame, skip=("+y",))
    mb.box((u, -0.05, z + h + fw / 2), (w, 0.1, fw), frame, skip=("+y",))
    mb.box((u, -0.05, z - fw / 2), (w, 0.1, fw), frame, skip=("+y",))
    if mullion:
        mb.box((u, -0.05, z + h / 2), (0.05, 0.08, h), frame, skip=("+y",))
    if sill:
        mb.box((u, -0.1, z - fw - 0.03), (w + 0.3, 0.2, 0.06), frame, skip=("+y",))



# ------------------------------------------------------------------ hollow storeys + dorm rooms
SLAB = 0.2                     # upper floor slab (its underside is the ground-floor ceiling)
WT = 0.2                       # outer wall thickness
STEP = 0.08                    # genkan step up to the room floor
IN_WALL = K.PLASTER_CREAM


def _x0(i):
    return X0 + i * RW


def _shell(aset, mb):
    """Outer walls of both storeys with real door / window openings, the upper floor slab and the top
    ceiling. Exterior trims, frames, lamps and plates stay in _main_block."""
    for (zb, zt) in ((ZG, Z2), (Z2, ZW)):
        up = zb > ZG
        s_ops, n_ops = [], []
        for i in range(NROOMS):
            x0 = _x0(i)
            # (apartment doors open outwards, onto the stoop / walkway: the genkan is only 0.95 m deep)
            s_ops.append(K.Door(x0 + 1.05, 0.9, 2.05, "slifer", trim=None, trim_in=K.TRIM_WOOD, swing="out"))
            s_ops.append(K.Window(x0 + 2.95, 1.4, 0.95, 1.95, frame=TRIM, mullions=1))
            n_ops.append(K.Window(x0 + 2.4, 1.0, 1.0 if up else 0.9, (1.0 if up else 0.9) + 0.75, frame=TRIM))
            n_ops.append(K.Window(x0 + 0.9, 0.5, 1.35 if up else 1.5, (1.35 if up else 1.5) + 0.4, frame=TRIM,
                                  mullions=0))
        rel = 1.0 if up else 1.1
        sides = {"s": s_ops, "n": n_ops,
                 # (east end window at the back of rooms 106 / 206, behind the bunk / bed: at the front it was
                 # covered by the Slifer tapestry, the colour-box tower and Banner's pictures)
                 "e": [K.Window(3.8, 1.0, rel, rel + 0.9, frame=TRIM)],
                 "w": [K.Window(-1.6, 1.0, rel, rel + 0.9, frame=TRIM)]}
        K.shell(aset, mb, X0, YF, X1, YB, zb, zt - zb, WT, WALL, inner=IN_WALL, sides=sides, base=K.TRIM_WOOD)
        # party walls between the rooms
        for i in range(1, NROOMS):
            x = _x0(i)
            # (up to the underside of the slab / top ceiling - not through it into the floor above)
            ztop = (Z2 - SLAB) if not up else ZW - 0.1
            K.wall(aset, mb, (x + 0.06, YF + WT), (x + 0.06, YB - WT), zb, ztop - zb, 0.12, IN_WALL, inner=IN_WALL)
    K.slab(mb, X0 + WT, YF + WT, X1 - WT, YB - WT, Z2, SLAB, top=K.WOODFLOOR, bottom=K.CEIL, side=IN_WALL)
    K.slab(mb, X0, YF, X1, YB, ZW, 0.1, top=WALL, bottom=K.CEIL)


def _rooms(aset, mb, nc):
    rng = random.Random(7)
    blankets_all = [("M_IntFabricRed", "M_IntFabricYellow", "M_IntFabricBlue"),
                    ("M_IntFabricBlue", "M_IntFabricWhite", "M_IntFabricRed"),
                    ("M_IntFabricGreen", "M_IntFabricRed", "M_IntFabricOrange"),
                    ("M_IntFabricPurple", "M_IntFabricBlue", "M_IntFabricYellow")]
    posters = ["DUEL!", "NEVER GIVE UP", "SLIFER RED", "DECK MASTER", "GET YOUR GAME ON!", "CARD OF THE WEEK"]
    for floor, zf in ((1, ZG), (2, Z2)):
        ceil = (Z2 - SLAB) if floor == 1 else ZW - 0.1
        for i in range(NROOMS):
            num = f"{floor}0{i + 1}"
            x0 = _x0(i)
            rx0 = (X0 + WT) if i == 0 else x0 + 0.06
            rx1 = (X1 - WT) if i == NROOMS - 1 else x0 + RW - 0.06
            ry0, ry1 = YF + WT, YB - WT
            zr = zf + STEP
            gx1 = x0 + 1.9                      # genkan (entry) right edge
            gy1 = ry0 + 0.95                    # genkan depth
            # ---- floors: concrete genkan, raised wooden floor with tatami, tiled WC
            mb.box_mm((rx0, ry0, zf), (gx1, gy1, zf + 0.01), "M_IntConcrete", skip=("-z",))
            # (the faces against the walls and the slab are never seen: left out, they cannot z-fight the skirting)
            mb.box_mm((rx0, gy1, zf), (rx1, ry1, zr), K.WOODFLOOR, mats={"-y": K.TRIM_WOOD}, skip=("+y", "-x", "+x", "-z"))
            mb.box_mm((gx1, ry0, zf), (rx1, gy1, zr), K.WOODFLOOR, mats={"-x": K.TRIM_WOOD}, skip=("-y", "+x", "-z"))
            mb.box_mm((rx0, gy1 - 0.02, zr - 0.04), (gx1, gy1 + 0.1, zr + 0.005), K.TRIM_WOOD)   # step nosing
            K.tatami(mb, rx0, gy1 + 0.1, rx1, 2.95, zr + 0.03)
            # ---- WC in the back-left corner (vent window above the toilet)
            wx1 = x0 + 1.7
            # WC door 0.85 m (a person fits through), set towards the WC's inner wall so its leaf swings clear
            # of the wardrobe beside it
            # (its right jamb 2 cm clear of the WC's side wall, which stands on x wx1-0.1 .. wx1); it opens into
            # the WC: a leaf swinging into the room would sweep the wardrobe corner and the walkway
            K.wall(aset, mb, (rx0, 2.95), (wx1, 2.95), zr, ceil - zr, 0.1, IN_WALL, inner=K.PLASTER_SKY,
                   openings=[K.Door(wx1 - rx0 - 0.425 - 0.12, 0.85, 2.0, "slifer_inner", trim=K.TRIM_WOOD,
                                    swing="in")])
            K.wall(aset, mb, (wx1, 2.95), (wx1, ry1), zr, ceil - zr, 0.1, IN_WALL, inner=K.PLASTER_SKY)
            with mb.at((0, 0, zr)):
                K.toilet_room(mb, rx0, 3.05, wx1 - 0.1, ry1)
            nc.box((x0 + 0.9, 3.9, ceil - 0.02), (0.3, 0.3, 0.02), K.PANEL_LIGHT)
            # ---- room contents
            jaden = num == "101"
            banner = num == "206"
            with mb.at((0, 0, zr)), nc.at((0, 0, zr)):
                if banner:
                    K.single_bed(mb, nc, rx1 - 0.55, 1.8, -90.0, blanket="M_IntFabricGreen", length=2.0, width=0.95)
                    K.bookcase(mb, nc, rx0 + 0.18, 0.9, 90.0, w=1.2, h=min(2.0, ceil - zr - 0.1), rng_seed=i)
                else:
                    K.bunk_bed(mb, nc, rx1 - 0.52, 1.75, -90.0, levels=3,
                               blankets=blankets_all[0] if jaden else rng.choice(blankets_all[1:]), gap=0.6,
                               length=2.0, width=0.92)
                    K.kotatsu(mb, nc, x0 + 1.95, 0.85, 0.0, quilt=rng.choice(("M_IntFabricOrange", "M_IntFabricRed",
                                                                                "M_IntFabricBlue")))
                K.desk(mb, nc, x0 + 2.95, ry0 + 0.32, 180.0, w=1.1, d=0.55, hutch=False, rng_seed=i + floor * 10)
                K.wardrobe(mb, rx0 + 0.31, 2.1, 90.0, w=1.2, d=0.6, h=min(2.0, ceil - zr - 0.15))
                # shoe shelf in the genkan (rests on the concrete, 7 cm below the raised floor)
                mb.box_mm((rx0, ry0 + 0.05, -STEP + 0.01), (rx0 + 0.32, ry0 + 0.85, 0.85 - STEP + 0.01), K.WOOD)
                for k in range(3):
                    nc.box((rx0 + 0.2, ry0 + 0.25 + k * 0.22, 0.815), (0.24, 0.1, 0.07), rng.choice(K.FABRICS))
            # genkan shoes on the concrete (below the step)
            for k in range(2):
                nc.box((x0 + 0.85 + k * 0.35, ry0 + 0.55, zf + 0.05), (0.12, 0.28, 0.08), rng.choice(("M_IntFabricRed", "M_IntBlack")))
            # props
            aset.prop("SM_Int_WoodChair", (x0 + 2.95, ry0 + 0.95, zr), 0.0)
            if banner:
                # reading corner against the right wall in front of the bed (armchair facing the room); in the
                # middle of the room it closed the way to the back but for a 0.77 m gap at the book case
                aset.prop("SM_Int_Armchair", (x0 + 3.6, -0.45, zr + 0.03), -90.0)
                aset.prop("SM_Int_SideTable", (x0 + 3.8, 0.3, zr + 0.03), 0.0)
                aset.prop("SM_Int_TeaSet", (x0 + 3.8, 0.3, zr + 0.59), 30.0)
                aset.prop("SM_Int_Basket", (x0 + 3.0, 0.55, zr + 0.03), 15.0)       # Pharaoh's basket
                K.nameplate(mb, aset, x0 + 1.05 + 0.75, YF - 0.005, zf + 1.6, 0.0, "Prof. Banner", w=0.55, h=0.11)
            else:
                # TV on a low cabinet against the left wall, facing the kotatsu
                mb.box_mm((rx0, 0.35, zr), (rx0 + 0.42, 1.35, zr + 0.42), K.WOOD_DARK)
                aset.prop("SM_Int_TV", (rx0 + 0.22, 0.85, zr + 0.42), 90.0)
                if rng.random() < 0.6:
                    aset.prop("SM_Int_Box", (rx1 - 0.3, -1.35, zr + 0.03), rng.uniform(-20, 20))
            # (rooms 101 / 201 have the west window at y -2.1 .. -1.1: clock and mirror over the tansu instead)
            aset.prop("SM_Int_WallClock", (rx0 + 0.02, 0.1 if i == 0 else -0.6, zr + 1.75), 90.0) if i % 2 == 0 else None
            # posters on the party wall above the bunk / bookcase side
            # (party wall beside the Slifer tapestry - not under it; Banner's on the front wall, clear of his
            # book cases)
            ppos = (rx1 - 0.01, -1.85, -90.0, 0.55, 0.75) if not banner else (x0 + 1.835, ry0 + 0.01, 180.0, 0.42, 0.6)
            K.poster(nc, aset, ppos[0], ppos[1], zr + 1.55, ppos[2], ppos[3], ppos[4], K.POSTERS[(i + floor) % 4],
                     text=(posters[(i + 2 * floor) % len(posters)] if not jaden else "GET YOUR GAME ON!"),
                     text_size=0.07)
            if jaden:
                # (above the shelf over the TV, under the nageshi rail - not on the window)
                K.poster(nc, aset, rx0 + 0.01, 0.85, zr + 1.78, 90.0, 0.6, 0.38, "M_IntPoster1", text="DUEL ACADEMY",
                         text_size=0.08)
                aset.prop("SM_Int_Pillows", (x0 + 1.95, -0.25, zr + 0.03), 10.0)
                for k in range(5):     # a deck spread out on the kotatsu
                    nc.box((x0 + 1.75 + k * 0.09, 0.75, zr + 0.415), (0.06, 0.085, 0.004), "M_CardBack")
            # curtains inside the front window
            K.curtains(nc, (X0, YF), (X1, YF), x0 + 2.95 - X0, 1.4, zf + 0.95, zf + 1.95,
                       ("M_IntFabricRed", "M_SliferLaundryWhite", "M_IntFabricBlue")[(i + floor) % 3], wall_thick=WT)
            # ---- the lived-in layer: fixtures, desk things, jackets, clutter (real sizes)
            DT.dress_room(aset, mb, nc, rx0, ry0, rx1, ry1, zr, ceil, style="japanese", seed=i + 10 * floor,
                          ac=floor == 2 and i % 2 == 0,
                          keep_clear=[(rx0, 2.9, x0 + 1.75, ry1), (rx0, 1.45, rx0 + 0.7, 2.9),
                                      (x0 + 0.6, 1.95, wx1 + 0.1, 2.95),
                                      (wx1 - 0.1, 1.95, rx1 - 0.9, 3.0),     # (the way past the WC)
                                      (rx1 - 1.1, 0.7, rx1, 2.8), (rx0, 0.3, rx0 + 0.5, 1.4)])
            DT.desk_set(nc, aset, x0 + 2.95, ry0 + 0.32, zr + 0.76, 180.0,
                        kind="student", seed=i + 7 * floor, w=1.1, d=0.55)
            # (the jackets clear of the corner post; in rooms 101 / 201 one hook between the post and the window)
            DT.coat_hooks(nc, rx0 + 0.001, ry0 + (0.4 if i == 0 else 0.62), zf + 1.7, 90.0, n=1 if i == 0 else 3,
                          dorm="white" if banner else "slifer", jackets=1 if banner or i == 0 else 2 + (i % 2), seed=i)
            if not banner:
                DT.floor_clutter(nc, aset, rx0, gy1 + 0.1, rx1, 2.9, zr + 0.03, "dorm", n=4, seed=i * 3 + floor,
                                 clear=[(x0 + 1.0, -0.2, x0 + 2.9, 1.9), (rx1 - 1.1, 0.7, rx1, 2.8),
                                        (rx0, 0.3, rx0 + 0.5, 1.4), (rx0, 1.45, rx0 + 0.7, 2.9),
                                        (x0 + 0.6, 1.95, wx1 + 0.1, 2.95),
                                        (wx1 - 0.1, 1.95, rx1 - 0.9, 3.0),   # (the way past the WC)
                                        (x0 + 2.2, gy1, x0 + 3.7, gy1 + 0.9)])
                # wall shelf over the TV: manga, deck boxes, a duel disk
                mb.box_mm((rx0, 0.45, zr + 1.35), (rx0 + 0.25, 1.25, zr + 1.38), K.WOOD)
                # (book_row runs along the frame's x: origin on the shelf, turned 90 deg to follow the wall)
                DT.book_row(nc, rx0 + 0.12, rx0 + 0.12 + 0.75, 0.48, zr + 1.38, 0.16, yaw=90.0, max_h=0.19, seed=i)
                DT.duel_disk(nc, x0 + 2.3, ry1 - 0.2, zr + 0.7, 25.0 + i * 40)        # (on the colour-box shelf)
                if jaden:
                    DT.deck_box(nc, x0 + 2.15, 0.95, zr + 0.415, 20.0, "M_IntFabricRed")
            else:
                DT.shelf_fill(nc, aset, rx0 + 0.18, 0.9, [zr + 0.45, zr + 0.85], 90.0, 0.85, 0.28, "decor", seed=55)
                aset.prop("SM_Int_CatStatue", (x0 + 3.0, 0.55, zr + 0.06), 160.0)    # Pharaoh dozing in the basket
            # light: flush ceiling lamp (+ a ceiling fan upstairs, where the ceiling is higher)
            K.panel_light(aset, nc, x0 + 2.4, 0.4, ceil, w=0.55, d=0.55, intensity=2600.0, radius=6.5,
                          color=(1.0, 0.88, 0.7))
            if floor == 2 and not banner:
                aset.prop("SM_Int_CeilingFan", (x0 + 2.4, 1.6, ceil), i * 23.0)
            _room_more(aset, mb, nc, i, floor, x0, rx0, rx1, zf, zr, ceil, rng)
    # preview cameras (Tools/preview_asset.py slifer --views inside)
    K.camera(aset, "room101", (X0 + 0.8, YF + 0.5, ZG + 1.55), (X0 + 3.4, 2.6, ZG + 0.9), 15.0)
    K.camera(aset, "room204", (_x0(3) + 0.8, YF + 0.5, Z2 + 1.6), (_x0(3) + 3.4, 2.6, Z2 + 0.9), 15.0)
    K.camera(aset, "room106", (_x0(5) + 0.8, YF + 0.5, ZG + 1.55), (_x0(5) + 3.4, 2.6, ZG + 0.9), 15.0)
    K.camera(aset, "room206_banner", (_x0(5) + 0.8, YF + 0.5, Z2 + 1.6), (_x0(5) + 3.0, 2.6, Z2 + 0.9), 15.0)
    K.camera(aset, "walkway", (X1 - 0.5, YWK + 0.4, Z2 + 1.6), (X0 + 4.0, YF, Z2 + 1.2), 20.0)

def _manga(nc, x, y, z, yaw, n, seed):
    """A pile of manga volumes (small paperbacks), slightly askew."""
    r = random.Random(seed)
    h = z
    for k in range(n):
        with nc.at((x + r.uniform(-0.01, 0.01), y + r.uniform(-0.01, 0.01), h + 0.009), rot=yaw + r.uniform(-14, 14)):
            nc.box((0, 0, 0), (0.115, 0.175, 0.018), r.choice(("M_IntFabricRed", "M_IntFabricBlue", "M_IntFabricYellow",
                                                               "M_IntFabricWhite", "M_IntFabricGreen", "M_IntFabricOrange")))
        h += 0.018


def _hanging_laundry(nc, x0, x1, y, z, seed, jacket=True):
    """A cord strung across the room with clothes pegged on it (indoor drying, it rains a lot)."""
    r = random.Random(seed)
    nc.beam((x0, y, z), (x1, y, z), 0.008, 0.008, "M_IntWoodDark")
    x = x0 + 0.15
    first = jacket
    while x < x1 - 0.3:
        if first:
            w, h, m = 0.45, 0.62, "M_DetJacketRed"
            first = False
        else:
            w, h = r.uniform(0.25, 0.45), r.uniform(0.2, 0.55)
            m = r.choice(("M_SliferLaundryWhite", "M_SliferLaundryBlue", "M_IntFabricRed", "M_IntFabricWhite"))
        nc.box((x + w / 2, y, z - h / 2 - 0.01), (w, 0.02, h), m)
        x += w + r.uniform(0.06, 0.18)


def _room_more(aset, mb, nc, i, floor, x0, rx0, rx1, zf, zr, ceil, rng):
    """Second lived-in layer for a dorm room: zabuton, manga piles, colour-box shelf under the back window,
    laundry on a cord, ramen cups, more posters, a mirror, a bin (real sizes)."""
    num = f"{floor}0{i + 1}"
    banner = num == "206"
    r = random.Random(i * 7 + floor)
    ry0, ry1 = YF + WT, YB - WT
    # colour-box shelf (2 x 3 cubbies) under the back window, between the WC and the bunk
    sx0, sx1 = x0 + 1.85, x0 + 3.05
    mb.box_mm((sx0, ry1 - 0.3, zr), (sx1, ry1, zr + 0.7), K.TRIM_WHITE if not banner else K.WOOD)
    for k in range(3):
        cx = sx0 + (sx1 - sx0) * (k + 0.5) / 3
        for lv in (0.04, 0.37):
            nc.box((cx, ry1 - 0.301, zr + lv + 0.15), (0.36, 0.004, 0.29), K.BLACK)
            if r.random() < 0.7:
                DT.book_row(nc, cx - 0.17, cx + 0.15, ry1 - 0.16, zr + lv + 0.02, 0.18, max_h=0.19, seed=i * 10 + k,
                            gaps=0.05)
    for k in range(2):
        _manga(nc, sx0 + 0.2 + k * 0.8, ry1 - 0.5, zr + 0.03, 0.0, r.randint(4, 9), i + k + floor)
    # washitsu carpentry: nageshi rail round the room at door-head height, corner posts, ceiling battens
    zn = zr + 2.0
    for (a0, b0, a1, b1) in ((rx0, ry0, rx1, ry0 + 0.04), (rx0, ry0, rx0 + 0.04, 2.95), (rx1 - 0.04, ry0, rx1, ry1)):
        mb.box_mm((a0, b0, zn), (a1, b1, zn + 0.1), K.WOOD)
    for (px, py) in ((rx0, ry0), (rx1 - 0.1, ry0), (rx1 - 0.1, ry1 - 0.1)):
        mb.box_mm((px, py, zf), (px + 0.1, py + 0.1, ceil), K.WOOD)
    for k in range(int((ry1 - ry0) / 0.45)):
        y = ry0 + 0.3 + k * 0.45
        nc.box(((rx0 + rx1) / 2, y, ceil - 0.012), (rx1 - rx0, 0.035, 0.024), K.WOOD)
    # (the kotatsu brings its own three zabuton; a second set lay on top of them)
    if not banner:
        for k in range(2):                                                         # cup ramen on the kotatsu
            nc.cylinder((x0 + 1.75 + k * 0.4, 1.05, zr + 0.397), 0.045, 0.09, "M_IntTrimWhite", seg=10, radius_top=0.055)
            nc.cylinder((x0 + 1.75 + k * 0.4, 1.05, zr + 0.487), 0.056, 0.004, "M_IntFabricRed", seg=10)
        for k in range(3):
            _manga(nc, x0 + 1.0 + k * 0.55, -1.25 + (k % 2) * 0.3, zr + 0.03, r.uniform(0, 90), r.randint(3, 8),
                   i * 5 + k + floor)
        # (strung along the back wall over the colour-box shelf: clothes hanging to 1.4 m across the room
        # were in everyone's face and in the WC door's swing)
        _hanging_laundry(nc, x0 + 1.85, rx1 - 0.2, YB - WT - 0.16, zr + 2.05, i + floor * 3)
        # party wall in front of the bunk: colour-box tower (manga, deck boxes, figures) + mini fridge
        tx = rx1 - 0.16
        mb.box_mm((rx1 - 0.32, -0.75, zr), (rx1, 0.45, zr + 1.15), K.TRIM_WHITE)
        for lv in (0.03, 0.4, 0.77):
            for k, yy in enumerate((-0.45, 0.15)):
                nc.box((rx1 - 0.321, yy, zr + lv + 0.17), (0.004, 0.56, 0.33), K.BLACK)
                if r.random() < 0.75:
                    DT.book_row(nc, tx, tx + 0.5, yy - 0.26, zr + lv + 0.02, 0.2, yaw=90.0, max_h=0.19,
                                seed=i * 13 + k + int(lv * 10), gaps=0.08)
        DT.deck_box(nc, tx, -0.3, zr + 1.15, 15.0 * i, "M_IntFabricRed")
        DT.deck_box(nc, tx + 0.02, -0.15, zr + 1.15, 40.0, "M_IntFabricBlue")
        nc.box((tx, 0.2, zr + 1.25), (0.08, 0.06, 0.2), "M_IntFabricYellow")             # figure
        mb.box_mm((rx1 - 0.48, -1.65, zr), (rx1 - 0.02, -1.15, zr + 0.82), K.TRIM_WHITE)   # mini fridge
        nc.box((rx1 - 0.485, -1.4, zr + 0.6), (0.01, 0.03, 0.2), K.METAL)
        nc.cylinder((rx1 - 0.25, -1.35, zr + 0.82), 0.033, 0.12, "M_IntFabricOrange", seg=8)   # soda can
        # a guest futon spread out on the tatami (somebody always sleeps over)
        K.futon(nc, x0 + 3.3, -0.45, 90.0, mat=("M_IntFabricRed", "M_SliferLaundryBlue")[i % 2])
        K.poster(nc, aset, x0 + 4.0, ry0, zr + 1.65, 180.0, 0.38, 0.52, K.POSTERS[(i + 3) % 4],
                 text=("DRAW", "WIN", "GX", "ACE")[i % 4], text_size=0.05)
        aset.prop("SM_Int_Mirror", (rx0, -0.82 if i == 0 else -1.25, zr + 1.0), 90.0)
        # tansu chest against the left wall with a few things on top
        mb.box_mm((rx0, -0.7, zr), (rx0 + 0.45, 0.25, zr + 0.75), K.WOOD_DARK)
        for k in range(3):
            nc.box((rx0 + 0.452, -0.225, zr + 0.13 + k * 0.24), (0.004, 0.88, 0.2), K.WOOD)
            nc.box((rx0 + 0.47, -0.225, zr + 0.13 + k * 0.24), (0.02, 0.12, 0.025), K.METAL)
        aset.prop("SM_Int_AlarmClock", (rx0 + 0.22, -0.45, zr + 0.75), 90.0)
        _manga(nc, rx0 + 0.22, 0.0, zr + 0.75, 0.0, 6, i + 40)
        # big Slifer tapestry on the party wall above the futon
        with nc.at((rx1 - 0.01, -0.6, zr + 1.55), rot=-90.0):
            nc.box((0, -0.006, 0), (1.6, 0.012, 0.69), "M_IntFabricRed")
            nc.box((0, -0.004, 0), (1.66, 0.008, 0.75), "M_IntFabricYellow")
            nc.box((0, -0.009, 0.36), (1.7, 0.02, 0.03), K.WOOD)
        aset.text("SLIFER RED", K.wall_point(rx1 - 0.01, -0.6, -90.0, 0.02, zr + 1.47), -90.0, size=0.16,
                  color=(1.0, 0.85, 0.2))
        K.poster(nc, aset, x0 + 1.835, ry0 + 0.01, zr + 1.6, 180.0, 0.42, 0.6, K.POSTERS[(i + 2) % 4],
                 text=("HERO!", "DRAW!", "FUSION", "LV 4")[(i + floor) % 4], text_size=0.06)
        K.poster(nc, aset, x0 + 1.7, 3.9, zr + 1.5, 90.0, 0.5, 0.65, K.POSTERS[(i + 1) % 4],
                 text=("SLIFER", "GO!", "DUEL!", "GX")[(i + 2 * floor) % 4], text_size=0.07)
        nc.cylinder((rx1 - 1.15, 3.4, zr + 0.03), 0.13, 0.3, "M_IntSteelBlue", seg=10, cap_top=False)        # bin
        for k in range(2):
            nc.sphere((rx1 - 1.15 + k * 0.1, 3.4, zr + 0.3), 0.05, "M_IntPaper", seg=6, rings=4)
    else:
        for k in range(3):
            _manga(nc, x0 + 2.2 + k * 0.35, -1.3, zr + 0.03, 20.0 * k, 6 + k, 60 + k)
        aset.prop("SM_Int_Frame", (rx1, -1.25, zr + 1.45), -90.0)
        aset.prop("SM_Int_Frame", (rx1, 1.0, zr + 1.55), -90.0)
        for k in range(4):                                                         # alchemy flasks
            nc.cylinder((rx0 + 0.18, 0.55 + k * 0.2, zr + 2.0 + 0.0), 0.045, 0.12, "M_IntGlassClear", seg=8)
        with mb.at((0, 0, zr)), nc.at((0, 0, zr)):
            K.bookcase(mb, nc, rx0 + 0.17, -0.75, 90.0, w=1.1, d=0.3, h=1.8, shelves=5, rng_seed=207)
        aset.prop("SM_Int_PottedPlantC", (rx1 - 0.42, -1.45, zr + 0.03), 0.0)
        K.poster(nc, aset, rx1 - 0.01, 0.05, zr + 1.72, -90.0, 1.3, 0.55, "M_IntPaper", text="ELEMENTS OF ALCHEMY",
                 text_color=(0.3, 0.2, 0.1), text_size=0.06)
        nc.box((x0 + 3.3, -0.2, zr + 0.036), (1.5, 1.3, 0.012), "M_IntFabricGreen")       # rug under the armchair
        K.poster(nc, aset, x0 + 1.7, 3.9, zr + 1.5, 90.0, 0.6, 0.8, "M_IntPaper", text="ALCHEMY",
                 text_color=(0.2, 0.4, 0.2), text_size=0.08)


# ------------------------------------------------------------------ main block
def _main_block(aset, mb, nc):
    # foundation / plinth and the concrete apron under the walkway
    mb.box_mm((X0 - 0.1, YF - 0.1, FOUND), (X1 + 0.1, YB + 0.1, ZG), CONC)
    mb.box_mm((ROOF_X0 + 0.15, YWK - 0.2, FOUND), (X1 + 0.25, YF - 0.1, 0.1), CONC)
    # body: hollow storeys (real door / window openings, rooms inside - see _rooms)
    _shell(aset, mb)
    for x, sgn in ((X0, -1), (X1, 1)):
        tri = [(x, YF, ZW), (x, YB, ZW), (x, YR, ZR - 0.16)]
        mb.poly(tri if sgn > 0 else list(reversed(tri)), WALL)
        # gable vent
        mb.box((x + sgn * 0.04, YR, ZW + 0.42), (0.08, 0.9, 0.5), TRIM)
        for k in range(3):
            mb.box((x + sgn * 0.09, YR, ZW + 0.26 + k * 0.14), (0.04, 0.8, 0.05), "M_DarkWood")
    # corner boards, belt course and base trim
    for x in (X0, X1):
        for y in (YF, YB):
            mb.box((x, y, (ZG + ZW) / 2), (0.16, 0.16, ZW - ZG), TRIM)
    mb.box_mm((X0 - 0.04, YB, Z2 - 0.12), (X1 + 0.04, YB + 0.06, Z2 + 0.04), TRIM)
    for x, s in ((X0, -1), (X1, 1)):
        mb.box_mm((min(x, x + s * 0.06), YF, Z2 - 0.12), (max(x, x + s * 0.06), YB, Z2 + 0.04), TRIM)
    mb.box_mm((X0 - 0.04, YB, ZG), (X1 + 0.04, YB + 0.05, ZG + 0.18), TRIM)
    xa = X0 - 0.04                          # (front base trim: stops at the ground-floor doorways)
    for i in range(NROOMS):
        ud = _x0(i) + 1.05
        mb.box_mm((xa, YF - 0.05, ZG), (ud - 0.45 - 0.1, YF, ZG + 0.18), TRIM)
        xa = ud + 0.45 + 0.1
    mb.box_mm((xa, YF - 0.05, ZG), (X1 + 0.04, YF, ZG + 0.18), TRIM)
    # room dividers on the front (pilasters between units)
    for i in range(1, NROOMS):
        x = X0 + i * RW
        mb.box((x, YF - 0.04, (ZG + ZW) / 2), (0.14, 0.08, ZW - ZG), TRIM, skip=("+y",))

    # ---------------- front: doors, windows, plates, porch lamps
    for floor, z in ((1, ZG), (2, Z2)):
        for i in range(NROOMS):
            x0 = X0 + i * RW
            ud, uw = x0 + 1.05, x0 + 2.95
            with mb.at((0, YF, 0)):
                window(mb, uw, z + 0.95, 1.4, 1.0, glass=None)
                mb.box((ud, -0.07, z + 2.32), (0.26, 0.02, 0.13), "M_WindowFrame")   # number plate
            # porch lamp next to the door
            with mb.at((0, YF, 0)):
                mb.box((ud + 0.8, -0.06, z + 2.2), (0.14, 0.12, 0.08), "M_DarkMetal", skip=("+y",))
                mb.box((ud + 0.8, -0.16, z + 2.12), (0.18, 0.18, 0.04), "M_DarkMetal")
            nc.box((ud + 0.8, YF - 0.16, z + 2.0), (0.12, 0.12, 0.16), "M_LampGlow")
            aset.light((ud + 0.8, YF - 0.35, z + 1.9), (1.0, 0.78, 0.48), 2500.0, 6.0, night_only=True)
            aset.text(f"{floor}0{i + 1}", (ud, YF - 0.105, z + 2.29), 0.0, size=0.09, color=(0.15, 0.08, 0.05))
            if floor == 1:   # concrete stoop
                mb.box_mm((ud - 0.65, YF - 0.45, 0.0), (ud + 0.65, YF, ZG), CONC)

    # ---------------- back: small windows, patched boards, mailboxes, sign
    with mb.at((0, YB, 0), rot=180):
        # local u runs -x in world: u = -x
        for z in (ZG + 0.9, Z2 + 1.0):
            for i in range(NROOMS):
                x = X0 + i * RW + 2.4
                window(mb, -x, z, 1.0, 0.75, glass=None)
                window(mb, -(X0 + i * RW + 0.9), z + 0.35, 0.5, 0.4, mullion=False, glass=None)   # WC vent
        # weathered patch boards (run-down charm)
        for k, (u, zz, ang) in enumerate(((-(-6.4), 1.2, 3), (-(-6.1), 1.6, -2), (-(2.5), 4.7, 2))):
            with mb.at((u, -0.03, zz), rot_y=ang):
                mb.box((0, 0, 0), (1.1, 0.05, 0.22), "M_Wood")
                mb.box((-0.45, -0.03, 0), (0.04, 0.02, 0.04), "M_DarkMetal")
                mb.box((0.45, -0.03, 0), (0.04, 0.02, 0.04), "M_DarkMetal")
        # mailbox rack near the west corner
        for r in range(2):
            for c in range(3):
                u = -(X0 + 0.8 + c * 0.45)
                zz = 1.05 + r * 0.38
                mb.box((u, -0.16, zz), (0.4, 0.3, 0.32), DOOR)
                mb.box((u, -0.32, zz + 0.06), (0.24, 0.02, 0.04), "M_Black")
        mb.box((-(X0 + 1.25), -0.16, 0.86), (1.45, 0.34, 0.06), TRIM)
        # dorm sign on the back wall (faces the arriving path)
        mb.box((-(-5.0), -0.08, 4.45), (6.0, 0.12, 0.9), DOOR)
        mb.box((-(-5.0), -0.05, 4.45), (6.25, 0.1, 1.1), TRIM)
    aset.text("SLIFER RED DORM", (-5.0, YB + 0.17, 4.42), 180.0, size=0.62, color=(1.0, 0.96, 0.86))
    for x in (-8.2, -1.8):
        mb.box((x, YB + 0.25, 5.15), (0.08, 0.5, 0.06), "M_DarkMetal")
        nc.box((x, YB + 0.5, 5.07), (0.18, 0.12, 0.1), "M_LampGlow")
    for x in (-8.2, -1.8):
        aset.light((x, YB + 0.55, 5.05), (1.0, 0.8, 0.55), 2000.0, 7.0, night_only=True)

    # end walls: windows (east end faces the dining hall passage)
    with mb.at((X1, 0, 0), rot=90):
        # local u = world y ; outward = +x
        for z in (ZG + 1.1, Z2 + 1.0):
            window(mb, 3.8, z, 1.0, 0.9, glass=None)
    with mb.at((X0, 0, 0), rot=-90):
        # local u = -y ; outward = -x
        window(mb, 1.6, Z2 + 1.0, 1.0, 0.9, glass=None)
        window(mb, 1.6, ZG + 1.1, 1.0, 0.9, glass=None)

    # ---------------- upper walkway along the front
    slab(mb, [(X0, YWK, Z2), (X1, YWK, Z2), (X1, YF, Z2), (X0, YF, Z2)], 0.2, "M_Wood",
         bottom_mat="M_DarkWood", side_mat=TRIM)
    # stair landing (west end, joins the walkway)
    LX = ROOF_X0 + 0.25    # outer x of landing
    slab(mb, [(LX, YWK, Z2), (X0, YWK, Z2), (X0, 0.6, Z2), (LX, 0.6, Z2)], 0.2, "M_Wood",
         bottom_mat="M_DarkWood", side_mat=TRIM)
    # fascia + joists + edge beam + posts
    mb.box_mm((LX - 0.04, YWK - 0.08, Z2 - 0.32), (X1 + 0.04, YWK, Z2 + 0.03), TRIM)
    nj = int((X1 - X0) / 1.0)
    for k in range(nj + 1):
        x = X0 + (X1 - X0) * k / nj
        mb.box_mm((x - 0.05, YWK, Z2 - 0.34), (x + 0.05, YF, Z2 - 0.2), "M_DarkWood")
    post_y = YWK + 0.14
    posts = [X0 + i * RW for i in range(NROOMS + 1)] + [LX + 0.12]
    for x in posts:
        xx = min(max(x, LX + 0.12), X1 - 0.12)
        mb.box((xx, post_y, (0.1 + Z2 - 0.32) / 2), (0.18, 0.18, Z2 - 0.32 - 0.1), TRIM)
        mb.box((xx, post_y, Z2 - 0.4), (0.5, 0.12, 0.12), TRIM)   # knee brace block
    mb.box((LX + 0.12, 0.45, (0.0 + Z2 - 0.2) / 2), (0.18, 0.18, Z2 - 0.2), TRIM)
    # walkway railing (a couple of balusters missing - it's the Slifer dorm)
    RZ = Z2
    railing(mb, (LX + 0.06, YWK + 0.06, RZ), (X1 - 0.06, YWK + 0.06, RZ), 1.05, TRIM,
            skip=(37, 38, 81))
    railing(mb, (X1 - 0.06, YWK + 0.06, RZ), (X1 - 0.06, YF - 0.06, RZ), 1.05, TRIM)
    railing(mb, (LX + 0.06, YWK + 0.06, RZ), (LX + 0.06, 0.6, RZ), 1.05, TRIM)

    # ---------------- exterior staircase (west end, climbs from the back towards the sea)
    SX0, SX1 = LX + 0.06, X0 - 0.04            # stair width ~1.6 m
    n_tread, rise, run = 15, Z2 / 16.0, 0.28    # 16 risers of 0.1875 m, 0.28 m going
    y_start = 0.6 + n_tread * run               # bottom edge (y = 4.8)
    for i in range(n_tread):
        zt = rise * (i + 1)
        ya, yb2 = y_start - run * (i + 1), y_start - run * i
        mb.box_mm((SX0 + 0.08, ya - 0.02, zt - 0.06), (SX1 - 0.02, yb2, zt), "M_Wood")
        mb.box_mm((SX0 + 0.08, yb2 - 0.03, zt - rise + 0.02), (SX1 - 0.02, yb2, zt - 0.06), "M_DarkWood")
    for x in (SX0 + 0.04, SX1 - 0.04):     # stringers just under the nosing line
        mb.beam((x, y_start + run, -0.2), (x, 0.6, Z2 - 0.2), 0.08, 0.3, TRIM)
    mb.box((SX0 + 0.04, y_start - 0.1, 0.5), (0.12, 0.12, 1.0), TRIM)
    railing(mb, (SX0 + 0.0, y_start - 0.05, 0.25), (SX0 + 0.0, 0.65, Z2), 1.0, TRIM, baluster=0.28)
    mb.box_mm((SX0 - 0.2, y_start - 0.3, -0.3), (SX1 + 0.1, y_start + 0.6, 0.02), CONC)   # landing pad

    # ---------------- roof
    zfe, zbe = roof_z(ROOF_YF), roof_z(ROOF_YB)
    RT = 0.15
    slab(mb, [(ROOF_X0, ROOF_YF, zfe), (ROOF_X1, ROOF_YF, zfe), (ROOF_X1, YR, ZR), (ROOF_X0, YR, ZR)], RT, ROOF)
    slab(mb, [(ROOF_X0, YR, ZR), (ROOF_X1, YR, ZR), (ROOF_X1, ROOF_YB, zbe), (ROOF_X0, ROOF_YB, zbe)], RT, ROOF)
    # standing seams (corrugated look)
    nseam = int((ROOF_X1 - ROOF_X0) / 0.9)
    for k in range(1, nseam):
        x = ROOF_X0 + (ROOF_X1 - ROOF_X0) * k / nseam
        mb.beam((x, ROOF_YF, zfe + 0.025), (x, YR, ZR + 0.025), 0.06, 0.05, ROOF)
        mb.beam((x, YR, ZR + 0.025), (x, ROOF_YB, zbe + 0.025), 0.06, 0.05, ROOF)
    mb.box((0.5 * (ROOF_X0 + ROOF_X1), YR, ZR + 0.03), (ROOF_X1 - ROOF_X0 + 0.1, 0.45, 0.1), TRIM)
    # fascia boards + verge boards
    mb.box_mm((ROOF_X0 - 0.06, ROOF_YF - 0.08, zfe - 0.32), (ROOF_X1 + 0.06, ROOF_YF, zfe + 0.03), TRIM)
    mb.box_mm((ROOF_X0 - 0.06, ROOF_YB, zbe - 0.32), (ROOF_X1 + 0.06, ROOF_YB + 0.08, zbe + 0.03), TRIM)
    for x in (ROOF_X0 - 0.03, ROOF_X1 + 0.03):
        mb.beam((x, ROOF_YF, zfe - 0.1), (x, YR, ZR - 0.1), 0.08, 0.3, TRIM)
        mb.beam((x, YR, ZR - 0.1), (x, ROOF_YB, zbe - 0.1), 0.08, 0.3, TRIM)
    # gutters + downpipes
    for y, z, s in ((ROOF_YF - 0.2, zfe - 0.28, -1), (ROOF_YB + 0.2, zbe - 0.28, 1)):
        mb.box_mm((ROOF_X0, y - 0.1, z - 0.06), (ROOF_X1, y + 0.1, z + 0.1), "M_Metal")
        for x in (ROOF_X0 + 0.25, ROOF_X1 - 0.25):
            mb.cylinder((x, y, 0.0), 0.06, z, "M_Metal", seg=8)
            mb.box((x, y + s * 0.0, 0.08), (0.16, 0.16, 0.16), "M_Metal")
    # rafter tails under the front eave
    for k in range(int((ROOF_X1 - ROOF_X0) / 1.3) + 1):
        x = ROOF_X0 + 0.2 + k * 1.3
        if x > ROOF_X1 - 0.1:
            break
        mb.beam((x, YF, roof_z(YF) - RT - 0.05), (x, ROOF_YF + 0.1, zfe - RT - 0.05), 0.08, 0.12, "M_DarkWood")

    # ---------------- roof clutter: water tank, vent pipes, antenna
    tx = -12.0
    for dx in (-0.6, 0.6):
        for dy in (-0.6, 0.6):
            zb = roof_z(YR + dy)
            mb.box((tx + dx, YR + dy, (zb + ZR + 0.7) / 2), (0.1, 0.1, ZR + 0.7 - zb), "M_RustMetal")
    mb.box((tx, YR, ZR + 0.75), (1.6, 1.6, 0.1), "M_RustMetal")
    mb.cylinder((tx, YR, ZR + 0.8), 0.78, 1.3, "M_Metal", seg=16)
    mb.cone((tx, YR, ZR + 2.1), 0.8, 0.3, "M_Metal", seg=16)
    for zz in (ZR + 1.05, ZR + 1.7):
        mb.cylinder((tx, YR, zz), 0.8, 0.06, "M_RustMetal", seg=16)
    mb.beam((tx + 0.78, YR, ZR + 1.0), (tx + 1.6, YR, ZR + 1.0), 0.08, 0.08, "M_Metal")
    mb.beam((tx + 1.6, YR, ZR + 1.0), (tx + 1.6, YR + 2.0, roof_z(YR + 2.0) + 0.06), 0.08, 0.08, "M_Metal")
    for vx, vy in ((-6.5, 3.2), (1.5, 3.2), (5.5, 3.0)):
        zb = roof_z(vy) - 0.1
        mb.cylinder((vx, vy, zb), 0.09, 1.1, "M_DarkMetal", seg=8)
        mb.cone((vx, vy, zb + 1.1), 0.18, 0.16, "M_DarkMetal", seg=8)
    ax, ay = 3.5, 2.0
    mb.cylinder((ax, ay, roof_z(ay) - 0.1), 0.04, 2.2, "M_Metal", seg=6)
    for k, ln in enumerate((1.6, 1.2, 0.8)):
        mb.box((ax, ay, roof_z(ay) + 1.4 + k * 0.3), (0.03, ln, 0.03), "M_Metal")

    # dorm name board hung on the outside of the walkway railing (faces the yard / sea)
    bx = -5.4
    mb.box((bx, YWK - 0.04, Z2 + 0.6), (4.1, 0.08, 0.8), WALL)
    mb.box((bx, YWK - 0.1, Z2 + 0.6), (3.9, 0.06, 0.64), DOOR)
    aset.text("SLIFER RED DORM", (bx, YWK - 0.155, Z2 + 0.58), 0.0, size=0.4, color=(1.0, 0.96, 0.86))
    # rusty patches on the corrugated roof
    for (px, py, w, d) in ((-15.5, -2.5, 1.8, 1.6), (-3.0, 3.6, 2.2, 1.2), (5.2, -3.8, 1.4, 1.5), (-8.0, -0.9, 1.0, 1.2)):
        y0, y1 = py - d / 2, py + d / 2
        z0, z1 = roof_z(y0) + 0.012, roof_z(y1) + 0.012
        mb.poly([(px - w / 2, y0, z0), (px + w / 2, y0, z0), (px + w / 2, y1, z1), (px - w / 2, y1, z1)], "M_RustMetal")
    # ---------------- futons airing over the walkway railing (no collision)
    for fx, mat in ((-9.6, "M_SliferLaundryBlue"), (-1.2, "M_SliferLaundryWhite"), (4.6, "M_SliferLaundryBlue")):
        nc.box((fx, YWK - 0.04, Z2 + 0.55), (1.4, 0.06, 1.0), mat)
        nc.box((fx, YWK + 0.06, Z2 + 1.11), (1.4, 0.26, 0.06), mat)
        nc.box((fx, YWK + 0.16, Z2 + 0.85), (1.4, 0.06, 0.5), mat)
    # potted plants on the apron
    for px in (-15.6, -6.2, 6.8):
        mb.cylinder((px, YF - 0.45, 0.1), 0.22, 0.4, "M_RustMetal", seg=10, radius_top=0.26)
        nc.sphere((px, YF - 0.45, 0.72), 0.32, "M_LeavesBush", seg=8, rings=6)
    # walkway life: sandals outside some doors, a broom + bucket by the stair, a crate of drinks, a plant
    r = random.Random(3)
    for i in (0, 1, 3, 4):
        ud = X0 + i * RW + 1.05
        for k in range(2 if i % 2 else 1):
            for s in (-1, 1):
                nc.box((ud + 0.55 + k * 0.3 + s * 0.06, YF - 0.35, Z2 + 0.02), (0.1, 0.25, 0.03),
                       r.choice(("M_IntFabricRed", "M_SliferLaundryBlue", "M_IntBlack")))
    aset.prop("SM_Int_Broom", (X0 - 0.4, -3.6, Z2), 90.0)
    aset.prop("SM_Int_Bucket", (X0 - 0.7, -4.2, Z2), 0.0)
    aset.prop("SM_Crate", (X1 - 0.45, YF - 0.5, Z2), 10.0, 0.6)
    nc.cylinder((-3.4, YF - 0.35, Z2), 0.16, 0.3, "M_RustMetal", seg=10, radius_top=0.19)
    nc.sphere((-3.4, YF - 0.35, Z2 + 0.5), 0.24, "M_LeavesBush", seg=8, rings=6)
    # stair landing lamp
    nc.box((LX + 0.12, -1.0, Z2 + 2.1), (0.14, 0.14, 0.18), "M_LampGlow")
    mb.box((LX + 0.12, -1.0, Z2 + 2.25), (0.2, 0.2, 0.08), "M_DarkMetal")
    aset.light((LX + 0.12, -1.0, Z2 + 2.1), (1.0, 0.78, 0.48), 3000.0, 7.0, night_only=True)


# ------------------------------------------------------------------ dining hall annex
def _dining(aset, mb, nc):
    cx = (DX0 + DX1) / 2
    cy = (DY0 + DY1) / 2
    mb.box_mm((DX0 - 0.1, DY0 - 0.1, FOUND), (DX1 + 0.1, DY1 + 0.1, DZ), CONC)
    ops = {
        0: [dict(u=2.5, w=1.6, z0=0.02, z1=2.55, frame=TRIM),      # (z0: the threshold is the floor's level)
            dict(u=6.6, w=2.8, z0=0.95, z1=2.35, glass="M_GlassClear", frame=TRIM)],
        1: [dict(u=2.0, w=1.6, z0=1.0, z1=2.3, glass="M_GlassClear", frame=TRIM),
            dict(u=4.9, w=1.6, z0=1.0, z1=2.3, glass="M_GlassClear", frame=TRIM),
            dict(u=7.1, w=0.9, z0=1.35, z1=2.2, glass="M_GlassClear", frame=TRIM)],
        2: [dict(u=4.5, w=1.0, z0=1.35, z1=2.2, glass="M_GlassClear", frame=TRIM)],
        3: [dict(u=4.5, w=1.6, z0=1.0, z1=2.3, glass="M_GlassClear", frame=TRIM)],
    }
    mb.room([(DX0, DY0), (DX1, DY0), (DX1, DY1), (DX0, DY1)], DZ, DWH, 0.2, WALL, openings=ops,
            floor_mat=K.WOODFLOOR, inner_mat="M_CreamWall")
    zt = DZ + DWH
    mb.poly([(DX0, DY0, zt - 0.22), (DX0, DY1, zt - 0.22), (DX1, DY1, zt - 0.22), (DX1, DY0, zt - 0.22)],
            "M_CreamWall")
    # mullions in the big front window
    for u in (DX0 + 6.6 - 0.47, DX0 + 6.6 + 0.47):
        mb.box((u, DY0 + 0.1, DZ + 1.65), (0.06, 0.24, 1.4), TRIM)
    # corner boards + base trim
    for x in (DX0, DX1):
        for y in (DY0, DY1):
            mb.box((x, y, (DZ + zt) / 2), (0.16, 0.16, DWH), TRIM)
    mb.box_mm((DX0 - 0.04, DY1, DZ), (DX1 + 0.04, DY1 + 0.05, DZ + 0.15), TRIM)
    mb.box_mm((DX1, DY0, DZ), (DX1 + 0.05, DY1, DZ + 0.15), TRIM)
    mb.box_mm((DX0 - 0.05, DY0, DZ), (DX0, DY1, DZ + 0.15), TRIM)
    # gable roof, ridge along Y (gable faces the sea)
    RH = 1.6
    mb.gable_roof((cx, cy, zt), DX1 - DX0, DY1 - DY0, RH, ROOF, overhang=0.5, thick=0.15,
                  gable_mat=WALL, ridge_axis="y")
    hw = (DX1 - DX0) / 2 + 0.5
    drop = RH * 0.5 / ((DX1 - DX0) / 2)
    ze = zt - drop
    for s in (-1, 1):
        nseam = 11
        for k in range(1, nseam):
            y = DY0 - 0.5 + (DY1 - DY0 + 1.0) * k / nseam
            mb.beam((cx + s * hw, y, ze + 0.025), (cx, y, zt + RH + 0.025), 0.06, 0.05, ROOF)
        mb.box((cx + s * hw, cy, ze - 0.12), (0.08, DY1 - DY0 + 1.1, 0.28), TRIM)   # fascia
        mb.box((cx + s * (hw + 0.15), cy, ze - 0.3), (0.2, DY1 - DY0 + 1.0, 0.16), "M_Metal")  # gutter
        mb.cylinder((cx + s * (hw + 0.15), DY1 + 0.3, 0.0), 0.06, ze - 0.3, "M_Metal", seg=8)
    mb.box((cx, cy, zt + RH + 0.03), (0.4, DY1 - DY0 + 1.1, 0.1), TRIM)
    for y in (DY0 - 0.53, DY1 + 0.53):
        mb.beam((cx - hw, y, ze - 0.1), (cx, y, zt + RH - 0.1), 0.3, 0.08, TRIM)
        mb.beam((cx, y, zt + RH - 0.1), (cx + hw, y, ze - 0.1), 0.3, 0.08, TRIM)

    # "DINING HALL" board on the front gable
    mb.box((cx, DY0 - 0.05, zt + 0.42), (3.4, 0.1, 0.55), DOOR)
    mb.box((cx, DY0 - 0.031, zt + 0.42), (3.6, 0.058, 0.7), TRIM)
    aset.text("DINING HALL", (cx, DY0 - 0.13, zt + 0.40), 0.0, size=0.38, color=(1.0, 0.95, 0.82))

    # ---------------- covered deck / porch with steps
    mb.box_mm((DX0, DECK_Y, FOUND), (DX1, DY0 - 0.1, DZ), "M_DarkWood", mats={"+z": "M_Wood"})
    for k in range(int((DX1 - DX0) / 0.25)):
        x = DX0 + 0.125 + k * 0.25
        mb.box((x, (DECK_Y + DY0) / 2, DZ + 0.005), (0.015, DY0 - DECK_Y - 0.02, 0.012), "M_DarkWood")
    sx0, sx1 = 12.6, 14.4
    mb.box_mm((sx0, DECK_Y - 0.35, FOUND), (sx1, DECK_Y, 0.30), "M_Wood")
    mb.box_mm((sx0, DECK_Y - 0.7, FOUND), (sx1, DECK_Y - 0.35, 0.15), "M_Wood")
    railing(mb, (DX0 + 0.06, DECK_Y + 0.06, DZ), (sx0 - 0.1, DECK_Y + 0.06, DZ), 0.9, "M_Wood",
            post_mat=TRIM)
    railing(mb, (sx1 + 0.1, DECK_Y + 0.06, DZ), (DX1 - 0.06, DECK_Y + 0.06, DZ), 0.9, "M_Wood",
            post_mat=TRIM)
    railing(mb, (DX1 - 0.06, DECK_Y + 0.06, DZ), (DX1 - 0.06, DY0 - 0.1, DZ), 0.9, "M_Wood",
            post_mat=TRIM)
    # porch roof (lean-to) on four posts
    pz0, pz1 = 2.98, 3.38
    slab(mb, [(DX0 - 0.15, DECK_Y - 0.25, pz0), (DX1 + 0.15, DECK_Y - 0.25, pz0),
              (DX1 + 0.15, DY0, pz1), (DX0 - 0.15, DY0, pz1)], 0.1, ROOF, bottom_mat="M_DarkWood")
    mb.box_mm((DX0 - 0.2, DECK_Y - 0.33, pz0 - 0.28), (DX1 + 0.2, DECK_Y - 0.25, pz0 + 0.03), TRIM)
    mb.box_mm((DX0 - 0.15, DECK_Y + 0.0, pz0 - 0.36), (DX1 + 0.15, DECK_Y + 0.2, pz0 - 0.14), TRIM)
    for x in (DX0 + 0.1, sx0 - 0.1, sx1 + 0.1, DX1 - 0.1):
        mb.box((x, DECK_Y + 0.1, (DZ + pz0 - 0.3) / 2), (0.16, 0.16, pz0 - 0.3 - DZ), TRIM)
    # porch lamp + bench-like crate
    mb.box((DX0 + 1.2, DY0 - 0.06, DZ + 2.35), (0.14, 0.12, 0.08), "M_DarkMetal")
    nc.box((DX0 + 1.2, DY0 - 0.16, DZ + 2.2), (0.12, 0.12, 0.16), "M_LampGlow")
    aset.light((DX0 + 1.2, DY0 - 0.16, DZ + 2.2), (1.0, 0.78, 0.48), 3000.0, 7.0, night_only=True)

    # ---------------- interior: tables, counter window, kitchen
    for ty in (-1.7, 1.0):
        mb.box_mm((15.2, ty - 0.45, DZ + 0.72), (19.2, ty + 0.45, DZ + 0.78), "M_Wood")
        for lx in (15.6, 18.8):
            mb.box_mm((lx - 0.05, ty - 0.35, DZ), (lx + 0.05, ty + 0.35, DZ + 0.72), "M_DarkWood")
        for s in (-1, 1):
            by = ty + s * 0.72
            mb.box_mm((15.2, by - 0.16, DZ + 0.42), (19.2, by + 0.16, DZ + 0.47), "M_Wood")
            for lx in (15.5, 18.9):
                mb.box_mm((lx - 0.04, by - 0.12, DZ), (lx + 0.04, by + 0.12, DZ + 0.42), "M_DarkWood")
        for bx in (15.8, 16.9, 18.0):
            for s in (-1, 1):
                p = (bx, ty + s * 0.25, DZ + 0.78)
                mb.cylinder(p, 0.12, 0.07, "M_WindowFrame", seg=10, radius_top=0.15)
                mb.cylinder((p[0], p[1], p[2] + 0.055), 0.12, 0.01, "M_SliferCurry", seg=10)
    # (mb.room lays its floor 2 cm above the slab: the leaves stand on it, over a threshold flush with it)
    aset.door((DX0 + 2.5, DY0 + 0.1, DZ + 0.02), 0.0, 1.6, 2.53, "slifer", double=True)
    mb.box_mm((DX0 + 2.5 - 0.8, DY0, DZ + 0.02), (DX0 + 2.5 + 0.8, DY0 + 0.2, DZ + 0.025), "M_Wood", skip=("-z",))
    # partition with the serving counter window
    PY = 3.0
    aset.door((DX0 + 0.2 + 7.4, PY + 0.075, DZ + 0.02), 0.0, 0.9, 2.08, "slifer_inner")
    # architraves round the entrance (inside face) and round the kitchen door (both faces)
    for (cx_, w_, h_, ys) in ((DX0 + 2.5, 1.6, 2.55, (DY0 + 0.2 + 0.015,)),
                              (DX0 + 0.2 + 7.4, 0.9, 2.1, (PY - 0.015, PY + 0.15 + 0.015))):
        for yy in ys:
            for sx in (-1, 1):
                mb.box((cx_ + sx * (w_ / 2 + 0.045), yy, DZ + 0.02 + (h_ + 0.09 - 0.02) / 2),
                       (0.09, 0.03, h_ + 0.09 - 0.02), K.TRIM_WOOD)
            mb.box((cx_, yy, DZ + h_ + 0.045), (w_ + 0.18, 0.03, 0.09), K.TRIM_WOOD)
    mb.wall((DX0 + 0.2, PY), (DX1 - 0.2, PY), DZ, DWH, 0.15, "M_CreamWall",
            openings=[dict(u=4.0, w=3.0, z0=0.95, z1=2.1), dict(u=7.4, w=0.9, z0=0.02, z1=2.1)])
    mb.box_mm((DX0 + 0.2 + 7.4 - 0.45, PY, DZ + 0.02), (DX0 + 0.2 + 7.4 + 0.45, PY + 0.15, DZ + 0.025), "M_Wood",
              skip=("-z",))
    mb.box_mm((DX0 + 0.2 + 2.5, PY - 0.3, DZ + 0.9), (DX0 + 0.2 + 5.5, PY + 0.45, DZ + 0.97), "M_Wood")
    mb.box_mm((DX0 + 0.2 + 2.4, PY - 0.08, DZ + 2.1), (DX0 + 0.2 + 5.6, PY, DZ + 2.4), DOOR)  # menu header
    aset.text("CURRY  -  RICE  -  MISO", (DX0 + 0.2 + 4.0, PY - 0.11, DZ + 2.25), 0.0, size=0.14,
              color=(1.0, 0.95, 0.8))
    # kitchen
    mb.box_mm((16.4, 4.05, DZ), (18.2, 4.8, DZ + 0.88), "M_DarkMetal")
    mb.cylinder((17.3, 4.4, DZ + 0.88), 0.36, 0.5, "M_Metal", seg=14)
    mb.cylinder((17.3, 4.4, DZ + 1.38), 0.37, 0.04, "M_SliferCurry", seg=14)
    mb.box_mm((16.5, 3.9, DZ + 2.2), (18.1, 4.8, DZ + 2.55), "M_Metal")         # hood
    mb.cylinder((17.3, 4.4, DZ + 2.55), 0.13, 3.1, "M_DarkMetal", seg=10)       # stove pipe
    mb.cylinder((17.3, 4.4, DZ + 5.65), 0.22, 0.12, "M_DarkMetal", seg=10)
    mb.cone((17.3, 4.4, DZ + 5.85), 0.3, 0.22, "M_DarkMetal", seg=10)
    mb.box_mm((11.3, 4.3, DZ), (12.2, 4.8, DZ + 1.9), "M_WindowFrame")          # fridge
    mb.box_mm((12.5, 4.25, DZ), (15.8, 4.8, DZ + 0.9), "M_ShopShelf")           # worktop
    mb.box_mm((13.2, 4.3, DZ + 0.9), (14.0, 4.75, DZ + 0.92), "M_Metal")         # sink
    mb.box_mm((12.5, 4.55, DZ + 1.5), (14.9, 4.8, DZ + 1.55), "M_ShopShelf")    # shelf (clear of the window)
    for k, x in enumerate((12.8, 13.3, 13.9, 14.6)):
        mb.cylinder((x, 4.67, DZ + 1.55), 0.1, 0.2 + 0.05 * (k % 2), "M_WindowFrame" if k % 2 else "M_Metal", seg=8)
    aset.emitter("steam", (17.3, 4.4, DZ + 6.1), scale=0.6, rate=0.6)
    # hanging lamps (no collision)
    for ly in (-1.7, 1.0):
        nc.box((17.2, ly, DZ + DWH - 0.35), (0.02, 0.02, 0.7), "M_Black")
        nc.cone((17.2, ly, DZ + DWH - 0.95), 0.35, 0.3, TRIM, seg=12)
        nc.sphere((17.2, ly, DZ + DWH - 0.95), 0.13, "M_LampGlow", seg=8, rings=6)
    for ly in (-1.7, 1.0):
        aset.light((17.2, ly, DZ + DWH - 0.95), (1.0, 0.8, 0.55), 2500.0, 8.0, night_only=False)
    aset.light((17.3, 4.0, DZ + 2.4), (1.0, 0.85, 0.65), 2000.0, 5.0, night_only=False)
    _dining_detail(aset, mb, nc)


def _dining_detail(aset, mb, nc):
    """Detail + scale pass of the dining hall: a third table by the west window, settings on every table,
    tea station, TV corner, shoe rack + jackets at the door, posters, curtains; the galley kitchen behind
    the serving hatch gets pots, rice sacks, utensils, shelving and its own light. Real sizes."""
    DF = DZ + 0.02                        # finished floor (mb.room lays the floor 2 cm up)
    CE = DZ + DWH - 0.22                  # ceiling
    xi0, xi1, yi0, yi1 = DX0 + 0.2, DX1 - 0.2, DY0 + 0.2, DY1 - 0.2
    PY = 3.0
    r = random.Random(5)
    # ---- settings on the two long tables: cups, spoons, chopsticks, napkin box, sauce, water jug
    for ty in (-1.7, 1.0):
        for bx in (15.8, 16.9, 18.0):
            for s in (-1, 1):
                DT.mug(nc, bx + 0.22, ty + s * 0.3, DZ + 0.78, seed=int(bx * 10) + s)
                nc.box((bx - 0.2, ty + s * 0.27, DZ + 0.785), (0.02, 0.17, 0.008), "M_DetSilver")
                nc.box((bx - 0.25, ty + s * 0.27, DZ + 0.785), (0.012, 0.22, 0.008), K.WOOD)
        nc.box((17.45, ty, DZ + 0.83), (0.12, 0.08, 0.1), K.TRIM_WHITE)
        nc.cylinder((17.3, ty + 0.05, DZ + 0.78), 0.025, 0.12, "M_SliferCurry", seg=8)
        nc.cylinder((17.62, ty - 0.04, DZ + 0.78), 0.025, 0.12, K.BLACK, seg=8)
        aset.prop("SM_Int_Jug", (15.3, ty, DZ + 0.78), 30.0)
    # ---- third table (4 seats) by the west window
    with mb.at((12.7, 0.6, DF)):
        mb.box((0, 0, 0.74), (1.5, 0.8, 0.04), "M_Wood")
        for sx in (-1, 1):
            for sy in (-1, 1):
                mb.box((sx * 0.68, sy * 0.33, 0.36), (0.05, 0.05, 0.72), "M_DarkWood")
    for dx in (-0.38, 0.38):
        for s in (-1, 1):
            aset.prop("SM_Int_WoodChair", (12.7 + dx, 0.6 + s * 0.62, DF), 0.0 if s > 0 else 180.0)
    DT.table_set(nc, aset, 12.7, 0.6, DF + 0.76, 0.0, "dining", seats=4, seed=3, length=1.2)
    aset.prop("SM_Int_CeilingLamp", (12.7, 0.6, CE), 0.0)
    # ---- tea / water station (west wall, south of the window)
    mb.box_mm((xi0, -2.2, DF), (xi0 + 0.5, -0.9, DF + 0.85), K.WOOD)
    aset.prop("SM_Int_Kettle", (xi0 + 0.25, -1.85, DF + 0.85), 90.0)
    for k in range(6):
        nc.cylinder((xi0 + 0.15 + (k % 2) * 0.14, -1.45 + (k // 2) * 0.13, DF + 0.85), 0.035, 0.08,
                    DT.MUGS[k % 4], seg=8)
    nc.box((xi0 + 0.25, -1.0, DF + 0.9), (0.3, 0.12, 0.1), K.WOOD_DARK)         # chopstick box
    # ---- TV corner: low cabinet + TV against the partition, west of the hatch
    mb.box_mm((11.5, PY - 0.45, DF), (13.1, PY, DF + 0.55), K.WOOD_DARK)
    aset.prop("SM_Int_TV", (12.3, PY - 0.24, DF + 0.55), 0.0)
    _manga(nc, 11.75, PY - 0.22, DF + 0.55, 10.0, 7, 4)
    # ---- entrance: shoe rack, slippers, jackets on hooks, umbrella
    mb.box_mm((11.3, yi0, DF), (12.5, yi0 + 0.32, DF + 0.45), K.WOOD)
    mb.box_mm((11.3, yi0, DF + 0.22), (12.5, yi0 + 0.325, DF + 0.24), K.WOOD_DARK)
    for k in range(4):
        for lv in (0.0, 0.24):
            nc.box((11.45 + k * 0.28, yi0 + 0.17, DF + 0.03 + lv), (0.2, 0.26, 0.06),
                   r.choice(("M_IntFabricRed", "M_IntFabricWhite", K.BLACK, "M_SliferLaundryBlue")))
    DT.coat_hooks(nc, 11.9, yi0, DF + 1.75, 180.0, n=3, dorm="slifer", jackets=2, seed=8)
    nc.cylinder((14.6, yi0 + 0.2, DF), 0.12, 0.45, K.METAL, seg=10, cap_top=False)
    nc.beam((14.6, yi0 + 0.2, DF + 0.05), (14.66, yi0 + 0.26, DF + 0.8), 0.03, 0.03, "M_IntFabricRed")
    # ---- serving hatch: tray stack, rice cooker, bell, menu cards
    for k in range(7):
        nc.box((14.05, PY - 0.12, DZ + 0.98 + k * 0.02), (0.4, 0.3, 0.018), "M_IntFabricRed")
    nc.cylinder((16.2, PY + 0.1, DZ + 0.97), 0.17, 0.28, K.TRIM_WHITE, seg=12)
    nc.cylinder((16.2, PY + 0.1, DZ + 1.25), 0.14, 0.03, "M_IntSteelBlue", seg=12)
    nc.sphere((15.2, PY - 0.2, DZ + 0.975), 0.04, K.TRIM_GOLD, seg=8, rings=5, hemi=True)
    for k, t in enumerate(("CURRY 300", "RICE FREE", "MISO 100")):
        nc.box((14.9 + k * 0.5, PY - 0.17, DZ + 2.03), (0.42, 0.01, 0.12), "M_IntPaper")
    # ---- walls: posters, clock, calendar, curtains, wainscot
    K.poster(nc, aset, 14.9, yi0, DF + 1.6, 180.0, 0.55, 0.75, "M_IntPoster1", text="CURRY NIGHT", text_size=0.06)
    K.poster(nc, aset, xi1, 0.4, DF + 1.6, -90.0, 0.5, 0.7, "M_IntPoster2", text="SLIFER RED", text_size=0.06)
    K.poster(nc, aset, 17.4, PY, DF + 1.7, 0.0, 0.6, 0.45, "M_IntPoster4", text="DUEL AFTER DINNER", text_size=0.04)
    aset.prop("SM_Int_WallClock", (xi0, -0.6, DF + 2.3), 90.0)
    aset.prop("SM_Int_Frame", (xi0, 2.2, DF + 1.7), 90.0)
    K.wainscot(mb, (xi0, yi0), (xi1, yi0), DF, 0.85, "M_Wood", cap=K.TRIM_WOOD, gaps=[(13.5 - xi0 - 0.9, 13.5 - xi0 + 0.9)])
    K.wainscot(mb, (xi1, yi0), (xi1, PY), DF, 0.85, "M_Wood", cap=K.TRIM_WOOD)
    K.wainscot(mb, (xi0, PY), (xi0, yi0), DF, 0.85, "M_Wood", cap=K.TRIM_WOOD)
    K.wainscot(mb, (xi1, PY), (xi0, PY), DF, 0.85, "M_Wood", cap=K.TRIM_WOOD,
               gaps=[(xi1 - 18.6 - 0.55, xi1 - 18.6 + 0.55), (xi1 - 16.7, xi1 - 13.7)])
    for (p0, p1, c, w, z0, z1) in (((DX0, DY0), (DX1, DY0), 6.6, 2.8, 0.95, 2.35),
                                   ((DX1, DY0), (DX1, DY1), 2.0, 1.6, 1.0, 2.3),
                                   ((DX1, DY0), (DX1, DY1), 4.9, 1.6, 1.0, 2.3),
                                   ((DX0, DY1), (DX0, DY0), 4.5, 1.6, 1.0, 2.3)):
        K.curtains(nc, p0, p1, c, w, DZ + z0, DZ + z1, ("M_IntFabricRed", "M_SliferLaundryWhite")[int(c) % 2],
                   wall_thick=0.2)
    DT.dress_room(aset, mb, nc, xi0, yi0, xi1, PY, DF, CE, style="japanese", seed=40, ac=False,
                  keep_clear=[(xi0 - 0.1, -2.3, xi0 + 0.1, 2.5), (11.4, PY - 0.1, 17.9, PY + 0.1),
                              (xi1 - 0.1, -2.0, xi1 + 0.1, 2.8), (15.7, yi0 - 0.1, 19.6, yi0 + 0.1)])
    DT.floor_clutter(nc, aset, xi0, yi0, xi1, PY, DF, "dorm", n=2, seed=41,
                     clear=[(11.2, -2.6, 15.0, -1.6), (14.9, -2.8, 19.8, 2.0), (11.2, -0.3, 14.2, 1.6),
                            (11.2, 2.4, 17.0, 3.0), (11.2, -2.3, 11.8, -0.8), (17.8, 1.8, 19.8, 3.0)])
    # ---- galley kitchen behind the hatch
    ky0, ky1 = PY + 0.15, yi1
    for k, (x, a) in enumerate(((12.7, "SM_Int_Pot"), (13.6, "SM_Int_CuttingBoard"), (14.25, "SM_Int_EnamelPot"),
                                (15.45, "SM_Int_Bowl"))):
        aset.prop(a, (x, 4.52, DZ + 0.9), 15.0 * k)
    for k in range(5):                                                       # ladles on a rail over the stove
        nc.box((16.6 + k * 0.3, 4.77, DZ + 1.75), (0.03, 0.02, 0.3), K.METAL)
        nc.cylinder((16.6 + k * 0.3, 4.74, DZ + 1.55), 0.05, 0.03, K.METAL, seg=8)
    nc.box((17.2, 4.78, DZ + 1.92), (1.5, 0.02, 0.02), K.METAL)
    aset.prop("SM_Int_SteelShelves", (19.25, 4.5, DZ), 180.0)
    for k in range(3):                                                       # rice sacks (clear of the inner door swing)
        with nc.at((12.0 + (k % 2) * 0.1, 3.60 + k * 0.05, DZ + 0.12 + k * 0.2), rot=10.0 * k):
            nc.box((0, 0, 0), (0.55, 0.38, 0.2), "M_SliferLaundryWhite")
    nc.box((17.9, 4.048, DZ + 0.62), (0.3, 0.004, 0.12), "M_IntFabricRed")           # tea towel on the oven bar
    mb.box_mm((12.5, 4.45, DZ + 1.8), (14.9, 4.8, DZ + 2.45), K.TRIM_WHITE)          # upper cupboards
    for k in range(4):
        nc.box((12.8 + k * 0.6, 4.448, DZ + 2.12), (0.56, 0.004, 0.6), "M_IntTrimWhite")
        nc.box((13.0 + k * 0.6, 4.44, DZ + 1.9), (0.1, 0.02, 0.025), K.METAL)
    nc.box((15.3, 4.45, DZ + 0.006 + 0.02), (6.0, 0.55, 0.012), K.BLACK)               # rubber mat
    # partition (kitchen face): plate rack, pegboard with pans + utensils, a calendar
    mb.box_mm((11.4, ky0, DZ + 1.2), (13.5, ky0 + 0.3, DZ + 1.23), K.WOOD)
    mb.box_mm((11.4, ky0, DZ + 1.65), (13.5, ky0 + 0.3, DZ + 1.68), K.WOOD)
    for k in range(9):
        nc.cylinder((11.6 + k * 0.22, ky0 + 0.15, DZ + 1.23), 0.1, 0.012 * (2 + k % 3), K.TRIM_WHITE, seg=12)
        nc.cylinder((11.6 + k * 0.22, ky0 + 0.15, DZ + 1.68), 0.05, 0.1, DT.MUGS[k % 4], seg=8)
    nc.box((17.4, ky0 + 0.01, DZ + 1.65), (1.2, 0.02, 0.8), "M_IntCork")
    for k in range(4):
        nc.cylinder((16.95 + k * 0.3, ky0 + 0.06, DZ + 1.5), 0.13 - 0.015 * k, 0.03, K.METAL, seg=12) \
            if k % 2 else nc.box((16.95 + k * 0.3, ky0 + 0.04, DZ + 1.7), (0.05, 0.02, 0.35), K.WOOD_DARK)
    aset.prop("SM_Int_Bucket", (12.6, 3.5, DZ), 0.0)
    aset.prop("SM_Int_Broom", (11.4, 3.4, DZ), 90.0)
    K.panel_light(aset, nc, 15.75, (ky0 + ky1) / 2, CE, w=1.0, d=0.3, intensity=2400.0, radius=6.0)   # (between joists)
    DT.dress_room(aset, mb, nc, xi0, ky0, xi1, ky1, DF, CE, style="service", seed=42,
                  keep_clear=[(11.2, 4.2, 19.8, 4.8)] + [(x - 0.12, ky0, x + 0.12, ky1)      # (and the joists)
                                                         for x in (11.9, 13.75, 15.1, 16.4, 18.0, 19.3)])
    K.poster(nc, aset, 11.2, 3.95, DF + 1.6, 90.0, 0.4, 0.55, "M_IntPaper", text="WASH HANDS!",
             text_color=(0.6, 0.1, 0.05), text_size=0.04)
    # exposed ceiling joists (clear of the kitchen's ceiling vent at x 13.05-13.65 and its light panel)
    for x in (11.9, 13.75, 15.1, 16.4, 18.0, 19.3):
        mb.box_mm((x - 0.06, yi0, CE - 0.2), (x + 0.06, yi1, CE), "M_DarkWood")
    K.bulletin(nc, aset, 12.3, PY, DF + 1.3, 0.0, w=1.1, h=0.75, title="DORM NEWS", rng_seed=9)
    K.camera(aset, "dining", (11.6, -2.35, DF + 1.6), (18.0, 2.2, DF + 0.9), 16.0)
    K.camera(aset, "dining_kitchen", (17.9, 3.4, DF + 1.6), (11.8, 4.35, DF + 1.0), 16.0)


# ------------------------------------------------------------------ yard / site dressing
def _yard(aset, mb, nc):
    # laundry poles with clothes
    lx0, lx1, ly = -14.5, -8.5, -10.5
    for x in (lx0, lx1):
        mb.box((x, ly, -0.2), (0.5, 0.5, 0.5), CONC)
        mb.cylinder((x, ly, 0.0), 0.05, 2.3, "M_Metal", seg=8)
        mb.box((x, ly, 2.25), (0.06, 1.3, 0.06), "M_Metal")
    for dy in (-0.55, 0.55):
        nc.beam((lx0, ly + dy, 2.22), (lx1, ly + dy, 2.22), 0.015, 0.015, "M_Black")
    clothes = [  # (x, dy, w, h, mat)
        (-13.6, -0.55, 0.7, 0.75, "M_Jacket"), (-12.6, -0.55, 0.55, 0.65, "M_SliferLaundryWhite"),
        (-11.7, -0.55, 0.5, 0.9, "M_Pants"), (-10.6, -0.55, 0.6, 0.6, "M_SliferLaundryWhite"),
        (-9.5, -0.55, 0.25, 0.3, "M_SliferLaundryBlue"), (-9.1, -0.55, 0.25, 0.3, "M_SliferLaundryWhite"),
        (-13.0, 0.55, 1.1, 0.5, "M_SliferLaundryBlue"), (-11.4, 0.55, 0.7, 0.75, "M_Jacket"),
        (-10.0, 0.55, 0.9, 0.55, "M_SliferLaundryWhite"),
    ]
    for x, dy, w, h, mat in clothes:
        nc.box((x, ly + dy, 2.2 - h / 2), (w, 0.03, h), mat)
        if mat == "M_Jacket":
            nc.box((x, ly + dy, 2.2 - 0.18), (w + 0.5, 0.03, 0.3), mat)        # sleeves
    # standing sign board where the academy path arrives
    sx, sy = -3.6, 24.0
    mb.box((sx, sy, 1.75), (3.6, 0.14, 1.0), DOOR)
    mb.box((sx, sy, 2.32), (3.9, 0.2, 0.14), TRIM)
    mb.box((sx, sy, 1.18), (3.9, 0.2, 0.14), TRIM)
    for dx in (-1.85, 1.85):
        mb.box((sx + dx, sy, 1.15), (0.16, 0.16, 2.3), "M_Wood")
        mb.box((sx + dx, sy, -0.2), (0.4, 0.4, 0.4), CONC)
    mb.pyramid((sx, sy, 2.39), 4.2, 0.5, 0.35, ROOF)
    aset.text("SLIFER RED DORM", (sx, sy + 0.1, 1.72), 180.0, size=0.48, color=(1.0, 0.96, 0.86))
    aset.text("SLIFER RED DORM", (sx, sy - 0.1, 1.72), 0.0, size=0.48, color=(1.0, 0.96, 0.86))
    aset.interact("sign", (sx, sy + 0.8, 1.0), 180.0, title="Slifer Red Dorm",
                  text="Home of Duel Academy's newest - and most underestimated - duelists. "
                       "Cheap rooms, curry for dinner, and the best ocean view on the island.")
    # mailbox on a post by the sign
    mx, my = 0.2, 24.6
    mb.box((mx, my, 0.55), (0.1, 0.1, 1.1), "M_Wood")
    mb.box((mx, my, 1.25), (0.38, 0.5, 0.32), DOOR)
    with mb.at((mx, my, 1.41), rot_x=90):
        mb.cylinder((0, 0, -0.25), 0.19, 0.5, DOOR, seg=12)
    mb.box((mx, my + 0.26, 1.28), (0.2, 0.02, 0.04), "M_Black")
    mb.box((mx + 0.21, my, 1.45), (0.03, 0.05, 0.3), "M_Gold")
    # stepping stones: path arrival -> passage between buildings -> yard
    stones = []
    for k in range(14):
        t = k / 13
        stones.append((0.4 + (9.5 - 0.4) * t + math.sin(k * 1.7) * 0.25, 22.5 + (6.2 - 22.5) * t))
    for k in range(6):
        stones.append((9.5 + math.sin(k * 2.1) * 0.2, 4.8 - k * 1.25))
    for k in range(7):
        stones.append((-1.0 - k * 2.4 + math.sin(k) * 0.3, 7.0 + math.cos(k * 1.3) * 0.3))
    for k, (x, y) in enumerate(stones):
        r = 0.42 + 0.08 * math.sin(k * 2.3)
        mb.cylinder((x, y, -0.15), r, 0.2, CONC, seg=8, angle0=k * 0.4, smooth=False)
    # rain barrel under the back downpipe
    rb = (ROOF_X1 - 0.25, ROOF_YB + 0.75)
    mb.cylinder((rb[0], rb[1], 0.0), 0.38, 0.95, "M_Wood", seg=12, radius_top=0.34, cap_mat="M_DarkWood")
    for zz in (0.15, 0.75):
        mb.cylinder((rb[0], rb[1], zz), 0.39, 0.06, "M_DarkMetal", seg=12)
    # fishing rod leaning on the fence + bucket (no collision)
    nc.beam((-5.6, -21.6, 0.0), (-5.0, -22.05, 2.9), 0.03, 0.03, "M_DarkWood")
    nc.cylinder((-5.5, -21.68, 0.6), 0.05, 0.08, "M_Metal", seg=8)
    nc.beam((-5.0, -22.05, 2.9), (-4.7, -22.6, 1.0), 0.004, 0.004, "M_WindowFrame")
    mb.cylinder((-4.6, -21.3, 0.0), 0.2, 0.32, "M_SliferLaundryBlue", seg=10, radius_top=0.24)
    # small fire pit with log seats in the yard (students hang out here)
    fp = (2.0, -13.5)
    for k in range(9):
        a = k / 9 * math.tau
        mb.box((fp[0] + math.cos(a) * 0.75, fp[1] + math.sin(a) * 0.75, 0.1), (0.35, 0.3, 0.25), "M_Rock")
    mb.cylinder((fp[0], fp[1], -0.05), 0.6, 0.08, "M_DarkConcrete", seg=10)
    for a in (0.3, 2.4, 4.3):
        with mb.at((fp[0] + math.cos(a) * 2.2, fp[1] + math.sin(a) * 2.2, 0.24), rot=math.degrees(a) + 90, rot_y=90):
            mb.cylinder((0, 0, -0.75), 0.24, 1.5, "M_Bark", seg=10)
    nc.box((fp[0], fp[1], 0.15), (0.7, 0.1, 0.1), "M_DarkWood")
    nc.box((fp[0], fp[1], 0.15), (0.1, 0.7, 0.1), "M_DarkWood")


# ------------------------------------------------------------------ sockets (props, npc, audio)
def _sockets(aset):
    # fence along the cliff side, gap at x = 0
    for k in range(7):
        aset.prop("SM_Fence_Wood", (-3.5 - 4.0 * k, -22.0, 0.0), 0.0)
        aset.prop("SM_Fence_Wood", (3.5 + 4.0 * k, -22.0, 0.0), 0.0)
    aset.prop("SM_Bench", (-9.0, -19.6, 0.0), 0.0)
    aset.prop("SM_Bench", (8.0, -19.4, 0.0), 0.0)
    aset.prop("SM_VendingMachine", (10.5, -1.6, ZG - 0.25), -90.0)
    aset.prop("SM_TrashBin", (10.55, -0.35, 0.0), -90.0)
    aset.prop("SM_Crate", (21.2, 3.6, 0.0), 0.0)
    aset.prop("SM_Crate", (21.2, 2.3, 0.0), 8.0)
    aset.prop("SM_Crate", (21.25, 3.5, 1.2), -6.0, 0.85)
    aset.prop("SM_Barrel", (21.1, 0.9, 0.0), 0.0)
    aset.prop("SM_Crate", (-6.4, -20.6, 0.0), 12.0, 0.7)
    aset.prop("SM_PicnicTable", (16.0, -12.0, 0.0), 0.0)
    aset.prop("SM_DuelDummy", (-3.0, -15.5, 0.0), 180.0)
    aset.prop("SM_Flagpole_Red", (-25.0, -12.0, 0.0), 0.0)
    aset.prop("SM_LampPost", (3.2, 25.0, 0.0), 180.0)
    aset.prop("SM_LampPost", (-22.5, 3.0, 0.0), 90.0)
    aset.prop("SM_TrashBin", (-21.8, -6.6, 0.0), 0.0)
    # vegetation
    for a, p, yaw in (("SM_PalmTree_A", (-27.0, -18.5), 30), ("SM_PalmTree_B", (26.0, -19.0), 200),
                      ("SM_PalmTree_A", (25.5, 9.0), 120), ("SM_BroadTree_A", (-25.0, 17.0), 0),
                      ("SM_BroadTree_A", (22.0, 22.0), 90), ("SM_BroadTree_C", (-13.0, 21.0), 0),
                      ("SM_BroadTree_C", (13.0, 15.0), 45)):
        aset.prop(a, (p[0], p[1], 0.0), yaw)
    for a, p in (("SM_Bush_A", (-21.5, 7.5)), ("SM_Bush_B", (-10.0, 6.4)), ("SM_Bush_B", (-3.0, 6.3)),
                 ("SM_Bush_A", (12.0, 6.8)), ("SM_FlowerBush_Red", (21.0, -5.2)),
                 ("SM_FlowerBush_Red", (11.2, -7.6)), ("SM_FlowerBush_Yellow", (-22.6, -2.8)),
                 ("SM_GrassClump_A", (-17.0, -21.0)), ("SM_GrassClump_A", (12.5, -21.2)),
                 ("SM_GrassClump_A", (20.0, -21.0)), ("SM_Rock_A", (-28.0, -9.0)), ("SM_Rock_B", (27.0, -4.0)),
                 ("SM_Fern_A", (7.2, 6.4)), ("SM_GrassClump_A", (-24.0, -21.3))):
        aset.prop(a, (p[0], p[1], 0.0), (p[0] * 37) % 360)
    # people + ambience
    aset.npc((-6.5, -13.0, 0.0), 0.0, dorm="slifer", wander=6.0)
    aset.npc((14.5, -9.0, 0.0), 160.0, dorm="slifer", wander=5.0)
    aset.npc((-4.0, 9.5, 0.0), 200.0, dorm="slifer", wander=8.0)
    aset.audio("A_Ocean", (0.0, -24.0, 0.0), radius=60.0)
    aset.audio("A_Wind", (0.0, -2.0, 7.0), radius=35.0, volume=0.5)
    aset.special("camera", (-24.0, -20.0, 1.7), target=(-5.0, -2.0, 3.0), lens=24.0)


def build():
    aset = AssetSet("slifer")
    main = aset.mesh("Slifer_Main")
    din = aset.mesh("Slifer_Dining")
    yard = aset.mesh("Slifer_Yard")
    nc = aset.mesh("Slifer_NoCol")
    inner = aset.mesh("Slifer_Interior")
    inner_nc = aset.mesh("Slifer_Interior_NoCol")
    _main_block(aset, main, nc)
    _rooms(aset, inner, inner_nc)
    _dining(aset, din, nc)
    _yard(aset, yard, nc)
    _sockets(aset)
    return aset


PLACEMENTS = {"slifer": with_travel(build, [
    ("dining", "slifer_dining", "Slifer Dining Hall", "Rice, sardines and Professor Banner's cat. The heart of Slifer Red."),
])}
