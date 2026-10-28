"""Editor menu + first-launch prompt for Duel Academy Island."""

import os

import unreal

from . import common as C

_tick_handle = None
_ticks = 0


def register():
    menus = unreal.ToolMenus.get()
    main = menus.find_menu("LevelEditor.MainMenu")
    if main is None:
        return
    sub = main.add_sub_menu("DuelAcademy", "DuelAcademy", "DuelAcademy", "Duel Academy", "Duel Academy Island tools")
    entries = [
        ("BuildIsland", "Build Island (import + level)",
         "Import every generated asset and build the island level (several minutes).",
         "import importlib, duel_academy.build as b; importlib.reload(b); b.build_island()"),
        ("RebuildLevel", "Rebuild Level Only",
         "Re-place all actors from SourceAssets/Data/layout.json using already imported assets.",
         "import importlib, duel_academy.build as b; importlib.reload(b); b.rebuild_level()"),
        ("OpenIsland", "Open Island Map", "Open the Duel Academy Island level.",
         f"import unreal; unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level('{C.MAP_PATH}')"),
    ]
    for name, label, tip, cmd in entries:
        e = unreal.ToolMenuEntry(name=name, type=unreal.MultiBlockType.MENU_ENTRY)
        e.set_label(label)
        e.set_tool_tip(tip)
        e.set_string_command(unreal.ToolMenuStringCommandType.PYTHON, "", cmd)
        sub.add_menu_entry("Island", e)
    menus.refresh_all_widgets()


def _first_run_tick(delta):
    global _ticks, _tick_handle
    _ticks += 1
    if _ticks < 90:
        return
    try:
        if unreal.AssetRegistryHelpers.get_asset_registry().is_loading_assets():
            return
    except Exception:  # noqa: BLE001
        pass
    unreal.unregister_slate_post_tick_callback(_tick_handle)
    _tick_handle = None
    if C.exists(C.MAP_PATH):
        return
    if not os.path.exists(C.data_path("layout.json")):
        C.warn("SourceAssets/Data/layout.json missing - run Tools/build_island.py (see README)")
        return
    answer = unreal.EditorDialog.show_message(
        "Duel Academy Island",
        "Welcome to Duel Academy Island!\n\n"
        "The island level hasn't been built in this project yet. Import the generated assets and build it now?\n"
        "(This takes a few minutes. You can also run it later from the 'Duel Academy' menu.)",
        unreal.AppMsgType.YES_NO)
    if answer == unreal.AppReturnType.YES:
        from . import build
        build.build_island()


def schedule_first_run_check():
    global _tick_handle
    try:
        if unreal.SystemLibrary.is_unattended():
            return
    except Exception:  # noqa: BLE001
        pass
    _tick_handle = unreal.register_slate_post_tick_callback(_first_run_tick)
