#!/usr/bin/env python3
"""Build the 12 monthly exam cycles from the existing question sets and catalog."""
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "DuelAcademyIsland", "Content", "Data")
questions = json.load(open(os.path.join(DATA, "Exams", "questions.json"), encoding="utf-8"))
practicals = json.load(open(os.path.join(DATA, "Exams", "practicals.json"), encoding="utf-8"))
sets = {s["exam_id"]: s for s in questions["exam_sets"]}
objectives = {o["id"]: o for o in practicals["objectives"]}

timed = ["P001", "P006", "P021", "P026", "P041", "P046", "P061", "P066", "P081", "P086", "P070", "P100"]
practical_order = ["battle", "spells", "traps", "damage", "fusion", "ritual", "special_summon",
                   "battle", "spells", "traps", "damage", "fusion"]
cycles = []
for index in range(1, 13):
    exam_id = f"EXAM_{index:02d}"
    question_set = sets[exam_id]
    practical_id = practical_order[index - 1]
    cycles.append({
        "exam_id": exam_id,
        "month_index": index,
        "written_set_id": exam_id,
        "question_ids": question_set["question_ids"],
        "timed_puzzle_id": timed[index - 1],
        "practical_objective_id": practical_id,
        "practical_focus": objectives[practical_id]["label"],
        "scoring": {
            "max_points": 500,
            "pass_mark": 300,
            "sections": {"written": 200, "timed": 100, "practical": 200},
        },
        "pass_mark": 300,
        "confidence": "low",
        "source": "A07 cycle assembly from questions.json sets, practicals.json objectives and the generated puzzle catalog; exact GBA monthly assignment is not extracted.",
        "notes": "500-point cycle: 10 written questions (200), one timed puzzle (100), one practical objective (200).",
    })

out = {
    "schema_version": 1,
    "description": "12 monthly exam cycles linking written sets, timed puzzles and practical objectives.",
    "max_points": 500,
    "pass_mark": 300,
    "scoring_ref": "scoring.json",
    "cycles": cycles,
}
with open(os.path.join(DATA, "Exams", "exams.json"), "w", encoding="utf-8") as handle:
    json.dump(out, handle, indent=2)
    handle.write("\n")
print(f"wrote {len(cycles)} exam cycles")
