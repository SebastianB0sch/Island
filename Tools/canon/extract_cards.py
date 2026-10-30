"""Verify the target 1,200-card database against the GBA ROM.

Usage:
    python Tools/canon/extract_cards.py [--rom PATH]

Writes:
    DuelAcademyIsland/Content/Data/Canon/cards_manifest.json
    DuelAcademyIsland/Content/Data/Canon/card_name_overrides.json
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from collections import Counter
from pathlib import Path

from canon_common import (
    CANON_DIR, CARD_STATS_BASE, DEFAULT_ROM, TARGET_CARDS, TOTAL_CARDS,
    canonical_card_record, card_fingerprint, count_by, ensure_dirs, load_rom,
    read_json, sha256_bytes, sha256_file, utc_now, write_json,
)

COMPARE_FIELDS = [
    "id", "name", "card_type", "monster_type", "subtype",
    "attribute", "level", "atk", "def", "description",
]


def rom_header(rom: bytes) -> dict[str, str]:
    title = rom[0xA0:0xAC].decode("ascii", errors="replace").strip("\x00 ")
    code = rom[0xAC:0xB0].decode("ascii", errors="replace")
    maker = rom[0xB0:0xB2].decode("ascii", errors="replace")
    return {"title": title, "game_code": code, "maker_code": maker}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    args = parser.parse_args()

    ensure_dirs()
    rom = load_rom(args.rom)
    target = read_json(TARGET_CARDS)
    if not isinstance(target, list) or len(target) != TOTAL_CARDS:
        raise SystemExit(f"target cards.json must contain {TOTAL_CARDS} records")

    rom_cards = [canonical_card_record(rom, card_id) for card_id in range(1, TOTAL_CARDS + 1)]
    target_by_id = {int(card["id"]): card for card in target}

    differences: list[dict] = []
    for expected in rom_cards:
        actual = target_by_id.get(expected["id"])
        if actual is None:
            differences.append({"id": expected["id"], "field": "*", "rom": "present", "target": "missing"})
            continue
        for field in COMPARE_FIELDS:
            if expected[field] != actual.get(field):
                differences.append({
                    "id": expected["id"], "field": field,
                    "rom": expected[field], "target": actual.get(field),
                })
    extra_ids = sorted(set(target_by_id) - {c["id"] for c in rom_cards})

    per_card_hashes = {
        str(card["id"]): card_fingerprint(card) for card in rom_cards
    }
    canonical_digest = hashlib.sha256(
        "\n".join(per_card_hashes[str(i)] for i in range(1, TOTAL_CARDS + 1)).encode("ascii")
    ).hexdigest()

    # One known non-ASCII ROM name: card 212 uses two raw bytes (F2 A4) that
    # the game renders as a Greek alpha. The target DB preserves the bytes as
    # U+FFFD, so they compare equal byte-for-byte but are not reader-friendly.
    non_ascii_names = [
        {"id": card["id"], "raw_name": card["name"],
         "suggested_display_name": "Kuwagata α"}
        for card in rom_cards if any(ord(ch) > 127 for ch in card["name"])
    ]

    manifest = {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {
            "rom": str(args.rom),
            "rom_sha256": sha256_bytes(rom),
            "rom_size": len(rom),
            "header": rom_header(rom),
            "card_tables": {
                "stats": f"0x{CARD_STATS_BASE:06X}",
                "names": "0xF25690 (offsets 0xF2A68C)",
                "descriptions": "0xF2B950 (offsets 0xF58294)",
            },
        },
        "target": {
            "path": TARGET_CARDS.relative_to(CANON_DIR.parents[2]).as_posix(),
            "sha256": sha256_file(TARGET_CARDS),
            "records": len(target),
        },
        "verification": {
            "status": "exact" if not differences and not extra_ids else "mismatch",
            "fields_compared": COMPARE_FIELDS,
            "differences": differences,
            "difference_count": len(differences),
            "extra_target_ids": extra_ids,
            "notes": [
                "Name and description strings are decoded latin-1 exactly like the ROM.",
                "Card descriptions are compared after removing @N colour tags.",
                "The target DB preserves the ROM byte order and the dummy card offsets.",
            ],
        },
        "id_range": [1, TOTAL_CARDS],
        "counts": {
            "total": len(rom_cards),
            "by_card_type": count_by(rom_cards, "card_type"),
            "by_attribute": count_by(rom_cards, "attribute"),
            "by_monster_type": count_by(rom_cards, "monster_type"),
            "by_subtype": count_by(rom_cards, "subtype"),
            "by_level": count_by(rom_cards, "level"),
        },
        "canonical_hash": {
            "algorithm": "sha256",
            "scope": "per-card sha256 over id|name|card_type|monster_type|subtype|attribute|level|atk|def|description",
            "value": canonical_digest,
        },
        "non_ascii_names": non_ascii_names,
        "per_card_sha256": per_card_hashes,
    }
    write_json(CANON_DIR / "cards_manifest.json", manifest)

    overrides = {
        "schema_version": 1,
        "notes": [
            "Display-only overrides. The runtime database keeps ROM bytes for byte-stable verification.",
            "Only apply these in UI/text rendering, never in card identity matching.",
        ],
        "overrides": [
            {"card_id": item["id"], "rom_name": item["raw_name"],
             "display_name": item["suggested_display_name"],
             "reason": "non-ASCII alpha rendered as U+FFFD by latin-1"}
            for item in non_ascii_names
        ],
    }
    write_json(CANON_DIR / "card_name_overrides.json", overrides)

    print(f"ROM: {args.rom}")
    print(f"cards: {len(rom_cards)}  target: {len(target)}")
    print(f"differences: {len(differences)}  extra target ids: {len(extra_ids)}")
    print(f"canonical hash: {canonical_digest}")
    print(f"card types: {manifest['counts']['by_card_type']}")
    if differences:
        for diff in differences[:20]:
            print("DIFF", diff)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
