"""Swap the remaining procedural / simple GX props for local Fab meshes.

This is the companion to :mod:`dai.fab_nature`.  The vegetation swap covers the
trees, palms, bushes, ferns, flowers and grass.  This module covers the remaining
instance groups that are either still procedural or simple enough that the
stylized Fab packs are a better fit:

* rocks / cliffs / volcanic rock / pebbles -> StyleHex stones and Stylized PBR
  Nature rocks;
* street furniture that is still procedural (bollard, planter, vending machine)
  -> College Raimon / Tropical Garden Lounge meshes;
* a few simple outdoor props that already had a CC0 stand-in but now use the
  matching Fab mesh (street lamp, beach chair/parasol, trash bin).

The packs are licensed marketplace content and are **not committed**.  They are
installed locally by ``Tools/import_fab_nature.py``.  When they are absent the
native / third-party meshes stay in place, so a fresh checkout still builds.

The native names stay in ``layout.json``.  Placement, NPC clearance, collision
proxies and the footprint checker keep using the procedural proportions they
were tuned for; only the render mesh changes at level-build time.  Each instance
is scaled from the native target height to the Fab mesh's measured height and
its pivot is moved so the mesh's lowest point sits on the same ground line.

The donor palette is ``C:/dev/argh/ue5/Content/Data/fab_palette.json``.
"""

from __future__ import annotations

import os

STYLEHEX_STONES = "/Game/StyleHex_Studio/Free_Packs/FREE_Stylized_Forest_Sample/Meshes/Stones"
PBR_ROCKS = "/Game/Stylized_PBR_Nature/Rocks/Assets"
TROPICAL_VEG = "/Game/TropicalGardenLounge/Vegetation/StaticMeshes"
COLLEGE = "/Game/CollegeRaimon/Meshes"


def _stone(name: str) -> str:
    return f"{STYLEHEX_STONES}/{name}.{name}"


def _rock(name: str) -> str:
    return f"{PBR_ROCKS}/{name}.{name}"


def _tropical(name: str) -> str:
    return f"{TROPICAL_VEG}/{name}.{name}"


def _college(name: str) -> str:
    return f"{COLLEGE}/{name}.{name}"


# Measured from the installed assets (Tools/measure_fab_nature.py).  ``height``
# and ``bottom`` are in metres at scale 1.  ``rot`` is an optional
# (pitch, yaw, roll) offset in degrees; the street-light mesh is authored lying
# along -Y and is rolled upright at spawn time.
ASSETS = {
    # StyleHex stylized stones
    "SM_Stone_1": dict(path=_stone("SM_Stone_1"), height=0.840, bottom=-0.363,
                       width=1.116, depth=1.203, category="rock"),
    "SM_Stone_2": dict(path=_stone("SM_Stone_2"), height=0.817, bottom=-0.434,
                       width=1.165, depth=1.404, category="rock"),
    "SM_Stone_3": dict(path=_stone("SM_Stone_3"), height=1.861, bottom=-0.891,
                       width=2.375, depth=2.865, category="rock"),
    "SM_Stone_Boulder_1": dict(path=_stone("SM_Stone_Boulder_1"), height=3.414, bottom=-1.368,
                               width=4.132, depth=4.887, category="rock"),
    # Stylized PBR Nature rocks
    "SM_R_Rock_01": dict(path=_rock("SM_R_Rock_01"), height=2.739, bottom=-1.244,
                         width=3.781, depth=3.940, category="rock"),
    "SM_R_Rock_02": dict(path=_rock("SM_R_Rock_02"), height=2.738, bottom=-1.336,
                         width=3.897, depth=4.107, category="rock"),
    "SM_R_Rock_03": dict(path=_rock("SM_R_Rock_03"), height=3.432, bottom=-1.359,
                         width=5.343, depth=4.595, category="rock"),
    "SM_R_Rock_04": dict(path=_rock("SM_R_Rock_04"), height=3.065, bottom=-1.340,
                         width=3.092, depth=2.776, category="rock"),
    # Tropical Garden Lounge potted plants (planter replacement)
    "SM_PlamPlant01": dict(path=_tropical("SM_PlamPlant01"), height=1.252, bottom=-0.016,
                           width=0.599, depth=0.485, category="prop"),
    "SM_PlamPlant02": dict(path=_tropical("SM_PlamPlant02"), height=1.743, bottom=-0.016,
                           width=1.947, depth=1.389, category="prop"),
    # College Raimon street / campus props
    "SM_ao336_lv1": dict(path=_college("SM_ao336_lv1"), height=0.653, bottom=-0.191,
                         width=0.383, depth=0.383, category="prop"),
    "SM_ao059_nosdw_lv1": dict(path=_college("SM_ao059_nosdw_lv1"), height=1.017, bottom=-0.180,
                               width=0.400, depth=0.440, category="prop"),
    "SM_ao127_01": dict(path=_college("SM_ao127_01"), height=2.200, bottom=-1.100,
                        width=1.000, depth=0.700, category="prop"),
    "SM_ao017_polelight_1_lv1": dict(path=_college("SM_ao017_polelight_1_lv1"),
                                     height=5.003, bottom=0.000, width=0.820, depth=0.818,
                                     category="prop", rot=(0.0, 0.0, -90.0)),
    "SM_ao130_nosdw_parasol_lv1": dict(path=_college("SM_ao130_nosdw_parasol_lv1"),
                                       height=2.543, bottom=-1.271, width=2.543, depth=2.903,
                                       category="prop"),
    "SM_chair01": dict(path=_college("SM_chair01"), height=0.555, bottom=-0.274,
                       width=0.490, depth=0.902, category="prop"),
}

# Category defaults mirror the native scatter flags in Tools/dai/layout.py.
# ``translate`` preserves the native group flags when they are present, so these
# are only fallbacks for hand-written groups.
CATEGORIES = {
    "rock": dict(collision=True, cull=(0, 0), shadow=True),
    "prop": dict(collision=True, cull=(0, 0), shadow=True),
}

# native asset -> target height (m, at native scale 1) + Fab variants
REPLACE = {
    # rocks / cliffs --------------------------------------------------------
    "SM_Rock_A": dict(target=1.4, category="rock", variants=("SM_Stone_1", "SM_Stone_2")),
    "SM_Rock_B": dict(target=1.05, category="rock", variants=("SM_Stone_2", "SM_Stone_1")),
    "SM_Rock_C": dict(target=5.2, category="rock",
                       variants=("SM_R_Rock_03", "SM_R_Rock_01", "SM_R_Rock_02")),
    "SM_Rock_D": dict(target=3.5, category="rock", variants=("SM_Stone_Boulder_1", "SM_Stone_3")),
    "SM_CliffRock_A": dict(target=12.6, category="rock", variants=("SM_R_Rock_04", "SM_R_Rock_03")),
    "SM_VolcanicRock_A": dict(target=3.6, category="rock", variants=("SM_R_Rock_04", "SM_R_Rock_01")),
    "SM_Pebbles_A": dict(target=0.3, category="rock", variants=("SM_Stone_1",)),
    # still-procedural street furniture -------------------------------------
    "SM_Bollard": dict(target=0.7, category="prop", variants=("SM_ao336_lv1",)),
    "SM_Planter": dict(target=1.2, category="prop", variants=("SM_PlamPlant02", "SM_PlamPlant01")),
    "SM_VendingMachine": dict(target=1.9, category="prop", variants=("SM_ao127_01",)),
    # simple outdoor props that already had a CC0 stand-in ------------------
    "SM_LampPost": dict(target=5.0, category="prop", variants=("SM_ao017_polelight_1_lv1",)),
    "SM_TrashBin": dict(target=1.0, category="prop", variants=("SM_ao059_nosdw_lv1",)),
    "SM_BeachUmbrella": dict(target=2.6, category="prop", variants=("SM_ao130_nosdw_parasol_lv1",)),
    "SM_BeachChair": dict(target=0.9, category="prop", variants=("SM_chair01",)),
}

# Marker assets that prove each pack is installed on this machine.  The
# installed folders are gitignored, so a fresh checkout keeps the native /
# third-party meshes instead of generating layout.json with missing meshes.
_INSTALL_MARKERS = (
    "DuelAcademyIsland/Content/CollegeRaimon/Meshes/SM_ao127_01.uasset",
    "DuelAcademyIsland/Content/Stylized_PBR_Nature/Rocks/Assets/SM_R_Rock_01.uasset",
    "DuelAcademyIsland/Content/StyleHex_Studio/Free_Packs/FREE_Stylized_Forest_Sample/Meshes/Stones/SM_Stone_1.uasset",
    "DuelAcademyIsland/Content/TropicalGardenLounge/Vegetation/StaticMeshes/SM_PlamPlant02.uasset",
)


def available(root: str | None = None) -> bool:
    """True when the Fab prop/rock packs are installed under ``root``."""
    if root is None:
        root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return all(os.path.isfile(os.path.join(root, marker)) for marker in _INSTALL_MARKERS)


def is_replaced(asset: str) -> bool:
    """True when a native instance group is handled by this Fab layer."""
    return asset in REPLACE


def translate(groups: dict) -> tuple[dict, dict]:
    """Translate native instance groups into Fab instance groups.

    ``groups`` is the level writer's native map:
        native name -> {items: [[x_cm, y_cm, z_cm, yaw_ue, scale(, pitch, roll)], ...], ...}
    The native group's collision / cull / shadow / folder flags are preserved.
    Returns ``(fab name -> group dict, native name -> stats dict)``.  Variants
    are assigned round-robin per native group, so the result is deterministic.
    """
    out: dict[str, dict] = {}
    stats: dict[str, dict] = {}
    for native_name, group in sorted(groups.items()):
        spec = REPLACE.get(native_name)
        if spec is None:
            continue
        items = group.get("items") or []
        if not items:
            continue
        target = float(spec["target"])
        variants = spec["variants"]
        fit = spec.get("fit", "height")
        count = 0
        for index, item in enumerate(items):
            fab_name = variants[index % len(variants)]
            asset = ASSETS[fab_name]
            base = float(item[4])
            if fit == "width":
                scale = target * base / float(asset["width"])
            elif fit == "depth":
                scale = target * base / float(asset["depth"])
            else:
                scale = target * base / float(asset["height"])
            bottom = float(asset.get("bottom_rotated", asset["bottom"]))
            z_cm = float(item[2]) - bottom * scale * 100.0
            fab_group = out.get(fab_name)
            if fab_group is None:
                meta = CATEGORIES.get(asset["category"], CATEGORIES["prop"])
                fab_group = dict(
                    mesh=asset["path"],
                    folder=group.get("folder", "Island/props"),
                    label=group.get("label") or f"Scatter_{fab_name}",
                    collision=bool(group.get("collision", meta["collision"])),
                    cull=[int(v) for v in group.get("cull", meta["cull"])],
                    shadow=bool(group.get("shadow", meta["shadow"])),
                    items=[],
                )
                rot = asset.get("rot")
                if rot:
                    fab_group["rot"] = [float(v) for v in rot]
                out[fab_name] = fab_group
            fab_group["items"].append([item[0], item[1], round(z_cm, 1), item[3], round(scale, 3)] + list(item[5:7]))
            count += 1
        stats[native_name] = dict(target=target, variants=list(variants), count=count)
    return out, stats
