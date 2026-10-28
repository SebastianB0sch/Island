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
from mathutils import Matrix

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


def _left_forearm(arm):
    """Name of the left forearm bone (name heuristics, then position: the student faces -Y, so its left is +X)."""
    bones = list(arm.data.bones)
    cands = [b for b in bones if any(k in b.name.lower().replace("_", "").replace(" ", "")
                                     for k in ("lowerarm", "forearm", "elbow"))] or bones
    left = [b for b in cands if b.name.lower().endswith((".l", "_l", "left", " l")) or b.name.lower().startswith(("l_", "left"))]
    pick = left or [b for b in cands if b.head_local.x > 0.05]
    return max(pick or cands, key=lambda b: b.head_local.x).name


def _add_duel_disk(arm, mesh):
    """Skin the duel disk (procedural, Tools/dai/assets/avatar.py) to the left forearm of the rest pose so it
    follows every animation. Its slots are named MT_Student_Duel*; UDAAvatarComponent hides them for students
    without a disk."""
    from . import palette
    from .assets import avatar
    bone = arm.data.bones[_left_forearm(arm)]
    disk = avatar.duel_disk().build("StudentDuelDisk")
    # avatar.py authors the disk for an arm hanging along -Z with its outside at -X; the T-pose left forearm
    # runs along +X (elbow -> wrist) with the back of the hand (outside) up: map +Z -> -X, -X -> +Z, Y -> -Y
    rot = Matrix(((0, 0, -1, 0), (0, -1, 0, 0), (-1, 0, 0, 0), (0, 0, 0, 1)))
    wrist = bone.tail_local - (bone.tail_local - bone.head_local).normalized() * 0.03
    disk.data.transform(Matrix.Translation(wrist) @ rot)
    for slot in disk.material_slots:
        src = slot.material.name.split(".")[0]
        new = "MT_Student_" + {"M_DuelDisk": "DuelDisk", "M_Gold": "DuelGold", "M_DuelFieldGlow": "DuelGlow"}.get(src, "Duel" + src)
        if new not in palette.MATERIALS:
            palette.register({new: dict(palette.MATERIALS[src])})
        mat = slot.material.copy()
        mat.name = new
        slot.material = mat
    vg = disk.vertex_groups.new(name=bone.name)
    vg.add(list(range(len(disk.data.vertices))), 1.0, "REPLACE")
    _select([mesh, disk], mesh)
    bpy.ops.object.join()
    return bone.name


def _ground_speed(arm, action):
    """cm/s a locomotion clip covers at play rate 1 (rig in metres): root motion if the hips travel,
    otherwise the median backwards speed of whichever foot is planted (in-place cycles)."""
    scene = bpy.context.scene
    _assign(arm, action)
    f0, f1 = (int(round(v)) for v in action.frame_range)
    fps = scene.render.fps / scene.render.fps_base
    names = [b.name for b in arm.pose.bones]
    feet = [n for n in names if any(k in n.lower() for k in ("foot", "toe", "ankle"))] or names
    hips = next((n for n in names if any(k in n.lower() for k in ("hip", "pelvis"))), names[0])
    track = {n: [] for n in feet + [hips]}
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        for n in track:
            track[n].append(np.array(arm.matrix_world @ arm.pose.bones[n].head))
    dur = max(f1 - f0, 1) / fps
    hp = np.array(track[hips])
    travel = np.linalg.norm(hp[-1, :2] - hp[0, :2]) / dur
    if travel > 0.2:
        return float(travel * 100.0)
    speeds = []
    for n in feet:
        p = np.array(track[n])
        if len(p) < 3:
            continue
        planted = p[:, 2] < p[:, 2].min() + 0.03
        v = np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1) * fps
        speeds += list(v[planted[:-1] & planted[1:]])
    return float(np.median(speeds) * 100.0) if speeds else None


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
    disk_bone = _add_duel_disk(arm, mesh) if s.get("duel_disk", True) else None

    out = os.path.join(C.OUT_MESHES, "Characters")
    _export([arm, mesh], arm, os.path.join(out, "SK_Student.fbx"), {"ARMATURE", "MESH"})
    info = dict(mesh=f"{OUT_REL}/SK_Student.fbx", anims={}, height_m=s.get("height", 1.72), duel_disk_bone=disk_bone,
                materials=[sl.material.name for sl in mesh.material_slots if sl.material])
    scene = bpy.context.scene
    for state, key in s.get("anims", {}).items():
        act = next((a for a in actions if key.lower() in a.name.lower()), None)
        if act is None:
            log(f"  !! character: no action matching '{key}' for {state}")
            continue
        if state in ("Walk", "Run"):
            speed = _ground_speed(arm, act)
            if speed:
                info.setdefault("ground_speed", {})[state] = round(speed, 1)
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
    log(f"  character: SK_Student {tris} tris, {len(arm.data.bones)} bones, anims {sorted(info['anims'])}, "
        f"ground speed {info.get('ground_speed', {})} cm/s")
    bpy.data.objects.remove(mesh, do_unlink=True)
    bpy.data.objects.remove(arm, do_unlink=True)
    return info
