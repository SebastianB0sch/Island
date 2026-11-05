# 07 — Python asset pipeline & editor scripts (pass 3)

Branch: `refactor/code-review-pass`. The working tree already contained passes 1
and 2; this report describes only additions on top of that tree.

## Scope and constraints

Owned scope: `Tools/dai/**` (excluding vendored/`.blender_site` files),
`DuelAcademyIsland/Content/Python/**/*.py`, and
`Tools/tests/test_python_pipeline.py`. This workstream did not run Blender,
UnrealBuildTool, UnrealEditor, or any Unreal process; no assets, manifests,
`SourceAssets/` files or `Content/` files were regenerated. `Tools/build_island.py`
is outside the owned file set and was reverted after an exploratory change; the
required follow-up is listed in the cross-workstream section.

## Findings

| ID | Severity | Location | Finding | Status |
|---|---|---|---|---|
| P1 | High | `Tools/dai/blend.py:141`, `Tools/dai/character.py:174`, `Tools/dai/textures.py:75`, `Tools/dai/terrain.py:547`, `Tools/dai/layout.py:584`, `Tools/dai/thirdparty.py:91`, `Tools/dai/anime/models.py:275`, `anime/face.py:264`, `anime/outfit.py:667`, `anime/build.py:455` | FBX/PNG/JPG/heightmap/`.npy` writers wrote directly to their final path. An interrupted Blender run could truncate a previously good asset, and a failed export left a partial file that the Unreal importer could not distinguish from a finished one. | Fixed with `Tools/dai/atomic.py` (same-directory temp file, `os.replace`, cleanup on failure); all listed writers now use it. |
| P2 | High | `Tools/dai/anime/build.py:455` (was 380-390) | The cast stage deleted every generated `.fbx` and the entire `Textures/Characters` tree before exporting anything. A crash mid-stage therefore destroyed the previous cast asset set. | Fixed: no upfront deletion; individual writes are atomic, `cast.json` is written first, then only files owned by the previous `cast.json` and absent from the new one are pruned. |
| P3 | High | `DuelAcademyIsland/Content/Python/duel_academy/importer.py:530` (old sequence delete at former 503-506) | `import_cast` deleted the old `A_Anime_*` sequence before Interchange imported the replacement. A failed import lost the take entirely. | Fixed: existing animation is renamed to `*__DAOld` before import; on failure the new/partial asset is deleted and the backup restored. Abandoned backups whose original exists are cleaned up; a backup whose original is still missing is kept for manual recovery. |
| P4 | High | `importer.py:197` / `:407` / `:721` | `import_meshes`, `import_character` and `import_cast` had no preflight. A missing/stale manifest file caused a partial asset replacement (Unreal import is not transactional). | Fixed: all referenced source files and key manifest fields are validated before the first import task. Mesh/cast preflight failures raise; the character path keeps the previous `SK_Student` and logs. `build_island` now aborts before rebuilding the level when the imported mesh count is incomplete (`build.py:74`). |
| P5 | Medium | `importer.py:571` and `:666` | Removing a cast id from `cast.json` left its `SK_Anime_*` / `A_Anime_*` Unreal assets behind (pass-2 P21). | Fixed: the importer records the generated cast asset names in `Saved/DuelAcademy/cast_assets.json` and deletes only previously recorded names no longer in the new manifest. Missing/unreadable state is non-destructive; empty manifests never prune; Skeleton/PhysicsAsset helpers and non-cast names are protected. |
| P6 | Medium | `Tools/dai/thirdparty.py:91`, `Tools/dai/anime/models.py:171` | Meshopt/VRM cache entries were trusted based only on mtime. A truncated cache from an interrupted copy/decode was reused forever. Cache keys used `abspath` without case normalisation. | Fixed with `Tools/dai/cache.py`: path keys use `realpath` + `normcase`, cache hits require a non-empty file and a valid GLB header/JSON chunk, and copies/decodes publish atomically. |
| P7 | Medium | `Tools/dai/thirdparty.py:237`, `Tools/dai/anime/models.py:319` | Extracted third-party textures were skipped whenever the output path already existed, so changing a source material never refreshed the generated texture. The VRM base-texture cache was keyed only by the registry key, not the model path. | Fixed: output textures pass `use_cache=False` and are rewritten atomically; the VRM base texture cache key includes the source-path digest. |
| P8 | Medium | `DuelAcademyIsland/Content/Python/duel_academy/asset_paths.py`, used at `importer.py:153` | Manifest paths were joined with `os.path.join(source_dir, rel)`, so absent validation allowed absolute paths or `..` traversal outside `SourceAssets`. | Fixed with `duel_academy/asset_paths.py:source_path`, which rejects absolute, drive-relative and `..` paths and verifies the resolved path stays under `SourceAssets`. Used by meshes, character, cast and cast animations. |
| P9 | Medium | `DuelAcademyIsland/Content/Python/duel_academy/build.py:62` | `ScopedSlowTask.make_dialog(True)` created a modal progress dialog even on the headless CLI path (`interactive=False`), which can block `-unattended` runs. | Fixed: `make_dialog(bool(interactive))`. |
| P10 | Medium | `build_island_cli.py`, `rebuild_level_cli.py` | Failures were logged with plain `unreal.log`, and no error-level marker or exit signal was produced. | Fixed: failure paths use `unreal.log_error` and `raise SystemExit(1)`; success logs are explicit. See the remaining risk about Unreal's `-ExecutePythonScript` exit-code propagation. |
| P11 | Low | `Tools/dai/anime/models.py:75` | `_gltf_json()` read the JSON chunk without checking a short read and let `JSONDecodeError` escape; a corrupt model could crash an otherwise recoverable `alpha_modes()`/`read_vrm()` path. | Fixed: short reads/parse errors return `None`; cache validation catches the corruption instead. |
| P12 | Low | `Tools/dai/thirdparty.py:237` | A zero-byte cache file or directory at the output path was accepted as a cache hit. | Fixed: cache hits require a non-empty regular file. |
| P13 | Low | `Tools/build_island.py:33` | Unknown stage arguments are silently ignored (`python Tools/build_island.py layuot` runs the full default pipeline), there is no `--help`, and the script does not return a distinct exit code. | **Out of scope; not edited.** Exact required change in the cross-workstream section. |
| P14 | Info | `importer.py:275` | `cleanup_imported_materials()` still deletes every Material/MaterialInstanceConstant/Texture2D under `Meshes/` and `Characters/`; a user asset placed there would be removed. | Documented; pre-existing behaviour, not narrowed in this pass to avoid changing generated-asset ownership rules. |
| P15 | Info | `importer.py:56`, `:99` | Texture/audio imports are glob-driven; an Unreal import failure mid-batch can still leave a partly replaced texture/sound set. There is no manifest to preflight. | Documented. |
| P16 | Info | `Tools/dai/thirdparty.py:91` | `gltf-transform` is run without a timeout; a hung Node process can stall a headless asset build. | Documented. |

## Changes made

### New helpers

- `Tools/dai/atomic.py` — `atomic_path()` context manager plus `write_bytes`,
  `write_text`, `copy_file` and `save_image`. Temp files are created in the
  target directory with the target suffix preserved (so Pillow and Blender keep
  choosing the same format), fsynced where applicable, replaced with
  `os.replace`, and removed if the writer or replace fails.
- `Tools/dai/cache.py` — `source_key()` (12-char SHA-1 of `realpath` +
  `normcase`), `cache_file()`, `is_fresh()` (exists, non-empty, newer than
  source), `is_glb()` (magic/version/declared length/JSON chunk bounds) and
  `require_file()`.
- `DuelAcademyIsland/Content/Python/duel_academy/asset_paths.py` — stdlib-only
  path validation, cast ownership/state helpers and an atomic JSON writer for
  the non-committed `Saved/DuelAcademy/cast_assets.json` record. This is what
  makes the cleanup logic unit-testable without Unreal.

### Blender/asset writers (`Tools/dai`)

- `blend.py`: `export_fbx` and `render` write to an atomic temp path; FBX
  object selection is cleared in `finally`.
- `character.py`: `export_skeletal` (student mesh and all student animations,
  plus the anime cast FBX calls) uses the atomic path helper.
- `textures.py`: `save_gray`/`save_rgb` and the direct terrain-layer JPEG write
  use `atomic.save_image` while preserving `optimize`/`quality` arguments.
- `terrain.py`: heightmap, splat maps, colour map and all `.npy` caches use the
  helpers (`np.save` receives a temp path ending in `.npy`, so it does not
  append a second extension).
- `layout.py`: minimap is atomic; generated objects are deleted in `finally`
  when export fails.
- `assets/props.py`: prop/collision objects are deleted in `finally` after an
  export failure.
- `thirdparty.py`: meshopt decoding and image extraction are atomic; decoded
  cache validation uses `dai.cache`; missing model files raise a clear error.
- `anime/models.py`: VRM copy and recoloured textures are atomic; VRM and
  `vrm_tex` cache keys include the source path; corrupted glTF JSON is handled
  without an exception; base textures are refreshed into the output tree.
- `anime/face.py`, `anime/outfit.py`: face/garment/skin textures use
  `atomic.save_image` with the original optimize flags.
- `anime/build.py`: no destructive pre-clean; after the new `cast.json` is
  written, files referenced by the previous manifest but not the new one are
  removed. Partial (`only=`) builds skip pruning, and an unreadable previous
  manifest disables pruning instead of guessing.

### Unreal editor scripts

- `duel_academy/importer.py`:
  - manifest path resolution goes through `asset_paths.source_path`;
  - `import_meshes` preflights names, folders, duplicate names and every source
    file before the first import task;
  - `import_character` preflights the mesh and skips only missing animation takes;
  - `import_cast` validates manifest structure/files, then imports; animation
    replacement uses a rename backup with restore on failure;
  - cast ownership state and opt-out (`prune=False`) stale-asset cleanup;
  - abandoned `__DAOld` backups are only deleted when the replacement exists;
  - `_find_in` ignores rollback backups.
- `duel_academy/build.py`: `build_island(..., prune_cast=True)` additive keyword;
  non-modal slow task on headless builds; aborts before level rebuild when the
  mesh import count is incomplete.
- `build_island_cli.py` / `rebuild_level_cli.py`: explicit success/failure
  logging, `unreal.log_error` on failure and `SystemExit(1)`.

### API / serialization impact

- Generated JSON formats, field ordering and image/FBX bytes are unchanged.
  `atomic.save_image` forwards the same `optimize`/`quality` kwargs as before;
  new temp filenames are not embedded in the generated content.
- Additive keyword arguments: `models.materials(..., source=None)`,
  `thirdparty._save_image(..., use_cache=True)`, `import_cast(..., prune=True)`,
  `build_island(..., prune_cast=True)`.
- New non-committed state: `DuelAcademyIsland/Saved/DuelAcademy/cast_assets.json`
  (the `Saved/` tree is already ignored).
- Cache filenames change once (`decoded/`, `vrm/`, `vrm_tex/`), so old cache
  entries are ignored and regenerated on the next Blender run; generated output
  is unchanged.

## Verification

Environment: Windows, repo root `C:\dev\GX`. No Blender or Unreal process was
launched; no asset or data file was regenerated.

| Command | Result |
|---|---|
| `python -m compileall -q Tools DuelAcademyIsland/Content/Python` | exit 0, no output |
| `python -m unittest Tools.tests.test_python_pipeline -v` | **39 tests, OK** (19 pass-2 tests + 20 new) |
| `python -m unittest discover -s Tools/tests -q` | **123 tests, 2 failures** in the concurrently-added, out-of-scope `Tools/tests/test_canon_manifest.py` (`cards_manifest.json` / `exams.json` size and hash mismatch). The scoped suite above stays green; this workstream changed no canon data or manifest. |
| Read-only manifest preflight using `duel_academy.asset_paths` against `SourceAssets/Data` | `cast_files=58 cast_missing=0 expected_assets=58 manifest_entries=220 manifest_missing=0` |
| Scripted `importer._validate_cast_manifest` / `_manifest_problems` against the current manifests with a stub `unreal` module | `cast problems: []`; `mesh problems: 0` |
| Atomic PNG/NPY smoke test in a system temp directory | PNG read back as `(4, 3)` RGB; NPY read back as `[0, 1, 2]`; no temp files left |
| `git diff --check` on changed files | exit 0; only Git's LF→CRLF advisory |

New tests cover: atomic bytes/text/image replacement, failure rollback and temp
cleanup; cache keys, freshness, GLB validation and missing-source errors;
manifest path traversal/absolute-path rejection; cast expected/stale ownership,
case-only renames, empty-manifest safety, state round-trip and LF atomic state
write.

## Remaining risks and cross-workstream follow-ups

1. **Unreal import is still not transactional.** Preflight prevents the common
   missing/stale-manifest failure and cast animations have a rename rollback,
   but `import_meshes` still replaces assets batch by batch and skeletal meshes
   cannot be staged without a separate import root and reference remap. If the
   engine fails mid-batch, previously imported assets remain, and the build now
   aborts before rebuilding the level when the mesh count is incomplete.
2. **Level save is not atomic.** `level.save_current_level()` writes the `.umap`
   through the editor API; there is no safe same-directory replacement for map
   saves. The build saves only at the end, so a failed build normally leaves the
   previous `.umap` on disk.
3. **Cast pruning bootstrap.** On the first run after upgrading, no ownership
   record exists, so pre-existing stale cast assets are not deleted; the record
   is created then and subsequent manifest shrink prunes correctly. Clearing
   `Saved/` pauses pruning until the next import recreates the record.
4. **Anime stage is not fully staged.** Individual files are atomic and old
   manifest-owned files are pruned only after the new `cast.json` is written,
   but a failure partway through a multi-member export leaves a mix of new and
   old FBX files until the stage is rerun. `only=` builds skip pruning.
5. **Texture cleanup is manifest-based.** Stale cast textures referenced by the
   previous `cast.json` are removed; orphan textures from pre-manifest builds
   remain until removed manually. Third-party texture outputs are always
   refreshed but old unreferenced files are not pruned.
6. **`cleanup_imported_materials()` is broad.** It still deletes all
   Material/MaterialInstanceConstant/Texture2D assets under `Meshes/` and
   `Characters/`, including any user asset placed there. Narrowing it needs an
   ownership marker for imported materials, which was outside this pass.
7. **Texture/audio imports remain glob-driven.** A missing source file cannot be
   preflighted from a manifest; an engine failure mid-batch can leave a partial
   set, though the next run replaces it.
8. **`gltf-transform` has no timeout.** A wedged Node process can still stall a
   headless Blender build; adding `subprocess.run(timeout=...)` is a small
   follow-up. The cache is now validated so a killed decode cannot be reused.
9. **Blender/Unreal integration was not runtime-tested.** The FBX/PNG atomic
   path keeps the target suffix, but a real Blender export and editor import
   should be run by the parent before shipping a regenerated asset set.
10. **Cross-workstream (parent/08): `Tools/build_island.py` CLI hardening.**
    This file is outside workstream 07's owned set, so the exploratory change
    was reverted. Required change: add a `parse_stages(argv)` that rejects
    unknown stage names (exit 2), handles `--help`/`-h` without importing
    `numpy`/`dai`, preserves the current default (`all stages except render`,
    `--render` adds render, `all` selects everything), and make the entry point
    `raise SystemExit(main(sys.argv[1:]))` with `main` returning 0. Current
    behaviour silently ignores a typo and runs the full pipeline.
11. **Cross-workstream (parent/CI): the headless CLIs cannot reliably set the
    Unreal process exit code.** They now log `[DuelAcademy] headless build
    FAILED` / `... succeeded` at error/log level and raise `SystemExit(1)`.
    The parent's headless harness should treat the failure marker or a reported
    Python exception as failure; the process exit code is owned by Unreal.
12. **`Tools/dai/jsonio.py` keeps its own atomic JSON writer.** It was correct
    in pass 2 and has its own tests; the new `atomic.write_text` helper is used
    by new call sites rather than refactoring the tested JSON writer in this
    pass.

No data, manifest, committed asset, C++ or out-of-scope tool file was changed.

## Parent integration follow-up

`Tools/build_island.py` was hardened during integration as requested: unknown
stage names/options now exit 2, `--help` exits without importing NumPy/dai,
stage order is normalized, and three parser tests were added. The final Python
suite is 126 tests on both 3.14 and 3.12. No Blender or Unreal asset build was
run, so the binary-import transactionality risks above remain open.
