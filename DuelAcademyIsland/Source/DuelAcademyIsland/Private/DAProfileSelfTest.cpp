// Duel Academy Island - progression self-test.
//
// Run with:
//   DuelAcademyIsland.exe -DAProfileSelfTest
// or from the console:
//   da.ProfileSelfTest
//
// The command-line variant logs PASS/FAIL lines and exits with status 1 when
// any check fails. The console variant only logs, so it is safe inside PIE.

#include "DAProfileSelfTestSubsystem.h"
#include "DACalendarSubsystem.h"
#include "DAProfileSubsystem.h"
#include "DASaveGame.h"
#include "DASettings.h"
#include "DATitleSystem.h"
#include "DuelAcademyIsland.h"

#include "Containers/Ticker.h"
#include "Dom/JsonObject.h"
#include "Dom/JsonValue.h"
#include "Engine/GameInstance.h"
#include "HAL/FileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMisc.h"
#include "Kismet/GameplayStatics.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Parse.h"
#include "Serialization/JsonReader.h"
#include "Serialization/JsonSerializer.h"
#include "UObject/StrongObjectPtr.h"

namespace
{
	const TCHAR* const TestSlotName = TEXT("DAProfileSelfTest_Slot");

	struct FProfileSelfTestContext
	{
		TStrongObjectPtr<UGameInstance> GameInstance;
		UDAProfileSubsystem* Profile = nullptr;
		UDACalendarSubsystem* Calendar = nullptr;
		UDATitleSystem* Titles = nullptr;
		UDASettings* Settings = nullptr;
		UDASaveSubsystem* Save = nullptr;

		int32 Checks = 0;
		int32 Failures = 0;

		FProfileSelfTestContext()
			: GameInstance(NewObject<UGameInstance>(GetTransientPackage()))
		{
			Profile = NewObject<UDAProfileSubsystem>(GameInstance.Get());
			Calendar = NewObject<UDACalendarSubsystem>(GameInstance.Get());
			Titles = NewObject<UDATitleSystem>(GameInstance.Get());
			Settings = NewObject<UDASettings>(GameInstance.Get());
			Save = NewObject<UDASaveSubsystem>(GameInstance.Get());
		}

		bool Check(bool bCondition, const FString& Label)
		{
			++Checks;
			if (bCondition)
			{
				UE_LOG(LogDuelAcademyIsland, Log, TEXT("[PASS] %s"), *Label);
			}
			else
			{
				++Failures;
				UE_LOG(LogDuelAcademyIsland, Error, TEXT("[FAIL] %s"), *Label);
			}
			return bCondition;
		}

		bool CheckInt(int32 Actual, int32 Expected, const FString& Label)
		{
			return Check(Actual == Expected, FString::Printf(TEXT("%s (expected %d, got %d)"), *Label, Expected, Actual));
		}

		bool CheckString(const FString& Actual, const FString& Expected, const FString& Label)
		{
			return Check(Actual.Equals(Expected, ESearchCase::CaseSensitive),
				FString::Printf(TEXT("%s (expected '%s', got '%s')"), *Label, *Expected, *Actual));
		}

		bool CheckNear(double Actual, double Expected, double Tolerance, const FString& Label)
		{
			return Check(FMath::Abs(Actual - Expected) <= Tolerance,
				FString::Printf(TEXT("%s (expected %.3f, got %.3f)"), *Label, Expected, Actual));
		}

		bool CheckEnum(EDADorm Actual, EDADorm Expected, const FString& Label)
		{
			return Check(Actual == Expected, FString::Printf(TEXT("%s (expected %s, got %s)"), *Label,
				*DuelAcademyProfile::DormToSaveKey(Expected), *DuelAcademyProfile::DormToSaveKey(Actual)));
		}
	};

	bool ParseJsonRoot(const FString& Json, TSharedPtr<FJsonObject>& OutRoot)
	{
		OutRoot.Reset();
		const TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(Json);
		return FJsonSerializer::Deserialize(Reader, OutRoot) && OutRoot.IsValid();
	}

	void TestNewGame(FProfileSelfTestContext& Test)
	{
		Test.Profile->InitializeNewGame(TEXT("Self Test"));
		Test.CheckString(Test.Profile->GetPlayerName(), TEXT("Self Test"), TEXT("new game name"));
		Test.CheckInt(Test.Profile->GetDP(), 3000, TEXT("new game DP is 3000"));
		Test.CheckEnum(Test.Profile->GetDorm(), EDADorm::Slifer, TEXT("new game dorm is Slifer"));
		Test.CheckString(Test.Profile->GetTitle(), TEXT("Apprentice Duelist"), TEXT("new game title is Apprentice Duelist"));
		Test.Check(Test.Profile->IsInitialized(), TEXT("new game profile is initialized"));

		Test.Check(Test.Calendar->LoadCalendarData(), TEXT("calendar.json loads"));
		Test.CheckInt(Test.Calendar->GetYear(), 1, TEXT("start year"));
		Test.CheckInt(Test.Calendar->GetMonthIndex(), 0, TEXT("start month index (October)"));
		Test.CheckInt(Test.Calendar->GetMonthNumber(), 10, TEXT("start month number"));
		Test.CheckInt(Test.Calendar->GetDay(), 7, TEXT("start day"));
		Test.Check(Test.Calendar->GetWeekday() == EDADayOfWeek::Saturday, TEXT("start date is Saturday"));
		Test.Check(Test.Calendar->GetPeriod() == EDADayPeriod::AM, TEXT("start period is AM"));
		Test.CheckInt(Test.Calendar->GetHour(), 8, TEXT("start hour is 8"));
		Test.CheckString(Test.Calendar->GetDateText(), TEXT("Saturday, October 7"), TEXT("date text"));
	}

	void TestCalendar(FProfileSelfTestContext& Test)
	{
		Test.Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
		Test.Check(Test.Calendar->GetWeekday() == EDADayOfWeek::Sunday, TEXT("October 1 Year 1 is Sunday"));

		Test.Calendar->SetDate(1, 0, 7, EDADayPeriod::AM);
		Test.Calendar->AdvancePeriod();
		Test.Check(Test.Calendar->GetPeriod() == EDADayPeriod::PM, TEXT("AM advances to PM"));
		Test.Calendar->AdvancePeriod();
		Test.Check(Test.Calendar->GetPeriod() == EDADayPeriod::Night, TEXT("PM advances to Night"));
		Test.Calendar->AdvancePeriod();
		Test.CheckInt(Test.Calendar->GetDay(), 8, TEXT("Night advances to the next day"));
		Test.Check(Test.Calendar->GetPeriod() == EDADayPeriod::AM, TEXT("next day starts in AM"));
		Test.Check(Test.Calendar->GetWeekday() == EDADayOfWeek::Sunday, TEXT("next day weekday"));

		Test.Calendar->Sleep();
		Test.CheckInt(Test.Calendar->GetDay(), 9, TEXT("Sleep advances a day"));
		Test.Check(Test.Calendar->GetWeekday() == EDADayOfWeek::Monday, TEXT("Sleep weekday"));

		Test.Calendar->SetDate(1, 0, 7, EDADayPeriod::AM);
		const bool bSkipped = Test.Calendar->SkipToDate(2, 0, 7, EDADayPeriod::AM);
		Test.Check(bSkipped, TEXT("SkipToDate can advance one school year"));
		Test.CheckInt(Test.Calendar->GetYear(), 2, TEXT("skipped year"));
		Test.CheckInt(Test.Calendar->GetMonthIndex(), 0, TEXT("skipped month"));
		Test.CheckInt(Test.Calendar->GetDay(), 7, TEXT("skipped day"));
		Test.CheckInt(Test.Calendar->GetAbsoluteDay(), 371, TEXT("absolute day after one school year and six days"));
		Test.Check(Test.Calendar->GetWeekday() == EDADayOfWeek::Sunday, TEXT("weekday after one school year"));
		Test.Check(!Test.Calendar->SkipToDate(1, 0, 7, EDADayPeriod::AM), TEXT("SkipToDate rejects the past"));

		Test.CheckInt(Test.Calendar->GetDaysInMonth(1, 4), 28, TEXT("February Year 1 is not leap"));
		Test.CheckInt(Test.Calendar->GetDaysInMonth(3, 4), 29, TEXT("February of school year 3 is leap"));

		for (int32 MonthIndex = 0; MonthIndex < 12; ++MonthIndex)
		{
			const int32 ExamDay = Test.Calendar->GetExamDay(1, MonthIndex);
			Test.Check(ExamDay >= 1 && ExamDay <= Test.Calendar->GetDaysInMonth(1, MonthIndex),
				FString::Printf(TEXT("exam day is in range for month %d"), MonthIndex));
			Test.Check(Test.Calendar->IsExamDayFor(1, MonthIndex, ExamDay),
				FString::Printf(TEXT("IsExamDayFor recognizes month %d exam"), MonthIndex));
			Test.Check(Test.Calendar->GetWeekdayForDate(1, MonthIndex, ExamDay) == EDADayOfWeek::Friday,
				FString::Printf(TEXT("exam day is a Friday for month %d"), MonthIndex));
		}

		Test.Calendar->SetDate(1, 0, 7, EDADayPeriod::AM);
		int32 NextYear = 0;
		int32 NextMonth = 0;
		int32 NextDay = 0;
		Test.Check(Test.Calendar->GetNextExamDate(NextYear, NextMonth, NextDay), TEXT("GetNextExamDate returns a date"));
		Test.Check(Test.Calendar->GetWeekdayForDate(NextYear, NextMonth, NextDay) == EDADayOfWeek::Friday,
			TEXT("GetNextExamDate returns a Friday"));
	}

	void TestDP(FProfileSelfTestContext& Test)
	{
		FDAProfileDuelResult Result;
		Result.bPlayerWon = true;
		Result.Turns = 10;
		Result.PlayerLp = 4000;
		Result.BattleDamageDealt = 2000;
		Result.MonstersDestroyedByBattle = 3;

		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 310, TEXT("DP base formula"));

		Result.Turns = 50;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 155, TEXT("DP turn > 40 halves"));

		Result.Turns = 6;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 620, TEXT("DP turn < 7 doubles"));

		Result.Turns = 4;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 1550, TEXT("DP turn < 5 multiplies by five"));

		Result.Turns = 2;
		Result.bWentSecond = true;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 3100, TEXT("DP turn 2 going second multiplies by ten"));

		Result.Turns = 10;
		Result.bWentSecond = false;
		Result.PlayerLp = 8000;
		Result.BattleDamageDealt = 0;
		Result.MonstersDestroyedByBattle = 0;
		Result.WinCondition = EDAWinCondition::Exodia;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 600, TEXT("DP Exodia bonus"));
		Result.WinCondition = EDAWinCondition::DeckOut;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 600, TEXT("DP deck-out bonus"));
		Result.WinCondition = EDAWinCondition::FinalCountdown;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 1100, TEXT("DP Final Countdown bonus"));
		Result.WinCondition = EDAWinCondition::DestinyBoard;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 3100, TEXT("DP Destiny Board bonus"));
		Result.WinCondition = EDAWinCondition::LifePoints;
		Result.BonusDP = 100;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 200, TEXT("DP event bonus"));

		Result.BonusDP = 0;
		Result.bPlayerWon = false;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 0, TEXT("DP loss awards nothing"));
		Result.bPlayerWon = true;
		Result.WinCondition = EDAWinCondition::Surrender;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 0, TEXT("DP surrender awards nothing"));

		Result.WinCondition = EDAWinCondition::LifePoints;
		Result.PlayerLp = 9999;
		Result.BattleDamageDealt = -500;
		Result.MonstersDestroyedByBattle = -4;
		Result.Turns = 10;
		Test.CheckInt(UDAProfileSubsystem::CalculateDuelDP(Result), 100, TEXT("DP clamps invalid negative stats"));

		Test.Profile->InitializeNewGame(TEXT("Duelist"));
		FDAProfileDuelResult Win;
		Win.bPlayerWon = true;
		Win.Turns = 10;
		Win.PlayerLp = 4000;
		Win.BattleDamageDealt = 2000;
		Win.MonstersDestroyedByBattle = 3;
		Win.OpponentId = TEXT("jaden");
		Win.Mode = TEXT("free");
		const int32 Earned = Test.Profile->RecordDuelResult(Win);
		Test.CheckInt(Earned, 310, TEXT("RecordDuelResult awards the formula"));
		Test.CheckInt(Test.Profile->GetDP(), 3310, TEXT("RecordDuelResult increases DP"));
		Test.CheckInt(Test.Profile->GetCounter(TEXT("wins_total")), 1, TEXT("RecordDuelResult increments wins_total"));
		Test.CheckInt(Test.Profile->GetCounter(TEXT("duels_total")), 1, TEXT("RecordDuelResult increments duels_total"));
		Test.CheckInt(Test.Profile->GetCounter(TEXT("wins_jaden")), 1, TEXT("RecordDuelResult increments opponent wins"));
		Test.CheckInt(Test.Profile->GetCounter(TEXT("monsters_destroyed_total")), 3, TEXT("RecordDuelResult stores battle destroys"));

		FDAProfileDuelResult Loss = Win;
		Loss.bPlayerWon = false;
		Test.CheckInt(Test.Profile->RecordDuelResult(Loss), 0, TEXT("RecordDuelResult loss grants no DP"));
		Test.CheckInt(Test.Profile->GetDP(), 3310, TEXT("RecordDuelResult loss keeps DP"));
		Test.CheckInt(Test.Profile->GetCounter(TEXT("duels_total")), 2, TEXT("RecordDuelResult counts losses"));
	}

	void TestTitles(FProfileSelfTestContext& Test)
	{
		Test.Check(Test.Titles->LoadDefinitions(), TEXT("titles.json loads"));
		const TArray<FDATitleDefinition> Permanent = Test.Titles->GetPermanentTitles();
		Test.CheckInt(Permanent.Num(), 12, TEXT("12 permanent titles"));
		Test.Check(Test.Titles->GetTemporaryTitles().Num() >= 2, TEXT("temporary titles load"));

		Test.Profile->InitializeNewGame(TEXT("Title Test"));
		Test.CheckString(Test.Titles->EvaluateTitle(Test.Profile), TEXT("Apprentice Duelist"), TEXT("fresh profile title"));

		for (const FDATitleDefinition& Definition : Permanent)
		{
			if (Definition.bFailState)
			{
				continue;
			}
			Test.Profile->InitializeNewGame(TEXT("Title Test"));
			Test.Profile->SetCounter(TEXT("wins_total"), Definition.MinWinsTotal);
			Test.Profile->SetCounter(TEXT("duels_total"), Definition.MinDuelsTotal);
			Test.Profile->SetCounter(TEXT("timed_clears"), Definition.MinTimedClears);
			Test.Profile->SetCounter(TEXT("written_correct"), Definition.MinWrittenCorrect);
			Test.Profile->SetCounter(TEXT("cards_owned"), Definition.MinCardsOwned);
			Test.Profile->SetCounter(TEXT("story_events_cleared"), Definition.MinStoryEvents);
			if (Definition.MinDP > Test.Profile->GetDP())
			{
				Test.Profile->AwardDP(Definition.MinDP - Test.Profile->GetDP());
			}
			if (Definition.bRequiresExamPassed)
			{
				Test.Profile->SetCounter(TEXT("exams_passed"), 1);
				Test.Profile->SetFlag(TEXT("exam_passed"), true);
			}
			if (Definition.bRequiresKingOfGames)
			{
				Test.Profile->SetFlag(TEXT("king_of_games"), true);
			}
			if (!Definition.RequiredFlag.IsEmpty())
			{
				Test.Profile->SetFlag(Definition.RequiredFlag, true);
			}
			if (Definition.bRequiresDorm)
			{
				Test.Profile->SetDorm(Definition.RequiredDorm);
			}
			Test.CheckString(Test.Titles->EvaluateTitle(Test.Profile), Definition.Name,
				FString::Printf(TEXT("title threshold %s"), *Definition.Id));
		}

		Test.Profile->InitializeNewGame(TEXT("Temp Title"));
		Test.Check(Test.Titles->GrantTemporaryTitle(Test.Profile, TEXT("occult_duelist"), 2), TEXT("grant temporary title"));
		Test.CheckString(Test.Profile->GetTitle(), TEXT("Occult Duelist"), TEXT("temporary title is active"));
		Test.CheckString(Test.Titles->EvaluateTitle(Test.Profile), TEXT("Occult Duelist"), TEXT("evaluate prefers temporary title"));
		Test.Profile->NotifyDayChanged(1, 0, 8);
		Test.CheckInt(Test.Profile->GetTemporaryTitleDaysRemaining(), 1, TEXT("temporary title ages"));
		Test.Profile->NotifyDayChanged(1, 0, 9);
		Test.CheckString(Test.Profile->GetTemporaryTitle(), FString(), TEXT("temporary title expires"));
		Test.CheckString(Test.Profile->GetTitle(), TEXT("Apprentice Duelist"), TEXT("title reverts after expiry"));

		Test.Profile->InitializeNewGame(TEXT("Dorm Test"));
		FDAExamOutcome Passed = Test.Titles->ApplyExamOutcome(Test.Profile, 450, 300);
		Test.Check(Passed.Outcome == EDAExamOutcomeKind::Passed, TEXT("exam pass outcome"));
		Test.Check(Passed.bPromoted, TEXT("exam pass promotes Slifer to Ra"));
		Test.CheckEnum(Test.Profile->GetDorm(), EDADorm::Ra, TEXT("dorm after first promotion"));

		Passed = Test.Titles->ApplyExamOutcome(Test.Profile, 450, 300);
		Test.Check(Passed.bPromoted, TEXT("exam pass promotes Ra to Obelisk"));
		Test.CheckEnum(Test.Profile->GetDorm(), EDADorm::Obelisk, TEXT("dorm after second promotion"));

		FDAExamOutcome Failed = Test.Titles->ApplyExamOutcome(Test.Profile, 100, 300);
		Test.Check(Failed.Outcome == EDAExamOutcomeKind::Dropout, TEXT("exam fail is a dropout outcome"));
		Test.Check(Failed.bDemoted, TEXT("exam fail demotes one dorm"));
		Test.CheckEnum(Test.Profile->GetDorm(), EDADorm::Ra, TEXT("dorm after failed exam"));
		Test.CheckString(Test.Profile->GetTitle(), TEXT("Dropout Boy"), TEXT("failed exam sets Dropout Boy"));
		Test.Check(Test.Profile->GetFlag(TEXT("dropout_boy")), TEXT("failed exam sets the dropout flag"));

		Test.Check(Test.Titles->CanPromoteDorm(Test.Profile, 450), TEXT("promotion score allows promotion"));
		Test.Check(!Test.Titles->CanPromoteDorm(Test.Profile, 399), TEXT("low score blocks promotion"));

		Test.Check(Test.Titles->RecoverFromDropout(Test.Profile, true), TEXT("recovery duel clears dropout"));
		Test.Check(!Test.Profile->GetFlag(TEXT("dropout_boy")), TEXT("recovery clears the dropout flag"));
		Test.CheckString(Test.Profile->GetTitle(), TEXT("Apprentice Duelist"), TEXT("title after dropout recovery"));
	}

	void TestSave(FProfileSelfTestContext& Test)
	{
		FString Error;
		Test.Save->DeleteNamedSlot(TestSlotName, Error);

		Test.Profile->InitializeNewGame(TEXT("Self Test"));
		Test.Profile->AwardDP(1500);
		Test.Profile->SetFlag(TEXT("met_jaden"), true);
		Test.Profile->IncrementCounter(TEXT("wins_total"), 4);
		Test.Profile->IncrementCounter(TEXT("duels_total"), 6);
		Test.Profile->SetDorm(EDADorm::Ra);
		Test.Titles->ForceTitle(Test.Profile, TEXT("rookie_duelist"));
		Test.Profile->SetTemporaryTitle(TEXT("Occult Duelist"), 3);
		Test.Profile->UnlockEmail(TEXT("jaden"));
		Test.Profile->MarkEmailRead(TEXT("jaden"), TEXT("jaden_01"));
		Test.Profile->AddDuelRequest(TEXT("jaden"), TEXT("duel_01"));
		Test.Profile->AddPlaytime(125.0);
		Test.Calendar->SetDate(1, 3, 12, EDADayPeriod::PM);
		Test.Settings->SetBgmVolume(0.25f);
		Test.Settings->SetSfxVolume(0.5f);
		Test.Settings->SetTextSpeed(EDATextSpeed::Fast);
		Test.Settings->SetLanguageKey(TEXT("fr"));
		Test.Settings->SetControl(TEXT("Interact"), TEXT("F"));

		Test.Check(Test.Save->SaveNamedSlotWithContext(TestSlotName, 3, Test.Profile, Test.Calendar, Test.Settings, Error),
			FString::Printf(TEXT("save round-trip write: %s"), *Error));

		const FDASaveSlotInfo Info = Test.Save->GetSlotInfo(TestSlotName, 3);
		Test.Check(Info.bExists, TEXT("slot metadata exists"));
		Test.CheckString(Info.PlayerName, TEXT("Self Test"), TEXT("slot metadata name"));
		Test.CheckInt(Info.DP, 4500, TEXT("slot metadata DP"));
		Test.CheckString(Info.Title, TEXT("Occult Duelist"), TEXT("slot metadata title"));
		Test.CheckEnum(Info.Dorm, EDADorm::Ra, TEXT("slot metadata dorm"));
		Test.CheckInt(Info.Year, 1, TEXT("slot metadata year"));
		Test.CheckInt(Info.MonthIndex, 3, TEXT("slot metadata month"));
		Test.CheckInt(Info.Day, 12, TEXT("slot metadata day"));
		Test.Check(Info.Period == EDADayPeriod::PM, TEXT("slot metadata period"));

		Test.Profile->InitializeNewGame(TEXT("Mutated"));
		Test.Profile->SpendDP(1000);
		Test.Profile->SetDorm(EDADorm::Slifer);
		Test.Calendar->SetDate(1, 0, 1, EDADayPeriod::AM);
		Test.Settings->ResetToDefaults();

		bool bRecovered = false;
		Test.Check(Test.Save->LoadNamedSlotWithContext(TestSlotName, Test.Profile, Test.Calendar, Test.Settings, Error, &bRecovered),
			FString::Printf(TEXT("save round-trip load: %s"), *Error));
		Test.Check(!bRecovered, TEXT("clean load does not use the backup"));
		Test.CheckString(Test.Profile->GetPlayerName(), TEXT("Self Test"), TEXT("loaded name"));
		Test.CheckInt(Test.Profile->GetDP(), 4500, TEXT("loaded DP"));
		Test.Check(Test.Profile->GetFlag(TEXT("met_jaden")), TEXT("loaded flag"));
		Test.CheckInt(Test.Profile->GetCounter(TEXT("wins_total")), 4, TEXT("loaded counter"));
		Test.CheckEnum(Test.Profile->GetDorm(), EDADorm::Ra, TEXT("loaded dorm"));
		Test.CheckString(Test.Profile->GetTitle(), TEXT("Occult Duelist"), TEXT("loaded title"));
		Test.CheckString(Test.Profile->GetTemporaryTitle(), TEXT("Occult Duelist"), TEXT("loaded temporary title"));
		Test.CheckInt(Test.Profile->GetTemporaryTitleDaysRemaining(), 3, TEXT("loaded temporary title days"));
		Test.Check(Test.Profile->IsEmailUnlocked(TEXT("jaden")), TEXT("loaded email unlock"));
		Test.Check(Test.Profile->IsEmailRead(TEXT("jaden"), TEXT("jaden_01")), TEXT("loaded email read"));
		Test.Check(Test.Profile->HasPendingDuelRequest(TEXT("jaden")), TEXT("loaded duel request"));
		Test.CheckString(Test.Profile->GetPlaytimeText(), TEXT("02:05"), TEXT("loaded playtime"));
		Test.CheckInt(Test.Calendar->GetMonthIndex(), 3, TEXT("loaded calendar month"));
		Test.CheckInt(Test.Calendar->GetDay(), 12, TEXT("loaded calendar day"));
		Test.Check(Test.Calendar->GetPeriod() == EDADayPeriod::PM, TEXT("loaded calendar period"));
		Test.CheckNear(Test.Settings->GetBgmVolume(), 0.25, 0.001, TEXT("loaded BGM volume"));
		Test.CheckNear(Test.Settings->GetSfxVolume(), 0.5, 0.001, TEXT("loaded SFX volume"));
		Test.Check(Test.Settings->GetTextSpeed() == EDATextSpeed::Fast, TEXT("loaded text speed"));
		Test.CheckString(Test.Settings->GetLanguageKey(), TEXT("fr"), TEXT("loaded language"));
		Test.CheckString(Test.Settings->GetControl(TEXT("Interact")), TEXT("F"), TEXT("loaded control binding"));

		// Two saves leave the first state in the backup; corrupting the primary
		// must transparently recover it.
		Test.Profile->SetPlayerName(TEXT("State B"));
		Test.Profile->AwardDP(5499);
		Test.Check(Test.Save->SaveNamedSlotWithContext(TestSlotName, 3, Test.Profile, Test.Calendar, Test.Settings, Error),
			FString::Printf(TEXT("second save for backup: %s"), *Error));

		const FString PrimaryPath = UDASaveSubsystem::GetSaveFilePath(TestSlotName);
		Test.Check(FFileHelper::SaveStringToFile(TEXT("corrupt"), *PrimaryPath), TEXT("corrupt primary save file"));

		const FDASaveSlotInfo CorruptInfo = Test.Save->GetSlotInfo(TestSlotName, 3);
		Test.Check(CorruptInfo.bUsingBackup, TEXT("metadata reports backup recovery"));

		bRecovered = false;
		Test.Check(Test.Save->LoadNamedSlotWithContext(TestSlotName, Test.Profile, Test.Calendar, Test.Settings, Error, &bRecovered),
			FString::Printf(TEXT("load recovers from backup: %s"), *Error));
		Test.Check(bRecovered, TEXT("load reports backup recovery"));
		Test.CheckString(Test.Profile->GetPlayerName(), TEXT("Self Test"), TEXT("backup recovered name"));
		Test.CheckInt(Test.Profile->GetDP(), 4500, TEXT("backup recovered DP"));

		IFileManager::Get().Delete(*UDASaveSubsystem::GetSaveFilePath(FString(TestSlotName) + TEXT("_backup")), false);
		UGameplayStatics::DeleteGameInSlot(FString(TestSlotName) + TEXT("_backup"), 0);
		FFileHelper::SaveStringToFile(TEXT("corrupt again"), *PrimaryPath);
		const FDASaveSlotInfo Unrecoverable = Test.Save->GetSlotInfo(TestSlotName, 3);
		Test.Check(Unrecoverable.bCorrupt, TEXT("corrupt slot without backup is flagged"));
		Test.Check(!Test.Save->LoadNamedSlotWithContext(TestSlotName, Test.Profile, Test.Calendar, Test.Settings, Error),
			TEXT("corrupt slot without backup fails to load"));
		Test.Check(!Test.Save->GetLastError().IsEmpty(), TEXT("load failure records LastError"));

		Test.Save->DeleteNamedSlot(TestSlotName, Error);
		const FDASaveSlotInfo DeletedInfo = Test.Save->GetSlotInfo(TestSlotName, 3);
		Test.Check(!DeletedInfo.bExists, TEXT("delete slot removes the files"));

		Test.CheckInt(Test.Save->EnumerateSlots().Num(), 4, TEXT("four save slots enumerate"));
		Test.Check(UDASaveSubsystem::IsValidSlotIndex(0), TEXT("autosave slot index is valid"));
		Test.Check(!UDASaveSubsystem::IsValidSlotIndex(4), TEXT("out-of-range slot index is rejected"));

		// Version 0 (flat prototype payload) migration.
		FString Legacy = TEXT("{\"name\":\"Legacy\",\"dorm\":\"Ra Yellow\",\"title\":\"\",\"dp\":1234,\"month\":12,\"day\":20,\"period\":\"PM\",\"flags\":{\"registered\":true},\"counters\":{\"wins\":7}}");
		Test.Check(Test.Save->MigrateJson(Legacy, 0, Error), FString::Printf(TEXT("migrate v0 payload: %s"), *Error));
		Test.CheckInt(UDASaveSubsystem::GetVersionFromJson(Legacy), 1, TEXT("migrated payload is version 1"));

		TSharedPtr<FJsonObject> LegacyRoot;
		Test.Check(ParseJsonRoot(Legacy, LegacyRoot), TEXT("migrated payload parses"));
		if (LegacyRoot.IsValid())
		{
			const TSharedPtr<FJsonObject>* LegacyProfile = nullptr;
			LegacyRoot->TryGetObjectField(TEXT("profile"), LegacyProfile);
			Test.Check(LegacyProfile && LegacyProfile->IsValid(), TEXT("migrated payload has a profile"));
			if (LegacyProfile && LegacyProfile->IsValid())
			{
				FString Name;
				int32 DP = 0;
				(*LegacyProfile)->TryGetStringField(TEXT("name"), Name);
				(*LegacyProfile)->TryGetNumberField(TEXT("dp"), DP);
				Test.CheckString(Name, TEXT("Legacy"), TEXT("migration preserves name"));
				Test.CheckInt(DP, 1234, TEXT("migration preserves DP"));
			}
			const TSharedPtr<FJsonObject>* LegacyCalendar = nullptr;
			LegacyRoot->TryGetObjectField(TEXT("calendar"), LegacyCalendar);
			if (LegacyCalendar && LegacyCalendar->IsValid())
			{
				int32 MonthIndex = -1;
				(*LegacyCalendar)->TryGetNumberField(TEXT("month_index"), MonthIndex);
				Test.CheckInt(MonthIndex, 2, TEXT("migration converts December to month index"));
			}
			const TSharedPtr<FJsonObject>* LegacyCounters = nullptr;
			LegacyRoot->TryGetObjectField(TEXT("counters"), LegacyCounters);
			if (LegacyCounters && LegacyCounters->IsValid())
			{
				int32 Wins = 0;
				(*LegacyCounters)->TryGetNumberField(TEXT("wins_total"), Wins);
				Test.CheckInt(Wins, 7, TEXT("migration renames legacy wins counter"));
			}
		}

		FString Future = TEXT("{\"version\":99}");
		Test.Check(!Test.Save->MigrateJson(Future, 99, Error), TEXT("newer save version is rejected"));
	}

	bool RunProfileSelfTest()
	{
		UE_LOG(LogDuelAcademyIsland, Display, TEXT("=== DA profile/calendar/save self-test ==="));

		FProfileSelfTestContext Test;
		TestNewGame(Test);
		TestCalendar(Test);
		TestDP(Test);
		TestTitles(Test);
		TestSave(Test);

		UE_LOG(LogDuelAcademyIsland, Display, TEXT("=== DA profile/calendar/save self-test: %d checks, %d failure(s) ==="), Test.Checks, Test.Failures);
		if (Test.Failures > 0)
		{
			UE_LOG(LogDuelAcademyIsland, Error, TEXT("DAProfileSelfTest FAILED."));
			return false;
		}
		UE_LOG(LogDuelAcademyIsland, Display, TEXT("DAProfileSelfTest PASSED."));
		return true;
	}

	void RunConsoleSelfTest(UWorld* World)
	{
		(void)World;
		RunProfileSelfTest();
	}

	FAutoConsoleCommandWithWorld GProfileSelfTestCommand(
		TEXT("da.ProfileSelfTest"),
		TEXT("Run the profile/calendar/title/save self-test. Usage: da.ProfileSelfTest"),
		FConsoleCommandWithWorldDelegate::CreateStatic(&RunConsoleSelfTest));
}

void UDAProfileSelfTestSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
	Super::Initialize(Collection);
	if (FParse::Param(FCommandLine::Get(), TEXT("DAProfileSelfTest")))
	{
		TickerHandle = FTSTicker::GetCoreTicker().AddTicker(
			FTickerDelegate::CreateUObject(this, &UDAProfileSelfTestSubsystem::Tick), 0.5f);
	}
}

void UDAProfileSelfTestSubsystem::Deinitialize()
{
	if (TickerHandle.IsValid())
	{
		FTSTicker::GetCoreTicker().RemoveTicker(TickerHandle);
		TickerHandle.Reset();
	}
	Super::Deinitialize();
}

bool UDAProfileSelfTestSubsystem::Tick(float DeltaSeconds)
{
	(void)DeltaSeconds;
	const bool bPassed = RunProfileSelfTest();
	FPlatformMisc::RequestExitWithStatus(false, bPassed ? 0 : 1, TEXT("DAProfileSelfTest"));
	return false;
}
