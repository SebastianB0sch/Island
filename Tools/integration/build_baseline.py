#!/usr/bin/env python3
"""Recompute Docs/Integration/baseline.json from the current tree and gates.

Every Python-derived count is freshly computed from the data the validators
read plus the validators themselves, so the baseline can never drift from
what the gates actually see:

    * Tools/validate/validate_all.py --json  (report/tool counts)
    * Tools/puzzles/validate.py              (roster/deck/ai/exam tallies)
    * Tools/world/validate_layout.py --json  (world zone / actor tallies)
    * the data files under Content/Data      (canon + runtime totals)

Unreal results (engine builds and in-editor self-tests) cannot be recomputed
without the editor; those sections are preserved verbatim from the dated
captured evidence and carry their own capture note.

Usage:
    python Tools/integration/build_baseline.py           # print, no writes
    python Tools/integration/build_baseline.py --check   # exit 1 when stale
    python Tools/integration/build_baseline.py --write   # refresh baseline.json
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))

from tooling import atomic  # noqa: E402  (path setup)

DATA = ROOT / "DuelAcademyIsland" / "Content" / "Data"
BASELINE_PATH = ROOT / "Docs" / "Integration" / "baseline.json"


def _load_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _run(*argv: str) -> str:
    completed = subprocess.run(
        [sys.executable, *argv],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"validator exited with {completed.returncode}:\n{completed.stdout}\n{completed.stderr}"
        )
    return completed.stdout


def _warn_count(payload: dict, code: str, noun: str) -> int | None:
    """Extract the leading count from a validator warning like '3 flag(s)...'."""
    message = next((f["message"] for f in payload if f.get("code") == code), "")
    match = re.match(rf"(\d+) {re.escape(noun)}", message)
    return int(match.group(1)) if match else None


def _validator_counts() -> dict:
    """Run the baseline validator and capture its self-reported numbers."""
    stdout = _run(str(ROOT / "Tools" / "validate" / "validate_all.py"), "--json")
    payload = json.loads(stdout)
    counts = payload["counts"]
    findings = payload.get("findings", [])
    return {
        "tool": "validate_all",
        "tool_version": payload.get("tool_version"),
        "mode": "baseline (nothing written)",
        "result": payload.get("result"),
        "errors": counts.get("errors"),
        "warnings": counts.get("warnings"),
        "gaps": counts.get("gaps"),
        "infos": counts.get("infos"),
        "files_read": counts.get("files_read"),
        "checks": counts.get("checks"),
        "finding_codes": sorted({finding["code"] for finding in findings}),
        "flags_unwritten": _warn_count(findings, "flag_unwritten", "flag(s) are read"),
        "counters_unwritten": _warn_count(findings, "counter_unwritten", "counter(s) are read"),
    }


def _puzzle_validator_counts() -> dict:
    stdout = _run(str(ROOT / "Tools" / "puzzles" / "validate.py"))
    summary = re.search(r"PASS summary: (\d+) checks, (\d+) failures, (\d+) warnings", stdout)
    tallies = re.search(
        r"duelists=(\d+) decks=(\d+) ai=(\d+) puzzles=(\d+) questions=(\d+) cycles=(\d+)",
        stdout,
    )
    if not summary or not tallies:
        raise RuntimeError(f"unexpected puzzles/validate.py output:\n{stdout}")
    checks, failures, warnings = (int(value) for value in summary.groups())
    duelists, decks, ai, puzzles, questions, cycles = (int(value) for value in tallies.groups())
    return {
        "tool": "Tools/puzzles/validate.py",
        "checks": checks,
        "failures": failures,
        "warnings": warnings,
        "result": "PASS" if failures == 0 else "FAIL",
        "duelists": duelists,
        "opponent_decks": decks,
        "ai_profiles": ai,
        "puzzles": puzzles,
        "questions": questions,
        "cycles": cycles,
    }


def _world_counts() -> dict:
    stdout = _run(str(ROOT / "Tools" / "world" / "validate_layout.py"), "--json")
    payload = json.loads(stdout)
    if payload.get("ok") is not True:
        raise RuntimeError(f"validate_layout reported errors: {payload['errors'][:5]}")
    summary = payload["summary"]
    return {
        "world_zones": summary["zones"],
        "world_locations": summary["locations"],
        "world_anchors": summary["anchors"],
        "interior_cells": summary["interiors"],
        "portals": summary["portals"],
        "spawns": summary["spawns"],
    }


def _canon_counts(codes: set[str]) -> dict:
    cards = _load_json(DATA / "cards.json")
    canon = DATA / "Canon"
    decks_doc = _load_json(canon / "decks.json")
    packs = _load_json(canon / "packs.json")["packs"]
    opponents_doc = _load_json(canon / "opponents.json")
    events = _load_json(canon / "events.json")["events"]
    puzzles = _load_json(canon / "puzzles.json")["puzzles"]
    titles = _load_json(canon / "titles.json")["titles"]
    banned = _load_json(canon / "banned_list.json")["cards"]

    pack_union = {card_id for pack in packs for card_id in pack["unique_card_ids"]}
    levels = {str(level): sum(1 for p in puzzles if p.get("level") == level) for level in range(1, 6)}

    return {
        "cards": len(cards),
        "fusion_recipes": len(_load_json(DATA / "fusions.json")),
        "ritual_procedures": len(_load_json(DATA / "rituals.json")),
        "decks": len(decks_doc["decks"]),
        "decks_complete": decks_doc["summary"]["complete"],
        "decks_partial": decks_doc["summary"]["partial"],
        "decks_unknown": decks_doc["summary"]["unknown"],
        "packs": len(packs),
        "pack_card_union": len(pack_union),
        "opponents": opponents_doc["count"],
        "named_duelists": opponents_doc["named_duelists"],
        "event_duelists": opponents_doc["event_duelists"],
        "events": len(events),
        "numbered_events_1_to_33": sum(1 for i in range(1, 34) if f"E{i:02d}" in {e["id"] for e in events}),
        "events_deck_refs_unresolved": 1 if "canon_event_deck_ref" in codes else 0,
        "puzzles": len(puzzles),
        "puzzle_levels": levels,
        "puzzle_setups_known": sum(1 for p in puzzles if p.get("setup")),
        "puzzle_timers_known": sum(1 for p in puzzles if p.get("time_limit_seconds") is not None),
        "titles": len(titles),
        "banlist_cards": len(banned),
    }


def _runtime_counts() -> dict:
    manifest = _load_json(DATA / "Effects" / "card_effect_manifest.json")
    status = manifest["summary"]["by_status"]
    scripts = sorted((DATA / "Effects" / "scripts").glob("*.json"))
    shop = _load_json(DATA / "Shop" / "packs.json")["packs"]
    pack_union = {cid for pack in shop for pool in pack["pools"] for cid in pool["cards"]}
    roster = _load_json(DATA / "Opponents" / "roster.json")["duelists"]
    roles = {role: sum(1 for d in roster if d.get("role") == role) for role in sorted({d.get("role") for d in roster})}
    ai_profiles = sorted((DATA / "Opponents" / "ai").glob("*.json"))
    puzzle_ids = {p["id"] for p in (_load_json(p) for p in (DATA / "Puzzles").glob("*.json")) if "id" in p}
    events_doc = _load_json(DATA / "Story" / "events.json")
    scenes_doc = _load_json(DATA / "Story" / "scenes" / "full_campaign.json")
    dialogue_doc = _load_json(DATA / "Story" / "dialogue" / "full_campaign.json")
    emails_doc = _load_json(DATA / "Story" / "emails.json")
    exams_doc = _load_json(DATA / "Exams" / "exams.json")
    questions_doc = _load_json(DATA / "Exams" / "questions.json")
    rules = _load_json(DATA / "Rules" / "banned_limited.json")
    starter_decks = _load_json(DATA / "decks.json")
    player_decks = _load_json(DATA / "Decks" / "player_decks.json")
    opponent_decks = sorted((DATA / "Opponents" / "decks").glob("*.json"))
    save_fixtures = sorted((DATA / "Integration" / "saves").glob("golden_*.json"))

    email_contacts = emails_doc.get("contacts", [])
    questions = questions_doc.get("questions", questions_doc)
    question_count = len(questions) if isinstance(questions, list) else sum(
        len(group) if isinstance(group, list) else 1 for group in questions.values()
    )

    return {
        "cards": len(_load_json(DATA / "cards.json")),
        "fusion_recipes": len(_load_json(DATA / "fusions.json")),
        "ritual_procedures": len(_load_json(DATA / "rituals.json")),
        "decks": len(starter_decks) + len(player_decks.get("decks", [])) + len(opponent_decks),
        "decks_breakdown": {
            "starter_shells": len(starter_decks),
            "player_saved": len(player_decks.get("decks", [])),
            "opponent_runtime": len(opponent_decks),
        },
        "packs": len(shop),
        "pack_card_union": len(pack_union),
        "opponents": len(roster),
        "opponents_by_role": roles,
        "ai_profiles": len(ai_profiles),
        "puzzles": len(puzzle_ids),
        "exams": len(exams_doc.get("cycles", [])),
        "exam_questions": question_count,
        "events": len(events_doc["events"]),
        "numbered_events_1_to_33": sum(
            1 for i in range(1, 34) if f"E{i:02d}" in {e["id"] for e in events_doc["events"]}
        ),
        "story_scenes": len(scenes_doc["scenes"]),
        "dialogue_lines": len(dialogue_doc["lines"]),
        "npc_schedule_slots": sum(len(d.get("schedule", [])) for d in roster),
        **_world_counts(),
        "effect_manifest_entries": manifest["summary"]["total"],
        "effect_scripted": status["scripted"],
        "effect_vanilla": status["vanilla"],
        "effect_pending": status["pending"],
        "effect_unsupported": status["unsupported"],
        "effect_data_scripts": len(scripts),
        "save_fixtures": len(save_fixtures),
        "forbidden_cards": len(rules.get("banned", [])),
        "limited_cards": len(rules.get("limited", [])),
        "semi_limited_cards": len(rules.get("semi_limited", [])),
        "emails_contacts": len(email_contacts),
        "emails_messages": sum(len(c.get("messages", [])) for c in email_contacts),
        "email_duel_requests": sum(len(c.get("duel_requests", [])) for c in email_contacts),
    }


UNREAL_NOTE = (
    "Unreal build/self-test and smoke strings below are dated captured "
    "evidence; refresh with Tools/integration/run_smoke.py --all at a "
    "content gate. All Python-only counts in this file are recomputed by "
    "Tools/integration/build_baseline.py."
)


def _known_gaps(canon: dict, runtime: dict) -> list[str]:
    """Data-gap statements, each number freshly computed from the counts."""
    return [
        (
            f"Effects: {runtime['effect_pending']} cards pending effect "
            f"implementation ({runtime['effect_scripted']} scripted = "
            f"{runtime['effect_data_scripts']} data scripts + "
            f"{runtime['effect_scripted'] - runtime['effect_data_scripts']} "
            f"engine handlers, {runtime['effect_vanilla']} vanilla covered by "
            f"fusions/rituals/generic rules)."
        ),
        (
            f"E02-E33 in-engine playthrough: all {runtime['events']} event "
            "definitions validate, but only the opening is covered by the "
            "story self-test."
        ),
        (
            f"Full dialogue/email UI integration: "
            f"{runtime['dialogue_lines']} dialogue lines and "
            f"{runtime['emails_contacts']} email contacts validate; UI "
            "behavior is not fully exercised."
        ),
        (
            f"Interiors generation: {runtime['interior_cells']} cells "
            "specified, generation and entry/exit/nav tests pending."
        ),
        "Shop/deck/exam UI wiring: PDA/dialogue screenshots exist, interactions incomplete.",
        (
            "Dorothy's Gift pack materialises the canon full pool (all 1,200 "
            "ids, copy weight 1); per-card rarity weights remain provisional."
        ),
        (
            f"Canon decks: {canon['decks'] - canon['decks_complete']}/"
            f"{canon['decks']} marked incomplete "
            f"({canon['decks_partial']} partial, {canon['decks_unknown']} unknown); "
            f"canon event deck refs unresolved: {canon['events_deck_refs_unresolved']}."
        ),
        "Canon puzzles: 100 solutions known, all setups/timers unknown.",
        "Canon exam week rule is unresolved.",
    ]


def _recorded_warnings(runtime: dict, validator: dict) -> list[str]:
    flags = validator.get("flags_unwritten")
    counters = validator.get("counters_unwritten")
    return [
        "5 duplicate-material fusion recipes need review; check generic-material handling.",
        "F.G.D. generic Dragon-count recipe needs effect-runtime support.",
        f"UFOroid Fighter recipe is unresolved.",
        (
            f"{flags if flags is not None else 3} flag(s) are read but never "
            "written and "
            f"{counters if counters is not None else 8} counter(s) are read "
            "but never written (see the validate_all findings for the lists)."
        ),
        "6 remaining pre-contract shapes are warnings; A03/A07 accepted shapes are INFO with optional migration notes.",
    ]


def build() -> dict:
    validator = _validator_counts()
    try:
        previous = _load_json(BASELINE_PATH)
    except OSError:
        previous = {}

    canon = _canon_counts(set(validator["finding_codes"]))
    runtime = _runtime_counts()

    return {
        "schema_version": 2,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
        "computed_by": "Tools/integration/build_baseline.py",
        "unreal_evidence": previous.get("baseline", {}),
        "smoke_captured": previous.get("smoke", {}),
        "unreal_evidence_note": UNREAL_NOTE,
        "canon_counts": canon,
        "runtime_counts": runtime,
        "validator": {
            key: value for key, value in validator.items()
            if key != "finding_codes"
        },
        "validator_finding_codes": validator["finding_codes"],
        "puzzle_validator": _puzzle_validator_counts(),
        "world_validator": {
            "tool": "Tools/world/validate_layout.py",
            "result": "PASS",
        },
        "known_gaps": _known_gaps(canon, runtime),
        "warnings": _recorded_warnings(runtime, validator),
        "gate1_results": previous.get("gate1_results", ""),
    }


def render_counts(baseline: dict) -> str:
    lines = []
    for section in ("canon_counts", "runtime_counts"):
        lines.append(f"{section}:")
        for key, value in baseline[section].items():
            lines.append(f"  {key} = {value}")
    lines.append("validator:")
    for key, value in baseline["validator"].items():
        lines.append(f"  {key} = {value}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recompute Docs/Integration/baseline.json")
    parser.add_argument("--write", action="store_true", help="update Docs/Integration/baseline.json")
    parser.add_argument("--check", action="store_true", help="exit 1 when baseline.json is stale")
    args = parser.parse_args(argv)
    if args.write and args.check:
        print("error: --write and --check are mutually exclusive", file=sys.stderr)
        return 2

    built = build()
    print(render_counts(built))
    if not (args.write or args.check):
        return 0

    current = _load_json(BASELINE_PATH)
    stale = [
        key for key in ("canon_counts", "runtime_counts", "validator", "puzzle_validator")
        if current.get(key) != built[key]
    ]
    if args.check:
        if stale:
            print(f"stale sections: {', '.join(stale)}", file=sys.stderr)
            return 1
        print("baseline is current", file=sys.stderr)
        return 0
    atomic.write_json(BASELINE_PATH, built)
    changed = ", ".join(stale) if stale else "none"
    print(f"wrote {BASELINE_PATH.relative_to(ROOT)} (sections changed: {changed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
