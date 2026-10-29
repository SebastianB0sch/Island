"""
Cycles toon render of anime cast members standing in a row (iterate on hair / faces / outfits).

    python Tools/preview_cast.py                      # the named cast -> Docs/previews/cast.png
    python Tools/preview_cast.py jaden syrus --state Wave --frame 20 --out /tmp/x.png
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--state", default="Idle")
    ap.add_argument("--frame", type=int, default=12)
    ap.add_argument("--out", default=None)
    ap.add_argument("--res", default="1800x720")
    ap.add_argument("--samples", type=int, default=32)
    ap.add_argument("--view", type=float, default=0.0, help="camera azimuth (deg): 0 front, 35 three-quarter, 180 back")
    a = ap.parse_args()
    from dai import config as C
    from dai.anime import build
    out = a.out or os.path.join(C.DOCS_DIR, "previews", "cast.png")
    w, h = (int(v) for v in a.res.split("x"))
    build.render_lineup(out, a.ids or None, a.state, a.frame, (w, h), a.samples, a.view)


if __name__ == "__main__":
    main()
