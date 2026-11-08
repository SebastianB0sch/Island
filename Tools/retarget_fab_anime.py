"""Bake the licensed Fab anime locomotion takes onto the GX cast (local-only).

The source takes must first be exported from the Unreal project:

    UnrealEditor-Cmd DuelAcademyIsland.uproject -run=pythonscript \
        -script=Tools/export_fab_locomotion.py -unattended -nosplash -nullrhi

Then run this launcher:

    python Tools/retarget_fab_anime.py
    python Tools/retarget_fab_anime.py --blender "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"

Outputs go to ``Tools/thirdparty/fab_anime/retargeted`` (gitignored).  Install them into
Unreal with ``Tools/apply_fab_locomotion.py``; a full cast rebuild also picks them up
automatically when the folder exists.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BLENDER_SCRIPT = os.path.join(REPO, "Tools", "retarget_fab_anime_blender.py")


def find_blender(explicit=None):
    if explicit:
        return explicit
    if os.environ.get("BLENDER"):
        return os.environ["BLENDER"]
    found = shutil.which("blender")
    if found:
        return found
    roots = [
        r"C:\Program Files\Blender Foundation",
        r"C:\Program Files\Blender Foundation\Blender",
    ]
    for root in roots:
        if not os.path.isdir(root):
            continue
        versions = sorted(
            (os.path.join(root, name) for name in os.listdir(root)
             if os.path.isdir(os.path.join(root, name))),
            reverse=True,
        )
        for folder in versions:
            exe = os.path.join(folder, "blender.exe")
            if os.path.isfile(exe):
                return exe
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blender", help="path to blender.exe")
    args = parser.parse_args(argv)

    blender = find_blender(args.blender)
    if not blender or not os.path.isfile(blender):
        print("retarget_fab_anime: could not find Blender. Pass --blender or set BLENDER.",
              file=sys.stderr)
        return 2
    print(f"retarget_fab_anime: using {blender}")
    result = subprocess.run(
        [blender, "--background", "--factory-startup", "--python", BLENDER_SCRIPT],
        cwd=REPO,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
