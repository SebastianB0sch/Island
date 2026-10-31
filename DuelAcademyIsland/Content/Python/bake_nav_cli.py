"""Bake navigation for the generated level and save it in the map."""

import unreal

world = unreal.EditorLevelLibrary.get_editor_world()
if not world:
    unreal.log_error("[DuelAcademy] bake_nav: no editor world")
else:
    unreal.SystemLibrary.execute_console_command(world, "RebuildNavigation")
    unreal.SystemLibrary.execute_console_command(world, "SaveCurrentLevel")
    unreal.log("[DuelAcademy] bake_nav: RebuildNavigation + SaveCurrentLevel requested")
