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
    cast      anime cast: skeletal SK_Anime_* meshes, A_Anime_* takes (CC0, retargeted), face textures,
              cast.json; assigns the cast to layout.json's NPC markers
    render    Cycles preview renders of the whole island -> Docs/renders/

Outputs go to DuelAcademyIsland/SourceAssets/, which the Unreal editor script
(DuelAcademyIsland/Content/Python/duel_academy/build.py) imports.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STAGES = ["textures", "terrain", "meshes", "audio", "layout", "cast", "render"]


def parse_stages(argv):
    """Return the ordered stage list, or None when help was requested.

    Raises ValueError for unknown stage names/options so a typo cannot silently
    run the full default pipeline.
    """
    if any(arg in ("-h", "--help") for arg in argv):
        return None

    unknown = [arg for arg in argv if arg != "all" and arg != "--render" and arg not in STAGES]
    if unknown:
        raise ValueError(f"unknown stage/option: {', '.join(unknown)}")

    if "all" in argv:
        return list(STAGES)

    requested = [stage for stage in argv if stage in STAGES]
    stages = requested or [stage for stage in STAGES if stage != "render"]
    if "--render" in argv:
        stages.append("render")
    return [stage for stage in STAGES if stage in stages]


def missing_stage_inputs(stages):
    """[(stage, producer, path)] for outputs of an earlier stage the run still needs.

    Stages always run in pipeline order, so a producer inside `stages` counts as
    available; selecting e.g. ``layout`` alone without the terrain caches must
    fail with a hint (exit 2) instead of an intermediate FileNotFoundError
    traceback from inside numpy / the layout stage.
    """
    from dai import config as C
    required_files = {
        "meshes": [("terrain", "cache", "height.npy"),
                   ("terrain", "cache", "terrain_cache.json")],
        "layout": [("terrain", "cache", name) for name in
                   ("height.npy", "forest.npy", "slope.npy", "occupied.npy", "d_in.npy",
                    "terrain_info.json", "terrain_cache.json")],
        "render": [("layout", "data", "layout.json"),
                   ("textures", "data", "terrain_layers.json"),
                   ("terrain", "cache", "height.npy"),
                   ("terrain", "cache", "terrain_cache.json")],
    }
    directories = {"cache": C.CACHE_DIR, "data": C.OUT_DATA}
    problems = []
    for stage in STAGES:
        if stage not in stages:
            continue
        entries = required_files.get(stage)
        if not entries:
            continue
        producers = {producer for producer, _dir, _name in entries}
        if producers <= set(stages):
            continue
        for producer, folder, name in entries:
            if producer in stages:
                continue
            path = os.path.join(directories[folder], name)
            if not os.path.isfile(path) or os.path.getsize(path) == 0:
                problems.append((stage, producer, path))
    return problems


def main(argv):
    unknown = [a for a in argv if a not in STAGES and a not in ("all", "--render")]
    if unknown:
        # A typo must not silently fall back to the full (multi-minute) rebuild.
        sys.exit(f"unknown stage(s): {' '.join(unknown)}; valid: all, --render, {', '.join(STAGES)}")
    stages = [a for a in argv if a in STAGES] or [s for s in STAGES if s != "render"] + (["render"] if "--render" in argv else [])
    if "all" in argv:
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
        try:
            if st == "terrain":
                from dai import terrain
                terrain.build_terrain(log)
            elif st == "meshes":
                from dai import terrain, terrain_mesh
                import numpy as np
                blend.reset_scene()
                terrain.check_cache("height.npy")   # refuses stale / mismatched tools/.cache entries
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
                from dai import layout   # layout.load_cached() re-checks the cache stamp
                blend.reset_scene()
                lay = layout.Layout(log)
                lay.place_world()
                lay.place_locations()
                lay.place_interiors()
                lay.place_path_dressing()
                lay.scatter()
                layout.export_props(lay.manifest, log)
                layout.export_avatar(lay.manifest, log)
                from dai import character
                try:
                    character.build(log)
                except Exception as e:  # noqa: BLE001 - never lose the layout over the optional skeletal student
                    log(f"  !! character export failed ({e}); the procedural avatar will be used")
                    stale = os.path.join(C.OUT_DATA, "character.json")
                    if os.path.exists(stale):
                        os.remove(stale)
                layout.terrain_manifest(lay.manifest)
                lay.minimap()
                lay.write()
            elif st == "cast":
                from dai.anime import build as cast_build
                cast_build.build(log)
            elif st == "render":
                from dai import render
                render.render_island(log)
        except StampedCacheError as error:
            # Terrain caches are stamped with FIELD_RES / WORLD_SIZE (terrain.py):
            # a mismatched or partial cache is refused (exit 2) instead of
            # silently producing a finished-looking but wrong layout.json.
            print(f"build_island: {error}", file=sys.stderr)
            return 2
        log(f"  ({time.time() - t0:.1f}s)")
    log(f"done in {time.time() - t_all:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
