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
        self.cloth_prefixes = set()
        # visible skin: torso from this height up, arm / leg intervals
        self.skin = dict(torso=0.80, arms=[(0.09, S.WRIST_X)], legs=[(S.ANKLE, 0.90)], hands=True)

    def add(self, part, color, slot="cloth", cells=(1, 1), **style):
        atlas = self.atlas[slot] or self.atlas["cloth"]
        slot = slot if self.atlas[slot] is not None else "cloth"
        if style:
            rect = atlas.paint(atlas.alloc(*cells), color, **style)
            part.uv = atlas.uv(rect, part.uv)
        else:
            rect = atlas.swatch(color)
            part.uv = atlas.uv(rect, np.full((len(part.v), 2), 0.5), inset=8.0)
        part.mat = self.mats[slot]
        part.face_mat = None
        self.parts.append(part)
        return part

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
        specs = {}
        for slot, atlas in self.atlas.items():
            if atlas is None:
                continue
            name = self.mats[slot]
            rel = f"{tex_rel}/T_{name[2:]}"
            atlas.save(os.path.join(tex_dir, rel + ".png"))
            specs[name] = dict(kind="toon", color=(1.0, 1.0, 1.0), rough=0.85, fill=0.5, base=rel)
        return specs


# --------------------------------------------------------------------------- shells
def _torso_shell(kit, name, z0, z1, ease, n=44, gap=None, flare=0.0, rows=None, front=0.0, back=0.0,
                 waist=0.0, top_in=0.0):
    """Shell round the torso from z0 (hem) to z1. ease: m, or fn(z). gap: front opening half angle (rad) or
    fn(z); flare: extra ease at the hem fading over 0.2 m; waist: cinch at the waist; top_in: pull the top
    ring towards the neck (shoulder seam)."""
    b = kit.body
    rows = rows or max(5, int((z1 - z0) / 0.020))
    zs = np.linspace(z0, z1, rows)
    rings = []
    opened = gap is not None
    for z in zs:
        e = ease(z) if callable(ease) else ease
        e = e + flare * (1.0 - M.smooth((z - z0) / 0.20))
        e = e - waist * math.exp(-((z - 1.04) / 0.07) ** 2)
        if z > 1.375:                                   # above the shoulder line: keep the collar opening wide
            e = e + (z - 1.375) * 0.9 - top_in
        g = (gap(z) if callable(gap) else gap) if opened else 0.0
        th = np.linspace(g, 2 * np.pi - g, n) if opened else np.linspace(0.0, 2 * np.pi, n, endpoint=False)
        rings.append(b.torso_ring(min(z, 1.405), e, theta=th, front=front, back=back) * (1, 1, 0) + (0, 0, z))
    p = M.loft(name, None, np.array(rings), closed=not opened, outline=1.0)
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


def _leg_shell(kit, name, side, z0, z1, ease, n=16, flare=0.0, cuff=0.0):
    b = kit.body
    s = 1.0 if side == "l" else -1.0
    zs = np.linspace(z1, z0, max(4, int((z1 - z0) / 0.026)))
    rings = []
    for z in zs:
        t = (z1 - z) / max(z1 - z0, 1e-6)
        e = (ease(z) if callable(ease) else ease) + flare * t ** 2 + cuff * M.smooth((t - 0.90) / 0.06)
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
        sleeve_style=None, thick=0.004, tail=None, front=0.0, cells=(2, 2)):
    """Shirt / blouse / jacket / coat body with optional sleeves.
    open: front opening half angle in degrees (0 = closed); v: depth (m) of a V neckline below `neck`;
    tail: hem chains to hang the part below the hips from ("skirt" | "coattail")."""
    g0 = math.radians(open)

    def gap(z):
        vv = M.smooth((z - (neck - v)) / max(v, 1e-3)) * 0.42 if v > 0 else 0.0
        return g0 + float(vv) + 1e-4

    p = _torso_shell(kit, "top", hem, neck, ease, gap=gap if (open > 0 or v > 0) else None, flare=flare,
                     waist=waist, front=front)
    if tail and hem < 0.90:
        p.weights(M.w_hips(0.93, 0.70, 0.55))
        hang(p, tail, 0.90, 0.90 - hem, share=0.55)
        kit.cloth_prefixes.add(tail)
    p = M.solidify(p, thick)
    kit.add(p, color, slot, cells=cells, **(style or {}))
    if open <= 0:                                        # closed fronts hide the chest up to their neckline
        kit.skin["torso"] = max(kit.skin["torso"], (neck - v - 0.03) if v > 0 else neck - 0.012)
    if sleeves != "none":
        x1 = sleeve_to or {"long": S.WRIST_X - 0.012, "short": 0.300, "cap": 0.235, "elbow": 0.420}[sleeves]
        for side in ("l", "r"):
            sl = M.solidify(_sleeve(kit, f"sleeve_{side}", side, 0.090, x1, ease * 0.72, cuff=cuff, puff=puff, bell=bell),
                            thick * 0.8)
            kit.add(sl, sleeve_color or color, slot, cells=(1, 1), **(sleeve_style or {}))
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
            r = base[:, :2] * (k * (1.0 + amp * (saw * fold - 0.5)))[:, None]
            rings.append(np.column_stack([r, np.full(n, z)]))
        p = M.loft("skirt", None, np.array(rings), closed=True, vs=np.linspace(1.0, 0.0, len(zs)))
        p.weights(M.w_hips(0.95, 0.72, 0.55))
        hang(p, "skirt", waist - 0.07, length - 0.07)
        p = M.solidify(p, thick)
        st = dict(style or {})
        kit.add(p, (under or color) if layer else color, slot, cells=(2, 1), **(st if not layer else {}))
    kit.cloth_prefixes.add("skirt")
    kit.cover_legs(hem + 0.06, 1.0)
    # shorts under the skirt so nothing is bare from below
    for side in ("l", "r"):
        s = _leg_shell(kit, "under", side, max(hem + 0.05, 0.74), 0.90, 0.003)
        kit.add(s, P.shade(color, v=0.55), "cloth", cells=(1, 1))
    hip = _torso_shell(kit, "under_hip", 0.80, 0.93, 0.002, n=28)
    kit.add(hip, P.shade(color, v=0.55), "cloth")


def pants(kit, color, waist=1.03, hem=0.10, ease=0.012, flare=0.0, cuff=0.0, style=None, slot="cloth",
          leg_style=None):
    hip = _torso_shell(kit, "pants_hip", 0.80, waist, lambda z: ease * (0.6 + 0.4 * M.smooth((1.0 - z) / 0.1)), n=36)
    hip.weights(M.w_hips(0.93, 0.80, 0.55))
    kit.add(hip, color, slot, **(style or {}))
    for side in ("l", "r"):
        leg = _leg_shell(kit, f"pants_{side}", side, hem, 0.885, ease, flare=flare, cuff=cuff)
        leg = M.solidify(leg, 0.003) if hem > 0.12 else leg
        kit.add(leg, color, slot, cells=(1, 2), **(leg_style or {}))
    kit.cover_legs(hem, 1.0)


def legwear(kit, color, top=0.60, style=None, ease=0.0018, bottom=S.ANKLE - 0.01):
    """Socks / stockings / thigh-highs up to `top`."""
    for side in ("l", "r"):
        leg = _leg_shell(kit, f"sock_{side}", side, bottom, top, ease, cuff=0.0)
        leg.outline *= 0.8
        kit.add(leg, color, "cloth", cells=(1, 2), **(style or {}))
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
        th = np.linspace(g, 2 * np.pi - g, 30)
        c, s = np.cos(th), np.sin(th)
        rows = []
        prof = ((0.034, 0.000), (0.036, 0.010), (0.018, 0.024 * size)) if kind == "shirt" else \
            ((0.000, 0.004), (0.020 * size, 0.004), (0.038 * size, 0.008))
        for dz, dr in prof:
            point = 1.0 + (0.55 * np.exp(-((np.minimum(th, 2 * np.pi - th) - g) / 0.30) ** 2) if kind == "shirt"
                           and dr > 0.02 else 0.0)
            rr = r0 + dr * point
            y = -c * rr * 1.08 + 0.004 - (z + dz - 1.375) * 0.07
            rows.append(np.column_stack([s * rr, y, np.full(len(th), z + dz - (0.012 * (point - 1.0)))]))
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
        y = -float(b.torso_dims(np.array(z))[1]) - 0.022
    c = np.array([x, y, z])
    parts = []
    for sx in (1.0, -1.0):
        t = np.linspace(0.0, 1.0, 9)
        path = c + np.column_stack([sx * 0.052 * size * t, 0.006 * np.sin(t * np.pi), 0.012 * size * np.sin(t * np.pi)])
        r = 0.020 * size * np.sin(np.clip(t * 1.25 + 0.12, 0, 1) * np.pi) ** 0.7 + 0.003
        parts.append(M.tube("bow", None, path, r, n=10, up=(0, 1, 0), flat=0.34))
        if tails:
            tp = c + np.column_stack([sx * (0.010 + 0.022 * t), -0.004 * t, -tails * t])
            parts.append(M.tube("bowtail", None, tp, 0.011 * size * (0.7 + 0.5 * t), n=8, up=(0, 1, 0), flat=0.22))
    parts.append(_box("knot", c, (0.018 * size, 0.014, 0.020 * size)))
    for i, p in enumerate(parts):
        p.rigid(bone) if bone else p.weights(M.w_spine)
        kit.add(p, (knot or color) if i == len(parts) - 1 else color, "cloth", **(style or {}))


def tie(kit, color, z=1.375, length=0.20, style=None):
    b = kit.body
    t = np.linspace(0.0, 1.0, 9)
    zz = z - length * t
    y = np.array([-float(b.torso_dims(np.array(q))[1]) for q in zz]) - 0.020
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
    f = float(b.torso_dims(np.array(z))[1])
    bk = _box("buckle", (0, -f - ease - 0.004, z), (0.034, 0.010, width * 1.25))
    kit.add(bk.weights(M.w_spine), buckle, "cloth")
    if pouch is not None:
        a = float(b.torso_dims(np.array(z - 0.04))[0])
        bx = _box("deckbox", (a + ease + 0.016, -0.012, z - 0.045), (0.030, 0.062, 0.080))
        kit.add(bx.weights(M.w_spine), pouch, "cloth", hem=[(0.0, pouch)], top=[(0.30, P.shade(pouch, v=0.7))])
        clasp = _box("clasp", (a + ease + 0.033, -0.012, z - 0.030), (0.006, 0.016, 0.016))
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
            h = b.hand(None, side, scale=(0.93 if b.female else 1.04) * 1.06)
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
    clasp = _box("capeclasp", (0, -float(b.torso_dims(np.array(1.36))[1]) - 0.02, 1.365), (0.03, 0.012, 0.02))
    kit.add(clasp.weights(M.w_spine), (lining or (0.86, 0.70, 0.30)), "cloth")


def scarf(kit, color, style=None, tail=0.22):
    b = kit.body
    th = np.linspace(0.0, 2 * np.pi, 22)
    path = np.column_stack([np.sin(th) * (b.neck_r + 0.020), -np.cos(th) * (b.neck_r + 0.024) + 0.002,
                            1.420 + 0.006 * np.cos(th)])
    p = M.tube("scarf", None, path, 0.022, n=10, flat=0.85, cap0=False, cap1=False)
    kit.add(p.weights(M.w_spine), color, "cloth", **(style or {}))
    t = np.linspace(0.0, 1.0, 8)
    tp = np.column_stack([0.030 + 0.02 * t, -b.neck_r - 0.045 - 0.03 * np.sin(t * 2.0), 1.415 - tail * t])
    tl = M.tube("scarftail", None, tp, 0.024 + 0.006 * t, n=8, up=(0, 1, 0), flat=0.25)
    kit.add(tl.weights(M.w_spine), color, "cloth", **(style or {}))
    kit.skin["torso"] = max(kit.skin["torso"], 1.39)


def emblem(kit, color, z=1.27, x=0.062, size=0.016, kind="star", lift=0.024):
    """Small badge on the chest (original geometric marks: star | diamond | disc)."""
    b = kit.body
    n = {"star": 10, "diamond": 4, "disc": 16}[kind]
    a = np.linspace(0, 2 * np.pi, n, endpoint=False) + (math.pi / 2)
    r = np.where(np.arange(n) % 2 == 0, 1.0, 0.45) * size if kind == "star" else np.full(n, size)
    e = 2.0 / 2.35
    ring0 = []
    for ai, ri in zip(a, r):
        px, pz = x + math.cos(ai) * ri, z + math.sin(ai) * ri
        aa, ff, _ = b.torso_dims(np.array(pz))
        py = -float(ff) * max(0.0, 1.0 - abs(px / float(aa)) ** 2.35) ** (1 / 2.35) - lift
        ring0.append((px, py, pz))
    ring0 = np.array(ring0)
    p = M.loft("emblem", None, np.array([ring0, ring0 + (0, -0.003, 0)]), closed=True, cap1=True, outline=0.6)
    kit.add(p.weights(M.w_torso), color, "cloth")


def buttons(kit, color, z0=1.08, z1=1.30, n=3, x=0.022, r=0.008, double=False):
    b = kit.body
    for z in np.linspace(z0, z1, n):
        for sx in ((1.0, -1.0) if double else (1.0,)):
            f = float(b.torso_dims(np.array(z))[1])
            c = np.array([sx * x, -f - 0.017, z])
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


GARMENTS = dict(top=top, skirt=skirt, pants=pants, legwear=legwear, shoes=shoes, collar=collar, bow=bow, tie=tie,
                belt=belt, band=band, gloves=gloves, cape=cape, scarf=scarf, emblem=emblem, buttons=buttons)
