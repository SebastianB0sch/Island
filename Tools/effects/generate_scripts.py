#!/usr/bin/env python3
"""Generate conservative data scripts for pending cards.

The generator is intentionally rule-based: each recipe in `effect_patterns.py`
matches the *whole* printed effect text.  If no recipe matches, the card is
left pending and the manifest/coverage tools record a precise reason.

Usage:
    python Tools/effects/generate_scripts.py --check
    python Tools/effects/generate_scripts.py --write
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import effect_data as data
import effect_patterns as patterns

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_effects import validate_json_schema  # noqa: E402


def _manifest_index() -> dict[int, dict]:
    manifest = data.load_json(data.MANIFEST_PATH)
    return {int(entry["id"]): entry for entry in manifest["cards"]}


def build_candidates() -> tuple[list[dict], list[dict]]:
    cards = data.load_cards()
    manifest = _manifest_index()
    schema = data.load_json(data.SCHEMA_PATH)
    generated: list[dict] = []
    skipped: list[dict] = []
    for card in sorted(cards, key=lambda item: int(item["id"])):
        card_id = int(card["id"])
        entry = manifest.get(card_id)
        if not entry or entry.get("status") != "pending":
            continue
        payload = patterns.build_payload(card, int(entry["tier"]))
        if payload is None:
            status, code, detail = patterns.classify_pending(card)
            skipped.append(
                {
                    "id": card_id,
                    "name": card.get("name"),
                    "type": card.get("card_type"),
                    "pending_status": status,
                    "reason_code": code,
                    "reason": detail,
                }
            )
            continue
        errors = validate_json_schema(payload, schema)
        if errors:
            skipped.append(
                {
                    "id": card_id,
                    "name": card.get("name"),
                    "type": card.get("card_type"),
                    "pending_status": "pending",
                    "reason_code": "generator_schema_error",
                    "reason": "; ".join(errors[:3]),
                }
            )
            continue
        generated.append(payload)
    return generated, skipped


def _script_path(card_id: int) -> Path:
    return data.SCRIPTS_DIR / f"{card_id}.json"


def write_payloads(payloads: list[dict], check: bool) -> tuple[int, int]:
    written = 0
    unchanged = 0
    for payload in payloads:
        path = _script_path(int(payload["card_id"]))
        serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == serialized:
                unchanged += 1
                continue
            raise SystemExit(
                f"refusing to overwrite existing script {path}; move it aside if it should be regenerated"
            )
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(serialized, encoding="utf-8", newline="\n")
        written += 1
    return written, unchanged


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Report what would be generated.")
    mode.add_argument("--write", action="store_true", help="Write missing script files.")
    args = parser.parse_args(argv)

    generated, skipped = build_candidates()
    if args.write:
        written, unchanged = write_payloads(generated, check=False)
        print(f"Wrote {written} script(s); {unchanged} already up to date.")
    else:
        print(f"Would generate {len(generated)} script(s).")
        for payload in generated:
            scripts = ", ".join(script["id"] for script in payload["scripts"])
            print(f"  {payload['card_id']:4d} {payload['name']} -> {scripts}")

    print(f"Still pending: {len(skipped)}")
    counts: dict[str, int] = {}
    for item in skipped:
        counts[item["reason_code"]] = counts.get(item["reason_code"], 0) + 1
    for code, count in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
        print(f"  {count:4d} {code}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
