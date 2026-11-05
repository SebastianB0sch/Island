# 05 — Python pipeline & validators

Branch: `refactor/code-review-pass`

Scope: `Tools/build_island.py`, `Tools/preview_asset.py`, `Tools/preview_anime.py`,
`Tools/audit_story_fidelity.py`, `Tools/dai/**` (excluding `thirdparty/`,
`.blender_site/`, `.cache/`), `Tools/canon/**`, `Tools/economy/**`,
`Tools/opponents/**`, `Tools/puzzles/**`, `Tools/story/**`,
`Tools/world/**`, `Tools/validate/**`, `DuelAcademyIsland/Content/Python/**/*.py`,
new tests under `Tools/tests/`, and this report. No C++, game data, `Tools/effects`,
or `Tools/integration` files were changed. The island/Blender pipeline was not
run.

## Summary

The Python pipeline is generally deterministic already: layout scatter uses a
seeded RNG, instances are sorted by asset name before writing, and the canon
builders sort sets before serializing. The real weaknesses were in the gates
and in tool portability, not in the generated values:

- `Tools/validate/validate_all.py` could report `PASS` while an individual
  check was `FAIL`, because `Report.result()` only counted findings. Several
  validators increment an `errors` counter for a malformed entry without
  attaching a finding, so the failed check was the only evidence.
- `schema_lite.py` silently treated an unknown `type` keyword as valid, so one
  typo in a contract schema could disable that schema entirely.
- `validate_all.py` skipped individual canon extract files when they were
  missing, and accepted empty deck/dialogue/scene/email/schedule/anchor
  collections as passes.
- Several canon/story tools hard-coded `C:\dev\GX` or a workstation temp path.
- The JSON report writer used platform newline translation and was not atomic.
- A mixed legacy/v1 event bundle normalized v1 records through the legacy
  mapper, dropping their fields.

The baseline gate remains green after the changes. The pre-existing
`import_canon_decks.py --check` failure was traced to a missing runtime-id
mapping entry, not a missing deck (details below), and was fixed during
integration.

## Findings

| ID | Severity | Location | Finding |
|---|---|---|---|
| F1 | High | `Tools/validate/validate_all.py:236-247` (old result logic) | `Report.result()` ignored `Check.status`. A validator can append a `fail` check without a finding — e.g. non-object canon entries (`:765-842`) or non-object portals/spawns/interiors (`:2440`, `:2483`, `:2511`) — and the overall run still printed `PASS`. Fixed by treating any `fail` check as a failed result. |
| F2 | High | `Tools/validate/schema_lite.py:150-158` | `_matches_type()` returned `True` for an unknown type name. A schema typo such as `"integerr"` therefore validated every value. Fixed by reporting an unknown schema type as an error. |
| F3 | High | `Tools/validate/validate_all.py:745-757` | `validate_canon_reference.items()` returned `(None, [])` for a missing canon file; callers only emitted checks when the document existed. Deleting `Canon/decks.json` produced no finding and no check at all. Fixed with an explicit `canon_file_missing` gap. |
| F4 | Medium | `Tools/validate/validate_all.py:1553, 2524, 3589, 3762, 3856, 3934, 4078` | Files that existed but contained zero records passed: empty deck/dialogue/scene/email/schedule/anchor collections emitted `PASS`. Fixed with explicit empty-collection gaps. |
| F5 | Medium | `Tools/validate/validate_all.py:3175-3220` | When any event in a bundle used the legacy `when`/`outcomes` shape, every event was passed through `_normalize_legacy_event()`. Mixed v1 records lost their `date`, `requires`, `commands`, rewards and other fields. Fixed to normalize only records matching the legacy predicate. |
| F6 | Medium | `Tools/validate/validate_all.py:344-389` | `load_json()` only caught `JSONDecodeError`/`ValueError`; invalid UTF-8 and `OSError` escaped to the generic `internal_error` boundary. `path.exists()` also accepted a directory, producing a later read error. Fixed with `is_file()` plus explicit `json_encoding`/`file_unreadable` findings. |
| F7 | Medium | `Tools/validate/validate_all.py:4713-4737`, `:4807-4814` | The `--report` output was written with `Path.write_text`, which translates newlines on Windows, and was not atomic; an interrupted run could leave a partial report. Fixed with a same-directory temp file, `os.replace`, UTF-8 and LF. |
| F8 | Medium | `Tools/validate/validate_all.py:212-229` | `apply_schema()` and the owning validator both called `report.check()` with the same key on schema failure, producing duplicate, contradictory checks (one `fail`, one `pass`). Fixed by merging duplicate keys and keeping the worst status. |
| F9 | Medium | `Tools/validate/validate_all.py:4754, 4801` | The exception handler checked `--debug`, but the parser never registered it, so `python Tools/validate/validate_all.py --debug` exited with an argparse error before any validation. Fixed by registering `--debug` and using `args.debug`. |
| F10 | Medium | `Tools/canon/build_banned.py:49`, `build_packs.py:303`, `build_puzzles.py:100`, `build_events.py:541`, `build_decks.py:215` | Four canon builders defaulted `--source` to `C:\Users\Sebas\AppData\Local\Temp\opencode\gxcanon\guide_wikitext.json`; the deck builder used cwd-relative `Tools/canon/cache/guide_wikitext.json`. All now resolve `CACHE_DIR / "guide_wikitext.json"`. |
| F11 | Medium | `Tools/audit_story_fidelity.py:3, 60` (pre-fix) | Hard-coded `C:\dev\GX`, unconditionally opened a user-specific temp dossier, had no `if __name__` guard and several `open()` calls without `encoding=`. Rewritten as a portable `--root`/optional `--local` CLI. |
| F12 | Medium | `Tools/story/*.py:4` (11 files) | `add_*`, `complete_e33`, `fix_*` scripts hard-coded `C:\dev\GX\DuelAcademyIsland\Content\Data`. They now derive the repository root from `__file__`. |
| F13 | Low | `Tools/validate/validate_all.py:517, 717` | The `cards` check used the global warning count for its status, so a warning produced by another lane could mark `cards` as `WARN` (and order changes could alter the report). Fixed to use the card-specific warning delta. |
| F14 | Low | `Tools/puzzles/validate.py:105-107, 175-177, 669-671, 1145-1172` | Missing `Opponents/decks`, `Opponents/ai` or `Puzzles` directories raised `FileNotFoundError` before the validator could report a failure; non-object JSON roots crashed on `.get()`; `--report report.md` passed an empty dirname to `os.makedirs`. Fixed with directory/type guards and a parent check. |
| F15 | Low | `Tools/world/validate_layout.py:124-132` | `zone_contains()` returned `True` when a zone had no valid `center`/`extent`, so a malformed zone silently accepted every point. Fixed to return `False`. |
| F16 | Low | `Tools/validate/README.md:30`, `Tools/canon/validate_canon.py:123` | Both documented/allowed an Extra Deck of 20, while `Rules/banned_limited.json` and the runtime validators use 15. Updated to 15. |
| F17 | Medium | `Tools/validate/validate_all.py:3184-3186, 3942-3944` | Event and schedule discovery uses `first_existing(candidates)`, so only one `Story/events/*.json` or `Story/schedules/*.json` file is ever validated when the root bundle exists. Latent file-discovery gap; not changed. |
| F18 | Low | `Tools/opponents/import_canon_decks.py:247-253`, `Tools/economy/sync_canon.py:62-66`, `Tools/puzzles/generate_puzzles.py:446-448` | These remaining writers are UTF-8 but non-atomic, and the generator writes directly to the data tree. Not changed; documented as follow-up. |
| F19 | Info | `Tools/validate/validate_all.py:4531` vs `:4278` | Cross-check rejects `unsupported` cards in decks/packs/puzzles but does not reject `pending` cards, despite the `effects_pending` hint saying pending cards must not appear in content. Content-policy decision, not changed. |
| F20 | Info | `Tools/validate/validate_all.py:253` | `generated_at` makes report bytes differ on every run by design. Ordering and findings are deterministic otherwise. |

No non-deterministic set/dict iteration was found affecting generated layout or
terrain data: `Layout.write()` sorts `instances`, scatter is seeded, and the
canon builders sort sets before output. The new atomic writer preserves the
existing `indent`/`separators` choices, so regenerated files keep their current
shape.

## Changes

### Gate and schema correctness (`Tools/validate`)

- `validate_all.py`
  - `Report.result()` now fails on any `fail` check as well as any error
    finding; strict/fail-on-gaps also honour `warn`/`gap` check statuses.
  - `Report.check()` merges duplicate keys and keeps the worst status/summary,
    so schema failures no longer coexist with a contradictory validator check.
  - `load_json()` rejects directories and reports invalid UTF-8/OSError as
    findings instead of reaching the generic internal-error boundary.
  - Canon extract files are reported as `canon_file_missing` gaps.
  - Empty deck/dialogue/scene/email/schedule/anchor collections are gaps, not
    passes.
  - Mixed legacy/v1 event bundles normalize only legacy records.
  - `cards` status uses its own warning delta, not global warnings.
  - `--debug` is a registered argparse flag and raises the original exception.
  - `--report` uses `write_report()`, an atomic UTF-8/LF writer.
- `schema_lite.py`
  - `load_schema()` translates OSError into `SchemaError`.
  - Unknown `type` values are reported instead of acting as a wildcard.
- `README.md`: corrected the Extra Deck limit and stale canon counts
  (37 canon decks / 28 opponents).
- New `Tools/tests/test_python_pipeline.py`: seven stdlib `unittest` cases for
  unknown schema types, failed-check aggregation, duplicate-key rejection,
  stable LF report bytes, and compact pipeline JSON output.

### Deterministic / atomic writes (`Tools/dai`, `Tools/canon`)

- Added `Tools/dai/jsonio.py`: `read_json()` and atomic `write_json()` with
  UTF-8, explicit newline handling, and caller-selected indentation/separators.
- Routed `layout.py` (`layout.json`, `materials.json`, `assets.json`),
  `terrain.py` (`terrain_info.json` and its reads), `character.py`
  (`character.json`), `textures.py` (`terrain_layers.json`), `anime/build.py`
  (`cast.json`, rewritten `layout.json`) and `render.py` reads through it.
- `canon_common.write_json()`/`write_text()` now write through a same-directory
  temp file and `os.replace`; canon output formatting is unchanged.
- Canon builder source defaults now use `canon_common.CACHE_DIR` instead of
  workstation/user temp paths.

### Path portability

- Rewrote `Tools/audit_story_fidelity.py` as a portable CLI with
  `--root` (default derived from `__file__`) and optional `--local`; all reads
  are UTF-8, and it no longer fails when the private dossier is absent.
- Replaced hard-coded `C:\dev\GX` roots in all eleven `Tools/story` migration
  scripts with `Path(__file__).resolve().parents[2] / ...`.

### Other validator hardening

- `Tools/puzzles/validate.py`: missing directories and non-object JSON roots
  are failures instead of tracebacks; `--report` handles a bare filename.
- `Tools/world/validate_layout.py`: malformed zones no longer prove containment.
- `Tools/canon/validate_canon.py`: Extra Deck bound aligned with the 15-card rules.

No game data, generated manifests, island assets, or Blender outputs were
regenerated or rewritten. `DuelAcademyIsland/Content/Data/Effects/card_effect_manifest.json`
was already modified before this work and was left untouched.

## Verification

Environment: Windows, Python 3.14.6, from `C:\dev\GX` unless noted. Unreal and
Blender were not launched. Generated reports were written to `%TEMP%`.

| Command | Result |
|---|---|
| `python -m compileall -q Tools DuelAcademyIsland/Content/Python` | exit 0 |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors, 15 warnings, 6 gaps, 304 info; 420 files read |
| `python Tools/validate/validate_all.py --strict` | **FAIL**, exit 1 (expected: warnings/gaps fail by design) |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 0 failures, 1 warning; `duelists=26 decks=32 ai=27 puzzles=100 questions=30 cycles=12` |
| `python Tools/opponents/import_canon_decks.py --check` | initially exit 1 (mapping gap); after the integration fix below: **PASS** — 32/32 runtime, 37/37 constructed, 32/32 roster/event references |
| `python -m unittest discover -s Tools/tests -v` | **37 tests, OK**, exit 0 (7 new in `test_python_pipeline.py`) |
| `python Tools/audit_story_fidelity.py` | exit 0; canon/runtime duel totals 39/39, 44 scenes, no missing scenes |
| `python Tools/world/validate_layout.py` | **PASS** — 20 existing, 6 merged, 0 missing, 10 needs_interior |
| `python Tools/economy/validate_decks.py` | **PASS** — 81 checks |
| `python Tools/economy/validate_packs.py` | **PASS** — 1,342 checks |
| `validate_all.py` and `puzzles/validate.py` launched from `%TEMP%` with absolute script paths | **PASS** in both cases |
| `git diff --check` | exit 0 (only Git's LF→CRLF advisory on Windows) |

The pre-fix `import_canon_decks.py --check` output was:

```text
PASS: 32/32 runtime opponent decks legal (full name/copy/year-1 audit)
PASS: 37/37 constructed decks legal under A04 static audit
FAIL: runtime deck files do not match mapping: missing=[], extra=['sheppard_year1']
FAIL: roster references unknown runtime deck 'sheppard_year1'
FAIL: story references unknown runtime deck 'sheppard_year1'
```

During integration the missing `DECK_MAP` entry was added; the check now passes
with `PASS: 32/32 runtime deck ids referenced by roster/events resolve`.

`git status` after verification showed only the intended Python/docs/test
changes plus pre-existing changes from other workstreams (`.github`, C++,
effects, integration). No validator-generated report or manifest in the
repository was modified by these runs.

## Follow-ups

1. **`sheppard_year1` mapping (fixed during integration).**
   The runtime deck **exists**:
   `DuelAcademyIsland/Content/Data/Opponents/decks/sheppard_year1.json`
   (48 main / 3 extra). It matches the canon record
   `DuelAcademyIsland/Content/Data/Canon/decks.json:5522`, was written by
   `Tools/story/complete_e33.py:26-28`, and is referenced by
   `Opponents/roster.json:3807-3820` and `Story/events.json:4246`.
   The importer's `DECK_MAP` (`Tools/opponents/import_canon_decks.py:45-211`)
   has 31 entries and ends at `zane_cyber_end`; it was not updated when the E33
   commit added the Sheppard file. `--check` builds `expected` from `DECK_MAP`
   (`:609`), sees the extra runtime file, then validates roster/story references
   against that same incomplete set (`:615-641`). The fix is a mapping entry
   such as `{"id": "sheppard_year1", "canon": "sheppard_year1", "opponent":
   "sheppard", ...}` (or routing `complete_e33.py` through the importer), not a
   new deck. Also correct `Docs/CodeReview/00-overview.md:40`, which currently
   says the runtime deck file is missing.
2. **Event/schedule file discovery (medium).** `validate_all` selects one event
   and one schedule file with `first_existing()`; if the data moves to
   `Story/events/*.json` or `Story/schedules/*.json`, only the first file is
   checked. Merge all candidate documents or require the root bundle.
3. **Shared JSON helpers (low).** Duplicate `load_json`/`write_json` helpers
   remain in `validate_all`, `canon_common`, `puzzles/validate`, economy and
   opponents. A cross-package module was not introduced because these scripts
   are launched standalone from different roots; `Tools/dai/jsonio.py` is the
   shared implementation for the Blender pipeline, and `canon_common` remains
   the canon-toolkit implementation.
4. **Remaining non-atomic writes (low).** `Tools/opponents/import_canon_decks.py`,
   `Tools/economy/sync_canon.py`, `Tools/puzzles/generate_puzzles.py` and
   `Tools/dai/credits.py` still write directly. Adopt the same temp+replace
   pattern if these generators become part of CI.
5. **Pending effects in content (policy).** `cross_check` only rejects
   `unsupported` cards; `pending` cards can still appear in decks/packs/puzzles.
   Decide whether that should be an error or a warning before the content gate.
6. **Schema subset gaps (low).** `schema_lite` still does not implement
   `format`, boolean draft-04 `exclusiveMinimum`/`exclusiveMaximum`, or
   `$ref`-to-external files. None are used by the current 20 schemas, but the
   README should say so.
7. **Reports are timestamped (info).** If reproducible report bytes matter, add
   a `SOURCE_DATE_EPOCH` or `--generated-at` override; the rest of the report
   ordering is deterministic.
8. **`Tools/puzzles/generate_exams.py` (low).** It executes on import and has no
   argparse/`main` guard; make it a `main()` CLI before adding it to automation.
