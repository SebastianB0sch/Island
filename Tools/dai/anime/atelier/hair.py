"""
Clump hair for the atelier characters.

Anime hair is a few dozen thick, pointed locks rather than strands. Every lock here is a lens-shaped ribbon
lofted along a path that starts at the crown, is combed over the scalp (head.Head.scalp, with a loft that
lets the hair stand off the skull) and then leaves the head: fringe locks end over the forehead, side and
back locks hang, flick or spike, tails hang from a tie. A cap under the locks closes the scalp.

A style is a dict of sections (see STYLES):

  fringe  {kind: centre|swept|m|straight|curtain, to: ring it ends at, n, width (deg), sweep, loft, part}
  sides   {to, free, n, curl, flare, asym: length of the right side relative to the left}
  back    {to, free, n, curl, flare, layers, taper}
  spikes  {lift, n, free, rings, curl, wave}   short spiky / curly hair leaving the scalp early
  tails   [{at: (theta deg, ring), n, free, dir, spread, wave, curl}]
  braids  [{at, free, direction, width, tuft}]  plaits (one beaded lock each)
  buns    [{at, r, flat}]                       wound buns on the scalp
  ahoge   free length of the antenna lock (or {free, az})

Every section also takes accent=True (or a list of lock / layer indices): those locks are painted in the
style's second "accent" colour (streaks, inner layers, dyed tails) when the hair is built with split UVs
(Hair.split: the texture's left half is the hair colour, its right half the accent).

UVs: u across a lock, v = distance from the crown in metres (paint.hair puts the highlight band at a fixed
distance, so it forms a ring round the head). Long locks are skinned to spring-bone chains
(HairJoint_<Key>_Long<nn>_<j> / _Short<nn>_<j>, the names the runtime's spring solver looks for).
"""

import numpy as np

from . import head as H
from . import mesh as M

UV_LENGTH = 1.0                       # metres of hair the texture's v axis covers
LONG = 0.20                           # free length (m) from which a lock gets a "Long" chain
BAND_END = 0.156                      # distance from the crown where paint.hair's highlight band ends
TOP_U = 0.80                          # the sheet's u < TOP_U is the lit face of a lock, the rest its underside


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
        self.accent = False                 # painted in the accent colour (Hair.split)
        self.braid = 0.0                    # > 0: a plait, bead length in metres
        seg = np.linalg.norm(np.diff(path, axis=0), axis=1)
        self.arc = np.concatenate([[0.0], np.cumsum(seg)])

    @property
    def free_len(self):
        return float(self.arc[-1] - self.arc[self.free_from])


class Hair:
    def __init__(self, head, body=None, seed=1):
        self.head = head
        self.body = body
        # A fitted head (clumphair.FittedHead: a VRoid base's skull) brings its own centre and size; every
        # length of a style recipe is in atelier design metres and is scaled by `k` on such a head.
        self.C = np.asarray(getattr(head, "centre", H.C), np.float64)
        self.k = float(getattr(head, "size", 1.0))
        self.radii = np.asarray(getattr(head, "radii", (0.086, 0.100, 0.100)), np.float64)
        self.rng = np.random.default_rng(seed)
        self.locks = []
        self.extra = []                     # parts that are not locks (buns)
        self.ties = []                      # (position, direction, radius) of tail / braid / bun ties
        self.split = False                  # two-colour texture: u < 0.5 hair colour, u > 0.5 accent

    @staticmethod
    def _is_accent(accent, i):
        return bool(accent) if isinstance(accent, (bool, int, float)) else i in tuple(accent)

    # ------------------------------------------------------------------ lock paths
    def lock(self, az, s0, s1, free=0.0, sweep=0.0, loft=(0.004, 0.012), width=0.030, thick=0.25,
             gravity=0.30, flare=0.0, curl=0.0, wave=0.0, lift=0.0, direction=None, blunt=0.0, kind=None,
             n_scalp=9, sector=None, forward=0.0, up=0.0):
        """Comb one lock from ring s0 to s1 at azimuth az (rad, 0 = front), then let `free` metres hang.
        sweep: azimuth change along the scalp part; flare: push away from the body axis; curl: tip turn
        (> 0 outwards / upwards); lift: initial upward kick of the free part; direction: explicit start
        direction of the free part; forward: push of the free part towards the chest; up: buoyancy against
        gravity (> 1: the lock keeps rising - upswept spikes)."""
        hd = self.head
        K = self.k
        long_ = free >= LONG
        free, width, loft = free * K, width * K, (loft[0] * K, loft[1] * K)
        t = np.linspace(0.0, 1.0, n_scalp)
        s = s0 + (s1 - s0) * t
        th = az + sweep * t ** 1.6
        lo = loft[0] + (loft[1] - loft[0]) * M.smooth(t * 1.15)
        p, n = hd.scalp(th, s, lo)
        path, nrm = [q for q in p], [q for q in n]
        free_from = len(path)
        if free > 1e-4:
            steps = max(3, int(free / (0.022 * K)))
            ds = free / steps
            d = _unit(path[-1] - path[-2]) if direction is None else _unit(np.asarray(direction, np.float64))
            d = _unit(d + np.array([0.0, 0.0, lift]))
            pos = path[-1].copy()
            for i in range(steps):
                k = (i + 1) / steps
                rad = np.array([pos[0], pos[1] - self.C[1], 0.0])
                rad = rad / max(np.linalg.norm(rad), 1e-6)
                tgt = _unit(np.array([0.0, -forward, -1.0 + up]) + rad * flare)
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
                    pos = self.body.push_out(pos[None], (0.014 + 0.010 * (1 - k)) * K)[0]
                # keep the lock outside the head too
                if hasattr(hd, "keep_out"):
                    pos = hd.keep_out(pos, 0.010 * K)
                else:
                    rel = pos - self.C
                    q = np.linalg.norm(rel / self.radii)
                    if q < 1.0 and rel[2] > -0.07 * K:
                        pos = self.C + rel / q
                path.append(pos.copy())
                nn = rad - d * float(rad @ d)
                nrm.append(_unit(nn) if np.linalg.norm(nn) > 1e-6 else nrm[-1])
        path, nrm = np.array(path), np.array(nrm)
        if self.body is not None and len(path) - free_from > 3 and getattr(self.body, "relax", False):
            # the collision pushes leave kinks where a lock meets the shoulders: relax them into a drape
            f = free_from
            for _ in range(6):
                path[f:-1] = 0.25 * path[f - 1:-2] + 0.5 * path[f:-1] + 0.25 * path[f + 1:]
                path[f:] = self.body.push_out(path[f:], 0.014 * K)
            tan = _unit(np.gradient(path[f - 1:], axis=0))[1:]
            rad = np.stack([path[f:, 0], path[f:, 1] - self.C[1], np.zeros(len(path) - f)], axis=1)
            nn = rad - tan * (rad * tan).sum(1, keepdims=True)
            ok = np.linalg.norm(nn, axis=1) > 1e-6
            nrm[f:][ok] = _unit(nn[ok])
        d0 = float(np.linalg.norm(path[0] - self.head.scalp(0.0, 0.0, 0.0)[0])) / K
        lk = Lock(path, nrm, width, thick, free_from, d0=d0, blunt=blunt, sector=az if sector is None else sector,
                  kind=kind or ("long" if long_ else "short"))
        self.locks.append(lk)
        return lk

    # ------------------------------------------------------------------ sections
    def _jit(self, amount):
        return 1.0 + self.rng.uniform(-amount, amount)

    def fringe(self, kind="centre", to=0.43, n=6, width=58.0, sweep=0.25, loft=(0.014, 0.021), spread=2.0,
               tip=0.016, long_mid=0.0, part=0.0, curl=0.0, s0=0.05, accent=False):
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
            lk = self.lock(a, s0, end, free=tip, sweep=sw, loft=(loft[0], loft[1] + 0.0025 * (i % 2)),
                           width=arc * spread, thick=0.24, gravity=0.55, curl=curl, forward=0.25,
                           blunt=0.75 if kind == "straight" else 0.0, kind="fringe")
            lk.accent = self._is_accent(accent, i)

    def sides(self, to=0.66, free=0.10, n=2, at=74.0, width=0.038, curl=0.0, flare=0.02, loft=(0.014, 0.018),
              forward=0.10, wave=0.0, sweep=0.0, asym=1.0, accent=False):
        for sx in (1.0, -1.0):
            for i in range(n):
                a = np.radians(at + i * 13.0) * sx
                ln = free * (1.0 - 0.12 * i) * self._jit(0.04) * (asym if sx < 0 else 1.0)
                lk = self.lock(a, 0.05, to + 0.03 * i, free=ln,
                               sweep=sweep * sx, loft=(loft[0], loft[1] + 0.003 * i), width=width, thick=0.26,
                               gravity=0.42, flare=flare, curl=curl, forward=forward,
                               wave=wave, sector=a)
                lk.accent = self._is_accent(accent, i)

    def back(self, to=0.72, free=0.30, n=11, start=96.0, curl=0.0, flare=0.02, layers=2, width=1.55,
             loft=(0.016, 0.022), taper=0.0, wave=0.0, blunt=0.0, lift=0.0, gravity=0.32, accent=False):
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
                lk = self.lock(a, 0.05, to - 0.05 * layer, free=ln, loft=(loft[0], loft[1] + 0.006 * layer),
                               width=arc * width, thick=0.24, gravity=gravity, flare=flare * (1.0 + 0.5 * layer),
                               curl=curl, wave=wave, blunt=blunt, lift=lift, sector=a)
                lk.accent = self._is_accent(accent, layer)

    def spikes(self, n=16, lift=0.55, free=0.07, rings=(0.20, 0.34, 0.50), start=48.0, flare=0.9, gravity=0.10,
               width=0.040, droop=0.0, curl=0.0, wave=0.0, up=0.0, lift_decay=0.35, accent=False, side_tame=0.0):
        """Spiky cut: locks leave the scalp early, row by row, and point outwards. side_tame: how much the
        spikes over the ears lose of their lift / flare (they stick out sideways like horns otherwise)."""
        a0 = np.radians(start)
        for row, s1 in enumerate(rings):
            m = max(5, int(n * (0.55 + 0.25 * row)))
            az = np.linspace(a0, 2 * np.pi - a0, m, endpoint=True) + row * 0.21
            for a in az:
                rel = abs(((a + np.pi) % (2 * np.pi)) - np.pi)            # 0 front .. pi back
                sd = side_tame * float(np.exp(-((rel - 0.5 * np.pi) / 0.62) ** 2))
                lk = self.lock(a, 0.03, s1 * self._jit(0.06), free=free * self._jit(0.20) * (1.0 + 0.25 * row),
                               loft=(0.012, 0.018 + 0.003 * row), width=width, thick=0.30,
                               gravity=gravity + droop * row + 0.30 * sd, flare=flare * (1.0 - 0.75 * sd),
                               lift=lift * (1.0 - lift_decay * row) * (1.0 - sd),
                               curl=curl, wave=wave, up=up * (1.0 - 0.12 * row) * (1.0 - sd), kind="short", sector=a)
                lk.accent = self._is_accent(accent, row)

    def tail(self, at=(180.0, 0.36), n=6, free=0.45, direction=(0.0, 0.7, 0.35), spread=0.020, wave=0.0,
             curl=0.0, width=0.040, gravity=0.26, flare=0.0, accent=False):
        """Tail from a tie on the head (ponytail, twin tail, side tail)."""
        th, s = np.radians(at[0]), at[1]
        base, nrm = self.head.scalp(th, s, 0.010 * self.k)
        d = _unit(np.asarray(direction, np.float64))
        side = _unit(np.cross(d, nrm))
        up = _unit(np.cross(side, d))
        made = []
        for i in range(n):
            a = 2 * np.pi * i / n
            off = (side * np.cos(a) + up * np.sin(a)) * spread * self.k
            dd = _unit(d + off * 6.0 / self.k)
            lk = self.lock(th, s - 0.02, s, free=free * self._jit(0.07) * (1.0 - 0.12 * (i % 2)),
                           loft=(0.008, 0.012), width=width, thick=0.34, gravity=gravity, wave=wave,
                           curl=curl, direction=dd, flare=flare, kind="long", n_scalp=2, sector=th + 0.001 * i)
            lk.p[: lk.free_from] += off[None] * 0.5
            lk.d0 = 0.16
            lk.accent = self._is_accent(accent, i)
            made.append(lk)
        self.ties.append((base + d * 0.028 * self.k, d, (spread * 0.7 + 0.015) * self.k))
        return base, made

    def braid(self, at=(180.0, 0.62), free=0.40, direction=(0.0, 0.4, -0.8), width=0.036, bead=0.030, gravity=0.34,
              flare=0.0, forward=0.0, tuft=0.05, accent=False):
        """Plait hanging from a tie on the head: one round lock modelled as a string of beads, ending in a
        loose tuft (the last `tuft` metres, below a second tie)."""
        th, s = np.radians(at[0]), at[1]
        base, nrm = self.head.scalp(th, s, 0.010 * self.k)
        d = _unit(np.asarray(direction, np.float64))
        lk = self.lock(th, s - 0.02, s, free=free + tuft, loft=(0.008, 0.012), width=width, thick=0.5, gravity=gravity,
                       direction=d, flare=flare, forward=forward, kind="long", n_scalp=2, sector=th)
        lk.d0 = 0.16
        lk.braid = bead * self.k
        lk.accent = self._is_accent(accent, 0)
        lk.tuft = tuft * self.k
        if tuft:
            L = lk.arc[-1] - tuft * self.k
            end = np.array([np.interp(L, lk.arc, lk.p[:, c]) for c in range(3)])
            self.ties.append((end, _unit(lk.p[-1] - lk.p[-2]), width * 0.40 * self.k))
        self.ties.append((base + d * 0.010 * self.k, d, width * 0.52 * self.k))
        return base, lk

    def bun(self, mat, at=(180.0, 0.24), r=0.040, flat=0.78, turns=1.4, accent=False):
        """Wound bun sitting on the scalp."""
        th, s = np.radians(at[0]), at[1]
        k = self.k
        base, n = self.head.scalp(th, s, 0.004 * k)
        n = _unit(n)
        a = _unit(np.cross(n, (0.0, 0.0, 1.0)) if abs(n[2]) < 0.95 else np.cross(n, (1.0, 0.0, 0.0)))
        b = np.cross(n, a)
        cen = base + n * r * k * flat * 0.62
        lat = np.linspace(-0.5 * np.pi, 0.5 * np.pi, 13)[1:-1]
        cols = 28
        rings = []
        for la in lat:
            ph = np.linspace(0.0, 2 * np.pi, cols, endpoint=False) + turns * la
            rr = r * k * np.cos(la)
            rings.append(cen[None] + rr * (np.cos(ph)[:, None] * a + np.sin(ph)[:, None] * b)
                         + (n * r * k * flat * np.sin(la))[None])
        p = M.loft("bun", mat, np.array(rings), closed=True, cap0=True, cap1=True, outline=0.55)
        C = cols + 1
        u = np.abs(((np.arange(C) / cols * 5.0) % 1.0) - 0.5) * 2.0          # five strands wound round
        nv = len(p.v)
        p.uv[: len(lat) * C, 0] = np.tile(u, len(lat)) * TOP_U
        p.uv[len(lat) * C:, 0] = 0.5 * TOP_U
        d = np.linalg.norm(p.v - self.head.scalp(0.0, 0.0, 0.0)[0], axis=1) / k
        p.uv[:, 1] = 1.0 - np.clip(0.17 + (d - d.min()) * 0.8, 0.0, 0.999)
        p._accent = bool(accent)
        p.rigid("head").rounded(cen, 0.55)
        self.extra.append(p)
        self.ties.append((base + n * 0.004 * k, n, r * k * 0.80))
        assert nv == len(p.v)
        return cen

    def ahoge(self, free=0.07, az=0.15, accent=False):
        lk = self.lock(az, 0.02, 0.06, free=free, loft=(0.004, 0.008), width=0.014, thick=0.45, gravity=0.16,
                       direction=(0.25, -0.35, 1.0), curl=1.6, kind="short")
        lk.accent = bool(accent)


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
        pts, _ = self.head.scalp(np.broadcast_to(th, s.shape), s, loft * self.k)
        p = M.loft("hair_cap", mat, pts, closed=True, cap0=True, outline=0.0)
        d = np.linalg.norm(p.v - self.head.scalp(0.0, 0.0, 0.0)[0], axis=1) / self.k
        p.uv[:, 1] = 1.0 - np.clip(d * 1.25 / UV_LENGTH, 0.0, 0.999)
        p.uv[:, 0] = 0.5 * TOP_U                                  # the middle of a lock: no streaks on the scalp
        return p.rigid("head").rounded(self.C + (0, 0.012 * self.k, 0), 0.8)

    def _braid_part(self, lk, mat):
        """A plait: round tube whose radius pulses bead by bead while it weaves from side to side."""
        S = self.k
        step = 0.005 * S
        f0 = lk.arc[lk.free_from - 1]
        n = max(8, int((lk.arc[-1] - f0) / step))
        arc = f0 + np.linspace(0.0, 1.0, n + 1) * (lk.arc[-1] - f0)
        path = np.stack([np.interp(arc, lk.arc, lk.p[:, c]) for c in range(3)], axis=1)
        nrm = _unit(np.stack([np.interp(arc, lk.arc, lk.n[:, c]) for c in range(3)], axis=1))
        tan = _unit(np.gradient(path, axis=0))
        side = _unit(np.cross(tan, nrm))
        nrm = _unit(np.cross(side, tan))
        d = arc - f0
        L = d[-1]
        body = max(L - lk.tuft, 1e-4)
        ph = np.pi * d / lk.braid
        plait = d < body
        r = lk.width * 0.5 * np.where(plait, 0.70 + 0.30 * np.abs(np.sin(ph)), 1.0)
        r *= np.minimum(1.0, 0.55 + d / (0.03 * S))                               # slim at the tie
        t = np.clip((d - body) / max(lk.tuft, 1e-4), 0.0, 1.0)                    # the tuft: flares, then a point
        r = np.where(plait, r * (1.0 - 0.22 * M.smooth(d / body)),
                     lk.width * 0.5 * 0.78 * (0.62 + 1.1 * t) * np.clip((1.0 - t) / 0.55, 0.0, 1.0) ** 0.7)
        r = np.maximum(r, lk.width * 0.02)
        path = path + side * (np.where(plait, np.sin(ph), 0.0) * lk.width * 0.13)[:, None]
        cols = 10
        a = np.linspace(0.0, 2 * np.pi, cols, endpoint=False)
        rings = path[:, None] + r[:, None, None] * (np.cos(a)[None, :, None] * side[:, None]
                                                    + np.sin(a)[None, :, None] * nrm[:, None] * 0.82)
        cu = np.abs(np.linspace(0.0, 2.0, cols + 1) % 2.0 - 1.0) * TOP_U         # two strands round the plait
        p = M.loft("braid", mat, rings, closed=True, cap1=True, us=cu, vs=np.zeros(n + 1))
        C = cols + 1
        v = 1.0 - np.clip((lk.d0 + d / S) / UV_LENGTH, 0.0, 0.999)
        p.uv[: (n + 1) * C, 1] = np.repeat(v, C)
        p.uv[(n + 1) * C:, 1] = v[-1]
        ol = np.repeat(np.where(r > lk.width * 0.1, 0.55, 0.25), C)
        p.outline = np.concatenate([ol, np.full(len(p.v) - len(ol), 0.3)])
        p.rounded(path.mean(axis=0), 0.0)
        p._tau = np.concatenate([np.repeat(arc, C), np.full(len(p.v) - (n + 1) * C, arc[-1])])
        return p

    def _tie_part(self, mat, pos, d, r):
        """Hair tie: a small torus round a tail / plait / bun base."""
        d = _unit(np.asarray(d, np.float64))
        a = _unit(np.cross(d, (0.0, 0.0, 1.0)) if abs(d[2]) < 0.95 else np.cross(d, (1.0, 0.0, 0.0)))
        b = np.cross(d, a)
        tr = max(0.0045 * self.k, r * 0.26)
        big = np.linspace(0.0, 2 * np.pi, 15)
        small = np.linspace(0.0, 2 * np.pi, 7, endpoint=False)
        rings = []
        for t in big:
            out = a * np.cos(t) + b * np.sin(t)
            rings.append(pos[None] + out[None] * (r + tr * np.cos(small)[:, None]) + d[None] * tr * np.sin(small)[:, None])
        p = M.loft("hair_tie", mat, np.array(rings), closed=True, outline=0.5)
        p.uv[:] = (0.5, 0.5)
        return p.rounded(pos, 0.0)

    def _lock_part(self, lk, mat):
        if lk.braid:
            return self._braid_part(lk, mat)
        K = len(lk.p)
        S = self.k
        L = max(lk.arc[-1], 1e-6)
        tau = lk.arc / L
        tip_len = max(0.012 * S, min(0.40 * L, 0.085 * S) * (1.0 - lk.blunt))
        tip = np.clip((L - lk.arc) / tip_len, 0.0, 1.0) ** 0.72
        w = lk.width * np.minimum(1.0, 0.62 + tau * 1.6) * tip
        w = np.maximum(w, lk.width * 0.03)
        th = np.minimum(lk.width * lk.thick, 0.011 * S) * np.minimum(1.0, 0.45 + tau * 2.2) * (0.25 + 0.75 * tip)
        tan = _unit(np.gradient(lk.p, axis=0))
        side = _unit(np.cross(tan, lk.n))
        nrm = _unit(np.cross(side, tan))
        # five columns over the lit face, three under it; both edges are doubled so the underside can sit in
        # its own (darker) strip of the sheet without the texture sweeping across a face
        us = np.array([-1.0, -0.55, 0.0, 0.55, 1.0, 1.0, 0.5, 0.0, -0.5, -1.0])
        bulge = np.array([0.0, 0.70, 1.0, 0.70, 0.0, 0.0, -0.28, -0.40, -0.28, 0.0])
        rings = lk.p[:, None] + side[:, None] * (us[None, :, None] * w[:, None, None] * 0.5) + \
            nrm[:, None] * (bulge[None, :, None] * th[:, None, None])
        cu = np.array([0.0, 0.225, 0.5, 0.775, 1.0]) * TOP_U
        cu = np.concatenate([cu, [0.99, 0.95, 0.91, 0.87, 0.83, 0.83]])
        dist = lk.d0 + lk.arc / S
        if lk.kind == "short" and 0 < lk.free_from < K and dist[lk.free_from - 1] < BAND_END:
            # a spike leaving the scalp above the painted highlight band: the band belongs to the head's
            # silhouette, not to the middle of a free spike - its free part starts below the band
            dist[lk.free_from:] += BAND_END - dist[lk.free_from - 1]
        v = 1.0 - np.clip(dist / UV_LENGTH, 0.0, 0.999)
        p = M.loft("lock", mat, rings, closed=True, cap1=True, us=cu, vs=np.zeros(K))
        C = rings.shape[1] + 1
        p.uv[: K * C, 1] = np.repeat(v, C)
        p.uv[K * C:, 1] = v[-1]
        ol = np.repeat(0.25 + 0.50 * tip, C)
        p.outline = np.concatenate([ol, np.full(len(p.v) - len(ol), 0.3)])
        below = np.clip((self.C[2] - 0.10 * S - p.v[:, 2]) / (0.25 * S), 0.0, 1.0)
        p.rounded(self.C + (0, 0.012 * S, 0), 0.62 * (1.0 - below) + 0.12 * below)
        p._tau = np.concatenate([np.repeat(lk.arc, C), np.full(len(p.v) - K * C, lk.arc[-1])])
        return p

    def _weights_like(self, part, pos, donors):
        """Skin an accessory like the nearest vertex of the lock parts it sits on."""
        best, src = None, None
        for q in donors:
            dist = np.linalg.norm(q.v - pos, axis=1)
            i = int(np.argmin(dist))
            if best is None or dist[i] < best:
                best, src = dist[i], (q, i)
        if src is None or best > 0.03 * self.k:
            return part.rigid("head")
        q, i = src
        part.w = {b: np.full(len(part.v), float(a[i])) for b, a in q.w.items() if a[i] > 1e-4}
        return part

    def build(self, mat, key, cap=True, cap_line=(0.27, 0.50, 0.74), min_chain=0.085, tie_mat=None):
        """-> (parts, bones): hair mesh parts and the spring bones [(name, parent, head, tail)].
        tie_mat: material of the hair ties at tail / plait / bun bases (None: no ties)."""
        parts = [self.cap(mat, cap_line)] if cap else []
        parts += self.extra
        chains = self._chains(key, min_chain)
        bones = [b for ch in chains for b in ch["bones"]]
        lock_parts = []
        for lk in self.locks:
            p = self._lock_part(lk, mat)
            p._accent = lk.accent
            lock_parts.append(p)
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
        if self.split:
            for p in parts:
                p.uv[:, 0] = np.clip(p.uv[:, 0], 0.0, 1.0) * 0.484 + (0.508 if getattr(p, "_accent", False) else 0.008)
        if tie_mat:
            for pos, d, r in self.ties:
                parts.append(self._weights_like(self._tie_part(tie_mat, np.asarray(pos), d, r), np.asarray(pos),
                                                lock_parts))
        return parts, bones

    def _chains(self, key, min_chain):
        """Group the free locks into azimuth sectors; one bone chain per sector along the mean path."""
        groups = {}
        for lk in self.locks:
            if lk.free_len < min_chain * self.k or lk.kind == "fringe":
                continue
            long_ = lk.free_len >= LONG * self.k
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
def style(hair, spec, mat=None):
    """Comb a style spec (dict of sections, see the module docstring) into `hair`. mat: the hair material
    (needed for buns, which are built as parts straight away)."""
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
    for t in spec.get("braids", ()):
        ties.append(hair.braid(**t)[0])
    for t in spec.get("buns", ()):
        ties.append(hair.bun(mat, **t))
    ah = spec.get("ahoge")
    if ah:
        hair.ahoge(**(ah if isinstance(ah, dict) else dict(free=ah)))
    return ties
