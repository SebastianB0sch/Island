#!/usr/bin/env python3
"""Coverage audit wrapper for the A05 effect lane.

Runs, in order:
  1. build_manifest.py's scan (rewrites card_effect_manifest.json)
  2. validate_effects.py's schema/integrity checks
  3. report_coverage.py (rewrites Docs/Effects/COVERAGE.md)
  4. coverage-target checks

Exit code is 1 if any validation error or coverage target fails.

Baseline stage (default): Tier 0 and Tier 1 are hard gates, usage legality and
fusion/ritual accounting are hard gates, and Tier 2/3 coverage is reported as
an explicit backlog. Release stage (--release): every Tier 2 and Tier 3 card
must be covered too, i.e. the full 1,200-card gate.

Usage:
    python Tools/effects/audit.py
    python Tools/effects/audit.py --release
    python Tools/effects/audit.py --strict-tier2
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_manifest
import effect_data as data
import report_coverage
import validate_effects


def _pct(value: int, total: int) -> float:
    if total == 0:
        return 100.0
    return (value / total) * 100.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict-tier2",
        action="store_true",
        help="Require every Tier 2 (usage-dataset) card to be covered. Release gate.",
    )
    parser.add_argument(
        "--strict-tier3",
        action="store_true",
        help="Require every Tier 3 (remaining pool) card to be covered. Release gate.",
    )
    parser.add_argument(
        "--release",
        action="store_true",
        help="Shortcut for --strict-tier2 --strict-tier3 (full 1,200-card gate).",
    )
    args = parser.parse_args(argv)
    strict_tier2 = args.strict_tier2 or args.release
    strict_tier3 = args.strict_tier3 or args.release

    print("== build manifest ==")
    manifest = build_manifest.build(write=True)
    build_manifest.print_summary(manifest)

    print("\n== validate ==")
    report, stats = validate_effects.validate()
    for warning in report.warnings:
        print(f"WARNING {warning}")
    for error in report.errors:
        print(f"ERROR {error}")

    print("\n== coverage report ==")
    coverage_text = report_coverage.build_report()
    coverage_path = data.ROOT / "Docs" / "Effects" / "COVERAGE.md"
    coverage_path.parent.mkdir(parents=True, exist_ok=True)
    coverage_path.write_text(coverage_text, encoding="utf-8", newline="\n")
    print(f"Wrote {coverage_path.relative_to(data.ROOT)}")

    entries = manifest["cards"]
    targets: list[tuple[str, float, float]] = []
    failures: list[str] = []

    tier_covered: dict[int, tuple[int, int]] = {}
    for tier in (0, 1, 2, 3):
        tier_entries = [entry for entry in entries if entry["tier"] == tier]
        covered = sum(
            1
            for entry in tier_entries
            if entry["status"] in ("scripted", "vanilla")
        )
        tier_covered[tier] = (covered, len(tier_entries))
        target = 0.0
        if tier in (0, 1):
            target = 100.0
        elif tier == 2 and strict_tier2:
            target = 100.0
        elif tier == 3 and strict_tier3:
            target = 100.0
        actual = _pct(covered, len(tier_entries))
        targets.append((f"Tier {tier} covered", actual, target))
        if actual + 1e-9 < target:
            failures.append(
                f"Tier {tier} coverage {covered}/{len(tier_entries)} ({actual:.1f}%) is below {target:.1f}%"
            )
        if tier in (2, 3) and target == 0.0 and covered < len(tier_entries):
            print(
                f"INFO Tier {tier} has {len(tier_entries) - covered} uncovered card(s); "
                "release gate: rerun with --release"
            )

    fusion = stats.get("fusion", {})
    ritual = stats.get("ritual", {})
    fusion_total = fusion.get("total", 0)
    fusion_accounted = fusion_total if fusion_total == 76 else 0
    ritual_total = ritual.get("total", 0)
    ritual_accounted = ritual_total if ritual_total == 22 else 0
    targets.append(("Fusion recipes accounted", _pct(fusion_accounted, 76), 100.0))
    targets.append(("Ritual procedures accounted", _pct(ritual_accounted, 22), 100.0))
    targets.append(("Fusion recipes resolved", _pct(fusion.get("resolved", 0), 76), 95.0))
    targets.append(("Ritual procedures resolved", _pct(ritual.get("resolved", 0), 22), 100.0))
    if fusion_accounted != 76:
        failures.append(f"Fusion coverage is {fusion_accounted}/76; every Fusion needs a recipe or explicit unresolved record")
    if ritual_accounted != 22:
        failures.append(f"Ritual coverage is {ritual_accounted}/22; every Ritual needs an entry")
    if _pct(fusion.get("resolved", 0), 76) < 95.0:
        failures.append(f"Only {fusion.get('resolved', 0)}/76 Fusion recipes resolved (target 95%)")
    if _pct(ritual.get("resolved", 0), 22) < 100.0:
        failures.append(f"Only {ritual.get('resolved', 0)}/22 Ritual procedures resolved (target 100%)")

    if report.errors:
        failures.append(f"{len(report.errors)} validation error(s)")

    print("\n== coverage targets ==")
    for label, actual, target in targets:
        status = "PASS" if actual + 1e-9 >= target else "FAIL"
        print(f"{status:4} {label}: {actual:.1f}% (target {target:.1f}%)")

    if failures:
        print("\nAUDIT FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nAUDIT PASSED")
    print(
        "Informational: overall coverage "
        f"{sum(tier_covered[tier][0] for tier in tier_covered)}/{len(entries)} "
        f"({_pct(sum(tier_covered[tier][0] for tier in tier_covered), len(entries)):.1f}%)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
