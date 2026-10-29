"""
Retarget CC0 Quaternius animation takes onto the anime cast skeleton (skeleton.py).

Both rigs rest in a T-pose facing -Y, so a world-space transfer is enough: for every frame the
rotation that takes a source bone from its rest to its posed orientation (in world space) is
applied to the mapped cast bone's rest orientation; unmapped cast bones keep their rest
relation to their parent. Hip translation is scaled by the leg-length ratio, so the much
different leg length of the cast still plants the feet. Works across the Quaternius rig variants
(Ultimate Animated Characters 43 bones, Ultimate Modular 62 bones, Animated Men 31 bones) -
the hierarchy differences (IK feet parented to the root, hands with or without a wrist bone)
do not matter because nothing is copied in local space.
"""

import math

import bpy
from mathutils import Euler, Matrix, Quaternion, Vector

from .. import thirdparty
from . import skeleton as S

# cast bone -> candidate source bones (first one present wins)
BONE_MAP = {
    "pelvis": ("Hips",),
    "spine_01": ("Abdomen",),
    "spine_02": ("Torso",),
    "spine_03": ("Chest",),
    "neck_01": ("Neck",),
    "head": ("Head",),
}
for _s, _S in (("l", "L"), ("r", "R")):
    BONE_MAP.update({
        f"clavicle_{_s}": (f"Shoulder.{_S}",),
        f"upperarm_{_s}": (f"UpperArm.{_S}",),
        f"lowerarm_{_s}": (f"LowerArm.{_S}",),
        f"hand_{_s}": (f"Wrist.{_S}", f"Palm.{_S}", f"LowerArm.{_S}"),
        f"thigh_{_s}": (f"UpperLeg.{_S}",),
        f"calf_{_s}": (f"LowerLeg.{_S}",),
        f"foot_{_s}": (f"Foot.{_S}",),
    })


def _rot(m):
    return m.to_3x3().normalized().to_quaternion()


class Source:
    """One imported source file: its armature and actions (meshes are discarded)."""

    def __init__(self, path):
        bpy.context.scene.render.fps = 30
        before = set(bpy.data.actions)
        objs = thirdparty.import_file(path)
        self.arm = next(o for o in objs if o.type == "ARMATURE")
        for o in objs:
            if o.type == "MESH":
                bpy.data.objects.remove(o, do_unlink=True)
        ad = self.arm.animation_data
        if ad:
            for t in list(ad.nla_tracks):
                ad.nla_tracks.remove(t)
        self.actions = [a for a in bpy.data.actions if a not in before]
        bpy.context.view_layer.update()   # world matrices of freshly imported objects
        mw = self.arm.matrix_world
        self.rest = {b.name: mw @ b.matrix_local for b in self.arm.data.bones}
        # glTF imports put the skin's bind pose (edit bones) at a constant offset from the animated node
        # space; the unanimated top bone measures that offset per frame (see bind_offset)
        self.top = next(b.name for b in self.arm.data.bones if b.parent is None)
        self.map = {}
        for dst, cands in BONE_MAP.items():
            src = next((c for c in cands if c in self.rest), None)
            if src:
                self.map[dst] = src
        self.leg = self.rest["UpperLeg.L"].translation.z - self.rest["Foot.L"].translation.z
        arm_dir = (self.rest["LowerArm.L"].translation - self.rest["UpperArm.L"].translation).normalized()
        if arm_dir.x < 0.9:
            raise RuntimeError(f"{path}: rest pose is not a T-pose (upper arm direction {tuple(arm_dir)})")

    def bind_offset(self):
        """Armature-space transform from the bind pose to the current animated node space."""
        return self.arm.pose.bones[self.top].matrix @ self.arm.data.bones[self.top].matrix_local.inverted()

    def action(self, take):
        """Action whose name ends with |take (or equals take)."""
        for a in self.actions:
            if a.name.split("|")[-1] == take:
                return a
        raise KeyError(f"take {take!r} not found (have {[a.name.split('|')[-1] for a in self.actions]})")

    def remove(self):
        for a in self.actions:
            bpy.data.actions.remove(a)
        bpy.data.objects.remove(self.arm, do_unlink=True)


def _assign(arm, action):
    ad = arm.animation_data or arm.animation_data_create()
    ad.action = action
    if action is not None and hasattr(ad, "action_slot") and ad.action_slot is None and len(action.slots):
        ad.action_slot = action.slots[0]


ARM_BONES = ("upperarm", "lowerarm", "hand")


def hierarchy(arm):
    """Bone names parent-first."""
    out = []

    def walk(b):
        out.append(b.name)
        for c in b.children:
            walk(c)
    for b in arm.data.bones:
        if b.parent is None:
            walk(b)
    return out


def _driven(arm):
    """Bones a take keys: the UE-Mannequin-named body bones present on this skeleton (fingers, hair and
    other helper bones keep their rest pose)."""
    return set(S.NAMES) & set(arm.data.bones.keys())


def _leg(arm):
    bones = arm.data.bones
    return bones["thigh_l"].head_local.z - bones["foot_l"].head_local.z


def bake(src, take, dst_arm, name, frames=None, speed=1.0, arm_drop=0.0):
    """Retarget src take onto dst_arm as a new action `name`. Returns the action.
    frames: optional (first, last) sub-range of the source take; speed > 1 plays it faster.
    arm_drop: degrees to swing both arms closer to the body (sources with bulky suits hold them out)."""
    drop = {s: Quaternion((0, 1, 0), math.radians(arm_drop) * (1 if s == "l" else -1)) for s in ("l", "r")}
    scene = bpy.context.scene
    act = src.action(take)
    _assign(src.arm, act)
    f0, f1 = act.frame_range if frames is None else frames
    f0, f1 = int(round(f0)), int(round(f1))
    out = bpy.data.actions.new(name)
    _assign(dst_arm, out)
    rest = {b.name: b.matrix_local.copy() for b in dst_arm.data.bones}
    rest_q = {k: _rot(m) for k, m in rest.items()}
    order = hierarchy(dst_arm)
    driven = _driven(dst_arm)
    for bname in driven:
        dst_arm.pose.bones[bname].rotation_mode = "QUATERNION"
    leg_scale = _leg(dst_arm) / src.leg
    hips = src.map.get("pelvis")
    n_out = max(1, int(round((f1 - f0) / speed)))
    prev = {}
    for k in range(n_out + 1):
        f = f0 + (f1 - f0) * k / n_out
        scene.frame_set(int(f), subframe=f - int(f))
        mw = src.arm.matrix_world
        hips_rest = (mw @ src.bind_offset() @ src.arm.data.bones[hips].matrix_local).translation if hips else None
        pose = {}
        for dname, sname in src.map.items():
            pose[dname] = mw @ src.arm.pose.bones[sname].matrix
        world = {}
        for bname in order:
            b = dst_arm.data.bones[bname]
            p = b.parent.name if b.parent else None
            if bname in pose and bname in driven:
                sname = src.map[bname]
                delta = _rot(pose[bname]) @ _rot(src.rest[sname]).inverted()
                if arm_drop and bname.rsplit("_", 1)[0] in ARM_BONES:
                    delta = drop[bname[-1]] @ delta
                q = delta @ rest_q[bname]
            elif p is not None:
                q = _rot(world[p]) @ rest_q[p].inverted() @ rest_q[bname]
            else:
                q = rest_q[bname]
            if p is None:
                off = (pose["pelvis"].translation - hips_rest) * leg_scale if (hips and bname == "pelvis") else None
                pos = rest[bname].translation + off if off is not None else rest[bname].translation
            else:
                pos = (world[p] @ rest[p].inverted() @ rest[bname]).translation
            world[bname] = Matrix.Translation(pos) @ q.to_matrix().to_4x4()
            if bname not in driven:
                continue
            parent_frame = rest[bname] if p is None else world[p] @ rest[p].inverted() @ rest[bname]
            basis = parent_frame.inverted() @ world[bname]
            pb = dst_arm.pose.bones[bname]
            bq = basis.to_quaternion()
            if bname in prev:
                bq.make_compatible(prev[bname])
            prev[bname] = bq
            pb.rotation_quaternion = bq
            pb.keyframe_insert("rotation_quaternion", frame=k, group=bname)
            if bname == "pelvis":
                pb.location = basis.translation
                pb.keyframe_insert("location", frame=k, group=bname)
    out.use_fake_user = True
    return out


def pose_action(dst_arm, name, keys):
    """Hand-authored take: keys = [(frame, {bone: offset})], parent-first like bake(). An offset is either
    an XYZ Euler rotation in degrees (world space, applied on top of the rest pose) or {"aim": direction,
    "roll": degrees} which points the bone along a world direction. Bones without an offset keep their rest
    relation to their parent. The optional "_pelvis_offset" entry moves the pelvis (metres)."""
    out = bpy.data.actions.new(name)
    _assign(dst_arm, out)
    rest = {b.name: b.matrix_local.copy() for b in dst_arm.data.bones}
    rest_q = {k: _rot(m) for k, m in rest.items()}
    order = hierarchy(dst_arm)
    driven = _driven(dst_arm)
    for bname in driven:
        dst_arm.pose.bones[bname].rotation_mode = "QUATERNION"
    prev = {}
    for frame, offsets in keys:
        world = {}
        for bname in order:
            b = dst_arm.data.bones[bname]
            p = b.parent.name if b.parent else None
            if bname not in driven:
                offsets_b = None
            else:
                offsets_b = offsets.get(bname)
            if isinstance(offsets_b, dict):
                o = offsets_b
                axis = rest_q[bname] @ Vector((0, 1, 0))
                aim = Vector(o["aim"]).normalized()
                q = axis.rotation_difference(aim) @ rest_q[bname]
                if o.get("roll"):
                    q = Quaternion(aim, math.radians(o["roll"])) @ q
            elif offsets_b is not None:
                e = offsets_b
                q = Euler(tuple(math.radians(v) for v in e), "XYZ").to_quaternion() @ rest_q[bname]
            elif p is not None:
                q = _rot(world[p]) @ rest_q[p].inverted() @ rest_q[bname]
            else:
                q = rest_q[bname]
            pos = rest[bname].translation if p is None else (world[p] @ rest[p].inverted() @ rest[bname]).translation
            if bname == "pelvis" and "_pelvis_offset" in offsets:
                pos = pos + Vector(offsets["_pelvis_offset"])
            world[bname] = Matrix.Translation(pos) @ q.to_matrix().to_4x4()
            if bname not in driven:
                continue
            parent_frame = rest[bname] if p is None else world[p] @ rest[p].inverted() @ rest[bname]
            basis = parent_frame.inverted() @ world[bname]
            pb = dst_arm.pose.bones[bname]
            bq = basis.to_quaternion()
            if bname in prev:
                bq.make_compatible(prev[bname])
            prev[bname] = bq
            pb.rotation_quaternion = bq
            pb.keyframe_insert("rotation_quaternion", frame=frame, group=bname)
            if bname == "pelvis":
                pb.location = basis.translation
                pb.keyframe_insert("location", frame=frame, group=bname)
    out.use_fake_user = True
    return out
