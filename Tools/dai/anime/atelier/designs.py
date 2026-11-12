"""
The original cast of the island academy.

Every character here is the project's own design: face, hairstyle and outfit are described with the
atelier's parameters (head.py / hair.py / outfit.py) - no third-party model, texture or likeness.

A design is a dict:

  name      the design's own name (credits / tooling; the game shows the cast slot's name)
  female    body table
  skin, build, bust, head {jaw, chin, cheek, face_w, cranium}
  eyes      eye-shape overrides (paint.EYE), iris / iris2 colours, brows, mouth, expression, blush, lips, mole
  hair      {color, color2 (tips), style (hair.py sections), cap, seed}
  outfit    [(garment kind, params)] in wearing order (outfit.GARMENTS + hairband / glasses / hairbow)
  tint      generic students: ["jacket", "hair"] parts Unreal recolours per dorm / NPC

The dorm accents (red / yellow / blue) are the academy's house colours.
"""

from .paint import shade

WHITE = (0.96, 0.96, 0.95)
CREAM = (0.96, 0.92, 0.84)
BLACK = (0.09, 0.09, 0.11)
NAVY = (0.12, 0.15, 0.29)
CHARCOAL = (0.19, 0.20, 0.25)
GREY = (0.55, 0.57, 0.62)
BROWN = (0.36, 0.22, 0.15)
GOLD = (0.90, 0.72, 0.30)
SILVER = (0.80, 0.82, 0.86)
RED = (0.78, 0.20, 0.21)
YELLOW = (0.95, 0.79, 0.32)
BLUE = (0.14, 0.28, 0.68)
TEAL = (0.10, 0.52, 0.55)
PLUM = (0.42, 0.20, 0.44)
TINT = (0.93, 0.93, 0.93)             # neutral base under a runtime tint

DORM = {"slifer": RED, "ra": YELLOW, "obelisk": BLUE, "white": WHITE, "teacher": PLUM}
MARK = {"slifer": "diamond", "ra": "disc", "obelisk": "star", "white": "diamond", "teacher": "disc"}

SKIN_FAIR = (1.0, 0.90, 0.82)
SKIN_WARM = (0.99, 0.85, 0.74)
SKIN_TAN = (0.90, 0.72, 0.58)
SKIN_DEEP = (0.66, 0.47, 0.36)

# --------------------------------------------------------------------------- eyes
F_ROUND = dict()
F_GENTLE = dict(tilt=-0.12, h=0.0290, upper=0.60, wing=0.22, wing_up=0.25)
F_SHARP = dict(tilt=0.16, h=0.0262, skew=0.22, wing=0.36, wing_up=0.75, upper=0.60)
F_SLEEPY = dict(h=0.0235, upper=0.50, tilt=-0.04, lash=0.0040)
F_BRIGHT = dict(h=0.0320, hw=0.0212, iris_w=0.64)
M_SOFT = dict(h=0.0232, hw=0.0196, lash=0.0027, wing=0.12, wing_up=0.3, iris_w=0.56, upper=0.58)
M_SHARP = dict(h=0.0200, hw=0.0202, lash=0.0028, wing=0.16, wing_up=0.6, iris_w=0.54, tilt=0.13, upper=0.56,
               skew=0.2)
M_ROUND = dict(h=0.0265, hw=0.0200, lash=0.0028, wing=0.10, wing_up=0.3, iris_w=0.60)
M_NARROW = dict(h=0.0172, hw=0.0205, lash=0.0026, wing=0.10, wing_up=0.4, iris_w=0.50, upper=0.52, tilt=0.05)
M_HEAD = dict(jaw=1.05, chin=0.003, face_w=0.97)
BROW_M = dict(thick=0.0036, len=0.036, arch=0.0018)
for _p, _k in ((F_GENTLE, 1.15), (F_SHARP, 1.15), (F_SLEEPY, 1.15), (F_BRIGHT, 1.13), (M_SOFT, 1.15), (M_SHARP, 1.17),
               (M_ROUND, 1.15), (M_NARROW, 1.18)):      # sizes relative to the reference eye (paint.EYE)
    for _n in ("h", "hw"):
        if _n in _p:
            _p[_n] = round(_p[_n] * _k, 5)

# --------------------------------------------------------------------------- hair
from .styles import HAIR  # noqa: E402  (the style recipes are shared with the VRoid-based looks)


def hair(style, color, color2=None, **kw):
    out = dict(color=color, style=dict(HAIR[style]), **kw)
    if color2:
        out["color2"] = color2
    return out


# --------------------------------------------------------------------------- outfits
def _pin(accent, x=0.066, z=1.275, kind="diamond"):
    return [("emblem", dict(color=accent, z=z, x=x, kind=kind, size=0.017)),
            ("emblem", dict(color=GOLD, z=z, x=x, kind="disc", size=0.006))]


def blazer_m(accent, jacket=NAVY, pants=CHARCOAL, shoes=BROWN, open_=13.0, slot="cloth", tie=True, mark="diamond",
             shirt=WHITE, hem=0.89, trim=None, band=True, pouch=True):
    """Shirt and tie under an open piped blazer, trousers, deck box on the belt."""
    trim = trim or accent
    out = [("top", dict(color=shirt, hem=0.97, ease=0.006, sleeve_to=0.655, cells=(1, 1), detail=dict(placket=dict(w=0.028, buttons=5)))),
           ("collar", dict(color=shirt, kind="shirt")),
           ("pants", dict(color=pants, ease=0.014))]
    if tie:
        out.append(("tie", dict(color=accent, style=dict(stripes=dict(n=7, width=0.28, color=shade(accent, v=0.62),
                                                                     axis="v")))))
    out += [("belt", dict(color=BLACK, pouch=shade(accent, v=0.85) if pouch else None)),
            ("top", dict(color=jacket, hem=hem, ease=0.014, open=open_, v=0.11, cuff=0.004, slot=slot, flare=0.006,
                         style=dict(edge=[(0.014, trim)], hem=[(0.035, trim)]),
                         sleeve_style=dict(hem=[(0.05, trim), (0.018, WHITE)]),
                         detail=dict(lapel=dict(color=shade(jacket, v=0.86, s=1.08)), pockets=("flap", "chest_r"),
                                     chest_kind="welt", buttons=dict(n=2, x=0.050, color=GOLD), back_seam=True))),
            ("shoes", dict(color=shoes, kind="loafer"))]
    if band:
        out.append(("band", dict(color=accent, side="l", x=0.275, ease=0.022, style=dict(hem=[(0.2, WHITE)],
                                                                                         top=[(0.2, WHITE)]))))
    return out + _pin(accent, kind=mark)


def bomber_m(accent, body=None, sleeves=WHITE, pants=CHARCOAL, shoes=WHITE, slot="cloth", mark="diamond"):
    """Short zipped jacket with contrast sleeves and a stand collar, sneakers."""
    body = body or accent
    dark = shade(accent, v=0.62)
    return [("top", dict(color=BLACK, hem=0.97, ease=0.005, sleeves="short", cells=(1, 1))),
            ("pants", dict(color=pants, ease=0.016, leg_style=dict(hem=[(0.04, dark)]))),
            ("belt", dict(color=BLACK, pouch=dark)),
            ("top", dict(color=body, hem=0.955, ease=0.015, slot=slot, cuff=-0.004,
                         style=dict(hem=[(0.09, dark)], edge=[(0.008, WHITE)]), sleeve_color=sleeves,
                         sleeve_style=dict(hem=[(0.07, dark)], ribs=dict(n=18, v1=0.07, depth=0.30)),
                         detail=dict(zip=True, pockets=("welt",), ribs=0.045, yoke=True))),
            ("collar", dict(color=dark, kind="stand", slot=slot)),
            ("shoes", dict(color=shoes, kind="sneaker", sole=WHITE, toe=accent))] + _pin(WHITE, kind=mark)


def coat_m(accent, coat=BLACK, pants=BLACK, shirt=None, shoes=BLACK, mark="diamond", hem=0.52):
    """Long open coat with a lined edge over a high-collar shirt, boots."""
    shirt = shirt or shade(accent, v=0.55, s=0.8)
    return [("top", dict(color=shirt, hem=0.97, ease=0.006, sleeve_to=0.64, cells=(1, 1), detail=dict(zip=True))),
            ("collar", dict(color=shirt, kind="stand")),
            ("pants", dict(color=pants, ease=0.013)),
            ("belt", dict(color=shade(accent, v=0.7), pouch=accent, buckle=SILVER)),
            ("top", dict(color=coat, hem=hem, ease=0.016, open=17.0, v=0.13, cuff=0.006, flare=0.030, tail="coattail",
                         style=dict(edge=[(0.010, accent), (0.006, SILVER)], hem=[(0.012, accent)]),
                         sleeve_style=dict(hem=[(0.07, accent), (0.015, SILVER)]), cells=(2, 4),
                         detail=dict(lapel=dict(z=1.12, w=0.058, color=shade(accent, v=0.72)), pockets=("flap",),
                                     pocket_z=0.90, pocket_button=SILVER, yoke=True, back_seam=True))),
            ("shoes", dict(color=shoes, kind="boot", shaft=0.30, sole=BLACK)),
            ("buttons", dict(color=SILVER, z0=1.10, z1=1.24, n=3, x=0.060))] + _pin(accent, kind=mark)


def vest_m(accent, vest=CHARCOAL, pants=CHARCOAL, shoes=BROWN, mark="diamond", slot="cloth"):
    """Rolled shirt sleeves, tie and a fitted vest."""
    return [("top", dict(color=WHITE, hem=0.97, ease=0.006, sleeves="elbow", cuff=0.004, cells=(1, 1),
                         sleeve_style=dict(hem=[(0.10, shade(WHITE, v=0.88))]), detail=dict(placket=dict(w=0.028, buttons=5)))),
            ("collar", dict(color=WHITE, kind="shirt")),
            ("pants", dict(color=pants, ease=0.014)),
            ("tie", dict(color=accent)),
            ("belt", dict(color=BROWN, pouch=accent)),
            ("top", dict(color=vest, hem=0.975, ease=0.013, sleeves="none", v=0.16, slot=slot,
                         style=dict(edge=[(0.012, accent)], hem=[(0.03, accent)]),
                         detail=dict(pockets=("welt",), pocket_z=1.075, pocket_x=0.070, panels=True, back_seam=True))),
            ("buttons", dict(color=GOLD, z0=1.03, z1=1.15, n=3, x=0.0, r=0.007)),
            ("shoes", dict(color=shoes, kind="loafer")),
            ("band", dict(color=accent, side="r", x=0.62, width=0.022, ease=0.006))] + _pin(accent, kind=mark)


def sailor_f(accent, skirt=None, top=WHITE, legs=BLACK, shoes=BROWN, bow=None, slot="cloth", mark="star",
             thigh=0.57, length=0.31):
    """Sailor blouse with a striped collar and a pleated skirt."""
    skirt = skirt or accent
    return [("top", dict(color=top, hem=0.995, ease=0.008, sleeves="short", puff=0.012, slot=slot,
                         style=dict(hem=[(0.05, accent)]), sleeve_style=dict(hem=[(0.16, accent), (0.05, WHITE)]))),
            ("collar", dict(color=accent, kind="sailor", style=dict(hem=[(0.07, WHITE), (0.05, accent), (0.05, WHITE)]))),
            ("bow", dict(color=bow or RED, knot=GOLD, size=0.8, tails=0.085)),
            ("skirt", dict(color=skirt, length=length, style=dict(hem=[(0.05, WHITE), (0.045, skirt), (0.035, WHITE)]))),
            ("legwear", dict(color=legs, top=thigh, style=dict(top=[(0.035, accent)]))),
            ("band", dict(color=accent, side="l", x=0.635, width=0.016, ease=0.004)),
            ("shoes", dict(color=shoes, kind="loafer"))]


def blazer_f(accent, jacket=NAVY, skirt=None, legs=WHITE, shoes=BROWN, slot="cloth", mark="star", bow=True,
             thigh=0.34, length=0.32, check=True):
    """Shirt and ribbon under a cropped piped blazer, checked pleated skirt, socks."""
    skirt = skirt or shade(accent, v=0.80)
    st = dict(hem=[(0.035, shade(skirt, v=0.6))])
    if check:
        st["stripes"] = dict(n=14, width=0.12, color=shade(skirt, v=1.35, s=0.7), alpha=0.55)
    out = [("top", dict(color=WHITE, hem=0.985, ease=0.006, sleeve_to=0.655, cells=(1, 1), detail=dict(placket=dict(w=0.028, buttons=5)))),
           ("collar", dict(color=WHITE, kind="shirt")),
           ("skirt", dict(color=skirt, length=length, style=st)),
           ("top", dict(color=jacket, hem=0.965, ease=0.012, open=11.0, v=0.12, slot=slot, waist=0.004, flare=0.008,
                        style=dict(edge=[(0.016, accent)], hem=[(0.05, accent)]),
                        sleeve_style=dict(hem=[(0.05, accent), (0.018, WHITE)]),
                        detail=dict(lapel=dict(z=1.14, w=0.040, color=shade(jacket, v=0.94, s=1.6)), pockets=("welt",),
                                    pocket_z=1.045, pocket_x=0.066, buttons=dict(n=2, z0=1.03, z1=1.09, x=0.040, color=GOLD),
                                    panels=True))),
           ("band", dict(color=accent, side="r", x=0.275, ease=0.018, width=0.028, style=dict(hem=[(0.2, WHITE)],
                                                                                            top=[(0.2, WHITE)]))),
           ("legwear", dict(color=legs, top=thigh, style=dict(top=[(0.06, accent)]))),
           ("shoes", dict(color=shoes, kind="loafer"))]
    if bow:
        out.insert(2, ("bow", dict(color=accent, size=0.85, z=1.345, knot=GOLD)))
    return out + _pin(accent, x=0.070, z=1.255, kind=mark)


def cardigan_f(accent, knit=CREAM, skirt=None, legs=BLACK, shoes=BROWN, mark="star", length=0.33):
    """Loose knit over a shirt, long ribbon, tights."""
    skirt = skirt or shade(accent, v=0.75)
    return [("top", dict(color=WHITE, hem=0.985, ease=0.005, sleeves="short", cells=(1, 1), detail=dict(placket=dict(w=0.028, buttons=5)))),
            ("collar", dict(color=WHITE, kind="shirt")),
            ("tie", dict(color=accent, length=0.13)),
            ("skirt", dict(color=skirt, length=length, pleats=16, style=dict(hem=[(0.04, accent)]))),
            ("top", dict(color=knit, hem=0.90, ease=0.019, open=9.0, v=0.17, bell=0.012, flare=0.012,
                         style=dict(hem=[(0.07, shade(knit, v=0.88))], edge=[(0.02, shade(knit, v=0.88))],
                                    stripes=dict(n=40, width=0.3, color=shade(knit, v=0.95), alpha=0.5)),
                         sleeve_style=dict(hem=[(0.10, shade(knit, v=0.88))], ribs=dict(n=18, v1=0.10, depth=0.28)),
                         detail=dict(pockets=("hip",), pocket_z=0.975, pocket_x=0.085, ribs=0.045))),
            ("buttons", dict(color=shade(accent, v=0.9), z0=0.96, z1=1.14, n=4, x=0.030, r=0.007)),
            ("legwear", dict(color=legs, top=0.86)),
            ("shoes", dict(color=shoes, kind="loafer"))] + _pin(accent, x=0.074, z=1.20, kind=mark)


def ranger_f(accent, jacket=WHITE, shorts=CHARCOAL, boots=None, mark="star", cape=None):
    """Fitted peplum jacket, shorts, thigh boots; optional back cape."""
    boots = boots or shade(accent, v=0.75)
    out = [("top", dict(color=BLACK, hem=0.985, ease=0.005, sleeves="none", cells=(1, 1))),
           ("collar", dict(color=BLACK, kind="stand", size=0.8)),
           ("pants", dict(color=shorts, hem=0.72, ease=0.010, leg_style=dict(hem=[(0.10, accent)]))),
           ("top", dict(color=jacket, hem=0.925, ease=0.014, open=8.0, v=0.14, waist=0.006, flare=0.030,
                        sleeves="elbow", bell=0.010,
                        style=dict(edge=[(0.014, accent), (0.006, GOLD)], hem=[(0.05, accent), (0.015, GOLD)]),
                        sleeve_style=dict(hem=[(0.12, accent), (0.03, GOLD)]))),
           ("belt", dict(color=shade(accent, v=0.6), pouch=accent, ease=0.021, z=1.03)),
           ("gloves", dict(color=BLACK, cuff=0.56, style=dict(top=[(0.10, accent)]))),
           ("shoes", dict(color=boots, kind="boot", shaft=0.62, heel=0.012, cuff=0.006, style=dict(top=[(0.05, GOLD)])))]
    if cape:
        out.append(("cape", dict(color=cape, length=0.50, style=dict(hem=[(0.03, GOLD), (0.02, cape), (0.012, GOLD)],
                                                                    gradient=(shade(cape, v=0.6), 0.0, 0.5)))))
    return out + _pin(accent, x=0.068, z=1.265, kind=mark)


def dress_f(accent, dress=None, legs=WHITE, shoes=BLACK, mark="star", apron=None):
    """Long-sleeved dress with a flared hem (staff / formal)."""
    dress = dress or shade(accent, v=0.7)
    out = [("top", dict(color=dress, hem=0.50, ease=0.010, v=0.07, waist=0.006, flare=0.11, tail="skirt", puff=0.008,
                        cuff=0.004, cells=(2, 4), style=dict(hem=[(0.02, WHITE), (0.015, dress), (0.01, WHITE)]),
                        sleeve_style=dict(hem=[(0.08, WHITE)]),
                        detail=dict(panels=True, pockets=("hip",), pocket_z=0.90,
                                    placket=dict(w=0.030, buttons=4, z0=1.08, z_top=1.28, z1=1.32, button=WHITE)))),
           ("collar", dict(color=WHITE, kind="shirt")),
           ("legwear", dict(color=legs, top=0.60)),
           ("shoes", dict(color=shoes, kind="loafer", heel=0.010))]
    if apron:
        out += [("top", dict(color=apron, hem=0.62, ease=0.016, open=118.0, sleeves="none", neck=1.25, flare=0.10,
                             tail="skirt", style=dict(hem=[(0.03, shade(apron, v=0.85))]))),
                ("belt", dict(color=apron, z=1.04, width=0.03, buckle=apron, ease=0.019))]
    out.append(("bow", dict(color=accent, size=0.8, z=1.36, knot=GOLD)))
    return out


def suit_m(accent, suit=CHARCOAL, shirt=WHITE, shoes=BLACK, long=False, coat=None):
    """Staff suit: closed jacket, tie; `coat`: colour of an open long coat (lab coat) worn over it."""
    out = [("top", dict(color=shirt, hem=0.97, ease=0.006, sleeve_to=0.655, cells=(1, 1), detail=dict(placket=dict(w=0.028, buttons=5)))),
           ("collar", dict(color=shirt, kind="shirt")),
           ("tie", dict(color=accent)),
           ("pants", dict(color=shade(suit, v=0.80), ease=0.015)),
           ("top", dict(color=suit, hem=0.88, ease=0.014, open=6.0, v=0.17, flare=0.006,
                        style=dict(edge=[(0.012, shade(suit, v=1.35))]),
                        sleeve_style=dict(hem=[(0.03, shade(suit, v=1.35))]),
                        detail=dict(lapel=dict(z=1.13, w=0.055, color=shade(suit, v=1.22)), pockets=("flap", "chest_r"),
                                    chest_kind="welt", back_seam=True))),
           ("buttons", dict(color=shade(suit, v=0.6), z0=1.00, z1=1.10, n=2, x=0.0)),
           ("shoes", dict(color=shoes, kind="loafer"))]
    if coat:
        out.append(("top", dict(color=coat, hem=0.50, ease=0.020, open=24.0, v=0.14, flare=0.02, tail="coattail",
                                cells=(2, 4), style=dict(edge=[(0.006, shade(coat, v=0.82))]),
                                sleeve_style=dict(hem=[(0.03, shade(coat, v=0.85))]),
                                detail=dict(lapel=dict(z=1.14, w=0.050, color=shade(coat, v=0.90)),
                                            pockets=("hip", "chest"), pocket_z=0.88, yoke=True, back_seam=True))))
    return out


# --------------------------------------------------------------------------- the cast
def _m(name, eyes=M_SOFT, **kw):
    d = dict(name=name, female=False, eyes=eyes, head=dict(M_HEAD, **kw.pop("head", {})),
             brows=dict(BROW_M, **kw.pop("brows", {})), blush=kw.pop("blush", 0.10), skin=SKIN_WARM)
    d.update(kw)
    return d


def _f(name, eyes=F_ROUND, **kw):
    d = dict(name=name, female=True, eyes=eyes, skin=SKIN_FAIR)
    d.update(kw)
    return d


DESIGNS = {
    # ------------------------------------------------------------------ red dorm
    "Kaien": _m("Kaien Asahi", M_ROUND, hair=hair("spiky", (0.74, 0.30, 0.16), (0.96, 0.62, 0.22), ombre=(0.10, 0.12)),
                iris=(0.80, 0.50, 0.16), expression=dict(Fun=0.55), mouth=dict(w=0.0115),
                outfit=bomber_m(RED, mark="diamond") + [("band", dict(color=WHITE, side="r", x=0.63, width=0.03,
                                                                      ease=0.006))]),
    "Pim": _m("Pim Sorrel", M_ROUND, build=0.92, hair=hair("mop", (0.45, 0.72, 0.78), (0.30, 0.50, 0.66)),
              iris=(0.35, 0.60, 0.62), brows=dict(angle=-7.0), expression=dict(BrowSorrow=0.35), blush=0.3,
              outfit=blazer_m(RED, jacket=shade(RED, v=0.9), pants=CREAM, shoes=shade(BLUE, v=0.8), open_=4.0,
                              trim=WHITE) + [("glasses", dict(color=(0.20, 0.22, 0.30), round_=1.0))]),
    "Bram": _m("Bram Hollis", M_NARROW, build=1.22, hair=hair("messy", (0.24, 0.17, 0.14)), iris=(0.40, 0.28, 0.16),
               head=dict(jaw=1.16, cheek=1.08, face_w=1.05), expression=dict(Fun=0.3), blush=0.30,
               outfit=vest_m(RED, vest=CREAM, pants=shade(BROWN, v=0.8))),
    # ------------------------------------------------------------------ yellow dorm
    "Leoric": _m("Leoric Vance", M_SHARP, hair=hair("neat", (0.16, 0.18, 0.24)), iris=(0.30, 0.42, 0.50),
                 brows=dict(angle=5.0), outfit=vest_m(YELLOW, vest=shade(YELLOW, v=0.95), mark="disc")),
    # ------------------------------------------------------------------ blue dorm
    "Rook": _m("Rook Mercer", M_SHARP, hair=hair("tall", (0.10, 0.10, 0.13)), iris=(0.42, 0.42, 0.50),
               brows=dict(angle=9.0), expression=dict(BrowAngry=0.5), mouth=dict(smile=-0.0008),
               outfit=coat_m(shade(PLUM, v=0.9, s=0.7), coat=BLACK, pants=shade(NAVY, v=0.8), mark="star")),
    "Aurel": _m("Aurel Kestrel", M_NARROW, hair=hair("long_m", (0.20, 0.33, 0.42), (0.12, 0.20, 0.30)),
                iris=(0.32, 0.50, 0.58), head=dict(jaw=1.02, chin=0.006),
                outfit=coat_m(BLUE, coat=WHITE, pants=NAVY, shirt=NAVY, shoes=NAVY, mark="star", hem=0.56)),
    "Selene": _f("Selene Marlowe", F_SHARP, hair=hair("long", (0.92, 0.80, 0.50), (0.98, 0.90, 0.68)),
                 iris=(0.62, 0.48, 0.26), expression=dict(Fun=0.2),
                 outfit=ranger_f(BLUE, cape=NAVY) + [("hairband", dict(color=NAVY))]),
    "Wren": _f("Wren Calloway", F_BRIGHT, hair=hair("flip", (0.60, 0.26, 0.16)), iris=(0.45, 0.30, 0.20),
               expression=dict(Fun=0.5), outfit=blazer_f(BLUE, jacket=WHITE, skirt=BLUE, thigh=0.34)),
    "Odile": _f("Odile Tanaka", F_GENTLE, hair=hair("hime", (0.11, 0.10, 0.14)), iris=(0.36, 0.30, 0.52),
                outfit=sailor_f(BLUE, legs=WHITE, thigh=0.36) + [("hairbow", dict(color=RED, at=(150.0, 0.30)))]),
    # ------------------------------------------------------------------ staff
    "Valmont": _m("Professor Valmont", M_NARROW, hair=hair("tied", (0.92, 0.85, 0.52)), iris=(0.48, 0.36, 0.60),
                  head=dict(jaw=0.94, chin=0.012, face_w=0.97), skin=SKIN_FAIR, lips=(0.62, 0.22, 0.40),
                  brows=dict(angle=8.0, thick=0.0026), expression=dict(Fun=0.35, BrowAngry=0.3),
                  outfit=coat_m(GOLD, coat=BLUE, pants=BLUE, shirt=(0.95, 0.62, 0.74), shoes=BLACK, mark="star",
                                hem=0.48) + [("scarf", dict(color=(0.95, 0.62, 0.74)))]),
    # ------------------------------------------------------------------ generic students (tinted in Unreal)
    "StudentM1": _m("Student", M_SOFT, hair=hair("messy", TINT), iris=(0.36, 0.26, 0.18), tint=["jacket", "hair"],
                    expression=dict(Fun=0.3),
                    outfit=bomber_m(TINT, body=TINT, sleeves=TINT, slot="tint", pants=CHARCOAL, shoes=WHITE)),
    "StudentF1": _f("Student", F_ROUND, hair=hair("bob", TINT), iris=(0.36, 0.26, 0.18), tint=["hair"],
                    outfit=blazer_f(BLUE, jacket=WHITE)),
    "StudentF2": _f("Student", F_GENTLE, hair=hair("twintails", TINT), iris=(0.30, 0.34, 0.22), tint=["hair"],
                    expression=dict(Fun=0.35), outfit=sailor_f(BLUE, thigh=0.56)),
}

# portrait-only and story-extra designs (built on demand by the portrait renderer)
EXTRAS = {
    "Corvin": _m("Professor Corvin", M_NARROW, hair=hair("long_m", (0.16, 0.14, 0.15)), iris=(0.40, 0.34, 0.24),
                 expression=dict(Fun=0.4, EyeJoy=0.6), outfit=suit_m(RED, suit=(0.30, 0.30, 0.34), coat=WHITE)
                 + [("glasses", dict(color=SILVER, round_=0.2))]),
    "Hale": _m("Chancellor Hale", M_SOFT, build=1.25, hair=hair("bald_ring", (0.55, 0.52, 0.50), cap=(0.60, 0.50, 0.74)),
               iris=(0.36, 0.28, 0.20), head=dict(jaw=1.15, cheek=1.08), expression=dict(Fun=0.4),
               outfit=suit_m(GOLD, suit=(0.52, 0.16, 0.20))),
    "Marta": _f("Marta Ives", F_GENTLE, build=1.15, skin=SKIN_WARM, hair=hair("lowtails", (0.50, 0.34, 0.24)),
                iris=(0.34, 0.26, 0.18), expression=dict(Fun=0.5), outfit=dress_f(RED, dress=(0.80, 0.42, 0.40),
                                                                                  apron=WHITE)),
    "Lysa": _f("Nurse Lysa", F_SHARP, hair=hair("ponytail", (0.55, 0.20, 0.24)), iris=(0.40, 0.28, 0.24),
               lips=(0.80, 0.30, 0.34), outfit=dress_f(BLUE, dress=WHITE, legs=(0.22, 0.20, 0.24))),
    "Sable": _m("Professor Sable", M_SHARP, skin=SKIN_TAN, hair=hair("swept", (0.14, 0.12, 0.12)),
                iris=(0.42, 0.30, 0.18), outfit=suit_m(YELLOW, suit=shade(YELLOW, v=0.55, s=0.8))),
    "Nix": _m("Nix", M_NARROW, hair=hair("long_m", (0.10, 0.09, 0.13), (0.30, 0.12, 0.34)), iris=(0.70, 0.22, 0.30),
              skin=(0.92, 0.88, 0.88), expression=dict(BrowAngry=0.6), mouth=dict(smile=-0.001),
              outfit=coat_m(PLUM, coat=(0.07, 0.07, 0.10), pants=BLACK, mark="diamond")),
    "Mirel": _f("Mirel Quince", F_BRIGHT, build=0.94, hair=hair("sidetail", (0.20, 0.22, 0.42)),
                iris=(0.55, 0.40, 0.22), expression=dict(Fun=0.5), outfit=blazer_f(RED, jacket=shade(RED, v=0.9),
                                                                                  skirt=CHARCOAL, legs=BLACK,
                                                                                  thigh=0.56)),
    "Tavi": _f("Tavi Brandt", F_SLEEPY, skin=SKIN_TAN, hair=hair("short_f", (0.90, 0.88, 0.84)),
               iris=(0.30, 0.60, 0.56), outfit=cardigan_f(YELLOW, mark="disc")),
    "Ione": _f("Ione Falk", F_GENTLE, hair=hair("wavy", (0.42, 0.26, 0.48), (0.80, 0.50, 0.70)), iris=(0.55, 0.36, 0.60),
               outfit=cardigan_f(BLUE, knit=(0.86, 0.84, 0.94)) + [("hairbow", dict(color=WHITE, at=(215.0, 0.33)))]),
}


def student_m(name, accent, style, color, eyes=M_SOFT, mark="diamond", kind="blazer", **kw):
    wear = {"blazer": lambda: blazer_m(accent, mark=mark), "bomber": lambda: bomber_m(accent, mark=mark),
            "vest": lambda: vest_m(accent, mark=mark), "coat": lambda: coat_m(accent, mark=mark)}[kind]()
    return _m(name, eyes, hair=hair(style, color), outfit=wear, **kw)


for _key, _args in {
    "Garrick": ("Garrick", RED, "messy", (0.40, 0.28, 0.18), M_SOFT, "diamond", "blazer", dict(expression=dict(Fun=0.4))),
    "Benno": ("Benno", YELLOW, "mop", (0.30, 0.22, 0.16), M_ROUND, "disc", "blazer", dict(build=1.2, blush=0.3)),
    "Thorne": ("Thorne", YELLOW, "spiky", (0.20, 0.26, 0.18), M_SHARP, "disc", "bomber", dict(iris=(0.36, 0.46, 0.26))),
    "Dmitar": ("Dmitar", YELLOW, "neat", (0.11, 0.11, 0.13), M_NARROW, "disc", "vest", dict()),
    "Tobias": ("Tobias", BLUE, "swept", (0.82, 0.66, 0.36), M_SHARP, "star", "blazer", dict(iris=(0.40, 0.44, 0.30))),
    "Torin": ("Torin", BLUE, "long_m", (0.15, 0.13, 0.18), M_NARROW, "star", "coat", dict(iris=(0.34, 0.28, 0.44))),
    "Conall": ("Conall", BLUE, "spiky", (0.36, 0.22, 0.14), M_SOFT, "star", "blazer", dict()),
    "Dane": ("Dane", BLUE, "tall", (0.18, 0.18, 0.22), M_SHARP, "star", "coat", dict(expression=dict(BrowAngry=0.4))),
    "Shade": ("Unknown Student", RED, "mop", (0.20, 0.20, 0.24), M_NARROW, "diamond", "blazer", dict()),
}.items():
    EXTRAS[_key] = student_m(*_args[:7], **_args[7])


def all_designs():
    out = dict(DESIGNS)
    out.update(EXTRAS)
    return out
