"""Build the top-level canon manifest with hashes and coverage counts."""
from __future__ import annotations

import sys
from pathlib import Path

from canon_common import (
    CANON_DIR, DEFAULT_ROM, REPO_ROOT, ensure_dirs, load_rom, read_json,
    sha256_bytes, sha256_file, utc_now, write_json,
)

FILES = [
    "cards_manifest.json", "card_name_overrides.json", "calendar.json",
    "titles.json", "packs.json", "opponents.json", "decks.json",
    "puzzles.json", "exams.json", "events.json", "banned_list.json",
    "dp_rules.json", "emails.json", "locations.json", "dialogue_keys.json",
    "text/dialogue_index.json", "text/name_table.json", "text/ui_strings.json",
    "text/title_strings.json", "text/dialogue_control_codes.json",
    "text/script_segments.json",
]


def count(path: Path, data) -> int | None:
    name = path.name
    if name == "cards_manifest.json":
        return data.get("counts", {}).get("total")
    if name == "packs.json":
        return len(data.get("packs", []))
    if name == "opponents.json":
        return len(data.get("opponents", []))
    if name == "decks.json":
        return len(data.get("decks", []))
    if name == "puzzles.json":
        return len(data.get("puzzles", []))
    if name == "events.json":
        return len(data.get("events", []))
    if name == "banned_list.json":
        return len(data.get("cards", []))
    if name == "titles.json":
        return len(data.get("titles", []))
    if name == "calendar.json":
        return len(data.get("school_year", {}).get("months", []))
    if name == "exams.json":
        return data.get("written", {}).get("question_templates_count")
    if name == "dialogue_index.json":
        return len(data.get("entries", []))
    if name == "name_table.json":
        return data.get("full_name_count")
    if name == "script_segments.json":
        return len(data.get("segments", []))
    return None


def main() -> int:
    ensure_dirs()
    rom = load_rom(DEFAULT_ROM)
    files = []
    for rel in FILES:
        path = CANON_DIR / rel
        if not path.exists():
            print(f"missing: {path}")
            continue
        data = read_json(path)
        files.append({
            "path": f"DuelAcademyIsland/Content/Data/Canon/{rel}",
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "records": count(path, data),
        })

    packs = read_json(CANON_DIR / "packs.json")
    events = read_json(CANON_DIR / "events.json")
    puzzles = read_json(CANON_DIR / "puzzles.json")
    decks = read_json(CANON_DIR / "decks.json")
    opponents = read_json(CANON_DIR / "opponents.json")
    titles = read_json(CANON_DIR / "titles.json")
    banned = read_json(CANON_DIR / "banned_list.json")
    exams = read_json(CANON_DIR / "exams.json")
    text = read_json(CANON_DIR / "text" / "dialogue_index.json")

    manifest = {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "project": "DuelAcademyIsland / Yu-Gi-Oh! GX: Duel Academy GBA port",
        "source": {
            "rom_sha256": sha256_bytes(rom),
            "rom_size": len(rom),
            "rom_header": rom[0xA0:0xB0].decode("ascii", errors="replace").strip("\x00 "),
            "target_cards": "DuelAcademyIsland/Content/Data/cards.json",
            "target_cards_sha256": sha256_file(REPO_ROOT / "DuelAcademyIsland" / "Content" / "Data" / "cards.json"),
        },
        "coverage": {
            "cards": 1200,
            "packs": len(packs["packs"]),
            "pack_unique_cards": packs["summary"]["total_unique_card_ids"],
            "events": len(events["events"]),
            "opponents": len(opponents["opponents"]),
            "decks": len(decks["decks"]),
            "complete_decks": decks["summary"]["complete"],
            "puzzles": len(puzzles["puzzles"]),
            "puzzles_with_solution": puzzles["summary"]["with_solution"],
            "banned_limited_cards": len(banned["cards"]),
            "titles": len(titles["titles"]),
            "written_question_templates": exams["written"]["question_templates_count"],
            "dialogue_strings": len(text["entries"]),
        },
        "confidence": {
            "cards": "exact (ROM byte comparison)",
            "packs": "high for price/pool, low for odds",
            "events": "high/medium (public guide + ROM text evidence)",
            "opponents": "medium (roster/archetype); 25 named + 3 event duelists",
            "decks": "mixed: 16 complete, 15 partial (14 with explicit unknown slots, 1 unverified), 6 fully unknown",
            "puzzles": "high for solutions, unknown for setups",
            "titles": "mixed; see per-title confidence",
            "banned_list": "high (public three-year table)",
            "text": "high for offsets/control codes; answer-key mapping still open",
        },
        "files": files,
        "legal": {
            "rom_committed": False,
            "save_committed": False,
            "full_dialogue_committed": False,
            "local_only_note": "Full dialogue and sample scenes are written outside the repository by extract_text.py.",
        },
    }
    write_json(CANON_DIR / "manifest.json", manifest)
    print(f"manifest files: {len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
