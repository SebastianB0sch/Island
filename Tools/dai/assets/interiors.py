"""
Procedural interior cells for the GBA story locations.

Each cell is built in **local metres** with:
    origin = centre of the floor
    floor  = z 0
    front  = +Y (the door is on the +Y wall; the Layout converts local +Y to
             Unreal -Y, which is the north edge of the cell bounds)

`Tools/dai/layout.py::Layout.place_interiors()` reads
`Content/Data/World/interiors.json`, calls `build_cell()` for every row and
places the returned AssetSet at the cell's `origin_ue`.  Nothing here is
hand-placed: dimensions, props and lights are derived from the cell data.

The generated meshes are named
    Interior_<cell_id>_Shell   (architecture, complex collision)
    Interior_<cell_id>_Props   (furniture, complex collision)
    Interior_<cell_id>_NoCol   (glass, glow, banners, posters - no collision)
and exported under Meshes/Locations/interiors.
"""

import math

from . import AssetSet
from . import interior as _K  # noqa: F401  (registers the M_Int* palette used by the cork boards)

# --------------------------------------------------------------------------- themes
def _theme(cell):
    cid = str(cell.get("id", ""))
    if cid.startswith("slifer"):
        return dict(wall="M_SliferWall", inner="M_CreamWall", trim="M_SliferTrim", floor="M_Wood",
                    ceiling="M_CreamWall", door="M_SliferDoor", stone="M_Concrete", glass="M_ShojiPaper",
                    fabric="M_Carpet", wood="M_Wood", dark="M_DarkWood", metal="M_DarkMetal",
                    gold="M_Gold", accent="M_SliferTrim", paper="M_ShojiPaper", glow="M_LampGlow")
    if cid.startswith("ra"):
        return dict(wall="M_RaWall", inner="M_CreamWall", trim="M_RaTrim", floor="M_Wood",
                    ceiling="M_CreamWall", door="M_DarkWood", stone="M_Concrete", glass="M_ShojiPaper",
                    fabric="M_Carpet", wood="M_Wood", dark="M_DarkWood", metal="M_DarkMetal",
                    gold="M_Gold", accent="M_RaTrim", paper="M_ShojiPaper", glow="M_LampGlow")
    if cid.startswith("obelisk"):
        return dict(wall="M_ObeliskWall", inner="M_ObeliskWall", trim="M_ObeliskTrim", floor="M_MarbleFloor",
                    ceiling="M_Marble", door="M_ObeliskTrim", stone="M_Marble", glass="M_Glass",
                    fabric="M_Carpet", wood="M_DarkWood", dark="M_DarkWood", metal="M_DarkMetal",
                    gold="M_Gold", accent="M_ObeliskTrim", paper="M_ShojiPaper", glow="M_LampGlow")
    return dict(wall="M_AcademyWall", inner="M_WhiteWall", trim="M_AcademyBlue", floor="M_MarbleFloor",
                ceiling="M_WhiteWall", door="M_AcademyBlue", stone="M_Concrete", glass="M_Glass",
                fabric="M_Carpet", wood="M_Wood", dark="M_DarkWood", metal="M_DarkMetal",
                gold="M_Gold", accent="M_AcademyBlue", paper="M_ShojiPaper", glow="M_LampGlow")


def _dims(cell):
    size = cell.get("size_m") or [6.0, 5.0, 3.2]
    w, d, h = (float(size[0]), float(size[1]), float(size[2]))
    return max(w, 3.0), max(d, 3.0), max(h, 2.6)


def _at(mb, x, y, yaw=0.0, z=0.0):
    return mb.at((x, y, z), rot=yaw)


# --------------------------------------------------------------------------- architecture
WT = 0.18            # wall thickness: the walls stand INSIDE the footprint, so the room's faces are at +-(w/2 - WT)
FZ = 0.02            # finished floor (the floor polygon); furniture stands on it, not on the slab under it
DOUBLE_DOOR = {"classroom", "exam", "dining"}


def _door_spec(cell):
    """(clear width, clear height, double, leaf style) of the cell's door: a 1.0 x 2.15 m single leaf, or a
    1.8 x 2.25 m pair for the big rooms - the same sizes as the doors of the in-place academy rooms."""
    w, d, h = _dims(cell)
    cid = str(cell.get("id", ""))
    style = ("slifer_inner" if cid.startswith("slifer") else "ra_inner" if cid.startswith("ra")
             else "obelisk_inner" if cid.startswith("obelisk") else "academy_wood")
    if str(cell.get("kind", "")) in DOUBLE_DOOR and w >= 8.0:
        return 1.8, min(2.25, h - 0.5), True, style
    return 1.0, min(2.15, h - 0.5), False, style


def _faces(cell):
    w, d, h = _dims(cell)
    return -w / 2.0 + WT, -d / 2.0 + WT, w / 2.0 - WT, d / 2.0 - WT


FURNISHED_WALLS = {"office", "headmaster_room"}     # book cases / cabinets stand on the back half of the side walls


# rooms whose furniture needs particular wall spans (Jaden's triple bunk fills the back-left corner)
WINDOW_SLOTS = {"slifer_jaden_room": [0.9]}


def _window_slots(cell):
    """Y centres of the side-wall window panels. Offices keep the back half of their side walls for the book
    cases and cabinets, so their windows are only in the door half."""
    w, d, h = _dims(cell)
    if cell.get("id") in WINDOW_SLOTS:
        return WINDOW_SLOTS[cell["id"]]
    if str(cell.get("kind", "")) in FURNISHED_WALLS:
        n = max(1, int(d / 2.0 / 3.2))
        return [(i + 0.5) * (d / 2.0 / n) for i in range(n)]
    n = max(1, int(w / 3.2))
    return [(i + 0.5) * (d / n) - d / 2.0 for i in range(n)]


def _room_shell(shell, nocol, cell, theme):
    from . import doors as DR
    w, d, h = _dims(cell)
    x0, x1 = -w / 2.0, w / 2.0
    y0, y1 = -d / 2.0, d / 2.0
    fx0, fy0, fx1, fy1 = _faces(cell)
    door_w, door_h, double, style = _door_spec(cell)

    # foundation / floor slab (collision top exactly at the visual floor)
    shell.box_mm((x0 - 0.18, y0 - 0.18, -0.28), (x1 + 0.18, y1 + 0.18, FZ - 0.002), theme["stone"])
    # room shell: walls, floor and ceiling.  Edge 2 is the +Y wall (door wall).
    footprint = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    door_opening = dict(u=w / 2.0, w=door_w, z0=0.0, z1=door_h)
    shell.room(footprint, 0.0, h, WT, theme["wall"], openings={2: [door_opening]},
               floor_mat=theme["floor"], ceil_mat=theme["ceiling"], inner_mat=theme["inner"])
    # ceiling slab above the ceiling polygon, so the cell is closed from above
    shell.box_mm((x0 - 0.18, y0 - 0.18, h + 0.005), (x1 + 0.18, y1 + 0.18, h + 0.22), theme["ceiling"])

    # door: reveal linings, an architrave round the opening on the room face and the leaf (or the pair of
    # leaves) closed on the wall's middle plane, filling the opening. The portal trigger behind it is what
    # takes the player out; the leaf is the same mesh the automatic doors use (assets/doors.py).
    hw = door_w / 2.0
    for sx in (-1, 1):
        shell.box((sx * (hw - 0.0025), y1 - WT / 2.0, door_h / 2.0), (0.005, WT, door_h), theme["trim"])
    shell.box((0.0, y1 - WT / 2.0, door_h - 0.0025), (door_w, WT, 0.005), theme["trim"])
    bw = 0.09
    ya = fy1 - 0.015
    for sx in (-1, 1):
        shell.box((sx * (hw + bw / 2.0), ya, FZ + (door_h + bw - FZ) / 2.0), (bw, 0.03, door_h + bw - FZ), theme["trim"])
    shell.box((0.0, ya, door_h + bw / 2.0), (door_w + 2 * bw, 0.03, bw), theme["trim"])
    lw = door_w / 2.0 if double else door_w
    leaf = DR.build_leaf(style, lw, door_h - FZ)
    ym = y1 - WT / 2.0
    # leaf mesh: pivot at the hinge, leaf along +X, outside face -Y. Rotated 180 deg its outside faces +Y
    # (the corridor side of the cell door) and it runs from the hinge at +hw towards -X.
    shell.extend(leaf, offset=(hw, ym, FZ), rot=180.0)
    if double:
        shell.extend(leaf, offset=(-hw, ym, FZ), rot=0.0)
    # small step outside the door, visible from the cell exit trigger
    shell.box_mm((-hw - 0.18, y1 + 0.02, -0.12), (hw + 0.18, y1 + 0.52, 0.06), theme["stone"])

    # skirting and crown moulding on the room faces (the skirting stops at the architrave)
    def run(a, b, z, t, hgt):
        shell.beam((a[0], a[1], z), (b[0], b[1], z), t, hgt, theme["trim"])
    for a, b in (((fx0, fy0 + 0.025), (fx1, fy0 + 0.025)), ((fx0 + 0.025, fy0), (fx0 + 0.025, fy1)),
                 ((fx1 - 0.025, fy0), (fx1 - 0.025, fy1))):
        run(a, b, FZ + 0.06, 0.05, 0.12)
    gap = hw + bw
    for a, b in (((fx0, fy1 - 0.025), (-gap, fy1 - 0.025)), ((gap, fy1 - 0.025), (fx1, fy1 - 0.025))):
        run(a, b, FZ + 0.06, 0.05, 0.12)
    for a, b in (((fx0, fy0 + 0.045), (fx1, fy0 + 0.045)), ((fx1 - 0.045, fy0), (fx1 - 0.045, fy1)),
                 ((fx1, fy1 - 0.045), (fx0, fy1 - 0.045)), ((fx0 + 0.045, fy1), (fx0 + 0.045, fy0))):
        run(a, b, h - 0.08, 0.09, 0.16)

    # side windows (paper/glass panels + frames) - interiors are below the island, so these are lit panels
    # on the wall faces, not real openings
    for sx in (-1, 1):
        for yy in _window_slots(cell):
            fx = sx * (w / 2.0 - WT)
            xg, xf = fx - sx * 0.02, fx - sx * 0.045
            nocol.box((xg, yy, 1.72), (0.035, 1.05, 1.22), theme["glass"])
            shell.box((xf, yy, 1.10), (0.09, 1.20, 0.07), theme["trim"])
            shell.box((xf, yy, 2.33), (0.09, 1.20, 0.07), theme["trim"])
            shell.box((xf, yy - 0.565, 1.715), (0.09, 0.07, 1.16), theme["trim"])
            shell.box((xf, yy + 0.565, 1.715), (0.09, 0.07, 1.16), theme["trim"])
            shell.box((fx - sx * 0.035, yy, 1.715), (0.07, 0.04, 1.16), theme["trim"])      # mullion
            shell.box((fx - sx * 0.035, yy, 1.72), (0.07, 1.06, 0.04), theme["trim"])       # transom

    # ceiling beams for scale / lighting bounce (flush with the ceiling, face to face)
    for i in range(1, max(2, int(d / 2.8))):
        yy = -d / 2.0 + i * d / max(2, int(d / 2.8))
        shell.box((0.0, yy, h - 0.08), (w - 2 * WT, 0.14, 0.16), theme["trim"])

    # room sign above the door, on the wall face, facing into the room
    aset_text = cell.get("_aset_text")
    if aset_text:
        aset_text(cell.get("display_name", "Room"), (0.0, fy1 - 0.02, door_h + bw + 0.22), 0.0,
                  size=0.16, color=(1.0, 0.96, 0.88))


def _ceiling_lamp(props, nocol, aset, x, y, h, theme, radius, intensity=7000.0, shadows=False, drop=0.35):
    """Pendant lamp hung from the ceiling at height h: canopy on the ceiling, stem, shade and glowing
    diffuser; the light sits just under the diffuser. (Called inside the room builder, which is lifted by
    FZ onto the finished floor: the geometry is offset back so it hangs from the real ceiling.)"""
    g = h - FZ
    props.cylinder((x, y, g - 0.03), 0.12, 0.03, theme["metal"], seg=12)
    props.cylinder((x, y, g - drop + 0.05), 0.015, drop - 0.08, theme["metal"], seg=6)
    props.cylinder((x, y, g - drop), 0.34, 0.05, theme["metal"], seg=12)
    nocol.cylinder((x, y, g - drop - 0.12), 0.30, 0.12, theme["glow"], seg=12, cap_top=False)
    aset.light((x, y, h - drop - 0.18), (1.0, 0.86, 0.66), intensity, radius, shadows=shadows)


# --------------------------------------------------------------------------- furniture
def _desk(props, x, y, yaw=0.0, w=1.4, d=0.68, h=0.74, theme=None):
    """Desk with the sitter on local +Y (the modesty panel is on the front, local -Y)."""
    theme = theme or {}
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, h - 0.035), (w, d, 0.07), theme.get("dark", "M_DarkWood"))
        for sx in (-1, 1):
            for sy in (-1, 1):
                props.box((sx * (w / 2.0 - 0.09), sy * (d / 2.0 - 0.08), (h - 0.07) / 2.0),
                          (0.07, 0.07, h - 0.07), theme.get("wood", "M_Wood"))
        props.box((0.0, -d / 2.0 + 0.05, h - 0.07 - h * 0.26), (w - 0.25, 0.04, h * 0.52),
                  theme.get("wood", "M_Wood"))


def _chair(props, x, y, yaw=0.0, theme=None):
    """Chair: the sitter faces local -Y (the back rest is on local +Y)."""
    theme = theme or {}
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, 0.45), (0.50, 0.50, 0.06), theme.get("wood", "M_Wood"))
        props.box((0.0, 0.22, 0.75), (0.50, 0.06, 0.54), theme.get("wood", "M_Wood"))
        for sx in (-1, 1):
            for sy in (-1, 1):
                props.box((sx * 0.20, sy * 0.20, 0.21), (0.05, 0.05, 0.42),
                          theme.get("dark", "M_DarkWood"))


def _bed(props, x, y, yaw=0.0, theme=None, z=0.0, single=True):
    """Bed with the head board on local +Y (put that against a wall)."""
    theme = theme or {}
    w = 1.05 if single else 1.45
    with _at(props, x, y, yaw, z):
        props.box((0.0, 0.0, 0.155), (w + 0.12, 2.05, 0.31), theme.get("dark", "M_DarkWood"))
        props.box((0.0, 0.0, 0.38), (w, 1.92, 0.20), "M_Fabric")
        props.box((0.0, 0.70, 0.52), (w * 0.62, 0.34, 0.08), "M_WhiteWall")
        props.box((0.0, -0.35, 0.51), (w * 0.96, 1.00, 0.06), theme.get("accent", "M_AcademyBlue"))
        props.box((0.0, 1.065, 0.53), (w + 0.12, 0.08, 1.06), theme.get("wood", "M_Wood"))


def _bunk(props, x, y, yaw=0.0, theme=None):
    theme = theme or {}
    _bed(props, x, y, yaw, theme, z=0.0, single=True)
    _bed(props, x, y, yaw, theme, z=1.35, single=True)
    with _at(props, x, y, yaw):
        for sx in (-1, 1):
            props.box((sx * 0.62, 0.95, 0.95), (0.08, 0.08, 1.90), theme.get("dark", "M_DarkWood"))
            props.box((sx * 0.62, -0.95, 0.95), (0.08, 0.08, 1.90), theme.get("dark", "M_DarkWood"))
        for z in (0.55, 1.15, 1.75):
            props.box((0.70, 0.55, z), (0.06, 0.55, 0.06), theme.get("metal", "M_DarkMetal"))


def _wardrobe(props, x, y, yaw=0.0, theme=None):
    """Wardrobe 1.15 x 0.60 m, doors on local +Y."""
    theme = theme or {}
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, 1.05), (1.15, 0.60, 2.10), theme.get("wood", "M_Wood"))
        props.box((0.0, 0.305, 1.05), (0.02, 0.01, 2.00), theme.get("dark", "M_DarkWood"))
        props.box((0.05, 0.315, 1.10), (0.03, 0.03, 0.16), theme.get("gold", "M_Gold"))
        props.box((-0.05, 0.315, 1.10), (0.03, 0.03, 0.16), theme.get("gold", "M_Gold"))


def _bookshelf(props, x, y, yaw=0.0, theme=None, w=1.80, depth=0.34, seed=0):
    """Open book case w x depth x 2.1 m, open side on local -Y (back on +Y: put that against a wall); the
    books stand on the shelves."""
    theme = theme or {}
    wood, dark = theme.get("wood", "M_Wood"), theme.get("dark", "M_DarkWood")
    t = 0.03
    with _at(props, x, y, yaw):
        props.box((0.0, depth / 2.0 - 0.01, 1.05), (w, 0.02, 2.10), wood)                    # back
        for sx in (-1, 1):
            props.box((sx * (w / 2.0 - t / 2.0), 0.0, 1.05), (t, depth, 2.10), wood)          # sides
        levels = (0.0, 0.5, 1.0, 1.5, 2.07)
        for z in levels:
            props.box((0.0, 0.0, z + t / 2.0), (w - 2 * t, depth - 0.02, t), dark)           # bottom/shelves/top
        cols = ("M_AcademyRed", "M_AcademyBlue", "M_AcademyYellow")
        n = int((w - 2 * t) / 0.11)
        for j, z in enumerate(levels[:-1]):
            zb = z + t
            for i in range(n):
                if (i * 7 + j * 3 + seed) % 5 == 0:
                    continue
                bh = 0.22 + 0.04 * ((i + j) % 3)
                props.box((-w / 2.0 + t + 0.055 + i * 0.11, -0.01, zb + bh / 2.0), (0.09, depth - 0.1, bh),
                          cols[(i + j) % 3])


def _blackboard(props, x, face_y, z, width, height, theme):
    """Chalk board on the -Y wall: its back on the wall face at face_y, the board facing +Y (the room)."""
    gold = theme.get("gold", "M_Gold")
    props.box_mm((x - width / 2.0, face_y, z - height / 2.0), (x + width / 2.0, face_y + 0.03, z + height / 2.0),
                 "M_DarkWood")
    props.box_mm((x - width / 2.0 + 0.08, face_y + 0.03, z - height / 2.0 + 0.06),
                 (x + width / 2.0 - 0.08, face_y + 0.035, z + height / 2.0 - 0.06), "M_Black")
    for zz in (z + height / 2.0 + 0.04, z - height / 2.0 - 0.04):
        props.box_mm((x - width / 2.0 - 0.08, face_y, zz - 0.04), (x + width / 2.0 + 0.08, face_y + 0.05, zz + 0.04), gold)
    for sx in (-1, 1):
        xx = x + sx * (width / 2.0 + 0.04)
        props.box_mm((xx - 0.04, face_y, z - height / 2.0), (xx + 0.04, face_y + 0.05, z + height / 2.0), gold)
    props.box_mm((x - width * 0.3, face_y, z - height / 2.0 - 0.14), (x + width * 0.3, face_y + 0.1, z - height / 2.0 - 0.1),
                 theme.get("trim", "M_WhiteWall"))                                           # chalk tray


def _clock(props, x, face_y, z, theme, side=1):
    """Wall clock on a Y wall face (side=+1: the -Y wall, facing +Y)."""
    with props.at((x, face_y, z), rot_x=-90.0 * side):
        props.cylinder((0, 0, 0), 0.30, 0.05, theme.get("gold", "M_Gold"), seg=24)
        props.cylinder((0, 0, 0.05), 0.25, 0.01, "M_WhiteWall", seg=24)
    yh = face_y + side * 0.065
    props.box((x, yh, z + 0.08), (0.025, 0.008, 0.16), "M_Black")
    props.box((x + 0.06, yh, z), (0.12, 0.008, 0.02), "M_Black")


def _rug(props, x, y, w, d, theme):
    props.box((x, y, 0.0125), (w, d, 0.025), theme.get("fabric", "M_Carpet"))


def _sofa(props, x, y, yaw=0.0, theme=None):
    theme = theme or {}
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, 0.26), (2.0, 0.82, 0.52), theme.get("fabric", "M_Carpet"))
        props.box((0.0, 0.34, 0.68), (2.0, 0.16, 0.65), theme.get("fabric", "M_Carpet"))
        for sx in (-1, 1):
            props.box((sx * 1.02, 0.0, 0.33), (0.16, 0.84, 0.66), theme.get("fabric", "M_Carpet"))


def _long_table(props, x, y, w, d, theme):
    props.box((x, y, 0.72), (w, d, 0.08), theme.get("dark", "M_DarkWood"))
    for sx in (-1, 1):
        for sy in (-1, 1):
            props.box((x + sx * (w / 2.0 - 0.25), y + sy * (d / 2.0 - 0.18), 0.34),
                      (0.12, 0.12, 0.68), theme.get("wood", "M_Wood"))


def _sideboard(props, x, y, w, theme, yaw=0.0):
    """Sideboard w x 0.55 m, the front (handles) on local -Y."""
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, 0.48), (w, 0.55, 0.96), theme.get("wood", "M_Wood"))
        props.box((0.0, 0.0, 0.99), (w + 0.06, 0.60, 0.06), theme.get("dark", "M_DarkWood"))
        for i in range(3):
            props.box((-w / 3.0 + i * w / 3.0, -0.285, 0.55), (0.04, 0.02, 0.30), theme.get("gold", "M_Gold"))


def _vitrine(props, nocol, x, y, w, theme, yaw=0.0, trophies=True):
    """Glass display cabinet w x 0.5 x 1.9 m (front on local -Y) with trophies / card cases on glass shelves."""
    gold = theme.get("gold", "M_Gold")
    with _at(props, x, y, yaw), _at(nocol, x, y, yaw):
        props.box((0.0, 0.0, 0.25), (w, 0.5, 0.5), theme.get("dark", "M_DarkWood"))           # plinth
        props.box((0.0, 0.0, 1.875), (w, 0.5, 0.05), theme.get("dark", "M_DarkWood"))         # top
        for sx in (-1, 1):
            props.box((sx * (w / 2.0 - 0.025), 0.0, 1.175), (0.05, 0.5, 1.35), theme.get("dark", "M_DarkWood"))
        props.box((0.0, 0.23, 1.175), (w - 0.1, 0.04, 1.35), theme.get("wood", "M_Wood"))       # back
        nocol.box((0.0, -0.235, 1.175), (w - 0.1, 0.01, 1.35), "M_GlassClear")
        for z in (0.95, 1.4):
            nocol.box((0.0, 0.0, z), (w - 0.1, 0.42, 0.01), "M_GlassClear")
        for k, z in enumerate((0.5, 0.955, 1.405)):
            for i in range(3):
                xx = -w / 2.0 + (i + 0.5) * w / 3.0
                if trophies and (i + k) % 2 == 0:
                    props.cylinder((xx, 0.0, z), 0.06, 0.03, gold, seg=10)
                    props.cylinder((xx, 0.0, z + 0.03), 0.02, 0.12, gold, seg=8)
                    props.cylinder((xx, 0.0, z + 0.15), 0.07, 0.12, gold, seg=12, radius_top=0.1)
                else:
                    props.box((xx, 0.0, z + 0.11), (0.18, 0.04, 0.22), theme.get("accent", "M_AcademyBlue"))


def _globe(props, x, y, theme):
    props.cylinder((x, y, 0.0), 0.22, 0.04, theme.get("dark", "M_DarkWood"), seg=12)
    props.cylinder((x, y, 0.04), 0.03, 0.72, theme.get("dark", "M_DarkWood"), seg=8)
    props.torus((x, y, 1.0), 0.27, 0.015, theme.get("gold", "M_Gold"), seg=20, tube_seg=4)
    props.sphere((x, y, 1.0), 0.25, "M_AcademyBlue", seg=16, rings=10)


def _notice_board(props, nocol, x, face_y, z, w, hgt, theme, side=1):
    """Cork notice board with pinned sheets on a Y wall face (side=+1: the -Y wall, facing +Y)."""
    y = face_y + side * 0.0125
    props.box((x, y, z), (w + 0.08, 0.025, hgt + 0.08), theme.get("dark", "M_DarkWood"))
    nocol.box((x, face_y + side * 0.026, z), (w, 0.003, hgt), "M_IntCork")
    for i in range(4):
        nocol.box((x - w * 0.36 + i * w * 0.24, face_y + side * 0.029, z + (0.12 if i % 2 else -0.08)),
                  (w * 0.18, 0.003, hgt * 0.42), theme.get("paper", "M_ShojiPaper"))


def _tank(props, nocol, aset, x, y, theme):
    props.box((x, y, 0.36), (1.20, 0.72, 0.72), theme.get("dark", "M_DarkWood"))
    nocol.box((x, y, 1.12), (1.08, 0.60, 0.80), "M_GlassClear")
    props.box((x, y, 1.565), (1.22, 0.74, 0.09), theme.get("metal", "M_DarkMetal"))
    nocol.box((x, y, 1.35), (0.70, 0.02, 0.06), theme.get("glow", "M_LampGlow"))
    aset.light((x, y, 1.35), (0.55, 0.85, 1.0), 1800.0, 3.0)


def _poster(nocol, x, face_y, z, w, h, theme, side=1):
    nocol.box((x, face_y + side * 0.006, z), (w, 0.012, h), theme.get("paper", "M_ShojiPaper"))
    nocol.box((x, face_y + side * 0.014, z), (w * 0.55, 0.004, h * 0.35), theme.get("accent", "M_AcademyBlue"))


def _banner(nocol, x, face_y, z, w, h, mat, side=1):
    nocol.box((x, face_y + side * 0.03, z), (w, 0.012, h), mat)
    nocol.box((x, face_y + side * 0.03, z + h / 2.0 + 0.03), (w + 0.12, 0.04, 0.04), "M_Gold")      # rod
    for sx in (-1, 1):
        nocol.box((x + sx * (w / 2.0 + 0.03), face_y + side * 0.012, z + h / 2.0 + 0.03), (0.03, 0.024, 0.06), "M_Gold")


def _trunk(props, x, y, theme):
    props.box((x, y, 0.29), (0.90, 0.55, 0.58), theme.get("dark", "M_DarkWood"))
    props.box((x, y, 0.61), (0.94, 0.59, 0.06), theme.get("gold", "M_Gold"))
    props.box((x, y - 0.285, 0.38), (0.12, 0.02, 0.14), theme.get("gold", "M_Gold"))


def _crest(nocol, props, x, face_y, z, theme):
    """Academy crest on the -Y wall face (facing +Y) with a light strip under it."""
    with props.at((x, face_y, z), rot_x=-90.0):
        props.cylinder((0, 0, 0), 0.85, 0.08, theme.get("gold", "M_Gold"), seg=24)
        props.cylinder((0, 0, 0.08), 0.72, 0.02, theme.get("accent", "M_AcademyBlue"), seg=24)
    props.box((x, face_y + 0.015, z - 1.05), (1.1, 0.03, 0.16), theme.get("gold", "M_Gold"))         # name plate


# --------------------------------------------------------------------------- room contents
# Every room keeps the door zone clear (1.2 m in front of the door), aisles of at least 0.8 m between desk
# columns (the 0.76 m player capsule fits) and its NPC marks (anchors.json) free of furniture.
def _front(props, nocol, aset, cell, theme, desk_w, board_w, board_h, chair_x=-0.35):
    """Front of a class / exam room: blackboard, clock, teacher's desk with the chair between the desk and the
    board (the teacher faces the class)."""
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    _blackboard(props, 0.0, fy0, 1.5, board_w, board_h, theme)
    _clock(props, 0.0, fy0, min(h - 0.5, 1.5 + board_h / 2.0 + 0.55), theme)
    _desk(props, 0.0, fy0 + 1.25, 180.0, desk_w, 0.72, 0.76, theme)
    _chair(props, chair_x, fy0 + 0.72, 180.0, theme)
    return fy0 + 1.25 + 0.36                       # front edge of the teacher's desk


def _desk_grid(props, theme, xs, ys, dw, dd):
    for y in ys:
        for x in xs:
            _desk(props, x, y, 0.0, dw, dd, 0.72, theme)
            _chair(props, x, y + dd / 2.0 + 0.22, 0.0, theme)


def _classroom(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    _front(props, nocol, aset, cell, theme, 1.8, min(6.0, w - 3.0), 1.35)
    for sx in (-1, 1):
        _banner(nocol, sx * 4.6, fy0, h - 1.3, 1.2, 2.0, "M_AcademyRed" if sx < 0 else "M_AcademyBlue")
    # 6 x 5 double-width student desks (1.1 m): 1.07 m aisles; 1.15 m row pitch
    dw, dd = 1.1, 0.56
    xs = [-w / 2.0 + 1.55 + c * (w - 3.1) / 5 for c in range(6)]
    ys = [fy0 + 2.95 + r * 1.15 for r in range(5)]
    _desk_grid(props, theme, xs, ys, dw, dd)
    _notice_board(props, nocol, -2.6, fy1, 1.55, 1.8, 0.9, theme, side=-1)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h, theme, max(w, d) * 0.62, 7800.0, True)
    aset.light((0.0, fy0 + 1.6, h - 0.65), (1.0, 0.92, 0.80), 3600.0, max(w, d) * 0.45)


def _exam(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    _front(props, nocol, aset, cell, theme, 1.7, min(5.0, w - 3.0), 1.15, chair_x=0.35)
    # 6 x 4 single exam desks (0.95 m): 0.87 m aisles
    dw, dd = 0.95, 0.56
    xs = [-w / 2.0 + 1.45 + c * (w - 2.9) / 5 for c in range(6)]
    ys = [fy0 + 2.85 + r * 1.1 for r in range(4)]
    _desk_grid(props, theme, xs, ys, dw, dd)
    _notice_board(props, nocol, 2.6, fy1, 1.55, 1.6, 0.9, theme, side=-1)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h, theme, max(w, d) * 0.62, 7000.0, True)


def _office(props, nocol, aset, cell, theme, desk_y=1.75, guests=(-0.9, 0.9)):
    """Office: the desk faces the door, the owner's chair behind it (wall side), guest chairs in front."""
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    yd = fy0 + desk_y
    _desk(props, 0.0, yd, 180.0, min(2.6, w - 2.5), 0.85, 0.78, theme)
    _chair(props, -0.35, yd - 0.85, 180.0, theme)
    for gx in guests:
        _chair(props, gx, yd + 0.95, 0.0, theme)
    _bookshelf(props, fx0 + 0.17, -d / 4.0, 90.0, theme)
    _rug(props, 0.0, 0.0, min(4.0, w - 2.0), min(2.6, d - 2.0), theme)
    _crest(nocol, props, 0.0, fy0, h - 0.95, theme)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h, theme, max(w, d) * 0.60, 6200.0, True)
    aset.light((0.0, yd, h - 0.65), (1.0, 0.84, 0.62), 2600.0, max(w, d) * 0.40)
    return yd


def _crowler(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    _office(props, nocol, aset, cell, theme)
    _vitrine(props, nocol, fx1 - 0.25, -d / 4.0, 1.4, theme, yaw=-90.0)           # display cabinet
    _sideboard(props, fx1 - 0.31, d / 4.0 - 0.4, 1.3, theme, yaw=-90.0)          # trophy shelf
    for k in range(3):
        props.cylinder((fx1 - 0.29, d / 4.0 - 0.8 + k * 0.4, 1.02), 0.06, 0.18, theme.get("gold", "M_Gold"), seg=10,
                       radius_top=0.09)


def _chancellor(props, nocol, aset, cell, theme):
    """Chancellor's office: the desk well back, so the ending mark in front of it has a 1 m clear radius."""
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    _office(props, nocol, aset, cell, theme, desk_y=1.37, guests=(-2.3, 2.3))
    _bookshelf(props, fx1 - 0.17, -d / 4.0, -90.0, theme, seed=2)
    _globe(props, fx1 - 0.7, d / 4.0, theme)
    # ending / King of Games presentation mark in front of the desk
    # (on the rug: a gold-edged blue mark, 1 m clear all round)
    props.box((0.0, fy0 + 2.82, 0.029), (1.6, 1.2, 0.008), theme.get("gold", "M_Gold"))
    props.box((0.0, fy0 + 2.82, 0.034), (1.4, 1.0, 0.004), theme.get("accent", "M_AcademyBlue"))


def _dorm_room(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    _bed(props, fx0 + 0.605, fy0 + 1.105, 180.0, theme)          # head board against the -Y wall
    _desk(props, fx1 - 0.31, fy0 + 1.15, 90.0, 1.25, 0.60, 0.74, theme)
    _chair(props, fx1 - 0.92, fy0 + 1.15, 90.0, theme)
    _wardrobe(props, fx1 - 0.6, fy1 - 0.31, 180.0, theme)
    _trunk(props, fx0 + 0.5, fy1 - 0.85, theme)
    _rug(props, 0.0, 0.0, min(2.8, w - 2.0), min(2.0, d - 2.0), theme)
    _poster(nocol, 0.4, fy0, h - 1.15, 0.8, 1.4, theme)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h, theme, max(w, d) * 0.58, 4800.0, True, drop=0.3)
    aset.light((0.0, fy0 + 1.3, h - 0.60), (1.0, 0.78, 0.55), 2200.0, max(w, d) * 0.38)


def _headmaster(props, nocol, aset, cell, theme):
    """Professor Banner's room: his desk 1.35 m off the back wall, so his mark (anchors.json) stands behind it
    beside his chair with room to spare; the guest chair is set aside, so the player's mark faces him across the
    desk with nothing in between; card binders on the desk."""
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    yd = fy0 + 1.35
    _desk(props, 0.0, yd, 180.0, 2.0, 0.80, 0.76, theme)
    _chair(props, -0.35, fy0 + 0.6, 180.0, theme)
    _chair(props, -0.8, yd + 0.85, 0.0, theme)
    for k, m in enumerate(("M_AcademyRed", "M_AcademyYellow", "M_AcademyBlue")):        # card binders
        props.box((0.45 + k * 0.07, yd - 0.1, 0.76 + 0.13), (0.05, 0.3, 0.26), m)
    props.box((-0.55, yd + 0.05, 0.765), (0.3, 0.22, 0.01), "M_ShojiPaper")             # notes
    _bookshelf(props, fx0 + 0.17, -d / 4.0, 90.0, theme)
    _tank(props, nocol, aset, fx1 - 0.82, fy0 + 0.92, theme)
    _rug(props, 0.0, 0.0, min(3.0, w - 2.0), min(2.2, d - 2.0), theme)
    _poster(nocol, 0.0, fy0, h - 1.10, 1.4, 0.9, theme)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h, theme, max(w, d) * 0.58, 5000.0, True, drop=0.3)
    aset.light((0.0, fy0 + 1.6, h - 0.60), (1.0, 0.80, 0.56), 2200.0, max(w, d) * 0.38)


def _dining(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    tw = min(6.2, w - 3.0)
    _long_table(props, 0.0, 0.0, tw, 1.55, theme)
    n = 6                                              # 12 chairs
    for i in range(n):
        x = -tw / 2.0 + 0.6 + i * (tw - 1.2) / max(1, n - 1)
        _chair(props, x, 1.12, 180.0, theme)
        _chair(props, x, -1.12, 0.0, theme)
    _sideboard(props, 0.0, fy0 + 0.31, min(4.0, w - 3.0), theme, yaw=180.0)
    _crest(nocol, props, 0.0, fy0, h - 0.95, theme)
    # chandelier: gold ring + glow disk on three chains from a ceiling rose
    g = h - FZ                                         # (the builder is lifted by FZ)
    zr = g - 0.70
    props.cylinder((0.0, 0.0, g - 0.04), 0.2, 0.04, theme.get("gold", "M_Gold"), seg=16)
    for k in range(3):
        a = 2 * math.pi * k / 3
        props.beam((0.0, 0.0, g - 0.04), (1.25 * math.cos(a), 1.25 * math.sin(a), zr + 0.08), 0.02, 0.02,
                   theme.get("gold", "M_Gold"))
    props.torus((0.0, 0.0, zr), 1.25, 0.10, theme.get("gold", "M_Gold"), seg=28, tube_seg=6)
    nocol.cylinder((0.0, 0.0, zr - 0.12), 1.05, 0.06, theme.get("glow", "M_LampGlow"), seg=28, cap_top=False)
    aset.light((0.0, 0.0, zr + FZ - 0.2), (1.0, 0.88, 0.65), 9000.0, max(w, d) * 0.72, shadows=True)
    aset.light((0.0, fy0 + 1.0, h - 0.60), (1.0, 0.82, 0.55), 2400.0, max(w, d) * 0.35)


def _slifer_dressing(props, nocol, aset, cell, theme, jackets=1, posters=(("SLIFER RED", 0.0),)):
    """Slifer touches on the room faces: dorm posters on the back wall, a coat-hook rail with red jackets on the
    door wall beside the door (clear of its architrave)."""
    from . import interior as K, detail as DT
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    for k, (text, x) in enumerate(posters):
        K.poster(nocol, aset, x, fy0 + 0.002, 1.75, 180.0, 0.5, 0.7, K.POSTERS[k % 4], text=text, text_size=0.06)
    DT.coat_hooks(nocol, -0.5 - 0.09 - 0.25 - 0.375, fy1 - 0.002, 1.75, 0.0, n=3, dorm="slifer", jackets=jackets,
                  seed=len(str(cell.get("id"))))


def _slifer_player(props, nocol, aset, cell, theme):
    """Slifer Room 101 (the player's): the standard dorm room with the bed for the sleep / save beat (its mark
    stands beside the bed) and the Slifer dressing."""
    _dorm_room(props, nocol, aset, cell, theme)
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    _slifer_dressing(props, nocol, aset, cell, theme, jackets=1, posters=(("SLIFER RED", 1.6),))


def _slifer_bunk_room(props, nocol, aset, cell, theme):
    """Jaden, Syrus and Chumley's room: the Slifer triple bunk in the back-left corner (ladder on the room side),
    a kotatsu on tatami in the middle with the three marks standing round it, Jaden's desk under the window,
    wardrobe, duel disk stand, card posters and clothes on the floor. Door zone and marks stay clear."""
    from . import interior as K, detail as DT
    w, d, h = _dims(cell)
    fx0, fy0, fx1, fy1 = _faces(cell)
    K.bunk_bed(props, nocol, fx0 + 1.03, fy0 + 0.49, 180.0, levels=3, gap=0.75, length=2.0, width=0.92,
               blankets=("M_IntFabricRed", "M_IntFabricBlue", "M_IntFabricYellow"))
    # tatami under the kotatsu (3 cm), the kotatsu on it
    tx0, ty0, tx1, ty1 = -1.25, -1.95, 1.95, 0.75
    K.tatami(props, tx0, ty0, tx1, ty1, 0.03)
    with props.at((0.0, 0.0, 0.03)), nocol.at((0.0, 0.0, 0.03)):
        K.kotatsu(props, nocol, 0.4, -0.6, 0.0, quilt="M_IntFabricOrange")
        for k in range(5):                                                  # a deck spread out on the table
            nocol.box((0.15 + k * 0.09, -0.75, 0.4), (0.06, 0.085, 0.004), "M_CardBack")
    # Jaden's desk under the -X window, chair facing it
    K.desk(props, nocol, fx0 + 0.3, 0.9, 90.0, w=1.1, d=0.6, hutch=False, rng_seed=3)
    _chair(props, fx0 + 0.85, 0.9, -90.0, theme)
    DT.duel_disk(nocol, fx0 + 0.3, 1.2, 0.76, 30.0)
    # wardrobe in the back-right corner, a colour-box shelf under the +X window
    K.wardrobe(props, fx1 - 0.6, fy0 + 0.31, 180.0, w=1.15, d=0.6, h=2.0)            # (doors to the room)
    props.box_mm((fx1 - 0.3, 0.3, 0.0), (fx1, 1.5, 0.7), "M_IntTrimWhite")
    for k in range(3):
        nocol.box((fx1 - 0.301, 0.5 + k * 0.4, 0.35), (0.004, 0.36, 0.6), "M_IntBlack")
        DT.deck_box(nocol, fx1 - 0.15, 0.5 + k * 0.4, 0.7, 10.0 * k, ("M_IntFabricRed", "M_IntFabricBlue",
                                                                     "M_IntFabricYellow")[k])
    # duel disk stand against the back wall between the bunk and the wardrobe
    props.box((-0.75, fy0 + 0.17, 0.5), (0.3, 0.3, 1.0), "M_IntWoodDark")
    DT.duel_disk(nocol, -0.75, fy0 + 0.17, 1.0, 0.0)
    # clothes on the floor (flat, out of the walkways)
    for (cx, cy, a, m) in ((2.45, -1.55, 20.0, "M_DetJacketRed"), (-0.1, -2.25, 10.0, "M_IntFabricWhite"),
                           (2.9, -0.9, 50.0, "M_IntFabricBlue")):
        with nocol.at((cx, cy, 0.0), rot=a):
            nocol.box((0.0, 0.0, 0.015), (0.5, 0.4, 0.03), m)
    _slifer_dressing(props, nocol, aset, cell, theme, jackets=3,
                     posters=(("GET YOUR GAME ON!", 0.25), ("DUEL!", 1.2)))
    K.poster(nocol, aset, fx1 - 0.002, -1.2, 1.6, -90.0, 0.55, 0.4, "M_IntPoster3", text="ELEMENTAL HEROES",
             text_size=0.045)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h, theme, max(w, d) * 0.58, 5000.0, True, drop=0.3)
    aset.light((0.0, fy0 + 1.3, h - 0.60), (1.0, 0.78, 0.55), 2200.0, max(w, d) * 0.38)


_CONTENT = {
    "classroom": _classroom,
    "exam": _exam,
    "office": _office,
    "dorm_room": _dorm_room,
    "headmaster_room": _headmaster,
    "dining": _dining,
}
# rooms whose `kind` is generic but whose story beats need their own dressing
_BY_ID = {
    "academy_crowler_office": _crowler,
    "academy_chancellor_office": _chancellor,
    "slifer_player_room": _slifer_player,
    "slifer_jaden_room": _slifer_bunk_room,
}


def build_cell(cell):
    """Build one interior cell from its `interiors.json` row."""
    cid = str(cell["id"])
    theme = _theme(cell)
    aset = AssetSet("interior_" + cid)
    shell = aset.mesh("Interior_" + cid + "_Shell")
    props = aset.mesh("Interior_" + cid + "_Props")
    nocol = aset.mesh("Interior_" + cid + "_NoCol")

    def set_text(text, pos, yaw=0.0, size=1.0, color=(1, 1, 1), emissive=False):
        aset.text(text, pos, yaw, size=size, color=color, emissive=emissive)

    cell_view = dict(cell)
    cell_view["_aset_text"] = set_text
    _room_shell(shell, nocol, cell_view, theme)

    kind = str(cell.get("kind", "dorm_room"))
    builder = _BY_ID.get(cid) or _CONTENT.get(kind, _dorm_room)
    # furniture stands on the finished floor (FZ), not on the slab under the floor polygon
    with props.at((0.0, 0.0, FZ)), nocol.at((0.0, 0.0, FZ)):
        builder(props, nocol, aset, cell, theme)

    # Room info interaction just inside the door.
    aset.interact("info", (0.0, _dims(cell)[1] / 2.0 - 0.85, 1.20), 0.0,
                  title=cell.get("display_name", "Room"),
                  text=cell.get("notes", ""), radius=2.5)

    return aset


PLACEMENTS = {}
