"""Run Tools/build_island.py inside Blender with the local scipy dependency path."""

import os
import runpy
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, ".blender_site"))
sys.path.insert(0, ROOT)

runpy.run_path(os.path.join(ROOT, "build_island.py"), run_name="__main__")
