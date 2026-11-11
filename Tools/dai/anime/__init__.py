"""
Anime cast: the island's students and teachers on one shared skeleton with CC0 gesture takes.

  atelier/     the project's own character generator (head, painted face, clump hair, body, outfits,
               the original cast designs) - every default cast member is built by it
  skeleton.py  shared UE5-Mannequin-named skeleton, anime-teen proportions (1.70 m, ~7 heads)
  retarget.py  CC0 Quaternius animation takes -> cast skeleton (+ hand-authored duel / swim takes)
  gait.py      biomechanical idle / walk / run solver
  cel.py       the cel shading classes shared by the previews and Unreal
  cast.py      who is who: slot names, dorms, dialogue, spawn markers, and the design that plays each
  roster.py    named ambient NPC identities: unique names, voices, hair colours
  models.py    import path for artist-made models that replace a slot (Docs/CHARACTER_MODELS.md)
  body.py      the duel disk attachment
  build.py     the "cast" pipeline stage: FBX meshes + takes, textures, Data/cast.json
"""
