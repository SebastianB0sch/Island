"""
Anime volume for the base models' hair: smooth, coherent warps instead of per-strand edits.

VRoid hair is a stack of thin strands lying on the scalp. Turning each strand on its own (the old
hairdo.spike) fans them apart: gaps open between neighbours, thin wisps stick out and the silhouette
gets wide and ragged. Anime hair in modern games reads as a few big, soft masses with a rounded outline,
so every step here moves neighbouring hair together:

  flow      the style direction: every strand bends (not turns rigidly) about its root towards "out and
            up" and stretches, with the bend and stretch smoothed over the strands' neighbours so a whole
            region of the head moves as one lock
  clump     strand tips gather into a few bigger locks (k-means on the tips): wide, overlapping masses that
            end in soft points instead of a fringe of separate needles
  widen     strands get a fuller cross-section (scaled about their own centre line) so layers overlap
  volume    the hair layer stands off the scalp: its thickness over the skull is scaled (top / back more
            than the sides) and lifted a little, the big fluffy dome of anime hair
  envelope  a soft limit on the silhouette: the head's half width times `side` above the ears, narrowing
            towards the jaw, a soft cap on the height - no strand pokes out of the overall shape
  under     a hair-coloured under-layer on the skull below the strands, so no skin shows between them

All steps are smooth functions of position and strand parameter, so the layers never cross and nothing
separates. The returned displacement field is also used to move the spring bones with the hair
(hairrig.py).
"""

import math

import numpy as np
from mathutils import Quaternion, Vector
from scipy.spatial import cKDTree

from . import hairdo as HD


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Strands:
    """Per-strand analysis of a hair mesh: island label, root, tip and the axial parameter t (0 root .. 1 tip)
    of every vertex."""

    def __init__(self, obj, hc, min_len=0.02):
        co, lab = HD.islands(obj.data)
        self.co0 = co.copy()
        self.lab = lab
        hw = HD._head_weight(obj)
        self.hc = np.array(hc[:])
        n = lab.max() + 1 if len(lab) else 0
        self.n = n
        self.idx = [np.where(lab == i)[0] for i in range(n)]
        self.root = np.zeros((n, 3))
        self.tip = np.zeros((n, 3))
        self.L = np.zeros(n)
        self.t = np.zeros(len(co))
        for i, idx in enumerate(self.idx):
            p = co[idx]
            root, far = HD._root_tip(p, hw[idx], hc)
            self.root[i], self.tip[i] = root, far
            d = np.linalg.norm(p - root, axis=1)
            L = float(d.max()) if len(d) else 0.0
            self.L[i] = L
            self.t[idx] = d / L if L > 1e-6 else 0.0
        self.live = self.L >= min_len

    def centerline(self, co, i, bins=10):
        """Centre line of strand i at positions co: (t samples, points)."""
        idx = self.idx[i]
        t = self.t[idx]
        p = co[idx]
        ts, ps = [], []
        for b in range(bins):
            lo, hi = b / bins, (b + 1) / bins
            m = (t >= lo) & (t <= hi if b == bins - 1 else t < hi)
            if m.any():
                ts.append(float(t[m].mean()))
                ps.append(p[m].mean(0))
        return np.array(ts), np.array(ps)


def _interp(ts, ps, t):
    if len(ts) == 1:
        return np.repeat(ps[:1], len(t), 0)
    return np.stack([np.interp(t, ts, ps[:, k]) for k in range(3)], 1)


# --------------------------------------------------------------------------- flow
def flow(S, co, lift=0.3, up=0.3, length=1.3, front_lift=0.1, front_length=1.1, crown_lift=None, side_lift=None,
         back_only=False, sigma=0.03, bend=0.6, sweep=0.0):
    """Smoothed, bending version of the old hairdo.spike (same parameters): per strand a turn towards
    out + up (+ sweep backwards: swept-back spikes that do not widen the head) and a stretch, averaged over the strands whose roots lie within ~sigma, applied progressively
    along the strand (bend: exponent of the turn's growth from root to tip)."""
    hc = Vector(S.hc.tolist())
    rv = np.zeros((S.n, 3))        # rotation vectors (axis * angle)
    st = np.ones(S.n)
    for i in range(S.n):
        if not S.live[i]:
            continue
        root, far = Vector(S.root[i].tolist()), Vector(S.tip[i].tolist())
        a = (far - root).normalized()
        out = (root - hc)
        out = out.normalized() if out.length > 1e-6 else Vector((0, 0, 1))
        front = out.y < -0.45 and far.z < hc.z + 0.04
        if back_only and out.y < 0.25:
            continue
        tgt = (out + Vector((0, sweep * (1 - max(0.0, -out.y)), up))).normalized()
        f, k = (front_lift, front_length) if front else (lift, length)
        if crown_lift is not None and out.z > 0.35:
            f, k = crown_lift, 1.0
        elif side_lift is not None and abs(out.x) > 0.6:
            f = side_lift
        q = Quaternion().slerp(a.rotation_difference(tgt), f)
        ax, ang = q.to_axis_angle()
        if ang > math.pi:
            ang -= 2 * math.pi
        rv[i] = np.array(ax[:]) * ang
        st[i] = k
    # neighbour average (roots within ~sigma move together)
    live = np.where(S.live)[0]
    tree = cKDTree(S.root[live])
    rv_s, st_s = rv.copy(), st.copy()
    for i in live:
        nb = tree.query_ball_point(S.root[i], 2.5 * sigma)
        j = live[nb]
        w = np.exp(-(np.linalg.norm(S.root[j] - S.root[i], axis=1) / sigma) ** 2) * np.minimum(1.0, S.L[j] / 0.06)
        w /= w.sum()
        rv_s[i] = (rv[j] * w[:, None]).sum(0)
        st_s[i] = (st[j] * w).sum()
    new = co.copy()
    for i in live:
        idx = S.idx[i]
        root = S.root[i]
        a = S.tip[i] - root
        a /= max(np.linalg.norm(a), 1e-9)
        rel = co[idx] - root
        along = rel @ a
        rel = rel + np.outer(along * (st_s[i] - 1.0), a)
        ang = np.linalg.norm(rv_s[i])
        if ang < 1e-6:
            new[idx] = root + rel
            continue
        ax = Vector((rv_s[i] / ang).tolist())
        frac = S.t[idx] ** bend
        for j, vi in enumerate(idx):
            q = Quaternion(ax, ang * frac[j])
            new[vi] = root + np.array((q @ Vector(rel[j].tolist()))[:])
    return new


# --------------------------------------------------------------------------- clump
LONG = 0.22                 # m: strands this long hang below the head (long hair keeps its own line)


def clump(S, co, size=4, pull=0.55, power=2.0, seed=7, below=0.15):
    """Gather the strand tips into bigger locks: k-means on (tip, root / 2) of the live strands that end above
    the jaw (head centre - `below`; long hanging hair keeps its line), about `size` strands per lock; every
    vertex moves towards its lock's mean tip by pull * t^power."""
    from scipy.cluster.vq import kmeans2
    live = np.array([i for i in np.where(S.live)[0] if S.tip[i][2] > S.hc[2] - below and S.L[i] < LONG], dtype=int)
    if len(live) < 2 * size:
        return co
    tips = np.array([co[S.idx[i]][np.argmax(S.t[S.idx[i]])] for i in live])
    feat = np.concatenate([tips, S.root[live] * 0.5], 1)
    k = max(2, len(live) // size)
    rng = np.random.default_rng(seed)
    init = feat[rng.choice(len(feat), k, replace=False)]
    cent, lab = kmeans2(feat, init, minit="matrix", iter=30)
    new = co.copy()
    for c in range(k):
        m = np.where(lab == c)[0]
        if len(m) < 2:
            continue
        target = tips[m].mean(0)
        for jj in m:
            i = live[jj]
            idx = S.idx[i]
            w = pull * S.t[idx] ** power
            new[idx] += np.outer(w, target - tips[jj])
    return new


# --------------------------------------------------------------------------- coherence
def smooth_field(rest, new, sigma=0.015, iters=2):
    """Neighbouring hair moves together: the displacement new - rest averaged over every vertex within ~2 sigma
    of the rest position (whatever strand it belongs to), so layers keep their order and nothing splits."""
    from scipy.sparse import csr_matrix
    tree = cKDTree(rest)
    pairs = tree.query_pairs(2.0 * sigma, output_type="ndarray")
    n = len(rest)
    i = np.concatenate([pairs[:, 0], pairs[:, 1], np.arange(n)])
    j = np.concatenate([pairs[:, 1], pairs[:, 0], np.arange(n)])
    d = np.linalg.norm(rest[i] - rest[j], axis=1)
    w = np.exp(-(d / sigma) ** 2)
    W = csr_matrix((w, (i, j)), shape=(n, n))
    W = csr_matrix(W.multiply(1.0 / np.asarray(W.sum(1)).ravel()[:, None]))
    disp = new - rest
    for _ in range(iters):
        disp = W @ disp
    return rest + disp


# --------------------------------------------------------------------------- widen
def widen(S, co, k=1.3, tip=0.35, root=0.2):
    """Fuller strands: the width across each strand (in the hair surface) scaled up to k a little way down the strand
    (from 1 at the root - VRoid strands start together at the crown whorl, widened root caps would splinter
    out of it - to k by t = root), easing to 1 + (k - 1) * tip at the tip (the point stays a point)."""
    new = co.copy()
    for i in np.where(S.live)[0]:
        idx = S.idx[i]
        ts, ps = S.centerline(co, i)
        if len(ts) < 2:
            continue
        c = _interp(ts, ps, S.t[idx])
        t = S.t[idx]
        s = 1 + (k - 1) * _smooth(t / max(root, 1e-3)) * (1 - (1 - tip) * t)
        # only across the strand, in the hair surface: the offset along the strand's width axis (perpendicular
        # to its tangent and to the outward normal). A curved strand's centre line sags under the surface, so
        # scaling the whole offset would push the strand off the head.
        tg = np.gradient(ps, axis=0) if len(ps) > 1 else np.zeros_like(ps)
        tg = _interp(ts, tg, t)
        tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-9)
        nrm = co[idx] - S.hc
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
        wax = np.cross(tg, nrm)
        wax /= np.maximum(np.linalg.norm(wax, axis=1, keepdims=True), 1e-9)
        lat = np.einsum("ij,ij->i", co[idx] - c, wax)
        new[idx] = co[idx] + wax * (lat * (s - 1))[:, None]
    return new


# --------------------------------------------------------------------------- volume
class Skull:
    """Inner surface of the hair: per direction from the head centre, the smallest (ellipsoid-normalised)
    radius of any hair vertex - the scalp the hair lies on. Smoothed over neighbouring directions."""

    def __init__(self, hc, co, axes, step=12.0, outer=False):
        self.hc = np.array(hc)
        self.axes = np.array(axes)
        self.step = step
        d = (co - self.hc) / self.axes
        r = np.linalg.norm(d, axis=1)
        az, el = self._angles(d)
        na, ne = int(360 / step), int(180 / step) + 1
        grid = np.full((ne, na), np.nan)
        ia = (az / step).astype(int) % na
        ie = np.clip(((el + 90) / step).round().astype(int), 0, ne - 1)
        for a, e, rr in zip(ia, ie, r):
            if np.isnan(grid[e, a]) or (rr > grid[e, a] if outer else rr < grid[e, a]):
                grid[e, a] = rr
        # fill holes / smooth (wrap in azimuth)
        for _ in range(3):
            g2 = grid.copy()
            for e in range(ne):
                for a in range(na):
                    nb = [grid[ee, (a + da) % na] for ee in (e - 1, e, e + 1) if 0 <= ee < ne for da in (-1, 0, 1)]
                    nb = [v for v in nb if not np.isnan(v)]
                    if nb:
                        g2[e, a] = 0.5 * (grid[e, a] if not np.isnan(grid[e, a]) else np.mean(nb)) + 0.5 * np.mean(nb)
            grid = g2
        grid[np.isnan(grid)] = np.nanmedian(grid)
        self.grid = grid

    @staticmethod
    def _angles(d):
        az = np.degrees(np.arctan2(d[:, 0], -d[:, 1])) % 360.0
        el = np.degrees(np.arcsin(np.clip(d[:, 2] / np.maximum(np.linalg.norm(d, axis=1), 1e-9), -1, 1)))
        return az, el

    def inner(self, co):
        d = (co - self.hc) / self.axes
        az, el = self._angles(d)
        na = self.grid.shape[1]
        fa = az / self.step
        fe = np.clip((el + 90) / self.step, 0, self.grid.shape[0] - 1)
        a0 = np.floor(fa).astype(int) % na
        a1 = (a0 + 1) % na
        e0 = np.floor(fe).astype(int)
        e1 = np.minimum(e0 + 1, self.grid.shape[0] - 1)
        ta, te = fa - np.floor(fa), fe - e0
        g = self.grid
        return ((g[e0, a0] * (1 - ta) + g[e0, a1] * ta) * (1 - te) + (g[e1, a0] * (1 - ta) + g[e1, a1] * ta) * te)


def volume(S, co, skull, top=1.8, back=1.6, side=1.25, front=1.15, loft=0.012, low_el=-25.0, root=0.06,
           layer=0.025):
    """Hair standing off the scalp: the layer's (ellipsoid-normalised) thickness over the skull scaled by a
    factor blended from `top` (crown), `back`, `side` and `front` (the fringe over the forehead) by direction,
    plus a lift of `loft` metres; both grow from the strand roots (only the very roots, t < root, stay on the
    scalp: the crown rises into a dome with the rest) and fade out below `low_el` (hanging locks keep their line)."""
    d = (co - skull.hc) / skull.axes
    r = np.linalg.norm(d, axis=1)
    u = d / np.maximum(r, 1e-9)[:, None]
    # elevation of each vertex's strand root: a strand carries its growth down to the tip (no shelf where
    # the lift would stop half way down a lock)
    rd = (S.root[S.lab] - skull.hc) / skull.axes
    el = np.degrees(np.arcsin(np.clip(rd[:, 2] / np.maximum(np.linalg.norm(rd, axis=1), 1e-9), -1, 1)))
    up = np.clip(u[:, 2], 0, 1) ** 2
    bk = np.clip(u[:, 1], 0, 1) ** 2
    fr = np.clip(-u[:, 1], 0, 1) ** 2
    sd = u[:, 0] ** 2
    tot = up + bk + sd + fr + 1e-6
    k = (top * up + back * bk + side * sd + front * fr) / tot
    fade = _smooth((el - low_el) / 20.0) * _smooth(S.t / max(root, 1e-3))
    k = 1 + (k - 1) * fade
    rin = skull.inner(co)
    th = np.maximum(r - rin, 0.0)
    # only the hair layer over the skull (its first `layer` metres) is thickened: a free-hanging lock further
    # out (twin tails, a fringe in front of the face) just moves with it instead of being flung outwards
    cap = layer / float(np.mean(skull.axes))
    lift = loft / float(np.mean(skull.axes)) * fade * (0.4 + 0.6 * (up + bk) / tot)
    dr = np.minimum(th, cap) * (k - 1) + lift
    dr = np.maximum(dr, 0.0)               # only ever outwards
    # below the head centre the growth is horizontal: pushing hanging hair down would only lengthen it
    # (a fringe sliding over the eyes)
    push = u.copy()
    push[:, 2] = np.maximum(push[:, 2], 0.0)
    push /= np.maximum(np.linalg.norm(push, axis=1, keepdims=True), 1e-9)
    return co + push * dr[:, None] * skull.axes


# --------------------------------------------------------------------------- envelope
def _soft(x, a, b):
    """Soft upper limit a for x >= 0 (identity well below a - b, never above a)."""
    s = a - b
    y = x.copy()
    m = x > s
    y[m] = s[m] + b[m] * np.tanh((x[m] - s[m]) / b[m])
    return y


def envelope(co, hc, half_w, side=1.45, jaw=1.15, top=None, soft=0.35, neck_z=None, free=None):
    """Soft limit of the silhouette: |x| below side * half_w over the head, narrowing to jaw * half_w at the
    chin (the anime bulb outline); optional height cap top * half_w above the head centre. Below neck_z
    (default: just under the chin) nothing is touched - long hair hangs at body width."""
    new = co.copy()
    z = co[:, 2] - hc[2]
    t = _smooth((-z - 0.01) / (half_w * 1.1))         # 0 at the ears .. 1 at the chin
    lim = half_w * (side + (jaw - side) * t)
    b = np.maximum(soft * half_w, 1e-3) * np.ones(len(co))
    x = np.abs(co[:, 0] - hc[0])
    nx = _soft(x, lim, b)
    if neck_z is None:
        neck_z = hc[2] - 1.5 * half_w
    if neck_z is not None:
        keep = _smooth((co[:, 2] - neck_z) / 0.04)
        nx = x + (nx - x) * keep
    if free is not None:                  # long hanging locks keep their line
        nx = np.where(free, x, nx)
    new[:, 0] = hc[0] + np.sign(co[:, 0] - hc[0]) * nx
    if top is not None:
        zt = np.maximum(z, 0)
        nz = _soft(zt, half_w * top * np.ones(len(co)), b)
        new[:, 2] = np.where(z > 0, hc[2] + nz, co[:, 2])
    return new


# --------------------------------------------------------------------------- under-layer
def _hairline(az, front_el=38.0, side_el=-28.0, back_el=-45.0):
    """Lowest elevation the under-layer reaches at azimuth az (0 = face): high over the forehead, down to
    the ears at the sides and to the nape at the back."""
    c = math.cos(math.radians(az))
    if c >= 0:
        return side_el + (front_el - side_el) * c ** 1.5
    return side_el + (back_el - side_el) * (-c) ** 1.2


def _opaque(me, vuv, vmat, level=0.95):
    """Vertices whose UV lands on an opaque texel of their material's base image (strand tips fade out)."""
    from . import models as M
    out = np.ones(len(vuv), bool)
    for mi, mt in enumerate(me.materials):
        if mt is None:
            continue
        try:
            img, _ = M._base_image(mt)
        except Exception:  # noqa: BLE001
            img = None
        if img is None or not img.size[0]:
            continue
        w, h = img.size
        px = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(px)
        a = px.reshape(h, w, 4)[..., 3]
        sel = vmat == mi
        u = np.clip((vuv[sel, 0] % 1.0) * w, 0, w - 1).astype(int)
        v = np.clip((vuv[sel, 1] % 1.0) * h, 0, h - 1).astype(int)
        out[sel] = a[v, u] >= level
    return out


def under_layer(obj, face, skull, skin=None, inset=0.985, lift=0.002, seg=40, rings=24, roots=None, **hairline):
    """Hair-coloured shell on the skull just inside the hair's inner layer (the scalp), above the hairline:
    a separate object "HairCap" with the hair's material and the UVs of the nearest strand root (roots are
    opaque; strand tips fade out in the alpha mask), rigid on the head. Hides the skin wherever the strands
    part."""
    import bpy
    from ..geo import MeshBuilder  # noqa: F401  (keeps the geo package import order)
    me = obj.data
    co = np.array([v.co[:] for v in me.vertices])
    uvl = me.uv_layers.active
    vuv = np.zeros((len(co), 2))
    if uvl is not None:
        for l in me.loops:
            vuv[l.vertex_index] = uvl.data[l.index].uv[:]
    mats = [p.material_index for p in me.polygons]
    vmat = np.zeros(len(co), dtype=int)
    for p in me.polygons:
        for v in p.vertices:
            vmat[v] = p.material_index
    ok = np.ones(len(co), bool) if roots is None else np.asarray(roots, bool).copy()
    ok &= _opaque(me, vuv, vmat)
    src = np.where(ok)[0] if np.any(ok) else np.arange(len(co))
    tree = cKDTree(co[src])
    verts, faces, grid = [], [], {}
    for e in range(rings + 1):
        el = -60.0 + 150.0 * e / rings
        for a in range(seg):
            az = 360.0 * a / seg
            u = np.array((math.sin(math.radians(az)) * math.cos(math.radians(el)),
                          -math.cos(math.radians(az)) * math.cos(math.radians(el)), math.sin(math.radians(el))))
            p0 = skull.hc + u * skull.axes
            r = float(skull.inner(p0[None])[0]) * inset
            if skin is not None:                 # just over the scalp skin (the hair's roots tuck into it)
                r = float(skin.inner(p0[None])[0]) + lift / float(np.mean(skull.axes))
            grid[e, a] = len(verts)
            verts.append(skull.hc + u * r * skull.axes)
    verts = np.array(verts)
    keep = {}
    for e in range(rings):
        for a in range(seg):
            q = [grid[e, a], grid[e, (a + 1) % seg], grid[e + 1, (a + 1) % seg], grid[e + 1, a]]
            az = 360.0 * (a + 0.5) / seg
            el = -60.0 + 150.0 * (e + 0.5) / rings
            if el < _hairline(az, **hairline):
                continue
            faces.append(q)
    if not faces:
        return None
    used = sorted({i for f in faces for i in f})
    remap = {o: n for n, o in enumerate(used)}
    vs = verts[used]
    fs = [[remap[i] for i in f] for f in faces]
    # crown: close the top
    m = bpy.data.meshes.new("HairCap")
    m.from_pydata([tuple(v) for v in vs], [], [tuple(f) for f in fs])
    m.update()
    _, near = tree.query(vs)
    near = src[near]
    for mt in me.materials:
        m.materials.append(mt)
    for p in m.polygons:
        p.material_index = int(np.bincount(vmat[near[list(p.vertices)]]).argmax())
        p.use_smooth = True
    uv = m.uv_layers.new(name=uvl.name if uvl is not None else "UVMap")
    for l in m.loops:
        uv.data[l.index].uv = vuv[near[l.vertex_index]].tolist()
    # outward normals: faces were wound by increasing azimuth / elevation
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(m)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(m)
    bm.free()
    cap = bpy.data.objects.new("HairCap", m)
    bpy.context.scene.collection.objects.link(cap)
    cap.parent = obj.parent
    vg = cap.vertex_groups.new(name="head")
    vg.add(list(range(len(vs))), 1.0, "REPLACE")
    mod = cap.modifiers.new("Armature", "ARMATURE")
    mod.object = obj.parent
    obj["da_hair_cap"] = cap.name
    return cap


def kept_vertices(obj, keep):
    """Vertices on faces whose material name contains one of `keep`."""
    me = obj.data
    out = np.zeros(len(me.vertices), bool)
    if not keep:
        return out
    hit = {i for i, m in enumerate(me.materials) if m is not None and any(k in m.name for k in keep)}
    for p in me.polygons:
        if p.material_index in hit:
            out[list(p.vertices)] = True
    return out


# --------------------------------------------------------------------------- driver
def axes_of(face):
    """Skull semi-axes (x, y, z) from the face mesh bounding box."""
    _, w, lo, hi = HD.head_frame(face)
    return (w * 0.5, w * 0.55, w * 0.62)


def shape(obj, face, spec, log=print, skin=None):
    """Apply spec {flow, clump, widen, volume, envelope} to the hair object; returns (rest positions,
    new positions) of its vertices (the deformation for hairrig.follow) and the under-layer object."""
    hc = HD.head_center(face)
    S = Strands(obj, hc)
    co = S.co0.copy()
    # accessories in the hair mesh (clips, ribbons: materials named in spec["keep"]) stay exactly as they are
    frozen = kept_vertices(obj, spec.get("keep", ()))
    S.live &= ~np.array([frozen[idx].any() for idx in S.idx], bool) if S.n else S.live

    def hold(c):
        c[frozen] = S.co0[frozen]
        return c

    if spec.get("flow"):
        co = hold(flow(S, co, **spec["flow"]))
    if spec.get("coherence", 0.015):
        co = hold(smooth_field(S.co0, co, spec.get("coherence", 0.015)))
    if spec.get("clump"):
        co = hold(clump(S, co, **spec["clump"]))
    if spec.get("widen"):
        w = spec["widen"]
        co = hold(widen(S, co, **(w if isinstance(w, dict) else dict(k=w))))
    axes = axes_of(face)
    if spec.get("volume"):
        skull = Skull(hc[:], S.co0[~frozen] if (~frozen).any() else S.co0, axes)
        grown = volume(S, co, skull, **spec["volume"])
        co = hold(smooth_field(co, grown, spec.get("coherence", 0.015) * 1.3, iters=2))   # the growth only
    if spec.get("envelope"):
        # locks hanging past the jaw (twin tails, long hair) keep their line; face-framing locks are bounded
        env = dict(spec["envelope"])
        jaw_z = env.get("neck_z") if env.get("neck_z") is not None else hc.z - 1.5 * axes[0]
        tips = np.array([co[idx][np.argmax(S.t[idx])][2] for idx in S.idx]) if S.n else np.zeros(0)
        hanging = ((S.L >= LONG) & (tips < jaw_z))[S.lab] if S.n else None
        co = hold(envelope(co, np.array(hc[:]), axes[0], free=hanging, **env))
    obj["da_hair_keep"] = list(spec.get("keep", ()))
    me = obj.data
    me.vertices.foreach_set("co", co.ravel())
    me.update()
    cap = None
    if spec.get("under", True):
        sk = Skull(hc[:], skin, axes, outer=True) if skin is not None and len(skin) else None
        cap = under_layer(obj, face, Skull(hc[:], S.co0, axes), sk, roots=S.t < 0.15, **(spec["under"] if isinstance(spec.get("under"), dict) else {}))
    w0 = float(np.ptp(S.co0[:, 0]))
    w1 = float(np.ptp(co[:, 0]))
    log(f"  anime: hair {obj.name}: {int(S.live.sum())} strands shaped, width {w0 * 100:.1f} -> {w1 * 100:.1f} cm")
    return S.co0, co, cap
