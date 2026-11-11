"""
Clump-hair style recipes (plain data: importable without Blender or numpy).

A recipe is a dict of hair.py sections (fringe / sides / back / spikes / tails / braids / buns / ahoge, see
hair.py's docstring). The atelier designs (designs.py) and the VRoid-based looks (../looks.py, built by
../clumphair.py) share them. Ring positions `to` / `at` are on the atelier head (0 crown, ~0.42 brows,
~0.50 eyes, ~0.58 cheeks, ~0.70 nape); lengths are metres on the atelier design head and are scaled to the
head the hair is combed on.

styled(name, **edits) derives a variant: per-section overrides are merged into the recipe's section
(fringe=dict(kind="swept")), None removes a section, other keys replace (ahoge=0.07, tails=[...]).
"""

HAIR = {

    # girls
    "long": dict(fringe=dict(kind="centre", n=6), sides=dict(to=0.66, free=0.16, n=2),
                 back=dict(to=0.72, free=0.46, n=11, taper=0.10)),
    "hime": dict(fringe=dict(kind="straight", to=0.415, n=7, width=52.0, spread=1.7),
                 sides=dict(to=0.62, free=0.085, n=2, width=0.042, at=70.0),
                 back=dict(to=0.72, free=0.56, n=12, blunt=0.55)),
    "bob": dict(fringe=dict(kind="swept", n=6, sweep=0.30), sides=dict(to=0.64, free=0.065, n=2, curl=-1.3, flare=0.0),
                back=dict(to=0.70, free=0.085, n=12, curl=-1.4, flare=0.03, layers=2, blunt=0.25)),
    "flip": dict(fringe=dict(kind="m", n=7), sides=dict(to=0.64, free=0.09, n=2, curl=1.3, flare=0.10),
                 back=dict(to=0.70, free=0.13, n=11, curl=1.6, flare=0.14)),
    "ponytail": dict(fringe=dict(kind="m", n=7), sides=dict(to=0.64, free=0.12, n=1, at=70.0),
                     back=dict(to=0.60, free=0.012, n=10, layers=1),
                     tails=[dict(at=(180.0, 0.33), n=7, free=0.46, direction=(0.0, 0.75, 0.45), wave=0.25)]),
    "twintails": dict(fringe=dict(kind="centre", n=6), sides=dict(to=0.64, free=0.11, n=1, at=68.0),
                      back=dict(to=0.62, free=0.012, n=10, layers=1),
                      tails=[dict(at=(112.0, 0.37), n=6, free=0.50, direction=(0.85, 0.20, 0.25), wave=0.3, flare=0.05),
                             dict(at=(248.0, 0.37), n=6, free=0.50, direction=(-0.85, 0.20, 0.25), wave=0.3,
                                  flare=0.05)]),
    "wavy": dict(fringe=dict(kind="curtain", n=6, to=0.44), sides=dict(to=0.66, free=0.20, n=2, wave=0.5, curl=0.5),
                 back=dict(to=0.72, free=0.40, n=11, wave=0.55, curl=0.7, flare=0.05)),
    "sidetail": dict(fringe=dict(kind="swept", n=6, sweep=-0.30), sides=dict(to=0.64, free=0.10, n=1),
                     back=dict(to=0.66, free=0.05, n=10, curl=-1.0),
                     tails=[dict(at=(105.0, 0.42), n=6, free=0.34, direction=(0.9, 0.0, 0.1), wave=0.4, curl=0.6)]),
    "lowtails": dict(fringe=dict(kind="straight", to=0.42, n=7, spread=1.7), sides=dict(to=0.64, free=0.07, n=1),
                     back=dict(to=0.68, free=0.03, n=10, layers=1),
                     tails=[dict(at=(140.0, 0.70), n=5, free=0.36, direction=(0.45, -0.25, -1.0), gravity=0.4),
                            dict(at=(220.0, 0.70), n=5, free=0.36, direction=(-0.45, -0.25, -1.0), gravity=0.4)]),
    "short_f": dict(fringe=dict(kind="swept", n=6, sweep=0.25), sides=dict(to=0.62, free=0.05, n=2, curl=0.6, flare=0.06),
                    back=dict(to=0.68, free=0.045, n=11, curl=0.8, flare=0.08)),
    # boys
    "spiky": dict(fringe=dict(kind="m", to=0.40, n=7, tip=0.022, spread=1.7),
                  spikes=dict(n=16, lift=0.60, free=0.075, flare=1.0)),
    # the same idea with the spikes standing out instead of hanging (reads spikier on a tall head)
    "spiky_up": dict(fringe=dict(kind="m", to=0.36, n=7, tip=0.018, spread=1.7),
                     spikes=dict(n=15, lift=0.9, free=0.066, flare=1.2, up=1.1, gravity=0.18, rings=(0.30, 0.40, 0.50),
                                 lift_decay=0.2, start=64.0),
                     back=dict(to=0.64, free=0.03, n=10, layers=1, flare=0.25, curl=0.8)),
    # swept-up crest: every spike keeps rising
    "crest": dict(fringe=dict(kind="m", to=0.37, n=5, tip=0.016, spread=1.8),
                  spikes=dict(n=12, lift=1.5, free=0.080, flare=0.22, up=2.3, gravity=0.30, rings=(0.10, 0.20, 0.30),
                              lift_decay=0.0),
                  sides=dict(to=0.56, free=0.02, n=2, width=0.034), back=dict(to=0.66, free=0.03, n=11, layers=2)),
    "neat": dict(fringe=dict(kind="swept", to=0.385, n=6, sweep=0.35, tip=0.010),
                 sides=dict(to=0.58, free=0.022, n=2, width=0.034),
                 back=dict(to=0.66, free=0.025, n=11, layers=2)),
    "messy": dict(fringe=dict(kind="centre", to=0.405, n=7, tip=0.020, spread=1.8),
                  sides=dict(to=0.60, free=0.04, n=2, curl=1.0, flare=0.12),
                  spikes=dict(n=13, lift=0.25, free=0.050, flare=0.9, rings=(0.30, 0.48), droop=0.1),
                  back=dict(to=0.66, free=0.045, n=10, curl=1.0, flare=0.10, layers=1)),
    "swept": dict(fringe=dict(kind="curtain", to=0.37, n=6, sweep=0.55, tip=0.012),
                  sides=dict(to=0.58, free=0.02, n=2), back=dict(to=0.66, free=0.03, n=11)),
    "mop": dict(fringe=dict(kind="straight", to=0.415, n=8, width=62.0, spread=1.7),
                sides=dict(to=0.60, free=0.03, n=2, curl=-0.8), back=dict(to=0.68, free=0.035, n=12, curl=-0.9)),
    "tied": dict(fringe=dict(kind="curtain", to=0.43, n=6, sweep=0.4), sides=dict(to=0.66, free=0.11, n=1),
                 back=dict(to=0.64, free=0.012, n=10, layers=1),
                 tails=[dict(at=(180.0, 0.62), n=5, free=0.30, direction=(0.0, 0.5, -0.6), gravity=0.4)]),
    "tall": dict(fringe=dict(kind="m", to=0.39, n=5, tip=0.018, spread=1.8),
                 spikes=dict(n=14, lift=0.95, free=0.095, flare=0.55, rings=(0.16, 0.30, 0.48), gravity=0.05),
                 back=dict(to=0.66, free=0.03, n=10, layers=1)),
    "long_m": dict(fringe=dict(kind="curtain", to=0.45, n=6, sweep=0.35), sides=dict(to=0.66, free=0.18, n=2),
                   back=dict(to=0.72, free=0.30, n=11)),
    "bald_ring": dict(sides=dict(to=0.58, free=0.02, n=2, at=82.0), back=dict(to=0.68, free=0.02, n=9, start=100.0)),

    # ------------------------------------------------------------------ more cuts (shared by both bodies)
    # close crop: the hair barely leaves the scalp
    "crop": dict(fringe=dict(kind="m", to=0.345, n=7, tip=0.008, spread=1.8, sweep=0.15),
                 sides=dict(to=0.52, free=0.010, n=2, width=0.036), back=dict(to=0.64, free=0.012, n=12, layers=2)),
    # long top combed over to one side, short sides and back
    "undercut": dict(fringe=dict(kind="swept", to=0.355, n=7, sweep=0.60, part=-22.0, width=62.0, tip=0.018,
                                 loft=(0.018, 0.027), spread=2.1),
                     sides=dict(to=0.50, free=0.008, n=2, width=0.034, loft=(0.010, 0.012)),
                     back=dict(to=0.62, free=0.010, n=12, layers=1, loft=(0.012, 0.014))),
    # short curls all over
    "curly": dict(fringe=dict(kind="m", to=0.345, n=7, tip=0.022, spread=1.8, curl=2.2),
                  spikes=dict(n=17, lift=0.20, free=0.062, flare=0.85, rings=(0.24, 0.40, 0.56), curl=2.6, wave=0.5,
                              gravity=0.16, width=0.044),
                  back=dict(to=0.66, free=0.045, n=11, curl=2.2, flare=0.10, layers=1)),
    # layered shoulder-length cut with flicked ends
    "shag": dict(fringe=dict(kind="curtain", to=0.385, n=7, sweep=0.30, tip=0.018),
                 sides=dict(to=0.64, free=0.115, n=2, curl=0.9, flare=0.10),
                 spikes=dict(n=12, lift=0.22, free=0.050, flare=0.9, rings=(0.30, 0.46), droop=0.12),
                 back=dict(to=0.70, free=0.165, n=11, curl=1.1, flare=0.10, layers=3, taper=0.25)),
    # one long plait down the back
    "braid": dict(fringe=dict(kind="centre", n=6, to=0.435), sides=dict(to=0.64, free=0.105, n=1, at=70.0),
                  back=dict(to=0.63, free=0.014, n=10, layers=1),
                  braids=[dict(at=(180.0, 0.60), free=0.40, direction=(0.0, 0.55, -0.75), width=0.050, bead=0.034)]),
    # two low plaits falling in front of the shoulders
    "twinbraids": dict(fringe=dict(kind="straight", to=0.425, n=7, spread=1.7), sides=dict(to=0.62, free=0.05, n=1),
                       back=dict(to=0.68, free=0.022, n=10, layers=1),
                       braids=[dict(at=(118.0, 0.66), free=0.27, direction=(0.55, -0.45, -0.9), width=0.040,
                                    forward=0.35),
                               dict(at=(242.0, 0.66), free=0.27, direction=(-0.55, -0.45, -0.9), width=0.040,
                                    forward=0.35)]),
    # hair gathered into a bun high on the back of the head
    "bun": dict(fringe=dict(kind="swept", n=6, sweep=0.28, to=0.43), sides=dict(to=0.66, free=0.125, n=1, at=68.0),
                back=dict(to=0.60, free=0.012, n=10, layers=1), buns=[dict(at=(180.0, 0.25), r=0.046)]),
    # two small buns on top with short tails
    "odango": dict(fringe=dict(kind="m", n=7), sides=dict(to=0.64, free=0.09, n=1, at=68.0),
                   back=dict(to=0.64, free=0.03, n=10, layers=1, curl=-0.8),
                   buns=[dict(at=(118.0, 0.21), r=0.034), dict(at=(242.0, 0.21), r=0.034)]),
    # long hair parted far to one side, the fringe sweeping across the forehead
    "sidelong": dict(fringe=dict(kind="swept", n=7, sweep=0.50, part=24.0, to=0.385, width=62.0, tip=0.018),
                     sides=dict(to=0.66, free=0.24, n=2, asym=0.55, curl=0.4),
                     back=dict(to=0.72, free=0.50, n=11, taper=0.16, curl=0.35, layers=2)),
    # high spiky ponytail
    "highpony": dict(fringe=dict(kind="m", n=7, to=0.415, tip=0.020), sides=dict(to=0.62, free=0.07, n=1, at=70.0),
                     back=dict(to=0.58, free=0.010, n=10, layers=1),
                     tails=[dict(at=(180.0, 0.20), n=7, free=0.30, direction=(0.0, 0.8, 0.75), wave=0.15,
                                 gravity=0.20, spread=0.024)]),
    # medium hair pushed back off the forehead, flicking out at the nape
    "pushed": dict(fringe=dict(kind="curtain", to=0.345, n=6, sweep=0.75, tip=0.030, width=50.0, loft=(0.018, 0.030)),
                   sides=dict(to=0.60, free=0.045, n=2, curl=1.2, flare=0.12, sweep=0.25),
                   back=dict(to=0.68, free=0.075, n=11, curl=1.5, flare=0.14, layers=2)),
    # long straight hair in a low tail tied at the nape, long side locks
    "lowtail": dict(fringe=dict(kind="curtain", to=0.44, n=6, sweep=0.38), sides=dict(to=0.68, free=0.20, n=1),
                    back=dict(to=0.64, free=0.012, n=10, layers=1),
                    tails=[dict(at=(180.0, 0.64), n=6, free=0.48, direction=(0.0, 0.45, -0.7), gravity=0.4,
                                spread=0.016)]),
}


def styled(name, **edits):
    """A recipe with per-section edits (see the module docstring)."""
    out = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, (list, tuple)) else v)
           for k, v in HAIR[name].items()}
    for key, val in edits.items():
        if val is None:
            out.pop(key, None)
        elif isinstance(val, dict) and isinstance(out.get(key), dict):
            out[key] = dict(out[key], **val)
        else:
            out[key] = val
    return out
