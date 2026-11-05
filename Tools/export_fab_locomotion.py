"""Export the licensed Fab anime locomotion takes to FBX for Blender retargeting.

Run with the Unreal editor (the pack must be installed locally):

    UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript \
        -script=Tools/export_fab_locomotion.py -unattended -nosplash -nullrhi

The FBXs are written to ``Tools/thirdparty/fab_anime/anim`` (gitignored) and consumed by
``Tools/retarget_fab_anime.py``.  They are derived from licensed Fab content and must not
be committed or redistributed.
"""

from __future__ import annotations

import os

import unreal

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(REPO, "Tools", "thirdparty", "fab_anime", "anim")
TAKES = ("a_manM_idle", "a_man_walk_F", "a_man_run_F")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    failed = 0
    for name in TAKES:
        path = f"/Game/AnimeCharacters/Animations/Locomotion/{name}"
        sequence = unreal.load_asset(path)
        if sequence is None:
            unreal.log_error(f"export_fab_locomotion: missing {path} (install the Fab pack first)")
            failed += 1
            continue
        out = os.path.join(OUT_DIR, f"{name}.fbx")
        task = unreal.AssetExportTask()
        task.set_editor_property("object", sequence)
        task.set_editor_property("filename", out)
        task.set_editor_property("exporter", unreal.AnimSequenceExporterFBX())
        task.set_editor_property("automated", True)
        task.set_editor_property("prompt", False)
        task.set_editor_property("replace_identical", True)
        if not unreal.Exporter.run_asset_export_task(task):
            unreal.log_error(f"export_fab_locomotion: could not export {name}")
            failed += 1
            continue
        unreal.log(f"export_fab_locomotion: {name} -> {out}")
    if failed:
        return 1
    unreal.log("export_fab_locomotion: PASS (3 takes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
