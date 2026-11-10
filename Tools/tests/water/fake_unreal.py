"""A stand-in for the Unreal Editor's ``unreal`` Python module, just big enough to build the water materials
of DuelAcademyIsland/Content/Python/duel_academy/materials.py outside the engine.

It is deliberately strict where the real editor is silent or only fails at shader-compile time:

* only the material expression classes listed in EXPRESSIONS exist (anything else is an AttributeError, as in
  the editor), each with the input pins, output pins and editable properties the real class has;
* connecting to a pin that does not exist returns False (as MaterialEditingLibrary does);
* setting a parameter on a material instance that its parent does not declare is recorded in PROBLEMS;
* a texture sample without a texture, or with a sampler type that does not match the texture, is a PROBLEM
  (in the editor: a material that fails to compile and renders as the grey default material).

It can also *evaluate* a recorded graph numerically (evaluate()), which is how the tests prove that the node
graph of M_DA_Water computes the contract's Gerstner formulas.

Everything here is test scaffolding; nothing is imported by the game or the editor scripts.
"""

import math

# --------------------------------------------------------------------------- log + asset registry
LOG = {"log": [], "warning": [], "error": []}
PROBLEMS = []          # things the real editor would only show as a broken material
ASSETS = {}            # object path -> fake asset
DIRECTORIES = set()
PROJECT_DIR = "."      # set by the test: the folder that holds SourceAssets/Data


def reset(project_dir="."):
    global PROJECT_DIR
    for entries in LOG.values():
        entries.clear()
    PROBLEMS.clear()
    ASSETS.clear()
    DIRECTORIES.clear()
    PROJECT_DIR = project_dir


def log(message):
    LOG["log"].append(str(message))


def log_warning(message):
    LOG["warning"].append(str(message))


def log_error(message):
    LOG["error"].append(str(message))


class Paths:
    @staticmethod
    def project_dir():
        return PROJECT_DIR

    @staticmethod
    def convert_relative_path_to_full(path):
        return path


# --------------------------------------------------------------------------- value types
class LinearColor:
    def __init__(self, r=0.0, g=0.0, b=0.0, a=1.0):
        self.r, self.g, self.b, self.a = float(r), float(g), float(b), float(a)

    def rgba(self):
        return (self.r, self.g, self.b, self.a)


class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        self.x, self.y, self.z = float(x), float(y), float(z)


class Vector2D:
    def __init__(self, x=0.0, y=0.0):
        self.x, self.y = float(x), float(y)


def _enum(name, *members):
    return type(name, (), {m: f"{name}.{m}" for m in members})


MaterialSamplerType = _enum("MaterialSamplerType", "SAMPLERTYPE_COLOR", "SAMPLERTYPE_LINEAR_COLOR",
                            "SAMPLERTYPE_NORMAL", "SAMPLERTYPE_MASKS")
SamplerSourceMode = _enum("SamplerSourceMode", "SSM_FROM_TEXTURE_ASSET", "SSM_WRAP_WORLD_GROUP_SETTINGS",
                          "SSM_CLAMP_WORLD_GROUP_SETTINGS")
MaterialShadingModel = _enum("MaterialShadingModel", "MSM_UNLIT", "MSM_DEFAULT_LIT", "MSM_SINGLE_LAYER_WATER")
BlendMode = _enum("BlendMode", "BLEND_OPAQUE", "BLEND_MASKED", "BLEND_TRANSLUCENT", "BLEND_ADDITIVE")
TranslucencyLightingMode = _enum("TranslucencyLightingMode", "TLM_VOLUMETRIC_NON_DIRECTIONAL",
                                 "TLM_SURFACE_PER_PIXEL_LIGHTING")
TextureMipValueMode = _enum("TextureMipValueMode", "TMVM_NONE", "TMVM_MIP_LEVEL", "TMVM_MIP_BIAS")
MaterialProperty = _enum("MaterialProperty", "MP_BASE_COLOR", "MP_METALLIC", "MP_SPECULAR", "MP_ROUGHNESS",
                         "MP_EMISSIVE_COLOR", "MP_OPACITY", "MP_OPACITY_MASK", "MP_NORMAL",
                         "MP_WORLD_POSITION_OFFSET", "MP_AMBIENT_OCCLUSION", "MP_REFRACTION")

# sampler type each kind of fake texture needs (importer.texture_kind -> compression / sRGB -> sampler)
SAMPLER_FOR_KIND = {"color": MaterialSamplerType.SAMPLERTYPE_COLOR, "linear": MaterialSamplerType.SAMPLERTYPE_LINEAR_COLOR,
                    "normal": MaterialSamplerType.SAMPLERTYPE_NORMAL, "masks": MaterialSamplerType.SAMPLERTYPE_MASKS}


class Texture2D:
    def __init__(self, name, kind):
        self.name, self.kind = name, kind

    def get_name(self):
        return self.name


def register_texture(name, kind, folder="/Game/DuelAcademy/Textures"):
    tex = Texture2D(name, kind)
    ASSETS[f"{folder}/{name}"] = tex
    return tex


# --------------------------------------------------------------------------- material expressions
# class -> (input pins in order, output pins in order, editable properties). Pin and property names are the
# real ones of UE 5 (MaterialEditingLibrary matches pins by these names; "" = the first pin).
_TEX_OUT = ("RGB", "R", "G", "B", "A", "RGBA")
_TEX_PROPS = ("texture", "sampler_type", "sampler_source", "mip_value_mode", "const_mip_value", "const_coordinate")
EXPRESSIONS = {
    "MaterialExpressionWorldPosition": ((), ("XYZ",), ("world_position_shader_offset",)),
    "MaterialExpressionVertexNormalWS": ((), ("",), ()),
    "MaterialExpressionTime": ((), ("",), ("ignore_pause", "override_period", "period")),
    "MaterialExpressionPixelDepth": ((), ("",), ()),
    "MaterialExpressionTextureCoordinate": ((), ("",), ("coordinate_index", "u_tiling", "v_tiling")),
    "MaterialExpressionConstant": ((), ("",), ("r",)),
    "MaterialExpressionConstant3Vector": ((), ("",), ("constant",)),
    "MaterialExpressionScalarParameter": ((), ("",), ("parameter_name", "default_value", "group")),
    "MaterialExpressionVectorParameter": ((), ("", "R", "G", "B", "A"), ("parameter_name", "default_value", "group")),
    "MaterialExpressionCollectionParameter": ((), ("",), ("collection", "parameter_name")),
    "MaterialExpressionPerInstanceCustomData": (("DefaultValue",), ("",), ("data_index", "const_default_value")),
    "MaterialExpressionTextureSample": (("UVs", "Tex", "Apply View MipBias"), _TEX_OUT, _TEX_PROPS),
    "MaterialExpressionTextureSampleParameter2D": (("UVs", "Apply View MipBias"), _TEX_OUT,
                                                   _TEX_PROPS + ("parameter_name", "group")),
    "MaterialExpressionPanner": (("Coordinate", "Time", "Speed"), ("",), ("speed_x", "speed_y", "const_coordinate")),
    "MaterialExpressionComponentMask": (("Input",), ("",), ("r", "g", "b", "a")),
    "MaterialExpressionAppendVector": (("A", "B"), ("",), ()),
    "MaterialExpressionMultiply": (("A", "B"), ("",), ("const_a", "const_b")),
    "MaterialExpressionAdd": (("A", "B"), ("",), ("const_a", "const_b")),
    "MaterialExpressionSubtract": (("A", "B"), ("",), ("const_a", "const_b")),
    "MaterialExpressionDivide": (("A", "B"), ("",), ("const_a", "const_b")),
    "MaterialExpressionMax": (("A", "B"), ("",), ("const_a", "const_b")),
    "MaterialExpressionMin": (("A", "B"), ("",), ("const_a", "const_b")),
    "MaterialExpressionDotProduct": (("A", "B"), ("",), ()),
    "MaterialExpressionLinearInterpolate": (("A", "B", "Alpha"), ("",), ("const_a", "const_b", "const_alpha")),
    "MaterialExpressionSine": (("Input",), ("",), ("period",)),
    "MaterialExpressionCosine": (("Input",), ("",), ("period",)),
    "MaterialExpressionSaturate": (("Input",), ("",), ()),
    "MaterialExpressionOneMinus": (("Input",), ("",), ()),
    "MaterialExpressionAbs": (("Input",), ("",), ()),
    "MaterialExpressionFrac": (("Input",), ("",), ()),
    "MaterialExpressionNormalize": (("VectorInput",), ("",), ()),
    "MaterialExpressionFresnel": (("ExponentIn", "BaseReflectFractionIn", "Normal"), ("",),
                                  ("exponent", "base_reflect_fraction")),
    "MaterialExpressionDepthFade": (("Opacity", "FadeDistance"), ("",), ("opacity_default", "fade_distance_default")),
    "MaterialExpressionSingleLayerWaterMaterialOutput": (
        ("Scattering Coefficients", "Absorption Coefficients", "Phase G", "Color Scale Behind Water"), (), ()),
}
# every input of these must be wired (their unconnected defaults are never what the water graphs want)
ALL_INPUTS_REQUIRED = {
    "MaterialExpressionComponentMask", "MaterialExpressionAppendVector", "MaterialExpressionMultiply",
    "MaterialExpressionAdd", "MaterialExpressionSubtract", "MaterialExpressionDivide", "MaterialExpressionMax",
    "MaterialExpressionMin", "MaterialExpressionDotProduct", "MaterialExpressionLinearInterpolate",
    "MaterialExpressionSine", "MaterialExpressionCosine", "MaterialExpressionSaturate", "MaterialExpressionOneMinus",
    "MaterialExpressionAbs", "MaterialExpressionFrac", "MaterialExpressionNormalize",
}
_PROP_DEFAULTS = {"period": 1.0, "coordinate_index": 0, "speed_x": 0.0, "speed_y": 0.0, "r": 0.0}


class MaterialExpression:
    INPUTS = ()
    OUTPUTS = ()
    PROPS = ()

    def __init__(self, material):
        self.material = material
        self.props = {}
        self.inputs = {}       # pin name -> (node, output name)

    def set_editor_property(self, name, value):
        if name not in self.PROPS:
            raise AttributeError(f"{type(self).__name__}: no editable property '{name}'")
        self.props[name] = value

    def get_editor_property(self, name):
        if name not in self.PROPS:
            raise AttributeError(f"{type(self).__name__}: no editable property '{name}'")
        return self.props.get(name, _PROP_DEFAULTS.get(name))

    def prop(self, name):
        return self.props.get(name, _PROP_DEFAULTS.get(name))


for _name, (_ins, _outs, _props) in EXPRESSIONS.items():
    globals()[_name] = type(_name, (MaterialExpression,), {"INPUTS": _ins, "OUTPUTS": _outs, "PROPS": _props})


# --------------------------------------------------------------------------- assets
MATERIAL_PROPS = {"shading_model", "blend_mode", "two_sided", "tangent_space_normal", "translucency_lighting_mode",
                  "used_with_instanced_static_meshes", "used_with_nanite", "used_with_skeletal_mesh"}


class Material:
    def __init__(self, name):
        self.name = name
        self.expressions = []
        self.outputs = {}      # MaterialProperty -> (node, output name)
        self.props = {"tangent_space_normal": True, "blend_mode": BlendMode.BLEND_OPAQUE,
                      "shading_model": MaterialShadingModel.MSM_DEFAULT_LIT}

    def get_name(self):
        return self.name

    def set_editor_property(self, name, value):
        if name not in MATERIAL_PROPS:
            raise AttributeError(f"Material: no editable property '{name}'")
        self.props[name] = value

    def get_editor_property(self, name):
        return self.props.get(name)

    def parameters(self, cls):
        return {str(e.prop("parameter_name")): e for e in self.expressions if isinstance(e, cls)}


class MaterialInstanceConstant:
    def __init__(self, name):
        self.name = name
        self.parent = None
        self.scalars, self.vectors, self.textures = {}, {}, {}

    def get_name(self):
        return self.name


class MaterialParameterCollection:
    def __init__(self, name):
        self.name = name
        self.props = {}

    def set_editor_property(self, name, value):
        self.props[name] = value


class _Bag:
    """Property bag for the small structs (collection parameters)."""

    def __init__(self):
        self.props = {}

    def set_editor_property(self, name, value):
        self.props[name] = value

    def get_editor_property(self, name):
        return self.props.get(name)


class CollectionScalarParameter(_Bag):
    pass


class CollectionVectorParameter(_Bag):
    pass


class MaterialFactoryNew:
    pass


class MaterialInstanceConstantFactoryNew:
    pass


class MaterialParameterCollectionFactoryNew:
    pass


class _AssetTools:
    def create_asset(self, name, folder, cls, factory):
        asset = cls(name)
        ASSETS[f"{folder}/{name}"] = asset
        return asset


class AssetToolsHelpers:
    @staticmethod
    def get_asset_tools():
        return _AssetTools()


class EditorAssetLibrary:
    @staticmethod
    def does_asset_exist(path):
        return path in ASSETS

    @staticmethod
    def load_asset(path):
        return ASSETS.get(path)

    @staticmethod
    def delete_asset(path):
        return ASSETS.pop(path, None) is not None

    @staticmethod
    def save_loaded_asset(asset):
        return True

    @staticmethod
    def does_directory_exist(path):
        return path in DIRECTORIES

    @staticmethod
    def make_directory(path):
        DIRECTORIES.add(path)
        return True


# --------------------------------------------------------------------------- MaterialEditingLibrary
def _pin(names, wanted):
    """The pin called `wanted` ("" = the first one), or None."""
    if wanted == "":
        return names[0] if names else None
    return wanted if wanted in names else None


class MaterialEditingLibrary:
    @staticmethod
    def create_material_expression(material, cls, x=0, y=0):
        if not (isinstance(cls, type) and issubclass(cls, MaterialExpression)):
            raise TypeError(f"not a material expression class: {cls!r}")
        node = cls(material)
        material.expressions.append(node)
        return node

    @staticmethod
    def connect_material_expressions(a, a_out, b, b_in):
        out_pin = _pin(a.OUTPUTS, a_out)
        in_pin = _pin(b.INPUTS, b_in)
        if out_pin is None or in_pin is None:
            return False
        b.inputs[in_pin] = (a, out_pin)
        return True

    @staticmethod
    def connect_material_property(node, out_name, prop):
        out_pin = _pin(node.OUTPUTS, out_name)
        if out_pin is None:
            return False
        node.material.outputs[prop] = (node, out_pin)
        return True

    @staticmethod
    def layout_material_expressions(material):
        return None

    @staticmethod
    def recompile_material(material):
        """What the shader compiler would reject: unwired maths, texture samples without / with the wrong texture."""
        for e in material.expressions:
            cls = type(e).__name__
            if cls in ALL_INPUTS_REQUIRED:
                for pin in e.INPUTS:
                    if pin not in e.inputs:
                        PROBLEMS.append(f"{material.name}: {cls}.{pin} is not connected")
            if cls.startswith("MaterialExpressionTextureSample"):
                tex = e.props.get("texture")
                if tex is None:
                    PROBLEMS.append(f"{material.name}: texture sample without a texture")
                elif SAMPLER_FOR_KIND[tex.kind] != e.props.get("sampler_type"):
                    PROBLEMS.append(f"{material.name}: {tex.name} ({tex.kind}) sampled as {e.props.get('sampler_type')}")

    @staticmethod
    def set_material_instance_parent(instance, parent):
        instance.parent = parent

    @staticmethod
    def _set(instance, store, cls, name, value):
        parent = instance.parent
        if parent is None or str(name) not in parent.parameters(cls):
            PROBLEMS.append(f"{instance.name}: parent {getattr(parent, 'name', None)} has no {cls.__name__[18:]} '{name}'")
            return False
        store[str(name)] = value
        return True

    @classmethod
    def set_material_instance_scalar_parameter_value(cls, instance, name, value):
        return cls._set(instance, instance.scalars, MaterialExpressionScalarParameter, name, float(value))  # noqa: F821

    @classmethod
    def set_material_instance_vector_parameter_value(cls, instance, name, value):
        return cls._set(instance, instance.vectors, MaterialExpressionVectorParameter, name, value)  # noqa: F821

    @classmethod
    def set_material_instance_texture_parameter_value(cls, instance, name, value):
        return cls._set(instance, instance.textures, MaterialExpressionTextureSampleParameter2D, name, value)  # noqa: F821

    @staticmethod
    def update_material_instance(instance):
        return None


# --------------------------------------------------------------------------- numeric evaluation of a graph
def _broadcast(a, b):
    """UE rule: component counts must match, or one side is a scalar."""
    if len(a) == len(b):
        return a, b
    if len(a) == 1:
        return a * len(b), b
    if len(b) == 1:
        return a, b * len(a)
    raise ValueError(f"cannot combine float{len(a)} with float{len(b)}")


def _zip(fn, a, b):
    a, b = _broadcast(a, b)
    return tuple(fn(x, y) for x, y in zip(a, b))


def evaluate(asset, prop, world_position=(0.0, 0.0, 0.0), time=0.0, textures=None, uvs=None, pixel_depth=1000.0):
    """Value (tuple of floats) the graph feeds into material property `prop`.

    asset: a Material, or a MaterialInstanceConstant (its parameter overrides are applied).
    textures: texture name -> fn(u, v) -> (r, g, b, a); uvs: texture coordinate index -> (u, v).
    Only the node types the water graphs use are implemented; anything else raises NotImplementedError.
    """
    textures, uvs = textures or {}, uvs or {}
    instance = asset if isinstance(asset, MaterialInstanceConstant) else None
    material = asset.parent if instance else asset
    cache = {}

    def value(node, out):
        key = (id(node), out)
        if key not in cache:
            cache[key] = compute(node, out)
        return cache[key]

    def pin(node, name):
        if name not in node.inputs:
            raise ValueError(f"{type(node).__name__}.{name} is not connected")
        src, out = node.inputs[name]
        return value(src, out)

    def channel(rgba, out):
        if out in ("", "RGB", "XYZ"):
            return tuple(rgba[:3])
        if out == "RGBA":
            return tuple(rgba)
        return (rgba["RGBA".index(out)],)

    def compute(node, out):
        cls = type(node).__name__[len("MaterialExpression"):]
        if cls == "WorldPosition":
            return tuple(float(c) for c in world_position)
        if cls == "Time":
            return (float(time),)
        if cls == "PixelDepth":
            return (float(pixel_depth),)
        if cls == "TextureCoordinate":
            return tuple(float(c) for c in uvs.get(int(node.prop("coordinate_index")), (0.0, 0.0)))
        if cls == "Constant":
            return (float(node.prop("r")),)
        if cls == "Constant3Vector":
            return node.props["constant"].rgba()[:3]
        if cls == "ScalarParameter":
            name = str(node.prop("parameter_name"))
            return (float(instance.scalars[name]) if instance and name in instance.scalars
                    else float(node.props["default_value"]),)
        if cls == "VectorParameter":
            name = str(node.prop("parameter_name"))
            color = instance.vectors[name] if instance and name in instance.vectors else node.props["default_value"]
            return channel(color.rgba(), out)
        if cls in ("TextureSample", "TextureSampleParameter2D"):
            u, v = pin(node, "UVs")[:2]
            return channel(textures[node.props["texture"].name](u, v), out)
        if cls == "Panner":
            coord = pin(node, "Coordinate")
            t = pin(node, "Time")[0] if "Time" in node.inputs else float(time)
            return (coord[0] + node.prop("speed_x") * t, coord[1] + node.prop("speed_y") * t)
        if cls == "ComponentMask":
            src = pin(node, "Input")
            return tuple(src[i] for i, c in enumerate("rgba") if node.props.get(c) and i < len(src))
        if cls == "AppendVector":
            return pin(node, "A") + pin(node, "B")
        if cls in ("Multiply", "Add", "Subtract", "Divide", "Max", "Min"):
            fn = {"Multiply": lambda x, y: x * y, "Add": lambda x, y: x + y, "Subtract": lambda x, y: x - y,
                  "Divide": lambda x, y: x / y, "Max": max, "Min": min}[cls]
            return _zip(fn, pin(node, "A"), pin(node, "B"))
        if cls == "DotProduct":
            a, b = _broadcast(pin(node, "A"), pin(node, "B"))
            return (sum(x * y for x, y in zip(a, b)),)
        if cls == "LinearInterpolate":
            a, b = _broadcast(pin(node, "A"), pin(node, "B"))
            alpha = pin(node, "Alpha")
            a, alpha = _broadcast(a, alpha)
            b, alpha = _broadcast(b, alpha)
            return tuple(x + (y - x) * k for x, y, k in zip(a, b, alpha))
        if cls in ("Sine", "Cosine"):
            period = float(node.prop("period"))
            fn = math.sin if cls == "Sine" else math.cos
            # UMaterialExpressionSine: sin(Input * 2 pi / Period) for a positive period, else sin(Input)
            return tuple(fn(x * 2.0 * math.pi / period) if period > 0.0 else fn(x) for x in pin(node, "Input"))
        if cls == "Saturate":
            return tuple(min(max(x, 0.0), 1.0) for x in pin(node, "Input"))
        if cls == "OneMinus":
            return tuple(1.0 - x for x in pin(node, "Input"))
        if cls == "Abs":
            return tuple(abs(x) for x in pin(node, "Input"))
        if cls == "Frac":
            return tuple(x - math.floor(x) for x in pin(node, "Input"))
        if cls == "Normalize":
            v = pin(node, "VectorInput")
            length = math.sqrt(sum(x * x for x in v)) or 1.0
            return tuple(x / length for x in v)
        raise NotImplementedError(f"evaluate: {cls}")

    node, out = material.outputs[prop]
    return value(node, out)
