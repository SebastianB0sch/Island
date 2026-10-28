"""Executed automatically by the Python Editor Script Plugin when the editor starts."""

import unreal

try:
    from duel_academy import menu

    menu.register()
    menu.schedule_first_run_check()
    unreal.log("[DuelAcademy] editor tools ready - see the 'Duel Academy' menu")
except Exception as e:  # noqa: BLE001
    unreal.log_error(f"[DuelAcademy] failed to initialise editor tools: {e}")
