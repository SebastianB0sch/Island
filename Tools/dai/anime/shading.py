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
