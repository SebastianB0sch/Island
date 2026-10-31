"""Shared data helpers for the A05 effect pipeline.

Standard library only. All paths are resolved from the repository root so the
tools behave the same when run from any working directory.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "DuelAcademyIsland" / "Content" / "Data"
CARDS_PATH = DATA / "cards.json"
DECKS_PATH = DATA / "decks.json"
FUSIONS_PATH = DATA / "fusions.json"
RITUALS_PATH = DATA / "rituals.json"
EFFECTS_DIR = DATA / "Effects"
SCRIPTS_DIR = EFFECTS_DIR / "scripts"
SCHEMA_PATH = EFFECTS_DIR / "schema.json"
MANIFEST_PATH = EFFECTS_DIR / "card_effect_manifest.json"
CANDIDATES_PATH = EFFECTS_DIR / "fusion_candidates.json"
TIER1_PATH = EFFECTS_DIR / "tier1_cards.json"
LEGAL_CARDS_PATH = EFFECTS_DIR / "legal_cards.json"
ENGINE_CPP = (
    ROOT
    / "DuelAcademyIsland"
    / "Source"
    / "DuelAcademyIsland"
    / "Private"
    / "DADuelEngine.cpp"
)

OPTIONAL_USAGE_DIRS = [
    DATA / "Decks",
    DATA / "Shop",
    DATA / "Puzzles",
    DATA / "Opponents",
    DATA / "Exams",
]

CARD_TYPE_ORDER = [
    "Normal Monster",
    "Effect Monster",
    "Fusion Monster",
    "Ritual Monster",
    "Spell",
    "Trap",
]

STATUS_ORDER = ["scripted", "vanilla", "pending", "unsupported"]

CARD_KEYS = {
    "cards",
    "card",
    "card_id",
    "card_ids",
    "main",
    "extra",
    "side",
    "pool",
    "hand",
    "field",
    "graveyard",
    "deck",
    "banished",
    "extra_deck",
    "spell_traps",
    "starter_cards",
    "reward_cards",
    "attacker_card_id",
    "target_card_id",
    "source_card_id",
}

FUSION_MATERIAL_PREFIX = re.compile(
    r'^\s*"([^"]+)"(?:\s*\+\s*"[^"]+")+'
)
RITUAL_LEVEL_PATTERNS = [
    re.compile(r"total Level\s+Stars?\s+equal\s+(\d+)\s+or more", re.I),
    re.compile(r"total Levels?\s+equal\s+(\d+)\s+or more", re.I),
]
RITUAL_SPELL_PATTERN = re.compile(
    r'Ritual Spell Card,?\s*"([^"]+)"', re.I
)
RITUAL_SPELL_TARGET_PATTERN = re.compile(
    r'Ritual Summon(?:ed with the Ritual Spell Card,?)?\s+"([^"]+)"', re.I
)


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.write("\n")


def load_cards() -> list[dict]:
    return load_json(CARDS_PATH)


def cards_by_id(cards: list[dict]) -> dict[int, dict]:
    return {int(card["id"]): card for card in cards}


def load_decks() -> list[dict]:
    if not DECKS_PATH.exists():
        return []
    return load_json(DECKS_PATH)


def normalize_text(value: str) -> str:
    """Fold case, punctuation and broken high-bit characters for matching."""
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-z0-9]+", " ", value.lower())
    return value.strip()


def text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sentence_split(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", value) if part.strip()]


def fusion_effect_text(card: dict) -> str:
    """Return the effect portion of a Fusion Monster description.

    Card 193 (Deepsea Shark) has a corrupted separator in cards.json, so its
    material line cannot be parsed. It has no effect text and is handled as a
    named override. Card 722 uses a generic material sentence instead of a
    quoted material list.
    """
    description = (card.get("description") or "").strip()
    if int(card["id"]) == 193:
        return ""
    if "5 Dragon monsters" in description:
        marker = "5 Dragon monsters."
        index = description.find(marker)
        if index >= 0:
            return description[index + len(marker):].strip()
    match = FUSION_MATERIAL_PREFIX.match(description)
    if not match:
        return description
    remainder = description[match.end():].lstrip()
    remainder = re.sub(r"^\.\s*", "", remainder)
    return remainder.strip()


def fusion_has_effect(card: dict) -> bool:
    return bool(fusion_effect_text(card))


def ritual_effect_text(card: dict) -> str:
    """Return the non-procedure portion of a Ritual Monster description."""
    description = (card.get("description") or "").strip()
    kept: list[str] = []
    for sentence in sentence_split(description):
        lowered = sentence.lower()
        if "ritual summon" in lowered:
            continue
        if "ritual spell card" in lowered:
            continue
        if "total level" in lowered:
            continue
        if "tribute" in lowered and ("level" in lowered or "hand" in lowered):
            continue
        kept.append(sentence)
    return " ".join(kept).strip()


def ritual_has_effect(card: dict) -> bool:
    return bool(ritual_effect_text(card))


def engine_name_literals() -> set[str]:
    """Names passed to TEXT(...) in the current engine.

    The 137-card regression baseline is the union of the four decks. 110 of
    those cards have an exact name literal in DADuelEngine.cpp; the remaining
    27 are Normal Monsters or the effect-free Fusion Monster 319, which are
    covered generically. This scanner is read-only and intentionally loose:
    Tier 0 coverage is only credited when a card also passes the vanilla test.
    """
    if not ENGINE_CPP.exists():
        return set()
    source = ENGINE_CPP.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'TEXT\("((?:[^"\\]|\\.)*)"\)', source))


def deck_ids(decks: list[dict] | None = None) -> set[int]:
    decks = decks if decks is not None else load_decks()
    used: set[int] = set()
    for deck in decks:
        for key in ("cards", "extra"):
            for value in deck.get(key, []):
                if isinstance(value, int):
                    used.add(value)
    return used


def _collect_ids(value, found: set[int]) -> None:
    if isinstance(value, int):
        if 1 <= value <= 1200:
            found.add(value)
        return
    if isinstance(value, str):
        return
    if isinstance(value, list):
        for item in value:
            _collect_ids(item, found)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("card_id", "card_ids", "id") and isinstance(item, int):
                if 1 <= item <= 1200:
                    found.add(item)
            else:
                _collect_ids(item, found)


def _walk_card_keys(value, found: set[int]) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in CARD_KEYS:
                _collect_ids(item, found)
            else:
                _walk_card_keys(item, found)
    elif isinstance(value, list):
        for item in value:
            _walk_card_keys(item, found)


def usage_sources() -> dict[int, set[str]]:
    """Collect card ids from every usage dataset that currently exists."""
    sources: dict[int, set[str]] = {}

    def add(ids: set[int], source: str) -> None:
        for card_id in ids:
            sources.setdefault(card_id, set()).add(source)

    decks = load_decks()
    add(deck_ids(decks), "decks.json")

    if LEGAL_CARDS_PATH.exists():
        payload = load_json(LEGAL_CARDS_PATH)
        found: set[int] = set()
        if isinstance(payload, list):
            _collect_ids(payload, found)
        elif isinstance(payload, dict):
            for key in ("cards", "card_ids", "legal", "ids"):
                if key in payload:
                    _collect_ids(payload[key], found)
            if not found:
                _walk_card_keys(payload, found)
        add(found, "Effects/legal_cards.json")

    for directory in OPTIONAL_USAGE_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.json")):
            try:
                payload = load_json(path)
            except (OSError, json.JSONDecodeError):
                continue
            found = set()
            _walk_card_keys(payload, found)
            add(found, str(path.relative_to(DATA)).replace("\\", "/"))

    return sources


def tier1_ids() -> list[int]:
    if not TIER1_PATH.exists():
        return []
    payload = load_json(TIER1_PATH)
    if isinstance(payload, dict):
        payload = payload.get("cards", [])
    return [int(value) for value in payload if isinstance(value, int)]


# ---------------------------------------------------------------------------
# Usage breakdown by content lane
# ---------------------------------------------------------------------------

USAGE_CATEGORY_ORDER = [
    "story_event_decks",
    "opponent_decks",
    "puzzle_decks",
    "starter_decks",
    "shop_packs",
    "story_rewards",
    "long_tail",
]


def _ids_from(value) -> set[int]:
    found: set[int] = set()
    _collect_ids(value, found)
    _walk_card_keys(value, found)
    return found


def _safe_load(path: Path):
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def _starter_breakdown() -> tuple[set[int], dict[str, dict]]:
    cards: set[int] = set()
    decks: dict[str, dict] = {}
    for deck in load_decks():
        deck_id = str(deck.get("id") or deck.get("name") or "starter")
        ids = _ids_from(deck.get("cards")) | _ids_from(deck.get("extra"))
        cards |= ids
        decks[deck_id] = {
            "name": deck.get("name") or deck_id,
            "source": "decks.json",
            "cards": sorted(ids),
        }
    path = DATA / "Decks" / "player_decks.json"
    payload = _safe_load(path)
    if isinstance(payload, dict):
        ids = _ids_from(payload.get("starter_cards"))
        cards |= ids
        decks["player_starter"] = {
            "name": "Player starter",
            "source": "Decks/player_decks.json",
            "cards": sorted(ids),
        }
        for deck in payload.get("decks", []) or []:
            if not isinstance(deck, dict):
                continue
            deck_id = str(deck.get("id") or deck.get("name") or "player_deck")
            ids = _ids_from(deck.get("main")) | _ids_from(deck.get("extra"))
            cards |= ids
            decks[deck_id] = {
                "name": deck.get("name") or deck_id,
                "source": "Decks/player_decks.json",
                "cards": sorted(ids),
            }
    return cards, decks


def _story_event_index() -> dict[str, list[dict]]:
    path = DATA / "Story" / "events.json"
    payload = _safe_load(path)
    index: dict[str, list[dict]] = {}
    if not isinstance(payload, dict):
        return index
    for event in payload.get("events", []) or []:
        if not isinstance(event, dict):
            continue
        for duel in event.get("duels", []) or []:
            if not isinstance(duel, dict):
                continue
            deck_id = duel.get("opponent_deck_id")
            if not isinstance(deck_id, str) or not deck_id:
                continue
            index.setdefault(deck_id, []).append(
                {
                    "event_id": event.get("id"),
                    "title": event.get("title"),
                    "opponent": duel.get("opponent_name") or duel.get("opponent_id"),
                }
            )
    return index


def _opponent_breakdown() -> tuple[set[int], set[int], dict[str, dict]]:
    story_index = _story_event_index()
    all_cards: set[int] = set()
    story_cards: set[int] = set()
    decks: dict[str, dict] = {}
    deck_dir = DATA / "Opponents" / "decks"
    if not deck_dir.exists():
        return all_cards, story_cards, decks
    for path in sorted(deck_dir.glob("*.json")):
        payload = _safe_load(path)
        if not isinstance(payload, dict):
            continue
        deck_id = str(payload.get("id") or path.stem)
        ids = _ids_from(payload.get("cards")) | _ids_from(payload.get("extra")) | _ids_from(
            payload.get("side")
        )
        all_cards |= ids
        events = story_index.get(deck_id, [])
        if events:
            story_cards |= ids
        decks[deck_id] = {
            "name": payload.get("name") or deck_id,
            "opponent": payload.get("opponent"),
            "source": str(path.relative_to(DATA)).replace("\\", "/"),
            "events": events,
            "cards": sorted(ids),
        }
    return all_cards, story_cards, decks


def _puzzle_breakdown() -> tuple[set[int], dict[str, dict]]:
    cards: set[int] = set()
    puzzles: dict[str, dict] = {}
    puzzle_dir = DATA / "Puzzles"
    if not puzzle_dir.exists():
        return cards, puzzles
    zones = ("hand", "field", "spell_traps", "graveyard", "deck", "extra", "extra_deck", "banished")
    for path in sorted(puzzle_dir.glob("*.json")):
        payload = _safe_load(path)
        if not isinstance(payload, dict):
            continue
        ids: set[int] = set()
        for side_key in ("player", "opponent_state"):
            state = payload.get(side_key)
            if not isinstance(state, dict):
                continue
            for zone in zones:
                ids |= _ids_from(state.get(zone))
        cards |= ids
        puzzle_id = str(payload.get("id") or path.stem)
        puzzles[puzzle_id] = {
            "title": payload.get("title") or puzzle_id,
            "level": payload.get("level"),
            "source": str(path.relative_to(DATA)).replace("\\", "/"),
            "cards": sorted(ids),
        }
    return cards, puzzles


def _shop_breakdown() -> tuple[set[int], dict[str, dict]]:
    cards: set[int] = set()
    packs: dict[str, dict] = {}
    payload = _safe_load(DATA / "Shop" / "packs.json")
    if not isinstance(payload, dict):
        return cards, packs
    for pack in payload.get("packs", []) or []:
        if not isinstance(pack, dict):
            continue
        pack_id = str(pack.get("id") or pack.get("name") or "pack")
        ids: set[int] = set()
        for pool in pack.get("pools", []) or []:
            if isinstance(pool, dict):
                ids |= _ids_from(pool.get("cards"))
        cards |= ids
        packs[pack_id] = {
            "name": pack.get("name") or pack_id,
            "category": pack.get("category"),
            "source": "Shop/packs.json",
            "cards": sorted(ids),
        }
    return cards, packs


def _story_reward_breakdown() -> tuple[set[int], dict[str, dict]]:
    cards: set[int] = set()
    events: dict[str, dict] = {}
    payload = _safe_load(DATA / "Story" / "events.json")
    if not isinstance(payload, dict):
        return cards, events
    for event in payload.get("events", []) or []:
        if not isinstance(event, dict):
            continue
        ids: set[int] = set()
        for outcome in event.get("outcomes", []) or []:
            if isinstance(outcome, dict) and outcome.get("type") == "grant_card":
                ids |= _ids_from(outcome.get("card_id"))
        ids |= _ids_from(event.get("rewards"))
        ids |= _ids_from(event.get("reward"))
        if not ids:
            continue
        cards |= ids
        event_id = str(event.get("id") or event.get("title") or "event")
        events[event_id] = {
            "title": event.get("title") or event_id,
            "cards": sorted(ids),
        }
    return cards, events


def usage_breakdown() -> dict:
    """Group card ids by the content lane that makes them reachable.

    The story decks are the opponent deck files referenced by
    `Story/events.json`.  `opponent_decks` is the full roster.  The priority
    field assigns each card to the first lane that references it, in the order
    requested for the A05 backlog.
    """
    starter_cards, starter_decks = _starter_breakdown()
    opponent_cards, story_deck_cards, opponent_decks = _opponent_breakdown()
    puzzle_cards, puzzles = _puzzle_breakdown()
    shop_cards, shop_packs = _shop_breakdown()
    reward_cards, story_rewards = _story_reward_breakdown()

    categories = {
        "story_event_decks": {"cards": story_deck_cards, "decks": opponent_decks},
        "opponent_decks": {"cards": opponent_cards, "decks": opponent_decks},
        "puzzle_decks": {"cards": puzzle_cards, "puzzles": puzzles},
        "starter_decks": {"cards": starter_cards, "decks": starter_decks},
        "shop_packs": {"cards": shop_cards, "packs": shop_packs},
        "story_rewards": {"cards": reward_cards, "events": story_rewards},
        "long_tail": {"cards": set(), "decks": {}},
    }
    all_card_ids = {int(card["id"]) for card in load_cards()}
    covered_ids: set[int] = set()
    for name in USAGE_CATEGORY_ORDER:
        if name == "long_tail":
            continue
        covered_ids |= {int(card_id) for card_id in categories[name]["cards"]}
    categories["long_tail"]["cards"] = all_card_ids - covered_ids

    card_categories: dict[int, set[str]] = {}
    card_labels: dict[int, set[str]] = {}
    for name, payload in categories.items():
        for card_id in payload["cards"]:
            card_categories.setdefault(int(card_id), set()).add(name)

    for deck_id, deck in opponent_decks.items():
        for card_id in deck["cards"]:
            card_labels.setdefault(int(card_id), set()).add(f"deck:{deck_id}")
            for event in deck.get("events", []):
                if event.get("event_id"):
                    card_labels[int(card_id)].add(f"event:{event['event_id']}")
    for deck_id, deck in starter_decks.items():
        for card_id in deck["cards"]:
            card_labels.setdefault(int(card_id), set()).add(f"starter:{deck_id}")
    for puzzle_id, puzzle in puzzles.items():
        for card_id in puzzle["cards"]:
            card_labels.setdefault(int(card_id), set()).add(f"puzzle:{puzzle_id}")
    for pack_id, pack in shop_packs.items():
        for card_id in pack["cards"]:
            card_labels.setdefault(int(card_id), set()).add(f"pack:{pack_id}")
    for event_id, event in story_rewards.items():
        for card_id in event["cards"]:
            card_labels.setdefault(int(card_id), set()).add(f"reward:{event_id}")

    priority: dict[int, str] = {}
    for name in USAGE_CATEGORY_ORDER:
        for card_id in sorted(categories[name]["cards"]):
            priority.setdefault(int(card_id), name)

    # Anything not covered by the five deck lanes falls into the long tail.
    all_ids: set[int] = set()
    for payload in categories.values():
        all_ids |= payload["cards"]
    for card_id in priority:
        all_ids.add(card_id)
    for card_id in sorted(all_ids):
        priority.setdefault(card_id, "long_tail")

    return {
        "categories": categories,
        "card_categories": card_categories,
        "card_labels": card_labels,
        "priority": priority,
    }



def tier_assignments(cards: list[dict]) -> dict[int, tuple[int, str]]:
    tier0 = deck_ids()
    tier1 = set(tier1_ids())
    tier2: set[int] = set()
    for card_id, sources in usage_sources().items():
        if "decks.json" in sources:
            continue
        tier2.add(card_id)
    result: dict[int, tuple[int, str]] = {}
    for card in cards:
        card_id = int(card["id"])
        if card_id in tier0:
            result[card_id] = (0, "four_deck_union")
        elif card_id in tier1:
            result[card_id] = (1, "tier1_vertical_slice")
        elif card_id in tier2:
            result[card_id] = (2, "usage_dataset")
        else:
            result[card_id] = (3, "remaining_pool")
    return result


def script_files() -> dict[int, Path]:
    files: dict[int, Path] = {}
    if not SCRIPTS_DIR.exists():
        return files
    for path in sorted(SCRIPTS_DIR.glob("*.json")):
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError):
            continue
        card_id = payload.get("card_id")
        if isinstance(card_id, int):
            files[card_id] = path
    return files


def script_path_for(card_id: int) -> str | None:
    path = SCRIPTS_DIR / f"{card_id}.json"
    if path.exists():
        return str(path.relative_to(ROOT)).replace("\\", "/")
    return None


def classify_card(
    card: dict,
    card_id: int,
    tier: int,
    tier_reason: str,
    has_script: bool,
    name_literals: set[str],
) -> dict:
    """Classify one card for the coverage manifest.

    Status definitions:
      scripted    - a data script exists, or the current engine has a verified
                    Tier 0 name handler.
      vanilla     - the card has no effect text; summoning is covered by the
                    generic rules, fusions.json or rituals.json.
      pending     - effect text exists but no data script/handler yet.
      unsupported - the card cannot be represented yet (kept explicit).
    """
    card_type = card.get("card_type", "")
    description = (card.get("description") or "").strip()
    status = "pending"
    implementation = "none"
    covered_by = ""
    reason = "effect text not yet scripted"

    import effect_patterns  # local import avoids a cycle at module load

    if has_script:
        status = "scripted"
        implementation = "data_script"
        covered_by = script_path_for(card_id) or f"Content/Data/Effects/scripts/{card_id}.json"
        reason = "hand-authored effect script"
    elif not description:
        status = "unsupported"
        implementation = "none"
        reason = "cards.json has no description to derive behavior from"
    elif card_type == "Normal Monster":
        status = "vanilla"
        implementation = "generic"
        covered_by = "DADuelEngine.cpp:Normal Monster rules"
        reason = "no effect text"
    elif effect_patterns.ritual_procedure_only(card) and not (
        tier == 0 and card.get("name") in name_literals
    ):
        status = "vanilla"
        implementation = "generic_ritual"
        covered_by = "Content/Data/rituals.json"
        reason = "ritual procedure is data in rituals.json; no standalone effect"
    elif effect_patterns.summoning_condition_only(card) and not (
        tier == 0 and card.get("name") in name_literals
    ):
        status = "vanilla"
        implementation = "generic"
        covered_by = "summoning condition only (no scriptable effect)"
        reason = "printed text is only a summoning restriction/procedure; no effect to script"
    elif card_type == "Fusion Monster":
        if not fusion_has_effect(card):
            status = "vanilla"
            implementation = "generic_fusion"
            covered_by = "Content/Data/fusions.json"
            reason = "effect-free Fusion Monster; summon procedure is a fusion recipe"
        else:
            status = "pending"
            implementation = "none"
            reason = "Fusion Monster has effect text not yet scripted"
    elif card_type == "Ritual Monster":
        if not ritual_has_effect(card):
            status = "vanilla"
            implementation = "generic_ritual"
            covered_by = "Content/Data/rituals.json"
            reason = "effect-free Ritual Monster; summon procedure is in rituals.json"
        else:
            status = "pending"
            implementation = "none"
            reason = "Ritual Monster has effect text not yet scripted"

    # Tier 0 is the regression baseline. Credit the verified name handlers only
    # for cards that are already in the four-deck union and still need a status.
    if (
        status == "pending"
        and tier == 0
        and card.get("name") in name_literals
    ):
        status = "scripted"
        implementation = "engine_cpp"
        covered_by = "DuelAcademyIsland/Source/DuelAcademyIsland/Private/DADuelEngine.cpp"
        reason = "137-card regression baseline: exact-name handler in DADuelEngine.cpp"

    result = {
        "id": card_id,
        "name": card.get("name", ""),
        "type": card_type,
        "subtype": card.get("subtype", ""),
        "status": status,
        "tier": tier,
        "tier_reason": tier_reason,
        "implementation": implementation,
        "covered_by": covered_by,
        "source_text_hash": text_hash(description),
        "script_path": script_path_for(card_id),
        "reason": reason,
    }
    if status == "pending":
        _, reason_code, detail = effect_patterns.classify_pending(card)
        result["pending_reason_code"] = reason_code
        result["pending_reason"] = f"{reason_code}: {detail}"
    return result


def build_manifest_data(cards: list[dict] | None = None) -> dict:
    cards = cards if cards is not None else load_cards()
    tiers = tier_assignments(cards)
    scripts = script_files()
    literals = engine_name_literals()
    entries = []
    for card in sorted(cards, key=lambda item: int(item["id"])):
        card_id = int(card["id"])
        tier, tier_reason = tiers[card_id]
        entries.append(
            classify_card(
                card,
                card_id,
                tier,
                tier_reason,
                card_id in scripts,
                literals,
            )
        )
    status_counts = {key: 0 for key in STATUS_ORDER}
    tier_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for entry in entries:
        status_counts[entry["status"]] += 1
        tier_counts[entry["tier"]] += 1

    breakdown = usage_breakdown()
    card_ids = {int(card["id"]) for card in cards}
    pending_by_priority = {name: [] for name in USAGE_CATEGORY_ORDER}
    for entry in entries:
        if entry["status"] != "pending":
            continue
        priority = breakdown["priority"].get(int(entry["id"]), "long_tail")
        pending_by_priority.setdefault(priority, []).append(int(entry["id"]))
    category_counts = {}
    for name in USAGE_CATEGORY_ORDER:
        ids = {int(card_id) for card_id in breakdown["categories"][name]["cards"]} & card_ids
        pending = [
            entry["id"] for entry in entries if entry["id"] in ids and entry["status"] == "pending"
        ]
        category_counts[name] = {
            "cards": len(ids),
            "pending": len(pending),
            "covered": len(ids) - len(pending),
        }

    return {
        "schema_version": 1,
        "generated_by": "Tools/effects/build_manifest.py",
        "source": {
            "cards": "DuelAcademyIsland/Content/Data/cards.json",
            "card_count": len(cards),
            "tier0_source": "DuelAcademyIsland/Content/Data/decks.json (union of cards + extra)",
            "tier1_source": "DuelAcademyIsland/Content/Data/Effects/tier1_cards.json",
            "engine_baseline": "DuelAcademyIsland/Source/DuelAcademyIsland/Private/DADuelEngine.cpp",
        },
        "summary": {
            "total": len(entries),
            "by_status": status_counts,
            "by_tier": {str(key): value for key, value in tier_counts.items()},
        },
        "coverage_by_deck": {
            "priority_order": USAGE_CATEGORY_ORDER,
            "categories": category_counts,
            "pending_by_priority": pending_by_priority,
        },
        "cards": entries,
    }


def manifest_index(manifest: dict | None = None) -> dict[int, dict]:
    manifest = manifest if manifest is not None else load_json(MANIFEST_PATH)
    return {int(entry["id"]): entry for entry in manifest.get("cards", [])}


def material_name_map(cards: list[dict]) -> dict[str, int]:
    mapping: dict[str, int] = {}
    for card in cards:
        mapping[card["name"].lower()] = int(card["id"])
        folded = normalize_text(card["name"])
        if folded:
            mapping.setdefault(folded, int(card["id"]))
    return mapping


def resolve_material_name(
    name: str, cards: list[dict], mapping: dict[str, int] | None = None
) -> int | None:
    mapping = mapping if mapping is not None else material_name_map(cards)
    direct = mapping.get(name.lower())
    if direct is not None:
        return direct
    folded = normalize_text(name)
    if not folded:
        return None
    return mapping.get(folded)


def fusion_types_for(result: dict) -> list[str]:
    card_id = int(result["id"])
    name = result.get("name", "")
    monster_type = result.get("monster_type", "")
    contact = card_id in {745, 747, 774, 775}
    types: list[str] = []
    if contact:
        types.append("Contact Fusion")
    else:
        types.append("Polymerization")
        if "Elemental Hero" in name:
            types.append("Miracle Fusion")
        if monster_type == "Dragon":
            types.append("Dragon's Mirror")
        if monster_type == "Machine":
            types.append("Power Bond")
        types.append("Fusion Gate")
    return types
