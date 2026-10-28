"""
Builds the Duel Academy master materials (node graphs created in code) and one
Material Instance per palette entry (Data/materials.json).

Masters (in /Game/DuelAcademy/Materials):
  M_DA_Master      opaque PBR: Tint * detail texture, detail normal
  M_DA_Foliage     two-sided, wind sway (world position offset)
  M_DA_Glass       translucent glass
  M_DA_Emissive    glowing surfaces; brighter at night (MPC NightFactor)
  M_DA_Water       single layer water (ocean, lake, hot springs)
  M_DA_Lava        panning emissive lava
  M_DA_Hologram    additive hologram (duel monsters, markers)
  M_DA_Smoke       translucent puffs, opacity from per-instance custom data
  M_DA_Beam        additive light beam
  M_DA_Waterfall   translucent panning water sheet
  M_DA_Terrain     splat-mapped terrain (8 layers)
  MPC_DuelAcademy  NightFactor / TimeOfDay (driven by ADAIslandManager)
"""

import unreal

from . import common as C

MEL = unreal.MaterialEditingLibrary


class Graph:
    """Tiny helper around MaterialEditingLibrary."""

    def __init__(self, name, folder=C.MAT_DIR):
        path = f"{folder}/{name}"
        if C.exists(path):
            unreal.EditorAssetLibrary.delete_asset(path)
        self.mat = C.asset_tools().create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())
        self.name = name
        self.x = -1600
        self.y = 0

    def node(self, cls, **props):
        n = MEL.create_material_expression(self.mat, cls, self.x, self.y)
        self.y += 140
        if self.y > 2400:
            self.y = 0
            self.x += 320
        for k, v in props.items():
            try:
                n.set_editor_property(k, v)
            except Exception as e:  # noqa: BLE001
                C.warn(f"{self.name}: {cls.__name__}.{k}: {e}")
        return n

    # ---- typed shortcuts
    def scalar(self, name, value):
        return self.node(unreal.MaterialExpressionScalarParameter, parameter_name=name, default_value=float(value))

    def vector(self, name, rgb, a=1.0):
        return self.node(unreal.MaterialExpressionVectorParameter, parameter_name=name, default_value=C.lc(rgb, a))

    def const(self, v):
        return self.node(unreal.MaterialExpressionConstant, r=float(v))

    def const3(self, rgb):
        return self.node(unreal.MaterialExpressionConstant3Vector, constant=C.lc(rgb))

    def tex(self, name, texture, sampler, uv=None, param=True):
        cls = unreal.MaterialExpressionTextureSampleParameter2D if param else unreal.MaterialExpressionTextureSample
        props = dict(texture=texture, sampler_type=sampler)
        if param:
            props["parameter_name"] = name
        n = self.node(cls, **props)
        try:
            n.set_editor_property("sampler_source", unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS)
        except Exception:  # noqa: BLE001
            pass
        if uv is not None:
            self.link(uv, "", n, "UVs")
        return n

    def link(self, a, a_out, b, b_in):
        names = [b_in] + {"ScatteringCoefficients": ["Scattering Coefficients"],
                          "AbsorptionCoefficients": ["Absorption Coefficients"],
                          "PhaseG": ["Phase G"], "ColorScaleBehindWater": ["Color Scale Behind Water"],
                          "Alpha": ["Alpha", "Lerp Alpha"]}.get(b_in, [])
        for nm in names:
            try:
                if MEL.connect_material_expressions(a, a_out, b, nm):
                    return True
            except Exception:  # noqa: BLE001
                pass
        C.warn(f"{self.name}: could not connect -> {type(b).__name__}.{b_in}")
        return False

    def op(self, cls, a, b, a_out="", b_out=""):
        n = self.node(cls)
        self.link(a, a_out, n, "A")
        self.link(b, b_out, n, "B")
        return n

    def mul(self, a, b, a_out="", b_out=""):
        return self.op(unreal.MaterialExpressionMultiply, a, b, a_out, b_out)

    def add(self, a, b, a_out="", b_out=""):
        return self.op(unreal.MaterialExpressionAdd, a, b, a_out, b_out)

    def sub(self, a, b, a_out="", b_out=""):
        return self.op(unreal.MaterialExpressionSubtract, a, b, a_out, b_out)

    def lerp(self, a, b, alpha, a_out="", b_out="", alpha_out=""):
        n = self.node(unreal.MaterialExpressionLinearInterpolate)
        self.link(a, a_out, n, "A")
        self.link(b, b_out, n, "B")
        self.link(alpha, alpha_out, n, "Alpha")
        return n

    def one_input(self, cls, src, src_out="", **props):
        n = self.node(cls, **props)
        self.link(src, src_out, n, "")
        return n

    def out(self, node, prop, node_out=""):
        try:
            MEL.connect_material_property(node, node_out, prop)
        except Exception as e:  # noqa: BLE001
            C.warn(f"{self.name}: output {prop}: {e}")

    def settings(self, **props):
        for k, v in props.items():
            try:
                self.mat.set_editor_property(k, v)
            except Exception as e:  # noqa: BLE001
                C.warn(f"{self.name}: setting {k}: {e}")

    def finish(self):
        try:
            self.mat.set_editor_property("used_with_instanced_static_meshes", True)
        except Exception:  # noqa: BLE001
            pass
        MEL.layout_material_expressions(self.mat)
        MEL.recompile_material(self.mat)
        unreal.EditorAssetLibrary.save_loaded_asset(self.mat)
        return self.mat


def T(name):
    return C.load(f"{C.TEX_DIR}/{name}")


S_LIN = unreal.MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR
S_NRM = unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL
S_MSK = unreal.MaterialSamplerType.SAMPLERTYPE_MASKS
S_COL = unreal.MaterialSamplerType.SAMPLERTYPE_COLOR


# --------------------------------------------------------------------------- MPC
def build_mpc():
    path = f"{C.MAT_DIR}/MPC_DuelAcademy"
    mpc = C.load(path)
    if mpc is None:
        mpc = C.asset_tools().create_asset("MPC_DuelAcademy", C.MAT_DIR, unreal.MaterialParameterCollection,
                                          unreal.MaterialParameterCollectionFactoryNew())
    params = []
    for n, v in (("NightFactor", 0.0), ("TimeOfDay", 16.0)):
        p = unreal.CollectionScalarParameter()
        p.set_editor_property("parameter_name", n)
        p.set_editor_property("default_value", v)
        params.append(p)
    mpc.set_editor_property("scalar_parameters", params)
    unreal.EditorAssetLibrary.save_loaded_asset(mpc)
    return mpc


def night_factor(g, mpc):
    return g.node(unreal.MaterialExpressionCollectionParameter, collection=mpc, parameter_name="NightFactor")


# --------------------------------------------------------------------------- masters
def build_master():
    g = Graph("M_DA_Master")
    uv = g.node(unreal.MaterialExpressionTextureCoordinate)
    tiling = g.scalar("Tiling", 1.0)
    uvt = g.mul(uv, tiling)
    tint = g.vector("Tint", (1, 1, 1))
    det = g.tex("DetailTex", T("T_Grunge_D"), S_LIN, uvt)
    det2 = g.mul(det, g.const(2.0), "R")
    strength = g.scalar("DetailStrength", 1.0)
    detail = g.lerp(g.const(1.0), det2, strength)
    base = g.mul(tint, detail)
    g.out(base, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.scalar("Roughness", 0.8), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.scalar("Metallic", 0.0), unreal.MaterialProperty.MP_METALLIC)
    nrm = g.tex("DetailNormal", T("T_Plaster_N"), S_NRM, uvt)
    flat = g.const3((0, 0, 1))
    n = g.lerp(flat, nrm, g.scalar("NormalStrength", 0.0), "", "RGB")
    g.out(n, unreal.MaterialProperty.MP_NORMAL)
    return g.finish()


def build_foliage():
    g = Graph("M_DA_Foliage")
    g.settings(two_sided=True)
    tint = g.vector("Tint", (0.2, 0.5, 0.15))
    # subtle per-object colour variation
    obj = g.node(unreal.MaterialExpressionObjectPositionWS)
    var = g.one_input(unreal.MaterialExpressionFrac, g.mul(obj, g.const(0.0013), "", ""), "")
    varm = g.one_input(unreal.MaterialExpressionComponentMask, var, r=True, g=False, b=False, a=False)
    shade = g.lerp(g.const(0.85), g.const(1.15), varm)
    g.out(g.mul(tint, shade), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.scalar("Roughness", 0.85), unreal.MaterialProperty.MP_ROUGHNESS)
    try:
        g.out(g.const3((0.05, 0.12, 0.02)), unreal.MaterialProperty.MP_SUBSURFACE_COLOR)
    except Exception:  # noqa: BLE001
        pass
    # wind: sin(time + world xy) * amount * height above the object's pivot
    wp = g.node(unreal.MaterialExpressionWorldPosition)
    t = g.node(unreal.MaterialExpressionTime)
    wpx = g.one_input(unreal.MaterialExpressionComponentMask, wp, r=True, g=False, b=False, a=False)
    wpy = g.one_input(unreal.MaterialExpressionComponentMask, wp, r=False, g=True, b=False, a=False)
    phase = g.add(g.mul(t, g.scalar("WindSpeed", 1.6)), g.mul(g.add(wpx, wpy), g.const(0.004)))
    sway = g.mul(g.one_input(unreal.MaterialExpressionSine, phase), g.scalar("WindAmount", 7.0))
    wpz = g.one_input(unreal.MaterialExpressionComponentMask, wp, r=False, g=False, b=True, a=False)
    objz = g.one_input(unreal.MaterialExpressionComponentMask, obj, r=False, g=False, b=True, a=False)
    height = g.one_input(unreal.MaterialExpressionSaturate, g.mul(g.sub(wpz, objz), g.const(0.0015)))
    amt = g.mul(sway, height)
    xy = g.node(unreal.MaterialExpressionAppendVector)
    g.link(amt, "", xy, "A")
    g.link(g.mul(amt, g.const(0.6)), "", xy, "B")
    xyz = g.node(unreal.MaterialExpressionAppendVector)
    g.link(xy, "", xyz, "A")
    g.link(g.const(0.0), "", xyz, "B")
    g.out(xyz, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    return g.finish()


def build_glass():
    g = Graph("M_DA_Glass")
    g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT, two_sided=True)
    try:
        g.settings(translucency_lighting_mode=unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    except Exception:  # noqa: BLE001
        pass
    g.out(g.vector("Tint", (0.6, 0.75, 0.85)), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.scalar("Roughness", 0.02), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.const(1.0), unreal.MaterialProperty.MP_SPECULAR)
    fres = g.node(unreal.MaterialExpressionFresnel, exponent=3.0)
    op = g.lerp(g.scalar("Opacity", 0.25), g.const(0.85), fres)
    g.out(op, unreal.MaterialProperty.MP_OPACITY)
    return g.finish()


def build_emissive(mpc):
    g = Graph("M_DA_Emissive")
    g.settings(two_sided=True)
    color = g.vector("Tint", (1, 0.85, 0.55))
    tex = g.tex("EmissiveTex", T("T_White") or T("T_Plaster_D"), S_COL,
                g.node(unreal.MaterialExpressionTextureCoordinate))
    use_tex = g.scalar("UseTexture", 0.0)
    texmix = g.lerp(g.const3((1, 1, 1)), tex, use_tex, "", "RGB")
    strength = g.scalar("Strength", 10.0)
    night = night_factor(g, mpc)
    boost = g.lerp(g.const(1.0), g.lerp(g.const(0.12), g.const(1.0), night), g.scalar("NightOnly", 0.0))
    em = g.mul(g.mul(g.mul(color, texmix), strength), boost)
    g.out(em, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    g.out(g.mul(color, texmix), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.const(0.4), unreal.MaterialProperty.MP_ROUGHNESS)
    return g.finish()


def build_water():
    g = Graph("M_DA_Water")
    ok = True
    try:
        g.settings(shading_model=unreal.MaterialShadingModel.MSM_SINGLE_LAYER_WATER)
    except Exception:  # noqa: BLE001
        ok = False
    wp = g.node(unreal.MaterialExpressionWorldPosition)
    xy = g.one_input(unreal.MaterialExpressionComponentMask, wp, r=True, g=True, b=False, a=False)
    scale = g.scalar("WaveScale", 0.0012)
    uv1 = g.mul(xy, scale)
    p1 = g.node(unreal.MaterialExpressionPanner, speed_x=0.015, speed_y=0.008)
    g.link(uv1, "", p1, "Coordinate")
    p2 = g.node(unreal.MaterialExpressionPanner, speed_x=-0.011, speed_y=0.017)
    g.link(g.mul(uv1, g.const(0.37)), "", p2, "Coordinate")
    n1 = g.tex("Normal1", T("T_WaterNormal"), S_NRM, p1, param=False)
    n2 = g.tex("Normal2", T("T_WaterNormal"), S_NRM, p2, param=False)
    n = g.add(n1, n2, "RGB", "RGB")
    nn = g.lerp(g.const3((0, 0, 1)), n, g.scalar("WaveStrength", 0.45))
    g.out(nn, unreal.MaterialProperty.MP_NORMAL)
    g.out(g.const(0.03), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.const(0.0), unreal.MaterialProperty.MP_METALLIC)
    scatter = g.vector("ScatterColor", (0.02, 0.18, 0.22))
    absorb = g.vector("Absorption", (0.45, 0.06, 0.04))
    if ok:
        g.out(g.const3((0.0, 0.0, 0.0)), unreal.MaterialProperty.MP_BASE_COLOR)
        slw = g.node(unreal.MaterialExpressionSingleLayerWaterMaterialOutput)
        g.link(scatter, "", slw, "ScatteringCoefficients")
        g.link(absorb, "", slw, "AbsorptionCoefficients")
        g.link(g.const(0.2), "", slw, "PhaseG")
    else:
        g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT)
        g.out(g.mul(scatter, g.const(3.0)), unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(g.const(0.85), unreal.MaterialProperty.MP_OPACITY)
    return g.finish()


def build_lava():
    g = Graph("M_DA_Lava")
    uv = g.node(unreal.MaterialExpressionTextureCoordinate)
    uvs = g.mul(uv, g.scalar("Tiling", 0.08))
    p1 = g.node(unreal.MaterialExpressionPanner, speed_x=0.01, speed_y=0.004)
    g.link(uvs, "", p1, "Coordinate")
    p2 = g.node(unreal.MaterialExpressionPanner, speed_x=-0.006, speed_y=0.009)
    g.link(g.mul(uvs, g.const(0.6)), "", p2, "Coordinate")
    a = g.tex("LavaTex", T("T_Lava"), S_COL, p1)
    b = g.tex("LavaTex2", T("T_Lava"), S_COL, p2, param=False)
    heat = g.add(a, b, "RGB", "RGB")
    t = g.node(unreal.MaterialExpressionTime)
    pulse = g.add(g.const(0.85), g.mul(g.one_input(unreal.MaterialExpressionSine, g.mul(t, g.const(0.8))), g.const(0.15)))
    em = g.mul(g.mul(heat, g.scalar("Strength", 18.0)), pulse)
    em = g.mul(em, g.vector("Tint", (1.0, 0.45, 0.12)))
    g.out(em, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    g.out(g.const3((0.05, 0.02, 0.01)), unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.const(0.9), unreal.MaterialProperty.MP_ROUGHNESS)
    return g.finish()


def build_hologram():
    g = Graph("M_DA_Hologram")
    g.settings(blend_mode=unreal.BlendMode.BLEND_ADDITIVE, shading_model=unreal.MaterialShadingModel.MSM_UNLIT, two_sided=True)
    color = g.vector("Color", (0.3, 0.9, 1.0))
    wp = g.node(unreal.MaterialExpressionWorldPosition)
    z = g.one_input(unreal.MaterialExpressionComponentMask, wp, r=False, g=False, b=True, a=False)
    t = g.node(unreal.MaterialExpressionTime)
    lines = g.one_input(unreal.MaterialExpressionSine, g.add(g.mul(z, g.const(0.12)), g.mul(t, g.const(6.0))))
    lines01 = g.add(g.mul(lines, g.const(0.25)), g.const(0.75))
    fres = g.node(unreal.MaterialExpressionFresnel, exponent=2.0)
    rim = g.add(g.const(0.35), fres)
    em = g.mul(g.mul(g.mul(color, lines01), rim), g.mul(g.scalar("Intensity", 4.0), g.scalar("Fade", 1.0)))
    g.out(em, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return g.finish()


def build_smoke():
    g = Graph("M_DA_Smoke")
    g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT)
    try:
        g.settings(translucency_lighting_mode=unreal.TranslucencyLightingMode.TLM_VOLUMETRIC_NON_DIRECTIONAL)
    except Exception:  # noqa: BLE001
        pass
    color = g.vector("Color", (0.9, 0.9, 0.92))
    g.out(color, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.mul(color, g.const(0.08)), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    cd = g.node(unreal.MaterialExpressionPerInstanceCustomData, data_index=0)
    fres = g.node(unreal.MaterialExpressionFresnel, exponent=1.6)
    soft = g.one_input(unreal.MaterialExpressionOneMinus, fres)
    op = g.mul(cd, soft)
    df = g.node(unreal.MaterialExpressionDepthFade, fade_distance_default=300.0)
    g.link(op, "", df, "Opacity")
    g.out(df, unreal.MaterialProperty.MP_OPACITY)
    return g.finish()


def build_beam():
    g = Graph("M_DA_Beam")
    g.settings(blend_mode=unreal.BlendMode.BLEND_ADDITIVE, shading_model=unreal.MaterialShadingModel.MSM_UNLIT, two_sided=True)
    fres = g.node(unreal.MaterialExpressionFresnel, exponent=1.2)
    core = g.one_input(unreal.MaterialExpressionOneMinus, fres)
    em = g.mul(g.mul(g.vector("Tint", (1.0, 0.93, 0.7)), core), g.scalar("Strength", 0.6))
    df = g.node(unreal.MaterialExpressionDepthFade, fade_distance_default=800.0)
    g.link(em, "", df, "Opacity")
    g.out(g.mul(em, df), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return g.finish()


def build_waterfall():
    g = Graph("M_DA_Waterfall")
    g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT, two_sided=True)
    try:
        g.settings(translucency_lighting_mode=unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    except Exception:  # noqa: BLE001
        pass
    uv = g.node(unreal.MaterialExpressionTextureCoordinate)
    uvs = g.mul(uv, g.const(0.25))
    p = g.node(unreal.MaterialExpressionPanner, speed_x=0.02, speed_y=-0.9)
    g.link(uvs, "", p, "Coordinate")
    n = g.tex("FlowTex", T("T_Noise"), S_LIN, p)
    streaks = g.one_input(unreal.MaterialExpressionComponentMask, n, r=True, g=False, b=False, a=False)
    col = g.vector("Tint", (0.85, 0.95, 1.0))
    g.out(col, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.mul(col, g.mul(streaks, g.const(0.4))), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    g.out(g.const(0.1), unreal.MaterialProperty.MP_ROUGHNESS)
    op = g.mul(g.scalar("Opacity", 0.8), g.add(g.const(0.45), g.mul(streaks, g.const(0.7))))
    g.out(g.one_input(unreal.MaterialExpressionSaturate, op), unreal.MaterialProperty.MP_OPACITY)
    return g.finish()


TERRAIN_LAYERS = [
    # name, detail texture, normal texture (or None), tint (linear-ish), splat (texture, channel)
    ("Grass", "T_Grass", "T_Grass_N", (0.085, 0.20, 0.035), None),
    ("ForestFloor", "T_Leaves", None, (0.04, 0.065, 0.015), ("B", "G")),
    ("Sand", "T_Sand", "T_Sand_N", (0.72, 0.58, 0.33), ("A", "R")),
    ("WetSand", "T_Sand", "T_Sand_N", (0.32, 0.24, 0.13), ("B", "B")),
    ("Ash", "T_Rock", "T_Rock_N", (0.035, 0.03, 0.03), ("B", "R")),
    ("Rock", "T_Rock", "T_Rock_N", (0.18, 0.165, 0.15), ("A", "G")),
    ("Dirt", "T_Dirt", "T_Dirt_N", (0.2, 0.12, 0.06), ("A", "B")),
    ("Paving", "T_Paving", "T_Paving_N", (0.5, 0.46, 0.4), ("A", "A")),
]


def build_terrain():
    g = Graph("M_DA_Terrain")
    uv = g.node(unreal.MaterialExpressionTextureCoordinate)
    splat_a = g.tex("SplatA", T("T_TerrainSplatA"), S_MSK, uv)
    splat_b = g.tex("SplatB", T("T_TerrainSplatB"), S_MSK, uv)
    tiles = g.scalar("DetailTiles", 768.0)       # 3072 m / 768 = 4 m per repeat
    duv = g.mul(uv, tiles)
    color = None
    normal = None
    for name, dtex, ntex, tint, splat in TERRAIN_LAYERS:
        d = g.tex(f"{name}Detail", T(f"{dtex}_D"), S_LIN, duv)
        c = g.mul(g.vector(f"{name}Tint", tint), g.mul(d, g.const(2.0), "R"))
        if ntex:
            nrm = g.tex(f"{name}Normal", T(ntex), S_NRM, duv)
        else:
            nrm = g.const3((0, 0, 1))
        if splat is None:
            color, normal = c, nrm
            continue
        tex_node = splat_a if splat[0] == "A" else splat_b
        color = g.lerp(color, c, tex_node, "", "", splat[1])
        normal = g.lerp(normal, nrm, tex_node, "", "RGB" if ntex else "", splat[1])
    # far distance: blend to the baked colour map so the island reads well from afar
    macro = g.tex("ColorMap", T("T_TerrainColor"), S_COL, uv)
    depth = g.node(unreal.MaterialExpressionPixelDepth)
    far = g.one_input(unreal.MaterialExpressionSaturate, g.mul(g.sub(depth, g.const(9000.0)), g.const(1.0 / 40000.0)))
    macro_lin = g.mul(macro, g.const(0.9), "RGB")
    final = g.lerp(color, macro_lin, g.mul(far, g.scalar("MacroBlend", 0.85)))
    g.out(final, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.lerp(g.const3((0, 0, 1)), normal, g.scalar("NormalStrength", 0.8)), unreal.MaterialProperty.MP_NORMAL)
    rough = g.lerp(g.const(0.92), g.const(0.55), splat_b, "", "", "B")   # wet sand is shinier
    g.out(rough, unreal.MaterialProperty.MP_ROUGHNESS)
    return g.finish()


# --------------------------------------------------------------------------- instances
KIND_PARENT = {
    "opaque": "M_DA_Master", "foliage": "M_DA_Foliage", "glass": "M_DA_Glass", "emissive": "M_DA_Emissive",
    "water": "M_DA_Water", "lava": "M_DA_Lava", "hologram": "M_DA_Hologram", "smoke": "M_DA_Smoke",
    "beam": "M_DA_Beam", "waterfall": "M_DA_Waterfall", "terrain": "M_DA_Terrain",
}

NIGHT_ONLY_EMISSIVE = {"M_LampGlow", "M_LighthouseLamp"}


def build_instances(palette, masters):
    out = {}
    for name, spec in palette.items():
        kind = spec.get("kind", "opaque")
        parent = masters.get(KIND_PARENT.get(kind, "M_DA_Master"))
        if parent is None:
            continue
        mi_name = f"MI_{name}"
        path = f"{C.MAT_DIR}/{mi_name}"
        mi = C.load(path)
        if mi is None:
            mi = C.asset_tools().create_asset(mi_name, C.MAT_DIR, unreal.MaterialInstanceConstant,
                                             unreal.MaterialInstanceConstantFactoryNew())
        MEL.set_material_instance_parent(mi, parent)
        col = C.lc(spec["color_linear"])
        try:
            if kind in ("opaque", "foliage"):
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", float(spec.get("rough", 0.8)))
                if kind == "opaque":
                    MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", float(spec.get("metallic", 0.0)))
                    detail = spec.get("detail")
                    if detail and T(f"T_{detail}_D"):
                        MEL.set_material_instance_texture_parameter_value(mi, "DetailTex", T(f"T_{detail}_D"))
                        MEL.set_material_instance_scalar_parameter_value(mi, "DetailStrength", 1.0)
                        MEL.set_material_instance_scalar_parameter_value(mi, "Tiling", float(spec.get("tiling", 1.0)))
                        if T(f"T_{detail}_N"):
                            MEL.set_material_instance_texture_parameter_value(mi, "DetailNormal", T(f"T_{detail}_N"))
                            MEL.set_material_instance_scalar_parameter_value(mi, "NormalStrength", 0.8)
                    else:
                        MEL.set_material_instance_scalar_parameter_value(mi, "DetailStrength", 0.0)
                        MEL.set_material_instance_scalar_parameter_value(mi, "NormalStrength", 0.0)
            elif kind == "glass":
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Opacity", float(spec.get("opacity", 0.25)))
            elif kind == "emissive":
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Strength", float(spec.get("strength", 5.0)))
                MEL.set_material_instance_scalar_parameter_value(mi, "NightOnly", 1.0 if name in NIGHT_ONLY_EMISSIVE else 0.0)
                tex = spec.get("texture")
                if tex and T(tex):
                    MEL.set_material_instance_texture_parameter_value(mi, "EmissiveTex", T(tex))
                    MEL.set_material_instance_scalar_parameter_value(mi, "UseTexture", 1.0)
            elif kind == "water":
                c = spec["color_linear"]
                MEL.set_material_instance_vector_parameter_value(mi, "ScatterColor", C.lc((c[0] * 0.35, c[1] * 0.35, c[2] * 0.35)))
                MEL.set_material_instance_vector_parameter_value(mi, "Absorption", C.lc((0.45 - c[0] * 0.3, 0.08 + (0.4 - c[1]) * 0.1, 0.05 + (0.4 - c[2]) * 0.1)))
            elif kind in ("lava", "beam"):
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Strength", float(spec.get("strength", 1.0)))
            elif kind == "hologram":
                MEL.set_material_instance_vector_parameter_value(mi, "Color", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Intensity", float(spec.get("strength", 4.0)))
            elif kind == "smoke":
                MEL.set_material_instance_vector_parameter_value(mi, "Color", col)
            elif kind == "waterfall":
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Opacity", float(spec.get("opacity", 0.8)))
        except Exception as e:  # noqa: BLE001
            C.warn(f"{mi_name}: parameter setup failed: {e}")
        MEL.update_material_instance(mi)
        unreal.EditorAssetLibrary.save_loaded_asset(mi)
        out[name] = mi
    C.log(f"material instances: {len(out)}")
    return out


def build_all(palette):
    C.ensure_dir(C.MAT_DIR)
    mpc = build_mpc()
    masters = {}
    for name, fn in (("M_DA_Master", build_master), ("M_DA_Foliage", build_foliage), ("M_DA_Glass", build_glass),
                     ("M_DA_Emissive", lambda: build_emissive(mpc)), ("M_DA_Water", build_water),
                     ("M_DA_Lava", build_lava), ("M_DA_Hologram", build_hologram), ("M_DA_Smoke", build_smoke),
                     ("M_DA_Beam", build_beam), ("M_DA_Waterfall", build_waterfall), ("M_DA_Terrain", build_terrain)):
        try:
            masters[name] = fn()
        except Exception as e:  # noqa: BLE001
            C.error(f"master material {name} failed: {e}")
    C.log(f"master materials: {sorted(masters)}")
    instances = build_instances(palette, masters)
    return mpc, masters, instances
