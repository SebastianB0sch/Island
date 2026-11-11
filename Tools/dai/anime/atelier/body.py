"""
The atelier body: torso, neck, arms, hands and legs lofted from cross-section tables.

The same tables are the pattern blocks of the outfit (outfit.py cuts every garment as an offset of these
sections, so cloth can not intersect the body it was cut from) and the collision shape the hair is combed
over (hair.py). Only the skin an outfit leaves visible is built.

Rest pose: the cast skeleton's T-pose (skeleton.py); +X is the character's left, the front is -Y.
"""

import numpy as np

from .. import skeleton as S
from . import mesh as M

# z, half width, front depth, back depth
TORSO_F = [(0.800, 0.055, 0.050, 0.060), (0.840, 0.128, 0.078, 0.092), (0.880, 0.150, 0.086, 0.100),
           (0.930, 0.146, 0.082, 0.094), (0.985, 0.112, 0.074, 0.076), (1.040, 0.088, 0.068, 0.064),
           (1.100, 0.096, 0.076, 0.068), (1.160, 0.118, 0.090, 0.076), (1.215, 0.132, 0.104, 0.084),
           (1.270, 0.136, 0.090, 0.086), (1.330, 0.138, 0.070, 0.082), (1.375, 0.120, 0.056, 0.070),
           (1.410, 0.050, 0.042, 0.048)]
TORSO_M = [(0.800, 0.055, 0.052, 0.060), (0.840, 0.125, 0.080, 0.090), (0.880, 0.140, 0.086, 0.096),
           (0.930, 0.138, 0.084, 0.090), (0.985, 0.122, 0.080, 0.078), (1.040, 0.110, 0.078, 0.072),
           (1.100, 0.118, 0.082, 0.076), (1.160, 0.142, 0.090, 0.084), (1.215, 0.160, 0.096, 0.090),
           (1.270, 0.166, 0.092, 0.090), (1.330, 0.164, 0.074, 0.086), (1.375, 0.138, 0.058, 0.074),
           (1.410, 0.056, 0.046, 0.052)]
# x along the arm, radius
ARM = [(0.120, 0.043), (0.175, 0.042), (0.240, 0.038), (0.330, 0.034), (0.440, 0.029), (0.500, 0.031),
       (0.600, 0.026), (0.675, 0.021)]
# z, radius, centre y offset
LEG = [(0.900, 0.080, -0.004), (0.840, 0.078, -0.004), (0.750, 0.071, -0.004), (0.620, 0.060, -0.003),
       (0.500, 0.048, -0.002), (0.470, 0.046, -0.002), (0.400, 0.047, 0.003), (0.340, 0.049, 0.006),
       (0.220, 0.036, 0.004), (0.110, 0.028, 0.001), (0.085, 0.029, 0.000)]
TORSO_POWER = 2.35


class Body:
    def __init__(self, female=True, build=1.0, bust=1.0):
        self.female = female
        self.build = build
        t = np.array(TORSO_F if female else TORSO_M, np.float64)
        t[:, 1:] *= (1.0 + (build - 1.0) * np.array([1.0, 1.3, 1.1]))[None]
        if female:
            t[7:9, 2] = t[7:9, 2] + (bust - 1.0) * np.array([0.008, 0.016])
        self.t = t
        self.arm_k = (0.86 if female else 1.0) * (0.6 + 0.4 * build)
        self.leg_k = (0.86 if female else 0.97) * (0.6 + 0.4 * build)
        self.neck_r = 0.028 if female else 0.035

    # ------------------------------------------------------------------ sections
    def torso_dims(self, z):
        d = M.spline(self.t[:, [0, 1, 2, 3]], z)
        return d[..., 0], d[..., 1], d[..., 2]

    def torso_ring(self, z, ease=0.0, n=40, theta=None, front=0.0, back=0.0):
        """Loop round the torso at height z (theta = 0 at the front, growing towards the left side).
        ease: outward offset (m); front / back: extra offset on that side."""
        th = np.linspace(0.0, 2 * np.pi, n, endpoint=False) if theta is None else np.asarray(theta, np.float64)
        a, f, b = self.torso_dims(np.asarray(z, np.float64))
        c, s = np.cos(th), np.sin(th)
        e = 2.0 / TORSO_POWER
        x = (a + ease) * np.sign(s) * np.abs(s) ** e
        y = np.where(c > 0, -(f + ease + front), (b + ease + back)) * np.abs(c) ** e
        return np.stack([x, y, np.broadcast_to(z, x.shape)], axis=-1)

    # positions garments and accessories ask for (another body - wardrobe.VBody - answers from its own shape)
    def front_y(self, z, x=0.0):
        """y of the chest / belly surface at height z, x off the centre line."""
        a, f, _ = self.torso_dims(np.array(z, np.float64))
        return -float(f) * max(0.0, 1.0 - abs(x / float(a)) ** TORSO_POWER) ** (1.0 / TORSO_POWER)

    def side_x(self, z):
        return float(self.torso_dims(np.array(z, np.float64))[0])

    def centre_y(self, z):
        return 0.0

    def neck_c(self, z):
        """y of the neck's centre line at height z (the neck leans forward)."""
        return 0.004 - (z - 1.375) * 0.07

    def arm_radius(self, x):
        return M.spline(ARM, np.abs(x)) * self.arm_k

    def arm_ring(self, x, ease=0.0, n=14, side=1.0, squash=1.0):
        """Loop round the arm at |x| (left: side = 1)."""
        cap = min(1.0, max(0.0, (abs(x) - 0.085) / 0.090)) ** 0.5       # rounded shoulder cap towards the neck
        r = (self.arm_radius(x) + ease) * max(cap, 0.12)
        drop = 0.024 * (1.0 - float(M.smooth((abs(x) - 0.15) / 0.13)))     # the shoulder slopes below the joint
        return M.ring((side * x, 0.0, S.SHOULDER - drop), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0), r, r * squash, n)

    def leg_dims(self, z):
        d = M.spline(LEG[::-1], z)
        return d[..., 0] * self.leg_k, d[..., 1]

    def leg_ring(self, z, ease=0.0, n=16, side=1.0, wide=1.0):
        r, cy = self.leg_dims(np.asarray(z, np.float64))
        return M.ring((side * S.HIP_X, cy, z), (1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (r * 0.96 + ease) * wide,
                      r * 1.03 + ease, n)

    def push_out(self, p, margin=0.012):
        """Move points (K, 3) out of the torso / neck (hair combing)."""
        p = np.array(p, np.float64)
        z = np.clip(p[:, 2], 0.82, 1.405)
        a, f, b = self.torso_dims(z)
        inside_z = (p[:, 2] < 1.43)
        d = np.where(p[:, 1] < 0, f, b) + margin
        q = np.hypot(p[:, 0] / (a + margin), p[:, 1] / d)
        k = np.where(inside_z & (q < 1.0), 1.0 / np.maximum(q, 0.05), 1.0)
        p[:, 0] *= k
        p[:, 1] *= k
        # neck column
        nz = (p[:, 2] >= 1.40) & (p[:, 2] < 1.50)
        r = np.hypot(p[:, 0], p[:, 1])
        k = np.where(nz & (r < self.neck_r + margin), (self.neck_r + margin) / np.maximum(r, 1e-4), 1.0)
        p[:, 0] *= k
        p[:, 1] *= k
        return p

    # ------------------------------------------------------------------ skin parts
    def torso(self, mat, z0, z1, rings=None):
        n = rings or max(4, int((z1 - z0) / 0.016))
        zs = np.linspace(z0, z1, n)
        pts = np.array([self.torso_ring(z) for z in zs])
        return M.loft("torso", mat, pts, closed=True, outline=0.8).weights(M.w_torso)

    def neck(self, mat):
        zs = np.linspace(1.375, 1.515, 8)
        r = self.neck_r * (1.0 + 0.25 * M.smooth((1.41 - zs) / 0.035))
        path = np.stack([np.zeros_like(zs), 0.006 - (zs - 1.375) * 0.07, zs], axis=1)
        return M.tube("neck", mat, path, r, n=18, up=(0, -1, 0), cap0=False, cap1=False,
                      outline=0.6).weights(M.w_spine)

    def arm(self, mat, side, x0=0.09, x1=S.WRIST_X):
        s = 1.0 if side == "l" else -1.0
        xs = np.linspace(x0, x1, max(4, int((x1 - x0) / 0.022)))
        pts = np.array([self.arm_ring(x, side=s) for x in xs])
        return M.loft(f"arm_{side}", mat, pts, closed=True, cap0=True, outline=0.8).weights(M.w_arm(side))

    def hand(self, mat, side, scale=None):
        k = scale or (0.88 if self.female else 1.0)
        px = np.array([0.668, 0.690, 0.715, 0.742, 0.764, 0.772])
        hw = np.array([0.0210, 0.0300, 0.0375, 0.0395, 0.0380, 0.0330]) * k
        ht = np.array([0.0190, 0.0150, 0.0125, 0.0115, 0.0105, 0.0085]) * k
        z = S.SHOULDER
        palm = M.loft("palm", mat, np.array([M.ring((x, 0.0, z), (0, -1, 0), (0, 0, 1), w, t, 16, power=3.0)
                                             for x, w, t in zip(px, hw, ht)]), closed=True, cap1=True, outline=0.7)
        parts = [palm]
        ys = np.array([-0.0275, -0.0092, 0.0090, 0.0265]) * k
        lens = np.array([0.066, 0.074, 0.068, 0.053]) * k
        for y, ln in zip(ys, lens):
            ang = np.radians([4.0, 14.0, 30.0, 44.0])
            seg = ln / 3.0
            p = [np.array([0.760, y, z - 0.001])]
            for a0, a1 in zip(ang, ang[1:]):
                am = 0.5 * (a0 + a1)
                p.append(p[-1] + seg * np.array([np.cos(am), 0.0, -np.sin(am)]))
            path = M.spline(np.column_stack([np.arange(4), np.array(p)]), np.linspace(0, 3, 9))
            r = np.linspace(0.0083, 0.0060, 9) * k
            r[-1] *= 0.7
            parts.append(M.tube("finger", mat, path, r, n=8, up=(0, -1, 0), cap0=False, outline=0.55))
        d = np.array([0.50, -0.80, -0.34])
        d /= np.linalg.norm(d)
        t = np.linspace(0, 1, 7)[:, None]
        path = np.array([0.700, -0.030 * k, z - 0.006]) + d * t * 0.056 * k + np.array([0.012, 0, 0]) * t * t
        r = np.linspace(0.0105, 0.0072, 7) * k
        r[-1] *= 0.7
        parts.append(M.tube("thumb", mat, path, r, n=8, up=(0, 0, 1), cap0=False, outline=0.55))
        hand = M.merge(f"hand_{side}", parts, mat)
        hand.w = M.w_arm("l", shoulder=False)(hand.v)
        tot = sum(hand.w.values())
        hand.w = {b: a / tot for b, a in hand.w.items() if a.max() > 1e-4}
        return hand if side == "l" else hand.mirrored(f"hand_{side}")

    def leg(self, mat, side, z0=S.ANKLE, z1=0.90):
        s = 1.0 if side == "l" else -1.0
        zs = np.linspace(z1, z0, max(4, int((z1 - z0) / 0.024)))
        pts = np.array([self.leg_ring(z, side=s) for z in zs])
        return M.loft(f"leg_{side}", mat, pts, closed=True, outline=0.8).weights(M.w_leg(side))
