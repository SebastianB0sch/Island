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

## Canon assumptions (pending A01)

- Exam day = last Friday of each month (`calendar.json` `exam.week`; change to
  `first`/`second`/`third`/`fourth` when A01 freezes the table).
- Exam pass mark `300`, dorm promotion `400` (`titles.json` `dorm_rules`).
- The 12 permanent title thresholds and temporary title list are conservative
  stubs, not final canon.
- New game: 3000 DP, Slifer Red, Apprentice Duelist, Saturday October 7 Year 1
  AM; October 1 Year 1 is treated as a Sunday so weekdays stay stable across
  the 12-month rollover (Year 1 is non-leap; school year 3 contains Feb 29).
