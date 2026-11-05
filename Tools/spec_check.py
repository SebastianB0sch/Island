"""
Interior spec check for the whole island - the definition of "up to spec":

  * audit (dai/inspect.py): 0 issues, except known false positives listed in ACCEPTED below
  * detail coverage per interior camera: rooms >= 45 %, halls / corridors / stairs / landings >= 35 %
    (big halls whose size is the point may be listed in WAIVED with a reason)
  * no painted (opaque) windows left except the decoration listed in PAINTED_OK (see storey_report.py)

    python Tools/spec_check.py                      # everything (slow: builds every location)
    python Tools/spec_check.py academy --json out.json

Exit code 0 when everything passes.
"""

import argparse
import importlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,F401

from dai import blend, inspect  # noqa: E402
from dai.assets import LOCATION_MODULES  # noqa: E402

HALL_WORDS = ("corridor", "hall", "stair", "landing", "foyer", "gallery", "lobby", "entrance", "concourse",
              "court", "arena", "walkway", "nave", "atrium", "terrace", "deck", "lookout", "view", "point",
              "shelter", "platform", "turret", "tower")

# audit lines that are known artefacts of auditing a location on its own (see the module reports)
ACCEPTED = [
    (r"^academy$", r"door academy 3\.00x3\.80 .*no floor at threshold height outside"),   # towers stand on terrain
    (r"^harbor$", r"SM_Container_Yellow .*nothing below it"),     # hangs from the crane spreader (outdoors)
    (r"^harbor$", r"SM_LampPost .*(floats|sunk)"),                # the floating ferry is drawn at the origin
]

# camera views below target whose size / shape is the point (reason shown in the report)
WAIVED = {}

# painted window area (m2) allowed per placement, with the reason
PAINTED_OK = {
    "academy": (1300.0, "arena pyramid roof slits, drum windows facing the arena / behind the stands, roof-void dormers"),
    "harbor": (7.0, "the ferry's outboard lifeboats"),
}


def is_hall(label):
    return any(w in label.lower() for w in HALL_WORDS)


def painted_area(aset):
    total = 0.0
    for mb in aset.meshes.values():
        for f, m in zip(mb.faces, mb.face_mats):
            if m != "M_Glass":
                continue
            vs = [mb.verts[i] for i in f]
            a = sum((vs[i] - vs[0]).cross(vs[i + 1] - vs[0]).length / 2 for i in range(1, len(vs) - 1))
            if a >= 0.05:
                total += a
    return total


def check(key, aset):
    res = inspect.audit(aset)
    fails = []
    for k in ("grounding", "ceiling", "wall", "clipping", "doors"):
        for line in res.get(k, []):
            if not any(re.search(pk, key) and re.search(pl, line) for pk, pl in ACCEPTED):
                fails.append(f"[{k}] {line}")
    rooms = []
    for r in res.get("rooms", []):
        target = 0.35 if is_hall(r["label"]) else 0.45
        ok = r["coverage"] >= target or (key, r["label"]) in WAIVED
        rooms.append(dict(r, target=target, ok=ok))
    painted = painted_area(aset)
    allow = PAINTED_OK.get(key, (2.0, ""))[0]
    return dict(issues=fails, rooms=rooms, painted=round(painted, 1), painted_ok=painted <= allow)


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("modules", nargs="*")
    ap.add_argument("--only", default=None)
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)
    mods = args.modules or LOCATION_MODULES
    out, n_fail = {}, 0
    for m in mods:
        mod = importlib.import_module(f"dai.assets.{m}")
        for key, fn in getattr(mod, "PLACEMENTS", {}).items():
            if args.only and key != args.only:
                continue
            blend.reset_scene()
            r = check(key, fn())
            out[key] = r
            bad_rooms = [x for x in r["rooms"] if not x["ok"]]
            fails = len(r["issues"]) + len(bad_rooms) + (not r["painted_ok"])
            n_fail += fails
            print(f"=== {key}: {len(r['issues'])} issues, {len(bad_rooms)}/{len(r['rooms'])} views below target, "
                  f"painted {r['painted']} m2 {'OK' if r['painted_ok'] else 'TOO MUCH'}", flush=True)
            for line in r["issues"][:20]:
                print("    " + line)
            for x in sorted(bad_rooms, key=lambda x: x["coverage"]):
                print(f"    {x['label']:34s} {100 * x['coverage']:4.0f} % < {100 * x['target']:.0f} %"
                      f"   ceiling {x['ceiling'] or 0:.2f} m")
    if args.json:
        with open(args.json, "w") as fp:
            json.dump(out, fp, indent=1)
    print(f"SPEC FAILURES: {n_fail}")
    sys.exit(1 if n_fail else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
