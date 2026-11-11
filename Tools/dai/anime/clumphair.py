"""
Clump hair on the VRoid base heads.

The atelier's hair generator (atelier/hair.py: a few dozen thick pointed locks combed from the crown, style
recipes in atelier/styles.py) only knows the atelier head. This module fits that head's scalp parametrisation
(azimuth, ring) to a VRoid base model's skull, so every recipe can replace the base's own hair mesh:

  FittedHead   the atelier head moved onto the measured skull: per-axis scale, the crown / eye line / chin
               heights matched (so a fringe "to the brows" ends at this face's brows), and every scalp point
               then snapped onto the model's real skull surface (a radial field sampled from the bald head
               under the VRoid hair), with the usual loft keeping the locks off the skin
  Torso        collision slices of the dressed body (rest pose), so long hair hangs outside neck, collar,
               shoulders and back
  build()      look entry -> hair mesh object + spring bones + painted texture + palette material

A look asks for it with entry["hair_style"] (see looks.py):

  style      recipe name (atelier/styles.HAIR) or a sections dict (styles.styled(...))
  ombre      (start, length) in metres from the crown of the fade into the hair's second colour
  accent     colour of the locks a recipe marks accent=True (streaks, inner layers); accent2: its tip tone
  tie        colour of the hair ties on tails / plaits / buns (None: no ties)
  highlight, seed, cap (front, side, back hairline rings), outline
"""

import os

import numpy as np

from .. import config as C
from .. import palette

TEX_REL = "Characters"
OBJECT_NAME = "ClumpHair"            # models.add_outline skips it: the locks bring their own ink hull
TINT_PAINT = (0.93, 0.93, 0.93)      # neutral hair under a runtime tint ("HairTint" material slots)


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


# --------------------------------------------------------------------------- measuring the base model
def _mesh_points(obj):
    """(positions, material name per vertex (lower case), head-bone weight per vertex) of a mesh object."""
    me = obj.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    names = [s.material.name.lower() if s.material else "" for s in obj.material_slots]
    vm = np.full(n, "", dtype=object)
    for p in me.polygons:
        nm = names[p.material_index] if p.material_index < len(names) else ""
        for vi in p.vertices:
            vm[vi] = nm
    hw = np.zeros(n)
    g = obj.vertex_groups.get("head")
    if g is not None:
        for v in me.vertices:
            for e in v.groups:
                if e.group == g.index:
                    hw[v.index] = e.weight
    return co, vm, hw


def measure(meshes):
    """Skull of a loaded base model (rest pose, metres, facing -Y): the points of the bald head and the
    landmarks the fit needs."""
    face = next(m for m in meshes if m.name.startswith("Face"))
    fco, fmat, _ = _mesh_points(face)
    fskin = np.array(["skin" in n for n in fmat])
    iris = np.array(["eyeiris" in n for n in fmat])
    F = fco[fskin]
    eye_z = float(fco[iris][:, 2].mean()) if iris.any() else float(F[:, 2].min() + 0.34 * np.ptp(F[:, 2]))
    eye_x = float(np.abs(fco[iris][:, 0]).mean()) if iris.any() else 0.032
    back_pts = []
    for m in meshes:
        if m is face:
            continue
        co, mat, hw = _mesh_points(m)
        sel = np.array(["skin" in n for n in mat]) & (hw > 0.5)
        if sel.any():
            back_pts.append(co[sel])
    B = np.concatenate(back_pts) if back_pts else F
    chin = float(F[np.abs(F[:, 0]) < 0.01][:, 2].min())
    crown = float(max(B[:, 2].max(), F[:, 2].max()))
    half_w = float(np.abs(B[B[:, 2] > eye_z + 0.02][:, 0]).max())            # cranium (the ears are face mesh)
    F = F[np.abs(F[:, 0]) <= half_w + 0.0005]                                # ...and stay out of the skull
    skull = np.concatenate([F, B[B[:, 2] > chin - 0.03]])
    back = float(B[:, 1].max())
    return dict(points=skull, crown=crown, chin=chin, eye_z=eye_z, eye_x=eye_x, half_w=half_w, back=back, face=F)


# --------------------------------------------------------------------------- the fitted head
class FittedHead:
    """The atelier head's scalp(theta, s, loft) on a measured skull (hair.Hair combs over this)."""

    def __init__(self, m, shape=None, log=None):
        from scipy.spatial import cKDTree
        from .atelier import head as HD
        self.atelier = HD.Head(shape)
        self.m = m
        a = self.atelier
        ss = np.linspace(0.0, 1.0, 201)
        front = a.point(np.zeros_like(ss), ss, sculpt=False)
        ring = a.point(np.linspace(0.0, 2 * np.pi, 90)[None], ss[:80, None], sculpt=False)
        a_crown, a_chin = float(front[:, 2].max()), float(front[:, 2].min())
        a_eye = float(a.eye["cz"])
        a_w = float(np.abs(ring[..., 0]).max())
        a_back = float(ring[..., 1].max())
        # forehead: the front profile a little above the brows, on both heads
        zf = a_eye + 0.045
        a_front = float(np.interp(-zf, -front[:, 2], front[:, 1]))
        self._za = np.array([a_chin - 1.0, a_chin, a_eye, a_crown])
        kz = (m["crown"] - m["chin"]) / (a_crown - a_chin)
        self._zv = np.array([m["chin"] - kz, m["chin"], m["eye_z"], m["crown"]])
        zf_v = float(np.interp(zf, self._za, self._zv))
        F = m["face"]
        band = F[(np.abs(F[:, 2] - zf_v) < 0.012) & (np.abs(F[:, 0]) < 0.02)]
        v_front = float(band[:, 1].min()) if len(band) else float(F[:, 1].min()) + 0.01
        self.kx = m["half_w"] / a_w
        self.ky = (m["back"] - v_front) / (a_back - a_front)
        self.y0 = v_front - self.ky * a_front
        self.kz = kz
        self.size = float((self.kx + self.ky + self.kz) / 3.0)            # scale of the recipe lengths
        self.centre = np.array([0.0, self.y0 + 0.004 * self.ky, float(np.interp(0.0, self._za, self._zv))])
        self.radii = np.array([0.086 * self.kx, 0.100 * self.ky, 0.100 * self.kz])
        # radial field of the real skull round `origin`
        self.origin = np.array([0.0, 0.5 * (m["back"] + v_front), m["eye_z"] + 0.030 * kz])
        rel = m["points"] - self.origin
        r = np.linalg.norm(rel, axis=1)
        keep = r > 0.03
        self._dirs = rel[keep] / r[keep, None]
        self._r = r[keep]
        self._tree = cKDTree(self._dirs)
        self.chin_z = m["chin"]
        if log:
            th = np.linspace(0.0, 2 * np.pi, 36, endpoint=False)
            s = np.linspace(0.05, 0.60, 12)
            p = self._affine(a.point(th[None], s[:, None], sculpt=False))
            d = np.linalg.norm(p - self.origin, axis=-1) - self.radius((p - self.origin).reshape(-1, 3)).reshape(p.shape[:-1])
            log(f"  clump hair: skull fit scale ({self.kx:.3f}, {self.ky:.3f}, {self.kz:.3f}), "
                f"residual {1000 * np.abs(d).mean():.1f} mm mean / {1000 * np.abs(d).max():.1f} mm max")

    # ------------------------------------------------------------------ surface
    def _affine(self, p):
        out = np.empty_like(p)
        out[..., 0] = p[..., 0] * self.kx
        out[..., 1] = self.y0 + p[..., 1] * self.ky
        out[..., 2] = np.interp(p[..., 2], self._za, self._zv)
        return out

    def radius(self, d):
        """Skull radius from `origin` along directions d (K, 3): smooth interpolation of the head's points."""
        d = np.asarray(d, np.float64).reshape(-1, 3)
        d = d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-12)
        dist, idx = self._tree.query(d, k=8)
        w = 1.0 / (dist ** 2 + 4e-4)
        return (self._r[idx] * w).sum(1) / w.sum(1)

    def _surface(self, theta, s):
        p = self._affine(self.atelier.point(theta, s, sculpt=False))
        rel = p - self.origin
        r = np.linalg.norm(rel, axis=-1)
        R = self.radius(rel.reshape(-1, 3)).reshape(r.shape)
        R = np.clip(R, 0.86 * r, 1.22 * r)                 # stay near the fit where the head has no points
        # the real surface above the jaw; the fitted egg below it (the field has only the neck there)
        k = _smooth((p[..., 2] - (self.chin_z - 0.01)) / 0.04)
        rr = r + (R - r) * k
        return self.origin + rel * (rr / np.maximum(r, 1e-9))[..., None]

    def scalp(self, theta, s, loft=0.0):
        theta, s = np.broadcast_arrays(np.asarray(theta, np.float64), np.asarray(s, np.float64))
        p = self._surface(theta, s)
        h = 4e-3
        dt = self._surface(theta + h, s) - self._surface(theta - h, s)
        ds = self._surface(theta, s + h) - self._surface(theta, np.maximum(s - h, 0.0))
        n = np.cross(dt, ds)
        ln = np.linalg.norm(n, axis=-1, keepdims=True)
        rad = p - (self.origin + np.array([0.0, 0.0, 0.01]))
        rad = rad / np.maximum(np.linalg.norm(rad, axis=-1, keepdims=True), 1e-9)
        n = np.where(ln > 1e-9, n / np.maximum(ln, 1e-12), rad)
        n = np.where((n * rad).sum(-1, keepdims=True) < 0, -n, n)
        n = n * 0.5 + rad * 0.5
        n = n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
        return p + n * np.asarray(loft, np.float64)[..., None], n

    def keep_out(self, pos, margin=0.01):
        """Push a free lock point out of the head (and the top of the neck)."""
        if pos[2] < self.chin_z - 0.035:
            return pos
        rel = pos - self.origin
        r = float(np.linalg.norm(rel))
        R = float(self.radius(rel[None])[0]) + margin * float(_smooth((pos[2] - (self.chin_z - 0.035)) / 0.03))
        return pos if r >= R else self.origin + rel * (R / max(r, 1e-9))


# --------------------------------------------------------------------------- body collision
class Torso:
    """Elliptic slices of the dressed body below the chin (rest pose): hair.Hair's `body`."""
    relax = True                         # hair.Hair smooths the pushed lock paths

    def __init__(self, arm, meshes, chin_z):
        h = {b.name: np.array(b.head_local) for b in arm.data.bones}
        sx = abs(float(h["upperarm_l"][0])) + 0.035
        pts = []
        for m in meshes:
            if m.name.startswith(("Hair", OBJECT_NAME)):
                continue
            if m.name.startswith("Face"):
                continue
            co, _, hw = _mesh_points(m)
            pts.append(co[(np.abs(co[:, 0]) < sx) & (co[:, 2] < chin_z + 0.01) & (hw < 0.5)])
        P = np.concatenate(pts)
        z0 = float(h["pelvis"][2]) - 0.12
        self.top = chin_z
        zs = np.arange(z0, chin_z + 1e-6, 0.01)
        rows = []
        for z in zs:
            sl = P[np.abs(P[:, 2] - z) < 0.012]
            if len(sl) < 6:
                rows.append(rows[-1] if rows else (0.0, 0.0, 0.0))
                continue
            y0, y1 = float(sl[:, 1].min()), float(sl[:, 1].max())
            rows.append((float(np.abs(sl[:, 0]).max()), 0.5 * (y0 + y1), 0.5 * (y1 - y0)))
        rows = np.array(rows)
        # conservative: every slice also covers its neighbours (collars, shoulder slope)
        a = np.maximum.reduce([rows[:, 0], np.roll(rows[:, 0], 1), np.roll(rows[:, 0], -1)])
        d = np.maximum.reduce([rows[:, 2], np.roll(rows[:, 2], 1), np.roll(rows[:, 2], -1)])
        a[0], a[-1], d[0], d[-1] = rows[0, 0], rows[-1, 0], rows[0, 2], rows[-1, 2]
        self.z, self.a, self.cy, self.d = zs, a, rows[:, 1], d

    def push_out(self, p, margin=0.012):
        p = np.array(p, np.float64)
        z = p[:, 2]
        a = np.interp(z, self.z, self.a) + margin
        d = np.interp(z, self.z, self.d) + margin
        cy = np.interp(z, self.z, self.cy)
        ry = p[:, 1] - cy
        q = np.hypot(p[:, 0] / a, ry / d)
        inside = (z < self.top) & (z > self.z[0]) & (q < 1.0)
        # out through the back or the chest rather than sideways: hair drapes behind / in front of the
        # shoulders instead of spreading over the arms
        edge = d * np.sqrt(np.clip(1.0 - (p[:, 0] / a) ** 2, 0.0, 1.0))
        p[:, 1] = np.where(inside, cy + np.where(ry >= -0.25 * d, edge, -edge), p[:, 1])
        return p


# --------------------------------------------------------------------------- build
def material_name(key, entry):
    return f"M_Anime_{key}_HairTint" if "hair" in entry.get("tint", ()) else f"M_Anime_{key}_Hair"


def resolve(spec):
    """hair_style -> (sections dict, options)."""
    from .atelier import styles
    if isinstance(spec, str):
        spec = dict(style=spec)
    st = spec.get("style", "long")
    sections = styles.styled(st) if isinstance(st, str) else st
    return sections, spec


def remove_base_hair(arm, meshes, log=print):
    """Delete the base model's own hair meshes (and the spring bones only they used)."""
    import bpy
    from .models import role_of
    from . import hairrig
    gone = 0
    for m in list(meshes):
        mats = [s.material.name for s in m.material_slots if s.material]
        if mats and all(role_of(n) == "hair" for n in mats):
            meshes.remove(m)
            bpy.data.objects.remove(m, do_unlink=True)
            gone += 1
    bones = hairrig.drop_unused(arm, meshes)
    log(f"  clump hair: removed {gone} base hair mesh(es), {bones} of their spring bones")


def build(arm, meshes, entry, key, log=print):
    """Replace the base hair of a loaded model with the clump hair of entry["hair_style"].
    Returns (hair object - also appended to `meshes` -, {names of the materials it registered})."""
    from .atelier import build as AB
    from .atelier import hair as HR
    from .atelier import mesh as AM
    from .atelier import paint as P
    from .build import preview_material
    sections, opt = resolve(entry["hair_style"])
    remove_base_hair(arm, meshes, log)
    head = FittedHead(measure(meshes), log=log)
    torso = Torso(arm, meshes, head.chin_z)

    tinted = "hair" in entry.get("tint", ())
    hair = entry.get("hair", {})
    mat = material_name(key, entry)
    accent = None if tinted else opt.get("accent")
    rel = f"{TEX_REL}/{key}/T_{mat[2:]}"
    P.hair(os.path.join(C.OUT_TEXTURES, rel + ".png"), TINT_PAINT if tinted else hair["color"],
           None if tinted else hair.get("color2"), highlight=opt.get("highlight"),
           ombre=opt.get("ombre", (0.45, 0.30)), seed=opt.get("seed", 3), accent=accent,
           accent2=opt.get("accent2"), contrast=1.6 if tinted else 1.0)
    specs = {mat: dict(kind="toon", color=(1.0, 1.0, 1.0), rough=0.85, fill=0.45, ring=0.0, base=rel)}
    tie_mat = None
    if opt.get("tie") is not None:
        tie_mat = f"M_Anime_{key}_Tie"
        specs[tie_mat] = dict(kind="toon", color=tuple(opt["tie"]), rough=0.7, fill=0.45, cel="cloth")
    palette.register(specs)

    hr = HR.Hair(head, torso, seed=opt.get("seed", 1))
    hr.split = accent is not None
    HR.style(hr, sections, mat)
    parts, bones = hr.build(mat, key, cap_line=opt.get("cap", (0.27, 0.50, 0.74)), tie_mat=tie_mat)
    AB.ensure_bones(arm, bones)
    line = opt.get("outline", 0.0028 * entry.get("outline", 0.0022) / 0.0022)
    obj = AM.assemble(OBJECT_NAME, parts, arm, preview_material, outline=line, log=None)
    meshes.append(obj)
    log(f"  clump hair: {key}: {len(hr.locks)} locks, {len(bones)} spring bones, "
        f"{sum(p.tris() for p in parts)} tris")
    return obj, set(specs) | {AM.OUTLINE_MAT}
