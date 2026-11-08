"""Run Tools/build_island.py inside Blender with the local scipy dependency path."""

import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, ".blender_site"))
sys.path.insert(0, ROOT)

# Blender keeps its own switches in sys.argv; build_island.py expects only the
# stage list.  Use the conventional `-- <stages>` separator.
if "--" in sys.argv:
    sys.argv = [sys.argv[0]] + sys.argv[sys.argv.index("--") + 1:]

runpy.run_path(os.path.join(ROOT, "build_island.py"), run_name="__main__")
