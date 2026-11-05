"""
Audit the interiors of one or more locations (see dai/inspect.py for the checks).

    python Tools/audit_interiors.py slifer ra            # modules
    python Tools/audit_interiors.py obelisk --only obelisk_girls
    python Tools/audit_interiors.py all --json Docs/previews/audit.json

Run with the Blender-as-a-module interpreter (pip install bpy, Python 3.13).
"""

import argparse
import importlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import bpy  # noqa: E402,F401

from dai import blend, inspect  # noqa: E402
from dai.assets import LOCATION_MODULES  # noqa: E402


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("modules", nargs="+")
    ap.add_argument("--only", default=None)
    ap.add_argument("--json", default=None)
    ap.add_argument("--limit", type=int, default=12)
    args = ap.parse_args(argv)
    mods = LOCATION_MODULES if args.modules == ["all"] else args.modules
    out = {}
    total = 0
    for m in mods:
        mod = importlib.import_module(f"dai.assets.{m}")
        for key, fn in getattr(mod, "PLACEMENTS", {}).items():
            if args.only and key != args.only:
                continue
            blend.reset_scene()
            aset = fn()
            print(f"=== {key}")
            res = inspect.audit(aset)
            total += inspect.report(key, res, limit=args.limit)
            out[key] = res
    if args.json:
        with open(args.json, "w") as fp:
            json.dump(out, fp, indent=1)
    print(f"TOTAL issues: {total}")


if __name__ == "__main__":
    main(sys.argv[1:])
