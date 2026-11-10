"""
Original looks on the VRoid sample base models.

The cast's faces, bodies and facial rigs are the official VRoid sample avatars (AvatarSample_A / B / C; their
embedded terms allow modification and redistribution, see Tools/thirdparty/vroid/*/SOURCE.txt). Each cast
slot gets its own look on top of a base: hair restyle (hairdo.py / hairshape.py), hair and eye colours, face
shape, resting expression, outfit and height. The looks are the project's own designs.

look() builds a cast entry in the vocabulary of models.build_model:

  model      vroid_a / vroid_b (girls), vroid_c (boys)
  outfit     None: the base model's own outfit, recoloured ("colors"); or a tailored set (outfit.py):
             short() jacket, blazer(), coat(), girl()
  hairdo     restyle of the base hair (shape(), top_layer, glasses, ...)
  face_shape {chin, jaw, cheeks}; expression: resting mix of the facial morphs
"""

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


def look(model, hair, iris, outfit=None, colors=None, hairdo=None, female=None, tint=(), **kw):
    """One cast look (the fields models.build_model reads). hair: (colour, second colour or None)."""
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


# --------------------------------------------------------------------------- hair restyles
_CLIPS = ("HAIR_03", "HAIR_04", "HAIR_05", "HAIR_06")        # vroid_b's hair ornaments
SPIKY = dict(shape=_shape(flow=dict(lift=0.45, up=0.3, sweep=0.35, length=1.15, front_lift=0.1, front_length=1.1,
                                    crown_lift=0.25, side_lift=0.3), volume=dict(top=2.8, back=2.3, side=1.6, loft=0.022)),
             top_layer=0.025)
NEAT = dict(shape=_shape(flow=dict(lift=0.1, up=0.2, length=1.0, front_lift=0.0, front_length=0.95, crown_lift=0.0)))
MOP = dict(shape=_shape(flow=dict(lift=0.5, up=0.35, length=1.08, front_lift=0.2, front_length=1.08, crown_lift=0.25),
                        volume=dict(top=2.6, back=2.3, side=1.8, loft=0.024), envelope=dict(side=1.6, jaw=1.4)))
TALL = dict(shape=_shape(flow=dict(lift=0.25, up=1.2, length=1.15, front_lift=0.7, front_length=1.05, crown_lift=0.15)))
MESSY = dict(shape=_shape(flow=dict(lift=0.3, up=0.6, sweep=0.4, length=1.22, front_lift=0.05, front_length=1.05,
                                    crown_lift=0.15)))
PUFF = dict(shape=_shape(flow=dict(lift=0.0, up=0.2, length=1.1, front_lift=0.0, front_length=1.0, crown_lift=0.0,
                                   side_lift=0.5), volume=dict(top=2.0, back=1.8, side=2.0, loft=0.015),
                         envelope=dict(side=1.65, jaw=1.5)))
LONG = dict(source="vroid_b", long_only=True, drop=_CLIPS,
            shape=_shape(flow=dict(lift=0.0, up=0.1, length=1.4, front_lift=0.0, front_length=1.05, crown_lift=0.0),
                         volume=dict(top=2.1, back=1.9, side=1.3, loft=0.014), envelope=dict(side=1.4, jaw=1.2)))
BOB = dict(shape=_shape(volume=dict(top=2.2, back=2.0, side=1.5), envelope=dict(side=1.55, jaw=1.45)))
TWIN = dict(shape=_shape(volume=dict(top=2.0, back=1.6, side=1.3, loft=0.012), envelope=dict(side=1.45, jaw=1.35),
                         keep=_CLIPS, audit=dict(width=2.45)))


def _glasses(hairdo, color=(0.30, 0.30, 0.32)):
    return dict(hairdo, glasses=color)


def _dorm(jacket, pants=CHARCOAL, shoes=BROWN, skirt=None):
    return dict(jacket=jacket, pants=pants, skirt=skirt or pants, shoes=shoes)


# --------------------------------------------------------------------------- the looks, by cast slot
LOOKS = {
    "jaden": look("vroid_c", ((0.74, 0.30, 0.16), (0.96, 0.62, 0.22)), (0.80, 0.50, 0.16), hairdo=SPIKY,
                  colors=_dorm(RED, CHARCOAL, WHITE), expression=dict(Fun=0.5)),
    "syrus": look("vroid_c", ((0.45, 0.72, 0.78), (0.30, 0.50, 0.66)), (0.35, 0.60, 0.62), hairdo=_glasses(MOP),
                  colors=_dorm(RED, CREAM, (0.20, 0.30, 0.55)), expression=dict(BrowSorrow=0.45),
                  face_shape=dict(cheeks=0.06)),
    "chumley": look("vroid_c", ((0.24, 0.17, 0.14), None), (0.40, 0.28, 0.16), hairdo=PUFF,
                    colors=_dorm(CREAM, (0.30, 0.30, 0.34), BROWN), expression=dict(Fun=0.3),
                    face_shape=dict(cheeks=0.12, jaw=0.06)),
    "bastion": look("vroid_c", ((0.16, 0.18, 0.24), None), (0.30, 0.42, 0.50), hairdo=NEAT,
                    colors=_dorm(YELLOW, (0.22, 0.24, 0.30), BROWN), face_shape=dict(chin=0.006, jaw=-0.03)),
    "chazz": look("vroid_c", ((0.10, 0.10, 0.13), None), (0.42, 0.42, 0.50), hairdo=TALL,
                  outfit=coat(BLACK, (0.35, 0.25, 0.40)), colors=_dorm(BLACK, BLACK, BLACK),
                  expression=dict(BrowAngry=0.5), face_shape=dict(chin=0.010, jaw=-0.05)),
    "zane": look("vroid_c", ((0.20, 0.33, 0.42), (0.12, 0.20, 0.30)), (0.32, 0.50, 0.58), hairdo=LONG,
                 colors=_dorm(WHITE, NAVY, NAVY), face_shape=dict(chin=0.014, jaw=-0.07)),
    "alexis": look("vroid_a", ((0.92, 0.80, 0.50), (0.98, 0.90, 0.68)), (0.62, 0.48, 0.26), hairdo=LONG,
                   colors=_dorm(WHITE, BLUE, BROWN, BLUE), expression=dict(Fun=0.2), face_shape=dict(chin=0.006)),
    "jasmine": look("vroid_a", ((0.60, 0.26, 0.16), None), (0.45, 0.30, 0.20), hairdo=BOB,
                    colors=_dorm(CREAM, BLUE, BROWN, BLUE), expression=dict(Fun=0.45)),
    "mindy": look("vroid_b", ((0.11, 0.10, 0.14), None), (0.36, 0.30, 0.52), hairdo=TWIN,
                  colors=_dorm(WHITE, BLUE, BLACK, BLUE)),
    "crowler": look("vroid_c", ((0.92, 0.85, 0.52), None), (0.48, 0.36, 0.60), hairdo=LONG, female=False,
                    outfit=coat(BLUE, GOLD, shirt=(0.95, 0.62, 0.74), pants=BLUE), colors=_dorm(BLUE, BLUE, BLACK, None),
                    expression=dict(Fun=0.35, BrowAngry=0.3), face_shape=dict(chin=0.018, jaw=-0.09)),
    "student_m1": look("vroid_c", (TINT_BASE, None), (0.35, 0.25, 0.18), hairdo=MESSY, tint=("jacket", "hair"),
                       colors=_dorm(WHITE, CHARCOAL, BROWN), expression=dict(Fun=0.3)),
    "student_f1": look("vroid_a", (TINT_BASE, None), (0.35, 0.25, 0.18), hairdo=BOB, tint=("hair",),
                       colors=_dorm(WHITE, BLUE, BROWN, BLUE)),
    "student_f2": look("vroid_b", (TINT_BASE, None), (0.30, 0.34, 0.22), hairdo=TWIN, tint=("hair",),
                       colors=_dorm(WHITE, BLUE, BROWN, BLUE), expression=dict(Fun=0.3)),
    # portrait-only speakers
    "banner": look("vroid_c", ((0.16, 0.14, 0.15), None), (0.40, 0.34, 0.24), hairdo=_glasses(LONG, (0.80, 0.82, 0.86)),
                   colors=_dorm(WHITE, (0.30, 0.30, 0.34)), expression=dict(Fun=0.4, EyeJoy=0.5)),
    "sheppard": look("vroid_c", ((0.55, 0.52, 0.50), None), (0.36, 0.28, 0.20), hairdo=NEAT,
                     colors=_dorm((0.52, 0.16, 0.20), (0.30, 0.20, 0.20)), expression=dict(Fun=0.4),
                     face_shape=dict(cheeks=0.12, jaw=0.08)),
    "mimicry": look("vroid_c", ((0.90, 0.88, 0.84), None), (0.30, 0.60, 0.56), hairdo=MOP,
                    colors=_dorm(YELLOW, CHARCOAL, BROWN)),
    "dorothy": look("vroid_a", ((0.50, 0.34, 0.24), None), (0.34, 0.26, 0.18), hairdo=BOB,
                    colors=_dorm((0.80, 0.42, 0.40), CREAM, BROWN, CREAM), expression=dict(Fun=0.5),
                    face_shape=dict(cheeks=0.10)),
    "fontaine": look("vroid_a", ((0.55, 0.20, 0.24), None), (0.40, 0.28, 0.24), hairdo=LONG,
                     colors=_dorm(WHITE, (0.22, 0.20, 0.24), BLACK), face_shape=dict(chin=0.008)),
    "sartyr": look("vroid_c", ((0.14, 0.12, 0.12), None), (0.42, 0.30, 0.18), hairdo=TALL,
                   colors=_dorm((0.50, 0.42, 0.18), CHARCOAL)),
    "beauregard": look("vroid_c", ((0.30, 0.22, 0.16), None), (0.34, 0.24, 0.14), hairdo=PUFF,
                       colors=_dorm(YELLOW), expression=dict(Fun=0.4), face_shape=dict(cheeks=0.12, jaw=0.06)),
    "brier": look("vroid_c", ((0.20, 0.26, 0.18), None), (0.36, 0.46, 0.26), hairdo=SPIKY, colors=_dorm(YELLOW),
                  expression=dict(BrowAngry=0.3, Fun=0.2)),
    "dimitri": look("vroid_c", ((0.11, 0.11, 0.13), None), (0.30, 0.24, 0.18), hairdo=NEAT, colors=_dorm(YELLOW),
                    expression=dict(BrowAngry=0.2)),
    "gerard": look("vroid_c", ((0.40, 0.28, 0.18), None), (0.38, 0.28, 0.18), hairdo=MESSY, colors=_dorm(RED),
                   expression=dict(Fun=0.3)),
    "topher": look("vroid_c", ((0.82, 0.66, 0.36), None), (0.42, 0.34, 0.22), hairdo=NEAT, colors=_dorm(BLUE),
                   expression=dict(BrowAngry=0.2, Fun=0.25)),
    "torrey": look("vroid_c", ((0.15, 0.13, 0.18), None), (0.34, 0.28, 0.44), hairdo=LONG, colors=_dorm(BLUE),
                   expression=dict(BrowAngry=0.25)),
    "conklin": look("vroid_c", ((0.36, 0.22, 0.14), None), (0.36, 0.26, 0.18), hairdo=SPIKY, colors=_dorm(BLUE),
                    expression=dict(BrowAngry=0.2)),
    "damon": look("vroid_c", ((0.18, 0.18, 0.22), None), (0.30, 0.28, 0.26), hairdo=TALL, colors=_dorm(BLUE),
                  expression=dict(BrowAngry=0.35)),
    "blair": look("vroid_b", ((0.20, 0.22, 0.42), None), (0.55, 0.40, 0.22), hairdo=TWIN,
                  colors=_dorm(RED, CHARCOAL, BLACK, CHARCOAL), expression=dict(Fun=0.5)),
    "shadow_duelist": look("vroid_c", ((0.10, 0.09, 0.13), (0.30, 0.12, 0.34)), (0.70, 0.22, 0.30), hairdo=LONG,
                           outfit=coat((0.07, 0.07, 0.10), PLUM), colors=_dorm(BLACK, BLACK, BLACK),
                           expression=dict(BrowAngry=0.6), face_shape=dict(chin=0.018, jaw=-0.09), outline=0.0030),
    "unknown_student": look("vroid_c", ((0.20, 0.20, 0.24), None), (0.35, 0.25, 0.18), hairdo=MOP, colors=_dorm(RED)),
}


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
