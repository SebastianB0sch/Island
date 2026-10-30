#!/usr/bin/env python3
"""Propose fusion and ritual recipes from cards.json.

Fusion recipes are extracted only from the material clause printed on the
Fusion Monster itself. Ritual recipes are reconciled against both the Ritual
Monster text and the Ritual Spell text. Nothing is guessed: anything that
cannot be resolved is emitted with status "unresolved" and a reason.

Outputs:
  Content/Data/Effects/fusion_candidates.json  review copy (all 76 Fusions)
  Content/Data/fusions.json                    engine-facing recipes
  Content/Data/rituals.json                    22 Ritual summon procedures

Usage:
  python Tools/effects/extract_fusion_recipes.py
  python Tools/effects/extract_fusion_recipes.py --check
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import effect_data as data

# cards.json contains a corrupted separator in Deepsea Shark's material line.
# The two named materials still exist in the card pool, so record the repair
# explicitly rather than silently matching fuzzy text.
MANUAL_MATERIAL_OVERRIDES: dict[int, list[int]] = {
    193: [194, 240],
}

CONTACT_FUSION_IDS = {745, 747, 774, 775}


def _material_clause(card: dict) -> str | None:
    description = (card.get("description") or "").strip()
    match = data.FUSION_MATERIAL_PREFIX.match(description)
    if match:
        return match.group(0)
    return None


def _resolve_names(
    names: list[str], cards: list[dict], mapping: dict[str, int]
) -> tuple[list[int], list[str]]:
    resolved: list[int] = []
    unresolved: list[str] = []
    for name in names:
        card_id = data.resolve_material_name(name, cards, mapping)
        if card_id is None:
            unresolved.append(name)
        else:
            resolved.append(card_id)
    return resolved, unresolved


def _source(
    result_id: int, method: str, override: bool = False
) -> dict:
    return {
        "type": "card_text",
        "card_id": result_id,
        "field": "description",
        "method": method,
        "override": override,
    }


def extract_fusion_candidates(cards: list[dict]) -> list[dict]:
    mapping = data.material_name_map(cards)
    by_id = data.cards_by_id(cards)
    candidates: list[dict] = []

    for card in sorted(
        (item for item in cards if item.get("card_type") == "Fusion Monster"),
        key=lambda item: int(item["id"]),
    ):
        result_id = int(card["id"])
        description = (card.get("description") or "").strip()
        material_names: list[str] = []
        materials: list[int] = []
        unresolved_names: list[str] = []
        materials_type = ""
        any_count = 0
        method = "explicit_materials"
        override = False
        notes: list[str] = []
        status = "resolved"
        confidence = "high"

        if result_id == 722:
            materials_type = "Dragon"
            any_count = 5
            method = "generic_type_count"
            confidence = "medium"
            material_names = ["5 Dragon monsters"]
            notes.append(
                "Card text defines a class of materials, not five named cards. "
                "The recipe is intentionally generic."
            )
        elif result_id in MANUAL_MATERIAL_OVERRIDES:
            materials = list(MANUAL_MATERIAL_OVERRIDES[result_id])
            material_names = [by_id[item]["name"] for item in materials]
            method = "manual_override"
            override = True
            confidence = "medium"
            notes.append(
                "cards.json contains a corrupted '+' separator in the material "
                "line; material names were resolved from the two quoted names."
            )
        else:
            clause = _material_clause(card)
            names = re.findall(r'"([^"]+)"', clause) if clause else []
            if not names:
                status = "unresolved"
                confidence = "unresolved"
                method = "unresolved"
                notes.append("No quoted material clause was found in card text.")
            else:
                material_names = names
                generic_slots = [
                    name
                    for name in names
                    if re.match(r"^\d+\s+.+Type monster$", name, re.I)
                ]
                specific_names = [name for name in names if name not in generic_slots]
                materials, unresolved_names = _resolve_names(
                    specific_names, cards, mapping
                )
                if any(any(ord(character) > 127 for character in name) for name in names):
                    method = "normalized_name_match"
                    confidence = "medium"
                    notes.append(
                        "Material name contains a non-ASCII corruption in cards.json; "
                        "resolved by normalized comparison."
                    )
                if generic_slots or unresolved_names:
                    status = "unresolved"
                    confidence = "unresolved"
                    method = "unresolved"
                    if generic_slots:
                        notes.append(
                            "Mixed specific/generic material slot is not representable "
                            "by the current engine recipe model: "
                            + ", ".join(generic_slots)
                        )
                    if unresolved_names:
                        notes.append(
                            "Unresolved material names: " + ", ".join(unresolved_names)
                        )

        fusion_types = data.fusion_types_for(card)
        if status == "resolved" and not materials and not any_count:
            status = "unresolved"
            confidence = "unresolved"
            notes.append("No usable materials after parsing.")

        engine_ready = (
            status == "resolved"
            and "Polymerization" in fusion_types
            and bool(materials or any_count)
        )
        if "Contact Fusion" in fusion_types:
            engine_ready = False
            notes.append(
                "Requires a banish-from-field contact-fusion primitive; the "
                "current engine does not implement it yet."
            )
        engine_supported = {
            "Polymerization",
            "Miracle Fusion",
            "Dragon's Mirror",
        }
        if not engine_supported.intersection(fusion_types):
            notes.append(
                "No fusion type in this recipe is currently resolved by "
                "DADuelEngine.cpp; A04 support is tracked in RUNTIME_INTERFACE.md."
            )

        candidate = {
            "result": result_id,
            "materials": materials,
            "fusionTypes": fusion_types,
            "name": card.get("name", ""),
            "confidence": confidence,
            "source": _source(result_id, method, override),
            "status": status,
            "materialNames": material_names,
            "engineReady": engine_ready,
            "notes": notes,
        }
        if materials_type:
            candidate["materialsType"] = materials_type
        if any_count:
            candidate["anyCount"] = any_count
        if status == "unresolved":
            candidate["reason"] = notes[0] if notes else "Unresolved material clause."
        candidates.append(candidate)

    return candidates


def fusion_summary(candidates: list[dict]) -> dict:
    return {
        "fusion_monsters": len(candidates),
        "resolved": sum(1 for item in candidates if item["status"] == "resolved"),
        "unresolved": sum(1 for item in candidates if item["status"] == "unresolved"),
        "engine_ready": sum(1 for item in candidates if item.get("engineReady")),
        "by_confidence": {
            key: sum(1 for item in candidates if item["confidence"] == key)
            for key in ("high", "medium", "low", "unresolved")
        },
    }


def canonical_fusion_recipes(candidates: list[dict]) -> list[dict]:
    recipes: list[dict] = []
    for candidate in candidates:
        resolved = candidate["status"] == "resolved"
        recipe = {
            "result": candidate["result"],
            # Unresolved recipes deliberately carry no usable material list so
            # the current loader (which accepts materials or anyCount) skips
            # them instead of fusing with a partial/incorrect requirement.
            "materials": candidate["materials"] if resolved else [],
            "fusionTypes": candidate["fusionTypes"],
            "name": candidate["name"],
            "confidence": candidate["confidence"],
            "source": candidate["source"],
            "status": candidate["status"],
            "materialNames": candidate.get("materialNames", []),
            "engineReady": candidate.get("engineReady", False),
            "notes": candidate.get("notes", []),
        }
        if resolved and candidate.get("materialsType"):
            recipe["materialsType"] = candidate["materialsType"]
        if resolved and candidate.get("anyCount"):
            recipe["anyCount"] = candidate["anyCount"]
        if not resolved:
            recipe["reason"] = candidate.get(
                "reason", "Unresolved material clause."
            )
        recipes.append(recipe)
    return recipes


def _extract_level_requirement(text: str) -> int | None:
    for pattern in data.RITUAL_LEVEL_PATTERNS:
        match = pattern.search(text)
        if match:
            return int(match.group(1))
    return None


def _find_ritual_spell(card: dict, cards: list[dict]) -> tuple[dict | None, str]:
    description = (card.get("description") or "").strip()
    match = data.RITUAL_SPELL_PATTERN.search(description)
    if match:
        spell_name = match.group(1).lower()
        for candidate in cards:
            if (
                candidate.get("card_type") == "Spell"
                and candidate.get("name", "").lower() == spell_name
            ):
                return candidate, "monster_text"
    # Fallback: a Ritual Spell that names this monster in its own text. This
    # covers Relinquished, Reshef and Elemental Mistress Doriado, whose monster
    # text does not repeat the spell name.
    target = card.get("name", "")
    quoted = f'"{target}"'
    for candidate in cards:
        if candidate.get("card_type") != "Spell":
            continue
        spell_description = (candidate.get("description") or "")
        lowered = spell_description.lower()
        if "ritual" not in lowered:
            continue
        if quoted.lower() in lowered:
            return candidate, "ritual_spell_text"
    return None, "unresolved"


def extract_rituals(cards: list[dict]) -> list[dict]:
    rituals: list[dict] = []
    for card in sorted(
        (item for item in cards if item.get("card_type") == "Ritual Monster"),
        key=lambda item: int(item["id"]),
    ):
        monster_id = int(card["id"])
        description = (card.get("description") or "").strip()
        spell, method = _find_ritual_spell(card, cards)
        notes: list[str] = []
        # The printed Level of the Ritual Monster is the canonical level sum in
        # this card pool. Card descriptions contain two known typos (Zera's
        # monster text and War-Lion Ritual's spell text); flag either mismatch
        # rather than silently preferring one prose source over the other.
        level_requirement = int(card.get("level") or 0)
        monster_text_level = _extract_level_requirement(description)
        spell_level = (
            _extract_level_requirement(spell.get("description", "")) if spell else None
        )
        if monster_text_level is not None and monster_text_level != level_requirement:
            notes.append(
                f"Monster description says total Level {monster_text_level}; "
                f"the printed Level is {level_requirement}. The printed Level is used."
            )
        if spell_level is not None and spell_level != level_requirement:
            notes.append(
                f"Ritual Spell text says total Level {spell_level}; the printed "
                f"Level is {level_requirement}. The printed Level is used."
            )
        if spell is not None:
            method = "monster_and_spell_text"

        confidence = "high"
        status = "resolved"
        reason = ""
        if spell is None:
            status = "unresolved"
            confidence = "unresolved"
            reason = "No matching Ritual Spell Card found in cards.json."
        elif level_requirement < 1:
            status = "unresolved"
            confidence = "unresolved"
            reason = "Ritual Monster has no printed Level."
        elif notes:
            confidence = "medium"

        ritual = {
            "monster": monster_id,
            "name": card.get("name", ""),
            "level": int(card.get("level") or 0),
            "ritual_spell": int(spell["id"]) if spell else 0,
            "ritual_spell_name": spell.get("name", "") if spell else "",
            "level_requirement": level_requirement or 0,
            "materials": {
                "mode": "level_sum",
                "min_total_level": level_requirement or 0,
                "tribute": True,
                "zones": ["hand", "field"],
            },
            "confidence": confidence,
            "source": {
                "type": "card_text",
                "monster_id": monster_id,
                "spell_id": int(spell["id"]) if spell else 0,
                "method": method,
            },
            "status": status,
            "notes": notes,
        }
        if status == "unresolved":
            ritual["reason"] = reason
        rituals.append(ritual)
    return rituals


def ritual_summary(rituals: list[dict]) -> dict:
    return {
        "ritual_monsters": len(rituals),
        "resolved": sum(1 for item in rituals if item["status"] == "resolved"),
        "unresolved": sum(1 for item in rituals if item["status"] == "unresolved"),
        "by_confidence": {
            key: sum(1 for item in rituals if item["confidence"] == key)
            for key in ("high", "medium", "low", "unresolved")
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Extract and report without writing any output file.",
    )
    parser.add_argument(
        "--candidates-only",
        action="store_true",
        help="Write fusion_candidates.json but not fusions.json.",
    )
    parser.add_argument(
        "--rituals-only",
        action="store_true",
        help="Write rituals.json only.",
    )
    args = parser.parse_args(argv)

    cards = data.load_cards()
    candidates = extract_fusion_candidates(cards)
    rituals = extract_rituals(cards)

    print("Fusion:", fusion_summary(candidates))
    print("Ritual:", ritual_summary(rituals))

    if args.check:
        return 0

    if not args.rituals_only:
        payload = {
            "schema_version": 1,
            "generated_by": "Tools/effects/extract_fusion_recipes.py",
            "source": "DuelAcademyIsland/Content/Data/cards.json",
            "summary": fusion_summary(candidates),
            "candidates": candidates,
        }
        data.write_json(data.CANDIDATES_PATH, payload)
        print(f"Wrote {data.CANDIDATES_PATH.relative_to(data.ROOT)}")
        if not args.candidates_only:
            data.write_json(
                data.FUSIONS_PATH, canonical_fusion_recipes(candidates)
            )
            print(f"Wrote {data.FUSIONS_PATH.relative_to(data.ROOT)}")

    if not args.candidates_only:
        data.write_json(data.RITUALS_PATH, rituals)
        print(f"Wrote {data.RITUALS_PATH.relative_to(data.ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
