"""Build the three-year Forbidden/Limited list from the public guide table."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from canon_common import CANON_DIR, CACHE_DIR, ensure_dirs, read_json, utc_now, write_json

GUIDE = "https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Banned_List"


def status(value: str) -> str:
    value = value.strip("{} ")
    if "|" in value:
        value = value.split("|")[-1]
    return value.strip().replace("Semi-limited", "Semi-Limited")


def parse_rows(text: str) -> list[dict]:
    rows = []
    block: list[str] = []
    for line in text.splitlines() + ["|-"]:
        if line.startswith("|-"):
            if len(block) >= 5:
                number, name_line = block[0], block[1]
                num_match = re.search(r"\d{3,4}", number)
                name_match = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", name_line)
                if num_match and name_match:
                    rows.append({
                        "card_id": int(num_match.group()),
                        "name": (name_match.group(2) or name_match.group(1)).strip(),
                        "wiki_link": name_match.group(1).strip(),
                        "year_1": status(block[2]),
                        "year_2": status(block[3]),
                        "year_3": status(block[4]),
                    })
            block = []
            continue
        if line.startswith("|"):
            block.append(line[1:].strip())
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path,
                        default=Path(r"C:\Users\Sebas\AppData\Local\Temp\opencode\gxcanon\guide_wikitext.json"))
    args = parser.parse_args()
    ensure_dirs()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "banned_facts.json"
    if cache_path.exists():
        rows = read_json(cache_path)["rows"]
    else:
        text = read_json(args.source)["Yu-Gi-Oh! GX Duel Academy/Banned List"]
        rows = parse_rows(text)
        write_json(cache_path, {"schema_version": 1, "source": GUIDE, "rows": rows})

    records = [{
        "card_id": row["card_id"],
        "name": row["name"],
        "status": {
            "year_1": row["year_1"],
            "year_2": row["year_2"],
            "year_3": row["year_3"],
        },
        "source": GUIDE,
        "confidence": "high",
    } for row in rows]

    status_counts: dict[str, dict[str, int]] = {}
    for record in records:
        for year, value in record["status"].items():
            status_counts.setdefault(year, {}).setdefault(value, 0)
            status_counts[year][value] += 1

    write_json(CANON_DIR / "banned_list.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": GUIDE,
        "notes": [
            "Three school years are tracked separately; the list changes between years.",
            "Status values are Forbidden, Limited, Semi-Limited or Unlimited.",
        ],
        "count": len(records),
        "status_counts": status_counts,
        "cards": records,
    })
    print(f"banned/limited cards: {len(records)}")
    print(status_counts)
    return 0


if __name__ == "__main__":
    sys.exit(main())
