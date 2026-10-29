"""
The cast: named Yu-Gi-Oh! GX characters (fan-made, original geometry) and generic students.

Each entry names the existing anime base model it is built from ("model": a key of the "anime_models"
registry, see models.py), the Duel Academy uniform tailored onto it ("outfit"), how its hair is restyled
("hairdo") and the hair / eye / shoe colours, after the characters' official designs. Without a model file the
procedural fallback (head.py / hair.py / body.py / face.py) builds the character instead:

  name       display name (HUD dialogue title)
  dorm       slifer | ra | obelisk | white | teacher   (HUD accent, NPC behaviour)
  scale      uniform runtime scale (the skeleton is shared; Syrus is small, Zane tall)
  body       {"female", "belly", "coat" (None | "long" | "tails"), "skirt", "boots", "open" (jacket V depth 0..1)}
  colors     sRGB colours of the outfit parts (jacket, trim, inner, pants, shoes, skirt, socks, coat ...)
  hair       {"style": hair.STYLES key, "color", "color2" (second tone), ...style params}
  face       face.py spec (eyes / brows / mouth / blush)
  extras     accessories: "glasses", "ruff", "bow"
  outfit     the uniform tailored onto a base model's body (outfit.py: jacket / shirt / pants / skirt / boots)
  hairdo     restyle of the base model's hair (hairdo.py: spike, source + long_only, gradient, glasses,
             ruff)
  tint       generic students: which materials Unreal recolours at runtime ("jacket" by dorm, "hair")
  lines      what they say when you talk to them (original lines)
  spawn      which layout.json NPC marker they take over: {"group", "dorm", "nth", "max_wander"}

All colours are sRGB 0..1.
"""

SKIN = (1.0, 0.87, 0.76)
WHITE = (0.96, 0.96, 0.95)
SLIFER_RED = (0.78, 0.07, 0.06)
RA_YELLOW = (0.98, 0.80, 0.14)
OBELISK_BLUE = (0.10, 0.24, 0.66)
TINT_BASE = (0.92, 0.92, 0.92)      # white-ish base under a runtime Tint

DORM_COLOR = {"slifer": SLIFER_RED, "ra": RA_YELLOW, "obelisk": OBELISK_BLUE, "white": WHITE}

_EYES_BOY = dict(w=0.31, h=0.38, spacing=0.40, z=-0.16, shape="round", lash=0.15)
_EYES_GIRL = dict(w=0.33, h=0.44, spacing=0.40, z=-0.16, shape="round", lash=0.17, female=True, iris_h=1.0)


def _face(eyes=None, brows=None, mouth=None, **kw):
    out = dict(eyes=dict(_EYES_BOY, **(eyes or {})), brows=dict(brows or {}), mouth=dict(mouth or {}))
    out.update(kw)
    return out


UNIFORM_PANTS = (0.90, 0.90, 0.88)    # white uniform trousers (Jaden until season 4)
BLACK_SHIRT = (0.08, 0.08, 0.09)


def _academy(jacket, cuff, shirt, pants, open_=0.15, trim=WHITE, **kw):
    """Slifer Red / Ra Yellow uniform after the dorm designs (Yugipedia / Yu-Gi-Oh! Wiki): a jacket reaching the
    waist with white trimmings, a white band round the shoulders, a band in the dorm colour at the cuffs and a
    stand-up collar; worn over a shirt, with trousers."""
    j = dict(color=jacket, trim=trim, trims=("front", "hem", "cuff", "collar"), open=open_, length="waist",
             drop=0.06, collar=0.05, cuff_color=cuff, shoulder=dict(color=trim), trim_w=0.012)
    j.update(kw.pop("coat", {}))
    out = dict(jacket=j, shirt=dict(color=shirt, sleeves="short", length="waist"), pants=dict(color=pants, width=kw.pop("width", 0.053)))
    out.update(kw)
    return out


def _coat(jacket, trim, shirt, pants, open_=0.6, **kw):
    """Long coat: Obelisk Blue boys wear blue long-tailed jackets with white trimmings, longer than the other
    dorms' (Yugipedia); also Chazz's black coat and Crowler's frock coat."""
    j = dict(color=jacket, trim=trim, trims=("front", "hem", "cuff", "collar"), open=open_, length="knee",
             collar=kw.pop("collar", 0.06), cuff_color=kw.pop("cuff", trim), trim_w=0.014)
    j.update(kw.pop("coat", {}))
    out = dict(jacket=j, shirt=dict(color=shirt, sleeves="short"), pants=dict(color=pants, width=kw.pop("width", 0.053)))
    out.update(kw)
    return out


def _boy(jacket, trim, shirt, pants, open_=0.2, length="hip", trims=("front", "cuff", "collar"), **kw):
    """Plain blazer over a shirt, with trousers (generic students: tinted per dorm in Unreal)."""
    j = dict(color=jacket, trim=trim, trims=trims, open=open_, length=length, collar=kw.pop("collar", 0.05))
    j.update(kw.pop("coat", {}))
    out = dict(jacket=j, shirt=dict(color=shirt, sleeves="short"), pants=dict(color=pants, width=kw.pop("width", 0.053)))
    out.update(kw)
    return out


def _girl(jacket=None, trim=None, skirt=None, boots=None, **kw):
    """Obelisk Blue girls' uniform (Yugipedia / Yu-Gi-Oh! Wiki): sleeveless white jacket with blue markings at
    the collar and chest, blue miniskirt with a light blue belt, royal blue boots."""
    jacket, trim = jacket or WHITE, trim or OBELISK_BLUE
    j = dict(color=jacket, trim=trim, trims=("front", "hem", "cuff", "collar"), open=0.2, length="waist",
             sleeves="none", collar=0.03, trim_w=0.014)
    j.update(kw.pop("jacket", {}))
    out = dict(jacket=j, shirt=dict(color=OBELISK_BLUE, sleeves="none", length="waist"),
               skirt=dict(color=skirt or OBELISK_BLUE, length=0.15, pleats=18, belt=(0.55, 0.74, 0.95)),
               boots=dict(color=boots or (0.10, 0.22, 0.62), top=0.86))
    out.update(kw)
    return out


CAST = {
    # ------------------------------------------------------------------ Slifer Red
    "jaden": dict(
        name="Jaden Yuki", dorm="slifer", scale=1.0, model="vroid_c",
        body=dict(open=1.0),
        outfit=dict(_academy(SLIFER_RED, (0.60, 0.04, 0.04), BLACK_SHIRT, UNIFORM_PANTS, open_=1.0)),
        hairdo=dict(spike=dict(lift=0.1, up=-0.5, length=1.25, back_only=True), gradient=(0.38, 0.2)),
        colors=dict(jacket=SLIFER_RED, trim=(0.10, 0.10, 0.12), inner=(0.08, 0.08, 0.09),
                    pants=UNIFORM_PANTS, shoes=(0.80, 0.10, 0.08), sole=(0.95, 0.93, 0.88)),
        hair=dict(style="jaden", color=(0.30, 0.16, 0.07), color2=(0.68, 0.38, 0.15)),
        face=_face(eyes=dict(iris=(0.55, 0.30, 0.08), w=0.31, h=0.42),
                   brows=dict(color=(0.30, 0.14, 0.05), angle=-4.0), mouth=dict(kind="grin", w=0.12)),
        lines=["Hey! You look like you'd be fun to duel. Get your deck ready!",
               "Classes are fine and all, but the real lessons happen on the duel field.",
               "Professor Banner's curry is the best thing about the Slifer dorm. Don't tell the Obelisks.",
               "Win or lose, as long as the duel was fun, it was a good one!"],
        spawn=dict(group="slifer", dorm="slifer", nth=0),
    ),
    "syrus": dict(
        name="Syrus Truesdale", dorm="slifer", scale=0.84, model="vroid_c",
        body=dict(open=0.75),
        outfit=dict(_academy(SLIFER_RED, (0.60, 0.04, 0.04), (0.98, 0.84, 0.22), UNIFORM_PANTS, open_=0.25)),
        hairdo=dict(glasses=(0.18, 0.18, 0.22)),
        colors=dict(jacket=SLIFER_RED, trim=WHITE, inner=(0.30, 0.55, 0.85),
                    pants=(0.70, 0.66, 0.55), shoes=(0.20, 0.30, 0.55), sole=WHITE),
        hair=dict(style="syrus", color=(0.55, 0.82, 0.92), color2=(0.38, 0.66, 0.82)),
        face=_face(eyes=dict(iris=(0.46, 0.49, 0.54), w=0.32, h=0.44, look=0.0),
                   brows=dict(color=(0.35, 0.55, 0.70), angle=-12.0, lift=0.12), mouth=dict(kind="open", w=0.10)),
        extras=["glasses"],
        lines=["J-Jaden says I should believe in my deck more... I'm trying!",
               "My big brother is the Kaiser. No pressure or anything.",
               "Vehicroids are the best. Want to see my favourite card?",
               "Is it true there's a ghost in the abandoned dorm? I'm not going there alone!"],
        spawn=dict(group="slifer", dorm="slifer", nth=1),
    ),
    "chumley": dict(
        name="Chumley Huffington", dorm="slifer", scale=1.02, model="vroid_c",
        body=dict(open=0.9, belly=1.0),
        outfit=dict(_academy(WHITE, SLIFER_RED, (0.94, 0.93, 0.88), (0.30, 0.30, 0.34), open_=0.85,
                              trim=SLIFER_RED, belly=1.0)),
        hairdo=dict(spike=dict(lift=0.2, up=0.0, length=1.15, front_lift=0.05, front_length=1.0)),
        colors=dict(jacket=SLIFER_RED, trim=WHITE, inner=(0.92, 0.90, 0.84),
                    pants=(0.30, 0.30, 0.34), shoes=(0.35, 0.25, 0.18), sole=(0.8, 0.78, 0.7)),
        hair=dict(style="chumley", color=(0.09, 0.08, 0.10)),
        face=_face(eyes=dict(iris=(0.36, 0.22, 0.12), w=0.24, h=0.26, shape="sleepy", spacing=0.36),
                   brows=dict(color=(0.25, 0.15, 0.10), thick=0.045), mouth=dict(kind="smile", w=0.14), blush=0.35),
        lines=["Ugh... is it lunchtime yet? I could go for a grilled cheese sandwich.",
               "Koalas are the most underrated monsters, you know.",
               "Repeating a year isn't so bad. You get to know all the good nap spots.",
               "My dad makes hot sauce. I'm going to make it big with my cards instead!"],
        spawn=dict(group="slifer", dorm="slifer", nth=2),
    ),
    # ------------------------------------------------------------------ Ra Yellow
    "bastion": dict(
        name="Bastion Misawa", dorm="ra", scale=1.04, model="vroid_c",
        body=dict(open=0.35),
        outfit=dict(_academy(RA_YELLOW, RA_YELLOW, (0.95, 0.95, 0.95), (0.22, 0.24, 0.30), open_=0.1,
                              coat=dict(buttons=dict(color=WHITE, n=1)))),
        colors=dict(jacket=RA_YELLOW, trim=WHITE, inner=(0.95, 0.95, 0.95),
                    pants=(0.22, 0.24, 0.30), shoes=(0.20, 0.16, 0.14), sole=(0.25, 0.22, 0.2)),
        hair=dict(style="bastion", color=(0.10, 0.09, 0.12)),
        face=_face(eyes=dict(iris=(0.30, 0.30, 0.34), w=0.29, h=0.36),
                   brows=dict(color=(0.08, 0.07, 0.09), angle=2.0), mouth=dict(kind="smile", w=0.10)),
        lines=["I've built six decks, one for every attribute. Statistically, one of them should beat you.",
               "My dorm room walls are covered in equations. The cleaning staff have given up.",
               "Ra Yellow is the perfect middle ground: the cafeteria is excellent and nobody expects too much.",
               "Every duel is just a problem waiting for the right formula."],
        spawn=dict(group="ra", dorm="ra", nth=0),
    ),
    # ------------------------------------------------------------------ Obelisk Blue
    "chazz": dict(
        name="Chazz Princeton", dorm="obelisk", scale=1.03, model="vroid_c",
        body=dict(open=0.6, coat="long"),
        outfit=dict(_coat((0.07, 0.07, 0.09), (0.40, 0.40, 0.44), (0.38, 0.20, 0.50), (0.10, 0.12, 0.26),
                           open_=0.7, collar=0.07)),
        hairdo=dict(spike=dict(lift=0.1, up=-0.3, length=1.3, front_lift=0.05, front_length=1.15)),
        colors=dict(jacket=(0.07, 0.07, 0.09), trim=(0.30, 0.30, 0.34), inner=(0.10, 0.10, 0.12),
                    pants=(0.08, 0.08, 0.10), shoes=(0.36, 0.22, 0.12), sole=(0.2, 0.2, 0.22)),
        hair=dict(style="chazz", color=(0.07, 0.07, 0.10), color2=(0.16, 0.16, 0.22)),
        face=_face(eyes=dict(iris=(0.22, 0.22, 0.26), w=0.29, h=0.30, shape="sharp", tilt=0.12),
                   brows=dict(color=(0.05, 0.05, 0.07), angle=16.0, thick=0.04), mouth=dict(kind="smirk", w=0.10)),
        lines=["The name's Chazz Princeton. Remember it - you'll be hearing it a lot.",
               "You want an autograph? Get in line. Behind my brothers' business cards.",
               "Ojama Yellow, get back in the deck before somebody sees you!",
               "I didn't lose. I'm just letting everybody else catch up."],
        spawn=dict(group="obelisk_boys", dorm="obelisk", nth=0),
    ),
    "zane": dict(
        name="Zane Truesdale", dorm="obelisk", scale=1.1, model="vroid_c",
        body=dict(open=0.3, coat="long"),
        outfit=dict(_coat(OBELISK_BLUE, WHITE, (0.14, 0.16, 0.24), (0.12, 0.13, 0.20), open_=0.6, collar=0.08,
                          coat=dict(tails=0.25, loose=0.012))),
        hairdo=dict(spike=dict(lift=0.0, up=0.0, length=1.3, front_lift=0.0, front_length=1.1)),
        colors=dict(jacket=WHITE, trim=OBELISK_BLUE, inner=(0.16, 0.18, 0.24),
                    pants=(0.12, 0.13, 0.18), shoes=(0.10, 0.10, 0.12), sole=(0.3, 0.3, 0.32)),
        hair=dict(style="zane", color=(0.16, 0.26, 0.52), color2=(0.12, 0.20, 0.42)),
        face=_face(eyes=dict(iris=(0.22, 0.38, 0.72), w=0.28, h=0.28, shape="sharp", tilt=0.06),
                   brows=dict(color=(0.12, 0.22, 0.25), angle=10.0), mouth=dict(kind="flat", w=0.08)),
        lines=["Respect your opponent. Duel them with everything you have.",
               "The sea is calm tonight. A good place to think about the next duel.",
               "My brother has more potential than he knows. Don't tell him I said that.",
               "A victory without respect means nothing."],
        spawn=dict(group="lighthouse", dorm="obelisk", nth=0),
    ),
    "alexis": dict(
        name="Alexis Rhodes", dorm="obelisk", scale=1.0, model="vroid_a",
        body=dict(female=True, open=0.0, skirt=True, boots=True),
        outfit=_girl(),
        hairdo=dict(source="vroid_b", long_only=True, drop=("HAIR_03", "HAIR_04", "HAIR_05", "HAIR_06")),
        colors=dict(jacket=WHITE, trim=OBELISK_BLUE, inner=OBELISK_BLUE, skirt=OBELISK_BLUE,
                    pants=SKIN, shoes=(0.10, 0.22, 0.62), boots=(0.10, 0.22, 0.62), sole=(0.08, 0.1, 0.25)),
        hair=dict(style="alexis", color=(0.80, 0.62, 0.32), color2=(0.85, 0.64, 0.30)),
        face=_face(eyes=dict(_EYES_GIRL, iris=(0.62, 0.42, 0.18)),
                   brows=dict(color=(0.70, 0.50, 0.25), angle=4.0, thick=0.026), mouth=dict(kind="smile", w=0.08),
                   blush=0.25),
        lines=["The Obelisk Blue girls' dorm is off limits to boys. Rules are rules.",
               "Cyber Blader and I could use a real challenge. Are you up for it?",
               "My brother disappeared from the abandoned dorm... I won't give up looking.",
               "Don't let anyone tell you which dorm defines you. Your duels do that."],
        spawn=dict(group="obelisk_girls", dorm="obelisk", nth=0),
    ),
    "jasmine": dict(
        name="Jasmine", dorm="obelisk", scale=0.98, model="vroid_a",
        body=dict(female=True, open=0.0, skirt=True, boots=True),
        outfit=_girl(),
        hairdo=dict(),
        colors=dict(jacket=WHITE, trim=OBELISK_BLUE, inner=OBELISK_BLUE, skirt=OBELISK_BLUE,
                    pants=SKIN, shoes=(0.10, 0.22, 0.62), boots=(0.10, 0.22, 0.62), sole=(0.08, 0.1, 0.25)),
        hair=dict(style="long_wavy", color=(0.40, 0.24, 0.13)),
        face=_face(eyes=dict(_EYES_GIRL, iris=(0.45, 0.47, 0.52)), brows=dict(color=(0.35, 0.10, 0.10)),
                   mouth=dict(kind="smile", w=0.08), blush=0.3),
        lines=["Alexis is the Queen of Obelisk Blue. Everybody knows that.",
               "Did you see that Slifer slacker sneak past the girls' dorm again?"],
        spawn=dict(group="obelisk_girls", dorm="obelisk", nth=1),
    ),
    "mindy": dict(
        name="Mindy", dorm="obelisk", scale=0.97, model="vroid_a",
        body=dict(female=True, open=0.0, skirt=True, boots=True),
        outfit=_girl(),
        hairdo=dict(source="vroid_b", long_only=True, trim="shoulder", drop=("HAIR_03", "HAIR_04", "HAIR_05", "HAIR_06")),
        colors=dict(jacket=WHITE, trim=OBELISK_BLUE, inner=OBELISK_BLUE, skirt=OBELISK_BLUE,
                    pants=SKIN, shoes=(0.10, 0.22, 0.62), boots=(0.10, 0.22, 0.62), sole=(0.08, 0.1, 0.25)),
        hair=dict(style="long_straight", color=(0.06, 0.06, 0.08)),
        face=_face(eyes=dict(_EYES_GIRL, iris=(0.38, 0.24, 0.14)), brows=dict(color=(0.05, 0.05, 0.07)),
                   mouth=dict(kind="open", w=0.08), blush=0.3),
        lines=["Ooh, are you new? Which dorm are you in? Wait, let me guess...",
               "The lake by our dorm is so pretty at sunset!"],
        spawn=dict(group="obelisk_girls", dorm="obelisk", nth=2),
    ),
    # ------------------------------------------------------------------ staff
    "crowler": dict(
        name="Dr. Vellian Crowler", dorm="teacher", scale=1.12, model="vroid_c",
        body=dict(open=0.2, coat="long"),
        outfit=dict(_coat((0.16, 0.30, 0.66), (0.92, 0.78, 0.30), WHITE, (0.16, 0.30, 0.66), open_=0.15, collar=0.0,
                             cuff=(0.96, 0.62, 0.78), width=0.05,
                             coat=dict(buttons=dict(color=(0.92, 0.78, 0.30), n=4),
                                       shoulder=dict(color=(0.96, 0.62, 0.78), w=0.04)))),
        hairdo=dict(source="vroid_b", long_only=True, drop=("HAIR_03", "HAIR_04", "HAIR_05", "HAIR_06"),
                    ponytail=dict(k=0.3, band=(0.06, 0.06, 0.07)), ruff=(0.96, 0.62, 0.78)),
        colors=dict(jacket=(0.16, 0.30, 0.66), trim=(0.92, 0.80, 0.30), inner=WHITE,
                    pants=(0.16, 0.30, 0.66), shoes=(0.10, 0.10, 0.12), sole=(0.3, 0.3, 0.3)),
        hair=dict(style="crowler", color=(0.92, 0.82, 0.52), color2=(0.80, 0.68, 0.38)),
        face=_face(eyes=dict(iris=(0.38, 0.30, 0.52), w=0.26, h=0.26, shape="sharp", spacing=0.35),
                   brows=dict(color=(0.75, 0.62, 0.35), angle=-6.0, arch=1.6),
                   mouth=dict(kind="lips", w=0.09, lip_color=(0.70, 0.18, 0.45)), face_extras=["eyeshadow", "nose"]),
        extras=["ruff"],
        lines=["Slifer Red? Hmph. Try not to drag the academy's reputation down, dropout boy.",
               "As Duel Academy's top professor, I demand punctuality, precision and elegance!",
               "My Ancient Gear Golem has humbled far greater duelists than you.",
               "The practical exam is on the arena field. Do try to pass it."],
        spawn=dict(group="academy", dorm="obelisk", nth=0, max_wander=60.0),
    ),
}

# ---------------------------------------------------------------------- generic students
# One mesh per look; Unreal tints the jacket by dorm and the hair per NPC ("tint").
STUDENTS = {
    "student_m1": dict(model="vroid_c", hair=dict(style="spiky"), face=_face(mouth=dict(kind="smile"))),
    "student_f1": dict(model="vroid_a", female=True, hair=dict(style="bob"),
                       face=_face(eyes=dict(_EYES_GIRL), mouth=dict(kind="open", w=0.07), blush=0.25)),
    "student_f2": dict(model="vroid_b", female=True, hair=dict(style="long_straight"),
                       face=_face(eyes=dict(_EYES_GIRL), mouth=dict(kind="smile", w=0.08), blush=0.25)),
}


def student_entry(key):
    """Expand a STUDENTS look into a full cast entry (tintable jacket / hair)."""
    s = STUDENTS[key]
    female = s.get("female", False)
    face = dict(s["face"])
    face["eyes"] = dict(face["eyes"], iris=(0.35, 0.25, 0.18))
    face.setdefault("brows", {})
    face["brows"] = dict(face["brows"], color=(0.22, 0.14, 0.10))
    if female:
        body = dict(female=True, open=0.0, skirt=True, boots=False)
        colors = dict(jacket=TINT_BASE, trim=WHITE, inner=OBELISK_BLUE, skirt=OBELISK_BLUE, pants=SKIN,
                      socks=(0.95, 0.95, 0.96), shoes=(0.30, 0.18, 0.12), sole=(0.2, 0.15, 0.1))
    else:
        body = dict(open=0.55)
        colors = dict(jacket=TINT_BASE, trim=WHITE, inner=(0.12, 0.12, 0.14), pants=(0.22, 0.24, 0.30),
                      shoes=(0.28, 0.16, 0.10), sole=(0.9, 0.88, 0.82))
    # boys wear their dorm's jacket (tinted in Unreal); the girls are all Obelisk Blue, as in the show
    if female:
        colors["jacket"] = WHITE
    if female:
        outfit = _girl()
    else:   # white jacket with dark trims: Unreal multiplies it with the dorm colour ("JacketTint")
        outfit = _boy(WHITE, (0.30, 0.30, 0.32), (0.10, 0.10, 0.12), (0.22, 0.24, 0.30), open_=0.55,
                      coat=dict(tint=True))
    return dict(name="Student", dorm="any", scale=1.0, body=body, colors=colors, model=s.get("model"), outfit=outfit,
                hair=dict(s["hair"], color=TINT_BASE), face=face, extras=s.get("extras", []),
                tint=["hair"] if female else ["jacket", "hair"], lines=[])


# The playable student: a generic look with a dorm-tinted jacket (J switches dorms in game)
PLAYER = "student_m1"


def all_entries():
    """{cast id: full entry} for everything the pipeline builds."""
    out = dict(CAST)
    for k in STUDENTS:
        out[k] = student_entry(k)
    return out


def generic_for(female):
    return [k for k, s in STUDENTS.items() if bool(s.get("female")) == female]


def assign_npcs(npcs):
    """Annotate layout.json npc entries with a cast id (named cast take their markers over, everybody else
    gets a deterministic generic look). Female students are Obelisk Blue (as in the show)."""
    import zlib
    used = set()
    for cid, c in CAST.items():
        sp = c.get("spawn")
        if not sp:
            continue
        nth = 0
        for n in npcs:
            if n.get("group") != sp["group"] or n.get("dorm") != sp["dorm"]:
                continue
            if sp.get("max_wander") is not None and n.get("wander", 0.0) > sp["max_wander"]:
                continue
            if id(n) in used:
                continue
            if nth == sp["nth"]:
                n["cast"] = cid
                n["name"] = c["name"]
                n["lines"] = list(c["lines"])
                n["scale"] = c["scale"]
                n["tint"] = False
                used.add(id(n))
                break
            nth += 1
    for n in npcs:
        if id(n) in used:
            continue
        h = zlib.crc32(("%.0f,%.0f" % (n["loc"][0], n["loc"][1])).encode())
        female = n.get("dorm") == "obelisk" and (n.get("group") == "obelisk_girls" or (
            n.get("group") != "obelisk_boys" and h % 100 < 40))
        looks = generic_for(female)
        n["cast"] = looks[(h // 100) % len(looks)]
        n.pop("name", None)
        n.pop("lines", None)
        n["scale"] = round(0.95 + (h % 11) * 0.01, 2)
        n["tint"] = True
    return npcs
