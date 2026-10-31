# A02 — Profile / Calendar / Save Integration

This document describes the runtime contracts added by A02. It is written for
A03/A06/A07/A09/A10; no shared file (`DATypes.h`, `DAGameMode.*`,
`DAIslandManager.*`, `DAStudentCharacter.*`, `DuelAcademyIsland.Build.cs`,
`Config/*.ini`) was modified.

## Subsystems

All five are `UGameInstanceSubsystem`s and are created automatically by
`UGameInstance::Init`; no `DefaultEngine.ini` change is required.

| Class | Header | Responsibility |
| --- | --- | --- |
| `UDAProfileSubsystem` | `DAProfileSubsystem.h` | identity, dorm, title, DP, flags, counters, email state, playtime, duel rewards |
| `UDACalendarSubsystem` | `DACalendarSubsystem.h` | school date, weekday, AM/PM/Night, exam days |
| `UDATitleSystem` | `DATitleSystem.h` | 12 permanent + temporary titles, dorm changes, Dropout Boy |
| `UDASaveSubsystem` | `DASaveGame.h` | 3 slots + autosave, atomic writes, backup, migration |
| `UDASettings` | `DASettings.h` | animation/text speed, activation confirm, audio, language, controls |

Data lives in `DuelAcademyIsland/Content/Data/Profile/`:
`titles.json`, `calendar.json`, `settings.json`.

## Initialization order (A09 / A10)

```cpp
UDAProfileSubsystem* Profile = GI->GetSubsystem<UDAProfileSubsystem>();
UDACalendarSubsystem* Calendar = GI->GetSubsystem<UDACalendarSubsystem>();
UDATitleSystem* Titles = GI->GetSubsystem<UDATitleSystem>();
UDASettings* Settings = GI->GetSubsystem<UDASettings>();
UDASaveSubsystem* Save = GI->GetSubsystem<UDASaveSubsystem>();

// New game:
Calendar->ResetToDefaults();          // Saturday, October 7, Year 1, AM
Profile->InitializeNewGame(Name);     // 3000 DP, Slifer, Apprentice Duelist
Titles->ApplyBestTitle(Profile);      // optional; evaluates the data table
Settings->LoadDefaults();             // automatic in Initialize anyway

// Continue:
FString Error;
Save->LoadSlot(SlotIndex, Error);     // applies profile + calendar + settings
```

`LoadSlot` applies calendar before profile internally, so `OnProfileLoaded`
observers see the loaded date. It must be used instead of constructing a
profile piecemeal.

## Autosave triggers

`UDAProfileSubsystem::RecordDuelResult` requests an autosave automatically.
The following call sites must request one explicitly (A09/A10 wiring):

```cpp
Save->RequestAutosave(TEXT("day_change"));      // after Sleep / AdvanceDay
Save->RequestAutosave(TEXT("exam_result"));     // after UDATitleSystem::ApplyExamOutcome
Save->RequestAutosave(TEXT("story_event"));     // after a completed event
Save->RequestAutosave(TEXT("pack_purchase"));   // after a successful shop transaction
```

Slot `0` is the autosave; slots `1..3` are manual. `EnumerateSlots()` always
returns four `FDASaveSlotInfo` entries. `bUsingBackup` means the primary was
corrupt and the `_backup` slot was loaded; `bCorrupt` means neither file could
be read.

## Save payload and extension providers

Schema version: `UDASaveSubsystem::CurrentVersion == 1`.

Root keys: `version`, `slot`, `slot_name`, `saved_at`, `meta`, `profile`,
`calendar`, `settings`, `flags`, `counters`, `emails`, plus optional
provider sections.

`calendar` is a root object written by
`UDACalendarSubsystem::WriteSaveData`. `ReadSaveData` also accepts the legacy
shape where `year`/`month`/`day`/`period` are at the root, so v0 payloads and
older fixtures still migrate. Do not move the calendar fields back to the root
of new saves.

Slot files are the serialized `UDASaveGame` memory archive plus a 16-byte
trailer (magic, format version, archive size, CRC32). Loads validate and strip
that trailer before calling `LoadGameFromMemory`, so a truncated or corrupted
file is reported as corrupt and recovered from the `_backup` slot instead of
being deserialized. This is why a deliberate 7-byte corrupt file can be handled
without an engine assertion.

A03/A06/A07 own their sections and should not add fields to `UDASaveGame`:

```cpp
class UDAInventorySubsystem : public UGameInstanceSubsystem, public IDASavePayloadProvider
{
    virtual FString GetSaveSectionName() const override { return TEXT("inventory"); }
    virtual bool WriteSaveSection(TSharedPtr<FJsonObject>& Out) const override;
    virtual bool ReadSaveSection(const TSharedPtr<FJsonObject>& In, FString& OutError) override;
};

Save->RegisterPayloadProvider(Inventory);
```

Reserved section names are rejected: `version`, `slot`, `slot_name`,
`saved_at`, `meta`, `profile`, `calendar`, `settings`, `flags`, `counters`,
`emails`, `sections`. Unknown root sections written by older/newer builds are
ignored, not deleted. Adding a new provider does not require a migration.

Migrations: `MigrateJson(Json, FromVersion, Error)` migrates in place to
`CurrentVersion`. Version `0` (the early flat prototype payload) is migrated to
v1: flat identity fields move into `profile`, `month` converts to
`month_index`, and legacy counters (`wins`, `timed`, `written`, `events`,
`cards`) are renamed. Newer versions are rejected with an error. There is no
v2 yet; add migration steps to `MigrateJson` when the schema changes.

## Inventory / deck handles

`UDAProfileSubsystem` never stores cards or decks. A06 should implement and
register:

```cpp
Profile->SetInventoryProvider(InventorySubsystem); // IDAProfileInventoryInterface
Profile->SetDeckProvider(DeckSubsystem);           // IDAProfileDeckInterface
```

`GetDistinctCardsOwned()` uses the provider, falling back to the `cards_owned`
counter for saves/tests without A06. Title evaluation calls it, so register the
provider before evaluating titles.

## Duel result contract

A04/A07 map their `FDuelResult` to `FDAProfileDuelResult`:

```cpp
FDAProfileDuelResult R;
R.OpponentId = Request.OpponentId;
R.Mode = Request.Mode;                  // "story" / "free" / "exam_timed" / "puzzle"
R.bPlayerWon = Result.bPlayerWon;
R.bDraw = Result.bDraw;
R.Turns = Result.Turns;
R.PlayerLp = Result.PlayerLp;
R.BattleDamageDealt = Result.BattleDamageDealt;
R.MonstersDestroyedByBattle = Result.MonstersDestroyedByBattle;
R.bWentSecond = bPlayerWentSecond;
R.WinCondition = EDAWinCondition::LifePoints; // or Exodia/DeckOut/FinalCountdown/DestinyBoard/Surrender
const int32 DP = Profile->RecordDuelResult(R);
```

Counters updated: `duels_total`, `wins_total`, `losses_total`, `draws_total`,
`wins_<opponent>`, `losses_<opponent>`, `battle_damage_total`,
`monsters_destroyed_total`, `lp_lost_total`, `timed_clears` (mode contains
"timed"/"puzzle"), `story_duels_won` (mode `story`).

## Titles and exams (A07)

```cpp
FDAExamOutcome Outcome = Titles->ApplyExamOutcome(Profile, Score, PassMark, bCanPromote);
// Pass: exams_passed++, may promote Slifer->Ra->Obelisk at PromotionScore (400 stub).
// Fail: demotes one dorm, sets dropout_boy/dropout flags, title = Dropout Boy.
bool bRecovered = Titles->RecoverFromDropout(Profile, bWonVsFondaFontaine);
```

`Titles->EvaluateTitle(Profile)` returns the best eligible title (temporary
title first, then Dropout Boy, then highest eligible permanent title).
`ForceTitle` is the debug/event override. `GrantTemporaryTitle(Profile, Id,
Days)` makes a temporary title active; `UDAProfileSubsystem::NotifyDayChanged`
ages it and falls back to the permanent title when it expires.

`ApplyExamOutcome` assumes the exam itself (written/timed/practical scoring) is
owned by A07. A02 only consumes the final score and pass mark.

## Island time bridge (A09/A10)

`ADAIslandManager` still owns the visual clock. The calendar owns the date.
Bridge without editing either file:

```cpp
Calendar->OnVisualHourChanged.AddDynamic(IslandBridge, &UIslandBridge::HandleHour);
void UIslandBridge::HandleHour(int32 Hour)
{
    if (ADAIslandManager* Manager = UDAIslandSubsystem::Get(this)->GetManager())
    {
        Manager->SetHour(static_cast<float>(Hour));
    }
}
// Initial sync:
Calendar->BroadcastVisualHour();
```

Do not let `ADAIslandManager` write back into `UDACalendarSubsystem`.

## Settings

`UDASettings` is included in every save payload. Changes are broadcast through
`OnSettingsChanged`; `Save()` requests an autosave. A09 can read
`GetAnimationSpeedScale()`, `GetTextSpeedCps()`, `GetBgmVolume()`,
`GetSfxVolume()`, `GetConfirmActivation()`, `GetSubtitles()`,
`GetLanguageKey()` and `GetControl(Action)` directly.

## Debug API

- Console: `da.ProfileSelfTest` — logs PASS/FAIL without exiting.
- Process: `DuelAcademyIsland.exe -DAProfileSelfTest` — logs, exits 0 on pass,
  1 on failure.
- C++: `Profile->InitializeNewGame`, `AwardDP`, `SetFlag`, `SetCounter`,
  `SetDorm`, `ForceTitle`, `SaveNow`, `Calendar->SetDate/SkipToDate`.

## Gate 3 scale tests (A02)

Two process-level switches cover the save/calendar scale gates. Both use the
real `UDAProfileSubsystem`, `UDACalendarSubsystem`, `UDASettings`,
`UDASaveSubsystem`, and the A06 `UDAInventorySubsystem` / `UDADeckLogic`
payload providers. They do not read or overwrite the golden saves in
`Content/Data/Integration/saves/`; all files are named `DASaveFuzz_*` or
`DATwelveMonth_*` and are deleted at the end. Implementation:
`DuelAcademyIsland/Source/DuelAcademyIsland/Private/DAA02GateTests.cpp`.

| Switch | Default | Purpose |
| --- | --- | --- |
| `-DASaveFuzz=N` | `N=10000` | random valid state round-trips, corruption/recovery, version/migration fuzz |
| `-DASaveFuzzSeed=S` | `0x5A02F022` | deterministic fuzz seed (decimal) |
| `-DATwelveMonthTest` | off | 365-day, 12-month calendar/profile simulation with save/load |

Console equivalents: `da.SaveFuzz [count] [seed]` and `da.TwelveMonthTest`.
Run each process switch separately; combining it with `-DAProfileSelfTest`
starts more than one exit ticker, so the process can exit after the first suite.

### `-DASaveFuzz=N`

Default counts:

- `N` valid states are built with random slots, names (including JSON escapes),
  genders, dorms, titles, temporary titles, DP, playtime, flags, counters,
  emails, dates/periods, settings/controls, inventory counts/ante and decks.
- `max(100, N/10)` corruption cases. For each case a known state A is saved,
  state B is saved over it (so A is the backup), then the primary file is
  flipped/truncated/duplicated/reordered/appended. Loading must recover A from
  the backup and deep-compare every field; the backup is then corrupted too and
  loading must fail cleanly with an error and `bCorrupt=true`, without deleting
  either file.
- `max(50, N/50)` migration cases. v0 flat payloads (with and without a JSON
  `version` field) are migrated in memory and as real v0 files, including the
  v0-JSON/v1-wrapper combination. Migrated names, dorm, title, gender, DP,
  fractional playtime, dates, flags, counters, settings defaults, meta and
  idempotence are checked. Future versions and invalid JSON are rejected.
- Per-batch `[PASS]`/`[FAIL]` lines are emitted for the roundtrip, corruption
  and migration batches, followed by:

```text
=== DASaveFuzz summary: 10000 states, 1000 corruption cases, 200 migration cases, <checks> checks, 0 failure(s), seed 0x5A02F022, max save size <bytes> bytes ===
DASaveFuzz PASSED.
```

A failed run ends with `DASaveFuzz FAILED.` and a non-zero process exit code.
Use `-DASaveFuzz=500` for a quick smoke run; the corruption/migration floors
still exercise every corruption mode and version variant.

```powershell
DuelAcademyIsland.exe -DAProfileSelfTest
DuelAcademyIsland.exe -DASaveFuzz=500
DuelAcademyIsland.exe -DASaveFuzz=10000 -DASaveFuzzSeed=1510141986
DuelAcademyIsland.exe -DATwelveMonthTest
```

### `-DATwelveMonthTest`

Starts at the canonical Saturday, October 7, Year 1, AM and advances 365 real
calendar days to October 7, Year 2. The random save-day stream is fixed at seed
`0x00012A02`, so runs are reproducible. Each day verifies:

- day/month/year rollover, month length, weekday, absolute-day monotonicity and
  no duplicate day or skipped month;
- AM (08:00) -> PM (14:00) -> Night (20:00) period rollover from
  `calendar.json` `period_hours`;
- exam days for every month: in range, configured weekday, `IsExamDayFor`, and
  `GetNextExamDate` agreement;
- story-style flags (`story_month_<m>_reached`, `exam_seen_<year>_<m>`) and
  birthday marker flags (`birthday_<m>`; see the ambiguity note below);
- non-negative DP/counters/playtime and INT_MAX clamping probes.

Save/load runs on every month boundary, on every exam day and on deterministic
random days. Before loading, the profile/calendar/settings/inventory/decks are
poisoned; loading must restore the exact date, DP, progress, flags, counters,
inventory counts/ante and deck payload. Output includes one
`[CHECKPOINT] Month n/12 ...` line per month and:

```text
=== DATwelveMonthTest summary: 365 days, 12 months, <n> saves, <n> loads, <n> random save days, <n> exam days, <checks> checks, 0 failure(s), max save size <bytes> bytes ===
DATwelveMonthTest PASSED.
```

### Defects fixed by these gates

- v0 migration truncated fractional `playtime_seconds` (it used an int32
  reader); the migration now uses a double-preserving move and also writes
  `meta.playtime_seconds`.
- A v0 payload with a JSON `version:0` archived with wrapper version 1 was not
  migrated because version 0 was treated as “missing”. JSON version 0 is now
  authoritative.
- Profile DP/temporary-title-day/counter reads could overflow on hostile or
  corrupted numeric input; they now clamp to `[0, INT_MAX]`.
- Calendar save-driven years are clamped to 9999 and absolute-day math is
  computed arithmetically, so a hostile year cannot spin an unbounded loop.
- Settings volume setters and profile playtime now reject non-finite values.

No existing public signature used by A03 was changed. The only new public
calendar surface is the non-breaking constant
`UDACalendarSubsystem::MaxSupportedYear`.

The harness registers A06's real `UDAInventorySubsystem` and `UDADeckLogic`
providers. If A06 changes its section schema, the harness may need a matching
update; A02's save/profile/calendar code is unaffected.

## Canon assumptions (pending A01)

- Exam day = last Friday of each month (`calendar.json` `exam.week`; change to
  `first`/`second`/`third`/`fourth` when A01 freezes the table). The exact week
  rule is still ambiguous: `Content/Data/Canon/calendar.json` records
  `exam_friday_default` as the last Friday with `exam_confidence: "low"`, while
  the November tournament story data describes a third-Friday rule. A02 keeps
  the data-driven `last` default until A01 freezes the table; A07's
  `UDAExamSubsystem::IsExamDay` only checks Friday, so it accepts any Friday.
- There is no birthday table or season field in the calendar/profile schema
  yet. The 12-month test plants `birthday_<month>` profile flags as markers and
  checks they survive; it does not invent canon birthdays. "Season" is
  represented only by the October..September month sequence and month names.
- Exam pass mark `300`, dorm promotion `400` (`titles.json` `dorm_rules`).
- The 12 permanent title thresholds and temporary title list are conservative
  stubs, not final canon.
- New game: 3000 DP, Slifer Red, Apprentice Duelist, Saturday October 7 Year 1
  AM; October 1 Year 1 is treated as a Sunday so weekdays stay stable across
  the 12-month rollover (Year 1 is non-leap; school year 3 contains Feb 29).
  `Year` is the school year (October..September), not the Gregorian year;
  January..September of school year N use calendar year N+1 for leap rules.
- A03 story content currently labels January..September as `year: 2` while
  this calendar keeps them in school Year 1 (rollover happens after September).
  A02 did not change `GetYear`/`SetDate`; story date conditions should key on
  `month_index` or normalize to the school-year label. This is an A03 content
  concern, not a calendar API change.
