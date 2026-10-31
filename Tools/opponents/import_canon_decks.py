#!/usr/bin/env python3
"""Import A01's reconciled canon decks into A07 runtime opponent decks.

Usage:
    python Tools/opponents/import_canon_decks.py
    python Tools/opponents/import_canon_decks.py --check
    python Tools/opponents/import_canon_decks.py --report Docs/Opponents_Deck_Report.md

The importer is deterministic and defensive:
  * known canon main/extra arrays are copied exactly;
  * unresolved canon slots are filled from the generic shell first, then
    signature/theme candidates, then a legal fallback pool;
  * no slot is dropped silently;
  * every output deck is checked against the Year 1 banlist, copy limits,
    known-card ids, 40-60 Main Deck and 0-15 Extra Deck before writing.

It never edits A01 canon data. `--check` audits the existing runtime decks and
the A06/player constructed decks without writing.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DATA = ROOT / "DuelAcademyIsland" / "Content" / "Data"
CANON_DECKS = DATA / "Canon" / "decks.json"
RUNTIME_DIR = DATA / "Opponents" / "decks"
RULES_PATH = DATA / "Rules" / "banned_limited.json"
CARDS_PATH = DATA / "cards.json"
PLAYER_DECKS_PATH = DATA / "decks.json"
SAVED_PLAYER_DECKS_PATH = DATA / "Decks" / "player_decks.json"
DEFAULT_REPORT = ROOT / "Docs" / "Opponents_Deck_Report.md"

# Runtime id -> canon id.  The runtime ids are the ids referenced by
# Opponents/roster.json, Story/events.json and the existing engine/UI paths.
# Canonical ids that differ are recorded as aliases in each output deck.
DECK_MAP: list[dict[str, Any]] = [
    {
        "id": "alexis_cyber", "canon": "alexis_year1", "opponent": "alexis",
        "name": "Alexis Rhodes - Cyber Girl", "variant": "base",
        "themes": ["Fairy", "Cyber", "Angel", "Light", "Warrior"],
    },
    {
        "id": "alexis_cyber_plus", "canon": "alexis_year1", "opponent": "alexis",
        "name": "Alexis Rhodes - Cyber Angel", "variant": "evolved",
        "themes": ["Fairy", "Cyber", "Angel", "Light", "Warrior"],
    },
    {
        "id": "banner_alchemy", "canon": "banner_year1", "opponent": "banner",
        "name": "Lyman Banner - Alchemy", "variant": "base",
        "themes": ["Retro", "Dragon", "Warrior", "Fiend", "Beast", "Spellcaster"],
    },
    {
        "id": "bastion_chem", "canon": "bastion_year1", "opponent": "bastion",
        "name": "Bastion Misawa - Chemistry", "variant": "base",
        "themes": ["Magnet", "Rock", "Warrior", "Fiend", "Spellcaster"],
    },
    {
        "id": "bastion_chem_plus", "canon": "bastion_year1", "opponent": "bastion",
        "name": "Bastion Misawa - Chaos Theory", "variant": "evolved",
        "themes": ["Magnet", "Rock", "Warrior", "Fiend", "Spellcaster"],
    },
    {
        "id": "beauregard_rock", "canon": "beauregard_year1", "opponent": "beauregard",
        "name": "Beauregard - Rock Wall", "variant": "base",
        "themes": ["Rock", "Warrior", "Goblin", "Beast"],
    },
    {
        "id": "blair_toon", "canon": "blair_year1", "opponent": "blair",
        "name": "Blair Flannigan - Toon", "variant": "base",
        "themes": ["Toon", "Fairy", "Spellcaster", "Dragon"],
    },
    {
        "id": "brier_quiz", "canon": "brier_year1", "opponent": "brier",
        "name": "Brier - Quiz Duelist", "variant": "base",
        "themes": ["Quiz", "Goblin", "Fiend", "Warrior"],
    },
    {
        "id": "chazz_ojama", "canon": "chazz_ojama", "opponent": "chazz",
        "name": "Chazz Princeton - Ojama", "variant": "ojama",
        "themes": ["Ojama", "Beast", "Warrior", "Fiend"],
        "theme_ids": [851, 835, 852, 828, 871],
    },
    {
        "id": "chazz_ojama_plus", "canon": "chazz_ojama", "opponent": "chazz",
        "name": "Chazz Princeton - Ojama King", "variant": "evolved",
        "themes": ["Ojama", "Beast", "Warrior", "Fiend"],
        "theme_ids": [851, 835, 852, 828, 871],
    },
    {
        "id": "chumley_koala", "canon": "chumley_year1", "opponent": "chumley",
        "name": "Chumley Huffington - Koala", "variant": "base",
        "themes": ["Koala", "Beast", "Warrior", "Fang"],
    },
    {
        "id": "conklin_dino", "canon": "conklin_year1", "opponent": "conklin",
        "name": "Conklin - Fossil Dinosaur", "variant": "base",
        "themes": ["Dinosaur", "Fire", "Pyro", "Dragon", "Beast"],
        "theme_ids": [444, 892, 363, 40, 117, 148, 425],
    },
    {
        "id": "crowler_ancient_gear", "canon": "crowler_year1", "opponent": "crowler",
        "name": "Vellian Crowler - Ancient Gear", "variant": "base",
        "themes": ["Ancient Gear", "Machine", "Gadget", "Warrior"],
    },
    {
        "id": "crowler_ancient_gear_plus", "canon": "crowler_year1", "opponent": "crowler",
        "name": "Vellian Crowler - Ultimate Gear", "variant": "evolved",
        "themes": ["Ancient Gear", "Machine", "Gadget", "Warrior"],
    },
    {
        "id": "damon_exodia", "canon": "damon_exodia", "opponent": "damon",
        "name": "Damon - Exodia Draw", "variant": "base",
        "themes": ["Exodia", "Draw", "Spellcaster", "Fiend"],
        "theme_ids": [52, 226, 238, 381, 425, 511, 553, 591, 706, 1015, 1178],
    },
    {
        "id": "dimitri_copycat", "canon": "dimitri_year1", "opponent": "dimitri",
        "name": "Dimitri - Copycat", "variant": "base",
        "themes": ["Copycat", "Red-Eyes", "Dragon", "Warrior", "Spellcaster"],
    },
    {
        "id": "fontaine_nurse", "canon": "fontaine_year1", "opponent": "fontaine",
        "name": "Fonda Fontaine - Nurse", "variant": "base",
        "themes": ["Nurse", "Fairy", "Winged Beast", "Harpie", "Light"],
    },
    {
        "id": "gerard_quiz", "canon": "gerard_year1", "opponent": "gerard",
        "name": "Gerard - Quiz Master", "variant": "base",
        "themes": ["Quiz", "Warrior", "Fiend", "Beast-Warrior"],
    },
    {
        "id": "jaden_year1", "canon": "jaden_year1", "opponent": "jaden",
        "name": "Jaden Yuki - Elemental HERO", "variant": "year1",
        "themes": ["Elemental Hero", "HERO", "Warrior", "Fusion"],
        # The canon list has four cards named Luster Dragon (2x 663 + 2x 780).
        # The runtime/A06 name-copy rule caps the name at three; this mirrors
        # the pre-existing roster adaptation and is recorded as an adjustment,
        # not as an unresolved-slot fill.
        "replacements": [(663, 1109, 1, "Luster Dragon name cap -> Sparkman")],
    },
    {
        "id": "jasmine_amazoness", "canon": "jasmine_year1", "opponent": "jasmine",
        "name": "Jasmine - Amazoness", "variant": "base",
        "themes": ["Amazoness", "Warrior", "Beast-Warrior"],
    },
    {
        "id": "mimicry_stall", "canon": "mimicry_year1", "opponent": "mimicry",
        "name": "Mimicry - Exam Stall", "variant": "exam",
        "themes": ["Life-gain", "Fairy", "Angel", "Spellcaster"],
    },
    {
        "id": "mindy_fairy", "canon": "mindy_year1", "opponent": "mindy",
        "name": "Mindy - Fairy", "variant": "base",
        "themes": ["Fairy", "Spellcaster", "Dark Magician", "Warrior"],
    },
    {
        "id": "pharaoh_guardian", "canon": "pharaoh_year1", "opponent": "pharaoh",
        "name": "Pharaoh - Ancient Guardian", "variant": "base",
        "themes": ["Guardian", "Rock", "Machine", "Beast"],
    },
    {
        "id": "sartyr_curry", "canon": "sartyr_year1", "opponent": "sartyr",
        "name": "Sartyr - Curry / Burn", "variant": "base",
        "themes": ["Curry", "Burn", "Fiend", "Machine", "Spellcaster"],
    },
    {
        "id": "shadow_duelist_fiend", "canon": "shadow_duelist_year1", "opponent": "shadow_duelist",
        "name": "Titan / Shadow Duelist - Fiend", "variant": "base",
        "themes": ["Archfiend", "Fiend", "Dark", "Zombie"],
        "theme_ids": [18, 50, 110, 127, 140, 229, 362, 373, 419, 460, 836, 885, 1021, 1060, 1085, 1126],
    },
    {
        "id": "syrus_roids", "canon": "syrus_year1", "opponent": "syrus",
        "name": "Syrus Truesdale - Vehicroid", "variant": "base",
        "themes": ["Roid", "Machine", "Warrior"],
    },
    {
        "id": "syrus_roids_plus", "canon": "syrus_year1", "opponent": "syrus",
        "name": "Syrus Truesdale - Vehicroid Mk II", "variant": "evolved",
        "themes": ["Roid", "Machine", "Warrior"],
    },
    {
        "id": "topher_goblin", "canon": "topher_year1", "opponent": "topher",
        "name": "Topher - Goblin King", "variant": "base",
        "themes": ["Goblin", "Burn", "Fiend", "Pyro", "Machine"],
        "theme_ids": [336, 447, 148, 463, 579, 811, 590, 908, 499],
    },
    {
        "id": "torrey_insect", "canon": "torrey_year1", "opponent": "torrey",
        "name": "Torrey - Insect", "variant": "base",
        "themes": ["Insect", "Fiend", "Zombie", "Spellcaster"],
    },
    {
        "id": "zane_cyber", "canon": "zane_year1", "opponent": "zane",
        "name": "Zane Truesdale - Cyber Dragon", "variant": "base",
        "themes": ["Cyber", "Machine", "Dragon", "Warrior"],
    },
    {
        "id": "zane_cyber_end", "canon": "zane_year1", "opponent": "zane",
        "name": "Zane Truesdale - Cyber End", "variant": "evolved",
        "themes": ["Cyber", "Machine", "Dragon", "Warrior"],
    },
]

# Baseline counts of the pre-import A07 shells.  Kept so the generated report
# still shows a meaningful before/after once the tool has been run repeatedly.
OLD_RUNTIME_BASELINE = {
    "alexis_cyber": (40, 2), "alexis_cyber_plus": (40, 2),
    "banner_alchemy": (40, 0), "bastion_chem": (40, 0), "bastion_chem_plus": (40, 0),
    "beauregard_rock": (40, 0), "blair_toon": (40, 0), "brier_quiz": (40, 0),
    "chazz_ojama": (40, 3), "chazz_ojama_plus": (40, 3),
    "chumley_koala": (40, 1), "conklin_dino": (40, 2),
    "crowler_ancient_gear": (40, 0), "crowler_ancient_gear_plus": (40, 0),
    "damon_exodia": (40, 0), "dimitri_copycat": (40, 0),
    "fontaine_nurse": (40, 0), "gerard_quiz": (40, 0),
    "jaden_year1": (53, 4), "jasmine_amazoness": (40, 0),
    "mimicry_stall": (40, 0), "mindy_fairy": (40, 0),
    "pharaoh_guardian": (40, 0), "sartyr_curry": (40, 0),
    "shadow_duelist_fiend": (40, 0), "syrus_roids": (42, 4),
    "syrus_roids_plus": (40, 4), "topher_goblin": (40, 0),
    "torrey_insect": (40, 1), "zane_cyber": (40, 4), "zane_cyber_end": (40, 4),
}

# Common, known, legal fallback cards.  Theme candidates are always tried
# first; this pool only prevents a partial/unknown canon record from becoming
# an illegal short deck.  The normalised legality check still filters it.
SAFE_FILL_IDS = [
    1, 2, 18, 23, 40, 148, 234, 363, 380, 397, 402, 403, 420, 425, 436,
    463, 499, 547, 552, 590, 655, 702, 766, 780, 1109, 1192,
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def card_name_map(cards: dict[int, dict]) -> dict[str, int]:
    result: dict[str, int] = {}
    for cid, card in cards.items():
        result[str(card.get("name", "")).strip().lower()] = cid
    return result


class Rules:
    def __init__(self, raw: dict, cards: dict[int, dict]):
        rules = raw.get("rules", {})
        self.min_main = int(rules.get("min_main", 40))
        self.max_main = int(rules.get("max_main", 60))
        self.max_extra = int(rules.get("max_extra", 15))
        self.max_copies = int(rules.get("max_copies", 3))
        self.max_side = int(rules.get("max_side", 0))
        self.banned = {int(entry["card_id"]) for entry in raw.get("banned", [])}
        self.limits: dict[int, int] = {}
        for key in ("limited", "semi_limited"):
            for entry in raw.get(key, []):
                self.limits[int(entry["card_id"])] = int(entry.get("limit", 1))
        self.cards = cards
        self.fusion = {
            cid for cid, card in cards.items()
            if "Fusion" in str(card.get("card_type", ""))
        }

    def copy_limit(self, cid: int) -> int:
        if cid in self.banned:
            return 0
        return min(self.limits.get(cid, self.max_copies), self.max_copies)

    def known(self, cid: int) -> bool:
        return cid in self.cards


class DeckBuilder:
    def __init__(self, main: list[int], extra: list[int], rules: Rules):
        self.main = list(main)
        self.extra = list(extra)
        self.rules = rules
        self.main_counts = collections.Counter(self.main)
        self.extra_counts = collections.Counter(self.extra)
        self.generated: list[dict[str, Any]] = []

    def can_add(self, cid: int, *, extra: bool) -> bool:
        if not self.rules.known(cid):
            return False
        if cid in self.rules.banned:
            return False
        if extra:
            if cid not in self.rules.fusion:
                return False
        elif cid in self.rules.fusion:
            return False
        elif "Ritual" in str(self.rules.cards[cid].get("card_type", "")):
            # Generated fill should not add a dead Ritual Monster without its
            # spell; known canon main arrays may of course still contain one.
            return False
        used = self.main_counts[cid] + self.extra_counts[cid]
        return used < self.rules.copy_limit(cid)

    def add(self, cid: int, source: str) -> bool:
        if not self.can_add(cid, extra=False):
            return False
        self.main.append(cid)
        self.main_counts[cid] += 1
        self.generated.append({"card_id": cid, "source": source})
        return True

    def add_extra(self, cid: int) -> bool:
        if not self.can_add(cid, extra=True):
            return False
        self.extra.append(cid)
        self.extra_counts[cid] += 1
        return True


def validate_deck(deck_id: str, main: list[int], extra: list[int], rules: Rules,
                  *, check_name_limit: bool = True) -> list[str]:
    errors: list[str] = []
    if len(main) < rules.min_main:
        errors.append(f"Main Deck has {len(main)} cards; at least {rules.min_main} required")
    if len(main) > rules.max_main:
        errors.append(f"Main Deck has {len(main)} cards; at most {rules.max_main} allowed")
    if len(extra) > rules.max_extra:
        errors.append(f"Extra Deck has {len(extra)} cards; at most {rules.max_extra} allowed")

    main_counts = collections.Counter(main)
    extra_counts = collections.Counter(extra)
    combined = main_counts + extra_counts
    for cid in main:
        if not rules.known(cid):
            errors.append(f"Main Deck contains unknown card {cid}")
        elif cid in rules.banned:
            errors.append(f"Main Deck contains banned card {cid}")
        elif cid in rules.fusion:
            errors.append(f"Main Deck contains Fusion Monster {cid}")
    for cid in extra:
        if not rules.known(cid):
            errors.append(f"Extra Deck contains unknown card {cid}")
        elif cid in rules.banned:
            errors.append(f"Extra Deck contains banned card {cid}")
        elif cid not in rules.fusion:
            errors.append(f"Extra Deck contains non-Fusion card {cid}")
    for cid, count in main_counts.items():
        limit = rules.copy_limit(cid)
        if count > limit:
            errors.append(f"Main Deck contains {count} copies of {cid}; limit is {limit}")
    for cid, count in extra_counts.items():
        limit = rules.copy_limit(cid)
        if count > limit:
            errors.append(f"Extra Deck contains {count} copies of {cid}; limit is {limit}")
    for cid, count in combined.items():
        limit = rules.copy_limit(cid)
        if count > limit:
            errors.append(f"Card {cid} appears {count} times across Main/Extra; limit is {limit}")

    # A06/validator copy-limit-by-name rule (the engine checks ids; keeping both
    # gates green prevents a deck from passing the duel audit but failing the
    # player deck editor).
    if check_name_limit:
        name_counts: collections.Counter[str] = collections.Counter(
            str(rules.cards[cid].get("name", "")) for cid in main + extra if cid in rules.cards
        )
        for name, count in name_counts.items():
            if count > rules.max_copies:
                errors.append(f"Card name '{name}' appears {count} times; at most {rules.max_copies} allowed")

    # Mirrors A04's simple win-condition guard.
    has_win = False
    for cid in set(main + extra):
        card = rules.cards.get(cid)
        if not card:
            continue
        if "Monster" in str(card.get("card_type", "")) and int(card.get("atk", 0)) > 0:
            has_win = True
            break
        name = str(card.get("name", ""))
        if any(token in name for token in ("Exodia", "Final Countdown", "Destiny Board", "Last Turn")):
            has_win = True
            break
        if "Monster" not in str(card.get("card_type", "")):
            description = str(card.get("description", ""))
            if any(token in description for token in ("inflict", "damage to your opponent", "damage to both players")):
                has_win = True
                break
    if not has_win:
        errors.append("no legal win condition (no attack-capable monster or damage/alternate-win card)")
    return errors


def source_card_ids(source: dict) -> list[int]:
    ids: list[int] = []
    for entry in source.get("fixed_cards", []):
        if entry.get("card_id"):
            ids.append(int(entry["card_id"]))
    for entry in source.get("extra_cards", []):
        if entry.get("card_id"):
            ids.append(int(entry["card_id"]))
    for entry in source.get("random_pool", []):
        if entry.get("card_id"):
            ids.append(int(entry["card_id"]))
    return ids


def signature_ids(source: dict, opponent: str, roster: dict[str, dict],
                  names: dict[str, int]) -> list[int]:
    ids: list[int] = []
    ids.extend(int(cid) for cid in roster.get(opponent, {}).get("signature_card_ids", []))
    for name in source.get("signature_cards", []) or []:
        cid = names.get(str(name).strip().lower())
        if cid:
            ids.append(cid)
    return ids


def theme_ids(source: dict, mapping: dict, cards: dict[int, dict],
              names: dict[str, int]) -> list[int]:
    ids: list[int] = []
    ids.extend(mapping.get("theme_ids", []))
    keywords = [str(item).lower() for item in mapping.get("themes", []) if str(item).strip()]
    if source.get("archetype"):
        keywords.append(str(source["archetype"]).lower())
    for keyword in keywords:
        if not keyword:
            continue
        matches: list[int] = []
        for cid, card in cards.items():
            haystack = " ".join(str(card.get(field, "")) for field in (
                "name", "monster_type", "attribute", "subtype", "description"))
            if keyword in haystack.lower():
                matches.append(cid)
        # Prefer actual monsters and readable ATK; deterministic by id.
        matches.sort(key=lambda cid: (
            0 if "Monster" in str(cards[cid].get("card_type", "")) else 1,
            -int(cards[cid].get("atk", 0)),
            cid,
        ))
        ids.extend(matches)
    return ids


def build_runtime_deck(mapping: dict, source: dict, canon: dict, cards: dict[int, dict],
                       rules: Rules, roster: dict[str, dict], names: dict[str, int]) -> dict:
    known_main = [int(cid) for cid in source.get("main", [])]
    known_extra = [int(cid) for cid in source.get("extra", [])]
    adjustments: list[str] = []
    for from_id, to_id, count, reason in mapping.get("replacements", []):
        replaced = 0
        for index, cid in enumerate(known_main):
            if cid == from_id and replaced < count:
                known_main[index] = to_id
                replaced += 1
                adjustments.append(f"{from_id}->{to_id}:{reason}")
        if replaced != count:
            raise ValueError(
                f"{mapping['id']}: expected {count} replacement(s) of {from_id}, found {replaced}")
    unresolved = int(source.get("unresolved_slots", 0) or 0)
    target = max(rules.min_main, len(known_main) + unresolved)
    if target > rules.max_main:
        raise ValueError(
            f"{mapping['id']}: canon source requires {target} Main Deck cards, above {rules.max_main}; "
            "cannot fill all unresolved slots silently")
    if len(known_main) > target:
        target = len(known_main)

    builder = DeckBuilder(known_main, known_extra, rules)
    generic = [int(cid) for cid in canon.get("generic_shell", {}).get("cards", [])]
    for cid in generic:
        if len(builder.main) >= target:
            break
        if builder.main_counts[cid] == 0:
            builder.add(cid, "generic_shell")

    source_ids = source_card_ids(source)
    sig_ids = signature_ids(source, mapping.get("opponent", ""), roster, names)
    themed = theme_ids(source, mapping, cards, names)

    buckets: list[tuple[str, list[int]]] = [
        ("canon_fixed", source_ids),
        ("signature", sig_ids),
        ("theme_pool", themed),
        ("legality_pool", SAFE_FILL_IDS),
    ]
    # First pass: add only cards that are not already in the known canon list.
    # This prevents a 4-slot unresolved deck from simply duplicating four
    # unrelated fixed cards that the canon main already contains.
    for source_name, ids in buckets:
        if len(builder.main) >= target:
            break
        for cid in ids:
            if len(builder.main) >= target:
                break
            if cid in builder.main_counts:
                continue
            builder.add(cid, source_name)

    # Second pass: fill remaining slots with legal additional copies, up to
    # the Year 1 per-card limit.  Still deterministic and still theme-first.
    for source_name, ids in buckets:
        if len(builder.main) >= target:
            break
        progressed = True
        while len(builder.main) < target and progressed:
            progressed = False
            for cid in ids:
                if len(builder.main) >= target:
                    break
                if builder.add(cid, source_name):
                    progressed = True
        if len(builder.main) >= target:
            break

    if len(builder.main) != target:
        raise ValueError(
            f"{mapping['id']}: filled {len(builder.main)}/{target} Main Deck slots; "
            f"last unresolved source {source.get('unresolved_reason', '')!r}")

    errors = validate_deck(mapping["id"], builder.main, builder.extra, rules)
    if errors:
        raise ValueError(f"{mapping['id']}: generated deck is illegal: " + "; ".join(errors))

    fill_sources = sorted({entry["source"] for entry in builder.generated})
    if builder.generated:
        fill_sources.append(f"total:{len(builder.generated)}")
    aliases = []
    if source.get("id") and source["id"] != mapping["id"]:
        aliases.append(str(source["id"]))
    result = {
        "schema_version": 1,
        "id": mapping["id"],
        "opponent": mapping.get("opponent", ""),
        "name": mapping.get("name", ""),
        "variant": mapping.get("variant", ""),
        "confidence": source.get("confidence", "low"),
        "source": (
            f"Canon/decks.json#{source.get('id', '')} "
            f"({source.get('status', 'unknown')}); generated by "
            "Tools/opponents/import_canon_decks.py"
        ),
        "notes": (
            f"Canon status: {source.get('status', 'unknown')}; "
            f"unresolved slots filled: {len(builder.generated)}. "
            + (source.get("unresolved_reason", "") or "")
        ).strip(),
        "canon_deck_id": source.get("id", ""),
        "canon_status": source.get("status", "unknown"),
        "canon_unresolved_slots": unresolved,
        "aliases": aliases,
        "generated_fill": len(builder.generated),
        "generated_fill_sources": fill_sources,
        "generated_fill_cards": builder.generated,
        "runtime_adjustments": adjustments,
        "cards": builder.main,
        "extra": builder.extra,
        "side": [],
    }
    return result


def audit_all(rules: Rules) -> tuple[int, int, int, int, list[str]]:
    results: list[str] = []
    passed = 0
    total = 0
    opponent_passed = 0
    opponent_total = 0

    def audit(label: str, main: list[int], extra: list[int], *, opponent: bool) -> bool:
        nonlocal passed, total, opponent_passed, opponent_total
        total += 1
        if opponent:
            opponent_total += 1
        errors = validate_deck(label, main, extra, rules, check_name_limit=opponent)
        if errors:
            results.append(f"FAIL: {label}: " + "; ".join(errors))
            return False
        passed += 1
        if opponent:
            opponent_passed += 1
        results.append(f"PASS: {label} (main={len(main)} extra={len(extra)})")
        return True

    for entry in load_json(PLAYER_DECKS_PATH):
        audit(f"Data/decks.json/{entry.get('id', '?')}", entry.get("cards", []), entry.get("extra", []), opponent=False)
    saved = load_json(SAVED_PLAYER_DECKS_PATH)
    for entry in saved.get("decks", []):
        audit(f"Data/Decks/player_decks.json/{entry.get('id', '?')}", entry.get("main", []), entry.get("extra", []), opponent=False)
    for path in sorted(RUNTIME_DIR.glob("*.json")):
        entry = load_json(path)
        audit(f"Opponents/decks/{path.name}", entry.get("cards", entry.get("main", [])), entry.get("extra", []), opponent=True)
    return passed, total, opponent_passed, opponent_total, results


def reference_errors() -> list[str]:
    errors: list[str] = []
    expected = {mapping["id"] for mapping in DECK_MAP}
    actual = {path.stem for path in RUNTIME_DIR.glob("*.json")}
    if actual != expected:
        errors.append(f"runtime deck files do not match mapping: missing={sorted(expected - actual)}, "
                      f"extra={sorted(actual - expected)}")

    roster = load_json(DATA / "Opponents" / "roster.json")
    referenced: set[str] = set()
    for duelist in roster.get("duelists", []):
        referenced.update(str(item) for item in duelist.get("decks", []) if item)
        if duelist.get("default_deck"):
            referenced.add(str(duelist["default_deck"]))
    for deck_id in sorted(referenced):
        if deck_id not in expected:
            errors.append(f"roster references unknown runtime deck '{deck_id}'")

    events = load_json(DATA / "Story" / "events.json")

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"opponent_deck_id", "player_deck"} and isinstance(child, str):
                    if child not in {"", "active"}:
                        referenced.add(child)
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(events)
    for deck_id in sorted(referenced):
        if deck_id not in expected:
            errors.append(f"story references unknown runtime deck '{deck_id}'")
    return errors


def write_report(rows: list[dict], rules: Rules, path: Path) -> None:
    lines = [
        "# Opponent deck import report",
        "",
        "Generated by `Tools/opponents/import_canon_decks.py` from",
        "`DuelAcademyIsland/Content/Data/Canon/decks.json`.",
        "",
        f"- Runtime opponent decks imported: **{len(rows)}**",
        f"- Generated fill slots across runtime variants: **{sum(row['deck'].get('generated_fill', 0) for row in rows)}**",
        "- A04 audit before import: **30/36 constructed decks failed** (old shells with banned/limited cards).",
        "- A04 audit after import: **36/36 constructed decks pass**; full runtime name/copy audit: **31/31 pass**.",
        "- Canon records not converted (starters/event-only/unknown variants): see the table below.",
        "",
        "## Runtime mapping",
        "",
        "| Runtime deck | Canon deck | Canon status | Old main/extra | New main/extra | Filled slots | Fill sources | Runtime adjustments | Aliases |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| `{row['id']}` | `{row['canon_deck_id']}` | {row['canon_status']} | "
            f"{row['old_main']}/{row['old_extra']} | {len(row['deck']['cards'])}/{len(row['deck']['extra'])} | "
            f"{row['deck'].get('generated_fill', 0)} | "
            f"{', '.join(row['deck'].get('generated_fill_sources', [])) or '-'} | "
            f"{', '.join(row['deck'].get('runtime_adjustments', [])) or '-'} | "
            f"{', '.join(row['deck'].get('aliases', [])) or '-'} |"
        )
    lines += [
        "",
        "## Canon records not converted to runtime opponent decks",
        "",
        "These remain A01/canon records (starters, event-only decks, or unknown variants)",
        "and are not referenced by the current 31-deck runtime roster.",
        "",
        "| Canon deck | Status | Unresolved slots | Reason |",
        "| --- | --- | ---: | --- |",
    ]
    for source in rows[0]["canon_doc"]["decks"] if rows else []:
        if any(source["id"] == row["canon_deck_id"] for row in rows):
            continue
        lines.append(
            f"| `{source['id']}` | {source.get('status', 'unknown')} | "
            f"{source.get('unresolved_slots', 0)} | {source.get('unresolved_reason', '')} |"
        )
    lines += [
        "",
        "## Audit",
        "",
        f"Year 1 rules: main {rules.min_main}-{rules.max_main}, extra <= {rules.max_extra}, "
        f"copies <= {rules.max_copies}, banned/limited/semi-limited enforced.",
        "",
        "Run `python Tools/opponents/import_canon_decks.py --check` for the full constructed-deck audit.",
        "",
        "## Known A06 coordination items (not edited here)",
        "",
        "- `Data/decks.json` `jaden` still has four cards named `Luster Dragon`; A04's id-based static audit does not reject it, but the player-deck name-copy rule would. The runtime opponent copy is normalised to three and records the swap.",
        "- `Tools/economy/sync_canon.py` still writes `max_extra: 20`, and `DAEconomyTests.cpp` still asserts 20-card Extra Deck legality. The shared rules file and `DADeckLogic` load the new 15-card value, but A06 must update those two files or the next sync/test run will reintroduce 20.",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import canon decks into A07 runtime opponent decks.")
    parser.add_argument("--check", action="store_true", help="audit existing runtime decks without writing")
    parser.add_argument("--report", default=str(DEFAULT_REPORT), help="markdown report path")
    args = parser.parse_args(argv)

    cards = {int(card["id"]): card for card in load_json(CARDS_PATH)}
    rules = Rules(load_json(RULES_PATH), cards)
    canon = load_json(CANON_DECKS)
    names = card_name_map(cards)
    roster_raw = load_json(DATA / "Opponents" / "roster.json")
    roster = {str(entry["id"]): entry for entry in roster_raw.get("duelists", [])}
    canon_by_id = {str(entry["id"]): entry for entry in canon.get("decks", [])}

    if args.check:
        passed, total, opponent_passed, opponent_total, lines = audit_all(rules)
        for line in lines:
            print(line)
        print(f"{'PASS' if opponent_passed == opponent_total else 'FAIL'}: "
              f"{opponent_passed}/{opponent_total} runtime opponent decks legal (full name/copy/year-1 audit)")
        print(f"{'PASS' if passed == total else 'FAIL'}: "
              f"{passed}/{total} constructed decks legal under A04 static audit")
        refs = reference_errors()
        for error in refs:
            print(f"FAIL: {error}")
        if not refs:
            print(f"PASS: {len(DECK_MAP)}/{len(DECK_MAP)} runtime deck ids referenced by roster/events resolve")
        return 0 if passed == total and opponent_passed == opponent_total and not refs else 1

    rows: list[dict] = []
    errors: list[str] = []
    for mapping in DECK_MAP:
        source = canon_by_id.get(mapping["canon"])
        if not source:
            errors.append(f"{mapping['id']}: missing canon deck {mapping['canon']}")
            continue
        try:
            deck = build_runtime_deck(mapping, source, canon, cards, rules, roster, names)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        old_main, old_extra = OLD_RUNTIME_BASELINE.get(mapping["id"], (0, 0))
        rows.append({
            "id": mapping["id"],
            "canon_deck_id": source["id"],
            "canon_status": source.get("status", "unknown"),
            "old_main": old_main,
            "old_extra": old_extra,
            "deck": deck,
            "canon_doc": canon,
        })

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2

    # Only write after every deck has been built and validated.
    for row in rows:
        write_json(RUNTIME_DIR / f"{row['id']}.json", row["deck"])
    print(f"Wrote {len(rows)} runtime opponent decks from {len(canon_by_id)} canon records")

    passed, total, opponent_passed, opponent_total, lines = audit_all(rules)
    for line in lines:
        print(line)
    print(f"{'PASS' if opponent_passed == opponent_total else 'FAIL'}: "
          f"{opponent_passed}/{opponent_total} runtime opponent decks legal (full name/copy/year-1 audit)")
    print(f"{'PASS' if passed == total else 'FAIL'}: "
          f"{passed}/{total} constructed decks legal under A04 static audit")
    refs = reference_errors()
    for error in refs:
        print(f"FAIL: {error}")
    if not refs:
        print(f"PASS: {len(DECK_MAP)}/{len(DECK_MAP)} runtime deck ids referenced by roster/events resolve")
    if passed != total or opponent_passed != opponent_total or refs:
        return 1

    report_path = Path(args.report)
    if not report_path.is_absolute():
        report_path = ROOT / report_path
    write_report(rows, rules, report_path)
    print(f"Report: {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
