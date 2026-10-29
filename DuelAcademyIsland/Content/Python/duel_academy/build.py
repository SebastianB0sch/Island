"""
Duel Academy Island - one-click editor build.

    Menu:  Duel Academy > Build Island            (import everything + build the level)
           Duel Academy > Rebuild Level Only      (re-place actors from layout.json)
    Python console:  import duel_academy.build as b; b.build_island()
    Command line:    UnrealEditor-Cmd DuelAcademyIsland.uproject -ExecutePythonScript="<project>/Content/Python/build_island_cli.py"
"""

import os
import time

import unreal

from . import common as C
from . import importer, level, materials


def _axis_check(layout, meshes):
    """Compare the imported terrain chunk with what the pipeline expected (Y handedness + units)."""
    chk = layout.get("axis_check", {})
    mesh = meshes.get(chk.get("mesh")) or C.load(f"{C.MESH_DIR}/Terrain/{chk.get('mesh')}")
    if mesh is None:
        C.warn("axis check skipped (terrain chunk missing)")
        return 1.0
    b = mesh.get_bounds()
    oy = float(b.origin.y)
    exp_y = float(chk.get("expected_center_y", oy))
    ext = float(b.box_extent.x)
    if ext < 1000.0:
        C.error(f"terrain chunk extent is {ext:.1f} uu - FBX units were not converted to centimetres!")
    if abs(oy - exp_y) <= abs(oy + exp_y):
        C.log(f"axis check OK (chunk centre y={oy:.0f}, expected {exp_y:.0f})")
        return 1.0
    C.warn(f"axis check: imported Y is mirrored (centre y={oy:.0f}, expected {exp_y:.0f}) - mirroring the layout")
    return -1.0


def build_island(import_assets=True, interactive=True):
    t0 = time.time()
    try:
        layout = C.load_json("layout.json")
        palette = C.load_json("materials.json")
        manifest = C.load_json("assets.json")
    except Exception as e:  # noqa: BLE001
        C.error(f"SourceAssets/Data missing - run Tools/build_island.py first ({e})")
        if interactive:
            unreal.EditorDialog.show_message("Duel Academy Island",
                                             "SourceAssets/Data/layout.json was not found.\n"
                                             "Run  python Tools/build_island.py  first (see README).",
                                             unreal.AppMsgType.OK)
        return False

    if C.native_class("DAIslandManager") is None:
        C.warn("C++ module DuelAcademyIsland not loaded - gameplay actors will be skipped. "
               "Compile the project (open the .uproject and accept the rebuild prompt) and rebuild.")

    n_inst = len(layout["instances"])
    work = (8 + len(manifest) + n_inst + 12) if import_assets else (n_inst + 12)
    with unreal.ScopedSlowTask(work, "Building Duel Academy Island...") as slow:
        slow.make_dialog(True)

        # ------------------------------------------------------------ assets
        meshes = {}
        if import_assets:
            slow.enter_progress_frame(2, "Importing textures")
            importer.import_textures()
            slow.enter_progress_frame(1, "Importing sounds")
            importer.import_audio()
            slow.enter_progress_frame(2, "Building materials")
            mpc, masters, instances = materials.build_all(palette)
            meshes = importer.import_meshes(manifest, slow)
            slow.enter_progress_frame(1, "Configuring meshes")
            for e in manifest:
                m = meshes.get(e["name"])
                if m is not None:
                    importer.configure_mesh(m, e, instances)
            importer.cleanup_imported_materials()
            slow.enter_progress_frame(1, "Importing the student character")
            importer.import_character(instances)
            slow.enter_progress_frame(1, "Importing the anime cast")
            importer.import_cast(masters)
            unreal.EditorAssetLibrary.save_directory(C.ROOT, only_if_is_dirty=True, recursive=True)
        else:
            mpc = C.load(f"{C.MAT_DIR}/MPC_DuelAcademy")
            instances = {}
            for e in manifest:
                m = C.load(f"{C.MESH_DIR}/{e['folder']}/{e['name']}")
                if m:
                    meshes[e["name"]] = m

        if slow.should_cancel():
            return False

        # ------------------------------------------------------------ level
        ysign = _axis_check(layout, meshes)
        slow.enter_progress_frame(1, "Creating level")
        level.open_or_create_map()
        placer = level.Placer(layout, meshes, instances, ysign)
        slow.enter_progress_frame(1, "Sky, sun, fog and clouds")
        env = placer.environment(mpc)
        placer.manager(env, mpc, C.load(f"{C.TEX_DIR}/T_IslandMap"))
        slow.enter_progress_frame(2, "Placing terrain and buildings")
        placer.statics()
        placer.floating()
        placer.instances(slow)
        slow.enter_progress_frame(2, "Lights, signs and gameplay")
        placer.lights()
        placer.texts()
        placer.zones()
        placer.interactables()
        placer.emitters()
        placer.audio()
        placer.npcs()
        placer.specials()
        placer.player_start()
        level.set_world_settings()
        slow.enter_progress_frame(2, "Saving")
        level.save()
        unreal.EditorAssetLibrary.save_directory(C.ROOT, only_if_is_dirty=True, recursive=True)

    msg = f"Duel Academy Island built in {time.time() - t0:.0f}s: {placer.count} actors."
    C.log(msg)
    if interactive:
        unreal.EditorDialog.show_message("Duel Academy Island", msg + "\n\nPress Play (Alt+P) to explore!", unreal.AppMsgType.OK)
    return True


def rebuild_level():
    return build_island(import_assets=False)
