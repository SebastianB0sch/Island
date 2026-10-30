"""Build the 48-pack booster catalogue from the public set list.

Facts are cached in Tools/canon/cache/packs_facts.json so the normal build is
offline. Use --source to rebuild the cache from a fetched wikitext snapshot.
No guide prose is copied into the output; only names, prices, unlock facts,
card ids and rarities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from canon_common import (
    CANON_DIR, CACHE_DIR, REPO_ROOT, ensure_dirs, read_json, utc_now, write_json,
)

PACK_PAGES = [
    "Basic 1-A", "Basic 1-B", "Basic 2-A", "Basic 2-B", "Basic 3-A", "Basic 3-B",
    "Basic 4-A", "Basic 4-B", "Basic 1-C", "Basic 2-C", "Basic 3-C", "Basic 4-C",
    "Effect Monsters (GX1-BP)", "Various Fields (GX1-BP)", "Equipments (GX1-BP)",
    "Fusions (GX1-BP)", "Rituals (GX1-BP)", "Continuous Effects (GX1-BP)",
    "Spell Collection 1 (GX1-BP)", "Spell Collection 2 (GX1-BP)",
    "Trap Collection 1 (GX1-BP)", "Trap Collection 2 (GX1-BP)",
    "Spell Special 1 (GX1-BP)", "Spell Special 2 (GX1-BP)",
    "Trap Special 1 (GX1-BP)", "Trap Special 2 (GX1-BP)",
    "Expert I (GX1-BP)", "Expert II (GX1-BP)", "Expert III (GX1-BP)",
    "Expert IV (GX1-BP)",
    "Power Destructions (GX1-BP)", "Effect Monsters Special (GX1-BP)",
    "Master Fusions (GX1-BP)", "The HERO (GX1-BP)", "Live Vehicles (GX1-BP)",
    "Be Quick (GX1-BP)", "Special Ways (GX1-BP)", "Dorothy's Gift (GX1-BP)",
    "Residents of the Sea (GX1-BP)", "Invitation to the Dark (GX1-BP)",
    "Pyrogen", "Fairy Dance", "Insect's Nest (GX1-BP)",
    "Dragons in Flight (GX1-BP)", "Beasts in Fight (GX1-BP)",
    "The Warriors (GX1-BP)", "The Machines (GX1-BP)",
    "Spellcaster's Dance (GX1-BP)",
]

PACK_IDS = {
    "Basic 1-A": ("basic_1a", "Basic"), "Basic 1-B": ("basic_1b", "Basic"),
    "Basic 2-A": ("basic_2a", "Basic"), "Basic 2-B": ("basic_2b", "Basic"),
    "Basic 3-A": ("basic_3a", "Basic"), "Basic 3-B": ("basic_3b", "Basic"),
    "Basic 4-A": ("basic_4a", "Basic"), "Basic 4-B": ("basic_4b", "Basic"),
    "Basic 1-C": ("basic_1c", "Basic"), "Basic 2-C": ("basic_2c", "Basic"),
    "Basic 3-C": ("basic_3c", "Basic"), "Basic 4-C": ("basic_4c", "Basic"),
    "Effect Monsters": ("effect_monsters", "Medium"),
    "Various Fields": ("various_fields", "Medium"),
    "Equipments": ("equipments", "Medium"),
    "Fusions": ("fusions", "Medium"),
    "Rituals": ("rituals", "Medium"),
    "Continuous Effects": ("continuous_effects", "Medium"),
    "Spell Collection 1": ("spell_collection_1", "Spell/Trap"),
    "Spell Collection 2": ("spell_collection_2", "Spell/Trap"),
    "Trap Collection 1": ("trap_collection_1", "Spell/Trap"),
    "Trap Collection 2": ("trap_collection_2", "Spell/Trap"),
    "Spell Special 1": ("spell_special_1", "Spell/Trap"),
    "Spell Special 2": ("spell_special_2", "Spell/Trap"),
    "Trap Special 1": ("trap_special_1", "Spell/Trap"),
    "Trap Special 2": ("trap_special_2", "Spell/Trap"),
    "Expert I": ("expert_1", "Expert"), "Expert II": ("expert_2", "Expert"),
    "Expert III": ("expert_3", "Expert"), "Expert IV": ("expert_4", "Expert"),
    "Power Destructions": ("power_destructions", "Special"),
    "Effect Monsters Special": ("effect_monsters_special", "Special"),
    "Master Fusions": ("master_fusions", "Special"),
    "The HERO": ("the_hero", "Special"),
    "Live Vehicles": ("live_vehicles", "Special"),
    "Be Quick": ("be_quick", "Special"),
    "Special Ways": ("special_ways", "Special"),
    "Dorothy's Gift": ("dorothys_gift", "Special"),
    "Residents of the Sea": ("residents_of_the_sea", "Attribute"),
    "Invitation to the Dark": ("invitation_to_the_dark", "Attribute"),
    "Pyrogen": ("pyrogen", "Attribute"),
    "Fairy Dance": ("fairy_dance", "Type"),
    "Insect's Nest": ("insects_nest", "Type"),
    "Dragons in Flight": ("dragons_in_flight", "Type"),
    "Beasts in Fight": ("beasts_in_fight", "Type"),
    "The Warriors": ("the_warriors", "Type"),
    "The Machines": ("the_machines", "Type"),
    "Spellcaster's Dance": ("spellcasters_dance", "Type"),
}

MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def strip_markup(text: str) -> str:
    text = re.sub(r"<ref.*?(/>|</ref>)", "", text, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.I)
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    return re.sub(r"\s+", " ", text).strip()


def link_name(text: str) -> str:
    text = strip_markup(text)
    text = re.sub(r"^[*\s]+", "", text)
    return text.strip(" .")


def parse_pack(page: str, text: str) -> dict:
    data = {
        "source_page": page,
        "source_url": "https://yugipedia.com/wiki/" + page.replace(" ", "_"),
        "name": page,
        "price": None,
        "cards_per_pack": None,
        "pool_size": None,
        "stock": None,
        "restock": None,
        "unlock_raw": None,
        "pool": [],
        "rarities": {},
        "full_pool": False,
    }
    if "{{Infobox set" in text:
        match = re.search(r"\|\s*en_name\s*=\s*(.+)", text)
        if match:
            data["name"] = match.group(1).strip()
        match = re.search(r"\|\s*size\s*=\s*(\d+)", text)
        if match:
            data["pool_size"] = int(match.group(1))
        match = re.search(r"Each pack costs (\d+) DP and contains (\d+) cards?\.", text)
        if match:
            data["price"] = int(match.group(1))
            data["cards_per_pack"] = int(match.group(2))
        match = re.search(r"There are (\d+) packs available", text)
        if match:
            data["stock"] = int(match.group(1))
        if "unlocked for purchase by default" in text:
            data["unlock_raw"] = "default"
        else:
            match = re.search(r"It is unlocked (.+?)\.", text)
            if match:
                data["unlock_raw"] = strip_markup(match.group(1))
        match = re.search(r"\{\{Video game set list\s*\|\s*cards\s*=\s*(.*?)\}\}", text, re.S)
        if match:
            for line in match.group(1).splitlines():
                line = line.strip()
                if not line or line.startswith("|") or ";" not in line:
                    continue
                name, rarity = line.split(";", 1)
                name = re.sub(r"\s*\(GX1\)$", "", name.strip())
                rarity = rarity.strip()
                data["pool"].append({"name": name, "rarity": rarity})
                data["rarities"].setdefault(rarity, []).append(name)
    else:
        def field(label: str) -> str | None:
            match = re.search(
                r"'''" + re.escape(label) + r":?'''\s*([^\n<]*)", text
            )
            return strip_markup(match.group(1)) if match else None

        data["name"] = field("Pack Name") or page
        data["unlock_raw"] = field("Unlocked")
        price = field("Price per Pack")
        if price:
            match = re.search(r"\d+", price)
            data["price"] = int(match.group()) if match else None
        per = field("Cards per Pack")
        if per:
            match = re.search(r"\d+", per)
            data["cards_per_pack"] = int(match.group()) if match else None
        size = field("Cards in the Entire Pack")
        if size:
            match = re.search(r"[\d,]+", size)
            data["pool_size"] = int(match.group().replace(",", "")) if match else None
        data["restock"] = field("Frequency")
        current = None
        for line in text.splitlines():
            line = line.strip()
            header = re.match(r"==\s*([^=]+?)\s*==", line)
            if header:
                current = header.group(1).strip()
                continue
            if line.startswith("*") and current:
                name = link_name(line[1:])
                if not name:
                    continue
                if name.lower().startswith("all cards"):
                    data["full_pool"] = True
                    continue
                data["pool"].append({"name": name, "rarity": current})
                data["rarities"].setdefault(current, []).append(name)
    return data


def normalize_name(name: str) -> str:
    name = name.replace("’", "'")
    name = re.sub(r"\s*\(GX1\)$", "", name)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load_card_lookup() -> tuple[dict[int, str], dict[str, int]]:
    cards = read_json(CANON_DIR.parent / "cards.json")
    by_id = {int(card["id"]): card["name"] for card in cards}
    by_name = {normalize_name(card["name"]): int(card["id"]) for card in cards}
    return by_id, by_name


def resolve_names(packs: list[dict], aliases: dict) -> list[dict]:
    by_id, by_name = load_card_lookup()
    normalized_aliases = {normalize_name(k): v for k, v in aliases.items()}
    for pack in packs:
        unresolved = []
        for entry in pack["pool"]:
            key = normalize_name(entry["name"])
            card_id = normalized_aliases.get(key)
            if card_id is None and key in by_name:
                card_id = by_name[key]
            entry["card_id"] = card_id
            if card_id is None:
                unresolved.append(entry["name"])
        pack["unresolved_names"] = sorted(set(unresolved))
        pack["pool_card_ids"] = [
            entry["card_id"] for entry in pack["pool"] if entry["card_id"] is not None
        ]
        # A guide name can appear twice; keep only the first id for references.
        pack["unique_card_ids"] = sorted(set(pack["pool_card_ids"]))
        if pack["pool_size"] is None:
            pack["pool_size"] = len(pack["pool"])
    return packs


def parse_unlock(raw: str | None) -> dict:
    if not raw:
        return {"type": "unknown", "confidence": "low"}
    text = raw.lower()
    result: dict = {"type": "other", "raw": raw, "confidence": "medium"}
    if raw == "default":
        return {"type": "default", "confidence": "high"}
    if "collection rate" in text:
        result["type"] = "collection"
        match = re.search(r'on ["“]?(.+?)["”]? pack', raw, re.I)
        if match:
            result["collection_pack"] = match.group(1).strip()
        result["percent"] = 90
        result["confidence"] = "high"
        return result
    if "tutorial" in text:
        result["type"] = "tutorial"
        result["confidence"] = "high"
        return result
    if "dorm" in text:
        result["type"] = "dorm"
        result["requirement"] = raw
        result["confidence"] = "medium"
        return result
    if "duel at" in text or "finishing a duel" in text:
        result["type"] = "location_duel"
        for location in ("Harbor", "Volcano", "Ocean", "Gym", "Duel Arena"):
            if location.lower() in text:
                result["location"] = location
                break
        result["confidence"] = "medium"
        return result
    if "rank" in text or "duelist" in text:
        result["type"] = "title"
        match = re.search(r'["“](.+?)["”]', raw)
        result["title"] = match.group(1) if match else None
        result["confidence"] = "medium"
        return result
    if "beat" in text or "event" in text or "clear" in text or "duel with" in text:
        result["type"] = "event"
        match = re.search(r'["“](.+?)["”]', raw)
        result["event"] = match.group(1) if match else None
        result["confidence"] = "medium"
        return result
    # Dates: "on March 20th", "on April 24th of the second year",
    # "during the last week of October", "during June".
    year = 2 if "second year" in text else 1
    month = None
    for name, number in MONTHS.items():
        if name in text:
            month = number
            break
    if month:
        result.update({"type": "calendar", "year": year, "month": month})
        day_match = re.search(r"(\d{1,2})(?:st|nd|rd|th)", text)
        if day_match:
            result["day"] = int(day_match.group(1))
            result["week"] = None
        elif "last week" in text:
            result["week"] = "last"
        elif "first week" in text:
            result["week"] = "first"
        else:
            result["week"] = None
        result["confidence"] = "high" if result.get("day") or result.get("week") else "medium"
        return result
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path,
                        default=Path(r"C:\Users\Sebas\AppData\Local\Temp\opencode\gxcanon\guide_wikitext.json"))
    args = parser.parse_args()
    ensure_dirs()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "packs_facts.json"
    if cache_path.exists():
        packs = read_json(cache_path)["packs"]
        source_note = "cache"
    else:
        source = read_json(args.source)
        packs = [parse_pack(page, source[page]) for page in PACK_PAGES if source.get(page)]
        source_note = str(args.source)
        write_json(cache_path, {
            "schema_version": 1,
            "generated_utc": utc_now(),
            "source_note": source_note,
            "packs": packs,
        })

    aliases = read_json(Path(__file__).with_name("card_aliases.json"))["aliases"]
    packs = resolve_names(packs, aliases)

    output = []
    for pack in packs:
        name = pack["name"]
        pack_id, category = PACK_IDS.get(name, (re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_"), "Other"))
        rarity_counts = {rarity: len(names) for rarity, names in pack["rarities"].items()}
        record = {
            "id": pack_id,
            "name": name,
            "category": category,
            "price_dp": pack["price"],
            "cards_per_pack": pack["cards_per_pack"],
            "pool_size_declared": pack["pool_size"],
            "pool_cards_listed": len(pack["pool"]),
            "stock": pack["stock"],
            "restock": pack["restock"],
            "unlock": parse_unlock(pack.get("unlock_raw")),
            "full_pool": pack["full_pool"],
            "rarity_counts": rarity_counts,
            "pool": pack["pool"],
            "unique_card_ids": pack["unique_card_ids"],
            "unresolved_names": pack["unresolved_names"],
            "odds_status": "unresolved",
            "confidence": {
                "name": "high",
                "price": "high" if pack["price"] is not None else "low",
                "pool": "high" if not pack["unresolved_names"] else "medium",
                "odds": "low",
            },
            "source": {
                "guide": pack["source_url"],
                "rom_pack_name_offset": None,
            },
        }
        payload = json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
        record["sha256"] = hashlib.sha256(payload).hexdigest()
        output.append(record)

    # Keep the canonical guide order explicitly.
    order = {PACK_IDS[name][0]: i for i, name in enumerate(PACK_IDS)}
    output.sort(key=lambda p: order.get(p["id"], 999))

    unresolved = [p["id"] for p in output if p["unresolved_names"]]
    data = {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {
            "guide": "https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Booster_Pack_List",
            "facts_cache": str(cache_path.relative_to(REPO_ROOT)),
            "cache_source": source_note,
        },
        "summary": {
            "pack_count": len(output),
            "with_unresolved_names": unresolved,
            "total_pool_entries": sum(len(p["pool"]) for p in output),
            "total_unique_card_ids": len({cid for p in output for cid in p["unique_card_ids"]}),
        },
        "packs": output,
    }
    write_json(CANON_DIR / "packs.json", data)
    print(f"packs: {len(output)}")
    print(f"pools with unresolved names: {len(unresolved)} -> {unresolved}")
    print(f"unique cards across pools: {data['summary']['total_unique_card_ids']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
