# API change log

All contract changes are recorded here. A change is **breaking** if it renames
or removes a frozen field, changes a type, adds a required field, or changes the
meaning of an existing value. Breaking changes require a schema/header version
bump and a migration.

## v1.0.0 - 2026-10-30 - Gate 0 contract freeze

Baseline: `port/baseline`; initial commit `b4d8bb0`, lane commits continuous
(HEAD observed `3c02d4c` at final validation).

Added:

- `Docs/Contracts/README.md`: contract index, ownership matrix, freeze rules.
- `headers/DAStoryContract.h`: `EStoryCommand`, `FStoryCommand`,
  `FStoryChoice`, `FStoryCommandQueue`.
- `headers/DADuelContract.h`: `EDuelMode`, `FDuelRequest`, `FDuelResult`,
  mode-string helpers.
- `schemas/save.v1.schema.json`: authoritative save payload v1, including
  optional mid-scene `story` resume state.
- Canon data schemas: cards, decks, fusions, limitations, packs, events,
  story scenes, dialogue, emails, schedules, anchors, opponents, puzzles,
  exams, exam questions, effects manifest, effect script.
- Test/replay schemas: duel request, duel result.
- `Tools/validate/validate_all.py` + `schema_lite.py`: data validation.
- `Tools/integration/run_smoke.py`: validator/UE smoke runner stub.
- `Content/Data/Integration/`: baseline manifest, golden save, report folder.

Decisions frozen:

- `FDuelRequest.Mode` is the lowercase string set `story`, `free`, `tutorial`,
  `exam_timed`, `exam_practical`, `puzzle`, `ante`. `EDuelMode` mirrors it.
  `tutorial` was added because the opening scene uses a tutorial duel that is
  neither a story win nor a free duel.
- `FStoryCommand` keeps the masterplan field layout and adds `CommandId` for
  save/resume idempotency.
- Save `month` is a real calendar month; exam/pack `month_index` /
  `school_month` is the October-first school index.
- Collection files accept a bare array or a `{version, <collection>}` wrapper.
- `cards.json`, `decks.json` and `fusions.json` keep their current array shape.

Known follow-ups (not yet changes):

- A04 to add `FDuelRequest`/`FDuelResult` adapters and a seeded self-test
  argument (`-DADuelSelfTest=N`), preserving `FDuelEngine::Start` and
  `RunSelfTest`.
- A02 to implement `save.v1` and `DASaveSelfTest` (round-trip, fuzz,
  corruption, v1 golden fixture).
- A03 to publish `Story/events.json`, `dialogue.json`, `schedules.json`,
  `emails.json` and `scenes/*.json`.
- A05 to publish the 1,200-entry effect manifest and replace the 5-recipe
  fusion stub with the full table.
- A06 to publish `Shop/packs.json` and opponent/player deck files.
- A07 to publish opponents, 100 puzzles and 12 exam cycles.
- A08 to publish `World/anchors.json` with every location/anchor used by A03.
- A09 to publish portrait fallback/localization key data used by dialogue.

## v1.0.1 - 2026-10-30 - validator compatibility pass

No breaking change. The validator now normalizes the pre-contract shapes that
landed during Gate 0 so the baseline report is actionable before lanes migrate:

- `duelists[]` roster + `default_deck`/`evolution_rules`.
- Single-object puzzle files with embedded `opponent` state and `time_limit`.
- `pools[]` + per-slot `slots[]` pack catalogue.
- `position_ue`/`location_id` anchors and implicit locations.
- `scenes{}` bundles with lowercase command aliases.
- `nodes{}` dialogue and `npcs{}` schedules.
- Event bundles with `trigger`/`requirements`/`outcomes`.
- `Rules/banned_limited.json` entry objects and `banned` alias.
- `Exams/exams.json` `cycles[]` + `questions.json` Qxxx/options/answer_index.

Each shape emits a `*_schema_drift` warning. The warning is removed only when
the lane migrates to the v1 file or A10 formally extends the schema.

## v1.0.2 - 2026-10-30 - runtime save/canon alignment

No breaking change; the v1 schema now documents the payload A02 actually writes
and the canon layer A01 published:

- Save: `slot_name`, `saved_at`, `calendar.month_index` (0..11; October=0),
  `calendar.weekday`/`hour`, profile metadata, `meta`, and lane provider
  sections are accepted. Flat and `{counts:{...}}` inventory forms are both
  valid. The golden fixture now mirrors the runtime shape.
- Duel: `Tutorial` added to `EDuelMode`/mode strings; `FDuelResult` exposes the
  extra `FDuelResultStats` counters already produced by A04.
- Canon: `canon_*` checks cover 35 events, 100 puzzles, 48 packs, 31 decks,
  25 opponents, 12-cycle exams, 14 titles, 63 banlist cards, and report canon
  gaps (incomplete decks, unknown puzzle setups/timers, unresolved exam week)
  separately from runtime gaps.
- `world` coverage now accepts single-segment anchor ids and the A08
  `position_ue`/implicit-location shape while warning about drift.

## How to propose a change

1. Add a section here with date, owner, files, reason, compatibility and tests.
2. Update the schema/header and `Tools/validate/validate_all.py` in the same
   change.
3. Run `python Tools/integration/run_smoke.py --validate` and paste the summary
   in the lane handoff.
4. A10 reviews at the next gate; consumers update in the same wave.

## Compatibility policy

- v1 accepts optional new fields; consumers must ignore unknown object keys.
- New required fields or changed value meanings bump the major version.
- Save migrations are forward-only and tested with the golden fixture in
  `Content/Data/Integration/saves/`.
- Deprecated fields stay readable for one wave and are removed only after all
  lanes report green.

