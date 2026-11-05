"""
Hair audit of the exported cast (the SK_Anime_*.fbx files Unreal imports): does each head of hair read as one
soft, coherent anime mass, and does it carry its fitted spring rig?

Per character, from the hair faces of the exported mesh (accessories a cast entry keeps, such as clips, left out):

  width          hair width above the chin over the face width (anime hair is big, but not a wide flare)
  holes          see-through holes inside the hair silhouette, front and side (separated locks), count and
                 share of the silhouette
  rough          silhouette perimeter over its convex hull's: 1 is a smooth outline, needles and ragged
                 strands push it up
  scalp_exposed  share of the skin on the back half of the head, above the ears, that is visible from behind
  rig            fitted HairJoint_<Key>_* chains the mesh is skinned to, and how many vertices they move
"""

import json
import os
import re

import numpy as np

# budget: what a coherent anime head of hair stays within
BUDGET = dict(width=1.75, holes=4, hole_frac=0.015, rough=1.6, scalp_exposed=0.02, min_chains=1)
RES = 320


def _tris(mesh, pred):
    me = mesh.data
    me.calc_loop_triangles()
    m = np.array(mesh.matrix_world)
    co = np.array([v.co[:] for v in me.vertices]) @ m[:3, :3].T + m[:3, 3]
    out = [co[list(t.vertices)] for t in me.loop_triangles
           if me.materials[t.material_index] is not None and pred(me.materials[t.material_index].name.lower())]
    return np.array(out) if out else np.zeros((0, 3, 3))


def _raster(tr, axes, lo, span):
    from PIL import Image, ImageDraw
    img = Image.new("L", (RES, RES), 0)
    d = ImageDraw.Draw(img)
    for t in tr:
        p = (t[:, axes] - lo) / span * (RES - 1)
        d.polygon([(float(x), float(RES - 1 - y)) for x, y in p], fill=255)
    return np.asarray(img) > 0


def _shape(mask):
    from scipy import ndimage
    from scipy.spatial import ConvexHull
    lab, n = ndimage.label(~mask)
    border = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])).tolist())
    sizes = ndimage.sum(np.ones_like(lab), lab, index=range(1, n + 1)) if n else []
    holes = [(i + 1, s) for i, s in enumerate(sizes) if (i + 1) not in border]
    area = int(mask.sum())
    edge = mask ^ ndimage.binary_erosion(mask)
    ys, xs = np.nonzero(edge)
    hull = ConvexHull(np.stack([xs, ys], 1)) if len(xs) > 3 else None
    return dict(holes=sum(1 for _, s in holes if s > 3), hole_frac=round(sum(s for _, s in holes) / max(area, 1), 4),
                rough=round(int(edge.sum()) / max(hull.area if hull else 1.0, 1e-6), 3))


def measure(path, keep=()):
    """Metrics of one exported cast FBX (imported into the current Blender scene and removed again)."""
    import bpy
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    try:
        arm = next(o for o in new if o.type == "ARMATURE")
        mesh = next(o for o in new if o.type == "MESH")
        keep = tuple(k.lower() for k in keep)
        hair = _tris(mesh, lambda n: "hair" in n and "band" not in n and "outline" not in n
                     and not any(k in n for k in keep))
        face = _tris(mesh, lambda n: "face" in n and "skin" in n)
        skin = _tris(mesh, lambda n: "skin" in n and "outline" not in n)
        fv, hv = face.reshape(-1, 3), hair.reshape(-1, 3)
        chin, top = float(fv[:, 2].min()), float(max(hv[:, 2].max(), fv[:, 2].max()))
        out = dict(width=round(float(np.ptp(hv[hv[:, 2] > chin][:, 0])) / float(np.ptp(fv[:, 0])), 3))
        c = np.array([0.0, float(fv[:, 1].mean()), (chin + top) / 2])
        span = 1.2 * max(np.ptp(hv[:, 0]), np.ptp(hv[:, 1]), top - chin)
        near = lambda tr: tr[tr[:, :, 2].mean(1) > chin - 0.02] if len(tr) else tr
        hh, ss = near(hair), near(skin)
        for view, ax in (("front", [0, 2]), ("side", [1, 2])):
            out[view] = _shape(_raster(hh, ax, c[ax] - span / 2, span))
        lo = c[[0, 2]] - span / 2
        back = ss[(ss[:, :, 1].mean(1) > c[1]) & (ss[:, :, 2].mean(1) > c[2] - 0.02)]
        sk = _raster(back, [0, 2], lo, span)
        out["scalp_exposed"] = round(float((sk & ~_raster(hh, [0, 2], lo, span)).sum()) / max(int(sk.sum()), 1), 4)
        groups = {g.index: g.name for g in mesh.vertex_groups if re.match(r"HairJoint_\w+?_(Short|Long)\d+_\d+$", g.name)}
        used, moved = set(), 0
        for v in mesh.data.vertices:
            hit = [groups[g.group] for g in v.groups if g.group in groups and g.weight > 1e-3]
            used.update(hit)
            moved += bool(hit)
        out["rig"] = dict(chains=len({n.rsplit("_", 1)[0] for n in used}), bones=len(used), vertices=moved,
                          skeleton_hair_bones=sum(1 for b in arm.data.bones if b.name.startswith("HairJoint")))
        return out
    finally:
        for o in new:
            bpy.data.objects.remove(o, do_unlink=True)


def over_budget(m):
    """Budget lines a measured character breaks (empty: within budget). A cast entry can widen a line for its
    design (hairdo shape "audit", e.g. twin tails spreading from the head: {"width": 2.45})."""
    b, bad = dict(BUDGET, **m.get("allow", {})), []
    if m["width"] > b["width"]:
        bad.append(f"width {m['width']:.2f} > {b['width']}")
    for v in ("front", "side"):
        if m[v]["holes"] > b["holes"] or m[v]["hole_frac"] > b["hole_frac"]:
            bad.append(f"{v} holes {m[v]['holes']} ({m[v]['hole_frac'] * 100:.1f} %)")
        if m[v]["rough"] > b["rough"]:
            bad.append(f"{v} outline rough {m[v]['rough']:.2f} > {b['rough']}")
    if m["scalp_exposed"] > b["scalp_exposed"]:
        bad.append(f"scalp exposed {m['scalp_exposed'] * 100:.1f} %")
    if m["rig"]["chains"] < b["min_chains"]:
        bad.append("no fitted hair chains")
    return bad


def report(ids=None, log=print):
    from . import build, cast as CAST
    entries = CAST.all_entries()
    rep = {}
    for cid in ids or list(entries):
        e = entries[cid]
        if not (e.get("hairdo") or {}).get("shape"):
            continue
        path = _fbx_path(build.key_name(cid))
        if not os.path.exists(path):
            log(f"  !! hair: {cid}: {path} missing (run Tools/build_island.py cast)")
            continue
        m = measure(path, keep=e["hairdo"]["shape"].get("keep", ()))
        m["allow"] = dict(e["hairdo"]["shape"].get("audit", {}))
        rep[cid] = m
        bad = over_budget(m)
        log(f"  hair {'OK  ' if not bad else 'OVER'} {cid:11s} width {m['width']:.2f}  holes {m['front']['holes']}/{m['side']['holes']}"
            f"  rough {m['front']['rough']:.2f}/{m['side']['rough']:.2f}  scalp {m['scalp_exposed'] * 100:.1f} %"
            f"  rig {m['rig']['chains']} chains / {m['rig']['vertices']} verts" + (f"  [{'; '.join(bad)}]" if bad else ""))
    return rep


def _fbx_path(key):
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.abspath(os.path.join(here, "..", "..", ".."))
    return os.path.join(repo, "DuelAcademyIsland", "SourceAssets", "Meshes", "Characters", "Anime", f"SK_Anime_{key}.fbx")


def to_json(rep, path):
    with open(path, "w") as fh:
        json.dump(rep, fh, indent=1)
