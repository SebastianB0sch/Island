"""
The protagonists: the playable student's bespoke models, written in the bespoke template (bespoke.py).

Both are original designs and a pair - the same academy, colours and kit, each with their own cut and
silhouette. The profile's gender picks one in game (DAStudentCharacter); both keep the runtime "JacketTint" slot
so the dorm switch recolours the coat. The generic students keep student_m1 / f1 / f2.

  hero      blue-black hair with a copper under-layer: side-parted, one long lock between the eyes, lifted
            piecey crown, flicked sides, a nape tail tied with a red cord. Amber eyes, an inked lash line, a
            serious resting expression, gold hoop earrings. A one-sleeved (left) academy coat cut away at the
            front with long tails, a gold card-suit border, a copper lining edge and a crest on the back, over a
            fitted black high-collar top; a leather strap over the left shoulder with a buckle and a card pouch,
            a belt stack, a thigh strap, fingerless gloves and an armoured duel-disk bracer on the bare right
            forearm
  heroine   the same colours in a long layered cut parted the other way, half up with a tail at the crown and
            long face-framing locks; amber eyes ringed in copper with an extra sparkle and a confident smile. The
            coat mirrored (right sleeve) and cropped higher with a cinched waist, a pleated skirt, thigh-highs,
            a thigh strap on the bare thigh, the strap over the right shoulder, the bracer on the left forearm

DESIGNS maps a cast id to its design; add a new bespoke character by adding a design here (bespoke.check()
lists what breaks the template's learnings).
"""

from .atelier.paint import shade

HAIR = (0.115, 0.125, 0.190)          # blue-black
HAIR_TIP = (0.215, 0.255, 0.420)      # the ends fade to ink blue
COPPER = (0.86, 0.44, 0.20)           # the dyed under-layer
COPPER_TIP = (0.97, 0.67, 0.36)
CORD = (0.80, 0.16, 0.18)             # tail tie
IRIS = (0.88, 0.58, 0.16)             # amber
SHEEN = (0.36, 0.44, 0.70)            # the cool highlight ring on the blue-black hair

TINT = (0.93, 0.93, 0.93)             # neutral coat under the runtime dorm tint
INK = (0.13, 0.14, 0.19)
SHIRT = (0.20, 0.21, 0.26)
PANTS = (0.15, 0.16, 0.21)
LEATHER = (0.33, 0.20, 0.13)
GOLD = (0.90, 0.72, 0.30)
SILVER = (0.80, 0.82, 0.86)
BOOTS = (0.18, 0.15, 0.14)
GUARD = (0.30, 0.31, 0.36)            # bracer shell

HAIR_COMMON = dict(color=HAIR, tip=HAIR_TIP, accent=COPPER, accent_tip=COPPER_TIP, tie=CORD, sheen_color=SHEEN,
                   sheen=0.55, ombre=(0.17, 0.12), res=2, min_chain=0.045, cap=(0.27, 0.52, 0.72))


def _fringe(az, s1, sweep, free, width, bump=0.0, **kw):
    return dict(az=az, s0=0.04, s1=s1, free=free, sweep=sweep, loft=(0.015, 0.022 + bump), width=width, thick=0.25,
                gravity=0.55, forward=0.25, kind="fringe", **kw)


def _strand(az, s1, sweep, free, **kw):
    return dict(az=az, s0=0.06, s1=s1, free=free, sweep=sweep, loft=(0.017, 0.027), width=0.030, thick=0.30,
                gravity=0.50, forward=0.28, curl=0.4, kind="fringe", strand=True, **kw)


def _mirror_az(locks):
    """The same locks parted the other way (azimuth and sweep negated)."""
    out = []
    for lk in locks:
        lk = dict(lk)
        lk["az"] = -lk["az"]
        if "sweep" in lk:
            lk["sweep"] = -lk["sweep"]
        out.append(lk)
    return out


# parted over the left brow; the long middle lock falls between the eyes
HERO_FRINGE = [
    _fringe(26.0, 0.375, 0.10, 0.014, 0.060),
    _fringe(14.0, 0.400, -0.12, 0.020, 0.066, 0.002),
    _fringe(3.0, 0.425, -0.18, 0.026, 0.066),
    _fringe(-1.0, 0.470, -0.04, 0.036, 0.050, 0.003),          # the long lock between the eyes
    _fringe(-14.0, 0.395, -0.10, 0.018, 0.060, 0.001),
    _fringe(-28.0, 0.395, -0.05, 0.018, 0.060, 0.003),
    _fringe(-44.0, 0.470, -0.04, 0.030, 0.056, 0.002, over_eye=True),   # frames the outer corner
    _fringe(38.0, 0.420, 0.16, 0.020, 0.060, 0.003),
    _fringe(50.0, 0.490, 0.10, 0.032, 0.054, 0.001, over_eye=True),
    _strand(10.0, 0.430, -0.10, 0.024),
    _strand(-6.0, 0.440, -0.05, 0.026),
    _strand(-38.0, 0.490, -0.08, 0.030, over_eye=True),
    _strand(44.0, 0.460, 0.14, 0.028),
]

HERO = dict(
    key="Hero", base="vroid_c", female=False, height=172, tint=("jacket",),
    hair=dict(HAIR_COMMON, seed=11, sections=dict(
        spikes=dict(n=13, lift=0.50, free=0.064, rings=(0.20, 0.34, 0.47), start=56.0, flare=0.80, gravity=0.22,
                    droop=0.07, up=0.30, width=0.058, curl=0.35, side_tame=0.60, lift_decay=0.30),
        back=dict(to=0.67, free=0.070, n=10, start=108.0, curl=1.15, flare=0.13, layers=2, width=1.55, accent=[0]),
        tails=[dict(at=(180.0, 0.63), n=5, free=0.24, direction=(0.0, 0.40, -0.92), spread=0.014, width=0.040,
                    gravity=0.40, accent=[1, 3])],
        ahoge=dict(free=0.065, az=-0.22)),
        locks=HERO_FRINGE + [
            # face-framing locks in front of the ears, the right one longer, both turning in at the tip
            dict(az=-60.0, s0=0.08, s1=0.60, free=0.085, loft=(0.015, 0.020), width=0.056, thick=0.26,
                 gravity=0.48, forward=0.16, curl=-0.7, flare=0.02),
            dict(az=60.0, s0=0.08, s1=0.58, free=0.060, loft=(0.015, 0.020), width=0.056, thick=0.26,
                 gravity=0.48, forward=0.16, curl=-0.6, flare=0.02),
            # sides over the ears: flicked out; the inner one copper and tucked under
            dict(az=84.0, s0=0.06, s1=0.62, free=0.050, loft=(0.012, 0.020), width=0.064, thick=0.26, gravity=0.45,
                 flare=0.08, curl=1.0, forward=0.04, mirror=True, asym=1.08),
            dict(az=92.0, s0=0.06, s1=0.62, free=0.068, loft=(0.012, 0.012), width=0.064, thick=0.26, gravity=0.45,
                 flare=0.02, curl=0.6, forward=0.04, mirror=True, asym=1.08, accent=True),
        ]),
    face=dict(iris=IRIS, lash=1.0, expression=dict(BrowAngry=0.30, Fun=0.04), face_shape=dict(chin=0.008, jaw=-0.05),
              earrings=(GOLD, CORD)),
    colors=dict(jacket=TINT, pants=PANTS, shoes=BOOTS, sole=(0.10, 0.10, 0.11)),
)

SUIT = dict(kind="diamond", n=30, v=0.040, size=0.32, h=0.014, color=GOLD)     # card-suit diamonds along a hem
CREST = dict(u=0.5, v=0.74, size=0.075, color=GOLD, alpha=0.9)                # on the back of the coat


def _coat(sleeve, hem, hem_front, waist, flare, open_=18.0, ease=0.020):
    return ("top", dict(color=TINT, hem=hem, hem_front=hem_front, ease=ease, open=open_, v=0.14, cuff=0.012,
                        flare=flare, waist=waist, tail="coattail", slot="tint", sleeve_sides=(sleeve,), cells=(2, 4),
                        style=dict(edge=[(0.014, INK), (0.006, GOLD), (0.010, COPPER)],
                                   hem=[(0.020, INK), (0.006, GOLD)], motif=SUIT, crest=CREST),
                        sleeve_style=dict(hem=[(0.08, INK), (0.012, GOLD), (0.012, INK)],
                                          motif=dict(SUIT, n=9, v=0.13, size=0.26, h=0.035)),
                        detail=dict(lapel=dict(z=1.13, w=0.064, color=shade(TINT, v=0.82)), pockets=("chest_r",),
                                    chest_kind="welt", yoke=True, back_seam=True, panels=True)))


def _strap(side, pouch_col):
    """Leather strap from one shoulder across the chest to the other hip and over the shoulder down the back."""
    s = 1.0 if side == "l" else -1.0
    return ("strap", dict(color=LEATHER, path=[(1.425, 26.0 * s), (1.33, 12.0 * s), (1.18, -22.0 * s), (1.04, -62.0 * s)],
                          over=[(1.425, 154.0 * s), (1.30, 172.0 * s), (1.15, 205.0 * s), (1.04, 240.0 * s)],
                          width=0.030, ease=0.030, buckles=(0.38,), buckle=SILVER, pouch=(0.80, pouch_col)))


HERO["wear"] = [
    ("top", dict(color=SHIRT, hem=0.97, ease=0.004, sleeves="long", cells=(1, 2), detail=dict(zip=True, panels=True, yoke=True))),
    ("collar", dict(color=SHIRT, kind="stand", size=1.30)),
    ("pants", dict(color=PANTS, ease=0.015, taper=0.45, leg_style=dict(hem=[(0.03, shade(PANTS, v=0.75))]))),
    ("belt", dict(color=LEATHER, z=1.010, width=0.030, buckle=SILVER, tilt=0.0)),
    ("belt", dict(color=shade(LEATHER, v=0.72), z=0.965, width=0.024, buckle=GOLD, ease=0.030, tilt=0.07,
                  pouch=shade(LEATHER, v=0.95))),
    ("legstrap", dict(color=shade(LEATHER, v=0.72), side="r", z=0.74, buckle=SILVER, pouch=shade(LEATHER, v=0.9))),
    _coat("l", hem=0.50, hem_front=0.95, waist=0.012, flare=0.040),
    _strap("l", shade(LEATHER, v=0.85)),
    ("gloves", dict(color=INK, cuff=0.555, style=dict(hem=[(0.10, shade(INK, v=1.5))]))),
    ("bracer", dict(color=GUARD, side="r", x0=0.445, x1=0.585, trim=GOLD, disk=INK, glow=COPPER)),
    ("band", dict(color=INK, side="l", x=0.250, width=0.032, ease=0.026, style=dict(hem=[(0.16, GOLD)], top=[(0.16, GOLD)]))),
    ("buttons", dict(color=GOLD, z0=1.14, z1=1.26, n=2, x=0.070)),
    ("emblem", dict(color=GOLD, z=1.300, x=0.074, kind="star", size=0.017)),
    ("emblem", dict(color=CORD, z=1.300, x=0.074, kind="disc", size=0.006)),
]


# --------------------------------------------------------------------------- the heroine
HEROINE_FRINGE = [dict(lk, s1=lk["s1"] - 0.015, free=lk["free"] * 0.8) for lk in _mirror_az(HERO_FRINGE[:9])] + [
    _strand(-12.0, 0.440, 0.10, 0.026),
    _strand(4.0, 0.450, 0.05, 0.028),
    _strand(40.0, 0.490, 0.08, 0.030, over_eye=True),
]

HEROINE = dict(
    key="Heroine", base="vroid_a", female=True, height=163, tint=("jacket",),
    hair=dict(HAIR_COMMON, seed=23, sections=dict(
        spikes=dict(n=11, lift=0.28, free=0.050, rings=(0.22, 0.38), start=58.0, flare=0.70, gravity=0.30,
                    droop=0.10, width=0.060, curl=0.4, side_tame=0.70),
        back=dict(to=0.72, free=0.34, n=12, start=100.0, taper=0.14, layers=2, flare=0.05, curl=0.6, wave=0.20,
                  width=1.60),
        # half up: a tail tied high at the back of the crown
        tails=[dict(at=(180.0, 0.30), n=6, free=0.26, direction=(0.0, 0.75, 0.30), wave=0.25, gravity=0.34,
                    spread=0.016, width=0.044, accent=[1, 4])],
        ahoge=dict(free=0.060, az=0.22)),
        locks=HEROINE_FRINGE + [
            # long face-framing locks to the collarbone, turning in
            dict(az=-58.0, s0=0.08, s1=0.60, free=0.11, loft=(0.015, 0.020), width=0.046, thick=0.26,
                 gravity=0.45, forward=0.22, curl=-0.8, flare=0.05, wave=0.25),
            dict(az=-50.0, s0=0.10, s1=0.58, free=0.07, loft=(0.016, 0.022), width=0.046, thick=0.26,
                 gravity=0.48, forward=0.22, curl=-0.9, flare=0.03, wave=0.2),
            dict(az=58.0, s0=0.08, s1=0.60, free=0.09, loft=(0.015, 0.020), width=0.046, thick=0.26,
                 gravity=0.45, forward=0.22, curl=-0.8, flare=0.05, wave=0.25),
            # long sides, the inner one copper
            dict(az=84.0, s0=0.06, s1=0.66, free=0.16, loft=(0.012, 0.020), width=0.066, thick=0.26, gravity=0.42,
                 flare=0.05, curl=0.6, forward=0.06, mirror=True, asym=1.05, wave=0.2),
            dict(az=94.0, s0=0.06, s1=0.66, free=0.20, loft=(0.012, 0.013), width=0.066, thick=0.26, gravity=0.42,
                 flare=0.03, curl=0.4, forward=0.04, mirror=True, asym=1.05, accent=True),
        ]),
    face=dict(iris=(0.92, 0.62, 0.20), iris_ring=(0.82, 0.32, 0.16), sparkle=True, lash=1.2,
              expression=dict(Fun=0.06, BrowAngry=0.06), face_shape=dict(chin=0.004), earrings=(GOLD, CORD)),
    colors=dict(jacket=TINT, skirt=INK, pants=INK, shoes=BOOTS, sole=(0.10, 0.10, 0.11)),
)

HEROINE["wear"] = [
    ("top", dict(color=SHIRT, hem=0.99, ease=0.004, sleeves="long", cells=(1, 2), detail=dict(zip=True, panels=True))),
    ("collar", dict(color=SHIRT, kind="stand", size=1.20)),
    ("skirt", dict(color=INK, length=0.29, pleats=16, flare=0.12, style=dict(hem=[(0.035, shade(INK, v=0.7)), (0.012, GOLD)]))),
    ("legwear", dict(color=(0.08, 0.08, 0.10), top=0.60, style=dict(top=[(0.030, GOLD), (0.012, INK)]))),
    ("belt", dict(color=LEATHER, z=1.035, width=0.026, buckle=SILVER)),
    ("belt", dict(color=shade(LEATHER, v=0.72), z=0.985, width=0.022, buckle=GOLD, ease=0.034, tilt=-0.07,
                  pouch=shade(LEATHER, v=0.95))),
    ("legstrap", dict(color=shade(LEATHER, v=0.72), side="l", z=0.665, buckle=SILVER, pouch=shade(LEATHER, v=0.9))),
    _coat("r", hem=0.58, hem_front=1.00, waist=0.0, flare=0.050, open_=16.0, ease=0.036),
    _strap("r", shade(LEATHER, v=0.85)),
    ("gloves", dict(color=INK, cuff=0.560, style=dict(hem=[(0.10, shade(INK, v=1.5))]))),
    ("bracer", dict(color=GUARD, side="l", x0=0.445, x1=0.580, trim=GOLD, disk=INK, glow=COPPER)),
    ("band", dict(color=INK, side="r", x=0.250, width=0.030, ease=0.026, style=dict(hem=[(0.16, GOLD)], top=[(0.16, GOLD)]))),
    ("emblem", dict(color=GOLD, z=1.290, x=0.070, kind="star", size=0.016)),
    ("emblem", dict(color=CORD, z=1.290, x=0.070, kind="disc", size=0.006)),
]

DESIGNS = {"hero": HERO, "heroine": HEROINE}
