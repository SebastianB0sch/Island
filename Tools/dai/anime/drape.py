"""
Cloth drape for the tailored uniforms (outfit.py).

A garment starts life as a copy of the skin it covers pushed out along the normal, so on its own it is a
body-paint shell: every muscle, the chest, the navel and the crotch show through the fabric and the sleeves
are skin tight. This pass turns those shells into clothes, the way a garment would hang in the rest pose:

  * torso   - in every direction round the body the fabric falls from the widest point above it (chest,
              shoulder blades, seat) and only comes back in slowly (`taper`), so hollows (waist, small of the
              back, between the breasts, under the seat) are bridged instead of followed
  * sleeves - round tubes round the arm axis, as wide as the widest part of the arm near them plus an ease
              that grows towards the cuff
  * legs    - straight trouser legs: round tubes that run from the thigh down to the hem width; the two legs
              never cross the mid plane
  * smooth  - a few Taubin (shrink-free) smoothing steps take out the remaining anatomy
  * collide - nothing ends up inside the body or the garments already draped underneath it (KD tree on the
              layer below, pushed out along its normal)
  * rims    - open edges (hem, cuffs, front opening) get a turned-in band, so the fabric has visible
              thickness instead of ending as a zero-width sheet

Everything is computed from vertex *positions*: the VRoid body splits its vertices along UV seams, so all
copies of a position are moved together and the garment cannot crack open along a seam.

The pass only ever moves a vertex outwards from where tailoring put it (plus smoothing), so bone weights
copied from the skin stay valid: a sleeve vertex is still weighted to the arm it surrounds.

fold_mask() paints anime crease lines (elbows, armpits, knees, crotch, hem stacking) into the garment
textures; outfit.paint() calls it.
"""

import math

import bmesh
import numpy as np
from mathutils import Vector
from scipy import ndimage
from scipy.spatial import cKDTree


# --------------------------------------------------------------------------- welded vertex groups
class Welded:
    """Unique positions of a set of BMVerts (UV-seam copies collapsed) with their 1-ring adjacency."""

    def __init__(self, verts, faces):
        self.verts = list(verts)
        co = np.array([v.co[:] for v in self.verts], np.float64)
        key = np.round(co / 1e-5).astype(np.int64)
        _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        self.inv = inv.ravel()
        self.co = co[first].copy()
        index = {v: i for i, v in enumerate(self.verts)}
        n = len(self.co)
        pairs = set()
        count = {}
        for f in faces:
            ids = [self.inv[index[v]] for v in f.verts if v in index]
            for a, b in zip(ids, ids[1:] + ids[:1]):
                if a != b:
                    e = (min(a, b), max(a, b))
                    pairs.add(e)
                    count[e] = count.get(e, 0) + 1
        self.nbr = [[] for _ in range(n)]
        for a, b in pairs:
            self.nbr[a].append(b)
            self.nbr[b].append(a)
        # open edges after welding (hem, cuffs, front opening, cut lines)
        self.open_edges = [e for e, c in count.items() if c == 1]
        self.boundary = np.zeros(n, bool)
        self.bnbr = [[] for _ in range(n)]          # neighbours along the open edges only
        for a, b in self.open_edges:
            self.boundary[a] = self.boundary[b] = True
            self.bnbr[a].append(b)
            self.bnbr[b].append(a)

    def write(self):
        for v, i in zip(self.verts, self.inv):
            v.co = Vector(self.co[i])

    def normals(self, faces):
        """Area-weighted vertex normals of the welded surface."""
        index = {v: i for i, v in enumerate(self.verts)}
        acc = np.zeros_like(self.co)
        for f in faces:
            ids = [self.inv[index[v]] for v in f.verts if v in index]
            if len(ids) < 3:
                continue
            p = self.co[ids]
            nrm = np.zeros(3)
            for k in range(1, len(ids) - 1):
                nrm += np.cross(p[k] - p[0], p[k + 1] - p[0])
            for i in ids:
                acc[i] += nrm
        ln = np.linalg.norm(acc, axis=1, keepdims=True)
        return acc / np.maximum(ln, 1e-12)


def _taubin(w, mask, steps=4, lam=0.5, mu=-0.53):
    """Shrink-free smoothing of the welded positions where mask is True. Open-edge vertices are smoothed
    along their edge only (a 1D smoothing of the hem / cuff / front line), so the edge stays a clean curve
    and does not get dragged into the surface."""
    idx = np.nonzero(mask)[0]
    if not len(idx):
        return
    nb = [w.bnbr[i] if w.boundary[i] else w.nbr[i] for i in idx]
    for _ in range(steps):
        for k in (lam, mu):
            new = w.co.copy()
            for j, i in enumerate(idx):
                if nb[j]:
                    new[i] = w.co[i] + k * (w.co[nb[j]].mean(0) - w.co[i])
            w.co = new


# --------------------------------------------------------------------------- limb axes
def _project(p, axis):
    """Closest point of every row of p on the polyline `axis` (Nx3): (point, arc length, total length)."""
    best_d = np.full(len(p), np.inf)
    best_pt = np.zeros_like(p)
    best_s = np.zeros(len(p))
    s0 = 0.0
    for a, b in zip(axis[:-1], axis[1:]):
        d = b - a
        L2 = float(d @ d)
        t = np.clip(((p - a) @ d) / max(L2, 1e-12), 0.0, 1.0)
        q = a + t[:, None] * d
        dist = np.linalg.norm(p - q, axis=1)
        better = dist < best_d
        best_d[better], best_pt[better], best_s[better] = dist[better], q[better], s0 + t[better] * math.sqrt(L2)
        s0 += math.sqrt(L2)
    return best_pt, best_s, s0


def _frame(axis):
    """Two unit vectors perpendicular to the limb's main direction (for an angle round the limb)."""
    d = axis[-1] - axis[0]
    d /= np.linalg.norm(d)
    up = np.array((0.0, 0.0, 1.0)) if abs(d[2]) < 0.8 else np.array((0.0, -1.0, 0.0))
    u = np.cross(d, up)
    u /= np.linalg.norm(u)
    v = np.cross(d, u)
    return d, u, v


def _tube(co, axis, sel, ease, roundness, taper_to=None, x_sign=0, fade=0.0):
    """Make the selected rows of co a round tube round `axis`.

    ease(s01) -> metres of room added, roundness 0..1 (1: perfect circle of the slice's widest radius),
    taper_to: (start s01, end radius) for straight trouser legs (the radius runs linearly from the widest
    thigh radius at start to end radius at the hem). x_sign: keep the tube on that side of x = 0."""
    p = co[sel]
    if not len(p):
        return
    q, s, total = _project(p, axis)
    s01 = s / max(total, 1e-6)
    rad = p - q
    r = np.linalg.norm(rad, axis=1)
    dirs = rad / np.maximum(r[:, None], 1e-9)
    # widest radius per 1 cm slice, then a running max over a few cm (no elbow / knee bumps)
    nb = max(2, int(total / 0.01) + 1)
    sb = np.clip((s / total * (nb - 1)).round().astype(int), 0, nb - 1)
    prof = np.zeros(nb)
    np.maximum.at(prof, sb, r)
    for i in range(1, nb):                     # fill empty slices from their neighbours
        if prof[i] == 0:
            prof[i] = prof[i - 1]
    prof = ndimage.maximum_filter1d(prof, size=7, mode="nearest")
    prof = ndimage.gaussian_filter1d(prof, 2.0, mode="nearest")
    target = prof[sb]
    if taper_to is not None:
        # straight trouser leg: from the widest thigh radius down to the hem width, never inside the leg
        start, end_r = taper_to
        top = float(prof[: max(1, int(nb * (start + 0.08)))].max())
        k = np.clip((s01 - start) / max(1e-6, 1 - start), 0, 1)
        straight = top + (max(end_r, 0.0) - top) * k
        target = np.where(s01 > start, np.maximum(straight, target), target)
    # fade: over the first `fade` metres of the limb the tube blends in from the torso drape (no gap opens
    # between the trouser legs at the crotch / under the arm)
    k = np.clip(s / fade, 0, 1) ** 2 if fade > 0 else 1.0
    want = r + (target - r) * roundness * k
    want = np.maximum(want, r) + ease(s01) * k
    new = q + dirs * want[:, None]
    if x_sign:
        new[:, 0] = np.where(new[:, 0] * x_sign < 0.004, x_sign * 0.004, new[:, 0])
    co[sel] = new


def _hull_radius(pts2, center, angles):
    """Distance from center to the convex hull of the 2D points along each angle (0 where the ray misses)."""
    from scipy.spatial import ConvexHull, QhullError
    out = np.zeros(len(angles))
    if len(pts2) < 4:
        return out
    try:
        hull = ConvexHull(pts2)
    except (QhullError, ValueError):
        return out
    poly = pts2[hull.vertices] - center
    a, b = poly, np.roll(poly, -1, axis=0)
    for k, phi in enumerate(angles):
        d = np.array((math.sin(phi), -math.cos(phi)))        # same angle convention as _torso
        # ray center + t d against every edge a + u (b - a)
        e = b - a
        den = d[0] * e[:, 1] - d[1] * e[:, 0]
        ok = np.abs(den) > 1e-12
        t = np.where(ok, (a[:, 0] * e[:, 1] - a[:, 1] * e[:, 0]) / np.where(ok, den, 1), -1)
        u = np.where(ok, (a[:, 0] * d[1] - a[:, 1] * d[0]) / np.where(ok, den, 1), -1)
        hit = ok & (t > 0) & (u >= -1e-9) & (u <= 1 + 1e-9)
        if hit.any():
            out[k] = t[hit].max()
    return out


def _torso(co, sel, axis_y, z_top, taper=0.28, ease=0.004, bins=48, under=None, hull=True, trunk=None):
    """Hang the selected rows of co from their widest point above, per direction round the torso; with hull,
    every horizontal slice is also pushed out to the convex hull of itself and the layer below (`under`), so
    the fabric spans hollows instead of following them (between the legs, the chest, the small of the back)."""
    p = co[sel]
    if not len(p):
        return
    cy = axis_y(p[:, 2])
    dx, dy = p[:, 0], p[:, 1] - cy
    r = np.hypot(dx, dy)
    phi = np.arctan2(dx, -dy)
    pb = np.round((phi + math.pi) / (2 * math.pi) * bins).astype(int) % bins
    z_lo = float(p[:, 2].min())
    nz = int((z_top - z_lo) / 0.01) + 2
    zb = np.clip(((z_top - p[:, 2]) / 0.01).round().astype(int), 0, nz - 1)
    R = np.zeros((bins, nz))
    np.maximum.at(R, (pb, zb), r)
    if hull:
        angles = np.arange(bins) / bins * 2 * math.pi - math.pi
        src = p if under is None or not len(under) else np.vstack([p, under])
        if trunk is not None:                 # (z above which, |x| limit): keep the arm roots out of the hull
            zt, xt = trunk
            src = src[(src[:, 2] <= zt) | (np.abs(src[:, 0]) < xt)]
        for j in range(nz):
            z = z_top - j * 0.01
            sl = src[np.abs(src[:, 2] - z) < 0.006]
            if len(sl) < 4:
                continue
            c = np.array((0.0, float(axis_y(np.array([z]))[0])))
            hr = _hull_radius(sl[:, :2], c, angles)
            R[:, j] = np.maximum(R[:, j], hr)
    # empty cells (no vertex there): carry the cell above down
    D = np.zeros_like(R)
    for j in range(nz):
        above = D[:, j - 1] - taper * 0.01 if j else np.zeros(bins)
        D[:, j] = np.maximum(R[:, j], above)
    # smooth round the body and down it (wrap round)
    D = ndimage.gaussian_filter(D, sigma=(1.2, 1.0), mode=("wrap", "nearest"))
    D = np.maximum(D, ndimage.gaussian_filter(R, sigma=(0.8, 0.6), mode=("wrap", "nearest")))
    want = np.maximum(r, D[pb, zb]) + ease
    k = want / np.maximum(r, 1e-6)
    out = p.copy()
    out[:, 0] = dx * k
    out[:, 1] = cy + dy * k
    co[sel] = out


def _collide(co, normals, under_pts, under_nrm, clear):
    """Push rows of co out of the layer below (points + outward normals) to keep `clear` metres of room."""
    if under_pts is None or not len(under_pts):
        return
    tree = cKDTree(under_pts)
    for _ in range(3):
        d, i = tree.query(co, k=4)
        moved = False
        for kk in range(4):
            p, n = under_pts[i[:, kk]], under_nrm[i[:, kk]]
            depth = np.einsum("ij,ij->i", co - p, n)
            near = d[:, kk] < 0.04
            push = np.where(near & (depth < clear), clear - depth, 0.0)
            if push.any():
                co += n * push[:, None]
                moved = True
        if not moved:
            break


# --------------------------------------------------------------------------- the pass
ARM_REACH = 0.085          # sleeve vertices lie within this distance of the arm's bone axis (m)


class Drape:
    """Owned by a outfit.Tailor: remembers the draped layers so each new one collides with the ones below."""

    def __init__(self, tailor):
        self.t = tailor
        r = tailor.rig
        skin_v = list({v for f in tailor.skin if f.is_valid for v in f.verts})
        self.layer_pts = np.array([v.co[:] for v in skin_v], np.float64)
        self.layer_nrm = np.array([tailor.N.get(v, v.normal)[:] for v in skin_v], np.float64)
        h = r.h
        self.arm_axis = {s: np.array([h[f"upperarm_{s}"][:], h[f"lowerarm_{s}"][:], h[f"hand_{s}"][:]])
                         for s in ("l", "r")}
        self.leg_axis = {s: np.array([p[:] for p in r.leg(s)]) for s in ("l", "r")}
        # torso centre line (front/back middle) per height, from the skin
        sk = self.layer_pts[np.abs(self.layer_pts[:, 0]) < r.shoulder_x]
        zs = np.arange(r.crotch - 0.05, r.neck + 0.05, 0.01)
        cy = []
        for z in zs:
            ring = sk[np.abs(sk[:, 2] - z) < 0.008]
            cy.append(0.5 * (ring[:, 1].min() + ring[:, 1].max()) if len(ring) else np.nan)
        cy = np.array(cy)
        ok = ~np.isnan(cy)
        self._zs, self._cy = zs[ok], cy[ok]

    def axis_y(self, z):
        return np.interp(z, self._zs, self._cy)

    def garment(self, name, sleeves=True, legs=False, torso_top=None, taper=0.28, ease=0.004, clear=0.006,
                hem_width=None, roundness=0.75, smooth=4, sleeve_ease=(0.006, 0.016), hull=True):
        t, r = self.t, self.t.rig
        faces = [f for f in t.faces_of(name)]
        if not faces:
            return
        verts = list({v for f in faces for v in f.verts})
        w = Welded(verts, faces)
        co = w.co
        ax = np.abs(co[:, 0])
        arm = (ax > r.shoulder_x + 0.025) & (co[:, 2] > r.shoulder_z - 0.16)
        # a sleeve vertex also has to lie round the arm: flank / belly vertices out at the armpit (Chumley's
        # widened trunk) stay torso, or the sleeve tube would inflate them into shoulder wings
        for s_, sg in (("l", 1), ("r", -1)):
            side = arm & (co[:, 0] * sg > 0)
            if side.any():
                q, _, _ = _project(co[side], self.arm_axis[s_])
                near = np.linalg.norm(co[side] - q, axis=1) < ARM_REACH
                idx = np.nonzero(side)[0]
                arm[idx[~near]] = False
        leg = (co[:, 2] < r.crotch - 0.01) & ~arm if legs else np.zeros(len(co), bool)
        top = torso_top if torso_top is not None else r.neck - 0.035
        torso = ~arm & ~leg & (co[:, 2] < top)
        lp = self.layer_pts
        # under the T-pose's level arms the slices would reach out along the arm and the hull would flare the
        # jacket sides into wings once the arms hang down: near the armpits only the trunk counts
        armpit = lp[:, 2] > r.shoulder_z - 0.2
        under = lp[(np.abs(lp[:, 0]) < np.where(armpit, r.shoulder_x - 0.035, r.shoulder_x + 0.01)) &
                   (lp[:, 2] < top) & (lp[:, 2] > co[:, 2].min() - 0.01)]
        self._hull_x = (r.shoulder_z - 0.2, r.shoulder_x - 0.035)
        _torso(co, torso, self.axis_y, top, taper=taper, ease=ease, under=under, hull=hull, trunk=self._hull_x)
        if sleeves:
            for s, sg in (("l", 1), ("r", -1)):
                sel = arm & (co[:, 0] * sg > 0)
                e0, e1 = sleeve_ease
                _tube(co, self.arm_axis[s], sel, lambda s01, e0=e0, e1=e1: e0 + (e1 - e0) * s01 ** 1.5, roundness)
        if legs:
            for s, sg in (("l", 1), ("r", -1)):
                sel = leg & (co[:, 0] * sg > 0)
                axis = self.leg_axis[s]
                total = float(np.linalg.norm(np.diff(axis, axis=0), axis=1).sum())
                start = max(0.0, (axis[0][2] - (r.crotch - 0.02)) / total)
                _tube(co, axis, sel, lambda s01: 0.004 + 0.004 * s01, roundness,
                      taper_to=(start, hem_width) if hem_width else None, x_sign=sg,
                      fade=max(0.0, axis[0][2] - (r.crotch - 0.01)) + 0.10)
        # blend the torso / limb seams and take out the remaining anatomy (boundary rows stay on their cuts)
        movable = co[:, 2] < top + 0.01
        z_edge = co[w.boundary, 2].copy()
        _taubin(w, movable, steps=smooth)
        co = w.co
        # open edges keep their height: hems / cuts stay exactly on their cut planes (outfit.extend hangs the
        # free part of a garment from the edges found there)
        co[w.boundary, 2] = z_edge
        # the torso already clears the convex hull of the layer below (re-checked after smoothing); a point /
        # normal collision test misreads concave layers (between the legs), so only the limbs use it
        _torso(co, torso, self.axis_y, top, taper=taper, ease=ease * 0.5, under=under, hull=hull, trunk=self._hull_x)
        limbs = ~torso
        if limbs.any():
            sub = co[limbs]
            _collide(sub, None, self.layer_pts, self.layer_nrm, clear)
            co[limbs] = sub
        w.co = co
        w.write()
        # this garment is the layer the next one drapes over
        self.layer_pts = np.vstack([self.layer_pts, co])
        self.layer_nrm = np.vstack([self.layer_nrm, w.normals(faces)])
        return w

    def rims(self, name, depth=0.006, lift=0.0015):
        """Turned-in band along the garment's open edges: visible fabric thickness at hems, cuffs and fronts."""
        t = self.t
        faces = t.faces_of(name)
        if not faces:
            return 0
        verts = list({v for f in faces for v in f.verts})
        w = Welded(verts, faces)
        nrm = w.normals(faces)
        open_keys = {(a, b) for a, b in w.open_edges}
        index = {v: i for i, v in enumerate(w.verts)}
        edges = []
        for f in faces:
            for e in f.edges:
                a, b = (w.inv[index[x]] for x in e.verts)
                if (min(a, b), max(a, b)) in open_keys and e.is_boundary:
                    edges.append(e)
        edges = list(dict.fromkeys(edges))
        if not edges:
            return 0
        ret = bmesh.ops.extrude_edge_only(t.bm, edges=edges)
        nverts = [x for x in ret["geom"] if isinstance(x, bmesh.types.BMVert)]
        nfaces = [x for x in ret["geom"] if isinstance(x, bmesh.types.BMFace)]
        for nv in nverts:
            src = next((e.other_vert(nv) for e in nv.link_edges if e.other_vert(nv) in index), None)
            if src is None:
                continue
            n = nrm[w.inv[index[src]]]
            nv.co = src.co - Vector(n) * depth + Vector((0, 0, lift))
        idx = t.garments[name]["idx"]
        for f in nfaces:
            f.material_index = idx
            f.smooth = True
        return len(nfaces)


# --------------------------------------------------------------------------- crease lines
def _limb_coords(P, axis):
    q, s, total = _project(P, axis)
    d, u, v = _frame(axis)
    rad = P - q
    theta = np.arctan2(rad @ v, rad @ u)
    return s, theta, total, np.linalg.norm(rad, axis=1)


def _lines(dist, width):
    """Anti-aliased ink-ish line strength from a signed distance (metres)."""
    return np.clip(1.0 - np.abs(dist) / width, 0.0, 1.0) ** 0.7


def fold_mask(P, name, rig, spec, legs=True):
    """Strength 0..1 of painted crease lines at the texel rest positions P (Nx3) of garment `name`."""
    m = np.zeros(len(P), np.float32)
    if not len(P):
        return m
    h = rig.h
    W = 0.0022
    ax = np.abs(P[:, 0])
    if name in ("Jacket", "Shirt") and spec.get("sleeves", "long") != "none":
        for s, sg in (("l", 1), ("r", -1)):
            axis = np.array([h[f"upperarm_{s}"][:], h[f"lowerarm_{s}"][:], h[f"hand_{s}"][:]])
            on = (P[:, 0] * sg > rig.shoulder_x + 0.02) & (P[:, 2] > rig.shoulder_z - 0.16)
            if not on.any():
                continue
            s_, th, total, _ = _limb_coords(P[on], axis)
            el = float(np.linalg.norm(axis[1] - axis[0]))
            # three curved creases on the inside of the elbow (front, -Y in the T-pose)
            fr = -(P[on][:, 1] - axis[0][1])
            span = np.clip(fr / 0.05, 0, 1)
            k = np.zeros(on.sum(), np.float32)
            for i, (off, strength) in enumerate(((-0.022, 0.75), (0.0, 1.0), (0.024, 0.75))):
                curve = el + off + 0.012 * np.sin(th * 1.5 + i)
                k = np.maximum(k, _lines(s_ - curve, W) * span * strength)
            # armpit fold running diagonally under the shoulder
            under = np.clip(-(P[on][:, 2] - axis[0][2]) / 0.04, 0, 1)
            k = np.maximum(k, _lines(s_ - 0.035 - 0.25 * (P[on][:, 1] - axis[0][1]), W) * under *
                           (s_ < 0.09))
            # cuff stacking: two short rings a little above the cuff
            near_cuff = s_ / max(total, 1e-6)
            for off in (0.86, 0.9):
                k = np.maximum(k, _lines(near_cuff - off - 0.01 * np.sin(th * 2), W / total) * 0.7 *
                               np.clip(np.cos(th * 1.3), 0, 1))
            m[on] = np.maximum(m[on], k)
    if name == "Jacket":
        # waist pull lines on the sides of the body, above the hem
        side = np.clip((ax - 0.07) / 0.06, 0, 1) * (ax < rig.shoulder_x + 0.02)
        z = P[:, 2]
        for off in (0.03, 0.065):
            curve = rig.waist + off - 0.25 * (ax - 0.1)
            m = np.maximum(m, _lines(z - curve, W) * side * 0.8)
    if name == "Pants" and legs:
        for s, sg in (("l", 1), ("r", -1)):
            axis = np.array([p[:] for p in rig.leg(s)])
            on = (P[:, 0] * sg > 0) & (P[:, 2] < rig.crotch + 0.02)
            if not on.any():
                continue
            s_, th, total, _ = _limb_coords(P[on], axis)
            knee = float(np.linalg.norm(axis[1] - axis[0]))
            back = np.clip((P[on][:, 1] - axis[1][1]) / 0.04, 0, 1)
            fr = np.clip(-(P[on][:, 1] - axis[1][1]) / 0.04, 0, 1)
            k = np.zeros(on.sum(), np.float32)
            for i, off in enumerate((-0.03, -0.005, 0.02)):          # behind the knee
                k = np.maximum(k, _lines(s_ - knee - off - 0.01 * np.sin(th * 2 + i), W) * back)
            # crotch whiskers: diagonal lines on the front of the thigh
            for i, off in enumerate((0.03, 0.06, 0.09)):
                curve = off + 0.5 * (sg * (P[on][:, 0] - axis[0][0]))
                k = np.maximum(k, _lines(s_ - curve, W) * fr * (s_ < 0.16) * 0.85)
            # hem break: the trouser leg stacks on the shoe
            s01 = s_ / max(total, 1e-6)
            for off in (0.9, 0.94):
                k = np.maximum(k, _lines(s01 - off - 0.008 * np.sin(th * 3), W / total) * 0.75)
            m[on] = np.maximum(m[on], k)
    if name == "Skirt":
        # pleat lines: the folds of the pleated skirt
        cy = rig.neck_c.y
        phi = np.arctan2(P[:, 0], -(P[:, 1] - cy))
        n = spec.get("pleats", 16)
        frac = (phi / (2 * math.pi) * n) % 1.0
        below = np.clip((rig.pelvis - P[:, 2]) / 0.04, 0, 1)
        m = np.maximum(m, _lines((frac - 0.5) * 0.05, W) * below)
    return m
