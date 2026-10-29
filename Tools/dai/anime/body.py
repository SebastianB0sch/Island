"""
Anime-teen body + Duel Academy uniform, modelled around the cast skeleton's T-pose (skeleton.py):
blazer with lapels and an open V showing the shirt, sleeves with cuffs, hands, pants or a pleated
skirt with socks / boots, shoes, optional long coat; accessories (glasses, ruff) and the duel disk.

Every builder returns [(MeshBuilder, weight fn, outline multiplier)] for skin.Assembly.
"""

import math

from mathutils import Vector

from ..assets.props import tube
from ..geo import MeshBuilder, TAU
from . import head as H
from . import skeleton as S
from . import skin as K

HEM = 0.835          # blazer hem (just below the hip joints)
COAT_HEM = 0.40      # long coats end just below the knee
COLLAR = 1.425
SKIRT_TOP, SKIRT_HEM = 1.03, 0.69


def torso_radii(z, body):
    """Half width (x) / half depth (y) of the torso surface at height z."""
    female = body.get("female", False)
    if female:
        prof = [(0.78, 0.178, 0.122), (0.88, 0.172, 0.118), (0.97, 0.150, 0.104), (1.05, 0.124, 0.090),
                (1.14, 0.132, 0.094), (1.24, 0.150, 0.100), (1.32, 0.158, 0.098), (1.37, 0.150, 0.086),
                (1.41, 0.096, 0.064), (1.44, 0.052, 0.046)]
    else:
        prof = [(0.78, 0.172, 0.120), (0.88, 0.164, 0.114), (0.97, 0.150, 0.104), (1.05, 0.142, 0.098),
                (1.15, 0.152, 0.104), (1.25, 0.166, 0.110), (1.33, 0.176, 0.104), (1.38, 0.166, 0.090),
                (1.415, 0.104, 0.066), (1.445, 0.056, 0.050)]
    if z <= prof[0][0]:
        rx, ry = prof[0][1], prof[0][2]
    elif z >= prof[-1][0]:
        rx, ry = prof[-1][1], prof[-1][2]
    else:
        for (z0, x0, y0), (z1, x1, y1) in zip(prof, prof[1:]):
            if z0 <= z <= z1:
                t = (z - z0) / (z1 - z0)
                rx, ry = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
                break
    belly = body.get("belly", 0.0)
    if belly:
        b = math.exp(-((z - 1.04) / 0.17) ** 2) * belly
        rx *= 1 + 0.32 * b
        ry *= 1 + 0.65 * b
    if female and 1.17 < z < 1.33:
        ry *= 1 + 0.16 * math.sin(math.pi * (z - 1.17) / 0.16)
    return rx, ry


def _ring(z, body, k=1.0, seg=24, flare=0.0, pleats=0.0):
    rx, ry = torso_radii(z, body)
    rx, ry = rx * k + flare, ry * k + flare * 0.75
    out = []
    for i in range(seg):
        a = TAU * i / seg - math.pi / 2          # i = 0 at the front (-Y)
        p = 1.0 + pleats * abs(math.sin(a * seg / 4))
        out.append((math.cos(a) * rx * p, math.sin(a) * ry * p, z))
    return out


def front_point(z, x, body, lift=0.0):
    rx, ry = torso_radii(z, body)
    x = max(-rx * 0.98, min(rx * 0.98, x))
    y = -ry * math.sqrt(max(0.0, 1 - (x / rx) ** 2))
    n = Vector((x / rx ** 2, y / ry ** 2, 0.0)).normalized()
    return Vector((x, y, z)) + n * lift


def _hem_follow():
    return K.hips_to_thighs(z_full=HEM - 0.02, z_start=S.PELVIS + 0.02, amount=0.45)


# --------------------------------------------------------------------------- uniform
def jacket(m, body):
    """Blazer body (+ long coat skirt), lapels, open V with the shirt, collar, trim."""
    parts = []
    mb = MeshBuilder("Jacket")
    zs = [HEM, HEM + 0.03, 0.92, 0.99, 1.06, 1.13, 1.20, 1.27, 1.33, 1.37, 1.40, 1.425, 1.445]
    rows = [_ring(z, body, 1.0, flare=0.016 if z < HEM + 0.05 else 0.0) for z in zs]
    mb.grid_faces(rows, m["jacket"], smooth=True, closed_u=True)
    hem_follow = _hem_follow()
    parts.append((mb, lambda p: K.torso(p) if p.z > S.PELVIS + 0.02 else hem_follow(p), 1.0))

    coat = body.get("coat")
    if coat:
        cb = MeshBuilder("Coat")
        czs = [COAT_HEM, 0.50, 0.60, 0.70, 0.78, HEM]
        seg = 24
        crow = [_ring(z, body, 1.0, seg=seg, flare=0.016 + (HEM - z) * 0.16) for z in czs]
        crow.append(rows[0])
        for j in range(len(crow) - 1):
            for i in range(seg):
                if i in (0, seg - 1):                       # open front slit
                    continue
                i2 = (i + 1) % seg
                cb.poly([crow[j][i], crow[j][i2], crow[j + 1][i2], crow[j + 1][i]], m["jacket"], smooth=True)
        tb = MeshBuilder("CoatTrim")
        hem = [Vector(p) for p in crow[0][1:seg]]
        tube(tb, [p + Vector((0, 0, 0.006)) for p in hem], [0.008] * len(hem), m["trim"], seg=5, cap_top=False)
        for i in (1, seg - 1):
            pts = [Vector(crow[j][i]) for j in range(len(crow))]
            tube(tb, pts, [0.007] * len(pts), m["trim"], seg=5, cap_top=False)
        fn = K.hips_to_thighs(z_full=COAT_HEM + 0.1, z_start=HEM + 0.04, amount=0.8)
        parts.append((cb, fn, 1.0))
        parts.append((tb, fn, 0.0))

    # shirt V (+ the strip of shirt an open jacket shows down to the hem)
    openness = body.get("open", 0.5)
    vb = 1.33 - 0.30 * min(1.0, openness / 0.8) if openness < 0.8 else HEM + 0.008
    strip = 0.042 if openness >= 0.8 else 0.0
    top_w = 0.07
    sh = MeshBuilder("Shirt")
    zz = [vb + (COLLAR - vb) * k / 10 for k in range(11)]

    def hw(z):
        t = max(0.0, min(1.0, (z - vb) / (COLLAR - vb)))
        return max(top_w * t ** 0.85, strip)
    grid = []
    for z in zz:
        w = max(hw(z), 0.002)
        grid.append([tuple(front_point(z, -w + 2 * w * c / 4, body, 0.008)) for c in range(5)])
    sh.grid_faces(grid, m["inner"], smooth=True)
    # crew neck of the shirt: fills the gap between the V, the collar and the neck
    sh.lathe([(0.064, COLLAR - 0.07), (0.058, COLLAR - 0.01), (0.049, COLLAR + 0.012)], m["inner"], seg=16,
             cap_top=False, cap_bottom=True, center=(0, 0.004, 0), sy=0.9)
    parts.append((sh, K.torso, 0.0))
    # ribbon bow for the girls' closed jackets
    if openness < 0.5 and body.get("female"):
        rb = MeshBuilder("Bow")
        c = front_point(COLLAR - 0.05, 0.0, body, 0.008)
        for s in (-1, 1):
            rb.sphere(tuple(c + Vector((s * 0.026, -0.003, 0.003))), 0.02, m["trim"], seg=8, rings=6,
                      scale=(1.35, 0.45, 0.75))
            tube(rb, [c + Vector((s * 0.006, -0.004, -0.008)), c + Vector((s * 0.018, -0.006, -0.05))],
                 [0.009, 0.003], m["trim"], seg=5)
        rb.sphere(tuple(c + Vector((0, -0.006, 0))), 0.011, m["trim"], seg=8, rings=6)
        parts.append((rb, K.torso, 0.0))

    # lapels: raised strips in the jacket colour along the V, edged with trim
    lp = MeshBuilder("Lapels")
    tr = MeshBuilder("Trim")
    lap_bottom = max(vb, 1.08) if openness < 0.8 else 1.08
    for s in (-1, 1):
        edge, outer = [], []
        lz = [lap_bottom + (COLLAR - lap_bottom) * k / 9 for k in range(10)]
        for z in lz:
            w = hw(z)
            lw = 0.018 + 0.042 * math.sin(math.pi * min(1.0, (z - lap_bottom) / (COLLAR - lap_bottom) * 0.9))
            edge.append(front_point(z, s * w, body, 0.011))
            outer.append(front_point(z, s * (w + lw), body, 0.011))
        rows = [[tuple(edge[i]), tuple(outer[i])] for i in range(len(lz))]
        if s < 0:
            rows = [list(reversed(r)) for r in rows]
        lp.grid_faces(rows, m["jacket"], smooth=True)
        tube(tr, [p + Vector((0, -0.002, 0)) for p in edge], [0.0065] * len(edge), m["trim"], seg=5, cap_top=False)
        tube(tr, [p + Vector((0, -0.002, 0)) for p in outer], [0.0055] * len(outer), m["trim"], seg=5, cap_top=False)
        if openness >= 0.8:      # front opening edge down to the hem
            fz = [HEM + (lap_bottom - HEM) * k / 8 for k in range(9)]
            pts = [front_point(z, s * hw(z), body, 0.010) for z in fz]
            tube(tr, pts, [0.0065] * len(pts), m["trim"], seg=5, cap_top=False)
        elif not body.get("female") and s > 0:   # buttons below the V
            for z in (vb - 0.06, vb - 0.17):
                if z > HEM + 0.05:
                    tr.sphere(tuple(front_point(z, 0.0, body, 0.007)), 0.009, m["trim"], seg=8, rings=5)
    parts.append((lp, K.torso, 0.0))
    parts.append((tr, K.torso, 0.0))

    # stand collar + hem trim
    cl = MeshBuilder("Collar")
    # low turned-down collar (open at the front where the lapels start)
    for i in range(18):
        a0, a1 = TAU * i / 18 - math.pi / 2, TAU * (i + 1) / 18 - math.pi / 2
        if abs(math.sin(a0) + 1) < 0.08 or abs(math.sin(a1) + 1) < 0.08:
            continue
        def ring(a, r, z):
            return (math.cos(a) * r, math.sin(a) * r * 0.9 + 0.006, z)
        cl.poly([ring(a0, 0.064, COLLAR - 0.01), ring(a1, 0.064, COLLAR - 0.01), ring(a1, 0.06, COLLAR + 0.022),
                 ring(a0, 0.06, COLLAR + 0.022)], m["jacket"], smooth=True)
    tube(cl, [Vector((math.cos(TAU * k / 18 - math.pi / 2 + 0.35) * 0.06,
                      math.sin(TAU * k / 18 - math.pi / 2 + 0.35) * 0.054 + 0.006, COLLAR + 0.022)) for k in range(16)],
         [0.005] * 16, m["trim"], seg=5, cap_top=False)
    if not coat:
        hem = _ring(HEM + 0.004, body, 1.0, flare=0.016)
        tube(cl, [Vector(p) for p in hem] + [Vector(hem[0])], [0.0075] * (len(hem) + 1), m["trim"], seg=5,
             cap_top=False)
    collar_top = COLLAR + 0.01
    parts.append((cl, lambda p: (K.torso(p) if p.z > S.PELVIS else hem_follow(p)) if p.z < collar_top
                  else {"spine_03": 0.6, "neck_01": 0.4}, 0.8))
    return parts


def arms(m):
    parts = []
    z = S.SHOULDER
    for s, side in ((1, "l"), (-1, "r")):
        mb = MeshBuilder(f"Sleeve_{side}")
        xs = (0.12, 0.175, 0.26, 0.36, 0.44, 0.53, 0.64)
        rr = (0.068, 0.067, 0.062, 0.057, 0.054, 0.050, 0.047)
        tube(mb, [Vector((s * x, 0.0, z)) for x in xs], list(rr), m["jacket"], seg=14, cap_top=True)
        mb.sphere((s * 0.15, 0.0, z - 0.004), 0.078, m["jacket"], seg=14, rings=8, scale=(1.0, 0.92, 0.92))
        parts.append((mb, K.arm_chain(side), 1.0))
        cf = MeshBuilder(f"Cuff_{side}")
        tube(cf, [Vector((s * 0.625, 0, z)), Vector((s * 0.655, 0, z))], [0.05, 0.05], m["trim"], seg=14)
        parts.append((cf, K.arm_chain(side), 1.0))
        hd = MeshBuilder(f"Hand_{side}")
        tube(hd, [Vector((s * 0.645, 0, z)), Vector((s * 0.675, 0, z))], [0.032, 0.03], m["skin"], seg=10)   # wrist
        hd.sphere((s * 0.705, -0.002, z - 0.004), 0.036, m["skin"], seg=12, rings=8, scale=(1.05, 0.42, 0.95))  # palm
        hd.sphere((s * 0.745, -0.002, z - 0.006), 0.029, m["skin"], seg=12, rings=8, scale=(1.2, 0.4, 0.9))  # fingers
        tube(hd, [Vector((s * 0.688, -0.015, z - 0.008)), Vector((s * 0.708, -0.033, z - 0.01)),
                  Vector((s * 0.724, -0.04, z - 0.012))], [0.011, 0.009, 0.007], m["skin"], seg=8)        # thumb
        parts.append((hd, K.arm_chain(side), 1.0))
    return parts


def legs(m, body):
    parts = []
    female = body.get("female", False)
    if not female:
        pt = MeshBuilder("PantsTop")
        rows = [_ring(z, {"female": False}, k, seg=20) for z, k in ((1.0, 0.92), (0.92, 0.95), (0.86, 0.93))]
        pt.grid_faces(rows, m["pants"], smooth=True, closed_u=True)
        pt.poly(list(reversed(rows[-1])), m["pants"], smooth=True)
        parts.append((pt, K.hips_to_thighs(z_full=0.80, z_start=0.90, amount=0.6), 0.6))
    else:
        sk = MeshBuilder("Skirt")
        zs = [SKIRT_TOP, 0.98, 0.91, 0.84, 0.77, SKIRT_HEM]
        rows = [_ring(z, body, 0.98, seg=36, flare=max(0.0, (0.98 - z)) * 0.30,
                      pleats=0.0 if z > 0.97 else 0.05) for z in zs]
        sk.grid_faces(list(reversed(rows)), m["skirt"], smooth=True, closed_u=True)
        parts.append((sk, K.hips_to_thighs(z_full=SKIRT_HEM, z_start=0.94, amount=0.6), 1.0))
        under = MeshBuilder("Undershorts")
        urows = [_ring(z, {"female": True}, k, seg=16) for z, k in ((1.0, 0.86), (0.86, 0.80))]
        under.grid_faces(urows, m["skirt"], smooth=True, closed_u=True)
        under.poly(list(reversed(urows[-1])), m["skirt"], smooth=True)
        parts.append((under, K.hips_to_thighs(z_full=0.80, z_start=0.90, amount=0.6), 0.0))
    for s, side in ((1, "l"), (-1, "r")):
        x = s * S.HIP_X
        lg = MeshBuilder(f"Leg_{side}")
        if not female:
            # narrow inside the jacket so the thighs never poke through it, full width below the hem
            tube(lg, [Vector((x * 0.8, 0, 0.98)), Vector((x * 0.92, 0, HEM + 0.04)), Vector((x, 0, HEM - 0.04)),
                      Vector((x, -0.006, S.KNEE)), Vector((x, 0, 0.17)), Vector((x, 0, 0.09))],
                 [0.060, 0.072, 0.086, 0.066, 0.058, 0.060], m["pants"], seg=14)
        else:
            boots = body.get("boots")
            sock = m.get("boots") if boots else m.get("socks", m["skin"])
            top = S.KNEE + 0.07 if boots else S.KNEE - 0.03
            # bare leg only down to just inside the boot / sock (a skin tube underneath would poke
            # through when the knee bends)
            knee_r = 0.052 + (top - S.KNEE) * 0.06
            tube(lg, [Vector((x * 0.85, 0, 0.96)), Vector((x, 0, 0.80)), Vector((x, -0.006, max(top, S.KNEE + 0.02))),
                      Vector((x, -0.006, top - 0.03))], [0.058, 0.07, knee_r, knee_r * 0.95], m["skin"], seg=14)
            r0 = 0.062 if boots else 0.055
            tube(lg, [Vector((x, -0.006, top)), Vector((x, 0, 0.30)), Vector((x, 0, 0.16)), Vector((x, 0, 0.07))],
                 [r0, r0 * 0.92, r0 * 0.78, r0 * 0.8], sock, seg=14)
            if boots:
                lg.torus((x, -0.006, top), r0, 0.008, m["sole"], seg=14, tube_seg=4)
        parts.append((lg, K.leg_chain(side), 1.0))
        sh = MeshBuilder(f"Shoe_{side}")
        k = 1.02 if female else 1.15
        sh.sphere((x, -0.045 * k, 0.05), 0.06 * k, m["shoes"], seg=14, rings=8, scale=(0.82, 2.0, 0.8))
        sh.verts = [Vector((v.x, v.y, max(v.z, 0.016))) for v in sh.verts]       # flat sole
        with sh.at((x, -0.045 * k, 0.0), scale=(0.82, 2.0, 1.0)):
            sh.cylinder((0, 0, 0.0), 0.062 * k, 0.018, m["sole"], seg=14)
        parts.append((sh, K.foot_fn(side), 1.0))
    return parts


# --------------------------------------------------------------------------- accessories
def glasses(mat, shape=None):
    mb = MeshBuilder("Glasses")
    rad = S.HEAD_RADIUS * 0.27
    centers = []
    for s in (-1, 1):
        c = H.face_surface(s * 0.40, -0.16, shape, lift=0.012)
        centers.append(c)
        with mb.at(tuple(c), rot_x=90):
            mb.torus((0, 0, 0), rad, 0.0028, mat, seg=20, tube_seg=5)
    a, b = centers[0] + Vector((rad, 0, 0.003)), centers[1] - Vector((rad, 0, -0.003))
    tube(mb, [a, (a + b) * 0.5 + Vector((0, -0.003, 0.006)), b], [0.0025] * 3, mat, seg=5)
    for s, c in zip((-1, 1), centers):
        e = c + Vector((s * rad, 0, 0))
        ear = Vector((s * S.HEAD_RADIUS * 0.88, S.HEAD_CENTER[1] + 0.03, c.z + 0.004))
        tube(mb, [e, e + (ear - e) * 0.5, ear], [0.0025] * 3, mat, seg=5)
    return [(mb, K.rigid("head"), 0.0)]


def ruff(mat):
    mb = MeshBuilder("Ruff")
    for i in range(14):
        a = TAU * i / 14
        mb.sphere((math.cos(a) * 0.08, math.sin(a) * 0.072 + 0.006, COLLAR + 0.04), 0.038, mat, seg=8, rings=6,
                  scale=(1.0, 1.0, 0.5))
    return [(mb, lambda p: {"spine_03": 0.5, "neck_01": 0.5}, 0.8)]


def duel_disk(m, elbow=(S.ELBOW_X, 0.0, S.SHOULDER), wrist=(S.WRIST_X, 0.0, S.SHOULDER)):
    """Academy-style duel disk on the left forearm (T-pose: forearm along +X, back of the arm up), placed
    between the given elbow and wrist joints of whichever skeleton it is built for."""
    mb = MeshBuilder("DuelDisk")
    e, w = Vector(elbow), Vector(wrist)
    with mb.at(tuple(e)):
        L = (w - e).length
        z = 0.065
        cx = L * 0.5
        mb.cylinder((cx, 0.0, z - 0.016), 0.105, 0.032, m["disk"], seg=24)
        mb.cylinder((cx, 0.0, z + 0.016), 0.055, 0.016, m["gold"], seg=18)
        mb.cylinder((cx, 0.0, z + 0.032), 0.03, 0.008, m["glow"], seg=14)
        # card blade with five monster zones, folded along the forearm towards the hand
        mb.box((cx + 0.28, 0.0, z - 0.008), (0.42, 0.11, 0.016), m["disk"])
        for k in range(5):
            mb.box((cx + 0.12 + k * 0.082, 0.0, z + 0.002), (0.066, 0.088, 0.005), m["glow"])
        tube(mb, [Vector((cx - 0.04, 0, 0)), Vector((cx + 0.04, 0, 0))], [0.052, 0.052], m["disk"], seg=14)
    return [(mb, K.rigid("lowerarm_l"), 0.7)]
