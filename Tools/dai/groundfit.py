"""
Ground fit and spacing for the scattered vegetation, rocks and logs.

* `Footprint` measures a catalog prop once (its real mesh, third-party or procedural): height, crown and
  trunk radii and its *underside* - the points of the mesh near the ground, with their height above its
  lowest point. A boulder's underside rises towards its bulge, a tree's is only its trunk and root flare,
  a fence's runs its whole length.
* `seat()` drops an instance until no point of that underside is above the terrain triangles under it:
  on a slope the downhill edge touches the ground instead of hanging over it, the uphill side is buried.
  Rocks and logs can lean with the slope instead (`tilt`), bedded into it. It also reports how much of the
  instance ended up underground and how far its top stands out, so a rock that would vanish into a bank or
  a tree whose foot spans a step can be skipped. `ue_rotator` turns a lean into Unreal's pitch and roll.
* `Spacing` keeps trunks, boulders and crowns apart: two trunks never grow through each other, crowns
  may interlock but not merge into one, and nothing is scattered into a rock.

Everything works on numpy arrays of candidates; the terrain sampler is `Layout.hf` (the drawn mesh).
"""

import math

import numpy as np

ANGLES = 8        # samples round a trunk for the step check
MAX_POINTS = 36   # contact points kept per footprint


class Footprint:
    """Measured shape of one catalog prop at scale 1 (metres, in its own frame)."""

    def __init__(self, name, verts, trunk=None, reach=None):
        v = np.asarray(verts, np.float64).reshape(-1, 3)
        self.name = name
        z0 = float(v[:, 2].min())
        self.h = float(v[:, 2].max() - z0)
        r = np.hypot(v[:, 0], v[:, 1])
        self.rmax = float(r.max())
        top = v[:, 2] > z0 + 0.4 * self.h
        self.crown = float(np.percentile(r[top], 90)) if top.any() else self.rmax
        foot = v[:, 2] < z0 + min(0.3, 0.15 * self.h)
        self.base = float(np.percentile(r[foot], 90)) if foot.any() else 0.1
        self.trunk = float(trunk) if trunk else self.base
        self.z0 = z0          # pivot to lowest point (a few meshes sit a little below their pivot)
        # the underside: points of the mesh close enough to the ground that a gap under them shows (a crown
        # 3 m up overhangs, it does not float) - per cell of an xy grid, the lowest vertex, as (x, y, height
        # above the lowest point). A fence keeps its length, a bench its four legs, a boulder its base.
        reach = min(0.5 * self.h, 1.2) if reach is None else reach * self.h
        low = v[v[:, 2] - z0 <= reach]
        cell = max(self.rmax / 6.0, 0.05)
        while True:
            key = np.floor(low[:, :2] / cell).astype(np.int64)
            order = np.lexsort((low[:, 2], key[:, 1], key[:, 0]))
            k = key[order]
            first = np.ones(len(order), bool)
            first[1:] = np.any(k[1:] != k[:-1], axis=1)
            pts = low[order[first]]
            if len(pts) <= MAX_POINTS:
                break
            cell *= 1.3
        pts = pts.copy()
        pts[:, 2] -= z0
        self.pts = np.vstack([[0.0, 0.0, 0.0], pts]) if not len(pts) or np.hypot(*pts[:, :2].T).min() > 0.05 else pts


def measure(name, P, reach=None):
    """Footprint of catalog prop `name` from its built mesh (P = dai.assets.props). reach: the fraction of its
    height up to which the underside must touch the ground (default: half of it, at most 1.2 m)."""
    from . import blend
    trunk = None
    if P.is_thirdparty(name):
        from . import thirdparty
        spec = thirdparty.registry()["props"][name]
        if spec.get("collision") == "trunk":
            trunk = spec.get("trunk_radius", 0.3)
        o = P.build_object(name)      # kept: export_all reuses the cached import
        verts = [tuple(o.matrix_world @ x.co) for x in o.data.vertices]
        return Footprint(name, verts, trunk, reach)
    mb, _ = P.get(name)
    o = mb.build(name + "_measure")
    try:
        verts = [tuple(o.matrix_world @ x.co) for x in o.data.vertices]
    finally:
        blend.delete([o])
    return Footprint(name, verts, trunk, reach)


def tilt_matrices(x, y, yaw, hf, radius, tilt, max_tilt):
    """(N, 3, 3) rotations (Blender frame: columns = the local axes in the world): the yaw, then a lean
    of `tilt` times the ground's slope over `radius` (at most `max_tilt` degrees) towards its fall line."""
    r = np.maximum(radius, 0.4)
    gx = (hf(x + r, y) - hf(x - r, y)) / (2 * r)
    gy = (hf(x, y + r) - hf(x, y - r)) / (2 * r)
    g = np.hypot(gx, gy)
    th = np.minimum(np.arctan(g) * tilt, np.radians(max_tilt))
    ax = np.where(g > 1e-9, gy / np.maximum(g, 1e-9), 1.0)      # axis z x n, n = (-gx, -gy, 1)
    ay = np.where(g > 1e-9, -gx / np.maximum(g, 1e-9), 0.0)
    c, s_, C1 = np.cos(th), np.sin(th), 1 - np.cos(th)
    T = np.empty(x.shape + (3, 3))                              # Rodrigues about (ax, ay, 0)
    T[:, 0, 0] = c + ax * ax * C1
    T[:, 0, 1] = ax * ay * C1
    T[:, 0, 2] = ay * s_
    T[:, 1, 0] = ax * ay * C1
    T[:, 1, 1] = c + ay * ay * C1
    T[:, 1, 2] = -ax * s_
    T[:, 2, 0] = -ay * s_
    T[:, 2, 1] = ax * s_
    T[:, 2, 2] = c
    a = np.radians(yaw)
    Z = np.zeros(x.shape + (3, 3))
    Z[:, 0, 0] = Z[:, 1, 1] = np.cos(a)
    Z[:, 0, 1] = -np.sin(a)
    Z[:, 1, 0] = np.sin(a)
    Z[:, 2, 2] = 1.0
    return T @ Z


def ue_rotator(M):
    """(yaw, pitch, roll) in degrees of Unreal's FRotator for Blender-frame rotations M (N, 3, 3).
    Unreal's frame is Blender's with Y mirrored, for the world and for the meshes' own axes alike."""
    F = np.diag([1.0, -1.0, 1.0])
    U = F @ M @ F                                     # columns: the local X, Y, Z axes in Unreal's world
    X, Y, Z = U[:, :, 0], U[:, :, 1], U[:, :, 2]
    pitch = np.arctan2(X[:, 2], np.hypot(X[:, 0], X[:, 1]))
    yaw = np.arctan2(X[:, 1], X[:, 0])
    sy = np.stack([-np.sin(yaw), np.cos(yaw), np.zeros_like(yaw)], 1)   # Y axis of (pitch, yaw, 0)
    roll = np.arctan2((Z * sy).sum(1), (Y * sy).sum(1))
    return np.degrees(yaw), np.degrees(pitch), np.degrees(roll)


def blender_matrix(yaw, pitch, roll):
    """Inverse of ue_rotator for one instance: the Blender-frame rotation of an Unreal FRotator."""
    sp, cp = math.sin(math.radians(pitch)), math.cos(math.radians(pitch))
    sy, cy = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
    sr, cr = math.sin(math.radians(roll)), math.cos(math.radians(roll))
    U = np.array([[cp * cy, sr * sp * cy - cr * sy, -(cr * sp * cy + sr * sy)],
                  [cp * sy, sr * sp * sy + cr * cy, cy * sr - cr * sp * sy],
                  [sp, -sr * cp, cr * cp]])
    F = np.diag([1.0, -1.0, 1.0])
    return F @ U @ F


def seat(hf, x, y, yaw, scale, fp, gap=0.03, sink=0.0, tilt=0.0, max_tilt=25.0):
    """(z, buried, step, M, stands_out) for instances of footprint `fp` at (x, y), yaw (degrees) and scale.

    z: pivot height so no point of the underside stands more than `gap` above the ground (minus `sink`, a
    deliberate embedding in metres at scale 1). buried: fraction of the instance's height below the highest
    ground under it. step: highest minus lowest ground round the trunk / base (a tree on a ledge).
    tilt > 0 beds the instance into the slope: it leans by that fraction of the slope (a boulder, a log),
    M is its rotation (N, 3, 3), the bare yaw when tilt is 0. stands_out: how far its top stands above the
    ground under it, as a fraction of its height (a boulder bedded in a cliff face shows its downhill half)."""
    x = np.atleast_1d(np.asarray(x, np.float64))
    y = np.atleast_1d(np.asarray(y, np.float64))
    s = np.broadcast_to(np.asarray(scale, np.float64), x.shape)
    yaw = np.broadcast_to(np.asarray(yaw, np.float64), x.shape)
    reach = float(np.hypot(fp.pts[:, 0], fp.pts[:, 1]).max()) if len(fp.pts) else 0.3
    M = tilt_matrices(x, y, yaw, hf, 0.7 * reach * s, tilt if tilt > 0 else 0.0, max_tilt)
    gc = hf(x, y)
    z = gc - M[:, 2, 2] * fp.z0 * s
    hi = gc.copy()
    dz_lo = M[:, 2, 2] * fp.z0 * s
    for (px, py, b) in fp.pts:
        q = np.array([px, py, b + fp.z0])
        d = (M @ q) * s[:, None]
        g = hf(x + d[:, 0], y + d[:, 1])
        z = np.minimum(z, g - d[:, 2])
        hi = np.maximum(hi, g)
        dz_lo = np.minimum(dz_lo, d[:, 2])
    lo_base, hi_base = gc.copy(), gc.copy()
    rb = max(fp.trunk, 0.15) * 1.3 * s
    for t in np.linspace(0.0, 2 * math.pi, ANGLES, endpoint=False):
        g = hf(x + math.cos(t) * rb, y + math.sin(t) * rb)
        lo_base = np.minimum(lo_base, g)
        hi_base = np.maximum(hi_base, g)
    z = z + gap - sink * s
    buried = np.clip((hi - (z + dz_lo)) / np.maximum(fp.h * s, 1e-3), 0.0, None)
    top = (M @ np.array([0.0, 0.0, fp.z0 + fp.h])) * s[:, None]
    out = (z + top[:, 2] - hf(x + top[:, 0], y + top[:, 1])) / np.maximum(fp.h * s, 1e-3)
    return z, buried, hi_base - lo_base, M, out


class Spacing:
    """Spatial hash of placed footprints: hard radius (trunk, boulder - nothing may overlap it) and soft
    radius (crown - other crowns may reach into it by a factor)."""

    def __init__(self, cell=8.0):
        self.cell = cell
        self.grid = {}
        self.rmax = 0.0

    def _key(self, x, y):
        return int(math.floor(x / self.cell)), int(math.floor(y / self.cell))

    def add(self, x, y, hard, soft=0.0):
        self.grid.setdefault(self._key(x, y), []).append((x, y, hard, soft))
        self.rmax = max(self.rmax, hard, soft)

    def ok(self, x, y, hard, soft=0.0, interlock=0.5):
        """True when (x, y) keeps clear of every hard radius and its crown overlaps no other crown by more
        than `interlock` (0 = crowns just touch, 1 = trunks may stand at the crown edge of the other)."""
        reach = hard + soft + 2 * self.rmax
        n = int(math.ceil(reach / self.cell))
        kx, ky = self._key(x, y)
        k = 1.0 - interlock
        for i in range(kx - n, kx + n + 1):
            for j in range(ky - n, ky + n + 1):
                for (px, py, ph, ps) in self.grid.get((i, j), ()):
                    d = math.hypot(x - px, y - py)
                    if d < hard + ph:
                        return False
                    if soft > 0.0 and ps > 0.0 and d < k * (soft + ps):
                        return False
        return True

    def hard_clear(self, x, y, r):
        """Vectorised: mask of points whose radius r keeps clear of every hard footprint."""
        pts = [(px, py, ph) for cell in self.grid.values() for (px, py, ph, _ps) in cell if ph > 0.0]
        x = np.asarray(x, np.float64)
        y = np.asarray(y, np.float64)
        if not pts or not x.size:
            return np.ones(x.shape, bool)
        from scipy.spatial import cKDTree
        a = np.array(pts)
        tree = cKDTree(a[:, :2])
        hmax = float(a[:, 2].max())
        r = np.broadcast_to(np.asarray(r, np.float64), x.shape)
        ok = np.ones(x.shape, bool)
        for n, near in enumerate(tree.query_ball_point(np.c_[x, y], r + hmax)):
            for m in near:
                if math.hypot(x[n] - a[m, 0], y[n] - a[m, 1]) < r[n] + a[m, 2]:
                    ok[n] = False
                    break
        return ok


def value_noise(rng, cell, octaves=((1.0, 1.0),)):
    """Smooth deterministic noise in [0, 1] over the world: a sum of gaussian-blurred random grids,
    `cell` metres per grid sample, octaves of (size multiplier, weight). Returns f(x, y)."""
    from scipy import ndimage
    from . import config as C
    from . import terrain
    n = int(C.WORLD_SIZE / cell) + 1
    acc = np.zeros((n, n))
    tot = 0.0
    for mul, w in octaves:
        g = ndimage.gaussian_filter(rng.random((n, n)), sigma=2.5 * mul, mode="wrap")
        g = (g - g.mean()) / max(g.std(), 1e-9)
        acc += w * g
        tot += w
    acc /= tot
    acc = 0.5 + 0.5 * np.tanh(acc * 0.9)     # roughly uniform in [0, 1]
    return terrain.Field(acc)
