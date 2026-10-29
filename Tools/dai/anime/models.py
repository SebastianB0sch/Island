"""
Existing anime models -> Duel Academy cast members.

Takes a rigged humanoid anime model (VRM 0.x / 1.0 such as the VRoid sample avatars, or any glTF /
FBX humanoid) registered in Tools/thirdparty/registry/anime.json ("anime_models") and turns it into
an Unreal-ready skeletal mesh:

  * VRM 0.x models face +Z in glTF (+Y in Blender) - turned round to face -Y like everything else
  * the humanoid bones (VRM humanoid map, or common Mixamo / VRoid names) are renamed to the UE5
    Mannequin scheme (pelvis, spine_01.., upperarm_l, ..), so the same CC0 takes drive every model
    and Unreal's IK Retargeter auto-maps it; hair / skirt / finger helper bones keep their names
  * the base outfit is replaced by a tailored Duel Academy uniform (outfit.py) and the hair restyled
    (hairdo.py) after each character's official design; hair, eye and shoe textures are recoloured;
    generic students get a neutral jacket / hair that Unreal tints at runtime ("JacketTint" /
    "HairTint" slots)
  * an inverted-hull ink outline is added to the body and hair
  * the retargeted / authored takes are baked onto the model's own skeleton (its proportions)
"""

import json
import math
import os
import re
import struct

import bpy
import numpy as np
from mathutils import Matrix
from PIL import Image

from .. import config as C
from .. import palette, thirdparty
from . import skin as K

TEX_REL = "Characters"

# VRM humanoid bone -> UE5 Mannequin bone
HUMAN_TO_UE = {
    "hips": "pelvis", "spine": "spine_01", "chest": "spine_02", "upperChest": "spine_03", "neck": "neck_01",
    "head": "head",
}
for _s, _side in (("left", "l"), ("right", "r")):
    HUMAN_TO_UE.update({
        f"{_s}Shoulder": f"clavicle_{_side}", f"{_s}UpperArm": f"upperarm_{_side}",
        f"{_s}LowerArm": f"lowerarm_{_side}", f"{_s}Hand": f"hand_{_side}",
        f"{_s}UpperLeg": f"thigh_{_side}", f"{_s}LowerLeg": f"calf_{_side}", f"{_s}Foot": f"foot_{_side}",
        f"{_s}Toes": f"ball_{_side}",
    })
    for finger, ue in (("Thumb", "thumb"), ("Index", "index"), ("Middle", "middle"), ("Ring", "ring"),
                       ("Little", "pinky")):
        # VRM 1.0: Metacarpal/Proximal/Distal for the thumb, Proximal/Intermediate/Distal otherwise;
        # VRM 0.x: Proximal/Intermediate/Distal for every finger
        segs = ("Metacarpal", "Proximal", "Distal") if finger == "Thumb" else ("Proximal", "Intermediate", "Distal")
        for i, seg in enumerate(segs):
            HUMAN_TO_UE[f"{_s}{finger}{seg}"] = f"{ue}_0{i + 1}_{_side}"
        if finger == "Thumb":
            HUMAN_TO_UE.setdefault(f"{_s}ThumbIntermediate", f"thumb_02_{_side}")

# material role from VRoid-style material names (…_Tops_01_CLOTH, …_HAIR, …_EyeIris_00_EYE, …)
ROLES = (("tops", ("tops",)), ("bottoms", ("bottoms",)), ("shoes", ("shoes",)), ("iris", ("eyeiris",)),
         ("hair", ("_hair", "hair_")), ("skin", ("_skin",)))


def role_of(mat_name):
    n = mat_name.lower()
    for role, keys in ROLES:
        if any(k in n for k in keys):
            return role
    return "other"


# --------------------------------------------------------------------------- VRM json
def _gltf_json(path):
    with open(path, "rb") as fp:
        head = fp.read(20)
        if head[:4] != b"glTF":
            return None
        n = struct.unpack_from("<I", head, 12)[0]
        return json.loads(fp.read(n))


def alpha_modes(path):
    """{material name: OPAQUE | MASK | BLEND} from a .vrm/.glb file ({} for other formats). VRM 0.x keeps the
    MToon render mode (_BlendMode: 0 opaque, 1 cutout, 2/3 transparent) in its own extension."""
    j = _gltf_json(path) or {}
    out = {m.get("name"): m.get("alphaMode", "OPAQUE") for m in j.get("materials", [])}
    for mp in j.get("extensions", {}).get("VRM", {}).get("materialProperties", []):
        mode = mp.get("floatProperties", {}).get("_BlendMode", 0)
        if mode >= 1 and mp.get("name") in out:
            out[mp["name"]] = "MASK" if mode == 1 else "BLEND"
    return out


def read_vrm(path):
    """(version 0 | 1 | None, {humanBone: node name}) from a .vrm/.glb file."""
    j = _gltf_json(path)
    if j is None:
        return None, {}
    names = [nd.get("name") for nd in j.get("nodes", [])]
    ext = j.get("extensions", {})
    if "VRMC_vrm" in ext:
        hb = ext["VRMC_vrm"]["humanoid"]["humanBones"]
        return 1, {k: names[v["node"]] for k, v in hb.items()}
    if "VRM" in ext:
        return 0, {h["bone"]: names[h["node"]] for h in ext["VRM"]["humanoid"]["humanBones"] if "node" in h}
    return None, {}


# common non-VRM rigs (Mixamo, VRoid FBX exports) when the file carries no humanoid map
NAME_HINTS = {
    "hips": ("mixamorig:Hips", "J_Bip_C_Hips", "Hips"), "spine": ("mixamorig:Spine", "J_Bip_C_Spine", "Spine"),
    "chest": ("mixamorig:Spine1", "J_Bip_C_Chest", "Chest"), "upperChest": ("mixamorig:Spine2", "J_Bip_C_UpperChest"),
    "neck": ("mixamorig:Neck", "J_Bip_C_Neck", "Neck"), "head": ("mixamorig:Head", "J_Bip_C_Head", "Head"),
}
for _s, _m, _v in (("left", "Left", "L"), ("right", "Right", "R")):
    for hb, mx, vr in (("Shoulder", "Shoulder", "Shoulder"), ("UpperArm", "Arm", "UpperArm"), ("LowerArm", "ForeArm", "LowerArm"),
                       ("Hand", "Hand", "Hand"), ("UpperLeg", "UpLeg", "UpperLeg"), ("LowerLeg", "Leg", "LowerLeg"),
                       ("Foot", "Foot", "Foot"), ("Toes", "ToeBase", "ToeBase")):
        NAME_HINTS[f"{_s}{hb}"] = (f"mixamorig:{_m}{mx}", f"J_Bip_{_v}_{vr}")


# --------------------------------------------------------------------------- import + normalise
def _select(objs, active):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def load(path, log=print):
    """Import a base model. Returns (armature 'root', [meshes]) - T-pose, metres, facing -Y, UE bone names."""
    version, human = read_vrm(path)
    src = path
    if path.lower().endswith(".vrm"):
        cache = os.path.join(C.CACHE_DIR, "vrm")
        os.makedirs(cache, exist_ok=True)
        src = os.path.join(cache, os.path.splitext(os.path.basename(path))[0] + ".glb")
        if not os.path.exists(src) or os.path.getmtime(src) < os.path.getmtime(path):
            with open(path, "rb") as a, open(src, "wb") as b:
                b.write(a.read())
    objs = thirdparty.import_file(src)
    if version == 0:                     # VRM 0.x faces +Z in glTF: turn the whole import round
        turn = Matrix.Rotation(math.pi, 4, "Z")
        for o in [o for o in objs if o.parent is None]:
            o.matrix_world = turn @ o.matrix_world
        bpy.context.view_layer.update()
    empties = [o for o in objs if o.type == "EMPTY"]
    arm = next(o for o in objs if o.type == "ARMATURE")
    meshes = [o for o in objs if o.type == "MESH" and len(o.data.polygons)
              and any(m.type == "ARMATURE" for m in o.modifiers)]
    for o in objs:
        if o is not arm and o not in meshes and o.type != "EMPTY":
            bpy.data.objects.remove(o, do_unlink=True)
    if arm.animation_data:
        arm.animation_data_clear()
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    # unparent from the import empties, apply everything
    mw = arm.matrix_world.copy()
    arm.parent = None
    arm.matrix_world = mw
    for o in empties:                                     # only this import's empties
        bpy.data.objects.remove(o, do_unlink=True)
    for m in meshes:
        w = m.matrix_world.copy()
        m.parent = arm
        m.matrix_world = w
        for mod in m.modifiers:
            if mod.type == "ARMATURE":
                mod.object = arm
    bpy.context.view_layer.update()
    _select([arm] + meshes, arm)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

    # humanoid bones -> UE5 Mannequin names
    if not human:
        for hb, cands in NAME_HINTS.items():
            b = next((c for c in cands if c in arm.data.bones), None)
            if b:
                human[hb] = b
    renames = {node: HUMAN_TO_UE[hb] for hb, node in human.items() if hb in HUMAN_TO_UE and node in arm.data.bones}
    taken = {b.name.lower() for b in arm.data.bones} - {n.lower() for n in renames}
    for old, new in renames.items():
        if new.lower() in taken:          # a helper bone already uses the UE name: move it aside
            arm.data.bones[next(b.name for b in arm.data.bones if b.name.lower() == new.lower())].name = new + "_src"
        arm.data.bones[old].name = new
        for m in meshes:
            vg = m.vertex_groups.get(old)
            if vg is not None:
                vg.name = new
    missing = [n for n in ("pelvis", "spine_01", "head", "upperarm_l", "lowerarm_l", "thigh_l", "calf_l", "foot_l")
               if n not in arm.data.bones]
    if missing:
        raise RuntimeError(f"{path}: no humanoid bones for {missing}")
    # the armature object becomes Unreal's root bone: drop parentless helper bones above the pelvis
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    p = eb["pelvis"].parent
    while p is not None:
        nxt = p.parent
        if p.name.lower() in ("root", "armature", "skeleton") or not any(
                m.vertex_groups.get(p.name) for m in meshes):
            for c in p.children:
                c.parent = nxt
            eb.remove(p)
        p = nxt
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.name = arm.data.name = "root"
    for m in meshes:
        if m.data.shape_keys:
            m.shape_key_clear()
    return arm, meshes


# --------------------------------------------------------------------------- textures
def _recolor(src_png, dst_png, target, keep=0.0, gradient=None, contrast=1.0):
    """Recolour a texture to `target` (sRGB) keeping its light / dark detail (luminance normalised to the
    dominant tone). keep blends some of the original colour back in. gradient = (colour, v, soft): below
    texture v (VRoid hair strands run from v=1 at the root to v=0 at the tip) blend into a second colour."""
    img = Image.open(src_png).convert("RGBA")
    a = np.asarray(img).astype(np.float32) / 255.0
    rgb, al = a[..., :3], a[..., 3]
    lum = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    mask = al > 0.5
    ref = np.percentile(lum[mask], 65) if mask.any() else 0.5
    k = np.clip(lum / max(ref, 0.03), 0.0, 1.3)
    k = (1.0 + (k - 1.0) * contrast)[..., None]          # contrast < 1: flatter (anime hair is near flat)
    out = k * np.array(target, np.float32)
    if gradient:
        col2, v0, soft = gradient
        h = out.shape[0]
        v = 1.0 - (np.arange(h, dtype=np.float32) + 0.5) / h
        t = np.clip((v0 + soft * 0.5 - v) / max(soft, 1e-3), 0, 1)
        t = (t * t * (3 - 2 * t))[:, None, None]
        out = out * (1 - t) + k * np.array(col2, np.float32) * t
    if keep:
        out = out * (1 - keep) + rgb * keep
    a[..., :3] = np.clip(out, 0, 1)
    os.makedirs(os.path.dirname(dst_png), exist_ok=True)
    Image.fromarray((a * 255 + 0.5).astype(np.uint8)).save(dst_png, optimize=True)


def _base_image(mat, alpha_mode=None):
    """(base colour image, alpha-masked?) - Principled materials, or the unlit (KHR_materials_unlit) node
    trees VRM 0.x models import as."""
    if not mat.node_tree:
        return None, False
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is not None:
        img, _ = thirdparty._image_from(bsdf.inputs["Base Color"])
        masked = bsdf.inputs["Alpha"].is_linked
    else:
        tex = next((n for n in mat.node_tree.nodes if n.type == "TEX_IMAGE" and n.image is not None), None)
        img = tex.image if tex else None
        masked = False
    if alpha_mode is not None:
        masked = alpha_mode in ("MASK", "BLEND")
    return img, masked


def materials(key, base, entry, meshes, alpha=None, log=print, skip=(), rig=None):
    """Recolour / extract every material of the base model and rename the slots to palette materials
    (skip: names of materials that are already palette materials, e.g. the tailored uniform)."""
    tint = set(entry.get("tint", []))
    col = entry.get("colors", {})
    hair = entry.get("hair", {})
    recolor = {
        "tops": None if "jacket" in tint else col.get("jacket"),
        "bottoms": col.get("skirt") if entry.get("body", {}).get("female") else col.get("pants"),
        "shoes": col.get("boots") or col.get("shoes"),
        "hair": None if "hair" in tint else hair.get("color"),
        "iris": entry.get("face", {}).get("eyes", {}).get("iris"),
    }
    neutral = {"tops": "jacket" in tint, "hair": "hair" in tint}
    done = {}
    for obj in meshes:
        for slot_idx, slot in enumerate(obj.material_slots):
            mat = slot.material
            if mat is None or mat.name in skip:
                continue
            if mat.name in done:
                slot.material = done[mat.name]
                continue
            role = role_of(mat.name)
            safe = thirdparty._safe(mat.name)
            # a model imported twice gets "<name>.001" materials: look the alpha mode up by the file's name
            src_name = re.sub(r"\.\d+$", "", re.sub(r"_Top$", "", mat.name))
            img, masked = _base_image(mat, (alpha or {}).get(src_name))
            base_png = None
            if img is not None:
                base_png = thirdparty._save_image(img, os.path.join(C.CACHE_DIR, "vrm_tex", base, f"{safe}.png"),
                                                  2048, mode="RGBA")
            if base_png and rig is not None and role == "skin" and "body" in mat.name.lower():
                from .outfit import fix_skin
                base_png = fix_skin(obj, slot_idx, base_png, base_png[:-4] + "_bare.png", rig,
                                    legs=bool(entry.get("body", {}).get("female")))
            target = recolor.get(role)
            if neutral.get(role):
                target = (0.94, 0.94, 0.94)
            elif role == "hair" and mat.name.endswith("_Top") and hair.get("color2"):
                target = hair["color2"]                  # hairdo.top_layer
            if base_png and target is not None:
                rel = f"{TEX_REL}/{key}/T_{key}_{safe}"
                grad = None
                g = (entry.get("hairdo") or {}).get("gradient")
                if role == "hair" and g and hair.get("color2") and not neutral["hair"]:
                    grad = (hair["color2"], g[0], g[1])
                _recolor(base_png, os.path.join(C.OUT_TEXTURES, rel + ".png"), target, gradient=grad,
                         contrast=0.55 if role == "hair" else 1.0)
                # "JacketTint" / "HairTint" in the slot name: Unreal recolours these per dorm / NPC
                suffix = {"tops": "_JacketTint" if neutral["tops"] else "",
                          "hair": "_HairTint" if neutral["hair"] else ""}.get(role, "")
                name = f"M_Anime_{key}_{safe}{suffix}"
            elif base_png:
                rel = f"{TEX_REL}/{base}/T_{base}_{safe}"
                dst = os.path.join(C.OUT_TEXTURES, rel + ".png")
                if not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    Image.open(base_png).save(dst, optimize=True)
                name = f"M_Anime_{base}_{safe}"
            else:
                rel = None
                name = f"M_Anime_{base}_{safe}"
            spec = dict(kind="toon", color=(1.0, 1.0, 1.0), rough=0.85,
                        fill=0.45, source_material=re.sub(r"\.\d+$", "", mat.name))
            if rel:
                spec["base"] = rel
            if masked:
                spec["masked"] = True
            palette.register({name: spec})
            from .build import preview_material   # Cycles preview version of the palette entry
            new = preview_material(name)
            done[mat.name] = new
            slot.material = new
    return done


# --------------------------------------------------------------------------- outline
def _alpha_lookup(obj):
    """face -> visible? for cut-out materials: texture alpha at the face's UV centre (hidden outfit parts of
    VRoid models are transparent texels, and must not get an outline)."""
    tex = {}
    for i, slot in enumerate(obj.material_slots):
        spec = palette.MATERIALS.get(slot.material.name if slot.material else "", {})
        if spec.get("masked") and spec.get("base"):
            path = os.path.join(C.OUT_TEXTURES, spec["base"] + ".png")
            if os.path.exists(path):
                tex[i] = np.asarray(Image.open(path).convert("RGBA"))[..., 3]
    return tex


def add_outline(obj, thickness, skip=("face",)):
    """Inverted hull for one mesh object (in place): inflated, flipped copy with the outline material."""
    import bmesh
    if any(s in obj.name.lower() for s in skip):
        return
    me = obj.data
    alpha = _alpha_lookup(obj)
    bm = bmesh.new()
    bm.from_mesh(me)
    uv = bm.loops.layers.uv.active
    hidden = []
    for f in bm.faces:
        a = alpha.get(f.material_index)
        if a is None or uv is None:
            continue
        u = sum(l[uv].uv.x for l in f.loops) / len(f.loops)
        v = sum(l[uv].uv.y for l in f.loops) / len(f.loops)
        h, w = a.shape
        if a[min(h - 1, max(0, int((1 - v % 1.0) * h))), min(w - 1, max(0, int((u % 1.0) * w)))] < 128:
            hidden.append(f)
    orig = [f for f in bm.faces if f not in set(hidden)]
    if not orig:
        bm.free()
        return
    geom = bmesh.ops.duplicate(bm, geom=orig)
    new_verts = [g for g in geom["geom"] if isinstance(g, bmesh.types.BMVert)]
    new_faces = [g for g in geom["geom"] if isinstance(g, bmesh.types.BMFace)]
    co = np.array([v.co[:] for v in new_verts])
    key = np.round(co / 1e-4).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    nrm = np.array([v.normal[:] for v in new_verts])
    acc = np.zeros((inv.max() + 1, 3))
    np.add.at(acc, inv, nrm)
    n = acc[inv]
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    for v, d in zip(new_verts, n):
        v.co += type(v.co)(d * thickness)
    bmesh.ops.reverse_faces(bm, faces=new_faces)
    mat = bpy.data.materials.get(K.OUTLINE_MAT)
    if mat.name not in me.materials:
        me.materials.append(mat)
    idx = list(me.materials).index(mat)
    for f in new_faces:
        f.material_index = idx
        f.smooth = True
    bm.to_mesh(me)
    bm.free()


# --------------------------------------------------------------------------- build one cast member
def build_model(cid, entry, key_name, log=print):
    """Import the registered base model of a cast entry and dress it. Returns (armature, mesh)."""
    from .build import preview_material, OUTLINE_COLOR
    base = entry["model"]
    spec = thirdparty.registry()["anime_models"][base]
    path = thirdparty.tp_path(spec["file"])
    arm, meshes = load(path, log)
    key = key_name(cid)
    palette.register({K.OUTLINE_MAT: dict(kind="outline", color=OUTLINE_COLOR)})
    preview_material(K.OUTLINE_MAT)
    from . import hairdo, outfit
    tailored = set()
    body = next((m for m in meshes if any(role_of(s.material.name) == "skin" and "body" in s.material.name.lower()
                                          for s in m.material_slots if s.material)), None)
    rig = None
    if body is not None:
        skin = {i for i, s in enumerate(body.material_slots) if s.material and role_of(s.material.name) == "skin"}
        rig = outfit.Rig(arm, body, skin)
        if entry.get("outfit"):
            t = outfit.tailor(arm, body, entry, key, log)
            tailored = {g["mat"] for g in t.garments.values()}
            _drop_unused_slots(body)
    alpha = alpha_modes(path)
    extra = []
    if rig is not None and (entry.get("hairdo")):
        more, extra = hairdo.restyle(arm, meshes, entry, key, rig, log)
        alpha.update(more)
        tailored |= {s.material.name for o in extra for s in o.material_slots if s.material}
    materials(key, key_name(base), entry, meshes, alpha, log, skip=tailored, rig=rig)
    meshes += extra
    for m in meshes:
        add_outline(m, entry.get("outline", 0.0022), skip=("face", "glasses"))
    _select(meshes, meshes[0])
    if len(meshes) > 1:
        bpy.ops.object.join()
    mesh = meshes[0]
    mesh.name = mesh.data.name = f"SK_Anime_{key}"
    return arm, mesh


def _drop_unused_slots(obj):
    _select([obj], obj)
    bpy.ops.object.material_slot_remove_unused()


def model_available(entry):
    base = entry.get("model")
    spec = thirdparty.registry().get("anime_models", {}).get(base) if base else None
    return bool(spec) and os.path.exists(thirdparty.tp_path(spec["file"]))
