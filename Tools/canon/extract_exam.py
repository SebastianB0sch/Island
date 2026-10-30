"""Extract the written-exam question bank and practical-exam definitions.

The text bank at 0x1430F2C..0x1434522 is plain ASCII with NUL terminators.
It contains 90 question templates and a shared answer/option pool. The
binary records at 0x1430BE0..0x1430F00 are still partially decoded; their
raw bytes are preserved in the output with an explicit confidence marker.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from canon_common import (
    CANON_DIR, DEFAULT_ROM, EXAM_TEXT_BASE, EXAM_TEXT_END, EXAM_TEXT_START,
    ascii_strings, ensure_dirs, load_rom, u32, write_json, utc_now,
)

PRACTICALS = [
    ("practical_1", "Practical Exam 1 - Battle", "Battle"),
    ("practical_2", "Practical Exam 2 - Spells", "Spells"),
    ("practical_3", "Practical Exam 3 - Traps", "Traps"),
    ("practical_4", "Practical Exam 4 - Damage", "Damage"),
    ("practical_5", "Practical Exam 5 - Fusion", "Fusion"),
    ("practical_6", "Practical Exam 6 - Ritual", "Ritual"),
    ("practical_7", "Practical Exam 7 - Special Summon", "Special Summon"),
]

GERARD_QUIZ = [
    {"q": "What is Jaden's dorm?", "a": "Slifer Red"},
    {"q": "What is Lyman Banner always hugging?", "a": "A cat (Pharaoh)"},
    {"q": "Who was the first person you met in this game?", "a": "Sheppard"},
    {"q": "Who can you challenge via e-mail?", "a": "Chumley Huffington (guide also lists Bastion in one translation)"},
    {"q": "How many hairs does Sheppard have?", "a": "0 (zero)"},
    {"q": "Who is Syrus' brother?", "a": "Zane Truesdale"},
    {"q": "Who is Jaden's favorite monster?", "a": "Winged Kuriboh"},
    {"q": "What is the name of this game?", "a": "Yu-Gi-Oh! GX Duel Academy"},
    {"q": "What do you air out on a fine day?", "a": "Deck"},
]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rom", type=Path, default=DEFAULT_ROM)
    args = parser.parse_args()
    ensure_dirs()
    rom = load_rom(args.rom)

    strings = ascii_strings(rom, EXAM_TEXT_START, EXAM_TEXT_END, 3)
    labels = {"Dummy Examination", "Answer", "Wrong Answer 1", "Wrong Answer 2", "Wrong Answer 3"}
    questions, options = [], []
    for item in strings:
        text = item["text"].strip()
        if text in labels:
            continue
        if text.endswith("?") and len(text) > 8:
            questions.append(item)
        elif len(text) > 2:
            options.append(item)

    # The 136-entry array at 0x1430BE0 mixes card ids and parameters. Preserve
    # every raw value; expose the valid card-id subset separately.
    raw_pool = []
    card_pool = []
    for offset in range(0x1430BE0, 0x1430E00, 4):
        value = u32(rom, offset)
        raw_pool.append({
            "offset": f"0x{offset:06X}",
            "value": value,
            "valid_card_id": 1 <= value <= 1200,
        })
        if 1 <= value <= 1200:
            card_pool.append({"offset": f"0x{offset:06X}", "card_id": value})

    # 64 x 28-byte question records addressed from 0x1430E00.
    records = []
    for i in range(64):
        entry_off = 0x1430E00 + i * 4
        rel = u32(rom, entry_off)
        abs_off = EXAM_TEXT_BASE + rel
        raw = rom[abs_off:abs_off + 28]
        records.append({
            "index": i,
            "table_offset": f"0x{entry_off:06X}",
            "relative_offset": f"0x{rel:06X}",
            "absolute_offset": f"0x{abs_off:06X}",
            "raw_hex": raw.hex(),
            "uint16": [
                int.from_bytes(raw[j:j + 2], "little") for j in range(0, len(raw), 2)
            ],
            "confidence": "low",
            "note": "28-byte record; 16-bit fields look like text/card ids but the mapping is not yet proven.",
        })

    data = {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "source": {
            "rom": str(args.rom),
            "text_base": f"0x{EXAM_TEXT_BASE:06X}",
            "text_range": [f"0x{EXAM_TEXT_START:06X}", f"0x{EXAM_TEXT_END:06X}"],
            "guide": "https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events",
        },
        "written": {
            "questions_per_exam": 10,
            "question_templates_count": len(questions),
            "question_templates": [
                {"offset": q["offset_hex"], "template": q["text"],
                 "placeholders": [p for p in ("%1", "%2", "%3") if p in q["text"]]}
                for q in questions
            ],
            "answer_option_pool_count": len(options),
            "answer_option_pool": [
                {"offset": o["offset_hex"], "text": o["text"]} for o in options
            ],
            "mapping_status": "templates extracted; per-question correct-answer mapping not proven",
            "confidence": "high for templates, low for individual answer keys",
        },
        "question_card_pool": {
            "raw_entry_count": len(raw_pool),
            "valid_card_id_count": len(card_pool),
            "cards": card_pool,
            "raw_entries": raw_pool,
            "confidence": "medium",
            "note": "Contiguous uint32 array at 0x1430BE0; 27 of 136 entries are valid card ids, the rest are parameters or pointers.",
        },
        "binary_question_records": {
            "count": len(records),
            "records": records,
            "confidence": "low",
        },
        "practical": {
            "objectives": [
                {"id": pid, "name": name, "theme": theme}
                for pid, name, theme in PRACTICALS
            ],
            "opponent": "mimicry",
            "confidence": "high",
            "source": "ROM strings at 0x146C23E..0x146C2DA; opponent from guide",
        },
        "scoring": {
            "max_score": 500,
            "components": ["written", "timed_duel", "practical"],
            "pass_mark": None,
            "pass_mark_notes": "Guide sources disagree between 250 and 300; verify in-game before freezing.",
            "confidence": "low",
        },
        "gerard_quiz": {
            "questions": GERARD_QUIZ,
            "reward_dp": 1000,
            "source": "Yugipedia Events (Event 21) and GameFAQs Event FAQ",
            "confidence": "medium",
        },
        "cycle": {
            "exams_per_year": 12,
            "exam_day": "Friday",
            "exam_week_rule": "unresolved; monthly Friday, exact week not proven",
            "confidence": "medium",
        },
    }
    write_json(CANON_DIR / "exams.json", data)
    print(f"question templates: {len(questions)}")
    print(f"answer options: {len(options)}")
    print(f"question card pool: {len(card_pool)}")
    print(f"binary records: {len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
