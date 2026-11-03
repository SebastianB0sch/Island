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
    "SM_Int_SchoolDesk": "Single school desk ~0.76 m, user side -Y",
    "SM_Int_SchoolChair": "School chair ~0.82 m, seat faces -Y",
    "SM_Int_Armchair": "Upholstered armchair ~0.95 m, faces -Y",
    "SM_Int_Sofa": "Three-seat sofa 2.1 m wide, faces -Y",
    "SM_Int_SofaB": "Sofa 1.9 m, faces -Y",
    "SM_Int_WoodChair": "Painted wooden chair ~0.9 m, faces -Y",
    "SM_Int_DiningChair": "Upholstered dining chair ~1.0 m, faces -Y",
    "SM_Int_BarStool": "Round bar stool ~0.78 m",
    "SM_Int_Ottoman": "Ottoman / pouf ~0.45 m",
    "SM_Int_Stool": "Small wooden stool ~0.45 m",
    "SM_Int_GreenChair": "Upholstered occasional chair ~0.85 m, faces -Y",
    "SM_Int_OfficeChair": "Office arm chair ~0.95 m, faces -Y",
    "SM_Int_Bench": "Painted wooden settle (bench with a 1.2 m back) 1.6 m wide, faces -Y",
    "SM_Int_Table": "Low rectangular wooden table 1.8 x 0.66 m, 0.55 m high",
    "SM_Int_RoundTable": "Round wooden table ~0.75 m",
    "SM_Int_CoffeeTable": "Round coffee table 1.2 m across, 0.45 m high",
    "SM_Int_OfficeDesk": "Metal office desk ~0.76 m, user side -Y",
    "SM_Int_LowTable": "Low tea table ~0.38 m (kotatsu height)",
    "SM_Int_SideTable": "Side table ~0.6 m",
    "SM_Int_Console": "Classic console table ~0.85 m, back against a wall at +Y",
    "SM_Int_GrandBed": "Carved double bed 1.8 m wide, headboard at +Y",
    "SM_Int_Nightstand": "Nightstand ~0.6 m",
    "SM_Int_NightstandB": "Painted nightstand ~0.55 m",
    "SM_Int_Bookshelf": "Worn wooden bookshelf ~2 m, back at +Y",
    "SM_Int_Shelves": "Painted wooden shelves ~1.8 m, back at +Y",
    "SM_Int_SteelShelves": "Steel frame shelving ~2 m",
    "SM_Int_Cabinet": "Painted wooden sideboard 1.84 x 0.96 m, 1.8 m high, back at +Y",
    "SM_Int_Wardrobe": "Carved wardrobe 1.54 x 1.0 m, 2.1 m high, back at +Y",
    "SM_Int_DisplayShelves": "Open display shelves ~1.8 m, back at +Y",
    "SM_Int_Chandelier": "Chandelier ~1.1 m tall, origin at the TOP (place at the ceiling); light added automatically",
    "SM_Int_CeilingLamp": "Pendant ceiling lamp ~0.6 m, origin at the TOP; light added automatically",
    "SM_Int_IndustrialLamp": "Hanging industrial lamp ~0.9 m, origin at the TOP; light added automatically",
    "SM_Int_CeilingFan": "Ceiling fan 1.3 m span, origin at the TOP",
    "SM_Int_DeskLamp": "Arm desk lamp ~0.5 m",
    "SM_Int_OilLamp": "Vintage oil lamp ~0.45 m",
    "SM_Int_PottedPlant": "Potted succulent ~0.6 m",
    "SM_Int_PottedPlantB": "Large potted plant ~1.4 m",
    "SM_Int_Painting": "Gilded picture frame 1 m wide, wall at +Y (origin bottom centre)",
    "SM_Int_Frame": "Hanging picture frame 0.6 m, wall at +Y",
    "SM_Int_Mirror": "Ornate wall mirror ~1.2 m, wall at +Y",
    "SM_Int_WallClock": "Wall clock 0.4 m, wall at +Y",
    "SM_Int_GrandfatherClock": "Grandfather clock ~2.1 m, back at +Y",
    "SM_Int_Chalkboard": "Standing chalkboard ~1.6 m",
    "SM_Int_TV": "Old CRT television ~0.45 m, screen -Y",
    "SM_Int_Register": "Cash register ~0.3 m",
    "SM_Int_Bust": "Marble bust ~0.7 m (place on a plinth)",
    "SM_Int_Books": "Row of books 0.5 m",
    "SM_Int_Box": "Cardboard box ~0.45 m",
    "SM_Int_Lifebuoy": "Lifebuoy ~0.75 m, wall at +Y",
    "SM_Int_Radio": "Radio transceiver ~0.35 m",
    "SM_Int_Extinguisher": "Fire extinguisher ~0.6 m",
    "SM_Int_WetFloor": "Wet floor sign ~0.62 m",
    "SM_Int_Basket": "Wicker basket ~0.3 m",
    "SM_Int_Bucket": "Wooden bucket ~0.3 m",
    "SM_Int_FoldingScreen": "Folding screen ~1.8 m",
    "SM_Int_Pillows": "Pair of throw pillows 0.9 m",
    "SM_Int_Suitcase": "Suitcase ~0.45 m",
    "SM_Int_Stove": "Electric stove ~0.9 m, front -Y",
    "SM_Int_Candelabra": "Brass candle holders ~0.4 m",
    "SM_Int_OldBed": "Old iron bed frame ~1 m wide",
    "SM_Int_RockingChair": "Rocking chair ~1 m, faces -Y",
    "SM_Int_ProjectorScreen": "Projector screen 2 m",
    "SM_Int_HandTruck": "Hand truck ~1.2 m",
    "SM_Int_RubberDuck": "Rubber duck 0.12 m",
    "SM_Int_Microwave": "Microwave ~0.3 m, front -Y",
    "SM_Int_Kettle": "Electric kettle ~0.25 m",
    "SM_Int_TeaSet": "Tea set on tray 0.5 m",
}

# lights that come with a fixture (offset from the origin, metres) - interiors are lit day and night
LIGHTS = {
    "SM_Int_Chandelier": dict(offset=(0, 0, -0.75), color=(1.0, 0.86, 0.62), intensity=6000.0, radius=12.0, night_only=False),
    "SM_Int_CeilingLamp": dict(offset=(0, 0, -0.55), color=(1.0, 0.88, 0.70), intensity=3500.0, radius=8.0, night_only=False),
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
    "SM_Int_DeskLamp": lambda: hanging(0.1, 0.5, MET),
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

assert set(BUILDERS) == set(CATALOG), set(BUILDERS) ^ set(CATALOG)


def collision(name, mb):
    """Simple box collision for the stand-ins (ceiling / wall decor gets none)."""
    if name in LIGHTS or name in ("SM_Int_CeilingFan", "SM_Int_Painting", "SM_Int_Frame", "SM_Int_Mirror",
                                  "SM_Int_WallClock", "SM_Int_Books", "SM_Int_RubberDuck", "SM_Int_Pillows",
                                  "SM_Int_Lifebuoy", "SM_Int_DeskLamp", "SM_Int_OilLamp", "SM_Int_Candelabra",
                                  "SM_Int_Kettle", "SM_Int_TeaSet", "SM_Int_ProjectorScreen"):
        return []
    (mn, mx) = mb.bounds()
    c = MeshBuilder("col")
    c.box_mm(mn, mx, "M_Concrete")
    return [c]
