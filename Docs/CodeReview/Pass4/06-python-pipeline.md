# Pass 4 — WS-06: Python asset pipeline

Branch `refactor/code-review-pass`, checkpoint `77cc9c7`. Scope honoured exactly
as assigned: `Tools/dai/**` (excluding the vendored `Tools/.blender_site`, which
was never touched), `Tools/build_island.py`, `Tools/build_island_blender.py`,
`DuelAcademyIsland/Content/Python/**`, and tests in `Tools/tests/`
(`test_python_pipeline.py` extended). No git commands were run; no Unreal /
Blender processes were started. Findings for other workstreams' files were read
only to verify contracts (e.g. `importer.py`'s `_prune_stale_cast` contract for
T1 — not edited, which is correct: T1 fixes the Blender-side manifest, the
importer side stays ownership-based as previously designed).

## Findings

| id | severity | where | status |
|----|----------|-------|--------|
| T1 | HIGH | `Tools/dai/anime/build.py` (publish step), new `Tools/dai/anime/manifest.py` | **fixed** |
| T2 | HIGH | `duel_academy/level.py` (`save`), `duel_academy/build.py` (`build_island`) | **fixed** |
| T3 | HIGH | `Tools/dai/thirdparty.py` (`_decode_meshopt`) | **fixed** |
| T4 | MED | `Tools/dai/thirdparty.py` (`_save_image`), `Tools/dai/anime/models.py` (`materials`) | **fixed** |
| T7 | MED | `Tools/dai/terrain.py`, `Tools/dai/cache.py`, `Tools/build_island.py` | **fixed** |
| T6 | MED | new `Tools/dai/anime/vrm.py`, `Tools/dai/anime/models.py` | **fixed** |
| T8 | LOW | `duel_academy/common.py` (`set_props`), strict opt-ins in `level.py` / `importer.py` | **fixed** |
| T11 | LOW | `models.py`, `textures.py`, `layout.py`, `outfit.py` | **fixed** |
| T12 | LOW | `Tools/dai/jsonio.py`, `Tools/dai/credits.py`, `Tools/dai/audio.py`, `duel_academy/asset_paths.py` | **fixed** |
| T13 | LOW | `Tools/dai/thirdparty.py` (`GLTF_TRANSFORM_CANDIDATES`) | **fixed** |
| T10 | LOW | new constants in `duel_academy/common.py`; consumers `importer.py`, `materials.py` | **fixed** |
| T14 | LOW | `Tools/build_island.py` (`missing_stage_inputs`, stage loop) | **fixed** |
| T5 | MED | engine-side mesh batch rollback | deferred (per brief, engine-side) |
| T9 | MED | importer category purge opt-out | deferred (per brief) |

## Changes and rationale

### T1 — partial cast builds must not shrink the manifest (HIGH)

* `build(only=...)` used to publish a subset manifest (`meshes`/`groups`/
  `materials` covering only the rebuilt members). The importer
  (`_prune_stale_cast`) treats cast.json as the whole inventory after the first
  ownership bootstrap, so the next `import_cast` deleted every `SK_Anime_*` /
  `A_Anime_*` asset missing from the subset — the docstring claim that partial
  builds "keep the rest of the cast" was not true end-to-end.
* New stdlib-only module `Tools/dai/anime/manifest.py` with the pure function
  `merge_partial_manifests(previous, subset)`: rebuilt `groups` / `meshes` /
  `materials` entries replace their previous ones by key; everything untouched
  keeps its previous entry (partial builds neither re-export nor prune, so the
  previous files still exactly match those entries). Extra top-level keys come
  from the subset with the previous document as fallback. Inputs are never
  mutated; the subset is returned unchanged when no previous manifest is
  usable (first partial build on an empty project) and a `TypeError` is raised
  for a non-object subset.
* `build()` now publishes the merged document for partial builds and the
  rebuilt document for full builds (full builds keep the old semantics incl.
  stale-file pruning). A partial build refuses to publish when the previous
  cast.json existed but is unreadable (fail-closed — that subset would again
  describe less of the cast than the importer expects) and logs a warning when
  no previous manifest exists at all. Stale-file pruning stays skipped for
  partial builds; the affected docstrings now say *why* instead of asserting
  the previously false claim.
* G1 unittest: the subset build leaves the full set represented, rebuilt
  entries win, untouched entries (and their materials) survive byte-identical.

### T2 — level save results are checked (HIGH)

* `level.save()` raises `RuntimeError("map save failed ...")` unless
  `LevelEditorSubsystem.save_current_level()` returns true.
* `duel_academy/build.py` checks both `EditorAssetLibrary.save_directory`
  results (after the cast import, and after the level save) the same way. The
  CLI path already maps exceptions / a False return to
  `unreal.log_error` + `SystemExit(1)`, so a failed save now ends the headless
  build loudly instead of reporting success with unsaved actors.

### T3 — gltf-transform timeout (HIGH)

* `_decode_meshopt` calls `subprocess.run(..., timeout=GLTF_TRANSFORM_TIMEOUT)`
  (120 s) and catches `subprocess.SubprocessError` (covers
  `CalledProcessError` *and* `TimeoutExpired`). Every failed attempt is
  recorded as `"<tool> (<elapsed>.1f s): <exception>"` and the final
  `RuntimeError` lists them, so a hang surfaces as a failure with the elapsed
  attempt instead of stalling the build forever.

### T4 — vrm_tex cache freshness (MED)

* `thirdparty._save_image` gained `fresh_against`: an existing cache entry is
  reused only while `cache.is_fresh(path, source)` holds (size + mtime), the
  same contract the VRM copy cache already uses. `models.materials()` passes
  the registered model file, so replacing a VRM in place regenerates the
  extracted base textures instead of silently keeping stale ones. The
  `vrm_tex` source-path keying (added in pass 3) stays.

### T7 — terrain cache stamping (MED)

* Reads of `Tools/.cache/*.npy` trusted existence only; after
  FIELD_RES/WORLD_SIZE changes or a partial run, layout happily mixed
  mismatched resolutions into a finished-looking layout.json.
* `save_outputs` now writes a `terrain_cache.json` stamp **last**
  (`{"field_res", "world_size"}` via `jsonio`); `terrain.check_cache()`
  (`require_stamp` in `Tools/dai/cache.py`) refuses (`StampedCacheError`) when
  the stamp is missing (pre-existing cache runs!), was written with a
  different `field_res` / `world_size`, or lists an empty/missing required
  file. `load_cached()` / `load_extra()` check their own required files, and
  the `meshes` stage checks `height.npy` before `np.load`.
* `build_island.main` turns `StampedCacheError` into exit 2 with the fix
  command on stderr ("run python Tools/build_island.py terrain").
* Integration consequence: on the current checkout `Tools/.cache` holds caches
  written before stamps existed, so the first post-integration `layout` /
  `meshes` run will refuse and the terrain stage must run once to re-stamp.
  This is the fail-closed behaviour the finding asked for.

### T6 — VRM parsing shape validation (MED)

* The three glTF JSON lookups (`_gltf_json`, `alpha_modes`, `read_vrm`,
  `target_names`) moved to stdlib-only `Tools/dai/anime/vrm.py` (the same
  test-in-the-dark pattern as `duel_academy/asset_paths.py`) and validate every
  level: nodes / materials / extensions / humanoid maps are type-checked,
  node indices must be in-bounds integers (bools refused), targetNames must be
  a non-empty list of strings. A corrupt GLB now returns safe empties instead
  of `KeyError`/`IndexError`/`TypeError`/`AttributeError`.
* `models.py` re-exports the three lookups so `hairdo.M.alpha_modes(path)` and
  friends keep working unchanged.

### T8 — `set_props` strict opt-in (LOW)

* `common.set_props(obj, strict=False, **kwargs)` re-raises (after logging)
  when a property could not be set. Default behaviour of every existing call
  site is unchanged ("do not flip every call site").
* Strict is opted into where a silently-kept default yields a broken
  gameplay actor: the `DAIslandManager` wiring in `level.manager()` (sun /
  moon / skylight / fog / map texture / lake + map bounds, both call sites)
  and the static-mesh FBX import options in `importer._fbx_options`
  (`convert_scene_unit` + collider flags — the same options whose silent
  failure produced 100× too small meshes).
* Note: `materials.py` contains no `set_props` call sites (its `Graph` helper
  has its own per-expression failure logging, which is correct for material
  parameters — a single broken expression node should log, not abort the whole
  graph). No change there.

### T11 — Pillow handles closed (LOW)

* All open-then-convert sites now use `with Image.open(...)`:
  `models._recolor`, `models.materials` (cache copy refresh), `models._alpha_lookup`,
  `textures._load_img` and the procedural-fallback layer loads,
  `layout.minimap`, plus the same pattern in `outfit.fix_skin` (same class of
  leak in an owned file). Behaviour identical; no more leaked file handles.

### T12 — atomic+fsync writers (LOW)

* `jsonio.write_json` now routes through `dai.atomic.write_text` (same-directory
  temp, `os.replace`, fsync; UTF-8 / LF unchanged — existing byte-format tests
  still pass).
* `credits.write` routes through `atomic.write_text` with the decided explicit
  LF newline policy (matches jsonio/atomic; generated MD must be stable across
  machines).
* `audio._write` builds the WAV via `atomic.atomic_path` and fsyncs the temp
  file (write-mode handle — Windows `FlushFileBuffers` refuses read-only
  fds) before publishing; partial WAVs can no longer reach SourceAssets/Audio.
* `duel_academy/asset_paths.write_json_atomic` keeps its "stdlib-only, no cross-
  tree imports" module contract (documented at the top of the file), so instead
  of importing `Tools/dai/atomic.py` it inlines the identical dance:
  flush + `os.fsync` before `os.replace`. Bytes and rollback behaviour are the
  same as dai.atomic.write_text produces; flagged here for transparency since
  the finding text asked for routing through dai.atomic.

### T13 — portable gltf-transform discovery (LOW)

* The hardcoded `/home/user/tools-node/...` candidate is gone;
  `GLTF_TRANSFORM_CANDIDATES` is `[env GLTF_TRANSFORM, shutil.which(...)]`.
  The used tool is logged on success ("decoding <file> with <tool>").

### T10 — centralized editor-side constants (LOW)

* `duel_academy/common.py` now owns `REF_SPEED = {"Walk": 300.0, "Run": 600.0}`
  (comment cross-references `UDAAvatarComponent`) and
  `WORLD_SIZE_M = 3072.0` (cross-references `Tools/dai/config.py WORLD_SIZE`).
  `importer.py` consumes `C.REF_SPEED` (its local duplicate is removed);
  `materials.py` consumes `C.WORLD_SIZE_M` as the `layout.json` fallback.
  The two trees cannot import each other's packages (editor vs Tools), which
  is why the centralization is one module on each side, each cross-commented.

### T14 — stage dependency guard (LOW)

* `build_island.main` computes `missing_stage_inputs(stages)` with stdlib-only
  imports, *before* Blender is imported, and exits 2 with the CLI error-code
  contract (`Tools/tests/test_cli_error_codes.py` style): one line per missing
  input and a fix hint ("run the terrain stage first … python Tools/build_island.py
  terrain layout …"). A stage whose producer is part of the same run (stages
  always run in pipeline order) imposes no requirement, so `terrain layout`,
  `all`, or plain invocations keep working.
* Stage guards: `meshes` ← `height.npy` + stamp, `layout` ← the six terrain
  cache files + stamp, `render` ← `layout.json` (layout),
  `terrain_layers.json` (textures), `height.npy` + stamp (terrain).

## New tests (`Tools/tests/test_python_pipeline.py`, 39 → 65 test methods)

* G1 `MergePartialManifestTests` — subset build keeps the full cast
  represented; rebuilt entries win; untouched entries byte-identical;
  unusable/untyped inputs behave as specified; no input mutation.
* G4 `AudioWriterTests` — WAV header (mono / 16-bit / SR / loop length ==
  `int(SR*dur)`) and writer-failure rollback (previous file kept, no temp).
* G5 `StageDependencyTests` — out-of-order stage selection exits 2 with
  "run the terrain stage first"; producer-in-run suppresses requirements;
  standalone stages impose none.
* T7 `StampedCacheTests` — missing / mismatched / partial / unreadable stamps
  raise `cache.StampedCacheError` with the fix command; a matching stamp passes
  and is returned.
* T3/T13 `ThirdpartyToolTests` — candidate list is env-first + PATH only; the
  decode path passes `timeout=GLTF_TRANSFORM_TIMEOUT` (stubbed
  `subprocess.run`), converts `TimeoutExpired` into the final RuntimeError
  naming tool + elapsed seconds; a successful decode publishes a valid GLB into
  the cache and logs which tool ran.
* T4 (same class) — `_save_image` reuses only cache entries not older than the
  source and keeps fresh entries untouched.
* T6 `VrmParseTests` — valid VRM 0.x/1.0 maps; `_BlendMode` overrides; corrupt
  manifests / GLB bytes / out-of-range node ids / malformed targetNames return
  safe empties instead of raising.

Blender-dependent modules are imported with stub `bpy` / `bmesh` /
`mathutils` modules in the test helper (`_install_blender_stubs`), only when no
real bpy wheel is importable, so the same tests stay valid on a Blender python.

## Verification (commands and exit statuses)

```
python -m unittest discover -s Tools/tests          # checkpoint state: Ran 126 tests, OK, exit 0
python -m unittest Tools.tests.test_python_pipeline # after: Ran 65 tests in 0.139s, OK, exit 0 (+26 methods)
python -m unittest discover -s Tools/tests -p test_cli_error_codes.py  # Ran 12 tests, OK, exit 0
python -m py_compile <23 touched/new files>         # exit 0
python Tools/build_island.py --help                 # exit 0 (doc; still does not import the pipeline)
python Tools/build_island.py layuot                 # exit 2, "unknown stage/option"
python Tools/build_island.py layout                 # exit 2, "the layout stage needs ...\terrain_cache.json
                                                    #  (built by the terrain stage)" + "run the terrain stage first"
                                                    #  (significant: legacy stampless Tools/.cache on this machine)
```

Full-suite status at report time:
`python -m unittest discover -s Tools/tests` → `Ran 186 tests in 11.1s, OK, exit 0`
(the 65 of this workstream's file included). During the pass, that suite
transiently showed 6 non-passes in `Tools/tests.test_data_tooling_ci` — WS-07's
concurrently edited module (`Tools/canon/fetch_guides.py` missing `import sys`,
schema_lite NULL-subschema, sync_canon fixtures). They failed identically when
run standalone with none of WS-06's modules imported, so they were independent
of this workstream's edits, and they are now green again. No WS-06 regressions.

## Remaining risks / notes for the parent

* One-time cost of T7: machines with pre-stamp `Tools/.cache` (this checkout)
  need a single `python Tools/build_island.py terrain` re-run before
  `layout` / `meshes` / `render` work again; the error message says so.
* T8 strict call sites are conservative (manager wiring, FBX unit/collider
  import options). The finding's "materials.py" has no `set_props` call sites;
  if more strict opt-ins are wanted (e.g. `level.zones()` / `interactables()`
  gameplay props), the keyword is ready — deliberately not flipped per scope.
* T12 in `asset_paths.py` inlines the fsync instead of importing `dai.atomic`
  to preserve that module's stdlib-only contract (useful: it keeps matching
  behaviour even if the repo layout moves).
* Deferred per brief: T5 (engine-side mesh batch rollback), T9 (purge
  opt-out) — untouched.
* Engine-side partners not touched by this workstream: `UDAAvatarComponent`
  walk/run speeds must continue to match `duel_academy/common.REF_SPEED`
  (now the single editor-side reference) and `DAIslandManager` props are now
  a hard failure if the C++ property names change — the same names are
  unchanged, so no visible engine diff is needed.
