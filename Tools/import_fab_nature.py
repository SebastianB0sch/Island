"""Install the licensed Fab nature / prop packs into the local UE project.

The packs are **not redistributable**.  This script copies only the content used
by the island from the local donor project:

    StyleHex_Studio/Free_Packs/FREE_Stylized_Forest_Sample  -> Content/StyleHex_Studio
    Stylized_PBR_Nature/Foliage                             -> Content/Stylized_PBR_Nature/Foliage
    Stylized_PBR_Nature/Rocks                               -> Content/Stylized_PBR_Nature/Rocks
    TropicalGardenLounge/Vegetation                         -> Content/TropicalGardenLounge/Vegetation
    CollegeRaimon                                           -> Content/CollegeRaimon

The destinations are gitignored.  Without them the build falls back to the
native procedural trees/grass and the curated CC0 props (the same behaviour as
a fresh checkout).

    python Tools/import_fab_nature.py
    python Tools/import_fab_nature.py --source "D:/Fab/Content"
    python Tools/import_fab_nature.py --force
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCE = r"C:\dev\argh\ue5\Content"
CONTENT = os.path.join(REPO, "DuelAcademyIsland", "Content")

# (source relative to --source, destination relative to Content, marker file, label)
PACKS = (
    ("StyleHex_Studio", "StyleHex_Studio",
     os.path.join("Free_Packs", "FREE_Stylized_Forest_Sample", "Meshes", "Trees", "SM_Tree_Birch_1.uasset"),
     "StyleHex FREE Stylized Forest Sample"),
    ("Stylized_PBR_Nature/Foliage", "Stylized_PBR_Nature/Foliage",
     os.path.join("Assets", "SM_Common_Tree_01.uasset"),
     "Stylized PBR Nature - Foliage"),
    ("Stylized_PBR_Nature/Rocks", "Stylized_PBR_Nature/Rocks",
     os.path.join("Assets", "SM_R_Rock_01.uasset"),
     "Stylized PBR Nature - Rocks"),
    ("TropicalGardenLounge/Vegetation", "TropicalGardenLounge/Vegetation",
     os.path.join("StaticMeshes", "SM_PlamTree.uasset"),
     "Tropical Garden Lounge - Vegetation"),
    ("TropicalGardenLounge/Misc", "TropicalGardenLounge/Misc",
     os.path.join("Materials", "M_BaseColor_Normal.uasset"),
     "Tropical Garden Lounge - Shared materials"),
    ("CollegeRaimon", "CollegeRaimon",
     os.path.join("Meshes", "SM_ao127_01.uasset"),
     "College Raimon (Fab environment)"),
)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help="folder containing the donor project's Content (default: %(default)s)")
    parser.add_argument("--force", action="store_true", help="replace an existing install")
    args = parser.parse_args(argv)

    source_root = os.path.abspath(args.source)
    if not os.path.isdir(source_root):
        print(f"import_fab_nature: source not found: {source_root}", file=sys.stderr)
        print("Set --source to the donor project's Content folder.", file=sys.stderr)
        return 2

    missing = []
    for rel_source, _rel_dest, marker, label in PACKS:
        marker_path = os.path.join(source_root, rel_source, marker)
        if not os.path.isfile(marker_path):
            missing.append(f"{label}: {marker_path}")
    if missing:
        print("import_fab_nature: the donor folder does not look like the expected packs:",
              file=sys.stderr)
        for line in missing:
            print("  missing " + line, file=sys.stderr)
        return 2

    for rel_source, rel_dest, _marker, label in PACKS:
        source = os.path.join(source_root, rel_source)
        dest = os.path.join(CONTENT, rel_dest)
        if os.path.isdir(dest) and not args.force:
            print(f"import_fab_nature: {label} already installed at {dest} (use --force to replace)")
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if os.path.isdir(dest) and args.force:
            shutil.rmtree(dest)
        print(f"import_fab_nature: copying {source} -> {dest}")
        shutil.copytree(source, dest)
        note = os.path.join(dest, "SOURCE.txt")
        with open(note, "w", encoding="utf-8", newline="\n") as fp:
            fp.write(
                f"{label}\n"
                "Licensed Fab marketplace content. Installed locally by Tools/import_fab_nature.py.\n"
                "Do not redistribute. This folder is excluded by .gitignore.\n"
            )

    print("import_fab_nature: installed. Restart the Unreal editor, then rebuild the level.")
    print("import_fab_nature: WARNING: licensed Fab content - do not commit or redistribute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
