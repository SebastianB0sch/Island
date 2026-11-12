"""Swap the procedural GX vegetation for the local Fab nature packs.

The Fab packs are licensed marketplace content and are **not committed**.  They
are installed locally by ``Tools/import_fab_nature.py`` (the same pattern as the
optional Fab Anime Character Pack).  When the packs are absent, ``layout.json``
keeps the native procedural vegetation, so a fresh checkout still builds.

The native asset names stay in ``layout.json``: placement, NPC clearance,
collision proxies and the footprint checker all keep using the procedural
proportions they were tuned for.  The Unreal level build imports this module and
swaps the *render* meshes when the local packs are installed, scaling each
instance from the native target height to the Fab mesh's native height.  The
mapping is deliberately conservative:

* trees use the StyleHex birch/broadleaf and Stylized PBR Nature common/pine
  meshes that the reference UE5 project also uses;
* palms use the Tropical Garden Lounge palm;
* the abandoned-dorm dead trees use the dark cypress (the packs have no
  leafless tree);
* bushes, ferns, flowers and grass use the StyleHex/Stylized PBR clumps.

The donor palette is ``C:/dev/argh/ue5/Content/Data/fab_palette.json``.
"""

from __future__ import annotations

import os

STYLEHEX = "/Game/StyleHex_Studio/Free_Packs/FREE_Stylized_Forest_Sample/Meshes"
PBR = "/Game/Stylized_PBR_Nature/Foliage/Assets"
TROPICAL = "/Game/TropicalGardenLounge/Vegetation/StaticMeshes"


def _stylehex(folder: str, name: str) -> str:
    return f"{STYLEHEX}/{folder}/{name}.{name}"


def _pbr(name: str) -> str:
    return f"{PBR}/{name}.{name}"


def _tropical(name: str) -> str:
    return f"{TROPICAL}/{name}.{name}"


# Native height (metres, at scale 1) and the mesh's lowest point relative to its
# pivot.  Measured from the installed assets; see Tools/measure_fab_nature.py.
ASSETS = {
    # StyleHex stylized forest
    "SM_Tree_Birch_1": dict(path=_stylehex("Trees", "SM_Tree_Birch_1"), height=12.071, bottom=-0.000, category="tree"),
    "SM_Tree_Birch_2": dict(path=_stylehex("Trees", "SM_Tree_Birch_2"), height=13.162, bottom=-0.000, category="tree"),
    "SM_Tree_Broadleaf_1": dict(path=_stylehex("Trees", "SM_Tree_Broadleaf_1"), height=15.705, bottom=-0.000, category="tree"),
    "SM_Tree_Broadleaf_2": dict(path=_stylehex("Trees", "SM_Tree_Broadleaf_2"), height=11.679, bottom=-0.000, category="tree"),
    "SM_Fol_Bush_1": dict(path=_stylehex("Foliage", "SM_Fol_Bush_1"), height=1.383, bottom=-0.040, category="bush"),
    "SM_Fol_Bush_2": dict(path=_stylehex("Foliage", "SM_Fol_Bush_2"), height=2.581, bottom=-0.176, category="bush"),
    "SM_Fol_Flower_Clump_1": dict(path=_stylehex("Foliage", "SM_Fol_Flower_Clump_1"), height=0.138, bottom=0.183, category="flower"),
    "SM_Fol_Flower_Clump_2": dict(path=_stylehex("Foliage", "SM_Fol_Flower_Clump_2"), height=0.188, bottom=0.203, category="flower"),
    "SM_Fol_Flower_Clump_3": dict(path=_stylehex("Foliage", "SM_Fol_Flower_Clump_3"), height=0.144, bottom=0.165, category="flower"),
    "SM_Fol_Grass_Clump_1": dict(path=_stylehex("Foliage", "SM_Fol_Grass_Clump_1"), height=0.556, bottom=-0.014, category="grass"),
    "SM_Fol_Grass_Clump_2": dict(path=_stylehex("Foliage", "SM_Fol_Grass_Clump_2"), height=0.493, bottom=-0.006, category="grass"),
    "SM_Fol_Grass_Clump_3": dict(path=_stylehex("Foliage", "SM_Fol_Grass_Clump_3"), height=0.289, bottom=-0.001, category="grass"),
    "SM_Fol_Grass_Clump_4": dict(path=_stylehex("Foliage", "SM_Fol_Grass_Clump_4"), height=0.700, bottom=0.000, category="grass"),
    "SM_Fol_Grass_Clump_5": dict(path=_stylehex("Foliage", "SM_Fol_Grass_Clump_5"), height=0.558, bottom=-0.003, category="grass"),
    # Stylized PBR Nature
    "SM_Common_Tree_02": dict(path=_pbr("SM_Common_Tree_02"), height=6.869, bottom=-0.257, category="tree"),
    "SM_Common_Tree_03": dict(path=_pbr("SM_Common_Tree_03"), height=6.739, bottom=-0.396, category="tree"),
    "SM_Common_Tree_05": dict(path=_pbr("SM_Common_Tree_05"), height=10.231, bottom=-0.259, category="tree"),
    "SM_Common_Tree_06": dict(path=_pbr("SM_Common_Tree_06"), height=7.568, bottom=-0.324, category="tree"),
    "SM_Common_Tree_08": dict(path=_pbr("SM_Common_Tree_08"), height=7.700, bottom=-0.191, category="tree"),
    "SM_Common_Tree_11": dict(path=_pbr("SM_Common_Tree_11"), height=8.526, bottom=-0.458, category="tree"),
    "SM_Pine_Tree_1": dict(path=_pbr("SM_Pine_Tree_1"), height=8.664, bottom=-0.041, category="tree"),
    "SM_Pine_Tree_2": dict(path=_pbr("SM_Pine_Tree_2"), height=6.794, bottom=-0.064, category="tree"),
    "SM_Bush": dict(path=_pbr("SM_Bush"), height=1.423, bottom=0.003, category="bush"),
    "SM_Fern": dict(path=_pbr("SM_Fern"), height=0.294, bottom=0.032, category="fern"),
    "SM_Grass": dict(path=_pbr("SM_Grass"), height=1.065, bottom=-0.457, category="grass"),
    "SM_Clover": dict(path=_pbr("SM_Clover"), height=0.684, bottom=-0.279, category="grass"),
    # Tropical Garden Lounge
    "SM_PlamTree": dict(path=_tropical("SM_PlamTree"), height=9.121, bottom=-0.066, category="tree"),
    "SM_Cypress02": dict(path=_tropical("SM_Cypress02"), height=4.361, bottom=-0.000, category="tree"),
}

# Category defaults mirror the native scatter flags in Tools/dai/layout.py.
CATEGORIES = {
    "tree": dict(collision=True, cull=(0, 0), shadow=True),
    "bush": dict(collision=False, cull=(12000, 20000), shadow=True),
    "fern": dict(collision=False, cull=(4000, 8000), shadow=False),
    "flower": dict(collision=False, cull=(8000, 14000), shadow=True),
    "grass": dict(collision=False, cull=(3000, 6000), shadow=False),
}

# native asset -> target height (m, at native scale 1) + Fab variants
REPLACE = {
    # trees -----------------------------------------------------------------
    "SM_PalmTree_A": dict(target=11.0, category="tree", variants=("SM_PlamTree",)),
    "SM_PalmTree_B": dict(target=8.0, category="tree", variants=("SM_PlamTree",)),
    "SM_BroadTree_A": dict(target=12.0, category="tree",
                            variants=("SM_Tree_Broadleaf_2", "SM_Common_Tree_05", "SM_Common_Tree_11",
                                      "SM_Tree_Birch_2")),
    "SM_BroadTree_B": dict(target=16.0, category="tree",
                            variants=("SM_Tree_Broadleaf_1", "SM_Tree_Broadleaf_2")),
    "SM_BroadTree_C": dict(target=6.0, category="tree",
                            variants=("SM_Tree_Birch_1", "SM_Tree_Birch_2", "SM_Common_Tree_03")),
    "SM_PineTree_A": dict(target=14.0, category="tree", variants=("SM_Pine_Tree_1", "SM_Pine_Tree_2")),
    "SM_DeadTree_A": dict(target=9.0, category="tree", variants=("SM_Cypress02",)),
    # bushes ----------------------------------------------------------------
    "SM_Bush_A": dict(target=1.6, category="bush", variants=("SM_Fol_Bush_1", "SM_Fol_Bush_2", "SM_Bush")),
    "SM_Bush_B": dict(target=1.0, category="bush", variants=("SM_Fol_Bush_1", "SM_Bush")),
    # flowers (low clumps; the native flower bushes were 1.2 m, the Fab clumps
    # are much wider, so keep them lower to preserve the garden footprint) ----
    "SM_FlowerBush_Red": dict(target=0.5, category="flower", variants=("SM_Fol_Flower_Clump_1",)),
    "SM_FlowerBush_Yellow": dict(target=0.5, category="flower", variants=("SM_Fol_Flower_Clump_2",)),
    "SM_FlowerBush_Blue": dict(target=0.5, category="flower", variants=("SM_Fol_Flower_Clump_3",)),
    "SM_FlowerBush_White": dict(target=0.5, category="flower",
                                 variants=("SM_Fol_Flower_Clump_1", "SM_Fol_Flower_Clump_3")),
    # undergrowth -----------------------------------------------------------
    "SM_Fern_A": dict(target=0.45, category="fern", variants=("SM_Fern",)),
    "SM_GrassClump_A": dict(target=0.6, category="grass",
                             variants=("SM_Fol_Grass_Clump_1", "SM_Fol_Grass_Clump_2", "SM_Fol_Grass_Clump_3",
                                       "SM_Fol_Grass_Clump_4", "SM_Fol_Grass_Clump_5", "SM_Grass", "SM_Clover")),
}


# Marker assets that prove each pack is installed on this machine.  The
# installed folders are gitignored, so a fresh checkout keeps the native
# procedural vegetation instead of generating layout.json with missing meshes.
_INSTALL_MARKERS = (
    "DuelAcademyIsland/Content/StyleHex_Studio/Free_Packs/FREE_Stylized_Forest_Sample/Meshes/Trees/SM_Tree_Birch_1.uasset",
    "DuelAcademyIsland/Content/Stylized_PBR_Nature/Foliage/Assets/SM_Common_Tree_01.uasset",
    "DuelAcademyIsland/Content/TropicalGardenLounge/Vegetation/StaticMeshes/SM_PlamTree.uasset",
)


def available(root: str | None = None) -> bool:
    """True when all three local Fab nature packs are installed under ``root``."""
    if root is None:
        # Tools/dai/fab_nature.py -> repository root
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return all(os.path.isfile(os.path.join(root, marker)) for marker in _INSTALL_MARKERS)


def is_replaced(asset: str) -> bool:
    """True when a native scatter/prop name is handled by the Fab layer."""
    return asset in REPLACE


def translate(instances: dict) -> tuple[dict, dict]:
    """Translate native instance groups into Fab instance groups.

    ``instances`` is the layout writer's native map:
        native name -> [[x_cm, y_cm, z_cm, yaw_ue, scale(, pitch, roll)], ...]
    (already in Unreal coordinates, Y mirrored).  Returns
        (fab name -> group dict, native name -> stats dict)
    where each group carries the Fab object path plus the same collision /
    cull / shadow flags the native group used.  Variants are assigned
    round-robin per native group, so the result is deterministic.
    """
    groups: dict[str, dict] = {}
    stats: dict[str, dict] = {}
    for native_name, items in sorted(instances.items()):
        spec = REPLACE.get(native_name)
        if spec is None or not items:
            continue
        target = float(spec["target"])
        variants = spec["variants"]
        count = 0
        for index, item in enumerate(items):
            fab_name = variants[index % len(variants)]
            asset = ASSETS[fab_name]
            scale = target * float(item[4]) / float(asset["height"])
            z_cm = float(item[2]) - float(asset["bottom"]) * scale * 100.0
            group = groups.get(fab_name)
            if group is None:
                meta = CATEGORIES[asset["category"]]
                group = dict(mesh=asset["path"], folder="Island/vegetation",
                             label=f"Scatter_{fab_name}", collision=bool(meta["collision"]),
                             cull=[int(meta["cull"][0]), int(meta["cull"][1])],
                             shadow=bool(meta["shadow"]), items=[])
                groups[fab_name] = group
            group["items"].append([item[0], item[1], round(z_cm, 1), item[3], round(scale, 3)] + list(item[5:7]))
            count += 1
        stats[native_name] = dict(target=target, variants=list(variants), count=count)
    return groups, stats
