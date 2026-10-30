#!/usr/bin/env python3
"""Small regression suite for the effect data pipeline.

Run:
    python Tools/effects/test_effects.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_manifest
import effect_data as data
import validate_effects


class EffectDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cards = data.load_cards()
        cls.manifest = build_manifest.build(write=True)

    def test_manifest_covers_every_card(self) -> None:
        entries = self.manifest["cards"]
        self.assertEqual(len(entries), 1200)
        self.assertEqual({entry["id"] for entry in entries}, set(range(1, 1201)))
        self.assertEqual(
            self.manifest["summary"]["total"],
            len(self.cards),
        )

    def test_tier_zero_is_green(self) -> None:
        tier0 = [entry for entry in self.manifest["cards"] if entry["tier"] == 0]
        self.assertEqual(len(tier0), 137)
        bad = [
            entry
            for entry in tier0
            if entry["status"] not in ("scripted", "vanilla")
        ]
        self.assertEqual(bad, [])

    def test_tier_one_is_scripted(self) -> None:
        tier1 = [entry for entry in self.manifest["cards"] if entry["tier"] == 1]
        self.assertEqual(len(tier1), 10)
        self.assertTrue(all(entry["status"] == "scripted" for entry in tier1))

    def test_all_scripts_and_recipes_validate(self) -> None:
        report, stats = validate_effects.validate()
        self.assertEqual(report.errors, [])
        self.assertEqual(stats["fusion"]["total"], 76)
        self.assertEqual(stats["ritual"]["total"], 22)
        self.assertEqual(stats["fusion"]["resolved"], 75)
        self.assertEqual(stats["ritual"]["resolved"], 22)

    def test_unknown_operation_is_rejected_by_schema(self) -> None:
        schema = data.load_json(data.SCHEMA_PATH)
        payload = data.load_json(data.SCRIPTS_DIR / "29.json")
        payload["scripts"][0]["operations"][0]["op"] = "teleport"
        errors = validate_effects.validate_json_schema(payload, schema)
        self.assertTrue(any("teleport" in error for error in errors))

    def test_manifest_build_is_deterministic(self) -> None:
        first = build_manifest.build(write=False)
        second = build_manifest.build(write=False)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main(verbosity=2)
