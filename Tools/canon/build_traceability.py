"""Generate Docs/Canon/TRACEABILITY.md from the canon JSON."""
from __future__ import annotations

import sys
from pathlib import Path

from canon_common import CANON_DIR, DOCS_DIR, read_json, utc_now, write_text


def main() -> int:
    cards = read_json(CANON_DIR.parent / "cards.json")
    card_manifest = read_json(CANON_DIR / "cards_manifest.json")
    packs = read_json(CANON_DIR / "packs.json")["packs"]
    events = read_json(CANON_DIR / "events.json")["events"]
    opponents = read_json(CANON_DIR / "opponents.json")["opponents"]
    decks = read_json(CANON_DIR / "decks.json")["decks"]
    puzzles = read_json(CANON_DIR / "puzzles.json")["puzzles"]
    titles = read_json(CANON_DIR / "titles.json")["titles"]
    banned = read_json(CANON_DIR / "banned_list.json")["cards"]
    exams = read_json(CANON_DIR / "exams.json")
    text = read_json(CANON_DIR / "text" / "dialogue_index.json")

    lines = [
        "# Canon traceability matrix",
        "",
        f"Generated: {utc_now()}",
        "",
        "One row per runtime ID. `Source` is a ROM offset, a public-guide URL, or an explicit inference.",
        "`Confidence` is `exact` only for byte-verified ROM data; everything guide-derived is marked.",
        "",
        "## Coverage summary",
        "",
        "| Type | Count | Source of truth | Confidence | Used by |",
        "| --- | ---: | --- | --- | --- |",
        f"| Cards | {len(cards)} | ROM 0xF243CC / 0xF2A68C / 0xF58294 | exact | A05, A06 |",
        f"| Packs | {len(packs)} | Yugipedia set pages + ROM pack names | high price/pool, low odds | A06 |",
        f"| Events | {len(events)} | Yugipedia Events + ROM dialogue | high/medium | A03 |",
        f"| Opponents | {len(opponents)} ({sum(1 for o in opponents if o.get('role') != 'event')} named + {sum(1 for o in opponents if o.get('role') == 'event')} event) | Yugipedia Opponents + ROM name pool | medium | A07 |",
        f"| Decks | {len(decks)} ({sum(1 for d in decks if d.get('complete'))} complete) | starter guide + Character Deck FAQ v1.4 + donor Jaden | high starters, mixed opponents | A06, A07 |",
        f"| Puzzles | {len(puzzles)} | Yugipedia puzzle pages | high solution, unknown setup | A07 |",
        f"| Titles | {len(titles)} | ROM 0x146C858 + guides | mixed | A02 |",
        f"| Banned/Limited | {len(banned)} | Yugipedia Banned List | high | A04, A06 |",
        f"| Written exam templates | {exams['written']['question_templates_count']} | ROM 0x1430F2C | high templates, low keys | A07 |",
        f"| Dialogue strings | {len(text['entries'])} | ROM 0x13F6DF0 / table 0x14280A0 | high offsets, local-only text | A03, A09 |",
        f"| Dialogue keys | {len(text['entries'])} | `DLG_XXXX` over the same index | high key stability | A03, A09 |",
        "",
    ]

    lines += ["## Cards", "", "| ID | Name | Type | Attribute | Level | ATK | DEF | Source | Confidence |",
              "| ---: | --- | --- | --- | ---: | ---: | ---: | --- | --- |"]
    for card in cards:
        lines.append(
            f"| {card['id']} | {card['name']} | {card['card_type']} | {card['attribute']} | "
            f"{card['level']} | {card['atk']} | {card['def']} | ROM 0x{0xF243CC + card['id'] * 4:06X} | exact |"
        )

    lines += ["", "## Packs", "", "| ID | Name | Price | Cards/pack | Pool | Unlock | Source | Confidence |",
              "| --- | --- | ---: | ---: | ---: | --- | --- | --- |"]
    for pack in packs:
        lines.append(
            f"| {pack['id']} | {pack['name']} | {pack['price_dp']} | {pack['cards_per_pack']} | "
            f"{pack['pool_cards_listed']} | {pack['unlock'].get('raw', pack['unlock'].get('type'))} | "
            f"[guide]({pack['source']['guide']}) | {pack['confidence']['pool']} |"
        )

    lines += ["", "## Events", "", "| ID | Title | When | Where | Confidence | Source | Dialogue candidates |",
              "| --- | --- | --- | --- | --- | --- | ---: |"]
    for event in events:
        when = event.get("when", {})
        when_text = ", ".join(f"{k}={v}" for k, v in when.items())
        lines.append(
            f"| {event['id']} | {event['title']} | {when_text} | {'; '.join(event.get('where', []))} | "
            f"{event['confidence']} | [Events]({event.get('source', 'https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events')}) | "
            f"{len(event.get('dialogue_candidates', []))} |"
        )

    lines += ["", "## Opponents", "", "| ID | Name | Dorm | Archetype | Signature cards | Confidence |",
              "| --- | --- | --- | --- | ---: | --- |"]
    for opponent in opponents:
        lines.append(
            f"| {opponent['id']} | {opponent['name']} | {opponent.get('section', '')} | "
            f"{opponent.get('archetype', '')} | {len(opponent.get('signature_card_ids', []))} | "
            f"{opponent.get('confidence', '')} |"
        )

    lines += ["", "## Decks", "",
              "| ID | Name | Type | Main | Extra | Status | Unresolved slots | Complete | Confidence | Source |",
              "| --- | --- | --- | ---: | ---: | --- | ---: | --- | --- | --- |"]
    for deck in decks:
        source = deck.get("source", "")
        if source.startswith("http"):
            source = f"[guide]({source})"
        lines.append(
            f"| {deck['id']} | {deck['name']} | {deck['type']} | {deck['main_count']} | "
            f"{deck['extra_count']} | {deck.get('status', '')} | {deck.get('unresolved_slots', 0)} | "
            f"{deck['complete']} | {deck.get('confidence', '')} | {source} |"
        )
    constructs = read_json(CANON_DIR / "decks.json").get("event_constructs", [])
    if constructs:
        lines += ["", "### Event constructs", "",
                  "| ID | Kind | Participants | Rounds | Source |",
                  "| --- | --- | --- | ---: | --- |"]
        for construct in constructs:
            participants = construct.get("participants") or [construct.get("participants_source", "")]
            lines.append(
                f"| {construct['id']} | {construct['kind']} | {', '.join(participants)} | "
                f"{construct.get('rounds')} | [Events]({construct.get('source', '')}) |"
            )

    lines += ["", "## Puzzles", "", "| ID | Level | Solution steps | Setup | Confidence | Source |",
              "| --- | ---: | ---: | --- | --- | --- |"]
    for puzzle in puzzles:
        lines.append(
            f"| {puzzle['id']} | {puzzle['level']} | {len(puzzle['solution_steps'])} | "
            f"{puzzle['setup'] or 'unknown'} | {puzzle['confidence']['solution']} | "
            f"[guide]({puzzle['source']}) |"
        )

    lines += ["", "## Titles", "", "| ID | Name | Permanent | Conditions | Confidence |",
              "| --- | --- | --- | --- | --- |"]
    for title in titles:
        lines.append(
            f"| {title['id']} | {title['name']} | {title['permanent']} | "
            f"{title['conditions']} | {title['confidence']} |"
        )

    lines += ["", "## Banned / Limited", "", "| Card ID | Name | Year 1 | Year 2 | Year 3 |",
              "| ---: | --- | --- | --- | --- |"]
    for card in banned:
        status = card["status"]
        lines.append(f"| {card['card_id']} | {card['name']} | {status['year_1']} | {status['year_2']} | {status['year_3']} |")

    lines += ["", "## Exams and text", "", "| ID | Type | Source | Confidence |",
              "| --- | --- | --- | --- |",
              f"| written_exam_bank | question templates | ROM 0x1430F2C | high templates / low keys |",
              f"| practical_exam_1..7 | practical definitions | ROM 0x146C23E | high |",
              f"| dialogue_index | 4,527 strings | ROM 0x13F6DF0 / 0x14280A0 | high offsets, local-only text |",
              f"| name_table | 26 full / 26 short names | ROM 0x146CB14 / 0x146CC32 | exact |",
              ""]

    write_text(DOCS_DIR / "TRACEABILITY.md", "\n".join(lines) + "\n")
    print(f"traceability rows: cards={len(cards)} packs={len(packs)} events={len(events)} "
          f"opponents={len(opponents)} decks={len(decks)} puzzles={len(puzzles)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
