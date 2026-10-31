# Canon dataset

This directory is A01's source of truth for the Duel Academy GBA port. It is
generated from the US ROM plus public guides; every datum carries a source and
a confidence marker.

## Read in this order

1. [`SOURCE_MAP.md`](SOURCE_MAP.md) — ROM offsets, table formats, extraction status.
2. [`TEXT_FORMAT.md`](TEXT_FORMAT.md) — encoding, control codes, speaker table, sample scene.
3. [`TRACEABILITY.md`](TRACEABILITY.md) — one row per runtime ID.
4. [`DECK_TRACEABILITY.md`](DECK_TRACEABILITY.md) — per-deck audit, card lists, evidence and unknown slots.
5. [`GATE3_RECONCILIATION.md`](GATE3_RECONCILIATION.md) — Gate 3 before/after gaps.
6. [`GAPS.md`](GAPS.md) — unresolved data and fallbacks.
7. [`LOCATION_MAP.md`](LOCATION_MAP.md) — A08's audited GBA→GX map.
   [`LOCATION_MAP_A01.md`](LOCATION_MAP_A01.md) — A01's ROM-name extraction and initial mapping.
8. [`LOCAL_ONLY.md`](LOCAL_ONLY.md) — why full dialogue is not committed.
9. [`VALIDATION.md`](VALIDATION.md) — latest validator output.

## Data files

| File | Records | Notes |
| --- | ---: | --- |
| `Content/Data/Canon/cards_manifest.json` | 1,200 | exact ROM verification, type counts, stable hash, per-card hashes |
| `Content/Data/Canon/card_name_overrides.json` | 1 | display-only fix for card 212 |
| `Content/Data/Canon/calendar.json` | 12 months | Oct 2006–Sep 2007, weekdays, periods, fixed dates |
| `Content/Data/Canon/titles.json` | 14 | 12 permanent + Dropout penalty + Occult temporary |
| `Content/Data/Canon/packs.json` | 48 | prices, pools, rarities, unlocks; all 1,200 cards obtainable |
| `Content/Data/Canon/opponents.json` | 28 | 25 named + 3 event duelists; dorm, archetype, signature cards, gifts, deck refs |
| `Content/Data/Canon/decks.json` | 37 | 16 complete, 15 partial (14 with explicit unknown slots, 1 unverified), 6 fully unknown; starters, donor Jaden, opponent/event decks, variants |
| `Content/Data/Canon/puzzles.json` | 100 | level, solution steps, cards; setups still unknown |
| `Content/Data/Canon/exams.json` | 89 templates | written bank, practical definitions, Gerard quiz |
| `Content/Data/Canon/events.json` | 35 | E01–E33 + E04b + E28b, conditions/rewards |
| `Content/Data/Canon/banned_list.json` | 63 | three-year Forbidden/Limited table |
| `Content/Data/Canon/dp_rules.json` | — | DP formula and event rewards |
| `Content/Data/Canon/emails.json` | — | contacts unlocked by events |
| `Content/Data/Canon/locations.json` | 26 | ROM names + GX mapping |
| `Content/Data/Canon/dialogue_keys.json` | 4,527 keys | stable `DLG_XXXX` keys + event candidate buckets |
| `Content/Data/Canon/manifest.json` | 21 files | source hashes, coverage, confidence |
| `Content/Data/Canon/text/*` | 4,527 strings | dialogue index, names, UI, control codes, script segments |

## Rebuild

```powershell
python Tools/canon/build_all.py
```

The offline path needs only:

- `$GX_ROM` (or `GX_ROM`), and
- `DuelAcademyIsland/Content/Data/cards.json`.

Guide facts are cached under `Tools/canon/cache/`. Opponent deck lists are
transcribed from the GameFAQs Character Deck List FAQ v1.4 into
`Tools/canon/deck_lists_faq.json`; the builder resolves every card against
`cards.json` and emits explicit `unresolved_slots` rather than filling gaps.
Re-fetch the public pages with `Tools/canon/fetch_guides.py` only when you
intentionally refresh them.

## Confidence

- `exact` — byte-for-byte ROM match.
- `high` — direct ROM text or unambiguous guide fact.
- `medium` — guide fact plus inference; verify in-game before freezing.
- `low` — placeholder/unresolved; see `GAPS.md`.

## Ownership

Only A01 edits `Tools/canon/**`, `Docs/Canon/**` and
`DuelAcademyIsland/Content/Data/Canon/**`. Downstream lanes consume this data
read-only and file correction requests through A10.
