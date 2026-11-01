"""Regression tests for the canon manifest hash inventory.

The manifest is a published derived artifact. These tests prove that it matches
the committed files and that a hash refresh cannot silently hide content drift.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "Tools"
sys.path.insert(0, str(TOOLS / "canon"))
sys.path.insert(0, str(TOOLS / "validate"))

import build_manifest  # noqa: E402
import validate_all  # noqa: E402
import validate_canon  # noqa: E402

CANON = REPO / "DuelAcademyIsland" / "Content" / "Data" / "Canon"


class CommittedManifestTests(unittest.TestCase):
    def test_committed_manifest_matches_every_file(self) -> None:
        errors = validate_canon.manifest_hash_errors(CANON / "manifest.json", REPO)
        self.assertEqual(errors, [])

    def test_manifest_covers_the_published_file_set(self) -> None:
        manifest = json.loads((CANON / "manifest.json").read_text(encoding="utf-8"))
        paths = [entry["path"] for entry in manifest["files"]]
        expected = {
            f"{build_manifest.MANIFEST_PATH_PREFIX}/{relative}"
            for relative in build_manifest.FILES
        }
        self.assertEqual(len(paths), len(set(paths)))
        self.assertEqual(set(paths), expected)

    def test_tampered_hash_is_detected(self) -> None:
        manifest = json.loads((CANON / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate_canon.manifest_hash_errors(path, REPO)
        self.assertTrue(any("manifest hash mismatch" in error for error in errors))

    def test_missing_and_unexpected_entries_are_detected(self) -> None:
        manifest = json.loads((CANON / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"][0]["path"] = "DuelAcademyIsland/Content/Data/Canon/not_published.json"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            errors = validate_canon.manifest_hash_errors(path, REPO)
        self.assertTrue(any("manifest missing file" in error for error in errors))
        self.assertTrue(any("unexpected file" in error for error in errors))
        self.assertTrue(any("omits published file" in error for error in errors))


class ManifestCliTests(unittest.TestCase):
    def test_report_directory_is_a_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                rc = validate_canon.main(["--report", tmp])
        self.assertEqual(rc, 2)
        self.assertIn("cannot write report", err.getvalue())


class ValidateAllManifestTests(unittest.TestCase):
    def _run(self, tmp: str, entry: dict) -> set[str]:
        root = Path(tmp)
        data_dir = root / "DuelAcademyIsland" / "Content" / "Data"
        canon = data_dir / "Canon"
        canon.mkdir(parents=True, exist_ok=True)
        (canon / "manifest.json").write_text(
            json.dumps({"files": [entry]}), encoding="utf-8"
        )
        report = validate_all.Report(
            root=root,
            data_dir=data_dir,
            contracts_dir=root / "Docs" / "Contracts",
        )
        context = validate_all.make_context(root, data_dir, root / "Docs" / "Contracts")
        validate_all.validate_canon_reference(context, report)
        return {finding.code for finding in report.findings}

    def test_validate_all_reports_a_missing_manifest_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codes = self._run(tmp, {
                "path": "DuelAcademyIsland/Content/Data/Canon/cards.json",
                "sha256": "0" * 64,
                "bytes": 1,
            })
        self.assertIn("canon_manifest_missing_file", codes)

    def test_validate_all_reports_a_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canon = root / "DuelAcademyIsland" / "Content" / "Data" / "Canon"
            canon.mkdir(parents=True)
            (canon / "cards.json").write_text("{}\n", encoding="utf-8")
            codes = self._run(tmp, {
                "path": "DuelAcademyIsland/Content/Data/Canon/cards.json",
                "sha256": "0" * 64,
                "bytes": 3,
            })
        self.assertIn("canon_manifest_hash", codes)

    def test_validate_all_rejects_a_path_outside_canon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            codes = self._run(tmp, {
                "path": "DuelAcademyIsland/Content/Data/cards.json",
                "sha256": "0" * 64,
                "bytes": 1,
            })
        self.assertIn("canon_manifest_path", codes)


class ManifestRefreshTests(unittest.TestCase):
    def test_refresh_rehashes_without_changing_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text((CANON / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8")
            before = json.loads(path.read_text(encoding="utf-8"))
            after = build_manifest.refresh_manifest_hashes(path, CANON)
        self.assertEqual(after["files"], before["files"])
        self.assertNotEqual(after["generated_utc"], "")

    def test_refresh_refuses_a_record_count_change(self) -> None:
        manifest = json.loads((CANON / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"][0]["records"] = -1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(build_manifest.ManifestDriftError):
                build_manifest.refresh_manifest_hashes(path, CANON)

    def test_refresh_refuses_a_file_set_change(self) -> None:
        manifest = json.loads((CANON / "manifest.json").read_text(encoding="utf-8"))
        manifest["files"] = manifest["files"][:-1]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(build_manifest.ManifestDriftError):
                build_manifest.refresh_manifest_hashes(path, CANON)

    def test_missing_data_is_reported_not_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            files, missing = build_manifest.build_file_entries(Path(tmp))
        self.assertEqual(files, [])
        self.assertEqual(missing, build_manifest.FILES)

    def test_refresh_failure_keeps_the_previous_manifest(self) -> None:
        original = (CANON / "manifest.json").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest.json"
            path.write_text(original, encoding="utf-8")
            with mock.patch.object(
                build_manifest, "build_file_entries", side_effect=OSError("disk error")
            ):
                with self.assertRaises(OSError):
                    build_manifest.refresh_manifest_hashes(path, CANON)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
