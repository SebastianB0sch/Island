"""Run the Fab locomotion retarget inside Blender.

    blender --background --factory-startup --python Tools/retarget_fab_anime_blender.py

Or use ``python Tools/retarget_fab_anime.py`` (the launcher finds Blender for you).
"""

import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from dai.anime import fab  # noqa: E402

raise SystemExit(fab.main())
