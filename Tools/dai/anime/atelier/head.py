"""
The atelier head.

The skull is a loft of tilted superellipse rings: level through the cranium, tipping forward through the
lower face so the jaw line rises from the chin to the ear the way an anime face does. Each ring has a
half width, a front and a back depth, so the front silhouette (cheek -> chin) and the profile are edited
independently (SHAPE keys; per-design overrides scale them).

The eyes are painted (paint.face) on a front projection of this surface. Everything that has to move is
geometry laid onto the surface in the same frame:

  lids     skin patches tucked inside the head under the upper / lower lid; morphs slide them out over
           the painted eye (Blink, Blink_L/R, EyeJoy, the half-closed Angry / Sorrow lids)
  brows    thin strips above the eyes (BrowAngry, BrowSorrow, Surprised)
  mouth    two lip-line strips lying on each other at rest (the anime mouth line) that open into a
           shape, with an interior that comes forward from inside the head (A I U E O, Joy ...)

Morph names are the ones the runtime drives (Tools/dai/anime/models.FACE_MORPHS).
"""

import numpy as np

from .. import skeleton as S
from . import mesh as M
from . import paint as P

C = np.array(S.HEAD_CENTER, np.float64)

# ring keys below the cranium: s, centre height, tilt, half width, front depth, back depth, power
LOWER = [
    (0.40, 0.025, 0.00, 0.0840, 0.0930, 0.0950, 2.20),
    (0.50, -0.008, 0.03, 0.0865, 0.0935, 0.0930, 2.35),
    (0.60, -0.036, 0.10, 0.0830, 0.0925, 0.0860, 2.40),
    (0.69, -0.052, 0.18, 0.0700, 0.0890, 0.0740, 2.20),
    (0.78, -0.066, 0.30, 0.0490, 0.0830, 0.0580, 1.85),
    (0.85, -0.073, 0.34, 0.0290, 0.0740, 0.0440, 1.70),
    (0.92, -0.076, 0.28, 0.0240, 0.0500, 0.0400, 2.00),
    (1.00, -0.080, 0.00, 0.0200, 0.0300, 0.0350, 2.00),
]
MOUTH_Z = -0.0635
BROW_Z = 0.0125

# mouth shapes: width scale, upper lip rise, lower lip drop, corner lift, roundness
MOUTHS = {
    "A": (0.85, 0.0022, 0.0100, 0.0000, 1.0), "I": (1.20, 0.0012, 0.0026, 0.0008, 0.6),
    "U": (0.45, 0.0016, 0.0034, 0.0000, 1.2), "E": (1.05, 0.0016, 0.0058, 0.0004, 0.7),
    "O": (0.60, 0.0032, 0.0078, 0.0000, 1.3),
    "Joy": (1.20, 0.0006, 0.0072, 0.0030, 0.55), "Fun": (1.15, 0.0, 0.0, 0.0030, 1.0),
    "Angry": (0.90, 0.0, 0.0, -0.0022, 1.0), "Sorrow": (0.82, 0.0, 0.0, -0.0024, 1.0),
    "Surprised": (0.50, 0.0022, 0.0052, 0.0, 1.3),
}


class Head:
    def __init__(self, shape=None, eyes=None):
        """shape: {jaw, chin, cheek, face_w, face_d, cranium}: multipliers / offsets on the base rings."""
        sh = dict(jaw=1.0, chin=0.0, cheek=1.0, face_w=1.0, cranium=1.0)
        sh.update(shape or {})
        self.shape = sh
        self.eye = P.eye_spec(eyes)
        keys = np.array(LOWER, np.float64)
        keys[:, 3] *= sh["face_w"]
        keys[2, 3] *= sh["cheek"]
        keys[3:6, 3] *= sh["jaw"]
        keys[4:7, 1] -= sh["chin"]
        self.keys = keys

    # ------------------------------------------------------------------ surface
    def _ring(self, s):
        s = np.asarray(s, np.float64)
        k = self.keys
        top = s < 0.40
        phi = np.clip(s / 0.40, 0.0, 1.0) * (np.pi / 2)
        sp = np.sin(phi) ** 0.82
        cr = self.shape["cranium"]
        low = M.spline(k, np.maximum(s, 0.40))
        zc = np.where(top, k[0, 1] + 0.088 * cr * np.cos(phi), low[..., 0])
        tau = np.where(top, 0.0, low[..., 1])
        a = np.where(top, np.maximum(k[0, 3] * sp, 1e-4), low[..., 2])
        f = np.where(top, np.maximum(k[0, 4] * sp, 1e-4), low[..., 3])
        b = np.where(top, np.maximum(k[0, 5] * sp * cr, 1e-4), low[..., 4])
        n = np.where(top, 2.0 + 0.2 * (s / 0.40), low[..., 5])
        return zc, tau, a, f, b, n

    def point(self, theta, s, sculpt=True):
        """Surface point (head-centre frame; front = -y) at angle theta (0 = front) and ring s (0 crown .. 1)."""
        theta, s = np.broadcast_arrays(np.asarray(theta, np.float64), np.asarray(s, np.float64))
        zc, tau, a, f, b, n = self._ring(s)
        c, sn = np.cos(theta), np.sin(theta)
        e = 2.0 / n
        x = a * np.sign(sn) * np.abs(sn) ** e
        yr = np.where(c > 0, -f, b) * np.abs(c) ** e
        z = zc + tau * yr
        p = np.stack([x, yr, z], axis=-1)
        if sculpt:
            p[..., 1] -= self._sculpt(x, z) * M.smooth(c * 2.5)
        return p

    def _sculpt(self, x, z):
        """Forward displacement of the face: nose, eye sockets, cheeks, lips."""
        ax = np.abs(x)
        nose = np.exp(-(x / 0.0080) ** 2) * (0.0040 * np.exp(-((z + 0.026) / 0.018) ** 2)
                                             + 0.0100 * np.exp(-((z + 0.0450) / 0.0080) ** 2))
        socket = -0.0030 * np.exp(-((ax - 0.034) / 0.022) ** 2 - ((z + 0.012) / 0.016) ** 2)
        cheek = 0.0022 * np.exp(-((ax - 0.040) / 0.020) ** 2 - ((z + 0.042) / 0.016) ** 2)
        lips = 0.0016 * np.exp(-(x / 0.014) ** 2 - ((z - MOUTH_Z) / 0.006) ** 2)
        return nose + socket + cheek + lips

    def project(self, x, z, lift=0.0):
        """Points of the front surface at face coordinates (x, z), lifted along the normal."""
        x, z = np.broadcast_arrays(np.asarray(x, np.float64), np.asarray(z, np.float64))
        shp = x.shape
        x, z = x.ravel(), z.ravel()
        ss = np.linspace(0.02, 0.92, 240)
        zf = self.point(np.zeros_like(ss), ss, sculpt=False)[:, 2]
        s = np.interp(-z, -zf, ss)
        th = np.arcsin(np.clip(x / np.maximum(self._ring(s)[2], 1e-6), -0.95, 0.95))
        h = 1e-4
        for _ in range(14):
            p = self.point(th, s, sculpt=False)
            r = np.stack([p[:, 0] - x, p[:, 2] - z], axis=1)
            dt = (self.point(th + h, s, sculpt=False) - p) / h
            ds = (self.point(th, s + h, sculpt=False) - p) / h
            det = dt[:, 0] * ds[:, 2] - ds[:, 0] * dt[:, 2]
            det = np.where(np.abs(det) < 1e-12, 1e-12, det)
            th = np.clip(th - 0.8 * (r[:, 0] * ds[:, 2] - ds[:, 0] * r[:, 1]) / det, -1.5, 1.5)
            s = np.clip(s - 0.8 * (dt[:, 0] * r[:, 1] - r[:, 0] * dt[:, 2]) / det, 0.01, 0.95)
        p = self.point(th, s)
        if lift:
            dt = self.point(th + h, s) - p
            ds = self.point(th, s + h) - p
            n = np.cross(ds, dt)
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
            n[n[:, 1] > 0] *= -1.0
            p = p + n * np.broadcast_to(np.asarray(lift, np.float64), shp).ravel()[:, None]
        return (p + C).reshape(shp + (3,))

    def scalp(self, theta, s, loft=0.0):
        """World-space scalp point pushed out along the (approximate) normal - the hair rides on this."""
        p = self.point(theta, s, sculpt=False)
        h = 1e-3
        dt = self.point(theta + h, s, sculpt=False) - p
        ds = self.point(theta, np.asarray(s) + h, sculpt=False) - p
        n = np.cross(dt, ds)
        ln = np.linalg.norm(n, axis=-1, keepdims=True)
        rad = p - np.array([0.0, 0.004, 0.02])
        rad /= np.maximum(np.linalg.norm(rad, axis=-1, keepdims=True), 1e-9)
        n = np.where(ln > 1e-9, n / np.maximum(ln, 1e-12), rad)
        n = np.where((n * rad).sum(-1, keepdims=True) < 0, -n, n)
        n = n * 0.5 + rad * 0.5
        n /= np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-9)
        return p + C + n * np.asarray(loft, np.float64)[..., None], n

    # ------------------------------------------------------------------ parts
    def uv(self, pts, back=None, a=None):
        """Front-projection UVs; back-facing vertices clamp to the silhouette (skin)."""
        rel = pts - C
        x = rel[:, 0]
        if back is not None:
            x = np.where(back, np.sign(x) * a, x)
        u = 0.5 + x / P.FACE_W
        v = (rel[:, 2] + P.FACE_Z0) / P.FACE_W
        return np.stack([np.clip(u, 0.085, 0.915), np.clip(v, 0.004, 0.996)], axis=1)

    def skull(self, mat, cols=88, rings=64):
        th = np.linspace(0.0, 2 * np.pi, cols, endpoint=False)
        # denser rings through the face
        s = np.concatenate([np.linspace(0.012, 0.36, rings // 4, endpoint=False),
                            np.linspace(0.36, 0.90, rings - rings // 4 - 4, endpoint=False),
                            np.linspace(0.90, 1.0, 4)])
        TH, SS = np.meshgrid(th, s)
        pts = self.point(TH, SS) + C
        part = M.loft("head", mat, pts, closed=True, cap0=True, outline=0.55)
        n = len(part.v)
        cth = np.concatenate([np.cos(np.concatenate([TH, TH[:, :1]], axis=1)).ravel(), np.ones(n)])[:n]
        a = np.concatenate([np.repeat(self._ring(s)[2], cols + 1), np.zeros(n)])[:n]
        part.uv = self.uv(part.v, cth < 0.0, a)
        part.rigid("head").rounded(C + (0.0, 0.012, -0.012), 0.72)
        # Surprised: the eyes open wider (the painted eye stretches with the surface)
        rel = part.v - C
        e = self.eye
        fall = np.exp(-((np.abs(rel[:, 0]) - e["cx"]) / 0.024) ** 2 - ((rel[:, 2] - e["cz"]) / 0.020) ** 2)
        d = np.zeros_like(part.v)
        d[:, 2] = (rel[:, 2] - e["cz"]) * 0.14 * fall * (rel[:, 1] < 0)
        part.morph("Surprised", d)
        return part

    def ears(self, mat):
        out = []
        zc, tau, a, f, b, n = self._ring(np.array(0.545))
        for sx in (1.0, -1.0):
            cen = C + (sx * (a - 0.004), 0.014, zc - 0.004)
            out_dir = np.array([sx * 0.85, 0.52, 0.0])
            rings = []
            for k, r in ((0.0, 1.0), (0.45, 0.96), (0.85, 0.74), (1.0, 0.40)):
                rings.append(M.ring(cen + out_dir * 0.014 * k, (-sx * 0.52, 0.85, 0.0), (0, 0.12, 1.0),
                                    0.0115 * r, 0.0215 * r, 14))
            p = M.loft("ear", mat, np.array(rings), closed=True, cap1=True, outline=0.6)
            p.uv[:] = (P.SWATCH_U, P.SWATCH_V["skin"])
            out.append(p.rigid("head").rounded(C, 0.6))
        return out

    def _swatch(self, part, name):
        part.uv[:] = (P.SWATCH_U, P.SWATCH_V[name])
        return part

    def lids(self, mat):
        """Upper / lower lid patches per eye with their morph targets."""
        e = self.eye
        hw = e["hw"]
        t = np.linspace(-1.12, 1.0 + e["wing"] + 0.10, 15)
        tc = np.clip(t, -1.0, 1.0)
        up, lo = P.lids(e, t)
        top = P.lash_top(e, t) + 0.0016
        ends = M.smooth((t + 1.12) / 0.14) * M.smooth((1.0 + e["wing"] + 0.10 - t) / 0.2)
        arc = lo + (up - lo) * (0.30 + 0.25 * (1.0 - tc * tc))          # ^_^ line
        parts = []
        for sx, tag in ((1.0, "L"), (-1.0, "R")):
            x = sx * (e["cx"] + t * hw)

            def rows(z_top, z_bot, n, lift):
                r = np.linspace(0.0, 1.0, n)[:, None]
                z = e["cz"] + z_top[None] + (z_bot - z_top)[None] * r
                return self.project(np.broadcast_to(x, z.shape), z, lift)

            def patch(name, swatch, n, rest, targets):
                p = self._swatch(M.grid(name, mat, rest, outline=0.0), swatch)
                p.rigid("head").rounded(C + (0.0, 0.012, -0.012), 0.72)
                for morph, tgt in targets.items():
                    p.morph(morph, (tgt - rest).reshape(-1, 3))
                return p

            hidden_up = lambda n: rows(up + 0.0030, up + 0.0022, n, -0.0045)        # noqa: E731
            hidden_lo = lambda n: rows(lo - 0.0022, lo - 0.0030, n, -0.0045)        # noqa: E731
            lash_h = 0.0011 * ends + 1e-5

            def closed(bottom, n, lift=0.0007):
                return rows(top, np.minimum(bottom + lash_h, top - 1e-5), n, lift)

            def rim(bottom, n, lift=0.0009):
                return rows(np.minimum(bottom + lash_h, top - 1e-5), bottom, n, lift)

            half = lambda k: up - (up - lo) * k * ends                              # noqa: E731
            blink = lo - 0.0004
            tg_skin = {"Blink": closed(blink, 6), f"Blink_{tag}": closed(blink, 6), "EyeJoy": closed(arc, 6),
                       "Joy": closed(arc, 6), "Fun": closed(half(0.38), 6), "Angry": closed(half(0.30), 6),
                       "Sorrow": closed(half(0.34), 6)}
            tg_rim = {"Blink": rim(blink, 2), f"Blink_{tag}": rim(blink, 2), "EyeJoy": rim(arc, 2),
                      "Joy": rim(arc, 2), "Fun": rim(half(0.38), 2), "Angry": rim(half(0.30), 2),
                      "Sorrow": rim(half(0.34), 2)}
            parts.append(patch(f"lid_{tag}", "skin", 6, hidden_up(6), tg_skin))
            parts.append(patch(f"lidlash_{tag}", "lash", 2, hidden_up(2), tg_rim))
            low_t = rows(arc - 0.0002, lo - 0.0035, 4, 0.0006)
            parts.append(patch(f"lowlid_{tag}", "skin", 4, hidden_lo(4), {"EyeJoy": low_t, "Joy": low_t}))
        return parts

    def brows(self, mat, spec=None):
        """Brow strips. spec: {z, len, thick, arch, angle (deg, inner end down = stern)}."""
        b = dict(z=BROW_Z, len=0.034, thick=0.0026, arch=0.0030, angle=0.0, x=None)
        b.update(spec or {})
        e = self.eye
        cx = b["x"] if b["x"] is not None else e["cx"] + 0.001
        t = np.linspace(-1.0, 1.0, 11)
        ang = np.radians(b["angle"])
        parts = []
        for sx, tag in ((1.0, "L"), (-1.0, "R")):
            def strip(dz_inner=0.0, dz_outer=0.0, dz=0.0):
                mid = b["z"] + e["cz"] + e["h"] * e["upper"] + b["arch"] * (1 - t * t) + np.tan(ang) * t * b["len"] * 0.5
                mid = mid + dz + dz_inner * (1 - t) * 0.5 + dz_outer * (1 + t) * 0.5
                th = b["thick"] * (0.45 + 0.55 * M.smooth((1.0 - t) / 1.3)) * M.smooth((t + 1.0) / 0.12 + 0.3)
                z = np.stack([mid + th * 0.5, mid - th * 0.5])
                x = np.broadcast_to(sx * (cx + t * b["len"] * 0.5), z.shape)
                return self.project(x, z, 0.0009)
            rest = strip()
            p = self._swatch(M.grid(f"brow_{tag}", mat, rest), "brow").rigid("head")
            p.rounded(C + (0.0, 0.012, -0.012), 0.72)
            for morph, kw in (("BrowAngry", dict(dz_inner=-0.0042, dz_outer=0.0020)),
                              ("Angry", dict(dz_inner=-0.0042, dz_outer=0.0020)),
                              ("BrowSorrow", dict(dz_inner=0.0040, dz_outer=-0.0024)),
                              ("Sorrow", dict(dz_inner=0.0040, dz_outer=-0.0024)),
                              ("Surprised", dict(dz=0.0045)), ("Joy", dict(dz=0.0016)), ("Fun", dict(dz=0.0010))):
                p.morph(morph, (strip(**kw) - rest).reshape(-1, 3))
            parts.append(p)
        return parts

    def mouth(self, mat, spec=None):
        """Mouth line + interior. spec: {w (half width), smile (corner lift at rest), z}."""
        m = dict(w=0.0115, smile=0.0010, z=MOUTH_Z, thick=0.00055)
        m.update(spec or {})
        t = np.linspace(-1.0, 1.0, 15)
        taper = (1.0 - t * t) ** 0.6

        def curve(ws=1.0, up=0.0, down=0.0, lift=0.0, rnd=1.0):
            shape = (1.0 - np.abs(t) ** (2.0 / max(rnd, 0.2))) ** max(rnd, 0.2) if rnd != 1.0 else (1.0 - t * t)
            shape = np.clip(shape, 0.0, 1.0)
            mid = m["z"] + (m["smile"] + lift) * t * t - 0.0004 * (1 - t * t) * (lift > 0)
            return t * m["w"] * ws, mid + up * shape, mid - down * shape

        def build(ws=1.0, up=0.0, down=0.0, lift=0.0, rnd=1.0, opened=False):
            x, zu, zl = curve(ws, up, down, lift, rnd)
            th = m["thick"] * taper + 2e-5
            upper = self.project(np.stack([x, x]), np.stack([zu + th, zu]), 0.0010)
            lower = self.project(np.stack([x, x]), np.stack([zl, zl - th]), 0.0010)
            r = np.linspace(0.0, 1.0, 5)[:, None]
            if opened:
                fill = self.project(np.broadcast_to(x, (5, len(t))), zu[None] + (zl - zu)[None] * r, 0.0006)
            else:
                zz = zu[None] - 0.0002 * r * taper[None]
                fill = self.project(np.broadcast_to(x * 0.8, (5, len(t))), zz, -0.0040)
            return upper, lower, fill

        ru, rl, rf = build()
        up = self._swatch(M.grid("lip_up", mat, ru), "line").rigid("head")
        lo = self._swatch(M.grid("lip_lo", mat, rl), "line").rigid("head")
        fill = M.grid("mouth_in", mat, rf).rigid("head")
        v = np.linspace(P.SWATCH_V["teeth"] + 0.03, P.SWATCH_V["tongue"] - 0.03, 5)
        fill.uv[:, 0] = P.SWATCH_U
        fill.uv[:, 1] = np.repeat(v, len(t))
        for name, (ws, u, d, lift, rnd) in MOUTHS.items():
            tu, tl, tf = build(ws, u, d, lift, rnd, opened=(u + d) > 1e-6)
            up.morph(name, (tu - ru).reshape(-1, 3))
            lo.morph(name, (tl - rl).reshape(-1, 3))
            if (u + d) > 1e-6:
                fill.morph(name, (tf - rf).reshape(-1, 3))
        for p in (up, lo, fill):
            p.rounded(C + (0.0, 0.012, -0.012), 0.72)
        return [up, lo, fill]

    def build(self, mat, brows=None, mouth=None):
        return [self.skull(mat)] + self.ears(mat) + self.lids(mat) + self.brows(mat, brows) + self.mouth(mat, mouth)


def bake_expression(parts, expression):
    """Mix morphs into the rest shape ({"Fun": 0.4, "BrowAngry": 0.3}): a design's resting expression.
    The morph targets stay relative offsets, so a blink on a smile is still a smile."""
    for p in parts:
        for name, w in (expression or {}).items():
            if name in p.morphs:
                p.v = p.v + p.morphs[name] * w
    return parts
