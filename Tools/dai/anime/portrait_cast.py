"""Portrait-only cast slots for named speakers who are not in the overworld cast.

The dialogue data has more named speakers than the island places as 3D characters. Rather than leave
their dialogue frames empty, each one is played by an original atelier design
(Tools/dai/anime/atelier/designs.py, EXTRAS) and rendered through the same cel-shaded pipeline as the
overworld cast. These slots are used only by Tools/render_portraits.py; they are deliberately not merged
into cast.CAST, so they do not change the world build, schedules or layout.
"""

from . import cast as C

# slot id: (display name, dorm, height cm, design)
SLOTS = {
    "banner": ("Lyman Banner", "teacher", 184, "Corvin"),
    "sheppard": ("Chancellor Sheppard", "teacher", 188, "Hale"),
    "mimicry": ("Professor Mimicry", "teacher", 177, "Tavi"),
    "dorothy": ("Miss Dorothy", "teacher", 165, "Marta"),
    "fontaine": ("Fonda Fontaine", "teacher", 167, "Lysa"),
    "sartyr": ("Sartyr", "ra", 176, "Sable"),
    "beauregard": ("Beauregard", "ra", 178, "Benno"),
    "brier": ("Brier", "ra", 172, "Thorne"),
    "dimitri": ("Dimitri", "ra", 176, "Dmitar"),
    "gerard": ("Gerard", "slifer", 173, "Garrick"),
    "topher": ("Topher", "obelisk", 170, "Tobias"),
    "torrey": ("Torrey", "obelisk", 174, "Torin"),
    "conklin": ("Conklin", "obelisk", 171, "Conall"),
    "damon": ("Damon", "obelisk", 181, "Dane"),
    "blair": ("Blair Flannigan", "slifer", 154, "Mirel"),
    "shadow_duelist": ("Shadow Duelist", "white", 184, "Nix"),
    "unknown_student": ("Student", "slifer", 170, "Shade"),
}


def _entry(name, dorm, height, design):
    from .atelier import designs
    female = bool(designs.all_designs()[design].get("female"))
    entry = dict(name=name, dorm=dorm, height=height, design=design, female=female, lines=[])
    entry["scale"] = C.scale_of(entry)
    return entry


def all_entries():
    """{id: entry} of portrait-only cast members (plus the generic student busts)."""
    from . import looks
    entries = {cid: _entry(*spec) for cid, spec in SLOTS.items()}
    for key in C.STUDENTS:
        entries[key] = C.student_entry(key)
    entries = {cid: looks.apply(cid, e) for cid, e in entries.items()}
    for cid, e in entries.items():
        if cid in C.STUDENTS and e.get("model"):         # a readable hair colour for the generic busts
            e["tint"] = []
            e["hair"] = dict(e["hair"], color=(0.30, 0.20, 0.14))
        e["scale"] = C.scale_of(e)
    return entries
