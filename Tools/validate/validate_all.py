#!/usr/bin/env python3
"""Duel Academy port data validator.

Usage:
    python Tools/validate/validate_all.py
    python Tools/validate/validate_all.py --strict
    python Tools/validate/validate_all.py --json --report Content/Data/Integration/reports/validate.json

The validator is deliberately usable from day one: a lane that has not published
its data yet produces a GAP, not a crash. Structural errors in files that do
exist are failures. --strict promotes gaps and warnings to failures for a gate.

Exit codes:
    0  no errors (baseline mode), or all checks green
    1  errors, or warnings/gaps under --strict
    2  configuration/internal error
"""

from __future__ import annotations

import argparse
import collections
import datetime as _dt
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import schema_lite  # noqa: E402  (local module)

TOOL_VERSION = "1.1.0"
DEFAULT_ROOT = HERE.parents[1]
LEVEL_ORDER = {"info": 0, "gap": 1, "warning": 2, "error": 3}
CHECK_STATUS = {"pass", "warn", "fail", "gap", "info"}

CARD_TYPES = {
    "Normal Monster",
    "Effect Monster",
    "Fusion Monster",
    "Ritual Monster",
    "Spell",
    "Trap",
}
MONSTER_TYPES = {"Normal Monster", "Effect Monster", "Fusion Monster", "Ritual Monster"}
ATTRIBUTES = {"DARK", "EARTH", "FIRE", "LIGHT", "WATER", "WIND", "NONE"}
SUBTYPES = {
    "Normal",
    "Effect",
    "Fusion",
    "Ritual",
    "Continuous",
    "Equip",
    "Quick-Play",
    "Field",
    "Counter",
}
DORMS = {"Slifer", "Ra", "Obelisk", "White", "Staff", "Event", "Exam"}
PERIODS = {"AM", "PM", "Night"}
WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
DUEL_MODES = {"story", "free", "exam_timed", "exam_practical", "puzzle", "ante", "tutorial"}
EVENT_STATES = {"available", "active", "complete", "failed", "skipped"}
EFFECT_STATUSES = {"scripted", "vanilla", "unsupported"}
PRACTICAL_OBJECTIVES = {
    "battle",
    "spells",
    "traps",
    "damage",
    "fusion",
    "ritual",
    "special_summon",
}
STORY_COMMANDS = {
    "Dialogue",
    "Choice",
    "Camera",
    "MoveNpc",
    "Fade",
    "Wait",
    "Banner",
    "PlaySfx",
    "Music",
    "Duel",
    "Reward",
    "SetFlag",
    "End",
}
PUZZLE_ACTIONS = {
    "normal_summon",
    "tribute_summon",
    "set_monster",
    "special_summon",
    "activate_spell",
    "set_spell_trap",
    "activate_trap",
    "flip_summon",
    "change_position",
    "activate_effect",
    "attack",
    "direct_attack",
    "fusion_summon",
    "ritual_summon",
    "discard",
    "end_turn",
}
SLUG_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
SCENE_ID_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*(?:\.[a-z0-9]+(?:_[a-z0-9]+)*)*$")
ANCHOR_RE = re.compile(r"^[a-z0-9_]+(?:\.[a-z0-9_]+)*$")
EVENT_RE = re.compile(r"^[A-Z]{1,3}[0-9]{2}[a-z]?$")
PUZZLE_RE = re.compile(r"^P[0-9]{3}$")
EXAM_RE = re.compile(r"^EXAM_[0-9]{2}$")
CARD_KEY_RE = re.compile(r"^[1-9][0-9]{0,3}$")


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    level: str
    code: str
    message: str
    file: str = ""
    path: str = ""
    hint: str = ""
    owner: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = {
            "level": self.level,
            "code": self.code,
            "message": self.message,
            "owner": self.owner,
        }
        if self.file:
            data["file"] = self.file
        if self.path:
            data["path"] = self.path
        if self.hint:
            data["hint"] = self.hint
        return data


@dataclass
class Check:
    key: str
    status: str
    summary: str
    owner: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "status": self.status,
            "summary": self.summary,
            "owner": self.owner,
        }


@dataclass
class Report:
    root: Path
    data_dir: Path
    contracts_dir: Path
    strict: bool = False
    fail_on_gaps: bool = False
    findings: list[Finding] = field(default_factory=list)
    checks: list[Check] = field(default_factory=list)
    files_read: list[str] = field(default_factory=list)
    json_errors: list[str] = field(default_factory=list)
    schema_errors: int = 0

    def add(
        self,
        level: str,
        code: str,
        message: str,
        *,
        file: str = "",
        path: str = "",
        hint: str = "",
        owner: str = "",
    ) -> None:
        if level not in LEVEL_ORDER:
            raise ValueError(f"bad finding level: {level}")
        self.findings.append(
            Finding(level, code, message, file=file, path=path, hint=hint, owner=owner)
        )

    def info(self, code: str, message: str, **kwargs: Any) -> None:
        self.add("info", code, message, **kwargs)

    def gap(self, code: str, message: str, **kwargs: Any) -> None:
        self.add("gap", code, message, **kwargs)

    def warn(self, code: str, message: str, **kwargs: Any) -> None:
        self.add("warning", code, message, **kwargs)

    def error(self, code: str, message: str, **kwargs: Any) -> None:
        self.add("error", code, message, **kwargs)

    def check(self, key: str, status: str, summary: str, owner: str = "") -> None:
        if status not in CHECK_STATUS:
            raise ValueError(f"bad check status: {status}")
        self.checks.append(Check(key, status, summary, owner))

    def counts(self) -> dict[str, int]:
        counts = {level: 0 for level in LEVEL_ORDER}
        for finding in self.findings:
            counts[finding.level] += 1
        return counts

    def result(self) -> str:
        counts = self.counts()
        failed = counts["error"] > 0
        if self.strict and (counts["warning"] > 0 or counts["gap"] > 0):
            failed = True
        if self.fail_on_gaps and counts["gap"] > 0:
            failed = True
        return "FAIL" if failed else "PASS"

    def as_dict(self) -> dict[str, Any]:
        counts = self.counts()
        return {
            "tool": "validate_all",
            "tool_version": TOOL_VERSION,
            "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "root": str(self.root),
            "data_dir": str(self.data_dir),
            "contracts_dir": str(self.contracts_dir),
            "strict": self.strict,
            "fail_on_gaps": self.fail_on_gaps,
            "result": self.result(),
            "counts": {
                "errors": counts["error"],
                "warnings": counts["warning"],
                "gaps": counts["gap"],
                "infos": counts["info"],
                "checks": len(self.checks),
                "files_read": len(self.files_read),
            },
            "checks": [check.to_dict() for check in self.checks],
            "findings": [finding.to_dict() for finding in self.findings],
            "files": self.files_read,
        }


# ---------------------------------------------------------------------------
# Context and file helpers
# ---------------------------------------------------------------------------


@dataclass
class Context:
    root: Path
    data_dir: Path
    contracts_dir: Path
    cards: dict[int, dict] = field(default_factory=dict)
    card_doc: Any = None
    decks: dict[str, dict] = field(default_factory=dict)
    deck_sources: dict[str, str] = field(default_factory=dict)
    fusions: list[dict] = field(default_factory=list)
    limitations: dict[str, set[int]] = field(
        default_factory=lambda: {"forbidden": set(), "limited": set(), "semi_limited": set()}
    )
    packs: dict[str, dict] = field(default_factory=dict)
    opponents: dict[str, dict] = field(default_factory=dict)
    puzzles: dict[str, dict] = field(default_factory=dict)
    exams: dict[str, dict] = field(default_factory=dict)
    questions: dict[str, dict] = field(default_factory=dict)
    events: dict[str, dict] = field(default_factory=dict)
    dialogue: dict[str, dict] = field(default_factory=dict)
    emails: dict[str, dict] = field(default_factory=dict)
    schedules: dict[str, dict] = field(default_factory=dict)
    locations: dict[str, dict] = field(default_factory=dict)
    anchors: dict[str, dict] = field(default_factory=dict)
    portals: list[dict] = field(default_factory=list)
    spawns: list[dict] = field(default_factory=list)
    effect_manifest: dict[int, dict] = field(default_factory=dict)
    effect_scripts: dict[str, dict] = field(default_factory=dict)
    scene_refs: dict[str, str] = field(default_factory=dict)
    referenced_text_keys: set[str] = field(default_factory=set)
    written_flags: set[str] = field(default_factory=set)
    read_flags: set[str] = field(default_factory=set)
    written_counters: set[str] = field(default_factory=set)
    read_counters: set[str] = field(default_factory=set)
    event_requires: dict[str, list[str]] = field(default_factory=dict)
    legacy_scene_refs: list[tuple[str, str, str]] = field(default_factory=list)
    scene_ids: set[str] = field(default_factory=set)
    missing_anchors: set[str] = field(default_factory=set)
    missing_locations: set[str] = field(default_factory=set)
    pack_cards: set[int] = field(default_factory=set)
    reward_cards: set[int] = field(default_factory=set)
    reward_packs: set[str] = field(default_factory=set)
    deck_cards: set[int] = field(default_factory=set)
    puzzle_cards: set[int] = field(default_factory=set)
    exam_cards: set[int] = field(default_factory=set)
    unsupported_cards: set[int] = field(default_factory=set)
    dataset_presence: dict[str, bool] = field(default_factory=dict)


def rel_path(report: Report, path: Path) -> str:
    try:
        return path.resolve().relative_to(report.root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _no_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def load_json(path: Path, report: Report, *, required: bool = False) -> Any:
    if not path.exists():
        if required:
            report.error(
                "file_missing",
                f"required file not found: {rel_path(report, path)}",
                file=rel_path(report, path),
                hint="publish the file from the owning lane",
            )
        return None
    try:
        text = path.read_text(encoding="utf-8")
        document = json.loads(text, object_pairs_hook=_no_duplicate_keys)
    except json.JSONDecodeError as exc:
        report.error(
            "json_parse",
            f"invalid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})",
            file=rel_path(report, path),
            hint="fix the reported line before re-running",
        )
        report.json_errors.append(rel_path(report, path))
        return None
    except ValueError as exc:
        report.error(
            "json_duplicate_key",
            str(exc),
            file=rel_path(report, path),
            hint="JSON objects must not repeat keys",
        )
        report.json_errors.append(rel_path(report, path))
        return None
    report.files_read.append(rel_path(report, path))
    return document


def collection(document: Any, key: str) -> list:
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        value = document.get(key)
        if isinstance(value, list):
            return value
        if isinstance(document.get("items"), list):
            return document["items"]
    return []


def first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def glob_json(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(directory.glob("*.json"))


def valid_card_id(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 1200


def as_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return None


def as_number(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def norm_card_list(values: Any) -> list[int]:
    """Normalize [1, {"card": 1, "count": 2}] to a flat id list (count repeated)."""
    result: list[int] = []
    if not isinstance(values, list):
        return result
    for item in values:
        if isinstance(item, int) and not isinstance(item, bool):
            result.append(item)
        elif isinstance(item, dict):
            card = item.get("card")
            count = item.get("count", 1)
            if isinstance(card, int) and not isinstance(card, bool):
                repeat = count if isinstance(count, int) and count > 0 else 1
                result.extend([card] * min(repeat, 99))
    return result


def norm_pool_entries(values: Any) -> list[dict]:
    """Return [{card, rarity?, weight?}] from ints or objects."""
    result: list[dict] = []
    if not isinstance(values, list):
        return result
    for item in values:
        if isinstance(item, int) and not isinstance(item, bool):
            result.append({"card": item})
        elif isinstance(item, dict) and isinstance(item.get("card"), int):
            result.append(item)
    return result


def schema_path(report: Report, name: str) -> Path:
    return report.contracts_dir / "schemas" / f"{name}.schema.json"


def apply_schema(document: Any, schema_name: str, rel: str, report: Report, *, key: str) -> None:
    path = schema_path(report, schema_name)
    if not path.exists():
        report.gap(
            "schema_missing",
            f"schema {schema_name} is missing",
            file=rel_path(report, path),
            owner="A10",
            hint="restore Docs/Contracts/schemas",
        )
        return
    try:
        schema = schema_lite.load_schema(path)
    except schema_lite.SchemaError as exc:
        report.error("schema_load", str(exc), file=rel_path(report, path), owner="A10")
        return
    errors = schema_lite.validate(document, schema)
    if errors:
        report.schema_errors += len(errors)
        report.check(key, "fail", f"{len(errors)} schema error(s)", owner="A10")
        for message in errors[:200]:
            report.error(
                "schema",
                f"{schema_name}: {message}",
                file=rel,
                owner="A10",
                hint="fix the data shape; see Docs/Contracts/schemas",
            )
        if len(errors) > 200:
            report.error(
                "schema_truncated",
                f"{schema_name}: {len(errors) - 200} more schema errors not shown",
                file=rel,
                owner="A10",
            )
    else:
        report.info("schema_ok", f"{schema_name} schema passed", file=rel)


def make_context(root: Path, data_dir: Path, contracts_dir: Path) -> Context:
    return Context(root=root, data_dir=data_dir, contracts_dir=contracts_dir)


# ---------------------------------------------------------------------------
# Cards, fusions, decks, limitations
# ---------------------------------------------------------------------------


def validate_cards(ctx: Context, report: Report) -> None:
    path = ctx.data_dir / "cards.json"
    ctx.dataset_presence["cards"] = path.exists()
    if not path.exists():
        report.error(
            "cards_missing",
            "cards.json is missing",
            file=rel_path(report, path),
            owner="A01",
            hint="the baseline card database is required for every other check",
        )
        report.check("cards", "fail", "cards.json missing", owner="A01")
        return
    doc = load_json(path, report)
    if doc is None:
        report.check("cards", "fail", "cards.json unreadable", owner="A01")
        return
    ctx.card_doc = doc
    apply_schema(doc, "cards", rel_path(report, path), report, key="cards")

    items = collection(doc, "cards")
    if not items:
        report.error("cards_empty", "cards.json contains no cards", file=rel_path(report, path), owner="A01")
        report.check("cards", "fail", "no cards", owner="A01")
        return

    seen: dict[int, str] = {}
    errors = 0
    for index, card in enumerate(items):
        where = f"$.cards[{index}]"
        if not isinstance(card, dict):
            report.error("card_shape", "card entry is not an object", file=rel_path(report, path), path=where, owner="A01")
            errors += 1
            continue
        card_id = card.get("id")
        if not valid_card_id(card_id):
            report.error(
                "card_id",
                f"card id {card_id!r} is outside 1..1200",
                file=rel_path(report, path),
                path=where,
                owner="A01",
            )
            errors += 1
            continue
        if card_id in seen:
            report.error(
                "card_duplicate",
                f"duplicate card id {card_id} (first at {seen[card_id]})",
                file=rel_path(report, path),
                path=where,
                owner="A01",
            )
            errors += 1
            continue
        seen[card_id] = where
        ctx.cards[card_id] = card

        name = card.get("name")
        description = card.get("description")
        card_type = card.get("card_type")
        subtype = card.get("subtype")
        attribute = card.get("attribute")
        level = card.get("level")
        atk = card.get("atk")
        defence = card.get("def")

        if not isinstance(name, str) or not name.strip():
            report.error("card_name", f"card {card_id} has an empty name", file=rel_path(report, path), path=where, owner="A01")
            errors += 1
        if not isinstance(description, str) or not description.strip():
            report.error(
                "card_description",
                f"card {card_id} has an empty description",
                file=rel_path(report, path),
                path=where,
                owner="A01",
            )
            errors += 1
        if card_type not in CARD_TYPES:
            report.error(
                "card_type",
                f"card {card_id} has unknown card_type {card_type!r}",
                file=rel_path(report, path),
                path=where,
                owner="A01",
            )
            errors += 1
        if subtype not in SUBTYPES:
            report.error(
                "card_subtype",
                f"card {card_id} has unknown subtype {subtype!r}",
                file=rel_path(report, path),
                path=where,
                owner="A01",
            )
            errors += 1
        if attribute not in ATTRIBUTES:
            report.error(
                "card_attribute",
                f"card {card_id} has unknown attribute {attribute!r}",
                file=rel_path(report, path),
                path=where,
                owner="A01",
            )
            errors += 1
        if not isinstance(level, int) or isinstance(level, bool):
            report.error("card_level", f"card {card_id} has invalid level {level!r}", file=rel_path(report, path), path=where, owner="A01")
            errors += 1
        if not isinstance(atk, int) or isinstance(atk, bool) or atk < 0:
            report.error("card_atk", f"card {card_id} has invalid ATK {atk!r}", file=rel_path(report, path), path=where, owner="A01")
            errors += 1
        if not isinstance(defence, int) or isinstance(defence, bool) or defence < 0:
            report.error("card_def", f"card {card_id} has invalid DEF {defence!r}", file=rel_path(report, path), path=where, owner="A01")
            errors += 1

        if card_type in MONSTER_TYPES:
            if isinstance(level, int) and not (1 <= level <= 12):
                report.error(
                    "card_monster_level",
                    f"monster {card_id} has level {level} outside 1..12",
                    file=rel_path(report, path),
                    path=where,
                    owner="A01",
                )
                errors += 1
            if attribute == "NONE":
                report.error(
                    "card_monster_attribute",
                    f"monster {card_id} has attribute NONE",
                    file=rel_path(report, path),
                    path=where,
                    owner="A01",
                )
                errors += 1
            expected_subtypes = {
                "Normal Monster": {"Normal"},
                "Effect Monster": {"Effect"},
                "Fusion Monster": {"Fusion"},
                "Ritual Monster": {"Ritual"},
            }.get(card_type, set())
            if subtype not in expected_subtypes:
                report.warn(
                    "card_subtype_mismatch",
                    f"{card_id} is {card_type} with subtype {subtype!r}",
                    file=rel_path(report, path),
                    path=where,
                    owner="A01",
                )
        elif card_type in {"Spell", "Trap"}:
            if isinstance(level, int) and level != 0:
                report.warn(
                    "card_spell_level",
                    f"{card_type.lower()} {card_id} has level {level} (expected 0)",
                    file=rel_path(report, path),
                    path=where,
                    owner="A01",
                )
            if attribute != "NONE":
                report.warn(
                    "card_spell_attribute",
                    f"{card_type.lower()} {card_id} has attribute {attribute!r} (expected NONE)",
                    file=rel_path(report, path),
                    path=where,
                    owner="A01",
                )
            allowed = {"Normal", "Continuous", "Equip", "Quick-Play", "Field", "Ritual"} if card_type == "Spell" else {"Normal", "Continuous", "Counter"}
            if subtype not in allowed:
                report.error(
                    "card_spell_subtype",
                    f"{card_type} {card_id} has incompatible subtype {subtype!r}",
                    file=rel_path(report, path),
                    path=where,
                    owner="A01",
                )
                errors += 1

    missing = [card_id for card_id in range(1, 1201) if card_id not in seen]
    if missing:
        sample = ", ".join(str(card_id) for card_id in missing[:20])
        suffix = "" if len(missing) <= 20 else f" ... (+{len(missing) - 20} more)"
        report.error(
            "cards_incomplete",
            f"{len(missing)} card id(s) missing from 1..1200: {sample}{suffix}",
            file=rel_path(report, path),
            owner="A01",
            hint="cards must be a complete 1..1200 set; use --strict at a content gate",
        )
        errors += 1
    if len(items) != 1200:
        report.warn(
            "cards_count",
            f"cards.json has {len(items)} entries (expected 1200)",
            file=rel_path(report, path),
            owner="A01",
        )

    status = "fail" if errors else ("warn" if report.counts()["warning"] else "pass")
    report.check(
        "cards",
        status,
        f"{len(ctx.cards)} unique cards; ids 1..1200 {'complete' if not missing else 'incomplete'}",
        owner="A01",
    )


def validate_canon_reference(ctx: Context, report: Report) -> None:
    """Validate A01's immutable canon extracts under Content/Data/Canon.

    Canon is reference data, not the runtime source of truth. Incomplete canon
    records are GAPs; malformed complete records are errors.
    """
    canon = ctx.data_dir / "Canon"
    if not canon.is_dir():
        report.gap(
            "canon_missing",
            "Content/Data/Canon is missing",
            owner="A01",
            hint="A01 publishes immutable canon extracts and traceability here",
        )
        report.check("canon", "gap", "no canon directory", owner="A01")
        return

    def items(name: str, key: str) -> tuple[Any, list]:
        path = canon / name
        if not path.exists():
            return None, []
        document = load_json(path, report)
        return document, collection(document, key) if document is not None else []

    # ---- opponents and decks first: events/puzzles reference them ----
    opponents_doc, opponents = items("opponents.json", "opponents")
    opponent_ids: set[str] = set()
    op_errors = 0
    for index, opponent in enumerate(opponents):
        if not isinstance(opponent, dict):
            op_errors += 1
            continue
        opponent_id = opponent.get("id")
        if not isinstance(opponent_id, str) or not SLUG_RE.match(opponent_id):
            report.error("canon_opponent_id", f"invalid opponent id {opponent_id!r}", file="Content/Data/Canon/opponents.json", owner="A01")
            op_errors += 1
            continue
        if opponent_id in opponent_ids:
            report.error("canon_opponent_duplicate", f"duplicate opponent id {opponent_id}", file="Content/Data/Canon/opponents.json", owner="A01")
            op_errors += 1
        opponent_ids.add(opponent_id)
        for card_id in opponent.get("signature_card_ids", []) or []:
            if not valid_card_id(card_id) or (ctx.cards and card_id not in ctx.cards):
                report.error("canon_opponent_card", f"opponent {opponent_id} signature card {card_id!r} is invalid", file="Content/Data/Canon/opponents.json", owner="A01")
                op_errors += 1
    if opponents_doc is not None:
        report.check(
            "canon_opponents",
            "fail" if op_errors else ("gap" if len(opponent_ids) < 20 else "pass"),
            f"{len(opponent_ids)} opponents",
            owner="A01",
        )

    decks_doc, decks = items("decks.json", "decks")
    deck_ids: set[str] = set()
    incomplete_decks: list[str] = []
    deck_errors = 0
    for index, deck in enumerate(decks):
        if not isinstance(deck, dict):
            deck_errors += 1
            continue
        deck_id = deck.get("id")
        if not isinstance(deck_id, str) or not SLUG_RE.match(deck_id):
            report.error("canon_deck_id", f"invalid deck id {deck_id!r}", file="Content/Data/Canon/decks.json", owner="A01")
            deck_errors += 1
            continue
        if deck_id in deck_ids:
            report.error("canon_deck_duplicate", f"duplicate deck id {deck_id}", file="Content/Data/Canon/decks.json", owner="A01")
            deck_errors += 1
        deck_ids.add(deck_id)
        main = deck.get("main", [])
        extra = deck.get("extra", [])
        complete = deck.get("complete", True)
        if not complete:
            incomplete_decks.append(deck_id)
            continue
        if not isinstance(main, list) or not (40 <= len(main) <= 60):
            report.error("canon_deck_size", f"complete deck {deck_id} has invalid main size", file="Content/Data/Canon/decks.json", owner="A01")
            deck_errors += 1
        if not isinstance(extra, list) or len(extra) > 20:
            report.error("canon_deck_extra", f"complete deck {deck_id} has invalid extra size", file="Content/Data/Canon/decks.json", owner="A01")
            deck_errors += 1
        for card_id in (main if isinstance(main, list) else []) + (extra if isinstance(extra, list) else []):
            if not valid_card_id(card_id) or (ctx.cards and card_id not in ctx.cards):
                report.error("canon_deck_card", f"deck {deck_id} has invalid card {card_id!r}", file="Content/Data/Canon/decks.json", owner="A01")
                deck_errors += 1
    if decks_doc is not None:
        if incomplete_decks:
            report.gap(
                "canon_deck_incomplete",
                f"{len(incomplete_decks)}/{len(deck_ids)} canon decks are incomplete: {', '.join(incomplete_decks[:10])}{' ...' if len(incomplete_decks) > 10 else ''}",
                file="Content/Data/Canon/decks.json",
                owner="A01",
                hint="canon deck lists are unknown in the public guides; A01 must either prove or mark them fallback",
            )
        report.check(
            "canon_decks",
            "fail" if deck_errors else ("gap" if incomplete_decks else "pass"),
            f"{len(deck_ids)} decks; {len(deck_ids) - len(incomplete_decks)} complete",
            owner="A01",
        )

    # ---- packs ----
    packs_doc, packs = items("packs.json", "packs")
    pack_ids: set[str] = set()
    pack_union: set[int] = set()
    pack_errors = 0
    empty_pools: list[str] = []
    for index, pack in enumerate(packs):
        if not isinstance(pack, dict):
            pack_errors += 1
            continue
        pack_id = pack.get("id")
        if not isinstance(pack_id, str) or not SLUG_RE.match(pack_id):
            report.error("canon_pack_id", f"invalid pack id {pack_id!r}", file="Content/Data/Canon/packs.json", owner="A01")
            pack_errors += 1
            continue
        if pack_id in pack_ids:
            report.error("canon_pack_duplicate", f"duplicate pack id {pack_id}", file="Content/Data/Canon/packs.json", owner="A01")
            pack_errors += 1
        pack_ids.add(pack_id)
        price = pack.get("price_dp")
        if not isinstance(price, int) or isinstance(price, bool) or price < 0:
            report.error("canon_pack_price", f"pack {pack_id} has invalid price_dp {price!r}", file="Content/Data/Canon/packs.json", owner="A01")
            pack_errors += 1
        size = pack.get("cards_per_pack")
        if not isinstance(size, int) or isinstance(size, bool) or not (1 <= size <= 10):
            report.error("canon_pack_size", f"pack {pack_id} has invalid cards_per_pack {size!r}", file="Content/Data/Canon/packs.json", owner="A01")
            pack_errors += 1
        pool = pack.get("pool", [])
        if not isinstance(pool, list):
            pack_errors += 1
            continue
        if not pool:
            empty_pools.append(pack_id)
        for entry in pool:
            card_id = entry.get("card_id") if isinstance(entry, dict) else None
            if not valid_card_id(card_id) or (ctx.cards and card_id not in ctx.cards):
                report.error("canon_pack_card", f"pack {pack_id} has invalid pool card {card_id!r}", file="Content/Data/Canon/packs.json", owner="A01")
                pack_errors += 1
            else:
                pack_union.add(card_id)
    if packs_doc is not None:
        missing_cards = 1200 - len(pack_union)
        if missing_cards:
            report.gap(
                "canon_pack_coverage",
                f"{missing_cards} card(s) are not in the canon pack pools",
                file="Content/Data/Canon/packs.json",
                owner="A01",
            )
        if empty_pools:
            report.gap(
                "canon_pack_empty",
                f"pack(s) with no pool: {', '.join(empty_pools)}",
                file="Content/Data/Canon/packs.json",
                owner="A01",
            )
        report.check(
            "canon_packs",
            "fail" if pack_errors else ("gap" if empty_pools or missing_cards else "pass"),
            f"{len(pack_ids)} packs; pool union {len(pack_union)}",
            owner="A01",
        )

    # ---- events ----
    events_doc, events = items("events.json", "events")
    event_ids: set[str] = set()
    event_errors = 0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            event_errors += 1
            continue
        event_id = event.get("id")
        if not isinstance(event_id, str) or not EVENT_RE.match(event_id):
            report.error("canon_event_id", f"invalid event id {event_id!r}", file="Content/Data/Canon/events.json", owner="A01")
            event_errors += 1
            continue
        if event_id in event_ids:
            report.error("canon_event_duplicate", f"duplicate event id {event_id}", file="Content/Data/Canon/events.json", owner="A01")
            event_errors += 1
        event_ids.add(event_id)
        when = event.get("when")
        if isinstance(when, dict) and isinstance(when.get("date"), dict):
            date = when["date"]
            month = date.get("month")
            day = date.get("day")
            if not isinstance(month, int) or not (1 <= month <= 12) or not isinstance(day, int) or not (1 <= day <= 31):
                report.error("canon_event_date", f"event {event_id} has invalid date {date!r}", file="Content/Data/Canon/events.json", owner="A01")
                event_errors += 1
        requirements = event.get("requirements", [])
        if not isinstance(requirements, list) or not requirements:
            report.error("canon_event_requirements", f"event {event_id} has no requirements", file="Content/Data/Canon/events.json", owner="A01")
            event_errors += 1
        for reward in event.get("rewards", []) or []:
            if not isinstance(reward, dict):
                continue
            for card in reward.get("cards", []) or []:
                card_id = card.get("card_id") if isinstance(card, dict) else None
                if card_id is not None and (not valid_card_id(card_id) or (ctx.cards and card_id not in ctx.cards)):
                    report.error("canon_event_reward_card", f"event {event_id} reward has invalid card {card_id!r}", file="Content/Data/Canon/events.json", owner="A01")
                    event_errors += 1
        for duel in event.get("duels", []) or []:
            if not isinstance(duel, dict):
                continue
            opponent = duel.get("opponent")
            if opponent and opponent not in opponent_ids:
                report.warn("canon_event_duel_ref", f"event {event_id} duel references opponent {opponent!r} not in Canon/opponents.json", file="Content/Data/Canon/events.json", owner="A01")
            deck_id = duel.get("deck")
            if deck_id and deck_ids and deck_id not in deck_ids:
                report.gap("canon_event_deck_ref", f"event {event_id} duel references canon deck {deck_id!r} not in Canon/decks.json", file="Content/Data/Canon/events.json", owner="A01")
    if events_doc is not None:
        expected = {f"E{index:02d}" for index in range(1, 34)}
        missing = sorted(expected - event_ids)
        if missing:
            report.gap(
                "canon_event_coverage",
                f"missing numbered events: {', '.join(missing)}",
                file="Content/Data/Canon/events.json",
                owner="A01",
            )
        report.check(
            "canon_events",
            "fail" if event_errors else ("gap" if missing else "pass"),
            f"{len(event_ids)} events; {len(expected - set(event_ids))} numbered missing",
            owner="A01",
        )

    # ---- puzzles ----
    puzzles_doc, puzzles = items("puzzles.json", "puzzles")
    puzzle_ids: set[str] = set()
    puzzle_levels: collections.Counter[int] = collections.Counter()
    puzzle_errors = 0
    no_setup: list[str] = []
    no_time: list[str] = []
    for index, puzzle in enumerate(puzzles):
        if not isinstance(puzzle, dict):
            puzzle_errors += 1
            continue
        puzzle_id = puzzle.get("id")
        if not isinstance(puzzle_id, str) or not PUZZLE_RE.match(puzzle_id):
            report.error("canon_puzzle_id", f"invalid puzzle id {puzzle_id!r}", file="Content/Data/Canon/puzzles.json", owner="A01")
            puzzle_errors += 1
            continue
        if puzzle_id in puzzle_ids:
            report.error("canon_puzzle_duplicate", f"duplicate puzzle id {puzzle_id}", file="Content/Data/Canon/puzzles.json", owner="A01")
            puzzle_errors += 1
        puzzle_ids.add(puzzle_id)
        level = puzzle.get("level")
        if isinstance(level, int) and 1 <= level <= 5:
            puzzle_levels[level] += 1
        else:
            report.error("canon_puzzle_level", f"puzzle {puzzle_id} has invalid level {level!r}", file="Content/Data/Canon/puzzles.json", owner="A01")
            puzzle_errors += 1
        if not puzzle.get("setup"):
            no_setup.append(puzzle_id)
        if puzzle.get("time_limit_seconds") is None:
            no_time.append(puzzle_id)
        solution_ids = puzzle.get("solution_card_ids", [])
        if not isinstance(solution_ids, list) or not solution_ids:
            report.error("canon_puzzle_solution", f"puzzle {puzzle_id} has no solution card ids", file="Content/Data/Canon/puzzles.json", owner="A01")
            puzzle_errors += 1
        else:
            for card_id in solution_ids:
                if not valid_card_id(card_id) or (ctx.cards and card_id not in ctx.cards):
                    report.error("canon_puzzle_card", f"puzzle {puzzle_id} solution references invalid card {card_id!r}", file="Content/Data/Canon/puzzles.json", owner="A01")
                    puzzle_errors += 1
    if puzzles_doc is not None:
        if len(puzzle_ids) != 100 or any(puzzle_levels.get(level, 0) != 20 for level in range(1, 6)):
            report.gap(
                "canon_puzzle_coverage",
                f"{len(puzzle_ids)} puzzles; levels {dict(sorted(puzzle_levels.items()))}",
                file="Content/Data/Canon/puzzles.json",
                owner="A01",
            )
        if no_setup:
            report.gap(
                "canon_puzzle_setup",
                f"{len(no_setup)}/100 canon puzzles have no decoded setup; runtime puzzles must supply one",
                file="Content/Data/Canon/puzzles.json",
                owner="A01",
                hint="ROM puzzle table not decoded; A07 authors runtime setups",
            )
        if no_time:
            report.gap(
                "canon_puzzle_timer",
                f"{len(no_time)}/100 canon puzzles have no decoded time limit",
                file="Content/Data/Canon/puzzles.json",
                owner="A01",
            )
        report.check(
            "canon_puzzles",
            "fail" if puzzle_errors else ("gap" if no_setup or no_time or len(puzzle_ids) != 100 else "pass"),
            f"{len(puzzle_ids)} puzzles; levels {dict(sorted(puzzle_levels.items()))}",
            owner="A01",
        )

    # ---- exams, titles, calendar, banlist ----
    exams_path = canon / "exams.json"
    exam_errors = 0
    if exams_path.exists():
        exams = load_json(exams_path, report)
        if not isinstance(exams, dict):
            report.error("canon_exams_shape", "Canon/exams.json must be an object", file="Content/Data/Canon/exams.json", owner="A01")
            exam_errors += 1
        else:
            cycle = exams.get("cycle", {})
            written = exams.get("written", {})
            practical = exams.get("practical", {})
            scoring = exams.get("scoring", {})
            if not isinstance(cycle, dict) or cycle.get("exams_per_year") != 12:
                report.error("canon_exams_cycle", "canon exams must declare 12 exams per year", file="Content/Data/Canon/exams.json", owner="A01")
                exam_errors += 1
            if not isinstance(written, dict) or written.get("questions_per_exam") != 10:
                report.error("canon_exams_written", "canon written exam must declare 10 questions", file="Content/Data/Canon/exams.json", owner="A01")
                exam_errors += 1
            if not isinstance(practical, dict) or len(practical.get("objectives", [])) != 7:
                report.error("canon_exams_practical", "canon practical exam must declare 7 objectives", file="Content/Data/Canon/exams.json", owner="A01")
                exam_errors += 1
            if not isinstance(scoring, dict) or scoring.get("max_score") != 500:
                report.error("canon_exams_scoring", "canon exam scoring must be 500 points", file="Content/Data/Canon/exams.json", owner="A01")
                exam_errors += 1
            if isinstance(cycle, dict) and cycle.get("exam_week_rule", "").startswith("unresolved"):
                report.gap("canon_exam_week", "canon exam week rule is unresolved", file="Content/Data/Canon/exams.json", owner="A01")
        report.check("canon_exams", "fail" if exam_errors else "pass", "12-cycle exam definition", owner="A01")
    else:
        report.gap("canon_exams_missing", "Canon/exams.json is missing", owner="A01")
        report.check("canon_exams", "gap", "no canon exams", owner="A01")

    titles_path = canon / "titles.json"
    if titles_path.exists():
        titles = load_json(titles_path, report)
        title_items = titles.get("titles", []) if isinstance(titles, dict) else []
        title_errors = 0
        seen_titles = set()
        for title in title_items:
            if not isinstance(title, dict) or not isinstance(title.get("name"), str):
                title_errors += 1
                continue
            if title["name"] in seen_titles:
                report.error("canon_title_duplicate", f"duplicate title {title['name']!r}", file="Content/Data/Canon/titles.json", owner="A01")
                title_errors += 1
            seen_titles.add(title["name"])
        report.check("canon_titles", "fail" if title_errors else ("gap" if len(seen_titles) < 12 else "pass"), f"{len(seen_titles)} titles", owner="A01")

    calendar_path = canon / "calendar.json"
    if calendar_path.exists():
        calendar = load_json(calendar_path, report)
        school_year = calendar.get("school_year", {}) if isinstance(calendar, dict) else {}
        periods = calendar.get("periods", []) if isinstance(calendar, dict) else []
        cal_errors = 0
        if not isinstance(school_year, dict) or not school_year:
            report.error("canon_calendar", "canon calendar has no school_year", file="Content/Data/Canon/calendar.json", owner="A01")
            cal_errors += 1
        if not isinstance(periods, list) or len(periods) < 3:
            report.error("canon_calendar_periods", "canon calendar must declare AM/PM/Night", file="Content/Data/Canon/calendar.json", owner="A01")
            cal_errors += 1
        report.check("canon_calendar", "fail" if cal_errors else "pass", f"12-month calendar; {len(periods)} periods", owner="A01")

    banned_path = canon / "banned_list.json"
    if banned_path.exists():
        banned = load_json(banned_path, report)
        cards = banned.get("cards", []) if isinstance(banned, dict) else []
        ban_errors = 0
        for entry in cards:
            card_id = entry.get("card_id") if isinstance(entry, dict) else entry
            if not valid_card_id(card_id):
                report.error("canon_banlist_card", f"invalid banlist card {entry!r}", file="Content/Data/Canon/banned_list.json", owner="A01")
                ban_errors += 1
        report.check("canon_banlist", "fail" if ban_errors else "pass", f"{len(cards)} listed cards", owner="A01")


def validate_fusions(ctx: Context, report: Report) -> None:
    path = ctx.data_dir / "fusions.json"
    ctx.dataset_presence["fusions"] = path.exists()
    if not path.exists():
        report.gap(
            "fusions_missing",
            "fusions.json is missing",
            file=rel_path(report, path),
            owner="A05",
            hint="publish the full fusion recipe table (76 fusion monsters)",
        )
        report.check("fusions", "gap", "no fusion data", owner="A05")
        return
    doc = load_json(path, report)
    if doc is None:
        report.check("fusions", "fail", "fusions.json unreadable", owner="A05")
        return
    apply_schema(doc, "fusions", rel_path(report, path), report, key="fusions")
    items = collection(doc, "fusions")
    ctx.fusions = [item for item in items if isinstance(item, dict)]
    errors = 0
    seen_recipe: dict[tuple[int, ...], str] = {}
    for index, recipe in enumerate(ctx.fusions):
        where = f"$.fusions[{index}]"
        result = recipe.get("result")
        materials = recipe.get("materials")
        fusion_types = recipe.get("fusionTypes")
        if not valid_card_id(result):
            report.error("fusion_result", f"recipe {index} has invalid result {result!r}", file=rel_path(report, path), path=where, owner="A05")
            errors += 1
        elif result in ctx.cards and ctx.cards[result].get("card_type") != "Fusion Monster":
            report.error(
                "fusion_result_type",
                f"recipe {index} result {result} is not a Fusion Monster",
                file=rel_path(report, path),
                path=where,
                owner="A05",
            )
            errors += 1
        if not isinstance(materials, list):
            report.error("fusion_materials", f"recipe {index} has no materials array", file=rel_path(report, path), path=where, owner="A05")
            errors += 1
            continue
        if not materials:
            if recipe.get("materialsType"):
                report.warn(
                    "fusion_generic_material",
                    f"recipe {result} uses a generic material type {recipe.get('materialsType')!r} with {recipe.get('anyCount', '?')} slots",
                    file=rel_path(report, path),
                    path=where,
                    owner="A05",
                    hint="ensure DAEffectRuntime supports type-count fusion recipes",
                )
            else:
                report.warn(
                    "fusion_unresolved",
                    f"recipe {result} has no concrete materials",
                    file=rel_path(report, path),
                    path=where,
                    owner="A05",
                )
            continue
        bad_materials = [m for m in materials if not valid_card_id(m) or (ctx.cards and m not in ctx.cards)]
        if bad_materials:
            report.error(
                "fusion_material_ref",
                f"recipe {index} references invalid card ids {bad_materials[:10]}",
                file=rel_path(report, path),
                path=where,
                owner="A05",
            )
            errors += 1
        duplicates = [m for m, count in collections.Counter(materials).items() if count > 1]
        if duplicates:
            report.warn(
                "fusion_duplicate_material",
                f"recipe {result} repeats material(s) {duplicates}; check generic-material handling",
                file=rel_path(report, path),
                path=where,
                owner="A05",
            )
        key = tuple(sorted(m for m in materials if isinstance(m, int)))
        if key in seen_recipe:
            report.warn(
                "fusion_duplicate_recipe",
                f"recipe {result} duplicates recipe {seen_recipe[key]} for materials {list(key)}",
                file=rel_path(report, path),
                path=where,
                owner="A05",
            )
        else:
            seen_recipe[key] = str(result)
        if not isinstance(fusion_types, list) or not fusion_types:
            report.error(
                "fusion_types",
                f"recipe {result} has no fusionTypes",
                file=rel_path(report, path),
                path=where,
                owner="A05",
            )
            errors += 1

    fusion_monsters = [cid for cid, card in ctx.cards.items() if card.get("card_type") == "Fusion Monster"]
    if len(ctx.fusions) < len(fusion_monsters):
        report.gap(
            "fusion_coverage",
            f"{len(ctx.fusions)}/{len(fusion_monsters)} fusion monsters have recipes",
            file=rel_path(report, path),
            owner="A05",
            hint="A05 must publish the full fusion table before content freeze",
        )
    report.check(
        "fusions",
        "fail" if errors else ("gap" if len(ctx.fusions) < len(fusion_monsters) else "pass"),
        f"{len(ctx.fusions)} recipes for {len(fusion_monsters)} fusion monsters",
        owner="A05",
    )


def validate_limitations(ctx: Context, report: Report) -> None:
    path = first_existing(
        [
            ctx.data_dir / "Canon" / "limitations.json",
            ctx.data_dir / "Rules" / "limitations.json",
            ctx.data_dir / "Rules" / "banned_limited.json",
        ]
    )
    ctx.dataset_presence["limitations"] = path is not None
    if path is None:
        report.gap(
            "limitations_missing",
            "no forbidden/limited list found",
            owner="A01",
            hint="expected Content/Data/Canon/limitations.json",
        )
        report.check("limitations", "gap", "banlist not published", owner="A01")
        return
    doc = load_json(path, report)
    if doc is None:
        report.check("limitations", "fail", "banlist unreadable", owner="A01")
        return
    if isinstance(doc, dict) and "version" in doc:
        apply_schema(doc, "limitations", rel_path(report, path), report, key="limitations")
    else:
        report.warn(
            "limitations_schema_drift",
            "banlist uses the pre-contract schema; canonical form is {version, forbidden, limited, semi_limited}",
            file=rel_path(report, path),
            owner="A01",
        )
    errors = 0
    buckets: dict[int, str] = {}
    aliases = {"forbidden": "banned"}
    for name in ("forbidden", "limited", "semi_limited"):
        values = doc.get(name, doc.get(aliases.get(name, name), [])) if isinstance(doc, dict) else []
        if not isinstance(values, list):
            report.error("limitations_shape", f"{name} must be an array", file=rel_path(report, path), owner="A01")
            errors += 1
            continue
        ctx.limitations[name] = set()
        for entry in values:
            card_id = entry.get("card_id") if isinstance(entry, dict) else entry
            if not valid_card_id(card_id):
                report.error(
                    "limitations_id",
                    f"{name} contains invalid card id {entry!r}",
                    file=rel_path(report, path),
                    owner="A01",
                )
                errors += 1
                continue
            if card_id in buckets:
                report.error(
                    "limitations_overlap",
                    f"card {card_id} is in both {buckets[card_id]} and {name}",
                    file=rel_path(report, path),
                    owner="A01",
                )
                errors += 1
            buckets[card_id] = name
            ctx.limitations[name].add(card_id)
    report.check(
        "limitations",
        "fail" if errors else "pass",
        f"forbidden={len(ctx.limitations['forbidden'])}, limited={len(ctx.limitations['limited'])}, semi={len(ctx.limitations['semi_limited'])}",
        owner="A01",
    )


def validate_decks(ctx: Context, report: Report) -> None:
    paths: list[Path] = []
    if (ctx.data_dir / "decks.json").exists():
        paths.append(ctx.data_dir / "decks.json")
    paths.extend(glob_json(ctx.data_dir / "Decks"))
    # A07 publishes opponent decks as one file per deck. They are still decks
    # under the contract, just with a different directory.
    paths.extend(glob_json(ctx.data_dir / "Opponents" / "decks"))
    if not paths:
        report.gap(
            "decks_missing",
            "no deck data found",
            owner="A06",
            hint="expected Content/Data/decks.json and/or Content/Data/Decks/*.json",
        )
        report.check("decks", "gap", "no decks", owner="A06")
        return

    errors = 0
    for path in paths:
        doc = load_json(path, report)
        if doc is None:
            errors += 1
            continue
        # Opponent deck files are a single deck object rather than an array.
        if isinstance(doc, dict) and isinstance(doc.get("id"), str) and (
            isinstance(doc.get("cards"), list) or isinstance(doc.get("main"), list)
        ):
            deck_items = [doc]
            apply_schema({"version": 1, "decks": deck_items}, "decks", rel_path(report, path), report, key="decks")
        else:
            deck_items = collection(doc, "decks")
            apply_schema(doc, "decks", rel_path(report, path), report, key="decks")
        for index, deck in enumerate(deck_items):
            if not isinstance(deck, dict):
                report.error("deck_shape", "deck entry is not an object", file=rel_path(report, path), path=f"$[{index}]", owner="A06")
                errors += 1
                continue
            deck_id = deck.get("id")
            if not isinstance(deck_id, str) or not SLUG_RE.match(deck_id):
                report.error("deck_id", f"invalid deck id {deck_id!r}", file=rel_path(report, path), path=f"$[{index}]", owner="A06")
                errors += 1
                continue
            if deck_id in ctx.decks:
                report.error(
                    "deck_duplicate",
                    f"duplicate deck id {deck_id} (also in {ctx.deck_sources.get(deck_id, '?')})",
                    file=rel_path(report, path),
                    owner="A06",
                )
                errors += 1
                continue
            ctx.decks[deck_id] = deck
            ctx.deck_sources[deck_id] = rel_path(report, path)

            main = deck.get("cards", deck.get("main", []))
            extra = deck.get("extra", [])
            side = deck.get("side", [])
            for label, values in (("main", main), ("extra", extra), ("side", side)):
                if not isinstance(values, list):
                    report.error(
                        "deck_list",
                        f"deck {deck_id} field {label} is not an array",
                        file=rel_path(report, path),
                        owner="A06",
                    )
                    errors += 1
                    continue
                for card_id in values:
                    if not valid_card_id(card_id):
                        report.error(
                            "deck_card_id",
                            f"deck {deck_id} has invalid card id {card_id!r} in {label}",
                            file=rel_path(report, path),
                            owner="A06",
                        )
                        errors += 1
                    elif ctx.cards and card_id not in ctx.cards:
                        report.error(
                            "deck_card_ref",
                            f"deck {deck_id} references missing card {card_id}",
                            file=rel_path(report, path),
                            owner="A06",
                        )
                        errors += 1
                    else:
                        ctx.deck_cards.add(card_id)

            main_ids = [c for c in main if valid_card_id(c)] if isinstance(main, list) else []
            if not (40 <= len(main_ids) <= 60):
                report.error(
                    "deck_main_size",
                    f"deck {deck_id} has {len(main_ids)} main-deck cards (must be 40..60)",
                    file=rel_path(report, path),
                    owner="A06",
                )
                errors += 1
            if isinstance(extra, list) and len(extra) > 20:
                report.error(
                    "deck_extra_size",
                    f"deck {deck_id} has {len(extra)} extra-deck cards (max 20)",
                    file=rel_path(report, path),
                    owner="A06",
                )
                errors += 1
            if isinstance(side, list) and len(side) > 15:
                report.error(
                    "deck_side_size",
                    f"deck {deck_id} has {len(side)} side-deck cards (max 15)",
                    file=rel_path(report, path),
                    owner="A06",
                )
                errors += 1

            all_ids = []
            for values in (main, extra, side):
                if isinstance(values, list):
                    all_ids.extend(v for v in values if valid_card_id(v))
            copy_counts = collections.Counter(all_ids)
            over = {card: count for card, count in copy_counts.items() if count > 3}
            if over:
                report.error(
                    "deck_copy_limit",
                    f"deck {deck_id} exceeds 3 copies: {dict(sorted(over.items()))}",
                    file=rel_path(report, path),
                    owner="A06",
                )
                errors += 1

            for card_id in ctx.limitations["forbidden"]:
                if card_id in copy_counts:
                    report.error(
                        "deck_forbidden",
                        f"deck {deck_id} contains forbidden card {card_id}",
                        file=rel_path(report, path),
                        owner="A06",
                    )
                    errors += 1
            for card_id in ctx.limitations["limited"]:
                if copy_counts.get(card_id, 0) > 1:
                    report.error(
                        "deck_limited",
                        f"deck {deck_id} has {copy_counts[card_id]} copies of limited card {card_id}",
                        file=rel_path(report, path),
                        owner="A06",
                    )
                    errors += 1
            for card_id in ctx.limitations["semi_limited"]:
                if copy_counts.get(card_id, 0) > 2:
                    report.error(
                        "deck_semi_limited",
                        f"deck {deck_id} has {copy_counts[card_id]} copies of semi-limited card {card_id}",
                        file=rel_path(report, path),
                        owner="A06",
                    )
                    errors += 1

            if isinstance(main, list):
                for card_id in main:
                    card = ctx.cards.get(card_id) if valid_card_id(card_id) else None
                    if card and card.get("card_type") == "Fusion Monster":
                        report.warn(
                            "deck_fusion_in_main",
                            f"deck {deck_id} has fusion monster {card_id} in the main deck",
                            file=rel_path(report, path),
                            owner="A06",
                        )
            if isinstance(extra, list):
                for card_id in extra:
                    card = ctx.cards.get(card_id) if valid_card_id(card_id) else None
                    if card and card.get("card_type") not in {"Fusion Monster"}:
                        report.warn(
                            "deck_nonfusion_in_extra",
                            f"deck {deck_id} has non-fusion card {card_id} in the extra deck",
                            file=rel_path(report, path),
                            owner="A06",
                        )

    status = "fail" if errors else "pass"
    report.check("decks", status, f"{len(ctx.decks)} decks; {len(ctx.deck_cards)} distinct cards", owner="A06")


# ---------------------------------------------------------------------------
# Packs, opponents, puzzles, exams, anchors
# ---------------------------------------------------------------------------


def validate_packs(ctx: Context, report: Report) -> None:
    path = first_existing([ctx.data_dir / "Shop" / "packs.json"])
    if path is None:
        candidates = glob_json(ctx.data_dir / "Shop")
        path = candidates[0] if candidates else None
    ctx.dataset_presence["packs"] = path is not None
    if path is None:
        report.gap(
            "packs_missing",
            "no booster pack catalogue found",
            owner="A06",
            hint="expected Content/Data/Shop/packs.json with 48 packs",
        )
        report.check("packs", "gap", "no packs", owner="A06")
        return

    doc = load_json(path, report)
    if doc is None:
        report.check("packs", "fail", "packs unreadable", owner="A06")
        return
    apply_schema(doc, "packs", rel_path(report, path), report, key="packs")

    errors = 0
    for index, pack in enumerate(collection(doc, "packs")):
        where = f"$.packs[{index}]"
        if not isinstance(pack, dict):
            report.error("pack_shape", "pack entry is not an object", file=rel_path(report, path), path=where, owner="A06")
            errors += 1
            continue
        pack_id = pack.get("id")
        if not isinstance(pack_id, str) or not SLUG_RE.match(pack_id):
            report.error("pack_id", f"invalid pack id {pack_id!r}", file=rel_path(report, path), path=where, owner="A06")
            errors += 1
            continue
        if pack_id in ctx.packs:
            report.error("pack_duplicate", f"duplicate pack id {pack_id}", file=rel_path(report, path), path=where, owner="A06")
            errors += 1
            continue
        ctx.packs[pack_id] = pack

        price = pack.get("price")
        if not isinstance(price, int) or isinstance(price, bool) or price < 0:
            report.error("pack_price", f"pack {pack_id} has invalid price {price!r}", file=rel_path(report, path), path=where, owner="A06")
            errors += 1
        pack_size = pack.get("pack_size", pack.get("cards_per_pack"))
        if not isinstance(pack_size, int) or isinstance(pack_size, bool) or not (1 <= pack_size <= 10):
            report.error("pack_size", f"pack {pack_id} has invalid pack_size {pack_size!r}", file=rel_path(report, path), path=where, owner="A06")
            errors += 1
            pack_size = None

        # Canonical v1 uses pool: [{card,...}]. The A06 catalogue currently
        # uses pools: [{rarity, cards:[id,...]}]; accept both and normalize.
        raw_pool = pack.get("pool")
        if raw_pool is None and isinstance(pack.get("pools"), list):
            raw_pool = []
            for group in pack["pools"]:
                if not isinstance(group, dict):
                    continue
                rarity = group.get("rarity")
                for card_id in group.get("cards", []) or []:
                    raw_pool.append({"card": card_id, "rarity": rarity})
        pool = norm_pool_entries(raw_pool)
        if not pool:
            report.gap("pack_pool", f"pack {pack_id} has an empty pool", file=rel_path(report, path), path=where, owner="A06")
            errors += 0
        seen_pool: set[int] = set()
        for entry in pool:
            card_id = entry.get("card")
            if not valid_card_id(card_id):
                report.error("pack_card_id", f"pack {pack_id} has invalid pool card {card_id!r}", file=rel_path(report, path), path=where, owner="A06")
                errors += 1
                continue
            if card_id in seen_pool:
                report.error("pack_duplicate_card", f"pack {pack_id} lists card {card_id} more than once", file=rel_path(report, path), path=where, owner="A06")
                errors += 1
            seen_pool.add(card_id)
            ctx.pack_cards.add(card_id)
            if ctx.cards and card_id not in ctx.cards:
                report.error("pack_card_ref", f"pack {pack_id} references missing card {card_id}", file=rel_path(report, path), path=where, owner="A06")
                errors += 1
            weight = entry.get("weight")
            if weight is not None and (not isinstance(weight, (int, float)) or isinstance(weight, bool) or weight < 0):
                report.error("pack_weight", f"pack {pack_id} card {card_id} has invalid weight {weight!r}", file=rel_path(report, path), path=where, owner="A06")
                errors += 1

        slots = pack.get("slots")
        if isinstance(slots, list) and slots:
            slot_total = 0
            for slot in slots:
                if not isinstance(slot, dict):
                    errors += 1
                    report.error("pack_slot", f"pack {pack_id} has a non-object slot", file=rel_path(report, path), path=where, owner="A06")
                    continue
                count = slot.get("count")
                if count is None:
                    # A06's catalogue lists one slot per card, with no count.
                    slot_total += 1
                elif not isinstance(count, int) or isinstance(count, bool) or count < 1:
                    report.error("pack_slot_count", f"pack {pack_id} slot count must be >= 1", file=rel_path(report, path), path=where, owner="A06")
                    errors += 1
                else:
                    slot_total += count
            if pack_size is not None and slot_total != pack_size:
                report.error(
                    "pack_slot_total",
                    f"pack {pack_id} slots total {slot_total} but pack_size is {pack_size}",
                    file=rel_path(report, path),
                    path=where,
                    owner="A06",
                )
                errors += 1

        weights = pack.get("rarity_weights")
        if isinstance(weights, dict) and weights:
            total = sum(v for v in weights.values() if isinstance(v, (int, float)) and not isinstance(v, bool))
            if abs(total - 100.0) > 0.01:
                report.error(
                    "pack_weights",
                    f"pack {pack_id} rarity weights sum to {total}, expected 100",
                    file=rel_path(report, path),
                    path=where,
                    owner="A06",
                )
                errors += 1

        unlock = pack.get("unlock")
        if isinstance(unlock, dict):
            school_month = unlock.get("school_month", unlock.get("month"))
            if school_month is not None and (not isinstance(school_month, int) or not (1 <= school_month <= 12)):
                report.error("pack_unlock_month", f"pack {pack_id} has invalid unlock month {school_month!r}", file=rel_path(report, path), path=where, owner="A06")
                errors += 1
            event_id = unlock.get("event")
            if event_id is not None and ctx.events and event_id not in ctx.events:
                report.error("pack_unlock_event", f"pack {pack_id} unlocks on missing event {event_id}", file=rel_path(report, path), path=where, owner="A06")
                errors += 1
            flag = unlock.get("flag")
            if flag is not None and (not isinstance(flag, str) or not SLUG_RE.match(flag)):
                report.error("pack_unlock_flag", f"pack {pack_id} has invalid unlock flag {flag!r}", file=rel_path(report, path), path=where, owner="A06")
                errors += 1

    if len(ctx.packs) != 48:
        report.gap(
            "pack_count",
            f"{len(ctx.packs)}/48 packs published",
            file=rel_path(report, path),
            owner="A06",
            hint="the canon set is 48 packs; fill before content freeze",
        )
    report.check(
        "packs",
        "fail" if errors else ("gap" if len(ctx.packs) != 48 else "pass"),
        f"{len(ctx.packs)} packs; pool union {len(ctx.pack_cards)} cards",
        owner="A06",
    )


def validate_opponents(ctx: Context, report: Report) -> None:
    path = first_existing([ctx.data_dir / "Opponents" / "opponents.json"])
    paths = [path] if path else glob_json(ctx.data_dir / "Opponents")
    ctx.dataset_presence["opponents"] = bool(paths)
    if not paths:
        report.gap(
            "opponents_missing",
            "no duelist roster found",
            owner="A07",
            hint="expected Content/Data/Opponents/opponents.json",
        )
        report.check("opponents", "gap", "no roster", owner="A07")
        return

    errors = 0
    for file_path in paths:
        doc = load_json(file_path, report)
        if doc is None:
            errors += 1
            continue
        # A07's roster currently uses duelists[] and evolution_rules instead of
        # opponents[]/evolution. Accept both shapes; the fields are additive.
        if isinstance(doc, dict) and isinstance(doc.get("duelists"), list):
            opponent_items = doc["duelists"]
            report.warn(
                "opponent_schema_drift",
                "roster uses duelists[]; canonical v1 wrapper is opponents[]",
                file=rel_path(report, file_path),
                owner="A07",
            )
        else:
            opponent_items = collection(doc, "opponents")
            apply_schema(doc, "opponents", rel_path(report, file_path), report, key="opponents")
        for index, opponent in enumerate(opponent_items):
            where = f"$.opponents[{index}]"
            if not isinstance(opponent, dict):
                report.error("opponent_shape", "opponent entry is not an object", file=rel_path(report, file_path), path=where, owner="A07")
                errors += 1
                continue
            opponent_id = opponent.get("id")
            if not isinstance(opponent_id, str) or not SLUG_RE.match(opponent_id):
                report.error("opponent_id", f"invalid opponent id {opponent_id!r}", file=rel_path(report, file_path), path=where, owner="A07")
                errors += 1
                continue
            if opponent_id in ctx.opponents:
                report.error("opponent_duplicate", f"duplicate opponent id {opponent_id}", file=rel_path(report, file_path), path=where, owner="A07")
                errors += 1
                continue
            ctx.opponents[opponent_id] = opponent
            name = opponent.get("name")
            if not isinstance(name, str) or not name.strip():
                report.error("opponent_name", f"opponent {opponent_id} has an empty name", file=rel_path(report, file_path), path=where, owner="A07")
                errors += 1
            decks = opponent.get("decks", [])
            if not decks and opponent.get("default_deck"):
                decks = [opponent["default_deck"]]
            if not decks and opponent.get("deck"):
                decks = [opponent["deck"]]
            if not isinstance(decks, list) or not decks:
                report.error("opponent_deck", f"opponent {opponent_id} has no deck", file=rel_path(report, file_path), path=where, owner="A07")
                errors += 1
            else:
                for deck_id in decks:
                    if not isinstance(deck_id, str) or not SLUG_RE.match(deck_id):
                        report.error("opponent_deck_id", f"opponent {opponent_id} has invalid deck id {deck_id!r}", file=rel_path(report, file_path), path=where, owner="A07")
                        errors += 1
                    elif ctx.decks and deck_id not in ctx.decks:
                        report.error("opponent_deck_ref", f"opponent {opponent_id} references missing deck {deck_id}", file=rel_path(report, file_path), path=where, owner="A07")
                        errors += 1
            evolutions = opponent.get("evolution", opponent.get("evolution_rules", []))
            for evo_index, evolution in enumerate(evolutions if isinstance(evolutions, list) else []):
                if not isinstance(evolution, dict):
                    errors += 1
                    continue
                evo_deck = evolution.get("deck")
                if not isinstance(evo_deck, str) or not SLUG_RE.match(evo_deck):
                    report.error("opponent_evolution_deck", f"opponent {opponent_id} evolution {evo_index} has invalid deck {evo_deck!r}", file=rel_path(report, file_path), path=where, owner="A07")
                    errors += 1
                elif ctx.decks and evo_deck not in ctx.decks:
                    report.error("opponent_evolution_ref", f"opponent {opponent_id} evolution references missing deck {evo_deck}", file=rel_path(report, file_path), path=where, owner="A07")
                    errors += 1
            difficulty = opponent.get("difficulty")
            if difficulty is not None and (not isinstance(difficulty, int) or not (1 <= difficulty <= 5)):
                report.error("opponent_difficulty", f"opponent {opponent_id} has invalid difficulty {difficulty!r}", file=rel_path(report, file_path), path=where, owner="A07")
                errors += 1
            dorm = opponent.get("dorm")
            if dorm is not None and dorm not in DORMS:
                report.error("opponent_dorm", f"opponent {opponent_id} has invalid dorm {dorm!r}", file=rel_path(report, file_path), path=where, owner="A07")
                errors += 1
            ai_profile = opponent.get("ai_profile")
            if ai_profile is not None and (not isinstance(ai_profile, str) or not SLUG_RE.match(ai_profile)):
                report.error("opponent_ai", f"opponent {opponent_id} has invalid ai_profile {ai_profile!r}", file=rel_path(report, file_path), path=where, owner="A07")
                errors += 1
            schedule = opponent.get("schedule")
            if isinstance(schedule, list):
                for slot in schedule:
                    if not isinstance(slot, dict):
                        report.warn("opponent_schedule", f"opponent {opponent_id} has a non-object schedule slot", file=rel_path(report, file_path), path=where, owner="A07")
                        continue
                    for weekday in slot.get("weekdays", []) or []:
                        if weekday not in WEEKDAYS:
                            report.error("opponent_schedule_weekday", f"opponent {opponent_id} has invalid weekday {weekday!r}", file=rel_path(report, file_path), path=where, owner="A07")
                            errors += 1
                    for period in slot.get("periods", []) or []:
                        if period not in PERIODS:
                            report.error("opponent_schedule_period", f"opponent {opponent_id} has invalid period {period!r}", file=rel_path(report, file_path), path=where, owner="A07")
                            errors += 1
            elif schedule is not None and (not isinstance(schedule, str) or not SLUG_RE.match(schedule)):
                report.error("opponent_schedule", f"opponent {opponent_id} has invalid schedule {schedule!r}", file=rel_path(report, file_path), path=where, owner="A07")
                errors += 1

    if len(ctx.opponents) < 20:
        report.gap(
            "opponent_count",
            f"{len(ctx.opponents)}/20+ ranked duelists published",
            file=rel_path(report, path) if path else "",
            owner="A07",
            hint="event-only opponents are extra; the ranked roster is 20+",
        )
    report.check(
        "opponents",
        "fail" if errors else ("gap" if len(ctx.opponents) < 20 else "pass"),
        f"{len(ctx.opponents)} opponents",
        owner="A07",
    )


def _check_state_cards(ctx: Context, state: Any, *, label: str, path: str, file: str, report: Report, owner: str) -> int:
    if not isinstance(state, dict):
        report.error("puzzle_state", f"{label} is not an object", file=file, path=path, owner=owner)
        return 1
    errors = 0
    lp = state.get("lp")
    if lp is not None and (not isinstance(lp, int) or isinstance(lp, bool) or lp < 0):
        report.error("puzzle_lp", f"{label}.lp is invalid: {lp!r}", file=file, path=path, owner=owner)
        errors += 1
    for zone in ("hand", "field", "spells", "spell_traps", "graveyard", "banished", "deck", "extra"):
        values = state.get(zone, [])
        if values is None:
            continue
        if not isinstance(values, list):
            report.error("puzzle_zone", f"{label}.{zone} must be an array", file=file, path=path, owner=owner)
            errors += 1
            continue
        for index, entry in enumerate(values):
            card_id = (
                entry
                if isinstance(entry, int)
                else (entry.get("card", entry.get("card_id")) if isinstance(entry, dict) else None)
            )
            if not valid_card_id(card_id):
                report.error(
                    "puzzle_card_id",
                    f"{label}.{zone}[{index}] has invalid card id {card_id!r}",
                    file=file,
                    path=f"{path}.{zone}[{index}]",
                    owner=owner,
                )
                errors += 1
            elif ctx.cards and card_id not in ctx.cards:
                report.error(
                    "puzzle_card_ref",
                    f"{label}.{zone}[{index}] references missing card {card_id}",
                    file=file,
                    path=f"{path}.{zone}[{index}]",
                    owner=owner,
                )
                errors += 1
            else:
                ctx.puzzle_cards.add(card_id)  # type: ignore[attr-defined]
            count = entry.get("count", 1) if isinstance(entry, dict) else 1
            if not isinstance(count, int) or isinstance(count, bool) or count < 1:
                report.error(
                    "puzzle_count",
                    f"{label}.{zone}[{index}] has invalid count {count!r}",
                    file=file,
                    path=f"{path}.{zone}[{index}]",
                    owner=owner,
                )
                errors += 1
    return errors


def validate_puzzles(ctx: Context, report: Report) -> None:
    path = first_existing([ctx.data_dir / "Puzzles" / "puzzles.json"])
    paths = [path] if path else glob_json(ctx.data_dir / "Puzzles")
    ctx.dataset_presence["puzzles"] = bool(paths)
    if not paths:
        report.gap(
            "puzzles_missing",
            "no timed duel puzzles found",
            owner="A07",
            hint="expected Content/Data/Puzzles/puzzles.json with P001..P100",
        )
        report.check("puzzles", "gap", "no puzzles", owner="A07")
        return

    errors = 0
    legacy_puzzle_files: list[str] = []
    for file_path in paths:
        doc = load_json(file_path, report)
        if doc is None:
            errors += 1
            continue
        # A07 publishes one Pxxx.json per puzzle with an embedded opponent
        # state. Accept that shape and report the contract drift once.
        if isinstance(doc, dict) and isinstance(doc.get("id"), str) and isinstance(doc.get("player"), dict):
            puzzle_items = [doc]
            legacy_puzzle_files.append(rel_path(report, file_path))
        else:
            puzzle_items = collection(doc, "puzzles")
            apply_schema(doc, "puzzles", rel_path(report, file_path), report, key="puzzles")
        for index, puzzle in enumerate(puzzle_items):
            where = f"$.puzzles[{index}]"
            file_label = rel_path(report, file_path)
            if not isinstance(puzzle, dict):
                report.error("puzzle_shape", "puzzle entry is not an object", file=file_label, path=where, owner="A07")
                errors += 1
                continue
            puzzle_id = puzzle.get("id")
            if not isinstance(puzzle_id, str) or not PUZZLE_RE.match(puzzle_id):
                report.error("puzzle_id", f"invalid puzzle id {puzzle_id!r}", file=file_label, path=where, owner="A07")
                errors += 1
                continue
            if puzzle_id in ctx.puzzles:
                report.error("puzzle_duplicate", f"duplicate puzzle id {puzzle_id}", file=file_label, path=where, owner="A07")
                errors += 1
                continue
            ctx.puzzles[puzzle_id] = puzzle

            level = puzzle.get("level")
            if not isinstance(level, int) or isinstance(level, bool) or not (1 <= level <= 5):
                report.error("puzzle_level", f"puzzle {puzzle_id} has invalid level {level!r}", file=file_label, path=where, owner="A07")
                errors += 1
            opponent = puzzle.get("opponent")
            opponent_id = puzzle.get("opponent_id")
            opponent_state = puzzle.get("opponent_state")
            if isinstance(opponent, dict):
                # Pre-contract A07 shape: opponent is the opponent's state.
                opponent_state = opponent
            elif isinstance(opponent, str):
                opponent_id = opponent
            if opponent_id is not None:
                if not isinstance(opponent_id, str) or not SLUG_RE.match(opponent_id):
                    report.error("puzzle_opponent", f"puzzle {puzzle_id} has invalid opponent {opponent_id!r}", file=file_label, path=where, owner="A07")
                    errors += 1
                elif ctx.opponents and opponent_id not in ctx.opponents:
                    report.error("puzzle_opponent_ref", f"puzzle {puzzle_id} references unknown opponent {opponent_id}", file=file_label, path=where, owner="A07")
                    errors += 1
            objective = puzzle.get("objective")
            if objective not in {
                "win",
                "win_this_turn",
                "reduce_lp_to_zero",
                "deal_damage",
                "destroy_monster",
                "special_summon",
                "fusion_summon",
                "ritual_summon",
                "survive_turns",
            }:
                report.error("puzzle_objective", f"puzzle {puzzle_id} has invalid objective {objective!r}", file=file_label, path=where, owner="A07")
                errors += 1
            time_limit = puzzle.get("time_limit_seconds", puzzle.get("time_limit"))
            if not isinstance(time_limit, int) or isinstance(time_limit, bool) or time_limit <= 0:
                report.error("puzzle_time", f"puzzle {puzzle_id} has invalid time limit {time_limit!r}", file=file_label, path=where, owner="A07")
                errors += 1
            turn_limit = puzzle.get("turn_limit")
            if not isinstance(turn_limit, int) or isinstance(turn_limit, bool) or not (1 <= turn_limit <= 20):
                report.error("puzzle_turn", f"puzzle {puzzle_id} has invalid turn limit {turn_limit!r}", file=file_label, path=where, owner="A07")
                errors += 1
            errors += _check_state_cards(ctx, puzzle.get("player"), label=f"{puzzle_id}.player", path=f"{where}.player", file=file_label, report=report, owner="A07")
            errors += _check_state_cards(ctx, opponent_state, label=f"{puzzle_id}.opponent_state", path=f"{where}.opponent_state", file=file_label, report=report, owner="A07")

            solution = puzzle.get("solution")
            if not isinstance(solution, list) or not solution:
                report.error("puzzle_solution", f"puzzle {puzzle_id} has no solution", file=file_label, path=where, owner="A07")
                errors += 1
            else:
                for step_index, step in enumerate(solution):
                    if not isinstance(step, dict):
                        report.error("puzzle_step", f"puzzle {puzzle_id} solution step {step_index} is not an object", file=file_label, path=where, owner="A07")
                        errors += 1
                        continue
                    action = step.get("action")
                    if action not in PUZZLE_ACTIONS:
                        report.error(
                            "puzzle_action",
                            f"puzzle {puzzle_id} solution step {step_index} has unknown action {action!r}",
                            file=file_label,
                            path=f"{where}.solution[{step_index}]",
                            owner="A07",
                        )
                        errors += 1
                    for key in ("card", "attacker_card_id", "target_card_id"):
                        card_id = step.get(key)
                        if card_id is not None and not valid_card_id(card_id):
                            report.error(
                                "puzzle_step_card",
                                f"puzzle {puzzle_id} solution step {step_index} has invalid {key} {card_id!r}",
                                file=file_label,
                                path=f"{where}.solution[{step_index}]",
                                owner="A07",
                            )
                            errors += 1
                    target = step.get("target")
                    if target is not None and not isinstance(target, str) and not valid_card_id(target):
                        report.error(
                            "puzzle_step_target",
                            f"puzzle {puzzle_id} solution step {step_index} has invalid target {target!r}",
                            file=file_label,
                            path=f"{where}.solution[{step_index}]",
                            owner="A07",
                        )
                        errors += 1
            reward = puzzle.get("reward_dp")
            if reward is None and isinstance(puzzle.get("reward"), dict):
                reward = puzzle["reward"].get("dp")
            if reward is not None and (not isinstance(reward, int) or isinstance(reward, bool) or reward < 0):
                report.error("puzzle_reward", f"puzzle {puzzle_id} has invalid reward_dp {reward!r}", file=file_label, path=where, owner="A07")
                errors += 1

    if legacy_puzzle_files:
        report.warn(
            "puzzle_schema_drift",
            f"{len(legacy_puzzle_files)} puzzle file(s) use a single object with embedded opponent state; canonical v1 uses puzzles[]",
            file=legacy_puzzle_files[0],
            owner="A07",
        )

    expected = {f"P{index:03d}" for index in range(1, 101)}
    missing = sorted(expected - set(ctx.puzzles))
    extra = sorted(set(ctx.puzzles) - expected)
    if missing or extra:
        report.gap(
            "puzzle_coverage",
            f"{len(ctx.puzzles)}/100 puzzles; missing {len(missing)}, unexpected {len(extra)}",
            file=rel_path(report, path) if path else "",
            owner="A07",
            hint="canon is P001..P100, 20 per level",
        )
    level_counts = collections.Counter(int(p.get("level", 0)) for p in ctx.puzzles.values())
    off_levels = {level: count for level, count in level_counts.items() if count != 20 and level in range(1, 6)}
    if ctx.puzzles and off_levels:
        report.warn(
            "puzzle_level_distribution",
            f"puzzle level counts are not 20 each: {dict(sorted(level_counts.items()))}",
            file=rel_path(report, path) if path else "",
            owner="A07",
        )
    report.check(
        "puzzles",
        "fail" if errors else ("gap" if missing or extra else "pass"),
        f"{len(ctx.puzzles)} puzzles; levels {dict(sorted(level_counts.items()))}",
        owner="A07",
    )


def validate_exams(ctx: Context, report: Report) -> None:
    exam_path = ctx.data_dir / "Exams" / "exams.json"
    question_path = ctx.data_dir / "Exams" / "questions.json"
    ctx.dataset_presence["exams"] = exam_path.exists()
    if not exam_path.exists():
        report.gap(
            "exams_missing",
            "no exam definitions found",
            owner="A07",
            hint="expected Content/Data/Exams/exams.json and questions.json",
        )
        report.check("exams", "gap", "no exams", owner="A07")
        return

    doc = load_json(exam_path, report)
    if doc is None:
        report.check("exams", "fail", "exams unreadable", owner="A07")
        return
    legacy_exams = isinstance(doc, dict) and isinstance(doc.get("cycles"), list) and not isinstance(doc.get("exams"), list)
    if legacy_exams:
        exam_items = doc["cycles"]
        report.warn(
            "exam_schema_drift",
            "exams use cycles[] with top-level question_ids/timed_puzzle_id/practical_objective_id; canonical v1 uses exams[] with written/timed/practical objects",
            file=rel_path(report, exam_path),
            owner="A07",
        )
    else:
        exam_items = collection(doc, "exams")
        apply_schema(doc, "exams", rel_path(report, exam_path), report, key="exams")

    practical_opponent = "mimicry"
    practical_path = ctx.data_dir / "Exams" / "practicals.json"
    if practical_path.exists():
        practical_doc = load_json(practical_path, report)
        if isinstance(practical_doc, dict) and isinstance(practical_doc.get("opponent"), str):
            practical_opponent = practical_doc["opponent"]

    if question_path.exists():
        qdoc = load_json(question_path, report)
        if qdoc is not None:
            legacy_questions = isinstance(qdoc, dict) and isinstance(qdoc.get("questions"), list) and qdoc["questions"] and isinstance(qdoc["questions"][0], dict) and "options" in qdoc["questions"][0]
            if not legacy_questions:
                apply_schema(qdoc, "exam-questions", rel_path(report, question_path), report, key="exam_questions")
            else:
                report.warn(
                    "exam_question_schema_drift",
                    "questions use Qxxx/options/answer_index; canonical v1 uses Wxxx/answers/correct_index",
                    file=rel_path(report, question_path),
                    owner="A07",
                )
            for index, question in enumerate(collection(qdoc, "questions")):
                if not isinstance(question, dict):
                    report.error("exam_question_shape", "question is not an object", file=rel_path(report, question_path), path=f"$[{index}]", owner="A07")
                    continue
                qid = question.get("id")
                if not isinstance(qid, str) or not re.match(r"^[A-Z][0-9]{3}$", qid):
                    report.error("exam_question_id", f"invalid question id {qid!r}", file=rel_path(report, question_path), owner="A07")
                    continue
                if qid in ctx.questions:
                    report.error("exam_question_duplicate", f"duplicate question id {qid}", file=rel_path(report, question_path), owner="A07")
                    continue
                ctx.questions[qid] = question
                answers = question.get("answers", question.get("options"))
                correct = question.get("correct_index", question.get("answer_index"))
                if not isinstance(answers, list) or not (2 <= len(answers) <= 4):
                    report.error("exam_question_answers", f"question {qid} must have 2..4 answers", file=rel_path(report, question_path), owner="A07")
                if not isinstance(correct, int) or isinstance(correct, bool) or not isinstance(answers, list) or not (0 <= correct < len(answers)):
                    report.error("exam_question_correct", f"question {qid} has invalid correct index {correct!r}", file=rel_path(report, question_path), owner="A07")
    else:
        report.gap(
            "exam_questions_missing",
            "questions.json is missing",
            file=rel_path(report, question_path),
            owner="A07",
        )

    errors = 0
    for index, exam in enumerate(exam_items):
        where = f"$.exams[{index}]"
        file_label = rel_path(report, exam_path)
        if not isinstance(exam, dict):
            report.error("exam_shape", "exam entry is not an object", file=file_label, path=where, owner="A07")
            errors += 1
            continue
        if legacy_exams:
            scoring = exam.get("scoring", {}) if isinstance(exam.get("scoring"), dict) else {}
            sections = scoring.get("sections", {}) if isinstance(scoring.get("sections"), dict) else {}
            exam = {
                "id": exam.get("exam_id"),
                "month_index": exam.get("month_index"),
                "written": {
                    "question_ids": exam.get("question_ids", []),
                    "max_points": sections.get("written", 200),
                },
                "timed": {
                    "puzzle_ids": [exam.get("timed_puzzle_id")] if exam.get("timed_puzzle_id") else [],
                    "max_points": sections.get("timed", 100),
                },
                "practical": {
                    "opponent": practical_opponent,
                    "objectives": [exam.get("practical_objective_id")] if exam.get("practical_objective_id") else [],
                    "max_points": sections.get("practical", 200),
                },
                "scoring": {
                    "written_max": sections.get("written", 200),
                    "timed_max": sections.get("timed", 100),
                    "practical_max": sections.get("practical", 200),
                    "max": scoring.get("max_points", 500),
                    "pass_mark": scoring.get("pass_mark", 300),
                },
                "_legacy": True,
            }
        exam_id = exam.get("id")
        if not isinstance(exam_id, str) or not EXAM_RE.match(exam_id):
            report.error("exam_id", f"invalid exam id {exam_id!r}", file=file_label, path=where, owner="A07")
            errors += 1
            continue
        if exam_id in ctx.exams:
            report.error("exam_duplicate", f"duplicate exam id {exam_id}", file=file_label, path=where, owner="A07")
            errors += 1
            continue
        ctx.exams[exam_id] = exam
        month_index = exam.get("month_index")
        if not isinstance(month_index, int) or isinstance(month_index, bool) or not (1 <= month_index <= 12):
            report.error("exam_month", f"exam {exam_id} has invalid month_index {month_index!r}", file=file_label, path=where, owner="A07")
            errors += 1
        written = exam.get("written", {})
        if not isinstance(written, dict):
            report.error("exam_written", f"exam {exam_id} written is not an object", file=file_label, path=where, owner="A07")
            errors += 1
        else:
            qids = written.get("question_ids", [])
            if not isinstance(qids, list) or len(qids) != 10:
                report.error("exam_written_count", f"exam {exam_id} must list exactly 10 written questions", file=file_label, path=where, owner="A07")
                errors += 1
            else:
                for qid in qids:
                    if not isinstance(qid, str) or not re.match(r"^[A-Z][0-9]{3}$", qid):
                        report.error("exam_written_id", f"exam {exam_id} has invalid question id {qid!r}", file=file_label, path=where, owner="A07")
                        errors += 1
                    elif ctx.questions and qid not in ctx.questions:
                        report.error("exam_written_ref", f"exam {exam_id} references missing question {qid}", file=file_label, path=where, owner="A07")
                        errors += 1
        timed = exam.get("timed", {})
        if not isinstance(timed, dict):
            report.error("exam_timed", f"exam {exam_id} timed is not an object", file=file_label, path=where, owner="A07")
            errors += 1
        else:
            pids = timed.get("puzzle_ids", [])
            if not isinstance(pids, list) or not pids:
                report.error("exam_timed_puzzles", f"exam {exam_id} has no timed puzzles", file=file_label, path=where, owner="A07")
                errors += 1
            else:
                for pid in pids:
                    if not isinstance(pid, str) or not PUZZLE_RE.match(pid):
                        report.error("exam_timed_id", f"exam {exam_id} has invalid puzzle id {pid!r}", file=file_label, path=where, owner="A07")
                        errors += 1
                    elif ctx.puzzles and pid not in ctx.puzzles:
                        report.error("exam_timed_ref", f"exam {exam_id} references missing puzzle {pid}", file=file_label, path=where, owner="A07")
                        errors += 1
            time_limit = timed.get("time_limit_seconds")
            if time_limit is not None and (not isinstance(time_limit, int) or time_limit <= 0):
                report.error("exam_timed_time", f"exam {exam_id} has invalid timed time limit {time_limit!r}", file=file_label, path=where, owner="A07")
                errors += 1
        practical = exam.get("practical", {})
        if not isinstance(practical, dict):
            report.error("exam_practical", f"exam {exam_id} practical is not an object", file=file_label, path=where, owner="A07")
            errors += 1
        else:
            objectives = practical.get("objectives", [])
            if not isinstance(objectives, list) or not objectives:
                report.error("exam_objectives", f"exam {exam_id} has no practical objectives", file=file_label, path=where, owner="A07")
                errors += 1
            else:
                unknown = [obj for obj in objectives if obj not in PRACTICAL_OBJECTIVES]
                if unknown:
                    report.error("exam_objective_ref", f"exam {exam_id} has unknown objectives {unknown}", file=file_label, path=where, owner="A07")
                    errors += 1
                if len(set(objectives)) != len(objectives):
                    report.error("exam_objective_duplicate", f"exam {exam_id} repeats a practical objective", file=file_label, path=where, owner="A07")
                    errors += 1
            opponent = practical.get("opponent")
            if not isinstance(opponent, str) or not SLUG_RE.match(opponent):
                report.error("exam_practical_opponent", f"exam {exam_id} has invalid practical opponent {opponent!r}", file=file_label, path=where, owner="A07")
                errors += 1
            elif ctx.opponents and opponent not in ctx.opponents:
                report.error("exam_practical_ref", f"exam {exam_id} references unknown opponent {opponent}", file=file_label, path=where, owner="A07")
                errors += 1

        scoring = exam.get("scoring", {})
        if not isinstance(scoring, dict):
            report.error("exam_scoring", f"exam {exam_id} scoring is not an object", file=file_label, path=where, owner="A07")
            errors += 1
        else:
            parts = [scoring.get("written_max"), scoring.get("timed_max"), scoring.get("practical_max")]
            if not all(isinstance(part, int) and not isinstance(part, bool) and part >= 0 for part in parts):
                report.error("exam_scoring_parts", f"exam {exam_id} has invalid scoring parts {parts}", file=file_label, path=where, owner="A07")
                errors += 1
            else:
                total = sum(parts)
                max_score = scoring.get("max")
                if max_score != total:
                    report.error(
                        "exam_scoring_total",
                        f"exam {exam_id} scoring max {max_score!r} != written+timed+practical ({total})",
                        file=file_label,
                        path=where,
                        owner="A07",
                    )
                    errors += 1
                if max_score != 500:
                    report.warn(
                        "exam_scoring_500",
                        f"exam {exam_id} max score is {max_score!r}; canon is 500",
                        file=file_label,
                        path=where,
                        owner="A07",
                    )
            pass_mark = scoring.get("pass_mark")
            if not isinstance(pass_mark, int) or isinstance(pass_mark, bool) or pass_mark < 0:
                report.error("exam_pass_mark", f"exam {exam_id} has invalid pass_mark {pass_mark!r}", file=file_label, path=where, owner="A07")
                errors += 1
            elif isinstance(scoring.get("max"), int) and pass_mark > scoring["max"]:
                report.error("exam_pass_mark_range", f"exam {exam_id} pass_mark {pass_mark} exceeds max {scoring['max']}", file=file_label, path=where, owner="A07")
                errors += 1

    expected_ids = {f"EXAM_{index:02d}" for index in range(1, 13)}
    missing = sorted(expected_ids - set(ctx.exams))
    if missing:
        report.gap(
            "exam_count",
            f"{len(ctx.exams)}/12 exams; missing {', '.join(missing)}",
            file=rel_path(report, exam_path),
            owner="A07",
        )
    report.check(
        "exams",
        "fail" if errors else ("gap" if missing else "pass"),
        f"{len(ctx.exams)} exams; {len(ctx.questions)} questions",
        owner="A07",
    )


def validate_anchors(ctx: Context, report: Report) -> None:
    path = ctx.data_dir / "World" / "anchors.json"
    ctx.dataset_presence["anchors"] = path.exists()
    if not path.exists():
        report.gap(
            "anchors_missing",
            "no world locations/anchors found",
            owner="A08",
            hint="expected Content/Data/World/anchors.json with locations, anchors, portals and spawns",
        )
        report.check("anchors", "gap", "no anchors", owner="A08")
        return

    doc = load_json(path, report)
    if doc is None:
        report.check("anchors", "fail", "anchors unreadable", owner="A08")
        return
    legacy_anchors = isinstance(doc, dict) and isinstance(doc.get("anchors"), list) and not isinstance(doc.get("locations"), list)
    if legacy_anchors:
        report.warn(
            "anchor_schema_drift",
            "anchors use position_ue/location_id and implicit locations; canonical v1 uses locations[], position{x,y,z}",
            file=rel_path(report, path),
            owner="A08",
        )
    else:
        apply_schema(doc, "anchors", rel_path(report, path), report, key="anchors")

    errors = 0
    locations = doc.get("locations", []) if isinstance(doc, dict) else []
    if not isinstance(locations, list):
        report.error("locations_shape", "locations must be an array", file=rel_path(report, path), owner="A08")
        errors += 1
        locations = []
    for index, location in enumerate(locations):
        if not isinstance(location, dict):
            report.error("location_shape", "location is not an object", file=rel_path(report, path), path=f"$.locations[{index}]", owner="A08")
            errors += 1
            continue
        loc_id = location.get("id")
        if not isinstance(loc_id, str) or not SLUG_RE.match(loc_id):
            report.error("location_id", f"invalid location id {loc_id!r}", file=rel_path(report, path), path=f"$.locations[{index}]", owner="A08")
            errors += 1
            continue
        if loc_id in ctx.locations:
            report.error("location_duplicate", f"duplicate location id {loc_id}", file=rel_path(report, path), owner="A08")
            errors += 1
            continue
        ctx.locations[loc_id] = location

    anchors = doc.get("anchors", []) if isinstance(doc, dict) else []
    if not isinstance(anchors, list):
        report.error("anchors_shape", "anchors must be an array", file=rel_path(report, path), owner="A08")
        errors += 1
        anchors = []
    if legacy_anchors:
        for anchor in anchors:
            if not isinstance(anchor, dict):
                continue
            for key in ("location_id", "zone_id"):
                loc_id = anchor.get(key)
                if isinstance(loc_id, str) and SLUG_RE.match(loc_id) and loc_id not in ctx.locations:
                    ctx.locations[loc_id] = {"id": loc_id, "name": loc_id.replace("_", " ").title(), "source": "implicit-anchor"}

    # A08 also publishes the full location map and split portal/spawn/interior
    # files. Merge them so the anchors check covers the actual world contract.
    location_map_path = ctx.data_dir / "World" / "location_map.json"
    if location_map_path.exists():
        location_map = load_json(location_map_path, report)
        for location in collection(location_map, "locations"):
            if not isinstance(location, dict):
                continue
            loc_id = location.get("id")
            if isinstance(loc_id, str) and SLUG_RE.match(loc_id) and loc_id not in ctx.locations:
                ctx.locations[loc_id] = {
                    "id": loc_id,
                    "name": location.get("gx_name", loc_id),
                    "source": "location-map",
                }
    for index, anchor in enumerate(anchors):
        where = f"$.anchors[{index}]"
        if not isinstance(anchor, dict):
            report.error("anchor_shape", "anchor is not an object", file=rel_path(report, path), path=where, owner="A08")
            errors += 1
            continue
        anchor_id = anchor.get("id")
        if not isinstance(anchor_id, str) or not ANCHOR_RE.match(anchor_id):
            report.error("anchor_id", f"invalid anchor id {anchor_id!r}", file=rel_path(report, path), path=where, owner="A08")
            errors += 1
            continue
        if anchor_id in ctx.anchors:
            report.error("anchor_duplicate", f"duplicate anchor id {anchor_id}", file=rel_path(report, path), path=where, owner="A08")
            errors += 1
            continue
        ctx.anchors[anchor_id] = anchor
        loc_id = anchor.get("location", anchor.get("location_id", anchor.get("zone_id")))
        if not isinstance(loc_id, str) or loc_id not in ctx.locations:
            report.error("anchor_location", f"anchor {anchor_id} references unknown location {loc_id!r}", file=rel_path(report, path), path=where, owner="A08")
            errors += 1
        position = anchor.get("position")
        if position is None and isinstance(anchor.get("position_ue"), list) and len(anchor["position_ue"]) == 3:
            position = dict(zip(("x", "y", "z"), anchor["position_ue"]))
        if not isinstance(position, dict) or not all(isinstance(position.get(axis), (int, float)) and not isinstance(position.get(axis), bool) for axis in ("x", "y", "z")):
            report.error("anchor_position", f"anchor {anchor_id} has invalid position", file=rel_path(report, path), path=where, owner="A08")
            errors += 1

    portals = doc.get("portals", []) if isinstance(doc, dict) else []
    portals_path = ctx.data_dir / "World" / "portals.json"
    if (not isinstance(portals, list) or not portals) and portals_path.exists():
        portal_doc = load_json(portals_path, report)
        portals = collection(portal_doc, "portals")
    if isinstance(portals, list):
        for index, portal in enumerate(portals):
            where = f"$.portals[{index}]"
            file_label = rel_path(report, portals_path) if portals_path.exists() and not (isinstance(doc, dict) and doc.get("portals")) else rel_path(report, path)
            if not isinstance(portal, dict):
                errors += 1
                continue
            portal_id = portal.get("id")
            if not isinstance(portal_id, str) or not SLUG_RE.match(portal_id):
                report.error("portal_id", f"invalid portal id {portal_id!r}", file=file_label, path=where, owner="A08")
                errors += 1
            # Canonical path uses from/to anchors. A08's split file uses
            # location_id/interior_id and target_portal_id instead.
            if "from" in portal or "to" in portal:
                for endpoint in ("from", "to"):
                    anchor_id = portal.get(endpoint)
                    if not isinstance(anchor_id, str) or anchor_id not in ctx.anchors:
                        report.error("portal_anchor", f"portal {portal_id} {endpoint} references unknown anchor {anchor_id!r}", file=file_label, path=where, owner="A08")
                        errors += 1
            else:
                loc_id = portal.get("location_id")
                if loc_id is not None and loc_id not in ctx.locations:
                    report.gap("portal_location", f"portal {portal_id} references unknown location {loc_id!r}", file=file_label, path=where, owner="A08")
                interior_id = portal.get("interior_id")
                if interior_id is not None and interior_id not in ctx.locations and interior_id not in ctx.anchors:
                    report.gap("portal_interior", f"portal {portal_id} references unknown interior {interior_id!r}", file=file_label, path=where, owner="A08")
            ctx.portals.append(portal)
        portal_ids = {p.get("id") for p in ctx.portals if isinstance(p, dict)}
        for portal in ctx.portals:
            target_id = portal.get("target_portal_id") if isinstance(portal, dict) else None
            if target_id and target_id not in portal_ids:
                report.gap(
                    "portal_target",
                    f"portal {portal.get('id')} targets missing portal {target_id}",
                    file=rel_path(report, portals_path) if portals_path.exists() else rel_path(report, path),
                    owner="A08",
                )

    spawns = doc.get("spawns", []) if isinstance(doc, dict) else []
    spawns_path = ctx.data_dir / "World" / "spawns.json"
    if (not isinstance(spawns, list) or not spawns) and spawns_path.exists():
        spawn_doc = load_json(spawns_path, report)
        spawns = collection(spawn_doc, "spawns")
    if isinstance(spawns, list):
        for index, spawn in enumerate(spawns):
            where = f"$.spawns[{index}]"
            file_label = rel_path(report, spawns_path) if spawns_path.exists() and not (isinstance(doc, dict) and doc.get("spawns")) else rel_path(report, path)
            if not isinstance(spawn, dict):
                errors += 1
                continue
            spawn_id = spawn.get("id")
            if not isinstance(spawn_id, str) or not SLUG_RE.match(spawn_id):
                report.error("spawn_id", f"invalid spawn id {spawn_id!r}", file=file_label, path=where, owner="A08")
                errors += 1
            npc = spawn.get("npc", spawn.get("role", spawn.get("display_name")))
            if not isinstance(npc, str) or not SLUG_RE.match(npc):
                # A08's split spawn format uses role/display_name rather than npc.
                if not isinstance(spawn.get("display_name"), str):
                    report.error("spawn_npc", f"spawn {spawn_id} has no npc/role/display_name", file=file_label, path=where, owner="A08")
                    errors += 1
            loc_id = spawn.get("location", spawn.get("location_id"))
            if not isinstance(loc_id, str) or loc_id not in ctx.locations:
                report.error("spawn_location", f"spawn {spawn_id} references unknown location {loc_id!r}", file=file_label, path=where, owner="A08")
                errors += 1
            anchor_id = spawn.get("anchor", spawn.get("anchor_id"))
            if anchor_id is not None and (not isinstance(anchor_id, str) or anchor_id not in ctx.anchors):
                report.gap("spawn_anchor", f"spawn {spawn_id} references unknown anchor {anchor_id!r}", file=file_label, path=where, owner="A08")
            ctx.spawns.append(spawn)

    cells_path = ctx.data_dir / "World" / "interiors.json"
    cells = []
    if cells_path.exists():
        cells_doc = load_json(cells_path, report)
        cells = collection(cells_doc, "cells")
        for index, cell in enumerate(cells):
            if not isinstance(cell, dict):
                errors += 1
                continue
            cell_id = cell.get("id")
            if not isinstance(cell_id, str) or not SLUG_RE.match(cell_id):
                report.error("interior_id", f"invalid interior cell id {cell_id!r}", file=rel_path(report, cells_path), path=f"$.cells[{index}]", owner="A08")
                errors += 1
            loc_id = cell.get("location_id")
            if loc_id is not None and loc_id not in ctx.locations:
                report.gap("interior_location", f"interior {cell_id} references unknown location {loc_id!r}", file=rel_path(report, cells_path), owner="A08")

    report.check(
        "anchors",
        "fail" if errors else "pass",
        f"{len(ctx.locations)} locations, {len(ctx.anchors)} anchors, {len(cells)} interiors, {len(ctx.portals)} portals, {len(ctx.spawns)} spawns",
        owner="A08",
    )


# ---------------------------------------------------------------------------
# Story: events, dialogue, scenes, emails, schedules
# ---------------------------------------------------------------------------


def _story_path(ctx: Context, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw
    text = value.replace("\\", "/")
    if text.startswith("Story/"):
        return ctx.data_dir / text
    return ctx.data_dir / "Story" / text


def _check_anchor_ref(
    ctx: Context, anchor: Any, report: Report, file: str, where: str, owner: str
) -> int:
    if anchor is None:
        return 0
    if not isinstance(anchor, str) or not ANCHOR_RE.match(anchor):
        report.error("anchor_ref_shape", f"invalid anchor id {anchor!r}", file=file, path=where, owner=owner)
        return 1
    if ctx.anchors and anchor not in ctx.anchors:
        ctx.missing_anchors.add(anchor)
        return 0
    return 0


def _check_location_ref(
    ctx: Context, location: Any, report: Report, file: str, where: str, owner: str
) -> int:
    if location is None:
        return 0
    if not isinstance(location, str) or not SLUG_RE.match(location):
        report.error("location_ref_shape", f"invalid location id {location!r}", file=file, path=where, owner=owner)
        return 1
    if ctx.locations and location not in ctx.locations:
        ctx.missing_locations.add(location)
        return 0
    return 0


def _validate_rewards(
    ctx: Context,
    rewards: Any,
    report: Report,
    *,
    file: str,
    where: str,
    owner: str,
) -> int:
    if rewards is None:
        return 0
    if not isinstance(rewards, dict):
        report.error("reward_shape", "rewards must be an object", file=file, path=where, owner=owner)
        return 1
    errors = 0
    dp = rewards.get("dp")
    if dp is not None and (not isinstance(dp, int) or isinstance(dp, bool) or dp < 0):
        report.error("reward_dp", f"invalid DP reward {dp!r}", file=file, path=where, owner=owner)
        errors += 1
    for entry in rewards.get("cards", []) or []:
        card_id = entry if isinstance(entry, int) else entry.get("card") if isinstance(entry, dict) else None
        if not valid_card_id(card_id):
            report.error("reward_card", f"invalid reward card {card_id!r}", file=file, path=where, owner=owner)
            errors += 1
        elif ctx.cards and card_id not in ctx.cards:
            report.error("reward_card_ref", f"reward references missing card {card_id}", file=file, path=where, owner=owner)
            errors += 1
        else:
            ctx.reward_cards.add(card_id)
    for entry in rewards.get("packs", []) or []:
        pack_id = entry if isinstance(entry, str) else entry.get("pack") if isinstance(entry, dict) else None
        if not isinstance(pack_id, str) or not SLUG_RE.match(pack_id):
            report.error("reward_pack", f"invalid reward pack {pack_id!r}", file=file, path=where, owner=owner)
            errors += 1
        else:
            ctx.reward_packs.add(pack_id)
            if ctx.packs and pack_id not in ctx.packs:
                report.error("reward_pack_ref", f"reward references missing pack {pack_id}", file=file, path=where, owner=owner)
                errors += 1
    for flag in rewards.get("flags", []) or []:
        if not isinstance(flag, str) or not SLUG_RE.match(flag):
            report.error("reward_flag", f"invalid reward flag {flag!r}", file=file, path=where, owner=owner)
            errors += 1
        else:
            ctx.written_flags.add(flag)
    counters = rewards.get("counters", {})
    if isinstance(counters, dict):
        for counter, value in counters.items():
            if not isinstance(counter, str) or not SLUG_RE.match(counter):
                report.error("reward_counter", f"invalid reward counter {counter!r}", file=file, path=where, owner=owner)
                errors += 1
            elif not isinstance(value, int) or isinstance(value, bool):
                report.error("reward_counter_value", f"counter {counter} reward must be an integer", file=file, path=where, owner=owner)
                errors += 1
            else:
                ctx.written_counters.add(counter)
    title = rewards.get("title")
    if title is not None and (not isinstance(title, str) or not title.strip()):
        report.error("reward_title", "title reward must be a non-empty string", file=file, path=where, owner=owner)
        errors += 1
    dorm = rewards.get("dorm")
    if dorm is not None and dorm not in DORMS:
        report.error("reward_dorm", f"invalid dorm reward {dorm!r}", file=file, path=where, owner=owner)
        errors += 1
    return errors


def _validate_reward_arg(
    ctx: Context, arg: Any, report: Report, *, file: str, where: str, owner: str
) -> int:
    if not isinstance(arg, str) or ":" not in arg:
        report.error("story_reward_arg", f"reward arg must be key:value, got {arg!r}", file=file, path=where, owner=owner)
        return 1
    key, value = arg.split(":", 1)
    key = key.strip()
    value = value.strip()
    if key == "dp":
        try:
            amount = int(value)
        except ValueError:
            amount = -1
        if amount < 0:
            report.error("story_reward_dp", f"invalid DP reward {arg!r}", file=file, path=where, owner=owner)
            return 1
        return 0
    if key == "card":
        try:
            card_id = int(value)
        except ValueError:
            card_id = -1
        if not valid_card_id(card_id):
            report.error("story_reward_card", f"invalid card reward {arg!r}", file=file, path=where, owner=owner)
            return 1
        if ctx.cards and card_id not in ctx.cards:
            report.error("story_reward_card_ref", f"reward references missing card {card_id}", file=file, path=where, owner=owner)
            return 1
        ctx.reward_cards.add(card_id)
        return 0
    if key == "pack":
        if not SLUG_RE.match(value):
            report.error("story_reward_pack", f"invalid pack reward {arg!r}", file=file, path=where, owner=owner)
            return 1
        ctx.reward_packs.add(value)
        if ctx.packs and value not in ctx.packs:
            report.error("story_reward_pack_ref", f"reward references missing pack {value}", file=file, path=where, owner=owner)
            return 1
        return 0
    if key == "flag":
        if not SLUG_RE.match(value):
            report.error("story_reward_flag", f"invalid flag reward {arg!r}", file=file, path=where, owner=owner)
            return 1
        ctx.written_flags.add(value)
        return 0
    if key == "title":
        if not value:
            report.error("story_reward_title", f"empty title reward {arg!r}", file=file, path=where, owner=owner)
            return 1
        return 0
    if key == "dorm":
        if value not in DORMS:
            report.error("story_reward_dorm", f"invalid dorm reward {arg!r}", file=file, path=where, owner=owner)
            return 1
        return 0
    if key == "reward_id":
        if not SLUG_RE.match(value):
            report.error("story_reward_id", f"invalid reward id {arg!r}", file=file, path=where, owner=owner)
            return 1
        return 0
    report.warn("story_reward_key", f"unknown reward key in {arg!r}", file=file, path=where, owner=owner)
    return 0


def _validate_condition(
    ctx: Context,
    condition: Any,
    report: Report,
    *,
    file: str,
    where: str,
    owner: str,
) -> int:
    if not isinstance(condition, dict):
        report.error("event_condition_shape", "condition must be an object", file=file, path=where, owner=owner)
        return 1
    kind = condition.get("type")
    if kind not in {
        "flag",
        "counter",
        "date",
        "weekday",
        "period",
        "event",
        "card",
        "location",
        "dorm",
        "title",
        "duel_result",
        "exam_result",
    }:
        report.error("event_condition_type", f"unknown condition type {kind!r}", file=file, path=where, owner=owner)
        return 1
    errors = 0
    op = condition.get("op")
    if op is not None and op not in {"==", "!=", ">", ">=", "<", "<="}:
        report.error("event_condition_op", f"invalid condition op {op!r}", file=file, path=where, owner=owner)
        errors += 1
    if kind in {"flag", "counter"}:
        name = condition.get("id")
        if not isinstance(name, str) or not SLUG_RE.match(name):
            report.error("event_condition_id", f"{kind} condition has invalid id {name!r}", file=file, path=where, owner=owner)
            errors += 1
        elif kind == "flag":
            ctx.read_flags.add(name)
            value = condition.get("value")
            if value is not None and not isinstance(value, bool):
                report.error("event_condition_value", f"flag {name} condition value must be boolean", file=file, path=where, owner=owner)
                errors += 1
        else:
            ctx.read_counters.add(name)
            value = condition.get("value")
            if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                report.error("event_condition_value", f"counter {name} condition value must be an integer", file=file, path=where, owner=owner)
                errors += 1
    elif kind == "date":
        month = condition.get("calendar_month", condition.get("month"))
        day = condition.get("day")
        if month is not None and (not isinstance(month, int) or not (1 <= month <= 12)):
            report.error("event_condition_month", f"invalid date month {month!r}", file=file, path=where, owner=owner)
            errors += 1
        if day is not None and (not isinstance(day, int) or not (1 <= day <= 31)):
            report.error("event_condition_day", f"invalid date day {day!r}", file=file, path=where, owner=owner)
            errors += 1
        if month is None and day is None:
            report.error("event_condition_date", "date condition needs calendar_month and/or day", file=file, path=where, owner=owner)
            errors += 1
    elif kind == "weekday":
        if condition.get("value") not in WEEKDAYS:
            report.error("event_condition_weekday", f"invalid weekday {condition.get('value')!r}", file=file, path=where, owner=owner)
            errors += 1
    elif kind == "period":
        if condition.get("value") not in PERIODS:
            report.error("event_condition_period", f"invalid period {condition.get('value')!r}", file=file, path=where, owner=owner)
            errors += 1
    elif kind == "event":
        event_id = condition.get("id")
        if not isinstance(event_id, str) or not EVENT_RE.match(event_id):
            report.error("event_condition_event", f"invalid event reference {event_id!r}", file=file, path=where, owner=owner)
            errors += 1
        elif ctx.events and event_id not in ctx.events:
            report.error("event_condition_event_ref", f"condition references unknown event {event_id}", file=file, path=where, owner=owner)
            errors += 1
        state = condition.get("state")
        if state is not None and state not in EVENT_STATES:
            report.error("event_condition_state", f"invalid event state {state!r}", file=file, path=where, owner=owner)
            errors += 1
    elif kind == "card":
        card_id = condition.get("id")
        if not valid_card_id(card_id):
            report.error("event_condition_card", f"invalid card reference {card_id!r}", file=file, path=where, owner=owner)
            errors += 1
        elif ctx.cards and card_id not in ctx.cards:
            report.error("event_condition_card_ref", f"condition references missing card {card_id}", file=file, path=where, owner=owner)
            errors += 1
        min_count = condition.get("min_count")
        if min_count is not None and (not isinstance(min_count, int) or min_count < 0):
            report.error("event_condition_count", f"invalid min_count {min_count!r}", file=file, path=where, owner=owner)
            errors += 1
    elif kind == "location":
        errors += _check_location_ref(ctx, condition.get("id"), report, file, where, owner)
    elif kind == "dorm":
        if condition.get("value") not in DORMS:
            report.error("event_condition_dorm", f"invalid dorm {condition.get('value')!r}", file=file, path=where, owner=owner)
            errors += 1
    elif kind == "title":
        if not isinstance(condition.get("value"), str) or not condition["value"].strip():
            report.error("event_condition_title", "title condition needs a non-empty value", file=file, path=where, owner=owner)
            errors += 1
    elif kind in {"duel_result", "exam_result"}:
        if condition.get("value") is None and condition.get("state") is None:
            report.error("event_condition_result", f"{kind} condition needs value/state", file=file, path=where, owner=owner)
            errors += 1
    if condition.get("negate") is not None and not isinstance(condition["negate"], bool):
        report.error("event_condition_negate", "negate must be boolean", file=file, path=where, owner=owner)
        errors += 1
    return errors


def _validate_commands(
    ctx: Context,
    commands: Any,
    report: Report,
    *,
    file: str,
    where: str,
    event_id: str | None,
    owner: str,
) -> int:
    if not isinstance(commands, list) or not commands:
        report.error("scene_commands", "commands must be a non-empty array", file=file, path=where, owner=owner)
        return 1
    errors = 0
    seen_ids: set[str] = set()
    for index, command in enumerate(commands):
        cwhere = f"{where}[{index}]"
        if not isinstance(command, dict):
            report.error("command_shape", "command must be an object", file=file, path=cwhere, owner=owner)
            errors += 1
            continue
        command_type = command.get("type")
        if command_type not in STORY_COMMANDS:
            report.error("command_type", f"unknown command type {command_type!r}", file=file, path=cwhere, owner=owner)
            errors += 1
            continue
        command_id = command.get("command_id")
        if command_id is not None:
            if not isinstance(command_id, str) or not command_id:
                report.error("command_id", "command_id must be a non-empty string", file=file, path=cwhere, owner=owner)
                errors += 1
            elif command_id in seen_ids:
                report.error("command_duplicate", f"duplicate command_id {command_id}", file=file, path=cwhere, owner=owner)
                errors += 1
            else:
                seen_ids.add(command_id)
        args = command.get("args", [])
        if not isinstance(args, list) or any(not isinstance(arg, str) for arg in args):
            report.error("command_args", "args must be an array of strings", file=file, path=cwhere, owner=owner)
            errors += 1
            args = []
        duration = command.get("duration", 0)
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
            report.error("command_duration", f"invalid duration {duration!r}", file=file, path=cwhere, owner=owner)
            errors += 1
        if command.get("skippable") is not None and not isinstance(command["skippable"], bool):
            report.error("command_skippable", "skippable must be boolean", file=file, path=cwhere, owner=owner)
            errors += 1
        if command_type == "End":
            if args:
                report.error("command_end_args", "End must not have args", file=file, path=cwhere, owner=owner)
                errors += 1
            if index != len(commands) - 1:
                report.error("command_end_position", "End must be the last command", file=file, path=cwhere, owner=owner)
                errors += 1
        else:
            if command_type == "Dialogue":
                text_key = command.get("text_key")
                if not isinstance(text_key, str) or not text_key:
                    report.error("command_dialogue_key", "Dialogue needs text_key", file=file, path=cwhere, owner=owner)
                    errors += 1
                else:
                    ctx.referenced_text_keys.add(text_key)
                    if ctx.dialogue and text_key not in ctx.dialogue:
                        report.error("command_dialogue_ref", f"Dialogue references missing text key {text_key}", file=file, path=cwhere, owner=owner)
                        errors += 1
                speaker = command.get("speaker")
                if speaker is not None and (not isinstance(speaker, str) or not SLUG_RE.match(speaker)):
                    report.error("command_speaker", f"invalid speaker {speaker!r}", file=file, path=cwhere, owner=owner)
                    errors += 1
            elif command_type == "Choice":
                text_key = command.get("text_key")
                if not isinstance(text_key, str) or not text_key:
                    report.error("command_choice_key", "Choice needs text_key", file=file, path=cwhere, owner=owner)
                    errors += 1
                else:
                    ctx.referenced_text_keys.add(text_key)
                    if ctx.dialogue and text_key not in ctx.dialogue:
                        report.error("command_choice_ref", f"Choice references missing text key {text_key}", file=file, path=cwhere, owner=owner)
                        errors += 1
                choices = command.get("choices")
                if choices is not None:
                    if not isinstance(choices, list) or not choices:
                        report.error("command_choices", "Choice choices must be a non-empty array", file=file, path=cwhere, owner=owner)
                        errors += 1
                    else:
                        ids: set[str] = set()
                        for choice_index, choice in enumerate(choices):
                            if not isinstance(choice, dict):
                                errors += 1
                                continue
                            cid = choice.get("id")
                            if not isinstance(cid, str) or not SLUG_RE.match(cid):
                                report.error("choice_id", f"invalid choice id {cid!r}", file=file, path=f"{cwhere}.choices[{choice_index}]", owner=owner)
                                errors += 1
                            elif cid in ids:
                                report.error("choice_duplicate", f"duplicate choice id {cid}", file=file, path=f"{cwhere}.choices[{choice_index}]", owner=owner)
                                errors += 1
                            else:
                                ids.add(cid)
                            choice_key = choice.get("text_key")
                            if not isinstance(choice_key, str) or not choice_key:
                                report.error("choice_key", "choice needs text_key", file=file, path=f"{cwhere}.choices[{choice_index}]", owner=owner)
                                errors += 1
                            else:
                                ctx.referenced_text_keys.add(choice_key)
                                if ctx.dialogue and choice_key not in ctx.dialogue:
                                    report.error("choice_key_ref", f"choice references missing text key {choice_key}", file=file, path=f"{cwhere}.choices[{choice_index}]", owner=owner)
                                    errors += 1
                            for flag in choice.get("set_flags", []) or []:
                                if not isinstance(flag, str) or not SLUG_RE.match(flag):
                                    report.error("choice_flag", f"invalid choice flag {flag!r}", file=file, path=f"{cwhere}.choices[{choice_index}]", owner=owner)
                                    errors += 1
                                else:
                                    ctx.written_flags.add(flag)
                elif not args and not command.get("_legacy"):
                    report.error("command_choice_args", "Choice needs choices or args", file=file, path=cwhere, owner=owner)
                    errors += 1
            elif command_type == "Camera":
                if not args:
                    report.error("command_camera", "Camera needs an anchor in args[0]", file=file, path=cwhere, owner=owner)
                    errors += 1
                else:
                    errors += _check_anchor_ref(ctx, args[0], report, file, cwhere, owner)
            elif command_type == "MoveNpc":
                if len(args) < 2:
                    report.error("command_movenpc", "MoveNpc needs npc and anchor args", file=file, path=cwhere, owner=owner)
                    errors += 1
                else:
                    if not SLUG_RE.match(args[0]):
                        report.error("command_movenpc_npc", f"invalid npc {args[0]!r}", file=file, path=cwhere, owner=owner)
                        errors += 1
                    errors += _check_anchor_ref(ctx, args[1], report, file, cwhere, owner)
            elif command_type == "Fade":
                if not args:
                    report.error("command_fade", "Fade needs in/out in args[0]", file=file, path=cwhere, owner=owner)
                    errors += 1
                elif args[0] not in {"in", "out", "black", "white"}:
                    report.warn("command_fade_value", f"unusual fade direction {args[0]!r}", file=file, path=cwhere, owner=owner)
            elif command_type == "Wait":
                if isinstance(duration, (int, float)) and duration <= 0:
                    report.error("command_wait", "Wait needs duration > 0", file=file, path=cwhere, owner=owner)
                    errors += 1
            elif command_type == "Banner":
                if not args or not args[0]:
                    report.error("command_banner", "Banner needs a key/text arg", file=file, path=cwhere, owner=owner)
                    errors += 1
            elif command_type in {"PlaySfx", "Music"}:
                if not args or not args[0]:
                    report.error("command_audio", f"{command_type} needs a cue id in args[0]", file=file, path=cwhere, owner=owner)
                    errors += 1
            elif command_type == "Duel":
                if len(args) < 3:
                    report.error("command_duel", "Duel needs opponent, deck and mode", file=file, path=cwhere, owner=owner)
                    errors += 1
                else:
                    opponent, deck_id, mode = args[0], args[1], args[2]
                    if ctx.opponents and opponent not in ctx.opponents:
                        report.error("command_duel_opponent", f"Duel references unknown opponent {opponent}", file=file, path=cwhere, owner=owner)
                        errors += 1
                    if ctx.decks and deck_id not in ctx.decks:
                        report.gap(
                            "command_duel_deck",
                            f"Duel references unknown deck {deck_id}",
                            file=file,
                            path=cwhere,
                            owner=owner,
                            hint="publish the tutorial/event deck or use an existing deck id",
                        )
                    if mode not in DUEL_MODES:
                        report.error("command_duel_mode", f"Duel has invalid mode {mode!r}", file=file, path=cwhere, owner=owner)
                        errors += 1
                    if mode == "puzzle":
                        if len(args) < 4 or not PUZZLE_RE.match(args[3]):
                            report.error("command_duel_puzzle", "puzzle duel needs a puzzle id in args[3]", file=file, path=cwhere, owner=owner)
                            errors += 1
                        elif ctx.puzzles and args[3] not in ctx.puzzles:
                            report.error("command_duel_puzzle_ref", f"Duel references unknown puzzle {args[3]}", file=file, path=cwhere, owner=owner)
                            errors += 1
            elif command_type == "Reward":
                if not args:
                    report.error("command_reward", "Reward needs at least one key:value arg", file=file, path=cwhere, owner=owner)
                    errors += 1
                for arg in args:
                    errors += _validate_reward_arg(ctx, arg, report, file=file, where=cwhere, owner=owner)
            elif command_type == "SetFlag":
                if not args or not SLUG_RE.match(args[0]):
                    report.error("command_setflag", "SetFlag needs a valid flag in args[0]", file=file, path=cwhere, owner=owner)
                    errors += 1
                else:
                    ctx.written_flags.add(args[0])
    if not any(isinstance(command, dict) and command.get("type") == "End" for command in commands):
        report.warn("scene_no_end", f"scene {event_id or '?'} has no End command", file=file, path=where, owner=owner)
    return errors


def _normalize_legacy_event(event: dict) -> dict:
    """Map A03's opening-bundle event shape to the v1 event graph shape."""
    out: dict[str, Any] = {
        "id": event.get("id"),
        "title": event.get("title", ""),
        "priority": event.get("priority"),
        "repeatable": event.get("repeatable", False),
        "source": "legacy-story-bundle",
    }
    trigger = event.get("trigger")
    if isinstance(trigger, dict):
        trigger_type = trigger.get("type")
        if trigger_type == "new_game":
            out["trigger_type"] = "new_game"
        elif trigger_type == "date":
            out["date"] = {
                "calendar_month": trigger.get("month"),
                "day": trigger.get("day"),
                "weekday": trigger.get("weekday"),
                "period": trigger.get("period"),
            }
        elif trigger_type == "talk":
            out["location"] = trigger.get("location")
            out["anchor"] = trigger.get("anchor")
            out["trigger_npc"] = trigger.get("npc")

    requirements = []
    requires_events = []
    for requirement in event.get("requirements", []) or []:
        if not isinstance(requirement, dict):
            continue
        kind = requirement.get("type")
        if kind == "event_complete":
            event_id = requirement.get("event")
            if isinstance(event_id, str):
                requires_events.append(event_id)
                requirements.append({"type": "event", "id": event_id, "state": "complete"})
        elif kind == "flag":
            requirements.append({"type": "flag", "id": requirement.get("flag"), "value": requirement.get("value", True)})
        elif kind in {"date_at_least", "date"}:
            requirements.append(
                {
                    "type": "date",
                    "calendar_month": requirement.get("month"),
                    "day": requirement.get("day"),
                    "op": ">=" if kind == "date_at_least" else "==",
                }
            )
        elif kind == "counter_at_least":
            requirements.append(
                {
                    "type": "counter",
                    "id": requirement.get("counter"),
                    "op": ">=",
                    "value": requirement.get("value"),
                }
            )
    if requirements:
        out["requires"] = requirements
    if requires_events:
        out["requires_events"] = requires_events

    scene = event.get("scene")
    if isinstance(scene, str):
        out["scene"] = scene
        out["_legacy_scene"] = True

    rewards: dict[str, Any] = {}
    flags = []
    counters: dict[str, int] = {}
    for outcome in event.get("outcomes", []) or []:
        if not isinstance(outcome, dict):
            continue
        kind = outcome.get("type")
        if kind == "set_flag":
            flag = outcome.get("flag")
            if isinstance(flag, str):
                flags.append(flag)
        elif kind == "add_counter":
            counter = outcome.get("counter")
            amount = outcome.get("amount", 0)
            if isinstance(counter, str) and isinstance(amount, int):
                counters[counter] = counters.get(counter, 0) + amount
        elif kind == "reward":
            # Reward ids are resolved by the story bundle's rewards table.
            pass
    if rewards:
        out["rewards"] = rewards
    if flags or counters:
        out["on_complete"] = {}
        if flags:
            out["on_complete"]["flags"] = flags
        if counters:
            out["on_complete"]["counters"] = counters
    if event.get("fail_forward") is True:
        out["fallback"] = "continue"
    return out


def validate_events(ctx: Context, report: Report) -> None:
    candidates = [ctx.data_dir / "Story" / "events.json", ctx.data_dir / "Story" / "opening.json"]
    candidates.extend(glob_json(ctx.data_dir / "Story" / "events"))
    path = first_existing(candidates)
    ctx.dataset_presence["events"] = path is not None
    if path is None:
        report.gap(
            "events_missing",
            "no story event graph found",
            owner="A03",
            hint="expected Content/Data/Story/events.json",
        )
        report.check("events", "gap", "no events", owner="A03")
        return
    doc = load_json(path, report)
    if doc is None:
        report.check("events", "fail", "events unreadable", owner="A03")
        return
    legacy_events = isinstance(doc, dict) and isinstance(doc.get("events"), list) and isinstance(doc.get("beats"), list)
    if legacy_events:
        items = [_normalize_legacy_event(event) for event in doc["events"] if isinstance(event, dict)]
        report.warn(
            "event_schema_drift",
            "events use trigger/requirements/outcomes and scene ids; canonical v1 uses date/requires/rewards and scene paths",
            file=rel_path(report, path),
            owner="A03",
        )
    else:
        items = collection(doc, "events")
        apply_schema(doc, "events", rel_path(report, path), report, key="events")
    records: list[tuple[int, dict]] = []
    errors = 0
    for index, event in enumerate(items):
        where = f"$.events[{index}]"
        if not isinstance(event, dict):
            report.error("event_shape", "event is not an object", file=rel_path(report, path), path=where, owner="A03")
            errors += 1
            continue
        event_id = event.get("id")
        if not isinstance(event_id, str) or not EVENT_RE.match(event_id):
            report.error("event_id", f"invalid event id {event_id!r}", file=rel_path(report, path), path=where, owner="A03")
            errors += 1
            continue
        if event_id in ctx.events:
            report.error("event_duplicate", f"duplicate event id {event_id}", file=rel_path(report, path), path=where, owner="A03")
            errors += 1
            continue
        ctx.events[event_id] = event
        records.append((index, event))

    for index, event in records:
        where = f"$.events[{index}]"
        event_id = event["id"]
        file_label = rel_path(report, path)
        title = event.get("title")
        if not isinstance(title, str) or not title.strip():
            report.error("event_title", f"event {event_id} has an empty title", file=file_label, path=where, owner="A03")
            errors += 1
        order = event.get("order")
        if order is not None and (not isinstance(order, int) or isinstance(order, bool)):
            report.error("event_order", f"event {event_id} has invalid order {order!r}", file=file_label, path=where, owner="A03")
            errors += 1
        if event.get("repeatable") is not None and not isinstance(event["repeatable"], bool):
            report.error("event_repeatable", f"event {event_id} repeatable must be boolean", file=file_label, path=where, owner="A03")
            errors += 1
        priority = event.get("priority")
        if priority is not None and (not isinstance(priority, int) or isinstance(priority, bool)):
            report.error("event_priority", f"event {event_id} has invalid priority {priority!r}", file=file_label, path=where, owner="A03")
            errors += 1

        date = event.get("date")
        if isinstance(date, dict):
            month = date.get("calendar_month", date.get("month"))
            day = date.get("day")
            weekday = date.get("weekday")
            period = date.get("period")
            if month is not None and (not isinstance(month, int) or not (1 <= month <= 12)):
                report.error("event_date_month", f"event {event_id} has invalid month {month!r}", file=file_label, path=where, owner="A03")
                errors += 1
            if day is not None and (not isinstance(day, int) or not (1 <= day <= 31)):
                report.error("event_date_day", f"event {event_id} has invalid day {day!r}", file=file_label, path=where, owner="A03")
                errors += 1
            if weekday is not None and weekday not in WEEKDAYS:
                report.error("event_date_weekday", f"event {event_id} has invalid weekday {weekday!r}", file=file_label, path=where, owner="A03")
                errors += 1
            if period is not None and period not in PERIODS:
                report.error("event_date_period", f"event {event_id} has invalid period {period!r}", file=file_label, path=where, owner="A03")
                errors += 1
        elif date is not None:
            report.error("event_date_shape", f"event {event_id} date must be an object", file=file_label, path=where, owner="A03")
            errors += 1
        errors += _check_location_ref(ctx, event.get("location"), report, file_label, where, "A03")
        errors += _check_anchor_ref(ctx, event.get("anchor"), report, file_label, where, "A03")
        dorm = event.get("dorm")
        if dorm is not None and dorm not in DORMS:
            report.error("event_dorm", f"event {event_id} has invalid dorm {dorm!r}", file=file_label, path=where, owner="A03")
            errors += 1

        conditions = event.get("requires", [])
        if conditions is not None:
            if not isinstance(conditions, list):
                report.error("event_requires", f"event {event_id} requires must be an array", file=file_label, path=where, owner="A03")
                errors += 1
            else:
                for cindex, condition in enumerate(conditions):
                    errors += _validate_condition(ctx, condition, report, file=file_label, where=f"{where}.requires[{cindex}]", owner="A03")

        requires_events = event.get("requires_events", [])
        if requires_events is not None:
            if not isinstance(requires_events, list):
                report.error("event_requires_events", f"event {event_id} requires_events must be an array", file=file_label, path=where, owner="A03")
                errors += 1
                ctx.event_requires[event_id] = []
            else:
                clean: list[str] = []
                for required in requires_events:
                    if not isinstance(required, str) or not EVENT_RE.match(required):
                        report.error("event_requires_event_id", f"event {event_id} has invalid required event {required!r}", file=file_label, path=where, owner="A03")
                        errors += 1
                    elif required == event_id:
                        report.error("event_self_requires", f"event {event_id} requires itself", file=file_label, path=where, owner="A03")
                        errors += 1
                    else:
                        clean.append(required)
                ctx.event_requires[event_id] = clean

        scene = event.get("scene")
        if scene is not None:
            if event.get("_legacy_scene"):
                ctx.legacy_scene_refs.append((event_id, str(scene), file_label))
            elif not isinstance(scene, str) or not scene.endswith(".json"):
                report.error("event_scene", f"event {event_id} has invalid scene path {scene!r}", file=file_label, path=where, owner="A03")
                errors += 1
            else:
                scene_file = _story_path(ctx, scene)
                if not scene_file.exists():
                    report.error("event_scene_missing", f"event {event_id} scene file not found: {scene}", file=file_label, path=where, owner="A03")
                    errors += 1
                else:
                    ctx.scene_refs[event_id] = rel_path(report, scene_file)
        commands = event.get("commands")
        if commands is not None:
            errors += _validate_commands(ctx, commands, report, file=file_label, where=f"{where}.commands", event_id=event_id, owner="A03")
        if scene is None and commands is None:
            report.error("event_scene_required", f"event {event_id} needs scene or commands", file=file_label, path=where, owner="A03")
            errors += 1

        choices = event.get("choices", [])
        if choices is not None:
            if not isinstance(choices, list):
                report.error("event_choices", f"event {event_id} choices must be an array", file=file_label, path=where, owner="A03")
                errors += 1
            else:
                choice_ids: set[str] = set()
                for cindex, choice in enumerate(choices):
                    cwhere = f"{where}.choices[{cindex}]"
                    if not isinstance(choice, dict):
                        report.error("event_choice_shape", "choice must be an object", file=file_label, path=cwhere, owner="A03")
                        errors += 1
                        continue
                    cid = choice.get("id")
                    if not isinstance(cid, str) or not SLUG_RE.match(cid):
                        report.error("event_choice_id", f"invalid choice id {cid!r}", file=file_label, path=cwhere, owner="A03")
                        errors += 1
                    elif cid in choice_ids:
                        report.error("event_choice_duplicate", f"duplicate choice id {cid}", file=file_label, path=cwhere, owner="A03")
                        errors += 1
                    else:
                        choice_ids.add(cid)
                    text_key = choice.get("text_key")
                    if not isinstance(text_key, str) or not text_key:
                        report.error("event_choice_key", "choice needs text_key", file=file_label, path=cwhere, owner="A03")
                        errors += 1
                    else:
                        ctx.referenced_text_keys.add(text_key)
                        if ctx.dialogue and text_key not in ctx.dialogue:
                            report.error("event_choice_key_ref", f"choice references missing text key {text_key}", file=file_label, path=cwhere, owner="A03")
                            errors += 1
                    errors += _validate_rewards(ctx, choice.get("rewards"), report, file=file_label, where=cwhere, owner="A03")
                    for flag in choice.get("set_flags", []) or []:
                        if not isinstance(flag, str) or not SLUG_RE.match(flag):
                            report.error("event_choice_flag", f"invalid choice flag {flag!r}", file=file_label, path=cwhere, owner="A03")
                            errors += 1
                        else:
                            ctx.written_flags.add(flag)
                    next_event = choice.get("next_event")
                    if next_event is not None and (not isinstance(next_event, str) or not EVENT_RE.match(next_event)):
                        report.error("event_choice_next", f"invalid next_event {next_event!r}", file=file_label, path=cwhere, owner="A03")
                        errors += 1

        duel = event.get("duel")
        if isinstance(duel, dict):
            opponent = duel.get("opponent")
            deck_id = duel.get("deck")
            mode = duel.get("mode")
            if ctx.opponents and opponent not in ctx.opponents:
                report.error("event_duel_opponent", f"event {event_id} references unknown opponent {opponent}", file=file_label, path=where, owner="A03")
                errors += 1
            if ctx.decks and deck_id not in ctx.decks:
                report.error("event_duel_deck", f"event {event_id} references unknown deck {deck_id}", file=file_label, path=where, owner="A03")
                errors += 1
            if mode not in DUEL_MODES:
                report.error("event_duel_mode", f"event {event_id} has invalid duel mode {mode!r}", file=file_label, path=where, owner="A03")
                errors += 1
            puzzle_id = duel.get("puzzle")
            if mode == "puzzle" and not puzzle_id:
                report.error("event_duel_puzzle", f"event {event_id} puzzle duel needs a puzzle id", file=file_label, path=where, owner="A03")
                errors += 1
            if puzzle_id is not None and ctx.puzzles and puzzle_id not in ctx.puzzles:
                report.error("event_duel_puzzle_ref", f"event {event_id} references unknown puzzle {puzzle_id}", file=file_label, path=where, owner="A03")
                errors += 1
        elif duel is not None:
            report.error("event_duel_shape", f"event {event_id} duel must be an object", file=file_label, path=where, owner="A03")
            errors += 1

        errors += _validate_rewards(ctx, event.get("rewards"), report, file=file_label, where=where, owner="A03")
        on_complete = event.get("on_complete")
        if isinstance(on_complete, dict):
            for flag in on_complete.get("flags", []) or []:
                if not isinstance(flag, str) or not SLUG_RE.match(flag):
                    report.error("event_complete_flag", f"invalid on_complete flag {flag!r}", file=file_label, path=where, owner="A03")
                    errors += 1
                else:
                    ctx.written_flags.add(flag)
            counters = on_complete.get("counters", {})
            if isinstance(counters, dict):
                for counter, value in counters.items():
                    if not isinstance(counter, str) or not SLUG_RE.match(counter):
                        report.error("event_complete_counter", f"invalid on_complete counter {counter!r}", file=file_label, path=where, owner="A03")
                        errors += 1
                    elif not isinstance(value, int) or isinstance(value, bool):
                        report.error("event_complete_counter_value", f"counter {counter} must be an integer", file=file_label, path=where, owner="A03")
                        errors += 1
                    else:
                        ctx.written_counters.add(counter)
        fallback = event.get("fallback")
        if fallback is not None and fallback not in {"continue", "retry", "end", "fail", "skip"}:
            report.error("event_fallback", f"event {event_id} has invalid fallback {fallback!r}", file=file_label, path=where, owner="A03")
            errors += 1

    expected = {f"E{index:02d}" for index in range(1, 34)}
    missing = sorted(expected - set(ctx.events))
    if missing:
        report.gap(
            "event_coverage",
            f"{len(ctx.events)} events; missing numbered events: {', '.join(missing)}",
            file=rel_path(report, path),
            owner="A03",
            hint="canon is E01..E33 plus E28b and event-only variants",
        )

    for event_id, required in ctx.event_requires.items():
        for required_id in required:
            if required_id not in ctx.events:
                report.error(
                    "event_requires_ref",
                    f"event {event_id} requires unknown event {required_id}",
                    file=rel_path(report, path),
                    owner="A03",
                )
                errors += 1

    # Static reachability through requires_events. Date/talk conditions still
    # gate runtime availability; this catches accidental islands and cycles.
    if ctx.events:
        state: dict[str, int] = {}

        def visit(event_id: str, stack: list[str]) -> None:
            if state.get(event_id) == 1:
                cycle = " -> ".join(stack + [event_id])
                report.error("event_cycle", f"requires_events cycle: {cycle}", file=rel_path(report, path), owner="A03")
                return
            if state.get(event_id) == 2:
                return
            state[event_id] = 1
            for required_id in ctx.event_requires.get(event_id, []):
                if required_id in ctx.events:
                    visit(required_id, stack + [event_id])
            state[event_id] = 2

        for event_id in ctx.events:
            visit(event_id, [])
        roots = [event_id for event_id in ctx.events if not ctx.event_requires.get(event_id)]
        reachable: set[str] = set()

        def mark(event_id: str) -> None:
            if event_id in reachable:
                return
            reachable.add(event_id)
            for candidate, required in ctx.event_requires.items():
                if event_id in required:
                    mark(candidate)

        for root in roots:
            mark(root)
        unreachable = sorted(set(ctx.events) - reachable)
        if roots and unreachable:
            report.warn(
                "event_unreachable",
                f"{len(unreachable)} event(s) not reachable through requires_events: {', '.join(unreachable[:20])}",
                file=rel_path(report, path),
                owner="A03",
                hint="date/talk triggers may still make them reachable; verify in the event graph test",
            )

    report.check(
        "events",
        "fail" if errors else ("gap" if missing else "pass"),
        f"{len(ctx.events)} events; {len(ctx.event_requires)} requirement edges",
        owner="A03",
    )


def validate_dialogue(ctx: Context, report: Report) -> None:
    candidates = [ctx.data_dir / "Story" / "dialogue.json"]
    candidates.extend(glob_json(ctx.data_dir / "Story" / "dialogue"))
    path = first_existing(candidates)
    ctx.dataset_presence["dialogue"] = path is not None
    if path is None:
        report.gap(
            "dialogue_missing",
            "no dialogue table found",
            owner="A03",
            hint="expected Content/Data/Story/dialogue.json",
        )
        report.check("dialogue", "gap", "no dialogue", owner="A03")
        return
    doc = load_json(path, report)
    if doc is None:
        report.check("dialogue", "fail", "dialogue unreadable", owner="A03")
        return
    if isinstance(doc, dict) and isinstance(doc.get("nodes"), dict):
        lines = doc["nodes"]
        report.warn(
            "dialogue_schema_drift",
            "dialogue uses nodes{}; canonical v1 wrapper is lines{}",
            file=rel_path(report, path),
            owner="A03",
        )
    else:
        lines = doc.get("lines") if isinstance(doc, dict) else None
        apply_schema(doc, "dialogue", rel_path(report, path), report, key="dialogue")
    if not isinstance(lines, dict):
        report.error("dialogue_lines", "dialogue.lines must be an object", file=rel_path(report, path), owner="A03")
        report.check("dialogue", "fail", "invalid dialogue table", owner="A03")
        return
    errors = 0
    for key, line in lines.items():
        where = f"$.lines[{key!r}]"
        if not isinstance(key, str) or not re.match(r"^[A-Za-z0-9_]+\.[A-Za-z0-9_.-]+$", key):
            report.warn("dialogue_key", f"unusual dialogue key {key!r}", file=rel_path(report, path), path=where, owner="A03")
        if not isinstance(line, dict):
            report.error("dialogue_line_shape", f"line {key} is not an object", file=rel_path(report, path), path=where, owner="A03")
            errors += 1
            continue
        text = line.get("text")
        if not isinstance(text, str) or not text.strip():
            report.error("dialogue_text", f"line {key} has empty text", file=rel_path(report, path), path=where, owner="A03")
            errors += 1
        speaker = line.get("speaker")
        if not isinstance(speaker, str) or not SLUG_RE.match(speaker):
            report.error("dialogue_speaker", f"line {key} has invalid speaker {speaker!r}", file=rel_path(report, path), path=where, owner="A03")
            errors += 1
        text_key = line.get("text_key")
        if text_key is not None and text_key != key:
            report.warn("dialogue_key_mismatch", f"line {key} text_key is {text_key!r}", file=rel_path(report, path), path=where, owner="A03")
        portrait = line.get("portrait")
        if portrait is not None and (not isinstance(portrait, str) or not portrait.strip()):
            report.error("dialogue_portrait", f"line {key} has invalid portrait", file=rel_path(report, path), path=where, owner="A03")
            errors += 1
        ctx.dialogue[key] = line

    report.check(
        "dialogue",
        "fail" if errors else "pass",
        f"{len(ctx.dialogue)} dialogue lines; {len(ctx.referenced_text_keys)} referenced by scenes",
        owner="A03",
    )


def _normalize_legacy_command(command: Any) -> Any:
    """Map A03's pre-contract lowercase command shape to FStoryCommand JSON."""
    if not isinstance(command, dict):
        return command
    raw_type = command.get("type")
    if not isinstance(raw_type, str):
        return command
    type_map = {
        "dialogue": "Dialogue",
        "choice": "Choice",
        "camera": "Camera",
        "move_npc": "MoveNpc",
        "fade": "Fade",
        "wait": "Wait",
        "banner": "Banner",
        "play_sfx": "PlaySfx",
        "music": "Music",
        "duel": "Duel",
        "reward": "Reward",
        "set_flag": "SetFlag",
        "end": "End",
    }
    if raw_type not in type_map:
        return command
    mapped = type_map[raw_type]
    out: dict[str, Any] = {"type": mapped, "_legacy": True}
    for key in ("command_id", "duration", "skippable"):
        if key in command:
            out[key] = command[key]
    if mapped == "Dialogue":
        out["speaker"] = command.get("speaker")
        out["portrait"] = command.get("portrait")
        out["text_key"] = command.get("key", command.get("text_key"))
    elif mapped == "Choice":
        out["text_key"] = command.get("key", command.get("text_key"))
        if isinstance(command.get("choices"), list):
            out["choices"] = command["choices"]
        out["args"] = command.get("args", [])
    elif mapped == "Camera":
        out["args"] = [command["anchor"]] if command.get("anchor") else command.get("args", [])
    elif mapped == "MoveNpc":
        out["args"] = [command.get("npc", ""), command.get("anchor", "")]
    elif mapped == "Fade":
        out["args"] = [command.get("mode", "out")]
    elif mapped == "Banner":
        out["args"] = [command.get("title", command.get("key", ""))]
    elif mapped == "PlaySfx":
        out["args"] = [command.get("sfx", command.get("cue", ""))]
    elif mapped == "Music":
        out["args"] = [command.get("track", "")]
    elif mapped == "Duel":
        out["args"] = [
            command.get("opponent_id", ""),
            command.get("opponent_deck_id", ""),
            command.get("mode", ""),
        ]
        if command.get("scenario_id"):
            out["args"].append(command["scenario_id"])
    elif mapped == "Reward":
        args: list[str] = []
        if isinstance(command.get("dp"), int):
            args.append(f"dp:{command['dp']}")
        if command.get("reward_id"):
            args.append(f"reward_id:{command['reward_id']}")
        out["args"] = args or command.get("args", [])
    elif mapped == "SetFlag":
        out["args"] = [command.get("flag", "")]
    elif mapped == "End":
        out["args"] = []
    else:
        out["args"] = command.get("args", [])
    return out


def validate_scenes(ctx: Context, report: Report) -> None:
    paths = glob_json(ctx.data_dir / "Story" / "scenes")
    ctx.dataset_presence["scenes"] = bool(paths)
    if not paths:
        report.gap(
            "scenes_missing",
            "no story scene files found",
            owner="A03",
            hint="expected Content/Data/Story/scenes/*.json",
        )
        report.check("scenes", "gap", "no scenes", owner="A03")
        return
    errors = 0
    seen_ids: dict[str, str] = {}
    next_scene_refs: list[tuple[str, str, str]] = []
    for path in paths:
        doc = load_json(path, report)
        if doc is None:
            errors += 1
            continue
        file_label = rel_path(report, path)
        if isinstance(doc, dict) and isinstance(doc.get("scenes"), dict):
            scene_items = list(doc["scenes"].values())
            report.warn(
                "scene_schema_drift",
                "scene bundle uses scenes{} and lowercase commands; canonical v1 is one file per scene with FStoryCommand types",
                file=file_label,
                owner="A03",
            )
        elif isinstance(doc, dict) and isinstance(doc.get("id"), str) and isinstance(doc.get("commands"), list):
            scene_items = [doc]
            apply_schema(doc, "story-scene", file_label, report, key="scenes")
        elif isinstance(doc, dict):
            scene_items = [doc]
            apply_schema(doc, "story-scene", file_label, report, key="scenes")
        else:
            report.error("scene_shape", "scene file must be an object", file=file_label, owner="A03")
            errors += 1
            continue

        for scene_index, scene in enumerate(scene_items):
            if not isinstance(scene, dict):
                report.error("scene_shape", "scene must be an object", file=file_label, owner="A03")
                errors += 1
                continue
            scene_id = scene.get("id")
            if not isinstance(scene_id, str) or not SCENE_ID_RE.match(scene_id):
                report.error("scene_id", f"invalid scene id {scene_id!r}", file=file_label, owner="A03")
                errors += 1
                continue
            if scene_id in seen_ids:
                report.error("scene_duplicate", f"duplicate scene id {scene_id} (also {seen_ids[scene_id]})", file=file_label, owner="A03")
                errors += 1
            else:
                seen_ids[scene_id] = file_label
            event_id = scene.get("event", scene.get("event_id"))
            if event_id is not None and (not isinstance(event_id, str) or not EVENT_RE.match(event_id)):
                report.error("scene_event", f"scene {scene_id} has invalid event {event_id!r}", file=file_label, owner="A03")
                errors += 1
            elif event_id is not None and ctx.events and event_id not in ctx.events:
                report.error("scene_event_ref", f"scene {scene_id} references unknown event {event_id}", file=file_label, owner="A03")
                errors += 1
            commands = scene.get("commands")
            if isinstance(commands, list):
                commands = [_normalize_legacy_command(command) for command in commands]
            errors += _validate_commands(ctx, commands, report, file=file_label, where=f"$.scenes[{scene_index}].commands", event_id=event_id, owner="A03")
            if isinstance(scene.get("commands"), list):
                for command in scene["commands"]:
                    if isinstance(command, dict) and str(command.get("type", "")).lower() == "end":
                        next_scene = command.get("next_scene")
                        if isinstance(next_scene, str) and next_scene:
                            next_scene_refs.append((scene_id, next_scene, file_label))

    for scene_id, next_scene, file_label in next_scene_refs:
        if next_scene not in seen_ids:
            report.error(
                "scene_next_ref",
                f"scene {scene_id} ends with next_scene {next_scene!r}, which is not defined",
                file=file_label,
                owner="A03",
            )
            errors += 1

    ctx.scene_ids = set(seen_ids)
    report.check("scenes", "fail" if errors else "pass", f"{len(seen_ids)} scene queues", owner="A03")


def validate_emails(ctx: Context, report: Report) -> None:
    path = ctx.data_dir / "Story" / "emails.json"
    ctx.dataset_presence["emails"] = path.exists()
    if not path.exists():
        report.gap(
            "emails_missing",
            "no PDA email table found",
            owner="A03",
            hint="expected Content/Data/Story/emails.json",
        )
        report.check("emails", "gap", "no emails", owner="A03")
        return
    doc = load_json(path, report)
    if doc is None:
        report.check("emails", "fail", "emails unreadable", owner="A03")
        return
    apply_schema(doc, "emails", rel_path(report, path), report, key="emails")
    errors = 0
    for index, email in enumerate(collection(doc, "emails")):
        where = f"$.emails[{index}]"
        file_label = rel_path(report, path)
        if not isinstance(email, dict):
            report.error("email_shape", "email must be an object", file=file_label, path=where, owner="A03")
            errors += 1
            continue
        email_id = email.get("id")
        if not isinstance(email_id, str) or not SLUG_RE.match(email_id):
            report.error("email_id", f"invalid email id {email_id!r}", file=file_label, path=where, owner="A03")
            errors += 1
            continue
        if email_id in ctx.emails:
            report.error("email_duplicate", f"duplicate email id {email_id}", file=file_label, path=where, owner="A03")
            errors += 1
            continue
        ctx.emails[email_id] = email
        sender = email.get("from")
        if not isinstance(sender, str) or not SLUG_RE.match(sender):
            report.error("email_from", f"email {email_id} has invalid sender {sender!r}", file=file_label, path=where, owner="A03")
            errors += 1
        subject = email.get("subject")
        if not isinstance(subject, str) or not subject.strip():
            report.error("email_subject", f"email {email_id} has empty subject", file=file_label, path=where, owner="A03")
            errors += 1
        if not email.get("body") and not email.get("body_key"):
            report.error("email_body", f"email {email_id} needs body or body_key", file=file_label, path=where, owner="A03")
            errors += 1
        unlock = email.get("unlock")
        if isinstance(unlock, dict):
            flag = unlock.get("flag")
            if flag is not None and (not isinstance(flag, str) or not SLUG_RE.match(flag)):
                report.error("email_unlock_flag", f"email {email_id} has invalid unlock flag {flag!r}", file=file_label, path=where, owner="A03")
                errors += 1
            event_id = unlock.get("event")
            if event_id is not None and ctx.events and event_id not in ctx.events:
                report.error("email_unlock_event", f"email {email_id} unlocks on unknown event {event_id}", file=file_label, path=where, owner="A03")
                errors += 1
            counter = unlock.get("counter")
            if counter is not None and (not isinstance(counter, str) or not SLUG_RE.match(counter)):
                report.error("email_unlock_counter", f"email {email_id} has invalid unlock counter {counter!r}", file=file_label, path=where, owner="A03")
                errors += 1
        request = email.get("duel_request")
        if isinstance(request, dict):
            if ctx.opponents and request.get("opponent") not in ctx.opponents:
                report.error("email_duel_opponent", f"email {email_id} references unknown opponent {request.get('opponent')}", file=file_label, path=where, owner="A03")
                errors += 1
            if ctx.decks and request.get("deck") not in ctx.decks:
                report.error("email_duel_deck", f"email {email_id} references unknown deck {request.get('deck')}", file=file_label, path=where, owner="A03")
                errors += 1
        attachments = email.get("attachments")
        if isinstance(attachments, dict):
            for card_id in attachments.get("cards", []) or []:
                if not valid_card_id(card_id) or (ctx.cards and card_id not in ctx.cards):
                    report.error("email_card", f"email {email_id} has invalid card attachment {card_id!r}", file=file_label, path=where, owner="A03")
                    errors += 1
            for pack_id in attachments.get("packs", []) or []:
                if not isinstance(pack_id, str) or not SLUG_RE.match(pack_id):
                    report.error("email_pack", f"email {email_id} has invalid pack attachment {pack_id!r}", file=file_label, path=where, owner="A03")
                    errors += 1
                elif ctx.packs and pack_id not in ctx.packs:
                    report.error("email_pack_ref", f"email {email_id} references unknown pack {pack_id}", file=file_label, path=where, owner="A03")
                    errors += 1
    report.check("emails", "fail" if errors else "pass", f"{len(ctx.emails)} emails", owner="A03")


def validate_schedules(ctx: Context, report: Report) -> None:
    candidates = [ctx.data_dir / "Story" / "schedules.json"]
    candidates.extend(glob_json(ctx.data_dir / "Story" / "schedules"))
    path = first_existing(candidates)
    ctx.dataset_presence["schedules"] = path is not None
    if path is None:
        report.gap(
            "schedules_missing",
            "no NPC schedule table found",
            owner="A03",
            hint="expected Content/Data/Story/schedules.json",
        )
        report.check("schedules", "gap", "no schedules", owner="A03")
        return
    doc = load_json(path, report)
    if doc is None:
        report.check("schedules", "fail", "schedules unreadable", owner="A03")
        return
    if isinstance(doc, dict) and isinstance(doc.get("npcs"), dict):
        schedule_items = list(doc["npcs"].values())
        report.warn(
            "schedule_schema_drift",
            "schedules use npcs{} with periods[]; canonical v1 is schedules[] with period",
            file=rel_path(report, path),
            owner="A03",
        )
    else:
        schedule_items = collection(doc, "schedules")
        apply_schema(doc, "schedules", rel_path(report, path), report, key="schedules")
    errors = 0
    seen_slots: dict[tuple[str, str, str], str] = {}
    for index, schedule in enumerate(schedule_items):
        where = f"$.schedules[{index}]"
        file_label = rel_path(report, path)
        if not isinstance(schedule, dict):
            report.error("schedule_shape", "schedule must be an object", file=file_label, path=where, owner="A03")
            errors += 1
            continue
        schedule_id = schedule.get("id", schedule.get("speaker_id"))
        if not isinstance(schedule_id, str) or not SLUG_RE.match(schedule_id):
            report.error("schedule_id", f"invalid schedule id {schedule_id!r}", file=file_label, path=where, owner="A03")
            errors += 1
            continue
        if schedule_id in ctx.schedules:
            report.error("schedule_duplicate", f"duplicate schedule id {schedule_id}", file=file_label, path=where, owner="A03")
            errors += 1
            continue
        ctx.schedules[schedule_id] = schedule
        npc = schedule.get("npc", schedule.get("speaker_id"))
        if not isinstance(npc, str) or not SLUG_RE.match(npc):
            report.error("schedule_npc", f"schedule {schedule_id} has invalid npc {npc!r}", file=file_label, path=where, owner="A03")
            errors += 1
        entries = schedule.get("entries")
        if not isinstance(entries, list) or not entries:
            report.error("schedule_entries", f"schedule {schedule_id} has no entries", file=file_label, path=where, owner="A03")
            errors += 1
            entries = []
        for eindex, entry in enumerate(entries):
            ewhere = f"{where}.entries[{eindex}]"
            if not isinstance(entry, dict):
                report.error("schedule_entry_shape", "schedule entry must be an object", file=file_label, path=ewhere, owner="A03")
                errors += 1
                continue
            weekdays = entry.get("weekdays")
            raw_periods = entry.get("periods", entry.get("period"))
            if isinstance(raw_periods, str):
                periods = [raw_periods]
            elif isinstance(raw_periods, list):
                periods = raw_periods
            else:
                periods = []
            if not isinstance(weekdays, list) or not weekdays:
                report.error("schedule_weekdays", f"schedule {schedule_id} entry needs weekdays", file=file_label, path=ewhere, owner="A03")
                errors += 1
                weekdays = []
            for weekday in weekdays:
                if weekday not in WEEKDAYS and weekday != "all":
                    report.error("schedule_weekday", f"schedule {schedule_id} has invalid weekday {weekday!r}", file=file_label, path=ewhere, owner="A03")
                    errors += 1
            if not periods:
                report.error("schedule_period", f"schedule {schedule_id} has no period/periods", file=file_label, path=ewhere, owner="A03")
                errors += 1
            for period in periods:
                if period not in PERIODS:
                    report.error("schedule_period", f"schedule {schedule_id} has invalid period {period!r}", file=file_label, path=ewhere, owner="A03")
                    errors += 1
            errors += _check_location_ref(ctx, entry.get("location"), report, file_label, ewhere, "A03")
            errors += _check_anchor_ref(ctx, entry.get("anchor"), report, file_label, ewhere, "A03")
            if isinstance(npc, str):
                for weekday in weekdays:
                    for period in periods:
                        key = (npc, weekday, str(period))
                        if key in seen_slots:
                            report.warn(
                                "schedule_overlap",
                                f"{npc} has overlapping {weekday}/{period} entries in {schedule_id} and {seen_slots[key]}",
                                file=file_label,
                                path=ewhere,
                                owner="A03",
                            )
                        else:
                            seen_slots[key] = schedule_id
        overrides = schedule.get("overrides", schedule.get("date_overrides", []))
        for oindex, override in enumerate(overrides if isinstance(overrides, list) else []):
            owhere = f"{where}.overrides[{oindex}]"
            if not isinstance(override, dict):
                errors += 1
                continue
            event_id = override.get("event", override.get("event_id"))
            if not isinstance(event_id, str) or not EVENT_RE.match(event_id):
                report.error("schedule_override_event", f"schedule {schedule_id} has invalid override event {event_id!r}", file=file_label, path=owhere, owner="A03")
                errors += 1
            elif ctx.events and event_id not in ctx.events:
                report.error("schedule_override_ref", f"schedule {schedule_id} override references unknown event {event_id}", file=file_label, path=owhere, owner="A03")
                errors += 1
            errors += _check_location_ref(ctx, override.get("location"), report, file_label, owhere, "A03")
            errors += _check_anchor_ref(ctx, override.get("anchor"), report, file_label, owhere, "A03")

    for opponent_id, opponent in ctx.opponents.items():
        schedule_id = opponent.get("schedule")
        if isinstance(schedule_id, str) and schedule_id and schedule_id not in ctx.schedules:
            report.error(
                "opponent_schedule_ref",
                f"opponent {opponent_id} references missing schedule {schedule_id}",
                file=rel_path(report, path),
                owner="A07",
            )
            errors += 1
        if not isinstance(schedule_id, (str, list)) and not opponent.get("event_only") and not opponent.get("locations"):
            report.warn(
                "opponent_schedule_missing",
                f"opponent {opponent_id} has no schedule and is not event_only",
                file=rel_path(report, path),
                owner="A07",
            )
    report.check("schedules", "fail" if errors else "pass", f"{len(ctx.schedules)} schedules", owner="A03")


# ---------------------------------------------------------------------------
# Effects and saves
# ---------------------------------------------------------------------------


def _effect_path(ctx: Context, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw
    text = value.replace("\\", "/")
    if text.startswith("Effects/"):
        return ctx.data_dir / text
    return ctx.data_dir / "Effects" / text


def validate_effects(ctx: Context, report: Report) -> None:
    path = ctx.data_dir / "Effects" / "manifest.json"
    ctx.dataset_presence["effects"] = path.exists()
    if not path.exists():
        report.gap(
            "effects_missing",
            "no effect coverage manifest found",
            owner="A05",
            hint="expected Content/Data/Effects/manifest.json with one entry per card",
        )
        report.check("effects", "gap", "no effect manifest", owner="A05")
        return
    doc = load_json(path, report)
    if doc is None:
        report.check("effects", "fail", "effect manifest unreadable", owner="A05")
        return
    apply_schema(doc, "effects", rel_path(report, path), report, key="effects")

    entries = doc.get("entries") if isinstance(doc, dict) else None
    if not isinstance(entries, list):
        report.error("effects_entries", "manifest.entries must be an array", file=rel_path(report, path), owner="A05")
        report.check("effects", "fail", "invalid manifest", owner="A05")
        return

    errors = 0
    statuses: collections.Counter[str] = collections.Counter()
    referenced_scripts: set[str] = set()
    for index, entry in enumerate(entries):
        where = f"$.entries[{index}]"
        file_label = rel_path(report, path)
        if not isinstance(entry, dict):
            report.error("effect_entry_shape", "manifest entry must be an object", file=file_label, path=where, owner="A05")
            errors += 1
            continue
        card_id = entry.get("card_id")
        if not valid_card_id(card_id):
            report.error("effect_card_id", f"invalid manifest card id {card_id!r}", file=file_label, path=where, owner="A05")
            errors += 1
            continue
        if card_id in ctx.effect_manifest:
            report.error("effect_duplicate", f"duplicate manifest entry for card {card_id}", file=file_label, path=where, owner="A05")
            errors += 1
            continue
        ctx.effect_manifest[card_id] = entry
        status = entry.get("status")
        if status not in EFFECT_STATUSES:
            report.error("effect_status", f"card {card_id} has invalid status {status!r}", file=file_label, path=where, owner="A05")
            errors += 1
            continue
        statuses[status] += 1
        if status == "unsupported":
            reason = entry.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                report.error("effect_reason", f"unsupported card {card_id} needs a reason", file=file_label, path=where, owner="A05")
                errors += 1
            ctx.unsupported_cards.add(card_id)
        elif status == "scripted":
            script = entry.get("script")
            if not isinstance(script, str) or not script.endswith(".json"):
                report.error("effect_script_missing", f"scripted card {card_id} needs a script path", file=file_label, path=where, owner="A05")
                errors += 1
            else:
                script_file = _effect_path(ctx, script)
                referenced_scripts.add(rel_path(report, script_file))
                if not script_file.exists():
                    report.error("effect_script_file", f"card {card_id} script not found: {script}", file=file_label, path=where, owner="A05")
                    errors += 1
        elif status == "vanilla" and entry.get("script"):
            report.warn("effect_vanilla_script", f"vanilla card {card_id} declares a script", file=file_label, path=where, owner="A05")

    missing = [card_id for card_id in range(1, 1201) if card_id not in ctx.effect_manifest]
    if missing:
        sample = ", ".join(str(card_id) for card_id in missing[:20])
        report.gap(
            "effect_coverage",
            f"{len(missing)} card(s) have no manifest entry: {sample}{' ...' if len(missing) > 20 else ''}",
            file=rel_path(report, path),
            owner="A05",
            hint="one entry per card 1..1200 is a release requirement",
        )

    # Scripts are validated whether or not the manifest points at them, so an
    # orphan script does not hide a schema error.
    script_dir = ctx.data_dir / "Effects"
    for script_file in glob_json(script_dir) + glob_json(script_dir / "scripts"):
        if script_file.name in {"manifest.json", "schema.json", "tier1_cards.json", "fusion_candidates.json"}:
            continue
        script_rel = rel_path(report, script_file)
        if script_rel not in referenced_scripts:
            report.warn(
                "effect_orphan_script",
                f"effect script not referenced by manifest: {script_file.name}",
                file=script_rel,
                owner="A05",
            )
        script_doc = load_json(script_file, report)
        if script_doc is None:
            errors += 1
            continue
        if isinstance(script_doc, dict) and isinstance(script_doc.get("scripts"), list):
            report.warn(
                "effect_script_schema_drift",
                "effect script uses scripts[]; canonical v1 uses top-level operations[]",
                file=script_rel,
                owner="A05",
            )
            operations = []
            for sub in script_doc["scripts"]:
                if isinstance(sub, dict) and isinstance(sub.get("operations"), list):
                    operations.extend(sub["operations"])
        else:
            apply_schema(script_doc, "effect-script", script_rel, report, key="effect_scripts")
            operations = script_doc.get("operations") if isinstance(script_doc, dict) else None
        if not isinstance(script_doc, dict):
            errors += 1
            continue
        script_card_id = script_doc.get("card_id")
        if not valid_card_id(script_card_id):
            report.error("effect_script_card", f"script {script_file.name} has invalid card_id {script_card_id!r}", file=script_rel, owner="A05")
            errors += 1
        elif script_file.stem.isdigit() and int(script_file.stem) != script_card_id:
            report.error(
                "effect_script_name",
                f"script filename {script_file.name} does not match card_id {script_card_id}",
                file=script_rel,
                owner="A05",
            )
            errors += 1
        if not isinstance(operations, list) or not operations:
            report.error("effect_operations", f"script {script_file.name} has no operations", file=script_rel, owner="A05")
            errors += 1

    if len(ctx.effect_manifest) != 1200:
        report.gap(
            "effect_manifest_count",
            f"{len(ctx.effect_manifest)}/1200 cards in the effect manifest",
            file=rel_path(report, path),
            owner="A05",
        )
    if statuses:
        report.info(
            "effect_status_counts",
            f"scripted={statuses['scripted']}, vanilla={statuses['vanilla']}, unsupported={statuses['unsupported']}",
            file=rel_path(report, path),
            owner="A05",
        )
    report.check(
        "effects",
        "fail" if errors else ("gap" if missing or len(ctx.effect_manifest) != 1200 else "pass"),
        f"{len(ctx.effect_manifest)} manifest entries; scripted={statuses['scripted']}, vanilla={statuses['vanilla']}, unsupported={statuses['unsupported']}",
        owner="A05",
    )


def _validate_save_semantics(
    ctx: Context, save: Any, report: Report, *, file: str
) -> int:
    if not isinstance(save, dict):
        report.error("save_shape", "save must be an object", file=file, owner="A02")
        return 1
    errors = 0
    if save.get("version") != 1:
        report.error("save_version", f"unsupported save version {save.get('version')!r}", file=file, owner="A02")
        errors += 1
    slot = save.get("slot")
    if not isinstance(slot, int) or isinstance(slot, bool) or not (0 <= slot <= 3):
        report.error("save_slot", f"invalid save slot {slot!r}", file=file, owner="A02")
        errors += 1
    profile = save.get("profile")
    if not isinstance(profile, dict):
        report.error("save_profile", "save.profile must be an object", file=file, owner="A02")
        errors += 1
    else:
        if not isinstance(profile.get("name"), str) or not profile["name"].strip():
            report.error("save_profile_name", "save profile name is empty", file=file, owner="A02")
            errors += 1
        if profile.get("dorm") not in DORMS:
            report.error("save_profile_dorm", f"invalid save dorm {profile.get('dorm')!r}", file=file, owner="A02")
            errors += 1
        if not isinstance(profile.get("dp"), int) or isinstance(profile.get("dp"), bool) or profile["dp"] < 0:
            report.error("save_profile_dp", f"invalid save DP {profile.get('dp')!r}", file=file, owner="A02")
            errors += 1
    calendar = save.get("calendar")
    if not isinstance(calendar, dict):
        report.error("save_calendar", "save.calendar must be an object", file=file, owner="A02")
        errors += 1
    else:
        month = calendar.get("month")
        month_index = calendar.get("month_index")
        day = calendar.get("day")
        period = calendar.get("period")
        if month is None and month_index is None:
            report.error("save_calendar_month", "calendar needs month or month_index", file=file, owner="A02")
            errors += 1
        if month is not None and (not isinstance(month, int) or not (1 <= month <= 12)):
            report.error("save_calendar_month", f"invalid calendar month {month!r}", file=file, owner="A02")
            errors += 1
        if month_index is not None and (not isinstance(month_index, int) or not (0 <= month_index <= 11)):
            report.error("save_calendar_month_index", f"invalid calendar month_index {month_index!r}", file=file, owner="A02")
            errors += 1
        if not isinstance(day, int) or not (1 <= day <= 31):
            report.error("save_calendar_day", f"invalid calendar day {day!r}", file=file, owner="A02")
            errors += 1
        if period not in PERIODS:
            report.error("save_calendar_period", f"invalid calendar period {period!r}", file=file, owner="A02")
            errors += 1
    inventory = save.get("inventory")
    if not isinstance(inventory, dict):
        report.error("save_inventory", "save.inventory must be an object", file=file, owner="A02")
        errors += 1
    else:
        # A02's runtime provider separates counts from metadata.
        if isinstance(inventory.get("counts"), dict):
            inventory = inventory["counts"]
        for key, count in inventory.items():
            if not CARD_KEY_RE.match(str(key)):
                report.error("save_inventory_key", f"invalid inventory card key {key!r}", file=file, owner="A02")
                errors += 1
                continue
            card_id = int(key)
            if not valid_card_id(card_id) or (ctx.cards and card_id not in ctx.cards):
                report.error("save_inventory_card", f"inventory references invalid card {card_id}", file=file, owner="A02")
                errors += 1
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                report.error("save_inventory_count", f"inventory card {card_id} has invalid count {count!r}", file=file, owner="A02")
                errors += 1
    decks = save.get("decks", [])
    if isinstance(decks, dict) and isinstance(decks.get("decks"), list):
        decks = decks["decks"]
    if not isinstance(decks, list):
        report.error("save_decks", "save.decks must be an array", file=file, owner="A02")
        errors += 1
    else:
        deck_ids: set[str] = set()
        for index, deck in enumerate(decks):
            if not isinstance(deck, dict):
                errors += 1
                continue
            deck_id = deck.get("id")
            if not isinstance(deck_id, str) or not SLUG_RE.match(deck_id):
                report.error("save_deck_id", f"invalid save deck id {deck_id!r}", file=file, owner="A02")
                errors += 1
                continue
            if deck_id in deck_ids:
                report.error("save_deck_duplicate", f"duplicate save deck id {deck_id}", file=file, owner="A02")
                errors += 1
            deck_ids.add(deck_id)
            main = deck.get("main", [])
            extra = deck.get("extra", [])
            side = deck.get("side", [])
            for label, values in (("main", main), ("extra", extra), ("side", side)):
                if not isinstance(values, list):
                    errors += 1
                    continue
                for card_id in values:
                    if not valid_card_id(card_id) or (ctx.cards and card_id not in ctx.cards):
                        report.error("save_deck_card", f"save deck {deck_id} has invalid card {card_id!r} in {label}", file=file, owner="A02")
                        errors += 1
            if isinstance(main, list) and not (40 <= len(main) <= 60):
                report.error("save_deck_size", f"save deck {deck_id} main size {len(main)} is outside 40..60", file=file, owner="A02")
                errors += 1
            if isinstance(extra, list) and len(extra) > 20:
                report.error("save_deck_extra", f"save deck {deck_id} extra size {len(extra)} exceeds 20", file=file, owner="A02")
                errors += 1
            if isinstance(side, list) and len(side) > 15:
                report.error("save_deck_side", f"save deck {deck_id} side size {len(side)} exceeds 15", file=file, owner="A02")
                errors += 1
            all_ids: list[int] = []
            for values in (main, extra, side):
                if isinstance(values, list):
                    all_ids.extend(v for v in values if valid_card_id(v))
            for card_id, count in collections.Counter(all_ids).items():
                if count > 3:
                    report.error("save_deck_copies", f"save deck {deck_id} has {count} copies of card {card_id}", file=file, owner="A02")
                    errors += 1
                if card_id in ctx.limitations["forbidden"]:
                    report.error("save_deck_forbidden", f"save deck {deck_id} contains forbidden card {card_id}", file=file, owner="A02")
                    errors += 1
                elif card_id in ctx.limitations["limited"] and count > 1:
                    report.error("save_deck_limited", f"save deck {deck_id} has {count} copies of limited card {card_id}", file=file, owner="A02")
                    errors += 1
                elif card_id in ctx.limitations["semi_limited"] and count > 2:
                    report.error("save_deck_semi", f"save deck {deck_id} has {count} copies of semi-limited card {card_id}", file=file, owner="A02")
                    errors += 1
    events = save.get("events")
    if isinstance(events, dict):
        for event_id, state in events.items():
            if not EVENT_RE.match(str(event_id)):
                report.error("save_event_id", f"invalid event id {event_id!r} in save", file=file, owner="A02")
                errors += 1
            if state not in EVENT_STATES:
                report.error("save_event_state", f"event {event_id} has invalid state {state!r}", file=file, owner="A02")
                errors += 1
    exams = save.get("exams")
    if isinstance(exams, list):
        months: set[int] = set()
        for exam in exams:
            if not isinstance(exam, dict):
                errors += 1
                continue
            month = exam.get("month")
            if not isinstance(month, int) or not (1 <= month <= 12):
                report.error("save_exam_month", f"invalid exam month {month!r} in save", file=file, owner="A02")
                errors += 1
            elif month in months:
                report.error("save_exam_duplicate", f"duplicate exam month {month} in save", file=file, owner="A02")
                errors += 1
            else:
                months.add(month)
            written = exam.get("written")
            if not isinstance(written, int) or not (0 <= written <= 10):
                report.error("save_exam_written", f"invalid written score {written!r}", file=file, owner="A02")
                errors += 1
            practical = exam.get("practical")
            if not isinstance(practical, int) or not (0 <= practical <= 500):
                report.error("save_exam_practical", f"invalid practical score {practical!r}", file=file, owner="A02")
                errors += 1
    return errors


def validate_saves(ctx: Context, report: Report) -> None:
    saves_dir = ctx.data_dir / "Integration" / "saves"
    paths = glob_json(saves_dir)
    if not paths:
        report.gap(
            "saves_missing",
            "no golden save fixtures found",
            owner="A10",
            hint="expected Content/Data/Integration/saves/*.json",
        )
        report.check("saves", "gap", "no save fixtures", owner="A10")
        return
    errors = 0
    for path in paths:
        doc = load_json(path, report)
        if doc is None:
            errors += 1
            continue
        apply_schema(doc, "save.v1", rel_path(report, path), report, key="saves")
        errors += _validate_save_semantics(ctx, doc, report, file=rel_path(report, path))
    report.check("saves", "fail" if errors else "pass", f"{len(paths)} save fixture(s)", owner="A02")


# ---------------------------------------------------------------------------
# Cross-data checks
# ---------------------------------------------------------------------------


def load_save_defaults(ctx: Context, report: Report) -> None:
    path = first_existing(
        [
            ctx.data_dir / "Profile" / "save_defaults.json",
            ctx.data_dir / "Story" / "initial_flags.json",
        ]
    )
    if path is None:
        return
    doc = load_json(path, report)
    if not isinstance(doc, dict):
        return
    flags = doc.get("flags", {})
    if isinstance(flags, dict):
        ctx.written_flags.update(str(key) for key in flags)
    counters = doc.get("counters", {})
    if isinstance(counters, dict):
        ctx.written_counters.update(str(key) for key in counters)


def cross_check(ctx: Context, report: Report) -> None:
    load_save_defaults(ctx, report)

    if ctx.missing_anchors:
        missing = sorted(ctx.missing_anchors)
        report.gap(
            "anchor_coverage",
            f"{len(missing)} anchor id(s) referenced by story/schedules are missing from World/anchors.json: {', '.join(missing[:12])}{' ...' if len(missing) > 12 else ''}",
            owner="A08",
            hint="publish the anchors or retarget the scene/schedule references before Gate 1",
        )
    if ctx.missing_locations:
        missing = sorted(ctx.missing_locations)
        report.gap(
            "location_coverage",
            f"{len(missing)} location id(s) referenced by story/schedules are missing from World/anchors.json: {', '.join(missing[:12])}{' ...' if len(missing) > 12 else ''}",
            owner="A08",
        )

    if ctx.effect_manifest:
        for label, cards in (
            ("deck", ctx.deck_cards),
            ("pack", ctx.pack_cards),
            ("puzzle", ctx.puzzle_cards),
        ):
            bad = sorted(set(cards) & ctx.unsupported_cards)
            if bad:
                report.error(
                    "unsupported_card_in_content",
                    f"{label}(s) contain unsupported card(s): {bad[:20]}",
                    owner="A05/A06/A07",
                    hint="script the card or remove it from obtainable content before release",
                )

    if ctx.packs:
        available = ctx.pack_cards | ctx.reward_cards
        missing = [card_id for card_id in range(1, 1201) if card_id not in available]
        if missing:
            report.gap(
                "card_obtainability",
                f"{len(missing)}/1200 cards are not in any pack or event reward (sample: {missing[:20]})",
                owner="A01/A06",
                hint="every card must be obtainable from a pack or event; fill pools/rewards",
            )
        else:
            report.info("card_obtainability", "all 1200 cards are obtainable from packs/rewards", owner="A06")
        # Packs may unlock on events; events load after packs, so re-check here.
        for pack_id, pack in ctx.packs.items():
            unlock = pack.get("unlock")
            if isinstance(unlock, dict):
                event_id = unlock.get("event")
                if event_id and ctx.events and event_id not in ctx.events:
                    report.error(
                        "pack_unlock_event_ref",
                        f"pack {pack_id} unlocks on unknown event {event_id}",
                        owner="A06",
                    )

    if ctx.events:
        unknown_flags = sorted(ctx.read_flags - ctx.written_flags)
        if unknown_flags:
            report.warn(
                "flag_unwritten",
                f"{len(unknown_flags)} flag(s) are read but never written by events/defaults: {unknown_flags[:20]}",
                owner="A03/A02",
                hint="check initial flags, exam/title/duel outcomes and event rewards",
            )
        unknown_counters = sorted(ctx.read_counters - ctx.written_counters)
        if unknown_counters:
            report.warn(
                "counter_unwritten",
                f"{len(unknown_counters)} counter(s) are read but never written: {unknown_counters[:20]}",
                owner="A03/A02",
            )

    if ctx.opponents and ctx.emails:
        for opponent_id, opponent in ctx.opponents.items():
            request = opponent.get("duel_request")
            if isinstance(request, dict):
                email_id = request.get("email")
                if email_id and email_id not in ctx.emails:
                    report.error(
                        "duel_request_email_ref",
                        f"opponent {opponent_id} references missing email {email_id}",
                        owner="A07/A03",
                    )

    if ctx.events and ctx.emails:
        for email_id, email in ctx.emails.items():
            unlock = email.get("unlock")
            if isinstance(unlock, dict):
                event_id = unlock.get("event")
                if event_id and event_id not in ctx.events:
                    report.error(
                        "email_event_ref",
                        f"email {email_id} unlocks on unknown event {event_id}",
                        owner="A03",
                    )

    if ctx.events:
        for event_id, event in ctx.events.items():
            for choice in event.get("choices", []) or []:
                if not isinstance(choice, dict):
                    continue
                next_event = choice.get("next_event")
                if next_event and next_event not in ctx.events:
                    report.error(
                        "choice_next_ref",
                        f"event {event_id} choice {choice.get('id')} points at unknown event {next_event}",
                        owner="A03",
                    )
            on_complete = event.get("on_complete")
            if isinstance(on_complete, dict):
                next_event = on_complete.get("next_event")
                if next_event and next_event not in ctx.events:
                    report.error(
                        "event_next_ref",
                        f"event {event_id} on_complete points at unknown event {next_event}",
                        owner="A03",
                    )

    if ctx.portals:
        endpoints = {(p.get("from"), p.get("to")) for p in ctx.portals if isinstance(p, dict)}
        for portal in ctx.portals:
            if not isinstance(portal, dict) or portal.get("bidirectional") is False:
                continue
            reverse = (portal.get("to"), portal.get("from"))
            if reverse not in endpoints:
                report.warn(
                    "portal_no_return",
                    f"portal {portal.get('id')} has no reverse portal",
                    owner="A08",
                )

    if ctx.puzzles:
        for puzzle_id, puzzle in ctx.puzzles.items():
            deck_id = puzzle.get("opponent_deck")
            if deck_id and ctx.decks and deck_id not in ctx.decks:
                report.error(
                    "puzzle_deck_ref",
                    f"puzzle {puzzle_id} references unknown opponent deck {deck_id}",
                    owner="A07",
                )

    # Cross-check the scene refs recorded by events, so a scene moved without
    # updating events is caught even if the file still exists elsewhere.
    for event_id, scene_rel in ctx.scene_refs.items():
        if not (ctx.root / scene_rel).exists():
            report.error("event_scene_link", f"event {event_id} scene {scene_rel} is missing", owner="A03")
    for event_id, scene_id, file_label in ctx.legacy_scene_refs:
        if ctx.scene_ids and scene_id not in ctx.scene_ids:
            report.error(
                "event_scene_id_ref",
                f"event {event_id} references unknown scene id {scene_id!r}",
                file=file_label,
                owner="A03",
            )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def print_report(report: Report, *, verbose: bool = False, json_output: bool = False) -> None:
    if json_output:
        print(json.dumps(report.as_dict(), indent=2, ensure_ascii=False))
        return
    counts = report.counts()
    print(f"Duel Academy port validation (validate_all {TOOL_VERSION})")
    print(f"  root:      {report.root}")
    print(f"  data:      {report.data_dir}")
    print(f"  contracts: {report.contracts_dir}")
    print()
    for check in report.checks:
        if check.status in {"fail", "gap", "warn"} or verbose:
            marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL", "gap": "GAP ", "info": "INFO"}[check.status]
            owner = f" [{check.owner}]" if check.owner else ""
            print(f"  {marker} {check.key}: {check.summary}{owner}")
    print()
    visible = [f for f in report.findings if f.level != "info" or verbose]
    if visible:
        print("Findings:")
        for finding in visible:
            location = finding.file or ""
            if finding.path:
                location = f"{location} {finding.path}".strip()
            owner = f" [{finding.owner}]" if finding.owner else ""
            print(f"  {finding.level.upper():7} {finding.code}: {finding.message}{owner}")
            if location:
                print(f"          at {location}")
            if finding.hint and (finding.level in {"error", "gap"} or verbose):
                print(f"          hint: {finding.hint}")
        print()
    print(
        "Summary: "
        f"{counts['error']} error(s), {counts['warning']} warning(s), "
        f"{counts['gap']} gap(s), {counts['info']} info; "
        f"{len(report.files_read)} file(s) read"
    )
    print(f"Result: {report.result()}")
    if report.strict:
        print("  (strict mode: warnings and gaps fail the run)")
    elif report.fail_on_gaps:
        print("  (--fail-on-gaps: gaps fail the run)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate Duel Academy port data against Docs/Contracts.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT, help="repository root")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Content/Data directory (default: <root>/DuelAcademyIsland/Content/Data)",
    )
    parser.add_argument(
        "--contracts-dir",
        type=Path,
        default=None,
        help="contracts directory (default: <root>/Docs/Contracts)",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings and gaps as failures")
    parser.add_argument("--fail-on-gaps", action="store_true", help="treat gaps as failures")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--report", type=Path, default=None, help="write a JSON report to this path")
    parser.add_argument("--verbose", action="store_true", help="show info and passing checks")
    parser.add_argument("--version", action="version", version=f"validate_all {TOOL_VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = args.root.resolve()
    data_dir = (args.data_dir or (root / "DuelAcademyIsland" / "Content" / "Data")).resolve()
    contracts_dir = (args.contracts_dir or (root / "Docs" / "Contracts")).resolve()
    if not root.exists():
        print(f"error: root does not exist: {root}", file=sys.stderr)
        return 2
    if not data_dir.exists():
        print(f"warning: data directory does not exist: {data_dir}", file=sys.stderr)

    report = Report(
        root=root,
        data_dir=data_dir,
        contracts_dir=contracts_dir,
        strict=args.strict,
        fail_on_gaps=args.fail_on_gaps,
    )
    ctx = make_context(root, data_dir, contracts_dir)

    try:
        validate_cards(ctx, report)
        validate_canon_reference(ctx, report)
        validate_fusions(ctx, report)
        validate_decks(ctx, report)
        validate_limitations(ctx, report)
        validate_packs(ctx, report)
        validate_opponents(ctx, report)
        validate_puzzles(ctx, report)
        validate_exams(ctx, report)
        validate_anchors(ctx, report)
        validate_events(ctx, report)
        validate_dialogue(ctx, report)
        validate_scenes(ctx, report)
        validate_emails(ctx, report)
        validate_schedules(ctx, report)
        validate_effects(ctx, report)
        validate_saves(ctx, report)
        cross_check(ctx, report)
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        report.error("internal_error", f"{type(exc).__name__}: {exc}", owner="A10")
        if "--debug" in (argv or sys.argv):
            raise

    print_report(report, verbose=args.verbose, json_output=args.json)

    if args.report:
        report_path = args.report
        if not report_path.is_absolute():
            report_path = root / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report.as_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if not args.json:
            print(f"Report: {report_path}")

    return 0 if report.result() == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
