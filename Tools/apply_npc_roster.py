"""Re-apply the ambient NPC roster to an existing layout.json.

The full ``layout`` stage needs Blender, but the roster only rewrites the NPC
markers.  This lets a layout.json that was generated before the roster existed
pick up the unique names, dialogue and hair colours without rebuilding the
island.

    python Tools/apply_npc_roster.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dai import config as C  # noqa: E402
from dai import jsonio  # noqa: E402
from dai.anime import cast as CAST  # noqa: E402


def main() -> int:
    path = os.path.join(C.OUT_DATA, "layout.json")
    if not os.path.exists(path):
        print(f"apply_npc_roster: missing {path}; run the layout stage first", file=sys.stderr)
        return 2
    layout = jsonio.read_json(path)
    npcs = layout.get("npcs", [])
    CAST.assign_npcs(npcs)
    jsonio.write_json(path, layout, separators=(",", ":"))
    names = [n["name"] for n in npcs if n.get("name")]
    print(f"apply_npc_roster: {len(npcs)} markers, {len(names)} named NPCs, "
          f"{len(set(names))} unique names -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
