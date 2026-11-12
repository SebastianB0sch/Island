# Water

The sea, the lake, the rivers and every fountain share one water model. The pipeline defines it
(`Tools/dai/water.py`, `Tools/dai/terrain.py`), writes it to `SourceAssets/Data/water.json` and a handful of
textures, and both the Unreal materials and the C++ gameplay code read the same numbers - so a boat rides the
wave that is drawn under it.

> **Status.** The pipeline half (terrain, meshes, textures, data) was built and rendered in Blender. The
> Unreal half (materials, C++) was written without an engine at hand: the wave maths is compiled outside the
> engine and checked against a Python reference, and the material graphs are built against a recording stand-in
> for the `unreal` module (`Tools/tests/test_water_engine.py`), but nothing has been compiled or looked at in
> Unreal yet. See [Not yet verified in the engine](#not-yet-verified-in-the-engine).

## Waves

A wave set is up to six Gerstner waves. Wave *i* has a unit direction `D`, wavelength `L`, amplitude `A`,
choppiness `s` (0..1), phase speed `c` and phase `phi`:

    k = 2 pi / L        omega = k c        theta = k D.p - omega t + phi
    offset.xy = sum D (s A m) cos(theta)
    offset.z  = sum A m sin(theta)
    normal    = normalize(-sum D.x k A m cos, -sum D.y k A m cos, 1 - sum k s A m sin)
    fold      = sum k s A m sin(theta)                 (whitecaps where it nears its maximum)

`p` is the resting position of a point of the surface, `t` game time, `m` the wave mask there. Because the waves
also move the water sideways, the height at a fixed spot is found by inverting the displacement
(three fixed-point steps `q = p - offset.xy(q)`).

| Set | Waves | Wavelengths | Amplitudes | Where |
|---|---|---|---|---|
| ocean | 6 | 24 - 78 m | 10 - 30 cm (about 1.3 m significant height in open water) | `M_Ocean` |
| lake | 3 | 6 - 11 m | 2 - 4 cm | `M_LakeWater` |

Only waves the meshes can carry are in the sets - at least four grid cells per wavelength (5 m cells at sea,
1.5 m on the lake). Everything shorter lives in the normal maps.

The same formula exists three times, deliberately small each time:

| Where | For |
|---|---|
| `Tools/dai/water.py` (`offset`, `height_at`, `normal`) | reference, tests |
| `Public/DAWaterWaves.h` (`DAWater::Evaluate`, `FWaveField`) | buoyancy, swimming, wading |
| `M_DA_Water` in `Content/Python/duel_academy/materials.py` | what is drawn |

## Island-wide maps

Written by the terrain stage, in the terrain's own layout (row 0 = north):

| Texture | Channels |
|---|---|
| `T_WaveMask` (256²) | R = wave amplitude scale. 1 in deep open water, small in the shallows, in coves and in the harbour basin behind the breakwater, 0 at the edge of the terrain domain (the coarse far sea stays flat). The same bytes are in `water.json` for the C++ side. |
| `T_WaterShore` (2048², RGBA) | R = water depth (0 at the waterline .. 1 at 8 m), G = distance from the shore into the water (1 at 40 m), B = submerged (sea, lake, river, pond), A = wet band on land (1 at the waterline .. 0 four metres up the bank) |

`T_WaterShore` drives the shoreline foam, the depth tint of the water, and - in the terrain material - the
caustics under shallow water and the dark wet band along every bank and beach.

## Tileable textures

`Tools/dai/water.py build_textures` (part of the `textures` stage):

| Texture | Content |
|---|---|
| `T_WaterDetailN` | wind ripples and capillary waves from a Phillips spectrum (two crossing wave trains) |
| `T_WaterFoam` | R thick foam, G lacy foam network, B fine bubbles |
| `T_Caustics` | the light net on a shallow bed |
| `T_Ripples` | rain-ring data (R ring profile, GB direction, A time offset) for fountain basins and pools |

## Materials

| Master | Palette kind | Used by |
|---|---|---|
| `M_DA_Water` | `water` | sea, lake: Gerstner displacement, analytic normal + layered detail normals, depth colour, shoreline foam with lapping bands, whitecaps |
| `M_DA_PoolWater` | `pool` | fountain basins, hot springs, interior pools: still water with rain rings |
| `M_DA_River` | `river` | rivers, the creek, the pond: flows along the mesh's UV0.v, foam in the rapids and along the banks |
| `M_DA_Waterfall` | `waterfall` | the falls |
| `M_DA_WaterFlow` | `flow` | fountain sheets, jets and foam |

Palette keys are documented at the top of `Tools/dai/palette.py`.

## Meshes

* `SM_Ocean` - a 5 m grid over the whole terrain domain wherever there is sea, then rings of doubling cell
  size out to 20 km, stitched 2:1 so the displaced part has no T-junctions.
* `SM_LakeSurface` - a 1.5 m grid over the lake and its arms.
* `SM_River_<Name>` - a 1.5 m grid over each river (a grid cannot fold over itself in a tight bend or a round
  pond the way a ribbon does). UV0 = (metres from the left bank, metres downstream), UV1 = (foam, bank).

## Rivers

`config.RIVERS` lists centre lines and widths only. The terrain stage does the rest (`terrain.py`
`river_profiles`, `carve_rivers`):

* the water level is the highest a river can have - just below the ground along its line, never rising
  downstream - so it pools on flats, runs down slopes as rapids and cuts a gorge only where a ridge is in the way;
* the channel is cut after everything else: a flat bed, banks at about 30 degrees, a low levee where the
  ground beside it lies below the water;
* wherever a path crosses, the road profile is held clear of the water and a bridge record is written; the
  layout stage builds the bridge (`assets/bridges.py`: stone arches under the paved roads, timber trestles on
  the trails).

Today: the **Academy River** (lake -> past the academy and Millbrook -> Willow Pond -> the sea below the gym,
1.9 km) and the **Forest Creek** (a spring in the forest -> the east coast, 0.7 km), with six bridges.

## The lake's arms

`config.LAKE_INLETS`: an arm of the lake is a polyline with the water's half width at each point, from its
head out into the open lake (today one: the inlet that reaches the girls' dorm jetty). `shoreline.inlet_q`
gives it as the lake's own normalised radius, which the terrain stage merges with the ellipse's - one
shoreline, one water raster, the same sand and bank shaping - while the arm keeps a bed of its own (`depth`
along the middle) and banks `bank` metres wide per unit of q. `water.json` lists the arms under `inlets`;
the engine's lake test is the ellipse, so `level.py` adds them to the island manager like the rivers: still
water at the lake's level, without the lake's wavelets.

## Gameplay

* `ADAIslandManager::QueryWater` / `GetWaterSurfaceZ` answer for any location: river, lake or sea, waves
  included. Rivers and ponds are wading water (never deep enough to swim); the swimmer rides the swell.
* `ADAFloatingActor` samples the surface at bow, stern, port and starboard and follows heave, pitch and roll
  through a damped spring - the ferry in the sheltered basin barely moves, a buoy outside it bobs.
* `ADAEmitter` kind `Jet` throws ballistic droplets along a fountain jet's path and splashes where they land;
  `Fireflies` drift along the banks at night.

## Tuning

* Wave sets: `OCEAN_WAVES` / `LAKE_WAVES` in `Tools/dai/water.py`, then `python Tools/build_island.py terrain`
  (rewrites `water.json`) and rebuild the materials and the level in the editor.
* Calmer or rougher coast: `wave_mask` in the same file.
* A new river: add it to `config.RIVERS`, run `terrain meshes layout`. A new arm of the lake: add it to
  `config.LAKE_INLETS`, the same stages.

## Not yet verified in the engine

Written carefully, but unseen in Unreal - check these first if something looks wrong:

* **The lake's arms in the water query.** `level.py` adds `water.json` "inlets" with `add_river`; standing
  in the girls' dorm inlet should report water at 30 m (a river body). If the player walks on the bed
  there, the arms did not reach the manager.

* **Foam on single layer water.** Foam is fed to base colour with *opacity as its coverage*. If the engine
  ignores opacity on this shading model, the foam simply does not show.
* **Sine / cosine nodes.** The wave graph sets their period to 1 and feeds cycles. If the property is ignored
  the waves are off by a factor of 2 pi.
* **Flow direction of rivers.** Assumes the FBX importer flips V. If a river runs uphill, negate `Flow`
  (`M_River` in `palette.py`) or set `BankFlip` to 0 if the bank foam sits mid-stream.
* **Clock.** Buoyancy uses `UWorld::GetTimeSeconds()`, the material its Time node. If they are not the same
  clock, floating things drift out of phase with the waves under them.
* The new C++ (`DAWaterWaves.h` aside) only passed a syntax check against hand-written stubs.
