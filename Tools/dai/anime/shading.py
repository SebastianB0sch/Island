"""
Geometry-side anime shading for the cast meshes (Blender).

face_normals(): anime faces are shaded as if they were a smooth egg, not a sculpted face - otherwise the
nose, lips and eye sockets throw blotchy cel shadows the moment the light moves. Every skin corner of the face
gets a custom normal blended from its own normal towards the normal of an ellipsoid fitted round the head
(the technique used by stylised fighting / gacha game characters). The custom normals are exported in the FBX
and Unreal imports them (importer: normal_import_method = IMPORT_NORMALS), and they deform with the skin.
The nose tip and the lips keep a little of their own normal so the face does not read as perfectly flat.
"""

import numpy as np

FACE_BLEND = 0.78          # 0 own normals .. 1 pure ellipsoid


def _face_skin_polys(me):
    from .cel import classify
    out = []
    for p in me.polygons:
        mat = me.materials[p.material_index] if p.material_index < len(me.materials) else None
        if mat is not None and classify(mat.name) == "face":
            out.append(p.index)
    return out


def face_normals(obj, arm=None, log=print, blend=FACE_BLEND):
    me = obj.data
    polys = _face_skin_polys(me)
    if not polys:
        return 0
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    vids = sorted({v for i in polys for v in me.polygons[i].vertices})
    pts = co[vids]
    lo, hi = pts.min(0), pts.max(0)
    w = float(hi[0] - lo[0])
    # ellipsoid round the skull: centre behind the face mask, a little above the eye line
    c = np.array((0.0, float(lo[1]) + w * 0.55, float(lo[2] + hi[2]) * 0.5 + w * 0.08))
    radii = np.array((w * 0.5, w * 0.58, w * 0.66))
    # current corner normals (custom normals are set for every corner of the mesh, so keep the rest as is)
    nl = len(me.loops)
    normals = np.empty(nl * 3)
    me.corner_normals.foreach_get("vector", normals)
    normals = normals.reshape(-1, 3)
    loop_vert = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", loop_vert)
    face_loops = np.array([li for i in polys for li in me.polygons[i].loop_indices], np.int64)
    p = co[loop_vert[face_loops]]
    e = (p - c) / radii ** 2
    e /= np.maximum(np.linalg.norm(e, axis=1, keepdims=True), 1e-9)
    own = normals[face_loops]
    # keep more of the own normal at the front centre (nose, lips) so the profile still reads
    front = np.clip((-(p[:, 1] - lo[1]) + w * 0.1) / (w * 0.2), 0, 1) * np.clip(1 - np.abs(p[:, 0]) / (w * 0.12), 0, 1)
    k = blend * (1 - 0.35 * front)
    n = own * (1 - k[:, None]) + e * k[:, None]
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    normals[face_loops] = n
    me.normals_split_custom_set([tuple(x) for x in normals])
    log(f"  anime: {obj.name}: smoothed face normals on {len(face_loops)} corners")
    return len(face_loops)


# --------------------------------------------------------------------------- hair
HAIR_BLEND = 0.82          # 0 own strand normals .. 1 pure volume normal
HAIR_SIGMA = 0.03          # m: spatial smoothing of the hair mass normal


def hair_normals(obj, arm=None, log=print, blend=HAIR_BLEND, sigma=HAIR_SIGMA):
    """Anime hair shades as one soft mass, not as a hundred thin strands: every hair corner's normal is blended
    towards a volume normal - the strands' own normals turned outwards (away from the skull) and averaged over
    everything within ~2 sigma, mixed with the normal of the ellipsoid round the head (a vertical cylinder below
    the head centre, where long hair hangs). One clean cel shadow line and one angel ring instead of streaks on
    every strand. Exported as custom normals like the face's."""
    from scipy.sparse import csr_matrix
    from scipy.spatial import cKDTree
    from .cel import classify
    me = obj.data
    hair_mats = {i for i, m in enumerate(me.materials)
                 if m is not None and classify(m.name) == "hair" and "band" not in m.name.lower()}
    polys = [p.index for p in me.polygons if p.material_index in hair_mats]
    face_polys = _face_skin_polys(me)
    if not polys or not face_polys:
        return 0
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    fv = sorted({v for i in face_polys for v in me.polygons[i].vertices})
    lo, hi = co[fv].min(0), co[fv].max(0)
    w = float(hi[0] - lo[0])
    c = np.array((0.0, float(lo[1]) + w * 0.55, float(lo[2] + hi[2]) * 0.5 + w * 0.08))
    radii = np.array((w * 0.5, w * 0.58, w * 0.66))
    nl = len(me.loops)
    normals = np.empty(nl * 3)
    me.corner_normals.foreach_get("vector", normals)
    normals = normals.reshape(-1, 3)
    loop_vert = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", loop_vert)
    loops = np.array([li for i in polys for li in me.polygons[i].loop_indices], np.int64)
    p = co[loop_vert[loops]]
    own = normals[loops]
    rel = p - c
    # ellipsoid above the head centre, easing into a vertical cylinder below it (hanging hair)
    e = rel / radii ** 2
    below = np.clip(-rel[:, 2] / (w * 0.6), 0, 1)
    e[:, 2] *= 1 - 0.85 * below
    e /= np.maximum(np.linalg.norm(e, axis=1, keepdims=True), 1e-9)
    # strand normals turned outwards, then averaged in space (the shape of the hair mass)
    out = np.where((np.einsum("ij,ij->i", own, e) < 0)[:, None], -own, own)
    # (binned into sigma / 2 cells first: all pairs of a dense head of hair within 2 sigma run into the
    # hundreds of millions)
    cell = 0.5 * sigma
    keys = np.floor(p / cell).astype(np.int64)
    _, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = inv.ravel()
    m = int(inv.max()) + 1
    cnt = np.bincount(inv, minlength=m).astype(np.float64)
    cen = np.stack([np.bincount(inv, weights=p[:, c], minlength=m) for c in range(3)], axis=1) / cnt[:, None]
    acc = np.stack([np.bincount(inv, weights=out[:, c], minlength=m) for c in range(3)], axis=1)
    tree = cKDTree(cen)
    pairs = tree.query_pairs(2.0 * sigma, output_type="ndarray")
    i = np.concatenate([pairs[:, 0], pairs[:, 1], np.arange(m)])
    j = np.concatenate([pairs[:, 1], pairs[:, 0], np.arange(m)])
    wt = np.exp(-(np.linalg.norm(cen[i] - cen[j], axis=1) / sigma) ** 2)
    cells = csr_matrix((wt, (i, j)), shape=(m, m)) @ acc
    dist, idx = tree.query(p, k=min(4, m))
    if idx.ndim == 1:
        dist, idx = dist[:, None], idx[:, None]
    wq = 1.0 / (dist ** 2 + (0.25 * cell) ** 2)
    mass = (cells[idx] * wq[..., None]).sum(1)
    mass /= np.maximum(np.linalg.norm(mass, axis=1, keepdims=True), 1e-9)
    vol = mass * 0.55 + e * 0.45
    vol /= np.maximum(np.linalg.norm(vol, axis=1, keepdims=True), 1e-9)
    # own normal oriented like the volume (the inner side of a strand shades like its outer side)
    own_o = np.where((np.einsum("ij,ij->i", own, vol) < 0)[:, None], -own, own)
    nn = own_o * (1 - blend) + vol * blend
    nn /= np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
    normals[loops] = nn
    me.normals_split_custom_set([tuple(x) for x in normals])
    log(f"  anime: {obj.name}: hair volume normals on {len(loops)} corners")
    return len(loops)


# --------------------------------------------------------------------------- neck
NECK_SHADE = 0.80          # 0 own normals .. 1 fully turned down


def neck_shadow(obj, arm, log=print, strength=NECK_SHADE):
    """The shadow the head throws on the neck, the one piece of ambient occlusion every anime character has:
    the normals of the neck skin are turned downwards (strongest right under the jaw, fading out towards the
    collar bones), so the cel ramp puts the neck on the shadow side whatever the light does. Custom normals,
    exported like the face's."""
    from .cel import classify
    me = obj.data
    groups = {g.name: g.index for g in obj.vertex_groups}
    if arm is None or "neck_01" not in groups or "head" not in arm.data.bones or "neck_01" not in arm.data.bones:
        return 0
    skin = {i for i, m in enumerate(me.materials) if m is not None and classify(m.name) == "skin"}
    polys = [p for p in me.polygons if p.material_index in skin]
    if not polys:
        return 0
    want = {groups["neck_01"]} | ({groups["head"]} if "head" in groups else set())
    nv = len(me.vertices)
    w = np.zeros(nv)
    for v in me.vertices:
        for e in v.groups:
            if e.group in want:
                w[v.index] += e.weight
    co = np.empty(nv * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    z0 = float(arm.data.bones["neck_01"].head_local.z)
    z1 = float(arm.data.bones["head"].head_local.z)
    nl = len(me.loops)
    normals = np.empty(nl * 3)
    me.corner_normals.foreach_get("vector", normals)
    normals = normals.reshape(-1, 3)
    loop_vert = np.empty(nl, np.int64)
    me.loops.foreach_get("vertex_index", loop_vert)
    loops = np.array([li for p in polys for li in p.loop_indices], np.int64)
    vi = loop_vert[loops]
    z = co[vi, 2]

    def smooth(t):
        t = np.clip(t, 0.0, 1.0)
        return t * t * (3.0 - 2.0 * t)

    k = strength * smooth((w[vi] - 0.3) / 0.4) * smooth((z - (z0 - 0.005)) / max(0.6 * (z1 - z0), 0.01)) \
        * (1.0 - smooth((z - (z1 + 0.045)) / 0.02))
    sel = k > 1e-3
    if not sel.any():
        return 0
    down = np.array([0.0, 0.30, -1.0])
    down /= np.linalg.norm(down)
    n = normals[loops[sel]] * (1.0 - k[sel, None]) + down * k[sel, None]
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    normals[loops[sel]] = n
    me.normals_split_custom_set([tuple(x) for x in normals])
    log(f"  anime: {obj.name}: neck shadow normals on {int(sel.sum())} corners")
    return int(sel.sum())
