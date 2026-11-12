"""
The cast: who stands where on the island, and which original design plays each part.

Every slot keeps its game data (HUD name, dorm, height, dialogue, spawn marker); how the character looks
comes from an atelier design (Tools/dai/anime/atelier/designs.py) - the project's own models, built from
scratch. No third-party base model is involved.

  name       display name (HUD dialogue title)
  dorm       slifer | ra | obelisk | white | teacher   (HUD accent, NPC behaviour)
  height     standing height in cm without hair (the runtime uniform scale is derived from it, see scale_of;
             the skeleton is shared, so heights differ by scale only)
  design     key of atelier.designs (face, hair, outfit)
  female     body table of the design (generic-look selection, voices)
  tint       generic students: which materials Unreal recolours at runtime ("jacket" by dorm, "hair")
  lines      what they say when you talk to them (original lines)
  spawn      which layout.json NPC marker they take over: {"group", "dorm", "nth", "near", "max_wander"}

An artist-made model can replace any design: register it under "anime_models" and name the slot or design
it replaces under "cast_models" in Tools/thirdparty/registry/anime.json (see Docs/CHARACTER_MODELS.md).

All colours are sRGB 0..1.
"""

SKIN = (1.0, 0.87, 0.76)
WHITE = (0.96, 0.96, 0.95)
SLIFER_RED = (0.78, 0.20, 0.21)
SLIFER_DARK = (0.50, 0.08, 0.10)
RA_DARK = (0.56, 0.49, 0.22)
RA_YELLOW = (0.95, 0.85, 0.46)
OBELISK_BLUE = (0.10, 0.24, 0.66)
OBELISK_TRIM = (0.33, 0.37, 0.75)
TINT_BASE = (0.92, 0.92, 0.92)      # white-ish base under a runtime Tint

DORM_COLOR = {"slifer": SLIFER_RED, "ra": RA_YELLOW, "obelisk": OBELISK_BLUE, "white": WHITE}

CAST = {
    "jaden": {'name': 'Jaden Yuki',
     'dorm': 'slifer',
     'height': 168,
     'design': 'Kaien',
     'lines': ["Hey! You look like you'd be fun to duel. Get your deck ready!",
               'Classes are fine and all, but the real lessons happen on the duel field.',
               "Professor Banner's curry is the best thing about the Slifer dorm. Don't tell the Obelisks.",
               'Win or lose, as long as the duel was fun, it was a good one!'],
     'spawn': {'group': 'slifer', 'dorm': 'slifer', 'nth': 0, 'near': (-107800.0, 25550.0)}},
    "syrus": {'name': 'Syrus Truesdale',
     'dorm': 'slifer',
     'height': 153,
     'design': 'Pim',
     'lines': ["J-Jaden says I should believe in my deck more... I'm trying!",
               'My big brother is the Kaiser. No pressure or anything.',
               'Vehicroids are the best. Want to see my favourite card?',
               "Is it true there's a ghost in the abandoned dorm? I'm not going there alone!"],
     'spawn': {'group': 'slifer', 'dorm': 'slifer', 'nth': 1, 'near': (-105550.0, 25800.0)}},
    "chumley": {'name': 'Chumley Huffington',
     'dorm': 'slifer',
     'height': 171,
     'design': 'Bram',
     'lines': ['Ugh... is it lunchtime yet? I could go for a grilled cheese sandwich.',
               'Koalas are the most underrated monsters, you know.',
               "Repeating a year isn't so bad. You get to know all the good nap spots.",
               "My dad makes hot sauce. I'm going to make it big with my cards instead!"],
     'spawn': {'group': 'slifer', 'dorm': 'slifer', 'nth': 0, 'near': (-107400.0, 27650.0)}},
    "bastion": {'name': 'Bastion Misawa',
     'dorm': 'ra',
     'height': 176,
     'design': 'Leoric',
     'lines': ["I've built six decks, one for every attribute. Statistically, one of them should beat you.",
               'My dorm room walls are covered in equations. The cleaning staff have given up.',
               'Ra Yellow is the perfect middle ground: the cafeteria is excellent and nobody expects too much.',
               'Every duel is just a problem waiting for the right formula.'],
     'spawn': {'group': 'ra', 'dorm': 'ra', 'nth': 5, 'near': (-67331.4, 64789.3)}},
    "chazz": {'name': 'Chazz Princeton',
     'dorm': 'obelisk',
     'height': 174,
     'design': 'Rook',
     'lines': ["The name's Chazz Princeton. Remember it - you'll be hearing it a lot.",
               "You want an autograph? Get in line. Behind my brothers' business cards.",
               'Ojama Yellow, get back in the deck before somebody sees you!',
               "I didn't lose. I'm just letting everybody else catch up."],
     'spawn': {'group': 'obelisk_boys', 'dorm': 'obelisk', 'nth': 7, 'near': (-58351.7, -51008.5)}},
    "zane": {'name': 'Zane Truesdale',
     'dorm': 'obelisk',
     'height': 183,
     'design': 'Aurel',
     'lines': ['Respect your opponent. Duel them with everything you have.',
               'The sea is calm tonight. A good place to think about the next duel.',
               "My brother has more potential than he knows. Don't tell him I said that.",
               'A victory without respect means nothing.'],
     'spawn': {'group': 'lighthouse', 'dorm': 'obelisk', 'nth': 0, 'near': (30150.0, 124650.0)}},
    "alexis": {'name': 'Alexis Rhodes',
     'dorm': 'obelisk',
     'height': 162,
     'design': 'Selene',
     'female': True,
     'lines': ["The Obelisk Blue girls' dorm is off limits to boys. Rules are rules.",
               'Cyber Blader and I could use a real challenge. Are you up for it?',
               "My brother disappeared from the abandoned dorm... I won't give up looking.",
               "Don't let anyone tell you which dorm defines you. Your duels do that."],
     'spawn': {'group': 'obelisk_girls', 'dorm': 'obelisk', 'nth': 0, 'near': (-23982.5, -88844.0)}},
    "jasmine": {'name': 'Jasmine',
     'dorm': 'obelisk',
     'height': 160,
     'design': 'Wren',
     'female': True,
     'lines': ['Alexis is the Queen of Obelisk Blue. Everybody knows that.',
               "Did you see that Slifer slacker sneak past the girls' dorm again?"],
     'spawn': {'group': 'obelisk_girls', 'dorm': 'obelisk', 'nth': 6, 'near': (-21245.9, -89388.5)}},
    "mindy": {'name': 'Mindy',
     'dorm': 'obelisk',
     'height': 158,
     'design': 'Odile',
     'female': True,
     'lines': ['Ooh, are you new? Which dorm are you in? Wait, let me guess...',
               'The lake by our dorm is so pretty at sunset!'],
     'spawn': {'group': 'obelisk_girls', 'dorm': 'obelisk', 'nth': 7, 'near': (-18402.8, -86849.0)}},
    "crowler": {'name': 'Dr. Vellian Crowler',
     'dorm': 'teacher',
     'height': 186,
     'design': 'Valmont',
     'lines': ["Slifer Red? Hmph. Try not to drag the academy's reputation down, dropout boy.",
               "As Duel Academy's top professor, I demand punctuality, precision and elegance!",
               'My Ancient Gear Golem has humbled far greater duelists than you.',
               'The practical exam is on the arena field. Do try to pass it.'],
     'spawn': {'group': 'academy', 'dorm': 'obelisk', 'nth': 0, 'max_wander': 60.0, 'near': (-1060.0, -16500.0)}},

}

# ---------------------------------------------------------------------- generic students
# One mesh per look; Unreal tints the jacket by dorm and the hair per NPC ("tint").
STUDENTS = {
    "student_m1": dict(design="StudentM1"),
    "student_f1": dict(design="StudentF1", female=True),
    "student_f2": dict(design="StudentF2", female=True),
}


def student_entry(key):
    """Expand a STUDENTS look into a full cast entry (tintable jacket / hair come from the design)."""
    from .atelier import designs
    s = STUDENTS[key]
    female = bool(s.get("female"))
    return dict(name="Student", dorm="any", height=GENERIC_HEIGHT[female], design=s["design"], female=female,
                tint=list(designs.DESIGNS[s["design"]].get("tint", ())), lines=[])


# The playable student: the protagonist's own bespoke model (hero.py: hand-placed hair, painted eyes, cut-away
# academy jacket) with a dorm-tinted jacket (J switches dorms in game). Without the VRoid base installed it
# falls back to the generic student design. The generic male students keep student_m1.
PLAYER = "hero"
PLAYER_FEMALE = "heroine"            # the player's model when the profile's gender is female (DAStudentCharacter)
HERO = {
    "hero": dict(name="Student", dorm="slifer", height=172, design="StudentM1", female=False, tint=["jacket"],
                 lines=[]),
    "heroine": dict(name="Student", dorm="slifer", height=163, design="StudentF1", female=True, tint=["jacket"],
                    lines=[]),
}

# Crown height (m, without hair) of the atelier bodies in their rest pose: turns the cast's heights into the
# runtime scale, so 168 cm means 168 cm on the island (doors, stairs and the 1.5 m/s walk are human scale).
# Must match atelier.build.height_of (boys / girls: the girls' head is a little larger).
BODY_HEIGHT = {False: 1.824, True: 1.844}
GENERIC_HEIGHT = {False: 170, True: 160}   # generic students (NPCs vary +-5 % round this)


def is_female(entry):
    return bool(entry.get("female"))


def scale_of(entry):
    """Runtime uniform scale of a cast entry: its height over the body's own height. An artist model that
    replaces the design reports its own measured height ("base_height", metres)."""
    if "height" not in entry:
        return float(entry.get("scale", 1.0))
    return round(entry["height"] / 100.0 / float(entry.get("base_height", BODY_HEIGHT[is_female(entry)])), 3)


def all_entries():
    """{cast id: full entry} for everything the pipeline builds (with the derived "scale")."""
    from . import looks
    out = {k: dict(v) for k, v in CAST.items()}
    for k in STUDENTS:
        out[k] = student_entry(k)
    for k, v in HERO.items():
        out[k] = dict(v)
    out = {k: looks.apply(k, e) for k, e in out.items()}      # VRoid-based look when the base is installed
    for e in out.values():
        e["scale"] = scale_of(e)
    return out


def generic_for(female):
    return [k for k, s in STUDENTS.items() if bool(s.get("female")) == female]


def _generic_scale(n):
    """Runtime scale of a generic marker: its look's height with a stable ±5 % size variation."""
    import zlib
    h = zlib.crc32(("%.0f,%.0f" % (n["loc"][0], n["loc"][1])).encode())
    from . import looks
    return round(scale_of(looks.apply(n["cast"], student_entry(n["cast"]))) * (0.95 + (h % 11) * 0.01), 3)


def assign_npcs(npcs):
    """Annotate layout.json npc entries with a cast id (named cast take their markers over, everybody else
    gets a deterministic generic look). Female students are Obelisk Blue (as in the show).

    Generic markers also receive a unique identity from ``roster.py`` (name, dialogue, hair colour), so
    the island's ambient students are characters rather than three repeated "Student" placeholders."""
    import zlib
    from . import roster
    used = set()
    entries = all_entries()
    for cid, c in CAST.items():
        c = entries[cid]
        sp = c.get("spawn")
        if not sp:
            continue
        cands = [n for n in npcs if n.get("group") == sp["group"] and n.get("dorm") == sp["dorm"] and id(n) not in used
                 and (sp.get("max_wander") is None or n.get("wander", 0.0) <= sp["max_wander"])]
        if not cands:
            continue
        if sp.get("near"):
            # anchored: the student marker closest to the character's spot (stable when rooms gain students)
            ax, ay = sp["near"]
            pick = min(cands, key=lambda n: (n["loc"][0] - ax) ** 2 + (n["loc"][1] - ay) ** 2)
        elif sp["nth"] < len(cands):
            pick = cands[sp["nth"]]
        else:
            continue
        pick["cast"] = cid
        pick["name"] = c["name"]
        pick["lines"] = list(c["lines"])
        pick["scale"] = scale_of(c)
        pick["tint"] = False
        used.add(id(pick))
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
        n["scale"] = _generic_scale(n)
        n["tint"] = True
    # Give every generic marker a unique identity (name, lines, hair colour).
    roster.assign_uniques(npcs)
    # The roster may switch a staff marker's base mesh to a female look; keep the
    # runtime scale consistent with the final cast id.
    for n in npcs:
        if n.get("tint", True):
            n["scale"] = _generic_scale(n)
    return npcs
