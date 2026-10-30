#!/usr/bin/env python3
"""Validate the Duel Academy opponent/AI/exam/puzzle data.

Usage:
    python Tools/puzzles/validate.py
    python Tools/puzzles/validate.py --report Docs/Opponents_Validation_Report.md
    python Tools/puzzles/validate.py --strict-warnings

Exit code 0 = PASS, 1 = FAIL. Warnings do not fail unless --strict-warnings.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from collections import Counter, defaultdict

ROOT_DEFAULT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
CARD_MIN, CARD_MAX = 1, 1200
DUELIST_ROLES = {"ranked", "staff", "event", "exam"}
DORMS = {"Slifer", "Ra", "Obelisk", "Staff", "Event", "Exam"}
PERIODS = {"AM", "PM", "Night"}
WEEKDAYS = {"Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"}
PUZZLE_ACTIONS = {
    "normal_summon", "special_summon", "set_monster", "activate_spell", "set_spell_trap",
    "activate_trap", "activate_effect", "attack", "change_position", "discard", "end_turn",
}
AI_STRATEGIES = {
    "beatdown", "burn", "stall", "fusion", "ritual", "control", "draw", "goblin", "machine",
    "fairy", "dragon", "warrior", "beast", "insect", "rock", "spellcaster", "aquatic", "cyber",
    "ojama", "ancient_gear", "amazoness", "copycat", "toon", "dinosaur", "shadow", "exodia",
    "exam_stall",
}


class Validator:
    def __init__(self, root: str):
        self.root = root
        self.checks = 0
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.sections: list[tuple[str, bool, str]] = []

    def ok(self, label: str, detail: str = "") -> None:
        self.checks += 1
        self.sections.append((label, True, detail))

    def fail(self, label: str, detail: str) -> None:
        self.checks += 1
        self.failures.append(f"{label}: {detail}")
        self.sections.append((label, False, detail))

    def warn(self, label: str, detail: str) -> None:
        self.warnings.append(f"{label}: {detail}")

    def require(self, condition: bool, label: str, detail: str) -> bool:
        if condition:
            self.ok(label, detail)
            return True
        self.fail(label, detail)
        return False


def load_json(path: str) -> object:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def data_path(root: str, *parts: str) -> str:
    return os.path.join(root, "DuelAcademyIsland", "Content", "Data", *parts)


def is_fusion(card: dict) -> bool:
    return "Fusion" in card.get("card_type", "")


def validate_cards(v: Validator, root: str) -> tuple[dict[int, dict], dict[str, int]]:
    path = data_path(root, "cards.json")
    cards = load_json(path)
    v.require(isinstance(cards, list), "cards.json", "root is an array")
    by_id: dict[int, dict] = {}
    names: dict[str, list[int]] = defaultdict(list)
    for card in cards:
        cid = card.get("id")
        if not isinstance(cid, int) or not (CARD_MIN <= cid <= CARD_MAX):
            v.fail("cards.json", f"invalid card id {cid!r}")
            continue
        if cid in by_id:
            v.fail("cards.json", f"duplicate card id {cid}")
        by_id[cid] = card
        names[card.get("name", "")].append(cid)
    v.require(len(by_id) == 1200, "cards.json", f"loaded {len(by_id)} cards")
    dup_names = {name: ids for name, ids in names.items() if len(ids) > 1}
    if dup_names:
        v.warn("cards.json", f"{len(dup_names)} duplicate card names (copy-limit by name still enforced)")
    return by_id, {name: len(ids) for name, ids in names.items()}


def validate_decks(v: Validator, root: str, cards: dict[int, dict], names: dict[str, int],
                   roster: dict | None) -> tuple[list[dict], dict[str, dict]]:
    decks_dir = data_path(root, "Opponents", "decks")
    files = sorted(f for f in os.listdir(decks_dir) if f.endswith(".json"))
    v.require(len(files) > 0, "decks", f"found {len(files)} deck files")
    decks: list[dict] = []
    by_id: dict[str, dict] = {}
    roster_deck_ids = set()
    if roster:
        for duelist in roster.get("duelists", []):
            roster_deck_ids.update(duelist.get("decks", []))
            if duelist.get("default_deck"):
                roster_deck_ids.add(duelist["default_deck"])

    for filename in files:
        path = os.path.join(decks_dir, filename)
        try:
            deck = load_json(path)
        except Exception as exc:  # noqa: BLE001 - report malformed content
            v.fail("decks", f"{filename}: {exc}")
            continue
        deck_id = deck.get("id")
        if deck_id != os.path.splitext(filename)[0]:
            v.fail("decks", f"{filename}: id {deck_id!r} does not match filename")
        if deck_id in by_id:
            v.fail("decks", f"duplicate deck id {deck_id!r}")
        by_id[deck_id] = deck
        decks.append(deck)

        main = deck.get("cards", [])
        extra = deck.get("extra", [])
        side = deck.get("side", [])
        v.require(isinstance(main, list), f"deck {deck_id}", "cards is an array")
        v.require(40 <= len(main) <= 60, f"deck {deck_id}", f"main deck size {len(main)} (need 40-60)")
        v.require(len(extra) <= 20, f"deck {deck_id}", f"extra deck size {len(extra)} (max 20)")
        v.require(len(side) <= 15, f"deck {deck_id}", f"side deck size {len(side)} (max 15)")

        id_counts = Counter(main + extra + side)
        name_counts: Counter[str] = Counter()
        for cid in main + extra + side:
            if not isinstance(cid, int) or cid not in cards:
                v.fail(f"deck {deck_id}", f"unknown card id {cid!r}")
                continue
            name_counts[cards[cid]["name"]] += 1
        for cid, count in id_counts.items():
            if count > 3:
                v.fail(f"deck {deck_id}", f"card id {cid} appears {count} times (max 3)")
        for name, count in name_counts.items():
            if count > 3:
                v.fail(f"deck {deck_id}", f"card name {name!r} appears {count} times (max 3)")

        for cid in main:
            if isinstance(cid, int) and cid in cards and is_fusion(cards[cid]):
                v.fail(f"deck {deck_id}", f"Fusion Monster {cid} is in the main deck")
        for cid in extra:
            if isinstance(cid, int) and cid in cards and not is_fusion(cards[cid]):
                v.fail(f"deck {deck_id}", f"non-Fusion card {cid} is in the extra deck")

        if not deck.get("confidence"):
            v.warn(f"deck {deck_id}", "missing confidence field")
        if not deck.get("source"):
            v.warn(f"deck {deck_id}", "missing source field")
        if roster_deck_ids and deck_id not in roster_deck_ids:
            v.warn(f"deck {deck_id}", "not referenced by roster.json")

    missing = roster_deck_ids - set(by_id)
    for deck_id in sorted(missing):
        v.fail("decks", f"roster references missing deck {deck_id!r}")
    return decks, by_id


def validate_ai(v: Validator, root: str) -> dict[str, dict]:
    ai_dir = data_path(root, "Opponents", "ai")
    files = sorted(f for f in os.listdir(ai_dir) if f.endswith(".json"))
    v.require(len(files) > 0, "ai", f"found {len(files)} AI profile files")
    profiles: dict[str, dict] = {}
    for filename in files:
        path = os.path.join(ai_dir, filename)
        try:
            profile = load_json(path)
        except Exception as exc:  # noqa: BLE001
            v.fail("ai", f"{filename}: {exc}")
            continue
        pid = profile.get("id")
        if pid != os.path.splitext(filename)[0]:
            v.fail("ai", f"{filename}: id {pid!r} does not match filename")
        if pid in profiles:
            v.fail("ai", f"duplicate profile id {pid!r}")
        profiles[pid] = profile
        strategy = profile.get("strategy")
        if strategy not in AI_STRATEGIES:
            v.fail(f"ai {pid}", f"unknown strategy {strategy!r}")
        aggression = profile.get("aggression")
        if not isinstance(aggression, (int, float)) or not (0.0 <= aggression <= 1.0):
            v.fail(f"ai {pid}", f"aggression {aggression!r} outside 0..1")
        weights = profile.get("weights", {})
        if not isinstance(weights, dict) or not weights:
            v.fail(f"ai {pid}", "weights must be a non-empty object")
        else:
            for key, value in weights.items():
                if not isinstance(value, (int, float)) or not (0.0 <= value <= 2.0):
                    v.fail(f"ai {pid}", f"weight {key}={value!r} outside 0..2")
        if not profile.get("confidence"):
            v.warn(f"ai {pid}", "missing confidence")
        if not profile.get("source"):
            v.warn(f"ai {pid}", "missing source")
    return profiles


def validate_roster(v: Validator, root: str, decks: dict[str, dict], ai: dict[str, dict],
                    cards: dict[int, dict]) -> tuple[dict | None, list[dict]]:
    path = data_path(root, "Opponents", "roster.json")
    try:
        roster = load_json(path)
    except Exception as exc:  # noqa: BLE001
        v.fail("roster", f"{path}: {exc}")
        return None, []
    duelists = roster.get("duelists", [])
    v.require(isinstance(duelists, list) and len(duelists) >= 25, "roster",
              f"{len(duelists)} duelists (need at least 25: 20 ranked + events)")
    ids: set[str] = set()
    ranked = 0
    for d in duelists:
        did = d.get("id")
        if not did:
            v.fail("roster", "duelist has no id")
            continue
        if did in ids:
            v.fail("roster", f"duplicate duelist id {did!r}")
        ids.add(did)
        role = d.get("role")
        if role not in DUELIST_ROLES:
            v.fail(f"roster {did}", f"unknown role {role!r}")
        if role == "ranked":
            ranked += 1
        if d.get("dorm") not in DORMS:
            v.fail(f"roster {did}", f"unknown dorm {d.get('dorm')!r}")
        if d.get("ai_profile") not in ai:
            v.fail(f"roster {did}", f"missing AI profile {d.get('ai_profile')!r}")
        decks_for = d.get("decks", [])
        if not decks_for:
            v.fail(f"roster {did}", "no decks")
        for deck_id in decks_for:
            if deck_id not in decks:
                v.fail(f"roster {did}", f"missing deck {deck_id!r}")
        default = d.get("default_deck")
        if default not in decks_for:
            v.fail(f"roster {did}", f"default deck {default!r} not in decks list")
        for rule in d.get("evolution_rules", []):
            if rule.get("deck") not in decks:
                v.fail(f"roster {did}", f"evolution deck {rule.get('deck')!r} missing")
            if not isinstance(rule.get("after_wins"), int) or rule.get("after_wins", 0) < 1:
                v.fail(f"roster {did}", "evolution after_wins must be >= 1")
            if not rule.get("confidence"):
                v.warn(f"roster {did}", "evolution rule missing confidence")
        for slot in d.get("schedule", []):
            if slot.get("zone") is None:
                v.fail(f"roster {did}", "schedule slot has no zone")
            for weekday in slot.get("weekdays", []):
                if weekday not in WEEKDAYS:
                    v.fail(f"roster {did}", f"invalid weekday {weekday!r}")
            for period in slot.get("periods", []):
                if period not in PERIODS:
                    v.fail(f"roster {did}", f"invalid period {period!r}")
        for location in d.get("locations", []):
            if not location.get("zone"):
                v.fail(f"roster {did}", "location has no zone")
        for card_id in d.get("ante", []):
            if card_id not in cards:
                v.fail(f"roster {did}", f"ante references unknown card {card_id}")
        for card_id in d.get("signature_card_ids", []):
            if card_id not in cards:
                v.fail(f"roster {did}", f"signature references unknown card {card_id}")
        for card_id in d.get("canon_gift_card_ids", []):
            if card_id not in cards:
                v.fail(f"roster {did}", f"canon gift references unknown card {card_id}")
        for gift in d.get("gifts", []):
            if gift.get("type") == "card" and gift.get("card_id") not in cards:
                v.fail(f"roster {did}", f"gift references unknown card {gift.get('card_id')}")
            if gift.get("type") == "dp" and not isinstance(gift.get("amount"), int):
                v.fail(f"roster {did}", "dp gift has no integer amount")
        if not d.get("confidence"):
            v.warn(f"roster {did}", "missing confidence")
        if not d.get("source"):
            v.warn(f"roster {did}", "missing source")
        # Anti/duel requests are optional for event-only/exam opponents.
        request = d.get("duel_request", {})
        if role in {"ranked", "staff"} and not request.get("unlock_flag"):
            v.warn(f"roster {did}", "ranked duelist has no duel-request unlock flag")
    v.require(ranked >= 20, "roster", f"{ranked} ranked duelists (need 20)")
    v.require(len(ids) >= 25, "roster", f"{len(ids)} unique duelists")
    return roster, duelists


def _check_card_ref(v: Validator, label: str, cid: object, cards: dict[int, dict]) -> None:
    if not isinstance(cid, int) or cid not in cards:
        v.fail(label, f"unknown card id {cid!r}")


def _check_zone(v: Validator, label: str, side_name: str, side: dict, cards: dict[int, dict]) -> None:
    monsters = side.get("field", [])
    spells = side.get("spell_traps", [])
    if len(monsters) > 5:
        v.fail(label, f"{side_name} has {len(monsters)} monsters (max 5)")
    if len(spells) > 5:
        v.fail(label, f"{side_name} has {len(spells)} spell/trap cards (max 5)")
    for entry in monsters:
        _check_card_ref(v, label, entry.get("card_id"), cards)
        if entry.get("position") not in {"attack", "defense"}:
            v.fail(label, f"{side_name} monster has invalid position {entry.get('position')!r}")
    for entry in spells:
        _check_card_ref(v, label, entry.get("card_id"), cards)
    for zone in ("hand", "graveyard", "deck", "extra"):
        for cid in side.get(zone, []):
            _check_card_ref(v, label, cid, cards)
    for cid in side.get("extra", []):
        if cid in cards and not is_fusion(cards[cid]):
            v.fail(label, f"{side_name} extra deck contains non-Fusion card {cid}")
    hand = side.get("hand", [])
    if len(hand) > 6:
        v.warn(label, f"{side_name} hand has {len(hand)} cards; puzzle setups may exceed the normal hand limit")


def validate_puzzles(v: Validator, root: str, cards: dict[int, dict], roster: dict | None) -> list[dict]:
    puzzle_dir = data_path(root, "Puzzles")
    files = sorted(f for f in os.listdir(puzzle_dir) if f.endswith(".json"))
    v.require(len(files) == 20, "puzzles", f"{len(files)} puzzle files (this pass targets P001-P020)")
    ids: set[str] = set()
    opponent_ids = {d.get("id") for d in (roster or {}).get("duelists", [])}
    puzzles: list[dict] = []
    for filename in files:
        path = os.path.join(puzzle_dir, filename)
        try:
            puzzle = load_json(path)
        except Exception as exc:  # noqa: BLE001
            v.fail("puzzles", f"{filename}: {exc}")
            continue
        pid = puzzle.get("id")
        label = f"puzzle {pid or filename}"
        if pid != os.path.splitext(filename)[0]:
            v.fail(label, "id does not match filename")
        if pid in ids:
            v.fail(label, "duplicate puzzle id")
        ids.add(pid)
        puzzles.append(puzzle)

        if puzzle.get("level") != 1:
            v.fail(label, f"level {puzzle.get('level')!r} (this pass is level 1)")
        if opponent_ids and puzzle.get("opponent") not in opponent_ids:
            v.fail(label, f"unknown opponent {puzzle.get('opponent')!r}")
        if not isinstance(puzzle.get("seed"), int):
            v.fail(label, "seed must be an integer")
        if not isinstance(puzzle.get("turn_limit"), int) or puzzle.get("turn_limit") < 1:
            v.fail(label, "turn_limit must be >= 1")
        if not isinstance(puzzle.get("time_limit"), int) or puzzle.get("time_limit") < 10:
            v.fail(label, "time_limit must be >= 10 seconds")
        if puzzle.get("objective") != "win_this_turn":
            v.fail(label, f"objective {puzzle.get('objective')!r} not supported")
        player = puzzle.get("player")
        opponent = puzzle.get("opponent_state", {}) if isinstance(puzzle.get("opponent_state"), dict) else {}
        if not isinstance(player, dict):
            v.fail(label, "player state missing")
            continue
        if not isinstance(player.get("lp"), int) or player.get("lp") <= 0:
            v.fail(label, "player.lp must be a positive integer")
        if not isinstance(opponent.get("lp"), int) or opponent.get("lp") <= 0:
            v.fail(label, "opponent.lp must be a positive integer")
        _check_zone(v, label, "player", player, cards)
        _check_zone(v, label, "opponent", opponent, cards)

        solution = puzzle.get("solution")
        if not isinstance(solution, list) or not solution:
            v.fail(label, "solution must be a non-empty array")
            continue
        setup_ids = set()
        for state in (player, opponent):
            for entry in state.get("field", []) + state.get("spell_traps", []):
                if isinstance(entry, dict):
                    setup_ids.add(entry.get("card_id"))
            for zone in ("hand", "graveyard", "deck", "extra"):
                setup_ids.update(state.get(zone, []))
        has_finisher = False
        for step_index, step in enumerate(solution):
            if not isinstance(step, dict):
                v.fail(label, f"solution step {step_index} is not an object")
                continue
            action = step.get("action")
            if action not in PUZZLE_ACTIONS:
                v.fail(label, f"solution step {step_index} has unknown action {action!r}")
                continue
            referenced = []
            if "card_id" in step:
                referenced.append(step.get("card_id"))
            if "attacker_card_id" in step:
                referenced.append(step.get("attacker_card_id"))
            referenced.extend(step.get("tribute_card_ids", []))
            target = step.get("target")
            if isinstance(target, int):
                referenced.append(target)
            for cid in referenced:
                _check_card_ref(v, label, cid, cards)
                if cid not in setup_ids:
                    v.fail(label, f"solution step {step_index} references card {cid} not present in the setup")
            if action == "attack":
                if step.get("target") != "direct" and not isinstance(step.get("target"), int):
                    v.fail(label, f"solution step {step_index} has invalid target")
                has_finisher = True
            elif action in {"normal_summon", "special_summon", "set_monster", "activate_spell",
                            "set_spell_trap", "activate_trap", "activate_effect", "change_position", "discard"}:
                if action in {"normal_summon", "set_monster", "set_spell_trap"}:
                    player_pool = set(player.get("hand", [])) | set(player.get("graveyard", [])) | set(player.get("deck", [])) | set(player.get("extra", []))
                    if step.get("card_id") not in player_pool:
                        v.fail(label, f"solution step {step_index} card is not available to the player")
                if action in {"normal_summon", "special_summon", "activate_spell", "activate_trap", "activate_effect"}:
                    has_finisher = has_finisher or action in {"activate_spell", "activate_trap", "activate_effect"}
        if not has_finisher:
            v.warn(label, "solution has no attack or activatable finisher")
        reward = puzzle.get("reward")
        if not isinstance(reward, dict):
            v.fail(label, "reward object missing")
        else:
            dp = reward.get("dp", 0)
            if not isinstance(dp, int) or dp < 0:
                v.fail(label, "reward.dp must be a non-negative integer")
            for cid in reward.get("cards", []):
                _check_card_ref(v, label, cid, cards)
        if not puzzle.get("confidence"):
            v.warn(label, "missing confidence")
        if not puzzle.get("source"):
            v.warn(label, "missing source")
        if not isinstance(puzzle.get("engine_ready"), bool):
            v.fail(label, "engine_ready must be a boolean")
        canon_ref = puzzle.get("canon_reference")
        if canon_ref:
            if not canon_ref.get("source"):
                v.fail(label, "canon_reference has no source")
            for cid in canon_ref.get("solution_card_ids", []):
                _check_card_ref(v, label + " canon", cid, cards)
            if not canon_ref.get("solution_steps"):
                v.warn(label, "canon_reference has no solution steps")
        else:
            v.warn(label, "no canon_reference attached")
    return puzzles


def validate_exams(v: Validator, root: str, cards: dict[int, dict], decks: dict[str, dict],
                   roster: dict | None) -> tuple[dict, dict, dict]:
    exam_dir = data_path(root, "Exams")
    questions = load_json(os.path.join(exam_dir, "questions.json"))
    practicals = load_json(os.path.join(exam_dir, "practicals.json"))
    scoring = load_json(os.path.join(exam_dir, "scoring.json"))

    qlist = questions.get("questions", [])
    v.require(len(qlist) >= 10, "exams", f"{len(qlist)} written questions (need at least 10)")
    qids: set[str] = set()
    for q in qlist:
        qid = q.get("id")
        if qid in qids:
            v.fail("exams", f"duplicate question id {qid!r}")
        qids.add(qid)
        options = q.get("options", [])
        if len(options) != 4:
            v.fail(f"question {qid}", f"{len(options)} options (need 4)")
        answer = q.get("answer_index")
        if not isinstance(answer, int) or not (0 <= answer < len(options)):
            v.fail(f"question {qid}", f"invalid answer_index {answer!r}")
        if not q.get("text") or not q.get("explanation"):
            v.fail(f"question {qid}", "missing text/explanation")
        if not q.get("confidence"):
            v.warn(f"question {qid}", "missing confidence")
    sets = questions.get("exam_sets", [])
    v.require(len(sets) == 12, "exams", f"{len(sets)} exam sets (need 12)")
    for exam_set in sets:
        label = f"exam set {exam_set.get('exam_id')}"
        qids_for_set = exam_set.get("question_ids", [])
        if len(qids_for_set) != 10:
            v.fail(label, f"{len(qids_for_set)} questions (need 10)")
        if len(set(qids_for_set)) != len(qids_for_set):
            v.fail(label, "duplicate question ids")
        for qid in qids_for_set:
            if qid not in qids:
                v.fail(label, f"unknown question {qid!r}")

    objectives = practicals.get("objectives", [])
    v.require(len(objectives) == 7, "practicals", f"{len(objectives)} objectives (need 7)")
    objective_ids = set()
    practical_points = 0
    for objective in objectives:
        oid = objective.get("id")
        if oid in objective_ids:
            v.fail("practicals", f"duplicate objective {oid!r}")
        objective_ids.add(oid)
        practical_points += objective.get("points", 0)
        if not isinstance(objective.get("target"), int) or objective.get("target") < 1:
            v.fail(f"practical {oid}", "target must be >= 1")
    v.require(practical_points == practicals.get("max_points", 200),
              "practicals", f"objective points sum {practical_points} == max_points {practicals.get('max_points')}")
    if practicals.get("deck") not in decks:
        v.fail("practicals", f"missing deck {practicals.get('deck')!r}")
    opponent_ids = {d.get("id") for d in (roster or {}).get("duelists", [])}
    if opponent_ids and practicals.get("opponent") not in opponent_ids:
        v.fail("practicals", f"missing opponent {practicals.get('opponent')!r}")

    sections = scoring.get("sections", {})
    section_total = 0
    for key in ("written", "timed", "practical"):
        section = sections.get(key, {})
        pts = section.get("max_points", 0)
        section_total += pts
        if not isinstance(pts, int) or pts <= 0:
            v.fail("scoring", f"section {key} has invalid max_points {pts!r}")
    v.require(section_total == scoring.get("max_points", 500),
              "scoring", f"section totals {section_total} == max_points {scoring.get('max_points')}")
    pass_mark = scoring.get("pass_mark")
    if not isinstance(pass_mark, int) or not (0 <= pass_mark <= scoring.get("max_points", 500)):
        v.fail("scoring", f"invalid pass_mark {pass_mark!r}")
    bands = scoring.get("grade_bands", [])
    if not bands:
        v.fail("scoring", "no grade bands")
    for band in bands:
        if not isinstance(band.get("min_points"), int):
            v.fail("scoring", "grade band has no integer min_points")
    if not scoring.get("confidence"):
        v.warn("scoring", "missing confidence")
    return questions, practicals, scoring


def build_report(root: str, v: Validator, cards: dict[int, dict], decks: list[dict],
                 roster: dict | None, ai: dict[str, dict], puzzles: list[dict],
                 questions: dict, practicals: dict, scoring: dict) -> str:
    lines = [
        "# Opponents / Exams / Puzzles — Validation Report",
        "",
        f"- Generated: {_dt.date.today().isoformat()}",
        f"- Root: `{root}`",
        f"- Result: **{'PASS' if not v.failures else 'FAIL'}**",
        f"- Checks: {v.checks} · Failures: {len(v.failures)} · Warnings: {len(v.warnings)}",
        "",
        "## Counts",
        "",
        f"- Cards: {len(cards)}",
        f"- Duelists: {len((roster or {}).get('duelists', []))} "
        f"({sum(1 for d in (roster or {}).get('duelists', []) if d.get('role') == 'ranked')} ranked)",
        f"- Opponent decks: {len(decks)}",
        f"- AI profiles: {len(ai)}",
        f"- Puzzles: {len(puzzles)} (level 1, P001-P020)",
        f"- Canon puzzle references attached: {sum(1 for p in puzzles if p.get('canon_reference'))}/{len(puzzles)}",
        f"- Engine-ready fallback lines: {sum(1 for p in puzzles if p.get('engine_ready'))}/{len(puzzles)}",
        f"- Written questions: {len(questions.get('questions', []))}; exam sets: {len(questions.get('exam_sets', []))}",
        f"- Practical objectives: {len(practicals.get('objectives', []))}",
        f"- Scoring: {scoring.get('max_points')} points, pass mark {scoring.get('pass_mark')}",
        "",
        "## Card support",
        "",
    ]
    referenced: set[int] = set()
    for deck in decks:
        referenced.update(deck.get("cards", []) + deck.get("extra", []) + deck.get("side", []))
    for duelist in (roster or {}).get("duelists", []):
        referenced.update(duelist.get("ante", []))
        referenced.update(duelist.get("signature_card_ids", []))
        referenced.update(duelist.get("canon_gift_card_ids", []))
        for gift in duelist.get("gifts", []):
            if gift.get("card_id"):
                referenced.add(gift["card_id"])
    for puzzle in puzzles:
        for state_key in ("player", "opponent_state"):
            state = puzzle.get(state_key, {}) if isinstance(puzzle.get(state_key), dict) else {}
            for entry in state.get("field", []) + state.get("spell_traps", []):
                if isinstance(entry, dict):
                    referenced.add(entry.get("card_id"))
            for zone in ("hand", "graveyard", "deck", "extra"):
                referenced.update(state.get(zone, []))
    unknown = sorted(cid for cid in referenced if cid not in cards)
    lines.append(f"- Referenced card ids: {len(referenced)} unique; unknown ids: {len(unknown)}"
                 + (f" ({unknown[:12]})" if unknown else ""))
    missing_recipes = []
    fusions_path = data_path(root, "fusions.json")
    if os.path.exists(fusions_path):
        try:
            fusion_results = {entry.get("result") for entry in load_json(fusions_path) if isinstance(entry, dict)}
        except Exception:  # noqa: BLE001
            fusion_results = set()
        for deck in decks:
            for cid in deck.get("extra", []):
                if cid not in fusion_results:
                    missing_recipes.append(f"{deck.get('id')}:{cid}")
    lines.append(f"- Extra Deck cards without a `fusions.json` recipe: "
                 f"{len(missing_recipes)}" + (f" ({', '.join(sorted(set(missing_recipes)))})" if missing_recipes else ""))
    lines += [
        "",
        "## Deck results",
        "",
        "| Deck | Opponent | Main | Extra | Confidence | Result |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for deck in sorted(decks, key=lambda d: d.get("id", "")):
        deck_id = deck.get("id")
        bad = [f for f in v.failures if f.startswith(f"deck {deck_id}:")]
        lines.append(
            f"| `{deck_id}` | {deck.get('opponent', '')} | {len(deck.get('cards', []))} | "
            f"{len(deck.get('extra', []))} | {deck.get('confidence', '')} | {'FAIL' if bad else 'PASS'} |"
        )
    lines += ["", "## Puzzle results", "", "| Puzzle | Time | Reward DP | Result |", "| --- | ---: | ---: | --- |"]
    for puzzle in sorted(puzzles, key=lambda p: p.get("id", "")):
        pid = puzzle.get("id")
        bad = [f for f in v.failures if f.startswith(f"puzzle {pid}:")]
        lines.append(
            f"| `{pid}` | {puzzle.get('time_limit')}s | {puzzle.get('reward', {}).get('dp', 0)} | "
            f"{'FAIL' if bad else 'PASS'} |"
        )
    lines += ["", "## Failures", ""]
    lines += [f"- {item}" for item in v.failures] or ["None."]
    lines += ["", "## Warnings", ""]
    lines += [f"- {item}" for item in v.warnings] or ["None."]
    lines += [
        "",
        "## Canon confidence",
        "",
        "Decks, puzzles and exam weights carry `confidence` and `source`. High-confidence entries: existing",
        "Jaden deck, Cyber Dragon/Ancient Gear/Amazoness card availability, core written rules. Low-confidence",
        "entries are reconstructions where the GBA list could not be extracted; A01 should replace them with",
        "traceable canon data. See `Docs/Opponents_Exams_Notes.md`.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Duel Academy opponent, AI, exam and puzzle data.")
    parser.add_argument("--root", default=ROOT_DEFAULT, help="Repository root (default: two levels above this script)")
    parser.add_argument("--report", default="", help="Write a Markdown validation report to this path")
    parser.add_argument("--strict-warnings", action="store_true", help="Treat warnings as failures")
    args = parser.parse_args()
    root = os.path.abspath(args.root)
    v = Validator(root)

    try:
        cards, names = validate_cards(v, root)
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL cards: {exc}")
        return 1

    roster = None
    try:
        # Load roster early enough for deck/roster cross-checks, then validate fully.
        roster_raw = load_json(data_path(root, "Opponents", "roster.json"))
    except Exception as exc:  # noqa: BLE001
        v.fail("roster", f"cannot load roster.json: {exc}")
        roster_raw = None

    decks, deck_by_id = validate_decks(v, root, cards, names, roster_raw)
    ai = validate_ai(v, root)
    if roster_raw is not None:
        roster, _duelists = validate_roster(v, root, deck_by_id, ai, cards)
    puzzles = validate_puzzles(v, root, cards, roster or roster_raw)
    try:
        questions, practicals, scoring = validate_exams(v, root, cards, deck_by_id, roster or roster_raw)
    except Exception as exc:  # noqa: BLE001
        v.fail("exams", f"cannot load exam data: {exc}")
        questions, practicals, scoring = {}, {}, {}

    for label, success, detail in v.sections:
        print(f"{'PASS' if success else 'FAIL'} {label}" + (f": {detail}" if detail else ""))
    for warning in v.warnings:
        print(f"WARN {warning}")

    failed = bool(v.failures) or (args.strict_warnings and bool(v.warnings))
    print("")
    print(f"{'PASS' if not failed else 'FAIL'} summary: {v.checks} checks, "
          f"{len(v.failures)} failures, {len(v.warnings)} warnings")
    print(f"duelists={(roster or roster_raw or {}).get('duelists', []) and len((roster or roster_raw).get('duelists', []))} "
          f"decks={len(decks)} ai={len(ai)} puzzles={len(puzzles)} "
          f"questions={len(questions.get('questions', []))}")

    if args.report:
        report_path = os.path.abspath(args.report)
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write(build_report(root, v, cards, decks, roster or roster_raw, ai, puzzles,
                                      questions, practicals, scoring))
        print(f"report={report_path}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
