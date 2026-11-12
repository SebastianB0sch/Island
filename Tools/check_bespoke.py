"""
Checks a bespoke character (Tools/dai/anime/hero.py DESIGNS) against the template's learnings.

    python Tools/check_bespoke.py                 # every bespoke design: design rules only (fast)
    python Tools/check_bespoke.py hero --built    # also build the model and measure how much of each eye
                                                  # the camera sees from -60..60 deg (hair over the eyes)

Exit code 1 when a rule is broken. See Docs/BESPOKE_CHARACTERS.md.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--built", action="store_true", help="build the model(s) in Blender and measure eye clearance")
    a = ap.parse_args()
    from dai.anime import bespoke, hero
    ids = a.ids or list(hero.DESIGNS)
    bad = 0
    for cid in ids:
        problems = bespoke.check(hero.DESIGNS[cid])
        if a.built:
            import bpy
            from dai import blend
            from dai.anime import build as B
            from dai.anime import cast as CAST
            blend.reset_scene()
            e = dict(CAST.all_entries()[cid])
            B.M.build_model(cid, B.use_artist_model(e, B.artist_model(cid, e)), B.key_name)
            clear = bespoke.eye_clearance([o for o in bpy.data.objects if o.type == "MESH"])
            print(f"{cid}: eye clearance (% seen, right / left)")
            for deg, (r, l) in clear.items():
                print(f"  {deg:+4d} deg  {r:5.0f}  {l:5.0f}")
            problems += bespoke.eye_problems(clear)
        print(f"{cid}: " + ("ok" if not problems else f"{len(problems)} problem(s)"))
        for p in problems:
            print(f"  - {p}")
        bad += bool(problems)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    from dai.determinism import pin_hash_seed
    pin_hash_seed()
    main()
