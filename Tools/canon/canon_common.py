"""Shared helpers for the Duel Academy GX canon extraction toolkit.

All paths resolve from this file, so the scripts work from any CWD.
The ROM is never copied into the repository; it is read in place.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
CANON_DIR = REPO_ROOT / "DuelAcademyIsland" / "Content" / "Data" / "Canon"
DOCS_DIR = REPO_ROOT / "Docs" / "Canon"
TOOLS_DIR = REPO_ROOT / "Tools" / "canon"
CACHE_DIR = TOOLS_DIR / "cache"
LOCAL_ONLY_DIR = Path(
    os.environ.get(
        "GX_CANON_LOCAL_DIR",
        str(REPO_ROOT / "Tools" / "canon" / ".local_only"),
    )
)

# Never hard-code a workstation path. Set GX_ROM to the local ROM before
# running an extraction tool; the ROM itself is never committed.
DEFAULT_ROM = Path(os.environ.get("GX_ROM", "GX_ROM.gba"))
TARGET_CARDS = REPO_ROOT / "DuelAcademyIsland" / "Content" / "Data" / "cards.json"

ROM_SIZE = 32 * 1024 * 1024
CARD_STATS_BASE = 0xF243CC
CARD_NAME_BASE = 0xF25690
CARD_NAME_TABLE = 0xF2A68C
CARD_DESC_BASE = 0xF2B950
CARD_DESC_TABLE = 0xF58294
TOTAL_CARDS = 1200

TEXT_BASE = 0x13F6DF0
TEXT_INDEX_TABLE = 0x14280A0
TEXT_INDEX_COUNT = 4527
SCRIPT_BASE = 0x13F0000
SCRIPT_END = 0x13F6DF0
EXAM_TEXT_BASE = 0x1430F10
EXAM_TEXT_START = 0x1430F2C
EXAM_TEXT_END = 0x1434600
NAME_FULL_BASE = 0x146CB14
NAME_SHORT_BASE = 0x146CC32
NAME_FULL_TABLE = 0x17F0BCC
NAME_SHORT_TABLE = 0x17F0C5C
NAME_TABLE_COUNT = 35
UI_STRING_BASE = 0x146C000
UI_STRING_END = 0x146D600
TITLE_BASE = 0x146C858

ATTRIBUTES = {
    0: "NONE", 1: "LIGHT", 2: "DARK", 3: "WATER",
    4: "FIRE", 5: "EARTH", 6: "WIND", 7: "DIVINE",
}
MONSTER_TYPES = {
    1: "Dragon", 2: "Zombie", 3: "Fiend", 4: "Pyro", 5: "Sea Serpent", 6: "Rock",
    7: "Machine", 8: "Fish", 9: "Dinosaur", 10: "Insect", 11: "Beast",
    12: "Beast-Warrior", 13: "Plant", 14: "Aqua", 15: "Warrior",
    16: "Winged Beast", 17: "Fairy", 18: "Spellcaster", 19: "Thunder",
    20: "Reptile", 21: "Trap", 22: "Spell",
}
MONSTER_SUBTYPES = {0: "Normal", 1: "Effect", 2: "Fusion", 3: "Ritual"}
SPELL_ICONS = {0: "Normal", 4: "Field", 6: "Equip", 8: "Continuous", 10: "Quick-Play"}
TRAP_ICONS = {0: "Normal", 2: "Counter", 8: "Continuous"}


def ensure_dirs() -> None:
    for path in (CANON_DIR, DOCS_DIR, TOOLS_DIR, CACHE_DIR, LOCAL_ONLY_DIR):
        path.mkdir(parents=True, exist_ok=True)


def load_rom(path: Path | str | None = None) -> bytes:
    rom_path = Path(path) if path else DEFAULT_ROM
    if not rom_path.exists():
        raise FileNotFoundError(
            f"ROM not found at {rom_path}. Set GX_ROM to the legally obtained ROM."
        )
    data = rom_path.read_bytes()
    if len(data) != ROM_SIZE:
        raise ValueError(f"Expected 32 MiB ROM, got {len(data)} bytes")
    return data


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write(value)


def u16(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<H", rom, offset)[0]


def u32(rom: bytes, offset: int) -> int:
    return struct.unpack_from("<I", rom, offset)[0]


def c_string(rom: bytes, offset: int, limit: int = 4096) -> str:
    end = rom.find(b"\x00", offset, offset + limit)
    if end < 0:
        end = offset + limit
    return rom[offset:end].decode("latin-1", errors="replace")


def ascii_strings(
    data: bytes, start: int, end: int, min_length: int = 2
) -> list[dict[str, Any]]:
    """Return runs of printable ASCII with their ROM offsets."""
    out: list[dict[str, Any]] = []
    run = bytearray()
    run_off = start
    for i in range(start, min(end, len(data))):
        byte = data[i]
        if 32 <= byte < 127:
            if not run:
                run_off = i
            run.append(byte)
        else:
            if len(run) >= min_length:
                out.append(
                    {"offset": run_off, "offset_hex": f"0x{run_off:06X}",
                     "text": run.decode("ascii")}
                )
            run = bytearray()
    if len(run) >= min_length:
        out.append(
            {"offset": run_off, "offset_hex": f"0x{run_off:06X}",
             "text": run.decode("ascii")}
        )
    return out


def parse_card_dword(word: int) -> dict[str, Any]:
    monster_type_id = (word >> 20) & 0x1F
    monster_type = MONSTER_TYPES.get(monster_type_id, f"Type_{monster_type_id}")
    attribute = ATTRIBUTES.get((word >> 29) & 0x07, "NONE")
    if monster_type == "Spell":
        return {
            "card_type": "Spell",
            "subtype": SPELL_ICONS.get((word >> 16) & 0x0F, "Normal"),
            "attribute": "NONE", "monster_type": "Spell",
            "level": 0, "atk": 0, "def": 0,
        }
    if monster_type == "Trap":
        return {
            "card_type": "Trap",
            "subtype": TRAP_ICONS.get((word >> 16) & 0x0F, "Normal"),
            "attribute": "NONE", "monster_type": "Trap",
            "level": 0, "atk": 0, "def": 0,
        }
    subtype = MONSTER_SUBTYPES.get((word >> 18) & 0x03, "Normal")
    return {
        "card_type": f"{subtype} Monster",
        "subtype": subtype,
        "attribute": attribute,
        "monster_type": monster_type,
        "level": (word >> 25) & 0x0F,
        "atk": ((word >> 9) & 0x1FF) * 10,
        "def": (word & 0x1FF) * 10,
    }


def clean_card_text(text: str) -> str:
    """Strip @N colour tags from card descriptions, matching the target DB."""
    out = []
    i = 0
    while i < len(text):
        if text[i] == "@" and i + 1 < len(text) and text[i + 1].isdigit():
            i += 2
            continue
        out.append(text[i])
        i += 1
    return "".join(out).strip()


def canonical_card_record(rom: bytes, card_id: int) -> dict[str, Any]:
    stats = parse_card_dword(u32(rom, CARD_STATS_BASE + card_id * 4))
    name_off = u32(rom, CARD_NAME_TABLE + card_id * 4)
    name_abs = CARD_NAME_BASE + name_off
    raw_name = c_string(rom, name_abs, 128)
    desc_off = u32(rom, CARD_DESC_TABLE + card_id * 4)
    desc_abs = CARD_DESC_BASE + desc_off
    raw_desc = c_string(rom, desc_abs, 2048)
    return {
        "id": card_id,
        "name": raw_name,
        "card_type": stats["card_type"],
        "monster_type": stats["monster_type"],
        "subtype": stats["subtype"],
        "attribute": stats["attribute"],
        "level": stats["level"],
        "atk": stats["atk"],
        "def": stats["def"],
        "description": clean_card_text(raw_desc),
        "_raw_description": raw_desc,
        "_name_offset": f"0x{name_abs:06X}",
        "_desc_offset": f"0x{desc_abs:06X}",
        "_dword": f"0x{u32(rom, CARD_STATS_BASE + card_id * 4):08X}",
    }


def card_fingerprint(card: dict[str, Any]) -> str:
    fields = (
        "id", "name", "card_type", "monster_type", "subtype",
        "attribute", "level", "atk", "def", "description",
    )
    payload = "\x1f".join(str(card.get(field, "")) for field in fields)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def count_by(records: Iterable[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        key = str(record.get(field, ""))
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def dump_struct_table(rom: bytes, start: int, count: int, width: int = 4) -> list[int]:
    return [u32(rom, start + i * width) for i in range(count)]
