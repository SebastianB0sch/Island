"""Facial expression recipes for the VRoid-derived cast.

The base models expose VRoid's ``Fcl_ALL_*`` / ``Fcl_BRW_*`` / ``Fcl_EYE_*`` /
``Fcl_MTH_*`` blendshapes.  The cast pipeline bakes a resting expression into
the face, so an expression frame must be rendered by rebuilding the model with
the target mix (see models._bake_expression and portrait.render_expression).

The story data uses a small vocabulary: neutral, happy, laugh, angry,
determined, shocked, sad, nervous, smug, thoughtful, proud, stern, sleepy,
hungry, confused and apologetic.  Each recipe below is deliberately broad
enough to read at the 164 px dialogue size, and keeps a little of the
character's resting expression so the face stays recognisable.
"""

# expression -> blendshape weights (names after "Fcl_")
WEIGHTS = {
    "happy": {"ALL_Joy": 1.0},
    "laugh": {"ALL_Fun": 1.0},
    "angry": {"ALL_Angry": 1.0},
    "determined": {"ALL_Angry": 0.55, "MTH_Angry": 0.30, "BRW_Angry": 0.25},
    "shocked": {"ALL_Surprised": 1.0, "MTH_O": 0.25},
    "sad": {"ALL_Sorrow": 1.0},
    "nervous": {"ALL_Sorrow": 0.45, "ALL_Surprised": 0.50, "MTH_Sorrow": 0.15},
    "smug": {"MTH_Fun": 0.85, "MTH_Joy": 0.20, "BRW_Angry": 0.25, "EYE_Close": 0.25, "EYE_Joy": 0.15},
    "thoughtful": {"ALL_Sorrow": 0.45, "ALL_Neutral": 0.45, "BRW_Sorrow": 0.15},
    "proud": {"ALL_Joy": 0.70, "ALL_Angry": 0.15, "BRW_Angry": 0.10},
    "stern": {"ALL_Angry": 0.85, "BRW_Angry": 0.20},
    "sleepy": {"EYE_Close": 0.85, "ALL_Sorrow": 0.10},
    "hungry": {"ALL_Joy": 0.55, "ALL_Surprised": 0.35, "MTH_O": 0.35},
    "confused": {"ALL_Sorrow": 0.45, "ALL_Surprised": 0.45, "BRW_Sorrow": 0.10},
    "apologetic": {"ALL_Sorrow": 0.90, "MTH_Sorrow": 0.15},
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
