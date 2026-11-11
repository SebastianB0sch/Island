"""
Atelier garments on the VRoid base bodies.

The atelier's outfit generator (atelier/outfit.py: tops, jackets and coats with sleeves, collars, pleated
skirts, trousers, legwear, bows, ties, belts, capes, badges - cut as offsets of the body's cross-sections and
painted into a texture atlas) only knows the atelier body. This module gives it a VRoid body to cut from, the
way clumphair.py gives the hair generator a VRoid skull:

  VBody     the cross-sections of a loaded base model, measured from its skin (rest pose): torso rings by
            height, arm rings along the arm, leg rings by height - answered in the atelier's design space, so
            the garment presets keep their vocabulary (hem=0.98 is "just below the waist" on every body). A
            landmark map (ankle, knee, crotch, waist, shoulder line, neck base; shoulder, elbow, wrist) takes
            the finished parts onto the model
  build()   look entry -> garment mesh object + hem spring bones + atlas texture(s) + palette materials. The
            parts are skinned with the weights of the nearest skin (they deform exactly like the body under
            them); the base model's own tops / bottoms are deleted, and so is the skin (and every inner
            layer) that an outer garment covers - nothing is left underneath to poke through in motion

A look asks for it with entry["wear"]: [(garment kind, params)] in wearing order (atelier/outfit.GARMENTS;
see looks.py for the presets). Not available on a VRoid body: generated shoes (the base model's shoes stay,
recoloured by colors["shoes"]; a "shoes" item is ignored) and full gloves (fingerless only).
"""

import math
import os

import numpy as np

from .. import config as C
from .. import palette
from . import skeleton as S

TEX_REL = "Characters"
OBJECT_NAME = "Wardrobe"            # models.add_outline skips it: the parts bring their own ink hull
ARM_PARTS = ("sleeve", "band", "glove")
RIGID_PARTS = ("buckle", "deckbox", "clasp", "button", "emblem", "knot", "tieknot", "capeclasp")
CHAIN_PREFIXES = ("skirt_", "coattail_")
ARM_BONES = ("upperarm", "lowerarm", "hand", "thumb", "index", "middle", "ring", "pinky")
LEG_BONES = ("thigh", "calf", "foot", "ball")
COVER_REACH = 0.05                  # an outer layer this close above a vertex hides it
SKIN_MARGIN = 0.022                 # covered skin / cloth this close to visible skin / cloth stays
THIGH_FOLLOW = 0.55                 # how much hanging cloth (skirt, coat tails) follows the thigh under it


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _blur(a, sigma, wrap=()):
    from scipy import ndimage
    mode = ["wrap" if i in wrap else "nearest" for i in range(a.ndim)]
    return ndimage.gaussian_filter(a, sigma, mode=mode)


def _fill_rows(R):
    """Fill NaN gaps of each row by periodic linear interpolation over the columns."""
    n = R.shape[1]
    idx = np.arange(n)
    last = None
    for r in range(R.shape[0]):
        ok = ~np.isnan(R[r])
        if ok.sum() >= 4:
            R[r] = np.interp(idx, idx[ok], R[r][ok], period=n)
            last = r
    for r in range(R.shape[0]):               # rows with (almost) no hit: nearest filled row
        if np.isnan(R[r]).any():
            ok = [q for q in range(R.shape[0]) if not np.isnan(R[q]).any()]
            R[r] = R[min(ok, key=lambda q: abs(q - r))]
    return R


class _Table:
    """r(s, angle) on a regular grid: rows along the axis, columns round it."""

    def __init__(self, s, R):
        self.s, self.R = np.asarray(s), R
        self.n = R.shape[1]

    def __call__(self, s, ang):
        s, ang = np.broadcast_arrays(np.asarray(s, np.float64), np.asarray(ang, np.float64))
        f = np.clip((s - self.s[0]) / (self.s[1] - self.s[0]), 0.0, len(self.s) - 1.001)
        i = np.floor(f).astype(int)
        t = f - i
        g = (ang % (2 * np.pi)) / (2 * np.pi) * self.n
        j = np.floor(g).astype(int) % self.n
        u = g - np.floor(g)
        j1 = (j + 1) % self.n
        return ((self.R[i, j] * (1 - u) + self.R[i, j1] * u) * (1 - t)
                + (self.R[i + 1, j] * (1 - u) + self.R[i + 1, j1] * u) * t)


# --------------------------------------------------------------------------- the measured body
class VBody:
    """The atelier Body interface (torso_ring / arm_ring / leg_ring / ...) answered from a VRoid model's skin.
    Positions are in the atelier's design space; to_model() takes points onto the model."""

    def __init__(self, arm, body, rig, female, log=None):
        from mathutils import Vector
        from mathutils.bvhtree import BVHTree
        from .models import role_of
        self.female = female
        self.over_shoes = False                # leg rings include the shoes (trousers hang over them)
        me = body.data
        n = len(me.vertices)
        co = np.empty(n * 3)
        me.vertices.foreach_get("co", co)
        self.co = co = co.reshape(-1, 3)
        roles = [role_of(s.material.name if s.material else "") for s in body.material_slots]
        gnames = [g.name for g in body.vertex_groups]
        W = np.zeros((n, len(gnames)), np.float32)
        for v in me.vertices:
            for e in v.groups:
                W[v.index, e.group] = e.weight
        W /= np.maximum(W.sum(1, keepdims=True), 1e-9)
        self.W, self.gnames = W, gnames
        arm_cols = [i for i, g in enumerate(gnames) if g.startswith(ARM_BONES)]
        arm_w = W[:, arm_cols].sum(1)
        tris, tri_face, shoe_tris = [], [], []
        for p in me.polygons:
            role = roles[p.material_index] if p.material_index < len(roles) else ""
            vs = list(p.vertices)
            for k in range(1, len(vs) - 1):
                t = (vs[0], vs[k], vs[k + 1])
                if role == "skin":
                    tris.append(t)
                    tri_face.append(p.index)
                elif role == "shoes":
                    shoe_tris.append(t)
        self.tris = np.array(tris)
        self.tri_face = np.array(tri_face)
        self.skin_faces = sorted(set(tri_face))
        cen = co[self.tris].mean(1)
        verts = [Vector(c) for c in co]
        self.bvh = BVHTree.FromPolygons(verts, [tuple(t) for t in tris])
        torso_t = [tuple(t) for t in self.tris[arm_w[self.tris].mean(1) < 0.5]]
        left_t = [tuple(t) for t in self.tris[cen[:, 0] > 0.0]]
        shoes_l = [t for t in shoe_tris if co[list(t)][:, 0].mean() > 0.0]
        bvh_torso = BVHTree.FromPolygons(verts, torso_t)
        bvh_left = BVHTree.FromPolygons(verts, left_t)
        arm_t = [tuple(t) for t in self.tris[(cen[:, 0] > 0.0) & (arm_w[self.tris].mean(1) >= 0.5)]]
        bvh_arm = BVHTree.FromPolygons(verts, arm_t)
        bvh_shoes = BVHTree.FromPolygons(verts, shoes_l) if shoes_l else None
        h = {b.name: np.array(b.head_local) for b in arm.data.bones}
        self.h = h

        def cast(tree, o, d, dist):
            hit = tree.ray_cast(Vector(o), Vector(d), dist)
            return hit[3] if hit[0] is not None else np.nan

        # ---- torso: rays from the centre line outwards, by height (the arms are left out; their holes close)
        crotch = float(rig.crotch_true)
        z_top = float(h["head"][2])
        zs = np.arange(crotch + 0.004, z_top, 0.006)
        skin_v = np.unique(self.tris)
        mid = co[skin_v][np.abs(co[skin_v][:, 0]) < 0.03]
        cy = np.full(len(zs), np.nan)
        for i, z in enumerate(zs):
            sl = mid[np.abs(mid[:, 2] - z) < 0.012]
            if len(sl) >= 2 and np.ptp(sl[:, 1]) > 0.03:
                cy[i] = 0.5 * (sl[:, 1].min() + sl[:, 1].max())
        ok = ~np.isnan(cy)
        cy = _blur(np.interp(zs, zs[ok], cy[ok]), 2.0)
        nth = 120
        th = np.linspace(0.0, 2 * np.pi, nth, endpoint=False)
        dirs = np.stack([np.sin(th), -np.cos(th), np.zeros(nth)], axis=1)
        x_lim = float(h["upperarm_l"][0]) + 0.035
        R = np.full((len(zs), nth), np.nan)
        for i, z in enumerate(zs):
            o = (0.0, cy[i], z)
            for j in range(nth):
                r = cast(bvh_torso, o, dirs[j], 0.4)
                if not np.isnan(r) and abs(r * dirs[j, 0]) <= x_lim:
                    R[i, j] = r
        R = _fill_rows(R)
        R = np.maximum(R, _blur(np.maximum(R, _blur(R, (1.5, 1.5), wrap=(1,))), (0.7, 0.7), wrap=(1,)))
        ext = (R * np.abs(dirs[:, 0])[None]).max(1)                      # half width by height
        sh_z = float(h["upperarm_l"][2])
        ref = float(np.interp(sh_z - 0.05, zs, ext))
        above = zs > sh_z - 0.05
        wide = np.nonzero(above & (ext >= 0.8 * ref))[0]
        z_sl = float(zs[wide.max()])                                      # shoulder line: top of the shoulders
        neck_mid = 0.5 * (float(h["neck_01"][2]) + z_top)
        self.neck_r = float(np.interp(neck_mid, zs, R.mean(1)))
        nb = np.nonzero((zs > z_sl) & (ext <= self.neck_r + 0.014))[0]
        z_nb = max(float(zs[nb.min()]) if len(nb) else z_sl + 0.03, z_sl + 0.012)   # neck base
        # rows below the crotch: the pattern block closes between the legs (like the atelier's)
        low = np.arange(crotch - 0.05, zs[0] - 1e-6, 0.006)
        k = 1.0 - 0.55 * _smooth((zs[0] - low) / 0.045)
        hips = R[:14].max(0)                                              # round both thighs (coats, long tops)
        z_th = crotch - 0.03
        o = np.array([0.0, cy[0], z_th])
        thighs = np.array([0.4 - cast(bvh_torso, o + dirs[j] * 0.4, -dirs[j], 0.4) for j in range(nth)])
        thighs = np.where(np.isnan(thighs), 0.0, thighs)
        hips = np.maximum(hips, _blur(np.maximum(thighs, _blur(thighs, 2.0, wrap=(0,))), 1.0, wrap=(0,)))
        # ...up to where the trouser legs end inside the hips (leg shells reach ~9 cm above the crotch)
        t_open = _smooth((zs[:26] - zs[12]) / (zs[25] - zs[12]))[:, None]
        R_open = np.concatenate([np.repeat(hips[None], len(low), 0), hips[None] * (1 - t_open) + R[:26] * t_open,
                                 R[26:]])
        R_open = np.maximum(R_open, np.concatenate([R[:1] * k[:, None], R]))
        R = np.concatenate([R[:1] * k[:, None], R])
        cy = np.concatenate([np.full(len(low), cy[0]), cy])
        zs = np.concatenate([low, zs])
        self.torso = self.torso_closed = _Table(zs, R)
        self.torso_open = _Table(zs, R_open)
        self._tz, self._cy = zs, cy
        # waist: the narrowest height between hips and chest (girls); boys' trousers sit lower than that
        lo, hi = crotch + 0.30 * (z_sl - crotch), crotch + 0.68 * (z_sl - crotch)
        band = (zs >= lo) & (zs <= hi)
        ext_all = (R * np.abs(dirs[:, 0])[None]).max(1)
        z_narrow = float(zs[band][np.argmin(ext_all[band])])
        waist = z_narrow if female else min(z_narrow, crotch + 0.46 * (z_sl - crotch))
        waist = min(waist, z_sl - 0.16)
        ankle, knee = float(h["foot_l"][2]), float(h["calf_l"][2])
        self.crotch, self.waist, self.z_sl, self.z_nb = crotch, waist, z_sl, z_nb
        # design height -> model height
        self._zc = np.array([0.0, S.ANKLE, S.KNEE, 0.80, 1.04, 1.26, 1.36, 1.392, 1.41, 2.41])
        self._zv = np.array([0.0, ankle, knee, crotch, waist, z_sl - 0.10, z_sl, z_nb - 0.006, z_nb + 0.002,
                             z_nb + 0.802])
        if np.any(np.diff(self._zv) <= 0):
            raise RuntimeError(f"wardrobe: body landmarks out of order {np.round(self._zv, 3)}")

        # ---- arm (left; the right mirrors it): rays from the arm's axis in planes across it
        sx, ex, wx = float(h["upperarm_l"][0]), float(h["lowerarm_l"][0]), float(h["hand_l"][0])
        self._xc = np.array([0.0, 0.09, S.SHOULDER_X, S.ELBOW_X, S.WRIST_X, S.WRIST_X + 1.0])
        self._xv = np.array([sx - 0.085, sx - 0.050, sx, ex, wx, wx + 1.0])
        ax_pts = np.array([h["upperarm_l"], h["lowerarm_l"], h["hand_l"]])
        xs = np.arange(sx - 0.04, wx + 0.03, 0.008)
        nph = 32
        ph = np.linspace(0.0, 2 * np.pi, nph, endpoint=False)
        ad = np.stack([np.zeros(nph), -np.cos(ph), np.sin(ph)], axis=1)
        RA = np.full((len(xs), nph), np.nan)
        cyz = np.stack([np.interp(xs, ax_pts[:, 0], ax_pts[:, 1]), np.interp(xs, ax_pts[:, 0], ax_pts[:, 2])], axis=1)
        for i, x in enumerate(xs):
            for _ in range(2):                                # second pass from the section's own centre
                o = (x, cyz[i, 0], cyz[i, 1])
                r = np.array([cast(bvh_left, o, ad[j], 0.075) for j in range(nph)])
                if np.isnan(r).any():
                    break
                pts = np.stack([cyz[i, 0] + r * ad[:, 1], cyz[i, 1] + r * ad[:, 2]], axis=1)
                cyz[i] = 0.5 * (pts.min(0) + pts.max(0))
            RA[i] = r
        valid = ~np.isnan(RA).any(1) & (np.nan_to_num(RA, nan=1.0).max(1) < 0.07)
        first = int(np.argmax(valid & (xs > sx + 0.01)))         # the first section clear of the torso
        self.x_free = float(xs[first])
        for i in range(len(xs)):
            if i < first:
                # inside the shoulder: the arm's own skin (the deltoid cap); what faces the torso closes smoothly
                cyz[i] = cyz[first]
                o = (xs[i], cyz[i, 0], cyz[i, 1])
                r = np.array([cast(bvh_arm, o, ad[j], 0.075) for j in range(nph)])
                r = np.minimum(r, RA[first])
                ok = ~np.isnan(r)
                RA[i] = np.interp(np.arange(nph), np.arange(nph)[ok], r[ok], period=nph) if ok.sum() >= 6 else np.nan
            elif not valid[i]:
                src = max(q for q in range(i) if valid[q])
                RA[i], cyz[i] = RA[src], cyz[src]
        for i in range(first - 1, -1, -1):
            if np.isnan(RA[i]).any():
                RA[i] = RA[i + 1] * 0.8
        RA = np.maximum(RA, _blur(np.maximum(RA, _blur(RA, (1.0, 1.0), wrap=(1,))), (0.6, 0.6), wrap=(1,)))
        self.arm = _Table(xs, RA)
        self._ax, self._acy, self._acz = xs, _blur(cyz[:, 0], 1.5), _blur(cyz[:, 1], 1.5)

        # ---- leg (left): rays from the leg's axis by height; with and without the shoes
        lg = np.array([h["foot_l"], h["calf_l"], h["thigh_l"]])
        lz = np.arange(ankle - 0.03, crotch + 0.16, 0.006)
        cxy = np.stack([np.interp(lz, lg[:, 2], lg[:, 0]), np.interp(lz, lg[:, 2], lg[:, 1])], axis=1)
        nl = 48
        lt = np.linspace(0.0, 2 * np.pi, nl, endpoint=False)
        ld = np.stack([np.cos(lt), -np.sin(lt), np.zeros(nl)], axis=1)
        RL = np.full((len(lz), nl), np.nan)
        RS = np.zeros((len(lz), nl))
        for i, z in enumerate(lz):
            for _ in range(2):
                o = (cxy[i, 0], cxy[i, 1], z)
                r = np.array([cast(bvh_left, o, ld[j], 0.2) for j in range(nl)])
                if np.isnan(r).any() or z > crotch - 0.01:
                    break
                pts = cxy[i] + r[:, None] * ld[:, :2]
                cxy[i] = 0.5 * (pts.min(0) + pts.max(0))
            RL[i] = r
            if bvh_shoes is not None:
                for j in range(nl):
                    far = np.array(o) + ld[j] * 0.3
                    d = cast(bvh_shoes, far, -ld[j], 0.3)
                    if not np.isnan(d):
                        RS[i, j] = 0.3 - d
        cxy[:, 0], cxy[:, 1] = _blur(cxy[:, 0], 1.5), _blur(cxy[:, 1], 1.5)
        # the inner side stops at the body's centre line above the crotch (one leg's block, not the pelvis)
        inner = np.where(ld[:, 0] < -1e-3, (cxy[:, :1] - 0.004) / np.maximum(-ld[:, 0], 1e-3)[None], np.inf)
        RL = np.where(np.isnan(RL), np.where(np.isfinite(inner), inner, np.nan), RL)
        RL = _fill_rows(RL)
        RL = np.where((lz > crotch - 0.03)[:, None], np.minimum(RL, inner), RL)
        self.shoe_top = float(lz[RS.max(1) > 0].max()) if (RS > 0).any() else ankle
        RSh = np.maximum(RL, RS)

        def tidy(a):
            a = np.maximum(a, _blur(np.maximum(a, _blur(a, (1.5, 1.2), wrap=(1,))), (0.7, 0.7), wrap=(1,)))
            return np.where((lz > crotch - 0.03)[:, None], np.minimum(a, inner), a)
        self.leg = _Table(lz, tidy(RL))
        self.leg_shod = _Table(lz, tidy(RSh))
        self._lz, self._lcx, self._lcy = lz, cxy[:, 0], cxy[:, 1]
        self._lt = lt
        if log:
            log(f"  wardrobe: body crotch {crotch:.3f} waist {waist:.3f} shoulder line {z_sl:.3f} neck base "
                f"{z_nb:.3f} (r {self.neck_r:.3f}), arm free from x {self.x_free:.3f}, shoe top {self.shoe_top:.3f}")

    # ------------------------------------------------------------------ design space <-> model
    def zv(self, z):
        return np.interp(z, self._zc, self._zv)

    def zc(self, z):
        return np.interp(z, self._zv, self._zc)

    def xv(self, x):
        return np.interp(x, self._xc, self._xv)

    def to_model(self, p, arm=False):
        """Design-space points (K, 3) -> model space. arm: points of a part built along the arm."""
        p = np.array(p, np.float64).reshape(-1, 3)
        if arm:
            x = self.xv(np.abs(p[:, 0]))
            return np.column_stack([np.sign(p[:, 0]) * x, p[:, 1] + np.interp(x, self._ax, self._acy),
                                    p[:, 2] - S.SHOULDER + np.interp(x, self._ax, self._acz)])
        return np.column_stack([p[:, 0], p[:, 1], self.zv(p[:, 2])])

    # ------------------------------------------------------------------ sections (the atelier Body interface)
    def centre_y(self, z):
        return float(np.interp(self.zv(z), self._tz, self._cy))

    def neck_c(self, z):
        return self.centre_y(z)

    def torso_ring(self, z, ease=0.0, n=40, theta=None, front=0.0, back=0.0):
        th = np.linspace(0.0, 2 * np.pi, n, endpoint=False) if theta is None else np.asarray(theta, np.float64)
        z = np.asarray(z, np.float64)
        zb, th = np.broadcast_arrays(z, th)
        zm = self.zv(zb)
        c, s = np.cos(th), np.sin(th)
        # (the atelier widens a top's neckline above the shoulder line; here the neck base is right there)
        ease = ease - 0.6 * np.maximum(zb - 1.375, 0.0)
        r = self.torso(zm, th) + ease + front * np.maximum(c, 0.0) + back * np.maximum(-c, 0.0)
        cy = np.interp(zm, self._tz, self._cy)
        return np.stack([r * s, cy - r * c, zb], axis=-1)

    def torso_dims(self, z):
        z = np.asarray(z, np.float64)
        zm = self.zv(z)
        cy = np.interp(zm, self._tz, self._cy)
        return (self.torso(zm, np.pi / 2), self.torso(zm, 0.0) - cy, self.torso(zm, np.pi) + cy)

    def front_y(self, z, x=0.0):
        th = np.linspace(-1.3, 1.3, 81)
        ring = self.torso_ring(float(z), theta=th)
        return float(np.interp(x, ring[:, 0], ring[:, 1]))

    def side_x(self, z):
        return float(self.torso(self.zv(z), np.pi / 2))

    def arm_ring(self, x, ease=0.0, n=14, side=1.0, squash=1.0):
        x = abs(float(x))
        cap = min(1.0, max(0.0, (x - 0.085) / 0.090)) ** 0.5                 # rounded cap inside the shoulder
        n = max(n, 18)
        t = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
        # at the shoulder a sleeve has the ease of its garment's body (the atelier cuts sleeves 0.72 closer)
        ease = ease * (1.0 + 0.39 * (1.0 - float(_smooth((x - S.SHOULDER_X) / 0.08))))
        r = (self.arm(self.xv(x), t) / math.cos(math.pi / n) + ease) * max(cap, 0.12)   # chords clear the arm
        drop = 0.026 * (1.0 - float(_smooth((x - 0.10) / 0.075)))             # the shoulder slopes below the joint
        return np.stack([np.full(n, side * x), -np.cos(t) * r, S.SHOULDER - drop + np.sin(t) * r * squash], axis=1)

    def leg_ring(self, z, ease=0.0, n=16, side=1.0, wide=1.0):
        zm = float(self.zv(z))
        n = max(n, 24)
        t = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
        tab = self.leg_shod if self.over_shoes else self.leg
        r = tab(zm, t) / math.cos(math.pi / n) + ease
        cx, cy = float(np.interp(zm, self._lz, self._lcx)), float(np.interp(zm, self._lz, self._lcy))
        x = cx + np.cos(t) * r * wide
        if zm > self.crotch - 0.03:
            x = np.maximum(x, 0.003)
        return np.stack([side * x, cy - np.sin(t) * r, np.full(n, float(z))], axis=1)

    def hand(self, *a, **k):
        raise NotImplementedError("wardrobe: full gloves are not available on a VRoid body (fingerless only)")

    # ------------------------------------------------------------------ skin weights
    def nearest(self, P):
        """Closest skin point of each P (K, 3): (points, distance, triangle index)."""
        from mathutils import Vector
        loc = np.empty((len(P), 3))
        idx = np.zeros(len(P), int)
        for i, p in enumerate(P):
            hit = self.bvh.find_nearest(Vector(p))
            loc[i] = hit[0]
            idx[i] = hit[2]
        return loc, np.linalg.norm(loc - P, axis=1), idx

    def weights_at(self, loc, idx):
        """Skin weights (K, G) at surface points `loc` on triangles `idx` (barycentric)."""
        t = self.tris[idx]
        a, b, c = self.co[t[:, 0]], self.co[t[:, 1]], self.co[t[:, 2]]
        v0, v1, v2 = b - a, c - a, loc - a
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
        d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = np.maximum(d00 * d11 - d01 * d01, 1e-18)
        v = np.clip((d11 * d20 - d01 * d21) / den, 0.0, 1.0)
        w = np.clip((d00 * d21 - d01 * d20) / den, 0.0, 1.0)
        u = np.clip(1.0 - v - w, 0.0, 1.0)
        return u[:, None] * self.W[t[:, 0]] + v[:, None] * self.W[t[:, 1]] + w[:, None] * self.W[t[:, 2]]


# --------------------------------------------------------------------------- hem spring bones
def cloth_bone_specs(arm, rig, prefix):
    """The hem chain ring of outfit.cloth_bones (same rest pose: body landmarks only, so every member built
    on one base model shares it) as atelier.build.ensure_bones specs."""
    from .outfit import CLOTH_CHAINS, CLOTH_SEG
    rx, ry = abs(rig.h["thigh_l"].x) + 0.075, 0.115
    z0, cy = rig.crotch + 0.05, rig.neck_c.y
    out = []
    for k in range(CLOTH_CHAINS):
        a = 2 * math.pi * k / CLOTH_CHAINS
        d = np.array([math.sin(a), -math.cos(a), 0.0])
        parent = ("thigh_l" if d[0] > 0 else "thigh_r") if abs(math.sin(a)) > 0.38 else "pelvis"
        p = np.array([d[0] * rx, cy + d[1] * ry, z0])
        for j in range(1, 4):
            seg = CLOTH_SEG if j < 3 else 0.03
            q = p + np.array([0.0, 0.0, -seg]) + d * (0.025 if j < 3 else 0.005)
            name = f"{prefix}_{k:02d}_{j}"
            out.append((name, parent, tuple(p), tuple(q), j < 3))
            parent, p = name, q
    return out


# --------------------------------------------------------------------------- skinning / hiding
def _skin_part(body, part):
    """Give a part (model space) the weights of the skin under it; hanging cloth keeps its hem chains."""
    chains = {b: w for b, w in part.w.items() if b.startswith(CHAIN_PREFIXES)}
    share = sum(chains.values()) if chains else np.zeros(len(part.v))
    if part.name.startswith(RIGID_PARTS):
        c = part.v.mean(0)[None]
        loc, _, idx = body.nearest(c)
        Wp = np.repeat(body.weights_at(loc, idx), len(part.v), axis=0)
    else:
        loc, _, idx = body.nearest(part.v)
        Wp = body.weights_at(loc, idx).astype(np.float64)
        # soften the jumps of "nearest" (armpits, crotch) along the part's own surface
        key = np.round(part.v / 1e-5).astype(np.int64)
        _, inv = np.unique(key, axis=0, return_inverse=True)
        inv = inv.ravel()
        e = set()
        for f in part.f:
            for a, b in zip(f, f[1:] + f[:1]):
                a, b = int(inv[a]), int(inv[b])
                if a != b:
                    e.add((min(a, b), max(a, b)))
        if e:
            e = np.array(sorted(e))
            m = inv.max() + 1
            Wm = np.zeros((m, Wp.shape[1]))
            cnt = np.zeros(m)
            np.add.at(Wm, inv, Wp)
            np.add.at(cnt, inv, 1.0)
            Wm /= cnt[:, None]
            for _ in range(3):
                acc = np.zeros_like(Wm)
                deg = np.zeros(m)
                np.add.at(acc, e[:, 0], Wm[e[:, 1]])
                np.add.at(acc, e[:, 1], Wm[e[:, 0]])
                np.add.at(deg, e[:, 0], 1.0)
                np.add.at(deg, e[:, 1], 1.0)
                Wm = 0.5 * Wm + 0.5 * acc / np.maximum(deg, 1.0)[:, None]
            Wp = Wm[inv]
    names = body.gnames
    if chains:
        # hanging cloth: mostly the pelvis; the thigh under it only takes a share (none on the centre line)
        legs = [i for i, g in enumerate(names) if g.startswith(LEG_BONES)]
        pel = names.index("pelvis")
        coat = any(b.startswith("coattail_") for b in chains) and part.name == "top"
        long_top = part.name == "top"            # coats and dresses lie on the thighs; skirts stand off them
        if coat:
            # an open coat's panels ride the thigh under them (their side chains do too); the front centre
            # chain hangs from the pelvis and would hold the panel back while the leg swings through it
            for j in (1, 2):
                c0 = chains.pop(f"coattail_00_{j}", None)
                if c0 is not None:
                    for name, m in ((f"coattail_01_{j}", part.v[:, 0] > 0), (f"coattail_07_{j}", part.v[:, 0] <= 0)):
                        chains[name] = chains.get(name, 0.0) + c0 * m
        follow = 1.0 if long_top else THIGH_FOLLOW
        k = _smooth(share / 0.05) * (1.0 - follow * _smooth(np.abs(part.v[:, 0]) / 0.07))
        moved = Wp[:, legs].sum(1) * k
        Wp[:, legs] *= (1.0 - k)[:, None]
        Wp[:, pel] += moved
    # at most four influences
    if Wp.shape[1] > 4:
        cut = np.partition(Wp, -4, axis=1)[:, -4][:, None]
        Wp = np.where(Wp >= cut, Wp, 0.0)
    Wp /= np.maximum(Wp.sum(1, keepdims=True), 1e-9)
    Wp *= (1.0 - share)[:, None]
    part.w = {names[i]: Wp[:, i] for i in range(Wp.shape[1]) if Wp[:, i].max() > 1e-4}
    part.w.update(chains)
    return share


def _bvh_of(parts, fixed_only):
    """BVH over the faces of parts (model space); fixed_only: leave out free-hanging cloth (it swings away)."""
    from mathutils.bvhtree import BVHTree
    V, F, off = [], [], 0
    for p, share in parts:
        for f in p.f:
            if not fixed_only or max(share[i] for i in f) < 0.05:
                F.append(tuple(i + off for i in f))
        V.append(p.v)
        off += len(p.v)
    if not F:
        return None
    return BVHTree.FromPolygons(np.concatenate(V).tolist(), F)


def _covered(tree, P, D, reach=COVER_REACH):
    from mathutils import Vector
    out = np.zeros(len(P), bool)
    if tree is None:
        return out
    for i in range(len(P)):
        out[i] = tree.ray_cast(Vector(P[i] - D[i] * 0.004), Vector(D[i]), reach)[0] is not None
    return out


def _keep_near_visible(P, covered, margin=SKIN_MARGIN):
    """Covered points close to a visible one stay (the cloth above them moves)."""
    from scipy.spatial import cKDTree
    if covered.all() or not covered.any():
        return covered
    d, _ = cKDTree(P[~covered]).query(P, distance_upper_bound=margin)
    return covered & ~np.isfinite(d)


def hide_layers(body, parts, shares, log=print):
    """Drop the faces of every part that a later (outer) part covers."""
    big = [i for i, p in enumerate(parts) if len(p.v) >= 150 and not p.name.startswith(RIGID_PARTS)]
    gone = 0
    for n, i in enumerate(big):
        later = [(parts[j], shares[j]) for j in big[n + 1:]]
        if not later:
            continue
        p = parts[i]
        loc, dist, _ = body.nearest(p.v)
        d = p.v - loc
        d /= np.maximum(dist, 1e-6)[:, None]
        hid = _covered(_bvh_of(later, True), p.v, d) & (shares[i] < 0.05)
        hid = _keep_near_visible(p.v, hid)
        if not hid.any():
            continue
        keep = [k for k, f in enumerate(p.f) if not all(hid[v] for v in f)]
        gone += len(p.f) - len(keep)
        p.f = [p.f[k] for k in keep]
        if p.face_mat is not None:
            p.face_mat = [p.face_mat[k] for k in keep]
    if gone:
        log(f"  wardrobe: {gone} hidden faces of inner layers removed")


def _delete_faces(me, pick):
    """Delete the faces pick(bmesh face) accepts (and the vertices only they used)."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if pick(f)], context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    me.update()


def covered_skin(body_obj, body, parts, shares, log=print):
    """Delete the base model's own tops / bottoms now; returns the rest-pose centres of the skin faces the
    garments cover, for strip_skin() - which runs after the materials are made: the body texture is shared
    by every look on the base model and is repainted from the whole skin (outfit.fix_skin)."""
    from .models import role_of
    me = body_obj.data
    roles = [role_of(s.material.name if s.material else "") for s in body_obj.material_slots]
    tree = _bvh_of(list(zip(parts, shares)), True)
    polys = me.polygons
    cen = np.array([polys[f].center[:] for f in body.skin_faces])
    nrm = np.array([polys[f].normal[:] for f in body.skin_faces])
    hid = _covered(tree, cen, nrm)
    # hands, head and feet always stay
    hid &= (np.abs(cen[:, 0]) < float(body.h["hand_l"][0]) - 0.02) & (cen[:, 2] < body.z_nb + 0.01)
    hid &= cen[:, 2] > float(body.h["foot_l"][2]) + 0.02
    hid = _keep_near_visible(cen, hid)
    gone = {i for i, r in enumerate(roles) if r in ("tops", "bottoms")}
    _delete_faces(me, lambda f: f.material_index in gone)
    log(f"  wardrobe: base outfit removed, {int(hid.sum())} of {len(hid)} skin faces are under the clothes")
    return cen[hid]


def strip_skin(body_obj, centres):
    """Delete the skin faces covered_skin() found (matched by their rest-pose centres)."""
    if not len(centres):
        return
    from scipy.spatial import cKDTree
    tree = cKDTree(np.asarray(centres))
    _delete_faces(body_obj.data, lambda f: tree.query(np.array(f.calc_center_median()))[0] < 2e-5)


# --------------------------------------------------------------------------- build
def material_names(key, entry):
    tint = "jacket" in entry.get("tint", ())
    return dict(cloth=f"M_Anime_{key}_Cloth", tint=f"M_Anime_{key}_JacketTint" if tint else None)


def build(arm, meshes, body_obj, rig, entry, key, log=print):
    """Dress a loaded base model in entry["wear"]. Returns (garment object - also appended to `meshes` -,
    {names of the materials it registered}, centres of the covered skin faces for strip_skin())."""
    from .atelier import build as AB
    from .atelier import mesh as AM
    from .atelier import outfit as OF
    from .build import preview_material
    female = bool(entry.get("body", {}).get("female", entry.get("female")))
    body = VBody(arm, body_obj, rig, female, log)
    mats = material_names(key, entry)

    class Kit(OF.Kit):
        def add(self, part, color, slot="cloth", cells=(1, 1), **style):
            part.arm_space = part.name.startswith(ARM_PARTS)
            return super().add(part, color, slot, cells, **style)

    kit = Kit(body, key, mats)
    for kind, params in entry["wear"]:
        if kind == "shoes":                      # the base model's shoes stay (colors["shoes"])
            continue
        params = dict(params)
        if kind == "gloves":
            params["fingerless"] = True
        if kind == "legwear":                    # socks end inside the base model's shoes
            params.setdefault("bottom", float(body.zc(min(body.shoe_top, float(body.h["foot_l"][2]) + 0.03))) - 0.02)
        body.over_shoes = kind == "pants"
        body.torso = body.torso_closed if kind in ("pants", "skirt") else body.torso_open
        OF.GARMENTS[kind](kit, **params)
    body.over_shoes = False
    parts = [p for p in kit.parts if len(p.v)]
    specs = kit.save(C.OUT_TEXTURES, f"{TEX_REL}/{key}")
    for name, spec in specs.items():
        spec["cel"] = "cloth"
        spec["fill"] = 0.45
    palette.register(specs)
    bones = []
    for prefix in sorted(kit.cloth_prefixes):
        bones += cloth_bone_specs(arm, rig, prefix)
    AB.ensure_bones(arm, bones)
    for p in parts:
        if p.name.startswith("sleeve"):          # no ink line round the sleeve head inside the shoulder
            p.outline = np.where(np.abs(p.v[:, 0]) < S.SHOULDER_X + 0.01, 0.0, p.outline)
        p.v = body.to_model(p.v, arm=p.arm_space)
        p.round_c = body.to_model(p.round_c, arm=p.arm_space)[0]
    shares = [_skin_part(body, p) for p in parts]
    hidden = covered_skin(body_obj, body, parts, shares, log)
    hide_layers(body, parts, shares, log)
    parts = [p for p in parts if p.f]
    line = entry.get("outline", 0.0022) * 1.15
    obj = AM.assemble(OBJECT_NAME, parts, arm, preview_material, outline=line, log=None)
    meshes.append(obj)
    log(f"  wardrobe: {key}: {len(parts)} parts, {sum(p.tris() for p in parts)} tris, "
        f"hem chains {sorted(kit.cloth_prefixes) or '-'}")
    return obj, set(specs) | {AM.OUTLINE_MAT}, hidden
