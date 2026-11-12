"""Walkable-space voxel field for the reachability audit (numpy only).

The collision triangles of a region are rasterised into vertical *spans* per grid column (the same idea
as Recast's solid heightfield, which is what Unreal's navmesh bake uses):

  * a triangle that is not near-vertical is sampled at every cell centre it covers (plus its edges, so
    slivers narrower than a cell are never lost); a near-vertical one is cut into vertical slices,
  * touching / overlapping spans of one column are merged into solids; a solid's top is *walkable* when
    the highest triangle that made it faces up within the walkable slope,
  * a walkable top is a *floor* when the next solid above it leaves the character's height free,
  * a floor is *standable* when no solid reaches into the character's body in any column within the
    capsule radius.  The body is the capsule with its round ends, raised by the max step height at the
    bottom: Unreal's StepUp / FindFloor let the capsule ride over anything up to MaxStepHeight with any
    part of its round bottom,
  * two standable floors in 4-neighbouring columns are connected when their height difference is at most
    the max step height (holes up to 30 cm wide are stepped across).

A flood fill over that graph answers "can the capsule walk from A to B".

Resolution limits (state them in every report): columns are `cell` wide (default 10 cm), obstacles are
whole columns, and the radius test uses `radius - cell / 2`, so a passage narrower than about
`2 * radius - 2 * cell` always fails, one wider than `2 * radius` always passes, and in between the
result depends on how the opening falls on the grid.  Exact door sizes are therefore measured
analytically by the caller, not by the grid.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

SRC_BUILDING, SRC_TERRAIN, SRC_PROP = 0, 1, 2
_ZK = 4096.0            # key = column * _ZK + height: heights must stay below this (metres above the grid floor)
GAP = 0.3               # metres: floors this far apart with nothing between them still connect (see _bridge_gaps)
_STEEP_NZ = 0.2         # |normal.z| below this: the triangle is rasterised as vertical slices


@dataclass(frozen=True)
class Agent:
    """Movement envelope (metres / degrees).  Defaults: ADAStudentCharacter on foot."""
    radius: float = 0.38
    height: float = 1.84
    step: float = 0.45
    slope: float = 46.0


# --------------------------------------------------------------------------- rasteriser
def _chunks(counts, limit):
    """Slices of `counts` whose sums stay near `limit` (each slice has at least one item)."""
    csum = np.cumsum(counts)
    start, total = 0, 0
    n = len(counts)
    while start < n:
        end = int(np.searchsorted(csum, total + limit, side="right"))
        end = max(end, start + 1)
        yield start, min(end, n)
        total = csum[min(end, n) - 1]
        start = end


def _segments(p, q, half, walk, src, out, nx, ny, cs):
    """Pieces of the 3D segments p -> q no longer than `half` in plan; one span per piece."""
    if len(p) == 0:
        return
    d = q - p
    n = np.maximum(1, np.ceil(np.hypot(d[:, 0], d[:, 1]) / half)).astype(np.int64)
    for a, b in _chunks(n, 4_000_000):
        nn = n[a:b]
        rep = np.repeat(np.arange(a, b), nn)
        first = np.cumsum(nn) - nn
        k = np.arange(len(rep)) - np.repeat(first, nn)
        t0 = k / n[rep]
        t1 = (k + 1) / n[rep]
        tm = (t0 + t1) * 0.5
        x = p[rep, 0] + d[rep, 0] * tm
        y = p[rep, 1] + d[rep, 1] * tm
        za = p[rep, 2] + d[rep, 2] * t0
        zb = p[rep, 2] + d[rep, 2] * t1
        i = np.floor(x / cs).astype(np.int64)
        j = np.floor(y / cs).astype(np.int64)
        ok = (i >= 0) & (i < nx) & (j >= 0) & (j < ny)
        out.append(((i + j * nx)[ok], np.minimum(za, zb)[ok].astype(np.float32),
                    np.maximum(za, zb)[ok].astype(np.float32), walk[rep][ok], src[rep][ok]))


def rasterize(tris, src, shape, cs, slope_deg):
    """tris (T, 3, 3) in grid space (x, y in [0, nx*cs) x [0, ny*cs), z >= 0), src (T,) int8.
    Returns unsorted span pieces: column, zlo, zhi, walkable, src."""
    nx, ny = shape
    tris = np.asarray(tris, np.float64)
    src = np.asarray(src, np.int8)
    out = []
    if len(tris) == 0:
        return _cat(out)
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    nrm = np.cross(v1 - v0, v2 - v0)
    area2 = np.linalg.norm(nrm, axis=1)
    good = area2 > 1e-10
    tris, src, nrm, area2 = tris[good], src[good], nrm[good], area2[good]
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    nrm = nrm / area2[:, None]
    walk_all = nrm[:, 2] >= math.cos(math.radians(slope_deg))
    steep = np.abs(nrm[:, 2]) < _STEEP_NZ
    half = cs * 0.5

    # ---- flat-ish triangles: cell centres inside the projection
    f = np.flatnonzero(~steep)
    if len(f):
        a0, a1, a2, n, w, s = v0[f], v1[f], v2[f], nrm[f], walk_all[f], src[f]
        xs = np.stack([a0[:, 0], a1[:, 0], a2[:, 0]], 1)
        ys = np.stack([a0[:, 1], a1[:, 1], a2[:, 1]], 1)
        i0 = np.maximum(np.ceil(xs.min(1) / cs - 0.5), 0).astype(np.int64)
        i1 = np.minimum(np.floor(xs.max(1) / cs - 0.5), nx - 1).astype(np.int64)
        j0 = np.maximum(np.ceil(ys.min(1) / cs - 0.5), 0).astype(np.int64)
        j1 = np.minimum(np.floor(ys.max(1) / cs - 0.5), ny - 1).astype(np.int64)
        ni = np.maximum(i1 - i0 + 1, 0)
        nj = np.maximum(j1 - j0 + 1, 0)
        cnt = ni * nj
        gx = -n[:, 0] / n[:, 2]
        gy = -n[:, 1] / n[:, 2]
        dz = half * (np.abs(gx) + np.abs(gy))
        sign = np.sign(n[:, 2])
        keep = np.flatnonzero(cnt > 0)
        for a, b in _chunks(cnt[keep], 6_000_000):
            sel = keep[a:b]
            c = cnt[sel]
            rep = np.repeat(sel, c)
            first = np.cumsum(c) - c
            k = np.arange(len(rep)) - np.repeat(first, c)
            i = i0[rep] + k % ni[rep]
            j = j0[rep] + k // ni[rep]
            px = (i + 0.5) * cs
            py = (j + 0.5) * cs
            ax, ay, bx, by, cx, cy = a0[rep, 0], a0[rep, 1], a1[rep, 0], a1[rep, 1], a2[rep, 0], a2[rep, 1]
            sg = sign[rep]
            eps = -1e-9
            inside = (((bx - ax) * (py - ay) - (by - ay) * (px - ax)) * sg >= eps) & \
                     (((cx - bx) * (py - by) - (cy - by) * (px - bx)) * sg >= eps) & \
                     (((ax - cx) * (py - cy) - (ay - cy) * (px - cx)) * sg >= eps)
            rep, i, j, px, py = rep[inside], i[inside], j[inside], px[inside], py[inside]
            z = a0[rep, 2] + gx[rep] * (px - a0[rep, 0]) + gy[rep] * (py - a0[rep, 1])
            d = dz[rep]
            wk = w[rep]
            out.append((i + j * nx, (z - d).astype(np.float32), np.where(wk, z, z + d).astype(np.float32),
                        wk, s[rep]))
        for p, q in ((a0, a1), (a1, a2), (a2, a0)):
            _segments(p, q, half, w, s, out, nx, ny, cs)

    # ---- near-vertical triangles: vertical slices every half cell along the wall
    g = np.flatnonzero(steep)
    if len(g):
        t, n, s = tris[g], nrm[g], src[g]
        h = np.hypot(n[:, 0], n[:, 1])
        ux, uy = -n[:, 1] / h, n[:, 0] / h
        sv = t[:, :, 0] * ux[:, None] + t[:, :, 1] * uy[:, None]
        order = np.argsort(sv, axis=1)
        rows = np.arange(len(t))[:, None]
        t = t[rows, order]
        sv = sv[rows, order]
        pa, pm, pc = t[:, 0], t[:, 1], t[:, 2]
        sa, sm, sc = sv[:, 0], sv[:, 1], sv[:, 2]
        span = np.maximum(sc - sa, 1e-9)
        nsl = np.maximum(1, np.ceil(span / half)).astype(np.int64)
        nowalk = np.zeros(len(t), bool)
        for a, b in _chunks(nsl, 4_000_000):
            nn = nsl[a:b]
            rep = np.repeat(np.arange(a, b), nn)
            first = np.cumsum(nn) - nn
            k = np.arange(len(rep)) - np.repeat(first, nn)
            sk = sa[rep] + (k + 0.5) / nsl[rep] * span[rep]
            tl = ((sk - sa[rep]) / span[rep])[:, None]
            p = pa[rep] + (pc[rep] - pa[rep]) * tl
            low = sk < sm[rep]
            d1 = np.maximum(sm[rep] - sa[rep], 1e-9)
            d2 = np.maximum(sc[rep] - sm[rep], 1e-9)
            q = np.where(low[:, None], pa[rep] + (pm[rep] - pa[rep]) * ((sk - sa[rep]) / d1)[:, None],
                         pm[rep] + (pc[rep] - pm[rep]) * ((sk - sm[rep]) / d2)[:, None])
            _segments(p, q, half, nowalk[rep], s[rep], out, nx, ny, cs)
        # the three edges too: the slices sample between them, not on them
        for p, q in ((pa, pm), (pm, pc), (pa, pc)):
            _segments(p, q, half, nowalk, s, out, nx, ny, cs)
    return _cat(out)


def _cat(parts):
    if not parts:
        return (np.zeros(0, np.int64), np.zeros(0, np.float32), np.zeros(0, np.float32), np.zeros(0, bool),
                np.zeros(0, np.int8))
    return tuple(np.concatenate([p[k] for p in parts]) for k in range(5))


# --------------------------------------------------------------------------- field
class Field:
    """Solid spans + standable floors of one region.  All heights are metres above the grid floor."""

    def __init__(self, pieces, shape, cs, agent, merge_gap=0.02):
        self.nx, self.ny = shape
        self.cs, self.agent = cs, agent
        col, zlo, zhi, walk, src = pieces
        order = np.lexsort((zlo, col))
        col, zlo, zhi, walk, src = col[order], zlo[order].astype(np.float64), zhi[order].astype(np.float64), \
            walk[order], src[order]
        if len(col) and float(zhi.max()) >= _ZK - 8:
            raise ValueError("region taller than the key range")
        if len(col) == 0:
            self._empty()
            return
        newcol = np.concatenate(([True], col[1:] != col[:-1]))
        rank = np.cumsum(newcol) - 1
        run = np.maximum.accumulate(zhi + rank * (2 * _ZK)) - rank * (2 * _ZK)   # running top inside a column
        start = newcol.copy()
        start[1:] |= zlo[1:] > run[:-1] + merge_gap
        first = np.flatnonzero(start)
        # top of each solid + the flags of the piece that made it (walkable wins a tie within 1 mm)
        score = (np.round(zhi * 1000.0).astype(np.int64) << 3) | (walk.astype(np.int64) << 2) | src.astype(np.int64)
        best = np.maximum.reduceat(score, first)
        self.scol = col[first]
        self.sbot = zlo[first]
        self.stop = (best >> 3) / 1000.0
        swalk = ((best >> 2) & 1).astype(bool)
        ssrc = (best & 3).astype(np.int8)
        self.skey = self.scol * _ZK + self.sbot
        nxt = np.full(len(first), np.inf)
        same = self.scol[1:] == self.scol[:-1]
        nxt[:-1][same] = self.sbot[1:][same]
        clear = nxt - self.stop
        fl = swalk & (clear >= agent.height - 1e-3)
        self.fcol, self.fz, self.fceil, self.fsrc = self.scol[fl], self.stop[fl], nxt[fl], ssrc[fl]
        self.fkey = self.fcol * _ZK + self.fz
        self.n = len(self.fcol)
        self.fi = (self.fcol % self.nx).astype(np.int64)
        self.fj = (self.fcol // self.nx).astype(np.int64)
        self._neighbours()
        self._clearance()

    def _empty(self):
        z = np.zeros(0)
        self.scol = self.fcol = self.fi = self.fj = np.zeros(0, np.int64)
        self.sbot = self.stop = self.skey = self.fz = self.fceil = self.fkey = z
        self.fsrc = np.zeros(0, np.int8)
        self.n = 0
        self.nb = np.zeros((4, 0), np.int64)
        self.edge = np.zeros(0, bool)
        self.stand = np.zeros(0, bool)

    def _shift(self, di, dj, idx=None):
        """Column of the neighbour at (di, dj) for every floor (or the floors idx); -1 outside the grid."""
        i = self.fi if idx is None else self.fi[idx]
        j = self.fj if idx is None else self.fj[idx]
        ni, nj = i + di, j + dj
        ok = (ni >= 0) & (ni < self.nx) & (nj >= 0) & (nj < self.ny)
        return np.where(ok, ni + nj * self.nx, -1)

    def neighbours(self, step):
        """(4, n) index of the floor a step of at most `step` away in +x, -x, +y, -y (-1: none)."""
        step = step + 1e-3
        nb = np.full((4, self.n), -1, np.int64)
        if self.n == 0:
            return nb
        for d, (di, dj) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
            nc = self._shift(di, dj)
            idx = np.searchsorted(self.fkey, nc * _ZK + (self.fz - step), side="left")
            idx_c = np.minimum(idx, self.n - 1)
            ok = (nc >= 0) & (idx < self.n) & (self.fcol[idx_c] == nc) & (self.fz[idx_c] <= self.fz + step)
            # two floors a full body height apart can both lie inside a tall step window: take the nearest
            alt = np.minimum(idx_c + 1, self.n - 1)
            better = ok & (self.fcol[alt] == nc) & (alt != idx_c) & \
                (np.abs(self.fz[alt] - self.fz) < np.abs(self.fz[idx_c] - self.fz))
            idx_c = np.where(better, alt, idx_c)
            nb[d] = np.where(ok, idx_c, -1)
        return nb

    def _bridge_gaps(self):
        """Link floors across holes narrower than GAP (a missing plank, the slot between a stair and its
        landing): the capsule rides over them on its rim, as Unreal's floor sweep does.  Only where the
        direct neighbour is missing; the radius test still keeps walls out."""
        step = self.agent.step + 1e-3
        for k in range(2, int(round(GAP / self.cs)) + 2):
            for d, (di, dj) in enumerate(((1, 0), (-1, 0), (0, 1), (0, -1))):
                todo = np.flatnonzero(self.nb[d] < 0)
                if len(todo) == 0:
                    continue
                nc = self._shift(di * k, dj * k, todo)
                z = self.fz[todo]
                idx = np.searchsorted(self.fkey, nc * _ZK + (z - step), side="left")
                idx_c = np.minimum(idx, self.n - 1)
                ok = (nc >= 0) & (idx < self.n) & (self.fcol[idx_c] == nc) & (self.fz[idx_c] <= z + step)
                self.nb[d][todo[ok]] = idx_c[ok]

    def _neighbours(self):
        self.nb = self.neighbours(self.agent.step)
        # floors with a missing direct neighbour - the only ones a wall can be near (see stand_mask).  Taken
        # before the gap bridging: a bridge across a wall's face columns (a 20 - 30 cm wall reads like a gap)
        # made the floors either side look interior, their radius test was skipped, and the flood walked
        # through the wall.
        self.edge = (self.nb < 0).any(axis=0) if self.n else np.zeros(0, bool)
        if self.n:
            self._bridge_gaps()

    def stand_mask(self, radius):
        """Floors with no solid inside the body band (max step .. height above the feet) in any column
        within `radius` (tested as radius - cell / 2, see the module notes)."""
        a = self.agent
        reach = max(radius - 0.5 * self.cs, 0.0) / self.cs
        r = int(math.floor(reach))
        offs = [(di, dj) for di in range(-r, r + 1) for dj in range(-r, r + 1)
                if (di or dj) and di * di + dj * dj <= reach * reach + 1e-9]
        # only floors near an edge of the walkable sheet can have a wall inside the radius
        near = self.edge.copy()
        for _ in range(int(math.ceil(1.5 * r)) + 1):
            grown = near.copy()
            for d in range(4):
                ok = self.nb[d] >= 0
                grown[ok] |= near[self.nb[d][ok]]
                grown[self.nb[d][ok]] |= near[ok]
            near = grown
        cand = np.flatnonzero(near)
        blocked = np.zeros(len(cand), bool)
        zc = self.fz[cand]
        ns = len(self.skey)
        for (di, dj) in offs:
            live = np.flatnonzero(~blocked)
            if len(live) == 0:
                break
            # the capsule's round ends: at plan distance d from the axis its surface starts cap above the
            # feet and ends cap below the head.  Unreal lets it ride up a step with any part of that round
            # bottom (StepUp / FindFloor perch on the edge), so a solid only blocks from step + cap upwards.
            d = min(self.cs * math.hypot(di, dj), radius)
            cap = radius - math.sqrt(max(radius * radius - d * d, 0.0))
            nc = self._shift(di, dj, cand[live])
            z = zc[live]
            idx = np.searchsorted(self.skey, nc * _ZK + (z + a.height - cap - 1e-3), side="left") - 1
            idx_c = np.clip(idx, 0, max(ns - 1, 0))
            hit = (nc >= 0) & (idx >= 0) & (self.scol[idx_c] == nc) & (self.stop[idx_c] > z + a.step + cap + 1e-3)
            blocked[live[hit]] = True
        stand = np.ones(self.n, bool)
        stand[cand[blocked]] = False
        return stand

    def _clearance(self):
        self.stand = self.stand_mask(self.agent.radius)

    # ------------------------------------------------------------------ queries
    def snap(self, x, y, z, reach=0.5, dz=0.6, standable=True, stand=None):
        """Index of the floor nearest to (x, y, z) (grid space) within `reach` in plan and `dz` in height,
        or -1.  With standable=False any floor counts (to explain a failure); stand overrides the agent's
        own standable mask (another capsule radius, see stand_mask)."""
        stand = self.stand if stand is None else stand
        r = int(math.ceil(reach / self.cs))
        ci, cj = int(math.floor(x / self.cs)), int(math.floor(y / self.cs))
        best, bd = -1, None
        for dj in range(-r, r + 1):
            for di in range(-r, r + 1):
                i, j = ci + di, cj + dj
                if not (0 <= i < self.nx and 0 <= j < self.ny):
                    continue
                d2 = ((i + 0.5) * self.cs - x) ** 2 + ((j + 0.5) * self.cs - y) ** 2
                if d2 > (reach + self.cs) ** 2:
                    continue
                c = i + j * self.nx
                lo = int(np.searchsorted(self.fkey, c * _ZK + (z - dz), side="left"))
                while lo < self.n and self.fcol[lo] == c and self.fz[lo] <= z + dz:
                    if not standable or stand[lo]:
                        cost = d2 + (self.fz[lo] - z) ** 2
                        if bd is None or cost < bd:
                            best, bd = lo, cost
                    lo += 1
        return best

    def flood(self, seeds, stand=None, nb=None, parent=None, seen=None, depth=None):
        """Boolean mask of the standable floors connected to any seed index.  stand / nb override the
        agent's own masks (relaxed envelopes); parent (int array) records the floor each one was reached
        from; seen continues an earlier flood."""
        stand = self.stand if stand is None else stand
        nb = self.nb if nb is None else nb
        seen = np.zeros(self.n, bool) if seen is None else seen
        front = np.asarray(seeds, np.int64)
        front = np.unique(front[(front >= 0)])
        front = front[stand[front]]
        seen[front] = True
        level = 0
        while len(front):
            level += 1
            cand = nb[:, front]
            src = np.broadcast_to(front, cand.shape)
            ok = cand >= 0
            cand, src = cand[ok], src[ok]
            ok = stand[cand] & ~seen[cand]
            cand, src = cand[ok], src[ok]
            front, first = np.unique(cand, return_index=True)
            seen[front] = True
            if parent is not None:
                parent[front] = src[first]
            if depth is not None:
                depth[front] = level
        return seen

    def components(self, mask):
        """Label the standable floors selected by mask: (labels with -1 outside, number of components)."""
        idx = np.flatnonzero(mask & self.stand)
        label = np.full(self.n, -1, np.int64)
        if len(idx) == 0:
            return label, 0
        parent = np.full(self.n, -1, np.int64)
        parent[idx] = idx
        us, vs = [], []
        for d in (0, 2):                        # +x and +y are enough: the graph is symmetric
            v = self.nb[d][idx]
            ok = v >= 0
            ok[ok] &= parent[v[ok]] >= 0
            us.append(idx[ok])
            vs.append(v[ok])
        u, v = np.concatenate(us), np.concatenate(vs)
        while True:
            pu, pv = parent[u], parent[v]
            lo = np.minimum(pu, pv)
            changed = pu != pv
            if not changed.any():
                break
            np.minimum.at(parent, pu[changed], lo[changed])
            np.minimum.at(parent, pv[changed], lo[changed])
            while True:                         # pointer jumping
                pp = parent[parent[idx]]
                if (pp == parent[idx]).all():
                    break
                parent[idx] = pp
        roots, inv = np.unique(parent[idx], return_inverse=True)
        label[idx] = inv
        return label, len(roots)

    def path_stats(self, mask):
        """(area m2, z min, z max) of the floors in mask."""
        if not mask.any():
            return 0.0, 0.0, 0.0
        z = self.fz[mask]
        return float(mask.sum()) * self.cs * self.cs, float(z.min()), float(z.max())


def build_field(tris, src, origin, size, cs=0.1, agent=Agent()):
    """Field for world-space triangles inside the box origin .. origin + size (metres)."""
    nx = int(math.ceil(size[0] / cs))
    ny = int(math.ceil(size[1] / cs))
    local = np.asarray(tris, np.float64) - np.asarray(origin, np.float64)
    return Field(rasterize(local, src, (nx, ny), cs, agent.slope), (nx, ny), cs, agent)
