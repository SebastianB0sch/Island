#!/usr/bin/env python3
"""Report pending card effects by content reachability.

Lanes, in priority order:

  1. story event opponent decks (`Story/events.json` -> Opponents/decks)
  2. all other opponent decks
  3. puzzle decks (`Puzzles/*.json`)
  4. starter decks (`decks.json`, `Decks/player_decks.json`)
  5. shop packs (`Shop/packs.json`)
  6. story reward/grant cards (secondary lane)
  7. long tail (not referenced by any of the above)

Outputs:
  * DuelAcademyIsland/Content/Data/Effects/coverage_by_deck.json
  * Docs/Effects/COVERAGE_BY_DECK.md

Usage:
    python Tools/effects/coverage.py
    python Tools/effects/coverage.py --check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import effect_data as data
import effect_patterns as patterns

LANE_TITLES = {
    "story_event_decks": "Story event opponent decks",
    "opponent_decks": "Opponent decks (full roster)",
    "puzzle_decks": "Puzzle decks",
    "starter_decks": "Starter / player decks",
    "shop_packs": "Shop packs",
    "story_rewards": "Story reward grants",
    "long_tail": "Long tail (no deck/pack/puzzle reference)",
}


def _table(headers: list[str], rows: list[list[object]]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def _manifest_index() -> dict[int, dict]:
    manifest = data.load_json(data.MANIFEST_PATH)
    return {int(entry["id"]): entry for entry in manifest["cards"]}


def _reason_of(entry: dict, card: dict) -> tuple[str, str]:
    code = entry.get("pending_reason_code")
    reason = entry.get("pending_reason")
    if code and reason:
        return code, reason
    import effect_patterns as patterns

    _, code, detail = patterns.classify_pending(card)
    return code, f"{code}: {detail}"


def build_report() -> tuple[dict, str]:
    cards = data.load_cards()
    by_id = data.cards_by_id(cards)
    manifest = data.load_json(data.MANIFEST_PATH)
    index = {int(entry["id"]): entry for entry in manifest["cards"]}
    breakdown = data.usage_breakdown()
    priority_order = data.USAGE_CATEGORY_ORDER

    pending = [entry for entry in manifest["cards"] if entry["status"] == "pending"]
    pending.sort(key=lambda entry: (priority_order.index(breakdown["priority"].get(entry["id"], "long_tail")), entry["id"]))

    category_rows: dict[str, dict] = {}
    for name in priority_order:
        ids = {int(card_id) for card_id in breakdown["categories"][name]["cards"] if int(card_id) in by_id}
        pending_ids = sorted(card_id for card_id in ids if index.get(card_id, {}).get("status") == "pending")
        item_rows = []
        payload = breakdown["categories"][name]
        item_map = payload.get("decks") or payload.get("puzzles") or payload.get("packs") or payload.get("events") or {}
        if name == "story_event_decks":
            item_map = {
                item_id: item for item_id, item in item_map.items() if item.get("events")
            }
        for item_id, item in item_map.items():
            item_ids = [card_id for card_id in item.get("cards", []) if card_id in by_id]
            item_pending = [card_id for card_id in item_ids if index.get(card_id, {}).get("status") == "pending"]
            item_rows.append(
                {
                    "id": item_id,
                    "name": item.get("name") or item.get("title") or item_id,
                    "cards": len(item_ids),
                    "pending": len(item_pending),
                    "pending_ids": sorted(item_pending),
                    "source": item.get("source"),
                    "events": item.get("events", []),
                    "opponent": item.get("opponent"),
                    "category": item.get("category"),
                    "level": item.get("level"),
                }
            )
        item_rows.sort(key=lambda row: (-row["pending"], row["id"]))
        category_rows[name] = {
            "cards": len(ids),
            "pending": len(pending_ids),
            "covered": len(ids) - len(pending_ids),
            "pending_ids": pending_ids,
            "items": item_rows,
        }

    reason_counts: dict[str, dict] = {}
    for entry in pending:
        card = by_id[int(entry["id"])]
        code, reason = _reason_of(entry, card)
        bucket = reason_counts.setdefault(code, {"count": 0, "detail": reason.split(": ", 1)[-1], "ids": []})
        bucket["count"] += 1
        bucket["ids"].append(int(entry["id"]))
    for bucket in reason_counts.values():
        bucket["ids"].sort()

    pending_rows = []
    for entry in pending:
        card = by_id[int(entry["id"])]
        code, reason = _reason_of(entry, card)
        categories = sorted(
            breakdown["card_categories"].get(int(entry["id"]), set()),
            key=lambda value: priority_order.index(value) if value in priority_order else 99,
        )
        pending_rows.append(
            {
                "id": int(entry["id"]),
                "name": entry["name"],
                "type": entry["type"],
                "tier": int(entry["tier"]),
                "priority": breakdown["priority"].get(int(entry["id"]), "long_tail"),
                "pending_reason_code": code,
                "pending_reason": reason,
                "categories": categories,
                "labels": sorted(breakdown["card_labels"].get(int(entry["id"]), set())),
            }
        )

    summary = {
        "total": len(manifest["cards"]),
        "scripted": sum(1 for entry in manifest["cards"] if entry["status"] == "scripted"),
        "vanilla": sum(1 for entry in manifest["cards"] if entry["status"] == "vanilla"),
        "pending": len(pending),
        "unsupported": sum(1 for entry in manifest["cards"] if entry["status"] == "unsupported"),
        "pending_by_priority": {
            name: sum(1 for row in pending_rows if row["priority"] == name) for name in priority_order
        },
        "pending_by_reason": {code: bucket["count"] for code, bucket in sorted(reason_counts.items())},
        "categories": {
            name: {
                "cards": row["cards"],
                "pending": row["pending"],
                "covered": row["covered"],
            }
            for name, row in category_rows.items()
        },
    }

    payload = {
        "schema_version": 1,
        "generated_by": "Tools/effects/coverage.py",
        "source": {
            "manifest": "DuelAcademyIsland/Content/Data/Effects/card_effect_manifest.json",
            "priority_order": priority_order,
        },
        "summary": summary,
        "categories": category_rows,
        "pending_cards": pending_rows,
    }

    return payload, render_markdown(payload)


def render_markdown(payload: dict) -> str:
    summary = payload["summary"]
    priority_order = payload["source"]["priority_order"]
    lines: list[str] = []
    lines.append("# Effect coverage by reachability")
    lines.append("")
    lines.append(
        "Generated by `python Tools/effects/coverage.py`. The manifest remains the source of "
        "truth; this report re-groups its `pending` rows by the content lane that can reach "
        "the card in this port."
    )
    lines.append("")
    lines.append("## Headline counts")
    lines.append("")
    lines.append(f"- Cards: **{summary['total']}**")
    lines.append(f"- Scripted: **{summary['scripted']}**")
    lines.append(f"- Vanilla / data-covered: **{summary['vanilla']}**")
    lines.append(f"- Pending: **{summary['pending']}**")
    lines.append(f"- Unsupported: **{summary['unsupported']}**")
    lines.append("")

    lines.append("## Reachability lanes")
    lines.append("")
    rows = []
    for name in priority_order:
        row = summary["categories"][name]
        rows.append(
            [
                LANE_TITLES[name],
                row["cards"],
                row["pending"],
                row["covered"],
            ]
        )
    lines.extend(_table(["Lane", "Unique cards", "Pending", "Covered"], rows))
    lines.append("")
    lines.append(
        "A card can appear in more than one lane. `priority` below assigns it to the first "
        "lane in the order shown. Story event opponent decks are the 20 `opponent_deck_id` "
        "files referenced by `Story/events.json`; the other opponent decks are still listed "
        "because they are playable from the roster."
    )
    lines.append("")
    lines.append(
        "Batch note: at the start of Gate 3.1 the story lane was 213 unique cards / 92 pending. "
        "Incoming deck data expanded it to 368 unique cards / 119 pending, so the lane totals are "
        "not like-for-like. Of the original 92-card backlog, 38 are now scripted and 54 remain "
        "pending."
    )
    lines.append("")

    lines.append("## Pending by priority")
    lines.append("")
    rows = []
    for name in priority_order:
        count = summary["pending_by_priority"][name]
        if count:
            rows.append([LANE_TITLES[name], count])
    lines.extend(_table(["Priority lane", "Pending"], rows))
    lines.append("")

    lines.append("## Pending by reason")
    lines.append("")
    lines.append(
        "Reasons are generated by the same pattern module that produces the scripts. A card "
        "stays pending when the whole printed effect is not covered, so a reason names the "
        "first unsupported capability rather than a guess about intent."
    )
    lines.append("")
    reason_rows = []
    for code, count in sorted(
        summary["pending_by_reason"].items(), key=lambda item: (-item[1], item[0])
    ):
        reason_rows.append([f"`{code}`", count])
    lines.extend(_table(["Reason code", "Pending"], reason_rows))
    lines.append("")
    lines.append("### Reason glossary")
    lines.append("")
    glossary_rows = []
    for code, count in sorted(
        summary["pending_by_reason"].items(), key=lambda item: (-item[1], item[0])
    ):
        detail = patterns.PENDING_REASONS.get(code, ("", ""))[1]
        if not detail:
            detail = next(
                (
                    row["pending_reason"].split(": ", 1)[-1]
                    for row in payload["pending_cards"]
                    if row["pending_reason_code"] == code
                ),
                "",
            )
        glossary_rows.append([f"`{code}`", count, detail])
    lines.extend(_table(["Reason code", "Pending", "Meaning"], glossary_rows))
    lines.append("")

    lines.append("## Story-event and roster hotspots")
    lines.append("")
    for name in ("story_event_decks", "opponent_decks", "puzzle_decks", "starter_decks"):
        category = payload["categories"][name]
        lines.append(f"### {LANE_TITLES[name]}")
        lines.append("")
        lines.append(
            f"- Unique cards: **{category['cards']}**; pending: **{category['pending']}**; "
            f"covered: **{category['covered']}**."
        )
        lane_rows = [row for row in payload["pending_cards"] if row["priority"] == name]
        if lane_rows:
            lane_reasons: dict[str, int] = {}
            for row in lane_rows:
                code = row["pending_reason_code"]
                lane_reasons[code] = lane_reasons.get(code, 0) + 1
            reason_summary = ", ".join(
                f"`{code}`={count}"
                for code, count in sorted(lane_reasons.items(), key=lambda item: (-item[1], item[0]))
            )
            lines.append(f"- Pending by reason: {reason_summary}.")
        if category["items"]:
            item_rows = []
            for item in category["items"][:20]:
                item_rows.append(
                    [
                        item["id"],
                        item["name"],
                        item["cards"],
                        item["pending"],
                    ]
                )
            lines.extend(_table(["ID", "Name", "Cards", "Pending"], item_rows))
            lines.append("")
        else:
            lines.append("")
    lines.append("")

    lines.append("## Full pending list by priority")
    lines.append("")
    lines.append(
        "The JSON report has the same rows plus every lane label (deck ids, puzzle ids, "
        "pack ids, event ids). The table below is intentionally complete so a later batch "
        "can be planned without reopening the manifest."
    )
    lines.append("")
    for name in priority_order:
        rows = [row for row in payload["pending_cards"] if row["priority"] == name]
        if not rows:
            continue
        lines.append(f"### {LANE_TITLES[name]} ({len(rows)})")
        lines.append("")
        table_rows = []
        for row in rows:
            table_rows.append(
                [
                    row["id"],
                    row["name"],
                    row["type"],
                    f"T{row['tier']}",
                    f"`{row['pending_reason_code']}`",
                ]
            )
        lines.extend(_table(["ID", "Name", "Type", "Tier", "Reason"], table_rows))
        lines.append("")

    lines.append("## Next batch")
    lines.append("")
    lines.append(
        "1. **Story event decks first.** Every card in this lane is reachable in the main "
        "campaign; convert the remaining whole-effect templates before touching shop-only "
        "cards."
    )
    lines.append(
        "2. **Roster decks second.** The non-story opponent decks add cards used by free "
        "duels and exams; they are still cheaper than the full shop pool."
    )
    lines.append(
        "3. **Runtime prerequisites.** The largest remaining groups need A04 primitives: "
        "side-specific Standby triggers, dynamic ATK/DEF, Equip/Field stat application, "
        "top-of-Deck placement, battle-damage triggers, and token creation. Do not script "
        "those effects around the gap."
    )
    lines.append(
        "4. **Vanilla/data-covered rows are not scripts.** Ritual Spell procedure text is "
        "covered by `rituals.json`; a summoning-restriction-only monster has no executable "
        "effect. Both are reported as `vanilla`, not `scripted`."
    )
    lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build the reports in memory without writing them.",
    )
    args = parser.parse_args(argv)
    payload, markdown = build_report()
    json_path = data.EFFECTS_DIR / "coverage_by_deck.json"
    md_path = data.ROOT / "Docs" / "Effects" / "COVERAGE_BY_DECK.md"
    if not args.check:
        data.write_json(json_path, payload)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(markdown, encoding="utf-8", newline="\n")
        print(f"Wrote {json_path.relative_to(data.ROOT)}")
        print(f"Wrote {md_path.relative_to(data.ROOT)}")
    print(
        f"pending={payload['summary']['pending']} "
        f"scripted={payload['summary']['scripted']} "
        f"vanilla={payload['summary']['vanilla']}"
    )
    for name in payload["source"]["priority_order"]:
        count = payload["summary"]["pending_by_priority"][name]
        if count:
            print(f"  {count:4d} {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
