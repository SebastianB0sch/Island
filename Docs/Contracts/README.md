# Integration contracts - v1 (Gate 0)

> **Owner:** A10 Gatekeeper. **Status:** frozen for Gate 0 on 2026-10-30.
> **Baseline:** `port/baseline`; initial commit `b4d8bb0`, lane commits land
> continuously (HEAD observed 3c02d4c at final validation).
> **Change process:** see [`API_CHANGELOG.md`](API_CHANGELOG.md). No lane may
> rename or remove a frozen field without an A10 review and a changelog entry.

This directory is the single source of truth for the interfaces the ten lanes
share. The JSON Schemas are normative for data; the headers in `headers/` are
the normative C++ shapes. Copy a header into `DuelAcademyIsland/Source/...`
when a lane adopts it; do not edit the copy in `Docs/Contracts/` from another
lane.

---

## 1. Freeze rules

1. **Additive changes only inside v1.** New optional fields are allowed if the
   validator treats them as optional and no consumer breaks. Renames, type
   changes and new required fields require a version bump.
2. **One writer per file.** Data files have one owner (section 7). Cross-lane
   edits go through A10 with a contract note and a test.
3. **No ad-hoc save keys.** Every progression field is in `save.v1.schema.json`.
   A02 owns the schema and migrations; other lanes request fields through A02.
4. **No hardcoded content.** Story text, rewards, decks, pack pools, puzzles and
   exams live in validated JSON, addressed by stable ids.
5. **No silent unsupported content.** A card that cannot be implemented gets an
   `unsupported` effect-manifest entry with a reason; if it appears in a deck,
   pack, puzzle or exam it is a release blocker, not a warning.
6. **Determinism.** Duel, pack, exam and puzzle inputs carry a seed. A result
   without its seed is not reproducible and fails validation.

The validator is the executable definition of these rules:

```powershell
python Tools/validate/validate_all.py
python Tools/validate/validate_all.py --strict
python Tools/integration/run_smoke.py --validate
```

`--strict` promotes known gaps and warnings to failures. Baseline mode reports
missing lane data as `GAP` without crashing, so the harness is usable from day
one.

---

## 2. Contract index

| Contract | File | Version | Producer | Consumers |
| --- | --- | --- | --- | --- |
| Story commands | [`headers/DAStoryContract.h`](headers/DAStoryContract.h) | 1 | A03 | A08, A09, A02 |
| Duel request/result | [`headers/DADuelContract.h`](headers/DADuelContract.h) | 1 | A04 | A02, A03, A07, A09 |
| Save payload | [`schemas/save.v1.schema.json`](schemas/save.v1.schema.json) | 1 | A02 | all systems |
| Cards | [`schemas/cards.schema.json`](schemas/cards.schema.json) | 1 | A01 | A04, A05, A06, A07 |
| Decks | [`schemas/decks.schema.json`](schemas/decks.schema.json) | 1 | A06 | A04, A07 |
| Fusions | [`schemas/fusions.schema.json`](schemas/fusions.schema.json) | 1 | A05 | A04, A06 |
| Limitations | [`schemas/limitations.schema.json`](schemas/limitations.schema.json) | 1 | A01 | A04, A06 |
| Packs | [`schemas/packs.schema.json`](schemas/packs.schema.json) | 1 | A06 | A02, A09 |
| Events | [`schemas/events.schema.json`](schemas/events.schema.json) | 1 | A03 | A02, A08, A09 |
| Story scenes | [`schemas/story-scene.schema.json`](schemas/story-scene.schema.json) | 1 | A03 | A08, A09 |
| Dialogue | [`schemas/dialogue.schema.json`](schemas/dialogue.schema.json) | 1 | A03 | A09 |
| Emails | [`schemas/emails.schema.json`](schemas/emails.schema.json) | 1 | A03 | A09 |
| Schedules | [`schemas/schedules.schema.json`](schemas/schedules.schema.json) | 1 | A03 | A08 |
| World anchors | [`schemas/anchors.schema.json`](schemas/anchors.schema.json) | 1 | A08 | A03, A09 |
| Opponents | [`schemas/opponents.schema.json`](schemas/opponents.schema.json) | 1 | A07 | A03, A04, A09 |
| Puzzles | [`schemas/puzzles.schema.json`](schemas/puzzles.schema.json) | 1 | A07 | A04, A09 |
| Exams | [`schemas/exams.schema.json`](schemas/exams.schema.json) | 1 | A07 | A02, A09 |
| Exam questions | [`schemas/exam-questions.schema.json`](schemas/exam-questions.schema.json) | 1 | A07 | A09 |
| Effect manifest | [`schemas/effects.schema.json`](schemas/effects.schema.json) | 1 | A05 | A04, A06, A07 |
| Effect script | [`schemas/effect-script.schema.json`](schemas/effect-script.schema.json) | 1 | A05 | A04 |
| Duel request JSON | [`schemas/duel-request.schema.json`](schemas/duel-request.schema.json) | 1 | A04 | tests, replay |
| Duel result JSON | [`schemas/duel-result.schema.json`](schemas/duel-result.schema.json) | 1 | A04 | tests, replay |

The schemas use JSON Schema draft-07. `Tools/validate/schema_lite.py` implements
the subset the validator needs, so no third-party package is required.

---

## 3. Canonical data layout

All runtime data lives under `DuelAcademyIsland/Content/Data/` and is staged by
`DefaultGame.ini` (`+DirectoriesToAlwaysStageAsUFS=(Path="Data")`).

```text
Content/Data/
├─ cards.json                     A01   array of 1,200 cards
├─ decks.json                     A06   existing starter decks
├─ fusions.json                   A05   existing fusion recipes
├─ Canon/                         A01   immutable baseline, traceability
│  └─ limitations.json            A01   forbidden/limited/semi-limited
├─ Decks/                         A06   extra deck files, same schema
├─ Shop/packs.json                A06   48 pack definitions
├─ Story/events.json              A03   event graph
├─ Story/dialogue.json            A03   line table, keyed by E01.node
├─ Story/schedules.json           A03   NPC weekly schedules
├─ Story/emails.json              A03   PDA mail + duel requests
├─ Story/scenes/*.json            A03   serializable command queues
├─ Opponents/opponents.json       A07   roster, decks, AI, evolution
├─ Puzzles/puzzles.json           A07   P001..P100
├─ Exams/exams.json               A07   12 exam cycles
├─ Exams/questions.json           A07   written question bank
├─ Effects/manifest.json          A05   one entry per card, 1..1200
├─ Effects/<card_id>.json         A05   effect scripts
├─ World/anchors.json             A08   locations, anchors, portals, spawns
├─ Profile/                       A02   titles, defaults, migrations
├─ UI/                            A09   portrait fallbacks, localization keys
└─ Integration/                   A10   fixtures, golden saves, reports
```

Existing `cards.json`, `decks.json` and `fusions.json` stay in their current
array form. New files may use a versioned wrapper:

```json
{ "version": 1, "events": [ ... ] }
```

The validator accepts either a bare array or the documented wrapper for every
collection except the save payload and effect manifest.

`Content/Data/Canon/**` is A01's reference layer and uses extraction-specific
shapes (`price_dp`, `pool[].card_id`, `when`/`where`, `solution_steps`,
`cycles[]`). It is checked by the validator's `canon_*` semantic checks, not by
the runtime schemas. Runtime files use the v1 schemas in this directory.

### Id conventions

| Entity | Format | Example |
| --- | --- | --- |
| Card | integer 1..1200 | `1` |
| Duelist / deck / pack / flag / counter | lowercase snake case | `shadow_duelist`, `jaden_year1`, `basic_1a` |
| Event | `E01`..`E33`, optional letter suffix | `E28b` |
| Puzzle | `P001`..`P100` | `P042` |
| Exam | `EXAM_01`..`EXAM_12` | `EXAM_01` |
| Scene / dialogue key | `<event>.<node>` | `E01.sheppard_01` |
| Anchor | `<location>.<segment>[.<segment>]` | `academy.lobby.door` |

---

## 4. Shared enumerations

These strings are frozen. C++ consumers should use the corresponding enum in
the headers; JSON uses the strings.

| Concept | Values |
| --- | --- |
| Dorm | `Slifer`, `Ra`, `Obelisk`, `White` (White = Society of Light story state) |
| Period | `AM`, `PM`, `Night` |
| Weekday | `Sunday`..`Saturday` (full English names) |
| Duel mode | `story`, `free`, `tutorial`, `exam_timed`, `exam_practical`, `puzzle`, `ante` |
| Story command | `Dialogue`, `Choice`, `Camera`, `MoveNpc`, `Fade`, `Wait`, `Banner`, `PlaySfx`, `Music`, `Duel`, `Reward`, `SetFlag`, `End` |
| Event state | `available`, `active`, `complete`, `failed`, `skipped` |
| Effect status | `scripted`, `vanilla`, `unsupported` |
| Card type | `Normal Monster`, `Effect Monster`, `Fusion Monster`, `Ritual Monster`, `Spell`, `Trap` |
| Exam result | `pass`, `fail`, `pending`, `exempt` |
| Practical objective | `battle`, `spells`, `traps`, `damage`, `fusion`, `ritual`, `special_summon` |

`month` is a real calendar month (1..12, October = 10) in saves, event dates and
`calendar_month` fields. `month_index` / `school_month` is the school-year index
(1 = October, 12 = September) in exam and pack schedules. Do not mix them.

---

## 5. Story command contract

`FStoryCommand` is a serializable queue item; it never draws UI or moves actors
directly. A03 produces the queue, A09 presents it, A08 supplies anchors, and
A02/A06 apply rewards and flags.

```cpp
FStoryCommand {
    EStoryCommand Type;
    FString CommandId;   // stable id for save/resume idempotency
    FString SpeakerId;   // "jaden"
    FString Portrait;    // "jaden_happy"; empty = fallback
    FString TextKey;     // "E01.sheppard_01"
    TArray<FString> Args;
    float Duration = 0.f;
    bool bSkippable = true;
}
```

Scene JSON mirrors the header:

```json
{
  "version": 1,
  "id": "E01",
  "event": "E01",
  "commands": [
    { "type": "Fade", "args": ["out"], "duration": 0.5, "skippable": false },
    { "type": "Dialogue", "speaker": "sheppard", "portrait": "sheppard_neutral",
      "text_key": "E01.sheppard_01", "skippable": true },
    { "type": "Duel", "args": ["syrus", "syrus_year1", "story"] },
    { "type": "Reward", "args": ["dp:100", "flag:event_01_cleared"] },
    { "type": "End" }
  ]
}
```

Rules enforced by `validate_all.py`:

- `End`, if present, is the last command.
- `Dialogue`/`Choice` keys exist in `Story/dialogue.json` once that file exists.
- `Camera` and `MoveNpc` anchors exist in `World/anchors.json` once that file
  exists.
- `Duel` opponents/decks/modes exist; `puzzle` mode names a valid puzzle.
- `Reward` card/pack/dp/title/dorm references are valid.
- A queue saved at any index restores identically; the save `story` object
  stores the scene id and `command_index`.

The exact GBA script text is **local-only reference**. Runtime dialogue may be a
transformative port or an original paraphrase; `source` on a line records which.
Do not commit extracted script dumps.

---

## 6. Duel request/result contract

`FDuelRequest` is built by A03/A07/A09 and consumed by A04. `FDuelResult` is
filled by A04 and consumed by A02 (DP/title/counters), A03 (story outcomes) and
A07 (exam/puzzle outcomes).

```cpp
FDuelRequest {
    FString OpponentId;       // roster slug
    FString OpponentDeckId;   // decks.json / Decks entry
    FString PlayerDeckId;     // inventory deck slot
    FString Mode;             // "story" | "free" | "exam_timed" | "exam_practical" | "puzzle" | "ante"
    FString PuzzleId;         // required for puzzle mode
    bool bAnte = false;
    int32 Seed = 0;
    int32 TurnLimit = 0;         // 0 = none
    int32 TimeLimitSeconds = 0;  // 0 = none
}
```

`FDuelResult` carries the statistics the DP formula needs (`Turns`, both LPs,
`BattleDamageDealt`, `MonstersDestroyedByBattle`), the final `DpEarned`, and
`FlagsSet`. It also carries `Seed`, `Reason`, `bPuzzleSolved` and
`TimeRemainingSeconds` so every result is replayable and testable.

Current engine note: `FDuelEngine::Start(PlayerDeckId, OpponentDeckId,
OpponentName, OpponentCharacterId)` and `FDuelEngine::RunSelfTest(Database,
Iterations)` exist today. A04 must add the request/result adapter without
breaking those signatures; the contract header is the target shape.

---

## 7. Save schema v1

`schemas/save.v1.schema.json` is the authoritative payload. It contains:

- `version` (const 1), `slot` (0 = autosave, 1..3 = manual), optional
  `slot_name`/`saved_at`
- `profile` (name, dorm, title, dp, gender, playtime/temporary-title fields)
- `calendar` (school year, real `month` 1..12, `month_index` 0..11,
  day, period, optional weekday/hour)
- `flags` and `counters` (stable snake_case keys)
- `inventory` (flat card id -> count, or A06 provider `{counts:{...}}`)
- `decks` (array, or provider section `{decks:[...]}`; main 40..60, extra <=20,
  side <=15, 3-copy limit)
- `events` (E-id -> state)
- `exams` (month index, written score, timed flag, practical score, result)
- `emails` (contact -> unlocked/read)
- `settings` (animation speed, activation confirmation, text speed, volumes)
- optional `story` (mid-scene resume: event/scene/command index/pending choice)
- optional `meta` (saved_at, playtime, build)

Migration rule: bump `version`, add a migration function in A02, keep a golden
v1 fixture in `Content/Data/Integration/saves/`, and prove the migration in
`DASaveSelfTest`. The validator checks every JSON save fixture against v1.

---

## 8. Data schema rules

- **Cards**: exactly 1,200 unique ids 1..1200; non-empty names/descriptions;
  monsters level 1..12 with a real attribute; spells/traps level 0 and
  `NONE`; subtype/card-type consistency.
- **Decks**: 40..60 main, <=20 extra, <=15 side (only if canon confirms a side
  deck), <=3 copies across main+extra+side, valid card ids, fusion monsters in
  extra, no non-fusion cards in extra.
- **Packs**: unique slug, price >= 0, pack size 1..10, non-empty pool, valid
  card ids, `slots` sum to pack size, rarity weights sum to 100 when present,
  unlock month/event/flag references valid. The union of all pack pools plus
  event rewards must eventually cover all 1,200 cards.
- **Events**: unique `E` ids; typed conditions only; valid dates/weekdays/
  periods; location/anchor/card/pack/opponent/deck/puzzle references; scene
  file exists; choices have unique ids and text keys; rewards granted once;
  `requires_events` is acyclic and every event is reachable.
- **Opponents**: unique slug, at least one deck, valid evolution decks, AI
  profile, difficulty 1..5, dorm enum, schedule reference, email hook.
- **Puzzles**: `P001..P100`, level 1..5 (20 each at content complete), valid
  setup card ids, turn/time limits, non-empty solution with known actions, seed.
- **Exams**: 12 cycles, unique month index, exactly 10 written questions,
  existing puzzle ids, 7 practical objectives, scoring max 500, pass mark.
- **Schedules**: valid weekdays/periods, existing locations/anchors, no
  overlapping entries for the same NPC/weekday/period, event overrides valid.
- **Anchors**: unique ids, existing location refs, numeric transforms, portal
  endpoints exist, spawn refs valid.
- **Effects**: exactly one manifest entry per card; scripted entries have a
  script with non-empty operations; unsupported entries have a reason; no
  unsupported card appears in a deck, pack, puzzle or exam.

---

## 9. Ownership matrix

Sole owner = only that agent edits. Shared files change only through A10.

| Path | Owner |
| --- | --- |
| `Tools/canon/**`, `Docs/Canon/**`, `Content/Data/Canon/**` | A01 |
| `DASaveGame.*`, `DAProfileSubsystem.*`, `DACalendarSubsystem.*`, `DATitleSystem.*`, `DASettings.*`, `Content/Data/Profile/**` | A02 |
| `DAStorySubsystem.*`, `DAEventGraph.*`, `Content/Data/Story/**`, `Docs/Story/**` | A03 |
| `DADuelEngine.*`, `DADuelRules.*`, `DADuelChain.*`, `DAEffectRuntime.*`, `DADuelTests.*` | A04 |
| `Content/Data/Effects/**`, `fusions.json`, `rituals.json`, `Tools/effects/**` | A05 |
| `DAInventorySubsystem.*`, `DAShopSubsystem.*`, `DADeckLogic.*`, `Content/Data/Shop/**`, `Content/Data/Decks/**`, `DACardDatabase.*`, `DACardRecords.*` | A06 |
| `DAOpponentSubsystem.*`, `DADuelistAI.*`, `DAExamSubsystem.*`, `Content/Data/Opponents/**`, `Puzzles/**`, `Exams/**`, `Tools/puzzles/**` | A07 |
| `Tools/dai/assets/**`, `Tools/dai/layout.py`, `Tools/dai/config.py`, `Content/Python/duel_academy/level.py`, `DAInterior*`, `DADoor*`, `DASceneAnchor*`, `DANpcSpawnPoint*`, `DANpcDirector*`, `DAWorldActors.*`, `DAStudentNPC.*`, `DAInteractable.*`, `Content/Data/World/**` | A08 |
| `DAHUD.*`, `DADuelUI.*`, `DADialogueUI.*`, `DAPDAUI.*`, `DAShopUI.*`, `DADeckUI.*`, `DAExamUI.*`, `DASaveUI.*`, `DACutscene.*`, `DACardArtSubsystem.*`, `DACharacterPortraitSubsystem.*`, `Content/Data/UI/**` | A09 |
| `Tools/validate/**`, `Tools/integration/**`, `.github/workflows/**`, `Docs/PORT_STATUS.md`, `Docs/Contracts/**`, `Content/Data/Integration/**`, build scripts | A10 |

Shared files (A10 only): `DAGameMode.*`, `DATypes.h`, `DAIslandSubsystem.*`,
`DAStudentCharacter.*`, `DuelAcademyIsland.Build.cs`, `Config/*.ini`,
`.uproject`, `DuelAcademyIsland.Target.cs`, `DuelAcademyIslandEditor.Target.cs`.

Generated/never hand-edited: `DuelAcademyIsland/Content/DuelAcademy/**`,
`Content/Collections/**`, `Content/Data/art/**`, `SourceAssets/**`.

A10 may make minimal glue fixes in shared files but must notify the lane owner
and record the change in `API_CHANGELOG.md`.

---

## 10. Integration and change process

1. **Lane RFC.** A lane that needs a contract change writes a short note:
   files, fields, consumers, migration, tests.
2. **A10 review.** A10 checks the change is additive or versioned, updates the
   schema/header, adds a validator assertion, and records it in
   `API_CHANGELOG.md`.
3. **Freeze.** The changed contract is announced at the next gate. Consumers
   update in the same wave; no lane silently forks a schema.
4. **Merge order.** A01/A10 -> A02/A04/A09 -> A03/A06/A08 -> A05/A07 -> A10.
   Run `python Tools/integration/run_smoke.py --validate` after every merge.
5. **No dirty tree.** Work on `port/aNN`; A10 merges into `port/baseline` at
   gates. Do not rebase another lane's uncommitted work.

---

## 11. Open canon questions

These are blockers for content freeze, not for systems work. A01 owns answers.

1. Exact exam pass mark and scoring weights (250 vs 300; practical 300).
2. Exact 48 pack prices, pack size, rarity slots, pools and unlock schedule.
3. Deck lists and evolution rules for all 20+ opponents, including ante/dorm
   variants.
4. Exact setups/solutions for all 100 timed puzzles; one-turn vs turn limit.
5. Full written-exam question bank and Gerard quiz answers.
6. Story script/dialogue extraction status and control codes.
7. Save layout/flags, to validate event conditions and title counters.
8. Whether a side deck exists; copy limit; banned/limited list.
9. Exact dates/conditions for E19/E20/E25/E28/E30.
10. Mandatory vs optional events and the exact ending trigger.
11. Offline link/trade equivalents.
12. Essential audio cues and synthesized replacements.

A01's `Content/Data/Canon/` extracts answer parts of 1-5 and 7-9 with explicit
confidence: 48 packs, 100 puzzles, 35 events, 25 opponents, 31 decks, 12-cycle
exams, 14 titles and a 63-card banlist. Puzzle setups/timers, the exact exam
week, most incomplete opponent decks, and the story-script extraction remain
open. The validator reports those as `canon_*` gaps, separate from runtime
gaps. See `Docs/PORT_STATUS.md` and `Docs/Canon/GAPS.md`.

---

## 12. Baseline data snapshot (2026-10-30)

The validator currently reads the live data tree, not just the baseline commit.
Counts at the Gate 0 snapshot:

- Canon reference (`Content/Data/Canon/`, A01): 35 events, 100 puzzles
  (20 per level), 48 packs, 25 opponents, 31 decks (4 complete), 12-cycle
  exams, 14 titles, 63 banlist cards. Canon is validated by the `canon_*`
  checks; it is not the runtime source of truth.
- `cards.json`: 1,200/1,200 cards, ids 1..1200, no duplicate ids.
- `decks.json` + `Opponents/decks/*` + player decks: 36 decks, all 40..60 main,
  extra <=4, <=3 copies. No side deck. Banlist: 14 forbidden, 40 limited,
  7 semi-limited; all published decks pass the current deck rules.
- `fusions.json`: 76/76 fusion monsters have recipes. Five recipes repeat a
  material and two use generic/unresolved materials; A05 must resolve them.
- `Shop/packs.json`: 48/48 packs; union of pools covers 1,200 cards.
  Dorothy's Gift has an empty pool (event-only placeholder).
- `Opponents/roster.json`: 25 duelists (20 ranked + event/exam-only), all deck
  references resolve.
- `Puzzles/P001..P100`: 100 runtime puzzle definitions across levels 1-5.
  Canon has 100 puzzles with solutions, but all canon setups and timers are
  unknown; A07 authors the runtime states and must prove the engine solutions.
- `Exams/`: `exams.json` now has 12 cycles; `questions.json` has 30 Qxxx
  questions and 12 sets; `scoring.json` and `practicals.json` define the
  500-point model and 7 objectives. The exam lifecycle still needs an engine
  test.
- `Story/opening.json`, `Story/scenes/opening.json`,
  `Story/dialogue/opening.json`, `Story/schedules/opening.json`: 3 runtime
  events (E01, E01b, FJ01), 21 scenes, 86 dialogue lines, 7 schedules. Canon
  has 35 events (E01..E33, E04b, E28b); the runtime E02..E33 wiring is missing.
- `World/`: 46 locations, 83 anchors, 10 interior cells, 20 portals and 28
  spawns. The opening scenes/schedules now resolve against the published
  anchor set; the validator reports no missing anchor ids.
- `Effects/`: 10 Tier-1 scripts and the 137-card engine regression baseline;
  `manifest.json` (1,200 entries) is missing.
- `Integration/saves/golden_new_game.json`: v1 golden save passes.
- The current duel engine exposes `Start`/`RunSelfTest` and the 137-card
  regression baseline; the `FDuelRequest`/`FDuelResult` adapter is target work
  for A04.
- `DATypes.h` currently exposes only `EDADorm`, `EDAInteractKind` and
  `FDAMessage`; the contract headers are not yet compiled into the module.

### Pre-contract data shapes

The following files were authored before the v1 wrappers landed. The validator
normalizes and validates them but emits `*_schema_drift` warnings so the owning
lane migrates at its gate:

| File | Current shape | v1 target |
| --- | --- | --- |
| `Rules/banned_limited.json` | `banned`/`limited` entry objects | `Canon/limitations.json` with integer id arrays |
| `Opponents/roster.json` | `duelists[]`, `evolution_rules` | `opponents[]`, `evolution` |
| `Puzzles/Pxxx.json` | one object per file, embedded opponent state | `puzzles[]` with `opponent`/`opponent_state` |
| `World/anchors.json` | `position_ue`, `location_id`, implicit locations | `locations[]`, `position{x,y,z}` |
| `Story/opening.json` | `trigger`/`requirements`/`outcomes`, scene ids | `date`/`requires`/`rewards`, scene paths |
| `Story/dialogue/opening.json` | `nodes{}` | `lines{}` |
| `Story/scenes/opening.json` | `scenes{}`, lowercase command types | one scene per file, `FStoryCommand` types |
| `Story/schedules/opening.json` | `npcs{}`, `periods[]` | `schedules[]`, `period` |
| `Exams/exams.json` + `questions.json` | `cycles[]`, Qxxx/options/answer_index | `exams[]`, Wxxx/answers/correct_index |

A10 will remove a drift warning only when the lane either migrates the file or
the schema is formally extended in `API_CHANGELOG.md`.

