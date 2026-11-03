#!/usr/bin/env python3
"""Build the 12 monthly exam cycles from the existing question sets and catalog."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # Tools/, for the shared common package
from common.jsonio import read_json, write_json  # noqa: E402
from common.paths import DATA_DIR as DATA  # noqa: E402

questions = read_json(DATA / "Exams" / "questions.json")
practicals = read_json(DATA / "Exams" / "practicals.json")
sets = {s["exam_id"]: s for s in questions["exam_sets"]}
objectives = {o["id"]: o for o in practicals["objectives"]}

TIMED_PUZZLES = ["P001", "P006", "P021", "P026", "P041", "P046", "P061", "P066", "P081", "P086", "P070", "P100"]
PRACTICAL_ORDER = ["battle", "spells", "traps", "damage", "fusion", "ritual", "special_summon",
                   "battle", "spells", "traps", "damage", "fusion"]

out = {
    "schema_version": 1,
    "description": "12 monthly exam cycles linking written sets, timed puzzles and practical objectives.",
    "max_points": 500,
    "pass_mark": 300,
    "scoring_ref": "scoring.json",
    "cycles": cycles,
}
# exams.json is stored ASCII-escaped (json.dump's default); keep the bytes stable.
write_json(DATA / "Exams" / "exams.json", out, ensure_ascii=True)
print(f"wrote {len(cycles)} exam cycles")
