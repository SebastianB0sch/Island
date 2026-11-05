"""Guards for the one-shot story migration scripts.

Importing a migration must never rewrite authored data. Each script keeps its
work behind main(), and the shared writer is atomic UTF-8/LF JSON.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
STORY = REPO / "Tools" / "story"
sys.path.insert(0, str(STORY))

import story_common  # noqa: E402

DATA_FILES = [
    REPO / "DuelAcademyIsland" / "Content" / "Data" / "Story" / "events.json",
    REPO / "DuelAcademyIsland" / "Content" / "Data" / "Story" / "scenes" / "full_campaign.json",
    REPO / "DuelAcademyIsland" / "Content" / "Data" / "Story" / "dialogue" / "full_campaign.json",
    REPO / "DuelAcademyIsland" / "Content" / "Data" / "Story" / "opening.json",
    REPO / "DuelAcademyIsland" / "Content" / "Data" / "World" / "spawns.json",
    REPO / "DuelAcademyIsland" / "Content" / "Data" / "World" / "anchors.json",
    REPO / "DuelAcademyIsland" / "Content" / "Data" / "Opponents" / "roster.json",
    REPO / "DuelAcademyIsland" / "Content" / "Data" / "Opponents" / "decks" / "sheppard_year1.json",
    REPO / "DuelAcademyIsland" / "Content" / "Data" / "Canon" / "decks.json",
]


def _migration_scripts() -> list[Path]:
    return sorted(path for path in STORY.glob("*.py") if path.name != "story_common.py")


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location(f"_story_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class StoryMigrationStructureTests(unittest.TestCase):
    def test_every_migration_has_a_main_guard(self) -> None:
        for path in _migration_scripts():
            with self.subTest(script=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                self.assertTrue(
                    any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in tree.body),
                    f"{path.name} has no main()",
                )
                source = path.read_text(encoding="utf-8")
                self.assertIn('if __name__ == "__main__":', source)

    def test_no_migration_writes_at_module_scope(self) -> None:
        for path in _migration_scripts():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in tree.body:
                if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
                    continue
                call = node.value
                self.assertFalse(
                    isinstance(call.func, ast.Attribute)
                    and call.func.attr in {"write_text", "write_json", "dump"},
                    f"{path.name}:{node.lineno} writes at import time",
                )


class StoryMigrationImportTests(unittest.TestCase):
    def test_importing_every_migration_leaves_data_untouched(self) -> None:
        before = {}
        for path in DATA_FILES:
            if path.exists():
                stat = path.stat()
                before[path] = (stat.st_size, stat.st_mtime_ns, path.read_bytes())
        for path in _migration_scripts():
            _load_module(path)
        for path, (size, mtime, payload) in before.items():
            with self.subTest(file=path.name):
                self.assertEqual(path.stat().st_size, size)
                self.assertEqual(path.stat().st_mtime_ns, mtime)
                self.assertEqual(path.read_bytes(), payload)


class StoryWriterTests(unittest.TestCase):
    def test_write_json_is_utf8_lf_and_leaves_no_temp_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "out.json"
            story_common.write_json(path, {"b": 2, "a": "é"})
            data = path.read_bytes()
        self.assertTrue(data.endswith(b"\n"))
        self.assertNotIn(b"\r\n", data)
        self.assertEqual(json.loads(data), {"b": 2, "a": "é"})
        self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_serialization_failure_keeps_the_previous_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            path.write_text("original\n", encoding="utf-8")
            with self.assertRaises(TypeError):
                story_common.write_json(path, {"bad": object()})
            self.assertEqual(path.read_text(encoding="utf-8"), "original\n")

    def test_failed_replace_keeps_the_previous_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.json"
            path.write_text("original\n", encoding="utf-8")
            with mock.patch.object(story_common.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    story_common.write_json(path, {"new": 1})
            self.assertEqual(path.read_text(encoding="utf-8"), "original\n")
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
