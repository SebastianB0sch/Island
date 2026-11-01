"""Atomic same-directory temp-file writers for the data tools.

A crash in the middle of a write must never leave a truncated JSON or
Markdown file behind, so every writer here serializes to a unique temporary
file in the *same directory* (which makes :func:`os.replace` atomic on every
supported filesystem), fsyncs it, and only then replaces the target.  If
serialization or the replace fails, the temporary file is removed and any
previous target stays untouched.

This is the shared home for the writer that canon/stdory/economy scripts
grow inline today; import it the same way the script folders import the
``dai`` package:

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from tooling import atomic
"""

from __future__ import annotations

import contextlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterator


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
    fd, temp_name = tempfile.mkstemp(
        prefix=target.name + ".", suffix=".tmp", dir=str(target.parent)
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


def write_json(path: str | os.PathLike[str], payload: Any) -> None:
    """Atomically replace ``path`` with ``json.dumps(payload, indent=2)``.

    The serialization convention (indent=2, ``ensure_ascii=False``, trailing
    LF) matches the writers in Tools/canon, Tools/economy and Tools/story so
    the bytes stay byte-identical with the previous first-try writers.
    """
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
