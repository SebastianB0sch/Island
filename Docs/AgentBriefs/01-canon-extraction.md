# A01 — Source Scribe

> **Read first:** `Docs/PORT_MASTERPLAN.md` (architecture, contracts, gates).
> **Role:** canon extraction and data archaeology.
> **Baseline branch:** `port/baseline` → work branch `port/a01-canon`.

## Mission

Turn the GBA original and public guides into a complete, machine-readable, traceable canon dataset for the port. You are the only agent allowed to define "what the original actually says."

## Inputs (read-only)

- `$GX_ROM`
- `$GX_ROM\patched.sav`, `romhack/save_crypto.py`
- `$GX_ROM\decompress_rom.py`, `romhack/README.md`, `romhack/cards.py`, `romhack/research/*`
- `$GX_ROM\game3d\src\duel\engine.js`, `decklists.js`, `public/data/cards.json`
- `$GX_ROM\ue5\Source\DuelAcademy\DuelEngine.*`, `DuelAcademyData.*`
- Public canon pages listed in Appendix D of the masterplan.
- Target data: `C:\dev\GX\DuelAcademyIsland\Content\Data\cards.json`.

## Owned files

- `Tools/canon/**`
- `Docs/Canon/**`
- `DuelAcademyIsland/Content/Data/Canon/**`
- `Docs/Canon/TRACEABILITY.md`, `GAPS.md`, `SOURCE_MAP.md`, `LOCATION_MAP.md`

Do **not** edit runtime C++, UI, world, save/schema, or another lane's data.

## Deliverables

1. **`Docs/Canon/SOURCE_MAP.md`**
   - ROM layout and offsets, text encoding/char map, control codes (`@5`, `@6`, `@7`, `$pNN`, line breaks).
   - Table formats for cards, names, descriptions, events, packs, decks, puzzles, exams, titles, calendar, save flags.
   - What is extracted vs. inferred vs. still unknown.

2. **`Tools/canon/*.py`**
   - Idempotent extractors/validators for cards, text, events, packs, decks, opponents, puzzles, exams, titles, banned list.
   - Never require network access for the core path; cache public pages only if needed.
   - Never write the ROM or extracted binary art into the repo.

3. **`Content/Data/Canon/*.json`**
   - `cards.json` verification (1,200 records match the ROM).
   - `calendar.json`: 12 months, weekdays, periods, exam days, first playable day.
   - `titles.json`: 12 permanent + temporary titles/conditions.
   - `packs.json`: 48 packs, prices, unlock conditions, card pools/rarity slots, pack size.
   - `opponents.json`: 20+ duelists, decks, evolution, dorm/location/schedule gates, gifts/ante.
   - `decks.json`: starter decks, canonical opponent decks, variants.
   - `puzzles.json`: 100 timed duels with fixed setups, limits, solutions, rewards.
   - `exams.json`: written question bank, practical definitions, scoring, pass mark.
   - `events.json`: 33+ events with date/weekday/period/location/condition/reward/choice data.
   - `dialogue_keys.json` + `emails.json` + `banned_list.json` + `dp_rules.json`.
   - `manifest.json` with schema version, source hashes, extraction date.

4. **`Docs/Canon/TRACEABILITY.md`**
   - One row per runtime ID: `id | type | source (ROM offset / URL / inference) | confidence | used by | test`.
   - Every event, opponent, pack, puzzle, exam, title, and card must appear.

5. **`Docs/Canon/GAPS.md`**
   - Missing/ambiguous data, fallback decision, owner, blocking impact.
   - Explicitly flag anything that cannot be extracted.

## Work plan

1. Verify the existing 1,200-card extraction against the ROM (`romhack --verify`); record card count/IDs.
2. Map the text system: find the story/dialogue table(s), decode the char map/control codes, and dump a sample scene. Start from the verified ASCII pools `0x146C000`–`0x146D000`; names at `0x146CB14`/`0x146CC32`.
3. Extract calendar/title/exam/DP strings and tables; cross-check against the Yugipedia pages.
4. Extract pack definitions/prices/pools; cross-check the 48-pack list.
5. Extract opponent decks/variants; cross-check with the opponents page.
6. Extract the 100 puzzle setups/solutions; if the ROM format is opaque, use the guide and mark confidence.
7. Extract event conditions/rewards; cross-check the events page; record ambiguous conditions.
8. Publish the baseline JSON + traceability + gaps.
9. Run a handoff review with A03/A06/A07; answer their canon questions; freeze `Canon/` (read-only afterward).

## Acceptance criteria

- [ ] 1,200 cards match the ROM exactly (IDs, names, stats, types, descriptions).
- [ ] 33+ events with conditions, locations, choices, rewards, and trace IDs.
- [ ] 48 packs with prices, unlocks, pools/odds and pack size.
- [ ] 20+ opponents with legal, complete deck lists and variants.
- [ ] 100 puzzles with setups, limits, solutions and rewards.
- [ ] 12 permanent titles + temporary titles with exact thresholds.
- [ ] 12-month calendar, exam days, periods, first playable day.
- [ ] Written-exam bank and practical definitions.
- [ ] Banned/limited list and DP formula.
- [ ] Text/char map documented; story dialogue status explicit (extracted or fallback).
- [ ] `TRACEABILITY.md` covers 100% of runtime IDs.
- [ ] No ROM/save/ripped asset committed; extraction output is reproducible.

## Non-goals

- Implementing runtime systems or UI.
- Writing final story prose (A03 owns the port script; you supply canon/keys).
- Changing the target save schema.
- Balancing the game (A10/A07).

## Handoff report

Report: files changed, extraction commands, counts, confidence levels, open questions, blockers, and the exact list of IDs now frozen for downstream lanes.
