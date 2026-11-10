# Character models

The cast is built two ways:

1. **The atelier** (`Tools/dai/anime/atelier`): the project's own generator. Every character in the
   default cast is modelled from scratch by it. No third-party base model is used, so the cast is
   redistributable with the project.
2. **Artist-made models**: any cast slot can be replaced by a model you made, commissioned or licensed.

The first gives a consistent, fully owned cast. It does not reach the hand-sculpted quality of a commercial
anime game's characters; the second is the route to that level, one character at a time.

Models from other games are not an option: they are those studios' property, and neither importing them nor
rebuilding their characters is something this pipeline is meant for.

## Atelier designs

A design (`atelier/designs.py`) is a dict of parameters:

| Key | Meaning |
|---|---|
| `female`, `build`, `bust`, `skin` | body table, stockiness, skin colour |
| `head` | `{jaw, chin, cheek, face_w, cranium}` multipliers on the skull rings |
| `eyes` | eye shape overrides (`paint.EYE`): size, tilt, lash, wing, iris size. Presets: `F_ROUND`, `F_GENTLE`, `F_SHARP`, `F_SLEEPY`, `F_BRIGHT`, `M_SOFT`, `M_SHARP`, `M_ROUND`, `M_NARROW` |
| `iris`, `iris2`, `brows`, `mouth`, `blush`, `lips`, `mole` | face paint and decals |
| `expression` | resting expression as a mix of the facial morphs, e.g. `{"Fun": 0.4, "BrowAngry": 0.3}` |
| `hair` | `{color, color2, style}`; `style` is a dict of sections (`fringe`, `sides`, `back`, `spikes`, `tails`, `ahoge`), see `HAIR` for the presets |
| `outfit` | `[(garment, params)]` in wearing order; garments are listed in `outfit.GARMENTS`, plus `hairband`, `glasses`, `hairbow` |
| `tint` | generic students: `["jacket", "hair"]` parts Unreal recolours per dorm / NPC |

`Tools/dai/anime/cast.py` maps each cast slot (name, dorm, height, dialogue, spawn marker) to a design.

```
python Tools/build_island.py cast                    # build and export the whole cast
python Tools/preview_anime.py jaden alexis           # Cycles lineup of two slots
python Tools/preview_anime.py alexis --portrait      # close-up
```

What a build produces per character: `SK_Anime_<Design>.fbx` on the shared `Cast` skeleton, a face sheet,
a hair sheet and a cloth atlas under `SourceAssets/Textures/Characters/<Design>/`, and its entry in
`SourceAssets/Data/cast.json`. A character is about 65-80k triangles and 5 materials.

## Replacing a slot with an artist-made model

1. Put the model in `Tools/thirdparty/<pack>/<asset>/` with a `SOURCE.txt` (author, licence, source URL).
2. Register it in `Tools/thirdparty/registry/anime.json`:

   ```json
   "anime_models": { "my_hero": { "file": "mypack/hero/hero.vrm", "female": false, "height": 1.72 } },
   "cast_models":  { "jaden": "my_hero" }
   ```

   `height` is the model's crown height in metres (without hair); it turns the slot's height in cm into
   the runtime scale. A `cast_models` key is a cast slot id or an atelier design key.
3. `python Tools/build_island.py cast`.

The model keeps its own face, hair, outfit and textures. The import (`Tools/dai/anime/models.py`):

* renames the humanoid bones to the UE5 Mannequin scheme. VRM 0.x / 1.0 humanoid maps are read from the
  file; Mixamo and `J_Bip_*` names are recognised otherwise. Required: hips, spine, head, upper and lower
  arms, upper and lower legs, feet.
* gives every material the cast's cel class (skin, face, hair, cloth or flat) from its name, and adds the
  ink outline.
* bakes the cast's takes onto the model's own proportions. Models on a different skeleton form their own
  skeleton group, with their own `A_Anime_<Group>_<State>` takes.

For the runtime features to work the model needs:

| Feature | What the model must have |
|---|---|
| Blinking, lip-sync, emotions | blendshapes for `Blink`, `Blink_L/R`, `A I U E O`, `Joy`, `Angry`, `Sorrow`, `Surprised`, `Fun` (also `EyeJoy`, `BrowAngry`, `BrowSorrow`). VRoid `Fcl_*`, VRM expression names, ARKit `eyeBlinkLeft/Right` and the plain names are mapped (`models.MORPH_ALIASES`). Missing ones are skipped. |
| Hair springs | hair bones under the head whose names contain `Hair` (`_Long` in the name selects the heavier long-hair spring) |
| Skirt / coat springs | bone chains named `skirt_*` / `coattail_*`, or containing `CoatSkirt` |
| Cel classes | material names containing `hair`, `skin`, `face`, or eye / brow / lash / mouth keywords for the flat class (`Tools/dai/anime/cel.py`) |

Check that the model's licence allows redistribution before committing it; otherwise keep it out of git
and register it only on your machine.

## Status of the artist path

The import code is the pipeline's earlier base-model path, kept for this purpose. It was exercised on VRM
0.x humanoids. Other sources (VRM 1.0, Mixamo FBX) share the same code but have not been run against a real
file in this repository, since none is checked in. Expect to adjust material names or the morph alias table
for a new source.
