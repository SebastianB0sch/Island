"""Build stable dialogue keys for A03/A09 from the text index and events."""
from __future__ import annotations

import sys

from canon_common import CANON_DIR, ensure_dirs, read_json, utc_now, write_json


def main() -> int:
    ensure_dirs()
    index = read_json(CANON_DIR / "text" / "dialogue_index.json")["entries"]
    events = read_json(CANON_DIR / "events.json")["events"] if (CANON_DIR / "events.json").exists() else []

    by_index = {entry["index"]: entry for entry in index}
    event_keys = []
    for event in events:
        lines = []
        for candidate in event.get("dialogue_candidates", []):
            entry = by_index.get(candidate["index"])
            if not entry:
                continue
            lines.append({
                "key": f"DLG_{entry['index']:04d}",
                "index": entry["index"],
                "offset": entry["offset"],
                "sha256": entry["sha256"],
                "text_preview": entry["text_preview"],
                "tokens": entry["tokens"],
            })
        event_keys.append({"event": event["id"], "title": event["title"], "lines": lines})

    write_json(CANON_DIR / "dialogue_keys.json", {
        "schema_version": 1,
        "generated_utc": utc_now(),
        "key_format": "DLG_<four-digit string index>",
        "total_lines": len(index),
        "full_index": "DuelAcademyIsland/Content/Data/Canon/text/dialogue_index.json",
        "notes": [
            "Keys are stable for this ROM and index table (0x14280A0, 4,527 entries).",
            "Event candidates are keyword matches, not final scene keys; A03 must confirm.",
            "The text itself is local-only; see Docs/Canon/LOCAL_ONLY.md.",
        ],
        "events": event_keys,
    })
    print(f"dialogue keys: {len(index)} total, {len(event_keys)} event buckets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
