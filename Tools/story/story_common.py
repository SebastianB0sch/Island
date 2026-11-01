"""Shared helpers for the one-shot A03 story migration scripts.

The scripts in this folder rewrite authored story JSON once. They must never
run on import and must not leave a truncated data file when interrupted, so
each keeps its work in ``main()`` and writes through :func:`write_json`.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "DuelAcademyIsland" / "Content" / "Data"
STORY_DIR = DATA_DIR / "Story"
CANON_DIR = DATA_DIR / "Canon"


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    """Write ``indent=2`` UTF-8 JSON with LF newlines via a same-directory temp."""
    payload = json.dumps(value, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
