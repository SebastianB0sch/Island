"""Headless build:  UnrealEditor-Cmd DuelAcademyIsland.uproject -ExecutePythonScript="<abs path>/build_island_cli.py" """

import unreal

from duel_academy import build

ok = build.build_island(import_assets=True, interactive=False)
unreal.log("[DuelAcademy] headless build " + ("succeeded" if ok else "FAILED"))
