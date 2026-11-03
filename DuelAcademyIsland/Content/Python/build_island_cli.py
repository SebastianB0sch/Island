"""Headless build:  UnrealEditor-Cmd DuelAcademyIsland.uproject -ExecutePythonScript="<abs path>/build_island_cli.py" """

import unreal

from duel_academy import build

try:
    ok = build.build_island(import_assets=True, interactive=False)
except Exception as exc:  # noqa: BLE001 - make the failure explicit in the log
    unreal.log_error(f"[DuelAcademy] headless build failed with an exception: {exc}")
    raise
if ok:
    unreal.log("[DuelAcademy] headless build succeeded")
else:
    unreal.log_error("[DuelAcademy] headless build FAILED")
    # -ExecutePythonScript does not reliably propagate an exit code, but raising
    # SystemExit still makes the Python plugin report this script as failed.
    raise SystemExit(1)
