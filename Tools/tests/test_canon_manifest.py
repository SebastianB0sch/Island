"""Regression tests for the canon manifest hash inventory.

The manifest is a published derived artifact. These tests prove that it matches
the committed files and that a hash refresh cannot silently hide content drift.
"""

from __future__ import annotations

import json
import os
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


class RecordDigestTests(unittest.TestCase):
    """V7: per-record digests embedded by the canon builders must re-verify.

    Each check mirrors the exact digest algorithm of the builder that wrote
    the record (build_decks.sha_deck, build_packs, build_puzzles,
    canon_common.card_fingerprint) so a tampered or drifted record cannot pass
    the manifest gate silently.
    """

    RUNTIME = REPO / "DuelAcademyIsland" / "Content" / "Data"

    def test_deck_record_digests_match(self) -> None:
        decks = json.loads((CANON / "decks.json").read_text(encoding="utf-8"))["decks"]
        digested = [deck for deck in decks if deck.get("sha256")]
        self.assertGreaterEqual(len(digested), 30)
        mismatched = [
            deck["id"] for deck in digested
            if validate_canon.deck_record_digest(deck) != deck["sha256"]
        ]
        self.assertEqual(mismatched, [])

    def test_pack_and_puzzle_record_digests_match(self) -> None:
        packs = json.loads((CANON / "packs.json").read_text(encoding="utf-8"))["packs"]
        self.assertEqual(len(packs), 48)
        for pack in packs:
            self.assertEqual(validate_canon.pack_record_digest(pack), pack["sha256"], pack["id"])
        puzzles = json.loads((CANON / "puzzles.json").read_text(encoding="utf-8"))["puzzles"]
        self.assertEqual(len(puzzles), 100)
        for puzzle in puzzles:
            self.assertEqual(
                validate_canon.puzzle_record_digest(puzzle), puzzle["sha256"], puzzle["id"]
            )

    def test_card_fingerprints_reproduce_the_canonical_digest(self) -> None:
        sys.path.insert(0, str(TOOLS / "canon"))
        from canon_common import card_fingerprint

        manifest = json.loads((CANON / "cards_manifest.json").read_text(encoding="utf-8"))
        per_card = manifest["per_card_sha256"]
        self.assertEqual(len(per_card), 1200)
        cards = json.loads((self.RUNTIME / "cards.json").read_text(encoding="utf-8"))
        payload = []
        for card in cards:
            actual = card_fingerprint(card)
            payload.append(actual)
            self.assertEqual(actual, per_card[str(card["id"])], f"card {card['id']}")
        import hashlib

        canonical = hashlib.sha256("\n".join(payload).encode("ascii")).hexdigest()
        self.assertEqual(canonical, manifest["canonical_hash"]["value"])

    def test_corrupted_deck_digest_is_detectable(self) -> None:
        decks = json.loads((CANON / "decks.json").read_text(encoding="utf-8"))["decks"]
        deck = dict(next(d for d in decks if d.get("sha256")))
        original_main = deck["main"]
        with mock.patch.dict(deck, {"main": original_main + [1]}):
            self.assertNotEqual(validate_canon.deck_record_digest(deck), deck["sha256"])


class LocalOnlyDialogueGateTests(unittest.TestCase):
    """V3: the supported local-only dossier must not fail the legal gate."""

    def test_dialogue_in_the_local_only_dossier_is_not_a_leak(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canon_dir = root / "Tools" / "canon"
            local_only = canon_dir / ".local_only"
            (canon_dir / "outside").mkdir(parents=True)
            (local_only / "reference").mkdir(parents=True)
            (canon_dir / "outside" / "dialogue_full.json").write_text("{}", encoding="utf-8")
            (local_only / "reference" / "dialogue_full.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(validate_canon, "REPO_ROOT", root), \
                 mock.patch.object(validate_canon, "LOCAL_ONLY_DIR", local_only):
                leaks = validate_canon.collect_dialogue_leaks()
        self.assertEqual(leaks, ["Tools/canon/outside/dialogue_full.json".replace("/", os.sep)])

    def test_environment_override_of_the_local_only_dir_is_respected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            canon_dir = root / "Tools" / "canon"
            override = root / "elsewhere" / "dossier"
            canon_dir.mkdir(parents=True)
            override.mkdir(parents=True)
            (canon_dir / "dialogue_full.json").write_text("{}", encoding="utf-8")
            (override / "dialogue_full.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(validate_canon, "REPO_ROOT", root), \
                 mock.patch.object(validate_canon, "LOCAL_ONLY_DIR", override):
                leaks = validate_canon.collect_dialogue_leaks()
        self.assertEqual(leaks, ["Tools/canon/dialogue_full.json".replace("/", os.sep)])


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
