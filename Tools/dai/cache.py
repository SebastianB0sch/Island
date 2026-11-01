"""Derived-file cache keys and validity checks.

The asset pipeline caches decoded meshopt glTF files and the VRM copies used by
Blender.  A cache entry must be keyed by the source *path* (two packs can ship
the same basename) and must not be trusted just because it exists: an
interrupted or truncated file is worse than no cache at all.
"""

from __future__ import annotations

import hashlib
import os
import struct


def source_key(path: str | os.PathLike[str]) -> str:
    """Stable 12-character key for a source path (case-insensitive on Windows)."""
    absolute = os.path.abspath(os.fspath(path))
    normalised = os.path.normcase(os.path.realpath(absolute))
    return hashlib.sha1(normalised.encode("utf-8")).hexdigest()[:12]


def cache_file(cache_dir: str | os.PathLike[str], source: str | os.PathLike[str], suffix: str) -> str:
    """Path for a derived copy of ``source`` inside ``cache_dir``."""
    source = os.fspath(source)
    stem = os.path.splitext(os.path.basename(source))[0]
    return os.path.join(os.fspath(cache_dir), f"{stem}-{source_key(source)}{suffix}")


def is_fresh(cache_path: str | os.PathLike[str], source_path: str | os.PathLike[str]) -> bool:
    """True when a non-empty cache exists and is at least as new as its source."""
    try:
        cached = os.stat(cache_path)
        source = os.stat(source_path)
    except OSError:
        return False
    return cached.st_size > 0 and cached.st_mtime_ns >= source.st_mtime_ns


def is_glb(path: str | os.PathLike[str]) -> bool:
    """Validate the GLB header and JSON chunk without parsing the whole file.

    Catches truncated caches left by an interrupted copy/decode: the declared
    total length and first chunk must fit inside the actual file.
    """
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as fp:
            header = fp.read(12)
            if len(header) < 12 or header[:4] != b"glTF":
                return False
            version, length = struct.unpack_from("<II", header, 4)
            if version not in (1, 2) or length < 20 or length > size:
                return False
            chunk = fp.read(8)
            if len(chunk) < 8:
                return False
            chunk_length, chunk_type = struct.unpack("<I4s", chunk)
            if chunk_type != b"JSON" or chunk_length == 0 or 20 + chunk_length > size:
                return False
    except OSError:
        return False
    return True


def require_file(path: str | os.PathLike[str], label: str = "source") -> str:
    """Return ``path`` or raise a clear ``FileNotFoundError`` naming it."""
    path = os.fspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"{label} file not found: {path}")
    return path
