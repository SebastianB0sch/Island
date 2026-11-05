"""
Standing-room check for the whole island, without exporting anything: every fast-travel arrival point has room
for the player (floor, no walls / furniture / props in the way, not in water, not on a cliff) and every NPC spot
is clear (dai/placement.py; NPCs blocked by furniture are first stepped clear, as the layout stage does).

    python Tools/people_check.py            # exit code 0 when there are no problems
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,F401

from dai import blend, layout  # noqa: E402


def main():
    blend.reset_scene()
    lay = layout.Layout(print)
    lay.place_world()
    lay.place_locations(export=False)
    lay.place_path_dressing(export=False)
    lay.scatter()
    problems = lay.check_people()
    for z in lay.zones():
        room = ""
        if z["parent"]:
            e = z["extent"]
            room = f"  room {2 * e[0] / 100:5.1f} x {2 * e[1] / 100:5.1f} x {2 * e[2] / 100:4.1f} m"
        print(f"  {z['id']:24s} parent={z['parent'] or '-':14s} feet {tuple(round(c, 1) for c in z['_feet'])}{room}")
    print(f"PEOPLE PROBLEMS: {len(problems)}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
