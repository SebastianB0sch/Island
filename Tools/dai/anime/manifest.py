"""Pure cast.json document helpers.

Everything here is stdlib-only and free of side effects so the manifest
rules can be unit-tested without Blender (the same pattern as
``duel_academy/asset_paths.py``); the Blender stage code in ``dai.anime.build``
supplies the file I/O around it.
"""

from __future__ import annotations

_MANIFEST_SECTIONS = ("groups", "meshes", "materials")


def merge_partial_manifests(previous, subset):
    """Merge a partial (``only=...``) cast build into the previous full manifest.

    A partial build regenerates a *subset* of the cast.  Publishing that subset
    as-is would make the Unreal importer's stale-cast cleanup delete every
    ``SK_Anime_*`` / ``A_Anime_*`` asset missing from it (the importer treats
    cast.json as the full inventory), so the published document must always
    describe the whole cast.

    Rebuilt entries win: for every key present in both documents the rebuilt
    ``groups`` / ``meshes`` / ``materials`` entries replace the previous ones.
    Everything the rebuild did not touch keeps its previous entry, which still
    matches the files the previous export wrote (a partial build re-exports
    only its subset and does not prune).  Any extra top-level keys are taken
    from ``subset`` with ``previous`` as fallback.

    Returns a new dict; neither input is modified.  A non-dict ``subset`` is a
    ``TypeError``; when ``previous`` is unusable (missing or unreadable full
    document) the subset is returned unchanged, as the best available
    description of the cast.
    """
    if not isinstance(subset, dict):
        raise TypeError(f"partial cast build document is not an object: {type(subset).__name__}")
    if not isinstance(previous, dict):
        return dict(subset)
    merged = {**previous, **subset}
    for section in _MANIFEST_SECTIONS:
        previous_section = previous.get(section)
        subset_section = subset.get(section)
        merged[section] = {**(previous_section if isinstance(previous_section, dict) else {}),
                           **(subset_section if isinstance(subset_section, dict) else {})}
    return merged
