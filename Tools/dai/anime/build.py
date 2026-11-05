"""
Builds the anime cast: one shared skeleton, the retargeted / authored animation takes, a skinned
SK_Anime_<Name> mesh per cast member (+ the duel disk attachment), the face textures, and
Data/cast.json for the Unreal importer. Also annotates layout.json's NPC markers with who stands
where (cast.assign_npcs).

Idle / Walk / Run come from the biomechanical gait solver (gait.py, foot-planting IK and a build-
time contact check); the other takes are retargeted CC0 clips or hand-authored poses. Every member
of a skeleton group is exported on one union armature (all hair / outfit helper bones merged), so
Unreal's shared Skeleton imports without a "regenerate skeleton" merge.

    python Tools/build_island.py cast             # build + export the cast
    python Tools/preview_anime.py [ids...]          # Cycles lineup render
"""

import os

import bpy
from mathutils import Matrix, Vector

from .. import config as C
from .. import jsonio, palette, thirdparty
from ..character import export_skeletal
from . import body as B
from . import cast as CAST
from . import face as FACE
from . import gait as GAIT
from . import hair as HAIR
from . import head as HEAD
from . import manifest as MANIFEST
from . import models as M
from . import retarget as RT
from . import skeleton as S
from . import skin as K

OUT_REL = "Meshes/Characters/Anime"
TEX_REL = "Characters"
OUTLINE_COLOR = (0.09, 0.06, 0.07)

# Authored takes (joint-space directions, see retarget.pose_action) --------------------------------
def _seg(rig, bone, target, rest_bone=None):
    """Pose offset that aims a limb segment (works on VRoid bones whose displayed tails point up)."""
    if rig is None:
        return {"aim": target}
    return {"seg": target, "rest": tuple(rig.seg[rest_bone or bone])}


def _periodic(points, t):
    """Periodic Catmull-Rom through [(phase, (x, y, z))] (phases ascending in [0, 1))."""
    from mathutils import Vector
    t %= 1.0
    n = len(points)
    for i in range(n):
        t0 = points[i][0]
        t1 = points[(i + 1) % n][0] + (1.0 if i == n - 1 else 0.0)
        tt = t + (1.0 if t < t0 else 0.0)
        if t0 <= tt <= t1:
            u = (tt - t0) / max(t1 - t0, 1e-6)
            p0 = Vector(points[(i - 1) % n][1])
            p1 = Vector(points[i][1])
            p2 = Vector(points[(i + 1) % n][1])
            p3 = Vector(points[(i + 2) % n][1])
            u2, u3 = u * u, u * u * u
            return 0.5 * ((2.0 * p1) + (-p0 + p2) * u + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * u2
                          + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * u3)
    return Vector(points[0][1])


def _bump(t, centre, width):
    """Smooth periodic bump: 1 at `centre`, 0 beyond +-width (phases wrap)."""
    import math
    d = abs(((t - centre + 0.5) % 1.0) - 0.5)
    if d >= width:
        return 0.0
    return 0.5 + 0.5 * math.cos(math.pi * d / width)


def _stance_feet(rig, left=(0.0, 0.0), right=(0.0, 0.0), toe_l=0.0, toe_r=0.0):
    """Planted ankle targets for a standing pose: (x offset outward, y offset backward) per foot."""
    from mathutils import Vector
    feet = {}
    for side, (dx, dy) in (("l", left), ("r", right)):
        s = 1.0 if side == "l" else -1.0
        feet[side] = (Vector((rig.foot_x[side] + s * dx, rig.joint[f"foot_{side}"].y + dy, rig.ankle_z)), 0.0, 0.0, True)
    return feet


DUEL_SECONDS = 4.0


def _duel_keys(rig=None):
    """Duel stance: feet planted shoulder-width with the disk side forward, knees soft, the disk arm
    held across the front with the forearm level, the card hand raised by the chest. One slow
    breath per 4 s loop with a small weight shift, so a long duel never looks frozen."""
    import math
    if rig is not None and not isinstance(rig, GAIT.Rig):
        rig = GAIT.Rig(rig)
    if rig is None:
        return [(0, {})]
    hs = rig.height_scale
    n = int(round(DUEL_SECONDS * GAIT.FPS))
    keys = []
    for f in range(n + 1):
        ph = f / n
        a = 2.0 * math.pi * ph
        br = 0.5 - 0.5 * math.cos(a)            # 0 exhaled .. 1 inhaled
        shift = math.sin(a)
        feet = _stance_feet(rig, left=(0.12 * hs, -0.11 * hs), right=(0.10 * hs, 0.10 * hs))
        yaw = 9.0 + 1.0 * shift                 # trunk turned a little to the right (card hand back)
        upper = {
            "pelvis": (1.5, 1.0 * shift, yaw * 0.6),
            "spine_01": (4.0, -0.5 * shift, yaw * 0.75),
            "spine_02": (5.0 + 0.8 * br, -0.8 * shift, yaw * 0.9),
            "spine_03": (4.0 + 1.2 * br, -1.0 * shift, yaw),
            "neck_01": (1.0 - 0.6 * br, 0.0, yaw * 0.4),
            # eyes on the opponent: the head counters the trunk turn
            "head": (-2.0 + 0.4 * br, 0.3 * shift, -4.0),
        }
        pelvis_z = (0.892 - 0.003 * br) * hs
        # Disk arm (left): elbow out and forward, forearm level across the body. Card hand
        # (right): elbow down at the side, hand raised in front of the chest.
        arms = {
            "l": (Vector((-0.09, -0.38, -0.17 + 0.006 * br)) * hs, (0.9, -0.1, -0.4), 4.0),
            "r": (Vector((0.06, -0.24, -0.05 + 0.006 * br)) * hs, (-0.35, 0.35, -1.0), 18.0),
        }
        key, _ = GAIT._assemble(rig, GAIT.IDLE, ph, 0.004 * shift * hs, pelvis_z, upper["pelvis"], feet, upper,
                                idle=True, arms=arms)
        keys.append((f, key))
    return keys


SWIM_SECONDS = 1.6     # one full stroke cycle (both arms) at the clip's 1.25 m/s reference speed


def _swim_keys(rig=None):
    """Front crawl, authored upright (the avatar component pitches the body forward in the water).

    Authoring frame: +Z is the swimming direction (overhead), -Y is down into the water (in front
    of the chest), +Y is up out of the water (behind the back). Per arm: entry in front of the
    shoulder, a short glide, a high-elbow catch, the pull under the chest, the push past the hip,
    and a high-elbow recovery out of the water. The body rolls ~40 deg towards the pulling arm,
    the head turns with the roll to breathe every second stroke, and the legs do a six-beat
    flutter kick from the hips with soft knees and pointed toes."""
    import math
    if rig is not None and not isinstance(rig, GAIT.Rig):
        rig = GAIT.Rig(rig)
    if rig is None:
        return [(0, {})]
    reach = (rig.upperarm + rig.lowerarm) * 0.97
    # wrist path relative to the shoulder (left arm, +x outward), in units of the arm's reach
    path = [
        (0.00, (0.10, -0.16, 0.95)),     # entry, arm extended overhead
        (0.14, (0.12, -0.30, 0.86)),     # glide / reach
        (0.28, (0.12, -0.68, 0.48)),     # catch: forearm vertical under a high elbow
        (0.42, (-0.06, -0.62, 0.02)),    # pull under the chest
        (0.56, (0.12, -0.36, -0.62)),    # push past the hip
        (0.64, (0.24, -0.06, -0.80)),    # exit at the thigh
        (0.78, (0.42, 0.34, -0.12)),     # recovery: elbow high, hand trailing low
        (0.90, (0.34, 0.16, 0.55)),      # hand swings forward beside the head
    ]
    n = int(round(SWIM_SECONDS * GAIT.FPS))
    keys = []
    for f in range(n + 1):
        ph = f / n
        roll = -40.0 * math.sin(2.0 * math.pi * (ph - 0.18))
        breath = -38.0 * _bump(ph, 0.36, 0.17)          # every second stroke, to the right
        arms = {}
        for side, s, off in (("l", 1.0, 0.0), ("r", -1.0, 0.5)):
            p = _periodic(path, ph + off)
            rel = Vector((s * p.x, p.y, p.z)) * reach
            # rotate the stroke with the body roll (about the long axis, +Z)
            rr = math.radians(roll)
            c, sn = math.cos(rr), math.sin(rr)
            rel = Vector((rel.x * c - rel.y * sn, rel.x * sn + rel.y * c, rel.z))
            bx, by = s * 0.55, 1.0          # the elbow stays high (towards the surface) and out
            bend = (bx * c - by * sn, bx * sn + by * c, 0.15)
            arms[side] = (rel, bend, 8.0)
        kick = 2.0 * math.pi * 3.0 * ph
        upper = {
            "pelvis": (0.0, 0.0, roll * 0.55),
            "spine_01": (0.0, 0.0, roll * 0.72),
            "spine_02": (0.0, 0.0, roll * 0.88),
            "spine_03": (0.0, 0.0, roll),
            "neck_01": (-6.0, 0.0, roll + breath * 0.4),
            "head": (-10.0 + 6.0 * _bump(ph, 0.36, 0.17), 0.0, roll + breath),
        }
        key, _ = GAIT._assemble(rig, GAIT.IDLE, ph, 0.0, rig.joint["pelvis"].z, upper["pelvis"],
                                _stance_feet(rig), upper, idle=True, arms=arms)
        # legs: flutter kick (overrides the planted-stance IK legs)
        for side, s, off in (("l", 1.0, 0.0), ("r", -1.0, math.pi)):
            th = 11.0 * math.sin(kick + off)                       # +X: towards +Y (up)
            flex = 14.0 + 12.0 * max(0.0, math.sin(kick + off - 0.9))
            yaw = roll * 0.45
            key[f"thigh_{side}"] = (th, 0.0, yaw)
            key[f"calf_{side}"] = (th + flex, 0.0, yaw)
            key[f"foot_{side}"] = (th + flex + 72.0, 0.0, yaw + s * 6.0)   # toes pointed along the shin
            key[f"ball_{side}"] = (th + flex + 72.0, 0.0, yaw + s * 6.0)
        keys.append((f, key))
    return keys


TREAD_SECONDS = 2.0


def _tread_keys(rig=None):
    """Treading water upright: forearms sculling in and out at chest depth, an alternating
    breaststroke-style (eggbeater) kick, a gentle rise and sink with each kick."""
    import math
    if rig is not None and not isinstance(rig, GAIT.Rig):
        rig = GAIT.Rig(rig)
    if rig is None:
        return [(0, {})]
    hs = rig.height_scale
    n = int(round(TREAD_SECONDS * GAIT.FPS))
    keys = []
    for f in range(n + 1):
        ph = f / n
        a = 2.0 * math.pi * ph
        scull = math.sin(2.0 * a)                # two sculls per loop
        arms = {}
        for side, s in (("l", 1.0), ("r", -1.0)):
            rel = Vector((s * (0.20 + 0.12 * scull), -0.30 + 0.03 * math.cos(2.0 * a), -0.30)) * hs
            arms[side] = (rel, (s * 1.0, 0.3, -0.6), 25.0 * scull * s)
        upper = {
            "pelvis": (8.0, 0.0, 0.0),
            "spine_01": (4.0, 0.0, 0.0),
            "spine_02": (2.0, 0.0, 0.0),
            "spine_03": (0.0, 0.0, 0.0),
            "neck_01": (-6.0, 0.0, 0.0),
            "head": (-10.0, 0.0, 6.0 * math.sin(a)),
        }
        key, _ = GAIT._assemble(rig, GAIT.IDLE, ph, 0.0, rig.joint["pelvis"].z, upper["pelvis"],
                                _stance_feet(rig), upper, idle=True, arms=arms)
        key["_pelvis_offset"] = (0.0, 0.0, 0.015 * math.sin(2.0 * a - 0.6))
        for side, s, off in (("l", 1.0, 0.0), ("r", -1.0, math.pi)):
            k = a + off
            hip = -35.0 - 15.0 * math.sin(k)                       # thighs forward (seated)
            knee = 70.0 + 25.0 * math.sin(k + 1.2)
            # knees and feet wide (abduction about the front-back axis: -Y rotation moves the
            # left leg out), the feet circling outward behind the knees
            out = -s * (15.0 + 6.0 * math.cos(k))
            key[f"thigh_{side}"] = (hip, out, 0.0)
            key[f"calf_{side}"] = (hip + knee, out * 1.3, 0.0)
            key[f"foot_{side}"] = (hip + knee - 10.0, out * 1.3, s * 20.0)
            key[f"ball_{side}"] = (hip + knee - 10.0, out * 1.3, s * 20.0)
        keys.append((f, key))
    return keys


def _air_feet(rig, hs, left, right):
    """Ankle targets relative to each hip's rest position (x outward, y backward, z up), metres."""
    feet = {}
    for side, (dx, dy, dz) in (("l", left), ("r", right)):
        s = 1.0 if side == "l" else -1.0
        feet[side] = (Vector((rig.foot_x[side] + s * dx * hs, rig.joint[f"foot_{side}"].y + dy * hs,
                              rig.ankle_z + dz * hs)), 0.0, 0.0, False)
    return feet


def _air_pose(rig, ph, pelvis_dz, lean, left, right, foot_pitch, arms_rel, arm_bend=(0.0, 0.3, -1.0), head=0.0):
    hs = rig.height_scale
    feet = _air_feet(rig, hs, left, right)
    for side in ("l", "r"):
        a, _, _, st = feet[side]
        feet[side] = (a, foot_pitch[side], foot_pitch[side] * 0.5, st)
    upper = {
        "pelvis": (lean * 0.3, 0.0, 0.0),
        "spine_01": (lean * 0.55, 0.0, 0.0),
        "spine_02": (lean * 0.8, 0.0, 0.0),
        "spine_03": (lean, 0.0, 0.0),
        "neck_01": (lean * 0.3, 0.0, 0.0),
        "head": (-lean * 0.6 + head, 0.0, 0.0),
    }
    arms = {}
    for side, s in (("l", 1.0), ("r", -1.0)):
        x, y, z = arms_rel
        arms[side] = (Vector((s * x, y, z)) * hs, (s * 0.25 + arm_bend[0] * s, arm_bend[1], arm_bend[2]), 12.0)
    key, _ = GAIT._assemble(rig, GAIT.IDLE, ph, 0.0, rig.joint["pelvis"].z + pelvis_dz * hs, upper["pelvis"],
                            feet, upper, idle=True, arms=arms)
    return key


def _sample(track, t):
    """Piecewise smoothstep through [(t, value)] where value is a float or a tuple."""
    for i in range(len(track) - 1):
        t0, v0 = track[i]
        t1, v1 = track[i + 1]
        if t0 <= t <= t1:
            u = GAIT._smooth((t - t0) / max(t1 - t0, 1e-6))
            if isinstance(v0, tuple):
                return tuple(a + (b - a) * u for a, b in zip(v0, v1))
            return v0 + (v1 - v0) * u
    return track[-1][1]


JUMP_SECONDS = 0.5


def _jump_keys(rig=None):
    """Airborne half of a standing jump, from the instant the feet leave the ground to the apex:
    the body is fully extended with the toes still pointed and the arms thrown up from the swing,
    then the knees and hips flex to tuck the legs up while the arms settle out to the sides for
    balance. The runtime times the clip to the real rise (v0 / g)."""
    if rig is not None and not isinstance(rig, GAIT.Rig):
        rig = GAIT.Rig(rig)
    if rig is None:
        return [(0, {})]
    n = int(round(JUMP_SECONDS * GAIT.FPS))
    # tracks over normalised time 0..1
    tuck = [(0.0, 0.0), (0.25, 0.15), (0.75, 1.0), (1.0, 1.0)]
    keys = []
    for f in range(n + 1):
        t = f / n
        k = _sample(tuck, t)
        # extended (toes pointed below the hips) -> tucked (ankles up, feet under the knees)
        left = (0.010, _lerp(0.02, 0.04, k), _lerp(-0.035, 0.20, k))
        right = (0.010, _lerp(0.05, 0.10, k), _lerp(-0.045, 0.16, k))
        foot = {"l": _lerp(38.0, 18.0, k), "r": _lerp(42.0, 24.0, k)}
        arms = _sample([(0.0, (0.10, -0.30, 0.10)), (0.35, (0.16, -0.24, -0.20)), (1.0, (0.22, -0.10, -0.38))], t)
        lean = _lerp(-2.0, 9.0, k)
        keys.append((f, _air_pose(rig, t, _lerp(0.035, -0.03, k), lean, left, right, foot, arms, head=-2.0)))
    return keys


FALL_SECONDS = 1.2


def _fall_keys(rig=None):
    """Falling: legs reaching down for the ground with soft knees (one a little ahead of the
    other), arms out and raised for balance, a slow cycling of the limbs so a long drop does not
    look frozen."""
    import math
    if rig is not None and not isinstance(rig, GAIT.Rig):
        rig = GAIT.Rig(rig)
    if rig is None:
        return [(0, {})]
    n = int(round(FALL_SECONDS * GAIT.FPS))
    keys = []
    for f in range(n + 1):
        t = f / n
        c = math.sin(2.0 * math.pi * t)
        left = (0.03, -0.08 + 0.05 * c, 0.07 + 0.03 * c)
        right = (0.04, 0.05 - 0.05 * c, 0.10 - 0.03 * c)
        foot = {"l": 14.0 + 4.0 * c, "r": 20.0 - 4.0 * c}
        # arms out and a little forward below shoulder height, elbows soft
        arms = (0.31 + 0.02 * c, -0.10 + 0.04 * c, -0.21 + 0.04 * math.sin(2.0 * math.pi * t + 1.0))
        keys.append((f, _air_pose(rig, t, -0.02, 3.0, left, right, foot, arms, arm_bend=(0.3, 0.7, -0.4), head=-6.0)))
    return keys


LAND_SECONDS = 0.7


def _land_keys(rig=None):
    """Landing from a jump: the feet plant on contact with the knees still nearly straight, the
    hips, knees and ankles flex together to absorb the impact (the pelvis drops ~20 cm in 0.15 s),
    the trunk pitches forward over the feet and the arms swing forward-down for balance, then the
    body rises back into the relaxed standing pose. The runtime scales the weight (and so the
    depth) with the impact speed."""
    if rig is not None and not isinstance(rig, GAIT.Rig):
        rig = GAIT.Rig(rig)
    if rig is None:
        return [(0, {})]
    hs = rig.height_scale
    n = int(round(LAND_SECONDS * GAIT.FPS))
    drop = [(0.0, 0.0), (0.21, -0.20), (0.36, -0.185), (1.0, -0.012)]
    lean = [(0.0, 2.0), (0.21, 20.0), (0.40, 16.0), (1.0, 1.2)]
    arms = [(0.0, (0.20, -0.06, -0.36)), (0.22, (0.17, -0.30, -0.36)), (0.45, (0.12, -0.24, -0.42)),
            (1.0, (0.05, 0.0, -0.455))]
    keys = []
    for f in range(n + 1):
        t = f / n
        feet = _stance_feet(rig, left=(0.03 * hs, 0.0), right=(0.03 * hs, 0.0))
        ln = _sample(lean, t)
        upper = {
            "pelvis": (ln * 0.45, 0.0, 0.0),
            "spine_01": (ln * 0.65, 0.0, 0.0),
            "spine_02": (ln * 0.85, 0.0, 0.0),
            "spine_03": (ln, 0.0, 0.0),
            "neck_01": (ln * 0.2, 0.0, 0.0),
            # eyes stay on the horizon
            "head": (-ln * 0.75, 0.0, 0.0),
        }
        x, y, z = _sample(arms, t)
        arm = {side: (Vector((s * x, y, z)) * hs, (s * 0.25, 0.4, -1.0), 10.0) for side, s in (("l", 1.0), ("r", -1.0))}
        # The pelvis also moves back a little so the centre of mass stays over the feet.
        dz = _sample(drop, t)
        key, _ = GAIT._assemble(rig, GAIT.IDLE, t, 0.0, 0.918 * hs + dz * hs, upper["pelvis"], feet, upper,
                                idle=True, arms=arm, pelvis_y=-dz * 0.35 * hs)
        keys.append((f, key))
    return keys


def _lerp(a, b, t):
    return a + (b - a) * t


# state -> (source registry key | None for authored, take, loop)
TAKES = [
    ("Wave", "A_Anime_Wave", False), ("Yes", "A_Anime_Yes", False), ("No", "A_Anime_No", False),
    ("Sit", "A_Anime_Sit", True), ("Clap", "A_Anime_Clap", False), ("Interact", "A_Anime_Interact", False),
]
# state -> (key generator, loop, authored ground speed in cm/s or None)
AUTHORED = {
    "Idle": (GAIT.idle_keys, True, 0.0),
    "Jump": (_jump_keys, False, None),
    "Fall": (_fall_keys, True, None),
    "Land": (_land_keys, False, None),
    "Walk": (GAIT.walk_keys, True, GAIT.WALK.speed * 100.0),
    "Run": (GAIT.run_keys, True, GAIT.RUN.speed * 100.0),
    "Duel": (_duel_keys, True, None),
    "Swim": (_swim_keys, True, None),
    "Tread": (_tread_keys, True, None),
}


def key_name(cid):
    return "".join(p.capitalize() for p in cid.split("_"))


# --------------------------------------------------------------------------- materials
def _toon(name, color, **kw):
    palette.register({name: dict(kind="toon", color=tuple(color), rough=0.85, fill=kw.pop("fill", 0.5), **kw)})
    return name


def materials(cid, entry, log=print):
    """Role -> palette material name for one cast member (registers palette entries, paints the face)."""
    key = key_name(cid)
    col = entry["colors"]
    tint = set(entry.get("tint", []))
    m = {}
    for role in ("jacket", "trim", "inner", "pants", "shoes", "sole", "skirt", "socks", "boots"):
        if role in col:
            suffix = "JacketTint" if (role == "jacket" and "jacket" in tint) else role.capitalize()
            m[role] = _toon(f"M_Anime_{key}_{suffix}", col[role])
    m["skin"] = _toon("M_Anime_Skin", CAST.SKIN)
    hc = entry["hair"]
    if "hair" in tint:
        m["hair"] = m["hair2"] = _toon(f"M_Anime_{key}_HairTint", hc["color"], fill=0.45)
    else:
        m["hair"] = _toon(f"M_Anime_{key}_Hair", hc["color"], fill=0.45)
        m["hair2"] = _toon(f"M_Anime_{key}_Hair2", hc.get("color2", hc["color"]), fill=0.45)
    tex = os.path.join(C.OUT_TEXTURES, TEX_REL, f"T_AnimeFace_{key}.png")
    FACE.paint(dict(entry["face"], skin=CAST.SKIN), tex)
    m["face"] = _toon(f"M_Anime_{key}_Face", (1.0, 1.0, 1.0), base=f"{TEX_REL}/T_AnimeFace_{key}", fill=0.6)
    m["glasses"] = _toon("M_Anime_Glasses", (0.20, 0.22, 0.28))
    m["ruff"] = _toon("M_Anime_Ruff", (0.97, 0.97, 0.96))
    palette.register({K.OUTLINE_MAT: dict(kind="outline", color=OUTLINE_COLOR)})
    return m


def disk_materials():
    return dict(disk=_toon("M_Anime_DuelDisk", (0.78, 0.80, 0.84)), gold=_toon("M_Anime_DiskGold", (0.95, 0.72, 0.22)),
                glow=_register_glow())


def _register_glow():
    palette.register({"M_Anime_DiskGlow": dict(kind="emissive", color=(0.25, 0.85, 1.0), strength=6.0)})
    return "M_Anime_DiskGlow"


# --------------------------------------------------------------------------- preview materials (Cycles)
def preview_material(name):
    """Toon look for Blender previews: banded diffuse + flat fill light, inverted-hull ink lines."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    spec = palette.MATERIALS.get(name, dict(kind="opaque", color=(1, 0, 1)))
    kind = spec.get("kind")
    if kind not in ("toon", "outline"):
        from .. import blend
        return blend.material(name)
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    lin = palette.srgb_to_linear(spec["color"])
    if kind == "outline":
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        ink = nt.nodes.new("ShaderNodeEmission")
        ink.inputs["Color"].default_value = (*lin, 1.0)
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
        nt.links.new(ink.outputs[0], mix.inputs[1])
        nt.links.new(tr.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
        return mat
    col = nt.nodes.new("ShaderNodeRGB")
    col.outputs[0].default_value = (*lin, 1.0)
    src = col.outputs[0]
    tex = None
    if spec.get("base"):
        img_path = os.path.join(C.OUT_TEXTURES, spec["base"] + ".png")
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(img_path, check_existing=True)
        src = tex.outputs["Color"]
    alpha = tex.outputs["Alpha"] if tex is not None and spec.get("masked") else None
    toon = nt.nodes.new("ShaderNodeBsdfToon")
    toon.component = "DIFFUSE"
    toon.inputs["Size"].default_value = 0.85
    toon.inputs["Smooth"].default_value = 0.12
    nt.links.new(src, toon.inputs["Color"])
    em = nt.nodes.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = spec.get("fill", 0.3)
    nt.links.new(src, em.inputs["Color"])
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(toon.outputs[0], add.inputs[0])
    nt.links.new(em.outputs[0], add.inputs[1])
    if alpha is not None:
        cut = nt.nodes.new("ShaderNodeMath")
        cut.operation = "GREATER_THAN"
        cut.inputs[1].default_value = 0.5
        nt.links.new(alpha, cut.inputs[0])
        tr = nt.nodes.new("ShaderNodeBsdfTransparent")
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(cut.outputs[0], mix.inputs[0])
        nt.links.new(tr.outputs[0], mix.inputs[1])
        nt.links.new(add.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs[0])
    else:
        nt.links.new(add.outputs[0], out.inputs[0])
    mat.diffuse_color = (*lin, 1.0)
    return mat


# --------------------------------------------------------------------------- characters
def build_character(cid, entry, arm):
    m = materials(cid, entry)
    bd = entry.get("body", {})
    shape = entry.get("head", {})
    asm = K.Assembly(f"SK_Anime_{key_name(cid)}")
    asm.add(HEAD.head(m["face"], m["skin"], shape), K.rigid("head"), 1.0)
    asm.add(HEAD.neck(m["skin"]), lambda p: K.spine(p) if p.z < S.NECK else
            {"neck_01": 1.0 - K._smooth((p.z - S.NECK) / 0.08), "head": K._smooth((p.z - S.NECK) / 0.08)}, 0.0)
    hc = entry["hair"]
    short, long = HAIR.build(hc["style"], m["hair"], m["hair2"], shape)
    asm.add(short, K.rigid("head"), 1.25)
    asm.add(long, K.head_and_body(), 1.25)
    for parts in (B.jacket(m, bd), B.arms(m), B.legs(m, bd)):
        for mb, fn, ol in parts:
            asm.add(mb, fn, ol)
    for ex in entry.get("extras", []):
        for mb, fn, ol in (B.glasses(m["glasses"], shape) if ex == "glasses" else B.ruff(m["ruff"]) if ex == "ruff" else []):
            asm.add(mb, fn, ol)
    return asm.build(arm, face_mats=[m["face"]], material_fn=preview_material)


def build_disk(arm, name="SK_Anime_DuelDisk"):
    """Duel disk skinned to this skeleton's left forearm (separate mesh, follows the body in Unreal)."""
    asm = K.Assembly(name)
    for mb, fn, ol in B.duel_disk(disk_materials(), *_disk_bones(arm)):
        asm.add(mb, fn, ol)
    return asm.build(arm, material_fn=preview_material)


# Retargeted takes performed standing on the spot: their legs are re-solved so both feet stay
# planted where the idle stands (the source rigs' proportions otherwise let them drift or sink).
PLANTED = {"Wave", "Yes", "No", "Clap", "Interact"}


def _replant(arm, action, log=print):
    """Re-bake a retargeted in-place take with two-bone leg IK pinning both ankles to the idle
    stance; the upper body, pelvis rotation and pelvis height are kept, the pelvis's horizontal
    drift is limited so the weight stays between the feet."""
    import math
    rig = GAIT.Rig(arm)
    RT._assign(arm, action)
    scene = bpy.context.scene
    f0, f1 = (int(round(v)) for v in action.frame_range)
    driven = set(S.NAMES) & set(arm.data.bones.keys())
    rest_pelvis = rig.rest["pelvis"].translation
    # The sources stand in their own (often crouched) stance: keep only the pelvis motion relative
    # to the take's first frame and put it on the cast's relaxed standing height.
    scene.frame_set(f0)
    first = arm.pose.bones["pelvis"].matrix.translation.copy()
    stand = Vector((0.0, 0.0, 0.918 * rig.height_scale - rest_pelvis.z))
    keys = []
    lifted = 0.0
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        k = {}
        for b in driven:
            q = arm.pose.bones[b].matrix.to_quaternion() @ rig.rest_q[b].inverted()
            k[b] = tuple(math.degrees(v) for v in q.to_euler("XYZ"))
        pm = arm.pose.bones["pelvis"].matrix
        rel = pm.translation - first
        off = stand + Vector((max(-0.03, min(0.03, rel.x)), max(-0.04, min(0.04, rel.y)),
                              max(-0.05, min(0.01, rel.z))))
        rot = pm.to_quaternion()
        ankles = {side: Vector((rig.foot_x[side], rig.joint[f"foot_{side}"].y, rig.ankle_z)) for side in ("l", "r")}
        # lower the pelvis until both straight-ish legs reach their planted ankles
        for _ in range(3):
            pw = Matrix.Translation(rest_pelvis + off) @ rot.to_matrix().to_4x4()
            worst = 0.0
            for side, ankle in ankles.items():
                worst = max(worst, (rig.hip(pw, side) - ankle).length - (rig.leg - 0.012))
            if worst <= 0.0:
                break
            off.z -= worst + 0.001
        lifted = min(lifted, off.z)
        pw = Matrix.Translation(rest_pelvis + off) @ rot.to_matrix().to_4x4()
        for side, ankle in ankles.items():
            thigh, calf, _ = rig.pose_leg(side, rig.hip(pw, side), ankle)
            k[f"thigh_{side}"] = {"seg": tuple(thigh), "rest": tuple(rig.seg[f"thigh_{side}"])}
            k[f"calf_{side}"] = {"seg": tuple(calf), "rest": tuple(rig.seg[f"calf_{side}"])}
            toe = (1 if side == "l" else -1) * GAIT.IDLE.toe_out
            k[f"foot_{side}"] = (0.0, 0.0, toe)
            k[f"ball_{side}"] = (0.0, 0.0, toe)
        k["_pelvis_offset"] = tuple(off)
        keys.append((f - f0, k))
    RT._assign(arm, None)
    name = action.name
    bpy.data.actions.remove(action)
    out = RT.pose_action(arm, name, keys)
    log(f"  anime: {name}: feet planted ({len(keys)} frames, pelvis {lifted * 100:+.1f} cm from the rest pose at its lowest)")
    return out


def bake_takes(arm, log=print):
    """All animation takes onto `arm`. Returns {state: (action, loop, speed)}."""
    reg = thirdparty.registry().get("anime", {})
    sources = {}
    out = {}
    for state, reg_key, loop in TAKES:
        spec = reg.get(reg_key)
        if not spec:
            log(f"  !! anime: no source registered for {reg_key}")
            continue
        path = thirdparty.tp_path(spec["file"])
        if path not in sources:
            sources[path] = RT.Source(path)
        rng = tuple(spec["frames"]) if spec.get("frames") else None
        act = RT.bake(sources[path], spec["take"], arm, reg_key, frames=rng, speed=spec.get("speed", 1.0),
                      arm_drop=spec.get("arm_drop", 0.0))
        if state in PLANTED:
            act = _replant(arm, act, log)
        out[state] = (act, loop, None)
    for src in sources.values():
        src.remove()
    for state, (fn, loop, speed) in AUTHORED.items():
        act = RT.pose_action(arm, f"A_Anime_{state}", fn(arm))
        if state in ("Walk", "Run"):
            metrics = GAIT.validate(arm, act, GAIT.WALK if state == "Walk" else GAIT.RUN, log)
            speed = metrics["speed"] * 100.0
        out[state] = (act, loop, speed)
    RT._assign(arm, None)
    return out


def _ground_speed(arm, action):
    """Natural ground speed (cm/s) of a locomotion cycle: how fast a planted foot slides backwards."""
    RT._assign(arm, action)
    scene = bpy.context.scene
    f0, f1 = (int(round(v)) for v in action.frame_range)
    ys = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        ys.append((arm.matrix_world @ arm.pose.bones["foot_l"].head).y)
    RT._assign(arm, None)
    dur = max(1, f1 - f0) / scene.render.fps
    return round(2.0 * (max(ys) - min(ys)) / dur * 100.0, 1)


# --------------------------------------------------------------------------- stage
PROCEDURAL = "Proc"      # skeleton group of the procedural fallback characters


def _export_takes(arm, group, out_dir, log):
    scene = bpy.context.scene
    takes = bake_takes(arm, log)
    anims = {}
    for state, (act, loop, speed) in takes.items():
        RT._assign(arm, act)
        f0, f1 = (int(round(v)) for v in act.frame_range)
        scene.frame_start, scene.frame_end = f0, max(f1, f0 + 1)
        name = f"A_Anime_{group}_{state}"
        export_skeletal([arm], arm, os.path.join(out_dir, f"{name}.fbx"), {"ARMATURE"}, anim=act, simplify=1.0,
                        deform_only=False)
        entry = dict(name=name, file=f"{OUT_REL}/{name}.fbx", loop=loop,
                     seconds=round((f1 - f0) / scene.render.fps, 3))
        if state in ("Walk", "Run"):
            entry["speed"] = round(speed if speed else _ground_speed(arm, act), 1)
        anims[state] = entry
    RT._assign(arm, None)
    log(f"  anime: {group}: {len(takes)} takes, walk {anims.get('Walk', {}).get('speed')} cm/s, "
        f"run {anims.get('Run', {}).get('speed')} cm/s")
    return anims


def _disk_bones(arm):
    b = arm.data.bones["lowerarm_l"]
    return tuple(b.head_local), tuple(b.tail_local)


def _merge_rig(base, arm, mesh, log=print):
    """Add the bones `arm` uses that `base` lacks, then rebind `mesh` to `base`.

    Each cast member is built from the same base model but restyling can keep or remove hair /
    outfit helper bones. Exporting every member with one union armature keeps Unreal's shared
    Skeleton complete, so importing a member can never trigger a "regenerate the skeleton"
    merge (which invalidates the meshes and takes already imported).
    """
    if base is arm:
        return
    order = []
    def walk(bone):
        order.append(bone)
        for child in bone.children:
            walk(child)
    for bone in arm.data.bones:
        if bone.parent is None:
            walk(bone)

    for o in bpy.context.scene.objects:
        o.select_set(False)
    base.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.mode_set(mode="EDIT")
    eb = base.data.edit_bones
    for bone in order:
        if bone.name in eb:
            current = eb[bone.name]
            if (current.head - bone.head_local).length > 1e-4 or (current.tail - bone.tail_local).length > 1e-4:
                log(f"  anime: helper bone {bone.name} differs between cast members; keeping the first rest pose")
            continue
        nb = eb.new(bone.name)
        nb.head = bone.head_local
        nb.tail = bone.tail_local
        try:
            nb.align_roll(bone.z_axis)
        except Exception:  # noqa: BLE001
            nb.roll = bone.roll
        nb.use_deform = bone.use_deform
        nb.use_connect = False
        if bone.parent is not None and bone.parent.name in eb:
            nb.parent = eb[bone.parent.name]
    bpy.ops.object.mode_set(mode="OBJECT")

    for mod in mesh.modifiers:
        if mod.type == "ARMATURE":
            mod.object = base
    world = mesh.matrix_world.copy()
    mesh.parent = base
    mesh.matrix_parent_inverse.identity()
    mesh.matrix_world = world


def _cast_output_files(info):
    """Manifest FBX paths (relative to SourceAssets) for one cast.json document."""
    files = set()

    def add(rel):
        if isinstance(rel, str) and rel:
            files.add(rel.replace("\\", "/"))

    for entry in (info.get("meshes") or {}).values():
        if isinstance(entry, dict):
            add(entry.get("file"))
    for group in (info.get("groups") or {}).values():
        if not isinstance(group, dict):
            continue
        for key in ("base_mesh", "duel_disk"):
            item = group.get(key) or {}
            if isinstance(item, dict):
                add(item.get("file"))
        for anim in (group.get("anims") or {}).values():
            if isinstance(anim, dict):
                add(anim.get("file"))
    return files


def _cast_output_textures(info):
    """Texture paths (relative to SourceAssets/Textures) referenced by the cast materials."""
    textures = set()
    for spec in (info.get("materials") or {}).values():
        base = spec.get("base") if isinstance(spec, dict) else None
        if isinstance(base, str) and base.startswith(TEX_REL + "/"):
            textures.add(base + ".png")
    return textures


def _remove_generated(root, rel, prefix):
    """Delete one generated file only if it stays under root and its prefix."""
    rel = rel.replace("\\", "/")
    if not rel.startswith(prefix):
        return False
    path = os.path.realpath(os.path.join(root, *rel.split("/")))
    root_real = os.path.realpath(root)
    try:
        if os.path.commonpath((root_real, path)) != root_real:
            return False
    except ValueError:
        return False
    if not os.path.isfile(path):
        return False
    os.remove(path)
    return True


def _prune_previous_outputs(old_info, new_info, log):
    """Remove files the previous cast.json owned but the new manifest no longer does.

    This runs only after the new cast.json has been written atomically, so an
    interrupted export leaves the previous manifests and meshes usable.  It is
    skipped for a partial (``only=...``) build: build() merges the rebuilt
    subset into the previous manifest (see merge_partial_manifests), so the
    published cast.json still lists the untouched members that keep their
    exported files - pruning here would delete referenced assets.  Members
    removed from the cast registry are dropped by the next full build.
    """
    if not isinstance(old_info, dict):
        return 0
    removed = 0
    for rel in sorted(_cast_output_files(old_info) - _cast_output_files(new_info)):
        try:
            removed += _remove_generated(C.OUT_DIR, rel, OUT_REL + "/")
        except OSError as exc:
            log(f"  !! anime: could not remove stale {rel}: {exc}")
    for rel in sorted(_cast_output_textures(old_info) - _cast_output_textures(new_info)):
        try:
            removed += _remove_generated(C.OUT_TEXTURES, rel, TEX_REL + "/")
        except OSError as exc:
            log(f"  !! anime: could not remove stale {rel}: {exc}")
    if removed:
        log(f"  anime: removed {removed} stale generated file(s)")
    return removed


def build(log=print, only=None):
    """Every cast member, grouped by skeleton: all members built on the same base model (or the procedural
    fallback rig) share one skeleton, one set of A_Anime_<Group>_<State> takes and one duel disk.

    With ``only`` (a list of cast ids) only those members (plus the player) are rebuilt, but the
    published cast.json still describes the whole cast: the rebuilt ``groups`` / ``meshes`` /
    ``materials`` entries overwrite their previous ones and the untouched members keep theirs
    (merge_partial_manifests), so the importer's stale-cast cleanup never deletes assets that are
    still on disk and still in the manifest.  A partial build also skips stale-file pruning for the
    same reason."""
    from .. import blend
    out_dir = os.path.join(C.OUT_DIR, OUT_REL)
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(os.path.join(C.OUT_TEXTURES, TEX_REL), exist_ok=True)
    # Keep the previous manifest until the new one is complete: the individual
    # FBX/PNG writers are atomic, and stale files are pruned below only after
    # cast.json has been replaced.
    old_info = None
    old_info_error = None
    cast_path = os.path.join(C.OUT_DATA, "cast.json")
    if os.path.exists(cast_path):
        try:
            old_info = jsonio.read_json(cast_path)
        except (OSError, ValueError) as exc:
            old_info_error = exc
            log(f"  !! anime: previous cast.json unreadable ({exc}); stale files will not be pruned")
    entries = CAST.all_entries()
    order = [CAST.PLAYER] + [c for c in entries if c != CAST.PLAYER]
    if only:
        order = [c for c in order if c in only or c == CAST.PLAYER]
    groups = {}
    for cid in order:
        e = entries[cid]
        g = key_name(e["model"]) if M.model_available(e) else PROCEDURAL
        groups.setdefault(g, []).append(cid)
    info = dict(player=CAST.PLAYER, groups={}, meshes={}, materials={})
    used = set()
    for group, cids in groups.items():
        blend.reset_scene()
        bpy.context.scene.render.fps = 30
        if group == PROCEDURAL:
            arm = S.create("root")
            built = []
            for cid in cids:
                built.append((cid, arm, build_character(cid, entries[cid], arm)))
        else:
            # Build every member once, then merge their helper bones into the first member's
            # armature and export all meshes on that one union skeleton.
            built = []
            for cid in cids:
                a, obj = M.build_model(cid, entries[cid], key_name, log)
                built.append((cid, a, obj))
            arm = built[0][1]
            for cid, a, obj in built[1:]:
                _merge_rig(arm, a, obj, log)
                bpy.data.objects.remove(a, do_unlink=True)
        g = dict(skeleton_mesh=None, anims=_export_takes(arm, group, out_dir, log))
        disk = build_disk(arm, f"SK_Anime_{group}_DuelDisk")
        export_skeletal([arm, disk], arm, os.path.join(out_dir, disk.name + ".fbx"), {"ARMATURE", "MESH"},
                        deform_only=False)
        g["duel_disk"] = dict(name=disk.name, file=f"{OUT_REL}/{disk.name}.fbx",
                              materials=[s.material.name for s in disk.material_slots if s.material])
        used.update(g["duel_disk"]["materials"])
        bpy.data.objects.remove(disk, do_unlink=True)
        for cid, a, obj in built:
            e = entries[cid]
            name = obj.name
            mats = [s.material.name for s in obj.material_slots if s.material]
            used.update(mats)
            entry = dict(name=name, group=group, display=e["name"], dorm=e["dorm"], scale=e.get("scale", 1.0),
                         tint=e.get("tint", []), female=bool(e.get("body", {}).get("female")), materials=mats)
            # every member is tailored / restyled individually: one FBX each, all on the group's
            # union skeleton (the first member's import creates it in Unreal, all others reuse it)
            export_skeletal([arm, obj], arm, os.path.join(out_dir, f"{name}.fbx"), {"ARMATURE", "MESH"},
                            deform_only=False)
            entry["file"] = f"{OUT_REL}/{name}.fbx"
            info["meshes"][cid] = entry
            g["skeleton_mesh"] = g["skeleton_mesh"] or name
            log(f"  anime: {name:24s} [{group}] {K.tri_count(obj):6d} tris, {len(mats)} materials")
            bpy.data.objects.remove(obj, do_unlink=True)
        info["groups"][group] = g
    mats = palette.material_json()
    info["materials"] = {k: mats[k] for k in sorted(used) if k in mats}
    # A partial build publishes the FULL manifest (rebuilt subset merged into the
    # previous document); publishing the subset alone would tell the importer
    # that every untouched member no longer exists and make it delete those
    # assets on the next import.
    if only is not None and old_info is None and old_info_error is not None:
        raise RuntimeError(
            f"partial cast build could not read the previous cast.json ({old_info_error}); "
            "the rebuilt subset alone would describe less of the cast than the importer expects - "
            "run a full build (python Tools/build_island.py cast) to republish the whole manifest")
    published = info if only is None else MANIFEST.merge_partial_manifests(old_info, info)
    if only is not None and not isinstance(old_info, dict):
        log("  !! anime: no previous cast.json to merge the partial build into; "
            "the published manifest only covers its rebuilt members")
    os.makedirs(C.OUT_DATA, exist_ok=True)
    jsonio.write_json(cast_path, published, indent=1)
    if only is None:
        try:
            _prune_previous_outputs(old_info, info, log)
        except Exception as exc:  # noqa: BLE001 - cleanup must not fail a successful export
            log(f"  !! anime: stale-file cleanup failed ({exc}); files left in place")
    annotate_layout(log)
    return published


def annotate_layout(log=print):
    """Assign cast members / generic looks to the NPC markers of an existing layout.json."""
    path = os.path.join(C.OUT_DATA, "layout.json")
    if not os.path.exists(path):
        return
    layout = jsonio.read_json(path)
    CAST.assign_npcs(layout.get("npcs", []))
    jsonio.write_json(path, layout, separators=(",", ":"))
    named = [n["cast"] for n in layout.get("npcs", []) if n.get("cast") and not n.get("tint", True)]
    log(f"  anime: layout.json npcs cast ({len(named)} named: {', '.join(named)})")


# --------------------------------------------------------------------------- preview render
def render_lineup(path, ids=None, state="Idle", frame=12, res=(1800, 720), samples=32, view=0.0, log=print,
                  portrait=False):
    """Cycles toon render of the cast standing in a row (for Docs/renders and quick iteration). portrait: a
    head-and-shoulders close-up of the first character instead (to compare with official portraits)."""
    import math
    from .. import blend
    blend.reset_scene()
    scene = bpy.context.scene
    scene.render.fps = 30
    entries = CAST.all_entries()
    ids = ids or list(CAST.CAST)
    src_key = dict((s, k) for s, k, _ in TAKES).get(state)
    src = spec = None
    if src_key:
        spec = thirdparty.registry().get("anime", {}).get(src_key)
        if spec is not None:
            src = RT.Source(thirdparty.tp_path(spec["file"]))
        else:
            log(f"  !! anime: no source registered for {src_key}; rendering the rest pose")
    shared = None
    spacing = 0.85
    for i, cid in enumerate(ids):
        e = entries[cid]
        if M.model_available(e):
            a, obj = M.build_model(cid, e, key_name)
            act = None
        else:
            if shared is None:
                shared = S.create("root")
                a = shared
            else:
                a = shared.copy()
                a.data = shared.data
                scene.collection.objects.link(a)
            obj = build_character(cid, e, a)
        if src is not None:
            act = RT.bake(src, spec["take"], a, f"{src_key}_{cid}", arm_drop=spec.get("arm_drop", 0.0))
        elif state in AUTHORED:
            act = RT.pose_action(a, f"pose_{cid}", AUTHORED[state][0](a))
        RT._assign(a, act)
        sc = e.get("scale", 1.0)
        a.location = ((i - (len(ids) - 1) / 2) * spacing, 0.0, 0.0)
        a.scale = (sc, sc, sc)
        obj.parent = a
    if src is not None:
        src.remove()
    scene.frame_set(frame)
    for o in scene.objects:
        if o.type == "MESH":
            o.visible_shadow = True
    blend.setup_render(res, samples, scene)
    scene.view_settings.view_transform = "Standard"     # flat anime colours, no filmic desaturation
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("cast")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.62, 0.74, 0.92, 1.0)
    bg.inputs[1].default_value = 0.9
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 2.6
    sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(48), 0, math.radians(-22))
    scene.collection.objects.link(sun)
    ground = bpy.data.meshes.new("ground")
    ground.from_pydata([(-20, -20, 0), (20, -20, 0), (20, 20, 0), (-20, 20, 0)], [], [(0, 1, 2, 3)])
    g = bpy.data.objects.new("ground", ground)
    gm = bpy.data.materials.new("groundmat")
    gm.diffuse_color = (0.55, 0.62, 0.45, 1)
    gm.use_nodes = True
    gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.50, 0.26, 1)
    ground.materials.append(gm)
    scene.collection.objects.link(g)
    width = len(ids) * spacing
    dist = max(3.6, width * 1.45)
    a = math.radians(view)
    if portrait:
        first = next(o for o in scene.objects if o.type == "ARMATURE")
        bpy.context.view_layer.update()
        head = first.matrix_world @ first.pose.bones["head"].head          # posed (the take moves the hips)
        bust = portrait == "bust"                    # head and chest (uniform details) instead of the face
        tgt = (head.x, head.y, head.z + (-0.12 if bust else 0.08) * first.scale.z)   # the head bone sits at the jaw
        d = 1.45 if bust else 0.9
        cam = blend.camera("cam", (tgt[0] + math.sin(a) * d, -math.cos(a) * d, tgt[2]), tgt, lens=50.0)
    else:
        cam = blend.camera("cam", (math.sin(a) * dist, -math.cos(a) * dist, 1.25), (0.0, 0.0, 0.92), lens=50.0)
    blend.render(cam, path)
    log(f"  lineup -> {path}")
