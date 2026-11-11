"""Render the missing UI character portraits from the project's own cast.

Run inside Blender (the cast pipeline uses bpy), with the hash seed pinned:

    set PYTHONHASHSEED=0
    "C:\\Program Files\\Blender Foundation\\Blender 5.2\\blender.exe" --background --factory-startup ^
        --python Tools/render_portraits.py -- --missing

Useful variants:

    ... -- --list                        status for every known speaker
    ... -- --ids chumley crowler         render only these ids
    ... -- --force --ids jaden           overwrite existing art
    ... -- --expressions                 render the expression frames declared in the story data
    ... -- --expressions --force         redraw every declared expression
    ... -- --samples 32 --view 8         slower, slightly three-quarter view

The script writes 512 x 512 busts plus *_face.png crops into
DuelAcademyIsland/Content/Data/Portraits, flattened onto the UI's #263541 panel.
"""

import argparse
import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(ROOT)
sys.path.insert(0, os.path.join(ROOT, ".blender_site"))
sys.path.insert(0, ROOT)

PORTRAIT_DIR = os.path.join(PROJECT, "DuelAcademyIsland", "Content", "Data", "Portraits")
STORY_DIR = os.path.join(PROJECT, "DuelAcademyIsland", "Content", "Data", "Story", "dialogue")


def _args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--ids", nargs="*", dest="id_list", default=[])
    ap.add_argument("--out", default=PORTRAIT_DIR)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--view", type=float, default=0.0)
    ap.add_argument("--force", action="store_true", help="overwrite portraits that already exist")
    ap.add_argument("--missing", action="store_true", help="only render ids with no <id>.png (default)")
    ap.add_argument("--list", action="store_true", help="report which speakers have art and exit")
    ap.add_argument("--expressions", action="store_true", help="render the expression frames declared in the story data")
    ap.add_argument("--expression", default="", help="with --expressions, render only this expression")
    ap.add_argument("--duel", action="store_true",
                    help="with --expressions, also render the six generic duel cut-in emotions")
    ap.add_argument("--include-official", action="store_true",
                    help="also render expressions for the Duel Links regulars instead of using official cut-ins")
    return ap.parse_args(argv)


def _declared_expressions():
    """{speaker id: {expression, ...}} from the dialogue speaker tables."""
    out = {}
    for path in sorted(glob.glob(os.path.join(STORY_DIR, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        for speaker, spec in data.get("speakers", {}).items():
            out.setdefault(speaker, set()).update(spec.get("expressions", []))
    return out


def _expression_pass(a, entries, wanted):
    from dai.anime import expressions as EXPR
    from dai.anime import portrait as PORTRAIT

    declared = _declared_expressions()
    if a.duel and wanted:
        for cid in wanted:
            declared.setdefault(cid, set()).update(EXPR.DUEL)
    ids = wanted or sorted(set(declared) & set(entries))
    rendered = 0
    for cid in ids:
        if cid not in entries or cid not in declared:
            continue
        if cid in EXPR.OFFICIAL and not a.include_official:
            print("%-18s official expression frames (Tools/fetch_expression_portraits.py)" % cid)
            continue
        base = os.path.join(a.out, cid + ".png")
        if not os.path.exists(base):
            print("%-18s base bust" % cid)
            PORTRAIT.render_pair(a.out, cid, entries[cid], samples=a.samples, view=a.view)
        for expression in sorted(declared[cid]):
            if a.expression and expression != a.expression:
                continue
            path = os.path.join(a.out, cid + "_" + expression + ".png")
            if os.path.exists(path) and not a.force:
                continue
            weights = EXPR.blend(EXPR.resting(entries[cid]), expression)
            if not weights:
                print("%-18s no recipe for %s" % (cid, expression))
                continue
            print("%-18s %s" % (cid, expression))
            PORTRAIT.render_expression(a.out, cid, entries[cid], expression, weights,
                                       samples=a.samples, view=a.view)
            rendered += 1
    print("expressions: %d frame(s) -> %s" % (rendered, a.out))


def main():
    a = _args()
    from dai.anime import cast as CAST
    from dai.anime import portrait as PORTRAIT
    from dai.anime import portrait_cast

    entries = CAST.all_entries()
    for cid, entry in portrait_cast.all_entries().items():
        # A real cast member always wins over the portrait-only stand-in, except
        # that the generic student busts get a readable hair colour.
        if cid.startswith("student_") or cid not in entries:
            entries[cid] = entry

    wanted = a.id_list or a.ids
    if wanted:
        unknown = [cid for cid in wanted if cid not in entries]
        if unknown:
            raise SystemExit("unknown portrait id(s): " + ", ".join(unknown))
        ids = wanted
    else:
        ids = list(entries)

    def has(cid):
        return os.path.exists(os.path.join(a.out, cid + ".png"))

    if a.list:
        for cid in ids:
            print("%-18s %s" % (cid, "ok" if has(cid) else "MISSING"))
        return

    if a.expressions:
        _expression_pass(a, entries, wanted)
        return

    if not a.force:
        ids = [cid for cid in ids if not has(cid)]
    if not ids:
        print("portraits: nothing to do")
        return

    print("portraits: %d id(s) -> %s" % (len(ids), a.out))
    for index, cid in enumerate(ids, 1):
        print("[%d/%d] %s" % (index, len(ids), cid))
        PORTRAIT.render_pair(a.out, cid, entries[cid], samples=a.samples, view=a.view)


if __name__ == "__main__":
    from dai.determinism import pin_hash_seed
    pin_hash_seed()
    main()
