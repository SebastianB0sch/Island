"""
Third-party (CC0 / CC-BY) asset ingestion.

Curated assets live in Tools/thirdparty/<pack>/<asset>/ (with SOURCE.txt) and are
mapped onto our catalog names by Tools/thirdparty/registry.json:

{
  "props": {
    "SM_PalmTree_A": {
      "file": "quaternius/palm_tall/palm.glb",   # relative to Tools/thirdparty
      "height": 11.0,          # scale so the bounding box is this tall (or "scale": s)
      "rotate": 0,             # extra yaw (deg) so the front faces -Y
      "collision": "trunk",    # trunk | hull | box | none
      "trunk_radius": 0.35,
      "foliage": ["Leaves"],   # material names (or substrings) that are foliage (masked, two-sided, wind)
      "exclude": ["Icosphere"] # object-name substrings to drop
    }
  },
  "materials": {               # palette overrides: real PBR texture sets for our palette names
    "M_Grass": {...}
  }
}

For every mesh we import the file with Blender, join and normalise it (pivot at
the base centre, metres, front -Y), rename its materials to unique "MT_<asset>_<n>"
slots, extract the PBR textures into SourceAssets/Textures/ThirdParty/<asset>/ and
register a "pbr" / "pbr_foliage" palette entry per material, which the Unreal
build turns into instances of M_DA_PBR / M_DA_PBRFoliage.
"""

import json
import math
import os
import shutil
import subprocess

import bmesh
import bpy
import numpy as np
from mathutils import Matrix, Vector

from . import config as C
from . import palette

TP_DIR = os.path.join(C.TOOLS_DIR, "thirdparty")
REG_PATH = os.path.join(TP_DIR, "registry.json")
TEX_OUT = os.path.join(C.OUT_TEXTURES, "ThirdParty")
GLTF_TRANSFORM_CANDIDATES = [
    os.environ.get("GLTF_TRANSFORM", ""),
    "/home/user/tools-node/node_modules/.bin/gltf-transform",
    shutil.which("gltf-transform") or "",
]

_registry = None


def registry():
    global _registry
    if _registry is None:
        if os.path.exists(REG_PATH):
            with open(REG_PATH, encoding="utf-8") as fp:
                _registry = json.load(fp)
        else:
            _registry = {}
        _registry.setdefault("props", {})
        _registry.setdefault("materials", {})
    return _registry


def has_prop(name):
    spec = registry()["props"].get(name)
    return bool(spec) and os.path.exists(os.path.join(TP_DIR, spec["file"]))


# --------------------------------------------------------------------------- import
def _decode_meshopt(path):
    """Blender's bpy wheel lacks the meshopt decoder; decompress with glTF-Transform when needed."""
    cache = os.path.join(C.CACHE_DIR, "decoded")
    os.makedirs(cache, exist_ok=True)
    out = os.path.join(cache, os.path.basename(path))
    if os.path.exists(out) and os.path.getmtime(out) >= os.path.getmtime(path):
        return out
    for tool in GLTF_TRANSFORM_CANDIDATES:
        if tool and os.path.exists(tool):
            subprocess.run([tool, "copy", path, out], check=True, capture_output=True)
            return out
    raise RuntimeError("meshopt-compressed glTF and no gltf-transform available "
                       "(npm install @gltf-transform/cli and set GLTF_TRANSFORM)")


def import_file(path):
    before = set(bpy.data.objects)
    ext = os.path.splitext(path)[1].lower()
    if ext in (".glb", ".gltf"):
        try:
            bpy.ops.import_scene.gltf(filepath=path)
        except RuntimeError as e:
            if "eshopt" not in str(e):
                raise
            for o in set(bpy.data.objects) - before:
                bpy.data.objects.remove(o, do_unlink=True)
            bpy.ops.import_scene.gltf(filepath=_decode_meshopt(path))
    elif ext == ".fbx":
        bpy.ops.import_scene.fbx(filepath=path)
    elif ext == ".obj":
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise ValueError(f"unsupported format: {path}")
    return [o for o in bpy.data.objects if o not in before]


def _join_static(objs, name, exclude=()):
    meshes = [o for o in objs if o.type == "MESH" and len(o.data.polygons) > 0
              and len(o.data.materials) > 0 and not any(x.lower() in o.name.lower() for x in exclude)]
    if not meshes:
        raise RuntimeError(f"{name}: no usable meshes")
    depsgraph = bpy.context.evaluated_depsgraph_get()
    parts = []
    for o in meshes:
        # bake modifiers (incl. armature rest pose) + world transform into a fresh mesh
        eo = o.evaluated_get(depsgraph)
        me = bpy.data.meshes.new_from_object(eo, preserve_all_data_layers=True, depsgraph=depsgraph)
        me.transform(o.matrix_world)
        po = bpy.data.objects.new(o.name + "_baked", me)
        bpy.context.scene.collection.objects.link(po)
        parts.append(po)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    if len(parts) > 1:
        with bpy.context.temp_override(active_object=parts[0], selected_editable_objects=parts, selected_objects=parts):
            bpy.ops.object.join()
    obj = parts[0]
    obj.name = name
    obj.data.name = name
    return obj


def _normalise(obj, spec):
    me = obj.data
    if spec.get("rotate"):
        me.transform(Matrix.Rotation(math.radians(spec["rotate"]), 4, "Z"))
    if spec.get("rotate_x"):
        me.transform(Matrix.Rotation(math.radians(spec["rotate_x"]), 4, "X"))
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mn, mx = co.min(0), co.max(0)
    s = 1.0
    if spec.get("height"):
        s = spec["height"] / max(mx[2] - mn[2], 1e-6)
    elif spec.get("width"):
        s = spec["width"] / max(mx[0] - mn[0], mx[1] - mn[1], 1e-6)
    elif spec.get("scale"):
        s = spec["scale"]
    if spec.get("origin", "base") == "base":
        off = Vector((-(mn[0] + mx[0]) / 2, -(mn[1] + mx[1]) / 2, -mn[2] + spec.get("z_offset", 0.0)))
    else:
        off = Vector((0, 0, spec.get("z_offset", 0.0)))
    me.transform(Matrix.Translation(off))
    me.transform(Matrix.Diagonal((s, s, s, 1.0)))
    me.update()


# --------------------------------------------------------------------------- materials / textures
def _image_from(socket, depth=0):
    """Follow links upstream to the first image texture node."""
    if socket is None or not socket.is_linked or depth > 6:
        return None, None
    link = socket.links[0]
    node = link.from_node
    if node.type == "TEX_IMAGE" and node.image is not None:
        return node.image, link.from_socket.name
    if node.type in ("SEPARATE_COLOR", "SEPRGB", "SEPARATE_RGB"):
        img, _ = _image_from(node.inputs[0], depth + 1)
        return img, "channel:" + link.from_socket.name
    if node.type == "NORMAL_MAP":
        return _image_from(node.inputs.get("Color"), depth + 1)
    for inp in node.inputs:
        if inp.is_linked:
            img, out = _image_from(inp, depth + 1)
            if img is not None:
                return img, out
    return None, None


def _save_image(img, path, max_size=2048, mode=None):
    if os.path.exists(path):
        return path
    w, h = img.size[:]
    if w == 0 or h == 0:
        return None
    px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, -1)
    px = np.flipud(px)
    ch = px.shape[2]
    from PIL import Image
    arr = (np.clip(px, 0, 1) * 255 + 0.5).astype(np.uint8)
    if ch == 4 and mode != "RGBA" and np.all(arr[..., 3] > 250):
        arr = arr[..., :3]
    pil = Image.fromarray(arr if arr.shape[2] != 1 else arr[..., 0])
    if max(w, h) > max_size:
        k = max_size / max(w, h)
        pil = pil.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.lower().endswith(".jpg"):
        pil.convert("RGB").save(path, quality=92)
    else:
        pil.save(path, optimize=True)
    return path


def _srgb(c):
    def f(x):
        return x * 12.92 if x <= 0.0031308 else 1.055 * (x ** (1 / 2.4)) - 0.055
    return tuple(max(0.0, min(1.0, f(v))) for v in c[:3])


def extract_materials(obj, asset, spec):
    """Rename material slots to MT_<asset>_<n>, export their textures, register palette entries."""
    foliage = [f.lower() for f in spec.get("foliage", [])]
    tex_dir = os.path.join(TEX_OUT, asset)
    max_size = spec.get("max_texture", 1024)
    for i, slot in enumerate(obj.material_slots):
        mat = slot.material
        if mat is None:
            continue
        orig = mat.name
        new_name = f"MT_{asset}_{i}"
        is_foliage = any(f in orig.lower() for f in foliage)
        entry = dict(kind="pbr_foliage" if is_foliage else "pbr", color=(1.0, 1.0, 1.0), rough=0.8, metallic=0.0,
                     detail=None, source_material=orig)
        bsdf = None
        if mat.node_tree:
            bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is not None:
            bc = bsdf.inputs["Base Color"]
            img, _ = _image_from(bc)
            if img is not None:
                ext = ".png" if (is_foliage or bsdf.inputs["Alpha"].is_linked) else ".jpg"
                p = _save_image(img, os.path.join(tex_dir, f"T_{asset}_{i}_BC{ext}"), max_size,
                                mode="RGBA" if ext == ".png" else None)
                if p:
                    entry["base"] = f"ThirdParty/{asset}/" + os.path.splitext(os.path.basename(p))[0]
            else:
                entry["color"] = _srgb(bc.default_value)
            if bsdf.inputs["Alpha"].is_linked or is_foliage:
                entry["masked"] = True
            nimg, _ = _image_from(bsdf.inputs["Normal"])
            if nimg is not None:
                p = _save_image(nimg, os.path.join(tex_dir, f"T_{asset}_{i}_N.png"), max_size)
                if p:
                    entry["normal"] = f"ThirdParty/{asset}/T_{asset}_{i}_N"
            rimg, rch = _image_from(bsdf.inputs["Roughness"])
            if rimg is not None:
                p = _save_image(rimg, os.path.join(tex_dir, f"T_{asset}_{i}_ORM.png"), max_size)
                if p:
                    entry["orm"] = f"ThirdParty/{asset}/T_{asset}_{i}_ORM"
                    # glTF metallicRoughness: roughness in G, metallic in B (via a Separate Color node)
                    entry["rough_channel"] = rch.split(":")[1][:1].upper() if rch and rch.startswith("channel:") else "R"
            else:
                entry["rough"] = float(bsdf.inputs["Roughness"].default_value)
            if not bsdf.inputs["Metallic"].is_linked:
                m = float(bsdf.inputs["Metallic"].default_value)
                metal_words = ("metal", "steel", "iron", "gold", "silver", "chrome", "brass", "copper", "alu")
                # glTF's metallicFactor defaults to 1.0 when unspecified - most low-poly art never meant that
                if not any(w in orig.lower() for w in metal_words):
                    m = 0.0 if m > 0.5 else m * 0.25
                entry["metallic"] = m
        entry.update(spec.get("material_overrides", {}).get(orig, {}))
        mat.name = new_name
        palette.register({new_name: entry})


# --------------------------------------------------------------------------- collision
def collision_meshes(obj, spec):
    """Returns a list of bpy objects named UCX_* (caller renames) approximating the asset."""
    kind = spec.get("collision", "hull")
    if kind == "none":
        return []
    me = obj.data
    co = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    mn, mx = co.min(0), co.max(0)
    bm = bmesh.new()
    if kind == "trunk":
        r = spec.get("trunk_radius", 0.3)
        h = spec.get("trunk_height", (mx[2] - mn[2]) * 0.55)
        bmesh.ops.create_cone(bm, cap_ends=True, segments=8, radius1=r, radius2=r * 0.8, depth=h,
                              matrix=Matrix.Translation((0, 0, h / 2)))
    elif kind == "box":
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = Vector(((mn[0] + mx[0]) / 2 + v.co.x * (mx[0] - mn[0]),
                           (mn[1] + mx[1]) / 2 + v.co.y * (mx[1] - mn[1]),
                           (mn[2] + mx[2]) / 2 + v.co.z * (mx[2] - mn[2])))
    else:  # convex hull of a vertex subsample
        pts = co if len(co) < 4000 else co[np.random.default_rng(0).choice(len(co), 4000, replace=False)]
        verts = [bm.verts.new(Vector(p)) for p in pts]
        res = bmesh.ops.convex_hull(bm, input=verts)
        for v in res.get("geom_interior", []) + res.get("geom_unused", []):
            if isinstance(v, bmesh.types.BMVert) and v.is_valid:
                bm.verts.remove(v)
        bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(8), verts=bm.verts[:], edges=bm.edges[:])
    cme = bpy.data.meshes.new("col")
    bm.to_mesh(cme)
    bm.free()
    co_obj = bpy.data.objects.new("col", cme)
    bpy.context.scene.collection.objects.link(co_obj)
    return [co_obj]


# --------------------------------------------------------------------------- public API
_built = {}


def build_prop(name):
    """Import + normalise the third-party asset mapped to catalog `name`. Returns the bpy object."""
    cached = _built.get(name)
    if cached is not None:
        try:
            if cached.name in bpy.data.objects:
                return cached
        except ReferenceError:   # object was deleted (e.g. after an export)
            pass
    spec = registry()["props"][name]
    path = os.path.join(TP_DIR, spec["file"])
    objs = import_file(path)
    asset = name.replace("SM_", "")
    obj = _join_static(objs, name, spec.get("exclude", ()))
    for m in list(obj.modifiers):
        obj.modifiers.remove(m)
    _normalise(obj, spec)
    extract_materials(obj, asset, spec)
    _built[name] = obj
    return obj


def credits():
    """[(catalog name, credit line)] for CREDITS.md."""
    out = []
    for name, spec in registry()["props"].items():
        src = os.path.join(TP_DIR, os.path.dirname(spec["file"]), "SOURCE.txt")
        out.append((name, spec.get("credit", ""), src if os.path.exists(src) else None))
    return out
