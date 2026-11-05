"""
Pose-space corrective morph targets for the clothes (Blender build + the weights formula shared with Unreal).

Linear blend skinning collapses the seat and the front of the hip when a thigh swings far: vertices
shared between the pelvis and a thigh are moved by an average of two rotation matrices, and two layers of
cloth with slightly different weights collapse by different amounts and cross (trousers out through a long
coat at the seat in a stride or a sit). Production rigs fix exactly this with pose-space correctives: shape
keys sculpted for a specific joint pose and faded in by that joint's angle.

Here they are solved instead of sculpted. For each side and each key pose (thigh forward 45 deg, forward
90 deg, back 30 deg, out 30 deg) the mesh is posed, every covered inner vertex that breaks through its
covering garment triangle (fitcheck anchors) is measured, and a rest-space displacement is solved over a few
passes: the covering cloth moves out along the triangle's normal, the layer under it tucks in. The
displacements are stored as point attributes (da_morph_Fit_<Key>_<side>, models.restore_morphs turns them
into morph targets after the join, like the face morphs) - only keys that fix something are kept.

weights() is the driver: from the thigh's direction in the pelvis frame relative to the rest pose it gives
pitch (forward +) and spread (outward +) in degrees and maps them to key weights. Unreal evaluates the same
formula every frame (UDAAvatarAnimInstance::UpdateCorrectives); the fit audit applies it per posed frame, so
what the audit measures is what the game shows.
"""

import math

import bpy
import numpy as np

PREFIX = "Fit_"
# chains of key poses along one motion: (key, angle deg); a pose between two keys blends them (tent weights)
FWD_KEYS = (("HipFwd1", 25.0), ("HipFwd", 50.0), ("HipFwd2", 90.0))      # thigh pitch forward
BACK_KEYS = (("HipBack1", 15.0), ("HipBack", 30.0))                      # thigh pitch backward
OUT_KEYS = (("HipOut", 30.0),)                                          # thigh spread outward
KNEE_KEYS = (("KneeBend1", 60.0), ("KneeBend", 110.0))                  # knee flexion
# key -> (pitch, spread, knee) degrees of the pose it is solved in
KEYS = dict([(k, (a, 0.0, 0.0)) for k, a in FWD_KEYS] + [(k, (-a, 0.0, 0.0)) for k, a in BACK_KEYS] +
            [(k, (0.0, a, 0.0)) for k, a in OUT_KEYS] + [(k, (0.0, 0.0, a)) for k, a in KNEE_KEYS])
SIDES = ("l", "r")
PASSES = 6
CAP = 0.06               # largest displacement of one key (m)
MARGIN = 0.003


# --------------------------------------------------------------------------- the driver (shared with Unreal)
def angles(pelvis_rest, hip_rest, knee_rest, pelvis_pose, hip_pose, knee_pose, side, fwd, up, out_axis):
    """(pitch, spread) in degrees of a thigh: its hip->knee direction in the pelvis frame, posed versus rest,
    measured in the rest pose's sagittal (forward / up) and frontal (outward / up) planes. Matrices are 3x3
    pelvis rotations (armature / component space), vectors 3-tuples; fwd / up / out_axis are the rest-pose
    directions in that space (out_axis points away from the body on that side)."""
    def to_pelvis(m, v):
        return np.asarray(m).T @ np.asarray(v, float)
    k0 = to_pelvis(pelvis_rest, np.subtract(knee_rest, hip_rest))
    k1 = to_pelvis(pelvis_pose, np.subtract(knee_pose, hip_pose))
    f = to_pelvis(pelvis_rest, fwd)
    u = to_pelvis(pelvis_rest, up)
    o = to_pelvis(pelvis_rest, out_axis)

    def ang(k, a):
        return math.degrees(math.atan2(float(k @ a), float(-(k @ u))))
    return ang(k1, f) - ang(k0, f), ang(k1, o) - ang(k0, o)


def _tent(chain, x, out):
    """Piecewise-linear weights of a chain of key angles for x >= 0 (the last key extrapolates to 1.2)."""
    prev = 0.0
    for i, (k, a) in enumerate(chain):
        nxt = chain[i + 1][1] if i + 1 < len(chain) else None
        if x <= prev or (nxt is not None and x >= nxt):
            w = 0.0
        elif x <= a:
            w = (x - prev) / (a - prev)
        elif nxt is None:
            w = min(1.2, x / a)
        else:
            w = (nxt - x) / (nxt - a)
        out[k] = max(0.0, w)
        prev = a


def knee_angle(hip, knee, ankle, hip0, knee0, ankle0):
    """Knee flexion (deg) relative to the rest pose: the angle between thigh and shin directions."""
    def ang(a, b, c):
        u, v = np.subtract(b, a), np.subtract(c, b)
        cs = float(np.dot(u, v) / max(np.linalg.norm(u) * np.linalg.norm(v), 1e-12))
        return math.degrees(math.acos(min(1.0, max(-1.0, cs))))
    return ang(hip, knee, ankle) - ang(hip0, knee0, ankle0)


def weights(pitch, spread, knee=0.0):
    """{key: weight} for a leg's thigh (pitch, spread) and knee flexion in degrees."""
    out = {}
    _tent(FWD_KEYS, max(0.0, pitch), out)
    _tent(BACK_KEYS, max(0.0, -pitch), out)
    _tent(OUT_KEYS, max(0.0, spread), out)
    _tent(KNEE_KEYS, max(0.0, knee), out)
    return out


# Blender armature space: the cast faces -Y, +X is the character's left
FWD, UP = (0.0, -1.0, 0.0), (0.0, 0.0, 1.0)
OUT = {"l": (1.0, 0.0, 0.0), "r": (-1.0, 0.0, 0.0)}


def blender_weights(arm):
    """{shape key name: weight} for the armature's current pose (used by the fit audit)."""
    pb, db = arm.pose.bones, arm.data.bones
    out = {}
    for s in SIDES:
        if f"thigh_{s}" not in pb or f"calf_{s}" not in pb:
            continue
        pitch, spread = angles(np.array(db["pelvis"].matrix_local.to_3x3()), db[f"thigh_{s}"].head_local,
                               db[f"calf_{s}"].head_local, np.array(pb["pelvis"].matrix.to_3x3().normalized()),
                               pb[f"thigh_{s}"].head, pb[f"calf_{s}"].head, s, FWD, UP, OUT[s])
        knee = knee_angle(pb[f"thigh_{s}"].head, pb[f"calf_{s}"].head, pb[f"foot_{s}"].head,
                          db[f"thigh_{s}"].head_local, db[f"calf_{s}"].head_local, db[f"foot_{s}"].head_local)
        for k, w in weights(pitch, spread, knee).items():
            out[f"{PREFIX}{k}_{s}"] = w
    return out


def displacement(obj, arm):
    """Rest-space displacement of the solved (still attribute-stored) correctives for the current pose, or
    None - lets the second fit relaxation pass see the correctives before they become morph targets."""
    from .models import MORPH_ATTR
    me = obj.data
    total = None
    for name, w in blender_weights(arm).items():
        if w <= 0:
            continue
        attr = me.attributes.get(MORPH_ATTR + name)
        if attr is None:
            continue
        d = np.empty(len(me.vertices) * 3, np.float32)
        attr.data.foreach_get("vector", d)
        total = d * w if total is None else total + d * w
    return None if total is None else total.reshape(-1, 3)


def apply(obj, arm):
    """Set the corrective shape keys of a built cast mesh for the current pose."""
    keys = obj.data.shape_keys
    if keys is None:
        return
    for name, w in blender_weights(arm).items():
        kb = keys.key_blocks.get(name)
        if kb is not None:
            kb.value = w


# --------------------------------------------------------------------------- solving the keys (build)
def _pose_thigh(arm, side, pitch, spread, knee=0.0):
    """Rest pose with one thigh rotated by (pitch forward, spread outward) degrees about the hip and the shin
    folded back by `knee` degrees about the knee."""
    from mathutils import Matrix
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    pb = arm.pose.bones[f"thigh_{side}"]
    head = pb.head.copy()
    rot = Matrix.Rotation(math.radians(-pitch), 4, "X")                   # knee towards -Y (forward)
    sgn = 1.0 if side == "l" else -1.0
    rot = Matrix.Rotation(math.radians(sgn * spread), 4, "Y") @ rot      # knee outwards
    pb.matrix = Matrix.Translation(head) @ rot @ Matrix.Translation(-head) @ pb.matrix
    bpy.context.view_layer.update()
    if knee:
        cb = arm.pose.bones[f"calf_{side}"]
        kh = cb.head.copy()
        bend = Matrix.Rotation(math.radians(knee), 4, "X")               # foot towards +Y (backwards)
        cb.matrix = Matrix.Translation(kh) @ bend @ Matrix.Translation(-kh) @ cb.matrix
        bpy.context.view_layer.update()


def build(obj, arm, log=print):
    """Solve the corrective keys for the tailored body mesh `obj` (before the outline / join) and store them
    as da_morph_Fit_* point attributes. Returns the number of keys kept."""
    from . import fitcheck as F
    from .models import MORPH_ATTR
    me = obj.data
    groups = F._groups(obj)
    if not any(g in groups for g in ("Jacket", "Skirt", "Pants")):
        return 0
    faces_all = [tuple(p.vertices) for p in me.polygons]
    verts_of = {g: np.array(sorted({v for fi in f for v in me.polygons[fi].vertices})) for g, f in groups.items()}
    outers = [g for g in groups if g != "skin"]
    from . import retarget as RT
    RT._assign(arm, None)
    arm.data.pose_position = "REST"
    rest, _ = F._evaluated(obj)
    arm.data.pose_position = "POSE"
    anchors = F._relax_anchors(rest, groups, faces_all, verts_of, outers)
    nbr = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nbr[a].append(b)
        nbr[b].append(a)
    co0 = np.array([v.co[:] for v in me.vertices])
    key = np.round(co0 / 1e-5).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    kept = 0
    for side in SIDES:
        for name, (pitch, spread, knee) in KEYS.items():
            disp = np.zeros_like(co0)
            first = None
            for _ in range(PASSES):
                me.vertices.foreach_set("co", (co0 + disp).ravel())
                me.update()
                _pose_thigh(arm, side, pitch, spread, knee)
                co, _ = F._evaluated(obj)
                step = np.zeros_like(co0)
                mag = np.zeros(len(co0))
                n_bad = 0
                for idx, tri_of, bary, mode in anchors:
                    h = F._heights(co, idx, tri_of, bary)
                    bad = h > F.EPS
                    if not bad.any():
                        continue
                    n_bad += int(bad.sum())
                    a_, b_, c_ = rest[tri_of[bad, 0]], rest[tri_of[bad, 1]], rest[tri_of[bad, 2]]
                    nrm = np.cross(b_ - a_, c_ - a_)
                    nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
                    need = h[bad] + MARGIN
                    share_out = 0.3 if mode == "tuck" else 0.6
                    for k, (vi, tri, bw) in enumerate(zip(idx[bad], tri_of[bad], bary[bad])):
                        tuck = -nrm[k] * need[k] * (1 - share_out)
                        if np.linalg.norm(tuck) > mag[vi]:
                            mag[vi], step[vi] = np.linalg.norm(tuck), tuck
                        for tv, x in zip(tri, bw):
                            push = nrm[k] * need[k] * share_out * (0.5 + 0.5 * x)
                            if np.linalg.norm(push) > mag[tv]:
                                mag[tv], step[tv] = np.linalg.norm(push), push
                if first is None:
                    first = n_bad
                if not n_bad:
                    break
                for _s in range(2):                       # spread (no dents) ...
                    nxt, nmag = step.copy(), mag.copy()
                    for vi in np.nonzero(mag > 0)[0]:
                        for u in nbr[vi]:
                            if mag[vi] * 0.6 > nmag[u]:
                                nmag[u], nxt[u] = mag[vi] * 0.6, step[vi] * 0.6
                    step, mag = nxt, nmag
                best = np.full(inv.max() + 1, -1.0)       # ... and keep seam copies together
                pick = np.zeros((inv.max() + 1, 3))
                for vi in np.nonzero(mag > 0)[0]:
                    if mag[vi] > best[inv[vi]]:
                        best[inv[vi]], pick[inv[vi]] = mag[vi], step[vi]
                step = np.where(best[inv][:, None] > 0, pick[inv], 0.0)
                disp += step
                ln = np.linalg.norm(disp, axis=1, keepdims=True)
                disp *= np.minimum(1.0, CAP / np.maximum(ln, 1e-12))
            me.vertices.foreach_set("co", co0.ravel())
            me.update()
            if first and np.abs(disp).max() > 1e-4:
                attr = me.attributes.new(f"{MORPH_ATTR}{PREFIX}{name}_{side}", "FLOAT_VECTOR", "POINT")
                attr.data.foreach_set("vector", disp.astype(np.float32).ravel())
                kept += 1
                log(f"  anime: {obj.name}: corrective {PREFIX}{name}_{side}: {first} poking vertices -> "
                    f"{n_bad} (max {np.linalg.norm(disp, axis=1).max() * 1000:.0f} mm)")
    from mathutils import Matrix
    for pb in arm.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return kept
