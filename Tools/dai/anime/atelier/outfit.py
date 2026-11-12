"""
Garments for the atelier characters.

Every garment is cut from the body's own cross-sections (body.Body.torso_ring / arm_ring / leg_ring) plus an
ease, so layers stack by construction: skin < legwear < shirt < jacket < coat. Open edges get an inner side
and a rim (mesh.solidify), free-hanging cloth is skinned to the shared spring chains (skirt_NN_J /
coattail_NN_J, the bones the runtime's cloth springs drive).

Colour and trim are painted into a per-character atlas (paint.Atlas): each part owns a rectangle and its
UVs (u round the body, v from hem to top) address hem bands, piping, gradients and motifs directly.

A design lists its garments as (kind, params) pairs; Kit.wear() dispatches to the functions below and
records which skin the outfit leaves visible (Kit.skin).
"""

import math

import numpy as np

from .. import skeleton as S
from . import mesh as M
from . import paint as P

CLOTH_CHAINS = 8
CLOTH_Z = 0.86
CLOTH_SEG = 0.11
CLOTH_RX, CLOTH_RY = 0.163, 0.115


def cloth_bone_specs(prefix):
    """[(name, parent, head, tail, deform)] of one shared hem chain ring (identical for every character, so
    the cast skeleton has a single set)."""
    out = []
    for k in range(CLOTH_CHAINS):
        a = 2 * math.pi * k / CLOTH_CHAINS
        d = np.array([math.sin(a), -math.cos(a), 0.0])
        parent = ("thigh_l" if d[0] > 0 else "thigh_r") if abs(math.sin(a)) > 0.38 else "pelvis"
        p = np.array([d[0] * CLOTH_RX, d[1] * CLOTH_RY, CLOTH_Z])
        for j in range(1, 4):
            seg = CLOTH_SEG if j < 3 else 0.03
            q = p + np.array([0.0, 0.0, -seg]) + d * (0.025 if j < 3 else 0.005)
            name = f"{prefix}_{k:02d}_{j}"
            out.append((name, parent, tuple(p), tuple(q), j < 3))
            parent, p = name, q
    return out


def hang(part, prefix, cut, drop, share=0.72):
    """Hand the part's vertices below `cut` over to the hem chains (fully by cut - drop)."""
    v = part.v
    t = np.clip((cut - v[:, 2]) / max(drop, 1e-3), 0.0, 1.0)
    k = share * M.smooth(t * 1.15) * (t > 0.02)
    a = np.arctan2(v[:, 0], -v[:, 1]) % (2 * np.pi)
    f = a / (2 * np.pi) * CLOTH_CHAINS
    k0 = np.floor(f).astype(int) % CLOTH_CHAINS
    wa = 1.0 - (f - np.floor(f))
    seg2 = M.smooth((t - 0.25) / 0.5)
    part.w = {b: w * (1.0 - k) for b, w in part.w.items()}
    for c in range(CLOTH_CHAINS):
        wk = np.where(k0 == c, wa, 0.0) + np.where((k0 + 1) % CLOTH_CHAINS == c, 1.0 - wa, 0.0)
        for j, ws in ((1, 1.0 - seg2), (2, seg2)):
            w = k * wk * ws
            if w.max() > 1e-4:
                part.w[f"{prefix}_{c:02d}_{j}"] = w
    return part


class Kit:
    """What a character's garments are cut with: its body, texture atlas and material names."""

    def __init__(self, body, key, mats):
        self.body = body
        self.key = key
        self.mats = mats                                  # {"cloth": name, "tint": name or None, "skin": name}
        self.atlas = {"cloth": P.Atlas(), "tint": P.Atlas(1024, 256) if mats.get("tint") else None}
        self.parts = []
        self.jobs = []
        self.cloth_prefixes = set()
        # visible skin: torso from this height up, arm / leg intervals
        self.skin = dict(torso=0.80, arms=[(0.09, S.WRIST_X)], legs=[(S.ANKLE, 0.90)], hands=True)

    def add(self, part, color, slot="cloth", cells=(1, 1), **style):
        slot = slot if self.atlas[slot] is not None else "cloth"
        # painted when the kit is saved (pack()): only then is it known how much room every part can have
        self.jobs.append((part, color, slot, cells, style))
        part.mat = self.mats[slot]
        part.face_mat = None
        self.parts.append(part)
        return part

    def pack(self):
        """Paint every part into its atlas, at twice the cell resolution when everything fits."""
        jobs, self.jobs = self.jobs, []
        for slot in {j[2] for j in jobs}:
            mine = [j for j in jobs if j[2] == slot]
            order = sorted(range(len(mine)), key=lambda i: -(mine[i][3][0] * mine[i][3][1]) if mine[i][4] else 1)
            src = self.atlas[slot]
            for scale in (2, 1):
                atlas = P.Atlas(src.size, src.cell)
                try:
                    rects = {i: atlas.alloc(mine[i][3][0] * scale, mine[i][3][1] * scale) for i in order if mine[i][4]}
                    for i in order:
                        if not mine[i][4]:
                            rects[i] = atlas.swatch(mine[i][1])
                except ValueError:
                    if scale == 1:
                        raise
                    continue
                break
            self.atlas[slot] = atlas
            for i, (part, color, _, _, style) in enumerate(mine):
                if style:
                    atlas.paint(rects[i], color, **style)
                    part.uv = atlas.uv(rects[i], part.uv)
                else:
                    part.uv = atlas.uv(rects[i], np.full((len(part.v), 2), 0.5), inset=8.0)

    def cover_arms(self, x0, x1):
        out = []
        for a, b in self.skin["arms"]:
            if x1 <= a or x0 >= b:
                out.append((a, b))
                continue
            if x0 > a + 0.02:
                out.append((a, x0))
            if x1 < b - 0.02:
                out.append((x1, b))
        self.skin["arms"] = out

    def cover_legs(self, z0, z1):
        out = []
        for a, b in self.skin["legs"]:
            if z1 <= a or z0 >= b:
                out.append((a, b))
                continue
            if z0 > a + 0.02:
                out.append((a, z0))
            if z1 < b - 0.02:
                out.append((z1, b))
        self.skin["legs"] = out

    def wear(self, garments):
        for kind, params in garments:
            GARMENTS[kind](self, **params)
        return self.parts

    def save(self, tex_dir, tex_rel):
        """Write the atlases; -> {material name: palette spec}."""
        import os
        self.pack()
        specs = {}
        for slot, atlas in self.atlas.items():
            if atlas is None:
                continue
            name = self.mats[slot]
            rel = f"{tex_rel}/T_{name[2:]}"
            atlas.save(os.path.join(tex_dir, rel + ".png"))
            specs[name] = dict(kind="toon", color=(1.0, 1.0, 1.0), rough=0.85, fill=0.5, base=rel)
        return specs


# --------------------------------------------------------------------------- painted tailoring
# What a texture artist adds to a garment (paint._detail): seams, plackets, pockets, lapels, fold hints at the
# joints and soft ambient shade under collars and arms. Built here because only the garment knows where its
# waist, elbow or knee sits in its own UVs.
def _perim(ring):
    r = np.asarray(ring, np.float64)
    return float(np.linalg.norm(np.diff(np.concatenate([r, r[:1]]), axis=0), axis=1).sum())


def _tailored(base, extra):
    """A style dict with tailoring merged in: list keys concatenate, 'shade' merges, the rest is set once."""
    out = dict(base or {})
    for k, val in extra.items():
        if val is None:
            continue
        if k == "shade":
            sh = dict(val)
            old = out.get("shade") or {}
            for kk, vv in old.items():
                sh[kk] = (list(sh.get(kk, ())) + list(vv)) if kk in ("spots", "under") else vv
            out["shade"] = sh
        elif isinstance(val, list):
            out[k] = list(out.get(k, ())) + val
        else:
            out.setdefault(k, val)
    return out


def _top_tailoring(kit, hem, neck, ease, opened, g0, detail):
    """Painted tailoring of a top's body. detail: dict(placket, zip, buttons, pockets, yoke, panels, back_seam,
    lapel, ribs, plain) - see top()."""
    b = kit.body
    H = neck - hem
    zm = min(max(0.5 * (hem + neck), 0.9), 1.3)
    W = _perim(b.torso_ring(zm, ease, n=48))
    two_pi = 2 * np.pi

    def uu(th):
        return (th - g0) / (two_pi - 2 * g0) if opened else (th % two_pi) / two_pi

    def vz(z):
        return (z - hem) / H

    def th_x(x, z):
        """Azimuth of the front point x metres left of the centre at height z."""
        th = np.linspace(-1.35, 1.35, 61)
        ring = b.torso_ring(float(min(z, 1.40)), ease, theta=th)
        return float(np.interp(x, ring[:, 0], th))

    side_l, side_r = uu(np.pi / 2), uu(3 * np.pi / 2)
    d = detail or {}
    st = dict(dims=(W, H), wrap=not opened)
    if d.get("plain"):
        return st
    shade = dict(top=(0.045, 0.34), spots=[], under=[])
    if hem < 1.20:
        for u in (side_l, side_r):
            shade["spots"].append((u, vz(1.285), 0.030, 0.075, 0.42))             # under the arms
    if hem < 0.93:
        shade["bottom"] = (0.5 * min(0.30, 0.95 - hem) + 0.04, 0.16)
    st["shade"] = shade
    seams = [("u", side_l, 0.0, vz(1.27)), ("u", side_r, 0.0, vz(1.27))]
    folds, lines, stitch, dots, pockets = [], [], [], [], []
    if hem < 1.0:                                           # waist creases pulling towards the side seams
        zw = 1.075
        for u, sgn in ((uu(np.pi / 2 - 0.42), 1.0), (uu(3 * np.pi / 2 + 0.42), -1.0)):
            folds.append(dict(u=u, v=vz(zw), len=0.070, n=2, gap=0.019, tilt=0.30 * sgn, s=0.5, thick=0.0026))
        for u, sgn in ((uu(np.pi - 0.5), -1.0), (uu(np.pi + 0.5), 1.0)):
            folds.append(dict(u=u, v=vz(zw + 0.01), len=0.055, n=2, gap=0.022, tilt=0.22 * sgn, s=0.4, thick=0.0024))
    stitch.append(("v", 0.011 / H, None, None))
    if opened:
        v_top = vz((d["lapel"].get("z", 1.16) if isinstance(d.get("lapel"), dict) else 1.16)) if d.get("lapel") else 1.0
        stitch += [("u", 0.011 / W, 0.0, v_top), ("u", 1.0 - 0.011 / W, 0.0, v_top)]
    if d.get("back_seam") or hem < 0.80:
        seams.append(("u", uu(np.pi), 0.0, vz(1.36)))
    if d.get("yoke"):
        zy = d["yoke"] if isinstance(d["yoke"], float) else 1.325
        lines += [(uu(np.pi - 1.25), vz(zy + 0.012), uu(np.pi), vz(zy - 0.008)),
                  (uu(np.pi), vz(zy - 0.008), uu(np.pi + 1.25), vz(zy + 0.012))]
    if d.get("panels"):                                     # princess seams front and back
        z1 = 1.30
        for th in (0.50, two_pi - 0.50, np.pi - 0.55, np.pi + 0.55):
            seams.append(("u", uu(th), 0.0, vz(z1)))
    pk = d.get("placket")
    if pk and not opened:                                   # button band down the closed front
        w = pk.get("w", 0.030)
        z1 = pk.get("z1", neck)
        st.setdefault("blocks", [])
        if pk.get("color") is not None:
            st["blocks"] = [(-0.5 * w / W, 0.5 * w / W, 0.0, vz(z1), pk["color"])]
        seams += [("u", 0.5 * w / W, 0.0, vz(z1)), ("u", 1.0 - 0.5 * w / W, 0.0, vz(z1))]
        n = pk.get("buttons", 0)
        if n:
            for z in np.linspace(pk.get("z0", hem + 0.05), pk.get("z_top", neck - 0.05), n):
                dots.append((0.0, vz(z), pk.get("r", 0.0055), pk.get("button", (0.92, 0.92, 0.90))))
    if d.get("zip") and not opened:
        seams.append(("u", 0.0, 0.0, 1.0))
        stitch += [("u", 0.007 / W, 0.0, 1.0), ("u", 1.0 - 0.007 / W, 0.0, 1.0)]
    bt = d.get("buttons")
    if bt and opened:                                       # buttons on the left front of an open jacket
        for z in np.linspace(bt.get("z0", 1.04), bt.get("z1", 1.14), bt.get("n", 2)):
            dots.append((uu(th_x(bt.get("x", 0.045), z)), vz(z), bt.get("r", 0.0065), bt.get("color", (0.85, 0.70, 0.30))))
    for name in d.get("pockets", ()):
        if name in ("chest", "chest_r"):
            sx = 1.0 if name == "chest" else -1.0
            z = 1.262
            u = uu(th_x(sx * 0.064, z)) if sx > 0 else uu(two_pi + th_x(sx * 0.064, z))
            pockets.append(dict(u=u, v=vz(z), w=0.066, h=0.070, kind=d.get("chest_kind", "patch")))
        elif name in ("hip", "flap", "welt"):
            z = d.get("pocket_z", max(hem + 0.085, 0.925))
            for sx in (1.0, -1.0):
                th = th_x(sx * d.get("pocket_x", 0.082), z)
                u = uu(th) if sx > 0 else uu(two_pi + th)
                pockets.append(dict(u=u, v=vz(z), w=0.092, h=0.085 if name != "welt" else 0.0,
                                    kind={"hip": "patch"}.get(name, name), button=d.get("pocket_button"),
                                    tilt=-0.10 * sx if name == "welt" else 0.0))
    if d.get("lapel") and opened:
        lp = dict(d["lapel"]) if isinstance(d["lapel"], dict) else {}
        zb = lp.pop("z", 1.16)
        st["lapel"] = dict(dict(v0=vz(zb), w=0.050, notch=vz(1.315)), **lp)
    if d.get("ribs"):
        st["ribs"] = dict(n=int(W / 0.011), v1=d["ribs"] / H, depth=0.30)
    st.update(seams=seams, creases=folds, lines=lines, stitch=stitch, dots=dots, pockets=pockets)
    return st


def _sleeve_tailoring(kit, x0, x1, ease, rolled=False):
    b = kit.body
    L = x1 - x0
    W = _perim(b.arm_ring(min(0.5 * (x0 + x1), 0.40), ease))

    def vx(x):
        return 1.0 - (x - x0) / L

    st = dict(dims=(W, L), wrap=True, seams=[("u", 0.75, 0.0, 1.0)], creases=[], stitch=[("v", 0.014 / L, None, None)],
              shade=dict(spots=[(0.75, vx(0.205), 0.030, 0.070, 0.42)], bottom=(0.03, 0.10)))
    if x1 > S.SHOULDER_X + 0.05:
        st["seams"].append(("v", vx(S.SHOULDER_X - 0.012), None, None))        # armhole seam
    if x1 > S.ELBOW_X + 0.04:
        ve = vx(S.ELBOW_X)
        st["creases"] += [dict(u=0.0, v=ve, len=0.070, n=3, gap=0.015, fan=0.9, s=0.70),
                        dict(u=0.5, v=ve - 0.02 / L, len=0.040, n=2, gap=0.016, s=0.45),
                        dict(u=0.92, v=vx(0.60), len=0.050, n=2, gap=0.014, tilt=0.25, s=0.5)]
        st["shade"]["spots"].append((0.0, ve, 0.022, 0.035, 0.22))
    elif rolled:
        st["creases"].append(dict(u=0.0, v=0.16, len=0.06, n=2, gap=0.012, s=0.5))
    return st


def _leg_tailoring(kit, hem, top_z, ease, crease=True):
    b = kit.body
    H = top_z - hem
    W = _perim(b.leg_ring(max(hem, 0.5), ease))

    def vz(z):
        return (z - hem) / H

    st = dict(dims=(W, H), wrap=True, seams=[("u", 0.0, 0.0, 1.0), ("u", 0.5, 0.0, 1.0)], creases=[], lines=[],
              stitch=[("v", 0.016 / H, None, None)],
              shade=dict(top=(0.05, 0.22), spots=[(0.5, vz(0.82), 0.040, 0.10, 0.34)], bottom=(0.05, 0.14)))
    if crease and hem < 0.40:
        st["lines"].append((0.25, vz(hem + 0.02), 0.25, vz(0.80)))
    if hem < S.KNEE - 0.08:
        st["creases"] += [dict(u=0.75, v=vz(S.KNEE), len=0.085, n=3, gap=0.017, curve=0.25, s=0.75),
                        dict(u=0.25, v=vz(S.KNEE + 0.035), len=0.055, n=2, gap=0.022, curve=-0.3, s=0.42),
                        dict(u=0.30, v=vz(0.835), len=0.075, n=2, gap=0.024, tilt=-0.45, s=0.5)]
    if hem < 0.20:
        st["creases"] += [dict(u=0.22, v=vz(hem + 0.060), len=0.085, n=2, gap=0.020, tilt=0.12, s=0.65),
                        dict(u=0.70, v=vz(hem + 0.075), len=0.070, n=2, gap=0.022, tilt=-0.15, s=0.55)]
    return st


def _hip_tailoring(kit, z0, waist, ease, pockets=True):
    b = kit.body
    H = waist - z0
    W = _perim(b.torso_ring(0.95, ease, n=48))

    def vz(z):
        return (z - z0) / H

    def ux(x, z=0.98):
        th = np.linspace(-1.35, 1.35, 61)
        ring = b.torso_ring(z, ease, theta=th)
        return (float(np.interp(x, ring[:, 0], th)) / (2 * np.pi)) % 1.0

    band = vz(waist - 0.034)
    st = dict(dims=(W, H), wrap=True, seams=[("v", band, None, None), ("u", 0.0, 0.0, band), ("u", 0.5, 0.0, band),
                                             ("u", 0.25, 0.0, band), ("u", 0.75, 0.0, band)],
              lines=[], pockets=[], stitch=[], shade=dict(top=(0.03, 0.30)))
    uf = ux(0.024)
    st["lines"] += [(uf, band, uf, vz(z0 + 0.075)), (uf, vz(z0 + 0.075), 0.0, vz(z0 + 0.045))]       # fly
    for x in (0.062, -0.062):                                # belt loops
        st["pockets"].append(dict(u=ux(x), v=vz(waist - 0.017), w=0.011, h=0.036))
    for u in (0.25, 0.75, 0.5 - 0.085 / W, 0.5 + 0.085 / W):
        st["pockets"].append(dict(u=u, v=vz(waist - 0.017), w=0.011, h=0.036))
    if pockets:
        for sx in (1.0, -1.0):                               # slanted front pockets, welted back pockets
            st["lines"].append((ux(sx * 0.070), band, 0.25 if sx > 0 else 0.75, vz(waist - 0.125)) if sx > 0 else
                               (0.75, vz(waist - 0.125), ux(sx * 0.070), band))
            st["pockets"].append(dict(u=0.5 + sx * 0.080 / W, v=vz(waist - 0.085), w=0.085, kind="welt"))
    return st


# --------------------------------------------------------------------------- shells
def _torso_shell(kit, name, z0, z1, ease, n=44, gap=None, flare=0.0, rows=None, front=0.0, back=0.0,
                 waist=0.0, top_in=0.0, cap0=False, hem_front=None):
    """Shell round the torso from z0 (hem) to z1. ease: m, or fn(z). gap: front opening half angle (rad) or
    fn(z); flare: extra ease at the hem fading over 0.2 m; waist: cinch at the waist; top_in: pull the top
    ring towards the neck (shoulder seam); hem_front: a cut-away hem - the front ends at this height and the
    hem sweeps down to z0 round the sides to the back (tails)."""
    b = kit.body
    rows = rows or max(5, int((z1 - z0) / 0.020))
    opened = gap is not None

    def ring(z, z_hem, th):
        e = ease(z) if callable(ease) else ease
        e = e + flare * (1.0 - M.smooth((z - z_hem) / 0.20))
        e = e - waist * math.exp(-((z - 1.04) / 0.07) ** 2)
        if z > 1.375:                                   # above the shoulder line: keep the collar opening wide
            e = e + (z - 1.375) * 0.9 - top_in
        return b.torso_ring(min(z, 1.405), e, theta=th, front=front, back=back) * (1, 1, 0) + (0, 0, z)

    rings = []
    for k, t in enumerate(np.linspace(0.0, 1.0, rows)):
        z = z0 + (z1 - z0) * t
        g = (gap(z) if callable(gap) else gap) if opened else 0.0
        th = np.linspace(g, 2 * np.pi - g, n) if opened else np.linspace(0.0, 2 * np.pi, n, endpoint=False)
        if hem_front is None:
            rings.append(ring(z, z0, th))
            continue
        # every column runs from its own hem height to the top: high at the front, z0 at the back
        off = np.abs(((th + np.pi) % (2 * np.pi)) - np.pi)          # 0 front .. pi back
        zh = hem_front + (z0 - hem_front) * M.smooth((off - 0.95) / 1.25)
        zc = zh + (z1 - zh) * t
        row = np.empty((n, 3))
        for c in range(n):
            row[c] = ring(zc[c], zh[c], th[c:c + 1])[0]
        rings.append(row)
    p = M.loft(name, None, np.array(rings), closed=not opened, outline=1.0, cap0=cap0 and not opened)
    return p.weights(M.w_torso)


def _sleeve(kit, name, side, x0, x1, ease, n=14, cuff=0.0, puff=0.0, bell=0.0):
    b = kit.body
    s = 1.0 if side == "l" else -1.0
    xs = np.linspace(x0, x1, max(4, int((x1 - x0) / 0.024)))
    rings = []
    for x in xs:
        t = (x - x0) / max(x1 - x0, 1e-6)
        e = (ease(x) if callable(ease) else ease) + puff * math.sin(min(1.0, t * 2.2) * math.pi) ** 2 \
            + bell * t ** 2.5 + cuff * M.smooth((t - 0.86) / 0.08)
        rings.append(b.arm_ring(x, e, n=n, side=s))
    return M.loft(name, None, np.array(rings), closed=True, vs=np.linspace(1.0, 0.0, len(xs))).weights(M.w_arm(side))


def _leg_shell(kit, name, side, z0, z1, ease, n=16, flare=0.0, cuff=0.0, taper=0.0):
    b = kit.body
    s = 1.0 if side == "l" else -1.0
    zs = np.linspace(z1, z0, max(4, int((z1 - z0) / 0.026)))
    rings = []
    for z in zs:
        t = (z1 - z) / max(z1 - z0, 1e-6)
        e = (ease(z) if callable(ease) else ease) + flare * t ** 2 + cuff * M.smooth((t - 0.90) / 0.06)
        if taper:
            e = e * (1.0 - taper * M.smooth((S.KNEE + 0.12 - z) / 0.30))
        rings.append(b.leg_ring(z, e, n=n, side=s))
    p = M.loft(name, None, np.array(rings), closed=True, vs=np.linspace(1.0, 0.0, len(zs)))
    return p.weights(M.w_leg(side))


def _box(name, centre, size, rot_z=0.0):
    c = np.asarray(centre, np.float64)
    hx, hy, hz = np.asarray(size, np.float64) / 2
    ca, sa = math.cos(rot_z), math.sin(rot_z)
    ax, ay = np.array([ca, sa, 0.0]), np.array([-sa, ca, 0.0])
    rings = [M.ring(c + (0, 0, z), ax, ay, hx * k, hy * k, 12, power=5.0) for z, k in
             ((-hz, 0.82), (-hz * 0.8, 1.0), (hz * 0.8, 1.0), (hz, 0.82))]
    return M.loft(name, None, np.array(rings), closed=True, cap0=True, cap1=True, outline=0.8)


# --------------------------------------------------------------------------- garments
def top(kit, color, hem=0.98, neck=1.392, ease=0.010, sleeves="long", open=0.0, v=0.0, flare=0.0, waist=0.0,
        slot="cloth", cuff=0.0, puff=0.0, bell=0.0, sleeve_to=None, sleeve_color=None, style=None,
        sleeve_style=None, thick=0.004, tail=None, front=0.0, cells=(2, 2), detail=None, hem_front=None,
        sleeve_sides=("l", "r")):
    """Shirt / blouse / jacket / coat body with optional sleeves.
    open: front opening half angle in degrees (0 = closed); v: depth (m) of a V neckline below `neck`;
    tail: hem chains to hang the part below the hips from ("skirt" | "coattail"); hem_front: cut-away front
    (the hem rises to this height at the front and falls to `hem` at the back); sleeve_sides: ("l",) for a
    one-sleeved coat (the other side is cut like a vest armhole);
    detail: painted tailoring on top of the automatic seams / fold hints / ambient shade (_top_tailoring):
    dict(placket=dict(w, buttons, color, button), zip=True, buttons=dict(n, z0, z1, x, color),
    pockets=("chest" | "chest_r" | "hip" | "flap" | "welt", ...), yoke=True, panels=True, back_seam=True,
    lapel=True | dict(z, w, color), ribs=<metres of ribbing at the hem>, plain=True); False: none at all."""
    g0 = math.radians(open)

    def gap(z):
        vv = M.smooth((z - (neck - v)) / max(v, 1e-3)) * 0.42 if v > 0 else 0.0
        return g0 + float(vv) + 1e-4

    p = _torso_shell(kit, "top", hem, neck, ease, gap=gap if (open > 0 or v > 0) else None, flare=flare,
                     waist=waist, front=front, hem_front=hem_front)
    if tail and hem < 0.90:
        p.weights(M.w_hips(0.93, 0.70, 0.55))
        hang(p, tail, 0.90, 0.90 - hem, share=0.55)
        kit.cloth_prefixes.add(tail)
    p = M.solidify(p, thick)
    opened = open > 0 or v > 0
    if detail is not False:
        style = _tailored(style, _top_tailoring(kit, hem, neck, ease, opened, g0 + 1e-4, detail))
    kit.add(p, color, slot, cells=cells, **(style or {}))
    if open <= 0:                                        # closed fronts hide the chest up to their neckline
        kit.skin["torso"] = max(kit.skin["torso"], (neck - v - 0.03) if v > 0 else neck - 0.012)
    if sleeves != "none":
        x1 = sleeve_to or {"long": S.WRIST_X - 0.012, "short": 0.300, "cap": 0.235, "elbow": 0.420}[sleeves]
        if detail is not False:
            sleeve_style = _tailored(sleeve_style, _sleeve_tailoring(kit, 0.090, x1, ease * 0.72,
                                                                    rolled=sleeves in ("elbow", "short")))
        for side in sleeve_sides:
            sl = M.solidify(_sleeve(kit, f"sleeve_{side}", side, 0.090, x1, ease * 0.72, cuff=cuff, puff=puff, bell=bell),
                            thick * 0.8)
            kit.add(sl, sleeve_color or color, slot, cells=(1, 2 if (cells[1] > 1 and x1 > 0.45) else 1),
                    **(sleeve_style or {}))
        kit.cover_arms(0.0, x1)
    else:
        kit.cover_arms(0.0, 0.155)


def skirt(kit, color, waist=1.035, length=0.36, flare=0.55, pleats=14, style=None, ease=0.008, slot="cloth",
          thick=0.004, layers=1, under=None):
    b = kit.body
    n = pleats * 4
    th = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    hem = waist - length
    for layer in range(layers):
        zs = np.linspace(waist + 0.012, hem + 0.035 * layer, 16)
        saw = np.abs(((th / (2 * np.pi) * pleats) % 1.0) - 0.5) * 2.0        # 0..1 triangle per pleat
        fold = np.where(((th / (2 * np.pi) * pleats) % 1.0) < 0.5, 1.0, 0.35)
        rings = []
        for z in zs:
            t = (waist - z) / length
            zb = max(z, 0.875)
            base = b.torso_ring(zb, ease + 0.004 * layer + 0.010 * M.smooth((waist - z) / 0.06), theta=th)
            k = 1.0 + flare * max(0.0, t) ** 0.85 * (1.0 + 0.10 * layer)
            amp = 0.13 * max(0.0, t) ** 1.1
            cen = np.array([0.0, b.centre_y(zb)])
            r = cen + (base[:, :2] - cen) * (k * (1.0 + amp * (saw * fold - 0.5)))[:, None]
            rings.append(np.column_stack([r, np.full(n, z)]))
        p = M.loft("skirt", None, np.array(rings), closed=True, vs=np.linspace(1.0, 0.0, len(zs)))
        p.weights(M.w_hips(0.95, 0.72, 0.55))
        hang(p, "skirt", waist - 0.07, length - 0.07)
        p = M.solidify(p, thick)
        st = _tailored(style, dict(dims=(_perim(rings[len(rings) // 2]), length), wrap=True,
                                   pleats=dict(n=pleats, depth=0.55), shade=dict(top=(0.03, 0.30), bottom=(0.07, 0.14)),
                                   seams=[("v", 1.0 - 0.030 / length, None, None)],
                                   stitch=[("v", 0.012 / length, None, None)]))
        kit.add(p, (under or color) if layer else color, slot, cells=(4, 2), **(st if not layer else {}))
    kit.cloth_prefixes.add("skirt")
    kit.cover_legs(hem + 0.06, 1.0)
    # shorts under the skirt so nothing is bare from below
    for side in ("l", "r"):
        s = _leg_shell(kit, "under", side, max(hem + 0.05, 0.74), 0.90, 0.003)
        kit.add(s, P.shade(color, v=0.74), "cloth", cells=(1, 1))
    hip = _torso_shell(kit, "under_hip", 0.80, 0.93, 0.002, n=28, cap0=True)
    kit.add(hip, P.shade(color, v=0.74), "cloth")


def pants(kit, color, waist=1.03, hem=0.10, ease=0.012, flare=0.0, cuff=0.0, style=None, slot="cloth",
          leg_style=None, taper=0.0, crease=True, detail=None):
    """Trousers / shorts. taper: how much of the ease the legs lose from the knee down (0..1: straight ->
    slim); crease: pressed front crease; detail=False: no painted tailoring."""
    hip_ease = lambda z: ease * (0.6 + 0.4 * M.smooth((1.0 - z) / 0.1))
    hip = _torso_shell(kit, "pants_hip", 0.80, waist, hip_ease, n=36, cap0=True)
    hip.weights(M.w_hips(0.93, 0.80, 0.55))
    if detail is not False:
        style = _tailored(style, _hip_tailoring(kit, 0.80, waist, ease * 0.8))
        leg_style = _tailored(leg_style, _leg_tailoring(kit, hem, 0.885, ease, crease=crease))
    kit.add(hip, color, slot, cells=(2, 1), **(style or {}))
    for side in ("l", "r"):
        leg = _leg_shell(kit, f"pants_{side}", side, hem, 0.885, ease, flare=flare, cuff=cuff, taper=taper)
        leg = M.solidify(leg, 0.003) if hem > 0.12 else leg
        kit.add(leg, color, slot, cells=(1, 2), **(leg_style or {}))
    kit.cover_legs(hem, 1.0)


def legwear(kit, color, top=0.60, style=None, ease=0.0018, bottom=S.ANKLE - 0.01):
    """Socks / stockings / thigh-highs up to `top`."""
    for side in ("l", "r"):
        leg = _leg_shell(kit, f"sock_{side}", side, bottom, top, ease, cuff=0.0)
        leg.outline *= 0.8
        H = top - bottom
        st = _tailored(style, dict(dims=(_perim(kit.body.leg_ring(0.5 * (top + bottom), ease)), H), wrap=True,
                                   shade=dict(bottom=(0.05, 0.12), under=[(1.0 - 0.012 / H, 0.012, 0.25)]),
                                   ribs=dict(n=22, v0=1.0 - 0.030 / H, depth=0.22)))
        kit.add(leg, color, "cloth", cells=(1, 2), **st)
    kit.cover_legs(0.0, top)


def shoes(kit, color, kind="loafer", shaft=0.0, sole=(0.16, 0.14, 0.15), style=None, heel=0.0, cuff=0.0,
          toe=None):
    """Footwear. kind: loafer | sneaker | boot; shaft: top of the boot shaft (z)."""
    b = kit.body
    ys = np.array([0.046, 0.030, 0.000, -0.045, -0.095, -0.140, -0.168, -0.180])
    hw = np.array([0.022, 0.032, 0.036, 0.038, 0.041, 0.038, 0.028, 0.012])
    ht = np.array([0.070, 0.092, 0.100, 0.078, 0.052, 0.040, 0.032, 0.018])
    if kind == "sneaker":
        hw, ht = hw * 1.06, ht * 1.05
    base = 0.012 + heel
    for side, s in (("l", 1.0), ("r", -1.0)):
        rings = []
        for y, w, h in zip(ys, hw, ht):
            lift = heel * M.smooth((y + 0.06) / 0.09)
            rings.append(M.ring((s * S.HIP_X, y, base + lift * 0.0 + h * 0.5), (1, 0, 0), (0, 0, 1), w, h * 0.5,
                                14, power=2.7))
        up = M.loft(f"shoe_{side}", None, np.array(rings), closed=True, cap0=True, cap1=True)
        up.uv[:, 1] = np.clip((up.v[:, 2] - base) / 0.10, 0.0, 1.0)
        up.weights(M.w_leg(side, hip=False))
        kit.add(up, color, "cloth", **(style or {}))
        srings = [M.ring((s * S.HIP_X, y, z), (1, 0, 0), (0, 0, 1), w + 0.003, 0.004, 14, power=4.0)
                  for z in (0.004, base + 0.002) for y, w in zip(ys, hw)]
        srings = np.array(srings).reshape(2, len(ys), 14, 3)
        for layer in srings:
            so = M.loft(f"sole_{side}", None, layer, closed=True, cap0=True, cap1=True, outline=0.6)
            so.weights(M.w_leg(side, hip=False))
            kit.add(so, sole, "cloth")
        if heel > 0:
            hl = _box(f"heel_{side}", (s * S.HIP_X, 0.028, base * 0.5), (0.040, 0.036, base))
            hl.weights(M.w_leg(side, hip=False))
            kit.add(hl, sole, "cloth")
        if toe is not None:
            cap = M.loft(f"toe_{side}", None, np.array(rings[-4:]) + (0, -0.001, 0.001), closed=True, cap1=True,
                         outline=0.0)
            cap.v = (cap.v - (s * S.HIP_X, 0, base)) * (1.03, 1.0, 1.04) + (s * S.HIP_X, 0, base)
            cap.weights(M.w_leg(side, hip=False))
            kit.add(cap, toe, "cloth")
        if shaft > 0.11:
            sh = _leg_shell(kit, f"shaft_{side}", side, 0.075, shaft, 0.007, cuff=cuff)
            sh = M.solidify(sh, 0.004)
            kit.add(sh, color, "cloth", cells=(1, 2), **(style or {}))
    if shaft > 0.11:
        kit.cover_legs(0.0, shaft - 0.02)
    kit.cover_legs(0.0, S.ANKLE + 0.02)


def collar(kit, color, kind="shirt", style=None, size=1.0, slot="cloth", z=1.398):
    """shirt: folded collar with points; stand: upright band; sailor: flap over the shoulders and back."""
    b = kit.body
    r0 = b.neck_r + 0.006
    if kind in ("shirt", "stand"):
        g = math.radians(16 if kind == "shirt" else 9)
        th = np.linspace(g, 2 * np.pi - g, 38 if kind == "shirt" else 30)
        c, s = np.cos(th), np.sin(th)
        rows = []
        if kind == "shirt":
            # a folded collar: the stand rises round the neck, the leaf turns over and lies on the shoulders,
            # running out into two points over the chest
            d = (np.minimum(th, 2 * np.pi - th) - g) / 0.42
            point = np.exp(-d ** 2)
            back = M.smooth((-c - 0.2) / 0.8)
            for dz, dr, k in ((0.000, 0.000, 0.0), (0.030, 0.002, 0.0), (0.035, 0.009, 0.0), (0.024, 0.021, 0.45),
                              (0.008, 0.034 * size, 1.0)):
                rr = r0 + dr * (1.0 + 0.30 * point * k)
                zz = z + dz - (0.034 * size * point + 0.006 * back) * k
                y = -c * rr * 1.08 + b.neck_c(z + dz) - 0.010 * point * k
                rows.append(np.column_stack([s * rr * (1.0 + 0.10 * point * k), y, zz]))
        else:
            for dz, dr in ((0.000, 0.004), (0.020 * size, 0.004), (0.038 * size, 0.008)):
                rr = r0 + dr
                y = -c * rr * 1.08 + b.neck_c(z + dz)
                rows.append(np.column_stack([s * rr, y, np.full(len(th), z + dz)]))
        p = M.loft("collar", None, np.array(rows), closed=False)
        p = M.solidify(p.weights(M.w_spine), 0.003)
        kit.add(p, color, slot, **(style or {}))
    else:
        g = math.radians(7)
        th = np.linspace(g, 2 * np.pi - g, 48)
        c = np.cos(th)
        front = M.smooth((c - 0.25) / 0.75)                  # 1 at the chest centre
        backw = M.smooth((-c - 0.35) / 0.5)                  # 1 across the back
        drop = 0.022 + 0.115 * size * front ** 1.5 + 0.095 * size * backw
        rows = []
        ks = np.linspace(0.0, 1.0, 7)
        for k in ks:
            zz = 1.408 - drop * k
            pts = np.array([b.torso_ring(float(zq), 0.014 + 0.003 * k, theta=np.array([tq]))[0]
                            for zq, tq in zip(np.minimum(zz, 1.405), th)])
            # the flap narrows towards the V point at the front
            pts[:, 0] *= 1.0 - 0.55 * front * k
            pts[:, 2] = zz
            rows.append(pts)
        p = M.loft("sailor", None, np.array(rows), closed=False, vs=np.linspace(1.0, 0.0, len(ks)))
        p = M.solidify(p.weights(M.w_torso), 0.003)
        kit.add(p, color, slot, cells=(2, 1), **(style or {}))


def bow(kit, color, z=1.335, size=1.0, tails=0.06, y=None, x=0.0, bone=None, style=None, knot=None):
    """Ribbon bow (chest by default; give `bone` + position for hair bows)."""
    b = kit.body
    if y is None:
        y = b.front_y(z) - 0.022
    c = np.array([x, y, z])
    parts = []
    for sx in (1.0, -1.0):
        t = np.linspace(0.0, 1.0, 9)
        path = c + np.column_stack([sx * 0.056 * size * t, 0.004 * np.sin(t * np.pi), 0.016 * size * t ** 1.3])
        r = 0.019 * size * np.sin(np.clip(t * 0.92 + 0.10, 0, 1) * np.pi * 0.62) ** 0.8 + 0.003
        parts.append(M.tube("bow", None, path, r, n=10, up=(0, 1, 0), flat=0.24, power=2.6))
        if tails:
            tp = c + np.column_stack([sx * (0.008 + 0.026 * t ** 1.2), -0.004 * t, -tails * t])
            parts.append(M.tube("bowtail", None, tp, 0.010 * size * (0.75 + 0.55 * t), n=8, up=(0, 1, 0), flat=0.20,
                                power=3.0))
    parts.append(_box("knot", c, (0.018 * size, 0.014, 0.020 * size)))
    for i, p in enumerate(parts):
        p.rigid(bone) if bone else p.weights(M.w_spine)
        kit.add(p, (knot or color) if i == len(parts) - 1 else color, "cloth", **(style or {}))


def tie(kit, color, z=1.375, length=0.20, style=None):
    b = kit.body
    t = np.linspace(0.0, 1.0, 9)
    zz = z - length * t
    y = np.array([b.front_y(q) for q in zz]) - 0.020
    w = 0.014 + 0.016 * np.sin(np.clip(t * 1.15, 0, 1) * np.pi * 0.5) - 0.020 * M.smooth((t - 0.86) / 0.14)
    p = M.tube("tie", None, np.column_stack([np.zeros(9), y, zz]), w, n=8, up=(0, 1, 0), flat=0.22)
    kit.add(p.weights(M.w_spine), color, "cloth", **(style or {}))
    kit.add(_box("tieknot", (0, y[0] + 0.002, z + 0.004), (0.026, 0.014, 0.024)).weights(M.w_spine), color, "cloth")


def belt(kit, color, z=1.02, width=0.026, buckle=(0.86, 0.70, 0.30), pouch=None, ease=0.016, tilt=0.0):
    """Belt with a buckle; pouch: colour of a deck box worn on the left hip."""
    b = kit.body
    th = np.linspace(0.0, 2 * np.pi, 40, endpoint=False)
    rings = []
    for dz in (-width / 2, width / 2):
        r = b.torso_ring(z + dz, ease, theta=th)
        r[:, 2] += tilt * np.sin(th) * 0.5
        rings.append(r)
    p = M.solidify(M.loft("belt", None, np.array(rings), closed=True), 0.004)
    kit.add(p.weights(M.w_spine), color, "cloth")
    fy = b.front_y(z) - ease
    bk = _box("buckle", (0, fy - 0.004, z), (0.036, 0.010, width * 1.30))
    kit.add(bk.weights(M.w_spine), buckle, "cloth")
    # a frame buckle: the belt shows through its window, a prong across it
    kit.add(_box("buckle", (0, fy - 0.0075, z), (0.024, 0.006, width * 0.78)).weights(M.w_spine), color, "cloth")
    kit.add(_box("buckle", (0.002, fy - 0.0095, z), (0.020, 0.004, width * 0.20)).weights(M.w_spine), buckle, "cloth")
    if pouch is not None:
        a = b.side_x(z - 0.04)
        cy = b.centre_y(z - 0.04)
        bx = _box("deckbox", (a + ease + 0.016, cy - 0.012, z - 0.045), (0.030, 0.062, 0.080))
        kit.add(bx.weights(M.w_spine), pouch, "cloth", hem=[(0.0, pouch)], top=[(0.30, P.shade(pouch, v=0.7))])
        clasp = _box("clasp", (a + ease + 0.033, cy - 0.012, z - 0.030), (0.006, 0.016, 0.016))
        kit.add(clasp.weights(M.w_spine), buckle, "cloth")


def band(kit, color, side="l", x=0.27, width=0.035, ease=0.012, style=None):
    """Arm band / bracelet / cuff."""
    for sd in (("l", "r") if side == "both" else (side,)):
        p = M.solidify(_sleeve(kit, f"band_{sd}", sd, x - width / 2, x + width / 2, ease), 0.003)
        kit.add(p, color, "cloth", **(style or {}))


def gloves(kit, color, cuff=0.60, style=None, fingerless=False):
    b = kit.body
    for side in ("l", "r"):
        if not fingerless:
            h = b.hand(None, side, scale=(0.88 if b.female else 1.0) * 1.06)
            h.uv[:] = 0.5
            kit.add(h, color, "cloth")
        p = M.solidify(_sleeve(kit, f"glove_{side}", side, cuff, S.WRIST_X + (0.045 if fingerless else 0.004), 0.006,
                               cuff=0.0), 0.003)
        kit.add(p, color, "cloth", **(style or {}))
    kit.cover_arms(cuff, S.WRIST_X + 0.1)
    kit.skin["hands"] = fingerless


def cape(kit, color, length=0.55, spread=110.0, style=None, top=1.385, flare=0.10, lining=None):
    """Cape hanging down the back from the shoulders."""
    b = kit.body
    a0 = math.radians(180.0 - spread)
    th = np.linspace(a0, 2 * np.pi - a0, 26)
    rows = []
    zs = np.linspace(top, top - length, 12)
    for z in zs:
        t = (top - z) / length
        ring_ = b.torso_ring(np.clip(z, 0.86, 1.375), 0.026 + flare * t ** 1.3, theta=th)
        ring_[:, :2] *= 1.0 + 0.03 * np.sin(th * 9.0)[:, None] * t
        ring_[:, 2] = z
        rows.append(ring_)
    p = M.loft("cape", None, np.array(rows), closed=False, vs=np.linspace(1.0, 0.0, len(zs)))
    p.weights(M.w_torso)
    hang(p, "coattail", top - 0.16, length - 0.16, share=0.85)
    kit.cloth_prefixes.add("coattail")
    kit.add(M.solidify(p, 0.004), color, "cloth", cells=(2, 2), **(style or {}))
    clasp = _box("capeclasp", (0, b.front_y(1.36) - 0.02, 1.365), (0.03, 0.012, 0.02))
    kit.add(clasp.weights(M.w_spine), (lining or (0.86, 0.70, 0.30)), "cloth")


def scarf(kit, color, style=None, tail=0.22):
    b = kit.body
    th = np.linspace(0.0, 2 * np.pi, 22)
    nc = b.neck_c(1.404)
    path = np.column_stack([np.sin(th) * (b.neck_r + 0.020), -np.cos(th) * (b.neck_r + 0.024) + nc,
                            1.420 + 0.006 * np.cos(th)])
    p = M.tube("scarf", None, path, 0.022, n=10, flat=0.85, cap0=False, cap1=False)
    kit.add(p.weights(M.w_spine), color, "cloth", **(style or {}))
    t = np.linspace(0.0, 1.0, 8)
    tp = np.column_stack([0.030 + 0.02 * t, nc - 0.002 - b.neck_r - 0.045 - 0.03 * np.sin(t * 2.0), 1.415 - tail * t])
    tl = M.tube("scarftail", None, tp, 0.024 + 0.006 * t, n=8, up=(0, 1, 0), flat=0.25)
    kit.add(tl.weights(M.w_spine), color, "cloth", **(style or {}))
    kit.skin["torso"] = max(kit.skin["torso"], 1.39)


def emblem(kit, color, z=1.27, x=0.062, size=0.016, kind="star", lift=0.024):
    """Small badge on the chest (original geometric marks: star | diamond | disc)."""
    b = kit.body
    n = {"star": 10, "diamond": 4, "disc": 16}[kind]
    a = np.linspace(0, 2 * np.pi, n, endpoint=False) + (math.pi / 2)
    r = np.where(np.arange(n) % 2 == 0, 1.0, 0.45) * size if kind == "star" else np.full(n, size)
    ring0 = []
    for ai, ri in zip(a, r):
        px, pz = x + math.cos(ai) * ri, z + math.sin(ai) * ri
        ring0.append((px, b.front_y(pz, px) - lift, pz))
    ring0 = np.array(ring0)
    p = M.loft("emblem", None, np.array([ring0, ring0 + (0, -0.003, 0)]), closed=True, cap1=True, outline=0.6)
    kit.add(p.weights(M.w_torso), color, "cloth")


def buttons(kit, color, z0=1.08, z1=1.30, n=3, x=0.022, r=0.008, double=False):
    b = kit.body
    for z in np.linspace(z0, z1, n):
        for sx in ((1.0, -1.0) if double else (1.0,)):
            c = np.array([sx * x, b.front_y(z) - 0.017, z])
            rings = [M.ring(c + (0, -d, 0), (1, 0, 0), (0, 0, 1), r * k, r * k, 10) for d, k in ((0, 1.0), (0.004, 0.8))]
            p = M.loft("button", None, np.array(rings), closed=True, cap1=True, outline=0.5)
            kit.add(p.weights(M.w_spine), color, "cloth")


def hairband(kit, color, head, width=0.012, at=0.20, style=None):
    """Band over the top of the head from ear to ear."""
    th = np.linspace(np.radians(-96), np.radians(96), 22)
    rows = []
    for ds in (-width, width):
        s = at + ds * 2.2 + 0.30 * np.abs(np.sin(th)) ** 2.2
        rows.append(head.scalp(th, s, 0.041)[0])
    p = M.solidify(M.loft("hairband", None, np.array(rows), closed=False), 0.004)
    kit.add(p.rigid("head"), color, "cloth", **(style or {}))


def glasses(kit, color, head, round_=0.9, lens=None):
    e = head.eye
    rw, rh = e["hw"] * 1.22, e["h"] * 0.60 * (0.8 + 0.4 * round_)
    for sx in (1.0, -1.0):
        a = np.linspace(0, 2 * np.pi, 20, endpoint=False)
        pw = 2.0 + (1.0 - round_) * 3.0
        x = sx * e["cx"] + np.sign(np.cos(a)) * np.abs(np.cos(a)) ** (2 / pw) * rw
        z = e["cz"] + 0.001 + np.sign(np.sin(a)) * np.abs(np.sin(a)) ** (2 / pw) * rh
        path = head.project(x, z, 0.012)
        path = np.concatenate([path, path[:1]])
        p = M.tube("rim", None, path, 0.0011, n=6, cap0=False, cap1=False, outline=0.0)
        kit.add(p.rigid("head"), color, "cloth")
        ear = head.project(np.array([sx * (e["cx"] + rw)]), np.array([e["cz"] + 0.003]), 0.012)[0]
        arm_ = np.array([ear, ear + (sx * 0.012, 0.085, 0.004)])
        kit.add(M.tube("temple", None, arm_, 0.0010, n=5, outline=0.0).rigid("head"), color, "cloth")
    br = head.project(np.array([-0.012, 0.0, 0.012]), np.full(3, e["cz"] + 0.004), 0.013)
    kit.add(M.tube("bridge", None, br, 0.0010, n=5, outline=0.0).rigid("head"), color, "cloth")


def _strap_part(name, P, N, width, thick):
    """Flat strap along points P (K, 3) lying on a surface with outward normals N: a thin box section."""
    tan = np.gradient(P, axis=0)
    tan /= np.maximum(np.linalg.norm(tan, axis=1, keepdims=True), 1e-12)
    side = np.cross(N, tan)
    side /= np.maximum(np.linalg.norm(side, axis=1, keepdims=True), 1e-12)
    h = width / 2
    rings = np.stack([P + side * h + N * thick, P - side * h + N * thick, P - side * h, P + side * h], axis=1)
    return M.loft(name, None, rings, closed=True, cap0=True, cap1=True, outline=0.7)


def _buckle(kit, at, normal, color, strap_color, size=(0.030, 0.026), name="buckle"):
    """Frame buckle lying on a strap: plate, window showing the strap, prong."""
    n = np.asarray(normal, np.float64)
    rot = math.atan2(-n[0], n[1])
    w, h = size
    for off, (sx, sy, sz), col in ((0.004, (w, 0.008, h), color), (0.0075, (w * 0.66, 0.005, h * 0.6), strap_color),
                                   (0.0095, (w * 0.10, 0.004, h * 0.62), color)):
        kit.add(_box(name, np.asarray(at) + n * off, (sx, sy, sz), rot_z=rot).weights(M.w_spine), col, "cloth")


def _on_torso(b, path, ease):
    """Points (K, 3) and outward normals of a [(z, azimuth deg)] path on the torso surface."""
    path = np.asarray(path, np.float64)
    seg = np.linspace(0.0, 1.0, len(path))
    t = np.linspace(0.0, 1.0, max(24, 12 * len(path)))
    zs = np.interp(t, seg, path[:, 0])
    th = np.radians(np.interp(t, seg, path[:, 1]))
    Q = np.array([b.torso_ring(min(z, 1.405), ease, theta=[a])[0] for z, a in zip(zs, th)])
    Q[:, 2] = zs
    cy = np.array([b.centre_y(min(z, 1.405)) for z in zs])
    N = np.stack([Q[:, 0], Q[:, 1] - cy, np.zeros(len(Q))], axis=1)
    N[:, 2] = np.clip(zs - 1.36, 0.0, None) * 6.0              # near the shoulder line the strap faces up
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    return Q, N


def strap(kit, color, path, width=0.024, ease=0.012, thick=0.0035, buckles=(), buckle=(0.80, 0.82, 0.86),
          pouch=None, style=None, name="strap", over=None, rise=0.040):
    """Strap lying on the torso along `path` [(z, azimuth deg)] (0 = front centre, + = the character's left;
    straps over the shoulder start at z ~1.425); buckles: fractions along it; pouch: (fraction, colour) of a
    small pouch hanging from it; over: the back half's path (from the shoulder down) - the strap then runs
    over the shoulder, `rise` metres above the shoulder line, as one piece."""
    b = kit.body
    Q, N = _on_torso(b, path, ease)
    if over is not None:
        Qb, Nb = _on_torso(b, over, ease)
        nf = len(Q)
        front_i = lambda f: nf - 1 - int(round(f * (nf - 1)))      # index along the front half, after reversing
        p0, p2 = Q[0], Qb[0]
        p1 = 0.5 * (p0 + p2) + np.array([0.0, 0.0, rise])
        s = np.linspace(0.0, 1.0, 12)[1:-1, None]
        bridge = (1 - s) ** 2 * p0 + 2 * (1 - s) * s * p1 + s ** 2 * p2
        up = np.array([0.0, 0.0, 1.0])
        nb = np.array([_n / np.linalg.norm(_n) for _n in (up * 0.8 + (1 - s) * N[0] * 0.4 + s * Nb[0] * 0.4)])
        Q = np.concatenate([Q[::-1], bridge, Qb])
        N = np.concatenate([N[::-1], nb, Nb])
        tot = len(Q) - 1
        buckles = [front_i(f) / tot for f in buckles]
        if pouch is not None:
            pouch = (front_i(pouch[0]) / tot, pouch[1])
    st = dict(edge=[(0.10, P.shade(color, v=0.70))], stitch=[("u", 0.22, 0.0, 1.0), ("u", 0.78, 0.0, 1.0)])
    st.update(style or {})
    kit.add(_strap_part(name, Q, N, width, thick).weights(M.w_spine), color, "cloth", **st)
    for f in buckles:
        i = int(round(f * (len(Q) - 1)))
        _buckle(kit, Q[i] + N[i] * thick, N[i], buckle, color)
    if pouch is not None:
        f, col = pouch
        i = int(round(f * (len(Q) - 1)))
        c = Q[i] + N[i] * (thick + 0.016) + np.array([0.0, 0.0, -0.035])
        rot = math.atan2(-N[i][0], N[i][1])
        kit.add(_box("deckbox", c, (0.058, 0.026, 0.072), rot_z=rot).weights(M.w_spine), col, "cloth",
                top=[(0.30, P.shade(col, v=0.72))], hem=[(0.06, P.shade(col, v=0.8))])
        _buckle(kit, c + N[i] * 0.013 + np.array([0.0, 0.0, 0.014]), N[i], buckle, col, size=(0.014, 0.016),
                name="clasp")


def legstrap(kit, color, side="r", z=0.72, width=0.026, ease=0.006, buckle=(0.80, 0.82, 0.86), pouch=None):
    """Strap round the thigh with a buckle on the outer front; pouch: colour of a slim pouch on the outside."""
    b = kit.body
    s = 1.0 if side == "l" else -1.0
    p = M.solidify(_leg_shell(kit, f"legstrap_{side}", side, z - width / 2, z + width / 2, ease), 0.003)
    kit.add(p, color, "cloth", edge=[(0.12, P.shade(color, v=0.7))])
    ring = b.leg_ring(z, ease + 0.003, n=24, side=s)
    cx = float(ring[:, 0].mean())
    cyy = float(ring[:, 1].mean())
    for ang, what in ((0.62, "buckle"), (0.0, "pouch")):
        q = ring[int(round(ang / (2 * math.pi) * 24)) % 24]
        n = np.array([q[0] - cx, q[1] - cyy, 0.0])
        n /= max(np.linalg.norm(n), 1e-9)
        if what == "buckle":
            _buckle(kit, q, n, buckle, color, size=(0.024, 0.022))
        elif pouch is not None:
            rot = math.atan2(-n[0], n[1])
            box = _box("deckbox", q + n * 0.016 + np.array([0.0, 0.0, -0.030]), (0.024, 0.060, 0.080), rot_z=rot)
            kit.add(box.weights(M.w_leg(side)), pouch, "cloth", top=[(0.28, P.shade(pouch, v=0.72))])
    kit.cover_legs(z - width / 2, z + width / 2)


def bracer(kit, color, side="r", x0=0.43, x1=0.57, trim=(0.90, 0.72, 0.30), disk=(0.20, 0.21, 0.26),
           glow=(0.95, 0.55, 0.20)):
    """Armoured forearm guard carrying a compact duel-disk plate: a hard shell with raised rims, segment
    lines, and a round disk with a lit ring on the back of the forearm."""
    sh = M.solidify(_sleeve(kit, f"band_bracer_{side}", side, x0, x1, 0.016), 0.005)
    kit.add(sh, color, "cloth", hem=[(0.10, trim)], top=[(0.10, trim)],
            seams=[("v", 0.38, None, None), ("v", 0.62, None, None)])
    for x in (x0 + 0.006, x1 - 0.006):
        rim = M.solidify(_sleeve(kit, f"band_rim_{side}", side, x - 0.006, x + 0.006, 0.022), 0.003)
        kit.add(rim, trim, "cloth")
    # the disk: a low cylinder on the back of the forearm (+z in the T-pose design space), a lit ring round it
    b = kit.body
    s = 1.0 if side == "l" else -1.0
    xm = 0.5 * (x0 + x1)
    top = b.arm_ring(xm, 0.022, n=24, side=s)
    c = top[int(np.argmax(top[:, 2]))].copy()
    for name, r, h0, h1, col in (("band_disk", 0.040, 0.000, 0.010, disk), ("band_diskring", 0.030, 0.010, 0.0125, glow),
                                 ("band_diskhub", 0.016, 0.0125, 0.016, color)):
        rings = [M.ring(c + (0, 0, h), (1, 0, 0), (0, 1, 0), r * k, r * k, 24) for h, k in ((h0, 1.0), (h1, 0.94))]
        p = M.loft(f"{name}_{side}", None, np.array(rings), closed=True, cap0=True, cap1=True, outline=0.6)
        kit.add(p.weights(M.w_arm(side)), col, "cloth")
    kit.cover_arms(x0, x1)


GARMENTS = dict(top=top, skirt=skirt, pants=pants, legwear=legwear, shoes=shoes, collar=collar, bow=bow, tie=tie,
                belt=belt, band=band, gloves=gloves, cape=cape, scarf=scarf, emblem=emblem, buttons=buttons,
                strap=strap, legstrap=legstrap, bracer=bracer)
