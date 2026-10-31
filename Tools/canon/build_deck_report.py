"""Generate Docs/Canon/DECK_TRACEABILITY.md from the canon deck data.

This is the Gate 3 deck audit: every canon deck id, opponent, evidenced card
list, count, unresolved slot count and source. It also records the negative ROM
deck-table search so downstream lanes do not assume the lists are ROM-extracted.
"""
from __future__ import annotations

import sys

from canon_common import CANON_DIR, DOCS_DIR, read_json, utc_now, write_text


def card_name_map() -> dict[int, str]:
    cards = read_json(CANON_DIR.parent / "cards.json")
    return {int(c["id"]): c["name"] for c in cards}


def main() -> int:
    names = card_name_map()
    decks_doc = read_json(CANON_DIR / "decks.json")
    decks = decks_doc["decks"]
    opponents = {o["id"]: o for o in read_json(CANON_DIR / "opponents.json")["opponents"]}
    events = {e["id"]: e for e in read_json(CANON_DIR / "events.json")["events"]}
    generic = decks_doc.get("generic_shell", {})

    lines = [
        "# Canon deck traceability (Gate 3)",
        "",
        f"Generated: {utc_now()}",
        "",
        "This report audits every deck in `Content/Data/Canon/decks.json` against the",
        "available game source and extraction evidence. It is the companion to",
        "`GATE3_RECONCILIATION.md` and `TRACEABILITY.md`.",
        "",
        "## 1. Evidence and method",
        "",
        "| Evidence | What it proves | Limits |",
        "| --- | --- | --- |",
        "| ROM card tables `0xF243CC`, `0xF2A68C`, `0xF58294` | Card ids, names, stats and descriptions used to resolve every deck entry. | Card data only; not deck membership. |",
        "| ROM text pool `0x13F6DF0` + offsets `0x14280A0` | Exam-week warning strings (indices 74 and 93); event dialogue previews. | Does not encode deck lists. |",
        "| `game3d/src/duel/decklists.js` | Donor Jaden list and three starter lists. | Donor implementation, not independently verified against a ROM deck table. |",
        "| Yugipedia Starter Decks page | Three starter deck lists. | Public guide; starter lists match the donor implementation. |",
        "| Yugipedia Opponents page | Opponent roster, archetypes and signature cards. | Does not publish full opponent lists. |",
        "| GameFAQs Character Deck List FAQ v1.4 (Tracy_Smith, 2006-03-11) | Character-specific opponent lists, counts, missing-card notes and the shared generic shell. | Player-written guide, not a ROM dump; the author marks several lists as incomplete. |",
        "| GameFAQs Event FAQ (ishingun, v3) | Event opponents, timed-puzzle solution and E22/E23/E26 context. | No deck lists for Jinzo, Goblin King or Bastion's Seventh Deck. |",
        "",
        "### ROM deck-table search (negative evidence)",
        "",
        "The ROM was read in place and never copied into the repository. Two searches",
        "were run against the verified US ROM (`0c2f6069...4afe`):",
        "",
        "1. Raw little-endian `u16` scan for the known starter and Jaden card-id sequences",
        "   (the `romhack/research/find_decks.py` method). No contiguous 40-card sequence",
        "   was found for Fire, Water, Wind or Jaden.",
        "2. Scan of every valid GBA BIOS LZ77/RLE block and search of the decompressed",
        "   output for the same sequences. No match.",
        "",
        "Conclusion: the ROM does not expose an obvious uncompressed 40-card deck table",
        "at the card-id encoding used by `cards.json`. The deck lists below are therefore",
        "guide-derived; they are not marked ROM-exact. This is why no deck is labelled",
        "`exact` even when the guide says its character list is complete.",
        "",
        "### Generic shell",
        "",
        f"The FAQ lists a shared {generic.get('count', 15)}-card Year 1 generic shell. It is",
        "appended only where `use_generic_shell` is true. The FAQ says the shell is 15 or",
        "16 cards; this dataset uses the 15-card Year 1 legal selection and records the",
        "optional 16th slot as a global unresolved shell slot.",
        "",
        "Generic shell ids: " + ", ".join(f"{cid} ({names.get(cid, '?')})" for cid in generic.get("cards", [])),
        "",
        "## 2. Deck summary",
        "",
        "| Deck id | Name | Opponent | Type | Main | Extra | Status | Unresolved | Complete | Confidence |",
        "| --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |",
    ]
    for deck in decks:
        lines.append(
            f"| `{deck['id']}` | {deck['name']} | {deck.get('opponent') or ''} | {deck['type']} | "
            f"{deck['main_count']} | {deck['extra_count']} | {deck.get('status', '')} | "
            f"{deck.get('unresolved_slots', 0)} | {deck['complete']} | {deck.get('confidence', '')} |"
        )

    lines += [
        "",
        "## 3. Per-deck audit",
        "",
        "Each section lists the evidenced cards (source name -> canon card id and count),",
        "then the generic shell and the explicit unresolved slots.",
        "",
    ]
    for deck in decks:
        lines += [
            f"### `{deck['id']}` - {deck['name']}",
            "",
            f"- Opponent: `{deck.get('opponent') or 'n/a'}`",
            f"- Type: `{deck['type']}`; status: **{deck.get('status', '')}**; complete: **{deck['complete']}**",
            f"- Main: **{deck['main_count']}**; Extra: **{deck['extra_count']}**; unresolved slots: **{deck.get('unresolved_slots', 0)}**",
            f"- Confidence: **{deck.get('confidence', '')}**",
            f"- Source: {deck.get('source', '')}",
        ]
        if deck.get("faq_section"):
            lines.append(f"- FAQ section: `{deck['faq_section']}`")
        if deck.get("use_generic_shell"):
            lines.append("- Generic shell applied: yes (15-card Year 1 selection)")
        else:
            lines.append("- Generic shell applied: no")
        if deck.get("unresolved_reason"):
            lines.append(f"- Unresolved reason: {deck['unresolved_reason']}")
        if deck.get("notes"):
            lines.append("- Notes: " + " ".join(deck["notes"]))
        lines.append("")

        fixed = deck.get("fixed_cards", [])
        if fixed:
            by_cat: dict[str, list[dict]] = {}
            for card in fixed:
                by_cat.setdefault(card.get("category", "other"), []).append(card)
            lines += ["| Category | Source name | Canon card | Count | Optional |", "| --- | --- | --- | ---: | --- |"]
            for category in ("spell", "trap", "monster14", "monster56", "monster7", "extra", "donor", "other"):
                for card in by_cat.pop(category, []):
                    lines.append(
                        f"| {category} | {card['name']} | {card['canon_name']} `#{card['card_id']}` | "
                        f"{card['count']} | {card.get('optional', False)} |"
                    )
            for category, cards in by_cat.items():
                for card in cards:
                    lines.append(
                        f"| {category} | {card['name']} | {card['canon_name']} `#{card['card_id']}` | "
                        f"{card['count']} | {card.get('optional', False)} |"
                    )
            lines.append("")
        else:
            lines += ["- No evidenced card list; the deck is an explicit unknown.", ""]

        if deck.get("extra_cards"):
            lines += ["Extra Deck evidence:", ""]
            for card in deck["extra_cards"]:
                lines.append(f"- {card['name']} -> {card['canon_name']} `#{card['card_id']}` x{card['count']}")
            lines.append("")

        if deck.get("random_pool"):
            pool = [p for p in deck["random_pool"] if p.get("card_id")]
            lines += [
                f"Random pool ({len(pool)} evidenced normal monsters, not counted in Main):",
                "",
                ", ".join(f"{p['name']} `#{p['card_id']}`" for p in pool),
                "",
            ]

        if deck.get("unresolved_slots", 0):
            lines += [
                f"**Unresolved:** {deck['unresolved_slots']} card slot(s). "
                "They are not silently filled; see the reason above.",
                "",
            ]

    # Event constructs
    lines += [
        "## 4. Event constructs and opponent reconciliation",
        "",
        "The three bracket/partner constructs are not roster duelists. They are",
        "represented as `tournament` or `partner_pool` objects in `events.json`;",
        "their participants resolve to existing roster ids and year-1 decks.",
        "",
        "| Construct | Kind | Participants | Rounds | Used by | Evidence |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for construct in decks_doc.get("event_constructs", []):
        participants = construct.get("participants") or [construct.get("participants_source", "")]
        used_by = [eid for eid, event in events.items()
                   for duel in event.get("duels", [])
                   if (duel.get("tournament") or {}).get("id") == construct["id"]
                   or (duel.get("partner_pool") or {}).get("id") == construct["id"]]
        lines.append(
            f"| `{construct['id']}` | {construct['kind']} | {', '.join(participants)} | "
            f"{construct.get('rounds')} | {', '.join(used_by)} | {construct.get('note', '')} |"
        )

    lines += [
        "",
        "### Added event opponents",
        "",
        "| Opponent id | Name | Deck | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for oid in ("jinzo", "goblin_king", "sheppard"):
        opponent = opponents.get(oid, {})
        lines.append(
            f"| `{oid}` | {opponent.get('name', '')} | {opponent.get('deck') or opponent.get('deck_kind', '')} | "
            f"{opponent.get('note', '')} |"
        )

    lines += [
        "",
        "## 5. Remaining unknowns",
        "",
        "| Area | Remaining unknown | Evidence/why it stays open | Owner |",
        "| --- | --- | --- | --- |",
        "| Partial opponent decks | 15 decks / 140 slots | The FAQ marks missing cards or optional/dorm-dependent slots; each record carries an explicit `unresolved_slots` count. | A07 |",
        "| Fully unknown decks | 6 decks / 240 slots | `jinzo_spirit`, `bastion_seventh`, `torrey_special`, `chazz_ojama`, `jaden_improved`, `bastion_magnet`; no published list. | A07 |",
        "| Generic shell 16th slot | 1 shared slot | FAQ says 15 or 16; only the 15-card Year 1 selection is proven. | A01/A07 |",
        "| ROM deck table | not located | Raw u16 and compressed-block scans found no contiguous deck table. | A01 |",
        "| Exam week | exact Friday | ROM/exam calendar routine not decoded; a raw search found no 12-entry exam-date table; fallback is last Friday, marked unproven. | A02 |",
        "",
    ]

    write_text(DOCS_DIR / "DECK_TRACEABILITY.md", "\n".join(lines) + "\n")
    print(f"deck report: {len(decks)} decks; "
          f"{sum(1 for d in decks if d.get('complete'))} complete; "
          f"{sum(1 for d in decks if d.get('status') == 'partial')} partial; "
          f"{sum(1 for d in decks if d.get('status') == 'unknown')} unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
