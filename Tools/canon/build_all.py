"""Run the full canon pipeline in dependency order.

Offline path: all guide-derived facts are cached under Tools/canon/cache/.
Only the ROM and the target cards.json are required.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
STEPS = [
    "extract_cards.py",
    "extract_text.py",
    "extract_exam.py",
    "build_packs.py",
    "build_banned.py",
    "build_decks.py",
    "build_puzzles.py",
    "build_events.py",
    "build_curated.py",
    "build_dialogue_keys.py",
    "build_manifest.py",
    "build_traceability.py",
    "validate_canon.py",
]


def main() -> int:
    for step in STEPS:
        print(f"\n=== {step} ===")
        result = subprocess.run([sys.executable, str(TOOLS / step)], cwd=TOOLS.parents[1])
        if result.returncode != 0:
            print(f"FAILED: {step}")
            return result.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
