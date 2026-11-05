"""
Cloth fit audit for the anime cast (Blender).

Tailored clothes are only as good as they look in motion: skinning moves every layer with its own bone
weights, so a shirt that clears the jacket in the rest pose can still poke through it at the elbow of a run,
or a thigh can push out of a skirt in a stride. This audit skins the finished mesh into real frames of the
cast's takes and measures, per character and per pose:

  poke     vertices of an inner layer (skin < trousers / gloves < shirt / skirt / boots < jacket / collar <
           capelet) that end up *outside* a layer above them: the nearest point of the outer garment is
           within 3 cm and the inner vertex sits above that surface (along its normal, not past its edge)
  depth    how far the worst one sticks out (mm)
  open     open edges that are not part of a garment's intended hem / cuff / neckline / opening loop
           (holes in the cloth)

    python Tools/fit_check.py [ids...] [--poses Idle,Walk,Run,Duel,Sit,Talk] [--json out.json]

fit_report() returns the numbers; the CLI prints a table and exits 1 when a character is over budget.
"""

import re

import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

# inner -> outer layer of every garment material (M_Anime_<Key>_<Garment>[_JacketTint])
LAYER = {"skin": 0, "Pants": 1, "Gloves": 1, "Shirt": 2, "Skirt": 2, "Boots": 2, "Jacket": 3, "Collar": 3,
         "Capelet": 4}
GARMENTS = ("Pants", "Gloves", "Shirt", "Skirt", "Boots", "Jacket", "Collar", "Capelet")
STIFF = ("Capelet", "Collar")   # stiff pieces: fit relaxation tucks what is under them instead of pushing them
STIFF_GIVE = 0.004               # ...and moves a stiff piece itself at most this far
REACH = 0.03         # an outer surface further away than this does not cover the vertex
EPS = 0.0015         # tolerance above the outer surface (shading / outline thickness)
COS_ABOVE = 0.55     # the offset must point along the outer surface's normal (not past its edge)

# frames (fraction of the take) that load a garment the most
POSES = {
    "Idle": (0.0, 0.5),
    "Walk": (0.0, 0.25, 0.5, 0.75),
    "Run": (0.0, 0.2, 0.4, 0.6, 0.8),
    "Duel": (0.0, 0.5),
    "Sit": (0.5,),
    "Talk": (0.25, 0.75),
}

# budgets: poking vertices allowed per pose (a few at grazing seams are invisible) and depth in mm
BUDGET_COUNT = 12
BUDGET_DEPTH = 4.0


def _layer_of(mat_name):
    from .cel import classify
    base = re.sub(r"_JacketTint$", "", mat_name)
    for g in GARMENTS:
        if base.endswith("_" + g):
            return g
    if classify(mat_name) in ("skin", "face"):
        return "skin"
    return None


def _groups(obj):
    """{layer name: face indices} of the final cast mesh (outline hull and hair excluded)."""
    out = {}
    me = obj.data
    names = [m.name if m else "" for m in me.materials]
    for p in me.polygons:
        g = _layer_of(names[p.material_index]) if p.material_index < len(names) else None
        if g:
            out.setdefault(g, []).append(p.index)
    return out


def _evaluated(obj):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(dg)
    me = ev.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    nrm = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("normal", nrm)
    ev.to_mesh_clear()
    mw = np.array(obj.matrix_world)
    co = co.reshape(-1, 3) @ mw[:3, :3].T + mw[:3, 3]
    return co, nrm.reshape(-1, 3) @ mw[:3, :3].T


def _tris(faces):
    out = []
    for f in faces:
        for k in range(1, len(f) - 1):
            out.append((f[0], f[k], f[k + 1]))
    return np.array(out, np.int64)


def _bvh(co, faces):
    tris = _tris(faces)
    return BVHTree.FromPolygons([tuple(c) for c in co], [tuple(t) for t in tris], all_triangles=True), tris


def _intended_open(obj, groups, covered=None):
    """Count open edges per garment that are not on one of its long boundary loops (hem, cuff, neckline,
    opening): short isolated open runs are holes - unless an outer garment lies over them at rest (the edge of
    a hidden-surface cut-out under a jacket is not visible). Welded by position (UV seams split the vertices)."""
    me = obj.data
    co = np.array([v.co[:] for v in me.vertices])
    key = np.round(co / 1e-5).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    hidden = set()
    for vs in (covered or {}).values():
        hidden.update(int(inv[v]) for v in vs)
    holes = {}
    for g, faces in groups.items():
        if g in ("skin", "Gloves"):          # fingerless gloves have their thumb openings
            continue
        count = {}
        for fi in faces:
            vs = [inv[v] for v in me.polygons[fi].vertices]
            for a, b in zip(vs, vs[1:] + vs[:1]):
                if a != b:
                    e = (min(a, b), max(a, b))
                    count[e] = count.get(e, 0) + 1
        open_e = [e for e, c in count.items() if c == 1]
        # connected runs of open edges
        adj = {}
        for a, b in open_e:
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
        seen, small = set(), 0
        for start in adj:
            if start in seen:
                continue
            stack, run = [start], []
            seen.add(start)
            while stack:
                v = stack.pop()
                run.append(v)
                for w in adj[v]:
                    if w not in seen:
                        seen.add(w)
                        stack.append(w)
            if len(run) < 12 and sum(1 for v in run if v in hidden) < 0.8 * len(run):
                small += len(run)            # a real hem / cuff / neckline loop has many vertices
        holes[g] = small
    return holes


DENSE_STEP = 2          # dense audit: every other frame of every take


def pose_frames(arm, take_names=None, log=print, dense=False):
    """[(pose, frame)] after baking the audited takes onto arm (actions kept on arm.animation_data)."""
    from . import build as B
    from . import retarget as RT
    from .. import thirdparty
    out = []
    reg = thirdparty.registry().get("anime", {})
    for pose, fracs in POSES.items():
        if take_names and pose not in take_names:
            continue
        if pose in B.AUTHORED:
            act = RT.pose_action(arm, f"fit_{pose}", B.AUTHORED[pose][0](arm))
        else:
            key = dict((s, k) for s, k, _ in B.TAKES).get(pose)
            spec = reg.get(key) if key else None
            if not spec:
                continue
            src = RT.Source(thirdparty.tp_path(spec["file"]))
            act = RT.bake(src, spec["take"], arm, f"fit_{pose}", arm_drop=spec.get("arm_drop", 0.0))
            src.remove()
        f0, f1 = (int(round(v)) for v in act.frame_range)
        if dense:
            frames = list(range(f0, f1 + 1, DENSE_STEP))       # the whole take, every DENSE_STEP-th frame
        else:
            frames = [int(round(f0 + (f1 - f0) * t)) for t in fracs]
        out.append((pose, act, frames))
    return out


def _anchor(tree, tris, co, pts, reach=REACH):
    """Rest-pose covering triangle of each point: (point index, triangle, barycentric) for the points that lie
    under an outer surface (within reach, below it along its normal, not past its edge)."""
    keep, tri_of, bary = [], [], []
    for i, q in enumerate(pts):
        loc, nrm, ti, dist = tree.find_nearest(q, reach)
        if loc is None:
            continue
        d = q - np.array(loc)
        ln = float(np.linalg.norm(d))
        h = float(d @ np.array(nrm))
        if ln >= EPS and (h > EPS or abs(h) / ln < COS_ABOVE):
            continue
        a, b, c = co[tris[ti]]
        m = np.array([b - a, c - a]).T
        uv, *_ = np.linalg.lstsq(m, np.array(loc) - a, rcond=None)
        keep.append(i)
        tri_of.append(tris[ti])
        bary.append((1 - uv[0] - uv[1], uv[0], uv[1]))
    return np.array(keep, np.int64), np.array(tri_of, np.int64).reshape(-1, 3), np.array(bary).reshape(-1, 3)


def _edge_tris(obj, faces, tris):
    """Per triangle: True when one of its edges is an open edge (hem, cuff, vent) of the garment (welded)."""
    me = obj.data
    co = np.array([v.co[:] for v in me.vertices])
    inv = np.unique(np.round(co / 1e-5).astype(np.int64), axis=0, return_inverse=True)[1].ravel()
    count = {}
    for f in faces:
        vs = [inv[v] for v in f]
        for a, b in zip(vs, vs[1:] + vs[:1]):
            if a != b:
                e = (min(a, b), max(a, b))
                count[e] = count.get(e, 0) + 1
    open_e = {e for e, c in count.items() if c == 1}
    out = np.zeros(len(tris), bool)
    for i, (a, b, c) in enumerate(tris):
        for x, y in ((a, b), (b, c), (c, a)):
            e = (min(inv[x], inv[y]), max(inv[x], inv[y]))
            if e in open_e:
                out[i] = True
                break
    return out


def _heights(co, pts_idx, tri_of, bary, slack=0.15):
    """Height of each anchored point above its (posed) covering triangle. A point that no longer projects onto
    that triangle (a vent or a hem swung away and uncovered it) is not poking through anything: -inf."""
    a, b, c = co[tri_of[:, 0]], co[tri_of[:, 1]], co[tri_of[:, 2]]
    p = a * bary[:, :1] + b * bary[:, 1:2] + c * bary[:, 2:3]
    n = np.cross(b - a, c - a)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    q = co[pts_idx]
    h = np.einsum("ij,ij->i", q - p, n)
    # barycentric coordinates of the projection onto the posed triangle
    proj = q - n * h[:, None]
    v0, v1, v2 = b - a, c - a, proj - a
    d00 = np.einsum("ij,ij->i", v0, v0)
    d01 = np.einsum("ij,ij->i", v0, v1)
    d11 = np.einsum("ij,ij->i", v1, v1)
    d20 = np.einsum("ij,ij->i", v2, v0)
    d21 = np.einsum("ij,ij->i", v2, v1)
    den = np.maximum(d00 * d11 - d01 * d01, 1e-18)
    wv = (d11 * d20 - d01 * d21) / den
    ww = (d00 * d21 - d01 * d20) / den
    wu = 1 - wv - ww
    slack = np.broadcast_to(np.asarray(slack, float), wu.shape)
    inside = (wu > -slack) & (wv > -slack) & (ww > -slack)
    return np.where(inside, h, -np.inf)


def audit(obj, arm, poses, log=print):
    """Fit numbers of one built cast mesh: {pose: {"poke": {pair: n}, "depth": mm, "float": n}}, holes.

    Coverage comes from the rest pose: every inner vertex that an outer garment lies over is anchored to the
    covering triangle (barycentric point). In each posed frame its height above that same triangle is
    measured: positive means it broke through the garment covering it. (Measuring against whatever outer
    surface happens to be nearest would count an arm resting on the torso as the shirt poking out.)"""
    from . import correctives
    from . import retarget as RT
    me = obj.data
    groups = _groups(obj)
    faces_all = [tuple(p.vertices) for p in me.polygons]
    verts_of = {g: np.array(sorted({v for fi in f for v in me.polygons[fi].vertices})) for g, f in groups.items()}
    scene = bpy.context.scene
    outers = [g for g in groups if g != "skin"]
    RT._assign(arm, None)
    arm.data.pose_position = "REST"
    if me.shape_keys:
        for kb in me.shape_keys.key_blocks[1:]:
            kb.value = 0.0
    co, _ = _evaluated(obj)
    arm.data.pose_position = "POSE"
    anchors = {}
    for outer in outers:
        ofaces = [faces_all[fi] for fi in groups[outer]]
        tree, tris = _bvh(co, ofaces)
        edge = _edge_tris(obj, ofaces, tris)
        tri_key = {tuple(t): e for t, e in zip(tris.tolist(), edge)}
        for inner, iv in verts_of.items():
            if LAYER[outer] <= LAYER[inner] or not len(iv):
                continue
            keep, tri_of, bary = _anchor(tree, tris, co, co[iv])
            if len(keep):
                # at an open edge (vent, hem) a point that leaves the triangle is uncovered, not poking:
                # exact projection there, a little slack between neighbouring triangles elsewhere
                slack = np.array([0.0 if tri_key.get(tuple(t), False) else 0.15 for t in tri_of.tolist()])
                anchors[(inner, outer)] = (iv[keep], tri_of, bary, slack)
    result = {}
    for pose, act, frames in poses:
        RT._assign(arm, act)
        worst = 0.0
        pairs = {}
        for fr in frames:
            scene.frame_set(fr)
            correctives.apply(obj, arm)          # the thigh-driven corrective morphs, as Unreal drives them
            co, _ = _evaluated(obj)
            for (inner, outer), (idx, tri_of, bary, slack) in anchors.items():
                h = _heights(co, idx, tri_of, bary, slack)
                bad = h > EPS
                if bad.any():
                    k = f"{inner}>{outer}"
                    pairs[k] = max(pairs.get(k, 0), int(bad.sum()))
                    worst = max(worst, float(h[bad].max()) * 1000.0)
        result[pose] = dict(poke=pairs, depth=round(worst, 1))
    RT._assign(arm, None)
    covered = {}
    for (inner, _), (idx, _, _, _) in anchors.items():
        covered.setdefault(inner, set()).update(int(i) for i in idx)
    return result, _intended_open(obj, groups, covered)


def _relax_anchors(rest, groups, faces_all, verts_of, outers):
    """[(inner vertex ids, covering triangles, barycentrics, mode)] - mode: push the outer garment out, tuck
    the inner layer in (under stiff pieces), or both (trousers / shirt under a coat)."""
    anchors = []
    for outer in outers:
        tree, tris = _bvh(rest, [faces_all[fi] for fi in groups[outer]])
        for inner, iv in verts_of.items():
            if LAYER[outer] <= LAYER[inner] or not len(iv):
                continue
            keep, tri_of, bary = _anchor(tree, tris, rest, rest[iv])
            if len(keep):
                if outer in STIFF:
                    mode = "tuck"
                elif outer == "Jacket" and inner in ("Pants", "Shirt"):
                    mode = "both"
                else:
                    mode = "push"
                anchors.append((iv[keep], tri_of, bary, mode))
    return anchors


def relax(obj, arm, log=print, iterations=12, margin=0.002, max_push=0.03, max_tuck=0.015, shape_fn=None):
    """Fit relaxation (build time, before the outline hull): pose the mesh through the audited takes, find every
    covered inner vertex that breaks through its covering triangle, and push that triangle's vertices out at
    rest (along their normals, smoothed over their neighbours) by the worst overshoot plus margin. Repeats until
    the poses are clear or `iterations` is used up. Stiff pieces (capelet, collar) are not pushed: the hidden
    inner vertex under them is tucked in instead. Returns the remaining poking vertex count."""
    from . import retarget as RT
    me = obj.data
    poses = pose_frames(arm, None, log)
    groups = _groups(obj)
    faces_all = [tuple(p.vertices) for p in me.polygons]
    verts_of = {g: np.array(sorted({v for fi in f for v in me.polygons[fi].vertices})) for g, f in groups.items()}
    outers = [g for g in groups if g != "skin"]
    nbr = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nbr[a].append(b)
        nbr[b].append(a)
    left = 0
    anchors = None
    best_left, best_co = None, None
    for it in range(iterations):
        RT._assign(arm, None)
        arm.data.pose_position = "REST"
        rest, rest_n = _evaluated(obj)
        arm.data.pose_position = "POSE"
        # coverage only ever grows: pairs found on an earlier pass stay anchored to their triangle (stable), the
        # relaxed shape can add new ones (the audit sees the final shape, so relaxation must too)
        fresh = _relax_anchors(rest, groups, faces_all, verts_of, outers)
        if anchors is None:
            anchors = fresh
        else:
            known = {}
            for k, (idx, _, _, _) in enumerate(anchors):
                known.setdefault(k, set(int(i) for i in idx))
            merged = []
            for (idx, tri_of, bary, mode), (fidx, ftri, fbary, fmode) in zip(anchors, fresh) \
                    if len(anchors) == len(fresh) else []:
                have = set(int(i) for i in idx)
                add = np.array([j for j, i in enumerate(fidx) if int(i) not in have], np.int64)
                if len(add):
                    idx = np.concatenate([idx, fidx[add]])
                    tri_of = np.concatenate([tri_of, ftri[add]])
                    bary = np.concatenate([bary, fbary[add]])
                merged.append((idx, tri_of, bary, mode))
            anchors = merged if merged else anchors + fresh
        worst = [np.full(len(a[0]), -1.0) for a in anchors]
        scene = bpy.context.scene
        base = np.array([v.co[:] for v in me.vertices]) if shape_fn else None
        for pose, act, frames in poses:
            RT._assign(arm, act)
            for fr in frames:
                scene.frame_set(fr)
                extra = shape_fn(arm) if shape_fn else None
                if extra is not None:
                    me.vertices.foreach_set("co", (base + extra).ravel())
                    me.update()
                co, _ = _evaluated(obj)
                if extra is not None:
                    me.vertices.foreach_set("co", base.ravel())
                    me.update()
                for k, (idx, tri_of, bary, _) in enumerate(anchors):
                    worst[k] = np.maximum(worst[k], _heights(co, idx, tri_of, bary))
        RT._assign(arm, None)
        # displacements along the covering triangle's rest normal: the coat moves out, the layer under it in
        nv = len(me.vertices)
        disp = np.zeros((nv, 3))
        mag = np.zeros(nv)
        left = 0

        def add(vi, vec):
            m = float(np.linalg.norm(vec))
            if m > mag[vi]:
                mag[vi] = m
                disp[vi] = vec
        for (idx, tri_of, bary, mode), w in zip(anchors, worst):
            bad = w > EPS
            left += int(bad.sum())
            if not bad.any():
                continue
            a_, b_, c_ = rest[tri_of[bad, 0]], rest[tri_of[bad, 1]], rest[tri_of[bad, 2]]
            n_ = np.cross(b_ - a_, c_ - a_)
            n_ /= np.maximum(np.linalg.norm(n_, axis=1, keepdims=True), 1e-12)
            need = w[bad] + margin
            if mode == "tuck":
                # under a stiff piece: tuck the hidden layer in, and let the stiff piece give a few mm at most
                out_amt, in_amt = np.minimum(need * 0.3, STIFF_GIVE), np.minimum(need, max_tuck)
            elif mode == "both":
                # trousers / shirt under a coat (covered nearly always): they may tuck in as far as the coat
                # loosens
                out_amt, in_amt = np.minimum(need * 0.5, max_push), np.minimum(need * 0.5, max_tuck)
            else:
                out_amt, in_amt = np.minimum(need, max_push), np.zeros_like(need)
            for k, (vi, tri, bw) in enumerate(zip(idx[bad], tri_of[bad], bary[bad])):
                if in_amt[k] > 0:
                    add(vi, -n_[k] * in_amt[k])
                if out_amt[k] > 0:
                    for tv, x in zip(tri, bw):
                        add(tv, n_[k] * out_amt[k] * (0.5 + 0.5 * x))
        if best_left is None or left < best_left:       # keep the best state (a pass can overshoot)
            best_left = left
            best_co = np.array([v.co[:] for v in me.vertices])
        if not left:
            break
        # spread over the neighbourhood (no dents / spikes) and keep seam copies together
        for _ in range(2):
            nxt, nmag = disp.copy(), mag.copy()
            for vi in np.nonzero(mag > 0)[0]:
                for u in nbr[vi]:
                    if mag[vi] * 0.6 > nmag[u]:
                        nmag[u] = mag[vi] * 0.6
                        nxt[u] = disp[vi] * 0.6
            disp, mag = nxt, nmag
        co0 = np.array([v.co[:] for v in me.vertices])
        key = np.round(co0 / 1e-5).astype(np.int64)
        _, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.ravel()
        best = np.full(inv.max() + 1, -1.0)
        pick = np.zeros((inv.max() + 1, 3))
        for vi in np.nonzero(mag > 0)[0]:
            g_ = inv[vi]
            if mag[vi] > best[g_]:
                best[g_] = mag[vi]
                pick[g_] = disp[vi]
        disp = np.where(best[inv][:, None] > 0, pick[inv], 0.0)
        me.vertices.foreach_set("co", (co0 + disp).ravel())
        me.update()
        moved = np.linalg.norm(disp, axis=1)
        log(f"  anime: {obj.name}: fit relax pass {it + 1}: {left} poking vertices, "
            f"{int((moved > 0).sum())} cloth vertices moved (max {moved.max() * 1000:.1f} mm)")
    if best_co is not None and best_left is not None and best_left < left:
        me.vertices.foreach_set("co", best_co.ravel())
        me.update()
        left = best_left
        log(f"  anime: {obj.name}: fit relax kept the best pass ({left} poking vertices)")
    for pose, act, _ in poses:
        bpy.data.actions.remove(act)
    return left


def fit_report(ids=None, takes=None, log=print, dense=False):
    """Build every cast member and audit it. Returns {cid: {"poses": ..., "holes": ...}}. Building a member
    paints its textures: they go to a temporary directory, so an audit never touches SourceAssets."""
    import os
    import shutil
    import tempfile
    from .. import config as C
    saved = C.OUT_TEXTURES
    tmp = tempfile.mkdtemp(prefix="da_fit_")
    try:
        C.OUT_TEXTURES = tmp
        os.makedirs(os.path.join(tmp, "Characters"), exist_ok=True)
        return _fit_report(ids, takes, log, dense)
    finally:
        C.OUT_TEXTURES = saved
        shutil.rmtree(tmp, ignore_errors=True)


def _fit_report(ids=None, takes=None, log=print, dense=False):
    from .. import blend
    from . import build as B
    from . import cast as CAST
    from . import models as M
    entries = CAST.all_entries()
    ids = ids or [c for c in entries]
    out = {}
    for cid in ids:
        e = entries[cid]
        if not M.model_available(e):
            continue
        blend.reset_scene()
        bpy.context.scene.render.fps = 30
        arm, obj = M.build_model(cid, e, B.key_name, log=lambda *a: None)
        poses = pose_frames(arm, takes, log, dense=dense)
        res, holes = audit(obj, arm, poses, log)
        out[cid] = dict(poses=res, holes=holes)
        log(summary_line(cid, out[cid]))
    return out


def over_budget(rep):
    bad = []
    for pose, r in rep["poses"].items():
        n = max(r["poke"].values()) if r["poke"] else 0
        if n > BUDGET_COUNT or r["depth"] > BUDGET_DEPTH:
            bad.append(pose)
    return bad


def summary_line(cid, rep):
    parts = []
    for pose, r in rep["poses"].items():
        n = sum(r["poke"].values())
        parts.append(f"{pose} {n}/{r['depth']}mm")
    holes = sum(rep["holes"].values())
    bad = over_budget(rep)
    tag = "OK  " if not bad and not holes else "FAIL"
    return f"  fit {tag} {cid:11s} " + " | ".join(parts) + f" | holes {holes}" + (f"  over: {','.join(bad)}" if bad else "")


def snap_residuals(obj, arm, log=print, shape_fn=None, rounds=6, ring=0.5, tuck=0.003):
    """Last step of the fit (build time): a covered inner vertex that still breaks through its covering
    triangle in some posed frame takes that triangle's interpolated bone weights and corrective displacement
    (it can then only move with the cloth over it), tucked `tuck` under it; its 1-ring blends `ring` of the
    way so no kink shows. Repeats `rounds` times. Returns the vertices still poking."""
    from . import retarget as RT
    from .models import MORPH_ATTR
    me = obj.data
    groups = _groups(obj)
    faces_all = [tuple(p.vertices) for p in me.polygons]
    verts_of = {g: np.array(sorted({v for fi in f for v in me.polygons[fi].vertices})) for g, f in groups.items()}
    outers = [g for g in groups if g != "skin"]
    poses = pose_frames(arm, None, log)
    nbr = [[] for _ in me.vertices]
    for e in me.edges:
        a, b = e.vertices
        nbr[a].append(b)
        nbr[b].append(a)
    attrs = [a.name for a in me.attributes if a.name.startswith(MORPH_ATTR)]
    # on the final (joined) mesh the correctives are real shape keys: drive them per frame and edit them
    keys = [kb for kb in (me.shape_keys.key_blocks[1:] if me.shape_keys else []) if kb.name.startswith("Fit_")]
    from . import correctives
    left = 0
    for rnd in range(rounds):
        RT._assign(arm, None)
        arm.data.pose_position = "REST"
        for kb in keys:
            kb.value = 0.0
        rest, _ = _evaluated(obj)
        arm.data.pose_position = "POSE"
        anchors = _relax_anchors(rest, groups, faces_all, verts_of, outers)
        worst = [np.full(len(a[0]), -np.inf) for a in anchors]
        base = np.array([v.co[:] for v in me.vertices])
        scene = bpy.context.scene
        for pose, act, frames in poses:
            RT._assign(arm, act)
            for fr in frames:
                scene.frame_set(fr)
                if keys:
                    correctives.apply(obj, arm)
                extra = shape_fn(arm) if shape_fn else None
                if extra is not None:
                    me.vertices.foreach_set("co", (base + extra).ravel())
                    me.update()
                co, _ = _evaluated(obj)
                if extra is not None:
                    me.vertices.foreach_set("co", base.ravel())
                    me.update()
                for k, (idx, tri_of, bary, _) in enumerate(anchors):
                    worst[k] = np.maximum(worst[k], _heights(co, idx, tri_of, bary))
        RT._assign(arm, None)
        for kb in keys:
            kb.value = 0.0
        targets = {}
        for (idx, tri_of, bary, _), w in zip(anchors, worst):
            for vi, tri, b in zip(idx[w > EPS], tri_of[w > EPS], bary[w > EPS]):
                targets.setdefault(int(vi), (tri, b))
        left = len(targets)
        # every copy of a position (UV seams split vertices) is bound and moved together, or the seam opens
        cur = np.array([v.co[:] for v in me.vertices])
        keyp = np.round(cur / 1e-5).astype(np.int64)
        _, winv = np.unique(keyp, axis=0, return_inverse=True)
        winv = winv.ravel()
        copies = {}
        for vi, g in enumerate(winv):
            copies.setdefault(int(g), []).append(vi)
        for vi in list(targets):
            for twin in copies[int(winv[vi])]:
                targets.setdefault(twin, targets[vi])
        if not left:
            break
        vg = obj.vertex_groups
        co0 = np.array([v.co[:] for v in me.vertices])
        disp = {}
        for n in attrs:
            d = np.empty(len(me.vertices) * 3, np.float32)
            me.attributes[n].data.foreach_get("vector", d)
            disp[n] = d.reshape(-1, 3)
        for kb in keys:
            d = np.empty(len(me.vertices) * 3, np.float32)
            kb.data.foreach_get("co", d)
            disp[kb.name] = d.reshape(-1, 3) - co0
        for vi, (tri, b) in targets.items():
            w = {}
            for tv, x in zip(tri, b):
                for g in me.vertices[int(tv)].groups:
                    w[g.group] = w.get(g.group, 0.0) + g.weight * x
            a_, b_, c_ = co0[tri]
            n_ = np.cross(b_ - a_, c_ - a_)
            n_ /= max(np.linalg.norm(n_), 1e-12)
            under = co0[vi] - n_ * tuck              # stays where it is (bound), just a little deeper
            for u, k in [(vi, 1.0)] + [(j, ring) for j in nbr[vi]]:
                own = {g.group: g.weight for g in me.vertices[u].groups}
                mix = {g: own.get(g, 0.0) * (1 - k) + w.get(g, 0.0) * k for g in set(own) | set(w)}
                tot = sum(mix.values()) or 1.0
                for g in list(own):
                    if g not in mix or mix[g] <= 1e-5:
                        vg[g].remove([u])
                for g, x in mix.items():
                    if x > 1e-5:
                        vg[g].add([u], x / tot, "REPLACE")
                for n in attrs:
                    t = disp[n][tri[0]] * b[0] + disp[n][tri[1]] * b[1] + disp[n][tri[2]] * b[2]
                    disp[n][u] = disp[n][u] * (1 - k) + t * k
            me.vertices[vi].co = under
            co0[vi] = under
        for n in attrs:
            me.attributes[n].data.foreach_set("vector", disp[n].ravel())
        if keys:
            basis = me.shape_keys.key_blocks[0]
            basis.data.foreach_set("co", co0.astype(np.float32).ravel())
            for kb in keys:
                kb.data.foreach_set("co", (co0 + disp[kb.name]).astype(np.float32).ravel())
        me.update()
        log(f"  anime: {obj.name}: fit snap round {rnd + 1}: {left} covered vertices bound to the cloth over them")
    for pose, act, _ in poses:
        bpy.data.actions.remove(act)
    return left
