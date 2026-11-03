"""Run Tools/build_island.py inside a Blender install instead of the bpy module.

    blender -b -P Tools/build_island_blender.py                # default stages
    blender -b -P Tools/build_island_blender.py -- terrain cast # selected stages

Blender's bundled Python lacks scipy; put it in Tools/.blender_site (gitignored),
e.g. `<blender python> -m pip install --target Tools/.blender_site scipy`.
"""

import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, ".blender_site"))
sys.path.insert(0, ROOT)

# Blender's own arguments (-b, -P <file>) are not build stages; only what follows "--" is.
script = os.path.join(ROOT, "build_island.py")
sys.argv = [script] + (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
runpy.run_path(script, run_name="__main__")
