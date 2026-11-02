"""Validate the canon dataset and emit a human-readable report.

Run after build_all.py. Exits non-zero on hard errors; warnings are recorded
in Docs/Canon/VALIDATION.md.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter

from build_manifest import FILES as MANIFEST_FILES, MANIFEST_PATH_PREFIX
from canon_common import (
    CANON_DIR, DOCS_DIR, REPO_ROOT, TOOLS_DIR, LOCAL_ONLY_DIR, card_fingerprint,
    read_json, sha256_bytes, sha256_file, utc_now, write_text,
)

CARD_IDS = set(range(1, 1201))


def is_under(path: Path, root: Path) -> bool:
    """True when ``path`` is ``root`` or one of its descendants."""
    try:
        path.resolve().relative_to(root.expanduser().resolve())
        return True
    except ValueError:
        return False


def deck_record_digest(deck: dict) -> str:
    """Mirror ``build_decks.sha_deck``: digest over the deck identity fields."""
    payload = {key: deck.get(key) for key in ("id", "name", "type", "opponent", "main", "extra")}
    return sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))


def pack_record_digest(record: dict) -> str:
    """Mirror ``build_packs``: digest over the record without its own ``sha256``.

    The builder hashes the record exactly as written, minus the digest field,
    so dropping only ``sha256`` reproduces it byte for byte.
    """
    payload = {key: value for key, value in record.items() if key != "sha256"}
    return sha256_bytes(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def puzzle_record_digest(puzzle: dict) -> str:
    """Mirror ``build_puzzles``: digest over the puzzle id and step texts."""
    payload = {
        "id": puzzle.get("id"),
        "steps": [step.get("text") for step in puzzle.get("solution_steps", [])],
    }
    return sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))


def manifest_hash_errors(manifest_path: Path, repo_root: Path) -> list[str]:
    """Return every missing/mismatched/duplicate manifest file entry."""
    errors: list[str] = []
    if not manifest_path.is_file():
        return [f"manifest missing {manifest_path}"]
    try:
        manifest = read_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"manifest unreadable {manifest_path}: {exc}"]
    files = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(files, list):
        return [f"manifest {manifest_path} has no files array"]

    seen: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append(f"manifest has a malformed file entry: {item!r}")
            continue
        rel = item["path"]
        if rel in seen:
            errors.append(f"manifest lists {rel} more than once")
            continue
        seen.add(rel)
        path = repo_root / rel
        if not path.is_file():
            errors.append(f"manifest missing file {rel}")
            continue
        expected = item.get("sha256")
        if not isinstance(expected, str) or len(expected) != 64:
            errors.append(f"manifest entry {rel} has an invalid sha256")
        elif sha256_file(path) != expected:
            errors.append(f"manifest hash mismatch {rel}")
        size = item.get("bytes")
        if isinstance(size, int) and not isinstance(size, bool) and size != path.stat().st_size:
            errors.append(f"manifest size mismatch {rel} ({size} != {path.stat().st_size})")

    expected_paths = {f"{MANIFEST_PATH_PREFIX}/{rel}" for rel in MANIFEST_FILES}
    missing_entries = sorted(expected_paths - seen)
    if missing_entries:
        errors.append(f"manifest omits published file(s): {missing_entries}")
    unexpected = sorted(seen - expected_paths)
    if unexpected:
        errors.append(f"manifest lists unexpected file(s): {unexpected}")
    return errors


def collect_dialogue_leaks() -> list[str]:
    """Full-dialogue JSONs committed under Tools/canon (relative to the repo).

    extract_text.py is supported to write the full dossier into the documented
    local-only directory (Tools/canon/.local_only by default, or the
    GX_CANON_LOCAL_DIR override); the gate only rejects one committed anywhere
    else.
    """
    return [
        str(path.relative_to(REPO_ROOT))
        for path in (REPO_ROOT / "Tools" / "canon").rglob("dialogue_full.json")
        if not is_under(path, LOCAL_ONLY_DIR)
    ]


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate the canon dataset.")
    parser.add_argument(
        "--report",
        type=Path,
        nargs="?",
        const=DOCS_DIR / "VALIDATION.md",
        default=None,
        help="write the Markdown report to this path "
             "(no value: Docs/Canon/VALIDATION.md). No report is written by "
             "default; the doc refresh is a deliberate step because it "
             "changes the committed file.",
    )
    # Kept for older invocations (CI used to pass it): reports are now off by
    # default, so this flag is a no-op.
    parser.add_argument("--no-report", action="store_true", help="ignored; no report is written unless --report is given")
    args = parser.parse_args(argv)

    report = Report()
    cards = read_json(CANON_DIR.parent / "cards.json")
    card_ids = {int(c["id"]) for c in cards}
    report.check("cards.count", len(cards) == 1200 and card_ids == CARD_IDS,
                 f"{len(cards)} records, ids 1..1200")
    manifest = read_json(CANON_DIR / "cards_manifest.json")
    report.check("cards.verified", manifest["verification"]["status"] == "exact",
                 f"{manifest['verification']['difference_count']} differences")
    report.check("cards.hash", len(manifest["canonical_hash"]["value"]) == 64,
                 manifest["canonical_hash"]["value"][:16] + "...")

    # Per-record digests: cards.json must still reproduce every per-card
    # fingerprint and the canonical digest published in cards_manifest.json.
    per_card_expected: dict[str, str] | None = manifest.get("per_card_sha256")
    if isinstance(per_card_expected, dict):
        fingerprint_errors: list[int] = []
        canonical_payload: list[str] = []
        for card in cards:
            expected = per_card_expected.get(str(card["id"]))
            if expected is None:
                fingerprint_errors.append(int(card["id"]))
                continue
            actual = card_fingerprint(card)
            canonical_payload.append(actual)
            if actual != expected:
                fingerprint_errors.append(int(card["id"]))
        if len(canonical_payload) == len(cards):
            canonical_actual = sha256_bytes("\n".join(canonical_payload).encode("ascii"))
        else:
            canonical_actual = "incomplete card set"
        report.check("cards.fingerprints", not fingerprint_errors,
                     f"{len(fingerprint_errors)} card digest(s) mismatched or absent"
                     + (f" e.g. {fingerprint_errors[:5]}" if fingerprint_errors else ""))
        report.check("cards.canonical_digest", canonical_actual == manifest["canonical_hash"]["value"],
                     "recomputed from the committed cards.json")
    else:
        report.check("cards.fingerprints", False, "cards_manifest.json has no per_card_sha256 map")

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

    pack_without_digest = [p["id"] for p in pack_records if not p.get("sha256")]
    pack_digest_errors = [
        p["id"] for p in pack_records
        if p.get("sha256") and pack_record_digest(p) != p["sha256"]
    ]
    report.check("packs.record_digests", not pack_digest_errors,
                 f"{len(pack_digest_errors)} mismatched, {len(pack_without_digest)} missing records")
    report.warn("packs.record_digests", not pack_without_digest,
                f"{len(pack_without_digest)} pack record(s) without a digest: {pack_without_digest}")
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

    opponents_doc = read_json(CANON_DIR / "opponents.json")
    opponents = opponents_doc["opponents"]
    opponent_ids = {o["id"] for o in opponents}
    report.check("opponents.count", len(opponents) == 28, str(len(opponents)))
    report.check("opponents.ids_unique", len(opponent_ids) == len(opponents), "")
    report.check("opponents.named_duelists", opponents_doc.get("named_duelists") == 25,
                 str(opponents_doc.get("named_duelists")))
    report.check("opponents.event_duelists", opponents_doc.get("event_duelists") == 3,
                 str(opponents_doc.get("event_duelists")))
    event_opponent_ids = {"jinzo", "goblin_king", "sheppard"}
    report.check("opponents.event_ids", event_opponent_ids <= opponent_ids,
                 str(sorted(event_opponent_ids - opponent_ids)))

    decks_doc = read_json(CANON_DIR / "decks.json")
    decks = decks_doc["decks"]
    deck_ids = {d["id"] for d in decks}
    report.check("decks.count", len(decks) == 37, str(len(decks)))
    report.check("decks.ids_unique", len(deck_ids) == len(decks), "")
    statuses = Counter(d.get("status", "unknown") for d in decks)
    report.check("decks.statuses", statuses["complete"] + statuses["partial"] + statuses["unknown"] == len(decks),
                 str(dict(statuses)))
    generic_shell = decks_doc.get("generic_shell", {}).get("cards", [])
    for deck in decks:
        for cid in deck["main"] + deck["extra"]:
            if cid not in CARD_IDS:
                report.errors.append(f"deck {deck['id']} references invalid card {cid}")
        report.check(f"decks.{deck['id']}.counts",
                     deck["main_count"] == len(deck["main"]) and deck["extra_count"] == len(deck["extra"]),
                     f"main {deck['main_count']}/{len(deck['main'])}, extra {deck['extra_count']}/{len(deck['extra'])}")
        report.check(f"decks.{deck['id']}.size_bounds", 0 <= deck["main_count"] <= 60,
                     f"main {deck['main_count']}")
        report.check(f"decks.{deck['id']}.extra", deck["extra_count"] <= 15,
                     f"extra {deck['extra_count']}")
        if deck["complete"]:
            report.check(f"decks.{deck['id']}.size", 40 <= deck["main_count"] <= 60,
                         f"main {deck['main_count']}")
            report.check(f"decks.{deck['id']}.resolved", deck.get("unresolved_slots", 0) == 0,
                         f"unresolved {deck.get('unresolved_slots', 0)}")
        else:
            unresolved = deck.get("unresolved_slots", 0)
            report.check(f"decks.{deck['id']}.unresolved", unresolved >= 0, f"unresolved {unresolved}")
            if deck.get("status") == "partial" and deck["main_count"] > 0:
                report.check(f"decks.{deck['id']}.reachable", deck["main_count"] + unresolved >= 40,
                             f"{deck['main_count']} known + {unresolved} unknown")
        counts = Counter(deck["main"])
        report.warn(f"decks.{deck['id']}.copies", max(counts.values(), default=0) <= 3,
                    "copy limit check is against the 3-copy rule, not the year list")
        if deck.get("use_generic_shell"):
            missing = Counter(generic_shell) - Counter(deck["main"])
            report.check(f"decks.{deck['id']}.generic_shell", not missing,
                         f"missing generic cards {dict(missing)}")
    unknown_decks = [d["id"] for d in decks if d.get("status") == "unknown"]
    report.warn("decks.unknown_explicit", True, f"{len(unknown_decks)} decks explicitly unknown: {unknown_decks}")

    deck_without_digest = [d["id"] for d in decks if not d.get("sha256")]
    deck_digest_errors = [
        d["id"] for d in decks
        if d.get("sha256") and deck_record_digest(d) != d["sha256"]
    ]
    report.check("decks.record_digests", not deck_digest_errors,
                 f"{len(deck_digest_errors)} mismatched, {len(deck_without_digest)} missing records")
    report.warn("decks.record_digests", not deck_without_digest,
                f"{len(deck_without_digest)} deck record(s) without a digest: {deck_without_digest}")

    # Event references: opponents, decks, tournament/partner constructs.
    for event in events:
        for duel in event.get("duels", []):
            if not isinstance(duel, dict):
                continue
            opponent = duel.get("opponent")
            if opponent and opponent not in opponent_ids:
                report.errors.append(f"{event['id']} duel references unknown opponent {opponent}")
            deck_id = duel.get("deck")
            if deck_id and deck_id not in deck_ids:
                report.errors.append(f"{event['id']} duel references unknown deck {deck_id}")
            if duel.get("deck_kind") == "timed_puzzle":
                if deck_id:
                    report.errors.append(f"{event['id']} timed puzzle must not reference a 40-card deck")
            for construct_key in ("tournament", "partner_pool"):
                construct = duel.get(construct_key)
                if not isinstance(construct, dict):
                    continue
                participants = construct.get("participants", [])
                if participants and not set(participants) <= opponent_ids:
                    report.errors.append(f"{event['id']} {construct_key} has unknown participants "
                                         f"{sorted(set(participants) - opponent_ids)}")
                if construct.get("participants_source") == "ranked_roster":
                    report.check(f"events.{event['id']}.{construct_key}.source", True, "ranked roster")
    for construct in decks_doc.get("event_constructs", []):
        participants = construct.get("participants", [])
        if participants and not set(participants) <= opponent_ids:
            report.errors.append(f"event construct {construct['id']} has unknown participants "
                                 f"{sorted(set(participants) - opponent_ids)}")

    puzzles = read_json(CANON_DIR / "puzzles.json")["puzzles"]
    report.check("puzzles.count", len(puzzles) == 100, str(len(puzzles)))
    report.check("puzzles.levels", all(sum(1 for p in puzzles if p["level"] == level) == 20 for level in range(1, 6)), "")
    report.check("puzzles.solutions", all(p["solution_steps"] for p in puzzles),
                 f"{sum(1 for p in puzzles if not p['solution_steps'])} missing")
    report.check("puzzles.card_ids", all(set(p["solution_card_ids"]) <= CARD_IDS for p in puzzles), "")

    puzzle_without_digest = [p["id"] for p in puzzles if not p.get("sha256")]
    puzzle_digest_errors = [
        p["id"] for p in puzzles
        if p.get("sha256") and puzzle_record_digest(p) != p["sha256"]
    ]
    report.check("puzzles.record_digests", not puzzle_digest_errors,
                 f"{len(puzzle_digest_errors)} mismatched, {len(puzzle_without_digest)} missing records")
    report.warn("puzzles.record_digests", not puzzle_without_digest,
                f"{len(puzzle_without_digest)} puzzle record(s) without a digest: {puzzle_without_digest}")

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
    cycle = exams.get("cycle", {})
    evidence = cycle.get("exam_week_evidence", {})
    report.warn("exams.exam_week",
                cycle.get("exam_week_rule", "").startswith("unresolved")
                and bool(evidence.get("confirmed")) and bool(evidence.get("conflicting")),
                cycle.get("exam_week_question", "exam week question missing"))

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
    dialogue_leaks = collect_dialogue_leaks()
    report.check("legal.no_full_dialogue", not dialogue_leaks, str(dialogue_leaks))

    # Manifest hash check. This is a hard error: the manifest is the published
    # hash inventory for the canonical extracts.
    manifest_errors = manifest_hash_errors(CANON_DIR / "manifest.json", REPO_ROOT)
    report.errors.extend(manifest_errors)
    report.check("manifest.hashes", not manifest_errors, f"{len(manifest_errors)} issue(s)")

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
    if args.report:
        report_path = args.report.expanduser()
        if not report_path.is_absolute():
            report_path = Path.cwd() / report_path
        try:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            write_text(report_path, "\n".join(lines) + "\n")
        except OSError as exc:
            print(f"error: cannot write report {report_path}: {exc}", file=sys.stderr)
            return 2

    print(f"checks: {len(report.checks)}  errors: {len(report.errors)}  warnings: {len(report.warnings)}")
    for error in report.errors:
        print("ERROR", error)
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
