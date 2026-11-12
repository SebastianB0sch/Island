"""
Surface parts for the atelier characters.

A Part is a plain numpy mesh (positions, faces, per-vertex UVs) that also carries what a character
needs beyond geometry: skin weights per bone, morph-target offsets, the ink-line width of the
inverted hull and how far its shading normals are rounded towards a centre (anime faces and hair
are lit as one soft volume, not as their small-scale geometry).

Parts are built by lofting rings (loft), stitched into one skinned Blender mesh by assemble().
"""

import numpy as np

from .. import skeleton as S

OUTLINE_MAT = "M_Anime_Outline"


def smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def spline(keys, x):
    """Monotone-ish cubic (Catmull-Rom) through keys [(x, y...)] sampled at x (array). y may be a vector."""
    k = np.asarray(keys, np.float64)
    xs, ys = k[:, 0], k[:, 1:]
    x = np.clip(np.asarray(x, np.float64), xs[0], xs[-1])
    i = np.clip(np.searchsorted(xs, x, side="right") - 1, 0, len(xs) - 2)
    x0, x1 = xs[i], xs[i + 1]
    t = ((x - x0) / np.maximum(x1 - x0, 1e-12))[..., None]
    p0, p1 = ys[i], ys[i + 1]
    im, ip = np.maximum(i - 1, 0), np.minimum(i + 2, len(xs) - 1)
    h = (x1 - x0)[..., None]
    m0 = (p1 - ys[im]) / np.maximum(x1 - xs[im], 1e-12)[..., None] * h
    m1 = (ys[ip] - p0) / np.maximum(xs[ip] - x0, 1e-12)[..., None] * h
    t2, t3 = t * t, t * t * t
    out = (2 * t3 - 3 * t2 + 1) * p0 + (t3 - 2 * t2 + t) * m0 + (-2 * t3 + 3 * t2) * p1 + (t3 - t2) * m1
    return out[..., 0] if out.shape[-1] == 1 else out


class Part:
    def __init__(self, name, mat, verts, faces, uv=None, outline=1.0):
        self.name = name
        self.mat = mat
        self.v = np.asarray(verts, np.float64).reshape(-1, 3)
        self.f = [tuple(int(i) for i in f) for f in faces]
        n = len(self.v)
        self.uv = np.zeros((n, 2)) if uv is None else np.asarray(uv, np.float64).reshape(n, 2)
        self.w = {}                       # bone -> (n,) weights
        self.morphs = {}                  # morph -> (n, 3) offsets
        self.outline = np.full(n, float(outline)) if np.isscalar(outline) else np.asarray(outline, np.float64)
        self.round = np.zeros(n)          # 0..1: blend of the shading normal towards (v - round_c)
        self.round_c = np.zeros(3)
        self.normal = None                # optional explicit shading normals (n, 3)
        self.face_mat = None              # optional per-face material names (default: self.mat)

    # ------------------------------------------------------------------ weights
    def rigid(self, bone):
        self.w = {bone: np.ones(len(self.v))}
        return self

    def weights(self, fn):
        """fn(positions) -> {bone: (n,)}; normalised here."""
        w = {b: np.asarray(a, np.float64) for b, a in fn(self.v).items()}
        tot = sum(w.values())
        tot = np.where(tot > 1e-9, tot, 1.0)
        self.w = {b: a / tot for b, a in w.items() if a.max() > 1e-4}
        return self

    def blend_to(self, bone, k):
        """Hand a share k (n,) of every vertex over to `bone` (spring / cloth chains)."""
        k = np.clip(np.asarray(k, np.float64), 0.0, 1.0)
        self.w = {b: a * (1.0 - k) for b, a in self.w.items()}
        self.w[bone] = self.w.get(bone, 0.0) + k
        return self

    # ------------------------------------------------------------------ shading / editing
    def rounded(self, centre, amount):
        self.round_c = np.asarray(centre, np.float64)
        self.round = np.full(len(self.v), float(amount)) if np.isscalar(amount) else np.asarray(amount, np.float64)
        return self

    def morph(self, name, delta):
        d = np.asarray(delta, np.float64).reshape(-1, 3)
        if np.abs(d).max() > 1e-7:
            self.morphs[name] = self.morphs[name] + d if name in self.morphs else d
        return self

    def flipped(self):
        self.f = [tuple(reversed(f)) for f in self.f]
        return self

    def mirrored(self, name=None):
        """Copy mirrored in X (left <-> right), bone suffixes swapped."""
        p = Part(name or self.name, self.mat, self.v * (-1, 1, 1), [tuple(reversed(f)) for f in self.f],
                 self.uv.copy(), self.outline.copy())
        p.w = {_swap(b): a.copy() for b, a in self.w.items()}
        p.morphs = {k: d * (-1, 1, 1) for k, d in self.morphs.items()}
        p.round, p.round_c = self.round.copy(), self.round_c * (-1, 1, 1)
        p.normal = None if self.normal is None else self.normal * (-1, 1, 1)
        p.face_mat = None if self.face_mat is None else list(self.face_mat)
        return p

    def tris(self):
        return sum(len(f) - 2 for f in self.f)


def _swap(bone):
    if bone.endswith("_l"):
        return bone[:-2] + "_r"
    if bone.endswith("_r"):
        return bone[:-2] + "_l"
    return bone.replace("_L_", "_#_").replace("_R_", "_L_").replace("_#_", "_R_")


# --------------------------------------------------------------------------- loft
def loft(name, mat, rings, closed=True, cap0=False, cap1=False, uv=(0.0, 1.0, 0.0, 1.0), outline=1.0,
         vs=None, us=None):
    """Quad surface through rings (R, N, 3). closed: the rings are loops (the seam column is duplicated so
    the UVs do not wrap). cap0 / cap1 close the first / last ring with a fan. uv = (u0, u1, v0, v1): u runs
    round the ring, v along the loft (vs / us: explicit per-ring / per-column coordinates in 0..1).
    Faces are oriented away from the ring centres."""
    rings = np.asarray(rings, np.float64)
    R, N = rings.shape[:2]
    if closed:
        rings = np.concatenate([rings, rings[:, :1]], axis=1)
    C = rings.shape[1]
    u0, u1, v0, v1 = uv
    uu = np.linspace(0.0, 1.0, C) if us is None else np.asarray(us, np.float64)
    if closed and us is not None and len(uu) == N:
        uu = np.concatenate([uu, [1.0]])
    vv = np.linspace(0.0, 1.0, R) if vs is None else np.asarray(vs, np.float64)
    U, V = np.meshgrid(u0 + (u1 - u0) * uu, v0 + (v1 - v0) * vv)
    verts = rings.reshape(-1, 3)
    uvs = np.stack([U.ravel(), V.ravel()], axis=1)
    faces = []
    for r in range(R - 1):
        a, b = r * C, (r + 1) * C
        for c in range(C - 1):
            faces.append((a + c, a + c + 1, b + c + 1, b + c))
    extra_v, extra_uv = [], []
    for cap, r in ((cap0, 0), (cap1, R - 1)):
        if not cap:
            continue
        idx = len(verts) + len(extra_v)
        extra_v.append(rings[r, :N].mean(axis=0))
        extra_uv.append(uvs[r * C])
        for c in range(C - 1):
            f = (idx, r * C + c + 1, r * C + c) if r == 0 else (idx, r * C + c, r * C + c + 1)
            faces.append(f)
    if extra_v:
        verts = np.concatenate([verts, np.array(extra_v)])
        uvs = np.concatenate([uvs, np.array(extra_uv)])
    p = Part(name, mat, verts, faces, uvs, outline)
    # orientation: away from the ring centres
    cen = rings[:, :N].mean(axis=1)
    tot = 0.0
    for f in faces[:: max(1, len(faces) // 200)]:
        if len(f) < 4:
            continue
        q = verts[list(f)]
        n = np.cross(q[1] - q[0], q[3] - q[0])
        r = min(f[0] // C, R - 1)
        tot += float(n @ (q.mean(axis=0) - cen[r]))
    if tot < 0:
        p.flipped()
    return p


def ring(centre, ax_u, ax_v, ru, rv, n=16, power=2.0, phase=0.0):
    """Superellipse loop round `centre` in the plane (ax_u, ax_v)."""
    t = phase + np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    c, s = np.cos(t), np.sin(t)
    e = 2.0 / power
    cu = np.sign(c) * np.abs(c) ** e
    sv = np.sign(s) * np.abs(s) ** e
    return (np.asarray(centre, np.float64)[None] + np.outer(cu * ru, ax_u) + np.outer(sv * rv, ax_v))


def tube(name, mat, path, radii, n=12, up=(0, 0, 1), flat=1.0, power=2.0, cap0=True, cap1=True, **kw):
    """Loft of superellipse rings along a polyline (K, 3). radii (K,); flat: thickness ratio along the
    frame's second axis."""
    path = np.asarray(path, np.float64)
    radii = np.broadcast_to(np.asarray(radii, np.float64), (len(path),))
    tan = np.gradient(path, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
    up = np.asarray(up, np.float64)
    rings = []
    for p, t, r in zip(path, tan, radii):
        a = np.cross(up, t)
        if np.linalg.norm(a) < 1e-6:
            a = np.cross((1.0, 0.0, 0.0), t)
        a /= np.linalg.norm(a)
        b = np.cross(t, a)
        rings.append(ring(p, a, b, r, r * flat, n, power))
    return loft(name, mat, np.array(rings), closed=True, cap0=cap0, cap1=cap1, **kw)


def grid(name, mat, pts, uv=(0.0, 1.0, 0.0, 1.0), outline=0.0):
    """Open quad patch through a (R, C, 3) point grid (decals: lids, brows, mouth)."""
    return loft(name, mat, pts, closed=False, uv=uv, outline=outline)


def solidify(part, thickness):
    """Give an open shell an inner side and rims (hems, cuffs, open jackets): the copy is pushed inwards
    along the vertex normals, flipped, and stitched to the boundary edges."""
    n = len(part.v)
    nrm = vertex_normals(part.v, part.f)
    inner = part.v - nrm * thickness
    faces = list(part.f) + [tuple(i + n for i in reversed(f)) for f in part.f]
    edges = {}
    for f in part.f:
        for a, b in zip(f, f[1:] + f[:1]):
            edges[(a, b)] = edges.get((a, b), 0) + 1
    key = np.round(part.v / 1e-5).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    und = {}
    for (a, b) in edges:
        k = (min(inv[a], inv[b]), max(inv[a], inv[b]))
        und[k] = und.get(k, 0) + 1
    for (a, b) in edges:
        if und[(min(inv[a], inv[b]), max(inv[a], inv[b]))] == 1:
            faces.append((b, a, a + n, b + n))
    out = Part(part.name, part.mat, np.concatenate([part.v, inner]), faces,
               np.concatenate([part.uv, part.uv]), np.concatenate([part.outline, part.outline * 0.0]))
    out.w = {b: np.concatenate([a, a]) for b, a in part.w.items()}
    out.morphs = {k: np.concatenate([d, d]) for k, d in part.morphs.items()}
    out.round, out.round_c = np.concatenate([part.round, part.round]), part.round_c
    if part.face_mat is not None:
        out.face_mat = list(part.face_mat) * 2 + [part.face_mat[0]] * (len(faces) - 2 * len(part.f))
    return out


def vertex_normals(v, faces):
    """Area-weighted normals shared by coincident positions (parts keep UV seams as split vertices)."""
    n = np.zeros_like(v)
    for f in faces:
        p = v[list(f)]
        fn = np.zeros(3)
        for i in range(1, len(f) - 1):
            fn += np.cross(p[i] - p[0], p[i + 1] - p[0])
        n[list(f)] += fn
    key = np.round(v / 2e-5).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    acc = np.zeros((inv.max() + 1, 3))
    np.add.at(acc, inv, n)
    n = acc[inv]
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def merge(name, parts, mat=None):
    """Concatenate parts into one (same material unless face_mat is used)."""
    parts = [p for p in parts if p is not None and len(p.v)]
    out_f, fm, off = [], [], 0
    for p in parts:
        out_f += [tuple(i + off for i in f) for f in p.f]
        fm += list(p.face_mat) if p.face_mat is not None else [p.mat] * len(p.f)
        off += len(p.v)
    out = Part(name, mat or parts[0].mat, np.concatenate([p.v for p in parts]), out_f,
               np.concatenate([p.uv for p in parts]), np.concatenate([p.outline for p in parts]))
    out.face_mat = fm
    bones = {b for p in parts for b in p.w}
    out.w = {b: np.concatenate([p.w.get(b, np.zeros(len(p.v))) for p in parts]) for b in bones}
    morphs = {m for p in parts for m in p.morphs}
    out.morphs = {m: np.concatenate([p.morphs.get(m, np.zeros((len(p.v), 3))) for p in parts]) for m in morphs}
    out.round = np.concatenate([p.round for p in parts])
    out.round_c = parts[0].round_c
    nrm = [p.normal for p in parts]
    if any(n is not None for n in nrm):
        out._normals = nrm
    out._round_cs = [(len(p.v), p.round_c) for p in parts]
    return out


# --------------------------------------------------------------------------- weight fields
def _seg_t(P, a, b):
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    d = b - a
    return (P - a) @ d / max(float(d @ d), 1e-12)


def w_spine(P):
    """Torso / neck / head by height."""
    from ..skin import SPINE_CENTERS
    z = P[:, 2]
    out = {b: np.zeros(len(P)) for b, _ in SPINE_CENTERS}
    c = SPINE_CENTERS
    out[c[0][0]] += (z <= c[0][1])
    for (b0, z0), (b1, z1) in zip(c, c[1:]):
        m = (z > z0) & (z <= z1)
        t = smooth((z - z0) / (z1 - z0))
        out[b0] += m * (1 - t)
        out[b1] += m * t
    out[c[-1][0]] += (z > c[-1][1])
    return out


def w_arm(side, blend=0.05, shoulder=True):
    s = 1.0 if side == "l" else -1.0
    joints = [S.CLAV_X, S.SHOULDER_X, S.ELBOW_X, S.WRIST_X, S.HAND_END_X + 0.2]
    bones = [f"clavicle_{side}", f"upperarm_{side}", f"lowerarm_{side}", f"hand_{side}"]

    def fn(P):
        x = P[:, 0] * s
        out = {}
        for i, b in enumerate(bones):
            lo, hi = joints[i], joints[i + 1]
            k = np.ones(len(P))
            if i > 0:
                k *= smooth((x - (lo - blend)) / (2 * blend))
            if i < len(bones) - 1:
                k *= 1.0 - smooth((x - (hi - blend)) / (2 * blend))
            out[b] = k
        if shoulder:                                   # inside the shoulder the torso keeps a share
            body = 1.0 - smooth((x - 0.10) / 0.09)
            sp = w_spine(P)
            out = {b: a * (1 - body) for b, a in out.items()}
            for b, a in sp.items():
                out[b] = out.get(b, 0.0) + a * body
        return out
    return fn


def w_leg(side, blend=0.06, hip=True):
    def fn(P):
        z = P[:, 2]
        y = P[:, 1]
        thigh = smooth((z - (S.KNEE - blend)) / (2 * blend))
        calf = (1 - thigh) * smooth((z - (S.ANKLE + 0.01)) / 0.05)
        foot = (1 - thigh) * (1 - smooth((z - (S.ANKLE + 0.01)) / 0.05))
        toe = foot * smooth((S.BALL_Y + 0.015 - y) / 0.03)
        out = {f"thigh_{side}": thigh, f"calf_{side}": calf, f"foot_{side}": foot - toe, f"ball_{side}": toe}
        if hip:
            k = 0.85 * smooth((z - (S.HIP - 0.07)) / 0.11)
            out = {b: a * (1 - k) for b, a in out.items()}
            out["pelvis"] = k
        return out
    return fn


def w_torso(P):
    """Spine blend; the shoulders hand over to the clavicles / upper arms."""
    out = w_spine(P)
    ax = np.abs(P[:, 0])
    k = smooth((ax - 0.085) / 0.075) * smooth((P[:, 2] - (S.SHOULDER - 0.17)) / 0.11)
    arm = smooth((ax - S.SHOULDER_X + 0.015) / 0.05)
    out = {b: a * (1 - k) for b, a in out.items()}
    for side, m in (("l", P[:, 0] > 0), ("r", P[:, 0] <= 0)):
        out[f"clavicle_{side}"] = k * (1 - arm) * m
        out[f"upperarm_{side}"] = k * arm * m
    return out


def w_hips(z_start, z_full, amount=0.8):
    """Pelvis wear (skirts, coat tails, trouser tops): below z_start the cloth follows the thigh on its side."""
    def fn(P):
        out = w_spine(P)
        k = amount * smooth((z_start - P[:, 2]) / (z_start - z_full)) * smooth(np.abs(P[:, 0]) / 0.07)
        out = {b: a * (1 - k) for b, a in out.items()}
        out["thigh_l"] = k * (P[:, 0] > 0)
        out["thigh_r"] = k * (P[:, 0] <= 0)
        return out
    return fn


# --------------------------------------------------------------------------- Blender mesh
def assemble(name, parts, arm, material_fn, outline=0.0030, log=None, outline_mat=OUTLINE_MAT):
    """Join parts into one skinned mesh object: materials, UVs, vertex groups, shape keys, rounded shading
    normals and the inverted-hull ink line (per-vertex width = outline * part.outline)."""
    import bpy
    parts = [p for p in parts if p is not None and len(p.v)]
    V = np.concatenate([p.v for p in parts])
    UV = np.concatenate([p.uv for p in parts])
    OL = np.concatenate([p.outline for p in parts])
    n = len(V)
    faces, fmat, off = [], [], 0
    N = np.zeros((n, 3))
    for p in parts:
        faces += [tuple(i + off for i in f) for f in p.f]
        fmat += list(p.face_mat) if p.face_mat is not None else [p.mat] * len(p.f)
        nrm = vertex_normals(p.v, p.f)
        subs = getattr(p, "_round_cs", [(len(p.v), p.round_c)])
        a = 0
        for cnt, c in subs:
            sl = slice(a, a + cnt)
            if p.round[sl].max() > 0:
                sph = p.v[sl] - c
                sph /= np.maximum(np.linalg.norm(sph, axis=1, keepdims=True), 1e-9)
                k = p.round[sl][:, None]
                m = nrm[sl] * (1 - k) + sph * k
                nrm[sl] = m / np.maximum(np.linalg.norm(m, axis=1, keepdims=True), 1e-9)
            a += cnt
        if p.normal is not None:
            nrm = p.normal
        N[off:off + len(p.v)] = nrm
        off += len(p.v)
    weights, morphs = {}, {}
    off = 0
    for p in parts:
        for b, a in p.w.items():
            weights.setdefault(b, np.zeros(n))[off:off + len(p.v)] = a
        for m, d in p.morphs.items():
            morphs.setdefault(m, np.zeros((n, 3)))[off:off + len(p.v)] = d
        if not p.w:
            raise ValueError(f"part {p.name} has no skin weights")
        off += len(p.v)
    # inverted hull: geometric (position-merged) normals so split UV seams do not open the line
    hull_n = vertex_normals(V, faces)
    keep = OL > 1e-6
    hull_faces = [tuple(i + n for i in reversed(f)) for f in faces if all(keep[i] for i in f)]
    hull_v = V + hull_n * (outline * OL)[:, None]
    allV = np.concatenate([V, hull_v])
    allUV = np.concatenate([UV, UV])
    allN = np.concatenate([N, -hull_n])
    all_faces = faces + hull_faces
    fmat = fmat + [outline_mat] * len(hull_faces)

    me = bpy.data.meshes.new(name)
    me.from_pydata(allV.tolist(), [], all_faces)
    order = []
    for m in fmat:
        if m not in order:
            order.append(m)
    for m in order:
        me.materials.append(material_fn(m))
    idx = {m: i for i, m in enumerate(order)}
    me.polygons.foreach_set("material_index", [idx[m] for m in fmat])
    me.polygons.foreach_set("use_smooth", [True] * len(all_faces))
    uvl = me.uv_layers.new(name="UVMap")
    loops = np.empty(len(me.loops), np.int32)
    me.loops.foreach_get("vertex_index", loops)
    uvl.data.foreach_set("uv", allUV[loops].ravel())
    me.update()
    me.normals_split_custom_set_from_vertices(allN.tolist())
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    for b, a in weights.items():
        a2 = np.concatenate([a, a])
        g = obj.vertex_groups.new(name=b)
        nz = np.nonzero(a2 > 1e-4)[0]
        for i, w in zip(nz.tolist(), a2[nz].tolist()):
            g.add([i], w, "REPLACE")
    if morphs:
        obj.shape_key_add(name="Basis", from_mix=False)
        base = allV.astype(np.float32)
        for m in sorted(morphs):
            d = np.concatenate([morphs[m], morphs[m]]).astype(np.float32)
            key = obj.shape_key_add(name=m, from_mix=False)
            key.data.foreach_set("co", (base + d).ravel())
            key.value = 0.0
    obj.parent = arm
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    if log:
        log(f"  atelier: {name}: {sum(len(f) - 2 for f in all_faces)} tris, {len(order)} materials, "
            f"{len(weights)} bones, {len(morphs)} morphs")
    return obj
