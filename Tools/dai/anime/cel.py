"""
The anime cel shading model shared by the Blender previews and Unreal (stdlib only).

Every cast material is put into one of a few shading classes, the way anime game shaders separate skin,
hair, cloth and the painted eye / mouth parts:

  class   lit/shadow ramp                    shadow colour            extras
  -----   ---------------------------------  -----------------------  ------------------------------------
  skin    hard step at half-Lambert 0.50     warm (reddened skin)     soft rim
  face    step at 0.30, wider (soft) edge    warm                     faint rim; smoothed normals (shading.py)
  hair    hard step at 0.48                  cool, deeper             rim + an "angel ring" highlight band
  cloth   hard step at 0.50                  cool, slightly blue      rim
  flat    none (always fully lit)            -                        eyes, brows, lashes, mouth, highlights

In Unreal the characters stay normally lit (Lumen GI, cast shadows, interior lamps, night) and a stencil-
masked post-process (PP_DA_Cel, materials.py) bands that lighting into two tones with a saturated shadow
colour; the character material itself (M_DA_Cel) carries the rim light, the hair highlight and turns
specular reflections off (no plastic sheen). The Cycles previews evaluate the same ramp directly
(build.preview_material).
"""

# half-Lambert threshold, edge width, shadow multiplier (linear RGB), rim strength, hair highlight strength
CLASSES = {
    "skin": dict(threshold=0.50, soft=0.035, shadow=(0.94, 0.70, 0.66), rim=0.22, spec=0.0),
    "face": dict(threshold=0.30, soft=0.10, shadow=(0.96, 0.76, 0.72), rim=0.12, spec=0.0),
    "hair": dict(threshold=0.48, soft=0.03, shadow=(0.58, 0.58, 0.74), rim=0.30, spec=0.45),
    "cloth": dict(threshold=0.50, soft=0.03, shadow=(0.62, 0.64, 0.82), rim=0.18, spec=0.0),
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
    return out
