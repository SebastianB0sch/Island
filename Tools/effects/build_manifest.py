#!/usr/bin/env python3
"""Build the per-card effect coverage manifest.

Scans cards.json, the four current decks, the Tier 1 reservation list, optional
usage datasets, and Content/Data/Effects/scripts/*.json. Writes a deterministic
manifest with one entry for every one of the 1,200 cards.

Usage:
    python Tools/effects/build_manifest.py
    python Tools/effects/build_manifest.py --check
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import effect_data as data


def build(write: bool = True) -> dict:
    manifest = data.build_manifest_data()
    if write:
        data.write_json(data.MANIFEST_PATH, manifest)
    return manifest


def print_summary(manifest: dict) -> None:
    summary = manifest["summary"]
    statuses = summary["by_status"]
    tiers = summary["by_tier"]
    print(f"Cards: {summary['total']}")
    print("By status: " + ", ".join(f"{key}={statuses[key]}" for key in data.STATUS_ORDER))
    print("By tier: " + ", ".join(f"T{tiers[str(tier)]}" for tier in (0, 1, 2, 3)))
    tier0 = [entry for entry in manifest["cards"] if entry["tier"] == 0]
    tier0_bad = [entry for entry in tier0 if entry["status"] not in ("scripted", "vanilla")]
    print(f"Tier 0 covered: {len(tier0) - len(tier0_bad)}/{len(tier0)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate the scan without rewriting card_effect_manifest.json.",
    )
    args = parser.parse_args(argv)
    manifest = build(write=not args.check)
    print_summary(manifest)
    if not args.check:
        print(f"Wrote {data.MANIFEST_PATH.relative_to(data.ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
