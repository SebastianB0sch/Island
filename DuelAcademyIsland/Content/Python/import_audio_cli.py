"""Import the generated audio (ambience, UI and M_* music) and save the assets.

    UnrealEditor-Cmd DuelAcademyIsland.uproject -ExecutePythonScript="DuelAcademyIsland/Content/Python/import_audio_cli.py" -unattended -nop4 -nullrhi -nosound

This is the audio-only slice of build_island_cli.py, useful after re-rendering
the Juicebox Studio soundtrack without rebuilding the whole island.
"""

import unreal

from duel_academy import common as C, importer

importer.import_audio()
if not unreal.EditorAssetLibrary.save_directory(C.ROOT, only_if_is_dirty=True, recursive=True):
    raise RuntimeError("saving /Game/DuelAcademy after the audio import failed")
unreal.log("[DuelAcademy] audio import complete and saved")
