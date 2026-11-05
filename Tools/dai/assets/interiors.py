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
def _room_shell(shell, nocol, cell, theme):
    w, d, h = _dims(cell)
    x0, x1 = -w / 2.0, w / 2.0
    y0, y1 = -d / 2.0, d / 2.0

    door_w = min(2.25, max(1.55, w * 0.30))
    door_h = min(2.35, max(2.0, h - 0.65))
    door_u = w / 2.0

    # foundation / floor slab (collision top exactly at the visual floor)
    shell.box_mm((x0 - 0.18, y0 - 0.18, -0.28), (x1 + 0.18, y1 + 0.18, 0.018), theme["stone"])
    # room shell: walls, floor and ceiling.  Edge 2 is the +Y wall (door wall).
    footprint = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    door_opening = dict(u=door_u, w=door_w, z0=0.0, z1=door_h, frame=theme["trim"])
    shell.room(footprint, 0.0, h, 0.18, theme["wall"], openings={2: [door_opening]},
               floor_mat=theme["floor"], ceil_mat=theme["ceiling"], inner_mat=theme["inner"])
    # ceiling slab above the ceiling polygon, so the cell is closed from above
    shell.box_mm((x0 - 0.18, y0 - 0.18, h + 0.005), (x1 + 0.18, y1 + 0.18, h + 0.22), theme["ceiling"])

    # baseboards and crown moulding (segmented around the door on the +Y wall)
    z0, z1 = 0.0, 0.12
    for (a, b) in (((x0 + 0.02, y0 + 0.02), (x1 - 0.02, y0 + 0.02)),
                   ((x0 + 0.02, y0 + 0.02), (x0 + 0.02, y1 - 0.02)),
                   ((x1 - 0.02, y0 + 0.02), (x1 - 0.02, y1 - 0.02))):
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy)
        if ln > 1e-3:
            shell.beam((a[0], a[1], 0.06), (b[0], b[1], 0.06), 0.05, 0.12, theme["trim"])
    gap = door_w / 2.0 + 0.12
    for (a, b) in (((x0 + 0.02, y1 - 0.02), (-gap, y1 - 0.02)),
                   ((gap, y1 - 0.02), (x1 - 0.02, y1 - 0.02))):
        shell.beam((a[0], a[1], 0.06), (b[0], b[1], 0.06), 0.05, 0.12, theme["trim"])

    for (a, b) in (((x0 + 0.02, y0 + 0.02), (x1 - 0.02, y0 + 0.02)),
                   ((x1 - 0.02, y0 + 0.02), (x1 - 0.02, y1 - 0.02)),
                   ((x1 - 0.02, y1 - 0.02), (x0 + 0.02, y1 - 0.02)),
                   ((x0 + 0.02, y1 - 0.02), (x0 + 0.02, y0 + 0.02))):
        shell.beam((a[0], a[1], h - 0.10), (b[0], b[1], h - 0.10), 0.09, 0.16, theme["trim"])

    # door leaf, frame and threshold on the +Y wall
    leaf_y = y1 - 0.035
    shell.box((0.0, leaf_y, door_h / 2.0), (door_w - 0.14, 0.07, door_h - 0.10), theme["door"])
    shell.box((0.0, leaf_y - 0.06, door_h * 0.45), (door_w * 0.34, 0.03, door_h * 0.28), theme["trim"])
    shell.box((0.0, leaf_y - 0.06, door_h * 0.74), (door_w * 0.34, 0.03, door_h * 0.18), theme["trim"])
    for sx in (-1, 1):
        shell.box((sx * (door_w / 2.0 + 0.07), y1 - 0.05, door_h / 2.0 + 0.04),
                  (0.14, 0.24, door_h + 0.10), theme["trim"])
    shell.box((0.0, y1 - 0.05, door_h + 0.09), (door_w + 0.30, 0.24, 0.14), theme["trim"])
    shell.box((door_w * 0.31, leaf_y - 0.10, 1.02), (0.06, 0.06, 0.18), theme["gold"])
    # small step outside the door, visible from the cell exit trigger
    shell.box_mm((-door_w / 2.0 - 0.18, y1 + 0.02, -0.12), (door_w / 2.0 + 0.18, y1 + 0.52, 0.06),
                 theme["stone"])

    # side windows (paper/glass panels + frames) - interiors are below the island,
    # so these are lit panels, not real openings
    n_win = max(1, int(w / 3.2))
    for sx in (-1, 1):
        for i in range(n_win):
            yy = (i + 0.5) * (d / n_win) - d / 2.0
            x = sx * (w / 2.0 - 0.10)
            nocol.box((x, yy, 1.72), (0.035, 1.05, 1.22), theme["glass"])
            shell.box((x + sx * 0.03, yy, 1.72), (0.09, 1.20, 0.07), theme["trim"])
            shell.box((x + sx * 0.03, yy, 1.10), (0.09, 1.20, 0.07), theme["trim"])
            shell.box((x + sx * 0.03, yy, 2.33), (0.09, 1.20, 0.07), theme["trim"])
            shell.box((x + sx * 0.03, yy - 0.56, 1.72), (0.09, 0.07, 1.25), theme["trim"])
            shell.box((x + sx * 0.03, yy + 0.56, 1.72), (0.09, 0.07, 1.25), theme["trim"])
            shell.box((x + sx * 0.03, yy, 1.72), (0.07, 0.06, 1.20), theme["trim"])

    # ceiling beams for scale / lighting bounce
    for i in range(1, max(2, int(d / 2.8))):
        yy = -d / 2.0 + i * d / max(2, int(d / 2.8))
        shell.box((0.0, yy, h - 0.16), (w - 0.35, 0.14, 0.16), theme["trim"])

    # room sign above the door, facing into the room
    aset_text = cell.get("_aset_text")
    if aset_text:
        aset_text(cell.get("display_name", "Room"), (0.0, y1 - 0.13, door_h + 0.30), 0.0,
                  size=0.16, color=(1.0, 0.96, 0.88))


def _ceiling_lamp(props, nocol, aset, x, y, z, theme, radius, intensity=7000.0, shadows=False):
    nocol.cylinder((x, y, z - 0.12), 0.30, 0.12, theme["glow"], seg=12, cap_top=False)
    props.cylinder((x, y, z - 0.02), 0.34, 0.05, theme["metal"], seg=12)
    aset.light((x, y, z - 0.30), (1.0, 0.86, 0.66), intensity, radius, shadows=shadows)


# --------------------------------------------------------------------------- furniture
def _desk(props, x, y, yaw=0.0, w=1.4, d=0.68, h=0.74, theme=None):
    theme = theme or {}
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, h), (w, d, 0.07), theme.get("dark", "M_DarkWood"))
        for sx in (-1, 1):
            for sy in (-1, 1):
                props.box((sx * (w / 2.0 - 0.09), sy * (d / 2.0 - 0.08), h / 2.0),
                          (0.07, 0.07, h), theme.get("wood", "M_Wood"))
        props.box((0.0, d / 2.0 - 0.05, h / 2.0 - 0.03), (w - 0.12, 0.04, h * 0.52),
                  theme.get("wood", "M_Wood"))


def _chair(props, x, y, yaw=0.0, theme=None):
    theme = theme or {}
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, 0.45), (0.50, 0.50, 0.06), theme.get("wood", "M_Wood"))
        props.box((0.0, 0.23, 0.75), (0.50, 0.06, 0.55), theme.get("wood", "M_Wood"))
        for sx in (-1, 1):
            for sy in (-1, 1):
                props.box((sx * 0.20, sy * 0.20, 0.225), (0.05, 0.05, 0.45),
                          theme.get("dark", "M_DarkWood"))


def _bed(props, x, y, yaw=0.0, theme=None, z=0.0, single=True):
    theme = theme or {}
    w = 1.05 if single else 1.45
    with _at(props, x, y, yaw, z):
        props.box((0.0, 0.0, 0.18), (w + 0.12, 2.05, 0.26), theme.get("dark", "M_DarkWood"))
        props.box((0.0, 0.0, 0.38), (w, 1.92, 0.20), "M_Fabric")
        props.box((0.0, 0.70, 0.50), (w * 0.62, 0.34, 0.12), "M_WhiteWall")
        props.box((0.0, -0.35, 0.50), (w * 0.96, 1.00, 0.08), theme.get("accent", "M_AcademyBlue"))
        props.box((0.0, 1.02, 0.66), (w + 0.12, 0.08, 0.80), theme.get("wood", "M_Wood"))


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
    theme = theme or {}
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, 1.05), (1.15, 0.60, 2.10), theme.get("wood", "M_Wood"))
        props.box((0.0, 0.31, 1.05), (0.04, 0.02, 2.00), theme.get("dark", "M_DarkWood"))
        props.box((0.0, 0.33, 1.60), (0.05, 0.03, 0.16), theme.get("gold", "M_Gold"))
        props.box((0.0, 0.33, 0.55), (0.05, 0.03, 0.16), theme.get("gold", "M_Gold"))


def _bookshelf(props, x, y, yaw=0.0, theme=None):
    theme = theme or {}
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, 1.05), (1.80, 0.34, 2.10), theme.get("wood", "M_Wood"))
        for z in (0.35, 0.85, 1.35, 1.85):
            props.box((0.0, -0.18, z), (1.70, 0.05, 0.06), theme.get("dark", "M_DarkWood"))
        for j, z in enumerate((0.44, 0.94, 1.44)):
            for i in range(9):
                if (i + j) % 3 == 0:
                    continue
                props.box((-0.70 + i * 0.17, -0.20, z + 0.13),
                          (0.10, 0.10, 0.24 + 0.05 * (i % 3)),
                          ("M_AcademyRed", "M_AcademyBlue", "M_AcademyYellow")[(i + j) % 3])


def _blackboard(props, x, y, z, width, height, theme):
    props.box((x, y, z), (width, 0.08, height), "M_DarkWood")
    props.box((x, y - 0.02, z), (width - 0.16, 0.02, height - 0.12), "M_Black")
    props.box((x, y - 0.06, z + height / 2.0 + 0.05), (width + 0.10, 0.10, 0.08), theme.get("gold", "M_Gold"))
    props.box((x, y - 0.06, z - height / 2.0 - 0.05), (width + 0.10, 0.10, 0.08), theme.get("gold", "M_Gold"))
    for sx in (-1, 1):
        props.box((x + sx * (width / 2.0 + 0.04), y - 0.06, z), (0.08, 0.10, height + 0.16),
                  theme.get("gold", "M_Gold"))
    props.box((x, y - 0.10, z - height / 2.0 - 0.12), (width * 0.45, 0.06, 0.06), theme.get("trim", "M_WhiteWall"))


def _clock(props, x, y, z, theme):
    with props.at((x, y, z), rot_x=90):
        props.cylinder((0, 0, 0), 0.30, 0.06, theme.get("gold", "M_Gold"), seg=24)
        props.cylinder((0, 0, 0.04), 0.25, 0.04, "M_WhiteWall", seg=24)
        props.box((0.06, 0.07, 0.0), (0.03, 0.03, 0.20), "M_Black")
        props.box((0.10, 0.07, 0.11), (0.16, 0.03, 0.03), "M_Black")


def _rug(props, x, y, w, d, theme):
    props.box((x, y, 0.035), (w, d, 0.03), theme.get("fabric", "M_Carpet"))


def _sofa(props, x, y, yaw=0.0, theme=None):
    theme = theme or {}
    with _at(props, x, y, yaw):
        props.box((0.0, 0.0, 0.36), (2.0, 0.82, 0.32), theme.get("fabric", "M_Carpet"))
        props.box((0.0, 0.34, 0.68), (2.0, 0.16, 0.65), theme.get("fabric", "M_Carpet"))
        for sx in (-1, 1):
            props.box((sx * 1.02, 0.0, 0.52), (0.16, 0.84, 0.52), theme.get("fabric", "M_Carpet"))


def _long_table(props, x, y, w, d, theme):
    props.box((x, y, 0.76), (w, d, 0.08), theme.get("dark", "M_DarkWood"))
    for sx in (-1, 1):
        for sy in (-1, 1):
            props.box((x + sx * (w / 2.0 - 0.25), y + sy * (d / 2.0 - 0.18), 0.38),
                      (0.12, 0.12, 0.76), theme.get("wood", "M_Wood"))


def _sideboard(props, x, y, w, theme):
    props.box((x, y, 0.48), (w, 0.55, 0.96), theme.get("wood", "M_Wood"))
    props.box((x, y, 0.98), (w + 0.10, 0.62, 0.06), theme.get("dark", "M_DarkWood"))
    for i in range(3):
        props.box((x - w / 3.0 + i * w / 3.0, y - 0.30, 0.55), (0.04, 0.02, 0.30), theme.get("gold", "M_Gold"))


def _tank(props, nocol, aset, x, y, theme):
    props.box((x, y, 0.36), (1.20, 0.72, 0.72), theme.get("dark", "M_DarkWood"))
    nocol.box((x, y, 1.12), (1.08, 0.60, 1.10), "M_GlassClear")
    props.box((x, y, 1.70), (1.22, 0.74, 0.10), theme.get("metal", "M_DarkMetal"))
    nocol.box((x, y, 1.35), (0.70, 0.02, 0.06), theme.get("glow", "M_LampGlow"))
    aset.light((x, y, 1.35), (0.55, 0.85, 1.0), 1800.0, 3.0)


def _poster(nocol, x, y, z, w, h, theme):
    nocol.box((x, y, z), (w, 0.02, h), theme.get("paper", "M_ShojiPaper"))
    nocol.box((x, y - 0.02, z), (w * 0.55, 0.01, h * 0.35), theme.get("accent", "M_AcademyBlue"))


def _banner(nocol, x, y, z, w, h, mat):
    nocol.box((x, y, z), (w, 0.02, h), mat)
    nocol.box((x, y - 0.02, z + h / 2.0), (w + 0.12, 0.04, 0.06), "M_Gold")


def _trunk(props, x, y, theme):
    props.box((x, y, 0.30), (0.90, 0.55, 0.58), theme.get("dark", "M_DarkWood"))
    props.box((x, y - 0.02, 0.62), (0.94, 0.62, 0.06), theme.get("gold", "M_Gold"))
    props.box((x, y - 0.29, 0.38), (0.12, 0.04, 0.14), theme.get("gold", "M_Gold"))


def _crest(nocol, props, x, y, z, theme):
    with props.at((x, y, z), rot_x=90):
        props.cylinder((0, 0, 0), 0.85, 0.08, theme.get("gold", "M_Gold"), seg=24)
        props.cylinder((0, 0, 0.05), 0.72, 0.03, theme.get("accent", "M_AcademyBlue"), seg=24)
    nocol.box((x, y - 0.06, z), (1.05, 0.02, 0.16), theme.get("glow", "M_LampGlow"))


# --------------------------------------------------------------------------- room contents
def _classroom(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    _blackboard(props, 0.0, -d / 2.0 + 0.18, 1.55, min(6.0, w - 2.0), 1.35, theme)
    _desk(props, 0.0, -d / 2.0 + 1.45, 180.0, 1.8, 0.72, 0.76, theme)
    _chair(props, 0.0, -d / 2.0 + 2.15, 180.0, theme)
    _clock(props, 0.0, -d / 2.0 + 0.10, h - 0.45, theme)
    for sx in (-1, 1):
        _banner(nocol, sx * 4.5, -d / 2.0 + 0.10, h - 1.25, 1.2, 2.0,
                "M_AcademyRed" if sx < 0 else "M_AcademyBlue")
    cols, rows = 6, 5
    for r in range(rows):
        for c in range(cols):
            x = -w / 2.0 + 1.55 + c * (w - 3.1) / (cols - 1)
            y = -d / 2.0 + 3.15 + r * 1.15
            _desk(props, x, y, 0.0, 1.18, 0.58, 0.72, theme)
            _chair(props, x, y + 0.55, 0.0, theme)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h - 0.35, theme, max(w, d) * 0.62, 7800.0, True)
    aset.light((0.0, -d / 2.0 + 2.2, h - 0.65), (1.0, 0.92, 0.80), 3600.0, max(w, d) * 0.45)


def _exam(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    _blackboard(props, 0.0, -d / 2.0 + 0.18, 1.50, min(5.0, w - 2.0), 1.15, theme)
    _desk(props, 0.0, -d / 2.0 + 1.30, 180.0, 1.7, 0.70, 0.76, theme)
    _chair(props, 0.0, -d / 2.0 + 1.95, 180.0, theme)
    cols, rows = 6, 4
    for r in range(rows):
        for c in range(cols):
            x = -w / 2.0 + 1.45 + c * (w - 2.9) / (cols - 1)
            y = -d / 2.0 + 3.0 + r * 1.10
            _desk(props, x, y, 0.0, 1.10, 0.56, 0.72, theme)
            _chair(props, x, y + 0.52, 0.0, theme)
    _clock(props, 0.0, -d / 2.0 + 0.10, h - 0.45, theme)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h - 0.35, theme, max(w, d) * 0.62, 7000.0, True)


def _office(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    _desk(props, 0.0, -d / 2.0 + 1.45, 180.0, min(2.6, w - 2.5), 0.85, 0.78, theme)
    _chair(props, 0.0, -d / 2.0 + 0.80, 180.0, theme)
    _chair(props, 0.0, -d / 2.0 + 2.65, 0.0, theme)
    _bookshelf(props, -w / 2.0 + 0.28, -d / 4.0, 90.0, theme)
    _sideboard(props, w / 2.0 - 0.85, -d / 4.0, 1.5, theme)
    _rug(props, 0.0, 0.0, min(4.0, w - 2.0), min(2.6, d - 2.0), theme)
    _crest(nocol, props, 0.0, -d / 2.0 + 0.09, h - 0.85, theme)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h - 0.35, theme, max(w, d) * 0.60, 6200.0, True)
    aset.light((0.0, -d / 2.0 + 1.8, h - 0.65), (1.0, 0.84, 0.62), 2600.0, max(w, d) * 0.40)


def _chancellor(props, nocol, aset, cell, theme):
    _office(props, nocol, aset, cell, theme)
    w, d, h = _dims(cell)
    # ending / King of Games presentation mark in front of the desk
    props.box((0.0, -d / 2.0 + 2.9, 0.02), (1.6, 1.2, 0.04), theme.get("fabric", "M_Carpet"))


def _dorm_room(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    _bed(props, -w / 2.0 + 1.20, -d / 2.0 + 1.20, 0.0, theme)
    _desk(props, w / 2.0 - 1.20, -d / 2.0 + 1.15, 90.0, 1.25, 0.60, 0.74, theme)
    _chair(props, w / 2.0 - 2.05, -d / 2.0 + 1.15, 90.0, theme)
    _wardrobe(props, w / 2.0 - 0.70, d / 2.0 - 0.75, 180.0, theme)
    _trunk(props, -w / 2.0 + 1.30, d / 2.0 - 1.05, theme)
    _rug(props, 0.0, 0.0, min(2.8, w - 2.0), min(2.0, d - 2.0), theme)
    _poster(nocol, 0.0, -d / 2.0 + 0.10, h - 1.15, 0.8, 1.4, theme)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h - 0.32, theme, max(w, d) * 0.58, 4800.0, True)
    aset.light((0.0, -d / 2.0 + 1.5, h - 0.60), (1.0, 0.78, 0.55), 2200.0, max(w, d) * 0.38)


def _headmaster(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    _desk(props, 0.0, -d / 2.0 + 1.35, 180.0, 2.0, 0.80, 0.76, theme)
    _chair(props, 0.0, -d / 2.0 + 0.70, 180.0, theme)
    _chair(props, 0.0, -d / 2.0 + 2.45, 0.0, theme)
    _bookshelf(props, -w / 2.0 + 0.28, -d / 4.0, 90.0, theme)
    _tank(props, nocol, aset, w / 2.0 - 1.00, -d / 2.0 + 1.10, theme)
    _rug(props, 0.0, 0.0, min(3.0, w - 2.0), min(2.2, d - 2.0), theme)
    _poster(nocol, 0.0, -d / 2.0 + 0.10, h - 1.10, 1.4, 0.9, theme)
    _ceiling_lamp(props, nocol, aset, 0.0, 0.0, h - 0.32, theme, max(w, d) * 0.58, 5000.0, True)
    aset.light((0.0, -d / 2.0 + 1.8, h - 0.60), (1.0, 0.80, 0.56), 2200.0, max(w, d) * 0.38)


def _dining(props, nocol, aset, cell, theme):
    w, d, h = _dims(cell)
    tw = min(6.2, w - 3.0)
    _long_table(props, 0.0, 0.0, tw, 1.55, theme)
    n = 4
    for i in range(n):
        x = -tw / 2.0 + 0.75 + i * (tw - 1.5) / max(1, n - 1)
        _chair(props, x, 1.25, 180.0, theme)
        _chair(props, x, -1.25, 0.0, theme)
    _sideboard(props, 0.0, -d / 2.0 + 0.55, min(4.0, w - 3.0), theme)
    _crest(nocol, props, 0.0, -d / 2.0 + 0.08, h - 0.85, theme)
    # chandelier: gold ring + glow disk
    props.torus((0.0, 0.0, h - 0.70), 1.25, 0.10, theme.get("gold", "M_Gold"), seg=28, tube_seg=6)
    nocol.cylinder((0.0, 0.0, h - 0.82), 1.05, 0.06, theme.get("glow", "M_LampGlow"), seg=28, cap_top=False)
    aset.light((0.0, 0.0, h - 0.75), (1.0, 0.88, 0.65), 9000.0, max(w, d) * 0.72, shadows=True)
    aset.light((0.0, -d / 2.0 + 1.2, h - 0.60), (1.0, 0.82, 0.55), 2400.0, max(w, d) * 0.35)


_CONTENT = {
    "classroom": _classroom,
    "exam": _exam,
    "office": _office,
    "dorm_room": _dorm_room,
    "headmaster_room": _headmaster,
    "dining": _dining,
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
    builder = _CONTENT.get(kind, _dorm_room)
    builder(props, nocol, aset, cell, theme)

    # Room info interaction just inside the door.
    aset.interact("info", (0.0, _dims(cell)[1] / 2.0 - 0.85, 1.20), 0.0,
                  title=cell.get("display_name", "Room"),
                  text=cell.get("notes", ""), radius=2.5)

    return aset


PLACEMENTS = {}
