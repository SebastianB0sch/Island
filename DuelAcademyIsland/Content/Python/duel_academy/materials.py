"""
Builds the Duel Academy master materials (node graphs created in code) and one
Material Instance per palette entry (Data/materials.json).

Masters (in /Game/DuelAcademy/Materials):
  M_DA_Master      opaque PBR: Tint * detail texture, detail normal
  M_DA_Foliage     two-sided, wind sway (world position offset)
  M_DA_Glass       translucent glass
  M_DA_Emissive    glowing surfaces; brighter at night (MPC NightFactor)
  M_DA_Water       single layer water of the sea and the lake: 6 Gerstner waves from Data/water.json (world
                   position offset + analytic normal, the same formulas as Source/.../DAWaterWaves.h), layered
                   detail normals, shoreline foam and shallow-water tint from T_WaterShore, whitecaps
  M_DA_PoolWater   single layer water of basins (fountain pools, hot springs): detail ripples + rain rings
  M_DA_River       single layer water flowing along the river ribbons' UVs, white water from UV1
  M_DA_Lava        panning emissive lava
  M_DA_Hologram    additive hologram (duel monsters, markers)
  M_DA_Smoke       translucent puffs, opacity from per-instance custom data
  M_DA_Beam        additive light beam
  M_DA_Waterfall   the waterfall: the M_DA_WaterFlow graph with heavier, faster, more opaque defaults
  M_DA_WaterFlow   fountain water (sheets, jets, foam): world-aligned, so no UVs - vertical faces stream
                   along world Z (FlowSpeed, < 0 = rising jets), flat faces churn; glints, soft contact, wobble
  M_DA_Spray       droplets of ADAEmitter's Spray / Jet kinds and its fireflies (opacity from per-instance
                   custom data, Glow = emissive strength)
  M_DA_Terrain     splat-mapped terrain (8 layers); wet shoreline, darker submerged ground and daytime
                   caustics under water from T_WaterShore / T_Caustics
  M_DA_Toon        anime cast, interiors and furniture: BaseTex * Tint (* optional detail texture) with a flat
                   "fill" light (cel look), dimmer at night
  M_DA_ToonMasked  same, alpha-masked + two-sided (hair cards, eyelashes, cut-out clothes)
  M_DA_Outline     unlit ink line of the inverted-hull outlines (cast and furniture)
  M_DA_Cel         anime cast (cast.json kind "cel", Tools/dai/anime/cel.py): lit base colour without specular
                   (no plastic sheen), a rim light on the side the key light comes from and an "angel ring"
                   highlight on hair; M_DA_CelMasked is the alpha-masked two-sided variant
  PP_DA_Cel        post-process (stencil 1 = the cast, set by UDAAvatarComponent): bands the real scene lighting
                   (Lumen GI, shadows, lamps, night) on the cast into a lit and a shadow tone with a saturated,
                   cooler shadow colour - the cel look without giving up the engine's lighting
  MPC_DuelAcademy  NightFactor / TimeOfDay / SunDirection (driven by ADAIslandManager)
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

    def tex(self, name, texture, sampler, uv=None, param=True, clamp=False):
        """clamp: shared clamping sampler instead of the shared wrapping one - for the island-wide maps, which
        are also looked up outside the island (the open sea must not repeat the island's shoreline)."""
        cls = unreal.MaterialExpressionTextureSampleParameter2D if param else unreal.MaterialExpressionTextureSample
        props = dict(texture=texture, sampler_type=sampler)
        if param:
            props["parameter_name"] = name
        n = self.node(cls, **props)
        try:
            n.set_editor_property("sampler_source", unreal.SamplerSourceMode.SSM_CLAMP_WORLD_GROUP_SETTINGS if clamp
                                  else unreal.SamplerSourceMode.SSM_WRAP_WORLD_GROUP_SETTINGS)
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

    # ---- small maths shortcuts (the water graphs are mostly arithmetic)
    def div(self, a, b, a_out="", b_out=""):
        return self.op(unreal.MaterialExpressionDivide, a, b, a_out, b_out)

    def maxn(self, a, b, a_out="", b_out=""):
        return self.op(unreal.MaterialExpressionMax, a, b, a_out, b_out)

    def dot(self, a, b, a_out="", b_out=""):
        return self.op(unreal.MaterialExpressionDotProduct, a, b, a_out, b_out)

    def sat(self, src, src_out=""):
        return self.one_input(unreal.MaterialExpressionSaturate, src, src_out)

    def one_minus(self, src, src_out=""):
        return self.one_input(unreal.MaterialExpressionOneMinus, src, src_out)

    def sin(self, cycles, src_out=""):
        """sin(2 pi x): the Sine node's period is 1 (set explicitly), so its input is in cycles, not radians."""
        return self.one_input(unreal.MaterialExpressionSine, cycles, src_out, period=1.0)

    def cos(self, cycles, src_out=""):
        """cos(2 pi x) - see sin()."""
        return self.one_input(unreal.MaterialExpressionCosine, cycles, src_out, period=1.0)

    def mask(self, src, channels, src_out=""):
        """Component mask, channels = any of "rgba" (e.g. "rg")."""
        return self.one_input(unreal.MaterialExpressionComponentMask, src, src_out, r="r" in channels,
                              g="g" in channels, b="b" in channels, a="a" in channels)

    def append(self, a, b):
        n = self.node(unreal.MaterialExpressionAppendVector)
        self.link(a, "", n, "A")
        self.link(b, "", n, "B")
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
        # skeletal: only the masters the student's slots derive from (PBR body, opaque/emissive duel disk) -
        # every other master would just compile unused GPU-skin permutations
        flags = ["used_with_instanced_static_meshes", "used_with_nanite"]
        if self.name in SKELETAL_MASTERS:
            flags.append("used_with_skeletal_mesh")
        for flag in flags:
            try:
                self.mat.set_editor_property(flag, True)
            except Exception:  # noqa: BLE001
                pass
        MEL.layout_material_expressions(self.mat)
        MEL.recompile_material(self.mat)
        unreal.EditorAssetLibrary.save_loaded_asset(self.mat)
        return self.mat


SKELETAL_MASTERS = {"M_DA_PBR", "M_DA_PBRFoliage", "M_DA_Master", "M_DA_Emissive"}


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
    vparams = []
    for n, v in (("SunDirection", (0.3, 0.2, 0.93, 1.0)),):
        p = unreal.CollectionVectorParameter()
        p.set_editor_property("parameter_name", n)
        p.set_editor_property("default_value", unreal.LinearColor(*v))
        vparams.append(p)
    try:
        mpc.set_editor_property("vector_parameters", vparams)
    except Exception as e:  # noqa: BLE001
        C.warn(f"MPC vector parameters: {e}")
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


# --------------------------------------------------------------------------- water (ocean, lake, pools, rivers)
# Number of Gerstner slots of M_DA_Water = DAWater::MaxWaves (Source/.../Public/DAWaterWaves.h).
WAVE_SLOTS = 6
# The island-wide maps (T_WaveMask, T_WaterShore) cover the terrain domain, centred on the world origin (cm).
ISLAND_MIN_CM = -153600.0
ISLAND_SIZE_CM = 307200.0
# The sea flattens between these distances (cm, max(|x|, |y|)) = DAWater::DefaultFadeStart / DefaultFadeEnd:
# SM_Ocean's fine grid ends at +-1.8 km, the coarse rings beyond stay flat (no cracks, no aliasing).
WAVE_FADE_START = 160000.0
WAVE_FADE_END = 178000.0
TWO_PI = 6.283185307179586


def TX(*names):
    """First of the named textures that exists (None if none does) - new textures fall back to older ones
    so the materials still build against a SourceAssets folder from before the water upgrade."""
    for name in names:
        tex = T(name)
        if tex is not None:
            return tex
    return None


def _sample_level0(node):
    """Sample mip 0 explicitly: this lookup also runs in the vertex shader (world position offset)."""
    try:
        node.set_editor_property("mip_value_mode", unreal.TextureMipValueMode.TMVM_MIP_LEVEL)
        node.set_editor_property("const_mip_value", 0)
    except Exception:  # noqa: BLE001 - the translator samples level 0 outside the pixel shader anyway
        pass
    return node


def _slw_output(g, scatter, absorb, phase_g=0.2):
    """Single layer water outputs; False when the shading model is unavailable (caller falls back)."""
    try:
        slw = g.node(unreal.MaterialExpressionSingleLayerWaterMaterialOutput)
    except Exception:  # noqa: BLE001
        return False
    g.link(scatter, "", slw, "ScatteringCoefficients")
    g.link(absorb, "", slw, "AbsorptionCoefficients")
    g.link(g.const(phase_g), "", slw, "PhaseG")
    return True


def _use_slw(g):
    try:
        g.mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_SINGLE_LAYER_WATER)
        return True
    except Exception:  # noqa: BLE001
        return False


def _foam_texture():
    """(texture, blob channel, lace channel): T_WaterFoam (R = thick blobs, G = lacy network), else the foam
    channel of T_WaterStreaks (G), else plain noise."""
    tex = T("T_WaterFoam")
    if tex is not None:
        return tex, "R", "G"
    tex = T("T_WaterStreaks")
    if tex is not None:
        return tex, "G", "G"
    return T("T_Noise"), "R", "R"


def _detail_normals(g, xy, t, layers):
    """Sum of panned normal-map layers (tangent xy). layers = [(texture, uv scale, pan x, pan y, weight node
    or None)]; returns a float2 node."""
    total = None
    for tex, scale, sx, sy, weight in layers:
        pan = g.node(unreal.MaterialExpressionPanner, speed_x=sx, speed_y=sy)
        g.link(g.mul(xy, g.const(scale)) if scale != 1.0 else xy, "", pan, "Coordinate")
        g.link(t, "", pan, "Time")
        n = g.mask(g.tex("", tex, S_NRM, pan, param=False), "rg", "RGB")
        if weight is not None:
            n = g.mul(n, weight)
        total = n if total is None else g.add(total, n)
    return total


def build_water():
    """M_DA_Water - the sea and the lake (single layer water).

    * 6 Gerstner slots (Wave<i>A / B / C vector parameters, filled per instance from Data/water.json) displace
      the surface (world position offset) and give the analytic normal; all phases are computed in cycles
      because the Sine / Cosine nodes have a period of 1. The amplitudes are scaled by T_WaveMask (MaskAmount)
      and flattened towards the far rings of SM_Ocean (WaveFadeStart / End). Same formulas as
      Source/.../Public/DAWaterWaves.h, so floating things ride exactly this surface.
    * World-space normal = wave normal + four panned detail layers (90 m, 22 m, 8 m swell texture and fine wind
      ripples); the fine layers fade with distance so the far sea does not show tiling.
    * Foam (base colour + opacity = coverage of single layer water's top layer, rougher): a solid rim and
      lapping bands along the shore from T_WaterShore's distance field, broken up by T_WaterFoam, and whitecaps
      where the Gerstner fold term peaks.
    * Shallow water scatters more and absorbs less (ShoreAmount), on top of single layer water's own depth
      absorption."""
    g = Graph("M_DA_Water")
    ok = _use_slw(g)
    g.settings(tangent_space_normal=False)
    wp = g.node(unreal.MaterialExpressionWorldPosition)
    try:
        # the resting position in the pixel shader too (by default it sees the displaced one there), so the
        # normal and the foam are evaluated at exactly the point the vertex shader displaced
        wp.set_editor_property("world_position_shader_offset",
                               unreal.WorldPositionIncludedOffsets.WPOS_EXCLUDE_ALL_SHADER_OFFSETS)
    except Exception:  # noqa: BLE001 - cosmetic: the waves move a point by well under a wavelength
        pass
    xy = g.mask(wp, "rg")
    time = g.node(unreal.MaterialExpressionTime)

    # ---- island-wide maps: uv = (xy - min) / size, row 0 = north
    iuv = g.add(g.mul(xy, g.const(1.0 / ISLAND_SIZE_CM)), g.const(-ISLAND_MIN_CM / ISLAND_SIZE_CM))
    iu, iv = g.mask(iuv, "r"), g.mask(iuv, "g")
    # MirrorY = 1 when the level had to be built with a mirrored Y axis (build.py axis check)
    iuv = g.append(iu, g.lerp(iv, g.one_minus(iv), g.scalar("MirrorY", 0.0)))

    # ---- amplitude scale m = wave mask * far fade * WaveAmount
    mask_tex = T("T_WaveMask")
    mask_amount = g.scalar("MaskAmount", 0.0)
    if mask_tex is not None:
        mask_node = _sample_level0(g.tex("", mask_tex, S_MSK, iuv, param=False, clamp=True))
        mask = g.lerp(g.const(1.0), mask_node, mask_amount, "", "R")
    else:
        mask = g.const(1.0)
    cheb = g.maxn(g.one_input(unreal.MaterialExpressionAbs, g.mask(xy, "r")),
                  g.one_input(unreal.MaterialExpressionAbs, g.mask(xy, "g")))
    fade_start = g.scalar("WaveFadeStart", WAVE_FADE_START)
    fade_end = g.scalar("WaveFadeEnd", WAVE_FADE_END)
    fade_t = g.sat(g.div(g.sub(cheb, fade_start), g.maxn(g.sub(fade_end, fade_start), g.const(1.0))))
    fade = g.one_minus(g.mul(g.mul(fade_t, fade_t), g.sub(g.const(3.0), g.mul(fade_t, g.const(2.0)))))
    m = g.mul(g.mul(mask, fade), g.scalar("WaveAmount", 1.0))

    # ---- Gerstner sum (see DAWater::Evaluate)
    off_xy = off_z = slope = fold = None
    for i in range(1, WAVE_SLOTS + 1):
        a = g.vector(f"Wave{i}A", (0.0, 0.0, 0.0), 0.0)     # dir.x / L, dir.y / L, speed / L, phase / 2 pi
        b = g.vector(f"Wave{i}B", (0.0, 0.0, 0.0), 0.0)     # A, s A, k A, k s A
        c = g.vector(f"Wave{i}C", (1.0, 0.0, 0.0), 0.0)     # dir.x, dir.y
        cycles = g.add(g.sub(g.dot(g.mask(a, "rg"), xy), g.mul(time, a, "", "B")), a, "", "A")
        s, co = g.sin(cycles), g.cos(cycles)
        d = g.mask(c, "rg")
        terms = (g.mul(d, g.mul(b, co, "G", "")), g.mul(b, s, "R", ""), g.mul(d, g.mul(b, co, "B", "")),
                 g.mul(b, s, "A", ""))
        if off_xy is None:
            off_xy, off_z, slope, fold = terms
        else:
            off_xy, off_z = g.add(off_xy, terms[0]), g.add(off_z, terms[1])
            slope, fold = g.add(slope, terms[2]), g.add(fold, terms[3])
    g.out(g.append(g.mul(off_xy, m), g.mul(off_z, m)), unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)

    # ---- normal: wave normal + detail layers (the fine ones fade with distance)
    scale = g.scalar("WaveScale", 0.0012)
    uv1 = g.mul(xy, scale)
    # WaveSpeed scales the detail layers' time: 1 for the sea and the lake
    wt = g.mul(time, g.scalar("WaveSpeed", 1.0))
    depth = g.node(unreal.MaterialExpressionPixelDepth)
    near_w = g.one_minus(g.sat(g.mul(g.sub(depth, g.const(2500.0)), g.const(1.0 / 9000.0))))
    mid_w = g.one_minus(g.mul(g.sat(g.mul(g.sub(depth, g.const(20000.0)), g.const(1.0 / 60000.0))), g.const(0.7)))
    swell = T("T_WaterNormal")
    ripple = TX("T_WaterDetailN", "T_WaterNormal")
    detail = _detail_normals(g, uv1, wt, [
        (swell, 1.0, 0.015, 0.008, mid_w),
        (swell, 0.37, -0.011, 0.017, mid_w),
        (ripple, 3.3, 0.05, -0.035, g.mul(near_w, g.const(0.8))),
        (swell, 0.083, 0.004, 0.006, g.const(0.6)),
    ])
    detail = g.mul(detail, g.scalar("WaveStrength", 0.45))
    n_xy = g.sub(detail, g.mul(slope, m))
    n_z = g.maxn(g.sub(g.const(1.0), g.mul(fold, m)), g.const(0.05))
    g.out(g.one_input(unreal.MaterialExpressionNormalize, g.append(n_xy, n_z)), unreal.MaterialProperty.MP_NORMAL)

    # ---- foam
    foam_tex, blob_ch, lace_ch = _foam_texture()
    fuv = g.mul(xy, g.scalar("FoamScale", 1.0 / 600.0))
    fp1 = g.node(unreal.MaterialExpressionPanner, speed_x=0.012, speed_y=0.007)
    g.link(fuv, "", fp1, "Coordinate")
    g.link(time, "", fp1, "Time")
    fp2 = g.node(unreal.MaterialExpressionPanner, speed_x=-0.009, speed_y=0.011)
    g.link(g.mul(fuv, g.const(1.7)), "", fp2, "Coordinate")
    g.link(time, "", fp2, "Time")
    f1 = g.tex("", foam_tex, S_LIN, fp1, param=False)
    f2 = g.tex("", foam_tex, S_LIN, fp2, param=False)
    lace = g.add(g.mul(f1, g.const(0.6), lace_ch), g.mul(f2, g.const(0.4), lace_ch))
    blobs = g.add(g.mul(f1, g.const(0.6), blob_ch), g.mul(f2, g.const(0.4), blob_ch))

    shore_tex = T("T_WaterShore")
    # (declared even without the shore map, so instances can always set them)
    shore_amount = g.scalar("ShoreAmount", 0.0)
    shore_strength = g.scalar("ShoreFoam", 0.0)
    shore_foam = None
    depth01 = None
    if shore_tex is not None:
        sh = g.tex("", shore_tex, S_MSK, iuv, param=False, clamp=True)
        depth01 = g.mask(sh, "r")                # 0 at the waterline .. 1 at >= 8 m
        dist01 = g.mask(sh, "g")                 # 0 at the waterline .. 1 at >= 40 m from the shore
        # a solid rim right at the waterline
        rim = g.one_minus(g.sat(g.div(dist01, g.scalar("ShoreRim", 0.05))))
        # lapping bands that travel towards the shore and die out with distance
        phase = g.add(g.add(g.mul(dist01, g.scalar("ShoreBands", 6.0)), g.mul(time, g.scalar("ShoreSpeed", 0.12))),
                      g.mul(lace, g.const(0.15)))
        wave01 = g.add(g.mul(g.sin(phase), g.const(0.5)), g.const(0.5))
        wave2 = g.mul(wave01, wave01)
        reach = g.one_minus(g.sat(g.div(dist01, g.scalar("ShoreReach", 0.35))))
        band = g.mul(g.mul(wave2, wave2), g.mul(reach, reach))
        raw = g.add(g.mul(rim, g.const(1.2)), g.mul(band, g.const(0.9)))
        broken = g.sub(g.mul(raw, g.add(g.mul(lace, g.const(1.3)), g.const(0.35))), g.const(0.25))
        shore_foam = g.mul(g.mul(g.sat(broken), shore_strength), shore_amount)
    # whitecaps where the crests of several waves pile up (fold / FoldMax), not in sheltered water (m)
    fold_n = g.div(g.mul(fold, m), g.scalar("FoldMax", 1.0))
    # fold_n is 0..1 of the set's own maximum (real sets are gentle: sum(k s A) ~ 0.13 for the sea), so the
    # threshold is relative: foam on roughly the top 40 % of the range
    crest = g.sat(g.mul(g.sub(fold_n, g.scalar("CrestStart", 0.58)), g.const(3.5)))
    crest_foam = g.mul(g.mul(crest, g.sat(g.add(g.mul(blobs, g.const(1.2)), g.const(0.3)))), g.scalar("Crest", 0.0))
    foam = g.sat(g.add(shore_foam, crest_foam)) if shore_foam is not None else g.sat(crest_foam)

    rough_far = g.lerp(g.const(0.03), g.const(0.12), g.sat(g.mul(depth, g.const(1.0 / 200000.0))))
    g.out(g.lerp(rough_far, g.const(0.45), foam), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.const(0.0), unreal.MaterialProperty.MP_METALLIC)

    # ---- water body colour
    scatter = g.vector("ScatterColor", (0.02, 0.18, 0.22))
    absorb = g.vector("Absorption", (0.45, 0.06, 0.04))
    if depth01 is not None:
        shallow = g.mul(g.one_minus(depth01), shore_amount)
        scatter = g.mul(scatter, g.lerp(g.const(1.0), g.scalar("ShallowScatter", 1.6), shallow))
        absorb = g.mul(absorb, g.lerp(g.const(1.0), g.scalar("ShallowAbsorption", 0.6), shallow))
    foam_color = g.vector("FoamColor", (0.9, 0.95, 1.0))
    if ok and _slw_output(g, scatter, absorb):
        g.out(g.mul(foam_color, foam), unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(g.mul(foam, g.scalar("FoamOpacity", 0.85)), unreal.MaterialProperty.MP_OPACITY)
    else:
        g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT)
        g.out(g.lerp(g.mul(scatter, g.const(3.0)), foam_color, foam), unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(g.lerp(g.const(0.85), g.const(1.0), foam), unreal.MaterialProperty.MP_OPACITY)
    return g.finish()


def _rain_rings(g, tex, uv, time, speed, offset):
    """One layer of expanding rings from T_Ripples (R = ring profile, GB = direction, A = time offset):
    f = frac(A + t), tf = f - 1 + R, h = saturate(1 - f) * R * sin(clamp(tf * 9, 0, 3) * pi)."""
    s = g.tex("", tex, S_LIN, uv, param=False)
    f = g.one_input(unreal.MaterialExpressionFrac, g.add(g.add(g.mul(time, speed), g.const(offset)), s, "", "A"))
    tf = g.add(g.sub(f, g.const(1.0)), s, "", "R")
    # clamp(tf * 9, 0, 3) * pi radians = 1.5 * saturate(tf * 3) cycles
    ring = g.sin(g.mul(g.sat(g.mul(tf, g.const(3.0))), g.const(1.5)))
    h = g.mul(g.mul(g.one_minus(f), s, "", "R"), ring)
    direction = g.sub(g.mul(g.mask(s, "gb", "RGB"), g.const(2.0)), g.const(1.0))
    return g.mul(direction, h)


def build_pool_water():
    """M_DA_PoolWater - still water in basins (fountain pools, hot springs): single layer water without
    displacement, small quick detail ripples (WaveScale / WaveSpeed / WaveStrength, world aligned) and
    expanding rain rings where the fountains' droplets fall (T_Ripples, Ripple / RippleScale / RippleSpeed)."""
    g = Graph("M_DA_PoolWater")
    ok = _use_slw(g)
    wp = g.node(unreal.MaterialExpressionWorldPosition)
    xy = g.mask(wp, "rg")
    time = g.node(unreal.MaterialExpressionTime)
    uv1 = g.mul(xy, g.scalar("WaveScale", 0.0045))
    wt = g.mul(time, g.scalar("WaveSpeed", 6.0))
    swell = T("T_WaterNormal")
    detail = _detail_normals(g, uv1, wt, [(swell, 1.0, 0.015, 0.008, None), (swell, 0.37, -0.011, 0.017, None)])
    n_xy = g.mul(detail, g.scalar("WaveStrength", 0.6))
    rings_tex = T("T_Ripples")
    # (declared even without the ring texture, so instances can always set them)
    ripple, ripple_scale, rspeed = g.scalar("Ripple", 0.6), g.scalar("RippleScale", 0.5), g.scalar("RippleSpeed", 1.0)
    if rings_tex is not None:
        ruv = g.mul(xy, g.mul(ripple_scale, g.const(0.01)))     # texture tiles per metre
        rings = g.add(_rain_rings(g, rings_tex, ruv, time, rspeed, 0.0),
                      _rain_rings(g, rings_tex, g.add(g.mul(ruv, g.const(1.63)), g.const(0.37)), time, rspeed, 0.5))
        n_xy = g.add(n_xy, g.mul(rings, ripple))
    g.out(g.one_input(unreal.MaterialExpressionNormalize, g.append(n_xy, g.const(1.0))), unreal.MaterialProperty.MP_NORMAL)
    g.out(g.const(0.03), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.const(0.0), unreal.MaterialProperty.MP_METALLIC)
    scatter = g.vector("ScatterColor", (0.05, 0.2, 0.24))
    absorb = g.vector("Absorption", (0.4, 0.06, 0.04))
    if ok and _slw_output(g, scatter, absorb):
        g.out(g.const3((0.0, 0.0, 0.0)), unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(g.const(0.0), unreal.MaterialProperty.MP_OPACITY)
    else:
        g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT)
        g.out(g.mul(scatter, g.const(3.0)), unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(g.const(0.85), unreal.MaterialProperty.MP_OPACITY)
    return g.finish()


def build_river():
    """M_DA_River - flowing water on the river ribbons (single layer water).
    UV0 = (metres across, metres along the stream); the FBX import flips V, so downstream is -V here and the
    layers are sampled at V + Time * Flow. UV1 = (foam: rapids / cascades, bank: 1 at the water's edge - also
    V-flipped by the import, hence BankFlip). Two normal layers and the foam drift downstream at different
    speeds; white water where UV1 says so and a lacy line along the banks."""
    g = Graph("M_DA_River")
    ok = _use_slw(g)
    uv0 = g.node(unreal.MaterialExpressionTextureCoordinate, coordinate_index=0)
    uv1 = g.node(unreal.MaterialExpressionTextureCoordinate, coordinate_index=1)
    time = g.node(unreal.MaterialExpressionTime)
    travel = g.mul(time, g.scalar("Flow", 1.2))                 # metres the surface has moved
    u, v = g.mask(uv0, "r"), g.mask(uv0, "g")

    def flowing(scale, speed, u_shift):
        """UV of a layer with tiles of 1 / scale metres drifting downstream at speed * Flow."""
        return g.append(g.add(g.mul(u, g.const(scale)), g.const(u_shift)),
                        g.mul(g.add(v, g.mul(travel, g.const(speed))), g.const(scale)))

    swell = T("T_WaterNormal")
    ripple = TX("T_WaterDetailN", "T_WaterNormal")
    n1 = g.mask(g.tex("", swell, S_NRM, flowing(1.0 / 3.0, 1.0, 0.0), param=False), "rg", "RGB")
    n2 = g.mask(g.tex("", ripple, S_NRM, flowing(1.0 / 1.3, 0.7, 0.37), param=False), "rg", "RGB")
    n_xy = g.mul(g.add(n1, n2), g.scalar("WaveStrength", 0.5))
    g.out(g.one_input(unreal.MaterialExpressionNormalize, g.append(n_xy, g.const(1.0))), unreal.MaterialProperty.MP_NORMAL)

    foam_tex, blob_ch, lace_ch = _foam_texture()
    f1 = g.tex("", foam_tex, S_LIN, flowing(1.0 / 2.5, 0.9, 0.0), param=False)
    f2 = g.tex("", foam_tex, S_LIN, flowing(1.0 / 1.1, 1.15, 0.5), param=False)
    blobs = g.add(g.mul(f1, g.const(0.6), blob_ch), g.mul(f2, g.const(0.4), blob_ch))
    lace = g.add(g.mul(f1, g.const(0.6), lace_ch), g.mul(f2, g.const(0.4), lace_ch))
    rapids_in = g.mask(uv1, "r")
    bank_raw = g.mask(uv1, "g")
    bank = g.lerp(bank_raw, g.one_minus(bank_raw), g.scalar("BankFlip", 1.0))
    rapids = g.sat(g.mul(rapids_in, g.add(g.mul(blobs, g.const(1.4)), g.const(0.4))))
    bank_foam = g.mul(g.mul(g.sat(g.mul(g.sub(bank, g.const(0.75)), g.const(4.0))), lace), g.const(0.8))
    foam = g.sat(g.mul(g.add(rapids, bank_foam), g.scalar("Foam", 1.0)))
    g.out(g.lerp(g.const(0.05), g.const(0.5), foam), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.const(0.0), unreal.MaterialProperty.MP_METALLIC)
    scatter = g.vector("ScatterColor", (0.04, 0.16, 0.16))
    absorb = g.vector("Absorption", (0.4, 0.07, 0.05))
    foam_color = g.vector("FoamColor", (0.92, 0.96, 1.0))
    if ok and _slw_output(g, scatter, absorb):
        g.out(g.mul(foam_color, foam), unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(g.mul(foam, g.const(0.85)), unreal.MaterialProperty.MP_OPACITY)
    else:
        g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT)
        g.out(g.lerp(g.mul(scatter, g.const(3.0)), foam_color, foam), unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(g.lerp(g.const(0.8), g.const(1.0), foam), unreal.MaterialProperty.MP_OPACITY)
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


def _mask(g, src, ch):
    return g.one_input(unreal.MaterialExpressionComponentMask, src, r=ch == "r", g=ch == "g", b=ch == "b", a=False)


def _append(g, a, b):
    n = g.node(unreal.MaterialExpressionAppendVector)
    g.link(a, "", n, "A")
    g.link(b, "", n, "B")
    return n


# M_DA_WaterFlow scalar parameters: (name, fountain default, waterfall default)
FLOW_DEFAULTS = (("FlowSpeed", 2.4, 6.0), ("StreakScale", 1.6, 0.55), ("StreakStretch", 4.0, 5.0),
                 ("FoamScale", 1.0, 0.45), ("FoamSpeed", 1.0, 1.6), ("Contrast", 1.8, 1.6), ("Sparkle", 0.5, 0.35),
                 ("Opacity", 0.55, 0.8), ("Base", 0.25, 0.55), ("Wobble", 1.0, 3.0))


def build_water_flow(name="M_DA_WaterFlow", waterfall=False):
    """Fountain water: overflow sheets, jets and foam (palette kind "flow", Tools/dai/assets/fountain.py).
    The waterfall (palette kind "waterfall", master M_DA_Waterfall) is the same graph with its own defaults:
    faster, broader streaks, a denser, whiter sheet and a livelier surface - so the falls stream along
    world Z whatever the sheet's UVs are, and the plunge pool's foam disc churns.
    World-aligned instead of UV-mapped, so any lathe, tube or ring flows the right way:
      * vertical faces sample T_WaterStreaks (R / B: threads stretched along V) in the two side projections,
        V = world Z (m) + Time * FlowSpeed - streaks fall at FlowSpeed m/s, rise for a negative speed.
        Two layers (the second finer and 1.37x faster) so it never reads as one sliding picture;
      * flat faces churn: the foam channel (G) under two crossing panners (FoamScale, FoamSpeed);
      * opacity = Opacity * lerp(Base, 1, streaks) (+ a little at grazing angles), depth-faded where the
        water meets the pool or the stone; white glints (Sparkle); a slight surface wobble (Wobble, cm)."""
    g = Graph(name)
    defaults = {key: (fall if waterfall else fountain) for key, fountain, fall in FLOW_DEFAULTS}

    def param(key):
        return g.scalar(key, defaults[key])

    g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT, two_sided=True)
    try:
        g.settings(translucency_lighting_mode=unreal.TranslucencyLightingMode.TLM_SURFACE_PER_PIXEL_LIGHTING)
    except Exception:  # noqa: BLE001
        pass
    tex = T("T_WaterStreaks") or T("T_Noise")
    wp = g.mul(g.node(unreal.MaterialExpressionWorldPosition), g.const(0.01))      # metres
    x, y, z = _mask(g, wp, "r"), _mask(g, wp, "g"), _mask(g, wp, "b")
    nrm = g.node(unreal.MaterialExpressionVertexNormalWS)
    ax = g.one_input(unreal.MaterialExpressionAbs, _mask(g, nrm, "r"))
    ay = g.one_input(unreal.MaterialExpressionAbs, _mask(g, nrm, "g"))
    az = g.one_input(unreal.MaterialExpressionAbs, _mask(g, nrm, "b"))
    t = g.node(unreal.MaterialExpressionTime)
    # ---- vertical faces: streaks along world Z
    flow = g.mul(t, param("FlowSpeed"))
    su = param("StreakScale")
    sv = g.op(unreal.MaterialExpressionDivide, su, param("StreakStretch"))
    v1 = g.mul(g.add(z, flow), sv)
    v2 = g.mul(g.add(z, g.mul(flow, g.const(1.37))), g.mul(sv, g.const(1.9)))

    def side(u):
        a = g.tex("", tex, S_LIN, _append(g, g.mul(u, su), v1), param=False)
        b = g.tex("", tex, S_LIN, _append(g, g.add(g.mul(u, g.mul(su, g.const(1.9))), g.const(0.37)), v2), param=False)
        return g.mul(g.add(a, b, "R", "B"), g.const(0.5))

    s_yz, s_xz = side(y), side(x)        # faces facing +-X see the YZ plane, faces facing +-Y the XZ plane
    w_side = g.add(g.add(ax, ay), g.const(1e-4))
    streak = g.op(unreal.MaterialExpressionDivide, g.add(g.mul(s_yz, ax), g.mul(s_xz, ay)), w_side)
    # ---- flat faces: churning foam
    xy = g.mul(_append(g, x, y), param("FoamScale"))
    ft = g.mul(t, param("FoamSpeed"))
    p1 = g.node(unreal.MaterialExpressionPanner, speed_x=0.11, speed_y=0.07)
    g.link(xy, "", p1, "Coordinate")
    g.link(ft, "", p1, "Time")
    p2 = g.node(unreal.MaterialExpressionPanner, speed_x=-0.08, speed_y=0.12)
    g.link(g.mul(xy, g.const(1.7)), "", p2, "Coordinate")
    g.link(ft, "", p2, "Time")
    f1 = g.tex("", tex, S_LIN, p1, param=False)
    f2 = g.tex("", tex, S_LIN, p2, param=False)
    foam = g.mul(g.add(f1, f2, "G", "G"), g.const(0.5))
    w_top = g.one_input(unreal.MaterialExpressionSaturate, g.mul(g.sub(az, g.const(0.55)), g.const(5.0)))
    s = g.lerp(streak, foam, w_top)
    s01 = g.one_input(unreal.MaterialExpressionSaturate,
                      g.add(g.mul(g.sub(s, g.const(0.5)), param("Contrast")), g.const(0.5)))
    # ---- shading
    tint = g.vector("Tint", (0.85, 0.95, 1.0) if waterfall else (0.86, 0.95, 1.0))
    g.out(g.mul(tint, g.lerp(g.const(0.8), g.const(1.1), s01)), unreal.MaterialProperty.MP_BASE_COLOR)
    s2 = g.mul(s01, s01)
    g.out(g.mul(tint, g.mul(g.mul(s2, s2), param("Sparkle"))), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    g.out(g.lerp(g.const(0.04), g.const(0.3), s01), unreal.MaterialProperty.MP_ROUGHNESS)
    op = g.mul(param("Opacity"), g.lerp(param("Base"), g.const(1.0), s01))
    op = g.add(op, g.mul(g.node(unreal.MaterialExpressionFresnel, exponent=3.0), g.const(0.2)))
    df = g.node(unreal.MaterialExpressionDepthFade, fade_distance_default=25.0)
    g.link(g.one_input(unreal.MaterialExpressionSaturate, op), "", df, "Opacity")
    g.out(df, unreal.MaterialProperty.MP_OPACITY)
    # ---- wobble along the normal (a living surface, not a glass shell)
    phase = g.add(g.mul(t, g.const(1.3)), g.mul(g.add(g.add(x, y), z), g.const(0.8)))
    wob = g.mul(g.one_input(unreal.MaterialExpressionSine, phase), param("Wobble"))
    g.out(g.mul(nrm, wob), unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    return g.finish()


def build_waterfall():
    """M_DA_Waterfall: see build_water_flow."""
    return build_water_flow("M_DA_Waterfall", waterfall=True)


def build_spray():
    """Droplets of ADAEmitter's Spray and Jet kinds: small bright specks, opacity from per-instance custom
    data 0. (M_DA_Smoke's 3 m depth fade would wipe out droplets a hand's width above the pool.)
    Glow = emissive strength: 0.35 for water droplets, raised by ADAEmitter for its fireflies."""
    g = Graph("M_DA_Spray")
    g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT)
    color = g.vector("Color", (0.92, 0.97, 1.0))
    g.out(color, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.mul(color, g.scalar("Glow", 0.35)), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    g.out(g.const(0.1), unreal.MaterialProperty.MP_ROUGHNESS)
    cd = g.node(unreal.MaterialExpressionPerInstanceCustomData, data_index=0)
    soft = g.one_input(unreal.MaterialExpressionOneMinus, g.node(unreal.MaterialExpressionFresnel, exponent=2.0))
    op = g.mul(cd, g.add(g.const(0.35), g.mul(soft, g.const(0.65))))
    df = g.node(unreal.MaterialExpressionDepthFade, fade_distance_default=8.0)
    g.link(op, "", df, "Opacity")
    g.out(df, unreal.MaterialProperty.MP_OPACITY)
    return g.finish()


def build_pbr(name, foliage=False):
    """Textured PBR master for third-party assets (CC0 packs): BaseTex*Tint, NormalTex, ORM-style mask."""
    g = Graph(name)
    if foliage:
        g.settings(blend_mode=unreal.BlendMode.BLEND_MASKED, two_sided=True)
    uv = g.node(unreal.MaterialExpressionTextureCoordinate)
    base = g.tex("BaseTex", T("T_White"), S_COL, uv)
    tint = g.vector("Tint", (1, 1, 1))
    g.out(g.mul(base, tint, "RGB", ""), unreal.MaterialProperty.MP_BASE_COLOR)
    nrm = g.tex("NormalTex", T("T_FlatNormal"), S_NRM, uv)
    g.out(nrm, unreal.MaterialProperty.MP_NORMAL, "RGB")
    orm = g.tex("ORMTex", T("T_DefaultMask"), S_MSK, uv)
    use = g.scalar("UseORM", 0.0)
    rough_tex = g.node(unreal.MaterialExpressionDotProduct)
    g.link(orm, "RGB", rough_tex, "A")
    g.link(g.vector("RoughChannel", (0, 1, 0)), "", rough_tex, "B")
    metal_tex = g.node(unreal.MaterialExpressionDotProduct)
    g.link(orm, "RGB", metal_tex, "A")
    g.link(g.vector("MetalChannel", (0, 0, 1)), "", metal_tex, "B")
    rough = g.lerp(g.scalar("Roughness", 0.8), rough_tex, use)
    metal = g.lerp(g.scalar("Metallic", 0.0), g.mul(metal_tex, g.scalar("MetalScale", 1.0)), use)
    g.out(rough, unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(metal, unreal.MaterialProperty.MP_METALLIC)
    if foliage:
        g.out(base, unreal.MaterialProperty.MP_OPACITY_MASK, "A")
        try:
            g.settings(opacity_mask_clip_value=0.4)
        except Exception:  # noqa: BLE001
            pass
        # same gentle wind sway as M_DA_Foliage
        wp = g.node(unreal.MaterialExpressionWorldPosition)
        obj = g.node(unreal.MaterialExpressionObjectPositionWS)
        t = g.node(unreal.MaterialExpressionTime)
        wpx = g.one_input(unreal.MaterialExpressionComponentMask, wp, r=True, g=False, b=False, a=False)
        wpy = g.one_input(unreal.MaterialExpressionComponentMask, wp, r=False, g=True, b=False, a=False)
        phase = g.add(g.mul(t, g.scalar("WindSpeed", 1.4)), g.mul(g.add(wpx, wpy), g.const(0.004)))
        sway = g.mul(g.one_input(unreal.MaterialExpressionSine, phase), g.scalar("WindAmount", 6.0))
        wpz = g.one_input(unreal.MaterialExpressionComponentMask, wp, r=False, g=False, b=True, a=False)
        objz = g.one_input(unreal.MaterialExpressionComponentMask, obj, r=False, g=False, b=True, a=False)
        height = g.one_input(unreal.MaterialExpressionSaturate, g.mul(g.sub(wpz, objz), g.const(0.0012)))
        amt = g.mul(sway, height)
        xy = g.node(unreal.MaterialExpressionAppendVector)
        g.link(amt, "", xy, "A")
        g.link(g.mul(amt, g.const(0.6)), "", xy, "B")
        xyz = g.node(unreal.MaterialExpressionAppendVector)
        g.link(xy, "", xyz, "A")
        g.link(g.const(0.0), "", xyz, "B")
        g.out(xyz, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    return g.finish()


def build_toon(name, mpc, masked=False):
    """Anime cast shading: lit base colour plus an emissive 'fill' of the same colour, which flattens the
    shadow side the way cel shading does. The fill fades at night (MPC NightFactor) so nobody glows."""
    g = Graph(name)
    if masked:
        g.settings(blend_mode=unreal.BlendMode.BLEND_MASKED, two_sided=True)
    uv = g.node(unreal.MaterialExpressionTextureCoordinate)
    base = g.tex("BaseTex", T("T_White"), S_COL, uv)
    col = g.mul(base, g.vector("Tint", (1, 1, 1)), "RGB", "")
    # optional tiling detail (planks, tiles, tatami weave) for interior surfaces; off (0) for the cast
    det = g.tex("DetailTex", T("T_Grunge_D"), S_LIN, g.mul(uv, g.scalar("Tiling", 1.0)))
    detail = g.lerp(g.const(1.0), g.mul(det, g.const(2.0), "R"), g.scalar("DetailStrength", 0.0))
    col = g.mul(col, detail)
    g.out(col, unreal.MaterialProperty.MP_BASE_COLOR)
    day = g.sub(g.const(1.0), g.mul(night_factor(g, mpc), g.const(0.75)))
    g.out(g.mul(g.mul(col, g.scalar("Fill", 0.45)), day), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    g.out(g.scalar("Roughness", 0.85), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.const(0.15), unreal.MaterialProperty.MP_SPECULAR)
    if masked:
        g.out(base, unreal.MaterialProperty.MP_OPACITY_MASK, "A")
        try:
            g.settings(opacity_mask_clip_value=0.5)
        except Exception:  # noqa: BLE001
            pass
    # morph targets: the cast faces blink / lip-sync through morphs; without the usage flag a cooked build
    # has no morph permutation of the material (the editor only patches it in for the running session)
    g.settings(used_with_skeletal_mesh=True, used_with_morph_targets=True)
    return g.finish()


def build_outline(mpc):
    """Ink line: unlit, one-sided (the inverted hull only shows around the silhouette)."""
    g = Graph("M_DA_Outline")
    g.settings(shading_model=unreal.MaterialShadingModel.MSM_UNLIT, used_with_skeletal_mesh=True,
               used_with_morph_targets=True)
    day = g.sub(g.const(1.0), g.mul(night_factor(g, mpc), g.const(0.5)))
    g.out(g.mul(g.vector("Tint", (0.09, 0.06, 0.07)), day), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return g.finish()


def _smooth_band(g, x, lo, hi):
    """saturate((x - lo) / (hi - lo)): a linear step from lo to hi (hi < lo flips it)."""
    return g.one_input(unreal.MaterialExpressionSaturate, g.mul(g.sub(x, g.const(lo)), g.const(1.0 / (hi - lo))))


def build_cel(name, mpc, masked=False):
    """Anime cast master (see the module docstring and Tools/dai/anime/cel.py)."""
    g = Graph(name)
    if masked:
        g.settings(blend_mode=unreal.BlendMode.BLEND_MASKED, two_sided=True)
    uv = g.node(unreal.MaterialExpressionTextureCoordinate)
    base = g.tex("BaseTex", T("T_White"), S_COL, uv)
    col = g.mul(base, g.vector("Tint", (1, 1, 1)), "RGB", "")
    g.out(col, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.const(0.0), unreal.MaterialProperty.MP_SPECULAR)
    g.out(g.const(1.0), unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.const(0.0), unreal.MaterialProperty.MP_METALLIC)
    key = g.node(unreal.MaterialExpressionCollectionParameter, collection=mpc, parameter_name="SunDirection")
    key_dir = g.one_input(unreal.MaterialExpressionComponentMask, key, "", r=True, g=True, b=True, a=False)
    key_w = g.one_input(unreal.MaterialExpressionComponentMask, key, "", r=False, g=False, b=False, a=True)
    n = g.node(unreal.MaterialExpressionVertexNormalWS)
    v = g.node(unreal.MaterialExpressionCameraVectorWS)
    ndl = g.op(unreal.MaterialExpressionDotProduct, n, key_dir)
    # lit side of the half-Lambert ramp (the post process does the actual banding with real shadows)
    lit = _smooth_band(g, g.add(g.mul(ndl, g.const(0.5)), g.const(0.5)), 0.40, 0.55)
    day = g.sub(g.const(1.0), g.mul(night_factor(g, mpc), g.const(0.7)))
    # rim: thin bright edge on the silhouette, on the side the key light comes from
    ndv = g.op(unreal.MaterialExpressionDotProduct, n, v)
    edge = _smooth_band(g, ndv, 0.32, 0.20)
    side = _smooth_band(g, g.op(unreal.MaterialExpressionDotProduct, key_dir, g.mul(v, g.const(-1.0))), -0.6, 0.2)
    rim = g.mul(g.mul(edge, side), g.scalar("Rim", 0.18))
    rim_col = g.lerp(col, g.const3((1.0, 0.98, 0.95)), g.const(0.55))
    emissive = g.mul(rim_col, rim)
    # angel ring on hair: annulus of N.H (cel.RING_NH)
    h = g.one_input(unreal.MaterialExpressionNormalize, g.add(v, key_dir))
    nh = g.op(unreal.MaterialExpressionDotProduct, n, h)
    ring = g.mul(_smooth_band(g, nh, 0.785, 0.80), _smooth_band(g, nh, 0.875, 0.86))
    ring = g.mul(g.mul(ring, lit), g.scalar("HairSpec", 0.0))
    emissive = g.add(emissive, g.mul(g.const3((1.0, 0.97, 0.92)), g.mul(ring, g.const(2.0))))
    # a little self-illumination so the shadow side never goes muddy (anime shadows are a colour, not black)
    emissive = g.add(emissive, g.mul(col, g.scalar("Fill", 0.08)))
    g.out(g.mul(g.mul(emissive, day), key_w), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if masked:
        g.out(base, unreal.MaterialProperty.MP_OPACITY_MASK, "A")
        try:
            g.settings(opacity_mask_clip_value=0.5)
        except Exception:  # noqa: BLE001
            pass
    # morph targets: the cast faces blink / lip-sync through morphs; without the usage flag a cooked build
    # has no morph permutation of the material (the editor only patches it in for the running session)
    g.settings(used_with_skeletal_mesh=True, used_with_morph_targets=True)
    return g.finish()


def build_cel_post(name="PP_DA_Cel"):
    """Stencil-masked cel banding of the cast's lighting (the module docstring)."""
    g = Graph(name)
    g.settings(material_domain=unreal.MaterialDomain.MD_POST_PROCESS)
    try:
        g.settings(blendable_location=unreal.BlendableLocation.BL_SCENE_COLOR_BEFORE_DOF)
    except Exception:  # noqa: BLE001 - older enum spelling
        g.settings(blendable_location=unreal.BlendableLocation.BL_BEFORE_TONEMAPPING)

    def scene(tid):
        return g.node(unreal.MaterialExpressionSceneTexture, scene_texture_id=tid)
    sc = g.one_input(unreal.MaterialExpressionComponentMask, scene(unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0), "Color",
                     r=True, g=True, b=True, a=False)
    dif = g.one_input(unreal.MaterialExpressionComponentMask, scene(unreal.SceneTextureId.PPI_DIFFUSE_COLOR), "Color",
                      r=True, g=True, b=True, a=False)
    stencil = scene(unreal.SceneTextureId.PPI_CUSTOM_STENCIL)
    luma = g.const3((0.3, 0.59, 0.11))
    dif_l = g.op(unreal.MaterialExpressionDotProduct, dif, luma)
    # light arriving at the pixel (colour) = scene colour / albedo
    light = g.op(unreal.MaterialExpressionDivide, sc, g.op(unreal.MaterialExpressionMax, dif, g.const(0.03)))
    lum = g.op(unreal.MaterialExpressionMax, g.op(unreal.MaterialExpressionDotProduct, light, luma), g.const(1e-4))
    hue = g.lerp(g.const3((1, 1, 1)), g.op(unreal.MaterialExpressionDivide, light, lum), g.const(0.6))
    exposure = g.node(unreal.MaterialExpressionEyeAdaptation)
    lum_e = g.mul(lum, exposure)                    # display-referred light level (~1 = fully lit)
    thr, soft = g.scalar("Threshold", 0.42), g.scalar("Softness", 0.06)
    lit = g.one_input(unreal.MaterialExpressionSaturate,
                      g.add(g.op(unreal.MaterialExpressionDivide, g.sub(lum_e, thr), soft), g.const(0.5)))
    lit_level = g.scalar("LitLevel", 1.0)
    # lit band: flat, but brighter-than-lit highlights (rim, hair ring, a lamp right next to them) survive
    lit_v = g.add(lit_level, g.mul(g.op(unreal.MaterialExpressionMax, g.sub(lum_e, lit_level), g.const(0.0)), g.const(0.6)))
    shadow_v = g.lerp(g.scalar("ShadowLevel", 0.52), lum_e, g.const(0.2))
    band = g.op(unreal.MaterialExpressionDivide, g.lerp(shadow_v, lit_v, lit), g.op(unreal.MaterialExpressionMax, exposure, g.const(1e-4)))
    # shadow colour: more saturated and a touch cooler than the albedo (cel shading's coloured shadows)
    sat = g.op(unreal.MaterialExpressionDivide, dif, g.op(unreal.MaterialExpressionMax, dif_l, g.const(1e-3)))
    shadow_tint = g.mul(g.lerp(g.const3((1, 1, 1)), sat, g.scalar("ShadowSaturation", 0.35)), g.const3((0.88, 0.88, 1.0)))
    tint = g.lerp(shadow_tint, g.const3((1, 1, 1)), lit)
    cel = g.mul(g.mul(g.mul(dif, hue), band), tint)
    # only the cast (stencil 1) and only lit surfaces with an albedo (the unlit ink outline keeps its colour)
    st = g.one_input(unreal.MaterialExpressionComponentMask, stencil, "Color", r=True, g=False, b=False, a=False)
    is_cast = g.one_input(unreal.MaterialExpressionSaturate,
                          g.sub(g.const(1.0), g.one_input(unreal.MaterialExpressionAbs, g.sub(st, g.const(1.0)))))
    has_albedo = _smooth_band(g, dif_l, 0.01, 0.03)
    k = g.mul(g.mul(is_cast, has_albedo), g.scalar("Strength", 1.0))
    g.out(g.lerp(sc, cel, k), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    MEL.layout_material_expressions(g.mat)
    MEL.recompile_material(g.mat)
    unreal.EditorAssetLibrary.save_loaded_asset(g.mat)
    return g.mat


TERRAIN_LAYERS = [
    # layer, splat (texture, channel) - Grass is the base layer (weight = whatever the others leave)
    ("Grass", None),
    ("ForestFloor", ("B", "G")),
    ("Sand", ("A", "R")),
    ("WetSand", ("B", "B")),
    ("Ash", ("B", "R")),
    ("Rock", ("A", "G")),
    ("Dirt", ("A", "B")),
    ("Paving", ("A", "A")),
]


# How each layer takes over from what lies under it (M_DA_Terrain, M_DA_Road): (height influence k, softness s).
# With a = saturate((2 w - 1 + (h - h_below) k) / s + 0.5) and s <= 2 (1 - k), a layer is exactly absent at
# weight 0 and exactly complete at weight 1; in between its own relief decides where it shows first - tufts,
# stones and ridges break through, joints and hollows fill last - so no two grounds ever cross-fade.
LAYER_BLEND = {
    "ForestFloor": (0.6, 0.7), "Sand": (0.5, 0.9), "WetSand": (0.4, 1.0), "Ash": (0.5, 0.8),
    "Rock": (0.7, 0.5), "Dirt": (0.6, 0.6), "Paving": (0.3, 0.35),
}
BLEND_NOISE = 0.5      # how far the break-up noise shifts a transition (never where a weight is 0 or 1)


def _height_blend(g, weight, height, below, name, noise=None, weight_out=""):
    """Blend factor of a layer over the surface below it (see LAYER_BLEND)."""
    k, soft = LAYER_BLEND[name]
    w = g.sat(weight, weight_out)
    if noise is not None:
        # w + (n - 0.5) B 4 w (1 - w): shifts the edge, leaves pure areas pure
        bell = g.mul(g.mul(w, g.one_minus(w)), g.const(4.0 * BLEND_NOISE))
        w = g.sat(g.add(w, g.mul(g.sub(noise, g.const(0.5)), bell)))
    rel = g.mul(g.sub(height, below), g.scalar(f"{name}BlendHeight", k))
    x = g.add(g.sub(g.mul(w, g.const(2.0)), g.const(1.0)), rel)
    return g.sat(g.add(g.div(x, g.scalar(f"{name}BlendSoft", min(soft, 2.0 * (1.0 - k)))), g.const(0.5)))


def _terrain_surface(g, uv, info, world_m, road=None):
    """The ground at `uv` (island-normalised, the splat maps' layout): colour, normal, roughness.

    Eight layers (T_Terrain_<Layer>_BC / _N / _R / _H) chosen by the splat maps and blended by height
    (_height_blend). road = (paving, earth): extra 0..1 coverages laid over the result with the very same
    blend, first the terrain's own Dirt layer (trodden earth: footpaths), then its Paving layer - 0 gives
    the terrain exactly, 1 that layer - which is what M_DA_Road draws on road ribbons, footpaths and bridge
    decks, so paving, path, verge and ground are one continuous surface."""
    splat_a = g.tex("SplatA", T("T_TerrainSplatA"), S_MSK, uv)
    splat_b = g.tex("SplatB", T("T_TerrainSplatB"), S_MSK, uv)
    # large-scale brightness variation breaks up visible tiling
    var = g.tex("VariationNoise", T("T_Noise"), S_LIN, g.mul(uv, g.const(6.0)))
    var2 = g.tex("VariationNoise2", T("T_Noise"), S_LIN, g.mul(uv, g.const(41.0)), param=False)
    vmix = g.add(g.mul(var, g.const(0.6), "R"), g.mul(var2, g.const(0.4), "R"))
    brightness = g.lerp(g.const(0.82), g.const(1.15), vmix)
    # fine noise (about 7 m and 2.5 m) that frays the edge of every transition
    fray1 = g.tex("", T("T_Noise"), S_LIN, g.mul(uv, g.const(world_m / 7.0)), param=False)
    fray2 = g.tex("", T("T_Noise"), S_LIN, g.mul(uv, g.const(world_m / 2.6)), param=False)
    fray = g.add(g.mul(fray1, g.const(0.6), "R"), g.mul(fray2, g.const(0.4), "R"))
    color = normal = rough = height = None
    n_out, r_out = "RGB", "R"
    paving = dirt = None
    for name, splat in TERRAIN_LAYERS:
        tile_m = float(info.get(name, {}).get("tile_m", 4.0))
        luv = g.mul(uv, g.scalar(f"{name}Tiles", world_m / tile_m))
        c = g.mul(g.tex(f"{name}Albedo", T(f"T_Terrain_{name}_BC"), S_COL, luv), g.vector(f"{name}Tint", (1, 1, 1)), "RGB", "")
        n = g.tex(f"{name}Normal", T(f"T_Terrain_{name}_N"), S_NRM, luv)
        r = g.tex(f"{name}Rough", T(f"T_Terrain_{name}_R"), S_MSK, luv)
        h_tex = T(f"T_Terrain_{name}_H")      # relief; a flat 0.5 without it (plain cross-fade edges)
        h = g.mask(g.tex(f"{name}Height", h_tex, S_MSK, luv), "r") if h_tex is not None else g.const(0.5)
        if name == "Paving":
            paving = (c, n, r, h)
        if name == "Dirt":
            dirt = (c, n, r, h)
        if splat is None:
            color, normal, rough, height = c, n, r, h
            continue
        tex_node = splat_a if splat[0] == "A" else splat_b
        a = _height_blend(g, tex_node, h, height, name, noise=fray, weight_out=splat[1])
        color = g.lerp(color, c, a)
        normal = g.lerp(normal, n, a, n_out, "RGB")
        rough = g.lerp(rough, r, a, r_out, "R")
        height = g.lerp(height, h, a)
        n_out, r_out = "", ""
    if road is not None:
        cover, earth = road
        for layer, name, amount in ((dirt, "Dirt", earth), (paving, "Paving", cover)):
            if layer is None or amount is None:
                continue
            c, n, r, h = layer
            a = _height_blend(g, amount, h, height, name, noise=fray)
            color = g.lerp(color, c, a)
            normal = g.lerp(normal, n, a, "", "RGB")
            rough = g.lerp(rough, r, a, "", "R")
            height = g.lerp(height, h, a)
    color = g.mul(color, brightness)
    return color, normal, rough


def _terrain_finish(g, uv, color, normal, rough, mpc, frame=None):
    """Far-distance macro colour, wet shoreline, water darkening and caustics, then the outputs - shared by
    the terrain and the road material so the two cannot drift apart.
    frame: None = the normal is in the mesh's own tangent space (the terrain: its UVs are the island's);
    else a +1 / -1 node (the sign of dv/dy) and the normal goes out in world space."""
    # far distance: blend to the baked colour map so the island reads well from afar
    macro = g.tex("ColorMap", T("T_TerrainColor"), S_COL, uv, clamp=True)
    depth = g.node(unreal.MaterialExpressionPixelDepth)
    far = g.one_input(unreal.MaterialExpressionSaturate, g.mul(g.sub(depth, g.const(12000.0)), g.const(1.0 / 50000.0)))
    final = g.lerp(color, macro, g.mul(far, g.scalar("MacroBlend", 0.75)), "", "RGB")
    roughness = g.mul(rough, g.scalar("RoughnessScale", 1.0))
    shore_tex = T("T_WaterShore")
    if shore_tex is not None:
        sh = g.tex("", shore_tex, S_MSK, uv, param=False, clamp=True)
        wet = g.mul(sh, g.scalar("WetStrength", 0.8), "A", "")
        under = g.mask(sh, "b")
        # wet sand / soil: darker, more saturated, glossy
        final = g.mul(final, g.lerp(g.const(1.0), g.const(0.62), wet))
        final = g.mul(final, g.lerp(g.const(1.0), g.scalar("SubmergedDarken", 0.8), under))
        roughness = g.lerp(roughness, g.const(0.25), wet)
        caustics_tex = T("T_Caustics")
        if caustics_tex is not None:
            wxy = g.mask(g.node(unreal.MaterialExpressionWorldPosition), "rg")
            cuv = g.mul(wxy, g.scalar("CausticScale", 1.0 / 350.0))
            time = g.node(unreal.MaterialExpressionTime)
            c1p = g.node(unreal.MaterialExpressionPanner, speed_x=0.03, speed_y=0.018)
            g.link(cuv, "", c1p, "Coordinate")
            g.link(time, "", c1p, "Time")
            c2p = g.node(unreal.MaterialExpressionPanner, speed_x=-0.022, speed_y=0.027)
            g.link(g.mul(cuv, g.const(1.37)), "", c2p, "Coordinate")
            g.link(time, "", c2p, "Time")
            c1 = g.tex("", caustics_tex, S_LIN, c1p, param=False)
            c2 = g.tex("", caustics_tex, S_LIN, c2p, param=False)
            net = g.op(unreal.MaterialExpressionMin, c1, c2, "R", "R")
            # only under water, fading with depth (R: 0 at the waterline .. 1 at >= 8 m), only by day
            amount = g.mul(g.mul(under, g.lerp(g.const(1.0), g.const(0.25), sh, "", "", "R")),
                           g.scalar("CausticStrength", 1.6))
            if mpc is not None:
                amount = g.mul(amount, g.one_minus(night_factor(g, mpc)))
            final = g.mul(final, g.add(g.mul(net, amount), g.const(1.0)))
    g.out(final, unreal.MaterialProperty.MP_BASE_COLOR)
    normal = g.lerp(g.const3((0, 0, 1)), normal, g.scalar("NormalStrength", 1.0))
    if frame is not None:
        # the terrain's tangent frame rebuilt on another mesh (M_DA_Road): tangent = world +X, bitangent =
        # the direction v grows in, both laid into the surface - the layer normals light a ribbon or a bridge
        # deck exactly as they light the ground, whatever UVs and rotation that mesh has
        vn = g.node(unreal.MaterialExpressionVertexNormalWS)
        x_axis = g.const3((1, 0, 0))
        tangent = g.one_input(unreal.MaterialExpressionNormalize, g.sub(x_axis, g.mul(vn, g.dot(vn, x_axis))))
        bitangent = g.mul(g.op(unreal.MaterialExpressionCrossProduct, vn, tangent), frame)
        ws = g.add(g.add(g.mul(tangent, g.mask(normal, "r")), g.mul(bitangent, g.mask(normal, "g"))),
                   g.mul(vn, g.mask(normal, "b")))
        normal = g.one_input(unreal.MaterialExpressionNormalize, ws)
    g.out(normal, unreal.MaterialProperty.MP_NORMAL)
    g.out(roughness, unreal.MaterialProperty.MP_ROUGHNESS)


def _terrain_inputs():
    try:
        info = C.load_json("terrain_layers.json")
    except Exception:  # noqa: BLE001
        info = {}
    try:
        world_m = float(C.load_json("layout.json")["world"]["size"]) / 100.0
    except Exception:  # noqa: BLE001 - layout.json is optional for a material-only rebuild
        world_m = C.WORLD_SIZE_M   # Tools/dai/config.py WORLD_SIZE (see common.py)
    return info, world_m


def build_terrain(mpc=None):
    """8-layer splat terrain with full-colour (photo or procedural) layer textures:
    T_Terrain_<Layer>_BC / _N / _R / _H, per-layer tiling from Data/terrain_layers.json. The layers are
    blended by height (LAYER_BLEND), never cross-faded.
    With T_WaterShore (same layout as the splat maps: R depth, G shore distance, B submerged, A wet band on
    land): the ground is darker and smoother where the water has just been (WetStrength), darker under water
    (SubmergedDarken), and under water by day a moving caustic network (T_Caustics, world aligned, two layers
    combined with min) brightens it - strongest in the shallows."""
    info, world_m = _terrain_inputs()
    g = Graph("M_DA_Terrain")
    uv = g.node(unreal.MaterialExpressionTextureCoordinate)
    color, normal, rough = _terrain_surface(g, uv, info, world_m)
    _terrain_finish(g, uv, color, normal, rough, mpc)
    return g.finish()


def build_road(mpc=None):
    """M_DA_Road - road ribbons, footpaths and paved bridge decks: the terrain material looked up by world
    position instead of mesh UVs, with the terrain's own layers laid over it by the mesh's vertex colour:
    R = paving coverage (a mesh without vertex colours is paved all over), G - R = trodden earth (the
    footpaths from a road to the doors of the houses beside it).

    Because it *is* the terrain's surface function, a ribbon whose rim is painted 0 shows there exactly what
    the ground under it shows (the dirt verge the splat map paints along every road, the paving of a plaza it
    ends on), and its paved middle is the same stone, at the same scale and brightness, as any paved ground:
    road, verge, pad and bridge deck meet without a seam. The layer normals are applied in the terrain's
    tangent frame (world space output), not the mesh's. MirrorY = 1 for a level built with a mirrored Y axis."""
    info, world_m = _terrain_inputs()
    g = Graph("M_DA_Road")
    xy = g.mask(g.node(unreal.MaterialExpressionWorldPosition), "rg")
    iuv = g.add(g.mul(xy, g.const(1.0 / ISLAND_SIZE_CM)), g.const(-ISLAND_MIN_CM / ISLAND_SIZE_CM))
    iu, iv = g.mask(iuv, "r"), g.mask(iuv, "g")
    mirror = g.scalar("MirrorY", 0.0)
    uv = g.append(iu, g.lerp(iv, g.one_minus(iv), mirror))
    vc = g.node(unreal.MaterialExpressionVertexColor)
    cover = g.mul(vc, g.scalar("Paving", 1.0), "R", "")
    # earth = G - R: green alone is a footpath; white (a mesh without colours) and the greys of the road
    # ribbons carry none
    earth = g.mul(g.sat(g.sub(vc, vc, "G", "R")), g.scalar("Earth", 1.0))
    color, normal, rough = _terrain_surface(g, uv, info, world_m, road=(cover, earth))
    g.settings(tangent_space_normal=False)
    _terrain_finish(g, uv, color, normal, rough, mpc, frame=g.lerp(g.const(1.0), g.const(-1.0), mirror))
    return g.finish()


# --------------------------------------------------------------------------- instances
KIND_PARENT = {
    "opaque": "M_DA_Master", "foliage": "M_DA_Foliage", "glass": "M_DA_Glass", "emissive": "M_DA_Emissive",
    "water": "M_DA_Water", "pool": "M_DA_PoolWater", "river": "M_DA_River",
    "lava": "M_DA_Lava", "hologram": "M_DA_Hologram", "smoke": "M_DA_Smoke",
    "beam": "M_DA_Beam", "waterfall": "M_DA_Waterfall", "flow": "M_DA_WaterFlow", "terrain": "M_DA_Terrain",
    "road": "M_DA_Road",
    "pbr": "M_DA_PBR", "pbr_foliage": "M_DA_PBRFoliage",
    "toon": "M_DA_Toon", "toon_masked": "M_DA_ToonMasked", "outline": "M_DA_Outline",
    "cel": "M_DA_Cel", "cel_masked": "M_DA_CelMasked",
}

CHANNEL = {"R": (1, 0, 0), "G": (0, 1, 0), "B": (0, 0, 1), "A": (0, 0, 0)}

NIGHT_ONLY_EMISSIVE = {"M_LampGlow", "M_LighthouseLamp"}

# palette key -> M_DA_WaterFlow scalar parameter (default = the master's)
FLOW_PARAMS = (("opacity", "Opacity", 0.55), ("flow", "FlowSpeed", 2.4), ("streak", "StreakScale", 1.6),
               ("stretch", "StreakStretch", 4.0), ("foam_scale", "FoamScale", 1.0), ("foam_speed", "FoamSpeed", 1.0),
               ("base", "Base", 0.25), ("contrast", "Contrast", 1.8), ("sparkle", "Sparkle", 0.5),
               ("wobble", "Wobble", 1.0))


# palette key -> scalar parameter, per water kind (missing keys keep the master's default)
WATER_PARAMS = (("wave_scale", "WaveScale"), ("wave_speed", "WaveSpeed"), ("wave_strength", "WaveStrength"))
POOL_PARAMS = WATER_PARAMS + (("ripple", "Ripple"), ("ripple_scale", "RippleScale"), ("ripple_speed", "RippleSpeed"))
RIVER_PARAMS = (("flow", "Flow"), ("foam", "Foam"), ("wave_strength", "WaveStrength"))


def is_open_water(spec):
    """Palette kind "water" covers the sea and the lake (waves / wave mask / shoreline: M_DA_Water) and, from
    before the pool kind existed, plain still water (aquaria, baths, ponds): that goes on M_DA_PoolWater -
    tangent-space normals, so it also works on faces that are not level, and none of the wave maths."""
    return bool(spec.get("waves") or spec.get("shore") or spec.get("mask"))


def load_water():
    """Data/water.json (wave sets, wave mask, rivers), or {} for a SourceAssets folder without it."""
    try:
        data = C.load_json("water.json")
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001 - optional: everything falls back to flat water
        return {}


def wave_slots(waves, mirror_y=False):
    """water.json wave list -> [(A, B, C)] 4-tuples for the Wave<i>A / B / C parameters of M_DA_Water, padded
    with zero-amplitude slots, and the largest possible fold sum(k s A) (FoldMax).
    A = (dir.x / L, dir.y / L, speed / L, phase / 2 pi), B = (A, s A, k A, k s A), C = (dir.x, dir.y, 0, 0);
    a missing / non-positive speed is the deep-water speed sqrt(g L / 2 pi), g = 981 cm/s^2."""
    slots, fold_max = [], 0.0
    for w in list(waves or [])[:WAVE_SLOTS]:
        try:
            dx, dy = float(w["dir"][0]), float(w["dir"][1])
            length, amp = float(w["wavelength"]), float(w["amplitude"])
            steep = min(max(float(w.get("steepness", 0.0)), 0.0), 1.0)
            speed, phase = float(w.get("speed", 0.0)), float(w.get("phase", 0.0))
        except (KeyError, IndexError, TypeError, ValueError):
            continue
        norm = (dx * dx + dy * dy) ** 0.5
        if length <= 1.0 or amp == 0.0 or norm < 1e-9:
            continue
        dx, dy = dx / norm, (-dy if mirror_y else dy) / norm
        if speed <= 0.0:
            speed = (981.0 * length / TWO_PI) ** 0.5
        k = TWO_PI / length
        slots.append(((dx / length, dy / length, speed / length, phase / TWO_PI),
                      (amp, steep * amp, k * amp, k * steep * amp), (dx, dy, 0.0, 0.0)))
        fold_max += k * steep * abs(amp)
    while len(slots) < WAVE_SLOTS:
        slots.append(((0.0, 0.0, 0.0, 0.0), (0.0, 0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0)))
    return slots, fold_max


def _set_water_instance(mi, spec, water, mirror_y=False):
    """Parameters of an M_DA_Water instance (palette kind "water")."""
    c = spec["color_linear"]
    MEL.set_material_instance_vector_parameter_value(mi, "ScatterColor", C.lc((c[0] * 0.35, c[1] * 0.35, c[2] * 0.35)))
    MEL.set_material_instance_vector_parameter_value(mi, "Absorption", C.lc((0.45 - c[0] * 0.3, 0.08 + (0.4 - c[1]) * 0.1, 0.05 + (0.4 - c[2]) * 0.1)))
    for key, param in WATER_PARAMS:
        if key in spec:
            MEL.set_material_instance_scalar_parameter_value(mi, param, float(spec[key]))
    body = water.get(str(spec.get("waves", "")), {}) if spec.get("waves") else {}
    slots, fold_max = wave_slots(body.get("waves") if isinstance(body, dict) else None, mirror_y)
    for i, (a, b, d) in enumerate(slots, 1):
        MEL.set_material_instance_vector_parameter_value(mi, f"Wave{i}A", C.lc(a[:3], a[3]))
        MEL.set_material_instance_vector_parameter_value(mi, f"Wave{i}B", C.lc(b[:3], b[3]))
        MEL.set_material_instance_vector_parameter_value(mi, f"Wave{i}C", C.lc(d[:3], d[3]))
    has_waves = fold_max > 0.0 or any(b[0] != 0.0 for _, b, _ in slots)
    shore = bool(spec.get("shore", False))
    scalars = {
        "FoldMax": fold_max if fold_max > 1e-6 else 1.0,
        "MaskAmount": 1.0 if spec.get("mask") else 0.0,
        "ShoreAmount": 1.0 if shore else 0.0,
        "ShoreFoam": float(spec.get("foam", 0.8 if shore else 0.0)),
        "Crest": float(spec.get("crest", 0.0)) if has_waves else 0.0,
        "MirrorY": 1.0 if mirror_y else 0.0,
    }
    fade = body.get("fade") if isinstance(body, dict) else None
    if isinstance(fade, (list, tuple)) and len(fade) == 2:
        scalars["WaveFadeStart"], scalars["WaveFadeEnd"] = float(fade[0]), float(fade[1])
    for param, value in scalars.items():
        MEL.set_material_instance_scalar_parameter_value(mi, param, value)


def mirror_water_instances(palette, instances):
    """The level is being built with a mirrored Y axis (build.py axis check): point the Gerstner waves and the
    island-wide map lookups of every sea / lake instance the same way, so the material still matches
    ADAIslandManager's wave queries."""
    water = load_water()
    n = 0
    for name, spec in palette.items():
        mi = instances.get(name) or C.load(f"{C.MAT_DIR}/MI_{name}")
        if spec.get("kind") == "road" and mi is not None:
            # M_DA_Road looks the terrain's maps up by world position: mirror that lookup with the level
            try:
                MEL.set_material_instance_scalar_parameter_value(mi, "MirrorY", 1.0)
                MEL.update_material_instance(mi)
                unreal.EditorAssetLibrary.save_loaded_asset(mi)
                n += 1
            except Exception as e:  # noqa: BLE001
                C.warn(f"MI_{name}: mirroring the road lookup failed: {e}")
            continue
        if spec.get("kind") != "water" or not is_open_water(spec) or mi is None:
            continue
        try:
            _set_water_instance(mi, spec, water, mirror_y=True)
            MEL.update_material_instance(mi)
            unreal.EditorAssetLibrary.save_loaded_asset(mi)
            n += 1
        except Exception as e:  # noqa: BLE001
            C.warn(f"MI_{name}: mirroring the water parameters failed: {e}")
    return n


def build_instances(palette, masters):
    out = {}
    water = load_water()
    for name, spec in palette.items():
        kind = spec.get("kind", "opaque")
        if kind in ("toon", "cel") and spec.get("masked"):
            kind = kind + "_masked"
        still = kind == "water" and not is_open_water(spec) and masters.get("M_DA_PoolWater") is not None
        if still:
            kind = "pool"
        parent = masters.get(KIND_PARENT.get(kind, "M_DA_Master"))
        if parent is None and kind in ("pool", "river"):
            parent = masters.get("M_DA_Water")      # still water rather than no material at all
            kind = "water" if parent is not None else kind
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
            elif kind in ("pbr", "pbr_foliage"):
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", float(spec.get("rough", 0.8)))
                MEL.set_material_instance_scalar_parameter_value(mi, "Metallic", float(spec.get("metallic", 0.0)))
                for key, param in (("base", "BaseTex"), ("normal", "NormalTex"), ("orm", "ORMTex")):
                    if spec.get(key):
                        tex = T(spec[key])
                        if tex:
                            MEL.set_material_instance_texture_parameter_value(mi, param, tex)
                        else:
                            C.warn(f"{mi_name}: texture {spec[key]} missing")
                if spec.get("orm") and T(spec["orm"]):
                    MEL.set_material_instance_scalar_parameter_value(mi, "UseORM", 1.0)
                    rc = spec.get("rough_channel", "G")
                    MEL.set_material_instance_vector_parameter_value(mi, "RoughChannel", C.lc(CHANNEL.get(rc, (0, 1, 0))))
                    # glTF packs metallic in B next to roughness in G; single-channel roughness maps carry no metal
                    MEL.set_material_instance_scalar_parameter_value(mi, "MetalScale", 1.0 if rc == "G" else 0.0)
            elif kind in ("toon", "toon_masked"):
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Fill", float(spec.get("fill", 0.45)))
                MEL.set_material_instance_scalar_parameter_value(mi, "Roughness", float(spec.get("rough", 0.85)))
                detail = spec.get("detail")
                if detail and T(f"T_{detail}_D"):
                    MEL.set_material_instance_texture_parameter_value(mi, "DetailTex", T(f"T_{detail}_D"))
                    MEL.set_material_instance_scalar_parameter_value(mi, "DetailStrength", float(spec.get("detail_strength", 0.55)))
                    MEL.set_material_instance_scalar_parameter_value(mi, "Tiling", float(spec.get("tiling", 1.0)))
                if spec.get("base"):
                    tex = T(spec["base"])
                    if tex:
                        MEL.set_material_instance_texture_parameter_value(mi, "BaseTex", tex)
                    else:
                        C.warn(f"{mi_name}: texture {spec['base']} missing")
            elif kind in ("cel", "cel_masked"):
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Rim", float(spec.get("rim", 0.18)))
                MEL.set_material_instance_scalar_parameter_value(mi, "HairSpec", float(spec.get("spec", 0.0)))
                # flat parts (eyes, brows, mouth) glow a little more so the post-process never darkens them
                fill = 0.35 if spec.get("cel") == "flat" else 0.08
                MEL.set_material_instance_scalar_parameter_value(mi, "Fill", fill)
                if spec.get("base"):
                    tex = T(spec["base"])
                    if tex:
                        MEL.set_material_instance_texture_parameter_value(mi, "BaseTex", tex)
                    else:
                        C.warn(f"{mi_name}: texture {spec['base']} missing")
            elif kind == "outline":
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
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
                _set_water_instance(mi, spec, water)
            elif kind in ("pool", "river"):
                c = spec["color_linear"]
                MEL.set_material_instance_vector_parameter_value(mi, "ScatterColor", C.lc((c[0] * 0.35, c[1] * 0.35, c[2] * 0.35)))
                MEL.set_material_instance_vector_parameter_value(mi, "Absorption", C.lc((0.45 - c[0] * 0.3, 0.08 + (0.4 - c[1]) * 0.1, 0.05 + (0.4 - c[2]) * 0.1)))
                for key, param in (POOL_PARAMS if kind == "pool" else RIVER_PARAMS):
                    if key in spec:
                        MEL.set_material_instance_scalar_parameter_value(mi, param, float(spec[key]))
                if still and "ripple" not in spec:
                    # plain still water from the "water" kind: no fountain droplets fall into it
                    MEL.set_material_instance_scalar_parameter_value(mi, "Ripple", 0.0)
            elif kind == "road":
                # the terrain's surface with its Paving layer laid on by vertex colour: nothing to tint
                MEL.set_material_instance_scalar_parameter_value(mi, "Paving", float(spec.get("paving", 1.0)))
                MEL.set_material_instance_scalar_parameter_value(mi, "Earth", float(spec.get("earth", 1.0)))
                MEL.set_material_instance_scalar_parameter_value(mi, "MirrorY", 0.0)
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
            elif kind == "flow":
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                for key, param, default in FLOW_PARAMS:
                    MEL.set_material_instance_scalar_parameter_value(mi, param, float(spec.get(key, default)))
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
                     ("M_DA_PoolWater", build_pool_water), ("M_DA_River", build_river),
                     ("M_DA_Lava", build_lava), ("M_DA_Hologram", build_hologram), ("M_DA_Smoke", build_smoke),
                     ("M_DA_Beam", build_beam), ("M_DA_Waterfall", build_waterfall),
                     ("M_DA_WaterFlow", build_water_flow), ("M_DA_Spray", build_spray),
                     ("M_DA_Terrain", lambda: build_terrain(mpc)),
                     ("M_DA_Road", lambda: build_road(mpc)),
                     ("M_DA_PBR", lambda: build_pbr("M_DA_PBR")),
                     ("M_DA_PBRFoliage", lambda: build_pbr("M_DA_PBRFoliage", foliage=True)),
                     ("M_DA_Toon", lambda: build_toon("M_DA_Toon", mpc)),
                     ("M_DA_ToonMasked", lambda: build_toon("M_DA_ToonMasked", mpc, masked=True)),
                     ("M_DA_Outline", lambda: build_outline(mpc)),
                     ("M_DA_Cel", lambda: build_cel("M_DA_Cel", mpc)),
                     ("M_DA_CelMasked", lambda: build_cel("M_DA_CelMasked", mpc, masked=True)),
                     ("PP_DA_Cel", build_cel_post)):
        try:
            masters[name] = fn()
        except Exception as e:  # noqa: BLE001
            C.error(f"master material {name} failed: {e}")
    C.log(f"master materials: {sorted(masters)}")
    instances = build_instances(palette, masters)
    return mpc, masters, instances
