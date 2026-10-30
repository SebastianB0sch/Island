"""Optional network refresh of the public-guide wikitext snapshot.

The normal build is offline and uses Tools/canon/cache/*.json. This script is
only for maintaining those caches. It writes the raw wikitext outside the
repository by default because it is copyrighted reference material.

Usage:
    python Tools/canon/fetch_guides.py
    python Tools/canon/fetch_guides.py --out C:\\path\\guide_wikitext.json
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from canon_common import LOCAL_ONLY_DIR

API = "https://yugipedia.com/api.php"
UA = "GXCanonResearch/0.1 (local canon verification)"

PACKS = [
    "Basic 1-A", "Basic 1-B", "Basic 2-A", "Basic 2-B", "Basic 3-A", "Basic 3-B",
    "Basic 4-A", "Basic 4-B", "Basic 1-C", "Basic 2-C", "Basic 3-C", "Basic 4-C",
    "Effect Monsters (GX1-BP)", "Various Fields (GX1-BP)", "Equipments (GX1-BP)",
    "Fusions (GX1-BP)", "Rituals (GX1-BP)", "Continuous Effects (GX1-BP)",
    "Spell Collection 1 (GX1-BP)", "Spell Collection 2 (GX1-BP)",
    "Trap Collection 1 (GX1-BP)", "Trap Collection 2 (GX1-BP)",
    "Spell Special 1 (GX1-BP)", "Spell Special 2 (GX1-BP)",
    "Trap Special 1 (GX1-BP)", "Trap Special 2 (GX1-BP)",
    "Expert I (GX1-BP)", "Expert II (GX1-BP)", "Expert III (GX1-BP)",
    "Expert IV (GX1-BP)", "Power Destructions (GX1-BP)",
    "Effect Monsters Special (GX1-BP)", "Master Fusions (GX1-BP)",
    "The HERO (GX1-BP)", "Live Vehicles (GX1-BP)", "Be Quick (GX1-BP)",
    "Special Ways (GX1-BP)", "Dorothy's Gift (GX1-BP)",
    "Residents of the Sea (GX1-BP)", "Invitation to the Dark (GX1-BP)",
    "Pyrogen", "Fairy Dance", "Insect's Nest (GX1-BP)",
    "Dragons in Flight (GX1-BP)", "Beasts in Fight (GX1-BP)",
    "The Warriors (GX1-BP)", "The Machines (GX1-BP)",
    "Spellcaster's Dance (GX1-BP)",
]

PAGES = [
    "Yu-Gi-Oh! GX Duel Academy/Events",
    "Yu-Gi-Oh! GX Duel Academy/Banned List",
    "Yu-Gi-Oh! GX Duel Academy/Starter Decks",
    "Yu-Gi-Oh! GX Duel Academy/Opponents",
    "Yu-Gi-Oh! GX Duel Academy/Booster Pack List",
] + PACKS + [f"Yu-Gi-Oh! GX Duel Academy Puzzle: {i:03d}" for i in range(1, 101)]


def fetch(title: str) -> tuple[str, str]:
    url = API + "?" + urllib.parse.urlencode({
        "action": "parse", "page": title, "prop": "wikitext",
        "format": "json", "formatversion": "2", "redirects": "1",
    })
    request = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                data = json.load(response)
            return title, data.get("parse", {}).get("wikitext", "")
        except Exception:  # noqa: BLE001
            time.sleep(8 + attempt * 8)
    return title, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=LOCAL_ONLY_DIR / "guide_wikitext.json")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    if args.out.exists():
        cache = json.loads(args.out.read_text(encoding="utf-8"))
    todo = [page for page in PAGES if not cache.get(page)]
    print(f"{len(cache)} cached, {len(todo)} to fetch")
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed({pool.submit(fetch, page): page for page in todo}):
            title, text = future.result()
            cache[title] = text
    args.out.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    empty = [page for page in PAGES if not cache.get(page)]
    print(f"wrote {args.out}; empty={len(empty)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
