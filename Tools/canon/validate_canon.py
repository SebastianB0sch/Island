"""Validate the canon dataset and emit a human-readable report.

Run after build_all.py. Exits non-zero on hard errors; warnings are recorded
in Docs/Canon/VALIDATION.md.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

from canon_common import (
    CANON_DIR, DOCS_DIR, REPO_ROOT, TOOLS_DIR, read_json, sha256_file, utc_now,
    write_text,
)

CARD_IDS = set(range(1, 1201))


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.checks: list[tuple[str, str, str]] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, "PASS" if ok else "FAIL", detail))
        if not ok:
            self.errors.append(f"{name}: {detail}")

    def warn(self, name: str, ok: bool, detail: str = "") -> None:
        self.checks.append((name, "PASS" if ok else "WARN", detail))
        if not ok:
            self.warnings.append(f"{name}: {detail}")


def main() -> int:
    report = Report()
    cards = read_json(CANON_DIR.parent / "cards.json")
    card_ids = {int(c["id"]) for c in cards}
    card_names = {int(c["id"]): c["name"] for c in cards}
    report.check("cards.count", len(cards) == 1200 and card_ids == CARD_IDS,
                 f"{len(cards)} records, ids 1..1200")
    manifest = read_json(CANON_DIR / "cards_manifest.json")
    report.check("cards.verified", manifest["verification"]["status"] == "exact",
                 f"{manifest['verification']['difference_count']} differences")
    report.check("cards.hash", len(manifest["canonical_hash"]["value"]) == 64,
                 manifest["canonical_hash"]["value"][:16] + "...")

    packs = read_json(CANON_DIR / "packs.json")
    pack_records = packs["packs"]
    report.check("packs.count", len(pack_records) == 48, str(len(pack_records)))
    report.check("packs.ids_unique", len({p["id"] for p in pack_records}) == len(pack_records), "")
    all_pack_ids = {cid for p in pack_records for cid in p["unique_card_ids"]}
    report.check("packs.cards_valid", all_pack_ids <= CARD_IDS,
                 f"{len(all_pack_ids - CARD_IDS)} invalid ids")
    report.check("packs.all_cards_obtainable", all_pack_ids == CARD_IDS,
                 f"{len(CARD_IDS - all_pack_ids)} cards missing")
    missing_prices = [p["id"] for p in pack_records if p["price_dp"] is None]
    report.check("packs.prices", not missing_prices, str(missing_prices))
    missing_sizes = [p["id"] for p in pack_records if not (p["cards_per_pack"] or 0)]
    report.check("packs.pack_sizes", not missing_sizes, str(missing_sizes))
    report.warn("packs.odds", False, "pack rarity odds are not published; A06 must define a seeded model")
    report.warn("packs.unresolved_names", not any(p["unresolved_names"] for p in pack_records),
                f"{sum(1 for p in pack_records if p['unresolved_names'])} packs have unresolved guide names")

    events = read_json(CANON_DIR / "events.json")["events"]
    event_ids = {e["id"] for e in events}
    report.check("events.count", len(events) >= 34, str(len(events)))
    report.check("events.ids_unique", len(event_ids) == len(events), "")
    report.check("events.numbered", len([e for e in events if isinstance(e["number"], int)]) >= 33, "")
    for event in events:
        for reward in event.get("rewards", []):
            refs = reward.get("cards", []) if isinstance(reward, dict) else []
            if not isinstance(refs, list):
                continue
            for ref in refs:
                if ref.get("card_id") is not None and ref["card_id"] not in CARD_IDS:
                    report.errors.append(f"{event['id']} reward card {ref['name']} -> invalid id {ref['card_id']}")
    unresolved_rewards = []
    for event in events:
        for reward in event.get("rewards", []):
            refs = reward.get("cards", []) if isinstance(reward, dict) else []
            if not isinstance(refs, list):
                continue
            for ref in refs:
                if ref.get("card_id") is None:
                    unresolved_rewards.append((event["id"], ref["name"]))
    report.warn("events.reward_cards_resolved", not unresolved_rewards, str(unresolved_rewards[:5]))

    opponents = read_json(CANON_DIR / "opponents.json")["opponents"]
    opponent_ids = {o["id"] for o in opponents}
    report.check("opponents.count", len(opponents) >= 20, str(len(opponents)))
    report.check("opponents.ids_unique", len(opponent_ids) == len(opponents), "")

    decks = read_json(CANON_DIR / "decks.json")["decks"]
    deck_ids = {d["id"] for d in decks}
    report.check("decks.count", len(decks) >= 20, str(len(decks)))
    report.check("decks.ids_unique", len(deck_ids) == len(decks), "")
    for deck in decks:
        for cid in deck["main"] + deck["extra"]:
            if cid not in CARD_IDS:
                report.errors.append(f"deck {deck['id']} references invalid card {cid}")
        if deck["complete"]:
            report.check(f"decks.{deck['id']}.size", 40 <= deck["main_count"] <= 60,
                         f"main {deck['main_count']}")
            report.check(f"decks.{deck['id']}.extra", deck["extra_count"] <= 20,
                         f"extra {deck['extra_count']}")
            counts = Counter(deck["main"])
            report.warn(f"decks.{deck['id']}.copies", max(counts.values(), default=0) <= 3,
                        "copy limit check is against the 3-copy rule, not the year list")

    puzzles = read_json(CANON_DIR / "puzzles.json")["puzzles"]
    report.check("puzzles.count", len(puzzles) == 100, str(len(puzzles)))
    report.check("puzzles.levels", all(sum(1 for p in puzzles if p["level"] == level) == 20 for level in range(1, 6)), "")
    report.check("puzzles.solutions", all(p["solution_steps"] for p in puzzles),
                 f"{sum(1 for p in puzzles if not p['solution_steps'])} missing")
    report.check("puzzles.card_ids", all(set(p["solution_card_ids"]) <= CARD_IDS for p in puzzles), "")

    titles = read_json(CANON_DIR / "titles.json")["titles"]
    permanent = [t for t in titles if t["permanent"]]
    report.check("titles.count", len(permanent) == 12, f"{len(permanent)} permanent titles")
    report.check("titles.dropout", any(t["id"] == "dropout_boy" for t in titles), "Dropout Boy state")
    report.check("titles.temporary", any(not t["permanent"] for t in titles), "Occult Duelist")

    calendar = read_json(CANON_DIR / "calendar.json")
    months = calendar["school_year"]["months"]
    report.check("calendar.months", len(months) == 12, str(len(months)))
    report.check("calendar.periods", calendar["periods"] == ["AM", "PM", "Night"], str(calendar["periods"]))
    report.check("calendar.first_playable", calendar["school_year"]["first_playable_day"] == "2006-10-07", "")

    banned = read_json(CANON_DIR / "banned_list.json")["cards"]
    report.check("banned.count", len(banned) >= 60, str(len(banned)))
    report.check("banned.ids", all(b["card_id"] in CARD_IDS for b in banned), "")
    report.check("banned.statuses", all(
        status in {"Forbidden", "Limited", "Semi-Limited", "Unlimited"}
        for b in banned for status in b["status"].values()), "")

    exams = read_json(CANON_DIR / "exams.json")
    report.check("exams.templates", exams["written"]["question_templates_count"] >= 80,
                 str(exams["written"]["question_templates_count"]))
    report.check("exams.practical", len(exams["practical"]["objectives"]) == 7, "")

    text = read_json(CANON_DIR / "text" / "dialogue_index.json")
    report.check("text.index", len(text["entries"]) == 4527, str(len(text["entries"])))
    names = read_json(CANON_DIR / "text" / "name_table.json")
    report.check("text.name_table", names["entry_count"] == 35, str(names["entry_count"]))
    report.check("text.full_names", names["named_full_count"] == 26, str(names["named_full_count"]))
    report.check("text.short_names", names["named_short_count"] == 26, str(names["named_short_count"]))
    report.check("text.name_pointer_pools",
                 names["string_pool_checks"]["full_first_pointer_matches"]
                 and names["string_pool_checks"]["short_first_pointer_matches"],
                 str(names["string_pool_checks"]))

    # Legal audit: no ROM/save/emulator or full dialogue in the repo.
    banned_suffixes = {".gba", ".sav", ".sgm", ".state"}
    # Only audit canon-owned paths and repo-root files. The UE project's
    # pre-existing Saved/SaveGames directory is runtime output, not canon data.
    audit_roots = [TOOLS_DIR, DOCS_DIR, CANON_DIR, REPO_ROOT]
    leaked = []
    for root in audit_roots:
        candidates = root.rglob("*") if root != REPO_ROOT else root.glob("*")
        for path in candidates:
            if not path.is_file() or path.suffix.lower() not in banned_suffixes:
                continue
            if "Saved" in path.parts or ".git" in path.parts:
                continue
            leaked.append(str(path.relative_to(REPO_ROOT)))
    report.check("legal.no_rom_or_save", not leaked, str(leaked[:5]))
    dialogue_leaks = [str(p.relative_to(REPO_ROOT)) for p in (REPO_ROOT / "Tools" / "canon").rglob("dialogue_full.json")]
    report.check("legal.no_full_dialogue", not dialogue_leaks, str(dialogue_leaks))

    # Manifest hash check.
    top = read_json(CANON_DIR / "manifest.json")
    for item in top["files"]:
        path = REPO_ROOT / item["path"]
        if not path.exists():
            report.errors.append(f"manifest missing file {item['path']}")
        elif sha256_file(path) != item["sha256"]:
            report.errors.append(f"manifest hash mismatch {item['path']}")
    report.check("manifest.hashes", not any("hash mismatch" in e for e in report.errors), "")

    lines = [
        "# Canon validation report",
        "",
        f"Generated: {utc_now()}",
        "",
        f"- Errors: **{len(report.errors)}**",
        f"- Warnings: **{len(report.warnings)}**",
        "",
        "| Check | Result | Detail |",
        "| --- | --- | --- |",
    ]
    for name, result, detail in report.checks:
        lines.append(f"| `{name}` | {result} | {detail} |")
    if report.errors:
        lines += ["", "## Errors", ""] + [f"- {e}" for e in report.errors]
    if report.warnings:
        lines += ["", "## Warnings", ""] + [f"- {w}" for w in report.warnings]
    write_text(DOCS_DIR / "VALIDATION.md", "\n".join(lines) + "\n")

    print(f"checks: {len(report.checks)}  errors: {len(report.errors)}  warnings: {len(report.warnings)}")
    for error in report.errors:
        print("ERROR", error)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
