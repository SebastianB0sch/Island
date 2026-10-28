"""
Skeletal student character from a third-party (CC0 / CC-BY) rigged + animated model.

Registry section "character" (Tools/thirdparty/registry/character.json):

{
  "character": {
    "SK_Student": {
      "file": "quaternius/worker/worker.glb",
      "height": 1.72,                       # metres, rest pose
      "anims": {"Idle": "Idle", "Walk": "Walk", "Run": "Run", "Jump": "Jump", "Wave": "Wave"},
                                            # state -> substring of the source action name
      "exclude": ["Icosphere"],             # mesh object names to drop
      "material_overrides": {"Shirt": {...}}
    }
  }
}

Outputs (SourceAssets/):
  Meshes/Characters/SK_Student.fbx          skinned mesh + armature (rest pose, no animation)
  Meshes/Characters/A_Student_<State>.fbx   armature-only animation takes
  Data/character.json                       read by the Unreal importer (importer.import_character)
  Textures/ThirdParty/Student/...           PBR textures; materials keep their names (MT_Student_Shirt ...)
                                            so UDAAvatarComponent can find the jacket / hair slots
"""

import json
import os

import bpy
import numpy as np

from . import config as C
from . import thirdparty

OUT_REL = "Meshes/Characters"


def spec():
    return thirdparty.registry()["character"].get("SK_Student")


def available():
    s = spec()
    return bool(s) and os.path.exists(thirdparty.tp_path(s["file"]))


def _mesh_bounds(meshes):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in meshes:
        eo = o.evaluated_get(depsgraph)
        me = eo.to_mesh()
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        mw = np.array(o.matrix_world)
        pts.append(co @ mw[:3, :3].T + mw[:3, 3])
        eo.to_mesh_clear()
    pts = np.concatenate(pts)
    return pts.min(0), pts.max(0)


def _select(objs, active):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = active


def _assign(arm, action):
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = action
    if action is not None and hasattr(ad, "action_slot") and ad.action_slot is None and len(action.slots):
        ad.action_slot = action.slots[0]


def _fcurves(action):
    """All F-curves of an action (Blender 4.4+ layered/slotted actions or legacy)."""
    if hasattr(action, "layers") and len(action.layers):
        for layer in action.layers:
            for strip in layer.strips:
                for bag in getattr(strip, "channelbags", []):
                    yield from bag.fcurves
    elif hasattr(action, "fcurves"):
        yield from action.fcurves


def _scale_locations(action, s):
    """Applying an armature's object scale does not touch bone location keys - scale them to match."""
    for fc in _fcurves(action):
        if fc.data_path.endswith(".location"):
            for kp in fc.keyframe_points:
                kp.co[1] *= s
                kp.handle_left[1] *= s
                kp.handle_right[1] *= s


def _export(objs, active, path, types, anim=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _select(objs, active)
    kw = dict(filepath=path, use_selection=True, object_types=types, apply_scale_options="FBX_SCALE_ALL",
              axis_forward="-Z", axis_up="Y", primary_bone_axis="Y", secondary_bone_axis="X",
              use_armature_deform_only=True, add_leaf_bones=False, mesh_smooth_type="FACE",
              use_mesh_modifiers=False, path_mode="STRIP", embed_textures=False, use_tspace=False,
              colors_type="LINEAR")
    if anim is None:
        kw.update(bake_anim=False)
    else:
        kw.update(bake_anim=True, bake_anim_use_all_bones=True, bake_anim_use_nla_strips=False,
                  bake_anim_use_all_actions=False, bake_anim_force_startend_keying=True,
                  bake_anim_simplify_factor=0.0)
    bpy.ops.export_scene.fbx(**kw)


def build(log=print):
    """Import, normalise and export the student. Returns the manifest entries (or [] when not registered)."""
    if not available():
        stale = os.path.join(C.OUT_DATA, "character.json")
        if os.path.exists(stale):
            os.remove(stale)
        log("  character: none registered (procedural avatar only)")
        return None
    s = spec()
    before_actions = set(bpy.data.actions)
    objs = thirdparty.import_file(thirdparty.tp_path(s["file"]))
    arm = next((o for o in objs if o.type == "ARMATURE"), None)
    if arm is None:
        raise RuntimeError("character: no armature in " + s["file"])
    excl = [x.lower() for x in s.get("exclude", [])]
    meshes = [o for o in objs if o.type == "MESH" and len(o.data.polygons) and len(o.data.materials)
              and any(m.type == "ARMATURE" for m in o.modifiers) and not any(x in o.name.lower() for x in excl)]
    for o in objs:
        if o not in meshes and o is not arm and o.type != "EMPTY":
            bpy.data.objects.remove(o, do_unlink=True)
    actions = [a for a in bpy.data.actions if a not in before_actions]

    # ---- rest pose, unparent from import empties, scale to the target height, apply transforms
    _assign(arm, None)
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    mw = arm.matrix_world.copy()
    arm.parent = None
    arm.matrix_world = mw
    for o in [o for o in bpy.context.scene.objects if o.type == "EMPTY" and not o.children]:
        bpy.data.objects.remove(o, do_unlink=True)
    mn, mx = _mesh_bounds(meshes)
    k = s.get("height", 1.72) / max(mx[2] - mn[2], 1e-6)
    obj_scale = arm.matrix_world.to_scale()[0]
    arm.location = (arm.location[0] - (mn[0] + mx[0]) / 2, arm.location[1] - (mn[1] + mx[1]) / 2, arm.location[2] - mn[2])
    arm.scale = [v * k for v in arm.scale]
    arm.location = [v * k for v in arm.location]
    bpy.context.view_layer.update()
    _select([arm] + meshes, arm)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    for a in actions:
        _scale_locations(a, k * obj_scale)

    # ---- one skinned mesh with meaningful material names
    for m in meshes:
        m.parent = arm
        m.matrix_parent_inverse.identity()
    if len(meshes) > 1:
        _select(meshes, meshes[0])
        bpy.ops.object.join()
    mesh = meshes[0]
    mesh.name = mesh.data.name = "SK_Student"
    arm.name = "root"
    spec_m = dict(s)
    spec_m["keep_names"] = True
    spec_m.setdefault("max_texture", 2048)
    thirdparty.extract_materials(mesh, "Student", spec_m)

    out = os.path.join(C.OUT_MESHES, "Characters")
    _export([arm, mesh], arm, os.path.join(out, "SK_Student.fbx"), {"ARMATURE", "MESH"})
    info = dict(mesh=f"{OUT_REL}/SK_Student.fbx", anims={}, height_m=s.get("height", 1.72),
                materials=[sl.material.name for sl in mesh.material_slots if sl.material])
    scene = bpy.context.scene
    for state, key in s.get("anims", {}).items():
        act = next((a for a in actions if key.lower() in a.name.lower()), None)
        if act is None:
            log(f"  !! character: no action matching '{key}' for {state}")
            continue
        _assign(arm, act)
        f0, f1 = (int(round(v)) for v in act.frame_range)
        scene.frame_start, scene.frame_end = f0, max(f1, f0 + 1)
        name = f"A_Student_{state}"
        _export([arm], arm, os.path.join(out, f"{name}.fbx"), {"ARMATURE"}, anim=act)
        info["anims"][state] = f"{OUT_REL}/{name}.fbx"
    _assign(arm, None)
    os.makedirs(C.OUT_DATA, exist_ok=True)
    with open(os.path.join(C.OUT_DATA, "character.json"), "w") as fp:
        json.dump(info, fp, indent=1)
    tris = sum(len(p.vertices) - 2 for p in mesh.data.polygons)
    log(f"  character: SK_Student {tris} tris, {len(arm.data.bones)} bones, anims {sorted(info['anims'])}")
    bpy.data.objects.remove(mesh, do_unlink=True)
    bpy.data.objects.remove(arm, do_unlink=True)
    return info
