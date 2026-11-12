"""
The protagonist: the playable student's own bespoke model.

Every other cast member is a look from the shared vocabulary (a hair recipe from atelier/styles.py, a garment
preset from looks.py). The player character is authored piece by piece instead, as an original design:

  hair     a hand-placed cut (comb(): every fringe lock, face-framing lock, crown layer and nape lock is
           placed individually): blue-black, side-parted with one long lock between the eyes, a lifted,
           piecey crown, flicked sides, a copper-dyed under-layer that shows at the ends, and a tail at the
           nape tied with a red cord
  face     the boys' VRoid base face with its own painted amber eyes, a heavier ink lash line, hair-coloured
           brows, a sharper jaw, a serious resting expression and gold hoop earrings with a red stone
  outfit   a dorm-coloured academy coat, open, with a single (left) sleeve, a cut-away front and long back
           tails, ink piping, a copper lining edge and a gold card-suit border; over a fitted black high-collar
           top. Hardware: a leather strap from the left shoulder to the right hip with a buckle and a card
           pouch, a belt stack (a second belt slung low with the deck holster), a thigh strap with a pouch,
           fingerless gloves, an arm band, and the statement piece - an armoured duel-disk bracer with a lit
           ring on the bare right forearm

The jacket keeps the runtime "JacketTint" slot (Unreal recolours it by dorm when the player switches dorms);
the hair does not tint (it is the character's own colour). The generic male students keep student_m1.
"""

import numpy as np

from .atelier.paint import shade

KEY = "Hero"

HAIR = (0.115, 0.125, 0.190)          # blue-black
HAIR_TIP = (0.215, 0.255, 0.420)      # the ends fade to ink blue
COPPER = (0.86, 0.44, 0.20)           # the dyed under-layer
COPPER_TIP = (0.97, 0.67, 0.36)
CORD = (0.80, 0.16, 0.18)             # tail tie
IRIS = (0.88, 0.58, 0.16)             # amber
SHEEN = (0.36, 0.44, 0.70)            # the cool highlight ring on the blue-black hair

TINT = (0.93, 0.93, 0.93)             # neutral jacket under the runtime dorm tint
INK = (0.13, 0.14, 0.19)              # piping / shirt
SHIRT = (0.20, 0.21, 0.26)
PANTS = (0.15, 0.16, 0.21)
LEATHER = (0.33, 0.20, 0.13)
GOLD = (0.90, 0.72, 0.30)
SILVER = (0.80, 0.82, 0.86)
BOOTS = (0.18, 0.15, 0.14)


# --------------------------------------------------------------------------- hair
# fringe locks: (azimuth deg, end ring, sweep rad, free m, width m, loft bump); + = the character's left.
# Parted over the left brow; the long middle locks cross between the eyes towards the right temple.
FRINGE = (
    (26.0, 0.375, 0.10, 0.014, 0.060, 0.000),
    (14.0, 0.400, -0.12, 0.020, 0.066, 0.002),
    (3.0, 0.425, -0.18, 0.026, 0.066, 0.000),
    (-1.0, 0.470, -0.04, 0.036, 0.050, 0.003),     # the long lock between the eyes
    (-14.0, 0.395, -0.10, 0.018, 0.060, 0.001),
    (-28.0, 0.395, -0.05, 0.018, 0.060, 0.003),
    (-44.0, 0.470, -0.04, 0.030, 0.056, 0.002),
    (38.0, 0.420, 0.16, 0.020, 0.060, 0.003),
    (50.0, 0.490, 0.10, 0.032, 0.054, 0.001),
)
# thin strands laid over the fringe: break up the edge (az, end, sweep, free)
STRANDS = (
    (10.0, 0.430, -0.10, 0.024),
    (-6.0, 0.440, -0.05, 0.026),
    (-38.0, 0.490, -0.08, 0.030),
    (44.0, 0.460, 0.14, 0.028),
)


def comb(hr):
    """Place the protagonist's cut on a clump-hair `hr` (atelier.hair.Hair on the fitted VRoid head)."""
    rad = np.radians
    for i, (az, end, sw, free, w, bump) in enumerate(FRINGE):
        hr.lock(rad(az), 0.04, end, free=free, sweep=sw, loft=(0.015, 0.022 + bump), width=w, thick=0.25,
                gravity=0.55, forward=0.25, kind="fringe")
    for az, end, sw, free in STRANDS:
        hr.lock(rad(az), 0.06, end, free=free, sweep=sw, loft=(0.017, 0.027), width=0.030, thick=0.30,
                gravity=0.50, forward=0.28, curl=0.4, kind="fringe")
    # face-framing locks in front of the ears: the right one longer (to the jaw), both turning in at the tip
    for az, end, free, curl in ((-60.0, 0.60, 0.085, -0.7), (60.0, 0.58, 0.060, -0.6)):
        hr.lock(rad(az), 0.08, end, free=free, sweep=0.0, loft=(0.015, 0.020), width=0.056, thick=0.26,
                gravity=0.48, forward=0.16, curl=curl, flare=0.02, sector=rad(az))
    # crown: piecey layers that leave the scalp early and fall outwards (volume on top, no spikes)
    hr.spikes(n=13, lift=0.50, free=0.064, rings=(0.20, 0.34, 0.47), start=56.0, flare=0.80, gravity=0.22,
              droop=0.07, up=0.30, width=0.058, curl=0.35, side_tame=0.60, lift_decay=0.30)
    # sides over the ears: flicked out; the inner one copper
    for sx in (1.0, -1.0):
        # (az, end ring, free, curl, flare, loft): the copper one sits under the outer lock and peeks out below
        for j, (az, end, free, curl, flare, loft) in enumerate(((84.0, 0.62, 0.050, 1.0, 0.08, 0.020),
                                                                 (92.0, 0.62, 0.068, 0.6, 0.02, 0.012))):
            lk = hr.lock(rad(az) * sx, 0.06, end, free=free * (1.08 if sx < 0 else 1.0), loft=(0.012, loft),
                         width=0.064, thick=0.26, gravity=0.45, flare=flare, curl=curl, forward=0.04, sector=rad(az) * sx)
            lk.accent = j == 1
    # back: a long copper under-layer flicking out below a shorter outer layer
    hr.back(to=0.67, free=0.070, n=10, start=108.0, curl=1.15, flare=0.13, layers=2, width=1.55, accent=[0])
    # nape tail: a short tied tail (red cord) under the back layers
    hr.tail(at=(180.0, 0.63), n=5, free=0.24, direction=(0.0, 0.40, -0.92), spread=0.014, width=0.040,
            gravity=0.40, accent=[1, 3])
    hr.ahoge(free=0.065, az=-0.22)


def hair_style():
    return dict(style={}, author="hero", accent=COPPER, accent2=COPPER_TIP, tie=CORD, ombre=(0.17, 0.12),
                highlight=SHEEN, sheen=0.55, seed=11, res=2, min_chain=0.045, cap=(0.27, 0.52, 0.72))


# --------------------------------------------------------------------------- outfit
def wear():
    """Garments in wearing order (atelier/outfit.GARMENTS vocabulary; fitted by looks._fit)."""
    from .looks import _fit
    gold, ink = GOLD, INK
    suit = dict(kind="diamond", n=30, v=0.040, size=0.32, h=0.014, color=gold)   # card-suit diamonds along the hem
    return _fit([
        # fitted black high-collar top (panelled, zipped) - shows on the bare right arm and down the open front
        ("top", dict(color=SHIRT, hem=0.97, ease=0.004, sleeves="long", cells=(1, 2),
                     detail=dict(zip=True, panels=True, yoke=True))),
        ("collar", dict(color=SHIRT, kind="stand", size=1.30)),
        ("pants", dict(color=PANTS, ease=0.015, taper=0.45,
                       leg_style=dict(hem=[(0.03, shade(PANTS, v=0.75))]))),
        ("belt", dict(color=LEATHER, z=1.010, width=0.030, buckle=SILVER, tilt=0.0)),
        # a second belt slung low and tilted, carrying the deck holster
        ("belt", dict(color=shade(LEATHER, v=0.72), z=0.965, width=0.024, buckle=GOLD, ease=0.030, tilt=0.07,
                      pouch=shade(LEATHER, v=0.95))),
        ("legstrap", dict(color=shade(LEATHER, v=0.72), side="r", z=0.74, buckle=SILVER, pouch=shade(LEATHER, v=0.9))),
        # the academy coat: open, one sleeve (left), cut away at the front and long behind, gold card-suit hem
        ("top", dict(color=TINT, hem=0.50, hem_front=0.95, ease=0.020, open=18.0, v=0.14, cuff=0.012, flare=0.040,
                     waist=0.012, tail="coattail", slot="tint", sleeve_sides=("l",), cells=(2, 4),
                     style=dict(edge=[(0.014, ink), (0.006, gold), (0.010, COPPER)],
                                hem=[(0.020, ink), (0.006, gold)], motif=suit),
                     sleeve_style=dict(hem=[(0.08, ink), (0.012, gold), (0.012, ink)],
                                       motif=dict(suit, n=9, v=0.13, size=0.26, h=0.035)),
                     detail=dict(lapel=dict(z=1.13, w=0.064, color=shade(TINT, v=0.82)), pockets=("chest_r",),
                                 chest_kind="welt", yoke=True, back_seam=True, panels=True))),
        # leather strap from the left shoulder across the chest to the right hip, buckle and a card pouch on it
        ("strap", dict(color=LEATHER, path=[(1.425, 26.0), (1.33, 12.0), (1.18, -22.0), (1.04, -62.0)],
                       width=0.030, ease=0.030, buckles=(0.38,), buckle=SILVER, pouch=(0.80, shade(LEATHER, v=0.85)))),
        ("strap", dict(color=LEATHER, path=[(1.425, 154.0), (1.30, 172.0), (1.15, 205.0), (1.04, 240.0)],
                       width=0.030, ease=0.030, name="strap_back")),
        ("gloves", dict(color=ink, cuff=0.555, style=dict(hem=[(0.10, shade(ink, v=1.5))]))),
        # the statement piece: an armoured duel-disk bracer on the bare right forearm
        ("bracer", dict(color=(0.30, 0.31, 0.36), side="r", x0=0.445, x1=0.585, trim=gold, disk=INK, glow=COPPER)),
        ("band", dict(color=INK, side="l", x=0.250, width=0.032, ease=0.026,
                      style=dict(hem=[(0.16, gold)], top=[(0.16, gold)]))),
        ("buttons", dict(color=gold, z0=1.14, z1=1.26, n=2, x=0.070)),
        ("emblem", dict(color=gold, z=1.300, x=0.074, kind="star", size=0.017)),
        ("emblem", dict(color=CORD, z=1.300, x=0.074, kind="disc", size=0.006)),
    ])


# --------------------------------------------------------------------------- the cast entry
def look():
    """The protagonist's look (models.build_model vocabulary) on the boys' VRoid base."""
    from . import looks as L
    out = L.look("vroid_c", (HAIR, HAIR_TIP), IRIS, hair_style=hair_style(), tint=("jacket",),
                 colors=dict(jacket=TINT, pants=PANTS, shoes=BOOTS, sole=(0.10, 0.10, 0.11)),
                 expression=dict(BrowAngry=0.30, Fun=0.04), face_shape=dict(chin=0.008, jaw=-0.05),
                 accessories=dict(earrings=(GOLD, CORD)), outline=0.0024)
    out["wear"] = wear()
    out["bespoke"] = KEY
    return out


# --------------------------------------------------------------------------- face paint
def _blobs(alpha):
    """(centre x, centre y, radius x, radius y) of the two iris discs (left / right halves of the sheet)."""
    h, w = alpha.shape
    out = []
    for x0, x1 in ((0, w // 2), (w // 2, w)):
        a = alpha[:, x0:x1].astype(np.float64)
        m = a > 24
        if m.sum() < 16:
            continue
        ys, xs = np.nonzero(m)
        wgt = a[m]
        cx, cy = float((xs * wgt).sum() / wgt.sum()) + x0, float((ys * wgt).sum() / wgt.sum())
        out.append((cx, cy, 0.5 * float(np.ptp(xs) + 1), 0.5 * float(np.ptp(ys) + 1)))
    return out


def _sm(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def paint_iris(tex, color=IRIS):
    """Layered anime iris over the base sheet's discs (alpha kept): dark top under the lid shadow, warm
    amber body, a bright crescent at the bottom, fine radial fibres, a collarette round the pupil, a soft
    inner reflection and an ink limbal ring."""
    rgb = tex[..., :3].astype(np.float32) / 255.0
    alpha = tex[..., 3]
    h, w = alpha.shape
    grow = 1.10                                             # a slightly larger iris than the base's
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    c = np.asarray(color, np.float32)
    deep = np.asarray(shade(color, v=0.30, s=1.25, h=-0.03), np.float32)
    mid = np.asarray(shade(color, v=0.72, s=1.15, h=-0.015), np.float32)
    bright = np.asarray(shade(color, v=1.30, s=0.80, h=0.02), np.float32)
    ink = np.asarray(shade(color, v=0.16, s=1.2, h=-0.05), np.float32)
    new_alpha = np.zeros((h, w), np.float32)
    for cx, cy, rx, ry in _blobs(alpha):
        rx, ry = rx * grow, ry * grow
        dx, dy = (X - cx) / rx, (Y - cy) / ry                # -1..1 over the disc, y down
        r = np.sqrt(dx * dx + dy * dy)
        new_alpha = np.maximum(new_alpha, _sm((1.0 - r) / 0.04 + 0.5))
        inside = r < 1.05
        ang = np.arctan2(dy, dx)
        # vertical body gradient: deep at the top, amber, bright at the bottom
        t = _sm((dy + 0.85) / 1.6)
        col = deep[None, None] * (1 - _sm(t / 0.45))[..., None] + mid[None, None] * _sm(t / 0.45)[..., None]
        col = col * (1 - _sm((t - 0.45) / 0.35))[..., None] + c[None, None] * _sm((t - 0.45) / 0.35)[..., None]
        col = col + (bright - col) * (_sm((dy - 0.25) / 0.55) * _sm((0.98 - r) / 0.25))[..., None] * 0.85
        # radial fibres, lighter in the lower half
        fib = 0.5 + 0.5 * np.sin(ang * 34.0 + 1.3 * np.sin(ang * 7.0))
        fib = fib ** 6 * _sm((r - 0.34) / 0.15) * _sm((0.92 - r) / 0.18) * (0.35 + 0.65 * _sm((dy + 0.1) / 0.6))
        col = col + (bright - col) * fib[..., None] * 0.30
        # collarette: a lighter ring round the pupil, then the pupil (a little tall)
        coll = np.exp(-((r - 0.40) / 0.06) ** 2) * (0.4 + 0.6 * _sm((dy + 0.2) / 0.6))
        col = col + (bright - col) * coll[..., None] * 0.35
        rp = np.sqrt(dx * dx + (dy * 0.86) ** 2)
        col = col + (ink - col) * _sm((0.30 - rp) / 0.04)[..., None]
        # soft inner reflection: a pale crescent low on the iris, opposite the main catch-light
        refl = _sm((0.18 - np.abs(np.sqrt((dx + 0.18) ** 2 + (dy - 0.42) ** 2) - 0.30)) / 0.12) * _sm((dy - 0.20) / 0.25)
        col = col + (np.float32(1.0) - col) * refl[..., None] * 0.22
        # the shadow the upper lid and lashes cast over the top of the iris
        col = col * (1.0 - 0.55 * _sm((-dy - 0.30) / 0.45))[..., None]
        # limbal ring
        col = col + (ink - col) * _sm((r - 0.84) / 0.12)[..., None]
        rgb = np.where(inside[..., None], col, rgb)
    out = tex.copy()
    out[..., :3] = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    out[..., 3] = (np.clip(new_alpha, 0, 1) * 255 + 0.5).astype(np.uint8)
    return out


def paint_highlight(tex, iris_tex):
    """Two catch-lights on the hero's eyes (a large soft one up and out, a small one low and in), painted
    on the highlight layer (it shares the iris sheet's layout)."""
    h, w = tex.shape[:2]
    Y, X = np.mgrid[0:h, 0:w].astype(np.float32)
    a = np.zeros((h, w), np.float32)
    for i, (cx, cy, rx, ry) in enumerate(_blobs(iris_tex[..., 3])):
        out_dir = -1.0 if i == 0 else 1.0                   # towards the outer corner of each eye
        for ox, oy, sx, sy, k in ((0.34 * out_dir, -0.38, 0.22, 0.17, 1.0), (-0.26 * out_dir, 0.36, 0.09, 0.08, 0.85)):
            d = np.sqrt(((X - (cx + ox * rx)) / (sx * rx)) ** 2 + ((Y - (cy + oy * ry)) / (sy * ry)) ** 2)
            a = np.maximum(a, _sm((1.0 - d) / 0.25) * k)
    out = np.zeros_like(tex)
    out[..., :3] = 255
    out[..., 3] = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
    return out


def repaint(source, tex, sheets):
    """models.merge_face_parts hook: the hero's own versions of the base face's sheets (source: the base
    material name; sheets: {source: RGBA array} of every face part, for cross references)."""
    s = source.lower()
    if "eyeiris" in s:
        return paint_iris(tex)
    if "eyehighlight" in s:
        iris = next((v for k, v in sheets.items() if "eyeiris" in k.lower()), None)
        return paint_highlight(tex, iris) if iris is not None else tex
    if "faceeyeline" in s:
        # a heavier, sharper upper lash line in near-black ink (the base's is soft and brown)
        from scipy import ndimage
        out = tex.copy()
        a = tex[..., 3].astype(np.float32)
        thick = ndimage.grey_dilation(a, size=(5, 3))
        out[..., 3] = np.clip(np.maximum(a, thick * 0.92), 0, 255).astype(np.uint8)
        out[..., :3] = (np.asarray(shade(HAIR, v=0.55, s=0.8), np.float32) * 255).astype(np.uint8)
        return out
    if "facebrow" in s:
        out = tex.copy()                                     # brows in the hair's own blue-black
        out[..., :3] = (np.asarray(shade(HAIR, v=0.9), np.float32) * 255).astype(np.uint8)
        return out
    return tex
