"""Build the top-level canon manifest with hashes and coverage counts.

The normal mode requires the ROM because it also records the ROM identity and
coverage. The extraction tools themselves are deterministic, but packaging may
sanitize the workstation ROM path in ``cards_manifest.json``/``exams.json``.
That sanitization changes the file bytes without changing any record, so
``--refresh-hashes`` re-hashes the published files while refusing to hide a
real content or record-count change.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

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

MANIFEST_PATH_PREFIX = "DuelAcademyIsland/Content/Data/Canon"


class ManifestDriftError(RuntimeError):
    """Raised when a hash-only refresh would hide a content change."""


def count(path: Path, data: Any) -> int | None:
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


def build_file_entries(canon_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    """Return manifest file entries plus the list of missing relative names."""
    files: list[dict[str, Any]] = []
    missing: list[str] = []
    for rel in FILES:
        path = canon_dir / rel
        if not path.exists():
            missing.append(rel)
            continue
        data = read_json(path)
        files.append({
            "path": f"{MANIFEST_PATH_PREFIX}/{rel}",
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "records": count(path, data),
        })
    return files, missing


def refresh_manifest_hashes(
    manifest_path: Path,
    canon_dir: Path,
) -> dict[str, Any]:
    """Refresh only the file hash/byte/record entries in an existing manifest.

    A refresh is intentionally narrower than a full build: it refuses to run
    when the file set or any ``records`` count differs from the current
    manifest, because that means the data changed rather than merely being
    sanitized or re-serialized. The caller must run the full build (with the
    ROM) in that case.
    """
    manifest = read_json(manifest_path)
    if not isinstance(manifest, dict) or not isinstance(manifest.get("files"), list):
        raise ManifestDriftError("manifest.json has no files array")
    old_entries = {
        item.get("path"): item
        for item in manifest["files"]
        if isinstance(item, dict) and isinstance(item.get("path"), str)
    }
    if len(old_entries) != len(manifest["files"]):
        raise ManifestDriftError("manifest.json contains malformed or duplicate file entries")

    files, missing = build_file_entries(canon_dir)
    if missing:
        raise ManifestDriftError(f"canon data is missing: {', '.join(missing)}")

    expected_paths = {entry["path"] for entry in files}
    if set(old_entries) != expected_paths:
        added = sorted(expected_paths - set(old_entries))
        removed = sorted(set(old_entries) - expected_paths)
        raise ManifestDriftError(
            f"manifest file set changed (added={added}, removed={removed}); run the full build"
        )

    for entry in files:
        previous = old_entries[entry["path"]]
        if previous.get("records") != entry["records"]:
            raise ManifestDriftError(
                f"{entry['path']} records changed from {previous.get('records')!r} "
                f"to {entry['records']!r}; run the full build"
            )

    manifest["files"] = files
    manifest["generated_utc"] = utc_now()
    write_json(manifest_path, manifest)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or refresh the canon manifest.")
    parser.add_argument(
        "--refresh-hashes",
        action="store_true",
        help="re-hash published canon files without requiring the ROM (fails on record changes)",
    )
    args = parser.parse_args(argv)

    if args.refresh_hashes:
        try:
            manifest = refresh_manifest_hashes(CANON_DIR / "manifest.json", CANON_DIR)
        except (OSError, ValueError, ManifestDriftError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        print(f"refreshed manifest hashes: {len(manifest['files'])} files")
        return 0

    ensure_dirs()
    rom = load_rom(DEFAULT_ROM)
    files, missing = build_file_entries(CANON_DIR)
    if missing:
        for rel in missing:
            print(f"error: missing canon file {rel}", file=sys.stderr)
        return 1

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
