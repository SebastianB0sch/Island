# WS-07 — Data tooling & CI (Pass 4)

Branch `refactor/code-review-pass`, baseline checkpoint `77cc9c7`.
Session report for the findings owned by this workstream (V1–V14, 9a/9b/9c
plus the CI additions). Everything below was verified against the current
tree before editing; canon/runtime data under
`DuelAcademyIsland/Content/**` was **not** modified.

## Scope and constraints

Owned (edited): `Tools/canon/**`, `Tools/effects/**`, `Tools/economy/**`,
`Tools/validate/**`, `Tools/puzzles/**` (selftest runner only),
`Tools/story/**`, `Tools/opponents/**`, `Tools/tests/` (new/extended unittest
files), `Tools/integration/**`, `Tools/world/**`,
`Tools/audit_story_*.py`, `.github/workflows/ci.yml`, `.gitignore`,
`Docs/Integration/README.md`, `Docs/Integration/baseline.json`,
`Docs/Canon/VALIDATION.md`. New shared module: `Tools/tooling/`.

Unchanged by rule: every file under `DuelAcademyIsland/**` (incl. card data,
canon extracts, effect manifests), `Tools/dai/**`, all Python editor
(`Content/Python/**`) scripts, all git operations. Validators were run in
CHECK/NO-WRITE mode only, with two deliberate, explicitly-owned exceptions:
`Docs/Canon/VALIDATION.md` (final doc refresh via `--report`) and
`Docs/Integration/baseline.json` (via the new `build_baseline.py --write`).

## Findings table

| ID | Sev | Location (as reported) | Status | Resolution |
|----|-----|------------------------|--------|------------|
| V1 | MED | `Tools/effects/effect_data.py:99-104`, `generate_scripts.py:96`, `audit.py:79,93`, `coverage.py:385,387`, `report_coverage.py:637` | fixed | Shared atomic writer `Tools/tooling/atomic.py` (temp-in-dir → serialize → fsync → `os.replace`, cleanup in `finally`); all listed writers routed through it (`data.write_json` covers the engine-loaded `fusions.json` / `rituals.json` / manifest path used by `audit.py:79`). |
| V2 | MED | `Tools/audit_story_reachability.py`, `audit_story_reachability2.py`, `audit_story_rewards.py` | fixed | Rewritten with `DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "DuelAcademyIsland" / "Content" / "Data"` (pattern of `audit_story_fidelity.py`) and `main()` + `__main__` guards; work runs only inside `main()`. Output format preserved. |
| V3 | MED | `Tools/canon/validate_canon.py:297` | fixed | Gate now excludes the documented local-only dossier (`LOCAL_ONLY_DIR` from `canon_common`, honouring `GX_CANON_LOCAL_DIR`) via the extracted `collect_dialogue_leaks()` + `is_under()`. A `dialogue_full.json` in the repo fighter anywhere else still fails the gate. |
| V4 | MED | `Tools/opponents/import_canon_decks.py:614-621,633-643` | fixed | `audit_all()` / `reference_errors()` call sites in `main()` wrapped in `try/except (OSError, ValueError)` printing `error: cannot load opponent deck inputs:` and **exit 2** (tested contract). Both the `--check` and write paths covered. |
| 9b | MED | `Tools/puzzles/run_engine_selftests.py:129-137` | fixed | Subprocess run refactored into `_execute()` reusing `Tools/integration/run_smoke.py` `_popen_tree_kwargs()` / `_terminate_process_tree()` (single kill strategy). Direct-child timeout semantics kept (timeout bounds the child; partial stdout/stderr still captured). |
| 9c | MED | `Tools/canon/validate_canon.py:88-94,309-329` | fixed | Reports are now **off by default**: `--report` (optional path, no value = `Docs/Canon/VALIDATION.md`) is required to write; `--no-report` accepted as a no-op for old invocations. README + CI untouched by the flip (CI already passed `--no-report`). |
| V7 | LOW | `Tools/canon/validate_canon.py` (digests) | fixed | Record-digest validation added, mirroring each builder's algorithm exactly: `build_decks.sha_deck` (decks), `build_packs` (packs), `build_puzzles` (puzzles), `canon_common.card_fingerprint` + `cards_manifest.json` `canonical_hash` (cards). Mismatch → error; *absent* digest → WARN (3 legacy starter decks, see risks). Tests in `Tools/tests/test_canon_manifest.py` (extended; original tests intact). |
| 9a | LOW→best | `Docs/Integration/baseline.json` + new `Tools/integration/build_baseline.py` | fixed | New script recomputes every Python-only count from the data + validators (`validate_all --json`, `puzzles/validate.py`, `world/validate_layout.py --json`), preserves the Unreal strings as dated captured evidence, interpolates fresh numbers into `known_gaps`/`warnings`, and writes atomically; `--check` flags staleness (CI-usable later). `baseline.json` regenerated (schema_version 2, `computed_by`, fresh `generated_at`). README contradictions fixed (see V10). |
| V5 | LOW | `Tools/economy/sync_canon.py:105-110,263-282` | fixed | Missing-canon config errors now exit **2** (same class as the load-failure contract); deck-legality check now runs **before** the writes and violations are errors that abort before any file is written (fail closed). Current tree is clean, so behaviour on valid data is unchanged. |
| V8 | LOW | `Tools/canon/fetch_guides.py:62-68,84-89` | fixed | Fetch failures are tracked (stderr summary), the script exits **1** while pages remain empty, and an empty fetch result never overwrites an existing non-empty cache entry (`write` skipped instead of `cache[title] = ""`). |
| V9 | LOW | `Tools/world/validate_layout.py:193-195` | fixed | `load_json()` is now called unconditionally, so a **missing** `layout.json` is reported as an error (`missing file: …`) and fails the run; the "zone checks are limited" warn+degrade remains only for an existing-but-unreadable file. |
| V10 | LOW | `.gitignore`, `Docs/Integration/README.md:58` | fixed | Added the generated canon-report path `Docs/Integration/reports/canon-validation.md` (consistent with the existing reports pattern). README gate commands now use `--no-report` for the canon gate, note that `--report Docs/Canon/VALIDATION.md` is the deliberate doc-refresh and that any explicit `--report` path is overwritten per run; CI-style temp paths documented. |
| V11 | LOW | `Tools/validate/schema_lite.py:33,134,334-346` | fixed | `integer` accepts integer-valued floats (`2.0` ok, `2.5` rejected — draft-07); `null` subschema nodes now error (`validate()` top-level still raises `SchemaError` by contract) instead of silently passing; numeric keywords (`minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`) reject booleans/non-numbers with a schema error instead of comparing `True`-equals-`1`. |
| V12 | LOW | `Tools/validate/validate_all.py:4861+` (docstring exit codes) | fixed | Unexpected validator exceptions now exit **2** (honoured after report printing; report still written for `--report` runs); `--debug` still re-raises. Data failures keep exit 1. |
| V6 | LOW | `Tools/story/add_choices.py:130-148` | fixed | The tautological `strip_outcomes` block was deleted with a post-migration note: matching `grant_card`/`set_title` outcomes only when they carry a `flag` key never matched, so the block never changed any outcome and the canonical data it ran on is untouched; the effective flag-only removal pass is kept. |
| V13 | INFO | `Tools/audit_story_reachability.py:39` | fixed | Dead `... if False else ...` branch removed (now simply `any(has_flag_block(r) ...)`) as part of the V2 rewrite. |
| V14 | INFO | `Tools/effects/effect_data.py:190` | fixed | Docstring re-derived honestly from the manifest: **109** `engine_cpp` tier-0 rows; the remaining **28** are 27 Normal Monsters + the effect-free Fusion Monster 319 (tier0 137 total, verified against `card_effect_manifest.json`). |
| CI | small | `.github/workflows/ci.yml` | fixed | New step after the pipeline checks: `coverage.py --check`, `report_coverage.py --check > /dev/null`, `python Tools/effects/audit.py` (matrix untouched). Flags verified; check-forms verified exit 0 locally; audit.py's default-stage targets verified read-only against the current data (Tier 0/1 100%, fusion 75/76 resolved ≥ 95%, ritual 22/22, no validation errors → would exit 0). |

Nothing was refused or deferred.

## Changes and rationale

- **`Tools/tooling/`** (new): `__init__.py` + `atomic.py` — same-directory
  temp file → serialize → flush + `os.fsync` → `os.replace`, with cleanup on
  failure and parent-dir creation. `write_text`, `write_bytes`,
  `write_json` (indent=2, `ensure_ascii=False`, trailing LF — byte-identical
  serialization with the previous first-try writers so refreshed outputs do
  not reformat). Imported the way the script folders already bootstrap:
  `sys.path.insert(0, <Tools dir>)` then `from tooling import atomic`.
- **Effects lane (V1)**: `effect_data.write_json` (the single funnel that
  writes `Data/fusions.json`, `Data/rituals.json`, the effect manifest and
  candidates — all engine-loaded) now publishes atomically.
  `generate_scripts.py`, `audit.py`, `coverage.py`, `report_coverage.py`
  route their JSON/Markdown outputs through the same helper.
- **Canon tools (V3/9c/V7/V8)**: as in the table; plus `fetch_guides` keeps
  atomic-writes via `canon_common.write_text` (unchanged) and its new
  fail-closed semantics are documented in the module docstring.
- **Audit scripts (V2/V13)**: fully portable, import-safe (the old files
  executed on `import`), no behaviour change to the printed tables.
- **`run_engine_selftests.py` (9b)**: process launch moved to `_execute()`
  sharing `run_smoke`'s tree-kill helpers; no third kill strategy. The log
  file format (`TIMEOUT after <n>s`, stdout/stderr capture) is unchanged.
- **`build_baseline.py` (9a)**: mode-by-default prints, `--check` exits 1 on
  stale counts, `--write` refreshes. Unreal evidence preserved verbatim with
  a capture note instead of silently claiming fresh numbers that the
  Python-only toolchain cannot verify.

## Verification (exact commands, exit codes)

All run from `C:\dev\GX` (Python 3.14.6):

| Command | Exit | Notes |
|---|---|---|
| `python -m unittest discover -s Tools/tests` | **0** | `Ran 186 tests in 11.077s OK` (baseline before this workstream: 126 tests) |
| `python Tools/validate/validate_all.py` | **0** | `0 error(s), 15 warning(s), 6 gap(s), 304 info; 421 file(s) read — PASS` (unchanged vs. baseline run) |
| `python Tools/canon/validate_canon.py --no-report` | **0** | `checks: 298 errors: 0 warnings: 2` (was 290/1; +8 digest-check rows, +1 honest WARN for the 3 legacy starter decks) |
| `python Tools/effects/validate_effects.py` | **0** | `OK: 253 effect script(s), fusion 75/76 resolved, ritual 22/22 resolved, 0 warning(s)` |
| `python Tools/puzzles/validate.py` | **0** | `PASS summary: 145 checks, 0 failures, 1 warnings` |
| `python Tools/economy/validate_decks.py` | **0** | `PASS - 81 checks, 0 failures` |
| `python Tools/economy/validate_packs.py` | **0** | `PASS - 1342 checks, 0 failures` |
| `python Tools/opponents/import_canon_decks.py --check` | **0** | `32/32 runtime decks legal; 37/37 constructed decks legal; 32/32 refs resolve` |
| `python Tools/world/validate_layout.py` | **0** | `PASS` |
| `python Tools/effects/test_effects.py` | **0** | 9 tests OK (generator refuse path still green) |
| `python Tools/world/test_interiors.py` | **0** | PASS |
| `python Tools/audit_story_reachability.py` / `...reachability2.py` / `...rewards.py` | **0/0/0** | portable now, run from any CWD |
| `python Tools/integration/build_baseline.py` | **0** | fresh counts printed; `--check` → **0** (idempotent; re-verified after the VALIDATION.md refresh) |
| `python -m compileall -q Tools .github` | **0** | |

New/updated regression coverage (`Tools/tests/test_data_tooling_ci.py`, 28
tests; `Tools/tests/test_canon_manifest.py`, +6 tests, 19 total):

- tooling atomicity: JSON/MD round-trip, temp-file litter, failed
  serialization keeps the previous file (V1).
- `generate_scripts` refuse-to-overwrite keeps existing bytes and stays
  atomic; `--check` writes nothing (V1).
- `effect_data.write_json` atomic publish (V1).
- `import_canon_decks --check` with missing `decks.json`,
  `Decks/player_decks.json` and `events.json` → exit 2, no traceback (V4).
- `fetch_guides`: all-fail sweep → exit 1, previous entries preserved, no
  `""` entries written; failed refetch never replaces good entries; full
  success → exit 0 (V8), network stubbed.
- `run_engine_selftests._execute` kill path using the portable
  grandchild-PID fixture from `test_run_smoke.py` → grandchild confirmed
  dead; in-time child keeps return code 3 (9b).
- `validate_layout.py`: missing `layout.json` → error; corrupt file → error
  + "zone checks are limited" (V9).
- `sync_canon`: config error exit 2; illegal generated banlist → violations
  reported, **no** output files written (fail closed); legal → files
  written normally (V5).
- `validate_all`: `RuntimeError` in a lane validator → exit 2 + stderr note;
  pure data failure still exit 1 (V12).
- `schema_lite`: `2.0`∈integer, `2.5`∉integer, null subschema errors,
  boolean bounds rejected, `multipleOf: 0` still ignored (V11).
- canon record digests: mirroring `deck_record_digest` /
  `pack_record_digest` / `puzzle_record_digest` /
  `card_fingerprint`+canonical recompute all match the committed data;
  corruption is detectable (V7). `collect_dialogue_leaks` honours
  `LOCAL_ONLY_DIR` and the `GX_CANON_LOCAL_DIR` override (V3).
- audit story scripts: `main([])` returns 0 for all three (V2).

`git diff --check` could not be run (no git commands allowed); an equivalent
scan over all 27 touched files found **0 trailing-whitespace/tab issues** and
0 injected line-ending changes; `.gitignore` and
`Tools/world/validate_layout.py` were already CRLF in the baseline tree and
were left byte-faithful.

## Remaining risks / notes

1. **`Docs/Canon/VALIDATION.md` and `Docs/Integration/baseline.json` changed
   by design** (owned docs, deliberate refresh). VALIDATION.md now records
   the 8 new digest checks and the starter-deck digest WARN; baseline.json
   is schema_version 2 with renamed UE sections (`unreal_evidence`,
   `smoke_captured`) — no code consumers of the old key names exist
   (grep-verified; only prose references).
2. **Digest coverage gap (WARN, not error)**: canon decks `fire`, `water`,
   `wind` predate the digests; back-filling requires re-running
   `Tools/canon/build_decks.py` against the guide cache, which would rewrite
   canon-owned data — off-limits here (see hand-off).
3. **CI `audit.py` step** regenerates its own derived files
   (`card_effect_manifest.json`, `Docs/Effects/COVERAGE.md`) on the CI
   workspace by design; on an in-sync checkout the rewrite is byte-identical
   (deterministic manifest verified by `test_effects.py`), and the step
   fails on any missed coverage target. It checks tier 0/1 + recipe
   accounting (default stage); Tier 2/3 stay informational until `--release`.
4. **`build_baseline.py` parses validator stdout** (`PASS summary:` /
   `duelists=...` line of `Tools/puzzles/validate.py`, `--json` payload of
   `validate_all.py`); a future format change breaks it loudly at the next
   `--write` (fail-fast, no silent stale data). Adding its `--check` to CI
   is a natural follow-up but was not requested.
5. **Effects coverage numbers** (`253` data scripts + `109` engine_cpp =
   `362` scripted) are honesty-refreshed in baseline.json/README; they move
   whenever A05 scripts more cards — `build_baseline.py --write` keeps the
   doc truthful mechanically.
6. **Unreal evidence** in `baseline.json` (`unreal_evidence`,
   `smoke_captured`) is dated captured data (2026-10-30) the Python-only
   toolchain cannot re-verify; README marks the refresh procedure
   (`run_smoke.py --all`) for the next content gate.

## Integration hand-offs

- **Canon data owner (A01 / parent):** add the embedded `sha256` to the three
  canon starter decks (`fire`, `water`, `wind`) by re-running
  `Tools/canon/build_decks.py` (uses `Tools/canon/cache/decks_facts.json`,
  no ROM needed) — this clears the `decks.record_digests` WARN in
  `Docs/Canon/VALIDATION.md`; hash refresh must follow canon manifest rules
  (`Tools/canon/build_manifest.py --refresh-hashes` is NOT needed if only
  digests change inside `decks.json` — its `records` counts stay stable; a
  content fingerprint rebuild would be).
- **Parent (CI):** the new step assumes `Tools/effects/audit.py` runs on a
  clean checkout (it writes its own derived artifacts; workspace-only).
  Optionally wire `python Tools/integration/build_baseline.py --check` into
  the pipeline to keep `baseline.json` from drifting again.
