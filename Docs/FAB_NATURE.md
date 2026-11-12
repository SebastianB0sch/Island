# Fab nature and prop packs (local-only)

The island can use the same stylized Fab assets as the reference UE5 project:

- **StyleHex FREE Stylized Forest Sample** - trees, bushes, flowers, grass and
  stones;
- **Stylized PBR Nature** - foliage and rocks;
- **Tropical Garden Lounge** - palms, cypress, undergrowth, rocks and potted
  plants;
- **College Raimon** - campus/street props (bollard, vending machine, street
  light, parasol, beach chair, trash bin).

They replace the native procedural trees, palms, bushes, ferns, flowers and
grass clumps, the remaining procedural street furniture, and the simple
rocks/outdoor props. Interior furniture and most outdoor props already use
curated CC0 assets from Poly Haven / Sketchfab (see
[Docs/FAB_ASSET_AUDIT.md](FAB_ASSET_AUDIT.md)); those are left as-is.

These are licensed marketplace packs. They are **not committed** and must never
be redistributed. The game falls back to the native procedural vegetation, the
curated CC0 props and the procedural street furniture when the folders are
absent, so a fresh checkout still builds and runs.

## Install

Close Unreal, then copy the nature/prop folders from the donor project:

```powershell
python Tools/import_fab_nature.py
# or
python Tools/import_fab_nature.py --source "D:\Fab\Content"
# replace an existing copy
python Tools/import_fab_nature.py --force
```

The destinations are gitignored:

```text
DuelAcademyIsland/Content/StyleHex_Studio/
DuelAcademyIsland/Content/Stylized_PBR_Nature/Foliage/
DuelAcademyIsland/Content/Stylized_PBR_Nature/Rocks/
DuelAcademyIsland/Content/TropicalGardenLounge/Vegetation/
DuelAcademyIsland/Content/TropicalGardenLounge/Misc/
DuelAcademyIsland/Content/CollegeRaimon/
```

`DefaultGame.ini` lists them under `DirectoriesToAlwaysCook`; remove those lines
if you do not install the packs.

## Rebuild the island

The swap happens in the **Unreal level build**, not in the Blender layout
stage. `layout.json` keeps the native vegetation/prop groups; when the level is
placed, `duel_academy/level.py` checks the local packs and swaps the render
meshes. Installing the packs therefore only needs a level rebuild:

```powershell
UnrealEditor-Cmd DuelAcademyIsland.uproject -ExecutePythonScript="C:/dev/GX/DuelAcademyIsland/Content/Python/rebuild_level_cli.py" `
  -unattended -nosplash -nullrhi -NoSourceControl
```

A full **Duel Academy > Build Island** run also picks up the packs. If the
packs are absent, the same build keeps the native procedural trees/grass, the
curated CC0 props and the procedural street furniture; `layout.json` does not
need to be regenerated for either case.

Regenerate `layout.json` with Blender only when the island layout itself
changes:

```powershell
"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --factory-startup `
  --python Tools\build_island_blender.py -- layout
```

## What is replaced

`Tools/dai/fab_nature.py` maps each native catalog name to one or more Fab
variants and a native target height:

| Native asset | Target height | Fab variants |
| --- | ---: | --- |
| `SM_PalmTree_A/B` | 11 / 8 m | Tropical `SM_PlamTree` |
| `SM_BroadTree_A` | 12 m | StyleHex broadleaf/birch, PBR common |
| `SM_BroadTree_B` | 16 m | StyleHex broadleaf 1/2 |
| `SM_BroadTree_C` | 6 m | StyleHex birch 1/2, PBR common 03 |
| `SM_PineTree_A` | 14 m | PBR pine 1/2 |
| `SM_DeadTree_A` | 9 m | Tropical `SM_Cypress02` (dark; the packs have no leafless tree) |
| `SM_Bush_A/B` | 1.6 / 1.0 m | StyleHex bushes 1/2, PBR bush |
| `SM_FlowerBush_*` | 0.5 m | StyleHex flower clumps 1–3 |
| `SM_Fern_A` | 0.45 m | PBR fern |
| `SM_GrassClump_A` | 0.6 m | StyleHex grass clumps 1–5, PBR grass/clover |

`Tools/dai/fab_props.py` covers the remaining procedural / simple instance
groups:

| Native asset | Target height | Fab variants |
| --- | ---: | --- |
| `SM_Rock_A/B/C/D` | 1.4 / 1.05 / 5.2 / 3.5 m | StyleHex stones, PBR rocks |
| `SM_CliffRock_A` | 12.6 m | PBR rock 04/03 |
| `SM_VolcanicRock_A` | 3.6 m | PBR rock 04/01 |
| `SM_Pebbles_A` | 0.3 m | StyleHex stone 1 |
| `SM_Bollard` | 0.7 m | College Raimon `SM_ao336_lv1` |
| `SM_Planter` | 1.2 m | Tropical `SM_PlamPlant02/01` |
| `SM_VendingMachine` | 1.9 m | College Raimon `SM_ao127_01` |
| `SM_LampPost` | 5.0 m | College Raimon `SM_ao017_polelight_1_lv1` (rolled upright) |
| `SM_TrashBin` | 1.0 m | College Raimon `SM_ao059_nosdw_lv1` |
| `SM_BeachUmbrella` | 2.6 m | College Raimon `SM_ao130_nosdw_parasol_lv1` |
| `SM_BeachChair` | 0.9 m | College Raimon `SM_chair01` |

The native names stay in `layout.json`. Placement, NPC clearance, collision
proxies and the footprint checker keep using the procedural proportions they
were tuned for; only the render mesh changes, at level-build time. Each
instance is scaled from the native target height to the Fab mesh's measured
height, and its pivot is moved so the mesh's lowest point sits on the same
ground line as the native mesh. Variants are assigned round-robin per native
group, deterministically. The prop swapper preserves the native group's
collision/cull/shadow flags and supports a per-asset pitch/yaw/roll offset (the
street-light mesh is authored lying along -Y and is rolled upright). Instances
the scatter bedded into a slope (boulders, logs, plants leaning a little with
the ground) carry their pitch and roll in `layout.json`; both swappers keep it.

The four instance groups that still have no suitable Fab mesh are the three
`SM_Flagpole_*` groups and `SM_DuelDummy`; they stay procedural. See
[Docs/FAB_ASSET_AUDIT.md](FAB_ASSET_AUDIT.md) for the full audit and free
downloadable alternatives.

## Tuning

- **A tree/rock/prop is too big/small:** edit the `target` height for that
  native name in `Tools/dai/fab_nature.py` or `Tools/dai/fab_props.py`, then
  rebuild the level (the swap is applied there).
- **A different Fab mesh:** add it to `ASSETS` and to the variant list in
  `REPLACE`. Use its Unreal object path (`/Game/.../SM_Foo.SM_Foo`).
- **Source mesh measurements:** run

  ```powershell
  UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript `
    -script=Tools/measure_fab_nature.py -unattended -nosplash -nullrhi
  ```

  and copy the reported height/bottom values into `ASSETS`. The script writes
  `Saved/fab_nature_bounds.json` and `Saved/fab_props_bounds.json`.

## Notes

- The packs' materials are kept as authored (stylized PBR with the packs' own
  foliage shading); the project does not force the character cel material onto
  them.
- The terrain ground texture is unchanged. Only the vegetation, rock and
  selected prop meshes are swapped.
- The abandoned dorm's dead trees use a dark cypress because none of the
  installed packs contains a leafless tree.
- `Tools/import_fab_nature.py` copies only the vegetation subset of the Tropical
  Garden Lounge pack, not its 5 GB interior/prop library. It copies the full
  College Raimon content folder for the street-prop swap.
- Interior furniture and most outdoor props already use curated CC0 assets from
  Poly Haven / Sketchfab; they are not procedural and are left as-is.
- The Stylized PBR Nature rock material logs a one-time
  `needed to set usage flag InstancedStaticMeshes` reminder because the level
  uses a HISM scatter. If you cook a build, enable **Used with Instanced Static
  Meshes** on `MI_R_Rock_1-5` (or its parent material) so the Fab rocks render
  in the packaged build.
