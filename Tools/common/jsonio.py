"""UTF-8 JSON / text I/O with the repository's on-disk format.

write_json produces ``json.dumps(value, indent=2, ensure_ascii=False) + "\\n"``
with LF line endings on every platform, creating parent directories.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path | str) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_text(path: Path | str, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def write_json(path: Path | str, value: Any, *, indent: int = 2, ensure_ascii: bool = False) -> None:
    write_text(path, json.dumps(value, indent=indent, ensure_ascii=ensure_ascii) + "\n")
