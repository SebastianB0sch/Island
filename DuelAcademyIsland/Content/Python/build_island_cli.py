"""Headless build:  UnrealEditor-Cmd DuelAcademyIsland.uproject -ExecutePythonScript="<abs path>/build_island_cli.py" """

import unreal

from duel_academy import build

ok = build.build_island(import_assets=True, interactive=False)
unreal.log("[DuelAcademy] headless build " + ("succeeded" if ok else "FAILED"))
if not ok:
    # Surface the failure as a Python error (LogPython: Error) so callers that
    # scan the log, or run via -run=pythonscript, can detect it.
    raise RuntimeError("[DuelAcademy] headless build failed")
