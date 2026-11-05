"""Pure manifest-path and cast-ownership helpers for the editor import scripts.

This module deliberately imports only the standard library so the rules can be
unit-tested on a machine without Unreal.  ``importer.py`` supplies the engine
asset-library calls; everything that decides *what* is safe lives here.
"""

from __future__ import annotations

import json
import ntpath
import os
import tempfile

CAST_STATE_VERSION = 1
CAST_MESH_PREFIX = "SK_Anime_"
CAST_ANIM_PREFIX = "A_Anime_"
# Importing a skeletal mesh also generates a Skeleton / PhysicsAsset next to it.
# They are not listed in cast.json but belong to the meshes, so never prune them
# by name alone.
CAST_PROTECTED_SUFFIXES = ("_Skeleton", "_PhysicsAsset")


def source_path(root: str | os.PathLike[str], rel) -> str:
    """Resolve a manifest path relative to ``root`` without allowing traversal.

    Generated manifests use project-relative, forward-slash paths.  Absolute
    paths, drive-relative paths (``C:foo``) and any ``..`` component are
    rejected rather than silently importing a file outside ``SourceAssets``.
    """
    if not isinstance(rel, str) or not rel.strip():
        raise ValueError("empty source path")
    normalised = rel.replace("\\", "/")
    drive, _ = ntpath.splitdrive(normalised)
    if drive or os.path.isabs(normalised) or normalised.startswith("/"):
        raise ValueError(f"absolute source path is not allowed: {rel!r}")
    parts = [part for part in normalised.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise ValueError(f"source path escapes the asset root: {rel!r}")
    root_real = os.path.realpath(os.fspath(root))
    path = os.path.realpath(os.path.join(root_real, *parts))
    try:
        common = os.path.commonpath((root_real, path))
    except ValueError:
        common = ""
    if common != root_real:
        raise ValueError(f"source path escapes the asset root: {rel!r}")
    return path


def missing_sources(root: str | os.PathLike[str], rels) -> list[tuple[str, str]]:
    """Return ``(manifest_path, reason)`` for invalid or missing source files."""
    problems = []
    for rel in rels:
        try:
            path = source_path(root, rel)
        except ValueError as exc:
            problems.append((str(rel), str(exc)))
            continue
        if not os.path.isfile(path):
            problems.append((str(rel), f"file not found: {path}"))
    return problems


def asset_name(path: str) -> str:
    """Asset name from a package path (``/Game/Dir/SK_Foo.SK_Foo`` -> ``SK_Foo``)."""
    leaf = str(path).replace("\\", "/").rsplit("/", 1)[-1]
    return leaf.split(".", 1)[0]


def is_cast_owned(name: str) -> bool:
    """True for assets the cast importer creates (and that are safe to prune)."""
    name = asset_name(name)
    lower = name.casefold()
    if lower.endswith(tuple(suffix.casefold() for suffix in CAST_PROTECTED_SUFFIXES)):
        return False
    return lower.startswith(tuple(prefix.casefold() for prefix in (CAST_MESH_PREFIX, CAST_ANIM_PREFIX)))


def expected_cast_assets(manifest: dict) -> set[str]:
    """Every asset name the current cast.json asks the importer to create."""
    expected: set[str] = set()
    for entry in (manifest.get("meshes") or {}).values():
        if isinstance(entry, dict) and entry.get("name"):
            expected.add(str(entry["name"]))
    for group in (manifest.get("groups") or {}).values():
        if not isinstance(group, dict):
            continue
        base = group.get("base_mesh") or {}
        if base.get("name"):
            expected.add(str(base["name"]))
        disk = group.get("duel_disk") or {}
        if disk.get("name"):
            expected.add(str(disk["name"]))
        for anim in (group.get("anims") or {}).values():
            if isinstance(anim, dict) and anim.get("name"):
                expected.add(str(anim["name"]))
    return expected


def stale_owned_assets(owned: set[str], expected: set[str]) -> list[str]:
    """Names recorded by a previous import that the new manifest no longer wants.

    An empty expected set is treated as an incomplete export (not "delete the
    whole cast") and returns nothing.
    """
    if not expected:
        return []
    # Unreal asset paths are case-insensitive: a case-only rename must not be
    # treated as a stale asset (deleting it would remove the new import).
    expected_folded = {name.casefold() for name in expected}
    return sorted(name for name in owned
                  if is_cast_owned(name) and name.casefold() not in expected_folded)


def state_document(names) -> dict:
    """Serializable ownership record written after a cast import."""
    return {"version": CAST_STATE_VERSION, "assets": sorted(set(map(str, names)))}


def owned_names(document) -> set[str]:
    """Read an ownership record, rejecting unknown formats instead of guessing."""
    if not isinstance(document, dict) or document.get("version") != CAST_STATE_VERSION:
        raise ValueError("unsupported cast ownership record")
    assets = document.get("assets")
    if not isinstance(assets, list):
        raise ValueError("cast ownership record has no asset list")
    return {str(name) for name in assets if str(name)}


def write_json_atomic(path: str | os.PathLike[str], value) -> None:
    """Small stdlib atomic writer for the ownership record in Saved/.

    Deliberately mirrors :func:`dai.atomic.write_text` without importing it: this
    module stays stdlib-only so the rules are unit-testable in the editor and in
    bare Python, hence the same-directory temp file, ``os.replace`` publish and
    ``os.fsync`` of the UTF-8 / LF bytes inlined below.
    """
    path = os.fspath(path)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=os.path.basename(path) + ".", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fp:
            json.dump(value, fp, indent=1)
            fp.write("\n")
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            try:
                os.unlink(temp_name)
            except OSError:
                pass
