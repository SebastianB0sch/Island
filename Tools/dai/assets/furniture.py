"""
Interior furniture + decor catalog (SM_Int_*).

The real meshes are curated CC0 Poly Haven models (Tools/thirdparty/registry/interiors.json), imported with the
anime treatment (cel-painted textures on M_DA_Toon, inverted-hull ink outline). Every entry also has a small
procedural stand-in here, so the build never breaks when a third-party file is missing.

Conventions (same as every catalog prop): metres, origin at the base centre, front (the side you use / look
at) facing -Y, wall-mounted pieces have their back at +Y. Ceiling fixtures have their origin at the TOP.
"""

from ..geo import MeshBuilder
from .. import palette

palette.register({
    "M_FurnWood":    dict(kind="toon", color=(0.62, 0.42, 0.25), rough=0.8, fill=0.35),
    "M_FurnDark":    dict(kind="toon", color=(0.32, 0.21, 0.14), rough=0.8, fill=0.35),
    "M_FurnFabric":  dict(kind="toon", color=(0.36, 0.52, 0.78), rough=0.95, fill=0.35),
    "M_FurnRed":     dict(kind="toon", color=(0.78, 0.20, 0.18), rough=0.95, fill=0.35),
    "M_FurnMetal":   dict(kind="toon", color=(0.62, 0.65, 0.70), rough=0.4, fill=0.3),
    "M_FurnWhite":   dict(kind="toon", color=(0.93, 0.92, 0.88), rough=0.6, fill=0.35),
    "M_FurnGold":    dict(kind="toon", color=(0.93, 0.74, 0.30), rough=0.35, fill=0.35),
    "M_FurnGreen":   dict(kind="toon", color=(0.30, 0.56, 0.26), rough=0.9, fill=0.35),
    "M_FurnGlow":    dict(kind="emissive", color=(1.0, 0.86, 0.62), strength=8.0),
})

W, D, FAB, RED, MET, WHT, GLD, GRN, GLOW = ("M_FurnWood", "M_FurnDark", "M_FurnFabric", "M_FurnRed", "M_FurnMetal",
                                           "M_FurnWhite", "M_FurnGold", "M_FurnGreen", "M_FurnGlow")

CATALOG = {
    "SM_Int_SchoolDesk": "Single school desk, user side -Y (0.71 x 0.55 x 0.88 m, real size)",
    "SM_Int_SchoolChair": "School chair, seat faces -Y (0.57 x 0.68 x 1.01 m, real size)",
    "SM_Int_Armchair": "Upholstered armchair, faces -Y (0.85 x 0.77 x 1.06 m, real size)",
    "SM_Int_Sofa": "Three-seat sofa, faces -Y (1.57 x 0.66 x 0.80 m, real size)",
    "SM_Int_SofaB": "Sofa, faces -Y (1.81 x 0.82 x 0.71 m, real size)",
    "SM_Int_WoodChair": "Painted wooden chair, faces -Y (0.43 x 0.54 x 0.96 m, real size)",
    "SM_Int_DiningChair": "Upholstered dining chair, faces -Y (0.43 x 0.58 x 0.97 m, real size)",
    "SM_Int_BarStool": "Round bar stool (0.48 x 0.49 x 0.75 m, real size)",
    "SM_Int_Ottoman": "Ottoman / pouf (0.89 x 0.62 x 0.62 m, real size)",
    "SM_Int_Stool": "Small wooden stool (0.60 x 0.51 x 0.63 m, real size)",
    "SM_Int_GreenChair": "Upholstered occasional chair, faces -Y (0.67 x 0.66 x 1.06 m, real size)",
    "SM_Int_OfficeChair": "Office arm chair, faces -Y (0.82 x 0.99 x 1.02 m, real size)",
    "SM_Int_Bench": "Painted wooden settle (bench with a back), faces -Y (1.17 x 0.50 x 0.89 m, real size)",
    "SM_Int_Table": "Low rectangular wooden table 1.8 x (1.80 x 0.66 x 0.55 m, real size)",
    "SM_Int_RoundTable": "Round wooden table ~0.75 m",
    "SM_Int_CoffeeTable": "Round coffee table across (1.30 x 1.30 x 0.49 m, real size)",
    "SM_Int_OfficeDesk": "Metal office desk, user side -Y (2.00 x 0.95 x 0.79 m, real size)",
    "SM_Int_LowTable": "Low tea table (kotatsu height) (0.84 x 0.84 x 0.50 m, real size)",
    "SM_Int_SideTable": "Side table (0.55 x 0.45 x 0.55 m, real size)",
    "SM_Int_Console": "Classic console table, back against a wall at +Y (1.54 x 0.59 x 0.95 m, real size)",
    "SM_Int_GrandBed": "Carved double bed, headboard at +Y (1.49 x 2.04 x 1.53 m, real size)",
    "SM_Int_Nightstand": "Nightstand (0.57 x 0.42 x 0.70 m, real size)",
    "SM_Int_NightstandB": "Painted nightstand (0.51 x 0.51 x 0.62 m, real size)",
    "SM_Int_Bookshelf": "Worn wooden bookshelf, back at +Y (1.37 x 0.58 x 2.06 m, real size)",
    "SM_Int_Shelves": "Painted wooden shelves, back at +Y (0.51 x 0.37 x 1.12 m, real size)",
    "SM_Int_SteelShelves": "Steel frame shelving (1.10 x 0.50 x 2.14 m, real size)",
    "SM_Int_Cabinet": "Painted wooden sideboard 1.84 x,, back at +Y (1.20 x 0.62 x 1.18 m, real size)",
    "SM_Int_Wardrobe": "Carved wardrobe 1.54 x,, back at +Y (1.72 x 1.12 x 2.36 m, real size)",
    "SM_Int_DisplayShelves": "Open display shelves, back at +Y (0.37 x 1.08 x 1.56 m, real size)",
    "SM_Int_Chandelier": "Chandelier, origin at the TOP (place at the ceiling); light added automatically (0.68 x 0.62 x 0.85 m, real size)",
    "SM_Int_CeilingLamp": "Pendant ceiling lamp, origin at the TOP; light added automatically (0.43 x 0.43 x 0.95 m, real size)",
    "SM_Int_IndustrialLamp": "Hanging industrial lamp ~0.9 m, origin at the TOP; light added automatically",
    "SM_Int_CeilingFan": "Ceiling fan, origin at the TOP (1.46 x 1.46 x 0.52 m, real size)",
    "SM_Int_DeskLamp": "Arm desk lamp (0.20 x 0.61 x 0.89 m, real size)",
    "SM_Int_OilLamp": "Vintage oil lamp (0.22 x 0.22 x 0.80 m, real size)",
    "SM_Int_PottedPlant": "Potted succulent (0.17 x 0.18 x 0.27 m, real size)",
    "SM_Int_PottedPlantB": "Large potted plant (0.70 x 0.66 x 0.84 m, real size)",
    "SM_Int_Painting": "Gilded picture frame, wall at +Y (origin bottom centre) (0.60 x 0.02 x 0.46 m, real size)",
    "SM_Int_Frame": "Hanging picture frame, wall at +Y (0.75 x 0.03 x 0.50 m, real size)",
    "SM_Int_Mirror": "Ornate wall mirror, wall at +Y (0.49 x 0.03 x 0.74 m, real size)",
    "SM_Int_WallClock": "Wall clock, wall at +Y (0.32 x 0.05 x 0.32 m, real size)",
    "SM_Int_GrandfatherClock": "Grandfather clock, back at +Y (0.63 x 0.43 x 2.19 m, real size)",
    "SM_Int_Chalkboard": "Standing chalkboard (0.92 x 0.76 x 1.51 m, real size)",
    "SM_Int_TV": "Old CRT television, screen -Y (0.60 x 0.47 x 0.46 m, real size)",
    "SM_Int_Register": "Cash register ~0.3 m",
    "SM_Int_Bust": "Marble bust (place on a plinth) (0.27 x 0.30 x 0.52 m, real size)",
    "SM_Int_Books": "Row of books (0.55 x 0.16 x 0.24 m, real size)",
    "SM_Int_Box": "Cardboard box (0.39 x 0.52 x 0.34 m, real size)",
    "SM_Int_Lifebuoy": "Lifebuoy, wall at +Y (0.78 x 0.15 x 0.84 m, real size)",
    "SM_Int_Radio": "Radio transceiver (0.57 x 0.41 x 0.43 m, real size)",
    "SM_Int_Extinguisher": "Fire extinguisher (0.28 x 0.37 x 0.66 m, real size)",
    "SM_Int_WetFloor": "Wet floor sign (0.30 x 0.36 x 0.63 m, real size)",
    "SM_Int_Basket": "Wicker basket (0.38 x 0.29 x 0.12 m, real size)",
    "SM_Int_Bucket": "Wooden bucket ~0.3 m",
    "SM_Int_FoldingScreen": "Folding screen (1.29 x 0.38 x 1.60 m, real size)",
    "SM_Int_Pillows": "Pair of throw pillows (0.94 x 0.45 x 0.45 m, real size)",
    "SM_Int_Suitcase": "Suitcase (1.61 x 0.24 x 0.57 m, real size)",
    "SM_Int_Stove": "Electric stove, front -Y (0.50 x 0.65 x 0.86 m, real size)",
    "SM_Int_Candelabra": "Brass candle holders ~0.4 m",
    "SM_Int_OldBed": "Old iron bed frame (0.91 x 2.00 x 1.20 m, real size)",
    "SM_Int_RockingChair": "Rocking chair, faces -Y (0.71 x 0.83 x 0.99 m, real size)",
    "SM_Int_ProjectorScreen": "Projector screen (1.09 x 0.92 x 1.80 m, real size)",
    "SM_Int_HandTruck": "Hand truck (0.59 x 0.69 x 1.40 m, real size)",
    "SM_Int_RubberDuck": "Rubber duck 0.12 m",
    "SM_Int_Microwave": "Microwave ~0.3 m, front -Y",
    "SM_Int_Kettle": "Electric kettle (0.32 x 0.25 x 0.30 m, real size)",
    "SM_Int_TeaSet": "Tea set on tray 0.5 m",
}

# lights that come with a fixture (offset from the origin, metres) - interiors are lit day and night
LIGHTS = {
    "SM_Int_Chandelier": dict(offset=(0, 0, -0.59), color=(1.0, 0.86, 0.62), intensity=6000.0, radius=12.0, night_only=False),
    "SM_Int_CeilingLamp": dict(offset=(0, 0, -0.75), color=(1.0, 0.88, 0.70), intensity=3500.0, radius=8.0, night_only=False),
    "SM_Int_IndustrialLamp": dict(offset=(0, 0, -0.85), color=(1.0, 0.84, 0.60), intensity=5000.0, radius=12.0, night_only=False),
}


# --------------------------------------------------------------------------- generic stand-ins
def _box(mb, x0, y0, z0, x1, y1, z1, m):
    mb.box_mm((x0, y0, z0), (x1, y1, z1), m)


def _legs(mb, hw, hd, h, r, m):
    for sx in (-1, 1):
        for sy in (-1, 1):
            _box(mb, sx * hw - r, sy * hd - r, 0, sx * hw + r, sy * hd + r, h, m)


def table(w, d, h, top=W, leg=D):
    mb = MeshBuilder("t")
    _box(mb, -w / 2, -d / 2, h - 0.04, w / 2, d / 2, h, top)
    _legs(mb, w / 2 - 0.06, d / 2 - 0.06, h - 0.04, 0.03, leg)
    return mb


def chair(h=0.9, seat=W, frame=D, w=0.45, back=True):
    mb = MeshBuilder("c")
    _legs(mb, w / 2 - 0.03, w / 2 - 0.03, 0.44, 0.02, frame)
    _box(mb, -w / 2, -w / 2, 0.42, w / 2, w / 2, 0.48, seat)
    if back:
        _box(mb, -w / 2, w / 2 - 0.05, 0.48, w / 2, w / 2, h, seat)
    return mb


def sofa(w, h=0.85, fab=FAB, d=0.9):
    mb = MeshBuilder("s")
    _box(mb, -w / 2, -d / 2, 0.08, w / 2, d / 2, 0.42, fab)
    _box(mb, -w / 2, d / 2 - 0.2, 0.42, w / 2, d / 2, h, fab)
    for s in (-1, 1):
        _box(mb, s * w / 2 - (0.18 if s > 0 else 0), -d / 2, 0.42, s * w / 2 + (0.18 if s < 0 else 0), d / 2, 0.62, fab)
    _legs(mb, w / 2 - 0.08, d / 2 - 0.08, 0.08, 0.03, D)
    return mb


def cabinet(w, d, h, m=W, shelves=0, books=False):
    mb = MeshBuilder("k")
    _box(mb, -w / 2, -d / 2 + 0.02, 0, w / 2, d / 2, h, m)
    if shelves:
        for k in range(shelves):
            z = 0.1 + (h - 0.2) * (k + 0.5) / shelves
            _box(mb, -w / 2 + 0.05, -d / 2, z - 0.02, w / 2 - 0.05, -d / 2 + 0.02, z, D)
            if books:
                for i in range(int((w - 0.2) / 0.06)):
                    x = -w / 2 + 0.12 + i * 0.06
                    _box(mb, x, -d / 2 + 0.05, z, x + 0.045, d / 2 - 0.05, z + 0.22 + 0.04 * (i % 3),
                         (RED, FAB, GRN, GLD)[i % 4])
    return mb


def bed(w, l, m=W, sheet=WHT):
    mb = MeshBuilder("b")
    _box(mb, -w / 2, -l / 2, 0, w / 2, l / 2, 0.35, m)
    _box(mb, -w / 2 + 0.03, -l / 2 + 0.03, 0.35, w / 2 - 0.03, l / 2 - 0.03, 0.55, sheet)
    _box(mb, -w / 2, l / 2 - 0.08, 0, w / 2, l / 2, 1.2, m)
    _box(mb, -w / 2 + 0.1, l / 2 - 0.5, 0.55, w / 2 - 0.1, l / 2 - 0.12, 0.68, sheet)
    return mb


def hanging(r, h, shade=GLD, glow=True):
    mb = MeshBuilder("h")
    mb.cylinder((0, 0, -h * 0.5), 0.012, h * 0.5, D, seg=6)
    mb.cone((0, 0, -h), r, h * 0.5, shade, seg=12)
    if glow:
        mb.sphere((0, 0, -h * 0.95), r * 0.35, GLOW, seg=8, rings=6)
    return mb


def desk_lamp():
    """Base-origin arm desk lamp (the curated asset is base-origin too)."""
    mb = MeshBuilder("dl")
    mb.cylinder((0, 0, 0), 0.09, 0.02, MET, seg=12)
    mb.cylinder((0, 0, 0.02), 0.018, 0.55, MET, seg=8)
    mb.cone((0.08, 0, 0.62), 0.12, 0.18, GLD, seg=12)
    return mb


def wall_piece(w, h, m=GLD, inner=FAB, depth=0.04):
    mb = MeshBuilder("w")
    _box(mb, -w / 2, -depth, 0, w / 2, 0, h, m)
    _box(mb, -w / 2 + 0.06, -depth - 0.005, 0.06, w / 2 - 0.06, -depth, h - 0.06, inner)
    return mb


def plant(h):
    mb = MeshBuilder("p")
    mb.cylinder((0, 0, 0), h * 0.18, h * 0.3, "M_RustMetal", seg=10, radius_top=h * 0.22)
    mb.sphere((0, 0, h * 0.62), h * 0.33, "M_LeavesBush", seg=10, rings=8)
    return mb


def lump(w, d, h, m):
    mb = MeshBuilder("l")
    _box(mb, -w / 2, -d / 2, 0, w / 2, d / 2, h, m)
    return mb


def cyl(r, h, m, seg=12):
    mb = MeshBuilder("y")
    mb.cylinder((0, 0, 0), r, h, m, seg=seg)
    return mb


def _ring(r, m):
    mb = MeshBuilder("r")
    with mb.at((0, 0, r), rot_x=90):
        mb.torus((0, 0, 0), r * 0.75, r * 0.25, m, seg=16, tube_seg=6)
    return mb


BUILDERS = {
    "SM_Int_SchoolDesk": lambda: table(0.65, 0.5, 0.76, W, MET),
    "SM_Int_SchoolChair": lambda: chair(0.82, W, MET, 0.42),
    "SM_Int_Armchair": lambda: sofa(0.9, 0.95, RED, 0.85),
    "SM_Int_Sofa": lambda: sofa(2.1),
    "SM_Int_SofaB": lambda: sofa(1.9, 0.8, GRN),
    "SM_Int_WoodChair": lambda: chair(0.9),
    "SM_Int_DiningChair": lambda: chair(1.0, RED, D),
    "SM_Int_BarStool": lambda: chair(0.78, RED, MET, 0.38, back=False),
    "SM_Int_Ottoman": lambda: cyl(0.3, 0.45, FAB),
    "SM_Int_Stool": lambda: chair(0.45, W, D, 0.35, back=False),
    "SM_Int_GreenChair": lambda: sofa(0.75, 0.85, GRN, 0.75),
    "SM_Int_OfficeChair": lambda: chair(0.95, FAB, MET, 0.5),
    "SM_Int_Bench": lambda: table(1.6, 0.4, 0.45),
    "SM_Int_Table": lambda: table(1.8, 0.66, 0.55),
    "SM_Int_RoundTable": lambda: table(1.0, 1.0, 0.75),
    "SM_Int_CoffeeTable": lambda: table(0.8, 0.8, 0.45),
    "SM_Int_OfficeDesk": lambda: table(1.4, 0.7, 0.76, MET, MET),
    "SM_Int_LowTable": lambda: table(1.0, 0.7, 0.38),
    "SM_Int_SideTable": lambda: table(0.5, 0.5, 0.6),
    "SM_Int_Console": lambda: table(1.2, 0.4, 0.85, D, D),
    "SM_Int_GrandBed": lambda: bed(1.8, 2.2, D),
    "SM_Int_Nightstand": lambda: lump(0.5, 0.4, 0.6, D),
    "SM_Int_NightstandB": lambda: lump(0.45, 0.4, 0.55, W),
    "SM_Int_Bookshelf": lambda: cabinet(1.0, 0.35, 2.0, W, 5, True),
    "SM_Int_Shelves": lambda: cabinet(0.9, 0.3, 1.8, WHT, 4),
    "SM_Int_SteelShelves": lambda: cabinet(1.2, 0.5, 2.0, MET, 4),
    "SM_Int_Cabinet": lambda: cabinet(0.9, 0.45, 1.8, W),
    "SM_Int_Wardrobe": lambda: cabinet(1.2, 0.6, 2.1, D),
    "SM_Int_DisplayShelves": lambda: cabinet(1.0, 0.35, 1.8, W, 4),
    "SM_Int_Chandelier": lambda: hanging(0.5, 1.1),
    "SM_Int_CeilingLamp": lambda: hanging(0.25, 0.6, WHT),
    "SM_Int_IndustrialLamp": lambda: hanging(0.3, 0.9, MET),
    "SM_Int_CeilingFan": lambda: hanging(0.65, 0.4, W, glow=False),
    "SM_Int_DeskLamp": desk_lamp,
    "SM_Int_OilLamp": lambda: cyl(0.08, 0.45, GLD),
    "SM_Int_PottedPlant": lambda: plant(0.6),
    "SM_Int_PottedPlantB": lambda: plant(1.4),
    "SM_Int_Painting": lambda: wall_piece(1.0, 0.8),
    "SM_Int_Frame": lambda: wall_piece(0.6, 0.45, D),
    "SM_Int_Mirror": lambda: wall_piece(0.8, 1.2, GLD, MET),
    "SM_Int_WallClock": lambda: wall_piece(0.4, 0.4, D, WHT),
    "SM_Int_GrandfatherClock": lambda: lump(0.5, 0.3, 2.1, D),
    "SM_Int_Chalkboard": lambda: wall_piece(0.8, 1.6, W, GRN, 0.1),
    "SM_Int_TV": lambda: lump(0.5, 0.45, 0.45, "M_Black"),
    "SM_Int_Register": lambda: lump(0.4, 0.4, 0.3, MET),
    "SM_Int_Bust": lambda: cyl(0.2, 0.7, WHT),
    "SM_Int_Books": lambda: cabinet(0.5, 0.2, 0.25, RED),
    "SM_Int_Box": lambda: lump(0.5, 0.4, 0.45, "M_ShopShelf"),
    "SM_Int_Lifebuoy": lambda: _ring(0.375, RED),
    "SM_Int_Radio": lambda: lump(0.45, 0.3, 0.35, MET),
    "SM_Int_Extinguisher": lambda: cyl(0.09, 0.6, RED),
    "SM_Int_WetFloor": lambda: lump(0.3, 0.25, 0.62, GLD),
    "SM_Int_Basket": lambda: cyl(0.22, 0.3, W),
    "SM_Int_Bucket": lambda: cyl(0.16, 0.3, W),
    "SM_Int_FoldingScreen": lambda: lump(1.6, 0.05, 1.8, WHT),
    "SM_Int_Pillows": lambda: lump(0.9, 0.2, 0.4, FAB),
    "SM_Int_Suitcase": lambda: lump(0.65, 0.22, 0.45, D),
    "SM_Int_Stove": lambda: lump(0.6, 0.6, 0.9, WHT),
    "SM_Int_Candelabra": lambda: cyl(0.06, 0.4, GLD),
    "SM_Int_OldBed": lambda: bed(1.0, 2.0, MET, WHT),
    "SM_Int_RockingChair": lambda: chair(1.0),
    "SM_Int_ProjectorScreen": lambda: wall_piece(2.0, 1.6, MET, WHT),
    "SM_Int_HandTruck": lambda: lump(0.5, 0.4, 1.2, MET),
    "SM_Int_RubberDuck": lambda: cyl(0.06, 0.12, GLD),
    "SM_Int_Microwave": lambda: lump(0.5, 0.35, 0.3, WHT),
    "SM_Int_Kettle": lambda: cyl(0.08, 0.25, MET),
    "SM_Int_TeaSet": lambda: lump(0.5, 0.35, 0.12, WHT),
}


# --------------------------------------------------------------------------- detail props (real size)
# name: (description, (x, y, z) metres) - CC0 Poly Haven, imported at scale 1; stand-ins are plain blocks
DETAIL = {
    "SM_Int_Pot": ("Brass cooking pot", (0.3, 0.3, 0.29)),
    "SM_Int_EnamelPot": ("Enamel cooking pot", (0.26, 0.18, 0.18)),
    "SM_Int_Jug": ("Ceramic jug", (0.28, 0.17, 0.21)),
    "SM_Int_Bowl": ("Wooden bowl", (0.31, 0.31, 0.09)),
    "SM_Int_CuttingBoard": ("Wooden cutting board", (0.45, 0.25, 0.04)),
    "SM_Int_Cake": ("Strawberry chocolate cake", (0.24, 0.24, 0.08)),
    "SM_Int_Apple": ("Apple", (0.1, 0.1, 0.09)),
    "SM_Int_Bananas": ("Bunch of bananas", (0.6, 0.24, 0.18)),
    "SM_Int_Lemon": ("Lemon", (0.07, 0.07, 0.1)),
    "SM_Int_Croissant": ("Croissant", (0.2, 0.08, 0.06)),
    "SM_Int_Goblets": ("Brass goblets", (0.45, 0.3, 0.27)),
    "SM_Int_Binder": ("Binder / notebook", (0.58, 0.2, 0.03)),
    "SM_Int_Clipboard": ("Clipboard", (0.23, 0.34, 0.04)),
    "SM_Int_Notepads": ("Notepads", (1.1, 0.66, 0.02)),
    "SM_Int_Stationery": ("Pen cup and stationery", (0.3, 0.08, 0.16)),
    "SM_Int_Laptop": ("Classic laptop", (0.65, 0.49, 0.54)),
    "SM_Int_Stapler": ("Stapler", (0.21, 0.05, 0.1)),
    "SM_Int_AlarmClock": ("Alarm clock", (0.23, 0.17, 0.17)),
    "SM_Int_Magnifier": ("Magnifying glass", (0.13, 0.03, 0.27)),
    "SM_Int_FireAlarm": ("Fire alarm call point, wall at +Y", (0.1, 0.03, 0.14)),
    "SM_Int_SecurityCam": ("Security camera, wall mounted", (0.17, 0.55, 0.29)),
    "SM_Int_MantelClock": ("Mantel clock", (0.48, 0.25, 0.16)),
    "SM_Int_Camera": ("Vintage camera", (0.21, 0.26, 0.08)),
    "SM_Int_Gamepad": ("Gamepad", (0.4, 0.43, 0.02)),
    "SM_Int_TVB": ("Small vintage television", (0.4, 0.35, 0.41)),
    "SM_Int_Postcards": ("Postcards", (0.68, 0.0, 0.54)),
    "SM_Int_Chess": ("Chess set", (0.55, 0.55, 0.11)),
    "SM_Int_Dartboard": ("Dartboard, wall at +Y", (0.45, 0.04, 0.45)),
    "SM_Int_Ukulele": ("Ukulele", (0.18, 0.05, 0.53)),
    "SM_Int_Ball": ("Football", (0.51, 0.22, 0.22)),
    "SM_Int_BaseballBat": ("Baseball bat", (0.06, 0.06, 0.91)),
    "SM_Int_PhotoFrame": ("Standing photo frame", (0.2, 0.1, 0.25)),
    "SM_Int_PhotoFrameB": ("Standing photo frame", (0.22, 0.1, 0.27)),
    "SM_Int_PaintingB": ("Gilded painting, wall at +Y", (0.66, 0.09, 0.77)),
    "SM_Int_FrameC": ("Hanging picture frame, wall at +Y", (0.39, 0.03, 0.5)),
    "SM_Int_Binoculars": ("Binoculars", (0.17, 0.29, 0.08)),
    "SM_Int_Compass": ("Ship's compass", (0.08, 0.15, 0.09)),
    "SM_Int_WhaleStatue": ("Bronze whale statue", (0.93, 1.37, 1.07)),
    "SM_Int_CatStatue": ("Cat statue", (0.15, 0.25, 0.28)),
    "SM_Int_HorseStatue": ("Horse statue", (0.16, 0.11, 0.22)),
    "SM_Int_VaseA": ("Antique ceramic vase", (0.26, 0.26, 0.44)),
    "SM_Int_VaseB": ("Ceramic vase", (0.22, 0.22, 0.31)),
    "SM_Int_VaseC": ("Brass vase", (0.23, 0.23, 0.69)),
    "SM_Int_Shell": ("Sea shell", (0.14, 0.07, 0.05)),
    "SM_Int_Candlestick": ("Wooden candlestick", (0.1, 0.1, 0.22)),
    "SM_Int_Broom": ("Broom", (0.42, 0.57, 1.2)),
    "SM_Int_Dustpan": ("Dustpan", (0.33, 0.37, 0.1)),
    "SM_Int_TrashBag": ("Trash bag", (0.53, 0.46, 0.57)),
    "SM_Int_Boots": ("Rubber boots", (0.89, 0.27, 0.37)),
    "SM_Int_LifeJacket": ("Life jacket", (0.7, 0.18, 0.99)),
    "SM_Int_Hat": ("Fisherman's hat", (0.32, 0.35, 0.12)),
    "SM_Int_Drawers": ("Drawer cabinet", (1.14, 0.49, 1.88)),
    "SM_Int_Vitrine": ("Glass-fronted vintage cabinet", (2.02, 0.67, 2.24)),
    "SM_Int_MediaCabinet": ("Low wooden cabinet / TV stand", (2.44, 0.52, 0.68)),
    "SM_Int_ChineseCabinet": ("Lacquered cabinet", (1.26, 0.55, 2.87)),
    "SM_Int_Dresser": ("Wooden dresser", (1.72, 1.01, 1.09)),
    "SM_Int_WoodSofa": ("Painted wooden sofa", (2.45, 0.79, 1.28)),
    "SM_Int_LoungeChair": ("Lounge chair", (1.01, 1.19, 1.17)),
    "SM_Int_ChineseArmchair": ("Wooden armchair", (0.85, 0.79, 1.59)),
    "SM_Int_PlasticChair": ("Plastic chair", (0.64, 0.63, 0.88)),
    "SM_Int_FoldingStool": ("Folding wooden stool", (0.53, 0.55, 0.44)),
    "SM_Int_MetalStool": ("Metal stool", (0.35, 0.35, 0.88)),
    "SM_Int_RoundTableB": ("Round wooden table", (0.8, 0.8, 0.75)),
    "SM_Int_SmallTable": ("Small wooden table", (0.92, 0.44, 0.53)),
    "SM_Int_CoffeeTableB": ("Coffee table", (1.2, 0.6, 0.39)),
    "SM_Int_TallSideTable": ("Tall side table", (0.38, 0.38, 0.76)),
    "SM_Int_DiningTable": ("Dining table", (2.26, 1.39, 0.88)),
    "SM_Int_CafeTable": ("Cafe table", (0.83, 0.52, 0.49)),
    "SM_Int_CafeChair": ("Cafe chair", (0.58, 0.6, 1.03)),
    "SM_Int_DayBed": ("Day bed / infirmary bed", (1.97, 0.85, 1.13)),
    "SM_Int_MetalRack": ("Metal rack", (0.92, 0.6, 1.9)),
    "SM_Int_ToolCart": ("Tool cart", (1.27, 0.75, 0.96)),
    "SM_Int_Toolbox": ("Metal toolbox", (0.4, 0.29, 0.35)),
    "SM_Int_Ladder": ("Wooden ladder", (0.96, 0.5, 1.33)),
    "SM_Int_WallSconce": ("Wall sconce, wall at +Y; light added automatically", (0.15, 0.25, 0.34)),
    "SM_Int_WallLamp": ("Wall lamp, wall at +Y; light added automatically", (0.27, 0.14, 0.43)),
    "SM_Int_ChandelierB": ("Ornate chandelier, origin at the TOP; light added automatically", (0.75, 0.82, 0.8)),
    "SM_Int_LanternLamp": ("Paper lantern lamp, origin at the TOP; light added automatically", (0.88, 0.88, 0.75)),
    "SM_Int_Lantern": ("Wooden lantern", (0.22, 0.23, 0.53)),
    "SM_Int_CageLight": ("Caged hanging light, origin at the TOP; light added automatically", (1.16, 0.31, 0.75)),
    "SM_Int_PottedPlantC": ("Potted plant", (0.59, 0.64, 1.35)),
    "SM_Int_PlanterBox": ("Planter box", (0.91, 0.41, 0.42)),
    "SM_Int_Aircon": ("Outdoor air conditioner unit (exterior wall detail)", (1.8, 0.37, 0.93)),
    "SM_Int_UtilityBox": ("Utility box, wall at +Y", (0.52, 0.43, 1.12)),
    "SM_Int_SecurityLight": ("Security light, wall at +Y", (0.32, 0.42, 0.53)),
}

_DETAIL_MAT = {"Pot": MET, "Jug": WHT, "Bowl": W, "Cake": RED, "Apple": RED, "Bananas": GLD, "Lemon": GLD,
               "Laptop": MET, "Plant": GRN, "Aircon": WHT, "Lamp": GLD, "Light": MET, "Chandelier": GLD}


def _detail_builder(name, dims):
    mat = next((m for k, m in _DETAIL_MAT.items() if k in name), W)
    # wall sconces/lamps are base-origin (their light offset is positive z); ceiling fixtures hang from the top
    top = name in LIGHTS and name not in ("SM_Int_WallSconce", "SM_Int_WallLamp")
    def build():
        mb = MeshBuilder("d")
        z0 = -dims[2] if top else 0.0
        mb.box_mm((-dims[0] / 2, -dims[1] / 2, z0), (dims[0] / 2, dims[1] / 2, z0 + dims[2]), mat)
        return mb
    return build


LIGHTS.update({
    "SM_Int_ChandelierB": dict(offset=(0, 0, -0.45), color=(1.0, 0.86, 0.62), intensity=6000.0, radius=12.0, night_only=False),
    "SM_Int_LanternLamp": dict(offset=(0, 0, -0.5), color=(1.0, 0.78, 0.5), intensity=3500.0, radius=8.0, night_only=False),
    "SM_Int_CageLight": dict(offset=(0, 0, -0.55), color=(1.0, 0.84, 0.6), intensity=3500.0, radius=9.0, night_only=False),
    "SM_Int_WallSconce": dict(offset=(0, -0.10, 0.13), color=(1.0, 0.84, 0.6), intensity=1500.0, radius=5.0, night_only=False),
    "SM_Int_WallLamp": dict(offset=(0, -0.05, 0.22), color=(1.0, 0.84, 0.6), intensity=1500.0, radius=5.0, night_only=False),
})
for _n, (_desc, _dims) in DETAIL.items():
    CATALOG[_n] = f"{_desc} ({_dims[0]:.2f} x {_dims[1]:.2f} x {_dims[2]:.2f} m, real size)"
    BUILDERS[_n] = _detail_builder(_n, _dims)

assert set(BUILDERS) == set(CATALOG), set(BUILDERS) ^ set(CATALOG)


def collision(name, mb):
    """Simple box collision for the stand-ins (ceiling / wall decor gets none)."""
    if name in DETAIL and max(DETAIL[name][1]) < 0.8:
        return []
    if name in LIGHTS or name in ("SM_Int_CeilingFan", "SM_Int_Painting", "SM_Int_Frame", "SM_Int_Mirror",
                                  "SM_Int_WallClock", "SM_Int_Books", "SM_Int_RubberDuck", "SM_Int_Pillows",
                                  "SM_Int_Lifebuoy", "SM_Int_DeskLamp", "SM_Int_OilLamp", "SM_Int_Candelabra",
                                  "SM_Int_Kettle", "SM_Int_TeaSet", "SM_Int_ProjectorScreen"):
        return []
    (mn, mx) = mb.bounds()
    c = MeshBuilder("col")
    c.box_mm(mn, mx, "M_Concrete")
    return [c]
