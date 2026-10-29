"""
Anime hair: a scalp cap plus tapered "locks" (bezier clumps, fat at the root, pointed at the tip),
the way anime characters are built in 3D games. Every style is a short list of locks placed in
head-relative spherical coordinates: az = degrees around the head (0 = face/-Y, +90 = the
character's left/+X, 180 = back), el = degrees up from the head centre, k = distance from the
head centre in head radii.

Locks below the neck (long hair) are skinned to the upper spine so they follow the body
(see build.py: the hair builder tags them).
"""

import math

from mathutils import Vector

from ..geo import MeshBuilder
from . import head as H
from . import skeleton as S

R = S.HEAD_RADIUS
C = Vector(S.HEAD_CENTER)
VOLUME = 1.25          # spike length multiplier (anime hair is big)
HW, HH = 0.95, 1.14    # the skull is an oval (head.py: width 0.92, height 1.12) - the hair follows it


def _dir(az, el):
    a, e = math.radians(az), math.radians(el)
    return Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))


def P(az, el, k=1.0):
    """Point around the head (head-relative spherical coordinates)."""
    d = _dir(az, el)
    return C + Vector((d.x * R * k * HW, d.y * R * k, d.z * R * k * HH))


def Z(z):
    """Long-hair tip heights are written on a 0.53 m pelvis / 0.80 m shoulder scale; map them onto the
    skeleton (pelvis -> S.PELVIS, shoulders -> S.SHOULDER)."""
    return S.PELVIS + (z - 0.53) * (S.SHOULDER - S.PELVIS) / 0.27


def F(fx, fz, out=0.016):
    """Point in front of the face at face-texture coordinates (fx, fz), `out` metres off the skin."""
    return H.face_surface(fx, fz, lift=out)


class Hair:
    def __init__(self, main, second=None, shape=None):
        self.mb = MeshBuilder("Hair")
        self.low = MeshBuilder("HairLong")       # locks reaching below the neck
        self.main = main
        self.second = second or main
        self.shape = shape or {}

    # ------------------------------------------------------------------ primitives
    def cap(self, bulk=1.07, top=1.08, front_el=26.0, side_el=-12.0, back_el=-48.0, mat=None, seg=28, rings=18,
            spiky_edge=0.0, front_mat=None, front_az=55.0, front_top=70.0):
        """Scalp shell above the hairline (front_el at the forehead, back_el at the nape). front_mat colours
        the front of the cap (|az| < front_az, below front_top elevation) for two-tone styles."""
        mat = mat or self.main
        rows = []
        els = [-90 + 180 * j / rings for j in range(rings + 1)]
        for el in els:
            row = []
            for i in range(seg):
                az = 360.0 * i / seg
                d = _dir(az, el)
                k = bulk * (1.0 + (top - 1.0) * max(0.0, d.z) ** 1.5)
                p = C + Vector((d.x * R * k * HW, d.y * R * k * 1.02, d.z * R * k * HH))
                row.append((p, az, el))
            rows.append(row)

        def line(az):
            c = math.cos(math.radians(az))
            base = front_el + (back_el - front_el) * (1 - c) / 2
            side = (1 - abs(c)) * (side_el - (front_el + back_el) / 2)
            return base + side * 0.6

        for j in range(rings):
            for i in range(seg):
                i2 = (i + 1) % seg
                corners = [rows[j][i], rows[j][i2], rows[j + 1][i2], rows[j + 1][i]]
                lo = min(c[2] for c in corners)
                lim = line(corners[0][1])
                if spiky_edge and i % 2:
                    lim -= spiky_edge
                if lo < lim:
                    continue
                az_c = corners[0][1] + 180.0 / seg
                az_c = az_c - 360.0 if az_c > 180.0 else az_c
                front = front_mat and abs(az_c) < front_az and max(c[2] for c in corners) < front_top
                self.mb.poly([tuple(c[0]) for c in corners], front_mat if front else mat, smooth=True)
        # crown cap
        top_p = C + Vector((0, 0, R * bulk * top * HH))
        for i in range(seg):
            i2 = (i + 1) % seg
            self.mb.poly([tuple(rows[-2][i][0]), tuple(rows[-2][i2][0]), tuple(top_p)], mat, smooth=True)

    def lock(self, root, tip, width, thick=None, mat=None, bulge=0.25, n=8, seg=6, twist=0.0, curl=None,
             long=False, taper=0.9):
        """Tapered clump from root to tip. bulge pushes the middle away from the head centre (so locks arc over
        the skull); curl adds a sideways hook near the tip (vector, metres)."""
        mat = mat or self.main
        thick = thick if thick is not None else width * 0.45
        root, tip = Vector(root), Vector(tip)
        mid = (root + tip) * 0.5
        out = (mid - C)
        out = out.normalized() if out.length > 1e-6 else Vector((0, 0, 1))
        ctrl = mid + out * R * bulge
        pts = []
        for i in range(n + 1):
            t = i / n
            p = root * (1 - t) ** 2 + ctrl * 2 * (1 - t) * t + tip * t * t
            if curl is not None:
                p = p + Vector(curl) * (t ** 2.5)
            pts.append(p)
        rows = []
        prev_w = None
        for i, p in enumerate(pts[:-1]):
            t = i / n
            tan = (pts[i + 1] - pts[max(i - 1, 0)]).normalized()
            o = p - C
            o = (o - tan * o.dot(tan))
            o = o.normalized() if o.length > 1e-6 else Vector((0, 0, 1))
            wdir = tan.cross(o).normalized()
            if prev_w is not None and wdir.dot(prev_w) < 0:
                wdir = -wdir
            prev_w = wdir
            if twist:
                a = math.radians(twist) * t
                wdir, o = wdir * math.cos(a) + o * math.sin(a), o * math.cos(a) - wdir * math.sin(a)
            w = width * (1 - t) ** taper * (0.85 + 0.15 * math.sin(math.pi * min(1.0, t * 1.4)))
            th = thick * (1 - t) ** 0.65
            rows.append([tuple(p + wdir * math.cos(2 * math.pi * k / seg) * w + o * math.sin(2 * math.pi * k / seg) * th)
                         for k in range(seg)])
        mb = self.low if long else self.mb
        mb.grid_faces(rows, mat, smooth=True, closed_u=True)
        tip_p = tuple(pts[-1])
        last = rows[-1]
        for k in range(seg):
            mb.poly([last[k], last[(k + 1) % seg], tip_p], mat, smooth=True)
        mb.poly(list(reversed(rows[0])), mat, smooth=True)

    def spike(self, az, el, taz, tel, tk, width=0.32, thick=None, mat=None, bulge=0.12, rk=0.92, **kw):
        """Lock from the scalp at (az, el) to the point (taz, tel, tk) - widths in head radii."""
        tk = 1.0 + (tk - 1.0) * VOLUME
        self.lock(P(az, el, rk), P(taz, tel, tk), width * R, None if thick is None else thick * R, mat, bulge, **kw)

    def bang(self, az, el, fx, fz, width=0.30, out=0.014, mat=None, bulge=0.30, **kw):
        """Fringe lock from the top-front scalp down over the forehead to face point (fx, fz)."""
        self.lock(P(az, el, 0.95), F(fx, fz, out), width * R, None, mat or self.second, bulge, **kw)

    def ring(self, n, az0, az1, el, tel, tk, width, mat=None, dz=0.0, jitter=0.0, **kw):
        """n spikes spread from az0 to az1 pointing outwards (tel / tk = tip elevation / distance)."""
        for i in range(n):
            t = i / max(1, n - 1)
            az = az0 + (az1 - az0) * t
            j = jitter * math.sin(i * 2.7 + 1.3)
            self.spike(az, el, az + j * 10, tel + j * 8, tk + j * 0.1, width, mat=mat, **kw)

    def build(self):
        return self.mb, self.low


# --------------------------------------------------------------------------- styles
def jaden(h):
    """Two-tone spiky mane: dark brown top swept back, orange-brown fringe and side locks."""
    h.cap(bulk=1.10, top=1.16, front_el=30, side_el=-14, back_el=-62, front_mat=h.second, front_az=60, front_top=72)
    m, o = h.main, h.second
    # back fan (dark), pointing back and slightly up
    for az, el, tel, tk, w in ((120, 30, 32, 1.75, 0.44), (150, 40, 44, 1.95, 0.48), (180, 42, 46, 2.0, 0.50),
                               (210, 40, 44, 1.95, 0.48), (240, 30, 32, 1.75, 0.44), (180, 64, 66, 1.85, 0.46),
                               (145, 64, 64, 1.75, 0.42), (215, 64, 64, 1.75, 0.42), (90, 62, 70, 1.6, 0.36),
                               (270, 62, 70, 1.6, 0.36)):
        h.spike(az, el, az, tel, tk, w, 0.22, m, bulge=0.10)
    # lower back (dark), pointing down-back, covering the nape
    for az in (130, 155, 180, 205, 230):
        h.spike(az, 0, az + (az - 180) * 0.15, -26, 1.6, 0.44, 0.20, m, bulge=0.08)
    for az in (160, 200):
        h.spike(az, -25, az, -48, 1.35, 0.40, 0.18, m, bulge=0.06)
    # upper sides (dark) flaring out
    for s in (-1, 1):
        h.spike(s * 100, 35, s * 114, 34, 1.7, 0.42, 0.20, m)
        h.spike(s * 72, 58, s * 80, 64, 1.55, 0.36, 0.18, m)
    # front: rising forelock + fringe (orange)
    h.spike(0, 64, 4, 74, 1.62, 0.46, 0.22, o, bulge=0.15)
    h.spike(-30, 60, -38, 68, 1.5, 0.40, 0.20, o, bulge=0.12)
    h.spike(30, 60, 38, 68, 1.5, 0.40, 0.20, o, bulge=0.12)
    for az, fx, fz, w in ((-42, -0.54, 0.20, 0.36), (-20, -0.26, 0.12, 0.36), (2, 0.02, 0.04, 0.36),
                          (22, 0.29, 0.12, 0.36), (44, 0.57, 0.20, 0.36)):
        h.bang(az, 55, fx, fz, w, mat=o)
    # side locks in front of the ears, down to the cheeks (orange) and a lower side spike
    for s in (-1, 1):
        h.lock(P(s * 72, 25, 0.95), F(s * 0.86, -0.52, 0.016), 0.32 * R, 0.15 * R, o, bulge=0.2)
        h.spike(s * 110, 5, s * 122, -20, 1.6, 0.40, 0.18, o, bulge=0.08)


def syrus(h):
    """Light-blue rounded mop that flares out into soft spikes all around."""
    h.cap(bulk=1.12, top=1.08, front_el=32, side_el=-6, back_el=-30)
    m, o = h.main, h.second
    for i in range(12):
        az = 40 + i * 25
        h.spike(az, 0, az, -16, 1.42, 0.40, 0.17, o if i % 2 else m, bulge=0.06)
    for az in (60, 120, 180, 240, 300):
        h.spike(az, 38, az, 30, 1.38, 0.38, 0.18, m, bulge=0.08)
    h.spike(0, 70, 0, 80, 1.28, 0.30, 0.14, m)
    for az, fx, fz in ((-30, -0.42, 0.30), (-8, -0.13, 0.26), (14, 0.17, 0.26), (34, 0.45, 0.30)):
        h.bang(az, 52, fx, fz, 0.32, mat=m, bulge=0.22)
    for s in (-1, 1):
        h.spike(s * 55, 8, s * 62, -22, 1.32, 0.34, 0.15, m, bulge=0.05)


def chumley(h):
    """Short messy dark hair with a cowlick."""
    h.cap(bulk=1.06, top=1.06, front_el=34, side_el=-4, back_el=-38)
    m = h.main
    h.ring(9, 70, 290, 8, -14, 1.32, 0.30, m, jitter=0.6, bulge=0.05)
    h.ring(6, 60, 300, 40, 34, 1.32, 0.30, m, jitter=0.8, bulge=0.06)
    h.spike(10, 75, 30, 88, 1.45, 0.20, 0.10, m, curl=(0.0, 0.03, -0.02))
    for az, fx, fz in ((-22, -0.30, 0.30), (0, 0.0, 0.26), (22, 0.30, 0.30)):
        h.bang(az, 58, fx, fz, 0.28, mat=m, bulge=0.2)


def bastion(h):
    """Neat short black hair, side part, fringe swept to one side."""
    h.cap(bulk=1.05, top=1.05, front_el=30, side_el=-10, back_el=-42)
    m = h.main
    for az, fx, fz, w in ((-30, -0.05, 0.30, 0.36), (-10, 0.25, 0.22, 0.36), (10, 0.48, 0.18, 0.32),
                          (32, 0.66, 0.06, 0.28)):
        h.bang(az, 60, fx, fz, w, mat=m, bulge=0.22)
    h.ring(7, 100, 260, 10, -20, 1.24, 0.30, m, bulge=0.04)
    for s in (-1, 1):
        h.lock(P(s * 70, 22, 0.95), F(s * 0.85, -0.35, 0.02), 0.26 * R, 0.10 * R, m, bulge=0.12)


def chazz(h):
    """Black hair spiking up and sweeping back, sharp fringe, locks along the jaw."""
    h.cap(bulk=1.09, top=1.12, front_el=30, back_el=-48)
    m, o = h.main, h.second
    for az, el, taz, tel, tk, w in ((0, 64, 0, 58, 1.85, 0.46), (35, 60, 50, 52, 1.8, 0.42), (-35, 60, -50, 52, 1.8, 0.42),
                                    (90, 50, 110, 40, 1.75, 0.42), (-90, 50, -110, 40, 1.75, 0.42),
                                    (140, 52, 155, 38, 1.9, 0.46), (-140, 52, -155, 38, 1.9, 0.46),
                                    (180, 56, 180, 42, 1.95, 0.48)):
        # tips lean back (towards az 180) instead of straight up
        h.spike(az, el, taz, tel, tk, w, 0.20, o if abs(az) in (35, 140) else m, bulge=0.16)
    for az in (130, 155, 180, 205, 230):
        h.spike(az, 0, az, -28, 1.55, 0.40, 0.18, m)
    for az, fx, fz in ((-28, -0.32, 0.10), (-8, -0.08, -0.04), (12, 0.18, 0.04), (32, 0.44, 0.14)):
        h.bang(az, 55, fx, fz, 0.30, mat=m, bulge=0.28)
    for s in (-1, 1):
        h.lock(P(s * 74, 22, 0.95), F(s * 0.88, -0.55, 0.016), 0.30 * R, 0.13 * R, m, bulge=0.15)


def zane(h):
    """Teal, medium length: heavy fringe over the eyes, locks to the jaw and nape."""
    h.cap(bulk=1.08, top=1.07, front_el=32, back_el=-45)
    m, o = h.main, h.second
    for az, fx, fz, w in ((-44, -0.62, -0.05, 0.30), (-24, -0.36, 0.02, 0.34), (-6, -0.12, -0.04, 0.34),
                          (12, 0.14, 0.0, 0.34), (30, 0.40, 0.04, 0.32), (48, 0.66, -0.06, 0.30)):
        h.bang(az, 58, fx, fz, w, mat=m, bulge=0.3)
    for s in (-1, 1):
        h.lock(P(s * 76, 20, 0.95), F(s * 0.9, -0.75, 0.016), 0.30 * R, 0.13 * R, m, bulge=0.16)
        h.spike(s * 105, 15, s * 112, -25, 1.48, 0.38, 0.16, o, bulge=0.06)
    h.ring(5, 140, 220, 15, -38, 1.5, 0.42, m, bulge=0.05)
    h.ring(4, 130, 230, 50, 36, 1.4, 0.40, o, bulge=0.06)


def _long_back(h, mat, length_z=0.60, n=9, spread=1.0, wave=0.0):
    """Curtain of long locks from the back of the head down the back."""
    for i in range(n):
        t = i / (n - 1)
        az = 100 + 160 * t
        a = math.radians(az)
        root = P(az, 15, 0.95)
        tip = Vector((math.sin(a) * 0.17 * spread, 0.05 + 0.10 * abs(math.cos(a)) + 0.02, Z(length_z + 0.03 * math.sin(i * 1.7))))
        curl = (math.sin(i * 2.1) * wave, 0.0, 0.0) if wave else None
        h.lock(root, tip, 0.42 * R, 0.16 * R, mat, bulge=0.25, n=10, long=True, curl=curl, taper=0.6)


def alexis(h):
    """Long straight honey-blonde hair, centre-parted fringe, long locks framing the face."""
    h.cap(bulk=1.07, top=1.06, front_el=34, back_el=-50)
    m, o = h.main, h.second
    for az, fx, fz, w in ((-34, -0.50, 0.10, 0.32), (-12, -0.22, 0.20, 0.30), (12, 0.22, 0.20, 0.30),
                          (34, 0.50, 0.10, 0.32)):
        h.bang(az, 62, fx, fz, w, mat=m, bulge=0.26)
    for s in (-1, 1):
        h.lock(P(s * 70, 25, 0.95), Vector((s * 0.15, -0.10, Z(0.62))), 0.36 * R, 0.13 * R, o, bulge=0.22, n=10,
               long=True, taper=0.7)
        h.lock(P(s * 95, 20, 0.95), Vector((s * 0.19, -0.02, Z(0.58))), 0.36 * R, 0.14 * R, m, bulge=0.25, n=10,
               long=True, taper=0.7)
    _long_back(h, m, 0.58)


def long_wavy(h):
    h.cap(bulk=1.08, top=1.07, front_el=30, back_el=-50)
    m = h.main
    for az, fx, fz in ((-36, -0.52, 0.06), (-16, -0.26, 0.14), (4, 0.02, 0.18), (24, 0.30, 0.12), (40, 0.56, 0.04)):
        h.bang(az, 60, fx, fz, 0.30, mat=m, bulge=0.26)
    for s in (-1, 1):
        h.lock(P(s * 75, 25, 0.95), Vector((s * 0.17, -0.07, Z(0.56))), 0.38 * R, 0.14 * R, m, bulge=0.25, n=10,
               long=True, curl=(s * 0.03, 0.0, 0.0), taper=0.7)
    _long_back(h, m, 0.57, wave=0.03)


def long_straight(h):
    h.cap(bulk=1.07, top=1.06, front_el=30, back_el=-50)
    m = h.main
    for az, fx, fz in ((-30, -0.45, 0.06), (-10, -0.15, 0.04), (10, 0.15, 0.04), (30, 0.45, 0.06)):
        h.bang(az, 60, fx, fz, 0.30, mat=m, bulge=0.26)
    for s in (-1, 1):
        h.lock(P(s * 75, 25, 0.95), Vector((s * 0.165, -0.06, Z(0.60))), 0.36 * R, 0.13 * R, m, bulge=0.22, n=10,
               long=True, taper=0.7)
    _long_back(h, m, 0.60)


def crowler(h):
    """Long blond hair: high forehead, big curled locks at the sides, a thick ponytail of curls."""
    h.cap(bulk=1.08, top=1.10, front_el=46, side_el=-5, back_el=-45)
    m, o = h.main, h.second
    for s in (-1, 1):
        h.lock(P(s * 55, 40, 0.95), F(s * 0.90, -0.30, 0.016), 0.36 * R, 0.16 * R, m, bulge=0.25,
               curl=(s * 0.03, -0.01, 0.04))
        for el, tel, k in ((20, -12, 1.55), (0, -35, 1.5)):
            h.spike(s * 100, el, s * 112, tel, k, 0.46, 0.22, o if el else m, bulge=0.12, curl=(s * 0.02, 0, 0.04))
    for az, el in ((150, 45), (210, 45), (180, 60)):
        h.spike(az, el, az, el - 6, 1.45, 0.44, 0.22, m, bulge=0.1)
    root = P(180, 20, 0.95)
    for i, (dx, z) in enumerate(((0.0, 0.58), (-0.07, 0.64), (0.07, 0.64), (-0.035, 0.54), (0.04, 0.55), (0.0, 0.66))):
        h.lock(root, Vector((dx, 0.22 + 0.03 * (i % 2), Z(z))), 0.52 * R, 0.26 * R, o if i % 2 else m, bulge=0.35,
               n=10, long=True, curl=(dx * 0.8, 0.05, 0.06), taper=0.7)


# ---------------------------------------------------------------- generic students (tinted in Unreal)
def spiky(h):
    h.cap(bulk=1.08, top=1.09, front_el=30, back_el=-40)
    m = h.main
    h.ring(5, 130, 230, 38, 42, 1.75, 0.42, m, bulge=0.08)
    h.ring(4, 120, 240, 5, -20, 1.5, 0.38, m, bulge=0.06)
    for s in (-1, 1):
        h.spike(s * 95, 35, s * 108, 34, 1.58, 0.38, 0.17, m)
    h.spike(0, 62, 6, 70, 1.45, 0.40, 0.18, m)
    for az, fx, fz in ((-34, -0.48, 0.18), (-12, -0.18, 0.10), (12, 0.20, 0.10), (34, 0.50, 0.18)):
        h.bang(az, 55, fx, fz, 0.32, mat=m)
    for s in (-1, 1):
        h.lock(P(s * 72, 25, 0.95), F(s * 0.86, -0.45, 0.016), 0.28 * R, 0.13 * R, m, bulge=0.2)


def neat(h):
    bastion(h)


def messy(h):
    h.cap(bulk=1.08, top=1.08, front_el=32, back_el=-40)
    m = h.main
    h.ring(9, 60, 300, 12, -10, 1.45, 0.34, m, jitter=0.9, bulge=0.06)
    h.ring(6, 40, 320, 48, 46, 1.45, 0.34, m, jitter=0.9, bulge=0.08)
    for az, fx, fz in ((-28, -0.36, 0.2), (-4, -0.04, 0.12), (20, 0.30, 0.18)):
        h.bang(az, 56, fx, fz, 0.32, mat=m)


def bowl(h):
    syrus(h)


def bob(h):
    h.cap(bulk=1.10, top=1.06, front_el=30, side_el=-20, back_el=-55)
    m = h.main
    for az, fx, fz in ((-32, -0.46, 0.16), (-11, -0.16, 0.12), (11, 0.16, 0.12), (32, 0.46, 0.16)):
        h.bang(az, 60, fx, fz, 0.32, mat=m, bulge=0.26)
    for i in range(9):
        az = 70 + i * 27.5
        h.spike(az, 10, az, -48, 1.28, 0.42, 0.16, m, bulge=0.12)


def ponytail(h):
    h.cap(bulk=1.07, top=1.06, front_el=32, side_el=-12, back_el=-45)
    m = h.main
    for az, fx, fz in ((-30, -0.44, 0.14), (-10, -0.14, 0.10), (12, 0.18, 0.12), (32, 0.46, 0.16)):
        h.bang(az, 60, fx, fz, 0.30, mat=m, bulge=0.26)
    for s in (-1, 1):
        h.lock(P(s * 74, 25, 0.95), F(s * 0.88, -0.55, 0.016), 0.24 * R, 0.10 * R, m, bulge=0.15)
    root = P(180, 40, 1.0)
    h.lock(root, Vector((0.0, 0.26, Z(0.68))), 0.50 * R, 0.30 * R, m, bulge=0.45, n=10, long=True, taper=0.8,
           curl=(0.0, 0.03, 0.0))


STYLES = {
    "jaden": jaden, "syrus": syrus, "chumley": chumley, "bastion": bastion, "chazz": chazz, "zane": zane,
    "alexis": alexis, "long_wavy": long_wavy, "long_straight": long_straight, "crowler": crowler,
    "spiky": spiky, "neat": neat, "messy": messy, "bowl": bowl, "bob": bob, "ponytail": ponytail,
}


def build(style, main, second=None, shape=None):
    h = Hair(main, second, shape)
    STYLES[style](h)
    return h.build()
