"""
Duel Academy uniforms tailored onto an existing anime base model (models.py).

The VRoid bodies are complete under their clothes, so a uniform is cut from the body itself: a garment
is a copy of the skin faces it covers pushed out along the surface normal (it keeps their bone weights,
so it deforms exactly like the body and cannot slide through it), optionally extended below its bottom
edge as a free-hanging tube (blazer hem, long coat tails, pleated skirt). Cut edges are snapped onto
clean lines (V opening, cuffs, hem). Collars are separate rings round the neck. The skin faces under
an opaque garment and the base model's own tops / bottoms are removed.

Garment textures are painted in 3D: every texel knows its rest-pose position, so trims along the front
opening, hem and cuffs and the buttons are plain distance tests, independent of the UV layout.

Outfit spec (cast.py "outfit"), every part optional, colours sRGB:
  jacket  {color, trim, trims (front / hem / cuff / collar / arm), trim_w, length (waist | hip | thigh |
           knee | calf), open (0 closed .. 1 wide open), sleeves (long | none), collar (height m or 0),
           flare, buttons {color, n}, tint (Unreal recolours it), loose (offset from the body, m)}
  shirt   {color, sleeves (short | long | none), length (waist | hip)}
  pants   {color, width (hem half width, m)}
  skirt   {color, length (m below the crotch), pleats, trim}
  boots   {color, top (fraction from ankle to knee)}
  belly   0..1 (Chumley)
"""

import math
import os

import bmesh
import bpy
import numpy as np
from mathutils import Vector
from PIL import Image
from scipy import ndimage
from scipy.spatial import cKDTree

from .. import config as C
from .. import palette

TEX_REL = "Characters"


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


class Rig:
    """Landmarks of a base model in its rest pose (metres, facing -Y)."""

    def __init__(self, arm, body, skin_mat):
        h = {b.name: Vector(b.head_local) for b in arm.data.bones}
        self.h = h
        self.pelvis, self.hip = h["pelvis"].z, h["thigh_l"].z
        self.knee, self.ankle = h["calf_l"].z, h["foot_l"].z
        self.neck, self.chest, self.waist = h["neck_01"].z, h["spine_03"].z, h["spine_01"].z
        self.shoulder_x, self.shoulder_z = h["upperarm_l"].x, h["upperarm_l"].z
        self.elbow_x, self.wrist_x = h["lowerarm_l"].x, h["hand_l"].x
        me = body.data
        co = np.array([v.co[:] for v in me.vertices])
        skin = sorted({i for p in me.polygons if p.material_index in skin_mat for i in p.vertices})
        s = co[skin]
        mid = s[(np.abs(s[:, 0]) < 0.012) & (s[:, 2] > self.knee + 0.1) & (s[:, 2] < self.pelvis)]
        self.crotch = float(mid[:, 2].min()) if len(mid) else self.hip - 0.12
        ring = s[(np.abs(s[:, 2] - (self.neck + 0.015)) < 0.012) & (np.abs(s[:, 0]) < 0.09)]
        self.neck_c = Vector((0.0, float((ring[:, 1].min() + ring[:, 1].max()) / 2), 0.0))
        self.neck_r = (float(np.abs(ring[:, 0]).max()), float((ring[:, 1].max() - ring[:, 1].min()) / 2))

    def leg(self, side):
        s = 1 if side == "l" else -1
        return [Vector((s * abs(self.h[f"{b}_l"].x), self.h[f"{b}_l"].y, self.h[f"{b}_l"].z))
                for b in ("thigh", "calf", "foot")]

    def hem_z(self, length):
        return {"waist": self.pelvis + 0.025, "hip": self.crotch + 0.05, "thigh": self.crotch + 0.05,
                "knee": self.crotch + 0.05, "calf": self.crotch + 0.05}[length]

    def hem_drop(self, length):
        """How far a garment hangs below its cut line."""
        top = self.crotch + 0.05
        return {"waist": 0.0, "hip": 0.085, "thigh": top - (self.crotch - 0.13),
                "knee": top - (self.knee - 0.03), "calf": top - (self.knee + self.ankle) * 0.5}[length]


class Tailor:
    def __init__(self, arm, body, key, log=print):
        self.arm, self.obj, self.key, self.log = arm, body, key, log
        self.me = body.data
        from .models import role_of
        self.roles = [role_of(s.material.name if s.material else "") for s in body.material_slots]
        skin = {i for i, r in enumerate(self.roles) if r == "skin"}
        self.rig = Rig(arm, body, skin)
        self.bm = bmesh.new()
        self.bm.from_mesh(self.me)
        self.bm.verts.ensure_lookup_table()
        self.dl = self.bm.verts.layers.deform.verify()
        self.groups = {vg.name: vg.index for vg in body.vertex_groups}
        self.skin = [f for f in self.bm.faces if f.material_index in skin]
        self.garments = {}      # name -> dict(faces, mat, spec, bounds)
        self.covered = set()    # skin faces hidden under an opaque garment
        self._normals()

    # ------------------------------------------------------------------ helpers
    def _normals(self):
        """Area-weighted skin normals averaged over coincident positions (UV seams split the vertices)."""
        self.bm.normal_update()
        verts = list({v for f in self.skin for v in f.verts})
        co = np.array([v.co[:] for v in verts])
        n = np.array([v.normal[:] for v in verts])
        _, inv = np.unique(np.round(co / 1e-4).astype(np.int64), axis=0, return_inverse=True)
        inv = inv.ravel()
        acc = np.zeros((inv.max() + 1, 3))
        np.add.at(acc, inv, n)
        n = acc[inv]
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        self.N = {v: Vector(d) for v, d in zip(verts, n)}

    def gi(self, name):
        if name not in self.groups:
            self.groups[name] = self.obj.vertex_groups.new(name=name).index
        return self.groups[name]

    def weights(self, v):
        return dict(v[self.dl])

    def set_weights(self, v, w):
        d = v[self.dl]
        d.clear()
        tot = sum(w.values()) or 1.0
        for g, x in w.items():
            if x > 1e-4:
                d[g] = x / tot

    def material(self, garment, tint=False):
        name = f"M_Anime_{self.key}_{garment}" + ("_JacketTint" if tint else "")
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        if mat.name not in self.me.materials:
            self.me.materials.append(mat)
        return list(self.me.materials).index(mat), name

    # ------------------------------------------------------------------ body edits
    def belly(self, amount):
        r = self.rig
        zc = (r.pelvis + r.chest) * 0.5
        span = (r.chest - r.pelvis) * 0.75
        for v in {v for f in self.skin for v in f.verts}:
            if abs(v.co.x) > r.shoulder_x + 0.05:
                continue
            g = math.exp(-((v.co.z - zc) / span) ** 2) * amount
            front = _smooth((-v.co.y + 0.02) / 0.08)
            v.co.y -= 0.11 * g * front
            v.co.x *= 1 + 0.30 * g
            v.co.y += 0.02 * g * (1 - front)
        self._normals()

    def drop_parts(self, roles=("tops", "bottoms")):
        kill = [f for f in self.bm.faces if f.material_index < len(self.roles) and self.roles[f.material_index] in roles]
        bmesh.ops.delete(self.bm, geom=kill, context="FACES")

    # ------------------------------------------------------------------ garments
    def select(self, pred, every=False):
        """Skin faces with any (every=True: every) vertex passing pred(co)."""
        test = all if every else any
        return [f for f in self.skin if f.is_valid and test(pred(v.co) for v in f.verts)]

    def shell(self, faces, offset, name, spec, covers=()):
        """Copy faces, push them out (offset: float or fn(co, normal) -> new co). covers: skin faces this
        garment hides (removed in finish)."""
        idx, mname = self.material(name, spec.get("tint", False))
        ret = bmesh.ops.duplicate(self.bm, geom=faces)
        fmap = ret["face_map"]
        moved = set()
        for f in faces:
            nf = fmap[f]
            nf.material_index = idx
            nf.smooth = True
            for ov, nv in zip(f.verts, nf.verts):
                if nv in moved:
                    continue
                n = self.N.get(ov, ov.normal)
                nv.co = offset(ov.co, n) if callable(offset) else ov.co + n * offset
                moved.add(nv)
        self.covered.update(covers)
        self.garments.setdefault(name, dict(mat=mname, idx=idx, spec=spec))

    def faces_of(self, name):
        idx = self.garments[name]["idx"]
        return [f for f in self.bm.faces if f.material_index == idx]

    def cut(self, name, co, no, region=None):
        """Split garment `name` exactly along the plane (co, no) and remove the part on the normal's side
        (only faces whose centre passes region(centre), if given)."""
        co, no = Vector(co), Vector(no).normalized()
        faces = [f for f in self.faces_of(name) if region is None or region(f.calc_center_median())]
        if not faces:
            return
        verts = list({v for f in faces for v in f.verts})
        edges = list({e for f in faces for e in f.edges})
        bmesh.ops.bisect_plane(self.bm, geom=verts + edges + faces, dist=1e-6, plane_co=co, plane_no=no)
        kill = [f for f in self.faces_of(name)
                if (f.calc_center_median() - co).dot(no) > 0 and (region is None or region(f.calc_center_median()))]
        bmesh.ops.delete(self.bm, geom=kill, context="FACES")
        bmesh.ops.delete(self.bm, geom=[v for v in self.bm.verts if not v.link_faces], context="VERTS")

    def edges_at(self, name, z):
        """Open edges of a garment lying on the height z (a cut line)."""
        out = []
        for f in self.faces_of(name):
            for e in f.edges:
                if e.is_boundary and all(abs(v.co.z - z) < 1e-4 for v in e.verts):
                    out.append(e)
        return list(dict.fromkeys(out))

    def extend(self, name, edges, drop, flare, rings=4, thigh=0.75, pleats=0, front=1.0):
        """Hang a tube below the boundary `edges`: drop metres down, flaring outwards, weights blending from
        the hem vertices' own weights into the thighs (so coat tails and skirts follow the legs)."""
        g = self.garments[name]
        base = {}
        for e in edges:
            for v in e.verts:
                base[v] = (v.co.copy(), self.weights(v))
        cx = 0.0
        cy = float(np.mean([c.y for c, _ in base.values()]))
        tl, tr = self.gi("thigh_l"), self.gi("thigh_r")
        prev = set(base)
        root = {v: v for v in base}
        cur = list(edges)
        new_faces = []
        for k in range(1, rings + 1):
            t = k / rings
            ret = bmesh.ops.extrude_edge_only(self.bm, edges=cur)
            nverts = [x for x in ret["geom"] if isinstance(x, bmesh.types.BMVert)]
            nedges = [x for x in ret["geom"] if isinstance(x, bmesh.types.BMEdge)]
            nfaces = [x for x in ret["geom"] if isinstance(x, bmesh.types.BMFace)]
            nset = set(nverts)
            for nv in nverts:
                src = next(e.other_vert(nv) for e in nv.link_edges if e.other_vert(nv) in prev)
                root[nv] = root[src]
                p0, w0 = base[root[nv]]
                rad = Vector((p0.x - cx, p0.y - cy, 0.0))
                rad = rad.normalized() if rad.length > 1e-6 else Vector((0, 1, 0))
                fl = flare * t ** 1.2
                if pleats:
                    phi = math.atan2(rad.x, -rad.y)
                    fl += 0.012 * t * abs(math.sin(pleats * phi * 0.5))
                # front < 1: tails - the hem rises towards the front
                back = _smooth((rad.y + 0.35) / 1.1)
                d = drop * (front + (1 - front) * back)
                nv.co = p0 + rad * fl * (0.5 + 0.5 * d / drop) + Vector((0, 0, -d * t))
                ks = thigh * _smooth(t * 1.2)
                side = _smooth((p0.x + 0.05) / 0.10)
                w = {gk: x * (1 - ks) for gk, x in w0.items()}
                w[tl] = w.get(tl, 0.0) + ks * side
                w[tr] = w.get(tr, 0.0) + ks * (1 - side)
                self.set_weights(nv, w)
            for f in nfaces:
                f.material_index = g["idx"]
                f.smooth = True
            new_faces += nfaces
            cur = [e for e in nedges if e.verts[0] in nset and e.verts[1] in nset]
            prev = nset
        return new_faces

    def collar(self, name, height, open_deg, lift=0.012):
        """Stand-up collar round the neck base (outer + inner wall + rim), open at the front."""
        g = self.garments[name]
        r = self.rig
        rx, ry = r.neck_r
        z0, z1 = r.neck - 0.035, r.neck + height
        seg, rows = 28, 4
        a0 = math.radians(open_deg * 0.5)
        angs = [a0 + (2 * math.pi - 2 * a0) * i / seg for i in range(seg + 1)]
        s3, nk = self.gi("spine_03"), self.gi("neck_01")
        grid = {}
        for wall, extra in (("o", 0.0), ("i", -0.005)):
            for j in range(rows + 1):
                t = j / rows
                z = z0 + (z1 - z0) * t
                grow = lift + 0.006 + 0.016 * t + extra
                for i, a in enumerate(angs):
                    x = math.sin(a) * (rx + grow)
                    y = r.neck_c.y - math.cos(a) * (ry + grow)
                    v = self.bm.verts.new((x, y, z))
                    self.set_weights(v, {s3: 1 - 0.5 * t, nk: 0.5 * t})
                    grid[wall, j, i] = v
        faces = []

        def quad(a, b, c, d):
            f = self.bm.faces.new((a, b, c, d))
            f.material_index = g["idx"]
            f.smooth = True
            faces.append(f)
        for j in range(rows):
            for i in range(seg):
                quad(grid["o", j, i], grid["o", j, i + 1], grid["o", j + 1, i + 1], grid["o", j + 1, i])
                quad(grid["i", j, i + 1], grid["i", j, i], grid["i", j + 1, i], grid["i", j + 1, i + 1])
        for i in range(seg):
            quad(grid["o", rows, i], grid["o", rows, i + 1], grid["i", rows, i + 1], grid["i", rows, i])
        for i in (0, seg):
            for j in range(rows):
                vs = (grid["o", j, i], grid["o", j + 1, i], grid["i", j + 1, i], grid["i", j, i])
                quad(*(vs if i == 0 else tuple(reversed(vs))))
        g["collar_top"] = z1
        return faces

    # ------------------------------------------------------------------ the uniform
    def jacket(self, spec):
        r = self.rig
        length = spec.get("length", "hip")
        hem = r.hem_z(length)
        sleeves = spec.get("sleeves", "long")
        cuff_x = r.wrist_x - 0.035 if sleeves == "long" else r.shoulder_x + 0.025
        opening = spec.get("open", 0.15)
        neck_cut = r.neck + 0.01
        top = neck_cut + 0.03
        # the front opening: a straight line per side from (x0, z0) up to (x1, top)
        if opening >= 0.6:
            x0, z0, x1 = 0.012 + 0.06 * opening, hem - 0.3, 0.035 + 0.06 * opening
        else:
            x0, z0, x1 = 0.0, r.chest - (r.chest - r.waist) * opening * 1.6, 0.035 + 0.06 * opening

        def gap(z):
            if z < z0:
                return 0.0
            return x0 + (x1 - x0) * (z - z0) / (top - z0)

        def inside(co):
            if abs(co.x) < r.neck_r[0] + 0.035 and co.z > neck_cut:
                return False
            return abs(co.x) < cuff_x and co.z > hem and co.z < r.shoulder_z + 0.12

        def in_gap(c):
            return c.y < r.neck_c.y and abs(c.x) < gap(c.z)

        faces = self.select(inside)
        covers = [f for f in self.select(inside, every=True) if not in_gap(f.calc_center_median())]
        self.shell(faces, spec.get("loose", 0.016), "Jacket", spec, covers)
        self.cut("Jacket", (cuff_x, 0, 0), (1, 0, 0))
        self.cut("Jacket", (-cuff_x, 0, 0), (-1, 0, 0))
        self.cut("Jacket", (0, 0, hem), (0, 0, -1))
        if opening:
            for sgn in (1, -1):
                d = Vector((sgn * (x1 - x0), 0, top - z0)).normalized()
                no = Vector((d.z, 0, -d.x))
                if no.x * sgn > 0:                            # point into the opening
                    no = -no
                self.cut("Jacket", (sgn * x0, 0, z0), no,
                         region=lambda c, sgn=sgn: c.y < r.neck_c.y and c.x * sgn > -0.002 and c.z > z0 - 0.02)
        drop = spec.get("drop", r.hem_drop(length))
        if drop > 0:
            long = drop > 0.15
            self.extend("Jacket", self.edges_at("Jacket", hem), drop, spec.get("flare", 0.035 if not long else 0.07),
                        rings=3 if not long else 6, thigh=0.45 if not long else 0.8, front=spec.get("tails", 1.0))
        if spec.get("collar", 0.05):
            self.collar("Jacket", spec.get("collar", 0.05), 70 + 80 * opening)
        g = self.garments["Jacket"]
        g["cuff_x"], g["hem"], g["gap"] = cuff_x, hem - drop, gap

    def shirt(self, spec):
        r = self.rig
        sleeves = spec.get("sleeves", "short")
        sx = {"short": r.shoulder_x + 0.10, "long": r.wrist_x - 0.04, "none": r.shoulder_x - 0.01}[sleeves]
        hem = r.hem_z(spec.get("length", "hip"))
        neck = r.neck - 0.012

        def inside(co):
            if abs(co.x) < r.neck_r[0] + 0.035 and co.z > neck:
                return False
            return abs(co.x) < sx and co.z > hem

        self.shell(self.select(inside), 0.010, "Shirt", spec, self.select(inside, every=True))
        self.cut("Shirt", (sx, 0, 0), (1, 0, 0))
        self.cut("Shirt", (-sx, 0, 0), (-1, 0, 0))
        self.cut("Shirt", (0, 0, hem), (0, 0, -1))
        if spec.get("length", "hip") == "hip":
            self.extend("Shirt", self.edges_at("Shirt", hem), 0.03, 0.012, rings=1, thigh=0.3)

    def pants(self, spec):
        r = self.rig
        top = r.pelvis + 0.045
        bottom = self.shoe_top() - 0.035
        width = spec.get("width", 0.062)
        legs = {s: r.leg(s) for s in ("l", "r")}

        def axis_point(co):
            pts = legs["l" if co.x > 0 else "r"]
            best = None
            for a, b in zip(pts, pts[1:]):
                d = b - a
                t = max(0.0, min(1.0, (co - a).dot(d) / d.length_squared))
                p = a + d * t
                if best is None or (co - p).length < (co - best).length:
                    best = p
            return best

        def offset(co, n):
            p = co + n * 0.007
            if co.z > r.knee + 0.12:
                return p
            a = axis_point(co)
            rad = Vector((p.x - a.x, p.y - a.y, 0.0))
            k = _smooth((r.knee + 0.12 - co.z) / 0.25)
            target = width * k + rad.length * (1 - k)
            if rad.length < target and rad.length > 1e-6:
                p = Vector((a.x, a.y, p.z)) + rad.normalized() * target
            return p

        def inside(co):
            return bottom < co.z < top

        self.shell(self.select(inside), offset, "Pants", spec, self.select(inside, every=True))
        self.cut("Pants", (0, 0, top), (0, 0, 1))
        self.cut("Pants", (0, 0, bottom), (0, 0, -1))

    def skirt(self, spec):
        r = self.rig
        top = r.pelvis + 0.04
        cut = r.crotch + 0.05

        def inside(co):
            return cut < co.z < top

        self.shell(self.select(inside), 0.010, "Skirt", spec, self.select(inside, every=True))
        self.cut("Skirt", (0, 0, top), (0, 0, 1))
        self.cut("Skirt", (0, 0, cut), (0, 0, -1))
        self.extend("Skirt", self.edges_at("Skirt", cut), spec.get("length", 0.17), 0.06, rings=4, thigh=0.55,
                    pleats=spec.get("pleats", 16))
        self.garments["Skirt"]["hem"] = cut - spec.get("length", 0.17)
        self.garments["Skirt"]["belt"] = top

    def boots(self, spec):
        r = self.rig
        lo = self.shoe_top() - 0.03
        hi = r.ankle + (r.knee - r.ankle) * spec.get("top", 0.85)

        def inside(co):
            return lo < co.z < hi

        self.shell(self.select(inside), 0.008, "Boots", spec, self.select(inside, every=True))
        self.cut("Boots", (0, 0, hi), (0, 0, 1))
        self.cut("Boots", (0, 0, lo), (0, 0, -1))
        self.garments["Boots"]["top"] = hi

    def shoe_top(self):
        n = len(self.roles)
        zs = [v.co.z for f in self.bm.faces if f.material_index < n and self.roles[f.material_index] == "shoes"
              for v in f.verts]
        return float(np.percentile(zs, 97)) if zs else self.rig.ankle + 0.06

    # ------------------------------------------------------------------ finish
    def finish(self):
        """Drop covered skin, write the mesh, unwrap + paint every garment."""
        bmesh.ops.delete(self.bm, geom=[f for f in self.covered if f.is_valid], context="FACES")
        loose = [v for v in self.bm.verts if not v.link_faces]
        bmesh.ops.delete(self.bm, geom=loose, context="VERTS")
        idx_of = {name: g["idx"] for name, g in self.garments.items()}
        self.bm.to_mesh(self.me)
        self.bm.free()
        self.me.update()
        for name, g in self.garments.items():
            _unwrap(self.obj, idx_of[name])
            rel = f"{TEX_REL}/{self.key}/T_{self.key}_{name}"
            paint(self.me, idx_of[name], g, self.rig, os.path.join(C.OUT_TEXTURES, rel + ".png"))
            # two-sided (the masked toon variant): the inside of an open jacket / coat tail / skirt is seen
            palette.register({g["mat"]: dict(kind="toon", color=(1.0, 1.0, 1.0), rough=0.85, fill=0.45, base=rel,
                                             masked=name in ("Jacket", "Skirt"))})
            from .build import preview_material
            old = self.me.materials[idx_of[name]]
            bpy.data.materials.remove(old)
            self.me.materials[idx_of[name]] = preview_material(g["mat"])


def _unwrap(obj, mat_idx):
    for o in bpy.context.scene.objects:
        o.select_set(False)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_mode(type="FACE")
    bpy.ops.mesh.select_all(action="DESELECT")
    bpy.ops.object.mode_set(mode="OBJECT")
    me = obj.data
    for p in me.polygons:
        if p.material_index == mat_idx:
            p.select = True
            for v in p.vertices:
                me.vertices[v].select = True
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.012, scale_to_bounds=True)
    bpy.ops.object.mode_set(mode="OBJECT")


# --------------------------------------------------------------------------- 3D texture painting
def bake_positions(me, mat_idx, size):
    """Per texel rest-pose position of the faces with material mat_idx: (pos HxWx3, mask HxW)."""
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    pos = np.zeros((size, size, 3), np.float32)
    mask = np.zeros((size, size), bool)
    co = np.array([v.co[:] for v in me.vertices], np.float32)
    for lt in me.loop_triangles:
        if me.polygons[lt.polygon_index].material_index != mat_idx:
            continue
        t = np.array([uv[l].uv[:] for l in lt.loops], np.float64) * size
        t[:, 1] = size - t[:, 1]
        p = co[list(lt.vertices)]
        x0, y0 = np.floor(t.min(0)).astype(int)
        x1, y1 = np.ceil(t.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = t
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        l1 = ((by - cy) * (xs - cx) + (cx - bx) * (ys - cy)) / den
        l2 = ((cy - ay) * (xs - cx) + (ax - cx) * (ys - cy)) / den
        l3 = 1 - l1 - l2
        eps = -0.02
        ins = (l1 >= eps) & (l2 >= eps) & (l3 >= eps)
        if not ins.any():
            continue
        rows, cols = (ys[ins] - 0.5).astype(int), (xs[ins] - 0.5).astype(int)
        pos[rows, cols] = l1[ins][:, None] * p[0] + l2[ins][:, None] * p[1] + l3[ins][:, None] * p[2]
        mask[rows, cols] = True
    return pos, mask


def _dilate(img, mask):
    idx = ndimage.distance_transform_edt(~mask, return_distances=False, return_indices=True)
    return img[idx[0], idx[1]]


def _edge_points(me, mat_idx, step=0.003):
    """Sample points along the open edges of a garment: [(point, edge midpoint)]."""
    count = {}
    for p in me.polygons:
        if p.material_index != mat_idx:
            continue
        for ek in p.edge_keys:
            count[ek] = count.get(ek, 0) + 1
    co = [v.co for v in me.vertices]
    pts = []
    # coincident edges of neighbouring faces split by UV seams are not open: weld by position first
    by_pos = {}
    for ek, n in count.items():
        a, b = co[ek[0]], co[ek[1]]
        key = tuple(sorted((tuple(round(x, 4) for x in a), tuple(round(x, 4) for x in b))))
        by_pos[key] = by_pos.get(key, 0) + n
    for key, n in by_pos.items():
        if n != 1:
            continue
        a, b = Vector(key[0]), Vector(key[1])
        k = max(1, int((b - a).length / step))
        for i in range(k + 1):
            pts.append(tuple(a + (b - a) * (i / k)))
    return np.array(pts, np.float32) if pts else np.zeros((0, 3), np.float32)


def paint(me, mat_idx, g, rig, path, size=None):
    spec = g["spec"]
    size = size or (1024 if g["spec"] is not None and "cuff_x" in g else 512)
    pos, mask = bake_positions(me, mat_idx, size)
    base = np.array(spec.get("color", (1, 1, 1)), np.float32)
    img = np.zeros((size, size, 3), np.float32)
    img[...] = base
    P = pos[mask]
    col = np.repeat(base[None], len(P), 0)
    # soft fold shading: a little darker towards the inside of the elbows / back of the knees is overkill -
    # anime uniforms are flat; only the trims and buttons are painted
    trims = spec.get("trims", ())
    tc = np.array(spec.get("trim", base), np.float32)
    tw = spec.get("trim_w", 0.016)
    if trims and len(P):
        pts = _edge_points(me, mat_idx)
        if len(pts):
            kind = _edge_kind(pts, g, rig)
            sel = np.isin(kind, list(trims))
            if sel.any():
                d, _ = cKDTree(pts[sel]).query(P)
                col[d < tw] = tc
        if "collar" in trims and g.get("collar_top"):
            col[P[:, 2] > g["collar_top"] - tw * 0.8] = tc
        if "cuff" in trims and g.get("cuff_x") and spec.get("sleeves", "long") != "none":
            # cuff band (its own colour, e.g. the dorm colour) edged with a trim line
            cw = spec.get("cuff_w", 0.045)
            ax = np.abs(P[:, 0])
            on_arm = P[:, 2] > rig.shoulder_z - 0.15
            col[(ax > g["cuff_x"] - cw - tw * 0.45) & on_arm] = tc
            col[(ax > g["cuff_x"] - cw) & on_arm] = spec.get("cuff_color", tc)
    sh = spec.get("shoulder")                         # band round the top of the sleeves
    if sh and len(P) and spec.get("sleeves", "long") != "none":
        ax = np.abs(P[:, 0])
        x0 = rig.shoulder_x + sh.get("at", 0.035)
        on_arm = P[:, 2] > rig.shoulder_z - 0.15
        col[(ax > x0) & (ax < x0 + sh.get("w", 0.03)) & on_arm] = sh.get("color", tc)
    if spec.get("panel"):                           # two-tone: a coloured band (Obelisk coats)
        pz0, pz1, pc = spec["panel"]
        col[(P[:, 2] > pz0) & (P[:, 2] < pz1)] = pc
    if spec.get("belt") and g.get("belt") and len(P):
        col[P[:, 2] > g["belt"] - spec.get("belt_w", 0.03)] = spec["belt"]
    b = spec.get("buttons")
    if b and len(P):
        gapf = g.get("gap")
        zs = np.linspace(rig.chest + 0.02, rig.pelvis + 0.04, b.get("n", 3))
        for z in zs:
            x = (gapf(z) + 0.02) if gapf and gapf(z) > 0 else 0.0
            for sx in ((-1, 1) if x else (1,)):
                c = np.array((sx * x, -1.0, z), np.float32)
                dd = np.hypot(P[:, 0] - c[0], P[:, 2] - c[2])
                front = P[:, 1] < rig.neck_c.y
                col[(dd < b.get("r", 0.011)) & front] = b["color"]
    img[mask] = col
    img = _dilate(img, mask)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path, optimize=True)


def _edge_kind(pts, g, rig):
    kind = np.full(len(pts), "front", dtype=object)
    cx = g.get("cuff_x")
    hem = g.get("hem")
    if cx:
        kind[np.abs(pts[:, 0]) > cx - 0.02] = "cuff"
    if hem is not None:
        # the bottom edge: lowest open edge in each direction round the body (coat tails hang lower at the
        # back than in front, so no single height)
        phi = np.arctan2(pts[:, 0], -(pts[:, 1] - rig.neck_c.y))
        sector = np.round(phi / math.radians(8)).astype(int)
        low = {}
        for sct, z in zip(sector, pts[:, 2]):
            low[sct] = min(low.get(sct, 1e9), z)
        lowest = np.array([low[sct] for sct in sector])
        kind[(pts[:, 2] < lowest + 0.02) & (pts[:, 2] < hem + 0.35) & (kind == "front")] = "hem"
    if g.get("top") is not None:
        kind[pts[:, 2] > g["top"] - 0.01] = "top"
    if g.get("collar_top"):
        kind[pts[:, 2] > rig.neck - 0.04] = np.where(kind[pts[:, 2] > rig.neck - 0.04] == "cuff", "cuff", "collar")
    return kind


def tailor(arm, body, entry, key, log=print):
    """Dress body (the base model's Body mesh) in entry["outfit"]. No-op without an outfit."""
    spec = entry.get("outfit")
    if not spec:
        return
    t = Tailor(arm, body, key, log)
    t._spec = spec
    if spec.get("belly"):
        t.belly(spec["belly"])
    t.drop_parts()
    if "pants" in spec:
        t.pants(spec["pants"])
    if "skirt" in spec:
        t.skirt(spec["skirt"])
    if "shirt" in spec:
        t.shirt(spec["shirt"])
    if "jacket" in spec:
        t.jacket(spec["jacket"])
    if "boots" in spec:
        t.boots(spec["boots"])
    t.finish()
    return t


def fix_skin(obj, mat_idx, src_png, dst_png, rig, legs=False):
    """Paint the base model's body texture back to bare skin where its painted-on clothing would show with
    the uniform: gloves on the hands (and tights on the legs for skirts). The skin tone is sampled from the
    neck."""
    img = np.asarray(Image.open(src_png).convert("RGBA")).astype(np.float32) / 255.0
    h, w = img.shape[:2]
    pos, mask = bake_positions(obj.data, mat_idx, max(h, w))
    if (h, w) != mask.shape:
        pos, mask = pos[:h, :w], mask[:h, :w]
    neck = mask & (pos[..., 2] > rig.neck + 0.005) & (pos[..., 2] < rig.neck + 0.05)
    if not neck.any():
        Image.fromarray((img * 255 + 0.5).astype(np.uint8)).save(dst_png)
        return dst_png
    ref = np.median(img[neck][:, :3], axis=0)
    region = mask & (np.abs(pos[..., 0]) > rig.wrist_x - 0.06)
    if legs:
        region |= mask & (pos[..., 2] < rig.crotch + 0.03) & (np.abs(pos[..., 0]) < rig.shoulder_x + 0.2)
    region = ndimage.binary_dilation(region, iterations=3) & ~(mask & ~region)
    img[region, :3] = ref
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst_png, optimize=True)
    return dst_png
