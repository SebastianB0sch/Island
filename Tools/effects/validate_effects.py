#!/usr/bin/env python3
"""Validate the effect data, fusion recipes and ritual recipes.

Checks:
  * schema.json is a valid Draft 2020-12 schema (when jsonschema is installed)
  * every Content/Data/Effects/scripts/<id>.json validates against it
  * card ids are unique and match cards.json names/types/source text
  * every card has exactly one manifest entry
  * no unsupported card appears in decks.json, legal_cards.json or any
    optional usage dataset (Content/Data/Decks, Shop, Puzzles, Opponents, Exams)
  * every Fusion/Ritual monster has an accounted-for recipe, and no recipe
    names a material that is absent from the source card text

Errors are printed with a file/card locator and a concrete fix hint. Exit code
is 1 when any error is found.

Usage:
    python Tools/effects/validate_effects.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import effect_data as data

try:
    import jsonschema
    from jsonschema import Draft202012Validator
except ImportError:  # pragma: no cover - exercised only on minimal Pythons
    jsonschema = None
    Draft202012Validator = None

STATUSES = {"scripted", "vanilla", "unsupported", "pending"}
IMPLEMENTATIONS = {"data_script", "engine_cpp", "generic", "generic_fusion", "generic_ritual", "none"}
TIERS = {0, 1, 2, 3}
CONFIDENCE = {"high", "medium", "low", "unresolved"}
FUSION_TYPES = {
    "Polymerization",
    "Miracle Fusion",
    "Dragon's Mirror",
    "Power Bond",
    "Fusion Gate",
    "Contact Fusion",
}
CUSTOM_PREDICATES = {
    "sent_from_field_to_graveyard",
    "ignition_main_phase",
    "battle_involving_self",
    "damage_step",
    "inherent_summon",
    "opponent_activation",
    "attack_declared_against_controller",
}

# Required/optional fields per operation. The schema owns the full field list;
# this table owns semantic requirements that JSON Schema cannot express cleanly.
OP_SPECS: dict[str, dict] = {
    "add_counter": {"required": {"target", "counter", "amount"}, "optional": {"max"}},
    "allow_fusion": {"required": {"fusion_type"}, "optional": {"banish_materials"}},
    "attack_directly": {"required": {"target"}, "optional": {}},
    "attack_lock": {"required": set(), "optional": {"target", "mode", "player", "amount", "side_wide"}},
    "banish": {"required": {"target"}, "optional": {"destination", "reason"}},
    "battle_damage_modifier": {"required": {"target"}, "optional": {"mode", "amount"}},
    "battle_damage_zero": {"required": {"target"}, "optional": {}},
    "battle_position_lock": {"required": {"target"}, "optional": {"mode"}},
    "change_position": {"required": {"target", "position"}, "optional": {}},
    "control": {"required": {"target"}, "optional": {"to"}},
    "copy": {"required": {"target"}, "optional": {"name", "card_id"}},
    "damage": {"required": {"amount"}, "optional": {"player", "reason", "mode", "count_zone", "count_zones", "count_filter", "multiplier", "divisor"}},
    "declare_name": {"required": {"name"}, "optional": {}},
    "destroy": {"required": {"target"}, "optional": {"reason"}},
    "destruction_replacement": {"required": {"target"}, "optional": {"mode", "reason"}},
    "destroy_replace": {"required": {"target"}, "optional": {"mode", "reason"}},
    "discard": {"required": {"target"}, "optional": {"player", "reason"}},
    "draw": {"required": {"count"}, "optional": {"player", "reason"}},
    "equip": {"required": {"target"}, "optional": {}},
    "excavate": {"required": {"count", "target"}, "optional": {"destination", "reveal"}},
    "extra_attack": {"required": {"target"}, "optional": {"count"}},
    "fusion": {"required": set(), "optional": {"fusion_type", "card_id", "banish_materials"}},
    "gain_lp": {"required": {"amount"}, "optional": {"player", "reason", "mode", "count_zone", "count_zones", "count_filter", "multiplier", "divisor"}},
    "heal": {"required": {"amount"}, "optional": {"player", "reason", "mode", "count_zone", "count_zones", "count_filter", "multiplier", "divisor"}},
    "inflict_damage": {"required": {"amount"}, "optional": {"player", "reason", "mode", "count_zone", "count_zones", "count_filter", "multiplier", "divisor"}},
    "inherent_special_summon": {"required": {"target"}, "optional": {"position"}},
    "lock_activation": {"required": {"target"}, "optional": {"mode"}},
    "look_at_deck": {"required": {"count"}, "optional": {"player"}},
    "mill": {"required": {"count"}, "optional": {"player", "reason"}},
    "modify_atk": {"required": {"target", "amount"}, "optional": {"counter", "mode", "count_zone", "count_zones", "count_filter", "multiplier", "divisor"}},
    "modify_def": {"required": {"target", "amount"}, "optional": {"counter", "mode", "count_zone", "count_zones", "count_filter", "multiplier", "divisor"}},
    "must_attack": {"required": set(), "optional": {"target", "mode", "player", "amount", "side_wide"}},
    "negate": {"required": {"target"}, "optional": {"mode"}},
    "negate_activation": {"required": {"target"}, "optional": {"mode"}},
    "negate_attack": {"required": set(), "optional": {"target", "mode"}},
    "piercing": {"required": {"target"}, "optional": {}},
    "place_counter": {"required": {"target", "counter", "amount"}, "optional": {"max"}},
    "prevent_battle_damage": {"required": {"target"}, "optional": {"player"}},
    "redirect_attack": {"required": {"target"}, "optional": {"to"}},
    "redirect_battle_damage": {"required": {"target"}, "optional": {"to"}},
    "remove_counter": {"required": {"target", "counter", "count"}, "optional": {}},
    "return_to_extra": {"required": {"target"}, "optional": {"reason"}},
    "return_to_hand": {"required": {"target"}, "optional": {"reason"}},
    "return_to_deck": {"required": {"target"}, "optional": {"shuffle", "reason", "destination", "position"}},
    "reveal": {"required": {"target"}, "optional": {}},
    "ritual": {"required": set(), "optional": {"card_id", "target"}},
    "roll_die": {"required": set(), "optional": {"count", "success_min", "success_max", "threshold", "success_operations", "failure_operations"}},
    "search": {"required": {"target"}, "optional": {"destination", "reveal", "shuffle"}},
    "send_to_grave": {"required": {"target"}, "optional": {"reason"}},
    "send_to_graveyard": {"required": {"target"}, "optional": {"reason"}},
    "set": {"required": {"target"}, "optional": {"position"}},
    "shuffle": {"required": set(), "optional": {"player"}},
    "skip_phase": {"required": set(), "optional": {"player", "mode"}},
    "special_summon": {"required": {"target"}, "optional": {"position"}},
    "spirit_return": {"required": {"target"}, "optional": {}},
    "summon": {"required": {"target"}, "optional": {"position"}},
    "summon_lock": {"required": set(), "optional": {"player", "mode"}},
    "take_control": {"required": {"target"}, "optional": {"to"}},
    "toss_coin": {"required": set(), "optional": {"count", "success_min", "success_max", "threshold", "success_operations", "failure_operations"}},
    "union_equip": {"required": {"target"}, "optional": {"position"}},
    "union_unequip": {"required": {"target"}, "optional": {"position"}},
}

COST_SPECS: dict[str, dict] = {
    "pay_lp": {"required": {"amount"}, "optional": {}},
    "discard": {"required": {"target"}, "optional": {"count"}},
    "discard_random": {"required": {"target"}, "optional": {"count"}},
    "tribute": {"required": {"target"}, "optional": {"count"}},
    "send_to_graveyard": {"required": {"target"}, "optional": {"count"}},
    "banish": {"required": {"target"}, "optional": {"count"}},
    "return_to_hand": {"required": {"target"}, "optional": {"count"}},
    "return_to_deck": {"required": {"target"}, "optional": {"count"}},
    "reveal": {"required": {"target"}, "optional": {}},
    "mill": {"required": {"count"}, "optional": {"player"}},
    "remove_counter": {"required": {"target", "counter", "count"}, "optional": {}},
    "change_position": {"required": {"target", "position"}, "optional": {}},
    "skip_draw": {"required": {}, "optional": {}},
    "destroy_self": {"required": {}, "optional": {}},
    "shuffle": {"required": {"target"}, "optional": {}},
}

TRIGGER_REFERENCES = {
    "on_summon": {"$trigger"},
    "on_normal_summon": {"$trigger"},
    "on_special_summon": {"$trigger"},
    "on_flip_summon": {"$trigger"},
    "on_flip": {"$trigger"},
    "on_attack_declared": {"$attacker", "$trigger"},
    "on_attack_target": {"$attacker", "$attack_target", "$trigger"},
    "on_damage_step": {"$attacker", "$attack_target", "$trigger"},
    "on_damage_calculated": {"$attacker", "$attack_target", "$trigger"},
    "on_battle_damage": {"$attacker", "$attack_target", "$trigger"},
    "on_battle_destroy_by_attacker": {"$attacker", "$trigger"},
    "on_sent_to_graveyard": {"$trigger"},
    "on_destroy": {"$trigger"},
    "on_battle_destroy": {"$trigger"},
    "on_draw": {"$trigger"},
    "on_position_change": {"$trigger"},
    "on_tribute_summon": {"$trigger"},
    "inherent_summon": {"$trigger"},
}


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, location: str, message: str, hint: str = "") -> None:
        text = f"{location}: {message}"
        if hint:
            text += f"\n    FIX: {hint}"
        self.errors.append(text)

    def warning(self, location: str, message: str) -> None:
        self.warnings.append(f"{location}: {message}")

    @property
    def ok(self) -> bool:
        return not self.errors


def _type_ok(value, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def _resolve_ref(schema: dict, root: dict):
    if "$ref" not in schema:
        return schema
    reference = schema["$ref"]
    if not reference.startswith("#/"):
        return schema
    target = root
    for part in reference[2:].split("/"):
        target = target[part]
    return target


def builtin_validate(instance, schema: dict, root: dict, path: str = "$") -> list[str]:
    """Small Draft-2020-12 subset used when jsonschema is unavailable."""
    schema = _resolve_ref(schema, root)
    errors: list[str] = []

    if "oneOf" in schema:
        matches = sum(
            1 for option in schema["oneOf"] if not builtin_validate(instance, option, root, path)
        )
        if matches != 1:
            errors.append(f"{path}: expected exactly one matching oneOf branch")
        return errors
    if "anyOf" in schema:
        if not any(not builtin_validate(instance, option, root, path) for option in schema["anyOf"]):
            errors.append(f"{path}: does not match any allowed shape")
        return errors
    if "allOf" in schema:
        for option in schema["allOf"]:
            errors.extend(builtin_validate(instance, option, root, path))
        return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: expected constant {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} is not one of {schema['enum']}")
    expected_type = schema.get("type")
    if expected_type and not _type_ok(instance, expected_type):
        errors.append(f"{path}: expected {expected_type}")
        return errors

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: string is too short")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: string does not match {schema['pattern']}")
    if isinstance(instance, int) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} is below minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} is above maximum {schema['maximum']}")

    if isinstance(instance, dict):
        for required in schema.get("required", []):
            if required not in instance:
                errors.append(f"{path}: missing required property '{required}'")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in instance:
                if key not in properties:
                    errors.append(f"{path}: unexpected property '{key}'")
        for key, value in instance.items():
            if key in properties:
                errors.extend(
                    builtin_validate(value, properties[key], root, f"{path}.{key}")
                )
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(f"{path}: needs at least {schema['minItems']} item(s)")
        item_schema = schema.get("items")
        if item_schema:
            for index, value in enumerate(instance):
                errors.extend(
                    builtin_validate(value, item_schema, root, f"{path}[{index}]")
                )
    return errors


def validate_json_schema(instance, schema: dict) -> list[str]:
    if Draft202012Validator is not None:
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(instance), key=lambda err: list(err.path))
        formatted = []
        for error in errors:
            path = "$"
            for part in error.path:
                path += f".{part}" if isinstance(part, str) else f"[{part}]"
            formatted.append(f"{path}: {error.message}")
        return formatted
    return builtin_validate(instance, schema, schema)


def _spec_sets(spec: dict) -> tuple[set, set]:
    """Normalise the small OP_SPECS tables ({} is a dict, not an empty set)."""
    required = spec.get("required", set())
    optional = spec.get("optional", set())
    if isinstance(required, dict):
        required = set(required)
    if isinstance(optional, dict):
        optional = set(optional)
    return set(required), set(optional)


def _check_target(
    report: Report,
    location: str,
    target,
    context: str,
    known_refs: set[str],
) -> None:
    if isinstance(target, str):
        if target not in {"$self", "$target", "$cost", "$trigger", "$attacker", "$attack_target", "$equipped"}:
            report.error(location, f"{context}: unknown target reference '{target}'")
        return
    if not isinstance(target, dict):
        report.error(location, f"{context}: target must be an object or a $reference")
        return
    zone = target.get("zone")
    if not isinstance(zone, str):
        report.error(location, f"{context}: target is missing a zone")
    count = target.get("count")
    if isinstance(count, dict):
        if count.get("min", 0) > count.get("max", 0):
            report.error(location, f"{context}: target count min is greater than max")
    chooser = target.get("chooser")
    if chooser and chooser not in {"controller", "opponent", "random"}:
        report.error(location, f"{context}: unknown chooser '{chooser}'")


def _check_condition(report: Report, location: str, condition) -> None:
    if condition is None:
        return
    if not isinstance(condition, dict):
        report.error(location, "condition must be an object")
        return
    custom = condition.get("custom")
    if custom and custom not in CUSTOM_PREDICATES:
        report.error(
            location,
            f"unknown custom condition '{custom}'",
            "add the predicate to CUSTOM_PREDICATES in validate_effects.py and implement it in A04's runtime",
        )
    for key in ("all", "any"):
        for index, child in enumerate(condition.get(key, []) or []):
            _check_condition(report, f"{location}.{key}[{index}]", child)
    if "not" in condition:
        _check_condition(report, f"{location}.not", condition["not"])


def _check_operations(
    report: Report,
    location: str,
    operations,
    trigger: str,
    has_target: bool,
    has_cost: bool,
) -> None:
    if not isinstance(operations, list) or not operations:
        report.error(location, "operations must be a non-empty array")
        return
    for index, operation in enumerate(operations):
        op_location = f"{location}.operations[{index}]"
        if not isinstance(operation, dict):
            report.error(op_location, "operation must be an object")
            continue
        op = operation.get("op")
        spec = OP_SPECS.get(op)
        if spec is None:
            report.error(
                op_location,
                f"unknown operation '{op}'",
                "add it to schema.json's op enum and OP_SPECS, or use an existing primitive",
            )
            continue
        required, optional = _spec_sets(spec)
        missing = required - operation.keys()
        if missing:
            report.error(
                op_location,
                f"operation '{op}' is missing required field(s): {', '.join(sorted(missing))}",
            )
        allowed = required | optional | {"op", "target", "notes"}
        unknown = set(operation) - allowed
        if unknown:
            report.error(
                op_location,
                f"operation '{op}' has unsupported field(s): {', '.join(sorted(unknown))}",
            )
        target = operation.get("target")
        if isinstance(target, str):
            if target == "$target" and not has_target:
                report.error(op_location, "uses $target but the script has no target selector")
            if target == "$cost" and not has_cost:
                report.error(op_location, "uses $cost but the script has no cost")
            if target.startswith("$") and target not in {"$self", "$target", "$cost", "$trigger", "$equipped"}.union(
                TRIGGER_REFERENCES.get(trigger, set())
            ):
                report.error(
                    op_location,
                    f"reference '{target}' is not available for trigger '{trigger}'",
                )
        elif target is not None:
            _check_target(report, op_location, target, f"operation '{op}'", set())
        if op == "allow_fusion" and operation.get("fusion_type") not in FUSION_TYPES:
            report.error(op_location, f"unknown fusion_type '{operation.get('fusion_type')}'")
        if op in {"draw", "discard", "mill", "inflict_damage", "gain_lp"}:
            player = operation.get("player")
            if player and player not in {"self", "opponent", "both"}:
                report.error(op_location, f"unknown player '{player}'")
        for branch_key in ("success_operations", "failure_operations"):
            branch = operation.get(branch_key)
            if branch is not None:
                _check_operations(
                    report,
                    f"{op_location}.{branch_key}",
                    branch,
                    trigger,
                    has_target,
                    has_cost,
                )


def validate_script_payload(
    report: Report,
    path: Path,
    payload: dict,
    cards: dict[int, dict],
    manifest: dict[int, dict],
    schema: dict,
) -> None:
    location = str(path.relative_to(data.ROOT)).replace("\\", "/")
    for error in validate_json_schema(payload, schema):
        report.error(location, f"schema: {error}")

    card_id = payload.get("card_id")
    card = cards.get(card_id)
    if card is None:
        report.error(location, f"card_id {card_id} does not exist in cards.json")
        return
    if payload.get("name") != card.get("name"):
        report.error(
            location,
            f"name '{payload.get('name')}' does not match cards.json '{card.get('name')}'",
        )
    if payload.get("card_type") != card.get("card_type"):
        report.error(
            location,
            f"card_type '{payload.get('card_type')}' does not match cards.json '{card.get('card_type')}'",
        )
    if payload.get("source_text") != (card.get("description") or ""):
        report.error(
            location,
            "source_text is not byte-identical to cards.json description",
            "copy the description verbatim so the traceability hash stays valid",
        )
    expected_hash = data.text_hash(card.get("description") or "")
    manifest_entry = manifest.get(card_id)
    if manifest_entry is None:
        report.error(location, f"card_id {card_id} has no manifest entry", "run build_manifest.py")
    else:
        if manifest_entry.get("tier") != payload.get("tier"):
            report.error(
                location,
                f"tier {payload.get('tier')} does not match manifest tier {manifest_entry.get('tier')}",
                "update tier1_cards.json or rerun build_manifest.py",
            )
        if manifest_entry.get("source_text_hash") != expected_hash:
            report.error(location, "manifest source_text_hash is stale", "rerun build_manifest.py")
        if manifest_entry.get("status") != "scripted":
            report.error(
                location,
                f"manifest status is '{manifest_entry.get('status')}' but a script file exists",
                "script files must produce status=scripted after build_manifest.py",
            )

    scripts = payload.get("scripts")
    if payload.get("status") == "scripted" and not scripts:
        report.error(location, "status=scripted requires at least one script")
    if payload.get("status") != "scripted" and scripts:
        report.error(location, "only status=scripted cards may define scripts")

    seen_ids: set[str] = set()
    for index, script in enumerate(scripts or []):
        if not isinstance(script, dict):
            continue
        script_id = script.get("id")
        if script_id in seen_ids:
            report.error(location, f"duplicate script id '{script_id}'")
        seen_ids.add(script_id)
        trigger = script.get("trigger", "")
        _check_condition(report, f"{location}:{script_id}", script.get("condition"))
        has_target = isinstance(script.get("target"), dict) or isinstance(
            script.get("target"), str
        )
        if has_target:
            _check_target(
                report, f"{location}:{script_id}", script["target"], "script target", set()
            )
        _check_operations(
            report,
            f"{location}:{script_id}",
            script.get("operations", []),
            trigger,
            has_target,
            bool(script.get("cost")),
        )
        for cost_index, cost in enumerate(script.get("cost", []) or []):
            cost_location = f"{location}:{script_id}.cost[{cost_index}]"
            if not isinstance(cost, dict):
                report.error(cost_location, "cost must be an object")
                continue
            op = cost.get("op")
            spec = COST_SPECS.get(op)
            if spec is None:
                report.error(cost_location, f"unknown cost operation '{op}'")
                continue
            required, optional = _spec_sets(spec)
            missing = required - cost.keys()
            if missing:
                report.error(
                    cost_location,
                    f"cost '{op}' is missing required field(s): {', '.join(sorted(missing))}",
                )
            allowed = required | optional | {"op"}
            unknown = set(cost) - allowed
            if unknown:
                report.error(
                    cost_location,
                    f"cost '{op}' has unsupported field(s): {', '.join(sorted(unknown))}",
                )
            if "target" in cost:
                _check_target(report, cost_location, cost["target"], "cost target", set())

        spell_speed = script.get("spell_speed")
        card_type = card.get("card_type")
        subtype = card.get("subtype")
        if card_type == "Trap" and isinstance(spell_speed, int) and spell_speed < 2:
            report.error(location, f"trap script '{script_id}' must have spell_speed >= 2")
        if card_type == "Spell" and subtype == "Quick-Play" and isinstance(spell_speed, int) and spell_speed < 2:
            report.error(location, f"Quick-Play script '{script_id}' must have spell_speed >= 2")
        once = script.get("once_per_turn")
        if once is not None and not isinstance(once, bool) and once != "duel":
            report.error(location, f"script '{script_id}' has invalid once_per_turn '{once}'")


def validate_manifest(
    report: Report, manifest: dict, cards: dict[int, dict], scripts: dict[int, Path]
) -> None:
    entries = manifest.get("cards")
    if not isinstance(entries, list):
        report.error("card_effect_manifest.json", "missing top-level cards array")
        return
    if len(entries) != len(cards):
        report.error(
            "card_effect_manifest.json",
            f"has {len(entries)} entries but cards.json has {len(cards)} cards",
            "rerun build_manifest.py",
        )
    seen: set[int] = set()
    for entry in entries:
        card_id = entry.get("id")
        if card_id in seen:
            report.error("card_effect_manifest.json", f"duplicate manifest id {card_id}")
        seen.add(card_id)
        if card_id not in cards:
            report.error("card_effect_manifest.json", f"manifest id {card_id} is not in cards.json")
            continue
        card = cards[card_id]
        if entry.get("name") != card.get("name"):
            report.error(
                "card_effect_manifest.json",
                f"card {card_id} name '{entry.get('name')}' does not match cards.json",
            )
        if entry.get("status") not in STATUSES:
            report.error("card_effect_manifest.json", f"card {card_id} has invalid status")
        if entry.get("tier") not in TIERS:
            report.error("card_effect_manifest.json", f"card {card_id} has invalid tier")
        if entry.get("implementation") not in IMPLEMENTATIONS:
            report.error("card_effect_manifest.json", f"card {card_id} has invalid implementation")
        expected_hash = data.text_hash(card.get("description") or "")
        if entry.get("source_text_hash") != expected_hash:
            report.error(
                "card_effect_manifest.json",
                f"card {card_id} source_text_hash is stale",
                "rerun build_manifest.py",
            )
        if entry.get("status") == "scripted" and entry.get("implementation") == "data_script":
            if card_id not in scripts:
                report.error(
                    "card_effect_manifest.json",
                    f"card {card_id} is marked data_script but has no script file",
                )
        script_path = entry.get("script_path")
        if script_path:
            if Path(script_path).name != f"{card_id}.json":
                report.error(
                    "card_effect_manifest.json",
                    f"card {card_id} script_path must end in {card_id}.json, found '{script_path}'",
                )
            if not (data.ROOT / script_path).exists():
                report.error(
                    "card_effect_manifest.json",
                    f"card {card_id} script_path does not exist: {script_path}",
                    "rerun build_manifest.py",
                )
        if entry.get("status") != "scripted" and card_id in scripts:
            report.error(
                "card_effect_manifest.json",
                f"card {card_id} has a script file but status is {entry.get('status')}",
            )
        if entry.get("tier") == 0 and entry.get("status") not in ("scripted", "vanilla"):
            report.error(
                "card_effect_manifest.json",
                f"Tier 0 card {card_id} ({entry.get('name')}) is {entry.get('status')}",
                "restore the engine handler or add a data script; Tier 0 must stay green",
            )
        if entry.get("tier") == 1 and entry.get("status") not in ("scripted", "vanilla"):
            report.error(
                "card_effect_manifest.json",
                f"Tier 1 card {card_id} ({entry.get('name')}) is {entry.get('status')}",
                "add the vertical-slice script or remove the card from tier1_cards.json",
            )
    missing = set(cards) - seen
    for card_id in sorted(missing)[:20]:
        report.error("card_effect_manifest.json", f"missing manifest entry for card {card_id}")
    if len(missing) > 20:
        report.error(
            "card_effect_manifest.json",
            f"... and {len(missing) - 20} more missing manifest entries",
        )


def validate_usage(report: Report, manifest: dict[int, dict]) -> None:
    sources = data.usage_sources()
    for card_id, places in sorted(sources.items()):
        entry = manifest.get(card_id)
        if entry and entry.get("status") == "unsupported":
            report.error(
                "usage",
                f"unsupported card {card_id} ({entry.get('name')}) is referenced by {', '.join(sorted(places))}",
                "support the card or remove it from the deck/pack/puzzle/legal list",
            )


def validate_fusions(report: Report, cards: list[dict]) -> dict:
    by_id = data.cards_by_id(cards)
    try:
        recipes = data.load_json(data.FUSIONS_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        report.error("Content/Data/fusions.json", f"cannot load: {exc}")
        return {"total": 0, "resolved": 0, "unresolved": 0}
    if not isinstance(recipes, list):
        report.error("Content/Data/fusions.json", "top level must be an array")
        return {"total": 0, "resolved": 0, "unresolved": 0}

    seen: set[int] = set()
    resolved = 0
    unresolved = 0
    for index, recipe in enumerate(recipes):
        location = f"Content/Data/fusions.json[{index}]"
        if not isinstance(recipe, dict):
            report.error(location, "recipe must be an object")
            continue
        result = recipe.get("result")
        if result in seen:
            report.error(location, f"duplicate recipe for result {result}")
        seen.add(result)
        result_card = by_id.get(result)
        if result_card is None:
            report.error(location, f"result {result} does not exist in cards.json")
            continue
        if result_card.get("card_type") != "Fusion Monster":
            report.error(location, f"result {result} is not a Fusion Monster")
        if recipe.get("name") != result_card.get("name"):
            report.error(location, f"name does not match cards.json '{result_card.get('name')}'")

        confidence = recipe.get("confidence")
        if confidence not in CONFIDENCE:
            report.error(location, f"invalid confidence '{confidence}'")
        status = recipe.get("status")
        if status not in {"resolved", "unresolved"}:
            report.error(location, f"invalid status '{status}'")
        if status == "resolved":
            resolved += 1
        else:
            unresolved += 1

        fusion_types = recipe.get("fusionTypes")
        if not isinstance(fusion_types, list) or not fusion_types:
            report.error(location, "fusionTypes must be a non-empty array")
        else:
            for fusion_type in fusion_types:
                if fusion_type not in FUSION_TYPES:
                    report.error(location, f"unknown fusion type '{fusion_type}'")

        source = recipe.get("source")
        if not isinstance(source, dict):
            report.error(location, "source must be an object")
        elif source.get("card_id") != result:
            report.error(location, "source.card_id must equal result")

        materials_type = recipe.get("materialsType", "")
        any_count = recipe.get("anyCount", 0)
        materials = recipe.get("materials", [])
        if not isinstance(materials, list):
            report.error(location, "materials must be an array")
            materials = []
        for material in materials:
            if not isinstance(material, int) or material not in by_id:
                report.error(location, f"material {material!r} does not exist in cards.json")
            elif not by_id[material].get("card_type", "").endswith("Monster"):
                report.error(location, f"material {material} is not a monster")
            elif material == result:
                report.error(location, "a Fusion Monster cannot be its own material")

        if status == "resolved":
            if not materials and not (materials_type and any_count):
                report.error(location, "resolved recipe has no materials and no generic materialsType/anyCount")
            if materials_type and not any_count:
                report.error(location, "materialsType requires anyCount")
            if any_count and not materials_type:
                report.error(location, "anyCount requires materialsType")
            if materials_type and materials_type not in {
                "Dragon", "Warrior", "Spellcaster", "Machine", "Fiend", "Fairy",
                "Beast", "Beast-Warrior", "Aqua", "Zombie", "Rock", "Insect",
                "Pyro", "Winged Beast", "Fish", "Plant", "Reptile", "Dinosaur",
                "Thunder", "Sea Serpent",
            }:
                report.error(location, f"unknown materialsType '{materials_type}'")

            description = data.normalize_text(result_card.get("description") or "")
            override = bool(source.get("override")) if isinstance(source, dict) else False
            if materials and not override:
                for material in materials:
                    name = data.normalize_text(by_id[material].get("name", ""))
                    if name and name not in description:
                        report.error(
                            location,
                            f"material {material} ('{by_id[material].get('name')}') is not named in the result card text",
                            "remove the invented material or mark source.override with a note",
                        )
            if materials_type and materials_type.lower() not in description:
                report.error(
                    location,
                    f"generic materialsType '{materials_type}' is not mentioned in the result card text",
                )
        else:
            if materials or any_count:
                report.error(
                    location,
                    "unresolved recipe must not expose materials/anyCount (the engine loader would use them)",
                )
            if not recipe.get("reason"):
                report.error(location, "unresolved recipe needs a reason")

    for card in cards:
        if card.get("card_type") == "Fusion Monster" and int(card["id"]) not in seen:
            report.error(
                "Content/Data/fusions.json",
                f"missing recipe for Fusion Monster {card['id']} ({card['name']})",
                "add a resolved recipe or an explicit unresolved record",
            )
    return {"total": len(recipes), "resolved": resolved, "unresolved": unresolved}


def validate_rituals(report: Report, cards: list[dict]) -> dict:
    by_id = data.cards_by_id(cards)
    try:
        rituals = data.load_json(data.RITUALS_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        report.error("Content/Data/rituals.json", f"cannot load: {exc}")
        return {"total": 0, "resolved": 0, "unresolved": 0}
    if not isinstance(rituals, list):
        report.error("Content/Data/rituals.json", "top level must be an array")
        return {"total": 0, "resolved": 0, "unresolved": 0}

    seen: set[int] = set()
    resolved = 0
    unresolved = 0
    for index, ritual in enumerate(rituals):
        location = f"Content/Data/rituals.json[{index}]"
        if not isinstance(ritual, dict):
            report.error(location, "ritual entry must be an object")
            continue
        monster_id = ritual.get("monster")
        if monster_id in seen:
            report.error(location, f"duplicate ritual entry for monster {monster_id}")
        seen.add(monster_id)
        monster = by_id.get(monster_id)
        if monster is None:
            report.error(location, f"monster {monster_id} does not exist in cards.json")
            continue
        if monster.get("card_type") != "Ritual Monster":
            report.error(location, f"monster {monster_id} is not a Ritual Monster")
        if ritual.get("name") != monster.get("name"):
            report.error(location, f"name does not match cards.json '{monster.get('name')}'")
        if ritual.get("level") != monster.get("level"):
            report.error(location, "level does not match cards.json")
        confidence = ritual.get("confidence")
        if confidence not in CONFIDENCE:
            report.error(location, f"invalid confidence '{confidence}'")
        status = ritual.get("status")
        if status not in {"resolved", "unresolved"}:
            report.error(location, f"invalid status '{status}'")
        if status == "resolved":
            resolved += 1
        else:
            unresolved += 1

        spell_id = ritual.get("ritual_spell")
        spell = by_id.get(spell_id)
        if spell is None:
            report.error(location, f"ritual_spell {spell_id} does not exist in cards.json")
        else:
            if spell.get("card_type") != "Spell":
                report.error(location, f"ritual_spell {spell_id} is not a Spell")
            if ritual.get("ritual_spell_name") != spell.get("name"):
                report.error(location, "ritual_spell_name does not match cards.json")
            spell_text = data.normalize_text(spell.get("description") or "")
            monster_name = data.normalize_text(monster.get("name") or "")
            if monster_name and monster_name not in spell_text:
                report.error(
                    location,
                    f"ritual spell does not name '{monster.get('name')}' in its text",
                )

        level_requirement = ritual.get("level_requirement")
        if not isinstance(level_requirement, int) or level_requirement < 1:
            report.error(location, "level_requirement must be a positive integer")
        materials = ritual.get("materials")
        if not isinstance(materials, dict):
            report.error(location, "materials must be an object")
        else:
            if materials.get("mode") != "level_sum":
                report.error(location, "materials.mode must be 'level_sum'")
            if materials.get("min_total_level") != level_requirement:
                report.error(location, "materials.min_total_level must equal level_requirement")
            if materials.get("tribute") is not True:
                report.error(location, "materials.tribute must be true")

        source = ritual.get("source")
        if not isinstance(source, dict):
            report.error(location, "source must be an object")
        else:
            if source.get("monster_id") != monster_id:
                report.error(location, "source.monster_id must equal monster")
            if source.get("spell_id") != spell_id:
                report.error(location, "source.spell_id must equal ritual_spell")

        if status == "unresolved" and not ritual.get("reason"):
            report.error(location, "unresolved ritual needs a reason")

    for card in cards:
        if card.get("card_type") == "Ritual Monster" and int(card["id"]) not in seen:
            report.error(
                "Content/Data/rituals.json",
                f"missing ritual entry for Ritual Monster {card['id']} ({card['name']})",
            )
    return {"total": len(rituals), "resolved": resolved, "unresolved": unresolved}


def validate(root: Path | None = None) -> tuple[Report, dict]:
    report = Report()
    cards = data.load_cards()
    card_index = data.cards_by_id(cards)

    try:
        schema = data.load_json(data.SCHEMA_PATH)
    except (OSError, json.JSONDecodeError) as exc:
        report.error("Content/Data/Effects/schema.json", f"cannot load: {exc}")
        return report, {"fusion": {}, "ritual": {}, "scripts": 0}

    if Draft202012Validator is not None:
        try:
            Draft202012Validator.check_schema(schema)
        except Exception as exc:  # noqa: BLE001 - surfaced as a data error
            report.error("Content/Data/Effects/schema.json", f"invalid JSON Schema: {exc}")

    if not data.MANIFEST_PATH.exists():
        report.error(
            "Content/Data/Effects/card_effect_manifest.json",
            "manifest is missing",
            "run python Tools/effects/build_manifest.py",
        )
        manifest = {}
    else:
        manifest = data.load_json(data.MANIFEST_PATH)
        validate_manifest(report, manifest, card_index, data.script_files())
    manifest_by_id = data.manifest_index(manifest) if manifest else {}

    script_paths = sorted(data.SCRIPTS_DIR.glob("*.json")) if data.SCRIPTS_DIR.exists() else []
    seen_cards: dict[int, Path] = {}
    seen_script_ids: dict[str, Path] = {}
    for path in script_paths:
        try:
            payload = data.load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            report.error(str(path), f"cannot load script JSON: {exc}")
            continue
        card_id = payload.get("card_id") if isinstance(payload, dict) else None
        if not isinstance(card_id, int):
            report.error(str(path), "script has no integer card_id")
            continue
        if card_id in seen_cards:
            report.error(
                str(path),
                f"duplicate script file for card {card_id} (already in {seen_cards[card_id].name})",
                "keep exactly one Effect/scripts/<card_id>.json per card",
            )
        else:
            seen_cards[card_id] = path
        for item in payload.get("scripts", []) or []:
            if not isinstance(item, dict):
                continue
            script_id = item.get("id")
            if not isinstance(script_id, str):
                continue
            if script_id in seen_script_ids:
                report.error(
                    str(path),
                    f"duplicate script id '{script_id}' (already in {seen_script_ids[script_id].name})",
                    "script ids are required to be unique across the whole scripts directory",
                )
            else:
                seen_script_ids[script_id] = path
        validate_script_payload(report, path, payload, card_index, manifest_by_id, schema)
        if path.stem != str(card_id):
            report.warning(str(path), f"file name should be {card_id}.json to match card_id")

    validate_usage(report, manifest_by_id)
    fusion_stats = validate_fusions(report, cards)
    ritual_stats = validate_rituals(report, cards)
    return report, {
        "fusion": fusion_stats,
        "ritual": ritual_stats,
        "scripts": len(seen_cards),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--quiet-warnings",
        action="store_true",
        help="Only print errors.",
    )
    args = parser.parse_args(argv)
    report, stats = validate()
    for warning in report.warnings:
        if not args.quiet_warnings:
            print(f"WARNING {warning}")
    for error in report.errors:
        print(f"ERROR {error}")
    if report.errors:
        print(f"\nFAILED: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        return 1
    print(
        "OK: "
        f"{stats['scripts']} effect script(s), "
        f"fusion {stats['fusion'].get('resolved', 0)}/{stats['fusion'].get('total', 0)} resolved, "
        f"ritual {stats['ritual'].get('resolved', 0)}/{stats['ritual'].get('total', 0)} resolved, "
        f"{len(report.warnings)} warning(s)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
