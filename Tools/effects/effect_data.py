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

    return {
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
