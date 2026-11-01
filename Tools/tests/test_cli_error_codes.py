"""CLI error-code regressions for data generators and validators.

Missing or unreadable input files must produce a short diagnostic and exit 2
(configuration error), not a traceback. These checks protect the CI gates from
being fooled by Python's generic unhandled-exception exit code.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "Tools"
for folder in ("puzzles", "economy", "opponents"):
    sys.path.insert(0, str(TOOLS / folder))

import generate_exams  # noqa: E402
import import_canon_decks  # noqa: E402
import run_engine_selftests  # noqa: E402
import sync_canon  # noqa: E402
import validate_decks  # noqa: E402
import validate_packs  # noqa: E402


def _load_puzzle_validator():
    path = TOOLS / "puzzles" / "validate.py"
    spec = importlib.util.spec_from_file_location("puzzle_validate", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_build_island():
    path = TOOLS / "build_island.py"
    spec = importlib.util.spec_from_file_location("build_island_cli", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class GeneratorCliTests(unittest.TestCase):
    def test_generate_exams_missing_inputs_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                rc = generate_exams.main(["--root", tmp])
        self.assertEqual(rc, 2)
        self.assertIn("cannot load exam inputs", err.getvalue())

    def test_generate_puzzles_missing_cards_is_configuration_error(self) -> None:
        path = TOOLS / "puzzles" / "generate_puzzles.py"
        spec = importlib.util.spec_from_file_location("generate_puzzles_cli", path)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                rc = module.main(["--root", tmp, "--no-canon"])
        self.assertEqual(rc, 2)
        self.assertIn("cannot load cards", err.getvalue())


class BuildIslandCliTests(unittest.TestCase):
    def test_help_does_not_import_the_pipeline(self) -> None:
        module = _load_build_island()
        self.assertIsNone(module.parse_stages(["--help"]))

    def test_unknown_stage_is_rejected(self) -> None:
        module = _load_build_island()
        with self.assertRaises(ValueError):
            module.parse_stages(["layuot"])

    def test_stage_selection_is_ordered_and_render_is_opt_in(self) -> None:
        module = _load_build_island()
        self.assertEqual(module.parse_stages(["layout", "terrain"]), ["terrain", "layout"])
        self.assertEqual(module.parse_stages(["--render"]), module.STAGES)
        self.assertEqual(module.parse_stages(["all"]), module.STAGES)


class ValidatorCliTests(unittest.TestCase):
    def test_validate_decks_missing_cards_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                with mock.patch.object(validate_decks, "CARDS", Path(tmp) / "missing.json"):
                    rc = validate_decks.main()
        self.assertEqual(rc, 2)
        self.assertIn("cannot load A06 deck data", err.getvalue())

    def test_validate_packs_missing_shop_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                with mock.patch.object(validate_packs, "SHOP_PACKS", Path(tmp) / "missing.json"):
                    rc = validate_packs.main()
        self.assertEqual(rc, 2)
        self.assertIn("cannot load A06 pack data", err.getvalue())

    def test_import_canon_decks_missing_cards_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                with mock.patch.object(import_canon_decks, "CARDS_PATH", Path(tmp) / "missing.json"):
                    rc = import_canon_decks.main(["--check"])
        self.assertEqual(rc, 2)
        self.assertIn("cannot load opponent deck inputs", err.getvalue())

    def test_sync_canon_missing_shop_template_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                with mock.patch.object(sync_canon, "SHOP_PACKS", Path(tmp) / "missing.json"):
                    rc = sync_canon.main([])
        self.assertEqual(rc, 2)
        self.assertIn("cannot load economy inputs", err.getvalue())

    def test_sync_canon_check_mode_does_not_write(self) -> None:
        paths = (sync_canon.SHOP_PACKS, sync_canon.RARITY, sync_canon.RULES)
        before = {path: path.read_bytes() for path in paths}
        with redirect_stdout(StringIO()):
            rc = sync_canon.main(["--check"])
        self.assertEqual(rc, 0)
        for path in paths:
            self.assertEqual(path.read_bytes(), before[path])


class HarnessCliTests(unittest.TestCase):
    def test_invalid_timeout_is_configuration_error(self) -> None:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
            rc = run_engine_selftests.main(["--timeout", "0"])
        self.assertEqual(rc, 2)
        self.assertIn("--timeout", err.getvalue())

    def test_puzzle_validator_report_directory_is_configuration_error(self) -> None:
        module = _load_puzzle_validator()
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                rc = module.main(["--root", str(REPO), "--report", tmp])
        self.assertEqual(rc, 2)
        self.assertIn("cannot write report", err.getvalue())


if __name__ == "__main__":
    unittest.main()
