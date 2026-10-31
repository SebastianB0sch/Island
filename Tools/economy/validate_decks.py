#!/usr/bin/env python3
"""Validate A06 player decks against the Year 1 rules and 15-card Extra Deck.

The A06 catalogue has two player-facing deck sources:

  Content/Data/decks.json              starter decks offered during onboarding
  Content/Data/Decks/player_decks.json default player deck slots

The checks mirror the runtime deck rules plus the player-deck name-copy rule:
main 40..60, Extra <= 15, Side <= 0, 3 copies by id and by printed name,
Year 1 forbidden/limited/semi-limited lists, and known card ids.

Run from the repo root:

  python Tools/economy/validate_decks.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DuelAcademyIsland" / "Content" / "Data"
RULES = DATA / "Rules" / "banned_limited.json"
CARDS = DATA / "cards.json"
STARTER_DECKS = DATA / "decks.json"
PLAYER_DECKS = DATA / "Decks" / "player_decks.json"

SLUG_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> int:
    failures: list[str] = []
    checks = 0

    def check(ok: bool, code: str, detail: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(f"{code}: {detail}")

    rules_doc = load(RULES)
    rules = rules_doc.get("rules", {}) or {}
    cards = load(CARDS)
    card_names = {int(card["id"]): str(card.get("name", "")) for card in cards}
    card_ids = set(card_names)

    max_extra = int(rules.get("max_extra", 0))
    max_copies = int(rules.get("max_copies", 0))
    max_side = int(rules.get("max_side", 0))
    min_main = int(rules.get("min_main", 0))
    max_main = int(rules.get("max_main", 0))
    check(max_extra == 15, "rules.max_extra", f"max_extra is {max_extra}, expected 15")
    check(max_copies == 3, "rules.max_copies", f"max_copies is {max_copies}, expected 3")

    forbidden = {int(entry["card_id"]) for entry in rules_doc.get("banned", []) if "card_id" in entry}
    limited = {
        int(entry["card_id"]): int(entry.get("limit", 1))
        for entry in rules_doc.get("limited", [])
        if "card_id" in entry
    }
    semi_limited = {
        int(entry["card_id"]): int(entry.get("limit", 2))
        for entry in rules_doc.get("semi_limited", [])
        if "card_id" in entry
    }

    deck_records: list[tuple[str, dict, str]] = []
    for deck in load(STARTER_DECKS):
        deck_records.append(("Content/Data/decks.json", deck, "cards"))
    player_doc = load(PLAYER_DECKS)
    for deck in player_doc.get("decks", []):
        deck_records.append(("Content/Data/Decks/player_decks.json", deck, "main"))

    seen_ids: set[str] = set()
    for source, deck, main_key in deck_records:
        deck_id = str(deck.get("id") or "")
        where = f"{deck_id!r} ({source})"
        check(bool(SLUG_RE.match(deck_id)), "deck.id", f"{where} has an invalid id")
        check(deck_id not in seen_ids, "deck.duplicate_id", f"{where} is duplicated")
        seen_ids.add(deck_id)
        check(
            isinstance(deck.get("name"), str) and bool(deck["name"].strip()),
            "deck.name",
            f"{where} has no name",
        )

        main = deck.get(main_key, [])
        extra = deck.get("extra", [])
        side = deck.get("side", [])
        check(isinstance(main, list), "deck.main_shape", f"{where} main is not an array")
        check(isinstance(extra, list), "deck.extra_shape", f"{where} extra is not an array")
        check(isinstance(side, list), "deck.side_shape", f"{where} side is not an array")
        main = main if isinstance(main, list) else []
        extra = extra if isinstance(extra, list) else []
        side = side if isinstance(side, list) else []

        check(
            min_main <= len(main) <= max_main,
            "deck.main_size",
            f"{where} has {len(main)} main cards (expected {min_main}..{max_main})",
        )
        check(
            len(extra) <= max_extra,
            "deck.extra_size",
            f"{where} has {len(extra)} Extra Deck cards (max {max_extra})",
        )
        check(
            len(side) <= max_side,
            "deck.side_size",
            f"{where} has {len(side)} Side Deck cards (max {max_side})",
        )

        all_ids: list[int] = []
        unknown: list[int] = []
        for card_id in main + extra + side:
            if not isinstance(card_id, int) or isinstance(card_id, bool):
                unknown.append(card_id)
                continue
            all_ids.append(card_id)
            if card_id not in card_ids:
                unknown.append(card_id)
        check(not unknown, "deck.card_ref", f"{where} has invalid card ids {unknown[:10]}")

        id_counts = Counter(all_ids)
        over_ids = {card_id: count for card_id, count in id_counts.items() if count > max_copies}
        check(not over_ids, "deck.copy_limit", f"{where} exceeds the id copy limit: {sorted(over_ids.items())}")

        name_counts = Counter(card_names.get(card_id, f"#{card_id}") for card_id in all_ids)
        over_names = {name: count for name, count in name_counts.items() if count > max_copies}
        check(not over_names, "deck.name_copy_limit", f"{where} exceeds the printed-name copy limit: {sorted(over_names.items())}")

        banned_hits = sorted(card_id for card_id in id_counts if card_id in forbidden)
        check(not banned_hits, "deck.forbidden", f"{where} contains forbidden cards {banned_hits}")
        limited_hits = sorted(
            card_id for card_id, count in id_counts.items() if card_id in limited and count > limited[card_id]
        )
        check(not limited_hits, "deck.limited", f"{where} exceeds Limited limits {limited_hits}")
        semi_hits = sorted(
            card_id for card_id, count in id_counts.items() if card_id in semi_limited and count > semi_limited[card_id]
        )
        check(not semi_hits, "deck.semi_limited", f"{where} exceeds Semi-Limited limits {semi_hits}")

        for card_id in extra:
            card = next((c for c in cards if int(c["id"]) == card_id), None)
            if card and card.get("card_type") != "Fusion Monster":
                check(False, "deck.extra_type", f"{where} has non-Fusion card {card_id} in the Extra Deck")
        for card_id in main:
            card = next((c for c in cards if int(c["id"]) == card_id), None)
            if card and card.get("card_type") == "Fusion Monster":
                check(False, "deck.fusion_in_main", f"{where} has Fusion card {card_id} in the main deck")

        if deck_id == "jaden":
            luster = name_counts.get("Luster Dragon", 0)
            check(luster == 3, "jaden.luster_dragon", f"jaden has {luster} printed Luster Dragon copies (expected 3)")
            check(id_counts.get(663, 0) == 1, "jaden.card_663", f"jaden has {id_counts.get(663, 0)} copies of 663")
            check(id_counts.get(780, 0) == 2, "jaden.card_780", f"jaden has {id_counts.get(780, 0)} copies of 780")
            check(id_counts.get(1109, 0) == 3, "jaden.card_1109", f"jaden has {id_counts.get(1109, 0)} copies of 1109")

    print("A06 player deck validation")
    print(
        f"  decks: {len(deck_records)}  Year 1 rules: main {min_main}..{max_main}, "
        f"Extra <= {max_extra}, copies <= {max_copies}"
    )
    if failures:
        print(f"RESULT: FAIL - {len(failures)} issue(s) across {checks} checks")
        for failure in failures[:80]:
            print(f"  - {failure}")
        if len(failures) > 80:
            print(f"  ... {len(failures) - 80} more")
        return 1
    print(f"RESULT: PASS - {checks} checks, 0 failures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
