"""
The anime cel shading model shared by the Blender previews and Unreal (stdlib only).

Every cast material is put into one of a few shading classes, the way anime game shaders separate skin,
hair, cloth and the painted eye / mouth parts:

  class   lit/shadow ramp                    shadow colour            extras
  -----   ---------------------------------  -----------------------  ------------------------------------
  skin    hard step at half-Lambert 0.50     warm (reddened skin)     soft rim, deeper core shadow, warm terminator
  face    step at 0.30, wider (soft) edge    warm                     faint rim; smoothed normals (shading.py)
  hair    hard step at 0.48                  cool, deeper             rim, core shadow (+ an "angel ring" band on
                                                                      hair without a painted highlight)
  cloth   hard step at 0.50                  cool, slightly blue      rim, core shadow
  flat    none (always fully lit)            -                        eyes, brows, lashes, mouth, highlights

In Unreal the characters stay normally lit (Lumen GI, cast shadows, interior lamps, night) and a stencil-
masked post-process (PP_DA_Cel, materials.py) bands that lighting into two tones with a saturated shadow
colour; the character material itself (M_DA_Cel) carries the rim light, the hair highlight and turns
specular reflections off (no plastic sheen). The Cycles previews evaluate the same ramp directly
(build.preview_material).
"""

# half-Lambert threshold, edge width, shadow multiplier (linear RGB), rim strength, hair highlight strength.
# Optional second step: below `threshold2` the shadow deepens to `shadow2` (the core shadow under arms, chins
# and folds); `terminator` (colour, strength) is a thin saturated band just inside the shadow edge - the warm
# line anime skin has where light turns to shade. Cloth keeps its core step below 0.155 - the value of a surface
# facing straight away from the key light horizontally - or the broad back of a coat, which sits right at
# that value, breaks into blotches wherever the cloth bulges a little; it is for undersides and folds. Unreal's M_DA_Cel reads rim / spec; the other fields are
# exported for it too (optional: a master material that does not know them ignores them).
CLASSES = {
    "skin": dict(threshold=0.50, soft=0.035, shadow=(0.95, 0.72, 0.67), rim=0.20, spec=0.0,
                 threshold2=0.20, shadow2=(0.86, 0.57, 0.55), terminator=(1.0, 0.50, 0.40), terminator_strength=0.38),
    "face": dict(threshold=0.30, soft=0.10, shadow=(0.96, 0.76, 0.72), rim=0.10, spec=0.0,
                 terminator=(1.0, 0.56, 0.46), terminator_strength=0.22),
    "hair": dict(threshold=0.48, soft=0.03, shadow=(0.62, 0.60, 0.76), rim=0.16, spec=0.45,
                 threshold2=0.18, shadow2=(0.44, 0.43, 0.62)),
    "cloth": dict(threshold=0.50, soft=0.03, shadow=(0.66, 0.67, 0.84), rim=0.15, spec=0.0,
                  threshold2=0.10, shadow2=(0.48, 0.50, 0.71)),
    "flat": dict(threshold=-1.0, soft=0.0, shadow=(1.0, 1.0, 1.0), rim=0.0, spec=0.0),
}

# hair highlight: the annulus of N.H between these two values (the arc of an 'angel ring')
RING_NH = (0.80, 0.86)

# direction *towards* the key light of the previews (matches the sun in build.render_lineup)
LIGHT_DIR = (-0.278, -0.689, 0.669)   # = the preview sun at (48, 0, -22) deg

_FLAT_KEYS = ("eyeiris", "eyewhite", "eyehighlight", "eyeline", "eyelash", "facebrow", "facemouth", "_eye",
              "brow", "lash", "mouth", "glasses", "teeth", "tongue")


def classify(name, spec=None):
    """Shading class of a cast material from its palette name (and spec, which may pin it: spec["cel"])."""
    if spec and spec.get("cel") in CLASSES:
        return spec["cel"]
    n = name.lower()
    src = (spec or {}).get("source_material", "").lower()
    both = n + " " + src
    if any(k in both for k in _FLAT_KEYS):
        return "flat"
    if "hair" in both:
        return "hair"
    if ("face" in both and "skin" in both) or n.endswith("_face"):
        return "face"
    if "skin" in both or "_body" in both:
        return "skin"
    return "cloth"


def params(name, spec=None):
    cls = classify(name, spec)
    out = dict(CLASSES[cls])
    out["cel"] = cls
    if spec and spec.get("ring") is not None:      # painted highlights (atelier hair): tune the shader ring
        out["spec"] = float(spec["ring"])
    return out
