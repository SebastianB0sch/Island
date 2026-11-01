"""Focused regression tests for the Python pipeline helpers.

These cover the gate behaviour that is easy to break without touching data:
schema type typos, check/finding aggregation, duplicate JSON keys, and stable
report writing. Run with:

    python -m unittest discover -s Tools/tests -v
"""

from __future__ import annotations

import json
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "Tools"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(TOOLS / "validate"))
sys.path.insert(0, str(TOOLS / "opponents"))
sys.path.insert(0, str(TOOLS / "economy"))
sys.path.insert(0, str(TOOLS / "puzzles"))
sys.path.insert(0, str(REPO / "DuelAcademyIsland" / "Content" / "Python"))

import schema_lite  # noqa: E402
import validate_all  # noqa: E402
import import_canon_decks  # noqa: E402
import sync_canon  # noqa: E402
import generate_exams  # noqa: E402
import generate_puzzles  # noqa: E402
from dai import atomic, cache  # noqa: E402
from dai import config as pipeline_config  # noqa: E402
from dai import jsonio  # noqa: E402
from duel_academy import asset_paths  # noqa: E402


class SchemaLiteTests(unittest.TestCase):
    def test_unknown_type_is_an_error(self) -> None:
        errors = schema_lite.validate(1, {"type": "integerr"})
        self.assertTrue(errors)
        self.assertIn("unknown type", errors[0])

    def test_known_type_still_passes(self) -> None:
        self.assertEqual(schema_lite.validate(1, {"type": "integer"}), [])


class ReportTests(unittest.TestCase):
    def make_report(self) -> validate_all.Report:
        return validate_all.Report(
            root=REPO,
            data_dir=REPO / "DuelAcademyIsland" / "Content" / "Data",
            contracts_dir=REPO / "Docs" / "Contracts",
        )

    def test_failed_check_fails_result_even_without_finding(self) -> None:
        report = self.make_report()
        report.check("cards", "fail", "malformed entry")
        self.assertEqual(report.result(), "FAIL")

    def test_duplicate_check_keys_merge_and_keep_worst_status(self) -> None:
        report = self.make_report()
        report.check("cards", "pass", "cards summary")
        report.check("cards", "fail", "1 schema error")
        self.assertEqual(len(report.checks), 1)
        self.assertEqual(report.checks[0].status, "fail")
        self.assertIn("schema error", report.checks[0].summary)
        self.assertEqual(report.result(), "FAIL")


class OpponentDeckTests(unittest.TestCase):
    def test_every_runtime_deck_is_mapped_and_referenced(self) -> None:
        mapping = {entry["id"] for entry in import_canon_decks.DECK_MAP}
        runtime = {path.stem for path in import_canon_decks.RUNTIME_DIR.glob("*.json")}
        self.assertEqual(runtime, mapping)
        self.assertEqual(import_canon_decks.reference_errors(), [])


class JsonTests(unittest.TestCase):
    def test_duplicate_keys_are_rejected(self) -> None:
        report = ReportTests().make_report()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dup.json"
            path.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            self.assertIsNone(validate_all.load_json(path, report))
        self.assertTrue(any(f.code == "json_duplicate_key" for f in report.findings))

    def test_report_writer_uses_stable_lf_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.json"
            validate_all.write_report(path, {"answer": 42})
            data = path.read_bytes()
        self.assertTrue(data.endswith(b"\n"))
        self.assertNotIn(b"\r\n", data)
        self.assertEqual(json.loads(data), {"answer": 42})

    def test_pipeline_json_writer_preserves_compact_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            jsonio.write_json(path, {"b": 2, "a": 1}, separators=(",", ":"))
            data = path.read_text(encoding="utf-8")
        self.assertEqual(data, '{"b":2,"a":1}')


class JsonIoTests(unittest.TestCase):
    def test_write_is_atomic_utf8_lf_and_leaves_no_temp_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "layout.json"
            jsonio.write_json(path, {"b": 2, "a": "é"}, indent=1, trailing_newline=True)
            data = path.read_bytes()
            self.assertTrue(data.endswith(b"\n"))
            self.assertNotIn(b"\r\n", data)
            self.assertIn(b"\\u00e9", data)  # ensure_ascii defaults to True
            self.assertEqual(list(path.parent.glob("*.tmp")), [])
            self.assertEqual(jsonio.read_json(path), {"b": 2, "a": "é"})

    def test_failed_replace_keeps_previous_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            path.write_text('{"keep": true}\n', encoding="utf-8", newline="\n")
            with mock.patch.object(jsonio.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    jsonio.write_json(path, {"new": 1})
            self.assertEqual(path.read_text(encoding="utf-8"), '{"keep": true}\n')
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_serialization_failure_does_not_touch_the_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layout.json"
            path.write_text("original\n", encoding="utf-8")
            with self.assertRaises(TypeError):
                jsonio.write_json(path, {"bad": object()})
            self.assertEqual(path.read_text(encoding="utf-8"), "original\n")


class PipelinePathTests(unittest.TestCase):
    def test_config_paths_derive_from_the_repository(self) -> None:
        self.assertEqual(Path(pipeline_config.REPO_DIR), REPO)
        self.assertEqual(Path(pipeline_config.TOOLS_DIR), TOOLS)
        self.assertEqual(Path(pipeline_config.UE_PROJECT_DIR), REPO / "DuelAcademyIsland")
        self.assertEqual(Path(pipeline_config.OUT_DIR), REPO / "DuelAcademyIsland" / "SourceAssets")
        for path in (pipeline_config.OUT_DATA, pipeline_config.OUT_TEXTURES, pipeline_config.CACHE_DIR):
            self.assertTrue(Path(path).is_absolute())
            self.assertTrue(Path(path).is_relative_to(REPO))

    def test_generator_default_roots_are_portable(self) -> None:
        self.assertEqual(Path(generate_exams.ROOT), REPO)
        self.assertEqual(Path(generate_puzzles.ROOT_DEFAULT), REPO)
        self.assertTrue(Path(generate_exams.DATA).is_relative_to(REPO))
        self.assertEqual(Path(import_canon_decks.ROOT), REPO)
        self.assertEqual(Path(sync_canon.ROOT), REPO)


class AtomicGeneratorWriteTests(unittest.TestCase):
    def _assert_atomic_json(self, writer, *, ensure_ascii: bool) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "out.json"
            writer(path, {"z": 1, "a": "é"})
            data = path.read_bytes()
            expected = (json.dumps({"z": 1, "a": "é"}, indent=2, ensure_ascii=ensure_ascii) + "\n").encode("utf-8")
            self.assertEqual(data, expected)
            self.assertNotIn(b"\r\n", data)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])

    def test_economy_writer_preserves_json_dump_bytes(self) -> None:
        self._assert_atomic_json(sync_canon.write, ensure_ascii=False)

    def test_opponent_writer_preserves_json_dump_bytes(self) -> None:
        self._assert_atomic_json(import_canon_decks.write_json, ensure_ascii=False)

    def test_puzzle_writer_preserves_json_dump_bytes(self) -> None:
        self._assert_atomic_json(generate_puzzles._write_json, ensure_ascii=True)

    def test_exam_writer_preserves_json_dump_bytes(self) -> None:
        self._assert_atomic_json(generate_exams._write_json_atomic, ensure_ascii=True)


class ExamCycleTests(unittest.TestCase):
    def test_build_cycles_is_deterministic_and_complete(self) -> None:
        questions = {"exam_sets": [{"exam_id": f"EXAM_{i:02d}", "question_ids": [f"Q{i:03d}"]}
                                   for i in range(1, 13)]}
        practical_ids = ["battle", "spells", "traps", "damage", "fusion", "ritual", "special_summon",
                         "battle", "spells", "traps", "damage", "fusion"]
        practicals = {"objectives": [{"id": pid, "label": pid.title()} for pid in practical_ids]}
        first = generate_exams.build_cycles(questions, practicals)
        second = generate_exams.build_cycles(questions, practicals)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 12)
        self.assertEqual(first[0]["exam_id"], "EXAM_01")
        self.assertEqual(first[0]["timed_puzzle_id"], "P001")
        self.assertEqual(first[0]["practical_objective_id"], "battle")
        self.assertEqual(first[-1]["timed_puzzle_id"], "P100")
        self.assertEqual(first[-1]["scoring"]["max_points"], 500)

    def test_invalid_rotation_length_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            generate_exams.build_cycles({"exam_sets": []}, {"objectives": []}, timed=["P001"])


class AtomicFileTests(unittest.TestCase):
    def test_write_bytes_replaces_target_and_leaves_no_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "T_Foo.png"
            path.write_bytes(b"old")
            atomic.write_bytes(path, b"new-bytes")
            self.assertEqual(path.read_bytes(), b"new-bytes")
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["T_Foo.png"])

    def test_failed_replace_keeps_previous_bytes_and_cleans_up(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "T_Foo.png"
            path.write_bytes(b"keep")
            with mock.patch.object(atomic.os, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    atomic.write_bytes(path, b"new")
            self.assertEqual(path.read_bytes(), b"keep")
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["T_Foo.png"])

    def test_writer_failure_keeps_previous_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SK_Foo.fbx"
            path.write_bytes(b"previous")
            with self.assertRaises(RuntimeError):
                with atomic.atomic_path(path) as temp_path:
                    temp_path.write_bytes(b"partial")
                    raise RuntimeError("export failed")
            self.assertEqual(path.read_bytes(), b"previous")
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["SK_Foo.fbx"])

    def test_save_image_keeps_target_suffix_and_kwargs(self) -> None:
        class FakeImage:
            def __init__(self) -> None:
                self.seen = None

            def save(self, target, **kwargs) -> None:
                self.seen = (Path(target).suffix, kwargs)
                Path(target).write_bytes(b"image")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "T_Foo.jpg"
            image = FakeImage()
            atomic.save_image(image, path, quality=92)
            self.assertEqual(path.read_bytes(), b"image")
            self.assertEqual(image.seen, (".jpg", {"quality": 92}))

    def test_copy_file_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.glb"
            target = Path(tmp) / "cache.glb"
            source.write_bytes(b"payload")
            target.write_bytes(b"old")
            atomic.copy_file(source, target)
            self.assertEqual(target.read_bytes(), b"payload")


def _glb_bytes(payload: bytes = b"{}") -> bytes:
    chunk = struct.pack("<I4s", len(payload), b"JSON") + payload
    return b"glTF" + struct.pack("<II", 2, 12 + len(chunk)) + chunk


class CacheTests(unittest.TestCase):
    def test_source_key_is_stable_and_path_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first = Path(tmp) / "pack_a" / "tree.glb"
            second = Path(tmp) / "pack_b" / "tree.glb"
            first.parent.mkdir()
            second.parent.mkdir()
            first.write_bytes(b"a")
            second.write_bytes(b"b")
            self.assertEqual(len(cache.source_key(first)), 12)
            self.assertEqual(cache.source_key(first), cache.source_key(Path(tmp) / "." / "pack_a" / "tree.glb"))
            self.assertNotEqual(cache.source_key(first), cache.source_key(second))

    def test_cache_file_contains_stem_and_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "tree.glb"
            path = Path(cache.cache_file(Path(tmp) / "cache", source, ".glb"))
            self.assertEqual(path.suffix, ".glb")
            self.assertTrue(path.name.startswith("tree-"))
            self.assertIn(cache.source_key(source), path.name)

    def test_is_fresh_rejects_missing_empty_and_older_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.glb"
            cached = Path(tmp) / "cached.glb"
            source.write_bytes(b"source")
            cached.write_bytes(b"")
            os.utime(cached, (2_000_000_000, 2_000_000_000))
            self.assertFalse(cache.is_fresh(cached, source))  # empty
            cached.write_bytes(b"cache")
            os.utime(source, (1_600_000_000, 1_600_000_000))
            os.utime(cached, (1_700_000_000, 1_700_000_000))
            self.assertTrue(cache.is_fresh(cached, source))
            os.utime(cached, (1_500_000_000, 1_500_000_000))
            self.assertFalse(cache.is_fresh(cached, source))
            cached.unlink()
            self.assertFalse(cache.is_fresh(cached, source))

    def test_glb_validation_detects_truncated_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "good.glb"
            bad = Path(tmp) / "bad.glb"
            good.write_bytes(_glb_bytes())
            bad.write_bytes(_glb_bytes()[:-2])
            self.assertTrue(cache.is_glb(good))
            self.assertFalse(cache.is_glb(bad))
            bad.write_bytes(b"not a glb")
            self.assertFalse(cache.is_glb(bad))

    def test_require_file_names_the_missing_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.fbx"
            with self.assertRaisesRegex(FileNotFoundError, "missing.fbx"):
                cache.require_file(missing, "mesh")


class ManifestPathTests(unittest.TestCase):
    def test_source_path_accepts_forward_and_back_slashes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "Meshes" / "Characters" / "SK_Anime_Foo.fbx"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"fbx")
            self.assertEqual(Path(asset_paths.source_path(root, "Meshes/Characters/SK_Anime_Foo.fbx")), target)
            self.assertEqual(Path(asset_paths.source_path(root, r"Meshes\Characters\SK_Anime_Foo.fbx")), target)

    def test_source_path_rejects_traversal_and_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("../outside.fbx", "Meshes/../../outside.fbx", "/etc/passwd",
                        r"C:\Windows\notepad.exe", "C:relative.fbx", r"\\server\share\asset.fbx", ""):
                with self.subTest(path=bad):
                    with self.assertRaises(ValueError):
                        asset_paths.source_path(tmp, bad)

    def test_missing_sources_reports_missing_and_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ok.fbx").write_bytes(b"x")
            problems = asset_paths.missing_sources(root, ["ok.fbx", "missing.fbx", "../escape.fbx"])
            self.assertEqual(len(problems), 2)
            self.assertTrue(problems[0][1].startswith("file not found"))
            self.assertIn("escapes", problems[1][1])

    def test_asset_name_strips_package_object_suffix(self) -> None:
        self.assertEqual(asset_paths.asset_name("/Game/Dir/SK_Foo.SK_Foo"), "SK_Foo")
        self.assertEqual(asset_paths.asset_name("A_Anime_Proc_Idle"), "A_Anime_Proc_Idle")


class CastCleanupTests(unittest.TestCase):
    def manifest(self) -> dict:
        return {
            "meshes": {
                "student_m1": {"name": "SK_Anime_StudentM1", "group": "Proc"},
                "jaden": {"name": "SK_Anime_Jaden", "group": "VroidC"},
            },
            "groups": {
                "Proc": {
                    "base_mesh": {"name": "SK_Anime_StudentM1", "file": "Meshes/Characters/Anime/SK_Anime_StudentM1.fbx"},
                    "anims": {"Idle": {"name": "A_Anime_Proc_Idle"},
                              "Walk": {"name": "A_Anime_Proc_Walk"}},
                    "duel_disk": {"name": "SK_Anime_Proc_DuelDisk"},
                },
                "VroidC": {
                    "anims": {"Idle": {"name": "A_Anime_VroidC_Idle"}},
                },
            },
        }

    def test_expected_assets_include_meshes_takes_and_disks(self) -> None:
        expected = asset_paths.expected_cast_assets(self.manifest())
        self.assertEqual(expected, {
            "SK_Anime_StudentM1", "SK_Anime_Jaden", "A_Anime_Proc_Idle", "A_Anime_Proc_Walk",
            "SK_Anime_Proc_DuelDisk", "A_Anime_VroidC_Idle",
        })

    def test_only_previously_owned_cast_assets_are_stale(self) -> None:
        expected = asset_paths.expected_cast_assets(self.manifest())
        owned = set(expected) | {
            "SK_Anime_Removed", "A_Anime_OldTake",      # removed cast entries -> prune
            "SK_Student", "SM_UserProp",                 # not cast-owned -> keep
            "SK_Anime_Proc_Skeleton", "SK_Anime_Jaden_PhysicsAsset",  # importer helpers -> keep
        }
        self.assertEqual(asset_paths.stale_owned_assets(owned, expected),
                         ["A_Anime_OldTake", "SK_Anime_Removed"])

    def test_empty_manifest_never_prunes(self) -> None:
        self.assertEqual(asset_paths.stale_owned_assets({"SK_Anime_Old"}, set()), [])

    def test_case_only_rename_is_not_stale(self) -> None:
        # Unreal asset paths are case-insensitive; a case-only change must not
        # delete the asset the current import just created.
        owned = {"sk_anime_studentm1", "a_anime_proc_idle"}
        expected = {"SK_Anime_StudentM1", "A_Anime_Proc_Idle"}
        self.assertEqual(asset_paths.stale_owned_assets(owned, expected), [])

    def test_ownership_state_round_trip_and_validation(self) -> None:
        document = asset_paths.state_document(["B", "A", "A"])
        self.assertEqual(asset_paths.owned_names(document), {"A", "B"})
        with self.assertRaises(ValueError):
            asset_paths.owned_names({"version": 99, "assets": []})
        with self.assertRaises(ValueError):
            asset_paths.owned_names({"version": 1})

    def test_state_writer_uses_lf_and_leaves_no_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "Saved" / "cast_assets.json"
            asset_paths.write_json_atomic(path, asset_paths.state_document(["SK_Anime_A"]))
            data = path.read_bytes()
            self.assertTrue(data.endswith(b"\n"))
            self.assertNotIn(b"\r\n", data)
            self.assertEqual(json.loads(data)["assets"], ["SK_Anime_A"])
            self.assertEqual(sorted(p.name for p in path.parent.iterdir()), ["cast_assets.json"])


if __name__ == "__main__":
    unittest.main()
