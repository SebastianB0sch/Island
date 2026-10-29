"""
Skinned mesh assembly for the anime cast.

Parts are ordinary MeshBuilder primitives (geo.py) plus a weight function that maps a rest-pose
vertex position to {bone: weight}. Assembly.build() joins them into one skinned mesh, adds the
anime ink line as an inverted hull (a slightly inflated, inside-out copy with the outline
material - one-sided rendering only shows the rim around the silhouette, in Unreal and in Cycles
via a backfacing mask) and gives the head its planar face-texture UVs.
"""

import math

import bpy
import numpy as np
from mathutils import Vector

from .. import blend, palette
from . import skeleton as S

OUTLINE = 0.0035            # ink line thickness (m) at scale 1
OUTLINE_MAT = "M_Anime_Outline"


# --------------------------------------------------------------------------- weight functions
def rigid(bone):
    return lambda p: {bone: 1.0}


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def chain(segments, blend_len=0.03):
    """segments: [(bone, a, b)] consecutive along a limb (rest pose). Vertices are projected onto the
    polyline; within blend_len of a joint the weight fades into the neighbouring bone."""
    segs = [(bone, Vector(a), Vector(b)) for bone, a, b in segments]

    def fn(p):
        best, bi, bt = 1e9, 0, 0.0
        for i, (_, a, b) in enumerate(segs):
            d = b - a
            L2 = max(d.length_squared, 1e-9)
            t = max(0.0, min(1.0, (p - a).dot(d) / L2))
            dist = (a + d * t - p).length
            if dist < best - 1e-6:
                best, bi, bt = dist, i, t
        bone, a, b = segs[bi]
        L = (b - a).length
        w = {bone: 1.0}
        s = bt * L
        if bi > 0 and s < blend_len:
            k = 0.5 * (1 - s / blend_len)
            w = {bone: 1 - k, segs[bi - 1][0]: k}
        elif bi < len(segs) - 1 and L - s < blend_len:
            k = 0.5 * (1 - (L - s) / blend_len)
            w = {bone: 1 - k, segs[bi + 1][0]: k}
        return w
    return fn


SPINE_CENTERS = [("pelvis", S.PELVIS - 0.02), ("spine_01", (S.SPINE1 + S.SPINE2) / 2),
                 ("spine_02", (S.SPINE2 + S.SPINE3) / 2), ("spine_03", (S.SPINE3 + S.NECK) / 2 + 0.01),
                 ("neck_01", (S.NECK + S.HEAD) / 2), ("head", S.HEAD + 0.03)]


def spine(p):
    """Torso: blend along the spine by height."""
    z = p.z
    c = SPINE_CENTERS
    if z <= c[0][1]:
        return {c[0][0]: 1.0}
    for (b0, z0), (b1, z1) in zip(c, c[1:]):
        if z <= z1:
            t = _smooth((z - z0) / (z1 - z0))
            return {b0: 1 - t, b1: t}
    return {c[-1][0]: 1.0}


def torso(p):
    """Jacket body: spine blend, shoulders hand over to the clavicle / upper arm."""
    w = spine(p)
    ax = abs(p.x)
    if p.z > S.SHOULDER - 0.16 and ax > 0.10:
        side = "l" if p.x > 0 else "r"
        k = _smooth((ax - 0.10) / 0.07) * _smooth((p.z - (S.SHOULDER - 0.16)) / 0.10)
        arm = _smooth((ax - S.SHOULDER_X + 0.01) / 0.04)
        w = {b: v * (1 - k) for b, v in w.items()}
        w[f"clavicle_{side}"] = w.get(f"clavicle_{side}", 0.0) + k * (1 - arm)
        w[f"upperarm_{side}"] = w.get(f"upperarm_{side}", 0.0) + k * arm
    return w


def hips_to_thighs(z_full, z_start, amount=0.75):
    """Pelvis wear (skirts, coat tails, pants top): vertices below z_start follow the thigh on their side,
    `amount` of the way at z_full."""
    def fn(p):
        side = "l" if p.x > 0 else "r"
        k = amount * _smooth((z_start - p.z) / (z_start - z_full)) * _smooth(abs(p.x) / 0.08)
        w = spine(p)
        w = {b: v * (1 - k) for b, v in w.items()}
        w[f"thigh_{side}"] = w.get(f"thigh_{side}", 0.0) + k
        return w
    return fn


def head_and_body(z_split=S.NECK + 0.02, z_full=S.SPINE2 + 0.05):
    """Long hair: rigid to the head above z_split, following the upper spine below."""
    def fn(p):
        k = _smooth((z_split - p.z) / (z_split - z_full))
        if k <= 0.0:
            return {"head": 1.0}
        return {"head": 1 - k, "spine_03": k * 0.7, "spine_02": k * 0.3}
    return fn


def arm_chain(side):
    s = 1 if side == "l" else -1
    z = S.SHOULDER
    return chain([(f"clavicle_{side}", (s * S.CLAV_X, 0, z), (s * S.SHOULDER_X, 0, z)),
                  (f"upperarm_{side}", (s * S.SHOULDER_X, 0, z), (s * S.ELBOW_X, 0, z)),
                  (f"lowerarm_{side}", (s * S.ELBOW_X, 0, z), (s * S.WRIST_X, 0, z)),
                  (f"hand_{side}", (s * S.WRIST_X, 0, z), (s * S.HAND_END_X, 0, z))], blend_len=0.05)


def leg_chain(side):
    s = 1 if side == "l" else -1
    x = s * S.HIP_X
    inner = chain([(f"thigh_{side}", (x, 0, S.HIP), (x, 0, S.KNEE)),
                   (f"calf_{side}", (x, 0, S.KNEE), (x, 0, S.ANKLE)),
                   (f"foot_{side}", (x, 0, S.ANKLE), (x, S.BALL_Y, S.BALL_Z))], blend_len=0.06)

    def fn(p):
        w = inner(p)
        if p.z > S.HIP - 0.06:                         # top of the thigh blends into the pelvis
            k = 0.5 * _smooth((p.z - (S.HIP - 0.06)) / 0.10)
            w = {b: v * (1 - k) for b, v in w.items()}
            w["pelvis"] = w.get("pelvis", 0.0) + k
        return w
    return fn


def foot_fn(side):
    def fn(p):
        if p.y < S.BALL_Y + 0.02:
            k = _smooth((S.BALL_Y + 0.02 - p.y) / 0.04)
            return {f"foot_{side}": 1 - k, f"ball_{side}": k}
        if p.z > S.ANKLE + 0.03:
            return {f"foot_{side}": 0.5, f"calf_{side}": 0.5}
        return {f"foot_{side}": 1.0}
    return fn


# --------------------------------------------------------------------------- assembly
class Assembly:
    def __init__(self, name):
        self.name = name
        self.parts = []   # (MeshBuilder, weight fn, outline multiplier)

    def add(self, mb, weights, outline=1.0):
        if mb.verts:
            self.parts.append((mb, weights, outline))
        return mb

    def _arrays(self):
        verts, faces, mats, smooth, wts, ol = [], [], [], [], [], []
        for mb, fn, mult in self.parts:
            base = len(verts)
            for v in mb.verts:
                verts.append(Vector(v))
                wts.append(fn(Vector(v)))
                ol.append(mult)
            faces += [tuple(i + base for i in f) for f in mb.faces]
            mats += mb.face_mats
            smooth += mb.face_smooth
        return verts, faces, mats, smooth, wts, ol

    @staticmethod
    def _smooth_normals(co, faces):
        """Area-weighted vertex normals averaged over coincident positions (primitives are not welded)."""
        n = np.zeros_like(co)
        for f in faces:
            p = co[list(f)]
            fn = np.zeros(3)
            for i in range(1, len(f) - 1):
                fn += np.cross(p[i] - p[0], p[i + 1] - p[0])
            for i in f:
                n[i] += fn
        key = np.round(co / 1e-4).astype(np.int64)
        _, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.ravel()
        acc = np.zeros((inv.max() + 1, 3))
        np.add.at(acc, inv, n)
        n = acc[inv]
        ln = np.linalg.norm(n, axis=1, keepdims=True)
        return n / np.maximum(ln, 1e-12)

    def build(self, arm, face_mats=(), outline=OUTLINE, material_fn=None):
        verts, faces, mats, smooth, wts, ol = self._arrays()
        co = np.array([tuple(v) for v in verts], np.float64)
        nv = len(verts)
        if outline > 0:
            nrm = self._smooth_normals(co, faces)
            keep_v = np.array(ol) > 0
            shell = co + nrm * (outline * np.array(ol))[:, None]
            out_faces, out_mats, out_smooth = [], [], []
            for f, m in zip(faces, mats):
                if all(keep_v[i] for i in f):
                    out_faces.append(tuple(i + nv for i in reversed(f)))
                    out_mats.append(OUTLINE_MAT)
                    out_smooth.append(True)
            co = np.concatenate([co, shell])
            wts = wts + wts
            faces = faces + out_faces
            mats = mats + out_mats
            smooth = smooth + out_smooth
        me = bpy.data.meshes.new(self.name)
        me.from_pydata([tuple(p) for p in co], [], faces)
        order, index = [], {}
        for m in mats:
            if m not in index:
                index[m] = len(order)
                order.append(m)
        mf = material_fn or blend.material
        for m in order:
            me.materials.append(mf(m))
        me.polygons.foreach_set("material_index", [index[m] for m in mats])
        me.polygons.foreach_set("use_smooth", smooth)
        blend.box_uv(me, 4.0)
        _face_uvs(me, {index[m] for m in face_mats if m in index})
        me.update()
        obj = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(obj)
        groups = {}
        for i, w in enumerate(wts):
            tot = sum(w.values())
            for b, v in w.items():
                if v <= 1e-4:
                    continue
                g = groups.get(b) or obj.vertex_groups.new(name=b)
                groups[b] = g
                g.add([i], v / tot, "REPLACE")
        obj.parent = arm
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = arm
        return obj


def _face_uvs(me, mat_indices):
    """Planar front projection of the head for the face texture (see face.py for the mapping)."""
    if not mat_indices:
        return
    cx, cy, cz = S.HEAD_CENTER
    R = S.HEAD_RADIUS
    uvl = me.uv_layers.active
    for poly in me.polygons:
        if poly.material_index not in mat_indices:
            continue
        for li in poly.loop_indices:
            p = me.vertices[me.loops[li].vertex_index].co
            u, v = (p.x - cx) / R, (p.z - cz) / R
            if p.y > cy + R * 0.05:            # back of the head -> skin at the rim of the texture
                ln = math.hypot(u, v) or 1.0
                u, v = u / ln * 0.98, v / ln * 0.98
            # the chin reaches below v = -1: clamp to the skin-coloured rim instead of wrapping
            uvl.data[li].uv = (min(0.995, max(0.005, 0.5 + u * 0.5)), min(0.995, max(0.005, 0.5 + v * 0.5)))


def tri_count(obj):
    return sum(len(p.vertices) - 2 for p in obj.data.polygons)


def register_material(name, **spec):
    palette.register({name: spec})
    return name
