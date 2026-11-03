"""
Door leaves for the automatic doors (ADADoor in C++).

Every doorway in a location module calls

    aset.door(pos, yaw, width, height, style="slifer", double=False, mode=None, swing="auto")

pos   = bottom centre of the clear opening, on the middle plane of the wall (where the closed leaf sits)
yaw   = the wall's frame, local -Y = OUTSIDE (same convention as MeshBuilder.wall / facade helpers)
mode  = "swing" | "slide" (default per style: shoji, lattice and glass doors slide)
swing = "auto" (away from whoever approaches) | "out" | "in"

The layout stage collects one leaf mesh per (style, leaf width, height) -> Meshes/Doors/SM_Door_*.fbx and a
`doors` list in layout.json; the Unreal build spawns one ADADoor per entry. Leaf mesh: pivot at the HINGE,
leaf along +X (leaf width), thickness centred on y = 0, z from 0 to the height, outside face -Y. Both faces
are dressed, so the same mesh works when the door opens inwards or outwards.
"""

import math

from ..geo import MeshBuilder
from .. import palette

palette.register({
    "M_DoorShoji":     dict(kind="opaque", color=(0.97, 0.94, 0.85), rough=0.9, detail="Fabric", tiling=2.0),
    "M_DoorPinkPanel": dict(kind="opaque", color=(0.97, 0.80, 0.85), rough=0.6, detail=None),
})

# style -> dict(kind, leaf, panel, handle, glass, frame, mode)
STYLES = {
    "slifer":       dict(kind="panel", leaf="M_SliferDoor", panel="M_SliferTrim", handle="M_Metal"),
    "slifer_inner": dict(kind="panel", leaf="M_Wood", panel="M_DarkWood", handle="M_Metal"),
    "ra":           dict(kind="glazed", leaf="M_RaTrim", panel="M_RaTrim", handle="M_Gold", glass="M_GlassClear"),
    "ra_inner":     dict(kind="panel", leaf="M_Wood", panel="M_RaTrim", handle="M_Gold"),
    "obelisk":      dict(kind="ornate", leaf="M_ObeliskTrim", panel="M_Gold", handle="M_Gold"),
    "obelisk_inner": dict(kind="ornate", leaf="M_ObeliskWall", panel="M_Gold", handle="M_Gold"),
    "girls":        dict(kind="ornate", leaf="M_ObeliskWall", panel="M_GirlsTrim", handle="M_Gold"),
    "girls_inner":  dict(kind="ornate", leaf="M_DoorPinkPanel", panel="M_ObeliskWall", handle="M_Gold"),
    "academy":      dict(kind="glazed", leaf="M_AcademyBlue", panel="M_Gold", handle="M_Gold", glass="M_GlassClear"),
    "academy_wood": dict(kind="panel", leaf="M_DarkWood", panel="M_Gold", handle="M_Gold"),
    "classroom":    dict(kind="vision", leaf="M_Wood", panel="M_AcademyBlue", handle="M_Metal", glass="M_GlassClear"),
    "office":       dict(kind="vision", leaf="M_WindowFrame", panel="M_Metal", handle="M_Metal", glass="M_GlassClear"),
    "glass":        dict(kind="glass", leaf="M_Metal", panel="M_Metal", handle="M_Metal", glass="M_GlassClear", mode="slide"),
    "metal":        dict(kind="metal", leaf="M_WarehouseWall", panel="M_DarkMetal", handle="M_Metal"),
    "lighthouse":   dict(kind="metal", leaf="M_LighthouseRed", panel="M_LighthouseWhite", handle="M_Metal"),
    "abandoned":    dict(kind="plank", leaf="M_RottenWood", panel="M_Boards", handle="M_RustMetal"),
    "wood":         dict(kind="plank", leaf="M_Wood", panel="M_DarkWood", handle="M_DarkMetal"),
    "shoji":        dict(kind="shoji", leaf="M_DarkWood", panel="M_DoorShoji", handle="M_DarkWood", mode="slide"),
    "lattice":      dict(kind="lattice", leaf="M_Wood", panel="M_DarkWood", handle="M_Wood", mode="slide"),
}

T = 0.05   # leaf thickness


def leaf_name(style, leaf_w, h):
    return f"SM_Door_{style}_{int(round(leaf_w * 100))}x{int(round(h * 100))}"


def default_mode(style):
    return STYLES.get(style, STYLES["wood"]).get("mode", "swing")


def _both(mb, center, size, mat):
    """A plaque that shows on both faces of the leaf (front at -y, back at +y)."""
    x, z = center[0], center[2]
    for s in (-1, 1):
        mb.box((x, s * (T / 2 + size[1] / 2), z), size, mat)


def _frame_panel(mb, x0, x1, z0, z1, mat, bar=0.045):
    """Raised rectangular moulding (four bars) on both faces."""
    w, h = x1 - x0, z1 - z0
    for s in (-1, 1):
        y = s * (T / 2 + 0.012)
        mb.box(((x0 + x1) / 2, y, z0 + bar / 2), (w, 0.024, bar), mat)
        mb.box(((x0 + x1) / 2, y, z1 - bar / 2), (w, 0.024, bar), mat)
        mb.box((x0 + bar / 2, y, (z0 + z1) / 2), (bar, 0.024, h), mat)
        mb.box((x1 - bar / 2, y, (z0 + z1) / 2), (bar, 0.024, h), mat)


def _handle(mb, w, h, mat, lever=True):
    x = w - 0.1
    z = min(1.0, h * 0.47)
    for s in (-1, 1):
        y = s * (T / 2 + 0.03)
        mb.box((x, s * (T / 2 + 0.01), z), (0.06, 0.02, 0.16), mat)       # rose / backplate
        if lever:
            mb.box((x - 0.06, y + s * 0.02, z + 0.04), (0.13, 0.025, 0.025), mat)
        else:
            mb.sphere((x, y + s * 0.01, z), 0.03, mat, seg=8, rings=6)


def build_leaf(style, w, h):
    st = STYLES.get(style, STYLES["wood"])
    kind, leaf, panel, handle = st["kind"], st["leaf"], st["panel"], st["handle"]
    glass = st.get("glass", "M_GlassClear")
    mb = MeshBuilder(leaf_name(style, w, h))
    g = 0.006   # hairline gap to the jamb

    def slab(x0, x1, z0, z1, mat=leaf, t=T):
        mb.box_mm((x0, -t / 2, z0), (x1, t / 2, z1), mat)

    if kind in ("panel", "ornate"):
        slab(g, w - g, 0.005, h - g)
        m = 0.12 if w > 0.6 else 0.08
        split = h * 0.42
        _frame_panel(mb, m, w - m, m + 0.02, split - 0.06, panel)
        _frame_panel(mb, m, w - m, split + 0.06, h - m, panel)
        if kind == "ornate":
            _frame_panel(mb, m + 0.08, w - m - 0.08, split + 0.14, h - m - 0.08, panel, bar=0.025)
            _both(mb, (w / 2, 0, split), (min(0.22, w * 0.25), 0.02, 0.06), handle)
        _handle(mb, w, h, handle, lever=kind == "ornate")
    elif kind in ("glazed", "vision"):
        m = 0.11
        split = h * (0.45 if kind == "glazed" else 0.55)
        gz1 = h - m if kind == "glazed" else min(h - 0.35, split + 0.75)
        gx0, gx1 = (m, w - m) if kind == "glazed" else (w * 0.3, w * 0.7)
        slab(g, w - g, 0.005, split)                       # bottom rail / kick panel
        slab(g, w - g, gz1, h - g)                         # top rail
        slab(g, gx0, split, gz1)                           # stiles
        slab(gx1, w - g, split, gz1)
        mb.box_mm((gx0, -0.008, split), (gx1, 0.008, gz1), glass)
        if kind == "glazed":
            mb.box(((gx0 + gx1) / 2, 0, (split + gz1) / 2), (0.035, T * 0.8, gz1 - split), leaf)   # muntin
            _frame_panel(mb, m, w - m, m, split - 0.08, panel)
        _handle(mb, w, h, handle)
    elif kind == "glass":
        f = 0.06
        slab(g, w - g, 0.005, 0.12, leaf)
        slab(g, w - g, h - 0.08, h - g, leaf)
        slab(g, f, 0.12, h - 0.08, leaf)
        slab(w - f, w - g, 0.12, h - 0.08, leaf)
        mb.box_mm((f, -0.01, 0.12), (w - f, 0.01, h - 0.08), glass)
        for s in (-1, 1):
            mb.box((w - 0.16, s * 0.05, h * 0.45), (0.035, 0.035, 0.9), handle)
    elif kind == "metal":
        slab(g, w - g, 0.005, h - g)
        for z in (0.25, h * 0.5, h - 0.25):
            _both(mb, (w / 2, 0, z), (w - 0.1, 0.012, 0.035), panel)
        _both(mb, (w / 2, 0, h * 0.78), (w * 0.45, 0.012, 0.25), panel)     # vent / sign plate
        _handle(mb, w, h, handle)
    elif kind == "plank":
        n = max(3, int(w / 0.14))
        pw = (w - 2 * g) / n
        for i in range(n):
            x0 = g + i * pw
            dz = 0.0 if style != "abandoned" else (0.04 * ((i * 7) % 3) - 0.04)
            mat = leaf if i % 3 else panel
            slab(x0 + 0.004, x0 + pw - 0.004, 0.005, h - g + dz, mat)
        for z in (0.3, h - 0.35):
            _both(mb, (w / 2, 0, z), (w - 0.06, 0.03, 0.12), panel)
        mb.beam((0.06, T / 2 + 0.03, 0.32), (w - 0.08, T / 2 + 0.03, h - 0.4), 0.1, 0.03, panel)   # Z brace (back)
        _handle(mb, w, h, handle, lever=False)
    elif kind in ("shoji", "lattice"):
        f = 0.05
        slab(g, w - g, 0.005, 0.1, leaf)
        slab(g, w - g, h - 0.06, h - g, leaf)
        slab(g, f, 0.1, h - 0.06, leaf)
        slab(w - f, w - g, 0.1, h - 0.06, leaf)
        if kind == "shoji":
            mb.box_mm((f, -0.004, 0.1), (w - f, 0.004, h - 0.06), panel)
            nx, nz = 3, 6
            bar = 0.018
        else:
            nx, nz = 5, 9
            bar = 0.03
        for i in range(1, nx):
            x = f + (w - 2 * f) * i / nx
            mb.box((x, 0, h / 2), (bar, T * 0.7, h - 0.16), leaf)
        for k in range(1, nz):
            z = 0.1 + (h - 0.16) * k / nz
            mb.box((w / 2, 0, z), (w - 2 * f, T * 0.7, bar), leaf)
        mb.box((w - 0.09, 0, h * 0.45), (0.03, T + 0.02, 0.12), panel if kind == "lattice" else "M_DarkMetal")
    else:
        slab(g, w - g, 0.005, h - g)
    return mb


def leaf_width(width, double):
    return width / 2 if double else width


def preview_objects(aset, open_deg=35.0):
    """Blender objects for the door leaves of an AssetSet (previews): leaves posed `open_deg` open."""
    objs = []
    cache = {}
    for s in aset.sockets:
        if s["type"] != "door":
            continue
        p = s["props"]
        lw = leaf_width(p["width"], p["double"])
        key = (p["style"], round(lw, 3), round(p["height"], 3))
        if key not in cache:
            cache[key] = build_leaf(p["style"], lw, p["height"])
        leaves = [(-p["width"] / 2, 0.0)] + ([(p["width"] / 2, 180.0)] if p["double"] else [])
        slide = p["mode"] == "slide"
        for hx, base in leaves:
            mb = MeshBuilder("DoorPreview")
            a = 0.0 if slide else open_deg * (1 if base == 0.0 else -1)
            off = 0.0
            if slide:
                off = (-1 if base == 0.0 else 1) * lw * open_deg / 90.0
            with mb.at(s["pos"], rot=s["yaw"]):
                with mb.at((hx + off, 0.0, 0.0), rot=base + a):
                    mb.extend(cache[key])
            objs.append(mb.build(f"Door_{len(objs)}"))
    return objs
