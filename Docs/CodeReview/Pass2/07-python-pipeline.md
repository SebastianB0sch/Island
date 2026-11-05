# 07 — Python asset pipeline & editor scripts

Branch: `refactor/code-review-pass` (working tree includes the completed first pass;
this report only describes additions on top of it).

Scope: `Tools/dai/**` (Blender/asset generator: geometry, textures, materials,
layout, anime cast, credits), `DuelAcademyIsland/Content/Python/**` (Unreal editor
scripts), the remaining generator writers in `Tools/economy`,
`Tools/opponents` and `Tools/puzzles/generate_exams.py` /
`generate_puzzles.py`, and `Tools/tests/test_python_pipeline.py`. No C++, game
data, generated assets, `Tools/effects` or `Tools/integration` files were
changed. Blender and Unreal were not launched.

## Summary

The first pass covered the validators and the file-writing paths of the main
JSON stages. This pass audited the Blender/asset generator and the Unreal
editor path, then finished the deferred atomic-write/CLI work. The important
fixes are small and leave generated output unchanged:

- An odd ring count passed to `MeshBuilder.sphere()` made the full sphere
  sample a negative-radius profile row. The anime jacket button (`body.py`)
  uses `rings=5`; it now gets a valid sphere.
- `outfit.fix_skin()`'s "do not paint outside the body island" mask was a
  tautology, so the three-pixel dilation was ignored and recolouring could
  touch unrelated atlas texels.
- `rebuild_level_cli.py` rebuilt the level with `interactive=True`, so the
  headless `-ExecutePythonScript` path could stop at an editor dialog.
- `models.add_outline()` could dereference a missing outline material, and the
  glTF header reader had no short-read/chunk-size guard.
- The meshopt/VRM cache keys used only the source basename; two packs shipping
  `tree.glb` could silently share a decoded cache file. Cache keys now include
  a stable path digest.
- A lake surface with no selected cells produced a 1-D empty face array and
  crashed on `faces.shape[1]`; it now produces an empty but valid mesh.
- The last non-atomic writers in economy/opponents/puzzles, plus `credits.py`
  and the generated WAV writer, now use same-directory temp files and
  `os.replace` while preserving their previous JSON formatting.
- `generate_exams.py` no longer runs at import time; it has a `main()` guard,
  context-managed reads, a pure `build_cycles()` and an atomic writer.

The generated values, JSON field ordering and serialized formats are
unchanged. JSON now consistently uses LF (matching the index and the first
pass's report writer; on Windows the previous text mode emitted CRLF in the
working tree). `exams.json` content was compared against a freshly built
document without writing it.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| P1 | High | `Tools/dai/geo.py:171` | `sphere(rings=…)` with an odd ring count computes `lo = -rings//2` and walks one row past the south pole with negative radius. `body.py:170` uses `rings=5`, producing a malformed button sphere. | Fixed: round full-sphere ring counts up to even. |
| P2 | High | `Tools/dai/anime/outfit.py:816-818` | `region = dilation(region) & ~(mask & ~region)` simplifies to `region`, so the dilation had no effect and painted texels outside the body island. | Fixed: intersect the dilation with `mask`. |
| P3 | High | `DuelAcademyIsland/Content/Python/rebuild_level_cli.py:7` | `rebuild_level()` called `build_island()` with the default `interactive=True`; the headless CLI could open a modal dialog and hang automation. | Fixed: `interactive` parameter and CLI passes `False`. |
| P4 | High | `Tools/dai/anime/models.py:404-445` | `add_outline()` assumed `K.OUTLINE_MAT` already exists; `bpy.data.materials.get()` returning `None` crashed on `mat.name` when used outside `build_model()`. | Fixed: create/fallback through `preview_material()`. |
| P5 | Medium | `Tools/dai/terrain_mesh.py:157` | An empty lake face list became a 1-D `np.array`, so `_mesh_from_arrays()` failed indexing `faces.shape[1]` (and `remap` was not exercised). | Fixed: reshape empty input to `(0, 4)`. |
| P6 | Medium | `Tools/dai/thirdparty.py:92-101`, `Tools/dai/anime/models.py:167-175` | Decoded-meshopt and converted-VRM caches keyed only by basename. Two packs with the same filename shared one cache entry; the second model could be imported from the wrong file. | Fixed: append a SHA-1 digest of the absolute source path. Old cache entries are simply ignored. |
| P7 | Medium | `Tools/dai/credits.py:61-89` | `usage()` depended on a global list populated only by `write()`; calling it standalone returned no usage. `write()` also wrote CREDITS.md non-atomically. | Fixed: explicit `folders` argument and atomic write. |
| P8 | Medium | `Tools/puzzles/generate_exams.py:8-50` | The script executed at import time, writing `exams.json`, and leaked open file handles through `json.load(open(...))`. | Fixed: pure `build_cycles()`, `main()`, context managers, atomic writer. |
| P9 | Medium | `Tools/economy/sync_canon.py:61`, `Tools/opponents/import_canon_decks.py:252/710`, `Tools/puzzles/generate_puzzles.py:446`, `Tools/dai/audio.py:19` | Remaining writers used direct `open(..., "w")`, so a crash could leave a truncated JSON/deck/report/WAV. | Fixed: same-directory temp file + `os.replace`; formatting is byte-for-byte comparable. |
| P10 | Medium | `DuelAcademyIsland/Content/Python/duel_academy/level.py:557` | `open_or_create_map()` ignored a failed `load_level()` and then cleared generated actors on whatever map was open. | Fixed: raise on `False`. |
| P11 | Medium | `DuelAcademyIsland/Content/Python/duel_academy/importer.py:258` | `find_asset_data()` / asset-class lookup was not guarded; a missing/stale registry entry aborted cleanup. `import_cast()` used `next(iter(members))` and could raise `StopIteration` for an empty skeleton group. | Fixed: guard lookup, skip empty groups with a warning. |
| P12 | Medium | `DuelAcademyIsland/Content/Python/duel_academy/materials.py:505-537` | Terrain material tiling hard-coded a 3072 m world; `n_out`/`r_out` were only initialized inside the first loop iteration. | Fixed: read `layout.json`'s world size with a fallback; initialize outputs before the loop. |
| P13 | Low | `Tools/dai/anime/models.py:75-83` | `_gltf_json()` assumed a full 20-byte header and accepted any chunk length. | Fixed: short-read and 64 MiB sanity guard. |
| P14 | Low | `Tools/dai/anime/build.py:478-486` | `render_lineup()` indexed `registry()["anime"][key]` directly; a checkout without that optional source crashed instead of rendering the rest pose. | Fixed: `.get()` fallback with a log line. |
| P15 | Low | `Tools/dai/textures.py:335` | The texture-count log omitted the three neutral/default textures. | Fixed: log count matches the files written. |
| P16 | Low | `Tools/dai/layout.py:24/397/582` | Unused imports/variables (`AssetSet`, `Terrain`, `h_all`); minimap failure had no actionable message. | Fixed/cleaned; minimap now raises a clear "run textures/terrain first" error. |
| P17 | Info | `Tools/dai/layout.py:182-221` | `_place_interior_sockets()` only handles light/text/interact/audio/emitter; prop/floating/npc sockets in an interior would be silently dropped. No current `interiors.py` builder emits them. | Documented; not changed (no current data affected). |
| P18 | Info | `Tools/dai/anime/cast.py:384-409` | Named NPC assignment consumes `used` markers before counting `nth`, so named characters can skip one matching marker when several share a group/dorm. It is deterministic and every named character still gets a distinct marker. | Documented; not changed to avoid reshuffling NPC placement. |
| P19 | Info | `Tools/dai/assets/features.py:159`, `Tools/dai/terrain.py:475` | Dead expressions (`-(0.0 if … else 0.0)`, lake-rock term multiplied by 0.0) are harmless but obscure intent. | Documented. |
| P20 | Info | `DuelAcademyIsland/Content/Python/duel_academy/menu.py:13-35` | Menu registration is not idempotent across module reloads; a reload can add a second submenu. | Documented; not changed. |
| P21 | Info | `DuelAcademyIsland/Content/Python/duel_academy/importer.py:463-548` | Stale cast meshes/animations from removed cast entries are not pruned; only the assets that are still listed are replaced. | Documented. |

## Changes

### Blender/asset generator (`Tools/dai`)

- `geo.py`: normalize odd full-sphere ring counts; hemispheres are unchanged.
- `terrain_mesh.py`: empty lake face array handling; removed unused import.
- `anime/outfit.py`: corrected `fix_skin()` dilation mask.
- `anime/models.py`: cache keys include a path digest; clear armature/skinned
  mesh errors; glTF header guard; outline material guard; small set reuse.
- `anime/build.py`: safer preview material texture variable and optional
  animation-source fallback; named-NPC log no longer assumes every entry has a
  `cast` key.
- `thirdparty.py`: meshopt cache key includes the source path digest.
- `credits.py`: `usage()` takes an explicit folder list and the markdown write
  is atomic.
- `audio.py`: WAV writes are atomic.
- `layout.py`: removed unused imports/locals and added an actionable minimap
  error.
- `textures.py`: corrected the texture-count log.

### Unreal editor scripts (`DuelAcademyIsland/Content/Python`)

- `duel_academy/build.py` / `rebuild_level_cli.py`: headless rebuild is
  non-interactive.
- `duel_academy/level.py`: fail instead of clearing actors after a failed level
  load; removed unused import.
- `duel_academy/importer.py`: guarded asset-registry cleanup and empty cast
  groups.
- `duel_academy/materials.py`: terrain tiling follows `layout.json` world size;
  terrain layer output names initialized before the loop.

### Generators and tests

- `Tools/economy/sync_canon.py`, `Tools/opponents/import_canon_decks.py`,
  `Tools/puzzles/generate_puzzles.py`: atomic JSON/report writers preserving
  the existing `indent=2` / `ensure_ascii` choices and trailing newline.
- `Tools/puzzles/generate_exams.py`: no import-time work, `build_cycles()`,
  `--root`, atomic write and a `main()` entry point.
- `Tools/tests/test_python_pipeline.py`: 11 new tests (19 total in this file)
  covering atomic write/rollback, LF/UTF-8 bytes, temp-file cleanup, path
  anchors for the generator roots, deterministic exam cycles, invalid
  rotation rejection and byte-compatible generator writers.

No data, manifest or asset file was regenerated or written during this work.

## Verification

Environment: Windows, Python 3.14.6, repo root `C:\dev\GX`. Blender and Unreal
were not launched; no source assets were rebuilt.

| Command | Result |
|---|---|
| `python -m compileall -q Tools DuelAcademyIsland/Content/Python` | exit 0 |
| `python -m unittest Tools.tests.test_python_pipeline -v` | **19 tests, OK** |
| `python -m unittest discover -s Tools/tests -v` | **70 tests, OK**, exit 0 (includes this file's 19 tests) |
| `python Tools/opponents/import_canon_decks.py --check` | **PASS** — 32/32 runtime decks, 37/37 constructed decks, 32/32 roster/story references |
| `python Tools/puzzles/validate.py` | **PASS** — 145 checks, 0 failures, 1 warning; `duelists=26 decks=32 ai=27 puzzles=100 questions=30 cycles=12` |
| `python Tools/economy/validate_decks.py` | **PASS** — 81 checks |
| `python Tools/economy/validate_packs.py` | **PASS** — 1,342 checks |
| `python Tools/validate/validate_all.py` | **PASS** — 0 errors, 15 warnings, 6 gaps, 304 info; 420 files read |
| `git diff --check` on changed files | exit 0 (only Git's LF→CRLF advisory) |

The `exams.json` compatibility check loaded `questions.json` and
`practicals.json`, built the same document with the new `build_cycles()`, and
compared the JSON text with the committed file: no content differences, only
the expected working-tree CRLF vs generator LF line endings.

## Remaining risks / follow-ups

1. **Asset builds are not transactional.** FBX/PNG/JPG/heightfield outputs are
   still written straight to `DuelAcademyIsland/SourceAssets`; an interrupted
   Blender run can leave a partial asset set. The JSON manifests are atomic, but
   binary outputs need either per-stage temp directories or a rebuild-from-
   scratch policy before they are put in CI. (Out of scope for a small fix.)
2. **Unreal import is not rollback-safe.** `import_meshes`/`import_cast`
   replace assets one at a time; a failure midway leaves the previous asset set
   partly updated. The editor build is already designed to be rerunnable.
3. **Cast cleanup is additive.** Removing a cast id from `cast.json` does not
   delete its previously imported `SK_Anime_*` mesh or animation sequences.
4. **Interior socket coverage.** `_place_interior_sockets()` handles the socket
   types the current `interiors.py` emits. If an interior builder later adds
   `prop`, `floating` or `npc` sockets, the layout will silently ignore them;
   extend the method then.
5. **NPC assignment semantics.** `cast.assign_npcs()`'s `nth` index counts
   *unused* matching markers, not the full marker list. Changing it would move
   existing named NPCs; leave it unless placement is being re-authored.
6. **Blender-only bugs cannot be unit-tested here.** The sphere/outline/skin
   fixes are covered by code inspection and compileall, not by a headless
   Blender render. A Blender smoke run (`build_island.py cast layout`) is the
   right verification before shipping a regenerated asset set.
7. **C++ follow-up:** none required. The editor-script changes are confined to
   Python and use existing native-class properties.
