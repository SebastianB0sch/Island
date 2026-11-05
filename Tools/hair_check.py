"""
Hair audit of the exported anime cast (see Tools/dai/anime/hairaudit.py): width, see-through holes, outline
roughness, exposed scalp and the fitted spring rig of every restyled head of hair.

    python Tools/hair_check.py                     # every cast member with a hair shape
    python Tools/hair_check.py jaden chazz --json /tmp/hair.json

Exit status 1 when a character is over the budget (hairaudit.BUDGET).
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    from dai.anime import hairaudit as H
    rep = H.report(a.ids or None)
    if a.json:
        H.to_json(rep, a.json)
    bad = [c for c, m in rep.items() if H.over_budget(m)]
    print(f"hair: {len(rep) - len(bad)}/{len(rep)} within budget" + (f" (over: {', '.join(bad)})" if bad else ""))
    sys.exit(1 if bad or not rep else 0)


if __name__ == "__main__":
    main()
