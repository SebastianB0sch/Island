"""Focused regression tests for the Python pipeline helpers.

These cover the gate behaviour that is easy to break without touching data:
schema type typos, check/finding aggregation, duplicate JSON keys, stable
report writing, cast-manifest merges (partial builds), VRM/glTF parsing under
corruption, the stamped terrain cache, the atomic WAV writer, gltf-transform
subprocess handling, and the build_island stage dependency guard. Run with:

    python -m unittest discover -s Tools/tests -v
"""

from __future__ import annotations

import json
import math
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
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
from dai.anime import manifest, roster, vrm  # noqa: E402
from dai.anime.vrm import alpha_modes, read_vrm, target_names  # noqa: E402
from dai import audio  # noqa: E402
import numpy as np  # noqa: E402
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
        self.assertEqual(asset_paths.asset_name("A_Anime_Cast_Idle"), "A_Anime_Cast_Idle")


class CastCleanupTests(unittest.TestCase):
    def manifest(self) -> dict:
        return {
            "meshes": {
                "student_m1": {"name": "SK_Anime_StudentM1", "group": "Cast"},
                "jaden": {"name": "SK_Anime_Jaden", "group": "ArtistA"},
            },
            "groups": {
                "Cast": {
                    "base_mesh": {"name": "SK_Anime_StudentM1", "file": "Meshes/Characters/Anime/SK_Anime_StudentM1.fbx"},
                    "anims": {"Idle": {"name": "A_Anime_Cast_Idle"},
                              "Walk": {"name": "A_Anime_Cast_Walk"}},
                    "duel_disk": {"name": "SK_Anime_Cast_DuelDisk"},
                },
                "ArtistA": {
                    "anims": {"Idle": {"name": "A_Anime_ArtistA_Idle"}},
                },
            },
        }

    def test_expected_assets_include_meshes_takes_and_disks(self) -> None:
        expected = asset_paths.expected_cast_assets(self.manifest())
        self.assertEqual(expected, {
            "SK_Anime_StudentM1", "SK_Anime_Jaden", "A_Anime_Cast_Idle", "A_Anime_Cast_Walk",
            "SK_Anime_Cast_DuelDisk", "A_Anime_ArtistA_Idle",
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
        owned = {"sk_anime_studentm1", "a_anime_cast_idle"}
        expected = {"SK_Anime_StudentM1", "A_Anime_Cast_Idle"}
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


class NpcRosterTests(unittest.TestCase):
    def markers(self) -> list[dict]:
        return [
            dict(loc=[0.0, 0.0, 0.0], group="academy", dorm="slifer", cast="student_m1", tint=True),
            dict(loc=[100.0, 0.0, 0.0], group="academy", dorm="ra", cast="student_m1", tint=True),
            dict(loc=[200.0, 0.0, 0.0], group="academy", dorm="white", cast="student_m1", tint=True),
            dict(loc=[300.0, 0.0, 0.0], group="academy", dorm="white", cast="student_m1", tint=True),
            dict(loc=[400.0, 0.0, 0.0], group="obelisk_girls", dorm="obelisk", cast="student_f1", tint=True),
            dict(loc=[500.0, 0.0, 0.0], group="obelisk_girls", dorm="obelisk", cast="student_f2", tint=True),
            dict(loc=[600.0, 0.0, 0.0], group="harbor", dorm="ra", cast="student_m1", tint=True),
            dict(loc=[700.0, 0.0, 0.0], group="harbor", dorm="ra", cast="student_m1", tint=True),
        ]

    def test_every_generic_marker_gets_a_unique_identity(self) -> None:
        markers = self.markers()
        roster.assign_uniques(markers)
        names = [m["name"] for m in markers]
        self.assertEqual(len(names), len(set(names)))
        for marker in markers:
            self.assertEqual(len(marker["lines"]), 3)
            self.assertEqual(len(marker["hair"]), 3)
            self.assertTrue(marker["roster_id"])
            first = marker["name"].split()[0]
            self.assertTrue(any(marker["name"] in line or first in line for line in marker["lines"]))

    def test_assignment_is_deterministic_and_preserves_named_cast(self) -> None:
        first = self.markers()
        second = self.markers()
        roster.assign_uniques(first)
        roster.assign_uniques(second)
        self.assertEqual([(m["name"], m["lines"], m["hair"]) for m in first],
                         [(m["name"], m["lines"], m["hair"]) for m in second])

        jaden = dict(loc=[0.0, 0.0, 0.0], group="slifer", dorm="slifer", cast="jaden",
                     tint=False, name="Jaden Yuki", lines=["Test line."], scale=0.964)
        roster.assign_uniques([jaden])
        self.assertEqual(jaden["name"], "Jaden Yuki")
        self.assertEqual(jaden["lines"], ["Test line."])

    def test_staff_identities_match_their_base_mesh(self) -> None:
        markers = self.markers()
        roster.assign_uniques(markers)
        for marker in markers:
            if marker["dorm"] == "white":
                self.assertIn(marker["cast"], ("student_m1", "student_f1", "student_f2"))
                self.assertNotEqual(marker["name"], "Student")

    def test_no_marker_carries_a_marketplace_look(self) -> None:
        # The licensed marketplace character pack was removed: every NPC is one of the
        # project's own atelier designs, and a stale key from an older layout is dropped.
        markers = self.markers()
        markers[0]["fab_look"] = "fab_male_a"
        roster.assign_uniques(markers)
        self.assertFalse([m for m in markers if "fab_look" in m])


class AtelierCastTests(unittest.TestCase):
    """The cast is built from the project's own designs (no third-party base model)."""

    GARMENTS = {"top", "skirt", "pants", "legwear", "shoes", "collar", "bow", "tie", "belt", "band", "gloves",
                "cape", "scarf", "emblem", "buttons", "hairband", "glasses", "hairbow"}

    def test_every_cast_slot_resolves_to_a_look(self) -> None:
        from dai.anime import cast, looks, portrait_cast
        from dai.anime.atelier import designs
        table = designs.all_designs()
        entries = dict(portrait_cast.all_entries(), **cast.all_entries())
        self.assertIn(cast.PLAYER, entries)
        for cid, entry in entries.items():
            self.assertIn(entry["design"], table, cid)             # generated fallback
            self.assertIn(cid, looks.LOOKS, cid)                   # VRoid-based look
            self.assertEqual(entry.get("model"), looks.LOOKS[cid]["model"], cid)
            self.assertGreater(entry["scale"], 0.8, cid)
            self.assertLess(entry["scale"], 1.15, cid)

    def test_looks_use_registered_bases_and_known_morphs(self) -> None:
        import json
        from dai.anime import looks
        with open(os.path.join(TOOLS, "thirdparty", "registry", "anime.json"), encoding="utf-8") as fp:
            reg = json.load(fp)
        morphs = {"Blink", "Joy", "Angry", "Sorrow", "Surprised", "Fun", "EyeJoy", "BrowAngry", "BrowSorrow"}
        for cid, spec in looks.LOOKS.items():
            self.assertIn(spec["model"], reg["anime_models"], cid)
            self.assertEqual(spec["base_height"], reg["anime_models"][spec["model"]]["height"], cid)
            self.assertLessEqual(set(spec.get("expression", {})), morphs, cid)
            self.assertLessEqual(set(spec.get("tint", ())), {"jacket", "hair"}, cid)

    def test_designs_are_complete(self) -> None:
        from dai.anime.atelier import designs
        for key, design in designs.all_designs().items():
            self.assertTrue(key[:1].isupper() and key.isalnum(), key)
            self.assertIn("style", design["hair"], key)
            self.assertEqual(len(design["hair"]["color"]), 3, key)
            self.assertTrue(design["outfit"], key)
            for kind, params in design["outfit"]:
                self.assertIn(kind, self.GARMENTS, f"{key}: {kind}")
                self.assertIsInstance(params, dict)
            for part in design.get("tint", ()):
                self.assertIn(part, ("jacket", "hair"), key)

    def test_generic_students_keep_their_runtime_tints(self) -> None:
        from dai.anime import cast
        entries = cast.all_entries()
        self.assertEqual(entries["student_m1"]["tint"], ["jacket", "hair"])
        self.assertEqual(entries["student_f1"]["tint"], ["hair"])
        self.assertEqual(cast.generic_for(True), ["student_f1", "student_f2"])
        self.assertEqual(cast.generic_for(False), ["student_m1"])



# ---------------------------------------------------------------------------
# Blender-dependent modules are unit-tested with stub bpy / bmesh / mathutils:
# dai.thirdparty only touches them inside function bodies, so an empty module
# object suffices for import.  Nothing is stubbed when a real bpy wheel exists.
def _install_blender_stubs() -> None:
    import importlib.util
    import types

    if "bpy" in sys.modules or importlib.util.find_spec("bpy") is not None:
        return
    for name in ("bpy", "bmesh"):
        sys.modules.setdefault(name, types.ModuleType(name))
    module = sys.modules.setdefault("mathutils", types.ModuleType("mathutils"))

    def stub(name_attr):
        class _NeverCall:
            def __call__(self, *args, **kwargs):
                raise AssertionError(f"mathutils.{name_attr} used inside a unit test")
        return _NeverCall()

    for attr in ("Euler", "Matrix", "Vector"):
        if not hasattr(module, attr):
            setattr(module, attr, stub(attr))


def _load_build_island_module():
    """Tools/build_island.py imported without the dai package tree executing."""
    import importlib.util

    path = TOOLS / "build_island.py"
    spec = importlib.util.spec_from_file_location("python_pipeline_build_island", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _StubbedThirdpartyMixin:
    """Mixin loading dai.thirdparty with the Blender stubs installed."""

    @classmethod
    def setUpClass(cls) -> None:
        _install_blender_stubs()
        from dai import thirdparty
        cls.tp = thirdparty


class MergePartialManifestTests(unittest.TestCase):
    """G1: a partial (only=...) cast build must publish the FULL manifest."""

    @staticmethod
    def full_cast() -> dict:
        return {
            "player": "jaden",
            "groups": {
                "Cast": {
                    "base_mesh": {"name": "SK_Anime_StudentM1", "file": "Meshes/Characters/Anime/SK_Anime_StudentM1.fbx"},
                    "anims": {"Idle": {"name": "A_Anime_Cast_Idle"}},
                },
                "ArtistA": {
                    "anims": {"Idle": {"name": "A_Anime_ArtistA_Idle"}},
                    "duel_disk": {"name": "SK_Anime_ArtistA_DuelDisk", "file": "Meshes/Characters/Anime/SK_Anime_ArtistA_DuelDisk.fbx"},
                },
            },
            "meshes": {
                "student_m1": {"name": "SK_Anime_StudentM1", "group": "Cast"},
                "jaden": {"name": "SK_Anime_Jaden", "group": "ArtistA", "file": "Meshes/Characters/Anime/SK_Anime_Jaden.fbx"},
                "alexis": {"name": "SK_Anime_Alexis", "group": "ArtistA", "file": "Meshes/Characters/Anime/SK_Anime_Alexis.fbx"},
            },
            "materials": {"M_Anime_StudentM1_Hair": {"kind": "toon"}, "M_Anime_Jaden_Top": {"kind": "toon"}},
        }

    def test_subset_build_leaves_the_full_set_represented(self) -> None:
        previous = self.full_cast()
        rebuilt = {
            "player": "jaden",
            "groups": {"ArtistA": {"anims": {"Idle": {"name": "A_Anime_ArtistA_Idle_R" }},
                                  "duel_disk": {"name": "SK_Anime_ArtistA_DuelDisk", "file": "Meshes/Characters/Anime/SK_Anime_ArtistA_DuelDisk.fbx"}}},
            "meshes": {"jaden": {"name": "SK_Anime_Jaden", "group": "ArtistA",
                                 "file": "Meshes/Characters/Anime/SK_Anime_Jaden_2.fbx"}},
            "materials": {"M_Anime_Jaden_Top": {"kind": "toon", "fill": 0.5}},
        }
        merged = manifest.merge_partial_manifests(previous, rebuilt)

        # no member dropped: the importer's stale-cast cleanup sees the whole cast
        self.assertEqual(set(merged["meshes"]), {"student_m1", "jaden", "alexis"})
        self.assertEqual(set(merged["groups"]), {"Cast", "ArtistA"})
        # rebuilt entries win
        self.assertEqual(merged["meshes"]["jaden"]["file"], "Meshes/Characters/Anime/SK_Anime_Jaden_2.fbx")
        self.assertEqual(merged["groups"]["ArtistA"]["anims"]["Idle"]["name"], "A_Anime_ArtistA_Idle_R")
        # untouched members + their materials survive untouched
        self.assertEqual(merged["meshes"]["student_m1"], previous["meshes"]["student_m1"])
        self.assertEqual(merged["meshes"]["alexis"], previous["meshes"]["alexis"])
        self.assertEqual(merged["groups"]["Cast"], previous["groups"]["Cast"])
        self.assertEqual(merged["materials"],
                         {**previous["materials"], **rebuilt["materials"]})
        # extra top-level keys / player come from the newer document
        self.assertEqual(merged["player"], "jaden")

    def test_unreadable_previous_document_falls_back_to_the_rebuild(self) -> None:
        previous = "corrupt"
        subset = {"meshes": {"k": {"name": "SK_Anime_K", "group": "Cast"}}}
        merged = manifest.merge_partial_manifests(previous, subset)
        self.assertEqual(merged, subset)

    def test_non_object_subset_is_refused(self) -> None:
        with self.assertRaises(TypeError):
            manifest.merge_partial_manifests({"meshes": {}}, 42)

    def test_inputs_are_neither_mutated(self) -> None:
        previous = self.full_cast()
        rebuilt = {"meshes": {"jaden": {"name": "SK_Anime_Jaden2", "group": "ArtistA"}}}
        manifest.merge_partial_manifests(previous, rebuilt)
        self.assertEqual(len(previous["meshes"]), 3)
        self.assertEqual(len(rebuilt["meshes"]), 1)

    def test_extra_top_level_keys_are_preserved(self) -> None:
        merged = manifest.merge_partial_manifests({"version": 3, "groups": {}},
                                                  {"version": 4, "meshes": {}})
        self.assertEqual(merged["version"], 4)   # subset key wins
        self.assertEqual(merged["groups"], {})
        self.assertEqual(merged["meshes"], {})


class VrmParseTests(unittest.TestCase):
    """T6: corrupt VRM / glTF manifests must yield safe empties, not exceptions."""

    @staticmethod
    def payload(document) -> bytes:
        return _glb_bytes(json.dumps(document).encode("utf-8"))

    def _document(self, **overrides) -> dict:
        doc = {
            "nodes": [{"name": "Root"}, {"name": "Hips"}, {"name": "UpperArm_L"}],
            "materials": [{"name": "Top", "alphaMode": "OPAQUE"}, {"name": "Hair", "alphaMode": "MASK"}],
            "extensions": {
                "VRMC_vrm": {"humanoid": {"humanBones": {"hips": {"node": 1},
                                                         "leftUpperArm": {"node": 2}}}},
            },
        }
        doc.update(overrides)
        return doc

    def test_valid_vrm_1_humanoid_map(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.vrm"
            path.write_bytes(self.payload(self._document()))
            self.assertEqual(read_vrm(str(path)), (1, {"hips": "Hips", "leftUpperArm": "UpperArm_L"}))

    def test_valid_vrm_0_humanoid_map(self) -> None:
        doc = self._document(extensions={"VRM": {"humanoid": {"humanBones": [
            {"bone": "hips", "node": 1}, {"bone": "leftUpperArm", "node": 2}]}}})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.vrm"
            path.write_bytes(self.payload(doc))
            self.assertEqual(target_names(str(path)), {})
            self.assertEqual(read_vrm(str(path)), (0, {"hips": "Hips", "leftUpperArm": "UpperArm_L"}))
            self.assertEqual(alpha_modes(str(path)), {"Top": "OPAQUE", "Hair": "MASK"})

    def test_vrm_0_blend_mode_overrides_alpha_mode(self) -> None:
        doc = self._document(extensions={"VRM": {
            "materialProperties": [{"name": "Top", "floatProperties": {"_BlendMode": 1}},
                                   {"name": "Hair", "floatProperties": {"_BlendMode": 2}}],
            "humanoid": {"humanBones": []}}})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.vrm"
            path.write_bytes(self.payload(doc))
            self.assertEqual(alpha_modes(str(path)), {"Top": "MASK", "Hair": "BLEND"})

    def test_corrupt_manifests_return_safe_empties(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(alpha_modes(str(Path(tmp) / "absent.glb")), {})
            self.assertEqual(read_vrm(str(Path(tmp) / "absent.glb")), (None, {}))
            cases = [
                {"nodes": "hunig"},
                {"nodes": [{"no_name": 1}], "extensions": {"VRMC_vrm": {"humanoid": {"humanBones": {"hips": {"node": 0}}}}}},
                {"nodes": [{"name": "A"}], "extensions": {"VRMC_vrm": {"humanoid": {"humanBones": {"hips": {"node": 42}}}}}},
                {"nodes": [{"name": "A"}], "extensions": {"VRMC_vrm": {"humanoid": {"humanBones": {"hips": 1}}}}},
                {"nodes": [{"name": "A"}], "extensions": {"VRM": "hunig"}},
                {"nodes": [{"name": "A"}], "extensions": {"VRM": {"humanoid": {"humanBones": [{"bone": "hips"}, 1]}}}},
                {"nodes": [{"name": "A"}], "extensions": {"VRM": {"humanoid": {"humanBones": [{"bone": "hips", "node": True}]}}}},
            ]
            for i, doc in enumerate(cases):
                path = Path(tmp) / f"case_{i}.vrm"
                path.write_bytes(self.payload(doc))
                with self.subTest(case=i):
                    version, human = read_vrm(str(path))
                    self.assertIn(version, (None, 0, 1))
                    self.assertTrue(all(isinstance(name, str) for name in human.values()))
                    self.assertEqual(alpha_modes(str(path)), {})
                    self.assertEqual(target_names(str(path)), {})

    def test_corrupt_glb_bytes_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for blob in (b"", b"glTF", b"glTF" + b"0" * 30, self.payload({"materials": [{"no_name": 1}]})[:-4]):
                path = Path(tmp) / "in.vrm"
                path.write_bytes(blob)
                self.assertEqual(read_vrm(str(path)), (None, {}), blob[:8])
                self.assertEqual(alpha_modes(str(path)), {})

    def test_target_names_are_validated(self) -> None:
        doc = self._document(meshes=[
            {"name": "Face", "extras": {"targetNames": ["Fcl_BRW_Angry"]}},
            {"name": "Body.001", "primitives": [{"extras": {"targetNames": ["A", "B"]}}]},
            {"name": "Broken", "extras": {"targetNames": "no"}},
            {"name": "Empty", "primitives": "no"},
            {"name": "Intish", "extras": {"targetNames": [3]}},
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "model.vrm"
            path.write_bytes(self.payload(doc))
            self.assertEqual(target_names(str(path)), {
                "Face": ["Fcl_BRW_Angry"], "Body": ["A", "B"],
            })


class StampedCacheTests(unittest.TestCase):
    """T7: terrain *.npy caches are stamped on write and refused on read."""

    def _require(self, cache_dir, *, fix="python Tools/build_island.py terrain"):
        return cache.require_stamp(cache_dir, "terrain_cache.json",
                                   {"field_res": 4, "world_size": 300.0},
                                   ("height.npy", "slope.npy"),
                                   subject="terrain caches", fix=fix)

    def test_missing_stamp_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "height.npy").write_bytes(b"x")
            with self.assertRaisesRegex(cache.StampedCacheError, "no terrain_cache\\.json stamp"):
                self._require(tmp)

    def test_mismatched_configuration_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("height.npy", "slope.npy"):
                (Path(tmp) / name).write_bytes(b"x")
            jsonio.write_json(Path(tmp) / "terrain_cache.json",
                              {"field_res": 2, "world_size": 200.0}, indent=1)
            with self.assertRaises(cache.StampedCacheError) as caught:
                self._require(tmp)
            message = str(caught.exception)
            self.assertIn("field_res=2", message)
            self.assertIn("field_res=4", message)
            self.assertIn("python Tools/build_island.py terrain", message)

    def test_partial_cache_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "height.npy").write_bytes(b"x")     # slope.npy missing
            jsonio.write_json(Path(tmp) / "terrain_cache.json",
                              {"field_res": 4, "world_size": 300.0}, indent=1)
            with self.assertRaisesRegex(cache.StampedCacheError, "slope\\.npy"):
                self._require(tmp)

    def test_valid_stamp_passes_and_returns_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("height.npy", "slope.npy"):
                (Path(tmp) / name).write_bytes(b"x")
            jsonio.write_json(Path(tmp) / "terrain_cache.json",
                              {"field_res": 4, "world_size": 300.0}, indent=1)
            stamp = self._require(tmp)
            self.assertEqual(stamp, {"field_res": 4, "world_size": 300.0})

    def test_unreadable_stamp_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("height.npy", "slope.npy", "terrain_cache.json"):
                (Path(tmp) / name).write_bytes(b"not json")
            with self.assertRaisesRegex(cache.StampedCacheError, "unreadable"):
                self._require(tmp)


class AudioWriterTests(unittest.TestCase):
    """G4: the WAV writer publishes a valid 16-bit mono header and rolls back on failure."""

    def test_write_produces_16bit_mono_wav_with_expected_loop_length(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A_Test.wav"
            frames = int(audio.SR * 0.06)
            samples = np.sin(np.linspace(0.0, 2.0 * math.pi * 8.0, frames))
            audio._write(str(path), samples)
            with wave.open(str(path), "rb") as w:
                self.assertEqual(w.getnchannels(), 1)
                self.assertEqual(w.getsampwidth(), 2)
                self.assertEqual(w.getframerate(), audio.SR)
                self.assertEqual(w.getcomptype(), "NONE")
                self.assertEqual(w.getnframes(), frames)   # loop length follows the duration
            # atomic publish: no temp files next to the target
            self.assertEqual([p.name for p in path.parent.iterdir()], ["A_Test.wav"])

    def test_writer_failure_keeps_previous_file_and_leaves_no_temp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "A_Test.wav"
            audio._write(str(path), np.zeros(64))
            before = path.read_bytes()
            with mock.patch.object(audio.wave, "open", side_effect=OSError("no wave writer")):
                with self.assertRaises(OSError):
                    audio._write(str(path), np.ones(64))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual([p.name for p in path.parent.iterdir()], ["A_Test.wav"])


class ThirdpartyToolTests(_StubbedThirdpartyMixin, unittest.TestCase):
    """T3 / T4 / T13: gltf-transform runner + extracted-texture cache freshness."""

    def test_candidate_list_is_portable_and_env_first(self) -> None:
        candidates = self.tp.GLTF_TRANSFORM_CANDIDATES
        self.assertEqual(candidates, [os.environ.get("GLTF_TRANSFORM", ""),
                                      shutil.which("gltf-transform") or ""])
        self.assertNotIn("/home/", " ".join(candidates))   # no personal tool path again

    def test_decode_passes_a_timeout_and_fails_closed_on_a_hang(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "packed.glb"
            source.write_bytes(b"meshopt")
            tool = Path(tmp) / "gltf-transform.cmd"
            tool.write_bytes(b"")
            calls = {}

            def hang(cmd, **kwargs):
                calls.update(kwargs)
                raise subprocess.TimeoutExpired(cmd, kwargs.get("timeout"))

            with mock.patch.object(self.tp, "GLTF_TRANSFORM_CANDIDATES", [str(tool)]), \
                    mock.patch.object(subprocess, "run", hang):
                with self.assertRaises(RuntimeError) as caught:
                    with redirect_stdout(StringIO()):
                        self.tp._decode_meshopt(str(source))
            self.assertEqual(calls.get("timeout"), self.tp.GLTF_TRANSFORM_TIMEOUT)
            message = str(caught.exception)
            self.assertIn("no working gltf-transform available", message)
            self.assertRegex(message, r"timed out after \d+(\.\d+)? seconds")
            self.assertRegex(message, r"\(\d+\.\ds\)")   # elapsed attempt is surfaced

    def test_decode_success_caches_and_logs_the_tool(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cache_root = Path(tmp) / "cache"
            source = Path(tmp) / "packed.glb"
            source.write_bytes(b"meshopt")
            tool = Path(tmp) / "gltf-transform.cmd"
            tool.write_bytes(b"")

            def decode(cmd, **kwargs):
                target = Path(cmd[3])
                target.write_bytes(_glb_bytes(b"{}"))
                return subprocess.CompletedProcess(cmd, 0)

            expected = Path(cache.cache_file(str(cache_root / "decoded"), str(source), ".glb"))
            with mock.patch.object(self.tp, "GLTF_TRANSFORM_CANDIDATES", [str(tool)]), \
                    mock.patch.object(self.tp.C, "CACHE_DIR", str(cache_root)), \
                    mock.patch.object(subprocess, "run", decode), \
                    redirect_stdout(StringIO()) as out:
                result = self.tp._decode_meshopt(str(source))
            self.assertEqual(result, str(expected))
            self.assertTrue(cache.is_glb(expected))
            self.assertIn(str(tool), out.getvalue())   # which tool was used is logged

    def _stub_image(self):
        class _StubImage:
            def __init__(self) -> None:
                self.size = (2, 2)
                self.pixels = [0.5] * 16     # 2x2 RGBA

        return _StubImage()

    def test_save_image_reuses_only_fresh_cache_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "model.vrm"
            source.write_bytes(b"vrm payload")
            cached = Path(tmp) / "T_X_Base.png"
            cached.write_bytes(b"stale")
            os.utime(source, (1_600_000_000, 1_600_000_000))
            os.utime(cached, (1_500_000_000, 1_500_000_000))
            result = self.tp._save_image(self._stub_image(), str(cached), fresh_against=str(source))
            self.assertEqual(result, str(cached))
            self.assertTrue(cache.is_fresh(cached, source))   # regenerated from the source image
            self.assertEqual(cached.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_save_image_keeps_a_fresh_cache_entry_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "model.vrm"
            source.write_bytes(b"vrm payload")
            cached = Path(tmp) / "T_X_Base.png"
            cached.write_bytes(b"cached-bytes")
            os.utime(source, (1_500_000_000, 1_500_000_000))
            os.utime(cached, (1_600_000_000, 1_600_000_000))
            result = self.tp._save_image(self._stub_image(), str(cached), fresh_against=str(source))
            self.assertEqual(result, str(cached))
            self.assertEqual(cached.read_bytes(), b"cached-bytes")


class StageDependencyTests(unittest.TestCase):
    """G5: running a stage before its producer exits 2 with a stage hint."""

    def test_missing_stage_input_is_an_exit_2_configuration_error(self) -> None:
        module = _load_build_island_module()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(pipeline_config, "CACHE_DIR", str(Path(tmp) / "cache")), \
                    mock.patch.object(pipeline_config, "OUT_DATA", str(Path(tmp) / "data")), \
                    redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                rc = module.main(["layout"])
        self.assertEqual(rc, 2)
        self.assertIn("run the terrain stage first", err.getvalue())
        self.assertIn("height.npy", err.getvalue())

    def test_producer_in_the_same_run_suppresses_the_requirement(self) -> None:
        module = _load_build_island_module()
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(pipeline_config, "CACHE_DIR", str(Path(tmp) / "cache")), \
                    mock.patch.object(pipeline_config, "OUT_DATA", str(Path(tmp) / "data")):
                self.assertEqual(module.missing_stage_inputs(["terrain", "layout", "meshes"]), [])
        # without the producer, all of its outputs are required
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(pipeline_config, "CACHE_DIR", str(Path(tmp) / "cache")), \
                    mock.patch.object(pipeline_config, "OUT_DATA", str(Path(tmp) / "data")):
                problems = module.missing_stage_inputs(["meshes"])
            self.assertEqual([(stage, producer) for stage, producer, _p in problems],
                             [("meshes", "terrain"), ("meshes", "terrain")])

    def test_standalone_stages_have_no_input_requirements(self) -> None:
        module = _load_build_island_module()
        self.assertEqual(module.missing_stage_inputs(["textures", "audio", "cast"]), [])


if __name__ == "__main__":
    unittest.main()
