# Credits

Duel Academy Island is an unofficial, non-commercial fan project inspired by *Yu-Gi-Oh! GX*.
Yu-Gi-Oh! and all related names are trademarks of their respective owners. The island's buildings,
terrain and vegetation are original interpretations modelled by the procedural pipeline in `Tools/`.
The anime cast is the project's own work too: every character is modelled from scratch by the generator in
`Tools/dai/anime/atelier` (original faces, hair and outfits); no third-party character model is used.

## Duel data and portraits

The playable duel database (`DuelAcademyIsland/Content/Data/`) contains card names, rules text, card
scans and starter-deck/fusion data ported from the reference UE5 duel engine. Yu-Gi-Oh! card names,
text and artwork are the property of Konami/Shueisha; they are included here for a non-commercial,
fan-made project and must not be redistributed as a commercial product. The scans are the same
YGOPRODeck-sourced images used by the reference project.

`Content/Data/Portraits/` contains the reference project's character busts and expression frames
(Konami *Duel Links* renders, including the official expression cut-ins for the regulars), plus
portraits and expression frames rendered locally from the project's own cast
(`Tools/render_portraits.py`) and a few UI icons. The Duel Links renders are fan-project reference
assets and are **not** redistributable. The generated portraits and expressions come from the
project's own cel-shaded models, described below.

## Local-only licensed content

The optional **Fab nature / prop packs** (StyleHex FREE Stylized Forest Sample, Stylized PBR Nature
foliage and rocks, the Tropical Garden Lounge vegetation, and the College Raimon environment kit) are
licensed marketplace content. They are installed locally with `Tools/import_fab_nature.py`, excluded from
git, and **not redistributed**. Without them the game uses the native procedural vegetation, the curated
CC0 rocks/props and the remaining procedural street furniture. See
[Docs/FAB_NATURE.md](Docs/FAB_NATURE.md) and [Docs/FAB_ASSET_AUDIT.md](Docs/FAB_ASSET_AUDIT.md).

## Third-party assets

All third-party art below is **CC0 / public domain**, **CC-BY** (attribution given here).
Every folder keeps a `SOURCE.txt` with the download URLs, license evidence and file hashes.
Paths are relative to `Tools/thirdparty/`.

| Asset folder | Author | License | Source | Used for |
|---|---|---|---|---|
| `3dtextures/Water_001` | Joao Paulo ("Katsukagi") / 3dtextures.me | CC0 1.0 (3dtextures.me dedicates all its textures to CC0; stated by the hosting repo and corroborated independently) | <https://3dtextures.me/tag/water/> | texture WaterNormal |
| `ambientcg/Fabric034` | ambientCG (Lennart Demes) | CC0 1.0 Universal | <https://ambientcg.com/view?id=Fabric034> | texture Fabric |
| `ambientcg/Ground092A` | ambientCG (Lennart Demes) | CC0 1.0 Universal | <https://ambientcg.com/view?id=Ground092A> | terrain layer Sand, texture Sand |
| `ambientcg/Marble012` | ambientCG (Lennart Demes) | CC0 1.0 Universal | <https://ambientcg.com/view?id=Marble012> | texture Marble |
| `eztree/trees` | Daniel Greenheck (EZ-Tree generator); bark textures Poly Haven / TextureCan | MIT (generator + bundled leaf textures); bark textures CC0 1.0 | <https://github.com/dgreenheck/ez-tree> | SM_BroadTree_A, SM_BroadTree_B, SM_Bush_B, SM_DeadTree_A, SM_PineTree_A |
| `googlepoly/fishing_trawler` | Poly by Google (Google Poly archive) | CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/) - ATTRIBUTION REQUIRED. | <https://poly.pizza/m/1ZuSXvhkRg_> | SM_FishingBoat |
| `khronos/Lantern` | Microsoft (artist: sbtron) | CC0-1.0 | <https://github.com/KhronosGroup/glTF-Sample-Assets/tree/main/Models/Lantern> | SM_LampPost_Old |
| `polyhaven/hdri/kloofendal_48d_partly_cloudy_puresky` | Greg Zaal (photography), Jarod Guest (sky processing) / Poly Haven | CC0 1.0 Universal (public domain dedication) | <https://polyhaven.com/a/kloofendal_48d_partly_cloudy_puresky> | sky (day) |
| `polyhaven/hdri/qwantani_night_puresky` | Greg Zaal (photography), Jarod Guest (processing) / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/qwantani_night_puresky> | sky (night) |
| `polyhaven/hdri/qwantani_sunset_puresky` | Greg Zaal (photography), Jarod Guest (processing) / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/qwantani_sunset_puresky> | sky (sunset) |
| `polyhaven/models/ArmChair_01` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/ArmChair_01> | SM_Int_Armchair |
| `polyhaven/models/Barrel_01` | Jorge Camacho | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/Barrel_01> | SM_Barrel |
| `polyhaven/models/Camera_01` | Rajil Jose Macatangay | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/Camera_01> | SM_Int_Camera |
| `polyhaven/models/CashRegister_01` | Joe Seabuhr | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/CashRegister_01> | SM_Int_Register |
| `polyhaven/models/Chandelier_01` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/Chandelier_01> | SM_Int_ChandelierB |
| `polyhaven/models/Chandelier_02` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/Chandelier_02> | SM_Int_Chandelier |
| `polyhaven/models/ClassicConsole_01` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/ClassicConsole_01> | SM_Int_Console |
| `polyhaven/models/ClassicNightstand_01` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/ClassicNightstand_01> | SM_Int_Nightstand |
| `polyhaven/models/GothicBed_01` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/GothicBed_01> | SM_Int_GrandBed |
| `polyhaven/models/GothicCabinet_01` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/GothicCabinet_01> | SM_Int_Wardrobe |
| `polyhaven/models/GreenChair_01` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/GreenChair_01> | SM_Int_GreenChair |
| `polyhaven/models/Ottoman_01` | Caspian Fortune | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/Ottoman_01> | SM_Int_Ottoman |
| `polyhaven/models/Rockingchair_01` | Jorge Camacho | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/Rockingchair_01> | SM_Int_RockingChair |
| `polyhaven/models/SchoolChair_01` | Ethan Place | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/SchoolChair_01> | SM_Int_SchoolChair |
| `polyhaven/models/SchoolDesk_01` | Ethan Place | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/SchoolDesk_01> | SM_Int_SchoolDesk |
| `polyhaven/models/Sofa_01` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/Sofa_01> | SM_Int_Sofa |
| `polyhaven/models/Television_01` | Gabriel Radić | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/Television_01> | SM_Int_TV |
| `polyhaven/models/Ukulele_01` | Joseph Burgan | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/Ukulele_01> | SM_Int_Ukulele |
| `polyhaven/models/WetFloorSign_01` | Fran Calvente | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/WetFloorSign_01> | SM_Int_WetFloor |
| `polyhaven/models/WoodenTable_01` | Ethan Place | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/WoodenTable_01> | SM_Int_Table |
| `polyhaven/models/alarm_clock_01` | Yann Kervran, James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/alarm_clock_01> | SM_Int_AlarmClock |
| `polyhaven/models/anthurium_botany_01` | Rob Tuytel (scanning), Rico Cilliers (modeling) (Poly Haven) | CC0 1.0 Universal (public domain). Attribution not required (credit appreciated). | <https://polyhaven.com/a/anthurium_botany_01> | SM_Bush_A |
| `polyhaven/models/antique_ceramic_vase_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/antique_ceramic_vase_01> | SM_Int_VaseA |
| `polyhaven/models/bananas` | Alexander Shulha | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/bananas> | SM_Int_Bananas |
| `polyhaven/models/bar_chair_round_01` | Dairon Sanchez | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/bar_chair_round_01> | SM_Int_BarStool |
| `polyhaven/models/baseball_bat` | Enrique Martín | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/baseball_bat> | SM_Int_BaseballBat |
| `polyhaven/models/binder_notebook` | DaDrood | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/binder_notebook> | SM_Int_Binder |
| `polyhaven/models/binoculars` | Derek Wight | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/binoculars> | SM_Int_Binoculars |
| `polyhaven/models/book_encyclopedia_set_01` | John Malcolm | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/book_encyclopedia_set_01> | SM_Int_Books |
| `polyhaven/models/boulder_01` | Rico Cilliers: All (Poly Haven) | CC0 1.0 Universal (public domain dedication). No attribution required; credit kept voluntarily. | Poly Haven "boulder_01" - https://polyhaven.com/a/boulder_01  (polyhaven.com / dl.polyhaven.org are blocked from this container) | SM_Rock_A |
| `polyhaven/models/brass_candleholders` | Tina | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/brass_candleholders> | SM_Int_Candelabra |
| `polyhaven/models/brass_goblets` | Tina | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/brass_goblets> | SM_Int_Goblets |
| `polyhaven/models/brass_pot_01` | Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/brass_pot_01> | SM_Int_Pot |
| `polyhaven/models/brass_vase_01` | Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/brass_vase_01> | SM_Int_VaseC |
| `polyhaven/models/bronze_whale_statue` | Tina | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/bronze_whale_statue> | SM_Int_WhaleStatue |
| `polyhaven/models/caged_hanging_light` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/caged_hanging_light> | SM_Int_CageLight |
| `polyhaven/models/calathea_orbifolia_01` | Rob Tuytel (scanning), Rico Cilliers (modeling) (Poly Haven) | CC0 1.0 Universal (public domain). Attribution not required (credit appreciated). | <https://polyhaven.com/a/calathea_orbifolia_01> | - |
| `polyhaven/models/cardboard_box_01` | Rahul Chaudhary | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/cardboard_box_01> | SM_Int_Box |
| `polyhaven/models/ceiling_fan` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/ceiling_fan> | SM_Int_CeilingFan |
| `polyhaven/models/ceramic_vase_02` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/ceramic_vase_02> | SM_Int_VaseB |
| `polyhaven/models/chess_set` | Riley Queen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/chess_set> | SM_Int_Chess |
| `polyhaven/models/chinese_armchair` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/chinese_armchair> | SM_Int_ChineseArmchair |
| `polyhaven/models/chinese_cabinet` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/chinese_cabinet> | SM_Int_ChineseCabinet |
| `polyhaven/models/chinese_chandelier` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/chinese_chandelier> | SM_Int_LanternLamp |
| `polyhaven/models/chinese_screen_panels` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/chinese_screen_panels> | SM_Int_FoldingScreen |
| `polyhaven/models/chinese_stool` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/chinese_stool> | SM_Int_Stool |
| `polyhaven/models/chinese_tea_table` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/chinese_tea_table> | SM_Int_LowTable |
| `polyhaven/models/classic_laptop` | Arrangemonk | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/classic_laptop> | SM_Int_Laptop |
| `polyhaven/models/clipboard` | ProgrammerOnCoffee | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/clipboard> | SM_Int_Clipboard |
| `polyhaven/models/coast_rocks_05` | Rob Tuytel (Poly Haven); game LODs derived by ishtiaq-ahmed-dev/rocket-mission-lab with meshoptimizer (UVs + Poly Haven 1k textures retained) | CC0 1.0 Universal (public domain). No attribution required. | Poly Haven "coast_rocks_05" - https://polyhaven.com/a/coast_rocks_05 (scan has ~0.77M tris at full res) | SM_Rock_D |
| `polyhaven/models/coffee_table_round_01` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/coffee_table_round_01> | SM_Int_CoffeeTable |
| `polyhaven/models/concrete_cat_statue` | Rico Cilliers, Riley Queen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/concrete_cat_statue> | SM_Int_CatStatue |
| `polyhaven/models/croissant` | Greg Zaal, Dario Barresi | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/croissant> | SM_Int_Croissant |
| `polyhaven/models/dartboard` | Satyaki Mandal | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/dartboard> | SM_Int_Dartboard |
| `polyhaven/models/dead_tree_trunk_02` | Jenelle van Heerden (Photography); Rico Cilliers (processing) (Poly Haven) | CC0 1.0 Universal (public domain dedication). No attribution required; credit kept voluntarily. | Poly Haven "dead_tree_trunk_02" - https://polyhaven.com/a/dead_tree_trunk_02  (polyhaven.com / dl.polyhaven.org are blocked from this container) | SM_Driftwood_A |
| `polyhaven/models/desk_lamp_arm_01` | Yann Kervran, Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/desk_lamp_arm_01> | SM_Int_DeskLamp |
| `polyhaven/models/dining_chair_02` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/dining_chair_02> | SM_Int_DiningChair |
| `polyhaven/models/dining_table` | Aron Łyczek | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/dining_table> | SM_Int_DiningTable |
| `polyhaven/models/drawer_cabinet` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/drawer_cabinet> | SM_Int_Drawers |
| `polyhaven/models/dustpan` | Balen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/dustpan> | SM_Int_Dustpan |
| `polyhaven/models/electric_stove` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/electric_stove> | SM_Int_Stove |
| `polyhaven/models/exterior_aircon_unit` | Monsta3D | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/exterior_aircon_unit> | SM_Int_Aircon |
| `polyhaven/models/fancy_picture_frame_01` | Rob Tuytel, Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/fancy_picture_frame_01> | SM_Int_Painting |
| `polyhaven/models/fancy_picture_frame_02` | Rob Tuytel, Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/fancy_picture_frame_02> | SM_Int_PaintingB |
| `polyhaven/models/fern_02` | Rob Tuytel (scanning), Rico Cilliers (modeling) (Poly Haven) | CC0 1.0 Universal (public domain). Attribution not required (credit appreciated). | <https://polyhaven.com/a/fern_02> | SM_Fern_A |
| `polyhaven/models/fire_alarm` | Slinc | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/fire_alarm> | SM_Int_FireAlarm |
| `polyhaven/models/fishermans_hat` | PierreB3D | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/fishermans_hat> | SM_Int_Hat |
| `polyhaven/models/folding_wooden_stool` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/folding_wooden_stool> | SM_Int_FoldingStool |
| `polyhaven/models/food_apple_01` | Oliver Harries | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/food_apple_01> | SM_Int_Apple |
| `polyhaven/models/football` | Amal Kumar | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/football> | SM_Int_Ball |
| `polyhaven/models/gallinera_chair` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/gallinera_chair> | SM_Int_CafeChair |
| `polyhaven/models/gallinera_table` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/gallinera_table> | SM_Int_CafeTable |
| `polyhaven/models/gamepad` | Josh Dean | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/gamepad> | SM_Int_Gamepad |
| `polyhaven/models/grass_medium_01` | Rob Tuytel (photography), Rico Cilliers (modeling) (Poly Haven) | CC0 1.0 Universal (public domain). Attribution not required (credit appreciated). | <https://polyhaven.com/a/grass_medium_01> | SM_GrassClump_A |
| `polyhaven/models/hand_truck` | Mutanzom3D | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/hand_truck> | SM_Int_HandTruck |
| `polyhaven/models/hanging_industrial_lamp` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/hanging_industrial_lamp> | SM_Int_IndustrialLamp |
| `polyhaven/models/hanging_picture_frame_02` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/hanging_picture_frame_02> | SM_Int_Frame |
| `polyhaven/models/hanging_picture_frame_03` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/hanging_picture_frame_03> | SM_Int_FrameC |
| `polyhaven/models/horse_statue_01` | Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/horse_statue_01> | SM_Int_HorseStatue |
| `polyhaven/models/industrial_wall_lamp` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/industrial_wall_lamp> | SM_Int_WallLamp |
| `polyhaven/models/industrial_wall_sconce` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/industrial_wall_sconce> | SM_Int_WallSconce |
| `polyhaven/models/jug_01` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/jug_01> | SM_Int_Jug |
| `polyhaven/models/korean_fire_extinguisher_01` | UM JOORIN | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/korean_fire_extinguisher_01> | SM_Int_Extinguisher |
| `polyhaven/models/lambis_shell` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/lambis_shell> | SM_Int_Shell |
| `polyhaven/models/lemon` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/lemon> | SM_Int_Lemon |
| `polyhaven/models/life_jacket` | PierreB3D | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/life_jacket> | SM_Int_LifeJacket |
| `polyhaven/models/lifebuoy` | Hank Kaamura | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/lifebuoy> | SM_Int_Lifebuoy |
| `polyhaven/models/magnifying_glass_01` | Nazar Borodavka | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/magnifying_glass_01> | SM_Int_Magnifier |
| `polyhaven/models/mantel_clock_01` | Yann Kervran, Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/mantel_clock_01> | SM_Int_MantelClock |
| `polyhaven/models/marble_bust_01` | Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/marble_bust_01> | SM_Int_Bust |
| `polyhaven/models/metal_office_desk` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/metal_office_desk> | SM_Int_OfficeDesk |
| `polyhaven/models/metal_stool_01` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/metal_stool_01> | SM_Int_MetalStool |
| `polyhaven/models/metal_toolbox` | Mateusz Sadek | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/metal_toolbox> | SM_Int_Toolbox |
| `polyhaven/models/metal_trash_can` | GurJas Studios | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/metal_trash_can> | SM_TrashBin |
| `polyhaven/models/mid_century_lounge_chair` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/mid_century_lounge_chair> | SM_Int_LoungeChair |
| `polyhaven/models/modern_arm_chair_01` | Vibrant Nordic | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/modern_arm_chair_01> | SM_Int_OfficeChair |
| `polyhaven/models/modern_ceiling_lamp_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/modern_ceiling_lamp_01> | SM_Int_CeilingLamp |
| `polyhaven/models/modern_coffee_table_01` | Amin | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/modern_coffee_table_01> | SM_Int_CoffeeTableB |
| `polyhaven/models/modern_wooden_cabinet` | Patrik Pangerl | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/modern_wooden_cabinet> | SM_Int_MediaCabinet |
| `polyhaven/models/mountainside` | Dario Barresi: Photography; Rico Cilliers: processing (Poly Haven) | CC0 1.0 Universal (public domain dedication). No attribution required; credit kept voluntarily. | Poly Haven "mountainside" - https://polyhaven.com/a/mountainside  (polyhaven.com / dl.polyhaven.org are blocked from this container) | SM_CliffRock_A |
| `polyhaven/models/ocean_buoy` | Mateusz Sadek | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/ocean_buoy> | SM_Buoy |
| `polyhaven/models/office_notepads` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/office_notepads> | SM_Int_Notepads |
| `polyhaven/models/old_bed_frame` | Luca B | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/old_bed_frame> | SM_Int_OldBed |
| `polyhaven/models/ornate_mirror_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/ornate_mirror_01> | SM_Int_Mirror |
| `polyhaven/models/painted_wooden_bench` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/painted_wooden_bench> | SM_Int_Bench |
| `polyhaven/models/painted_wooden_cabinet` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/painted_wooden_cabinet> | SM_Int_Cabinet |
| `polyhaven/models/painted_wooden_chair_01` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/painted_wooden_chair_01> | SM_Int_WoodChair |
| `polyhaven/models/painted_wooden_nightstand` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/painted_wooden_nightstand> | SM_Int_NightstandB |
| `polyhaven/models/painted_wooden_shelves` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/painted_wooden_shelves> | SM_Int_Shelves |
| `polyhaven/models/painted_wooden_sofa` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/painted_wooden_sofa> | SM_Int_WoodSofa |
| `polyhaven/models/planter_box_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/planter_box_01> | SM_Int_PlanterBox |
| `polyhaven/models/plastic_broom` | L | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/plastic_broom> | SM_Int_Broom |
| `polyhaven/models/plastic_monobloc_chair_01` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/plastic_monobloc_chair_01> | SM_Int_PlasticChair |
| `polyhaven/models/postcard_set_01` | James Ray Cock, Jurita Burger | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/postcard_set_01> | SM_Int_Postcards |
| `polyhaven/models/pot_enamel_01` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/pot_enamel_01> | SM_Int_EnamelPot |
| `polyhaven/models/potted_plant_01` | Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/potted_plant_01> | SM_Int_PottedPlantC |
| `polyhaven/models/potted_plant_02` | Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/potted_plant_02> | SM_Int_PottedPlantB |
| `polyhaven/models/potted_plant_04` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/potted_plant_04> | SM_Int_PottedPlant |
| `polyhaven/models/projector_screen` | PeterM | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/projector_screen> | SM_Int_ProjectorScreen |
| `polyhaven/models/rock_09` | Jenelle van Heerden: All (Poly Haven) | CC0 1.0 Universal (public domain dedication). No attribution required; credit kept voluntarily. | Poly Haven "rock_09" - https://polyhaven.com/a/rock_09  (polyhaven.com / dl.polyhaven.org are blocked from this container) | SM_Rock_B |
| `polyhaven/models/rock_face_02` | Dario Barresi: All; Rico Cilliers: processing (Poly Haven) | CC0 1.0 Universal (public domain dedication). No attribution required; credit kept voluntarily. | Poly Haven "rock_face_02" - https://polyhaven.com/a/rock_face_02  (polyhaven.com / dl.polyhaven.org are blocked from this container) | SM_Rock_C |
| `polyhaven/models/round_wooden_table_01` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/round_wooden_table_01> | SM_Int_RoundTable |
| `polyhaven/models/round_wooden_table_02` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/round_wooden_table_02> | SM_Int_RoundTableB |
| `polyhaven/models/rubber_boots` | L | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/rubber_boots> | SM_Int_Boots |
| `polyhaven/models/rubber_duck_toy` | Plat251 | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/rubber_duck_toy> | SM_Int_RubberDuck |
| `polyhaven/models/seadogs_compass` | Benny Weimer | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/seadogs_compass> | SM_Int_Compass |
| `polyhaven/models/security_camera_01` | Alexander Otterbeck, Yann Kervran | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/security_camera_01> | SM_Int_SecurityCam |
| `polyhaven/models/security_light` | Maximilian Schuster | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/security_light> | SM_Int_SecurityLight |
| `polyhaven/models/side_table_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/side_table_01> | SM_Int_SideTable |
| `polyhaven/models/side_table_tall_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/side_table_tall_01> | SM_Int_TallSideTable |
| `polyhaven/models/small_wooden_table_01` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/small_wooden_table_01> | SM_Int_SmallTable |
| `polyhaven/models/sofa_02` | Kirill Sannikov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/sofa_02> | SM_Int_SofaB |
| `polyhaven/models/standing_chalkboard_01` | ParzivalCG | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/standing_chalkboard_01> | SM_Int_Chalkboard |
| `polyhaven/models/standing_picture_frame_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/standing_picture_frame_01> | SM_Int_PhotoFrame |
| `polyhaven/models/standing_picture_frame_02` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/standing_picture_frame_02> | SM_Int_PhotoFrameB |
| `polyhaven/models/stationery_supplies` | Mateusz Sadek | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/stationery_supplies> | SM_Int_Stationery |
| `polyhaven/models/steel_frame_shelves_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/steel_frame_shelves_01> | SM_Int_SteelShelves |
| `polyhaven/models/stone_01` | Dario Barresi: Photography; Rico Cilliers: photography, processing (Poly Haven) | CC0 1.0 Universal (public domain dedication). No attribution required; credit kept voluntarily. | Poly Haven "stone_01" - https://polyhaven.com/a/stone_01  (polyhaven.com / dl.polyhaven.org are blocked from this container) | SM_Pebbles_A |
| `polyhaven/models/strawberry_chocolate_cake` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/strawberry_chocolate_cake> | SM_Int_Cake |
| `polyhaven/models/street_lamp_01` | Josh Dean | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/street_lamp_01> | SM_LampPost |
| `polyhaven/models/tea_set_01` | James Ray Cock, Rico Cilliers, Jurita Burger | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/tea_set_01> | SM_Int_TeaSet |
| `polyhaven/models/television_02` | Benny Weimer | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/television_02> | SM_Int_TVB |
| `polyhaven/models/throw_pillows_01` | Serhii Khromov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/throw_pillows_01> | SM_Int_Pillows |
| `polyhaven/models/tool_cart` | Savva Zakharov | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/tool_cart> | SM_Int_ToolCart |
| `polyhaven/models/trashbag` | Benny Weimer | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/trashbag> | SM_Int_TrashBag |
| `polyhaven/models/tree_stump_01` | Rob Tuytel (All) (Poly Haven) | CC0 1.0 Universal (public domain dedication). No attribution required; credit kept voluntarily. | Poly Haven "tree_stump_01" - https://polyhaven.com/a/tree_stump_01  (polyhaven.com / dl.polyhaven.org are blocked from this container) | SM_Stump_A |
| `polyhaven/models/utility_box_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/utility_box_01> | SM_Int_UtilityBox |
| `polyhaven/models/vintage_cabinet_01` | Rico Cilliers | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_cabinet_01> | SM_Int_Vitrine |
| `polyhaven/models/vintage_day_bed` | Aron Łyczek | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_day_bed> | SM_Int_DayBed |
| `polyhaven/models/vintage_electric_kettle` | SV Garip | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_electric_kettle> | SM_Int_Kettle |
| `polyhaven/models/vintage_grandfather_clock_01` | Yann Kervran, James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_grandfather_clock_01> | SM_Int_GrandfatherClock |
| `polyhaven/models/vintage_microwave` | Adam Nekola | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_microwave> | SM_Int_Microwave |
| `polyhaven/models/vintage_oil_lamp` | Monsta3D | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_oil_lamp> | SM_Int_OilLamp |
| `polyhaven/models/vintage_radio_transceiver` | Mateusz Sadek | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_radio_transceiver> | SM_Int_Radio |
| `polyhaven/models/vintage_stapler` | Mateusz Sadek | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_stapler> | SM_Int_Stapler |
| `polyhaven/models/vintage_suitcase` | Maximilian Schuster | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_suitcase> | SM_Int_Suitcase |
| `polyhaven/models/vintage_wooden_drawer_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/vintage_wooden_drawer_01> | SM_Int_Dresser |
| `polyhaven/models/wall_clock` | PierreB3D | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wall_clock> | SM_Int_WallClock |
| `polyhaven/models/wicker_basket_01` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wicker_basket_01> | SM_Int_Basket |
| `polyhaven/models/wooden_bookshelf_worn` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wooden_bookshelf_worn> | SM_Int_Bookshelf |
| `polyhaven/models/wooden_bowl_01` | Oliver Harries | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wooden_bowl_01> | SM_Int_Bowl |
| `polyhaven/models/wooden_bucket_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wooden_bucket_01> | SM_Int_Bucket |
| `polyhaven/models/wooden_candlestick` | Josh Dean | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wooden_candlestick> | SM_Int_Candlestick |
| `polyhaven/models/wooden_cutting_board` | Kuutti Siitonen | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wooden_cutting_board> | SM_Int_CuttingBoard |
| `polyhaven/models/wooden_display_shelves_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wooden_display_shelves_01> | SM_Int_DisplayShelves |
| `polyhaven/models/wooden_ladder` | Miroslav Turura | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wooden_ladder> | SM_Int_Ladder |
| `polyhaven/models/wooden_lantern_01` | James Ray Cock | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wooden_lantern_01> | SM_Int_Lantern |
| `polyhaven/models/wooden_picnic_table` | Ulan Cabanilla | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/wooden_picnic_table> | SM_PicnicTable |
| `polyhaven/models/worn_metal_rack` | Luca B | CC0-1.0 (public domain dedication; no attribution required) | <https://polyhaven.com/a/worn_metal_rack> | SM_Int_MetalRack |
| `polyhaven/textures/brown_planks_09` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/brown_planks_09> | texture Planks |
| `polyhaven/textures/clay_roof_tiles_02` | Amal Kumar / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/clay_roof_tiles_02> | texture RoofTiles |
| `polyhaven/textures/cobblestone_floor_08` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/cobblestone_floor_08> | terrain layer Paving |
| `polyhaven/textures/concrete` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/concrete> | texture Concrete |
| `polyhaven/textures/corrugated_iron` | Dimitrios Savva (photography), Jenelle van Heerden (processing) / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/corrugated_iron> | texture Corrugated |
| `polyhaven/textures/damp_beach_sand` | Dimitrios Savva / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/damp_beach_sand> | terrain layer WetSand |
| `polyhaven/textures/dark_rock` | Amal Kumar / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/dark_rock> | terrain layer Ash |
| `polyhaven/textures/dirt_floor` | eye-candy.xyz / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/dirt_floor> | terrain layer Dirt, texture Dirt |
| `polyhaven/textures/distressed_painted_planks` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/distressed_painted_planks> | texture Siding |
| `polyhaven/textures/forest_leaves_03` | Rob Tuytel, Dimitrios Savva / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/forest_leaves_03> | terrain layer ForestFloor |
| `polyhaven/textures/leafy_grass` | Charlotte Baglioni / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/leafy_grass> | terrain layer Grass, texture Grass |
| `polyhaven/textures/long_white_tiles` | Jenelle van Heerden, Sergej Majboroda / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/long_white_tiles> | texture FloorTiles |
| `polyhaven/textures/painted_plaster_wall` | Amal Kumar / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/painted_plaster_wall> | texture Plaster |
| `polyhaven/textures/rectangular_paving` | Dimitrios Savva / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/rectangular_paving> | texture Paving |
| `polyhaven/textures/red_brick_03` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/red_brick_03> | texture Bricks |
| `polyhaven/textures/rock_boulder_dry` | Dimitrios Savva (photography), Rico Cilliers (processing) / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/rock_boulder_dry> | terrain layer Rock, texture Rock |
| `polyhaven/textures/white_plaster_02` | Rob Tuytel / Poly Haven | CC0 1.0 Universal | <https://polyhaven.com/a/white_plaster_02> | texture Grunge |
| `quaternius/adventurer` | Quaternius (https://quaternius.com) | CC0 1.0 Universal (public domain dedication) | <https://poly.pizza/m/5EGWBMpuXq> | A_Anime_Interact |
| `quaternius/astronaut` | Quaternius (https://quaternius.com) | CC0 1.0 Universal (public domain dedication) | <https://poly.pizza/m/0D54W8yfrA> | A_Anime_No, A_Anime_Wave, A_Anime_Yes |
| `quaternius/worker` | Quaternius (https://quaternius.com) | CC0 1.0 Universal (public domain dedication) | <https://poly.pizza/u/Quaternius> | A_Anime_Clap, A_Anime_Sit, SK_Student |
| `sketchfab/beach_chair` | stealth86 | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/3d-models/beach-chair-57e9477018d244378302070a8738b566> | SM_BeachChair |
| `sketchfab/beach_umbrella` | stealth86 | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/3d-models/beach-umbrella-1014ad7c8a4c4aa8ba5e88fc6151aa4f> | SM_BeachUmbrella |
| `sketchfab/city_props_vol2` | TampaJoey | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/3d-models/city-props-collection-volume-2-2f52ea53c58e455f9b69d11f58763c96> | SM_Bench |
| `sketchfab/container_20ft` | Ashkelon | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/3d-models/container-20ft-623de0e3ed6b47878c6b280969971743> | SM_Container_Blue, SM_Container_Red, SM_Container_Yellow |
| `sketchfab/iron_fence` | plaggy | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/3d-models/iron-fence-9c5ad29c104c48e69a1227927655d489> | SM_Fence_Iron |
| `sketchfab/old_japanese_lamp` | MarcHoogkamp | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/models/2d95746c71724633baf24d8066ecf8db> | SM_StoneLantern |
| `sketchfab/old_rowboat` | TooManyDemons | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/3d-models/old-rowboat-9922d5678af84adeb1c9b479856446ca> | SM_Rowboat |
| `sketchfab/rock_basalt` | yonimantz (https://sketchfab.com/yonimantz09) | CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) - ATTRIBUTION REQUIRED, commercial use allowed. | Sketchfab "Rock - Basalt" - https://sketchfab.com/3d-models/rock-basalt-9c42ca8140994bfca5029cf61b431214  (sketchfab.com is blocked from this container) | SM_VolcanicRock_A |
| `sketchfab/signpost` | Tetiana_Denysenko | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/3d-models/signpost-493bcedc8b344a38a9a67587b14bfcff> | SM_Signpost |
| `sketchfab/wooden_crate` | Memorie | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/3d-models/wooden-crate-2a3ac54357bb4b92bfbc119111c09fd1> | SM_Crate |
| `sketchfab/wooden_fence` | adventurer (ahmagh2e) | CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) - attribution REQUIRED | <https://sketchfab.com/3d-models/wooden-fence-building-farm-3a1e2a4bcbcf4a66a465e34e8ac5fb8f> | SM_Fence_Wood |
| `sweethome3d/acacia` | Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es) | CC-BY 3.0 Unported (https://creativecommons.org/licenses/by/3.0/) - ATTRIBUTION REQUIRED. | <https://www.sweethome3d.com/> | SM_BroadTree_C |
| `sweethome3d/coconut_palms` | Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es) | CC-BY 3.0 Unported (https://creativecommons.org/licenses/by/3.0/) - ATTRIBUTION REQUIRED. | <https://www.sweethome3d.com/> | SM_PalmTree_A, SM_PalmTree_B |
| `sweethome3d/hedge` | Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es) | CC-BY 3.0 Unported (https://creativecommons.org/licenses/by/3.0/) - ATTRIBUTION REQUIRED. | <https://www.sweethome3d.com/> | texture Leaves |
| `sweethome3d/hydrangea` | Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es) | CC-BY 3.0 Unported (https://creativecommons.org/licenses/by/3.0/) - ATTRIBUTION REQUIRED. | <https://www.sweethome3d.com/> | SM_FlowerBush_Blue, SM_FlowerBush_White |
| `sweethome3d/roses_bush` | Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es) | CC-BY 3.0 Unported (https://creativecommons.org/licenses/by/3.0/) - ATTRIBUTION REQUIRED. | <https://www.sweethome3d.com/> | SM_FlowerBush_Red, SM_FlowerBush_Yellow |

### CC-BY attributions

- `googlepoly/fishing_trawler`: "Boat" by Poly by Google, licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/), source https://poly.pizza/m/1ZuSXvhkRg_. Modified (rescaled, converted for Unreal Engine).
- `sketchfab/beach_chair`: "Beach Chair" (https://sketchfab.com/3d-models/beach-chair-57e9477018d244378302070a8738b566) by stealth86 (https://sketchfab.com/stealth86) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/beach_umbrella`: "Beach Umbrella" (https://sketchfab.com/3d-models/beach-umbrella-1014ad7c8a4c4aa8ba5e88fc6151aa4f) by stealth86 (https://sketchfab.com/stealth86) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/city_props_vol2`: "City Props Collection (volume 2)" (https://sketchfab.com/3d-models/city-props-collection-volume-2-2f52ea53c58e455f9b69d11f58763c96) by TampaJoey (https://sketchfab.com/TampaJoey) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/container_20ft`: "Container 20FT" (https://sketchfab.com/3d-models/container-20ft-623de0e3ed6b47878c6b280969971743) by Ashkelon (https://sketchfab.com/Ashkelon) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/iron_fence`: "Iron Fence" (https://sketchfab.com/3d-models/iron-fence-9c5ad29c104c48e69a1227927655d489) by plaggy (https://sketchfab.com/plaggy) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/old_japanese_lamp`: "Old Japanese Lamp" (https://sketchfab.com/models/2d95746c71724633baf24d8066ecf8db) by MarcHoogkamp (https://sketchfab.com/MarcHoogkamp) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/old_rowboat`: "Old Rowboat" (https://sketchfab.com/3d-models/old-rowboat-9922d5678af84adeb1c9b479856446ca) by TooManyDemons (https://sketchfab.com/toomanydemons) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/rock_basalt`: This work is based on "Rock - Basalt" (https://sketchfab.com/3d-models/rock-basalt-9c42ca8140994bfca5029cf61b431214) by yonimantz (https://sketchfab.com/yonimantz09) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/signpost`: "Signpost" (https://sketchfab.com/3d-models/signpost-493bcedc8b344a38a9a67587b14bfcff) by Tetiana_Denysenko (https://sketchfab.com/tetiana_denysenko) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/wooden_crate`: "Wooden Crate" (https://sketchfab.com/3d-models/wooden-crate-2a3ac54357bb4b92bfbc119111c09fd1) by Memorie (https://sketchfab.com/Memorie) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sketchfab/wooden_fence`: "Wooden fence Building Farm" (https://sketchfab.com/3d-models/wooden-fence-building-farm-3a1e2a4bcbcf4a66a465e34e8ac5fb8f) by adventurer (https://sketchfab.com/ahmagh2e) licensed under CC-BY-4.0 (http://creativecommons.org/licenses/by/4.0/)
- `sweethome3d/acacia`: "Acacia" 3D model by Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es), from the Sweet Home 3D Scopia furniture library (https://www.sweethome3d.com), licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/). Modified: meshes joined, decimated from 103k to 20k triangles, rescaled to metres, converted to glTF.
- `sweethome3d/coconut_palms`: "Coconut tree" and "Bended coconut tree" 3D models by Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es), from the Sweet Home 3D Scopia furniture library (https://www.sweethome3d.com), licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/). Modified: meshes joined, decimated from 81k to 20k triangles, rescaled to metres, converted to glTF.
- `sweethome3d/hedge`: "Hedge" (hedgeTextured) 3D model and texture by Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es), from the Sweet Home 3D Scopia furniture library (https://www.sweethome3d.com), licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/). Modified: decimated from 19.5k to 6k triangles, rescaled to metres, converted to glTF.
- `sweethome3d/hydrangea`: "Hydrangea" 3D model by Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es), from the Sweet Home 3D Scopia furniture library (https://www.sweethome3d.com), licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/). Modified: meshes joined, rescaled to metres, converted to glTF; blue and white flower textures re-coloured from the original pink.
- `sweethome3d/roses_bush`: "Roses bush" 3D model by Space Mushrooms <info@sweethome3d.com> and Scopia Visual Interfaces Systems, s.l. (http://www.scopia.es), from the Sweet Home 3D Scopia furniture library (https://www.sweethome3d.com), licensed under CC BY 3.0 (https://creativecommons.org/licenses/by/3.0/). Modified: meshes joined, decimated from 18k to 10k triangles, rescaled to metres, converted to glTF; yellow petal texture re-coloured from the original red.

## Tools

- [Blender](https://www.blender.org/) (GPL) as the `bpy` Python module - modelling, import, FBX export, Cycles renders
- [glTF-Transform](https://gltf-transform.dev/) (MIT) - meshopt decompression of glTF downloads
- [EZ-Tree](https://github.com/dgreenheck/ez-tree) (MIT) by Daniel Greenheck - procedural broadleaf / pine tree generation
- NumPy, SciPy, Pillow - terrain, textures and audio synthesis
- Unreal Engine 5.8 - Lumen, Nanite, Enhanced Input, editor Python
