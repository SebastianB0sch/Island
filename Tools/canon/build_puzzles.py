"""Build the 100 timed-duel records from the public puzzle pages.

The guide publishes solution steps but not the initial hands/fields. Those
setups must come from the ROM puzzle table (not yet decoded) or in-game
observation; every record says so explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from canon_common import CANON_DIR, CACHE_DIR, ensure_dirs, read_json, utc_now, write_json

PAGE = "Yu-Gi-Oh! GX Duel Academy Puzzle: {:03d}"
GUIDE = "https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_{:03d}"


def norm(name: str) -> str:
    name = name.replace("’", "'")
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load_lookup() -> tuple[dict[int, str], dict[str, int], dict[str, int]]:
    cards = read_json(CANON_DIR.parent / "cards.json")
    by_id = {int(c["id"]): c["name"] for c in cards}
    by_name = {norm(c["name"]): int(c["id"]) for c in cards}
    aliases_raw = read_json(Path(__file__).with_name("card_aliases.json"))["aliases"]
    aliases = {norm(k): v for k, v in aliases_raw.items() if v is not None}
    return by_id, by_name, aliases


def resolve(name: str, by_name: dict[str, int], aliases: dict[str, int]) -> int | None:
    key = norm(name)
    return aliases.get(key, by_name.get(key))


def parse_steps(text: str) -> list[dict]:
    def make_step(body: str) -> dict | None:
        body = re.sub(r"^Step\s*\d+\s*:\s*", "", body.strip(), flags=re.I)
        body = body.strip()
        if not body or body.lower().rstrip(".") in {"piece of cake", "win", "victory"}:
            return None
        links = []
        for link in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", body):
            links.append((link.group(2) or link.group(1)).strip())
        clean = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", body)
        clean = re.sub(r"\[\[([^\]]+)\]\]", r"\1", clean)
        return {"text": clean, "card_names": links}

    steps = []
    for line in text.splitlines():
        line = line.strip()
        match = re.match(r"^(?:\d+[.)]|[*#-])\s*(.+)$", line)
        if not match:
            continue
        step = make_step(match.group(1))
        if step:
            steps.append(step)
    if steps:
        return steps

    # Some pages use paragraphs with "Step N:" prefixes instead of a list.
    body = re.sub(r"\[\[Category:[^\]]+\]\]", "", text)
    for paragraph in re.split(r"\n\s*\n", body):
        step = make_step(paragraph)
        if step:
            steps.append(step)
    return steps


def write_puzzles(records: list[dict]) -> None:
    unresolved = [r["id"] for r in records if not r["solution_steps"]]
    write_json(CANON_DIR / "puzzles.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {
            "list": "https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Timed_Duel_List",
            "solutions": "https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy_Puzzle:_NNN",
        },
        "summary": {
            "count": len(records),
            "by_level": {str(level): sum(1 for r in records if r["level"] == level) for level in range(1, 6)},
            "with_solution": len(records) - len(unresolved),
            "without_solution": unresolved,
            "setup_status": "unknown for all records; ROM puzzle table not decoded",
        },
        "puzzles": records,
    })
    print(f"puzzles: {len(records)}  solutions: {len(records) - len(unresolved)}")
    print("without solution:", unresolved)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path,
                        default=Path(r"C:\Users\Sebas\AppData\Local\Temp\opencode\gxcanon\guide_wikitext.json"))
    args = parser.parse_args()
    ensure_dirs()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "puzzles_facts.json"
    if cache_path.exists():
        records = read_json(cache_path)["puzzles"]
        by_id, by_name, aliases = load_lookup()
        write_puzzles(records)
        return 0

    source = read_json(args.source)
    by_id, by_name, aliases = load_lookup()

    records = []
    for number in range(1, 101):
        title = PAGE.format(number)
        text = source.get(title, "")
        steps = parse_steps(text)
        card_names = sorted({name for step in steps for name in step["card_names"]})
        card_ids = sorted({
            cid for cid in (resolve(name, by_name, aliases) for name in card_names)
            if cid is not None
        })
        payload = json.dumps({"id": f"P{number:03d}", "steps": [s["text"] for s in steps]},
                             sort_keys=True).encode("utf-8")
        records.append({
            "id": f"P{number:03d}",
            "level": (number - 1) // 20 + 1,
            "opponent": "mimicry",
            "turn_limit": 1,
            "time_limit_seconds": None,
            "setup": None,
            "objective": "win_during_your_turn",
            "solution_steps": steps,
            "solution_card_names": card_names,
            "solution_card_ids": card_ids,
            "reward": None,
            "source": GUIDE.format(number),
            "confidence": {
                "solution": "high" if steps else "low",
                "setup": "unknown",
                "limits": "low",
                "reward": "low",
            },
            "sha256": hashlib.sha256(payload).hexdigest(),
            "gap": None if steps else "No guide solution extracted; page may be missing or formatted differently.",
        })

    write_json(cache_path, {
        "schema_version": 1,
        "source": "Yugipedia puzzle pages",
        "puzzles": records,
    })
    write_puzzles(records)
    return 0


if __name__ == "__main__":
    sys.exit(main())
