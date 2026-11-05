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
           flare, buttons {color, n}, tint (Unreal recolours it), loose (offset from the body, m),
           collar_flare, collar_color, collar_trim, lining (inside of the collar), cuff_color, shoulder {color, w},
           tails (front hem fraction), drop, capelet {color, trim, trim2, drop, open, wide, deep},
           shield {color, border, w, below, side, point, border_w} (the chest panel)}
  shirt   {color, sleeves (short | long | none), length (waist | hip), turtleneck}
  pants   {color, width (hem half width, m)}
  skirt   {color, length (m below the crotch), pleats, trim}
  boots   {color, top (fraction from ankle to knee)}
  gloves  {color, trim, from (fraction along the forearm)} - fingerless
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

from .. import atomic
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
        # `crotch` (lowest midline skin) is where the inner thighs meet, and every hem length is defined from it
        # (design reference, kept). `crotch_true` is the real fork of the legs - the downward-facing skin on
        # the midline - and is what construction respects: torso garments are cut from the skin only above it
        # and continue as a hanging tube below (no leg tops / crotch underside copied into a jacket).
        self.crotch = float(mid[:, 2].min()) if len(mid) else self.hip - 0.12
        down = [p.center.z for p in me.polygons if p.material_index in skin_mat and abs(p.center.x) < 0.02
                and self.knee + 0.1 < p.center.z < self.pelvis and p.normal.z < -0.6]
        self.crotch_true = max(self.crotch, float(np.median(down))) if down else self.crotch
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
        from .drape import Drape
        self.drape = Drape(self)   # cloth pass: each garment hangs over the layers draped before it

    # ------------------------------------------------------------------ helpers
    def _normals(self):
        """Area-weighted skin normals averaged over coincident positions (UV seams split the vertices)."""
        self.bm.normal_update()
        verts = list(dict.fromkeys(v for f in self.skin for v in f.verts))
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
        for v in dict.fromkeys(v for f in self.skin for v in f.verts):
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
        verts = list(dict.fromkeys(v for f in faces for v in f.verts))
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
        g.setdefault("tube", {}).update(root)       # free vertex -> its hem root (vents, panel weights)
        return new_faces

    # vents of long coat tails: (angle round the body, degrees: 0 front, 90 left side, 180 back) and how far up
    # the tail they are cut (fraction of the drop)
    VENTS = ((0.0, 1.0), (90.0, 1.0), (-90.0, 1.0), (180.0, 1.0))

    def vents(self, name, cut, drop):
        """Split a long coat's free-hanging tube into panels (the front parting below the closure, side vents and
        a centre back vent, as on real frock coats / long coats / tailcoats) and skin each panel to the leg it covers: the front panels follow their own
        thigh, the back panels the pelvis and their side's thigh. Without vents one tube of fabric spans both
        legs and every stride tears a knee through it."""
        g = self.garments[name]
        tube = g.get("tube", {})
        if not tube:
            return 0
        cy = self.rig.neck_c.y
        roots = list(dict.fromkeys(tube.values()))

        def ang(co):
            return math.degrees(math.atan2(co.x, -(co.y - cy)))

        def adiff(a, b):
            return abs((a - b + 180.0) % 360.0 - 180.0)
        # the hem root nearest each vent angle, then the vertical edge chain hanging from it
        split = []
        for va, frac in self.VENTS:
            r0 = min(roots, key=lambda r: adiff(ang(r.co), va))
            col = sorted([v for v, r in tube.items() if r is r0 and v is not r0], key=lambda v: -v.co.z)
            col = [v for v in col if (cut - v.co.z) >= drop * (1.0 - frac) - 1e-4]
            chain = [r0] + [v for v in sorted(tube, key=lambda v: -v.co.z) if tube[v] is r0 and v is not r0]
            for a, b in zip(chain, chain[1:]):
                if b in col:
                    e = self.bm.edges.get((a, b))
                    if e is not None:
                        split.append(e)
        if split:
            # remember the vent edges by position: they stay plain fabric edges (no turned-in thickness band,
            # whose two halves would cross at the top of the parting - drape.rims)
            g.setdefault("vent_pos", set()).update(
                tuple(round(c, 5) for c in v.co) for e in split for v in e.verts)
            bmesh.ops.split_edges(self.bm, edges=split)
        # panel side / front from the faces: after the cut no face straddles a vent, so the centre of every face
        # says which panel it is on; a vertex takes the side all its faces agree on (a vertex still shared at the
        # top of a vent stays undecided and keeps its own weights)
        free = [f for f in self.faces_of(name) if max(v.co.z for v in f.verts) < cut + 1e-4]
        votes = {}
        for f in free:
            c = f.calc_center_median()
            sd = "l" if c.x > 0 else "r"
            for v in f.verts:
                votes.setdefault(v, set()).add((sd, c.y < cy))
        side_of, front_of = {}, {}
        for v, vs in votes.items():
            sides = {x[0] for x in vs}
            if len(sides) == 1:
                side_of[v] = sides.pop()
                front_of[v] = sum(1 for x in vs if x[1]) * 2 >= len(vs)
        g["panel_side"] = side_of
        # panel weights: front panels -> own thigh, back panels -> pelvis + own thigh (+ cloth bones later)
        tl, tr, pv = self.gi("thigh_l"), self.gi("thigh_r"), self.gi("pelvis")
        n = 0
        for f in self.faces_of(name):
            for v in f.verts:
                if v.co.z >= cut - 1e-4 or v not in side_of:
                    continue
                t = min(1.0, (cut - v.co.z) / max(drop, 1e-3))
                left = side_of[v] == "l"
                front = front_of[v]
                ks = _smooth(t * 1.4)
                own = self.weights(v)
                leg = tl if left else tr
                if front:
                    target = {leg: 1.0}
                else:
                    target = {pv: 0.35, leg: 0.65}
                w = {gk: x * (1 - ks) for gk, x in own.items()}
                for gk, x in target.items():
                    w[gk] = w.get(gk, 0.0) + x * ks
                self.set_weights(v, w)
                n += 1
        self.log(f"  anime: {self.key}: {name}: {len(self.VENTS)} vents, {n} panel vertices re-skinned")
        return n

    def capelet(self, spec):
        """Wide collar lying over the shoulders (the Obelisk girls' navy capelet in their Tag Force portraits):
        a cone from the neck base out to the shoulders, draped over the jacket / shirt underneath (pushed out
        radially wherever they reach further), open at the front."""
        idx, mname = self.material("Capelet", spec.get("tint", False))
        g = self.garments.setdefault("Capelet", dict(mat=mname, idx=idx, spec=spec))
        r = self.rig
        rx, ry = r.neck_r
        cy = r.neck_c.y
        top, drop = r.neck + 0.006, spec.get("drop", 0.075)
        sx, sy = r.shoulder_x + spec.get("wide", 0.06) - rx, spec.get("deep", 0.065)
        # what the capelet lies on: max distance from the neck axis per direction / height
        under = [self.garments[n]["idx"] for n in ("Jacket", "Shirt") if n in self.garments]
        pts = np.array([v.co[:] for f in self.bm.faces if f.material_index in under for v in f.verts])
        reach = {}
        if len(pts):
            pts = pts[(pts[:, 2] > top - drop - 0.04) & (np.abs(pts[:, 0]) < r.shoulder_x + 0.08)]   # not the sleeves
            ang = np.degrees(np.arctan2(pts[:, 0], -(pts[:, 1] - cy)))
            rad = np.hypot(pts[:, 0], pts[:, 1] - cy)
            for a_, z_, r_ in zip(np.round(ang / 8).astype(int), np.round(pts[:, 2] / 0.01).astype(int), rad):
                k = (a_, z_)
                reach[k] = max(reach.get(k, 0.0), r_)

        def clearance(a_deg, z):
            best = 0.0
            for da in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    best = max(best, reach.get((int(round(a_deg / 8)) + da, int(round(z / 0.01)) + dz), 0.0))
            return best

        seg, rows = 36, 6
        a0 = math.radians(spec.get("open", 36) * 0.5)
        angs = [a0 + (2 * math.pi - 2 * a0) * i / seg for i in range(seg + 1)]
        s3, cl, cr = self.gi("spine_03"), self.gi("clavicle_l"), self.gi("clavicle_r")
        ul, ur = self.gi("upperarm_l"), self.gi("upperarm_r")
        grid = {}
        for wall, extra in (("o", 0.0), ("i", -0.004)):
            for j in range(rows + 1):
                t = j / rows
                z = top - drop * t
                for i, a in enumerate(angs):
                    ex, ey = rx + 0.012 + sx * t ** 0.8, ry + 0.012 + sy * t ** 0.8
                    x, y = math.sin(a) * ex, cy - math.cos(a) * ey
                    rad = math.hypot(x, y - cy)
                    need = clearance(math.degrees(math.atan2(x, -(y - cy))), z) + 0.010
                    if rad < need:
                        x, y = x * need / rad, cy + (y - cy) * need / rad
                    # the outer part rides on the shoulder: clavicle, then upper arm (it was built over the
                    # T-pose's level arms and has to drape down with them)
                    side = abs(math.sin(a)) * t
                    k_cl = 0.5 * side
                    k_ua = 0.55 * _smooth((abs(x) - r.shoulder_x + 0.02) / 0.06) * side
                    v = self.bm.verts.new((x * (1 + extra / max(ex, 1e-3)), cy + (y - cy) * (1 + extra / max(ey, 1e-3)), z))
                    self.set_weights(v, {s3: max(0.0, 1 - k_cl - k_ua), (cl if x > 0 else cr): k_cl,
                                         (ul if x > 0 else ur): k_ua})
                    grid[wall, j, i] = v
        faces = []

        def quad(*vs):
            f = self.bm.faces.new(vs)
            f.material_index = idx
            f.smooth = True
            faces.append(f)
        for j in range(rows):
            for i in range(seg):
                quad(grid["o", j, i + 1], grid["o", j, i], grid["o", j + 1, i], grid["o", j + 1, i + 1])
                quad(grid["i", j, i], grid["i", j, i + 1], grid["i", j + 1, i + 1], grid["i", j + 1, i])
        for i in range(seg):
            quad(grid["o", rows, i + 1], grid["o", rows, i], grid["i", rows, i], grid["i", rows, i + 1])
        for i in (0, seg):
            for j in range(rows):
                vs = (grid["o", j, i], grid["o", j + 1, i], grid["i", j + 1, i], grid["i", j, i])
                quad(*(vs if i == seg else tuple(reversed(vs))))
        g["hem"] = top - drop
        return faces

    def collar(self, spec, height, open_deg, flare=0.016, lift=0.012):
        """Stand-up collar round the neck base (outer + inner wall + rim), open at the front and flaring out by
        `flare` at the top; its own garment, so the lining can differ (the portraits: white-lined collars)."""
        idx, mname = self.material("Collar", spec.get("tint", False))
        g = self.garments.setdefault("Collar", dict(mat=mname, idx=idx, spec=spec))
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
                grow = lift + 0.006 + flare * t + extra
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
        g["collar"] = dict(rx=rx, ry=ry, cy=r.neck_c.y, z0=z0, z1=z1, grow=lift + 0.006, flare=flare)
        return faces

    # ------------------------------------------------------------------ the uniform
    def jacket(self, spec):
        r = self.rig
        length = spec.get("length", "hip")
        hem = r.hem_z(length)
        cutz = max(hem, r.crotch_true + 0.02)       # skin shell only above the real fork of the legs
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
            return abs(co.x) < cuff_x and co.z > cutz and co.z < r.shoulder_z + 0.12

        def in_gap(c):
            return c.y < r.neck_c.y and abs(c.x) < gap(c.z)

        faces = self.select(inside)
        covers = [f for f in self.select(inside, every=True) if not in_gap(f.calc_center_median())]
        self.shell(faces, spec.get("loose", 0.016), "Jacket", spec, covers)
        self.cut("Jacket", (cuff_x, 0, 0), (1, 0, 0))
        self.cut("Jacket", (-cuff_x, 0, 0), (-1, 0, 0))
        self.cut("Jacket", (0, 0, cutz), (0, 0, -1))
        if opening:
            for sgn in (1, -1):
                d = Vector((sgn * (x1 - x0), 0, top - z0)).normalized()
                no = Vector((d.z, 0, -d.x))
                if no.x * sgn > 0:                            # point into the opening
                    no = -no
                self.cut("Jacket", (sgn * x0, 0, z0), no,
                         region=lambda c, sgn=sgn: c.y < r.neck_c.y and c.x * sgn > -0.002 and c.z > z0 - 0.02)
        # cloth: the jacket hangs from the chest / shoulder blades over the shirt and trousers, with round sleeves
        # that widen a little towards the cuff. The free-hanging part (blazer hem, coat tails) is hung from the
        # draped hem afterwards, so it keeps its clean cut instead of being re-draped round the legs; then a
        # turned-in band of fabric thickness runs along every open edge
        self.drape.garment("Jacket", taper=0.2, ease=0.006 + spec.get("loose", 0.0) * 0.25, clear=0.008,
                           sleeve_ease=(0.008, 0.02))
        drop = spec.get("drop", r.hem_drop(length))
        free = drop + (cutz - hem)                  # the hanging part reaches the designed hem height
        if free > 1e-4:
            long = drop > 0.15
            self.extend("Jacket", self.edges_at("Jacket", cutz), free, spec.get("flare", 0.035 if not long else 0.07),
                        rings=max(3 if not long else 6, int(round(free / 0.03))), thigh=0.45 if not long else 0.8,
                        front=spec.get("tails", 1.0))
            if long:
                self.vents("Jacket", cutz, free)
        self.drape.rims("Jacket", depth=0.007)
        if spec.get("collar", 0.05):
            trim = spec.get("trim", spec.get("color"))
            cspec = dict(color=spec.get("collar_color", spec.get("color")), trim=spec.get("collar_trim", trim),
                         lining=spec.get("lining", spec.get("color")), tint=spec.get("tint", False),
                         trims=("collar",) if "collar" in spec.get("trims", ()) else (), trim_w=spec.get("trim_w", 0.012))
            self.collar(cspec, spec.get("collar", 0.05), 70 + 80 * opening, spec.get("collar_flare", 0.016))
        g = self.garments["Jacket"]
        g["cuff_x"], g["hem"], g["gap"] = cuff_x, hem - drop, gap
        g["cut"] = cutz                    # below: the free-hanging hem / tails (they hide nothing)
        if drop > 0.15:
            g["cloth"] = dict(prefix="coattail", cut=cutz, drop=free)     # long coat tails swing (cloth_bones)
        if spec.get("capelet"):
            self.capelet(spec["capelet"])

    def shirt(self, spec):
        r = self.rig
        sleeves = spec.get("sleeves", "short")
        sx = {"short": r.shoulder_x + 0.10, "long": r.wrist_x - 0.04, "none": r.shoulder_x - 0.01}[sleeves]
        hem = r.hem_z(spec.get("length", "hip"))
        cutz = max(hem, r.crotch_true + 0.02)
        turtle = spec.get("turtleneck", False)
        neck = r.neck + 0.05 if turtle else r.neck - 0.012

        def inside(co):
            if abs(co.x) < r.neck_r[0] + 0.035 and co.z > neck:
                return False
            return abs(co.x) < sx and co.z > cutz

        self.shell(self.select(inside), 0.010, "Shirt", spec, self.select(inside, every=True))
        self.cut("Shirt", (sx, 0, 0), (1, 0, 0))
        self.cut("Shirt", (-sx, 0, 0), (-1, 0, 0))
        self.cut("Shirt", (0, 0, cutz), (0, 0, -1))
        if turtle:
            self.cut("Shirt", (0, 0, neck), (0, 0, 1), region=lambda c: abs(c.x) < r.neck_r[0] + 0.04)
        self.drape.garment("Shirt", taper=0.3, ease=0.003, clear=0.004, sleeve_ease=(0.004, 0.008),
                           torso_top=(neck - 0.02) if turtle else None)
        tail = 0.03 if spec.get("length", "hip") == "hip" and not spec.get("tucked") else 0.0
        if tail + (cutz - hem) > 1e-4:
            self.extend("Shirt", self.edges_at("Shirt", cutz), tail + (cutz - hem), 0.012,
                        rings=max(1, int(round((tail + cutz - hem) / 0.03))), thigh=0.3)

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
        # straight trouser legs hanging from the seat and thighs (no crotch / knee anatomy)
        self.drape.garment("Pants", sleeves=False, legs=True, torso_top=top, taper=0.45, ease=0.003,
                           clear=0.005, hem_width=width, roundness=0.8, hull=False)
        self.drape.rims("Pants", depth=0.005)

    def skirt(self, spec):
        r = self.rig
        top = r.pelvis + 0.04
        cut = max(r.crotch + 0.05, r.crotch_true + 0.02)     # skin shell only above the real fork of the legs
        length = spec.get("length", 0.17) + (cut - (r.crotch + 0.05))   # same hem height as designed

        def inside(co):
            return cut < co.z < top

        self.shell(self.select(inside), 0.010, "Skirt", spec, self.select(inside, every=True))
        self.cut("Skirt", (0, 0, top), (0, 0, 1))
        self.cut("Skirt", (0, 0, cut), (0, 0, -1))
        self.drape.garment("Skirt", sleeves=False, torso_top=top, taper=0.1, ease=0.002, clear=0.006, smooth=2)
        self.extend("Skirt", self.edges_at("Skirt", cut), length, 0.06, rings=max(4, int(round(length / 0.04))),
                    thigh=0.55, pleats=spec.get("pleats", 16))
        self.garments["Skirt"]["hem"] = cut - length
        self.garments["Skirt"]["cloth"] = dict(prefix="skirt", cut=cut, drop=length)
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

    def gloves(self, spec):
        """Fingerless gloves from the forearm to the knuckles (Alexis's duel gloves in her Duel Links art)."""
        r = self.rig
        x0 = r.elbow_x + (r.wrist_x - r.elbow_x) * spec.get("from", 0.35)
        x1 = abs(r.h["middle_01_l"].x) - 0.005 if "middle_01_l" in r.h else r.wrist_x + 0.06

        def inside(co):
            return x0 < abs(co.x) < x1

        self.shell(self.select(inside), 0.004, "Gloves", spec, self.select(inside, every=True))
        for sgn in (1, -1):
            self.cut("Gloves", (sgn * x0, 0, 0), (-sgn, 0, 0), region=lambda c, sgn=sgn: c.x * sgn > 0)
            self.cut("Gloves", (sgn * x1, 0, 0), (sgn, 0, 0), region=lambda c, sgn=sgn: c.x * sgn > 0)

    def shoe_top(self):
        n = len(self.roles)
        zs = [v.co.z for f in self.bm.faces if f.material_index < n and self.roles[f.material_index] == "shoes"
              for v in f.verts]
        return float(np.percentile(zs, 97)) if zs else self.rig.ankle + 0.06

    # ------------------------------------------------------------------ finish
    def finish(self, leg_contact=None):
        """Layered skinning, drop covered skin, write the mesh, unwrap + paint every garment. leg_contact (dict)
        receives {rest position: how much a free-hanging hem vertex follows the leg under it}."""
        from .drape import fix_leg_sides, hide_covered, inherit_weights
        hide_covered(self, self.log)
        inherit_weights(self, self.log)
        fix_leg_sides(self, self.log)
        if leg_contact is not None:
            for v, k in getattr(self, "leg_contact", {}).items():
                if v.is_valid:
                    leg_contact[tuple(round(c, 5) for c in v.co)] = k
        bmesh.ops.delete(self.bm, geom=[f for f in self.covered if f.is_valid], context="FACES")
        loose = [v for v in self.bm.verts if not v.link_faces]
        bmesh.ops.delete(self.bm, geom=loose, context="VERTS")
        idx_of = {name: g["idx"] for name, g in self.garments.items()}
        self.bm.to_mesh(self.me)
        self.bm.free()
        self.me.update()
        for name, g in self.garments.items():
            g["name"] = name
            _unwrap(self.obj, idx_of[name])
            rel = f"{TEX_REL}/{self.key}/T_{self.key}_{name}"
            paint(self.me, idx_of[name], g, self.rig, os.path.join(C.OUT_TEXTURES, rel + ".png"))
            # two-sided (the masked toon variant): the inside of an open jacket / coat tail / skirt is seen
            palette.register({g["mat"]: dict(kind="toon", color=(1.0, 1.0, 1.0), rough=0.85, fill=0.45, base=rel,
                                             masked=name in ("Jacket", "Skirt", "Capelet"))})
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
        key = tuple(sorted((tuple(round(x, 3) for x in a), tuple(round(x, 3) for x in b))))   # 1 mm: plane cuts
        by_pos[key] = by_pos.get(key, 0) + n
    for key, n in by_pos.items():
        if n != 1:
            continue
        a, b = Vector(key[0]), Vector(key[1])
        k = max(1, int((b - a).length / step))
        for i in range(k + 1):
            pts.append(tuple(a + (b - a) * (i / k)))
    return np.array(pts, np.float32) if pts else np.zeros((0, 3), np.float32)


# crease lines: a darker, slightly cooler shade of the cloth (anime fold lines, not photographic AO)
FOLD_DARK = 0.30


PAINT_SS = 2              # garment textures are painted at this supersampling and filtered down (smooth trims)


def paint(me, mat_idx, g, rig, path, size=None):
    spec = g["spec"]
    out_size = size or (2048 if g["spec"] is not None and "cuff_x" in g else 1024)
    size = out_size * PAINT_SS
    pos, mask = bake_positions(me, mat_idx, size)
    base = np.array(spec.get("color", (1, 1, 1)), np.float32)
    img = np.zeros((size, size, 3), np.float32)
    img[...] = base
    P = pos[mask]
    col = np.repeat(base[None], len(P), 0)
    if len(P) and g.get("name"):
        from .drape import fold_mask
        fm = fold_mask(P, g["name"], rig, spec)[:, None]
        shade = base * np.array((0.86, 0.88, 1.0), np.float32) * (1 - FOLD_DARK)
        col = col * (1 - fm) + shade[None] * fm
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
                if spec.get("trim2") is not None:          # a second, inner line along the trim
                    col[(d >= tw) & (d < tw + spec.get("trim2_w", 0.006))] = spec["trim2"]
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
    cg = g.get("collar")
    if cg and spec.get("lining") is not None and len(P):
        # inner wall of the collar: inside the outer wall's ellipse at that height
        t = np.clip((P[:, 2] - cg["z0"]) / (cg["z1"] - cg["z0"]), 0, 1)
        go = cg["grow"] + cg["flare"] * t
        rho = np.hypot(P[:, 0] / (cg["rx"] + go), (P[:, 1] - cg["cy"]) / (cg["ry"] + go))
        col[rho < 0.985] = spec["lining"]
    sh = spec.get("shoulder")                         # band round the top of the sleeves
    if sh and len(P) and spec.get("sleeves", "long") != "none":
        ax = np.abs(P[:, 0])
        x0 = rig.shoulder_x + sh.get("at", 0.035)
        on_arm = P[:, 2] > rig.shoulder_z - 0.15
        col[(ax > x0) & (ax < x0 + sh.get("w", 0.03)) & on_arm] = sh.get("color", tc)
    if spec.get("panel"):                           # two-tone: a coloured band (Obelisk coats)
        pz0, pz1, pc = spec["panel"]
        col[(P[:, 2] > pz0) & (P[:, 2] < pz1)] = pc
    sd = spec.get("shield")
    if sd and len(P):
        # the Duel Academy chest panel: a shield (pentagon) from below the collar to a point on the chest, in
        # its own colour with a border (Tag Force Special / Duel Links art)
        top = rig.neck - sd.get("below", 0.02)
        W = sd.get("w", 0.11)
        side_z = top - sd.get("side", 0.07)
        point = side_z - sd.get("point", 0.08)
        ax = np.abs(P[:, 0])
        zb = point + (side_z - point) * np.clip(ax / W, 0, 1)
        d = np.minimum(np.minimum(top - P[:, 2], W - ax), (P[:, 2] - zb) * W / math.hypot(W, side_z - point))
        front = (P[:, 1] < rig.neck_c.y) & (P[:, 2] < rig.shoulder_z + 0.06)
        inside = front & (d > 0)
        bw = sd.get("border_w", 0.012)
        col[inside] = sd.get("color", (0.96, 0.96, 0.95))
        col[inside & (d < bw)] = sd.get("border", tc)
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
    # anti-aliasing: the trims, the shield panel, buttons and crease lines are hard tests per texel; painting at
    # PAINT_SS x and filtering down gives them smooth edges instead of texel steps along curved seams
    hi = Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
    atomic.save_image(hi.resize((out_size, out_size), Image.LANCZOS), path, optimize=True)


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


# --------------------------------------------------------------------------- cloth bones (secondary motion)
CLOTH_CHAINS = 8          # bone chains round a skirt / coat hem
CLOTH_SEG = 0.11          # length of each of the two chain segments (m)
CLOTH_SHARE = 0.72        # how much of the hem the cloth bones carry (the rest keeps following the thighs)
COAT_SWING = 0.28         # vented coat panels: share of their cloth bones (they are skinned to the legs)


def cloth_bones(arm, body, rig, garments, log=print, leg_contact=None):
    """Bone chains round the free-hanging part of skirts and long coats, skinned into the hem, so Unreal's
    spring layer (UDAAvatarAnimInstance, bones skirt_* / coattail_*) can swing the cloth. The rest pose comes
    from body landmarks only (not the garment), so every member built on the same base model gets identical
    bones and the shared union skeleton stays consistent (build._merge_rig)."""
    specs = [g["cloth"] for g in garments.values() if g.get("cloth")]
    if not specs:
        return 0
    rx, ry = abs(rig.h["thigh_l"].x) + 0.075, 0.115
    z0 = rig.crotch + 0.05
    cy = rig.neck_c.y
    for o in bpy.context.scene.objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    pelvis = eb["pelvis"]
    rings = {}
    for cs in specs:
        pre = cs["prefix"]
        for k in range(CLOTH_CHAINS):
            a = 2 * math.pi * k / CLOTH_CHAINS
            d = Vector((math.sin(a), -math.cos(a), 0.0))
            head = Vector((d.x * rx, cy + d.y * ry, z0))
            # chains over a leg ride on that thigh (the panel follows the leg, the springs swing it on top);
            # the front and back centre chains hang from the pelvis
            if abs(math.sin(a)) > 0.38:
                parent = eb["thigh_l" if d.x > 0 else "thigh_r"]
            else:
                parent = pelvis
            pts = [head]
            for j in range(1, 4):
                seg = CLOTH_SEG if j < 3 else 0.03
                pts.append(pts[-1] + Vector((0, 0, -seg)) + d * (0.025 if j < 3 else 0.005))
            for j in range(3):
                name = f"{pre}_{k:02d}_{j + 1}"
                b = eb.get(name) or eb.new(name)
                b.head, b.tail = pts[j], pts[j + 1]
                b.parent = parent
                b.use_connect = j > 0
                b.use_deform = j < 2
                parent = b
        rings[pre] = cs
    bpy.ops.object.mode_set(mode="OBJECT")

    me = body.data
    vgs = {vg.name: vg for vg in body.vertex_groups}
    # hem vertices lying against a leg follow it (drape.inherit_weights); the cloth bones only get the rest.
    # Keyed by rest position (the bmesh vertices are gone by now).
    contact = leg_contact or {}

    def group(name):
        if name not in vgs:
            vgs[name] = body.vertex_groups.new(name=name)
        return vgs[name]

    mats = {g["idx"]: g.get("cloth") for g in garments.values() if g.get("cloth")}
    on = {}
    for p in me.polygons:
        cs = mats.get(p.material_index)
        if cs is not None:
            for v in p.vertices:
                on[v] = cs
    count = 0
    for vi, cs in on.items():
        v = me.vertices[vi]
        t = (cs["cut"] - v.co.z) / max(cs["drop"], 1e-3)
        if t <= 0.02:
            continue
        t = min(1.0, t)
        share = CLOTH_SHARE * _smooth(t * 1.15)
        # leg-following hems keep a little swing (COAT_SWING of the chains, which ride the thighs themselves)
        share *= max(COAT_SWING if cs["prefix"] == "coattail" else 0.0,
                     1.0 - contact.get(tuple(round(c, 5) for c in v.co), 0.0))
        a = math.atan2(v.co.x, -(v.co.y - cy)) % (2 * math.pi)
        f = a / (2 * math.pi) * CLOTH_CHAINS
        k0 = int(math.floor(f)) % CLOTH_CHAINS
        k1 = (k0 + 1) % CLOTH_CHAINS
        wa = 1.0 - (f - math.floor(f))
        seg2 = _smooth((t - 0.25) / 0.5)
        for gi, gw in [(g.group, g.weight) for g in v.groups]:    # existing weights make room
            if gw > 0:
                body.vertex_groups[gi].add([vi], gw * (1 - share), "REPLACE")
        for kk, wk in ((k0, wa), (k1, 1 - wa)):
            for j, ws in ((1, 1 - seg2), (2, seg2)):
                w = share * wk * ws
                if w > 1e-4:
                    group(f"{cs['prefix']}_{kk:02d}_{j}").add([vi], w, "ADD")
        count += 1
    log(f"  anime: {body.name}: cloth bones {', '.join(sorted(rings))} ({CLOTH_CHAINS} chains), {count} hem vertices")
    return count


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
        shirt = dict(spec["shirt"])
        if spec.get("jacket", {}).get("length") in ("thigh", "knee", "calf"):
            # under a long coat the shirt is tucked in: it ends inside the trousers' waistband (its tail would
            # ride the legs, and its hem would sit right where the trousers meet the coat panels)
            shirt["tucked"] = True
            shirt["length"] = "waist"
        t.shirt(shirt)
    if "jacket" in spec:
        t.jacket(spec["jacket"])
    if "boots" in spec:
        t.boots(spec["boots"])
    if "gloves" in spec:
        t.gloves(spec["gloves"])
    contact = {}
    t.finish(contact)
    cloth_bones(arm, body, t.rig, t.garments, log, leg_contact=contact)
    return t


def fix_skin(obj, mat_idx, src_png, dst_png, rig, legs=False):
    """Paint the base model's body texture back to bare skin where its painted-on clothing would show with
    the uniform: gloves on the hands (and tights on the legs for skirts). The skin tone is sampled from the
    neck."""
    with Image.open(src_png) as src_img:
        img = np.asarray(src_img.convert("RGBA")).astype(np.float32) / 255.0
    h, w = img.shape[:2]
    pos, mask = bake_positions(obj.data, mat_idx, max(h, w))
    if (h, w) != mask.shape:
        pos, mask = pos[:h, :w], mask[:h, :w]
    neck = mask & (pos[..., 2] > rig.neck + 0.005) & (pos[..., 2] < rig.neck + 0.05)
    if not neck.any():
        atomic.save_image(Image.fromarray((img * 255 + 0.5).astype(np.uint8)), dst_png)
        return dst_png
    ref = np.median(img[neck][:, :3], axis=0)
    region = mask & (np.abs(pos[..., 0]) > rig.wrist_x - 0.06)
    if legs:
        region |= mask & (pos[..., 2] < rig.crotch + 0.03) & (np.abs(pos[..., 0]) < rig.shoulder_x + 0.2)
    # Grow the recoloured area a little to cover the seam, but never paint texels
    # that do not belong to the body island (other atlas regions share this texture).
    region = ndimage.binary_dilation(region, iterations=3) & mask
    img[region, :3] = ref
    atomic.save_image(Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8)), dst_png, optimize=True)
    return dst_png
