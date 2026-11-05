"""Portrait-only cast entries for named speakers who are not in the overworld cast.

The dialogue data has more named speakers than the island currently places as
3D characters (Banner, Sheppard, Dorothy, the Ra Yellow and Obelisk students,
...).  Rather than leave their dialogue frames empty, each one gets a cast look
here and is rendered through the same cel-shaded pipeline as the regulars.
These entries are used only by Tools/render_portraits.py; they are deliberately
not merged into cast.CAST, so they do not change the world build, schedules or
layout.
"""

from . import cast as C

WHITE = C.WHITE
SLIFER = C.SLIFER_RED
SLIFER_DARK = C.SLIFER_DARK
RA = C.RA_YELLOW
RA_DARK = C.RA_DARK
OBELISK = C.OBELISK_BLUE
OBELISK_TRIM = C.OBELISK_TRIM
SKIN = C.SKIN
UNIFORM_PANTS = C.UNIFORM_PANTS


def _girl_academy(jacket, dark, shirt, skirt, open_=0.0, panel=WHITE, **kw):
    """A dorm jacket over a pleated skirt (the girls' version of the regular uniform)."""
    out = C._academy(jacket, dark, shirt, UNIFORM_PANTS, open_=open_, panel=panel, **kw)
    out.pop("pants", None)
    out["skirt"] = dict(color=skirt, length=0.16, pleats=18)
    return out


def _colors(jacket, trim, inner, *, pants=None, skirt=None, shoes=(0.20, 0.16, 0.14),
            sole=(0.30, 0.30, 0.32), socks=None, boots=None, **extra):
    out = dict(jacket=jacket, trim=trim, inner=inner, shoes=shoes, sole=sole)
    if pants is not None:
        out["pants"] = pants
    if skirt is not None:
        out["skirt"] = skirt
    if socks is not None:
        out["socks"] = socks
    if boots is not None:
        out["boots"] = boots
    out.update(extra)
    return out


def _entry(name, dorm, height, model, body, outfit, hair, face, **kw):
    entry = dict(name=name, dorm=dorm, height=height, model=model, body=body, outfit=outfit,
                 hair=hair, face=face)
    entry.update(kw)
    return entry


# --------------------------------------------------------------------------- staff
def _banner():
    outfit = C._coat((0.18, 0.30, 0.17), (0.78, 0.70, 0.42), (0.94, 0.92, 0.84), (0.18, 0.20, 0.16),
                     open_=0.05, collar=0.055,
                     coat=dict(buttons=dict(color=(0.82, 0.72, 0.38), n=4),
                               shield=dict(color=(0.94, 0.92, 0.84), border=(0.78, 0.70, 0.42), w=0.12)))
    return _entry(
        "Lyman Banner", "teacher", 184, "vroid_c",
        dict(open=0.05, coat="long"), outfit,
        dict(style="crowler", color=(0.24, 0.38, 0.20), color2=(0.14, 0.26, 0.12)),
        C._face(eyes=dict(iris=(0.42, 0.48, 0.28), w=0.28, h=0.34, shape="sharp", spacing=0.37),
                brows=dict(color=(0.18, 0.26, 0.12), angle=-2.0, thick=0.032),
                mouth=dict(kind="smile", w=0.11), face_extras=["mustache"]),
        hairdo=dict(source="vroid_b", long_only=True, drop=("HAIR_03", "HAIR_04", "HAIR_05", "HAIR_06"),
                    shape=C._shape(volume=dict(top=2.0, back=1.7, side=1.3, loft=0.012),
                                   envelope=dict(side=1.45, jaw=1.3)),
                    glasses=(0.24, 0.24, 0.28)),
        face_shape=dict(chin=0.012, jaw=-0.07),
        expression=dict(MTH_Fun=0.25, EYE_Joy=0.2),
        colors=_colors((0.18, 0.30, 0.17), (0.78, 0.70, 0.42), (0.94, 0.92, 0.84),
                       pants=(0.18, 0.20, 0.16), shoes=(0.24, 0.16, 0.11)),
        extras=["glasses"],
    )


def _sheppard():
    outfit = C._coat((0.38, 0.11, 0.13), (0.86, 0.70, 0.28), (0.96, 0.94, 0.88), (0.20, 0.16, 0.14),
                     open_=0.05, collar=0.05,
                     coat=dict(buttons=dict(color=(0.86, 0.70, 0.28), n=4),
                               shield=dict(color=(0.96, 0.94, 0.88), border=(0.86, 0.70, 0.28), w=0.12)))
    return _entry(
        "Chancellor Sheppard", "teacher", 188, "vroid_c",
        dict(open=0.05, coat="long"), outfit,
        dict(style="neat", color=(0.40, 0.31, 0.25), color2=(0.28, 0.22, 0.18)),
        C._face(eyes=dict(iris=(0.34, 0.24, 0.16), w=0.28, h=0.32, shape="sharp", spacing=0.37),
                brows=dict(color=(0.26, 0.20, 0.16), angle=6.0, thick=0.045, arch=1.2),
                mouth=dict(kind="flat", w=0.11), face_extras=["mustache"]),
        hairdo=dict(shape=C._shape(flow=dict(lift=0.05, up=0.15, sweep=0.25, length=1.05,
                                             front_lift=0.0, front_length=1.0, crown_lift=0.0),
                                   volume=dict(top=2.0, back=1.8, side=1.3, loft=0.012),
                                   envelope=dict(side=1.4, jaw=1.2))),
        face_shape=dict(chin=0.02, jaw=-0.09),
        expression=dict(BRW_Angry=0.35, EYE_Angry=0.2, MTH_Fun=0.15),
        colors=_colors((0.38, 0.11, 0.13), (0.86, 0.70, 0.28), (0.96, 0.94, 0.88),
                       pants=(0.20, 0.16, 0.14), shoes=(0.12, 0.10, 0.09)),
    )


def _mimicry():
    outfit = C._coat((0.24, 0.17, 0.38), (0.66, 0.60, 0.80), (0.94, 0.92, 0.96), (0.16, 0.15, 0.22),
                     open_=0.15, collar=0.05,
                     coat=dict(buttons=dict(color=(0.72, 0.66, 0.88), n=3),
                               shield=dict(color=(0.94, 0.92, 0.96), border=(0.66, 0.60, 0.80), w=0.12)))
    return _entry(
        "Professor Mimicry", "teacher", 177, "vroid_c",
        dict(open=0.15, coat="long"), outfit,
        dict(style="neat", color=(0.40, 0.24, 0.50), color2=(0.28, 0.15, 0.36)),
        C._face(eyes=dict(iris=(0.48, 0.32, 0.62), w=0.28, h=0.3, shape="sharp", spacing=0.37, tilt=0.08),
                brows=dict(color=(0.24, 0.14, 0.30), angle=12.0, thick=0.035),
                mouth=dict(kind="smirk", w=0.10)),
        hairdo=dict(shape=C._shape(flow=dict(lift=0.35, up=0.35, sweep=0.35, length=1.15,
                                             front_lift=0.15, front_length=1.05, crown_lift=0.2),
                                   volume=dict(top=2.3, back=2.0, side=1.4, loft=0.016),
                                   envelope=dict(side=1.45, jaw=1.25)),
                    glasses=(0.22, 0.20, 0.26)),
        face_shape=dict(chin=0.018, jaw=-0.08),
        expression=dict(MTH_Fun=0.35, EYE_Joy=0.25, BRW_Angry=0.15),
        colors=_colors((0.24, 0.17, 0.38), (0.66, 0.60, 0.80), (0.94, 0.92, 0.96),
                       pants=(0.16, 0.15, 0.22), shoes=(0.12, 0.10, 0.14)),
        extras=["glasses"],
    )


def _dorothy():
    outfit = _girl_academy((0.62, 0.35, 0.22), (0.86, 0.64, 0.36), WHITE, (0.42, 0.24, 0.18),
                           open_=0.0, panel=(0.98, 0.92, 0.80),
                           coat=dict(length="knee", buttons=dict(color=(0.90, 0.72, 0.42), n=3)))
    return _entry(
        "Miss Dorothy", "teacher", 165, "vroid_a",
        dict(female=True, open=0.0, skirt=True, boots=False), outfit,
        dict(style="bob", color=(0.48, 0.28, 0.17), color2=(0.34, 0.18, 0.10)),
        C._face(eyes=dict(C._EYES_GIRL, iris=(0.48, 0.32, 0.18)),
                brows=dict(color=(0.36, 0.18, 0.10), angle=2.0, thick=0.026),
                mouth=dict(kind="smile", w=0.09), blush=0.28),
        hairdo=dict(shape=C._shape(flow=dict(lift=0.15, up=-0.1, length=1.12, front_lift=0.05,
                                             front_length=1.0, crown_lift=0.1, side_lift=0.25),
                                   volume=dict(top=2.1, back=1.9, side=1.4, loft=0.014),
                                   envelope=dict(side=1.5, jaw=1.4))),
        expression=dict(MTH_Fun=0.45, EYE_Joy=0.3),
        colors=_colors((0.62, 0.35, 0.22), (0.86, 0.64, 0.36), WHITE, skirt=(0.42, 0.24, 0.18),
                       socks=(0.95, 0.94, 0.90), shoes=(0.30, 0.18, 0.12)),
    )


def _fontaine():
    outfit = _girl_academy(WHITE, (0.84, 0.38, 0.55), (0.98, 0.84, 0.90), (0.80, 0.36, 0.52),
                           open_=0.0, panel=(1.0, 0.93, 0.96),
                           coat=dict(length="knee", buttons=dict(color=(0.90, 0.62, 0.72), n=3)))
    return _entry(
        "Fonda Fontaine", "teacher", 167, "vroid_a",
        dict(female=True, open=0.0, skirt=True, boots=False), outfit,
        dict(style="long_wavy", color=(0.90, 0.55, 0.66), color2=(0.72, 0.38, 0.50)),
        C._face(eyes=dict(C._EYES_GIRL, iris=(0.42, 0.30, 0.46)),
                brows=dict(color=(0.55, 0.28, 0.38), angle=4.0, thick=0.024),
                mouth=dict(kind="smile", w=0.09), blush=0.32),
        hairdo=dict(shape=C._shape(flow=dict(lift=0.1, up=-0.35, length=1.18, front_lift=0.0,
                                             front_length=1.0, crown_lift=0.12),
                                   volume=dict(top=2.2, back=2.0, side=1.35, loft=0.014),
                                   envelope=dict(side=1.45, jaw=1.35))),
        expression=dict(MTH_Fun=0.4, EYE_Joy=0.2),
        colors=_colors(WHITE, (0.84, 0.38, 0.55), (0.98, 0.84, 0.90),
                       skirt=(0.80, 0.36, 0.52), socks=(1.0, 0.98, 0.98), shoes=(0.90, 0.52, 0.64)),
    )


def _sartyr():
    outfit = C._academy(RA, RA_DARK, (0.92, 0.90, 0.78), (0.22, 0.24, 0.30), open_=0.0)
    return _entry(
        "Sartyr", "ra", 176, "vroid_c",
        dict(open=0.0), outfit,
        dict(style="neat", color=(0.30, 0.24, 0.16), color2=(0.20, 0.16, 0.10)),
        C._face(eyes=dict(iris=(0.36, 0.30, 0.20), w=0.28, h=0.32, shape="sharp", spacing=0.37),
                brows=dict(color=(0.22, 0.18, 0.12), angle=4.0, thick=0.038),
                mouth=dict(kind="smirk", w=0.10), face_extras=["mustache"]),
        hairdo=dict(shape=C._shape(flow=dict(lift=0.05, up=0.2, sweep=0.3, length=1.08,
                                             front_lift=0.0, front_length=1.0, crown_lift=0.0),
                                   volume=dict(top=2.0, back=1.8, side=1.3, loft=0.012),
                                   envelope=dict(side=1.4, jaw=1.2))),
        face_shape=dict(chin=0.012, jaw=-0.06),
        expression=dict(MTH_Fun=0.25, BRW_Angry=0.2),
        colors=_colors(RA, RA_DARK, (0.92, 0.90, 0.78), pants=(0.22, 0.24, 0.30),
                       shoes=(0.24, 0.18, 0.12)),
    )


# --------------------------------------------------------------------------- students
def _ra_boy(name, height, hair_color, hair_style, face, *, belly=0.0, model="vroid_c", **kw):
    outfit = C._academy(RA, RA_DARK, (0.94, 0.92, 0.84), (0.22, 0.24, 0.30), open_=0.0,
                        belly=belly)
    return _entry(
        name, "ra", height, model,
        dict(open=0.0, belly=belly), outfit,
        dict(style=hair_style, color=hair_color, color2=tuple(c * 0.75 for c in hair_color)),
        face,
        hairdo=kw.pop("hairdo", None),
        face_shape=kw.pop("face_shape", None),
        expression=kw.pop("expression", None),
        colors=_colors(RA, RA_DARK, (0.94, 0.92, 0.84), pants=(0.22, 0.24, 0.30),
                       shoes=(0.24, 0.18, 0.12)),
        **kw,
    )


def _obelisk_boy(name, height, hair_color, hair_style, face, **kw):
    outfit = C._coat(WHITE, OBELISK, (0.08, 0.08, 0.10), (0.12, 0.13, 0.20), open_=0.25,
                     collar=0.06,
                     coat=dict(shield=dict(color=WHITE, border=OBELISK, w=0.12, side=0.09, point=0.09)))
    return _entry(
        name, "obelisk", height, "vroid_c",
        dict(open=0.25, coat="long"), outfit,
        dict(style=hair_style, color=hair_color, color2=tuple(c * 0.75 for c in hair_color)),
        face,
        hairdo=kw.pop("hairdo", None),
        face_shape=kw.pop("face_shape", None),
        expression=kw.pop("expression", None),
        colors=_colors(WHITE, OBELISK, (0.08, 0.08, 0.10), pants=(0.12, 0.13, 0.20),
                       shoes=(0.10, 0.10, 0.12), sole=(0.3, 0.3, 0.32)),
        **kw,
    )


def _slifer_boy(name, height, hair_color, hair_style, face, **kw):
    outfit = C._academy(SLIFER, SLIFER_DARK, (0.94, 0.92, 0.84), UNIFORM_PANTS, open_=0.0)
    return _entry(
        name, "slifer", height, "vroid_c",
        dict(open=0.0), outfit,
        dict(style=hair_style, color=hair_color, color2=tuple(c * 0.75 for c in hair_color)),
        face,
        hairdo=kw.pop("hairdo", None),
        face_shape=kw.pop("face_shape", None),
        expression=kw.pop("expression", None),
        colors=_colors(SLIFER, SLIFER_DARK, (0.94, 0.92, 0.84), pants=UNIFORM_PANTS,
                       shoes=(0.30, 0.18, 0.12)),
        **kw,
    )


def _blair():
    outfit = _girl_academy(SLIFER, SLIFER_DARK, (0.96, 0.90, 0.62), (0.60, 0.16, 0.18), open_=0.0,
                           panel=(1.0, 0.96, 0.82))
    return _entry(
        "Blair Flannigan", "slifer", 154, "vroid_a",
        dict(female=True, open=0.0, skirt=True, boots=False), outfit,
        dict(style="bob", color=(0.92, 0.76, 0.42), color2=(0.76, 0.56, 0.26)),
        C._face(eyes=dict(C._EYES_GIRL, iris=(0.44, 0.30, 0.16)),
                brows=dict(color=(0.62, 0.44, 0.22), angle=2.0, thick=0.022),
                mouth=dict(kind="smile", w=0.08), blush=0.35),
        hairdo=dict(shape=C._shape(flow=dict(lift=0.12, up=-0.2, length=1.12, front_lift=0.05,
                                             front_length=1.0, crown_lift=0.08, side_lift=0.2),
                                   volume=dict(top=2.2, back=2.0, side=1.4, loft=0.014),
                                   envelope=dict(side=1.5, jaw=1.45))),
        expression=dict(MTH_Fun=0.4, EYE_Joy=0.25),
        colors=_colors(SLIFER, SLIFER_DARK, (0.96, 0.90, 0.62), skirt=(0.60, 0.16, 0.18),
                       socks=(0.95, 0.94, 0.90), shoes=(0.30, 0.18, 0.12)),
    )


def _unknown_student():
    """A generic Slifer student for the placeholder speaker in ui.json."""
    entry = dict(C.student_entry("student_m1"))
    entry["name"] = "Student"
    entry["tint"] = []
    entry["colors"] = dict(entry["colors"], jacket=SLIFER)
    entry["outfit"] = dict(entry["outfit"])
    entry["outfit"]["jacket"] = dict(entry["outfit"]["jacket"], color=SLIFER)
    entry["hair"] = dict(entry["hair"], color=(0.22, 0.15, 0.10))
    return entry


def _generic_student(key, hair_color):
    """A generic student bust with a readable hair colour instead of the white tint base.

    The jacket stays a neutral tint base (Unreal recolours it per dorm at runtime),
    but a static portrait needs a face and hair that read as a person.
    """
    entry = dict(C.student_entry(key))
    entry["name"] = "Student"
    entry["tint"] = [t for t in entry.get("tint", []) if t != "hair"]
    entry["hair"] = dict(entry["hair"], color=hair_color)
    return entry


def all_entries():
    """{id: entry} of portrait-only cast members."""
    entries = {
        "unknown_student": _unknown_student(),
        "student_m1": _generic_student("student_m1", (0.22, 0.15, 0.10)),
        "student_f1": _generic_student("student_f1", (0.12, 0.09, 0.08)),
        "student_f2": _generic_student("student_f2", (0.34, 0.20, 0.13)),
        "banner": _banner(),
        "sheppard": _sheppard(),
        "mimicry": _mimicry(),
        "dorothy": _dorothy(),
        "fontaine": _fontaine(),
        "sartyr": _sartyr(),
        "beauregard": _ra_boy(
            "Beauregard", 178, (0.28, 0.20, 0.14), "chumley",
            C._face(eyes=dict(iris=(0.34, 0.24, 0.14), w=0.24, h=0.28, spacing=0.36),
                    brows=dict(color=(0.18, 0.12, 0.08), thick=0.04),
                    mouth=dict(kind="smile", w=0.12), blush=0.25),
            belly=1.0, expression=dict(MTH_Fun=0.35, EYE_Joy=0.2),
        ),
        "brier": _ra_boy(
            "Brier", 172, (0.18, 0.22, 0.15), "spiky",
            C._face(eyes=dict(iris=(0.30, 0.36, 0.22), w=0.29, h=0.34, shape="sharp"),
                    brows=dict(color=(0.12, 0.16, 0.10), angle=10.0, thick=0.036),
                    mouth=dict(kind="smirk", w=0.10)),
            expression=dict(BRW_Angry=0.3, MTH_Fun=0.2),
        ),
        "dimitri": _ra_boy(
            "Dimitri", 176, (0.10, 0.10, 0.12), "neat",
            C._face(eyes=dict(iris=(0.30, 0.24, 0.18), w=0.28, h=0.32, shape="sharp"),
                    brows=dict(color=(0.08, 0.08, 0.09), angle=6.0, thick=0.034),
                    mouth=dict(kind="flat", w=0.09)),
            expression=dict(BRW_Angry=0.2),
        ),
        "gerard": _slifer_boy(
            "Gerard", 173, (0.36, 0.26, 0.17), "messy",
            C._face(eyes=dict(iris=(0.38, 0.28, 0.18), w=0.28, h=0.32),
                    brows=dict(color=(0.24, 0.16, 0.10), angle=2.0, thick=0.034),
                    mouth=dict(kind="smile", w=0.10)),
            expression=dict(MTH_Fun=0.3),
        ),
        "topher": _obelisk_boy(
            "Topher", 170, (0.78, 0.62, 0.34), "neat",
            C._face(eyes=dict(iris=(0.42, 0.34, 0.22), w=0.28, h=0.32, shape="sharp"),
                    brows=dict(color=(0.52, 0.40, 0.22), angle=8.0, thick=0.03),
                    mouth=dict(kind="smirk", w=0.10)),
            expression=dict(BRW_Angry=0.2, MTH_Fun=0.25),
        ),
        "torrey": _obelisk_boy(
            "Torrey", 174, (0.14, 0.12, 0.16), "long_straight",
            C._face(eyes=dict(iris=(0.28, 0.22, 0.34), w=0.27, h=0.32, shape="sharp"),
                    brows=dict(color=(0.08, 0.06, 0.10), angle=6.0, thick=0.032),
                    mouth=dict(kind="flat", w=0.09)),
            hairdo=dict(source="vroid_b", long_only=True, drop=("HAIR_03", "HAIR_04", "HAIR_05", "HAIR_06"),
                        shape=C._shape(flow=dict(lift=0.0, up=0.1, length=1.4, front_lift=0.0,
                                                 front_length=1.05, crown_lift=0.0),
                                       volume=dict(top=2.1, back=1.9, side=1.3, loft=0.014),
                                       envelope=dict(side=1.4, jaw=1.2))),
            expression=dict(BRW_Angry=0.25, EYE_Angry=0.2),
        ),
        "conklin": _obelisk_boy(
            "Conklin", 171, (0.32, 0.20, 0.13), "spiky",
            C._face(eyes=dict(iris=(0.36, 0.26, 0.18), w=0.29, h=0.34),
                    brows=dict(color=(0.18, 0.12, 0.08), angle=6.0, thick=0.034),
                    mouth=dict(kind="smirk", w=0.10)),
            expression=dict(BRW_Angry=0.2),
        ),
        "damon": _obelisk_boy(
            "Damon", 181, (0.16, 0.16, 0.20), "messy",
            C._face(eyes=dict(iris=(0.30, 0.28, 0.26), w=0.28, h=0.32, shape="sharp"),
                    brows=dict(color=(0.10, 0.10, 0.12), angle=8.0, thick=0.038),
                    mouth=dict(kind="flat", w=0.10)),
            expression=dict(BRW_Angry=0.35, EYE_Angry=0.2),
        ),
        "blair": _blair(),
        "shadow_duelist": _entry(
            "Shadow Duelist", "white", 184, "vroid_c",
            dict(open=0.45, coat="long"),
            C._coat((0.05, 0.05, 0.07), (0.30, 0.24, 0.36), (0.12, 0.10, 0.14), (0.05, 0.05, 0.08),
                    open_=0.45, collar=0.08,
                    coat=dict(shield=dict(color=(0.18, 0.14, 0.22), border=(0.42, 0.36, 0.50), w=0.12))),
            dict(style="long_straight", color=(0.08, 0.07, 0.10), color2=(0.04, 0.04, 0.06)),
            C._face(eyes=dict(iris=(0.62, 0.20, 0.24), w=0.28, h=0.30, shape="sharp"),
                    brows=dict(color=(0.04, 0.04, 0.06), angle=16.0, thick=0.04),
                    mouth=dict(kind="flat", w=0.10)),
            hairdo=dict(source="vroid_b", long_only=True, drop=("HAIR_03", "HAIR_04", "HAIR_05", "HAIR_06"),
                        shape=C._shape(flow=dict(lift=0.0, up=0.05, length=1.5, front_lift=0.0,
                                                 front_length=1.1, crown_lift=0.0),
                                       volume=dict(top=2.0, back=1.8, side=1.3, loft=0.012),
                                       envelope=dict(side=1.4, jaw=1.2))),
            face_shape=dict(chin=0.018, jaw=-0.09),
            expression=dict(BRW_Angry=0.6, EYE_Angry=0.4, MTH_Angry=0.2),
            colors=_colors((0.05, 0.05, 0.07), (0.30, 0.24, 0.36), (0.12, 0.10, 0.14),
                           pants=(0.05, 0.05, 0.08), shoes=(0.06, 0.06, 0.08)),
            outline=0.0030,
        ),
    }
    return entries
