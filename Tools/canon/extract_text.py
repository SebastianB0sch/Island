"""Extract and index the GBA text system.

Verified layout (see Docs/Canon/TEXT_FORMAT.md):
  0x13F6DF0  NUL-terminated string pool (story, system, location names)
  0x14280A0  4,472 x uint32 offsets into the pool (master string index)
  0x13F0000  story-script bytecode; `05 30 <u16 id> <u8> 00` shows string id
  0x146CB14  full speaker names (26 entries)
  0x146CC32  short speaker names (21 entries)
  0x146C000-0x146D600  UI/format strings

The full dialogue text is written only to a local-only directory outside the
repository. The committed index stores hashes, lengths, control tokens and a
short preview so A03 can map keys without copying the original script.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

from canon_common import (
    CANON_DIR, DEFAULT_ROM, LOCAL_ONLY_DIR, NAME_FULL_BASE, NAME_FULL_TABLE,
    NAME_SHORT_BASE, NAME_SHORT_TABLE, NAME_TABLE_COUNT, SCRIPT_BASE, SCRIPT_END,
    TEXT_BASE, TEXT_INDEX_COUNT, TEXT_INDEX_TABLE, TITLE_BASE, UI_STRING_BASE,
    UI_STRING_END, ascii_strings, c_string, ensure_dirs, load_rom, u16, u32,
    write_json, write_text,
)

TOKEN_RE = re.compile(
    r"(\$[pPcCyYLmM][0-9]{2,5}|\$[A-Za-z][0-9]{0,5}|@[0-9]|#[nNrRkKsSeEpPbB]|#>?[0-9]+_[0-9]+|%[0-9sd])"
)


def parse_index(rom: bytes) -> list[dict]:
    entries = []
    for index in range(TEXT_INDEX_COUNT):
        rel = u32(rom, TEXT_INDEX_TABLE + index * 4)
        abs_off = TEXT_BASE + rel
        text = c_string(rom, abs_off, 8192)
        tokens = TOKEN_RE.findall(text)
        entries.append({
            "index": index,
            "offset": f"0x{abs_off:06X}",
            "length": len(text),
            "sha256": hashlib.sha256(text.encode("latin-1", errors="replace")).hexdigest(),
            "text_preview": text[:80],
            "tokens": sorted(set(tokens)),
            "speaker_refs": sorted(set(re.findall(r"\$[pP]([0-9]{2})", text))),
            "card_refs": sorted(set(re.findall(r"\$c([0-9]{4})", text, re.I))),
            "message_refs": sorted(set(re.findall(r"\$m([0-9]{5})", text))),
            "uses_title": "$L" in text,
            "uses_dorm": bool(re.search(r"\$y[0-9]", text)),
        })
    return entries


def parse_name_table(rom: bytes, table_offset: int) -> list[dict]:
    """Parse a 35-entry table of GBA pointers to name strings.

    The dialogue token `$pNN` is 1-based into this table: $p01 -> entry 0
    (Jaden), $p31 -> entry 30 (Sheppard). Unused slots point at the literal
    string "reserved.".
    """
    out = []
    for index in range(NAME_TABLE_COUNT):
        pointer = u32(rom, table_offset + index * 4)
        if not (0x08000000 <= pointer < 0x0A000000):
            out.append({"index": index, "offset": None, "name": None, "reserved": True})
            continue
        abs_off = pointer - 0x08000000
        text = c_string(rom, abs_off, 128)
        out.append({
            "index": index,
            "offset": f"0x{abs_off:06X}",
            "name": None if text == "reserved." else text,
            "reserved": text == "reserved.",
            "raw": text,
        })
    return out


def parse_script(rom: bytes) -> tuple[list[dict], list[dict]]:
    messages = []
    for off in range(SCRIPT_BASE, SCRIPT_END - 5, 2):
        if rom[off] == 0x05 and rom[off + 1] == 0x30:
            messages.append({
                "offset": f"0x{off:06X}",
                "message_id": u16(rom, off + 2),
                "arg4": rom[off + 4],
                "arg5": rom[off + 5],
            })
    # Split into readable script segments. The VM uses jumps, so this is a
    # presentation grouping, not a formal scene table.
    segments = []
    current = []
    for msg in messages:
        if current:
            prev = current[-1]
            off_gap = int(msg["offset"], 16) - int(prev["offset"], 16)
            id_gap = msg["message_id"] - prev["message_id"]
            if off_gap > 0x120 or id_gap > 0x60 or id_gap < 0:
                segments.append(current)
                current = []
        current.append(msg)
    if current:
        segments.append(current)
    out = []
    for i, segment in enumerate(segments, 1):
        out.append({
            "segment_id": f"SEG_{i:03d}",
            "start": segment[0]["offset"],
            "end": segment[-1]["offset"],
            "message_count": len(segment),
            "first_message_id": segment[0]["message_id"],
            "last_message_id": segment[-1]["message_id"],
            "messages": segment,
        })
    return messages, out


def control_code_inventory(entries: list[dict]) -> dict:
    counts: dict[str, int] = {}
    examples: dict[str, str] = {}
    for entry in entries:
        for token in entry["tokens"]:
            counts[token] = counts.get(token, 0) + 1
            examples.setdefault(token, entry["text_preview"])
    families = {
        "@N": "text colour/highlight tag (card names in descriptions and UI)",
        "$pNN / $PNN": "speaker name from the 26-entry full-name pool; 00 = player",
        "#>N_NNNN": "portrait / expression command",
        "#n": "new line (same text box)",
        "#r": "next text page / wait for confirm",
        "#k": "wait for player input",
        "$C1-$C4": "text palette / emphasis colour",
        "$yN": "dorm name substitution",
        "$L": "current duelist title",
        "$cNNNN": "card name by card id",
        "$mNNNNN": "message/string jump by id",
        "#S / #E / #P / #M1": "duel-log substitutions (spell, effect, player, monster)",
        "%s / %d / %1 / %2": "printf-style substitutions",
    }
    return {
        "counts": dict(sorted(counts.items(), key=lambda item: (-item[1], item[0]))),
        "examples": examples,
        "families": families,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    parser.add_argument("--sample-segment", default="SEG_007")
    args = parser.parse_args()

    ensure_dirs()
    LOCAL_ONLY_DIR.mkdir(parents=True, exist_ok=True)
    rom = load_rom(args.rom)

    entries = parse_index(rom)
    full_names = parse_name_table(rom, NAME_FULL_TABLE)
    short_names = parse_name_table(rom, NAME_SHORT_TABLE)
    ui_strings = ascii_strings(rom, UI_STRING_BASE, UI_STRING_END, 2)
    messages, segments = parse_script(rom)

    # Full text is local-only and never written under the repo.
    local_lines = []
    for entry in entries:
        text = c_string(rom, int(entry["offset"], 16), 8192)
        local_lines.append({
            "index": entry["index"], "offset": entry["offset"], "text": text,
        })
    local_json = LOCAL_ONLY_DIR / "dialogue_full.json"
    write_json(local_json, local_lines)

    sample = next((s for s in segments if s["segment_id"] == args.sample_segment), segments[0])
    sample_lines = []
    for msg in sample["messages"]:
        entry = entries[msg["message_id"]]
        sample_lines.append(
            f"[{msg['offset']}] id={msg['message_id']} (0x{msg['message_id']:04X}) "
            f"arg={msg['arg4']}/{msg['arg5']}\n"
            f"{c_string(rom, int(entry['offset'], 16), 8192)}\n"
        )
    sample_path = LOCAL_ONLY_DIR / f"{sample['segment_id']}_full.txt"
    write_text(sample_path, "\n".join(sample_lines))

    sample_redacted = {
        "segment_id": sample["segment_id"],
        "start": sample["start"],
        "end": sample["end"],
        "message_count": sample["message_count"],
        "messages": [
            {
                "offset": msg["offset"],
                "message_id": msg["message_id"],
                "message_hex": f"0x{msg['message_id']:04X}",
                "string_offset": entries[msg["message_id"]]["offset"],
                "string_sha256": entries[msg["message_id"]]["sha256"],
                "text_preview": entries[msg["message_id"]]["text_preview"],
                "tokens": entries[msg["message_id"]]["tokens"],
            }
            for msg in sample["messages"]
        ],
        "full_text_location": str(sample_path),
    }

    title_strings = ascii_strings(rom, TITLE_BASE, 0x146C950, 2)

    write_json(CANON_DIR / "text" / "dialogue_index.json", {
        "schema_version": 1,
        "source": {"table": f"0x{TEXT_INDEX_TABLE:06X}", "base": f"0x{TEXT_BASE:06X}",
                   "count": TEXT_INDEX_COUNT},
        "full_text_committed": False,
        "full_text_local_only": str(local_json),
        "entries": entries,
    })
    full_first_pointer = u32(rom, NAME_FULL_TABLE)
    short_first_pointer = u32(rom, NAME_SHORT_TABLE)
    write_json(CANON_DIR / "text" / "name_table.json", {
        "schema_version": 1,
        "string_pool_checks": {
            "full_base_expected": f"0x{NAME_FULL_BASE:06X}",
            "full_first_pointer": f"0x{full_first_pointer:08X}",
            "full_first_pointer_matches": full_first_pointer == 0x08000000 + NAME_FULL_BASE,
            "short_base_expected": f"0x{NAME_SHORT_BASE:06X}",
            "short_first_pointer": f"0x{short_first_pointer:08X}",
            "short_first_pointer_matches": short_first_pointer == 0x08000000 + NAME_SHORT_BASE,
        },
        "notes": [
            "Dialogue uses $pNN, 1-based: NN=01 -> full_names[0] (Jaden), NN=31 -> full_names[30] (Sheppard).",
            "NN=00 is the player name supplied at registration.",
            "Unused slots point at the literal string 'reserved.'.",
            "Blair appears twice (disguise and reveal); the engine selects by story state.",
        ],
        "full_name_table": f"0x{NAME_FULL_TABLE:06X}",
        "short_name_table": f"0x{NAME_SHORT_TABLE:06X}",
        "entry_count": NAME_TABLE_COUNT,
        "full_names": full_names,
        "short_names": short_names,
        "named_full_count": sum(1 for n in full_names if n["name"]),
        "named_short_count": sum(1 for n in short_names if n["name"]),
    })
    write_json(CANON_DIR / "text" / "ui_strings.json", {
        "schema_version": 1,
        "source": {"base": f"0x{UI_STRING_BASE:06X}", "end": f"0x{UI_STRING_END:06X}"},
        "strings": ui_strings,
    })
    write_json(CANON_DIR / "text" / "title_strings.json", {
        "schema_version": 1,
        "source": f"0x{TITLE_BASE:06X}",
        "titles": title_strings,
    })
    write_json(CANON_DIR / "text" / "dialogue_control_codes.json", {
        "schema_version": 1,
        "inventory": control_code_inventory(entries),
    })
    write_json(CANON_DIR / "text" / "script_segments.json", {
        "schema_version": 1,
        "source": {"script_base": f"0x{SCRIPT_BASE:06X}", "script_end": f"0x{SCRIPT_END:06X}"},
        "message_command": "05 30 <u16 string index> <u8 arg4> <u8 arg5>",
        "total_message_commands": len(messages),
        "unique_message_ids": len({m["message_id"] for m in messages}),
        "segments": segments,
        "sample_segment": sample_redacted,
    })

    print(f"index entries: {len(entries)}")
    print(f"name table entries: {len(full_names)} full / {len(short_names)} short; "
          f"named {sum(1 for n in full_names if n['name'])} / {sum(1 for n in short_names if n['name'])}")
    print(f"UI strings: {len(ui_strings)}  title strings: {len(title_strings)}")
    print(f"script message commands: {len(messages)}  segments: {len(segments)}")
    print(f"sample: {sample['segment_id']} ({sample['message_count']} messages)")
    print(f"local-only dialogue: {local_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
