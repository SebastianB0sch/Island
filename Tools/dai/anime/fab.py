"""Retarget the licensed Fab Anime Character Pack locomotion takes onto the GX cast.

The Fab pack's anime rig is an A-pose UE4-Mannequin skeleton; the GX cast is a T-pose
skeleton whose leg / spine bone tails point up.  A straight local-rotation copy folds
the legs and splays the arms, so every frame is solved from the *segment direction*
(the direction from a joint to its child joint) instead:

  * the target rest segment is rotated onto the source pose segment;
  * the target keeps its own bone lengths and body proportions;
  * the source pelvis travel is scaled by the leg-length ratio so the stride matches;
  * every other helper bone keeps its rest relation to the animated parent.

This runs inside Blender (the same environment as ``build_island.py cast``) and writes
armature-only FBX takes under ``Tools/thirdparty/fab_anime/retargeted``.  That folder is
local-only: the FBXs are derived from licensed Fab content and must never be committed.

    blender --background --factory-startup --python Tools/retarget_fab_anime_blender.py

The FBXs are installed into Unreal by ``Tools/apply_fab_locomotion.py``.
"""

from __future__ import annotations

import json
import os

import bpy
from mathutils import Matrix, Vector

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
ANIM_DIR = os.path.join(REPO, "Tools", "thirdparty", "fab_anime", "anim")
OUT_DIR = os.path.join(REPO, "Tools", "thirdparty", "fab_anime", "retargeted")
CAST_FBX_DIR = os.path.join(REPO, "DuelAcademyIsland", "SourceAssets", "Meshes", "Characters", "Anime")
CAST_JSON = os.path.join(REPO, "DuelAcademyIsland", "SourceAssets", "Data", "cast.json")


def _cast_info():
    with open(CAST_JSON, "r", encoding="utf-8") as fp:
        return json.load(fp)

# state -> source FBX stem exported from the Fab pack by export_fab_locomotion()
SOURCES = {
    "Idle": "a_manM_idle",
    "Walk": "a_man_walk_F",
    "Run": "a_man_run_F",
}

# The Fab rig and the GX cast share the UE Mannequin bone names, but the GX cast's
# bone tails do not follow the limb joints.  Define the real limb segment explicitly.
SEG_CHILD = {
    "pelvis": "spine_01",
    "spine_01": "spine_02",
    "spine_02": "spine_03",
    "spine_03": "neck_01",
    "neck_01": "head",
}
for _s in ("l", "r"):
    SEG_CHILD.update({
        f"clavicle_{_s}": f"upperarm_{_s}",
        f"upperarm_{_s}": f"lowerarm_{_s}",
        f"lowerarm_{_s}": f"hand_{_s}",
        f"thigh_{_s}": f"calf_{_s}",
        f"calf_{_s}": f"foot_{_s}",
        f"foot_{_s}": f"ball_{_s}",
    })
    for _f in ("thumb", "index", "middle", "ring", "pinky"):
        SEG_CHILD[f"{_f}_01_{_s}"] = f"{_f}_02_{_s}"
        SEG_CHILD[f"{_f}_02_{_s}"] = f"{_f}_03_{_s}"


def _rot(matrix):
    return matrix.to_quaternion().normalized()


def _segment_dir(mats, bone):
    """Direction from `bone` to its limb child (bone Y for leaves)."""
    child = SEG_CHILD.get(bone)
    if child and child in mats:
        return (mats[child].translation - mats[bone].translation).normalized()
    return (mats[bone].to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()


def _import(path, anim):
    bpy.ops.import_scene.fbx(filepath=path, use_anim=anim)


def _find_armatures():
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    src = next((a for a in armatures
                if a.animation_data and a.animation_data.action
                and "thigh_l" in a.data.bones), None)
    dst = next((a for a in armatures if len(a.data.bones) > 100 and "pelvis" in a.data.bones), None)
    return src, dst


def retarget_take(src_path, base_path, group, state, log=print):
    """Bake one Fab source take onto the cast skeleton and export an armature-only FBX."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.render.fps = 30
    _import(src_path, True)
    _import(base_path, False)
    src, dst = _find_armatures()
    if src is None or dst is None:
        raise RuntimeError("could not find the source / cast armatures")
    action = src.animation_data.action
    if action is None:
        raise RuntimeError("the source FBX has no animation action")

    src_rest = {b.name: (src.matrix_world @ b.matrix_local) for b in src.data.bones}
    dst_rest = {b.name: (dst.matrix_world @ b.matrix_local) for b in dst.data.bones}
    mapped = [b.name for b in src.data.bones
              if b.name in dst.data.bones and b.name != "root"]
    if "pelvis" not in mapped:
        raise RuntimeError("the source rig has no pelvis")
    leg_scale = ((dst_rest["thigh_l"].translation.z - dst_rest["foot_l"].translation.z)
                 / (src_rest["thigh_l"].translation.z - src_rest["foot_l"].translation.z))

    order = []

    def add(bone):
        if bone.name in order:
            return
        if bone.parent:
            add(bone.parent)
        order.append(bone.name)

    for bone in dst.data.bones:
        add(bone)
    order = [name for name in order if name in dst_rest]

    for name in order:
        dst.pose.bones[name].rotation_mode = "QUATERNION"
    dst.animation_data_create()
    baked = bpy.data.actions.new(f"A_Anime_{group}_{state}")
    dst.animation_data.action = baked

    first, last = int(action.frame_range[0]), int(action.frame_range[1])
    for frame in range(first, last + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()
        src_pose = {b.name: (src.matrix_world @ b.matrix) for b in src.pose.bones}
        world = {}
        for name in order:
            bone = dst.data.bones[name]
            parent = bone.parent.name if bone.parent else None
            if name in mapped:
                if (name not in SEG_CHILD and parent is not None
                        and parent in src_pose and parent in src_rest):
                    # Leaf bones (head, hands, finger tips, toes) have no limb child to
                    # define a segment.  Transfer their rotation delta in the parent's
                    # frame instead of comparing local Y axes: the Fab and GX leaf bones
                    # are authored with very different local axes, and the old fallback
                    # turned the head/face backwards and twisted the hands.
                    src_local_rest = _rot(src_rest[parent].inverted() @ src_rest[name])
                    src_local_pose = _rot(src_pose[parent].inverted() @ src_pose[name])
                    delta = (src_local_pose @ src_local_rest.inverted()).normalized()
                    dst_local_rest = _rot(dst_rest[parent].inverted() @ dst_rest[name])
                    q = (_rot(world[parent]) @ delta @ dst_local_rest).normalized()
                else:
                    q = (_segment_dir(dst_rest, name).rotation_difference(
                        _segment_dir(src_pose, name)) @ _rot(dst_rest[name])).normalized()
            elif parent is not None:
                q = (_rot(world[parent]) @ _rot(dst_rest[parent]).inverted()
                     @ _rot(dst_rest[name])).normalized()
            else:
                q = _rot(dst_rest[name])
            if parent is None:
                offset = ((src_pose["pelvis"].translation - src_rest["pelvis"].translation)
                          * leg_scale) if name == "pelvis" else None
                pos = dst_rest[name].translation + offset if offset is not None else dst_rest[name].translation
            else:
                pos = (world[parent] @ dst_rest[parent].inverted() @ dst_rest[name]).translation
            world[name] = Matrix.Translation(pos) @ q.to_matrix().to_4x4()

        for name in order:
            if name == "root":
                continue
            dst.pose.bones[name].matrix = world[name]
            bpy.context.view_layer.update()
        for name in order:
            if name == "root":
                continue
            pose_bone = dst.pose.bones[name]
            pose_bone.keyframe_insert("rotation_quaternion", frame=frame, group=name)
            if name == "pelvis":
                pose_bone.keyframe_insert("location", frame=frame, group=name)

    bpy.context.scene.frame_start = first
    bpy.context.scene.frame_end = last
    bpy.context.scene.frame_set(first)
    bpy.context.view_layer.update()

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{group}_{state}.fbx")
    bpy.ops.object.select_all(action="DESELECT")
    dst.select_set(True)
    bpy.context.view_layer.objects.active = dst
    bpy.ops.export_scene.fbx(
        filepath=out,
        use_selection=True,
        object_types={"ARMATURE"},
        # FBX_SCALE_NONE bakes the 100x FBX unit conversion into the object transforms
        # (the file is cm while the Blender action is metres).  apply_fab_locomotion.py
        # divides the baked pelvis track by 100 to return to the cast skeleton's metre
        # convention.
        apply_scale_options="FBX_SCALE_NONE",
        axis_forward="-Z",
        axis_up="Y",
        primary_bone_axis="Y",
        secondary_bone_axis="X",
        use_armature_deform_only=False,
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        bake_anim_simplify_factor=0.0,
    )
    log(f"  fab: {group} {state}: {last - first + 1} frames -> {os.path.basename(out)}")
    return out


def group_base_fbx(group, log=print):
    """The cast base mesh FBX that defines a skeleton group's proportions."""
    info = _cast_info()
    spec = (info.get("groups") or {}).get(group) or {}
    mesh_name = spec.get("skeleton_mesh")
    if not mesh_name:
        raise RuntimeError(f"cast group {group} has no skeleton_mesh")
    path = os.path.join(CAST_FBX_DIR, f"{mesh_name}.fbx")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    return path


def retarget_all(log=print):
    missing = [name for name in SOURCES.values()
               if not os.path.isfile(os.path.join(ANIM_DIR, f"{name}.fbx"))]
    if missing:
        log("fab: missing exported source takes: " + ", ".join(missing))
        log("fab: run export_fab_locomotion() in the Unreal editor first")
        return 0
    groups = list((_cast_info().get("groups") or {}).keys())
    for group in groups:
        try:
            base = group_base_fbx(group, log)
        except Exception as exc:  # noqa: BLE001 - one bad group must not hide the rest
            log(f"fab: {group}: {exc}")
            continue
        for state, source in SOURCES.items():
            src = os.path.join(ANIM_DIR, f"{source}.fbx")
            retarget_take(src, base, group, state, log)
    return 0


def main():
    return retarget_all(log=print)


if __name__ == "__main__":
    raise SystemExit(main())
