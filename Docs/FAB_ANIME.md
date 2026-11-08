# Fab Anime Character Pack (local-only)

The island's native cast is built from VRoid samples with permissive terms. The
**Fab Anime Character Pack (Legacy)** is different: it is licensed marketplace
content, so it is **not committed** and must never be redistributed.

The game uses it as an optional extra layer for ambient NPCs:

- `UDAFabAnimeComponent` (`Source/DuelAcademyIsland/Public/DAFabAnimePuppet.h`)
  spawns the pack's `bp_AnimeCharacter` as a cosmetic puppet, swaps the
  head/hair/top/bottom meshes, tints the hair and casual clothes, and feeds the
  host's velocity to the pack's locomotion blueprint.
- The puppet is scaled to the host's **visible standing height**
  (`UDAAvatarComponent::GetStandingHeight()`, including hair), so the pack's
  ~200 cm male / ~187 cm female bodies match the GX cast's real 153-186 cm
  heights and keep the ambient NPCs' deterministic ±5 % size variation. The
  scale is measured from the assembled head/hair/top/bottom silhouette and is
  applied to the body-part components, not the actor, so the feet stay on the
  host's floor and the outline children inherit it.
- The puppet's movement component stays in `MOVE_Walking` (but is not ticked) so
  the pack's locomotion ABP selects Idle/Walk/Run instead of its "In Air" state.
  Each frame the host's velocity is copied to it.
- The pack's outline shells (`SkeletalMeshComponent_0..3`) are paired with their
  animated body part by parent / existing leader pose, use it as their leader pose
  and get the matching swapped mesh. They no longer keep the default male meshes on
  female looks.
- If the pack is absent, `ActivateLook()` fails closed and the NPC keeps its native
  GX cast avatar. A fresh checkout therefore still runs.

The pack's idle / walk / run takes can also be retargeted onto the **native GX
cast**, replacing the procedural gait clips for Jaden, the regulars and the
named students. See [Native cast locomotion](#native-cast-locomotion).

## Install

Close Unreal, then copy the pack from your Fab library (or from the donor
project's `Content/AnimeCharacters`):

```powershell
python Tools/import_fab_anime.py
# or
python Tools/import_fab_anime.py --source "D:\Fab\AnimeCharacterPack"
```

The destination is `DuelAcademyIsland/Content/AnimeCharacters`, which is
excluded by `.gitignore`. `DefaultGame.ini` also lists it under
`DirectoriesToAlwaysCook`; remove that line if you do not install the pack.

The editor build does not import the pack: the assets are already `.uasset`
files, so just restart the editor and rebuild the level
(`Duel Academy → Build Island` / `Rebuild Level Only`).  For a fast NPC-only
refresh of an existing level, run:

```powershell
UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript -script=Tools/apply_world_npc_data.py -unattended -nosplash -nullrhi
```

## Verify

The headless editor check loads the Blueprint, spawns a temporary NPC, and
activates every look.  It verifies the requested head/hair/top/bottom meshes, that
the puppet is scaled to the host avatar's standing height and stands on the host
floor, that every outline shell uses its body part's mesh and leader pose, the
grounded movement state, look switching and native-avatar restore.

```powershell
UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript -script=Tools/test_fab_anime.py -unattended -nosplash -nullrhi
```

A healthy run logs `FabAnimeTest: PASS ALL` for all eight looks.

The native-cast retarget has its own headless check. It skips on a fresh
checkout (no local retargeted FBXs) and otherwise verifies every group's
`A_Anime_<Group>_Idle/Walk/Run` clip: the cast skeleton, the expected durations,
the long Walk (> 1.05 s) / short Run (< 0.68 s) pair that `SetupCast` uses to
detect Fab locomotion, and the normalised pelvis track.

```powershell
UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript -script=Tools/test_fab_locomotion.py -unattended -nosplash -nullrhi
```

A healthy run logs `FabLocomotionTest: PASS ALL` (or `SKIP` when the local
retargeted takes are not installed).

## Looks

`roster.py` assigns Fab looks to roughly one in seven male and one in four
female ambient students. The schedule crowd rows in `spawns.json` also use a
few. The ids are:

| Id | Body | Hair | Outfit |
|---|---|---|---|
| `fab_male_a` | male average | M1 | T-shirt / trousers |
| `fab_male_b` | male average | M2 | tank / shorts |
| `fab_male_c` | male average | M1 | tank / trousers |
| `fab_male_d` | male average | M2 | T-shirt / shorts |
| `fab_female_a` | female average | F1 | tank / skirt |
| `fab_female_b` | female average | F2 | turtleneck / skirt |
| `fab_female_c` | female average | F2 | tank / shorts |
| `fab_female_d` | female average | F1 | turtleneck / shorts |

The face material (two per gender) and hair colour are part of each look. The
casual top and bottom take the NPC's dorm colour so they sit alongside the
uniformed cast.

## Native cast locomotion

The Fab anime rig is an A-pose UE4-Mannequin skeleton while the GX cast is a
T-pose skeleton whose leg / spine bone tails point **up**. Copying local
rotations folds the legs and splays the arms, so `Tools/dai/anime/fab.py` solves
each frame from the real limb **segment direction** (joint to child joint), keeps
the cast's own bone lengths, and scales the source pelvis travel by the
leg-length ratio.

The pipeline is three local-only steps:

```powershell
# 1. export the pack's takes from Unreal (once per pack install)
UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript `
  -script=Tools/export_fab_locomotion.py -unattended -nosplash -nullrhi

# 2. retarget onto every cast skeleton group (Blender)
python Tools/retarget_fab_anime.py

# 3. install the retargeted A_Anime_<Group>_Idle/Walk/Run takes
UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript `
  -script=Tools/apply_fab_locomotion.py -unattended -nosplash -nullrhi
```

The intermediate FBXs live in `Tools/thirdparty/fab_anime/` and are **gitignored**;
they are derived from licensed content. `apply_fab_locomotion.py` imports the
takes over the existing `A_Anime_<Group>_Idle/Walk/Run` assets and normalises the
baked pelvis track (the cast skeleton keeps its 100x root unit). Without the
retargeted files the procedural gait takes stay in place and nothing changes.

A full cast rebuild (`Duel Academy → Build Island`, `python Tools/build_island.py cast`)
regenerates the gait takes, so `importer.py` now re-applies these local Fab takes
automatically when `Tools/thirdparty/fab_anime/retargeted` exists (step 3 remains
useful for refreshing an existing level without a full rebuild). The retarget
transfers leaf-bone rotation (head, hands, toes) in the parent frame, so the
cast's head faces forward and the hands keep their natural twist. The measured
planted-foot speeds are about 1.33-1.58 m/s walk and 5.55-6.59 m/s for the sprint
take (per skeleton group); `UDAAvatarComponent::SetupCast` detects the long-walk /
short-run pair and uses those per-group reference speeds, so the feet no longer skate
at the old 1.30 / 2.65 m/s guess. The gait fallback keeps its original 150 / 420 cm/s
reference, so a machine without the pack behaves exactly as before. The Fab
puppets keep using the pack's own `abp_Human` and are unaffected by the retarget.

## Licence

The Fab Anime Character Pack is licensed to the project owner through Epic
Games' Fab marketplace. It is **not** covered by the project's source licence
and must not be committed, packaged for redistribution, or shared. The local
`SOURCE.txt` written by the import script records this. The C++ component and
the look ids are original project code/data.
