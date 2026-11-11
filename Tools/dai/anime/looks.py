"""
Original looks on the VRoid sample base models.

The cast's faces, bodies and facial rigs are the official VRoid sample avatars (AvatarSample_A / B / C; their
embedded terms allow modification and redistribution, see Tools/thirdparty/vroid/*/SOURCE.txt). Each cast
slot gets its own look on top of a base: generated clump hair (clumphair.py), hair and eye colours, face
shape, resting expression, outfit and height. The looks are the project's own designs.

look() builds a cast entry in the vocabulary of models.build_model:

  model      vroid_a / vroid_b (girls), vroid_c (boys)
  wear       generated garments cut from the base body's own cross-sections (wardrobe.py): a list of
             (garment kind, params) in wearing order, in the atelier's vocabulary (atelier/outfit.GARMENTS) -
             the presets below (bomber, sweater, vest, blazer, tunic, coat, suit; sailor, blazer_f, cardigan,
             pinafore, dress). What every look uses; the base model's shoes stay (colors["shoes"])
  outfit     the older alternatives when a look has no "wear": None - the base model's own outfit,
             recoloured ("colors") - or a set tailored from the skin (outfit.py): short(), blazer(), coat(), girl()
  hair_style generated clump hair replacing the base hair: {style: recipe sections, ombre, accent, tie, ...}
             (clumphair.py; recipes in atelier/styles.py) - what every look below uses
  hairdo     the older alternative: restyle of the base model's own hair (shape(), top_layer, ...)
  accessories {glasses: colour, earrings: (metal, stone), nose: colour, ruff: colour}
  face_shape {chin, jaw, cheeks}; expression: resting mix of the facial morphs
"""

from .atelier import designs as D
from .atelier.paint import shade
from .atelier.styles import styled

WHITE = (0.96, 0.96, 0.95)
BLACK = (0.09, 0.09, 0.11)
NAVY = (0.12, 0.15, 0.29)
CHARCOAL = (0.19, 0.20, 0.25)
CREAM = (0.96, 0.92, 0.84)
BROWN = (0.36, 0.22, 0.15)
GOLD = (0.90, 0.72, 0.30)
RED = (0.78, 0.20, 0.21)
YELLOW = (0.95, 0.79, 0.32)
BLUE = (0.14, 0.28, 0.68)
PLUM = (0.42, 0.20, 0.44)
TINT_BASE = (0.92, 0.92, 0.92)
BASE_HEIGHT = {"vroid_a": 1.550, "vroid_b": 1.511, "vroid_c": 1.743}     # crown height of each base (m)

_EYES_BOY = dict(w=0.31, h=0.38, spacing=0.40, z=-0.16, shape="round", lash=0.15)
_EYES_GIRL = dict(w=0.33, h=0.44, spacing=0.40, z=-0.16, shape="round", lash=0.17, female=True, iris_h=1.0)


def _face(eyes=None, brows=None, mouth=None, **kw):
    out = dict(eyes=dict(_EYES_BOY, **(eyes or {})), brows=dict(brows or {}), mouth=dict(mouth or {}))
    out.update(kw)
    return out




def _shape(flow=None, volume=None, envelope=None, clump=None, widen=1.5, **kw):
    """Coherent anime volume for a base model's own cut: big soft masses, a rounded outline, no gaps."""
    out = dict(coherence=0.018, widen=widen if isinstance(widen, dict) else dict(k=widen, tip=0.5),
               clump=dict(dict(size=5, pull=0.65, power=1.6), **(clump or {})),
               volume=dict(dict(top=2.4, back=2.0, side=1.4, front=1.15, loft=0.018), **(volume or {})),
               envelope=dict(dict(side=1.5, jaw=1.3), **(envelope or {})))
    if flow:
        out["flow"] = flow
    out.update(kw)
    return out


def short(color, trim, shirt=WHITE, pants=CHARCOAL, open_=0.0, **kw):
    """Waist-length jacket with a stand collar over a shirt, trousers."""
    j = dict(color=color, trim=trim, trims=("front", "hem", "cuff", "collar"), open=open_, length="waist", drop=0.06,
             collar=0.05, collar_flare=0.03, lining=WHITE, cuff_color=color, cuff_w=0.05, trim_w=0.008)
    j.update(kw)
    return dict(jacket=j, shirt=dict(color=shirt, sleeves="short", length="waist"), pants=dict(color=pants, width=0.053))


def blazer(color, trim, shirt=WHITE, pants=CHARCOAL, open_=0.3, **kw):
    j = dict(color=color, trim=trim, trims=("front", "cuff", "collar"), open=open_, length="hip", collar=0.05)
    j.update(kw)
    return dict(jacket=j, shirt=dict(color=shirt, sleeves="short"), pants=dict(color=pants, width=0.053))


def coat(color, trim, shirt=CHARCOAL, pants=BLACK, open_=0.6, **kw):
    j = dict(color=color, trim=trim, trims=("front", "hem", "cuff", "collar"), open=open_, length="knee", collar=0.06,
             collar_flare=0.045, lining=WHITE, cuff_color=trim, trim_w=0.014)
    j.update(kw)
    return dict(jacket=j, shirt=dict(color=shirt, sleeves="short"), pants=dict(color=pants, width=0.053))


def girl(color, trim, skirt, boots=None, shirt=BLACK, **kw):
    """Sleeveless fitted jacket over a high-neck top, pleated skirt, boots."""
    j = dict(color=color, trim=trim, trims=("front", "hem", "cuff", "collar"), open=0.0, length="waist", sleeves="none",
             collar=0.045, collar_flare=0.04, lining=WHITE, trim_w=0.014)
    j.update(kw)
    return dict(jacket=j, shirt=dict(color=shirt, sleeves="none", length="waist", turtleneck=True),
                skirt=dict(color=skirt, length=0.15, pleats=18, belt=trim), boots=dict(color=boots or skirt, top=0.86))


# --------------------------------------------------------------------------- wardrobe (wardrobe.py)
# Original outfits in the atelier's garment vocabulary; `accent` is the wearer's dorm colour. The cuts come
# from atelier/designs.py where one fits; _fit() adapts a preset to the VRoid bodies.
TINT = D.TINT


def _fit(wear):
    """Layer a garment list for the VRoid bodies: straight trousers instead of leg-hugging ones, the belt
    under the jacket, every outer top clear of the layer below it."""
    out, tops = [], 0
    for kind, p in wear:
        p = dict(p)
        if kind == "pants":
            if p.get("hem", 0.10) < 0.5:
                p["ease"] = max(p.get("ease", 0.012), 0.018)
                p.setdefault("flare", 0.016)
        elif kind == "belt":
            if tops < 2:                             # worn under the jacket
                p["ease"] = min(p.get("ease", 0.016), 0.013)
        elif kind == "top":
            tops += 1
            if tops == 2 and p.get("ease", 0.010) >= 0.011:
                p["ease"] = max(p["ease"], 0.024 if p.get("tail") else 0.019)
            elif tops > 2:
                p["ease"] = max(p.get("ease", 0.010), 0.026)
        out.append((kind, p))
    return out


def bomber(accent, **kw):
    """Short zipped jacket with contrast sleeves and a stand collar."""
    return _fit(D.bomber_m(accent, **kw))


def blazer_m(accent, **kw):
    """Shirt and tie under an open piped blazer, deck box on the belt."""
    return _fit(D.blazer_m(accent, **kw))


def vest(accent, **kw):
    """Rolled shirt sleeves, tie and a fitted vest."""
    return _fit(D.vest_m(accent, **kw))


def long_coat(accent, **kw):
    """Long open coat with a lined edge over a high-collar shirt."""
    return _fit(D.coat_m(accent, **kw))


def suit(accent, **kw):
    """Staff suit; coat=<colour>: an open long coat over it."""
    return _fit(D.suit_m(accent, **kw))


def sweater(accent, knit=NAVY, pants=CHARCOAL, shirt=WHITE, mark="diamond"):
    """V-neck pullover with striped ribbing over a shirt and tie."""
    rib = shade(knit, v=0.78)
    return _fit([("top", dict(color=shirt, hem=0.97, ease=0.006, sleeve_to=0.66, cells=(1, 1))),
                 ("collar", dict(color=shirt, kind="shirt")),
                 ("tie", dict(color=accent, length=0.12)),
                 ("pants", dict(color=pants, ease=0.016)),
                 ("top", dict(color=knit, hem=0.93, ease=0.019, v=0.10, cuff=-0.003, flare=-0.004, sleeve_to=0.645,
                              style=dict(hem=[(0.035, rib), (0.02, accent), (0.03, rib)]),
                              sleeve_style=dict(hem=[(0.05, rib), (0.025, accent), (0.03, rib)])))] + D._pin(accent, kind=mark))


def tunic(accent, cloth=WHITE, pants=NAVY, slot="cloth", mark="diamond", piping=None):
    """Closed hip-length tunic with a stand collar, piped front and a row of buttons."""
    piping = piping or accent
    return _fit([("top", dict(color=BLACK, hem=0.97, ease=0.005, sleeves="short", cells=(1, 1))),
                 ("pants", dict(color=pants, ease=0.016)),
                 ("top", dict(color=cloth, hem=0.87, ease=0.019, slot=slot, cuff=0.003, flare=0.004,
                              style=dict(hem=[(0.03, piping)], edge=[(0.012, piping)]),
                              sleeve_style=dict(hem=[(0.06, piping), (0.015, cloth), (0.012, piping)]))),
                 ("collar", dict(color=piping, kind="stand", slot=slot)),
                 ("belt", dict(color=shade(pants, v=0.7), z=1.0, ease=0.025, pouch=shade(accent, v=0.85))),
                 ("buttons", dict(color=GOLD, z0=1.08, z1=1.32, n=4, x=0.0, r=0.007))] + D._pin(GOLD, kind=mark))


def sailor(accent, **kw):
    """Sailor blouse with a striped collar and a pleated skirt."""
    return _fit(D.sailor_f(accent, **kw))


def blazer_f(accent, **kw):
    """Shirt and ribbon under a cropped piped blazer, pleated skirt, socks."""
    return _fit(D.blazer_f(accent, **kw))


def cardigan(accent, **kw):
    """Loose knit over a shirt, long ribbon, tights."""
    return _fit(D.cardigan_f(accent, **kw))


def dress(accent, **kw):
    """Long-sleeved dress with a flared hem; apron=<colour> adds one."""
    return _fit(D.dress_f(accent, **kw))


def pinafore(accent, cloth=None, blouse=WHITE, legs=WHITE, thigh=0.36, length=0.33):
    """Puff-sleeved blouse under a sleeveless V-neck bodice and a pleated skirt in one colour."""
    cloth = cloth or shade(accent, v=0.8)
    return _fit([("top", dict(color=blouse, hem=0.985, ease=0.006, sleeves="short", puff=0.012, cells=(1, 1),
                              sleeve_style=dict(hem=[(0.14, accent)]))),
                 ("collar", dict(color=blouse, kind="shirt")),
                 ("bow", dict(color=accent, size=0.8, z=1.345, knot=GOLD)),
                 ("skirt", dict(color=cloth, length=length, pleats=16, style=dict(hem=[(0.03, WHITE), (0.03, cloth),
                                                                                    (0.02, WHITE)]))),
                 ("top", dict(color=cloth, hem=1.0, ease=0.019, sleeves="none", v=0.15,
                              style=dict(edge=[(0.014, WHITE)]))),
                 ("buttons", dict(color=GOLD, z0=1.06, z1=1.14, n=2, x=0.028, r=0.007, double=True)),
                 ("legwear", dict(color=legs, top=thigh, style=dict(top=[(0.05, accent)])))])


def look(model, hair, iris, outfit=None, colors=None, hairdo=None, female=None, tint=(), **kw):
    """One cast look (the fields models.build_model reads). hair: (colour, second colour or None);
    hair_style: clump hair (see _hair below); accessories: {glasses: colour, ...} (hairdo.accessories)."""
    female = model != "vroid_c" if female is None else female
    col = dict(jacket=NAVY, trim=WHITE, inner=WHITE, pants=CHARCOAL, skirt=NAVY, shoes=BROWN, sole=WHITE)
    col.update(colors or {})
    h = dict(style="base", color=hair[0])
    if hair[1]:
        h["color2"] = hair[1]
    out = dict(model=model, base_height=BASE_HEIGHT[model], female=female, body=dict(female=female), colors=col, hair=h,
               face=_face(eyes=dict(_EYES_GIRL if female else _EYES_BOY, iris=iris)), tint=list(tint))
    if outfit:
        out["outfit"] = outfit
    if hairdo:
        out["hairdo"] = hairdo
    out.update(kw)
    return out


# --------------------------------------------------------------------------- hair
# Every slot wears generated clump hair (clumphair.py) in one of the atelier recipes (atelier/styles.HAIR),
# varied per look: _hair(recipe, <section edits>, <options>). Options (not hair.py sections): ombre
# (start, length in metres from the crown of the fade into the second hair colour), accent / accent2 (colour
# of the locks a section marks accent=...), tie (hair-tie colour), highlight, seed, cap, outline.
_OPTIONS = ("ombre", "accent", "accent2", "tie", "highlight", "seed", "cap", "outline")


def _hair(recipe, **kw):
    opt = {k: kw.pop(k) for k in _OPTIONS if k in kw}
    return dict(style=styled(recipe, **kw), **opt)


def _glasses(color=(0.30, 0.30, 0.32)):
    return dict(glasses=color)


# The older way - restyling the base model's own cut (hairdo.py / hairshape.py, look key "hairdo") - still
# works for a look without "hair_style"; _shape() above builds its parameters.
def _dorm(jacket, pants=CHARCOAL, shoes=BROWN, skirt=None):
    return dict(jacket=jacket, pants=pants, skirt=skirt or pants, shoes=shoes)


# --------------------------------------------------------------------------- the looks, by cast slot
LOOKS = {
    "jaden": look("vroid_c", ((0.74, 0.30, 0.16), (0.96, 0.62, 0.22)), (0.80, 0.50, 0.16),
                  hair_style=_hair("spiky_up", ombre=(0.115, 0.07), ahoge=0.055),
                  colors=_dorm(RED, CHARCOAL, WHITE), expression=dict(Fun=0.5)),
    "syrus": look("vroid_c", ((0.45, 0.72, 0.78), (0.30, 0.50, 0.66)), (0.35, 0.60, 0.62),
                  hair_style=_hair("mop", ombre=(0.13, 0.10)), accessories=_glasses(),
                  colors=_dorm(RED, CREAM, (0.20, 0.30, 0.55)), expression=dict(BrowSorrow=0.45),
                  face_shape=dict(cheeks=0.06)),
    "chumley": look("vroid_c", ((0.24, 0.17, 0.14), None), (0.40, 0.28, 0.16), hair_style=_hair("curly"),
                    colors=_dorm(CREAM, (0.30, 0.30, 0.34), BROWN), expression=dict(Fun=0.3),
                    face_shape=dict(cheeks=0.12, jaw=0.06)),
    "bastion": look("vroid_c", ((0.16, 0.18, 0.24), None), (0.30, 0.42, 0.50), hair_style=_hair("neat"),
                    colors=_dorm(YELLOW, (0.22, 0.24, 0.30), BROWN), face_shape=dict(chin=0.006, jaw=-0.03)),
    "chazz": look("vroid_c", ((0.10, 0.10, 0.13), None), (0.42, 0.42, 0.50), hair_style=_hair("crest"),
                  colors=_dorm(BLACK, BLACK, BLACK),
                  expression=dict(BrowAngry=0.5), face_shape=dict(chin=0.010, jaw=-0.05)),
    "zane": look("vroid_c", ((0.20, 0.33, 0.42), (0.12, 0.20, 0.30)), (0.32, 0.50, 0.58),
                 hair_style=_hair("shag", ombre=(0.16, 0.12)),
                 colors=_dorm(WHITE, NAVY, NAVY), face_shape=dict(chin=0.014, jaw=-0.07)),
    "alexis": look("vroid_a", ((0.92, 0.80, 0.50), (0.98, 0.90, 0.68)), (0.62, 0.48, 0.26),
                   hair_style=_hair("long", ahoge=0.06, ombre=(0.40, 0.30)),
                   colors=_dorm(WHITE, BLUE, BROWN, BLUE), expression=dict(Fun=0.2), face_shape=dict(chin=0.006)),
    "jasmine": look("vroid_a", ((0.60, 0.26, 0.16), None), (0.45, 0.30, 0.20), hair_style=_hair("ponytail", tie=BLUE),
                    colors=_dorm(CREAM, BLUE, BROWN, BLUE), expression=dict(Fun=0.45)),
    "mindy": look("vroid_b", ((0.11, 0.10, 0.14), None), (0.36, 0.30, 0.52), hair_style=_hair("hime"),
                  colors=_dorm(WHITE, BLUE, BLACK, BLUE)),
    "crowler": look("vroid_c", ((0.92, 0.85, 0.52), None), (0.48, 0.36, 0.60), hair_style=_hair("lowtail", tie=PLUM),
                    female=False,
                    colors=_dorm(BLUE, BLUE, BLACK, None),
                    expression=dict(Fun=0.35, BrowAngry=0.3), face_shape=dict(chin=0.018, jaw=-0.09)),
    "student_m1": look("vroid_c", (TINT_BASE, None), (0.35, 0.25, 0.18), hair_style=_hair("messy"),
                       tint=("jacket", "hair"), colors=_dorm(WHITE, CHARCOAL, BROWN), expression=dict(Fun=0.3)),
    "student_f1": look("vroid_a", (TINT_BASE, None), (0.35, 0.25, 0.18), hair_style=_hair("bob"), tint=("hair",),
                       colors=_dorm(WHITE, BLUE, BROWN, BLUE)),
    "student_f2": look("vroid_b", (TINT_BASE, None), (0.30, 0.34, 0.22),
                       hair_style=_hair("twinbraids", tie=(0.75, 0.20, 0.25)), tint=("hair",),
                       colors=_dorm(WHITE, BLUE, BROWN, BLUE), expression=dict(Fun=0.3)),
    # portrait-only speakers
    "banner": look("vroid_c", ((0.16, 0.14, 0.15), None), (0.40, 0.34, 0.24), hair_style=_hair("tied", tie=WHITE),
                   accessories=_glasses((0.80, 0.82, 0.86)),
                   colors=_dorm(WHITE, (0.30, 0.30, 0.34)), expression=dict(Fun=0.4, EyeJoy=0.5)),
    "sheppard": look("vroid_c", ((0.55, 0.52, 0.50), None), (0.36, 0.28, 0.20), hair_style=_hair("crop"),
                     colors=_dorm((0.52, 0.16, 0.20), (0.30, 0.20, 0.20)), expression=dict(Fun=0.4),
                     face_shape=dict(cheeks=0.12, jaw=0.08)),
    "mimicry": look("vroid_c", ((0.90, 0.88, 0.84), None), (0.30, 0.60, 0.56), hair_style=_hair("swept"),
                    colors=_dorm(YELLOW, CHARCOAL, BROWN)),
    "dorothy": look("vroid_a", ((0.50, 0.34, 0.24), None), (0.34, 0.26, 0.18), hair_style=_hair("bun", tie=CREAM),
                    colors=_dorm((0.80, 0.42, 0.40), CREAM, BROWN, CREAM), expression=dict(Fun=0.5),
                    face_shape=dict(cheeks=0.10)),
    "fontaine": look("vroid_a", ((0.55, 0.20, 0.24), None), (0.40, 0.28, 0.24), hair_style=_hair("sidelong"),
                     colors=_dorm(WHITE, (0.22, 0.20, 0.24), BLACK), face_shape=dict(chin=0.008)),
    "sartyr": look("vroid_c", ((0.14, 0.12, 0.12), None), (0.42, 0.30, 0.18), hair_style=_hair("undercut"),
                   colors=_dorm((0.50, 0.42, 0.18), CHARCOAL)),
    "beauregard": look("vroid_c", ((0.30, 0.22, 0.16), None), (0.34, 0.24, 0.14),
                       hair_style=_hair("mop", fringe=dict(kind="m", to=0.37)),
                       colors=_dorm(YELLOW), expression=dict(Fun=0.4), face_shape=dict(cheeks=0.12, jaw=0.06)),
    "brier": look("vroid_c", ((0.20, 0.26, 0.18), None), (0.36, 0.46, 0.26), hair_style=_hair("spiky", spikes=dict(start=64.0)),
                  colors=_dorm(YELLOW), expression=dict(BrowAngry=0.3, Fun=0.2)),
    "dimitri": look("vroid_c", ((0.11, 0.11, 0.13), None), (0.30, 0.24, 0.18),
                    hair_style=_hair("neat", fringe=dict(kind="curtain", sweep=0.45)), colors=_dorm(YELLOW),
                    expression=dict(BrowAngry=0.2)),
    "gerard": look("vroid_c", ((0.40, 0.28, 0.18), None), (0.38, 0.28, 0.18), hair_style=_hair("messy", ahoge=0.05),
                   colors=_dorm(RED), expression=dict(Fun=0.3)),
    "topher": look("vroid_c", ((0.82, 0.66, 0.36), None), (0.42, 0.34, 0.22), hair_style=_hair("pushed"),
                   colors=_dorm(BLUE), expression=dict(BrowAngry=0.2, Fun=0.25)),
    "torrey": look("vroid_c", ((0.15, 0.13, 0.18), None), (0.34, 0.28, 0.44), hair_style=_hair("long_m"),
                   colors=_dorm(BLUE), expression=dict(BrowAngry=0.25)),
    "conklin": look("vroid_c", ((0.36, 0.22, 0.14), None), (0.36, 0.26, 0.18),
                    hair_style=_hair("crop", fringe=dict(kind="swept", sweep=0.3)), colors=_dorm(BLUE),
                    expression=dict(BrowAngry=0.2)),
    "damon": look("vroid_c", ((0.18, 0.18, 0.22), None), (0.30, 0.28, 0.26), hair_style=_hair("undercut", fringe=dict(part=20.0, sweep=-0.6)),
                  colors=_dorm(BLUE), expression=dict(BrowAngry=0.35)),
    "blair": look("vroid_b", ((0.20, 0.22, 0.42), None), (0.55, 0.40, 0.22), hair_style=_hair("odango", tie=YELLOW),
                  colors=_dorm(RED, CHARCOAL, BLACK, CHARCOAL), expression=dict(Fun=0.5)),
    "shadow_duelist": look("vroid_c", ((0.10, 0.09, 0.13), (0.30, 0.12, 0.34)), (0.70, 0.22, 0.30),
                           hair_style=_hair("long_m", fringe=dict(accent=[1, 4]), sides=dict(accent=[1]),
                                            accent=(0.52, 0.20, 0.56), ombre=(0.30, 0.20)),
                           colors=_dorm(BLACK, BLACK, BLACK),
                           expression=dict(BrowAngry=0.6), face_shape=dict(chin=0.018, jaw=-0.09), outline=0.0030),
    "unknown_student": look("vroid_c", ((0.20, 0.20, 0.24), None), (0.35, 0.25, 0.18),
                            hair_style=_hair("mop", fringe=dict(to=0.44)), colors=_dorm(RED)),
}

# --------------------------------------------------------------------------- who wears what
# Dorm accents: slifer red, ra yellow, obelisk blue. (colors["shoes"] above recolours the base model's shoes.)
_PINK = (0.95, 0.62, 0.74)
_LILAC = (0.86, 0.84, 0.94)
WEAR = {
    "jaden": bomber(RED, sleeves=WHITE, pants=CHARCOAL),
    "syrus": sweater(RED, knit=(0.62, 0.17, 0.19), pants=CREAM),
    "chumley": vest(RED, vest=CREAM, pants=shade(BROWN, v=0.8)),
    "bastion": blazer_m(YELLOW, jacket=shade(YELLOW, v=0.97), trim=WHITE, pants=(0.22, 0.24, 0.30), mark="disc"),
    "chazz": long_coat(shade(PLUM, v=0.9, s=0.7), coat=BLACK, pants=shade(NAVY, v=0.8), mark="star"),
    "zane": tunic(BLUE, cloth=WHITE, pants=NAVY, mark="star"),
    "alexis": blazer_f(BLUE, jacket=WHITE, skirt=BLUE, thigh=0.34),
    "jasmine": sailor(BLUE, top=CREAM, legs=WHITE, thigh=0.36),
    "mindy": cardigan(BLUE, knit=_LILAC, legs=BLACK),
    "crowler": long_coat(GOLD, coat=BLUE, pants=BLUE, shirt=_PINK, mark="star", hem=0.50),
    "student_m1": tunic(TINT, cloth=TINT, piping=shade(TINT, v=0.80), pants=CHARCOAL, slot="tint"),
    "student_f1": pinafore(BLUE),
    "student_f2": sailor(BLUE, skirt=NAVY, legs=BLACK, thigh=0.57, bow=YELLOW),
    # portrait-only speakers
    "banner": suit(RED, suit=(0.30, 0.30, 0.34), coat=WHITE),
    "sheppard": suit(GOLD, suit=(0.52, 0.16, 0.20)),
    "mimicry": blazer_m(YELLOW, jacket=CHARCOAL, mark="disc"),
    "dorothy": dress(RED, dress=(0.80, 0.42, 0.40), apron=CREAM),
    "fontaine": dress(BLUE, dress=WHITE, legs=(0.22, 0.20, 0.24)),
    "sartyr": suit(YELLOW, suit=shade(YELLOW, v=0.55, s=0.8)),
    "beauregard": vest(YELLOW, vest=shade(YELLOW, v=0.95), mark="disc"),
    "brier": bomber(YELLOW, mark="disc"),
    "dimitri": sweater(YELLOW, knit=(0.24, 0.24, 0.28), mark="disc"),
    "gerard": blazer_m(RED, jacket=shade(RED, v=0.9), trim=WHITE, tie=False),
    "topher": tunic(BLUE, cloth=shade(BLUE, v=0.9), piping=WHITE, pants=WHITE, mark="star"),
    "torrey": long_coat(BLUE, coat=NAVY, pants=CHARCOAL, mark="star", hem=0.62),
    "conklin": blazer_m(BLUE, jacket=NAVY, mark="star"),
    "damon": vest(BLUE, vest=NAVY, pants=CHARCOAL, mark="star"),
    "blair": blazer_f(RED, jacket=shade(RED, v=0.9), skirt=CHARCOAL, legs=BLACK, thigh=0.57, mark="diamond"),
    "shadow_duelist": long_coat(PLUM, coat=(0.07, 0.07, 0.10), pants=BLACK, mark="diamond"),
    "unknown_student": bomber(RED, body=CHARCOAL, sleeves=RED),
}
for _cid, _wear in WEAR.items():
    LOOKS[_cid]["wear"] = _wear


def apply(cid, entry):
    """Merge a slot's VRoid look into its cast entry when the base model is installed; otherwise the entry
    keeps its atelier design (the fully generated fallback)."""
    spec = LOOKS.get(cid)
    if not spec:
        return entry
    from .. import thirdparty
    import os
    reg = (thirdparty.registry().get("anime_models") or {}).get(spec["model"])
    if not reg or not os.path.exists(thirdparty.tp_path(reg["file"])):
        return entry
    out = dict(entry)
    out.update({k: (dict(v) if isinstance(v, dict) else v) for k, v in spec.items()})
    return out
