"""
Hairstyles and head accessories on the base models' own hair (models.py).

VRoid hair is built from separate strands (one mesh island each), so a style is a per-strand edit:

  spike      rotate every strand about its root towards "out and up" and stretch it along its length
             (Jaden's and Chazz's spikier manes from the short base cut)
  source     borrow another base model's hair, fitted to this head by the two faces' bounding boxes and
             re-skinned to head + upper spine; with long_only just its strands that reach below the neck,
             tucked under this model's own cut (long straight hair for Alexis / Jasmine / Mindy / Crowler
             from VRoid B's tails under VRoid A's / C's own fringe)
  drop       materials of the borrowed hair to leave out (hair clips, ribbons)
  gradient   (v, softness): two-tone hair, a texture gradient along the strands into hair "color2"
             (Jaden's orange ends; applied in models.materials)

plus accessories built in place from the face landmarks: round glasses (Syrus) and a frilled ruff
(Crowler).
"""

import math

import bmesh
import bpy
import numpy as np
from mathutils import Quaternion, Vector
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .. import palette, thirdparty

def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def islands(me, weld=True):
    """Connected strand index per vertex (welded by position: UV seams split vertices)."""
    co = np.array([v.co[:] for v in me.vertices])
    e = np.array([ed.vertices[:] for ed in me.edges])
    _, inv = np.unique(np.round(co / (1e-5 if weld else 1e-12)).astype(np.int64), axis=0, return_inverse=True)
    inv = inv.ravel()
    n = inv.max() + 1
    g = coo_matrix((np.ones(len(e)), (inv[e[:, 0]], inv[e[:, 1]])), shape=(n, n))
    _, lab = connected_components(g, directed=False)
    return co, lab[inv]


def head_frame(face):
    """(centre, width) of the face mesh bounding box."""
    co = np.array([v.co[:] for v in face.data.vertices])
    lo, hi = co.min(0), co.max(0)
    return Vector(((lo + hi) / 2).tolist()), float(hi[0] - lo[0]), Vector(lo.tolist()), Vector(hi.tolist())


def head_center(face):
    c, w, lo, hi = head_frame(face)
    # the skull centre sits behind the face mask, about a third of a face width
    return Vector((0.0, hi.y + w * 0.05, c.z + w * 0.12))


# --------------------------------------------------------------------------- strand edits
def spike(obj, hc, lift=0.4, up=0.5, length=1.3, front_lift=0.15, front_length=1.1, min_len=0.03):
    me = obj.data
    co, lab = islands(me)
    new = co.copy()
    for i in range(lab.max() + 1):
        idx = np.where(lab == i)[0]
        p = co[idx]
        d = np.linalg.norm(p - np.array(hc), axis=1)
        root = p[np.argsort(d)[:max(3, len(idx) // 12)]].mean(0)
        far = p[np.argmax(np.linalg.norm(p - root, axis=1))]
        axis = Vector(far - root)
        L = axis.length
        if L < min_len:
            continue
        a = axis.normalized()
        out = (Vector(root) - hc)
        out = out.normalized() if out.length > 1e-6 else Vector((0, 0, 1))
        front = out.y < -0.45 and far[2] < hc.z + 0.04
        tgt = (out + Vector((0, 0, up))).normalized()
        q = a.rotation_difference(tgt)
        f, k = (front_lift, front_length) if front else (lift, length)
        q = Quaternion().slerp(q, f)
        for j, vi in enumerate(idx):
            rel = Vector(p[j] - root)
            along = rel.dot(a)
            rel = rel + a * along * (k - 1.0)
            new[vi] = (Vector(root) + q @ rel)[:]
    for v, c in zip(me.vertices, new):
        v.co = c
    me.update()


# --------------------------------------------------------------------------- borrowed hair
def borrow(src_key, arm, meshes, rig_neck, rig_chest, drop=(), log=print, long_only=False, bury=0.75):
    """Replace the model's hair with base model src_key's hair (long_only: keep this model's own cut and add
    just the borrowed strands that reach below the neck, their tied-up tops pulled in under the own hair).
    Returns the new hair object and the alpha modes of its materials (for models.materials)."""
    from . import models as M
    path = thirdparty.tp_path(thirdparty.registry()["anime_models"][src_key]["file"])
    alpha = M.alpha_modes(path)
    face = next(m for m in meshes if m.name.startswith("Face"))
    old = [m for m in meshes if m.name.startswith("Hair")]
    a2, m2 = M.load(path, log)
    hair = next(m for m in m2 if m.name.startswith("Hair"))
    face2 = next(m for m in m2 if m.name.startswith("Face"))
    c_t, w_t, lo_t, hi_t = head_frame(face)
    c_s, w_s, lo_s, hi_s = head_frame(face2)
    s = w_t / w_s
    # anchor: the top of the face / brow line, so the fringe sits where the old one did
    ref_t = Vector((c_t.x, hi_t.y, hi_t.z))
    ref_s = Vector((c_s.x, hi_s.y, hi_s.z))
    me = hair.data
    for v in me.vertices:
        v.co = ref_t + (v.co - ref_s) * s
    hc = head_center(face)
    long_isl = None
    if long_only:
        co, lab = islands(me)
        low = {int(l) for l in np.unique(lab[co[:, 2] < rig_neck])}
        long_isl = lab
        cut = hc.z - 0.02
        # straighten the tied-up top of every long strand: shift it over the strand's hanging part, pulled in
        # towards the head so it disappears under this model's own hair
        z_band = cut - 0.13
        for l in low:
            idx = np.where(lab == l)[0]
            p = co[idx]
            band = p[(p[:, 2] > z_band - 0.03) & (p[:, 2] < z_band + 0.01)]
            upper = p[:, 2] > z_band
            if not len(band) or not upper.any():
                continue
            hang = band[:, :2].mean(0)
            target = np.array(hc[:2]) + (hang - np.array(hc[:2])) * bury
            shift = target - p[upper, :2].mean(0)
            for j in idx[upper]:
                v = me.vertices[j]
                t = _smooth((v.co.z - z_band) / 0.10)
                v.co.x += shift[0] * t
                v.co.y += shift[1] * t
    if long_only:
        # gather what is left of the tied-up tails into a cone under the own hair: radius from the head axis
        # limited to the bob near the neck, opening out further down the back
        ax = np.array((0.0, hc.y + 0.02))
        top = rig_neck + 0.04
        for v, l in zip(me.vertices, long_isl):
            if int(l) not in low or v.co.z < top - 0.30:
                continue
            lim = 0.10 + 0.55 * max(0.0, top - v.co.z)
            d = np.array((v.co.x, v.co.y)) - ax
            r = float(np.hypot(*d))
            if r > lim:
                d *= lim / r
                v.co.x, v.co.y = float(ax[0] + d[0]), float(ax[1] + d[1])
    # leave out clips / ribbons (and with long_only everything that does not reach below the neck)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    names = [mt.name if mt else "" for mt in me.materials]
    kill = [f for f in bm.faces if any(d in names[f.material_index] for d in drop)
            or (long_isl is not None and (int(long_isl[f.verts[0].index]) not in low
                                          or f.calc_center_median().z > hc.z - 0.10))]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    if long_only:                       # pieces cut off the strand tops: drop what no longer reaches the neck
        co, lab = islands(me, weld=False)
        stray = {int(l) for l in np.unique(lab) if co[lab == l, 2].min() > rig_neck}
        if stray:
            bm = bmesh.new()
            bm.from_mesh(me)
            bm.verts.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if int(lab[v.index]) in stray], context="VERTS")
            bm.to_mesh(me)
            bm.free()
    # re-skin: rigid to the head above the neck, following the upper spine further down
    hair.vertex_groups.clear()
    gh, g3, g2 = (hair.vertex_groups.new(name=n) for n in ("head", "spine_03", "spine_02"))
    z_split, z_full = rig_neck + 0.03, rig_chest
    for v in me.vertices:
        k = _smooth((z_split - v.co.z) / max(0.05, z_split - z_full))
        if k <= 0:
            gh.add([v.index], 1.0, "REPLACE")
            continue
        gh.add([v.index], 1 - k, "REPLACE")
        g3.add([v.index], k * 0.7, "REPLACE")
        g2.add([v.index], k * 0.3, "REPLACE")
    # unique material names (both models use the same VRoid names)
    renamed = {}
    for i, mt in enumerate(me.materials):
        if mt is None:
            continue
        base = mt.name.split(".")[0]
        c = mt.copy()
        c.name = f"{src_key}_{base}"
        renamed[c.name] = alpha.get(base, "OPAQUE")
        me.materials[i] = c
    hair.parent = arm
    for mod in hair.modifiers:
        if mod.type == "ARMATURE":
            mod.object = arm
    for o in m2:
        if o is not hair:
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.data.objects.remove(a2, do_unlink=True)
    if long_only:
        hair.name = "HairLong"
        meshes.append(hair)
        return hair, renamed
    for o in old:
        meshes.remove(o)
        bpy.data.objects.remove(o, do_unlink=True)
    hair.name = "Hair"
    meshes.append(hair)
    return hair, renamed


# --------------------------------------------------------------------------- accessories
def _eyes(face):
    """Centres of the two irises (rest pose)."""
    me = face.data
    idx = [i for i, mt in enumerate(me.materials) if mt and "eyeiris" in mt.name.lower()]
    co = np.array([v.co[:] for v in me.vertices])
    vs = sorted({v for p in me.polygons if p.material_index in idx for v in p.vertices})
    pts = co[vs]
    out = []
    for side in (1, -1):
        s = pts[pts[:, 0] * side > 0]
        out.append(Vector(s.mean(0).tolist()))
    return out


def glasses(arm, face, color, name="Glasses"):
    """Round glasses in front of the irises, temples back to the ears; rigid on the head."""
    from ..geo import MeshBuilder
    from ..assets.props import tube
    eyes = _eyes(face)
    _, w, lo, hi = head_frame(face)
    rad = w * 0.15
    mb = MeshBuilder(name)
    centers = []
    for e in eyes:
        c = Vector((e.x * 1.08, lo.y - 0.006, e.z - rad * 0.12))
        centers.append(c)
        with mb.at(tuple(c), rot_x=90):
            mb.torus((0, 0, 0), rad, 0.0022, color, seg=22, tube_seg=5)
    a, b = sorted(centers, key=lambda c: c.x)
    a, b = a + Vector((rad, 0, 0.002)), b - Vector((rad, 0, -0.002))
    tube(mb, [a, (a + b) * 0.5 + Vector((0, -0.002, 0.005)), b], [0.002] * 3, color, seg=5)
    for c in centers:
        s = 1 if c.x > 0 else -1
        e0 = c + Vector((s * rad, 0, 0))
        ear = Vector((s * w * 0.50, hi.y + w * 0.05, c.z + 0.004))
        tube(mb, [e0, e0 + (ear - e0) * 0.5 + Vector((s * 0.004, 0, 0)), ear], [0.002] * 3, color, seg=5)
    return _attach(mb, arm, {"head": 1.0})


def ruff(arm, rig, color, name="Ruff"):
    """Frilled collar of puffs round the neck base (spine_03 / neck_01)."""
    from ..geo import MeshBuilder
    mb = MeshBuilder(name)
    rx, ry = rig.neck_r
    n = 16
    for ring, (k, z, sz) in enumerate(((1.0, rig.neck + 0.0, 0.034), (0.82, rig.neck + 0.03, 0.03))):
        for i in range(n):
            a = 2 * math.pi * (i + 0.5 * ring) / n
            x = math.sin(a) * (rx + 0.04) * k
            y = rig.neck_c.y - math.cos(a) * (ry + 0.04) * k
            mb.sphere((x, y, z), sz, color, seg=8, rings=6, scale=(1.0, 1.0, 0.55))
    return _attach(mb, arm, {"spine_03": 0.6, "neck_01": 0.4})


def _attach(mb, arm, weights):
    from .build import preview_material
    obj = mb.build(mb.name)
    for slot in obj.material_slots:
        if slot.material is not None:
            name = slot.material.name
            bpy.data.materials.remove(slot.material)
            slot.material = preview_material(name)
    for g, w in weights.items():
        vg = obj.vertex_groups.new(name=g)
        vg.add(list(range(len(obj.data.vertices))), w, "REPLACE")
    obj.parent = arm
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm
    return obj


def register_accessory_material(name, color):
    palette.register({name: dict(kind="toon", color=tuple(color), rough=0.6, fill=0.45)})
    return name


def restyle(arm, meshes, entry, key, rig, log=print):
    """Apply entry["hairdo"] to the base model's hair; returns ({extra alpha modes}, [accessory objects])."""
    spec = entry.get("hairdo") or {}
    alpha = {}
    face = next(m for m in meshes if m.name.startswith("Face"))
    hair = next(m for m in meshes if m.name.startswith("Hair"))
    if spec.get("source"):
        new, alpha = borrow(spec["source"], arm, meshes, rig.neck, rig.chest, spec.get("drop", ()), log,
                            long_only=spec.get("long_only", False))
        if not spec.get("long_only"):
            hair = new
    hc = head_center(face)
    if spec.get("spike"):
        spike(hair, hc, **spec["spike"])
    extra = []
    if spec.get("glasses"):
        mat = register_accessory_material(f"M_Anime_{key}_Glasses", spec["glasses"])
        extra.append(glasses(arm, face, mat))
    if spec.get("ruff"):
        mat = register_accessory_material(f"M_Anime_{key}_Ruff", spec["ruff"])
        extra.append(ruff(arm, rig, mat))
    return alpha, extra
