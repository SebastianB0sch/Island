"""
Atelier: the project's own anime character generator.

Every cast member is modelled from scratch by this package - no third-party base model is involved:

  mesh.py     lofted surface parts with analytic UVs, skin weights, morph targets and ink-line widths
  head.py     the head: tilted-ring loft, painted eyes, eyelid / mouth / brow rigs (16 morph targets)
  paint.py    face, iris, hair and cloth textures painted in UV space (numpy, no source images)
  body.py     torso, limbs and hands from cross-section tables shared with the outfit and hair collision
  hair.py     clump hair: styled locks flowing from the crown, with spring-bone chains
  outfit.py   layered garments cut from the body's own cross-sections (jackets, skirts, coats, boots ...)
  designs.py  the original cast: faces, hairstyles and outfits
  build.py    one design -> one skinned mesh on the shared cast skeleton

The generated meshes use the same skeleton, material classes, morph-target names and spring-bone
prefixes as the rest of the pipeline (Tools/dai/anime), so Unreal imports them unchanged.
"""
