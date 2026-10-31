#!/usr/bin/env python3
"""Validate A06's 48-pack shop catalogue.

Checks the runtime catalogue against the read-only canon extraction and the
1,200-card database:

  * every pack has a materialised, non-empty pool;
  * every pool card id exists and appears once per pack;
  * fixed slots have a matching rarity pool and rare-plus weights are sane;
  * price, stock, restock, purchase limit, unlock text and conditions exist;
  * every pack category is a known canon set family (no missing set);
  * Dorothy's Gift materialises the canon full pool (all 1,200 cards, weight 1).

Run from the repo root:

  python Tools/economy/validate_packs.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DuelAcademyIsland" / "Content" / "Data"
SHOP_PACKS = DATA / "Shop" / "packs.json"
CANON_PACKS = DATA / "Canon" / "packs.json"
CARDS = DATA / "cards.json"
RARITY = DATA / "Rules" / "card_rarity.json"

RARITY_ORDER = ["Common", "Rare", "SuperRare", "UltraRare", "SecretRare"]
RARITY_KEYS = {name.replace(" ", "").lower(): name for name in RARITY_ORDER}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
UNLOCK_TYPES = {
    "start",
    "tutorial",
    "event",
    "counter",
    "title",
    "dorm_changes",
    "visited_all_dorms",
    "pack_completion",
    "collection_percent",
    "location_duels",
    "month_at_least",
    "flag",
}


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def canonical_rarity(text) -> str | None:
    if not isinstance(text, str):
        return None
    return RARITY_KEYS.get(text.replace("_", "").replace(" ", "").lower())


def flatten_pool(pack: dict) -> list[tuple[int, str]]:
    entries: list[tuple[int, str]] = []
    for group in pack.get("pools", []) or []:
        if not isinstance(group, dict):
            continue
        rarity = canonical_rarity(group.get("rarity"))
        for card_id in group.get("cards", []) or []:
            entries.append((card_id, rarity or "?"))
    return entries


def main() -> int:
    failures: list[str] = []
    checks = 0

    def check(ok: bool, code: str, detail: str) -> None:
        nonlocal checks
        checks += 1
        if not ok:
            failures.append(f"{code}: {detail}")

    shop = load(SHOP_PACKS)
    canon = load(CANON_PACKS)
    cards = load(CARDS)
    rarity_doc = load(RARITY)

    card_ids = {int(card["id"]) for card in cards}
    card_rarity = {
        int(entry["card_id"]): can
        for entry in rarity_doc.get("rarities", [])
        if (can := canonical_rarity(entry.get("rarity"))) is not None
    }
    canon_by_id = {str(pack.get("id")): pack for pack in canon.get("packs", [])}
    canon_categories = {str(pack.get("category")) for pack in canon.get("packs", [])}
    packs = shop.get("packs", [])
    defaults = shop.get("defaults", {}) or {}
    default_weights = defaults.get("rare_plus_weights", []) or []

    check(len(packs) == 48, "shop.pack_count", f"expected 48 packs, found {len(packs)}")
    check(len(card_ids) == 1200, "cards.count", f"expected 1,200 cards, found {len(card_ids)}")
    check(
        len(canon_by_id) == 48,
        "canon.pack_count",
        f"expected 48 canon packs, found {len(canon_by_id)}",
    )

    default_positive = 0
    for weight in default_weights:
        value = weight.get("weight", 0) if isinstance(weight, dict) else 0
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            default_positive += value
    check(len(default_weights) > 0, "shop.default_weights", "rare_plus_weights is empty")
    check(
        default_positive == 100,
        "shop.default_weight_total",
        f"default rare-plus weights sum to {default_positive}, expected 100",
    )

    seen_ids: set[str] = set()
    pool_union: set[int] = set()
    dorothy_seen = False

    for index, pack in enumerate(packs):
        if not isinstance(pack, dict):
            check(False, "pack.shape", f"packs[{index}] is not an object")
            continue

        pack_id = pack.get("id")
        where = f"packs[{index}] ({pack_id!r})"
        if not isinstance(pack_id, str) or not SLUG_RE.match(pack_id):
            check(False, "pack.id", f"{where} has an invalid id")
            continue
        check(pack_id not in seen_ids, "pack.duplicate_id", f"{where} is duplicated")
        seen_ids.add(pack_id)
        canon_pack = canon_by_id.get(pack_id)

        check(bool(str(pack.get("name") or "").strip()), "pack.name", f"{where} has no name")
        category = str(pack.get("category") or "")
        check(bool(category), "pack.category", f"{where} has no category/set")
        check(
            category in canon_categories,
            "pack.category_ref",
            f"{where} references category/set {category!r} not present in Canon/packs.json",
        )
        check(bool(str(pack.get("source") or "").strip()), "pack.source", f"{where} has no source")

        price = pack.get("price")
        check(
            isinstance(price, int) and not isinstance(price, bool) and 0 < price <= 1_000_000,
            "pack.price",
            f"{where} has invalid price {price!r}",
        )
        pack_size = pack.get("pack_size")
        check(
            isinstance(pack_size, int) and not isinstance(pack_size, bool) and 1 <= pack_size <= 10,
            "pack.pack_size",
            f"{where} has invalid pack_size {pack_size!r}",
        )
        restock = pack.get("restock_days")
        check(
            isinstance(restock, int) and not isinstance(restock, bool) and restock >= 1,
            "pack.restock_days",
            f"{where} has invalid restock_days {restock!r}",
        )
        stock = pack.get("stock")
        check(
            isinstance(stock, int) and not isinstance(stock, bool) and stock >= 0,
            "pack.stock",
            f"{where} has invalid stock {stock!r} (0 means unlimited)",
        )
        purchase_limit = pack.get("purchase_limit")
        check(
            isinstance(purchase_limit, int)
            and not isinstance(purchase_limit, bool)
            and purchase_limit >= 1,
            "pack.purchase_limit",
            f"{where} has invalid purchase_limit {purchase_limit!r}",
        )

        unlock = pack.get("unlock")
        description = unlock.get("description") if isinstance(unlock, dict) else None
        check(
            isinstance(description, str) and bool(description.strip()),
            "pack.unlock_description",
            f"{where} has no unlock description",
        )
        conditions = unlock.get("conditions") if isinstance(unlock, dict) else None
        check(
            isinstance(conditions, list) and len(conditions) > 0,
            "pack.unlock_conditions",
            f"{where} has no unlock conditions",
        )
        for condition in conditions if isinstance(conditions, list) else []:
            if not isinstance(condition, dict):
                check(False, "pack.unlock_condition", f"{where} has a non-object unlock condition")
                continue
            condition_type = str(condition.get("type") or "")
            check(
                condition_type in UNLOCK_TYPES,
                "pack.unlock_type",
                f"{where} has unknown unlock type {condition_type!r}",
            )

        if canon_pack:
            check(
                pack.get("name") == canon_pack.get("name"),
                "pack.canon_name",
                f"{where} name differs from canon {canon_pack.get('name')!r}",
            )
            check(
                price == canon_pack.get("price_dp"),
                "pack.canon_price",
                f"{where} price {price!r} differs from canon {canon_pack.get('price_dp')!r}",
            )
            check(
                pack_size == canon_pack.get("cards_per_pack"),
                "pack.canon_size",
                f"{where} pack_size {pack_size!r} differs from canon {canon_pack.get('cards_per_pack')!r}",
            )
            check(
                category == canon_pack.get("category"),
                "pack.canon_category",
                f"{where} category {category!r} differs from canon {canon_pack.get('category')!r}",
            )
            check(
                bool(pack.get("all_cards")) == bool(canon_pack.get("full_pool")),
                "pack.canon_full_pool",
                f"{where} all_cards does not match canon full_pool",
            )
        else:
            check(False, "pack.canon_ref", f"{where} has no matching pack in Canon/packs.json")

        entries = flatten_pool(pack)
        ids = [card_id for card_id, _ in entries]
        check(len(ids) > 0, "pack.pool_empty", f"{where} has an empty pool")
        check(
            len(ids) == len(set(ids)),
            "pack.pool_duplicate",
            f"{where} lists {len(ids) - len(set(ids))} duplicate card id(s)",
        )
        for card_id, _ in entries:
            if not isinstance(card_id, int) or isinstance(card_id, bool) or card_id not in card_ids:
                check(False, "pack.pool_card", f"{where} references missing card {card_id!r}")
        pack_pool = {card_id for card_id in ids if isinstance(card_id, int)}
        pool_union.update(pack_pool)

        if canon_pack and not canon_pack.get("full_pool"):
            canon_ids = {int(card_id) for card_id in canon_pack.get("unique_card_ids", [])}
            check(
                pack_pool == canon_ids,
                "pack.pool_canon",
                f"{where} pool union differs from canon ({len(pack_pool)} vs {len(canon_ids)})",
            )

        slots = pack.get("slots", []) or []
        check(
            isinstance(slots, list) and len(slots) == pack_size,
            "pack.slots_total",
            f"{where} has {len(slots) if isinstance(slots, list) else '?'} slots for pack_size {pack_size!r}",
        )
        pool_by_rarity = {
            canonical_rarity(group.get("rarity")): group.get("cards", []) or []
            for group in pack.get("pools", []) or []
            if isinstance(group, dict)
        }
        for slot_index, slot in enumerate(slots if isinstance(slots, list) else []):
            if not isinstance(slot, dict):
                check(False, "pack.slot", f"{where} slot {slot_index} is not an object")
                continue
            slot_type = str(slot.get("type") or "").lower()
            if slot_type in ("fixed", "fixed_rarity"):
                rarity = canonical_rarity(slot.get("rarity"))
                check(
                    rarity is not None and len(pool_by_rarity.get(rarity, [])) > 0,
                    "pack.fixed_pool",
                    f"{where} fixed slot {slot_index} has no {slot.get('rarity')!r} pool",
                )
            elif slot_type in ("any", "any_card"):
                check(
                    bool(pack.get("all_cards")) or any(pool_by_rarity.values()),
                    "pack.any_pool",
                    f"{where} any-card slot {slot_index} has no source pool",
                )
            elif slot_type in ("rare_plus", ""):
                weights = slot.get("weights") or default_weights
                positive = 0
                usable = False
                for weight in weights:
                    if not isinstance(weight, dict):
                        continue
                    value = weight.get("weight", 0)
                    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                        check(False, "pack.weight_value", f"{where} slot {slot_index} has invalid weight {value!r}")
                        continue
                    positive += value
                    if len(pool_by_rarity.get(canonical_rarity(weight.get("rarity")), [])) > 0:
                        usable = True
                check(
                    positive > 0,
                    "pack.weight_total",
                    f"{where} slot {slot_index} has no positive rare-plus weights",
                )
                check(
                    usable,
                    "pack.weight_pool",
                    f"{where} slot {slot_index} has no weight pointing at a non-empty pool",
                )
            else:
                check(False, "pack.slot_type", f"{where} slot {slot_index} has unknown type {slot_type!r}")

        if pack_id == "dorothys_gift":
            dorothy_seen = True
            check(bool(pack.get("all_cards")), "dorothy.all_cards", "all_cards is not true")
            check(bool(pack.get("prefer_unowned")), "dorothy.prefer_unowned", "prefer_unowned is not true")
            check(price == 1000, "dorothy.price", f"price is {price!r}, expected 1000")
            check(pack_size == 7, "dorothy.pack_size", f"pack_size is {pack_size!r}, expected 7")
            check(restock == 7, "dorothy.restock", f"restock_days is {restock!r}, expected 7")
            check(stock == 0, "dorothy.stock", f"stock is {stock!r}, expected 0 (canon unlimited)")
            check(
                pack.get("pool_card_count") == 1200,
                "dorothy.pool_count",
                f"pool_card_count is {pack.get('pool_card_count')!r}, expected 1200",
            )
            check(
                pack.get("pool_copy_weight") == 1,
                "dorothy.copy_weight",
                f"pool_copy_weight is {pack.get('pool_copy_weight')!r}, expected 1",
            )
            check(
                pack.get("pool_status") == "canon_full_pool",
                "dorothy.pool_status",
                f"pool_status is {pack.get('pool_status')!r}",
            )
            check(
                len(entries) == 1200,
                "dorothy.pool_entries",
                f"pool has {len(entries)} entries, expected one per card",
            )
            check(
                pack_pool == card_ids,
                "dorothy.pool_coverage",
                f"pool covers {len(pack_pool)}/1200 cards",
            )
            check(
                all(
                    card_rarity.get(card_id) in (None, rarity)
                    for card_id, rarity in entries
                ),
                "dorothy.pool_rarity",
                "pool group rarity does not match Rules/card_rarity.json",
            )
            unlock_type = (
                conditions[0].get("type")
                if isinstance(conditions, list) and conditions and isinstance(conditions[0], dict)
                else None
            )
            unlock_value = (
                conditions[0].get("value")
                if isinstance(conditions, list) and conditions and isinstance(conditions[0], dict)
                else None
            )
            check(
                unlock_type == "collection_percent" and unlock_value == 90,
                "dorothy.unlock",
                f"unlock is {unlock_type!r}/{unlock_value!r}, expected collection_percent/90",
            )
            check(
                all(str(slot.get("type", "")).lower() in ("any", "any_card") for slot in slots if isinstance(slot, dict)),
                "dorothy.slots",
                "all slots must be any-card slots",
            )

    check(dorothy_seen, "dorothy.present", "dorothys_gift is missing from the catalogue")
    check(
        pool_union == card_ids,
        "shop.pool_union",
        f"pack pool union is {len(pool_union)}/1200 cards",
    )

    print("A06 pack catalogue validation")
    print(f"  packs: {len(packs)}  cards: {len(card_ids)}  pool union: {len(pool_union)}")
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
