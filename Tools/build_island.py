"""
Duel Academy Island - procedural asset pipeline.

Usage (Blender 5.x as a Python module:  pip install bpy  ->  Python 3.13):

    python Tools/build_island.py                 # everything
    python Tools/build_island.py terrain layout  # selected stages

Stages (in order):
    textures  procedural tileable textures + curated photo texture sets (third-party CC0)
    terrain   heightfield, splat maps, colour map, heightmap PNG, caches
    meshes    terrain chunk FBX + ocean / sea floor / lake surfaces
    audio     synthesised ambience + UI sounds
    layout    location meshes, props, avatar, roads, vegetation scatter,
              layout.json / materials.json / assets.json, minimap
    render    Cycles preview renders of the whole island -> Docs/renders/

Outputs go to DuelAcademyIsland/SourceAssets/, which the Unreal editor script
(DuelAcademyIsland/Content/Python/duel_academy/build.py) imports.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STAGES = ["textures", "terrain", "meshes", "audio", "layout", "render"]


def main(argv):
    stages = [a for a in argv if a in STAGES] or [s for s in STAGES if s != "render"] + (["render"] if "--render" in argv else [])
    if argv and argv[0] == "all":
        stages = STAGES
    import numpy as np
    from dai import blend, config as C
    t_all = time.time()
    log = lambda m: print(m, flush=True)
    for st in STAGES:
        if st not in stages:
            continue
        t0 = time.time()
        log(f"[{st}]")
        if st == "terrain":
            from dai import terrain
            terrain.build_terrain(log)
        elif st == "meshes":
            from dai import terrain_mesh
            blend.reset_scene()
            h = np.load(os.path.join(C.CACHE_DIR, "height.npy"))
            terrain_mesh.build_chunks(h, log=log)
            terrain_mesh.build_water(h, log=log)
        elif st == "textures":
            from dai import textures
            textures.build_textures(log)
        elif st == "audio":
            from dai import audio
            audio.build_audio(log)
        elif st == "layout":
            from dai import layout
            blend.reset_scene()
            lay = layout.Layout(log)
            lay.place_world()
            lay.place_locations()
            lay.place_path_dressing()
            lay.scatter()
            layout.export_props(lay.manifest, log)
            layout.export_avatar(lay.manifest, log)
            layout.terrain_manifest(lay.manifest)
            lay.minimap()
            lay.write()
        elif st == "render":
            from dai import render
            render.render_island(log)
        log(f"  ({time.time() - t0:.1f}s)")
    log(f"done in {time.time() - t_all:.1f}s")


if __name__ == "__main__":
    main(sys.argv[1:])
