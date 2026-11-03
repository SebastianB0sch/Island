# Opponents, Exams & Puzzles â€” A07 Notes

> Status: first pass complete (data-first). Baseline editor build is untouched by this lane.
> Owner: A07 Challenger. Branch: `port/baseline`.
> Scope of this pass: roster/deck/AI/exam/puzzle data, C++ skeletons, validators and tests. No duel-engine, HUD, UI, story, world, save, shop or inventory files were edited.

## 1. What shipped

| Area | Files | Count |
| --- | --- | ---: |
| Roster | `Content/Data/Opponents/roster.json` | 25 duelists (20 ranked, 4 event-only, 1 exam-only) |
| Opponent decks | `Content/Data/Opponents/decks/*.json` | 31 (25 base + 6 evolution variants) |
| AI profiles | `Content/Data/Opponents/ai/*.json` | 27 |
| Timed puzzles | `Content/Data/Puzzles/P001..P100.json` | 100 (20 per level) |
| Exam cycles | `Content/Data/Exams/exams.json` | 12 (EXAM_01..EXAM_12) |
| Written questions | `Content/Data/Exams/questions.json` | 30 questions + 12 deterministic 10-question sets |
| Practicals | `Content/Data/Exams/practicals.json` | 7 objectives, 200 practical points |
| Scoring | `Content/Data/Exams/scoring.json` | 500 points, pass mark 300 (candidate 250/300) |
| C++ | `DAOpponentSubsystem.*`, `DAExamSubsystem.*`, `DADuelistAI.*` | roster/deck/AI loader, exam lifecycle, policy stub |
| Tests | `DAOpponentTests.cpp`, `DAPuzzleTests.cpp`, `DAExamTests.cpp` | automation tests under `DuelAcademy.*` |
| Validator | `Tools/puzzles/validate.py` | cards/decks/roster/AI/puzzles/exams |
| Puzzle generator | `Tools/puzzles/generate_puzzles.py` | reproducible P021-P100 templates |
| Exam-cycle generator | `Tools/puzzles/generate_exams.py` | reproducible 12-cycle links |
| Report | `Docs/Opponents_Validation_Report.md` | generated PASS report |

Current validator result:

```text
PASS summary: 141 checks, 0 failures, 1 warnings
duelists=25 decks=31 ai=27 puzzles=100 questions=30
```

The one warning is pre-existing: `cards.json` has one duplicated card name (`Luster Dragon`, ids 663 and 780). Copy limits are by card name, so the roster copy of Jaden's deck swaps one 663 for Sparkman (1109) to stay legal; the baseline `Content/Data/decks.json` story deck is **not** edited (A06 owns it).

## 2. Data schemas

### 2.1 `Opponents/roster.json`

```json
{
  "schema_version": 1,
  "duelists": [{
    "id": "jaden",
    "name": "Jaden Yuki",
    "aliases": ["Judai Yuki"],
    "role": "ranked",              // ranked | staff | event | exam
    "rank": 1,
    "dorm": "Slifer",              // Slifer | Ra | Obelisk | Staff | Event | Exam
    "year": 1,
    "title": "Slifer Red",
    "ai_profile": "fusion",
    "decks": ["jaden_year1"],
    "default_deck": "jaden_year1",
    "signature_card_ids": [363, 381, 655, 663, 666],
    "signature_cards": ["Cyber-Tech Alligator", "Polymerization"],
    "canon_gift_card_ids": [1129],
    "canon_source": "https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Opponents",
    "canon_confidence": "medium",
    "evolution_rules": [{
      "id": "jaden_winged_kuriboh",
      "after_wins": 3,
      "counter": "wins_jaden",
      "deck": "jaden_year1",
      "confidence": "low",
      "source": "..."
    }],
    "schedule": [{
      "weekdays": ["Monday", "Tuesday"],
      "periods": ["AM", "PM"],
      "zone": "academy",
      "interior": "academy_arena"
    }],
    "locations": [
      { "zone": "slifer", "interior": "slifer_common", "name": "Slifer common room" }
    ],
    "access": {
      "requires_flag": "met_jaden",
      "requires_title": "",
      "requires_dorm": "",
      "event_only": false,
      "min_day": 0
    },
    "email": {
      "unlock_flag": "met_jaden",
      "address": "jaden.yuki@duelacademy.edu",
      "threads": [{ "id": "jaden_01", "subject": "Duel me!", "unlock_flag": "met_jaden" }]
    },
    "duel_request": {
      "unlock_flag": "met_jaden", "min_wins": 0,
      "cooldown_days": 1, "max_per_day": 1
    },
    "gifts": [{ "id": "jaden_christmas", "type": "dp", "amount": 500, "event": "E_CHRISTMAS" }],
    "ante": [1106, 1107, 1109],
    "walk_home": { "enabled": true, "zone": "slifer", "weekdays": ["Friday"], "period": "Night", "flag": "walk_home_jaden" },
    "confidence": "high",
    "source": "...",
    "notes": "..."
  }]
}
```

* `schedule` slots are matched by zone + optional interior + weekday + period. Empty arrays mean â€œanyâ€.
* `signature_card_ids` / `signature_cards` and `canon_gift_card_ids` are copied from A01's `Content/Data/Canon/opponents.json` for traceability. A01 notes that full opponent deck lists are not published; the actual 40-card reconstructions live in `decks/`.
* `access` gates are evaluated by `UDAOpponentSubsystem::IsDuelistUnlocked`; story flags are supplied by A03/A02.
* `gifts` are data only; A03 decides when the Christmas/event gift is granted.
* `confidence`/`source` are mandatory in practice even though the loader treats them as strings.

### 2.2 `Opponents/decks/<id>.json`

```json
{
  "schema_version": 1,
  "id": "zane_cyber",
  "opponent": "zane",
  "name": "Zane Truesdale - Cyber Dragon",
  "variant": "base",
  "confidence": "high",
  "source": "Yugipedia opponent outline + GX Cyber Dragon card pool",
  "notes": "Cyber Twin/End fusion recipes are present in A05's fusions.json.",
  "cards": [1152, 1152, 1152, 348, 348, "..."],
  "extra": [1157, 1158, 1155, 1156],
  "side": []
}
```

Deck rules enforced by `Tools/puzzles/validate.py`:

* 40â€“60 main, â‰¤20 extra, â‰¤15 side (side is not used by the duel engine yet).
* â‰¤3 copies by **card id** and by **card name**.
* Main deck contains no Fusion Monster; Extra Deck contains only Fusion Monsters.
* Every card id is in `cards.json` (1â€“1200).
* Every roster deck/evolution reference exists.

### 2.3 `Opponents/ai/<id>.json`

```json
{
  "schema_version": 1,
  "id": "fusion",
  "label": "Fusion",
  "strategy": "fusion",             // maps to EDAAIStrategy
  "difficulty": 3,
  "deterministic": true,
  "aggression": 0.75,
  "weights": {
    "summon": 0.9, "attack": 0.9, "direct_attack": 0.8,
    "removal": 0.6, "equip": 0.5, "set_trap": 0.7,
    "field_spell": 0.7, "fusion": 1.0, "ritual": 0.2,
    "burn": 0.1, "stall": 0.1, "draw": 0.4, "search": 0.7
  },
  "thresholds": {
    "attack_into_set_atk": 1900, "tribute_min_gain": 200,
    "save_removal_for_atk": 1600, "hold_trap_lp": 2500,
    "direct_attack_when_lethal": true, "respect_face_down": true
  },
  "preferred_card_names": ["Polymerization", "Miracle Fusion"],
  "avoid_card_names": [],
  "confidence": "medium",
  "source": "game3d/src/duel/engine.js runAiTurn heuristics + A07 design"
}
```

### 2.4 `Puzzles/P001..P100.json`

Follows the masterplan Appendix C.4 shape, with one deliberate clarification: `opponent` is the opponent **id**, and the fixed opponent board is `opponent_state`.

```json
{
  "schema_version": 1,
  "id": "P018",
  "level": 1,
  "title": "Polymerization Finish",
  "opponent": "mimicry",
  "seed": 1018,
  "turn_limit": 1,
  "time_limit": 75,
  "objective": "win_this_turn",
  "player": {
    "lp": 8000,
    "hand": [381, 1106, 1107],
    "field": [], "spell_traps": [], "graveyard": [], "deck": [], "extra": [1129]
  },
  "opponent_state": {
    "lp": 2100, "hand": [], "field": [], "spell_traps": [], "graveyard": [], "deck": [], "extra": []
  },
  "solution": [
    { "action": "activate_spell", "card_id": 381 },
    { "action": "attack", "attacker_card_id": 1129, "target": "direct" }
  ],
  "reward": { "dp": 180, "cards": [] },
  "engine_ready": true,
  "confidence": "medium",
  "source": "Original puzzle authored for the port (A07)...",
  "notes": "..."
}
```

Supported solution actions (validator and future replay adapter): `normal_summon` (optional `tribute_card_ids`), `special_summon`, `set_monster`, `activate_spell`, `set_spell_trap`, `activate_trap`, `activate_effect`, `attack` (`target`: `"direct"` or a card id), `change_position`, `discard`, `end_turn`.

P001-P020 are the original authored level-1 fallback lines. P021-P100 are generated by `Tools/puzzles/generate_puzzles.py` from ten tactical templates (direct attack, tribute summon, fusion, ritual, spell removal, trap negation, position switch, piercing, burn, special summon), two variants per level for levels 2-5. Every puzzle is one-turn with a fixed board, `turn_limit`, `time_limit`, reward, confidence and source.

Supported solution actions (validator and future replay adapter): `normal_summon` (optional `tribute_card_ids`), `special_summon`, `set_monster`, `activate_spell`, `set_spell_trap`, `activate_trap`, `activate_effect`, `attack` (`target`: `"direct"` or a card id), `change_position`, `discard`, `end_turn`.

All 100 use engine-supported cards: Blue-Eyes/Red-Eyes/Cyber-Tech Alligator, Fissure, Snatch Steal, Premature Burial, Monster Reincarnation, Heavy Storm, Book of Moon, Tribute to the Doomed, Upstart Goblin, Black Pendant, United We Stand, Mage Power, Sparks, Polymerization, Miracle Fusion, Incandescent Ordeal, Seven Tools of the Bandit, Spiritual Fire Art - Kurenai and Autonomous Action Unit.

Each file also carries `canon_reference`, copied from A01's `Content/Data/Canon/puzzles.json`: canonical solution card ids/names/steps, source URL and confidence. A01 has no fixed-board data (`setup: null`), so `setup_status` explicitly says the board, time limit and reward are port-authored. The playable line is an engine-ready fallback (`engine_ready: true`); P001's canonical line, for example, is Autonomous Action Unit + Exodia + Piranha Army, which will replace the fallback once the original setup and A05 effects are available. The validator replays all 80 generated templates with a small deterministic simulator (summon levels, tributes, equipment modifiers, fusion/ritual resolution, burn, piercing, Mirror Force + Seven Tools), so arithmetic and basic legality are checked without a UE build.

### 2.5 `Exams/questions.json`

* 30 questions (4 options, `answer_index`, explanation, topic, difficulty, confidence/source).
* 12 `exam_sets`, each 10 unique question ids selected deterministically.
* Covers summoning, deck rules, field limits, battle, fusion/ritual, victory, turn structure, chains, Spell Speeds, traps, card types and positions.
* GBA-specific answers (20-card Fusion Deck, 6-card hand limit) are marked `confidence: medium`; non-GBA rules are `high`.

### 2.6 `Exams/practicals.json`

Seven objectives, 200 points total:

| Objective | Event key | Target | Points |
| --- | --- | ---: | ---: |
| Battle | `monster_destroyed_by_battle` | 3 | 30 |
| Spells | `spell_activated` | 3 | 30 |
| Traps | `trap_activated` | 2 | 30 |
| Damage | `battle_damage_dealt` | 3000 | 30 |
| Fusion | `fusion_summoned` | 1 | 30 |
| Ritual | `ritual_summoned` | 1 | 25 |
| Special Summon | `special_summoned` | 2 | 25 |

Opponent `mimicry`, deck `mimicry_stall`, 8000 LP, 10 turns, 600 s, pass 120/200. Fail recovery is `fontaine` / `fontaine_nurse`. A01's `Canon/exams.json` confirms the seven themes and Mimicry; the thresholds are A07-authored (`canon_source` / `canon_note` in the file).

### 2.7 `Exams/scoring.json`

* 500 points: written 200 (10 Ã— 20), timed 100, practical 200.
* Pass mark 300; candidates 250/300 are recorded because A01 has not verified the GBA threshold.
* Grade bands S/A/B/C/F and retry/recovery fields are data-only; A02 maps pass/fail to title and dorm.
* `confidence: low` â€” exact weights/thresholds are not canon-verified. A01 confirms 500 points and the 250/300 pass-mark dispute (`canon_source` / `canon_note`).

### 2.8 `Exams/exams.json`

Twelve cycles, `EXAM_01`..`EXAM_12`. Each cycle links:

```json
{
  "exam_id": "EXAM_01",
  "month_index": 1,
  "written_set_id": "EXAM_01",
  "question_ids": ["Q001", "Q004", "..."],
  "timed_puzzle_id": "P001",
  "practical_objective_id": "battle",
  "practical_focus": "Destroy 3 monsters by battle",
  "scoring": { "max_points": 500, "pass_mark": 300,
               "sections": { "written": 200, "timed": 100, "practical": 200 } },
  "pass_mark": 300,
  "confidence": "low",
  "source": "..."
}
```

`Tools/puzzles/generate_exams.py` builds the file deterministically from the existing `questions.json` sets, `practicals.json` objectives and P001-P100 catalog. The timed puzzles rotate levels 1-5; the practical objective rotates through the seven themes. Exact GBA month-to-puzzle/objective assignments are not extracted, hence `confidence: low`. `UDAExamSubsystem::Reload` now loads this file and uses its authored question/timed-puzzle/practical ids instead of the old formula-only selection.

### 2.9 Runtime opponent decks and canon import

The 31 runtime files in `Content/Data/Opponents/decks/*.json` were rebuilt from the 37 reconciled canonical records in `Content/Data/Canon/decks.json`. The importer is `Tools/opponents/import_canon_decks.py`; the full before/after table and remaining canon gaps are in `Docs/Opponents_Deck_Report.md`.

Before the import, 30/36 constructed decks failed A04's static audit because the old shells contained banned `Monster Reborn` (385), `Imperial Order` (472), `Chaos Emperor Dragon` (886), and excess copies of limited `Jinzo` (348), `Reflect Bounder` (350), `MST` (436), `Injection Fairy Lily` (516), etc. After the import, 226 unresolved/variant slots were deterministically filled across the 31 runtime files and every runtime opponent deck and player/starter deck passes the audit:

```text
PASS: 31/31 runtime opponent decks legal (full name/copy/year-1 audit)
PASS: 36/36 constructed decks legal under A04 static audit
```

Canonical ids map to runtime ids as aliases, e.g. `alexis_year1 -> alexis_cyber`/`alexis_cyber_plus`, `syrus_year1 -> syrus_roids`/`syrus_roids_plus`, `zane_year1 -> zane_cyber`/`zane_cyber_end`. Runtime ids used by `events.json` are preserved (`chazz_ojama`, `damon_exodia`, etc.). The only known runtime adjustment is Jaden's fourth `Luster Dragon` name copy (canon 2x 663 + 2x 780) swapped to Elemental Hero Sparkman (1109) to satisfy the player-deck name-copy rule; this is recorded per-file as `runtime_adjustments`.

## 3. C++ APIs

### 3.1 `UDAOpponentSubsystem` (`DAOpponentSubsystem.h/.cpp`)

Game-instance subsystem. Loads `roster.json`, every `decks/*.json` and every `ai/*.json` on `Initialize`; `Reload(FString&)` is idempotent for tests. `Reload` also registers every loaded opponent deck with `UCardDatabaseSubsystem::RegisterDeck`, making the ids resolvable by `FDuelEngine::Start`.

Key calls:

```cpp
const FDAOpponentDef* FindOpponent(const FString& Id) const;
const FDAOpponentDeckDef* FindDeck(const FString& Id) const;
const FDAIProfileDef* FindAIProfile(const FString& Id) const;
bool GetDeckCards(const FString& Id, TArray<int32>& OutMain, TArray<int32>& OutExtra) const;

bool IsDuelistUnlocked(Id, PlayerTitle, PlayerDorm, const TSet<FString>& Flags, DayIndex, FString& OutReason) const;
bool CanDuelAtLocation(Id, Zone, Interior, Weekday, Period, FString& OutReason) const;
FString ResolveDeckFor(Id, const TMap<FString,int32>& Counters) const;

FDAOpponentDuelOutcome RecordDuelResult(Id, bool bPlayerWon, bool bDraw = false);
int32 GetWins(Id) const; int32 GetLosses(Id) const;

bool UnlockEmail(Id, ThreadId); bool MarkEmailRead(Id, ThreadId);
bool CanRequestDuel(Id, DayIndex, PlayerWins, FString& OutReason) const;
bool ConsumeDuelRequest(Id, DayIndex, PlayerWins, FString& OutReason);
void ResetDailyRequests(DayIndex);

const FDAOpponentRuntimeState& GetRuntimeState() const;
void SetRuntimeState(const FDAOpponentRuntimeState&);
```

`FDAOpponentRuntimeState` is deliberately save-friendly (`Wins`, `Losses`, `Draws`, `Emails`, `RequestsToday`, `RequestDay`). A02 should store it under the profile/save schema; this subsystem never writes disk.

`RecordDuelResult` increments counters and reports the highest evolution deck satisfied by win count. `ResolveDeckFor` accepts the profile's counter map (e.g. `wins_zane`) so A02 can own the canonical counters.

### 3.2 `UDAExamSubsystem` (`DAExamSubsystem.h/.cpp`)

Lifecycle:

```text
StartExam(month, seed)
  -> Written
  -> SubmitWrittenAnswer(questionId, answerIndex)*
  -> FinishWritten
  -> BeginTimed(puzzleId or empty for deterministic pick)
  -> SubmitTimedResult(solved, turns, seconds)
  -> BeginPractical
  -> RecordPracticalEvent(objectiveId, amount)*
  -> FinishPractical
  -> FinishExam(FDAExamResult&, FString&)
```

Scoring is computed from the JSON files, not hard-coded:

```text
written = min(correct * points_per_correct, 200)
timed   = solved ? 100 : 0
practical = sum(completed objective points), capped at 200
total   = written + timed + practical
pass    = total >= pass_mark
```

`FDAExamResult` contains `MonthIndex`, `WrittenCorrect/Points`, `bTimedSolved`, `TimedPoints`, `PracticalPoints`, `DPReward`, `TotalPoints`, `bPassed`, `Grade`, `TitleOutcome`, `DormOutcome`, completed/failed objective ids and `Flags` (`exam_passed`, `exam_failed`, `practical_passed`, `practical_failed`, `dropout_boy`). `DPReward` is 0 in current content because no canonical exam DP amount is extracted; A02/A03 own any actual DP grant. A09 renders the payload.

Data selectors: `GetCurrentQuestionIds`, `GetQuestion`, `GetCurrentQuestion`, `GetQuestionCount`, `GetPracticalProgress`, `GetPracticalObjectives`, `GetPassMark`, `PickTimedPuzzle(month)`, `GetCycles`, `GetCycle(month)`, `GetCycleCount`. `RecordPracticalStats(...)` is the seven-counter adapter for `FDuelResultStats`.

`Reload` now also reads `Exams/exams.json` into `FDAExamCycle` records. `StartExam(month)` uses the authored question set, `PickTimedPuzzle(month)` returns the authored `timed_puzzle_id` (falling back to the old formula only if the cycle data is absent), and `FinishExam` uses the cycle pass mark and optional `dp_reward`. `FDAExamResult::DPReward` is 0 in the current content because no canonical exam DP amount has been extracted; A02/A03 remain the authorities for any DP grant.

Exam/dorm/title outcomes are still recommendations in `FDAExamResult`; A02's `UDATitleSystem::ApplyExamOutcome` remains the state owner.

`GetPhase()` states: `None`, `Written`, `WrittenDone`, `Timed`, `TimedDone`, `Practical`, `PracticalDone`, `Finished`.

### 3.3 `FDAIDuelistAI` (`DADuelistAI.h/.cpp`)

A deterministic, engine-independent policy stub:

```cpp
void Configure(const FDAIProfileDef& Profile, int32 Seed);
void SetCardDatabase(const UCardDatabaseSubsystem* Database);
int32 ScoreCard(const FCardRecord& Card) const;
FDAAIDecision ChooseAction(const FDAAIDuelSnapshot& Snapshot) const;
bool ShouldAttack(...); bool ShouldSetTrap(...);
```

`FDAAIDuelSnapshot` is a minimal hand/field/LP/turn snapshot; `FDAAIDecision` is an abstract action (`NormalSummon`, `SetMonster`, `ActivateSpell`, `SetSpellTrap`, `Attack`, `DirectAttack`, `EndTurn`, etc.) with a card id and target. It does **not** call or mutate `FDuelEngine`.

## 4. Integration points

### 4.1 A04 â€” integration status and remaining hook

A04 now exposes the scenario and result contracts this lane needs:

* `DADuelRules.h`: `FDuelScenario`, `FDuelScenarioCard`, `FDuelResultStats`.
* `DADuelEngine.h`: `StartScenario(const FDuelScenario&, FString&)`, `GetActiveScenario()`, `CheckScenarioTimeout()`, `IsScenarioObjectiveComplete()`, `GetResultStats()`, `ValidateDeck(...)`, plus the existing `NormalSummon`/`ActivateSpell`/`Attack` calls.

**Puzzle mapping (ready, no engine edit needed):**

| A07 JSON | `FDuelScenario` |
| --- | --- |
| `id`, `title`, `objective` | `Id`, `Name`, `Objective` |
| `player.lp`, `opponent_state.lp` | `PlayerLp`, `OpponentLp` |
| `player.hand/deck/graveyard/extra` | `PlayerHand/Deck/Graveyard/Extra` |
| `opponent_state.hand/deck/graveyard/extra` | `OpponentHand/Deck/Graveyard/Extra` |
| `player.field[]` | `PlayerField` with `Zone = EDuelZone::Monster`, `bDefense = position == "defense"`, `bFaceDown = !face_up`, sequential `ZoneIndex` |
| `player.spell_traps[]` | `PlayerField` with `Zone = EDuelZone::SpellTrap`, `bFaceDown = !face_up` |
| `opponent_state.field/spell_traps` | `OpponentField` |
| `turn_limit`, `time_limit`, `seed` | `TurnLimit`, `TimeLimitSeconds`, `Seed` |
| `opponent` | lookup in `UDAOpponentSubsystem` for name/portrait; the fixed board comes from `opponent_state` |

The replay adapter should apply `solution` steps through the existing engine actions and fail the puzzle if any step is rejected. A04 owns `StartScenario`; A07 owns the JSON and solution data.

**Opponent deck handoff (resolved):** `FDuelEngine::Start` still resolves both sides through `UCardDatabaseSubsystem::FindDeck`, but the card database now has a narrow `RegisterDeck(const FStarterDeckDef&)` hook. `UDAOpponentSubsystem::Reload` registers all 31 runtime opponent decks after loading `Content/Data/Opponents/decks/*.json`, so story/UI deck ids from `events.json` and `roster.json` resolve without teaching A06's economy code about the Opponents directory.

The 31 runtime deck files are regenerated from A01's reconciled `Canon/decks.json` by:

```powershell
python Tools/opponents/import_canon_decks.py
python Tools/opponents/import_canon_decks.py --check
```

Known canon lists are copied exactly; unresolved/unknown slots are filled from the canon generic shell, then signature/theme cards, then a legal fallback pool. Each output records `canon_deck_id`, `aliases`, `generated_fill`, `generated_fill_sources`, `generated_fill_cards` and any `runtime_adjustments`. The audit mirrors A04's static deck audit (40-60 main, <=15 extra, known ids, Fusion-only Extra, Year 1 banned/limited, win condition); A06/validator name-copy limits are also checked for the 31 opponent decks.

**AI policy (still missing):**

```cpp
// Suggested on FDuelEngine:
void SetAiPolicy(TFunction<FDAAIDecision(const FDAAIDuelSnapshot&)> InPolicy);
// or a virtual interface:
// bool RequestAiDecision(const FDAAIDuelSnapshot&, FDAAIDecision&);
```

A07 supplies `FDAIDuelistAI::ChooseAction` / `ShouldAttack` / `ShouldSetTrap`; A04 owns legality/targeting and should ignore `None`/`EndTurn` gracefully. Until this exists, the engine's built-in `AiPlayMainPhase`/`AiPlayBattlePhase` remain the runtime behaviour and the profile data is inert.

**Practical counters (adapter ready):**

`FDuelResultStats` already exposes `BattleDamageDealt`, `MonstersDestroyedByBattle`, `FusionSummons`, `RitualSummons`, `SpecialSummons`, `SpellsActivated`, `TrapsActivated`, `Turns`, LP and draw/discard counters. A07 exposes:

```cpp
Exam->RecordPracticalStats(
    Stats.BattleDamageDealt, Stats.MonstersDestroyedByBattle,
    Stats.FusionSummons, Stats.RitualSummons, Stats.SpecialSummons,
    Stats.SpellsActivated, Stats.TrapsActivated);
```

Call it once at duel end with cumulative totals (or call `RecordPracticalEvent` with deltas during the duel, not both). For a live progress bar before duel end, A04/A09 can call `RecordPracticalEvent` from the corresponding visual/result events; the final `RecordPracticalStats` remains the authoritative end-of-duel check.

For a live practical scenario, `FDuelScenario` also has the matching required counters: `RequiredMonstersDestroyed` (battle), `RequiredSpellsActivated` (spells), `RequiredTrapsActivated` (traps), `RequiredBattleDamage` (damage), `RequiredFusionSummons` (fusion), `RequiredRitualSummons` (ritual) and `RequiredSpecialSummons` (special summon). Map them from `Exams/practicals.json`; the targets are already in that file.

**Result statistics** â€” `FDuelResultStats` is sufficient for DP and the seven practical counters; no new engine fields are required for this pass.

### 4.2 A09 â€” exam/UI payload

A09 should not parse JSON. It can use:

* `UDAExamSubsystem::GetQuestion` / `GetCurrentQuestionIds` for the written screen.
* `GetCurrentQuestionIndex` / `GetAnsweredCount` for progress.
* `GetPracticalProgress()` for objective rows (label, progress, target, awarded points, complete).
* `GetPhase()` for section transitions.
* `GetResult()` and `FinishExam()` for the breakdown screen.
* `UDAOpponentSubsystem::GetDuelistsByRank()`, `FindOpponent`, `FindDeck`, `FindAIProfile` for the PDA/duel-request list.
* `FDAExamResult::Flags` for title/dorm messages (A02 remains the authority).

No UI/UMG assets were added.

### 4.3 A02 â€” save/profile fields

Add to the save schema (via A02, not this lane):

* `FDAOpponentRuntimeState` â€” wins/losses/draws, email read/unread state, daily request counters.
* Exam history: month, total, written correct, timed solved, practical points, pass/fail, grade.
* Exam retry counters and `exam_exempt` flag.
* Current title/dorm (already A02-owned) â€” `FDAExamResult::TitleOutcome`/`DormOutcome` are recommendations only.

### 4.4 A05 â€” effect/fusion gaps exposed by the decks

A05's current `fusions.json` contains 76 recipes and now covers every Extra Deck card used by the 31 roster decks: Steam Gyroid (1155), UFOroid Fighter (1156), Cyber Twin Dragon (1157), Cyber End Dragon (1158), Ojama King (1018), Flame Wingman (1129), Thunder Giant (1130), Shining Flare Wingman (1200), Meteor B. Dragon (319) and F.G.D. (722). The validator reports `Extra Deck cards without a fusions.json recipe: 0`.

The remaining A05 gap is **effect coverage**, not recipe coverage. Decks include cards outside the current 137-card tier (Toon, Ojama Delta Hurricane, Exodia win check, Cyber Dragon's summon condition, etc.). They are legal to load; A05's coverage manifest should mark them `unsupported` until scripted, and story/exam duels should not require those effects before Tier 2 is complete.

### 4.5 A06 â€” deck validation

`Tools/puzzles/validate.py` is the data-side validator. A06's `DADeckLogic` should remain the runtime validator; it can read the same `FDAOpponentDeckDef` and reuse the copy/name rules. The validator currently checks 40â€“60 main, extra fusion-only, â‰¤3 by id/name.

### 4.6 A08 â€” interiors

Roster schedules use proposed interior ids such as `academy_arena`, `academy_classroom`, `academy_exam_room`, `academy_office`, `academy_shop`, `slifer_common`, `slifer_banner_room`, `ra_common`, `obelisk_common`, `obelisk_girls_common`, `abandoned_hall`, `gym_main`. A08 must either create these ids or publish a mapping; `CanDuelAtLocation` treats an empty interior schedule as â€œany interior in that zoneâ€.

### 4.7 A03 â€” story flags

Provisional flags used by the roster/AI data: `met_<duelist>`, `event_goblin_king`, `event_fossil`, `event_shadow_game`, `exam_day`, `walk_home_<duelist>`, `wins_<duelist>`. A03 should confirm or rename them; the loader treats them as opaque strings.

## 5. Canon gaps and confidence

| Item | Confidence | Gap / action |
| --- | --- | --- |
| Jaden deck | high | Existing game3d/GBA starter list; one illegal duplicate-name copy swapped in the roster file. |
| Cyber Dragon / Ancient Gear / Amazoness / Ojama / Vehicroid card availability | high | Cards 1111â€“1158, 639/641/781/1199, 835/851/852/871/1018 are in the DB. |
| Exact GBA deck lists for 24 duelists | low/medium | Reconstructed from archetype + card pool; A01's signature/gift cards are merged into roster metadata, but A01 confirms full deck lists are not published. |
| 20 ranked + 5 event/exam opponents | medium | Names/roles from the brief and GBA outline; exact ranks/schedules are A07-authored. |
| 100 puzzles | low for setup, high for canon solution list | P001â€“P100 present, levels 1â€“5 Ã—20. P001â€“P020 are authored fallbacks; P021â€“P100 are generated templates. A01's canonical solution is attached; A01 has no fixed-board setup. |
| Exam pass mark (250 vs 300) | low | Recorded both candidates; `scoring.json` and all 12 cycles use 300 for now. |
| Exam weights (200/100/200) | low | Authored split; exact GBA weights unknown. |
| Written question bank | medium | Starter bank authored from 2006 rules; GBA-specific answers marked medium. |
| Practical thresholds (3/3/2/3000/1/1/2) | low | Authored to make the seven objectives achievable in 10 turns. |
| Banned/limited list | unknown | A01/A06 now ship a banned list, but this validator checks size/copies only; runtime deck legality remains A06's `DADeckLogic`. |
| Event dates/conditions | unknown | Roster uses generic schedules; A03 owns the actual event calendar. |
| Fusion recipes for GX-era cards | high | A05's 76-recipe table covers every Extra Deck card in the roster; effect coverage is tracked separately. |
| Ante/gift/email text | low | Structural data only; exact GBA content not extracted. |

## 6. Validation

Run:

```powershell
python Tools/puzzles/validate.py --report Docs/Opponents_Validation_Report.md
python Tools/opponents/import_canon_decks.py --check
```

It checks:

* card ids and 1,200-card count;
* 40â€“60 main, â‰¤3 copies by id/name, fusion-only extra;
* roster references, AI profile references, evolution decks, schedule weekdays/periods, ante/gift card ids;
* puzzle files P001â€“P100, 20 per level, card references, zones, solution/action presence, solution cards present in the fixed setup, time/turn limits, rewards;
* deterministic replay of the 80 generated template puzzles (summon/tribute levels, equips, fusion/ritual, burn, piercing, Mirror Force + Seven Tools);
* 30 questions, 4 options, valid answers, 12 sets Ã— 10 unique ids, 7 practicals, 500-point scoring;
* 12 exam cycles: month 1â€“12, written set, 10 question ids, timed puzzle id, practical objective id, 500-point section sum and pass mark;
* 31 runtime opponent decks against the Year 1 banlist, 40-60 main, <=15 extra, known ids, Fusion-only Extra, copy/name limits and roster/event references (`Tools/opponents/import_canon_decks.py --check`).

Current result: `validate.py` **PASS**, 141 checks, 0 failures, 1 warning (duplicate `Luster Dragon` name in the baseline card DB); deck audit **PASS**, 31/31 runtime opponent decks and 36/36 constructed decks under A04 rules.

## 7. Blockers / next pass

1. **A04 AI policy hook** â€” the scenario/result APIs are present, but policy injection is not. Without it the 27 AI profiles remain data-only and 1,000-duel self-play cannot exercise them. Suggested signatures are in Â§4.1.
2. **Opponent deck handoff** â€” resolved for A07: `UDAOpponentSubsystem::Reload` registers the 31 runtime decks through `UCardDatabaseSubsystem::RegisterDeck`, so `FDuelEngine::Start` resolves them. Remaining canon-unknown fills are tracked in `Docs/Opponents_Deck_Report.md`.
3. **A04 puzzle replay adapter** â€” resolved for A07: `DAPuzzleRuntime` loads the JSON into `FDuelScenario` and replays the authored line through `FDuelEngine` (`-DAPuzzleSelfTest`, `da.PuzzleSelfTest`). The remaining gap is canon board fidelity, not the adapter.
4. **A05 effect coverage** â€” all deck Extra Deck recipes now exist; the remaining A05 work is scripting the non-Tier-1 card effects used by archetype decks (Toon, Ojama, Exodia, Cyber Dragon, etc.).
5. **A01 canon extraction** â€” exact GBA deck lists, fixed puzzle boards, exam weights/pass mark, banned list, gifts/emails. A01 solution metadata is attached, but boards remain port-authored.
6. **A02 save schema** â€” fold `FDAOpponentRuntimeState` and exam history into the versioned save; this pass keeps them transient.
7. **A08 interior ids** â€” reconcile the proposed schedule interiors with the actual interior cells.
8. **Engine replay** â€” resolved for A07: `-DAPuzzleSelfTest` replays all 100 authored lines in-engine; `-DAExamSelfTest` drives all 12 cycles through `UDAExamSubsystem`. See `Docs/Puzzles/PUZZLE_ENGINE_TESTS.md`.
9. **Canonical puzzle boards** â€” A01 has solution steps but no fixed setups; replace the P001â€“P100 authored boards/time limits/rewards when A01/A04 publish the original scenario data.
10. **AI self-play** â€” 1,000 seeded duels and per-profile behaviour tests, once A04's AI hook exists.
11. **A06 max-extra coordination** â€” shared rules data is now `max_extra: 15` and `DADeckLogic` reads it, but A06's `Tools/economy/sync_canon.py` still writes 20 and `DAEconomyTests.cpp` still asserts 20-card Extra Deck legality. Those A06-owned files must be updated before the next sync/test gate. `Data/decks.json` `jaden` also has four cards named `Luster Dragon`; the runtime opponent copy is normalised to three, but the A06 player deck data still needs the same name-cap cleanup.

## 8. Engine self-tests (A07 Gate 3)

Two headless suites prove the authored content through the real engine:

```text
-DAPuzzleSelfTest       all 100 puzzles load, start, verify seed/turn/time limits
                        and the authored board, then replay every solution step to
                        a player win.
-DAExamSelfTest         all 12 cycles: 10/10 written + authored timed puzzle solve
                        + seven practical objectives -> 500/S, and a 6/10 failing
                        mix -> 120/F/Dropout Boy; includes retry, month 12->1
                        rollover, invalid-month and partial-pass (330/C) checks.
-DAPuzzleExamSelfTest   both suites in one process; prints
                        "A07SelfTest: BOTH SUITES PASS".
```

Console equivalents are `da.PuzzleSelfTest`, `da.ExamSelfTest` and
`da.PuzzleExamSelfTest`. The suites use a transient `UDAExamSubsystem` and never
touch UI/save/profile state.

Expected stable markers:

```text
PuzzleSelfTest: 102 passed, 0 failed. ALL PASS
ExamSelfTest: <N> passed, 0 failed. ALL PASS
A07SelfTest: BOTH SUITES PASS
```

A dedicated runner and the integration smoke flags are documented in
[`Docs/Puzzles/PUZZLE_ENGINE_TESTS.md`](Puzzles/PUZZLE_ENGINE_TESTS.md).
Current content changes made for engine replay: P015 Sets `Seven Tools of the
Bandit` instead of an Equip Spell (A04's `SetSpellTrap` only accepts Traps and
Quick-Play Spells), and P047 uses a Level 5 field body so A04's level-sorted
ritual tribute selection cannot consume it. Canon board/time-limit data and a
canonical exam DP amount remain A01 blockers.

