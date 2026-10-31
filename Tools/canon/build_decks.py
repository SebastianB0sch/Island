"""Build starter decks, opponent roster and opponent deck records.

The three starter decks are complete and verified against the guide. Opponent
decks are transcribed from the GameFAQs Character Deck List FAQ v1.4 (section
VII), with the shared Year 1 generic shell appended where the FAQ says the
character uses it. Every record carries an explicit status and, where the FAQ
says cards are missing, an ``unresolved_slots`` count so downstream lanes
cannot mistake a partial list for a legal 40-card deck.

The ROM has no contiguous, uncompressed 40-card deck table at the card-id
encoding used by ``cards.json``. A raw u16 sequence scan and a GBA LZ77/RLE
block scan both came up empty (see Docs/Canon/GATE3_RECONCILIATION.md). Deck
lists therefore remain guide-derived and are marked accordingly.
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
FAQ_URL = "https://gamefaqs.gamespot.com/gba/928593-yu-gi-oh-gx-duel-academy/faqs/41382"
CURATED_PATH = Path(__file__).with_name("deck_lists_faq.json")

# The five event-only constructs are not roster duelists. They are represented
# in events.json as tournament/partner objects with explicit participant IDs.
EVENT_CONSTRUCT_IDS = {"festival_bracket", "chocolate_bracket", "walk_home_partner"}


def norm(name: str) -> str:
    name = name.replace("’", "'")
    name = re.sub(r"\s*\(GX1\)$", "", name)
    return re.sub(r"[^a-z0-9]", "", name.lower())


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def load_cards() -> tuple[dict[int, str], dict[str, int], dict[str, int]]:
    cards = read_json(CANON_DIR.parent / "cards.json")
    by_id = {int(c["id"]): c["name"] for c in cards}
    by_name = {norm(c["name"]): int(c["id"]) for c in cards}
    aliases_raw = read_json(Path(__file__).with_name("card_aliases.json"))["aliases"]
    aliases = {norm(k): v for k, v in aliases_raw.items() if v is not None}
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
            "status": "complete",
            "unresolved_slots": 0,
            "unresolved": [item["name"] for item in items if not item["resolved"]],
            "source": GUIDE_BASE + STARTER_PAGE.replace(" ", "_"),
            "confidence": "high",
        })
    return decks


def parse_opponents(text: str, aliases: dict, by_name: dict, by_id: dict[int, str]) -> tuple[list[dict], list[dict]]:
    """Fallback parser used only when the facts cache is absent."""
    opponents = []
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
            slug = slugify(name)
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

    for opponent in opponents:
        opponent["signature_card_ids"] = sorted({
            cid for cid in (
                resolve(link_name(m), aliases, by_name)
                for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", opponent.pop("deck_text"))
            ) if cid is not None
        })
        opponent["signature_cards"] = [by_id[cid] for cid in opponent["signature_card_ids"]]
        opponent["archetype"] = "unclassified"
        opponent["gift_card_ids"] = sorted({
            cid for cid in (
                resolve(link_name(m), aliases, by_name)
                for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", opponent.pop("gift_text"))
            ) if cid is not None
        })
        opponent["gift_cards"] = [by_id[cid] for cid in opponent["gift_card_ids"]]
        opponent["confidence"] = "medium"
        opponent["source"] = GUIDE_BASE + OPPONENTS_PAGE.replace(" ", "_")
    return opponents, []


def sha_deck(deck: dict) -> str:
    payload = json.dumps({k: deck.get(k) for k in ("id", "name", "type", "opponent", "main", "extra")},
                         sort_keys=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def curated_deck(did: str, source: dict, deck_type: str) -> dict:
    deck = {
        "id": did,
        "name": source["name"],
        "type": deck_type,
        "opponent": source.get("opponent"),
        "archetype": source.get("archetype", "unclassified"),
        "main": source.get("main", []),
        "extra": source.get("extra", []),
        "main_count": len(source.get("main", [])),
        "extra_count": len(source.get("extra", [])),
        "complete": bool(source.get("complete")),
        "status": source.get("status", "unknown"),
        "confidence": source.get("confidence", "low"),
        "source": source.get("source", FAQ_URL),
        "faq_section": source.get("faq_section"),
        "use_generic_shell": bool(source.get("use_generic_shell")),
        "fixed_cards": source.get("fixed_cards", []),
        "extra_cards": source.get("extra_cards", []),
        "unresolved_slots": int(source.get("unresolved_slots", 0)),
        "unresolved_reason": source.get("unresolved_reason", ""),
        "random_pool": source.get("random_pool", []),
        "notes": source.get("notes", []),
    }
    deck["sha256"] = sha_deck(deck)
    return deck


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path,
                        default=Path("Tools/canon/cache/guide_wikitext.json"),
                        help="optional wikitext cache; only needed when decks_facts.json is absent")
    args = parser.parse_args()
    ensure_dirs()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / "decks_facts.json"
    by_id, by_name, aliases = load_cards()
    curated = read_json(CURATED_PATH)

    if cache_path.exists():
        cached = read_json(cache_path)
        starters = cached["starters"]
        opponents = cached["opponents"]
    else:
        source = read_json(args.source)
        starters = parse_starter_decks(source[STARTER_PAGE], aliases, by_name)
        opponents, _ = parse_opponents(source[OPPONENTS_PAGE], aliases, by_name, by_id)

    for starter in starters:
        starter.setdefault("status", "complete")
        starter.setdefault("unresolved_slots", 0)
        starter.setdefault("unresolved_reason", "")
    deck_records: list[dict] = list(starters)
    for did, source in curated["opponent_decks"].items():
        deck_records.append(curated_deck(did, source, "opponent"))
    for did, source in curated["event_decks"].items():
        deck_records.append(curated_deck(did, source, source.get("type", "event")))

    variants = [
        {
            "id": "chazz_ojama", "name": "Chazz Princeton - Ojama", "type": "opponent_variant",
            "opponent": "chazz", "archetype": "Ojama", "main": [], "extra": [],
            "main_count": 0, "extra_count": 0, "complete": False, "status": "unknown",
            "unresolved_slots": 40,
            "unresolved_reason": "Event 15 deck; full list not published.",
            "signature_cards": ["Ojama Yellow", "Ojama Green", "Ojama Black", "Ojama Trio", "Ojama Delta Hurricane!!"],
            "source": GUIDE_BASE + "Yu-Gi-Oh!_GX_Duel_Academy/Events",
            "confidence": "low",
        },
        {
            "id": "jaden_improved", "name": "Jaden Yuki - Improved", "type": "opponent_variant",
            "opponent": "jaden", "archetype": "Elemental HERO", "main": [], "extra": [],
            "main_count": 0, "extra_count": 0, "complete": False, "status": "unknown",
            "unresolved_slots": 40,
            "unresolved_reason": "Event 3 upgrade; full list not published.",
            "signature_cards": ["Elemental Hero Flame Wingman"],
            "source": GUIDE_BASE + "Yu-Gi-Oh!_GX_Duel_Academy/Events",
            "confidence": "low",
        },
        {
            "id": "bastion_magnet", "name": "Bastion Misawa - Magnet", "type": "opponent_variant",
            "opponent": "bastion", "archetype": "Magnet Warrior", "main": [], "extra": [],
            "main_count": 0, "extra_count": 0, "complete": False, "status": "unknown",
            "unresolved_slots": 40,
            "unresolved_reason": "One of six Bastion decks; only signature cards documented.",
            "signature_cards": ["Alpha The Magnet Warrior", "Beta The Magnet Warrior",
                                "Gamma The Magnet Warrior", "Valkyrion the Magna Warrior"],
            "source": GUIDE_BASE + OPPONENTS_PAGE.replace(" ", "_"),
            "confidence": "low",
        },
    ]
    for deck in variants:
        deck["sha256"] = sha_deck(deck)
    deck_records.extend(variants)

    # Roster: the 25 named duelists from the original extraction plus the three
    # named event duelists reconciled in Gate 3.
    roster = {o["id"]: dict(o) for o in opponents}
    for addition in curated["opponent_additions"]:
        roster[addition["id"]] = dict(addition)
    for oid, opponent in roster.items():
        opponent.setdefault("role", "named")
        decks = [d["id"] for d in deck_records if d.get("opponent") == oid and d["type"] in
                 {"opponent", "opponent_variant", "event"}]
        opponent["decks"] = sorted(set(opponent.get("decks", []) + decks))
        if opponent.get("deck"):
            opponent["default_deck"] = opponent["deck"]
        elif f"{oid}_year1" in opponent["decks"]:
            opponent["default_deck"] = f"{oid}_year1"
        elif opponent["decks"]:
            complete = [d["id"] for d in deck_records
                        if d["id"] in opponent["decks"] and d.get("complete")]
            opponent["default_deck"] = (complete or opponent["decks"])[0]
    roster_list = sorted(roster.values(), key=lambda o: (o.get("role") == "event", o["id"]))

    write_json(CANON_DIR / "decks.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {
            "starters": GUIDE_BASE + STARTER_PAGE.replace(" ", "_"),
            "opponents": GUIDE_BASE + OPPONENTS_PAGE.replace(" ", "_"),
            "opponent_decks": FAQ_URL,
            "opponent_decks_title": "Character Deck List FAQ v1.4 (Tracy_Smith, 2006-03-11)",
            "jaden_donor": "game3d/src/duel/decklists.js (local donor; not committed)",
            "rom_deck_table": curated["source"]["rom_deck_table"],
        },
        "summary": {
            "total": len(deck_records),
            "complete": sum(1 for deck in deck_records if deck["complete"]),
            "incomplete": sum(1 for deck in deck_records if not deck["complete"]),
            "unknown": sum(1 for deck in deck_records if deck.get("status") == "unknown"),
            "partial": sum(1 for deck in deck_records if deck.get("status") == "partial"),
        },
        "generic_shell": curated["generic_shell"],
        "event_constructs": curated["event_constructs"],
        "decks": deck_records,
    })

    write_json(CANON_DIR / "opponents.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {
            "roster": GUIDE_BASE + OPPONENTS_PAGE.replace(" ", "_"),
            "decks": FAQ_URL,
            "rom_names": "0x146CB14 / 0x146CC32",
        },
        "notes": [
            "Roster names come from the verified ROM name pool at 0x146CB14/0x146CC32.",
            "25 named duelists are the original extraction; jinzo, goblin_king and sheppard are event-only additions reconciled in Gate 3.",
            "Tournament/partner constructs (festival_bracket, chocolate_bracket, walk_home_partner) are NOT roster duelists; they live in decks.json event_constructs and events.json duel objects.",
            "Mimicry is the practical-exam proctor; the Character Deck FAQ calls the same role 'Test Proctor'.",
        ],
        "count": len(roster_list),
        "named_duelists": sum(1 for o in roster_list if o.get("role") != "event"),
        "event_duelists": sum(1 for o in roster_list if o.get("role") == "event"),
        "opponents": roster_list,
    })
    print(f"starter decks: {len(starters)}  complete: {sum(1 for s in starters if s['complete'])}")
    print(f"opponents: {len(roster_list)}  decks: {len(deck_records)}")
    print("deck status:", {s: sum(1 for d in deck_records if d.get("status") == s)
                            for s in ("complete", "partial", "unknown")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
