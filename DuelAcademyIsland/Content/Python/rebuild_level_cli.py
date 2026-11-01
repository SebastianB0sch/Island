"""Rebuild only the level from the current SourceAssets/layout.json."""

import unreal

from duel_academy import build

try:
    ok = build.rebuild_level(interactive=False)
except Exception as exc:  # noqa: BLE001 - make the failure explicit in the log
    unreal.log_error(f"[DuelAcademy] rebuild level failed with an exception: {exc}")
    raise
if ok:
    unreal.log("[DuelAcademy] rebuild level succeeded")
else:
    unreal.log_error("[DuelAcademy] rebuild level FAILED")
    raise SystemExit(1)
