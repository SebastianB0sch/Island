"""Measure the installed Fab nature / prop meshes (headless Unreal editor).

The layout swappers (Tools/dai/fab_nature.py and Tools/dai/fab_props.py) scale
every Fab instance from the native target height, so they need the source mesh
height and the mesh's lowest point relative to its pivot.  This script measures
both and writes:

    DuelAcademyIsland/Saved/fab_nature_bounds.json
    DuelAcademyIsland/Saved/fab_props_bounds.json

Run after Tools/import_fab_nature.py:

    UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript ^
        -script=Tools/measure_fab_nature.py -unattended -nosplash -nullrhi

If a mesh's source art changes, copy the new height/bottom values into the
module's ASSETS table.  Assets with a ``rot`` offset are authored in a different
orientation; the measured values are reported in their authored space and the
module stores the upright values explicitly.
"""

import json
import os
import sys

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "Tools"))

from dai import fab_nature, fab_props  # noqa: E402  (pure-Python modules, safe outside Blender)


def measure(module, filename):
    out = {}
    for name, spec in sorted(module.ASSETS.items()):
        path = spec["path"]
        mesh = unreal.EditorAssetLibrary.load_asset(path)
        if mesh is None:
            # The object-path form can fail on some engine builds; try the package path.
            mesh = unreal.EditorAssetLibrary.load_asset(path.rsplit(".", 1)[0])
        if mesh is None:
            unreal.log_warning(f"FABMEASURE missing {path} (run Tools/import_fab_nature.py)")
            continue
        bounds = mesh.get_bounds()
        origin, extent = bounds.origin, bounds.box_extent
        out[name] = dict(
            path=path,
            height_cm=extent.z * 2.0,
            bottom_cm=origin.z - extent.z,
            width_cm=extent.x * 2.0,
            depth_cm=extent.y * 2.0,
            rot=list(spec.get("rot") or (0.0, 0.0, 0.0)),
        )
        unreal.log(f"FABMEASURE {name}: height={extent.z * 2.0:.1f}cm "
                   f"bottom={origin.z - extent.z:.1f}cm width={extent.x * 2.0:.1f}cm")

    dest = os.path.join(REPO, "DuelAcademyIsland", "Saved", filename)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fp:
        json.dump(out, fp, indent=1)
    unreal.log(f"FABMEASURE wrote {dest} ({len(out)} meshes)")


measure(fab_nature, "fab_nature_bounds.json")
measure(fab_props, "fab_props_bounds.json")
