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
    tree = cKDTree(p)
    pairs = tree.query_pairs(2.0 * sigma, output_type="ndarray")
    n = len(p)
    i = np.concatenate([pairs[:, 0], pairs[:, 1], np.arange(n)])
    j = np.concatenate([pairs[:, 1], pairs[:, 0], np.arange(n)])
    wt = np.exp(-(np.linalg.norm(p[i] - p[j], axis=1) / sigma) ** 2)
    W = csr_matrix((wt, (i, j)), shape=(n, n))
    mass = W @ out
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
