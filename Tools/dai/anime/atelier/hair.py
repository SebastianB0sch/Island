"""
Clump hair for the atelier characters.

Anime hair is a few dozen thick, pointed locks rather than strands. Every lock here is a lens-shaped ribbon
lofted along a path that starts at the crown, is combed over the scalp (head.Head.scalp, with a loft that
lets the hair stand off the skull) and then leaves the head: fringe locks end over the forehead, side and
back locks hang, flick or spike, tails hang from a tie. A cap under the locks closes the scalp.

A style is a dict of sections (see STYLES):

  fringe  {kind: centre|swept|m|straight|curtain, to: ring it ends at, n, width (deg), sweep, loft}
  sides   {to, free, n, curl, flare}
  back    {to, free, n, curl, flare, layers, taper}
  spikes  {lift, n, free, rings}      short spiky hair leaving the scalp early
  tails   [{at: (theta deg, ring), n, free, dir, spread, wave, curl}]
  ahoge   free length of the antenna lock

UVs: u across a lock, v = distance from the crown in metres (paint.hair puts the highlight band at a fixed
distance, so it forms a ring round the head). Long locks are skinned to spring-bone chains
(HairJoint_<Key>_Long<nn>_<j> / _Short<nn>_<j>, the names the runtime's spring solver looks for).
"""

import numpy as np

from . import head as H
from . import mesh as M

UV_LENGTH = 1.0                       # metres of hair the texture's v axis covers
LONG = 0.20                           # free length (m) from which a lock gets a "Long" chain


def _unit(v):
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12)


class Lock:
    """One lock: centre line (K, 3), outward normals (K, 3), widths, where it leaves the head."""

    def __init__(self, path, normal, width, thick, free_from, d0=0.0, blunt=0.0, sector=0.0, kind="short"):
        self.p, self.n = path, normal
        self.width, self.thick = width, thick
        self.free_from = free_from          # index of the first free (off-scalp) point
        self.d0 = d0
        self.blunt = blunt
        self.sector = sector                # azimuth (rad) used to group locks into spring chains
        self.kind = kind
        seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
        self.arc = np.concatenate([[0.0], np.cumsum(seg)])

    @property
    def free_len(self):
        return float(self.arc[-1] - self.arc[self.free_from])


class Hair:
    def __init__(self, head, body=None, seed=1):
        self.head = head
        self.body = body
        self.rng = np.random.default_rng(seed)
        self.locks = []

    # ------------------------------------------------------------------ lock paths
    def lock(self, az, s0, s1, free=0.0, sweep=0.0, loft=(0.004, 0.012), width=0.030, thick=0.25,
             gravity=0.30, flare=0.0, curl=0.0, wave=0.0, lift=0.0, direction=None, blunt=0.0, kind=None,
             n_scalp=9, sector=None, forward=0.0):
        """Comb one lock from ring s0 to s1 at azimuth az (rad, 0 = front), then let `free` metres hang.
        sweep: azimuth change along the scalp part; flare: push away from the body axis; curl: tip turn
        (> 0 outwards / upwards); lift: initial upward kick of the free part; direction: explicit start
        direction of the free part; forward: push of the free part towards the chest."""
        hd = self.head
        t = np.linspace(0.0, 1.0, n_scalp)
        s = s0 + (s1 - s0) * t
        th = az + sweep * t ** 1.6
        lo = loft[0] + (loft[1] - loft[0]) * M.smooth(t * 1.15)
        p, n = hd.scalp(th, s, lo)
        path, nrm = [q for q in p], [q for q in n]
        free_from = len(path)
        if free > 1e-4:
            steps = max(3, int(free / 0.022))
            ds = free / steps
            d = _unit(path[-1] - path[-2]) if direction is None else _unit(np.asarray(direction, np.float64))
            d = _unit(d + np.array([0.0, 0.0, lift]))
            pos = path[-1].copy()
            for i in range(steps):
                k = (i + 1) / steps
                rad = np.array([pos[0], pos[1] - H.C[1], 0.0])
                rad = rad / max(np.linalg.norm(rad), 1e-6)
                tgt = _unit(np.array([0.0, -forward, -1.0]) + rad * flare)
                d = _unit(d * (1.0 - gravity) + tgt * gravity)
                if curl:
                    side = _unit(np.cross(d, rad))
                    ang = curl * k * k * (2.2 / steps)
                    d = _unit(d * np.cos(ang) + np.cross(side, d) * np.sin(ang))
                if wave:
                    side = _unit(np.cross(d, rad))
                    pos = pos + side * wave * np.sin(k * 9.0) * ds
                pos = pos + d * ds
                if self.body is not None:
                    pos = self.body.push_out(pos[None], 0.014 + 0.010 * (1 - k))[0]
                # keep the lock outside the head too
                rel = pos - H.C
                q = np.linalg.norm(rel / np.array([0.086, 0.100, 0.100]))
                if q < 1.0 and rel[2] > -0.07:
                    pos = H.C + rel / q
                path.append(pos.copy())
                nn = rad - d * float(rad @ d)
                nrm.append(_unit(nn) if np.linalg.norm(nn) > 1e-6 else nrm[-1])
        path, nrm = np.array(path), np.array(nrm)
        d0 = float(np.linalg.norm(path[0] - self.head.scalp(0.0, 0.0, 0.0)[0]))
        lk = Lock(path, nrm, width, thick, free_from, d0=d0, blunt=blunt, sector=az if sector is None else sector,
                  kind=kind or ("long" if free >= LONG else "short"))
        self.locks.append(lk)
        return lk

    # ------------------------------------------------------------------ sections
    def _jit(self, amount):
        return 1.0 + self.rng.uniform(-amount, amount)

    def fringe(self, kind="centre", to=0.43, n=6, width=58.0, sweep=0.25, loft=(0.014, 0.021), spread=2.0,
               tip=0.016, long_mid=0.0, part=0.0, curl=0.0, s0=0.05):
        """Fringe over the forehead, from the crown to ring `to` (0.42 brows .. 0.50 eyes .. 0.58 cheeks)."""
        w = np.radians(width)
        az = np.linspace(-w, w, n) + np.radians(part)
        for i, a in enumerate(az):
            u = (a - np.radians(part)) / w                       # -1 .. 1 across the fringe
            end, sw = to, 0.0
            if kind == "centre":
                sw = sweep * np.sign(u) * (0.35 + 0.65 * abs(u))
                end = to + 0.05 * abs(u) - long_mid * 0.0
            elif kind == "swept":
                sw = sweep * (0.6 + 0.4 * (u + 1) / 2)
                end = to + 0.06 * (u + 1) / 2
            elif kind == "m":
                sw = sweep * np.sign(u) * abs(u) * 0.8
                end = to + 0.07 * (1.0 - min(1.0, abs(u) * 2.2)) + 0.05 * max(0.0, abs(u) - 0.55)
            elif kind == "curtain":
                sw = sweep * np.sign(u if u else 1.0) * (1.0 - 0.5 * abs(u))
                end = to + 0.10 * abs(u)
            elif kind == "straight":
                end = to
            end = end * self._jit(0.025 if kind != "straight" else 0.004)
            arc = 0.090 * (2 * w / max(n - 1, 1))
            self.lock(a, s0, end, free=tip, sweep=sw, loft=(loft[0], loft[1] + 0.0025 * (i % 2)),
                      width=arc * spread, thick=0.24, gravity=0.55, curl=curl, forward=0.25,
                      blunt=0.75 if kind == "straight" else 0.0, kind="fringe")

    def sides(self, to=0.66, free=0.10, n=2, at=74.0, width=0.038, curl=0.0, flare=0.02, loft=(0.014, 0.018),
              forward=0.10, wave=0.0, sweep=0.0):
        for sx in (1.0, -1.0):
            for i in range(n):
                a = np.radians(at + i * 13.0) * sx
                self.lock(a, 0.05, to + 0.03 * i, free=free * (1.0 - 0.12 * i) * self._jit(0.04),
                          sweep=sweep * sx, loft=(loft[0], loft[1] + 0.003 * i), width=width, thick=0.26,
                          gravity=0.42, flare=flare, curl=curl * (1 if curl >= 0 else 1), forward=forward,
                          wave=wave, sector=a)

    def back(self, to=0.72, free=0.30, n=11, start=96.0, curl=0.0, flare=0.02, layers=2, width=1.55,
             loft=(0.016, 0.022), taper=0.0, wave=0.0, blunt=0.0, lift=0.0, gravity=0.32):
        """Hair round the back of the head from +-start degrees, hanging `free` metres below ring `to`.
        taper: the middle of the back hangs longer (> 0) or shorter (< 0)."""
        a0 = np.radians(start)
        for layer in range(layers):
            m = n - layer
            az = np.linspace(a0, 2 * np.pi - a0, m) + (np.pi / m if layer else 0.0) * 0.0
            if layer:
                az = az + (az[1] - az[0]) * 0.5
                az = az[:-1]
            for a in az:
                u = abs((a - np.pi) / (np.pi - a0))               # 0 centre back .. 1 sides
                ln = free * (1.0 + taper * (1.0 - u)) * (1.0 - 0.16 * layer) * self._jit(0.05)
                arc = 0.095 * (2 * (np.pi - a0) / max(m - 1, 1))
                self.lock(a, 0.05, to - 0.05 * layer, free=ln, loft=(loft[0], loft[1] + 0.006 * layer),
                          width=arc * width, thick=0.24, gravity=gravity, flare=flare * (1.0 + 0.5 * layer),
                          curl=curl, wave=wave, blunt=blunt, lift=lift, sector=a)

    def spikes(self, n=16, lift=0.55, free=0.07, rings=(0.20, 0.34, 0.50), start=48.0, flare=0.9, gravity=0.10,
               width=0.040, droop=0.0):
        """Spiky cut: locks leave the scalp early, row by row, and point outwards."""
        a0 = np.radians(start)
        for row, s1 in enumerate(rings):
            m = max(5, int(n * (0.55 + 0.25 * row)))
            az = np.linspace(a0, 2 * np.pi - a0, m, endpoint=True) + row * 0.21
            for a in az:
                self.lock(a, 0.03, s1 * self._jit(0.06), free=free * self._jit(0.20) * (1.0 + 0.25 * row),
                          loft=(0.012, 0.018 + 0.003 * row), width=width, thick=0.30, gravity=gravity + droop * row,
                          flare=flare, lift=lift * (1.0 - 0.35 * row), kind="short", sector=a)

    def tail(self, at=(180.0, 0.36), n=6, free=0.45, direction=(0.0, 0.7, 0.35), spread=0.020, wave=0.0,
             curl=0.0, width=0.040, gravity=0.26, flare=0.0):
        """Tail from a tie on the head (ponytail, twin tail, side tail)."""
        th, s = np.radians(at[0]), at[1]
        base, nrm = self.head.scalp(th, s, 0.010)
        d = _unit(np.asarray(direction, np.float64))
        side = _unit(np.cross(d, nrm))
        up = _unit(np.cross(side, d))
        made = []
        for i in range(n):
            a = 2 * np.pi * i / n
            off = (side * np.cos(a) + up * np.sin(a)) * spread
            dd = _unit(d + off * 6.0)
            lk = self.lock(th, s - 0.02, s, free=free * self._jit(0.07) * (1.0 - 0.12 * (i % 2)),
                           loft=(0.008, 0.012), width=width, thick=0.34, gravity=gravity, wave=wave,
                           curl=curl, direction=dd, flare=flare, kind="long", n_scalp=2, sector=th + 0.001 * i)
            lk.p[: lk.free_from] += off[None] * 0.5
            lk.d0 = 0.16
            made.append(lk)
        return base, made

    def ahoge(self, free=0.07, az=0.15):
        self.lock(az, 0.02, 0.06, free=free, loft=(0.004, 0.008), width=0.014, thick=0.45, gravity=0.16,
                  direction=(0.25, -0.35, 1.0), curl=1.6, kind="short")

    # ------------------------------------------------------------------ geometry
    def cap(self, mat, line=(0.27, 0.50, 0.74), loft=0.009):
        """Scalp shell under the locks: down to ring line[0] at the front, line[1] at the sides, line[2] at
        the back."""
        th = np.linspace(0.0, 2 * np.pi, 48, endpoint=False)
        front = 0.5 + 0.5 * np.cos(th)
        side = np.sin(th) ** 2
        edge = line[2] + (line[0] - line[2]) * M.smooth(front * 1.05) ** 1.4
        edge = edge + (line[1] - 0.5 * (line[0] + line[2])) * side * 0.6
        rows = np.linspace(0.0, 1.0, 14)
        s = 0.012 + (edge[None] - 0.012) * rows[:, None]
        pts, _ = self.head.scalp(np.broadcast_to(th, s.shape), s, loft)
        p = M.loft("hair_cap", mat, pts, closed=True, cap0=True, outline=0.0)
        d = np.linalg.norm(p.v - self.head.scalp(0.0, 0.0, 0.0)[0], axis=1)
        p.uv[:, 1] = 1.0 - np.clip(d * 1.25 / UV_LENGTH, 0.0, 0.999)
        return p.rigid("head").rounded(H.C + (0, 0.012, 0), 0.8)

    def _lock_part(self, lk, mat):
        K = len(lk.p)
        L = max(lk.arc[-1], 1e-6)
        tau = lk.arc / L
        tip_len = max(0.012, min(0.40 * L, 0.085) * (1.0 - lk.blunt))
        tip = np.clip((L - lk.arc) / tip_len, 0.0, 1.0) ** 0.72
        w = lk.width * np.minimum(1.0, 0.62 + tau * 1.6) * tip
        w = np.maximum(w, lk.width * 0.03)
        th = np.minimum(lk.width * lk.thick, 0.011) * np.minimum(1.0, 0.45 + tau * 2.2) * (0.25 + 0.75 * tip)
        tan = _unit(np.gradient(lk.p, axis=0))
        side = _unit(np.cross(tan, lk.n))
        nrm = _unit(np.cross(side, tan))
        us = np.array([-1.0, -0.55, 0.0, 0.55, 1.0, 0.5, 0.0, -0.5])
        bulge = np.array([0.0, 0.70, 1.0, 0.70, 0.0, -0.28, -0.40, -0.28])
        rings = lk.p[:, None] + side[:, None] * (us[None, :, None] * w[:, None, None] * 0.5) + \
            nrm[:, None] * (bulge[None, :, None] * th[:, None, None])
        cu = np.array([0.0, 0.225, 0.5, 0.775, 1.0, 0.75, 0.5, 0.25, 0.0])
        v = 1.0 - np.clip((lk.d0 + lk.arc) / UV_LENGTH, 0.0, 0.999)
        p = M.loft("lock", mat, rings, closed=True, cap1=True, us=cu, vs=np.zeros(K))
        C = rings.shape[1] + 1
        p.uv[: K * C, 1] = np.repeat(v, C)
        p.uv[K * C:, 1] = v[-1]
        ol = np.repeat(0.25 + 0.50 * tip, C)
        p.outline = np.concatenate([ol, np.full(len(p.v) - len(ol), 0.3)])
        below = np.clip((H.C[2] - 0.10 - p.v[:, 2]) / 0.25, 0.0, 1.0)
        p.rounded(H.C + (0, 0.012, 0), 0.62 * (1.0 - below) + 0.12 * below)
        p._tau = np.concatenate([np.repeat(lk.arc, C), np.full(len(p.v) - K * C, lk.arc[-1])])
        return p

    def build(self, mat, key, cap=True, cap_line=(0.27, 0.50, 0.74), min_chain=0.085):
        """-> (parts, bones): hair mesh parts and the spring bones [(name, parent, head, tail)]."""
        parts = [self.cap(mat, cap_line)] if cap else []
        chains = self._chains(key, min_chain)
        bones = [b for ch in chains for b in ch["bones"]]
        for lk in self.locks:
            p = self._lock_part(lk, mat)
            p.rigid("head")
            ch = self._chain_for(lk, chains)
            if ch is not None:
                f0 = lk.arc[lk.free_from - 1]
                x = np.clip((p._tau - f0) / max(lk.free_len, 1e-6), 0.0, 1.0)      # 0 at the head .. 1 at the tip
                nb = len(ch["bones"])
                pos = x * nb * ch["reach"]
                rigid = 1.0 - M.smooth(x / 0.12)
                p.w = {"head": rigid}
                for j, (name, _, _, _) in enumerate(ch["bones"]):
                    k = np.clip(1.0 - np.abs(pos - (j + 0.5)), 0.0, 1.0)
                    if j == nb - 1:
                        k = np.maximum(k, (pos > j + 0.5).astype(float))
                    if j == 0:
                        k = np.maximum(k, (pos < 0.5).astype(float))
                    p.w[name] = k * (1.0 - rigid)
                tot = sum(p.w.values())
                p.w = {b: a / np.maximum(tot, 1e-9) for b, a in p.w.items()}
            parts.append(p)
        return parts, bones

    def _chains(self, key, min_chain):
        """Group the free locks into azimuth sectors; one bone chain per sector along the mean path."""
        groups = {}
        for lk in self.locks:
            if lk.free_len < min_chain or lk.kind == "fringe":
                continue
            long_ = lk.free_len >= LONG
            width = 0.55 if long_ else 0.70
            sec = int(np.floor(((lk.sector % (2 * np.pi)) + width / 2) / width))
            groups.setdefault((long_, sec), []).append(lk)
        chains = []
        for idx, ((long_, sec), locks) in enumerate(sorted(groups.items(), key=lambda kv: (not kv[0][0], kv[0][1]))):
            joints = 5 if long_ else 3
            ln = float(np.mean([lk.free_len for lk in locks]))
            samples = []
            for lk in locks:
                f0 = lk.arc[lk.free_from - 1]
                d = f0 + np.linspace(0.0, 1.0, joints + 1) * min(lk.free_len, ln)
                samples.append(np.stack([np.interp(d, lk.arc, lk.p[:, c]) for c in range(3)], axis=1))
            J = np.mean(samples, axis=0)
            kind = "Long" if long_ else "Short"
            nn = sum(1 for c in chains if c["kind"] == kind)
            bones, parent = [], "head"
            for j in range(joints):
                name = f"HairJoint_{key}_{kind}{nn:02d}_{j}"
                bones.append((name, parent, tuple(J[j]), tuple(J[j + 1])))
                parent = name
            chains.append(dict(kind=kind, locks=locks, bones=bones, reach=1.0))
        return chains

    @staticmethod
    def _chain_for(lk, chains):
        for ch in chains:
            if any(l is lk for l in ch["locks"]):
                return ch
        return None


# --------------------------------------------------------------------------- styles
def style(hair, spec):
    """Comb a style spec (dict of sections, see the module docstring) into `hair`."""
    if spec.get("fringe"):
        hair.fringe(**spec["fringe"])
    if spec.get("sides"):
        hair.sides(**spec["sides"])
    if spec.get("spikes"):
        hair.spikes(**spec["spikes"])
    if spec.get("back"):
        hair.back(**spec["back"])
    ties = []
    for t in spec.get("tails", ()):
        ties.append(hair.tail(**t)[0])
    if spec.get("ahoge"):
        hair.ahoge(spec["ahoge"])
    return ties
