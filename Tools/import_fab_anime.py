"""Install the licensed Fab Anime Character Pack into the local UE project.

The pack is **not redistributable**.  This script copies it from the local
donor project into `DuelAcademyIsland/Content/AnimeCharacters`, which is
gitignored.  The game falls back to the native GX cast when the folder is
absent, so a fresh checkout still runs.

    python Tools/import_fab_anime.py
    python Tools/import_fab_anime.py --source "D:/Fab/AnimeCharacterPack"
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SOURCE = r"C:\dev\argh\ue5\Content\AnimeCharacters"
DEST = os.path.join(REPO, "DuelAcademyIsland", "Content", "AnimeCharacters")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE,
                        help="folder containing the Fab Anime Character Pack (Content/AnimeCharacters)")
    parser.add_argument("--force", action="store_true", help="overwrite an existing install")
    args = parser.parse_args(argv)

    source = os.path.abspath(args.source)
    if not os.path.isdir(source):
        print(f"import_fab_anime: source not found: {source}", file=sys.stderr)
        print("Set --source to the AnimeCharacters folder from your Fab install.", file=sys.stderr)
        return 2
    blueprint = os.path.join(source, "Blueprints", "Characters", "bp_AnimeCharacter.uasset")
    if not os.path.isfile(blueprint):
        print(f"import_fab_anime: {source} does not look like the Anime Character Pack "
              "(missing Blueprints/Characters/bp_AnimeCharacter.uasset)", file=sys.stderr)
        return 2
    if os.path.isdir(DEST) and not args.force:
        print(f"import_fab_anime: already installed at {DEST} (use --force to replace)")
        return 0

    os.makedirs(os.path.dirname(DEST), exist_ok=True)
    if os.path.isdir(DEST) and args.force:
        shutil.rmtree(DEST)
    print(f"import_fab_anime: copying {source} -> {DEST}")
    shutil.copytree(source, DEST)
    note = os.path.join(DEST, "SOURCE.txt")
    with open(note, "w", encoding="utf-8", newline="\n") as fp:
        fp.write(
            "Fab Anime Character Pack (Legacy)\n"
            "Licensed marketplace content. Installed locally by Tools/import_fab_anime.py.\n"
            "Do not redistribute. This folder is excluded by .gitignore.\n"
        )
    print("import_fab_anime: installed. Restart the Unreal editor, then rebuild the level.")
    print("import_fab_anime: WARNING: licensed Fab content - do not commit or redistribute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
