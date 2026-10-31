# Story Runtime — Opening + Full Campaign Scaffold

> **Owner:** A03 (Director).
> **Files:** `DAStorySubsystem.h/.cpp`, `DAEventGraph.h/.cpp`.
> **Data:** `Content/Data/Story/opening.json`, `scenes/opening.json`, `dialogue/opening.json`, `schedules/opening.json`, plus the additive `events.json`, `scenes/full_campaign.json`, `dialogue/full_campaign.json`, `emails.json`.
> **Status:** compile-by-inspection pass; no UE build was run (the combined build is owned by A10/the user).

---

## 1. What this layer does

`UDAStorySubsystem` is a `UGameInstanceSubsystem` that owns:

- the loaded opening event graph (`FDAEventGraph`);
- the 35-event full-campaign scaffold merged into the same graph/maps;
- the serializable scene command queue;
- dialogue/choice resolution and A09 callback binding;
- event requirements/triggers/outcomes;
- A02 flags, counters, DP and calendar changes;
- A06 deck/card grants where an API exists;
- schedule lookups for A08;
- save/load of the story section;
- the `-DAOpeningTest` / `da.OpeningTest` opening runner;
- the headless `da.StorySelfTest` opening check;
- the headless `-DAFullStorySelfTest` / `da.FullStorySelfTest` 35-event audit;
- the in-engine `-DAStoryPlaythroughTest` / `da.StoryPlaythroughTest` E02-E33
  playthrough harness (see `Docs/Story/CAMPAIGN_PLAYTHROUGH.md`).

It does **not** draw UI, move NPCs, start cameras, or implement duel rules. Camera/MoveNpc/Fade/Banner/PlaySfx/Music are emitted as log/presentation cues until A08/A09 bind them; dialogue and duel entry use the existing A09 APIs.

---

## 2. Public API

```cpp
UDAStorySubsystem* Story = UDAStorySubsystem::Get(WorldContext);

// Data / flow
bool LoadOpeningData();
bool LoadFullCampaignData();   // additive; skips full E01, merges 34 events
bool IsFullCampaignLoaded() const;
int32 GetLoadedEventCount() const;
int32 GetEmailContactCount() const;
void StartOpening();          // resume/continue; uses current profile name
void StartOpeningFresh();     // clean run: reset profile/calendar, default Fire deck
void StartEvent(const FString& EventId); // e.g. "E01", "E02", "E04b"
bool CanStartEvent(const FString& EventId, FString& OutReason) const;
void Advance();               // automation/input bridge
void Choose(int32 OptionIndex);
bool IsRunning() const;
FString GetCurrentEventId() const;
FString GetCurrentSceneId() const;
int32 GetCurrentCommandIndex() const;

// New-game setup / identity
void SetPlayerName(const FString& NewName);
void SelectStarterDeck(const FString& DeckId); // fire, water or wind

// Duels
void NotifyDuelResult(bool bPlayerWon, bool bDraw); // preferred A04/A09 hook

// Schedules (A08 handoff)
bool GetScheduledNpcLocation(const FString& NpcId, const FString& Weekday,
    const FString& Period, FString& OutLocation, FString& OutAnchor);
bool GetScheduledNpcLocationNow(const FString& NpcId,
    FString& OutLocation, FString& OutAnchor);

// Save state (also registered as IDASavePayloadProvider section "story")
FString SaveState() const;
bool LoadState(const FString& Json, FString& OutError);

// Campaign playthrough / reward handoffs
bool RunStoryPlaythroughTest();
FString GetLastPlaythroughReport() const;
TArray<FString> GetPendingPackGrants() const;
bool ConsumePendingPackGrant(const FString& PackId);
TArray<FString> GetEmailContactIds() const;
TArray<FString> GetEmailMessageIds(const FString& ContactId) const;
TArray<FString> GetEmailDuelRequestIds(const FString& ContactId) const;
TArray<FString> GetUnlockedDuelIds() const;
bool IsDuelUnlocked(const FString& DuelId) const;
```

`StartOpeningFresh()` is not a `UFUNCTION`; the console/debug runner calls it. `StartOpening()` is the normal new-game/continue entry point.

### Recommended new-game wiring (A09/A06)

1. Create the profile: `Profile->InitializeNewGame(PlayerName)`.
2. Let the player choose a starter deck and call `Story->SelectStarterDeck(DeckId)`.
3. Call `Story->StartOpening()`.

If no deck was selected, the story selects **Fire** and sets `starter_deck_fire` / `starter_deck_chosen`. It records the choice in story state even when A06's deck provider is absent.

---

## 3. Opening flow / state machine

```text
StartOpeningFresh()
  -> Profile->InitializeNewGame("ALEX")
  -> Calendar->SetDate(1, 0, 1, AM)  // Oct 1 prologue
  -> EnsureStarterDeck("fire")
  -> StartEvent("E01")

E01: b01 -> b02 -> b03_registration -> b03_name_entry
     -> choice: name confirm
     -> b03_name_accepted -> b04 -> b05 -> b06_tutorial
     -> tutorial choice -> b06_tutorial_duel
     -> (headless: simulated win) b06_tutorial_win
     -> End(complete_event=true)
     -> E01 outcomes: flags, rewards, calendar -> Oct 7 AM
     -> TryStartNextAvailableEvent() -> E01b

E01b: b07_first_free_roam -> save/later choice
      -> b07_save | b07_free_roam
      -> End(enter_free_roam=true, complete_event=true)
      -> E01b outcomes: first_free_roam, shop_unlocked, save_unlocked,
         fast_travel_unlocked, opening_complete
      -> no auto-start for FJ01 (talk trigger)

FJ01 (optional, external talk):
  b08_jaden_intro -> accept | decline
  decline -> End(enter_free_roam=true, complete_event=false)
  accept  -> b08_jaden_duel_setup -> duel -> win/lose scene
          -> End(enter_free_roam=true, complete_event=true)
```

**Key rule:** `End.complete_event=false` leaves the event available (Jaden decline). `End.enter_free_roam=true` returns control to the player. `FinishEvent` applies event outcomes only when `complete_event=true`.

---

## 3A. Full campaign scaffold (35 events)

The full campaign is **additive**: `Initialize()` calls `LoadOpeningData()` and then `LoadFullCampaignData()`. The opening bundle stays authoritative; the full bundle is merged into the same `EventGraph`, `Scenes`, `Lines`, `Rewards` and `EmailContacts` maps.

| File | Contents |
| --- | --- |
| `Content/Data/Story/events.json` | 35 canon event records: `E01`–`E33`, `E04b`, `E28b`. Each has `id`, `title`, `canon_event`, `when`, `where`, `trigger`, `requirements`, `outcomes`, `rewards` (raw A01 audit copy), `once`, `priority`, `scene`, `dialogue_keys`, `canon_requirements`, `confidence`. |
| `Content/Data/Story/scenes/full_campaign.json` | 35 scenes, ids `full.<event>`, 5–8 commands each (limit 3–8). Uses the existing command schema. |
| `Content/Data/Story/dialogue/full_campaign.json` | 75 lines with stable keys `E02.01` …; every line is `source: "port-scaffold"`, with speaker, portrait hint and confidence. |
| `Content/Data/Story/emails.json` | 6 A01 contacts (Alexis, Chazz, Chumley, Jaden, Syrus, Zane), unlock event ids, scaffold messages and duel requests. |

**Opening protection:** full `E01` is present in `events.json` for the 35-event audit, but `LoadFullCampaignData()` excludes it from the graph merge. `opening.json` still owns the trigger, scene, dialogue and rewards for the opening.

### Event availability / translation

- A01 `wins_against` is translated to A02 counters (`wins_jaden`, `wins_syrus`, `wins_chumley`, etc.).
- Title/dorm conditions use the normalized A02 values (`Slifer Red`, `Ra Yellow`, `Obelisk Blue`).
- Month/day/period gates use `date`, `weekday`, `period`; a `date` without `day` means “any time in that month” (Duel Festival). A02's `Year` is the school year (October–September), so January–September after the opening are still Year 1.
- `exam_day` uses `UDACalendarSubsystem::IsExamDay()`.
- Card ownership uses `UDAInventorySubsystem` (`card` condition).
- `talk` events still need an external interaction caller (`StartEvent`), and are skipped by the auto-start path.
- Unsupported A01 concepts (exact chance rolls, multi-month hidden waits, per-duelist 10-win counts, minigames) are approximated and recorded in each event's `canon_requirements` / `notes`.

### Duel ids

A01 opponent/deck ids are mapped to the A07 roster/decks that exist today:

| A01 | A07 runtime |
| --- | --- |
| `jaden_year1` / `jaden_improved` | `jaden` / `jaden_year1` |
| `syrus_year1` | `syrus` / `syrus_roids` |
| `zane_year1` | `zane` / `zane_cyber` |
| `shadow_duelist_year1`, `jinzo_spirit` | `shadow_duelist` / `shadow_duelist_fiend` |
| `torrey_year1` | `torrey` / `torrey_insect` |
| `chazz_year1`, `chazz_ojama` | `chazz` / `chazz_ojama` |
| `brier_year1` | `brier` / `brier_quiz` |
| `beauregard_year1` | `beauregard` / `beauregard_rock` |
| `damon_exodia` | `damon` / `damon_exodia` |
| `yugi_deck` | `dimitri` / `dimitri_copycat` |
| `blair_year1` | `blair` / `blair_toon` |
| `bastion_seventh` | `bastion` / `bastion_chem` |
| `fontaine_year1` | `fontaine` / `fontaine_nurse` |
| `chumley_year1` | `chumley` / `chumley_koala` |
| `topher`, `conklin` | `topher` / `topher_goblin`, `conklin` / `conklin_dino` |

`goblin_king` and the `jinzo` spirit have no A07 runtime opponents yet; they use Brier / Shadow Duelist placeholders and are flagged in the event notes.

### Sequential duels

Multi-duel events (`E12`, `E16`, `E17`, `E19`, `E20`, `E28`) emit consecutive `duel` commands with empty `on_win`/`on_lose`/`on_draw`. `ResolvePendingDuel()` now advances to the next command when no result scene is set instead of finishing the event. A duel that does set a branch scene still jumps to it.

### Full campaign audit

`RunFullStorySelfTest()` (console `da.FullStorySelfTest`, command line `-DAFullStorySelfTest`) checks:

1. 35 canonical ids, unique ids, ids matching the read-only A01 canon manifest, and the merged event count.
2. each `full.<event>` scene exists, has 3–8 commands and only known command types;
3. every event `dialogue_keys` and every scene dialogue key resolves;
4. every A08 anchor used by the bundle exists (when `anchors.json` is readable);
5. every reward type is known, `pack` / `pack_by_dorm` ids exist in the A06 shop, and every `reward_id` outcome resolves;
6. every duel opponent/deck (events, scenes, email requests) exists in `Content/Data/Opponents/roster.json`;
7. 12-month availability (Oct Year 1 → Sep Year 2, all periods):
   - a **counterless** pass reports events unreachable without counters;
   - a **maxed-progress** pass grants all referenced flags/counters/events, all three dorms and the Dropout Boy title, and verifies all 35 events can become available;
8. `StartEvent` can resolve every canonical id and its runtime scene.

The audit snapshots and restores the live profile/calendar and removes any temporary test card, so it does not destroy save progress.

---

## 4. Command mapping

The scenes use the authored lowercase shape; `FDAStoryCommand::Type` uses the masterplan enum.

| JSON `type` | Enum | Runtime behavior |
| --- | --- | --- |
| `dialogue` | `Dialogue` | Resolves `key` in the merged opening/full-campaign line map, builds `FDADialogueLine`, calls `ADAHUD::BeginDialogueLine`. Blocks until `OnDialogueClosed`; the callback increments the command index and requests the next tick. |
| `choice` | `Choice` | Resolves the line, filters option requirements, builds a one-line `FDADialogueLine` with `bChoice=true`, calls `ADAHUD::BeginDialogue` with a unique conversation id. `OnChoiceMade` applies the option and jumps to `next_scene` + `next_key`. |
| `camera` | `Camera` | Logs the anchor (A08 can bind a camera request later). Non-blocking. |
| `move_npc` | `MoveNpc` | Logs npc/anchor (A08 director owns movement). Non-blocking. |
| `fade` | `Fade` | Logs mode/duration; non-blocking. |
| `wait` | `Wait` | Blocks for `duration` unless headless/fast-forward. The ticker increments the command index when the timer expires. |
| `banner` | `Banner` | Logs title/subtitle/style. Non-blocking. |
| `play_sfx` | `PlaySfx` | Logs cue id. Non-blocking. |
| `music` | `Music` | Logs track. Non-blocking. |
| `duel` | `Duel` | Captures opponent/deck/mode/result scenes, then calls `ADAHUD::OpenDuelDeckSelect(opponent, name, deck)`. Blocks; the ticker waits for the duel UI to close and infers the result from A02 counters (or uses `NotifyDuelResult`). With no `on_win/on_lose/on_draw`, the next command runs (sequential multi-duel events). |
| `reward` | `Reward` | Applies `reward_id` through the opening reward table; inline `dp`/`emails`/`deck_id`/`flags` are fallbacks. Idempotent by command/reward id. |
| `set_flag` | `SetFlag` | Calls `UDAProfileSubsystem::SetFlag`. Non-blocking. |
| `end` | `End` | If `next_scene` is set, starts it; otherwise finishes the event. Honors `complete_event` and `enter_free_roam`. |

### Choice/input details

- Choice options are the **filtered** `ActiveChoices`; `Choose(Index)` indexes into that filtered list, matching the UI buttons.
- The name-entry line has `input.kind = "text"`. A09 has no text-entry UI yet, so the runtime:
  - shows Mimicry's prompt as a normal line;
  - on close, applies the current profile name (default `ALEX`, max 8, uppercase) and advances to the confirmation choice.
- A09 can replace this later by calling `Story->SetPlayerName(Name)` from a real text-entry screen; the confirmation line then reads back the new name.
- Escape-close is disabled on choice lines; if the UI closes without a choice, the runtime takes option 0 to avoid a softlock.

### Re-entrancy rule

`OnDialogueClosed` / `OnChoiceMade` never call `BeginDialogue` or `BeginDialogueLine` synchronously. They set `bPendingContinue`; the subsystem ticker pumps the queue on the next tick. `Advance()` and `Choose()` are explicit automation/input bridges.

---

## 5. Event graph

`FDAEventGraph` loads the `events` array from `opening.json`, then merges `events.json` via `MergeFromJson()` (skipping full `E01`):

- `id`, `title`, `scene`, `priority`, `once`, `repeatable`, `optional`, `canon_event`;
- `trigger` (authored) and contract-compatible `date`/`location` fields;
- `requirements` (authored) and `requires` (contract alias);
- `outcomes` (authored) and `on_complete` (contract alias for flags/counters).

Supported triggers:

- `new_game` — profile `new_game` or `new_game_started`;
- `date` — year/month/day/weekday/period (month is the real calendar month, October = 10). Without `day`, the trigger matches the whole month;
- `weekday` / `period` / `exam_day` — direct calendar conditions;
- `flag` — flag condition;
- `event` / `event_complete` — completion flag;
- `talk` — caller-driven (auto-start skips it);
- `always`.

Supported conditions:

- `flag` (`id`/`flag`, boolean `value`);
- `counter` (`id`/`counter`, `op`, `value`);
- `event` / `event_complete` (`id`/`event`, `state=complete`);
- `date` / `date_at_least` (`year`, `month`/`calendar_month`, `day`, `op`, optional `weekday`/`period`; no `day` = whole month);
- `weekday`, `period`, `dorm` (normalizes `Slifer`/`Slifer Red`, etc.), `title`, `card` (`id`, `min_count`);
- `exam_day` — `UDACalendarSubsystem::IsExamDay()`;
- `all`/`any` nested groups (both `type:"all"` and `{ "all": [...] }` shapes);
- `talk`/`always`/`location` are pass-throughs (location is A08-owned);
- `duel_result`/`exam_result` are accepted but not evaluated yet.

`GetAvailableEvents` sorts by priority descending and skips completed `once` events. `TryStartNextAvailableEvent` auto-starts non-`talk` events; the optional Jaden duel is started only by a talk/interaction caller (`StartEvent("FJ01")`).

---

## 6. Rewards and progression

| Reward id | Runtime effect |
| --- | --- |
| `opening_starting_dp` | Ensures the profile has at least 3,000 DP. A02's default is already 3,000, so this does not double the budget. |
| `opening_email_contacts` | Unlocks Jaden, Syrus and Chumley email. |
| `opening_starter_deck_fire/water/wind` | Records `SelectedStarterDeck`, calls `IDAProfileDeckInterface::SetActiveDeckId` when A06 provides it, sets `starter_deck_<id>` and `starter_deck_chosen`. |

Persistent grants are idempotent by `reward_id` or `cmd:<command_id>` and are stored in the story save section. If a scene reward is replayed after load, it is skipped.

A02-owned duel counters (`wins_total`, `wins_jaden`, `wins_syrus`, `wins_chumley`, `duels_total`, etc.) are **not** applied by story outcomes; A02's `RecordDuelResult` owns them. Story-owned tutorial counters (`tutorial_duels_played`, `tutorial_duels_won`) are applied by E01 outcomes.

Cards are granted through `UDAInventorySubsystem::AddCard` when available (with
the profile `card_<id>` counter as a fallback). Packs are queued as unopened
grants in story state (`GetPendingPackGrants()` / `ConsumePendingPackGrant()`)
because A06 does not yet expose an unopened-pack inventory; the opening slice has
no pack reward.

Full-campaign outcomes additionally handle:

- `double_dp` / `dp_multiplier` — awards `current DP × (multiplier − 1)`;
- `exam_exemption` — sets `exam_exempt_next` plus `exam_exempt_<scope>`;
- `unlock_duel` — records `UnlockedDuels` and `duel_unlocked_<id>`;
- `item` — sets `item_<name>` and increments a matching counter;
- `temporary_title` / `restore_title` — uses A02 `SetTemporaryTitle` / `ClearTemporaryTitle` and remembers the previous title;
- `name_change` — sets `name_change_unlocked`;
- `grant_pack` - queues an unopened pack grant in `GetPendingPackGrants()` until A06 exposes an inventory hook.

---

## 7. Duels

### Tutorial

- Data: `mode: "free"`, `tutorial: true`, opponent `syrus`, deck `syrus_roids`, 4,000 LP, 10-turn limit, no DP, no win counter.
- Runtime: `ADAHUD::OpenDuelDeckSelect("syrus", "Syrus Truesdale", "syrus_roids")`.
- The frozen duel-mode enum has no `tutorial` value; the story uses `free` + `tutorial: true`. A04/A07 must honor the LP/turn overrides and must not call A02 `RecordDuelResult` for this practice match, or must pass a mode A02 treats as no-reward/no-counter.
- Loss is a valid branch (`b06_tutorial_lose`); the player can retry or continue. E01 completes either way.

### Optional Jaden free duel

- Data: `mode: "free"`, opponent `jaden`, deck `jaden`, 8,000 LP, DP by normal formula, counts as a win.
- Runtime: `ADAHUD::OpenDuelDeckSelect("jaden", "Jaden Yuki", "jaden")`.
- Loss completes FJ01 and unlocks repeatable free duels; there is no story gate.

### Result detection

The current HUD has no public duel-result callback. The story currently:

1. records `wins_jaden` / `wins_syrus` / `draws_total` before opening the duel;
2. polls `ADAHUD::IsDuelOpen()` each tick;
3. when the duel UI closes, infers win/draw/loss from the counter delta;
4. falls back to a loss if the duel UI never opens (10-second guard), avoiding a softlock.

**Preferred integration:** A04/A09/A10 should call `Story->NotifyDuelResult(bPlayerWon, bDraw)` as soon as the result is known. That bypasses the inference and is the only reliable path once A02 starts recording results differently.

---

## 8. Schedules for A08

`GetScheduledNpcLocation(NpcId, Weekday, Period, OutLocation, OutAnchor)`:

- reads `schedules/opening.json` `npcs{}`;
- evaluates `date_overrides` first (date + period + flag conditions), then base `entries` (weekdays + period + conditions);
- highest `priority` wins;
- returns the raw location id and anchor id.

`GetScheduledNpcLocationNow` uses A02's current weekday/period. The story does **not** move actors; A08's `DANpcDirector` owns spawn/move/despawn.

Example:

```cpp
FString Location, Anchor;
if (Story->GetScheduledNpcLocationNow(TEXT("jaden"), Location, Anchor))
{
    // A08: place/keep Jaden at (Location, Anchor)
}
```

---

## 9. Save/load

`UDAStorySubsystem` implements `IDASavePayloadProvider` and registers itself with A02 under section **`story`** when the reflected interface is available. If registration fails, `SaveState()`/`LoadState()` still work for custom hosts.

The section contains a `state` string with:

- `event`, `scene`, `command`, `running`, `free_roam`, `opening_started`;
- `starter_deck`;
- `completed` event ids;
- `applied_rewards` ids;
- `unlocked_duels` ids;
- `previous_title`;
- `objectives` map.

Load restores the current scene command array and index. Waiting flags are cleared; the next tick re-executes the blocking command (dialogue/choice) or re-opens the duel selector. Rewards are protected by `applied_rewards`.

**Known limitation:** saving in the middle of a duel and reloading re-opens the story duel selector rather than resuming the in-progress board. A04/A02 own mid-duel save; coordinate before enabling story saves during a duel.

---

## 10. Running the opening / full campaign

### Auto-run on launch

```powershell
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
  "C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  /Game/DuelAcademy/Maps/DuelAcademyIsland `
  -game -windowed -ResX=1920 -ResY=1080 -DAOpeningTest
```

`-DAOpeningTest` waits for the local player/HUD, then after ~2 seconds calls `StartOpeningFresh()`. It resets profile/calendar, selects Fire, and plays the opening. Do not combine it with `-DADuelScreenshot`, `-DADuelSelfTest`, `-DAUITest`, `-DAStorySelfTest`, `-DAFullStorySelfTest` or `-DAStoryPlaythroughTest` in one process.

`-DAFullStorySelfTest` is the headless audit-only switch: it waits ~2 seconds, then runs the 35-event audit without starting a scene. It does not need a HUD, so it works with `-nullrhi -game`.

### Console commands

| Command | Effect |
| --- | --- |
| `da.OpeningTest` | Start the opening on a fresh profile/calendar. |
| `da.StorySelfTest` | Run the headless opening self-test and log PASS/FAIL checks. |
| `da.FullStorySelfTest` | Run the headless 35-event full-campaign audit. |
| `da.StoryPlaythroughTest` | Run the in-engine E02-E33 playthrough harness. |
| `da.StoryStart E01` | Start a specific event (opening or full campaign). |
| `da.StoryName Alex` | Set the profile name (max 8, uppercased). |
| `da.StoryDeck fire` | Select/activate a starter deck (`fire`, `water`, `wind`). |
| `da.StoryAdvance` | Advance the current dialogue/queue for automation. |
| `da.StoryChoose 0` | Choose a pending option by filtered index. |
| `da.StoryState` | Log current event/scene/command/date/DP. |

### Headless self-test

```powershell
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
  "C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  /Game/DuelAcademy/Maps/DuelAcademyIsland `
  -game -nullrhi -DAStorySelfTest
```

The self-test resets the profile/calendar, runs E01 -> E01b with headless dialogue/choice handling and a simulated tutorial win, then checks:

- E01 and E01b completed;
- free roam reached;
- `registered`, `tutorial_complete`, `first_free_roam`, `shop_unlocked`, `save_unlocked`, `starter_deck_chosen` flags;
- DP exactly 3,000;
- calendar **Saturday, October 7, Year 1, AM**;
- command guard did not fire.

Expected log:

```text
StorySelfTest: PASS E01 completed
StorySelfTest: PASS E01b completed
StorySelfTest: PASS free roam
...
StorySelfTest: PASS in 0.xxx s
```

`RunSelfTest()` stores the same report in `GetLastSelfTestReport()`.

### Full campaign audit

```powershell
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
  "C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  /Game/DuelAcademy/Maps/DuelAcademyIsland `
  -game -nullrhi -DAFullStorySelfTest
```

Expected report shape (the exact unreachable list depends on gameplay counters):

```text
FullStorySelfTest: PASS full campaign loaded
FullStorySelfTest: PASS 35 canonical event ids
FullStorySelfTest: INFO 35 canonical events, 35 full scenes, ...
FullStorySelfTest: PASS every event has a loaded scene
FullStorySelfTest: PASS all dialogue keys resolve
FullStorySelfTest: PASS A07 opponent decks resolve
FullStorySelfTest: INFO 4/35 events reachable without counters
FullStorySelfTest: INFO unreachable without counters: E02, E03, ...
FullStorySelfTest: PASS all 35 events reachable with progress
FullStorySelfTest: PASS in 0.xxx s
```

The static bundle audit (run outside UE on 2026-10-30) found:

- 35 events / 35 scenes / 75 dialogue lines / 6 email contacts;
- 38 event duel records and 38 scene duel commands, all resolving to A07 roster ids and decks (plus 6 email duel requests);
- 218 commands total, every scene 5–8 commands;
- every camera/event anchor resolving in `Content/Data/World/anchors.json`;
- maxed-progress availability: **35/35**;
- counterless availability: 4/35 (`E01`, `E09`, `E11`, `E32`), with the remaining 31 gated by counters/flags/titles/prior events.

`Tools/validate/validate_all.py` also returns PASS for the bundle. Its remaining A03 warnings are the known `flag_unwritten` hooks (`post_game`, `walk_home_partner_3`) and `counter_unwritten` counters owned by A02/A04; the scene-bundle warnings are the same pre-contract bundle shape used by the opening.

### In-engine campaign playthrough

`-DAStoryPlaythroughTest` (console `da.StoryPlaythroughTest`) runs the real
E02-E33 scene queues, not just the data audit. It starts a fresh profile, plays
E01/E01b, advances A02 for 365 simulated days, starts every event when its
data gates are valid, drives `Advance`/`Choose(0)` and
`NotifyDuelResult(true, false)`, checks flags/DP/cards/emails/packs, and restores
the live save. See `Docs/Story/CAMPAIGN_PLAYTHROUGH.md` for the coverage table,
expected log lines and remaining blockers.

```powershell
& "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe" `
  "C:\dev\GX\DuelAcademyIsland\DuelAcademyIsland.uproject" `
  /Game/DuelAcademy/Maps/DuelAcademyIsland `
  -game -nullrhi -DAStoryPlaythroughTest
```

Expected aggregate result: **35/35 events started, 35/35 completed, 38/38
full-campaign duel commands plus the E01 tutorial (39/39 story duels), 0 missing
scenes/dialogue/commands, 6/6 email contacts**. E11/E28/E28b are canonically
Year 2 and are reported as beyond the first 365 days before the forced runtime
pass advances A02 to Year 2.

---

## 11. Integration hooks / current gaps

| Lane | Hook | Status |
| --- | --- | --- |
| **A02** | `InitializeNewGame`, `SetPlayerName`, `SetFlag`, `IncrementCounter`, `AwardDP`, `UnlockEmail`, `SetTitle`, `SetDorm`, `SetDate`, `IDASavePayloadProvider` | Connected. A02 default DP is 3,000; the opening reward ensures a minimum, not an addition. |
| **A09** | `BeginDialogue`, `BeginDialogueLine`, `GetDialogueUI`, `OnDialogueClosed`, `OnChoiceMade` | Connected. Name entry has no text-entry UI yet; runtime auto-fills the current/default name. Choice Escape-close is disabled. |
| **A08** | `GetScheduledNpcLocation`; camera/move cues are logged only | Schedule query ready. Six anchors are still requests: `gym_assembly_staff`, `slifer_cafeteria_seat_03`, `slifer_dorm_front_jaden`, `slifer_dorm_front_syrus`, `slifer_dorm_front_chumley`, `slifer_yard_practice`. NPC movement is intentionally not done here. |
| **A04/A07** | `NotifyDuelResult`; `OpenDuelDeckSelect` | Start connected. Result callback is missing on the HUD; current fallback infers from A02 counters. Tutorial uses `free` + `tutorial: true`, `syrus_roids`, 4,000 LP/10 turns. |
| **A06** | Deck provider `SetActiveDeckId`; `UDAInventorySubsystem::AddCard` | Deck activation works when A06 registers the provider. Story pack grants are queued in `GetPendingPackGrants()`; A06/A09 must consume them into an unopened-pack inventory. Starter deck UI should call `SelectStarterDeck`. |
| **A01 canon** | `Content/Data/Canon/*` | Read-only input. 35 event records and 6 email contacts are reflected in the scaffold; exact dialogue/message bodies remain local-only. |
| **A10** | `-DAOpeningTest`, `-DAStorySelfTest`, `-DAFullStorySelfTest`, console commands, save section `story` | Ready for the combined build. The full campaign is a bundle (one scene object per event inside `scenes/full_campaign.json`), not one file per event. |

### Blockers / next pass

1. **Name-entry UI (A09):** replace the `ALEX` auto-fill with a real 8-character entry screen and call `SetPlayerName`.
2. **Duel-result callback (A04/A09):** call `NotifyDuelResult`; otherwise win/loss is inferred from A02 counters.
3. **Tutorial result policy (A02/A04/A07):** do not award DP or wins for the `tutorial: true` practice match.
4. **Six A08 anchors:** publish them or retarget the scene/schedule references.
5. **Schedule actor movement (A08):** bind `GetScheduledNpcLocationNow` to `DANpcDirector`.
6. **Camera/fade/banner/SFX/music presentation (A08/A09):** currently logged; bind via a presentation delegate or direct calls when the APIs are stable.
7. **Canonical scene split (A10/A03):** `scenes/opening.json` and `scenes/full_campaign.json` are bundles; the frozen A10 layout wants one file per scene plus `Story/events.json`, `Story/dialogue.json`, `Story/schedules.json`.
8. **Exact dialogue / email bodies (A01):** the scaffold is faithful paraphrase only; exact canon text stays local-only.
9. **Story-only characters / minigames (A01/A07/A09):** Goblin King, Jinzo spirit, the Gerard quiz, the E04 one-turn puzzle, E20 ante rules, E28 bracket order, E29 LP-based DP and E31 partner-specific routes are placeholders.
10. **Exact anchors (A08):** the scaffold uses existing anchors only; event-specific anchor requests are listed in the data notes rather than silently retargeted.
11. **World progress flags (A08/A09/A10):** `stayed_in_room_three_weekends`, `walk_home_partner_3` and `post_game` still have no gameplay producer; the playthrough harness simulates them through A02 and logs them.
12. **Unopened pack inventory (A06):** story now queues pack grants in `GetPendingPackGrants()`; A06/A09 must consume them.

No shared C++/UI/world/save files were modified. No UE build was run in this pass.
