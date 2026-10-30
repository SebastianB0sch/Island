# Duel Academy GBA → DuelAcademyIsland — Port Masterplan

> **Status:** planning document, not yet dispatched.
> **Source of the original game:** `C:\dev\argh` (GBA ROM, ROM toolkit, Three.js reference, older UE5 donor).
> **Target game:** `C:\dev\GX` (`DuelAcademyIsland`, Unreal Engine 5.8, C++).
> **Goal:** port the complete single-player story and functionality of *Yu-Gi-Oh! GX: Duel Academy* (GBA) into the 3D island, not just the first Jaden duel.

---

## 0. How to read this plan

- **Sections 1–4** define the target, the source, the architecture and the shared contracts.
- **Section 5** introduces the ten subagents and their boundaries.
- **Section 6** is the execution order (waves and gates).
- **Section 7** is the test and acceptance matrix.
- **Section 8** is the risk register.
- **Section 9** lists the canon questions that must be answered before content is frozen.
- **Section 10** is the immediate dispatch order.
- **Appendix A** is the full feature inventory from the GBA game.
- **Appendix B** maps GBA locations onto the GX island.
- **Appendix C** contains data-contract examples.
- **Appendix D** lists concrete source leads (ROM tables, donor files, docs).
- The per-agent briefs live in [`Docs/AgentBriefs/`](AgentBriefs/).

The plan assumes the user wants **full single-player fidelity**: the 12-month school year, all story events, all exams and timed duels, the full card economy, and the King of Games ending. Platform-only GBA features (link cable battles/trading) are called out as adaptations, not silent omissions.

---

## 1. Mission and definition of done

### 1.1 Mission

Port the complete GBA campaign into `C:\dev\GX` as a native UE 5.8 experience:

1. A new student arrives at Duel Academy.
2. The player lives through a 12-month school year, October to September.
3. The player duels the full roster, earns DP, buys packs, builds decks, takes monthly exams, changes dorms, and triggers all 33+ story events.
4. The player reaches the King of Games ending, then can continue in a post-game state.

### 1.2 Definition of done

The port is done when **all** of the following are true:

- [ ] **New game → credits** is playable without debug commands or hand-edited data.
- [ ] The opening matches the original beats: Sheppard's speech, registration/name entry, Slifer dorm introduction, Banner's 3,000 DP grant, Syrus's tutorial, first free-roam day.
- [ ] The calendar runs for 12 in-game months with Sunday–Saturday weeks and AM/PM/Night periods.
- [ ] All 33 numbered story events (34 including the Valentine reversal) are implemented, reachable, testable and recorded in the traceability matrix.
- [ ] All 100 timed duels are implemented as fixed, solvable one-turn (or stated-turn-limit) puzzles.
- [ ] The monthly exam cycle works: written questions, timed puzzle, practical exam, scoring, pass/fail, title and dorm outcomes.
- [ ] All 12 permanent duelist titles and the temporary/special titles are implemented with canonical conditions.
- [ ] The full 20+ duelist roster is present with canonical decks, deck evolution, schedules, dorm restrictions and email/duel requests.
- [ ] All 48 booster packs are purchasable/unlockable with canonical pools, prices and odds; all 1,200 cards are obtainable.
- [ ] All 1,200 cards have data, artwork fallback, fusion/ritual handling, and a rules implementation or an explicit, tested classification.
- [ ] Every card that can appear in a story duel, opponent deck, puzzle, pack or exam is fully supported by the rules engine.
- [ ] Deck construction works: 40–60 main deck, 20-card Fusion/Extra Deck, copy limits, banned/limited list, deck copy/erase, sorting/filtering.
- [ ] The PDA works: map, calendar, deck, mail, save, options, records, limitation list.
- [ ] Save/load works at any point, with 3 slots plus autosave, versioning and migration.
- [ ] All story locations are reachable; interiors exist for every location that has a scene.
- [ ] All named speakers have portraits/expressions or a deliberate fallback.
- [ ] The 12-month automated simulation completes with no softlocks, no missing events and no invalid decks.
- [ ] `1000` seeded AI-vs-AI duels complete with no stalls; all 100 puzzles pass their scripted solution; save fuzz passes.
- [ ] The project builds and packages from a clean checkout with the documented data-generation steps.
- [ ] No ROM, save file, emulator, ripped Konami art/audio or other non-redistributable asset is committed.
- [ ] `Docs/PORT_STATUS.md`, the traceability matrix and the player-facing controls/credits are up to date.

### 1.3 Explicit scope adaptations

These are the only intentional deviations from a 1:1 GBA port. Everything else should be faithful.

| GBA feature | Port decision |
| --- | --- |
| 2D map screen / menu navigation | Replaced by the 3D island, PDA and fast travel. The same destinations, schedules and restrictions remain. |
| GBA link cable battles/trades | Out of scope for the first release. Add offline trade/password equivalents if time allows. |
| Original sampled music/SFX | Do not rip. Reuse the project's synthesized audio and add original procedural cues. |
| GBA screen layout and fonts | Replaced by the project's Canvas HUD, with the same information architecture. |
| Original save file (`.sav`) | Native UE save slots are the source of truth. An optional importer can read the original save with `romhack/save_crypto.py` as a post-release tool. |
| 2D portraits | Reuse the project's portrait/cast pipeline; add expressions/fallbacks for every speaker. |

---

## 2. What exists today

### 2.1 Target: `C:\dev\GX`

**Engine/project**

- UE 5.8 C++ project `DuelAcademyIsland` (`DuelAcademyIsland/DuelAcademyIsland.uproject`).
- Code-only HUD (Canvas), no Blueprint graph required.
- Procedural island: 3 km × 3 km, 17 named zones, day/night cycle, ocean/lake swimming, volcano, harbor, dorms, gym, abandoned dorm, hot springs, lighthouse.
- Anime cast built from VRoid samples, with uniforms/hair and a generic student fallback.
- Editor Python pipeline in `Tools/` and `DuelAcademyIsland/Content/Python/`.

**Duel**

- 1,200-card database (`Content/Data/cards.json`).
- 4 deck lists (`decks.json`): Fire, Water, Wind starters + Jaden.
- 5 fusion recipes (`fusions.json`).
- Native `FDuelEngine` with 137 cards covered by name-specific handlers.
- Canvas duel board, hand/field/piles, AI, result/rematch, card art, portraits, expression cut-ins, visual event feed.
- Simplified rules: no chain-building UI, no per-effect target prompts, no banned list, no coin toss, no side deck, automatic defensive traps.

**World/economy gaps**

- Card shop sells 32 original fan-made cards, not the 1,200-card GBA pool.
- Collection is a `TSet` on the player pawn; no inventory/save.
- No calendar, DP, titles, dorm promotion, exams, story flags, emails, schedules or save/load.
- No interiors for story locations.
- NPCs are the named cast (Jaden, Syrus, Chumley, Bastion, Chazz, Zane, Alexis, Jasmine, Mindy, Crowler) plus generic students with fixed lines; no data-driven roster/schedules.
- `ADAIslandManager` tracks a simple `Day` and clock, not the GBA school calendar.

**Important:** the target working tree currently contains substantial uncommitted work (duel engine, data, cast, HUD changes). **Do not let subagents start from a dirty tree.** See §10.

### 2.2 Source: `C:\dev\argh`

- **ROM toolkit** (`decompress_rom.py`, `romhack/`): card extraction/reinjection, portraits/faces, save crypto, compressed-block research.
- **Three.js reference** (`game3d/`): 1,200-card database, canonical starter deck lists, Jaden deck, a 22-test headless duel engine and duel UI. It is the behavioural reference for rules.
- **Older UE5 donor** (`ue5/`): native duel engine with 137-card effect coverage, three-storey Slifer dorm interior, dialogue NPCs, quest state, card/deck viewer, portraits/expressions, procedural audio, Fab pipeline. Reuse **concepts and layouts**, not binaries, and adapt to GX coordinates/architecture.
- **Art direction** (`art/`, `docs/art/`, `docs/audio/`): style tokens, world layout, asset catalog, audio guide.
- The `argh` repo has **no commits yet** (files are staged). Treat it as read-only reference.

### 2.3 Original GBA game: the feature baseline

| System | What the original does |
| --- | --- |
| Calendar | 12 months (October–September), Sunday–Saturday, AM/PM/Night. First playable day is Saturday, October 7. Exams monthly on Friday. |
| Story | 33 numbered events (34 with 28.2), following the first anime season. Opening: Sheppard's speech, registration, Slifer dorm, Banner's 3,000 DP, Syrus tutorial. Ending: King of Games. |
| Dorms | Slifer Red, Ra Yellow, Obelisk Blue. Dorm changes through exams/events; each dorm has different rooms, cafeteria, NPCs and headmaster. |
| Titles | 12 permanent titles from Dropout Boy to King of Games, plus temporary Story/Event titles. Conditions combine wins, timed clears, written-exam percentage and card collection. |
| DP | Win rewards: 100 base + 1 per 100 LP lost + 1 per 100 battle damage + 50 per battle-destroyed monster; bonuses for Exodia/deck-out/Final Countdown/Destiny Board; turn-count multipliers; event rewards. 3,000 starting DP. |
| Duels | 1,200 cards, 8,000 LP, 40–60 main deck, 20-card Fusion Deck, 3-copy limit, banned/limited list, chain/target/timing prompts, ante duels, coin toss, surrender, activation-timing settings. |
| Opponents | 20 ranked duelists plus event-only opponents (Pharaoh, Topher, Conklin, Mimicry, Shadow Duelist/Titan). Each has a canonical deck and some evolve after wins. |
| Shop | 48 booster packs across Basic/Medium/Spell & Trap/Expert/Special/Attribute/Type categories, with prices and unlock schedules. Dorothy's Gift event pack. |
| Card Trunk | 1,200-card collection, card list/detail, deck construction, deck copy/erase, sorting/filtering, limitation list, recipes. |
| Exams | Written (10 questions), timed duel (one of 100 puzzles), practical (7 possible objectives vs Mimicry). Scored out of 500; pass threshold around 250–300 (verify with A01). Fail → Dropout Boy; recovery duel vs Fonda Fontaine. Exemptions from some story events. |
| Timed duels | 100 fixed puzzles in 5 levels (20 each), each with a specific hand/field and a one-turn solution, time limit and retries. |
| PDA | Map, Calendar, Edit Deck, Send Mail, Save, Options, Records, Limitation, Link/Trade. Email contacts unlock after meeting; can request duels. |
| Story events | 33 events with date/weekday/period/location/title/dorm/win-count conditions; choices; card/DP/pack rewards; some event-only duels and timed duels. |
| Social | Walk-home scenes, dorm headmaster gifts (Christmas), New Year visits, Valentine chocolate event, Chumley room event, Dorothy truck event, Titan/Shadow Game, Gerard quiz, Blair reveal, etc. |
| Post-game | King of Games title, name change, continued play. |

**Critical source-data gap:** the ROM string pools at `0x146C000+` are plain ASCII and contain the UI/name/format strings (verified). Story dialogue/scene scripts have not yet been located/decoded. A01's first job is to find them; if blocked, the fallback is the Yugipedia event guide plus original dialogue written for this port. Do not let this block systems work.

---

## 3. Porting principles and non-negotiables

1. **Data-driven content, C++ systems.** Story events, dialogue, schedules, packs, decks, puzzles, exams and effects live in validated JSON, not in monolithic C++ switches.
2. **One writer per file.** Every file has an owner in §4.6. Cross-lane changes go through A10 and a contract note.
3. **Keep the existing duel green.** The current 137-card behaviour is the regression baseline. Refactor behind tests; never break the Jaden duel while adding content.
4. **No manual level edits.** The island is generated by `Tools/` + editor Python. Change the generator, not the `.umap`.
5. **No Blueprints or binary UI assets.** Continue the project's code-only Canvas HUD approach. This keeps diffs reviewable and packaging simple.
6. **Preserve original IDs.** Card IDs stay 1–1200; duelist/pack/event/puzzle IDs are stable slugs. Traceability is mandatory.
7. **Determinism.** Duel RNG, pack RNG, exam selection and puzzle validation must accept a seed and be reproducible in tests.
8. **Save early, save versioned.** Every progression field is in the save schema from day one; add migrations, not ad-hoc flags.
9. **Local-only assets stay local.** ROM, save, emulator, ripped card art/portraits/audio and exact extracted story text must not be committed. See §7.5.
10. **Adapt, don't flatten.** The 3D island is the point. Use interiors, fast travel, schedules and scene anchors to preserve the GBA's places and beats.
11. **No silent omissions.** If a card, event, pack or mechanic cannot be completed, it gets an explicit `unsupported` record and a release blocker; it does not quietly disappear.

---

## 4. Target architecture

### 4.1 Runtime service map

```text
GameInstance
├─ UDACanonSubsystem          immutable data: cards, packs, decks, opponents, events, puzzles, exams
├─ UDAProfileSubsystem        player identity, dorm, title, DP, counters, flags, inventory, decks, emails
├─ UDACalendarSubsystem       year/month/day/weekday/period, advance, exam days, events
├─ UDASaveSubsystem           slots, autosave, JSON payload, versioning, migration
├─ UDAStorySubsystem          event graph, conditions, scene queue, outcomes
├─ UDAScheduleSubsystem       NPC schedule resolution, spawn/despawn/teleport requests
├─ UDAInventorySubsystem      card counts, pack opening, deck validation, collection
├─ UDAShopSubsystem           pack catalogue, prices, unlocks, purchases
├─ UDAExamSubsystem           written/timed/practical exam lifecycle and scoring
├─ UDAOpponentSubsystem       roster, deck evolution, email/duel requests, AI profiles
├─ UDADuelService             wraps FDuelEngine; normal/puzzle/exam/ante modes; results
└─ UDAUIController/HUD        screens, dialogue, PDA, shop, deck editor, exam, results
World
├─ ADAIslandManager           sky/time-of-day; reads calendar
├─ ADALocationVolume          zones / fast travel
├─ ADAInteriorPortal          door → interior cell
├─ ADASceneAnchor             camera/NPC marks for scenes
├─ ADANpcSpawnPoint           schedule spawn points
└─ ADAStudentNPC              data-driven NPC actor
```

### 4.2 Ownership and dependency graph

```text
A01 Canon ─────────┬──────────────► A03 Story
                   ├──────────────► A06 Economy
                   └──────────────► A07 Duelists/Exams/Puzzles

A02 Profile/Calendar/Save ────────► A03, A06, A07, A09

A04 Duel Rules ───► A05 Effects ──► A07

A08 World/Interiors ──────────────► A03 (anchors), A09 (cutscenes)
A09 UI/UX ────────────────────────► A03 (dialogue), A06 (screens), A07 (exams)

A10 Integration ──► all lanes (contracts, merges, tests, release)
```

### 4.3 Story scene contract

A03 must not draw UI or move actors directly. It emits a queue of commands consumed by A09/A08:

```cpp
enum class EStoryCommand : uint8 {
    Dialogue, Choice, Camera, MoveNpc, Fade, Wait, Banner,
    PlaySfx, Music, Duel, Reward, SetFlag, End
};

struct FStoryCommand {
    EStoryCommand Type;
    FString SpeakerId;      // "jaden"
    FString Portrait;       // "jaden_happy"
    FString TextKey;        // localization/trace key
    TArray<FString> Args;   // choices, anchors, ids
    float Duration = 0.f;
    bool bSkippable = true;
};
```

- Dialogue/choice/portrait execution: A09.
- Camera anchors, NPC blocking, fades/letterbox: A08 + A09.
- Duel: A04/A07, result returned to A03.
- Rewards/flags: A02/A06.
- Story command queues are serializable, so save/load mid-scene is possible.

### 4.4 Duel request/result contract

```cpp
struct FDuelRequest {
    FString OpponentId;       // "jaden"
    FString OpponentDeckId;   // "jaden_year1"
    FString PlayerDeckId;     // inventory deck id
    FString Mode;             // "story" | "free" | "exam_timed" | "exam_practical" | "puzzle" | "ante"
    FString PuzzleId;         // optional
    bool bAnte = false;
    int32 Seed = 0;
};

struct FDuelResult {
    FString OpponentId;
    FString Mode;
    bool bPlayerWon = false;
    bool bDraw = false;
    int32 Turns = 0;
    int32 PlayerLp = 0;
    int32 OpponentLp = 0;
    int32 BattleDamageDealt = 0;
    int32 MonstersDestroyedByBattle = 0;
    int32 DpEarned = 0;
    TArray<FString> FlagsSet;
};
```

A04 owns the engine and result statistics; A02 converts the result to DP/title/counters; A03 consumes story outcomes; A07 consumes exam/puzzle results.

### 4.5 Canonical data files

All runtime data lives under `DuelAcademyIsland/Content/Data/` and is staged by `DefaultGame.ini`.

| File/dir | Owner | Purpose |
| --- | --- | --- |
| `cards.json` | A01 baseline, A06 loader | 1,200-card database (existing). |
| `Canon/` | A01 | Extraction manifests, traceability, immutable baseline copies. |
| `Effects/` | A05 | Per-card effect scripts + coverage manifest. |
| `fusions.json`, `rituals.json` | A05 | Full fusion/ritual recipe tables. |
| `decks.json`, `Decks/` | A06 | Starter decks, opponent decks, player deck slots. |
| `Shop/` | A06 | 48 pack definitions, prices, pools, odds, unlocks. |
| `Opponents/` | A07 | Roster, decks, AI profiles, evolution, schedules. |
| `Puzzles/` | A07 | 100 timed-duel scenarios and solutions. |
| `Exams/` | A07 | Written question bank, practical definitions, scoring. |
| `Story/` | A03 | Events, dialogue, choices, schedules, emails. |
| `World/` | A08 | Interior portals, anchors, spawn points, location map. |
| `UI/` | A09 | Screen layouts, localization keys, portrait fallbacks. |
| `Profile/` | A02 | Titles, calendar defaults, settings defaults, save schema. |
| `Integration/` | A10 | Test fixtures, golden saves, validation reports. |

**Rule:** A01's `Canon/` files are read-only after handoff. If a downstream lane finds a canon error, it files a correction request; A01 updates the baseline and the traceability matrix. Do not fork canon silently.

### 4.6 File ownership matrix

**Sole owner (only that agent edits):**

| Path | Owner |
| --- | --- |
| `Tools/canon/**`, `Docs/Canon/**`, `Content/Data/Canon/**` | A01 |
| `.../DASaveGame.*`, `DAProfileSubsystem.*`, `DACalendarSubsystem.*`, `DATitleSystem.*`, `DASettings.*`, `Content/Data/Profile/**` | A02 |
| `.../DAStorySubsystem.*`, `DAEventGraph.*`, `Content/Data/Story/**`, `Docs/Story/**` | A03 |
| `.../DADuelEngine.*`, `DADuelRules.*`, `DADuelChain.*`, `DAEffectRuntime.*`, `DADuelTests.*` | A04 |
| `Content/Data/Effects/**`, `fusions.json`, `rituals.json`, `Tools/effects/**` | A05 |
| `.../DAInventorySubsystem.*`, `DAShopSubsystem.*`, `DADeckLogic.*`, `Content/Data/Shop/**`, `Content/Data/Decks/**`, `DACardDatabase.*`, `DACardRecords.*` | A06 |
| `.../DAOpponentSubsystem.*`, `DADuelistAI.*`, `DAExamSubsystem.*`, `Content/Data/Opponents/**`, `Puzzles/**`, `Exams/**`, `Tools/puzzles/**` | A07 |
| `Tools/dai/assets/**`, `Tools/dai/layout.py`, `Tools/dai/config.py`, `Content/Python/duel_academy/level.py`, `.../DAInterior*`, `DADoor*`, `DASceneAnchor*`, `DANpcSpawnPoint*`, `DANpcDirector*`, `DAWorldActors.*`, `DAStudentNPC.*`, `DAInteractable.*`, `Content/Data/World/**` | A08 |
| `.../DAHUD.*`, `DADuelUI.*`, `DADialogueUI.*`, `DAPDAUI.*`, `DAShopUI.*`, `DADeckUI.*`, `DAExamUI.*`, `DASaveUI.*`, `DACutscene.*`, `DACardArtSubsystem.*`, `DACharacterPortraitSubsystem.*`, `Content/Data/UI/**` | A09 |
| `Tools/validate/**`, `.github/workflows/**`, `Docs/PORT_STATUS.md`, `Content/Data/Integration/**`, build scripts | A10 |

**Shared files (change only through A10):**

`DAGameMode.*`, `DATypes.h`, `DAIslandSubsystem.*`, `DAStudentCharacter.*`, `DuelAcademyIsland.Build.cs`, `Config/*.ini`, `.uproject`, `DuelAcademyIsland.Target.cs`, `DuelAcademyIslandEditor.Target.cs`.

**Generated/never hand-edit:**

`DuelAcademyIsland/Content/DuelAcademy/**`, `Content/Collections/**`, `Content/Data/art/**`, `SourceAssets/**` (regenerate via `Tools/`).

### 4.7 Naming and ID conventions

| Entity | Format | Examples |
| --- | --- | --- |
| Card | integer 1–1200 | `1` = Blue-Eyes White Dragon |
| Duelist | lowercase slug | `jaden`, `syrus`, `crowler`, `shadow_duelist` |
| Deck | `<duelist>_<variant>` | `jaden_year1`, `chazz_ojama`, `zane_cyber` |
| Pack | lowercase snake case | `basic_1a`, `master_fusions`, `dorothys_gift` |
| Event | `E01` … `E33`, `E28b` | `E04a`, `E04b` |
| Puzzle | `P001` … `P100` | `P001` |
| Exam | `EXAM_<month_index>` | `EXAM_01` |
| Flag | snake_case | `registered`, `met_alexis`, `event_04_cleared` |
| Counter | snake_case | `wins_total`, `wins_jaden`, `timed_clears`, `written_correct` |
| Dialogue key | `<event>.<node>` | `E01.sheppard_01` |

### 4.8 Save schema (v1)

```json
{
  "version": 1,
  "slot": 1,
  "profile": {
    "name": "Alex",
    "dorm": "Slifer",
    "title": "Apprentice Duelist",
    "dp": 3000,
    "gender": "unspecified"
  },
  "calendar": { "year": 1, "month": 10, "day": 7, "period": "AM" },
  "flags": { "registered": true, "met_jaden": true },
  "counters": { "wins_total": 0, "wins_jaden": 0, "timed_clears": 0, "written_correct": 0 },
  "inventory": { "1": 3, "40": 2 },
  "decks": [
    { "id": "player_1", "name": "My Deck", "main": [1, 40], "extra": [319] }
  ],
  "events": { "E01": "complete", "E02": "available" },
  "exams": [ { "month": 1, "written": 7, "timed": true, "practical": 250, "result": "pass" } ],
  "emails": { "jaden": { "unlocked": true, "read": ["jaden_01"] } },
  "settings": { "animation_speed": 2, "confirm_activation": true }
}
```

- A02 owns the schema and migrations.
- Every new subsystem adds fields through A02, never by writing ad-hoc keys into the save.
- Autosave on day change, exam result, story event completion, pack purchase and duel result.

---

## 5. The ten subagents

> Detailed, copy-pasteable briefs are in `Docs/AgentBriefs/`.

| ID | Name | Mission | Primary dependencies |
| --- | --- | --- | --- |
| **A01** | **Source Scribe** — canon extraction & archaeology | Extract the GBA's cards, text, events, packs, decks, puzzles, exams and flags; publish a traceable canon dataset. | ROM/toolkit, guides, donor repos |
| **A02** | **Registrar** — profile, calendar, save, progression | Own player identity, date/time, DP, titles, counters, flags, save slots and settings. | A01 (thresholds/dates) |
| **A03** | **Director** — story campaign & schedules | Implement the event graph, 33+ story events, dialogue, choices, NPC schedules and story outcomes. | A01, A02, A08, A09 |
| **A04** | **Rules Architect** — duel rules core | Complete the 2006 rules engine: chains, targeting, timing, banned list, ante, puzzle modes, deterministic tests. | A05, A07 |
| **A05** | **Cardwright** — card effects & fusion/ritual data | Build the data-driven effect layer and cover all 1,200 cards, fusion and ritual recipes. | A04 |
| **A06** | **Quartermaster** — economy, shop, inventory, deck builder | Implement 48 packs, DP purchases, card trunk, deck construction/validation and player decks. | A01, A02, A09 |
| **A07** | **Challenger** — duelists, AI, exams, 100 puzzles | Implement the full roster, canonical decks, AI profiles, 100 timed puzzles and exam lifecycle. | A01, A02, A04, A05 |
| **A08** | **Architect** — world, interiors, spatial story integration | Add enterable story locations, portals, anchors, NPC spawn points and schedule-driven placement. | A01, A03, A09 |
| **A09** | **Interface** — UI/UX, dialogue, PDA, presentation | Build every player-facing screen, dialogue system, cutscenes, shop/deck/exam UI and feedback. | A02, A03, A06, A07 |
| **A10** | **Gatekeeper** — integration, QA, release | Freeze contracts, merge lanes, build the test harness, run the 12-month simulation, package and audit. | All |

### 5.1 A01 — Source Scribe (canon extraction)

**Mission:** turn the GBA ROM and public guides into a complete, machine-readable, traceable canon dataset.

**Must produce**

- `Docs/Canon/SOURCE_MAP.md`: ROM offsets, text encoding/control codes, table layouts, save layout, unresolved areas.
- `Tools/canon/*.py`: idempotent extractors for cards, text, events, packs, decks, puzzles, exams, titles, calendar.
- `Content/Data/Canon/*.json`: baseline cards, packs, decks, opponents, puzzles, exams, events, dialogue keys, calendar, titles, banned list.
- `Docs/Canon/TRACEABILITY.md`: every runtime ID mapped to a ROM offset/guide URL/test.
- `Docs/Canon/GAPS.md`: missing/ambiguous data and fallback decisions.

**Key source leads**

- Card tables: `0xF243CC` (stats), `0xF25690` (names), `0xF2A68C` (name offsets), `0xF2B950` (descriptions), `0xF58294` (desc offsets).
- UI/name strings: plain ASCII around `0x146C000`–`0x146D000`; full-name pool `0x146CB14`, short-name pool `0x146CC32`.
- Save crypto: `romhack/save_crypto.py`; save file `patched.sav`.
- Public canon: Yugipedia `Events`, `Opponents`, `Timed Duel List`, `Booster Pack List`, `Starter Decks`, `Banned List`.
- Donor implementations: `game3d/src/duel/engine.js`, `game3d/src/duel/decklists.js`, `ue5/Source/DuelAcademy/DuelEngine.*`.

**Do not:** edit runtime C++, UI, world or the target save schema.

**Acceptance:** all 1,200 cards match; 33+ events with conditions/rewards; 48 packs with pools/prices/unlocks; 20+ opponents with decks; 100 puzzles with solutions; 12 titles; calendar and exam rules; every datum has a trace ID. No ROM/ripped assets committed.

### 5.2 A02 — Registrar (profile, calendar, save, progression)

**Mission:** make the school year, the player and the save data real.

**Scope**

- `UDAProfileSubsystem`: name, dorm, title, DP, counters, flags, inventory handles, deck handles, email state.
- `UDACalendarSubsystem`: 12 months, weeks, AM/PM/Night, exam days, event date queries, day advance/sleep, fast-forward for tests.
- `UDATitleSystem`: 12 permanent titles + temporary titles, canonical thresholds, exam/dorm outcomes.
- `UDASaveSubsystem`: 3 slots + autosave, JSON payload, versioning/migration, atomic writes, corruption recovery, screenshot metadata.
- `UDASettings`: animation speed, activation timing, text speed, audio, controls, language keys.
- Debug/console API for the other agents: `SetDate`, `AwardDP`, `SetFlag`, `RecordDuelResult`, `ForceTitle`, `SaveNow`.

**Acceptance**

- 12-month calendar advances with correct weekdays/periods; exam Fridays identified.
- DP formula and turn multipliers match canon; unit tests for each branch.
- Title thresholds and dorm promotion match A01; tests for every title.
- Save round-trip is byte-stable for identical state; fuzz 10,000 random states; migration from v1→v2 test.
- No subsystem writes directly to disk; all through A02.

### 5.3 A03 — Director (story campaign & schedules)

**Mission:** deliver the complete GBA story as a data-driven event graph, with every scene, choice, schedule and outcome.

**Scope**

- `UDAStorySubsystem` + `FDAEventGraph`: event availability, priority, once/repeatable, prerequisites, triggers (date, weekday, period, location, talk, duel result, exam result, flag, counter, card ownership), scene queue, choices, rewards, failure/retry.
- 33+ events, including opening, Slifer/Ra/Obelisk arcs, festivals, Christmas, New Year, Valentine, Gerard quiz, Blair reveal, Titan/Shadow Game, Goblin King, Yugi's deck, 7th Deck, walk-home, Dorothy truck, Chumley room, King of Games.
- `Content/Data/Story/events.json`, `dialogue.json`, `schedules.json`, `emails.json`, `scenes/*.json`.
- NPC schedule data (who is where on which weekday/period, event overrides).
- Story-facing email content and choices.

**Acceptance**

- Event graph validator: all 33+ events reachable from a new game; no unreachable nodes; no cycles without exit; all conditions reference valid flags/counters.
- 12-month simulation reaches every event at least once under canonical conditions.
- Choices have deterministic outcomes; rewards granted exactly once.
- Save/load mid-scene restores the exact command queue.
- No event can softlock the player; every required duel has a retry/exit path.

### 5.4 A04 — Rules Architect (duel rules core)

**Mission:** turn the current 137-card friendly engine into a complete, tested 2006-era rules engine.

**Scope**

- Split `DADuelEngine.cpp` into rules/chain/effect/ai/test units.
- Chain building and spell speeds, priority, optional triggers, target selection, cost payment, damage step, attack replay, flip/continuous effects, lingering effects, End Phase timing.
- Activation timing settings (manual/automatic per card), trap timing, counter traps, quick-play from hand/set.
- Deck validation: 40–60 main, 20 extra, 3 copies, banned/limited list, ante, side deck if canon requires.
- Duel modes: normal, story, exam timed, exam practical, puzzle, ante; coin toss/go first-second; surrender; result statistics for DP.
- Deterministic seeded RNG, replay/record, AI policy interface, debug self-test.

**Acceptance**

- Existing 137-card regression suite passes unchanged.
- New rule tests: chain, targeting, damage step, priority, timing, banned list, ante, deck validation, puzzle setup.
- 1,000 seeded AI-vs-AI duels complete with no stalls.
- API/result contract in §4.4 is stable; A05/A07/A09 compile against it.

### 5.5 A05 — Cardwright (effects & fusion/ritual data)

**Mission:** make every one of the 1,200 cards behave correctly, via a data-driven effect layer.

**Scope**

- Work with A04 to define `DAEffectRuntime` primitives (draw, discard, destroy, banish, search, summon, position, ATK/DEF, negate, counters, etc.).
- `Content/Data/Effects/<card_id>.json` scripts with trigger/condition/cost/target/operation/duration.
- Batch conversion: 850 effect cards (410 Effect Monsters, 280 Spells, 160 Traps) + effect-bearing Fusions/Rituals.
- Full fusion/ritual recipe tables (76 Fusions, 22 Rituals; all materials and spell names).
- Coverage manifest: `scripted`, `vanilla`, `unsupported` with reason; audit tool.
- Tiering: Tier 0 = current 137; Tier 1 = vertical slice; Tier 2 = all story/opponent/puzzle/pack cards; Tier 3 = all 1,200.

**Acceptance**

- 100% of cards have a manifest entry.
- Every card that can be obtained or used in a duel is `scripted`; no `unsupported` card appears in a deck/pack/puzzle.
- Fusion/ritual tests for every recipe; no invalid materials.
- A05's scripts are validated by schema and by an in-engine effect self-test.

### 5.6 A06 — Quartermaster (economy, shop, inventory, deck builder)

**Mission:** make DP, packs, the card trunk and deck construction work like the GBA game.

**Scope**

- `UDAInventorySubsystem`: card counts, 3-copy limit, add/remove, collection stats, pack opening RNG, ante removal/return.
- `UDAShopSubsystem`: 48 packs, prices, unlock conditions (month/event/title), pools/odds, 5-card (verify) pack opening, Dorothy's Gift.
- `UDAProfileSubsystem` DP integration with A02 (purchases, rewards, refunds).
- `DADeckLogic`: 40–60 main, 20 extra, banned/limited, deck copy/erase, sorting/filtering, recipes, starter decks, opponent deck templates.
- `Content/Data/Shop/*`, `Content/Data/Decks/*`, `DACardDatabase.*`/`DACardRecords.*` loaders.

**Acceptance**

- All 1,200 cards obtainable only through valid packs/events; no pack references a missing card.
- Pack simulation matches canonical rarity/odds within tolerance; every pack has a price and unlock.
- Deck validation rejects illegal decks with the exact GBA-style message; 3-copy limit enforced.
- Inventory/deck/DP survive save/load; no negative DP; no duplication exploit.
- All 4 existing decks still load; new player decks work.

### 5.7 A07 — Challenger (duelists, AI, exams, 100 puzzles)

**Mission:** populate the school with the full roster, make them duel like themselves, and implement the exam/puzzle content.

**Scope**

- 20+ duelists + event-only opponents, canonical decks, deck evolution (Jinzo additions, Chazz Ojama, etc.), dorm restrictions, schedules/locations (data), email/duel requests, walk-home, ante.
- AI profiles: strategy per deck (beatdown, burn, stall, fusion, ritual, control), difficulty, puzzle solver/validator.
- 100 timed puzzles, 5 levels × 20, fixed hands/fields/graveyards, turn/time limits, solutions, retries.
- Exam lifecycle: written question bank, timed puzzle selection, practical objectives (Battle/Spells/Traps/Damage/Fusion/Ritual/Special Summon), Mimicry deck, 500-point scoring, pass/fail, retries, exemptions.
- `Content/Data/Opponents/*`, `Puzzles/*`, `Exams/*`, `Tools/puzzles/*`.

**Acceptance**

- Every opponent deck legal and uses supported cards.
- 100/100 puzzles validated by scripted solution and engine; no ambiguous solutions.
- Exam scoring reproducible; pass/fail and title/dorm outcomes match canon.
- AI self-play no stalls; each AI profile behaves distinctly in scripted scenarios.
- All event-required opponents/modes available.

### 5.8 A08 — Architect (world, interiors, spatial integration)

**Mission:** make every GBA location a real place in the 3D island, and give the story stages, doors and NPC marks.

**Scope**

- Location mapping (Appendix B): academy interiors (lobby, classroom, test room, arena, Crowler/Chancellor offices), Slifer/Ra/Obelisk dorm interiors (rooms, cafeterias, common rooms, headmaster rooms), gym, card shop, harbor, ocean/beach, volcano crater, girls' dorm front, abandoned dorm.
- `ADAInteriorPortal`: door trigger, fade, teleport to interior cell, return portal.
- Interior cells: collision, lighting, nav, props, signage, spawn points; reuse the procedural kit and donor layouts.
- `ADASceneAnchor`: camera marks for dialogue/cutscenes; `ADANpcSpawnPoint`; `DANpcDirector` for schedule-driven spawn/move/despawn.
- `Content/Data/World/*`, layout updates in `Tools/dai/layout.py`/`config.py`, editor build script updates.
- Map/fast-travel destinations and zone metadata.

**Acceptance**

- Every story location in Appendix B is reachable and enterable.
- No portal loops, no falling through floors, no nav dead zones; automated entry/exit tests.
- Every scene anchor referenced by A03 exists; missing anchors fail validation.
- Regenerating the island from `Tools/` produces the same layout plus interiors; no manual `.umap` edits.
- Performance budget respected (no interior load > 2 s; no permanent tick cost when empty).

### 5.9 A09 — Interface (UI/UX, dialogue, PDA, presentation)

**Mission:** make the port feel like a complete game: every screen, every line, every reward.

**Scope**

- Title/new game/continue, name entry, options, credits.
- HUD: clock/calendar, location banner, objective, DP, title, dorm, interaction prompt, toasts.
- Dialogue: typewriter, portraits/expressions, speaker names, choices, history/log, skip/auto.
- PDA: map/fast travel, calendar, deck, mail/contacts, save/load, options, records, limitation list.
- Shop: pack browse, prices, unlock reasons, pack-opening animation, card reveal, DP balance.
- Deck editor: collection, filters/sort, deck slots, add/remove, validation messages, recipes, copy/erase.
- Exam UI: written questions, timer, practical objective/progress, result breakdown.
- Story presentation: fades, letterbox, camera anchors, banners, music/SFX hooks; duel result/DP/title/dorm promotion screens.
- Controller/keyboard/mouse support; 1080p/4K legibility; screenshot/debug modes.

**Acceptance**

- Every screen reachable and closable with keyboard, gamepad and mouse; no modal deadlocks.
- No hardcoded story text; all strings come from A03/A01 keys with trace IDs.
- Save/load prompts and error states work.
- UI automation screenshots for every screen at 1920×1080 and 3840×2160.
- A09 consumes A02/A03/A06/A07 APIs; it does not implement gameplay rules.

### 5.10 A10 — Gatekeeper (integration, QA, release)

**Mission:** keep ten lanes shippable, prove the port with automated tests, and own the release.

**Scope**

- Baseline branch/worktrees, contract headers, merge order, API change log.
- Test harness: data validation, save fuzz, event reachability, 12-month simulation, 1000-duel self-test, 100-puzzle validation, pack odds, effect coverage, UI smoke, performance.
- CI, build scripts, packaging, save migration, crash/log triage.
- `Docs/PORT_STATUS.md`, `Docs/Contracts/*`, `Content/Data/Integration/*`.
- Legal/asset audit; no ROM/ripped assets; credits.
- Final playthrough and release checklist.

**Acceptance**

- One command runs the full validation suite; CI green.
- 12-month scripted playthrough completes; every gate in §7 passes.
- Packaged build launches, saves, loads, and plays without editor-only dependencies.
- No P0/P1 bugs; documented known issues.
- Release notes and legal audit signed off.

---

## 6. Execution plan

### Wave 0 — Baseline and contracts (A01, A10; all others read-only)

**Goal:** a clean, buildable baseline and frozen interfaces before parallel work.

1. A10 commits/stashes the current WIP on a baseline branch; verifies the project builds and the current Jaden duel self-test passes.
2. A10 creates the contract headers/schemas in §4.3–4.5 and the worktree/branch convention.
3. A01 starts the extraction spike: card verification, text/string map, event/pack/deck/puzzle tables, save layout.
4. A02/A04/A09 write short RFCs against the contracts (no implementation yet).
5. All agents read the target/donor code and write "what I will not touch" notes.

**Gate 0:** baseline builds; Jaden duel passes; contracts reviewed; no dirty-tree conflicts.

### Wave 1 — Vertical slice (A02, A03, A04, A06, A08, A09; A01/A10 support)

**Goal:** prove the whole stack with the opening hour.

- New game → name → Sheppard speech → registration → Slifer dorm → Banner's 3,000 DP → Syrus tutorial → first free-roam save.
- Slifer dorm interior + one academy room + one exterior scene anchor.
- Three starter decks, the Syrus tutorial duel, one free Jaden duel, one pack purchase, one exam screen stub, one save/load.
- PDA shell, dialogue system, DP/title HUD, card trunk basics.

**Gate 1:** a player can complete the opening, save, reload, buy a pack and win/lose the Jaden duel; A10's smoke test covers it.

### Wave 2 — Systems complete (A02–A09)

**Goal:** every system exists and is testable, even if content is partial.

- Full rules/chain/targeting; effect runtime + Tier 1 cards.
- Inventory/shop/deck editor; all 48 pack definitions stubbed.
- Exam lifecycle + first 20 puzzles.
- Event graph + first 10 events; schedule director; all story interiors roughed in.
- Full PDA/shop/deck/exam/dialogue UI.

**Gate 2:** systems integration test; 12-month fast-forward with placeholder events; 1000 AI duels; 20 puzzles; save fuzz; no P0 crashes.

### Wave 3 — Content fill (A01, A03, A05, A06, A07, A08; A09 polish; A10 test)

**Goal:** fill the game.

- All 33+ events and dialogue; all emails/walk-home/random events.
- All 100 puzzles; all 12 exam cycles; all 20+ opponents/decks/evolution.
- All 48 packs; all 1,200 cards obtainable; Tier 2 effects complete.
- All interiors and anchors.
- Tier 3 effects and remaining cards.

**Gate 3:** content complete by traceability matrix; no missing IDs; all story/pack/puzzle decks legal; 100/100 puzzles; 33+/33+ events; 48/48 packs.

### Wave 4 — Integration, balance, performance (A10 lead; all support)

**Goal:** make it a coherent game.

- 12-month playthrough; economy balance; AI difficulty; exam fairness; puzzle timing.
- Save migration, autosave, corruption recovery.
- Performance passes (interiors, UI, duels, 1,200-card load).
- UI/UX polish, controller/accessibility, localization keys.
- Bug fixing from the full matrix.

**Gate 4:** release-candidate criteria in §7.4 met; no P0/P1; performance budget met.

### Wave 5 — Release (A10 lead; all support)

- Package Windows build; verify data staging; clean-checkout build.
- Legal audit; credits; README/controls; known issues.
- Final playthrough and tag.

**Gate 5:** packaged build passes the release checklist; docs updated; tag created.

### Dispatch order

Do **not** start all ten implementation lanes at once. Recommended:

1. **A01 + A10** (extraction + baseline/contracts).
2. **A02 + A04 + A09** (profile/calendar/save, rules core, UI shell).
3. **A03 + A06 + A08** (story skeleton, economy, interiors).
4. **A05 + A07** (effects and exam/puzzle content) once A04's runtime contract is stable.
5. **A10** merges at every gate; all agents pause for gate reviews.

A01 and A10 can run for the entire program; A05 and A07 are the longest content lanes.

---

## 7. Test and acceptance matrix

### 7.1 Data validation (A10 owns; A01 supplies)

- IDs unique; cards 1–1200; every referenced card/deck/pack/puzzle/exam/event exists.
- Decks: 40–60 main, ≤20 extra, ≤3 copies, banned/limited legal.
- Packs: prices, unlocks, pools, odds; every card obtainable.
- Events: unique IDs, valid conditions/flags/counters, reachable, no dead ends.
- Puzzles: valid setup, solution exists, turn/time limit.
- Exams: 10 questions, valid puzzle, valid practical, 500-point scoring.
- Schedules: every NPC has a valid location/period; every anchor exists.
- Dialogue: every speaker has a portrait/fallback; every key exists.
- Effects: every card has a manifest entry; no unsupported card in a legal deck.

### 7.2 Automated tests

| Suite | What it proves | Owner |
| --- | --- | --- |
| `canon_validate` | Data integrity/traceability | A01/A10 |
| `profile_tests` | DP, titles, counters, flags, dorm | A02 |
| `calendar_tests` | 12 months, weekdays, periods, exam days | A02 |
| `save_tests` | Round-trip, fuzz, migration, corruption | A02/A10 |
| `story_tests` | Event conditions, reachability, rewards once | A03 |
| `duel_rules_tests` | Chains, targeting, timing, banned, ante | A04 |
| `effect_tests` | Per-card scripts, fusion/ritual | A05 |
| `economy_tests` | Pack odds, DP, inventory, deck legality | A06 |
| `opponent_tests` | Deck legality, AI profiles, evolution | A07 |
| `puzzle_tests` | 100/100 solutions, time/turn limits | A07 |
| `exam_tests` | Written/timed/practical scoring | A07 |
| `world_tests` | Portals, anchors, nav, collision | A08 |
| `ui_smoke` | Every screen opens/closes, no deadlocks | A09 |
| `playthrough` | Opening → 12 months → credits | A10 |
| `duel_selftest` | 1,000 seeded AI-vs-AI, no stalls | A04/A10 |
| `performance` | 60 fps, load/save budgets | A10 |

### 7.3 Manual/scripted playthrough checklist

- New game, name entry, opening scenes, registration, Slifer dorm, Banner 3,000 DP, Syrus tutorial.
- First free-roam save/load; sleep to next day; time-of-day NPC changes.
- Buy a pack; open it; build a legal deck; win/lose a duel; DP and title update.
- Take an exam: written, timed puzzle, practical; pass and fail paths; Dropout Boy recovery.
- Dorm promotion Slifer → Ra → Obelisk; dorm-specific rooms/NPCs/events.
- Events: E01–E33 in order and out of order; branch choices; rewards once.
- Christmas, New Year, Valentine, Gerard quiz, Blair reveal, Titan/Shadow Game, Goblin King, Yugi's deck, 7th Deck, walk-home, Dorothy truck, Chumley room.
- King of Games ending; post-game/name change.
- Save/load at each beat; autosave; corrupt save recovery.

### 7.4 Release-candidate gates

- [ ] 100% of §1.2.
- [ ] Zero P0/P1 bugs; P2 documented.
- [ ] 12-month playthrough completes in one session and across saves.
- [ ] 1,000 AI duels no stalls; 100/100 puzzles.
- [ ] 48/48 packs; 1,200/1,200 cards obtainable; Tier 2 effects 100%.
- [ ] 33+/33+ events; 12/12 exam cycles; 20+/20+ opponents.
- [ ] 60 fps at 1080p on target hardware; save < 1 s; fast travel < 2 s.
- [ ] Clean-checkout build + package passes.
- [ ] Legal audit clean; credits/README updated.

### 7.5 Legal/asset audit

- No ROM, `.sav`, emulator, or extracted ROM assets committed.
- Card scans/portraits remain local-only and are not added to a public build.
- Story text: exact GBA dialogue is local-only reference; runtime text should be a transformative port or original paraphrase unless the project owner accepts the fan-project risk. Keep a `LOCAL_ONLY` manifest and a public-build fallback.
- Music/SFX: no ripped tracks; only synthesized/original cues.
- Fab/third-party licenses unchanged; new assets get a `SOURCE.txt`/CREDITS entry.

---

## 8. Risk register

| Risk | Impact | Mitigation | Owner |
| --- | --- | --- | --- |
| 1,200-card effect coverage is enormous | Critical path; blocks shop/puzzles/story decks | Data-driven DSL, tiering, batch conversion, coverage audit; gate release on obtainable cards only until Tier 3 | A04/A05 |
| GBA story text not yet located/decoded | Story fidelity | A01 extraction spike; parallel fallback to event guide + original dialogue; systems use keys, not text | A01/A03 |
| GX vs. donor architecture divergence | Rework/merge pain | Port concepts/APIs; use GX naming; A10 contract headers; no blind copy | All |
| Interior work is large | Schedule risk | Prioritize story locations; portal cells; modular kit; roughed-in rooms first, polish later | A08 |
| Monolithic files cause conflicts | Merge loss | Split engine/UI early; one writer per file; worktrees; A10 merge gates | A04/A09/A10 |
| Obscure GBA rules/balance | Incorrect behavior | A01 canon extraction + tests; document deviations; use game3d as second reference | A01/A04 |
| Save corruption/migration | Player data loss | Versioned JSON, atomic writes, fuzz/migration tests, autosave | A02/A10 |
| 10 agents overrun the project | Chaos | Waves, gates, file ownership, no dirty tree, A10 as gatekeeper | A10 |
| Copyright/asset leakage | Legal | Local-only manifest, audit, no ripped assets committed | A10 |
| Link/trade scope creep | Delay | Explicit adaptation; offline trade/password stretch only | A06/A10 |
| Performance (1,200 cards, interiors, UI) | Poor release | Lazy data load, no permanent interior ticks, profiling gates | A08/A09/A10 |

---

## 9. Canon questions A01 must answer before content freeze

1. Exact exam pass mark and scoring weights (250 vs. 300; practical 300; written/timed values).
2. Exact 48 pack prices, pack size, rarity slots, card pools and unlock schedule.
3. Exact deck lists and evolution rules for all 20+ opponents, including ante and dorm variants.
4. Exact setups/solutions for all 100 timed puzzles; confirm one-turn vs. turn limit.
5. Full written-exam question bank and the Gerard quiz answers.
6. Story script/dialogue extraction status; control codes (`@5`, `@6`, `@7`, `$pNN`) and text encoding.
7. Save layout/flags, to validate event conditions and title counters.
8. Whether a side deck exists; copy limit; banned/limited list.
9. Exact event dates/conditions where the guide is vague (E19/E20/E25/E28/E30).
10. Which story events are mandatory vs. optional, and the exact ending trigger.
11. Whether link/trade features need offline equivalents for "full functionality".
12. Which original audio cues are essential; map to synthesized replacements.

---

## 10. Immediate next actions

1. **Protect the current work.** Commit or stash `C:\dev\GX`'s current WIP on a baseline branch before any subagent edits. Do not let agents start from the dirty tree.
2. **Create the baseline branch/worktrees.** A10 creates `port/baseline`, then `port/a01`…`port/a10`. Use one worktree per agent.
3. **Dispatch A01 + A10 first.** A01's extraction spike and A10's contracts unblock everyone else.
4. **Review Gate 0.** Freeze the schemas in §4.3–4.5; publish `Docs/Contracts/README.md`.
5. **Dispatch A02 + A04 + A09.** Start the profile/calendar/save skeleton, rules refactor and UI shell.
6. **Dispatch A03 + A06 + A08.** Build the opening vertical slice.
7. **Add A05 + A07** once the effect runtime and duel request/result contracts are stable.
8. **Run Gate 1 (opening hour) before content breadth.** Do not fill 33 events on an unproven stack.

**Suggested first message to each agent:** use the matching file in `Docs/AgentBriefs/` verbatim, plus:
> Read `Docs/PORT_MASTERPLAN.md` first. Work only in your owned files. Baseline is `port/baseline`. Do not touch another lane's files. Report files changed, tests run, API changes and blockers.

---

## Appendix A — Full GBA feature inventory (mapped)

| # | Feature | Original detail | Owner | Target file(s) |
| --- | --- | --- | --- | --- |
| 1 | New game/continue | Name entry, save slots, erase warning | A02/A09 | `DAProfileSubsystem`, save UI |
| 2 | Opening | Sheppard speech, registration, Slifer dorm, Banner DP, Syrus tutorial | A03 | `Story/E01` |
| 3 | Calendar | 12 months, Sunday–Saturday, AM/PM/Night | A02 | `DACalendarSubsystem` |
| 4 | Dorms | Slifer/Ra/Obelisk, rooms/cafeterias/headmasters, switching | A02/A03/A08 | profile, story, interiors |
| 5 | Titles | 12 permanent + temporary titles | A02 | `DATitleSystem` |
| 6 | DP | Canon formula, multipliers, event rewards, ante | A02/A04 | profile + duel result |
| 7 | Story events | 33+ events, conditions, choices, rewards | A03 | `Story/events.json` |
| 8 | NPC schedules | Weekday/period/location, event overrides | A03/A08 | schedules + director |
| 9 | Email/PDA | Contacts, messages, duel requests, records | A03/A09 | story emails + PDA UI |
| 10 | Duels | 8,000 LP, 1,200 cards, chains/targets/timing | A04/A05 | `DADuelEngine` |
| 11 | Deck construction | 40–60 main, 20 extra, 3 copies, banned/limited | A06 | `DADeckLogic` |
| 12 | Card trunk | Collection, list/detail, recipes | A06/A09 | inventory + UI |
| 13 | Shop | 48 packs, prices/unlocks/odds, Dorothy gift | A06 | `DAShopSubsystem` |
| 14 | Opponents | 20+ duelists, decks, evolution, dorm gates | A07 | `DAOpponentSubsystem` |
| 15 | AI | Deck-specific behavior, difficulty | A07 | `DADuelistAI` |
| 16 | Timed duels | 100 puzzles, 5 levels, solutions | A07 | `Puzzles/` |
| 17 | Exams | Written/timed/practical, 500 points, pass/fail | A07 | `DAExamSubsystem` |
| 18 | Dorm/rank outcomes | Promotion/demotion, Dropout Boy, exemptions | A02/A07 | title/dorm logic |
| 19 | Random/event duels | Titan, Shadow Game, Goblin King, etc. | A03/A07 | event + opponents |
| 20 | Social events | Walk-home, Christmas, New Year, Valentine, Chumley, Dorothy | A03 | events/dialogue |
| 21 | Save/load | PDA save, autosave, slots | A02/A09 | save subsystem + UI |
| 22 | Options | Animation speed, activation timing, audio | A02/A09 | settings + UI |
| 23 | Records | Wins, timed clears, exam %, collection | A02/A09 | counters + UI |
| 24 | Limitation list | Banned/limited cards | A04/A06 | rules + deck validation |
| 25 | Trade/link | GBA link cable | A06 (stretch) | offline equivalent |
| 26 | Password | Card password machine | A06 (optional) | offline equivalent |
| 27 | Ending | King of Games, name change, post-game | A03/A02 | story end + title |
| 28 | Tutorial | Syrus tutorial, quizzes/minigames | A03/A09 | story + UI |
| 29 | Tutorial mode | Standalone rules quizzes/minigames from the main menu | A03/A09 | tutorial UI/data |
| 30 | Audio | 30+ cues/BGM | A09/A10 | synthesized cues |
| 31 | Presentation | Portraits, expressions, effects | A09 | portrait/cutscene systems |

---

## Appendix B — GBA location → GX island mapping

| GBA location | GX target | Notes |
| --- | --- | --- |
| Duel Academy front | Academy plaza / main entrance | Existing zone; add scene anchor. |
| Classroom | Academy interior classroom | New interior cell. |
| Test room | Academy interior exam room | New interior cell; exam UI. |
| Duel Arena | Grand Duel Arena | Existing walk-in arena; add story duel anchors. |
| Gym | Duel Gym & Beach | Existing gym; add interior/exam practical anchor. |
| Dr. Crowler's room | Academy staff office | New interior cell. |
| Chancellor's office | Academy top-floor office | New interior cell; ending trigger. |
| Card shop | Academy Card Shop | Existing shop; replace fan cards with 48 packs. |
| Slifer Red — front | Slifer Red Dorm exterior | Existing. |
| Slifer Red — cafeteria | Slifer interior cafeteria | New interior cell. |
| Slifer Red — your room | Slifer interior dorm room | New interior cell; sleep/save. |
| Slifer Red — Banner's room | Slifer interior headmaster room | New interior cell; Pharaoh event. |
| Slifer Red — Jaden's room | Slifer interior bunk room | New interior cell; E03. |
| Ra Yellow — front | Ra Yellow Dorm exterior | Existing. |
| Ra Yellow — cafeteria | Ra interior cafeteria | New interior cell. |
| Ra Yellow — your room | Ra interior dorm room | New interior cell. |
| Obelisk Blue boys — front | Obelisk Blue Dorm exterior | Existing. |
| Obelisk Blue boys — dining | Obelisk interior dining room | New interior cell. |
| Obelisk Blue boys — your room | Obelisk interior dorm room | New interior cell. |
| Obelisk Blue girls — front | Obelisk Blue Girls' Dorm exterior | Existing; story trigger only. |
| Harbor | Harbor & Lighthouse | Existing. |
| Ocean / next to ocean | Beach / shore / lake overlook | Existing; add anchor. |
| Volcano — near crater | Volcano viewpoint/crater | Existing; Titan event. |
| Abandoned dorm | Abandoned Dorm | Existing; Shadow Game/Titan alternate. |
| Hot springs / forest / lighthouse | Existing island zones | Optional flavor/schedules. |

**Rule:** any mapping change is recorded in `Docs/Canon/LOCATION_MAP.md` and validated by A08/A10.

---

## Appendix C — Data-contract examples

### C.1 Event

```json
{
  "id": "E04a",
  "title": "Old Memories, Part 1",
  "when": { "weekday": "Sunday", "period": "AM" },
  "where": "any",
  "requirements": [
    { "type": "title_at_least", "value": "Average Duelist" },
    { "type": "flag", "flag": "met_syrus", "value": true }
  ],
  "scene": "scenes/e04a_old_memories.json",
  "outcomes": [
    { "type": "set_flag", "flag": "event_04a_cleared" },
    { "type": "grant_card", "card_id": 1161 }
  ],
  "once": true,
  "priority": 100
}
```

### C.2 Dialogue node

```json
{
  "key": "E01.sheppard_01",
  "speaker": "sheppard",
  "portrait": "sheppard_neutral",
  "text": "Welcome, new students, to Duel Academy!",
  "next": "E01.sheppard_02",
  "sfx": "A_UIVoice",
  "camera": "academy_gym_podium"
}
```

### C.3 Pack

```json
{
  "id": "basic_1a",
  "name": "1-A",
  "price": 150,
  "unlock": { "from_month": 1, "event": null },
  "cards_per_pack": 5,
  "slots": [
    { "rarity": "common", "count": 4 },
    { "rarity": "rare", "count": 1 }
  ],
  "pool": [1, 40, 115, 117]
}
```

### C.4 Puzzle

```json
{
  "id": "P001",
  "level": 1,
  "opponent": "mimicry",
  "seed": 1001,
  "turn_limit": 1,
  "time_limit": 60,
  "player": { "lp": 8000, "hand": [1, 40], "field": [], "graveyard": [] },
  "opponent": { "lp": 8000, "hand": [], "field": [{ "card_id": 319, "position": "attack" }], "graveyard": [] },
  "objective": "win_this_turn",
  "solution": [{ "action": "summon", "card_id": 1 }, { "action": "attack", "target": "direct" }],
  "reward": { "dp": 100 }
}
```

### C.5 Effect script

```json
{
  "card_id": 123,
  "name": "Example Card",
  "scripts": [
    {
      "trigger": "on_summon",
      "condition": { "controller": "self", "face_up": true },
      "cost": [{ "op": "pay_lp", "amount": 500 }],
      "target": { "zone": "opponent_monster", "filter": { "atk_max": 1500 }, "count": 1 },
      "operations": [{ "op": "destroy", "target": "$target" }],
      "optional": true,
      "spell_speed": 1
    }
  ]
}
```

---

## Appendix D — Source leads

### D.1 GBA ROM

- Card stats: `0xF243CC`, 1,200 × 4 bytes.
- Card names: `0xF25690`; name offsets `0xF2A68C`.
- Card descriptions: `0xF2B950`; description offsets `0xF58294`.
- UI/name/format strings: plain ASCII around `0x146C000`–`0x146D000`; full names `0x146CB14`; short names `0x146CC32`.
- Save crypto: `romhack/save_crypto.py`; test save `patched.sav`.
- ROM toolkit docs: `romhack/README.md`, `decompress_rom.py`.

### D.2 Public canon pages (secondary; use for gaps)

- `https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Events`
- `https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Opponents`
- `https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Timed_Duel_List`
- `https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Booster_Pack_List`
- `https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Starter_Decks`
- `https://yugipedia.com/wiki/Yu-Gi-Oh!_GX_Duel_Academy/Banned_List`
- Game manual PDF: `https://www.videogamemanual.com/gba/Yu-Gi-Oh!%20GX%20-%20Duel%20Academy%20(USA).pdf` (scanned, 80 pages).

### D.3 Donor code

- Rules reference: `C:\dev\argh\game3d\src\duel\engine.js`, `decklists.js`, `ui.js`.
- Native duel reference: `C:\dev\argh\ue5\Source\DuelAcademy\DuelEngine.*`, `DuelAcademyHUD.*`.
- Interiors: `C:\dev\argh\ue5\Source\DuelAcademy\AcademyInterior.cpp`, `SliferDorm.cpp`.
- Dialogue/NPC: `DialogueNpc.*`, `DuelAcademyGameMode.cpp`.
- Audio: `DuelAcademyAudio.*`, `docs/audio/AUDIO_GUIDE.md`.
- Art/layout: `art/world.layout.json`, `docs/art/*`.

### D.4 Target

- `DuelAcademyIsland/Source/DuelAcademyIsland/Public/*.h`
- `DuelAcademyIsland/Content/Data/*.json`
- `Tools/dai/*.py`, `Tools/dai/assets/*.py`
- `DuelAcademyIsland/Content/Python/duel_academy/*.py`

---

## Appendix E — Definition-of-done checklist (release)

Use this as the final gate; copy it into `Docs/PORT_STATUS.md` and tick it.

- [ ] Clean baseline + branch/worktree discipline followed.
- [ ] Opening hour playable with save/load.
- [ ] 12-month calendar and schedules.
- [ ] 33+ events, all reachable, no softlocks.
- [ ] 12 exam cycles, pass/fail/dropout/recovery.
- [ ] 100 timed puzzles, 100/100 validated.
- [ ] 48 packs, 1,200 cards obtainable.
- [ ] 20+ opponents, legal decks, deck evolution.
- [ ] 1,200 cards have data + effect manifest; all obtainable cards scripted.
- [ ] Deck editor, trunk, DP, titles, dorms, PDA.
- [ ] Every story location reachable; interiors work.
- [ ] UI complete, controller/mouse/keyboard, 1080p/4K.
- [ ] Save slots/autosave/migration/corruption recovery.
- [ ] 1,000 AI duels no stalls; 12-month simulation passes.
- [ ] Performance budgets met.
- [ ] Clean-checkout build/package passes.
- [ ] Legal audit clean; credits/docs updated.
- [ ] No P0/P1 bugs; known issues documented.
