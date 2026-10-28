# Credits

Duel Academy Island is an unofficial, non-commercial fan project inspired by *Yu-Gi-Oh! GX*.
Yu-Gi-Oh! and all related names are trademarks of their respective owners; no copyrighted
game or anime assets are included. Buildings are original interpretations modelled by the
procedural pipeline in `Tools/`.

## Third-party assets

All third-party art below is **CC0 / public domain** or **CC-BY** (attribution given here).
Every folder keeps a `SOURCE.txt` with the download URLs, license evidence and file hashes.
Paths are relative to `Tools/thirdparty/`.

| Asset folder | Author | License | Source | Used for |
|---|---|---|---|---|
| `3dtextures/Water_001` | 3dtextures.me (Joao Paulo) | CC0 (public domain) as stated by the hosting repo | <https://3dtextures.me/> | texture WaterNormal |
| `ambientcg/Fabric034` | ambientCG (Lennart Demes) | CC0 1.0 Universal | <https://ambientcg.com/view?id=Fabric034> | texture Fabric |
| `ambientcg/Ground092A` | ambientCG (Lennart Demes) | CC0 1.0 Universal | <https://ambientcg.com/view?id=Ground092A> | terrain layer Sand, texture Sand |
| `ambientcg/Marble012` | ambientCG (Lennart Demes) | CC0 1.0 Universal | <https://ambientcg.com/view?id=Marble012> | texture Marble |
| `polyhaven/hdri/kloofendal_48d_partly_cloudy_puresky` | Greg Zaal (photography), Jarod Guest (sky processing) / Poly Haven | CC0 1.0 Universal (public domain dedication) | <https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky> | sky (day) |
| `polyhaven/hdri/qwantani_night_puresky` | Greg Zaal (photography), Jarod Guest (processing) / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/qwantani_night_puresky> | sky (night) |
| `polyhaven/hdri/qwantani_sunset_puresky` | Greg Zaal (photography), Jarod Guest (processing) / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/qwantani_sunset_puresky> | sky (sunset) |
| `polyhaven/textures/brown_planks_09` | Poly Haven artist (credited on the asset page) | CC0 1.0 Universal | <https://polyhaven.com/a/brown_planks_09> | texture Planks |
| `polyhaven/textures/clay_roof_tiles_02` | Poly Haven artist (credited on the asset page) | CC0 1.0 Universal | <https://polyhaven.com/a/clay_roof_tiles_02> | texture RoofTiles |
| `polyhaven/textures/cobblestone_floor_08` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/cobblestone_floor_08> | terrain layer Paving |
| `polyhaven/textures/concrete` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/concrete> | texture Concrete |
| `polyhaven/textures/corrugated_iron` | Poly Haven artist (credited on the asset page) | CC0 1.0 Universal | <https://polyhaven.com/a/corrugated_iron> | texture Corrugated |
| `polyhaven/textures/damp_beach_sand` | Poly Haven artist (credited on the asset page) | CC0 1.0 Universal | <https://polyhaven.com/a/damp_beach_sand> | terrain layer WetSand |
| `polyhaven/textures/dark_rock` | Amal Kumar / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/dark_rock> | terrain layer Ash |
| `polyhaven/textures/dirt_floor` | eye-candy.xyz / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/dirt_floor> | terrain layer Dirt, texture Dirt |
| `polyhaven/textures/distressed_painted_planks` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/distressed_painted_planks> | texture Siding |
| `polyhaven/textures/forest_leaves_03` | Dimitrios Savva, Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/forest_leaves_03> | terrain layer ForestFloor |
| `polyhaven/textures/leafy_grass` | Charlotte Baglioni / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/leafy_grass> | terrain layer Grass, texture Grass |
| `polyhaven/textures/long_white_tiles` | Jenelle van Heerden, Sergej Majboroda / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/long_white_tiles> | texture FloorTiles |
| `polyhaven/textures/painted_plaster_wall` | Amal Kumar / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/painted_plaster_wall> | texture Plaster |
| `polyhaven/textures/rectangular_paving` | Poly Haven artist (credited on the asset page) | CC0 1.0 Universal | <https://polyhaven.com/a/rectangular_paving> | texture Paving |
| `polyhaven/textures/red_brick_03` | Poly Haven artist (credited on the asset page) | CC0 1.0 Universal | <https://polyhaven.com/a/red_brick_03> | texture Bricks |
| `polyhaven/textures/rock_boulder_dry` | Dimitrios Savva (photography), Rico Cilliers (processing) / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/rock_boulder_dry> | terrain layer Rock, texture Rock |
| `polyhaven/textures/white_plaster_02` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/white_plaster_02> | texture Grunge |

## Tools

- [Blender](https://www.blender.org/) (GPL) as the `bpy` Python module - modelling, import, FBX export, Cycles renders
- [glTF-Transform](https://gltf-transform.dev/) (MIT) - meshopt decompression of glTF downloads
- [EZ-Tree](https://github.com/dgreenheck/ez-tree) (MIT) by Daniel Greenheck - procedural broadleaf / pine tree generation
- NumPy, SciPy, Pillow - terrain, textures and audio synthesis
- Unreal Engine 5.8 - Lumen, Nanite, Enhanced Input, editor Python
