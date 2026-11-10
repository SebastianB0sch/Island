"""
Builds the Duel Academy master materials (node graphs created in code) and one
Material Instance per palette entry (Data/materials.json).

Masters (in /Game/DuelAcademy/Materials):
  M_DA_Master      opaque PBR: Tint * detail texture, detail normal
  M_DA_Foliage     two-sided, wind sway (world position offset)
  M_DA_Glass       translucent glass
  M_DA_Emissive    glowing surfaces; brighter at night (MPC NightFactor)
  M_DA_Water       realistic single layer water (ocean, lake, ponds, pools): Gerstner waves, shore surf,
                   whitecaps, detail ripples, depth / shore data from T_WaterField (Tools/dai/water.py)
  M_DA_Lava        panning emissive lava
  M_DA_Hologram    additive hologram (duel monsters, markers)
  M_DA_Smoke       translucent puffs, opacity from per-instance custom data
  M_DA_Beam        additive light beam
  M_DA_WaterFlow   falling / flowing water (falls, fountain sheets and jets, spouts, white water): world-aligned, so no UVs - vertical faces stream
                   along world Z (FlowSpeed, < 0 = rising jets), flat faces churn; glints, soft contact, wobble
  M_DA_Spray       droplets of ADAEmitter's Spray kind (opacity from per-instance custom data)
  M_DA_Terrain     splat-mapped terrain (8 layers)
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
  PP_DA_Underwater post-process under the sea / lake: light absorbed along the view ray, blue-green
                   in-scatter fog, a slight wobble (MPC Underwater)
  MPC_DuelAcademy  NightFactor / TimeOfDay / SunDirection / Underwater / WaterSurfaceZ (ADAIslandManager)
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
    # Underwater (0..1) / WaterSurfaceZ (cm): set by ADAIslandManager when the camera dips below the sea or lake
    for n, v in (("NightFactor", 0.0), ("TimeOfDay", 16.0), ("Underwater", 0.0), ("WaterSurfaceZ", 0.0)):
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


# Custom (HLSL) nodes: the wave / foam maths lives in water_hlsl.py so it can be unit-tested without Unreal
_CMOT = {1: "CMOT_FLOAT1", 2: "CMOT_FLOAT2", 3: "CMOT_FLOAT3", 4: "CMOT_FLOAT4"}


def custom(g, desc, code, inputs, size=3, extra=()):
    """Custom expression: `inputs` = {name: (node, output)}; extra = ((name, size), ...) additional outputs."""
    n = g.node(unreal.MaterialExpressionCustom, code=code, description=desc,
               output_type=getattr(unreal.CustomMaterialOutputType, _CMOT[size]))
    try:
        n.set_editor_property("inputs", [unreal.CustomInput(input_name=k) for k in inputs])
        if extra:
            n.set_editor_property("additional_outputs", [
                unreal.CustomOutput(output_name=k, output_type=getattr(unreal.CustomMaterialOutputType, _CMOT[sz]))
                for k, sz in extra])
    except Exception as e:  # noqa: BLE001
        C.warn(f"{g.name}: custom node {desc}: {e}")
    for k, (src, out) in inputs.items():
        g.link(src, out, n, k)
    return n


def _world_pos(g):
    """World position before any material offset (the waves move vertices; their maths needs the rest
    position in both the vertex and the pixel shader)."""
    wp = g.node(unreal.MaterialExpressionWorldPosition)
    try:
        wp.set_editor_property("world_position_shader_offset",
                               unreal.WorldPositionIncludedOffsets.WPT_EXCLUDE_ALL_SHADER_OFFSETS)
    except Exception as e:  # noqa: BLE001
        C.warn(f"{g.name}: world position without offsets: {e}")
    return wp


def _field_sample(g, wp, use_field):
    """T_WaterField at this world XY (mip 0: it is also read in the vertex shader), or 'open deep sea'
    (depth max, far from shore, exposed, not lake) when the instance does not use it."""
    try:
        world_cm = float(C.load_json("layout.json")["world"]["size"])
    except Exception:  # noqa: BLE001 - layout.json is optional for a material-only rebuild
        world_cm = C.WORLD_SIZE_M * 100.0
    xy = g.one_input(unreal.MaterialExpressionComponentMask, wp, r=True, g=True, b=False, a=False)
    uv = g.mul(g.add(xy, g.const(world_cm / 2.0)), g.const(1.0 / world_cm))
    f = g.tex("", T("T_WaterField") or T("T_White"), S_LIN, uv, param=False)
    try:
        f.set_editor_property("mip_value_mode", unreal.TextureMipValueMode.TMVM_MIP_LEVEL)
        f.set_editor_property("const_mip_value", 0)
        # the texture's own clamp, not the shared wrapping sampler: beyond the island square the edge texels
        # (open deep sea) must continue - wrapping would repeat the island's shallows every 3 km out at sea
        f.set_editor_property("sampler_source", unreal.SamplerSourceMode.SSM_FROM_TEXTURE_ASSET)
    except Exception as e:  # noqa: BLE001
        C.warn(f"{g.name}: water field sampler: {e}")
    open_sea = g.node(unreal.MaterialExpressionConstant4Vector, constant=unreal.LinearColor(1.0, 1.0, 1.0, 0.0))
    return g.lerp(open_sea, f, use_field, "", "RGBA")


# scalar parameters of M_DA_Water: palette key, parameter, default (= the ocean)
WATER_PARAMS = (
    ("wave_height", "WaveHeight", 1.0), ("wave_length", "WaveLength", 1.0), ("choppy", "Choppy", 1.0),
    ("wind_angle", "WindAngle", 0.0), ("mesh_spacing", "MeshSpacing", 1.5), ("clipmap", "ClipmapRatio", 1.0 / 32.0),
    ("use_field", "UseField", 1.0), ("foam", "FoamAmount", 1.0), ("surf", "SurfAmount", 1.0),
    ("surf_spacing", "SurfSpacing", 9.0), ("surf_period", "SurfPeriod", 7.0), ("surf_width", "SurfWidth", 35.0),
    ("caps_at", "CapsAt", 0.75), ("detail_scale", "DetailScale", 0.12), ("detail_speed", "DetailSpeed", 1.0),
    ("detail_strength", "DetailStrength", 0.3), ("macro_strength", "MacroStrength", 0.12),
    ("detail_fade", "DetailFade", 250.0), ("rough", "Roughness", 0.02),
)


def build_water():
    """Realistic water (ocean, lake, ponds, pools, a glass of water) - single layer water shading:
      * waves: Gerstner sum displacing the surface (WPO) with matching per-pixel normals (water_hlsl.py),
        calmed over shallows and in sheltered water by T_WaterField, faded by mesh / pixel resolution;
      * detail: three world-aligned T_WaterNormal layers (two crossing wind ripples, one macro layer that
        breaks the tiling far out), dragged downstream by FlowVelocity in rivers;
      * foam: surf bands rolling onto the beaches, a lapping rim at the waterline and whitecaps on the
        sharpest crests, broken up by churned foam - drawn as the water's top layer (opacity);
      * light: absorption / scattering per body of water (clear tropical sea, green lake, milky hot spring),
        F0 0.02, refraction, rougher far away where the ripples are too small to resolve."""
    from . import water_hlsl as W
    g = Graph("M_DA_Water")
    ok = True
    try:
        g.settings(shading_model=unreal.MaterialShadingModel.MSM_SINGLE_LAYER_WATER)
    except Exception:  # noqa: BLE001
        ok = False
    g.settings(tangent_space_normal=False)        # the wave normals are world space
    P = {k: g.scalar(name, v) for k, name, v in WATER_PARAMS}
    wp = _world_pos(g)
    t = g.node(unreal.MaterialExpressionTime)
    cam = g.node(unreal.MaterialExpressionCameraPositionWS)
    field = _field_sample(g, wp, P["use_field"])
    common = {"P": (wp, ""), "T": (t, ""), "Field": (field, ""), "Cam": (cam, ""), "Height": (P["wave_height"], ""),
              "Len": (P["wave_length"], ""), "Choppy": (P["choppy"], ""), "Wind": (P["wind_angle"], ""),
              "Spacing": (P["mesh_spacing"], ""), "Clip": (P["clipmap"], "")}
    # ---- waves
    wpo = custom(g, "Gerstner offset", W.wpo_code(), common)
    g.out(wpo, unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    wn = custom(g, "Gerstner normal", W.normal_code(), common, extra=(("Crest", 1),))
    # ---- detail ripples
    flow = g.vector("FlowVelocity", (0.0, 0.0, 0.0))
    duv = custom(g, "Detail UVs", W.detail_uv_code(),
                 {"P": (wp, ""), "T": (t, ""), "Scale": (P["detail_scale"], ""), "Speed": (P["detail_speed"], ""),
                  "Flow": (flow, "")}, size=2, extra=(("UV2", 2), ("UV3", 2)))
    layers = []
    for out in ("", "UV2", "UV3"):
        n = g.tex("", T("T_WaterNormal"), S_NRM, None, param=False)
        g.link(duv, out, n, "UVs")
        layers.append(n)
    normal = custom(g, "Combine normals", (
        "float dist = length(P - Cam) * 0.01;\n"
        "float fade = lerp(1.0, 0.3, saturate(dist / Fade));\n"
        "float2 d = (D1.xy + D2.xy) * S * fade + D3.xy * M;\n"
        "return normalize(Ng + float3(d, 0));\n"),
        {"Ng": (wn, ""), "D1": (layers[0], "RGB"), "D2": (layers[1], "RGB"), "D3": (layers[2], "RGB"),
         "S": (P["detail_strength"], ""), "M": (P["macro_strength"], ""), "Fade": (P["detail_fade"], ""),
         "P": (wp, ""), "Cam": (cam, "")})
    g.out(normal, unreal.MaterialProperty.MP_NORMAL)
    # ---- foam
    xy = g.mul(g.one_input(unreal.MaterialExpressionComponentMask, wp, r=True, g=True, b=False, a=False),
               g.const(0.01))
    churn1 = g.node(unreal.MaterialExpressionPanner, speed_x=0.05, speed_y=0.03)
    g.link(g.mul(xy, g.const(0.45)), "", churn1, "Coordinate")
    churn2 = g.node(unreal.MaterialExpressionPanner, speed_x=-0.04, speed_y=0.05)
    g.link(g.mul(xy, g.const(0.8)), "", churn2, "Coordinate")
    streaks = T("T_WaterStreaks") or T("T_Noise")
    churn = g.mul(g.add(g.tex("", streaks, S_LIN, churn1, param=False), g.tex("", streaks, S_LIN, churn2, param=False),
                        "G", "G"), g.const(0.5))
    breakup = g.tex("", T("T_Noise"), S_LIN, g.mul(xy, g.const(1.0 / 60.0)), param=False)
    foam = custom(g, "Foam", W.foam_code(),
                  {"Field": (field, ""), "T": (t, ""), "Crest": (wn, "Crest"), "Churn": (churn, ""),
                   "Breakup": (breakup, "R"), "Foam": (P["foam"], ""), "Surf": (P["surf"], ""),
                   "SurfSpacing": (P["surf_spacing"], ""), "SurfPeriod": (P["surf_period"], ""),
                   "SurfWidth": (P["surf_width"], ""), "CapsAt": (P["caps_at"], "")}, size=1)
    rough = custom(g, "Roughness", (
        "float dist = length(P - Cam) * 0.01;\n"
        "return lerp(R + 0.08 * saturate(dist / 1500.0), 0.6, Foam);\n"),
        {"R": (P["rough"], ""), "Foam": (foam, ""), "P": (wp, ""), "Cam": (cam, "")}, size=1)
    g.out(rough, unreal.MaterialProperty.MP_ROUGHNESS)
    g.out(g.const(0.0), unreal.MaterialProperty.MP_METALLIC)
    g.out(g.const(0.255), unreal.MaterialProperty.MP_SPECULAR)          # F0 = 0.02 (water)
    scatter = g.vector("ScatterColor", (0.004, 0.022, 0.03))
    absorb = g.vector("Absorption", (0.38, 0.055, 0.03))
    foam_col = g.mul(g.vector("FoamColor", (0.88, 0.91, 0.92)), foam)
    if ok:
        g.out(foam_col, unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(foam, unreal.MaterialProperty.MP_OPACITY)                   # SLW: coverage of the foam top layer
        g.out(g.const(1.33), unreal.MaterialProperty.MP_REFRACTION)
        slw = g.node(unreal.MaterialExpressionSingleLayerWaterMaterialOutput)
        g.link(scatter, "", slw, "ScatteringCoefficients")
        g.link(absorb, "", slw, "AbsorptionCoefficients")
        g.link(g.const(0.2), "", slw, "PhaseG")
    else:
        g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT)
        g.out(g.add(g.mul(scatter, g.const(12.0)), foam_col), unreal.MaterialProperty.MP_BASE_COLOR)
        g.out(g.add(g.const(0.8), g.mul(foam, g.const(0.2))), unreal.MaterialProperty.MP_OPACITY)
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


def build_water_flow():
    """Fountain water: overflow sheets, jets and foam (palette kind "flow", Tools/dai/assets/fountain.py).
    World-aligned instead of UV-mapped, so any lathe, tube or ring flows the right way:
      * vertical faces sample T_WaterStreaks (R / B: threads stretched along V) in the two side projections,
        V = world Z (m) + Time * FlowSpeed - streaks fall at FlowSpeed m/s, rise for a negative speed.
        Two layers (the second finer and 1.37x faster) so it never reads as one sliding picture;
      * flat faces churn: the foam channel (G) under two crossing panners (FoamScale, FoamSpeed), and on a
        sloped sheet the churn also slides downhill at FlowSpeed (a waterfall's lip, a chute);
      * opacity = Opacity * lerp(Base, 1, streaks) (+ a little at grazing angles), depth-faded where the
        water meets the pool or the stone; white glints (Sparkle); a slight surface wobble (Wobble, cm)."""
    g = Graph("M_DA_WaterFlow")
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
    flow = g.mul(t, g.scalar("FlowSpeed", 2.4))
    su = g.scalar("StreakScale", 1.6)
    sv = g.op(unreal.MaterialExpressionDivide, su, g.scalar("StreakStretch", 4.0))
    v1 = g.mul(g.add(z, flow), sv)
    v2 = g.mul(g.add(z, g.mul(flow, g.const(1.37))), g.mul(sv, g.const(1.9)))

    def side(u):
        a = g.tex("", tex, S_LIN, _append(g, g.mul(u, su), v1), param=False)
        b = g.tex("", tex, S_LIN, _append(g, g.add(g.mul(u, g.mul(su, g.const(1.9))), g.const(0.37)), v2), param=False)
        return g.mul(g.add(a, b, "R", "B"), g.const(0.5))

    s_yz, s_xz = side(y), side(x)        # faces facing +-X see the YZ plane, faces facing +-Y the XZ plane
    w_side = g.add(g.add(ax, ay), g.const(1e-4))
    streak = g.op(unreal.MaterialExpressionDivide, g.add(g.mul(s_yz, ax), g.mul(s_xz, ay)), w_side)
    # ---- flat faces: churning foam, carried downhill on sloped sheets (the normal leans towards the descent;
    # its horizontal part times the sign of its height works for both sides of a two-sided sheet)
    lean = g.mul(_append(g, _mask(g, nrm, "r"), _mask(g, nrm, "g")),
                 g.one_input(unreal.MaterialExpressionSign, _mask(g, nrm, "b")))
    xy = g.mul(g.sub(_append(g, x, y), g.mul(lean, flow)), g.scalar("FoamScale", 1.0))
    ft = g.mul(t, g.scalar("FoamSpeed", 1.0))
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
                      g.add(g.mul(g.sub(s, g.const(0.5)), g.scalar("Contrast", 1.8)), g.const(0.5)))
    # ---- shading
    tint = g.vector("Tint", (0.86, 0.95, 1.0))
    g.out(g.mul(tint, g.lerp(g.const(0.8), g.const(1.1), s01)), unreal.MaterialProperty.MP_BASE_COLOR)
    s2 = g.mul(s01, s01)
    g.out(g.mul(tint, g.mul(g.mul(s2, s2), g.scalar("Sparkle", 0.5))), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    g.out(g.lerp(g.const(0.04), g.const(0.3), s01), unreal.MaterialProperty.MP_ROUGHNESS)
    op = g.mul(g.scalar("Opacity", 0.55), g.lerp(g.scalar("Base", 0.25), g.const(1.0), s01))
    op = g.add(op, g.mul(g.node(unreal.MaterialExpressionFresnel, exponent=3.0), g.const(0.2)))
    df = g.node(unreal.MaterialExpressionDepthFade, fade_distance_default=25.0)
    g.link(g.one_input(unreal.MaterialExpressionSaturate, op), "", df, "Opacity")
    g.out(df, unreal.MaterialProperty.MP_OPACITY)
    # ---- wobble along the normal (a living surface, not a glass shell)
    phase = g.add(g.mul(t, g.const(1.3)), g.mul(g.add(g.add(x, y), z), g.const(0.8)))
    wob = g.mul(g.one_input(unreal.MaterialExpressionSine, phase), g.scalar("Wobble", 1.0))
    g.out(g.mul(nrm, wob), unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)
    return g.finish()


def build_spray():
    """Droplets of ADAEmitter's Spray kind: small bright specks, opacity from per-instance custom data 0.
    (M_DA_Smoke's 3 m depth fade would wipe out droplets a hand's width above the pool.)"""
    g = Graph("M_DA_Spray")
    g.settings(blend_mode=unreal.BlendMode.BLEND_TRANSLUCENT)
    color = g.vector("Color", (0.92, 0.97, 1.0))
    g.out(color, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.mul(color, g.const(0.35)), unreal.MaterialProperty.MP_EMISSIVE_COLOR)
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
    g.settings(used_with_skeletal_mesh=True)
    return g.finish()


def build_outline(mpc):
    """Ink line: unlit, one-sided (the inverted hull only shows around the silhouette)."""
    g = Graph("M_DA_Outline")
    g.settings(shading_model=unreal.MaterialShadingModel.MSM_UNLIT, used_with_skeletal_mesh=True)
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
    g.settings(used_with_skeletal_mesh=True)
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


def build_terrain(mpc=None):
    """8-layer splat terrain with full-colour (photo or procedural) layer textures:
    T_Terrain_<Layer>_BC / _N / _R, per-layer tiling from Data/terrain_layers.json.
    Under the sea and the lake (T_WaterField depth) sunlight focused by the waves dances over the bed:
    two drifting T_Caustics layers, combined with min() so the network shifts and breaks like the real thing,
    strongest in the shallows and gone by ~15 m and at night."""
    try:
        info = C.load_json("terrain_layers.json")
    except Exception:  # noqa: BLE001
        info = {}
    g = Graph("M_DA_Terrain")
    uv = g.node(unreal.MaterialExpressionTextureCoordinate)
    splat_a = g.tex("SplatA", T("T_TerrainSplatA"), S_MSK, uv)
    splat_b = g.tex("SplatB", T("T_TerrainSplatB"), S_MSK, uv)
    try:
        world_m = float(C.load_json("layout.json")["world"]["size"]) / 100.0
    except Exception:  # noqa: BLE001 - layout.json is optional for a material-only rebuild
        world_m = C.WORLD_SIZE_M   # Tools/dai/config.py WORLD_SIZE (see common.py)
    # large-scale brightness variation breaks up visible tiling
    var = g.tex("VariationNoise", T("T_Noise"), S_LIN, g.mul(uv, g.const(6.0)))
    var2 = g.tex("VariationNoise2", T("T_Noise"), S_LIN, g.mul(uv, g.const(41.0)), param=False)
    vmix = g.add(g.mul(var, g.const(0.6), "R"), g.mul(var2, g.const(0.4), "R"))
    brightness = g.lerp(g.const(0.82), g.const(1.15), vmix)
    color = normal = rough = None
    n_out, r_out = "RGB", "R"
    for name, splat in TERRAIN_LAYERS:
        tile_m = float(info.get(name, {}).get("tile_m", 4.0))
        luv = g.mul(uv, g.scalar(f"{name}Tiles", world_m / tile_m))
        c = g.mul(g.tex(f"{name}Albedo", T(f"T_Terrain_{name}_BC"), S_COL, luv), g.vector(f"{name}Tint", (1, 1, 1)), "RGB", "")
        n = g.tex(f"{name}Normal", T(f"T_Terrain_{name}_N"), S_NRM, luv)
        r = g.tex(f"{name}Rough", T(f"T_Terrain_{name}_R"), S_MSK, luv)
        if splat is None:
            color, normal, rough = c, n, r
            continue
        tex_node = splat_a if splat[0] == "A" else splat_b
        color = g.lerp(color, c, tex_node, "", "", splat[1])
        normal = g.lerp(normal, n, tex_node, n_out, "RGB", splat[1])
        rough = g.lerp(rough, r, tex_node, r_out, "R", splat[1])
        n_out, r_out = "", ""
    color = g.mul(color, brightness)
    # caustics on the sea / lake bed
    if T("T_Caustics") is not None and T("T_WaterField") is not None:
        wxy = g.mul(g.one_input(unreal.MaterialExpressionComponentMask, g.node(unreal.MaterialExpressionWorldPosition),
                                r=True, g=True, b=False, a=False), g.const(0.01))
        c1 = g.node(unreal.MaterialExpressionPanner, speed_x=0.035, speed_y=0.02)
        g.link(g.mul(wxy, g.const(1.0 / 3.2)), "", c1, "Coordinate")
        c2 = g.node(unreal.MaterialExpressionPanner, speed_x=-0.028, speed_y=0.037)
        g.link(g.mul(wxy, g.const(1.0 / 2.3)), "", c2, "Coordinate")
        day = g.const(1.0) if mpc is None else g.one_input(unreal.MaterialExpressionOneMinus, night_factor(g, mpc))
        caus = custom(g, "Caustics", (
            "float d = Depth * 40.0;\n"
            "float fade = smoothstep(0.05, 0.5, d) * exp(-d / 7.0);\n"
            "return 1.0 + min(C1, C2) * 2.2 * fade * Day * S;\n"),
            {"C1": (g.tex("", T("T_Caustics"), S_LIN, c1, param=False), "R"),
             "C2": (g.tex("", T("T_Caustics"), S_LIN, c2, param=False), "R"),
             "Depth": (g.tex("", T("T_WaterField"), S_LIN, uv, param=False), "R"),
             "Day": (day, ""), "S": (g.scalar("CausticStrength", 1.6), "")}, size=1)
        color = g.mul(color, caus)
    # far distance: blend to the baked colour map so the island reads well from afar
    macro = g.tex("ColorMap", T("T_TerrainColor"), S_COL, uv)
    depth = g.node(unreal.MaterialExpressionPixelDepth)
    far = g.one_input(unreal.MaterialExpressionSaturate, g.mul(g.sub(depth, g.const(12000.0)), g.const(1.0 / 50000.0)))
    final = g.lerp(color, macro, g.mul(far, g.scalar("MacroBlend", 0.75)), "", "RGB")
    g.out(final, unreal.MaterialProperty.MP_BASE_COLOR)
    g.out(g.lerp(g.const3((0, 0, 1)), normal, g.scalar("NormalStrength", 1.0)), unreal.MaterialProperty.MP_NORMAL)
    g.out(g.mul(rough, g.scalar("RoughnessScale", 1.0)), unreal.MaterialProperty.MP_ROUGHNESS)
    return g.finish()


def build_underwater_post(mpc, name="PP_DA_Underwater"):
    """What the camera sees below the sea or the lake (MPC Underwater, set by ADAIslandManager): the scene
    loses red, then green, along the view ray (Absorption, per metre), blue-green light scattered in the
    water fills in with distance (Density), darker at night; the image wobbles a little."""
    g = Graph(name)
    g.settings(material_domain=unreal.MaterialDomain.MD_POST_PROCESS)
    try:
        g.settings(blendable_location=unreal.BlendableLocation.BL_SCENE_COLOR_BEFORE_DOF)
    except Exception:  # noqa: BLE001 - older enum spelling
        g.settings(blendable_location=unreal.BlendableLocation.BL_BEFORE_TONEMAPPING)
    under = g.node(unreal.MaterialExpressionCollectionParameter, collection=mpc, parameter_name="Underwater")
    t = g.node(unreal.MaterialExpressionTime)
    uv = custom(g, "Wobble", (
        "return UV + float2(sin(T * 1.7 + UV.y * 31.0), cos(T * 1.3 + UV.x * 23.0)) * 0.0025 * U;\n"),
        {"UV": (g.node(unreal.MaterialExpressionScreenPosition), "ViewportUV"), "T": (t, ""), "U": (under, "")}, size=2)
    sc = g.node(unreal.MaterialExpressionSceneTexture, scene_texture_id=unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
    g.link(uv, "", sc, "UVs")
    depth = g.node(unreal.MaterialExpressionSceneTexture, scene_texture_id=unreal.SceneTextureId.PPI_SCENE_DEPTH)
    g.link(uv, "", depth, "UVs")
    out = custom(g, "Underwater", (
        "float d = Depth * 0.01;\n"
        "float3 trans = exp(-d * Absorb);\n"
        "float fogk = 1.0 - exp(-d * Density);\n"
        "float3 fog = FogColor * lerp(1.0, 0.05, Night);\n"
        "float3 water = Scene * trans * (1.0 - fogk) + fog * fogk;\n"
        "return lerp(Scene, water, U);\n"),
        {"Scene": (g.one_input(unreal.MaterialExpressionComponentMask, sc, "Color", r=True, g=True, b=True, a=False), ""),
         "Depth": (g.one_input(unreal.MaterialExpressionComponentMask, depth, "Color", r=True, g=False, b=False, a=False), ""),
         "U": (under, ""), "Night": (night_factor(g, mpc), ""),
         "Absorb": (g.vector("Absorption", (0.38, 0.055, 0.03)), ""), "Density": (g.scalar("Density", 0.06), ""),
         "FogColor": (g.vector("FogColor", (0.02, 0.13, 0.16)), "")})
    g.out(out, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    return g.finish()


# --------------------------------------------------------------------------- instances
KIND_PARENT = {
    "opaque": "M_DA_Master", "foliage": "M_DA_Foliage", "glass": "M_DA_Glass", "emissive": "M_DA_Emissive",
    "water": "M_DA_Water", "lava": "M_DA_Lava", "hologram": "M_DA_Hologram", "smoke": "M_DA_Smoke",
    "beam": "M_DA_Beam", "flow": "M_DA_WaterFlow", "terrain": "M_DA_Terrain",
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


def build_instances(palette, masters):
    out = {}
    for name, spec in palette.items():
        kind = spec.get("kind", "opaque")
        if kind in ("toon", "cel") and spec.get("masked"):
            kind = kind + "_masked"
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
                c = spec["color_linear"]
                # per-metre coefficients: explicit in the palette, else derived from the colour
                scatter = spec.get("scatter") or (c[0] * 0.35, c[1] * 0.35, c[2] * 0.35)
                absorb = spec.get("absorb") or (0.45 - c[0] * 0.3, 0.08 + (0.4 - c[1]) * 0.1, 0.05 + (0.4 - c[2]) * 0.1)
                MEL.set_material_instance_vector_parameter_value(mi, "ScatterColor", C.lc(tuple(scatter)))
                MEL.set_material_instance_vector_parameter_value(mi, "Absorption", C.lc(tuple(absorb)))
                fx, fy = spec.get("flow", (0.0, 0.0))
                MEL.set_material_instance_vector_parameter_value(mi, "FlowVelocity", C.lc((float(fx), float(fy), 0.0)))
                for key, param, default in WATER_PARAMS:
                    MEL.set_material_instance_scalar_parameter_value(mi, param, float(spec.get(key, default)))
            elif kind in ("lava", "beam"):
                MEL.set_material_instance_vector_parameter_value(mi, "Tint", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Strength", float(spec.get("strength", 1.0)))
            elif kind == "hologram":
                MEL.set_material_instance_vector_parameter_value(mi, "Color", col)
                MEL.set_material_instance_scalar_parameter_value(mi, "Intensity", float(spec.get("strength", 4.0)))
            elif kind == "smoke":
                MEL.set_material_instance_vector_parameter_value(mi, "Color", col)
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
                     ("M_DA_Lava", build_lava), ("M_DA_Hologram", build_hologram), ("M_DA_Smoke", build_smoke),
                     ("M_DA_Beam", build_beam),
                     ("M_DA_WaterFlow", build_water_flow), ("M_DA_Spray", build_spray), ("M_DA_Terrain", lambda: build_terrain(mpc)),
                     ("M_DA_PBR", lambda: build_pbr("M_DA_PBR")),
                     ("M_DA_PBRFoliage", lambda: build_pbr("M_DA_PBRFoliage", foliage=True)),
                     ("M_DA_Toon", lambda: build_toon("M_DA_Toon", mpc)),
                     ("M_DA_ToonMasked", lambda: build_toon("M_DA_ToonMasked", mpc, masked=True)),
                     ("M_DA_Outline", lambda: build_outline(mpc)),
                     ("M_DA_Cel", lambda: build_cel("M_DA_Cel", mpc)),
                     ("M_DA_CelMasked", lambda: build_cel("M_DA_CelMasked", mpc, masked=True)),
                     ("PP_DA_Cel", build_cel_post), ("PP_DA_Underwater", lambda: build_underwater_post(mpc))):
        try:
            masters[name] = fn()
        except Exception as e:  # noqa: BLE001
            C.error(f"master material {name} failed: {e}")
    C.log(f"master materials: {sorted(masters)}")
    instances = build_instances(palette, masters)
    return mpc, masters, instances
