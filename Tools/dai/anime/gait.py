"""
Biomechanical walk / run / idle cycles for the anime cast skeleton (skeleton.py).

The walk and run takes are *not* retargeted from a source clip: every frame is solved from a
gait model, so the foot plants exactly on the ground while the body travels at the authored
speed, and the rest of the body follows the mechanics of human locomotion:

  * stance feet follow a contact path that moves backwards at the locomotion speed
    (heel strike -> foot flat -> heel off -> toe off), with the shoe rolling about the heel
    and then the ball and the toe joint staying flat on the ground;
  * two-bone leg IK from the moving hip to the ankle target, so the knees bend naturally and
    never hyper-extend; the pelvis height is the highest one that still lets the stance leg
    reach the ground (a natural pelvis bob, lowest at double support, highest at mid stance),
  * pelvis yaw / list / sway, counter-rotating shoulders and spine, forward lean, stabilised
    head, opposing arm swing with elbow flexion and relaxed wrists;
  * running gets a real flight phase, a spring-like stance compression, a high heel recovery
    and a stronger forward lean; walking keeps double support with the foot flat under the
    body.

All cycles are periodic (frame 0 and frame N are identical) and measured with the same contact
test the runtime uses. `validate` reports the measured ground speed, foot penetration, contact
quality, knee range and loop error; build.py bakes the takes and logs the result.
"""

import math
from dataclasses import dataclass, field

from mathutils import Euler, Matrix, Vector

from . import skeleton as S

FPS = 30


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _lerp(a, b, t):
    return a + (b - a) * t


def _lerp_vec(a, b, t):
    return Vector(a) + (Vector(b) - Vector(a)) * t


def _rx(deg, v):
    """Rotate v about the character's lateral axis (+X): positive = toe down."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return Vector((v.x, v.y * c - v.z * s, v.y * s + v.z * c))


@dataclass
class Gait:
    """Parameters of one locomotion cycle. Speeds in metres, cycle time in seconds, angles deg."""

    name: str
    speed: float               # ground speed (m/s)
    cycle: float               # duration of one full cycle (two steps)
    duty: float                # stance fraction of the cycle (< 0.5: flight phases)
    contact_y: float           # contact point Y at heel strike (m; the character faces -Y)
    heel_angle: float          # toe-up angle at heel strike
    heel_flat: float           # phase fraction where the foot becomes flat
    heel_off: float            # phase fraction where the heel starts to rise
    push_angle: float          # toe-down angle at toe-off
    swing_lift: float          # extra ankle height mid-swing
    swing_toe: float           # extra toe-up during swing
    lean: float                # forward lean (deg)
    pelvis_yaw: float
    pelvis_roll: float
    shoulder_yaw: float
    trunk_roll: float
    sway: float                # lateral pelvis shift
    knee_margin: float         # minimum knee flex (shortens the leg)
    toe_out: float
    profile: tuple = field(default_factory=tuple)

    @property
    def stride(self):
        return self.speed * self.cycle

    @property
    def step(self):
        return self.stride * 0.5

    @property
    def frames(self):
        return int(round(self.cycle * FPS))


# Authored at human scale (1.7 m cast): a normal walk and a solid distance run.
WALK = Gait(
    name="Walk", speed=1.50, cycle=0.80, duty=0.58, contact_y=-0.300,
    heel_angle=15.0, heel_flat=0.10, heel_off=0.40, push_angle=42.0,
    swing_lift=0.105, swing_toe=13.0,
    lean=2.4, pelvis_yaw=4.0, pelvis_roll=3.0, shoulder_yaw=5.0, trunk_roll=1.5,
    sway=0.018, knee_margin=0.012, toe_out=6.0,
    profile=((0.00, 0.860), (0.25, 0.930), (0.50, 0.860), (0.75, 0.930), (1.00, 0.860)),
)

RUN = Gait(
    name="Run", speed=4.20, cycle=14.0 / FPS, duty=0.30, contact_y=-0.105,
    heel_angle=3.0, heel_flat=0.055, heel_off=0.16, push_angle=52.0,
    swing_lift=0.255, swing_toe=7.0,
    lean=6.5, pelvis_yaw=8.0, pelvis_roll=4.0, shoulder_yaw=11.0, trunk_roll=2.2,
    sway=0.011, knee_margin=0.055, toe_out=3.0,
    profile=((0.00, 0.880), (0.15, 0.842), (0.26, 0.840), (0.31, 0.855),
             (0.405, 0.940), (0.50, 0.880), (0.65, 0.842), (0.76, 0.840),
             (0.81, 0.855), (0.905, 0.940), (1.00, 0.880)),
)

IDLE_PERIOD = 3.0


# --------------------------------------------------------------------------- rig helpers
class Rig:
    def __init__(self, arm):
        self.arm = arm
        self.rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
        self.rest_q = {n: m.to_3x3().normalized().to_quaternion() for n, m in self.rest.items()}
        self.length = {b.name: float(b.length) for b in arm.data.bones}
        self.joint = {n: m.translation.copy() for n, m in self.rest.items()}
        # Limb segments are measured between joint heads, not along the (arbitrary) bone tails:
        # the VRoid cast skeletons keep display tails pointing up even though the limb hangs down.
        self.seg = {}
        for parent, child in (
            ("thigh_l", "calf_l"), ("thigh_r", "calf_r"),
            ("calf_l", "foot_l"), ("calf_r", "foot_r"),
            ("upperarm_l", "lowerarm_l"), ("upperarm_r", "lowerarm_r"),
            ("lowerarm_l", "hand_l"), ("lowerarm_r", "hand_r"),
        ):
            d = self.joint[child] - self.joint[parent]
            self.seg[parent] = d.normalized()
            self.length[parent] = d.length
        self.thigh = self.length["thigh_l"]
        self.calf = self.length["calf_l"]
        self.upperarm = self.length["upperarm_l"]
        self.lowerarm = self.length["lowerarm_l"]
        self.leg = self.thigh + self.calf
        # Shoe geometry, read from the rest skeleton and scaled by the foot length.
        self.foot_x = {"l": self.joint["foot_l"].x, "r": self.joint["foot_r"].x}
        self.ankle_z = self.joint["foot_l"].z
        self.ball_z = self.joint["ball_l"].z
        self.ball_offset = self.joint["ball_l"] - self.joint["foot_l"]
        canon_foot = 0.1185
        s = max(0.5, min(2.0, self.ball_offset.length / canon_foot))
        self.heel_back = 0.075 * s
        self.toe_len = 0.085 * s
        # Locomotion poses are authored around the canonical 1.70 m skeleton; scale vertical
        # targets by the target rig's pelvis height so proportionally taller bases do not crouch.
        self.height_scale = self.joint["pelvis"].z / S.PELVIS

    def pelvis(self, offset, rot):
        pos = self.rest["pelvis"].translation + Vector(offset)
        q = Euler(tuple(math.radians(v) for v in rot), "XYZ").to_quaternion() @ self.rest_q["pelvis"]
        return Matrix.Translation(pos) @ q.to_matrix().to_4x4()

    def hip(self, pelvis_world, side):
        return (pelvis_world @ self.rest["pelvis"].inverted()
                @ self.rest[f"thigh_{side}"]).translation

    def upper_world(self, pelvis_world, upper):
        """World matrices of the spine chain and clavicles for the given absolute Euler offsets."""
        world = {"pelvis": pelvis_world}
        for bname in ("spine_01", "spine_02", "spine_03", "neck_01", "head"):
            b = self.arm.data.bones[bname]
            p = b.parent.name
            pos = (world[p] @ self.rest[p].inverted() @ self.rest[bname]).translation
            q = Euler(tuple(math.radians(v) for v in upper[bname]), "XYZ").to_quaternion() @ self.rest_q[bname]
            world[bname] = Matrix.Translation(pos) @ q.to_matrix().to_4x4()
        for side in ("l", "r"):
            clav = f"clavicle_{side}"
            p = self.arm.data.bones[clav].parent.name
            pos = (world[p] @ self.rest[p].inverted() @ self.rest[clav]).translation
            q = (world[p].to_quaternion() @ self.rest_q[p].inverted() @ self.rest_q[clav])
            world[clav] = Matrix.Translation(pos) @ q.to_matrix().to_4x4()
        return world

    def shoulder(self, upper_world, side):
        clav = f"clavicle_{side}"
        return (upper_world[clav] @ self.rest[clav].inverted()
                @ self.rest[f"upperarm_{side}"]).translation

    def pose_arm(self, side, shoulder, wrist, bend_dir):
        """Two-bone arm IK -> (upperarm target direction, forearm target direction)."""
        l1, l2 = self.upperarm, self.lowerarm
        d = wrist - shoulder
        dist = max(d.length, 1e-6)
        max_len = l1 + l2 - 1e-5
        if dist > max_len:
            wrist = shoulder + d * (max_len / dist)
            d = wrist - shoulder
            dist = max_len
        n = d.normalized()
        bend = Vector(bend_dir) - n * Vector(bend_dir).dot(n)
        if bend.length < 1e-4:
            bend = Vector((1.0 if side == "l" else -1.0, 0.0, 0.0))
        bend.normalize()
        cos_a = (l1 * l1 + dist * dist - l2 * l2) / (2.0 * l1 * dist)
        cos_a = max(-1.0, min(1.0, cos_a))
        sin_a = math.sqrt(max(0.0, 1.0 - cos_a * cos_a))
        elbow = shoulder + n * (l1 * cos_a) + bend * (l1 * sin_a)
        return (elbow - shoulder).normalized(), (wrist - elbow).normalized()

    def pose_leg(self, side, hip, ankle):
        """Two-bone IK -> (thigh target direction, calf target direction)."""
        s = 1.0 if side == "l" else -1.0
        d = ankle - hip
        dist = max(d.length, 1e-6)
        max_len = self.leg - 1e-5
        clamped = dist > max_len
        if clamped:
            ankle = hip + d * (max_len / dist)
            d = ankle - hip
            dist = max_len
        n = d.normalized()
        forward = Vector((0.0, -1.0, 0.0))
        bend = forward - n * forward.dot(n)
        if bend.length < 1e-4:
            bend = Vector((0.0, -1.0, 0.0))
        bend = (bend.normalized() + Vector((s * 0.055, 0.0, 0.0))).normalized()
        cos_a = (self.thigh * self.thigh + dist * dist - self.calf * self.calf) / (2.0 * self.thigh * dist)
        cos_a = max(-1.0, min(1.0, cos_a))
        sin_a = math.sqrt(max(0.0, 1.0 - cos_a * cos_a))
        knee = hip + n * (self.thigh * cos_a) + bend * (self.thigh * sin_a)
        return (knee - hip).normalized(), (ankle - knee).normalized(), clamped


# --------------------------------------------------------------------------- gait model
def _curve(profile, phase):
    """Periodic piecewise smoothstep through (phase, value) control points."""
    p = phase % 1.0
    pts = list(profile)
    for i in range(len(pts) - 1):
        p0, v0 = pts[i]
        p1, v1 = pts[i + 1]
        if p0 <= p <= p1:
            if p1 <= p0:
                return v1
            return _lerp(v0, v1, _smooth((p - p0) / (p1 - p0)))
    return pts[-1][1]


def _foot(rig, gait, phase, side):
    """Return (ankle target, foot pitch, ball pitch, in_stance) for one leg.

    The contact point travels backwards at the authored speed during stance; the ankle is
    placed above it so the heel, sole or ball is exactly on the ground. The shoe dimensions
    come from the target rig, so the same gait plants on the VRoid cast and on the fallback
    skeleton.
    """
    lp = (phase + (0.0 if side == "l" else 0.5)) % 1.0
    fx = rig.foot_x[side]
    heel_off_v = Vector((0.0, rig.heel_back, -rig.ankle_z))
    ball_off_v = Vector((rig.ball_offset.x, rig.ball_offset.y, rig.ball_offset.z))
    stride = gait.stride

    def stance_foot(p):
        # Contact point (heel during heel roll, then the sole reference, then the ball).
        # The character faces -Y, so a planted foot travels +Y (backwards) at the ground speed.
        h = gait.contact_y + stride * p
        if p <= gait.heel_flat:
            th = -gait.heel_angle * (1.0 - _smooth(p / max(gait.heel_flat, 1e-6)))
            heel = Vector((fx, h, 0.0))
            ankle = heel - _rx(th, heel_off_v)
            return ankle, th, th
        if p <= gait.heel_off:
            ankle = Vector((fx, h - rig.heel_back, rig.ankle_z))
            return ankle, 0.0, 0.0
        t = (p - gait.heel_off) / max(gait.duty - gait.heel_off, 1e-6)
        th = gait.push_angle * _smooth(t)
        ball = Vector((fx + ball_off_v.x, h - rig.heel_back + ball_off_v.y, rig.ball_z))
        ankle = ball - _rx(th, ball_off_v)
        return ankle, th, 0.0

    if lp < gait.duty:
        ankle, pitch, ball = stance_foot(lp)
        return ankle, pitch, ball, True

    # Swing: start at toe-off, end at the next heel strike.
    a0, p0, _ = stance_foot(gait.duty)
    a1, p1, _ = stance_foot(0.0)
    t = (lp - gait.duty) / max(1.0 - gait.duty, 1e-6)
    e = _smooth(t)
    ankle = _lerp_vec(a0, a1, e)
    ankle.z += gait.swing_lift * math.sin(math.pi * t) ** 0.85
    pitch = _lerp(p0, p1, e) - gait.swing_toe * math.sin(math.pi * t)
    ball = pitch * _smooth(min(1.0, t / 0.16))
    return ankle, pitch, ball, False


def _pelvis_base(gait, phase):
    if gait.name == "Run":
        return _curve(gait.profile, phase)
    if gait.name == "Walk":
        return 0.895 - 0.035 * math.cos(4.0 * math.pi * phase)
    return 0.92


def _wrist_target(rig, gait, phase, side, shoulder, idle=False):
    s = 1.0 if side == "l" else -1.0
    c = math.cos(2.0 * math.pi * phase)
    hs = rig.height_scale
    if idle or gait.name == "Idle":
        y = 0.010 * math.sin(2.0 * math.pi * phase + (0.6 if s > 0 else 1.7))
        z = shoulder.z - 0.455 * hs
        x = shoulder.x + s * 0.050 * hs
    elif gait.name == "Run":
        fwd = -s * c
        y = s * 0.180 * c
        z = shoulder.z - (0.330 - 0.150 * (0.5 + 0.5 * fwd)) * hs
        x = shoulder.x + s * 0.030 * hs
    else:
        y = s * 0.150 * c
        z = shoulder.z - 0.450 * hs
        x = shoulder.x + s * 0.055 * hs
    return Vector((x, y, z))


def _hand_dir(fore, wrist_deg=10.0):
    down = Vector((0.0, 0.0, -1.0)) - fore * fore.dot(Vector((0.0, 0.0, -1.0)))
    if down.length < 1e-4:
        down = Vector((0.0, -1.0, 0.0))
    down.normalize()
    a = math.radians(wrist_deg)
    return (fore * math.cos(a) + down * math.sin(a)).normalized()


def _upper_body(gait, phase):
    """Absolute world-space Euler offsets (deg) for pelvis, spine, neck and head."""
    c = math.cos(2.0 * math.pi * phase)
    s = math.sin(2.0 * math.pi * phase)
    yaw_p = -gait.pelvis_yaw * c
    yaw_s = gait.shoulder_yaw * c
    roll_p = -gait.pelvis_roll * s
    roll_s = gait.trunk_roll * s
    lean = gait.lean
    out = {
        "pelvis": (lean * 0.16, roll_p, yaw_p),
        "spine_01": (lean * 0.30, roll_s * 0.45, yaw_s * 0.22),
        "spine_02": (lean * 0.55, roll_s * 0.80, yaw_s * 0.58),
        "spine_03": (lean * 0.92, roll_s, yaw_s),
        "neck_01": (lean * 0.28, roll_s * 0.2, yaw_s * 0.55),
        "head": (-lean * 0.18 + 0.4 * math.sin(2.0 * math.pi * phase * 2.0),
                 -roll_s * 0.25, yaw_s * 0.10 - 0.8 * math.sin(2.0 * math.pi * phase * 0.5)),
    }
    return out


def _frame(rig, gait, phase, idle=False):
    """Solve all bone targets for one phase. Returns (key dict, metrics)."""
    if idle:
        # Relaxed standing: feet planted, slow weight shift and breathing.
        a = 2.0 * math.pi * phase
        gait = IDLE
        sway = 0.0075 * math.sin(a)
        yaw = 1.3 * math.sin(a + 0.4)
        roll = -1.1 * math.sin(a)
        lean = 1.2 + 0.25 * math.sin(a * 2.0)
        base = 0.918 + 0.0018 * math.sin(a * 2.0)
        base *= rig.height_scale
        pelvis_rot = (lean * 0.16, roll, yaw)
        feet = {side: (Vector((rig.foot_x[side], rig.joint[f"foot_{side}"].y, rig.ankle_z)), 0.0, 0.0,
                       True) for side in ("l", "r")}
        pelvis_x = sway * rig.height_scale
        upper = {
            "pelvis": (lean * 0.16, roll, yaw),
            "spine_01": (lean * 0.30, -roll * 0.45, -yaw * 0.20),
            "spine_02": (lean * 0.55 + 0.35 * math.sin(a * 2.0), -roll * 0.80, -yaw * 0.55),
            "spine_03": (lean * 0.92 + 0.45 * math.sin(a * 2.0), -roll, -yaw * 0.85),
            "neck_01": (lean * 0.25, -roll * 0.15, -yaw * 0.4),
            "head": (-lean * 0.10, roll * 0.15, -yaw * 0.05 + 2.5 * math.sin(a + 0.6)),
        }
        return _assemble(rig, gait, phase, pelvis_x, base, pelvis_rot, feet, upper, idle=True)

    base = _pelvis_base(gait, phase) * rig.height_scale
    sway = gait.sway * math.sin(2.0 * math.pi * phase) * rig.height_scale
    upper = _upper_body(gait, phase)
    pelvis_rot = upper["pelvis"]
    feet = {side: _foot(rig, gait, phase, side) for side in ("l", "r")}

    # The pelvis must be low enough for every stance foot. Compute each hip position with a
    # pelvis at z=0; the rotation does not change when the pelvis slides vertically.
    tmp = rig.pelvis((sway, 0.0, 0.0), pelvis_rot)
    limit = 1e9
    for side, (ankle, pitch, ball, stance) in feet.items():
        if not stance:
            continue
        hip = rig.hip(tmp, side)
        dz = hip.z - tmp.translation.z
        horiz2 = (hip.x - ankle.x) ** 2 + (hip.y - ankle.y) ** 2
        reach = rig.leg - max(0.0, gait.knee_margin * (0.4 + 0.6 * math.sin(math.pi * min(1.0, phase / max(gait.duty, 1e-6)))))
        if horiz2 >= reach * reach:
            horiz2 = (reach * 0.995) ** 2
        limit = min(limit, ankle.z - dz + math.sqrt(max(0.0, reach * reach - horiz2)))
    if limit < 1e8:
        base = min(base, limit - 0.002)
    if base < S.PELVIS - 0.22:
        base = S.PELVIS - 0.22

    return _assemble(rig, gait, phase, sway, base, pelvis_rot, feet, upper)


def _assemble(rig, gait, phase, pelvis_x, pelvis_z, pelvis_rot, feet, upper, idle=False):
    offset = pelvis_z - rig.joint["pelvis"].z
    pelvis_world = rig.pelvis((pelvis_x, 0.0, offset), pelvis_rot)
    key = {"_pelvis_offset": (pelvis_x, 0.0, offset)}
    for bname, rot in upper.items():
        key[bname] = rot
    clamped = 0
    for side in ("l", "r"):
        ankle, pitch, ball, stance = feet[side]
        hip = rig.hip(pelvis_world, side)
        thigh, calf, was_clamped = rig.pose_leg(side, hip, ankle)
        clamped += int(was_clamped)
        key[f"thigh_{side}"] = {"seg": tuple(thigh), "rest": tuple(rig.seg[f"thigh_{side}"])}
        key[f"calf_{side}"] = {"seg": tuple(calf), "rest": tuple(rig.seg[f"calf_{side}"])}
        key[f"foot_{side}"] = (pitch, 0.0, (1 if side == "l" else -1) * gait.toe_out)
        key[f"ball_{side}"] = (ball, 0.0, (1 if side == "l" else -1) * gait.toe_out)

    upper_world = rig.upper_world(pelvis_world, upper)
    for side, s in (("l", 1.0), ("r", -1.0)):
        shoulder = rig.shoulder(upper_world, side)
        wrist = _wrist_target(rig, gait, phase, side, shoulder, idle)
        bend_dir = (s * 0.14, 0.42, -1.0) if gait.name != "Idle" else (s * 0.10, 0.22, -1.0)
        up_dir, fore_dir = rig.pose_arm(side, shoulder, wrist, bend_dir)
        h = _hand_dir(fore_dir, 14.0 if gait.name == "Run" else 10.0)
        key[f"upperarm_{side}"] = {"seg": tuple(up_dir), "rest": tuple(rig.seg[f"upperarm_{side}"])}
        key[f"lowerarm_{side}"] = {"seg": tuple(fore_dir), "rest": tuple(rig.seg[f"lowerarm_{side}"])}
        key[f"hand_{side}"] = {"seg": tuple(h), "rest": tuple(rig.seg[f"lowerarm_{side}"])}
    return key, {"clamped": clamped, "pelvis_z": pelvis_z, "feet": feet}


def _keys(rig, gait, idle=False):
    if not isinstance(rig, Rig):
        rig = Rig(rig)
    n = int(round(IDLE_PERIOD * FPS)) if idle else gait.frames
    out = []
    for i in range(n + 1):
        phase = (i / n) % 1.0
        key, _ = _frame(rig, gait, phase, idle=idle)
        out.append((i, key))
    return out


# IDLE is a Gait instance used by _frame; its profile is not used but the fields keep the
# assemble helpers simple.
IDLE = Gait(
    name="Idle", speed=0.0, cycle=IDLE_PERIOD, duty=1.0, contact_y=0.0,
    heel_angle=0.0, heel_flat=0.0, heel_off=0.0, push_angle=0.0,
    swing_lift=0.0, swing_toe=0.0,
    lean=1.2, pelvis_yaw=0.0, pelvis_roll=0.0, shoulder_yaw=0.0, trunk_roll=0.0,
    sway=0.0, knee_margin=0.012, toe_out=5.0,
)


def walk_keys(rig=None):
    return _keys(rig, WALK)


def run_keys(rig=None):
    return _keys(rig, RUN)


def idle_keys(rig=None):
    return _keys(rig, IDLE, idle=True)


# --------------------------------------------------------------------------- validation
def _contact_points(arm, rig, side, rest):
    """World heel / ball / toe points of the posed shoe, using the actual bone matrices and
    the shoe dimensions measured from the rest skeleton."""
    foot = arm.pose.bones[f"foot_{side}"]
    ball = arm.pose.bones[f"ball_{side}"]
    fy = rig.joint[f"foot_{side}"].y
    by = rig.joint[f"ball_{side}"].y
    bx = rig.joint[f"ball_{side}"].x
    heel = Vector((rig.foot_x[side], fy + rig.heel_back, 0.0))
    ball_sole = Vector((bx, by, 0.0))
    toe = Vector((bx, by - rig.toe_len, 0.0))
    h = arm.matrix_world @ foot.matrix @ rest[f"foot_{side}"].inverted() @ heel
    b = arm.matrix_world @ ball.matrix @ rest[f"ball_{side}"].inverted() @ ball_sole
    t = arm.matrix_world @ ball.matrix @ rest[f"ball_{side}"].inverted() @ toe
    return h, b, t


def validate(arm, action, gait, log=print, raise_on_error=True):
    """Check foot planting, penetration, loop closure and knee range of a baked gait take."""
    from . import retarget as RT
    scene = bpy.context.scene
    rig = Rig(arm)
    RT._assign(arm, action)
    f0, f1 = (int(round(v)) for v in action.frame_range)
    rest = {b.name: b.matrix_local.copy() for b in arm.data.bones}
    ys, zs = {"l": [], "r": []}, []
    knee_min, knee_max = 180.0, 0.0
    pelvis_z = []
    for f in range(f0, f1 + 1):
        scene.frame_set(f)
        frame_z = []
        for side in ("l", "r"):
            h, b, t = _contact_points(arm, rig, side, rest)
            frame_z += [h.z, b.z, t.z]
            ys[side].append((h.y, b.y, t.y, min(h.z, b.z, t.z)))
            th = arm.pose.bones[f"calf_{side}"].head - arm.pose.bones[f"thigh_{side}"].head
            cf = arm.pose.bones[f"foot_{side}"].head - arm.pose.bones[f"calf_{side}"].head
            knee_min = min(knee_min, math.degrees(th.angle(cf)))
            knee_max = max(knee_max, math.degrees(th.angle(cf)))
        zs.append(min(frame_z))
        pelvis_z.append((arm.matrix_world @ arm.pose.bones["pelvis"].head).z)
    dur = max(1, f1 - f0) / scene.render.fps
    # Ground speed: median backward velocity of the lowest contact point while it is planted.
    speeds = []
    for side in ("l", "r"):
        for i in range(len(ys[side]) - 1):
            z0 = ys[side][i][3]
            z1 = ys[side][i + 1][3]
            if z0 < 0.012 and z1 < 0.012:
                speeds.append(max(ys[side][i + 1][0] - ys[side][i][0],
                                  ys[side][i + 1][1] - ys[side][i][1],
                                  ys[side][i + 1][2] - ys[side][i][2]) * scene.render.fps)
    speeds = [v for v in speeds if v > 0.05]
    measured = sorted(speeds)[len(speeds) // 2] if speeds else 0.0
    penetration = min(zs) * 1000.0
    contact = 100.0 * sum(1 for z in zs if z < 0.015) / len(zs)
    # Loop closure: compare every bone transform at the first and last frame.
    scene.frame_set(f0)
    first = {b.name: arm.pose.bones[b.name].matrix.copy() for b in arm.data.bones}
    scene.frame_set(f1)
    loop = 0.0
    for b in arm.data.bones:
        a = first[b.name]
        c = arm.pose.bones[b.name].matrix
        loop = max(loop, (a.translation - c.translation).length)
        loop = max(loop, math.degrees(a.to_quaternion().rotation_difference(c.to_quaternion()).angle))
    RT._assign(arm, None)
    ok = (penetration > -9.0 and contact > (64.0 if gait.name == "Run" else 78.0) and
          measured > gait.speed * 0.92 and measured < gait.speed * 1.08 and loop < 0.002)
    log(f"  gait {gait.name:4s}: {gait.frames} frames, authored {gait.speed:.2f} m/s, "
        f"measured {measured:.2f} m/s, contact {contact:.0f}%, lowest {penetration:.1f} mm, "
        f"knee {knee_min:.0f}-{knee_max:.0f} deg, pelvis {(min(pelvis_z)):.3f}-{max(pelvis_z):.3f} m, "
        f"loop {loop:.4f} {'OK' if ok else 'CHECK'}")
    if raise_on_error and not ok:
        raise RuntimeError(f"gait validation failed for {gait.name}")
    return dict(speed=measured, contact=contact, penetration=penetration, loop=loop,
                knee=(knee_min, knee_max), pelvis=(min(pelvis_z), max(pelvis_z)), ok=ok)


# bpy is imported lazily only in validate so the gait maths can be unit-tested outside Blender.
try:  # pragma: no cover - Blender only
    import bpy  # noqa: F401
except Exception:  # noqa: BLE001
    bpy = None
