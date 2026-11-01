#!/usr/bin/env python3
"""Small regression suite for the effect data pipeline.

Run:
    python Tools/effects/test_effects.py
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audit
import build_manifest
import effect_data as data
import validate_effects


class EffectDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cards = data.load_cards()
        # Keep the test read-only: build the manifest in memory instead of
        # rewriting the committed data file as a side effect of running tests.
        cls.manifest = build_manifest.build(write=False)

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

    def test_ids_from_only_reads_card_fields(self) -> None:
        self.assertEqual(data._ids_from([1, 2, 1200]), {1, 2, 1200})
        self.assertEqual(data._ids_from({"cards": [1, 2], "amount": 500}), {1, 2})
        self.assertEqual(
            data._ids_from({"rewards": [{"type": "dp", "amount": 500}]}), set()
        )
        self.assertEqual(
            data._ids_from({"reward": {"card_id": 42, "count": 3}}), {42}
        )

    def test_duplicate_script_files_fail_loudly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            (directory / "1.json").write_text('{"card_id": 1}', encoding="utf-8")
            (directory / "2.json").write_text('{"card_id": 1}', encoding="utf-8")
            with mock.patch.object(data, "SCRIPTS_DIR", directory):
                with self.assertRaises(ValueError):
                    data.script_files()

    def test_recipe_totals_are_derived_from_cards(self) -> None:
        cards = [
            {"card_type": "Fusion Monster"},
            {"card_type": "Ritual Monster"},
            {"card_type": "Spell"},
        ]
        self.assertEqual(audit._expected_recipe_totals(cards), (1, 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
