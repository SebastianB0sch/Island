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

import math
import os
import re

import bpy
import numpy as np
from mathutils import Matrix
from PIL import Image

from .. import atomic, cache
from .. import config as C
from .. import palette, thirdparty
from . import skin as K
from .vrm import alpha_modes, read_vrm, target_names

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
         ("mouth", ("facemouth",)),
         ("hair", ("_hair", "hair_")), ("skin", ("_skin",)))


def role_of(mat_name):
    n = mat_name.lower()
    for role, keys in ROLES:
        if any(k in n for k in keys):
            return role
    return "other"


# --------------------------------------------------------------------------- VRM json
# _gltf_json / alpha_modes / read_vrm / target_names live in dai.anime.vrm
# (stdlib-only so they can be unit-tested without Blender) and are imported above.

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


def _bake_expression(obj, names, expression):
    """Mix VRoid blendshapes into the face's rest shape: {"BRW_Angry": 0.6, "EYE_Angry": 0.3, ...} (names after
    "Fcl_", case-insensitive) - a character's resting expression (Chazz's scowl, Crowler's grin)."""
    kb = obj.data.shape_keys.key_blocks
    n = len(obj.data.vertices)
    base = np.empty(n * 3)
    kb[0].data.foreach_get("co", base)
    co = base.copy()
    for key, w in expression.items():
        i = next((i for i, nm in enumerate(names) if nm.lower().endswith("fcl_" + key.lower())), None)
        if i is None or i + 1 >= len(kb):
            continue
        tgt = np.empty(n * 3)
        kb[i + 1].data.foreach_get("co", tgt)
        co += (tgt - base) * w
    return co


def load(path, log=print, expression=None):
    """Import a base model. Returns (armature 'root', [meshes]) - T-pose, metres, facing -Y, UE bone names.
    expression: blendshape mix baked into the face (see _bake_expression)."""
    cache.require_file(path, "anime model")
    version, human = read_vrm(path)
    src = path
    if path.lower().endswith(".vrm"):
        if not cache.is_glb(path):
            raise RuntimeError(f"{path}: not a valid VRM/GLB file")
        cache_dir = os.path.join(C.CACHE_DIR, "vrm")
        os.makedirs(cache_dir, exist_ok=True)
        src = cache.cache_file(cache_dir, path, ".glb")
        # Validate the cache: an interrupted copy used to leave a truncated .glb
        # that still looked newer than the source and was reused forever.
        if not cache.is_fresh(src, path) or not cache.is_glb(src):
            atomic.copy_file(path, src)
    objs = thirdparty.import_file(src)
    if version == 0:                     # VRM 0.x faces +Z in glTF: turn the whole import round
        turn = Matrix.Rotation(math.pi, 4, "Z")
        for o in [o for o in objs if o.parent is None]:
            o.matrix_world = turn @ o.matrix_world
        bpy.context.view_layer.update()
    empties = [o for o in objs if o.type == "EMPTY"]
    arm = next((o for o in objs if o.type == "ARMATURE"), None)
    if arm is None:
        raise RuntimeError(f"{path}: no armature in the imported model")
    meshes = [o for o in objs if o.type == "MESH" and len(o.data.polygons)
              and any(m.type == "ARMATURE" for m in o.modifiers)]
    if not meshes:
        raise RuntimeError(f"{path}: no skinned meshes in the imported model")
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
    names = target_names(path)
    for m in meshes:
        if m.data.shape_keys:
            co = None
            src = names.get(m.name.split(".")[0]) or [k.name for k in m.data.shape_keys.key_blocks[1:]]
            if expression and src:
                co = _bake_expression(m, src, expression)
            deltas = _morph_deltas(m, src) if src else {}
            m.shape_key_clear()
            if co is not None:
                m.data.vertices.foreach_set("co", co)
                m.data.update()
            # the facial rig survives the restyle as point attributes (carried through joins / edits) and
            # becomes morph targets again in build_model (restore_morphs)
            for morph, d in deltas.items():
                attr = m.data.attributes.new(MORPH_ATTR + morph, "FLOAT_VECTOR", "POINT")
                attr.data.foreach_set("vector", d.astype(np.float32))
    return arm, meshes


# --------------------------------------------------------------------------- facial rig
# morph target (Unreal) -> VRoid blendshape (after "Fcl_"): blinking, the five visemes and the emotions.
# Exported relative to the character's own resting expression, so a blink on Chazz's scowl stays a scowl.
FACE_MORPHS = {
    "Blink": "EYE_Close", "Blink_L": "EYE_Close_L", "Blink_R": "EYE_Close_R",
    "A": "MTH_A", "I": "MTH_I", "U": "MTH_U", "E": "MTH_E", "O": "MTH_O",
    "Joy": "ALL_Joy", "Angry": "ALL_Angry", "Sorrow": "ALL_Sorrow", "Surprised": "ALL_Surprised",
    "Fun": "ALL_Fun", "EyeJoy": "EYE_Joy", "BrowAngry": "BRW_Angry", "BrowSorrow": "BRW_Sorrow",
}
MORPH_ATTR = "da_morph_"


# The same morphs under the names other pipelines export (VRM 1.0 expressions, ARKit, common MMD / Unity
# names), so an artist-made model keeps its facial rig. Matched case-insensitively against the end of the
# blendshape name; the VRoid "Fcl_" name above is tried first.
MORPH_ALIASES = {
    "Blink": ("blink", "eyeblink", "eyesclosed", "eye_close", "mabataki"),
    "Blink_L": ("blinkleft", "blink_l", "eyeblinkleft", "eyeblink_l", "wink_l", "winkleft"),
    "Blink_R": ("blinkright", "blink_r", "eyeblinkright", "eyeblink_r", "wink_r", "winkright"),
    "A": ("aa", "vrc.v_aa", "mouth_a", "v_aa", "_a"), "I": ("ih", "vrc.v_ih", "mouth_i", "v_ih", "_i"),
    "U": ("ou", "vrc.v_ou", "mouth_u", "v_ou", "_u"), "E": ("ee", "vrc.v_e", "mouth_e", "v_e", "_e"),
    "O": ("oh", "vrc.v_oh", "mouth_o", "v_oh", "_o"),
    "Joy": ("happy", "joy", "smile"), "Angry": ("angry", "anger"), "Sorrow": ("sad", "sorrow"),
    "Surprised": ("surprised", "surprise"), "Fun": ("relaxed", "fun"),
    "EyeJoy": ("eye_joy", "eyesmile", "eye_smile", "eyejoy"),
    "BrowAngry": ("brow_angry", "browangry", "browdown"), "BrowSorrow": ("brow_sorrow", "browsorrow", "browinnerup"),
}


def _morph_index(names, morph):
    """Index into `names` of the blendshape that plays `morph` (None if the model has none)."""
    low = [n.lower() for n in names]
    key = "fcl_" + FACE_MORPHS[morph].lower()
    for i, n in enumerate(low):
        if n.endswith(key):
            return i
    for alias in MORPH_ALIASES.get(morph, ()):
        for i, n in enumerate(low):
            if n == alias or n.endswith("." + alias) or n.endswith("_" + alias.lstrip("_")) and len(alias) > 2:
                return i
    for i, n in enumerate(low):                      # a shape key simply named after the morph
        if n == morph.lower():
            return i
    return None


def _morph_deltas(obj, names):
    """{morph: (n*3,) offset from the base model's basis} for the FACE_MORPHS this mesh has."""
    kb = obj.data.shape_keys.key_blocks
    n = len(obj.data.vertices)
    base = np.empty(n * 3)
    kb[0].data.foreach_get("co", base)
    out = {}
    for morph in FACE_MORPHS:
        i = _morph_index(names, morph)
        if i is None or i + 1 >= len(kb):
            continue
        tgt = np.empty(n * 3)
        kb[i + 1].data.foreach_get("co", tgt)
        d = tgt - base
        if np.abs(d).max() > 1e-6:
            out[morph] = d
    return out


def restore_morphs(obj, log=print):
    """Turn the da_morph_* point attributes back into shape keys (Unreal morph targets) on the final mesh."""
    me = obj.data
    attrs = [a.name for a in me.attributes if a.name.startswith(MORPH_ATTR)]
    if not attrs:
        return 0
    n = len(me.vertices)
    base = np.empty(n * 3, np.float32)
    me.vertices.foreach_get("co", base)
    obj.shape_key_add(name="Basis", from_mix=False)
    for name in attrs:
        d = np.empty(n * 3, np.float32)
        me.attributes[name].data.foreach_get("vector", d)
        key = obj.shape_key_add(name=name[len(MORPH_ATTR):], from_mix=False)
        key.data.foreach_set("co", base + d)
        key.value = 0.0                 # rest face; Unreal drives the weights at runtime
    for name in attrs:
        me.attributes.remove(me.attributes[name])
    log(f"  anime: {obj.name}: {len(attrs)} face morph targets")
    return len(attrs)


# --------------------------------------------------------------------------- textures
def _recolor(src_png, dst_png, target, keep=0.0, gradient=None, contrast=1.0):
    """Recolour a texture to `target` (sRGB) keeping its light / dark detail (luminance normalised to the
    dominant tone). keep blends some of the original colour back in. gradient = (colour, v, soft): below
    texture v (VRoid hair strands run from v=1 at the root to v=0 at the tip) blend into a second colour."""
    with Image.open(src_png) as src_img:
        img = src_img.convert("RGBA")
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
    atomic.save_image(Image.fromarray((a * 255 + 0.5).astype(np.uint8)), dst_png, optimize=True)


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


def materials(key, base, entry, meshes, alpha=None, log=print, skip=(), rig=None, source=None):
    """Recolour / extract every material of the base model and rename the slots to palette materials
    (skip: names of materials that are already palette materials, e.g. the tailored uniform)."""
    tint = set(entry.get("tint", []))
    col = entry.get("colors", {})
    hair = entry.get("hair", {})
    # The vrm_tex cache entries are keyed by source path (like the decoded glTF
    # cache) so two packs with the same model name cannot collide.
    tex_cache_key = f"{base}-{cache.source_key(source)}" if source else base
    recolor = {
        "tops": None if "jacket" in tint else col.get("jacket"),
        "bottoms": col.get("skirt") if entry.get("body", {}).get("female") else col.get("pants"),
        "shoes": col.get("boots") or col.get("shoes"),
        "hair": None if "hair" in tint else hair.get("color"),
        "iris": entry.get("face", {}).get("eyes", {}).get("iris"),
        "mouth": col.get("lips"),                       # lipstick (Crowler)
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
                # `fresh_against` reuses the cache only while it is not older than
                # the registered model file (see thirdparty._save_image).
                base_png = thirdparty._save_image(img, os.path.join(C.CACHE_DIR, "vrm_tex", tex_cache_key, f"{safe}.png"),
                                                  2048, mode="RGBA", fresh_against=source)
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
                         contrast=0.55 if role == "hair" else 1.0, keep=0.35 if role == "mouth" else 0.0)
                # "JacketTint" / "HairTint" in the slot name: Unreal recolours these per dorm / NPC
                suffix = {"tops": "_JacketTint" if neutral["tops"] else "",
                          "hair": "_HairTint" if neutral["hair"] else ""}.get(role, "")
                name = f"M_Anime_{key}_{safe}{suffix}"
            elif base_png:
                rel = f"{TEX_REL}/{base}/T_{base}_{safe}"
                dst = os.path.join(C.OUT_TEXTURES, rel + ".png")
                # Always refresh the output copy: the cache may predate a texture
                # or material change, and the previous code kept stale files forever.
                with Image.open(base_png) as cached:
                    atomic.save_image(cached, dst, optimize=True)
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
                with Image.open(path) as img:
                    tex[i] = np.asarray(img.convert("RGBA"))[..., 3]
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
    hidden_set = set(hidden)
    orig = [f for f in bm.faces if f not in hidden_set]
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
    if mat is None:
        # build_model() creates this up front; keep the helper usable on its own.
        from .build import preview_material
        mat = preview_material(K.OUTLINE_MAT)
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
    arm, meshes = load(path, log, entry.get("expression"))
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
    if rig is not None and (entry.get("hairdo") or entry.get("face_shape")):
        more, extra = hairdo.restyle(arm, meshes, entry, key, rig, log)
        alpha.update(more)
        tailored |= {s.material.name for o in extra for s in o.material_slots if s.material}
    materials(key, key_name(base), entry, meshes, alpha, log, skip=tailored, rig=rig, source=path)
    if body is not None and entry.get("outfit"):
        # cloth fit relaxation: loosen the clothes wherever a take would push an inner layer through them
        from . import correctives, fitcheck
        fitcheck.relax(body, arm, log)
        # pose-space correctives for what a static fit cannot hold (big hip swings), driven by the thighs
        correctives.build(body, arm, log)
        # ...and a second static pass with the correctives active clears what their blending leaves
        fitcheck.relax(body, arm, log, iterations=6, shape_fn=lambda a: correctives.displacement(body, a))
        # last few covered vertices that still break through follow the cloth over them exactly
        fitcheck.snap_residuals(body, arm, log, shape_fn=lambda a: correctives.displacement(body, a))
    meshes += extra
    for m in meshes:
        add_outline(m, entry.get("outline", 0.0022), skip=("face", "glasses", "haircap"))
    face = next((m for m in meshes if m.name.startswith("Face")), meshes[0])
    _select(meshes, face)
    if len(meshes) > 1:
        bpy.ops.object.join()
    mesh = face
    mesh.name = mesh.data.name = f"SK_Anime_{key}"
    from . import shading
    shading.face_normals(mesh, arm, log)
    shading.hair_normals(mesh, arm, log)
    restore_morphs(mesh, log)
    if entry.get("outfit"):
        # final check on exactly what is exported: covered vertices still breaking through follow their cloth
        from . import fitcheck
        fitcheck.snap_residuals(mesh, arm, log)
    return arm, mesh


def _drop_unused_slots(obj):
    _select([obj], obj)
    bpy.ops.object.material_slot_remove_unused()


def model_available(entry):
    base = entry.get("model")
    spec = thirdparty.registry().get("anime_models", {}).get(base) if base else None
    return bool(spec) and os.path.exists(thirdparty.tp_path(spec["file"]))
