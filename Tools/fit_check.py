"""
Cloth fit audit of the anime cast (see Tools/dai/anime/fitcheck.py).

    python Tools/fit_check.py                      # every cast member, all audited poses
    python Tools/fit_check.py jaden alexis --poses Walk,Run --json /tmp/fit.json -v

Exit status 1 when a character pokes through its clothes beyond the budget or its cloth has holes.
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--poses", default=None, help="comma list of Idle,Walk,Run,Duel,Sit,Talk")
    ap.add_argument("--json", default=None)
    ap.add_argument("-v", action="store_true", help="print the poking layer pairs per pose")
    a = ap.parse_args()
    from dai.anime import fitcheck as F
    rep = F.fit_report(a.ids or None, a.poses.split(",") if a.poses else None)
    if a.v:
        for cid, r in rep.items():
            for pose, p in r["poses"].items():
                if p["poke"]:
                    print(f"    {cid} {pose}: " + ", ".join(f"{k} {n}" for k, n in sorted(p["poke"].items())))
            if any(r["holes"].values()):
                print(f"    {cid} holes: {r['holes']}")
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(rep, fh, indent=1)
    bad = [c for c, r in rep.items() if F.over_budget(r) or any(r["holes"].values())]
    print(f"fit: {len(rep) - len(bad)}/{len(rep)} within budget" + (f" (over: {', '.join(bad)})" if bad else ""))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    from dai.determinism import pin_hash_seed
    pin_hash_seed()   # reproducible cloth fit (see dai/determinism.py)
    main()
