"""Build starter decks, opponent roster and opponent deck skeletons.

Starter decks are complete and verified against the guide. Opponent decks are
reconstructed as *archetypes* with signature cards, because the public guide
does not publish full 40-card lists for every duelist. Completeness is explicit
per record so downstream lanes cannot mistake a skeleton for a legal deck.
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

STARTER_PAGE = "Yu-Gi-Oh! GX Duel Academy/Starter Decks"
OPPONENTS_PAGE = "Yu-Gi-Oh! GX Duel Academy/Opponents"
GUIDE_BASE = "https://yugipedia.com/wiki/"

SLUGS = {
    "Lyman Banner": "banner", "Pharaoh": "pharaoh", "Jaden Yuki": "jaden",
    "Syrus Truesdale": "syrus", "Chumley Huffington": "chumley",
    "Bastion Misawa": "bastion", "Blair Flannigan": "blair",
    "Gerard": "gerard", "Sartyr": "sartyr", "Dimitri": "dimitri",
    "Brier": "brier", "Beauregard": "beauregard",
    "Vellian Crowler": "crowler", "Fonda Fontaine": "fontaine",
    "Zane Truesdale": "zane", "Chazz Princeton": "chazz", "Topher": "topher",
    "Conklin": "conklin", "Alexis Rhodes": "alexis", "Mindy": "mindy",
    "Jasmine": "jasmine", "Torrey": "torrey", "Damon": "damon",
    "Mimicry": "mimicry", "The Shadow Duelist": "shadow_duelist",
    "Shadow Duelist": "shadow_duelist", "Titan": "shadow_duelist",
}


def norm(name: str) -> str:
    name = name.replace("’", "'")
    name = re.sub(r"\s*\(GX1\)$", "", name)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def load_cards() -> tuple[dict[int, str], dict[str, int], dict[str, int]]:
    cards = read_json(CANON_DIR.parent / "cards.json")
    by_id = {int(c["id"]): c["name"] for c in cards}
    by_name = {norm(c["name"]): int(c["id"]) for c in cards}
    aliases_raw = read_json(Path(__file__).with_name("card_aliases.json"))["aliases"]
    aliases = {norm(k): v for k, v in aliases_raw.items() if v is not None}
    # Extra names used by the starter page that are not pack-page aliases.
    aliases.update({
        norm("Sky Scout"): 490,
        norm("Harpie's Brother"): 490,
        norm("Luster Dragon #2"): 663,
        norm("Luster Dragon"): 780,
    })
    return by_id, by_name, aliases


def resolve(name: str, aliases: dict[str, int], by_name: dict[str, int]) -> int | None:
    key = norm(name)
    return aliases.get(key, by_name.get(key))


def link_name(match: re.Match) -> str:
    return (match.group(2) or match.group(1)).strip()


def parse_starter_decks(text: str, aliases: dict, by_name: dict) -> list[dict]:
    decks = []
    labels = ["fire", "water", "wind"]
    names = ["Fire Starter", "Water Starter", "Wind Starter"]
    parts = text.split('| valign="top"')
    for index, part in enumerate(parts[1:3 + 1]):
        items = []
        for match in re.finditer(r"\* \[\[([^\]|]+)(?:\|([^\]]+))?\]\]\s*x(\d+)", part):
            card_name = link_name(match)
            count = int(match.group(3))
            card_id = resolve(card_name, aliases, by_name)
            items.append({
                "name": card_name,
                "card_id": card_id,
                "count": count,
                "resolved": card_id is not None,
            })
        extra = []
        main = []
        for item in items:
            if item["name"] == "Meteor B. Dragon":
                extra.append(item["card_id"])
            else:
                main.extend([item["card_id"]] * item["count"])
        decks.append({
            "id": labels[index],
            "name": names[index],
            "type": "starter",
            "main": main,
            "extra": extra,
            "main_count": len(main),
            "extra_count": len(extra),
            "complete": all(item["resolved"] for item in items),
            "unresolved": [item["name"] for item in items if not item["resolved"]],
            "source": GUIDE_BASE + STARTER_PAGE.replace(" ", "_"),
            "confidence": "high",
        })
    return decks


def parse_jaden_donor() -> dict | None:
    donor = Path(r"C:\dev\argh\game3d\src\duel\decklists.js")
    if not donor.exists():
        return None
    text = donor.read_text(encoding="utf-8")
    block = re.search(r"export const JADEN_DECK = \{(.*?)\n\};", text, re.S)
    if not block:
        return None
    cards = [int(x) for x in re.findall(r"\b(\d{1,4})\b", block.group(1).split("cards:")[1].split("extra:")[0])]
    extra_match = re.search(r"extra:\s*\[([^\]]*)\]", block.group(1))
    extra = [int(x) for x in re.findall(r"\d+", extra_match.group(1))] if extra_match else []
    return {
        "id": "jaden_year1",
        "name": "Jaden Yuki - Year 1",
        "type": "opponent",
        "opponent": "jaden",
        "main": cards,
        "extra": extra,
        "main_count": len(cards),
        "extra_count": len(extra),
        "complete": True,
        "source": "C:/dev/argh/game3d/src/duel/decklists.js (donor implementation)",
        "confidence": "medium",
        "notes": ["Donor list, not independently verified against the ROM deck table."],
    }


def parse_opponents(text: str, aliases: dict, by_name: dict, by_id: dict[int, str]) -> tuple[list[dict], list[dict]]:
    opponents = []
    decks = []
    section = None
    current = None
    deck_lines: list[str] = []
    gift_lines: list[str] = []

    lines = text.splitlines()
    for line in lines + ["* END"]:
        if line.startswith("=="):
            section = line.strip("= ").strip()
            continue
        heading = re.match(r"[-*]+\s*\[\[([^\]|]+)(?:\|([^\]]+))?\]\](.*)", line)
        if heading:
            if current:
                current["deck_text"] = " ".join(deck_lines).strip()
                current["gift_text"] = " ".join(gift_lines).strip()
                opponents.append(current)
            name = (heading.group(2) or heading.group(1)).strip()
            note = re.sub(r"\s+", " ", heading.group(3)).strip(" ()")
            slug = SLUGS.get(name)
            if not slug:
                continue
            current = {
                "id": slug,
                "name": name,
                "guide_name": name,
                "section": section,
                "note": note,
                "deck_text": "",
                "gift_text": "",
            }
            deck_lines, gift_lines = [], []
            continue
        if current:
            if line.strip().startswith("Deck:"):
                deck_lines.append(line.strip()[5:].strip())
            elif line.strip().startswith("Gift Card"):
                gift_lines.append(line.strip())
            elif line.strip() and not line.startswith("{{") and not line.startswith("[["):
                if deck_lines:
                    deck_lines.append(line.strip())

    if current:
        current["deck_text"] = " ".join(deck_lines).strip()
        current["gift_text"] = " ".join(gift_lines).strip()
        opponents.append(current)

    for opponent in opponents:
        opponent["signature_card_ids"] = sorted({
            cid for cid in (
                resolve(link_name(m), aliases, by_name)
                for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", opponent["deck_text"])
            ) if cid is not None
        })
        opponent["signature_cards"] = [by_id[cid] for cid in opponent["signature_card_ids"]]
        opponent["archetype"] = infer_archetype(opponent["deck_text"])
        opponent["gift_card_ids"] = sorted({
            cid for cid in (
                resolve(link_name(m), aliases, by_name)
                for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", opponent["gift_text"])
            ) if cid is not None
        })
        opponent["gift_cards"] = [by_id[cid] for cid in opponent["gift_card_ids"]]
        opponent["confidence"] = "medium"
        opponent["source"] = GUIDE_BASE + OPPONENTS_PAGE.replace(" ", "_")
        opponent.pop("deck_text", None)
        opponent.pop("gift_text", None)
        if opponent["id"] != "jaden":
            decks.append(make_opponent_deck(opponent, aliases, by_name))
    return opponents, decks


def infer_archetype(text: str) -> str:
    match = re.search(r"Uses (?:a|an) ([^.!]+?) Deck", text, re.I)
    if match:
        value = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", match.group(1))
        value = re.sub(r"\[\[([^\]]+)\]\]", r"\1", value)
        return value.replace("Knowldege", "Knowledge").strip()
    if "Elemental Hero" in text:
        return "Elemental HERO / Dragon beatdown"
    if "Vehicroid" in text:
        return "Vehicroid"
    if "Cyber Dragon" in text:
        return "Cyber Dragon / Fusion"
    return "unclassified"


def make_opponent_deck(opponent: dict, aliases: dict, by_name: dict) -> dict:
    deck_id = f"{opponent['id']}_year1"
    return {
        "id": deck_id,
        "name": f"{opponent['name']} - Year 1",
        "type": "opponent",
        "opponent": opponent["id"],
        "archetype": opponent.get("archetype") or "unclassified",
        "main": [],
        "extra": [],
        "main_count": 0,
        "extra_count": 0,
        "complete": False,
        "signature_cards": opponent.get("signature_cards", []),
        "source": GUIDE_BASE + OPPONENTS_PAGE.replace(" ", "_"),
        "confidence": "low",
        "gap": "Public guide gives an archetype and signature cards, not a full 40-card list.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path,
                        default=Path(r"C:\Users\Sebas\AppData\Local\Temp\opencode\gxcanon\guide_wikitext.json"))
    args = parser.parse_args()
    ensure_dirs()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "decks_facts.json"
    by_id, by_name, aliases = load_cards()
    if cache_path.exists():
        cached = read_json(cache_path)
        starters = cached["starters"]
        jaden = cached["jaden"]
        opponents = cached["opponents"]
        opponent_decks = cached["opponent_decks"]
    else:
        source = read_json(args.source)
        starters = parse_starter_decks(source[STARTER_PAGE], aliases, by_name)
        jaden = parse_jaden_donor()
        opponents, opponent_decks = parse_opponents(source[OPPONENTS_PAGE], aliases, by_name, by_id)
        write_json(cache_path, {
            "schema_version": 1,
            "source": "Yugipedia starter/opponent pages + game3d donor",
            "starters": starters,
            "jaden": jaden,
            "opponents": opponents,
            "opponent_decks": opponent_decks,
        })

    variants = [
        {
            "id": "chazz_ojama", "name": "Chazz Princeton - Ojama", "type": "opponent_variant",
            "opponent": "chazz", "archetype": "Ojama", "main": [], "extra": [],
            "main_count": 0, "extra_count": 0, "complete": False,
            "signature_cards": ["Ojama Yellow", "Ojama Green", "Ojama Black", "Ojama Trio", "Ojama Delta Hurricane!!"],
            "source": GUIDE_BASE + "Yu-Gi-Oh!_GX_Duel_Academy/Events",
            "confidence": "medium", "gap": "Event 15 deck; full list not published.",
        },
        {
            "id": "jaden_improved", "name": "Jaden Yuki - Improved", "type": "opponent_variant",
            "opponent": "jaden", "archetype": "Elemental HERO", "main": [], "extra": [],
            "main_count": 0, "extra_count": 0, "complete": False,
            "signature_cards": ["Elemental Hero Flame Wingman"],
            "source": GUIDE_BASE + "Yu-Gi-Oh!_GX_Duel_Academy/Events",
            "confidence": "medium", "gap": "Event 3 upgrade; full list not published.",
        },
        {
            "id": "bastion_magnet", "name": "Bastion Misawa - Magnet", "type": "opponent",
            "opponent": "bastion", "archetype": "Magnet Warrior", "main": [], "extra": [],
            "main_count": 0, "extra_count": 0, "complete": False,
            "signature_cards": ["Alpha The Magnet Warrior", "Beta The Magnet Warrior", "Gamma The Magnet Warrior", "Valkyrion the Magna Warrior"],
            "source": GUIDE_BASE + OPPONENTS_PAGE.replace(" ", "_"),
            "confidence": "medium", "gap": "One of six Bastion decks; only signature cards documented.",
        },
    ]

    deck_records = starters + ([jaden] if jaden else []) + opponent_decks + variants
    for deck in deck_records:
        payload = json.dumps({k: deck.get(k) for k in ("id", "name", "type", "opponent", "main", "extra")},
                             sort_keys=True).encode("utf-8")
        deck["sha256"] = hashlib.sha256(payload).hexdigest()

    write_json(CANON_DIR / "decks.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {
            "starters": GUIDE_BASE + STARTER_PAGE.replace(" ", "_"),
            "opponents": GUIDE_BASE + OPPONENTS_PAGE.replace(" ", "_"),
            "jaden_donor": "C:/dev/argh/game3d/src/duel/decklists.js",
        },
        "summary": {
            "total": len(deck_records),
            "complete": sum(1 for deck in deck_records if deck["complete"]),
            "incomplete": sum(1 for deck in deck_records if not deck["complete"]),
        },
        "decks": deck_records,
    })

    write_json(CANON_DIR / "opponents.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": GUIDE_BASE + OPPONENTS_PAGE.replace(" ", "_"),
        "notes": [
            "Roster names come from the verified ROM name pool at 0x146CB14/0x146CC32.",
            "Guide roles and archetypes are secondary; full deck lists are not published.",
        ],
        "count": len(opponents),
        "opponents": opponents,
    })
    print(f"starter decks: {len(starters)}  complete: {sum(1 for s in starters if s['complete'])}")
    print(f"opponents: {len(opponents)}  decks: {len(deck_records)}")
    print("starter main counts:", [s["main_count"] for s in starters])
    return 0


if __name__ == "__main__":
    sys.exit(main())
