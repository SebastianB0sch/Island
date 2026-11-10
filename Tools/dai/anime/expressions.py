"""Facial expression recipes for the cast's portrait frames.

Every cast model carries the same facial morph targets (atelier/head.py: Joy, Fun, Angry, Sorrow,
Surprised, the brow and blink morphs, the visemes). A story expression is a small mix of them, layered over
a quarter of the character's resting expression so the face stays recognisable.
"""

# expression -> facial morph weights (the cast's morph targets, see atelier/head.py)
WEIGHTS = {
    "happy": {"Joy": 1.0},
    "laugh": {"Fun": 0.6, "Joy": 0.6, "A": 0.35},
    "angry": {"Angry": 1.0},
    "determined": {"Angry": 0.60, "BrowAngry": 0.30},
    "shocked": {"Surprised": 1.0, "O": 0.25},
    "sad": {"Sorrow": 1.0},
    "nervous": {"Sorrow": 0.50, "Surprised": 0.50},
    "smug": {"Fun": 0.90, "BrowAngry": 0.25, "Blink": 0.20},
    "thoughtful": {"Sorrow": 0.40, "BrowSorrow": 0.20},
    "proud": {"Joy": 0.70, "BrowAngry": 0.20},
    "stern": {"Angry": 0.85, "BrowAngry": 0.20},
    "sleepy": {"Blink": 0.85, "BrowSorrow": 0.15},
    "hungry": {"Joy": 0.55, "Surprised": 0.35, "O": 0.35},
    "confused": {"Sorrow": 0.45, "Surprised": 0.45, "BrowSorrow": 0.10},
    "apologetic": {"Sorrow": 0.90, "BrowSorrow": 0.15},
}

# The duel HUD's generic cut-in emotions (DADuelUI::SpawnDuelFxReaction).
# Characters with a bespoke story expression use that frame first; these are
# rendered for named opponents whose story data declares no expressions.
DUEL = {"happy", "angry", "determined", "shocked", "sad", "laugh"}

# Frames rendered from the project's own models.  The five regulars with
# ported Duel Links art get official cut-ins from fetch_expression_portraits.py.
GENERATED = {
    "banner", "beauregard", "blair", "brier", "chumley", "conklin", "crowler",
    "damon", "dimitri", "dorothy", "fontaine", "gerard", "jasmine", "mimicry",
    "mindy", "sartyr", "shadow_duelist", "sheppard", "topher", "torrey",
    "student_m1", "student_f1", "student_f2", "unknown_student",
}
OFFICIAL = {"alexis", "bastion", "chazz", "syrus", "zane"}


def resting(entry):
    """Resting expression of a cast entry: its own override, else its design's."""
    if entry.get("expression") is not None:
        return dict(entry["expression"])
    if entry.get("design"):
        from .atelier import designs
        return dict(designs.all_designs()[entry["design"]].get("expression") or {})
    return {}


def blend(resting, expression):
    """Blendshape mix for one expression, retaining a quarter of the resting face."""
    if expression == "neutral":
        return dict(resting or {})
    target = WEIGHTS.get(expression)
    if target is None:
        return {}
    out = {}
    for key, value in (resting or {}).items():
        out[key] = value * 0.25
    for key, value in target.items():
        out[key] = min(1.0, out.get(key, 0.0) + value)
    return out
