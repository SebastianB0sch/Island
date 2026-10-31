#!/usr/bin/env python3
"""Sync A06 economy data from A01's read-only Canon extraction.

This script never edits Content/Data/Canon/. It regenerates:

  Content/Data/Shop/packs.json          (canon packs + A06 slot/odds overlay)
  Content/Data/Rules/card_rarity.json   (rarity hint for trunk filters)
  Content/Data/Rules/banned_limited.json(year 1 banned/limited list)

Run from the repo root:

  python Tools/economy/sync_canon.py

A01 remains the source of truth for ids, pools, prices and unlock text. A06
owns the slot layout / odds overlay and the deck rules wrapper.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DuelAcademyIsland" / "Content" / "Data"
CANON_PACKS = DATA / "Canon" / "packs.json"
CANON_BANNED = DATA / "Canon" / "banned_list.json"
SHOP_PACKS = DATA / "Shop" / "packs.json"
RULES = DATA / "Rules" / "banned_limited.json"
RARITY = DATA / "Rules" / "card_rarity.json"
CARDS = DATA / "cards.json"
DECKS = DATA / "decks.json"

RARITY_ORDER = ["Common", "Rare", "SuperRare", "UltraRare", "SecretRare"]
RARITY_MAP = {
    "Common": "Common",
    "Rare": "Rare",
    "Super Rare": "SuperRare",
    "Ultra Rare": "UltraRare",
    "Secret Rare": "SecretRare",
}

# Canon calendar descriptions -> school-year month index (1 = October).
CALENDAR_MONTHS = {
    "basic_3a": 1,
    "basic_3b": 2,
    "basic_4a": 4,
    "basic_4b": 5,
    "basic_1c": 6,
    "basic_2c": 7,
    "basic_3c": 8,
    "basic_4c": 9,
}


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def restock_days(text: str | None, fallback: int) -> int:
    if not text:
        return fallback
    text = text.lower()
    if "four weeks" in text:
        return 28
    if "three weeks" in text:
        return 21
    if "two weeks" in text:
        return 14
    return 7


def main() -> int:
    if not CANON_PACKS.exists():
        print(f"missing canon packs: {CANON_PACKS}", file=sys.stderr)
        return 1
    if not CANON_BANNED.exists():
        print(f"missing canon banned list: {CANON_BANNED}", file=sys.stderr)
        return 1

    canon = load(CANON_PACKS)
    shop = load(SHOP_PACKS)
    banned = load(CANON_BANNED)
    cards = load(CARDS)

    rank = {rarity: index for index, rarity in enumerate(RARITY_ORDER)}
    rarity_by_card: dict[int, str] = {}
    for canon_pack in canon["packs"]:
        if canon_pack.get("full_pool"):
            continue
        for entry in canon_pack.get("pool", []):
            rarity = RARITY_MAP.get(entry.get("rarity", ""))
            card_id = entry.get("card_id")
            if not rarity or not isinstance(card_id, int) or card_id <= 0:
                continue
            if card_id not in rarity_by_card or rank[rarity] > rank[rarity_by_card[card_id]]:
                rarity_by_card[card_id] = rarity
    for card in cards:
        rarity_by_card.setdefault(int(card["id"]), "Common")

    old_by_name = {pack["name"]: pack for pack in shop["packs"]}
    old_by_id = {pack["id"]: pack for pack in shop["packs"]}

    new_packs = []
    for canon_pack in canon["packs"]:
        old = old_by_name.get(canon_pack["name"]) or old_by_id.get(canon_pack["id"])
        if not old:
            print(f"no slot template for {canon_pack['name']}", file=sys.stderr)
            return 1

        pools = {rarity: [] for rarity in RARITY_ORDER}
        for entry in canon_pack.get("pool", []):
            rarity = RARITY_MAP.get(entry.get("rarity", ""))
            card_id = entry.get("card_id")
            if rarity and isinstance(card_id, int) and card_id > 0 and card_id not in pools[rarity]:
                pools[rarity].append(card_id)
        for rarity in pools:
            pools[rarity].sort()

        conditions = old.get("unlock", {}).get("conditions", [])
        if canon_pack["id"] in CALENDAR_MONTHS:
            conditions = [{"type": "month_at_least", "key": "", "value": CALENDAR_MONTHS[canon_pack["id"]]}]

        pack = {
            "id": canon_pack["id"],
            "name": canon_pack["name"],
            "category": canon_pack["category"],
            "price": canon_pack["price_dp"],
            "pack_size": canon_pack["cards_per_pack"],
            "restock_days": restock_days(canon_pack.get("restock"), old.get("restock_days", 7)),
            "purchase_limit": old.get("purchase_limit", 1),
            "stock": int(canon_pack.get("stock") or 0),
            "unlock": {
                "description": canon_pack.get("unlock", {}).get("raw") or old.get("unlock", {}).get("description", ""),
                "conditions": conditions,
            },
            "slots": old["slots"],
            "pools": [{"rarity": rarity, "cards": pools.get(rarity, [])} for rarity in RARITY_ORDER],
            "canon_status": "provisional",
            "source": "Content/Data/Canon/packs.json (A01) + A06 provisional slots/odds",
        }
        if canon_pack["id"] == "dorothys_gift":
            # Canon/packs.json marks this pack full_pool=true with a declared
            # 1,200-card pool. Materialise the exact ids instead of leaving an
            # empty pools array; every card has copy weight 1 (uniform).
            all_card_ids = sorted(int(card["id"]) for card in cards)
            pools = {rarity: [] for rarity in RARITY_ORDER}
            for card_id in all_card_ids:
                pools[rarity_by_card.get(card_id, "Common")].append(card_id)
            pack["pools"] = [
                {"rarity": rarity, "cards": pools[rarity]} for rarity in RARITY_ORDER
            ]
            pack["all_cards"] = True
            pack["prefer_unowned"] = True
            pack["pool_status"] = "canon_full_pool"
            pack["pool_note"] = (
                "Canon/packs.json full_pool=true declares all 1,200 cards; "
                "each card has copy weight 1 (uniform), no per-card canon weights."
            )
            pack["pool_card_count"] = len(all_card_ids)
            pack["pool_copy_weight"] = 1
        new_packs.append(pack)

    if len(new_packs) != 48:
        print(f"expected 48 packs, generated {len(new_packs)}", file=sys.stderr)
        return 1

    shop["packs"] = new_packs
    shop["source"] = "Content/Data/Canon/packs.json (A01) + A06 provisional slot/odds overlay."
    shop["canon_status"] = "provisional"
    shop["notes"] = [
        "Pack ids, names, categories, prices, pack sizes and pools come from A01's Canon/packs.json.",
        "Rarity/slot layout and rare-plus weights remain provisional; A01 marks odds_status unresolved.",
        "Unlock descriptions are A01 canon raw text; structured condition keys are port integration hooks.",
        "Calendar packs use month_at_least until A02 exposes exact last-week/day windows.",
        "Dorothy's Gift materialises A01's full_pool=true as all 1,200 card ids at copy weight 1; any-card slots still prefer unowned cards.",
    ]
    write(SHOP_PACKS, shop)

    write(
        RARITY,
        {
            "schema": 1,
            "canon_status": "provisional",
            "source": "Derived from Content/Data/Canon/packs.json pools (highest rarity per card).",
            "notes": "Global rarity is only a collection/filter hint. A card can have different rarities in different packs.",
            "rarities": [
                {"card_id": card_id, "rarity": rarity_by_card[card_id]}
                for card_id in sorted(rarity_by_card)
            ],
        },
    )

    banned_ids = []
    limited = []
    semi_limited = []
    for card in banned["cards"]:
        status = card.get("status", {}).get("year_1", "Unlimited")
        card_id = card["card_id"]
        if status == "Forbidden":
            banned_ids.append({"card_id": card_id, "name": card.get("name", ""), "reason": "GX1 year 1 Forbidden"})
        elif status == "Limited":
            limited.append({"card_id": card_id, "limit": 1, "name": card.get("name", ""), "reason": "GX1 year 1 Limited"})
        elif status == "Semi-Limited":
            semi_limited.append({"card_id": card_id, "limit": 2, "name": card.get("name", ""), "reason": "GX1 year 1 Semi-Limited"})

    write(
        RULES,
        {
            "schema": 1,
            "canon_status": "canon_year_1",
            "source": "Content/Data/Canon/banned_list.json (A01, Yugipedia GX1 banned list), year_1 statuses.",
            "notes": "Year 1 list is applied to deck construction. Year 2/3 lists remain in Canon/banned_list.json for later story phases.",
            "max_owned_copies": 3,
            "rules": {
                "min_main": 40,
                "max_main": 60,
                "max_extra": 15,
                "max_copies": 3,
                "max_side": 0,
                "max_player_decks": 24,
                "deck_name_min_length": 1,
                "deck_name_max_length": 24,
            },
            "banned": banned_ids,
            "limited": limited,
            "semi_limited": semi_limited,
            "schema_notes": {
                "banned": "Array of card ids or {card_id, name, reason}. Forbidden in year 1.",
                "limited": "Array of {card_id, limit, name, reason}; limit is 1.",
                "semi_limited": "Array of {card_id, limit, name, reason}; limit is 2.",
            },
        },
    )

    # Sanity: the default player deck must be legal under the year 1 list.
    banned_set = {entry["card_id"] for entry in banned_ids}
    limited_map = {entry["card_id"]: entry["limit"] for entry in limited}
    semi_map = {entry["card_id"]: entry["limit"] for entry in semi_limited}
    for deck in load(DECKS):
        counts: dict[int, int] = {}
        for card_id in deck["cards"]:
            counts[card_id] = counts.get(card_id, 0) + 1
        for card_id, count in counts.items():
            if card_id in banned_set:
                print(f"WARNING: {deck['id']} contains forbidden card {card_id}", file=sys.stderr)
            if card_id in limited_map and count > limited_map[card_id]:
                print(f"WARNING: {deck['id']} exceeds limited card {card_id}", file=sys.stderr)
            if card_id in semi_map and count > semi_map[card_id]:
                print(f"WARNING: {deck['id']} exceeds semi-limited card {card_id}", file=sys.stderr)

    print(f"synced {len(new_packs)} packs, {len(banned_ids)} forbidden, {len(limited)} limited, {len(semi_limited)} semi-limited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
