"""
Anime cast: Yu-Gi-Oh! GX style students and teachers (fan-made, original geometry) on CC0 animation.

  skeleton.py  shared UE5-Mannequin-named skeleton, anime-teen proportions (1.70 m, ~7 heads)
  retarget.py  CC0 Quaternius animation takes -> cast skeleton (+ hand-authored duel / swim takes)
  head.py      oval anime head carrying the painted face (face.py)
  hair.py      scalp cap + tapered anime locks, one style per character
  body.py      Duel Academy uniforms (blazer, coat, skirt, boots), accessories, duel disk
  skin.py      skin weights, inverted-hull ink outline, assembly into one skinned mesh
  cast.py      who is who: looks, dorms, dialogue, which NPC marker they take over
  build.py     the "cast" pipeline stage: FBX meshes + takes, face textures, Data/cast.json
"""
