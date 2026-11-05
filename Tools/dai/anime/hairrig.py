"""
Spring rig for the restyled hair: chains fitted to the hair as it is now, weights blended smoothly between
neighbouring chains so the whole head of hair swings as one soft mass.

The VRoid base rigs do not survive a restyle: their HairJoint bones stay where the original strands were
(springs then pivot about the wrong points), most strands are bolted to the head, the borrowed long hair is
skinned to the spine, and every chain swings on its own, so neighbouring locks drift apart. Here:

  * chains are laid out round the head by azimuth (`short` hair: one chain per sector over the strands' tips;
    `long` hair below the neck: its own longer chains), each following the mean centre line of its strands
  * a vertex's weight is shared between the two nearest chains (Gaussian in azimuth) and blended along the
    chain with hat functions, so no seam opens between locks; the roots stay rigid on the head and the chains
    start where they end (pivots part-way down the locks: the hair at the scalp stays put, the ends sway)
  * bone names are per character (HairJoint_<Key>_Short03_1, HairJoint_<Key>_Long02_4): the union skeleton
    of a group keeps every member's own pivots, and Unreal drops the chains a mesh does not skin
    (UDAAvatarAnimInstance: chains outside the LOD's required bones are skipped)

Unreal's spring solver (DAAvatarAnimInstance.cpp) adds the coherence at runtime: chains are integrated
level by level and every joint is pulled towards the mean motion of its neighbouring chains.
simulate() is the same solver in Python, to preview the motion in Blender.
"""

import math

import bpy
import numpy as np

from . import hairshape as HS

SHORT_JOINTS = 3            # bones per short chain (plus the tip bone)
LONG_JOINTS = 5
SHORT_SECTORS = 10
LONG_SECTORS = 8
ROOT_RIGID = {"short": 0.28, "long": 0.10}   # strand fraction rigid on the head
AZ_SIGMA = 0.75             # chain weight falloff in azimuth, in sector widths


def _az(v):
    return math.degrees(math.atan2(v[0], -v[1])) % 360.0


def _daz(a, b):
    d = (a - b + 180.0) % 360.0 - 180.0
    return abs(d)


def _resample(ts, ps, n, t0=0.0):
    out = []
    for j in range(n + 1):
        t = t0 + (1 - t0) * j / n
        out.append([np.interp(t, ts, ps[:, k]) for k in range(3)])
    return np.array(out)


def _project(p, joints):
    """Position along a polyline (0 .. len(joints) - 1) of the closest point to every row of p."""
    best_d = np.full(len(p), np.inf)
    best_t = np.zeros(len(p))
    for j in range(len(joints) - 1):
        a, b = joints[j], joints[j + 1]
        ab = b - a
        f = np.clip(((p - a) @ ab) / max(ab @ ab, 1e-12), 0, 1)
        d = np.linalg.norm(p - (a + f[:, None] * ab), axis=1)
        m = d < best_d
        best_d[m] = d[m]
        best_t[m] = j + f[m]
    return best_t


class Chain:
    def __init__(self, kind, index, az, joints):
        self.kind, self.index, self.az, self.joints = kind, index, az, joints

    def bone(self, j, key):
        return f"HairJoint_{key}_{self.kind.capitalize()}{self.index:02d}_{j}"


def _layout(S, co, hc, kind, sectors, joints, min_len, t0=0.0, subset=None):
    """Chains of one hair object: sectors by the azimuth of the strand tips; per sector the mean centre line
    of its strands (weighted by length). Returns (chains, per-strand {chain: weight})."""
    live = [i for i in (range(S.n) if subset is None else subset) if S.L[i] >= min_len]
    if not live:
        return [], {}
    tip_az = {}
    for i in live:
        idx = S.idx[i]
        tip = co[idx][np.argmax(S.t[idx])]
        tip_az[i] = _az(tip - hc)
    width = 360.0 / sectors
    chains = []
    for c in range(sectors):
        az = c * width
        mem = [(i, math.exp(-(_daz(tip_az[i], az) / (width * AZ_SIGMA)) ** 2)) for i in live]
        mem = [(i, w) for i, w in mem if w > 0.35]
        if len(mem) < 2:
            continue
        acc, wsum = None, 0.0
        for i, w in mem:
            ts, ps = S.centerline(co, i)
            if len(ts) < 2:
                continue
            ts = (ts - ts.min()) / max(ts.max() - ts.min(), 1e-6)
            path = _resample(ts, ps, joints, t0)     # the chain starts where the rigid roots end
            ww = w * S.L[i]
            acc = path * ww if acc is None else acc + path * ww
            wsum += ww
        if acc is None:
            continue
        chains.append(Chain(kind, len(chains), az, acc / wsum))
    # strand -> chain weights: the two nearest chains in azimuth
    weights = {}
    for i in live:
        ws = sorted(((math.exp(-(_daz(tip_az[i], ch.az) / (width * AZ_SIGMA)) ** 2), k)
                     for k, ch in enumerate(chains)), reverse=True)[:2]
        tot = sum(w for w, _ in ws)
        if tot > 1e-6:
            weights[i] = {k: w / tot for w, k in ws if w / tot > 0.05}
    return chains, weights


def _make_bones(arm, chains, key, parent="head"):
    inv = arm.matrix_world.inverted()
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    head = eb[parent]
    for ch in chains:
        prev = head
        J = ch.joints
        n = len(J) - 1
        for j in range(n + 1):
            a = J[j]
            b = J[j + 1] if j < n else J[n] + (J[n] - J[n - 1]) * 0.35
            name = ch.bone(j, key)
            bone = eb.get(name) or eb.new(name)
            bone.head = inv @ __import__("mathutils").Vector(a.tolist())
            bone.tail = inv @ __import__("mathutils").Vector(b.tolist())
            bone.parent = prev
            bone.use_connect = j > 0
            bone.use_deform = True
            prev = bone
    bpy.ops.object.mode_set(mode="OBJECT")


def _skin(obj, S, co, chains, weights, key, max_inf=4):
    """Vertex weights: head at the roots, then the strand's chains (azimuth blend) along hat functions."""
    for vg in list(obj.vertex_groups):
        if vg.name.startswith("HairJoint") or vg.name in ("spine_03", "spine_02"):
            obj.vertex_groups.remove(vg)
    head = obj.vertex_groups.get("head") or obj.vertex_groups.new(name="head")
    groups = {}
    n = len(co)
    rows = [dict() for _ in range(n)]
    proj = {}
    for k, ch in enumerate(chains):
        proj[k] = _project(co, ch.joints)
    for i in range(S.n):
        idx = S.idx[i]
        cw = weights.get(i)
        rigid = ROOT_RIGID[chains[next(iter(cw))].kind] if cw else 1.0
        for vi in idx:
            t = S.t[vi]
            h = 1.0 - float(HS._smooth(t / rigid)) if cw else 1.0
            row = rows[vi]
            row["head"] = h
            if not cw:
                continue
            for k, w in cw.items():
                tau = proj[k][vi]
                nb = len(chains[k].joints)       # bones 0..n (the last one is the tip bone)
                for b in range(nb):
                    hat = max(0.0, 1.0 - abs(tau - (b + 0.5)))
                    if b == 0 and tau < 0.5:
                        hat = 1.0
                    if hat > 0:
                        nm = chains[k].bone(b, key)
                        row[nm] = row.get(nm, 0.0) + (1 - h) * w * hat
    for vi, row in enumerate(rows):
        items = sorted(row.items(), key=lambda kv: -kv[1])[:max_inf]
        tot = sum(w for _, w in items)
        if tot <= 1e-9:
            items, tot = [("head", 1.0)], 1.0
        for name, w in items:
            if w / tot < 1e-3:
                continue
            g = head if name == "head" else groups.get(name)
            if g is None:
                g = groups[name] = obj.vertex_groups.get(name) or obj.vertex_groups.new(name=name)
            g.add([vi], w / tot, "REPLACE")
        if "head" not in dict(items):
            head.remove([vi])


LONG_STRAND = 0.22          # m: strands at least this long ...
LONG_DROP = 0.25            # m: ... and ending this far below the head centre hang down the back: long chains


def _is_long(S, i, hc):
    """Long hair (heavier, freer chains) hangs below the shoulders; a boy's nape locks stay short hair."""
    return S.L[i] >= LONG_STRAND and S.tip[i][2] < hc[2] - LONG_DROP


def rig(arm, meshes, face, key, log=print):
    """Re-rig every hair object of a restyled model (Hair, HairLong): new chains + weights, short chains over
    the head and long chains for the strands hanging below it. Returns the chains (for simulate)."""
    from . import hairdo as HD
    hc = np.array(HD.head_center(face)[:])
    out = []
    for obj in meshes:
        if not obj.name.startswith("Hair") or obj.name.startswith("HairCap"):
            continue
        S = HS.Strands(obj, hc)
        co = S.co0
        frozen = HS.kept_vertices(obj, tuple(obj.get("da_hair_keep", ())))   # clips / ribbons: rigid on the head
        chains, weights = [], {}
        for kind in ("short", "long"):
            sub = [i for i in range(S.n) if _is_long(S, i, hc) == (kind == "long") and not frozen[S.idx[i]].any()]
            sectors, joints = (LONG_SECTORS, LONG_JOINTS) if kind == "long" else (SHORT_SECTORS, SHORT_JOINTS)
            ch, w = _layout(S, co, hc, kind, sectors, joints, min_len=0.05 if kind == "short" else LONG_STRAND,
                            t0=ROOT_RIGID[kind] * 0.8, subset=sub)
            base = sum(1 for c in out + chains if c.kind == kind)      # indices unique per kind and model
            off = len(chains)
            for c in ch:
                c.index += base
            chains += ch
            weights.update({i: {k + off: v for k, v in cw.items()} for i, cw in w.items()})
        if not chains:
            continue
        _make_bones(arm, chains, key)
        _skin(obj, S, co, chains, weights, key)
        kinds = {k: sum(1 for c in chains if c.kind == k) for k in ("short", "long")}
        log(f"  anime: hair rig {obj.name}: {kinds['short']} short + {kinds['long']} long chains, "
            f"{sum(len(c.joints) for c in chains)} bones, {len(weights)} strands on springs")
        out += chains
    return out


def drop_unused(arm, meshes, prefix="HairJoint-"):
    """Remove the base model's own HairJoint bones once nothing is skinned to them any more."""
    used = set()
    for m in meshes:
        names = {vg.index: vg.name for vg in m.vertex_groups if vg.name.startswith(prefix)}
        if not names:
            continue
        for v in m.data.vertices:
            for g in v.groups:
                if g.weight > 1e-4 and g.group in names:
                    used.add(names[g.group])
        for vg in list(m.vertex_groups):            # empty groups of removed bones
            if vg.name in names.values() and vg.name not in used:
                m.vertex_groups.remove(vg)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    gone = 0
    # children first
    for b in sorted([b for b in eb if b.name.startswith(prefix)], key=lambda b: -len(b.parent_recursive)):
        if b.name in used or any(c.name in used for c in b.children_recursive):
            continue
        eb.remove(b)
        gone += 1
    bpy.ops.object.mode_set(mode="OBJECT")
    return gone


# --------------------------------------------------------------------------- preview solver
# The same parameters and algorithm as UDAAvatarAnimInstance's spring solver (DAAvatarAnimInstance.cpp,
# SpringParamsFor / ApplySprings), in metres: VRM verlet tails, solved level by level, cohesion towards the
# neighbouring chains, a cone limit round the animated direction, head sphere and (long hair) back capsule.
PARAMS = {
    "short": dict(stiffness=3.0, drag=0.6, gravity=0.05, cohesion=0.6, max_angle=18.0, inertia=0.05, body=False),
    "long": dict(stiffness=1.6, drag=0.5, gravity=0.06, cohesion=0.5, max_angle=50.0, inertia=0.15, body=True),
}


def _chains_of(arm):
    """{(group, chain): [bone names root -> tip]} from the armature's HairJoint_<Key>_<Kind><nn>_<j> bones."""
    import re
    out = {}
    for b in arm.data.bones:
        m = re.match(r"(HairJoint_\w+?_(Short|Long))(\d+)_(\d+)$", b.name)
        if m:
            out.setdefault((m.group(1), int(m.group(3))), []).append((int(m.group(4)), b.name))
    return {k: [n for _, n in sorted(v)] for k, v in out.items()}


def _closest(p, a, b):
    ab = b - a
    t = min(1.0, max(0.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return a + ab * t


def simulate(arm, frame_start, frame_end, fps=30, velocity=(0.0, 0.0, 0.0), key=True):
    """Run the spring solver over the armature's current action from frame_start to frame_end (the character
    moving at `velocity` m/s in world space, as it does in game) and key the hair bones' rotations, so a
    preview render of frame_end shows the hair as the game would. Returns the largest deflection (degrees)."""
    from mathutils import Matrix, Quaternion, Vector
    scene = bpy.context.scene
    chains = _chains_of(arm)
    if not chains:
        return 0.0
    names = list(chains)
    kinds = {k: ("long" if k[0].endswith("Long") else "short") for k in names}
    pb = arm.pose.bones
    hair_bones = {n for k in names for n in chains[k]}
    act = arm.animation_data.action if arm.animation_data else None
    if act is not None:                      # an earlier solve's keys would leak into the "animated" pose
        bags = [bag for layer in getattr(act, "layers", []) for strip in layer.strips
                for bag in getattr(strip, "channelbags", [])] or ([act] if hasattr(act, "fcurves") else [])
        for bag in bags:
            for fc in [fc for fc in bag.fcurves if any(f'"{n}"' in fc.data_path for n in hair_bones)]:
                bag.fcurves.remove(fc)
    for k in names:
        for n in chains[k]:
            pb[n].rotation_mode = "QUATERNION"
    baked = {}
    # neighbours: the two nearest tips of the same group (rest pose), within 25 cm
    tips = {k: arm.data.bones[chains[k][-1]].head_local.copy() for k in names}
    nbrs = {}
    for k in names:
        near = sorted((((tips[k] - tips[o]).length, o) for o in names if o != k and o[0] == k[0]), key=lambda x: x[0])
        nbrs[k] = [o for d, o in near[:2] if d < 0.25]
    vel = Vector(velocity)
    dt = min(1.0 / fps, 1.0 / 20.0)
    cur, prev = {}, {}
    max_defl = 0.0
    per_frame = []
    for f in range(frame_start, frame_end + 1):
        frame_defl = 0.0
        scene.frame_set(f)
        for k in names:                      # animated (unturned) pose: hair bones carry no take keys
            for n in chains[k]:
                pb[n].rotation_quaternion = Quaternion()
        off = vel * ((f - frame_start) / fps)
        W = arm.matrix_world
        bpy.context.view_layer.update()
        head_c = W @ (pb["head"].head + Vector((0, 0.01, 0.09))) + off
        head_r = 0.095 * W.to_scale().z
        body = None
        if "spine_02" in pb and "neck_01" in pb:
            body = (W @ pb["spine_02"].head + off, W @ pb["neck_01"].head + off)
        depth = max(len(v) for v in chains.values()) - 1
        if f > frame_start:                  # tails ride along with (1 - inertia) of the character's own move
            step = vel / fps
            for (k, j) in list(cur):
                carry = step * (1 - PARAMS[kinds[k]]["inertia"])
                cur[(k, j)] = cur[(k, j)] + carry
                prev[(k, j)] = prev[(k, j)] + carry
        for j in range(depth):
            bpy.context.view_layer.update()
            lv = {}
            for k in names:
                bones = chains[k]
                if j >= len(bones) - 1:
                    continue
                P = PARAMS[kinds[k]]
                b = pb[bones[j]]
                hw = W @ b.head + off
                tw = W @ b.tail + off            # animated tail (this bone not yet turned this frame)
                L = (tw - hw).length
                if L < 1e-6:
                    continue
                c = cur.get((k, j))
                if c is None:
                    cur[(k, j)] = prev[(k, j)] = tw.copy()
                    c = tw.copy()
                nxt = c + (c - prev[(k, j)]) * (1 - P["drag"]) + (tw - hw) / L * (P["stiffness"] * dt * L * 20.0) \
                    + Vector((0, 0, -1)) * (P["gravity"] * dt)
                lv[k] = (hw, tw, hw + (nxt - hw).normalized() * L, L)
            coh = {}
            for k, (hw, tw, nxt, L) in lv.items():
                ns = [o for o in nbrs[k] if o in lv]
                cw = PARAMS[kinds[k]]["cohesion"]
                if ns and cw > 0:
                    avg = sum(((lv[o][2] - lv[o][1]) for o in ns), Vector()) / len(ns)
                    dev = (nxt - tw).lerp(avg, cw)
                    nxt = hw + (tw + dev - hw).normalized() * L
                coh[k] = nxt
            for k, (hw, tw, _, L) in lv.items():
                P = PARAMS[kinds[k]]
                nxt = coh[k]
                rest = (tw - hw) / L
                d = (nxt - hw).normalized()
                ang = math.degrees(rest.angle(d, 0.0))
                if ang > P["max_angle"]:
                    q = rest.rotation_difference(d)
                    nxt = hw + (Quaternion().slerp(q, P["max_angle"] / ang) @ rest) * L
                r = min(head_r, 0.95 * (tw - head_c).length)
                o = nxt - head_c
                if 1e-9 < o.length < r:
                    nxt = hw + ((head_c + o.normalized() * r) - hw).normalized() * L
                if P["body"] and body is not None:
                    ar = _closest(tw, *body)
                    r = min(0.11, 0.95 * (tw - ar).length)
                    cc = _closest(nxt, *body)
                    o = nxt - cc
                    if 1e-9 < o.length < r:
                        nxt = hw + ((cc + o.normalized() * r) - hw).normalized() * L
                prev[(k, j)] = cur[(k, j)]
                cur[(k, j)] = nxt
                # turn the bone (armature space) so its tail follows the particle
                Wi = W.inverted()
                h_a, t_a, n_a = Wi @ (hw - off), Wi @ (tw - off), Wi @ (nxt - off)
                delta = (t_a - h_a).normalized().rotation_difference((n_a - h_a).normalized())
                max_defl = max(max_defl, math.degrees(delta.angle))
                frame_defl = max(frame_defl, math.degrees(delta.angle))
                b = pb[chains[k][j]]
                M = b.matrix.copy()
                b.matrix = Matrix.Translation(h_a) @ delta.to_matrix().to_4x4() @ Matrix.Translation(-h_a) @ M
        per_frame.append(frame_defl)
        if key:
            bpy.context.view_layer.update()
            baked[f] = {n: pb[n].rotation_quaternion.copy() for n in hair_bones}
    for f, rots in baked.items():            # keyed after the solve, so no key feeds back into it
        for n, q in rots.items():
            pb[n].rotation_quaternion = q
            pb[n].keyframe_insert("rotation_quaternion", frame=f)
    arm["hair_sim"] = dict(max=max_defl, mean=float(np.mean(per_frame)) if per_frame else 0.0)
    return max_defl
