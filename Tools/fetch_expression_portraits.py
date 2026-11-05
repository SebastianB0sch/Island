"""Fetch the official Duel Links expression cut-ins for the regulars.

The five regulars whose base portraits are ported Duel Links renders (Alexis,
Bastion, Chazz, Syrus and Zane) already have official expression art on
Yugipedia.  This script downloads the selected frames, fits them onto the same
512 x 512 #263541 panel as the dialogue portraits, and writes them as
``<id>_<expression>.png``.  Jaden and the player already ship with their
expression frames.

The files are fan-project reference assets, local-only and not redistributable
(see CREDITS.md).  The project's own cast renders are produced separately by
Tools/render_portraits.py --expressions.

    python Tools/fetch_expression_portraits.py
    python Tools/fetch_expression_portraits.py --force
"""

import argparse
import io
import json
import os
import urllib.parse
import urllib.request

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "DuelAcademyIsland", "Content", "Data", "Portraits")
API = "https://yugipedia.com/api.php"
PANEL = (38, 53, 65)
SIZE = 512
MARGIN = 16
BOTTOM = 504
USER_AGENT = "DuelAcademyIsland-portrait-tool/1.0"

# target expression -> (Yugipedia file prefix, frame number)
# Frames follow the Duel Links set: 1 neutral, 2 happy/confident, 3 angry,
# 4 shocked, 5 sad, 6 laugh, 7/8 character-specific (nervous, determined, ...).
SOURCES = {
    "alexis": {
        "neutral": ("AlexisRhodes", 1),
        "happy": ("AlexisRhodes", 2),
        "angry": ("AlexisRhodes", 3),
    },
    "bastion": {
        "neutral": ("BastionMisawa", 1),
        "happy": ("BastionMisawa", 2),
        "thoughtful": ("BastionMisawa", 7),
    },
    "chazz": {
        "neutral": ("ChazzPrinceton", 1),
        "smug": ("ChazzPrinceton", 2),
        "angry": ("ChazzPrinceton", 3),
    },
    "syrus": {
        "neutral": ("SyrusTruesdale", 1),
        "happy": ("SyrusTruesdale", 2),
        "shocked": ("SyrusTruesdale", 4),
        "nervous": ("SyrusTruesdale", 7),
        "determined": ("SyrusTruesdale", 3),
    },
    "zane": {
        "neutral": ("ZaneTruesdale", 1),
        "happy": ("ZaneTruesdale", 2),
        "stern": ("ZaneTruesdale", 3),
    },
}


def _query(params):
    params = dict(params, format="json")
    url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def _urls():
    titles = []
    for frames in SOURCES.values():
        for prefix, index in frames.values():
            titles.append("File:%s-DULI-DuelPortrait-%d.png" % (prefix, index))
    out = {}
    for start in range(0, len(titles), 40):
        chunk = titles[start:start + 40]
        data = _query({
            "action": "query",
            "titles": "|".join(chunk),
            "prop": "imageinfo",
            "iiprop": "url",
        })
        for page in data.get("query", {}).get("pages", {}).values():
            info = page.get("imageinfo") or []
            if info:
                out[page["title"]] = info[0]["url"]
    return out


def _download(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=90) as response:
        return Image.open(io.BytesIO(response.read())).convert("RGBA")


def _panel(image):
    box = image.getchannel("A").getbbox()
    if not box:
        return None
    art = image.crop(box)
    scale = min((SIZE - MARGIN * 2) / art.width, (BOTTOM - MARGIN) / art.height)
    art = art.resize((max(1, round(art.width * scale)), max(1, round(art.height * scale))),
                     Image.LANCZOS)
    canvas = Image.new("RGBA", (SIZE, SIZE), (*PANEL, 255))
    canvas.alpha_composite(art, ((SIZE - art.width) // 2, BOTTOM - art.height))
    return canvas.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="overwrite existing expression frames")
    ap.add_argument("--dry-run", action="store_true", help="print the files that would be written")
    a = ap.parse_args()

    urls = _urls()
    missing = []
    written = 0
    for cid, frames in sorted(SOURCES.items()):
        for expression, (prefix, index) in sorted(frames.items()):
            name = "%s-DULI-DuelPortrait-%d.png" % (prefix, index)
            title = "File:" + name
            target = os.path.join(OUT, cid + "_" + expression + ".png")
            if os.path.exists(target) and not a.force:
                print("%-18s %-10s exists" % (cid, expression))
                continue
            url = urls.get(title)
            if not url:
                missing.append(title)
                print("%-18s %-10s MISSING URL %s" % (cid, expression, title))
                continue
            print("%-18s %-10s <- %s" % (cid, expression, url))
            if a.dry_run:
                continue
            image = _panel(_download(url))
            if image is None:
                missing.append(title)
                continue
            image.save(target, optimize=True)
            written += 1
    print("expression cut-ins: %d written, %d missing" % (written, len(missing)))
    return 1 if missing else 0


if __name__ == "__main__":
    raise SystemExit(main())
