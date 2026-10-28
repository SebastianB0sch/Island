"""
Material palette - the single source of truth for every material slot name.

Colours are written in sRGB (0..1) for readability and converted to linear for
both the Blender preview materials and the exported materials.json that the
Unreal build script turns into Material Instances.

kind:
  opaque    - M_DA_Master (base colour * detail grunge, optional normal map)
  glass     - M_DA_Glass  (translucent, used for real openings you can see through)
  emissive  - M_DA_Emissive (unlit glow; lamps, screens, duel field lines)
  foliage   - M_DA_Foliage (two-sided, gentle wind sway via WPO)
  water     - M_DA_Water (single layer water)
  lava      - M_DA_Lava (panning emissive)
  hologram  - M_DA_Hologram (additive, pulsing)
  smoke     - M_DA_Smoke (translucent, per-instance fade)
  terrain   - M_DA_Terrain (splat-mapped)
  beam      - M_DA_Beam (additive cone)
  waterfall - M_DA_Waterfall (panning translucent water sheet)

detail: name of a tileable detail texture (T_<detail>_D / _N) or None.
tiling: UV tiling multiplier (mesh UVs are 1 unit = 1 metre).
"""

def _c(r, g, b):
    return (r, g, b)


MATERIALS = {
    # ------------------------------------------------------------ generic architecture
    "M_WhiteWall":      dict(kind="opaque", color=_c(0.92, 0.91, 0.87), rough=0.85, detail="Plaster", tiling=0.5),
    "M_CreamWall":      dict(kind="opaque", color=_c(0.90, 0.84, 0.68), rough=0.9, detail="Plaster", tiling=0.5),
    "M_Marble":         dict(kind="opaque", color=_c(0.93, 0.93, 0.91), rough=0.25, detail="Marble", tiling=0.25),
    "M_MarbleFloor":    dict(kind="opaque", color=_c(0.82, 0.80, 0.76), rough=0.15, detail="FloorTiles", tiling=0.5),
    "M_Concrete":       dict(kind="opaque", color=_c(0.62, 0.62, 0.60), rough=0.95, detail="Concrete", tiling=0.25),
    "M_DarkConcrete":   dict(kind="opaque", color=_c(0.38, 0.38, 0.38), rough=0.95, detail="Concrete", tiling=0.25),
    "M_Paving":         dict(kind="opaque", color=_c(0.78, 0.74, 0.68), rough=0.9, detail="Paving", tiling=0.5),
    "M_Asphalt":        dict(kind="opaque", color=_c(0.22, 0.22, 0.23), rough=0.9, detail="Concrete", tiling=0.25),
    "M_Glass":          dict(kind="opaque", color=_c(0.10, 0.17, 0.27), rough=0.05, metallic=0.6, detail=None),
    "M_GlassClear":     dict(kind="glass", color=_c(0.60, 0.75, 0.85), rough=0.02, opacity=0.25, detail=None),
    "M_WindowFrame":    dict(kind="opaque", color=_c(0.95, 0.95, 0.95), rough=0.6, detail=None),
    "M_Gold":           dict(kind="opaque", color=_c(0.95, 0.72, 0.22), rough=0.3, metallic=1.0, detail=None),
    "M_Metal":          dict(kind="opaque", color=_c(0.60, 0.62, 0.65), rough=0.45, metallic=1.0, detail=None),
    "M_DarkMetal":      dict(kind="opaque", color=_c(0.15, 0.16, 0.18), rough=0.5, metallic=1.0, detail=None),
    "M_RustMetal":      dict(kind="opaque", color=_c(0.42, 0.22, 0.12), rough=0.9, metallic=0.4, detail="Grunge", tiling=0.5),
    "M_Wood":           dict(kind="opaque", color=_c(0.55, 0.38, 0.22), rough=0.8, detail="Planks", tiling=0.5),
    "M_DarkWood":       dict(kind="opaque", color=_c(0.30, 0.20, 0.12), rough=0.8, detail="Planks", tiling=0.5),
    "M_RottenWood":     dict(kind="opaque", color=_c(0.24, 0.20, 0.15), rough=0.95, detail="Planks", tiling=0.5),
    "M_Fabric":         dict(kind="opaque", color=_c(0.70, 0.12, 0.10), rough=0.95, detail=None),
    "M_Black":          dict(kind="opaque", color=_c(0.03, 0.03, 0.035), rough=0.6, detail=None),
    "M_Rubber":         dict(kind="opaque", color=_c(0.08, 0.08, 0.08), rough=0.9, detail=None),

    # ------------------------------------------------------------ Duel Academy main building
    "M_AcademyWall":    dict(kind="opaque", color=_c(0.94, 0.94, 0.92), rough=0.7, detail="Plaster", tiling=0.4),
    "M_AcademyBlue":    dict(kind="opaque", color=_c(0.10, 0.25, 0.62), rough=0.55, detail=None),
    "M_AcademyRoof":    dict(kind="opaque", color=_c(0.13, 0.32, 0.72), rough=0.45, detail="RoofTiles", tiling=0.5),
    "M_AcademyRed":     dict(kind="opaque", color=_c(0.72, 0.10, 0.08), rough=0.55, detail=None),
    "M_AcademyYellow":  dict(kind="opaque", color=_c(0.96, 0.78, 0.18), rough=0.55, detail=None),
    "M_ArenaFloor":     dict(kind="opaque", color=_c(0.10, 0.11, 0.15), rough=0.3, detail="FloorTiles", tiling=0.25),
    "M_ArenaSeat":      dict(kind="opaque", color=_c(0.12, 0.22, 0.55), rough=0.7, detail=None),
    "M_DuelFieldGlow":  dict(kind="emissive", color=_c(0.25, 0.85, 1.00), strength=12.0),
    "M_EmblemGlow":     dict(kind="emissive", color=_c(1.00, 0.75, 0.25), strength=4.0),
    "M_Screen":         dict(kind="emissive", color=_c(0.30, 0.55, 0.95), strength=3.0),
    "M_Carpet":         dict(kind="opaque", color=_c(0.55, 0.08, 0.10), rough=1.0, detail="Fabric", tiling=1.0),
    "M_ShopShelf":      dict(kind="opaque", color=_c(0.82, 0.70, 0.52), rough=0.6, detail="Planks", tiling=0.5),
    "M_CardPack":       dict(kind="opaque", color=_c(0.85, 0.45, 0.10), rough=0.35, metallic=0.3, detail=None),

    # ------------------------------------------------------------ Slifer Red
    "M_SliferWall":     dict(kind="opaque", color=_c(0.88, 0.80, 0.62), rough=0.9, detail="Siding", tiling=0.5),
    "M_SliferRoof":     dict(kind="opaque", color=_c(0.60, 0.07, 0.05), rough=0.6, detail="Corrugated", tiling=0.5),
    "M_SliferTrim":     dict(kind="opaque", color=_c(0.50, 0.08, 0.06), rough=0.7, detail=None),
    "M_SliferDoor":     dict(kind="opaque", color=_c(0.62, 0.12, 0.08), rough=0.6, detail=None),

    # ------------------------------------------------------------ Ra Yellow
    "M_RaWall":         dict(kind="opaque", color=_c(0.97, 0.82, 0.30), rough=0.85, detail="Plaster", tiling=0.5),
    "M_RaRoof":         dict(kind="opaque", color=_c(0.62, 0.30, 0.12), rough=0.7, detail="RoofTiles", tiling=0.5),
    "M_RaTrim":         dict(kind="opaque", color=_c(0.96, 0.95, 0.90), rough=0.6, detail=None),

    # ------------------------------------------------------------ Obelisk Blue
    "M_ObeliskWall":    dict(kind="opaque", color=_c(0.95, 0.95, 0.96), rough=0.6, detail="Plaster", tiling=0.4),
    "M_ObeliskRoof":    dict(kind="opaque", color=_c(0.10, 0.20, 0.55), rough=0.45, detail="RoofTiles", tiling=0.5),
    "M_ObeliskTrim":    dict(kind="opaque", color=_c(0.12, 0.28, 0.70), rough=0.5, detail=None),
    "M_GirlsRoof":      dict(kind="opaque", color=_c(0.38, 0.58, 0.88), rough=0.45, detail="RoofTiles", tiling=0.5),
    "M_GirlsTrim":      dict(kind="opaque", color=_c(0.94, 0.66, 0.74), rough=0.55, detail=None),

    # ------------------------------------------------------------ Abandoned dorm
    "M_OldStone":       dict(kind="opaque", color=_c(0.36, 0.35, 0.37), rough=0.95, detail="Bricks", tiling=0.5),
    "M_OldRoof":        dict(kind="opaque", color=_c(0.16, 0.16, 0.19), rough=0.9, detail="RoofTiles", tiling=0.5),
    "M_Ivy":            dict(kind="foliage", color=_c(0.16, 0.30, 0.12), rough=0.9, detail=None),
    "M_Boards":         dict(kind="opaque", color=_c(0.35, 0.28, 0.20), rough=0.95, detail="Planks", tiling=0.5),

    # ------------------------------------------------------------ Harbor
    "M_HarborConcrete": dict(kind="opaque", color=_c(0.66, 0.65, 0.62), rough=0.95, detail="Concrete", tiling=0.25),
    "M_PierWood":       dict(kind="opaque", color=_c(0.45, 0.34, 0.24), rough=0.9, detail="Planks", tiling=0.5),
    "M_LighthouseWhite":dict(kind="opaque", color=_c(0.96, 0.96, 0.94), rough=0.6, detail="Plaster", tiling=0.5),
    "M_LighthouseRed":  dict(kind="opaque", color=_c(0.80, 0.10, 0.08), rough=0.5, detail=None),
    "M_LighthouseLamp": dict(kind="emissive", color=_c(1.00, 0.92, 0.65), strength=25.0),
    "M_WarehouseWall":  dict(kind="opaque", color=_c(0.48, 0.56, 0.62), rough=0.7, metallic=0.3, detail="Corrugated", tiling=0.5),
    "M_ShipHull":       dict(kind="opaque", color=_c(0.95, 0.95, 0.96), rough=0.4, detail=None),
    "M_ShipStripe":     dict(kind="opaque", color=_c(0.08, 0.25, 0.70), rough=0.4, detail=None),
    "M_ShipBottom":     dict(kind="opaque", color=_c(0.55, 0.10, 0.08), rough=0.6, detail=None),
    "M_HelipadMark":    dict(kind="opaque", color=_c(0.95, 0.85, 0.15), rough=0.6, detail=None),
    "M_CrateRed":       dict(kind="opaque", color=_c(0.60, 0.15, 0.10), rough=0.7, metallic=0.3, detail="Corrugated", tiling=1.0),
    "M_CrateBlue":      dict(kind="opaque", color=_c(0.12, 0.30, 0.60), rough=0.7, metallic=0.3, detail="Corrugated", tiling=1.0),
    "M_CrateYellow":    dict(kind="opaque", color=_c(0.85, 0.65, 0.12), rough=0.7, metallic=0.3, detail="Corrugated", tiling=1.0),

    # ------------------------------------------------------------ Gym / hot springs
    "M_GymRoof":        dict(kind="opaque", color=_c(0.25, 0.55, 0.50), rough=0.4, metallic=0.5, detail=None),
    "M_CourtFloor":     dict(kind="opaque", color=_c(0.70, 0.48, 0.28), rough=0.35, detail="Planks", tiling=0.5),
    "M_CourtLine":      dict(kind="opaque", color=_c(0.95, 0.95, 0.95), rough=0.5, detail=None),
    "M_HotWater":       dict(kind="water", color=_c(0.45, 0.75, 0.72), rough=0.05, detail=None),
    "M_OnsenRock":      dict(kind="opaque", color=_c(0.40, 0.38, 0.36), rough=0.8, detail="Rock", tiling=0.5),
    "M_ShojiPaper":     dict(kind="opaque", color=_c(0.95, 0.92, 0.82), rough=0.9, detail=None),

    # ------------------------------------------------------------ nature
    "M_Bark":           dict(kind="opaque", color=_c(0.36, 0.26, 0.18), rough=0.95, detail="Bark", tiling=1.0),
    "M_PalmBark":       dict(kind="opaque", color=_c(0.55, 0.45, 0.32), rough=0.95, detail="Bark", tiling=1.0),
    "M_DeadBark":       dict(kind="opaque", color=_c(0.30, 0.27, 0.24), rough=0.95, detail="Bark", tiling=1.0),
    "M_LeavesBroad":    dict(kind="foliage", color=_c(0.20, 0.45, 0.14), rough=0.8, detail=None),
    "M_LeavesDark":     dict(kind="foliage", color=_c(0.12, 0.32, 0.12), rough=0.8, detail=None),
    "M_LeavesPalm":     dict(kind="foliage", color=_c(0.30, 0.55, 0.15), rough=0.8, detail=None),
    "M_LeavesPine":     dict(kind="foliage", color=_c(0.10, 0.28, 0.16), rough=0.85, detail=None),
    "M_LeavesBush":     dict(kind="foliage", color=_c(0.22, 0.48, 0.18), rough=0.85, detail=None),
    "M_Hedge":          dict(kind="opaque", color=_c(0.15, 0.38, 0.13), rough=0.9, detail="Leaves", tiling=1.0),
    "M_Grass":          dict(kind="foliage", color=_c(0.35, 0.58, 0.18), rough=0.9, detail=None),
    "M_FlowerRed":      dict(kind="foliage", color=_c(0.90, 0.15, 0.20), rough=0.7, detail=None),
    "M_FlowerYellow":   dict(kind="foliage", color=_c(0.98, 0.85, 0.20), rough=0.7, detail=None),
    "M_FlowerBlue":     dict(kind="foliage", color=_c(0.35, 0.45, 0.95), rough=0.7, detail=None),
    "M_FlowerWhite":    dict(kind="foliage", color=_c(0.96, 0.96, 0.96), rough=0.7, detail=None),
    "M_Rock":           dict(kind="opaque", color=_c(0.48, 0.46, 0.43), rough=0.9, detail="Rock", tiling=0.25),
    "M_VolcanicRock":   dict(kind="opaque", color=_c(0.20, 0.18, 0.18), rough=0.9, detail="Rock", tiling=0.25),
    "M_Sand":           dict(kind="opaque", color=_c(0.90, 0.82, 0.62), rough=1.0, detail="Sand", tiling=0.5),
    "M_Soil":           dict(kind="opaque", color=_c(0.35, 0.26, 0.18), rough=1.0, detail="Dirt", tiling=0.5),

    # ------------------------------------------------------------ special effects / water
    "M_Ocean":          dict(kind="water", color=_c(0.05, 0.35, 0.50), rough=0.05, detail=None),
    "M_LakeWater":      dict(kind="water", color=_c(0.10, 0.45, 0.45), rough=0.05, detail=None),
    "M_Lava":           dict(kind="lava", color=_c(1.00, 0.35, 0.05), strength=40.0),
    "M_Waterfall":      dict(kind="waterfall", color=_c(0.85, 0.95, 1.00), opacity=0.8),
    "M_Hologram":       dict(kind="hologram", color=_c(0.30, 0.90, 1.00), strength=6.0),
    "M_CardBack":       dict(kind="emissive", color=_c(0.65, 0.40, 0.18), strength=2.5, texture="T_CardBack"),
    "M_Smoke":          dict(kind="smoke", color=_c(0.55, 0.55, 0.57), opacity=0.5),
    "M_Steam":          dict(kind="smoke", color=_c(0.95, 0.95, 0.97), opacity=0.35),
    "M_LampGlow":       dict(kind="emissive", color=_c(1.00, 0.85, 0.55), strength=15.0),
    "M_Beam":           dict(kind="beam", color=_c(1.00, 0.93, 0.70), strength=1.5),
    "M_Terrain":        dict(kind="terrain", color=_c(0.4, 0.6, 0.3), rough=0.95, detail=None),

    # ------------------------------------------------------------ avatar
    "M_Skin":           dict(kind="opaque", color=_c(0.96, 0.80, 0.68), rough=0.6, detail=None),
    "M_Hair":           dict(kind="opaque", color=_c(0.35, 0.20, 0.10), rough=0.6, detail=None),
    "M_Jacket":         dict(kind="opaque", color=_c(0.75, 0.08, 0.06), rough=0.8, detail="Fabric", tiling=2.0),
    "M_Shirt":          dict(kind="opaque", color=_c(0.12, 0.12, 0.14), rough=0.9, detail="Fabric", tiling=2.0),
    "M_Pants":          dict(kind="opaque", color=_c(0.15, 0.17, 0.25), rough=0.9, detail="Fabric", tiling=2.0),
    "M_Shoes":          dict(kind="opaque", color=_c(0.25, 0.10, 0.06), rough=0.5, detail=None),
    "M_DuelDisk":       dict(kind="opaque", color=_c(0.70, 0.72, 0.76), rough=0.35, metallic=0.8, detail=None),
}

# Jacket colours per dorm (used by the character's dynamic material)
DORM_JACKETS = {
    "slifer": _c(0.75, 0.08, 0.06),
    "ra": _c(0.96, 0.80, 0.15),
    "obelisk": _c(0.12, 0.28, 0.72),
    "white": _c(0.95, 0.95, 0.95),
}

TERRAIN_LAYERS = [
    # name, srgb tint used for the minimap / Blender preview
    ("Grass", (0.34, 0.52, 0.20)),
    ("Sand", (0.88, 0.80, 0.60)),
    ("Rock", (0.45, 0.43, 0.40)),
    ("Dirt", (0.50, 0.38, 0.25)),
    ("Paving", (0.75, 0.72, 0.66)),
    ("Ash", (0.20, 0.18, 0.18)),
    ("ForestFloor", (0.22, 0.30, 0.13)),
    ("WetSand", (0.60, 0.52, 0.38)),
]


def srgb_to_linear(c):
    def f(x):
        return x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4
    return tuple(f(x) for x in c)


def material_json():
    """Serializable material table with linear colours (consumed by the UE build script)."""
    out = {}
    for name, m in MATERIALS.items():
        d = dict(m)
        d["color_linear"] = srgb_to_linear(m["color"])
        d.setdefault("rough", 0.8)
        d.setdefault("metallic", 0.0)
        d.setdefault("detail", None)
        d.setdefault("tiling", 1.0)
        d.setdefault("strength", 1.0)
        d.setdefault("opacity", 1.0)
        out[name] = d
    return out


def register(materials):
    """Let asset modules add their own palette entries (call at module import time).
    Existing names are never overwritten."""
    for k, v in materials.items():
        MATERIALS.setdefault(k, v)
