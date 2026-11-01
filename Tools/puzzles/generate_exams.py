#!/usr/bin/env python3
"""Build the 12 monthly exam cycles from the existing question sets and catalog."""
import argparse
import json
import os
import sys
import tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "DuelAcademyIsland", "Content", "Data")

TIMED_PUZZLES = ["P001", "P006", "P021", "P026", "P041", "P046", "P061", "P066", "P081", "P086", "P070", "P100"]
PRACTICAL_ORDER = ["battle", "spells", "traps", "damage", "fusion", "ritual", "special_summon",
                   "battle", "spells", "traps", "damage", "fusion"]


def build_cycles(questions, practicals, timed=None, practical_order=None):
    """Return the 12 exam-cycle records for the given question/practical documents."""
    timed = list(TIMED_PUZZLES if timed is None else timed)
    practical_order = list(PRACTICAL_ORDER if practical_order is None else practical_order)
    if len(timed) != 12 or len(practical_order) != 12:
        raise ValueError("the exam rotation must list exactly 12 timed puzzles and 12 practicals")
    sets = {s["exam_id"]: s for s in questions["exam_sets"]}
    objectives = {o["id"]: o for o in practicals["objectives"]}
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
    return cycles


def _write_json_atomic(path, value):
    """Write the same bytes as json.dump(indent=2) + newline, via a temp file."""
    payload = json.dumps(value, indent=2) + "\n"
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the 12 monthly exam cycles.")
    parser.add_argument("--root", default=ROOT, help="repository root (defaults to this checkout)")
    args = parser.parse_args(argv)
    data = os.path.join(os.path.abspath(args.root), "DuelAcademyIsland", "Content", "Data")
    try:
        with open(os.path.join(data, "Exams", "questions.json"), encoding="utf-8") as handle:
            questions = json.load(handle)
        with open(os.path.join(data, "Exams", "practicals.json"), encoding="utf-8") as handle:
            practicals = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot load exam inputs: {exc}", file=sys.stderr)
        return 2
    cycles = build_cycles(questions, practicals)
    out = {
        "schema_version": 1,
        "description": "12 monthly exam cycles linking written sets, timed puzzles and practical objectives.",
        "max_points": 500,
        "pass_mark": 300,
        "scoring_ref": "scoring.json",
        "cycles": cycles,
    }
    _write_json_atomic(os.path.join(data, "Exams", "exams.json"), out)
    print(f"wrote {len(cycles)} exam cycles")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
