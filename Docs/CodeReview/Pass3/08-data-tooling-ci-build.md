# 08 — Data tooling, validators, CI and build harness (pass 3)

Branch: `refactor/code-review-pass` (the pass-1/pass-2 working tree is the
baseline; this report only describes additions on top of it).

Scope: `Tools/canon/**`, `Tools/story/**`, `Tools/validate/**`,
`Tools/puzzles/*.py`, `Tools/economy/*.py`, `Tools/opponents/**`,
`Tools/integration/**`, `Tools/tests/test_run_smoke.py` and new
`Tools/tests/**` files, `.github/workflows/ci.yml`,
`Docs/Integration/README.md`, `DAA02GateTests.cpp`, the game-mode files and
`DuelAcademyIsland.Build.cs`/target/config files, plus the one canon manifest
whose hashes had to be refreshed (explicitly allowed by the workstream brief).
No runtime save, gameplay or generated asset code was edited.

Constraints honoured: no UnrealBuildTool, UnrealEditor, Blender or other Unreal
process was launched; no commit or stage was made; all generated reports/logs
were written under `%TEMP%` and none were added to the repository.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| F1 | High | `DuelAcademyIsland/Content/Data/Canon/manifest.json`; `Tools/canon/build_manifest.py` | The manifest recorded hashes for `cards_manifest.json` and `exams.json` from before commit `bef5982` sanitized `source.rom` from an absolute workstation path to `$GX_ROM`. That sanitization removed exactly 43 bytes from each file, but the manifest was not rebuilt; `validate_canon.py` therefore failed with two stale hashes. The committed file bytes are authoritative. | Fixed with a controlled `build_manifest.py --refresh-hashes` that refuses to run if the file set or any `records` count changes. Only the two hashes, byte counts and `generated_utc` changed in `manifest.json`. |
| F2 | High | `Tools/canon/build_manifest.py` old loop | A missing canon file was printed and silently skipped, yet the build returned 0 and wrote a manifest that omitted it. | Fixed: missing files are a hard error (exit 1) in both full and refresh modes. |
| F3 | High | `Tools/canon/validate_canon.py` old `manifest.hashes` check | The check only searched for `"hash mismatch"`, so a missing file, duplicate entry, bad digest, or wrong byte count was not reflected in the check result. The manifest also never asserted that all published files are listed. | Fixed with `manifest_hash_errors()`: missing/malformed/duplicate/unexpected entries, missing files, digest mismatches, invalid digests and byte-size mismatches are all reported. |
| F4 | High | `Tools/validate/validate_all.py` | The baseline validator never read `Canon/manifest.json`, so a stale canon hash passed the main CI gate. | Fixed: `canon_manifest` check plus `canon_manifest_*` findings for missing/hash/size/duplicate/path failures. |
| F5 | Medium | All twelve `Tools/story/*.py` migrations | The scripts ran their writes at import time and used non-atomic `Path.write_text`. Importing a helper or a test could silently rewrite authored story data; a crash could truncate events/scenes/dialogue. | Fixed: every script has `main()` and an `if __name__ == "__main__"` guard; reads/writes use `Tools/story/story_common.py` with same-directory temp + `os.replace` and stable UTF-8/LF JSON. `add_choices.py` is now idempotent (it does not insert a second choice command/end), and `add_e29_recovery.py` deduplicates the DP outcome instead of using the previous tautological filter. |
| F6 | Medium | `Tools/integration/run_smoke.py` report/log writers | Step logs and the final smoke JSON were written directly. A killed report write could leave a truncated JSON report; an unwritable report path raised a traceback instead of a configuration error. | Fixed: `_write_text_atomic()` is used for logs and reports; report-directory/report-path failures return 2 with a short diagnostic. |
| F7 | Medium | `run_smoke.py::_inspect_automation` | A no-tests phrase plus a completion line could turn an unexpected crash exit (for example 7) into an intentional `skip`. | Fixed: the skip contract now accepts only completion codes `0/-1` with process exits `0/-1/255`; anything else stays a failure. Existing timeout/crash/no-marker cases remain fail-closed. |
| F8 | Medium | `Tools/economy/*.py`, `Tools/puzzles/generate_*.py`, `Tools/puzzles/validate.py`, `Tools/opponents/import_canon_decks.py` | Several CLIs loaded required data before any error handling, producing a traceback (generic exit 1) for missing/corrupt inputs; `sync_canon.py` had no argument parser at all, so unknown flags were silently ignored and it performed writes. | Fixed: explicit diagnostics and exit 2 for unreadable inputs; `sync_canon.py` now has `--check` (build/validate without writing) and rejects unknown options. `puzzles/validate.py` and `generate_puzzles.py` accept `argv` for tests, and the puzzle report write is atomic. |
| F9 | Low | `Tools/puzzles/run_engine_selftests.py` | One-second log slugs could collide; the log write was non-atomic; `--timeout 0`/negative caused a `ValueError` traceback. | Fixed: microsecond/PID slug, atomic log write, `--timeout >= 1` validation and exit 2 on log-write failure. |
| F10 | Low | `.github/workflows/ci.yml` | The canon gate was absent because the manifest was stale; only Python 3.13 was exercised. | Fixed: canon gate added after it passed locally, and the job now covers Python 3.12 and 3.13. Actions remain SHA-pinned, checkout is non-persistent and the 10-minute ceiling remains. |
| F11 | Low | `Docs/Integration/README.md` | The gate commands did not mention the canon validator and the current-state paragraph did not state the canon result. | Fixed: canon command and the verified 290-check/0-error/1-warning result added. |
| F12 | Low | `Tools/opponents/import_canon_decks.py` report text | The generated report still claimed `Data/decks.json` had four Luster Dragon copies and that `sync_canon.py`/`DAEconomyTests` used a 20-card Extra Deck. Both statements are stale; the current files use three Luster copies and a 15-card cap. | Fixed in the report generator. |
| F13 | Low | `DAA02GateTests.cpp` | The save fuzz asserted cleanup only indirectly; a primary/backup/temp file left behind would not fail the test even though it would leak into the player save folder. | Added post-cleanup checks for every fuzz/corruption/migration slot and the twelve-month slot. Runtime save code was not changed. |
| F14 | Info | `Docs/Integration/baseline.json` | Baseline counts are stale (for example canon decks 31→37, effects scripted 119→362, and old warning/gap counts). The file is outside this workstream's owned set. | Not edited; listed as a cross-workstream follow-up below. |
| F15 | Info | `Tools/puzzles/run_engine_selftests.py` | The dedicated runner still uses `subprocess.run(timeout=…)`, which kills only the direct child. The gate path `run_smoke.py` has the full process-tree killer. | Documented as a remaining risk; not changed because the active merge gate uses `run_smoke.py`. |

## Changes

### Canon manifest and validation

- `Tools/canon/canon_common.py`: added `ROM_SOURCE_LABEL = "$GX_ROM"` so future
  extraction runs write the same portable label that is already committed.
- `Tools/canon/extract_cards.py`, `extract_exam.py`: write that label instead
  of the local absolute ROM path. This removes the root cause of the 43-byte
  sanitization drift; no generated values changed.
- `Tools/canon/build_manifest.py`:
  - `build_file_entries()` returns entries plus missing files.
  - `refresh_manifest_hashes()` refreshes hash/byte/record entries only after
    checking that the manifest file set and every `records` count are unchanged;
    otherwise it raises `ManifestDriftError`.
  - `--refresh-hashes` is the controlled republish path; full builds now fail
    on missing files instead of silently omitting them.
- `DuelAcademyIsland/Content/Data/Canon/manifest.json`: refreshed the two stale
  entries. Exact changes: `cards_manifest.json` 97886 → 97843 bytes and
  `4f6368b…` → `5ec865d…`; `exams.json` 88779 → 88736 bytes and `6da1556…` →
  `3c314f3…`; `generated_utc` updated. No other field or data file changed.
- `Tools/canon/validate_canon.py`: added `manifest_hash_errors()`, full
  missing/duplicate/size/coverage checks, `--report PATH` and `--no-report`.
  The default still writes `Docs/Canon/VALIDATION.md` (documented contract); CI
  uses `--no-report` so the checkout stays clean.
- `Tools/canon/fetch_guides.py`: cache write is atomic.
- `Tools/validate/validate_all.py`: added the `canon_manifest` check and
  findings; the validator now reads one more file (421 vs 420) but the baseline
  warning/gap/error counts are unchanged.
- `Tools/validate/README.md`: documented the new check.

### Story migrations

- New `Tools/story/story_common.py`: repository paths plus atomic
  `read_json`/`write_json` (UTF-8, LF, `indent=2`, temp + `os.replace`).
- All twelve migration scripts now expose `main()`, do no work at import, and
  use the shared writer. `add_choices.py` skips an already-present choice and
  `add_e29_recovery.py` keeps exactly one `grant_dp_from_last_lp` outcome.
- No authored data was regenerated or rewritten during this work; the
  import-only regression test snapshots the data files and verifies that
  importing every migration leaves bytes and mtimes untouched.

### Harness, validators and generators

- `Tools/integration/run_smoke.py`: atomic log/report writes, report-path
  diagnostics (exit 2), tightened automation no-tests skip.
- `Tools/tests/test_run_smoke.py`: new tests for the unexpected-exit skip case,
  the successful no-tests skip, atomic writes and unwritable report paths.
- Economy/opponent/puzzle CLIs now report missing inputs with exit 2;
  `sync_canon.py --check` is write-free.
- `Tools/puzzles/run_engine_selftests.py`: portable log slug, atomic log,
  timeout validation.
- `Tools/puzzles/validate.py`: atomic Markdown report and exit 2 on write
  failure.

### CI, docs and build/test integrity

- `.github/workflows/ci.yml`: Python 3.12/3.13 matrix, canon gate added,
  existing gates preserved. Actions are still pinned to commit SHAs; the job
  keeps its 10-minute timeout and uses `$RUNNER_TEMP` for harness artifacts.
- `Docs/Integration/README.md`: canon gate command and verified status.
- `DAA02GateTests.cpp`: added save-file cleanup assertions. No runtime save
  code was touched.
- `DuelAcademyIsland.Build.cs`, `DuelAcademyIsland*.Target.cs` and
  `Config/Default*.ini` were reviewed. No high-confidence defect was found:
  the module list covers the includes in use, input uses Enhanced Input, and
  online/EOS settings are disabled for offline single-player. No config was
  regenerated or re-tuned.

## Tests added

- `Tools/tests/test_canon_manifest.py` (13 cases): committed manifest matches
  every file; file-set coverage; tampered/missing/unexpected/duplicate entries;
  `validate_all` wiring for missing/hash/path errors; refresh success and
  refusal on record/file-set drift; refresh failure keeps the old manifest;
  report-path error code.
- `Tools/tests/test_story_scripts.py` (6 cases): every migration has a main
  guard, no module-scope writes, importing all migrations leaves data bytes and
  mtimes unchanged, and the shared writer is atomic and failure-safe.
- `Tools/tests/test_cli_error_codes.py` (9 cases): missing-input exit 2 for
  exams/puzzles/economy/opponents, `sync_canon --check` writes nothing, invalid
  harness timeout, and puzzle report-write failure.
- `Tools/tests/test_run_smoke.py` (+4 cases, now 56): automation skip
  tightening, atomic writer, unwritable report path.

## Verification

Environment: Windows, Python 3.14.6 and 3.12.10, repository root `C:\dev\GX`.
No Unreal, UBT or Blender process was launched.

| Command | Result |
|---|---|
| `python -m compileall -q Tools DuelAcademyIsland/Content/Python` | exit 0 |
| `python -m unittest discover -s Tools/tests` | **122 tests, OK**, ~9.4 s |
| `py -3.12 -m unittest discover -s Tools/tests` | **122 tests, OK**, ~8.7 s |
| `python Tools/canon/build_manifest.py --refresh-hashes` | exit 0, 21 files refreshed (only the two stale entries changed) |
| `python Tools/canon/validate_canon.py --no-report` | **290 checks, 0 errors, 1 warning**, exit 0 |
| `python Tools/canon/validate_canon.py --report %TEMP%\gx-canon\VALIDATION.md` | exit 0; report written outside the repository |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors, 15 warnings, 6 gaps, 304 info; 421 files read |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 0 failures, 1 warning; duelists=26 decks=32 ai=27 puzzles=100 questions=30 cycles=12 |
| `python Tools/economy/validate_decks.py` | **PASS** — 81 checks, 0 failures |
| `python Tools/economy/validate_packs.py` | **PASS** — 1,342 checks, 0 failures |
| `python Tools/opponents/import_canon_decks.py --check` | **PASS** — 32/32 runtime decks, 37/37 constructed decks, 32/32 refs |
| `python Tools/economy/sync_canon.py --check` | exit 0; 48 packs, 14 forbidden, 40 limited, 7 semi-limited; no files written |
| `python Tools/integration/run_smoke.py --validate --report-dir %TEMP%\gx-smoke-final ...` | **PASS**, exit 0; report/log only in temp |
| `python Tools/integration/run_smoke.py --all --dry-run --report-dir %TEMP%\gx-smoke-dry ...` | exit 0; 7 planned steps, all skip |
| YAML parse of `.github/workflows/ci.yml` (PyYAML `safe_load`) | valid; 1 job, 16 steps, matrix Python 3.12/3.13 |
| `git diff --check` | exit 0 (only Git's LF→CRLF advisory warnings from the global checkout config) |
| `git status --short` on scoped data/report paths | only intended source/CI/report changes; no generated canon/smoke artifacts |

## Remaining risks and follow-ups

1. **Full canon rebuild still needs the ROM.** `--refresh-hashes` is safe for
   sanitized/re-serialized files, but any real content change must go through
   `build_all.py` and a full manifest build. Do not use `--refresh-hashes` to
   paper over changed record counts; the tool refuses that case.
2. **`Docs/Integration/baseline.json` is stale.** It still records 31 canon
   decks, 119 scripted effects and older warning/gap totals. It is outside this
   workstream's owned file set; A10 should regenerate it from the current
   validator/smoke output.
3. **The C++ additions were not compiled or run here.** The parent session owns
   the build and headless suite. The new checks depend on the existing
   `UDASaveSubsystem::GetSaveFilePath`/`DeleteNamedSlot` behaviour already used
   by the same test file.
4. **`run_engine_selftests.py` timeout is still child-only.** The dedicated
   runner is not the merge gate; `run_smoke.py` has the process-tree killer.
   Aligning the dedicated runner with those helpers is a reasonable follow-up.
5. **Story migrations are atomic per file, not transactional across the three
   data documents.** A crash between writes can leave one document updated and
   another not. They are one-shot migrations, now import-safe and idempotent
   where it matters.
6. **CI was validated by YAML parsing only.** The matrix doubles the job count;
   the 10-minute ceiling is unchanged and all steps are expected to stay well
   under it, but the first hosted run is the real timing check.
7. **`run_smoke`'s no-tests skip remains a log heuristic.** It now rejects
   unexpected exit codes, but a future Unreal log format change can still
   require parser maintenance. The failure mode is fail-closed (a skipped gate
   becomes a failure).
8. **`validate_canon.py` still writes `Docs/Canon/VALIDATION.md` by default.**
   This is the documented report contract; local runs should use
   `--no-report` when a clean tree is required. CI uses `--no-report`.
9. **`sync_canon.py` writes three files, one at a time.** `--check` avoids
   writes for inspection, but the normal run is not a single transaction across
   `Shop/packs.json`, `Rules/card_rarity.json` and `Rules/banned_limited.json`.
10. **No gameplay tuning or config regeneration was performed.** Build/config
    review found no high-confidence defect; if the parent's build reports a
    module or setting issue, that should be handled from the build log rather
    than speculative config edits.

## Cross-workstream changes the parent must integrate

- None required in runtime code. The only C++ edit is the owned test file
  `DAA02GateTests.cpp`; workstream 02 does not need to change save runtime.
- Parent must run UBT and the headless self-tests to compile and exercise the
  new cleanup assertions.
- A10/data owner should refresh `Docs/Integration/baseline.json` (stale counts
  listed above).
- If the parent keeps a generated `Docs/Canon/VALIDATION.md` in the tree, run
  `python Tools/canon/validate_canon.py` once after integration; otherwise use
  `--no-report` and leave the existing report untouched.

## 6. Parent integration follow-up

- Concurrent workstreams briefly restored the pre-pass canon manifest after
  this workstream refreshed it. The parent reran
  `Tools/canon/build_manifest.py --refresh-hashes`; the final manifest matches
  the committed `cards_manifest.json` and `exams.json` bytes and
  `validate_canon.py --no-report` reports 290 checks / 0 errors / 1 warning.
- `Tools/build_island.py` was hardened during integration: `parse_stages()`
  rejects unknown names/options with exit 2, `--help` exits before importing
  NumPy/dai, stage order is normalized, and three parser tests were added to
  `Tools/tests/test_cli_error_codes.py`.
- The final Python suite is **126 tests** on both 3.14 and 3.12; validator,
  smoke, economy, puzzle, opponent and world gates pass.
- `Docs/Integration/baseline.json` remains stale and is still an A10 follow-up.
