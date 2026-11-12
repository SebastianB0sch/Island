# Bespoke characters: the template

The protagonists (`hero`, `heroine`) are the first two *bespoke* characters: they are written by hand, lock by
lock and garment by garment, as plain data in `Tools/dai/anime/hero.py`, and built by the template engine
`Tools/dai/anime/bespoke.py`. Every future character that should reach the same level starts from this
template rather than from a preset look.

![The protagonists](renders/protagonists.jpg)

## Making a new bespoke character

1. **Add a design** to `hero.DESIGNS` (or a new module the registry imports): `key`, `base` (`vroid_a` /
   `vroid_b` girls, `vroid_c` boys), `female`, `height` (cm), `tint`, `hair`, `face`, `colors`, `wear`.
   Copy the closest protagonist and change it; the helper functions (`_fringe`, `_strand`, `_mirror_az`,
   `_coat`, `_strap`) are there to be reused.
2. **Add a cast entry** for it in `cast.py` (name, dorm, height, an atelier fallback design) - or point an
   existing slot at it by giving the slot's id a design in `hero.DESIGNS`.
3. **Check it**: `python Tools/check_bespoke.py` runs `bespoke.check(design)`, which lists every place a design
   breaks a learning below (the test suite runs it on every registered design too). `python
   Tools/check_bespoke.py <id> --built` also builds the model and measures how much of each eye a camera sees
   from -60 to 60 deg (`bespoke.eye_clearance`): both eyes need half their area from the front and the near
   eye 40 % from +-20 deg - hair that hides the eyes is the defect a design table cannot show.
4. **Preview** with the scratch renderer pattern used for the protagonists: `build.render_lineup(..., entries=E)`
   for a face, a 3/4 full body and a back view. Render one view at a time - parallel previews write the same
   texture files and race. Preview a runtime-tinted coat in a dorm colour (it is near white in the build).
   Previews write into `SourceAssets/Textures`: restore them (`git checkout`) or rebuild the cast before
   committing.
5. **Build**: `python Tools/build_island.py cast`.

## The design data

| Key | What it holds |
|---|---|
| `hair.sections` | recipe sections combed first (`fringe`, `sides`, `back`, `spikes`, `tails`, `braids`, `buns`, `ahoge`: `atelier/hair.py`) - use them for the bulk (crown, back, tails) |
| `hair.locks` | every hand-placed lock: `az` (deg, + = the character's left), `s0`/`s1` (rings: 0 crown, ~0.42 brows, ~0.50 eyes, ~0.58 cheeks, ~0.70 nape), `free` (m hanging past `s1`), `sweep`, `width`, `loft`, `gravity`, `forward`, `curl`, `flare`, `wave`, `kind` (`fringe` locks get no spring chain); `mirror=True` (both sides, `asym` scales the right one), `accent=True` (accent colour), `strand=True` (thin overlay lock), `over_eye=True` (allowed to cover an eye) |
| `hair` colours | `color`, `tip` (ombre), `accent`, `accent_tip`, `tie`, `sheen_color`, `sheen`; quality: `res` (2), `min_chain` (0.045) |
| `face` | `iris`, `iris_ring` (two-tone), `sparkle` (third catch-light), `lash` (lash line weight, 0 = the base's), `brows`, `expression` (base morph mix), `face_shape` (`chin`, `jaw`, `cheeks`), `earrings` (metal, stone) |
| `wear` | `[(garment, params)]` in wearing order - `atelier/outfit.GARMENTS`, including the bespoke pieces below |

Garments added for the protagonists, available to every design:

| Garment / option | |
|---|---|
| `top(hem_front=z)` | cut-away hem: short at the front, `hem` at the back (tails on the coat-tail chains) |
| `top(sleeve_sides=("l",))` | one-sleeved coat (the other side is a vest armhole) |
| `top(drape=0.02)` | the shell hangs plumb from the shoulder blades and the hips instead of following the body into the small of the back (the value: how far it may still taper per metre) |
| `top(vent=(z, spread))` | a centre back vent up to `z`: the tails part by `spread` rad at the hem and hang from their own hem chains (the legs swing through it) |
| `top(clear=0.006)` | the shell stands this far outside everything already worn on the torso - it tents over belts, pouches, thigh straps and skirts instead of cutting through them |
| `strap(path, over=...)` | strap on the torso along `[(z, azimuth)]`, over the shoulder as one piece with `over`, with buckles and a pouch |
| `legstrap(pouch_at, buckle_at)` | thigh strap with a buckle and a pouch, placed in degrees round the thigh from its outer side (negative: towards the back, behind the hanging hand) |
| `bracer` | armoured forearm guard with a duel-disk plate and a lit ring |
| style `motif=dict(..., h=...)` | border patterns (always give `h`) |
| style `crest=dict(u, v, size, color, outline, rim)` | a large emblem painted on a garment (the back of a coat: `u=0.5`), with an ink rim so it reads on any dorm colour |
| `spikes=dict(..., symmetric=True)` | recipe spikes staggered inside their fan (always set it - see the learnings) |

## Learnings

What made the difference on the protagonists - `bespoke.check()` enforces the hair and motif rules,
`check_bespoke.py --built` the eyes.

- **Measure the eyes, do not eyeball them.** The hero's right eye was 1 % visible from the front for two
  rounds of lock tuning: the culprit was not a hand-placed lock but the recipe `spikes`, whose rows each turn
  their fan by 0.21 rad - the lowest row reaches round to -32 deg on one side only. `symmetric=True` and the
  ray-cast clearance (0 -> 78 % from the front, 2 -> 97 % from -20 deg) settled it.
- **A lock ends where its tip hangs**, `s1` plus its free length (~3 rings per metre), not at `s1`. Face-framing
  locks belong just in front of the ears (~74 deg); at 60 deg they lie on the cheek seen from that side.

- **Lock width.** Locks need about twice the width that seems right on paper (a recipe fringe lock is ~0.07
  design-m). Below 0.045 the hair turns stringy, with gaps and a heavy outline per lock - only thin overlay
  strands (`strand=True`) go narrower.
- **Sweep moves the lock.** A lock ends at `az + sweep`. A fringe lock ending below the brows over an eye
  (12-34 deg off centre) hides that eye; shorten it or move it, unless the design wants it (`over_eye`).
- **Resolution and physics.** `res=2` removes the faceted look in close-ups; `min_chain=0.045` gives the
  short side / back locks spring chains, not only the long ones.
- **Dark hair needs its own highlight colour** (`sheen_color`, a cool tone at ~0.55) or the ring vanishes.
- **Motifs need `h`** or they smear into stripes over the whole garment.
- **Eyes.** The base iris is a flat disc: paint it in layers and put two catch-lights on the highlight layer;
  ink and thicken the lash line for a sharper face. On the girls' base, `Fun` above ~0.1 closes the eyes.
- **Silhouette beats surface.** The cut-away hem, one sleeve, straps with buckles, a belt stack and one
  statement piece (the bracer) did more than any texture work.
- **Layering is geometry, not ease.** An outer coat sized by ease alone either cuts through the belt pouch or,
  over a flared skirt, balloons into a sack. `clear` fits it over what is under it and `drape` lets it fall
  from there: the heroine's coat went from ease 0.036 and a bell to ease 0.024 and a tailored line.
- **Coats hang, they do not hug.** A shell that follows the small of the back faces slightly down there and
  the cel ramp shades that as a dark blotch; the drape is measured from one vertical axis (cloth falls
  plumb - measured from the body's leaning centre line a "straight" back still tucks in). Long coats get no
  painted waist creases at the back, and a back vent turns the sack of a long coat into a tailcoat.
- **The cel core shadow is for creases.** A surface facing straight away from the key light sits at
  half-Lambert ~0.155; the cloth core step was at 0.20, so every gentle bulge of a coat's back crossed it.
  It is at 0.10 now (`cel.py`).
- **Thin bands keep the skin under them.** Cutting away the base model's skin under a 2.6 cm thigh strap
  opened holes beside it (its faces are as tall as the strap is wide); straps, belts and bands are left out
  of the skin cut (`wardrobe.THIN_PARTS`).
- **Long hair and accents.** An accent under-layer reads on short cuts; on long back hair it shows as
  patches - keep the accent to the tail and to short locks at the ears (a long copper side lock shows
  through the back hair as torn patches at the shoulders).
- **Budget.** A bespoke character is ~175-200k triangles and 13 materials (the regular cast ~50-80k, 9):
  the double-resolution hair is most of it.

## Still to do for real parity

The template removes the generic look; it does not make a sculpted character. The faces and bodies are the
VRoid bases', garments are generated shells with painted detail, hair is separate pointed locks, and the
Unreal cel material does not yet read the extra shading layers. An artist-made model through the replacement
slot (`Docs/CHARACTER_MODELS.md`) remains the route to full parity.
