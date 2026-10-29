"""
The anime cast skeleton: UE5-Mannequin bone names, anime-teen proportions (1.70 m, ~7 heads tall).

Every cast member shares this exact skeleton (same bones, same rest pose), so Unreal imports one
Skeleton asset and every A_Anime_* animation plays on every SK_Anime_* mesh. Height differences
between characters (Syrus is small, Zane tall, the girls a little shorter) are a uniform component
scale at runtime; body shape differences (Chumley's belly, coats, skirts) are in the meshes.

Rest pose: T-pose, metres, the character faces -Y (Blender) like every other asset, its left side
is +X. The bone names follow the UE5 Mannequin (pelvis, spine_01..03, neck_01, head,
clavicle/upperarm/lowerarm/hand, thigh/calf/foot/ball), so Unreal's IK Retargeter auto-maps it
to Manny/Quinn if you want to play the engine's own animations on the cast.

The armature object is named "root" (it becomes the root bone in Unreal, like the Mannequin).
"""

import bpy

# joint heights (m) - body.py / skin.py / hair.py model around these joints
GROUND = 0.0
ANKLE = 0.085
KNEE = 0.47
HIP = 0.875           # thigh joints
PELVIS = 0.93
SPINE1 = 1.01
SPINE2 = 1.12
SPINE3 = 1.235
NECK = 1.395
HEAD = 1.475          # skull base (top of the neck)
HEAD_TOP = 1.72       # end of the head bone (not the top of the hair)
SHOULDER = 1.39       # arm joint height (T-pose arms are horizontal at this height)
HIP_X = 0.088
CLAV_X = 0.03
SHOULDER_X = 0.175
ELBOW_X = 0.44
WRIST_X = 0.675
HAND_END_X = 0.78
BALL_Y = -0.105
BALL_Z = 0.03
TOE_Y = -0.175

# head geometry (used by head.py / hair.py / skin.py): anime heads are a bit large and oval
HEAD_RADIUS = 0.116
HEAD_CENTER = (0.0, -0.008, HEAD + 0.112)


def bones():
    """[(name, parent, head, tail)] in parent-first order."""
    out = [
        ("pelvis", None, (0, 0, PELVIS), (0, 0, SPINE1)),
        ("spine_01", "pelvis", (0, 0, SPINE1), (0, 0, SPINE2)),
        ("spine_02", "spine_01", (0, 0, SPINE2), (0, 0, SPINE3)),
        ("spine_03", "spine_02", (0, 0, SPINE3), (0, 0, NECK)),
        ("neck_01", "spine_03", (0, 0, NECK), (0, 0, HEAD)),
        ("head", "neck_01", (0, 0, HEAD), (0, 0, HEAD_TOP)),
    ]
    for s, side in ((1, "l"), (-1, "r")):
        out += [
            (f"clavicle_{side}", "spine_03", (s * CLAV_X, 0, SHOULDER + 0.01), (s * SHOULDER_X, 0, SHOULDER)),
            (f"upperarm_{side}", f"clavicle_{side}", (s * SHOULDER_X, 0, SHOULDER), (s * ELBOW_X, 0, SHOULDER)),
            (f"lowerarm_{side}", f"upperarm_{side}", (s * ELBOW_X, 0, SHOULDER), (s * WRIST_X, 0, SHOULDER)),
            (f"hand_{side}", f"lowerarm_{side}", (s * WRIST_X, 0, SHOULDER), (s * HAND_END_X, 0, SHOULDER)),
            (f"thigh_{side}", "pelvis", (s * HIP_X, 0, HIP), (s * HIP_X, -0.006, KNEE)),
            (f"calf_{side}", f"thigh_{side}", (s * HIP_X, -0.006, KNEE), (s * HIP_X, 0, ANKLE)),
            (f"foot_{side}", f"calf_{side}", (s * HIP_X, 0, ANKLE), (s * HIP_X, BALL_Y, BALL_Z)),
            (f"ball_{side}", f"foot_{side}", (s * HIP_X, BALL_Y, BALL_Z), (s * HIP_X, TOE_Y, BALL_Z)),
        ]
    return out


NAMES = [b[0] for b in bones()]


def create(name="root"):
    """Create the armature object (rest pose) in the current scene and return it."""
    data = bpy.data.armatures.new(name)
    arm = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(arm)
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.scene.objects:
        o.select_set(o is arm)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = data.edit_bones
    for bname, parent, head, tail in bones():
        b = eb.new(bname)
        b.head = head
        b.tail = tail
        # arms / feet: bone Z up; legs / spine: bone Z forward (-Y) - stable, mirror-consistent local axes
        horizontal = bname.split("_")[0] in ("clavicle", "upperarm", "lowerarm", "hand", "foot", "ball")
        b.align_roll((0, 0, 1) if horizontal else (0, -1, 0))
        if parent:
            b.parent = eb[parent]
            b.use_connect = False
    bpy.ops.object.mode_set(mode="OBJECT")
    for pb in arm.pose.bones:
        pb.rotation_mode = "QUATERNION"
    return arm
