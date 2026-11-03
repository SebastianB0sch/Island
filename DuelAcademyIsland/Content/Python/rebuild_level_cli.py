"""Rebuild only the level from the current SourceAssets/layout.json."""

import unreal

from duel_academy import build

ok = build.rebuild_level(interactive=False)
unreal.log("[DuelAcademy] rebuild level " + ("succeeded" if ok else "FAILED"))
if not ok:
    raise RuntimeError("[DuelAcademy] rebuild level failed")
