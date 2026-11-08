# Procedural / simple asset audit

This audit records what the island still builds procedurally, what already uses
a real asset, and what the optional Fab packs replace. The goal is to keep the
"replace the blockout with real assets" work honest: most props are already real
CC0 assets, and the remaining gaps are small and explicit.

## Instance groups (171 total)

| Category | Groups | Current source | Notes |
| --- | ---: | --- | --- |
| Vegetation (trees, palms, bushes, ferns, flowers, grass) | 15 | **Fab** (`Tools/dai/fab_nature.py`) | StyleHex / PBR Nature / Tropical |
| Rocks and cliffs | 7 | **Fab** (`Tools/dai/fab_props.py`) | StyleHex stones, PBR rocks |
| Driftwood, stump | 2 | CC0 Poly Haven | Already real; no suitable Fab mesh |
| Outdoor props replaced with Fab | 7 | **Fab** (`Tools/dai/fab_props.py`) | bollard, planter, vending machine, lamp post, trash bin, beach chair/parasol |
| Other outdoor props | 12 | CC0 Poly Haven / Sketchfab | barrel, bench, containers, crate, fences, old lamp, picnic table, signpost, stone lantern |
| Interior furniture / decor | 124 | CC0 Poly Haven (`Tools/thirdparty/registry/interiors.json`) | real size, cel-painted + ink outline |
| **Still procedural** | **4** | native Blender meshes | 3 `SM_Flagpole_*`, `SM_DuelDummy` |

The four remaining instance groups are intentionally left procedural because
none of the installed Fab packs has a convincing match:

- **Flagpoles** - the packs have flag *banners* and building-scale flags, but no
  free-standing 10 m pole with a flag. The procedural pole is simple, correctly
  sized and already has the correct collision/light behaviour.
- **Duel dummy** - a GX-specific post + duel disk. The packs have no training
  dummy/mannequin; a generic stand-in would look out of place.

## Static geometry

These are still procedural and are a much larger replacement project than the
prop pass:

| Static content | Count | Notes |
| --- | ---: | --- |
| Terrain chunks | 64 | heightfield + splat material; intentionally custom |
| Building/location meshes | ~120 | academy, dorms, gym, harbor, lighthouse, onsen, etc. |
| Road ribbons | 6 | procedural splines |
| Terrain features (volcano, water, lake, waterfall, cliffs, beach, forest) | ~20 | custom terrain features |
| Door leaves | 587 | procedural door kit with automatic open/close |

Replacing the buildings with a Fab kit would change the layout, interiors,
collision, NPC navigation and door sockets. It is feasible with a modular
school/campus kit, but it is a separate, larger milestone. The safest first
candidates are the exterior shells only (keep the existing interiors and
collision proxies).

## Free / downloadable alternatives

Fab has a permanent free-content filter:

- <https://www.unrealengine.com/fabfreecontent>
- <https://www.fab.com/search?ui_filter_price=1&is_free=1>

Targeted Fab searches (check the current price; the free filter is already set):

| Gap | Fab search |
| --- | --- |
| Flagpole / flag | <https://www.fab.com/search?q=flagpole&is_free=1> |
| Training dummy / mannequin | <https://www.fab.com/search?q=training+dummy&is_free=1> |
| Vending machine | <https://www.fab.com/search?q=vending+machine&is_free=1> |
| Street furniture / bollards | <https://www.fab.com/search?q=street+props&is_free=1> |
| Modular school / campus | <https://www.fab.com/search?q=modular+school&is_free=1> |
| Modular building kit | <https://www.fab.com/search?q=modular+building&is_free=1> |

CC0 alternatives that fit the project's existing third-party pipeline:

- **Quaternius Modular Streets Pack** (CC0, 25 models incl. street props):
  <https://quaternius.com/packs/modularstreets.html>
- **Quaternius Downtown City MegaKit** (CC0, 315 modular city models):
  <https://quaternius.com/packs/downtowncitymegakit.html>
- **Quaternius Ultimate Buildings Pack** (CC0):
  <https://quaternius.com/packs/ultimatetexturedbuildings.html>
- **Quaternius Ultimate House Interior Pack** (CC0, furniture):
  <https://quaternius.com/packs/ultimatehomeinterior.html>
- **Quaternius Ultimate Furniture Pack** (CC0):
  <https://quaternius.com/packs/ultimatefurniture.html>
- **Kenney City Kit (Roads)** (CC0):
  <https://kenney.nl/assets/city-kit-roads>
- **Kenney 3D assets** (CC0):
  <https://kenney.nl/assets>
- **Poly Haven Planter Box 01** (CC0; already downloaded locally as
  `polyhaven/models/planter_box_01`):
  <https://polyhaven.com/a/planter_box_01>
- **Poly Haven models** (CC0):
  <https://polyhaven.com/models>
- **Poly Pizza** (CC0 low-poly models, including Quaternius packs):
  <https://poly.pizza/>
- **Cenji Urban & Street Props Mega Pack** (120 free assets incl. a detailed
  vending machine; check the itch.io license):
  <https://cenjiyt.itch.io/low-poly-urban-street-props-mega-pack-120-free-assets>

When adding one of these, follow the existing `Tools/thirdparty/` pattern: put
the asset under `Tools/thirdparty/<pack>/<asset>/` with a `SOURCE.txt`, register
it in `Tools/thirdparty/registry/*.json`, and rebuild the Blender layout. The
Unreal build imports it like the other curated CC0 assets.

## Verified build

After installing the local packs and rebuilding the level:

```text
Fab nature:     85,185 native instances -> 25 Fab meshes
Fab props/rocks: 3,797 native instances -> 16 Fab meshes
Scatter actors:  183 (103,374 instances total)
Remaining procedural: 3 flagpole groups + duel dummy
```

The level inspection confirms the new Fab meshes are the active scatter meshes:
`SM_ao017_polelight_1_lv1` (266), `SM_ao127_01` (40), `SM_ao336_lv1` (29),
`SM_ao059_nosdw_lv1` (18), `SM_ao130_nosdw_parasol_lv1` (12), `SM_chair01` (15),
`SM_PlamPlant01/02` (13 each), plus the StyleHex/PBR rock variants.
