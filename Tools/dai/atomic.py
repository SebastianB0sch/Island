"""Same-directory temp-file + :func:`os.replace` helpers for binary assets.

Blender's FBX exporter, Pillow and ``numpy.save`` all write their target file
directly.  A crash mid-write therefore leaves a truncated FBX / PNG / JPG /
heightfield, which later import stages cannot tell from a finished asset.  The
helpers here write to a unique temporary file in the *same directory* (so
``os.replace`` stays atomic on every supported filesystem) and only publish it
once the writer has finished.

Temporary names keep the target suffix (``T_Foo.png.<id>.tmp.png``) so writers
that select an output format from the extension - notably Pillow and Blender's
FBX exporter - keep their previous behaviour.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Iterator


def _target(path: str | os.PathLike[str]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


@contextlib.contextmanager
def atomic_path(path: str | os.PathLike[str]) -> Iterator[Path]:
    """Yield a temporary path next to ``path``; replace ``path`` on success.

    The temporary file is always removed when the block raises or when
    :func:`os.replace` fails, leaving any previous target untouched.
    """
    target = _target(path)
    suffix = target.suffix or ".tmp"
    fd, temp_name = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp" + suffix, dir=str(target.parent)
    )
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        yield temp_path
        os.replace(temp_path, target)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def write_bytes(path: str | os.PathLike[str], data: bytes) -> None:
    """Atomically replace ``path`` with ``data``."""
    with atomic_path(path) as temp_path:
        with temp_path.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())


def write_text(
    path: str | os.PathLike[str],
    text: str,
    *,
    encoding: str = "utf-8",
    newline: str | None = "\n",
) -> None:
    """Atomically replace ``path`` with ``text`` (UTF-8 and LF by default)."""
    with atomic_path(path) as temp_path:
        with temp_path.open("w", encoding=encoding, newline=newline) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())


def copy_file(source: str | os.PathLike[str], path: str | os.PathLike[str]) -> None:
    """Copy ``source`` over ``path`` atomically."""
    with atomic_path(path) as temp_path:
        shutil.copyfile(source, temp_path)


def save_image(image, path: str | os.PathLike[str], **save_kwargs) -> str:
    """Save a Pillow image atomically, keeping the target's format suffix."""
    with atomic_path(path) as temp_path:
        image.save(temp_path, **save_kwargs)
    return os.fspath(path)
