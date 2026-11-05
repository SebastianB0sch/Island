"""Regression tests for the WS-07 data-tooling & CI findings (Pass 4).

Stdlib only, no network, no Unreal: each case drives the affected script
against fixture data or a stubbed network/subprocess so CI can run the whole
file on a clean checkout.
"""

from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "Tools"
for folder in ("canon", "effects", "economy", "opponents", "puzzles", "validate", "tooling", "world"):
    sys.path.insert(0, str(TOOLS / folder))

import atomic  # noqa: E402
import effect_data as effect_data  # noqa: E402
import generate_scripts  # noqa: E402
import fetch_guides  # noqa: E402
import import_canon_decks  # noqa: E402
import run_engine_selftests  # noqa: E402
import schema_lite  # noqa: E402
import sync_canon  # noqa: E402
import validate_all  # noqa: E402
import validate_layout  # noqa: E402


def _load_audit_script(name: str):
    """Load a root-level Tools/audit_story_*.py as a module and execute it."""
    spec = importlib.util.spec_from_file_location(f"{name}_cli", TOOLS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AtomicWriterTests(unittest.TestCase):
    def test_write_json_round_trips_without_temp_litter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fusions.json"
            atomic.write_json(path, {"recipes": [1, 2]})
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                json.dumps({"recipes": [1, 2]}, indent=2, ensure_ascii=False) + "\n",
            )
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_failed_serialization_keeps_the_previous_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rituals.json"
            atomic.write_json(path, {"kept": True})
            before = path.read_bytes()
            with self.assertRaises(TypeError):
                atomic.write_json(path, {"bad": {1, 2}})  # sets are not JSON-serializable
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_write_text_keeps_lf_newlines_and_no_temp_litter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "nested" / "report.md"
            atomic.write_text(path, "line one\nline two\n")
            self.assertEqual(path.read_text(encoding="utf-8"), "line one\nline two\n")
            self.assertEqual(list(path.parent.glob("*.tmp")), [])


class EffectScriptWriterTests(unittest.TestCase):
    def test_generate_scripts_refuses_to_overwrite_and_keeps_existing_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scripts_dir = Path(tmp)
            existing = scripts_dir / "7.json"
            existing.write_text('{"hand": "authored"}\n', encoding="utf-8")
            before = existing.read_bytes()
            with mock.patch.object(effect_data, "SCRIPTS_DIR", scripts_dir):
                with self.assertRaises(SystemExit) as raised:
                    generate_scripts.write_payloads([{"card_id": 7}], check=False)
            self.assertIn("refusing to overwrite", str(raised.exception))
            self.assertEqual(existing.read_bytes(), before)
            self.assertEqual(list(scripts_dir.glob("*.tmp")), [])

    def test_generate_scripts_writes_new_scripts_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scripts_dir = Path(tmp)
            with mock.patch.object(effect_data, "SCRIPTS_DIR", scripts_dir):
                written, unchanged = generate_scripts.write_payloads(
                    [{"card_id": 7}], check=False
                )
            self.assertEqual((written, unchanged), (1, 0))
            path = scripts_dir / "7.json"
            self.assertEqual(
                path.read_text(encoding="utf-8"),
                json.dumps({"card_id": 7}, indent=2, ensure_ascii=False) + "\n",
            )
            self.assertEqual(list(scripts_dir.glob("*.tmp")), [])

    def test_generate_scripts_check_mode_writes_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            scripts_dir = Path(tmp)
            with mock.patch.object(effect_data, "SCRIPTS_DIR", scripts_dir):
                written, unchanged = generate_scripts.write_payloads(
                    [{"card_id": 7}], check=True
                )
            self.assertEqual((written, unchanged), (1, 0))
            self.assertFalse((scripts_dir / "7.json").exists())


class EffectManifestWriterTests(unittest.TestCase):
    def test_manifest_write_round_trips_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            manifest_dir = Path(tmp)
            payload = {"schema_version": 1, "cards": [{"id": 1}]}
            with mock.patch.object(
                effect_data, "MANIFEST_PATH", manifest_dir / "card_effect_manifest.json"
            ):
                effect_data.write_json(effect_data.MANIFEST_PATH, payload)
            self.assertEqual(
                json.loads(
                    (manifest_dir / "card_effect_manifest.json").read_text(encoding="utf-8")
                ),
                payload,
            )
            self.assertEqual(list(manifest_dir.glob("*.tmp")), [])


class ImportCanonDecksCliTests(unittest.TestCase):
    """V4: every --check input load is inside the exit-2 error contract."""

    def _check_with(self, **patches: Path) -> tuple[int, str]:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
                with mock.patch.multiple(import_canon_decks, **patches):
                    rc = import_canon_decks.main(["--check"])
        return rc, err.getvalue()

    def test_missing_player_decks_json_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            rc, err = self._check_with(
                PLAYER_DECKS_PATH=Path(tmp) / "missing_decks.json",
                RUNTIME_DIR=empty,
            )
        self.assertEqual(rc, 2)
        self.assertIn("cannot load opponent deck inputs", err)

    def test_missing_saved_player_decks_json_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            rc, err = self._check_with(
                SAVED_PLAYER_DECKS_PATH=Path(tmp) / "missing_player_decks.json",
                RUNTIME_DIR=empty,
            )
        self.assertEqual(rc, 2)
        self.assertIn("cannot load opponent deck inputs", err)

    def test_missing_events_json_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            rc, err = self._check_with(
                DATA=Path(tmp) / "data_root",
                RUNTIME_DIR=empty,
            )
        self.assertEqual(rc, 2)
        self.assertIn("cannot load opponent deck inputs", err)


def _empty_cache_entries(cache: dict) -> int:
    return sum(1 for value in cache.values() if not value)


class FetchGuidesFailureTests(unittest.TestCase):
    """V8: failures must be tracked, exit non-zero, never non-empty -> ''."""

    def _run(self, argv: list[str], stub) -> tuple[int, str, str]:
        with redirect_stdout(StringIO()) as out, redirect_stderr(StringIO()) as err:
            with mock.patch.object(sys, "argv", ["fetch_guides.py", *argv]), \
                 mock.patch.object(fetch_guides, "fetch", side_effect=stub):
                rc = fetch_guides.main()
        return rc, out.getvalue(), err.getvalue()

    def test_failed_fetches_fail_closed_and_keep_existing_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "guide_wikitext.json"
            out.write_text(
                json.dumps({fetch_guides.PAGES[0]: "existing wikitext"}),
                encoding="utf-8",
            )
            rc, _stdout, err = self._run(["--out", str(out)], lambda title: (title, ""))
            self.assertEqual(rc, 1)
            self.assertIn("fetch(es) failed", err)
            cache = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(cache.get(fetch_guides.PAGES[0]), "existing wikitext")
            self.assertEqual(_empty_cache_entries(cache), 0)

    def test_failed_refetch_never_replaces_good_entries(self) -> None:
        # A later refresh that would overwrite the existing non-empty entries
        # must keep them and instead record the failures.
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "guide_wikitext.json"
            out.write_text(
                json.dumps({
                    fetch_guides.PAGES[0]: "text zero",
                    fetch_guides.PAGES[1]: "text one",
                }),
                encoding="utf-8",
            )

            def stub(title: str) -> tuple[str, str]:
                return title, ""

            rc, _stdout, err = self._run(["--out", str(out)], stub)
            self.assertEqual(rc, 1)
            self.assertIn("fetch(es) failed", err)
            cache = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(cache.get(fetch_guides.PAGES[0]), "text zero")
            self.assertEqual(cache.get(fetch_guides.PAGES[1]), "text one")
            self.assertEqual(_empty_cache_entries(cache), 0)

    def test_full_success_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "guide_wikitext.json"
            rc, _stdout, _err = self._run(
                ["--out", str(out)], lambda title: (title, "wikitext for " + title)
            )
            self.assertEqual(rc, 0)
            cache = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(len(cache), len(fetch_guides.PAGES))


class EngineSelftestTimeoutTests(unittest.TestCase):
    """9b: the kill path must be the shared process-tree strategy.

    The fixture spawns a long-lived grandchild and records its PID, so the
    test fails if only the direct child is killed.  It mirrors the portable
    fixture in Tools/tests/test_run_smoke.py so both runners are covered the
    same way.
    """

    _TREE_SCRIPT = """
import subprocess, sys, time
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(str(child.pid))
print("parent-ready", flush=True)
print("parent-stderr", file=sys.stderr, flush=True)
time.sleep(60)
"""

    def test_execute_kills_the_full_process_tree_on_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            pid_file = tmp_path / "child.pid"
            returncode, output, timed_out = run_engine_selftests._execute(
                [sys.executable, "-c", self._TREE_SCRIPT, str(pid_file)],
                tmp_path,
                4,
            )
            self.assertIsNone(returncode)
            self.assertTrue(timed_out)
            self.assertIn("TIMEOUT after 4s", output)
            self.assertIn("parent-ready", output)
            self.assertIn("parent-stderr", output)
            self.assertTrue(pid_file.exists())
            child_pid = int(pid_file.read_text(encoding="utf-8").strip())
            self.addCleanup(_force_kill, child_pid)
            self.assertTrue(
                _wait_until_dead(child_pid),
                f"child process {child_pid} survived the timeout",
            )

    def test_execute_keeps_direct_child_timeout_semantics(self) -> None:
        returncode, output, timed_out = run_engine_selftests._execute(
            [sys.executable, "-c", "print('fast'); import sys; sys.exit(3)"],
            Path(tempfile.gettempdir()),
            10,
        )
        self.assertEqual(returncode, 3)
        self.assertFalse(timed_out)
        self.assertIn("fast", output)


def _pid_alive(pid: int) -> bool:
    """Cross-platform liveness check (fixture helper from test_run_smoke.py)."""
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return exit_code.value == 259  # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_until_dead(pid: int, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            return True
        time.sleep(0.05)
    return not _pid_alive(pid)


def _force_kill(pid: int) -> None:
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


class WorldLayoutMissingTests(unittest.TestCase):
    """V9: a missing layout.json must be reported; degrade only on read failure."""

    WORLD_SUBDIR = Path("DuelAcademyIsland") / "Content" / "Data" / "World"
    LAYOUT_SUBDIR = Path("DuelAcademyIsland") / "SourceAssets" / "Data"

    def _world_docs(self, root: Path) -> None:
        docs = (
            ("location_map.json", {"summary": {"total": 0, "existing": 0, "needs_interior": 0, "merged": 0, "missing": 0}, "locations": []}),
            ("interiors.json", {"cells": []}),
            ("portals.json", {"portals": []}),
            ("anchors.json", {"anchors": []}),
            ("spawns.json", {"spawns": []}),
        )
        for name, payload in docs:
            path = root / self.WORLD_SUBDIR
            path.mkdir(parents=True, exist_ok=True)
            (path / name).write_text(json.dumps(payload), encoding="utf-8")

    def test_missing_layout_json_is_reported_as_an_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._world_docs(root)
            with redirect_stdout(StringIO()) as out:
                rc = validate_layout.main(["--root", str(root)])
        self.assertEqual(rc, 1)
        self.assertIn("missing file", out.getvalue())
        self.assertIn("layout.json", out.getvalue())

    def test_corrupt_layout_json_keeps_the_degrade_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._world_docs(root)
            layout_dir = root / self.LAYOUT_SUBDIR
            layout_dir.mkdir(parents=True, exist_ok=True)
            (layout_dir / "layout.json").write_text("{not json", encoding="utf-8")
            with redirect_stdout(StringIO()) as out:
                rc = validate_layout.main(["--root", str(root)])
        self.assertEqual(rc, 1)
        self.assertIn("invalid JSON in", out.getvalue())
        self.assertIn("zone checks are limited", out.getvalue())


def _canon_pack(index: int) -> dict:
    return {
        "id": f"p{index:02d}",
        "name": f"Pack {index:02d}",
        "category": "Other",
        "price_dp": 100,
        "cards_per_pack": 5,
        "full_pool": False,
        "pool": [],
        "unique_card_ids": [],
        "unresolved_names": [],
        "restock": "",
        "unlock": {"raw": "always"},
        "stock": 5,
    }


def _shop_pack(index: int) -> dict:
    return {
        "id": f"p{index:02d}",
        "name": f"Pack {index:02d}",
        "category": "Other",
        "slots": [],
        "restock_days": 7,
        "purchase_limit": 1,
        "unlock": {"description": "", "conditions": []},
    }


class SyncCanonExitCodeTests(unittest.TestCase):
    """V5: config errors exit 2 and the legality check fails closed."""

    def _fixture(self, tmp: str, banned_deck: bool) -> dict[str, Path]:
        root = Path(tmp)
        banned: dict = {"schema_version": 1, "cards": []}
        decks: list = [{"id": "legal_deck", "cards": [2, 2, 3]}]
        if banned_deck:
            banned = {
                "schema_version": 1,
                "cards": [{"card_id": 111, "name": "Bad Card", "status": {"year_1": "Forbidden"}}],
            }
            decks = [{"id": "illegal_deck", "cards": [111, 111]}]
        paths = {
            "CANON_PACKS": root / "canon" / "packs.json",
            "CANON_BANNED": root / "canon" / "banned_list.json",
            "SHOP_PACKS": root / "Shop" / "packs.json",
            "RULES": root / "Rules" / "banned_limited.json",
            "RARITY": root / "Rules" / "card_rarity.json",
            "CARDS": root / "cards.json",
            "DECKS": root / "decks.json",
        }
        paths["CANON_PACKS"].parent.mkdir(parents=True, exist_ok=True)
        paths["CANON_PACKS"].write_text(json.dumps({"packs": [_canon_pack(i) for i in range(48)]}), encoding="utf-8")
        paths["CANON_BANNED"].write_text(json.dumps(banned), encoding="utf-8")
        # SHOP_PACKS is the old slot template input; RULES/RARITY are outputs.
        paths["SHOP_PACKS"].parent.mkdir(parents=True, exist_ok=True)
        paths["SHOP_PACKS"].write_text(json.dumps({"packs": [_shop_pack(i) for i in range(48)]}), encoding="utf-8")
        paths["CARDS"].write_text("[]", encoding="utf-8")
        paths["DECKS"].write_text(json.dumps(decks), encoding="utf-8")
        return paths

    def _run(self, argv: list[str], **patches) -> tuple[int, str]:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()) as err:
            with mock.patch.multiple(sync_canon, **patches):
                rc = sync_canon.main(argv)
        return rc, err.getvalue()

    def test_missing_canon_packs_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.json"
            rc, err = self._run([], CANON_PACKS=missing)
        self.assertEqual(rc, 2)
        self.assertIn("missing canon packs", err)

    def test_illegal_banlist_fails_closed_before_any_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixture(tmp, banned_deck=True)
            shop_before = paths["SHOP_PACKS"].read_bytes()
            rc, err = self._run([], **paths)
            self.assertEqual(rc, 1)
            self.assertIn("legality violation", err)
            self.assertIn("illegal_deck contains forbidden card 111", err)
            for name in ("RULES", "RARITY"):
                self.assertFalse(paths[name].exists(), f"{name} was written despite violations")
            self.assertEqual(paths["SHOP_PACKS"].read_bytes(), shop_before)

    def test_all_legal_decks_write_normally(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = self._fixture(tmp, banned_deck=False)
            rc, _err = self._run([], **paths)
            self.assertEqual(rc, 0)
            for name in ("SHOP_PACKS", "RULES", "RARITY"):
                self.assertTrue(paths[name].exists(), f"{name} missing after a legal sync")


class ValidateAllExitCodeTests(unittest.TestCase):
    """V12: unexpected tool exceptions exit 2, not the data-failure 1."""

    def test_internal_error_returns_exit_2(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()) as out, redirect_stderr(StringIO()) as err:
                with mock.patch.object(
                    validate_all, "validate_cards", side_effect=RuntimeError("boom")
                ):
                    rc = validate_all.main(["--root", str(tmp)])
        self.assertEqual(rc, 2)
        self.assertIn("internal_error", out.getvalue())
        self.assertIn("exited with 2", err.getvalue())

    def test_data_failures_still_exit_1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                rc = validate_all.main(["--root", str(tmp)])
        # A missing cards.json is a data error (exit 1), not an internal error.
        self.assertEqual(rc, 1)


class SchemaLiteSemanticsTests(unittest.TestCase):
    """V11: draft-07 integer semantics, null subschemas, guarded numerics."""

    def test_integer_type_accepts_integer_valued_floats(self) -> None:
        self.assertEqual(schema_lite.validate(2.0, {"type": "integer"}), [])
        self.assertEqual(schema_lite.validate(2, {"type": "integer"}), [])

    def test_integer_type_rejects_fractional_floats(self) -> None:
        self.assertNotEqual(schema_lite.validate(2.5, {"type": "integer"}), [])

    def test_null_subschema_is_reported_not_accepted(self) -> None:
        # A top-level null schema is rejected by the loader contract...
        with self.assertRaises(schema_lite.SchemaError):
            schema_lite.validate(5, None)
        # ...and a nested null subschema node fails loudly instead of
        # silently accepting the value.
        nested = schema_lite.validate(
            {"x": 5}, {"type": "object", "properties": {"x": None}}
        )
        self.assertTrue(any("invalid schema node" in error for error in nested))

    def test_boolean_numeric_keyword_is_reported(self) -> None:
        errors = schema_lite.validate(0.5, {"type": "number", "minimum": True})
        self.assertTrue(any("schema minimum must be a number" in error for error in errors))
        multiple = schema_lite.validate(2.0, {"type": "number", "multipleOf": False})
        self.assertTrue(any("schema multipleOf must be a number" in error for error in multiple))

    def test_multiple_of_zero_stays_ignored(self) -> None:
        self.assertEqual(schema_lite.validate(2.0, {"type": "number", "multipleOf": 0}), [])


class AuditStoryScriptTests(unittest.TestCase):
    """V2/V13: portable roots, main() guards, no import-time execution."""

    def test_mains_run_green_and_side_effect_free(self) -> None:
        for name in ("audit_story_reachability", "audit_story_reachability2", "audit_story_rewards"):
            module = _load_audit_script(name)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(module.main([]), 0, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
